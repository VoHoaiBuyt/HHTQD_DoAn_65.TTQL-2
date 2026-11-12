"""Seeded scenario-v2 data generation, validation, and planning outputs."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from core.curriculum import (
    ROOT,
    load_enriched_curriculum,
    load_rules_config,
    read_yaml,
)
from core.gpa import cumulative_gpa, round_course_grade, semester_gpa
from core.metrics import read_metrics, write_metrics
from core.ml_data import read_source, source_feature_columns
from core.optimizer import (
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    DEFAULT_LAMBDA,
    LOAD_BUDGETS,
    RETAKE_POLICY,
    compute_unlock_values,
    estimated_graduation_semester,
    optimize_plan,
    plan_final_semester_cases,
    three_plans,
)
from core.pass_prob import p_student_pass
from core.rules import credit_limits, evaluate_student


SCENARIO_DIR = ROOT / "data" / "scenarios"
PROFILE_PATH = SCENARIO_DIR / "student_profile_v2.csv"
PROGRESS_PATH = SCENARIO_DIR / "student_progress_v2.csv"
VALIDATION_PATH = ROOT / "reports" / "generated" / "scenario_v2_validation.json"
PLANS_PATH = ROOT / "reports" / "generated" / "plans_by_student.csv"
SENSITIVITY_PATH = ROOT / "reports" / "generated" / "ilp_sensitivity.csv"
UNLOCK_PATH = ROOT / "reports" / "generated" / "unlock_value_summary.json"
SPEC_PATH = ROOT / "reports" / "generated" / "optimization_spec.md"
SEED = 20261105
LABEL_SCENARIO = "SCENARIO"
LABEL_REAL = "REAL (UCI-697)"
OPTIMIZER_CONFIG_PATH = ROOT / "config" / "optimizer_scenario_v2.yaml"

PERSONAS = [
    {
        "student_id": "V2-001",
        "persona": "Giỏi",
        "persona_purpose": "T1 tốt, tín chỉ đạt kỳ vọng cao",
        "last_completed_semester": 1,
        "target_semester": 2,
        "ml_scope": "T1_valid",
        "grade_center": 8.5,
    },
    {
        "student_id": "V2-002",
        "persona": "Trung bình",
        "persona_purpose": "T1 trung bình, so sánh phương án cân bằng",
        "last_completed_semester": 1,
        "target_semester": 2,
        "ml_scope": "T1_valid",
        "grade_center": 6.6,
    },
    {
        "student_id": "V2-003",
        "persona": "Yếu kém",
        "persona_purpose": "TBHK dưới 5,00 và trượt POL307",
        "last_completed_semester": 1,
        "target_semester": 2,
        "ml_scope": "T1_valid",
        "grade_center": 4.3,
        "failed_ids": ["POL307"],
    },
    {
        "student_id": "V2-004",
        "persona": "Sát ngưỡng 5,00",
        "persona_purpose": "Kiểm tra biên 12-18 so với 15-27",
        "last_completed_semester": 1,
        "target_semester": 2,
        "ml_scope": "T1_valid",
        "grade_center": 5.0,
        "exact_first_term_grade": 5.0,
    },
    {
        "student_id": "V2-005",
        "persona": "Nợ đọng sát W1",
        "persona_purpose": "Nhiều môn nợ 22-26 tín chỉ ở kỳ kế tiếp",
        "last_completed_semester": 5,
        "target_semester": 6,
        "ml_scope": "extension_assumption",
        "grade_center": 6.0,
        "debt_target": 24,
    },
    {
        "student_id": "V2-006",
        "persona": "Trượt môn chặn chuỗi",
        "persona_purpose": "HP024 trượt chặn HP029 và các môn mạng phụ thuộc",
        "last_completed_semester": 2,
        "target_semester": 3,
        "ml_scope": "extension_assumption",
        "grade_center": 6.0,
        "failed_ids": ["HP024"],
    },
    {
        "student_id": "V2-007",
        "persona": "Gần tốt nghiệp",
        "persona_purpose": "Chỉ còn HP037 học lại, mở kỳ lẻ",
        "last_completed_semester": 8,
        "target_semester": 9,
        "ml_scope": "extension_assumption",
        "grade_center": 6.4,
        "failed_ids": ["HP037"],
    },
    {
        "student_id": "V2-008",
        "persona": "Đã đủ điều kiện tốt nghiệp",
        "persona_purpose": "Kiểm tra trạng thái graduation_ready và kỳ cuối",
        "last_completed_semester": 8,
        "target_semester": 9,
        "ml_scope": "extension_assumption",
        "grade_center": 7.0,
        "graduation_ready": True,
    },
    {
        "student_id": "V2-009",
        "persona": "Mở lại ô tự chọn",
        "persona_purpose": "Trượt một môn tự chọn, kiểm tra chọn lại trong cùng ô",
        "last_completed_semester": 4,
        "target_semester": 6,
        "ml_scope": "extension_assumption",
        "grade_center": 6.2,
        "failed_elective_slot": True,
    },
]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except (TypeError, ValueError):
        pass
    return value.item() if hasattr(value, "item") else value


def _choose_program_courses(
    curriculum: dict[str, Any],
    specialization: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    all_courses = curriculum["courses"]
    program = curriculum["program_config"]["program"]
    required_slots = list(program["required_elective_slots"][specialization])
    required_slots.append(str(curriculum["enrichment_config"]["graduation_slot"]["slot"]))
    course_type_mandatory = next(
        row["course_type"] for row in all_courses if row["course_type"].strip()
    )
    mandatory = [
        row
        for row in all_courses
        if row["course_type"] == course_type_mandatory
        and bool(row["counts_toward_total"])
        and row["specialization"] in {"common", specialization}
    ]
    choices: dict[str, str] = {}
    selected_electives: list[dict[str, Any]] = []
    for slot in required_slots:
        alternatives = sorted(
            (
                row
                for row in all_courses
                if bool(row["counts_toward_total"])
                and row.get("elective_slot") == slot
                and row["specialization"] in {"common", specialization}
            ),
            key=lambda row: str(row["course_id"]),
        )
        if not alternatives:
            raise ValueError(f"No OFFICIAL course choice for slot {slot}")
        choice = alternatives[0]
        choices[slot] = str(choice["course_id"])
        selected_electives.append(choice)
    program_courses = mandatory + selected_electives
    if len({str(row["course_id"]) for row in program_courses}) != len(program_courses):
        raise ValueError("A course was selected as both mandatory and an elective")
    total = sum(int(row["credits"]) for row in program_courses)
    expected_total = int(program["total_credits"])
    if total != expected_total:
        raise ValueError(
            f"OFFICIAL {specialization} course selection totals {total}, expected {expected_total}"
        )
    return program_courses, choices


def _with_retake_factors(
    eligible_courses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for source in eligible_courses:
        course = dict(source)
        if course.get("status") == "failed":
            attempts = int(course.get("attempt_count", 1) or 1)
            course["retake_multiplier"] = float(
                RETAKE_POLICY["repeated_attempt"]
                if attempts > 1
                else RETAKE_POLICY["first_retake"]
            )
        else:
            course["retake_multiplier"] = float(RETAKE_POLICY["non_retake"])
        result.append(course)
    return result


def _find_credit_subset(
    courses: list[dict[str, Any]],
    target: int,
) -> list[dict[str, Any]]:
    best: dict[int, list[dict[str, Any]]] = {0: []}
    for course in courses:
        credits = int(course["credits"])
        for subtotal, selected in list(best.items()):
            new_total = subtotal + credits
            if new_total <= target and new_total not in best:
                best[new_total] = selected + [course]
    if target in best:
        return best[target]
    nearby = [
        value for value in best if 22 <= value <= 26
    ]
    if not nearby:
        raise ValueError("Cannot create the requested official-credit W1 scenario")
    return best[min(nearby, key=lambda value: abs(value - target))]


def _real_vectors() -> tuple[list[str], list[dict[str, Any]]]:
    frame = read_source()
    columns = source_feature_columns(include_sensitivity_features=True)
    rows = frame[columns].to_dict(orient="records")
    ratio_column = "Curricular units 1st sem (approved)"
    enrolled_column = "Curricular units 1st sem (enrolled)"
    rows.sort(
        key=lambda row: (
            float(row[ratio_column]) / max(float(row[enrolled_column]), 1.0),
            str(row.get("Course", "")),
        )
    )
    if len(rows) < len(PERSONAS):
        raise ValueError("REAL (UCI-697) does not contain enough feature vectors")
    indexes = [
        round(index * (len(rows) - 1) / (len(PERSONAS) - 1))
        for index in range(len(PERSONAS))
    ]
    return columns, [rows[index] for index in indexes]


def generate_scenario_rows(
    *,
    seed: int = SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    curriculum = load_enriched_curriculum()
    rules_config = load_rules_config()
    optimizer_config = read_yaml(OPTIMIZER_CONFIG_PATH)
    specialization = str(optimizer_config["scenario"]["default_specialization"])
    program_courses, elective_choices = _choose_program_courses(
        curriculum, specialization
    )
    program = curriculum["program_config"]["program"]
    slot_credits = {
        str(slot): int(credits)
        for slot, credits in curriculum["enrichment_config"]["slot_required_credits"].items()
    }
    profile_features, real_vectors = _real_vectors()
    course_by_id = {str(row["course_id"]): row for row in curriculum["courses"]}
    selected_ids = {str(row["course_id"]) for row in program_courses}
    mandatory_token = next(row["course_type"] for row in program_courses)
    program_ids = {
        str(row["course_id"])
        for row in program_courses
        if row["course_type"] == mandatory_token
    }
    profiles: list[dict[str, Any]] = []
    progress_rows: list[dict[str, Any]] = []
    scenario_records: dict[str, Any] = {}

    for persona_index, definition in enumerate(PERSONAS):
        student_id = str(definition["student_id"])
        last_semester = int(definition["last_completed_semester"])
        fail_ids = set(str(value) for value in definition.get("failed_ids", []))
        if definition.get("debt_target"):
            debt_candidates = [
                row
                for row in program_courses
                if row["course_type"] == mandatory_token
                and int(row["planned_semester"]) <= last_semester
                and str(row["course_id"]) not in fail_ids
            ]
            failures = _find_credit_subset(
                debt_candidates, int(definition["debt_target"])
            )
            fail_ids.update(str(row["course_id"]) for row in failures)
        if definition.get("failed_elective_slot"):
            failed_choice = next(
                (
                    row
                    for row in program_courses
                    if row.get("elective_slot")
                    and int(row["planned_semester"]) <= last_semester
                    and str(row["course_id"]) not in fail_ids
                ),
                None,
            )
            if failed_choice is None:
                raise ValueError("No eligible OFFICIAL elective for failed-slot scenario")
            fail_ids.add(str(failed_choice["course_id"]))

        per_course: dict[str, dict[str, Any]] = {}
        selected_slot_ids = set(elective_choices.values())
        for course in curriculum["courses"]:
            course_id = str(course["course_id"])
            is_program_course = course_id in selected_ids
            selected_in_slot = course_id in selected_slot_ids
            planned = int(course["planned_semester"])
            status = "not_taken"
            grade: float | None = None
            semester_taken: int | str = ""
            attempts = 0
            if is_program_course and planned <= last_semester:
                status = "completed"
                grade = round_course_grade(
                    max(
                        5.05,
                        min(
                            9.9,
                            float(definition["grade_center"]) + rng.gauss(0, 0.65),
                        ),
                    ),
                    rules_config["regulation"],
                )
                semester_taken = planned
                attempts = 1
            if course_id in fail_ids:
                status = "failed"
                grade = (
                    3.0
                    if course_id == "POL307" and student_id == "V2-003"
                    else max(1.0, min(4.9, 3.6 + rng.gauss(0, 0.45)))
                )
                semester_taken = planned
                attempts = 1
            if definition.get("exact_first_term_grade") and planned == 1 and status == "completed":
                grade = float(definition["exact_first_term_grade"])
            per_course[course_id] = {
                "status": status,
                "grade_10": grade,
                "attempt_count": attempts,
                "semester_taken": semester_taken,
                "selected_in_slot": selected_in_slot,
            }

        if student_id == "V2-004":
            # A uniform 5.0 on HK1 makes the boundary exact after credit weighting.
            for course_id, record in per_course.items():
                course = course_by_id[course_id]
                if int(course["planned_semester"]) == 1 and record["status"] in {"completed", "failed"}:
                    record["grade_10"] = 5.0
        profile_for_gpa = per_course
        gpa_value = cumulative_gpa(
            curriculum["courses"], profile_for_gpa, rules_config["regulation"]
        )
        previous_gpa = semester_gpa(
            curriculum["courses"],
            profile_for_gpa,
            last_semester,
            rules_config["regulation"],
        )
        if student_id == "V2-003":
            previous_gpa = semester_gpa(
                curriculum["courses"], profile_for_gpa, 1, rules_config["regulation"]
            )
        if student_id == "V2-004":
            previous_gpa = 5.0

        first_term_rows = [
            record
            for course_id, record in per_course.items()
            if course_id in selected_ids
            and int(course_by_id[course_id]["planned_semester"]) == 1
            and record["status"] in {"completed", "failed"}
        ]
        first_term_enrolled = len(first_term_rows)
        first_term_approved = sum(
            record["status"] == "completed"
            and float(record["grade_10"] or 0) >= 5.0
            for record in first_term_rows
        )
        first_term_grade = semester_gpa(
            curriculum["courses"], profile_for_gpa, 1, rules_config["regulation"]
        )
        real_features = dict(real_vectors[persona_index])
        scenario_features = {
            key: _clean(value) for key, value in real_features.items()
        }
        scenario_features.update(
            {
                "Curricular units 1st sem (credited)": 0,
                "Curricular units 1st sem (enrolled)": first_term_enrolled,
                "Curricular units 1st sem (evaluations)": first_term_enrolled,
                "Curricular units 1st sem (approved)": first_term_approved,
                "Curricular units 1st sem (grade)": (
                    round(float(first_term_grade) * 2, 2)
                    if first_term_grade is not None
                    else 0.0
                ),
                "Curricular units 1st sem (without evaluations)": 0,
            }
        )
        student_probability = p_student_pass(scenario_features)
        if student_probability is None:
            raise ValueError(
                f"p_student_pass returned None for {student_id}; "
                "scenario plan generation must stop without fabricated probabilities"
            )

        earned_credits = sum(
            int(course_by_id[course_id]["credits"])
            for course_id, record in per_course.items()
            if course_id in selected_ids and record["status"] == "completed"
        )
        credits_remaining = int(program["total_credits"]) - earned_credits
        outcomes = {
            "gdtc": bool(student_id == "V2-008"),
            "qpan": bool(student_id == "V2-008"),
            "foreign_language": bool(student_id == "V2-008"),
            "informatics": bool(student_id == "V2-008"),
        }
        profile = {
            "student_id": student_id,
            "persona": definition["persona"],
            "persona_purpose": definition["persona_purpose"],
            "specialization": specialization,
            "specialization_source_label": optimizer_config["scenario"][
                "specialization_label"
            ],
            "last_completed_semester": last_semester,
            "target_semester": int(definition["target_semester"]),
            "ml_scope": definition["ml_scope"],
            "ml_scope_reason": (
                "T1 sau HK1, trước đăng ký HK2."
                if definition["ml_scope"] == "T1_valid"
                else "Extension assumption: dùng đặc trưng HK1 đã dựng từ bảng điểm hiện tại."
            ),
            "previous_semester_gpa": previous_gpa,
            "gpa": gpa_value,
            "credits_earned": earned_credits,
            "credits_remaining": credits_remaining,
            "p_student_pass": student_probability,
            "graduation_outcomes": json.dumps(outcomes, ensure_ascii=False),
            "feature_source_label": LABEL_REAL,
            "feature_derivation_label": "GIẢ ĐỊNH (tín chỉ HK1 lấy từ bảng điểm; điểm nhân 2 lên thang 0-20)",
            "course_feature_note": "Course giữ nguyên vector REAL (UCI-697); không có nghĩa là mã/ngành học NTU.",
            "source_label": LABEL_SCENARIO,
            "program_total_credits": int(program["total_credits"]),
            "elective_choices": json.dumps(elective_choices, ensure_ascii=False),
            **scenario_features,
        }
        profiles.append(profile)
        for course in curriculum["courses"]:
            course_id = str(course["course_id"])
            record = per_course[course_id]
            row = {
                "student_id": student_id,
                "course_id": course_id,
                **record,
                "counts_toward_total": bool(course["counts_toward_total"]),
                "selected_in_slot": bool(record["selected_in_slot"]),
                "source_label": LABEL_SCENARIO,
                "curriculum_source_label": course["source_label"],
            }
            if row["grade_10"] is None:
                row["grade_10"] = ""
            progress_rows.append(row)
        scenario_records[student_id] = {
            "profile": profile,
            "progress": per_course,
            "program_course_ids": sorted(selected_ids),
            "program_mandatory_ids": sorted(program_ids),
            "elective_choices": elective_choices,
            "current_debt_credits": sum(
                int(course_by_id[course_id]["credits"])
                for course_id, record in per_course.items()
                if course_id in selected_ids and record["status"] == "failed"
            ),
        }

    metadata = {
        "curriculum": curriculum,
        "rules_config": rules_config,
        "optimizer_config": optimizer_config,
        "profile_feature_columns": profile_features,
        "scenario_records": scenario_records,
        "program_courses": program_courses,
        "elective_choices": elective_choices,
        "slot_credits": slot_credits,
        "selected_course_ids": sorted(selected_ids),
        "specialization": specialization,
        "seed": seed,
    }
    return profiles, progress_rows, metadata


def validate_scenario_v2(
    profiles: list[dict[str, Any]],
    progress_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    curriculum = metadata["curriculum"]
    program = curriculum["program_config"]["program"]
    records = metadata["scenario_records"]
    all_course_ids = {str(row["course_id"]) for row in curriculum["courses"]}
    program_ids = set(metadata["selected_course_ids"])
    errors: list[dict[str, Any]] = []
    students = []
    progress_by_student: dict[str, list[dict[str, Any]]] = {}
    for row in progress_rows:
        progress_by_student.setdefault(str(row["student_id"]), []).append(row)
    for profile in profiles:
        student_id = str(profile["student_id"])
        student_rows = progress_by_student.get(student_id, [])
        row_ids = [str(row["course_id"]) for row in student_rows]
        student_errors = []
        if len(row_ids) != len(all_course_ids) or set(row_ids) != all_course_ids:
            student_errors.append("INCOMPLETE_OR_UNKNOWN_COURSE_PROGRESS")
        if len(row_ids) != len(set(row_ids)):
            student_errors.append("DUPLICATE_PROGRESS_COURSE_ID")
        chosen_slots: Counter[str] = Counter()
        for row in student_rows:
            if row["selected_in_slot"]:
                course = next(
                    item
                    for item in curriculum["courses"]
                    if str(item["course_id"]) == str(row["course_id"])
                )
                if course.get("elective_slot"):
                    chosen_slots[str(course["elective_slot"])] += 1
        required_slots = set(program["required_elective_slots"][str(profile["specialization"])])
        required_slots.add(str(curriculum["enrichment_config"]["graduation_slot"]["slot"]))
        if any(chosen_slots.get(slot) != 1 for slot in required_slots):
            student_errors.append("ELECTIVE_SLOT_CHOICE_COUNT_NOT_ONE")
        earned = sum(
            int(next(course for course in curriculum["courses"] if str(course["course_id"]) == row_id)["credits"])
            for row_id in program_ids
            if next(
                (row for row in student_rows if str(row["course_id"]) == row_id),
                {},
            ).get("status")
            == "completed"
        )
        remaining = int(program["total_credits"]) - earned
        if earned + remaining != int(program["total_credits"]):
            student_errors.append("EARNED_PLUS_REMAINING_NOT_130")
        if profile["credits_earned"] != earned or profile["credits_remaining"] != remaining:
            student_errors.append("PROFILE_CREDIT_TOTAL_MISMATCH")
        record = records[student_id]
        expected_earned = record["profile"]["credits_earned"]
        if expected_earned != earned:
            student_errors.append("SCENARIO_PROGRESS_CREDIT_RECOMPUTE_MISMATCH")
        if student_errors:
            errors.extend(
                {"student_id": student_id, "code": code}
                for code in student_errors
            )
        students.append(
            {
                "student_id": student_id,
                "persona": profile["persona"],
                "credits_earned": earned,
                "credits_remaining": remaining,
                "credits_total": earned + remaining,
                "TBHK_previous_semester": profile["previous_semester_gpa"],
                "TBTCL": profile["gpa"],
                "ml_scope": profile["ml_scope"],
                "p_student_pass": profile["p_student_pass"],
                "current_debt_credits": record["current_debt_credits"],
                "selected_slots": dict(chosen_slots),
                "errors": student_errors,
            }
        )
    return {
        "status": "PASS" if not errors else "FAIL",
        "seed": metadata["seed"],
        "source_label": LABEL_SCENARIO,
        "feature_source_label": LABEL_REAL,
        "specialization_default": metadata["specialization"],
        "n_profiles": len(profiles),
        "n_progress_rows": len(progress_rows),
        "expected_course_rows_per_profile": len(all_course_ids),
        "program_total_credits": int(program["total_credits"]),
        "n_errors": len(errors),
        "errors": errors,
        "students": students,
        "credit_limit_regimes": {
            row["student_id"]: (
                "WEAK_OR_POOR"
                if isinstance(row["TBHK_previous_semester"], (float, int))
                and row["TBHK_previous_semester"] < 5
                else "NORMAL"
                if isinstance(row["TBHK_previous_semester"], (float, int))
                else "UNKNOWN"
            )
            for row in students
        },
        "unknowns": [
            "Corequisite semantics remain UNCONFIRMED per regulation configuration.",
            "Offering parity and extension_assumption ML scope are GIẢ ĐỊNH.",
            "No course-difficulty probability factor is modeled.",
        ],
    }


def _get_profile_progress(
    record: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        course_id: {
            "status": value["status"],
            "grade_10": value["grade_10"],
            "attempt_count": value["attempt_count"],
            "semester_taken": value["semester_taken"],
        }
        for course_id, value in record["progress"].items()
    }


def _make_plan_rows(
    profiles: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    curriculum = metadata["curriculum"]
    rules_config = metadata["rules_config"]
    courses = curriculum["courses"]
    prerequisites = curriculum["prerequisites"]
    program_courses = metadata["program_courses"]
    mean_credits = sum(int(row["credits"]) for row in program_courses) / len(program_courses)
    selected_program_ids = set(metadata["selected_course_ids"])
    slot_credits = metadata["slot_credits"]
    generated: list[dict[str, Any]] = []
    for profile in profiles:
        student_id = str(profile["student_id"])
        record = metadata["scenario_records"][student_id]
        progress = _get_profile_progress(record)
        profile_for_rules = {
            **profile,
            "progress": progress,
            "graduation_outcomes": json.loads(profile["graduation_outcomes"]),
        }
        evaluated = evaluate_student(
            profile_for_rules,
            curriculum,
            rules_config,
            int(profile["target_semester"]),
        )
        eligible = _with_retake_factors([
            row for row in evaluated["eligible_courses"]
            if str(row["course_id"]) in selected_program_ids
        ])
        status_by_course = {
            course_id: row["status"] for course_id, row in progress.items()
        }
        course_by_id = {str(row["course_id"]): row for row in courses}
        active_slots = {
            str(course_by_id[course_id].get("elective_slot"))
            for course_id, status in status_by_course.items()
            if course_id in course_by_id
            and course_by_id[course_id].get("elective_slot")
            and status in {"completed", "in_progress"}
        }
        required_slots = set(
            curriculum["program_config"]["program"]["required_elective_slots"][
                str(profile["specialization"])
            ]
        )
        required_slots.add(str(curriculum["enrichment_config"]["graduation_slot"]["slot"]))
        missing_slots = required_slots - active_slots
        unlock = compute_unlock_values(
            [str(row["course_id"]) for row in eligible],
            prerequisites,
            status_by_course,
            credits_by_course={
                course_id: int(course_by_id[course_id]["credits"])
                for course_id in course_by_id
            },
            elective_slots_by_course={
                course_id: course_by_id[course_id].get("elective_slot")
                for course_id in course_by_id
            },
            missing_slots=missing_slots,
            slot_credits=slot_credits,
        )
        limits = evaluated["progress_stats"]["registration_credit_limits"]
        current_debt = int(record["current_debt_credits"])
        plan_list = three_plans(
            eligible,
            p_student=float(profile["p_student_pass"]),
            mean_credits=mean_credits,
            credit_limits=limits,
            prerequisites=prerequisites,
            progress=progress,
            unlock_values=unlock,
            beta=DEFAULT_BETA,
            gamma=DEFAULT_GAMMA,
            load_lambda=DEFAULT_LAMBDA,
            current_debt_credits=current_debt,
            graduation_ready=bool(evaluated["progress_stats"]["graduation_ready"]),
        )
        for plan in plan_list:
            target_semester = int(profile["target_semester"])
            expected_rem = max(
                0.0,
                float(evaluated["progress_stats"]["credits_remaining"])
                - float(plan.get("expected_credits_passed", 0.0)),
            )
            chain = evaluated["progress_stats"][
                "minimum_semesters_prerequisite_chain"
            ]
            chain_semesters = int(chain) if isinstance(chain, (int, float)) else 0
            future = estimated_graduation_semester(
                target_semester, round(expected_rem), chain_semesters
            )
            selected = plan.get("selected_courses", [])
            warnings = list(plan.get("warnings", []))
            if (
                float(plan.get("p_warning_W1", 0.0)) >= 0.5
                or float(plan.get("p_warning_W2", 0.0)) >= 0.5
                or float(plan.get("p_at_least_one_failure", 0.0)) >= 0.5
            ):
                warnings.append(
                    "Xác suất cảnh báo/trượt ước tính cao; cần cân nhắc tải học tập "
                    "và trao đổi với cố vấn học tập."
                )
            if plan.get("status") == "best_effort" or plan.get("risk_cap_exceeded") or plan.get("regulatory_conflict"):
                if "cố vấn" not in " ".join(warnings).casefold():
                    warnings.append(
                        "Phương án có rủi ro, không được gọi là an toàn; hãy gặp cố vấn học tập."
                    )
            warnings = list(dict.fromkeys(warnings))
            generated.append(
                {
                    "student_id": student_id,
                    "persona": profile["persona"],
                    "specialization": profile["specialization"],
                    "target_semester": target_semester,
                    "ml_scope": profile["ml_scope"],
                    "plan_type": plan["plan_type"],
                    "plan_label": plan["plan_label"],
                    "status": plan["status"],
                    "selected_course_ids": json.dumps(plan.get("selected_course_ids", []), ensure_ascii=False),
                    "selected_course_names": json.dumps(
                        [
                            {
                                "course_id": course["course_id"],
                                "course_name": course["course_name"],
                            }
                            for course in selected
                        ],
                        ensure_ascii=False,
                    ),
                    "selected_credits": plan.get("selected_credits", 0),
                    "pass_probabilities": json.dumps(
                        plan.get("pass_probabilities", {}), sort_keys=True
                    ),
                    "expected_credits_passed": plan.get("expected_credits_passed", 0.0),
                    "expected_failed_courses": plan.get("expected_failed_courses", 0.0),
                    "p_at_least_one_failure": plan.get("p_at_least_one_failure", 0.0),
                    "p_warning_W1": plan.get("p_warning_W1", 0.0),
                    "p_warning_W2": plan.get("p_warning_W2", 0.0),
                    "retake_credits_total": plan.get("retake_credits_total", 0),
                    "honors_downgrade_risk": plan.get("honors_downgrade_risk", False),
                    "unlock_values": json.dumps(
                        {
                            course_id: unlock[course_id]
                            for course_id in plan.get("selected_course_ids", [])
                        },
                        sort_keys=True,
                    ),
                    "objective_value": plan.get("objective_value", 0.0),
                    "scenario_budget": plan.get("scenario_budget", ""),
                    "Fmax": (
                        "∞"
                        if "fmax" in plan and plan["fmax"] is None
                        else plan.get("fmax", "")
                    ),
                    "risk_cap_exceeded": plan.get("risk_cap_exceeded", False),
                    "risk_cap_mode": plan.get("risk_cap_mode", "off"),
                    "regulatory_conflict": plan.get("regulatory_conflict", False),
                    "warnings": json.dumps(warnings, ensure_ascii=False),
                    "explanation": plan["explanation"],
                    "difference_explanation": plan["difference_explanation"],
                    "estimated_graduation_semester": future["semester"],
                    "graduation_estimate_assumption": future["assumption"],
                    "source_label": LABEL_SCENARIO,
                }
            )
    return generated


def _rule_examples(
    profiles: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    curriculum = metadata["curriculum"]
    rules_config = metadata["rules_config"]
    selected_ids = set(metadata["selected_course_ids"])
    program_courses = metadata["program_courses"]
    course_by_id = {str(row["course_id"]): row for row in curriculum["courses"]}
    mean_credits = sum(int(row["credits"]) for row in program_courses) / len(program_courses)
    examples: dict[str, Any] = {}
    evaluated_by_id: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        student_id = str(profile["student_id"])
        record = metadata["scenario_records"][student_id]
        progress = _get_profile_progress(record)
        evaluated = evaluate_student(
            {
                **profile,
                "progress": progress,
                "graduation_outcomes": json.loads(profile["graduation_outcomes"]),
            },
            curriculum,
            rules_config,
            int(profile["target_semester"]),
        )
        evaluated_by_id[student_id] = evaluated
    examples["registration_limits"] = {
        student_id: evaluated_by_id[student_id]["progress_stats"][
            "registration_credit_limits"
        ]
        for student_id in ("V2-003", "V2-004")
    }
    examples["w1_boundary_scenario"] = {
        "current_debt_credits": metadata["scenario_records"]["V2-005"][
            "current_debt_credits"
        ],
        "active": next(
            flag["active"]
            for flag in evaluated_by_id["V2-005"]["academic_flags"]
            if flag["code"] == "W1"
        ),
        "threshold": 24,
        "comparison": ">",
    }

    hp024_result = evaluated_by_id["V2-006"]
    examples["hp024_blocked_chain"] = {
        "failed_course": "HP024",
        "blocked_course_ids": sorted(
            row["course_key"]
            for row in hp024_result["blocked_courses"]
            if row["course_key"] in {"HP029", "HP039-NW", "HP040-NW", "HP041-NW", "HP042-NW", "HP044-NW"}
        ),
        "reasons": {
            row["course_key"]: row["reasons"]
            for row in hp024_result["blocked_courses"]
            if row["course_key"] in {"HP029", "HP039-NW", "HP040-NW", "HP041-NW", "HP042-NW", "HP044-NW"}
        },
    }
    failed_slot_result = evaluated_by_id["V2-009"]
    failed_slot_course = next(
        course_id
        for course_id, status in metadata["scenario_records"]["V2-009"]["progress"].items()
        if status["status"] == "failed"
        and course_id in selected_ids
        and course_by_id[course_id].get("elective_slot")
    )
    reopened_slot = str(course_by_id[failed_slot_course]["elective_slot"])
    examples["failed_elective_slot_reopened"] = {
        "failed_course_id": failed_slot_course,
        "slot": reopened_slot,
        "eligible_alternatives": sorted(
            str(course["course_id"])
            for course in failed_slot_result["eligible_courses"]
            if course.get("elective_slot") == reopened_slot
        ),
    }

    final_profile = next(profile for profile in profiles if profile["student_id"] == "V2-007")
    final_record = metadata["scenario_records"]["V2-007"]
    final_progress = _get_profile_progress(final_record)
    final_evaluated = evaluated_by_id["V2-007"]
    eligible = _with_retake_factors([
        row for row in final_evaluated["eligible_courses"]
        if str(row["course_id"]) in selected_ids
    ])
    previous_gpa = final_profile["previous_semester_gpa"]
    regulated_bounds = credit_limits(
        {"previous_semester_gpa": previous_gpa},
        {
            "previous_semester_gpa": previous_gpa,
            "registration_completes_program": False,
            "is_first_semester": False,
        },
        rules_config["regulation"],
    )
    outstanding = [
        course_id
        for course_id in sorted(selected_ids)
        if final_progress.get(course_id, {}).get("status") != "completed"
    ]
    examples["final_semester_cases"] = plan_final_semester_cases(
        eligible,
        outstanding_course_ids=outstanding,
        p_student=float(final_profile["p_student_pass"]),
        mean_credits=mean_credits,
        credit_limits=regulated_bounds,
        prerequisites=curriculum["prerequisites"],
        progress=final_progress,
        current_debt_credits=final_record["current_debt_credits"],
    )
    examples["final_semester_cases"]["outstanding_course_ids"] = outstanding

    weak_profile = next(profile for profile in profiles if profile["student_id"] == "V2-003")
    weak_record = metadata["scenario_records"]["V2-003"]
    weak_progress = _get_profile_progress(weak_record)
    weak_eval = evaluated_by_id["V2-003"]
    weak_eligible = _with_retake_factors([
        row for row in weak_eval["eligible_courses"]
        if str(row["course_id"]) in selected_ids
    ])
    examples["credit_regime_comparison_same_profile"] = compare_credit_regimes(
        eligible_courses=weak_eligible,
        p_student=float(weak_profile["p_student_pass"]),
        mean_credits=mean_credits,
        prerequisites=curriculum["prerequisites"],
        progress=weak_progress,
        unlock_values={},
        current_debt_credits=weak_record["current_debt_credits"],
    )
    examples["forced_retakes_near_graduation"] = final_evaluated["forced_retakes"]
    return examples


def _sensitivity_rows(
    profiles: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    curriculum = metadata["curriculum"]
    config = metadata["rules_config"]
    selected_ids = set(metadata["selected_course_ids"])
    all_courses = curriculum["courses"]
    program_courses = metadata["program_courses"]
    mean_credits = sum(int(row["credits"]) for row in program_courses) / len(program_courses)
    rows: list[dict[str, Any]] = []
    sensitivity_profiles = ["V2-002", "V2-003", "V2-006"]
    for profile in profiles:
        if str(profile["student_id"]) not in sensitivity_profiles:
            continue
        record = metadata["scenario_records"][str(profile["student_id"])]
        progress = _get_profile_progress(record)
        evaluated = evaluate_student(
            {
                **profile,
                "progress": progress,
                "graduation_outcomes": json.loads(profile["graduation_outcomes"]),
            },
            curriculum,
            config,
            int(profile["target_semester"]),
        )
        eligible = _with_retake_factors([
            course for course in evaluated["eligible_courses"]
            if str(course["course_id"]) in selected_ids
        ])
        limits = evaluated["progress_stats"]["registration_credit_limits"]
        default_budget = (
            LOAD_BUDGETS.get(str(limits["regime"]), (int(limits.get("cmax") or 18),))[1]
        )
        for beta in (0.0, 0.125, 0.5):
            for gamma in (0.5, 1.0, 2.0):
                for load_lambda in (0.0, 0.1, 0.3):
                    result = optimize_plan(
                        eligible,
                        p_student=float(profile["p_student_pass"]),
                        mean_credits=mean_credits,
                        credit_limits=limits,
                        prerequisites=curriculum["prerequisites"],
                        progress=progress,
                        scenario_budget=default_budget,
                        beta=beta,
                        gamma=gamma,
                        load_lambda=load_lambda,
                        current_debt_credits=int(record["current_debt_credits"]),
                    )
                    rows.append(
                        {
                            "student_id": profile["student_id"],
                            "persona": profile["persona"],
                            "beta": beta,
                            "gamma": gamma,
                            "lambda": load_lambda,
                            "p_star": gamma / (1.0 + gamma),
                            "scenario_budget": default_budget,
                            "selected_load": result.get("selected_load", 0),
                            "selected_course_ids": json.dumps(
                                result.get("selected_course_ids", []), ensure_ascii=False
                            ),
                            "selected_credits": result.get("selected_credits", 0),
                            "expected_credits_passed": result.get("expected_credits_passed", 0.0),
                            "expected_failed_courses": result.get("expected_failed_courses", 0.0),
                            "status": result["status"],
                            "source_label": LABEL_SCENARIO,
                        }
                    )
    return rows


def _unlock_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    curriculum = metadata["curriculum"]
    program_courses = metadata["program_courses"]
    ids = [str(course["course_id"]) for course in program_courses]
    course_by_id = {str(course["course_id"]): course for course in program_courses}
    statuses = {course_id: "not_taken" for course_id in ids}
    credits = {course_id: int(course["credits"]) for course_id, course in course_by_id.items()}
    values = compute_unlock_values(
        ids,
        curriculum["prerequisites"],
        statuses,
        credits_by_course=credits,
    )
    nonzero = {course_id: value for course_id, value in values.items() if value > 0}
    return {
        "source_label": "OFFICIAL (NTU)",
        "specialization": metadata["specialization"],
        "strict_prerequisite_edge_count": sum(
            row["type"] == "tiên quyết" for row in curriculum["prerequisites"]
        ),
        "delta": 0.5,
        "prerequisite_only_u_distribution": dict(sorted(Counter(values.values()).items())),
        "nonzero_prerequisite_unlocks": dict(sorted(nonzero.items())),
        "interpretation": (
            "Giá trị u_i từ tiên quyết bắc cầu tập trung ở một số nút; "
            "không suy diễn rằng mọi học phần đều mở khóa chuỗi."
        ),
        "slot_completion_value_added_at_plan_time": True,
    }


def _write_optimization_spec(unlock: dict[str, Any]) -> None:
    nonzero = unlock["nonzero_prerequisite_unlocks"]
    lines = [
        "# Optimization specification — scenario v2",
        "",
        "Nguồn chương trình: OFFICIAL (NTU). Kịch bản đầu vào: SCENARIO; đặc trưng tuyển sinh/nhân khẩu học: REAL (UCI-697).",
        "",
        "## Objective",
        "",
        "`maximize Σ[c_i p_i - γ c_i(1-p_i) + β u_i] x_i`, where `p_i = clip(p_student × exp(-λ max(0, units(L)-6)) × r_retake(i), 0, 1)`.",
        "Here `units(L)=floor(L/mean_credits+0.5)` and `L` is actual selected credits; every feasible integer L is solved separately so the model stays linear.",
        "`c[(1+γ)p-γ]` has break-even `p*=γ/(1+γ)`; with γ=1, p*=0.5. For p<p*, expected-credit utility is negative unless βu compensates.",
        "Defaults β=0.125, γ=1, λ=0.1, 6-unit threshold, δ=0.5, and retake multipliers {0.9, 1.0, 1.1} are GIẢ ĐỊNH; mapping is first retake=0.9, repeated attempt=1.1, non-retake=1.0.",
        "",
        "## Unlock value",
        "",
        "`u_i` is the sum of not-completed strict-prerequisite descendant credits discounted by `δ^distance`, plus remaining elective/graduation slot credits where relevant.",
        f"Official strict prerequisite edges: {unlock['strict_prerequisite_edge_count']}. Nonzero prerequisite-only u_i: `{json.dumps(nonzero, ensure_ascii=False, sort_keys=True)}`.",
        "Most courses have no strict-prerequisite descendants; unlock value is concentrated, not a general difficulty or course-value score.",
        "",
        "## Constraints and outputs",
        "",
        "- Binary selection is restricted to eligible courses, official regulatory credit limits, course offering, prerequisites, corequisites, and at most one course per elective slot.",
        "- Mandatory failed-course retakes are hard constraints unless their total credits exceed cmax; such a conflict yields `best_effort`, a regulatory-conflict flag, and an advisor warning.",
        "- `risk_cap_mode` supports off/soft/hard; the main three-plan output uses off and computes `risk_cap_exceeded` afterward. The Fmax grid is scanned post-hoc. P(Dropout) and Fmax are advisory and do not limit registration rights.",
        "- W1/W2 warning probabilities use exact dynamic programming over credits. Courses are independent pass/fail events (limitation); no course-difficulty multiplier is used.",
        "- best_effort and risk-cap/regulatory conflicts always carry explicit risk language and an academic-advisor recommendation; they never use the `An toàn` label.",
        "- Final-semester cases A (regulation-limited) and B (completion plan) are evaluated separately; B is only valid if all missing courses are eligible and offered.",
        "",
        "## Limitations and unresolved assumptions",
        "",
        "- Corequisite meaning and prerequisite completeness remain UNCONFIRMED.",
        "- Offering parity is inferred from `offered_semesters`; summer offerings and class availability are not modeled.",
        "- Extension-assumption probabilities apply the HK1 stratum estimate beyond T1 and are not validated as a later-term prediction.",
        "- The 130-credit program credit count and official course/pre-requisite rows are not generated or inferred by this optimizer.",
        "",
    ]
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_scenario_v2_generation(
    *,
    seed: int = SEED,
    generate_plans: bool = True,
) -> dict[str, Any]:
    profiles, progress_rows, metadata = generate_scenario_rows(seed=seed)
    validation = validate_scenario_v2(profiles, progress_rows, metadata)
    if validation["n_errors"]:
        VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        VALIDATION_PATH.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise ValueError(f"Scenario-v2 validation failed: {validation['errors']}")

    profile_feature_columns = metadata["profile_feature_columns"]
    profile_columns = [
        "student_id",
        "persona",
        "persona_purpose",
        "specialization",
        "specialization_source_label",
        "last_completed_semester",
        "target_semester",
        "ml_scope",
        "ml_scope_reason",
        "previous_semester_gpa",
        "gpa",
        "credits_earned",
        "credits_remaining",
        "p_student_pass",
        "graduation_outcomes",
        "feature_source_label",
        "feature_derivation_label",
        "course_feature_note",
        "source_label",
        "program_total_credits",
        "elective_choices",
        *profile_feature_columns,
    ]
    _write_csv(PROFILE_PATH, profiles, profile_columns)
    progress_columns = [
        "student_id",
        "course_id",
        "status",
        "grade_10",
        "attempt_count",
        "semester_taken",
        "selected_in_slot",
        "counts_toward_total",
        "source_label",
        "curriculum_source_label",
    ]
    _write_csv(PROGRESS_PATH, progress_rows, progress_columns)

    plan_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    if generate_plans:
        plan_rows = _make_plan_rows(profiles, metadata)
        sensitivity_rows = _sensitivity_rows(profiles, metadata)
        plan_columns = list(plan_rows[0]) if plan_rows else []
        _write_csv(PLANS_PATH, plan_rows, plan_columns)
        _write_csv(SENSITIVITY_PATH, sensitivity_rows, list(sensitivity_rows[0]) if sensitivity_rows else [])

    unlock = _unlock_summary(metadata)
    UNLOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNLOCK_PATH.write_text(
        json.dumps(unlock, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_optimization_spec(unlock)
    validation["output_files"] = {
        "profiles": str(PROFILE_PATH.relative_to(ROOT)),
        "progress": str(PROGRESS_PATH.relative_to(ROOT)),
        "plans": str(PLANS_PATH.relative_to(ROOT)) if generate_plans else None,
        "sensitivity": str(SENSITIVITY_PATH.relative_to(ROOT)) if generate_plans else None,
        "unlock_summary": str(UNLOCK_PATH.relative_to(ROOT)),
        "optimization_spec": str(SPEC_PATH.relative_to(ROOT)),
    }
    validation["plans_count"] = len(plan_rows)
    validation["plans_by_student"] = dict(
        Counter(row["student_id"] for row in plan_rows)
    )
    validation["sensitivity_rows"] = len(sensitivity_rows)
    validation["course_rows"] = len(metadata["curriculum"]["courses"])
    validation["scenario_program_courses"] = len(metadata["program_courses"])
    validation["program_credit_total_verified"] = sum(
        int(row["credits"]) for row in metadata["program_courses"]
    )
    validation["unlock_summary"] = unlock
    validation["rule_examples"] = _rule_examples(profiles, metadata)
    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    current_metrics = read_metrics()
    current_metrics["scenario_v2"] = {
        "status": validation["status"],
        "seed": seed,
        "profiles": len(profiles),
        "progress_rows": len(progress_rows),
        "validation_errors": validation["n_errors"],
        "plans": len(plan_rows),
        "sensitivity_rows": len(sensitivity_rows),
        "program_total_credits": validation["program_credit_total_verified"],
    }
    write_metrics(current_metrics)
    return validation


def compare_credit_regimes(
    *,
    eligible_courses: list[dict[str, Any]],
    p_student: float,
    mean_credits: float,
    prerequisites: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    unlock_values: dict[str, float],
    current_debt_credits: int = 0,
) -> dict[str, Any]:
    """Compare official normal/weak bounds on an identical course set."""
    outputs = {}
    for regime, minimum, maximum in (
        ("WEAK_OR_POOR", 12, 18),
        ("NORMAL", 15, 27),
    ):
        plan = optimize_plan(
            eligible_courses,
            p_student=p_student,
            mean_credits=mean_credits,
            credit_limits={"cmin": minimum, "cmax": maximum, "regime": regime},
            prerequisites=prerequisites,
            progress=progress,
            unlock_values=unlock_values,
            current_debt_credits=current_debt_credits,
        )
        outputs[regime] = {
            "cmin": minimum,
            "cmax": maximum,
            "selected_credits": plan.get("selected_credits"),
            "selected_course_ids": plan.get("selected_course_ids"),
            "expected_failed_courses": plan.get("expected_failed_courses"),
            "status": plan.get("status"),
        }
    return outputs
