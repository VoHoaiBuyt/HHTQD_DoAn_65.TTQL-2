from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from scripts.build_report import (
    MC_HISTOGRAM_SOURCE_LABEL,
    REPORT_PATH,
    ROOT,
    _markdown_table,
    _read_text,
    report_tables,
)


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
    if "Kiểm tái tạo (thay cho code_hash không tồn tại)" not in report_text:
        raise ValueError("Report is missing the Monte Carlo reproducibility disclosure")
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
    return checked


def main() -> None:
    checked = check_report()
    print("PASS: curriculum n_checks sourced from JSON; informational counts are separate.")
    print(f"PASS: {len(checked)} source tables match reports/generated inputs.")
    print(f"PASS: {len(REQUIRED_HEADINGS)} required report sections are present.")
    print(f"REPORT_CONSISTENCY: PASS ({len(checked)} tables)")


if __name__ == "__main__":
    main()
