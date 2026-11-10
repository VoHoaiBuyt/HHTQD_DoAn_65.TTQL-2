# Ánh xạ UCI-697 sang CTĐT mô phỏng

**Nhãn dữ liệu:** nguồn học vụ **REAL (UCI-697)**; chương trình và hồ sơ dùng làm fixture **SIMULATED**. Không nối trực tiếp record sinh viên thật với học phần NTU.

## Nguồn và phạm vi CTĐT

- UCI-697: https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success (truy cập 2026-11-05). Tài liệu UCI nói dữ liệu chứa thông tin đầu vào và kết quả học thuật cuối học kỳ 1/2; bảng biến không cung cấp mã học phần/tín chỉ/tiên quyết.
- Bài báo UCI trích dẫn: M. V. Martins, D. Tolledo, J. Machado, L. M. T. Baptista, V. Realinho, “Early prediction of student's performance in higher education: a case study” (2021), https://doi.org/10.1007/978-3-030-72657-7_16. Metadata được kiểm tra qua UCI API/Crossref; toàn văn nhà xuất bản không truy cập được để xác minh thêm timestamp theo từng trường.
- Cổng CTĐT chính thức NTU: https://ctdt.ntu.edu.vn (khảo sát 2026-11-05). Sau khảo sát, PDF `210_CNTT.pdf` được cung cấp; catalogue trong `data/processed/courses.csv` lấy theo mục 7.1 của tài liệu này.
- `student_progress.csv` và `student_profile.csv` trong `data/processed/` vẫn là fixture **SIMULATED**, không phải dữ liệu sinh viên NTU. Tiến độ được dựng lại trên học phần bắt buộc chung; không suy đoán chuyên ngành hoặc xem điểm mô phỏng là dữ liệu thật.

## Giả định nối số học phần

UCI dùng số `curricular units` theo học kỳ, không định danh từng unit bằng mã học phần. Để tạo fixture:

1. Tạm coi **1 curricular unit ≈ 1 học phần** khi tính số học phần đã đăng ký/đạt trong hồ sơ **SIMULATED**.
2. Không suy ra số tín chỉ UCI từ số unit. Tín chỉ của fixture lấy trực tiếp từ từng dòng `courses.csv`.
3. Không thể nối một unit UCI cụ thể với `course_id` mô phỏng; chỉ so sánh ở mức số lượng/tổng hợp.
4. Catalogue mục 7.1 có 101 dòng với lựa chọn tự chọn, ba chuyên ngành và hai phương án tốt nghiệp. Mỗi lộ trình chọn đúng một chuyên ngành, một phương án tốt nghiệp và một lựa chọn cho mỗi ô tự chọn để đạt 130 tín chỉ; không cộng tất cả dòng thay thế thành tín chỉ của một sinh viên.

Các quy ước trên là **giả định mô phỏng**, không phải kết quả thực nghiệm hay dữ liệu đào tạo NTU.

## Giả định quy đổi điểm

UCI mô tả `Curricular units ... (grade)` trên thang 0–20. Để fixture so khớp tên cột, tạm dùng ánh xạ tuyến tính:

- `grade_10 = grade_20 / 2`, giới hạn đầu vào UCI ở `[0, 20]`, kết quả `[0, 10]`.
- `grade_4 = grade_10 × 0.4`, giới hạn kết quả `[0, 4]`.
- Chiều ngược dùng cho cột `Curricular units 1st sem (grade)` của hồ sơ fixture: `grade_20 = grade_10 × 2`.

Đây là **giả định tạm**, không có căn cứ trong tài liệu UCI để khẳng định tương đương thang điểm/quy chế Việt Nam. Phép chia 2 (0–20 → 0–10) chỉ dùng để tạo đặc trưng ML trong fixture; **không dùng để suy ngưỡng đạt học phần của NTU**. Không dùng công thức này để quyết định đạt/trượt; ngưỡng đạt, quy đổi chính thức và GPA cần xác nhận với giảng viên/NTU. Các giá trị `grade_10` của `student_progress.csv` được sinh để phục vụ kiểm thử, không phải kết quả học tập thật.

## Đặc trưng ML có thể/không thể tạo từ hồ sơ mô phỏng

### Có thể tạo ở mức fixture

- Sáu trường HK1: `Curricular units 1st sem (enrolled)` và `approved` đếm từ các hàng fixture; `credited` mặc định 0 khi chưa mô phỏng công nhận tín chỉ; `grade` lấy trung bình điểm đạt trên thang 10 rồi nhân 2; `evaluations` và `without evaluations` đếm theo trạng thái fixture.
- `Age at enrollment` và các trường đầu vào khác được ghi thành giá trị **SIMULATED** theo kịch bản. Mã ngành tuyển sinh, học vấn/quốc tịch/nghề nghiệp phụ huynh dùng mã giống hình thức UCI chỉ để thử schema, không khẳng định mã đó có cùng ý nghĩa/phân phối tại NTU.

### Chưa thể tạo hợp lệ/không dùng ở bộ đặc trưng T1 cơ sở

- `Debtor`, `Tuition fees up to date`, `Scholarship holder`, `Unemployment rate`, `Inflation rate`, `GDP`: tài liệu UCI truy cập được không xác định timestamp cho từng trường. Gắn trạng thái **chưa xác minh**, không đưa vào bộ đặc trưng T1 cơ sở; chỉ bổ sung sau khi có nguồn định thời điểm.
- `Target`: không tạo nhãn giả cho persona, vì không có kết quả cuối kỳ thực nghiệm.
- `Curricular units 2nd sem (credited)` và `(enrolled)`: là biến quyết định/đầu vào mô phỏng phương án tại T1, không phải feature đã quan sát cho ML.
- Sáu feature đầu vào T0 của UCI có thể điền thành mã mô phỏng trong fixture, nhưng ý nghĩa/miền giá trị không đồng nhất với hồ sơ thật NTU. Không coi các mã này là dữ liệu triển khai.

## Những gì ML UCI không biết

Mô hình học từ dữ liệu **REAL (UCI-697)** không có thông tin định danh từng học phần, số tín chỉ môn, độ khó học phần, quan hệ tiên quyết, lịch mở môn hay lựa chọn tổ hợp môn trong CTĐT NTU. Mô hình không thể tự suy ra rủi ro đạt của từng môn/plan từ `risk_score` tổng thể. Các yếu tố môn học/tiên quyết chỉ có trong bảng **SIMULATED**; mọi cách dùng chúng để điều chỉnh rủi ro phương án cần được nêu là giả định và phải kiểm chứng ở giai đoạn sau.
