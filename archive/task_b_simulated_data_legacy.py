"""
Task B: Tạo dữ liệu mô phỏng chương trình đào tạo CNTT
Tất cả dữ liệu gắn nhãn SIMULATED - không phải CTĐT chính thức NTU
"""
import sys, csv, pathlib
sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(r"e:\HHTQD_DoAn")
SIM  = ROOT / "data" / "simulated"
SIM.mkdir(parents=True, exist_ok=True)

# =========================================================
# 1. COURSES.CSV
# =========================================================
# Dựa trên khung chương trình CNTT phổ biến tại VN
# Nguồn: suy luận từ các CTĐT CNTT ĐH VN - SIMULATED
courses = [
    # (course_id, course_name, credits, expected_semester, course_type, offered_semesters)
    ("MATH101", "Giải tích 1",                 4, 1, "required", "1,2"),
    ("MATH102", "Đại số tuyến tính",           3, 1, "required", "1,2"),
    ("IT101",   "Nhập môn lập trình (C/C++)",  3, 1, "required", "1,2"),
    ("IT102",   "Toán rời rạc",                3, 2, "required", "1,2"),
    ("MATH103", "Giải tích 2",                 3, 2, "required", "1,2"),
    ("IT103",   "Lập trình hướng đối tượng",   3, 2, "required", "1,2"),
    ("IT104",   "Cấu trúc dữ liệu và giải thuật", 4, 3, "required", "1,2"),
    ("IT105",   "Kiến trúc máy tính",          3, 3, "required", "1,2"),
    ("IT106",   "Cơ sở dữ liệu",               4, 3, "required", "1,2"),
    ("IT107",   "Mạng máy tính",               3, 4, "required", "1,2"),
    ("IT108",   "Hệ điều hành",                3, 4, "required", "1,2"),
    ("IT109",   "Lập trình web",               3, 4, "required", "1,2"),
    ("IT201",   "Trí tuệ nhân tạo",            3, 5, "required", "1,2"),
    ("IT202",   "Học máy",                     3, 5, "elective", "1,2"),
    ("IT203",   "Phát triển phần mềm",         4, 5, "required", "1,2"),
    ("IT204",   "An toàn thông tin",           3, 6, "required", "1,2"),
    ("IT205",   "Khai phá dữ liệu",            3, 6, "elective", "2"),
    ("IT206",   "Hệ hỗ trợ ra quyết định",     3, 6, "elective", "1,2"),
    ("IT301",   "Thực tập tốt nghiệp",         4, 7, "required", "1,2"),
    ("IT302",   "Đồ án tốt nghiệp",            9, 8, "required", "1,2"),
]

with open(SIM / "courses.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["course_id","course_name","credits","expected_semester","course_type","offered_semesters","source"])
    for row in courses:
        w.writerow(list(row) + ["SIMULATED"])

print(f"[OK] courses.csv — {len(courses)} học phần")

# =========================================================
# 2. PREREQUISITES.CSV
# =========================================================
prerequisites = [
    ("MATH102", "MATH101"),   # Đại số → Giải tích 1
    ("MATH103", "MATH101"),   # Giải tích 2 → Giải tích 1
    ("IT102",   "IT101"),     # Toán rời rạc → Nhập môn LP
    ("IT103",   "IT101"),     # OOP → Nhập môn LP
    ("IT104",   "IT103"),     # CTDL → OOP
    ("IT104",   "IT102"),     # CTDL → Toán rời rạc
    ("IT105",   "IT101"),     # Kiến trúc MT → Nhập môn LP
    ("IT106",   "IT104"),     # CSDL → CTDL
    ("IT107",   "IT105"),     # Mạng → Kiến trúc MT
    ("IT108",   "IT105"),     # HĐH → Kiến trúc MT
    ("IT109",   "IT103"),     # Web → OOP
    ("IT109",   "IT106"),     # Web → CSDL
    ("IT201",   "MATH102"),   # AI → Đại số TT
    ("IT201",   "IT104"),     # AI → CTDL
    ("IT202",   "IT201"),     # ML → AI
    ("IT202",   "MATH103"),   # ML → Giải tích 2
    ("IT203",   "IT106"),     # Phát triển PM → CSDL
    ("IT203",   "IT109"),     # Phát triển PM → Web
    ("IT204",   "IT107"),     # ATTT → Mạng
    ("IT205",   "IT202"),     # Khai phá DL → ML
    ("IT205",   "IT106"),     # Khai phá DL → CSDL
    ("IT206",   "IT201"),     # HHTQD → AI
    ("IT206",   "IT202"),     # HHTQD → ML
    ("IT301",   "IT203"),     # Thực tập → Phát triển PM
    ("IT302",   "IT301"),     # Đồ án → Thực tập
]

with open(SIM / "prerequisites.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["course_id","prerequisite_id","source"])
    for row in prerequisites:
        w.writerow(list(row) + ["SIMULATED"])

print(f"[OK] prerequisites.csv — {len(prerequisites)} ràng buộc tiên quyết")

# =========================================================
# 3. STUDENT_PROGRESS_TEMPLATE.CSV
# =========================================================
# Mô phỏng 5 sinh viên với các tiến độ khác nhau
import random
random.seed(42)

statuses = ["completed", "in_progress", "failed", "pending"]
progress_rows = []
student_scenarios = {
    "SV001": {"label": "on_track",    "completed_sems": [1,2,3,4], "current_sem": 5},
    "SV002": {"label": "at_risk",     "completed_sems": [1,2,3],   "current_sem": 4, "failed": ["IT106"]},
    "SV003": {"label": "high_risk",   "completed_sems": [1,2],     "current_sem": 3, "failed": ["IT103","IT102"]},
    "SV004": {"label": "dropout_risk","completed_sems": [1],       "current_sem": 2, "failed": ["IT101","MATH102"]},
    "SV005": {"label": "excellent",   "completed_sems": [1,2,3,4,5],"current_sem": 6},
}

for sv_id, scenario in student_scenarios.items():
    for cid, cname, credits, exp_sem, ctype, offered, _ in [list(r) + ["SIMULATED"] for r in courses]:
        if exp_sem in scenario["completed_sems"]:
            if cid in scenario.get("failed", []):
                grade = round(random.uniform(2.5, 4.9), 1)
                status = "failed"
            else:
                grade = round(random.uniform(5.5, 10.0), 1)
                status = "completed"
        elif exp_sem == scenario["current_sem"]:
            grade = None
            status = "in_progress"
        else:
            grade = None
            status = "pending"
        progress_rows.append([sv_id, scenario["label"], cid, status, grade if grade else "", "SIMULATED"])

with open(SIM / "student_progress_template.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["student_id","risk_label","course_id","status","grade","source"])
    for row in progress_rows:
        w.writerow(row)

print(f"[OK] student_progress_template.csv — {len(progress_rows)} dòng ({len(student_scenarios)} sinh viên)")

# =========================================================
# 4. STUDENT_PROFILE_TEMPLATE.CSV
# =========================================================
# Mapping từ UCI-697 feature space → sinh viên mô phỏng
profiles = [
    # student_id, risk_label, age_at_enroll, gender, marital_status,
    #   scholarship, debtor, tuition_up_to_date, displaced,
    #   prev_qualification_grade, admission_grade,
    #   cu1_enrolled, cu1_approved, cu1_grade,
    #   cu2_enrolled, cu2_approved, cu2_grade,  <-- available only at T2
    #   gdp, unemployment_rate, inflation_rate
    ("SV001","on_track",     19,"Male",  "Single",0,0,1,0,140.0,130.0,6,6,13.5,6,6,14.0,1.74,10.8,1.4),
    ("SV002","at_risk",      21,"Female","Single",0,0,1,0,120.0,118.0,6,4,10.2,6,3,9.1, 1.74,10.8,1.4),
    ("SV003","high_risk",    22,"Male",  "Single",0,1,0,1,110.0,105.0,5,2, 7.5,5,1,6.3, 1.74,13.9,2.1),
    ("SV004","dropout_risk", 25,"Male",  "Married",0,1,0,1,100.0, 95.0,4,1, 5.0,0,0,0.0, 1.74,13.9,2.1),
    ("SV005","excellent",    18,"Female","Single",1,0,1,0,160.0,155.0,6,6,16.0,6,6,17.0, 2.50, 7.6,0.3),
]

profile_header = [
    "student_id","risk_label","age_at_enrollment","gender","marital_status",
    "scholarship_holder","debtor","tuition_fees_up_to_date","displaced",
    "previous_qualification_grade","admission_grade",
    "cu1_sem_enrolled","cu1_sem_approved","cu1_sem_grade",
    "cu2_sem_enrolled","cu2_sem_approved","cu2_sem_grade",
    "gdp","unemployment_rate","inflation_rate","source"
]

with open(SIM / "student_profile_template.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(profile_header)
    for row in profiles:
        w.writerow(list(row) + ["SIMULATED"])

print(f"[OK] student_profile_template.csv — {len(profiles)} hồ sơ sinh viên mô phỏng")
print("\n[DONE] Task B — dữ liệu mô phỏng đã tạo xong tại data/simulated/")

