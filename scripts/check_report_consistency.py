from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE

from scripts.build_final_report import (
    MEDIA,
    REQUIRED_IMAGES,
    REPORT_FIGURES,
    REPORT_PATH,
    ROOT,
    _parse_table,
    _read_text,
)
from scripts.build_report import report_tables
from scripts.audit_report_prose import audit as audit_report_prose


EXPECTED_CHAPTERS = (
    "CHƯƠNG 1. GIỚI THIỆU",
    "CHƯƠNG 2. CƠ SỞ VÀ PHƯƠNG PHÁP",
    "CHƯƠNG 3. DỮ LIỆU VÀ QUY CHẾ",
    "CHƯƠNG 4. THIẾT KẾ HỆ THỐNG",
    "CHƯƠNG 5. MÔ HÌNH ML",
    "CHƯƠNG 6. TỐI ƯU ILP",
    "CHƯƠNG 7. MÔ PHỎNG MONTE CARLO",
    "CHƯƠNG 8. GIAO DIỆN HỆ THỐNG",
    "CHƯƠNG 9. KIỂM THỬ VÀ HƯỚNG DẪN CÀI ĐẶT, CHẠY",
    "CHƯƠNG 10. KẾT LUẬN, HẠN CHẾ VÀ HƯỚNG PHÁT TRIỂN",
)
CAPTION = re.compile(r"^Bảng ([A-E]|\d+)\.(\d+)\. (.+)$")


def _contents(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def _paragraph_text(paragraph) -> str:
    return "".join(paragraph._p.xpath(".//w:t/text()"))


def _check_fonts(document: Document) -> tuple[int, int]:
    checked_runs = 0
    table_runs = 0
    expected_styles = {
        "Normal": 12,
        "Title": 12,
        "Subtitle": 12,
        "Caption": 12,
        "TOC 1": 12,
        "TOC 2": 12,
        "Heading 1": 14,
        "Heading 2": 13,
        "Heading 3": 12,
    }
    for name, size in expected_styles.items():
        if name not in document.styles:
            raise ValueError(f"Required paragraph style is missing: {name}")
        style = document.styles[name]
        if style.font.name != "Times New Roman" or style.font.size.pt != size:
            raise ValueError(f"Style {name} must be Times New Roman {size} pt")
        rpr = style.element.rPr
        rfonts = rpr.rFonts if rpr is not None else None
        if rfonts is None or any(
            rfonts.get(qn(f"w:{key}")) != "Times New Roman"
            for key in ("ascii", "hAnsi", "eastAsia", "cs")
        ):
            raise ValueError(f"Style {name} lacks explicit Times New Roman mappings")
    for style in document.styles:
        if style.type not in {WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER}:
            continue
        if style.font.name != "Times New Roman":
            raise ValueError(f"Style {style.name} must use Times New Roman")
        rpr = style.element.rPr
        rfonts = rpr.rFonts if rpr is not None else None
        if rfonts is None or any(
            rfonts.get(qn(f"w:{key}")) != "Times New Roman"
            for key in ("ascii", "hAnsi", "eastAsia", "cs")
        ):
            raise ValueError(f"Style {style.name} lacks explicit font mappings")
    for paragraph in document.paragraphs:
        expected_size = {
            "Heading 1": 14,
            "Heading 2": 13,
            "Heading 3": 12,
        }.get(paragraph.style.name, 12)
        for run in paragraph.runs:
            if not run.text and not run._element.xpath("./w:rPr/w:rFonts"):
                continue
            checked_runs += 1
            if run.font.name != "Times New Roman":
                raise ValueError(f"Non-Times New Roman paragraph run: {run.text[:50]!r}")
            if run.font.size is None or run.font.size.pt != expected_size:
                raise ValueError(
                    f"{paragraph.style.name} run must use {expected_size} pt: {run.text[:50]!r}"
                )
            rfonts = run._element.rPr.rFonts if run._element.rPr is not None else None
            if rfonts is None or any(
                rfonts.get(qn(f"w:{key}")) != "Times New Roman"
                for key in ("ascii", "hAnsi", "eastAsia", "cs")
            ):
                raise ValueError(f"Missing explicit Times New Roman font mappings: {run.text[:50]!r}")
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        table_runs += 1
                        if run.font.name != "Times New Roman" or run.font.size.pt != 11:
                            raise ValueError("Table runs must use Times New Roman 11 pt")
                        rfonts = run._element.rPr.rFonts if run._element.rPr is not None else None
                        if rfonts is None or any(
                            rfonts.get(qn(f"w:{key}")) != "Times New Roman"
                            for key in ("ascii", "hAnsi", "eastAsia", "cs")
                        ):
                            raise ValueError("Table run lacks explicit East Asian font mapping")
    for section in document.sections:
        for paragraph in section.footer.paragraphs:
            for run in paragraph.runs:
                if run.font.name != "Times New Roman" or run.font.size.pt != 12:
                    raise ValueError("Footer runs must use Times New Roman 12 pt")
    return checked_runs, table_runs


def check_report(report_path: Path = REPORT_PATH) -> list[str]:
    if not report_path.is_file():
        raise FileNotFoundError(f"Final Word report not found: {report_path}")
    document = Document(report_path)
    headings1 = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.style.name == "Heading 1"]
    missing = [heading for heading in EXPECTED_CHAPTERS if heading not in headings1]
    if missing:
        raise ValueError(f"Missing final report chapters: {missing}")
    for required in ("PHỤ LỤC A.", "PHỤ LỤC B.", "PHỤ LỤC C.", "PHỤ LỤC D.", "PHỤ LỤC E."):
        if not any(heading.startswith(required) for heading in headings1):
            raise ValueError(f"Missing required appendix heading: {required}")
    headings2 = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.style.name == "Heading 2"]
    if not headings2:
        raise ValueError("Report must use Heading 2 styles for sections")
    required_chapter7_sections = {
        "7.1 Thiết kế mô phỏng",
        "7.2 Vì sao kết quả thay đổi theo λ",
        "7.3 Vì sao ILP không luôn tốt hơn B1/B2",
        "7.4 Những yếu tố chưa được mô phỏng",
        "7.5 Kết quả theo hồ sơ (V2-001, V2-003)",
        "7.6 Kiểm tra tái tạo và độ tin cậy",
    }
    if not required_chapter7_sections.issubset(set(headings2)):
        raise ValueError(f"Missing Chapter 7 sections: {required_chapter7_sections - set(headings2)}")

    caption_titles: list[str] = []
    table_caption_count = 0
    figure_caption_count = 0
    for paragraph in document.paragraphs:
        text = _paragraph_text(paragraph).strip()
        instructions = [
            field.get(qn("w:instr"), "")
            for field in paragraph._p.xpath(".//w:fldSimple")
        ]
        match = CAPTION.match(text)
        if match and any(value.startswith("SEQ Table") for value in instructions):
            caption_titles.append(match.group(3))
            table_caption_count += 1
        elif text.startswith("Hình ") and any(
            value.startswith("SEQ Figure") for value in instructions
        ):
            figure_caption_count += 1
    if table_caption_count != len(document.tables):
        raise ValueError(f"Table captions ({table_caption_count}) do not match tables ({len(document.tables)})")
    if figure_caption_count != len(document.inline_shapes):
        raise ValueError(f"Figure captions ({figure_caption_count}) do not match images ({len(document.inline_shapes)})")
    chapter7_table_captions = [
        title for title in caption_titles
        if title.startswith((
            "Tóm tắt Monte Carlo", "Tải tín chỉ, units(L)", "Tín chỉ trung bình mỗi kỳ",
            "KTC ghép cặp của V2-001/V2-003", "Nhãn Pareto V2-001/V2-003",
        ))
    ]
    if len(chapter7_table_captions) != 5:
        raise ValueError(f"Chapter 7 must contain exactly five specified tables, found {len(chapter7_table_captions)}")
    non_caption_text = [
        _paragraph_text(paragraph).strip()
        for paragraph in document.paragraphs
        if not any(
            field.get(qn("w:instr"), "").startswith(("SEQ Table", "SEQ Figure"))
            for field in paragraph._p.xpath(".//w:fldSimple")
        )
    ]
    for paragraph in document.paragraphs:
        caption = CAPTION.match(_paragraph_text(paragraph).strip())
        if not caption:
            continue
        instructions = [
            field.get(qn("w:instr"), "")
            for field in paragraph._p.xpath(".//w:fldSimple")
        ]
        if not any(value.startswith(("SEQ Table", "SEQ Figure")) for value in instructions):
            continue
        kind = "Bảng" if any(value.startswith("SEQ Table") for value in instructions) else "Hình"
        reference = f"{kind} {caption.group(1)}.{caption.group(2)}"
        if not any(reference in text for text in non_caption_text):
            raise ValueError(f"Caption is not referenced in report text: {reference}")
    missing_images = [name for name, _, _ in REQUIRED_IMAGES if not (MEDIA / name).is_file()]
    if missing_images:
        raise FileNotFoundError(f"Required demo screenshots missing: {missing_images}")
    expected_figures = len(REQUIRED_IMAGES) + len(REPORT_FIGURES) + 1
    if len(document.inline_shapes) != expected_figures:
        raise ValueError(f"Expected {expected_figures} report figures, found {len(document.inline_shapes)}")

    source = {title: (headers, rows) for title, headers, rows in report_tables()}
    tables_by_caption: dict[str, list[list[str]]] = {}
    table_index = 0
    for paragraph in document.paragraphs:
        match = CAPTION.match(_paragraph_text(paragraph).strip())
        instructions = [
            field.get(qn("w:instr"), "")
            for field in paragraph._p.xpath(".//w:fldSimple")
        ]
        if match and any(value.startswith("SEQ Table") for value in instructions):
            title = match.group(3)
            if table_index >= len(document.tables):
                raise ValueError(f"Missing Word table for caption {title}")
            if title in tables_by_caption:
                raise ValueError(f"Duplicate table caption: {title}")
            tables_by_caption[title] = _contents(document.tables[table_index])
            table_index += 1
    checked = []
    for title, (headers, rows) in source.items():
        actual = tables_by_caption.get(title)
        expected = [headers, *rows]
        if actual != expected:
            raise ValueError(f"Source table differs from generated artifact: {title}")
        checked.append(title)
    if len(checked) != len(source):
        raise ValueError("Not all source-backed report tables were verified")
    if "Ma trận góp ý, thay đổi, vị trí và bằng chứng" not in tables_by_caption:
        raise ValueError("Appendix A feedback matrix is missing")
    matrix_headers, matrix_rows = _parse_table(_read_text("final_requirements_matrix.md"))
    if matrix_headers != ["Nhóm góp ý", "Thay đổi đã làm", "Vị trí (chương/tệp)", "Bằng chứng"] or len(matrix_rows) != 4:
        raise ValueError("Appendix A must contain four feedback groups and four requested columns")
    if tables_by_caption["Ma trận góp ý, thay đổi, vị trí và bằng chứng"] != [matrix_headers, *matrix_rows]:
        raise ValueError("Appendix A does not match final_requirements_matrix.md")

    fields = [field.get(qn("w:instr"), "") for field in document._element.xpath(".//w:fldSimple")]
    if not any(instruction.startswith('TOC \\o "1-2"') for instruction in fields):
        raise ValueError("Missing automatic Heading 1–2 TOC")
    if not any(instruction.startswith('TOC \\h \\z \\c "Table"') for instruction in fields):
        raise ValueError("Missing generated list of tables")
    if not any(instruction.startswith('TOC \\h \\z \\c "Figure"') for instruction in fields):
        raise ValueError("Missing generated list of figures")
    if sum(instruction.startswith("SEQ Table") for instruction in fields) != table_caption_count:
        raise ValueError("Every table caption must use a SEQ field")
    if sum(instruction.startswith("SEQ Figure") for instruction in fields) != figure_caption_count:
        raise ValueError("Every figure caption must use a SEQ field")
    update_fields = document.settings.element.find(qn("w:updateFields"))
    if update_fields is None or update_fields.get(qn("w:val")) not in {"true", "1"}:
        raise ValueError("Word updateFields must be enabled")
    footer_fields = [
        field.get(qn("w:instr"), "")
        for section in document.sections
        for field in section.footer._element.xpath(".//w:fldSimple")
    ]
    if "PAGE" not in footer_fields:
        raise ValueError("Footer page-number field is missing")

    for section in document.sections:
        if round(section.page_width.cm, 1) != 21.0 or round(section.page_height.cm, 1) != 29.7:
            raise ValueError("Report pages must be A4")
        if round(section.left_margin.cm, 1) != 3.0 or any(
            round(value.cm, 1) != 2.0
            for value in (section.top_margin, section.bottom_margin, section.right_margin)
        ):
            raise ValueError("Report margins must be 3 cm left and 2 cm elsewhere")
    _check_fonts(document)

    reference_numbers: set[int] = set()
    bibliography_numbers: set[int] = set()
    in_bibliography = False
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if paragraph.style.name == "Heading 1" and text.upper() == "TÀI LIỆU THAM KHẢO":
            in_bibliography = True
            continue
        if in_bibliography:
            match = re.match(r"\[(\d+)\]\s", text)
            if match:
                bibliography_numbers.add(int(match.group(1)))
        else:
            for citation in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", text):
                reference_numbers.update(int(value.strip()) for value in citation.split(","))
    if not reference_numbers or reference_numbers != bibliography_numbers:
        raise ValueError(
            f"Citation/bibliography mismatch: citations={sorted(reference_numbers)}, "
            f"bibliography={sorted(bibliography_numbers)}"
        )

    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    if "Kết quả là phân tích kịch bản theo giả định; không phải bằng chứng hiệu quả với sinh viên NTU." not in text:
        raise ValueError("Required Monte Carlo limitation statement is missing")
    if "Trạng thái `optimal` chỉ có nghĩa nghiệm tối ưu theo hàm mục tiêu và các ràng buộc đã mô hình hóa" not in text:
        raise ValueError("Required optimal-status limitation is missing")
    if re.search(r"Phần 4-fix|_repro_tmp|stage2_report\.docx|BaoCao_Nhom1_HTTQD_65\.TTQL-2\.docx", text, re.I):
        raise ValueError("Obsolete/internal terms remain in the final report")

    prose_numbers = audit_report_prose()
    unmatched = [row for row in prose_numbers if row["source_match"] == "KHÔNG KHỚP/CHƯA XÁC ĐỊNH"]
    if unmatched:
        raise ValueError(f"{len(unmatched)} report prose numbers have no generated/config source match")
    checked.extend(("Appendix A feedback matrix", "front-matter fields", "report formatting", "sourced prose"))
    return checked


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    checked = check_report()
    document = Document(REPORT_PATH)
    headings = [paragraph.text for paragraph in document.paragraphs if paragraph.style.name == "Heading 1"]
    print("REPORT_CONSISTENCY: PASS")
    print(f"SOURCE_TABLES={len([title for title, _, _ in report_tables()])}")
    print(f"TOTAL_TABLES={len(document.tables)}")
    print(f"FIGURES={len(document.inline_shapes)}")
    print(f"HEADING_1={len(headings)}")
    print("HEADING_LIST=" + " | ".join(headings))
    print(f"REPORT_CHECKS={len(checked)}")


if __name__ == "__main__":
    main()
