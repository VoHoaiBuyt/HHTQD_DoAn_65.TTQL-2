# Hệ hỗ trợ cảnh báo rủi ro học tập và tối ưu lộ trình tín chỉ

Prototype dành cho ngành Công nghệ thông tin, Trường Đại học Nha Trang. Hệ thống kết nối dự báo ML tại T1, quy tắc đào tạo, tối ưu ILP, phân tích Monte Carlo và giao diện Streamlit. Đây là công cụ hỗ trợ thảo luận, không thay thế tư vấn học vụ.

## Nguồn và nhãn dữ liệu

- `REAL (UCI-697)`: đặc trưng mô hình được lấy từ bộ dữ liệu UCI; chưa được kiểm định trên sinh viên NTU.
- `OFFICIAL (NTU)`: CTĐT và QĐ 753 theo tài liệu do nhóm cung cấp. Trường không có trong nguồn được ghi `UNKNOWN`, `source=NOT_FOUND`.
- `SCENARIO`: hồ sơ minh họa, không phải dữ liệu cá nhân thật.
- `GIẢ ĐỊNH`: tham số/diễn giải mô phỏng; trạng thái chưa xác nhận được nêu trong báo cáo.
- Mã `HP0xx` là mã định danh nội bộ do nhóm gán; xem `docs/course_code_provenance.md`.

## Cài đặt và chạy trên Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
python -m streamlit run app/main.py
```

Mở địa chỉ cục bộ do Streamlit in ra. Ứng dụng chỉ dùng hồ sơ `SCENARIO`. ML chỉ hiển thị với hồ sơ có phạm vi T1 hợp lệ. Mức cảnh báo rủi ro độc lập với trạng thái solver; trạng thái `optimal` không xác nhận phù hợp học vụ. Phương án mức CAO khuyến nghị trao đổi với cố vấn học tập.

## Báo cáo và kiểm tra

Báo cáo Word thống nhất: `reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx`.
Thư gửi giảng viên được lưu riêng ngoài gói phân phối; không nằm trong `dist/`.
Ước lượng độ dài báo cáo: `reports/generated/report_stats.json`.

```powershell
python -m scripts.build_final_report --final
python -m scripts.check_report_consistency
python -m scripts.check_dist_links
```

`--final` yêu cầu đầy đủ ảnh chụp thật trong `demo_media/`, dữ liệu nguồn và transcript pytest đã loại đường dẫn máy cá nhân. Các số báo cáo lấy từ artifact trong `reports/generated/`; không chạy lại mô phỏng hay huấn luyện để dựng báo cáo. Cấu trúc và tệp nộp được liệt kê trong `deliverables.md`.

Notebook EDA `notebooks/01_eda_uci697.ipynb` được kiểm tra chạy từ đầu trong môi trường sạch trước khi đóng gói; gói phân phối giữ notebook ở trạng thái không có output.

## Hạn chế

Mô hình học máy được xây trên UCI-697 (Bồ Đào Nha), không trên sinh viên NTU. Một số mã học phần, quan hệ tiên quyết/song hành và diễn giải quy chế còn cần đối chiếu. Monte Carlo là phân tích kịch bản theo giả định, không phải bằng chứng hiệu quả với sinh viên NTU. Các ảnh giao diện thật và ngữ cảnh chụp được ghi trong `demo_media/README.md`.
