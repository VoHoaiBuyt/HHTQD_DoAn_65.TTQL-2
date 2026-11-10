from __future__ import annotations

from core.data.consistency import audit_scenario, get_student_progress


TEST_FIXTURE = "TEST_FIXTURE"


def test_progress_queries_are_isolated_by_student() -> None:
    rows = [
        {"student_id": "A", "course_id": "C1", "status": "completed"},
        {"student_id": "B", "course_id": "C1", "status": "failed"},
    ]
    assert get_student_progress(rows, "A") == [rows[0]]
    assert get_student_progress(rows, "B") == [rows[1]]


def test_scenario_audit_recomputes_per_student_without_cross_contamination() -> None:
    courses = [
        {
            "course_id": "C1",
            "credits": "3",
            "course_type": "bắt buộc",
            "planned_semester": "1",
            "specialization": "common",
            "counts_toward_total": True,
        }
    ]
    profiles = [
        {
            "student_id": "A",
            "specialization": "SE",
            "current_semester": "1",
            "cumulative_credits": "99",
            "credits_remaining": "1",
            "failed_courses_count": "0",
            "gpa": "3.0",
            "Curricular units 1st sem (enrolled)": "1",
            "Curricular units 1st sem (approved)": "1",
        },
        {
            "student_id": "B",
            "specialization": "SE",
            "current_semester": "1",
            "cumulative_credits": "0",
            "credits_remaining": "130",
            "failed_courses_count": "0",
            "gpa": "2.0",
        },
    ]
    progress = [
        {
            "student_id": "A",
            "course_id": "C1",
            "status": "completed",
            "grade_10": "8.0",
            "semester_taken": "1",
        }
    ]
    result = audit_scenario(
        profiles,
        progress,
        courses,
        [],
        {"program": {"total_credits": 130, "specializations": ["SE"]}},
    )
    by_student = {row["student_id"]: row for row in result["students"]}
    assert by_student["A"]["recomputed_cumulative_credits"] == 3
    assert by_student["B"]["recomputed_cumulative_credits"] == 0
    assert any(
        defect["code"] == "CUMULATIVE_CREDITS_MISMATCH"
        for defect in by_student["A"]["defects"]
    )
    assert any(
        defect["code"] == "GPA_MISMATCH"
        for defect in by_student["A"]["defects"]
    )
    assert any(
        defect["code"] == "GPA_CANNOT_RECOMPUTE"
        for defect in by_student["B"]["defects"]
    )
