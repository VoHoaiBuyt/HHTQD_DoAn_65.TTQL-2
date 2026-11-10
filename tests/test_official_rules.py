from __future__ import annotations

from typing import Any

import pytest

from core.curriculum import load_enriched_curriculum, load_rules_config
from core.gpa import classify_study_year, cumulative_gpa, semester_gpa
from core.optimizer import optimize_plan
from core.regulation import iter_parameters, load_regulation_config
from core.rules import _academic_flags, credit_limits, evaluate_student


TEST_FIXTURE = "TEST_FIXTURE"


def _course(
    course_id: str,
    *,
    credits: int = 3,
    course_type: str = "bắt buộc",
    offering_rule: list[str] | None = None,
    elective_slot: str | None = None,
    specialization: str = "common",
    counts_toward_total: bool = True,
    group: str = TEST_FIXTURE,
) -> dict[str, Any]:
    offerings = offering_rule or ["both"]
    return {
        "course_id": course_id,
        "course_name": course_id,
        "credits": credits,
        "planned_semester": 1,
        "course_type": course_type,
        "offered_semesters": ",".join(offerings),
        "offering_rule": offerings,
        "group": group,
        "source_label": TEST_FIXTURE,
        "specialization": specialization,
        "counts_toward_total": counts_toward_total,
        "elective_slot": elective_slot,
        "slot_required_credits": 2 if elective_slot else None,
        "graduation_slot": elective_slot == "HP048",
        "code_source": TEST_FIXTURE,
        "enrichment_label": TEST_FIXTURE,
    }


def _evaluate(
    courses: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    *,
    semester: int = 1,
    profile_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = {
        "student_id": TEST_FIXTURE,
        "specialization": "SE",
        "last_completed_semester": semester,
        "progress": progress,
        **(profile_updates or {}),
    }
    return evaluate_student(
        profile,
        {"courses": courses, "prerequisites": []},
        load_rules_config(),
        semester,
    )


def _flags(
    courses: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    *,
    semester: int,
    profile: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    result = _academic_flags(
        {"last_completed_semester": semester, **(profile or {})},
        courses,
        progress,
        load_regulation_config(),
    )
    return {flag["code"]: flag for flag in result}


def _required_graduation_profile(gpa: float) -> tuple[dict[str, Any], dict[str, Any]]:
    curriculum = load_enriched_curriculum()
    program = curriculum["program_config"]["program"]
    required_ids = {
        str(course["course_id"])
        for course in curriculum["courses"]
        if course["counts_toward_total"]
        and course["course_type"] == "bắt buộc"
        and course["specialization"] in {"common", "SE"}
    }
    required_slots = set(program["required_elective_slots"]["SE"])
    required_slots.add("HP048")
    for slot in required_slots:
        alternatives = [
            course
            for course in curriculum["courses"]
            if course["counts_toward_total"]
            and course["elective_slot"] == slot
            and course["specialization"] in {"common", "SE"}
        ]
        assert alternatives, slot
        required_ids.add(str(alternatives[0]["course_id"]))
    course_by_id = {
        str(course["course_id"]): course for course in curriculum["courses"]
    }
    grades = {course_id: gpa for course_id in required_ids}
    if gpa == 5.49:
        subsets: dict[int, list[str]] = {0: []}
        for course_id in sorted(required_ids):
            credits = int(course_by_id[course_id]["credits"])
            for total, course_ids in list(subsets.items()):
                next_total = total + credits
                if next_total <= 117 and next_total not in subsets:
                    subsets[next_total] = course_ids + [course_id]
        assert 117 in subsets
        high_grade_ids = set(subsets[117])
        for course_id in required_ids:
            grades[course_id] = 5.5 if course_id in high_grade_ids else 5.4
    progress = {
        course_id: {
            "status": "completed",
            "grade_10": grades[course_id],
            "attempt_count": 1,
            "semester_taken": int(course_by_id[course_id]["planned_semester"]),
        }
        for course_id in required_ids
    }
    profile = {
        "student_id": TEST_FIXTURE,
        "specialization": "SE",
        "last_completed_semester": 8,
        "registration_completes_program": True,
        "progress": progress,
        "graduation_outcomes": {
            "gdtc": True,
            "qpan": True,
            "foreign_language": True,
            "informatics": True,
        },
    }
    return curriculum, profile


def test_official_configuration_references_and_statuses() -> None:
    config = load_regulation_config()
    parameters = iter_parameters(config)
    assert parameters
    assert all(
        item["ref"] and item["rule_status"] and isinstance(item["modeled"], bool)
        for item in parameters
    )
    assert all(
        item["rule_status"] == "CONFIRMED"
        for item in parameters
        if item["path"].startswith(
            ("credit_limits.normal.", "credit_limits.weak_or_poor.")
        )
    )
    assert any(item["rule_status"] == "UNCONFIRMED" for item in parameters)
    assert config["retake"]["improvement_study"]["rule_status"] == "CONFIRMED"
    assert config["retake"]["improvement_study"]["modeled"] is False
    assert config["academic_warnings"]["monte_carlo_scope"]["rule_status"] == "MODELING_DECISION"
    assert config["graduation"]["required_outcomes"]["rule_status"] == "CONFIRMED"
    assert config["graduation"]["outcome_details"]["rule_status"] == "UNKNOWN"
    parameters_by_path = {item["path"]: item for item in parameters}
    expected_references = {
        "gpa.grade_scale": "Đ14.1, Đ15.2b",
        "gpa.course_grade_rounding_decimals": "Đ15.2b",
        "gpa.rounding_decimals": "Đ17.1",
        "gpa.passing_grade_minimum": "Đ15.2c",
        "credit_limits.summer_term": "Đ7.2b",
        "academic_warnings.evaluation_scope": "Đ19.1",
        "academic_warnings.W1.threshold": "Đ19.1a",
        "academic_warnings.W3.first_semester_threshold": "Đ19.1b",
        "academic_warnings.W4.cumulative_average_threshold_by_study_year": "Đ19.1c",
        "retake.honors_repeat_credit_ratio": "Đ22.3a",
        "graduation.cumulative_gpa_minimum": "Đ14.3, Đ21.1c",
    }
    assert {
        path: parameters_by_path[path]["ref"] for path in expected_references
    } == expected_references
    assert {
        item["name"] for item in config["assumptions"]["items"]
    } == {
        "w1_debt",
        "study_year_boundary",
        "final_semester",
        "corequisite_semantics",
        "odd_even_offerings",
    }


@pytest.mark.parametrize(
    ("average", "regime", "minimum", "maximum"),
    [
        (5.00, "NORMAL", 15, 27),
        (4.99, "WEAK_OR_POOR", 12, 18),
    ],
)
def test_credit_limits_follow_previous_semester_average(
    average: float,
    regime: str,
    minimum: int,
    maximum: int,
) -> None:
    limits = credit_limits(
        {"academic_warning_active": regime == "NORMAL"},
        {"previous_semester_gpa": average},
    )
    assert (limits["regime"], limits["cmin"], limits["cmax"]) == (
        regime,
        minimum,
        maximum,
    )


def test_credit_limits_do_not_use_warning_flag_or_guess_unknown_gpa() -> None:
    limits = credit_limits({"academic_warning_active": True}, {})
    assert limits["regime"] == "UNKNOWN"
    assert (limits["cmin"], limits["cmax"]) == ("UNKNOWN", "UNKNOWN")
    unrestricted = credit_limits(
        {"academic_warning_active": True},
        {"previous_semester_gpa": 4.0, "registration_completes_program": True},
    )
    assert (unrestricted["cmin"], unrestricted["cmax"]) == (0, None)
    assert unrestricted["regime"] == "UNRESTRICTED_FINAL"
    assert any("GIẢ ĐỊNH" in note for note in unrestricted["notes"])


def test_credit_limits_summer_and_first_semester_exceptions() -> None:
    summer = credit_limits({}, {"is_summer_term": True})
    assert (summer["cmin"], summer["cmax"]) == (None, None)
    assert summer["regime"] == "UNRESTRICTED_SUMMER"
    first = credit_limits({}, {"is_first_semester": True})
    assert (first["cmin"], first["cmax"]) == (None, None)
    assert first["regime"] == "FIRST_SEMESTER_PLAN"


@pytest.mark.parametrize(
    ("credits", "active"),
    [(24, False), (25, True)],
)
def test_w1_debt_credit_boundary(credits: int, active: bool) -> None:
    flags = _flags(
        [_course("F", credits=credits)],
        {"F": {"status": "failed", "semester_taken": 1}},
        semester=1,
    )
    assert flags["W1"]["active"] is active
    assert flags["W1"]["value"] == credits


@pytest.mark.parametrize(
    ("failed_credits", "registered_credits", "active"),
    [(3, 6, False), (4, 7, True)],
)
def test_w2_credit_ratio_boundary(
    failed_credits: int,
    registered_credits: int,
    active: bool,
) -> None:
    courses = [
        _course("F", credits=failed_credits),
        _course("P", credits=registered_credits - failed_credits),
    ]
    flags = _flags(
        courses,
        {
            "F": {"status": "failed", "semester_taken": 1},
            "P": {"status": "completed", "grade_10": 7, "semester_taken": 1},
        },
        semester=1,
    )
    assert flags["W2"]["active"] is active
    assert flags["W2"]["value"] == pytest.approx(failed_credits / registered_credits)


def test_w2_uses_officially_rounded_course_grade() -> None:
    flags = _flags(
        [_course("ROUND")],
        {
            "ROUND": {
                "status": "completed",
                "grade_10": 4.96,
                "semester_taken": 1,
            }
        },
        semester=1,
    )
    assert flags["W2"]["failed_credits"] == 0


@pytest.mark.parametrize(
    ("semester", "grade", "active"),
    [
        (1, 4.00, False),
        (1, 3.99, True),
        (2, 4.50, False),
        (2, 4.49, True),
    ],
)
def test_w3_grade_thresholds(
    semester: int,
    grade: float,
    active: bool,
) -> None:
    if grade in {4.0, 4.5}:
        courses = [_course("C", credits=10)]
        progress = {
            "C": {
                "status": "failed",
                "grade_10": grade,
                "semester_taken": semester,
            }
        }
    else:
        low = round(grade - 0.1, 1)
        courses = [_course("LOW", credits=1), _course("HIGH", credits=9)]
        progress = {
            "LOW": {"status": "failed", "grade_10": low, "semester_taken": semester},
            "HIGH": {"status": "failed", "grade_10": grade, "semester_taken": semester},
        }
    flags = _flags(courses, progress, semester=semester)
    assert flags["W3"]["active"] is active
    assert flags["W3"]["value"] == grade


@pytest.mark.parametrize(
    ("credits", "threshold", "grade", "active"),
    [
        (34, 5.2, 5.19, True),
        (34, 5.2, 5.20, False),
        (35, 5.3, 5.29, True),
        (35, 5.3, 5.30, False),
        (70, 5.4, 5.39, True),
        (70, 5.4, 5.40, False),
        (105, 5.5, 5.49, True),
        (105, 5.5, 5.50, False),
    ],
)
def test_w4_study_year_and_threshold_boundaries(
    credits: int,
    threshold: float,
    grade: float,
    active: bool,
) -> None:
    if grade == threshold:
        courses = [_course("C", credits=credits)]
        progress = {
            "C": {"status": "completed", "grade_10": grade, "semester_taken": 2}
        }
    else:
        lower_grade = round(threshold - 0.1, 1)
        higher_credits = round((grade - lower_grade) * 10 * credits)
        lower_credits = credits - higher_credits
        courses = [
            _course("LOW", credits=lower_credits),
            _course("HIGH", credits=higher_credits),
        ]
        progress = {
            "LOW": {
                "status": "completed",
                "grade_10": lower_grade,
                "semester_taken": 2,
            },
            "HIGH": {
                "status": "completed",
                "grade_10": threshold,
                "semester_taken": 2,
            },
        }
    flags = _flags(courses, progress, semester=2)
    assert flags["W4"]["threshold"] == threshold
    assert flags["W4"]["active"] is active


@pytest.mark.parametrize(
    ("credits", "year", "status"),
    [
        (34, 1, "CONFIRMED"),
        (35, 2, "CONFIRMED"),
        (69, 2, "CONFIRMED"),
        (70, 3, "CONFIRMED"),
        (104, 3, "CONFIRMED"),
        (105, 4, "UNCONFIRMED"),
    ],
)
def test_study_year_credit_boundaries(credits: int, year: int, status: str) -> None:
    result = classify_study_year(credits, load_regulation_config())
    assert result["year"] == year
    assert result["status"] == status


@pytest.mark.parametrize(
    ("warnings", "duration", "active"),
    [
        (1, 8, False),
        (2, 8, False),
        (3, 8, True),
        (0, 16, False),
        (0, 17, True),
    ],
)
def test_forced_withdrawal_boundaries(
    warnings: int,
    duration: int,
    active: bool,
) -> None:
    flags = _flags(
        [],
        {},
        semester=duration,
        profile={
            "consecutive_warning_count": warnings,
            "duration_main_semesters": duration,
        },
    )
    assert flags["FORCED_WITHDRAWAL"]["active"] is active
    assert flags["FORCED_WITHDRAWAL"]["status"] == "CONFIRMED"


def test_pass_fail_monte_carlo_only_reports_w1_w2_scope() -> None:
    flags = _flags(
        [_course("F", credits=25)],
        {"F": {"status": "failed", "semester_taken": 1}},
        semester=1,
        profile={"simulation_mode": "pass_fail", "grade_data_available": False},
    )
    assert flags["W1"]["active"]
    assert flags["W3"]["calculation_status"] == "pass_fail_only"
    assert flags["W4"]["calculation_status"] == "pass_fail_only"
    assert "chỉ W1/W2" in flags["MONTE_CARLO_WITHDRAWAL_SCOPE"]["message"]


def test_gpa_uses_highest_passed_grade_and_excludes_codes_and_external_courses() -> None:
    config = load_regulation_config()
    courses = [
        _course("REPEAT", credits=3),
        _course("INCOMPLETE", credits=3),
        _course(
            "EXTERNAL",
            credits=5,
            counts_toward_total=False,
            group="GDTC và QP-AN ngoài 130 tín chỉ",
        ),
        _course("CONDITION", credits=4, course_type="điều kiện"),
    ]
    progress = {
        "REPEAT": {
            "status": "completed",
            "attempts": [
                {"status": "failed", "grade_10": 4.0, "semester_taken": 1},
                {"status": "completed", "grade_10": 7.0, "semester_taken": 2},
                {"status": "completed", "grade_10": 8.0, "semester_taken": 3},
            ],
        },
        "INCOMPLETE": {
            "status": "completed",
            "grade_10": "I",
            "semester_taken": 3,
        },
        "EXTERNAL": {
            "status": "completed",
            "grade_10": 10,
            "semester_taken": 3,
        },
        "CONDITION": {
            "status": "completed",
            "grade_10": 10,
            "semester_taken": 3,
        },
    }
    assert semester_gpa(courses, progress, 3, config) == 8.0
    assert cumulative_gpa(courses, progress, config) == 8.0
    assert semester_gpa(
        courses,
        {"REPEAT": {"status": "failed", "grade_10": 4.0, "semester_taken": 1}},
        1,
        config,
    ) == 4.0


def test_course_grades_are_rounded_to_one_decimal_before_gpa() -> None:
    config = load_regulation_config()
    courses = [_course("ROUND")]
    progress = {
        "ROUND": {
            "status": "completed",
            "grade_10": 4.96,
            "semester_taken": 1,
        }
    }
    assert semester_gpa(courses, progress, 1, config) == 5.0
    assert cumulative_gpa(courses, progress, config) == 5.0


def test_summer_term_does_not_trigger_academic_flags() -> None:
    flags = _flags(
        [_course("F", credits=30)],
        {"F": {"status": "failed", "grade_10": 1.0, "semester_taken": 2}},
        semester=2,
        profile={"is_summer_term": True},
    )
    assert not any(flags[f"W{index}"]["active"] for index in range(1, 5))
    assert all(
        flags[f"W{index}"]["calculation_status"] == "not_applicable_summer"
        for index in range(1, 5)
    )


def test_mandatory_retake_is_forced_only_when_offered_and_optimizer_hard_constraint() -> None:
    course = _course("RETAKE", offering_rule=["odd"])
    progress = {
        "RETAKE": {
            "status": "failed",
            "grade_10": 4.9,
            "attempt_count": 1,
            "semester_taken": 1,
        }
    }
    even = _evaluate([course], progress, semester=2)
    assert not even["forced_retakes"]
    assert any(
        reason["code"] == "NOT_OFFERED"
        for item in even["blocked_courses"]
        if item["course_key"] == "RETAKE"
        for reason in item["reasons"]
    )
    odd = _evaluate([course], progress, semester=3)
    assert odd["forced_retakes"] == [
        {
            "course_key": "RETAKE",
            "grade_10": 4.9,
            "must_register": True,
            "status": "CONFIRMED",
            "ref": "Đ11.1",
        }
    ]
    solution = optimize_plan(
        [
            {
                "course_id": "RETAKE",
                "credits": 3,
                "status": "failed",
                "must_register": True,
            }
        ],
        p_student=0.1,
        mean_credits=3,
        credit_limits={"cmin": 0, "cmax": 3, "regime": "TEST_FIXTURE"},
        prerequisites=[],
        progress={"RETAKE": {"status": "failed"}},
        beta=0,
        gamma=100,
        load_lambda=0,
    )
    assert solution["selected_course_ids"] == ["RETAKE"]


def test_mandatory_retake_threshold_uses_rounded_official_grade() -> None:
    course = _course("RETAKE", offering_rule=["odd"])
    result = _evaluate(
        [course],
        {
            "RETAKE": {
                "status": "failed",
                "grade_10": 4.96,
                "attempt_count": 1,
                "semester_taken": 1,
            }
        },
        semester=3,
    )
    assert result["forced_retakes"] == []


def test_evaluate_student_reports_warning_regime_and_forced_retake() -> None:
    courses = [
        _course(f"RETAKE-{index}", credits=5, offering_rule=["odd"])
        for index in range(5)
    ]
    progress = {
        course["course_id"]: {
            "status": "failed",
            "grade_10": 4.9,
            "attempt_count": 1,
            "semester_taken": 2,
        }
        for course in courses
    }
    result = _evaluate(
        courses,
        progress,
        semester=3,
        profile_updates={"last_completed_semester": 2},
    )
    flags = {flag["code"]: flag for flag in result["academic_flags"]}
    assert flags["W1"]["active"] is True
    assert flags["W2"]["active"] is True
    assert result["progress_stats"]["registration_credit_limits"]["regime"] == "WEAK_OR_POOR"
    assert (
        result["progress_stats"]["registration_credit_limits"]["cmin"],
        result["progress_stats"]["registration_credit_limits"]["cmax"],
    ) == (12, 18)
    assert len(result["forced_retakes"]) == 5
    assert all(item["must_register"] for item in result["forced_retakes"])


def test_failed_elective_reopens_slot_and_allows_alternative() -> None:
    courses = [
        _course("E-A", course_type="tự chọn", elective_slot="HP016"),
        _course("E-B", course_type="tự chọn", elective_slot="HP016"),
    ]
    result = _evaluate(
        courses,
        {"E-A": {"status": "failed", "grade_10": 4.0, "attempt_count": 1}},
    )
    eligible = {row["course_id"] for row in result["eligible_courses"]}
    assert {"E-A", "E-B"}.issubset(eligible)
    assert not result["forced_retakes"]


@pytest.mark.parametrize(
    ("grade", "ready"),
    [(5.49, False), (5.50, True)],
)
def test_graduation_gpa_boundary(grade: float, ready: bool) -> None:
    curriculum, profile = _required_graduation_profile(grade)
    result = evaluate_student(profile, curriculum, load_rules_config(), 8)
    assert result["progress_stats"]["credits_earned"] == 130
    assert result["progress_stats"]["graduation_conditions"]["cumulative_gpa"]["value"] == grade
    assert result["progress_stats"]["graduation_ready"] is ready


def test_graduation_requires_all_learning_outcomes() -> None:
    curriculum, profile = _required_graduation_profile(5.5)
    profile["graduation_outcomes"]["qpan"] = False
    result = evaluate_student(profile, curriculum, load_rules_config(), 8)
    assert result["progress_stats"]["graduation_conditions"]["learning_outcomes"]["status"] == "NOT_MET"
    assert result["progress_stats"]["graduation_ready"] is False


def test_honors_repeat_credit_indicator_uses_strict_five_percent_boundary() -> None:
    course = _course("REPEATED", credits=3)
    below = _evaluate(
        [course],
        {"REPEATED": {"status": "completed", "grade_10": 7, "attempt_count": 3}},
    )
    assert below["progress_stats"]["retake_credits_total"] == 6
    assert below["progress_stats"]["honors_downgrade_risk"] is False
    above = _evaluate(
        [course],
        {"REPEATED": {"status": "completed", "grade_10": 7, "attempt_count": 4}},
    )
    assert above["progress_stats"]["retake_credits_total"] == 9
    assert above["progress_stats"]["honors_downgrade_risk"] is True
    assert any(flag["code"] == "HONORS_DOWNGRADE_RISK" for flag in above["edge_case_flags"])
