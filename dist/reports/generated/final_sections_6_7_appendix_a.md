# Trích nguyên văn Chương 6, Chương 7 và Phụ lục A

Nguồn: báo cáo Word cuối kỳ. Bảng được sao từ nội dung Word.

## CHƯƠNG 6. TỐI ƯU ILP

### Mục tiêu, ràng buộc và cách đọc phương án

maximize Σ[c_i p_i - γ c_i(1-p_i) + β u_i] x_i`, where `p_i = clip(p_student × exp(-λ max(0, units(L)-6)) × r_retake(i), 0, 1)`.

Ngưỡng hòa vốn p*=γ/(1+γ)=0.5; β=0.125, γ=1.0. g_load tính theo L là tổng tín chỉ thực chọn và ngưỡng units(L)=6; u_i khác 0 trên 6 học phần (HP024, HP028, HP029, POL307, POL308, POL309), theo optimization_spec.md.

Ba nhãn hiển thị là Ưu tiên giảm rủi ro, Cân bằng và Tăng tốc. Ngưỡng CAO/TRUNG BÌNH/THẤP là GIẢ ĐỊNH, tách khỏi trạng thái solver. Cấu hình main plan dùng risk_cap_mode=off; P(Dropout) và Fmax là khuyến nghị mềm, không khóa quyền đăng ký.

Trạng thái `optimal` chỉ có nghĩa nghiệm tối ưu theo hàm mục tiêu và các ràng buộc đã mô hình hóa; không đồng nghĩa với phương án phù hợp nhất về mặt học vụ. Với mức CAO: khuyến nghị trao đổi với cố vấn học tập.

V2-005 có P(W1)=0.967, kỳ vọng trượt 3.54 môn, mức CAO. Các trường hợp best_effort, regulatory_conflict và risk_cap_exceeded vẫn được trình bày kèm cảnh báo riêng; không được diễn giải solver status thành xác nhận học vụ.

Bảng 6.1. ILP — độ nhạy scenario V2-002

Bảng 6.1 trình bày dữ liệu theo nguồn đã ghi.

| β | γ | λ | p* | Ngân sách | Tải chọn | Tín chỉ đạt kỳ vọng | Môn trượt kỳ vọng | Trạng thái |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.125 | 1.0 | 0.0 | 0.5 | 18 | 18 | 16.746332431277594 | 0.5571855860988464 | optimal |
| 0.125 | 1.0 | 0.1 | 0.5 | 18 | 18 | 16.746332431277594 | 0.5571855860988464 | optimal |
| 0.125 | 1.0 | 0.3 | 0.5 | 18 | 18 | 16.746332431277594 | 0.5571855860988464 | optimal |

Nguồn: SCENARIO / GIẢ ĐỊNH – reports/generated/ilp_sensitivity.csv.

Bảng các phương án cho chín hồ sơ và so sánh ngân sách dài được chuyển sang Phụ lục E, Bảng E.2–E.3. Ngân sách ở đó là kịch bản so sánh, không phải giới hạn chính thức. V2-001, V2-002, V2-004 có bộ ba phương án trùng hoàn toàn với hồ sơ khác do kế hoạch đã lưu có cùng học phần, tín chỉ và chỉ số đầu ra dưới các đầu vào/ràng buộc hiện hành. 6/9 hồ sơ có kết quả khác nhau ở ít nhất hai mức ngân sách (V2-001: 15, 18, 21; V2-002: 15, 18, 21; V2-003: 12, 15, 18; V2-004: 15, 18, 21; V2-006: 15, 18, 21; V2-009: 15, 18, 21). Các giá trị giống nhau khi ngân sách tăng chỉ phản ánh kết quả artifact hiện có.

## CHƯƠNG 7. MÔ PHỎNG MONTE CARLO

### 7.1 Thiết kế mô phỏng

Các bảng ở chương này chỉ đọc artifact Monte Carlo đã có; không chạy mô phỏng lại. Nhãn đầu vào là SCENARIO / GIẢ ĐỊNH; N mỗi tổ hợp được đọc từ mc_results.csv (1000 lượt). Seed được lưu: UNKNOWN.

Bảng 7.1. Tóm tắt Monte Carlo theo λ và chính sách

Bảng 7.1 trình bày dữ liệu theo nguồn đã ghi.

| λ | Chính sách | P(tốt nghiệp ≤8 kỳ) | P(tốt nghiệp ≤16 kỳ) | Kỳ tốt nghiệp TB | Môn trượt kỳ vọng |
| --- | --- | --- | --- | --- | --- |
| 0 | ILP-matched | 0.410 | 0.888 | 9.760 | 4.048 |
| 0 | ILP-fixed | 0.282 | 0.887 | 10.171 | 4.062 |
| 0 | B1 | 0.542 | 0.888 | 9.137 | 4.465 |
| 0 | B2 | 0.534 | 0.887 | 9.218 | 4.463 |
| 0 | B3 | 0.111 | 0.881 | 11.072 | 4.345 |
| 0.1 | ILP-matched | 0.282 | 0.887 | 10.171 | 4.062 |
| 0.1 | ILP-fixed | 0.282 | 0.887 | 10.171 | 4.062 |
| 0.1 | B1 | 0.242 | 0.837 | 10.495 | 11.580 |
| 0.1 | B2 | 0.206 | 0.799 | 10.807 | 11.710 |
| 0.1 | B3 | 0.111 | 0.881 | 11.072 | 4.345 |
| 0.3 | ILP-matched | 0.282 | 0.887 | 10.171 | 4.062 |
| 0.3 | ILP-fixed | 0.282 | 0.887 | 10.171 | 4.062 |
| 0.3 | B1 | 0.114 | 0.508 | 13.139 | 17.700 |
| 0.3 | B2 | 0.112 | 0.415 | 13.567 | 16.698 |
| 0.3 | B3 | 0.111 | 0.881 | 11.072 | 4.345 |

Nguồn: SCENARIO / GIẢ ĐỊNH, trung bình ngang trọng số từ mc_results.csv; không phải ước lượng NTU.

### 7.2 Vì sao kết quả thay đổi theo λ

Trong mô hình, λ nhân với g_load; hàm phạt chỉ kích hoạt khi units(L) vượt 6. Bảng 7.2 đối chiếu tín chỉ L với ngưỡng và mức phạt; Bảng 7.3 cho thấy tải tín chỉ trung bình theo chính sách và λ. B1/B2 có hồ sơ vượt ngưỡng, trong khi ILP-matched nằm trong vùng không phạt tại λ=0,1 và 0,3, nên chỉ số ILP-matched giữ nguyên giữa hai mức λ trong artifact. Đây là hệ quả của giả định hàm mục tiêu, không phải bằng chứng thực nghiệm.

Bảng 7.2. Tải tín chỉ, units(L) và g_load theo λ

Bảng 7.2 trình bày dữ liệu theo nguồn đã ghi.

| λ | L tín chỉ | Mean credits NW | units(L) | g_load | Bị phạt |
| --- | --- | --- | --- | --- | --- |
| 0.1 | 15 | 2.8261 | 5 | 1.0000 | Không |
| 0.1 | 18 | 2.8261 | 6 | 1.0000 | Không |
| 0.1 | 21 | 2.8261 | 7 | 0.9048 | Có |
| 0.1 | 24 | 2.8261 | 8 | 0.8187 | Có |
| 0.3 | 15 | 2.8261 | 5 | 1.0000 | Không |
| 0.3 | 18 | 2.8261 | 6 | 1.0000 | Không |
| 0.3 | 21 | 2.8261 | 7 | 0.7408 | Có |
| 0.3 | 24 | 2.8261 | 8 | 0.5488 | Có |

Nguồn: mc_explanations.json; quy tắc units(L) trong config/optimizer_scenario_v2.yaml.

Bảng 7.3. Tín chỉ trung bình mỗi kỳ theo chính sách và λ

Bảng 7.3 trình bày dữ liệu theo nguồn đã ghi.

| Chính sách | λ | Tín chỉ/kỳ trung bình | Số hồ sơ | Nhãn nguồn |
| --- | --- | --- | --- | --- |
| ILP-matched | 0.1 | 11.3743 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| B1 | 0.1 | 14.8842 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| B2 | 0.1 | 15.3306 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| B3 | 0.1 | 10.1403 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| ILP-matched | 0.3 | 11.3743 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| B1 | 0.3 | 16.2731 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| B2 | 0.3 | 17.1556 | 9 | GIẢ ĐỊNH (Monte Carlo) |
| B3 | 0.3 | 10.1403 | 9 | GIẢ ĐỊNH (Monte Carlo) |

Nguồn: mc_explanations.json; kết quả mô phỏng SCENARIO / GIẢ ĐỊNH.

Mean credits NW=2.8261; largest integer load without penalty=18 credits. Bảng 7.2 cho thấy tải L=15/18 nằm dưới ngưỡng, còn L=21/24 vượt ngưỡng theo cấu hình.

Trong mc_profile_metrics.csv, selected_load_mean lớn nhất của ILP-matched là 14.873 ở λ=0,1 và 14.873 ở λ=0,3; đều dưới ngưỡng 18 tín chỉ tương ứng units(L)=6. Với B1/B2, các giá trị lớn nhất giữa hồ sơ lần lượt là 20.519/21.843 ở λ=0,1 và 21.303/22.139 ở λ=0,3; các tải vượt ngưỡng chịu phạt trong mô hình. Vì vậy thay đổi kết quả theo λ phụ thuộc giả định phạt tải, không phải bằng chứng thực nghiệm.

### 7.3 Vì sao ILP không luôn tốt hơn B1/B2

Ở λ=0, P(tốt nghiệp ≤8 kỳ) của ILP-matched là 0.410, so với 0.542 của B1 và 0.534 của B2; số môn trượt kỳ vọng tương ứng là 4.048, 4.465 và 4.463. ILP-matched có xác suất tốt nghiệp đúng hạn thấp hơn nhưng ít lượt trượt kỳ vọng hơn; vì vậy thứ hạng phụ thuộc chỉ tiêu. Lợi thế quan sát được tại λ>0 phụ thuộc giả định phạt tải; phân tích REAL (UCI-697), mục C.2, không xác nhận giả định quan hệ tải-phạt này.

### 7.4 Những yếu tố chưa được mô phỏng

Chưa mô phỏng học kỳ hè, điều kiện mở lớp, học cải thiện, W3/W4, chuỗi điểm thật (dùng điểm đại diện 7,0/4,0), tương quan giữa các môn (giả định độc lập), hazard bỏ học tường minh và biến động chuẩn đầu ra (giả định đã đạt). M3′ là proxy từ dữ liệu Bồ Đào Nha, xác suất từng môn độc lập và không có hệ số độ khó; không cộng hazard dropout lần hai.

### 7.5 Kết quả theo hồ sơ (V2-001, V2-003)

Bảng 7.4 trình bày KTC ghép cặp và Bảng 7.5 nhãn Pareto cho V2-001/V2-003 tại λ=0 và 0,1. Nhãn Pareto phụ thuộc λ và bộ chỉ tiêu; các phân loại cặp không phải kết luận tổng thể cho mọi mục tiêu.

Bảng 7.4. KTC ghép cặp của V2-001/V2-003, λ=0 và λ=0.1

Bảng 7.4 trình bày dữ liệu theo nguồn đã ghi.

| student_id | comparison | lambda | diff_p_graduated_on_time | ci_p_graduated_on_time_lower | ci_p_graduated_on_time_upper | diff_expected_failed_courses | ci_expected_failed_courses_lower | ci_expected_failed_courses_upper |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V2-001 | ILP-matched - B1 | 0.0 | -0.247 | -0.278 | -0.214975 | -0.052 | -0.1950249999999999 | 0.0840249999999999 |
| V2-001 | ILP-matched - B2 | 0.0 | -0.232 | -0.265 | -0.199 | -0.099 | -0.228 | 0.0290499999999999 |
| V2-003 | ILP-matched - B1 | 0.0 | -0.1 | -0.1220249999999999 | -0.079 | -0.003 | -0.2180249999999999 | 0.2050249999999999 |
| V2-003 | ILP-matched - B2 | 0.0 | -0.081 | -0.103 | -0.06 | -0.18 | -0.382025 | 0.0340499999999999 |
| V2-001 | ILP-matched - B1 | 0.1 | 0.07 | 0.031 | 0.107 | -13.339 | -13.61605 | -13.064975 |
| V2-001 | ILP-matched - B2 | 0.1 | 0.137 | 0.102 | 0.171 | -13.313 | -13.572025 | -13.038975 |
| V2-003 | ILP-matched - B1 | 0.1 | -0.002 | -0.008 | 0.003 | -9.198 | -9.504 | -8.8949 |
| V2-003 | ILP-matched - B2 | 0.1 | 0.002 | -0.0010249999999999 | 0.006 | -9.136 | -9.482075 | -8.817874999999999 |

Nguồn: SCENARIO / GIẢ ĐỊNH, mc_pairwise.csv; cột KTC là bootstrap ghép cặp đã lưu.

Bảng 7.5. Nhãn Pareto V2-001/V2-003, λ=0 và λ=0.1

Bảng 7.5 trình bày dữ liệu theo nguồn đã ghi.

| student_id | policy_a | policy_b | lambda | dominance |
| --- | --- | --- | --- | --- |
| V2-001 | ILP-matched | B1 | 0.0 | ILP bị trội trong cặp |
| V2-001 | ILP-matched | B2 | 0.0 | ILP bị trội trong cặp |
| V2-001 | ILP-matched | B3 | 0.0 | ILP không bị trội trong cặp |
| V2-001 | ILP-matched | ILP-fixed | 0.0 | ILP không bị trội trong cặp |
| V2-003 | ILP-matched | B1 | 0.0 | ILP bị trội trong cặp |
| V2-003 | ILP-matched | B2 | 0.0 | ILP bị trội trong cặp |
| V2-003 | ILP-matched | B3 | 0.0 | ILP không bị trội trong cặp |
| V2-003 | ILP-matched | ILP-fixed | 0.0 | ILP không bị trội trong cặp |
| V2-001 | ILP-matched | B1 | 0.1 | ILP không bị trội trong cặp |
| V2-001 | ILP-matched | B2 | 0.1 | ILP không bị trội trong cặp |
| V2-001 | ILP-matched | B3 | 0.1 | ILP không bị trội trong cặp |
| V2-001 | ILP-matched | ILP-fixed | 0.1 | chưa phân biệt |
| V2-003 | ILP-matched | B1 | 0.1 | ILP không bị trội trong cặp |
| V2-003 | ILP-matched | B2 | 0.1 | ILP không bị trội trong cặp |
| V2-003 | ILP-matched | B3 | 0.1 | ILP không bị trội trong cặp |
| V2-003 | ILP-matched | ILP-fixed | 0.1 | chưa phân biệt |

Nguồn: SCENARIO / GIẢ ĐỊNH, mc_pareto.csv. Nhãn Pareto là tên loại so sánh trong artifact, không phải kết luận tổng thể.

Hình 7.1. Phân phối kỳ tốt nghiệp theo chính sách

Nguồn: SCENARIO / GIẢ ĐỊNH – reports/figures/mc_graduation_distribution.png.

Hình 7.1: Phân phối kỳ tốt nghiệp theo 5 chính sách cho thấy khi tăng λ từ 0.0 lên 0.3, xác suất tốt nghiệp đúng hạn (≤8 kỳ) trung bình của B1 giảm từ 0.542 xuống 0.114, trong khi ILP-matched giữ mức 0.410 đến 0.282 với số môn trượt kỳ vọng tại λ=0.3 là 4.062 so với 17.700 ở B1. Các đường phân phối phản ánh sự dịch chuyển kỳ tốt nghiệp khi tải phạt hoặc rủi ro tăng. Đây là kết quả phân tích kịch bản GIẢ ĐỊNH/SCENARIO từ reports/generated/mc_results.csv, không phải bằng chứng hiệu quả thực tế trên sinh viên NTU.

Hình 7.2. Biên Pareto theo kịch bản mô phỏng

Nguồn: SCENARIO / GIẢ ĐỊNH – reports/figures/mc_pareto.png (nhãn Pareto phụ thuộc λ).

Hình 7.2: Biểu đồ Pareto đối chiếu mục tiêu đúng hạn và số môn trượt kỳ vọng trên 108 cặp so sánh ở 3 mức λ trong mc_pareto.csv: nhãn nghiêng về ILP trong 50 cặp, nghiêng về chính sách đối chiếu ở 12 cặp, đánh đổi ở 7 cặp và chưa phân biệt ở 39 cặp. Vị trí các điểm cho thấy ILP thường giảm số môn trượt khi λ > 0 nhưng đánh đổi tốc độ tích lũy tín chỉ ở một số hồ sơ. Toàn bộ nhãn Pareto thuộc kịch bản GIẢ ĐỊNH/SCENARIO phụ thuộc cấu hình λ và giả định xác suất.

### 7.6 Kiểm tra tái tạo và độ tin cậy

Phạm vi tái tạo được giới hạn; không có code_hash trong artifact.

Tái tạo bổ sung V2-003/ILP-matched, λ=0,3 chưa hoàn tất trong giới hạn 10 phút; theo chỉ dẫn đã thử fallback λ=0,1 nhưng lần đó cũng chưa hoàn tất trong giới hạn. Không có kết quả đối chiếu cho cả hai lần chạy.

Với V2-005/B1, mô phỏng đã ghi kết quả nhưng hậu xử lý phát sinh `KeyError`; thông báo lỗi nguyên văn không được lưu. Đối chiếu được thực hiện trên `reports/generated/V2-005_B1_results.csv` và `reports/generated/V2-005_B1_grad_hist.csv` đã có trước khi hậu xử lý lỗi, so với các dòng tương ứng trong `mc_results.csv` và `mc_grad_hist.csv`: 109/109 cột kết quả (101 cột số trong V2-005) và 1/1 dòng histogram khớp theo tiêu chí đã duyệt; `source_label` là khác biệt metadata.

Kết quả là phân tích kịch bản theo giả định; không phải bằng chứng hiệu quả với sinh viên NTU.

## PHỤ LỤC A. PHẢN HỒI TỪNG GÓP Ý

Bảng A.1. Ma trận góp ý, thay đổi, vị trí và bằng chứng

Bảng A.1 trình bày dữ liệu theo nguồn đã ghi.

| Nhóm góp ý | Thay đổi đã làm | Vị trí (chương/tệp) | Bằng chứng |
| --- | --- | --- | --- |
| Dữ liệu CTĐT và quy chế | Phân biệt REAL, OFFICIAL, SCENARIO và GIẢ ĐỊNH; ghi HP0xx là mã nội bộ, quan hệ tiên quyết chưa xác nhận đầy đủ, lịch mở môn chẵn/lẻ là giả định suy từ CTĐT; trường thiếu giữ UNKNOWN/source=NOT_FOUND. | Chương 3, Phụ lục E; `docs/course_code_provenance.md`; `config/program_official.yaml`; `config/credit_rules_official.yaml` | `reports/generated/curriculum_validation.json`: 13 kiểm tra, 10 PASS, 3 WARN, 0 FAIL; PDF CTĐT/QĐ được ghi rõ là chưa có trong repository và cần nhóm cung cấp để xác minh độc lập. |
| Mô hình ML tại T1 | Giữ phạm vi sau HK1/trước đăng ký HK2; tách train/validation/test, chỉ dùng holdout đã lưu làm kết quả chính; nêu validation lạc quan khi chọn mô hình/ngưỡng, KTC bootstrap, Enrolled, đồ thị test/validation và giới hạn SHAP. | Chương 5; `docs/ml_protocol.md`; `reports/generated/model_comparison.csv`; `reports/generated/ml_validation_bootstrap_ci.json` | `reports/generated/test_evaluation.json`: holdout được đánh giá một lần; chia tập 2654/885/885; dữ liệu REAL (UCI-697), chưa kiểm định trên sinh viên NTU. |
| ILP, quy tắc và phương án | Trình bày ba nhãn phương án, mức cảnh báo riêng solver, ghi chú bắt buộc về `optimal`, khuyến nghị cố vấn với mức CAO; g_load dùng tín chỉ thực chọn; cập nhật so sánh ngân sách; xử lý lặp lọc môn song hành và kiểm thử hồi quy. | Chương 4 và 6, Phụ lục E; `core/rules.py`; `core/optimizer.py`; `tests/test_core_rules.py`; `reports/generated/plans_by_student.csv`; `reports/generated/plans_by_budget.csv` | Hồ sơ SCENARIO và bảng nguồn được giữ nguyên; V2-001/002/004 trùng bộ ba đầu ra theo artifact; best_effort luôn kèm cảnh báo và khuyến nghị cố vấn. |
| Monte Carlo, giao diện, kiểm thử và bàn giao | Chia Chương 7 thành sáu mục; giải thích độ nhạy λ, KTC/Pareto tại λ=0 và 0,1, giới hạn mô phỏng; ghi rõ tái tạo chưa hoàn tất và đối chiếu V2-005/B1; đưa ảnh chụp giao diện thật; thống nhất một báo cáo và gói dist. | Chương 7–9, Phụ lục E; `demo_media/README.md`; `reports/generated/pytest_summary.txt`; `README.md`; `HANDOFF.md`; `deliverables.md`; `dist/` | `reports/generated/mc_results.csv`, `mc_pairwise.csv`, `mc_pareto.csv`, `final_mc_reproduction.md`; ảnh thật; kết quả pytest, health, consistency và liên kết được ghi trong `reports/generated/final_dist_validation.md`. |

Nguồn: reports/generated/final_requirements_matrix.md; bảng được dựng trực tiếp từ nguồn.
