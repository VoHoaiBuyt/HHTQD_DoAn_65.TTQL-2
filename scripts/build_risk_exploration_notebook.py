"""Build the reproducible exploratory notebook for task C."""

from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "02_risk_to_plan_exploration.ipynb"

cells = [
    nbformat.v4.new_markdown_cell(
        """# Khảo sát chuyển rủi ro sang phương án đăng ký

Phân tích **EXPLORATORY, chưa phải mô hình cuối**. Dữ liệu học vụ gắn nhãn **REAL (UCI-697)**; hồ sơ, học phần, hệ số độ khó và kế hoạch gắn nhãn **SIMULATED** hoặc **GIẢ ĐỊNH kịch bản**. Mốc dự báo T1 chỉ dùng thuộc tính `available_at` là `T0` hoặc `T1_known`. `T1_decision` chỉ được dùng ở phép thử chẩn đoán M1 và phân tích tải C.3; tuyệt đối không dùng trong feature cơ sở.

Chạy từ thư mục gốc dự án, sau khi cài dependencies hiện có của notebook 01. Seed cố định: `20261105`.
"""
    ),
    nbformat.v4.new_code_cell(
        """from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

ROOT = Path.cwd()
if not (ROOT / "src").exists():
    ROOT = Path.cwd().parent
sys.path.insert(0, str(ROOT))

from src.analysis.risk_to_plan_exploration import run_exploration

result = run_exploration()
print(f"Data label: {result['data_label']}; seed={result['seed']}")
print(f"T1 base features: {result['feature_count']}")
feature_gate_passed = all(
    name not in {
        "Debtor", "Tuition fees up to date", "Scholarship holder",
        "Unemployment rate", "Inflation rate", "GDP",
        "Curricular units 2nd sem (credited)",
        "Curricular units 2nd sem (enrolled)",
        "Curricular units 2nd sem (evaluations)",
        "Curricular units 2nd sem (approved)",
        "Curricular units 2nd sem (grade)",
        "Curricular units 2nd sem (without evaluations)",
        "Target",
    }
    for name in result["features"]
)
assert feature_gate_passed
print("Feature timestamp gate passed:", feature_gate_passed)"""
    ),
    nbformat.v4.new_markdown_cell("## C.1 — P(Dropout) mức sinh viên tại T1"),
    nbformat.v4.new_code_cell(
        """dropout = result["dropout_model"]
display(pd.DataFrame([{
    "data_label": "REAL (UCI-697), exploratory",
    "CV accuracy mean": dropout["cv_accuracy_mean"],
    "CV macro-F1 mean": dropout["cv_f1_macro_mean"],
    "CV F1 Dropout mean": dropout["cv_f1_dropout_mean"],
    "holdout precision Dropout": dropout["holdout_precision_dropout"],
    "holdout recall Dropout": dropout["holdout_recall_dropout"],
    "holdout F1 Dropout": dropout["holdout_f1_dropout"],
    "holdout Brier (one-vs-rest)": dropout["brier_dropout"],
}]).round(4))

display(pd.DataFrame(
    dropout["confusion_matrix"],
    index=dropout["confusion_labels"],
    columns=dropout["confusion_labels"],
).rename_axis("Actual \\\\ Predicted"))
print("Risk tier thresholds selected from training OOF validation:")
print(dropout["risk_tier_validation_thresholds"])

calibration = dropout["calibration"]
plt.figure(figsize=(5, 5))
plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
plt.plot(
    calibration["predicted_mean"],
    calibration["observed_dropout_rate"],
    marker="o",
    label="Holdout quantile bins",
)
plt.xlabel("Mean predicted P(Dropout)")
plt.ylabel("Observed Dropout rate")
plt.title("Calibration — REAL (UCI-697), exploratory")
plt.legend()
plt.grid(alpha=0.25)
plt.show()"""
    ),
    nbformat.v4.new_markdown_cell(
        """## C.2 — Tỷ lệ đạt học phần HK2

`pass_rate_2 = approved_2nd / enrolled_2nd`, chỉ định nghĩa khi số học phần HK2 đăng ký lớn hơn 0. Có 180 sinh viên không đăng ký HK2 nên không có mẫu số, bị loại khỏi nhãn hồi quy. `without evaluations` vẫn nằm trong mẫu số `enrolled`; các unit đó chưa được tính là đạt, và được thống kê riêng để thể hiện bất định về cơ hội đánh giá. Đặc trưng mô hình vẫn chỉ là T0 + T1-known.
"""
    ),
    nbformat.v4.new_code_cell(
        """pass_rate = result["pass_rate_model"]
display(pd.DataFrame([{
    "data_label": "REAL (UCI-697), exploratory",
    "students with enrolled_2 > 0": pass_rate["eligible_students"],
    "students excluded (enrolled_2 = 0)": pass_rate["excluded_zero_enrollment"],
    "CV MAE": pass_rate["cv_mae_mean"],
    "CV RMSE": pass_rate["cv_rmse_mean"],
    "holdout MAE": pass_rate["holdout_mae"],
    "holdout RMSE": pass_rate["holdout_rmse"],
    "holdout calibration decile MAE (raw)": pass_rate["holdout_calibration_mae_raw"],
    "holdout calibration decile MAE (isotonic)": pass_rate["holdout_calibration_mae_isotonic"],
    "holdout MAE (isotonic)": pass_rate["holdout_mae_isotonic"],
    "holdout RMSE (isotonic)": pass_rate["holdout_rmse_isotonic"],
    "HK2 units without evaluations": result["without_evaluation_units_hk2"],
}]).round(4))"""
    ),
    nbformat.v4.new_code_cell(
        """display(pass_rate["calibration_deciles_raw"].round(4))
display(pass_rate["calibration_deciles_isotonic"].round(4))
zero_enrollment = result["stratified_load"]["table"].query("hk2_enrolled_band == '0'")
print("Dropout rate among enrolled_2=0 (REAL):",
      zero_enrollment["dropout_rate"].iloc[0])"""
    ),
    nbformat.v4.new_markdown_cell(
        """## C.3 — Tải đăng ký và kết quả quan sát

Tầng năng lực HK1 chia theo quantile của tỷ lệ `approved_1st / enrolled_1st`; tải HK2 chia thành `0`, `1–5`, `6–7`, `8+` curricular units. Pass rate là pooled approved/enrolled theo tầng; Dropout rate là tỷ lệ sinh viên trong tầng. Đây là quan sát REAL, không phải hiệu ứng nhân quả.
"""
    ),
    nbformat.v4.new_code_cell(
        """load_table = result["stratified_load"]["table"].copy()
display(load_table.sort_values(
    ["hk1_ability", "hk2_enrolled_band"],
    key=lambda col: col.map({
        "Thấp": 0, "Trung bình": 1, "Cao": 2,
        "0": 0, "1-5": 1, "6-7": 2, "8+": 3,
    }) if col.name in {"hk1_ability", "hk2_enrolled_band"} else col,
).round(4))
print("Adjusted observational OR per extra HK2 unit:",
      round(result["stratified_load"]["adjusted_or_per_hk2_unit"], 6))
print("REAL HK2 denominator totals:")
display(result["stratified_load"]["overall"].round(4))
print("M3-prime baseline pooled by HK1 ability, REAL (UCI-697):")
display(result["stratified_load"]["m3_prime_table"].round(4))

display(load_table.pivot(
    index="hk1_ability", columns="hk2_enrolled_band", values="pass_rate_2"
).reindex(index=["Thấp", "Trung bình", "Cao"], columns=["0", "1-5", "6-7", "8+"]).round(3))"""
    ),
    nbformat.v4.new_markdown_cell(
        """## M1 — Diagnostic counterfactual, loại làm phương pháp chính

M1 thêm biến quyết định `enrolled_2` vào mô hình Dropout rồi thay đổi giá trị cho một vector đặc trưng đại diện. Đây không phải mô hình vận hành hợp lệ tại T1, và không phải can thiệp nhân quả.
"""
    ),
    nbformat.v4.new_code_cell(
        """m1 = result["m1"]
display(m1["counterfactual_table"].round(4))
assert m1["counterfactual_table"]["predicted_p_dropout"].diff().dropna().gt(0).all()
print("Holdout Brier with T1_decision:",
      round(m1["holdout_brier_with_t1_decision"], 6))
print("Holdout Brier without T1_decision:",
      round(m1["holdout_brier_without_t1_decision"], 6))
print("Binary same-controls OR per unit:",
      round(m1["binary_same_controls_or_per_enrolled_unit"], 6))
print("Three-class effective counterfactual OR per unit:",
      round(m1["multiclass_effective_counterfactual_or_per_enrolled_unit"], 6))"""
    ),
    nbformat.v4.new_markdown_cell(
        """## M2/M3' — Hệ số môn học SIMULATED và so sánh persona

        M2 dùng `p_student_pass × f_difficulty × g_load × r_retake`, cắt về [0,1]. M3' lấy tỷ lệ REAL theo riêng tầng năng lực HK1, gộp mọi mức tải; tầng hiếm dưới cỡ mẫu tối thiểu trong config được gộp với tầng kề. Tỷ lệ theo band tải chỉ giữ làm minh chứng thiên lệch chọn lọc.
"""
    ),
    nbformat.v4.new_code_cell(
        """persona = result["persona"]
display(persona["difficulty_factors_table"].round(4))
display(persona["table"][[
    "data_label", "student_id", "persona", "ability_tier_from_real_hk1",
    "scenario_credit_budget", "planned_credits_actual", "selected_course_ids",
    "p_dropout_student_level", "p_student_pass_rate_model",
    "m2_expected_credits_passed", "m2_expected_failed_courses",
    "m3_prime_p_pass_by_ability", "m3_band_p_pass_selection_bias_reference",
    "m3_expected_failed_courses", "status",
]].round(4))"""
    ),
    nbformat.v4.new_markdown_cell("## C.6 — Kiểm tra logic và khả năng khả thi"),
    nbformat.v4.new_code_cell(
        """scenario_results = persona["table"]
monotonic_checks = []
for student_id, group in scenario_results.groupby("student_id"):
    group = group.sort_values("scenario_credit_budget")
    monotonic_checks.append({
        "data_label": "SIMULATED",
        "student_id": student_id,
        "M2_expected_failures_non_decreasing": bool(
            group["m2_expected_failed_courses"].diff().dropna().ge(-1e-9).all()
        ),
        "M3prime_expected_failures_non_decreasing": bool(
            group["m3_expected_failed_courses"].diff().dropna().ge(-1e-9).all()
        ),
        "credits_increase_or_saturate": bool(
            group["m2_expected_credits_passed"].diff().dropna().ge(-1e-9).all()
        ),
        "budgets_underfilled": bool(
            (group["planned_credits_actual"] < group["scenario_credit_budget"]).any()
        ),
    })
checks = pd.DataFrame(monotonic_checks)
display(checks)
assert checks["M2_expected_failures_non_decreasing"].all()
assert checks["M3prime_expected_failures_non_decreasing"].all()
assert checks["credits_increase_or_saturate"].all()
assert scenario_results.loc[
    scenario_results["student_id"].eq("S001"), "p_student_pass_rate_model"
].iloc[0] > scenario_results.loc[
    scenario_results["student_id"].eq("S003"), "p_student_pass_rate_model"
].iloc[0]
display(scenario_results.groupby(
    ["student_id", "persona"], as_index=False
).agg(
    p_student_pass_rate_model=("p_student_pass_rate_model", "first"),
    p_dropout_student_level=("p_dropout_student_level", "first"),
).sort_values("p_student_pass_rate_model", ascending=False).round(4))"""
    ),
    nbformat.v4.new_markdown_cell(
        """## C.7 — Độ nhạy của tải, độ khó và học lại

Các hệ số dưới đây là **GIẢ ĐỊNH kịch bản**, không phải ước lượng nhân quả. Độ nhạy tải tại ngân sách 12/15/18 dùng pooled pass rate REAL làm mốc minh họa, `f_difficulty = 1`, `r_retake = 1`; nó không đại diện cho dự báo cá nhân. Bảng persona thay đổi đồng thời các hệ số trong lưới config.
"""
    ),
    nbformat.v4.new_code_cell(
        """display(persona["load_sensitivity"].round(4))
display(persona["sensitivity_summary"].round(4))
print("Sensitivity grid from config:", result["exploration_config"])"""
    ),
]

notebook = nbformat.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python"},
    },
)
nbformat.validate(notebook)
NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(notebook, NOTEBOOK_PATH)
print(f"Created {NOTEBOOK_PATH}")
