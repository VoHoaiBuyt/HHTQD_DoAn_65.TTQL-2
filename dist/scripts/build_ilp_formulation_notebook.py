"""Build the reproducible Stage 1 ILP formulation-check notebook."""

from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "03_ilp_formulation_check.ipynb"

notebook = nbformat.v4.new_notebook()
notebook.cells = [
    nbformat.v4.new_markdown_cell(
        """# Kiểm tra công thức ILP — prototype giai đoạn 1

Mọi persona/CTĐT trong notebook là **SIMULATED**; tầng M3' lấy tỷ lệ nền từ **REAL (UCI-697)**. Các hệ số độ khó, tải, β/γ và giới hạn rủi ro là tham số **GIẢ ĐỊNH kịch bản**. Kết quả chỉ xác nhận khả năng chạy và sanity-check công thức, không chứng minh hiệu quả hoặc quan hệ nhân quả.

Seed: `20261105`. Bộ giải: PuLP + HiGHS.
"""
    ),
    nbformat.v4.new_code_cell(
        """from pathlib import Path
import sys

ROOT = Path.cwd()
if not (ROOT / "src").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from src.analysis.ilp_formulation_check import run_prototype

prototype = run_prototype()
print(f"Solver: {prototype['method']} | seed: {prototype['seed']}")
print("Persona:", ", ".join(prototype["personas"]))
"""
    ),
    nbformat.v4.new_markdown_cell(
        """## D.4 — Bốn persona × ngân sách 12/15/18 × λ"""
    ),
    nbformat.v4.new_code_cell(
        """prototype["results"][[
    "data_label", "student_id", "ability_tier_hk1", "p_dropout", "risk_tier",
    "p_student_m3_prime", "requested_credit_scenario", "effective_credit_max",
    "load_lambda", "status", "selected_course_ids", "selected_credits",
    "expected_failed_courses", "objective_value"
]].sort_values(["student_id", "requested_credit_scenario", "load_lambda"])"""
    ),
    nbformat.v4.new_markdown_cell(
        """## Độ nhạy β/γ"""
    ),
    nbformat.v4.new_code_cell(
        """prototype["objective_sensitivity"].sort_values(
    ["student_id", "beta", "gamma"]
)"""
    ),
    nbformat.v4.new_markdown_cell(
        """## Kiểm tra không suy biến bằng ablation minh họa

Fixture nhỏ dưới đây là **SIMULATED / GIẢ ĐỊNH**, không phải CTĐT hay dữ liệu học tập. So sánh tắt/bật giá trị mở khóa `u_i` và trần số môn kỳ vọng trượt `F_max`.
"""
    ),
    nbformat.v4.new_code_cell(
        """from src.optimize.ilp_prototype import solve_plan

toy_courses = [
    {"course_id": "A", "credits": 3, "status": "not_taken"},
    {"course_id": "B", "credits": 3, "status": "not_taken"},
    {"course_id": "C", "credits": 3, "status": "not_taken"},
    {"course_id": "D", "credits": 3, "status": "not_taken"},
]
common = {
    "eligible_courses": toy_courses,
    "p_student_m3_prime": 1.0,
    "load_lambda": 0.0,
    "risk_tier": "toy",
    "scenario_credit_max": 6,
    "expected_fail_cap": 0.8,
    "average_credits_per_unit": 2.67,
    "median_real_load_units": 6,
    "unlock_values": {"A": 0, "B": 0, "C": 10, "D": 0},
    "beta": 1.0,
    "gamma": 1.0,
    "minimum_credits": 6,
    "course_factors": {"A": 0.9, "B": 0.5, "C": 0.25, "D": 0.85},
}
ablations = [
    solve_plan(**common, enable_unlock_value=False, enable_expected_fail_cap=False),
    solve_plan(**common, enable_unlock_value=True, enable_expected_fail_cap=False),
    solve_plan(**common, enable_unlock_value=True, enable_expected_fail_cap=True),
]
[
    {
        "unlock_enabled": item["unlock_enabled"],
        "F_max_enabled": item["expected_fail_cap_enabled"],
        "selected_course_ids": item["selected_course_ids"],
        "selected_credits": item["selected_credits"],
        "expected_failed_courses": item["expected_failed_courses"],
    }
    for item in ablations
]"""
    ),
]
notebook.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3"},
}
nbformat.validate(notebook)
NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(notebook, NOTEBOOK_PATH)
print(f"Wrote {NOTEBOOK_PATH}")
