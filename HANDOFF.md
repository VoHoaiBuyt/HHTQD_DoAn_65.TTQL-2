# Bàn giao hiện trạng

## Báo cáo và gói nộp

- Báo cáo thống nhất: `reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx`.
- Hướng dẫn cài đặt/chạy: `README.md`.
- Danh mục tệp thuộc gói: `deliverables.md`.
- Ảnh chụp giao diện thật: `demo_media/README.md`.
- Nguồn mã HP và giới hạn xác minh: `docs/course_code_provenance.md`.

## Phạm vi kết quả

- Hồ sơ là `SCENARIO`; đặc trưng ML lấy từ `REAL (UCI-697)`.
- CTĐT và quy chế được gắn `OFFICIAL (NTU)` theo tài liệu nhóm cung cấp.
- Tham số mô phỏng và ngưỡng cảnh báo mang nhãn `GIẢ ĐỊNH`; chưa xác nhận được ghi `UNCONFIRMED`.
- Monte Carlo trong báo cáo chỉ đọc kết quả đã lưu. Không tái chạy MC, huấn luyện lại hoặc truy cập tập test khi hoàn thiện báo cáo.
- Phương án mức CAO kèm khuyến nghị trao đổi với cố vấn. `optimal` chỉ mô tả nghiệm theo hàm mục tiêu/ràng buộc được mô hình hóa.
- Thư gửi giảng viên được lưu riêng ngoài `dist/`; độ dài ước lượng báo cáo ở `reports/generated/report_stats.json`.

## Kiểm tra trước khi bàn giao

Chạy từ thư mục gốc bằng PowerShell:

```powershell
python -m pytest
python -m scripts.check_report_consistency
python -m scripts.check_dist_links
python -m streamlit run app/main.py
```

Sau khi dựng `dist/`, kiểm tra cài đặt, pytest, health, các liên kết nội bộ và report consistency từ bản sao sạch. Kết quả mới nhất cần ghi trong `reports/generated/final_dist_validation.md` và `reports/generated/pytest_summary.txt`. Notebook EDA được chạy từ đầu trong môi trường sạch; bản trong gói không chứa output. Không tạo tag bàn giao trước khi được duyệt.
