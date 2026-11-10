# Historical HANDOFF — superseded

This archived note describes the previous SIMULATED Stage 1 pipeline and is
not current evidence or a source for final results. The active Part 1 status,
OFFICIAL curriculum validation, and scenario-v1 defect audit are recorded in
the repository-root `HANDOFF.md` and `reports/generated/`.

## Trạng thái

- **A/B:** UCI-697 khảo sát; raw giữ nguyên; CTĐT/persona là **SIMULATED**; validator PASS nguyên văn ở `reports/curriculum_validation.txt` và B.2 báo cáo gộp.
- **C:** exploratory models, leakage gate T1, calibration pass-rate, M1/C.3 đối chiếu, M3' baseline, restriction thresholds và persona REAL-derived đã cập nhật. Không huấn luyện mô hình cuối.
- **D:** rule engine tách academic flags/eligibility; cảnh báo rủi ro không khóa tải mặc định. ILP prototype dùng soft Fmax, Cmin fallback và status chuẩn; S003 có kế hoạch `best_effort` kèm cờ vượt cap.
- **E:** phân công/timeline cập nhật; TV3 nhận việc tự lấy CTĐT/quy chế NTU ở Tuần 1.
- **Chưa làm:** Monte Carlo nhiều kỳ/đối chứng B1–B3; mô hình cuối, UI và đánh giá hiệu quả NTU. Các persona chỉ sanity-check; không tuyên bố hiệu quả.

## Nhãn dữ liệu, mốc, seed

- `data/raw/uci_697/data.csv`: **REAL (UCI-697)**, giữ nguyên.
- Catalogue trong `data/processed/courses.csv` lấy từ PDF `210_CNTT.pdf`, mục 7.1. Các quan hệ tiên quyết theo mục này; tiến độ/hồ sơ trong `data/processed/` vẫn **SIMULATED** và chỉ gồm các học phần bắt buộc chung. Feature persona lấy từ medoid REAL của từng tercile năng lực HK1; S002 được kiểm tra thuộc Trung bình.
- Feature dự báo T1 chỉ dùng `available_at ∈ {T0,T1_known}`. `enrolled_2` là `T1_decision`, chỉ dùng trong phân tích tải/M1 diagnostic. Sáu trường chưa rõ timestamp bị loại.
- Seed chính: **20261105**.
- Chia grade 0–20 → 0–10 chỉ tạo feature ML fixture, không suy ngưỡng đạt NTU.

## Kết quả cần lưu ý

- Validator CTĐT kiểm tra các nhánh thay thế riêng: 101 dòng catalogue, 130 tín chỉ mỗi lộ trình.
- M1 binary OR `enrolled_2` 1,314506; M1 3-class effective OR 1,161026; C.3 observational OR 1,000469. Khác estimand, không nhân quả; M1 không dùng làm chính.
- Pass-rate holdout RF MAE/RMSE 0,124046/0,193556; isotonic 0,124389/0,195836, nên isotonic không dùng cho pass-rate. Bảng calibration 10 decile trong báo cáo.
- M3' all Target: Thấp 0,248377; Trung bình 0,779404; Cao 0,931902. Non-Dropout-only: 0,564428/0,833310/0,946581; đây là survivor-only hậu nghiệm, không dùng làm baseline. RF cho persona S003 là 0,048941; không chọn số thuận lợi.
- Warning tier OOF shares/PPV: Thấp 12,72%/4,89%; Trung bình 32,95%/7,80%; Cao 54,34%/53,25%. Restriction mềm exploratory threshold P calibrated ≥0,50, PPV 0,809; 173 người gần tỷ lệ nền 32,13%, không ai vượt threshold.
- Config `enforce_cap=false`; cap tín chỉ/Fmax là khuyến nghị mềm. Prototype giải từng scenario 12/15/18 × λ={0;0,1;0,3}. S003 tại 12, λ=0,1 chọn `IT501, IT502, IT503, IT504`, 12 tín chỉ; expected failures 2,980257, Fmax 1, slack 1,980257; `best_effort`, `risk_cap_exceeded=true`.
- Mô phỏng hazard dropout và chế độ có điều kiện không bỏ học đã đặc tả; chưa chạy Monte Carlo. Hazard hằng kỳ từ P(Dropout) là giả định, không phải ước lượng trực tiếp.

## Chạy lại

Từ gốc `E:\HHTQD_DoAn`, Python 3.14:

```powershell
python -m pip install -r requirements-stage1.txt
python src\data\validate_curriculum.py
python src\analysis\risk_to_plan_exploration.py
python src\optimize\plan_risk.py
python -m unittest discover -s tests -v
python src\analysis\ilp_formulation_check.py
python scripts\build_risk_exploration_notebook.py
python scripts\build_ilp_formulation_notebook.py
python -m jupyter nbconvert --to notebook --execute --inplace notebooks\02_risk_to_plan_exploration.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace notebooks\03_ilp_formulation_check.ipynb
```

`reports/generated/` được tái tạo từ pipeline: OOF warning/restriction, calibration deciles, M3'/non-Dropout, persona scenarios, ILP scenarios và recommendation. Notebook chỉ gọi lại pipeline/script, không là mô hình cuối. Validator ghi kết quả vào `reports/curriculum_validation.txt`.

## Cấu hình/method

- `P(Dropout)` dùng riêng cho warning/risk tier và khuyến nghị cố vấn; không nhân trực tiếp vào xác suất đạt môn.
- Warning ngưỡng recall và restriction threshold/PPV độc lập. Restriction threshold isotonic + PPV cùng train OOF có optimistic bias; phải đánh giá trên validation độc lập trước khi áp dụng.
- M3' pass-rate nền gộp mọi tải theo HK1; λ/difficulty/retake là **GIẢ ĐỊNH** kịch bản. `enrolled_2=0` không bị coi là Dropout/pass=0.
- ILP objective đo tín chỉ tương đương; β=1/8, γ=1 theo quy tắc trong spec; `u_i` là downstream credits chiết khấu. Fmax là số môn trượt kỳ vọng, khác với loss tín chỉ.
- Status ILP: `optimal`, `best_effort`, `no_eligible_courses`, `graduation_ready`, `infeasible_data_error`; xem `reports/optimization_spec.md`.
- Chưa có CTĐT/quy chế NTU được xác minh. Cap tín chỉ/GPA/attempts, λ, β/γ, deadline và risk policy đều có source/label/TODO trong `src/config/credit_rules.yaml`.

## Tệp chính

| Nhóm | Tệp |
|---|---|
| Báo cáo gộp/phương pháp/spec | `reports/stage1_report.md`, `reports/risk_to_plan_methods.md`, `reports/optimization_spec.md` |
| Config, rule, plan | `src/config/credit_rules.yaml`, `src/rules/rule_engine.py`, `src/optimize/plan_risk.py` |
| Prototype | `src/optimize/ilp_prototype.py`, `src/analysis/ilp_formulation_check.py`, `notebooks/03_ilp_formulation_check.ipynb` |
| C exploration | `src/analysis/risk_to_plan_exploration.py`, `notebooks/02_risk_to_plan_exploration.ipynb` |
| Persona/data/validation | `src/data/generate_simulated_data.py`, `reports/curriculum_validation.txt`, `reports/data_dictionary.csv` |
| Kết quả được sinh | `reports/generated/` |
| Tests | `tests/test_stage1_rules_and_optimizer.py` |
| Thư gửi cô (không sửa lượt này) | `reports/cover_message_to_co_Thuy.md` |

## Việc cần xác nhận trước giai đoạn 2

1. Nhãn `Enrolled` và mốc T1; timestamp 6 feature chưa rõ.
2. CTĐT/quy chế tín chỉ/GPA/học lại; tuần 1 TV3 tự tìm tài liệu và ghi nguồn.
3. Có duyệt warning + khuyến nghị mềm, threshold restriction/PPV exploratory và không hard-cap mặc định không.
4. Chấp nhận baseline M3', giả định độc lập, λ/difficulty/retake và hazard dropout như kịch bản không.
5. Tiêu chí so B1–B3 với dung sai 95% theo paired Monte Carlo SE.
6. Hạn nộp thực tế và thời gian nhóm có thể triển khai.
