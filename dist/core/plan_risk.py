"""LEGACY exploratory conversion from student pass-rate to course/plan outcomes.

All course-level factors and independence calculations are planning assumptions;
this module does not claim that UCI-697 identifies course-specific outcomes.
"""

from collections.abc import Mapping, Sequence
from math import floor, prod
from typing import Any
import warnings

M3_ABILITY_ORDER = ("Thấp", "Trung bình", "Cao")


def credits_to_curricular_units(total_credits: float, average_credits_per_unit: float) -> int:
    """Map nonnegative credits to units using nearest-integer, half-up rounding."""
    if total_credits < 0:
        raise ValueError("total_credits must be non-negative")
    if average_credits_per_unit <= 0:
        raise ValueError("average_credits_per_unit must be positive")
    units_equivalent = total_credits / average_credits_per_unit
    return floor(units_equivalent + 0.5)


def m3_prime_probability(
    ability_tier: str,
    strata: Mapping[str, Mapping[str, int]],
    *,
    minimum_students: int,
) -> float | None:
    """Return a pooled pass rate by HK1 ability, merging adjacent tiers if sparse.

    Each ``strata`` entry contains ``students``, ``approved_units`` and
    ``enrolled_units`` for REAL observations with HK2 enrollment. Adjacent tiers
    are pooled outward from the requested tier until the configured minimum
    student count is met. Returns ``None`` if it cannot be met.
    """
    if ability_tier not in M3_ABILITY_ORDER:
        raise ValueError(f"Unknown HK1 ability tier: {ability_tier}")
    if minimum_students <= 0:
        raise ValueError("minimum_students must be positive")

    center = M3_ABILITY_ORDER.index(ability_tier)
    for radius in range(len(M3_ABILITY_ORDER)):
        indexes = [
            index
            for index in range(len(M3_ABILITY_ORDER))
            if abs(index - center) <= radius
        ]
        selected = [strata.get(M3_ABILITY_ORDER[index], {}) for index in indexes]
        student_count = sum(int(item.get("students", 0)) for item in selected)
        enrolled_units = sum(int(item.get("enrolled_units", 0)) for item in selected)
        approved_units = sum(int(item.get("approved_units", 0)) for item in selected)
        if student_count >= minimum_students and enrolled_units > 0:
            return min(1.0, max(0.0, approved_units / enrolled_units))
    return None


def plan_risk(
    student_id: str,
    plan: Sequence[Mapping[str, Any]],
    *,
    p_student_pass: float,
    difficulty_factors: Mapping[str, float] | None = None,
    load_multiplier: float = 1.0,
    retake_multiplier: float = 1.0,
    average_credits_per_unit: float,
) -> dict[str, Any]:
    """LEGACY: estimate outcomes using simulated difficulty and load factors.

    Parameters
    ----------
    student_id:
        Simulated or real student key used for traceability.
    plan:
        Course rows with ``course_id``, positive ``credits``, and optional
        ``group``, ``difficulty_factor``, ``status``, and ``attempt_count``.
    p_student_pass:
        Base probability/rate of passing a curricular unit, estimated at the
        student level from T0 + T1_known features. It is not P(Dropout).
    difficulty_factors:
        SIMULATED factors keyed by course ID first, then course group. Defaults
        to 1.0 when no factor is found.
    load_multiplier:
        Explicit scenario-only monotone multiplier in [0, 1]; not learned as a
        causal effect from the observational UCI data.
    retake_multiplier:
        Explicit scenario-only multiplier applied only to repeat attempts
        (status ``failed`` or attempt_count > 1).
    average_credits_per_unit:
        Mean credits per course in the SIMULATED curriculum, used only to
        convert plan credits to approximate UCI curricular units.

    Returns
    -------
    dict
        Per-course pass probabilities, expected passed credits, expected failed
        count, independence-based probabilities of >=1/>=2 failures, and a
        0–100 credits-weighted plan risk index (``None`` for an empty plan).
    """
    if not student_id:
        raise ValueError("student_id must be non-empty")
    warnings.warn(
        "core.plan_risk.plan_risk is a LEGACY Stage 1 prototype; "
        "it uses simulated difficulty/load factors.",
        DeprecationWarning,
        stacklevel=2,
    )
    for name, value in (
        ("p_student_pass", p_student_pass),
        ("load_multiplier", load_multiplier),
        ("retake_multiplier", retake_multiplier),
        ("average_credits_per_unit", average_credits_per_unit),
    ):
        if not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
    if not 0 <= p_student_pass <= 1:
        raise ValueError("p_student_pass must be between 0 and 1")
    if not 0 <= load_multiplier <= 1:
        raise ValueError("load_multiplier must be between 0 and 1")
    if retake_multiplier < 0:
        raise ValueError("retake_multiplier must be non-negative")
    if average_credits_per_unit <= 0:
        raise ValueError("average_credits_per_unit must be positive")

    factors = difficulty_factors or {}
    course_probabilities: dict[str, float] = {}
    total_credits = 0.0
    for course in plan:
        course_id = str(course.get("course_id", ""))
        if not course_id:
            raise ValueError("Every plan course must have course_id")
        if course_id in course_probabilities:
            raise ValueError(f"Duplicate course_id in plan: {course_id}")
        credits = float(course.get("credits", 0))
        if credits <= 0:
            raise ValueError(f"Course {course_id} must have positive credits")
        group = str(course.get("group", ""))
        factor = float(
            course.get(
                "difficulty_factor",
                factors.get(course_id, factors.get(group, 1.0)),
            )
        )
        if factor < 0:
            raise ValueError(f"Difficulty factor for {course_id} must be non-negative")

        repeat = (
            str(course.get("status", "")) == "failed"
            or int(course.get("attempt_count", 0)) > 1
        )
        retake_factor = retake_multiplier if repeat else 1.0
        probability = p_student_pass * factor * load_multiplier * retake_factor
        course_probabilities[course_id] = min(1.0, max(0.0, probability))
        total_credits += credits

    probabilities = list(course_probabilities.values())
    failure_probabilities = [1.0 - probability for probability in probabilities]
    expected_credits_passed = sum(
        float(course["credits"]) * course_probabilities[str(course["course_id"])]
        for course in plan
    )
    expected_failed = sum(failure_probabilities)
    all_pass_probability = prod(probabilities)
    exactly_one_failure_probability = sum(
        failure_probabilities[index]
        * prod(
            probability
            for other_index, probability in enumerate(probabilities)
            if other_index != index
        )
        for index in range(len(probabilities))
    )

    return {
        "student_id": student_id,
        "p_pass_by_course": course_probabilities,
        "expected_credits_passed": expected_credits_passed,
        "expected_failed_courses": expected_failed,
        "prob_at_least_k_fail": {
            "k=1": 1.0 - all_pass_probability,
            "k=2": 1.0 - all_pass_probability - exactly_one_failure_probability,
        },
        "plan_risk_index": (
            100.0 * (1.0 - expected_credits_passed / total_credits)
            if total_credits
            else None
        ),
        "total_plan_credits": total_credits,
        "equivalent_curricular_units": total_credits / average_credits_per_unit,
        "rounded_curricular_units_half_up": credits_to_curricular_units(
            total_credits,
            average_credits_per_unit,
        ),
        "independence_assumption": True,
    }


def _self_test() -> None:
    """Run a deterministic arithmetic check for local validation."""
    plan = [
        {"course_id": "A", "credits": 3},
        {"course_id": "B", "credits": 2, "status": "failed", "attempt_count": 2},
    ]
    result = plan_risk(
        "TEST",
        plan,
        p_student_pass=0.8,
        difficulty_factors={"A": 1.0, "B": 0.9},
        load_multiplier=0.95,
        retake_multiplier=1.05,
        average_credits_per_unit=2.5,
    )
    assert result["p_pass_by_course"]["A"] == 0.76
    assert result["p_pass_by_course"]["B"] == 0.8 * 0.9 * 0.95 * 1.05
    assert 0 <= result["prob_at_least_k_fail"]["k=2"] <= result["prob_at_least_k_fail"]["k=1"] <= 1
    assert 0 <= result["plan_risk_index"] <= 100
    empty_plan = plan_risk(
        "EMPTY",
        [],
        p_student_pass=0.8,
        average_credits_per_unit=2.5,
    )
    assert empty_plan["plan_risk_index"] is None
    assert credits_to_curricular_units(12.0, 8 / 3) == 5
    assert credits_to_curricular_units(0.0, 8 / 3) == 0
    assert credits_to_curricular_units(15.0, 8 / 3) >= credits_to_curricular_units(
        12.0, 8 / 3
    )
    merged_rate = m3_prime_probability(
        "Trung bình",
        {
            "Thấp": {"students": 10, "approved_units": 4, "enrolled_units": 10},
            "Trung bình": {
                "students": 15,
                "approved_units": 12,
                "enrolled_units": 20,
            },
            "Cao": {"students": 40, "approved_units": 36, "enrolled_units": 40},
        },
        minimum_students=30,
    )
    assert merged_rate == (4 + 12 + 36) / (10 + 20 + 40)


if __name__ == "__main__":
    _self_test()
    print("plan_risk self-test: PASS")
