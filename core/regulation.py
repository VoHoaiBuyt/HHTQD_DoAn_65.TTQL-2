"""Load, validate, and summarize official rules and explicit assumptions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGULATION_PATH = ROOT / "config" / "credit_rules_official.yaml"
REPORT_PATH = ROOT / "reports" / "generated" / "regulation_assumptions.md"
ALLOWED_STATUSES = {"UNCONFIRMED", "UNKNOWN", "CONFIRMED", "MODELING_DECISION"}


def load_regulation_config(path: Path = REGULATION_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    parameters = list(iter_parameters(config))
    for parameter in parameters:
        if (
            not parameter["ref"]
            or parameter["rule_status"] not in ALLOWED_STATUSES
            or not isinstance(parameter["modeled"], bool)
        ):
            raise ValueError(
                f"Invalid regulation metadata at {parameter['path']}: "
                "every parameter needs a reference, rule_status, and modeled flag"
            )
    expected_rules = {
        "credit_limits.normal.minimum": 15,
        "credit_limits.normal.maximum": 27,
        "credit_limits.weak_or_poor.minimum": 12,
        "credit_limits.weak_or_poor.maximum": 18,
        "academic_warnings.forced_withdrawal.consecutive_warnings_strictly_greater_than": 2,
        "academic_warnings.forced_withdrawal.maximum_main_semesters": 16,
    }
    by_path = {parameter["path"]: parameter["value"] for parameter in parameters}
    for parameter_path, expected in expected_rules.items():
        if by_path.get(parameter_path) != expected:
            raise ValueError(
                f"Official rule mismatch at {parameter_path}: "
                f"expected {expected!r}, got {by_path.get(parameter_path)!r}"
            )
    return config


def iter_parameters(
    value: Any,
    path: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if "value" in value and "ref" in value and "rule_status" in value:
            parameters.append(
                {
                    "path": ".".join(path),
                    "value": value["value"],
                    "ref": value["ref"],
                    "rule_status": value["rule_status"],
                    "modeled": value["modeled"],
                    "conflict": value.get("conflict", ""),
                    "label": value.get("label", ""),
                }
            )
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                parameters.extend(iter_parameters(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            parameters.extend(iter_parameters(child, path + (str(index),)))
    return parameters


def write_regulation_report(
    config: dict[str, Any],
    path: Path = REPORT_PATH,
) -> str:
    parameters = iter_parameters(config)
    lines = [
        "# Quy chế đào tạo NTU — nguồn QĐ 753/2021",
        "",
        f"Nguồn: {config.get('source_label', 'UNKNOWN')}.",
        "`rule_status` mô tả căn cứ quy chế; `modeled` mô tả phạm vi hiện thực hóa trong code.",
        "",
        "| Quy tắc | Giá trị | Điều/nguồn | rule_status | modeled | Ghi chú |",
        "|---|---|---|---|---:|---|",
    ]
    for parameter in parameters:
        value = str(parameter["value"]).replace("|", "\\|").replace("\n", " ")
        ref = str(parameter["ref"]).replace("|", "\\|").replace("\n", " ")
        conflict = str(parameter["conflict"] or parameter["label"])
        conflict = conflict.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{parameter['path']}` | `{value}` | {ref} | "
            f"`{parameter['rule_status']}` | {parameter['modeled']} | {conflict} |"
        )
    unconfirmed = [
        parameter for parameter in parameters
        if parameter["rule_status"] in {"UNCONFIRMED", "UNKNOWN", "MODELING_DECISION"}
    ]
    lines.extend(["", "## UNCONFIRMED/UNKNOWN", ""])
    lines.extend(
        f"- `{item['path']}`: `{item['rule_status']}`"
        for item in unconfirmed
    )
    if not unconfirmed:
        lines.append("- Không có.")
    assumptions = config.get("assumptions", {})
    assumption_items = assumptions.get("items", [])
    lines.extend(["", "## GIẢ ĐỊNH cần nhóm xác nhận", ""])
    if assumption_items:
        lines.extend(
            f"- `{item['name']}`: {item['value']} "
            f"(`{item['rule_status']}`, modeled=`{item['modeled']}`)"
            for item in assumption_items
        )
    else:
        lines.append("- Không có.")
    lines.extend(
        [
            "",
            "## Hạn chế và phạm vi",
            "",
            "- Học kỳ hè và điều kiện mở lớp chưa mô hình hóa; kết quả thận trọng hơn thực tế.",
            "- Học cải thiện chưa mô hình hóa.",
            "- Học kỳ phụ, điều kiện mở lớp, và chuẩn đầu ra chi tiết chưa mô hình hóa.",
            "- Chuẩn đầu ra chi tiết chưa có; chỉ nhận cờ Boolean trong hồ sơ kịch bản.",
            "- Giới hạn đăng ký theo quy chế là ràng buộc chính thức; "
            "trần rủi ro là khuyến nghị mềm, không làm mất quyền đăng ký.",
            "",
        ]
    )
    text = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    write_regulation_report(load_regulation_config())
