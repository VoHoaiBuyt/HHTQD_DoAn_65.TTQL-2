from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from docx import Document
from docx.table import Table as DocxTable
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt
from docx.text.paragraph import Paragraph

from app.risk_labels import RISK_THRESHOLDS
from scripts.build_report import (
    _markdown_table,
    _read_text,
    display_pareto_label,
    report_tables,
)
from scripts.final_claims import plan_signatures


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
REPORT_PATH = ROOT / "reports" / "BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx"
MEDIA = ROOT / "demo_media"
OUTBOX = ROOT / "outbox"
REQUIRED_IMAGES = (
    ("V2-005-PADK.png", "V2-005 · Phương án đăng ký", "Mức CAO, trạng thái bộ giải, cảnh báo cố vấn và ghi chú optimal."),
    ("V2-003-PADK.png", "V2-003 · Phương án đăng ký", "Bảng phương án và mức cảnh báo rủi ro."),
    ("V2-003-WhatIf.png", "V2-003 · What-if", "Bảng so sánh phương án mặc định và what-if."),
    ("V2-006-MP.png", "V2-006 · Mô phỏng", "Kết quả mô phỏng theo hồ sơ và λ đã chọn."),
    ("V2-006-HP.png", "V2-006 · Học phần", "Danh sách học phần và trạng thái điều kiện."),
    ("V2-006-DLGD.png", "V2-006 · Nguy cơ & cảnh báo", "Trang cảnh báo rủi ro của hồ sơ SCENARIO."),
)
REPORT_FIGURES = (
    (5, "final_confusion_matrix_test.png", "Ma trận nhầm lẫn trên tập test", "REAL (UCI-697), holdout test; được vẽ từ reports/generated/test_evaluation.json."),
    (5, "precision_recall_validation.png", "Đường precision–recall trên tập validation", "REAL (UCI-697), validation dùng lựa chọn mô hình/ngưỡng; reports/figures/precision_recall_validation.png."),
    (5, "calibration_validation.png", "Độ tin cậy xác suất trên tập validation", "REAL (UCI-697), validation; reports/figures/calibration_validation.png."),
    (5, "shap_global_validation.png", "SHAP toàn cục trên tập validation", "REAL (UCI-697), validation; SHAP giải thích mô hình, không phải nhân quả; reports/figures/shap_global_validation.png."),
    (7, "mc_graduation_distribution.png", "Phân phối kỳ tốt nghiệp theo chính sách", "SCENARIO / GIẢ ĐỊNH, artifact Monte Carlo đã lưu; reports/figures/mc_graduation_distribution.png."),
    (7, "mc_pareto.png", "Biên Pareto theo kịch bản mô phỏng", "SCENARIO / GIẢ ĐỊNH, artifact Monte Carlo đã lưu; nhãn Pareto phụ thuộc λ; reports/figures/mc_pareto.png."),
)
TABLE_SOURCES = {
    "CTĐT — kiểm tra": "OFFICIAL (NTU), validator CTĐT đã sinh.",
    "CTĐT — số kiểm tra và thông tin (tách riêng)": "OFFICIAL (NTU), curriculum_validation.json.",
    "CTĐT — mã HP cần xác minh": "OFFICIAL (NTU); mã HP có tiền tố HP là mã định danh nội bộ do nhóm gán.",
    "Quy chế — bảng giả định và trạng thái": "OFFICIAL (NTU), QĐ 753/QĐ-ĐHNT theo artifact nhóm cung cấp; diễn giải chưa xác nhận giữ UNCONFIRMED/UNKNOWN.",
    "ML — validation ba lớp": "REAL (UCI-697), model_comparison.csv.",
    "ML — validation nhị phân": "REAL (UCI-697), model_comparison.csv.",
    "ML — đánh giá holdout một lần": "REAL (UCI-697), test_evaluation.json; đánh giá đã lưu, không truy cập tập test trong tác vụ này.",
    "ML — bootstrap KTC 95% trên validation": "REAL (UCI-697), ml_validation_bootstrap_ci.json.",
    "ML — hiệu chuẩn xác suất (metrics.json)": "REAL (UCI-697), metrics.json.",
    "ML — SHAP toàn cục, năm đặc trưng đầu": "REAL (UCI-697), shap_global.csv; SHAP giải thích mô hình, không phải nhân quả.",
    "ILP — ba phương án cho 9 hồ sơ": "SCENARIO; GIẢ ĐỊNH cho xác suất, ngưỡng cảnh báo và hàm mục tiêu; giới hạn CTĐT lấy từ OFFICIAL (NTU).",
    "ILP — độ nhạy scenario V2-002": "SCENARIO / GIẢ ĐỊNH, ilp_sensitivity.csv.",
}
MC_TABLE_TITLES = {
    "Monte Carlo — kết quả từng hồ sơ, λ=0.1",
    "Monte Carlo — histogram từng hồ sơ, λ=0.1",
    "Monte Carlo — so sánh cặp từng hồ sơ, λ=0.1",
    "Monte Carlo — Pareto từng hồ sơ, λ=0.1",
    "Monte Carlo — KTC V2-001 và V2-003, λ=0.1",
    "Monte Carlo — Pareto V2-001 và V2-003, λ=0.1",
    "Monte Carlo — ghi chú metadata histogram, λ=0.1",
}


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


def _set_font(style, size: int, bold: bool | None = None, italic: bool | None = None) -> None:
    style.font.name = "Times New Roman"
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{key}"), "Times New Roman")


def _set_run_font(run, size: int, bold: bool | None = None, italic: bool | None = None) -> None:
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{key}"), "Times New Roman")


def _format_document(document: Document) -> None:
    for name in ("TOC 1", "TOC 2"):
        if name not in document.styles:
            document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    for style in document.styles:
        if style.type in {WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER}:
            _set_font(style, 12)
        if style.type == WD_STYLE_TYPE.PARAGRAPH:
            style.paragraph_format.line_spacing = 1.3
    for name in ("Normal", "Title", "Subtitle", "Caption", "TOC 1", "TOC 2"):
        _set_font(document.styles[name], 12)
    _set_font(document.styles["Heading 1"], 14, bold=True)
    _set_font(document.styles["Heading 2"], 13, bold=True)
    _set_font(document.styles["Heading 3"], 12, bold=True, italic=True)
    for section in document.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2)


def _add_field(paragraph, instruction: str, display: str = "1") -> None:
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), instruction)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), "Times New Roman")
    properties.append(fonts)
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "24")
    properties.append(size)
    run.append(properties)
    text = OxmlElement("w:t")
    text.text = display
    run.append(text)
    field.append(run)
    paragraph._p.append(field)


def _configure_fields(document: Document) -> None:
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    document.settings.element.append(update)


def _add_page_number(section) -> None:
    section.footer.is_linked_to_previous = False
    paragraph = section.footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run("Trang ")
    _add_field(paragraph, "PAGE")
    for run in paragraph.runs:
        _set_run_font(run, 12)


def _add_toc(document: Document, instruction: str) -> None:
    paragraph = document.add_paragraph()
    _add_field(paragraph, instruction, "")
    document.add_paragraph(
        "Mở bằng Microsoft Word và chọn Update Field để cập nhật danh mục.",
        style="Caption",
    )


def _add_heading(document: Document, level: int, text: str):
    return document.add_heading(text.upper() if level == 1 else text, level=level)


def _add_paragraph(document: Document, text: str, *, style: str | None = None):
    paragraph = document.add_paragraph(style=style)
    paragraph.add_run(text)
    return paragraph


def _add_caption(document: Document, chapter: int, kind: str, number: int, title: str) -> None:
    paragraph = document.add_paragraph(style="Caption")
    paragraph.paragraph_format.keep_with_next = True
    if kind == "table":
        paragraph.add_run(f"Bảng {chapter}.")
        reset = " \\r 1" if number == 1 else ""
        _add_field(paragraph, f"SEQ Table \\* ARABIC{reset}", str(number))
        paragraph.add_run(f". {title}")
    else:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run(f"Hình {chapter}.")
        reset = " \\r 1" if number == 1 else ""
        _add_field(paragraph, f"SEQ Figure \\* ARABIC{reset}", str(number))
        paragraph.add_run(f". {title}")
    for run in paragraph.runs:
        _set_run_font(run, 12)


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _add_table(
    document: Document,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    chapter: int | str,
    table_number: int,
    source: str,
) -> int:
    _add_caption(document, chapter, "table", table_number, title)
    reference = _add_paragraph(
        document, f"Bảng {chapter}.{table_number} trình bày dữ liệu theo nguồn đã ghi."
    )
    reference.paragraph_format.keep_with_next = True
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for index, value in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = str(value)
        _shade_cell(cell, "D9EAF7")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = str(value)
            cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.line_spacing = 1.3
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    _set_run_font(run, 11, bold=row is table.rows[0])
    _add_paragraph(document, f"Nguồn: {source}", style="Caption")
    return table_number + 1


def _add_image(
    document: Document,
    path: Path,
    chapter: int,
    figure_number: int,
    title: str,
    description: str,
    source: str,
) -> int:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    run.add_picture(str(path), width=Inches(6.0))
    inline = run._r.xpath(".//wp:docPr")
    if inline:
        inline[0].set("descr", description)
    _add_caption(document, chapter, "figure", figure_number, title)
    _add_paragraph(document, f"Nguồn: {source}", style="Caption")
    _add_paragraph(document, f"Hình {chapter}.{figure_number} được dùng để minh họa giao diện ở chương này.")
    return figure_number + 1


def _build_architecture_figure() -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    output = GENERATED / "final_architecture.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = [
        ("REAL (UCI-697)", "ML tại T1"),
        ("OFFICIAL (NTU)", "Quy tắc học vụ"),
        ("SCENARIO / GIẢ ĐỊNH", "ILP, phương án"),
        ("SCENARIO / GIẢ ĐỊNH", "Monte Carlo"),
        ("Hồ sơ SCENARIO", "Giao diện Streamlit"),
    ]
    fig, axis = plt.subplots(figsize=(12, 3.2))
    axis.set_xlim(0, 12)
    axis.set_ylim(0, 3.2)
    axis.axis("off")
    xs = [0.2, 2.6, 5.0, 7.4, 9.8]
    for index, (source, label) in enumerate(labels):
        box = FancyBboxPatch(
            (xs[index], 1.0), 2.0, 1.25,
            boxstyle="round,pad=0.08", linewidth=1.2,
            edgecolor="#284b63", facecolor="#e8f1f5",
        )
        axis.add_patch(box)
        axis.text(xs[index] + 1, 1.75, source, ha="center", va="center", fontsize=8, weight="bold")
        axis.text(xs[index] + 1, 1.3, label, ha="center", va="center", fontsize=9)
        if index < len(labels) - 1:
            axis.annotate(
                "", xy=(xs[index + 1] - 0.1, 1.62), xytext=(xs[index] + 2.1, 1.62),
                arrowprops={"arrowstyle": "->", "lw": 1.4, "color": "#284b63"},
            )
    axis.text(6, 0.45, "Luồng hỗ trợ quyết định; không thay thế tư vấn học vụ", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output


def _build_test_confusion_figure() -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    evaluation = _read_json("test_evaluation.json")
    matrix = np.asarray(evaluation["confusion_matrix"], dtype=int)
    if matrix.shape != (3, 3):
        raise ValueError(f"Expected a saved 3x3 test confusion matrix, received {matrix.shape}")
    output = GENERATED / "final_confusion_matrix_test.png"
    fig, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set(
        xticks=range(3), yticks=range(3),
        xticklabels=("Dropout", "Enrolled", "Graduate"),
        yticklabels=("Dropout", "Enrolled", "Graduate"),
        xlabel="Dự đoán", ylabel="Nhãn thật",
        title=f"XGBoost — holdout test (N={evaluation['test_rows']})",
    )
    for row in range(3):
        for column in range(3):
            axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
    fig.colorbar(image, ax=axis, label="Số mẫu")
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output


def _write_report_stats(path: Path) -> dict[str, Any]:
    document = Document(path)
    stats: dict[str, Any] = {
        "estimation_note": "Ước lượng, không phải số trang đo bằng bộ dựng Word/PDF.",
        "page_estimate_method": "≈400 từ/trang văn xuôi + số hàng dữ liệu/25 + 0.6 trang/hình; phụ lục loại khỏi tổng thân.",
        "total_word_count": 0,
        "table_count": len(document.tables),
        "figure_count": len(document.inline_shapes),
        "chapters": {},
        "body_estimated_pages_excluding_appendices": 0,
    }
    chapter_data: dict[str, dict[str, int | float]] = {}
    current = "front_matter"
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = "".join(child.xpath(".//w:t/text()"))
            style = child.xpath("./w:pPr/w:pStyle/@w:val")
            if style and style[0] == "Heading1" and text:
                match = re.match(r"CHƯƠNG (\d+)\.", text, re.I)
                if match:
                    current = f"chapter_{match.group(1)}"
                elif text.upper().startswith("PHỤ LỤC"):
                    current = "appendices"
            words = len(text.split())
            chapter_data.setdefault(current, {"words": 0, "table_rows": 0, "figures": 0})
            chapter_data[current]["words"] += words
            if child.xpath(".//wp:docPr"):
                chapter_data[current]["figures"] += 1
        elif child.tag.endswith("}tbl"):
            chapter_data.setdefault(current, {"words": 0, "table_rows": 0, "figures": 0})
            rows = child.xpath("./w:tr")
            chapter_data[current]["table_rows"] += max(0, len(rows) - 1)
            table_words = len(" ".join(child.xpath(".//w:t/text()")).split())
            chapter_data[current]["words"] += table_words
    for name, item in chapter_data.items():
        words = int(item["words"])
        rows = int(item["table_rows"])
        figures = int(item["figures"])
        pages = words / 400 + rows / 25 + figures * 0.6
        stats["chapters"][name] = {
            "word_count": words,
            "table_data_rows": rows,
            "figure_count": figures,
            "estimated_pages": round(pages, 2),
        }
        stats["total_word_count"] += words
        if name.startswith("chapter_"):
            stats["body_estimated_pages_excluding_appendices"] += pages
    stats["body_estimated_pages_excluding_appendices"] = round(
        stats["body_estimated_pages_excluding_appendices"], 2
    )
    (GENERATED / "report_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return stats


def _write_report_extract(path: Path) -> None:
    document = Document(path)
    lines = [
        "# Trích nguyên văn Chương 6, Chương 7 và Phụ lục A",
        "",
        "Nguồn: báo cáo Word cuối kỳ. Bảng được sao từ nội dung Word.",
        "",
    ]
    active = False
    sequence_numbers: dict[tuple[str, str], int] = defaultdict(int)
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            caption = re.match(r"^(Bảng|Hình) ([A-E]|\d+)\.\s*\.\s*(.+)$", text)
            instructions = [
                field.get(qn("w:instr"), "")
                for field in paragraph._p.xpath(".//w:fldSimple")
            ]
            if caption and any(
                instruction.startswith(
                    "SEQ Table" if caption.group(1) == "Bảng" else "SEQ Figure"
                )
                for instruction in instructions
            ):
                kind, chapter = caption.group(1), caption.group(2)
                sequence_numbers[(kind, chapter)] += 1
                text = f"{kind} {chapter}.{sequence_numbers[(kind, chapter)]}. {caption.group(3)}"
            if paragraph.style.name == "Heading 1":
                normalized = text.upper()
                if normalized.startswith("CHƯƠNG 6.") or normalized.startswith("CHƯƠNG 7.") or normalized.startswith("PHỤ LỤC A."):
                    active = True
                    lines.extend([f"## {text}", ""])
                else:
                    active = False
                continue
            if not active or not text:
                continue
            if paragraph.style.name == "Heading 2":
                lines.extend([f"### {text}", ""])
            else:
                lines.extend([text, ""])
        elif child.tag == qn("w:tbl") and active:
            table = DocxTable(child, document)
            rows = [[cell.text.replace("|", "\\|").replace("\n", " ") for cell in row.cells] for row in table.rows]
            if rows:
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
                lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
                lines.append("")
    (GENERATED / "final_sections_6_7_appendix_a.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def _parse_table(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        raise ValueError("Expected a Markdown table with a header and data rows")

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    headers = cells(lines[0])
    rows = [cells(line) for line in lines[2:] if len(cells(line)) == len(headers)]
    return headers, rows


def _set_page_numbering(section) -> None:
    sect_pr = section._sectPr
    pg_num = sect_pr.find(qn("w:pgNumType"))
    if pg_num is None:
        pg_num = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num)
    pg_num.set(qn("w:start"), "1")


def _profile_summary() -> tuple[int, int, list[str], int]:
    plans = _read_csv("plans_by_student.csv")
    identical, distinct, repeated = plan_signatures(plans)
    count = len({row["student_id"] for row in plans})
    return count, identical, repeated, distinct


def _budget_sensitivity_summary() -> tuple[int, dict[str, list[str]]]:
    rows = _read_csv("plans_by_budget.csv")
    signature_fields = (
        "plan_type",
        "status",
        "selected_course_ids",
        "selected_credits",
        "expected_credits_passed",
        "expected_failed_courses",
        "p_at_least_one_failure",
        "p_warning_W1",
        "p_warning_W2",
        "retake_credits_total",
        "estimated_graduation_semester",
        "risk_level",
    )
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["student_id"]][row["scenario_budget"]].append(row)
    if len(grouped) != 9 or any(len(plans) != 3 for budgets in grouped.values() for plans in budgets.values()):
        raise ValueError("Expected three plan rows per profile and budget in plans_by_budget.csv")
    differing_profiles: dict[str, list[str]] = {}
    for student_id, budgets in grouped.items():
        signatures = {
            budget: tuple(
                tuple(plan[field] for field in signature_fields)
                for plan in sorted(plans, key=lambda item: item["plan_type"])
            )
            for budget, plans in budgets.items()
        }
        if len(set(signatures.values())) > 1:
            differing_profiles[student_id] = sorted(budgets, key=int)
    return len(differing_profiles), differing_profiles


def _mc_summary_table() -> tuple[list[str], list[list[str]]]:
    rows = _read_csv("mc_results.csv")
    lambdas = sorted({float(row["lambda"]) for row in rows})
    policies = ("ILP-matched", "ILP-fixed", "B1", "B2", "B3")
    headers = ["λ", "Chính sách", "P(tốt nghiệp ≤8 kỳ)", "P(tốt nghiệp ≤16 kỳ)", "Kỳ tốt nghiệp TB", "Môn trượt kỳ vọng"]
    output = []
    for lam in lambdas:
        for policy in policies:
            group = [
                row for row in rows
                if float(row["lambda"]) == lam and row["policy"] == policy
            ]
            if not group:
                continue
            output.append([
                f"{lam:g}",
                policy,
                f"{sum(float(row['p_graduated_on_time']) for row in group) / len(group):.3f}",
                f"{sum(float(row['p_graduated_16']) for row in group) / len(group):.3f}",
                f"{sum(float(row['mean_graduation_semester']) for row in group) / len(group):.3f}",
                f"{sum(float(row['expected_failed_courses']) for row in group) / len(group):.3f}",
            ])
    return headers, output


def _mc_policy_mean(lambda_value: float, policy: str, metric: str) -> float:
    rows = [
        row for row in _read_csv("mc_results.csv")
        if float(row["lambda"]) == lambda_value and row["policy"] == policy
    ]
    if not rows:
        raise ValueError(f"No saved Monte Carlo rows for lambda={lambda_value}, policy={policy}")
    return sum(float(row[metric]) for row in rows) / len(rows)


def _mc_load_summary() -> dict[tuple[float, str], float]:
    grouped: dict[tuple[float, str], list[float]] = defaultdict(list)
    for row in _read_csv("mc_profile_metrics.csv"):
        key = (float(row["lambda"]), row["policy"])
        grouped[key].append(float(row["selected_load_mean"]))
    if not grouped:
        raise ValueError("mc_profile_metrics.csv contains no saved load summaries")
    return {key: max(values) for key, values in grouped.items()}


def _record_final_report_metrics() -> None:
    metrics_path = GENERATED / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8-sig"))
    monte_carlo = {}
    for lambda_value in (0.0, 0.1, 0.3):
        monte_carlo[f"lambda_{lambda_value:g}"] = {
            policy: {
                "p_graduated_on_time_mean": _mc_policy_mean(
                    lambda_value, policy, "p_graduated_on_time"
                ),
                "expected_failed_courses_mean": _mc_policy_mean(
                    lambda_value, policy, "expected_failed_courses"
                ),
            }
            for policy in ("ILP-matched", "B1", "B2")
        }
    load_summary = _mc_load_summary()
    metrics["final_report"] = {
        "source_label": "GIẢ ĐỊNH (tổng hợp từ artifact Monte Carlo đã lưu)",
        "sources": [
            "reports/generated/mc_results.csv",
            "reports/generated/mc_profile_metrics.csv",
        ],
        "monte_carlo": monte_carlo,
        "max_selected_load_mean_by_lambda_and_policy": {
            f"lambda_{lambda_value:g}": {
                policy: load_summary[(lambda_value, policy)]
                for policy in ("ILP-matched", "B1", "B2")
            }
            for lambda_value in (0.1, 0.3)
        },
    }
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _mc_ci_pareto_tables() -> tuple[list[str], list[list[str]], list[str], list[list[str]]]:
    pairwise = _read_csv("mc_pairwise.csv")
    pareto = _read_csv("mc_pareto.csv")
    students = {"V2-001", "V2-003"}
    pair_fields = (
        "student_id", "comparison", "lambda", "diff_p_graduated_on_time",
        "ci_p_graduated_on_time_lower", "ci_p_graduated_on_time_upper",
        "diff_expected_failed_courses", "ci_expected_failed_courses_lower",
        "ci_expected_failed_courses_upper",
    )
    paired_rows = [
        [row[field] for field in pair_fields]
        for row in pairwise
        if row["student_id"] in students
        and float(row["lambda"]) in {0.0, 0.1}
        and row["comparison"] in {"ILP-matched - B1", "ILP-matched - B2"}
    ]
    pareto_fields = ("student_id", "policy_a", "policy_b", "lambda", "dominance")
    pareto_rows = [
        [
            display_pareto_label(row["dominance"])
            if field == "dominance"
            else row[field]
            for field in pareto_fields
        ]
        for row in pareto
        if row["student_id"] in students
        and float(row["lambda"]) in {0.0, 0.1}
    ]
    if not paired_rows or not pareto_rows:
        raise ValueError("Saved MC artifacts do not contain the requested paired CI/Pareto rows")
    return list(pair_fields), paired_rows, list(pareto_fields), pareto_rows


def _write_cover_message() -> None:
    text = (
        "Kính gửi cô,\n\n"
        "Em gửi cô báo cáo cuối kỳ đã thống nhất thành một tệp Word duy nhất. "
        "Nhóm đã đổi nhãn phương án thành “Ưu tiên giảm rủi ro”, “Cân bằng” và “Tăng tốc”; "
        "`optimal` chỉ biểu thị nghiệm theo hàm mục tiêu và ràng buộc đã mô hình hóa. Báo cáo "
        "phân biệt REAL (UCI-697), OFFICIAL (NTU) do nhóm cung cấp, SCENARIO và các trường/"
        "quan hệ UNKNOWN hoặc UNCONFIRMED. Phần Monte Carlo giải thích ảnh hưởng của λ và giới "
        "hạn mô phỏng; kết quả không phải bằng chứng hiệu quả với sinh viên NTU. Tên tệp, "
        "README, HANDOFF, deliverables.md và đường dẫn dist đã thống nhất.\n\n"
        "Tệp đính kèm: báo cáo Word, mã nguồn, requirements, kết quả đã sinh, "
        "`reports/generated/pytest_summary.txt` đã loại đường dẫn cá nhân, ảnh giao diện và "
        "SHA256SUMS.txt. "
        "ML chưa được kiểm định trên sinh viên NTU; hai lần tái tạo Monte Carlo bổ sung chưa "
        "hoàn tất; giả định và dữ liệu CTĐT còn cần cố vấn xác nhận. Em kính mong cô góp ý.\n\n"
        "Em cảm ơn cô.\n\nHọ tên: ____________________\nMSSV: ____________________"
    )
    word_count = len(text.split())
    if not 150 <= word_count <= 200:
        raise ValueError(f"Final cover message must contain 150–200 words, got {word_count}")
    OUTBOX.mkdir(parents=True, exist_ok=True)
    (OUTBOX / "final_cover_message.md").write_text(text, encoding="utf-8")


def _write_feedback_matrix() -> None:
    source = _read_text("final_requirements_matrix.md")
    lines = source.splitlines()
    title = "# Phụ lục A — Phản hồi các góp ý"
    content = (
        title
        + "\n\n"
        + "Bảng dưới đây đối chiếu nhóm góp ý, thay đổi, vị trí và bằng chứng theo ma trận nguồn.\n\n"
        + "\n".join(line for line in lines if line.startswith("|"))
        + "\n"
    )
    (GENERATED / "final_response_to_feedback.md").write_text(content, encoding="utf-8")


def _prepare_final_mc_reproduction() -> Path:
    output = GENERATED / "final_mc_reproduction.md"
    if output.is_file():
        return output
    source = GENERATED / "mc_interpretation.md"
    if not source.is_file():
        raise FileNotFoundError(f"Monte Carlo reproduction evidence is missing: {source}")
    lines = _read_text("mc_interpretation.md").splitlines()
    reproduction = next(
        (line.strip().replace("**", "") for line in lines if line.strip().startswith("**Kiểm tái tạo")),
        None,
    )
    additional = next(
        (line.strip() for line in lines if line.strip().startswith("Tái tạo bổ sung")),
        None,
    )
    v2005 = next(
        (line.strip() for line in lines if line.strip().startswith("Với V2-005/B1,")),
        None,
    )
    if not reproduction or not additional or not v2005:
        raise ValueError(f"Monte Carlo reproduction evidence is incomplete: {source}")
    output.write_text(
        "# Kiểm chứng tái tạo Monte Carlo\n\n"
        + reproduction
        + "\n\n"
        + additional
        + "\n\n"
        + v2005
        + "\n",
        encoding="utf-8",
    )
    return output


def _write_heading_outline(document: Document) -> None:
    lines = ["# Danh sách Heading 1/2", ""]
    for paragraph in document.paragraphs:
        if paragraph.style.name in {"Heading 1", "Heading 2"}:
            lines.append(f"- {paragraph.style.name}: {paragraph.text}")
    (GENERATED / "final_heading_outline.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _prepare_styles(document: Document) -> None:
    for style_name in ("Normal", "Title", "Subtitle", "Caption", "Heading 1", "Heading 2", "Heading 3"):
        style = document.styles[style_name]
        size = {
            "Heading 1": 14,
            "Heading 2": 13,
            "Heading 3": 12,
            "Caption": 12,
        }.get(style_name, 12)
        _set_font(style, size, bold=style_name.startswith("Heading"))
    document.styles["Heading 1"].font.all_caps = True
    document.styles["Heading 3"].font.italic = True
    for style_name in ("Normal", "Heading 1", "Heading 2", "Heading 3"):
        document.styles[style_name].paragraph_format.line_spacing = 1.3


def build_final_report(*, final: bool = False, output_path: Path = REPORT_PATH) -> Path:
    _prepare_final_mc_reproduction()
    missing = [name for name, _, _ in REQUIRED_IMAGES if not (MEDIA / name).is_file()]
    if final and missing:
        raise FileNotFoundError(f"--final requires these real demo images: {missing}")
    if final:
        for name in ("metrics.json", "ml_validation_bootstrap_ci.json", "model_comparison.csv",
                     "plans_by_student.csv", "plans_by_budget.csv", "mc_results.csv",
                     "mc_pairwise.csv", "mc_pareto.csv", "mc_grad_hist.csv",
                     "mc_profile_metrics.csv", "final_mc_reproduction.md",
                     "final_requirements_matrix.md", "pytest_summary.txt", "prose_claims.csv"):
            if not (GENERATED / name).is_file():
                raise FileNotFoundError(f"--final requires reports/generated/{name}")

    _record_final_report_metrics()
    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)
    _prepare_styles(document)
    _format_document(document)
    _configure_fields(document)

    document.add_paragraph("TRƯỜNG ĐẠI HỌC NHA TRANG", style="Title").alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("KHOA CÔNG NGHỆ THÔNG TIN", style="Subtitle").alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("\nBÁO CÁO ĐỒ ÁN", style="Title").alignment = WD_ALIGN_PARAGRAPH.CENTER
    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("HỆ HỖ TRỢ CẢNH BÁO RỦI RO HỌC TẬP\nVÀ TỐI ƯU LỘ TRÌNH TÍN CHỈ")
    for line in (
        "Môn học: ______________________________",
        "Nhóm: _________________________________",
        "Giảng viên hướng dẫn: __________________",
        "Thời gian: _____________________________",
        "Thành viên · Họ tên / MSSV / phân công:",
        "1. _____________________________________",
        "2. _____________________________________",
        "3. _____________________________________",
        "4. _____________________________________",
    ):
        document.add_paragraph(line).alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_page_break()

    _add_heading(document, 1, "Lời mở đầu / Tóm tắt")
    profile_count, identical_count, repeated_profiles, distinct_count = _profile_summary()
    test_metrics = _read_json("test_evaluation.json")
    curriculum = _read_json("curriculum_validation.json")
    risk_rows = _read_csv("final_risk_levels.csv")
    high_count = sum(row["risk_level"] == "CAO" for row in risk_rows)
    v2005 = next(
        row for row in risk_rows
        if row["student_id"] == "V2-005" and row["plan_type"] == "risk_focused"
    )
    _add_paragraph(
        document,
        "Đề tài hiện thực luồng dự báo rủi ro tại T1, quy tắc đào tạo, tối ưu ILP, mô phỏng "
        "Monte Carlo và giao diện Streamlit. CTĐT/quy chế được nhóm cung cấp mang nhãn "
        "OFFICIAL (NTU); đặc trưng mô hình lấy từ REAL (UCI-697); hồ sơ là SCENARIO. "
        "Báo cáo nêu riêng các giả định và nội dung UNKNOWN/UNCONFIRMED, không coi đầu ra "
        "mô phỏng là xác nhận học vụ hay hiệu quả thực tế tại NTU."
    )
    _add_paragraph(
        document,
        f"Holdout đã lưu gồm {test_metrics['test_rows']} dòng, được đánh giá "
        f"{test_metrics['evaluation_count']} lần; Dropout recall của XGBoost ba lớp là "
        f"{test_metrics['per_class']['Dropout']['recall']:.4f}, còn Enrolled recall là "
        f"{test_metrics['per_class']['Enrolled']['recall']:.4f}. Kết quả holdout là kết quả "
        "đánh giá đã lưu; không truy cập tập test trong lần hoàn thiện này."
    )
    repeated = ", ".join(repeated_profiles) if repeated_profiles else "không có"
    budget_sensitive_count, budget_sensitive_profiles = _budget_sensitivity_summary()
    _add_paragraph(
        document,
        f"Trong {profile_count} hồ sơ SCENARIO, {identical_count} hồ sơ có ba phương án "
        f"trùng hoàn toàn với hồ sơ khác ({repeated}); có {distinct_count} bộ ba kết quả khác nhau. "
        f"{budget_sensitive_count}/{profile_count} hồ sơ có ít nhất hai mức ngân sách cho kết quả khác nhau."
    )
    _add_paragraph(
        document,
        f"Mức cảnh báo rủi ro là GIẢ ĐỊNH; {high_count} phương án trong bảng hiện hành ở mức CAO. "
        f"V2-005/Ưu tiên giảm rủi ro có P(W1)={float(v2005['p_warning_W1']):.3f}, "
        f"kỳ vọng trượt {float(v2005['expected_failed_courses']):.2f} môn. "
        "Phương án mức CAO kèm khuyến nghị trao đổi với cố vấn học tập."
    )
    _add_paragraph(
        document,
        f"Validator CTĐT ghi {curriculum['n_checks']} kiểm tra: {curriculum['n_pass']} PASS, "
        f"{curriculum['n_warn']} WARN, {curriculum['n_fail']} FAIL; đây là kết quả của artifact "
        "kiểm định, không phải xác nhận toàn bộ dữ liệu học vụ."
    )

    _add_heading(document, 1, "Mục lục")
    _add_toc(document, 'TOC \\o "1-2" \\h \\z \\u')
    _add_heading(document, 1, "Danh mục bảng")
    _add_toc(document, 'TOC \\h \\z \\c "Table"')
    _add_heading(document, 1, "Danh mục hình")
    _add_toc(document, 'TOC \\h \\z \\c "Figure"')
    _add_heading(document, 1, "Danh mục từ viết tắt")
    for abbreviation in (
        "ILP — quy hoạch tuyến tính nguyên.",
        "ML — học máy.",
        "KTC — khoảng tin cậy.",
        "NTU — Trường Đại học Nha Trang.",
        "UCI — University of California, Irvine.",
        "T1 — sau học kỳ 1, trước đăng ký học kỳ 2.",
        "W1/W2 — cảnh báo học vụ được mô hình trong phạm vi hiện hành.",
    ):
        _add_paragraph(document, abbreviation, style="List Bullet")
    body_section = document.add_section(WD_SECTION.NEW_PAGE)
    body_section.page_width = Cm(21)
    body_section.page_height = Cm(29.7)
    body_section.top_margin = Cm(2)
    body_section.bottom_margin = Cm(2)
    body_section.left_margin = Cm(3)
    body_section.right_margin = Cm(2)
    body_section.different_first_page_header_footer = False
    _set_page_numbering(body_section)
    _add_page_number(body_section)

    source_tables = {title: (headers, rows) for title, headers, rows in report_tables()}
    tables_by_chapter: dict[int, list[str]] = {
        3: [
            "CTĐT — số kiểm tra và thông tin (tách riêng)",
            "CTĐT — kiểm tra",
            "Quy chế — bảng giả định và trạng thái",
        ],
        5: [
            "ML — validation ba lớp",
            "ML — validation nhị phân",
            "ML — đánh giá holdout một lần",
            "ML — bootstrap KTC 95% trên validation",
            "ML — hiệu chuẩn xác suất (metrics.json)",
            "ML — SHAP toàn cục, năm đặc trưng đầu",
        ],
        6: ["ILP — độ nhạy scenario V2-002"],
    }
    counters = defaultdict(lambda: 1)
    figure_counters: dict[int, int] = defaultdict(lambda: 1)

    _add_heading(document, 1, "Chương 1. Giới thiệu")
    _add_heading(document, 2, "Bài toán, mục tiêu và phạm vi")
    _add_paragraph(
        document,
        "Bài toán là hỗ trợ rà soát rủi ro học tập và so sánh các lộ trình tín chỉ dưới nguồn "
        "CTĐT/quy chế do nhóm cung cấp. Hệ thống là prototype; đầu ra cần được người học và cố "
        "vấn đối chiếu với quy định hiện hành. Không dùng hồ sơ cá nhân thật."
    )
    _add_heading(document, 2, "Bố cục báo cáo")
    _add_paragraph(
        document,
        "Các chương trình bày dữ liệu/quy chế, kiến trúc và kiểm thử, mô hình ML, tối ưu ILP, "
        "Monte Carlo, giao diện, cài đặt, hạn chế; các phụ lục lưu góp ý, giả định và bàn giao."
    )

    _add_heading(document, 1, "Chương 2. Cơ sở và phương pháp")
    _add_heading(document, 2, "Dự báo, đánh giá và giải thích")
    _add_paragraph(
        document,
        "Bài toán phân lớp gồm Logistic Regression và Random Forest trong scikit-learn [3, 4], "
        "cùng XGBoost [5]. Chỉ số được "
        "trình bày theo lớp, gồm precision/recall/F1, PR-AUC và Brier; validation dùng lựa chọn "
        "mô hình/ngưỡng/hiệu chuẩn, còn holdout là đánh giá một lần đã ghi. Bootstrap mô tả "
        "khoảng tin cậy; SHAP [6] giải thích mô hình, không phải nhân quả."
    )
    _add_heading(document, 2, "ILP và mô phỏng")
    _add_paragraph(
        document,
        "Bộ tối ưu chọn học phần nhị phân với hàm mục tiêu có utility kỳ vọng và giá trị mở khóa; "
        "ràng buộc được tách khỏi các cảnh báo mềm. Monte Carlo đọc artifact kết quả đã lưu để "
        "đối chiếu chính sách và độ nhạy theo giả định. Không chạy lại Monte Carlo trong tác vụ này."
    )

    _add_heading(document, 1, "Chương 3. Dữ liệu và quy chế")
    _add_heading(document, 2, "Ba loại thông tin và nguồn")
    _add_paragraph(
        document,
        "REAL (UCI-697) là nguồn đặc trưng ML [1, 2], không phải dữ liệu sinh viên NTU. OFFICIAL (NTU) "
        "là CTĐT và QĐ 753/QĐ-ĐHNT theo tài liệu nhóm cung cấp; PDF QĐ và 210_CNTT.pdf không có "
        "trong repository nên chưa thể xác minh độc lập. SCENARIO là hồ sơ minh họa; "
        "các xác suất và tham số mô phỏng ghi GIẢ ĐỊNH. Trường không có trong nguồn được giữ "
        "UNKNOWN, source=NOT_FOUND."
    )
    _add_paragraph(
        document,
        "Trong data/official/courses.csv, mã HP0xx là mã định danh nội bộ do nhóm gán, không có "
        "trong PDF theo xác nhận của nhóm. PDF CTĐT do nhóm cung cấp nhưng không có trong repository; "
        "do đó danh sách mã và giới hạn truy nguyên được tách sang Phụ lục E, Bảng E.1 và "
        "docs/course_code_provenance.md, không khẳng định đã đối chiếu trực tiếp."
    )
    for title in tables_by_chapter[3]:
        headers, rows = source_tables[title]
        if title == "CTĐT — kiểm tra":
            headers, rows = source_tables[title]
        _add_table(
            document, title, headers, rows, 3, counters[3],
            TABLE_SOURCES.get(title, "OFFICIAL (NTU)"),
        )
        counters[3] += 1
    _add_heading(document, 2, "Giới hạn dữ liệu quy chế")
    _add_paragraph(
        document,
        "Validator hiện lưu trạng thái WARN và UNCONFIRMED; quan hệ tiên quyết/song hành chưa "
        f"được xác nhận đầy đủ. Artifact ghi {curriculum['summary']['prerequisite_graph']['edge_count']} "
        "quan hệ tiên quyết/song hành; tính đầy đủ vẫn chưa được xác nhận. Lịch mở môn suy từ chẵn/lẻ "
        "là GIẢ ĐỊNH (suy từ CTĐT) với quy tắc "
        "hiện hành trong config/courses_enrichment.yaml. Không suy diễn thêm môn, tín chỉ, tiên "
        "quyết, học kỳ hoặc giới hạn ngoài nguồn."
    )

    _add_heading(document, 1, "Chương 4. Thiết kế hệ thống")
    _add_heading(document, 2, "Luồng xử lý và rule engine")
    _add_paragraph(
        document,
        "Kiến trúc xử lý theo thứ tự ML tại T1 → kiểm tra quy tắc học vụ → ILP mô hình bằng "
        "PuLP [7] và giải bằng HiGHS [8, 10] → mô phỏng → giao diện Streamlit [9]. Logic nghiệp vụ "
        "ở core/ không phụ thuộc Streamlit. Lỗi xử lý môn "
        "song hành được sửa bằng cách lặp loại các học phần không đủ điều kiện tới khi tập đủ "
        "điều kiện ổn định; kiểm thử hồi quy và ý nghĩa quy chế của quan hệ này được nêu riêng."
    )
    architecture_path = _build_architecture_figure()
    figure_counters[4] = _add_image(
        document, architecture_path, 4, figure_counters[4],
        "Sơ đồ kiến trúc xử lý từ dữ liệu đến giao diện",
        "Luồng ML tại T1, quy tắc học vụ, ILP, Monte Carlo và giao diện; mỗi thành phần gắn nhãn nguồn.",
        "Tổng hợp kiến trúc thực tế; nguồn thành phần ghi trong sơ đồ, reports/generated/final_architecture.png.",
    )
    _add_heading(document, 2, "Kiểm thử nghiệp vụ")
    rule_rows = [
        ["Nguồn CTĐT và tính nhất quán", "tests/test_curriculum_validation.py; tests/test_data_consistency.py"],
        ["Tiên quyết, song hành và điều kiện học phần", "tests/test_core_rules.py; tests/test_official_rules.py"],
        ["Giới hạn tín chỉ, GPA, học lại", "tests/test_official_rules.py; tests/test_core_rules.py"],
        ["best_effort, xung đột và cảnh báo cố vấn", "tests/test_optimizer_v2.py; tests/test_app_smoke.py"],
        ["Cô lập hồ sơ và giao diện", "tests/test_app_smoke.py"],
    ]
    counters[4] = _add_table(
        document,
        "Nhóm kiểm thử rule engine và bằng chứng",
        ["Phạm vi", "Bằng chứng"],
        rule_rows,
        4,
        counters[4],
        "Mã kiểm thử trong tests/; kết quả chạy được ghi trong pytest_summary.txt.",
    )

    _add_heading(document, 1, "Chương 5. Mô hình ML")
    _add_heading(document, 2, "Mốc T1, tách tập và kết quả")
    _add_paragraph(
        document,
        "Mô hình chỉ có phạm vi hợp lệ sau HK1, trước đăng ký HK2. Pipeline loại các biến sau "
        "thời điểm T1 và fit tiền xử lý trong tập train. Validation được dùng lựa chọn mô hình/"
        "ngưỡng/hiệu chuẩn nên có thể lạc quan; holdout là kết quả chính và được dùng một lần "
        "sau khi lựa chọn đã cố định. Enrolled bị kiểm duyệt phải."
    )
    _add_paragraph(
        document,
        "Hình 5.1–5.4 lần lượt trình bày ma trận nhầm lẫn của holdout test, PR và hiệu chuẩn trên "
        "validation, cùng SHAP toàn cục trên validation; validation tham gia lựa chọn nên có thể lạc quan."
    )
    for chapter, name, title, source in REPORT_FIGURES:
        if chapter != 5:
            continue
        image_path = (
            _build_test_confusion_figure()
            if name == "final_confusion_matrix_test.png"
            else ROOT / "reports" / "figures" / name
        )
        if final and not image_path.is_file():
            raise FileNotFoundError(f"--final requires saved report figure: {image_path}")
        if image_path.is_file():
            figure_counters[chapter] = _add_image(
                document, image_path, chapter, figure_counters[chapter],
                title, title, source,
            )
    comparison = _read_csv("model_comparison.csv")
    three = next(row for row in comparison if row["task"] == "three_class" and row["model"] == "XGBoost")
    binary = next(row for row in comparison if row["task"] == "binary_dropout" and row["model"] == "XGBoost")
    bootstrap = _read_json("ml_validation_bootstrap_ci.json")
    ml_metrics = _read_json("metrics.json")["ml"]["validation"]
    three_recall = ml_metrics["multiclass"]["XGBoost"]["dropout_recall_at_precision_0.50"]["recall"]
    binary_recall = ml_metrics["binary"]["XGBoost"]["dropout_recall_at_precision_0.50"]["recall"]
    _add_paragraph(
        document,
        f"Validation XGBoost ba lớp so với nhị phân: PR-AUC Dropout "
        f"{float(three['dropout_pr_auc']):.4f} và {float(binary['dropout_pr_auc']):.4f}; "
        f"recall tại precision ≥ 0,50 là {three_recall:.4f} và {binary_recall:.4f}; "
        f"Brier là {float(three['dropout_brier']):.4f} và {float(binary['dropout_brier']):.4f}. "
        f"Bootstrap 95% của mô hình ba lớp: PR-AUC "
        f"[{float(bootstrap['metrics']['dropout_pr_auc']['ci95_lower']):.4f}, "
        f"{float(bootstrap['metrics']['dropout_pr_auc']['ci95_upper']):.4f}], Brier "
        f"[{float(bootstrap['metrics']['dropout_brier']['ci95_lower']):.4f}, "
        f"{float(bootstrap['metrics']['dropout_brier']['ci95_upper']):.4f}]. "
        "Artifact không có KTC ghép cặp cho chênh lệch giữa hai bài toán (và không lưu KTC "
        "nhị phân cho recall/Brier); do đó chưa thể kết luận có hay không phân biệt được "
        "về mặt thống kê giữa hai cách tiếp cận."
    )
    _add_paragraph(
        document,
        "Trên holdout đã lưu, Dropout recall của XGBoost ba lớp là "
        f"{test_metrics['per_class']['Dropout']['recall']:.4f} "
        f"({test_metrics['confusion_matrix'][0][0]}/{test_metrics['per_class']['Dropout']['support']}); "
        "đây không phải recall validation hay mô hình nhị phân. Recall lớp Enrolled thấp; "
        "kết quả không được khái quát sang sinh viên NTU."
    )
    for title in tables_by_chapter[5]:
        headers, rows = source_tables[title]
        _add_table(
            document, title, headers, rows, 5, counters[5],
            TABLE_SOURCES[title],
        )
        counters[5] += 1
    _add_heading(document, 2, "Giải thích mô hình")
    _add_paragraph(
        document,
        "SHAP mô tả đóng góp của đặc trưng cho đầu ra mô hình; không chứng minh quan hệ nhân quả. "
        "Sự khác biệt miền dữ liệu Bồ Đào Nha–NTU và recall Enrolled là hạn chế trọng yếu."
    )

    _add_heading(document, 1, "Chương 6. Tối ưu ILP")
    _add_heading(document, 2, "Mục tiêu, ràng buộc và cách đọc phương án")
    optimization = _read_text("optimization_spec.md")
    formulas = [
        line.strip().strip("`")
        for line in optimization.splitlines()
        if line.strip().startswith("`maximize")
    ]
    _add_paragraph(document, formulas[0] if formulas else "Hàm mục tiêu và quy tắc được lấy từ optimization_spec.md.")
    optimizer_config = yaml.safe_load(
        (ROOT / "config" / "optimizer_scenario_v2.yaml").read_text(encoding="utf-8-sig")
    )["optimizer"]
    u_line = next(
        line for line in optimization.splitlines()
        if line.startswith("Official strict prerequisite edges:")
    )
    u_values = json.loads(re.search(r"Nonzero prerequisite-only u_i: `([^`]+)`", u_line).group(1))
    _add_paragraph(
        document,
        f"Ngưỡng hòa vốn p*=γ/(1+γ)={optimizer_config['objective']['p_break_even']}; "
        f"β={optimizer_config['objective']['beta']}, γ={optimizer_config['objective']['gamma']}. "
        f"g_load tính theo L là tổng tín chỉ thực chọn và ngưỡng units(L)="
        f"{optimizer_config['load']['threshold_units']}; u_i khác 0 trên {len(u_values)} học phần "
        f"({', '.join(u_values)}), theo optimization_spec.md."
    )
    _add_paragraph(
        document,
        "Ba nhãn hiển thị là Ưu tiên giảm rủi ro, Cân bằng và Tăng tốc. Ngưỡng CAO/TRUNG BÌNH/THẤP "
        "là GIẢ ĐỊNH, tách khỏi trạng thái solver. Cấu hình main plan dùng risk_cap_mode=off; "
        "P(Dropout) và Fmax là khuyến nghị mềm, không khóa quyền đăng ký."
    )
    _add_paragraph(
        document,
        "Trạng thái `optimal` chỉ có nghĩa nghiệm tối ưu theo hàm mục tiêu và các ràng buộc đã "
        "mô hình hóa; không đồng nghĩa với phương án phù hợp nhất về mặt học vụ. Với mức CAO: "
        "khuyến nghị trao đổi với cố vấn học tập."
    )
    _add_paragraph(
        document,
        "V2-005 có P(W1)="
        f"{float(v2005['p_warning_W1']):.3f}, kỳ vọng trượt "
        f"{float(v2005['expected_failed_courses']):.2f} môn, mức CAO. "
        "Các trường hợp best_effort, regulatory_conflict và risk_cap_exceeded vẫn được trình bày "
        "kèm cảnh báo riêng; không được diễn giải solver status thành xác nhận học vụ."
    )
    for title in tables_by_chapter[6]:
        headers, rows = source_tables[title]
        _add_table(
            document, title, headers, rows, 6, counters[6],
            TABLE_SOURCES[title],
        )
        counters[6] += 1
    budget_rows = _read_csv("plans_by_budget.csv")
    budget_sensitive_count, budget_sensitive_profiles = _budget_sensitivity_summary()
    budget_diff_summary = "; ".join(
        "{}: {}".format(student_id, ", ".join(budgets))
        for student_id, budgets in budget_sensitive_profiles.items()
    ) or "không có"
    _add_paragraph(
        document,
        "Bảng các phương án cho chín hồ sơ và so sánh ngân sách dài được chuyển sang "
        "Phụ lục E, Bảng E.2–E.3. Ngân sách ở đó là kịch bản so sánh, không phải giới hạn chính thức. "
        f"{', '.join(repeated_profiles) if repeated_profiles else 'Không có hồ sơ'} có bộ ba phương án "
        "trùng hoàn toàn với hồ sơ khác do kế hoạch đã lưu có cùng học phần, tín chỉ và chỉ số "
        "đầu ra dưới các đầu vào/ràng buộc hiện hành. "
        f"{budget_sensitive_count}/9 hồ sơ có kết quả khác nhau ở ít nhất hai mức ngân sách "
        f"({budget_diff_summary}). Các giá trị giống nhau khi ngân sách tăng chỉ phản ánh kết quả artifact hiện có."
    )

    _add_heading(document, 1, "Chương 7. Mô phỏng Monte Carlo")
    _add_heading(document, 2, "7.1 Thiết kế mô phỏng")
    mc_rows = _read_csv("mc_results.csv")
    if not mc_rows:
        raise ValueError("mc_results.csv contains no saved Monte Carlo results")
    seeds = sorted({row.get("seed", "") for row in mc_rows if row.get("seed")})
    run_counts = sorted({row["n_runs"] for row in mc_rows if row.get("n_runs")})
    _add_paragraph(
        document,
        "Các bảng ở chương này chỉ đọc artifact Monte Carlo đã có; không chạy mô phỏng lại. "
        f"Nhãn đầu vào là SCENARIO / GIẢ ĐỊNH; N mỗi tổ hợp được đọc từ mc_results.csv "
        f"({', '.join(run_counts) if run_counts else 'UNKNOWN'} lượt). "
        f"Seed được lưu: {', '.join(seeds) if seeds else 'UNKNOWN'}."
    )
    mc_headers, mc_data = _mc_summary_table()
    counters[7] = _add_table(
        document,
        "Tóm tắt Monte Carlo theo λ và chính sách",
        mc_headers,
        mc_data,
        7,
        counters[7],
        "SCENARIO / GIẢ ĐỊNH, trung bình ngang trọng số từ mc_results.csv; không phải ước lượng NTU.",
    )
    saved_explanations = _read_json("mc_explanations.json")
    _add_heading(document, 2, "7.2 Vì sao kết quả thay đổi theo λ")
    _add_paragraph(
        document,
        "Trong mô hình, λ nhân với g_load; hàm phạt chỉ kích hoạt khi units(L) vượt 6. "
        "Bảng 7.2 đối chiếu tín chỉ L với ngưỡng và mức phạt; Bảng 7.3 cho thấy tải tín chỉ "
        "trung bình theo chính sách và λ. B1/B2 có hồ sơ vượt ngưỡng, trong khi ILP-matched "
        "nằm trong vùng không phạt tại λ=0,1 và 0,3, nên chỉ số ILP-matched giữ nguyên giữa hai "
        "mức λ trong artifact. Đây là hệ quả của giả định hàm mục tiêu, không phải bằng chứng thực nghiệm."
    )
    load_rows = saved_explanations["load_penalties"]
    counters[7] = _add_table(
        document,
        "Tải tín chỉ, units(L) và g_load theo λ",
        ["λ", "L tín chỉ", "Mean credits NW", "units(L)", "g_load", "Bị phạt"],
        [
            [
                f"{row['lambda']:.1f}",
                str(row["credits_L"]),
                f"{row['mean_credits_NW']:.4f}",
                str(row["units_L"]),
                f"{row['g_load']:.4f}",
                "Có" if row["penalized"] else "Không",
            ]
            for row in load_rows
        ],
        7,
        counters[7],
        "mc_explanations.json; quy tắc units(L) trong config/optimizer_scenario_v2.yaml.",
    )
    average_credit_rows = saved_explanations["average_selected_credits_per_semester"]
    counters[7] = _add_table(
        document,
        "Tín chỉ trung bình mỗi kỳ theo chính sách và λ",
        ["Chính sách", "λ", "Tín chỉ/kỳ trung bình", "Số hồ sơ", "Nhãn nguồn"],
        [
            [
                row["policy"],
                f"{row['lambda']:.1f}",
                f"{row['mean_credits_per_semester']:.4f}",
                str(row["profile_rows"]),
                row["source_label"],
            ]
            for row in average_credit_rows
        ],
        7,
        counters[7],
        "mc_explanations.json; kết quả mô phỏng SCENARIO / GIẢ ĐỊNH.",
    )
    _add_paragraph(
        document,
        f"Mean credits NW={saved_explanations['nw_mean_credits']:.4f}; "
        f"largest integer load without penalty={saved_explanations['largest_integer_load_without_penalty']} credits. "
        "Bảng 7.2 cho thấy tải L=15/18 nằm dưới ngưỡng, còn L=21/24 vượt ngưỡng theo cấu hình."
    )
    load_summary = _mc_load_summary()
    _add_paragraph(
        document,
        "Trong mc_profile_metrics.csv, selected_load_mean lớn nhất của ILP-matched là "
        f"{load_summary[(0.1, 'ILP-matched')]:.3f} ở λ=0,1 và "
        f"{load_summary[(0.3, 'ILP-matched')]:.3f} ở λ=0,3; đều dưới ngưỡng 18 tín chỉ "
        "tương ứng units(L)=6. Với B1/B2, các giá trị lớn nhất giữa hồ sơ lần lượt là "
        f"{load_summary[(0.1, 'B1')]:.3f}/{load_summary[(0.1, 'B2')]:.3f} ở λ=0,1 "
        f"và {load_summary[(0.3, 'B1')]:.3f}/{load_summary[(0.3, 'B2')]:.3f} ở λ=0,3; "
        "các tải vượt ngưỡng chịu phạt trong mô hình. Vì vậy thay đổi kết quả theo λ phụ thuộc "
        "giả định phạt tải, không phải bằng chứng thực nghiệm."
    )
    _add_heading(document, 2, "7.3 Vì sao ILP không luôn tốt hơn B1/B2")
    lambda_zero = {
        policy: {
            "p8": _mc_policy_mean(0.0, policy, "p_graduated_on_time"),
            "failed": _mc_policy_mean(0.0, policy, "expected_failed_courses"),
        }
        for policy in ("ILP-matched", "B1", "B2")
    }
    _add_paragraph(
        document,
        "Ở λ=0, P(tốt nghiệp ≤8 kỳ) của ILP-matched là "
        f"{lambda_zero['ILP-matched']['p8']:.3f}, so với "
        f"{lambda_zero['B1']['p8']:.3f} của B1 và {lambda_zero['B2']['p8']:.3f} của B2; "
        "số môn trượt kỳ vọng tương ứng là "
        f"{lambda_zero['ILP-matched']['failed']:.3f}, {lambda_zero['B1']['failed']:.3f} và "
        f"{lambda_zero['B2']['failed']:.3f}. ILP-matched có xác suất tốt nghiệp đúng hạn thấp "
        "hơn nhưng ít lượt trượt kỳ vọng hơn; vì vậy thứ hạng phụ thuộc chỉ tiêu. "
        "Lợi thế quan sát được tại λ>0 phụ thuộc giả định phạt tải; phân tích REAL (UCI-697), "
        "mục C.2, không xác nhận giả định quan hệ tải-phạt này."
    )
    _add_heading(document, 2, "7.4 Những yếu tố chưa được mô phỏng")
    _add_paragraph(
        document,
        "Chưa mô phỏng học kỳ hè, điều kiện mở lớp, học cải thiện, W3/W4, chuỗi điểm thật "
        "(dùng điểm đại diện 7,0/4,0), tương quan giữa các môn (giả định độc lập), hazard bỏ học "
        "tường minh và biến động chuẩn đầu ra (giả định đã đạt). M3′ là proxy từ dữ liệu Bồ Đào "
        "Nha, xác suất từng môn độc lập và không có hệ số độ khó; không cộng hazard dropout lần hai."
    )
    _add_heading(document, 2, "7.5 Kết quả theo hồ sơ (V2-001, V2-003)")
    _add_paragraph(
        document,
        "Bảng 7.4 trình bày KTC ghép cặp và Bảng 7.5 nhãn Pareto cho V2-001/V2-003 tại λ=0 "
        "và 0,1. Nhãn Pareto phụ thuộc λ và bộ chỉ tiêu; các phân loại cặp không phải kết luận "
        "tổng thể cho mọi mục tiêu."
    )
    paired_headers, paired_rows, pareto_headers, pareto_rows = _mc_ci_pareto_tables()
    counters[7] = _add_table(
        document,
        "KTC ghép cặp của V2-001/V2-003, λ=0 và λ=0.1",
        paired_headers,
        paired_rows,
        7,
        counters[7],
        "SCENARIO / GIẢ ĐỊNH, mc_pairwise.csv; cột KTC là bootstrap ghép cặp đã lưu.",
    )
    counters[7] = _add_table(
        document,
        "Nhãn Pareto V2-001/V2-003, λ=0 và λ=0.1",
        pareto_headers,
        pareto_rows,
        7,
        counters[7],
        "SCENARIO / GIẢ ĐỊNH, mc_pareto.csv. Nhãn Pareto là tên loại so sánh trong artifact, không phải kết luận tổng thể.",
    )
    for chapter, name, title, source in REPORT_FIGURES:
        if chapter != 7:
            continue
        image_path = ROOT / "reports" / "figures" / name
        if final and not image_path.is_file():
            raise FileNotFoundError(f"--final requires saved report figure: {image_path}")
        if image_path.is_file():
            figure_counters[chapter] = _add_image(
                document, image_path, chapter, figure_counters[chapter],
                title, title, source,
            )
    _add_heading(document, 2, "7.6 Kiểm tra tái tạo và độ tin cậy")
    interpretation = _read_text("final_mc_reproduction.md")
    reproduction = next(
        (line.strip().replace("**", "") for line in interpretation.splitlines()
         if line.strip().startswith("**Kiểm tái tạo")),
        "Phạm vi tái tạo được giới hạn; không có code_hash trong artifact.",
    )
    _add_paragraph(document, reproduction)
    additional_reproduction = next(
        (line.strip() for line in interpretation.splitlines()
         if line.strip().startswith("Tái tạo bổ sung")),
        "Hai lần tái tạo bổ sung chưa hoàn tất; chưa có kết quả đối chiếu.",
    )
    _add_paragraph(document, additional_reproduction)
    v2005_note = next(
        (line.strip() for line in interpretation.splitlines()
         if line.strip().startswith("Với V2-005/B1,")),
        None,
    )
    if v2005_note:
        _add_paragraph(
            document,
            v2005_note.replace(
                "V2-005_B1_results.csv", "reports/generated/V2-005_B1_results.csv"
            ).replace(
                "V2-005_B1_grad_hist.csv",                 "reports/generated/V2-005_B1_grad_hist.csv"
            ),
        )
    _add_paragraph(
        document,
        "Kết quả là phân tích kịch bản theo giả định; không phải bằng chứng hiệu quả với sinh viên NTU."
    )

    _add_heading(document, 1, "Chương 8. Giao diện hệ thống")
    _add_heading(document, 2, "Ảnh chụp thật và nội dung hiển thị")
    _add_paragraph(
        document,
        "Các ảnh sau được chụp từ ứng dụng Streamlit đang chạy, trên hồ sơ SCENARIO. "
        "Mức cảnh báo rủi ro hiển thị riêng với trạng thái bộ giải."
    )
    for name, screen, description in REQUIRED_IMAGES:
        if not (MEDIA / name).is_file():
            if final:
                raise FileNotFoundError(f"Required screenshot missing: {MEDIA / name}")
            continue
        figure_title = f"{screen} — {description}"
        figure_counters[8] = _add_image(
            document, MEDIA / name, 8, figure_counters[8], figure_title, description,
            f"Ảnh chụp thật từ demo_media/{name}; hồ sơ {screen.split(' · ')[0]}, nhãn SCENARIO.",
        )

    _add_heading(document, 1, "Chương 9. Kiểm thử và hướng dẫn cài đặt, chạy")
    _add_heading(document, 2, "Kiểm thử và gói sạch")
    pytest_summary = _read_text("pytest_summary.txt")
    summary_lines = [
        line.strip() for line in pytest_summary.splitlines()
        if re.search(r"\b\d+ passed\b", line)
    ]
    pytest_line = summary_lines[-1] if summary_lines else "Chưa có kết quả pytest tổng hợp."
    if re.search(r"(?i)(?<![\w])[A-Z]:(?:\\|/)", pytest_summary):
        raise ValueError("pytest_summary.txt contains machine-specific paths; sanitize it before --final")
    _add_paragraph(document, f"Kết quả pytest đã lưu: {pytest_line}")
    _add_paragraph(
        document,
        "Lệnh PowerShell: python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1; "
        "python -m pip install -r requirements.txt; python -m pytest; "
        "python -m streamlit run app/main.py."
    )
    _add_paragraph(
        document,
        "Không có LibreOffice/Microsoft Word renderer khả dụng; số trang thật chưa kiểm chứng. "
        "Ước lượng độ dài theo chương được ghi trong reports/generated/report_stats.json."
    )

    _add_heading(document, 1, "Chương 10. Kết luận, hạn chế và hướng phát triển")
    _add_heading(document, 2, "Kết luận")
    _add_paragraph(
        document,
        "Prototype tích hợp các thành phần dự báo tại T1, kiểm tra quy tắc, tối ưu lộ trình, "
        "mô phỏng kịch bản và giao diện. Đây là năng lực kỹ thuật của bản mẫu, không phải kết "
        "luận về hiệu quả cho sinh viên NTU."
    )
    _add_heading(document, 2, "Hạn chế và hướng phát triển")
    _add_paragraph(
        document,
        "Cần đối chiếu mã học phần, quan hệ tiên quyết/song hành, diễn giải QĐ 753 và lịch mở "
        "môn với cố vấn/đơn vị đào tạo. Mô hình ML cần được thẩm định với dữ liệu NTU được phép "
        "sử dụng; MC cần bổ sung các yếu tố học vụ còn thiếu và kiểm chứng với chuyên gia. "
        "Enrolled recall thấp, mô hình có khác biệt miền dữ liệu, còn nhiều giả định chưa xác nhận."
    )

    _add_heading(document, 1, "Tài liệu tham khảo")
    accessed = date.today().strftime("%d/%m/%Y")
    references = [
        f"Realinho, V., Machado, J., Baptista, L., & Martins, M. V. (2022). Predict Students’ Dropout and Academic Success [Dataset]. UCI Machine Learning Repository, dataset 697. https://doi.org/10.24432/C5MC89. Xác minh: trang UCI, mục Cite/metadata; truy cập {accessed}.",
        f"Realinho, V., Machado, J., Baptista, L., & Martins, M. V. (2022). Predicting Student Dropout and Academic Success. Data, 7(11), 146. https://doi.org/10.3390/data7110146. Xác minh: metadata Crossref theo DOI; truy cập {accessed}.",
        f"Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, E. (2011). Scikit-learn: Machine Learning in Python. Journal of Machine Learning Research, 12(85), 2825–2830. https://jmlr.org/papers/v12/pedregosa11a.html. Xác minh: trang bài báo JMLR; truy cập {accessed}.",
        f"Breiman, L. (2001). Random Forests. Machine Learning, 45(1), 5–32. https://doi.org/10.1023/A:1010933404324. Xác minh: metadata Crossref theo DOI; truy cập {accessed}.",
        f"Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 785–794. https://doi.org/10.1145/2939672.2939785. Xác minh: metadata Crossref theo DOI; truy cập {accessed}.",
        f"Lundberg, S. M., & Lee, S.-I. (2017). A Unified Approach to Interpreting Model Predictions. Advances in Neural Information Processing Systems 30. https://papers.nips.cc/paper/7062-a-unified-approach-to-interpreting-model-predictions. Xác minh: trang proceedings NeurIPS; truy cập {accessed}.",
        f"Department of Engineering Science, The University of Auckland (2011). PuLP: A Linear Programming Toolkit for Python. Optimization Online. https://optimization-online.org/2011/09/3178/. Xác minh: trang bài viết và tệp PDF liên kết; truy cập {accessed}.",
        f"Huangfu, Q., & Hall, J. A. J. (2018). Parallelizing the dual revised simplex method. Mathematical Programming Computation, 10(1), 119–142. https://doi.org/10.1007/s12532-017-0130-5. Xác minh: metadata Crossref theo DOI; truy cập {accessed}.",
        f"Streamlit, Inc. (n.d.). Streamlit documentation. https://docs.streamlit.io/. Xác minh: trang tài liệu chính thức; truy cập {accessed}.",
        f"ERGO-Code. (n.d.). HiGHS — Linear optimization software. https://github.com/ERGO-Code/HiGHS. Xác minh: kho mã chính thức và mô tả solver; truy cập {accessed}.",
    ]
    for index, reference in enumerate(references, 1):
        _add_paragraph(document, f"[{index}] {reference}")
    _add_paragraph(
        document,
        "QĐ 753/QĐ-ĐHNT, Thông tư 08/2021/TT-BGDĐT và PDF 210_CNTT.pdf chưa được liệt kê "
        "thành mục trích dẫn vì bản gốc hoặc trang văn bản cụ thể chưa xác minh được trong lượt "
        "tra cứu này; bản PDF QĐ/CTĐT cũng không có trong repository. Nhãn OFFICIAL (NTU) trong "
        "báo cáo chỉ phản ánh hồ sơ do nhóm cung cấp, không thay thế việc đính kèm và kiểm tra nguồn gốc.",
    )

    _add_heading(document, 1, "Phụ lục A. Phản hồi từng góp ý")
    matrix_headers, matrix_rows = _parse_table(_read_text("final_requirements_matrix.md"))
    _add_table(
        document,
        "Ma trận góp ý, thay đổi, vị trí và bằng chứng",
        matrix_headers,
        matrix_rows,
        "A",
        counters[0],
        "reports/generated/final_requirements_matrix.md; bảng được dựng trực tiếp từ nguồn.",
    )
    _write_feedback_matrix()

    _add_heading(document, 1, "Phụ lục B. Tham số GIẢ ĐỊNH và trạng thái")
    assumption_rows = [
        ["Tải phạt, ngưỡng units(L), γ, β, δ, hệ số học lại", "GIẢ ĐỊNH", "config/optimizer_scenario_v2.yaml", "UNCONFIRMED"],
        [
            "Ngưỡng mức cảnh báo",
            (
                f"CAO: expected failures ≥{RISK_THRESHOLDS['high_failed_courses']:.1f} "
                f"hoặc P(W1)/P(W2) ≥{RISK_THRESHOLDS['high_warning_probability']:.1f}; "
                f"TRUNG BÌNH: expected failures ≥{RISK_THRESHOLDS['medium_failed_courses']:.1f}"
            ),
            "app/risk_labels.py; GIẢ ĐỊNH. fast_fmax trong optimizer chỉ áp dụng cho chiến lược Tăng tốc.",
            "UNCONFIRMED",
        ],
        ["M3′ và phân bố xác suất từng môn", "GIẢ ĐỊNH / dữ liệu ngoài NTU", "config/monte_carlo_scenario.yaml", "UNCONFIRMED"],
        ["Tính độc lập giữa kết quả các môn", "GIẢ ĐỊNH", "config/monte_carlo_scenario.yaml", "UNCONFIRMED"],
        ["Điểm đại diện đạt/trượt và hazard", "GIẢ ĐỊNH; hazard tường minh chưa mô phỏng", "config/monte_carlo_scenario.yaml", "UNCONFIRMED"],
        ["Quan hệ tiên quyết/song hành và mở môn", "OFFICIAL chưa xác nhận đầy đủ / GIẢ ĐỊNH suy từ CTĐT", "data/official/; config/courses_enrichment.yaml", "UNCONFIRMED"],
    ]
    _add_table(
        document,
        "Danh mục giả định và tình trạng xác nhận",
        ["Tham số/diễn giải", "Nhãn", "Nguồn", "Trạng thái"],
        assumption_rows,
        "B",
        1,
        "config/, reports/generated/optimization_spec.md; chưa xác nhận được ghi UNCONFIRMED.",
    )

    _add_heading(document, 1, "Phụ lục C. Danh mục bàn giao và cấu trúc thư mục")
    dist = ROOT / "dist"
    if dist.is_dir():
        tree_lines = []
        for path in sorted(dist.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())):
            suffix = "/" if path.is_dir() else ""
            tree_lines.append(path.name + suffix)
    else:
        tree_lines = ["dist chưa dựng; cấu trúc chưa kiểm chứng."]
    _add_paragraph(document, "Cây thư mục cấp một thực tế của dist/ tại thời điểm sinh:")
    for line in tree_lines:
        _add_paragraph(document, line, style="List Bullet")
    _add_paragraph(
        document,
        "Gói chỉ gồm tệp phục vụ chạy, kiểm chứng và bàn giao; tư liệu lưu trữ, tài liệu mẫu, "
        "môi trường phát triển và cache không thuộc gói. Tên báo cáo duy nhất trong gói là "
        "reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx."
    )
    _add_heading(document, 1, "Phụ lục D. Phân công thành viên")
    for index in range(1, 5):
        _add_paragraph(document, f"{index}. Họ tên: ____________________  MSSV: ____________________  Phân công: ____________________")

    _add_heading(document, 1, "Phụ lục E. Bảng chi tiết và artifact hỗ trợ")
    _add_paragraph(
        document,
        "Phụ lục này lưu các bảng dài và bảng chi tiết đã rút khỏi Chương 3, 6 và 7. "
        "Giá trị giữ nguyên từ file nguồn; nhãn nguồn và giới hạn xác minh đi kèm từng bảng."
    )
    appendix_tables = [
        (
            "CTĐT — mã HP cần xác minh",
            *source_tables["CTĐT — mã HP cần xác minh"],
            "OFFICIAL (NTU) theo nguồn nhóm cung cấp; mã HP0xx do nhóm gán; PDF 210_CNTT.pdf không có trong repository.",
        ),
        (
            "ILP — ba phương án cho 9 hồ sơ",
            *source_tables["ILP — ba phương án cho 9 hồ sơ"],
            TABLE_SOURCES["ILP — ba phương án cho 9 hồ sơ"],
        ),
    ]
    budget_headers = list(budget_rows[0].keys())
    appendix_tables.append((
        "So sánh kế hoạch theo ngân sách",
        budget_headers,
        [[row[key] for key in budget_headers] for row in budget_rows],
        "SCENARIO / GIẢ ĐỊNH, reports/generated/plans_by_budget.csv; không phải giới hạn chính thức.",
    ))
    expulsion_profiles = saved_explanations[
        "profiles_with_expulsion_probability_at_least_0_95_under_all_rows"
    ]
    expulsion_headers = [
        "Hồ sơ", "P(buộc thôi học), min–max", "Môn trượt kỳ vọng, min–max",
        "P(tốt nghiệp ≤16 kỳ), min–max", "Giới hạn cảnh báo liên tiếp", "Nguyên nhân/diễn giải",
    ]
    expulsion_rows = [
        [
            row["student_id"],
            f"{row['p_expelled_min']:.3f}–{row['p_expelled_max']:.3f}",
            f"{row['expected_failed_courses_min']:.3f}–{row['expected_failed_courses_max']:.3f}",
            f"{row['p_graduated_16_min']:.3f}–{row['p_graduated_16_max']:.3f}",
            str(row["consecutive_warning_limit"]),
            row["interpretation"],
        ]
        for row in expulsion_profiles
    ] or [["Không có hồ sơ đạt ngưỡng trong artifact.", "", "", "", "", "Chưa kiểm chứng ngoài các dòng đã lưu."]]
    appendix_tables.append((
        "Hồ sơ P(buộc thôi học) ≥0.95 ở mọi chính sách đã lưu",
        expulsion_headers,
        expulsion_rows,
        "SCENARIO / GIẢ ĐỊNH, reports/generated/mc_explanations.json.",
    ))
    for title in sorted(MC_TABLE_TITLES):
        headers, rows = source_tables[title]
        appendix_tables.append((
            title, headers, rows,
            "SCENARIO / GIẢ ĐỊNH; artifact Monte Carlo đã lưu trong reports/generated/.",
        ))
    for table_title, headers, rows, source in appendix_tables:
        _add_table(document, table_title, headers, rows, "E", counters["E"], source)
        counters["E"] += 1
        if table_title == "ILP — ba phương án cho 9 hồ sơ":
            _add_paragraph(
                document,
                "Ghi chú: mọi trạng thái best_effort đi kèm cảnh báo rủi ro và khuyến nghị trao đổi "
                "với cố vấn học tập; không có phương án nào được xác nhận là an toàn.",
            )

    for paragraph in document.paragraphs:
        if paragraph.style.name.startswith("Heading"):
            paragraph.paragraph_format.keep_with_next = True
        for run in paragraph.runs:
            heading_size = {
                "Heading 1": 14,
                "Heading 2": 13,
                "Heading 3": 12,
            }.get(paragraph.style.name)
            if heading_size is not None:
                _set_run_font(
                    run,
                    heading_size,
                    bold=True,
                    italic=paragraph.style.name == "Heading 3",
                )
            elif run.font.name != "Times New Roman":
                _set_run_font(run, 12)
    document.save(output_path)
    _write_cover_message()
    _write_heading_outline(document)
    _write_report_extract(output_path)
    _write_report_stats(output_path)
    if final:
        _validate_final_document(output_path)
    return output_path


def _validate_final_document(path: Path) -> None:
    document = Document(path)
    text = "\n".join([p.text for p in document.paragraphs] + [
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    ])
    forbidden_internal = re.compile(r"\b(?:AQL|ATT|agent)\b|Phần \d+-fix|_repro_tmp", re.I)
    if forbidden_internal.search(text):
        raise ValueError(f"--final report includes an internal/obsolete term: {forbidden_internal.search(text).group()}")
    placeholders = re.compile(r"\b(TODO|TBD|PLACEHOLDER|CHƯA CÓ ẢNH|Hình ảnh sẽ được bổ sung)\b", re.I)
    if placeholders.search(text):
        raise ValueError(f"--final report contains a placeholder: {placeholders.search(text).group()}")
    expected_figures = len(REQUIRED_IMAGES) + len(REPORT_FIGURES) + 1
    if len(document.inline_shapes) != expected_figures:
        raise ValueError(f"--final expected {expected_figures} report figures, found {len(document.inline_shapes)}")
    headings = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
    expected_chapters = [f"CHƯƠNG {i}." for i in range(1, 11)]
    missing = [prefix for prefix in expected_chapters if not any(h.startswith(prefix) for h in headings)]
    if missing:
        raise ValueError(f"--final missing chapter headings: {missing}")
    for required in ("pytest_summary.txt", "report_stats.json"):
        if not (GENERATED / required).is_file():
            raise FileNotFoundError(f"--final requires reports/generated/{required}")
    chapter7_sections = {
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.style.name == "Heading 2"
    }
    expected_chapter7_sections = {
        "7.1 Thiết kế mô phỏng",
        "7.2 Vì sao kết quả thay đổi theo λ",
        "7.3 Vì sao ILP không luôn tốt hơn B1/B2",
        "7.4 Những yếu tố chưa được mô phỏng",
        "7.5 Kết quả theo hồ sơ (V2-001, V2-003)",
        "7.6 Kiểm tra tái tạo và độ tin cậy",
    }
    if not expected_chapter7_sections.issubset(chapter7_sections):
        raise ValueError(f"--final is missing Chapter 7 sections: {expected_chapter7_sections - chapter7_sections}")
    for required in ("PHỤ LỤC E.",):
        if not any(h.startswith(required) for h in headings):
            raise ValueError(f"--final missing required appendix heading: {required}")
    broken = []
    for match in re.finditer(r"(?<![\w:])(?:[\w.-]+/)+[\w .-]+\.(?:py|md|csv|json|yaml|yml|docx|png|txt)", text):
        candidate = ROOT / Path(match.group().replace("/", "\\"))
        if not candidate.exists():
            broken.append(match.group())
    if broken:
        raise FileNotFoundError(f"--final report references missing repository paths: {sorted(set(broken))}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build the single source-driven final Word report.")
    parser.add_argument("--final", action="store_true", help="Fail on missing evidence, placeholders, and broken references.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    print(f"REPORT={build_final_report(final=args.final, output_path=output)}")


if __name__ == "__main__":
    main()
