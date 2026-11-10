"""Audit scenario inputs against the OFFICIAL curriculum without editing them."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from typing import Any

from core.curriculum import (
    ROOT,
    enrich_courses,
    load_curriculum,
    load_enrichment_config,
    load_program_config,
    read_csv,
)
from core.metrics import update_metrics


SCENARIO_DIR = ROOT / "data" / "scenarios_v1"
PROFILE_PATH = SCENARIO_DIR / "student_profile.csv"
PROGRESS_PATH = SCENARIO_DIR / "student_progress.csv"
OUTPUT_PATH = ROOT / "reports" / "generated" / "scenario_v1_defects.json"


def get_student_progress(
    progress_rows: list[dict[str, Any]],
    student_id: str,
) -> list[dict[str, Any]]:
    """Return rows for one student only; no shared mutable/cache state is used."""
    return [
        dict(row)
        for row in progress_rows
        if str(row.get("student_id")) == str(student_id)
    ]


def audit_scenario(
    profiles: list[dict[str, Any]],
    progress_rows: list[dict[str, Any]],
    courses: list[dict[str, Any]],
    prerequisites: list[dict[str, Any]],
    program_config: dict[str, Any],
) -> dict[str, Any]:
    course_by_id = {str(row["course_id"]): row for row in courses}
    prereq_by_course: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prerequisites:
        prereq_by_course[str(row["course_id"])].append(row)
    profile_ids = [str(row["student_id"]) for row in profiles]
    profile_set = set(profile_ids)
    course_references = sorted(
        {
            str(row.get("course_id"))
            for row in progress_rows
            if str(row.get("course_id")) not in course_by_id
        }
    )
    progress_by_student: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in progress_rows:
        progress_by_student[str(row["student_id"])].append(row)
    orphan_progress_students = sorted(
        set(progress_by_student) - profile_set
    )

    total_credits = int(program_config["program"]["total_credits"])
    students: list[dict[str, Any]] = []
    for profile in profiles:
        student_id = str(profile["student_id"])
        own_rows = get_student_progress(progress_rows, student_id)
        defects: list[dict[str, Any]] = []
        counted_rows = [row for row in own_rows if row["course_id"] in course_by_id]
        seen: set[str] = set()
        duplicate_courses = []
        for row in counted_rows:
            course_id = str(row["course_id"])
            if course_id in seen:
                duplicate_courses.append(course_id)
            seen.add(course_id)
        if duplicate_courses:
            defects.append(
                {
                    "code": "DUPLICATE_STUDENT_COURSE",
                    "course_ids": sorted(set(duplicate_courses)),
                }
            )

        earned = sum(
            int(course_by_id[str(row["course_id"])]["credits"])
            for row in counted_rows
            if row.get("status") == "completed"
            and course_by_id[str(row["course_id"])].get(
                "counts_toward_total", True
            )
        )
        failed_count = sum(row.get("status") == "failed" for row in counted_rows)
        expected_remaining = max(0, total_credits - earned)
        if (
            int(
                profile.get(
                    "last_completed_semester",
                    profile.get("current_semester", 0),
                )
                or 0
            )
            >= 8
            and expected_remaining > 0
        ):
            defects.append(
                {
                    "code": "HK8_REMAINING_CREDITS",
                    "recomputed_credits_remaining": expected_remaining,
                    "message": "Scenario reaches semester 8 with required program credits still outstanding.",
                }
            )
        if (
            "cumulative_credits" in profile
            and str(profile["cumulative_credits"]) != str(earned)
        ):
            defects.append(
                {
                    "code": "CUMULATIVE_CREDITS_MISMATCH",
                    "profile_value": profile["cumulative_credits"],
                    "recomputed_value": earned,
                }
            )
        if (
            "credits_remaining" in profile
            and str(profile["credits_remaining"]) != str(expected_remaining)
        ):
            defects.append(
                {
                    "code": "CREDITS_REMAINING_MISMATCH",
                    "profile_value": profile["credits_remaining"],
                    "recomputed_value": expected_remaining,
                }
            )
        if (
            "failed_courses_count" in profile
            and str(profile["failed_courses_count"]) != str(failed_count)
        ):
            defects.append(
                {
                    "code": "FAILED_COURSES_COUNT_MISMATCH",
                    "profile_value": profile["failed_courses_count"],
                    "recomputed_value": failed_count,
                }
            )

        completed_grades = [
            float(row["grade_10"])
            for row in counted_rows
            if row.get("status") == "completed" and row.get("grade_10") not in {"", None}
        ]
        if len(set(completed_grades)) == 1 and len(completed_grades) > 1:
            defects.append(
                {
                    "code": "CONSTANT_COMPLETED_GRADES",
                    "grade_10": completed_grades[0],
                    "completed_course_count": len(completed_grades),
                }
            )
        completed_rows = [
            row for row in counted_rows if row.get("status") == "completed"
        ]
        completed_gpa_rows = [
            row
            for row in completed_rows
            if row.get("grade_10") not in {"", None}
        ]
        recomputed_gpa_10: float | None = None
        if completed_rows and len(completed_gpa_rows) == len(completed_rows):
            gpa_credits = sum(
                int(course_by_id[str(row["course_id"])]["credits"])
                for row in completed_gpa_rows
            )
            if gpa_credits:
                recomputed_gpa_10 = sum(
                    int(course_by_id[str(row["course_id"])]["credits"])
                    * float(row["grade_10"])
                    for row in completed_gpa_rows
                ) / gpa_credits
        if profile.get("gpa") not in {"", None} and recomputed_gpa_10 is not None:
            profile_gpa = float(profile["gpa"])
            if abs(profile_gpa - recomputed_gpa_10) > 1e-6:
                defects.append(
                    {
                        "code": "GPA_MISMATCH",
                        "profile_value": profile_gpa,
                        "recomputed_gpa_10": recomputed_gpa_10,
                        "profile_scale": "UNCONFIRMED",
                        "comparison_note": (
                            "No scale conversion is applied; compare only if the profile "
                            "GPA is confirmed to use the 10-point scale."
                        ),
                    }
                )
        elif profile.get("gpa") not in {"", None}:
            defects.append(
                {
                    "code": "GPA_CANNOT_RECOMPUTE",
                    "reason": "At least one completed course lacks a grade_10 value.",
                }
            )

        semester = int(
            profile.get("last_completed_semester", profile.get("current_semester", 0))
            or 0
        )
        has_t1_features = any(
            str(key).startswith("Curricular units 1st sem")
            for key in profile
        )
        if has_t1_features and semester != 1:
            defects.append(
                {
                    "code": "T1_MODEL_SEMESTER_MISMATCH",
                    "scenario_semester": semester,
                    "expected_semester": 1,
                    "model_label": "extension_assumption (GIẢ ĐỊNH năm đầu) or off",
                }
            )

        semester_one_rows = [
            row for row in counted_rows if str(row.get("semester_taken")) == "1"
        ]
        enrolled_count = sum(
            row.get("status") in {"completed", "failed", "in_progress"}
            for row in semester_one_rows
        )
        approved_count = sum(
            row.get("status") == "completed" for row in semester_one_rows
        )
        feature_checks = [
            (
                "Curricular units 1st sem (enrolled)",
                enrolled_count,
                "HK1 progress row count is treated as an approximate unit count.",
            ),
            (
                "Curricular units 1st sem (approved)",
                approved_count,
                "Completed HK1 course row count is treated as an approximate unit count.",
            ),
        ]
        for field, recomputed, assumption in feature_checks:
            if field not in profile or profile[field] in {"", None}:
                continue
            if float(profile[field]) != recomputed:
                defects.append(
                    {
                        "code": "HK1_FEATURE_PROGRESS_MISMATCH",
                        "feature": field,
                        "profile_value": profile[field],
                        "recomputed_value": recomputed,
                        "label": "GIẢ ĐỊNH (suy từ CTĐT)",
                        "comparison_rule": assumption,
                    }
                )

        history_errors = []
        status_by_course = {
            str(row["course_id"]): str(row.get("status", "not_taken"))
            for row in counted_rows
        }
        term_by_course = {
            str(row["course_id"]): (
                int(row["semester_taken"])
                if str(row.get("semester_taken", "")).isdigit()
                else None
            )
            for row in counted_rows
        }
        for row in counted_rows:
            course_id = str(row["course_id"])
            if row.get("status") != "completed":
                continue
            for relation in prereq_by_course.get(course_id, []):
                prerequisite_id = str(relation["prerequisite_id"])
                prerequisite_status = status_by_course.get(
                    prerequisite_id, "not_taken"
                )
                prerequisite_term = term_by_course.get(prerequisite_id)
                course_term = term_by_course.get(course_id)
                relation_type = str(relation["type"])
                valid = (
                    prerequisite_status == "completed"
                    and prerequisite_term is not None
                    and course_term is not None
                    and prerequisite_term < course_term
                    if relation_type == "tiên quyết"
                    else prerequisite_status in {"completed", "in_progress"}
                    and prerequisite_term is not None
                    and course_term is not None
                    and prerequisite_term <= course_term
                    if relation_type == "song hành"
                    else True
                )
                if not valid:
                    history_errors.append(
                        {
                            "course_id": course_id,
                            "prerequisite_id": prerequisite_id,
                            "type": relation_type,
                            "prerequisite_status": prerequisite_status,
                            "prerequisite_semester": prerequisite_term,
                            "course_semester": course_term,
                        }
                    )
        if history_errors:
            defects.append(
                {
                    "code": "COMPLETED_COURSE_PREREQUISITE_HISTORY_INVALID",
                    "relations": history_errors,
                }
            )

        specialization = str(profile.get("specialization", "UNKNOWN"))
        specialization_check: dict[str, Any]
        if specialization == "UNKNOWN":
            specialization_check = {
                "status": "UNKNOWN",
                "reason": "No specialization field is present; branch-specific completion cannot be evaluated.",
            }
            defects.append(
                {
                    "code": "SPECIALIZATION_AND_ELECTIVE_COMPLETION_UNKNOWN",
                    "reason": (
                        "The profile has no specialization; required branch courses "
                        "and elective slots cannot be determined."
                    ),
                }
            )
        else:
            required_ids = {
                str(row["course_id"])
                for row in courses
                if row.get("specialization") in {"common", specialization}
                and row.get("course_type") == "bắt buộc"
                and row.get("counts_toward_total", True)
            }
            done_ids = {
                str(row["course_id"])
                for row in counted_rows
                if row.get("status") == "completed"
            }
            specialization_check = {
                "status": "CHECKED",
                "missing_required_course_ids": sorted(required_ids - done_ids),
            }
            required_slots = (
                program_config["program"]
                .get("required_elective_slots", {})
                .get(specialization)
            )
            if required_slots is not None:
                completed_slots = {
                    str(course_by_id[str(row["course_id"])].get("elective_slot"))
                    for row in counted_rows
                    if row.get("status") == "completed"
                    and str(row["course_id"]) in course_by_id
                    and course_by_id[str(row["course_id"])].get("elective_slot")
                    is not None
                }
                missing_slots = sorted(set(required_slots) - completed_slots)
                specialization_check["missing_elective_slots"] = missing_slots
            else:
                specialization_check["missing_elective_slots"] = "UNKNOWN"
            if required_ids - done_ids and semester >= 8:
                defects.append(
                    {
                        "code": "MISSING_SPECIALIZATION_OR_MANDATORY_COURSES",
                        "course_ids": sorted(required_ids - done_ids),
                    }
                )
            if (
                required_slots is not None
                and specialization_check["missing_elective_slots"]
                and semester >= 8
            ):
                defects.append(
                    {
                        "code": "MISSING_ELECTIVE_SLOTS",
                        "slot_ids": specialization_check["missing_elective_slots"],
                    }
                )
        students.append(
            {
                "student_id": student_id,
                "scenario_semester": semester,
                "recomputed_cumulative_credits": earned,
                "recomputed_credits_remaining": expected_remaining,
                "recomputed_failed_courses_count": failed_count,
                "recomputed_gpa_10": recomputed_gpa_10,
                "specialization_check": specialization_check,
                "defects": defects,
                "unconfirmed": [
                    {
                        "field": "GPA",
                        "status": "UNCONFIRMED",
                        "reason": "No official formula/threshold was provided to recompute GPA from grade_10.",
                    }
                ]
                if profile.get("gpa") not in {"", None}
                else [],
            }
        )

    return {
        "status": "CHECKED",
        "source_label": "SCENARIO",
        "inputs": {
            "profile_rows": len(profiles),
            "progress_rows": len(progress_rows),
        },
        "global_defects": {
            "unknown_progress_course_ids": course_references,
            "progress_for_unknown_students": orphan_progress_students,
            "duplicate_profile_ids": sorted(
                student_id
                for student_id, count in Counter(profile_ids).items()
                if count > 1
            ),
        },
        "students": students,
        "unknown": [
            {
                "field": "GPA conversion/consistency",
                "source": "NOT_FOUND",
                "reason": "No official GPA computation policy was provided.",
            }
        ],
        "assumptions": [
            {
                "label": "GIẢ ĐỊNH (suy từ CTĐT)",
                "rule": "Completed HK1 course count approximates UCI approved units; taken HK1 course count approximates enrolled units.",
            }
        ],
    }


def main() -> int:
    missing = [
        str(path.relative_to(ROOT))
        for path in (PROFILE_PATH, PROGRESS_PATH)
        if not path.is_file()
    ]
    if missing:
        result: dict[str, Any] = {
            "status": "NOT_RUN",
            "source_label": "SCENARIO",
            "missing_inputs": missing,
            "reason": (
                "The checkout has no data/scenarios_v1 inputs. No scenario rows "
                "were substituted or inferred."
            ),
            "students": [],
        }
    else:
        official = load_curriculum()
        curriculum_rows = enrich_courses(
            official["courses"], load_enrichment_config()
        )
        result = audit_scenario(
            read_csv(PROFILE_PATH),
            read_csv(PROGRESS_PATH),
            curriculum_rows,
            official["prerequisites"],
            load_program_config(),
        )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    update_metrics(
        {
            "scenario_v1_consistency": {
                "status": result["status"],
                "students": len(result.get("students", [])),
                "defect_count": sum(
                    len(student.get("defects", []))
                    for student in result.get("students", [])
                ),
                "defects_by_code": dict(
                    sorted(
                        Counter(
                            defect["code"]
                            for student in result.get("students", [])
                            for defect in student.get("defects", [])
                        ).items()
                    )
                ),
                "specialization_unknown_count": sum(
                    student.get("specialization_check", {}).get("status")
                    == "UNKNOWN"
                    for student in result.get("students", [])
                ),
                "gpa_unconfirmed_count": sum(
                    any(
                        item.get("field") == "GPA"
                        for item in student.get("unconfirmed", [])
                    )
                    for student in result.get("students", [])
                ),
                "missing_inputs": result.get("missing_inputs", []),
            }
        }
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
