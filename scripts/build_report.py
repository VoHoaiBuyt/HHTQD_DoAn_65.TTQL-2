from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from scripts.final_claims import (
    HIGH_RISK_ADVICE,
    RISK_THRESHOLDS,
    build_risk_rows,
    load_validation_claims,
    plan_signatures,
    write_final_artifacts,
    write_risk_levels,
)


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
REPORT_PATH = ROOT / "reports" / "stage2_report.docx"
MC_HISTOGRAM_SOURCE_LABEL = "SCENARIO / GIẢ ĐỊNH (Monte Carlo)"


def _read_json(name: str) -> dict[str, Any]:
    path = GENERATED / name
    if not path.is_file():
        raise FileNotFoundError(f"Required report input not found: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(name: str) -> list[dict[str, str]]:
    path = GENERATED / name
    if not path.is_file():
        raise FileNotFoundError(f"Required report input not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_text(name: str) -> str:
    path = GENERATED / name
    if not path.is_file():
        raise FileNotFoundError(f"Required report input not found: {path}")
    content = path.read_bytes()
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return content.decode(encoding)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required report input not found: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return value


def _fmt(value: Any, decimals: int = 3) -> str:
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def _find_one(rows: list[dict[str, str]], description: str, **filters: str) -> dict[str, str]:
    matches = [
        row for row in rows
        if all(row.get(key) == value for key, value in filters.items())
    ]
    if not matches:
        raise ValueError(f"No source row found for {description}: {filters}")
    if len(matches) > 1:
        raise ValueError(f"Expected one source row for {description}, found {len(matches)}")
    return matches[0]


def _markdown_table(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        raise ValueError("The regulation assumptions file has no readable Markdown table")

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    headers = cells(lines[0])
    rows = []
    for line in lines[2:]:
        row = cells(line)
        if len(row) == len(headers):
            rows.append(row)
    if not rows:
        raise ValueError("The regulation assumptions table contains no data rows")
    return headers, rows


def report_tables() -> list[tuple[str, list[str], list[list[str]]]]:
    curriculum = _read_json("curriculum_validation.json")
    checks = curriculum.get("checks", [])
    if curriculum.get("n_checks") != len(checks):
        raise ValueError("curriculum_validation.json n_checks does not match its checks array")
    status_counts = {
        status: sum(check.get("status") == status for check in checks)
        for status in ("PASS", "WARN", "FAIL")
    }
    if (
        curriculum.get("n_pass") != status_counts["PASS"]
        or curriculum.get("n_warn") != status_counts["WARN"]
        or curriculum.get("n_fail") != status_counts["FAIL"]
    ):
        raise ValueError("curriculum_validation.json summary counts do not match checks")
    summary = curriculum["summary"]
    course_summary = summary["course_counts"]
    prerequisite_summary = summary["prerequisite_graph"]
    unconfirmed_course_codes = course_summary["unknown_course_codes"]

    model_rows = _read_csv("model_comparison.csv")
    three_class = [row for row in model_rows if row["task"] == "three_class"]
    binary = [row for row in model_rows if row["task"] == "binary_dropout"]
    if not three_class or not binary:
        raise ValueError("Model comparison must include three-class and binary validation rows")
    model_headers = [
        "Mô hình", "Accuracy", "Macro-F1", "Dropout precision", "Dropout recall",
        "Dropout F1", "Dropout PR-AUC", "Dropout Brier",
    ]
    model_fields = [
        "model", "accuracy", "macro_f1", "dropout_precision", "dropout_recall",
        "dropout_f1", "dropout_pr_auc", "dropout_brier",
    ]

    test_metrics = _read_json("test_evaluation.json")
    bootstrap = _read_json("ml_validation_bootstrap_ci.json")
    metrics = _read_json("metrics.json")
    ml_metrics = metrics["ml"]
    calibration = ml_metrics["calibration"]
    shap_rows = _read_csv("shap_global.csv")[:5]
    if len(shap_rows) < 5:
        raise ValueError("shap_global.csv must have at least five ranked features")

    plans = _read_csv("plans_by_student.csv")
    plans.sort(key=lambda row: (row["student_id"], row["plan_type"]))
    risk_by_plan = {
        (row["student_id"], row["plan_type"]): row
        for row in build_risk_rows(plans)
    }

    mc = _read_csv("mc_results.csv")
    mc_rows = [row for row in mc if float(row["lambda"]) == 0.1]
    mc_rows.sort(key=lambda row: (row["student_id"], row["policy"]))
    pairwise = _read_csv("mc_pairwise.csv")
    pairwise_rows = [row for row in pairwise if float(row["lambda"]) == 0.1]
    pairwise_rows.sort(key=lambda row: (row["student_id"], row["comparison"]))
    pareto = _read_csv("mc_pareto.csv")
    pareto_rows = [row for row in pareto if float(row["lambda"]) == 0.1]
    pareto_rows.sort(key=lambda row: (row["student_id"], row["policy_a"], row["policy_b"]))
    selected_scenarios = {"V2-001", "V2-003"}
    mc_focus_rows = [row for row in mc_rows if row["student_id"] in selected_scenarios]
    pareto_focus_rows = [row for row in pareto_rows if row["student_id"] in selected_scenarios]
    histogram = [
        row for row in _read_csv("mc_grad_hist.csv")
        if float(row["lambda"]) == 0.1
    ]
    histogram.sort(
        key=lambda row: (
            row["student_id"], row["policy"], row["outcome"],
            float(row["semester"]) if row["semester"] else -1,
        )
    )
    if not mc_rows or not pairwise_rows or not pareto_rows or not histogram:
        raise ValueError("Per-profile Monte Carlo result, histogram, paired, and Pareto rows are required")

    sensitivity = _read_csv("ilp_sensitivity.csv")
    sensitivity_rows = [
        row for row in sensitivity
        if row["student_id"] == "V2-002"
        and float(row["beta"]) == 0.125
        and float(row["gamma"]) == 1.0
        and row["scenario_budget"] == "18"
    ]
    sensitivity_rows.sort(key=lambda row: float(row["lambda"]))
    if not sensitivity_rows:
        raise ValueError("No matching ILP sensitivity rows for V2-002 were found")

    regulation_headers, regulation_rows = _markdown_table(
        _read_text("regulation_assumptions.md")
    )

    def selected(rows: list[dict[str, str]], fields: list[str]) -> list[list[str]]:
        return [[row[field] for field in fields] for row in rows]

    return [
        (
            "CTĐT — kiểm tra",
            ["Mã kiểm tra", "Trạng thái", "Thông tin"],
            [[item["id"], item["status"], item["message"]] for item in checks],
        ),
        (
            "CTĐT — số kiểm tra và thông tin (tách riêng)",
            ["Chỉ số", "Giá trị"],
            [
                ["n_checks (đếm từ JSON)", str(curriculum["n_checks"])],
                ["PASS", str(curriculum["n_pass"])],
                ["WARN", str(curriculum["n_warn"])],
                ["FAIL", str(curriculum["n_fail"])],
                ["course_rows (thông tin)", str(course_summary["total_rows"])],
                ["prerequisite_edges (thông tin)", str(prerequisite_summary["edge_count"])],
            ],
        ),
        (
            "CTĐT — mã HP cần xác minh",
            ["Mã học phần", "Trạng thái nguồn"],
            [[code, "UNCONFIRMED — cần đối chiếu PDF do nhóm cung cấp"] for code in unconfirmed_course_codes],
        ),
        (
            "ML — validation ba lớp",
            model_headers,
            [
                [_fmt(row[field]) for field in model_fields[:1]]
                + [_fmt(float(row[field])) for field in model_fields[1:]]
                for row in three_class
            ],
        ),
        (
            "ML — validation nhị phân",
            model_headers,
            [
                [_fmt(row[field]) for field in model_fields[:1]]
                + [_fmt(float(row[field])) for field in model_fields[1:]]
                for row in binary
            ],
        ),
        (
            "ML — đánh giá holdout một lần",
            ["Chỉ số", "Giá trị nguồn"],
            [
                ["model_name", str(test_metrics["model_name"])],
                ["task", str(test_metrics["task"])],
                ["test_rows", str(test_metrics["test_rows"])],
                ["evaluation_count", str(test_metrics["evaluation_count"])],
                ["accuracy", _fmt(test_metrics["accuracy"])],
                ["macro_f1", _fmt(test_metrics["macro_f1"])],
                ["brier_dropout", _fmt(test_metrics["brier_dropout"])],
                [
                    "confusion_matrix (Dropout, Enrolled, Graduate)",
                    json.dumps(test_metrics["confusion_matrix"], ensure_ascii=False),
                ],
            ],
        ),
        (
            "ML — bootstrap KTC 95% trên validation",
            ["Chỉ số", "Ước lượng", "Cận dưới", "Cận trên"],
            [
                [
                    metric,
                    _fmt(values["estimate"]),
                    _fmt(values["ci95_lower"]),
                    _fmt(values["ci95_upper"]),
                ]
                for metric, values in bootstrap["metrics"].items()
            ],
        ),
        (
            "ML — hiệu chuẩn xác suất (metrics.json)",
            ["Phương pháp / chỉ số", "Giá trị nguồn"],
            [
                ["selected_method", str(calibration["selected_method"])],
                ["uncalibrated_brier", _fmt(calibration["uncalibrated_brier"])],
                ["isotonic_brier", _fmt(calibration["isotonic_brier"])],
                ["platt_brier", _fmt(calibration["platt_brier"])],
                ["OOF fit rows", str(calibration["oof_fit_rows"])],
                ["OOF test rows used", str(calibration["oof_test_rows_used"])],
            ],
        ),
        (
            "ML — SHAP toàn cục, năm đặc trưng đầu",
            ["Đặc trưng", "Mean |SHAP|"],
            [[row["feature"], _fmt(float(row["mean_abs_shap"]))] for row in shap_rows],
        ),
        (
            "ILP — ba phương án cho 9 hồ sơ",
            [
                "Hồ sơ", "Persona", "Phương án", "Trạng thái", "Tín chỉ chọn",
                "Tín chỉ đạt kỳ vọng", "Môn trượt kỳ vọng", "P(W1)", "P(W2)",
                "Mức cảnh báo rủi ro", "Cảnh báo",
            ],
            [
                [
                    row["student_id"], row["persona"], row["plan_type"], row["status"],
                    row["selected_credits"], row["expected_credits_passed"],
                    row["expected_failed_courses"], row["p_warning_W1"], row["p_warning_W2"],
                    risk_by_plan[(row["student_id"], row["plan_type"])]["risk_level"],
                    (
                        f"{row['warnings']} {HIGH_RISK_ADVICE}".strip()
                        if risk_by_plan[(row["student_id"], row["plan_type"])]["risk_level"] == "CAO"
                        else row["warnings"]
                    ),
                ]
                for row in plans
            ],
        ),
        (
            "ILP — độ nhạy scenario V2-002",
            ["β", "γ", "λ", "p*", "Ngân sách", "Tải chọn", "Tín chỉ đạt kỳ vọng", "Môn trượt kỳ vọng", "Trạng thái"],
            selected(
                sensitivity_rows,
                [
                    "beta", "gamma", "lambda", "p_star", "scenario_budget",
                    "selected_load", "expected_credits_passed", "expected_failed_courses",
                    "status",
                ],
            ),
        ),
        (
            "Monte Carlo — kết quả từng hồ sơ, λ=0.1",
            ["Hồ sơ", "Chính sách", "N", "P tốt nghiệp ≤8 kỳ", "KTC 95%", "P tốt nghiệp ≤16 kỳ", "Kỳ tốt nghiệp TB", "Môn trượt kỳ vọng", "P buộc thôi học W1/W2"],
            [
                [
                    row["student_id"],
                    row["policy"],
                    row["n_runs"],
                    _fmt(float(row["p_graduated_on_time"])),
                    f"[{_fmt(float(row['ci_p_graduated_on_time_lower']))}, {_fmt(float(row['ci_p_graduated_on_time_upper']))}]",
                    _fmt(float(row["p_graduated_16"])),
                    _fmt(float(row["mean_graduation_semester"])),
                    _fmt(float(row["expected_failed_courses"])),
                    _fmt(float(row["p_expelled_regulatory"])),
                ]
                for row in mc_rows
            ],
        ),
        (
            "Monte Carlo — histogram từng hồ sơ, λ=0.1",
            ["Hồ sơ", "Chính sách", "Kết quả", "Kỳ", "Số lượt", "N", "Nhãn nguồn hiển thị"],
            [
                [
                    row["student_id"], row["policy"], row["outcome"], row["semester"],
                    row["count"], row["n_total"], MC_HISTOGRAM_SOURCE_LABEL,
                ]
                for row in histogram
            ],
        ),
        (
            "Monte Carlo — so sánh cặp từng hồ sơ, λ=0.1",
            ["Hồ sơ", "So sánh", "N", "Chênh lệch P đúng hạn", "KTC 95% chênh lệch", "Chênh lệch môn trượt", "KTC 95% chênh lệch môn trượt"],
            [
                [
                    row["student_id"],
                    row["comparison"],
                    row["n_runs"],
                    _fmt(float(row["diff_p_graduated_on_time"])),
                    f"[{_fmt(float(row['ci_p_graduated_on_time_lower']))}, {_fmt(float(row['ci_p_graduated_on_time_upper']))}]",
                    _fmt(float(row["diff_expected_failed_courses"])),
                    f"[{_fmt(float(row['ci_expected_failed_courses_lower']))}, {_fmt(float(row['ci_expected_failed_courses_upper']))}]",
                ]
                for row in pairwise_rows
            ],
        ),
        (
            "Monte Carlo — Pareto từng hồ sơ, λ=0.1",
            ["Hồ sơ", "Chính sách A", "Chính sách B", "Kết luận", "Diễn giải nguồn"],
            [
                [
                    row["student_id"], row["policy_a"], row["policy_b"],
                    row["dominance"], row["interpretation"],
                ]
                for row in pareto_rows
            ],
        ),
        (
            "Monte Carlo — KTC V2-001 và V2-003, λ=0.1",
            ["Hồ sơ", "Chính sách", "P tốt nghiệp ≤8 kỳ", "KTC 95%", "P buộc thôi học W1/W2", "KTC 95% W1/W2"],
            [
                [
                    row["student_id"], row["policy"],
                    _fmt(float(row["p_graduated_on_time"])),
                    f"[{_fmt(float(row['ci_p_graduated_on_time_lower']))}, {_fmt(float(row['ci_p_graduated_on_time_upper']))}]",
                    _fmt(float(row["p_expelled_regulatory"])),
                    f"[{_fmt(float(row['ci_p_expelled_regulatory_lower']))}, {_fmt(float(row['ci_p_expelled_regulatory_upper']))}]",
                ]
                for row in mc_focus_rows
            ],
        ),
        (
            "Monte Carlo — Pareto V2-001 và V2-003, λ=0.1",
            ["Hồ sơ", "Chính sách A", "Chính sách B", "Nhãn Pareto"],
            selected(pareto_focus_rows, ["student_id", "policy_a", "policy_b", "dominance"]),
        ),
        (
            "Monte Carlo — ghi chú metadata histogram, λ=0.1",
            ["Trường", "Giá trị nguồn", "Giá trị báo cáo"],
            [
                [
                    "source_label",
                    "trống trong mc_grad_hist.csv",
                    MC_HISTOGRAM_SOURCE_LABEL,
                ],
            ],
        ),
        (
            "Quy chế — bảng giả định và trạng thái",
            regulation_headers,
            regulation_rows,
        ),
    ]


def _add_table(document: Document, title: str, headers: list[str], rows: list[list[str]]) -> None:
    table = document.add_table(rows=2, cols=len(headers))
    table.style = "Table Grid"
    table.rows[0].cells[0].text = title
    for cell, value in zip(table.rows[1].cells, headers):
        cell.text = value
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = str(value)
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(7)
    document.add_paragraph()


def _add_section(document: Document, title: str, level: int = 1) -> None:
    section_numbers = {
        "TÓM TẮT ĐIỀU HÀNH": 1,
        "DỮ LIỆU OFFICIAL (NTU)": 2,
        "QUY CHẾ QĐ 753/2021 VÀ CÁCH MÔ HÌNH HÓA": 3,
        "MÔ HÌNH ML — MỐC T1": 4,
        "RULE ENGINE VÀ KẾT QUẢ KIỂM THỬ": 5,
        "ILP — HÀM MỤC TIÊU VÀ CÁC PHƯƠNG ÁN": 6,
        "MONTE CARLO — MÔ PHỎNG, KHÔNG PHẢI BẰNG CHỨNG THỰC TẾ": 7,
        "GIAO DIỆN STREAMLIT": 8,
        "CÀI ĐẶT VÀ CHẠY": 9,
        "HẠN CHẾ VÀ PHẦN CHƯA HOÀN THÀNH": 10,
        "PHỤ LỤC — CÂY THƯ MỤC, FILE VÀ GIẢ ĐỊNH": 11,
    }
    number = section_numbers.get(title)
    display_title = f"{number}. {title}" if number is not None else title
    document.add_heading(display_title, level=level)


def _add_subsection(document: Document, title: str) -> None:
    document.add_heading(title, level=2)


def _add_word_field(paragraph, instruction: str, placeholder: str = "1") -> None:
    run = OxmlElement("w:r")
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = f" {instruction} "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, code, separate, text, end):
        run.append(element)
    paragraph._p.append(run)


def _add_toc(document: Document) -> None:
    title = document.add_paragraph()
    title.style = document.styles["Title"]
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("MỤC LỤC")
    paragraph = document.add_paragraph()
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), 'TOC \\o "1-2" \\h \\z \\u')
    field.set(qn("w:dirty"), "true")
    field_run = OxmlElement("w:r")
    field_text = OxmlElement("w:t")
    field_text.text = "Mở tài liệu trong Word và cập nhật trường để hiện mục lục, số trang."
    field_run.append(field_text)
    field.append(field_run)
    paragraph._p.append(field)
    document.add_page_break()


def _configure_document_fields(document: Document) -> None:
    update_fields = OxmlElement("w:updateFields")
    update_fields.set(qn("w:val"), "true")
    document.settings.element.append(update_fields)
    for section in document.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer.add_run("Trang ")
        _add_word_field(footer, "PAGE")


def _write_heading_outline(document: Document) -> None:
    headings = [
        (paragraph.style.name, paragraph.text.strip())
        for paragraph in document.paragraphs
        if paragraph.style.name in {"Heading 1", "Heading 2"} and paragraph.text.strip()
    ]
    lines = ["# Thứ tự Heading 1/2 trong báo cáo", ""]
    for style, text in headings:
        prefix = "- " if style == "Heading 1" else "  - "
        lines.append(f"{prefix}{style}: {text}")
    lines.extend(["", "Số trang thật: chưa kiểm chứng (không render Word/PDF trong môi trường tạo báo cáo)."])
    (GENERATED / "final_heading_outline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _add_table_by_title(document: Document, tables: list[tuple[str, list[str], list[list[str]]]], title: str) -> None:
    match = next(item for item in tables if item[0] == title)
    _add_table(document, *match)


def _build_mc_distribution_figure(histogram: list[dict[str, str]]) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = GENERATED / "final_mc_graduation_distribution.png"
    policies = sorted({row["policy"] for row in histogram})
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for axis, student_id in zip(axes, ("V2-001", "V2-003")):
        rows = [
            row for row in histogram
            if row["student_id"] == student_id
            and row["outcome"] == "graduated"
            and row["semester"]
        ]
        for policy in policies:
            policy_rows = [row for row in rows if row["policy"] == policy]
            if not policy_rows:
                continue
            total = int(policy_rows[0]["n_total"])
            by_semester: dict[int, int] = {}
            for row in policy_rows:
                semester = int(float(row["semester"]))
                by_semester[semester] = by_semester.get(semester, 0) + int(row["count"])
            semesters = sorted(by_semester)
            axis.plot(
                semesters,
                [by_semester[semester] / total for semester in semesters],
                marker="o",
                label=policy,
            )
        axis.set_title(student_id)
        axis.set_xlabel("Kỳ chính tốt nghiệp")
        axis.set_xlim(1, 16)
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Tỷ lệ trên N lượt mô phỏng")
    axes[-1].legend(fontsize=8)
    figure.suptitle("Monte Carlo, λ=0,1 — phân phối kỳ tốt nghiệp theo hồ sơ")
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)
    return output


def build_report(output_path: Path = REPORT_PATH) -> Path:
    write_final_artifacts()
    risk_rows = write_risk_levels()
    tables = report_tables()
    curriculum = _read_json("curriculum_validation.json")
    test_metrics = _read_json("test_evaluation.json")
    metrics = _read_json("metrics.json")
    validation_claims = load_validation_claims()
    bootstrap = _read_json("ml_validation_bootstrap_ci.json")
    model_comparison = _read_csv("model_comparison.csv")
    mc = _read_csv("mc_results.csv")
    mc_histogram = [
        row for row in _read_csv("mc_grad_hist.csv")
        if float(row["lambda"]) == 0.1
    ]
    plans = _read_csv("plans_by_student.csv")
    sensitivity = _read_csv("ilp_sensitivity.csv")
    regulation_text = _read_text("regulation_assumptions.md")
    optimization_text = _read_text("optimization_spec.md")
    mc_interpretation = _read_text("mc_interpretation.md")
    enrolled_analysis = _read_text("enrolled_analysis.md")
    environment_validation = _read_text("final_environment_validation.md")
    pytest_summary = _read_text("pytest_summary.txt")
    app_test_summary = _read_text("final_app_test.txt")
    health_summary = _read_text("final_health.txt")
    hash_rows = _read_csv("restructure_hashes.csv")
    optimizer_config = _read_yaml(ROOT / "config" / "optimizer_scenario_v2.yaml")
    mc_config = _read_yaml(ROOT / "config" / "monte_carlo_scenario.yaml")
    objective_config = optimizer_config["optimizer"]["objective"]
    load_config = optimizer_config["optimizer"]["load"]
    simulation_config = mc_config["monte_carlo"]
    identical_profile_count, distinct_plan_signatures, repeated_profiles = plan_signatures(plans)
    profile_count = len({row["student_id"] for row in plans})
    screens_path = ROOT / "docs" / "screens_to_capture.md"
    pytest_path = GENERATED / "pytest_summary.txt"

    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(13)
    for style_name in ("Title", "Heading 1", "Heading 2", "Heading 3"):
        document.styles[style_name].font.name = "Times New Roman"
        document.styles[style_name].font.size = Pt(16 if style_name == "Heading 1" else 14)

    title = document.add_heading("BÁO CÁO GIAI ĐOẠN 2", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = document.add_paragraph(
        "Hệ hỗ trợ cảnh báo rủi ro học tập và tối ưu lộ trình tín chỉ — CNTT, Trường Đại học Nha Trang"
    )
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph(
        "Báo cáo được tổng hợp từ artifact hiện có trong reports/generated/. "
        "Kết quả mô phỏng và ML trên UCI-697 không phải bằng chứng hiệu quả tại NTU."
    )
    document.add_paragraph("Họ tên: ______________________________________________")
    document.add_paragraph("MSSV: _________________________________________________")
    document.add_page_break()
    _add_toc(document)
    _configure_document_fields(document)

    _add_section(document, "TÓM TẮT ĐIỀU HÀNH")
    _add_subsection(document, "Tóm tắt và phạm vi")
    document.add_paragraph(
        "Bản mẫu đã kết nối dự báo ML tại T1 trên REAL (UCI-697), quy tắc đào tạo, tối ưu ILP, "
        "Monte Carlo và giao diện Streamlit. CTĐT được nhóm cung cấp mang nhãn OFFICIAL (NTU); "
        "hồ sơ là SCENARIO. Các bảng và số liệu trong báo cáo được lấy từ artifact đã sinh, "
        "không nhập số kết quả bằng tay."
    )
    document.add_paragraph(
        f"Holdout ML có {test_metrics['test_rows']} dòng và chỉ được đánh giá một lần; "
        f"Enrolled recall là {test_metrics['per_class']['Enrolled']['recall']:.4f}. Monte Carlo "
        "là mô phỏng trên hồ sơ kịch bản với các giả định; khác biệt trong mô phỏng không phải bằng "
        "chứng hiệu quả với sinh viên NTU. Mã HP, một số ngữ nghĩa quy chế, học kỳ hè, mở lớp và "
        "học cải thiện còn hạn chế hoặc chưa xác nhận. Đây là prototype hỗ trợ thảo luận, không phải "
        "dự báo đã kiểm định tại NTU hay khuyến nghị đăng ký an toàn."
    )
    repeated_text = ", ".join(repeated_profiles) if repeated_profiles else "không có"
    document.add_paragraph(
        f"Từ {profile_count} hồ sơ SCENARIO, {identical_profile_count} hồ sơ có bộ kết quả "
        f"ba phương án giống hệt ({repeated_text}), nên có {distinct_plan_signatures} kiểu "
        "kết quả khác nhau."
    )
    high_risk_count = sum(row["risk_level"] == "CAO" for row in risk_rows)
    v2005 = next(row for row in risk_rows if row["student_id"] == "V2-005" and row["plan_type"] == "risk_focused")
    document.add_paragraph(
        f"Mức cảnh báo rủi ro là GIẢ ĐỊNH theo ngưỡng đã mô tả; có {high_risk_count} phương án "
        f"mức CAO. Riêng V2-005 risk_focused: P(W1)={float(v2005['p_warning_W1']):.3f}, "
        f"kỳ vọng trượt {float(v2005['expected_failed_courses']):.2f} môn."
    )
    _add_subsection(document, "Các điểm đã chỉnh so với báo cáo lần trước")
    matrix_headers, matrix_rows = _markdown_table(
        _read_text("final_requirements_matrix.md")
    )
    _add_table(
        document,
        "Các điểm đã chỉnh so với báo cáo lần trước",
        matrix_headers,
        matrix_rows,
    )

    _add_section(document, "DỮ LIỆU OFFICIAL (NTU)")
    _add_subsection(document, "Nguồn và phạm vi dữ liệu")
    course_summary = curriculum["summary"]["course_counts"]
    prerequisite_summary = curriculum["summary"]["prerequisite_graph"]
    document.add_paragraph(
        f"Nhãn: {curriculum['source_label']}; tài liệu nhóm cung cấp: "
        f"{curriculum['source_document']}, mục {curriculum['source_section']}. "
        f"Artifact hiện ghi {course_summary['total_rows']} dòng CTĐT và "
        f"{prerequisite_summary['edge_count']} quan hệ tiên quyết/song hành. "
        "Ngày truy cập/phiên bản tài liệu không có trong artifact: UNKNOWN, source=NOT_FOUND. "
        "Không tự bổ sung học phần, tín chỉ hoặc điều kiện ngoài nguồn."
    )
    document.add_paragraph(
        f"REAL (UCI-697) chỉ cung cấp vector/đặc trưng cho ML; số hồ sơ minh họa SCENARIO là "
        f"{len({row['student_id'] for row in plans})}. Tham số mô phỏng và kế hoạch được gắn "
        "GIẢ ĐỊNH khi không phải dữ liệu CTĐT/quy chế đã xác nhận."
    )
    document.add_paragraph(
        "Các mã học phần được validator liệt kê là chưa xác minh được đưa vào bảng riêng; "
        "các trường không có trong nguồn chính thức phải giữ UNKNOWN/source=NOT_FOUND. "
        "Những dòng UNCONFIRMED "
        "và UNKNOWN của quy chế được liệt kê nguyên trạng ở bảng phụ lục bên dưới."
    )
    _add_table_by_title(document, tables, "CTĐT — số kiểm tra và thông tin (tách riêng)")
    _add_table_by_title(document, tables, "CTĐT — mã HP cần xác minh")
    _add_table_by_title(document, tables, "CTĐT — kiểm tra")
    document.add_paragraph(
        "n_checks là số kiểm tra trong mảng checks của JSON. course_rows và prerequisite_edges "
        "là thông tin mô tả riêng, không cộng vào n_checks."
    )
    document.add_paragraph(
        f"Kiểm định hiện hành: n_checks={curriculum['n_checks']} "
        f"(PASS={curriculum['n_pass']}, WARN={curriculum['n_warn']}, FAIL={curriculum['n_fail']}). "
        "Mã học phần trùng hoặc chưa xác minh được không được tự chuẩn hóa."
    )

    _add_section(document, "QUY CHẾ QĐ 753/2021 VÀ CÁCH MÔ HÌNH HÓA")
    _add_subsection(document, "Quy tắc và trạng thái xác nhận")
    document.add_paragraph(
        "Nguồn quy chế được ghi là QĐ 753/QĐ-ĐHNT ngày 13/08/2021, áp dụng khóa 60 trở đi. "
        "Các giá trị, điều khoản, trạng thái CONFIRMED/UNCONFIRMED/UNKNOWN và ghi chú mô hình "
        "được trích trực tiếp từ regulation_assumptions.md; nội dung này không thay thế việc "
        "đối chiếu văn bản gốc."
    )
    _add_table_by_title(document, tables, "Quy chế — bảng giả định và trạng thái")

    _add_section(document, "MÔ HÌNH ML — MỐC T1")
    _add_subsection(document, "Giao thức, validation và so sánh")
    document.add_paragraph(
        "Mốc hợp lệ: sau HK1, trước đăng ký HK2. Ba thuật toán được so sánh: Logistic Regression, "
        "Random Forest và XGBoost. Quy trình tách train/validation/test là 60/20/20 có phân tầng; "
        "train dùng cho fit và tuning, validation cho lựa chọn mô hình/ngưỡng/hiệu chuẩn. "
        f"Holdout test có {test_metrics['test_rows']} dòng, evaluation_count="
        f"{test_metrics['evaluation_count']}; test không dùng để chọn mô hình."
    )
    document.add_paragraph(
        "Validation có thể lạc quan vì được dùng để chọn mô hình, ngưỡng và hiệu chuẩn. "
        "Enrolled là lớp bị kiểm duyệt phải. Các số sau đây chỉ so sánh XGBoost trên validation."
    )
    xgb_three = validation_claims["models"]["three_class"]
    xgb_binary = validation_claims["models"]["binary_dropout"]
    three_metrics = validation_claims["three_metrics"]
    binary_metrics = validation_claims["binary_metrics"]
    document.add_paragraph(
        f"Validation XGBoost: PR-AUC Dropout ba lớp={float(xgb_three['dropout_pr_auc']):.4f}, "
        f"nhị phân={float(xgb_binary['dropout_pr_auc']):.4f}; recall tại precision ≥ 0,50 "
        f"ba lớp={float(three_metrics['dropout_recall_at_precision_0.50']['recall']):.4f}, "
        f"nhị phân={float(binary_metrics['dropout_recall_at_precision_0.50']['recall']):.4f}; "
        f"Brier ba lớp={float(xgb_three['dropout_brier']):.4f}, "
        f"nhị phân={float(xgb_binary['dropout_brier']):.4f}."
    )
    document.add_paragraph(
        "ml_validation_bootstrap_ci.json lưu KTC 95% validation riêng cho XGBoost ba lớp; "
        "không có KTC ghép cặp 95% cho chênh lệch ba lớp so với nhị phân. Vì vậy chưa đủ "
        "cơ sở để kết luận hai cách tiếp cận phân biệt được về mặt thống kê."
    )
    _add_subsection(document, "KTC validation và kiểm định Enrolled")
    _add_table_by_title(document, tables, "ML — validation ba lớp")
    _add_table_by_title(document, tables, "ML — validation nhị phân")
    _add_table_by_title(document, tables, "ML — đánh giá holdout một lần")
    _add_table_by_title(document, tables, "ML — bootstrap KTC 95% trên validation")
    _add_table_by_title(document, tables, "ML — hiệu chuẩn xác suất (metrics.json)")
    document.add_paragraph(
        "Khoảng tin cậy bootstrap chỉ áp dụng cho validation, không phải holdout. "
        f"Phương pháp: {bootstrap['interval_method']}; số lần bootstrap lấy từ file nguồn. "
        f"Phương pháp hiệu chuẩn được chọn: {metrics['ml']['calibration']['selected_method']}; "
        "độ tin cậy xác suất được phản ánh bằng Brier score và các giá trị calibration; "
        f"trạng thái holdout calibration={test_metrics.get('calibration', 'không có trường trong artifact')}. "
        "Enrolled là lớp bị kiểm duyệt phải (right-censored); không diễn giải là nhãn hoàn tất "
        "tương lai đã biết. SHAP giải thích mô hình, không phải nhân quả."
    )
    _add_table_by_title(document, tables, "ML — SHAP toàn cục, năm đặc trưng đầu")
    document.add_paragraph(
        "Phân tích Enrolled (REAL UCI-697, validation): "
        + next(
            (line.strip() for line in enrolled_analysis.splitlines()
             if "XGBoost" in line and "|" in line),
            "chi tiết được lưu trong reports/generated/enrolled_analysis.md.",
        )
    )
    document.add_paragraph(
        "Giao thức, đặc trưng T1 và one-shot test: docs/ml_protocol.md. "
        "Test chỉ chạy một lần; validation được dùng để chọn nên có thể lạc quan."
    )
    document.add_paragraph(
        "Chi tiết phân tích Enrolled, calibration, test và SHAP: "
        "reports/generated/enrolled_analysis.md, metrics.json, test_evaluation.json, "
        "shap_global.csv và shap_local_examples.json."
    )

    _add_section(document, "RULE ENGINE VÀ KẾT QUẢ KIỂM THỬ")
    _add_subsection(document, "Bao phủ kiểm thử")
    document.add_paragraph(
        "Kiểm tra CTĐT và số đếm được tách thành bảng riêng. Pytest bao gồm kiểm tra prerequisite/"
        "corequisite, ràng buộc tín chỉ, học lại, các trường hợp infeasible/best_effort, dữ liệu, "
        "mô phỏng và smoke test giao diện. Lỗi môn song hành được kiểm tra bằng các ca regression "
        "trong tests/test_core_rules.py; kết quả chạy toàn bộ được lưu nguyên văn tại "
        f"{pytest_path.relative_to(ROOT)}."
    )
    rule_test_groups = [
        ["(a)", "Nguồn CTĐT và kiểm tra dữ liệu", "tests/test_curriculum_validation.py; tests/test_data_consistency.py", "Đã chạy cùng full pytest"],
        ["(b)", "Tiên quyết và điều kiện học phần", "tests/test_core_rules.py; tests/test_official_rules.py", "Đã chạy cùng full pytest"],
        ["(c)", "Song hành hai chiều, chuỗi và lan truyền đến điểm ổn định", "tests/test_core_rules.py", "Đã chạy regression tests"],
        ["(d)", "Giới hạn tín chỉ và GPA theo QĐ 753", "tests/test_official_rules.py", "Đã chạy cùng full pytest"],
        ["(e)", "Học lại/cải thiện và trạng thái tiến độ", "tests/test_official_rules.py; tests/test_core_rules.py", "Đã chạy cùng full pytest"],
        ["(f)", "best_effort, xung đột quy chế và cảnh báo cố vấn", "tests/test_optimizer_v2.py; tests/test_app_smoke.py", "Đã chạy cùng full pytest"],
        ["(g)", "Seed, common random numbers, histogram và kết quả MC", "tests/test_dss_simulation.py", "Đã chạy cùng full pytest"],
        ["(h)", "Cô lập hồ sơ và các trang Streamlit", "tests/test_data_consistency.py; tests/test_app_smoke.py", "Đã chạy cùng full pytest"],
    ]
    _add_table(
        document,
        "Rule engine — tám nhóm kiểm tra (a)–(h)",
        ["Nhóm", "Phạm vi", "Bằng chứng kiểm thử", "Kết quả"],
        rule_test_groups,
    )
    document.add_paragraph(
        "Lỗi song hành trước đây được xử lý bằng cách lặp việc loại học phần không đủ điều kiện "
        "đến khi tập đủ điều kiện ổn định. Ý nghĩa học thuật của quan hệ song hành vẫn cần xác nhận."
    )

    _add_section(document, "ILP — HÀM MỤC TIÊU VÀ CÁC PHƯƠNG ÁN")
    _add_subsection(document, "Phương án và mức cảnh báo rủi ro")
    document.add_paragraph(
        "Công thức, định nghĩa p*, β, γ, xác suất môn đạt, unlock value, ràng buộc và cách chọn "
        "ba chiến lược được lấy từ reports/generated/optimization_spec.md. Ngân sách đăng ký là "
        "kịch bản, không phải giới hạn chính thức; cấu hình phân biệt sinh viên thường và yếu/kém. "
        "P(Dropout) và Fmax là khuyến nghị mềm, không làm mất quyền đăng ký chính thức."
    )
    formula_lines = [
        line.strip() for line in optimization_text.splitlines()
        if line.strip().startswith("`maximize") or "p*" in line or "Defaults β=" in line
    ]
    for line in formula_lines:
        document.add_paragraph(line.replace("`", ""), style="List Bullet")
    strict_edges_line = next(
        (line.strip() for line in optimization_text.splitlines()
         if line.strip().startswith("Official strict prerequisite edges:")),
        "Số cạnh tiên quyết nghiêm ngặt được ghi trong optimization_spec.md.",
    )
    document.add_paragraph(
        f"p*=γ/(1+γ); với γ={objective_config['gamma']} thì p*="
        f"{objective_config['p_break_even']}. {strict_edges_line} "
        "u_i khác 0 và giá trị từng học phần được liệt kê trong optimization_spec.md. "
        "g_load dùng L là tổng tín chỉ thực chọn và units(L), không lấy số môn thay cho tín chỉ."
    )
    _add_table_by_title(document, tables, "ILP — ba phương án cho 9 hồ sơ")
    _add_table_by_title(document, tables, "ILP — độ nhạy scenario V2-002")
    document.add_paragraph(
        f"Mức cảnh báo là GIẢ ĐỊNH: CAO nếu số môn trượt kỳ vọng ≥ {RISK_THRESHOLDS['high_failed_courses']:.1f} "
        f"hoặc P(W1) ≥ {RISK_THRESHOLDS['high_warning_probability']:.1f} hoặc "
        f"P(W2) ≥ {RISK_THRESHOLDS['high_warning_probability']:.1f}; TRUNG BÌNH nếu số môn "
        f"trượt kỳ vọng ≥ {RISK_THRESHOLDS['medium_failed_courses']:.1f}; nếu không thì THẤP. "
        f"Với mọi mức CAO: {HIGH_RISK_ADVICE}. "
        f"Riêng V2-005 risk_focused là CAO (P(W1)={float(v2005['p_warning_W1']):.3f}; "
        f"kỳ vọng trượt {float(v2005['expected_failed_courses']):.2f} môn). "
        "Trong app, nhãn risk_focused hiển thị “An toàn” ngay cả với hồ sơ CAO này; "
        "đây là nhãn gây hiểu nhầm, cần AQL xem xét riêng. "
        "Các dòng best_effort luôn phải giữ cảnh báo rủi ro và khuyến nghị gặp cố vấn học tập; "
        "không được gọi là an toàn. Bảng kế hoạch lấy dữ liệu từ plans_by_student.csv; "
        "chi tiết warnings/status đầy đủ vẫn nằm trong artifact nguồn."
    )
    document.add_paragraph(
        f"Artifact kế hoạch có {len(plans)} dòng; độ nhạy có {len(sensitivity)} dòng. "
        "Phạm vi độ nhạy trong báo cáo là lát cắt được chỉ rõ trong tiêu đề bảng, không đại diện "
        "cho toàn bộ lưới."
    )

    _add_section(document, "MONTE CARLO — MÔ PHỎNG, KHÔNG PHẢI BẰNG CHỨNG THỰC TẾ")
    _add_subsection(document, "Thiết kế, kết quả và giới hạn")
    mc_seed = metrics.get("monte_carlo", {}).get("seed", "UNKNOWN")
    mc_runs = sorted({int(row["n_runs"]) for row in mc})
    policies = sorted({row["policy"] for row in mc})
    lambdas = sorted({float(row["lambda"]) for row in mc})
    high_risk_rows = [
        row for row in mc
        if row["student_id"] == "V2-005" and float(row["lambda"]) == 0.1
    ]
    high_risk_probabilities = [
        float(row["p_expelled_regulatory"]) for row in high_risk_rows
    ]
    pareto_labels = sorted({row["dominance"] for row in _read_csv("mc_pareto.csv")})
    document.add_paragraph(
        f"Thiết kế: chính sách {', '.join(policies)}; số ngẫu nhiên chung dùng cùng seed/run_index; "
        f"N={', '.join(map(str, mc_runs))}; seed={mc_seed}; λ={', '.join(_fmt(v, 1) for v in lambdas)}. "
        "Bảng chính báo cáo từng hồ sơ, các trung bình gộp chỉ để mô tả. KTC, paired comparison và "
        "bốn nhãn Pareto lấy từ artifact; giả định pass/fail độc lập, điểm đại diện 7,0/4,0, không "
        "mô phỏng hè và chưa mô phỏng W3/W4."
    )
    document.add_paragraph(
        "Khác biệt trong mô phỏng không phải bằng chứng hiệu quả với sinh viên NTU. V2-005 là hồ sơ "
        "SCENARIO nợ đọng sát W1; P(buộc thôi học theo phạm vi W1/W2) tại λ=0,1 nằm trong khoảng "
        f"{min(high_risk_probabilities):.3f}–{max(high_risk_probabilities):.3f} theo các chính sách. "
        f"Nhãn Pareto trong artifact: {', '.join(pareto_labels)}. Đây không phải xác suất thực tế "
        "của sinh viên NTU."
    )
    _add_table_by_title(document, tables, "Monte Carlo — kết quả từng hồ sơ, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — so sánh cặp từng hồ sơ, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — Pareto từng hồ sơ, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — histogram từng hồ sơ, λ=0.1")
    figure_path = _build_mc_distribution_figure(mc_histogram)
    document.add_picture(str(figure_path), width=Inches(6.6))
    document.add_paragraph(
        "Biểu đồ phân phối kỳ tốt nghiệp lấy trực tiếp từ mc_grad_hist.csv cho V2-001 và V2-003; "
        "kỳ không có quan sát không được nội suy. source_label trống trong CSV đã lưu; báo cáo dùng "
        f"nhãn hiển thị {MC_HISTOGRAM_SOURCE_LABEL} từ hằng số script. Đây là khác biệt metadata."
    )
    _add_table_by_title(document, tables, "Monte Carlo — KTC V2-001 và V2-003, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — Pareto V2-001 và V2-003, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — ghi chú metadata histogram, λ=0.1")
    document.add_paragraph(
        "Kiểm tái tạo 3 nhóm (V2-001/ILP-matched, V2-001/B1, V2-005/B1; λ=0,1); "
        "trong đó 1 nhóm dùng ILP; không có code_hash. Với các nhóm này, 109/109 cột "
        "kết quả khớp; V2-005 có 101 cột số trong tổng 109 cột. Sai số số học ≤ 1e-9; "
        "khóa dòng và count/n_total của histogram khớp. Đây không phải kiểm chứng toàn bộ "
        "tổ hợp hồ sơ/chính sách."
    )
    document.add_paragraph(
        "Riêng V2-005/B1, mô phỏng đã ghi kết quả nhưng hậu xử lý phát sinh KeyError; "
        "thông báo lỗi nguyên văn không được lưu. Đối chiếu được thực hiện trên "
        "V2-005_B1_results.csv và V2-005_B1_grad_hist.csv với dòng V2-005/B1 trong "
        "mc_results.csv và mc_grad_hist.csv; đây là các tệp đã có trước khi hậu xử lý lỗi. "
        "Tái tạo bổ sung V2-003/ILP-matched, λ=0,3 chưa hoàn tất trong giới hạn 10 phút; "
        "theo chỉ dẫn đã thử fallback λ=0,1 nhưng lần đó cũng chưa hoàn tất trong giới hạn. "
        "Không có kết quả đối chiếu cho cả hai lần chạy."
    )
    document.add_paragraph("Diễn giải Monte Carlo nguyên văn từ mc_interpretation.md:")
    for line in mc_interpretation.splitlines():
        if line.strip():
            document.add_paragraph(line)

    _add_section(document, "GIAO DIỆN STREAMLIT")
    _add_subsection(document, "Trang giao diện và ảnh minh họa")
    document.add_paragraph(
        "Ứng dụng: app/main.py. Hồ sơ là SCENARIO; ML chỉ hiển thị trong phạm vi T1 hợp lệ; "
        "kết quả mô phỏng được gắn nhãn giả định. Bảng đối chiếu dưới đây theo docs/screens_to_capture.md; "
        "chụp đủ 7 trang cho 9 hồ sơ SCENARIO, không dùng dữ liệu cá nhân."
    )
    _add_table(
        document,
        "Đối chiếu chức năng giao diện và trang",
        ["Yêu cầu", "Trang Streamlit", "Điều cần kiểm tra/chụp"],
        [
            ["Hồ sơ và tiến độ", "Hồ sơ & tiến độ", "Chỉ hồ sơ SCENARIO; trạng thái/điểm nhất quán."],
            ["Cảnh báo rủi ro tại T1", "Nguy cơ & cảnh báo", "ML chỉ tại T1; P(Dropout) là khuyến nghị mềm."],
            ["Đủ điều kiện học phần", "Học phần", "Hiển thị tiên quyết/song hành và lý do chặn."],
            ["Nhiều phương án đăng ký", "Phương án đăng ký", "Ba phương án; best_effort kèm cảnh báo và cố vấn."],
            ["Tham số giả định", "What-if", "λ/Fmax gắn nhãn GIẢ ĐỊNH."],
            ["Kết quả mô phỏng", "Mô phỏng", "N, CI ghép cặp, Pareto, histogram và chính sách."],
            ["Nguồn dữ liệu và hạn chế", "Dữ liệu & giả định", "Nhãn OFFICIAL/REAL/SCENARIO/GIẢ ĐỊNH."],
        ],
    )
    for caption in (
        "[ẢNH 1: V2-001 – Phương án đăng ký – ba phương án, trạng thái và cảnh báo]",
        "[ẢNH 2: V2-002 – Mô phỏng – CI ghép cặp và nhãn Pareto tại λ=0,1]",
        "[ẢNH 3: V2-003 – Nguy cơ & cảnh báo – T1 và thông điệp cố vấn]",
    ):
        paragraph = document.add_paragraph(caption)
        paragraph.paragraph_format.space_after = Pt(12)

    _add_section(document, "CÀI ĐẶT VÀ CHẠY")
    _add_subsection(document, "Cài đặt và kiểm tra")
    document.add_paragraph(
        "Windows PowerShell — chạy từ thư mục gốc repo trong môi trường Python mới:"
    )
    for command in (
        "python -m venv .venv",
        r".\.venv\Scripts\Activate.ps1",
        "python -m pip install --upgrade pip",
        "python -m pip install -r requirements.txt",
        "python -m pytest -v",
        "streamlit run app/main.py",
    ):
        document.add_paragraph(command, style="List Bullet")
    document.add_paragraph("Tạo báo cáo và kiểm tra tính nhất quán:")
    for command in (
        "python -m scripts.build_report",
        "python -m scripts.check_report_consistency",
    ):
        document.add_paragraph(command, style="List Bullet")
    full_test_line = next(
        (line.strip() for line in reversed(pytest_summary.splitlines()) if " passed" in line),
        "chưa kiểm chứng",
    )
    app_test_line = next(
        (line.strip() for line in reversed(app_test_summary.splitlines()) if " passed" in line),
        "chưa kiểm chứng",
    )
    hash_matches = sum(row["status"] == "MATCH" for row in hash_rows)
    document.add_paragraph(
        f"Kết quả tại repo: full pytest `{full_test_line}`; AppTest `{app_test_line}`; "
        f"Streamlit health `{health_summary.strip()}`; baseline hash {hash_matches}/{len(hash_rows)} MATCH."
    )
    document.add_paragraph(environment_validation)

    _add_section(document, "HẠN CHẾ VÀ PHẦN CHƯA HOÀN THÀNH")
    _add_subsection(document, "Giới hạn và việc cần xác nhận")
    for limitation in (
        "Chưa ghi nhận ngày truy cập/phiên bản PDF CTĐT trong artifact; mã HP và tính đầy đủ ngữ nghĩa tiên quyết còn UNCONFIRMED.",
        "Chưa xác nhận một số quy tắc suy từ CTĐT, bao gồm nhóm tự chọn, mở môn theo chẵn/lẻ và ngữ nghĩa môn song hành.",
        "UCI-697 là dữ liệu Bồ Đào Nha; hồ sơ SCENARIO minh họa, không phải dữ liệu sinh viên NTU.",
        "Kết quả dự báo xác suất đạt môn, tải, điểm đại diện, tính độc lập môn học và Monte Carlo có giả định; không phải kết quả thực tế.",
        "Môn học được mô phỏng độc lập; chưa mô hình hóa học kỳ hè, điều kiện mở lớp và học cải thiện.",
        "W3/W4 chưa có trong Monte Carlo do thiếu chuỗi điểm; phạm vi cảnh báo thôi học trong mô phỏng là W1/W2.",
        "Điểm đại diện 7,0/4,0 là GIẢ ĐỊNH. LightGBM chưa cài; OULAD không sử dụng.",
        "Ảnh/video giao diện do nhóm bổ sung; cài đặt từ môi trường sạch chưa được kiểm chứng trong chặng 6a.",
        "Không tìm thấy validator code_hash; kiểm tái tạo thay thế. source_label của histogram lưu trống, báo cáo gắn nhãn bằng hằng số script.",
        "Không kết luận mô phỏng tốt hơn cách đăng ký thông thường; các khác biệt chỉ thuộc kịch bản và giả định đã nêu.",
    ):
        document.add_paragraph(limitation, style="List Bullet")

    _add_section(document, "PHỤ LỤC — CÂY THƯ MỤC, FILE VÀ GIẢ ĐỊNH")
    _add_subsection(document, "Tham số giả định")
    document.add_paragraph(
        "Cây thư mục rút gọn: app/ (giao diện); core/ (logic không phụ thuộc Streamlit); "
        "config/ (quy chế và giả định); data/official/, data/scenarios/, data/processed/; "
        "models/; notebooks/; scripts/; tests/; docs/; reports/generated/; archive/ (chỉ lưu trữ, "
        "không dùng trong kết quả cuối). Gói dist/ sẽ được dựng riêng ở chặng 6b."
    )
    document.add_paragraph("Câu hỏi xin cô xác nhận (có phương án mặc định) được gửi riêng tại reports/generated/final_questions_for_co.md.")
    document.add_paragraph("Tham số GIẢ ĐỊNH chính:")
    assumptions = [
        [
            "β, γ và điểm hòa vốn p*",
            f"{objective_config['beta']}; {objective_config['gamma']}; {objective_config['p_break_even']}",
            "config/optimizer_scenario_v2.yaml",
        ],
        [
            "λ mặc định và ngưỡng tải",
            f"{load_config['lambda']}; {load_config['threshold_units']} units",
            "config/optimizer_scenario_v2.yaml",
        ],
        [
            "Multiplier học lại",
            " / ".join(str(value) for value in load_config["retake_multipliers"]),
            "config/optimizer_scenario_v2.yaml",
        ],
        [
            "N, seed, λ mô phỏng",
            f"{simulation_config['minimum_runs_per_profile_policy_lambda']}; "
            f"{simulation_config['seed']}; {simulation_config['default_lambdas']}",
            "config/monte_carlo_scenario.yaml",
        ],
        [
            "Điểm đại diện đạt/trượt",
            f"{simulation_config['pass_fail_proxy']['passed_course_grade_for_graduation_gpa']} / "
            f"{simulation_config['pass_fail_proxy']['failed_course_grade_for_transcript_state']}",
            "config/monte_carlo_scenario.yaml",
        ],
        [
            "Hè, mở lớp, học cải thiện",
            "chưa mô hình hóa/UNCONFIRMED",
            "reports/generated/regulation_assumptions.md",
        ],
    ]
    _add_table(
        document,
        "Phụ lục — tham số GIẢ ĐỊNH",
        ["Tham số", "Giá trị/phạm vi", "Nguồn"],
        assumptions,
    )
    deliverables = [
        "Mã nguồn: core/, app/, scripts/, tests/.",
        "Notebook: notebooks/01_eda_uci697.ipynb (chạy với REAL UCI-697); notebook cũ trong archive/ không dùng làm kết quả.",
        "Dữ liệu và cấu hình: data/official/, data/scenarios/, data/processed/, config/; dữ liệu scenario mang nhãn SCENARIO.",
        "ML: models/early_warning.joblib; reports/generated/model_comparison.csv, test_evaluation.json, ml_validation_bootstrap_ci.json, shap_global.csv.",
        "Rule/ILP: reports/generated/curriculum_validation.json, regulation_assumptions.md, plans_by_student.csv, ilp_sensitivity.csv.",
        "Monte Carlo: reports/generated/mc_results.csv, mc_grad_hist.csv, mc_pairwise.csv, mc_pareto.csv và diễn giải.",
        "Tài liệu chạy: README.md, HANDOFF.md, docs/screens_to_capture.md.",
        "Báo cáo: reports/stage2_report.docx; transcript: reports/generated/pytest_summary.txt.",
        "Ảnh/video demo: chưa có; nhóm bổ sung.",
    ]
    for item in deliverables:
        document.add_paragraph(item, style="List Bullet")
    document.add_paragraph(
        "Tệp nguồn chính: " + ", ".join(
            name for name in (
                "curriculum_validation.json", "metrics.json", "model_comparison.csv",
                "test_evaluation.json", "ml_validation_bootstrap_ci.json", "mc_results.csv",
                "mc_grad_hist.csv", "mc_pairwise.csv", "mc_pareto.csv", "plans_by_student.csv",
                "ilp_sensitivity.csv", "regulation_assumptions.md",
            )
        )
    )
    document.add_paragraph(
        "Ghi chú: ml_summary.json không có trong workspace tại thời điểm sinh báo cáo; "
        "nội dung ML lấy từ model_comparison.csv, test_evaluation.json, metrics.json và "
        "ml_validation_bootstrap_ci.json."
    )
    if not screens_path.is_file():
        raise FileNotFoundError(f"Screenshot instructions not found: {screens_path}")
    if not pytest_path.is_file():
        raise FileNotFoundError(f"Raw pytest output not found: {pytest_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    _write_heading_outline(document)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the stage 2 Word report from generated artifacts.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    output = build_report(args.output)
    print(f"REPORT_WRITTEN: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
