"""Minimal PuLP model used only to verify the Stage 1 objective formulation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import exp
from typing import Any

import pulp

from src.optimize.plan_risk import credits_to_curricular_units


def compute_unlock_values(
    course_ids: Sequence[str],
    prerequisites: Sequence[Mapping[str, Any]],
    status_by_course: Mapping[str, str],
    *,
    credits_by_course: Mapping[str, float] | None = None,
    discount_per_edge: float = 0.5,
) -> dict[str, float]:
    """Value unfinished downstream credits, discounted by prerequisite distance."""
    if not 0 <= discount_per_edge <= 1:
        raise ValueError("discount_per_edge must be in [0, 1]")
    graph: dict[str, set[str]] = {}
    for relation in prerequisites:
        if relation["type"] not in {"tiên quyết", "học trước"}:
            continue
        graph.setdefault(str(relation["prerequisite_id"]), set()).add(
            str(relation["course_id"])
        )

    def descendant_distances(course_id: str) -> dict[str, int]:
        distances: dict[str, int] = {}
        stack = [(child, 1) for child in graph.get(course_id, ())]
        while stack:
            dependent, distance = stack.pop()
            if dependent in distances and distances[dependent] <= distance:
                continue
            distances[dependent] = distance
            stack.extend(
                (child, distance + 1)
                for child in graph.get(dependent, ())
            )
        return distances

    unlock: dict[str, float] = {}
    for course_id in course_ids:
        distances = descendant_distances(course_id)
        unlock[course_id] = sum(
            float((credits_by_course or {}).get(dependent, 1.0))
            * discount_per_edge**distance
            for dependent, distance in distances.items()
            if status_by_course.get(dependent) != "completed"
        )
    return unlock


def solve_plan(
    eligible_courses: Sequence[Mapping[str, Any]],
    *,
    p_student_m3_prime: float,
    load_lambda: float,
    risk_tier: str,
    scenario_credit_max: int,
    expected_fail_cap: float,
    average_credits_per_unit: float,
    median_real_load_units: int,
    unlock_values: Mapping[str, float],
    beta: float,
    gamma: float,
    minimum_credits: int = 12,
    relaxed_minimum_credits: int = 6,
    course_factors: Mapping[str, float] | None = None,
    retake_multiplier: float = 1.0,
    enable_unlock_value: bool = True,
    enable_expected_fail_cap: bool = True,
    status_by_course: Mapping[str, str] | None = None,
    prerequisite_rows: Sequence[Mapping[str, Any]] = (),
    require_blocking_retakes: bool = True,
    enforce_cap: bool = False,
    risk_cap_slack_penalty: float = 1000.0,
    graduation_ready: bool = False,
) -> dict[str, Any]:
    """Solve one prototype semester plan with scenario-fixed load probability.

    The load multiplier is fixed using the maximum load of this risk-tier
    scenario before solving. This keeps the formulation linear; it is a
    conservative scenario approximation, not the exact plan-dependent model.
    """
    if not 0 <= p_student_m3_prime <= 1:
        raise ValueError("p_student_m3_prime must be in [0, 1]")
    if load_lambda < 0:
        raise ValueError("load_lambda must be non-negative")
    if (
        minimum_credits < 0
        or relaxed_minimum_credits < 0
        or relaxed_minimum_credits > minimum_credits
        or scenario_credit_max < minimum_credits
    ):
        raise ValueError("Invalid credit bounds")
    if beta < 0 or gamma < 0:
        raise ValueError("Objective weights must be non-negative")
    if retake_multiplier < 0:
        raise ValueError("retake_multiplier must be non-negative")
    if expected_fail_cap < 0 or risk_cap_slack_penalty <= 0:
        raise ValueError("Risk cap and slack penalty must be positive")

    items = list(eligible_courses)
    status = status_by_course or {
        str(course["course_id"]): str(course.get("status", "not_taken"))
        for course in items
    }
    ids = [str(course["course_id"]) for course in items]
    if len(ids) != len(set(ids)):
        raise ValueError("eligible_courses contains duplicate course_id")
    if graduation_ready:
        return {
            "solver": "PuLP/HiGHS",
            "prototype": True,
            "status": "graduation_ready",
            "solver_status": "Not run",
            "selected_course_ids": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "expected_fail_cap": expected_fail_cap,
            "risk_cap_exceeded": False,
            "reduced_load_advised": False,
            "message": "Sinh viên đã đạt ngưỡng tín chỉ tốt nghiệp.",
            "suggested_action": "Đối chiếu các điều kiện tốt nghiệp còn lại với cố vấn.",
        }
    if not ids:
        return {
            "solver": "PuLP/HiGHS",
            "prototype": True,
            "status": "no_eligible_courses",
            "solver_status": "Not run",
            "selected_course_ids": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "expected_fail_cap": expected_fail_cap,
            "risk_cap_exceeded": False,
            "reduced_load_advised": False,
            "message": "Không có học phần đủ điều kiện trong kỳ này.",
            "suggested_action": "Kiểm tra lịch mở và môn tiên quyết; gặp cố vấn nếu cần.",
        }
    effective_max = scenario_credit_max
    units = credits_to_curricular_units(
        effective_max,
        average_credits_per_unit,
    )
    load_multiplier = min(
        1.0,
        max(
            0.0,
            exp(-load_lambda * max(0, units - median_real_load_units)),
        ),
    )
    by_id = {str(course["course_id"]): course for course in items}
    credits = {course_id: int(by_id[course_id]["credits"]) for course_id in ids}
    unlock = {course_id: float(unlock_values.get(course_id, 0.0)) for course_id in ids}
    if any(value < 0 for value in unlock.values()):
        raise ValueError("Unlock values must be non-negative credit-equivalents")
    factors = course_factors or {}
    p_by_course: dict[str, float] = {}
    for course_id in ids:
        factor = float(factors.get(course_id, 1.0))
        if factor < 0:
            raise ValueError(f"course factor for {course_id} must be non-negative")
        repeated = (
            status.get(course_id) == "failed"
            or int(by_id[course_id].get("attempt_count", 0) or 0) > 1
        )
        retake_factor = retake_multiplier if repeated else 1.0
        p_by_course[course_id] = min(
            1.0,
            max(
                0.0,
                p_student_m3_prime
                * factor
                * retake_factor
                * load_multiplier,
            ),
        )

    def solve_with_minimum(minimum: int) -> tuple[Any, Any, Any, Any]:
        model = pulp.LpProblem("stage1_plan_prototype", pulp.LpMaximize)
        selected = {
            course_id: model.add_variable(
                name=f"select_{index}",
                lowBound=0,
                upBound=1,
                cat="Binary",
            )
            for index, course_id in enumerate(ids)
        }
        slack = None
        model += pulp.lpSum(
            (
                credits[course_id] * p_by_course[course_id]
                + beta * (unlock[course_id] if enable_unlock_value else 0.0)
                - gamma
                * credits[course_id]
                * (1.0 - p_by_course[course_id])
            )
            * selected[course_id]
            for course_id in ids
        )
        if enable_expected_fail_cap:
            expected_failures = pulp.lpSum(
                (1.0 - p_by_course[course_id]) * selected[course_id]
                for course_id in ids
            )
            if enforce_cap:
                model += expected_failures <= expected_fail_cap
            else:
                slack = model.add_variable(
                    name="risk_cap_slack",
                    lowBound=0,
                    cat="Continuous",
                )
                model += expected_failures <= expected_fail_cap + slack
                model.objective -= risk_cap_slack_penalty * slack
        model += pulp.lpSum(
            credits[course_id] * selected[course_id] for course_id in ids
        ) >= minimum
        model += pulp.lpSum(
            credits[course_id] * selected[course_id] for course_id in ids
        ) <= effective_max

        id_set = set(ids)
        for relation in prerequisite_rows:
            if relation["type"] != "song hành":
                continue
            course_id = str(relation["course_id"])
            prerequisite_id = str(relation["prerequisite_id"])
            if (
                status.get(prerequisite_id) != "completed"
                and course_id in id_set
                and prerequisite_id in id_set
            ):
                model += selected[course_id] <= selected[prerequisite_id]

        if require_blocking_retakes:
            for course_id in ids:
                if status.get(course_id) != "failed":
                    continue
                course = by_id[course_id]
                if str(course.get("course_type")) != "bắt buộc":
                    continue
                if unlock[course_id] > 0:
                    model += selected[course_id] == 1

        solve_stats = model.solve(pulp.HiGHS(msg=False))
        chosen = (
            [
                course_id
                for course_id in ids
                if pulp.value(selected[course_id]) > 0.5
            ]
            if solve_stats.has_solution
            else []
        )
        slack_value = (
            float(pulp.value(slack) or 0.0)
            if slack is not None
            else 0.0
        )
        return model, solve_stats, chosen, slack_value

    model, solve_stats, chosen, slack_value = solve_with_minimum(minimum_credits)
    solver_status = solve_stats.status.name
    used_minimum = minimum_credits
    reduced_load_advised = False
    if not solve_stats.has_solution and relaxed_minimum_credits < minimum_credits:
        model, solve_stats, chosen, slack_value = solve_with_minimum(
            relaxed_minimum_credits
        )
        solver_status = solve_stats.status.name
        used_minimum = relaxed_minimum_credits
        reduced_load_advised = solve_stats.has_solution
    if not solve_stats.has_solution:
        return {
            "solver": "PuLP/HiGHS",
            "prototype": True,
            "status": "infeasible_data_error",
            "solver_status": solver_status,
            "risk_tier": risk_tier,
            "scenario_credit_max": scenario_credit_max,
            "effective_credit_max": effective_max,
            "selected_course_ids": [],
            "selected_credits": 0,
            "expected_credits_passed": 0.0,
            "expected_failed_courses": 0.0,
            "expected_fail_cap": expected_fail_cap,
            "risk_cap_exceeded": False,
            "reduced_load_advised": False,
            "message": "Không tìm thấy phương án hợp lệ sau chuỗi dự phòng.",
            "suggested_action": "Rà dữ liệu eligibility, prerequisite, giới hạn tín chỉ và cấu hình.",
        }
    risk_cap_exceeded = enable_expected_fail_cap and slack_value > 1e-7
    status_name = (
        "best_effort"
        if risk_cap_exceeded or reduced_load_advised
        else "optimal"
    )
    actual_credits = sum(credits[course_id] for course_id in chosen)
    expected_credits_passed = sum(
        credits[course_id] * p_by_course[course_id] for course_id in chosen
    )
    expected_failed = sum(1.0 - p_by_course[course_id] for course_id in chosen)
    return {
        "solver": "PuLP/HiGHS",
        "prototype": True,
        "status": status_name,
        "solver_status": solver_status,
        "risk_tier": risk_tier,
        "scenario_credit_max": scenario_credit_max,
        "effective_credit_max": effective_max,
        "load_lambda": load_lambda,
        "load_multiplier": load_multiplier,
        "p_pass_by_course": p_by_course,
        "selected_course_ids": chosen,
        "selected_credits": actual_credits,
        "expected_credits_passed": expected_credits_passed,
        "expected_failed_courses": expected_failed,
        "expected_fail_cap": expected_fail_cap,
        "risk_cap_slack": slack_value,
        "risk_cap_exceeded": risk_cap_exceeded,
        "reduced_load_advised": reduced_load_advised,
        "minimum_credits_used": used_minimum,
        "message": (
            "Phương án có phần expected failures vượt mức khuyến nghị mềm."
            if risk_cap_exceeded
            else "Đã đề xuất giảm tải theo mức sàn dự phòng."
            if reduced_load_advised
            else "Tìm được phương án tối ưu trong các ràng buộc."
        ),
        "suggested_action": (
            "Trao đổi với cố vấn về tải học và môn học lại."
            if risk_cap_exceeded or reduced_load_advised
            else "Xem xét phương án cùng các kịch bản tải khác."
        ),
        "objective_value": (
            float(pulp.value(model.objective))
            if solve_stats.has_solution
            else None
        ),
        "beta": beta,
        "gamma": gamma,
        "unlock_enabled": enable_unlock_value,
        "expected_fail_cap_enabled": enable_expected_fail_cap,
        "enforce_cap": enforce_cap,
    }
