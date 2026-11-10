# Danh sách màn hình cần chụp

Chạy ứng dụng bằng `streamlit run app/main.py`. Tất cả hồ sơ dưới đây là
`SCENARIO`; không chụp thông tin cá nhân thật. Trên từng hồ sơ chụp đủ 7 trang:
**Hồ sơ & tiến độ**, **Nguy cơ & cảnh báo**, **Học phần**, **Phương án đăng ký**,
**What-if**, **Mô phỏng**, **Dữ liệu & giả định**.

| Kịch bản | Trang / tùy chọn cần thể hiện |
|---|---|
| V2-001 | Toàn bộ 7 trang; ML tại T1, chế độ tín chỉ thường, what-if λ=0,1 và Fmax=2,0; ở Mô phỏng để mặc định ILP-matched, bật ILP-fixed để xem độ bền, chọn λ=0,1 và chụp phân phối kỳ tốt nghiệp cùng đường đúng hạn 8 kỳ. |
| V2-002 | Toàn bộ 7 trang; T1 với hồ sơ học tập trung bình; so sánh xác suất đạt giữa các phương án đang có; chụp Mô phỏng tại λ=0,1 gồm CI ghép cặp và Pareto. |
| V2-003 | Toàn bộ 7 trang; T1, cảnh báo học vụ và chế độ tín chỉ yếu/kém; what-if trong khoảng giới hạn đang hiển thị; chụp Mô phỏng tại λ=0,1. |
| V2-004 | Toàn bộ 7 trang; ngưỡng TBHK 5,00 và chế độ tín chỉ do core trả về. |
| V2-005 | Toàn bộ 7 trang; ML tắt do `extension_assumption`, nợ tín chỉ/cờ W1 và khuyến nghị gặp cố vấn nếu kế hoạch bị giới hạn; chụp trang Mô phỏng tại λ=0,1. |
| V2-006 | Toàn bộ 7 trang; ML tắt do `extension_assumption`, học phần bị chặn bởi tiên quyết và môn học lại. |
| V2-007 | Toàn bộ 7 trang; ML tắt, gần tốt nghiệp và học lại; kiểm tra kỳ tốt nghiệp ước tính có nhãn giả định. |
| V2-008 | Toàn bộ 7 trang; ML tắt, trạng thái đủ điều kiện tốt nghiệp và trường hợp không có phương án đăng ký. |
| V2-009 | Toàn bộ 7 trang; ML tắt, học lại/mở lại ô tự chọn và nguyên nhân học phần bị chặn. |

Ở trang **Hồ sơ & tiến độ**, chụp thêm một trạng thái chỉnh sửa hợp lệ (đổi trạng
thái kèm điểm phù hợp) và một trạng thái không hợp lệ để thể hiện thông báo kiểm
tra nhất quán. Trang **Mô phỏng** tự đọc danh sách chính sách, cặp so sánh, nhãn
Pareto và các λ hiện có từ CSV; không giả định số lượng cố định. Mặc định bật
ILP-matched; bật ILP-fixed để xem độ bền (planner không biết λ thế giới). Chụp
`mc_results.csv`, `mc_pairwise.csv`, `mc_pareto.csv`, `mc_grad_hist.csv` theo
hồ sơ/λ: số lượt MC, phân phối tốt nghiệp theo kỳ, vạch đúng hạn 8 kỳ, buộc
thôi học/chưa hoàn tất kỳ 16, KTC ghép cặp và nhãn Pareto có màu. Khung diễn giải
đọc trực tiếp từ `mc_interpretation.md`. Nếu histogram hoặc các artifact MC
không còn, ghi rõ “chưa kiểm chứng”; không dựng lại từ số liệu tổng hợp.

Ca kiểm tra chạy thật bổ sung bằng Streamlit AppTest: đủ 9 hồ sơ × 7 trang;
ML tắt, không có phương án, hồ sơ ở kỳ cuối, chỉnh sửa điểm/trạng thái không
nhất quán, cảnh báo cố vấn và đổi hồ sơ không rò nội dung hồ sơ trước.
