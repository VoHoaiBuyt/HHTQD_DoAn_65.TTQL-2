# Câu hỏi xin cô xác nhận

1. Cảnh báo nên trình bày ba lớp (Dropout/Enrolled/Graduate) hay nhị phân? Validation XGBoost có Dropout recall 0,7113 ở ba lớp và 0,6655 ở nhị phân (chênh 0,0458); chưa có KTC ghép cặp giữa hai bài toán để kết luận chênh lệch nằm trong sai số. Test hiện chỉ đánh giá ba lớp. **Mặc định:** giữ ba lớp để không gộp Enrolled bị kiểm duyệt vào nhãn khác.
2. Báo cáo Monte Carlo nên trình bày cả λ=0 và λ>0? **Mặc định:** trình bày λ=0 và λ=0,1 làm lát cắt chính; λ=0,3 là độ nhạy, tất cả gắn nhãn GIẢ ĐỊNH.
3. Có dùng lưới kịch bản {15, 18, 21} cho sinh viên thường và 12 tín chỉ chỉ cho hồ sơ yếu/kém không? **Mặc định:** có, nhưng đây là lưới phân tích, không thay giới hạn QĐ 753; cấu hình quy chế thường là 15–27, yếu/kém 12–18.
4. Trong Monte Carlo có giới hạn buộc thôi học ở W1/W2 do không có chuỗi điểm để đánh giá W3/W4 không? **Mặc định:** chỉ W1/W2; ghi rõ W3/W4 chưa mô phỏng.
5. Cô duyệt tiêu chí Pareto hiện tại và KTC bootstrap ghép cặp 95% không? **Mặc định:** chỉ kết luận trội khi tiêu chí chính và KTC cùng ủng hộ; nếu không thì ghi chưa phân biệt.
6. Có cần bổ sung OULAD hay mô hình hóa học kỳ hè? **Mặc định:** chưa thêm nguồn hoặc giả định ngoài dữ liệu được nhóm cung cấp; OULAD chưa sử dụng, hè chưa mô hình hóa.
