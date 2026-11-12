"""Scenario-v2 credit planning with exact selected-load probabilities."""

from __future__ import annotations

from collections import defaultdict
from math import ceil, exp, log
from pathlib import Path
from typing import Any

import pulp
import yaml

from core.rules import coreq_constraints


ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER_CONFIG_PATH = ROOT / "config" / "optimizer_scenario_v2.yaml"


def load_optimizer_config(path: Path = OPTIMIZER_CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return config


_CONFIG = load_optimizer_config()
_OPTIMIZER_CONFIG = _CONFIG["optimizer"]
SAFE_RATIO = float(_OPTIMIZER_CONFIG["plan_selection"]["safe_ratio"])
FAST_FMAX = float(_OPTIMIZER_CONFIG["plan_selection"]["fast_fmax"])
FMAX_GRID: tuple[float | None, ...] = tuple(
    None if value is None else float(value)
    for value in _OPTIMIZER_CONFIG["risk_cap"]["fmax_grid"]
)
LOAD_BUDGETS = {
    regime: tuple(int(value) for value in values)
    for regime, values in _OPTIMIZER_CONFIG["scenario_budgets"].items()
}
DEFAULT_BETA = float(_OPTIMIZER_CONFIG["objective"]["beta"])
DEFAULT_GAMMA = float(_OPTIMIZER_CONFIG["objective"]["gamma"])
DEFAULT_LAMBDA = float(_OPTIMIZER_CONFIG["load"]["lambda"])
DEFAULT_DELTA = float(_OPTIMIZER_CONFIG["unlock"]["discount_per_prerequisite_edge"])
DEFAULT_RISK_CAP_MODE = str(_OPTIMIZER_CONFIG["risk_cap"]["default"])
DEFAULT_RISK_CAP_PENALTY = float(_OPTIMIZER_CONFIG["risk_cap"]["soft_slack_penalty"])
RETAKE_MULTIPLIERS = tuple(
    float(value) for value in _OPTIMIZER_CONFIG["load"]["retake_multipliers"]
)
RETAKE_POLICY = _OPTIMIZER_CONFIG["load"]["retake_multiplier_policy"]
ADVISOR_WARNING = (
    "Phương án có rủi ro và không phải phương án an toàn; "
    "khuyến nghị trao đổi với cố vấn học tập."
)


def compute_unlock_values(
    course_ids: list[str],
    prerequisites: list[dict[str, Any]],
    status_by_course: dict[str, str],
    *,
    credits_by_course: dict[str, int],
    elective_slots_by_course: dict[str, str | None] | None = None,
    missing_slots: set[str] | None = None,
    slot_credits: dict[str, int] | None = None,
    discount_per_edge: float = DEFAULT_DELTA,
) -> dict[str, float]:
    """Value descendant credits and missing elective/graduation slots."""
    if not 0 <= discount_per_edge <= 1:
        raise ValueError("discount_per_edge must be in [0, 1]")
    graph: dict[str, set[str]] = defaultdict(set)
    for relation in prerequisites:
        if relation.get("type") == "tiên quyết":
            graph[str(relation["prerequisite_id"])].add(str(relation["course_id"]))

    def distances_from(course_id: str) -> dict[str, int]:
        distances: dict[str, int] = {}
        stack = [(child, 1) for child in graph.get(course_id, set())]
        while stack:
            child, distance = stack.pop()
            if child in distances and distances[child] <= distance:
                continue
            distances[child] = distance
            stack.extend((next_child, distance + 1) for next_child in graph.get(child, set()))
        return distances

    missing = missing_slots or set()
    slots = elective_slots_by_course or {}
    values: dict[str, float] = {}
    for course_id in course_ids:
        downstream = sum(
            credits_by_course.get(dependent, 0) * discount_per_edge**distance
            for dependent, distance in distances_from(course_id).items()
            if status_by_course.get(dependent) != "completed"
        )
        slot = slots.get(course_id)
        slot_value = (
            float((slot_credits or {}).get(slot, 0))
            if slot is not None and slot in missing
            else 0.0
        )
        values[course_id] = float(downstream + slot_value)
    return values


def course_expected_value(
    credits: int,
    pass_probability: float,
    unlock_value: float,
    *,
    beta: float,
    gamma: float,
) -> float:
    """Return c[(1+gamma)p-gamma] + beta*u."""
    if credits < 0 or not 0 <= pass_probability <= 1:
        raise ValueError("Invalid credit or pass-probability value")
    if min(beta, gamma, unlock_value) < 0:
        raise ValueError("Objective weights and unlock value must be non-negative")
    return credits * ((1.0 + gamma) * pass_probability - gamma) + beta * unlock_value


def _failure_probabilities(
    selected: list[dict[str, Any]],
    pass_probabilities: dict[str, float],
    *,
    current_debt_credits: int,
    registered_credits: int,
    warning_threshold_credits: int = 24,
) -> tuple[float, float]:
    distribution: dict[tuple[int, int], float] = {(0, 0): 1.0}
    for course in selected:
        course_id = str(course["course_id"])
        credits = int(course["credits"])
        p_pass = pass_probabilities[course_id]
        is_retake = course.get("status") == "failed"
        updated: dict[tuple[int, int], float] = defaultdict(float)
        for (failed_credits, debt_delta), probability in distribution.items():
            updated[
                (failed_credits, debt_delta - credits if is_retake else debt_delta)
            ] += probability * p_pass
            updated[
                (
                    failed_credits + credits,
                    debt_delta + credits,
                )
            ] += probability * (1.0 - p_pass)
        distribution = {
            outcome: probability
            for outcome, probability in updated.items()
            if probability > 1e-15
        }

    p_w2 = sum(
        probability
        for (failed_credits, _), probability in distribution.items()
        if failed_credits > 0.5 * registered_credits
    )
    p_w1 = sum(
        probability
        for (_, debt_delta), probability in distribution.items()
        if current_debt_credits + debt_delta > warning_threshold_credits
    )
    return min(1.0, max(0.0, p_w1)), min(1.0, max(0.0, p_w2))


def _solve_fixed_load(
    courses: list[dict[str, Any]],
    *,
    selected_load: int,
    p_student: float,
    mean_credits: float,
    load_lambda: float,
    retake_multiplier: float,
    beta: float,
    gamma: float,
    unlock_values: dict[str, float],
    prerequisite_rows: list[dict[str, Any]],
    completed_or_in_progress: set[str],
    forced_ids: set[str],
    expected_fail_cap: float | None,
    risk_cap_mode: str,
    soft_cap_penalty: float,
    forced_conflict: bool,
    current_debt_credits: int,
) -> dict[str, Any] | None:
    if not courses:
        return None
    mean = max(float(mean_credits), 1e-9)
    load_units = int((selected_load / mean) + 0.5)
    load_factor = exp(-load_lambda * max(0, load_units - 6))
    by_id = {str(course["course_id"]): course for course in courses}
    pass_probabilities = {}
    for course_id, course in by_id.items():
        retake_factor = retake_multiplier
        if course.get("status") == "failed":
            attempts = int(course.get("attempt_count", 1) or 1)
            default_retake_factor = (
                RETAKE_POLICY["repeated_attempt"]
                if attempts > 1
                else RETAKE_POLICY["first_retake"]
            )
            retake_factor *= float(
                course.get("retake_multiplier", default_retake_factor)
            )
        pass_probabilities[course_id] = min(
            1.0,
            max(0.0, p_student * load_factor * retake_factor),
        )

    problem = pulp.LpProblem("ntu_scenario_v2_plan", pulp.LpMaximize)
    variables = {
        course_id: problem.add_variable(f"x_{index}", cat="Binary")
        for index, course_id in enumerate(by_id)
    }
    problem += pulp.lpSum(
        course_expected_value(
            int(course["credits"]),
            pass_probabilities[course_id],
            float(unlock_values.get(course_id, 0.0)),
            beta=beta,
            gamma=gamma,
        )
        * variables[course_id]
        for course_id, course in by_id.items()
    )
    problem += pulp.lpSum(
        int(course["credits"]) * variables[course_id]
        for course_id, course in by_id.items()
    ) == selected_load
    for course_id in forced_ids:
        if course_id in variables:
            problem += variables[course_id] == 1
    for course_id, peer_id in coreq_constraints(prerequisite_rows):
        if course_id in variables and peer_id in variables:
            problem += variables[course_id] <= variables[peer_id]
        elif (
            course_id in variables
            and peer_id in completed_or_in_progress
        ):
            continue
    slots: dict[str, list[str]] = defaultdict(list)
    for course_id, course in by_id.items():
        slot = course.get("elective_slot")
        if slot:
            slots[str(slot)].append(course_id)
    for slot_ids in slots.values():
        problem += pulp.lpSum(variables[course_id] for course_id in slot_ids) <= 1

    expected_failures = pulp.lpSum(
        (1.0 - pass_probabilities[course_id]) * variables[course_id]
        for course_id in by_id
    )
    cap_slack = None
    if expected_fail_cap is not None and risk_cap_mode in {"soft", "hard"}:
        if risk_cap_mode == "hard":
            problem += expected_failures <= expected_fail_cap
        else:
            cap_slack = problem.add_variable("risk_cap_slack", lowBound=0)
            problem += expected_failures <= expected_fail_cap + cap_slack
            problem.setObjective(
                problem.objective - soft_cap_penalty * cap_slack
            )

    solver = pulp.HiGHS(msg=False)
    solve_stats = problem.solve(solver)
    solver_status = solve_stats.status.name
    if solver_status != "Optimal":
        return None
    selected_ids = [
        course_id
        for course_id, variable in variables.items()
        if (pulp.value(variable) or 0.0) > 0.5
    ]
    selected = [by_id[course_id] for course_id in selected_ids]
    chosen_probabilities = {
        course_id: pass_probabilities[course_id] for course_id in selected_ids
    }
    p_w1, p_w2 = _failure_probabilities(
        selected,
        chosen_probabilities,
        current_debt_credits=current_debt_credits,
        registered_credits=selected_load,
    )
    total_credit = sum(int(course["credits"]) for course in selected)
    failed_retakes = [
        course for course in selected if course.get("status") == "failed"
    ]
    expected_credit_passed = sum(
        int(course["credits"]) * chosen_probabilities[str(course["course_id"])]
        for course in selected
    )
    expected_failed = sum(1.0 - value for value in chosen_probabilities.values())
    return {
        "solver": "PuLP/HiGHS",
        "solver_status": solver_status,
        "status": "best_effort" if forced_conflict else "optimal",
        "selected_course_ids": sorted(selected_ids),
        "selected_courses": selected,
        "selected_credits": total_credit,
        "selected_load": total_credit,
        "load_units": load_units,
        "mean_credits": mean,
        "load_factor": load_factor,
        "pass_probabilities": chosen_probabilities,
        "expected_credits_passed": expected_credit_passed,
        "expected_failed_courses": expected_failed,
        "objective_value": float(pulp.value(problem.objective) or 0.0),
        "expected_fail_cap": expected_fail_cap,
        "risk_cap_exceeded": (
            expected_fail_cap is not None
            and expected_failed > expected_fail_cap + 1e-8
        ),
        "risk_cap_mode": risk_cap_mode,
        "p_warning_W1": p_w1,
        "p_warning_W2": p_w2,
        "p_at_least_one_failure": 1.0
        - exp(sum(log(max(1e-300, value)) for value in chosen_probabilities.values())),
        "retake_credits_total": sum(int(course["credits"]) for course in failed_retakes),
        "honors_downgrade_risk": sum(
            int(course["credits"]) for course in failed_retakes
        )
        > 6.5,
        "forced_retake_conflict": forced_conflict,
        "risk_cap_slack": float(pulp.value(cap_slack) or 0.0) if cap_slack else 0.0,
    }


def optimize_plan(
    eligible_courses: list[dict[str, Any]],
    *,
    p_student: float,
    mean_credits: float,
    credit_limits: dict[str, Any],
    prerequisites: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    unlock_values: dict[str, float] | None = None,
    scenario_budget: int | None = None,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    load_lambda: float = DEFAULT_LAMBDA,
    retake_multiplier: float = 1.0,
    risk_cap_mode: str = DEFAULT_RISK_CAP_MODE,
    expected_fail_cap: float | None = None,
    soft_cap_penalty: float = DEFAULT_RISK_CAP_PENALTY,
    current_debt_credits: int = 0,
    graduation_ready: bool = False,
) -> dict[str, Any]:
    """Optimize across exact selected loads; never treats risk as permission control."""
    if not 0 <= p_student <= 1:
        raise ValueError("p_student must be in [0, 1]")
    if mean_credits <= 0 or load_lambda < 0:
        raise ValueError("mean_credits must be positive and load_lambda non-negative")
    if min(beta, gamma, retake_multiplier, soft_cap_penalty) < 0:
        raise ValueError("Optimization weights must be non-negative")
    if risk_cap_mode not in {"off", "soft", "hard"}:
        raise ValueError("risk_cap_mode must be off, soft, or hard")
    if graduation_ready:
        return {
            "status": "graduation_ready",
            "solver": "not run",
            "selected_course_ids": [],
            "selected_courses": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "risk_cap_exceeded": False,
            "warnings": [],
        }
    if not eligible_courses:
        return {
            "status": "no_eligible_courses",
            "solver": "not run",
            "selected_course_ids": [],
            "selected_courses": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "risk_cap_exceeded": False,
            "warnings": ["Không có môn đủ điều kiện trong kỳ mục tiêu."],
        }

    items = [
        dict(course)
        for course in eligible_courses
        if bool(course.get("counts_toward_total", True))
    ]
    if not items:
        return {
            "status": "no_eligible_courses",
            "solver": "not run",
            "selected_course_ids": [],
            "selected_courses": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "risk_cap_exceeded": False,
            "warnings": ["Không có môn đủ điều kiện thuộc chương trình 130 tín chỉ."],
        }
    if len({str(course["course_id"]) for course in items}) != len(items):
        raise ValueError("eligible_courses contains duplicate course_id")
    for course in items:
        course_id = str(course["course_id"])
        course["current_debt"] = progress.get(course_id, {}).get("status") == "failed"
    cmax_raw = credit_limits.get("cmax")
    cmin_raw = credit_limits.get("cmin")
    cmax = sum(int(course["credits"]) for course in items) if cmax_raw in (None, "UNKNOWN") else int(cmax_raw)
    cmin = 0 if cmin_raw in (None, "UNKNOWN") else int(cmin_raw)
    if scenario_budget is not None:
        cmax = min(cmax, scenario_budget)
    forced = {
        str(course["course_id"])
        for course in items
        if course.get("must_register")
    }
    forced_credits = sum(
        int(course["credits"])
        for course in items
        if str(course["course_id"]) in forced
    )
    forced_conflict = forced_credits > cmax
    if forced_conflict:
        values = unlock_values or {}
        forced_order = sorted(
            (
                course for course in items
                if str(course["course_id"]) in forced
            ),
            key=lambda course: (
                -float(values.get(str(course["course_id"]), 0.0)),
                -int(course["credits"]),
                str(course["course_id"]),
            ),
        )
        selected_forced: set[str] = set()
        used = 0
        for course in forced_order:
            credits = int(course["credits"])
            if used + credits <= cmax:
                selected_forced.add(str(course["course_id"]))
                used += credits
        forced = selected_forced

    possible_loads = [
        load
        for load in range(max(1, cmin), cmax + 1)
        if any(int(course["credits"]) <= load for course in items)
    ]
    if forced and not forced_conflict:
        forced_min = sum(
            int(course["credits"])
            for course in items
            if str(course["course_id"]) in forced
        )
        possible_loads = [load for load in possible_loads if load >= forced_min]
    if not possible_loads:
        possible_loads = [cmax] if cmax > 0 else []
    completed_or_in_progress = {
        course_id
        for course_id, record in progress.items()
        if record.get("status") in {"completed", "in_progress"}
    }
    candidates: list[dict[str, Any]] = []
    for load in possible_loads:
        result = _solve_fixed_load(
            items,
            selected_load=load,
            p_student=p_student,
            mean_credits=mean_credits,
            load_lambda=load_lambda,
            retake_multiplier=retake_multiplier,
            beta=beta,
            gamma=gamma,
            unlock_values=unlock_values or {},
            prerequisite_rows=prerequisites,
            completed_or_in_progress=completed_or_in_progress,
            forced_ids=forced,
            expected_fail_cap=expected_fail_cap,
            risk_cap_mode=risk_cap_mode,
            soft_cap_penalty=soft_cap_penalty,
            forced_conflict=forced_conflict,
            current_debt_credits=current_debt_credits,
        )
        if result is not None:
            candidates.append(result)
    if not candidates and risk_cap_mode == "hard":
        fallback = optimize_plan(
            eligible_courses,
            p_student=p_student,
            mean_credits=mean_credits,
            credit_limits=credit_limits,
            prerequisites=prerequisites,
            progress=progress,
            unlock_values=unlock_values,
            scenario_budget=scenario_budget,
            beta=beta,
            gamma=gamma,
            load_lambda=load_lambda,
            retake_multiplier=retake_multiplier,
            risk_cap_mode="off",
            expected_fail_cap=expected_fail_cap,
            soft_cap_penalty=soft_cap_penalty,
            current_debt_credits=current_debt_credits,
            graduation_ready=False,
        )
        fallback["status"] = "best_effort"
        fallback["warnings"] = list(fallback.get("warnings", [])) + [
            "Không có nghiệm dưới trần Fmax; đã nới trần mềm để tìm phương án.",
            ADVISOR_WARNING,
        ]
        return fallback
    if not candidates and cmin > 0:
        fallback = optimize_plan(
            eligible_courses,
            p_student=p_student,
            mean_credits=mean_credits,
            credit_limits={**credit_limits, "cmin": 0},
            prerequisites=prerequisites,
            progress=progress,
            unlock_values=unlock_values,
            scenario_budget=scenario_budget,
            beta=beta,
            gamma=gamma,
            load_lambda=load_lambda,
            retake_multiplier=retake_multiplier,
            risk_cap_mode=risk_cap_mode,
            expected_fail_cap=expected_fail_cap,
            soft_cap_penalty=soft_cap_penalty,
            current_debt_credits=current_debt_credits,
            graduation_ready=False,
        )
        if fallback["status"] not in {"no_eligible_courses", "infeasible_data_error"}:
            fallback["status"] = "best_effort"
            fallback["warnings"] = list(fallback.get("warnings", [])) + [
                "Không có tổ hợp khả thi đạt cận dưới tín chỉ; đã nới cận dưới.",
                ADVISOR_WARNING,
            ]
            return fallback
    if not candidates:
        return {
            "status": "infeasible_data_error",
            "solver": "PuLP/HiGHS",
            "selected_course_ids": [],
            "selected_courses": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "risk_cap_exceeded": False,
            "warnings": ["Không có nghiệm khả thi trong các giới hạn dữ liệu."],
        }
    best = max(
        candidates,
        key=lambda plan: (
            plan["objective_value"],
            plan["expected_credits_passed"],
            -plan["expected_failed_courses"],
            -plan["selected_credits"],
        ),
    )
    if best["selected_credits"] < cmin:
        best["status"] = "best_effort"
        best.setdefault("warnings", []).append(
            "Không đủ môn khả thi để đạt cận dưới tín chỉ đăng ký."
        )
    if forced_conflict:
        best["status"] = "best_effort"
        best["regulatory_conflict"] = True
        best["warnings"] = [
            "Tổng tín chỉ học lại bắt buộc vượt hạn mức đăng ký; "
            "đã ưu tiên môn có giá trị mở khóa cao hơn.",
            ADVISOR_WARNING,
        ]
    else:
        best["regulatory_conflict"] = False
        best["warnings"] = list(best.get("warnings", []))
    if best["risk_cap_exceeded"] or best["status"] == "best_effort":
        best["warnings"].append(ADVISOR_WARNING)
    if cmin_raw in (None, "UNKNOWN") or cmax_raw in (None, "UNKNOWN"):
        best["warnings"].append(
            "Giới hạn tín chỉ quy chế UNKNOWN; giới hạn này không được suy đoán."
        )
    return best


def three_plans(
    eligible_courses: list[dict[str, Any]],
    *,
    p_student: float,
    mean_credits: float,
    credit_limits: dict[str, Any],
    prerequisites: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    unlock_values: dict[str, float],
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    load_lambda: float = DEFAULT_LAMBDA,
    budgets: tuple[int, ...] | None = None,
    current_debt_credits: int = 0,
    safe_ratio: float = SAFE_RATIO,
    fast_fmax: float = FAST_FMAX,
    graduation_ready: bool = False,
    risk_cap_mode: str = "off",
) -> list[dict[str, Any]]:
    """Select risk-focused, objective-focused, and acceleration plan candidates."""
    regime = str(credit_limits.get("regime", "NORMAL"))
    selected_budgets = budgets or LOAD_BUDGETS.get(regime, ())
    plans: list[dict[str, Any]] = []
    for budget in selected_budgets:
        result = optimize_plan(
            eligible_courses,
            p_student=p_student,
            mean_credits=mean_credits,
            credit_limits=credit_limits,
            prerequisites=prerequisites,
            progress=progress,
            unlock_values=unlock_values,
            scenario_budget=budget,
            beta=beta,
            gamma=gamma,
            load_lambda=load_lambda,
            risk_cap_mode=risk_cap_mode,
            expected_fail_cap=fast_fmax if risk_cap_mode != "off" else None,
            current_debt_credits=current_debt_credits,
            graduation_ready=graduation_ready,
        )
        if result["status"] in {"infeasible_data_error", "no_eligible_courses"}:
            continue
        for cap in FMAX_GRID:
            if cap is not None and result["expected_failed_courses"] > cap:
                continue
            candidate = dict(result)
            candidate.update(
                {
                    "scenario_budget": budget,
                    "fmax": cap,
                    "risk_cap_mode": risk_cap_mode,
                }
            )
            plans.append(candidate)
    if not plans:
        empty = optimize_plan(
            eligible_courses,
            p_student=p_student,
            mean_credits=mean_credits,
            credit_limits=credit_limits,
            prerequisites=prerequisites,
            progress=progress,
            unlock_values=unlock_values,
            beta=beta,
            gamma=gamma,
            load_lambda=load_lambda,
            graduation_ready=graduation_ready,
            risk_cap_mode=risk_cap_mode,
            expected_fail_cap=fast_fmax if risk_cap_mode != "off" else None,
        )
        plans = [empty]
    for plan in plans:
        plan.setdefault("selected_course_ids", [])
        plan.setdefault("expected_credits_passed", 0.0)
        plan.setdefault("expected_failed_courses", 0.0)
        plan.setdefault("objective_value", 0.0)
        plan.setdefault("p_warning_W1", 0.0)
        plan.setdefault("p_warning_W2", 0.0)
        plan.setdefault("p_at_least_one_failure", 0.0)
        plan.setdefault("pass_probabilities", {})
        plan.setdefault("warnings", [])
    nondominated: list[dict[str, Any]] = []
    for candidate in plans:
        dominated = any(
            other["expected_credits_passed"] >= candidate["expected_credits_passed"]
            and other["expected_failed_courses"] <= candidate["expected_failed_courses"]
            and (
                other["expected_credits_passed"] > candidate["expected_credits_passed"]
                or other["expected_failed_courses"] < candidate["expected_failed_courses"]
            )
            for other in plans
        )
        if not dominated:
            nondominated.append(candidate)

    max_expected_credits = max(plan["expected_credits_passed"] for plan in nondominated)
    safe_pool = [
        plan
        for plan in nondominated
        if plan["expected_credits_passed"] >= safe_ratio * max_expected_credits
    ]
    safest = min(
        safe_pool,
        key=lambda plan: (
            plan["expected_failed_courses"],
            plan["p_warning_W1"] + plan["p_warning_W2"],
            plan["selected_credits"],
        ),
    )
    balanced = max(
        nondominated,
        key=lambda plan: (
            plan["objective_value"],
            plan["expected_credits_passed"],
            -plan["expected_failed_courses"],
        ),
    )
    fast_pool = [
        plan
        for plan in nondominated
        if plan["expected_failed_courses"] <= fast_fmax
    ]
    fast = max(
        fast_pool or nondominated,
        key=lambda plan: (
            plan["expected_credits_passed"],
            -plan["expected_failed_courses"],
        ),
    )
    if not fast_pool and fast["status"] not in {"graduation_ready", "no_eligible_courses"}:
        fast = dict(fast)
        fast["status"] = "best_effort"
        fast["risk_cap_exceeded"] = fast["expected_failed_courses"] > fast_fmax
        fast["expected_fail_cap"] = fast_fmax
        fast["fmax"] = fast_fmax
        fast["risk_cap_mode"] = "off"
        fast["warnings"] = list(dict.fromkeys([
            *fast.get("warnings", []),
            "Không có phương án đạt Fmax cho Tăng tốc; hiển thị phương án khả thi gần nhất.",
            ADVISOR_WARNING,
        ]))
    chosen = [
        ("risk_focused", safest, "Ưu tiên giảm số môn trượt, trong ngưỡng safe_ratio tín chỉ kỳ vọng."),
        ("balanced", balanced, "Tối ưu hàm mục tiêu có tính điểm đạt, rủi ro trượt và giá trị mở khóa."),
        ("acceleration", fast, "Ưu tiên tín chỉ đạt kỳ vọng dưới ngưỡng số môn trượt fast_fmax."),
    ]
    display_labels = {
        "risk_focused": "An toàn (mục tiêu giảm rủi ro; không bảo đảm an toàn)",
        "balanced": "Cân bằng",
        "acceleration": "Tăng tốc",
    }
    results = []
    for kind, plan, explanation in chosen:
        item = dict(plan)
        item["plan_type"] = kind
        if item["status"] == "best_effort":
            item["plan_label"] = (
                "best_effort — "
                + display_labels[kind].replace("An toàn", "ưu tiên giảm rủi ro")
            )
        elif item["status"] == "graduation_ready":
            item["plan_label"] = "Đã đủ điều kiện tốt nghiệp — không cần đăng ký"
        elif item["status"] == "no_eligible_courses":
            item["plan_label"] = "Không có môn đủ điều kiện"
        else:
            item["plan_label"] = display_labels[kind]
        item["explanation"] = explanation
        item["plan_difference_note"] = (
            "Các chiến lược có thể trùng nhau nếu biên Pareto chỉ có một lựa chọn."
        )
        other_plans = [
            other for other_kind, other, _ in chosen if other_kind != kind
        ]
        if all(
            set(item["selected_course_ids"]) == set(other["selected_course_ids"])
            for other in other_plans
        ):
            item["difference_explanation"] = (
                "Trùng tập môn với hai chiến lược còn lại vì các tiêu chí chọn cùng một nghiệm Pareto."
            )
        else:
            differences = []
            for other_kind, other, _ in chosen:
                if other_kind == kind:
                    continue
                added = sorted(
                    set(item["selected_course_ids"])
                    - set(other["selected_course_ids"])
                )
                omitted = sorted(
                    set(other["selected_course_ids"])
                    - set(item["selected_course_ids"])
                )
                differences.append(
                    f"so với {other_kind}: thêm {added or 'không môn nào'}, "
                    f"bỏ {omitted or 'không môn nào'}"
                )
            item["difference_explanation"] = (
                "; ".join(differences)
                + f"; tín chỉ kỳ vọng {item['expected_credits_passed']:.2f}, "
                f"số môn trượt kỳ vọng {item['expected_failed_courses']:.2f}."
            )
        if item["status"] == "best_effort" or item.get("risk_cap_exceeded"):
            item["warnings"] = list(
                dict.fromkeys([*item.get("warnings", []), ADVISOR_WARNING])
            )
        results.append(item)
    return results


def estimated_graduation_semester(
    target_semester: int,
    remaining_credits: int,
    prerequisite_chain_semesters: int,
    *,
    assumed_maximum_credits: int = 27,
) -> dict[str, Any]:
    """Estimate a lower bound; the semester cap and offering schedule are assumptions."""
    if min(target_semester, remaining_credits, prerequisite_chain_semesters) < 0:
        raise ValueError("Semester and credit counts must be non-negative")
    future_by_credits = ceil(remaining_credits / assumed_maximum_credits)
    future_chain = max(0, prerequisite_chain_semesters - 1)
    additional = max(future_by_credits, future_chain)
    return {
        "semester": target_semester + additional,
        "additional_semesters_lower_bound": additional,
        "assumption": "GIẢ ĐỊNH: tối đa 27 tín chỉ/kỳ; chuỗi tiên quyết từ dữ liệu hiện có.",
    }


def plan_final_semester_cases(
    eligible_courses: list[dict[str, Any]],
    *,
    outstanding_course_ids: list[str],
    p_student: float,
    mean_credits: float,
    credit_limits: dict[str, Any],
    prerequisites: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    unlock_values: dict[str, float] | None = None,
    current_debt_credits: int = 0,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    load_lambda: float = DEFAULT_LAMBDA,
) -> dict[str, Any]:
    """Return regulation-limited case A and completion-plan case B."""
    case_a = optimize_plan(
        eligible_courses,
        p_student=p_student,
        mean_credits=mean_credits,
        credit_limits=credit_limits,
        prerequisites=prerequisites,
        progress=progress,
        unlock_values=unlock_values,
        current_debt_credits=current_debt_credits,
        beta=beta,
        gamma=gamma,
        load_lambda=load_lambda,
    )
    by_id = {
        str(course["course_id"]): dict(course)
        for course in eligible_courses
        if bool(course.get("counts_toward_total", True))
    }
    missing = set(outstanding_course_ids)
    if not missing.issubset(by_id):
        return {
            "A_regulation_limited": case_a,
            "B_completion_plan": {
                "status": "infeasible_data_error",
                "selected_course_ids": [],
                "missing_eligible_course_ids": sorted(missing - set(by_id)),
                "warnings": [
                    "Không thể hoàn tất toàn bộ tín chỉ còn thiếu do môn chưa đủ điều kiện/lịch mở."
                ],
            },
        }
    forced_courses = []
    for course_id, course in by_id.items():
        course["must_register"] = course_id in missing
        forced_courses.append(course)
    completion_credits = sum(int(by_id[course_id]["credits"]) for course_id in missing)
    case_b = optimize_plan(
        forced_courses,
        p_student=p_student,
        mean_credits=mean_credits,
        credit_limits={"cmin": 0, "cmax": completion_credits, "regime": "UNRESTRICTED_FINAL"},
        prerequisites=prerequisites,
        progress=progress,
        unlock_values=unlock_values,
        current_debt_credits=current_debt_credits,
        scenario_budget=completion_credits,
        beta=beta,
        gamma=gamma,
        load_lambda=load_lambda,
    )
    if case_b["selected_credits"] != completion_credits:
        case_b["status"] = "infeasible_data_error"
        case_b["warnings"] = list(case_b.get("warnings", [])) + [
            "Phương án B chưa chọn đủ tín chỉ để hoàn tất chương trình."
        ]
    else:
        case_b["status"] = (
            "final_semester_plan"
            if case_b["status"] == "optimal"
            else case_b["status"]
        )
    return {"A_regulation_limited": case_a, "B_completion_plan": case_b}
