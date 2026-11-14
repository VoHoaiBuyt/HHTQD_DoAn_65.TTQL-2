"""Streamlit demo for student input, rule assessment, and ILP planning."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.assessment import (
    assess_student,
    build_plans,
    default_rules,
    load_bundle,
    load_curriculum,
    persona_payload,
)
from src.services.input_validation import (
    ALLOWED_STATUSES,
    InputError,
    normalize_profile,
    normalize_progress_rows,
)

st.set_page_config(
    page_title="DSS cảnh báo rủi ro & lộ trình tín chỉ",
    layout="wide",
)

REPORTS_DIR = ROOT / "reports" / "generated"
STRATEGY_LABELS = {
    "ILP": "ILP (PuLP)",
    "B1": "B1 — đúng kỳ + học lại",
    "B2": "B2 — tối đa tín chỉ",
    "B3": "B3 — cố định 15 tín chỉ",
}


@st.cache_resource
def get_bundle() -> dict:
    return load_bundle()


@st.cache_resource
def get_curriculum() -> dict:
    return load_curriculum()


@st.cache_resource
def get_rules() -> dict:
    return default_rules()


@st.cache_resource(show_spinner=False)
def get_shap_context() -> dict | None:
    """LinearExplainer for the serving LR pipeline on a REAL UCI-697 background."""
    try:
        import shap
    except ImportError:
        return None
    from src.analysis.risk_to_plan_exploration import _load_real_data

    bundle = get_bundle()
    data, features, _, _ = _load_real_data()
    background = data[features].sample(
        n=min(120, len(data)), random_state=int(bundle["seed"])
    )
    pipeline = bundle["dropout_model"]
    preprocessor = pipeline.named_steps["columntransformer"]
    model = pipeline.named_steps["logisticregression"]
    transformed = preprocessor.transform(background)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    explainer = shap.LinearExplainer(
        model, shap.maskers.Independent(transformed, max_samples=200)
    )
    return {
        "explainer": explainer,
        "preprocessor": preprocessor,
        "feature_names": [str(name) for name in preprocessor.get_feature_names_out()],
        "dropout_index": list(model.classes_).index("Dropout"),
    }


def _clean_feature_name(name: str) -> str:
    short = name.split("__", 1)[-1]
    if name.startswith("categorical__"):
        base, _, value = short.rpartition("_")
        return f"{base} = {value}" if base else short
    return short


def explain_dropout(profile: dict, top_n: int = 10) -> pd.DataFrame | None:
    context = get_shap_context()
    if context is None:
        return None
    features = get_bundle()["features"]
    frame = pd.DataFrame(
        [{feature: profile[feature] for feature in features}], columns=features
    )
    transformed = context["preprocessor"].transform(frame)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    raw = context["explainer"].shap_values(transformed)
    if isinstance(raw, list):
        raw = np.asarray(raw[context["dropout_index"]])
    values = np.asarray(raw)
    if values.ndim == 3:
        values = values[:, :, context["dropout_index"]]
    contributions = pd.DataFrame(
        {
            "feature": [
                _clean_feature_name(name) for name in context["feature_names"]
            ],
            "shap_value": values[0],
        }
    )
    contributions["abs_shap"] = contributions["shap_value"].abs()
    return contributions.sort_values("abs_shap", ascending=False).head(top_n)


def progress_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in ("grade_10", "attempt_count", "semester_taken"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def show_data_labels() -> None:
    st.sidebar.caption(
        "**REAL (UCI-697)** cho mô hình · **SIMULATED** cho CTĐT/persona · "
        "**GIẢ ĐỊNH** cho λ, độ khó, học lại, trần tín chỉ."
    )
    st.sidebar.caption(
        "Kết quả exploratory, không phải quy chế NTU và không diễn giải nhân quả."
    )


def render_inputs(curriculum: dict):
    mode = st.sidebar.radio(
        "Nguồn dữ liệu",
        ["Persona mẫu", "Nhập tay", "CSV"],
        key="input_mode",
    )
    persona_id = None
    if mode == "Persona mẫu":
        persona_id = st.sidebar.selectbox(
            "Chọn persona",
            sorted(curriculum["profiles"]["student_id"].tolist()),
            key="persona_id",
        )

    st.subheader("1. Nhập hồ sơ")
    if mode == "Persona mẫu":
        profile, rows = persona_payload(curriculum, persona_id)
        st.caption(
            f"Persona **{persona_id}** · {profile.get('persona', '')} · "
            f"{profile.get('persona_purpose', '')}"
        )
        st.dataframe(
            progress_frame(rows),
            width="stretch",
            hide_index=True,
            height=260,
        )
        return mode, persona_id, profile, rows, True

    if mode == "CSV":
        col1, col2 = st.columns(2)
        with col1:
            profile_file = st.file_uploader(
                "profile.csv (1 dòng)", type="csv", key="profile_csv"
            )
            st.download_button(
                "Tải mẫu profile.csv",
                curriculum["profiles"]
                .head(1)
                .to_csv(index=False)
                .encode("utf-8-sig"),
                file_name="profile_template.csv",
                key="download_profile",
            )
        with col2:
            progress_file = st.file_uploader(
                "progress.csv", type="csv", key="progress_csv"
            )
            sample = curriculum["progress"]
            st.download_button(
                "Tải mẫu progress.csv",
                sample[sample["student_id"] == "S002"]
                .to_csv(index=False)
                .encode("utf-8-sig"),
                file_name="progress_template.csv",
                key="download_progress",
            )
        if profile_file is None or progress_file is None:
            st.info("Tải đủ hai tệp CSV để đánh giá.")
            return mode, None, None, None, False
        try:
            profile_frame_csv = pd.read_csv(profile_file, encoding="utf-8-sig")
            progress_csv = pd.read_csv(progress_file, encoding="utf-8-sig")
            if profile_frame_csv.empty:
                raise InputError("profile.csv không có dòng dữ liệu.")
            profile = normalize_profile(profile_frame_csv.iloc[0].to_dict())
            rows = normalize_progress_rows(
                progress_csv.to_dict("records"),
                known_course_ids=curriculum["course_by_id"].keys(),
            )
        except (InputError, pd.errors.ParserError, UnicodeDecodeError) as error:
            st.error(str(error))
            return mode, None, None, None, False
        return mode, None, profile, rows, False

    st.caption(
        "Nhập các trường hồ sơ và sửa bảng tiến độ. Chế độ này không có đủ "
        "24 feature T0/T1-known nên **không ước lượng P(Dropout)**."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        student_id = st.text_input("Mã sinh viên", value="S002", key="manual_id")
        semester = st.number_input(
            "Học kỳ hiện tại", min_value=1, max_value=8, value=4, key="manual_sem"
        )
        gpa = st.number_input(
            "GPA (hệ 4)", min_value=0.0, max_value=4.0, value=2.6, step=0.01,
            key="manual_gpa",
        )
    with col2:
        cumulative = st.number_input(
            "Tín chỉ tích lũy", min_value=0, max_value=300, value=64,
            key="manual_credits",
        )
        failed_count = st.number_input(
            "Số môn chưa đạt", min_value=0, max_value=48, value=2,
            key="manual_failed",
        )
    with col3:
        hk1_enrolled = st.number_input(
            "Unit HK1 đăng ký", min_value=0, max_value=30, value=7,
            key="manual_hk1_enrolled",
        )
        hk1_approved = st.number_input(
            "Unit HK1 đạt", min_value=0, max_value=30, value=6,
            key="manual_hk1_approved",
        )
        hk1_grade = st.number_input(
            "Điểm TB HK1 (thang 20)", min_value=0.0, max_value=20.0,
            value=12.0, step=0.1, key="manual_hk1_grade",
        )

    if "manual_progress" not in st.session_state:
        _, rows = persona_payload(curriculum, "S002")
        st.session_state["manual_progress"] = progress_frame(rows)
    edited = st.data_editor(
        st.session_state["manual_progress"],
        key="progress_editor",
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        column_config={
            "course_id": st.column_config.TextColumn("Môn", disabled=True),
            "status": st.column_config.SelectboxColumn(
                "Trạng thái", options=sorted(ALLOWED_STATUSES), required=True
            ),
            "grade_10": st.column_config.NumberColumn(
                "Điểm hệ 10", min_value=0.0, max_value=10.0, step=0.1
            ),
            "attempt_count": st.column_config.NumberColumn(
                "Số lần học", min_value=0, max_value=10, step=1
            ),
            "semester_taken": st.column_config.NumberColumn(
                "Học kỳ đã học", min_value=1, max_value=8, step=1
            ),
        },
    )
    try:
        profile = normalize_profile(
            {
                "student_id": student_id,
                "current_semester": semester,
                "gpa": gpa,
                "cumulative_credits": cumulative,
                "failed_courses_count": failed_count,
                "hk1_enrolled": hk1_enrolled,
                "hk1_approved": hk1_approved,
                "hk1_grade": hk1_grade,
            }
        )
        progress_rows = [
            {**row, "student_id": profile["student_id"]}
            for row in normalize_progress_rows(
                edited.to_dict("records"),
                known_course_ids=curriculum["course_by_id"].keys(),
            )
        ]
    except InputError as error:
        st.error(str(error))
        return mode, None, None, None, False
    return mode, None, profile, progress_rows, False


def render_assessment(assessment: dict) -> None:
    rule_result = assessment["rule_result"]
    st.subheader("2. Cảnh báo và điều kiện đăng ký")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tầng cảnh báo", assessment["risk_label"])
    col2.metric(
        "P(Dropout) hiệu chuẩn",
        "—" if assessment["p_dropout_calibrated"] is None
        else f"{assessment['p_dropout_calibrated']:.3f}",
    )
    col3.metric("Tầng năng lực HK1", assessment["ability_tier"])
    col4.metric("Môn đủ điều kiện", len(rule_result["eligible_courses"]))
    st.caption(assessment["risk_note"])
    if assessment["p_pass_model"] is not None:
        st.caption(
            f"RF pass-rate exploratory: {assessment['p_pass_model']:.3f} · "
            f"M3′ nền: {assessment['p_pass_m3_prime']:.3f}"
        )
    elif assessment["p_pass_m3_prime"] is not None:
        st.caption(f"M3′ nền (REAL, theo tầng HK1): {assessment['p_pass_m3_prime']:.3f}")

    flags = pd.DataFrame(rule_result.get("academic_flags", []))
    if not flags.empty:
        st.markdown("**Cảnh báo học vụ (không dùng ML)**")
        st.dataframe(flags, width="stretch", hide_index=True)

    edge = pd.DataFrame(rule_result.get("edge_case_flags", []))
    if not edge.empty:
        st.markdown("**Cờ ca biên**")
        st.dataframe(edge, width="stretch", hide_index=True)

    progress_stats = rule_result.get("progress_stats", {})
    if progress_stats:
        st.markdown("**Tiến độ tín chỉ**")
        stat_cols = st.columns(4)
        stat_cols[0].metric("Tín chỉ tích lũy", progress_stats.get("credits_earned", "—"))
        stat_cols[1].metric("Tín chỉ còn lại", progress_stats.get("credits_remaining", "—"))
        stat_cols[2].metric(
            "Chậm tiến độ", progress_stats.get("credits_behind_expected", "—")
        )
        stat_cols[3].metric(
            "HK tối thiểu còn lại",
            progress_stats.get("minimum_semesters_remaining", "—"),
        )
        st.caption(
            f"Chuỗi tiên quyết dài nhất: "
            f"{progress_stats.get('longest_strict_prerequisite_chain', '—')} HK · "
            f"Đạt ngưỡng tín chỉ tốt nghiệp: "
            f"{'Có' if progress_stats.get('graduation_credit_threshold_met') else 'Chưa'}."
        )

    eligible = pd.DataFrame(rule_result["eligible_courses"])
    if eligible.empty:
        st.warning("Không có học phần đủ điều kiện trong kỳ tới.")
    else:
        st.markdown("**Học phần đủ điều kiện**")
        st.dataframe(
            eligible[
                [
                    "course_id",
                    "course_name",
                    "credits",
                    "group",
                    "status",
                    "planned_semester",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    failed = pd.DataFrame(rule_result.get("failed_courses", []))
    if not failed.empty:
        st.markdown("**Học phần chưa đạt (cần học lại)**")
        st.dataframe(
            failed[["course_id", "course_name", "credits", "attempt_count"]],
            width="stretch",
            hide_index=True,
        )

    blocked_rows = [
        {
            "course_id": course["course_id"],
            "course_name": course.get("course_name", ""),
            "credits": course["credits"],
            "unmet_prerequisites": ", ".join(
                f"{item['prerequisite_id']} ({item['type']}, {item['status']})"
                for item in course.get("unmet_prerequisites", [])
            ),
        }
        for course in rule_result.get("blocked_courses", [])
    ]
    if blocked_rows:
        st.markdown("**Học phần bị chặn bởi tiên quyết**")
        st.dataframe(
            pd.DataFrame(blocked_rows), width="stretch", hide_index=True
        )

    render_shap(assessment)
    st.caption(
        "Cảnh báo rủi ro chỉ để hiển thị/cố vấn; cap tín chỉ và Fmax là "
        "khuyến nghị mềm (`enforce_cap=false`), không phải quy chế."
    )


def render_shap(assessment: dict) -> None:
    st.markdown("**Vì sao mô hình dự đoán rủi ro? (SHAP · LR đang phục vụ)**")
    if not assessment["risk_estimated"]:
        st.info(
            "Chế độ nhập tay/CSV thiếu 24 feature T0/T1-known nên không tính SHAP."
        )
        return
    try:
        with st.spinner("Đang tính SHAP..."):
            table = explain_dropout(assessment["profile"])
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
        st.warning(f"Không tính được SHAP: {error}")
        return
    if table is None:
        st.info("Chưa cài `shap` nên không hiển thị giải thích.")
        return
    table = table.assign(shap_value=table["shap_value"].round(4))
    st.dataframe(
        table[["feature", "shap_value"]], width="stretch", hide_index=True
    )
    st.caption(
        "SHAP dương làm tăng P(Dropout), âm làm giảm. Đây là đóng góp vào "
        "**dự đoán** của mô hình, **không phải quan hệ nhân quả**."
    )


def _plan_signature(
    assessment: dict,
    budgets: list[int],
    load_lambda: float,
    fmax: float,
    enforce_cap: bool,
) -> tuple:
    profile = assessment["profile"]
    return (
        str(profile.get("student_id")),
        int(profile.get("current_semester", 0)),
        round(float(load_lambda), 4),
        tuple(sorted(budgets)),
        round(float(fmax), 4),
        bool(enforce_cap),
    )


def render_plan(assessment: dict, curriculum: dict) -> None:
    st.subheader("3. Lộ trình học phần: so sánh nhiều ngân sách tín chỉ")
    rule_result = assessment["rule_result"]
    targets = [int(value) for value in get_rules()["scenario_credit_targets"]["values"]]
    col1, col2, col3, col4 = st.columns([1.4, 1.4, 1, 1])
    with col1:
        budgets = st.multiselect(
            "Ngân sách tín chỉ (so sánh cùng lúc)",
            targets,
            default=targets,
            key="plan_budgets",
        )
    with col2:
        load_lambda = st.slider(
            "λ tải học (GIẢ ĐỊNH kịch bản)",
            min_value=0.0,
            max_value=0.5,
            value=0.1,
            step=0.05,
            key="load_lambda",
        )
    with col3:
        fmax = st.number_input(
            "Fmax (môn trượt kỳ vọng)",
            min_value=0.0,
            max_value=6.0,
            value=float(rule_result["expected_failed_course_cap"]),
            step=0.5,
            key="plan_fmax",
        )
    with col4:
        enforce_cap = st.checkbox(
            "Áp trần tín chỉ khuyến nghị",
            value=bool(rule_result["enforce_cap"]),
            key="plan_enforce_cap",
            help="Mặc định TẮT: P(Dropout) chỉ là cảnh báo mềm, không tự chặn đăng ký.",
        )

    st.caption(
        "Mục tiêu ILP: `Σ credits×p_pass + β×unlock − γ×credits×(1−p_pass)`; "
        "β/γ/λ là **GIẢ ĐỊNH kịch bản**, không phải ước lượng nhân quả. "
        "Fmax mặc định lấy theo tầng cảnh báo."
    )

    if not budgets:
        st.warning("Chọn ít nhất một ngân sách tín chỉ.")
        return
    signature = _plan_signature(assessment, budgets, load_lambda, fmax, enforce_cap)
    if st.button("Lập & so sánh lộ trình", key="run_plan", type="primary"):
        try:
            with st.spinner("Đang giải ILP cho các ngân sách..."):
                plans = build_plans(
                    assessment,
                    curriculum,
                    get_bundle(),
                    get_rules(),
                    budgets=sorted(budgets),
                    load_lambda=load_lambda,
                    expected_fail_cap_override=fmax,
                    enforce_cap_override=enforce_cap,
                )
            st.session_state["plan_results"] = plans
            st.session_state["plan_signature"] = signature
        except (InputError, ValueError, KeyError) as error:
            st.error(str(error))
            return

    plans = st.session_state.get("plan_results")
    if not plans:
        st.info(
            "Bấm **Lập & so sánh lộ trình** để giải ILP cho 12/15/18 tín chỉ."
        )
        return
    if st.session_state.get("plan_signature") != signature:
        st.warning(
            "Tham số đã thay đổi nhưng bảng dưới vẫn là kết quả lần chạy trước. "
            "Bấm lại nút để cập nhật."
        )

    comparison = pd.DataFrame(
        [
            {
                "Ngân sách": plan["budget"],
                "Trần áp dụng": plan["scenario_credit_max"],
                "Trạng thái": plan["result"].get("status", "—"),
                "Tín chỉ chọn": plan["result"].get("selected_credits", 0),
                "Tín chỉ đạt kỳ vọng": round(
                    float(plan["result"].get("expected_credits_passed", 0.0)), 2
                ),
                "Môn trượt kỳ vọng": round(
                    float(plan["result"].get("expected_failed_courses", 0.0)), 2
                ),
                "Fmax": round(float(plan["result"].get("expected_fail_cap", 0.0)), 2),
                "Vượt Fmax": "CÓ" if plan["result"].get("risk_cap_exceeded") else "không",
                "Fallback": plan["result"].get("fallback_mode", "normal"),
            }
            for plan in plans
        ]
    )
    st.markdown("**So sánh các ngân sách**")
    st.dataframe(comparison, width="stretch", hide_index=True)

    detail_budget = st.selectbox(
        "Xem chi tiết ngân sách",
        [plan["budget"] for plan in plans],
        key="plan_detail_budget",
    )
    plan = next(item for item in plans if item["budget"] == detail_budget)
    result = plan["result"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trạng thái", result.get("status", "—"))
    col2.metric("Tín chỉ chọn", result.get("selected_credits", 0))
    col3.metric(
        "Tín chỉ đạt kỳ vọng",
        f"{result.get('expected_credits_passed', 0.0):.2f}",
    )
    col4.metric(
        "Số môn trượt kỳ vọng",
        f"{result.get('expected_failed_courses', 0.0):.2f}",
    )

    status = result.get("status")
    if status == "infeasible_data_error":
        st.error(
            "**Không tìm được phương án hợp lệ.** "
            + result.get("suggested_action", "")
        )
    elif status == "best_effort":
        st.error(
            f"**best_effort — KHÔNG phải phương án an toàn.** "
            f"Môn trượt kỳ vọng {result.get('expected_failed_courses', 0.0):.2f} "
            f"vượt Fmax {result.get('expected_fail_cap', 0.0):.2f} "
            f"(slack {result.get('risk_cap_slack', 0.0):.2f}). "
            f"{result.get('suggested_action', 'Trao đổi với cố vấn học tập.')} "
            "P(Dropout) chỉ là cảnh báo mềm, không tự động chặn đăng ký."
        )
    elif result.get("reduced_load_advised"):
        st.warning(result.get("message", "Đã đề xuất giảm tải."))
    else:
        st.success(result.get("message", "Phương án tối ưu."))

    st.caption(
        f"Tín chỉ chọn {result.get('selected_credits', 0)} / ngân sách "
        f"{plan['budget']} · hệ số tải tính trên "
        f"{result.get('load_basis_credits', 0)} tín chỉ (λ={load_lambda:.2f}, "
        f"{result.get('load_refinement_iterations', 0)} vòng tinh chỉnh). "
        "Chọn ít hơn ngân sách là bình thường: tín chỉ môn học rời rạc, "
        "Cmin chỉ là sàn mềm."
    )

    selected = pd.DataFrame(plan["selected_courses"])
    if selected.empty:
        st.warning("Phương án không chọn học phần nào.")
    else:
        display = selected[
            ["course_id", "course_name", "credits", "group", "status", "p_pass"]
        ].copy()
        display["p_pass"] = (display["p_pass"] * 100).round(1)
        display = display.rename(columns={"p_pass": "P(đạt) %"})
        st.dataframe(display, width="stretch", hide_index=True)

    combined = pd.DataFrame(
        [
            {"budget": plan["budget"], **course}
            for plan in plans
            for course in plan["selected_courses"]
        ]
    )
    if not combined.empty:
        st.download_button(
            "Tải kế hoạch tất cả ngân sách (CSV)",
            combined.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"plans_{assessment['profile']['student_id']}.csv",
            key="download_plans",
        )
    st.caption(
        "Kết quả từ prototype PuLP/HiGHS; persona/CTĐT **SIMULATED**, "
        "λ/β/γ/retake là **GIẢ ĐỊNH**, không phải dự báo nhân quả."
    )


def _pct(value: float) -> str:
    return f"{float(value):.1%}"


def render_simulation() -> None:
    st.subheader("4. Mô phỏng Monte Carlo: ILP vs B1/B2/B3")
    st.caption(
        "**SIMULATED**: 1.000 lượt/sinh viên/chiến lược với common random numbers; "
        "P(đạt) = M3′ **REAL (UCI-697)** × hệ số độ khó và λ **GIẢ ĐỊNH**. "
        "Đây là phân tích kịch bản, không phải bằng chứng thực nghiệm tại NTU."
    )
    summary_path = REPORTS_DIR / "monte_carlo_summary.csv"
    by_student_path = REPORTS_DIR / "monte_carlo_by_student.csv"
    paired_path = REPORTS_DIR / "monte_carlo_paired_differences.csv"
    if not summary_path.exists():
        st.info(
            "Chưa có kết quả mô phỏng. Chạy: "
            "`.venv/bin/python scripts/monte_carlo_strategies.py --runs 1000`"
        )
        return

    aggregate = pd.read_csv(summary_path)
    aggregate = aggregate[aggregate["scope"] == "ALL"]
    display = pd.DataFrame(
        {
            "Chiến lược": [
                STRATEGY_LABELS.get(value, value)
                for value in aggregate["strategy"]
            ],
            "Tốt nghiệp (95% CI)": [
                f"{_pct(row.graduation_rate)} "
                f"[{_pct(row.graduation_rate_ci_low)}, "
                f"{_pct(row.graduation_rate_ci_high)}]"
                for row in aggregate.itertuples()
            ],
            "Đúng hạn (95% CI)": [
                f"{_pct(row.on_time_rate)} "
                f"[{_pct(row.on_time_rate_ci_low)}, "
                f"{_pct(row.on_time_rate_ci_high)}]"
                for row in aggregate.itertuples()
            ],
            "Khả thi": [_pct(value) for value in aggregate["feasibility_rate"]],
            "Môn trượt TB (95% CI)": [
                f"{row.mean_simulated_failures:.2f} "
                f"[{row.mean_simulated_failures_ci_low:.2f}, "
                f"{row.mean_simulated_failures_ci_high:.2f}]"
                for row in aggregate.itertuples()
            ],
            "Tín chỉ TB": aggregate["mean_credits_earned"].round(1),
            "HK TB": aggregate["mean_semesters_to_graduation"].round(2),
            "Pareto": aggregate["pareto_frontier"].map(
                {True: "Có", False: "Không"}
            ),
        }
    )
    st.markdown("**Tổng hợp toàn bộ persona (7 sinh viên × 1.000 lượt)**")
    st.dataframe(display, width="stretch", hide_index=True)

    image_columns = st.columns(2)
    for column, name, caption in (
        (
            image_columns[0],
            "monte_carlo_pareto.png",
            "Pareto: tối thiểu môn trượt vs tối đa tỷ lệ đúng hạn",
        ),
        (
            image_columns[1],
            "monte_carlo_rates.png",
            "Tỷ lệ tốt nghiệp / đúng hạn / khả thi theo chiến lược",
        ),
    ):
        path = REPORTS_DIR / name
        if path.exists():
            with column:
                st.image(str(path), caption=caption, width="stretch")

    if by_student_path.exists():
        by_student = pd.read_csv(by_student_path)
        students = sorted(by_student["student_id"].unique())
        strategies = [
            value
            for value in by_student["strategy"].unique()
            if value in STRATEGY_LABELS
        ]
        col1, col2 = st.columns(2)
        with col1:
            picked_students = st.multiselect(
                "Lọc sinh viên", students, default=students, key="mc_students"
            )
        with col2:
            picked_strategies = st.multiselect(
                "Lọc chiến lược",
                strategies,
                default=strategies,
                format_func=lambda value: STRATEGY_LABELS[value],
                key="mc_strategies",
            )
        filtered = by_student[
            by_student["student_id"].isin(picked_students)
            & by_student["strategy"].isin(picked_strategies)
        ]
        st.markdown("**Kết quả theo sinh viên**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Sinh viên": filtered["student_id"],
                    "Chiến lược": [
                        STRATEGY_LABELS.get(value, value)
                        for value in filtered["strategy"]
                    ],
                    "Tốt nghiệp": [_pct(value) for value in filtered["graduation_rate"]],
                    "Đúng hạn": [_pct(value) for value in filtered["on_time_rate"]],
                    "Khả thi": [_pct(value) for value in filtered["feasibility_rate"]],
                    "Môn trượt TB": filtered["mean_simulated_failures"].round(2),
                    "Tín chỉ TB": filtered["mean_credits_earned"].round(1),
                    "HK TB": filtered["mean_semesters_to_graduation"].round(2),
                }
            ),
            width="stretch",
            hide_index=True,
        )

    if paired_path.exists():
        paired = pd.read_csv(paired_path)
        st.markdown("**Chênh lệch bắt cặp so với ILP**")
        st.dataframe(
            pd.DataFrame(
                {
                    "So sánh": paired["comparison"],
                    "Chỉ số": paired["metric"],
                    "Chênh lệch TB": paired["mean_difference"].round(4),
                    "95% CI": [
                        f"[{low:.4f}, {high:.4f}]"
                        for low, high in zip(paired["ci_low"], paired["ci_high"])
                    ],
                    "CI loại 0": paired["ci_excludes_zero"].map(
                        {True: "Có", False: "Không"}
                    ),
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Đọc trung thực: ILP giảm số môn trượt và tăng khả thi so với B1, "
            "nhưng B1 có tỷ lệ đúng hạn cao hơn; ILP không thắng mọi chỉ số."
        )
    st.caption(
        "Tái lập: `.venv/bin/python scripts/monte_carlo_strategies.py --runs 1000` · "
        "chi tiết trong `reports/generated/monte_carlo_meta.json`."
    )


def main() -> None:
    st.title("DSS cảnh báo rủi ro học vụ và lộ trình tín chỉ")
    show_data_labels()
    curriculum = get_curriculum()
    try:
        get_bundle()
    except FileNotFoundError as error:
        st.error(str(error))
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Nhập hồ sơ", "Đánh giá", "Lộ trình", "Mô phỏng"]
    )
    with tab1:
        mode, _persona_id, profile, progress_rows, use_ml = render_inputs(curriculum)
        if st.button("Đánh giá", key="assess", type="primary"):
            if profile is None or progress_rows is None:
                st.error("Chưa có đủ dữ liệu để đánh giá.")
            else:
                try:
                    with st.spinner("Đang đánh giá..."):
                        assessment = assess_student(
                            profile,
                            progress_rows,
                            curriculum,
                            get_bundle(),
                            get_rules(),
                            use_ml=use_ml,
                        )
                    st.session_state["assessment"] = assessment
                    st.session_state["assessment_mode"] = mode
                    st.session_state.pop("plan", None)
                    st.session_state.pop("plan_results", None)
                    st.session_state.pop("plan_signature", None)
                    st.success(
                        f"Đã đánh giá {profile['student_id']} "
                        f"({mode}). Chuyển sang tab Đánh giá."
                    )
                except (InputError, ValueError, KeyError) as error:
                    st.error(str(error))

    assessment = st.session_state.get("assessment")
    with tab2:
        if assessment is None:
            st.info("Chưa có kết quả. Nhập hồ sơ và bấm **Đánh giá**.")
        else:
            st.caption(
                f"Chế độ: **{st.session_state.get('assessment_mode', '—')}** · "
                f"Mã: **{assessment['profile']['student_id']}**"
            )
            render_assessment(assessment)

    with tab3:
        if assessment is None:
            st.info("Cần đánh giá hồ sơ trước khi lập lộ trình.")
        else:
            render_plan(assessment, curriculum)

    with tab4:
        render_simulation()

    with st.expander("Giới hạn và nhãn dữ liệu"):
        st.markdown(
            "- **REAL (UCI-697)**: mô hình exploratory; domain shift sang NTU chưa kiểm định.\n"
            "- **SIMULATED**: CTĐT, tiến độ, persona, độ khó nhóm môn, mô phỏng Monte Carlo.\n"
            "- **GIẢ ĐỊNH**: λ, retake, β/γ, trần tín chỉ/Fmax; `enforce_cap=false`.\n"
            "- Nhập tay/CSV không có đủ 24 feature nên **không** chạy ML risk; "
            "lộ trình dùng M3′ và tầng trung bình.\n"
            "- Không dùng kết quả làm quyết định học vụ chính thức."
        )


if __name__ == "__main__":
    main()
