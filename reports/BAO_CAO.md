# Báo cáo giai đoạn 1 — Hệ hỗ trợ ra quyết định cảnh báo rủi ro học vụ và tối ưu hóa lộ trình tích lũy tín chỉ

> **Nhãn dữ liệu dùng trong toàn báo cáo:**
> - **REAL (UCI-697):** số liệu lấy trực tiếp từ bộ dữ liệu UCI-697.
> - **SIMULATED:** chương trình đào tạo, học phần, tiến độ và persona do nhóm tự dựng để thử schema/thuật toán, **không phải** CTĐT chính thức của Trường ĐH Nha Trang.
> - **GIẢ ĐỊNH:** tham số chính sách/kịch bản chưa được kiểm chứng (λ, độ khó, học lại, β, γ, ngưỡng cảnh báo…).
>
> **Phạm vi:** khảo sát dữ liệu, thiết kế hệ thống và kế hoạch giai đoạn 2. Mô hình và bộ giải ở đây chỉ exploratory/prototype; chưa huấn luyện mô hình cuối, chưa triển khai giao diện và không coi persona là bằng chứng hiệu quả.

## 0. Tóm tắt điều hành

Đề xuất đề tài “Hệ hỗ trợ ra quyết định cảnh báo rủi ro học tập và tối ưu hóa lộ trình tích lũy tín chỉ sinh viên” theo kiến trúc nối tiếp:

1. ML cảnh báo nguy cơ bỏ học từ đặc trưng có sẵn tại T1 (cuối HK1, trước đăng ký HK2).
2. Rule engine cảnh báo học vụ và xác định môn đủ điều kiện.
3. Tối ưu kế hoạch học phần có ràng buộc tín chỉ/tiên quyết/rủi ro (ILP).
4. Mô phỏng nhiều kỳ và so sánh với phương án đăng ký thông thường.

ML cảnh báo bỏ học và cảnh báo học vụ theo GPA/tiến độ là **hai bài toán riêng**, không gộp đầu ra.

Khảo sát **REAL (UCI-697)** có 4.424 sinh viên, 37 thuộc tính, không thiếu/trùng toàn dòng. UCI không có dữ liệu cấp học phần, số tín chỉ từng môn hay CTĐT; nhóm đã dựng catalogue 48 môn/128 tín chỉ **SIMULATED** để thử schema và logic. Xác suất Dropout và tỷ lệ đạt HK2 chỉ là kết quả exploratory trên dữ liệu Bồ Đào Nha; áp vào persona mô phỏng chỉ kiểm tra logic, không kiểm chứng độ chính xác tại NTU.

Tải HK2 trong dữ liệu quan sát không cho bằng chứng nhất quán về quan hệ giảm pass-rate trong cùng tầng HK1. Vì vậy không dùng counterfactual đổi số môn đăng ký làm phương pháp quyết định. Baseline pass-rate đề xuất là **M3′ theo tầng năng lực HK1, gộp mọi mức tải**; ảnh hưởng tải/độ khó/học lại chỉ hiển thị như tham số **GIẢ ĐỊNH kịch bản** độ nhạy.

Prototype PuLP/HiGHS xác nhận mô hình nhỏ có nghiệm khác nhau theo persona/ngân sách, đồng thời cho thấy ràng buộc rủi ro có thể làm một số persona không khả thi — đây là thông tin để rà config, không phải hiệu quả hệ thống.

**Trạng thái:** A/B (dữ liệu, CTĐT, validator) và C/D (mô hình exploratory, rule engine, ILP prototype) đã xong ở mức thiết kế; Monte Carlo nhiều kỳ, đối chứng B1–B3, UI và đánh giá trên NTU **chưa làm**. Nhóm cần cô góp ý về nhãn/mốc T1, CTĐT và quy chế chính thức, cách dùng P(Dropout), giả định mô phỏng và tiêu chí so sánh. Báo cáo không khẳng định mô hình tốt hơn baseline.

## 1. Nguồn dữ liệu, mốc T1 và kiểm soát leakage

### 1.1. Nguồn và chất lượng

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

### 1.2. Nguồn CTĐT và ánh xạ UCI sang học phần mô phỏng

- Bài báo UCI trích dẫn: M. V. Martins, D. Tolledo, J. Machado, L. M. T. Baptista, V. Realinho, “Early prediction of student's performance in higher education: a case study” (2021), https://doi.org/10.1007/978-3-030-72657-7_16. Metadata được kiểm tra qua UCI API/Crossref; toàn văn nhà xuất bản không truy cập được để xác minh thêm timestamp theo từng trường.
- Cổng CTĐT chính thức NTU: https://ctdt.ntu.edu.vn (truy cập 2026-11-05). Trang là ứng dụng web; các API ngành/chương trình yêu cầu xác thực (401). Không thu được bảng CTĐT CNTT công khai có thể đọc được trong khảo sát này.
- Vì vậy toàn bộ `data/simulated/` là **SIMULATED**, dựng theo cấu trúc phổ biến để thử schema/thuật toán, **không phải CTĐT chính thức của Trường ĐH Nha Trang**. Cần thay/duyệt theo CTĐT và quy chế thật trước triển khai.

Giả định nối số học phần:

1. Tạm coi **1 curricular unit ≈ 1 học phần** khi tính số học phần đã đăng ký/đạt trong hồ sơ **SIMULATED**.
2. Không suy ra số tín chỉ UCI từ số unit. Tín chỉ của fixture lấy trực tiếp từ từng dòng `courses.csv`.
3. Không thể nối một unit UCI cụ thể với `course_id` mô phỏng; chỉ so sánh ở mức số lượng/tổng hợp.
4. CTĐT nháp có 8 kỳ, 40 học phần bắt buộc và 8 dòng tự chọn placeholder; tổng tín chỉ kiểm tra là tổng của 48 dòng. Mỗi placeholder đại diện một học phần tự chọn giả định được chọn, không phải tên môn thật; phân bổ placeholder theo kỳ chỉ là dữ liệu mẫu.

Giả định quy đổi điểm:

- `grade_10 = grade_20 / 2`, giới hạn đầu vào UCI ở `[0, 20]`, kết quả `[0, 10]`.
- `grade_4 = grade_10 × 0.4`, giới hạn kết quả `[0, 4]`.
- Chiều ngược dùng cho cột `Curricular units 1st sem (grade)` của hồ sơ fixture: `grade_20 = grade_10 × 2`.

Đây là **giả định tạm**, không có căn cứ trong tài liệu UCI để khẳng định tương đương thang điểm/quy chế Việt Nam. Phép chia 2 chỉ dùng để tạo đặc trưng ML trong fixture; **không dùng để suy ngưỡng đạt học phần của NTU**. Ngưỡng đạt, quy đổi chính thức và GPA cần xác nhận với giảng viên/NTU. Các giá trị `grade_10` của `student_progress.csv` được sinh để phục vụ kiểm thử, không phải kết quả học tập thật.

### 1.3. Thời điểm có sẵn và leakage

Từ điển thuộc tính đầy đủ lưu tại `reports/data_dictionary.csv`, gồm tên, kiểu, ý nghĩa, nhóm, `available_at`, cờ leakage và lý do. Feature cơ sở ở mốc **T1: cuối HK1, trước đăng ký HK2** chỉ nhận thuộc tính `T0` hoặc `T1_known`.

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

### 1.4. Đặc trưng ML có thể/không thể tạo từ hồ sơ mô phỏng

**Có thể tạo ở mức fixture:**

- Sáu trường HK1: `Curricular units 1st sem (enrolled)` và `approved` đếm từ các hàng fixture; `credited` mặc định 0 khi chưa mô phỏng công nhận tín chỉ; `grade` lấy trung bình điểm đạt trên thang 10 rồi nhân 2; `evaluations` và `without evaluations` đếm theo trạng thái fixture.
- `Age at enrollment` và các trường đầu vào khác được ghi thành giá trị **SIMULATED** theo kịch bản. Mã ngành tuyển sinh, học vấn/quốc tịch/nghề nghiệp phụ huynh dùng mã giống hình thức UCI chỉ để thử schema.

**Chưa thể tạo hợp lệ/không dùng ở bộ đặc trưng T1 cơ sở:**

- `Debtor`, `Tuition fees up to date`, `Scholarship holder`, `Unemployment rate`, `Inflation rate`, `GDP`: chưa xác định timestamp ⇒ gắn trạng thái **chưa xác minh**, không đưa vào bộ đặc trưng T1 cơ sở.
- `Target`: không tạo nhãn giả cho persona, vì không có kết quả cuối kỳ thực nghiệm.
- `Curricular units 2nd sem (credited)` và `(enrolled)`: là biến quyết định/đầu vào mô phỏng phương án tại T1, không phải feature đã quan sát cho ML.

### 1.5. Kết quả EDA và đề xuất nhãn

Target mất cân bằng; cần báo cáo precision, recall, F1 lớp Dropout và confusion matrix, không dùng accuracy làm tiêu chí duy nhất. XGBoost/RF/LR là ứng viên đánh giá ở giai đoạn 2; hiện chỉ chạy Logistic Regression/RF exploratory phục vụ mục 3. Không huấn luyện mô hình cuối. Cần xác nhận nhãn ba lớp/ý nghĩa `Enrolled` và mốc T1 ở mục 11.

## 2. CTĐT mô phỏng, tiến độ và persona

### 2.1. Schema dữ liệu

```mermaid
erDiagram
    COURSES {
        string course_id PK
        string course_name
        int credits
        int planned_semester
        string course_type
        string offered_semesters
        string group
        string source_label
    }

    PREREQUISITES {
        string course_id PK, FK
        string prerequisite_id PK, FK
        string type
        string source_label
    }

    STUDENT_PROFILE {
        string student_id PK
        string persona
        int current_semester
        int cumulative_credits
        float gpa
        int failed_courses_count
        string source_label
    }

    STUDENT_PROGRESS {
        string student_id PK, FK
        string course_id PK, FK
        string status
        float grade_10
        int attempt_count
        int semester_taken
        string source_label
    }

    COURSES ||--o{ PREREQUISITES : "course_id"
    COURSES ||--o{ PREREQUISITES : "prerequisite_id"
    STUDENT_PROFILE ||--o{ STUDENT_PROGRESS : has
    COURSES ||--o{ STUDENT_PROGRESS : records
```

Khóa và ràng buộc:

- `courses`: PK `course_id`.
- `prerequisites`: PK ghép (`course_id`, `prerequisite_id`); cả hai là FK tới `courses.course_id`.
- `student_profile`: PK `student_id`.
- `student_progress`: PK ghép (`student_id`, `course_id`); FK `student_id` tới `student_profile.student_id`, FK `course_id` tới `courses.course_id`.
- Tất cả bảng trong sơ đồ là **SIMULATED**. CSV hiện thực hóa khóa bằng cột định danh; việc cưỡng chế FK/PK được kiểm tra bởi script, vì CSV không tự thực thi ràng buộc quan hệ.

### 2.2. Catalogue và kiểm tra

Catalogue **SIMULATED** có 48 môn (40 bắt buộc, 8 elective placeholder), 8 học kỳ và 128 tín chỉ; tín chỉ theo kỳ HK1–HK8 lần lượt 16, 15, 16, 17, 16, 16, 16, 16. Mọi giới hạn hiện tại là fixture theo cấu hình, không phải quy chế.

Kết quả chạy lại `python src/data/validate_curriculum.py` trên dữ liệu hiện hành — **nguyên văn**, nhãn **SIMULATED**:

```text
Curriculum validation — SIMULATED
PASS: Mã học phần duy nhất.
PASS: Số học phần 48 nằm trong khoảng 40–50.
PASS: Có đủ học kỳ dự kiến 1–8.
PASS: Mọi học phần được gắn nhãn SIMULATED.
PASS: Mọi course_id và prerequisite_id trong quan hệ tiên quyết đều tồn tại.
PASS: Đồ thị tiên quyết là DAG, không có chu trình.
PASS: Thứ tự học kỳ phù hợp loại quan hệ tiên quyết/học trước/song hành.
PASS: Loại quan hệ chỉ gồm 'tiên quyết', 'học trước' hoặc 'song hành'.
PASS: Mỗi học phần có ít nhất một học kỳ mở, gồm học kỳ dự kiến.
PASS: Tổng tín chỉ catalogue 128 nằm trong khoảng 120–140.
PASS: Tín chỉ từng học kỳ nằm trong khoảng cấu hình 12–18.
Tín chỉ theo học kỳ — SIMULATED: HK1=16, HK2=15, HK3=16, HK4=17, HK5=16, HK6=16, HK7=16, HK8=16
KẾT LUẬN: PASS (128 tín chỉ, 48 học phần)
```

### 2.3. Persona

Persona được tạo từ medoid vector feature REAL thuộc từng tầng HK1 rồi gắn nhãn SIMULATED; S002 được kiểm tra thuộc tầng Trung bình. Các ca học lại, môn chặn chuỗi, gần tốt nghiệp và hoàn tất tín chỉ dùng để sanity-check rule engine. Persona không đủ môn để lấp tải được giữ nguyên, không thêm môn trái prerequisite. Toàn bộ điểm/course graph/lịch mở còn phải thay bằng dữ liệu CTĐT chính thức.

### 2.4. Hạn chế: domain shift

Mô hình/quan sát học từ **REAL (UCI-697)** tại các cơ sở Bồ Đào Nha; hồ sơ và chương trình hiện tại là **SIMULATED**. Áp mô hình UCI lên persona chỉ kiểm tra luồng dữ liệu, thứ tự tương đối và logic hệ thống, **không** xác nhận độ chính xác cho NTU. Cần dữ liệu NTU được phê duyệt và đánh giá độc lập trước khi dùng thực tế.

## 3. Hai mục tiêu dự báo và mô hình exploratory

### 3.1. Tách hai mục tiêu

Hai đại lượng đích **không được gộp**:

1. `P(Dropout | T1)`: xác suất bỏ học cấp sinh viên, do bộ phân loại dùng feature `available_at ∈ {T0, T1_known}` ước lượng. Chỉ dùng để cảnh báo/ràng buộc ở rule engine; **không nhân trực tiếp** vào xác suất đạt môn.
2. `pass_rate_2 = approved_2nd / enrolled_2nd`: tỷ lệ đạt curricular unit HK2 hậu nghiệm. Chỉ xác định khi `enrolled_2 > 0`; dùng để xây nền ước lượng pass. `without evaluations` vẫn ở mẫu số enrollment, không được tính là approved, và được báo cáo riêng.

`enrolled_2` là `T1_decision`: chỉ dùng phân tầng/diagnostic C.3/M1; không đưa vào feature model P(Dropout) hay pass-rate tại T1. Sáu trường chưa rõ timestamp và mọi outcome HK2 đều bị loại khỏi feature cơ sở.

### 3.2. Mô hình cơ sở exploratory

Logistic Regression ba lớp dùng 24 feature T0 + T1-known, train/test tách riêng 80/20 có phân tầng; train đánh giá bằng Stratified 5-fold CV. Random Forest Regressor ước lượng pass-rate trên nhóm có `enrolled_2 > 0` (KFold 5-fold). Đây là mô hình thử để tạo đầu ra cho phân tích, **không phải** lựa chọn hay huấn luyện mô hình cuối. Seed `20261105`.

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

### 3.3. Hiệu chuẩn pass-rate

Bảng dưới là calibration theo decile dự báo trên holdout **REAL (UCI-697)**. Mỗi decile có 84–85 sinh viên.

| Decile | n | Trung bình dự báo | Trung bình thực tế |
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

Isotonic được fit trên dự đoán OOF của train, đánh giá trên cùng holdout: MAE/RMSE thô **0,124046/0,193556**, isotonic **0,124389/0,195836**; MAE calibration decile **0,012507** so với **0,015273**. **Không áp dụng isotonic** cho pass-rate trong exploratory này vì không cải thiện các chỉ số holdout đã định trước; đây chưa phải kết luận hiệu chuẩn cuối.

### 3.4. Kiểm định tải học quan sát, không nhân quả

Năng lực nền phân tầng theo tỷ lệ đạt HK1; tải HK2 chia 1–5, 6–7, 8+ curricular units. Pass rate là pooled `approved_2 / enrolled_2`; nhóm enrollment bằng 0 giữ riêng. Nhãn **REAL (UCI-697)**:

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

### 3.5. Đối chiếu M1 với hồi quy C.3

M1 diagnostic được fit trên cùng 24 feature T0 + T1-known **cộng** `enrolled_2` và cùng train/holdout split. Với các feature giữ cố định:

- Binary Logistic Regression (`Dropout` so với phần còn lại): OR của `enrolled_2` **1,314506/unit**.
- Logistic ba lớp: xác suất Dropout tại vector đại diện tăng từ **0,057021** khi `enrolled_2=1` lên **0,238071** khi `enrolled_2=12`; OR hiệu dụng qua hai điểm là **1,161026/unit**.
- C.3 observational OR **1,000469** (kiểm soát ít biến hơn, không cùng mô hình đặc trưng/ước lượng).

Hai OR M1 không trùng nhau vì binary Logistic và xác suất một lớp trong softmax ba lớp là các hàm khác nhau; OR ba lớp là hiệu dụng qua hai mức counterfactual, không phải hệ số tuyến tính. Ba con số không cùng một estimand. M1 tạo xu hướng rủi ro tăng khi tăng tải ở hai cách biểu diễn, nhưng thay `T1_decision` trong mô hình không phải can thiệp hợp lệ và có thể ngoại suy. **M1 bị loại làm phương pháp quyết định**, không chọn con số thuận lợi và không diễn giải chiều này thành nhân quả.

## 4. Chuyển rủi ro tổng thể thành xác suất từng môn

### 4.1. So sánh phương pháp

| Phương pháp | Giả định, ưu/nhược và kiểm chứng | Quyết định |
|---|---|---|
| M1: thay `enrolled_2` trong mô hình Dropout | `T1_decision` không phải feature đã quan sát; phản ánh liên hệ và ngoại suy, không nhận dạng tác động. Chiều counterfactual tăng Dropout; đối chiếu với phân tầng mục 3.4, không dùng ra quyết định. | Loại làm chính. |
| M2: hai tầng tham số | `p_i=clip(p_student × f_difficulty(i) × g_load(plan) × r_retake(i),0,1)`. Factor độ khó từ median grade_10 theo nhóm SIMULATED / median chung, cắt quantile 10–90; fixture 0,9083–1,1597. `g_load=exp(−λ×max(0,units−6))`; `r_retake` lưới {0,9;1,0;1,1}. Dễ giải thích, nhưng môn/độ khó/tải không được UCI nhận dạng. | Độ nhạy; λ={0;0,1;0,3} và factor là **GIẢ ĐỊNH**. |
| M3: tầng HK1 × band tải | Tỷ lệ pooled REAL trong ô; tầng Trung bình 8+ là 0,841799 so với 1–5 là 0,755601. Có thể bị selection bias. | Chỉ minh chứng thiên lệch chọn tải. |
| M3′: tầng HK1, gộp mọi band tải | `p_student=Σapproved_2/Σenrolled_2` trong tầng HK1; không đưa selection-by-load vào xác suất nền. | **Baseline chính**; hiệu ứng tải chỉ vào qua `g_load` của M2. |

M2 ước lượng `p_student` bằng RF pass-rate từ T0 + T1-known, **không phải** `P(Dropout)`. `units = total_credits / mean(course.credits)` trên catalogue SIMULATED; mean hiện tại 128/48 = **2,6667** tín chỉ/môn. 12/15/18 tín chỉ tương ứng 4,5/5,625/6,75 unit; quy tắc half-up `floor(x+0.5)` cho 5/6/7, không dùng bankers rounding. `g_load` dùng số unit tương đương chưa làm tròn trong `plan_risk`; prototype ILP dùng unit làm tròn từ trần tải kịch bản để giữ mô hình tuyến tính. `median_units_REAL=6`.

### 4.2. Baseline M3′

**REAL (UCI-697):** Thấp 1.683/6.776 = **0,248377** (1.169 sinh viên có đăng ký); Trung bình 7.349/9.429 = **0,779404** (1.347); Cao 10.592/11.366 = **0,931902** (1.728). Nếu strata dưới ngưỡng tối thiểu 30 sinh viên, gộp dần với tầng liền kề theo thứ tự Thấp–Trung bình–Cao, tính lại tỷ lệ từ tổng approved/enrolled; nếu vẫn không đủ mẫu trả “không ước lượng được”, không tự thay bằng 0.

M3′ gồm cả sinh viên sau đó có Target=Dropout; đây là pass-rate quan sát của các unit đã đăng ký, không phải xác suất pass có điều kiện sống sót. Loại họ sau khi biết Target là phân tích hậu nghiệm survivor-only:

| Tầng HK1 | M3′ mọi Target | M3′ chỉ Target≠Dropout | Mẫu non-Dropout có enrollment |
|---|---:|---:|---:|
| Thấp | 0,248377 | 0,564428 | 286 |
| Trung bình | 0,779404 | 0,833310 | 1.037 |
| Cao | 0,931902 | 0,946581 | 1.577 |

Đối chiếu **SIMULATED persona** (vector feature REAL-derived): S003/yếu có M3′=0,248377, rate tầng non-Dropout=0,564428 và RF dự báo cá thể=0,048941; S002/trung bình lần lượt 0,779404, 0,833310, 0,593345. Mức 0,7457 nêu trước đây không tái lập được bằng phép pooling hiện hành; không thay số để khớp ví dụ. Mặc định dùng M3′ làm baseline ổn định, không điều kiện hóa theo Dropout hậu nghiệm; RF và non-Dropout table chỉ là đối chiếu/độ nhạy. Chế độ mô phỏng hazard bỏ học, nếu dùng, tách riêng ở mục 8.

### 4.3. Đặc tả `plan_risk`

Hàm `plan_risk(student_id, plan, p_student_pass, ...)` trong `src/optimize/plan_risk.py` nhận danh sách môn có `course_id`, `credits`, nhóm/độ khó, trạng thái và số lần học; xác suất nền **M3′ hoặc RF pass-rate** phải được ghi nguồn rõ. Trả về:

- `p_pass_by_course`
- `expected_credits_passed = Σ credits_i × p_i`
- `expected_failed_courses = Σ (1 − p_i)`
- `prob_at_least_k_fail` cho k=1,2
- `plan_risk_index = 100 × (1 − expected_credits_passed / Σcredits)`
- tổng tín chỉ/unit

Plan rỗng trả `None`.

Với `p_i` và giả định độc lập:

```text
E[tín chỉ đạt] = Σ credits_i × p_i
E[số môn trượt] = Σ (1 − p_i)
P(≥1 trượt) = 1 − Π p_i
P(≥2 trượt) = 1 − Π p_i − Σ_i [(1 − p_i) × Π_(j≠i) p_j]
```

Độc lập là giả định, không phải dữ kiện; năng lực chung có thể làm kết quả môn tương quan. Mapping credit → curricular unit là xấp xỉ: chia tổng tín chỉ theo trung bình tín chỉ/môn SIMULATED; làm tròn half-up để phân band UCI, đảm bảo đơn điệu. Không suy ra số tín chỉ chính thức từ UCI.

Môn học lại: trạng thái `failed`/`attempt_count>1` được gắn factor `r_retake` **GIẢ ĐỊNH** {0,9;1,0;1,1}; mặc định trung tâm 1,0, không giả định học lại chắc chắn tốt hơn. `P(Dropout)` không đi vào `p_i`; warning dùng để hiển thị/cố vấn, caps tín chỉ/Fmax là khuyến nghị mềm mặc định, không hard-enforce (`enforce_cap=false`).

### 4.4. Persona và độ nhạy

Persona **SIMULATED** lấy vector feature từ medoid hồ sơ **REAL** ở tầng HK1 tương ứng, sau đó gắn nhãn SIMULATED và dựng tiến độ CTĐT fixture. S002 được kiểm tra thuộc tầng **Trung bình**. Heuristic subset-sum lũy tiến chọn plan lớn hơn bằng cách giữ các môn đã chọn ở budget trước, rồi bổ sung môn chưa học/chưa đạt hợp lịch mở/prerequisite; không dùng ILP:

| Persona / tầng HK1 từ REAL | Budget tín chỉ | Thực chọn | M3′ `p_student` | Expected failures M3′ | Ghi chú (SIMULATED) |
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

Với nested plans, expected failures không giảm khi tăng tải; expected credits passed của persona yếu tăng chậm (M3′ đồng nhất xác suất nên không mô hình hóa bão hòa/giảm). S004 chỉ lấp 14/16 ở ngân sách 15/18; S005 lấp 15 ở budget 18; S006 chỉ còn 2 tín chỉ; S008 không còn môn tương lai. Đây là giới hạn của persona/đồ thị SIMULATED, không thêm môn trái prerequisite để giả tạo khả năng đăng ký.

**Độ nhạy M2 trên plan S003 12 tín chỉ (SIMULATED + GIẢ ĐỊNH):** λ {0;0,1;0,3} × difficulty {0,8;1,0;1,2} × retake {0,9;1,0;1,1} tạo khoảng **3,758010–3,845897 expected failures**, **0,462309–0,725971 expected credits passed** và plan-risk **93,950238–96,147426**. Đây là cực trị của lưới tham số, không phải khoảng tin cậy. `p_student` RF của S003 rất thấp (0,048941), nên đầu ra khác M3′ đáng kể. M3′ là baseline chính; khoảng này minh họa mức phụ thuộc giả định của M2.

## 5. Rule engine: cảnh báo học vụ và điều kiện đăng ký

`evaluate_student` trong `src/rules/rule_engine.py` tách hai loại quyết định:

- `academic_flags`: cảnh báo học vụ từ GPA, tín chỉ chậm tiến độ, môn chưa đạt; **không dùng ML**.
- `eligible_courses`: chưa đạt/chưa học, còn lượt học lại, được mở kỳ tới và thỏa quan hệ prerequisite:
  - `tiên quyết` yêu cầu đã đạt;
  - `học trước` yêu cầu đã học/đang học;
  - `song hành` cho phép nếu học phần kia đã hoàn tất/đang học hoặc cùng được chọn.
  - Được học vượt kỳ dự kiến nếu mở đúng kỳ và đủ prerequisite.
- `progress_stats`: tín chỉ tích lũy/còn thiếu, kỳ tối thiểu còn lại là max(cận dưới theo tín chỉ tối đa/kỳ, chuỗi prerequisite nghiêm ngặt dài nhất).
- `edge_case_flags`: đã đủ tín chỉ tốt nghiệp; không có môn đủ điều kiện; môn bắt buộc không mở kỳ tới; môn bắt buộc bị chặn bởi prerequisite.

### 5.1. Cảnh báo ≠ hạn chế tải

Hai ngưỡng warning được chọn trên 5-fold OOF train **REAL**, theo mục tiêu recall Dropout ≥0,98 và ≥0,90; giá trị 0,029362 và 0,138654, recall tương ứng 0,980651 và 0,900616:

| Tầng cảnh báo | Sinh viên | Tỷ lệ train OOF | Dropout thực tế | PPV trong tầng |
|---|---:|---:|---:|---:|
| Thấp | 450 | 12,72% | 4,89% | 4,89% |
| Trung bình | 1.166 | 32,95% | 7,80% | 7,80% |
| Cao | 1.923 | 54,34% | 53,25% | 53,25% |

Warning ưu tiên recall để hiển thị và đề nghị cố vấn; PPV của warning “Cao” chưa đủ để khóa tải. Restriction mềm **riêng** dùng P(Dropout) isotonic-calibrated OOF, ngưỡng đề xuất `P≥0,50`, chọn theo PPV mục tiêu ≥0,70 và ít nhất 30 mẫu. Độ nhạy **REAL, train OOF calibrated**:

| Threshold | n | PPV | Recall |
|---:|---:|---:|---:|
| 0,50 | 866 | 0,809 | 0,617 |
| 0,65 | 656 | 0,889 | 0,513 |
| 0,75 | 574 | 0,915 | 0,462 |

Trong nhóm 173 sinh viên có P trong ±0,02 quanh tỷ lệ nền 32,13%, **0** người vượt ngưỡng restriction 0,50. Isotonic và chọn ngưỡng cùng OOF nên có optimistic bias; phải xác nhận trên validation độc lập. Mọi cap tín chỉ 18/15/12 và Fmax 2/1,5/1 là khuyến nghị mềm mặc định `enforce_cap: false`, **không phải quy chế**. Cấu hình có thể bật hard cap nhưng chỉ sau duyệt; hiện kịch bản 12/15/18 không bị xóa theo tầng.

## 6. Tối ưu hóa lộ trình bằng ILP

### 6.1. Đầu vào, đầu ra

Đầu vào: `eligible_courses`, `student_profile`, `risk_score` (P(Dropout) thô và hiệu chuẩn), M3′ pass-rate nền theo tầng HK1, scenario 12/15/18 tín chỉ, λ={0;0,1;0,3}. `P(Dropout)` chỉ dùng hiển thị cảnh báo và đề xuất gặp cố vấn; không nhân trực tiếp vào xác suất đạt môn. Tầng nguy cơ không xóa kịch bản tải.

Đầu ra `recommended_plan`: mã môn, tín chỉ, xác suất đạt theo môn, tín chỉ kỳ vọng đạt, số môn trượt kỳ vọng, xác suất có ít nhất 1/2 môn trượt (giả định độc lập), trạng thái chuẩn, cờ `risk_cap_exceeded`/`reduced_load_advised`, cảnh báo và hành động gợi ý.

### 6.2. Mô hình toán học

Với mỗi môn đủ điều kiện `i`, biến nhị phân `x_i∈{0,1}`; `E` là tập môn hợp lệ sau rule engine:

```text
x_i ∈ {0,1}
maximize Σ_i [c_i p_i − γ c_i(1−p_i) + β u_i] x_i − M s

C_min_used ≤ Σ_i c_i x_i ≤ C_scenario
Σ_i (1−p_i) x_i ≤ F_max(tier) + s        (mặc định mềm)
s ≥ 0
x_i ≤ x_prerequisite                   (song hành chưa đạt/đang học)
x_i = 1                                (môn bắt buộc học lại đang chặn chuỗi)
```

- `C_scenario` lần lượt là 12/15/18; các kịch bản được giải độc lập với tầng cảnh báo. Trần tổng 18 là cấu hình fixture. `C_min=12`; nếu không có nghiệm do cận dưới, retry với `C_min_relaxed=6`, bật cờ `reduced_load_advised`. Cả hai là **GIẢ ĐỊNH/TODO: đối chiếu quy chế về học kỳ giảm tải/cảnh báo học vụ**.
- `F_max` theo tầng là khuyến nghị mềm mặc định (`enforce_cap: false`); slack `s` tính số môn kỳ vọng vượt khuyến nghị, phạt `M=1000` tín chỉ tương đương/slack unit trong prototype. Nếu `enforce_cap=true`, Fmax thành ràng buộc cứng; không có nghiệm sau khi thử Cmin giảm thì trả lỗi dữ liệu/infeasible rõ ràng.
- Tiên quyết nghiêm ngặt đã đạt trước kỳ; học trước theo rule engine; song hành chưa hoàn tất buộc chọn đồng thời nếu cả hai đủ điều kiện. Lịch mở/lượt học lại được lọc ở rule engine. Môn bắt buộc học lại đang chặn chuỗi, nếu eligible, là ràng buộc cứng.

### 6.3. Đơn vị hàm mục tiêu và tham số

```text
u_i = Σ_{j ∈ D_i, j chưa hoàn tất} c_j × δ^{d(i,j)}
δ = 0,5
β = 1/8
γ = 1
```

`u_i` là **tín chỉ tương đương mở khóa**: tổng tín chỉ các học phần phụ thuộc bắc cầu chưa hoàn tất, chiết khấu 50% mỗi cạnh prerequisite. Tất cả số hạng đo tín chỉ kỳ vọng/quy đổi:

- `c_i p_i`: tín chỉ đạt kỳ vọng;
- `γ c_i(1−p_i)`: chi phí tín chỉ phải học lại kỳ vọng;
- `β u_i`: giá trị mở khóa đã chiết khấu.

Quy tắc chọn `γ=1` quy một tín chỉ trượt kỳ vọng thành một tín chỉ chi phí học lại; `β=1/8` lấy nghịch đảo khung 8 học kỳ fixture, tức phần tín chỉ tương lai chỉ có giá trị bằng 1/8 một tín chỉ hiện tại. Đây là quy ước cấu hình **GIẢ ĐỊNH**, không phải giá trị ước lượng. Độ nhạy β={0;0,125;0,25;0,5}, γ={0,5;1;2}; không chọn trọng số thuận lợi sau khi xem kết quả.

`F_max` không trùng với chi phí trượt trong mục tiêu: mục tiêu tính chi phí theo số tín chỉ từng môn, còn Fmax giới hạn số môn trượt kỳ vọng không phân biệt số tín chỉ để tránh phương án có nhiều môn rủi ro dù chi phí tín chỉ trung bình thấp. Slack/penalty giúp vẫn trả best effort khi vi phạm khuyến nghị.

### 6.4. Trạng thái chuẩn và chuỗi dự phòng

| Trạng thái | Ý nghĩa |
|---|---|
| `optimal` | Nghiệm tối ưu, không vượt Fmax mềm, Cmin thường. |
| `best_effort` | Vẫn có phương án nhưng vượt Fmax hoặc dùng Cmin giảm tải; kèm cờ và khuyến nghị trao đổi cố vấn. |
| `no_eligible_courses` | Không gọi solver; gợi ý kiểm tra lịch mở/tiên quyết và gặp cố vấn. |
| `graduation_ready` | Đủ tín chỉ tốt nghiệp; không tạo kế hoạch đăng ký giả. |
| `infeasible_data_error` | Cả lượt chuẩn và lượt giảm Cmin đều không tạo nghiệm; cần rà schema, prerequisite, giới hạn và dữ liệu. |

Trạng thái nội bộ PuLP được lưu riêng ở `solver_status`. Fmax được đưa vào trước như slack bị phạt lớn; nếu bài toán vẫn vô nghiệm thì giảm Cmin theo config; không có fallback khả thi mới báo `infeasible_data_error`.

### 6.5. Prototype và tính không suy biến

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

Ablation toy **SIMULATED/GIẢ ĐỊNH** xác nhận objective mở khóa có thể đổi nghiệm và Fmax/penalty slack ảnh hưởng lựa chọn. Unit test bài toán 4 môn giải tay có nghiệm `{A,D}`, objective 4,5 tín chỉ tương đương; toàn bộ tests chạy lại bằng lệnh ở mục 12. Đây là kiểm tra công thức, không chứng minh hiệu quả nghiệp vụ.

**Kiểm tra đơn vị chi tiết:** bốn môn, mỗi môn 3 tín chỉ, ngân sách đúng 6; β=0,125, γ=1; xác suất A=0,90, B=0,50, C=0,60, D=0,85; chỉ C có `u=8` tín chỉ tương đương. Điểm từng môn: A=2,4; B=0; C=1,6; D=2,1. Cặp A+D có objective 4,5, lớn hơn A+C=4,0 và D+C=3,7, do đó nghiệm đã biết là {A,D}. Ablation thứ hai bật giá trị mở khóa để đổi lựa chọn sang môn mở đường; bật Fmax mềm với phạt slack lớn khiến solver ưu tiên phương án trong ngưỡng khi có phương án thay thế.

## 7. Kiến trúc, công nghệ và chức năng dự kiến

### 7.1. Luồng hệ thống

> Giao diện MVP (3 tab nhập/đánh giá/lộ trình) đã chạy được; sơ đồ dưới là kiến trúc đích, phần SHAP và Monte Carlo vẫn ở giai đoạn 2. Dữ liệu chương trình/persona hiện **SIMULATED**; mô hình học **REAL (UCI-697)**. Đầu ra không được diễn giải nhân quả.

```mermaid
flowchart LR
    UCI["REAL (UCI-697)<br/>student records + Target"]
    CUR["SIMULATED / NTU-approved curriculum<br/>courses, prerequisites, openings"]
    PROF["student_profile<br/>T0 + T1_known, current term, progress"]
    PRE["Preprocessing / feature gate<br/>T1 only; remove post-outcome"]
    ML["ML candidate models<br/>LR / RF / XGBoost"]
    SHAP["SHAP explanation<br/>local + global, non-causal"]
    RULE["Rule engine<br/>academic_flags + eligible_courses<br/>progress_stats + edge_case_flags"]
    ILP["ILP planner<br/>x_i, credits/prereq, soft F_max, fallback"]
    MC["Route simulation<br/>12 / 15 / 18 × λ range"]
    UI["Web UI MVP (Streamlit)<br/>profile, risk, plan, comparison"]

    UCI -->|"raw Target + time-stamped attributes"| PRE
    PROF -->|"student_features: T0 + T1_known"| PRE
    PRE -->|"student_features: leakage-filtered schema"| ML
    ML -->|"P(Dropout) raw + calibrated metadata<br/>and pass-rate estimate (separate target)"| SHAP
    ML -->|"risk_score + shap_values<br/>warning tier separate from calibrated soft restriction"| RULE
    PROF -->|"student_profile: completed/failed/in-progress"| RULE
    CUR -->|"courses + prerequisites + semester openings"| RULE
    RULE -->|"eligible_courses[], progress_stats,<br/>academic_flags, warning tier + soft caps (enforce_cap=false)"| ILP
    ML -->|"M3' p_student baseline for pass-rate;<br/>not P(Dropout)"| ILP
    CUR -->|"credits, course type, graph-derived u_i"| ILP
    ILP -->|"3 plans × {12,15,18} × λ; choose recommendation;<br/>expected failures, slack flags, standard status"| MC
    MC -->|"scenario_summary: completion semesters,<br/>on-time probability, credits passed, failures;<br/>range over λ"| UI
    SHAP -->|"risk factors + limitations"| UI
    RULE -->|"flags + progress + eligibility"| UI
    ILP -->|"recommended plan + best-effort/edge status<br/>and suggested action"| UI
```

### 7.2. Hợp đồng dữ liệu giữa các lớp

| Giao diện | Schema tối thiểu |
|---|---|
| ML | Input `student_features` chỉ có `available_at ∈ {T0,T1_known}`; output `risk_score` (P(Dropout), 0–1, kèm trạng thái/metrics hiệu chuẩn) + `shap_values`. Giai đoạn 2 phải fit calibrator trên validation; exploratory hiện tại mới báo Brier/calibration curve, chưa hiệu chuẩn lại. Pass-rate ở HK2 là target khác, không thay risk score. |
| Rule engine | Input `student_profile + curriculum`; output `eligible_courses[]`, `progress_stats`, `academic_flags[]`, `edge_case_flags[]`, warning tier, recommended soft caps và `enforce_cap`. |
| ILP | Input `eligible_courses + M3' p_student + risk constraints`; output các phương án 12/15/18 × λ, `recommended_plan`, p_pass/course, expected failures, slack flags và một trong các status chuẩn. |
| Scenario | Input các plan và khuyến nghị; output phân phối hoàn thành, tín chỉ đạt, failures và so sánh B1–B3. P(đúng hạn) phải gắn chế độ conditional-no-dropout hoặc dropout-hazard. |

### 7.3. Công nghệ đề xuất

| Thành phần | Công nghệ đề xuất | Lý do / rủi ro |
|---|---|---|
| Dữ liệu/ML | Python, pandas, scikit-learn; LR/RF/XGBoost | Tái lập, phù hợp dữ liệu bảng; XGBoost phụ thuộc cài đặt/hiệu chuẩn |
| Giải thích | SHAP | giải thích toàn cục/cục bộ; tương quan feature làm attribution không nhân quả |
| Rule/ILP | Python, YAML, PuLP + HiGHS (hoặc OR-Tools) | quy tắc cấu hình, solver mở; infeasible và trọng số cần giải thích |
| Giao diện | Streamlit | đã dựng MVP 3 tab (persona/nhập tay/CSV); chưa có SHAP/Monte Carlo trên UI |

Màn hình dự kiến: nhập/chọn hồ sơ; P(Dropout) và SHAP; flags/progress; môn đủ điều kiện và thứ tự học lại; phương án 12/15/18 với khoảng theo λ; so sánh ILP với B1–B3. SHAP giải thích tương quan cục bộ/toàn cục, không khẳng định nguyên nhân.

Đánh giá giai đoạn 2: Dropout Precision/Recall/F1/confusion matrix, ưu tiên recall với calibration/Brier; fit calibration trên validation và lưu trạng thái/metrics vào `risk_score`. Hệ thống so với B1–B3 về kỳ hoàn thành, đúng hạn, tín chỉ đạt/kỳ, trượt kỳ vọng, tính khả thi và độ nhạy. Persona cần gồm giỏi/trung bình/yếu, môn nợ chặn chuỗi, môn không mở, ít môn đủ điều kiện, gần tốt nghiệp và hồ sơ thiếu. “Tốt hơn” chưa chốt: đề xuất tiêu chí Pareto—không làm giảm xác suất hoàn thành đúng hạn và cải thiện ít nhất một chỉ số rủi ro/tiến độ trong các khoảng kịch bản; cần cô duyệt trước khi chạy.

## 8. Mô phỏng nhiều kỳ và đối chứng — thiết kế giai đoạn 2

Chưa chạy Monte Carlo nhiều kỳ/đối chứng hoàn chỉnh. Thiết kế **SIMULATED/GIẢ ĐỊNH**, N≥1.000, seed 20261105, λ={0;0,1;0,3}:

1. **Có điều kiện không bỏ học (mặc định):** chỉ mô phỏng pass/fail theo Bernoulli(p_i), không dùng P(Dropout); môn trượt trở lại trạng thái học lại. Mọi xác suất hoàn thành đúng hạn phải ghi rõ chế độ này.
2. **Có hazard bỏ học (độ nhạy):** nếu có P(Dropout) tích lũy cho H kỳ còn lại, giả định hazard hằng kỳ `h=1−(1−P(Dropout))^(1/H)`; mỗi kỳ mô phỏng dropout độc lập với kết quả môn và dừng sinh viên khi event xảy ra. Đây là giả định phân rã xác suất tích lũy, không phải hazard được UCI ước lượng. Mọi xác suất đúng hạn ở chế độ này phải ghi riêng.

Đối chứng cùng persona/seed: **B1** khung kỳ dự kiến + học lại; **B2** greedy tối đa tín chỉ; **B3** cố định 15 tín chỉ; so với ILP. Báo phân phối kỳ hoàn thành, P(đúng hạn), môn trượt kỳ vọng, tín chỉ đạt/kỳ; khoảng min–max theo λ/độ nhạy không gọi là CI. Các môn độc lập là giả định, có thể làm sai phương sai/xác suất hoàn tất.

Tiêu chí Pareto phải chốt trước khi chạy: dùng common random numbers và paired difference giữa hệ thống với từng baseline. Mỗi metric tính sai số chuẩn của paired differences qua N lượt; dung sai 95% là `1,96×SE_difference`. Chênh lệch nằm trong ±dung sai được xem là chưa phân biệt, không tính là cải thiện hay suy giảm. Chỉ tuyên bố ILP “tốt hơn” nếu không có metric chính xấu hơn dung sai và có ít nhất một cải thiện vượt dung sai; phải báo theo từng λ và từng chế độ dropout. Chưa có kết quả hiệu quả giai đoạn 1.

## 9. Phân công và kế hoạch giai đoạn 2

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

## 10. Hạn chế chung

- UCI không có course-level outcomes, difficulty, prerequisites, CTĐT hoặc attempts; mô hình không thể tự suy xác suất đạt từng môn.
- Kết quả ML chỉ exploratory và domain shift từ Bồ Đào Nha sang NTU chưa kiểm định.
- M3′ gồm cả Target=Dropout; non-Dropout-only là phân tích survivor hậu nghiệm, không dùng làm baseline.
- Quan sát tải không nhân quả; `without evaluations` vẫn nằm trong mẫu số proxy.
- M2 difficulty/retake/load và hazard dropout là giả định.
- P(Dropout) hiện có isotonic/threshold trên OOF cùng mẫu nên PPV có optimistic bias.
- Xác suất trượt môn dùng giả định độc lập.
- Chưa chạy Monte Carlo nhiều kỳ/đối chứng B1–B3, chưa làm UI hay chứng minh lợi ích.
- SHAP giải thích mô hình, không nhân quả.
- Độ khó, tín chỉ môn, tiên quyết, lịch mở, attempts đều **SIMULATED**; không có dữ liệu cấp môn UCI.
- M3′ pooling theo năng lực bỏ qua tải và biến cố cá nhân.
- Ngưỡng risk tiers chọn exploratory trên 5-fold OOF train để đạt recall mục tiêu; cần đánh giá lại trên validation/NTU. Không dùng holdout để chọn threshold.

## 11. Câu hỏi cho cô (tối đa 6)

1. **Nhãn và mốc dự báo:** cô có duyệt ba lớp Dropout/Enrolled/Graduate và T1 cuối HK1 trước đăng ký HK2 không? Mặc định nhóm dùng 3 lớp, Enrolled là lớp riêng và loại feature HK2/biến chưa rõ timestamp.
2. **CTĐT/quy chế:** nhóm sẽ tự lấy CTĐT CNTT và quy chế đào tạo từ Trường ĐH Nha Trang; nếu cô muốn áp dụng giới hạn tín chỉ cụ thể hoặc tài liệu cụ thể, xin cô cho biết. Mặc định lưu nguồn/phiên bản, dùng fixture SIMULATED nếu chưa xác minh được tài liệu.
3. **Dùng P(Dropout):** cô có đồng ý cảnh báo và khuyến nghị mềm theo tầng, không hạn chế cứng tải? Mặc định warning chỉ hiển thị/đề nghị gặp cố vấn; cap tín chỉ và Fmax mềm (`enforce_cap=false`), không nhân P(Dropout) vào p_pass môn.
4. **Giả định mô phỏng:** có chấp nhận độc lập giữa môn và lưới λ={0;0,1;0,3}, difficulty/retake là GIẢ ĐỊNH kịch bản để so sánh không? Mặc định hiển thị song song, không chọn một giá trị tối ưu.
5. **Tiêu chí thành công:** có duyệt Pareto so với B1–B3, với dung sai 95% theo sai số chuẩn Monte Carlo (chênh lệch trong dung sai tính là chưa phân biệt) không? Mặc định chốt trước khi chạy và không tuyên bố tốt hơn nếu chưa đạt.
6. **Hạn nộp:** hạn nộp thực tế và số tuần còn lại là khi nào? Mặc định timeline tương đối 8 tuần, điều chỉnh sau khi cô xác nhận.

## 12. Chạy lại và cấu trúc bàn giao

### 12.1. Lệnh chạy lại

Từ gốc repository (Python 3.14):

```bash
python -m pip install -r requirements-stage1.txt
python src/data/generate_simulated_data.py
python src/data/validate_curriculum.py
python src/analysis/risk_to_plan_exploration.py
python src/optimize/plan_risk.py
python -m unittest discover -s tests -v
python src/analysis/ilp_formulation_check.py
python scripts/build_risk_exploration_notebook.py
python scripts/build_ilp_formulation_notebook.py
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/02_risk_to_plan_exploration.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/03_ilp_formulation_check.ipynb
```

Chạy giao diện MVP (Streamlit):

```bash
python -m pip install -r requirements-app.txt
python scripts/train_and_save_models.py      # một lần, tạo artifacts/risk_bundle.joblib
streamlit run app/streamlit_app.py
```

Giao diện có 3 nguồn nhập: **Persona mẫu** (chạy đủ ML), **Nhập tay** và **CSV** (không đủ 24 feature nên bỏ ML risk, lộ trình dùng M3′ và tầng trung bình — ghi rõ trên UI). Kết quả đánh giá và lộ trình giữ trong `st.session_state`; bảng lộ trình tải được CSV.

`reports/generated/` được tái tạo từ pipeline: OOF warning/restriction, calibration deciles, M3′/non-Dropout, persona scenarios, ILP scenarios và recommendation. Notebook chỉ gọi lại pipeline/script, không là mô hình cuối. Validator ghi kết quả vào `reports/curriculum_validation.txt`.

### 12.2. Tệp bàn giao

| Nhóm | Tệp |
|---|---|
| Báo cáo duy nhất | `reports/BAO_CAO.md` |
| Config, rule, plan | `src/config/credit_rules.yaml`, `src/rules/rule_engine.py`, `src/optimize/plan_risk.py` |
| Prototype | `src/optimize/ilp_prototype.py`, `src/analysis/ilp_formulation_check.py`, `notebooks/03_ilp_formulation_check.ipynb` |
| C exploration | `src/analysis/risk_to_plan_exploration.py`, `notebooks/02_risk_to_plan_exploration.ipynb` |
| Persona/data/validation | `src/data/generate_simulated_data.py`, `reports/curriculum_validation.txt`, `reports/data_dictionary.csv` |
| EDA | `notebooks/01_eda_uci697.ipynb` |
| Giao diện MVP | `app/streamlit_app.py`, `src/services/assessment.py`, `src/services/input_validation.py`, `requirements-app.txt` |
| Ví dụ nhập liệu | `samples/` (8 cặp profile/progress + `index.csv` + `invalid/`) |
| Artifact mô hình | `scripts/train_and_save_models.py`, `artifacts/risk_bundle.joblib`, `artifacts/model_metadata.json` |
| Kết quả được sinh | `reports/generated/` |
| Tests | `tests/test_stage1_rules_and_optimizer.py`, `tests/test_services_assessment.py`, `tests/test_app_smoke.py` |

### 12.3. Cấu hình và phương pháp

- `P(Dropout)` dùng riêng cho warning/risk tier và khuyến nghị cố vấn; không nhân trực tiếp vào xác suất đạt môn.
- Warning ngưỡng recall và restriction threshold/PPV độc lập. Restriction threshold isotonic + PPV cùng train OOF có optimistic bias; phải đánh giá trên validation độc lập trước khi áp dụng.
- M3′ pass-rate nền gộp mọi tải theo HK1; λ/difficulty/retake là **GIẢ ĐỊNH** kịch bản. `enrolled_2=0` không bị coi là Dropout/pass=0.
- ILP objective đo tín chỉ tương đương; β=1/8, γ=1 theo quy tắc ở mục 6.3; `u_i` là downstream credits chiết khấu. Fmax là số môn trượt kỳ vọng, khác với loss tín chỉ.
- Status ILP: `optimal`, `best_effort`, `no_eligible_courses`, `graduation_ready`, `infeasible_data_error`; chi tiết ở mục 6.4.
- Chưa có CTĐT/quy chế NTU được xác minh. Cap tín chỉ/GPA/attempts, λ, β/γ, deadline và risk policy đều có source/label/TODO trong `src/config/credit_rules.yaml`.

### 12.4. Giới hạn kết luận

Chưa huấn luyện mô hình cuối, chưa chạy Monte Carlo nhiều kỳ/đối chứng. Giao diện Streamlit hiện là **prototype MVP** (persona/nhập tay/CSV), chưa phải hệ thống production và chưa nối SHAP/Monte Carlo; nhập tay/CSV chỉ dùng rule engine + M3′. Không tuyên bố hiệu quả NTU. Mọi bảng/hồ sơ CTĐT tự dựng ghi **SIMULATED**; kết quả lấy từ UCI ghi **REAL (UCI-697)**; tham số chưa kiểm chứng ghi **GIẢ ĐỊNH**.

## Phụ lục A. Bảng kết quả sinh tự động

Mọi bảng dưới giữ nguyên nhãn nguồn trong tệp:

| Tệp | Nội dung |
|---|---|
| `reports/generated/risk_warning_tier_oof.csv` | Ngưỡng, phân bố và PPV của 3 tầng cảnh báo trên OOF train |
| `reports/generated/risk_restriction_threshold_oof.csv` | Độ nhạy threshold restriction mềm (P calibrated) |
| `reports/generated/pass_rate_calibration_deciles.csv` | Calibration 10 decile của RF pass-rate trên holdout |
| `reports/generated/m3_prime_by_hk1_tier.csv` | M3′ theo tầng HK1 (mọi Target) |
| `reports/generated/m3_prime_non_dropout_by_hk1_tier.csv` | M3′ chỉ Target≠Dropout (survivor-only, đối chiếu) |
| `reports/generated/risk_to_plan_persona_scenarios.csv` | Persona × ngân sách 12/15/18 và expected failures |
| `reports/generated/ilp_prototype_scenarios.csv` | Prototype ILP × persona × ngân sách × λ |
| `reports/generated/ilp_scenario_recommendations.csv` | Khuyến nghị chọn theo tiêu chí mềm |
| `reports/data_dictionary.csv` | Từ điển thuộc tính UCI kèm `available_at`/leakage |
| `reports/curriculum_validation.txt` | Kết quả validator CTĐT **SIMULATED** (PASS) |
