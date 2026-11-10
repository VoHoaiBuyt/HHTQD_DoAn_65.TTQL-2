from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.view_data import (
    PAGE_KEYS,
    build_page_data,
    build_plans_data,
    build_simulation_data,
    list_scenarios,
    options_cache_key,
    progress_override_from_rows,
)
from core.run_dss import clear_dss_cache, run_dss

TEST_FIXTURE = "TEST_FIXTURE"
run_dss_module = import_module("core.run_dss")


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
    assert "An toàn" not in plan["display_label"]


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
    from app.view_data import build_simulation_data

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
    monkeypatch.setattr("app.view_data.MC_GRAD_HIST_PATH", missing_path)
    simulation = build_simulation_data(result)
    assert simulation["available"] is True
    assert simulation["grad_hist"] is None


def test_apptest_missing_histogram_displays_no_reconstruction_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "app.view_data.MC_GRAD_HIST_PATH",
        tmp_path / "missing_mc_grad_hist.csv",
    )
    app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    app.sidebar.radio[0].set_value(app.sidebar.radio[0].options[5])
    app.run()
    assert not app.exception
    assert any("Không có `mc_grad_hist.csv`" in info.value for info in app.info)


@pytest.mark.parametrize("page", PAGE_KEYS)
def test_apptest_all_pages_for_every_scenario(page: str) -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    scenarios = list_scenarios()
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    assert not app.exception

    for scenario in scenarios:
        app.sidebar.selectbox[0].set_value(scenario["student_id"])
        app.sidebar.radio[0].set_value(page)
        app.run()
        assert not app.exception, (
            f"AppTest exception for {scenario['student_id']} × {page}: "
            f"{[error.message for error in app.exception]}"
        )
        assert app.sidebar.selectbox[0].value == scenario["student_id"]
        assert any("Nhãn nguồn:" in caption.value for caption in app.caption), (
            f"Missing source badge for {scenario['student_id']} × {page}"
        )
        if page == "Nguy cơ & cảnh báo" and scenario["ml_scope"] != "T1_valid":
            assert any("ML tắt" in warning.value for warning in app.warning)
        if page == "Mô phỏng":
            policy_multiselect = next(
                widget for widget in app.multiselect if widget.label == "Chính sách hiển thị"
            )
            assert policy_multiselect.value == (
                ["ILP-matched"]
                if "ILP-matched" in policy_multiselect.options
                else [policy_multiselect.options[0]]
            )
        if page == "Phương án đăng ký" and scenario["student_id"] in {
            "V2-005",
            "V2-007",
        }:
            assert any("cố vấn học tập" in error.value for error in app.error)


def test_apptest_ml_disabled_no_plan_final_term_and_invalid_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    profile_selector = app.sidebar.selectbox[0]
    page_selector = app.sidebar.radio[0]

    profile_selector.set_value("V2-005")
    page_selector.set_value("Nguy cơ & cảnh báo")
    app.run()
    assert not app.exception
    assert any("ML tắt" in warning.value for warning in app.warning)

    profile_selector = app.sidebar.selectbox[0]
    page_selector = app.sidebar.radio[0]
    profile_selector.set_value("V2-008")
    page_selector.set_value("Phương án đăng ký")
    app.run()
    assert not app.exception
    assert any("graduation_ready" in caption.value for caption in app.caption)

    profile_selector = app.sidebar.selectbox[0]
    page_selector = app.sidebar.radio[0]
    profile_selector.set_value("V2-001")
    page_selector.set_value("Hồ sơ & tiến độ")
    app.run()
    progress_editor = next(
        frame
        for frame in app.dataframe
        if frame.key == "progress_editor_V2-001"
    )
    completed_row = progress_editor.value.index[
        progress_editor.value["status"].eq("completed")
    ][0]
    app.session_state["progress_editor_V2-001"] = {
        "edited_rows": {int(completed_row): {"grade_10": 4.9}},
        "added_rows": [],
        "deleted_rows": [],
    }
    app.run()
    assert not app.exception
    assert any("chưa nhất quán" in error.value for error in app.error)


def test_apptest_reports_empty_plan_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_run_dss = run_dss_module.run_dss

    def run_without_plans(student_id, options=None):
        result = original_run_dss(student_id, options)
        result["plans"] = []
        return result

    monkeypatch.setattr(run_dss_module, "run_dss", run_without_plans)
    st.cache_data.clear()
    app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    app.sidebar.radio[0].set_value("Phương án đăng ký")
    app.run()
    assert not app.exception
    assert any("Core không trả phương án đăng ký" in warning.value for warning in app.warning)


@pytest.mark.parametrize(
    "status",
    ["best_effort", "regulatory_conflict", "risk_cap_exceeded"],
)
def test_apptest_risky_statuses_show_advisor_callout(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    original_run_dss = run_dss_module.run_dss

    def run_with_risky_status(student_id, options=None):
        result = original_run_dss(student_id, options)
        result["plans"][0]["status"] = status
        return result

    monkeypatch.setattr(run_dss_module, "run_dss", run_with_risky_status)
    st.cache_data.clear()
    app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    app.sidebar.radio[0].set_value("Phương án đăng ký")
    app.run()
    assert not app.exception
    assert any("cố vấn học tập" in error.value for error in app.error)


def test_apptest_does_not_leak_previous_profile_content() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    app.sidebar.radio[0].set_value("Hồ sơ & tiến độ")
    app.sidebar.selectbox[0].set_value("V2-001")
    app.run()
    app.sidebar.selectbox[0].set_value("V2-005")
    app.run()
    assert not app.exception
    rendered = "\n".join(str(element.value) for element in app.markdown)
    assert "V2-005" in rendered
    assert "V2-001" not in rendered
