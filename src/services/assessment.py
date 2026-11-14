"""Application service layer shared by the Streamlit UI and tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.analysis.risk_to_plan_exploration import (
    COURSES_PATH,
    HK1_APPROVED,
    HK1_ENROLLED,
    PREREQUISITES_PATH,
    PROFILE_PATH,
    PROGRESS_PATH,
    _read_csv,
)
from src.optimize.ilp_prototype import compute_unlock_values, solve_plan
from src.optimize.plan_risk import M3_ABILITY_ORDER, m3_prime_probability
from src.rules.rule_engine import evaluate_student, load_rules

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "artifacts" / "risk_bundle.joblib"

TIER_LABELS = {
    "low": "Thấp",
    "medium": "Trung bình",
    "high": "Cao",
}


def load_bundle(path: Path = BUNDLE_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Chưa có artifact mô hình tại {path}. "
            "Chạy: python scripts/train_and_save_models.py"
        )
    return joblib.load(path)


def load_curriculum() -> dict[str, Any]:
    courses = _read_csv(COURSES_PATH).to_dict("records")
    prerequisites = _read_csv(PREREQUISITES_PATH).to_dict("records")
    profiles = _read_csv(PROFILE_PATH)
    progress = _read_csv(PROGRESS_PATH)
    for course in courses:
        course["credits"] = int(course["credits"])
        course["planned_semester"] = int(course["planned_semester"])
    return {
        "courses": courses,
        "prerequisites": prerequisites,
        "profiles": profiles,
        "progress": progress,
        "course_by_id": {course["course_id"]: course for course in courses},
    }


def persona_payload(
    curriculum: dict[str, Any], student_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    profiles = curriculum["profiles"]
    matched = profiles[profiles["student_id"] == student_id]
    if matched.empty:
        raise ValueError(f"Không tìm thấy persona {student_id}.")
    profile = {
        key: (None if pd.isna(value) else value)
        for key, value in matched.iloc[0].to_dict().items()
    }
    progress = curriculum["progress"]
    rows = progress[progress["student_id"] == student_id]
    progress_rows = [
        {
            key: (None if pd.isna(value) else value)
            for key, value in row.items()
        }
        for row in rows.to_dict("records")
    ]
    return profile, progress_rows


def ability_tier(hk1_rate: float, cut_points: list[float]) -> str:
    if hk1_rate < cut_points[0]:
        return M3_ABILITY_ORDER[0]
    if hk1_rate < cut_points[1]:
        return M3_ABILITY_ORDER[1]
    return M3_ABILITY_ORDER[2]


def predict_dropout(
    profile: dict[str, Any], bundle: dict[str, Any]
) -> tuple[float, float]:
    frame = pd.DataFrame(
        [{feature: profile[feature] for feature in bundle["features"]}],
        columns=bundle["features"],
    )
    model = bundle["dropout_model"]
    class_index = list(model[-1].classes_).index("Dropout")
    raw = float(model.predict_proba(frame)[0][class_index])
    calibrated = float(bundle["risk_calibrator"].predict([raw])[0])
    return raw, min(max(calibrated, 0.0), 1.0)


def predict_pass_rate(
    profile: dict[str, Any], bundle: dict[str, Any]
) -> float:
    frame = pd.DataFrame(
        [{feature: profile[feature] for feature in bundle["features"]}],
        columns=bundle["features"],
    )
    return float(
        min(max(bundle["pass_rate_model"].predict(frame)[0], 0.0), 1.0)
    )


def assess_student(
    profile: dict[str, Any],
    progress_rows: list[dict[str, Any]],
    curriculum: dict[str, Any],
    bundle: dict[str, Any],
    rules: dict[str, Any],
    *,
    use_ml: bool,
) -> dict[str, Any]:
    if use_ml:
        p_dropout, p_calibrated = predict_dropout(profile, bundle)
    else:
        p_dropout, p_calibrated = 0.0, None

    rule_result = evaluate_student(
        profile,
        curriculum["courses"],
        curriculum["prerequisites"],
        progress_rows,
        next_semester=int(profile["current_semester"]) + 1,
        p_dropout=p_dropout,
        p_dropout_calibrated=p_calibrated,
        rules=rules,
    )

    enrolled = float(profile.get(HK1_ENROLLED, 0) or 0)
    approved = float(profile.get(HK1_APPROVED, 0) or 0)
    hk1_rate = approved / enrolled if enrolled > 0 else 0.0
    tier = ability_tier(hk1_rate, bundle["ability_cut_points"])
    p_m3_prime = m3_prime_probability(
        tier,
        bundle["pooled_strata"],
        minimum_students=int(
            rules["risk_to_plan_exploration"]["m3_prime"]["minimum_students"]["value"]
        ),
    )
    p_pass_model = predict_pass_rate(profile, bundle) if use_ml else None

    return {
        "profile": profile,
        "progress_rows": progress_rows,
        "rule_result": rule_result,
        "p_dropout": p_dropout if use_ml else None,
        "p_dropout_calibrated": p_calibrated if use_ml else None,
        "risk_estimated": use_ml,
        "risk_label": (
            TIER_LABELS[rule_result["risk_tier"]] if use_ml else "Chưa ước lượng"
        ),
        "risk_note": (
            "P(Dropout) từ mô hình exploratory; chỉ để cảnh báo, không nhân vào p_pass."
            if use_ml
            else "Thiếu 24 feature T0/T1-known nên không ước lượng P(Dropout); "
            "lộ trình dùng baseline M3' và tầng trung bình (GIẢ ĐỊNH)."
        ),
        "ability_tier": tier,
        "p_pass_m3_prime": p_m3_prime,
        "p_pass_model": p_pass_model,
        "planning_tier": rule_result["risk_tier"] if use_ml else "medium",
    }


def build_plans(
    assessment: dict[str, Any],
    curriculum: dict[str, Any],
    bundle: dict[str, Any],
    rules: dict[str, Any],
    *,
    budgets: list[int] | None = None,
    load_lambda: float = 0.1,
    retake_multiplier: float = 1.0,
) -> list[dict[str, Any]]:
    budgets = budgets or [
        int(value) for value in rules["scenario_credit_targets"]["values"]
    ]
    rule_result = assessment["rule_result"]
    eligible = rule_result["eligible_courses"]
    statuses = {
        str(row["course_id"]): str(row.get("status", "not_taken"))
        for row in assessment["progress_rows"]
    }
    credits_by_course = {
        course["course_id"]: float(course["credits"])
        for course in curriculum["courses"]
    }
    unlock = compute_unlock_values(
        [course["course_id"] for course in eligible],
        curriculum["prerequisites"],
        statuses,
        credits_by_course=credits_by_course,
        discount_per_edge=float(
            rules["optimization"]["unlock_discount_per_edge"]["value"]
        ),
    )
    course_factors = {
        course["course_id"]: float(
            bundle["difficulty_factors"].get(course.get("group"), 1.0)
        )
        for course in eligible
    }
    tier = assessment["planning_tier"]
    expected_fail_cap = float(
        rules["rule_engine"]["risk_tiers"]["expected_failed_course_caps"][tier]
    )
    graduation_ready = any(
        flag.get("code") == "GRADUATION_CREDITS_MET"
        for flag in rule_result["edge_case_flags"]
    )

    results: list[dict[str, Any]] = []
    for budget in budgets:
        scenario_max = budget
        if rule_result["enforce_cap"] and rule_result["load_restriction_recommended"]:
            scenario_max = min(
                scenario_max, int(rule_result["recommended_credit_cap"])
            )
        result = solve_plan(
            eligible,
            p_student_m3_prime=float(assessment["p_pass_m3_prime"] or 0.0),
            load_lambda=load_lambda,
            risk_tier=tier,
            scenario_credit_max=scenario_max,
            expected_fail_cap=expected_fail_cap,
            average_credits_per_unit=float(
                bundle["average_credits_per_unit"]
            ),
            median_real_load_units=6,
            unlock_values=unlock,
            beta=float(rules["optimization"]["beta_unlock_value"]["value"]),
            gamma=float(rules["optimization"]["gamma_failure_penalty"]["value"]),
            minimum_credits=int(
                rules["semester_credit_limits"]["minimum"]["value"]
            ),
            relaxed_minimum_credits=int(
                rules["optimization"]["c_min_relaxed"]["value"]
            ),
            course_factors=course_factors,
            retake_multiplier=retake_multiplier,
            status_by_course=statuses,
            prerequisite_rows=curriculum["prerequisites"],
            require_blocking_retakes=bool(
                rules["optimization"]["required_retake_courses"]["value"]
            ),
            enforce_cap=bool(rule_result["enforce_cap"]),
            risk_cap_slack_penalty=float(
                rules["optimization"]["risk_cap_slack_penalty"]["value"]
            ),
            graduation_ready=graduation_ready,
        )
        p_by_course = result.get("p_pass_by_course", {})
        selected = [
            {
                **curriculum["course_by_id"][course_id],
                "status": statuses.get(course_id, "not_taken"),
                "p_pass": float(p_by_course.get(course_id, 0.0)),
            }
            for course_id in result.get("selected_course_ids", [])
        ]
        results.append(
            {
                "budget": budget,
                "scenario_credit_max": scenario_max,
                "load_lambda": load_lambda,
                "result": result,
                "selected_courses": selected,
            }
        )
    return results


def default_rules() -> dict[str, Any]:
    return load_rules()
