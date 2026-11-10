# Diễn giải Monte Carlo — Phần 4-fix

**Phạm vi:** kịch bản SCENARIO, seed 20261108, N=1.000 cho mỗi hồ sơ/chính sách; kết quả không phải ước lượng hiệu quả thực tế tại NTU. Các số tóm tắt dưới đây là trung bình ngang trọng số 9 hồ sơ, chỉ để mô tả; suy luận và Pareto phải xem theo từng hồ sơ trong `mc_results.csv`, `mc_pairwise.csv`, `mc_pareto.csv`.

| λ thế giới | Chính sách | P(tốt nghiệp ≤8 kỳ) | P(≤16 kỳ) | Kỳ tốt nghiệp TB kiểm duyệt | Số lượt trượt TB |
|---:|---|---:|---:|---:|---:|
| 0,0 | ILP-matched | 0,410 | 0,888 | 9,760 | 4,048 |
| 0,0 | ILP-fixed (planner λ=0,1) | 0,282 | 0,887 | 10,171 | 4,062 |
| 0,0 | B1 | 0,542 | 0,888 | 9,137 | 4,465 |
| 0,0 | B2 | 0,534 | 0,887 | 9,218 | 4,463 |
| 0,1 | ILP-matched / ILP-fixed | 0,282 | 0,887 | 10,171 | 4,062 |
| 0,1 | B1 | 0,242 | 0,837 | 10,495 | 11,580 |
| 0,1 | B2 | 0,206 | 0,799 | 10,807 | 11,710 |
| 0,3 | ILP-matched / ILP-fixed | 0,282 | 0,887 | 10,171 | 4,062 |
| 0,3 | B1 | 0,114 | 0,508 | 13,139 | 17,700 |
| 0,3 | B2 | 0,112 | 0,415 | 13,567 | 16,698 |
| mọi λ | B3 (15 tín chỉ/kỳ) | 0,111 | 0,881 | 11,072 | 4,345 |

Ở λ=0, ILP-matched không vượt B1/B2 về xác suất tốt nghiệp đúng hạn trong trung bình mô tả; B1/B2 có kỳ tốt nghiệp trung bình thấp hơn và nhiều lượt trượt hơn. Khi λ>0, baseline B1/B2 chịu trực tiếp hệ số phạt tải trong khi B3 giữ tải 15 tín chỉ; do đó mọi chênh lệch phụ thuộc giả định λ và cách đặt tải, không phải hiệu quả đã xác nhận. ILP-fixed cố định planner λ=0,1 để đo độ nhạy với sai lệch giữa planner và thế giới; ILP-matched dùng cùng λ với thế giới.

Phân tích quan sát **REAL (UCI-697), C.2** không tìm bằng chứng tải cao làm giảm tỷ lệ đạt: trong tầng Trung bình pass-rate là 0,756 / 0,730 / 0,842 (1–5 / 6–7 / 8+ units), tầng Cao là 0,915 / 0,915 / 0,966; tầng Thấp không đơn điệu. Đây không phải thí nghiệm ngẫu nhiên và không cho phép kết luận nhân quả. Vì vậy không kết luận hệ thống tốt hơn cách đăng ký thông thường; ILP chỉ có thể hữu ích khi người dùng/cố vấn muốn so sánh phương án dưới giả định rủi ro, giới hạn và quy tắc đã xác nhận.

**Hạn chế:** M3' gồm cả sinh viên UCI về sau Dropout và là proxy ngoài NTU; không cộng hazard dropout lần hai. Kết quả từng môn độc lập; kỳ hè không mô phỏng; W3/W4 chưa mô phỏng; điểm đạt/trượt 7,0/4,0 là GIẢ ĐỊNH dùng tính TBHK và tốt nghiệp. λ, hệ số học lại và mô hình xác suất đều là giả định/exploratory. Các trung bình trên không thay thế KTC ghép cặp và kết luận Pareto theo từng hồ sơ.

**Kiểm tái tạo 3 nhóm (V2-001/ILP-matched, V2-001/B1, V2-005/B1; λ=0,1); trong đó 1 nhóm dùng ILP; không có code_hash.** Đây không phải kiểm chứng toàn bộ tổ hợp hồ sơ/chính sách.

Với V2-005/B1, mô phỏng đã ghi kết quả nhưng hậu xử lý phát sinh `KeyError`; thông báo lỗi nguyên văn không được lưu. Đối chiếu được thực hiện trên `V2-005_B1_results.csv` và `V2-005_B1_grad_hist.csv` đã có trước khi hậu xử lý lỗi, so với các dòng tương ứng trong `mc_results.csv` và `mc_grad_hist.csv`: 109/109 cột kết quả (101 cột số trong V2-005) và 1/1 dòng histogram khớp theo tiêu chí đã duyệt; `source_label` là khác biệt metadata.

Tái tạo bổ sung V2-003/ILP-matched, λ=0,3 chưa hoàn tất trong giới hạn 10 phút; theo chỉ dẫn đã thử fallback λ=0,1 nhưng lần đó cũng chưa hoàn tất trong giới hạn. Không có kết quả đối chiếu cho cả hai lần chạy.
