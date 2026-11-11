# Ma trận đối chiếu yêu cầu và lưu ý của giảng viên

| Ý | Trạng thái | Bằng chứng và ghi chú |
|---|---|---|
| 1. Dữ liệu CTĐT và nguồn | Một phần | `data/official/`, `config/program_official.yaml`, `reports/generated/curriculum_validation.json`: nhãn OFFICIAL (NTU), 101 dòng và 15 quan hệ; mã HP và một số diễn giải quan hệ còn cần xác nhận. |
| 2. QĐ 753/2021 và rule engine | Một phần | `config/credit_rules_official.yaml`, `reports/generated/regulation_assumptions.md`, `tests/test_official_rules.py`: điều khoản được ghi nguồn; hè, mở lớp, học cải thiện và một số ngữ nghĩa chưa mô hình hóa/xác nhận. |
| 3. ML tại T1 | Một phần | `docs/ml_protocol.md`, `reports/generated/model_comparison.csv`, `metrics.json`: split train/validation/test=2654/885/885; test_evaluations=1; chỉ UCI-697, chưa kiểm định trên sinh viên NTU. |
| 4. ILP và phương án | Một phần | `reports/generated/optimization_spec.md`, `plans_by_student.csv`, `ilp_sensitivity.csv`: 9 hồ sơ × 3 phương án; giới hạn chưa được quy chế chứng minh được giữ nhãn giả định hoặc UNCONFIRMED. |
| 5. Monte Carlo và giao diện | Một phần | `mc_results.csv`, `mc_grad_hist.csv`, `mc_pairwise.csv`, `mc_pareto.csv`, `app/main.py`: 9 hồ sơ SCENARIO; phân tích giả định, không phải bằng chứng hiệu quả tại NTU; ảnh/video thuộc gói demo. |
| 6. Kiểm thử, báo cáo và đóng gói | Một phần | `pytest_summary.txt`, `stage2_report.docx`, `README.md`, `HANDOFF.md`, `final_dist_validation.md`: full pytest tại repo và trên dist sạch đã chạy; ảnh/video chưa được bổ sung. |
| Enrolled recall (validation) | Đã làm, còn hạn chế | REAL (UCI-697), validation: Logistic Regression=0.2893, XGBoost=0.3270. Enrolled bị kiểm duyệt phải; không diễn giải là nhãn kết quả cuối. |
| Lỗi môn song hành | Đã làm một phần | `core/rules.py`, `tests/test_core_rules.py`: lọc lặp đến điểm ổn định; ca regression cho quan hệ hai chiều, chuỗi, đang học, không mở kỳ và ràng buộc ILP. Ý nghĩa quy chế của “song hành” còn UNCONFIRMED. |
| Kiểm định số lượng hiện hành | Đã làm; số cũ được đính chính | `curriculum_validation.json`: `n_checks=13`, `n_pass=10`, `n_warn=3`, `n_fail=0`. `n_checks` là độ dài mảng `checks`. |
| g_load theo ngân sách | Đã làm | `optimization_spec.md`, `core/optimizer.py`, `plans_by_student.csv`: tải lấy từ tín chỉ thực chọn L và chuyển thành `units(L)` theo công thức; không dùng số môn làm đại diện tín chỉ. |
| S003 best_effort | Đã làm một phần | Hồ sơ và số liệu S003 thuộc Persona/catalogue SIMULATED cũ, không thuộc đầu ra hiện hành. Đầu ra SCENARIO có phương án best_effort; cần giữ cảnh báo rủi ro và khuyến nghị cố vấn. |
| P(Dropout) | Đã làm | `optimization_spec.md`, `plans_by_student.csv`: cảnh báo mềm/hậu kiểm; risk cap chính ở chế độ off; không khóa quyền đăng ký. |
| Nhãn phương án và cảnh báo rủi ro | Đã làm | `app/view_data.py`, `app/main.py`, `final_risk_thresholds.json`: risk_focused=Ưu tiên giảm rủi ro; balanced=Cân bằng; acceleration=Tăng tốc. Mức CAO hiện riêng với trạng thái bộ giải, kèm khuyến nghị cố vấn. |
