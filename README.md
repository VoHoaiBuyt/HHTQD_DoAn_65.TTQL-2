# Academic Advisor Decision Support System

> **Hệ thống Hỗ trợ Quyết định Cố vấn Học tập**  
> Cảnh báo sớm rủi ro bỏ học · Lộ trình tín chỉ tối ưu · Mô phỏng Monte Carlo

---

## Mục lục

- [Tại sao có hệ thống này?](#-tại-sao-có-hệ-thống-này)
- [Hệ thống làm được gì?](#-hệ-thống-làm-được-gì)
- [Kiến trúc tổng quan](#-kiến-trúc-tổng-quan)
- [Cài đặt môi trường](#-cài-đặt-môi-trường)
- [Hướng dẫn chạy từng thành phần](#-hướng-dẫn-chạy-từng-thành-phần)
  - [1. Kiểm tra chương trình đào tạo](#1-kiểm-tra-chương-trình-đào-tạo)
  - [2. Huấn luyện mô hình ML](#2-huấn-luyện-mô-hình-ml)
  - [3. Benchmark so sánh mô hình](#3-benchmark-so-sánh-mô-hình)
  - [4. Mô phỏng Monte Carlo](#4-mô-phỏng-monte-carlo)
  - [5. Giao diện Streamlit](#5-giao-diện-streamlit)
  - [6. Chạy Unit Tests](#6-chạy-unit-tests)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Dữ liệu sử dụng](#-dữ-liệu-sử-dụng)
- [Lưu ý nghiên cứu](#-lưu-ý-nghiên-cứu)

---

## 🎯 Tại sao có hệ thống này?

Trong thực tế, **cố vấn học tập** phải theo dõi hàng trăm sinh viên mỗi học kỳ. Việc phát hiện sớm sinh viên có nguy cơ bỏ học và xây dựng lộ trình đăng ký tín chỉ phù hợp thường dựa vào kinh nghiệm cá nhân — tốn thời gian, dễ bỏ sót và thiếu nhất quán.

**Ba vấn đề cụ thể hệ thống này giải quyết:**

| Vấn đề | Hạn chế hiện tại | Giải pháp trong hệ thống |
|--------|-----------------|--------------------------|
| Phát hiện rủi ro bỏ học | Chỉ dựa vào cảm quan, không có con số | Mô hình ML (LR / RF / LightGBM) dự báo xác suất bỏ học tại T1 |
| Xây dựng lộ trình đăng ký | Thủ công, không tối ưu tải học | ILP tối ưu hóa đăng ký tín chỉ theo ngưỡng rủi ro của từng sinh viên |
| Đánh giá hiệu quả chiến lược | Không có cơ sở định lượng | Monte Carlo ≥ 1,000 lượt so sánh ILP với 3 baseline (B1/B2/B3) |

> **Nguyên tắc thiết kế quan trọng:** Hệ thống **không tự động khóa quyền đăng ký** của sinh viên. Mọi cảnh báo đều là gợi ý cho cố vấn — quyết định cuối cùng thuộc về con người.

---

## 🔧 Hệ thống làm được gì?

```
Nhập hồ sơ sinh viên
        │
        ▼
┌───────────────────┐     ┌──────────────────────────┐
│   Rule Engine     │────▶│  Danh sách môn đủ ĐK     │
│  (Tiên quyết /    │     │  (fixed-point iteration) │
│   Song hành)      │     └──────────────┬───────────┘
└───────────────────┘                    │
                                         ▼
┌───────────────────┐     ┌──────────────────────────┐
│   ML Risk Model   │────▶│  P(dropout) · Tier cảnh  │
│  LR / RF / LGBM   │     │  báo: Thấp/Trung/Cao     │
└───────────────────┘     └──────────────┬───────────┘
                                         │
                                         ▼
┌───────────────────┐     ┌──────────────────────────┐
│   ILP Optimizer   │────▶│  3 phương án đăng ký:    │
│  (PuLP + HiGHS)   │     │  An toàn / Tiến độ /     │
└───────────────────┘     │  Cân bằng                │
                          └──────────────┬───────────┘
                                         │
                                         ▼
                          ┌──────────────────────────┐
                          │  Monte Carlo Simulation  │
                          │  ILP vs B1 vs B2 vs B3   │
                          │  95% CI · Pareto Frontier│
                          └──────────────────────────┘
```

---

## 🏗️ Kiến trúc tổng quan

```
📦 Academic-Advisor-Decision-Support-System
├── 🖥️  app/
│   └── streamlit_app.py          ← Giao diện web (4 tab)
├── 📊  scripts/
│   ├── train_and_save_models.py  ← Huấn luyện & lưu mô hình
│   ├── benchmark_risk_models.py  ← Benchmark ML (60/20/20 split)
│   └── monte_carlo_strategies.py ← Mô phỏng 4 chiến lược
├── 🧠  src/
│   ├── rules/rule_engine.py      ← Kiểm tra tiên quyết / song hành
│   ├── optimize/ilp_prototype.py ← ILP tối ưu đăng ký tín chỉ
│   ├── analysis/                 ← Khám phá dữ liệu & ML
│   ├── services/assessment.py   ← Orchestration: ML + Rule + ILP
│   └── config/credit_rules.yaml ← Cấu hình ngưỡng & tham số
├── 🧪  tests/
│   ├── test_dss_core.py          ← 35 unit tests (rule + ILP)
│   └── test_stage1_rules_and_optimizer.py
├── 📁  data/
│   ├── raw/uci_697/data.csv      ← Dữ liệu THỰC (4,424 sinh viên)
│   └── simulated/                ← CTĐT & persona mô phỏng
└── 📈  reports/generated/        ← Kết quả CSV/PNG/JSON
```

---

## ⚙️ Cài đặt môi trường

**Yêu cầu:** Python 3.11+

```bash
# 1. Clone repo
git clone https://github.com/vothanhtong/Academic-Advisor-Decision-Support-System.git
cd Academic-Advisor-Decision-Support-System

# 2. Tạo virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# hoặc: .venv\Scripts\activate   # Windows

# 3. Cài đặt thư viện
pip install -r requirements-app.txt
```

<details>
<summary>📦 Thư viện chính</summary>

| Thư viện | Mục đích |
|----------|----------|
| `streamlit` | Giao diện web |
| `pulp` + `highspy` | ILP solver (HiGHS) |
| `scikit-learn` | LR, RF, calibration, metrics |
| `lightgbm` | Gradient boosting classifier |
| `shap` | Giải thích mô hình (SHAP values) |
| `pandas` / `numpy` | Xử lý dữ liệu |
| `matplotlib` | Biểu đồ |

</details>

---

## 🚀 Hướng dẫn chạy từng thành phần

### 1. Kiểm tra chương trình đào tạo

Xác minh toàn bộ CTĐT mô phỏng (48 học phần, 128 tín chỉ) không có vòng lặp tiên quyết hoặc lỗi cấu trúc.

```bash
python src/data/validate_curriculum.py
```

**Kết quả mong đợi:**
```
✓ 11 kiểm tra — KẾT LUẬN: PASS
Báo cáo: reports/curriculum_validation.txt
```

---

### 2. Huấn luyện mô hình ML

Huấn luyện mô hình dự báo rủi ro bỏ học từ dữ liệu UCI-697 và lưu bundle.

```bash
python scripts/train_and_save_models.py
```

**Kết quả:** `artifacts/risk_bundle.joblib` — dùng cho UI và Monte Carlo.

---

### 3. Benchmark so sánh mô hình

So sánh 3 thuật toán (LR, RandomForest, LightGBM) theo chuẩn nghiên cứu:

```
Protocol:
  ├── 60% Train  → 5-fold CV, chọn siêu tham số
  ├── 20% Val    → Calibration (isotonic) + threshold tuning
  └── 20% Test   → Đánh giá cuối (chỉ chạy 1 lần)
```

```bash
python scripts/benchmark_risk_models.py
```

**Kết quả xuất ra `reports/generated/`:**

| File | Nội dung |
|------|----------|
| `ml_benchmark_summary.csv` | Accuracy, Macro-F1, PR-AUC, Brier, Confusion Matrix |
| `ml_benchmark_cv_folds.csv` | Kết quả 5-fold CV trên tập Train |
| `ml_benchmark_calibration.csv` | Calibration curve (validation) |
| `shap_lgbm_global.csv` / `.png` | Top features theo SHAP (LightGBM) |
| `shap_lr_global.csv` / `.png` | Top features theo SHAP (LR) |

> **Lưu ý:** SHAP chỉ phản ánh mức đóng góp của feature vào **dự đoán của mô hình**, không phải quan hệ nhân quả.

**Ví dụ kết quả:**
```
Task     Model               macro-F1   dropout-F1   PR-AUC   Brier
3-class  LightGBM            0.6115     0.6144       0.739    0.145
binary   LogisticRegression  0.7780     0.6964       0.783    0.129
binary   RandomForest        0.7520     0.6595       0.716    0.147
binary   LightGBM            0.7654     0.6752       0.730    0.145
```

---

### 4. Mô phỏng Monte Carlo

So sánh chiến lược ILP với 3 baseline qua ≥ 1,000 lượt mô phỏng mỗi sinh viên.

**Tham số giả định** (thay đổi để phân tích độ nhạy):

| Tham số | Giá trị mặc định | Mô tả |
|---------|-----------------|-------|
| `λ` (load lambda) | `0.1` | Hệ số giảm xác suất theo tải học tập |
| Retake multiplier | `1.0` | Thi lại không có lợi thế so với lần đầu |
| Difficulty range | `0.7 – 1.3` | Hệ số độ khó theo nhóm học phần |
| P(Dropout) | Từ ML model | Chỉ dùng phân tầng cảnh báo, **không** là hazard rate |

```bash
# Chạy mặc định (1,000 lượt × 7 sinh viên × 4 chiến lược)
python scripts/monte_carlo_strategies.py

# Chạy nhanh để kiểm tra (100 lượt)
python scripts/monte_carlo_strategies.py --runs 100

# Chỉ chạy cho một số sinh viên cụ thể
python scripts/monte_carlo_strategies.py --students S001,S003
```

**Kết quả xuất ra `reports/generated/`:**

| File | Nội dung |
|------|----------|
| `monte_carlo_summary.csv` | 5 chỉ tiêu + 95% CI theo chiến lược |
| `monte_carlo_by_student.csv` | Phân tích chi tiết từng sinh viên |
| `monte_carlo_paired_differences.csv` | ILP vs B1/B2/B3 (paired differences) |
| `monte_carlo_pareto.png` | Pareto frontier: on-time vs failures |
| `monte_carlo_runs.csv` | Raw data toàn bộ lượt chạy |

**5 chỉ tiêu đánh giá (đều có 95% CI):**

| # | Chỉ tiêu | Cột CSV |
|---|----------|---------|
| 1 | Số học kỳ dự kiến tốt nghiệp | `mean_semesters_to_graduation` |
| 2 | Xác suất tốt nghiệp đúng hạn (≤ HK8) | `on_time_rate` |
| 3 | Số môn trượt kỳ vọng | `mean_simulated_failures` |
| 4 | Số tín chỉ tích lũy trung bình | `mean_credits_earned` |
| 5 | Tỷ lệ phương án khả thi | `feasibility_rate` |

**4 chiến lược đối sánh:**

| Chiến lược | Mô tả |
|-----------|-------|
| **ILP** | PuLP + HiGHS, tối ưu theo P(pass) và rủi ro từng sinh viên |
| **B1** | Đúng lộ trình chuẩn CTĐT + ưu tiên thi lại môn trượt |
| **B2** | Tham lam — đăng ký tối đa 18 tín chỉ có thể |
| **B3** | Cố định 15 tín chỉ/học kỳ |

---

### 5. Giao diện Streamlit

Giao diện web tương tác với 4 tab:

```bash
streamlit run app/streamlit_app.py
```

Mở trình duyệt tại: **http://localhost:8501**

| Tab | Chức năng |
|-----|-----------|
| **Nhập hồ sơ** | Upload CSV hoặc nhập tay thông tin sinh viên |
| **Đánh giá rủi ro** | Xem P(dropout), tier cảnh báo, SHAP top features |
| **Lộ trình tín chỉ** | So sánh 3 phương án ILP (An toàn / Tiến độ / Cân bằng) |
| **Mô phỏng** | Kết quả Monte Carlo tổng quan và theo từng sinh viên |

---

### 6. Chạy Unit Tests

```bash
pytest tests/ -v
```

**Kết quả mong đợi:** `35 passed` trong vòng < 5 giây.

| Nhóm test | Số test | Nội dung |
|-----------|---------|----------|
| `TestConcurrentChainBlocking` | 5 | Thuật toán fixed-point: môn song hành dây chuyền |
| `TestStudentIdIsolation` | 4 | Không trộn dữ liệu giữa các sinh viên |
| `TestILPBestEffort` | 5 | Gắn cờ `best_effort` khi kỳ vọng trượt > F_max |
| `TestILPEdgeCases` | 7 | Vô nghiệm, tốt nghiệp, trùng lặp, tham số lỗi |
| `TestILPLoadBasis` | 2 | Hội tụ load basis sau ≤ 3 vòng lặp |
| `TestILPVariants` | 8 | 3 objective profiles: safe / progress / balanced |
| `TestCurriculumValidation` | 4 | Tính nhất quán log kiểm tra CTĐT |

---

## 📁 Cấu trúc thư mục

```
.
├── app/
│   └── streamlit_app.py              # Giao diện web Streamlit
├── artifacts/
│   └── risk_bundle.joblib            # Mô hình ML đã huấn luyện
├── data/
│   ├── raw/uci_697/data.csv          # Dataset THỰC — 4,424 sinh viên
│   └── simulated/                    # CTĐT + persona sinh viên (MÔ PHỎNG)
│       ├── courses.csv
│       ├── prerequisites.csv
│       ├── student_profile.csv
│       └── student_progress.csv
├── notebooks/
│   ├── 01_eda_uci697.ipynb           # EDA dataset UCI-697
│   ├── 02_risk_to_plan_exploration.ipynb
│   └── 03_ilp_formulation_check.ipynb
├── reports/
│   ├── generated/                    # Outputs CSV/PNG/JSON tự sinh
│   └── diagrams/                     # Sơ đồ kiến trúc & ER
├── scripts/
│   ├── benchmark_risk_models.py      # Benchmark LR/RF/LightGBM
│   ├── monte_carlo_strategies.py     # Monte Carlo ILP vs B1/B2/B3
│   └── train_and_save_models.py      # Huấn luyện & lưu bundle
├── src/
│   ├── config/credit_rules.yaml      # Cấu hình ngưỡng & tham số
│   ├── optimize/ilp_prototype.py     # ILP solver (PuLP + HiGHS)
│   ├── rules/rule_engine.py          # Kiểm tra tiên quyết/song hành
│   ├── services/assessment.py        # Orchestration tổng thể
│   └── analysis/                     # Risk & plan exploration
├── tests/
│   ├── test_dss_core.py              # 35 unit tests (rule + ILP + MC)
│   └── test_stage1_rules_and_optimizer.py
├── conftest.py                        # pytest path setup
├── requirements-app.txt
└── README.md
```

---

## 📊 Dữ liệu sử dụng

| Nguồn | Loại | Mô tả |
|-------|------|-------|
| **UCI-697** | **THỰC** | 4,424 sinh viên đại học Bồ Đào Nha; nhãn Dropout / Enrolled / Graduate |
| **CTĐT mô phỏng** | **MÔ PHỎNG** | 48 học phần, 128 tín chỉ; không phải dữ liệu trường thực |
| **Persona sinh viên** | **MÔ PHỎNG** | 8 sinh viên (S001–S008) với các profile rủi ro khác nhau |

---

## ⚠️ Lưu ý nghiên cứu

- **Mô hình ML** được huấn luyện trên dữ liệu UCI-697 (Bồ Đào Nha). Hiệu suất có thể khác khi áp dụng cho sinh viên Việt Nam.
- **CTĐT và kết quả Monte Carlo** là **MÔ PHỎNG** — không phải bằng chứng từ trường thực.
- **SHAP** giải thích đóng góp của feature vào dự đoán, **không** chứng minh quan hệ nhân quả.
- Hệ thống **không tự động khóa quyền đăng ký** của sinh viên dù ở mức rủi ro cao nhất.

---

<div align="center">

Được phát triển trong khuôn khổ đồ án môn **Hệ thống Hỗ trợ Quyết định**  
Nhóm 1 · 65.TTQL-2

</div>
