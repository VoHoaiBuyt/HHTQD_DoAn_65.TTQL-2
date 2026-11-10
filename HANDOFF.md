# [MỐC] Phần 1/6 — nạp và kiểm định CTĐT OFFICIAL

## a) Đã làm / chưa làm

**Đã làm**

- Nạp `data/official/courses.csv` và `data/official/prerequisites.csv` từ nội
  dung nhóm cung cấp của `210_CNTT.pdf`, mục 7.1; giữ nguyên course IDs và gắn
  `source_label=OFFICIAL (NTU)`.
- Tách logic curriculum, validation, rules, consistency, risk planning, ILP và
  metrics vào `core/`; các module optimizer cũ trong `src/optimize/` còn wrapper
  tương thích cho script/notebook.
- Thêm enrichment/config và báo cáo giả định. Enrichment chỉ áp dụng khi nạp,
  không sửa CSV OFFICIAL. Quy tắc chuyên ngành, elective slot, HP017, HP048,
  lịch mở và ngữ nghĩa tiên quyết vẫn được gắn nhãn GIẢ ĐỊNH.
- Chuyển generators/validator và test legacy của catalogue SIMULATED vào
  `archive/`; test cũ không còn bị pytest thu thập.
- Hoàn tất `evaluate_student`, corequisite fixed-point pruning và ràng buộc ILP
  tương ứng; `best_effort` luôn có cảnh báo rủi ro và khuyến nghị gặp cố vấn,
  không gọi phương án là “an toàn”.
- Audit scenario v1 mà không sửa đầu vào; dữ liệu này chỉ dùng để kiểm tra, không
  dùng làm kết quả cuối.

**Chưa làm**

- Chưa có scenario v2; chưa triển khai ML, Monte Carlo nhiều kỳ, giao diện
  Streamlit hoặc đánh giá hiệu quả NTU.
- Chưa xác minh mã HP0xx, tính đầy đủ/ý nghĩa quy chế của danh sách tiên quyết,
  lịch mở môn và quy chế học vụ từ nguồn chính thức.
- Chưa xác định chuyên ngành của các hồ sơ v1; không suy đoán để tính thiếu môn
  chuyên ngành/tự chọn.

## b) File tạo/sửa chính

- Dữ liệu/config: `data/official/*.csv`, `data/scenarios_v1/*.csv`,
  `data/scenarios/.gitkeep`, `config/courses_enrichment.yaml`,
  `config/program_official.yaml`.
- Core: `core/curriculum.py`, `core/curriculum_validation.py`,
  `core/rules.py`, `core/ilp.py`, `core/plan_risk.py`,
  `core/data/consistency.py`, `core/metrics.py`.
- Tests: `tests/test_core_rules.py`, `tests/test_curriculum_validation.py`,
  `tests/test_data_consistency.py`, `tests/test_metrics.py`.
- Báo cáo/config trợ giúp: `requirements.txt`, `README.md`,
  `reports/curriculum_validation.txt` và các tệp trong `reports/generated/`.
- Tài liệu Stage 1 trước đây được giữ ở trạng thái lịch sử; không dùng số liệu
  exploratory/persona cũ làm kết quả hiện tại.

## c) Kết quả chạy

**Validator — `python -m core.curriculum_validation` (trích trường kết quả từ
stdout JSON):**

```json
{
  "source_label": "OFFICIAL (NTU)",
  "source_document": "210_CNTT.pdf",
  "source_section": "7.1",
  "n_checks": 13,
  "n_pass": 10,
  "n_warn": 3,
  "n_fail": 0
}
```

- 101 course rows: 54 bắt buộc, 47 tự chọn; 19 môn ngoài tổng 130 tín chỉ.
- Cả SE/IS/NW đều có bắt buộc `[17, 15, 17, 13, 11, 15, 12, 10]`, tự chọn
  `[0, 2, 2, 5, 5, 3, 3, 0]`, tổng 130.
- Đồ thị tiên quyết: 15 cạnh, không chu trình, chuỗi dài nhất 3 môn.
- Ba WARN: trùng tên môn cần rà soát; mã HP chưa xác nhận nguồn; độ đầy đủ
  prerequisite `UNCONFIRMED`. Chi tiết đầy đủ tại
  `reports/generated/curriculum_validation.json`.

**Scenario v1 — `python -m core.data.consistency` (stdout JSON):**

- `status=CHECKED`, 8 hồ sơ, 248 dòng tiến độ; không có mã môn lạ, hồ sơ mồ côi
  hoặc ID hồ sơ trùng.
- 27 defect: 8 lệch mốc T1; 13 lệch feature HK1 so với số dòng tiến độ; 4 hồ sơ
  có điểm hoàn thành hằng số; 2 hồ sơ ở HK8 nhưng còn tín chỉ.
- GPA `UNCONFIRMED`; specialization `UNKNOWN` ở cả hồ sơ do không có trường đó.
  Không ước lượng công thức GPA hay gán chuyên ngành.
- Chi tiết theo từng hồ sơ tại `reports/generated/scenario_v1_defects.json`.

**Pytest — `python -m pytest -q` (nguyên văn):**

```text
...............                                                          [100%]
============================== warnings summary ===============================
C:\Users\DELL\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anyio\pytest_plugin.py:14
  C:\Users\DELL\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
15 passed, 1 warning in 0.79s
```

`git diff --check` passed; compatibility imports from `src.optimize.*` passed.

## d) Quyết định thiết kế

- Course ID là khóa; tên môn không dùng làm khóa vì dữ liệu có tên trùng.
- Không ghi cột suy diễn vào CSV OFFICIAL; giữ chúng trong loader/config, nhãn
  `GIẢ ĐỊNH (suy từ CTĐT)`.
- Không xác nhận ngầm “không có dòng prerequisite” thành “không có tiên quyết”.
- `best_effort` không có nghĩa là an toàn; luôn kèm khuyến nghị trao đổi với cố
  vấn học tập.
- Các CSV scenario v1 được giữ nguyên để audit; không tái sử dụng cho kết quả ML
  hoặc kết quả cuối.

## e) Cần nhóm xác nhận

1. Mã HP0xx/HP0xx-x nào có trong PDF, mã nào do nhóm gán?
2. `HP017-A` và `BUA319` có thật sự cùng một ô tự chọn không? Cách nhóm các ô
   khác theo mã có đúng bảng PDF không?
3. Danh sách prerequisite đã đầy đủ chưa; “tiên quyết” có nghĩa phải đạt và
   “song hành” có thể học cùng kỳ theo cách đang mô hình hóa không?
4. `offered_semesters=odd/even/both` có phản ánh lịch mở học kỳ thực tế không;
   học kỳ phụ có cần mô hình hóa không?
5. Quy chế chính thức về trần tín chỉ, học lại, ngưỡng cảnh báo và tính GPA là
   gì?
6. Chuyên ngành nào được gán cho từng sinh viên scenario v1 (nếu nhóm xác nhận
   cần đánh giá thiếu môn theo nhánh)?

## f) Bước tiếp theo

- Chờ nhóm xác nhận các câu hỏi ở trên và cung cấp quy chế chính thức.
- Phần 2: hoàn thiện rule/solver theo quy chế đã xác nhận; giữ mọi UNKNOWN rõ
  ràng cho tới khi có nguồn.
- Phần 3: tạo scenario v2 trên học phần OFFICIAL và vector REAL được phép; tách
  train/test trước khi đánh giá ML.

---

# [MỐC] Phần 6/6 — kiểm thử, báo cáo Word và đóng gói

## Lệnh chạy lại từ môi trường mới

Từ thư mục gốc repo, dùng Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m core.curriculum_validation
python -m core.data.consistency
python -m core.regulation
python -m scripts.generate_scenario_v2
python -m scripts.run_monte_carlo --runs 1000 --lambda 0.1 --workers 4
python -m scripts.build_report
python -m scripts.check_report_consistency
python -m pytest -v
streamlit run app/main.py
```

ML holdout đã được đánh giá một lần (`evaluation_count=1`); không chạy lại
`python -m core.train_models --evaluate-test` với cùng split. Nếu huấn luyện lại,
chỉ chạy `python -m core.train_models --skip-test`; mọi lần truy cập test mới cần
quyết định và log riêng.

## Seed và trạng thái

- Split REAL (UCI-697): `data/processed/split_manifest.json`, seed `20261105`.
- Scenario v2: `reports/generated/scenario_v2_validation.json`, seed `20261105`.
- Monte Carlo: `config/monte_carlo_scenario.yaml` và
  `reports/generated/mc_runtime.json`, seed `20261108`.
- Bootstrap KTC ML validation: `reports/generated/ml_validation_bootstrap_ci.json`,
  seed `20261110`.
- Test summary nguyên văn: `reports/generated/pytest_summary.txt`.
- Word report: `reports/stage2_report.docx`; kiểm tra bảng:
  `python -m scripts.check_report_consistency`.

## Danh sách file giao chính

- Mã nguồn: `core/`, `app/`, `scripts/`, `tests/`.
- Notebook: `notebooks/01_eda_uci697.ipynb`,
  `archive/02_risk_to_plan_exploration.ipynb`,
  `archive/03_ilp_formulation_check.ipynb` (legacy Stage 1).
- Dữ liệu/config: `data/official/`, `data/scenarios/`, `data/processed/`,
  `config/`; không dùng catalogue SIMULATED trong kết quả cuối.
- ML: `models/early_warning.joblib`,
  `reports/generated/model_comparison.csv`,
  `reports/generated/test_evaluation.json`,
  `reports/generated/ml_validation_bootstrap_ci.json`,
  `reports/generated/shap_global.csv`.
- Rule/ILP: `reports/generated/curriculum_validation.json`,
  `reports/generated/regulation_assumptions.md`,
  `reports/generated/plans_by_student.csv`,
  `reports/generated/ilp_sensitivity.csv`.
- Monte Carlo: `reports/generated/mc_results.csv`,
  `reports/generated/mc_pairwise.csv`, `reports/generated/mc_pareto.csv`.
- Kiểm thử/báo cáo/hướng dẫn: `reports/generated/pytest_summary.txt`,
  `reports/stage2_report.docx`, `docs/screens_to_capture.md`, `README.md`,
  `HANDOFF.md`.

Ảnh giao diện chưa có trong gói; dùng `docs/screens_to_capture.md` và chỉ chụp
hồ sơ SCENARIO. Không có `mc_grad_hist.csv` trong artifact hiện tại, vì vậy không
báo cáo phân phối kỳ tốt nghiệp suy ra.

## Trạng thái dọn cấu trúc Phần 5.5

- Cache/bytecode sinh lại được đã xóa; `.gitignore` loại `.venv`, `__pycache__`,
  `*.pyc`, `.pytest_cache` và `.ipynb_checkpoints`.
- Baseline SHA-256 được dựng từ tag `pre-restructure`; danh sách chính xác và
  so sánh hiện tại nằm tại `reports/generated/restructure_baseline.txt` và
  `reports/generated/restructure_hashes.csv`. Bộ lọc tag có 72 file sau khi
  loại `pytest_summary.txt` theo chỉ đạo; cả 72 hash đều khớp.
- Tài liệu kỹ thuật được chuyển từ `reports/` sang `docs/`; tài liệu/notebook
  Stage 1 được lưu trong `archive/`. `reports/data_dictionary.csv` còn bản
  tương thích byte-identical do `core/data/consistency.py` vẫn đọc đường dẫn đó.
- Trạng thái, cây thư mục, các mục REVIEW và kết quả cổng được ghi trong
  `cleanup_manifest.md`. Step 2C/2D được hoãn; các mục REVIEW chưa có quyết
  định cụ thể vẫn được giữ nguyên.
