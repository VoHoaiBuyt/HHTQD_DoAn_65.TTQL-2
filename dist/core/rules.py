"""Eligibility rules independent from any user-interface framework."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from core.gpa import (
    classify_academic_performance,
    classify_study_year,
    cumulative_gpa,
    round_course_grade,
    semester_gpa,
)
from core.regulation import load_regulation_config


COMPLETED = "completed"
IN_PROGRESS = "in_progress"
FAILED = "failed"
NOT_TAKEN = "not_taken"


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def credit_limits(
    profile: Mapping[str, Any],
    semester_context: Mapping[str, Any],
    regulation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return official enrollment bounds from the previous main-term average."""
    config = regulation or load_regulation_config()
    notes = [
        "Ràng buộc tín chỉ quy chế khác với trần rủi ro mềm; "
        "P(Dropout) chỉ là cảnh báo/khuyến nghị.",
    ]
    if bool(semester_context.get("is_summer_term", False)):
        notes.append(
            "Học kỳ phụ không áp giới hạn tối thiểu/tối đa; điều kiện mở lớp "
            "chưa mô hình hóa nên kết quả thận trọng hơn thực tế."
        )
        return {
            "cmin": None,
            "cmax": None,
            "regime": "UNRESTRICTED_SUMMER",
            "notes": notes,
        }
    if bool(semester_context.get("registration_completes_program", False)):
        notes.append(
            "GIẢ ĐỊNH (nhận diện kỳ cuối khóa từ kế hoạch): kế hoạch đăng ký "
            "hoàn tất toàn bộ tín chỉ còn thiếu; thực tế nên đăng ký ít nhất "
            "bằng số tín chỉ còn thiếu."
        )
        return {
            "cmin": 0,
            "cmax": None,
            "regime": "UNRESTRICTED_FINAL",
            "notes": notes,
        }
    first_semester = bool(
        semester_context.get("is_first_semester", profile.get("is_first_semester", False))
    )
    if first_semester:
        notes.append(
            "Học kỳ đầu không thuộc giới hạn đăng ký này; kế hoạch do Nhà trường ấn định (Đ9.1b)."
        )
        return {
            "cmin": None,
            "cmax": None,
            "regime": "FIRST_SEMESTER_PLAN",
            "notes": notes,
        }
    previous_average = _number(
        semester_context.get(
            "previous_semester_gpa",
            profile.get("previous_semester_gpa"),
        )
    )
    if previous_average is None:
        notes.append(
            "Không có TBHK của học kỳ chính liền trước; giới hạn tín chỉ "
            "không thể xác định."
        )
        return {
            "cmin": "UNKNOWN",
            "cmax": "UNKNOWN",
            "regime": "UNKNOWN",
            "previous_semester_gpa": None,
            "notes": notes,
        }
    threshold = float(
        config["credit_limits"]["previous_semester_average_threshold"]["value"]
    )
    if previous_average >= threshold:
        regime = "NORMAL"
        bounds = config["credit_limits"]["normal"]
    else:
        regime = "WEAK_OR_POOR"
        bounds = config["credit_limits"]["weak_or_poor"]
    notes.append(
        f"Chế độ {regime} theo TBHK học kỳ chính liền trước "
        f"{previous_average:.2f} (ngưỡng {threshold:.2f})."
    )
    return {
        "cmin": int(bounds["minimum"]["value"]),
        "cmax": int(bounds["maximum"]["value"]),
        "regime": regime,
        "previous_semester_gpa": previous_average,
        "notes": notes,
    }


def _academic_flags(
    profile: Mapping[str, Any],
    courses: Sequence[Mapping[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
    regulation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rules = regulation["academic_warnings"]
    course_by_id = {str(row["course_id"]): row for row in courses}
    semester = int(
        profile.get(
            "last_completed_semester",
            profile.get("current_semester", 0),
        )
        or 0
    )
    summer_term = bool(profile.get("is_summer_term", False))
    grades_available = (
        profile.get("grade_data_available") is not False
        and profile.get("simulation_mode") != "pass_fail"
    )
    debt_credits = sum(
        int(course_by_id[course_id]["credits"])
        for course_id, status_row in statuses.items()
        if course_id in course_by_id
        and status_row.get("status") == FAILED
    )
    w1_threshold = rules["W1"]["threshold"]
    flags: list[dict[str, Any]] = [
        {
            "code": "W1",
            "active": not summer_term
            and debt_credits > int(w1_threshold["value"]),
            "value": debt_credits,
            "unit": "credits",
            "threshold": w1_threshold["value"],
            "comparison": ">",
            "status": rules["W1"]["debt_definition"]["rule_status"],
            "ref": w1_threshold["ref"],
            "calculation_status": (
                "not_applicable_summer" if summer_term else "computed"
            ),
            "definition_status": rules["W1"]["debt_definition"]["rule_status"],
        }
    ]
    registered_credits = 0
    failed_credits = 0
    for course_id, status_row in statuses.items():
        course = course_by_id.get(course_id)
        if course is None:
            continue
        grade = _number(status_row.get("grade_10"))
        taken_semester = _number(status_row.get("semester_taken"))
        if taken_semester != semester:
            continue
        status = str(status_row.get("status", NOT_TAKEN))
        credits = int(course["credits"])
        if status in {COMPLETED, FAILED, IN_PROGRESS}:
            registered_credits += credits
            if status == FAILED or (
                grade is not None
                and round_course_grade(grade, regulation) < 5.0
            ):
                failed_credits += credits
    failed_ratio = (
        failed_credits / registered_credits if registered_credits else None
    )
    w2_threshold = float(rules["W2"]["threshold"]["value"])
    flags.append(
        {
            "code": "W2",
            "active": (
                not summer_term
                and failed_ratio is not None
                and failed_ratio > w2_threshold
            ),
            "value": failed_ratio,
            "failed_credits": failed_credits,
            "registered_credits": registered_credits,
            "threshold": w2_threshold,
            "comparison": ">",
            "status": rules["W2"]["threshold"]["rule_status"],
            "ref": rules["W2"]["threshold"]["ref"],
            "calculation_status": (
                "not_applicable_summer"
                if summer_term
                else "computed"
                if failed_ratio is not None
                else "cannot_compute"
            ),
        }
    )
    gpa_semester = (
        semester_gpa(courses, statuses, semester, regulation)
        if grades_available and not summer_term
        else None
    )
    first_term = bool(
        profile.get("is_first_semester_of_program", semester == 1)
    )
    w3_rule = (
        rules["W3"]["first_semester_threshold"]
        if first_term
        else rules["W3"]["later_semester_threshold"]
    )
    threshold = float(w3_rule["value"])
    flags.append(
        {
            "code": "W3",
            "active": (
                gpa_semester is not None
                and gpa_semester < threshold
                and not summer_term
            ),
            "value": gpa_semester,
            "unit": "GPA10",
            "threshold": threshold,
            "comparison": "<",
            "status": w3_rule["rule_status"],
            "ref": w3_rule["ref"],
            "calculation_status": (
                "not_applicable_summer"
                if summer_term
                else "pass_fail_only"
                if not grades_available
                else "computed"
                if gpa_semester is not None
                else "cannot_compute"
            ),
            "classification": classify_academic_performance(
                gpa_semester, regulation
            ),
        }
    )
    earned_credits = sum(
        int(course_by_id[course_id]["credits"])
        for course_id, status_row in statuses.items()
        if course_id in course_by_id
        and status_row.get("status") == COMPLETED
        and bool(course_by_id[course_id].get("counts_toward_total", True))
    )
    study_year = classify_study_year(earned_credits, regulation)
    cumulative_average = (
        cumulative_gpa(courses, statuses, regulation)
        if grades_available
        else None
    )
    w4_threshold = rules["W4"]["cumulative_average_threshold_by_study_year"]
    year_threshold = w4_threshold["value"][study_year["year"]]
    flags.append(
        {
            "code": "W4",
            "active": (
                cumulative_average is not None
                and cumulative_average < float(year_threshold)
                and not summer_term
            ),
            "value": cumulative_average,
            "unit": "GPA10",
            "study_year": study_year["year"],
            "accumulated_credits": earned_credits,
            "study_year_status": study_year["status"],
            "study_year_label": study_year["label"],
            "threshold": year_threshold,
            "comparison": "<",
            "status": (
                "UNCONFIRMED"
                if study_year["status"] == "UNCONFIRMED"
                else w4_threshold["rule_status"]
            ),
            "ref": w4_threshold["ref"],
            "calculation_status": (
                "not_applicable_summer"
                if summer_term
                else "pass_fail_only"
                if not grades_available
                else "computed"
                if cumulative_average is not None
                else "cannot_compute"
            ),
        }
    )
    warning_count = int(profile.get("consecutive_warning_count", 0) or 0)
    duration = int(
        profile.get(
            "duration_main_semesters",
            profile.get("duration_semesters", profile.get("last_completed_semester", 0)),
        )
        or 0
    )
    withdrawal_rule = rules["forced_withdrawal"]
    consecutive_limit = int(
        withdrawal_rule["consecutive_warnings_strictly_greater_than"]["value"]
    )
    duration_limit = int(withdrawal_rule["maximum_main_semesters"]["value"])
    withdrawal_active = warning_count > consecutive_limit or duration > duration_limit
    flags.append(
        {
            "code": "FORCED_WITHDRAWAL",
            "active": withdrawal_active,
            "consecutive_warning_count": warning_count,
            "consecutive_warning_threshold": consecutive_limit,
            "trigger": "consecutive warnings > 2 or main semesters > 16",
            "duration_semesters": duration,
            "maximum_duration_semesters": duration_limit,
            "status": withdrawal_rule["consecutive_warnings_strictly_greater_than"]["rule_status"],
            "ref": withdrawal_rule["consecutive_warnings_strictly_greater_than"]["ref"],
        }
    )
    if profile.get("simulation_mode") == "pass_fail":
        flags.append(
            {
                "code": "MONTE_CARLO_WITHDRAWAL_SCOPE",
                "message": "Buộc thôi học theo quy chế (chỉ W1/W2); W3/W4 chỉ áp dụng khi có điểm.",
                "status": rules["monte_carlo_scope"]["rule_status"],
                "ref": rules["monte_carlo_scope"]["ref"],
            }
        )
    return flags


def _cumulative_gpa(
    completed_courses: Sequence[Mapping[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
    regulation: Mapping[str, Any],
) -> float | None:
    return cumulative_gpa(completed_courses, statuses, regulation)


def _retake_credits_total(
    courses: Sequence[Mapping[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
) -> int:
    course_by_id = {str(course["course_id"]): course for course in courses}
    total = 0
    for course_id, record in statuses.items():
        course = course_by_id.get(course_id)
        if course is None or not bool(course.get("counts_toward_total", True)):
            continue
        attempts = record.get("attempts")
        repeated_attempts = (
            max(0, len(attempts) - 1)
            if isinstance(attempts, Sequence) and not isinstance(attempts, (str, bytes))
            else max(0, int(record.get("attempt_count", 1) or 1) - 1)
        )
        total += int(course["credits"]) * repeated_attempts
    return total


def coreq_constraints(
    prerequisite_rows: Sequence[Mapping[str, Any]],
    course_ids: Iterable[str] | None = None,
) -> list[tuple[str, str]]:
    """Return directed x_course <= x_corequisite constraints for ILP models."""
    allowed = set(course_ids) if course_ids is not None else None
    constraints = {
        (str(row["course_id"]), str(row["prerequisite_id"]))
        for row in prerequisite_rows
        if str(row.get("type")) == "song hành"
        and (
            allowed is None
            or (
                str(row["course_id"]) in allowed
                and str(row["prerequisite_id"]) in allowed
            )
        )
    }
    return sorted(constraints)


def _offered_in(course: Mapping[str, Any], target_semester: int) -> bool:
    offerings = course.get("offering_rule", course.get("offered_semesters", []))
    if isinstance(offerings, str):
        offering_values = {part.strip() for part in offerings.split(",")}
    else:
        offering_values = {str(value).strip() for value in offerings}
    semester_key = "odd" if target_semester % 2 else "even"
    return "both" in offering_values or semester_key in offering_values


def _prerequisite_relations(
    prerequisite_rows: Sequence[Mapping[str, Any]],
    course_id: str,
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in prerequisite_rows
        if str(row["course_id"]) == course_id
    ]


def _unmet_strict_roots(
    prerequisite_rows: Sequence[Mapping[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
    course_id: str,
    strict_type: str,
    visiting: set[str] | None = None,
) -> list[str]:
    path = set() if visiting is None else set(visiting)
    if course_id in path:
        return []
    path.add(course_id)
    unmet = [
        str(row["prerequisite_id"])
        for row in _prerequisite_relations(prerequisite_rows, course_id)
        if str(row["type"]) == strict_type
        and statuses.get(str(row["prerequisite_id"]), {}).get("status") != COMPLETED
    ]
    if not unmet:
        return []
    roots: set[str] = set()
    for prerequisite_id in unmet:
        ancestors = _unmet_strict_roots(
            prerequisite_rows,
            statuses,
            prerequisite_id,
            strict_type,
            path,
        )
        roots.update(ancestors or [prerequisite_id])
    return sorted(roots)


def _specialization_applies(course: Mapping[str, Any], specialization: str) -> bool:
    course_specialization = str(course.get("specialization", "common"))
    return (
        course_specialization in {"common", specialization}
        or not bool(course.get("counts_toward_total", True))
    )


def _active_slot_choices(
    courses: Sequence[Mapping[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
    specialization: str | None = None,
) -> set[str]:
    selected: set[str] = set()
    for course in courses:
        slot = course.get("elective_slot")
        if slot is None or (
            specialization is not None
            and not _specialization_applies(course, specialization)
        ):
            continue
        status = str(statuses.get(str(course["course_id"]), {}).get("status", NOT_TAKEN))
        if status in {COMPLETED, IN_PROGRESS}:
            selected.add(str(slot))
    return selected


def _credit_value(course: Mapping[str, Any]) -> int:
    return int(course["credits"])


def _mandatory(course: Mapping[str, Any]) -> bool:
    return str(course.get("course_type")) == "bắt buộc"


def evaluate_student(
    profile: Mapping[str, Any],
    curriculum: Mapping[str, Any],
    rules_cfg: Mapping[str, Any],
    target_semester: int,
) -> dict[str, Any]:
    """Evaluate course eligibility and progress from an isolated scenario profile."""
    if target_semester < 1:
        raise ValueError("target_semester must be positive")
    student_id = str(profile.get("student_id", "")).strip()
    if not student_id:
        raise ValueError("profile.student_id is required")
    specialization = str(profile.get("specialization", ""))
    allowed_specializations = set(
        rules_cfg["program"]["program"]["specializations"]
    )
    if specialization not in allowed_specializations:
        raise ValueError(f"Unknown specialization: {specialization}")

    courses = list(curriculum["courses"])
    prerequisites = list(curriculum["prerequisites"])
    progress = profile.get("progress", {})
    if not isinstance(progress, Mapping):
        raise ValueError("profile.progress must map course IDs to progress records")
    statuses = {
        str(course_id): dict(record)
        for course_id, record in progress.items()
    }
    course_by_id = {str(row["course_id"]): row for row in courses}
    unknown_progress_ids = sorted(set(statuses) - set(course_by_id))
    if unknown_progress_ids:
        raise ValueError(f"Progress references unknown course IDs: {unknown_progress_ids}")

    enrichment = rules_cfg["enrichment"]
    program_config = rules_cfg["program"]
    prerequisite_config = enrichment["prerequisite_semantics"]
    regulation = rules_cfg.get("regulation") or load_regulation_config()
    strict_type = str(prerequisite_config["strict_type"]["value"])
    concurrent_type = str(prerequisite_config["concurrent_type"]["value"])
    retake_config = program_config["unknowns"]["retake_limit"]
    maximum_attempts = (
        None if retake_config["value"] == "UNKNOWN" else int(retake_config["value"])
    )
    active_slots = _active_slot_choices(courses, statuses, specialization)
    blocked_reasons: dict[str, list[dict[str, Any]]] = {}
    candidates: list[dict[str, Any]] = []
    required_unavailable: set[str] = set()

    for course in courses:
        course_id = str(course["course_id"])
        status_row = statuses.get(course_id, {"status": NOT_TAKEN})
        status = str(status_row.get("status", NOT_TAKEN))
        reasons: list[dict[str, Any]] = []
        if not _specialization_applies(course, specialization):
            reasons.append(
                {
                    "code": "OTHER_SPECIALIZATION",
                    "specialization": course.get("specialization"),
                }
            )
        if status in {COMPLETED, IN_PROGRESS}:
            reasons.append({"code": "ALREADY_COMPLETED_OR_IN_PROGRESS", "status": status})
        elif status not in {FAILED, NOT_TAKEN}:
            raise ValueError(f"Unknown progress status for {course_id}: {status}")
        if (
            status in {FAILED, NOT_TAKEN}
            and _specialization_applies(course, specialization)
        ):
            for relation in _prerequisite_relations(prerequisites, course_id):
                if (
                    str(relation["type"]) == strict_type
                    and statuses.get(
                        str(relation["prerequisite_id"]), {}
                    ).get("status")
                    != COMPLETED
                ):
                    prerequisite_id = str(relation["prerequisite_id"])
                    roots = _unmet_strict_roots(
                        prerequisites,
                        statuses,
                        course_id,
                        strict_type,
                    )
                    reasons.append(
                        {
                            "code": "PREREQUISITE_NOT_COMPLETED",
                            "course_id": prerequisite_id,
                            "root_causes": roots,
                        }
                    )
        if (
            status == FAILED
            and maximum_attempts is not None
            and int(status_row.get("attempt_count", 0) or 0) >= maximum_attempts
        ):
            reasons.append({"code": "RETAKE_LIMIT_REACHED"})
        if course.get("elective_slot") is not None and str(
            course["elective_slot"]
        ) in active_slots and status not in {COMPLETED, IN_PROGRESS}:
            reasons.append(
                {
                    "code": "ELECTIVE_SLOT_ALREADY_SELECTED",
                    "slot": str(course["elective_slot"]),
                }
            )
        if not _offered_in(course, target_semester):
            reasons.append(
                {
                    "code": "NOT_OFFERED",
                    "target_semester": target_semester,
                    "label": enrichment["offering_rule"]["label"],
                }
            )
        if reasons:
            blocked_reasons[course_id] = reasons
            if (
                _mandatory(course)
                and bool(course.get("counts_toward_total", True))
                and _specialization_applies(course, specialization)
                and status in {FAILED, NOT_TAKEN}
            ):
                if any(reason["code"] == "NOT_OFFERED" for reason in reasons):
                    required_unavailable.add(course_id)
            continue

        candidates.append(
            {
                **course,
                "status": status,
                "attempt_count": int(status_row.get("attempt_count", 0) or 0),
            }
        )

    candidate_ids = {str(row["course_id"]) for row in candidates}
    initially_eligible: set[str] = set()
    for course in candidates:
        course_id = str(course["course_id"])
        unmet: list[dict[str, Any]] = []
        for relation in _prerequisite_relations(prerequisites, course_id):
            prerequisite_id = str(relation["prerequisite_id"])
            relation_type = str(relation["type"])
            prerequisite_status = str(
                statuses.get(prerequisite_id, {}).get("status", NOT_TAKEN)
            )
            if relation_type == strict_type:
                if prerequisite_status != COMPLETED:
                    unmet.append(
                        {
                            "code": "PREREQUISITE_NOT_COMPLETED",
                            "course_id": prerequisite_id,
                        }
                    )
            elif relation_type == concurrent_type:
                if prerequisite_status in {COMPLETED, IN_PROGRESS}:
                    continue
                if prerequisite_id not in candidate_ids:
                    unmet.append(
                        {
                            "code": "COREQUISITE_NOT_ELIGIBLE",
                            "course_id": prerequisite_id,
                        }
                    )
            else:
                raise ValueError(
                    f"Unsupported prerequisite relation type: {relation_type}"
                )
        if unmet:
            blocked_reasons.setdefault(course_id, []).extend(unmet)
        else:
            initially_eligible.add(course_id)

    eligible_ids = set(initially_eligible)
    while True:
        removed: dict[str, list[dict[str, Any]]] = {}
        for course_id in eligible_ids:
            for relation in _prerequisite_relations(prerequisites, course_id):
                if str(relation["type"]) != concurrent_type:
                    continue
                prerequisite_id = str(relation["prerequisite_id"])
                prerequisite_status = str(
                    statuses.get(prerequisite_id, {}).get("status", NOT_TAKEN)
                )
                if (
                    prerequisite_status not in {COMPLETED, IN_PROGRESS}
                    and prerequisite_id not in eligible_ids
                ):
                    removed.setdefault(course_id, []).append(
                        {
                            "code": "COREQUISITE_NOT_ELIGIBLE",
                            "course_id": prerequisite_id,
                        }
                    )
        if not removed:
            break
        for course_id, reasons in removed.items():
            eligible_ids.discard(course_id)
            blocked_reasons.setdefault(course_id, []).extend(reasons)

    eligible_courses = [
        row for row in candidates if str(row["course_id"]) in eligible_ids
    ]
    eligible_courses.sort(
        key=lambda row: (
            int(row["planned_semester"]),
            str(row["course_id"]),
        )
    )
    blocked_courses = [
        {"course_key": course_id, "reasons": reasons}
        for course_id, reasons in sorted(blocked_reasons.items())
        if reasons
    ]

    program = program_config["program"]
    completed_courses = [
        row
        for row in courses
        if statuses.get(str(row["course_id"]), {}).get("status") == COMPLETED
        and bool(row.get("counts_toward_total", True))
    ]
    credits_earned = sum(_credit_value(row) for row in completed_courses)
    required_courses = [
        row
        for row in courses
        if _mandatory(row)
        and bool(row.get("counts_toward_total", True))
        and _specialization_applies(row, specialization)
    ]
    missing_mandatory = [
        row
        for row in required_courses
        if statuses.get(str(row["course_id"]), {}).get("status") != COMPLETED
    ]
    missing_mandatory_credits = sum(_credit_value(row) for row in missing_mandatory)

    slot_credit_requirements = enrichment["slot_required_credits"]
    required_slots = set(program["required_elective_slots"][specialization])
    required_slots.add(str(enrichment["graduation_slot"]["slot"]))
    remaining_slots = sorted(required_slots - active_slots)
    elective_credits_remaining = sum(
        int(slot_credit_requirements[slot]) for slot in remaining_slots
    )
    target_credits = int(program["total_credits"])
    credits_remaining = max(0, target_credits - credits_earned)
    all_completed_courses = [
        row
        for row in courses
        if statuses.get(str(row["course_id"]), {}).get("status") == COMPLETED
    ]
    cumulative_average = _cumulative_gpa(
        all_completed_courses,
        statuses,
        regulation,
    )
    graduation_config = regulation["graduation"]
    required_outcomes = list(graduation_config["required_outcomes"]["value"])
    supplied_outcomes = profile.get("graduation_outcomes", {})
    outcome_results = {
        outcome: (
            "MET"
            if isinstance(supplied_outcomes, Mapping)
            and supplied_outcomes.get(outcome) is True
            else "NOT_MET"
            if isinstance(supplied_outcomes, Mapping)
            and supplied_outcomes.get(outcome) is False
            else "UNKNOWN"
        )
        for outcome in required_outcomes
    }
    graduation_conditions = {
        "program_credits": {
            "status": "MET" if credits_earned >= int(graduation_config["credits_required"]["value"]) else "NOT_MET",
            "earned": credits_earned,
            "required": int(graduation_config["credits_required"]["value"]),
        },
        "mandatory_courses": {
            "status": "MET" if not missing_mandatory else "NOT_MET",
            "missing_course_ids": sorted(str(row["course_id"]) for row in missing_mandatory),
        },
        "elective_and_graduation_slots": {
            "status": "MET" if not remaining_slots else "NOT_MET",
            "missing_slots": remaining_slots,
        },
        "cumulative_gpa": {
            "status": (
                "MET"
                if cumulative_average is not None
                and cumulative_average >= float(graduation_config["cumulative_gpa_minimum"]["value"])
                else "NOT_MET"
                if cumulative_average is not None
                else "UNKNOWN"
            ),
            "value": cumulative_average,
            "required": float(graduation_config["cumulative_gpa_minimum"]["value"]),
            "scale": 10,
        },
        "learning_outcomes": {
            "status": "MET"
            if all(value == "MET" for value in outcome_results.values())
            else "NOT_MET"
            if any(value == "NOT_MET" for value in outcome_results.values())
            else "UNKNOWN",
            "details": outcome_results,
        },
    }
    graduation_ready = all(
        condition["status"] == "MET"
        for condition in graduation_conditions.values()
    )
    maximum_term_credits = program_config["unknowns"]["max_credits_per_semester"][
        "value"
    ]
    credit_term_lower_bound: int | None = None
    if maximum_term_credits != "UNKNOWN":
        credit_term_lower_bound = math.ceil(
            credits_remaining / int(maximum_term_credits)
        )

    chain_lower_bound = _remaining_prerequisite_chain(
        course_by_id,
        prerequisites,
        statuses,
        strict_type,
        specialization,
    )
    if graduation_ready:
        minimum_semesters_remaining: int | str = 0
    elif credit_term_lower_bound is not None:
        minimum_semesters_remaining = max(
            credit_term_lower_bound, chain_lower_bound
        )
    elif chain_lower_bound:
        minimum_semesters_remaining = chain_lower_bound
    else:
        minimum_semesters_remaining = "UNKNOWN"

    academic_flags = _academic_flags(profile, courses, statuses, regulation)
    completed_semester = int(
        profile.get(
            "last_completed_semester",
            profile.get("current_semester", 0),
        )
        or 0
    )
    previous_semester_average = (
        semester_gpa(courses, statuses, completed_semester, regulation)
        if completed_semester > 0
        and not bool(profile.get("is_summer_term", False))
        and profile.get("grade_data_available") is not False
        else _number(
            profile.get(
                "registration_previous_semester_gpa",
                profile.get("previous_semester_gpa"),
            )
        )
    )
    registration_completes_program = bool(
        profile.get("registration_completes_program", False)
    )
    plan_ids = profile.get("registration_plan_course_ids")
    if (
        not registration_completes_program
        and isinstance(plan_ids, Sequence)
        and not isinstance(plan_ids, (str, bytes))
    ):
        planned_ids = {str(course_id) for course_id in plan_ids}
        planned_rows = [
            course_by_id[course_id]
            for course_id in planned_ids
            if course_id in course_by_id
        ]
        planned_slots = {
            str(course["elective_slot"])
            for course in planned_rows
            if course.get("elective_slot") is not None
        }
        registration_completes_program = (
            {str(row["course_id"]) for row in missing_mandatory}.issubset(planned_ids)
            and set(remaining_slots).issubset(planned_slots)
            and sum(
                int(row["credits"])
                for row in planned_rows
                if bool(row.get("counts_toward_total", True))
            )
            >= credits_remaining
        )
    semester_credit_limits = credit_limits(
        {**profile, "previous_semester_gpa": previous_semester_average},
        {
            "is_first_semester": bool(profile.get("is_first_semester", target_semester == 1)),
            "registration_completes_program": registration_completes_program,
            "is_summer_term": bool(profile.get("is_summer_term", False)),
            "previous_semester_gpa": previous_semester_average,
        },
        regulation,
    )
    retake_grade_threshold = float(
        regulation["retake"]["mandatory_below_grade"]["value"]
    )
    forced_retakes = []
    for row in eligible_courses:
        course_id = str(row["course_id"])
        status_row = statuses.get(course_id, {})
        grade = _number(status_row.get("grade_10"))
        if grade is not None:
            grade = round_course_grade(grade, regulation)
        if (
            _mandatory(row)
            and status_row.get("status") == FAILED
            and grade is not None
            and grade < retake_grade_threshold
        ):
            row["must_register"] = True
            forced_retakes.append(
                {
                    "course_key": course_id,
                    "grade_10": grade,
                    "must_register": True,
                    "status": regulation["retake"]["mandatory_below_grade"]["rule_status"],
                    "ref": regulation["retake"]["mandatory_below_grade"]["ref"],
                }
            )
    retake_credits_total = _retake_credits_total(courses, statuses)
    honors_threshold = (
        float(regulation["retake"]["honors_repeat_credit_ratio"]["value"])
        * int(regulation["retake"]["honors_program_credits"]["value"])
    )
    honors_downgrade_risk = retake_credits_total > honors_threshold
    edge_case_flags: list[dict[str, Any]] = []
    if enrichment["prerequisite_semantics"]["completeness"] == "UNCONFIRMED":
        edge_case_flags.append(
            {
                "code": "PREREQUISITE_COMPLETENESS_UNCONFIRMED",
                "severity": "warning",
                "label": "GIẢ ĐỊNH (chờ đối chiếu quy chế)",
                "message": "Chưa xác nhận rằng dòng tiên quyết vắng mặt nghĩa là không có tiên quyết.",
            }
        )
    if maximum_attempts is None:
        edge_case_flags.append(
            {
                "code": "RETAKE_LIMIT_UNKNOWN",
                "severity": "warning",
                "source": "NOT_FOUND",
                "message": "Không áp giới hạn lượt học lại khi chưa có quy chế xác nhận.",
            }
        )
    if honors_downgrade_risk:
        edge_case_flags.append(
            {
                "code": "HONORS_DOWNGRADE_RISK",
                "severity": "info",
                "retake_credits_total": retake_credits_total,
                "threshold": honors_threshold,
                "comparison": ">",
                "status": regulation["retake"]["honors_repeat_credit_ratio"]["rule_status"],
                "ref": regulation["retake"]["honors_repeat_credit_ratio"]["ref"],
                "message": "Tín chỉ học lại vượt 5% tổng tín chỉ chương trình; chỉ báo thông tin.",
            }
        )
    if graduation_ready:
        edge_case_flags.append(
            {
                "code": "GRADUATION_READY",
                "severity": "info",
                "message": "Đã hoàn thành tín chỉ bắt buộc và các ô lựa chọn của lộ trình.",
            }
        )
    elif not eligible_courses:
        edge_case_flags.append(
            {
                "code": "NO_ELIGIBLE_COURSES",
                "severity": "warning",
                "message": "Không có học phần đủ điều kiện trong kỳ mục tiêu.",
            }
        )
    required_unavailable.update(
        str(row["course_id"])
        for row in required_courses
        if statuses.get(str(row["course_id"]), {}).get("status")
        in {FAILED, NOT_TAKEN}
        and not _offered_in(row, target_semester)
    )
    required_blocked = sorted(
        row["course_key"]
        for row in blocked_courses
        if row["course_key"] in {str(course["course_id"]) for course in required_courses}
    )
    if required_unavailable:
        edge_case_flags.append(
            {
                "code": "REQUIRED_COURSE_NOT_OFFERED",
                "severity": "warning",
                "course_keys": sorted(required_unavailable),
            }
        )
    if required_blocked:
        edge_case_flags.append(
            {
                "code": "REQUIRED_COURSE_BLOCKED",
                "severity": "warning",
                "course_keys": required_blocked,
            }
        )

    return {
        "student_id": student_id,
        "target_semester": target_semester,
        "eligible_courses": eligible_courses,
        "blocked_courses": blocked_courses,
        "progress_stats": {
            "credits_earned": credits_earned,
            "credits_remaining": credits_remaining,
            "mandatory_credits_remaining": missing_mandatory_credits,
            "mandatory_courses_remaining": sorted(
                str(row["course_id"]) for row in missing_mandatory
            ),
            "elective_slots_remaining": remaining_slots,
            "elective_credits_remaining": elective_credits_remaining,
            "minimum_semesters_remaining": minimum_semesters_remaining,
            "minimum_semesters_credit_limit": (
                credit_term_lower_bound
                if credit_term_lower_bound is not None
                else "UNKNOWN"
            ),
            "minimum_semesters_prerequisite_chain": chain_lower_bound,
            "graduation_ready": graduation_ready,
            "graduation_conditions": graduation_conditions,
            "cumulative_gpa_10": cumulative_average,
            "gpa_definition": regulation["gpa"]["cumulative_average"]["value"],
            "credits_include_external_courses": False,
            "registration_credit_limits": semester_credit_limits,
            "retake_credits_total": retake_credits_total,
            "honors_repeat_credit_threshold": honors_threshold,
            "honors_downgrade_risk": honors_downgrade_risk,
        },
        "academic_flags": academic_flags,
        "forced_retakes": forced_retakes,
        "edge_case_flags": edge_case_flags,
        "data_labels": [
            "OFFICIAL (NTU)",
            "GIẢ ĐỊNH (suy từ CTĐT)",
            "GIẢ ĐỊNH (chờ đối chiếu quy chế)",
        ],
    }


def _remaining_prerequisite_chain(
    course_by_id: Mapping[str, Mapping[str, Any]],
    prerequisite_rows: Sequence[Mapping[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
    strict_type: str,
    specialization: str,
) -> int:
    prerequisites: dict[str, list[str]] = {}
    for row in prerequisite_rows:
        if str(row["type"]) != strict_type:
            continue
        course_id = str(row["course_id"])
        prerequisite_id = str(row["prerequisite_id"])
        if course_id not in course_by_id or prerequisite_id not in course_by_id:
            continue
        if not _specialization_applies(course_by_id[course_id], specialization):
            continue
        prerequisites.setdefault(course_id, []).append(prerequisite_id)
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(course_id: str) -> int:
        if statuses.get(course_id, {}).get("status") == COMPLETED:
            return 0
        if course_id in visiting:
            return 0
        if course_id in memo:
            return memo[course_id]
        visiting.add(course_id)
        value = 1 + max(
            (depth(parent) for parent in prerequisites.get(course_id, [])),
            default=0,
        )
        visiting.remove(course_id)
        memo[course_id] = value
        return value

    return max((depth(course_id) for course_id in prerequisites), default=0)
