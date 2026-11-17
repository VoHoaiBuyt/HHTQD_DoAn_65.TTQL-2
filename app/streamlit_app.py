"""Streamlit UI cho hệ thống cảnh báo học vụ và lộ trình tín chỉ."""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
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
    page_title="Hệ thống Hỗ trợ Cảnh báo Học vụ & Tối ưu Lộ trình Tín chỉ",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

REPORTS_DIR = ROOT / "reports" / "generated"

# ── Display label maps (UI only, không ảnh hưởng backend) ────────────────────

STRATEGY_LABELS = {
    "ILP": "ILP — Tối ưu hóa lộ trình",
    "B1": "B1 — Đúng tiến độ + học lại",
    "B2": "B2 — Tối đa tín chỉ",
    "B3": "B3 — Cố định 15 tín chỉ",
}

RISK_TIER_STYLE: dict[str, dict[str, str]] = {
    "Thấp":           {"bg": "#dcfce7", "text": "#15803d", "border": "#86efac", "icon": "✅"},
    "Trung bình":     {"bg": "#fef9c3", "text": "#a16207", "border": "#fde047", "icon": "⚠️"},
    "Cao":            {"bg": "#fee2e2", "text": "#b91c1c", "border": "#fca5a5", "icon": "🔴"},
    "Chưa ước lượng": {"bg": "#f1f5f9", "text": "#475569", "border": "#cbd5e1", "icon": "—"},
}

_STATUS_VI = {
    "completed":   "Đã hoàn thành",
    "failed":      "Chưa đạt",
    "in_progress": "Đang học",
    "not_taken":   "Chưa học",
}

_PLAN_STATUS_VI = {
    "optimal":              "Tối ưu ✅",
    "best_effort":          "Nỗ lực tối đa ⚠️",
    "infeasible_data_error":"Không khả thi ❌",
    "graduation_ready":     "Đủ ĐK tốt nghiệp 🎓",
    "no_eligible_courses":  "Không có môn ĐK",
}

_FALLBACK_VI = {
    "normal":            "Bình thường",
    "relaxed_minimum":   "Nới sàn tín chỉ",
    "minimum_zero":      "Không có sàn",
    "no_forced_retakes": "Không ép học lại",
    "relaxed_fail_cap":  "Nới ngưỡng trượt",
    "at_least_one_course": "Ít nhất 1 môn",
}

# ── CSS ───────────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """
<style>
/* ── Layout ──────────────────────────────── */
.stApp { background: #f8fafc; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; }

/* ── Typography ──────────────────────────── */
h1 {
    color: #0f172a; font-size: 1.65rem; font-weight: 800;
    letter-spacing: -0.025em; line-height: 1.25;
}
h2, h3 { color: #1e293b; }
main.stMain h3 {
    border-left: 4px solid #2563eb; padding-left: 0.65rem;
    font-size: 1.0rem; font-weight: 700;
    margin-top: 1.4rem; margin-bottom: 0.6rem;
}
p, li, span, label, small { color: #334155; }

/* ── Sidebar ─────────────────────────────── */
div[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e2e8f0;
}
div[data-testid="stSidebar"] .stCaption p {
    color: #64748b; font-size: 0.77rem; line-height: 1.55;
}

/* ── Metric cards ────────────────────────── */
div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1rem 1.1rem;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06);
    transition: box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 8px rgba(15,23,42,0.08);
}
div[data-testid="stMetricLabel"] p {
    color: #64748b; font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.07em;
}
div[data-testid="stMetricValue"] {
    color: #0f172a; font-weight: 800; font-size: 1.4rem;
}

/* ── Buttons ─────────────────────────────── */
.stButton > button {
    border-radius: 10px; font-weight: 600;
    padding: 0.45rem 1.15rem;
    border: 1.5px solid #cbd5e1;
    background: #ffffff; color: #374151;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    border-color: #2563eb; color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}
.stButton > button[kind="primary"] {
    background: #2563eb;
    border-color: transparent; color: #ffffff;
    box-shadow: 0 1px 3px rgba(37,99,235,0.35);
}
.stButton > button[kind="primary"]:hover {
    background: #1d4ed8; color: #ffffff;
    box-shadow: 0 4px 8px rgba(37,99,235,0.3);
}

/* ── Tabs ────────────────────────────────── */
div[data-testid="stTabs"] button[role="tab"] {
    border-radius: 999px; padding: 0.32rem 1.1rem;
    font-weight: 600; color: #64748b; font-size: 0.88rem;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #2563eb;
}

/* ── DataFrames ──────────────────────────── */
div[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0; border-radius: 12px;
    background: #ffffff; overflow: hidden;
}

/* ── Alerts ──────────────────────────────── */
.stAlert, div[data-testid="stAlert"] { border-radius: 12px; }

/* ── Expander ────────────────────────────── */
div[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    overflow: hidden;
}

/* ── Download button ─────────────────────── */
div[data-testid="stDownloadButton"] > button {
    border-radius: 8px; font-size: 0.84rem;
}

hr { border-color: #e2e8f0; margin: 0.8rem 0; }
</style>
"""

DATA_CHIPS = (
    '<div style="margin:4px 0 18px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
    '<span style="background:#dbeafe;color:#1d4ed8;padding:4px 12px;'
    'border-radius:999px;font-size:11.5px;font-weight:700;letter-spacing:0.03em">'
    "Dữ liệu huấn luyện: Thực tế (UCI)</span>"
    '<span style="background:#fef3c7;color:#b45309;padding:4px 12px;'
    'border-radius:999px;font-size:11.5px;font-weight:700;letter-spacing:0.03em">'
    "Dữ liệu kiểm thử: Mô phỏng CTĐT</span>"
    '<span style="background:#f1f5f9;color:#475569;padding:4px 12px;'
    'border-radius:999px;font-size:11.5px;font-weight:700;letter-spacing:0.03em">'
    "Tham số: Tải học tập &amp; Rủi ro học lại</span>"
    "</div>"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def inject_styles() -> None:
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


def risk_badge(label: str) -> str:
    s = RISK_TIER_STYLE.get(label, RISK_TIER_STYLE["Chưa ước lượng"])
    return (
        f'<span style="background:{s["bg"]};color:{s["text"]};'
        f'border:1.5px solid {s["border"]};border-radius:999px;'
        f'padding:5px 14px;font-weight:700;font-size:0.88rem;'
        f'display:inline-block;margin:6px 0 10px">'
        f'{s["icon"]}&nbsp;{label}</span>'
    )


def _display_with_status(df: pd.DataFrame) -> pd.DataFrame:
    """Bản sao để hiển thị: map giá trị status sang tiếng Việt."""
    out = df.copy()
    if "status" in out.columns:
        out["status"] = out["status"].map(lambda s: _STATUS_VI.get(str(s), s))
    return out


def progress_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for col in ("grade_10", "attempt_count", "semester_taken"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def _pct(value: float) -> str:
    return f"{float(value):.1%}"


def _risk_note_vi(assessment: dict) -> str:
    if assessment["risk_estimated"]:
        return (
            "Xác suất rủi ro bỏ học từ mô hình dự báo; chỉ mang tính tham khảo, "
            "không ảnh hưởng trực tiếp đến tỷ lệ đạt môn."
        )
    return (
        "Không đủ thông tin đặc trưng để ước tính xác suất rủi ro bỏ học; "
        "lộ trình sử dụng tỷ lệ nền theo nhóm năng lực HK1 (giả định kịch bản)."
    )


# ── Cached resources ──────────────────────────────────────────────────────────

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
    """LinearExplainer cho serving LR pipeline trên UCI-697 background."""
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
        "feature_names": [str(n) for n in preprocessor.get_feature_names_out()],
        "dropout_index": list(model.classes_).index("Dropout"),
    }


# ── SHAP ──────────────────────────────────────────────────────────────────────

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
        [{feat: profile[feat] for feat in features}], columns=features
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
            "feature": [_clean_feature_name(n) for n in context["feature_names"]],
            "shap_value": values[0],
        }
    )
    contributions["abs_shap"] = contributions["shap_value"].abs()
    return contributions.sort_values("abs_shap", ascending=False).head(top_n)


def render_shap_chart(table: pd.DataFrame) -> None:
    df = table.copy()
    df["Ảnh hưởng"] = df["shap_value"].apply(
        lambda v: "Làm tăng rủi ro" if v > 0 else "Làm giảm rủi ro"
    )
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "shap_value:Q",
                title="Mức độ ảnh hưởng (SHAP)",
                axis=alt.Axis(grid=True, gridColor="#e2e8f0"),
            ),
            y=alt.Y("feature:N", sort="-x", title=None),
            color=alt.Color(
                "Ảnh hưởng:N",
                scale=alt.Scale(
                    domain=["Làm tăng rủi ro", "Làm giảm rủi ro"],
                    range=["#dc2626", "#16a34a"],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("feature:N", title="Đặc trưng"),
                alt.Tooltip("shap_value:Q", format="+.4f", title="SHAP"),
            ],
        )
        .properties(height=max(260, len(df) * 28))
    )
    zero_line = (
        alt.Chart(pd.DataFrame({"x": [0]}))
        .mark_rule(color="#94a3b8", strokeWidth=1.5)
        .encode(x="x:Q")
    )
    st.altair_chart(
        (bars + zero_line).configure_view(strokeWidth=0).configure_axis(labelFontSize=12),
        use_container_width=True,
    )


def render_shap(assessment: dict) -> None:
    st.markdown("**Các yếu tố ảnh hưởng đến dự báo rủi ro bỏ học (SHAP)**")
    if not assessment["risk_estimated"]:
        st.info(
            "Ở chế độ nhập thủ công / tải CSV, dữ liệu không đủ đặc trưng "
            "để tính phân tích SHAP."
        )
        return
    try:
        with st.spinner("Đang phân tích yếu tố ảnh hưởng..."):
            table = explain_dropout(assessment["profile"])
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as err:
        st.warning(f"Không thực hiện được phân tích SHAP: {err}")
        return
    if table is None:
        st.info("Thư viện `shap` chưa được cài đặt.")
        return
    render_shap_chart(table.assign(shap_value=table["shap_value"].round(4)))
    st.caption(
        "Thanh màu đỏ: yếu tố làm tăng rủi ro · Thanh màu xanh: yếu tố làm giảm rủi ro. "
        "Đây là giải thích dự đoán của mô hình, **không phản ánh quan hệ nhân quả**."
    )


# ── Sidebar + Input ───────────────────────────────────────────────────────────

def show_data_labels() -> None:
    st.sidebar.markdown("### Trợ lý Học vụ Thông minh")
    st.sidebar.caption("Mô hình thử nghiệm • Nhóm 1")
    st.sidebar.divider()
    st.sidebar.caption(
        "**Dữ liệu thực tế (UCI-697)** dùng để huấn luyện mô hình · "
        "**Dữ liệu mô phỏng** cho chương trình đào tạo và hồ sơ sinh viên · "
        "**Giả định kịch bản** cho các hệ số tải học và rủi ro học lại."
    )
    st.sidebar.caption(
        "Kết quả mang tính chất tham khảo hỗ trợ quyết định, không thay thế "
        "quy chế đào tạo chính thức của Trường Đại học Nha Trang (NTU)."
    )


def render_inputs(curriculum: dict):
    mode = st.sidebar.radio(
        "Nguồn dữ liệu",
        ["Hồ sơ mẫu (Có sẵn)", "Nhập thủ công", "Tải lên file CSV"],
        key="input_mode",
    )
    persona_id = None
    if mode == "Hồ sơ mẫu (Có sẵn)":
        persona_id = st.sidebar.selectbox(
            "Chọn hồ sơ sinh viên mẫu",
            sorted(curriculum["profiles"]["student_id"].tolist()),
            key="persona_id",
        )

    st.subheader("1. Nhập hồ sơ sinh viên")

    if mode == "Hồ sơ mẫu (Có sẵn)":
        profile, rows = persona_payload(curriculum, persona_id)
        persona_desc = profile.get("persona", "").strip()
        persona_purpose = profile.get("persona_purpose", "").strip()
        st.caption(
            f"Hồ sơ **{persona_id}**: {persona_desc}"
            + (f" — {persona_purpose}" if persona_purpose else "")
        )
        st.dataframe(
            _display_with_status(progress_frame(rows)),
            use_container_width=True,
            hide_index=True,
            height=260,
            column_config={
                "student_id":     st.column_config.TextColumn("Mã sinh viên"),
                "course_id":      st.column_config.TextColumn("Mã học phần"),
                "status":         st.column_config.TextColumn("Trạng thái"),
                "grade_10":       st.column_config.NumberColumn("Điểm hệ 10", format="%.1f"),
                "attempt_count":  st.column_config.NumberColumn("Số lần học", format="%d"),
                "semester_taken": st.column_config.NumberColumn("Học kỳ", format="%d"),
            },
        )
        return mode, persona_id, profile, rows, True

    if mode == "Tải lên file CSV":
        col1, col2 = st.columns(2)
        with col1:
            profile_file = st.file_uploader(
                "Tệp hồ sơ (profile.csv — 1 dòng dữ liệu)",
                type="csv", key="profile_csv",
            )
            st.download_button(
                "Tải mẫu profile.csv",
                curriculum["profiles"].head(1).to_csv(index=False).encode("utf-8-sig"),
                file_name="profile_template.csv",
                key="download_profile",
            )
        with col2:
            progress_file = st.file_uploader(
                "Tệp tiến độ (progress.csv)",
                type="csv", key="progress_csv",
            )
            st.download_button(
                "Tải mẫu progress.csv",
                curriculum["progress"][
                    curriculum["progress"]["student_id"] == "S002"
                ].to_csv(index=False).encode("utf-8-sig"),
                file_name="progress_template.csv",
                key="download_progress",
            )
        if profile_file is None or progress_file is None:
            st.info("Vui lòng tải lên cả hai tệp CSV để hệ thống có thể đánh giá.")
            return mode, None, None, None, False
        try:
            profile_frame_csv = pd.read_csv(profile_file, encoding="utf-8-sig")
            progress_csv = pd.read_csv(progress_file, encoding="utf-8-sig")
            if profile_frame_csv.empty:
                raise InputError("Tệp profile.csv không có dòng dữ liệu.")
            profile = normalize_profile(profile_frame_csv.iloc[0].to_dict())
            rows = normalize_progress_rows(
                progress_csv.to_dict("records"),
                known_course_ids=curriculum["course_by_id"].keys(),
            )
        except (InputError, pd.errors.ParserError, UnicodeDecodeError) as err:
            st.error(str(err))
            return mode, None, None, None, False
        return mode, None, profile, rows, False

    # Nhập thủ công
    st.caption(
        "Nhập thông tin hồ sơ và chỉnh sửa bảng tiến độ học tập. "
        "Ở chế độ này, không đủ thông tin đặc trưng để "
        "**ước tính xác suất rủi ro bỏ học**."
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
            "Số môn HK1 đăng ký", min_value=0, max_value=30, value=7,
            key="manual_hk1_enrolled",
        )
        hk1_approved = st.number_input(
            "Số môn HK1 đạt", min_value=0, max_value=30, value=6,
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
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "course_id": st.column_config.TextColumn("Mã học phần", disabled=True),
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
    except InputError as err:
        st.error(str(err))
        return mode, None, None, None, False
    return mode, None, profile, progress_rows, False


# ── Tab Đánh giá ──────────────────────────────────────────────────────────────

def render_assessment(assessment: dict) -> None:
    rule_result = assessment["rule_result"]
    risk_label = assessment["risk_label"]

    st.subheader("2. Kết quả đánh giá rủi ro & điều kiện đăng ký")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mức cảnh báo rủi ro", risk_label)
    col2.metric(
        "Xác suất rủi ro bỏ học",
        "—" if assessment["p_dropout_calibrated"] is None
        else f"{assessment['p_dropout_calibrated']:.3f}",
    )
    col3.metric("Nhóm năng lực Học kỳ 1", assessment["ability_tier"])
    col4.metric("Học phần đủ ĐK đăng ký", len(rule_result["eligible_courses"]))

    st.markdown(risk_badge(risk_label), unsafe_allow_html=True)
    st.caption(_risk_note_vi(assessment))
    if assessment["p_pass_model"] is not None:
        st.caption(
            f"Dự báo tỷ lệ đạt môn (Random Forest): {assessment['p_pass_model']:.3f} · "
            f"Tỷ lệ nền theo nhóm năng lực: {assessment['p_pass_m3_prime']:.3f}"
        )
    elif assessment["p_pass_m3_prime"] is not None:
        st.caption(
            f"Tỷ lệ nền theo nhóm năng lực HK1 (dữ liệu thực tế UCI): "
            f"{assessment['p_pass_m3_prime']:.3f}"
        )

    flags = pd.DataFrame(rule_result.get("academic_flags", []))
    if not flags.empty:
        st.markdown("**Cảnh báo học vụ (theo quy tắc nghiệp vụ)**")
        st.dataframe(flags, use_container_width=True, hide_index=True)

    edge = pd.DataFrame(rule_result.get("edge_case_flags", []))
    if not edge.empty:
        st.markdown("**Lưu ý đặc biệt**")
        st.dataframe(edge, use_container_width=True, hide_index=True)

    progress_stats = rule_result.get("progress_stats", {})
    if progress_stats:
        st.markdown("**Tổng quan tiến độ tín chỉ**")
        sc = st.columns(4)
        sc[0].metric("Tín chỉ đã tích lũy", progress_stats.get("credits_earned", "—"))
        sc[1].metric("Tín chỉ còn lại", progress_stats.get("credits_remaining", "—"))
        sc[2].metric("Chậm so với tiến độ", progress_stats.get("credits_behind_expected", "—"))
        sc[3].metric(
            "Học kỳ tối thiểu còn lại",
            progress_stats.get("minimum_semesters_remaining", "—"),
        )
        grad_met = progress_stats.get("graduation_credit_threshold_met")
        st.caption(
            f"Chuỗi tiên quyết dài nhất: "
            f"{progress_stats.get('longest_strict_prerequisite_chain', '—')} học kỳ · "
            f"Đạt ngưỡng tín chỉ tốt nghiệp: {'✅ Có' if grad_met else '❌ Chưa'}."
        )

    eligible = pd.DataFrame(rule_result["eligible_courses"])
    if eligible.empty:
        st.warning("Không có học phần đủ điều kiện đăng ký trong kỳ tới.")
    else:
        st.markdown("**Học phần đủ điều kiện đăng ký**")
        st.dataframe(
            _display_with_status(
                eligible[["course_id", "course_name", "credits", "group", "status", "planned_semester"]]
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "course_id":        st.column_config.TextColumn("Mã học phần"),
                "course_name":      st.column_config.TextColumn("Tên học phần"),
                "credits":          st.column_config.NumberColumn("Số TC", format="%d"),
                "group":            st.column_config.TextColumn("Nhóm môn"),
                "status":           st.column_config.TextColumn("Trạng thái"),
                "planned_semester": st.column_config.NumberColumn("HK kế hoạch", format="%d"),
            },
        )

    failed = pd.DataFrame(rule_result.get("failed_courses", []))
    if not failed.empty:
        st.markdown("**Học phần cần học lại**")
        st.dataframe(
            failed[["course_id", "course_name", "credits", "attempt_count"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "course_id":     st.column_config.TextColumn("Mã học phần"),
                "course_name":   st.column_config.TextColumn("Tên học phần"),
                "credits":       st.column_config.NumberColumn("Số TC", format="%d"),
                "attempt_count": st.column_config.NumberColumn("Đã học (lần)", format="%d"),
            },
        )

    blocked_rows = [
        {
            "course_id": c["course_id"],
            "course_name": c.get("course_name", ""),
            "credits": c["credits"],
            "unmet_prerequisites": ", ".join(
                f"{item['prerequisite_id']} ({item['type']}, {item['status']})"
                for item in c.get("unmet_prerequisites", [])
            ),
        }
        for c in rule_result.get("blocked_courses", [])
    ]
    if blocked_rows:
        st.markdown("**Học phần chưa đủ điều kiện tiên quyết**")
        st.dataframe(
            pd.DataFrame(blocked_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "course_id":          st.column_config.TextColumn("Mã học phần"),
                "course_name":        st.column_config.TextColumn("Tên học phần"),
                "credits":            st.column_config.NumberColumn("Số TC", format="%d"),
                "unmet_prerequisites":st.column_config.TextColumn("Tiên quyết chưa đáp ứng"),
            },
        )

    render_shap(assessment)
    st.caption(
        "Kết quả cảnh báo chỉ mang tính tham khảo; giới hạn tín chỉ và ngưỡng môn không đạt "
        "là khuyến nghị hỗ trợ, không phải quy chế bắt buộc."
    )


# ── Tab Lộ trình ──────────────────────────────────────────────────────────────

def _plan_signature(
    assessment: dict,
    budgets: list[int],
    load_lambda: float,
    fmax: float,
    enforce_cap: bool,
) -> tuple:
    p = assessment["profile"]
    return (
        str(p.get("student_id")),
        int(p.get("current_semester", 0)),
        round(float(load_lambda), 4),
        tuple(sorted(budgets)),
        round(float(fmax), 4),
        bool(enforce_cap),
    )


def render_plan_comparison_chart(plans: list[dict]) -> None:
    rows = []
    for plan in plans:
        r = plan["result"]
        label = f"{plan['budget']} TC"
        rows.extend([
            {"Ngân sách": label, "Chỉ số": "Tín chỉ đăng ký",
             "Giá trị": r.get("selected_credits", 0)},
            {"Ngân sách": label, "Chỉ số": "Tín chỉ dự báo đạt",
             "Giá trị": round(float(r.get("expected_credits_passed", 0.0)), 2)},
        ])
    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Ngân sách:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                "Giá trị:Q",
                title="Tín chỉ",
                axis=alt.Axis(grid=True, gridColor="#e2e8f0"),
            ),
            color=alt.Color(
                "Chỉ số:N",
                scale=alt.Scale(
                    domain=["Tín chỉ đăng ký", "Tín chỉ dự báo đạt"],
                    range=["#2563eb", "#16a34a"],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            xOffset="Chỉ số:N",
            tooltip=[
                "Ngân sách:N",
                "Chỉ số:N",
                alt.Tooltip("Giá trị:Q", format=".2f"),
            ],
        )
        .properties(height=240)
    )
    st.altair_chart(chart.configure_view(strokeWidth=0), use_container_width=True)


def render_plan(assessment: dict, curriculum: dict) -> None:
    st.subheader("3. Lộ trình học phần: so sánh các phương án tín chỉ")
    rule_result = assessment["rule_result"]
    targets = [int(v) for v in get_rules()["scenario_credit_targets"]["values"]]

    col1, col2, col3, col4 = st.columns([1.4, 1.4, 1, 1])
    with col1:
        budgets = st.multiselect(
            "Mức tín chỉ cần so sánh",
            targets, default=targets, key="plan_budgets",
        )
    with col2:
        load_lambda = st.slider(
            "Hệ số tải học tập (kịch bản thử nghiệm)",
            min_value=0.0, max_value=0.5, value=0.1, step=0.05, key="load_lambda",
        )
    with col3:
        fmax = st.number_input(
            "Ngưỡng môn không đạt cho phép",
            min_value=0.0, max_value=6.0,
            value=float(rule_result["expected_failed_course_cap"]),
            step=0.5, key="plan_fmax",
        )
    with col4:
        enforce_cap = st.checkbox(
            "Áp giới hạn tín chỉ khuyến nghị",
            value=bool(rule_result["enforce_cap"]),
            key="plan_enforce_cap",
            help="Mặc định TẮT: hệ thống chỉ cảnh báo, không tự giới hạn đăng ký.",
        )

    st.caption(
        "Hệ thống tối ưu chọn học phần để tối đa hóa tín chỉ đạt được và mở khóa môn tiếp theo, "
        "đồng thời kiểm soát rủi ro trượt môn. "
        "Các hệ số và ngưỡng là **giả định kịch bản thử nghiệm**, chưa phải quy chế chính thức."
    )

    if not budgets:
        st.warning("Vui lòng chọn ít nhất một mức tín chỉ.")
        return

    signature = _plan_signature(assessment, budgets, load_lambda, fmax, enforce_cap)
    if st.button("Lập & so sánh lộ trình", key="run_plan", type="primary"):
        try:
            with st.spinner("Đang tối ưu lộ trình học tập..."):
                plans = build_plans(
                    assessment, curriculum, get_bundle(), get_rules(),
                    budgets=sorted(budgets), load_lambda=load_lambda,
                    expected_fail_cap_override=fmax, enforce_cap_override=enforce_cap,
                )
            st.session_state["plan_results"] = plans
            st.session_state["plan_signature"] = signature
        except (InputError, ValueError, KeyError) as err:
            st.error(str(err))
            return

    plans = st.session_state.get("plan_results")
    if not plans:
        st.info(
            "Bấm **Lập & so sánh lộ trình** để xây dựng phương án học tập "
            "cho các mức tín chỉ 12/15/18."
        )
        return
    if st.session_state.get("plan_signature") != signature:
        st.warning(
            "Tham số đã thay đổi nhưng kết quả hiển thị là từ lần chạy trước. "
            "Bấm lại nút để cập nhật."
        )

    render_plan_comparison_chart(plans)

    comparison = pd.DataFrame(
        [
            {
                "Mức tín chỉ": plan["budget"],
                "Trần áp dụng": plan["scenario_credit_max"],
                "Kết quả": _PLAN_STATUS_VI.get(
                    plan["result"].get("status", ""), plan["result"].get("status", "—")
                ),
                "TC đăng ký": plan["result"].get("selected_credits", 0),
                "TC dự báo đạt": round(
                    float(plan["result"].get("expected_credits_passed", 0.0)), 2
                ),
                "Môn không đạt (dự báo)": round(
                    float(plan["result"].get("expected_failed_courses", 0.0)), 2
                ),
                "Ngưỡng trượt": round(float(plan["result"].get("expected_fail_cap", 0.0)), 2),
                "Vượt ngưỡng": "CÓ ⚠️" if plan["result"].get("risk_cap_exceeded") else "—",
                "Chế độ dự phòng": _FALLBACK_VI.get(
                    plan["result"].get("fallback_mode", "normal"), "Bình thường"
                ),
            }
            for plan in plans
        ]
    )
    st.markdown("**So sánh các phương án**")
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    detail_budget = st.selectbox(
        "Xem chi tiết phương án",
        [p["budget"] for p in plans],
        format_func=lambda v: f"{v} tín chỉ",
        key="plan_detail_budget",
    )
    plan = next(item for item in plans if item["budget"] == detail_budget)
    result = plan["result"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Kết quả",
        _PLAN_STATUS_VI.get(result.get("status", ""), result.get("status", "—")),
    )
    col2.metric("Tín chỉ đăng ký", result.get("selected_credits", 0))
    col3.metric("Tín chỉ dự báo đạt", f"{result.get('expected_credits_passed', 0.0):.2f}")
    col4.metric("Số môn dự báo không đạt", f"{result.get('expected_failed_courses', 0.0):.2f}")

    status = result.get("status")
    if status == "infeasible_data_error":
        st.error(
            "**Không tìm được phương án phù hợp.** " + result.get("suggested_action", "")
        )
    elif status == "best_effort":
        st.error(
            f"**Phương án nỗ lực tối đa — Cần thận trọng.** "
            f"Dự báo số môn không đạt ({result.get('expected_failed_courses', 0.0):.2f}) "
            f"vượt ngưỡng cho phép ({result.get('expected_fail_cap', 0.0):.2f}). "
            f"{result.get('suggested_action', 'Trao đổi với cố vấn học tập.')} "
            "Hệ thống chỉ cảnh báo, không tự động hạn chế đăng ký."
        )
    elif result.get("reduced_load_advised"):
        st.warning(result.get("message", "Đề xuất giảm tải học tập."))
    else:
        st.success(result.get("message", "Phương án tối ưu."))

    st.caption(
        f"Tín chỉ đăng ký: {result.get('selected_credits', 0)} / Mức chọn: {plan['budget']} · "
        f"Tính trên {result.get('load_basis_credits', 0)} TC "
        f"(hệ số tải={load_lambda:.2f}, "
        f"{result.get('load_refinement_iterations', 0)} lần tinh chỉnh). "
        "Chọn ít hơn mức chọn là bình thường do tín chỉ môn học rời rạc."
    )

    selected = pd.DataFrame(plan["selected_courses"])
    if selected.empty:
        st.warning("Phương án này không tìm được học phần phù hợp.")
    else:
        display = _display_with_status(
            selected[["course_id", "course_name", "credits", "group", "status", "p_pass"]].copy()
        )
        display["p_pass"] = (selected["p_pass"] * 100).round(1)
        display = display.rename(columns={"p_pass": "P(đạt) %"})
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "course_id":   st.column_config.TextColumn("Mã học phần"),
                "course_name": st.column_config.TextColumn("Tên học phần"),
                "credits":     st.column_config.NumberColumn("Số TC", format="%d"),
                "group":       st.column_config.TextColumn("Nhóm môn"),
                "status":      st.column_config.TextColumn("Trạng thái"),
                "P(đạt) %": st.column_config.ProgressColumn(
                    "Xác suất đạt (%)", min_value=0, max_value=100, format="%.1f%%"
                ),
            },
        )

    combined = pd.DataFrame(
        [
            {"budget": p["budget"], **course}
            for p in plans
            for course in p["selected_courses"]
        ]
    )
    if not combined.empty:
        st.download_button(
            "Tải xuống kế hoạch học tập (CSV)",
            combined.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ke_hoach_{assessment['profile']['student_id']}.csv",
            key="download_plans",
        )
    st.caption(
        "Dữ liệu hồ sơ và chương trình đào tạo là **mô phỏng**; "
        "các hệ số tải học và rủi ro học lại là **giả định kịch bản**, "
        "không phản ánh quan hệ nhân quả."
    )


# ── Tab Mô phỏng ──────────────────────────────────────────────────────────────

def render_simulation() -> None:
    st.subheader("4. Mô phỏng Monte Carlo: So sánh chiến lược đăng ký")
    st.caption(
        "Thực hiện 1.000 lượt mô phỏng cho mỗi hồ sơ sinh viên và chiến lược đăng ký. "
        "Xác suất đạt môn được ước tính từ dữ liệu thực tế (UCI) nhân với hệ số tải học "
        "và độ khó môn học (giả định kịch bản). "
        "Đây là phân tích thử nghiệm, không phải bằng chứng thực nghiệm tại NTU."
    )
    summary_path = REPORTS_DIR / "monte_carlo_summary.csv"
    by_student_path = REPORTS_DIR / "monte_carlo_by_student.csv"
    paired_path = REPORTS_DIR / "monte_carlo_paired_differences.csv"

    if not summary_path.exists():
        st.info(
            "Chưa có kết quả mô phỏng. Chạy lệnh sau để tạo: "
            "`.venv/bin/python scripts/monte_carlo_strategies.py --runs 1000`"
        )
        return

    aggregate = pd.read_csv(summary_path)
    aggregate = aggregate[aggregate["scope"] == "ALL"]
    display = pd.DataFrame(
        {
            "Chiến lược": [STRATEGY_LABELS.get(v, v) for v in aggregate["strategy"]],
            "Tỷ lệ tốt nghiệp (95% CI)": [
                f"{_pct(row.graduation_rate)} "
                f"[{_pct(row.graduation_rate_ci_low)}, {_pct(row.graduation_rate_ci_high)}]"
                for row in aggregate.itertuples()
            ],
            "Tỷ lệ đúng hạn (95% CI)": [
                f"{_pct(row.on_time_rate)} "
                f"[{_pct(row.on_time_rate_ci_low)}, {_pct(row.on_time_rate_ci_high)}]"
                for row in aggregate.itertuples()
            ],
            "Tỷ lệ khả thi": [_pct(v) for v in aggregate["feasibility_rate"]],
            "Môn không đạt TB (95% CI)": [
                f"{row.mean_simulated_failures:.2f} "
                f"[{row.mean_simulated_failures_ci_low:.2f}, "
                f"{row.mean_simulated_failures_ci_high:.2f}]"
                for row in aggregate.itertuples()
            ],
            "TC trung bình": aggregate["mean_credits_earned"].round(1),
            "HK trung bình": aggregate["mean_semesters_to_graduation"].round(2),
            "Pareto tối ưu": aggregate["pareto_frontier"].map({True: "✅", False: "—"}),
        }
    )
    st.markdown("**Tổng hợp 7 hồ sơ sinh viên × 1.000 lượt mô phỏng**")
    st.dataframe(display, use_container_width=True, hide_index=True)

    image_columns = st.columns(2)
    for col, name, caption_text in (
        (
            image_columns[0],
            "monte_carlo_pareto.png",
            "Phân tích Pareto: giảm thiểu môn không đạt vs tối đa tỷ lệ hoàn thành đúng hạn",
        ),
        (
            image_columns[1],
            "monte_carlo_rates.png",
            "Tỷ lệ tốt nghiệp / đúng hạn / khả thi theo từng chiến lược đăng ký",
        ),
    ):
        path = REPORTS_DIR / name
        if path.exists():
            with col:
                st.image(str(path), caption=caption_text, use_container_width=True)

    if by_student_path.exists():
        by_student = pd.read_csv(by_student_path)
        students = sorted(by_student["student_id"].unique())
        strategies = [v for v in by_student["strategy"].unique() if v in STRATEGY_LABELS]
        col1, col2 = st.columns(2)
        with col1:
            picked_students = st.multiselect(
                "Lọc theo hồ sơ sinh viên", students, default=students, key="mc_students"
            )
        with col2:
            picked_strategies = st.multiselect(
                "Lọc theo chiến lược", strategies, default=strategies,
                format_func=lambda v: STRATEGY_LABELS[v],
                key="mc_strategies",
            )
        filtered = by_student[
            by_student["student_id"].isin(picked_students)
            & by_student["strategy"].isin(picked_strategies)
        ]
        st.markdown("**Kết quả chi tiết theo từng sinh viên**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Sinh viên": filtered["student_id"],
                    "Chiến lược": [STRATEGY_LABELS.get(v, v) for v in filtered["strategy"]],
                    "Tỷ lệ tốt nghiệp": [_pct(v) for v in filtered["graduation_rate"]],
                    "Tỷ lệ đúng hạn": [_pct(v) for v in filtered["on_time_rate"]],
                    "Tỷ lệ khả thi": [_pct(v) for v in filtered["feasibility_rate"]],
                    "Môn không đạt TB": filtered["mean_simulated_failures"].round(2),
                    "TC trung bình": filtered["mean_credits_earned"].round(1),
                    "HK trung bình": filtered["mean_semesters_to_graduation"].round(2),
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    if paired_path.exists():
        paired = pd.read_csv(paired_path)
        st.markdown("**So sánh hiệu quả với phương án tối ưu hóa ILP**")
        st.dataframe(
            pd.DataFrame(
                {
                    "So sánh": paired["comparison"],
                    "Chỉ số": paired["metric"],
                    "Chênh lệch trung bình": paired["mean_difference"].round(4),
                    "Khoảng tin cậy 95%": [
                        f"[{low:.4f}, {high:.4f}]"
                        for low, high in zip(paired["ci_low"], paired["ci_high"])
                    ],
                    "Có sự khác biệt rõ rệt": paired["ci_excludes_zero"].map(
                        {True: "✅ Có", False: "—"}
                    ),
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Phương án tối ưu hóa ILP giảm số môn không đạt và tăng tính khả thi so với B1, "
            "nhưng B1 có tỷ lệ hoàn thành đúng hạn cao hơn — mỗi chiến lược có ưu và nhược điểm riêng."
        )
    st.caption(
        "Tái lập kết quả: `.venv/bin/python scripts/monte_carlo_strategies.py --runs 1000` · "
        "Chi tiết tại `reports/generated/monte_carlo_meta.json`."
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    inject_styles()
    st.title("Hệ thống Hỗ trợ Cảnh báo Học vụ & Tối ưu Lộ trình Tín chỉ")
    st.markdown(DATA_CHIPS, unsafe_allow_html=True)
    show_data_labels()
    curriculum = get_curriculum()
    try:
        get_bundle()
    except FileNotFoundError as err:
        st.error(str(err))
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 Nhập hồ sơ", "📊 Đánh giá", "🗺️ Lộ trình", "🎲 Mô phỏng"]
    )

    with tab1:
        mode, _, profile, progress_rows, use_ml = render_inputs(curriculum)
        if st.button("Phân tích & Đánh giá rủi ro", key="assess", type="primary"):
            if profile is None or progress_rows is None:
                st.error("Chưa có đủ dữ liệu để phân tích.")
            else:
                try:
                    with st.spinner("Đang phân tích hồ sơ..."):
                        assessment = assess_student(
                            profile, progress_rows, curriculum,
                            get_bundle(), get_rules(), use_ml=use_ml,
                        )
                    st.session_state["assessment"] = assessment
                    st.session_state["assessment_mode"] = mode
                    st.session_state.pop("plan", None)
                    st.session_state.pop("plan_results", None)
                    st.session_state.pop("plan_signature", None)
                    st.success(
                        f"Đã phân tích hồ sơ sinh viên **{profile['student_id']}** ({mode}). "
                        "Chuyển sang tab **📊 Đánh giá** để xem kết quả."
                    )
                except (InputError, ValueError, KeyError) as err:
                    st.error(str(err))

    assessment = st.session_state.get("assessment")

    with tab2:
        if assessment is None:
            st.info(
                "Chưa có kết quả phân tích. Vui lòng nhập hồ sơ ở tab **📋 Nhập hồ sơ** "
                "và bấm **Phân tích & Đánh giá rủi ro**."
            )
        else:
            st.caption(
                f"Nguồn dữ liệu: **{st.session_state.get('assessment_mode', '—')}** · "
                f"Sinh viên: **{assessment['profile']['student_id']}**"
            )
            render_assessment(assessment)

    with tab3:
        if assessment is None:
            st.info("Vui lòng hoàn thành đánh giá hồ sơ trước khi lập lộ trình học tập.")
        else:
            render_plan(assessment, curriculum)

    with tab4:
        render_simulation()

    with st.expander("ℹ️ Lưu ý về phạm vi & nguồn gốc dữ liệu"):
        st.markdown(
            "- **Dữ liệu thực tế (UCI-697)**: Mô hình được huấn luyện trên dữ liệu sinh viên "
            "Bồ Đào Nha; chưa được kiểm định trên dữ liệu sinh viên NTU.\n"
            "- **Dữ liệu mô phỏng**: Chương trình đào tạo, tiến độ học tập, hồ sơ sinh viên mẫu "
            "và kết quả mô phỏng Monte Carlo đều là dữ liệu tổng hợp.\n"
            "- **Giả định kịch bản**: Hệ số tải học tập, hệ số học lại, các trọng số tối ưu hóa "
            "và ngưỡng tín chỉ là ước lượng thử nghiệm, chưa được hiệu chỉnh thực tế.\n"
            "- Ở chế độ nhập thủ công / tải CSV, không đủ thông tin để ước tính xác suất rủi ro; "
            "lộ trình sử dụng tỷ lệ nền theo nhóm năng lực.\n"
            "- **Không sử dụng kết quả này làm cơ sở cho các quyết định học vụ chính thức.**"
        )


if __name__ == "__main__":
    main()
