"""GPA and study-year calculations grounded in the configured NTU rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


_NON_NUMERIC_GRADE_CODES = {"I", "X", "R"}


def round_course_grade(value: float, config: Mapping[str, Any]) -> float:
    places = int(config["gpa"]["course_grade_rounding_decimals"]["value"])
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _grade(
    value: Any,
    excluded_codes: set[str],
    config: Mapping[str, Any],
) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().upper() in excluded_codes:
        return None
    try:
        return round_course_grade(float(value), config)
    except (TypeError, ValueError):
        return None


def _attempts(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    attempts = record.get("attempts")
    if isinstance(attempts, Sequence) and not isinstance(attempts, (str, bytes)):
        return [attempt for attempt in attempts if isinstance(attempt, Mapping)]
    return [record]


def _excluded_course(course: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
    gpa_config = config["gpa"]
    if not bool(course.get("counts_toward_total", True)):
        return True
    excluded_groups = {
        str(value) for value in gpa_config["excluded_course_groups"]["value"]
    }
    if str(course.get("group", "")) in excluded_groups:
        return True
    excluded_types = {
        str(value).strip().casefold()
        for value in gpa_config["excluded_course_type_values"]["value"]
    }
    return str(course.get("course_type", "")).strip().casefold() in excluded_types


def _round_gpa(value: float, config: Mapping[str, Any]) -> float:
    places = int(config["gpa"]["rounding_decimals"]["value"])
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def semester_gpa(
    courses: Sequence[Mapping[str, Any]],
    progress: Mapping[str, Mapping[str, Any]],
    semester: int,
    config: Mapping[str, Any],
) -> float | None:
    """Return credit-weighted GPA for a term, including graded failed courses."""
    excluded_codes = {
        str(code).upper() for code in config["gpa"]["excluded_grade_codes"]["value"]
    }
    excluded_codes |= _NON_NUMERIC_GRADE_CODES
    weighted_sum = 0.0
    total_credits = 0
    for course in courses:
        if _excluded_course(course, config):
            continue
        course_id = str(course["course_id"])
        record = progress.get(course_id)
        if not isinstance(record, Mapping):
            continue
        credits = int(course["credits"])
        for attempt in _attempts(record):
            if int(attempt.get("semester_taken", -1) or -1) != semester:
                continue
            grade = _grade(
                attempt.get("grade_10"),
                excluded_codes,
                config,
            )
            if grade is None:
                continue
            weighted_sum += credits * grade
            total_credits += credits
    if not total_credits:
        return None
    return _round_gpa(weighted_sum / total_credits, config)


def cumulative_gpa(
    courses: Sequence[Mapping[str, Any]],
    progress: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> float | None:
    """Return passed-course GPA using the highest grade across recorded attempts."""
    excluded_codes = {
        str(code).upper() for code in config["gpa"]["excluded_grade_codes"]["value"]
    }
    excluded_codes |= _NON_NUMERIC_GRADE_CODES
    passing_grade = float(config["gpa"]["passing_grade_minimum"]["value"])
    weighted_sum = 0.0
    total_credits = 0
    for course in courses:
        if _excluded_course(course, config):
            continue
        course_id = str(course["course_id"])
        record = progress.get(course_id)
        if not isinstance(record, Mapping):
            continue
        passed_grades: list[float] = []
        for attempt in _attempts(record):
            grade = _grade(
                attempt.get("grade_10"),
                excluded_codes,
                config,
            )
            status = str(attempt.get("status", record.get("status", "")))
            if grade is not None and grade >= passing_grade and status == "completed":
                passed_grades.append(grade)
        if passed_grades:
            credits = int(course["credits"])
            weighted_sum += credits * max(passed_grades)
            total_credits += credits
    if not total_credits:
        return None
    return _round_gpa(weighted_sum / total_credits, config)


def classify_academic_performance(
    semester_average: float | None,
    config: Mapping[str, Any],
) -> str:
    """Classify whether the average meets the official non-weak/poor threshold."""
    if semester_average is None:
        return "UNKNOWN"
    threshold = float(
        config["academic_classification"]["weak_or_poor_threshold"]["value"]
    )
    return "YEU_KEM" if semester_average < threshold else "NOT_YEU_KEM"


def classify_study_year(
    accumulated_credits: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Map accumulated credits to year level; 105-credit boundary is labeled."""
    if accumulated_credits < 0:
        raise ValueError("accumulated_credits must be non-negative")
    year_one, year_two, year_three = (
        int(value)
        for value in config["study_year"]["credit_thresholds"]["value"]
    )
    if accumulated_credits < year_one:
        year = 1
    elif accumulated_credits < year_two:
        year = 2
    elif accumulated_credits < year_three:
        year = 3
    else:
        year = 4
    exact_boundary = accumulated_credits == year_three
    return {
        "year": year,
        "accumulated_credits": accumulated_credits,
        "status": "UNCONFIRMED" if exact_boundary else "CONFIRMED",
        "label": (
            "GIẢ ĐỊNH (đúng 105 tín chỉ gán năm 4)"
            if exact_boundary
            else None
        ),
    }
