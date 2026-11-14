# Hệ hỗ trợ cảnh báo rủi ro học tập và tối ưu lộ trình tín chỉ (NTU)

Hệ hỗ trợ quyết định (DSS) dành cho ngành Công nghệ Thông tin, Trường Đại học Nha Trang. Hệ thống tích hợp dự báo Machine Learning cảnh báo sớm tại mốc T1 kèm giải thích cục bộ SHAP (XAI), cấu trúc đồ thị tiên quyết (DAG), mô hình tối ưu hóa tuyến tính nguyên (ILP) phân tích What-if tương tác, phân tích quỹ đạo dài hạn Monte Carlo và giao diện Web chuẩn học thuật (FastAPI Backend + React/HTML/CSS Portal) hỗ trợ Dark/Light Mode.

## Nguồn và nhãn dữ liệu

- `REAL (UCI-697)`: đặc trưng mô hình được lấy từ bộ dữ liệu giáo dục đại học UCI; chưa được kiểm định trên sinh viên NTU.
- `OFFICIAL (NTU)`: CTĐT và QĐ 753/QĐ-ĐHNT theo tài liệu quy chế chính thức. Trường không có trong nguồn được ghi `UNKNOWN`, `source=NOT_FOUND`.
- `SCENARIO`: 9 hồ sơ kịch bản minh họa tổng hợp (V2-001 đến V2-009), không phải dữ liệu cá nhân thật.
- `GIẢ ĐỊNH`: tham số mô phỏng (λ, β, γ) và quy tắc mùa vụ mở môn suy từ CTĐT.
- Mã `HP0xx` là mã định danh nội bộ do nhóm gán; xem `docs/course_code_provenance.md`.

## Cài đặt và khởi chạy hệ thống (Windows PowerShell)

```powershell
# 1. Kích hoạt môi trường và cài đặt thư viện
python -m pip install -r requirements.txt

# 2. Chạy bộ kiểm thử tự động (116 tests)
python -m pytest tests/ scripts/test_prose_claims.py -q

# 3. Khởi chạy ứng dụng Web (FastAPI + React Dashboard)
.\run_web_app.ps1
```

Sau khi chạy `run_web_app.ps1`, truy cập trình duyệt tại:
- **Giao diện Web học thuật:** `http://localhost:8000/`
- **Tài liệu API Swagger:** `http://localhost:8000/docs`

Giao diện hỗ trợ chuyển đổi giao diện Sáng / Tối (**Light Mode / Dark Mode**), thẻ sinh viên học thuật trực quan và 7 bảng điều khiển chuyên sâu. Mức cảnh báo rủi ro hoàn toàn độc lập với trạng thái solver (`optimal`/`best_effort`). Mọi phương án rủi ro CAO đều khuyến nghị trao đổi trực tiếp với Cố vấn học tập.

## Báo cáo và kiểm tra

Báo cáo Word thống nhất: `reports/BaoCao_Nhom1_HTTQD_65.TTQL-Final.docx`.
Ước lượng độ dài báo cáo: `reports/generated/report_stats.json`.

```powershell
python -m scripts.build_final_report --final
python -m scripts.check_report_consistency
python -m scripts.check_dist_links
```

## Hạn chế

Mô hình học máy được xây trên UCI-697 (Bồ Đào Nha), không trên sinh viên NTU. Một số mã học phần, quan hệ tiên quyết/song hành và diễn giải quy chế còn cần đối chiếu. Monte Carlo là phân tích kịch bản theo giả định, không phải bằng chứng hiệu quả với sinh viên NTU. Các ảnh giao diện thật và ngữ cảnh chụp được ghi trong `demo_media/README.md`.
