from __future__ import annotations

import json
from typing import Any

from core.curriculum import load_enriched_curriculum, load_rules_config
from core.rules import evaluate_student


TEST_FIXTURE = "TEST_FIXTURE"


def north_west_demo() -> tuple[dict[str, Any], dict[str, Any], int]:
    curriculum = load_enriched_curriculum()
    progress = {
        str(course["course_id"]): {
            "status": (
                "failed"
                if str(course["course_id"]) == "HP024"
                else "completed"
            ),
            "grade_10": 4.0 if str(course["course_id"]) == "HP024" else 7.0,
            "attempt_count": 1,
            "semester_taken": int(course["planned_semester"]),
        }
        for course in curriculum["courses"]
        if int(course["planned_semester"]) <= 2
        and course["specialization"] in {"common", "NW"}
    }
    progress["POL307"] = {
        "status": "completed",
        "grade_10": 7.0,
        "attempt_count": 1,
        "semester_taken": 1,
    }
    profile = {
        "student_id": TEST_FIXTURE,
        "specialization": "NW",
        "last_completed_semester": 2,
        "progress": progress,
    }
    return profile, curriculum, 3


def test_nw_example_blocks_hp029_and_transitive_dependents() -> None:
    profile, curriculum, target_semester = north_west_demo()
    result = evaluate_student(profile, curriculum, load_rules_config(), target_semester)
    eligible = {course["course_id"] for course in result["eligible_courses"]}
    blocked = {
        course["course_key"]: course["reasons"]
        for course in result["blocked_courses"]
    }
    assert "HP029" not in eligible
    assert any(
        reason.get("course_id") == "HP024"
        and reason["code"] == "PREREQUISITE_NOT_COMPLETED"
        for reason in blocked["HP029"]
    )
    for course_id in ("HP039-NW", "HP040-NW", "HP041-NW", "HP042-NW", "HP044-NW"):
        assert course_id not in eligible
        assert any(
            reason["code"] == "PREREQUISITE_NOT_COMPLETED"
            and (
                reason.get("course_id") == "HP029"
                or "HP024" in reason.get("root_causes", [])
            )
            for reason in blocked[course_id]
        )
    assert result["student_id"] == TEST_FIXTURE


if __name__ == "__main__":
    profile, curriculum, target_semester = north_west_demo()
    result = evaluate_student(
        profile,
        curriculum,
        load_rules_config(),
        target_semester,
    )
    print(
        json.dumps(
            {
                "eligible_courses": result["eligible_courses"],
                "blocked_courses": result["blocked_courses"],
                "progress_stats": result["progress_stats"],
                "academic_flags": result["academic_flags"],
                "edge_case_flags": result["edge_case_flags"],
                "forced_retakes": result["forced_retakes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
