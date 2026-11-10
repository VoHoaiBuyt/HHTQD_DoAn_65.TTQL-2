"""Rule-based academic flags, course eligibility, and progress statistics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "src" / "config" / "credit_rules.yaml"


def load_rules(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def risk_tier(p_dropout: float, rules: Mapping[str, Any]) -> str:
    """Map the model score to a provisional warning tier."""
    if not 0 <= p_dropout <= 1:
        raise ValueError("p_dropout must be in [0, 1]")
    tiers = rules["rule_engine"]["risk_tiers"]
    if p_dropout <= float(tiers["low_max_p_dropout"]["value"]):
        return "low"
    if p_dropout <= float(tiers["medium_max_p_dropout"]["value"]):
        return "medium"
    return "high"


def _course_prerequisites_met(
    course_id: str,
    prerequisite_rows: Sequence[Mapping[str, Any]],
    status_by_course: Mapping[str, str],
    candidate_ids: set[str],
    rules: Mapping[str, Any],
    *,
    eligible_ids: set[str] | None = None,
) -> bool:
    policy = rules["rule_engine"]["prerequisite_policy"]
    for relation in prerequisite_rows:
        if str(relation["course_id"]) != course_id:
            continue
        prerequisite_id = str(relation["prerequisite_id"])
        relation_type = str(relation["type"])
        status = status_by_course.get(prerequisite_id, "not_taken")
        if relation_type == policy["strict_type"]["value"]:
            if status != "completed":
                return False
        elif relation_type == policy["prior_study_type"]["value"]:
            if status not in {"completed", "failed", "in_progress"}:
                return False
        elif relation_type == policy["concurrent_type"]["value"]:
            if status in {"completed", "in_progress"}:
                continue
            if prerequisite_id not in candidate_ids:
                return False
            if eligible_ids is not None and prerequisite_id not in eligible_ids:
                return False
        else:
            raise ValueError(f"Unknown prerequisite relation type: {relation_type}")
    return True


def _resolve_concurrent_eligibility(
    base_candidates: Sequence[Mapping[str, Any]],
    prerequisite_rows: Sequence[Mapping[str, Any]],
    status_by_course: Mapping[str, str],
    rules: Mapping[str, Any],
) -> set[str]:
    candidate_ids = {str(course["course_id"]) for course in base_candidates}
    eligible_ids = {
        str(course["course_id"])
        for course in base_candidates
        if _course_prerequisites_met(
            str(course["course_id"]),
            prerequisite_rows,
            status_by_course,
            candidate_ids,
            rules,
        )
    }

    concurrent_type = rules["rule_engine"]["prerequisite_policy"]["concurrent_type"]["value"]
    while True:
        changed = False
        for course in base_candidates:
            course_id = str(course["course_id"])
            if course_id not in eligible_ids:
                continue
            for relation in prerequisite_rows:
                if str(relation["course_id"]) != course_id:
                    continue
                if str(relation["type"]) != concurrent_type:
                    continue
                prerequisite_id = str(relation["prerequisite_id"])
                status = status_by_course.get(prerequisite_id, "not_taken")
                if status in {"completed", "in_progress"}:
                    continue
                if prerequisite_id not in eligible_ids:
                    eligible_ids.remove(course_id)
                    changed = True
                    break
            if changed:
                break
        if not changed:
            return eligible_ids


def _longest_strict_prerequisite_chain(
    courses: Sequence[Mapping[str, Any]],
    prerequisite_rows: Sequence[Mapping[str, Any]],
    status_by_course: Mapping[str, str],
    strict_type: str,
) -> int:
    strict_prerequisites: dict[str, list[str]] = {}
    course_ids = {str(course["course_id"]) for course in courses}
    for relation in prerequisite_rows:
        course_id = str(relation["course_id"])
        prerequisite_id = str(relation["prerequisite_id"])
        if (
            str(relation["type"]) == strict_type
            and course_id in course_ids
            and prerequisite_id in course_ids
        ):
            strict_prerequisites.setdefault(course_id, []).append(prerequisite_id)

    memo: dict[str, int] = {}

    def depth(course_id: str) -> int:
        if status_by_course.get(course_id) == "completed":
            return 0
        if course_id in memo:
            return memo[course_id]
        memo[course_id] = 1 + max(
            (depth(prerequisite) for prerequisite in strict_prerequisites.get(course_id, [])),
            default=0,
        )
        return memo[course_id]

    return max((depth(course_id) for course_id in course_ids), default=0)


def evaluate_student(
    student_profile: Mapping[str, Any],
    courses: Sequence[Mapping[str, Any]],
    prerequisites: Sequence[Mapping[str, Any]],
    student_progress: Sequence[Mapping[str, Any]],
    *,
    next_semester: int,
    p_dropout: float,
    p_dropout_calibrated: float | None = None,
    rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return separate academic warnings, eligibility, and curriculum progress.

    Courses planned after ``next_semester`` may be taken ahead when they are
    offered in that term and their prerequisite conditions are met.
    """
    active_rules = rules or load_rules()
    if next_semester < 1:
        raise ValueError("next_semester must be positive")
    student_id = str(student_profile.get("student_id", ""))
    if not student_id:
        raise ValueError("student_profile must include student_id")
    tier = risk_tier(float(p_dropout), active_rules)
    if p_dropout_calibrated is not None and not 0 <= p_dropout_calibrated <= 1:
        raise ValueError("p_dropout_calibrated must be in [0, 1]")
    restriction_probability = (
        float(p_dropout_calibrated)
        if p_dropout_calibrated is not None
        else float(p_dropout)
    )
    restriction_config = active_rules["rule_engine"]["risk_restriction"]
    restriction_threshold = float(
        restriction_config.get(
            "selected_probability_threshold",
            restriction_config["minimum_probability"],
        )["value"]
    )
    load_restriction_recommended = (
        restriction_probability >= restriction_threshold
    )

    progress_by_course = {
        str(row["course_id"]): row for row in student_progress
    }
    status_by_course = {
        course_id: str(row.get("status", "not_taken"))
        for course_id, row in progress_by_course.items()
    }
    maximum_attempts = int(
        active_rules["retake"]["maximum_attempts"]["value"]
    )
    offered_key = "odd" if next_semester % 2 else "even"
    base_candidates = []
    for course in courses:
        course_id = str(course["course_id"])
        status = status_by_course.get(course_id, "not_taken")
        if status not in {"failed", "not_taken"}:
            continue
        attempt_count = int(
            progress_by_course.get(course_id, {}).get("attempt_count", 0) or 0
        )
        if status == "failed" and attempt_count >= maximum_attempts:
            continue
        offerings = {
            value.strip()
            for value in str(course["offered_semesters"]).split(",")
        }
        if "both" not in offerings and offered_key not in offerings:
            continue
        base_candidates.append(
            {
                **course,
                "course_id": course_id,
                "credits": int(course["credits"]),
                "status": status,
                "attempt_count": attempt_count,
            }
        )

    candidate_ids = {str(item["course_id"]) for item in base_candidates}
    eligible_ids = _resolve_concurrent_eligibility(
        base_candidates,
        prerequisites,
        status_by_course,
        active_rules,
    )
    eligible_courses = [
        course
        for course in base_candidates
        if str(course["course_id"]) in eligible_ids
    ]
    eligible_courses.sort(
        key=lambda item: (
            0 if item["status"] == "failed" else 1,
            int(item["planned_semester"]),
            item["course_id"],
        )
    )

    edge_case_flags: list[dict[str, str]] = []
    academic = active_rules["academic_warning"]
    academic_flags: list[dict[str, str]] = []
    gpa = student_profile.get("gpa")
    if gpa not in (None, "") and float(gpa) < float(academic["gpa_below"]["value"]):
        academic_flags.append(
            {
                "code": "LOW_GPA",
                "severity": "warning",
                "source": "academic_rule",
                "message": "GPA thấp hơn ngưỡng cảnh báo cấu hình.",
            }
        )
    failed_count = int(student_profile.get("failed_courses_count", 0) or 0)
    if failed_count > 0:
        academic_flags.append(
            {
                "code": "FAILED_COURSES",
                "severity": "warning",
                "source": "academic_rule",
                "message": f"Còn {failed_count} học phần chưa đạt theo hồ sơ.",
            }
        )

    program = active_rules["program"]
    expected_semesters = int(program["expected_semester_count"]["value"])
    expected_credits = (
        float(program["expected_total_credits"]["max"])
        + float(program["expected_total_credits"]["min"])
    ) / 2
    expected_per_semester = expected_credits / expected_semesters
    current_semester = int(student_profile.get("current_semester", 0) or 0)
    completed_credits = sum(
        int(course["credits"])
        for course in courses
        if status_by_course.get(str(course["course_id"])) == "completed"
    )
    credits_remaining = max(
        0,
        int(active_rules["rule_engine"]["graduation"]["credits_required"]["value"])
        - completed_credits,
    )
    if credits_remaining == 0:
        edge_case_flags.append(
            {
                "code": "GRADUATION_CREDITS_MET",
                "severity": "info",
                "source": "curriculum_rule",
                "message": "Đã đạt ngưỡng tín chỉ tốt nghiệp mô phỏng.",
            }
        )
    elif not eligible_courses:
        edge_case_flags.append(
            {
                "code": "NO_ELIGIBLE_COURSES",
                "severity": "warning",
                "source": "curriculum_rule",
                "message": "Không có học phần đủ điều kiện trong kỳ; cần kiểm tra tiên quyết/lịch mở.",
            }
        )

    unavailable_required_courses = []
    blocked_required_courses = []
    for course in courses:
        course_id = str(course["course_id"])
        if str(course.get("course_type")) != "bắt buộc":
            continue
        if int(course["planned_semester"]) > next_semester:
            continue
        status = status_by_course.get(course_id, "not_taken")
        if status not in {"failed", "not_taken"}:
            continue
        attempt_count = int(
            progress_by_course.get(course_id, {}).get("attempt_count", 0) or 0
        )
        if status == "failed" and attempt_count >= maximum_attempts:
            continue
        if not _course_prerequisites_met(
            course_id,
            prerequisites,
            status_by_course,
            candidate_ids,
            active_rules,
            eligible_ids=eligible_ids,
        ):
            blocked_required_courses.append(course_id)
            continue
        offerings = {
            value.strip()
            for value in str(course["offered_semesters"]).split(",")
        }
        if "both" not in offerings and offered_key not in offerings:
            unavailable_required_courses.append(course_id)
    if unavailable_required_courses:
        edge_case_flags.append(
            {
                "code": "REQUIRED_COURSE_NOT_OFFERED",
                "severity": "warning",
                "source": "curriculum_rule",
                "message": (
                    "Học phần bắt buộc chưa mở kỳ tới: "
                    + ", ".join(sorted(unavailable_required_courses))
                ),
            }
        )
    if blocked_required_courses:
        edge_case_flags.append(
            {
                "code": "REQUIRED_COURSE_BLOCKED",
                "severity": "warning",
                "source": "curriculum_rule",
                "message": (
                    "Học phần bắt buộc bị chặn bởi tiên quyết: "
                    + ", ".join(sorted(blocked_required_courses))
                ),
            }
        )
    credits_behind = max(
        0,
        int(round(current_semester * expected_per_semester - completed_credits)),
    )
    if credits_behind >= int(academic["credits_behind_expected"]["value"]):
        academic_flags.append(
            {
                "code": "CREDITS_BEHIND",
                "severity": "warning",
                "source": "academic_rule",
                "message": f"Thiếu tiến độ tích lũy khoảng {credits_behind} tín chỉ.",
            }
        )

    semester_limits = active_rules["semester_credit_limits"]
    recommended_credit_cap = min(
        int(semester_limits["maximum"]["value"]),
        int(active_rules["rule_engine"]["risk_tiers"]["credit_caps"][tier]),
    )
    enforce_cap = bool(
        active_rules["rule_engine"]["risk_tiers"]["enforce_cap"]["value"]
    )
    max_credits = (
        recommended_credit_cap
        if enforce_cap and load_restriction_recommended
        else int(semester_limits["maximum"]["value"])
    )
    minimum_terms_by_credits = (
        math.ceil(credits_remaining / max_credits) if credits_remaining else 0
    )
    longest_chain = _longest_strict_prerequisite_chain(
        courses,
        prerequisites,
        status_by_course,
        active_rules["rule_engine"]["prerequisite_policy"]["strict_type"]["value"],
    )
    minimum_terms = max(minimum_terms_by_credits, longest_chain)
    progress_stats = {
        "credits_earned": completed_credits,
        "credits_remaining": credits_remaining,
        "credits_behind_expected": credits_behind,
        "minimum_semesters_remaining": minimum_terms,
        "longest_strict_prerequisite_chain": longest_chain,
        "graduation_credit_threshold_met": credits_remaining == 0,
        "data_label": "SIMULATED curriculum + academic rules",
    }
    tier_config = active_rules["rule_engine"]["risk_tiers"]
    return {
        "student_id": student_id,
        "risk_tier": tier,
        "risk_tier_purpose": "warning only; not a hard load restriction",
        "risk_tier_thresholds_label": "validation-derived exploratory; TODO giảng viên duyệt",
        "credit_cap": max_credits,
        "recommended_credit_cap": recommended_credit_cap,
        "load_restriction_recommended": load_restriction_recommended,
        "restriction_probability": restriction_probability,
        "restriction_probability_threshold": restriction_threshold,
        "enforce_cap": enforce_cap,
        "expected_failed_course_cap": float(
            tier_config["expected_failed_course_caps"][tier]
        ),
        "eligible_courses": eligible_courses,
        "progress_stats": progress_stats,
        "academic_flags": academic_flags,
        "edge_case_flags": edge_case_flags,
        "p_dropout": float(p_dropout),
        "data_label": "SIMULATED planning fixture + EXPLORATORY risk",
    }
