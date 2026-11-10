from __future__ import annotations

from itertools import combinations
from typing import Any

from core.curriculum import (
    load_enriched_curriculum,
    load_rules_config,
)
from core.optimizer import optimize_plan
from core.rules import coreq_constraints, evaluate_student


TEST_FIXTURE = "TEST_FIXTURE"


def fixture_course(
    course_id: str,
    *,
    offerings: str = "both",
    specialization: str = "common",
) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "course_name": course_id,
        "credits": 3,
        "planned_semester": 1,
        "course_type": "bắt buộc",
        "offered_semesters": offerings,
        "group": TEST_FIXTURE,
        "source_label": TEST_FIXTURE,
        "specialization": specialization,
        "counts_toward_total": True,
        "elective_slot": None,
        "slot_required_credits": None,
        "graduation_slot": False,
        "code_source": TEST_FIXTURE,
        "offering_rule": [part.strip() for part in offerings.split(",")],
        "enrichment_label": TEST_FIXTURE,
    }


def evaluate_fixture(
    courses: list[dict[str, Any]],
    prerequisites: list[dict[str, str]],
    progress: dict[str, dict[str, Any]] | None = None,
    *,
    semester: int = 1,
    rules_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return evaluate_student(
        {
            "student_id": "TEST_STUDENT",
            "specialization": "SE",
            "last_completed_semester": 0,
            "progress": progress or {},
        },
        {"courses": courses, "prerequisites": prerequisites},
        rules_cfg or load_rules_config(),
        semester,
    )


def relation(course_id: str, prerequisite_id: str, kind: str) -> dict[str, str]:
    return {
        "course_id": course_id,
        "prerequisite_id": prerequisite_id,
        "type": kind,
        "source_label": TEST_FIXTURE,
    }


def eligible_ids(result: dict[str, Any]) -> set[str]:
    return {str(row["course_id"]) for row in result["eligible_courses"]}


def blocked_reasons(result: dict[str, Any], course_id: str) -> list[dict[str, Any]]:
    return next(
        row["reasons"]
        for row in result["blocked_courses"]
        if row["course_key"] == course_id
    )


def test_coreq_a_b_c_removes_a_when_b_has_unmet_prerequisite() -> None:
    courses = [fixture_course(course_id) for course_id in ["A", "B", "C"]]
    result = evaluate_fixture(
        courses,
        [relation("A", "B", "song hành"), relation("B", "C", "tiên quyết")],
    )
    assert "A" not in eligible_ids(result)
    assert "B" not in eligible_ids(result)
    assert any(reason["code"] == "PREREQUISITE_NOT_COMPLETED" for reason in blocked_reasons(result, "B"))
    assert any(reason["code"] == "COREQUISITE_NOT_ELIGIBLE" for reason in blocked_reasons(result, "A"))


def test_two_way_coreq_keeps_both_when_both_are_eligible() -> None:
    courses = [fixture_course(course_id) for course_id in ["A", "B"]]
    result = evaluate_fixture(
        courses,
        [relation("A", "B", "song hành"), relation("B", "A", "song hành")],
    )
    assert eligible_ids(result) == {"A", "B"}
    assert coreq_constraints(
        [relation("A", "B", "song hành"), relation("B", "A", "song hành")]
    ) == [("A", "B"), ("B", "A")]


def test_two_way_coreq_removes_peer_when_one_side_has_unmet_prerequisite() -> None:
    courses = [fixture_course(course_id) for course_id in ["A", "B", "C"]]
    result = evaluate_fixture(
        courses,
        [
            relation("A", "B", "song hành"),
            relation("B", "A", "song hành"),
            relation("B", "C", "tiên quyết"),
        ],
    )
    assert "A" not in eligible_ids(result)
    assert "B" not in eligible_ids(result)


def test_coreq_in_progress_is_satisfied_without_reselecting_peer() -> None:
    courses = [fixture_course(course_id) for course_id in ["A", "B"]]
    result = evaluate_fixture(
        courses,
        [relation("A", "B", "song hành")],
        {"B": {"status": "in_progress", "attempt_count": 1}},
    )
    assert "A" in eligible_ids(result)
    assert "B" not in eligible_ids(result)


def test_coreq_peer_not_offered_blocks_dependent_course() -> None:
    courses = [
        fixture_course("A", offerings="odd"),
        fixture_course("B", offerings="even"),
    ]
    result = evaluate_fixture(
        courses,
        [relation("A", "B", "song hành")],
        semester=1,
    )
    assert "A" not in eligible_ids(result)
    assert any(
        reason["code"] == "COREQUISITE_NOT_ELIGIBLE"
        for reason in blocked_reasons(result, "A")
    )


def test_coreq_chain_propagates_removal_to_fixed_point() -> None:
    courses = [
        fixture_course(course_id) for course_id in ["A", "B", "C", "D"]
    ]
    result = evaluate_fixture(
        courses,
        [
            relation("A", "B", "song hành"),
            relation("B", "D", "song hành"),
            relation("D", "C", "tiên quyết"),
        ],
    )
    assert not eligible_ids(result).intersection({"A", "B", "D"})
    assert all(
        any(
            reason["code"] == "COREQUISITE_NOT_ELIGIBLE"
            for reason in blocked_reasons(result, course_id)
        )
        for course_id in ["A", "B"]
    )


def test_all_ilp_selection_sets_obey_coreq_inequalities() -> None:
    constraints = coreq_constraints(
        [
            relation("A", "B", "song hành"),
            relation("C", "D", "song hành"),
        ],
        {"A", "B", "C", "D"},
    )
    ids = ["A", "B", "C", "D"]
    feasible = []
    for selected_size in range(len(ids) + 1):
        for selection in combinations(ids, selected_size):
            selected = set(selection)
            constraints_hold = all(
                left not in selected or right in selected
                for left, right in constraints
            )
            if constraints_hold:
                feasible.append(selected)
                assert all(
                    left not in selected or right in selected
                    for left, right in constraints
                )
    assert set() in feasible
    assert {"A", "B", "C", "D"} in feasible
    assert {"A"} not in feasible
    assert {"C"} not in feasible


def test_ilp_solution_obeys_coreq_constraint() -> None:
    result = optimize_plan(
        [
            {"course_id": "A", "credits": 3, "status": "not_taken"},
            {"course_id": "B", "credits": 3, "status": "not_taken"},
        ],
        p_student=0.8,
        mean_credits=3.0,
        credit_limits={"cmin": 3, "cmax": 6, "regime": "TEST_FIXTURE"},
        prerequisites=[relation("A", "B", "song hành")],
        progress={},
        beta=0.0,
        gamma=0.0,
        load_lambda=0.0,
    )
    selected = set(result["selected_course_ids"])
    assert selected == {"A", "B"}


def test_official_hp043_nw_coreq_with_hp037_eligible_or_blocked() -> None:
    curriculum = load_enriched_curriculum()
    rules_cfg = load_rules_config()
    prerequisites = curriculum["prerequisites"]
    hp043_relation = [
        row
        for row in prerequisites
        if row["course_id"] == "HP043-NW"
        and row["prerequisite_id"] == "HP037"
        and row["type"] == "song hành"
    ]
    assert len(hp043_relation) == 1

    ready = evaluate_student(
        {
            "student_id": "NW_READY",
            "specialization": "NW",
            "last_completed_semester": 6,
            "progress": {"HP029": {"status": "completed", "attempt_count": 1}},
        },
        curriculum,
        rules_cfg,
        7,
    )
    assert {"HP037", "HP043-NW"}.issubset(eligible_ids(ready))

    bounded_rules = load_rules_config()
    bounded_rules["program"]["unknowns"]["retake_limit"] = {
        "value": 1,
        "source": TEST_FIXTURE,
    }
    blocked = evaluate_student(
        {
            "student_id": "NW_BLOCKED",
            "specialization": "NW",
            "last_completed_semester": 6,
            "progress": {
                "HP029": {"status": "completed", "attempt_count": 1},
                "HP037": {"status": "failed", "attempt_count": 1},
            },
        },
        curriculum,
        bounded_rules,
        7,
    )
    assert "HP037" not in eligible_ids(blocked)
    assert "HP043-NW" not in eligible_ids(blocked)
    assert any(
        reason.get("course_id") == "HP037"
        and reason["code"] == "COREQUISITE_NOT_ELIGIBLE"
        for reason in blocked_reasons(blocked, "HP043-NW")
    )


def test_outside_program_courses_do_not_change_credit_totals() -> None:
    curriculum = load_enriched_curriculum()
    result = evaluate_student(
        {
            "student_id": "OUTSIDE",
            "specialization": "SE",
            "last_completed_semester": 0,
            "progress": {
                "QPAD011": {"status": "completed", "attempt_count": 1}
            },
        },
        curriculum,
        load_rules_config(),
        1,
    )
    assert result["progress_stats"]["credits_earned"] == 0
    assert any(row["course_id"] == "PHE6000" for row in result["eligible_courses"])
