"""Generate clearly labeled curriculum and persona fixtures for Stage 1."""

import csv
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "simulated"
SEED = 20261105

COURSES = [
    ("IT101", "Toán rời rạc I", 3, 1, "bắt buộc", "Cơ sở toán học"),
    ("IT102", "Đại số tuyến tính", 3, 1, "bắt buộc", "Cơ sở toán học"),
    ("IT103", "Nhập môn công nghệ thông tin", 3, 1, "bắt buộc", "Đại cương"),
    ("IT104", "Kỹ năng học tập đại học", 3, 1, "bắt buộc", "Đại cương"),
    ("IT105", "Tiếng Anh cơ bản", 2, 1, "bắt buộc", "Đại cương"),
    ("EL106", "Tự chọn đại cương kỳ 1 (placeholder)", 2, 1, "tự chọn", "Tự chọn đại cương 1"),
    ("IT201", "Lập trình cơ bản", 3, 2, "bắt buộc", "Lập trình"),
    ("IT202", "Toán rời rạc II", 3, 2, "bắt buộc", "Cơ sở toán học"),
    ("IT203", "Cấu trúc dữ liệu", 3, 3, "bắt buộc", "Lập trình"),
    ("IT204", "Kiến trúc máy tính", 3, 2, "bắt buộc", "Hệ thống"),
    ("IT205", "Xác suất thống kê", 2, 2, "bắt buộc", "Cơ sở toán học"),
    ("EL206", "Tự chọn cơ sở kỳ 2 (placeholder)", 2, 2, "tự chọn", "Tự chọn cơ sở 1"),
    ("IT301", "Lập trình hướng đối tượng", 3, 3, "bắt buộc", "Lập trình"),
    ("IT302", "Cơ sở dữ liệu", 3, 3, "bắt buộc", "Dữ liệu"),
    ("IT303", "Mạng máy tính", 3, 3, "bắt buộc", "Hệ thống"),
    ("IT304", "Giải thuật và cấu trúc dữ liệu nâng cao", 3, 4, "bắt buộc", "Lập trình"),
    ("IT305", "Hệ điều hành", 2, 3, "bắt buộc", "Hệ thống"),
    ("EL306", "Tự chọn cơ sở kỳ 2 (placeholder)", 2, 2, "tự chọn", "Tự chọn cơ sở 2"),
    ("IT401", "Công nghệ phần mềm", 3, 4, "bắt buộc", "Kỹ nghệ phần mềm"),
    ("IT402", "Phát triển ứng dụng web", 3, 4, "bắt buộc", "Phát triển ứng dụng"),
    ("IT403", "Phân tích và thiết kế hệ thống", 3, 4, "bắt buộc", "Kỹ nghệ phần mềm"),
    ("IT404", "Nhập môn trí tuệ nhân tạo", 3, 4, "bắt buộc", "Trí tuệ nhân tạo"),
    ("IT405", "An toàn thông tin", 2, 4, "bắt buộc", "An toàn thông tin"),
    ("EL406", "Tự chọn cơ sở kỳ 3 (placeholder)", 2, 3, "tự chọn", "Tự chọn cơ sở 3"),
    ("IT501", "Thiết kế phần mềm", 3, 5, "bắt buộc", "Kỹ nghệ phần mềm"),
    ("IT502", "Kho dữ liệu", 3, 5, "bắt buộc", "Dữ liệu"),
    ("IT503", "Điện toán đám mây và DevOps", 3, 5, "bắt buộc", "Hệ thống"),
    ("IT504", "Lập trình an toàn", 3, 5, "bắt buộc", "An toàn thông tin"),
    ("IT505", "Thiết kế giao diện người dùng", 2, 5, "bắt buộc", "Phát triển ứng dụng"),
    ("EL506", "Tự chọn chuyên ngành kỳ 5 (placeholder)", 2, 5, "tự chọn", "Tự chọn chuyên ngành 1"),
    ("IT601", "Kiểm thử phần mềm", 3, 6, "bắt buộc", "Kỹ nghệ phần mềm"),
    ("IT602", "Phát triển ứng dụng di động", 3, 6, "bắt buộc", "Phát triển ứng dụng"),
    ("IT603", "Khai phá dữ liệu", 3, 6, "bắt buộc", "Dữ liệu"),
    ("IT604", "An ninh mạng", 3, 6, "bắt buộc", "An toàn thông tin"),
    ("IT605", "Phân tích hệ thống thông tin", 2, 6, "bắt buộc", "Kỹ nghệ phần mềm"),
    ("EL606", "Tự chọn chuyên ngành kỳ 6 (placeholder)", 2, 6, "tự chọn", "Tự chọn chuyên ngành 2"),
    ("IT701", "Đồ án chuẩn bị tốt nghiệp", 3, 7, "bắt buộc", "Đồ án"),
    ("IT702", "Học máy ứng dụng", 3, 7, "bắt buộc", "Trí tuệ nhân tạo"),
    ("IT703", "Hệ thống thông tin doanh nghiệp", 3, 7, "bắt buộc", "Hệ thống thông tin"),
    ("IT704", "Kiến trúc giải pháp đám mây", 3, 7, "bắt buộc", "Hệ thống"),
    ("IT705", "Chuẩn bị thực tập", 2, 7, "bắt buộc", "Thực tập"),
    ("EL706", "Tự chọn chuyên ngành kỳ 7 (placeholder)", 2, 7, "tự chọn", "Tự chọn chuyên ngành 3"),
    ("IT801", "Thực tập doanh nghiệp", 3, 8, "bắt buộc", "Thực tập"),
    ("IT802", "Đồ án tốt nghiệp", 3, 8, "bắt buộc", "Đồ án"),
    ("IT803", "Quản lý dự án công nghệ thông tin", 3, 8, "bắt buộc", "Quản lý"),
    ("IT804", "Chuyên đề trí tuệ nhân tạo và dữ liệu", 3, 8, "bắt buộc", "Trí tuệ nhân tạo"),
    ("IT805", "Seminar công nghệ thông tin", 2, 8, "bắt buộc", "Đại cương"),
    ("EL806", "Tự chọn chuyên ngành kỳ 8 (placeholder)", 2, 8, "tự chọn", "Tự chọn chuyên ngành 4"),
]

PREREQUISITES = [
    ("IT201", "IT103", "tiên quyết"),
    ("IT202", "IT101", "tiên quyết"),
    ("IT203", "IT201", "tiên quyết"),
    ("IT203", "IT202", "tiên quyết"),
    ("IT204", "IT103", "tiên quyết"),
    ("IT205", "IT102", "tiên quyết"),
    ("IT301", "IT201", "tiên quyết"),
    ("IT302", "IT201", "tiên quyết"),
    ("IT303", "IT204", "tiên quyết"),
    ("IT304", "IT203", "tiên quyết"),
    ("IT305", "IT204", "tiên quyết"),
    ("IT401", "IT301", "tiên quyết"),
    ("IT401", "IT202", "tiên quyết"),
    ("IT402", "IT301", "tiên quyết"),
    ("IT402", "IT302", "tiên quyết"),
    ("IT403", "IT302", "tiên quyết"),
    ("IT404", "IT205", "tiên quyết"),
    ("IT405", "IT303", "tiên quyết"),
    ("IT501", "IT401", "tiên quyết"),
    ("IT502", "IT302", "tiên quyết"),
    ("IT503", "IT305", "tiên quyết"),
    ("IT503", "IT303", "tiên quyết"),
    ("IT504", "IT405", "tiên quyết"),
    ("IT505", "IT402", "tiên quyết"),
    ("IT601", "IT501", "tiên quyết"),
    ("IT602", "IT402", "tiên quyết"),
    ("IT603", "IT404", "tiên quyết"),
    ("IT604", "IT405", "tiên quyết"),
    ("IT605", "IT403", "tiên quyết"),
    ("IT701", "IT601", "tiên quyết"),
    ("IT701", "IT605", "tiên quyết"),
    ("IT702", "IT603", "tiên quyết"),
    ("IT703", "IT501", "tiên quyết"),
    ("IT704", "IT503", "tiên quyết"),
    ("IT705", "IT401", "học trước"),
    ("IT801", "IT701", "tiên quyết"),
    ("IT802", "IT701", "tiên quyết"),
    ("IT803", "IT605", "tiên quyết"),
    ("IT804", "IT702", "tiên quyết"),
    ("IT805", "IT701", "học trước"),
]

PERSONAS = [
    {
        "student_id": "S001",
        "persona": "Giỏi, đúng tiến độ",
        "persona_purpose": "Kiểm thử lộ trình đạt tốt, tải học tập ổn định.",
        "feature_tier": "Cao",
        "current_semester": 4,
        "grade_level": 8.6,
        "failed": {},
        "age": 20,
    },
    {
        "student_id": "S002",
        "persona": "Trung bình, đúng tiến độ",
        "persona_purpose": "Kiểm thử đề xuất cân bằng cho kết quả trung bình.",
        "feature_tier": "Trung bình",
        "current_semester": 4,
        "grade_level": 6.8,
        "failed": {},
        "age": 19,
    },
    {
        "student_id": "S003",
        "persona": "Yếu, chậm tiến độ",
        "persona_purpose": "Kiểm thử giảm tải và ưu tiên học lại học phần chưa đạt.",
        "feature_tier": "Thấp",
        "current_semester": 4,
        "grade_level": 5.7,
        "failed": {"IT104": 4.4},
        "age": 21,
    },
    {
        "student_id": "S004",
        "persona": "Có nhiều môn nợ",
        "persona_purpose": "Kiểm thử nhiều học phần chưa đạt và tác động lên tín chỉ còn thiếu.",
        "feature_tier": "Thấp",
        "current_semester": 4,
        "grade_level": 5.5,
        "failed": {"IT104": 4.2, "IT202": 4.5, "IT302": 4.7},
        "age": 22,
    },
    {
        "student_id": "S005",
        "persona": "Nợ môn chặn chuỗi tiên quyết",
        "persona_purpose": "Kiểm thử học lại IT202 trước các học phần phụ thuộc IT203/IT304.",
        "feature_tier": "Trung bình",
        "current_semester": 4,
        "grade_level": 6.0,
        "failed": {"IT202": 4.3},
        "age": 21,
    },
    {
        "student_id": "S006",
        "persona": "Gần tốt nghiệp, còn một môn nợ",
        "persona_purpose": "Kiểm thử lập kế hoạch hoàn tất số tín chỉ cuối và học phần nợ.",
        "feature_tier": "Trung bình",
        "current_semester": 8,
        "grade_level": 7.3,
        "failed": {"EL706": 4.8},
        "age": 23,
    },
    {
        "student_id": "S007",
        "persona": "Nguy cơ chậm do trượt môn nền tảng",
        "persona_purpose": "Kiểm thử học phần nền tảng chưa đạt chặn học phần lập trình kế tiếp.",
        "feature_tier": "Thấp",
        "current_semester": 3,
        "grade_level": 5.8,
        "failed": {"IT201": 4.6},
        "age": 20,
    },
    {
        "student_id": "S008",
        "persona": "Giỏi, tích lũy gần hoàn tất",
        "persona_purpose": "Kiểm thử sinh viên tiến độ tốt ở kỳ cuối.",
        "feature_tier": "Cao",
        "current_semester": 8,
        "grade_level": 9.0,
        "failed": {},
        "age": 23,
    },
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def real_feature_templates() -> dict[str, tuple[dict[str, float], str]]:
    data = pd.read_csv(ROOT / "data" / "raw" / "uci_697" / "data.csv", sep=";")
    data.columns = data.columns.str.strip()
    with (ROOT / "reports" / "data_dictionary.csv").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        feature_names = [
            row["attribute_name"]
            for row in csv.DictReader(file)
            if row["available_at"] in {"T0", "T1_known"}
        ]

    enrollment = data["Curricular units 1st sem (enrolled)"].to_numpy(dtype=float)
    approved = data["Curricular units 1st sem (approved)"].to_numpy(dtype=float)
    approval_rate = np.divide(
        approved,
        enrollment,
        out=np.zeros(len(data), dtype=float),
        where=enrollment > 0,
    )
    cut_points = np.quantile(approval_rate, [1 / 3, 2 / 3])
    tiers = pd.cut(
        approval_rate,
        bins=[-np.inf, cut_points[0], cut_points[1], np.inf],
        labels=["Thấp", "Trung bình", "Cao"],
        include_lowest=True,
        right=False,
    )

    templates: dict[str, tuple[dict[str, float], str]] = {}
    for tier in ["Thấp", "Trung bình", "Cao"]:
        subset = data.loc[np.asarray(tiers == tier), feature_names]
        if subset.empty:
            raise ValueError(f"Không có hồ sơ REAL trong tầng HK1 {tier}")
        center = subset.median()
        scale = subset.std().replace(0, 1).fillna(1)
        distance = (((subset - center) / scale) ** 2).sum(axis=1)
        row_index = int(distance.idxmin())
        representative = data.loc[row_index, feature_names].astype(float).to_dict()
        rate = (
            representative["Curricular units 1st sem (approved)"]
            / max(representative["Curricular units 1st sem (enrolled)"], 1)
        )
        observed_tier = (
            "Thấp" if rate < cut_points[0]
            else "Trung bình" if rate < cut_points[1]
            else "Cao"
        )
        if observed_tier != tier:
            raise ValueError(
                f"Vector đại diện {tier} rơi vào tầng {observed_tier}; "
                "không thể gán nhãn persona đúng."
            )
        templates[tier] = (
            representative,
            f"REAL (UCI-697) medoid, data-row={row_index + 2}, tier={tier}",
        )
    return templates


def make_curriculum() -> None:
    course_rows = [
        {
            "course_id": course_id,
            "course_name": course_name,
            "credits": credits,
            "planned_semester": semester,
            "course_type": course_type,
            "offered_semesters": "odd" if semester % 2 else "even",
            "group": group,
            "source_label": "SIMULATED",
        }
        for course_id, course_name, credits, semester, course_type, group in COURSES
    ]
    prerequisite_rows = [
        {
            "course_id": course_id,
            "prerequisite_id": prerequisite_id,
            "type": prerequisite_type,
            "source_label": "SIMULATED",
        }
        for course_id, prerequisite_id, prerequisite_type in PREREQUISITES
    ]
    write_csv(
        OUTPUT_DIR / "courses.csv",
        [
            "course_id",
            "course_name",
            "credits",
            "planned_semester",
            "course_type",
            "offered_semesters",
            "group",
            "source_label",
        ],
        course_rows,
    )
    write_csv(
        OUTPUT_DIR / "prerequisites.csv",
        ["course_id", "prerequisite_id", "type", "source_label"],
        prerequisite_rows,
    )


def make_student_fixtures() -> None:
    rng = random.Random(SEED)
    course_by_id = {course[0]: course for course in COURSES}
    prereqs_by_course: dict[str, list[str]] = {}
    for course_id, prerequisite_id, _ in PREREQUISITES:
        prereqs_by_course.setdefault(course_id, []).append(prerequisite_id)

    progress_rows = []
    profile_rows = []
    feature_templates = real_feature_templates()
    for persona in PERSONAS:
        status_by_course: dict[str, str] = {}
        course_grade: dict[str, float] = {}

        for course_id, course_name, credits, semester, _, _ in COURSES:
            prereqs_passed = all(
                status_by_course.get(prerequisite_id) == "completed"
                for prerequisite_id in prereqs_by_course.get(course_id, [])
            )
            planned_failure = course_id in persona["failed"]

            if semester > persona["current_semester"]:
                status = "not_taken"
            elif not prereqs_passed:
                status = "not_taken"
            elif planned_failure:
                status = "failed"
            else:
                status = "completed"

            status_by_course[course_id] = status
            grade = ""
            if status == "completed":
                grade = round(
                    max(5.5, min(9.8, persona["grade_level"] + rng.uniform(-0.7, 0.7))),
                    1,
                )
                course_grade[course_id] = grade
            elif status == "failed":
                grade = float(persona["failed"][course_id])
                course_grade[course_id] = grade

            progress_rows.append(
                {
                    "student_id": persona["student_id"],
                    "course_id": course_id,
                    "status": status,
                    "grade_10": grade,
                    "attempt_count": (
                        2 if status == "failed"
                        else 1 if status in {"completed", "in_progress"} else 0
                    ),
                    "semester_taken": (
                        semester if status in {"completed", "failed"} else
                        persona["current_semester"] if status == "in_progress" else ""
                    ),
                    "source_label": "SIMULATED",
                }
            )

        completed_credits = sum(
            course_by_id[course_id][2]
            for course_id, status in status_by_course.items()
            if status == "completed"
        )
        attempted_grades = [
            grade for course_id, grade in course_grade.items()
            if status_by_course[course_id] in {"completed", "failed"}
        ]
        gpa = round((sum(attempted_grades) / len(attempted_grades)) * 0.4, 2) if attempted_grades else ""
        profile_features, template_source = feature_templates[persona["feature_tier"]]
        profile_rows.append(
            {
                "student_id": persona["student_id"],
                "persona": persona["persona"],
                "persona_purpose": persona["persona_purpose"],
                "current_semester": persona["current_semester"],
                "cumulative_credits": completed_credits,
                "credits_remaining": sum(course[2] for course in COURSES) - completed_credits,
                "gpa": gpa,
                "failed_courses_count": sum(
                    status == "failed" for status in status_by_course.values()
                ),
                "feature_template_source": template_source,
                **profile_features,
                "feature_source_label": "REAL-derived; persona SIMULATED",
                "source_label": "SIMULATED",
            }
        )

    write_csv(
        OUTPUT_DIR / "student_progress.csv",
        [
            "student_id",
            "course_id",
            "status",
            "grade_10",
            "attempt_count",
            "semester_taken",
            "source_label",
        ],
        progress_rows,
    )
    write_csv(
        OUTPUT_DIR / "student_profile.csv",
        [
            "student_id",
            "persona",
            "persona_purpose",
            "current_semester",
            "cumulative_credits",
            "credits_remaining",
            "gpa",
            "failed_courses_count",
            "feature_template_source",
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
            "Curricular units 1st sem (credited)",
            "Curricular units 1st sem (enrolled)",
            "Curricular units 1st sem (evaluations)",
            "Curricular units 1st sem (approved)",
            "Curricular units 1st sem (grade)",
            "Curricular units 1st sem (without evaluations)",
            "feature_source_label",
            "source_label",
        ],
        profile_rows,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    make_curriculum()
    make_student_fixtures()
    print(f"Generated SIMULATED curriculum and student fixtures in {OUTPUT_DIR}")
    print(f"Fixed random seed: {SEED}")


if __name__ == "__main__":
    main()
