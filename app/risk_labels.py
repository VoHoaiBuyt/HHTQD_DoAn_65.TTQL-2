from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLAN_DISPLAY_LABELS = {
    "risk_focused": "Ưu tiên giảm rủi ro",
    "balanced": "Cân bằng",
    "acceleration": "Tăng tốc",
}

RISK_THRESHOLDS = {
    "high_failed_courses": 1.0,
    "high_warning_probability": 0.5,
    "medium_failed_courses": 0.5,
    "source_label": "GIẢ ĐỊNH",
    "config_file": "config/optimizer_scenario_v2.yaml",
    "config_key": "optimizer.plan_selection.fast_fmax",
}

RISK_THRESHOLD_NOTE = (
    "Ngưỡng cảnh báo là GIẢ ĐỊNH cho nhãn hiển thị; cấu hình "
    "`optimizer.plan_selection.fast_fmax` chỉ là ngưỡng cho chiến lược Tăng tốc, "
    "không được dùng thay cho các ngưỡng cảnh báo dưới đây."
)


def risk_level(plan: Mapping[str, Any]) -> str:
    failed = float(plan["expected_failed_courses"])
    w1 = float(plan["p_warning_W1"])
    w2 = float(plan["p_warning_W2"])
    if (
        failed >= RISK_THRESHOLDS["high_failed_courses"]
        or w1 >= RISK_THRESHOLDS["high_warning_probability"]
        or w2 >= RISK_THRESHOLDS["high_warning_probability"]
    ):
        return "CAO"
    if failed >= RISK_THRESHOLDS["medium_failed_courses"]:
        return "TRUNG BÌNH"
    return "THẤP"
