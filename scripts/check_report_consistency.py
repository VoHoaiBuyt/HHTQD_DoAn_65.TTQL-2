from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from scripts.build_report import (
    MC_HISTOGRAM_SOURCE_LABEL,
    REPORT_PATH,
    ROOT,
    _markdown_table,
    _read_text,
    report_tables,
)
from scripts.audit_report_prose import audit as audit_report_prose


REQUIRED_HEADINGS = {
    "TÓM TẮT ĐIỀU HÀNH",
    "DỮ LIỆU OFFICIAL (NTU)",
    "QUY CHẾ QĐ 753/2021 VÀ CÁCH MÔ HÌNH HÓA",
    "MÔ HÌNH ML — MỐC T1",
    "RULE ENGINE VÀ KẾT QUẢ KIỂM THỬ",
    "ILP — HÀM MỤC TIÊU VÀ CÁC PHƯƠNG ÁN",
    "MONTE CARLO — MÔ PHỎNG, KHÔNG PHẢI BẰNG CHỨNG THỰC TẾ",
    "GIAO DIỆN STREAMLIT",
    "CÀI ĐẶT VÀ CHẠY",
    "HẠN CHẾ VÀ PHẦN CHƯA HOÀN THÀNH",
    "PHỤ LỤC — CÂY THƯ MỤC, FILE VÀ GIẢ ĐỊNH",
}


def _table_contents(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def check_report(report_path: Path = REPORT_PATH) -> list[str]:
    if not report_path.is_file():
        raise FileNotFoundError(f"Word report not found: {report_path}")
    document = Document(report_path)
    paragraphs = [
        re.sub(r"^\d+\.\s*", "", paragraph.text.strip())
        for paragraph in document.paragraphs
    ]
    missing_headings = sorted(REQUIRED_HEADINGS - set(paragraphs))
    if missing_headings:
        raise ValueError(f"Report is missing required headings: {missing_headings}")

    tables_by_title: dict[str, list[list[str]]] = {}
    for table in document.tables:
        contents = _table_contents(table)
        if not contents or not contents[0]:
            continue
        title = contents[0][0]
        if title in tables_by_title:
            raise ValueError(f"Duplicate report source table: {title}")
        tables_by_title[title] = contents

    checked = []
    for title, headers, rows in report_tables():
        if title not in tables_by_title:
            raise ValueError(f"Report is missing source table: {title}")
        actual = tables_by_title[title]
        expected = [[title] + [""] * (len(headers) - 1), headers, *rows]
        if actual != expected:
            raise ValueError(
                f"Report table does not match generated source: {title}; "
                f"expected {len(expected)} rows, got {len(actual)}"
            )
        checked.append(title)

    matrix_headers, matrix_rows = _markdown_table(
        _read_text("final_requirements_matrix.md")
    )
    matrix = tables_by_title.get("Các điểm đã chỉnh so với báo cáo lần trước")
    expected_matrix = [
        ["Các điểm đã chỉnh so với báo cáo lần trước"]
        + [""] * (len(matrix_headers) - 1),
        matrix_headers,
        *matrix_rows,
    ]
    if matrix != expected_matrix:
        raise ValueError("The report's comparison matrix differs from final_requirements_matrix.md")
    histogram = tables_by_title["Monte Carlo — histogram từng hồ sơ, λ=0.1"]
    if any(row[-1] != MC_HISTOGRAM_SOURCE_LABEL for row in histogram[2:]):
        raise ValueError("Histogram display labels do not use the report generator source label")
    report_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    if "Kiểm tái tạo 3 nhóm (V2-001/ILP-matched, V2-001/B1, V2-005/B1; λ=0,1)" not in report_text:
        raise ValueError("Report is missing the Monte Carlo reproducibility disclosure")
    interpretation = _read_text("mc_interpretation.md")
    if "Kiểm tái tạo 3 nhóm (V2-001/ILP-matched, V2-001/B1, V2-005/B1; λ=0,1)" not in interpretation:
        raise ValueError("Monte Carlo interpretation is missing the scoped reproduction disclosure")
    if "optimizer không nằm trong" in report_text or "không ảnh hưởng đến kết quả đã lưu" in report_text:
        raise ValueError("Report contains an unsupported broad optimizer-impact claim")
    checked.append("Các điểm đã chỉnh so với báo cáo lần trước")

    curriculum_table = next(
        rows for title, _, rows in report_tables()
        if title == "CTĐT — số kiểm tra và thông tin (tách riêng)"
    )
    summary = {row[0]: row[1] for row in curriculum_table}
    checks = int(summary["n_checks (đếm từ JSON)"])
    if checks != len(
        next(rows for title, _, rows in report_tables() if title == "CTĐT — kiểm tra")
    ):
        raise ValueError("n_checks is not the number of validation checks")
    prose_numbers = audit_report_prose()
    unmatched = [
        row for row in prose_numbers
        if row["source_match"] == "KHÔNG KHỚP/CHƯA XÁC ĐỊNH"
    ]
    if unmatched:
        raise ValueError(
            f"Report prose contains {len(unmatched)} numbers without a generated/config source match"
        )
    heading_styles = [
        paragraph.style.name
        for paragraph in document.paragraphs
        if paragraph.style.name in {"Heading 1", "Heading 2"}
    ]
    if "Heading 1" not in heading_styles or "Heading 2" not in heading_styles:
        raise ValueError("Report must contain both Heading 1 and Heading 2 styles")
    field_instructions = [
        field.get(qn("w:instr"), "")
        for field in document._element.xpath(".//w:fldSimple")
    ]
    if not any(instruction.startswith("TOC ") for instruction in field_instructions):
        raise ValueError("Report is missing the automatic level 1–2 table-of-contents field")
    update_fields = document.settings.element.find(qn("w:updateFields"))
    if update_fields is None or update_fields.get(qn("w:val")) not in {"true", "1"}:
        raise ValueError("Word updateFields is not enabled")
    footer_xml = "\n".join(
        paragraph._p.xml
        for section in document.sections
        for paragraph in section.footer.paragraphs
    )
    if " PAGE " not in footer_xml:
        raise ValueError("Report footer is missing its page-number field")
    plan_table = tables_by_title["ILP — ba phương án cho 9 hồ sơ"]
    if "Mức cảnh báo rủi ro" not in plan_table[1]:
        raise ValueError("Plan table is missing the risk-level column")
    if len(plan_table) != 29:
        raise ValueError("Plan table must contain all 27 plans and its two header rows")
    if not any(
        "khuyến nghị trao đổi với cố vấn học tập" in cell
        for row in plan_table[2:]
        for cell in row
    ):
        raise ValueError("High-risk plan rows are missing the advisor recommendation")
    if "XGBoost: PR-AUC Dropout ba lớp=" not in report_text or "recall tại precision ≥ 0,50" not in report_text:
        raise ValueError("Report is missing the corrected validation comparison")
    if "chênh=0.0458" in report_text or "recall ba lớp=0.7113, nhị phân=0.6655" in report_text:
        raise ValueError("Report contains the incorrect validation/test recall comparison")
    return checked


def main() -> None:
    checked = check_report()
    print("PASS: curriculum n_checks sourced from JSON; informational counts are separate.")
    print(f"PASS: {len(checked)} source tables match reports/generated inputs.")
    print(f"PASS: {len(REQUIRED_HEADINGS)} required report sections are present.")
    prose_numbers = audit_report_prose()
    print(
        f"PASS: {len(prose_numbers)} prose-number occurrences matched reports/generated or config; 0 unresolved."
    )
    print(f"REPORT_CONSISTENCY: PASS ({len(checked)} tables)")


if __name__ == "__main__":
    main()
