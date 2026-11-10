"""Reproducible Stage 1 prototype run for a small PuLP/HiGHS model."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.risk_to_plan_exploration import run_exploration  # noqa: E402
from src.optimize.ilp_prototype import compute_unlock_values, solve_plan  # noqa: E402
from src.rules.rule_engine import evaluate_student  # noqa: E402

CONFIG_PATH = ROOT / "src" / "config" / "credit_rules.yaml"
COURSES_PATH = ROOT / "data" / "processed" / "courses.csv"
PREREQUISITES_PATH = ROOT / "data" / "processed" / "prerequisites.csv"
PROGRESS_PATH = ROOT / "data" / "processed" / "student_progress.csv"
PROFILE_PATH = ROOT / "data" / "processed" / "student_profile.csv"
PERSONA_IDS = ("S001", "S002", "S003", "S005")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def run_prototype() -> dict[str, Any]:
    """Run the rule-to-ILP prototype on REAL-derived SIMULATED personas."""
    with CONFIG_PATH.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    rules = config
    experiment = run_exploration()
    courses = _read_csv(COURSES_PATH)
    prerequisites = _read_csv(PREREQUISITES_PATH)
    progress = _read_csv(PROGRESS_PATH)
    profiles = {
        row["student_id"]: row for row in _read_csv(PROFILE_PATH)
    }
    persona_result = (
        experiment["persona"]["table"]
        .drop_duplicates("student_id")
        .set_index("student_id")
    )
    dropout_model = experiment["dropout_model"]["full_model_for_persona_sanity_only"]
    features = experiment["features"]
    class_index = list(dropout_model[-1].classes_).index("Dropout")
    average_credits = float(experiment["persona"]["average_credits_per_unit"])
    load_values = [
        float(value)
        for value in config["optimization"]["load_lambda_sensitivity"]["values"]
    ]
    scenario_credits = [
        int(value) for value in config["scenario_credit_targets"]["values"]
    ]
    difficulty_factors = experiment["persona"]["difficulty_factors"]
    risk_thresholds = experiment["dropout_model"]["risk_tier_validation_thresholds"]
    risk_calibrator = risk_thresholds["risk_probability_calibrator"]
    results: list[dict[str, Any]] = []
    sensitivities: list[dict[str, Any]] = []
    recommendation_rows: list[dict[str, Any]] = []
    course_credits = {
        row["course_id"]: float(row["credits"]) for row in courses
    }

    for student_id in PERSONA_IDS:
        profile = profiles[student_id]
        profile_features = pd.DataFrame(
            [{feature: float(profile[feature]) for feature in features}],
            columns=features,
        )
        p_dropout = float(
            dropout_model.predict_proba(profile_features)[0][class_index]
        )
        p_dropout_calibrated = float(
            risk_calibrator.predict([p_dropout])[0]
        )
        rule_result = evaluate_student(
            profile,
            courses,
            prerequisites,
            [row for row in progress if row["student_id"] == student_id],
            next_semester=int(profile["current_semester"]) + 1,
            p_dropout=p_dropout,
            p_dropout_calibrated=p_dropout_calibrated,
            rules=rules,
        )
        ability_row = persona_result.loc[student_id]
        p_student = float(ability_row["m3_prime_p_pass_by_ability"])
        eligible = rule_result["eligible_courses"]
        statuses = {
            row["course_id"]: row["status"]
            for row in progress
            if row["student_id"] == student_id
        }
        unlock = compute_unlock_values(
            [course["course_id"] for course in eligible],
            prerequisites,
            statuses,
            credits_by_course=course_credits,
            discount_per_edge=float(
                config["optimization"]["unlock_discount_per_edge"]["value"]
            ),
        )
        course_factors = {
            course["course_id"]: float(difficulty_factors.get(course["group"], 1.0))
            for course in eligible
        }
        for target in scenario_credits:
            for load_lambda in load_values:
                scenario_max = target
                if (
                    rule_result["enforce_cap"]
                    and rule_result["load_restriction_recommended"]
                ):
                    scenario_max = min(
                        scenario_max,
                        int(rule_result["recommended_credit_cap"]),
                    )
                result = solve_plan(
                    eligible,
                    p_student_m3_prime=p_student,
                    load_lambda=load_lambda,
                    risk_tier=rule_result["risk_tier"],
                    scenario_credit_max=scenario_max,
                    expected_fail_cap=float(
                        rule_result["expected_failed_course_cap"]
                    ),
                    average_credits_per_unit=average_credits,
                    median_real_load_units=6,
                    unlock_values=unlock,
                    beta=float(config["optimization"]["beta_unlock_value"]["value"]),
                    gamma=float(
                        config["optimization"]["gamma_failure_penalty"]["value"]
                    ),
                    minimum_credits=int(
                        config["semester_credit_limits"]["minimum"]["value"]
                    ),
                    relaxed_minimum_credits=int(
                        config["optimization"]["c_min_relaxed"]["value"]
                    ),
                    course_factors=course_factors,
                    retake_multiplier=1.0,
                    status_by_course=statuses,
                    prerequisite_rows=prerequisites,
                    require_blocking_retakes=bool(
                        config["optimization"]["required_retake_courses"]["value"]
                    ),
                    enforce_cap=bool(rule_result["enforce_cap"]),
                    risk_cap_slack_penalty=float(
                        config["optimization"]["risk_cap_slack_penalty"]["value"]
                    ),
                    graduation_ready=bool(
                        rule_result["progress_stats"][
                            "graduation_credit_threshold_met"
                        ]
                    ),
                )
                results.append(
                    {
                        "data_label": "SIMULATED + GIẢ ĐỊNH kịch bản; prototype",
                        "student_id": student_id,
                        "persona": profile["persona"],
                        "ability_tier_hk1": ability_row[
                            "ability_tier_from_real_hk1"
                        ],
                        "p_dropout": p_dropout,
                        "p_dropout_calibrated": p_dropout_calibrated,
                        "risk_tier": rule_result["risk_tier"],
                        "load_restriction_recommended": rule_result[
                            "load_restriction_recommended"
                        ],
                        "p_student_m3_prime": p_student,
                        "eligible_course_count": len(eligible),
                        "requested_credit_scenario": target,
                        "on_time_feasible": (
                            int(rule_result["progress_stats"][
                                "minimum_semesters_remaining"
                            ])
                            <= max(
                                0,
                                int(
                                    config["monte_carlo"][
                                        "completion_deadline_semesters"
                                    ]["value"]
                                )
                                - int(profile["current_semester"]),
                            )
                        ),
                        "load_lambda": load_lambda,
                        **result,
                    }
                )

        for load_lambda in load_values:
            persona_scenarios = [
                row
                for row in results
                if row["student_id"] == student_id
                and row["load_lambda"] == load_lambda
            ]
            acceptable = [
                row
                for row in persona_scenarios
                if row["status"] in {"optimal", "best_effort"}
                and row["expected_failed_courses"]
                <= row["expected_fail_cap"] + 1e-8
                and row["on_time_feasible"]
            ]
            recommendation_pool = acceptable or [
                row
                for row in persona_scenarios
                if row["status"] in {"optimal", "best_effort"}
            ]
            recommendation = (
                max(
                    recommendation_pool,
                    key=lambda row: (
                        row["expected_credits_passed"],
                        -row["expected_failed_courses"],
                        -row["requested_credit_scenario"],
                    ),
                )
                if recommendation_pool
                else None
            )
            recommendation_rows.append(
                {
                    "data_label": "SIMULATED + GIẢ ĐỊNH kịch bản; prototype",
                    "student_id": student_id,
                    "load_lambda": load_lambda,
                    "recommended_credit_scenario": (
                        recommendation["requested_credit_scenario"]
                        if recommendation
                        else None
                    ),
                    "selected_course_ids": (
                        ", ".join(recommendation["selected_course_ids"])
                        if recommendation
                        else ""
                    ),
                    "selected_credits": (
                        recommendation["selected_credits"]
                        if recommendation
                        else 0
                    ),
                    "expected_failed_courses": (
                        recommendation["expected_failed_courses"]
                        if recommendation
                        else None
                    ),
                    "meets_soft_risk_and_deadline": bool(acceptable),
                    "action": (
                        "Đề xuất kịch bản thỏa tiêu chí mềm."
                        if acceptable
                        else "Không có kịch bản đạt mọi tiêu chí; gặp cố vấn và xem xét giảm tải."
                    ),
                }
            )

        for beta in config["optimization"]["objective_sensitivity"]["beta_values"]:
            for gamma in config["optimization"]["objective_sensitivity"]["gamma_values"]:
                sensitivity = solve_plan(
                    eligible,
                    p_student_m3_prime=p_student,
                    load_lambda=0.1,
                    risk_tier=rule_result["risk_tier"],
                    scenario_credit_max=18,
                    expected_fail_cap=float(
                        rule_result["expected_failed_course_cap"]
                    ),
                    average_credits_per_unit=average_credits,
                    median_real_load_units=6,
                    unlock_values=unlock,
                    beta=float(beta),
                    gamma=float(gamma),
                    minimum_credits=int(
                        config["semester_credit_limits"]["minimum"]["value"]
                    ),
                    relaxed_minimum_credits=int(
                        config["optimization"]["c_min_relaxed"]["value"]
                    ),
                    course_factors=course_factors,
                    status_by_course=statuses,
                    prerequisite_rows=prerequisites,
                    require_blocking_retakes=bool(
                        config["optimization"]["required_retake_courses"]["value"]
                    ),
                    enforce_cap=bool(rule_result["enforce_cap"]),
                    risk_cap_slack_penalty=float(
                        config["optimization"]["risk_cap_slack_penalty"]["value"]
                    ),
                )
                sensitivities.append(
                    {
                        "data_label": "SIMULATED + GIẢ ĐỊNH kịch bản; prototype",
                        "student_id": student_id,
                        "beta": float(beta),
                        "gamma": float(gamma),
                        "status": sensitivity["status"],
                        "selected_credits": sensitivity["selected_credits"],
                        "selected_course_ids": ", ".join(
                            sensitivity["selected_course_ids"]
                        ),
                        "objective_value": sensitivity["objective_value"],
                    }
                )

    return {
        "data_label": "SIMULATED + GIẢ ĐỊNH kịch bản; prototype",
        "seed": experiment["seed"],
        "results": pd.DataFrame(results),
        "recommendations": pd.DataFrame(recommendation_rows),
        "objective_sensitivity": pd.DataFrame(sensitivities),
        "method": "PuLP with HiGHS",
        "personas": list(PERSONA_IDS),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run_prototype()
    output_dir = ROOT / "reports" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    result["results"].to_csv(
        output_dir / "ilp_prototype_scenarios.csv",
        index=False,
        encoding="utf-8-sig",
    )
    result["recommendations"].to_csv(
        output_dir / "ilp_scenario_recommendations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"ILP formulation check — {result['data_label']}")
    print(f"Solver={result['method']}; seed={result['seed']}")
    print(result["results"].to_string(index=False))
    print("Scenario recommendation by persona and lambda:")
    print(result["recommendations"].to_string(index=False))
    print("Objective-weight sensitivity (scenario max 18, lambda=0.1):")
    print(result["objective_sensitivity"].to_string(index=False))


if __name__ == "__main__":
    main()
