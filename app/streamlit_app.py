"""Streamlit demo for student input, rule assessment, and ILP planning."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.assessment import (  # noqa: E402
    assess_student,
    build_plans,
    default_rules,
    load_bundle,
    load_curriculum,
    persona_payload,
)
from src.services.input_validation import (  # noqa: E402
    ALLOWED_STATUSES,
    InputError,
    normalize_profile,
    normalize_progress_rows,
)

st.set_page_config(
    page_title="DSS cảnh báo rủi ro & lộ trình tín chỉ",
    layout="wide",
)


@st.cache_resource
def get_bundle() -> dict:
    return load_bundle()


@st.cache_resource
def get_curriculum() -> dict:
    return load_curriculum()


@st.cache_resource
def get_rules() -> dict:
    return default_rules()


def profile_frame(profile: dict, index: int = 0) -> pd.DataFrame:
    return pd.DataFrame([profile], index=[index])


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
        progress_rows = normalize_progress_rows(
            edited.to_dict("records"),
            known_course_ids=curriculum["course_by_id"].keys(),
        )
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
    st.caption(
        "Cảnh báo rủi ro chỉ để hiển thị/cố vấn; cap tín chỉ và Fmax là "
        "khuyến nghị mềm (`enforce_cap=false`), không phải quy chế."
    )


def render_plan(assessment: dict, curriculum: dict) -> None:
    st.subheader("3. Lộ trình học phần")
    col1, col2 = st.columns([1, 2])
    with col1:
        budget = st.selectbox(
            "Ngân sách tín chỉ",
            [int(value) for value in get_rules()["scenario_credit_targets"]["values"]],
            index=0,
            key="budget",
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
    if st.button("Lập lộ trình", key="run_plan", type="primary"):
        try:
            with st.spinner("Đang giải ILP..."):
                plans = build_plans(
                    assessment,
                    curriculum,
                    get_bundle(),
                    get_rules(),
                    budgets=[budget],
                    load_lambda=load_lambda,
                )
            st.session_state["plan"] = plans[0]
        except (InputError, ValueError, KeyError) as error:
            st.error(str(error))

    plan = st.session_state.get("plan")
    if not plan:
        st.info("Bấm **Lập lộ trình** để chạy ILP cho ngân sách đã chọn.")
        return

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
    if result.get("risk_cap_exceeded"):
        st.warning(
            f"Vượt Fmax mềm {result.get('risk_cap_slack', 0.0):.2f} môn. "
            + result.get("suggested_action", "")
        )
    elif result.get("reduced_load_advised"):
        st.warning(result.get("message", ""))
    else:
        st.success(result.get("message", ""))

    selected = pd.DataFrame(plan["selected_courses"])
    if not selected.empty:
        st.dataframe(
            selected[
                ["course_id", "course_name", "credits", "group", "status", "p_pass"]
            ],
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Tải kế hoạch CSV",
            selected.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"plan_{assessment['profile']['student_id']}_{budget}.csv",
            key="download_plan",
        )
    st.caption(
        "Kết quả từ prototype PuLP/HiGHS; person/CTĐT SIMULATED, λ là GIẢ ĐỊNH, "
        "không phải dự báo nhân quả."
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

    tab1, tab2, tab3 = st.tabs(["Nhập hồ sơ", "Đánh giá", "Lộ trình"])
    with tab1:
        mode, persona_id, profile, progress_rows, use_ml = render_inputs(curriculum)
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

    with st.expander("Giới hạn và nhãn dữ liệu"):
        st.markdown(
            "- **REAL (UCI-697)**: mô hình exploratory; domain shift sang NTU chưa kiểm định.\n"
            "- **SIMULATED**: CTĐT, tiến độ, persona, độ khó nhóm môn.\n"
            "- **GIẢ ĐỊNH**: λ, retake, β/γ, trần tín chỉ/Fmax; `enforce_cap=false`.\n"
            "- Nhập tay/CSV không có đủ 24 feature nên **không** chạy ML risk; "
            "lộ trình dùng M3′ và tầng trung bình.\n"
            "- Không dùng kết quả làm quyết định học vụ chính thức."
        )


if __name__ == "__main__":
    main()
