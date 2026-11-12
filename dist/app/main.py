from __future__ import annotations

import json
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from app.view_data import (
    MC_INTERPRETATION_PATH,
    PAGE_KEYS,
    build_courses_data,
    build_plans_data,
    build_profile_data,
    build_provenance_data,
    build_risk_data,
    build_simulation_data,
    build_what_if_data,
    list_scenarios,
    normalize_options,
    options_cache_key,
    progress_override_from_rows,
)
from app.risk_labels import RISK_THRESHOLD_NOTE
from core.run_dss import run_dss


@st.cache_data(show_spinner=False)
def _cached_dss(student_id: str, canonical_options: str) -> dict[str, Any]:
    options = json.loads(canonical_options)
    if options.get("risk_cap_mode") is None:
        options.pop("risk_cap_mode")
    return run_dss(student_id, options)


def _run(student_id: str, options: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_options(options)
    return _cached_dss(student_id, options_cache_key(normalized))


def _format(value: Any, suffix: str = "") -> str:
    if value is None or value == "UNKNOWN":
        return "UNKNOWN"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def _format_probability(value: Any) -> str:
    if value is None or value == "UNKNOWN":
        return "UNKNOWN"
    return f"{float(value):.1%}"


def _source_badge(label: str) -> None:
    st.caption(f"**Nhãn nguồn:** `{label}`")


def _base_progress_override(student_id: str) -> dict[str, dict[str, Any]]:
    stored = st.session_state.get("progress_overrides", {})
    return stored.get(student_id, {})


def _render_profile(result: dict[str, Any], student_id: str) -> None:
    data = build_profile_data(result)
    student = data["student"]
    stats = data["stats"]
    st.subheader(f"{student['persona'] or 'Hồ sơ'} · {student_id}")
    st.write(
        f"Kịch bản: **{student_id}** · Ngành/chuyên ngành: "
        f"**{student.get('specialization', 'UNKNOWN')}** · "
        f"Kỳ gần nhất hoàn tất: **{student.get('last_completed_semester', 'UNKNOWN')}**"
    )
    _source_badge("SCENARIO")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Tín chỉ tích lũy", _format(stats["credits_earned"]), "SCENARIO")
    metric_cols[1].metric("Còn thiếu", _format(stats["credits_remaining"]), "OFFICIAL (NTU)")
    metric_cols[2].metric("TBHK kỳ liền trước", _format(data["previous_semester_gpa"]), "SCENARIO")
    metric_cols[3].metric("TBTCL", _format(stats.get("cumulative_gpa_10")), "SCENARIO")
    metric_cols[4].metric("Năm trình độ", _format(data["study_year"]), "OFFICIAL (NTU)")

    st.markdown("**Tiến độ ô tự chọn**")
    missing_slots = stats.get("elective_slots_remaining", [])
    st.write(
        "Ô còn thiếu: " + (", ".join(missing_slots) if missing_slots else "Không còn ô thiếu.")
    )
    st.caption(
        f"Tín chỉ tự chọn còn thiếu: {_format(stats.get('elective_credits_remaining'))} · "
        f"Số kỳ tối thiểu còn lại: {_format(stats.get('minimum_semesters_remaining'))}"
    )
    _source_badge("OFFICIAL (NTU) + GIẢ ĐỊNH (suy từ CTĐT)")

    st.markdown("**Bảng học phần**")
    rows = data["progress_rows"]
    frame = pd.DataFrame(rows)
    if frame.empty:
        st.info("Không có dữ liệu học phần.")
        return
    editable = frame[["course_id", "status", "grade_10", "attempt_count", "semester_taken"]].copy()
    editor_key = f"progress_editor_{student_id}"
    changed = st.data_editor(
        editable,
        key=editor_key,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        column_config={
            "course_id": st.column_config.TextColumn("Mã học phần", disabled=True),
            "status": st.column_config.SelectboxColumn(
                "Trạng thái",
                options=["completed", "failed", "in_progress", "not_taken"],
                required=True,
            ),
            "grade_10": st.column_config.NumberColumn(
                "Điểm / 10", min_value=0.0, max_value=10.0, step=0.1
            ),
            "attempt_count": st.column_config.NumberColumn("Số lần học", disabled=True),
            "semester_taken": st.column_config.NumberColumn("Học kỳ", disabled=True),
        },
    )
    try:
        changed_override = progress_override_from_rows(changed.to_dict("records"))
        base_override = progress_override_from_rows(editable.to_dict("records"))
    except (TypeError, ValueError) as error:
        st.error(f"Dữ liệu chỉnh sửa chưa nhất quán: {error}")
        return
    if changed_override != base_override:
        overrides = dict(st.session_state.get("progress_overrides", {}))
        overrides[student_id] = changed_override
        st.session_state["progress_overrides"] = overrides
        st.success("Đã kiểm tra trạng thái/điểm. Đang tính lại tiến độ, điều kiện và phương án.")
        st.rerun()


def _render_risk(result: dict[str, Any]) -> None:
    data = build_risk_data(result)
    st.subheader("Nguy cơ & cảnh báo")
    if data["enabled"]:
        risk = data["risk"]
        st.info("Ước lượng dựa trên kết quả học kỳ 1, hợp lệ ở mốc T1.")
        col1, col2, col3 = st.columns(3)
        col1.metric("P(Dropout)", f"{risk['p_dropout_calibrated']:.1%}", "REAL (UCI-697)")
        col2.metric("Tầng cảnh báo", risk["warning_tier"], "REAL (UCI-697)")
        col3.metric("Ngưỡng mô hình", f"{risk['threshold_used']:.3f}", "REAL (UCI-697)")
        shap_rows = sorted(
            risk.get("shap_values", []),
            key=lambda row: abs(float(row.get("value", 0))),
            reverse=True,
        )[:15]
        if shap_rows:
            st.markdown("**SHAP cục bộ**")
            shap_frame = pd.DataFrame(shap_rows).set_index("feature")
            st.bar_chart(shap_frame)
            _source_badge("REAL (UCI-697)")
            st.caption("Giải thích mô hình, không phải nguyên nhân.")
        st.caption(
            f"Phiên bản mô hình: {risk.get('model_version', 'UNKNOWN')} · "
            f"scope: {result['profile_summary']['ml_scope']}"
        )
        st.caption("Ước lượng khám phá từ UCI-697; chưa được xác thực trên sinh viên NTU.")
    else:
        st.warning(f"ML tắt — {data['reason']}")
        st.caption("Không hiển thị P(Dropout), tầng cảnh báo hoặc SHAP ngoài phạm vi T1.")

    st.markdown("**Cờ học vụ W1–W4**")
    flags = [flag for flag in data["flags"] if flag.get("code") in {"W1", "W2", "W3", "W4"}]
    if flags:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Cờ": flag.get("code"),
                        "Đang kích hoạt": flag.get("active", "UNKNOWN"),
                        "Giá trị": flag.get("value", "UNKNOWN"),
                        "Ngưỡng": flag.get("threshold", "UNKNOWN"),
                        "Đơn vị": flag.get("unit", ""),
                        "Điều": flag.get("ref", "UNKNOWN"),
                        "Trạng thái tính": flag.get("calculation_status", "UNKNOWN"),
                    }
                    for flag in flags
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Core không trả cờ W1–W4 cho hồ sơ này.")
    count = data["consecutive_warning_count"]
    st.metric("Số lần cảnh báo liên tiếp", _format(count), "OFFICIAL (NTU)")
    _source_badge("OFFICIAL (NTU)")
    other_flags = [flag for flag in data["flags"] if flag.get("code") not in {"W1", "W2", "W3", "W4"}]
    if other_flags:
        with st.expander("Cờ/giới hạn bổ sung"):
            st.dataframe(pd.DataFrame(other_flags), hide_index=True, width="stretch")


def _render_courses(result: dict[str, Any]) -> None:
    data = build_courses_data(result)
    st.subheader("Học phần")
    st.markdown(f"**Đủ điều kiện ({len(data['eligible'])})**")
    if data["eligible"]:
        st.dataframe(
            pd.DataFrame(data["eligible"]),
            hide_index=True,
            width="stretch",
        )
    st.markdown(f"**Môn còn nợ ({len(data['debts'])}); cột bắt buộc theo Đ11**")
    if data["debts"]:
        st.dataframe(pd.DataFrame(data["debts"]), hide_index=True, width="stretch")
    else:
        st.info("Không có môn ở trạng thái trượt trong hồ sơ.")
    st.markdown(f"**Bị chặn ({len(data['blocked'])})**")
    if data["blocked"]:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Mã học phần": row.get("course_key"),
                        "Lý do / tiên quyết": row.get("reason_text", "UNKNOWN"),
                    }
                    for row in data["blocked"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    _source_badge("OFFICIAL (NTU)")
    st.caption("Lịch mở môn và phần làm giàu CTĐT có nhãn GIẢ ĐỊNH (suy từ CTĐT).")


def _render_plan_cards(data: dict[str, Any]) -> None:
    plans = data["plans"]
    st.info(
        "Trạng thái `optimal` chỉ có nghĩa nghiệm tối ưu theo hàm mục tiêu và các "
        "ràng buộc đã mô hình hóa; không đồng nghĩa với phương án phù hợp nhất về mặt học vụ."
    )
    st.caption(RISK_THRESHOLD_NOTE)
    columns = st.columns(max(1, len(plans)))
    for index, plan in enumerate(plans):
        with columns[index]:
            st.markdown(f"### {plan['display_label']}")
            if plan["risk_level"] == "CAO":
                st.error(
                    "Mức cảnh báo rủi ro: CAO — khuyến nghị trao đổi với cố vấn học tập."
                )
            else:
                st.caption(f"Mức cảnh báo rủi ro: {plan['risk_level']}")
            status = str(plan.get("status", "UNKNOWN"))
            if plan["status_needs_advisor"]:
                st.error(
                    f"Trạng thái `{status}` — kết quả có rủi ro/giới hạn. "
                    "Khuyến nghị gặp cố vấn học tập."
                )
            else:
                st.caption(f"Trạng thái: `{status}`")
            st.metric("Tín chỉ đăng ký", _format(plan.get("selected_credits")), "GIẢ ĐỊNH")
            st.metric("Tín chỉ đạt kỳ vọng", _format(plan.get("expected_credits_passed")), "GIẢ ĐỊNH")
            st.metric("Môn trượt kỳ vọng", _format(plan.get("expected_failed_courses")), "GIẢ ĐỊNH")
            st.metric("P(≥1 trượt)", _format_probability(plan.get("p_at_least_one_failure")), "GIẢ ĐỊNH")
            st.caption(
                f"p_warning W1: {_format_probability(plan.get('p_warning_W1'))} · "
                f"W2: {_format_probability(plan.get('p_warning_W2'))}"
            )
            st.caption(f"Tín chỉ học lại: {_format(plan.get('retake_credits_total'))}")
            st.caption(
                f"Kỳ tốt nghiệp ước tính: {_format(plan.get('estimated_graduation'))} "
                "(GIẢ ĐỊNH)"
            )
            courses = plan.get("selected_courses", [])
            if not courses:
                ids = plan.get("selected_course_ids", [])
                courses = [{"course_id": course_id} for course_id in ids]
            st.markdown("**Môn đăng ký / xác suất đạt**")
            probabilities = plan.get("pass_probabilities", {})
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Mã học phần": course.get("course_id"),
                            "Tên": course.get("course_name", "UNKNOWN"),
                            "P(đạt)": (
                                _format_probability(probabilities[course.get("course_id")])
                                if course.get("course_id") in probabilities
                                else "UNKNOWN"
                            ),
                        }
                        for course in courses
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            if plan.get("explanation"):
                st.caption(plan["explanation"])
            if plan.get("difference_explanation"):
                st.caption(plan["difference_explanation"])


def _render_plans(result: dict[str, Any]) -> None:
    st.subheader("Phương án đăng ký (ILP)")
    data = build_plans_data(result)
    if not data["plans"]:
        st.warning("Core không trả phương án đăng ký.")
        return
    _render_plan_cards(data)
    _source_badge("GIẢ ĐỊNH (xác suất, trọng số và mô hình tối ưu)")


def _render_what_if(result: dict[str, Any], student_id: str) -> None:
    st.subheader("What-if")
    limits = result["credit_regime"]
    minimum, maximum = limits.get("cmin"), limits.get("cmax")
    st.caption(
        f"Chế độ tín chỉ: **{limits.get('regime', 'UNKNOWN')}** "
        f"({minimum if minimum is not None else 'UNKNOWN'}–"
        f"{maximum if maximum is not None else 'UNKNOWN'}). "
        + " ".join(limits.get("notes", []))
    )
    _source_badge("OFFICIAL (NTU)")
    options: dict[str, Any] = {}
    if isinstance(minimum, int) and isinstance(maximum, int) and minimum <= maximum:
        selected_credits = st.slider(
            "Ngân sách đăng ký (tín chỉ)",
            min_value=minimum,
            max_value=maximum,
            value=min(maximum, max(minimum, 18)),
            key=f"whatif_budget_{student_id}",
        )
        options["budget"] = selected_credits
    else:
        st.info("Không có giới hạn cmin/cmax áp dụng; không hiển thị thanh trượt ngân sách.")
    fmax = st.select_slider(
        "Mức chấp nhận rủi ro Fmax",
        options=[0.5, 1.0, 1.5, 2.0, 3.0],
        value=2.0,
        key=f"whatif_fmax_{student_id}",
    )
    load_lambda = st.number_input(
        "Hệ số tải λ",
        min_value=0.0,
        value=0.1,
        step=0.1,
        key=f"whatif_lambda_{student_id}",
    )
    st.caption(
        "Tham số GIẢ ĐỊNH: λ mặc định 0,1; Fmax lấy lưới [0,5; 1; 1,5; 2; 3] "
        "trong config/optimizer_scenario_v2.yaml. Giới hạn đăng ký vẫn theo quy chế."
    )
    options.update(
        {
            "fmax": float(fmax),
            "lambda": float(load_lambda),
            "risk_cap_mode": "soft",
            "progress_override": _base_progress_override(student_id),
        }
    )
    alternate = _run(student_id, options)
    data = build_what_if_data(result, alternate)
    st.markdown("**So sánh phương án mặc định và what-if**")
    st.caption(RISK_THRESHOLD_NOTE)
    rows = []
    for title, plans in (
        ("Mặc định", data["baseline_plans"]),
        ("What-if", data["comparison_plans"]),
    ):
        for plan in plans:
            rows.append(
                {
                    "Bộ phương án": title,
                    "Chiến lược": plan["display_label"],
                    "Trạng thái": plan.get("status", "UNKNOWN"),
                    "Tín chỉ": plan.get("selected_credits", "UNKNOWN"),
                    "Tín chỉ đạt kỳ vọng": plan.get("expected_credits_passed", "UNKNOWN"),
                    "Môn trượt kỳ vọng": plan.get("expected_failed_courses", "UNKNOWN"),
                    "P(≥1 trượt)": plan.get("p_at_least_one_failure", "UNKNOWN"),
                    "Mức cảnh báo rủi ro": plan["risk_level"],
                }
            )
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        for row in rows:
            if row["Mức cảnh báo rủi ro"] == "CAO":
                st.error(
                    f"{row['Bộ phương án']} · {row['Chiến lược']}: mức cảnh báo rủi ro "
                    "CAO — khuyến nghị trao đổi với cố vấn học tập."
                )
    _source_badge("GIẢ ĐỊNH (what-if); OFFICIAL (NTU) (giới hạn tín chỉ)")


def _render_simulation(result: dict[str, Any]) -> None:
    st.subheader("Mô phỏng Monte Carlo")
    available_data = build_simulation_data(result)
    if not available_data["available"]:
        data = available_data
    else:
        lambda_options = available_data["available_lambdas"]
        selected_lambda = st.selectbox(
            "Hệ số tải λ của mô phỏng",
            options=lambda_options,
            index=lambda_options.index(available_data["selected_lambda"]),
            format_func=lambda value: f"{value:g}",
            key=f"simulation_lambda_{result['profile_summary']['student_id']}",
        )
        data = build_simulation_data(
            result,
            load_lambda=float(selected_lambda),
        )
    st.warning(
        "Đây là kết quả mô phỏng theo giả định, không phải bằng chứng hiệu quả với sinh viên NTU."
    )
    if not data["available"]:
        st.info(
            "Chưa có kết quả MC cho hồ sơ này (`reports/generated/mc_results.csv` "
            "chưa được tạo hoặc không chứa hồ sơ đang chọn); chưa kiểm chứng."
        )
        return
    results = data["results"]
    run_counts = sorted({int(value) for value in results["n_runs"].dropna()}) if "n_runs" in results else []
    st.caption(
        f"Hồ sơ: {data['student_id']} · "
        f"Số lượt MC mỗi phương án: {', '.join(map(str, run_counts)) or 'UNKNOWN'} · "
        f"λ={data['selected_lambda'] if data['selected_lambda'] is not None else 'UNKNOWN'} · "
        "Nhãn nguồn: GIẢ ĐỊNH"
    )
    policies = data["available_policies"]
    if not policies:
        st.info("Không có cột/chính sách trong kết quả MC; chưa kiểm chứng.")
        return
    default_policy = "ILP-matched" if "ILP-matched" in policies else policies[0]
    displayed_policies = st.multiselect(
        "Chính sách hiển thị",
        options=policies,
        default=[default_policy],
        key=f"simulation_policies_{data['student_id']}_{data['selected_lambda']}",
    )
    if "ILP-fixed" in policies:
        st.info(
            "ILP-fixed là phương án độ bền: planner dùng λ cố định trong cấu hình "
            "và không biết λ của thế giới mô phỏng. Chọn chính sách này để xem hàng."
        )
    if not displayed_policies:
        st.info("Chọn ít nhất một chính sách để hiển thị kết quả.")
    results = results.loc[results["policy"].astype(str).isin(displayed_policies)].copy()
    st.markdown("**Chỉ tiêu theo chính sách đã chọn**")
    if "policy" in results.columns:
        for column, title in (
            ("mean_graduation_semester", "Kỳ tốt nghiệp trung bình"),
            ("p_graduated_on_time", "Xác suất đúng hạn"),
            ("expected_failed_courses", "Số môn trượt kỳ vọng"),
            ("credits_accumulated_4_sem", "Tín chỉ sau 4 kỳ"),
        ):
            if column in results.columns:
                st.markdown(f"**{title}**")
                st.bar_chart(results.set_index("policy")[[column]])
                st.caption("Nhãn nguồn: GIẢ ĐỊNH (Monte Carlo)")
        if "credits_accumulated_final" in results.columns:
            st.markdown("**Tín chỉ tích lũy cuối mô phỏng**")
            st.bar_chart(results.set_index("policy")[["credits_accumulated_final"]])
            st.caption("Nhãn nguồn: GIẢ ĐỊNH (Monte Carlo)")
    st.dataframe(results, hide_index=True, width="stretch")
    if {"policy", "p_graduated_on_time"}.issubset(results.columns):
        on_time_rows = []
        for _, row in results.iterrows():
            lower = row.get("ci_p_graduated_on_time_lower")
            upper = row.get("ci_p_graduated_on_time_upper")
            on_time_rows.append(
                {
                    "Phương án": row["policy"],
                    "P(đúng hạn)": f"{float(row['p_graduated_on_time']):.1%}",
                    "KTC 95%": (
                        f"[{float(lower):.1%}, {float(upper):.1%}]"
                        if pd.notna(lower) and pd.notna(upper)
                        else "UNKNOWN"
                    ),
                }
            )
        st.markdown("**Xác suất đúng hạn và khoảng tin cậy 95%**")
        st.dataframe(pd.DataFrame(on_time_rows), hide_index=True, width="stretch")
    histogram = data["grad_hist"]
    if histogram is not None and not histogram.empty:
        st.markdown("**Phân phối tốt nghiệp theo học kỳ mô phỏng**")
        histogram = histogram.loc[
            histogram["policy"].astype(str).isin(displayed_policies)
        ].copy()
        graduated = histogram.loc[
            histogram["outcome"].eq("graduated")
            & pd.to_numeric(histogram["semester"], errors="coerce").notna()
        ]
        if not graduated.empty:
            semester_counts = graduated.pivot_table(
                index="semester",
                columns="policy",
                values="count",
                aggfunc="sum",
                fill_value=0,
            ).sort_index()
            figure, axis = plt.subplots(figsize=(9, 4))
            semester_counts.plot(kind="bar", ax=axis)
            axis.axvline(
                x=list(semester_counts.index).index(8) + 0.5
                if 8 in semester_counts.index
                else 0,
                color="#555555",
                linestyle="--",
                linewidth=1.5,
                label="Đúng hạn = 8 kỳ",
            )
            axis.set_xlabel("Học kỳ tốt nghiệp")
            axis.set_ylabel("Số lượt")
            axis.legend()
            figure.tight_layout()
            st.pyplot(figure)
            plt.close(figure)

        terminal_rows = []
        for policy, group in histogram.groupby("policy", sort=False):
            total_values = pd.to_numeric(group["n_total"], errors="coerce").dropna().unique()
            if len(total_values) != 1:
                raise ValueError(f"{policy}: histogram n_total is inconsistent")
            total = int(total_values[0])
            graduated_count = int(group.loc[group["outcome"].eq("graduated"), "count"].sum())
            forced_count = int(
                group.loc[group["outcome"].eq("forced_withdrawal"), "count"].sum()
            )
            explicitly_unfinished = int(
                group.loc[group["outcome"].eq("not_finished_16"), "count"].sum()
            )
            unfinished_count = total - graduated_count - forced_count
            if explicitly_unfinished:
                if explicitly_unfinished != unfinished_count:
                    raise ValueError(f"{policy}: histogram outcome counts do not partition n_total")
            if unfinished_count < 0:
                raise ValueError(f"{policy}: histogram counts exceed n_total")
            terminal_rows.append(
                {
                    "Chính sách": policy,
                    "Tốt nghiệp (đến kỳ 16)": graduated_count,
                    "Buộc thôi học": forced_count,
                    "Chưa tốt nghiệp kỳ 16": unfinished_count,
                    "Tổng lượt": total,
                }
            )
        st.markdown("**Kết quả đến kỳ 16**")
        st.dataframe(
            pd.DataFrame(terminal_rows).set_index("Chính sách"),
            width="stretch",
        )
        st.caption(
            "Số lượt chưa tốt nghiệp kỳ 16 là phần còn lại trong n_total sau khi "
            "trừ tốt nghiệp và buộc thôi học; không phải kết quả suy diễn ngoài histogram."
        )
        st.caption("Nhãn nguồn: GIẢ ĐỊNH (Monte Carlo).")
    else:
        st.info(
            "Không có `mc_grad_hist.csv`; không thể dựng phân phối kỳ tốt nghiệp "
            "hay suy diễn lượt chưa hoàn tất."
        )

    pareto_labels = {
        "ILP vượt trội": "background-color: #d9ead3; color: #274e13",
        "ILP bị vượt trội": "background-color: #f4cccc; color: #660000",
        "đánh đổi": "background-color: #fff2cc; color: #7f6000",
        "chưa phân biệt": "background-color: #eeeeee; color: #333333",
    }
    pareto_badge_colors = {
        "ILP vượt trội": "green",
        "ILP bị vượt trội": "red",
        "đánh đổi": "orange",
        "chưa phân biệt": "gray",
    }
    for label in data["pareto_labels"]:
        st.badge(label, color=pareto_badge_colors.get(label, "gray"))

    pairwise_source = data["pairwise"]
    if pairwise_source is not None and not pairwise_source.empty:
        comparisons = data["available_comparisons"]
        selected_comparisons = st.multiselect(
            "Cặp so sánh",
            options=comparisons,
            default=comparisons,
            key=f"simulation_comparisons_{data['student_id']}_{data['selected_lambda']}",
        )
        st.markdown("**Chênh lệch ghép cặp và khoảng tin cậy 95%**")
        pairwise = pairwise_source.loc[
            pairwise_source["comparison"].astype(str).isin(selected_comparisons)
        ].copy()
        pareto = data["pareto"]
        if pareto is not None and not pareto.empty:
            pairwise = pairwise.merge(
                pareto[
                    ["student_id", "policy_a", "policy_b", "lambda", "dominance"]
                ],
                on=["student_id", "policy_a", "policy_b", "lambda"],
                how="left",
            )
        pair_columns = [
            column
            for column in (
                "comparison",
                "diff_p_graduated_on_time",
                "ci_p_graduated_on_time_lower",
                "ci_p_graduated_on_time_upper",
                "diff_p_graduated_16",
                "ci_p_graduated_16_lower",
                "ci_p_graduated_16_upper",
                "diff_mean_graduation_semester",
                "ci_mean_graduation_semester_lower",
                "ci_mean_graduation_semester_upper",
                "diff_expected_failed_courses",
                "ci_expected_failed_courses_lower",
                "ci_expected_failed_courses_upper",
                "diff_credits_accumulated_4_sem",
                "ci_credits_accumulated_4_sem_lower",
                "ci_credits_accumulated_4_sem_upper",
                "dominance",
            )
            if column in pairwise.columns
        ]
        pairwise_display = pairwise[pair_columns]
        if "dominance" in pairwise_display.columns:
            pairwise_display = pairwise_display.style.map(
                lambda value: pareto_labels.get(
                    str(value), "background-color: #eeeeee; color: #333333"
                ),
                subset=["dominance"],
            )
        st.dataframe(pairwise_display, hide_index=True, width="stretch")
    if data["pareto"] is not None and not data["pareto"].empty:
        st.markdown("**Nhãn Pareto**")
        pareto = data["pareto"].copy()
        if "dominance" in pareto.columns:
            pareto_display = pareto.style.map(
                lambda value: pareto_labels.get(
                    str(value), "background-color: #eeeeee; color: #333333"
                ),
                subset=["dominance"],
            )
        else:
            pareto_display = pareto
        st.dataframe(pareto_display, hide_index=True, width="stretch")
    _source_badge("GIẢ ĐỊNH")

    with st.container(border=True):
        st.markdown("### Diễn giải và giới hạn")
        if MC_INTERPRETATION_PATH.is_file():
            st.markdown(MC_INTERPRETATION_PATH.read_text(encoding="utf-8-sig"))
        else:
            st.info("`mc_interpretation.md` chưa có; diễn giải chưa kiểm chứng.")


def _render_provenance() -> None:
    st.subheader("Dữ liệu & giả định")
    data = build_provenance_data()
    st.dataframe(pd.DataFrame(data["sources"]), hide_index=True, width="stretch")
    _source_badge("OFFICIAL (NTU) · REAL (UCI-697) · SCENARIO · GIẢ ĐỊNH")
    st.markdown(f"**Phiên bản CTĐT:** {data['curriculum_version']}")
    st.markdown("**UNCONFIRMED**")
    for item in data["unconfirmed"]:
        st.markdown(f"- {item}")
    st.markdown("**Hạn chế mô hình**")
    for item in data["limitations"]:
        st.markdown(f"- {item}")
    st.caption(
        "Lịch mở môn chẵn/lẻ là GIẢ ĐỊNH (suy từ CTĐT); chưa có nguồn chính thức "
        "được xác nhận cho quy tắc này."
    )


def main() -> None:
    st.set_page_config(page_title="NTU · Hỗ trợ quyết định học tập", layout="wide")
    st.title("Hỗ trợ quyết định cảnh báo rủi ro học tập")
    st.caption("Mỗi hồ sơ dưới đây là kịch bản, không phải dữ liệu cá nhân thật.")
    scenarios = list_scenarios()
    if not scenarios:
        st.error("Không tìm thấy hồ sơ kịch bản trong data/scenarios/.")
        return
    ids = [row["student_id"] for row in scenarios]
    selected_id = st.sidebar.selectbox(
        "Chọn kịch bản sinh viên",
        ids,
        format_func=lambda value: (
            f"{value} · "
            + next((row["persona"] for row in scenarios if row["student_id"] == value), "")
        ),
    )
    selected = next(row for row in scenarios if row["student_id"] == selected_id)
    st.sidebar.caption(f"ML scope: {selected['ml_scope']}")
    st.sidebar.caption(selected["ml_scope_reason"])
    page = st.sidebar.radio("Trang", PAGE_KEYS)

    result = _run(
        selected_id,
        {"progress_override": _base_progress_override(selected_id)},
    )
    if page == "Hồ sơ & tiến độ":
        _render_profile(result, selected_id)
    elif page == "Nguy cơ & cảnh báo":
        _render_risk(result)
    elif page == "Học phần":
        _render_courses(result)
    elif page == "Phương án đăng ký":
        _render_plans(result)
    elif page == "What-if":
        _render_what_if(result, selected_id)
    elif page == "Mô phỏng":
        _render_simulation(result)
    else:
        _render_provenance()


if __name__ == "__main__":
    main()
