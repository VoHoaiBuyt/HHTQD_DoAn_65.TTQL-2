"""Validate the SIMULATED curriculum graph and credit bounds."""

import csv
import sys
from collections import defaultdict
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
COURSES_PATH = ROOT / "data" / "simulated" / "courses.csv"
PREREQUISITES_PATH = ROOT / "data" / "simulated" / "prerequisites.csv"
RULES_PATH = ROOT / "src" / "config" / "credit_rules.yaml"
REPORT_PATH = ROOT / "reports" / "curriculum_validation.txt"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
VALID_OFFERING_VALUES = {"odd", "even", "both"}
VALID_PREREQUISITE_TYPES = {"tiên quyết", "học trước", "song hành"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def check(condition: bool, message: str, failures: list[str]) -> str:
    if condition:
        return f"PASS: {message}"
    failures.append(message)
    return f"FAIL: {message}"


def main() -> int:
    failures: list[str] = []
    results: list[str] = ["Curriculum validation — SIMULATED"]
    try:
        with RULES_PATH.open(encoding="utf-8") as file:
            rules = yaml.safe_load(file)
        courses = read_csv(COURSES_PATH)
        prerequisites = read_csv(PREREQUISITES_PATH)
    except (OSError, yaml.YAMLError, csv.Error) as error:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(f"FAIL: Không đọc được đầu vào: {error}\n", encoding="utf-8")
        print(f"Không đọc được đầu vào: {error}")
        return 1

    course_ids = [row["course_id"] for row in courses]
    course_by_id = {row["course_id"]: row for row in courses}
    semester_credits: dict[int, int] = defaultdict(int)
    for row in courses:
        try:
            semester = int(row["planned_semester"])
            credits = int(row["credits"])
            semester_credits[semester] += credits
        except ValueError:
            failures.append(f"Giá trị học kỳ/tín chỉ không hợp lệ ở {row.get('course_id')}")

    program_rules = rules["program"]
    expected_course_range = program_rules["expected_course_count"]
    results.append(
        check(
            len(course_ids) == len(set(course_ids)),
            "Mã học phần duy nhất.",
            failures,
        )
    )
    results.append(
        check(
            expected_course_range["min"] <= len(courses) <= expected_course_range["max"],
            f"Số học phần {len(courses)} nằm trong khoảng "
            f"{expected_course_range['min']}–{expected_course_range['max']}.",
            failures,
        )
    )
    expected_semesters = program_rules["expected_semester_count"]["value"]
    results.append(
        check(
            set(semester_credits) == set(range(1, expected_semesters + 1)),
            f"Có đủ học kỳ dự kiến 1–{expected_semesters}.",
            failures,
        )
    )
    results.append(
        check(
            all(row.get("source_label") == "SIMULATED" for row in courses),
            "Mọi học phần được gắn nhãn SIMULATED.",
            failures,
        )
    )

    missing_course_references = sorted(set(course_ids) - set(course_by_id))
    missing_prerequisites = [
        row for row in prerequisites if row["prerequisite_id"] not in course_by_id
    ]
    missing_dependent_courses = [
        row for row in prerequisites if row["course_id"] not in course_by_id
    ]
    results.append(
        check(
            not missing_prerequisites and not missing_dependent_courses,
            "Mọi course_id và prerequisite_id trong quan hệ tiên quyết đều tồn tại.",
            failures,
        )
    )
    if missing_prerequisites:
        failures.append(f"prerequisite_id không tồn tại: {missing_prerequisites}")
    if missing_dependent_courses:
        failures.append(f"course_id không tồn tại trong quan hệ tiên quyết: {missing_dependent_courses}")

    edges: dict[str, list[str]] = defaultdict(list)
    for row in prerequisites:
        course_id = row["course_id"]
        prerequisite_id = row["prerequisite_id"]
        if course_id in course_by_id and prerequisite_id in course_by_id:
            edges[course_id].append(prerequisite_id)

    visiting: set[str] = set()
    visited: set[str] = set()
    cycle_found = False

    def visit(course_id: str) -> None:
        nonlocal cycle_found
        if course_id in visiting:
            cycle_found = True
            return
        if course_id in visited:
            return
        visiting.add(course_id)
        for prerequisite_id in edges.get(course_id, []):
            visit(prerequisite_id)
        visiting.remove(course_id)
        visited.add(course_id)

    for course_id in course_ids:
        visit(course_id)
    results.append(
        check(not cycle_found, "Đồ thị tiên quyết là DAG, không có chu trình.", failures)
    )

    invalid_semester_order = []
    invalid_prerequisite_types = []
    for row in prerequisites:
        course_id = row["course_id"]
        prerequisite_id = row["prerequisite_id"]
        if course_id in course_by_id and prerequisite_id in course_by_id:
            course_semester = int(course_by_id[course_id]["planned_semester"])
            prerequisite_semester = int(
                course_by_id[prerequisite_id]["planned_semester"]
            )
            relation_type = row["type"]
            if (
                relation_type in {"tiên quyết", "học trước"}
                and course_semester <= prerequisite_semester
            ) or (
                relation_type == "song hành"
                and course_semester < prerequisite_semester
            ):
                invalid_semester_order.append(row)
        if row["type"] not in VALID_PREREQUISITE_TYPES:
            invalid_prerequisite_types.append(row)
    results.append(
        check(
            not invalid_semester_order,
            "Thứ tự học kỳ phù hợp loại quan hệ tiên quyết/học trước/song hành.",
            failures,
        )
    )
    if invalid_semester_order:
        failures.append(f"Quan hệ sai thứ tự học kỳ: {invalid_semester_order}")
    results.append(
        check(
            not invalid_prerequisite_types,
            "Loại quan hệ chỉ gồm 'tiên quyết', 'học trước' hoặc 'song hành'.",
            failures,
        )
    )
    if invalid_prerequisite_types:
        failures.append(f"Loại quan hệ không hợp lệ: {invalid_prerequisite_types}")

    invalid_offerings = []
    for row in courses:
        offerings = {value.strip() for value in row["offered_semesters"].split(",") if value.strip()}
        planned_semester = int(row["planned_semester"])
        planned_parity = "odd" if planned_semester % 2 else "even"
        opens_as_planned = "both" in offerings or planned_parity in offerings
        if not offerings or not offerings.issubset(VALID_OFFERING_VALUES) or not opens_as_planned:
            invalid_offerings.append(row["course_id"])
    results.append(
        check(
            not invalid_offerings,
            "Mỗi học phần có ít nhất một học kỳ mở, gồm học kỳ dự kiến.",
            failures,
        )
    )
    if invalid_offerings:
        failures.append(f"Học phần có lịch mở không hợp lệ: {invalid_offerings}")

    total_credits = sum(int(row["credits"]) for row in courses)
    total_rules = program_rules["expected_total_credits"]
    results.append(
        check(
            total_rules["min"] <= total_credits <= total_rules["max"],
            f"Tổng tín chỉ catalogue {total_credits} nằm trong khoảng "
            f"{total_rules['min']}–{total_rules['max']}.",
            failures,
        )
    )
    term_rules = rules["semester_credit_limits"]
    term_min = term_rules["minimum"]["value"]
    term_max = term_rules["maximum"]["value"]
    invalid_term_loads = {
        semester: credits
        for semester, credits in semester_credits.items()
        if not term_min <= credits <= term_max
    }
    results.append(
        check(
            not invalid_term_loads,
            f"Tín chỉ từng học kỳ nằm trong khoảng cấu hình {term_min}–{term_max}.",
            failures,
        )
    )
    results.append(
        "Tín chỉ theo học kỳ — SIMULATED: "
        + ", ".join(
            f"HK{semester}={semester_credits.get(semester, 0)}"
            for semester in range(1, expected_semesters + 1)
        )
    )

    if failures:
        results.append(f"KẾT LUẬN: FAIL ({len(failures)} vấn đề)")
        results.extend(f"- {failure}" for failure in failures)
    else:
        results.append(f"KẾT LUẬN: PASS ({total_credits} tín chỉ, {len(courses)} học phần)")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(results) + "\n", encoding="utf-8")
    print("\n".join(results))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
