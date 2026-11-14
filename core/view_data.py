from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.risk_labels import (
    PLAN_DISPLAY_LABELS,
    RISK_THRESHOLD_NOTE,
    risk_level,
)


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "data" / "scenarios" / "student_profile_v2.csv"
MC_RESULTS_PATH = ROOT / "reports" / "generated" / "mc_results.csv"
MC_PAIRWISE_PATH = ROOT / "reports" / "generated" / "mc_pairwise.csv"
MC_PARETO_PATH = ROOT / "reports" / "generated" / "mc_pareto.csv"
MC_GRAD_HIST_PATH = ROOT / "reports" / "generated" / "mc_grad_hist.csv"
MC_INTERPRETATION_PATH = ROOT / "reports" / "generated" / "mc_interpretation.md"
PAGE_KEYS = (
    "Hồ sơ & tiến độ",
    "Nguy cơ & cảnh báo",
    "Học phần",
    "Phương án đăng ký",
    "What-if",
    "Mô phỏng",
    "Dữ liệu & giả định",
)


def list_scenarios() -> list[dict[str, str]]:
    with SCENARIO_PATH.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return [
        {
            "student_id": row["student_id"],
            "persona": row.get("persona", ""),
            "persona_purpose": row.get("persona_purpose", ""),
            "ml_scope": row.get("ml_scope", "UNKNOWN"),
            "ml_scope_reason": row.get("ml_scope_reason", ""),
        }
        for row in rows
    ]


def normalize_options(options: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = options or {}
    return {
        "budget": None if raw.get("budget") is None else int(raw["budget"]),
        "fmax": None if raw.get("fmax") is None else float(raw["fmax"]),
        "lambda": float(raw.get("lambda", 0.1)),
        "risk_cap_mode": raw.get("risk_cap_mode"),
        "progress_override": _jsonable(raw.get("progress_override", {})),
    }


def options_cache_key(options: dict[str, Any] | None = None) -> str:
    return json.dumps(
        normalize_options(options),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


app_cache_key = options_cache_key


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def build_profile_data(result: dict[str, Any]) -> dict[str, Any]:
    stats = result["progress"]["stats"]
    progress_rows = [
        {"course_id": course_id, **status}
        for course_id, status in sorted(result["progress"]["by_course"].items())
    ]
    return {
        "student": result["profile_summary"],
        "progress_rows": progress_rows,
        "stats": stats,
        "previous_semester_gpa": result["credit_regime"].get(
            "previous_semester_gpa"
        ),
        "study_year": next(
            (
                flag.get("study_year_label", flag.get("study_year"))
                for flag in result["academic_flags"]
                if flag.get("code") == "W4"
            ),
            "UNKNOWN",
        ),
        "source_label": "SCENARIO",
        "curriculum_label": "OFFICIAL (NTU)",
    }


def build_risk_data(result: dict[str, Any]) -> dict[str, Any]:
    risk = result.get("risk")
    summary = result["profile_summary"]
    enabled = summary.get("ml_scope") == "T1_valid" and risk is not None
    return {
        "enabled": enabled,
        "reason": (
            risk.get("scope_note", "")
            if enabled
            else result.get("risk_reason")
            or summary.get("ml_scope_reason")
            or f"ml_scope={summary.get('ml_scope', 'UNKNOWN')}"
        ),
        "risk": risk if enabled else None,
        "flags": result.get("academic_flags", []),
        "consecutive_warning_count": next(
            (
                flag.get("consecutive_warning_count")
                for flag in result.get("academic_flags", [])
                if flag.get("code") == "FORCED_WITHDRAWAL"
            ),
            None,
        ),
        "source_label": "REAL (UCI-697)",
        "academic_source_label": "OFFICIAL (NTU)",
    }


def build_courses_data(result: dict[str, Any]) -> dict[str, Any]:
    forced_ids = {
        str(row.get("course_key")) for row in result.get("forced_retakes", [])
    }
    debts = [
        {
            "course_id": course_id,
            "grade_10": row.get("grade_10"),
            "attempt_count": row.get("attempt_count"),
            "mandatory_retake_D11": course_id in forced_ids,
            "ref": "Đ11" if course_id in forced_ids else "",
        }
        for course_id, row in result["progress"]["by_course"].items()
        if row.get("status") == "failed"
    ]
    reason_labels = {
        "PREREQUISITE_NOT_COMPLETED": "Chưa đạt môn tiên quyết",
        "COREQUISITE_NOT_ELIGIBLE": "Chưa đủ điều kiện học song hành",
        "NOT_OFFERED": "Không mở trong kỳ theo giả định lịch mở môn",
        "ELECTIVE_SLOT_ALREADY_SELECTED": "Ô tự chọn đã đủ",
        "RETAKE_LIMIT_REACHED": "Đã chạm giới hạn học lại",
        "ALREADY_COMPLETED_OR_IN_PROGRESS": "Đã hoàn thành hoặc đang học",
    }
    blocked = []
    for row in result.get("blocked", []):
        explanations = []
        for reason in row.get("reasons", []):
            code = str(reason.get("code", "UNKNOWN"))
            message = reason_labels.get(code, code)
            prerequisite = reason.get("course_id")
            if prerequisite:
                message += f": {prerequisite}"
            explanations.append(message)
        blocked.append(
            {
                "course_key": row.get("course_key"),
                "reasons": row.get("reasons", []),
                "reason_text": "; ".join(explanations) or "UNKNOWN",
            }
        )
    return {
        "eligible": result.get("eligible", []),
        "blocked": blocked,
        "debts": debts,
        "forced_retakes": result.get("forced_retakes", []),
        "source_label": "OFFICIAL (NTU)",
        "enrichment_label": "GIẢ ĐỊNH (suy từ CTĐT)",
    }


def build_plans_data(result: dict[str, Any]) -> dict[str, Any]:
    cards = []
    risky_statuses = {"best_effort", "regulatory_conflict", "risk_cap_exceeded"}
    for plan in result.get("plans", []):
        status = str(plan.get("status", "UNKNOWN"))
        status_issue = (
            status in risky_statuses
            or bool(plan.get("regulatory_conflict"))
            or bool(plan.get("risk_cap_exceeded"))
        )
        level = risk_level(plan)
        cards.append(
            {
                **plan,
                "display_label": PLAN_DISPLAY_LABELS.get(
                    str(plan.get("plan_type")), str(plan.get("plan_type"))
                ),
                "risk_level": level,
                "risk_threshold_note": RISK_THRESHOLD_NOTE,
                "status_needs_advisor": status_issue,
                "needs_advisor": status_issue or level == "CAO",
                "source_label": "GIẢ ĐỊNH",
            }
        )
    return {"plans": cards, "source_label": "GIẢ ĐỊNH"}


def build_what_if_data(
    result: dict[str, Any], comparison_result: dict[str, Any] | None = None
) -> dict[str, Any]:
    stats = result["progress"]["stats"]
    limits = result["credit_regime"]
    return {
        "limits": limits,
        "baseline_plans": build_plans_data(result)["plans"],
        "comparison_plans": build_plans_data(comparison_result or result)["plans"],
        "stats": stats,
        "source_label": "OFFICIAL (NTU)",
        "parameter_label": "GIẢ ĐỊNH",
    }


def _read_optional_csv(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    return pd.read_csv(path, encoding="utf-8-sig")


def build_simulation_data(
    result: dict[str, Any],
    student_id: str | None = None,
    load_lambda: float | None = None,
) -> dict[str, Any]:
    frames = {
        "results": _read_optional_csv(MC_RESULTS_PATH),
        "pairwise": _read_optional_csv(MC_PAIRWISE_PATH),
        "pareto": _read_optional_csv(MC_PARETO_PATH),
        "grad_hist": _read_optional_csv(MC_GRAD_HIST_PATH),
    }
    selected_id = student_id or result["profile_summary"]["student_id"]
    filtered: dict[str, pd.DataFrame | None] = {}
    for name, frame in frames.items():
        if frame is not None and "student_id" in frame.columns:
            frame = frame.loc[frame["student_id"].astype(str) == str(selected_id)].copy()
        filtered[name] = frame
    pairwise = filtered["pairwise"]
    if (
        pairwise is not None
        and "comparison" not in pairwise.columns
        and {"policy_a", "policy_b"}.issubset(pairwise.columns)
    ):
        pairwise["comparison"] = (
            pairwise["policy_a"].astype(str) + " - " + pairwise["policy_b"].astype(str)
        )
        filtered["pairwise"] = pairwise
    results = filtered["results"]
    available_lambdas = (
        sorted(float(value) for value in results["lambda"].dropna().unique())
        if results is not None and "lambda" in results.columns
        else []
    )
    selected_lambda = load_lambda
    if selected_lambda is None and available_lambdas:
        selected_lambda = 0.1 if 0.1 in available_lambdas else available_lambdas[0]
    if selected_lambda is not None:
        for name, frame in filtered.items():
            if frame is not None and "lambda" in frame.columns:
                filtered[name] = frame.loc[
                    pd.to_numeric(frame["lambda"], errors="coerce").sub(
                        float(selected_lambda)
                    ).abs().lt(1e-9)
                ].copy()
    results = filtered["results"]
    pairwise = filtered["pairwise"]
    pareto = filtered["pareto"]
    return {
        **filtered,
        "available": results is not None and not results.empty,
        "source_label": "GIẢ ĐỊNH",
        "student_id": selected_id,
        "available_lambdas": available_lambdas,
        "selected_lambda": selected_lambda,
        "available_policies": (
            sorted(results["policy"].dropna().astype(str).unique())
            if results is not None and "policy" in results.columns
            else []
        ),
        "available_comparisons": (
            sorted(pairwise["comparison"].dropna().astype(str).unique())
            if pairwise is not None and "comparison" in pairwise.columns
            else []
        ),
        "pareto_labels": (
            sorted(pareto["dominance"].dropna().astype(str).unique())
            if pareto is not None and "dominance" in pareto.columns
            else []
        ),
        "interpretation_path": MC_INTERPRETATION_PATH,
    }


def build_provenance_data() -> dict[str, Any]:
    return {
        "sources": [
            {"nhãn": "OFFICIAL (NTU)", "nguồn": "data/official/", "chi tiết": "CTĐT và tiên quyết do nhóm cung cấp"},
            {"nhãn": "OFFICIAL (NTU)", "nguồn": "config/credit_rules_official.yaml", "chi tiết": "QĐ 753/QĐ-ĐHNT, 13/08/2021"},
            {"nhãn": "REAL (UCI-697)", "nguồn": "data/raw/uci_697/ và data/processed/", "chi tiết": "Vector đặc trưng mô hình; không phải hồ sơ cá nhân NTU"},
            {"nhãn": "SCENARIO", "nguồn": "data/scenarios/", "chi tiết": "Hồ sơ kịch bản, không phải dữ liệu cá nhân thật"},
            {"nhãn": "GIẢ ĐỊNH", "nguồn": "config/ và reports/generated/", "chi tiết": "Tham số/đầu ra mô phỏng; chỉ dùng khi có nhãn"},
        ],
        "curriculum_version": "UNKNOWN — chưa có phiên bản CTĐT trong metadata được đọc.",
        "unconfirmed": [
            "Nhận diện kỳ cuối qua kế hoạch đăng ký hoàn tất là UNCONFIRMED.",
            "Xử lý biên đúng 105 tín chỉ khi gán năm trình độ là UNCONFIRMED.",
            "Định nghĩa nợ cho W1 là UNCONFIRMED.",
            "Ngữ nghĩa song hành và độ đầy đủ của tiên quyết còn UNCONFIRMED.",
            "Lịch mở môn suy từ chẵn/lẻ là UNCONFIRMED / GIẢ ĐỊNH, không phải dữ kiện chính thức.",
            "Học kỳ hè và điều kiện mở lớp chưa được mô hình hóa.",
            "Giới hạn lượt học lại có giá trị UNKNOWN, source=NOT_FOUND.",
            "Chi tiết chuẩn đầu ra có giá trị UNKNOWN, source=NOT_FOUND.",
            "Mã HP0xx chưa được xác nhận nguồn gốc trong bảng CTĐT trích xuất.",
        ],
        "limitations": [
            "Không mô hình hóa học kỳ hè.",
            "Không mô hình hóa điều kiện mở lớp.",
            "Không mô hình hóa học cải thiện.",
            "M3' có nguồn dữ liệu Bồ Đào Nha; không phải bằng chứng hiệu quả với sinh viên NTU.",
        ],
    }


def build_page_data(
    page: str,
    result: dict[str, Any],
    *,
    comparison_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    builders = {
        "Hồ sơ & tiến độ": build_profile_data,
        "Nguy cơ & cảnh báo": build_risk_data,
        "Học phần": build_courses_data,
        "Phương án đăng ký": build_plans_data,
        "What-if": lambda value: build_what_if_data(value, comparison_result),
        "Mô phỏng": lambda value: build_simulation_data(value),
        "Dữ liệu & giả định": lambda _value: build_provenance_data(),
    }
    if page not in builders:
        raise ValueError(f"Unknown page: {page}")
    return builders[page](result)


def progress_override_from_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    allowed = {"completed", "failed", "in_progress", "not_taken"}
    override: dict[str, dict[str, Any]] = {}
    for row in rows:
        course_id = str(row["course_id"])
        status = str(row.get("status", "not_taken"))
        if status not in allowed:
            raise ValueError(f"{course_id}: trạng thái không hợp lệ: {status}")
        grade_value = row.get("grade_10")
        grade = None if pd.isna(grade_value) or grade_value == "" else float(grade_value)
        if grade is not None and not 0 <= grade <= 10:
            raise ValueError(f"{course_id}: điểm phải nằm trong khoảng 0–10.")
        if status == "completed" and (grade is None or grade < 5):
            raise ValueError(f"{course_id}: môn đạt cần có điểm từ 5,0 trở lên.")
        if status == "failed" and (grade is None or grade >= 5):
            raise ValueError(f"{course_id}: môn trượt cần có điểm dưới 5,0.")
        if status in {"in_progress", "not_taken"} and grade is not None:
            raise ValueError(f"{course_id}: trạng thái này không được có điểm kết thúc.")
        attempts = int(row.get("attempt_count", 0) or 0)
        semester = row.get("semester_taken")
        semester_value = None if pd.isna(semester) or semester == "" else int(semester)
        override[course_id] = {
            "status": status,
            "grade_10": grade,
            "attempt_count": attempts,
            "semester_taken": semester_value,
        }
    return override
