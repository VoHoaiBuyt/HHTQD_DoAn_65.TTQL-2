"""Boundary validation for user-entered profiles and progress rows."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

ALLOWED_STATUSES = {"completed", "in_progress", "failed", "not_taken"}


class InputError(ValueError):
    """User-correctable input error shown directly in the UI."""


def parse_number(
    value: Any,
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    required: bool = True,
) -> float | None:
    if isinstance(value, float) and math.isnan(value):
        value = None
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise InputError(f"{field}: không được để trống.")
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "").replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise InputError(f"{field}: giá trị '{value}' không phải số.") from error
    if not math.isfinite(number):
        raise InputError(f"{field}: giá trị phải là số hữu hạn.")
    if minimum is not None and number < minimum:
        raise InputError(f"{field}: phải ≥ {minimum}.")
    if maximum is not None and number > maximum:
        raise InputError(f"{field}: phải ≤ {maximum}.")
    return number


def parse_integer(value: Any, field: str, **bounds: float) -> int:
    number = parse_number(value, field, **bounds)
    assert number is not None
    if not number.is_integer():
        raise InputError(f"{field}: phải là số nguyên.")
    return int(number)


def normalize_profile(
    profile: Mapping[str, Any],
    *,
    max_semester: int = 8,
) -> dict[str, Any]:
    student_id = str(profile.get("student_id", "")).strip()
    if not student_id:
        raise InputError("Mã sinh viên: không được để trống.")

    current_semester = parse_integer(
        profile.get("current_semester"),
        "Học kỳ hiện tại",
        minimum=1,
        maximum=max_semester,
    )
    gpa = parse_number(profile.get("gpa"), "GPA", minimum=0.0, maximum=4.0)
    cumulative_credits = parse_integer(
        profile.get("cumulative_credits"),
        "Tín chỉ tích lũy",
        minimum=0,
        maximum=300,
    )
    failed_courses_count = parse_integer(
        profile.get("failed_courses_count"),
        "Số môn chưa đạt",
        minimum=0,
        maximum=48,
    )
    def first_present(*values: Any) -> Any:
        for value in values:
            if value is not None and not (
                isinstance(value, float) and math.isnan(value)
            ):
                return value
        return None

    hk1_enrolled = parse_integer(
        first_present(
            profile.get("hk1_enrolled"),
            profile.get("Curricular units 1st sem (enrolled)"),
        ),
        "Số unit HK1 đăng ký",
        minimum=0,
        maximum=30,
    )
    hk1_approved = parse_integer(
        first_present(
            profile.get("hk1_approved"),
            profile.get("Curricular units 1st sem (approved)"),
        ),
        "Số unit HK1 đạt",
        minimum=0,
        maximum=hk1_enrolled,
    )
    hk1_grade = parse_number(
        first_present(
            profile.get("hk1_grade"),
            profile.get("Curricular units 1st sem (grade)"),
        ),
        "Điểm trung bình HK1 (thang 20)",
        minimum=0.0,
        maximum=20.0,
        required=False,
    )

    normalized = dict(profile)
    normalized.update(
        {
            "student_id": student_id,
            "current_semester": current_semester,
            "gpa": float(gpa),
            "cumulative_credits": int(cumulative_credits),
            "failed_courses_count": int(failed_courses_count),
            "hk1_enrolled": hk1_enrolled,
            "hk1_approved": hk1_approved,
            "hk1_grade": (float(hk1_grade) if hk1_grade is not None else None),
            "Curricular units 1st sem (enrolled)": hk1_enrolled,
            "Curricular units 1st sem (approved)": hk1_approved,
            "Curricular units 1st sem (grade)": (
                float(hk1_grade) if hk1_grade is not None else 0.0
            ),
        }
    )
    return normalized


def normalize_progress_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    known_course_ids: Sequence[str],
    max_semester: int = 8,
) -> list[dict[str, Any]]:
    known = set(known_course_ids)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        course_id = str(row.get("course_id", "")).strip()
        if not course_id:
            raise InputError(f"Dòng tiến độ {index}: thiếu course_id.")
        if course_id not in known:
            raise InputError(f"Dòng {index}: course_id '{course_id}' không có trong CTĐT.")
        if course_id in seen:
            raise InputError(f"Dòng {index}: course_id '{course_id}' bị trùng.")
        seen.add(course_id)

        status = str(row.get("status", "not_taken")).strip().lower()
        if status not in ALLOWED_STATUSES:
            raise InputError(
                f"Dòng {index}: status '{status}' không hợp lệ "
                f"({', '.join(sorted(ALLOWED_STATUSES))})."
            )
        attempt_value = row.get("attempt_count", 0)
        if isinstance(attempt_value, float) and math.isnan(attempt_value):
            attempt_value = 0
        attempt_count = parse_integer(
            attempt_value or 0,
            f"Dòng {index} - số lần học",
            minimum=0,
            maximum=10,
        )
        grade = parse_number(
            row.get("grade_10"),
            f"Dòng {index} - điểm hệ 10",
            minimum=0.0,
            maximum=10.0,
            required=False,
        )
        semester_taken = parse_number(
            row.get("semester_taken"),
            f"Dòng {index} - học kỳ đã học",
            minimum=1,
            maximum=max_semester,
            required=False,
        )
        normalized.append(
            {
                "student_id": str(row.get("student_id", "")).strip(),
                "course_id": course_id,
                "status": status,
                "grade_10": grade,
                "attempt_count": attempt_count,
                "semester_taken": (
                    int(semester_taken) if semester_taken is not None else None
                ),
            }
        )
    return normalized
