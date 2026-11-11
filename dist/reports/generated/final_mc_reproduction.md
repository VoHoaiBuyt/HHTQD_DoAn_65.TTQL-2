# Kiểm chứng tái tạo Monte Carlo

Kiểm tái tạo 3 nhóm (V2-001/ILP-matched, V2-001/B1, V2-005/B1; λ=0,1); trong đó 1 nhóm dùng ILP; không có code_hash. Đây không phải kiểm chứng toàn bộ tổ hợp hồ sơ/chính sách.

Tái tạo bổ sung V2-003/ILP-matched, λ=0,3 chưa hoàn tất trong giới hạn 10 phút; theo chỉ dẫn đã thử fallback λ=0,1 nhưng lần đó cũng chưa hoàn tất trong giới hạn. Không có kết quả đối chiếu cho cả hai lần chạy.

Với V2-005/B1, mô phỏng đã ghi kết quả nhưng hậu xử lý phát sinh `KeyError`; thông báo lỗi nguyên văn không được lưu. Đối chiếu được thực hiện trên `V2-005_B1_results.csv` và `V2-005_B1_grad_hist.csv` đã có trước khi hậu xử lý lỗi, so với các dòng tương ứng trong `mc_results.csv` và `mc_grad_hist.csv`: 109/109 cột kết quả (101 cột số trong V2-005) và 1/1 dòng histogram khớp theo tiêu chí đã duyệt; `source_label` là khác biệt metadata.
