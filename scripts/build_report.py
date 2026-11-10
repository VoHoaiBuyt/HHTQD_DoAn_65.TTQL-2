from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
REPORT_PATH = ROOT / "reports" / "stage2_report.docx"


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
    return path.read_text(encoding="utf-8-sig")


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
    plan_rows = [row for row in plans if row["student_id"] == "V2-001"]
    plan_rows.sort(key=lambda row: row["plan_type"])
    if len(plan_rows) != 3:
        raise ValueError("Expected three registered plan variants for scenario V2-001")

    mc = _read_csv("mc_results.csv")
    mc_rows = [
        row for row in mc
        if row["student_id"] == "V2-001" and float(row["lambda"]) == 0.1
    ]
    if not mc_rows:
        raise ValueError("No Monte Carlo result exists for V2-001 at lambda=0.1")
    mc_rows.sort(key=lambda row: row["policy"])

    pairwise = _read_csv("mc_pairwise.csv")
    pairwise_rows = [
        row for row in pairwise
        if row["student_id"] == "V2-001" and float(row["lambda"]) == 0.1
    ]
    pareto = _read_csv("mc_pareto.csv")
    pareto_rows = [
        row for row in pareto
        if row["student_id"] == "V2-001" and float(row["lambda"]) == 0.1
    ]
    if not pairwise_rows or not pareto_rows:
        raise ValueError("Monte Carlo paired-comparison and Pareto rows are required")
    pairwise_rows.sort(key=lambda row: row["comparison"])
    pareto_rows.sort(key=lambda row: (row["policy_a"], row["policy_b"]))

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
            "ILP — ba phương án scenario V2-001",
            ["Loại", "Trạng thái", "Tín chỉ chọn", "Môn chọn (mã)", "Môn trượt kỳ vọng", "Graduation kỳ ước tính"],
            selected(
                plan_rows,
                [
                    "plan_type", "status", "selected_credits", "selected_course_ids",
                    "expected_failed_courses", "estimated_graduation_semester",
                ],
            ),
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
            "Monte Carlo — scenario V2-001, λ=0.1",
            ["Chính sách", "Số lượt", "P tốt nghiệp đúng hạn", "KTC 95%", "Kỳ tốt nghiệp TB", "Môn trượt kỳ vọng", "Best-effort quyết định"],
            [
                [
                    row["policy"],
                    row["n_runs"],
                    _fmt(float(row["p_graduated_on_time"])),
                    f"[{_fmt(float(row['ci_p_graduated_on_time_lower']))}, {_fmt(float(row['ci_p_graduated_on_time_upper']))}]",
                    _fmt(float(row["mean_graduation_semester"])),
                    _fmt(float(row["expected_failed_courses"])),
                    row["best_effort_decisions"],
                ]
                for row in mc_rows
            ],
        ),
        (
            "Monte Carlo — so sánh cặp V2-001, λ=0.1",
            ["So sánh", "Lượt", "Chênh lệch P đúng hạn", "KTC 95% chênh lệch", "Chênh lệch môn trượt", "KTC 95% chênh lệch môn trượt"],
            [
                [
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
            "Monte Carlo — Pareto V2-001, λ=0.1",
            ["Chính sách A", "Chính sách B", "Kết luận", "Diễn giải nguồn"],
            selected(pareto_rows, ["policy_a", "policy_b", "dominance", "interpretation"]),
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
    document.add_heading(title, level=level)


def _add_table_by_title(document: Document, tables: list[tuple[str, list[str], list[list[str]]]], title: str) -> None:
    match = next(item for item in tables if item[0] == title)
    _add_table(document, *match)


def build_report(output_path: Path = REPORT_PATH) -> Path:
    tables = report_tables()
    curriculum = _read_json("curriculum_validation.json")
    test_metrics = _read_json("test_evaluation.json")
    metrics = _read_json("metrics.json")
    bootstrap = _read_json("ml_validation_bootstrap_ci.json")
    mc = _read_csv("mc_results.csv")
    plans = _read_csv("plans_by_student.csv")
    sensitivity = _read_csv("ilp_sensitivity.csv")
    regulation_text = _read_text("regulation_assumptions.md")
    optimization_text = _read_text("optimization_spec.md")
    screens_path = ROOT / "docs" / "screens_to_capture.md"
    pytest_path = GENERATED / "pytest_summary.txt"

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9)

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

    _add_section(document, "TÓM TẮT ĐIỀU HÀNH")
    document.add_paragraph(
        "Đã triển khai pipeline ML tại T1 trên REAL (UCI-697), rule engine/kiểm tra CTĐT, "
        "bộ tối ưu ILP, mô phỏng Monte Carlo và giao diện Streamlit. Kiểm tra CTĐT đọc "
        "n_checks từ JSON; pytest bao phủ core, optimizer, dữ liệu, mô phỏng và smoke test giao diện. "
        "Báo cáo này lấy bảng và chỉ số từ artifact sinh tự động, không bổ sung kết quả thủ công."
    )
    document.add_paragraph(
        "Hạn chế trọng yếu: CTĐT được nhóm cung cấp nhưng mã HP/prerequisite và một số diễn giải "
        "quy chế vẫn chưa xác nhận; UCI-697 là dữ liệu ngoài NTU; tải, pass/fail tương lai và "
        "Monte Carlo là giả định; ảnh chụp UI chưa được đính kèm. Do đó đây là prototype hỗ trợ "
        "thảo luận, không phải dự báo đã kiểm định cho sinh viên NTU hay khuyến nghị đăng ký an toàn."
    )

    _add_section(document, "DỮ LIỆU OFFICIAL (NTU)")
    document.add_paragraph(
        f"Nhãn: {curriculum['source_label']}; tài liệu nhóm cung cấp: "
        f"{curriculum['source_document']}, mục {curriculum['source_section']}. "
        "Ngày truy cập/phiên bản tài liệu không có trong artifact: UNKNOWN, source=NOT_FOUND. "
        "Không tự bổ sung học phần, tín chỉ hoặc điều kiện ngoài nguồn."
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

    _add_section(document, "QUY CHẾ QĐ 753/2021 VÀ CÁCH MÔ HÌNH HÓA")
    document.add_paragraph(
        "Nguồn quy chế được ghi là QĐ 753/QĐ-ĐHNT ngày 13/08/2021, áp dụng khóa 60 trở đi. "
        "Các giá trị, điều khoản, trạng thái CONFIRMED/UNCONFIRMED/UNKNOWN và ghi chú mô hình "
        "được trích trực tiếp từ regulation_assumptions.md; nội dung này không thay thế việc "
        "đối chiếu văn bản gốc."
    )
    _add_table_by_title(document, tables, "Quy chế — bảng giả định và trạng thái")

    _add_section(document, "MÔ HÌNH ML — MỐC T1")
    document.add_paragraph(
        "Mốc hợp lệ: sau HK1, trước đăng ký HK2. Các mô hình được so sánh trên validation; "
        "bảng ba lớp và nhị phân giữ riêng. Holdout được đánh giá một lần theo artifact hiện có; "
        f"evaluation_count={test_metrics['evaluation_count']}. Test không dùng để chọn mô hình."
    )
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
        "tương lai đã biết. SHAP giải thích mô hình, không hàm ý quan hệ nhân quả."
    )
    _add_table_by_title(document, tables, "ML — SHAP toàn cục, năm đặc trưng đầu")
    document.add_paragraph(
        "Chi tiết phân tích Enrolled, calibration, test và SHAP: "
        "reports/generated/enrolled_analysis.md, metrics.json, test_evaluation.json, "
        "shap_global.csv và shap_local_examples.json."
    )

    _add_section(document, "RULE ENGINE VÀ KẾT QUẢ KIỂM THỬ")
    document.add_paragraph(
        "Kiểm tra CTĐT và số đếm được tách thành bảng riêng. Pytest bao gồm kiểm tra prerequisite/"
        "corequisite, ràng buộc tín chỉ, học lại, các trường hợp infeasible/best_effort, dữ liệu, "
        "mô phỏng và smoke test giao diện. Lỗi môn song hành được kiểm tra bằng các ca regression "
        "trong tests/test_core_rules.py; kết quả chạy toàn bộ được lưu nguyên văn tại "
        f"{pytest_path.relative_to(ROOT)}."
    )

    _add_section(document, "ILP — HÀM MỤC TIÊU VÀ CÁC PHƯƠNG ÁN")
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
    _add_table_by_title(document, tables, "ILP — ba phương án scenario V2-001")
    _add_table_by_title(document, tables, "ILP — độ nhạy scenario V2-002")
    document.add_paragraph(
        "Các dòng best_effort luôn phải giữ cảnh báo rủi ro và khuyến nghị gặp cố vấn học tập; "
        "không được gọi là an toàn. Bảng kế hoạch chỉ trình bày dữ liệu từ plans_by_student.csv; "
        "chi tiết warnings/status đầy đủ vẫn nằm trong artifact nguồn."
    )
    document.add_paragraph(
        f"Artifact kế hoạch có {len(plans)} dòng; độ nhạy có {len(sensitivity)} dòng. "
        "Phạm vi độ nhạy trong báo cáo là lát cắt được chỉ rõ trong tiêu đề bảng, không đại diện "
        "cho toàn bộ lưới."
    )

    _add_section(document, "MONTE CARLO — MÔ PHỎNG, KHÔNG PHẢI BẰNG CHỨNG THỰC TẾ")
    document.add_paragraph(
        f"mc_results.csv có {len(mc)} dòng. Bảng dưới đây là lát cắt scenario V2-001, λ=0.1; "
        "KTC lấy từ kết quả mô phỏng. So sánh cặp dùng bootstrap paired và Pareto theo artifact; "
        "không suy rộng từ một kịch bản sang sinh viên NTU. Các giả định gồm pass/fail độc lập, "
        "điểm đại diện và cấu hình tải; W3/W4 không được đánh giá trong mô phỏng do thiếu điểm. "
        "Không có mc_grad_hist.csv trong artifact hiện tại nên không thể dựng phân phối kỳ tốt nghiệp; "
        "không nội suy hoặc suy diễn phân phối này."
    )
    _add_table_by_title(document, tables, "Monte Carlo — scenario V2-001, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — so sánh cặp V2-001, λ=0.1")
    _add_table_by_title(document, tables, "Monte Carlo — Pareto V2-001, λ=0.1")

    _add_section(document, "GIAO DIỆN STREAMLIT")
    document.add_paragraph(
        "Ứng dụng: app/main.py. Hồ sơ là SCENARIO; ML chỉ hiển thị trong phạm vi T1 hợp lệ; "
        "kết quả mô phỏng được gắn nhãn giả định. Không có ảnh chụp được đính kèm trong artifact "
        "hiện tại. Chụp theo docs/screens_to_capture.md và chỉ dùng hồ sơ SCENARIO."
    )
    for caption in (
        "Ảnh 1 — Hồ sơ & tiến độ: [CHƯA CHỤP — bổ sung ảnh tại đây]",
        "Ảnh 2 — Nguy cơ & cảnh báo: [CHƯA CHỤP — bổ sung ảnh tại đây]",
        "Ảnh 3 — Phương án đăng ký và trang mô phỏng: [CHƯA CHỤP — bổ sung ảnh tại đây]",
    ):
        paragraph = document.add_paragraph(caption)
        paragraph.paragraph_format.space_after = Pt(12)

    _add_section(document, "CÀI ĐẶT VÀ CHẠY")
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

    _add_section(document, "HẠN CHẾ VÀ PHẦN CHƯA HOÀN THÀNH")
    for limitation in (
        "Chưa ghi nhận ngày truy cập/phiên bản PDF CTĐT trong artifact; mã HP và tính đầy đủ ngữ nghĩa tiên quyết còn UNCONFIRMED.",
        "Chưa xác nhận một số quy tắc suy từ CTĐT, bao gồm nhóm tự chọn, mở môn theo chẵn/lẻ và ngữ nghĩa môn song hành.",
        "REAL (UCI-697) khác miền NTU; không có đánh giá hiệu quả dự báo trên sinh viên NTU.",
        "Kết quả dự báo xác suất đạt môn, tải, điểm đại diện, tính độc lập môn học và Monte Carlo có giả định; không phải kết quả thực tế.",
        "Không mô phỏng học kỳ hè và một số đầu ra/điểm cần cho W3/W4; kết quả tốt nghiệp phụ thuộc điều kiện mô phỏng.",
        "Chưa chụp ảnh giao diện; chưa kiểm chứng cài đặt từ một máy/môi trường sạch mới.",
        "Phân phối kỳ tốt nghiệp chỉ có thể báo cáo khi artifact tương ứng chứa dữ liệu; không nội suy khi thiếu dữ liệu.",
    ):
        document.add_paragraph(limitation, style="List Bullet")

    _add_section(document, "ĐỐI CHIẾU YÊU CẦU CỦA GIẢNG VIÊN (MỤC 1–6)")
    document.add_paragraph(
        "Rubric gốc riêng của giảng viên không có trong workspace. Bảng dưới đây đối chiếu sáu "
        "phần dự án/mốc triển khai hiện có; cần xác nhận lại nếu thứ tự mục 1–6 của cô khác."
    )
    crosswalk = [
        ["1", "Dữ liệu CTĐT và nguồn", "Làm một phần", "data/official/; config/program_official.yaml; curriculum_validation.json — mã HP/prerequisite còn xác minh."],
        ["2", "Quy chế và rule engine", "Làm một phần", "config/credit_rules_official.yaml; regulation_assumptions.md; tests/test_official_rules.py — còn UNCONFIRMED/UNKNOWN."],
        ["3", "ML cảnh báo tại T1", "Làm một phần", "model_comparison.csv; test_evaluation.json; ml_validation_bootstrap_ci.json — chỉ UCI-697, chưa kiểm định NTU."],
        ["4", "ILP và phương án đăng ký", "Làm một phần", "plans_by_student.csv; ilp_sensitivity.csv; optimization_spec.md — các tham số/nhánh quy chế còn giả định."],
        ["5", "Monte Carlo và giao diện", "Làm một phần", "mc_results.csv; mc_pairwise.csv; mc_pareto.csv; app/main.py; docs/screens_to_capture.md — chưa có ảnh, mô phỏng không phải bằng chứng."],
        ["6", "Kiểm thử, báo cáo, đóng gói", "Làm một phần", "pytest_summary.txt; stage2_report.docx; HANDOFF.md — cần xác nhận cài đặt sạch và rubric gốc."],
    ]
    _add_table(
        document,
        "Đối chiếu sáu phần dự án — trạng thái và bằng chứng",
        ["Mục", "Yêu cầu", "Trạng thái", "Bằng chứng"],
        crosswalk,
    )

    _add_section(document, "CÂU HỎI XIN CÔ XÁC NHẬN (TỐI ĐA 6)")
    questions = [
        "Cảnh báo dùng ba lớp Dropout/Enrolled/Graduate hay nhị phân Dropout/non-Dropout? Mặc định: ba lớp; chênh lệch hiện nằm trong sai số và Enrolled được giữ riêng.",
        "P(Dropout) có được dùng như khuyến nghị mềm, không áp trần đăng ký? Mặc định: chỉ cảnh báo/khuyến nghị gặp cố vấn, không ràng buộc quyền đăng ký.",
        "Ngân sách kịch bản đã đúng chưa? Mặc định: nhóm yếu/kém có thể xét 12; sinh viên thường dùng {15, 18, 21}; không đổi giới hạn chính thức.",
        "Đầu ra buộc thôi học trong mô phỏng có giới hạn W1/W2 khi không có điểm HK để tính W3/W4? Mặc định: chỉ W1/W2 trong mô phỏng; rule engine vẫn giữ đầy đủ quy tắc có dữ liệu.",
        "Cô duyệt tiêu chí Pareto hiện tại và KTC 95% paired bootstrap? Mặc định: chỉ kết luận trội khi tiêu chí và KTC cùng ủng hộ; còn chồng lấp thì chưa phân biệt.",
        "Có cần bổ sung OULAD hoặc mô hình hóa học kỳ hè? Mặc định: chưa thêm nguồn/giả định mới khi chưa được duyệt và chưa có dữ liệu chính thức phù hợp.",
    ]
    for question in questions:
        document.add_paragraph(question, style="List Number")

    _add_section(document, "PHỤ LỤC — DANH SÁCH FILE GIAO")
    deliverables = [
        "Mã nguồn: core/, app/, scripts/, tests/.",
        "Notebook hoạt động: notebooks/01_eda_uci697.ipynb. Notebook Stage 1 cũ: archive/02_risk_to_plan_exploration.ipynb và archive/03_ilp_formulation_check.ipynb.",
        "Dữ liệu và cấu hình: data/official/, data/scenarios/, data/processed/, config/; dữ liệu scenario mang nhãn SCENARIO.",
        "ML: models/early_warning.joblib; reports/generated/model_comparison.csv, test_evaluation.json, ml_validation_bootstrap_ci.json, shap_global.csv.",
        "Rule/ILP: reports/generated/curriculum_validation.json, regulation_assumptions.md, plans_by_student.csv, ilp_sensitivity.csv.",
        "Monte Carlo: reports/generated/mc_results.csv, mc_pairwise.csv, mc_pareto.csv và các artifact liên quan.",
        "Tài liệu chạy: README.md, HANDOFF.md, docs/screens_to_capture.md.",
        "Báo cáo: reports/stage2_report.docx; kết quả test: reports/generated/pytest_summary.txt.",
    ]
    for item in deliverables:
        document.add_paragraph(item, style="List Bullet")
    document.add_paragraph(
        "Tệp nguồn chính: " + ", ".join(
            name for name in (
                "curriculum_validation.json", "metrics.json", "model_comparison.csv",
                "test_evaluation.json", "ml_validation_bootstrap_ci.json", "mc_results.csv",
                "mc_pairwise.csv", "mc_pareto.csv", "plans_by_student.csv",
                "ilp_sensitivity.csv", "regulation_assumptions.md",
            )
        )
    )
    if not screens_path.is_file():
        raise FileNotFoundError(f"Screenshot instructions not found: {screens_path}")
    if not pytest_path.is_file():
        raise FileNotFoundError(f"Raw pytest output not found: {pytest_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the stage 2 Word report from generated artifacts.")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    output = build_report(args.output)
    print(f"REPORT_WRITTEN: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
