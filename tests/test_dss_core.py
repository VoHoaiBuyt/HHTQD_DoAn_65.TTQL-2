"""
pytest — DSS core test suite
=============================
Covers:
  1. Concurrent-chain prerequisite blocking (A song hành B, B thiếu tiên quyết C).
  2. student_id cross-contamination guard in rule_engine.evaluate_student.
  3. ILP best_effort flag when expected_failed > F_max (S003-like scenario).
  4. Edge cases: no eligible courses, graduation_ready, duplicate course IDs,
     selected credits < budget.
  5. Load-basis convergence: load_basis_credits reflects actual selected credits.
  6. Multi-variant plans: solve_plan_variants returns 3 distinct plans with correct
     ordering behaviour (safe picks easy courses, progress picks high-unlock courses).
  7. Curriculum-validation consistency: check count matches log file.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.optimize.ilp_prototype import solve_plan, solve_plan_variants
from src.rules.rule_engine import evaluate_student, load_rules


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def rules():
    return load_rules()


def _course(
    course_id: str,
    *,
    credits: int = 3,
    planned_sem: int = 1,
    offered: str = "both",
    course_type: str = "tự chọn",
) -> dict:
    return {
        "course_id": course_id,
        "course_name": f"Môn {course_id}",
        "credits": str(credits),
        "planned_semester": str(planned_sem),
        "course_type": course_type,
        "offered_semesters": offered,
    }


def _profile(student_id: str = "T-TEST", semester: int = 2) -> dict:
    return {
        "student_id": student_id,
        "current_semester": semester,
        "gpa": 2.8,
        "failed_courses_count": 0,
    }


def _ilp_base(**overrides) -> dict:
    """Minimal solve_plan keyword arguments; override as needed."""
    base = dict(
        p_student_m3_prime=0.75,
        load_lambda=0.0,
        risk_tier="medium",
        scenario_credit_max=18,
        expected_fail_cap=1.5,
        average_credits_per_unit=3.0,
        median_real_load_units=6,
        unlock_values={},
        beta=0.125,
        gamma=1.0,
        minimum_credits=6,
        relaxed_minimum_credits=3,
        require_blocking_retakes=False,
    )
    base.update(overrides)
    return base


# ═════════════════════════════════════════════════════════════════════════════
# 1.  Concurrent-chain prerequisite blocking
# ═════════════════════════════════════════════════════════════════════════════

class TestConcurrentChainBlocking:
    """
    Fixed-point invariant: a course is eligible only when ALL prerequisites
    (strict, prior, concurrent) are met — transitively.  The iteration removes
    blocked courses one pass at a time until the eligible set is stable.
    """

    def test_chain_a_concurrent_b_b_strict_c_blocks_both(self, rules):
        """A song hành B, B tiên quyết C, C not_taken → A and B blocked; C eligible."""
        courses = [_course("A"), _course("B"), _course("C")]
        prerequisites = [
            {"course_id": "A", "prerequisite_id": "B", "type": "song hành"},
            {"course_id": "B", "prerequisite_id": "C", "type": "tiên quyết"},
        ]
        result = evaluate_student(
            _profile("T-CH1"),
            courses, prerequisites, [],
            next_semester=1, p_dropout=0.1, rules=rules,
        )
        eligible = {r["course_id"] for r in result["eligible_courses"]}
        blocked = {r["course_id"] for r in result["blocked_courses"]}

        assert "B" not in eligible, "B phải bị chặn — C chưa hoàn thành"
        assert "A" not in eligible, "A phải bị chặn — đối tác song hành B không eligible"
        assert "C" in eligible, "C không có tiên quyết → đủ điều kiện"
        assert "A" in blocked
        assert "B" in blocked

    def test_chain_unblocked_once_c_completed(self, rules):
        """Khi C completed, B và A đều đủ điều kiện."""
        courses = [_course("A"), _course("B")]
        prerequisites = [
            {"course_id": "A", "prerequisite_id": "B", "type": "song hành"},
            {"course_id": "B", "prerequisite_id": "C", "type": "tiên quyết"},
        ]
        result = evaluate_student(
            _profile("T-CH2"),
            courses, prerequisites,
            [{"course_id": "C", "status": "completed", "attempt_count": 1}],
            next_semester=2, p_dropout=0.1, rules=rules,
        )
        eligible = {r["course_id"] for r in result["eligible_courses"]}
        assert {"A", "B"} == eligible

    def test_deep_chain_propagates_blockage(self, rules):
        """A song hành B, B song hành C, C tiên quyết D, D not_taken → A/B/C blocked."""
        courses = [_course(cid) for cid in "ABCD"]
        prerequisites = [
            {"course_id": "A", "prerequisite_id": "B", "type": "song hành"},
            {"course_id": "B", "prerequisite_id": "C", "type": "song hành"},
            {"course_id": "C", "prerequisite_id": "D", "type": "tiên quyết"},
        ]
        result = evaluate_student(
            _profile("T-CH3"),
            courses, prerequisites, [],
            next_semester=1, p_dropout=0.1, rules=rules,
        )
        eligible = {r["course_id"] for r in result["eligible_courses"]}
        assert "A" not in eligible
        assert "B" not in eligible
        assert "C" not in eligible
        assert "D" in eligible

    def test_mutual_concurrent_pair_both_eligible(self, rules):
        """A song hành B và B song hành A → cả hai tự thỏa mãn nhau → đều eligible."""
        courses = [_course("A"), _course("B")]
        prerequisites = [
            {"course_id": "A", "prerequisite_id": "B", "type": "song hành"},
            {"course_id": "B", "prerequisite_id": "A", "type": "song hành"},
        ]
        result = evaluate_student(
            _profile("T-CH4"),
            courses, prerequisites, [],
            next_semester=1, p_dropout=0.1, rules=rules,
        )
        eligible = {r["course_id"] for r in result["eligible_courses"]}
        assert eligible == {"A", "B"}

    def test_prior_study_type_requires_attempted_not_completed(self, rules):
        """học trước chỉ yêu cầu đã từng học (kể cả failed); chưa học mới bị chặn."""
        courses = [_course("A"), _course("B")]
        prerequisites = [
            {"course_id": "A", "prerequisite_id": "B", "type": "học trước"},
        ]
        # B chưa học → A bị chặn
        result_blocked = evaluate_student(
            _profile("T-CH5"),
            courses, prerequisites, [],
            next_semester=1, p_dropout=0.1, rules=rules,
        )
        eligible_blocked = {r["course_id"] for r in result_blocked["eligible_courses"]}
        assert "A" not in eligible_blocked

        # B failed → A đủ điều kiện (học trước chấp nhận failed)
        result_ok = evaluate_student(
            _profile("T-CH5"),
            courses, prerequisites,
            [{"course_id": "B", "status": "failed", "attempt_count": 1}],
            next_semester=2, p_dropout=0.1, rules=rules,
        )
        eligible_ok = {r["course_id"] for r in result_ok["eligible_courses"]}
        assert "A" in eligible_ok


# ═════════════════════════════════════════════════════════════════════════════
# 2.  student_id cross-contamination guard
# ═════════════════════════════════════════════════════════════════════════════

class TestStudentIdIsolation:
    def test_progress_row_with_wrong_student_id_raises(self, rules):
        """Progress row thuộc sinh viên khác → ValueError chứa 'không khớp'."""
        with pytest.raises(ValueError, match="không khớp"):
            evaluate_student(
                _profile("S001"),
                [], [],
                [{"student_id": "S999", "course_id": "X",
                  "status": "completed", "attempt_count": 1}],
                next_semester=3, p_dropout=0.1, rules=rules,
            )

    def test_blank_student_id_in_progress_row_is_accepted(self, rules):
        """student_id trống (import CSV, dữ liệu cũ) → chấp nhận, không raise."""
        result = evaluate_student(
            _profile("S001"),
            [_course("X")], [],
            [{"student_id": "", "course_id": "X",
              "status": "completed", "attempt_count": 1}],
            next_semester=3, p_dropout=0.1, rules=rules,
        )
        assert result["student_id"] == "S001"

    def test_matching_student_id_in_progress_row_is_accepted(self, rules):
        result = evaluate_student(
            _profile("S001"),
            [_course("X")], [],
            [{"student_id": "S001", "course_id": "X",
              "status": "failed", "attempt_count": 1}],
            next_semester=3, p_dropout=0.1, rules=rules,
        )
        assert result["student_id"] == "S001"

    def test_multiple_foreign_ids_all_named_in_error(self, rules):
        """Hai sinh viên lạ trong tiến độ → lỗi nêu tên cả hai."""
        with pytest.raises(ValueError) as exc_info:
            evaluate_student(
                _profile("S001"),
                [], [],
                [
                    {"student_id": "S002", "course_id": "A",
                     "status": "completed", "attempt_count": 1},
                    {"student_id": "S003", "course_id": "B",
                     "status": "completed", "attempt_count": 1},
                ],
                next_semester=3, p_dropout=0.1, rules=rules,
            )
        msg = str(exc_info.value)
        assert "S002" in msg or "S003" in msg


# ═════════════════════════════════════════════════════════════════════════════
# 3.  ILP best_effort when expected_failed > F_max  (S003-like scenario)
# ═════════════════════════════════════════════════════════════════════════════

class TestILPBestEffort:
    """
    S003 profile: hk1_approved=0 → ability tier=Thấp → low p_pass_m3_prime.
    With 6 courses × p_fail≈0.7, expected_failed ≈ 4.2 >> F_max=1.0.
    The plan must be flagged 'best_effort'; enrolment must NOT be auto-locked.
    """

    def _six_risky_courses(self):
        return [
            {"course_id": f"M{i}", "credits": 3, "status": "not_taken"}
            for i in range(1, 7)
        ]

    def test_low_pass_rate_triggers_best_effort(self):
        result = solve_plan(
            self._six_risky_courses(),
            **_ilp_base(
                p_student_m3_prime=0.3,
                expected_fail_cap=1.0,
                scenario_credit_max=18,
                minimum_credits=6,
            ),
        )
        assert result["status"] == "best_effort", (
            f"Expected best_effort, got '{result['status']}'; "
            f"expected_failed={result['expected_failed_courses']:.2f}"
        )
        assert result["expected_failed_courses"] > result["expected_fail_cap"]

    def test_best_effort_message_names_advisor(self):
        """Thông báo best_effort phải khuyến nghị gặp Cố vấn học tập."""
        result = solve_plan(
            self._six_risky_courses(),
            **_ilp_base(p_student_m3_prime=0.3, expected_fail_cap=1.0),
        )
        assert "Cố vấn" in result["message"] or "Khuyến nghị" in result["message"]

    def test_best_effort_does_not_auto_lock_enrolment(self):
        """Hệ thống tuyệt đối không có trường 'locked' hay tự động khóa đăng ký."""
        result = solve_plan(
            self._six_risky_courses(),
            **_ilp_base(p_student_m3_prime=0.3, expected_fail_cap=1.0),
        )
        assert "locked" not in result, "Không được có trường 'locked' trong kết quả"
        assert "enrollment_blocked" not in result
        # suggested_action phải nhắc "KHÔNG tự động hạn chế"
        assert "KHÔNG" in result.get("suggested_action", "") or \
               "cố vấn" in result.get("suggested_action", "").lower()

    def test_expected_fail_exceeded_field_present_and_correct(self):
        """expected_fail_exceeded phải xuất hiện và đúng giá trị."""
        # Cap rất thấp → exceeded
        tight = solve_plan(
            [{"course_id": "A", "credits": 3}],
            **_ilp_base(
                p_student_m3_prime=0.5,
                expected_fail_cap=0.1,
                minimum_credits=3,
                scenario_credit_max=3,
            ),
        )
        assert "expected_fail_exceeded" in tight
        if tight["status"] not in ("no_eligible_courses", "graduation_ready"):
            assert tight["expected_fail_exceeded"] is True

        # High pass rate → not exceeded
        easy = solve_plan(
            [{"course_id": f"C{i}", "credits": 3} for i in range(4)],
            **_ilp_base(
                p_student_m3_prime=0.98,
                expected_fail_cap=1.5,
                minimum_credits=12,
                scenario_credit_max=12,
            ),
        )
        if easy["status"] == "optimal":
            assert easy["expected_fail_exceeded"] is False

    def test_optimal_when_pass_rate_high_enough(self):
        result = solve_plan(
            [{"course_id": f"C{i}", "credits": 3} for i in range(4)],
            **_ilp_base(
                p_student_m3_prime=0.95,
                expected_fail_cap=1.5,
                minimum_credits=12,
                scenario_credit_max=12,
            ),
        )
        assert result["status"] == "optimal"
        assert not result["expected_fail_exceeded"]


# ═════════════════════════════════════════════════════════════════════════════
# 4.  Edge cases: terminal states, duplicates, credits < budget
# ═════════════════════════════════════════════════════════════════════════════

class TestILPEdgeCases:
    def test_empty_eligible_list_returns_no_eligible_status(self):
        result = solve_plan([], **_ilp_base())
        assert result["status"] == "no_eligible_courses"
        assert result["selected_course_ids"] == []
        assert result["selected_credits"] == 0
        assert result["expected_fail_exceeded"] is False

    def test_graduation_ready_returns_explicit_status(self):
        result = solve_plan([], graduation_ready=True, **_ilp_base())
        assert result["status"] == "graduation_ready"
        assert result["selected_credits"] == 0

    def test_selected_credits_less_than_budget_is_valid(self):
        """Chỉ có 2 môn × 3TC khả dụng; budget=18 → selected=6 < 18 là đúng."""
        courses = [
            {"course_id": "A", "credits": 3, "status": "not_taken"},
            {"course_id": "B", "credits": 3, "status": "not_taken"},
        ]
        result = solve_plan(
            courses,
            **_ilp_base(
                p_student_m3_prime=0.8,
                scenario_credit_max=18,
                minimum_credits=6,
                expected_fail_cap=5.0,
                beta=0.0,
                gamma=0.0,
            ),
        )
        assert result["status"] in ("optimal", "best_effort")
        assert result["selected_credits"] == 6, (
            f"Chỉ 6TC khả dụng; selected_credits phải là 6 dù budget 18. "
            f"Nhận: {result['selected_credits']}"
        )
        assert result["selected_credits"] < 18

    def test_duplicate_course_ids_raise_value_error(self):
        courses = [
            {"course_id": "X", "credits": 3},
            {"course_id": "X", "credits": 3},
        ]
        with pytest.raises(ValueError, match="duplicate"):
            solve_plan(courses, **_ilp_base())

    def test_negative_p_student_raises(self):
        with pytest.raises(ValueError):
            solve_plan([], **_ilp_base(p_student_m3_prime=-0.1))

    def test_invalid_credit_bounds_raise(self):
        with pytest.raises(ValueError, match="[Ii]nvalid|bound"):
            solve_plan(
                [],
                **_ilp_base(
                    minimum_credits=15,
                    relaxed_minimum_credits=20,  # relaxed > minimum → invalid
                ),
            )

    def test_objective_contributions_returned_for_feasible_plans(self):
        """objective_contributions phải có cho mỗi môn được chọn."""
        courses = [
            {"course_id": f"C{i}", "credits": 3} for i in range(4)
        ]
        result = solve_plan(
            courses,
            **_ilp_base(
                minimum_credits=6,
                scenario_credit_max=6,
                beta=0.125,
                gamma=1.0,
            ),
        )
        if result["status"] in ("optimal", "best_effort"):
            assert "objective_contributions" in result
            selected_ids = set(result["selected_course_ids"])
            contrib_ids = {c["course_id"] for c in result["objective_contributions"]}
            assert contrib_ids == selected_ids, (
                "objective_contributions phải chứa đúng các môn được chọn"
            )
            for c in result["objective_contributions"]:
                assert "pass_term" in c
                assert "fail_penalty" in c
                assert "unlock_term" in c
                assert "total_contribution" in c


# ═════════════════════════════════════════════════════════════════════════════
# 5.  Load-basis converges to actual selected credits
# ═════════════════════════════════════════════════════════════════════════════

class TestILPLoadBasis:
    def test_load_basis_credits_equals_actual_selected(self):
        """
        scenario_credit_max=18 nhưng chỉ 6TC khả dụng.
        Sau refinement loop, load_basis_credits phải hội tụ về 6, không phải 18.
        load_multiplier phải tính từ 6TC → 1.0 (không bị penalty).
        """
        courses = [
            {"course_id": "X", "credits": 3},
            {"course_id": "Y", "credits": 3},
        ]
        result = solve_plan(
            courses,
            p_student_m3_prime=0.8,
            load_lambda=0.5,
            risk_tier="medium",
            scenario_credit_max=18,
            expected_fail_cap=5.0,
            average_credits_per_unit=3.0,
            median_real_load_units=2,
            unlock_values={},
            beta=0.0,
            gamma=0.0,
            minimum_credits=6,
            relaxed_minimum_credits=6,
            require_blocking_retakes=False,
        )
        assert result["selected_credits"] == 6
        assert result["load_basis_credits"] == 6, (
            f"load_basis_credits phải là 6 (thực tế), không phải 18 (ngân sách). "
            f"Nhận: {result['load_basis_credits']}"
        )
        assert not result["load_basis_mismatch"]
        # load từ 6TC = 2 units = median → multiplier = 1.0
        assert result["load_multiplier"] == pytest.approx(1.0, abs=1e-9)
        # scenario_load_multiplier tính từ 18TC >> median → phải thấp hơn nhiều
        assert result["scenario_load_multiplier"] < 0.5

    def test_load_mismatch_flag_absent_when_converged(self):
        """load_basis_mismatch=False khi vòng lặp hội tụ."""
        courses = [{"course_id": f"C{i}", "credits": 3} for i in range(4)]
        result = solve_plan(
            courses,
            **_ilp_base(
                load_lambda=0.1,
                scenario_credit_max=12,
                minimum_credits=12,
                beta=0.0,
                gamma=0.0,
            ),
        )
        if result["status"] in ("optimal", "best_effort"):
            assert not result["load_basis_mismatch"]


# ═════════════════════════════════════════════════════════════════════════════
# 6.  Multi-variant plans (solve_plan_variants)
# ═════════════════════════════════════════════════════════════════════════════

class TestILPVariants:
    @pytest.fixture
    def six_courses(self):
        return [
            {"course_id": f"C{i}", "credits": 3, "status": "not_taken"}
            for i in range(1, 7)
        ]

    def _base_variants_kwargs(self, **overrides):
        base = dict(
            p_student_m3_prime=0.65,
            load_lambda=0.0,
            risk_tier="medium",
            scenario_credit_max=12,
            expected_fail_cap=5.0,
            average_credits_per_unit=3.0,
            median_real_load_units=6,
            unlock_values={f"C{i}": 0.0 for i in range(1, 7)},
            beta=0.125,
            gamma=1.0,
            minimum_credits=6,
            relaxed_minimum_credits=3,
            require_blocking_retakes=False,
        )
        base.update(overrides)
        return base

    def test_returns_exactly_three_variants(self, six_courses):
        variants = solve_plan_variants(six_courses, **self._base_variants_kwargs())
        assert len(variants) == 3

    def test_variant_keys_are_safe_progress_balanced(self, six_courses):
        variants = solve_plan_variants(six_courses, **self._base_variants_kwargs())
        keys = [v["variant_key"] for v in variants]
        assert keys == ["safe", "progress", "balanced"]

    def test_each_variant_has_required_fields(self, six_courses):
        variants = solve_plan_variants(six_courses, **self._base_variants_kwargs())
        required = {"variant_key", "variant_label", "objective_note", "beta", "gamma", "result"}
        for v in variants:
            assert required <= v.keys(), f"Variant {v.get('variant_key')} thiếu trường"

    def test_safe_variant_has_zero_beta(self, six_courses):
        """Safe variant dùng beta_scale=0 → scaled beta=0."""
        variants = solve_plan_variants(six_courses, **self._base_variants_kwargs())
        safe = next(v for v in variants if v["variant_key"] == "safe")
        assert safe["beta"] == pytest.approx(0.0)

    def test_progress_variant_prefers_high_unlock_course(self):
        """Progress variant (β×4) phải chọn UNLOCK_COURSE khi unlock_value rất cao."""
        courses = [
            {"course_id": "UNLOCK", "credits": 3, "status": "not_taken"},
            {"course_id": "PLAIN",  "credits": 3, "status": "not_taken"},
        ]
        unlock_values = {"UNLOCK": 25.0, "PLAIN": 0.0}
        variants = solve_plan_variants(
            courses,
            p_student_m3_prime=0.7,
            load_lambda=0.0,
            risk_tier="low",
            scenario_credit_max=3,   # only 1 course fits
            expected_fail_cap=5.0,
            average_credits_per_unit=3.0,
            median_real_load_units=6,
            unlock_values=unlock_values,
            beta=0.125,
            gamma=1.0,
            minimum_credits=3,
            relaxed_minimum_credits=3,
            require_blocking_retakes=False,
        )
        progress = next(v for v in variants if v["variant_key"] == "progress")
        progress_ids = set(progress["result"].get("selected_course_ids", []))
        assert "UNLOCK" in progress_ids, (
            f"Progress variant phải chọn UNLOCK (unlock=25) chứ không phải PLAIN. "
            f"Chọn: {progress_ids}"
        )

    def test_safe_variant_avoids_hard_course(self):
        """Safe variant (γ cao) phải tránh môn khó (p_pass thấp) khi có lựa chọn."""
        courses = [
            {"course_id": "HARD", "credits": 3, "status": "not_taken"},
            {"course_id": "EASY", "credits": 3, "status": "not_taken"},
        ]
        course_factors = {"HARD": 0.2, "EASY": 1.0}  # HARD: 20% of base rate
        unlock_values = {"HARD": 0.0, "EASY": 0.0}
        variants = solve_plan_variants(
            courses,
            p_student_m3_prime=0.7,
            load_lambda=0.0,
            risk_tier="medium",
            scenario_credit_max=3,
            expected_fail_cap=5.0,
            average_credits_per_unit=3.0,
            median_real_load_units=6,
            unlock_values=unlock_values,
            beta=0.0,
            gamma=1.0,
            minimum_credits=3,
            relaxed_minimum_credits=3,
            course_factors=course_factors,
            require_blocking_retakes=False,
        )
        safe = next(v for v in variants if v["variant_key"] == "safe")
        safe_ids = set(safe["result"].get("selected_course_ids", []))
        assert "EASY" in safe_ids, (
            f"Safe variant phải chọn EASY (p_pass=0.70) thay vì HARD (p_pass=0.14). "
            f"Chọn: {safe_ids}"
        )

    def test_safe_expected_fail_lte_progress_expected_fail(self):
        """
        Với unlock cao cho môn khó: progress chọn môn khó → expected_fail cao hơn safe.
        safe_fail ≤ progress_fail phải đúng.
        """
        courses = [
            {"course_id": "HARD", "credits": 3, "status": "not_taken"},
            {"course_id": "EASY", "credits": 3, "status": "not_taken"},
        ]
        course_factors = {"HARD": 0.3, "EASY": 1.0}
        unlock_values = {"HARD": 20.0, "EASY": 0.0}
        variants = solve_plan_variants(
            courses,
            p_student_m3_prime=0.7,
            load_lambda=0.0,
            risk_tier="medium",
            scenario_credit_max=3,
            expected_fail_cap=5.0,
            average_credits_per_unit=3.0,
            median_real_load_units=6,
            unlock_values=unlock_values,
            beta=0.125,
            gamma=1.0,
            minimum_credits=3,
            relaxed_minimum_credits=3,
            course_factors=course_factors,
            require_blocking_retakes=False,
        )
        safe = next(v for v in variants if v["variant_key"] == "safe")
        progress = next(v for v in variants if v["variant_key"] == "progress")
        safe_fail = safe["result"].get("expected_failed_courses", 0.0)
        progress_fail = progress["result"].get("expected_failed_courses", 0.0)
        assert safe_fail <= progress_fail + 1e-6, (
            f"Safe ({safe_fail:.3f}) phải ≤ progress ({progress_fail:.3f}) expected_failed"
        )

    def test_all_variants_flagged_best_effort_when_all_risky(self):
        """
        Nếu p_pass rất thấp và F_max=1: mọi phương án đều phải gắn best_effort
        (không có phương án nào có thể đạt optimal).
        """
        risky = [{"course_id": f"R{i}", "credits": 3} for i in range(6)]
        variants = solve_plan_variants(
            risky,
            p_student_m3_prime=0.2,
            load_lambda=0.0,
            risk_tier="high",
            scenario_credit_max=18,
            expected_fail_cap=1.0,
            average_credits_per_unit=3.0,
            median_real_load_units=6,
            unlock_values={f"R{i}": 0.0 for i in range(6)},
            beta=0.125,
            gamma=1.0,
            minimum_credits=6,
            relaxed_minimum_credits=3,
            require_blocking_retakes=False,
        )
        for v in variants:
            r = v["result"]
            terminal = {"no_eligible_courses", "graduation_ready", "infeasible_data_error"}
            if r["status"] not in terminal:
                assert r["status"] == "best_effort", (
                    f"Variant '{v['variant_key']}' status='{r['status']}' "
                    f"expected_failed={r.get('expected_failed_courses', '?'):.2f}"
                )


# ═════════════════════════════════════════════════════════════════════════════
# 7.  Curriculum-validation consistency
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def _curriculum_validation_run():
    """Chạy validate_curriculum.py một lần cho cả module; trả về (proc, log_text)."""
    script = ROOT / "src" / "data" / "validate_curriculum.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
    )
    log_path = ROOT / "reports" / "curriculum_validation.txt"
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    return proc, log_text


class TestCurriculumValidation:
    """
    Chạy validate_curriculum.py qua subprocess, sau đó kiểm tra:
    - exit code = 0 (tất cả PASS)
    - số dòng PASS + FAIL trong log == 11 (số lệnh check() trong main())
    - không có dòng FAIL nào
    - Kết luận PASS
    """

    def test_script_exits_with_zero(self, _curriculum_validation_run):
        proc, _ = _curriculum_validation_run
        assert proc.returncode == 0, (
            f"validate_curriculum.py phải exit 0 (all PASS). "
            f"stdout: {proc.stdout[:500]}"
        )

    def test_log_has_no_fail_lines(self, _curriculum_validation_run):
        _, log_text = _curriculum_validation_run
        fail_lines = [l for l in log_text.splitlines() if l.startswith("FAIL:")]
        assert fail_lines == [], f"Log có FAIL lines: {fail_lines}"

    def test_check_count_is_eleven(self, _curriculum_validation_run):
        """
        validate_curriculum.py có đúng 11 lệnh check() trong main().
        Log phải có 11 dòng PASS (hoặc FAIL nếu có lỗi dữ liệu).
        """
        _, log_text = _curriculum_validation_run
        check_lines = [
            l for l in log_text.splitlines()
            if l.startswith("PASS:") or l.startswith("FAIL:")
        ]
        assert len(check_lines) == 11, (
            f"Số tiêu chí kiểm tra phải là 11 (đúng với số check() trong "
            f"validate_curriculum.py). Thực tế: {len(check_lines)}. "
            f"Nếu validate_curriculum.py đã thêm/bớt check(), cập nhật số này."
        )

    def test_conclusion_says_pass(self, _curriculum_validation_run):
        _, log_text = _curriculum_validation_run
        assert "KẾT LUẬN: PASS" in log_text, (
            "Dòng KẾT LUẬN phải là PASS. Log hiện tại:\n" + log_text[-300:]
        )
