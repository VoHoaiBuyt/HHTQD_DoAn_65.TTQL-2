# Đặc tả bài toán tối ưu hóa lộ trình (giai đoạn thiết kế)

> Catalogue/persona **SIMULATED**, pass-rate nền **REAL (UCI-697)** exploratory; mọi giá trị chính sách là **GIẢ ĐỊNH/TODO** cho tới khi đối chiếu CTĐT/quy chế NTU. Prototype chỉ kiểm tra công thức, không chứng minh hiệu quả.

## 1. Đầu vào, đầu ra và tách cảnh báo

Đầu vào gồm `eligible_courses`, `student_profile`, `risk_score` (P(Dropout) thô và hiệu chuẩn), M3' pass-rate nền theo tầng HK1, scenario 12/15/18 tín chỉ, λ={0;0,1;0,3}. `P(Dropout)` dùng để hiển thị cảnh báo và đề xuất gặp cố vấn; không nhân trực tiếp vào xác suất đạt môn. Tầng nguy cơ không xóa kịch bản tải.

Đầu ra `recommended_plan`: mã môn, tín chỉ, xác suất đạt theo môn, tín chỉ kỳ vọng đạt, số môn trượt kỳ vọng, xác suất có ít nhất 1/2 môn trượt (giả định độc lập), trạng thái chuẩn, cờ `risk_cap_exceeded`/`reduced_load_advised`, cảnh báo và hành động gợi ý. Nếu không có môn đủ điều kiện hoặc đủ tín chỉ tốt nghiệp, trả trạng thái chuyên biệt.

## 2. Xác suất và quy đổi tải

```text
p_i = clip(p_M3'(ability) × f_difficulty(i) × r_retake(i) × g_load, 0, 1)
g_load = exp(−λ × max(0, U_scenario − median_units_REAL))
U_scenario = floor(C_scenario / mean_credits_per_course_SIMULATED + 0.5)
```

Tải được cố định theo ngân sách kịch bản trước khi giải để giữ ILP tuyến tính; đây là xấp xỉ, không phải hiệu ứng nhân quả. `mean_credits_per_course` từ fixture là 128/48=2,6667 tín chỉ/môn **SIMULATED**; trung vị enrollment HK2 UCI là 6 **REAL**. Half-up `floor(x+0.5)` cho 4,5→5, không dùng bankers rounding; phép quy đổi đơn điệu. UCI curricular unit không phải tín chỉ NTU.

M3' là tỷ lệ pass gộp mọi mức tải theo tầng HK1: Thấp 0,248377; Trung bình 0,779404; Cao 0,931902 **REAL**. `f_difficulty` suy từ trung vị điểm nhóm trong catalogue/tiến độ mô phỏng; `r_retake` có lưới {0,9;1,0;1,1}; λ={0;0,1;0,3}. Difficulty, retake và λ là **GIẢ ĐỊNH**; hiệu ứng tải chỉ đi qua `g_load`.

## 3. Mô hình tối ưu ILP

Với `i ∈ E`, `E` là tập môn hợp lệ sau rule engine:

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
- `F_max` theo tầng là khuyến nghị mềm mặc định, cấu hình `enforce_cap: false`; slack `s` tính số môn kỳ vọng vượt khuyến nghị, phạt `M=1000` tín chỉ tương đương/slack unit trong prototype. Nếu `enforce_cap=true`, Fmax thành ràng buộc cứng; không có nghiệm sau khi thử Cmin giảm thì trả lỗi dữ liệu/infeasible rõ ràng.
- Tiên quyết nghiêm ngặt đã đạt trước kỳ; học trước theo rule engine; song hành chưa hoàn tất buộc chọn đồng thời nếu cả hai đủ điều kiện. Lịch mở/lượt học lại được lọc ở rule engine. Môn bắt buộc học lại đang chặn chuỗi, nếu eligible, là ràng buộc cứng.
- Nếu không còn môn eligible: `no_eligible_courses`, gợi ý kiểm tra lịch mở/tiên quyết và gặp cố vấn. Nếu đủ tín chỉ tốt nghiệp: `graduation_ready`, không tạo kế hoạch đăng ký giả.

### Đơn vị hàm mục tiêu và tham số

```text
u_i = Σ_{j ∈ D_i, j chưa hoàn tất} c_j × δ^{d(i,j)}
δ = 0,5
β = 1/8
γ = 1
```

`u_i` là **tín chỉ tương đương mở khóa**: tổng tín chỉ các học phần phụ thuộc bắc cầu chưa hoàn tất, chiết khấu 50% mỗi cạnh prerequisite. Tất cả số hạng đo tín chỉ kỳ vọng/quy đổi: `c_i p_i` là tín chỉ đạt kỳ vọng; `γ c_i(1−p_i)` là chi phí tín chỉ phải học lại kỳ vọng; `βu_i` là giá trị mở khóa đã chiết khấu. Quy tắc chọn `γ=1` quy một tín chỉ trượt kỳ vọng thành một tín chỉ chi phí học lại; `β=1/8` lấy nghịch đảo khung 8 học kỳ fixture, tức phần tín chỉ tương lai chỉ có giá trị bằng 1/8 một tín chỉ hiện tại. Đây là quy ước cấu hình **GIẢ ĐỊNH**, không phải giá trị ước lượng. Phân tích độ nhạy β={0;0,125;0,25;0,5}, γ={0,5;1;2}; không chọn trọng số thuận lợi sau khi xem kết quả.

`F_max` không trùng với chi phí trượt trong mục tiêu: mục tiêu tính chi phí theo số tín chỉ từng môn, còn Fmax giới hạn số môn trượt kỳ vọng không phân biệt số tín chỉ để tránh phương án có nhiều môn rủi ro dù chi phí tín chỉ trung bình thấp. Slack/penalty giúp vẫn trả best effort khi vi phạm khuyến nghị.

## 4. Trạng thái chuẩn và chuỗi dự phòng

`optimal`: nghiệm tối ưu, không vượt Fmax mềm, Cmin thường. `best_effort`: vẫn có phương án nhưng vượt Fmax hoặc dùng Cmin giảm tải; kèm cờ và khuyến nghị trao đổi cố vấn. `no_eligible_courses`/`graduation_ready`: không gọi solver. `infeasible_data_error`: cả lượt chuẩn và lượt giảm Cmin đều không tạo nghiệm, cần rà schema, prerequisite, giới hạn và dữ liệu. Trạng thái nội bộ PuLP được lưu riêng ở `solver_status`.

### Nhãn hiển thị và mức cảnh báo

- `risk_focused`: “Ưu tiên giảm rủi ro”; `balanced`: “Cân bằng”;
  `acceleration`: “Tăng tốc”. Đây là nhãn chiến lược, độc lập với trạng thái
  bộ giải.
- Mức cảnh báo giao diện là `GIẢ ĐỊNH`: CAO nếu số môn trượt kỳ vọng ≥1,0,
  P(W1) ≥0,5 hoặc P(W2) ≥0,5; TRUNG BÌNH nếu số môn trượt kỳ vọng ≥0,5;
  còn lại THẤP. CAO luôn có cảnh báo đỏ và khuyến nghị trao đổi với cố vấn.
- `optimal` chỉ nói nghiệm tối ưu theo hàm mục tiêu và các ràng buộc được mô
  hình hóa; không kết luận phương án đó phù hợp nhất về mặt học vụ. `best_effort`,
  xung đột quy chế và vượt trần rủi ro tiếp tục có cảnh báo riêng.

Fmax được đưa vào trước như slack bị phạt lớn; nếu bài toán vẫn vô nghiệm thì giảm Cmin theo config; không có fallback khả thi mới báo `infeasible_data_error`. Prototype S003 dùng Cmin=12, Fmax=1, `enforce_cap=false`: phải trả kế hoạch 12 tín chỉ với `status=best_effort`, `risk_cap_exceeded=true`, số vượt cap và gợi ý gặp cố vấn. Nếu sau này bật hard cap thì không được che giấu tình trạng không khả thi.

## 5. Kiểm tra đơn vị và không suy biến

Unit test giải tay bài toán bốn môn, mỗi môn 3 tín chỉ, ngân sách đúng 6; β=0,125, γ=1; xác suất A=0,90, B=0,50, C=0,60, D=0,85; chỉ C có `u=8` tín chỉ tương đương. Điểm từng môn: A=2,4; B=0; C=1,6; D=2,1. Cặp A+D có objective 4,5, lớn hơn A+C=4,0 và D+C=3,7, do đó nghiệm đã biết là {A,D}; test kiểm chứng objective và nghiệm. Các xác suất/điểm là fixture **SIMULATED/GIẢ ĐỊNH**, không phải kết quả REAL.

Test ablation thứ hai bật giá trị mở khóa để đổi lựa chọn sang môn mở đường; bật Fmax mềm với phạt slack lớn khiến solver ưu tiên phương án trong ngưỡng khi có phương án thay thế. Kết quả kiểm thử không khẳng định objective đúng chính sách; β/γ và Fmax cần duyệt.

## 6. Prototype 4 persona và khuyến nghị

PuLP/HiGHS giải riêng từng persona × {12,15,18} × λ={0;0,1;0,3}, không áp cứng trần tầng theo mặc định. Mỗi λ chọn một khuyến nghị từ các phương án khả thi thỏa `expected_failures ≤ F_max` và cận kỳ tối thiểu phù hợp deadline; ưu tiên tín chỉ đạt kỳ vọng, sau đó ít môn trượt và ngân sách nhỏ hơn. Nếu không phương án nào thỏa, chọn best effort ít rủi ro hơn và nêu hành động gặp cố vấn. Tầng cảnh báo chỉ gắn nhãn/rà soát, không xóa kịch bản.

Mọi persona/CTĐT là **SIMULATED**, feature vector được lấy làm medoid trong phân vị tầng HK1 của hồ sơ **REAL**, và giá trị course/difficulty/λ là **GIẢ ĐỊNH**. Chạy lại bằng `python src/analysis/ilp_formulation_check.py`; đầu ra CSV tại `reports/generated/ilp_prototype_scenarios.csv` và `ilp_scenario_recommendations.csv`. Các con số persona chỉ là sanity-check logic.

## 7. Monte Carlo, bỏ học và tiêu chí so sánh

Chưa chạy Monte Carlo nhiều kỳ. Giai đoạn 2 dùng N≥1.000, seed 20261105, common random numbers giữa ILP/B1/B2/B3:

1. **Có điều kiện không bỏ học (mặc định):** chỉ mô phỏng kết quả pass/fail môn theo Bernoulli(p_i), không dùng P(Dropout); thất bại chuyển thành môn học lại, cập nhật tiến độ/eligibility.
2. **Có hazard bỏ học (độ nhạy):** nếu chỉ có P(Dropout) tổng trong H kỳ còn lại, giả định hazard hằng kỳ `h=1−(1−P(Dropout))^(1/H)`; mỗi kỳ mô phỏng bỏ học độc lập với môn và dừng sinh viên khi event xảy ra. Đây là giả định phân rã xác suất tích lũy, không phải hazard được UCI ước lượng. Báo rõ chế độ cạnh mọi P(đúng hạn).

B1 là khung kỳ dự kiến + học lại; B2 greedy tối đa tín chỉ; B3 cố định 15 tín chỉ. Cùng persona, seed, λ, kỳ hạn và eligibility. Báo phân phối kỳ hoàn thành, P(đúng hạn), môn trượt kỳ vọng, tín chỉ đạt/kỳ; khoảng min–max theo λ/độ nhạy không gọi là CI. Độc lập giữa môn là giả định và có thể làm sai phương sai/xác suất hoàn tất.

Tiêu chí Pareto phải chốt trước khi chạy: dùng chênh lệch paired theo cùng seed; với từng metric tính sai số chuẩn của chênh lệch từ N lượt và dung sai `1,96 × SE_difference`. Chỉ coi đúng hạn/tín chỉ đạt cải thiện khi vượt dung sai theo chiều tốt; chỉ coi expected failures/kỳ hoàn thành suy giảm khi xấu hơn dung sai; biến động nằm trong ±dung sai được xem là chưa phân biệt được, không tuyên bố cải thiện/suy giảm. ILP chỉ “tốt hơn” nếu không có metric chính xấu quá dung sai và có ít nhất một cải thiện vượt dung sai; báo riêng từng λ/chế độ dropout.
