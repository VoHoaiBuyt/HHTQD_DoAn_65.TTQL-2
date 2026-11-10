from __future__ import annotations

import inspect
import itertools
from typing import Any

import pytest

from core.optimizer import (
    _failure_probabilities,
    course_expected_value,
    optimize_plan,
    plan_final_semester_cases,
    three_plans,
)


TEST_FIXTURE = "TEST_FIXTURE"


def _course(
    course_id: str,
    *,
    credits: int = 3,
    status: str = "not_taken",
    elective_slot: str | None = None,
    must_register: bool = False,
    retake_multiplier: float | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "course_id": course_id,
        "course_name": course_id,
        "credits": credits,
        "status": status,
        "attempt_count": 1 if status == "failed" else 0,
        "must_register": must_register,
        "elective_slot": elective_slot,
        "counts_toward_total": True,
        "source_label": TEST_FIXTURE,
    }
    if retake_multiplier is not None:
        row["retake_multiplier"] = retake_multiplier
    return row


def _limits(minimum: int = 0, maximum: int = 27) -> dict[str, Any]:
    return {"cmin": minimum, "cmax": maximum, "regime": TEST_FIXTURE}


def test_objective_break_even_threshold_and_unlock_compensation() -> None:
    assert course_expected_value(3, 0.5, 0, beta=0, gamma=1) == 0
    assert course_expected_value(3, 0.49, 0, beta=0, gamma=1) < 0
    assert course_expected_value(3, 0.49, 4, beta=0.125, gamma=1) > 0
    assert 1 / (1 + 1) == 0.5


def test_actual_selected_load_not_scenario_budget_sets_pass_probability() -> None:
    courses = [_course("A"), _course("B")]
    common = {
        "eligible_courses": courses,
        "p_student": 0.8,
        "mean_credits": 3,
        "credit_limits": _limits(maximum=9),
        "prerequisites": [],
        "progress": {},
        "beta": 0,
        "gamma": 0,
        "load_lambda": 0.3,
    }
    smaller_budget = optimize_plan(**common, scenario_budget=6)
    larger_budget = optimize_plan(**common, scenario_budget=9)
    assert smaller_budget["selected_course_ids"] == larger_budget["selected_course_ids"]
    assert smaller_budget["selected_load"] == larger_budget["selected_load"] == 6
    assert smaller_budget["pass_probabilities"] == larger_budget["pass_probabilities"]
    assert smaller_budget["expected_failed_courses"] == pytest.approx(
        larger_budget["expected_failed_courses"]
    )


def test_warning_probabilities_exactly_match_exhaustive_enumeration() -> None:
    courses = [
        _course("A", credits=3),
        _course("B", credits=2, status="failed"),
        _course("C", credits=4),
        _course("D", credits=3),
    ]
    probabilities = {"A": 0.7, "B": 0.6, "C": 0.8, "D": 0.9}
    p_w1, p_w2 = _failure_probabilities(
        courses,
        probabilities,
        current_debt_credits=23,
        registered_credits=12,
    )
    expected_w1 = 0.0
    expected_w2 = 0.0
    for outcomes in itertools.product((False, True), repeat=len(courses)):
        probability = 1.0
        failed_credits = 0
        debt_delta = 0
        for course, passed in zip(courses, outcomes, strict=True):
            course_id = course["course_id"]
            course_probability = probabilities[course_id]
            probability *= course_probability if passed else 1 - course_probability
            if not passed:
                failed_credits += course["credits"]
                debt_delta += course["credits"]
            elif course["status"] == "failed":
                debt_delta -= course["credits"]
        if 23 + debt_delta > 24:
            expected_w1 += probability
        if failed_credits > 6:
            expected_w2 += probability
    assert p_w1 == pytest.approx(expected_w1)
    assert p_w2 == pytest.approx(expected_w2)


def test_empty_eligibility_and_external_courses_are_not_optimizable() -> None:
    assert optimize_plan(
        [],
        p_student=0.8,
        mean_credits=3,
        credit_limits=_limits(),
        prerequisites=[],
        progress={},
    )["status"] == "no_eligible_courses"
    external = _course("EXTERNAL")
    external["counts_toward_total"] = False
    result = optimize_plan(
        [external],
        p_student=0.8,
        mean_credits=3,
        credit_limits=_limits(),
        prerequisites=[],
        progress={},
    )
    assert result["status"] == "no_eligible_courses"


def test_hard_risk_cap_fallback_is_best_effort_with_advisor_warning() -> None:
    result = optimize_plan(
        [_course("A")],
        p_student=0.1,
        mean_credits=3,
        credit_limits=_limits(),
        prerequisites=[],
        progress={},
        risk_cap_mode="hard",
        expected_fail_cap=0.1,
        scenario_budget=3,
    )
    assert result["status"] == "best_effort"
    assert result["risk_cap_exceeded"] is True
    assert any("cố vấn" in warning for warning in result["warnings"])


def test_soft_risk_cap_uses_problem_variable_factory() -> None:
    result = optimize_plan(
        [_course("A")],
        p_student=0.1,
        mean_credits=3,
        credit_limits=_limits(),
        prerequisites=[],
        progress={},
        risk_cap_mode="soft",
        expected_fail_cap=0.1,
        scenario_budget=3,
    )
    assert result["status"] in {"optimal", "best_effort"}
    assert result["risk_cap_exceeded"] is True


def test_best_effort_three_plan_labels_never_claim_safety() -> None:
    plans = three_plans(
        [_course("A")],
        p_student=0.2,
        mean_credits=3,
        credit_limits=_limits(minimum=15, maximum=27),
        prerequisites=[],
        progress={},
        unlock_values={},
        budgets=(15,),
    )
    assert len(plans) == 3
    for plan in plans:
        assert plan["status"] == "best_effort"
        assert "An toàn" not in plan["plan_label"]
        assert any("cố vấn" in warning for warning in plan["warnings"])
    acceleration = next(plan for plan in plans if plan["plan_type"] == "acceleration")
    assert acceleration["fmax"] == pytest.approx(1.0)


def test_forced_retake_conflict_prioritizes_unlock_value_and_warns() -> None:
    result = optimize_plan(
        [
            _course("A", status="failed", must_register=True),
            _course("B", status="failed", must_register=True),
            _course("C"),
        ],
        p_student=0.7,
        mean_credits=3,
        credit_limits=_limits(maximum=3),
        prerequisites=[],
        progress={"A": {"status": "failed"}, "B": {"status": "failed"}},
        unlock_values={"A": 3, "B": 1},
        scenario_budget=3,
    )
    assert result["status"] == "best_effort"
    assert result["regulatory_conflict"] is True
    assert result["selected_course_ids"] == ["A"]
    assert any("cố vấn" in warning for warning in result["warnings"])


def test_discrete_credit_infeasibility_relaxes_minimum_as_best_effort() -> None:
    result = optimize_plan(
        [_course("A", credits=3)],
        p_student=0.8,
        mean_credits=3,
        credit_limits=_limits(minimum=5, maximum=5),
        prerequisites=[],
        progress={},
    )
    assert result["status"] == "best_effort"
    assert result["selected_course_ids"] == ["A"]
    assert result["selected_credits"] == 3
    assert any("cận dưới" in warning for warning in result["warnings"])


def test_one_course_per_elective_slot_is_enforced() -> None:
    result = optimize_plan(
        [
            _course("A", elective_slot="SLOT"),
            _course("B", elective_slot="SLOT"),
            _course("C"),
        ],
        p_student=0.8,
        mean_credits=3,
        credit_limits=_limits(maximum=9),
        prerequisites=[],
        progress={},
    )
    assert not {"A", "B"}.issubset(result["selected_course_ids"])


def test_final_term_cases_compare_limited_and_completion_plan() -> None:
    result = plan_final_semester_cases(
        [_course("LAST")],
        outstanding_course_ids=["LAST"],
        p_student=0.8,
        mean_credits=3,
        credit_limits=_limits(minimum=15, maximum=27),
        prerequisites=[],
        progress={},
    )
    case_a = result["A_regulation_limited"]
    case_b = result["B_completion_plan"]
    assert case_a["selected_credits"] == 3
    assert case_a["status"] == "best_effort"
    assert case_b["selected_course_ids"] == ["LAST"]
    assert case_b["status"] == "final_semester_plan"


def test_scenario_pipeline_does_not_import_legacy_optimizer() -> None:
    from core import optimizer, scenario_v2

    assert "core.ilp" not in inspect.getsource(optimizer)
    assert "core.ilp" not in inspect.getsource(scenario_v2)
