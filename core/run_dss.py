"""Single DSS entry point shared by interfaces and simulation."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

from core.models import MODEL_PATH, predict_risk
from core.optimizer import (
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    DEFAULT_LAMBDA,
    DEFAULT_RISK_CAP_MODE,
    FAST_FMAX,
    LOAD_BUDGETS,
    SAFE_RATIO,
    compute_unlock_values,
    estimated_graduation_semester,
    three_plans,
)
from core.rules import evaluate_student
from core.scenario_v2 import generate_scenario_rows


PROVENANCE = {
    "profile_summary": {"label": "SCENARIO"},
    "risk": {"label": "REAL (UCI-697)", "interpretation": "exploratory; not NTU-validated"},
    "credit_regime": {"label": "OFFICIAL (NTU)", "assumptions": "GIẢ ĐỊNH for pass/fail simulation after baseline term"},
    "academic_flags": {"label": "OFFICIAL (NTU)", "unconfirmed": ["W1 debt definition"]},
    "progress": {"label": "SCENARIO"},
    "eligible": {"label": "OFFICIAL (NTU)", "enrichment": "GIẢ ĐỊNH"},
    "blocked": {"label": "OFFICIAL (NTU)", "enrichment": "GIẢ ĐỊNH"},
    "forced_retakes": {"label": "OFFICIAL (NTU)"},
    "plans": {"label": "GIẢ ĐỊNH (optimizer weights and probabilities)"},
    "pareto_points": {"label": "GIẢ ĐỊNH (optimizer weights and probabilities)"},
    "p_student_pass": {"label": "REAL (UCI-697)", "scope": "M3-prime estimate; exploratory for NTU"},
}

_DATA_CONTEXT: dict[str, Any] | None = None
_DSS_CACHE: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
_RISK_CACHE: dict[str, dict[str, Any] | None] = {}
_DSS_CACHE_LIMIT = 512


def _context() -> dict[str, Any]:
    global _DATA_CONTEXT
    if _DATA_CONTEXT is None:
        profiles, _, metadata = generate_scenario_rows()
        _DATA_CONTEXT = {
            "profiles": {str(row["student_id"]): row for row in profiles},
            "metadata": metadata,
            "curriculum": metadata["curriculum"],
            "rules_config": metadata["rules_config"],
        }
    return _DATA_CONTEXT


def clear_dss_cache() -> None:
    """Clear result and immutable source-data caches for isolated callers/tests."""
    global _DATA_CONTEXT
    _DSS_CACHE.clear()
    _RISK_CACHE.clear()
    _DATA_CONTEXT = None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _normalise_options(options: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    raw = dict(options or {})
    budget = raw.get("budget")
    budget = None if budget is None else int(budget)
    if budget is not None and budget < 1:
        raise ValueError("budget must be a positive integer")
    fmax = raw.get("fmax")
    fmax = None if fmax is None else float(fmax)
    if fmax is not None and fmax < 0:
        raise ValueError("fmax must be non-negative")
    load_lambda = float(raw.get("lambda", DEFAULT_LAMBDA))
    if load_lambda < 0:
        raise ValueError("lambda must be non-negative")
    mode = str(raw.get("risk_cap_mode", DEFAULT_RISK_CAP_MODE))
    if mode not in {"off", "soft", "hard"}:
        raise ValueError("risk_cap_mode must be off, soft, or hard")
    scenario_set = raw.get("scenario_set")
    if scenario_set is not None:
        if isinstance(scenario_set, (str, bytes)):
            raise TypeError("scenario_set must be a sequence of positive integer budgets")
        scenario_set = tuple(int(value) for value in scenario_set)
        if not scenario_set or any(value < 1 for value in scenario_set):
            raise ValueError("scenario_set must contain positive integer budgets")
    profile_override = _jsonable(raw.get("profile_override", {}))
    progress_override = _jsonable(raw.get("progress_override", {}))
    target_semester = raw.get("target_semester")
    target_semester = None if target_semester is None else int(target_semester)
    if target_semester is not None and target_semester < 1:
        raise ValueError("target_semester must be positive")
    normalized = {
        "budget": budget,
        "fmax": fmax,
        "lambda": load_lambda,
        "risk_cap_mode": mode,
        "scenario_set": scenario_set,
        "profile_override": profile_override,
        "progress_override": progress_override,
        "target_semester": target_semester,
        "include_plans": bool(raw.get("include_plans", True)),
        "bypass_cache": bool(raw.get("bypass_cache", False)),
    }
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return normalized, canonical


def _risk_for(student_id: str, profile: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    scope = str(profile.get("ml_scope", "off"))
    if scope != "T1_valid":
        return None, f"ML off for scope {scope}; later-term estimate is not validated."
    if not MODEL_PATH.exists():
        return None, f"T1 model artifact is unavailable: {MODEL_PATH}"
    if student_id not in _RISK_CACHE:
        _RISK_CACHE[student_id] = predict_risk(dict(profile))
    return copy.deepcopy(_RISK_CACHE[student_id]), None


def run_dss(
    student_id: str,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one profile and return the shared DSS response schema.

    Simulation-only options may override progress/profile and suppress plan
    solving for heuristic policies; ordinary callers should use the defaults.
    """
    normalized, canonical = _normalise_options(options)
    sid = str(student_id).strip()
    cache_key = (sid, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
    if not normalized["bypass_cache"] and cache_key in _DSS_CACHE:
        _DSS_CACHE.move_to_end(cache_key)
        return copy.deepcopy(_DSS_CACHE[cache_key])

    ctx = _context()
    if sid not in ctx["profiles"]:
        raise ValueError(f"Student ID not found in scenarios: {sid}")
    base_profile = ctx["profiles"][sid]
    profile = {**base_profile, **normalized["profile_override"]}
    record = ctx["metadata"]["scenario_records"][sid]
    base_progress = {
        course_id: {
            "status": row["status"],
            "grade_10": row["grade_10"],
            "attempt_count": row["attempt_count"],
            "semester_taken": row["semester_taken"],
        }
        for course_id, row in record["progress"].items()
    }
    progress = base_progress
    progress.update(copy.deepcopy(normalized["progress_override"]))
    target_semester = normalized["target_semester"] or int(profile["target_semester"])
    grad_outcomes = profile.get("graduation_outcomes", {})
    if isinstance(grad_outcomes, str):
        grad_outcomes = json.loads(grad_outcomes)
    profile_for_eval = {
        **profile,
        "progress": progress,
        "graduation_outcomes": grad_outcomes,
    }
    evaluated = evaluate_student(
        profile_for_eval, ctx["curriculum"], ctx["rules_config"], target_semester
    )
    progress_stats = evaluated["progress_stats"]
    limits = progress_stats["registration_credit_limits"]
    risk, risk_reason = _risk_for(sid, base_profile)

    metadata = ctx["metadata"]
    courses = ctx["curriculum"]["courses"]
    course_by_id = {str(row["course_id"]): row for row in courses}
    program_ids = set(metadata["selected_course_ids"])
    program_courses = metadata["program_courses"]
    mean_credits = sum(int(row["credits"]) for row in program_courses) / len(program_courses)
    eligible = [
        row for row in evaluated["eligible_courses"]
        if str(row["course_id"]) in program_ids
    ]
    status_by_course = {course_id: row["status"] for course_id, row in progress.items()}
    active_slots = {
        str(course_by_id[course_id]["elective_slot"])
        for course_id, status in status_by_course.items()
        if course_id in course_by_id
        and course_by_id[course_id].get("elective_slot")
        and status in {"completed", "in_progress"}
    }
    required_slots = set(
        ctx["curriculum"]["program_config"]["program"]["required_elective_slots"][
            str(profile["specialization"])
        ]
    )
    required_slots.add(str(ctx["curriculum"]["enrichment_config"]["graduation_slot"]["slot"]))
    missing_slots = required_slots - active_slots
    unlock = compute_unlock_values(
        [str(row["course_id"]) for row in eligible],
        ctx["curriculum"]["prerequisites"],
        status_by_course,
        credits_by_course={key: int(row["credits"]) for key, row in course_by_id.items()},
        elective_slots_by_course={
            key: row.get("elective_slot") for key, row in course_by_id.items()
        },
        missing_slots=missing_slots,
        slot_credits=metadata["slot_credits"],
    )

    regime = str(limits.get("regime", "UNKNOWN"))
    budgets = normalized["scenario_set"]
    if budgets is None:
        if normalized["budget"] is not None:
            budgets = (normalized["budget"],)
        else:
            budgets = LOAD_BUDGETS.get(regime, ())
    plans: list[dict[str, Any]] = []
    if normalized["include_plans"]:
        current_debt = sum(
            int(course_by_id[course_id]["credits"])
            for course_id, row in progress.items()
            if row.get("status") == "failed"
            and course_id in course_by_id
            and course_id in program_ids
        )
        plans = three_plans(
            eligible,
            p_student=float(profile["p_student_pass"]),
            mean_credits=mean_credits,
            credit_limits=limits,
            prerequisites=ctx["curriculum"]["prerequisites"],
            progress=progress,
            unlock_values=unlock,
            beta=DEFAULT_BETA,
            gamma=DEFAULT_GAMMA,
            load_lambda=normalized["lambda"],
            budgets=budgets,
            current_debt_credits=current_debt,
            safe_ratio=SAFE_RATIO,
            fast_fmax=normalized["fmax"] if normalized["fmax"] is not None else FAST_FMAX,
            graduation_ready=bool(progress_stats["graduation_ready"]),
            risk_cap_mode=normalized["risk_cap_mode"],
        )
        for plan in plans:
            remaining = max(
                0.0,
                float(progress_stats["credits_remaining"])
                - float(plan.get("expected_credits_passed", 0.0)),
            )
            chain = progress_stats["minimum_semesters_prerequisite_chain"]
            plan["estimated_graduation"] = estimated_graduation_semester(
                target_semester,
                round(remaining),
                int(chain) if isinstance(chain, (int, float)) else 0,
            )

    warnings = [
        f"[{flag.get('code')}] {flag.get('message', '')}"
        for flag in evaluated.get("edge_case_flags", [])
    ]
    warnings.extend(
        warning
        for plan in plans
        for warning in plan.get("warnings", [])
        if warning not in warnings
    )
    if risk_reason:
        warnings.append(risk_reason)
    if profile.get("simulation_mode") == "pass_fail":
        warnings.append(
            "GIẢ ĐỊNH mô phỏng: giới hạn tín chỉ giữ TBHK gần nhất đã biết; "
            "điểm không được sinh trong Monte Carlo."
        )

    plan_statuses = {str(plan.get("status")) for plan in plans}
    if "infeasible_data_error" in plan_statuses:
        status = "infeasible_data_error"
    elif "best_effort" in plan_statuses:
        status = "best_effort"
    elif progress_stats["graduation_ready"]:
        status = "graduation_ready"
    elif not eligible:
        status = "no_eligible_courses"
    else:
        status = "optimal"
    result = {
        "profile_summary": {
            "student_id": sid,
            "persona": profile.get("persona"),
            "specialization": profile["specialization"],
            "last_completed_semester": int(profile.get("last_completed_semester", 0)),
            "target_semester": target_semester,
            "ml_scope": profile["ml_scope"],
            "ml_scope_reason": profile.get("ml_scope_reason", ""),
        },
        "risk": risk,
        "risk_reason": risk_reason,
        "credit_regime": {
            "regime": limits.get("regime"),
            "cmin": limits.get("cmin"),
            "cmax": limits.get("cmax"),
            "previous_semester_gpa": limits.get("previous_semester_gpa"),
            "notes": list(limits.get("notes", [])),
        },
        "academic_flags": evaluated["academic_flags"],
        "progress": {"stats": progress_stats, "by_course": progress},
        "eligible": eligible,
        "blocked": evaluated["blocked_courses"],
        "forced_retakes": evaluated["forced_retakes"],
        "plans": plans,
        "pareto_points": [
            {
                "plan_type": plan.get("plan_type"),
                "selected_credits": plan.get("selected_credits", 0),
                "expected_credits_passed": plan.get("expected_credits_passed", 0.0),
                "expected_failed_courses": plan.get("expected_failed_courses", 0.0),
                "p_warning_W1": plan.get("p_warning_W1", 0.0),
                "p_warning_W2": plan.get("p_warning_W2", 0.0),
                "status": plan.get("status"),
            }
            for plan in plans
        ],
        "status": status,
        "warnings": list(dict.fromkeys(warnings)),
        "provenance": copy.deepcopy(PROVENANCE),
    }
    if not normalized["bypass_cache"]:
        _DSS_CACHE[cache_key] = copy.deepcopy(result)
        _DSS_CACHE.move_to_end(cache_key)
        while len(_DSS_CACHE) > _DSS_CACHE_LIMIT:
            _DSS_CACHE.popitem(last=False)
    return result
