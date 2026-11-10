# [MỐC] Phần 5-fix — giao diện và chạy thật

## F4 — AppTest, ca đặc biệt và thời gian What-if

Đầu vào Phần 4-fix được xác nhận trước triển khai: `mc_results.csv`,
`mc_pairwise.csv`, `mc_pareto.csv`, `mc_grad_hist.csv` và
`mc_interpretation.md` đều tồn tại. AppTest thực thi ứng dụng thật từ
`app/main.py`; toàn bộ 9 hồ sơ × 7 trang (63 tổ hợp) không phát sinh exception.

Ca đặc biệt được kiểm thử:

- ML ngoài T1 hiển thị thông báo ML tắt.
- Core không trả phương án: trang đăng ký hiển thị cảnh báo, không exception.
- V2-008 ở kỳ cuối, `graduation_ready`: trang phương án render bình thường.
- Chỉnh điểm hoàn thành xuống 4,9: từ chối dữ liệu không nhất quán, không rerun
  DSS; không exception.
- `best_effort`, `regulatory_conflict`, `risk_cap_exceeded`: đều hiện khuyến
  nghị gặp cố vấn học tập.
- Đổi hồ sơ V2-001 → V2-005: nội dung hồ sơ trước không còn trong trang mới.
- Thiếu `mc_grad_hist.csv`: báo không dựng/suy diễn phân phối, không exception.

Fresh `run_dss` What-if cho V2-001, ngân sách 18, Fmax 2,0, λ=0,1,
`risk_cap_mode=soft`:

```text
run_dss What-if: 1.2718s, 3 plans, status=optimal
```

Kết quả dưới ngưỡng 10 giây; giữ cache hiện có `st.cache_data`, khóa gồm
student ID và options chuẩn hóa. Lỗi PuLP 4.2 `LpVariable(..., lowBound=0)`
được sửa sang `problem.add_variable(..., lowBound=0)` và có regression test
cho soft risk-cap.

## F5 — đối chiếu yêu cầu giao diện

| Yêu cầu | Trang | Hàm hiển thị / dữ liệu |
|---|---|---|
| Nhập/chọn hồ sơ kịch bản | Sidebar; Hồ sơ & tiến độ | `main`, `_render_profile`, `build_profile_data` |
| Nguy cơ, cảnh báo, SHAP | Nguy cơ & cảnh báo | `_render_risk`, `build_risk_data` |
| Môn đủ điều kiện, nợ, bị chặn | Học phần | `_render_courses`, `build_courses_data` |
| Các phương án ILP, tín chỉ, P đạt, cảnh báo | Phương án đăng ký | `_render_plans`, `_render_plan_cards`, `build_plans_data` |
| Tham số và đối chiếu what-if | What-if | `_render_what_if`, `build_what_if_data`, `_run` |
| So sánh phương án, histogram, CI, Pareto | Mô phỏng | `_render_simulation`, `build_simulation_data` |
| Phân biệt OFFICIAL/REAL/SCENARIO/GIẢ ĐỊNH | Tất cả trang; Dữ liệu & giả định | `_source_badge`, `_render_provenance`, `build_provenance_data` |

Trang Mô phỏng mặc định bật `ILP-matched`; `ILP-fixed` là lựa chọn độ bền,
được chú thích planner không biết λ thế giới. Danh sách policy, comparison,
Pareto labels và λ đọc từ artifact. Pareto có màu: xanh (vượt trội), đỏ (bị
vượt trội), cam (đánh đổi), xám (chưa phân biệt). Histogram đánh dấu đúng hạn
8 kỳ và hiển thị tốt nghiệp, buộc thôi học, phần chưa hoàn tất đến kỳ 16; nếu
file histogram vắng mặt, UI không dựng lại từ aggregate. Nội dung giới hạn
đọc trực tiếp từ `mc_interpretation.md`.

## F6 — bằng chứng chạy

### Full pytest, nguyên văn

Lệnh:

```text
python -m pytest -q --disable-warnings
```

Kết quả:

```text
........................................................................ [ 60%]
...............................................                          [100%]
119 passed, 252 warnings in 48.27s
```

### AppTest cases

Tổ hợp `test_apptest_all_pages_for_every_scenario` lặp đủ chín scenario trong
mỗi trang:

- `test_apptest_all_pages_for_every_scenario[Hồ sơ & tiến độ]`
- `test_apptest_all_pages_for_every_scenario[Nguy cơ & cảnh báo]`
- `test_apptest_all_pages_for_every_scenario[Học phần]`
- `test_apptest_all_pages_for_every_scenario[Phương án đăng ký]`
- `test_apptest_all_pages_for_every_scenario[What-if]`
- `test_apptest_all_pages_for_every_scenario[Mô phỏng]`
- `test_apptest_all_pages_for_every_scenario[Dữ liệu & giả định]`

Các AppTest special:

- `test_apptest_ml_disabled_no_plan_final_term_and_invalid_edit`
- `test_apptest_reports_empty_plan_state`
- `test_apptest_risky_statuses_show_advisor_callout[best_effort]`
- `test_apptest_risky_statuses_show_advisor_callout[regulatory_conflict]`
- `test_apptest_risky_statuses_show_advisor_callout[risk_cap_exceeded]`
- `test_apptest_does_not_leak_previous_profile_content`
- `test_apptest_missing_histogram_displays_no_reconstruction_message`

### Cây thư mục `app/`

```text
app/
├── __init__.py
├── main.py
└── view_data.py
```

### Lệnh chạy / test

```powershell
streamlit run app/main.py
python -m pytest tests/test_app_smoke.py -q
python -m pytest -q --disable-warnings
```

Danh sách chụp màn hình đã cập nhật tại `reports/screens_to_capture.md`, gồm
ILP-matched/ILP-fixed, histogram và các ca không kiểm chứng được.

## File thay đổi / tạo

- Sửa: `app/main.py`, `app/view_data.py`, `core/optimizer.py`,
  `tests/test_app_smoke.py`, `tests/test_optimizer_v2.py`, `README.md`,
  `reports/screens_to_capture.md`, `reports/generated/metrics.json`.
- Tạo: `reports/generated/part5_fix_report.md`.

## Quyết định và mục cần AQL xác nhận

- Chưa có ảnh chụp thật trong artifact; `screens_to_capture.md` là checklist
  cập nhật, không ghi nhận ảnh đã chụp.
- Mục chụp liên quan tới mô phỏng vẫn là SCENARIO/GIẢ ĐỊNH, không phải bằng
  chứng hiệu quả với sinh viên NTU.
