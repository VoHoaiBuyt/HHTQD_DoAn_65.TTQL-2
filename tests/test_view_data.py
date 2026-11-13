from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from core.risk_labels import PLAN_DISPLAY_LABELS
from core.run_dss import clear_dss_cache, run_dss
from core.view_data import (
    PAGE_KEYS,
    build_page_data,
    build_plans_data,
    build_simulation_data,
    list_scenarios,
    options_cache_key,
    progress_override_from_rows,
)

TEST_FIXTURE = "TEST_FIXTURE"


def test_all_page_data_builders_smoke_for_available_scenarios() -> None:
    clear_dss_cache()
    scenarios = list_scenarios()
    assert scenarios
    for scenario in scenarios:
        result = run_dss(scenario["student_id"])
        for page in PAGE_KEYS:
            data = build_page_data(page, result)
            assert isinstance(data, dict)
        assert build_page_data("Hồ sơ & tiến độ", result)["student"]["student_id"] == scenario["student_id"]
        assert build_page_data("Nguy cơ & cảnh báo", result)["enabled"] == (
            scenario["ml_scope"] == "T1_valid" and result["risk"] is not None
        )
        simulation = build_page_data("Mô phỏng", result)
        assert simulation["available"] is True
        assert set(simulation["results"]["policy"]) == set(
            simulation["available_policies"]
        )
        assert simulation["results"]["n_runs"].gt(0).all()
        assert simulation["results"]["lambda"].nunique() == 1
        assert simulation["selected_lambda"] in simulation["available_lambdas"]
        assert len(simulation["pairwise"]) == len(simulation["available_comparisons"])
        assert set(simulation["pareto"]["dominance"]) == set(
            simulation["pareto_labels"]
        )


def test_app_cache_key_normalizes_options_without_sharing_profiles() -> None:
    assert options_cache_key({"lambda": 0.1, "budget": 18}) == options_cache_key(
        {"budget": 18, "lambda": 0.1}
    )
    first = run_dss("V2-001", {"include_plans": False})
    second = run_dss("V2-005", {"include_plans": False})
    first["progress"]["by_course"]["POL307"]["status"] = "failed"
    assert second["profile_summary"]["student_id"] == "V2-005"
    assert run_dss("V2-001", {"include_plans": False})["progress"]["by_course"]["POL307"]["status"] != "failed"


def test_progress_editor_rejects_inconsistent_status_and_grade() -> None:
    try:
        progress_override_from_rows(
            [
                {
                    "course_id": f"{TEST_FIXTURE}-COURSE",
                    "status": "completed",
                    "grade_10": 4.9,
                    "attempt_count": 1,
                    "semester_taken": 1,
                }
            ]
        )
    except ValueError as error:
        assert "điểm từ 5,0" in str(error)
    else:
        raise AssertionError("Inconsistent status/grade should be rejected.")


def test_problem_plan_status_is_red_flagged_without_safe_label() -> None:
    result = run_dss("V2-001")
    test_result = deepcopy(result)
    test_result["plans"][0]["status"] = "best_effort"
    plan = build_plans_data(test_result)["plans"][0]
    assert plan["needs_advisor"] is True
    assert plan["display_label"] == PLAN_DISPLAY_LABELS["risk_focused"]


@pytest.mark.parametrize(
    "status",
    ["best_effort", "regulatory_conflict", "risk_cap_exceeded"],
)
def test_all_risky_plan_statuses_require_advisor(status: str) -> None:
    result = run_dss("V2-001")
    test_result = deepcopy(result)
    test_result["plans"][0]["status"] = status
    plan = build_plans_data(test_result)["plans"][0]
    assert plan["needs_advisor"] is True


def test_simulation_data_filters_all_mc_tables_to_requested_lambda() -> None:
    result = run_dss("V2-001", {"include_plans": False})
    simulation = build_page_data("Mô phỏng", result)
    lambdas = simulation["available_lambdas"]
    assert len(lambdas) >= 1
    selected = build_page_data("Mô phỏng", result)
    assert selected["results"]["lambda"].nunique() == 1

    for load_lambda in lambdas:
        filtered = build_simulation_data(result, load_lambda=load_lambda)
        assert filtered["available"] is True
        assert filtered["results"]["lambda"].eq(load_lambda).all()
        assert filtered["pairwise"]["lambda"].eq(load_lambda).all()
        assert filtered["pareto"]["lambda"].eq(load_lambda).all()


def test_missing_graduation_histogram_is_reported_without_reconstruction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = run_dss("V2-001", {"include_plans": False})
    missing_path = tmp_path / "missing_mc_grad_hist.csv"
    monkeypatch.setattr("core.view_data.MC_GRAD_HIST_PATH", missing_path)
    simulation = build_simulation_data(result)
    assert simulation["available"] is True
    assert simulation["grad_hist"] is None
