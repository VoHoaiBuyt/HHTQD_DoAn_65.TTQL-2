from __future__ import annotations

from core.scenario_v2 import (
    _rule_examples,
    generate_scenario_rows,
    validate_scenario_v2,
)


def test_scenario_v2_contains_complete_official_progress_and_130_credit_balance() -> None:
    profiles, progress, metadata = generate_scenario_rows(seed=20261105)
    validation = validate_scenario_v2(profiles, progress, metadata)
    assert validation["status"] == "PASS"
    assert validation["n_profiles"] == 9
    assert validation["n_progress_rows"] == 9 * 101
    assert validation["n_errors"] == 0
    assert all(
        row["credits_earned"] + row["credits_remaining"] == 130
        for row in validation["students"]
    )
    assert all(profile["source_label"] == "SCENARIO" for profile in profiles)
    assert all(
        profile["feature_source_label"] == "REAL (UCI-697)"
        for profile in profiles
    )


def test_t1_profiles_have_computed_gpa_and_probabilities_from_model_api() -> None:
    profiles, _, _ = generate_scenario_rows(seed=20261105)
    by_id = {profile["student_id"]: profile for profile in profiles}
    assert all(
        by_id[f"V2-00{index}"]["ml_scope"] == "T1_valid"
        for index in range(1, 5)
    )
    assert by_id["V2-003"]["previous_semester_gpa"] < 5
    assert by_id["V2-003"]["p_student_pass"] is not None
    assert by_id["V2-004"]["previous_semester_gpa"] == 5
    assert all(profile["gpa"] is not None for profile in profiles)


def test_scenario_edge_cases_retain_prerequisite_and_elective_evidence() -> None:
    profiles, _, metadata = generate_scenario_rows(seed=20261105)
    records = metadata["scenario_records"]
    failed_ids = {
        course_id
        for course_id, progress in records["V2-005"]["progress"].items()
        if progress["status"] == "failed"
    }
    assert records["V2-005"]["current_debt_credits"] == 24
    assert "POL307" in {
        course_id
        for course_id, progress in records["V2-003"]["progress"].items()
        if progress["status"] == "failed"
    }
    assert "HP024" in {
        course_id
        for course_id, progress in records["V2-006"]["progress"].items()
        if progress["status"] == "failed"
    }
    assert "HP037" in {
        course_id
        for course_id, progress in records["V2-007"]["progress"].items()
        if progress["status"] == "failed"
    }
    assert len(failed_ids) >= 5

    examples = _rule_examples(profiles, metadata)
    assert {
        "HP029",
        "HP039-NW",
        "HP040-NW",
        "HP041-NW",
        "HP042-NW",
        "HP044-NW",
    }.issubset(set(examples["hp024_blocked_chain"]["blocked_course_ids"]))
    assert examples["failed_elective_slot_reopened"]["eligible_alternatives"]
    assert examples["w1_boundary_scenario"]["current_debt_credits"] == 24
    assert examples["w1_boundary_scenario"]["active"] is False
    assert examples["final_semester_cases"]["B_completion_plan"]["status"] == "final_semester_plan"
    assert examples["credit_regime_comparison_same_profile"]["WEAK_OR_POOR"]["cmin"] == 12
    assert examples["credit_regime_comparison_same_profile"]["NORMAL"]["cmin"] == 15
