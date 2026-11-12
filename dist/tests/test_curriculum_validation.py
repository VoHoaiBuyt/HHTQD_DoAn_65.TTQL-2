from __future__ import annotations

from core.curriculum import (
    load_curriculum,
    load_enrichment_config,
    load_program_config,
)
from core.curriculum_validation import validate_curriculum


def test_official_course_ids_and_program_credit_paths() -> None:
    curriculum = load_curriculum()
    result = validate_curriculum(
        curriculum["courses"],
        curriculum["prerequisites"],
        load_enrichment_config(),
        load_program_config(),
    )
    assert result["n_fail"] == 0
    assert result["summary"]["course_counts"]["total_rows"] == 101
    assert result["summary"]["course_counts"]["course_type"] == {
        "bắt buộc": 54,
        "tự chọn": 47,
    }
    for totals in result["summary"]["semester_credits_by_specialization"].values():
        assert totals["mandatory"] == [17, 15, 17, 13, 11, 15, 12, 10]
        assert totals["elective"] == [0, 2, 2, 5, 5, 3, 3, 0]
        assert totals["total"] == 130


def test_unconfirmed_assumptions_are_explicit() -> None:
    result = validate_curriculum(
        load_curriculum()["courses"],
        load_curriculum()["prerequisites"],
        load_enrichment_config(),
        load_program_config(),
    )
    check_ids = {row["id"]: row for row in result["checks"]}
    assert check_ids["prerequisite_completeness_confirmed"]["status"] == "WARN"
    assert "unconfirmed" in check_ids["prerequisite_completeness_confirmed"]["message"]
    assert check_ids["course_code_source_confirmation"]["status"] == "WARN"
    assert result["n_checks"] == result["n_pass"] + result["n_warn"] + result["n_fail"]
