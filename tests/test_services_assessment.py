from __future__ import annotations

import unittest

from src.services.assessment import (
    assess_student,
    build_plans,
    default_rules,
    load_bundle,
    load_curriculum,
    persona_payload,
)
from src.services.input_validation import (
    InputError,
    normalize_profile,
    normalize_progress_rows,
)

EXPECTED_ELIGIBLE = {
    "S001": 8,
    "S002": 8,
    "S003": 9,
    "S004": 6,
    "S005": 6,
    "S006": 1,
    "S007": 5,
    "S008": 0,
}


class AssessmentServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_bundle()
        cls.curriculum = load_curriculum()
        cls.rules = default_rules()

    def test_eligible_course_counts_match_fixture(self) -> None:
        for student_id, expected in EXPECTED_ELIGIBLE.items():
            profile, rows = persona_payload(self.curriculum, student_id)
            assessment = assess_student(
                profile,
                rows,
                self.curriculum,
                self.bundle,
                self.rules,
                use_ml=True,
            )
            self.assertEqual(
                len(assessment["rule_result"]["eligible_courses"]),
                expected,
                student_id,
            )
            self.assertGreaterEqual(assessment["p_dropout"], 0.0)
            self.assertLessEqual(assessment["p_dropout"], 1.0)

    def test_manual_mode_skips_ml_and_keeps_rules(self) -> None:
        profile, rows = persona_payload(self.curriculum, "S002")
        manual_profile = normalize_profile(
            {
                "student_id": "MANUAL-01",
                "current_semester": profile["current_semester"],
                "gpa": profile["gpa"],
                "cumulative_credits": profile["cumulative_credits"],
                "failed_courses_count": profile["failed_courses_count"],
                "hk1_enrolled": profile["Curricular units 1st sem (enrolled)"],
                "hk1_approved": profile["Curricular units 1st sem (approved)"],
                "hk1_grade": profile["Curricular units 1st sem (grade)"],
            }
        )
        manual_rows = [
            {**row, "student_id": "MANUAL-01"}
            for row in normalize_progress_rows(
                rows, known_course_ids=self.curriculum["course_by_id"].keys()
            )
        ]
        assessment = assess_student(
            manual_profile,
            manual_rows,
            self.curriculum,
            self.bundle,
            self.rules,
            use_ml=False,
        )
        self.assertIsNone(assessment["p_dropout"])
        self.assertEqual(assessment["risk_label"], "Chưa ước lượng")
        self.assertEqual(
            len(assessment["rule_result"]["eligible_courses"]),
            EXPECTED_ELIGIBLE["S002"],
        )
        self.assertIsNotNone(assessment["p_pass_m3_prime"])

    def test_plan_is_reproducible_for_s001(self) -> None:
        profile, rows = persona_payload(self.curriculum, "S001")
        assessment = assess_student(
            profile,
            rows,
            self.curriculum,
            self.bundle,
            self.rules,
            use_ml=True,
        )
        plans = build_plans(
            assessment,
            self.curriculum,
            self.bundle,
            self.rules,
            budgets=[12],
            load_lambda=0.0,
        )
        result = plans[0]["result"]
        self.assertEqual(result["status"], "optimal")
        self.assertEqual(result["selected_credits"], 12)
        self.assertAlmostEqual(result["expected_failed_courses"], 0.018, places=3)

    def test_s003_all_budgets_are_best_effort_not_safe(self) -> None:
        profile, rows = persona_payload(self.curriculum, "S003")
        assessment = assess_student(
            profile,
            rows,
            self.curriculum,
            self.bundle,
            self.rules,
            use_ml=True,
        )
        plans = build_plans(
            assessment,
            self.curriculum,
            self.bundle,
            self.rules,
            budgets=[12, 15, 18],
            load_lambda=0.1,
        )
        self.assertEqual([plan["budget"] for plan in plans], [12, 15, 18])
        for plan in plans:
            result = plan["result"]
            self.assertEqual(result["status"], "best_effort", plan["budget"])
            self.assertTrue(result["risk_cap_exceeded"])
            self.assertAlmostEqual(result["expected_failed_courses"], 2.98, places=2)
            self.assertEqual(result["expected_fail_cap"], 1.0)

    def test_comma_decimal_and_range_validation(self) -> None:
        profile = normalize_profile(
            {
                "student_id": "S999",
                "current_semester": "4",
                "gpa": "2,75",
                "cumulative_credits": "64",
                "failed_courses_count": "1",
                "hk1_enrolled": "7",
                "hk1_approved": "6",
                "hk1_grade": "12,5",
            }
        )
        self.assertAlmostEqual(profile["gpa"], 2.75)
        self.assertAlmostEqual(profile["hk1_grade"], 12.5)

        with self.assertRaises(InputError):
            normalize_profile(
                {
                    "student_id": "S999",
                    "current_semester": 9,
                    "gpa": 3.0,
                    "cumulative_credits": 64,
                    "failed_courses_count": 0,
                    "hk1_enrolled": 7,
                    "hk1_approved": 6,
                    "hk1_grade": 12.0,
                }
            )
        with self.assertRaises(InputError):
            normalize_profile(
                {
                    "student_id": "S999",
                    "current_semester": 4,
                    "gpa": 3.0,
                    "cumulative_credits": 64,
                    "failed_courses_count": 0,
                    "hk1_enrolled": 5,
                    "hk1_approved": 6,
                    "hk1_grade": 12.0,
                }
            )

    def test_raw_uci_profile_template_is_accepted(self) -> None:
        raw_row = {
            "student_id": "UCI-ROW",
            "current_semester": 4,
            "gpa": 3.1,
            "cumulative_credits": 64,
            "failed_courses_count": 1,
            "Curricular units 1st sem (enrolled)": 7,
            "Curricular units 1st sem (approved)": 6,
            "Curricular units 1st sem (grade)": 13.5,
        }
        profile = normalize_profile(raw_row)
        self.assertEqual(profile["hk1_enrolled"], 7)
        self.assertEqual(profile["hk1_approved"], 6)
        self.assertAlmostEqual(profile["hk1_grade"], 13.5)

    def test_progress_rows_from_another_student_are_rejected(self) -> None:
        profile, rows = persona_payload(self.curriculum, "S001")
        foreign_rows = [{**row, "student_id": "S002"} for row in rows]
        with self.assertRaises(InputError):
            assess_student(
                profile,
                foreign_rows,
                self.curriculum,
                self.bundle,
                self.rules,
                use_ml=False,
            )

    def test_progress_validation_rejects_unknown_and_duplicate(self) -> None:
        with self.assertRaises(InputError):
            normalize_progress_rows(
                [{"course_id": "KHONG-CO", "status": "completed"}],
                known_course_ids=self.curriculum["course_by_id"].keys(),
            )
        with self.assertRaises(InputError):
            normalize_progress_rows(
                [
                    {"course_id": "IT101", "status": "completed"},
                    {"course_id": "IT101", "status": "failed"},
                ],
                known_course_ids=self.curriculum["course_by_id"].keys(),
            )


if __name__ == "__main__":
    unittest.main()
