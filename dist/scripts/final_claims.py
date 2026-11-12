from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from app.risk_labels import PLAN_DISPLAY_LABELS, RISK_THRESHOLDS, risk_level as _risk_level

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
HIGH_RISK_ADVICE = (
    "khuyến nghị trao đổi với cố vấn học tập; `optimal` chỉ có nghĩa tối ưu theo hàm mục tiêu, "
    "không có nghĩa an toàn"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def load_validation_claims() -> dict[str, Any]:
    metrics = _read_json(GENERATED / "metrics.json")["ml"]
    comparison = _read_csv(GENERATED / "model_comparison.csv")
    models = {
        row["task"]: row
        for row in comparison
        if row["model"] == "XGBoost"
    }
    if "three_class" not in models or "binary_dropout" not in models:
        raise ValueError("XGBoost comparison rows for both validation tasks are required")
    three_metrics = metrics["validation"]["multiclass"]["XGBoost"]
    binary_metrics = metrics["validation"]["binary"]["XGBoost"]
    bootstrap = _read_json(GENERATED / "ml_validation_bootstrap_ci.json")
    if bootstrap.get("source_label", "").find("validation-only") < 0:
        raise ValueError("The bootstrap artifact must be validation-only")
    return {
        "models": models,
        "three_metrics": three_metrics,
        "binary_metrics": binary_metrics,
        "bootstrap": bootstrap,
        "metrics": metrics,
    }


def risk_level(row: dict[str, str]) -> str:
    return _risk_level(row)


def plan_signatures(plans: list[dict[str, str]]) -> tuple[int, int, list[str]]:
    fields = (
        "plan_type",
        "status",
        "selected_course_ids",
        "selected_credits",
        "expected_credits_passed",
        "expected_failed_courses",
        "p_warning_W1",
        "p_warning_W2",
    )
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in plans:
        grouped.setdefault(row["student_id"], []).append(row)
    if len(grouped) != 9 or any(len(rows) != 3 for rows in grouped.values()):
        raise ValueError("Expected three plan rows for each of the nine scenario profiles")
    signatures = {
        student_id: tuple(
            tuple(row[field] for field in fields)
            for row in sorted(rows, key=lambda item: item["plan_type"])
        )
        for student_id, rows in grouped.items()
    }
    counts = Counter(signatures.values())
    identical_profile_count = sum(count for count in counts.values() if count > 1)
    repeated_profiles = sorted(
        student_id
        for student_id, signature in signatures.items()
        if counts[signature] > 1
    )
    return identical_profile_count, len(counts), repeated_profiles


def _fmt(value: float, decimals: int = 4) -> str:
    return f"{value:.{decimals}f}"


def _find_matrix_row(text: str, prefix: str) -> tuple[int, str]:
    for index, line in enumerate(text.splitlines()):
        if line.startswith(f"| {prefix}"):
            return index, line
    raise ValueError(f"Requirements matrix row not found: {prefix}")


def _csv_claim(
    location: str, source_file: str, selector: dict[str, str], field: str, raw: str
) -> dict[str, str]:
    key = ";".join(f"{name}={value}" for name, value in selector.items())
    key += f";field={field}"
    try:
        number = _fmt(float(raw))
    except ValueError:
        number = raw
    return {
        "location": location,
        "number": number,
        "source_file": source_file,
        "key": key,
        "source_value": raw,
    }


def _json_claim(location: str, path: str, key: str, value: Any) -> dict[str, str]:
    raw = str(value)
    try:
        number = _fmt(float(value))
    except (TypeError, ValueError):
        number = raw
    return {
        "location": location,
        "number": number,
        "source_file": path,
        "key": key,
        "source_value": raw,
    }


def build_risk_rows(plans: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for plan in sorted(plans, key=lambda row: (row["student_id"], row["plan_type"])):
        level = risk_level(plan)
        rows.append(
            {
                "student_id": plan["student_id"],
                "plan_type": plan["plan_type"],
                "display_label": PLAN_DISPLAY_LABELS.get(
                    plan["plan_type"], plan["plan_type"]
                ),
                "selected_credits": plan["selected_credits"],
                "expected_credits_passed": plan["expected_credits_passed"],
                "expected_failed_courses": plan["expected_failed_courses"],
                "p_warning_W1": plan["p_warning_W1"],
                "p_warning_W2": plan["p_warning_W2"],
                "risk_level": level,
                "warning": HIGH_RISK_ADVICE if level == "CAO" else "",
            }
        )
    return rows


def build_prose_claim_rows() -> list[dict[str, str]]:
    bundle = load_validation_claims()
    plans = _read_csv(GENERATED / "plans_by_student.csv")
    model_rows = bundle["models"]
    three, binary = model_rows["three_class"], model_rows["binary_dropout"]
    claims: list[dict[str, str]] = []

    for location, task, row in (
        ("final_questions_for_co.md", "three_class", three),
        ("final_questions_for_co.md", "binary_dropout", binary),
    ):
        selector = {"task": task, "model": "XGBoost"}
        claims.append(_csv_claim(location, "reports/generated/model_comparison.csv", selector, "dropout_pr_auc", row["dropout_pr_auc"]))
        claims.append(_csv_claim(location, "reports/generated/model_comparison.csv", selector, "dropout_brier", row["dropout_brier"]))

    for task, metric_name in (
        ("multiclass", "three_metrics"),
        ("binary", "binary_metrics"),
    ):
        metric = bundle[metric_name]["dropout_recall_at_precision_0.50"]
        claims.append(
            _json_claim(
                "final_questions_for_co.md",
                "reports/generated/metrics.json",
                f"ml.validation.{task}.XGBoost.dropout_recall_at_precision_0.50.recall",
                metric["recall"],
            )
        )

    boot = bundle["bootstrap"]["metrics"]
    for metric_name in ("dropout_pr_auc", "dropout_brier"):
        for bound in ("estimate", "ci95_lower", "ci95_upper"):
            claims.append(
                _json_claim(
                    "final_questions_for_co.md",
                    "reports/generated/ml_validation_bootstrap_ci.json",
                    f"metrics.{metric_name}.{bound}",
                    boot[metric_name][bound],
                )
            )

    grouped_source = "reports/generated/plans_by_student.csv"
    for plan in plans:
        selector = {"student_id": plan["student_id"], "plan_type": plan["plan_type"]}
        for field in (
            "selected_credits",
            "expected_credits_passed",
            "expected_failed_courses",
            "p_warning_W1",
            "p_warning_W2",
        ):
            claims.append(
                _csv_claim                ("BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx / plan table", grouped_source, selector, field, plan[field])
            )

    identical_count, distinct_count, repeated = plan_signatures(plans)
    profile_count = len({row["student_id"] for row in plans})
    for location in ("BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx", "outbox/final_cover_message.md"):
        claims.append(
            _json_claim(
                location,
                grouped_source,
                "derived:identical_profile_count",
                identical_count,
            )
        )
        claims.append(
            _json_claim(
                location,
                grouped_source,
                "derived:distinct_plan_signatures",
                distinct_count,
            )
        )
        claims.append(
            {
                "location": location,
                "number": str(profile_count),
                "source_file": grouped_source,
                "key": "derived:profile_count",
                "source_value": str(profile_count),
            }
        )
    claims.extend(
        [
            {
                "location": "final_requirements_matrix.md",
                "number": str(len(plans)),
                "source_file": grouped_source,
                "key": "derived:plan_row_count",
                "source_value": str(len(plans)),
            },
            {
                "location": "final_requirements_matrix.md",
                "number": str(len({row["student_id"] for row in plans})),
                "source_file": grouped_source,
                "key": "derived:profile_count",
                "source_value": str(len({row["student_id"] for row in plans})),
            },
            {
                "location": "final_requirements_matrix.md",
                "number": str(len({row["student_id"] for row in _read_csv(GENERATED / "mc_results.csv")})),
                "source_file": "reports/generated/mc_results.csv",
                "key": "derived:mc_profile_count",
                "source_value": str(len({row["student_id"] for row in _read_csv(GENERATED / "mc_results.csv")})),
            },
            {
                "location": "BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx / executive summary",
                "number": str(sum(row["risk_level"] == "CAO" for row in build_risk_rows(plans))),
                "source_file": grouped_source,
                "key": "derived:high_risk_plan_count",
                "source_value": str(sum(row["risk_level"] == "CAO" for row in build_risk_rows(plans))),
            },
        ]
    )
    claims.extend(
        [
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/curriculum_validation.json",
                "summary.course_counts.total_rows",
                _read_json(GENERATED / "curriculum_validation.json")["summary"]["course_counts"]["total_rows"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/curriculum_validation.json",
                "summary.prerequisite_graph.edge_count",
                _read_json(GENERATED / "curriculum_validation.json")["summary"]["prerequisite_graph"]["edge_count"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/metrics.json",
                "ml.protocol.split_counts.validation",
                bundle["metrics"]["protocol"]["split_counts"]["validation"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/metrics.json",
                "ml.protocol.split_counts.test",
                bundle["metrics"]["protocol"]["split_counts"]["test"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/metrics.json",
                "ml.protocol.test_evaluations",
                bundle["metrics"]["protocol"]["test_evaluations"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/curriculum_validation.json",
                "n_checks",
                _read_json(GENERATED / "curriculum_validation.json")["n_checks"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/curriculum_validation.json",
                "n_pass",
                _read_json(GENERATED / "curriculum_validation.json")["n_pass"],
            ),
            _json_claim(
                "final_requirements_matrix.md",
                "reports/generated/curriculum_validation.json",
                "n_warn",
                _read_json(GENERATED / "curriculum_validation.json")["n_warn"],
            ),
        ]
    )
    for location, key, value in (
        ("final_questions_for_co.md", "monte_carlo.default_lambdas", _read_yaml(ROOT / "config" / "monte_carlo_scenario.yaml")["monte_carlo"]["default_lambdas"]),
        ("final_questions_for_co.md", "optimizer.scenario_budgets.NORMAL", _read_yaml(ROOT / "config" / "optimizer_scenario_v2.yaml")["optimizer"]["scenario_budgets"]["NORMAL"]),
        ("final_questions_for_co.md", "optimizer.scenario_budgets.WEAK_OR_POOR", _read_yaml(ROOT / "config" / "optimizer_scenario_v2.yaml")["optimizer"]["scenario_budgets"]["WEAK_OR_POOR"]),
        ("final_questions_for_co.md", "derived:confidence_level_percent", _read_yaml(ROOT / "config" / "monte_carlo_scenario.yaml")["monte_carlo"]["confidence_level"] * 100),
    ):
        items = list(enumerate(value)) if isinstance(value, list) else [(None, value)]
        for index, item in items:
            claim_key = f"{key}.{index}" if index is not None else key
            claims.append(
                _json_claim(
                    location,
                    "config/monte_carlo_scenario.yaml"
                    if key.startswith("monte_carlo") or key.startswith("derived:")
                    else "config/optimizer_scenario_v2.yaml",
                    claim_key,
                    item,
                )
            )
    for key, value in (
        ("high_expected_failed_courses_gte", RISK_THRESHOLDS["high_failed_courses"]),
        ("high_warning_probability_gte", RISK_THRESHOLDS["high_warning_probability"]),
        ("medium_expected_failed_courses_gte", RISK_THRESHOLDS["medium_failed_courses"]),
    ):
        claims.append(
            _json_claim(
                "BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx / risk thresholds",
                "reports/generated/final_risk_thresholds.json",
                key,
                value,
            )
        )

    return claims


def write_prose_claims() -> list[dict[str, str]]:
    claims = build_prose_claim_rows()
    output = GENERATED / "prose_claims.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("location", "number", "source_file", "key", "source_value"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(claims)
    return claims


def _write_risk_thresholds() -> None:
    optimizer = _read_yaml(ROOT / "config" / "optimizer_scenario_v2.yaml")["optimizer"]
    (GENERATED / "final_risk_thresholds.json").write_text(
        json.dumps(
            {
                "source_label": RISK_THRESHOLDS["source_label"],
                "high_expected_failed_courses_gte": RISK_THRESHOLDS["high_failed_courses"],
                "high_warning_probability_gte": RISK_THRESHOLDS["high_warning_probability"],
                "medium_expected_failed_courses_gte": RISK_THRESHOLDS["medium_failed_courses"],
                "threshold_note": (
                    "Ngưỡng cảnh báo hiển thị là GIẢ ĐỊNH theo yêu cầu WP1. "
                    "fast_fmax và Fmax mềm là tham số bộ lập kế hoạch; không đồng nhất "
                    "chúng với các ngưỡng cảnh báo rủi ro."
                ),
                "config_file": "config/optimizer_scenario_v2.yaml",
                "fast_fmax_config_key": "optimizer.plan_selection.fast_fmax",
                "fast_fmax_config_value": optimizer["plan_selection"]["fast_fmax"],
                "soft_fmax_grid_config_key": "optimizer.risk_cap.fmax_grid",
                "soft_fmax_grid_config_value": optimizer["risk_cap"]["fmax_grid"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_final_artifacts() -> None:
    bundle = load_validation_claims()
    plans = _read_csv(GENERATED / "plans_by_student.csv")
    model_rows = bundle["models"]
    three = model_rows["three_class"]
    binary = model_rows["binary_dropout"]
    three_recall = bundle["three_metrics"]["dropout_recall_at_precision_0.50"]["recall"]
    binary_recall = bundle["binary_metrics"]["dropout_recall_at_precision_0.50"]["recall"]
    ci_claim = (
        "KTC ghép cặp 95% cho chênh lệch giữa hai bài toán không có trong "
        "`ml_validation_bootstrap_ci.json` (tệp chỉ lưu KTC validation của mô hình ba lớp)."
    )
    question = (
        "1. Cảnh báo nên trình bày ba lớp (Dropout/Enrolled/Graduate) hay nhị phân? "
        f"Validation XGBoost: PR-AUC Dropout ba lớp={_fmt(float(three['dropout_pr_auc']))}, "
        f"nhị phân={_fmt(float(binary['dropout_pr_auc']))}; recall tại precision ≥ 0,50 "
        f"ba lớp={_fmt(three_recall)}, nhị phân={_fmt(binary_recall)}; "
        f"Brier ba lớp={_fmt(float(three['dropout_brier']))}, "
        f"nhị phân={_fmt(float(binary['dropout_brier']))}. {ci_claim} "
        "Vì vậy chưa đủ cơ sở để kết luận hai cách tiếp cận phân biệt được về mặt thống kê. "
        "**Mặc định:** giữ ba lớp để không gộp Enrolled bị kiểm duyệt phải vào nhãn khác."
    )
    question_path = GENERATED / "final_questions_for_co.md"
    question_text = question_path.read_text(encoding="utf-8-sig")
    mc_config = _read_yaml(ROOT / "config" / "monte_carlo_scenario.yaml")["monte_carlo"]
    optimizer = _read_yaml(ROOT / "config" / "optimizer_scenario_v2.yaml")["optimizer"]
    lambdas = mc_config["default_lambdas"]
    normal_budget = optimizer["scenario_budgets"]["NORMAL"]
    weak_budget = optimizer["scenario_budgets"]["WEAK_OR_POOR"]
    confidence_percent = int(round(mc_config["confidence_level"] * 100))
    question_lines = question_text.splitlines()
    replacements = {
        "2.": (
            f"2. Báo cáo Monte Carlo nên trình bày cả λ=0 và λ>0? **Mặc định:** trình bày "
            f"λ={lambdas[0]} và λ={lambdas[1]} làm lát cắt chính; λ={lambdas[-1]} là độ nhạy, "
            "tất cả gắn nhãn GIẢ ĐỊNH."
        ),
        "3.": (
            f"3. Có dùng lưới kịch bản {normal_budget} cho sinh viên thường và "
            f"{weak_budget} tín chỉ cho hồ sơ yếu/kém không? **Mặc định:** có, nhưng đây là lưới "
            "phân tích, không thay giới hạn QĐ 753."
        ),
        "5.": (
            f"5. Cô duyệt tiêu chí Pareto hiện tại và KTC bootstrap ghép cặp {confidence_percent}% "
            "không? **Mặc định:** chỉ kết luận trội khi tiêu chí chính và KTC cùng ủng hộ; "
            "nếu không thì ghi chưa phân biệt."
        ),
    }
    for index, line in enumerate(question_lines):
        for prefix, replacement in replacements.items():
            if line.startswith(prefix + " "):
                question_lines[index] = replacement
                break
    labels_question = (
        "7. Cô xác nhận cách trình bày ba nhãn “Ưu tiên giảm rủi ro”, “Cân bằng”, "
        "“Tăng tốc” và mức cảnh báo rủi ro GIẢ ĐỊNH tách biệt với trạng thái bộ giải không?"
    )
    if not any(line.startswith("7. ") for line in question_lines):
        question_lines.append(labels_question)
    question_path.write_text(
        "\n".join([question, *question_lines[1:]]) + "\n",
        encoding="utf-8",
    )

    matrix_path = GENERATED / "final_requirements_matrix.md"
    matrix_text = matrix_path.read_text(encoding="utf-8-sig")
    lr_recall = bundle["metrics"]["validation"]["multiclass"]["LogisticRegression"]["per_class"]["Enrolled"]["recall"]
    xgb_enrolled_recall = bundle["metrics"]["validation"]["multiclass"]["XGBoost"]["per_class"]["Enrolled"]["recall"]
    curriculum = _read_json(GENERATED / "curriculum_validation.json")
    split = bundle["metrics"]["protocol"]["split_counts"]
    mc_rows = _read_csv(GENERATED / "mc_results.csv")
    plan_count = len(plans)
    profile_count = len({row["student_id"] for row in plans})
    row_replacements = {
        "1. Dữ liệu CTĐT": (
            f"| 1. Dữ liệu CTĐT và nguồn | Một phần | `data/official/`, `config/program_official.yaml`, "
            f"`reports/generated/curriculum_validation.json`: nhãn OFFICIAL (NTU), "
            f"{curriculum['summary']['course_counts']['total_rows']} dòng và "
            f"{curriculum['summary']['prerequisite_graph']['edge_count']} quan hệ; mã HP và một số "
            "diễn giải quan hệ còn cần xác nhận. |"
        ),
        "3. ML tại T1": (
            f"| 3. ML tại T1 | Một phần | `docs/ml_protocol.md`, `reports/generated/model_comparison.csv`, "
            f"`metrics.json`: split train/validation/test={split['train']}/{split['validation']}/{split['test']}; "
            f"test_evaluations={bundle['metrics']['protocol']['test_evaluations']}; chỉ UCI-697, "
            "chưa kiểm định trên sinh viên NTU. |"
        ),
        "4. ILP và phương án": (
            f"| 4. ILP và phương án | Một phần | `reports/generated/optimization_spec.md`, "
            f"`plans_by_student.csv`, `ilp_sensitivity.csv`: {profile_count} hồ sơ × "
            f"{plan_count // profile_count} phương án; giới hạn chưa được quy chế chứng minh được "
            "giữ nhãn giả định hoặc UNCONFIRMED. |"
        ),
        "5. Monte Carlo và giao diện": (
            f"| 5. Monte Carlo và giao diện | Một phần | `mc_results.csv`, `mc_grad_hist.csv`, "
            f"`mc_pairwise.csv`, `mc_pareto.csv`, `app/main.py`: {len({row['student_id'] for row in mc_rows})} "
            "hồ sơ SCENARIO; phân tích giả định, không phải bằng chứng hiệu quả tại NTU; "
            "ảnh/video thuộc gói demo. |"
        ),
        "Enrolled recall": (
            "| Enrolled recall (validation) | Đã làm, còn hạn chế | "
            f"REAL (UCI-697), validation: Logistic Regression={_fmt(lr_recall)}, "
            f"XGBoost={_fmt(xgb_enrolled_recall)}. Enrolled bị kiểm duyệt phải; "
            "không diễn giải là nhãn kết quả cuối. |"
        ),
        "“14 tiêu chí”": (
            f"| Kiểm định số lượng hiện hành | Đã làm; số cũ được đính chính | "
            f"`curriculum_validation.json`: `n_checks={curriculum['n_checks']}`, "
            f"`n_pass={curriculum['n_pass']}`, `n_warn={curriculum['n_warn']}`, "
            f"`n_fail={curriculum['n_fail']}`. `n_checks` là độ dài mảng `checks`. |"
        ),
        "S003 best_effort": (
            "| S003 best_effort | Đã làm một phần | Hồ sơ và số liệu S003 thuộc Persona/catalogue "
            "SIMULATED cũ, không thuộc đầu ra hiện hành. Đầu ra SCENARIO có phương án best_effort; "
            "cần giữ cảnh báo rủi ro và khuyến nghị cố vấn. |"
        ),
        "Nhãn phương án và cảnh báo": (
            "| Nhãn phương án và cảnh báo rủi ro | Đã làm | "
            f"`app/view_data.py`, `app/main.py`, `final_risk_thresholds.json`: "
            f"risk_focused={PLAN_DISPLAY_LABELS['risk_focused']}; "
            f"balanced={PLAN_DISPLAY_LABELS['balanced']}; "
            f"acceleration={PLAN_DISPLAY_LABELS['acceleration']}. "
            "Mức CAO hiện riêng với trạng thái bộ giải, kèm khuyến nghị cố vấn. |"
        ),
    }
    matrix_lines = matrix_text.splitlines()
    for prefix, new_row in row_replacements.items():
        try:
            row_index, _ = _find_matrix_row(matrix_text, prefix)
        except ValueError:
            if prefix == "“14 tiêu chí”":
                row_index, _ = _find_matrix_row(matrix_text, "Kiểm định số lượng hiện hành")
                matrix_lines[row_index] = new_row
            elif prefix == "Nhãn phương án và cảnh báo":
                matrix_lines.append(new_row)
            else:
                raise
        else:
            matrix_lines[row_index] = new_row
    matrix_path.write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")

    identical_count, distinct_count, repeated = plan_signatures(plans)
    profile_count = len({row["student_id"] for row in plans})
    repeated_text = ", ".join(repeated) if repeated else "không có"
    draft_path = GENERATED / "final_cover_message.md"
    draft = draft_path.read_text(encoding="utf-8-sig").rstrip()
    mandatory_note = (
        f"Từ {profile_count} hồ sơ SCENARIO, {identical_count} hồ sơ có bộ kết quả ba phương án "
        f"giống hệt ({repeated_text}), nên có {distinct_count} kiểu kết quả khác nhau."
    )
    media_files = [
        path
        for path in (ROOT / "demo_media").rglob("*")
        if path.is_file()
    ] if (ROOT / "demo_media").is_dir() else []
    image_count = sum(path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} for path in media_files)
    video_count = sum(path.suffix.lower() in {".mp4", ".mov", ".webm"} for path in media_files)
    if image_count and video_count:
        media_note = "Ảnh minh họa và video giao diện có trong `demo_media/`."
    elif image_count:
        media_note = "Ảnh minh họa giao diện có trong `demo_media/`; hiện chưa có video."
    elif video_count:
        media_note = "Video giao diện có trong `demo_media/`; hiện chưa có ảnh minh họa."
    else:
        media_note = "Chưa có ảnh minh họa hoặc video giao diện trong `demo_media/`."
    added_sentences = (
        "Em kính mong cô góp ý trước khi nhóm hoàn thiện. "
        "Kết quả Monte Carlo là phân tích kịch bản theo giả định, không phải bằng chứng hiệu quả "
        "với sinh viên NTU."
    )
    labels_note = (
        f"Nhãn phương án hiển thị: {PLAN_DISPLAY_LABELS['risk_focused']}, "
        f"{PLAN_DISPLAY_LABELS['balanced']}, {PLAN_DISPLAY_LABELS['acceleration']}. "
        "Mức cảnh báo rủi ro là GIẢ ĐỊNH và tách khỏi trạng thái bộ giải."
    )
    draft = draft.replace(
        "Ảnh/video giao diện chưa được nhóm bổ sung; OULAD chưa sử dụng.",
        f"{media_note} OULAD chưa sử dụng.",
    )
    if labels_note not in draft:
        draft = draft.replace("\n\nTừ ", f"\n\n{labels_note}\n\nTừ ", 1)
    if mandatory_note not in draft:
        draft = draft.replace("Em cảm ơn cô.", f"{mandatory_note}\n\n{added_sentences}\n\nEm cảm ơn cô.")
    draft_path.write_text(draft + "\n", encoding="utf-8")
    _write_risk_thresholds()
    write_prose_claims()


def write_risk_levels() -> list[dict[str, str]]:
    rows = build_risk_rows(_read_csv(GENERATED / "plans_by_student.csv"))
    _write_risk_thresholds()
    output = GENERATED / "final_risk_levels.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "student_id",
                "plan_type",
                "display_label",
                "selected_credits",
                "expected_credits_passed",
                "expected_failed_courses",
                "p_warning_W1",
                "p_warning_W2",
                "risk_level",
                "warning",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows
