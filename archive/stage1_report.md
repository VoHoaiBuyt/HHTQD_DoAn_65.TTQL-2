# Báo cáo giai đoạn 1 — khảo sát, thiết kế và kế hoạch

> **Thông báo trạng thái:** Đây là báo cáo exploratory lịch sử, được viết trước
> khi nạp lại CTĐT OFFICIAL và kiểm toán scenario v1. Các mô tả cũ về catalogue
> hoặc persona SIMULATED, số liệu ILP/persona, cùng đường dẫn lệnh không phải kết
> quả của Phần 1 hiện tại. Không dùng chúng cho kết quả cuối; xem `HANDOFF.md`,
> `reports/generated/curriculum_validation.json` và
> `reports/generated/scenario_v1_defects.json` để biết trạng thái đã kiểm chứng.

> **Phạm vi tại thời điểm soạn bản lịch sử này:** khảo sát dữ liệu, thiết kế hệ thống và kế hoạch giai đoạn 2. Mô hình và bộ giải ở đây chỉ exploratory/prototype; không huấn luyện mô hình cuối, không triển khai giao diện và không coi persona là bằng chứng hiệu quả. Các nhận định này không mô tả trạng thái dữ liệu của Phần 1 hiện tại.

## Tóm tắt điều hành

Đề xuất đề tài “Hệ hỗ trợ ra quyết định cảnh báo rủi ro học tập và tối ưu hóa lộ trình tích lũy tín chỉ sinh viên” theo kiến trúc nối tiếp: (1) ML cảnh báo nguy cơ bỏ học từ đặc trưng có sẵn tại T1, (2) rule engine cảnh báo học vụ và xác định môn đủ điều kiện, (3) tối ưu kế hoạch học phần có ràng buộc tín chỉ/tiên quyết/rủi ro, (4) mô phỏng nhiều kỳ và so sánh với phương án đăng ký thông thường. ML cảnh báo bỏ học và cảnh báo học vụ theo GPA/tiến độ là hai bài toán riêng.

Khảo sát **REAL (UCI-697)** có 4.424 sinh viên, 37 thuộc tính, không thiếu/trùng toàn dòng. Catalogue CNTT hiện dùng nội dung mục 7.1 của PDF `210_CNTT.pdf` (130 tín chỉ theo từng lộ trình); tiến độ/hồ sơ sinh viên trong `data/processed/` vẫn là dữ liệu mô phỏng. Các kết quả exploratory UCI không kiểm chứng độ chính xác ở NTU.

Tải HK2 trong dữ liệu quan sát không cho bằng chứng nhất quán về quan hệ giảm pass-rate trong cùng tầng HK1. Vì vậy không dùng counterfactual đổi số môn đăng ký làm phương pháp quyết định. Baseline pass-rate đề xuất là M3' theo tầng năng lực HK1, gộp mọi mức tải; ảnh hưởng tải/độ khó/học lại chỉ hiển thị như tham số **GIẢ ĐỊNH kịch bản** độ nhạy. Prototype PuLP/HiGHS xác nhận mô hình nhỏ có nghiệm khác nhau theo persona/ngân sách, đồng thời cho thấy ràng buộc rủi ro có thể làm một số persona không khả thi—đây là thông tin để rà config, không phải hiệu quả hệ thống.

Nhóm cần cô góp ý về nhãn/mốc T1, CTĐT và quy chế chính thức, cách dùng P(Dropout) để điều chỉnh tải, giả định mô phỏng và tiêu chí so sánh. Báo cáo không khẳng định mô hình tốt hơn baseline; việc đó chỉ được đánh giá ở giai đoạn 2 bằng dữ liệu/tiêu chí được duyệt trước.

## A. Khảo sát dữ liệu UCI-697

### A.1. Nguồn và chất lượng

- **REAL (UCI-697):** [Predict Students' Dropout and Academic Success](https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success), UCI ID 697.
- Tệp raw giữ nguyên tại `data/raw/uci_697/data.csv`; SHA-256 khớp tệp tải từ UCI: `3EF126DE5CEFFF26EB11FBB4237F1A1401CB64B488E2F1D598C23CEDEB4C45AE`.
- Kết quả EDA: **4.424 dòng × 37 thuộc tính**, không có giá trị thiếu, không có dòng trùng hoàn toàn; pandas đọc 29 cột số nguyên, 7 cột số thực và một cột chuỗi (`Target`).
- Phân phối Target **REAL (UCI-697)**:

| Target | Số sinh viên | Tỷ lệ |
|---|---:|---:|
| Dropout | 1.421 | 32,12% |
| Enrolled | 794 | 17,95% |
| Graduate | 2.209 | 49,93% |

Target được quan sát cuối cùng, không phải nhãn thời gian thực độc lập. Đề xuất tạm bài toán 3 lớp; `Dropout` là lớp cảnh báo ưu tiên recall. Chưa chốt việc xem `Enrolled` là chưa hoàn tất hay trạng thái độc lập.

### A.2. Thời điểm có sẵn và leakage

Từ điển thuộc tính Stage 1 được lưu trữ tại `archive/data_dictionary.csv`, gồm tên, kiểu, ý nghĩa, nhóm, `available_at`, cờ leakage và lý do. Feature cơ sở ở mốc **T1: cuối HK1, trước đăng ký HK2** chỉ nhận thuộc tính `T0` hoặc `T1_known`.

- Đầu vào/tuyển sinh: nhân khẩu học, phương thức/ngành tuyển sinh, học vấn đầu vào, điểm xét tuyển.
- Học thuật HK1: credited, enrolled, evaluations, approved, grade, without evaluations; quan sát sau khi có kết quả HK1.
- HK2: credited/enrolled là `T1_decision`, chỉ dùng phân tích phương án; evaluations/approved/grade/without evaluations là post-outcome và không vào feature T1.
- `Debtor`, `Tuition fees up to date`, `Scholarship holder`, `Unemployment rate`, `Inflation rate`, `GDP`: timestamp theo thuộc tính chưa xác minh, loại khỏi feature cơ sở.

Một số tương quan mô tả Pearson với Dropout (không nhân quả) **REAL (UCI-697)**:

| Thuộc tính | r | Quyết định thời điểm |
|---|---:|---|
| HK2 grade | -0,5718 | hậu nghiệm, leakage tại T1 |
| HK2 approved | -0,5695 | hậu nghiệm, leakage tại T1 |
| HK1 grade | -0,4807 | dùng sau HK1 |
| HK1 approved | -0,4791 | dùng sau HK1 |
| Age at enrollment | 0,2542 | có ở đầu vào |
| Debtor | 0,2294 | timestamp chưa xác minh, loại khỏi cơ sở |

UCI có sáu chỉ số học thuật cho mỗi học kỳ: curricular units credited/enrolled/evaluations/approved/grade/without evaluations. Trung bình `enrolled` HK1 của Graduate là 6,670 so với 5,821 của Dropout **(REAL)**; đây chỉ là tương quan. Không suy diễn đăng ký nhiều gây giảm hoặc tăng nguy cơ. Số unit UCI không phải tín chỉ NTU.

### A.3. Kết quả EDA và đề xuất nhãn

EDA cho thấy Target mất cân bằng; cần báo cáo precision, recall, F1 lớp Dropout và confusion matrix, không dùng accuracy làm tiêu chí duy nhất. XGBoost/RF/LR là ứng viên đánh giá ở giai đoạn 2; hiện chỉ chạy Logistic Regression/RF exploratory phục vụ C. Không huấn luyện mô hình cuối. Cần xác nhận nhãn ba lớp/ý nghĩa `Enrolled` và mốc T1 ở câu hỏi cuối báo cáo.

## B. Cấu trúc dữ liệu cho tối ưu hóa tín chỉ

### B.1. Nguồn và schema

Catalogue học phần được nhập từ PDF CTĐT CNTT chuẩn `210_CNTT.pdf`, mục 7.1, trong `data/processed/`. Tiến độ và hồ sơ persona tiếp tục là **SIMULATED**; tiến độ hiện chỉ dựng trên các học phần bắt buộc chung, không giả định chọn chuyên ngành. Schema:

| Bảng | Trường trọng yếu | Nhãn |
|---|---|---|
| `courses` | `course_id`, `course_name`, `credits`, `planned_semester`, `course_type`, `offered_semesters`, `group`, `source_label` | PDF mục 7.1 |
| `prerequisites` | `course_id`, `prerequisite_id`, `type` (`tiên quyết`/`học trước`/`song hành`), `source_label` | PDF mục 7.1 |
| `student_progress` | `student_id`, `course_id`, `status`, `grade_10`, `attempt_count`, `semester_taken` | SIMULATED |
| `student_profile` | `student_id`, feature T0/T1-known, kỳ hiện tại, GPA, tín chỉ đạt/còn thiếu, số môn nợ | SIMULATED/REAL-derived feature template |

Khóa ghép tiến độ là (`student_id`,`course_id`); mã môn và sinh viên là khóa ngoại. Trạng thái gồm completed/in_progress/failed/not_taken. Dữ liệu UCI không nối record cá nhân thật với course_id.

### B.2. CTĐT nháp và kiểm tra

Catalogue có 101 dòng gồm học phần chung, lựa chọn thay thế, ba nhánh chuyên ngành và hai phương án tốt nghiệp; các phương án thay thế không cộng dồn. Mỗi lộ trình có 130 tín chỉ, gồm 110 tín chỉ bắt buộc (chọn một phương án tốt nghiệp) và 20 tín chỉ tự chọn. Phân bổ theo kỳ của lộ trình đã chọn là HK1–HK8: 17, 17, 19, 18, 16, 18, 15, 10. Các chi tiết phụ thuộc PDF; hồ sơ sinh viên vẫn là mô phỏng.

### B.3. Ánh xạ và persona

UCI curricular unit chỉ được coi xấp xỉ một học phần khi đếm; không suy tín chỉ/môn. Các quan hệ tiên quyết được trích từ mục 7.1; các dòng tiến độ là mô phỏng, hiện chỉ bao gồm học phần bắt buộc chung. Điểm UCI 0–20 chia 2 thành 0–10 chỉ để tạo feature ML fixture; **không dùng để suy ngưỡng đạt NTU**. Mã ngành/nhân khẩu học trong persona chỉ thử schema.

Persona được tạo từ medoid vector feature REAL thuộc từng tầng HK1 rồi gắn nhãn SIMULATED; S002 được kiểm tra thuộc tầng Trung bình. Các ca học lại, môn chặn chuỗi, gần tốt nghiệp và hoàn tất tín chỉ dùng để sanity-check rule engine. Các persona không đủ môn để lấp tải được giữ nguyên, không thêm môn trái prerequisite. Điểm và lịch sử học vẫn là dữ liệu mô phỏng.

### B.4. Hạn chế: domain shift

Mô hình/quan sát học từ **REAL (UCI-697)** tại các cơ sở Bồ Đào Nha; hồ sơ và chương trình hiện tại là **SIMULATED**. Áp mô hình UCI lên persona chỉ kiểm tra luồng dữ liệu, thứ tự tương đối và logic hệ thống, **không** xác nhận độ chính xác cho NTU. Cần dữ liệu NTU được phê duyệt và đánh giá độc lập trước khi dùng thực tế.

## C. Chuyển rủi ro sang phương án đăng ký

### C.0. Đối soát sửa đổi C (I.1–I.7)

| Mục | Trạng thái | Bằng chứng |
|---|---|---|
| I.1 Validator CTĐT | Đã làm | Chạy lại `python src/data/validate_curriculum.py`; block PASS nguyên văn 14 dòng tại B.2 và trong `reports/curriculum_validation.txt`. |
| I.2 M1 vs C.3 | Đã làm | M1 binary OR `enrolled_2`=1,314506; M1 3-class hiệu dụng=1,161026; C.3 hồi quy quan sát kiểm soát=1,000469. Khác mô hình/feature set/estimand; M1 chỉ diagnostic, không nhân quả. |
| I.3 Calibration pass-rate | Đã làm | Bảng 10 decile holdout ở C.1; raw RF MAE/RMSE 0,124046/0,193556, isotonic 0,124389/0,195836; không áp dụng isotonic. |
| I.4 M3' | Đã làm | Baseline gộp mọi tải theo HK1: Thấp 0,248377; Trung bình 0,779404; Cao 0,931902. M3 theo band tải chỉ minh họa selection bias (Trung bình: 0,841799 ở 8+ so với 0,755601 ở 1–5). |
| I.5 Quy đổi units | Đã làm | `credits_to_curricular_units` dùng half-up `floor(x+0.5)`, nên 4,5→5, đơn điệu; chi tiết ở [plan_risk.py](../src/optimize/plan_risk.py) và config. |
| I.6 `enrolled_2=0` | Đã làm | 180 sinh viên không được gán pass-rate=0 hay mặc định là Dropout; tỷ lệ Dropout quan sát trong nhóm là 42,7778% **REAL**. |
| I.7 Persona | Đã làm | [generate_simulated_data_legacy.py](../archive/generate_simulated_data_legacy.py) lấy medoid feature vector thực trong mỗi một phần ba tầng năng lực HK1; kiểm tra lại tầng trước khi xuất. Nội dung này chỉ là lịch sử exploratory và không phải dữ liệu scenario cuối. |

Chi tiết hiệu chuẩn theo decile, gồm dự báo/trung bình thực tế, được trình bày ở C.1; bảng phân tầng tầng cảnh báo/PPV và ngưỡng restriction hiệu chuẩn được bổ sung ở D.1. Các persona mang nhãn **SIMULATED**, không phải hồ sơ cá nhân thật.

### C.1. Hai mục tiêu riêng và baseline exploratory

1. `P(Dropout | T1)`: nguy cơ bỏ học cấp sinh viên, dự báo bằng feature T0+T1-known; cảnh báo/ràng buộc ở rule engine, không nhân trực tiếp vào xác suất đạt môn.
2. `pass_rate_2 = approved_2nd / enrolled_2nd`: tỷ lệ đạt HK2 cấp sinh viên, nhãn hậu nghiệm dùng làm nền xác suất đạt môn. Chỉ tính nếu enrollment >0. Nhóm `enrolled_2=0` (180 sinh viên) không bị coi là Dropout; tỷ lệ Dropout trong nhóm là 42,7778% **(REAL)**. `without evaluations` vẫn ở mẫu số enrollment, chưa tính approved; tổng 665 unit **(REAL)** được theo dõi riêng.

Logistic Regression 3 lớp dùng 24 feature; train/test stratified 80/20, seed `20261105`, Stratified 5-fold CV trên train. RF pass-rate dùng KFold 5-fold và holdout riêng. Kết quả **REAL (UCI-697), exploratory**:

| Chỉ số | Giá trị |
|---|---:|
| Dropout CV accuracy / macro-F1 / F1 | 0,714046 / 0,616392 / 0,709335 |
| Dropout holdout precision / recall / F1 | 0,701031 / 0,718310 / 0,709565 |
| Dropout holdout Brier one-vs-rest | 0,121147 |
| Confusion matrix, hàng/cột [Dropout, Enrolled, Graduate] | `[[204,20,60],[48,46,65],[39,24,379]]` |
| pass-rate CV MAE / RMSE | 0,120090 / 0,183969 |
| pass-rate holdout MAE / RMSE | 0,124046 / 0,193556 |

Calibration theo decile holdout **REAL (UCI-697)**, gồm cỡ mẫu, trung bình dự báo và thực tế:

| Decile | n | Dự báo trung bình | Pass rate thực tế |
|---:|---:|---:|---:|
| 0 | 85 | 0,009787 | 0,012381 |
| 1 | 85 | 0,208263 | 0,237507 |
| 2 | 85 | 0,518382 | 0,531022 |
| 3 | 85 | 0,709199 | 0,673686 |
| 4 | 85 | 0,792052 | 0,788403 |
| 5 | 84 | 0,844018 | 0,853117 |
| 6 | 85 | 0,876832 | 0,877344 |
| 7 | 85 | 0,917449 | 0,912353 |
| 8 | 85 | 0,954386 | 0,943961 |
| 9 | 85 | 0,982630 | 0,966373 |

Isotonic fit OOF train cho holdout MAE/RMSE 0,124389/0,195836, kém hơn RF thô 0,124046/0,193556; calibration decile MAE 0,015273 so với 0,012507. **Không hiệu chuẩn isotonic** cho pass-rate trong thử nghiệm này; chưa phải kết luận cuối.

### C.2. Kiểm định tải học REAL, không nhân quả

Năng lực nền phân tầng theo `approved_1st/enrolled_1st`; band tải HK2 là 1–5, 6–7, 8+ units. Bảng **REAL (UCI-697)**:

| Tầng HK1 | Tải HK2 | Sinh viên | Pass rate HK2 | Tỷ lệ Dropout |
|---|---:|---:|---:|---:|
| Thấp | 0 | 180 | không xác định | 0,427778 |
| Thấp | 1–5 | 578 | 0,286415 | 0,697232 |
| Thấp | 6–7 | 495 | 0,190445 | 0,828283 |
| Thấp | 8+ | 96 | 0,327546 | 0,729167 |
| Trung bình | 1–5 | 197 | 0,755601 | 0,213198 |
| Trung bình | 6–7 | 720 | 0,729621 | 0,275000 |
| Trung bình | 8+ | 430 | 0,841799 | 0,162791 |
| Cao | 1–5 | 307 | 0,915243 | 0,107492 |
| Cao | 6–7 | 1.002 | 0,914521 | 0,092814 |
| Cao | 8+ | 419 | 0,966438 | 0,059666 |

Hồi quy Logistic nhị phân mô tả Dropout, kiểm soát tỷ lệ đạt HK1, số môn HK1 đăng ký/đạt, điểm HK1 và tuổi, cho OR quan sát 1,000469/unit HK2. Mẫu hình trong tầng không đơn điệu; kết luận **(c) dữ liệu quan sát chưa đủ để kết luận tải cao làm giảm tỷ lệ đạt**. Không có ngẫu nhiên hóa, tải tự chọn/có thể bị buộc và còn nhiễu chưa đo; không diễn giải là nhân quả.

### C.3. M1 so với hồi quy C.2

M1 diagnostic có cùng feature set T0+T1-known + `enrolled_2`, cùng train/test split. Logistic nhị phân Dropout-vs-rest cho OR 1,314506/unit; mô hình 3 lớp tại vector đại diện cho OR hiệu dụng 1,161026/unit (P(Dropout) tăng 0,057021 khi 1 unit lên 0,238071 khi 12 units). C.3 quan sát cho OR 1,000469 nhưng dùng bộ kiểm soát nhỏ hơn và mô hình/estimand khác. Binary và softmax cũng khác dạng hàm; OR softmax hiệu dụng tính qua hai mức counterfactual, có thể ngoại suy. Do đó không chọn con số thuận lợi; M1 chỉ là diagnostic, **bị loại làm phương pháp chính** và không phải can thiệp nhân quả.

### C.4. Phương pháp chuyển sang xác suất từng môn

| Phương pháp | Giả định, ưu/nhược và kiểm chứng | Quyết định |
|---|---|---|
| M1: thay `enrolled_2` trong mô hình Dropout | T1_decision không phải feature đã quan sát; phản ánh liên hệ và ngoại suy, không nhận dạng tác động. Chiều counterfactual tăng Dropout; đối chiếu với phân tầng C.2, không dùng ra quyết định. | Loại làm chính. |
| M2: hai tầng tham số | `p_i=clip(p_student × f_difficulty(i) × g_load(plan) × r_retake(i),0,1)`. Factor độ khó từ median grade_10 theo nhóm SIMULATED / median chung, cắt quantile 10–90; fixture 0,9083–1,1597. `g_load=exp(−λ×max(0,units−6))`; `r_retake` lưới {0,9;1,0;1,1}. Dễ giải thích, nhưng môn/độ khó/tải không được UCI nhận dạng. | Độ nhạy; λ={0;0,1;0,3} và factor là **GIẢ ĐỊNH**, không ước lượng nhân quả. |
| M3: tầng HK1 × band tải | Tỷ lệ pooled REAL trong ô; tầng Trung bình 8+ là 0,841799 so với 1–5 là 0,755601. Có thể bị selection bias; không dùng làm baseline. | Chỉ minh chứng thiên lệch chọn tải. |
| M3': tầng HK1, gộp mọi band tải | `p_student=Σapproved_2/Σenrolled_2` trong tầng HK1; không đưa selection-by-load vào xác suất nền. | **Baseline chính**; hiệu ứng tải chỉ vào qua `g_load` của M2. |

M3' **REAL (UCI-697)**: Thấp 1.683/6.776=0,248377 (n=1.169 có enrollment); Trung bình 7.349/9.429=0,779404 (n=1.347); Cao 10.592/11.366=0,931902 (n=1.728). Nếu strata có dưới 30 sinh viên, gộp tầng kề theo Thấp–Trung bình–Cao; nếu vẫn không đạt mẫu trả “không ước lượng được”, không thay bằng 0. Đây là pooling exploratory, chưa kiểm chứng NTU.

M3' gồm cả sinh viên sau đó có Target=Dropout; đây là pass-rate quan sát của các unit đã đăng ký, không phải xác suất pass có điều kiện sống sót. Tính lại sau khi loại Dropout cho thấy tỷ lệ pass cao hơn, nhưng conditioning trên kết quả cuối kỳ tạo selection/survivorship bias:

| Tầng HK1 | M3' mọi Target | M3' chỉ Target≠Dropout | Mẫu non-Dropout có enrollment |
|---|---:|---:|---:|
| Thấp | 0,248377 | 0,564428 | 286 |
| Trung bình | 0,779404 | 0,833310 | 1.037 |
| Cao | 0,931902 | 0,946581 | 1.577 |

Đối chiếu **SIMULATED persona** (vector feature REAL-derived): S003/yếu có M3'=0,248377, rate tầng non-Dropout=0,564428 và RF dự báo cá thể=0,048941; S002/trung bình lần lượt 0,779404, 0,833310, 0,593345. Mức 0,7457 được nêu như ví dụ trước không tái lập được bằng phép tính hiện tại; không thay số để khớp ví dụ. RF là mô hình cá thể exploratory, còn M3' là pooling theo tầng; cả hai chịu domain shift. Mặc định dùng M3' làm baseline ổn định, không điều kiện hóa theo Dropout hậu nghiệm; RF và non-Dropout table chỉ là đối chiếu/độ nhạy. Chế độ mô phỏng hazard bỏ học, nếu dùng, tách riêng ở D.3.

### C.5. Đặc tả `plan_risk` và persona

`plan_risk(student_id, plan, p_student_pass, ...)` trả `p_pass_by_course`, `expected_credits_passed=Σcredits_i·p_i`, `expected_failed_courses=Σ(1−p_i)`, `prob_at_least_k_fail` (k=1,2), `plan_risk_index=100×(1−expected_credits_passed/Σcredits_i)` và tổng tín chỉ. `P(Dropout)` không phải đối số xác suất đạt môn. Xác suất ≥1/≥2 trượt hiện giả định độc lập; tương quan do năng lực chung là hạn chế.

Quy đổi **SIMULATED/GIẢ ĐỊNH**: `units_equivalent=total_credits/mean(course.credits)`; mean fixture 128/48=2,6667, nên 12/15/18 tín chỉ thành 4,5/5,625/6,75 curricular units. Làm tròn half-up `floor(x+0.5)` cho 5/6/7 (không dùng Python bankers rounding), đơn điệu theo tổng tín chỉ. Không suy ra tín chỉ UCI/NTU. Môn học lại dùng `r_retake` giả định {0,9;1,0;1,1}, mặc định 1,0 do không có dữ liệu outcome học lại.

Persona **SIMULATED** lấy feature medoid từ hồ sơ REAL theo tầng HK1. Heuristic subset-sum lũy tiến chọn plan lớn hơn bằng cách giữ các môn đã chọn ở budget trước, rồi bổ sung môn chưa học/chưa đạt hợp lịch mở/prerequisite; không dùng ILP:

| Persona / tầng HK1 REAL-derived | Budget | Tín chỉ thực chọn | M3' p_pass | Expected failures M3' |
|---|---:|---:|---:|---:|
| S001 / Cao | 12 / 15 / 18 | 12 / 14 / 18 | 0,931902 | 0,272391 / 0,340489 / 0,476685 |
| S002 / Trung bình | 12 / 15 / 18 | 12 / 14 / 18 | 0,779404 | 0,882384 / 1,102980 / 1,544172 |
| S003 / Thấp | 12 / 15 / 18 | 12 / 15 / 17 | 0,248377 | 3,006494 / 3,758117 / 4,509740 |
| S005 / Trung bình | 12 / 15 / 18 | 12 / 15 / 15 | 0,779404 | 1,102980 / 1,323576 / 1,323576 |

Tăng tải làm expected failures không giảm trong các nested plans; expected credits passed của persona yếu tăng chậm vì M3' gán nền chung theo tầng và không mô hình bão hòa. S004 chỉ lấp 14/16 ở ngân sách 15/18 do eligibility; S006 chỉ còn 2 tín chỉ; S008 đã đạt ngưỡng 128 tín chỉ. Không coi các persona là bằng chứng độ chính xác. Độ nhạy M2 của S003 ở plan 12 tín chỉ: lambda × difficulty × retake cho 3,758010–3,845897 expected failures; 0,462309–0,725971 expected credits; plan-risk 93,950238–96,147426 **(SIMULATED + GIẢ ĐỊNH, cực trị lưới, không phải CI)**.

## D. Thiết kế hệ thống và tối ưu hóa

### D.1. Tầng quy tắc và output

Rule engine tách hai loại quyết định:

- `academic_flags`: cảnh báo học vụ từ GPA, tín chỉ chậm tiến độ, môn chưa đạt; **không dùng ML**.
- `eligible_courses`: chưa đạt/chưa học, còn lượt học lại, được mở kỳ tới và thỏa quan hệ prerequisite. `tiên quyết` yêu cầu đã đạt; `học trước` yêu cầu đã học/đang học; `song hành` cho phép nếu học phần kia đã hoàn tất/đang học hoặc cùng được chọn. Được học vượt kỳ dự kiến nếu mở đúng kỳ và đủ prerequisite.
- `progress_stats`: tín chỉ tích lũy/còn thiếu, kỳ tối thiểu còn lại là max(cận dưới theo tín chỉ tối đa/kỳ, chuỗi prerequisite nghiêm ngặt dài nhất).
- `edge_case_flags`: đã đủ tín chỉ tốt nghiệp; không có môn đủ điều kiện; môn bắt buộc không mở kỳ tới; môn bắt buộc bị chặn bởi prerequisite.

**Cảnh báo ≠ hạn chế tải.** Hai ngưỡng warning được chọn trên 5-fold OOF train **REAL**, theo mục tiêu recall Dropout ≥0,98 và ≥0,90; giá trị 0,029362 và 0,138654, recall tương ứng 0,980651 và 0,900616. Phân bố và PPV trong các tầng warning:

| Tầng cảnh báo | Sinh viên | Tỷ lệ train OOF | Dropout thực tế | PPV trong tầng |
|---|---:|---:|---:|---:|
| Thấp | 450 | 12,72% | 4,89% | 4,89% |
| Trung bình | 1.166 | 32,95% | 7,80% | 7,80% |
| Cao | 1.923 | 54,34% | 53,25% | 53,25% |

Warning ưu tiên recall để hiển thị và đề nghị cố vấn; PPV của warning “Cao” chưa đủ để khóa tải. Restriction mềm riêng dùng P(Dropout) isotonic-calibrated OOF, ngưỡng đề xuất `P≥0,50`, chọn theo PPV mục tiêu ≥0,70 và ít nhất 30 mẫu. Độ nhạy **REAL, train OOF calibrated**: threshold 0,50 có n=866, PPV=0,809, recall=0,617; 0,65 có n=656, PPV=0,889, recall=0,513; 0,75 có n=574, PPV=0,915, recall=0,462. Trong nhóm 173 sinh viên có P trong ±0,02 quanh tỷ lệ nền 32,13%, **0** người vượt ngưỡng restriction 0,50. Isotonic và chọn ngưỡng cùng OOF nên có optimistic bias; phải xác nhận trên validation độc lập. Mọi cap tín chỉ 18/15/12 và Fmax 2/1,5/1 là khuyến nghị mềm mặc định `enforce_cap: false`, không phải quy chế. Cấu hình có thể bật hard cap nhưng chỉ sau duyệt; hiện kịch bản 12/15/18 không bị xóa theo tầng.

### D.2. Mô hình toán học

Đặc tả đầy đủ ở `docs/optimization_spec.md`. Với mỗi môn đủ điều kiện `i`, biến nhị phân `x_i∈{0,1}`; ràng buộc:

```text
C_min_used ≤ Σ c_i x_i ≤ C_scenario
x_i ≤ x_prerequisite          (chỉ quan hệ song hành chưa hoàn tất)
Σ (1 − p_i) x_i ≤ F_max(tầng cảnh báo) + slack
x_i = 1                       (môn bắt buộc học lại đang chặn chuỗi, nếu eligible)
slack ≥ 0
```

Hàm mục tiêu đề xuất:

```text
maximize Σ[c_i·p_i − γ·c_i·(1−p_i) + β·u_i]x_i − M·slack
Σ(1−p_i)x_i ≤ F_max(tầng cảnh báo) + slack
```

`u_i=Σ(c_j×δ^distance(i,j))` cho môn j phụ thuộc bắc cầu chưa đạt, `δ=0,5`; đơn vị là tín chỉ tương đương mở khóa. `c_i p_i` là tín chỉ đạt kỳ vọng; `c_i(1-p_i)` là tín chỉ học lại kỳ vọng; `u_i` là tín chỉ downstream mở khóa chiết khấu. Chọn `γ=1` theo quy tắc một tín chỉ trượt tương đương một tín chỉ chi phí học lại; `β=1/8` theo nghịch đảo khung 8 học kỳ fixture, là **GIẢ ĐỊNH**, không fit dữ liệu. Sensitivity β={0;0,125;0,25;0,5}, γ={0,5;1;2}. Fmax khác mục tiêu: nó giới hạn số môn trượt kỳ vọng, còn objective tính tổn thất theo tín chỉ; slack bị phạt 1000 tín chỉ tương đương/unit trong prototype. Trần tín chỉ chỉ bật cứng khi cấu hình được duyệt.

### D.3. Prototype và tính không suy biến

Prototype PuLP/HiGHS chạy trên 4 persona S001/S002/S003/S005 (feature medoid từ **REAL**, tiến độ/catalogue **SIMULATED**) độc lập theo ngân sách × λ. Bảng dưới ghi tín chỉ được chọn và expected failures theo thứ tự λ=0/0,1/0,3; “!” là cờ vượt Fmax mềm; kết quả **SIMULATED + GIẢ ĐỊNH, prototype**:

| Persona | Scenario | Tín chỉ chọn λ=0/0,1/0,3 | Expected failures λ=0/0,1/0,3 | Trạng thái λ=0/0,1/0,3 |
|---|---:|---|---|---|
| S001 | 12 | 12/12/12 | 0,018/0,018/0,018 | optimal/optimal/optimal |
| S001 | 15 | 15/15/15 | 0,086/0,086/0,086 | optimal/optimal/optimal |
| S001 | 18 | 18/18/18 | 0,200/0,795/1,919 | optimal/optimal/optimal |
| S002 | 12 | 12/12/12 | 0,785/0,785/0,785 | optimal/optimal/optimal |
| S002 | 15 | 14/14/14 | 1,000/1,000/1,000 | optimal/optimal/optimal |
| S002 | 18 | 14/12/12 | 1,000/1,105/1,629 | optimal/best_effort!/best_effort! |
| S003 | 12 | 12/12/12 | 2,980/2,980/2,980 | best_effort!/best_effort!/best_effort! |
| S003 | 15 | 12/12/12 | 2,980/2,980/2,980 | best_effort!/best_effort!/best_effort! |
| S003 | 18 | 12/12/12 | 2,980/3,077/3,245 | best_effort!/best_effort!/best_effort! |
| S005 | 12 | 12/12/12 | 0,900/0,900/0,900 | optimal/optimal/optimal |
| S005 | 15 | 13/13/13 | 0,944/0,944/0,944 | optimal/optimal/optimal |
| S005 | 18 | 13/12/12 | 0,944/1,290/1,963 | optimal/best_effort!/best_effort! |

Kịch bản thực sự khác ở S001/S002/S005 theo tải và λ; S003 chọn 12 ở mọi ngân sách vì Fmax mềm bị vượt đáng kể và slack bị phạt lớn. Không có trần tầng cứng; S003 vẫn có phương án cụ thể thay vì infeasible. Kịch bản 12/15 đôi khi không đổi theo λ vì số curricular units quy đổi không vượt median REAL 6. Bảng recommendation chọn trong các kịch bản theo tiêu chí mềm; CSV đầy đủ (kể cả 3 λ/persona) ở `reports/generated/ilp_prototype_scenarios.csv` và recommendation ở `ilp_scenario_recommendations.csv`. Khi không có phương án đồng thời đạt Fmax và cận kỳ tối thiểu, chọn best effort và khuyên gặp cố vấn; tầng cảnh báo không xóa scenario.

Với S003, λ=0,1, kế hoạch 12 tín chỉ `IT501, IT502, IT503, IT504` có expected failures 2,980257 so với Fmax=1; `risk_cap_slack=1,980257`, `risk_cap_exceeded=true`, `reduced_load_advised=false`, `status=best_effort`. Hành động: trao đổi cố vấn về tải và học lại. Lượt giảm Cmin chưa kích hoạt trong ca này vì slack Fmax đã cho solver tạo nghiệm; test riêng kiểm tra hard cap + Cmin=12 không khả thi thì retry Cmin_relaxed=6 tạo kế hoạch giảm tải và cờ tương ứng.

Ablation toy **SIMULATED/GIẢ ĐỊNH** xác nhận objective mở khóa có thể đổi nghiệm và Fmax/penalty slack ảnh hưởng lựa chọn. Unit test bài toán 4 môn giải tay có nghiệm `{A,D}`, objective 4,5 tín chỉ tương đương; toàn bộ tests được chạy lại bằng lệnh trong HANDOFF. Đây là kiểm tra công thức, không chứng minh hiệu quả nghiệp vụ.

### D.4. Mô phỏng nhiều kỳ và đối chứng — thiết kế giai đoạn 2

Chưa chạy Monte Carlo nhiều kỳ/đối chứng hoàn chỉnh. Thiết kế **SIMULATED/GIẢ ĐỊNH**, N≥1.000, seed 20261105, λ={0;0,1;0,3}:

1. **Có điều kiện không bỏ học (mặc định):** chỉ mô phỏng pass/fail theo Bernoulli(p_i), không dùng P(Dropout); môn trượt trở lại trạng thái học lại. Mọi xác suất hoàn thành đúng hạn phải ghi rõ chế độ này.
2. **Có hazard bỏ học (độ nhạy):** nếu có P(Dropout) tích lũy cho H kỳ còn lại, giả định hazard hằng kỳ `h=1−(1−P(Dropout))^(1/H)`; mỗi kỳ mô phỏng dropout độc lập với kết quả môn và dừng sinh viên khi event xảy ra. Đây là giả định phân rã xác suất tích lũy, không phải hazard được UCI ước lượng. Mọi xác suất đúng hạn ở chế độ này phải ghi riêng.

Đối chứng cùng persona/seed: **B1** khung kỳ dự kiến + học lại; **B2** greedy tối đa tín chỉ; **B3** cố định 15 tín chỉ; so với ILP. Báo phân phối kỳ hoàn thành, P(đúng hạn), môn trượt kỳ vọng, tín chỉ đạt/kỳ; khoảng min–max theo λ/độ nhạy không gọi là CI. Các môn độc lập là giả định, có thể làm sai phương sai/xác suất hoàn tất.

Tiêu chí Pareto phải chốt trước khi chạy: dùng common random numbers và paired difference giữa hệ thống với từng baseline. Mỗi metric tính sai số chuẩn của paired differences qua N lượt; dung sai 95% là `1,96×SE_difference`. Chênh lệch nằm trong ±dung sai được xem là chưa phân biệt, không tính là cải thiện hay suy giảm. Chỉ tuyên bố ILP “tốt hơn” nếu không có metric chính xấu hơn dung sai và có ít nhất một cải thiện vượt dung sai; phải báo theo từng λ và từng chế độ dropout. Chưa có kết quả hiệu quả giai đoạn 1.

### D.5. Kiến trúc, công nghệ và chức năng dự kiến

Sơ đồ luồng/schema lưu `docs/diagrams/architecture.md`. Đề xuất giai đoạn 2:

| Thành phần | Công nghệ đề xuất | Lý do / rủi ro |
|---|---|---|
| Dữ liệu/ML | Python, pandas, scikit-learn; LR/RF/XGBoost | Tái lập, phù hợp dữ liệu bảng; XGBoost phụ thuộc cài đặt/hiệu chuẩn |
| Giải thích | SHAP | giải thích toàn cục/cục bộ; tương quan feature làm attribution không nhân quả |
| Rule/ILP | Python, YAML, PuLP + HiGHS (hoặc OR-Tools) | quy tắc cấu hình, solver mở; infeasible và trọng số cần giải thích |
| Giao diện | Streamlit (đề xuất) | nhanh cho prototype; chưa triển khai ở giai đoạn này |

Màn hình dự kiến: nhập/chọn hồ sơ; P(Dropout) và SHAP; flags/progress; môn đủ điều kiện và thứ tự học lại; phương án 12/15/18 với khoảng theo λ; so sánh ILP với B1–B3. SHAP giải thích tương quan cục bộ/toàn cục, không khẳng định nguyên nhân.

Đánh giá giai đoạn 2: Dropout Precision/Recall/F1/confusion matrix, ưu tiên recall với calibration/Brier; fit calibration trên validation và lưu trạng thái/metrics vào `risk_score` (exploratory hiện tại chưa được hiệu chuẩn lại). Hệ thống so với B1–B3 về kỳ hoàn thành, đúng hạn, tín chỉ đạt/kỳ, trượt kỳ vọng, tính khả thi và độ nhạy. Persona cần gồm giỏi/trung bình/yếu, môn nợ chặn chuỗi, môn không mở, ít môn đủ điều kiện, gần tốt nghiệp và hồ sơ thiếu. “Tốt hơn” chưa chốt: đề xuất tiêu chí Pareto—không làm giảm xác suất hoàn thành đúng hạn và cải thiện ít nhất một chỉ số rủi ro/tiến độ trong các khoảng kịch bản; cần cô duyệt trước khi chạy.

## E. Phân công và kế hoạch giai đoạn 2

| Thành viên | Module / đầu ra | Phụ thuộc | Tiêu chí hoàn thành |
|---|---|---|---|
| Thành viên 1 | Nạp/kiểm tra REAL; feature gate, LR/RF/XGBoost, validation/calibration, SHAP; API `predict_risk(student_features) → risk_score + shap_values` | Dictionary thời điểm, nhãn/mốc T1 được duyệt | Không leakage; test schema; metric/seed tái lập; SHAP không diễn giải nhân quả |
| Thành viên 2 | Rule engine, curriculum graph, eligibility, ILP, Monte Carlo; API `evaluate_student(profile,curriculum) → eligible_courses/progress_stats/academic_flags`; `plan_risk`/`optimize_plan` | CTĐT/quy chế, API risk/plan schema | Tests tiên quyết/ca biên; không hard-code; baseline B1–B3; status chuẩn và fallback rõ cờ |
| Thành viên 3 | Tuần 1 tự lấy CTĐT CNTT và quy chế Trường ĐH Nha Trang, ghi nguồn/phiên bản; dữ liệu SIMULATED/fixture thay thế, tích hợp, báo cáo và kiểm thử end-to-end | Schema/API của TV1/TV2; xác nhận màn hình; không giả định tài liệu chính thức nếu chưa truy xuất được | Lưu nguồn và ngày truy cập; đối chiếu CTĐT/giới hạn với cô; demo nhập hồ sơ→cảnh báo→plan→scenario; nhãn REAL/SIMULATED; kiểm thử tái lập |

**Điểm tích hợp:** `student_features → risk_score (0–1) + shap_values`; `student_profile + curriculum → eligible_courses[], progress_stats, academic_flags`; `eligible_courses + M3' base/risk tier → recommended_plan`; `recommended_plan × {12,15,18} × λ → so sánh lộ trình`. Định dạng CSV/JSON UTF-8, tên biến tiếng Anh, báo cáo tiếng Việt; seed mặc định 20261105. Nhánh tính năng riêng, PR/review chéo trước merge, khóa version dependency khi có môi trường chung.

**Timeline tương đối (chưa biết hạn nộp thực tế):**

| Tuần | Mốc / kiểm tra |
|---|---|
| 1 | TV3 tự lấy CTĐT CNTT/quy chế NTU và ghi nguồn; hỏi cô nếu muốn dùng tài liệu/giới hạn cụ thể; duyệt nhãn/T1, giữ fixture nếu chưa có |
| 2 | Chuẩn hóa data pipeline, split/validation và test leakage |
| 3 | Baseline ML, recall/hiệu chuẩn và SHAP; review TV1 |
| 4 | Rule engine + tests prerequisite/retake/edge cases |
| 5 | ILP, xử lý infeasible, đối chứng B1–B3 và test objective |
| 6 | Monte Carlo/độ nhạy, đánh giá persona |
| 7 | UI tích hợp và test end-to-end |
| 8 | Sửa lỗi, báo cáo, demo và kiểm tra tái lập |

Đường găng: **CTĐT/quy chế → schema + rules → eligible_courses → ILP → mô phỏng → tích hợp UI/đánh giá**. ML chạy song song sau khi xác nhận feature gate; giao diện phụ thuộc hai API.

| Rủi ro | Giảm thiểu | Phụ trách |
|---|---|---|
| Thiếu CTĐT/quy chế chính thức | Giữ fixture riêng, gắn nhãn, không suy luận chính thức; xin dữ liệu sớm | TV2 + TV3 |
| Domain shift Bồ Đào Nha → NTU | Không tuyên bố hiệu quả NTU; tìm dữ liệu được duyệt, đánh giá ngoài mẫu | TV1 |
| Selection bias của tải | Không coi M1/M3 theo tải là nhân quả; hiển thị λ như kịch bản | TV1 |
| ILP infeasible/suy biến | Mềm hóa Fmax, retry Cmin giảm tải có cờ, trạng thái/hành động chuẩn, ablation `u_i/F_max` | TV2 |
| Persona phụ thuộc tham số giả định | Sensitivity grid và thay bằng dữ liệu NTU; giữ raw config/source | TV2 + TV3 |
| Môn học tương quan nhưng mô phỏng độc lập | Báo hạn chế, kiểm tra kịch bản tương quan trong giai đoạn 2 | TV2 |
| Lỗi tích hợp schema/phiên bản | Hợp đồng API/fixtures, pin dependencies, smoke test CI | Cả nhóm |
| Lịch mở/lượt học lại không chính xác | Đối chiếu quy chế, test edge cases và chặn dùng trước duyệt | TV2 |

## Hạn chế chung

UCI không có course-level outcomes, difficulty, prerequisites, CTĐT hoặc attempts; mô hình không thể tự suy xác suất đạt từng môn. Kết quả ML chỉ exploratory và domain shift từ Bồ Đào Nha sang NTU chưa kiểm định. M3' gồm cả Target=Dropout; non-Dropout-only là phân tích survivor hậu nghiệm, không dùng làm baseline. Quan sát tải không nhân quả; `without evaluations` vẫn nằm trong mẫu số proxy. M2 difficulty/retake/load và hazard dropout là giả định; P(Dropout) hiện có isotonic/threshold trên OOF cùng mẫu nên PPV có optimistic bias. Xác suất trượt môn dùng độc lập. Chưa chạy Monte Carlo nhiều kỳ/đối chứng B1–B3, chưa làm UI hay chứng minh lợi ích. SHAP giải thích mô hình, không nhân quả.

## Câu hỏi cho cô (tối đa 6)

1. **Nhãn và mốc dự báo:** cô có duyệt ba lớp Dropout/Enrolled/Graduate và T1 cuối HK1 trước đăng ký HK2 không? Mặc định nhóm dùng 3 lớp, Enrolled là lớp riêng và loại feature HK2/biến chưa rõ timestamp.
2. **CTĐT/quy chế:** nhóm sẽ tự lấy CTĐT CNTT và quy chế đào tạo từ Trường ĐH Nha Trang; nếu cô muốn áp dụng giới hạn tín chỉ cụ thể hoặc tài liệu cụ thể, xin cô cho biết. Mặc định lưu nguồn/phiên bản, dùng fixture SIMULATED nếu chưa xác minh được tài liệu.
3. **Dùng P(Dropout):** cô có đồng ý cảnh báo và khuyến nghị mềm theo tầng, không hạn chế cứng tải? Mặc định warning chỉ hiển thị/đề nghị gặp cố vấn; cap tín chỉ và Fmax mềm (`enforce_cap=false`), không nhân P(Dropout) vào p_pass môn.
4. **Giả định mô phỏng:** có chấp nhận độc lập giữa môn và lưới λ={0;0,1;0,3}, difficulty/retake là GIẢ ĐỊNH kịch bản để so sánh không? Mặc định hiển thị song song, không chọn một giá trị tối ưu.
5. **Tiêu chí thành công:** có duyệt Pareto so với B1–B3, với dung sai 95% theo sai số chuẩn Monte Carlo (chênh lệch trong dung sai tính là chưa phân biệt) không? Mặc định chốt trước khi chạy và không tuyên bố tốt hơn nếu chưa đạt.
6. **Hạn nộp:** hạn nộp thực tế và số tuần còn lại là khi nào? Mặc định timeline tương đối 8 tuần, điều chỉnh sau khi cô xác nhận.

## Tự kiểm tra báo cáo gộp

- **Ước lượng độ dài:** khoảng 10 trang A4 khi dàn trang gọn (10,5–11 pt, bảng hẹp, giãn dòng đơn); đây là ước tính từ ~6.300 từ, chưa render PDF.
- **Tiêu chí F1–F8:** đã có bằng chứng I.1–I.7; risk warning/soft restriction tách riêng; 12/15/18 × λ độc lập; fallback S003; objective cùng đơn vị và test giải tay; p M3'/non-Dropout/RF cùng hai chế độ Monte Carlo; dung sai paired-SE; 6 câu hỏi và việc TV3 lấy CTĐT ở Tuần 1.
- **Nguồn tái lập:** validator bằng `python src/data/validate_curriculum.py`; C.1/C.3/C.6/C.7 bằng `python src/analysis/risk_to_plan_exploration.py`; prototype bằng `python src/analysis/ilp_formulation_check.py`; unit tests bằng `python -m unittest discover -s tests -v`. Seed `20261105`; các bảng OOF/calibration/persona/prototype được xuất vào `reports/generated/`.
- **Giới hạn kết luận:** chưa huấn luyện mô hình cuối, chưa chạy Monte Carlo nhiều kỳ/đối chứng, chưa làm giao diện, không tuyên bố hiệu quả NTU.

## Tệp bàn giao

- EDA/từ điển: `notebooks/01_eda_uci697.ipynb`, `archive/data_dictionary.csv`.
- Catalogue, tiến độ, validator/config: `data/processed/`, `src/data/validate_curriculum.py`, `reports/curriculum_validation.txt`, `src/config/credit_rules.yaml`.
- Rủi ro/plan: `docs/risk_to_plan_methods.md`, `archive/02_risk_to_plan_exploration.ipynb`, `src/optimize/plan_risk.py`.
- Rule/ILP/kiến trúc: `src/rules/rule_engine.py`, `src/optimize/ilp_prototype.py`, `docs/optimization_spec.md`, `docs/diagrams/architecture.md`, `archive/03_ilp_formulation_check.ipynb`.
- Bảng kết quả tái lập: `reports/generated/` (OOF warning/restriction, calibration, M3', persona, prototype và khuyến nghị).
- Kế hoạch/thư: `HANDOFF.md`; thư Stage 1 không có trong workspace (`NOT_FOUND`).
