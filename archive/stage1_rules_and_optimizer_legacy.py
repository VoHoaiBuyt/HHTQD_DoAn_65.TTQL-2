import csv
import unittest
from pathlib import Path

from src.optimize.ilp_prototype import solve_plan
from src.rules.rule_engine import evaluate_student, load_rules


ROOT = Path(__file__).resolve().parents[1]


def read_csv(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


class RuleEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = load_rules()
        cls.courses = read_csv("data/processed/courses.csv")
        cls.prerequisites = read_csv("data/processed/prerequisites.csv")
        cls.progress = read_csv("data/processed/student_progress.csv")
        cls.profiles = {
            row["student_id"]: row
            for row in read_csv("data/processed/student_profile.csv")
        }

    def student_progress(self, student_id: str) -> list[dict[str, str]]:
        return [
            row for row in self.progress if row["student_id"] == student_id
        ]

    def test_all_outputs_remain_separate_and_study_ahead_is_allowed(self) -> None:
        courses = [
            {
                "course_id": "BASE",
                "course_name": "Môn nền",
                "credits": "3",
                "planned_semester": "1",
                "course_type": "bắt buộc",
                "offered_semesters": "odd",
            },
            {
                "course_id": "AHEAD",
                "course_name": "Môn học vượt",
                "credits": "3",
                "planned_semester": "5",
                "course_type": "bắt buộc",
                "offered_semesters": "odd",
            },
        ]
        result = evaluate_student(
            self.profiles["S001"],
            courses,
            [
                {
                    "course_id": "AHEAD",
                    "prerequisite_id": "BASE",
                    "type": "tiên quyết",
                }
            ],
            [{"course_id": "BASE", "status": "completed", "attempt_count": 1}],
            next_semester=3,
            p_dropout=0.1,
            rules=self.rules,
        )
        self.assertIn("academic_flags", result)
        self.assertIn("eligible_courses", result)
        self.assertIn("progress_stats", result)
        self.assertTrue(
            any(
                row["course_id"] == "AHEAD"
                for row in result["eligible_courses"]
            )
        )

    def test_unmet_strict_prerequisite_excludes_course(self) -> None:
        result = evaluate_student(
            self.profiles["S005"],
            self.courses,
            self.prerequisites,
            self.student_progress("S005"),
            next_semester=5,
            p_dropout=0.2,
            rules=self.rules,
        )
        eligible_ids = {row["course_id"] for row in result["eligible_courses"]}
        self.assertNotIn("HP029", eligible_ids)
        blocked_flags = [
            flag
            for flag in result["edge_case_flags"]
            if flag["code"] == "REQUIRED_COURSE_BLOCKED"
        ]
        self.assertTrue(blocked_flags)
        self.assertIn("HP029", blocked_flags[0]["message"])

    def test_concurrent_peer_without_eligibility_excludes_course(self) -> None:
        courses = [
            {
                "course_id": "A",
                "course_name": "Môn song hành A",
                "credits": "3",
                "planned_semester": "1",
                "course_type": "bắt buộc",
                "offered_semesters": "odd",
            },
            {
                "course_id": "B",
                "course_name": "Môn song hành B",
                "credits": "3",
                "planned_semester": "1",
                "course_type": "bắt buộc",
                "offered_semesters": "odd",
            },
            {
                "course_id": "C",
                "course_name": "Môn tiên quyết C",
                "credits": "3",
                "planned_semester": "1",
                "course_type": "bắt buộc",
                "offered_semesters": "odd",
            },
        ]
        result = evaluate_student(
            self.profiles["S001"],
            courses,
            [
                {"course_id": "A", "prerequisite_id": "B", "type": "song hành"},
                {"course_id": "B", "prerequisite_id": "C", "type": "tiên quyết"},
            ],
            [],
            next_semester=3,
            p_dropout=0.1,
            rules=self.rules,
        )
        eligible_ids = {row["course_id"] for row in result["eligible_courses"]}
        self.assertNotIn("A", eligible_ids)
        self.assertNotIn("B", eligible_ids)

    def test_graduation_and_no_eligible_course_edges_are_reported(self) -> None:
        graduation_courses = [
            {
                "course_id": "DEGREE",
                "credits": "130",
                "planned_semester": "8",
                "course_type": "bắt buộc",
                "offered_semesters": "even",
            }
        ]
        graduated = evaluate_student(
            self.profiles["S008"],
            graduation_courses,
            [],
            [{"course_id": "DEGREE", "status": "completed", "attempt_count": 1}],
            next_semester=9,
            p_dropout=0.05,
            rules=self.rules,
        )
        self.assertTrue(
            any(
                flag["code"] == "GRADUATION_CREDITS_MET"
                for flag in graduated["edge_case_flags"]
            )
        )

        no_courses = evaluate_student(
            self.profiles["S006"],
            [],
            [],
            self.student_progress("S006"),
            next_semester=9,
            p_dropout=0.2,
            rules=self.rules,
        )
        self.assertTrue(
            any(
                flag["code"] == "NO_ELIGIBLE_COURSES"
                for flag in no_courses["edge_case_flags"]
            )
        )

    def test_warning_tier_does_not_hard_lock_load_by_default(self) -> None:
        result = evaluate_student(
            self.profiles["S002"],
            self.courses,
            self.prerequisites,
            self.student_progress("S002"),
            next_semester=5,
            p_dropout=0.32,
            p_dropout_calibrated=0.32,
            rules=self.rules,
        )

        self.assertEqual(result["risk_tier"], "high")
        self.assertFalse(result["load_restriction_recommended"])
        self.assertFalse(result["enforce_cap"])
        self.assertEqual(result["credit_cap"], 19)
        self.assertEqual(result["recommended_credit_cap"], 12)


class OptimizerPrototypeTests(unittest.TestCase):
    def test_terminal_statuses_are_explicit(self) -> None:
        common = {
            "p_student_m3_prime": 0.5,
            "load_lambda": 0.0,
            "risk_tier": "prototype",
            "scenario_credit_max": 12,
            "expected_fail_cap": 1.0,
            "average_credits_per_unit": 3.0,
            "median_real_load_units": 2,
            "unlock_values": {},
            "beta": 0.125,
            "gamma": 1.0,
            "minimum_credits": 12,
            "relaxed_minimum_credits": 6,
        }
        no_courses = solve_plan([], **common)
        graduated = solve_plan([], graduation_ready=True, **common)

        self.assertEqual(no_courses["status"], "no_eligible_courses")
        self.assertEqual(graduated["status"], "graduation_ready")

    def test_unlock_value_and_failure_cap_change_solution(self) -> None:
        courses = [
            {"course_id": "A", "credits": 3, "status": "not_taken"},
            {"course_id": "B", "credits": 3, "status": "not_taken"},
            {"course_id": "C", "credits": 3, "status": "not_taken"},
            {"course_id": "D", "credits": 3, "status": "not_taken"},
        ]
        factors = {"A": 0.9, "B": 0.5, "C": 0.25, "D": 0.85}
        unlock = {"A": 0, "B": 0, "C": 10, "D": 0}
        common = {
            "eligible_courses": courses,
            "p_student_m3_prime": 1.0,
            "load_lambda": 0.0,
            "risk_tier": "prototype",
            "scenario_credit_max": 6,
            "expected_fail_cap": 0.8,
            "average_credits_per_unit": 2.67,
            "median_real_load_units": 6,
            "unlock_values": unlock,
            "beta": 1.0,
            "gamma": 1.0,
            "minimum_credits": 6,
            "course_factors": factors,
        }
        without_unlock = solve_plan(
            **common,
            enable_unlock_value=False,
            enable_expected_fail_cap=False,
        )
        with_unlock = solve_plan(
            **common,
            enable_unlock_value=True,
            enable_expected_fail_cap=False,
        )
        with_fail_cap = solve_plan(
            **common,
            enable_unlock_value=True,
            enable_expected_fail_cap=True,
        )

        self.assertEqual(without_unlock["status"], "optimal")
        self.assertEqual(with_unlock["status"], "optimal")
        self.assertEqual(with_fail_cap["status"], "optimal")
        self.assertNotEqual(
            set(without_unlock["selected_course_ids"]),
            set(with_unlock["selected_course_ids"]),
        )
        self.assertIn("C", with_unlock["selected_course_ids"])
        self.assertNotIn("C", with_fail_cap["selected_course_ids"])
        self.assertLessEqual(
            with_fail_cap["expected_failed_courses"],
            with_fail_cap["expected_fail_cap"] + 1e-8,
        )

    def test_credit_equivalent_objective_has_known_four_course_optimum(self) -> None:
        courses = [
            {"course_id": course_id, "credits": 3, "status": "not_taken"}
            for course_id in ["A", "B", "C", "D"]
        ]
        result = solve_plan(
            courses,
            p_student_m3_prime=1.0,
            load_lambda=0.0,
            risk_tier="prototype",
            scenario_credit_max=6,
            expected_fail_cap=10.0,
            average_credits_per_unit=3.0,
            median_real_load_units=2,
            unlock_values={"A": 0.0, "B": 0.0, "C": 8.0, "D": 0.0},
            beta=0.125,
            gamma=1.0,
            minimum_credits=6,
            relaxed_minimum_credits=3,
            course_factors={"A": 0.9, "B": 0.5, "C": 0.6, "D": 0.85},
            require_blocking_retakes=False,
        )

        self.assertEqual(result["status"], "optimal")
        self.assertEqual(set(result["selected_course_ids"]), {"A", "D"})
        self.assertAlmostEqual(result["objective_value"], 4.5)

    def test_soft_failure_cap_returns_best_effort_with_flag(self) -> None:
        result = solve_plan(
            [
                {"course_id": "A", "credits": 3, "status": "not_taken"},
                {"course_id": "B", "credits": 3, "status": "not_taken"},
            ],
            p_student_m3_prime=0.2,
            load_lambda=0.0,
            risk_tier="high",
            scenario_credit_max=6,
            expected_fail_cap=0.5,
            average_credits_per_unit=3.0,
            median_real_load_units=2,
            unlock_values={},
            beta=0.125,
            gamma=1.0,
            minimum_credits=6,
            relaxed_minimum_credits=3,
            enforce_cap=False,
            risk_cap_slack_penalty=1000.0,
            require_blocking_retakes=False,
        )

        self.assertEqual(result["status"], "best_effort")
        self.assertTrue(result["risk_cap_exceeded"])
        self.assertEqual(result["selected_credits"], 6)

    def test_hard_cap_retries_with_relaxed_credit_minimum(self) -> None:
        result = solve_plan(
            [
                {"course_id": "A", "credits": 3, "status": "not_taken"},
                {"course_id": "B", "credits": 3, "status": "not_taken"},
            ],
            p_student_m3_prime=0.2,
            load_lambda=0.0,
            risk_tier="high",
            scenario_credit_max=6,
            expected_fail_cap=1.0,
            average_credits_per_unit=3.0,
            median_real_load_units=2,
            unlock_values={},
            beta=0.125,
            gamma=1.0,
            minimum_credits=6,
            relaxed_minimum_credits=3,
            enforce_cap=True,
            require_blocking_retakes=False,
        )

        self.assertEqual(result["status"], "best_effort")
        self.assertTrue(result["reduced_load_advised"])
        self.assertEqual(result["selected_credits"], 3)
        self.assertFalse(result["risk_cap_exceeded"])

    def test_infeasible_after_fallback_has_standard_error_state(self) -> None:
        result = solve_plan(
            [
                {"course_id": "A", "credits": 3, "status": "not_taken"},
                {"course_id": "B", "credits": 3, "status": "not_taken"},
            ],
            p_student_m3_prime=0.2,
            load_lambda=0.0,
            risk_tier="high",
            scenario_credit_max=6,
            expected_fail_cap=0.1,
            average_credits_per_unit=3.0,
            median_real_load_units=2,
            unlock_values={},
            beta=0.125,
            gamma=1.0,
            minimum_credits=6,
            relaxed_minimum_credits=3,
            enforce_cap=True,
            require_blocking_retakes=False,
        )

        self.assertEqual(result["status"], "infeasible_data_error")
        self.assertEqual(result["selected_course_ids"], [])
        self.assertTrue(result["suggested_action"])


if __name__ == "__main__":
    unittest.main()
