from __future__ import annotations

import numpy as np

import core.simulation as simulation
from core.run_dss import clear_dss_cache, run_dss
from core.scenario_v2 import generate_scenario_rows
from core.simulation import (
    MAX_ATTEMPTS_PER_COURSE,
    MAX_SEMESTERS,
    _validate_selected,
    common_random_matrix,
    compute_p_pass,
    evaluate_pareto_dominance,
    select_policy_courses,
    simulate_student_trajectory,
    wilson_score_interval,
    warning_streak,
)


TEST_FIXTURE = "TEST_FIXTURE"


def test_run_dss_returns_schema_and_isolates_sequential_profiles() -> None:
    clear_dss_cache()
    first = run_dss("V2-001", {"include_plans": False})
    first["progress"]["by_course"]["POL307"]["status"] = "failed"
    second = run_dss("V2-005", {"include_plans": False})
    first_again = run_dss("V2-001", {"include_plans": False})

    assert set(first_again) == {
        "profile_summary",
        "risk",
        "risk_reason",
        "credit_regime",
        "academic_flags",
        "progress",
        "eligible",
        "blocked",
        "forced_retakes",
        "plans",
        "pareto_points",
        "status",
        "warnings",
        "provenance",
    }
    assert first_again["progress"]["by_course"]["POL307"]["status"] != "failed"
    assert first_again["progress"]["stats"]["credits_earned"] == 17
    assert second["progress"]["stats"]["credits_earned"] == 63
    assert first_again["risk"] is not None
    assert second["risk"] is None
    assert second["risk_reason"]


def test_run_dss_full_three_plan_schema_and_cache_options() -> None:
    clear_dss_cache()
    result = run_dss("V2-003", {"scenario_set": [12, 15, 18], "lambda": 0.1})
    repeat = run_dss("V2-003", {"scenario_set": (12, 15, 18), "lambda": 0.1})
    different = run_dss("V2-003", {"scenario_set": [12], "lambda": 0.3})
    assert [plan["plan_type"] for plan in result["plans"]] == [
        "risk_focused",
        "balanced",
        "acceleration",
    ]
    assert result == repeat
    assert len(different["plans"]) == 3
    assert result["credit_regime"]["regime"] == "WEAK_OR_POOR"
    assert result["provenance"]["progress"]["label"] == "SCENARIO"


def test_run_dss_handles_all_scenario_v2_profiles() -> None:
    profiles, _, _ = generate_scenario_rows()
    clear_dss_cache()
    for profile in profiles:
        result = run_dss(profile["student_id"], {"include_plans": False})
        assert result["profile_summary"]["student_id"] == profile["student_id"]
        assert result["profile_summary"]["specialization"] == "NW"
        assert len(result["progress"]["by_course"]) == 101
        assert isinstance(result["academic_flags"], list)
        assert isinstance(result["eligible"], list)
        assert isinstance(result["blocked"], list)
        assert isinstance(result["forced_retakes"], list)
        assert result["plans"] == []


def test_common_random_numbers_and_probability_are_seeded() -> None:
    first = common_random_matrix(seed=20261108, run_index=4, n_courses=101)
    second = common_random_matrix(seed=20261108, run_index=4, n_courses=101)
    assert first.shape == (MAX_SEMESTERS, 101, MAX_ATTEMPTS_PER_COURSE)
    assert np.array_equal(first, second)
    probability = compute_p_pass(0.7, 15, 3, 0.0, False, 1)
    assert probability == 0.7
    sample = np.random.default_rng(82).random(100000)
    assert abs(float(np.mean(sample < probability)) - probability) < 0.01


def test_pareto_reports_both_directions_tradeoffs_and_indistinguishable() -> None:
    assert evaluate_pareto_dominance(
        {"p8": (0.1, 0.05, 0.15)}, ["p8"], []
    ) == "ILP vượt trội"
    assert evaluate_pareto_dominance(
        {"p8": (-0.1, -0.15, -0.05)}, ["p8"], []
    ) == "ILP bị vượt trội"
    assert evaluate_pareto_dominance(
        {"p8": (0.1, 0.05, 0.15), "fails": (0.2, 0.1, 0.25)},
        ["p8"],
        ["fails"],
    ) == "đánh đổi"
    assert evaluate_pareto_dominance(
        {"p8": (0.0, -0.01, 0.01)}, ["p8"], []
    ) == "chưa phân biệt"


def test_ilp_cache_key_distinguishes_planner_lambda() -> None:
    candidates = [
        {
            "course_id": "TEST_FIXTURE-COURSE",
            "credits": 3,
            "planned_semester": 1,
            "status": "not_taken",
            "elective_slot": None,
            "source_label": TEST_FIXTURE,
        }
    ]
    args = (
        "ILP-fixed",
        candidates,
        {"cmin": 0, "cmax": 15, "regime": TEST_FIXTURE},
        0.8,
        3.0,
        0.1,
        [],
        {},
        {},
    )
    cache: dict[object, tuple[list[str], str]] = {}
    first_plan = {
        "plans": [
            {"plan_type": "balanced", "status": "best_effort", "selected_course_ids": []}
        ]
    }
    second_plan = {
        "plans": [
            {
                "plan_type": "balanced",
                "status": "optimal",
                "selected_course_ids": ["TEST_FIXTURE-COURSE"],
            }
        ]
    }
    first = select_policy_courses(
        *args, cache, dss_result=first_plan, planner_lambda=0.1
    )
    repeated = select_policy_courses(
        *args, cache, dss_result=first_plan, planner_lambda=0.1
    )
    changed = select_policy_courses(
        *args, cache, dss_result=second_plan, planner_lambda=0.3
    )
    assert first == repeated == ([], "best_effort")
    assert changed == (["TEST_FIXTURE-COURSE"], "optimal")


def test_simulation_uses_previous_simulated_term_gpa_for_next_regime(
    monkeypatch,
) -> None:
    profiles, _, metadata = generate_scenario_rows()
    profile = next(row for row in profiles if row["student_id"] == "V2-001")
    courses = metadata["curriculum"]["courses"]
    indexes = {str(row["course_id"]): index for index, row in enumerate(courses)}
    original_run_dss = simulation.run_dss
    seen_gpa: dict[int, float | None] = {}

    def recording_run_dss(student_id, options=None):
        opts = options or {}
        override = opts.get("profile_override", {})
        target = opts.get("target_semester")
        if target is not None and not opts.get("include_plans", False):
            seen_gpa[int(target)] = override.get("registration_previous_semester_gpa")
        return original_run_dss(student_id, options)

    monkeypatch.setattr(simulation, "run_dss", recording_run_dss)
    all_passes = np.zeros(
        (MAX_SEMESTERS, len(courses), MAX_ATTEMPTS_PER_COURSE),
        dtype=float,
    )
    simulate_student_trajectory(
        metadata["scenario_records"]["V2-001"],
        profile,
        "B1",
        0.1,
        metadata["curriculum"],
        metadata["rules_config"],
        metadata["slot_credits"],
        all_passes,
        indexes,
        {},
    )
    assert 2 in seen_gpa and 3 in seen_gpa
    assert seen_gpa[2] == profile["previous_semester_gpa"]
    assert seen_gpa[3] == 7.0


def test_identical_matched_and_fixed_plans_have_identical_crn_outcomes() -> None:
    profiles, _, metadata = generate_scenario_rows()
    profile = next(row for row in profiles if row["student_id"] == "V2-001")
    curriculum = metadata["curriculum"]
    courses = curriculum["courses"]
    indexes = {str(row["course_id"]): index for index, row in enumerate(courses)}
    draws = common_random_matrix(seed=20261108, run_index=0, n_courses=len(courses))
    results = [
        simulate_student_trajectory(
            metadata["scenario_records"]["V2-001"],
            profile,
            policy,
            0.1,
            curriculum,
            metadata["rules_config"],
            metadata["slot_credits"],
            draws,
            indexes,
            {},
            planner_lambda=0.1,
        )
        for policy in ("ILP-matched", "ILP-fixed")
    ]
    assert results[0] == results[1]


def test_warning_streak_forces_withdrawal_only_on_third_consecutive_warning() -> None:
    count, expelled = warning_streak(0, True, False)
    assert (count, expelled) == (1, False)
    count, expelled = warning_streak(count, False, True)
    assert (count, expelled) == (2, False)
    count, expelled = warning_streak(count, True, True)
    assert (count, expelled) == (3, True)
    assert warning_streak(count, False, False) == (0, False)


def test_wilson_interval_has_exact_probability_boundaries() -> None:
    assert wilson_score_interval(0, 1000)[0] == 0.0
    assert wilson_score_interval(1000, 1000)[1] == 1.0


def test_baseline_policies_obey_caps_corequisites_and_forced_retake() -> None:
    candidates = [
        {
            "course_id": "DEP",
            "credits": 3,
            "planned_semester": 1,
            "status": "not_taken",
            "elective_slot": None,
            "source_label": TEST_FIXTURE,
        },
        {
            "course_id": "COREQ",
            "credits": 3,
            "planned_semester": 2,
            "status": "not_taken",
            "elective_slot": None,
            "source_label": TEST_FIXTURE,
        },
        {
            "course_id": "RETAKE",
            "credits": 3,
            "planned_semester": 1,
            "status": "failed",
            "attempt_count": 1,
            "must_register": True,
            "elective_slot": None,
            "source_label": TEST_FIXTURE,
        },
    ]
    relation = [
        {
            "course_id": "DEP",
            "prerequisite_id": "COREQ",
            "type": "song hành",
            "source_label": TEST_FIXTURE,
        }
    ]
    limits = {"cmin": 0, "cmax": 6, "regime": TEST_FIXTURE}
    for policy in ("B1", "B2", "B3"):
        selected, status = select_policy_courses(
            policy,
            candidates,
            limits,
            0.7,
            3,
            0.1,
            relation,
            {"RETAKE": {"status": "failed", "attempt_count": 1}},
            {},
            {},
        )
        assert "RETAKE" in selected
        assert status == "optimal"
        _validate_selected(
            selected,
            candidates,
            {"RETAKE": {"status": "failed", "attempt_count": 1}},
            relation,
            limits,
        )
        if "DEP" in selected:
            assert "COREQ" in selected


def test_forced_retake_capacity_conflict_is_reported() -> None:
    candidates = [
        {
            "course_id": course_id,
            "credits": 3,
            "planned_semester": 1,
            "status": "failed",
            "attempt_count": 1,
            "must_register": True,
            "elective_slot": None,
            "source_label": TEST_FIXTURE,
        }
        for course_id in ("R1", "R2")
    ]
    selected, status = select_policy_courses(
        "B1",
        candidates,
        {"cmin": 0, "cmax": 3, "regime": TEST_FIXTURE},
        0.7,
        3,
        0.1,
        [],
        {course_id: {"status": "failed", "attempt_count": 1} for course_id in ("R1", "R2")},
        {},
        {},
    )
    assert len(selected) == 1
    assert status == "regulatory_conflict"


def test_simulation_is_deterministic_and_third_warning_stops_trajectory() -> None:
    profiles, _, metadata = generate_scenario_rows()
    profile = next(row for row in profiles if row["student_id"] == "V2-001")
    courses = metadata["curriculum"]["courses"]
    indexes = {str(row["course_id"]): index for index, row in enumerate(courses)}
    all_failures = np.ones(
        (MAX_SEMESTERS, len(courses), MAX_ATTEMPTS_PER_COURSE),
        dtype=float,
    )

    def run() -> dict[str, float | int]:
        return simulate_student_trajectory(
            metadata["scenario_records"]["V2-001"],
            profile,
            "B1",
            0.1,
            metadata["curriculum"],
            metadata["rules_config"],
            metadata["slot_credits"],
            all_failures,
            indexes,
            {},
        )

    first = run()
    second = run()
    assert first == second
    assert first["expelled_regulatory"] == 1
    assert first["graduated_16"] == 0
