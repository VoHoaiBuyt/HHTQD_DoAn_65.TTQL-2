# Chuyển rủi ro tổng thể thành rủi ro phương án

## 1. Mốc thông tin, dữ liệu và đích dự báo

Đây là kết quả **EXPLORATORY, chưa phải mô hình cuối**; seed `20261105`. Dữ liệu học vụ là **REAL (UCI-697)**; chương trình, môn học và persona dùng trong thử nghiệm là **SIMULATED**. Mốc dự báo T1 là cuối HK1, trước đăng ký HK2.

Hai đại lượng đích không được gộp:

1. `P(Dropout | T1)`: xác suất bỏ học cấp sinh viên, do bộ phân loại dùng feature `available_at ∈ {T0,T1_known}` ước lượng. Chỉ dùng để cảnh báo/ràng buộc ở rule engine; không nhân trực tiếp vào xác suất đạt môn.
2. `pass_rate_2 = approved_2nd / enrolled_2nd`: tỷ lệ đạt curricular unit HK2 hậu nghiệm. Chỉ xác định khi `enrolled_2nd > 0`; được dùng để xây nền ước lượng pass. `without evaluations` vẫn ở mẫu số enrollment, không được tính là approved, và được báo cáo riêng.

`enrolled_2` là `T1_decision`: chỉ dùng phân tầng/diagnostic C.3/M1; không đưa vào feature model P(Dropout) hay pass-rate tại T1. Sáu trường chưa rõ timestamp và mọi outcome HK2 đều bị loại khỏi feature cơ sở.

### Đối soát I.1–I.7 và tách warning/restriction

| Sửa đổi | Trạng thái | Bằng chứng |
|---|---|---|
| I.1 Validator | Đã làm | `reports/curriculum_validation.txt` PASS; kết quả nguyên văn được đặt trong mục B.2 báo cáo gộp. |
| I.2 M1/C.3 | Đã làm | OR M1 binary 1,314506; OR 3-class hiệu dụng 1,161026; C.3 observational OR 1,000469. Khác feature set/mô hình/estimand; M1 diagnostic, không nhân quả. |
| I.3 Calibration pass-rate | Đã làm | Bảng 10 decile holdout bên dưới; isotonic không cải thiện MAE/RMSE, không áp dụng. |
| I.4 M3' | Đã làm | Baseline gộp mọi mức tải theo HK1; Trung bình: 0,841799 ở tải 8+ so với 0,755601 ở 1–5 chỉ là M3 selection-bias reference. |
| I.5 Units | Đã làm | `floor(x+0.5)`, 4,5→5; docstring [plan_risk.py](../src/optimize/plan_risk.py) và config nêu lý do/đơn điệu. |
| I.6 enrolled_2=0 | Đã làm | 180 trường hợp; không coi là dropout/pass=0; observed dropout 42,7778%. |
| I.7 Persona | Đã làm | Tạo từ medoid REAL ở mỗi tercile HK1; S002 được kiểm tra thuộc Trung bình. |

Warning tiers chọn theo recall và chỉ để hiển thị: **REAL (UCI-697), train OOF** Thấp n=450/share 12,72%/PPV 4,89%; Trung bình n=1.166/share 32,95%/PPV 7,80%; Cao n=1.923/share 54,34%/PPV 53,25%. Restriction mềm tách riêng dùng isotonic-calibrated probability, threshold 0,50 đạt PPV 0,809 (n=866), recall 0,617; threshold 0,65 đạt 0,889/0,513; threshold 0,75 đạt 0,915/0,462. Không ai trong 173 điểm P=0,3213±0,02 bị xếp restriction. Đây là **GIẢ ĐỊNH chính sách/validation exploratory**; isotonic và threshold dùng cùng OOF nên có optimistic bias. `enforce_cap=false` mặc định, không khóa cứng sinh viên theo warning tier.

## 2. C.1 — Mô hình cơ sở exploratory

Logistic Regression ba lớp dùng 24 feature T0 + T1-known, train/test tách riêng 80/20 có phân tầng; train đánh giá bằng Stratified 5-fold CV. Random Forest Regressor ước lượng pass-rate trên nhóm có `enrolled_2 > 0` (KFold 5-fold). Đây là mô hình thử để tạo đầu ra cho phân tích, không phải lựa chọn hay huấn luyện mô hình cuối.

**REAL (UCI-697), exploratory**

| Chỉ số | Giá trị |
|---|---:|
| Dropout: CV accuracy / macro-F1 / F1 | 0,714046 / 0,616392 / 0,709335 |
| Dropout: holdout precision / recall / F1 | 0,701031 / 0,718310 / 0,709565 |
| Dropout: holdout Brier one-vs-rest | 0,121147 |
| Confusion matrix (hàng/thứ tự nhãn: Dropout, Enrolled, Graduate) | `[[204,20,60],[48,46,65],[39,24,379]]` |
| Pass-rate: số sinh viên có `enrolled_2 > 0` / không đăng ký | 4.244 / 180 |
| Pass-rate: CV MAE / RMSE | 0,120090 / 0,183969 |
| Pass-rate: holdout MAE / RMSE | 0,124046 / 0,193556 |

`enrolled_2 = 0` không được tự gán nhãn “bỏ học” hay pass-rate bằng 0: tỷ lệ Dropout quan sát trong nhóm này là **42,7778% (REAL)**, nên nhóm vẫn có thể thuộc nhiều Target. Hệ thống giữ trạng thái không đăng ký riêng; mô hình Dropout dự báo riêng, còn pass-rate không định nghĩa ở mẫu số bằng 0.

### Hiệu chuẩn pass-rate

Bảng dưới là calibration theo decile dự báo trên holdout **REAL (UCI-697)**. Mỗi decile có 84–85 sinh viên.

| Decile | Trung bình dự báo | Trung bình thực tế |
|---:|---:|---:|
| 0 | 0,009787 | 0,012381 |
| 1 | 0,208263 | 0,237507 |
| 2 | 0,518382 | 0,531022 |
| 3 | 0,709199 | 0,673686 |
| 4 | 0,792052 | 0,788403 |
| 5 | 0,844018 | 0,853117 |
| 6 | 0,876832 | 0,877344 |
| 7 | 0,917449 | 0,912353 |
| 8 | 0,954386 | 0,943961 |
| 9 | 0,982630 | 0,966373 |

Isotonic được fit trên dự đoán OOF của train, đánh giá trên cùng holdout: MAE/RMSE thô **0,124046/0,193556**, isotonic **0,124389/0,195836**; MAE calibration decile **0,012507** so với **0,015273**. **Không áp dụng isotonic** trong exploratory này vì không cải thiện các chỉ số holdout đã định trước; đây chưa phải kết luận hiệu chuẩn cuối.

## 3. C.3 — Kiểm định tải học quan sát, không nhân quả

Năng lực nền phân tầng theo tỷ lệ đạt HK1; tải HK2 chia 1–5, 6–7, 8+ curricular units. Pass rate là pooled `approved_2 / enrolled_2`; nhóm enrollment bằng 0 giữ riêng. Bảng dưới có cả số sinh viên, pass rate và tỷ lệ Dropout theo ô; nhãn **REAL (UCI-697)**.

| Tầng HK1 | Tải HK2 | Sinh viên | Pass rate HK2 | Tỷ lệ Dropout |
|---|---:|---:|---:|---:|
| Thấp | 0 | 180 | Không xác định | 0,427778 |
| Thấp | 1–5 | 578 | 0,286415 | 0,697232 |
| Thấp | 6–7 | 495 | 0,190445 | 0,828283 |
| Thấp | 8+ | 96 | 0,327546 | 0,729167 |
| Trung bình | 1–5 | 197 | 0,755601 | 0,213198 |
| Trung bình | 6–7 | 720 | 0,729621 | 0,275000 |
| Trung bình | 8+ | 430 | 0,841799 | 0,162791 |
| Cao | 1–5 | 307 | 0,915243 | 0,107492 |
| Cao | 6–7 | 1.002 | 0,914521 | 0,092814 |
| Cao | 8+ | 419 | 0,966438 | 0,059666 |

Hồi quy Logistic nhị phân mô tả `Dropout` có kiểm soát tỷ lệ đạt HK1, số môn HK1 đăng ký/đạt, điểm HK1 và tuổi cho OR quan sát **1,000469** mỗi curricular unit HK2 tăng thêm. Trong từng tầng, dấu không đồng nhất: tải 6–7 thấp hơn tải 1–5 ở tầng Thấp/Trung bình nhưng gần như không đổi ở tầng Cao; 8+ lại có pass rate cao hơn ở cả ba tầng so với 6–7. Kết luận theo yêu cầu là **(c) dữ liệu quan sát chưa đủ để kết luận tải cao làm giảm tỷ lệ đạt**; không có bằng chứng nhất quán theo tầng về quan hệ đơn điệu.

Đây là quan sát, không có ngẫu nhiên hóa; chọn tải có thể phụ thuộc năng lực/hoàn cảnh chưa đo và không biết ai bị buộc đăng ký nhiều. Không trình bày OR hoặc bảng trên như hiệu ứng nhân quả.

## 4. Đối chiếu M1 với hồi quy C.3 (I.2)

M1 diagnostic được fit trên cùng 24 feature T0 + T1-known **cộng** `enrolled_2` và cùng train/holdout split. Với các feature giữ cố định, binary Logistic Regression (`Dropout` so với phần còn lại) cho OR của `enrolled_2` **1,314506/unit**. Trên cùng feature set, mô hình Logistic ba lớp cho xác suất Dropout tại vector đại diện tăng từ **0,057021** khi đặt `enrolled_2=1` lên **0,238071** khi đặt `enrolled_2=12`; OR hiệu dụng qua hai điểm là **1,161026/unit**.

Hai OR M1 không trùng nhau vì binary Logistic và xác suất một lớp trong softmax ba lớp là các hàm khác nhau; OR ba lớp là hiệu dụng qua hai mức counterfactual, không phải hệ số tuyến tính. C.3 cho OR **1,000469**, nhưng dùng hồi quy quan sát kiểm soát ít biến hơn và không cùng mô hình đặc trưng/ước lượng; không thể coi ba con số là cùng một estimand. M1 tạo xu hướng rủi ro tăng khi tăng tải ở hai cách biểu diễn, nhưng thay `T1_decision` trong mô hình không phải can thiệp hợp lệ và có thể ngoại suy. **M1 bị loại làm phương pháp quyết định**, không chọn con số thuận lợi và không diễn giải chiều này thành nhân quả.

## 5. C.4 — So sánh phương pháp chuyển rủi ro sang phương án

### M1 — Thay feature enrolled HK2

- **Giả định:** mô hình giữ nguyên quan hệ đã học khi thay số unit HK2 đăng ký.
- **Điều kiện:** diagnostic để phát hiện chiều bất hợp lý; không dùng như dự báo T1 hay ước lượng can thiệp.
- **Ưu:** đơn giản, tận dụng mô hình P(Dropout).
- **Nhược/rủi ro:** `enrolled_2` là quyết định tương lai; quan sát bị confounding và correlated skill; kết quả M1 tăng P(Dropout) theo tải nhưng không nhận dạng tác động.
- **Kiểm chứng:** so sánh binary/3-class cùng feature set, đối chiếu C.3 và kiểm tra extrapolation. M1 bị loại làm phương pháp chính.

### M2 — Hai tầng với hệ số tải tường minh

```text
p_i = clip(p_student × f_difficulty(i) × g_load(plan) × r_retake(i), 0, 1)
g_load = exp(−λ × max(0, units(plan) − median_units_REAL))
```

`p_student` là RF pass-rate từ T0 + T1-known, không phải `P(Dropout)`. `f_difficulty` được tạo **SIMULATED** bằng trung vị điểm nhóm học phần chia trung vị chung, cắt ở phân vị 10–90 của các nhóm; fixture hiện cho factor khoảng **0,9083–1,1597**. `r_retake` có lưới **GIẢ ĐỊNH** {0,9; 1,0; 1,1}. UCI không có outcome/difficulty/attempt ở cấp môn.

`units = total_credits / mean(course.credits)` trên catalogue SIMULATED; mean hiện tại 128/48 = **2,6667**. 12/15/18 tín chỉ tương ứng 4,5/5,625/6,75 unit; quy tắc half-up `floor(x+0.5)` cho 5/6/7, không dùng bankers rounding. `g_load` dùng số unit tương đương chưa làm tròn trong `plan_risk`; prototype ILP dùng unit làm tròn từ trần tải kịch bản để giữ mô hình tuyến tính. `median_units_REAL=6`. Vì C.3 không xác nhận tác động nhân quả, λ ∈ {0; 0,1; 0,3} là **GIẢ ĐỊNH kịch bản**, trình bày song song.

- **Ưu:** có thể phân biệt môn qua hệ số fixture, giải thích rõ tải và lần học lại.
- **Nhược/rủi ro:** tải/độ khó không được nhận dạng từ UCI; domain shift lớn.
- **Kiểm chứng:** độ nhạy nhiều λ, factor độ khó và retake; thay bằng dữ liệu NTU được phê duyệt khi có.

### M3 — Band tải × tầng HK1 (chỉ minh chứng thiên lệch chọn lọc)

Tỷ lệ pooled REAL trong từng ô (tầng năng lực HK1 × band tải HK2). Ở tầng Trung bình, pass rate ô 8+ là **0,841799**, so với **0,755601** ở band 1–5. Không xem đây là bằng chứng tải cao cải thiện kết quả: người có năng lực/điều kiện khác nhau có thể tự chọn tải. M3 theo band không còn là baseline.

### M3' — Baseline chính: tỷ lệ theo tầng HK1, gộp mọi tải

```text
p_student = Σ approved_2 / Σ enrolled_2
            trong tầng năng lực HK1; mọi band tải HK2 được gộp
```

**REAL (UCI-697):** Thấp 1.683/6.776 = **0,248377** (1.169 sinh viên có đăng ký); Trung bình 7.349/9.429 = **0,779404** (1.347); Cao 10.592/11.366 = **0,931902** (1.728). Nếu strata dưới ngưỡng tối thiểu 30 sinh viên, gộp dần với tầng liền kề theo thứ tự Thấp–Trung bình–Cao, tính lại tỷ lệ từ tổng approved/enrolled; nếu vẫn không đủ mẫu trả “không ước lượng được”, không tự thay bằng 0.

**Chọn M3' làm baseline chính** vì không mang selection-by-load vào xác suất nền; hiệu ứng tải chỉ đi qua `g_load` khi hiển thị M2. M3' không phân biệt độ khó môn hay học lại; M2 là độ nhạy SIMULATED. Mọi xác suất vẫn là proxy UCI, chưa được kiểm chứng tại NTU.

M3' gồm cả sinh viên sau đó có Target=Dropout; loại họ sau khi biết Target là phân tích hậu nghiệm survivor-only. **REAL**: tỷ lệ pass M3' / chỉ Target≠Dropout lần lượt Thấp 0,248377/0,564428 (n non-Dropout=286), Trung bình 0,779404/0,833310 (n=1.037), Cao 0,931902/0,946581 (n=1.577). Ví dụ 0,7457 không tái lập được bằng phép pooling hiện hành. S003/yếu: M3'=0,248377; non-Dropout tầng=0,564428; RF cá thể=0,048941. Không chọn giá trị thuận lợi: baseline chính là M3' vì không điều kiện theo outcome tương lai; non-Dropout-only có survivorship bias, RF cá thể exploratory và domain shift. Mọi kết quả chỉ áp dụng như proxy.

## 6. C.5 — Đặc tả đầu ra `plan_risk`

Hàm `plan_risk(student_id, plan, p_student_pass, ...)` trong `src/optimize/plan_risk.py` nhận danh sách môn có `course_id`, `credits`, nhóm/độ khó, trạng thái và số lần học; xác suất nền **M3' hoặc RF pass-rate** phải được ghi nguồn rõ. Trả về `p_pass_by_course`, `expected_credits_passed`, `expected_failed_courses`, `prob_at_least_k_fail` cho k=1,2, `plan_risk_index`, tổng tín chỉ/unit. Hiện `plan_risk_index = 100 × (1 − expected_credits_passed / Σcredits)`; plan rỗng trả `None`.

Với `p_i` và giả định độc lập:

```text
E[tín chỉ đạt] = Σ credits_i × p_i
E[số môn trượt] = Σ (1 − p_i)
P(≥1 trượt) = 1 − Π p_i
P(≥2 trượt) = 1 − Π p_i − Σ_i [(1 − p_i) × Π_(j≠i) p_j]
```

Độc lập là giả định, không phải dữ kiện; năng lực chung có thể làm kết quả môn tương quan. Mapping credit → curricular unit là xấp xỉ: chia tổng tín chỉ theo trung bình tín chỉ/môn SIMULATED; làm tròn half-up để phân band UCI, đảm bảo đơn điệu. Không suy ra số tín chỉ chính thức từ UCI.

Môn học lại: trạng thái `failed`/`attempt_count>1` được gắn factor `r_retake` **GIẢ ĐỊNH** {0,9;1,0;1,1}; mặc định trung tâm 1,0, không giả định học lại chắc chắn tốt hơn. `P(Dropout)` không đi vào `p_i`; warning dùng để hiển thị/cố vấn, caps tín chỉ/Fmax là khuyến nghị mềm mặc định, không hard-enforce (`enforce_cap=false`).

## 7. C.6–C.7 — Persona và độ nhạy

Persona **SIMULATED** lấy vector feature từ medoid hồ sơ **REAL** ở tầng HK1 tương ứng, sau đó gắn nhãn SIMULATED và dựng tiến độ CTĐT fixture. S002 được kiểm tra thuộc tầng **Trung bình**. Tám persona được chạy; subset-sum lũy tiến ở budget cao hơn giữ môn đã chọn ở budget thấp rồi bổ sung môn đủ điều kiện/đúng lịch mở/prerequisite.

| Persona / tầng HK1 từ REAL | Budget tín chỉ | Thực chọn | M3' `p_student` | Expected failures M3' | Ghi chú (SIMULATED) |
|---|---:|---:|---:|---:|---|
| S001 / Cao | 12 | 12 | 0,931902 | 0,272391 | Đủ |
| S001 / Cao | 15 | 14 | 0,931902 | 0,340489 | Underfill |
| S001 / Cao | 18 | 18 | 0,931902 | 0,476685 | Đủ |
| S002 / Trung bình | 12 | 12 | 0,779404 | 0,882384 | Đủ |
| S002 / Trung bình | 15 | 14 | 0,779404 | 1,102980 | Underfill |
| S002 / Trung bình | 18 | 18 | 0,779404 | 1,544172 | Đủ |
| S003 / Thấp | 12 | 12 | 0,248377 | 3,006494 | Đủ |
| S003 / Thấp | 15 | 15 | 0,248377 | 3,758117 | Đủ |
| S003 / Thấp | 18 | 17 | 0,248377 | 4,509740 | Underfill |
| S005 / Trung bình | 12 | 12 | 0,779404 | 1,102980 | Đủ; môn nợ IT202 chặn chuỗi |
| S005 / Trung bình | 15 | 15 | 0,779404 | 1,323576 | Đủ |
| S005 / Trung bình | 18 | 15 | 0,779404 | 1,323576 | Không đủ môn đủ điều kiện |

Với nested plans, expected failures không giảm khi tăng tải; expected credits passed của persona yếu tăng chậm (M3' đồng nhất xác suất nên không mô hình hóa bão hòa/giảm). S004 chỉ lấp 14/16 ở ngân sách 15/18; S005 lấp 15 ở budget 18; S006 chỉ còn 2 tín chỉ; S008 không còn môn tương lai. Đây là giới hạn của persona/đồ thị SIMULATED, không thêm môn trái prerequisite để giả tạo khả năng đăng ký.

**Độ nhạy M2 trên plan S003 12 tín chỉ (SIMULATED + GIẢ ĐỊNH)**: λ {0;0,1;0,3} × difficulty {0,8;1,0;1,2} × retake {0,9;1,0;1,1} tạo khoảng **3,758010–3,845897 expected failures**, **0,462309–0,725971 expected credits passed** và plan-risk **93,950238–96,147426**. Đây là cực trị của lưới tham số; p_student RF của S003 rất thấp (0,048941), nên đầu ra khác M3' đáng kể. Không phải khoảng tin cậy. M3' là baseline chính; khoảng này minh họa mức phụ thuộc giả định của M2.

## 8. Hạn chế và bàn giao sang D

- Quan sát UCI không nhận dạng tác động nhân quả của tải; M1 bị loại.
- Domain shift: **REAL (UCI-697)** từ Bồ Đào Nha; áp mô hình lên persona **SIMULATED** chỉ sanity-check luồng/logic, không xác nhận độ chính xác NTU.
- Độ khó, tín chỉ môn, tiên quyết, lịch mở, attempts đều **SIMULATED**; không có dữ liệu cấp môn UCI.
- `without evaluations` vẫn trong mẫu số enrollment, coi chưa approved cho proxy; nhóm này có cơ hội đánh giá không đồng đều.
- M3' pooling theo năng lực bỏ qua tải và biến cố cá nhân; độc lập giữa môn là giả định.
- Ngưỡng risk tiers chọn exploratory trên 5-fold OOF train để đạt recall mục tiêu 0,90/0,98; cần đánh giá lại trên validation/NTU. Không dùng holdout để chọn threshold.

Tái chạy: `python src/analysis/risk_to_plan_exploration.py`; tự kiểm tra quy đổi/rủi ro: `python src/optimize/plan_risk.py`. Notebook lưu trữ: `archive/02_risk_to_plan_exploration.ipynb`.
