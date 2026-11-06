# -*- coding: utf-8 -*-
"""Generate the UCI-697 data dictionary from the verified raw CSV."""

import csv
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "raw" / "uci_697" / "data.csv"
OUTPUT_PATH = ROOT / "reports" / "data_dictionary.csv"

METADATA = {
    "Marital status": (
        "Tình trạng hôn nhân của sinh viên.",
        "Nhân khẩu học",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thuộc thông tin hồ sơ đầu vào; cần xác nhận quy trình cập nhật nếu có thay đổi.",
    ),
    "Application mode": (
        "Mã phương thức tuyển sinh.",
        "Học thuật đầu vào",
        "Tuyển sinh/nhập học (T0).",
        "Không (tại T1).",
        "Được xác định trước khi học kỳ 1 bắt đầu.",
    ),
    "Application order": (
        "Thứ tự ưu tiên nguyện vọng tuyển sinh.",
        "Học thuật đầu vào",
        "Tuyển sinh/nhập học (T0).",
        "Không (tại T1).",
        "Được xác định trong hồ sơ tuyển sinh.",
    ),
    "Course": (
        "Mã ngành/chương trình sinh viên theo học.",
        "Học thuật đầu vào",
        "Tuyển sinh/nhập học (T0).",
        "Không (tại T1).",
        "Ngành học được xác định khi nhập học.",
    ),
    "Daytime/evening attendance": (
        "Hình thức học ban ngày hoặc buổi tối.",
        "Học thuật đầu vào",
        "Tuyển sinh/nhập học (T0).",
        "Không (tại T1).",
        "Thông tin hình thức học ban đầu.",
    ),
    "Previous qualification": (
        "Mã bằng cấp/trình độ học vấn trước khi nhập học.",
        "Học thuật đầu vào",
        "Hồ sơ tuyển sinh (T0).",
        "Không (tại T1).",
        "Bằng cấp đã có trước khi vào trường.",
    ),
    "Previous qualification (grade)": (
        "Điểm của bằng cấp/trình độ học vấn trước khi nhập học.",
        "Học thuật đầu vào",
        "Hồ sơ tuyển sinh (T0).",
        "Không (tại T1).",
        "Kết quả học tập có trước thời điểm dự báo.",
    ),
    "Nacionality": (
        "Mã quốc tịch (tên thuộc tính theo tệp nguồn).",
        "Nhân khẩu học",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thuộc thông tin hồ sơ đầu vào.",
    ),
    "Mother's qualification": (
        "Mã trình độ học vấn của mẹ.",
        "Kinh tế–xã hội",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin gia đình có sẵn tại hồ sơ đầu vào.",
    ),
    "Father's qualification": (
        "Mã trình độ học vấn của cha.",
        "Kinh tế–xã hội",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin gia đình có sẵn tại hồ sơ đầu vào.",
    ),
    "Mother's occupation": (
        "Mã nghề nghiệp của mẹ.",
        "Kinh tế–xã hội",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin gia đình có sẵn tại hồ sơ đầu vào.",
    ),
    "Father's occupation": (
        "Mã nghề nghiệp của cha.",
        "Kinh tế–xã hội",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin gia đình có sẵn tại hồ sơ đầu vào.",
    ),
    "Admission grade": (
        "Điểm xét tuyển/đầu vào đại học.",
        "Học thuật đầu vào",
        "Tuyển sinh/nhập học (T0).",
        "Không (tại T1).",
        "Được ghi nhận trước khi bắt đầu học.",
    ),
    "Displaced": (
        "Chỉ báo sinh viên sống xa nơi thường trú/gia đình.",
        "Nhân khẩu học",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin đầu vào; cần xác nhận định nghĩa mã hóa với tài liệu UCI.",
    ),
    "Educational special needs": (
        "Chỉ báo nhu cầu hỗ trợ giáo dục đặc biệt.",
        "Nhân khẩu học",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin đầu vào; cần tuân thủ quyền riêng tư khi sử dụng.",
    ),
    "Debtor": (
        "Chỉ báo sinh viên có khoản nợ/đang nợ theo mã của bộ dữ liệu.",
        "Kinh tế–xã hội",
        "Thời điểm chụp trạng thái không được xác định trong CSV.",
        "Có thể có.",
        "Chỉ dùng tại T1 nếu xác minh trạng thái đã được ghi nhận không muộn hơn T1.",
    ),
    "Tuition fees up to date": (
        "Chỉ báo học phí đã được thanh toán đúng hạn.",
        "Kinh tế–xã hội",
        "Thời điểm chụp trạng thái không được xác định trong CSV.",
        "Có thể có.",
        "Chỉ dùng tại T1 nếu xác minh trạng thái đã được ghi nhận không muộn hơn T1.",
    ),
    "Gender": (
        "Mã giới tính theo cách mã hóa của bộ dữ liệu.",
        "Nhân khẩu học",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thông tin hồ sơ đầu vào; không suy diễn ý nghĩa 0/1 nếu chưa tra từ điển UCI.",
    ),
    "Scholarship holder": (
        "Chỉ báo sinh viên thuộc diện nhận học bổng.",
        "Kinh tế–xã hội",
        "Thời điểm và kỳ xét học bổng không được xác định trong CSV.",
        "Có thể có.",
        "Chỉ dùng tại T1 nếu xác minh trạng thái học bổng đã có tại mốc đó.",
    ),
    "Age at enrollment": (
        "Tuổi của sinh viên khi nhập học.",
        "Nhân khẩu học",
        "Nhập học (T0).",
        "Không (tại T1).",
        "Mốc tuổi được xác định tại thời điểm nhập học.",
    ),
    "International": (
        "Chỉ báo sinh viên quốc tế.",
        "Nhân khẩu học",
        "Hồ sơ khi nhập học (T0).",
        "Không (tại T1).",
        "Thuộc hồ sơ đầu vào.",
    ),
    "Curricular units 1st sem (credited)": (
        "Số học phần học kỳ 1 được công nhận/miễn trừ.",
        "Học thuật HK1",
        "Đến hết HK1 (T1).",
        "Không (cho dự báo tại T1).",
        "Đã phát sinh trước khi dự báo sau HK1; không dùng nếu mốc dự báo là T0.",
    ),
    "Curricular units 1st sem (enrolled)": (
        "Số học phần đăng ký trong học kỳ 1.",
        "Học thuật HK1",
        "Sau đợt đăng ký HK1; muộn nhất tại T1.",
        "Không (cho dự báo tại T1).",
        "Có thể là đặc trưng tại T1, nhưng không có sẵn tại mốc trước đăng ký HK1.",
    ),
    "Curricular units 1st sem (evaluations)": (
        "Số lượt đánh giá/thi của các học phần học kỳ 1.",
        "Học thuật HK1",
        "Đến hết HK1 (T1).",
        "Không (cho dự báo tại T1).",
        "Chỉ được dùng sau khi hoạt động đánh giá HK1 đã diễn ra.",
    ),
    "Curricular units 1st sem (approved)": (
        "Số học phần học kỳ 1 đạt/được công nhận hoàn thành.",
        "Học thuật HK1",
        "Sau khi có kết quả HK1 (T1).",
        "Không (cho dự báo tại T1).",
        "Chỉ có sẵn sau khi kết thúc đánh giá HK1; cầu nối tiến độ học tập.",
    ),
    "Curricular units 1st sem (grade)": (
        "Điểm trung bình học phần học kỳ 1 theo thang của bộ dữ liệu.",
        "Học thuật HK1",
        "Sau khi có kết quả HK1 (T1).",
        "Không (cho dự báo tại T1).",
        "Kết quả quá khứ tại mốc T1; không dùng nếu dự báo trước khi hoàn thành HK1.",
    ),
    "Curricular units 1st sem (without evaluations)": (
        "Số học phần HK1 không có lượt đánh giá.",
        "Học thuật HK1",
        "Đến hết HK1 (T1).",
        "Không (cho dự báo tại T1).",
        "Chỉ được xác định sau khi kỳ đánh giá HK1 kết thúc.",
    ),
    "Curricular units 2nd sem (credited)": (
        "Số học phần học kỳ 2 được công nhận/miễn trừ.",
        "Học thuật HK2",
        "Trong/sau HK2 (T2).",
        "Có.",
        "Chưa tồn tại tại mốc dự báo T1 trước khi đăng ký HK2.",
    ),
    "Curricular units 2nd sem (enrolled)": (
        "Số học phần đăng ký trong học kỳ 2.",
        "Học thuật HK2",
        "Sau đợt đăng ký HK2 (sau T1).",
        "Có.",
        "Là thông tin tương lai đối với quyết định đăng ký tại T1; loại khỏi mô hình T1.",
    ),
    "Curricular units 2nd sem (evaluations)": (
        "Số lượt đánh giá/thi của các học phần học kỳ 2.",
        "Học thuật HK2",
        "Đến hết HK2 (T2).",
        "Có.",
        "Hoạt động đánh giá chưa diễn ra tại T1.",
    ),
    "Curricular units 2nd sem (approved)": (
        "Số học phần học kỳ 2 đạt/được công nhận hoàn thành.",
        "Học thuật HK2",
        "Sau khi có kết quả HK2 (T2).",
        "Có.",
        "Kết quả tương lai tại T1; tương quan lớn với Target không phải bằng chứng dự báo hợp lệ.",
    ),
    "Curricular units 2nd sem (grade)": (
        "Điểm trung bình học phần học kỳ 2 theo thang của bộ dữ liệu.",
        "Học thuật HK2",
        "Sau khi có kết quả HK2 (T2).",
        "Có.",
        "Điểm HK2 chưa được tạo tại T1.",
    ),
    "Curricular units 2nd sem (without evaluations)": (
        "Số học phần HK2 không có lượt đánh giá.",
        "Học thuật HK2",
        "Đến hết HK2 (T2).",
        "Có.",
        "Chưa thể quan sát tại T1.",
    ),
    "Unemployment rate": (
        "Tỷ lệ thất nghiệp vĩ mô gắn với quan sát sinh viên.",
        "Vĩ mô",
        "Theo năm; ngày công bố/ghép dữ liệu chưa có trong CSV.",
        "Có thể có.",
        "Chỉ dùng nếu giá trị của đúng năm dự báo đã công bố tại T1.",
    ),
    "Inflation rate": (
        "Tỷ lệ lạm phát vĩ mô gắn với quan sát sinh viên.",
        "Vĩ mô",
        "Theo năm; ngày công bố/ghép dữ liệu chưa có trong CSV.",
        "Có thể có.",
        "Chỉ dùng nếu giá trị của đúng năm dự báo đã công bố tại T1.",
    ),
    "GDP": (
        "Chỉ số GDP vĩ mô gắn với quan sát sinh viên.",
        "Vĩ mô",
        "Theo năm; ngày công bố/ghép dữ liệu chưa có trong CSV.",
        "Có thể có.",
        "Chỉ dùng nếu giá trị của đúng năm dự báo đã công bố tại T1.",
    ),
    "Target": (
        "Trạng thái cuối cùng: Dropout, Enrolled hoặc Graduate.",
        "Biến mục tiêu",
        "Trạng thái tại thời điểm kết thúc/quan sát trong nghiên cứu.",
        "Không áp dụng (nhãn).",
        "Nhãn cần dự đoán; tuyệt đối không dùng làm đặc trưng đầu vào.",
    ),
}

CATEGORICAL_FIELDS = {
    "Marital status",
    "Application mode",
    "Application order",
    "Course",
    "Daytime/evening attendance",
    "Previous qualification",
    "Nacionality",
    "Mother's qualification",
    "Father's qualification",
    "Mother's occupation",
    "Father's occupation",
    "Displaced",
    "Educational special needs",
    "Debtor",
    "Tuition fees up to date",
    "Gender",
    "Scholarship holder",
    "International",
    "Target",
}

T0_ATTRIBUTES = {
    "Marital status",
    "Application mode",
    "Application order",
    "Course",
    "Daytime/evening attendance",
    "Previous qualification",
    "Previous qualification (grade)",
    "Nacionality",
    "Mother's qualification",
    "Father's qualification",
    "Mother's occupation",
    "Father's occupation",
    "Admission grade",
    "Displaced",
    "Educational special needs",
    "Gender",
    "Age at enrollment",
    "International",
}
UNVERIFIED_ATTRIBUTES = {
    "Debtor",
    "Tuition fees up to date",
    "Scholarship holder",
    "Unemployment rate",
    "Inflation rate",
    "GDP",
}
HK2_DECISION_ATTRIBUTES = {
    "Curricular units 2nd sem (credited)",
    "Curricular units 2nd sem (enrolled)",
}
HK2_POST_OUTCOME_ATTRIBUTES = {
    "Curricular units 2nd sem (evaluations)",
    "Curricular units 2nd sem (approved)",
    "Curricular units 2nd sem (grade)",
    "Curricular units 2nd sem (without evaluations)",
}
UCI_DATASET_SOURCE = (
    "UCI ID 697, trang mô tả và bảng biến, "
    "https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success "
    "(truy cập 2026-11-05)."
)
UCI_PAPER_SOURCE = (
    "Bài báo UCI trích dẫn: M. V. Martins et al., "
    "\"Early prediction of student's performance in higher education: a case study\" (2021), "
    "DOI https://doi.org/10.1007/978-3-030-72657-7_16; "
    "toàn văn không truy cập được để xác minh timestamp từng biến."
)


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu REAL (UCI-697): {DATA_PATH}")

    df = pd.read_csv(DATA_PATH, sep=";")
    df.columns = df.columns.str.strip()
    if set(df.columns) != set(METADATA):
        missing = sorted(set(df.columns) - set(METADATA))
        extra = sorted(set(METADATA) - set(df.columns))
        raise ValueError(f"Schema nguồn không khớp; thiếu metadata={missing}, thừa metadata={extra}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "data_label",
        "attribute_name",
        "data_type",
        "meaning",
        "group",
        "availability_timing",
        "available_at",
        "availability_source",
        "leakage_risk",
        "leakage_reason",
    ]
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for name in df.columns:
            meaning, group, timing, risk, reason = METADATA[name]
            if name in T0_ATTRIBUTES:
                available_at = "T0"
                timing = "Đầu vào/tuyển sinh (T0)."
                availability_source = (
                    f"{UCI_DATASET_SOURCE} Trang UCI mô tả thông tin đầu vào tại thời điểm nhập học."
                )
            elif "1st sem" in name:
                available_at = "T1_known"
                timing = "Kết quả/hoàn tất HK1 (đã biết tại T1)."
                availability_source = (
                    f"{UCI_DATASET_SOURCE} Thành tích HK1 được ghi nhận cuối học kỳ; "
                    "dùng sau khi có kết quả HK1."
                )
            elif name in HK2_DECISION_ATTRIBUTES:
                available_at = "T1_decision"
                timing = "Quyết định/đầu vào mô phỏng khi đăng ký HK2 (T1)."
                availability_source = (
                    f"{UCI_DATASET_SOURCE} Tại T1 đây là biến quyết định lúc đăng ký HK2; "
                    "dùng làm đầu vào mô phỏng kịch bản, không phải leakage."
                )
                risk = "Không"
                reason = (
                    "Giá trị đăng ký HK2 là quyết định cần mô phỏng tại T1; "
                    "không dùng làm đặc trưng đã quan sát của ML."
                )
            elif name in HK2_POST_OUTCOME_ATTRIBUTES:
                available_at = "post_outcome"
                timing = "Kết quả sau khi HK2 diễn ra (post-outcome)."
                availability_source = (
                    f"{UCI_DATASET_SOURCE} Thành tích HK2 chỉ được ghi nhận cuối HK2."
                )
                risk = "Có (leakage tại T1)"
                reason = "Thông tin phát sinh sau quyết định T1; không đưa vào đặc trưng dự báo T1."
            elif name in UNVERIFIED_ATTRIBUTES:
                available_at = "chưa xác minh"
                timing = "Chưa xác minh theo tài liệu truy cập."
                availability_source = (
                    f"{UCI_DATASET_SOURCE} Bảng biến không nêu timestamp theo từng trường; "
                    f"{UCI_PAPER_SOURCE} Không đủ căn cứ xác định trường này đã có tại T1."
                )
                risk = "Chưa xác minh"
                reason = (
                    "Không có timestamp theo từng trường trong tài liệu đã truy cập; "
                    "loại khỏi bộ đặc trưng T1 cơ sở."
                )
            elif name == "Target":
                available_at = "post_outcome"
                timing = "Trạng thái cuối cùng/post-outcome."
                availability_source = (
                    f"{UCI_DATASET_SOURCE} Target là trạng thái cuối cùng trong bài toán phân loại."
                )
            else:
                raise ValueError(f"Chưa phân loại thời điểm cho thuộc tính: {name}")
            dtype = str(df[name].dtype)
            if name in CATEGORICAL_FIELDS:
                data_type = f"Danh mục/mã số ({dtype})"
            elif pd.api.types.is_integer_dtype(df[name]):
                data_type = f"Số nguyên ({dtype})"
            else:
                data_type = f"Số thực ({dtype})"
            writer.writerow(
                {
                    "data_label": "REAL (UCI-697)",
                    "attribute_name": name,
                    "data_type": data_type,
                    "meaning": meaning,
                    "group": group,
                    "availability_timing": timing,
                    "available_at": available_at,
                    "availability_source": availability_source,
                    "leakage_risk": risk,
                    "leakage_reason": reason,
                }
            )
    print(f"Generated {OUTPUT_PATH} with {len(df.columns)} source attributes.")


if __name__ == "__main__":
    main()
