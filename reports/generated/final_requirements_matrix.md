# Ma trận đối chiếu yêu cầu và lưu ý của giảng viên

| Ý | Trạng thái | Bằng chứng và ghi chú |
|---|---|---|
| 1. Dữ liệu CTĐT và nguồn | Một phần | `data/official/`, `config/program_official.yaml`, `reports/generated/curriculum_validation.json`: nhãn OFFICIAL (NTU), 101 dòng; mã HP và một số diễn giải quan hệ còn cần xác nhận. |
| 2. QĐ 753/2021 và rule engine | Một phần | `config/credit_rules_official.yaml`, `reports/generated/regulation_assumptions.md`, `tests/test_official_rules.py`: điều khoản được ghi nguồn; hè, mở lớp, học cải thiện và một số ngữ nghĩa chưa mô hình hóa/xác nhận. |
| 3. ML tại T1 | Một phần | `docs/ml_protocol.md`, `reports/generated/model_comparison.csv`, `test_evaluation.json`, `ml_validation_bootstrap_ci.json`: test 885 dòng, evaluation_count=1; chỉ UCI-697, chưa kiểm định trên sinh viên NTU. |
| 4. ILP và phương án | Một phần | `reports/generated/optimization_spec.md`, `plans_by_student.csv`, `ilp_sensitivity.csv`: 9 hồ sơ × 3 phương án; các hồ sơ/giới hạn chưa được quy chế chứng minh được giữ nhãn giả định hoặc UNCONFIRMED. |
| 5. Monte Carlo và giao diện | Một phần | `mc_results.csv`, `mc_grad_hist.csv`, `mc_pairwise.csv`, `mc_pareto.csv`, `app/main.py`, `docs/screens_to_capture.md`: phân tích kịch bản, không phải bằng chứng hiệu quả tại NTU; ảnh/video do nhóm bổ sung. |
| 6. Kiểm thử, báo cáo và đóng gói | Một phần | `pytest_summary.txt`, `stage2_report.docx`, `README.md`, `HANDOFF.md`, `final_dist_validation.md`: full pytest tại repo và trên dist sạch đã chạy; ảnh/video chưa được bổ sung. |
| Enrolled recall khoảng 28,9% | Đã làm, còn hạn chế | `enrolled_analysis.md`: Logistic Regression validation Enrolled recall=0,2893; XGBoost validation=0,3270. Kết quả test chính: 40/159, recall=0,2516 (`test_evaluation.json`). Enrolled bị kiểm duyệt phải; không diễn giải là nhãn cuối cùng. |
| Lỗi môn song hành | Đã làm một phần | `core/rules.py`, `tests/test_core_rules.py`: lọc lặp đến điểm ổn định; ca regression cho quan hệ hai chiều, chuỗi, đang học, không mở kỳ và ràng buộc ILP. Ý nghĩa quy chế của “song hành” còn UNCONFIRMED. |
| “14 tiêu chí” so với 11 dòng kiểm tra | Đã làm; số cũ được đính chính | `curriculum_validation.json`: `n_checks=13`, `n_pass=10`, `n_warn=3`, `n_fail=0`. `n_checks` là độ dài mảng `checks`; không thay bằng số quan hệ tiên quyết. |
| g_load theo ngân sách | Đã làm | `optimization_spec.md`, `core/optimizer.py`, `plans_by_student.csv`: tải lấy từ tín chỉ thực chọn L và chuyển thành `units(L)` theo công thức; không dùng số môn làm đại diện tín chỉ. |
| S003 best_effort | Đã làm một phần | S003 và số liệu 2,98/Fmax=1 thuộc Persona/catalogue mô phỏng cũ, không thuộc đầu ra hiện hành. Đầu ra SCENARIO hiện có các phương án best_effort (ví dụ V2-005 acceleration, V2-007); cần giữ cảnh báo rủi ro và khuyến nghị cố vấn. |
| P(Dropout) | Đã làm | `optimization_spec.md`, `plans_by_student.csv`: cảnh báo mềm/hậu kiểm; risk cap chính ở chế độ off; không khóa quyền đăng ký. |
