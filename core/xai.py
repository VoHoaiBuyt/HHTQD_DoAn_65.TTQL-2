"""Local model explainability (XAI) for student risk at T1."""

from __future__ import annotations

import re
from typing import Any

from core.run_dss import run_dss


# Mapping raw feature names to human-readable Vietnamese labels
FEATURE_LABELS_VI = {
    "Admission grade": "Điểm tuyển sinh đầu vào",
    "Age at enrollment": "Độ tuổi khi nhập học",
    "Curricular units 1st sem (grade)": "Điểm trung bình học phần HK1",
    "Curricular units 1st sem (approved)": "Số học phần đạt HK1",
    "Curricular units 1st sem (evaluations)": "Số lượt đánh giá/thi HK1",
    "Curricular units 1st sem (enrolled)": "Số học phần đăng ký HK1",
    "Previous qualification (grade)": "Điểm tốt nghiệp THPT/bằng cấp trước",
    "Tuition fees up to date": "Tình trạng nộp học phí đúng hạn",
    "Scholarship holder": "Sinh viên có học bổng",
    "Debtor": "Sinh viên có nợ học phí",
    "Gender": "Giới tính",
    "Displaced": "Sinh viên xa nhà/ngoại tỉnh",
    "Application mode": "Phương thức xét tuyển",
    "Application order": "Thứ tự nguyện vọng đăng ký",
    "Daytime/evening attendance": "Hình thức học (ngày/tối)",
    "Mother's qualification": "Trình độ học vấn của mẹ",
    "Father's qualification": "Trình độ học vấn của cha",
    "Mother's occupation": "Nghề nghiệp của mẹ",
    "Father's occupation": "Nghề nghiệp của cha",
}

_XAI_CACHE: dict[str, dict[str, Any]] = {}


def _clean_feature_name(raw_name: str) -> tuple[str, str, Any]:
    """Clean sklearn pipeline output feature name and extract category info if present."""
    name = raw_name
    category_val = None
    if name.startswith("numeric__"):
        name = name.replace("numeric__", "")
    elif name.startswith("categorical__"):
        name = name.replace("categorical__", "")
        # format: FeatureName_Value
        parts = name.rsplit("_", 1)
        if len(parts) == 2:
            name = parts[0]
            category_val = parts[1]
    label_vi = FEATURE_LABELS_VI.get(name, name)
    if category_val is not None:
        label_vi = f"{label_vi} (Mã: {category_val})"
    return name, label_vi, category_val


def explain_student_risk(student_id: str, top_k: int = 6) -> dict[str, Any]:
    """Calculate and return top local SHAP feature contributions for a student."""
    sid = str(student_id).strip()
    if sid in _XAI_CACHE:
        return _XAI_CACHE[sid]

    dss_data = run_dss(sid)
    profile = dss_data.get("profile_summary", {})
    risk = dss_data.get("risk")
    ml_scope = str(profile.get("ml_scope", "off"))

    if ml_scope != "T1_valid" or not risk:
        res = {
            "student_id": sid,
            "status": "not_applicable",
            "message": f"Giải thích XAI mốc T1 không áp dụng cho phạm vi '{ml_scope}' (chỉ áp dụng cho hồ sơ sau HK1, trước HK2).",
            "features": [],
            "summary": "Hồ sơ không thuộc phạm vi mốc T1 hợp lệ.",
            "source_label": "REAL (UCI-697) – SHAP Kernel/Tree Explainer",
        }
        _XAI_CACHE[sid] = res
        return res

    shap_values = risk.get("shap_values", [])
    if not shap_values:
        res = {
            "student_id": sid,
            "status": "unavailable",
            "message": "Không tìm thấy giá trị SHAP cục bộ trong kết quả suy luận.",
            "features": [],
            "summary": "Không có dữ liệu SHAP.",
            "source_label": "REAL (UCI-697)",
        }
        _XAI_CACHE[sid] = res
        return res

    # Sort features by absolute contribution
    sorted_features = sorted(shap_values, key=lambda item: abs(float(item["value"])), reverse=True)
    top_features = []

    for item in sorted_features[:top_k]:
        raw_feat = str(item["feature"])
        val = float(item["value"])
        base_name, label_vi, cat_val = _clean_feature_name(raw_feat)
        student_val = profile.get(base_name, "N/A")

        # Direction explanation
        direction = "increase" if val > 0 else "decrease"
        top_features.append({
            "raw_feature": raw_feat,
            "feature_name": base_name,
            "label_vi": label_vi,
            "shap_value": round(val, 4),
            "abs_shap": round(abs(val), 4),
            "student_value": student_val,
            "direction": direction,
            "effect_vi": "Làm tăng nguy cơ cảnh báo/bỏ học" if val > 0 else "Làm giảm nguy cơ (yếu tố tích cực)",
        })

    # Generate helpful counselor summary
    risk_tier = risk.get("warning_tier", "low")
    p_dropout = risk.get("p_dropout_calibrated", 0.0)

    inc_factors = [f["label_vi"] for f in top_features if f["shap_value"] > 0]
    dec_factors = [f["label_vi"] for f in top_features if f["shap_value"] <= 0]

    summary_parts = []
    if inc_factors:
        summary_parts.append(f"Yếu tố chính làm tăng rủi ro: {', '.join(inc_factors[:2])}.")
    if dec_factors:
        summary_parts.append(f"Yếu tố tích cực giúp kìm hãm rủi ro: {', '.join(dec_factors[:2])}.")

    summary_text = " ".join(summary_parts) if summary_parts else "Các đặc trưng có đóng góp tương đương."

    result = {
        "student_id": sid,
        "status": "success",
        "p_dropout": round(p_dropout, 4),
        "warning_tier": risk_tier,
        "features": top_features,
        "summary": summary_text,
        "source_label": "REAL (UCI-697) – SHAP Explainer (Lớp Dropout)",
        "limitation_note": "SHAP phản ánh mức độ đóng góp của đặc trưng trong mô hình dự báo UCI-697, không khẳng định mối quan hệ nhân quả học tập tại NTU.",
    }
    _XAI_CACHE[sid] = result
    return result
