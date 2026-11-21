# 📘 ÔN TẬP VẤN ĐÁP — Hệ thống Hỗ trợ Cảnh báo Học vụ & Tối ưu Lộ trình Tín chỉ

> Tài liệu ôn thi môn **Hệ hỗ trợ ra quyết định (DSS)** — tổng hợp từ mã nguồn `app/`, `src/`, `scripts/` và 3 notebook trong `notebooks/`.
> Mẹo học: mỗi phần có **🎯 Câu chốt** — học thuộc câu này trước, phần giải thích để trả lời khi bị hỏi sâu.

---

## 🧭 Tóm tắt 30 giây (học thuộc nguyên văn)

> "Hệ thống của nhóm em là một **DSS hướng mô hình** giúp **cố vấn học tập** và **sinh viên** trả lời 2 câu hỏi: *(1) sinh viên này có nguy cơ bỏ học không, vì sao?* và *(2) kỳ tới nên đăng ký những môn nào, bao nhiêu tín chỉ?*
> Hệ thống kết hợp 4 khối: **Học máy** (Logistic Regression dự báo P(Dropout) + SHAP giải thích), **Bộ luật** (Rule Engine kiểm tra tiên quyết, lịch mở môn, cảnh báo học vụ), **Tối ưu ILP** (PuLP + HiGHS chọn tập môn tối ưu dưới ràng buộc tín chỉ và rủi ro), và **Mô phỏng Monte Carlo** (1.000 lượt để so sánh chiến lược ILP với 3 cách đăng ký thông thường B1/B2/B3). Giao diện làm bằng **Streamlit**. Hệ thống chỉ **khuyến nghị**, không tự động hạn chế quyền đăng ký của sinh viên."

---

# PHẦN 1. LÝ DO RA ĐỜI & MỤC ĐÍCH CỦA HỆ THỐNG

## 1.1. Vấn đề thực tế (vì sao cần hệ thống?)

| Đối tượng | Khó khăn hiện tại |
|---|---|
| **Sinh viên** | Mỗi kỳ phải **tự chọn môn và số tín chỉ**. Đăng ký **quá nhiều** dễ trượt nhiều môn, bị cảnh báo học vụ. Đăng ký **quá ít** thì chậm tốt nghiệp. Không nắm hết **chuỗi môn tiên quyết**: trượt một môn nền tảng (ví dụ IT202) có thể chặn cả chuỗi môn phía sau (IT203 → IT304). |
| **Cố vấn học tập** | Phụ trách nhiều sinh viên nên **không thể xem kỹ từng hồ sơ**. Thường chỉ phát hiện sinh viên yếu **khi đã quá muộn** (đã bị cảnh báo, đã nợ nhiều môn). Thiếu công cụ để **định lượng** rủi ro và **so sánh** các phương án đăng ký. |
| **Nhà trường** | Tỷ lệ bỏ học cao gây lãng phí. Trong dữ liệu UCI, **32,12%** sinh viên bỏ học. |

## 1.2. Vì sao đây là bài toán của môn DSS?

Theo lý thuyết DSS, đây là **bài toán bán cấu trúc** (semi-structured):
- **Phần có cấu trúc** (máy làm được): quy chế tín chỉ min/max, môn tiên quyết, lịch mở kỳ chẵn/lẻ, tính xác suất, giải bài toán tối ưu.
- **Phần phi cấu trúc** (con người quyết định): hoàn cảnh riêng của sinh viên, động lực học, nguyện vọng tốt nghiệp sớm hay an toàn. Những thứ này máy không đo được.

➡ Vì vậy hệ thống **không ra quyết định thay** mà **hỗ trợ**: đưa ra *cảnh báo + giải thích + nhiều phương án + mô phỏng hệ quả*, để **cố vấn và sinh viên chọn**. Đây chính là tinh thần DSS: *"hỗ trợ, không thay thế người ra quyết định"*.

Hệ thống đi đủ **4 pha ra quyết định của Simon**:

| Pha của Simon | Hệ thống làm gì |
|---|---|
| **Intelligence** (nhận diện vấn đề) | Dự báo P(Dropout), gắn mức cảnh báo Thấp/Trung bình/Cao, bật cờ học vụ (GPA thấp, nợ môn, chậm tiến độ). |
| **Design** (thiết kế phương án) | Rule Engine lọc môn đủ điều kiện. ILP tạo phương án cho các mức 12/15/18 tín chỉ. |
| **Choice** (lựa chọn) | Bảng so sánh phương án (tín chỉ đạt kỳ vọng, số môn trượt kỳ vọng, vượt ngưỡng hay không) và phân tích Pareto. |
| **Implementation / Review** | Tải kế hoạch học tập ra file CSV. Mô phỏng Monte Carlo kiểm tra hệ quả dài hạn. |

## 1.3. Mục đích cụ thể

1. **Cảnh báo sớm** tại mốc **T1** (ngay sau khi có điểm HK1, trước khi đăng ký HK2), lúc vẫn còn kịp can thiệp.
2. **Giải thích được** (Explainable AI): dùng SHAP cho biết *yếu tố nào* đẩy rủi ro lên hoặc xuống, để cố vấn có lý do khi trao đổi với sinh viên.
3. **Đề xuất lộ trình tối ưu**: chọn môn sao cho tối đa tín chỉ đạt được và mở khóa các môn kỳ sau, đồng thời kiểm soát số môn trượt.
4. **So sánh chiến lược** bằng mô phỏng, thay vì nói cảm tính "học ít cho an toàn".
5. **Minh bạch nguồn dữ liệu**: mọi con số đều gắn nhãn **REAL (UCI-697)** / **SIMULATED** / **GIẢ ĐỊNH**.

## 1.4. Giá trị cho từng người dùng

- **Cố vấn học tập**: lọc nhanh sinh viên nguy cơ cao, có bằng chứng (SHAP) để tư vấn, có sẵn 3 phương án để so sánh trong buổi gặp.
- **Sinh viên**: biết môn nào được đăng ký, môn nào bị chặn và vì sao, xác suất qua từng môn, nên chọn 12, 15 hay 18 tín chỉ.

🎯 **Câu chốt:** *"Bài toán đăng ký tín chỉ là bài toán bán cấu trúc: quy chế và xác suất thì máy tính được, nhưng quyết định cuối cùng phụ thuộc hoàn cảnh sinh viên. Vì vậy cần DSS để kết hợp mô hình định lượng với phán đoán của cố vấn, chứ không dùng một hệ tự động ra quyết định."*

## 1.5. Dữ liệu dùng trong hệ thống (rất hay bị hỏi)

| Nhãn | Dữ liệu | Dùng để |
|---|---|---|
| **REAL (UCI-697)** | Bộ *Predict Students' Dropout and Academic Success*: 4.424 sinh viên, 37 thuộc tính, dữ liệu Bồ Đào Nha. | Huấn luyện mô hình dự báo bỏ học và tỷ lệ đạt môn. |
| **SIMULATED** | CTĐT mô phỏng 48 học phần (128 tín chỉ, 8 học kỳ), 40 quan hệ tiên quyết, 8 hồ sơ sinh viên mẫu S001–S008. | Kiểm thử Rule Engine, ILP, Monte Carlo. |
| **GIẢ ĐỊNH** | λ (hệ số tải) = 0,1, β = 0,125, γ = 1,0, ngưỡng trượt, hệ số học lại… | Tham số kịch bản, có phân tích độ nhạy. |

⚠ **Hạn chế phải tự nói ra trước:** mô hình học trên dữ liệu Bồ Đào Nha, **chưa kiểm định trên sinh viên NTU**. CTĐT là mô phỏng. Kết quả chỉ để tham khảo.

---

# PHẦN 2. HƯỚNG DẪN SỬ DỤNG & GIẢI THÍCH CHỨC NĂNG GIAO DIỆN (`app/streamlit_app.py`)

**Chạy ứng dụng:**
```bash
source .venv/bin/activate
streamlit run app/streamlit_app.py      # mở http://localhost:8501
```
(Nếu chưa có file mô hình `artifacts/risk_bundle.joblib`, chạy trước: `python scripts/train_and_save_models.py`.)

**Bố cục:** thanh bên trái (sidebar) chọn **nguồn dữ liệu** và hiện ghi chú nguồn dữ liệu. Khu vực chính có **4 tab** đi theo đúng quy trình ra quyết định:

```
📋 Nhập hồ sơ  →  📊 Đánh giá  →  🗺️ Lộ trình  →  🎲 Mô phỏng
 (Dữ liệu)        (Intelligence)    (Design/Choice)   (Đánh giá chiến lược)
```

## 2.1. Sidebar: chọn nguồn dữ liệu

Radio **"Nguồn dữ liệu"** có 3 lựa chọn:

| Chế độ | Người dùng làm gì | Có dự báo ML không? |
|---|---|---|
| **Hồ sơ mẫu (Có sẵn)** | Chọn 1 trong 8 sinh viên mẫu S001–S008 ở ô *"Chọn hồ sơ sinh viên mẫu"*. | ✅ **Có**: hồ sơ mẫu có đủ 24 đặc trưng mà mô hình cần. |
| **Nhập thủ công** | Gõ mã SV, học kỳ hiện tại, GPA (hệ 4), tín chỉ tích lũy, số môn chưa đạt, số môn HK1 đăng ký/đạt, điểm TB HK1 (thang 20). Sửa trực tiếp bảng tiến độ (trạng thái, điểm, số lần học). | ❌ Không: thiếu 24 đặc trưng. Hệ thống dùng **tỷ lệ nền theo nhóm năng lực HK1 (M3′)**. |
| **Tải lên file CSV** | Tải 2 file `profile.csv` (1 dòng) và `progress.csv`. Có nút **"Tải mẫu profile.csv / progress.csv"** để lấy file mẫu. | ❌ Không (như trên). |

8 hồ sơ mẫu: S001 *Giỏi, đúng tiến độ* · S002 *Trung bình* · S003 *Yếu, chậm tiến độ* · S004 *Nhiều môn nợ* · S005 *Nợ môn chặn chuỗi tiên quyết* · S006 *Gần tốt nghiệp, còn 1 môn nợ* · S007 *Trượt môn nền tảng* · S008 *Giỏi, gần hoàn tất*.

## 2.2. Tab 📋 "Nhập hồ sơ"

- **Hiển thị:** bảng tiến độ học tập (mã học phần, trạng thái *Đã hoàn thành / Chưa đạt / Đang học / Chưa học*, điểm hệ 10, số lần học, học kỳ).
- **Bấm nút:** **"Phân tích & Đánh giá rủi ro"** (nút xanh).
- **Hệ thống làm:** kiểm tra dữ liệu đầu vào (`input_validation.py`: điểm 0–10, mã môn phải có trong CTĐT, không trùng, tiến độ phải đúng mã SV) rồi gọi `assess_student()`, tức chạy ML + Rule Engine.
- **Kết quả:** thông báo *"Đã phân tích hồ sơ… chuyển sang tab Đánh giá"*. Nếu dữ liệu sai sẽ báo lỗi đỏ, ghi rõ dòng nào sai.

## 2.3. Tab 📊 "Đánh giá": kết quả đánh giá rủi ro & điều kiện đăng ký

| Thành phần | Ý nghĩa |
|---|---|
| **4 thẻ số liệu** | *Mức cảnh báo rủi ro* (Thấp/Trung bình/Cao/Chưa ước lượng) · *Xác suất rủi ro bỏ học* (đã hiệu chuẩn isotonic) · *Nhóm năng lực HK1* (Thấp/TB/Cao) · *Số học phần đủ điều kiện đăng ký*. |
| **Huy hiệu màu** | ✅ xanh = Thấp · ⚠️ vàng = Trung bình · 🔴 đỏ = Cao. |
| **Dòng phụ** | *Dự báo tỷ lệ đạt môn (Random Forest)* và *Tỷ lệ nền theo nhóm năng lực (M3′)*. |
| **Bảng "Cảnh báo học vụ"** | Cờ từ bộ luật: `LOW_GPA` (GPA < 2,0), `FAILED_COURSES` (còn môn nợ), `CREDITS_BEHIND` (chậm ≥ 12 tín chỉ so với tiến độ chuẩn). |
| **Bảng "Lưu ý đặc biệt"** | `GRADUATION_CREDITS_MET` (đủ tín chỉ tốt nghiệp), `NO_ELIGIBLE_COURSES`, `REQUIRED_COURSE_NOT_OFFERED` (môn bắt buộc kỳ tới không mở), `REQUIRED_COURSE_BLOCKED` (môn bắt buộc bị chặn bởi tiên quyết). |
| **Tổng quan tiến độ tín chỉ** | Tín chỉ đã tích lũy · còn lại · chậm so với tiến độ · số học kỳ tối thiểu còn lại · chuỗi tiên quyết dài nhất. |
| **Học phần đủ điều kiện đăng ký** | Danh sách môn được phép học kỳ tới (môn nợ được xếp lên đầu). |
| **Học phần cần học lại** | Các môn trượt. |
| **Học phần chưa đủ điều kiện tiên quyết** | Môn bị chặn và môn tiên quyết nào chưa đạt. |
| **Biểu đồ SHAP** | Top 10 yếu tố ảnh hưởng đến dự báo bỏ học (chỉ có ở chế độ hồ sơ mẫu). |

## 2.4. Tab 🗺️ "Lộ trình": so sánh các phương án tín chỉ (ILP)

**Người dùng chỉnh 4 tham số:**
1. **"Mức tín chỉ cần so sánh"**: chọn nhiều mức trong 12 / 15 / 18.
2. **"Hệ số tải học tập λ"**: thanh trượt 0 → 0,5, mặc định 0,1. Đây là giả định "học càng nhiều thì xác suất qua môn càng giảm".
3. **"Ngưỡng môn không đạt cho phép" (Fmax)**: mặc định theo mức rủi ro (Thấp 2,0 · TB 1,5 · Cao 1,0).
4. **Checkbox "Áp giới hạn tín chỉ khuyến nghị"**: mặc định **TẮT**. Khi tắt, hệ thống chỉ cảnh báo chứ không giới hạn cứng.

**Bấm nút "Lập & so sánh lộ trình"**: hệ thống gọi `build_plans()` và giải bài toán ILP cho từng mức tín chỉ.

**Kết quả nhận được:**
- **Biểu đồ cột nhóm**: tín chỉ đăng ký so với tín chỉ dự báo đạt cho từng mức.
- **Bảng "So sánh các phương án"**: kết quả (*Tối ưu ✅ / Nỗ lực tối đa ⚠️ / Không khả thi ❌ / Đủ ĐK tốt nghiệp 🎓*), tín chỉ đăng ký, tín chỉ dự báo đạt, số môn không đạt dự báo, ngưỡng trượt, có vượt ngưỡng không, chế độ dự phòng.
- **"Xem chi tiết phương án"**: chọn 1 mức để xem 4 thẻ số liệu, thông báo (xanh = ổn, vàng = nên giảm tải, đỏ = cần gặp cố vấn) và **bảng môn đề xuất kèm thanh "Xác suất đạt (%)"**.
- **Nút "Tải xuống kế hoạch học tập (CSV)"**.
- Nếu đổi tham số mà chưa bấm lại nút, hệ thống báo *"kết quả hiển thị là từ lần chạy trước"*.

## 2.5. Tab 🎲 "Mô phỏng": Monte Carlo so sánh chiến lược

(Không cần đánh giá hồ sơ trước. Tab này đọc kết quả có sẵn trong `reports/generated/`.)
- **Bảng tổng hợp 7 hồ sơ × 1.000 lượt**: tỷ lệ tốt nghiệp, tỷ lệ đúng hạn (kèm KTC 95%), tỷ lệ khả thi, số môn trượt trung bình, tín chỉ trung bình, số học kỳ trung bình, có nằm trên biên **Pareto** không.
- **2 hình**: biểu đồ Pareto và biểu đồ tỷ lệ tốt nghiệp (giải thích ở Phần 4).
- **Bộ lọc** theo sinh viên và theo chiến lược, kèm bảng chi tiết từng sinh viên.
- **Bảng "So sánh hiệu quả với ILP"**: chênh lệch ghép cặp ILP − B1/B2/B3, KTC 95%, có khác biệt rõ rệt không (✅ nếu khoảng tin cậy không chứa 0).

Cuối trang có ô **"ℹ️ Lưu ý về phạm vi & nguồn gốc dữ liệu"**.

🎯 **Câu chốt:** *"Giao diện đi theo đúng 4 bước: nhập dữ liệu → đánh giá rủi ro → lập phương án → mô phỏng chiến lược. Người dùng không cần biết thuật toán, chỉ cần chọn hồ sơ, bấm 2 nút và đọc bảng so sánh."*

---

# PHẦN 3. GIẢI THÍCH CÁC THUẬT TOÁN & MÔ HÌNH

## Sơ đồ tổng thể luồng dữ liệu

```
Hồ sơ SV (24 đặc trưng T0+T1) ──► [ML1] Logistic Regression ──► P(Dropout) ──► Isotonic ──► P đã hiệu chuẩn
                               │                                   │
                               │                                   └──► Phân tầng Thấp/TB/Cao ──► Fmax, trần tín chỉ khuyến nghị
                               ├──► [ML2] Random Forest Regressor ──► tỷ lệ đạt môn (tham khảo)
                               └──► Tỷ lệ HK1 đạt/đăng ký ──► Nhóm năng lực ──► [M3′] tỷ lệ đạt nền p₀

Tiến độ học tập + CTĐT ──► [RULE] Rule Engine ──► môn đủ ĐK / bị chặn / nợ, cờ cảnh báo
                                                       │
p₀ × độ khó × hệ số tải × hệ số học lại ──► p_i ───────┴──► [ILP] PuLP + HiGHS ──► Phương án 12/15/18 TC
                                                                     │
                                                    [MC] Monte Carlo 1.000 lượt × 16 học kỳ ──► so sánh ILP vs B1/B2/B3
```

---

## 3.1. Notebook 01 — EDA (khảo sát dữ liệu UCI-697)

- **Input:** `data/raw/uci_697/data.csv` (4.424 dòng × 37 cột).
- **Làm gì:** kiểm tra chất lượng dữ liệu (**0 giá trị thiếu, 0 dòng trùng**), phân phối nhãn, tương quan với Dropout, **phân nhóm thuộc tính theo thời điểm quan sát**.
- **Output / kết luận quan trọng nhất:** chia thuộc tính thành:
  - **T0** (lúc nhập học, 18 thuộc tính): tuổi, giới tính, điểm xét tuyển, nghề/trình độ cha mẹ…
  - **T1_known** (sau HK1, 6 thuộc tính): số môn HK1 đăng ký, đạt, điểm TB HK1…
  - **T1_decision** (quyết định đăng ký HK2): **không được** dùng làm đặc trưng.
  - **post_outcome** (kết quả HK2, Target): **cấm dùng**, vì dùng là **rò rỉ dữ liệu (data leakage)**.
  - **Chưa xác minh** (Debtor, học phí, học bổng, GDP, lạm phát, thất nghiệp): loại bỏ.
- **Vì sao quan trọng:** HK2 có tương quan mạnh nhất với Dropout (r ≈ −0,57), nhưng tại thời điểm cần cảnh báo (T1) ta **chưa có** điểm HK2. Dùng nó sẽ làm mô hình đẹp trên giấy nhưng **vô dụng khi triển khai**. Vì vậy mô hình chỉ dùng **24 đặc trưng = 18 T0 + 6 T1_known**.

## 3.2. [ML1] Mô hình dự báo bỏ học: **Logistic Regression đa lớp** (Notebook 02, mục C.1)

- **Input:** 24 đặc trưng. Biến phân loại được **One-Hot Encoding**, biến số được **StandardScaler** chuẩn hóa.
- **Output:** xác suất 3 lớp **Dropout / Enrolled / Graduate**. Hệ thống lấy **P(Dropout)**.
- **Cách huấn luyện:** chia 80/20 có phân tầng (stratified), **5-fold Stratified Cross-Validation**, seed cố định 20261105.
- **Kết quả (holdout):** Accuracy CV ≈ **0,714** · Precision Dropout ≈ **0,70** · **Recall Dropout ≈ 0,72** · F1 Dropout ≈ **0,71** · Brier ≈ **0,121**.
- **Vì sao chọn Logistic Regression?** (`scripts/benchmark_risk_models.py` đã so sánh **LR, Random Forest, LightGBM**):
  1. Kết quả tương đương mô hình phức tạp: trên tập test LR có **F1 Dropout 0,689 / ROC-AUC 0,860 / PR-AUC 0,774**, tốt nhất trong 3 mô hình.
  2. **Hiệu chuẩn tốt nhất**: ECE = 0,035, thấp nhất (RF là 0,060). Với DSS, *xác suất phải đáng tin*, vì 30% phải thật sự nghĩa là 30%.
  3. **Dễ giải thích**: hệ số tuyến tính, dùng được SHAP LinearExplainer chính xác và nhanh.
  4. Dữ liệu nhỏ (~4.400 dòng) nên mô hình đơn giản ít bị overfit.
- **Vì sao giữ 3 lớp?** Lớp *Enrolled* (vẫn đang học, chưa tốt nghiệp) **không đồng nghĩa** với "an toàn", nên không gộp vào Graduate.

## 3.3. Hiệu chuẩn xác suất: **Isotonic Regression**

- **Input:** P(Dropout) thô từ dự đoán out-of-fold (OOF).
- **Output:** P(Dropout) **đã hiệu chuẩn**, là con số hiển thị trên giao diện.
- **Vì sao:** xác suất thô của mô hình có thể bị lệch (ví dụ dự đoán 40% nhưng thực tế chỉ 30% bỏ học). Isotonic là hàm **đơn điệu tăng**, chỉ "nắn" lại thang xác suất cho khớp tỷ lệ thực tế, **không làm thay đổi thứ hạng** của sinh viên.

## 3.4. Phân tầng cảnh báo Thấp / Trung bình / Cao

- **Cách chọn ngưỡng:** dựa trên **Recall** trong validation OOF, không chọn cảm tính.
  - P ≤ **0,029** → **Thấp**. Ngưỡng này là ngưỡng lớn nhất mà vẫn bắt được ≥ **98%** sinh viên bỏ học.
  - P ≤ **0,139** → **Trung bình**. Ngưỡng lớn nhất bắt được ≥ **90%** sinh viên bỏ học.
  - Lớn hơn nữa → **Cao**.
- **Kết quả kiểm định:** nhóm Cao có tỷ lệ bỏ học thực tế **53,3%**, nhóm TB **7,8%**, nhóm Thấp **4,9%**. Nghĩa là các tầng **phân biệt rõ** mức rủi ro.
- **Vì sao ưu tiên Recall?** Trong cảnh báo sớm, **bỏ sót một sinh viên sắp bỏ học (False Negative) tốn kém hơn nhiều** so với nhắc nhầm một sinh viên an toàn (False Positive). Bị nhắc nhầm thì chỉ mất một buổi gặp cố vấn.
- Mỗi tầng gắn với tham số khuyến nghị: **trần tín chỉ** 18/15/12 và **Fmax** 2,0/1,5/1,0. Ngoài ra chỉ khi **P đã hiệu chuẩn ≥ 0,50** (ngưỡng chọn để PPV ≥ 0,70) mới *khuyến nghị giảm tải*, và mặc định **không áp cứng**.

## 3.5. Giải thích mô hình: **SHAP (LinearExplainer)**

- **Input:** hồ sơ 1 sinh viên + 120 mẫu nền (background) từ UCI.
- **Output:** với mỗi đặc trưng, một giá trị SHAP. **Dương → đẩy rủi ro bỏ học lên**, **âm → kéo rủi ro xuống**. Tổng các giá trị SHAP + giá trị nền = dự đoán.
- **Vì sao dùng:** DSS cần **minh bạch**. Cố vấn không thể nói "máy bảo em có nguy cơ" mà phải nói được *"vì số môn HK1 em đạt thấp"*. SHAP dựa trên **lý thuyết trò chơi (giá trị Shapley)**, chia công bằng "công/tội" cho từng yếu tố.
- **Toàn cục (top theo mean|SHAP|):** ① **Số môn đạt HK1** (mạnh nhất, vượt xa các yếu tố khác) ② Số môn đăng ký HK1 ③ Tuổi nhập học ④ Điểm TB HK1 ⑤ Số môn được công nhận.
- ⚠ **SHAP giải thích mô hình, KHÔNG chứng minh nhân quả.**

## 3.6. [ML2] Dự báo tỷ lệ đạt môn: **Random Forest Regressor** (Notebook 02, mục C.2)

- **Input:** 24 đặc trưng (như trên).
- **Output:** tỷ lệ đạt HK2 = *số môn đạt HK2 / số môn đăng ký HK2* (giá trị 0–1).
- **Cấu hình:** 160 cây, `min_samples_leaf=8`, `max_features=0.8`. Loại 180 SV không đăng ký HK2 vì không có mẫu số.
- **Kết quả:** MAE ≈ **0,124**, RMSE ≈ **0,193** (sai số trung bình khoảng 12 điểm phần trăm).
- **Vì sao Random Forest:** quan hệ phi tuyến, ít cần chỉnh tham số, chịu được nhiễu. Có thử hiệu chuẩn isotonic nhưng không cải thiện nên giữ mô hình thô.
- **Vai trò trên app:** hiển thị **để tham khảo**. Xác suất đưa vào ILP lại dùng M3′ (xem dưới) vì M3′ ổn định hơn và có thể tính cả khi nhập tay.

## 3.7. [M3′] Tỷ lệ đạt nền theo **nhóm năng lực HK1**

- **Input:** tỷ lệ *môn đạt HK1 / môn đăng ký HK1*.
- **Cách làm:** chia SV UCI thành 3 nhóm theo phân vị: **Thấp** (< 0,667), **Trung bình** (0,667 – < 1), **Cao** (= 1, đạt hết). Với mỗi nhóm, tính **tỷ lệ đạt gộp ở HK2** từ dữ liệu thật:
  - Thấp ≈ **24,8%** (1.683/6.776) · Trung bình ≈ **77,9%** (7.349/9.429) · Cao ≈ **93,2%** (10.592/11.366).
- Nếu một nhóm có < 30 sinh viên thì gộp với nhóm kề để tránh ước lượng từ mẫu quá nhỏ.
- **Output:** `p₀`, xác suất qua một môn "trung bình" của sinh viên.
- **Vì sao:** đơn giản, có căn cứ dữ liệu thật, giải thích được ("sinh viên như em, ở kỳ sau trung bình qua 78% số môn") và dùng được ngay cả khi chỉ biết kết quả HK1.

## 3.8. Mô hình xác suất qua từng môn (M2, `plan_risk.py`)

$$p_i = p_0 \times f_{\text{độ khó}}(i) \times g_{\text{tải}} \times r_{\text{học lại}} \quad (\text{cắt về } [0,1])$$

- **f_độ khó**: theo nhóm môn, bằng *trung vị điểm nhóm / trung vị điểm chung* (SIMULATED, cắt ở phân vị 10–90%). **> 1 là nhóm dễ**, < 1 là nhóm khó. Ví dụ *Cơ sở toán học* = 0,88 (khó), *Hệ thống thông tin* = 1,17 (dễ).
- **g_tải** = `exp(−λ × max(0, số_học_phần − 6))`. Học ≤ 6 học phần (khoảng 16 tín chỉ) thì không bị phạt, vượt thì xác suất giảm dần theo hàm mũ. **λ = 0,1 là GIẢ ĐỊNH**, vì dữ liệu thật **không cho thấy** học nhiều làm tăng bỏ học (OR ≈ 1,0005 cho mỗi môn thêm). Do đó phải làm **phân tích độ nhạy** với λ ∈ {0; 0,1; 0,3}.
- **r_học lại** = 1,0 (giả định thận trọng: thi lại không dễ hơn).
- **Từ p_i suy ra cho cả kế hoạch:** tín chỉ đạt kỳ vọng = Σ cᵢ·pᵢ · số môn trượt kỳ vọng = Σ(1−pᵢ) · P(trượt ≥ 1 môn) = 1 − Π pᵢ (giả định các môn **độc lập**).

## 3.9. [RULE] Bộ luật nghiệp vụ: **Rule Engine** (`src/rules/rule_engine.py`)

- **Input:** hồ sơ, CTĐT (môn, tín chỉ, kỳ mở), bảng tiên quyết, tiến độ học, file cấu hình `credit_rules.yaml`.
- **Các luật chính:**
  1. **Ứng viên**: chỉ xét môn *chưa học* hoặc *đã trượt*. Bỏ môn đã học quá **3 lần**.
  2. **Lịch mở môn**: kỳ tới là lẻ thì chỉ lấy môn mở kỳ lẻ (`odd`), kỳ chẵn lấy môn `even`, môn `both` luôn được lấy.
  3. **Tiên quyết** có 3 loại:
     - *tiên quyết*: phải **đã đạt** môn trước.
     - *học trước*: chỉ cần **đã học** (đạt, trượt hoặc đang học đều được).
     - *song hành*: môn kia đã đạt/đang học **hoặc** cũng đủ điều kiện để học cùng kỳ.
  4. **Thuật toán điểm bất động (fixed point):** bắt đầu từ tất cả ứng viên, lặp lại việc loại các môn không thỏa điều kiện cho tới khi tập không đổi. Cách này xử lý đúng cặp **song hành** (A cần B, B cần A) và lan truyền việc bị chặn theo chuỗi.
  5. **Cờ học vụ:** GPA < 2,0 (`LOW_GPA`), còn môn nợ (`FAILED_COURSES`), chậm ≥ 12 tín chỉ so với tiến độ chuẩn (`CREDITS_BEHIND`), môn bắt buộc không mở/bị chặn, đủ tín chỉ tốt nghiệp.
  6. **Thống kê tiến độ:** học kỳ tối thiểu còn lại = max(⌈tín chỉ còn / trần⌉, **chuỗi tiên quyết dài nhất**). Chuỗi dài nhất tính bằng **đệ quy có ghi nhớ (DFS + memo) trên đồ thị DAG** tiên quyết.
- **Output:** danh sách môn đủ ĐK / bị chặn (kèm lý do) / cần học lại, cờ cảnh báo, mức rủi ro, trần tín chỉ khuyến nghị, Fmax.
- **Vì sao dùng luật (không dùng ML):** quy chế là **tri thức tường minh, bắt buộc đúng 100%**. Luật dễ kiểm tra, dễ sửa khi quy chế đổi (chỉ cần sửa YAML) và giải thích được. ML không phù hợp để "đoán" quy chế.

## 3.10. [ILP] Tối ưu lộ trình: **Quy hoạch nguyên nhị phân** bằng PuLP + HiGHS (`src/optimize/ilp_prototype.py`, Notebook 03)

**Biến quyết định:** xᵢ ∈ {0, 1}, bằng 1 nếu đăng ký môn i (chỉ xét môn đủ điều kiện).

**Hàm mục tiêu (tối đa hóa):**
$$\max \sum_i x_i\Big[\underbrace{c_i p_i}_{\text{TC đạt kỳ vọng}} + \underbrace{\beta\, u_i}_{\text{giá trị mở khóa}} - \underbrace{\gamma\, c_i (1-p_i)}_{\text{phạt TC trượt}}\Big] \;-\; 1000\cdot s$$

- cᵢ: số tín chỉ · pᵢ: xác suất đạt · **uᵢ (unlock value)**: tổng tín chỉ các môn *phía sau* mà môn i mở khóa, mỗi bậc chiết khấu ×0,5 (môn con ×0,5, môn cháu ×0,25…) · **β = 0,125** (= 1/8 học kỳ) · **γ = 1** (1 TC trượt = 1 TC phải học lại) · s: biến "chùng" (slack) của ràng buộc rủi ro.

**Ràng buộc:**
1. **Tín chỉ:** `C_min (12) ≤ Σ cᵢxᵢ ≤ C_max` (12/15/18 theo kịch bản).
2. **Rủi ro (mềm):** `Σ (1 − pᵢ)xᵢ ≤ Fmax + s`, tức số môn trượt kỳ vọng không vượt ngưỡng. Nếu buộc phải vượt thì s > 0 và bị phạt 1000 mỗi đơn vị, đồng thời trạng thái thành *best_effort*.
3. **Song hành:** `x_A ≤ x_B` (học A thì phải học B cùng kỳ nếu B chưa đạt).
4. **Bắt buộc học lại:** môn bắt buộc đã trượt mà đang chặn chuỗi (uᵢ > 0) thì `xᵢ = 1`.

**Kỹ thuật bổ sung:**
- **Tinh chỉnh tải lặp (tối đa 3 vòng):** pᵢ phụ thuộc vào số tín chỉ thực tế đăng ký, mà số tín chỉ lại do ILP chọn. Vì vậy hệ thống giải lần 1 với trần, tính lại pᵢ theo số tín chỉ thật rồi giải lại cho tới khi ổn định.
- **Chuỗi dự phòng (fallback)** khi không có nghiệm: nới sàn 12 → 6 TC → 0 TC (ít nhất 1 môn) → bỏ ép học lại → nới ngưỡng trượt. Hệ thống **luôn cố đưa ra phương án** và ghi rõ đã nới ràng buộc nào.
- **Trạng thái kết quả:** `optimal` / `best_effort` / `graduation_ready` / `no_eligible_courses` / `infeasible_data_error`.
- Có sẵn hàm `solve_plan_variants` tạo 3 biến thể (An toàn: β=0, γ×2,5 · Tiến độ: β×4, γ×0,3 · Cân bằng). Giao diện hiện so sánh theo **3 mức tín chỉ** 12/15/18.

**Vì sao dùng ILP?**
- Chọn môn là bài toán **"chọn hay không chọn"**, thuộc dạng **bài toán cái túi (knapsack)** có thêm ràng buộc. Biến nhị phân mô tả đúng bản chất.
- Có **nhiều ràng buộc cứng** (tín chỉ, song hành, học lại) mà phương pháp tham lam dễ vi phạm hoặc bỏ lỡ nghiệm tốt.
- ILP **đảm bảo nghiệm tối ưu toàn cục** theo mô hình. HiGHS là bộ giải mã nguồn mở, nhanh (chưa tới 1 giây với ~20 môn).
- Hàm mục tiêu **đa tiêu chí** cân bằng 3 mục tiêu mâu thuẫn: *qua nhiều tín chỉ* ↔ *ít trượt* ↔ *mở khóa môn chiến lược*.

**Kiểm chứng trong Notebook 03 (ablation):** ví dụ đồ chơi 4 môn A, B, C, D:
- Tắt cả uᵢ và Fmax → chọn **A, D** (dễ qua nhất).
- Bật uᵢ → chọn **A, C** (C khó nhưng mở khóa nhiều môn), số trượt kỳ vọng tăng lên 0,85.
- Bật thêm Fmax = 0,8 → mô hình bị buộc quay về phương án an toàn hơn.

➡ Chứng minh **mỗi thành phần trong mô hình đều có tác dụng thật** (không suy biến). Notebook 03 còn chạy 4 persona × 3 mức tín chỉ × λ, và **độ nhạy β ∈ {0; 0,125; 0,25; 0,5}, γ ∈ {0,5; 1; 2}**.

## 3.11. [MC] **Mô phỏng Monte Carlo** (`scripts/monte_carlo_strategies.py`)

- **Mục đích:** ILP chỉ tối ưu **1 học kỳ**. Câu hỏi dài hạn là *nếu theo một chiến lược suốt khóa học thì có tốt nghiệp đúng hạn không?* Không có dữ liệu thật để thử nên phải **mô phỏng**.
- **4 chiến lược so sánh:**
  - **ILP**: phương án tối ưu, trần 18 tín chỉ.
  - **B1**: đúng lộ trình CTĐT, ưu tiên học lại môn trượt.
  - **B2**: tham lam, đăng ký tối đa 18 tín chỉ.
  - **B3**: cố định 15 tín chỉ mỗi kỳ.
- **Quy trình mỗi lượt:** từ học kỳ hiện tại tới tối đa **học kỳ 16**, mỗi kỳ: Rule Engine lọc môn → chiến lược chọn môn → **tung đồng xu Bernoulli** cho từng môn (qua nếu số ngẫu nhiên < pᵢ) → cập nhật trạng thái. Dừng khi đủ **128 tín chỉ**.
- **Thiết kế thống kê:**
  - **1.000 lượt** × 7 hồ sơ × 4 chiến lược (S008 đã đủ tín chỉ nên loại).
  - Dùng **"số ngẫu nhiên chung" (Common Random Numbers)**: mọi chiến lược gặp **cùng một chuỗi may rủi**, nên khác biệt giữa chúng là do chiến lược chứ không phải do may mắn.
  - **KTC 95% bằng bootstrap** (lấy mẫu lại 1.000 lần).
  - **Biên Pareto**: chiến lược không bị chiến lược nào khác tốt hơn ở *cả hai* chỉ tiêu (ít trượt hơn **và** đúng hạn nhiều hơn).
- **Output (tổng hợp):**

| Chiến lược | Tốt nghiệp (≤ HK16) | Đúng hạn (≤ HK8) | Khả thi | Số lượt trượt TB | Pareto |
|---|---|---|---|---|---|
| **ILP** | 44,3% | 4,0% | **51,6%** (cao nhất) | **12,01** (thấp nhất) | ✅ |
| B1 | 45,0% | **6,1%** (cao nhất) | 38,3% | 12,44 | ✅ |
| B2 | 43,4% | 4,4% | 38,0% | 12,83 | — |
| B3 | 45,3% | 0,0% | 40,9% | 12,29 | — |

- **Kết luận trung thực:** ILP **giảm số môn trượt** có ý nghĩa thống kê so với cả 3 chiến lược (ILP−B2: −0,82 môn, KTC không chứa 0) và **khả thi nhất**. Tuy nhiên **B1 đúng hạn cao hơn** ILP (+2,1 điểm %). ILP và B1 cùng nằm trên **biên Pareto**, tức **không có chiến lược nào tốt nhất mọi mặt, chỉ có đánh đổi**. Đây là thông tin quan trọng cho người ra quyết định.
- **Vì sao dùng Monte Carlo:** hệ thống có **tính ngẫu nhiên** (qua/trượt), **nhiều kỳ phụ thuộc nhau** (trượt kỳ này thì kỳ sau bị chặn), nên không giải được bằng công thức đóng. Mô phỏng nhiều lần cho ra **phân phối kết quả** thay vì một con số duy nhất.

## 3.12. Phân tích độ nhạy & các phân tích chẩn đoán (Notebook 02)

- **C.3 Tải và kết quả quan sát:** bảng tỷ lệ đạt theo *nhóm năng lực × số môn đăng ký HK2* cho thấy **học nhiều không làm tỷ lệ đạt giảm**. Nhóm TB: 1–5 môn 75,6%, 6–7 môn 73,0%, 8+ môn **84,2%**. Lý do là **thiên lệch chọn lọc**: sinh viên giỏi mới dám đăng ký nhiều. ➡ Không được suy ra nhân quả từ dữ liệu quan sát, nên **λ phải là giả định + phân tích độ nhạy**.
- **M1 (phản thực tế chẩn đoán):** thử đưa biến "số môn đăng ký HK2" vào mô hình. Kết quả không cải thiện Brier (0,1214 so với 0,1211), và đây là biến quyết định, không phải biến quan sát được tại T1. ➡ **Bị loại** khỏi phương pháp chính.
- **C.6 Kiểm tra logic:** tăng ngân sách tín chỉ thì số môn trượt kỳ vọng **không giảm** và tín chỉ đạt **không giảm** (tính đơn điệu). Tất cả assert đều qua.
- **C.7 Độ nhạy:** thay đổi λ ∈ {0; 0,1; 0,3}, độ khó ×{0,8; 1; 1,2}, hệ số học lại ×{0,9; 1; 1,1}.

🎯 **Câu chốt Phần 3:** *"ML trả lời 'ai có nguy cơ', SHAP trả lời 'vì sao', Rule Engine trả lời 'được học môn gì', ILP trả lời 'nên học môn gì', còn Monte Carlo trả lời 'làm vậy lâu dài thì sao'."*

---

# PHẦN 4. Ý NGHĨA CÁC BIỂU ĐỒ

## 4.1. Biểu đồ trong Notebook

### 📊 Biểu đồ 1: "Phân phối Target — REAL (UCI-697)" (Notebook 01)
- **Loại:** cột đứng. **Trục X:** trạng thái (Dropout · Enrolled · Graduate). **Trục Y:** số sinh viên.
- **Số liệu:** Dropout **1.421 (32,12%)** · Enrolled **794 (17,95%)** · Graduate **2.209 (49,93%)**.
- **Insight:** cứ **3 sinh viên thì có 1 người bỏ học**, cho thấy vấn đề đáng giải quyết. Dữ liệu **mất cân bằng vừa phải**, nên phải chia tập có **phân tầng (stratify)** và đánh giá bằng **F1 / Recall của lớp Dropout** thay vì chỉ nhìn Accuracy.
- **Giúp quyết định:** chọn bài toán 3 lớp và chọn chỉ số đánh giá phù hợp.

### 📊 Biểu đồ 2: "Tương quan đơn biến với Dropout" (Notebook 01)
- **Loại:** cột ngang, top 12. **Trục X:** hệ số tương quan Pearson r (âm = càng cao càng ít bỏ học). **Trục Y:** tên thuộc tính.
- **Số liệu:** điểm HK2 (−0,57), số môn đạt HK2 (−0,57), **điểm HK1 (−0,48), số môn đạt HK1 (−0,48)**, đóng học phí đúng hạn (−0,43), tuổi nhập học (+0,25), học bổng (−0,25), nợ học phí (+0,23), giới tính (+0,20).
- **Insight:** **kết quả học tập kỳ đầu là tín hiệu cảnh báo mạnh nhất**. Nhưng các biến HK2 chỉ biết **sau** khi đăng ký, nên dùng sẽ bị **rò rỉ dữ liệu**. Các biến tài chính chưa xác minh được nên cũng bị loại.
- **Giúp quyết định:** chọn **mốc cảnh báo T1** (ngay sau HK1) và tập 24 đặc trưng hợp lệ. Tương quan **không phải nhân quả**.

### 📊 Biểu đồ 3: "Calibration — REAL (UCI-697)" (Notebook 02, mục C.1)
- **Loại:** đường + điểm. **Trục X:** P(Dropout) dự đoán trung bình theo từng nhóm (bin). **Trục Y:** tỷ lệ bỏ học thực tế trong nhóm. **Đường chéo nét đứt** là hiệu chuẩn hoàn hảo.
- **Cách đọc:** điểm nằm **sát đường chéo** nghĩa là mô hình nói 30% thì thực tế ≈ 30%. Điểm nằm **dưới** đường chéo là mô hình *phóng đại* rủi ro, **trên** là *đánh giá thấp* rủi ro.
- **Insight:** mô hình bám khá sát đường chéo (Brier ≈ 0,12), xác suất đủ tin cậy để dùng làm cảnh báo, và được tinh chỉnh thêm bằng Isotonic.
- **Giúp quyết định:** người dùng có thể tin **con số xác suất**, không chỉ tin thứ hạng.

*(Notebook 02 và 03 còn nhiều **bảng** quan trọng: ma trận nhầm lẫn, bảng tỷ lệ đạt theo nhóm năng lực × tải, bảng kết quả ILP 4 persona × 12/15/18, bảng độ nhạy β/γ, bảng ablation. Xem Phần 3.)*

**Ma trận nhầm lẫn (holdout) — nên nhớ:**

| Thực tế \ Dự đoán | Dropout | Enrolled | Graduate |
|---|---|---|---|
| **Dropout** | **204** | 20 | 60 |
| **Enrolled** | 48 | 46 | 65 |
| **Graduate** | 39 | 24 | **379** |

➡ Bắt đúng 204/284 sinh viên bỏ học (≈ 72%). Lớp *Enrolled* khó dự đoán nhất vì nằm "lưng chừng".

## 4.2. Biểu đồ trên App và trong báo cáo

### 📊 Biểu đồ 4: "Các yếu tố ảnh hưởng đến dự báo rủi ro bỏ học (SHAP)" (tab Đánh giá)
- **Loại:** cột ngang, top 10. **Trục X:** giá trị SHAP (mức độ ảnh hưởng). **Trục Y:** tên đặc trưng. Có đường dọc tại 0.
- **Màu:** 🔴 **đỏ = làm tăng rủi ro** (SHAP > 0) · 🟢 **xanh = làm giảm rủi ro** (SHAP < 0). Thanh càng dài thì ảnh hưởng càng lớn.
- **Insight:** cho **từng sinh viên** biết lý do. Ví dụ: "số môn đạt HK1 thấp" là thanh đỏ dài nhất, còn "điểm xét tuyển cao" là thanh xanh.
- **Giúp quyết định:** cố vấn biết **nên can thiệp vào đâu**, ví dụ hỗ trợ học lại các môn HK1. Một số yếu tố như tuổi, nghề cha mẹ thì không thay đổi được, chỉ dùng để hiểu bối cảnh. Đây là giải thích **mô hình**, không phải nhân quả.

### 📊 Biểu đồ 5: "So sánh phương án tín chỉ" (tab Lộ trình)
- **Loại:** cột nhóm. **Trục X:** mức tín chỉ (12 TC · 15 TC · 18 TC). **Trục Y:** số tín chỉ. **2 cột mỗi nhóm:** 🔵 *Tín chỉ đăng ký* · 🟢 *Tín chỉ dự báo đạt*.
- **Insight:** **khoảng cách giữa cột xanh dương và cột xanh lá = số tín chỉ có thể trượt**. Nếu tăng từ 15 lên 18 TC mà cột "dự báo đạt" gần như không tăng thì **học thêm không đáng**, vì chỉ tăng rủi ro (hiệu ứng **lợi ích biên giảm dần** do hệ số tải).
- **Giúp quyết định:** chọn mức tín chỉ cân bằng giữa tiến độ và rủi ro.
- *Đi kèm:* cột **"Xác suất đạt (%)"** dạng thanh tiến trình cho từng môn đề xuất.

### 📊 Biểu đồ 6: "Pareto chiến lược đăng ký" (tab Mô phỏng, `monte_carlo_pareto.png`)
- **Loại:** điểm có thanh sai số (error bar). **Trục X:** số môn trượt kỳ vọng (**càng thấp càng tốt**). **Trục Y:** xác suất tốt nghiệp đúng hạn (**càng cao càng tốt**). Mỗi điểm là 1 chiến lược (ILP, B1, B2, B3). Thanh sai số là **KTC 95%**.
- **Cách đọc:** vùng **lý tưởng là góc trên bên trái** (ít trượt, đúng hạn cao). Nếu 2 thanh sai số **chồng lên nhau** thì khác biệt chưa chắc có thật.
- **Insight:** **ILP lệch trái nhất** (ít trượt nhất), **B1 cao nhất** (đúng hạn nhiều nhất). Cả hai nằm trên **biên Pareto**, còn B2 và B3 bị lấn át.
- **Giúp quyết định:** sinh viên **sợ trượt / đang bị cảnh báo** nên theo ILP, sinh viên **ưu tiên tốt nghiệp đúng hạn** có thể cân nhắc B1. Không có chiến lược tối ưu tuyệt đối.

### 📊 Biểu đồ 7: "Tỷ lệ tốt nghiệp theo chiến lược" (tab Mô phỏng, `monte_carlo_rates.png`)
- **Loại:** cột nhóm. **Trục X:** 4 chiến lược. **Trục Y:** tỷ lệ (0–1). **2 cột:** 🔵 *Tốt nghiệp trong giới hạn 16 kỳ* · 🔴 *Tốt nghiệp đúng hạn (≤ HK8)*.
- **Insight:** tỷ lệ tốt nghiệp trong 16 kỳ của 4 chiến lược **gần bằng nhau** (~43–45%), nhưng tỷ lệ **đúng hạn rất thấp** (0–6%). Lý do là các hồ sơ mẫu cố tình được chọn là ca khó (nợ môn, chậm tiến độ). B3 (15 TC/kỳ) **0% đúng hạn** vì 15 × 8 = 120 < 128 tín chỉ, **về mặt số học không thể** tốt nghiệp đúng hạn.
- **Giúp quyết định:** cho thấy với sinh viên đã chậm tiến độ, **"đăng ký ít cho an toàn" (B3) gần như chắc chắn trễ hạn**. Cần cân nhắc kỹ khi khuyên giảm tải.

### 📊 Biểu đồ 8 (báo cáo): "15 đặc trưng ảnh hưởng mạnh nhất — SHAP toàn cục" (`reports/generated/shap_dropout_top15*.png`)
- **Trục X:** mean(|SHAP|) cho lớp Dropout (độ lớn ảnh hưởng trung bình trên toàn bộ dữ liệu). **Trục Y:** đặc trưng.
- **Insight:** **số môn đạt HK1** áp đảo (≈ 1,33, gấp gần 3 lần yếu tố thứ hai). Tiếp theo là số môn đăng ký HK1, tuổi, điểm HK1.
- **Giúp quyết định:** khẳng định chính sách "**theo dõi sát kết quả học kỳ 1**" là đòn bẩy cảnh báo sớm quan trọng nhất.

---

# PHẦN 5. 15 CÂU HỎI VẤN ĐÁP DSS KÈM ĐÁP ÁN MẪU

## 🅰 Nhóm 1: Ba thành phần của DSS (Dữ liệu – Mô hình – Giao diện)

### Câu 1. Hệ thống của em có đủ 3 thành phần của một DSS không? Chỉ rõ từng thành phần.
**Đáp:** Có, đủ 3 thành phần:
- **Phân hệ quản lý dữ liệu (Data):** dữ liệu thật UCI-697 (4.424 SV), CTĐT và tiến độ mô phỏng (`data/simulated/`), cấu hình quy chế `credit_rules.yaml`, file mô hình đã huấn luyện `risk_bundle.joblib`. Có tầng **kiểm tra dữ liệu đầu vào** (`input_validation.py`).
- **Phân hệ quản lý mô hình (Model):** Logistic Regression + Isotonic, Random Forest, M3′, SHAP, Rule Engine, ILP (PuLP/HiGHS), Monte Carlo. Tất cả gom về tầng dịch vụ `src/services/assessment.py`.
- **Phân hệ giao diện (Dialog/UI):** Streamlit 4 tab, có bảng, biểu đồ, thanh trượt tham số, nút tải CSV.
- Ngoài ra còn **người dùng** (cố vấn, sinh viên), là thành phần thứ 4 theo một số giáo trình.

### Câu 2. Dữ liệu huấn luyện là của Bồ Đào Nha, vậy có áp dụng được cho sinh viên NTU không?
**Đáp:** Chưa áp dụng trực tiếp được, và nhóm em ghi rõ điều đó trên giao diện. Nhóm dùng UCI-697 vì đây là bộ dữ liệu thật, công khai, có nhãn bỏ học, trong khi dữ liệu NTU là dữ liệu cá nhân nhạy cảm. Hệ thống được thiết kế **tách rời dữ liệu khỏi mô hình**: khi có dữ liệu NTU chỉ cần chạy lại `train_and_save_models.py` và cập nhật file YAML, giao diện và thuật toán giữ nguyên. Mọi kết quả đều gắn nhãn **REAL / SIMULATED / GIẢ ĐỊNH** để người dùng không hiểu nhầm.

### Câu 3. Làm sao em tránh rò rỉ dữ liệu (data leakage)?
**Đáp:** Nhóm phân loại **thời điểm quan sát** của từng thuộc tính (T0, T1_known, T1_decision, post_outcome). Mô hình chỉ dùng **24 đặc trưng biết được tại T1**: 18 thông tin đầu vào và 6 kết quả HK1. **Loại toàn bộ biến HK2** dù chúng tương quan mạnh nhất (r ≈ −0,57), và loại 6 biến tài chính/kinh tế chưa xác minh. Notebook 02 có câu `assert` tự động kiểm tra không có biến cấm nào lọt vào. Ngoài ra **ngưỡng phân tầng được chọn trên dữ liệu out-of-fold** của tập huấn luyện, tập test chỉ chấm điểm **một lần**.

### Câu 4. Vì sao lại dùng file YAML cấu hình mà không viết cứng các ngưỡng vào code?
**Đáp:** Đây là nguyên tắc **tách tri thức nghiệp vụ khỏi mã nguồn** trong phân hệ mô hình của DSS. Quy chế đào tạo (min/max tín chỉ, số lần học lại, ngưỡng GPA) có thể thay đổi theo từng năm và từng trường. Với YAML, phòng đào tạo **sửa một con số là hệ thống cập nhật**, không cần lập trình lại. Mỗi tham số trong YAML còn ghi **nguồn gốc và nhãn** (SIMULATED/GIẢ ĐỊNH/TODO xác nhận), giúp minh bạch và dễ kiểm toán.

### Câu 5. Giao diện của em hỗ trợ người ra quyết định như thế nào, chứ không chỉ hiển thị kết quả?
**Đáp:** Giao diện hỗ trợ theo 4 cách:
1. **Phân tích "What-if"**: người dùng tự đổi λ, Fmax, mức tín chỉ, bật/tắt trần tín chỉ rồi xem kết quả thay đổi ra sao.
2. **So sánh nhiều phương án song song** (12/15/18 TC) thay vì đưa ra một đáp án duy nhất.
3. **Giải thích** bằng SHAP và lý do bị chặn của từng môn.
4. **Cảnh báo màu** và thông báo hành động ("Trao đổi với cố vấn học tập").

Giao diện cũng đi đúng trình tự ra quyết định Simon (nhận diện → thiết kế → lựa chọn). Hệ thống **không tự động khóa đăng ký**, quyền quyết định thuộc về con người.

## 🅱 Nhóm 2: Độ tin cậy của dự báo

### Câu 6. Mô hình dự báo đúng bao nhiêu phần trăm? Như vậy có đủ tốt không?
**Đáp:** Accuracy khoảng **71%**, **Recall lớp Dropout ≈ 72%**, Precision ≈ 70%, F1 ≈ 0,71, ROC-AUC trên tập test ≈ 0,86. Accuracy không phải chỉ số quan trọng nhất. Trong cảnh báo sớm, quan trọng là **bắt được sinh viên sắp bỏ học (Recall)**. Vì vậy khi phân tầng, nhóm chọn ngưỡng để tầng "Trung bình trở lên" bắt được **≥ 98%** và tầng "Cao" bắt được **≥ 90%** sinh viên bỏ học. Mô hình chỉ dùng dữ liệu đến hết HK1, nên mức này là hợp lý. Đây cũng là công cụ **sàng lọc**, quyết định cuối cùng vẫn do cố vấn đưa ra.

### Câu 7. Vì sao không dùng mô hình mạnh hơn như LightGBM hay Random Forest để dự báo bỏ học?
**Đáp:** Nhóm đã **benchmark cả 3 mô hình** (LR, RF, LightGBM) theo cùng quy trình chia 60/20/20, CV trên tập train, hiệu chuẩn và chọn ngưỡng trên validation, test chấm một lần. Kết quả: LR đạt **F1 Dropout, ROC-AUC, PR-AUC cao nhất trên test** và **hiệu chuẩn tốt nhất** (ECE 0,035 so với 0,060 của RF). Với dữ liệu nhỏ, dạng bảng và cần giải thích, mô hình đơn giản là lựa chọn đúng. Nguyên tắc ở đây là **dao cạo Occam**: mô hình phức tạp hơn không mang lại lợi ích thì không dùng.

### Câu 8. Hiệu chuẩn xác suất (calibration) là gì, tại sao DSS cần nó?
**Đáp:** Hiệu chuẩn tức là khi mô hình nói "30% bỏ học" thì trong 100 sinh viên như vậy thực tế phải có khoảng 30 người bỏ học. DSS dùng **con số xác suất để ra quyết định** (so với ngưỡng, nhân vào số tín chỉ kỳ vọng), nên xác suất sai thì quyết định sai. Nhóm dùng **Isotonic Regression** để hiệu chuẩn, kiểm tra bằng **biểu đồ calibration** (điểm sát đường chéo) và **Brier score ≈ 0,12** (càng gần 0 càng tốt).

### Câu 9. SHAP cho thấy "tuổi nhập học" làm tăng rủi ro. Vậy có phải tuổi cao là nguyên nhân bỏ học không?
**Đáp:** **Không.** SHAP chỉ giải thích **mô hình đã dựa vào yếu tố nào để dự đoán**, không chứng minh **nhân quả**. Tuổi cao có thể đi kèm với việc vừa học vừa làm, có gia đình… và chính những yếu tố đó mới tác động. Giao diện ghi rõ *"không phản ánh quan hệ nhân quả"*. Cố vấn chỉ nên dùng SHAP để **mở đầu cuộc trao đổi** và tập trung vào yếu tố **can thiệp được**, như số môn đạt HK1.

### Câu 10. Có nhiều tham số là "giả định" như λ, β, γ. Làm sao người dùng tin kết quả được?
**Đáp:** Nhóm xử lý bằng 3 cách:
1. **Minh bạch:** mỗi tham số có nhãn GIẢ ĐỊNH và lý do chọn giá trị (ví dụ β = 1/8 vì CTĐT có 8 học kỳ, γ = 1 vì 1 tín chỉ trượt bằng 1 tín chỉ phải học lại).
2. **Phân tích độ nhạy:** chạy với λ ∈ {0; 0,1; 0,3}, β ∈ {0…0,5}, γ ∈ {0,5; 1; 2}, độ khó ×{0,8; 1; 1,2} để xem kết luận có thay đổi không.
3. **Cho người dùng tự chỉnh** λ và Fmax trên giao diện.

Riêng λ, dữ liệu thật **không cho thấy** học nhiều làm tăng bỏ học (OR ≈ 1,0005, có thiên lệch chọn lọc), nên nhóm **không bịa ra quan hệ nhân quả** mà để λ là kịch bản. Đây là cách làm trung thực của một prototype DSS.

## 🅲 Nhóm 3: Ràng buộc tối ưu tín chỉ

### Câu 11. Em mô hình hóa bài toán chọn môn bằng ILP như thế nào?
**Đáp:** Biến **xᵢ ∈ {0,1}** cho biết có đăng ký môn i hay không. Hàm mục tiêu **tối đa** Σ xᵢ·[cᵢpᵢ + β·uᵢ − γ·cᵢ(1−pᵢ)], gồm 3 phần: tín chỉ đạt kỳ vọng, thưởng mở khóa môn sau, phạt tín chỉ trượt. Ràng buộc gồm:
1. 12 ≤ Σcᵢxᵢ ≤ trần (12/15/18).
2. Số môn trượt kỳ vọng Σ(1−pᵢ)xᵢ ≤ Fmax + slack (slack bị phạt 1000).
3. Môn song hành: x_A ≤ x_B.
4. Môn bắt buộc đã trượt mà đang chặn chuỗi thì xᵢ = 1.

Bộ giải là **PuLP + HiGHS**. Bài toán có dạng **knapsack nhiều ràng buộc**.

### Câu 12. Nếu bài toán vô nghiệm thì sao, ví dụ không đủ môn để đạt 12 tín chỉ tối thiểu?
**Đáp:** Hệ thống có **chuỗi dự phòng (fallback) nhiều bậc** chứ không báo lỗi: nới sàn 12 → 6 TC (giảm tải) → 0 TC nhưng ít nhất 1 môn → bỏ ép học lại → nới ngưỡng trượt. Kết quả ghi rõ **chế độ dự phòng** đã dùng và trạng thái **"Nỗ lực tối đa ⚠️"** kèm khuyến nghị gặp cố vấn. Ràng buộc rủi ro là **ràng buộc mềm** (có slack) nên luôn có nghiệm và **không tự động hạn chế** sinh viên. Chỉ khi tất cả đều thất bại mới trả về `infeasible_data_error` để kiểm tra lại dữ liệu.

### Câu 13. "Giá trị mở khóa" (unlock value) là gì? Tại sao cần nó?
**Đáp:** uᵢ là **tổng tín chỉ các môn phía sau** trong đồ thị tiên quyết mà môn i mở khóa, mỗi bậc chiết khấu 50% (môn con ×0,5, môn cháu ×0,25…). Nếu chỉ tối đa tín chỉ đạt, mô hình sẽ **né môn khó** dù môn đó là "nút cổ chai". Ví dụ sinh viên S005 trượt IT202 thì bị chặn IT203 và IT304. Thêm β·uᵢ giúp mô hình **nhìn xa** cho các kỳ sau. Ablation trong Notebook 03 chứng minh điều này: khi bật uᵢ, mô hình chọn môn C (khó nhưng mở khóa 10 tín chỉ) thay cho môn D.

### Câu 14. Tại sao không dùng thuật toán tham lam (greedy) cho đơn giản?
**Đáp:** Tham lam chọn từng môn theo thứ tự ưu tiên nên **không đảm bảo tối ưu toàn cục** và khó xử lý đồng thời nhiều ràng buộc (song hành, ngưỡng rủi ro, bắt buộc học lại). Thực tế nhóm đã dùng tham lam làm **chiến lược đối chứng** B1/B2/B3 trong Monte Carlo. Kết quả: ILP **ít trượt hơn có ý nghĩa thống kê** so với cả 3 (ví dụ ít hơn B2 0,82 lượt, KTC 95% [−0,99; −0,64]) và có **tỷ lệ khả thi cao nhất** (51,6% so với 38–41%). Với khoảng 20 môn, HiGHS giải dưới 1 giây nên chi phí tính toán không đáng kể.

## 🅳 Nhóm 4: Tính ứng dụng thực tế & đánh giá

### Câu 15. Kết quả Monte Carlo cho thấy ILP đúng hạn **thấp hơn** B1. Vậy hệ thống có thật sự hữu ích không? Triển khai thực tế cần gì?
**Đáp:** Nhóm em báo cáo **trung thực** kết quả này. ILP **giảm trượt môn** và **khả thi hơn**, còn B1 đúng hạn cao hơn khoảng 2 điểm %. Cả hai cùng nằm trên **biên Pareto**, tức là **đánh đổi**, không có lựa chọn thắng tuyệt đối. Đây chính là giá trị của DSS: **lượng hóa sự đánh đổi** để cố vấn chọn theo ưu tiên của từng sinh viên (sinh viên đang bị cảnh báo thì ưu tiên ít trượt, sinh viên muốn ra trường đúng hạn thì ưu tiên tiến độ). Hệ thống cũng có thể chỉnh β (thưởng mở khóa) để nghiêng về tiến độ.

**Để triển khai thực tế cần:**
1. **Huấn luyện lại** trên dữ liệu NTU (có ẩn danh, đúng quy định bảo vệ dữ liệu cá nhân).
2. Nhập **CTĐT và quy chế chính thức** (QĐ đào tạo NTU) vào YAML.
3. **Hiệu chuẩn λ và hệ số độ khó** từ điểm thật.
4. **Kết nối hệ thống đào tạo** (API) để lấy tiến độ tự động.
5. Cho **cố vấn dùng thử** và thu phản hồi, đo hiệu quả bằng thử nghiệm có đối chứng.
6. Bổ sung học kỳ hè, điều kiện mở lớp, học cải thiện, những thứ hiện chưa được mô hình hóa.

---

## 📝 Phụ lục: Bảng tra nhanh con số (học thuộc)

| Nội dung | Con số |
|---|---|
| Dữ liệu UCI | 4.424 SV · 37 thuộc tính · 0 thiếu · 0 trùng |
| Tỷ lệ nhãn | Dropout 32,12% · Enrolled 17,95% · Graduate 49,93% |
| Số đặc trưng dùng | 24 (18 T0 + 6 T1_known) |
| LR (holdout) | Acc ≈ 0,71 · Precision 0,70 · Recall 0,72 · F1 0,71 · Brier 0,121 |
| Ngưỡng tầng | Thấp ≤ 0,029 · TB ≤ 0,139 · Cao > 0,139 (recall 98% / 90%) |
| Tỷ lệ bỏ học thực theo tầng | Cao 53,3% · TB 7,8% · Thấp 4,9% |
| RF tỷ lệ đạt | MAE 0,124 · RMSE 0,193 |
| M3′ theo năng lực HK1 | Thấp 24,8% · TB 77,9% · Cao 93,2% |
| Tham số ILP | β = 0,125 · γ = 1 · chiết khấu mở khóa 0,5 · phạt slack 1000 · λ = 0,1 |
| Quy chế mô phỏng | 12–18 TC/kỳ · 128 TC tốt nghiệp · 8 kỳ chuẩn · tối đa 16 kỳ · học tối đa 3 lần |
| Trần theo tầng | TC: 18/15/12 · Fmax: 2,0/1,5/1,0 (Thấp/TB/Cao) |
| Monte Carlo | 1.000 lượt × 7 hồ sơ × 4 chiến lược · seed 20261105 · bootstrap KTC 95% |
| Kết quả MC | ILP ít trượt nhất (12,01) & khả thi nhất (51,6%) · B1 đúng hạn cao nhất (6,1%) · Pareto: ILP, B1 |

## 💡 Mẹo trả lời vấn đáp
1. **Luôn nói hạn chế trước khi bị hỏi**: dữ liệu Bồ Đào Nha, CTĐT mô phỏng, tham số giả định. Giảng viên đánh giá cao sự trung thực.
2. Khi bị hỏi "vì sao chọn X", trả lời theo khung: **bản chất bài toán → yêu cầu của DSS (chính xác / giải thích / tin cậy) → đã so sánh với phương án khác**.
3. Phân biệt rõ 3 cặp khái niệm dễ bị bắt bẻ: **tương quan ≠ nhân quả** · **tối ưu theo mô hình ≠ tốt nhất ngoài đời** · **hỗ trợ quyết định ≠ tự động quyết định**.
