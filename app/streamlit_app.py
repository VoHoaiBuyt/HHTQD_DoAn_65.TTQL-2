"""Streamlit UI cho hệ thống cảnh báo học vụ và lộ trình tín chỉ.

Bố cục "kết quả trước, chi tiết sau":
  • Thanh bên: chọn nguồn dữ liệu + hồ sơ (hồ sơ mẫu tự phân tích ngay).
  • Bảng tổng quan cố định trên cùng: mức rủi ro, tiến độ, kết luận nhanh, phương án gợi ý.
  • 4 tab chi tiết: Rủi ro & học phần · Lộ trình · Mô phỏng · Dữ liệu đầu vào.
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
GRADUATION_CREDITS = 128

# ── Nhãn hiển thị (chỉ dùng cho giao diện) ───────────────────────────────────

STRATEGY_LABELS = {
    "ILP": "ILP — Tối ưu hóa",
    "B1": "B1 — Đúng lộ trình + học lại",
    "B2": "B2 — Tối đa 18 tín chỉ",
    "B3": "B3 — Cố định 15 tín chỉ",
}
# Màu cố định theo chiến lược (không đổi khi lọc).
STRATEGY_COLORS = {"ILP": "#2a78d6", "B1": "#eb6834", "B2": "#eda100", "B3": "#1baf7a"}

RISK_STYLE: dict[str, dict[str, str]] = {
    "Thấp": {"bg": "#e7f6e7", "fg": "#0a6b0a", "bar": "#0ca30c", "icon": "🟢"},
    "Trung bình": {"bg": "#fff4d6", "fg": "#8a5a00", "bar": "#fab219", "icon": "🟡"},
    "Cao": {"bg": "#fde8e8", "fg": "#a11d1d", "bar": "#d03b3b", "icon": "🔴"},
    "Chưa ước lượng": {"bg": "#eef1f5", "fg": "#475569", "bar": "#94a3b8", "icon": "⚪"},
}

_STATUS_VI = {
    "completed": "✅ Đã đạt",
    "failed": "❌ Chưa đạt",
    "in_progress": "⏳ Đang học",
    "not_taken": "⬜ Chưa học",
}

_PLAN_STATUS_VI = {
    "optimal": "Tối ưu ✅",
    "best_effort": "Nỗ lực tối đa ⚠️",
    "infeasible_data_error": "Không khả thi ❌",
    "graduation_ready": "Đủ ĐK tốt nghiệp 🎓",
    "no_eligible_courses": "Không có môn ĐK",
}

_FALLBACK_VI = {
    "normal": "Bình thường",
    "relaxed_minimum": "Nới sàn tín chỉ",
    "minimum_zero": "Không có sàn",
    "no_forced_retakes": "Không ép học lại",
    "relaxed_fail_cap": "Nới ngưỡng trượt",
    "at_least_one_course": "Ít nhất 1 môn",
}

FEATURE_VI = {
    "Admission grade": "Điểm xét tuyển",
    "Age at enrollment": "Tuổi nhập học",
    "Application mode": "Phương thức xét tuyển",
    "Application order": "Thứ tự nguyện vọng",
    "Course": "Ngành (mã UCI)",
    "Curricular units 1st sem (approved)": "Số môn ĐẠT ở HK1",
    "Curricular units 1st sem (credited)": "Số môn được công nhận HK1",
    "Curricular units 1st sem (enrolled)": "Số môn ĐĂNG KÝ ở HK1",
    "Curricular units 1st sem (evaluations)": "Số lần dự thi HK1",
    "Curricular units 1st sem (grade)": "Điểm TB HK1",
    "Curricular units 1st sem (without evaluations)": "Số môn bỏ thi HK1",
    "Daytime/evening attendance": "Học ca ngày/tối",
    "Displaced": "Học xa nhà",
    "Educational special needs": "Nhu cầu hỗ trợ đặc biệt",
    "Father's occupation": "Nghề của cha",
    "Father's qualification": "Trình độ của cha",
    "Gender": "Giới tính",
    "International": "SV quốc tế",
    "Marital status": "Tình trạng hôn nhân",
    "Mother's occupation": "Nghề của mẹ",
    "Mother's qualification": "Trình độ của mẹ",
    "Nacionality": "Quốc tịch",
    "Previous qualification": "Bằng cấp trước",
    "Previous qualification (grade)": "Điểm bằng cấp trước",
}

# ── CSS ───────────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """
<style>
.stApp { background: #f6f8fb; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1280px; }
.stApp h1 { color: #0f172a; font-size: 1.6rem !important; font-weight: 800; letter-spacing: -0.02em;
            line-height: 1.25 !important; padding-bottom: 0.2rem !important; }
main.stMain h3 { border-left: 4px solid #2a78d6; padding-left: 0.6rem; font-size: 1.02rem;
                 font-weight: 700; margin-top: 1.1rem; margin-bottom: 0.5rem; color: #1e293b; }
div[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
div[data-testid="stMetric"] { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
                              padding: 0.75rem 0.9rem; }
div[data-testid="stMetricLabel"] p { color: #64748b; font-size: 0.74rem; font-weight: 700;
                                     text-transform: uppercase; letter-spacing: 0.05em; }
div[data-testid="stMetricValue"] { color: #0f172a; font-weight: 800; font-size: 1.35rem; }
.stButton > button { border-radius: 10px; font-weight: 600; }
div[data-testid="stTabs"] button[role="tab"] p { font-weight: 700; font-size: 0.95rem; }
div[data-testid="stDataFrame"] { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.stAlert, div[data-testid="stAlert"] { border-radius: 10px; }
div[data-testid="stExpander"] { border: 1px solid #e2e8f0 !important; border-radius: 10px !important;
                                background: #fff; }

/* Thẻ KPI tự vẽ */
.kpi { border-radius: 14px; padding: 14px 16px; height: 100%; border: 1px solid #e2e8f0; background: #fff; }
.kpi .lbl { font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi .val { font-size: 1.7rem; font-weight: 800; line-height: 1.2; margin-top: 4px; color: #0f172a; }
.kpi .sub { font-size: 0.8rem; color: #475569; margin-top: 2px; }
.kpi .bar { height: 8px; border-radius: 99px; background: #e2e8f0; margin-top: 8px; overflow: hidden; }
.kpi .bar > span { display: block; height: 100%; border-radius: 99px; }

/* Quy trình DSS */
.flow { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin: 2px 0 14px 0; }
.flow .step { background: #fff; border: 1px solid #dbe3ee; border-radius: 999px; padding: 4px 12px;
              font-size: 0.8rem; font-weight: 600; color: #334155; }
.flow .arr { color: #94a3b8; font-weight: 700; }

/* Hộp kết luận */
.verdict { background: #fff; border: 1px solid #e2e8f0; border-left: 5px solid #2a78d6;
           border-radius: 12px; padding: 12px 16px; margin-top: 12px; }
.verdict h4 { margin: 0 0 6px 0; font-size: 0.95rem; color: #0f172a; }
.verdict ul { margin: 0; padding-left: 1.1rem; }
.verdict li { margin: 3px 0; color: #1e293b; font-size: 0.92rem; }
</style>
"""

FLOW_HTML = (
    '<div class="flow">'
    '<span class="step">📥 Dữ liệu hồ sơ</span><span class="arr">→</span>'
    '<span class="step">🤖 Học máy dự báo rủi ro</span><span class="arr">→</span>'
    '<span class="step">📏 Luật quy chế lọc môn</span><span class="arr">→</span>'
    '<span class="step">🧮 Tối ưu ILP chọn môn</span><span class="arr">→</span>'
    '<span class="step">🎲 Mô phỏng Monte Carlo</span>'
    "</div>"
)

# ── Tiện ích ──────────────────────────────────────────────────────────────────


def inject_styles() -> None:
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
    # Trang đã là tiếng Việt: chặn Google Translate tự dịch (dịch sai, vd. "Nhập thủ công" → "khóa công").
    components.html(
        """<script>
        const d = window.parent.document;
        d.documentElement.setAttribute("translate", "no");
        d.documentElement.classList.add("notranslate");
        d.documentElement.lang = "vi";
        if (!d.querySelector('meta[name="google"]')) {
            const m = d.createElement("meta"); m.name = "google"; m.content = "notranslate"; d.head.appendChild(m);
        }
        </script>""",
        height=0,
    )


def _pct(value: float) -> str:
    return f"{float(value):.1%}"


def kpi_card(label: str, value: str, sub: str = "", *, bg: str = "#fff", fg: str = "#0f172a",
             bar: float | None = None, bar_color: str = "#2a78d6") -> str:
    bar_html = (
        f'<div class="bar"><span style="width:{max(0.0, min(1.0, bar)) * 100:.0f}%;'
        f'background:{bar_color}"></span></div>'
        if bar is not None
        else ""
    )
    return (
        f'<div class="kpi" style="background:{bg}">'
        f'<div class="lbl">{label}</div>'
        f'<div class="val" style="color:{fg}">{value}</div>'
        f'<div class="sub">{sub}</div>{bar_html}</div>'
    )


def _display_with_status(df: pd.DataFrame) -> pd.DataFrame:
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


def _pretty_feature(name: str) -> str:
    short = name.split("__", 1)[-1]
    if name.startswith("categorical__"):
        base, _, value = short.rpartition("_")
        return f"{FEATURE_VI.get(base, base)} = {value}" if base else short
    return FEATURE_VI.get(short, short)


# ── Tài nguyên cache ──────────────────────────────────────────────────────────


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
    """LinearExplainer cho pipeline LR trên nền dữ liệu UCI-697."""
    try:
        import shap
    except ImportError:
        return None
    from src.analysis.risk_to_plan_exploration import _load_real_data

    bundle = get_bundle()
    data, features, _, _ = _load_real_data()
    background = data[features].sample(n=min(120, len(data)), random_state=int(bundle["seed"]))
    pipeline = bundle["dropout_model"]
    preprocessor = pipeline.named_steps["columntransformer"]
    model = pipeline.named_steps["logisticregression"]
    transformed = preprocessor.transform(background)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    explainer = shap.LinearExplainer(model, shap.maskers.Independent(transformed, max_samples=200))
    return {
        "explainer": explainer,
        "preprocessor": preprocessor,
        "feature_names": [str(n) for n in preprocessor.get_feature_names_out()],
        "dropout_index": list(model.classes_).index("Dropout"),
    }


@st.cache_data(show_spinner=False)
def load_mc_tables() -> dict[str, pd.DataFrame | None]:
    def read(name: str) -> pd.DataFrame | None:
        path = REPORTS_DIR / name
        return pd.read_csv(path) if path.exists() else None

    return {
        "summary": read("monte_carlo_summary.csv"),
        "by_student": read("monte_carlo_by_student.csv"),
        "paired": read("monte_carlo_paired_differences.csv"),
    }


# ── SHAP ──────────────────────────────────────────────────────────────────────


def explain_dropout(profile: dict, top_n: int = 8) -> pd.DataFrame | None:
    context = get_shap_context()
    if context is None:
        return None
    features = get_bundle()["features"]
    frame = pd.DataFrame([{feat: profile[feat] for feat in features}], columns=features)
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
            "feature": [_pretty_feature(n) for n in context["feature_names"]],
            "shap_value": values[0],
        }
    )
    contributions["abs_shap"] = contributions["shap_value"].abs()
    return contributions.sort_values("abs_shap", ascending=False).head(top_n)


def shap_for(assessment: dict) -> pd.DataFrame | None:
    """SHAP cho hồ sơ hiện tại, lưu trong session để không tính lại."""
    if not assessment["risk_estimated"]:
        return None
    key = f"shap::{assessment['profile'].get('student_id')}"
    if key not in st.session_state:
        try:
            st.session_state[key] = explain_dropout(assessment["profile"])
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
            st.session_state[key] = None
    return st.session_state[key]


def render_shap_chart(table: pd.DataFrame) -> None:
    df = table.copy()
    df["Ảnh hưởng"] = df["shap_value"].apply(lambda v: "Làm TĂNG rủi ro" if v > 0 else "Làm GIẢM rủi ro")
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("shap_value:Q", title="← giảm rủi ro  ·  mức ảnh hưởng (SHAP)  ·  tăng rủi ro →",
                    axis=alt.Axis(grid=True, gridColor="#eef2f7")),
            y=alt.Y("feature:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240, labelFontSize=12)),
            color=alt.Color(
                "Ảnh hưởng:N",
                scale=alt.Scale(domain=["Làm TĂNG rủi ro", "Làm GIẢM rủi ro"], range=["#eb6834", "#2a78d6"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[alt.Tooltip("feature:N", title="Yếu tố"),
                     alt.Tooltip("shap_value:Q", format="+.3f", title="SHAP")],
        )
        .properties(height=alt.Step(30))
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#94a3b8").encode(x="x:Q")
    st.altair_chart((bars + zero).configure_view(strokeWidth=0), use_container_width=True)


# ── Lập phương án ─────────────────────────────────────────────────────────────


def _plan_signature(assessment: dict, budgets: list[int], load_lambda: float,
                    fmax: float, enforce_cap: bool) -> tuple:
    p = assessment["profile"]
    return (
        str(p.get("student_id")),
        int(p.get("current_semester", 0)),
        round(float(load_lambda), 4),
        tuple(sorted(budgets)),
        round(float(fmax), 4),
        bool(enforce_cap),
    )


def default_plan_params(assessment: dict) -> tuple[list[int], float, float, bool]:
    rule_result = assessment["rule_result"]
    targets = [int(v) for v in get_rules()["scenario_credit_targets"]["values"]]
    return targets, 0.1, float(rule_result["expected_failed_course_cap"]), bool(rule_result["enforce_cap"])


def run_plans(assessment: dict, budgets: list[int], load_lambda: float, fmax: float, enforce_cap: bool) -> None:
    plans = build_plans(
        assessment, get_curriculum(), get_bundle(), get_rules(),
        budgets=sorted(budgets), load_lambda=load_lambda,
        expected_fail_cap_override=fmax, enforce_cap_override=enforce_cap,
    )
    st.session_state["plan_results"] = plans
    st.session_state["plan_signature"] = _plan_signature(assessment, budgets, load_lambda, fmax, enforce_cap)


def recommend_plan(plans: list[dict]) -> dict | None:
    """Gợi ý tham khảo: phương án 'Tối ưu' có tín chỉ đạt kỳ vọng cao nhất;
    nếu không có thì chọn phương án ít môn trượt kỳ vọng nhất."""
    if not plans:
        return None
    optimal = [p for p in plans if p["result"].get("status") == "optimal"]
    if optimal:
        return max(optimal, key=lambda p: float(p["result"].get("expected_credits_passed", 0.0)))
    usable = [p for p in plans if p["result"].get("selected_course_ids")]
    if usable:
        return min(usable, key=lambda p: float(p["result"].get("expected_failed_courses", 0.0)))
    return plans[0]


# ── Thanh bên ─────────────────────────────────────────────────────────────────


def render_sidebar(curriculum: dict) -> tuple[str, str | None]:
    sb = st.sidebar
    sb.markdown("### 🎓 Trợ lý Học vụ")
    sb.caption("Đồ án HHTQĐ · Nhóm 1")
    mode = sb.radio(
        "① Nguồn dữ liệu",
        ["Hồ sơ mẫu (Có sẵn)", "Nhập dữ liệu thủ công", "Tải lên file CSV"],
        key="input_mode",
    )
    persona_id = None
    if mode == "Hồ sơ mẫu (Có sẵn)":
        profiles = curriculum["profiles"]
        labels = dict(zip(profiles["student_id"].astype(str), profiles["persona"].astype(str)))
        persona_id = sb.selectbox(
            "② Chọn sinh viên",
            sorted(labels),
            format_func=lambda sid: f"{sid} · {labels.get(sid, '')}",
            key="persona_id",
        )
        sb.caption("Hồ sơ mẫu được **phân tích tự động** ngay khi chọn.")
    else:
        sb.caption("② Nhập dữ liệu ở tab **📋 Dữ liệu đầu vào**, rồi bấm nút bên dưới.")
    sb.button("🔍 Phân tích & Đánh giá rủi ro", key="assess", type="primary", use_container_width=True)
    sb.divider()
    with sb.expander("ℹ️ Nguồn dữ liệu & giới hạn"):
        st.markdown(
            "- **Thực tế (UCI-697):** 4.424 SV Bồ Đào Nha — dùng huấn luyện mô hình.\n"
            "- **Mô phỏng:** CTĐT 48 môn/128 TC và 8 hồ sơ mẫu.\n"
            "- **Giả định:** hệ số tải, độ khó, trọng số tối ưu.\n"
            "- Chỉ **khuyến nghị** — không thay quy chế NTU, không tự động hạn chế đăng ký."
        )
    return mode, persona_id


# ── Tab: Dữ liệu đầu vào ──────────────────────────────────────────────────────


def render_inputs(curriculum: dict, mode: str, persona_id: str | None):
    if mode == "Hồ sơ mẫu (Có sẵn)":
        profile, rows = persona_payload(curriculum, persona_id)
        st.markdown(f"### Hồ sơ {persona_id} · {profile.get('persona', '')}")
        if str(profile.get("persona_purpose") or "").strip():
            st.caption(f"Tình huống minh họa: {profile['persona_purpose']}")
        st.dataframe(
            _display_with_status(progress_frame(rows)),
            use_container_width=True, hide_index=True, height=320,
            column_config={
                "student_id": st.column_config.TextColumn("Mã SV"),
                "course_id": st.column_config.TextColumn("Mã học phần"),
                "status": st.column_config.TextColumn("Trạng thái"),
                "grade_10": st.column_config.NumberColumn("Điểm hệ 10", format="%.1f"),
                "attempt_count": st.column_config.NumberColumn("Số lần học", format="%d"),
                "semester_taken": st.column_config.NumberColumn("Học kỳ", format="%d"),
            },
        )
        return profile, rows, True

    if mode == "Tải lên file CSV":
        st.markdown("### Tải lên hồ sơ")
        col1, col2 = st.columns(2)
        with col1:
            profile_file = st.file_uploader("Tệp hồ sơ (profile.csv — 1 dòng)", type="csv", key="profile_csv")
            st.download_button(
                "⬇️ Tải mẫu profile.csv",
                curriculum["profiles"].head(1).to_csv(index=False).encode("utf-8-sig"),
                file_name="profile_template.csv", key="download_profile",
            )
        with col2:
            progress_file = st.file_uploader("Tệp tiến độ (progress.csv)", type="csv", key="progress_csv")
            st.download_button(
                "⬇️ Tải mẫu progress.csv",
                curriculum["progress"][curriculum["progress"]["student_id"] == "S002"]
                .to_csv(index=False).encode("utf-8-sig"),
                file_name="progress_template.csv", key="download_progress",
            )
        if profile_file is None or progress_file is None:
            st.info("Tải lên **cả hai** tệp CSV rồi bấm **🔍 Phân tích** ở thanh bên.")
            return None, None, False
        try:
            profile_frame_csv = pd.read_csv(profile_file, encoding="utf-8-sig")
            progress_csv = pd.read_csv(progress_file, encoding="utf-8-sig")
            if profile_frame_csv.empty:
                raise InputError("Tệp profile.csv không có dòng dữ liệu.")
            profile = normalize_profile(profile_frame_csv.iloc[0].to_dict())
            rows = normalize_progress_rows(
                progress_csv.to_dict("records"), known_course_ids=curriculum["course_by_id"].keys()
            )
        except (InputError, pd.errors.ParserError, UnicodeDecodeError) as err:
            st.error(str(err))
            return None, None, False
        return profile, rows, False

    st.markdown("### Nhập dữ liệu thủ công")
    st.caption("Chế độ này thiếu đặc trưng cho mô hình học máy → hệ thống dùng tỷ lệ đạt nền theo năng lực HK1.")
    col1, col2, col3 = st.columns(3)
    with col1:
        student_id = st.text_input("Mã sinh viên", value="S002", key="manual_id")
        semester = st.number_input("Học kỳ hiện tại", min_value=1, max_value=8, value=4, key="manual_sem")
        gpa = st.number_input("GPA (hệ 4)", min_value=0.0, max_value=4.0, value=2.6, step=0.01, key="manual_gpa")
    with col2:
        cumulative = st.number_input("Tín chỉ tích lũy", min_value=0, max_value=300, value=64, key="manual_credits")
        failed_count = st.number_input("Số môn chưa đạt", min_value=0, max_value=48, value=2, key="manual_failed")
    with col3:
        hk1_enrolled = st.number_input("Số môn HK1 đăng ký", min_value=0, max_value=30, value=7, key="manual_hk1_enrolled")
        hk1_approved = st.number_input("Số môn HK1 đạt", min_value=0, max_value=30, value=6, key="manual_hk1_approved")
        hk1_grade = st.number_input("Điểm TB HK1 (thang 20)", min_value=0.0, max_value=20.0, value=12.0,
                                    step=0.1, key="manual_hk1_grade")

    if "manual_progress" not in st.session_state:
        _, rows = persona_payload(curriculum, "S002")
        st.session_state["manual_progress"] = progress_frame(rows)
    edited = st.data_editor(
        st.session_state["manual_progress"],
        key="progress_editor", use_container_width=True, hide_index=True, num_rows="fixed",
        column_config={
            "course_id": st.column_config.TextColumn("Mã học phần", disabled=True),
            "status": st.column_config.SelectboxColumn("Trạng thái", options=sorted(ALLOWED_STATUSES), required=True),
            "grade_10": st.column_config.NumberColumn("Điểm hệ 10", min_value=0.0, max_value=10.0, step=0.1),
            "attempt_count": st.column_config.NumberColumn("Số lần học", min_value=0, max_value=10, step=1),
            "semester_taken": st.column_config.NumberColumn("Học kỳ đã học", min_value=1, max_value=8, step=1),
        },
    )
    try:
        profile = normalize_profile(
            {
                "student_id": student_id, "current_semester": semester, "gpa": gpa,
                "cumulative_credits": cumulative, "failed_courses_count": failed_count,
                "hk1_enrolled": hk1_enrolled, "hk1_approved": hk1_approved, "hk1_grade": hk1_grade,
            }
        )
        progress_rows = [
            {**row, "student_id": profile["student_id"]}
            for row in normalize_progress_rows(
                edited.to_dict("records"), known_course_ids=curriculum["course_by_id"].keys()
            )
        ]
    except InputError as err:
        st.error(str(err))
        return None, None, False
    return profile, progress_rows, False


# ── Phân tích ─────────────────────────────────────────────────────────────────


def run_assessment(profile: dict, rows: list[dict], use_ml: bool, mode: str, signature: tuple) -> None:
    with st.spinner("Đang phân tích hồ sơ…"):
        assessment = assess_student(profile, rows, get_curriculum(), get_bundle(), get_rules(), use_ml=use_ml)
    st.session_state["assessment"] = assessment
    st.session_state["assessment_mode"] = mode
    st.session_state["assessment_signature"] = signature
    # Xóa kết quả và giá trị widget của hồ sơ trước để tham số trở về mặc định của hồ sơ mới.
    for key in ("plan", "plan_results", "plan_signature", "plan_budgets", "load_lambda",
                "plan_fmax", "plan_enforce_cap", "plan_detail_budget"):
        st.session_state.pop(key, None)
    with st.spinner("Đang tối ưu lộ trình…"):
        run_plans(assessment, *default_plan_params(assessment))


# ── Bảng tổng quan ────────────────────────────────────────────────────────────


def render_overview(assessment: dict) -> None:
    profile = assessment["profile"]
    rule_result = assessment["rule_result"]
    stats = rule_result.get("progress_stats", {})
    label = assessment["risk_label"]
    style = RISK_STYLE.get(label, RISK_STYLE["Chưa ước lượng"])

    persona = str(profile.get("persona") or "").strip()
    st.markdown(f"#### 👤 {profile.get('student_id')}" + (f" · {persona}" if persona else "")
                + f" — chuẩn bị đăng ký học kỳ {int(profile.get('current_semester', 0)) + 1}")

    earned = int(stats.get("credits_earned", 0) or 0)
    eligible_n = len(rule_result["eligible_courses"])
    failed_n = len(rule_result.get("failed_courses", []))
    p = assessment["p_dropout_calibrated"]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        kpi_card("Mức cảnh báo rủi ro", f"{style['icon']} {label}",
                 "Theo mô hình học máy" if assessment["risk_estimated"] else "Thiếu dữ liệu cho mô hình",
                 bg=style["bg"], fg=style["fg"]),
        unsafe_allow_html=True,
    )
    c2.markdown(
        kpi_card("Xác suất bỏ học", "—" if p is None else _pct(p),
                 "Đã hiệu chuẩn (Isotonic)" if p is not None else
                 f"Tỷ lệ đạt nền HK1: {_pct(assessment['p_pass_m3_prime'] or 0)}",
                 bar=None if p is None else p, bar_color=style["bar"]),
        unsafe_allow_html=True,
    )
    c3.markdown(
        kpi_card("Tiến độ tín chỉ", f"{earned}/{GRADUATION_CREDITS}",
                 f"Còn ≥ {stats.get('minimum_semesters_remaining', '—')} học kỳ",
                 bar=earned / GRADUATION_CREDITS, bar_color="#2a78d6"),
        unsafe_allow_html=True,
    )
    c4.markdown(
        kpi_card("Học phần kỳ tới", f"{eligible_n} môn",
                 f"được đăng ký · {failed_n} môn cần học lại",
                 fg="#0f172a" if failed_n == 0 else "#a11d1d"),
        unsafe_allow_html=True,
    )

    # Kết luận nhanh
    bullets: list[str] = []
    if assessment["risk_estimated"]:
        line = f"{style['icon']} Nguy cơ bỏ học **{label}** (xác suất {_pct(p)})."
        shap_table = shap_for(assessment)
        if shap_table is not None and not shap_table.empty:
            # Ưu tiên yếu tố dạng số (dễ hiểu) thay vì mã danh mục như "Nghề của cha = 4".
            readable = shap_table[~shap_table["feature"].str.contains(" = ", regex=False)]
            top = (readable if not readable.empty else shap_table).iloc[0]
            direction = "đẩy rủi ro LÊN" if top["shap_value"] > 0 else "kéo rủi ro XUỐNG"
            line += f" Yếu tố ảnh hưởng lớn nhất: *{top['feature']}* ({direction})."
        bullets.append(line)
    else:
        bullets.append("⚪ Chưa ước lượng nguy cơ bằng học máy (thiếu đặc trưng) — lộ trình dùng tỷ lệ đạt nền theo năng lực HK1.")
    flags = rule_result.get("academic_flags", [])
    if flags:
        bullets.append("⚠️ Cảnh báo học vụ: " + "; ".join(f["message"] for f in flags))
    else:
        bullets.append("✅ Không có cảnh báo học vụ theo quy chế.")

    plans = st.session_state.get("plan_results") or []
    best = recommend_plan(plans)
    if best is not None:
        res = best["result"]
        status = res.get("status")
        if status == "graduation_ready":
            bullets.append("🎓 Đã đủ tín chỉ tốt nghiệp — không cần đăng ký thêm.")
        elif res.get("selected_course_ids"):
            text = (
                f"🗺️ Gợi ý tham khảo: đăng ký **{res.get('selected_credits', 0)} tín chỉ** "
                f"({len(res['selected_course_ids'])} môn) → dự báo đạt "
                f"**{float(res.get('expected_credits_passed', 0)):.1f} TC**, "
                f"trượt kỳ vọng **{float(res.get('expected_failed_courses', 0)):.2f} môn**."
            )
            if status != "optimal":
                text += " ⚠️ Mọi phương án đều vượt ngưỡng rủi ro → **nên gặp cố vấn học tập**."
            bullets.append(text)
        else:
            bullets.append("🗺️ Không tìm được phương án phù hợp — cần kiểm tra lại tiên quyết/lịch mở môn.")

    items = "".join(f"<li>{_md_inline(b)}</li>" for b in bullets)
    st.markdown(f'<div class="verdict"><h4>📌 Kết luận nhanh</h4><ul>{items}</ul></div>',
                unsafe_allow_html=True)


def _md_inline(text: str) -> str:
    """Chuyển **đậm** và *nghiêng* sang HTML cho hộp kết luận."""
    import re

    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)


# ── Tab 1: Rủi ro & học phần ──────────────────────────────────────────────────


def render_risk_and_courses(assessment: dict) -> None:
    rule_result = assessment["rule_result"]
    left, right = st.columns([1.15, 1])

    with left:
        st.markdown("### Vì sao mô hình đánh giá như vậy? (SHAP)")
        if not assessment["risk_estimated"]:
            st.info("Chỉ có ở chế độ **Hồ sơ mẫu** (đủ 24 đặc trưng cho mô hình).")
        else:
            table = shap_for(assessment)
            if table is None:
                st.info("Không tính được SHAP (thiếu thư viện `shap`).")
            else:
                render_shap_chart(table.assign(shap_value=table["shap_value"].round(4)))
                st.caption("🟧 Cam: đẩy rủi ro **lên** · 🟦 Xanh: kéo rủi ro **xuống**. "
                           "Đây là giải thích mô hình, **không phải nhân quả**.")
        if assessment["p_pass_model"] is not None:
            st.caption(
                f"Tỷ lệ đạt môn dự báo (Random Forest): **{_pct(assessment['p_pass_model'])}** · "
                f"Tỷ lệ đạt nền theo nhóm năng lực HK1 ({assessment['ability_tier']}): "
                f"**{_pct(assessment['p_pass_m3_prime'])}**"
            )

    with right:
        st.markdown("### Kiểm tra theo quy chế")
        flags = rule_result.get("academic_flags", [])
        edges = rule_result.get("edge_case_flags", [])
        if not flags and not edges:
            st.success("Không có cảnh báo hay lưu ý nào.")
        for flag in flags:
            st.warning(flag["message"], icon="⚠️")
        for flag in edges:
            (st.info if flag.get("severity") == "info" else st.warning)(flag["message"], icon="📌")

        stats = rule_result.get("progress_stats", {})
        if stats:
            s1, s2, s3 = st.columns(3)
            s1.metric("TC còn lại", stats.get("credits_remaining", "—"))
            s2.metric("Chậm tiến độ", f"{stats.get('credits_behind_expected', '—')} TC")
            s3.metric("Chuỗi tiên quyết", f"{stats.get('longest_strict_prerequisite_chain', '—')} kỳ",
                      help="Chuỗi môn tiên quyết dài nhất chưa hoàn thành → số kỳ tối thiểu.")

    st.markdown("### Học phần kỳ tới")
    eligible = pd.DataFrame(rule_result["eligible_courses"])
    failed = pd.DataFrame(rule_result.get("failed_courses", []))
    blocked_rows = [
        {
            "course_id": c["course_id"],
            "course_name": c.get("course_name", ""),
            "credits": c["credits"],
            "unmet": ", ".join(item["prerequisite_id"] for item in c.get("unmet_prerequisites", [])),
        }
        for c in rule_result.get("blocked_courses", [])
    ]
    view = st.radio(
        "Xem",
        [f"✅ Được đăng ký ({len(eligible)})", f"❌ Cần học lại ({len(failed)})", f"🔒 Bị chặn ({len(blocked_rows)})"],
        horizontal=True, label_visibility="collapsed", key="course_view",
    )
    cfg = {
        "course_id": st.column_config.TextColumn("Mã"),
        "course_name": st.column_config.TextColumn("Tên học phần"),
        "credits": st.column_config.NumberColumn("TC", format="%d"),
        "group": st.column_config.TextColumn("Nhóm môn"),
        "status": st.column_config.TextColumn("Trạng thái"),
        "planned_semester": st.column_config.NumberColumn("HK theo CTĐT", format="%d"),
        "attempt_count": st.column_config.NumberColumn("Đã học (lần)", format="%d"),
        "unmet": st.column_config.TextColumn("Thiếu môn tiên quyết"),
    }
    if view.startswith("✅"):
        if eligible.empty:
            st.warning("Không có học phần đủ điều kiện đăng ký trong kỳ tới.")
        else:
            st.dataframe(_display_with_status(eligible[["course_id", "course_name", "credits", "group", "status",
                                                        "planned_semester"]]),
                         use_container_width=True, hide_index=True, column_config=cfg)
    elif view.startswith("❌"):
        if failed.empty:
            st.success("Không có môn cần học lại. 👍")
        else:
            st.dataframe(failed[["course_id", "course_name", "credits", "attempt_count"]],
                         use_container_width=True, hide_index=True, column_config=cfg)
    else:
        if not blocked_rows:
            st.success("Không có môn bị chặn bởi tiên quyết.")
        else:
            st.dataframe(pd.DataFrame(blocked_rows), use_container_width=True, hide_index=True, column_config=cfg)


# ── Tab 2: Lộ trình ───────────────────────────────────────────────────────────


def render_plan_comparison_chart(plans: list[dict]) -> None:
    rows = []
    for plan in plans:
        r = plan["result"]
        label = f"{plan['budget']} TC"
        rows += [
            {"Mức": label, "Chỉ số": "Tín chỉ đăng ký", "Giá trị": r.get("selected_credits", 0)},
            {"Mức": label, "Chỉ số": "Tín chỉ dự báo đạt",
             "Giá trị": round(float(r.get("expected_credits_passed", 0.0)), 2)},
        ]
    chart = (
        alt.Chart(pd.DataFrame(rows))
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Mức:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Giá trị:Q", title="Tín chỉ", axis=alt.Axis(gridColor="#eef2f7")),
            color=alt.Color("Chỉ số:N",
                            scale=alt.Scale(domain=["Tín chỉ đăng ký", "Tín chỉ dự báo đạt"],
                                            range=["#2a78d6", "#1baf7a"]),
                            legend=alt.Legend(title=None, orient="top")),
            xOffset="Chỉ số:N",
            tooltip=["Mức:N", "Chỉ số:N", alt.Tooltip("Giá trị:Q", format=".2f")],
        )
        .properties(height=250)
    )
    st.altair_chart(chart.configure_view(strokeWidth=0), use_container_width=True)


def render_plan(assessment: dict) -> None:
    rule_result = assessment["rule_result"]
    targets, d_lambda, d_fmax, d_enforce = default_plan_params(assessment)

    with st.expander("⚙️ Tùy chỉnh tham số (What-if) — mặc định đã chạy sẵn", expanded=False):
        col1, col2, col3, col4 = st.columns([1.4, 1.4, 1, 1])
        with col1:
            budgets = st.multiselect("Mức tín chỉ so sánh", targets, default=targets, key="plan_budgets")
        with col2:
            load_lambda = st.slider("Hệ số tải học tập λ (giả định)", 0.0, 0.5, d_lambda, 0.05, key="load_lambda",
                                    help="Học càng nhiều tín chỉ thì xác suất qua môn giảm bao nhiêu.")
        with col3:
            fmax = st.number_input("Ngưỡng môn trượt cho phép", 0.0, 6.0, d_fmax, 0.5, key="plan_fmax")
        with col4:
            enforce_cap = st.checkbox("Áp trần tín chỉ khuyến nghị", value=d_enforce, key="plan_enforce_cap",
                                      help="Mặc định TẮT: hệ thống chỉ cảnh báo, không tự giới hạn.")
        clicked = st.button("🔄 Lập & so sánh lộ trình", key="run_plan", type="primary")

    if not budgets:
        st.warning("Chọn ít nhất một mức tín chỉ.")
        return
    signature = _plan_signature(assessment, budgets, load_lambda, fmax, enforce_cap)
    if clicked:
        try:
            with st.spinner("Đang tối ưu lộ trình học tập…"):
                run_plans(assessment, budgets, load_lambda, fmax, enforce_cap)
        except (InputError, ValueError, KeyError) as err:
            st.error(str(err))
            return

    plans = st.session_state.get("plan_results")
    if not plans:
        st.info("Bấm **🔄 Lập & so sánh lộ trình** trong mục tham số.")
        return
    if st.session_state.get("plan_signature") != signature:
        st.warning("Tham số đã đổi — bấm **🔄 Lập & so sánh lộ trình** để cập nhật kết quả.")

    best = recommend_plan(plans)
    left, right = st.columns([1, 1.25])
    with left:
        st.markdown("### So sánh nhanh các mức tín chỉ")
        render_plan_comparison_chart(plans)
        st.caption("Khoảng cách giữa 2 cột = số tín chỉ **có thể trượt**. "
                   "Nếu tăng tín chỉ mà cột xanh lá gần như không tăng → học thêm không đáng.")
    with right:
        st.markdown("### Bảng so sánh")
        comparison = pd.DataFrame(
            [
                {
                    "Mức": f"{'⭐ ' if plan is best else ''}{plan['budget']} TC",
                    "Kết quả": _PLAN_STATUS_VI.get(plan["result"].get("status", ""), plan["result"].get("status", "—")),
                    "TC đăng ký": plan["result"].get("selected_credits", 0),
                    "TC đạt": round(float(plan["result"].get("expected_credits_passed", 0.0)), 1),
                    "Môn trượt": round(float(plan["result"].get("expected_failed_courses", 0.0)), 2),
                }
                for plan in plans
            ]
        )
        st.dataframe(comparison, use_container_width=True, hide_index=True)
        cap = float(plans[0]["result"].get("expected_fail_cap", 0.0))
        fallback = {_FALLBACK_VI.get(p["result"].get("fallback_mode", "normal"), "Bình thường") for p in plans}
        st.caption(f"Ngưỡng môn trượt cho phép: **{cap:g}** · Chế độ dự phòng: {', '.join(sorted(fallback))}.  \n"
                   "⭐ = gợi ý tham khảo: phương án *Tối ưu* có nhiều tín chỉ đạt nhất "
                   "(nếu không có thì chọn phương án ít trượt nhất).")

    st.markdown("### Chi tiết phương án")
    budget_options = [p["budget"] for p in plans]
    detail_budget = st.radio(
        "Phương án", budget_options,
        index=budget_options.index(best["budget"]) if best else 0,
        format_func=lambda v: f"{v} tín chỉ" + (" ⭐" if best and v == best["budget"] else ""),
        horizontal=True, label_visibility="collapsed",
        key=f"plan_detail_budget_{assessment['profile'].get('student_id')}",
    )
    plan = next(item for item in plans if item["budget"] == detail_budget)
    result = plan["result"]
    status = result.get("status")
    if status == "infeasible_data_error":
        st.error("**Không tìm được phương án phù hợp.** " + result.get("suggested_action", ""))
    elif status == "best_effort":
        st.error(
            "**KHÔNG phải phương án an toàn — Cần thận trọng.** "
            f"Số môn trượt dự báo ({result.get('expected_failed_courses', 0.0):.2f}) "
            f"vượt ngưỡng cho phép ({result.get('expected_fail_cap', 0.0):.2f}). "
            f"{result.get('suggested_action', 'Trao đổi với cố vấn học tập.')}"
        )
    elif status == "graduation_ready":
        st.success("🎓 " + result.get("message", "Đã đạt ngưỡng tín chỉ tốt nghiệp."))
    elif result.get("reduced_load_advised"):
        st.warning(result.get("message", "Đề xuất giảm tải học tập."))
    else:
        st.success(result.get("message", "Phương án tối ưu."))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tín chỉ đăng ký", result.get("selected_credits", 0))
    m2.metric("TC dự báo đạt", f"{result.get('expected_credits_passed', 0.0):.1f}")
    m3.metric("Môn trượt dự báo", f"{result.get('expected_failed_courses', 0.0):.2f}")
    m4.metric("Kết quả", _PLAN_STATUS_VI.get(status, status or "—"))

    selected = pd.DataFrame(plan["selected_courses"])
    if not selected.empty:
        display = _display_with_status(selected[["course_id", "course_name", "credits", "group", "status"]].copy())
        display["P(đạt) %"] = (selected["p_pass"] * 100).round(1)
        st.dataframe(
            display, use_container_width=True, hide_index=True,
            column_config={
                "course_id": st.column_config.TextColumn("Mã"),
                "course_name": st.column_config.TextColumn("Tên học phần"),
                "credits": st.column_config.NumberColumn("TC", format="%d"),
                "group": st.column_config.TextColumn("Nhóm môn"),
                "status": st.column_config.TextColumn("Trạng thái"),
                "P(đạt) %": st.column_config.ProgressColumn("Xác suất đạt", min_value=0, max_value=100,
                                                             format="%.1f%%"),
            },
        )
    combined = pd.DataFrame([{"budget": p["budget"], **c} for p in plans for c in p["selected_courses"]])
    if not combined.empty:
        st.download_button(
            "⬇️ Tải kế hoạch học tập (CSV)",
            combined.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ke_hoach_{assessment['profile']['student_id']}.csv", key="download_plans",
        )
    with st.expander("🧮 Mô hình tối ưu hoạt động thế nào?"):
        st.markdown(
            "**Biến:** xᵢ = 1 nếu chọn môn i.  \n"
            "**Mục tiêu (tối đa):** Σ xᵢ · [ tín chỉ × P(đạt) + β · giá trị mở khóa môn sau − γ · tín chỉ × P(trượt) ]  \n"
            "**Ràng buộc:** 12 ≤ tổng tín chỉ ≤ mức chọn · số môn trượt kỳ vọng ≤ ngưỡng (mềm) · "
            "môn song hành học cùng kỳ · môn bắt buộc đã trượt mà chặn chuỗi phải học lại.  \n"
            f"Bộ giải PuLP + HiGHS · λ = {load_lambda:.2f} · "
            f"tinh chỉnh tải {result.get('load_refinement_iterations', 0)} lần. "
            "Các hệ số là **giả định kịch bản**, chưa phải quy chế chính thức."
        )
    _ = rule_result  # giữ chữ ký rõ ràng


# ── Tab 3: Mô phỏng ───────────────────────────────────────────────────────────


def render_simulation() -> None:
    tables = load_mc_tables()
    summary = tables["summary"]
    st.caption("1.000 lượt mô phỏng cả khóa học (tối đa 16 học kỳ) cho mỗi hồ sơ × mỗi chiến lược. "
               "Kết quả là **thử nghiệm trên dữ liệu mô phỏng**, không phải bằng chứng thực tế tại NTU.")
    if summary is None:
        st.info("Chưa có kết quả. Chạy: `python scripts/monte_carlo_strategies.py --runs 1000`")
        return
    agg = summary[summary["scope"] == "ALL"].copy()
    agg["Chiến lược"] = agg["strategy"].map(lambda s: STRATEGY_LABELS.get(s, s))

    least_fail = agg.loc[agg["mean_simulated_failures"].idxmin()]
    best_time = agg.loc[agg["on_time_rate"].idxmax()]
    best_feas = agg.loc[agg["feasibility_rate"].idxmax()]
    c1, c2, c3 = st.columns(3)
    c1.markdown(kpi_card("Ít trượt môn nhất", str(least_fail["strategy"]),
                         f"{least_fail['mean_simulated_failures']:.2f} lượt trượt TB"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Đúng hạn cao nhất", str(best_time["strategy"]),
                         f"{_pct(best_time['on_time_rate'])} tốt nghiệp ≤ HK8"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Khả thi cao nhất", str(best_feas["strategy"]),
                         f"{_pct(best_feas['feasibility_rate'])} lượt luôn có môn để học"), unsafe_allow_html=True)
    pareto = ", ".join(agg.loc[agg["pareto_frontier"].astype(bool), "strategy"].astype(str))
    st.info(f"**Kết luận:** không có chiến lược tốt nhất mọi mặt — biên Pareto gồm **{pareto}**. "
            "ILP giảm trượt môn, B1 ưu tiên tiến độ → chọn theo ưu tiên của từng sinh viên.", icon="⚖️")

    domain = [STRATEGY_LABELS.get(s, s) for s in agg["strategy"]]
    colors = [STRATEGY_COLORS.get(s, "#52514e") for s in agg["strategy"]]
    color = alt.Color("Chiến lược:N", scale=alt.Scale(domain=domain, range=colors), legend=None)

    left, right = st.columns(2)
    with left:
        st.markdown("### Đánh đổi: ít trượt ↔ đúng hạn (Pareto)")
        base = alt.Chart(agg)
        points = base.mark_point(filled=True, size=140).encode(
            x=alt.X("mean_simulated_failures:Q", title="Số lượt trượt TB (← càng ít càng tốt)",
                    scale=alt.Scale(zero=False)),
            y=alt.Y("on_time_rate:Q", title="Tỷ lệ tốt nghiệp đúng hạn (↑ càng cao càng tốt)",
                    axis=alt.Axis(format=".0%"), scale=alt.Scale(zero=False)),
            color=color,
            tooltip=["Chiến lược", alt.Tooltip("mean_simulated_failures:Q", format=".2f", title="Trượt TB"),
                     alt.Tooltip("on_time_rate:Q", format=".1%", title="Đúng hạn")],
        )
        xerr = base.mark_rule(strokeWidth=2).encode(
            x="mean_simulated_failures_ci_low:Q", x2="mean_simulated_failures_ci_high:Q",
            y="on_time_rate:Q", color=color)
        yerr = base.mark_rule(strokeWidth=2).encode(
            y="on_time_rate_ci_low:Q", y2="on_time_rate_ci_high:Q", x="mean_simulated_failures:Q",
            color=color)
        labels = base.mark_text(dx=10, dy=-10, align="left", fontWeight="bold", color="#334155").encode(
            x="mean_simulated_failures:Q", y="on_time_rate:Q", text="strategy:N")
        st.altair_chart((xerr + yerr + points + labels).properties(height=320).configure_view(strokeWidth=0),
                        use_container_width=True)
        st.caption("Góc **trên-trái** là tốt nhất. Thanh ngang/dọc = khoảng tin cậy 95%.")
    with right:
        st.markdown("### Tỷ lệ tốt nghiệp theo chiến lược")
        long = agg.melt(id_vars=["strategy", "Chiến lược"], value_vars=["graduation_rate", "on_time_rate"],
                        var_name="Chỉ số", value_name="Tỷ lệ")
        long["Chỉ số"] = long["Chỉ số"].map({"graduation_rate": "Tốt nghiệp (≤ HK16)",
                                             "on_time_rate": "Đúng hạn (≤ HK8)"})
        bars = (
            alt.Chart(long).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("strategy:N", title=None, axis=alt.Axis(labelAngle=0),
                        sort=[s for s in STRATEGY_LABELS if s in set(agg["strategy"])]),
                y=alt.Y("Tỷ lệ:Q", axis=alt.Axis(format=".0%", gridColor="#eef2f7"), title=None),
                color=alt.Color("Chỉ số:N", scale=alt.Scale(range=["#2a78d6", "#eb6834"]),
                                legend=alt.Legend(title=None, orient="top")),
                xOffset="Chỉ số:N",
                tooltip=["Chiến lược", "Chỉ số", alt.Tooltip("Tỷ lệ:Q", format=".1%")],
            ).properties(height=320)
        )
        st.altair_chart(bars.configure_view(strokeWidth=0), use_container_width=True)
        st.caption("B3 (15 TC/kỳ) không thể đúng hạn: 15 × 8 = 120 < 128 tín chỉ.")

    with st.expander("📋 Bảng tổng hợp đầy đủ (kèm khoảng tin cậy 95%)"):
        st.dataframe(
            pd.DataFrame({
                "Chiến lược": agg["Chiến lược"],
                "Tốt nghiệp": [f"{_pct(r.graduation_rate)} [{_pct(r.graduation_rate_ci_low)}, "
                               f"{_pct(r.graduation_rate_ci_high)}]" for r in agg.itertuples()],
                "Đúng hạn": [f"{_pct(r.on_time_rate)} [{_pct(r.on_time_rate_ci_low)}, "
                             f"{_pct(r.on_time_rate_ci_high)}]" for r in agg.itertuples()],
                "Khả thi": [_pct(v) for v in agg["feasibility_rate"]],
                "Trượt TB": agg["mean_simulated_failures"].round(2),
                "TC TB": agg["mean_credits_earned"].round(1),
                "HK TB": agg["mean_semesters_to_graduation"].round(2),
                "Pareto": agg["pareto_frontier"].map({True: "✅", False: "—"}),
            }),
            use_container_width=True, hide_index=True,
        )

    paired = tables["paired"]
    if paired is not None:
        with st.expander("🔬 ILP khác các chiến lược khác có ý nghĩa thống kê không?"):
            metric_vi = {"on_time": "Đúng hạn", "graduated": "Tốt nghiệp", "simulated_failures": "Lượt trượt",
                         "credits_earned": "Tín chỉ", "semesters_to_graduation": "Số học kỳ"}
            st.dataframe(
                pd.DataFrame({
                    "So sánh": paired["comparison"],
                    "Chỉ số": paired["metric"].map(lambda m: metric_vi.get(m, m)),
                    "Chênh lệch TB": paired["mean_difference"].round(3),
                    "KTC 95%": [f"[{lo:.3f}, {hi:.3f}]" for lo, hi in zip(paired["ci_low"], paired["ci_high"])],
                    "Khác biệt rõ": paired["ci_excludes_zero"].map({True: "✅ Có", False: "—"}),
                }),
                use_container_width=True, hide_index=True,
            )
            st.caption("✅ khi khoảng tin cậy 95% không chứa 0. Mọi chiến lược dùng chung chuỗi số ngẫu nhiên "
                       "nên so sánh là công bằng.")

    by_student = tables["by_student"]
    if by_student is not None:
        with st.expander("👥 Kết quả theo từng sinh viên"):
            students = sorted(by_student["student_id"].unique())
            picked = st.multiselect("Sinh viên", students, default=students, key="mc_students")
            f = by_student[by_student["student_id"].isin(picked) & by_student["strategy"].isin(STRATEGY_LABELS)]
            st.dataframe(
                pd.DataFrame({
                    "SV": f["student_id"],
                    "Chiến lược": f["strategy"].map(STRATEGY_LABELS),
                    "Tốt nghiệp": [_pct(v) for v in f["graduation_rate"]],
                    "Đúng hạn": [_pct(v) for v in f["on_time_rate"]],
                    "Khả thi": [_pct(v) for v in f["feasibility_rate"]],
                    "Trượt TB": f["mean_simulated_failures"].round(2),
                    "HK TB": f["mean_semesters_to_graduation"].round(2),
                }),
                use_container_width=True, hide_index=True,
            )


# ── Điểm vào ──────────────────────────────────────────────────────────────────


def _input_signature(mode: str, persona_id: str | None, profile: dict | None) -> tuple:
    return (mode, persona_id, None if profile is None else str(profile.get("student_id")))


def main() -> None:
    inject_styles()
    st.title("🎓 Hệ thống Hỗ trợ Cảnh báo Học vụ & Tối ưu Lộ trình Tín chỉ")
    st.markdown(FLOW_HTML, unsafe_allow_html=True)

    curriculum = get_curriculum()
    try:
        get_bundle()
    except FileNotFoundError as err:
        st.error(str(err))
        st.stop()

    mode, persona_id = render_sidebar(curriculum)
    overview_slot = st.container()
    tab_data, tab_plan, tab_sim, tab_risk = st.tabs(
        ["📋 Dữ liệu đầu vào", "🗺️ Lộ trình đề xuất", "🎲 Mô phỏng chiến lược", "⚠️ Rủi ro & Học phần"]
    )

    with tab_data:
        profile, progress_rows, use_ml = render_inputs(curriculum, mode, persona_id)

    signature = _input_signature(mode, persona_id, profile)
    clicked = bool(st.session_state.get("assess"))
    auto = mode == "Hồ sơ mẫu (Có sẵn)" and st.session_state.get("assessment_signature") != signature
    if clicked or auto:
        if profile is None or progress_rows is None:
            if clicked:
                st.sidebar.error("Chưa có đủ dữ liệu để phân tích.")
        else:
            try:
                run_assessment(profile, progress_rows, use_ml, mode, signature)
            except (InputError, ValueError, KeyError) as err:
                st.sidebar.error(str(err))

    # Đổi nguồn dữ liệu thì không hiển thị kết quả của nguồn cũ.
    previous = st.session_state.get("assessment_signature")
    if previous is not None and previous[0] != mode:
        for key in ("assessment", "assessment_signature", "plan_results", "plan_signature"):
            st.session_state.pop(key, None)

    assessment = st.session_state.get("assessment")
    with overview_slot:
        if assessment is None:
            st.info("👈 Chọn nguồn dữ liệu ở thanh bên rồi bấm **🔍 Phân tích & Đánh giá rủi ro**.")
        else:
            render_overview(assessment)

    with tab_risk:
        if assessment is None:
            st.info("Chưa có kết quả phân tích.")
        else:
            render_risk_and_courses(assessment)
    with tab_plan:
        if assessment is None:
            st.info("Cần phân tích hồ sơ trước khi lập lộ trình.")
        else:
            render_plan(assessment)
    with tab_sim:
        render_simulation()


if __name__ == "__main__":
    main()
