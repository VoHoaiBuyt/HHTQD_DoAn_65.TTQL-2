# -*- coding: utf-8 -*-
"""Build a reproducible exploratory notebook for REAL (UCI-697)."""

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


ROOT = Path(__file__).resolve().parent
NOTEBOOK_PATH = ROOT / "notebooks" / "01_eda_uci697.ipynb"

nb = new_notebook()
nb.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
nb.cells = [
    new_markdown_cell(
        """# Khảo sát dữ liệu REAL (UCI-697)

**Nguồn:** *Predict Students' Dropout and Academic Success*, UCI ID 697.  
**Mục tiêu:** khảo sát chất lượng, biến mục tiêu, liên hệ thống kê và rủi ro rò rỉ theo thời điểm.  
**Phạm vi:** EDA; không huấn luyện mô hình cuối cùng. Tệp CSV gốc trong `data/raw/uci_697/` chỉ được đọc, không chỉnh sửa.

`Target` có ba trạng thái cuối cùng: `Dropout`, `Enrolled`, `Graduate`. EDA có thể so sánh Dropout với phần còn lại, nhưng `Enrolled` không được mặc định là đã an toàn hay chắc chắn sẽ bỏ học.
"""
    ),
    new_code_cell(
        """from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

plt.rcParams["figure.figsize"] = (9, 5)
plt.rcParams["axes.grid"] = True

candidate_paths = [
    Path("data/raw/uci_697/data.csv"),
    Path("../data/raw/uci_697/data.csv"),
]
DATA_PATH = next((path.resolve() for path in candidate_paths if path.is_file()), None)
if DATA_PATH is None:
    raise FileNotFoundError(
        "Không tìm thấy data/raw/uci_697/data.csv. "
        "Hãy chạy notebook từ thư mục gốc dự án hoặc notebooks/."
    )

df = pd.read_csv(DATA_PATH, sep=";")
df.columns = df.columns.str.strip()
print(f"Nguồn: REAL (UCI-697) — {DATA_PATH}")
print(f"Kích thước: {df.shape[0]:,} dòng × {df.shape[1]} thuộc tính")
display(df.head())
"""
    ),
    new_code_cell(
        """quality = pd.DataFrame(
    {
        "missing_count": df.isna().sum(),
        "missing_percent": (df.isna().mean() * 100).round(3),
        "dtype": df.dtypes.astype(str),
        "distinct_values": df.nunique(dropna=False),
    }
)
print(f"Tổng giá trị thiếu: {int(df.isna().sum().sum())}")
print(f"Số dòng trùng lặp hoàn toàn: {int(df.duplicated().sum())}")
print("Phân bố kiểu dữ liệu:")
print("REAL (UCI-697) — bảng chất lượng dữ liệu:")
display(df.dtypes.value_counts().rename_axis("dtype").to_frame("column_count"))
print("REAL (UCI-697) — từ điển kiểm tra từng thuộc tính:")
display(quality)
"""
    ),
    new_code_cell(
        """target_order = ["Dropout", "Enrolled", "Graduate"]
target_counts = df["Target"].value_counts().reindex(target_order, fill_value=0)
target_summary = pd.DataFrame(
    {
        "count": target_counts,
        "percent": (target_counts / len(df) * 100).round(2),
    }
)
print("REAL (UCI-697) — phân phối nhãn Target:")
display(target_summary)

ax = target_counts.plot(
    kind="bar",
    color=["#c0392b", "#e0a800", "#27864b"],
    edgecolor="black",
)
ax.set_title("Phân phối Target — REAL (UCI-697)")
ax.set_xlabel("Trạng thái")
ax.set_ylabel("Số sinh viên")
ax.tick_params(axis="x", rotation=0)
for position, value in enumerate(target_counts):
    ax.text(position, value, f"{value:,}\\n({value / len(df) * 100:.2f}%)",
            ha="center", va="bottom")
plt.tight_layout()
plt.show()

print(
    "Nhãn chính đề xuất: dự báo 3 lớp Target; xác suất lớp Dropout là chỉ báo "
    "nguy cơ bỏ học. Giữ Enrolled thành lớp riêng vì đây không đồng nghĩa "
    "với Graduate hoặc Non-dropout đã xác nhận."
)
print(
    "Chưa đặt ngưỡng xác suất cho nhãn cảnh báo cao; cần chọn bằng tập "
    "validation theo mục tiêu recall và kiểm tra hiệu chuẩn."
)
"""
    ),
    new_code_cell(
        """# Liên hệ Pearson giữa biến số và chỉ báo Dropout (mô tả, không hàm ý nhân quả).
df_eda = df.copy()
df_eda["dropout_indicator"] = df_eda["Target"].eq("Dropout").astype(int)
numeric_df = df_eda.select_dtypes(include="number")
dropout_corr = (
    numeric_df.corr(numeric_only=True)["dropout_indicator"]
    .drop("dropout_indicator")
    .sort_values(key=lambda values: values.abs(), ascending=False)
)
print("REAL (UCI-697) — tương quan với chỉ báo Dropout; gồm HK2, không phải tập đặc trưng hợp lệ tại T1:")
display(dropout_corr.head(15).rename("pearson_r").to_frame())

safe_t1_features = [
    "Curricular units 1st sem (enrolled)",
    "Curricular units 1st sem (evaluations)",
    "Curricular units 1st sem (approved)",
    "Curricular units 1st sem (grade)",
    "Curricular units 1st sem (without evaluations)",
]
print("REAL (UCI-697) — tương quan HK1, khả dụng sau khi kết thúc HK1 (T1):")
display(dropout_corr.reindex(safe_t1_features).rename("pearson_r").to_frame())

ax = dropout_corr.head(12).sort_values().plot(kind="barh", color="#4472c4")
ax.set_title("Tương quan đơn biến với Dropout — REAL (UCI-697)")
ax.set_xlabel("Pearson r (mô tả; không phải tác động nhân quả)")
plt.tight_layout()
plt.show()
"""
    ),
    new_code_cell(
        """# Cầu nối học thuật sang tiến độ/tín chỉ: UCI ghi số curricular units (học phần),
# không cung cấp số tín chỉ theo CTĐT của Trường ĐH Nha Trang.
bridge_features = [
    "Curricular units 1st sem (credited)",
    "Curricular units 1st sem (enrolled)",
    "Curricular units 1st sem (evaluations)",
    "Curricular units 1st sem (approved)",
    "Curricular units 1st sem (grade)",
    "Curricular units 1st sem (without evaluations)",
    "Curricular units 2nd sem (credited)",
    "Curricular units 2nd sem (enrolled)",
    "Curricular units 2nd sem (evaluations)",
    "Curricular units 2nd sem (approved)",
    "Curricular units 2nd sem (grade)",
    "Curricular units 2nd sem (without evaluations)",
]
print("REAL (UCI-697) — trung bình các thuộc tính học thuật theo Target; HK2 là mô tả hậu nghiệm:")
display(df.groupby("Target", observed=True)[bridge_features].mean().round(3).T)

hk1 = [
    "Curricular units 1st sem (enrolled)",
    "Curricular units 1st sem (approved)",
    "Curricular units 1st sem (grade)",
]
print("REAL (UCI-697) — trung bình các thuộc tính HK1 theo Target:")
display(df.groupby("Target", observed=True)[hk1].mean().round(3))

print(
    "Không quy đổi trực tiếp số học phần trong UCI thành tín chỉ NTU: "
    "cần bảng ánh xạ CTĐT/khối lượng tín chỉ riêng."
)
"""
    ),
    new_code_cell(
        """        # Mốc vận hành: T1 = sau khi có kết quả HK1, trước khi đăng ký HK2.
timing_groups = {
            "T0 — thông tin đầu vào": [
        "Marital status", "Application mode", "Application order", "Course",
        "Daytime/evening attendance", "Previous qualification",
        "Previous qualification (grade)", "Nacionality", "Mother's qualification",
        "Father's qualification", "Mother's occupation", "Father's occupation",
        "Admission grade", "Displaced", "Educational special needs", "Gender",
        "Age at enrollment", "International",
    ],
    "T1_known — kết quả HK1": [name for name in df.columns if "1st sem" in name],
    "T1_decision — lựa chọn đăng ký HK2, không phải feature đã quan sát": [
        "Curricular units 2nd sem (credited)",
        "Curricular units 2nd sem (enrolled)",
    ],
    "post_outcome — kết quả HK2 và Target": [
        "Curricular units 2nd sem (evaluations)",
        "Curricular units 2nd sem (approved)",
        "Curricular units 2nd sem (grade)",
        "Curricular units 2nd sem (without evaluations)",
        "Target",
    ],
    "Chưa xác minh — loại khỏi feature T1 cơ sở": [
        "Debtor",
        "Tuition fees up to date",
        "Scholarship holder",
        "Unemployment rate",
        "Inflation rate",
        "GDP",
    ],
}
print("REAL (UCI-697) — phân nhóm thuộc tính theo thời điểm quan sát:")
for timing, columns in timing_groups.items():
    print(f"{timing}: {len(columns)} thuộc tính")
    print(", ".join(columns))

print(
    "Nguồn thời điểm: UCI ID 697 mô tả thông tin đầu vào tại enrollment và thành "
    "tích cuối HK1/HK2; bài báo trích dẫn trên UCI không truy cập được toàn văn. "
    "Tài liệu không chỉ rõ thời điểm chụp sáu biến chưa xác minh."
)
print(
    "Tại T1, enrolled/credited HK2 biểu diễn quyết định/đầu vào mô phỏng kịch bản, "
    "không phải feature đã quan sát cho ML. Chỉ sáu kết quả HK2 là hậu nghiệm/leakage."
)
"""
    ),
]

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
nbformat.write(nb, NOTEBOOK_PATH)
print(f"Created {NOTEBOOK_PATH}")
