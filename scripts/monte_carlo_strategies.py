"""Monte Carlo comparison of the ILP plan against three registration baselines.

SIMULATED scenario analysis, not NTU evidence. Course outcomes are Bernoulli
draws using the M3' pass-rate prior estimated from REAL UCI-697, multiplied by
SIMULATED course-difficulty factors and ASSUMED load/retake multipliers.
P(Dropout) is used only for warning/tier selection; it is not simulated as a
per-semester hazard.

Strategies
----------
ILP : risk-aware PuLP plan (build_plans) with a fixed 18-credit budget.
B1  : planned-semester courses + failed retakes, then planned courses <= term.
B2  : any eligible course, greedily fill up to 18 credits.
B3  : any eligible course, greedily fill up to 15 credits.

Protocol
--------
* 1,000 runs per student per strategy (7 active personas; S008 already graduated).
* Common random numbers: every strategy sees the same course/term uniform draws,
  so paired differences are comparable.
* Horizon: up to semester 16; on-time means graduation by semester 8.
* Metrics: graduation rate, on-time rate, feasibility/plan-success rates,
  semesters to graduation, simulated failures, credits earned.
* 95% CI by bootstrap; Pareto frontier minimises failures and maximises on-time.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from math import exp
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.optimize.plan_risk import credits_to_curricular_units
from src.rules.rule_engine import evaluate_student, load_rules
from src.services.assessment import (
    assess_student,
    build_plans,
    load_bundle,
    load_curriculum,
    persona_payload,
)

OUTPUT_DIR = ROOT / "reports" / "generated"
STRATEGIES = ["ILP", "B1", "B2", "B3"]
STRATEGY_LABELS = {
    "ILP": "ILP (risk-aware)",
    "B1": "B1 lộ trình + thi lại",
    "B2": "B2 tối đa tín chỉ (18)",
    "B3": "B3 cố định 15 tín chỉ",
}
MEDIAN_LOAD_UNITS = 6
DEADLINE_SEMESTER = 8
HORIZON_SEMESTER = 16
GRADUATION_CREDITS = 128
BOOTSTRAP_REPETITIONS = 1000


def _course_credits(curriculum: dict[str, Any]) -> dict[str, int]:
    return {
        str(course["course_id"]): int(course["credits"])
        for course in curriculum["courses"]
    }


def _course_indices(curriculum: dict[str, Any]) -> dict[str, int]:
    return {
        str(course["course_id"]): index
        for index, course in enumerate(curriculum["courses"])
    }


def _initial_state(
    curriculum: dict[str, Any],
    progress_rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, int], dict[str, int | None]]:
    status = {
        str(course["course_id"]): "not_taken"
        for course in curriculum["courses"]
    }
    attempts = {course_id: 0 for course_id in status}
    semester_taken: dict[str, int | None] = {course_id: None for course_id in status}
    for row in progress_rows:
        course_id = str(row["course_id"])
        status[course_id] = str(row.get("status", "not_taken"))
        attempts[course_id] = int(row.get("attempt_count", 0) or 0)
        taken = row.get("semester_taken")
        semester_taken[course_id] = int(taken) if pd.notna(taken) else None
    return status, attempts, semester_taken


def _progress_rows(
    student_id: str,
    status: dict[str, str],
    attempts: dict[str, int],
    semester_taken: dict[str, int | None],
) -> list[dict[str, Any]]:
    return [
        {
            "student_id": student_id,
            "course_id": course_id,
            "status": course_status,
            "attempt_count": attempts.get(course_id, 0),
            "semester_taken": semester_taken.get(course_id),
            "grade_10": None,
        }
        for course_id, course_status in status.items()
        if course_status in {"completed", "failed"}
    ]


def _concurrent_closure(
    course_id: str,
    status: dict[str, str],
    prerequisites: list[dict[str, Any]],
) -> set[str]:
    closure = {course_id}
    stack = [course_id]
    while stack:
        current = stack.pop()
        for relation in prerequisites:
            if str(relation["course_id"]) != current:
                continue
            if str(relation["type"]) != "song hành":
                continue
            partner = str(relation["prerequisite_id"])
            if (
                status.get(partner) not in {"completed", "in_progress"}
                and partner not in closure
            ):
                closure.add(partner)
                stack.append(partner)
    return closure


def _greedy_plan(
    candidates: list[dict[str, Any]],
    *,
    cap: int,
    status: dict[str, str],
    prerequisites: list[dict[str, Any]],
    eligible_ids: set[str],
    allowed_ids: set[str],
    credits: dict[str, int],
    planned_semester: dict[str, int],
    priority,
) -> list[str]:
    selected: list[str] = []
    selected_set: set[str] = set()
    used = 0
    for course in sorted(candidates, key=priority):
        course_id = str(course["course_id"])
        if course_id in selected_set:
            continue
        closure = _concurrent_closure(course_id, status, prerequisites)
        if not closure <= eligible_ids or not closure <= allowed_ids:
            continue
        new_members = closure - selected_set
        added_credits = sum(credits.get(member, 0) for member in new_members)
        if added_credits == 0 or used + added_credits > cap:
            continue
        ordered = sorted(
            new_members,
            key=lambda member: (planned_semester.get(member, 99), member),
        )
        selected.extend(ordered)
        selected_set |= new_members
        used += added_credits
    return selected


def _select_plan(
    strategy: str,
    *,
    student_id: str,
    profile: dict[str, Any],
    rule_result: dict[str, Any],
    curriculum: dict[str, Any],
    bundle: dict[str, Any],
    rules: dict[str, Any],
    status: dict[str, str],
    attempts: dict[str, int],
    semester_taken: dict[str, int | None],
    semester: int,
    p_pass_m3: float,
) -> list[str]:
    if strategy == "ILP":
        assessment = {
            "progress_rows": _progress_rows(
                student_id, status, attempts, semester_taken
            ),
            "rule_result": rule_result,
            "p_pass_m3_prime": p_pass_m3,
            "planning_tier": rule_result["risk_tier"],
        }
        plans = build_plans(
            assessment,
            curriculum,
            bundle,
            rules,
            budgets=[18],
            load_lambda=float(
                rules["risk_to_plan_exploration"]["base_load_lambda"]["value"]
            ),
            retake_multiplier=1.0,
        )
        return list(plans[0]["result"].get("selected_course_ids", []))

    eligible = rule_result["eligible_courses"]
    eligible_ids = {str(course["course_id"]) for course in eligible}
    credits = _course_credits(curriculum)
    planned_semester = {
        str(course["course_id"]): int(course["planned_semester"])
        for course in curriculum["courses"]
    }
    if strategy == "B1":
        candidates = [
            course
            for course in eligible
            if str(course["status"]) == "failed"
            or int(course["planned_semester"]) <= semester
        ]
        allowed_ids = {str(course["course_id"]) for course in candidates}
        priority = lambda course: (
            0 if str(course["status"]) == "failed" else 1,
            int(course["planned_semester"]),
            str(course["course_id"]),
        )
    else:
        candidates = eligible
        allowed_ids = eligible_ids
        priority = lambda course: (
            int(course["planned_semester"]),
            str(course["course_id"]),
        )
    cap = 15 if strategy == "B3" else 18
    return _greedy_plan(
        candidates,
        cap=cap,
        status=status,
        prerequisites=curriculum["prerequisites"],
        eligible_ids=eligible_ids,
        allowed_ids=allowed_ids,
        credits=credits,
        planned_semester=planned_semester,
        priority=priority,
    )


def _course_probability(
    course_id: str,
    *,
    status: dict[str, str],
    attempts: dict[str, int],
    course_by_id: dict[str, dict[str, Any]],
    difficulty_factors: dict[str, float],
    p_pass_m3: float,
    load_multiplier: float,
    retake_multiplier: float,
) -> float:
    course = course_by_id[course_id]
    factor = float(difficulty_factors.get(str(course.get("group", "")), 1.0))
    repeated = status.get(course_id) == "failed" or attempts.get(course_id, 0) > 0
    retake_factor = retake_multiplier if repeated else 1.0
    return min(1.0, max(0.0, p_pass_m3 * factor * load_multiplier * retake_factor))


def _simulate_path(
    strategy: str,
    *,
    student_id: str,
    profile: dict[str, Any],
    curriculum: dict[str, Any],
    bundle: dict[str, Any],
    rules: dict[str, Any],
    p_pass_m3: float,
    p_dropout: float,
    p_dropout_calibrated: float | None,
    run_seed: int,
) -> dict[str, Any]:
    credits = _course_credits(curriculum)
    course_indices = _course_indices(curriculum)
    course_by_id = curriculum["course_by_id"]
    status, attempts, semester_taken = _initial_state(
        curriculum, profile["_progress_rows"]
    )
    initial_completed = sum(
        credits[course_id]
        for course_id, course_status in status.items()
        if course_status == "completed"
    )
    if initial_completed >= GRADUATION_CREDITS:
        return {
            "strategy": strategy,
            "student_id": student_id,
            "graduated": 1,
            "on_time": int(int(profile["current_semester"]) <= DEADLINE_SEMESTER),
            "graduation_semester": int(profile["current_semester"]),
            "semesters_to_graduation": 0,
            "simulated_failures": 0,
            "credits_earned": 0,
            "final_credits": initial_completed,
            "no_eligible_semesters": 0,
            "empty_plan_semesters": 0,
            "idle_semesters": 0,
            "feasible": 1,
            "plan_success": 1,
            "permanently_failed_courses": 0,
        }

    rng = np.random.default_rng(run_seed)
    uniforms = rng.random((HORIZON_SEMESTER + 2, len(course_indices)))
    load_lambda = float(
        rules["risk_to_plan_exploration"]["base_load_lambda"]["value"]
    )
    maximum_attempts = int(rules["retake"]["maximum_attempts"]["value"])
    average_credits = float(bundle["average_credits_per_unit"])
    difficulty_factors = {
        str(key): float(value) for key, value in bundle["difficulty_factors"].items()
    }

    completed = initial_completed
    simulated_failures = 0
    credits_earned = 0
    no_eligible_semesters = 0
    empty_plan_semesters = 0
    idle_semesters = 0
    graduation_semester: int | None = None
    semester = int(profile["current_semester"]) + 1

    while completed < GRADUATION_CREDITS and semester <= HORIZON_SEMESTER:
        current_profile = dict(profile)
        current_profile["current_semester"] = semester - 1
        current_profile["cumulative_credits"] = completed
        current_profile["failed_courses_count"] = sum(
            1 for course_status in status.values() if course_status == "failed"
        )
        rule_result = evaluate_student(
            current_profile,
            curriculum["courses"],
            curriculum["prerequisites"],
            _progress_rows(student_id, status, attempts, semester_taken),
            next_semester=semester,
            p_dropout=p_dropout,
            p_dropout_calibrated=p_dropout_calibrated,
            rules=rules,
        )
        eligible_courses = rule_result["eligible_courses"]
        selected = _select_plan(
            strategy,
            student_id=student_id,
            profile=current_profile,
            rule_result=rule_result,
            curriculum=curriculum,
            bundle=bundle,
            rules=rules,
            status=status,
            attempts=attempts,
            semester_taken=semester_taken,
            semester=semester,
            p_pass_m3=p_pass_m3,
        )
        if not eligible_courses:
            no_eligible_semesters += 1
        elif not selected:
            if strategy == "B1":
                idle_semesters += 1
            else:
                empty_plan_semesters += 1
        if not selected:
            has_remaining_attempt = any(
                course_status != "completed"
                and attempts.get(course_id, 0) < maximum_attempts
                for course_id, course_status in status.items()
            )
            if not has_remaining_attempt:
                break
            semester += 1
            continue

        selected_credits = sum(credits[course_id] for course_id in selected)
        units = credits_to_curricular_units(selected_credits, average_credits)
        load_multiplier = min(
            1.0,
            max(0.0, exp(-load_lambda * max(0, units - MEDIAN_LOAD_UNITS))),
        )
        for course_id in selected:
            probability = _course_probability(
                course_id,
                status=status,
                attempts=attempts,
                course_by_id=course_by_id,
                difficulty_factors=difficulty_factors,
                p_pass_m3=p_pass_m3,
                load_multiplier=load_multiplier,
                retake_multiplier=1.0,
            )
            uniform = uniforms[semester, course_indices[course_id]]
            attempts[course_id] = attempts.get(course_id, 0) + 1
            semester_taken[course_id] = semester
            if uniform < probability:
                if status[course_id] != "completed":
                    completed += credits[course_id]
                    credits_earned += credits[course_id]
                status[course_id] = "completed"
            else:
                status[course_id] = "failed"
                simulated_failures += 1

        if completed >= GRADUATION_CREDITS:
            graduation_semester = semester
            break
        semester += 1

    permanently_failed = sum(
        1
        for course_id, course_status in status.items()
        if course_status == "failed" and attempts.get(course_id, 0) >= maximum_attempts
    )
    graduated = graduation_semester is not None
    return {
        "strategy": strategy,
        "student_id": student_id,
        "graduated": int(graduated),
        "on_time": int(
            graduated and graduation_semester <= DEADLINE_SEMESTER
        ),
        "graduation_semester": graduation_semester,
        "semesters_to_graduation": (
            graduation_semester - int(profile["current_semester"])
            if graduated
            else np.nan
        ),
        "simulated_failures": simulated_failures,
        "credits_earned": credits_earned,
        "final_credits": completed,
        "no_eligible_semesters": no_eligible_semesters,
        "empty_plan_semesters": empty_plan_semesters,
        "idle_semesters": idle_semesters,
        "feasible": int(no_eligible_semesters == 0),
        "plan_success": int(empty_plan_semesters == 0),
        "permanently_failed_courses": permanently_failed,
    }


def _bootstrap_mean_ci(
    values: np.ndarray,
    *,
    rng: np.random.Generator,
    repetitions: int = BOOTSTRAP_REPETITIONS,
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if values.size == 0:
        return np.nan, np.nan
    samples = np.array(
        [
            values[rng.integers(0, values.size, values.size)].mean()
            for _ in range(repetitions)
        ]
    )
    low, high = np.percentile(samples, [2.5, 97.5])
    return float(low), float(high)


def _summarize(
    frame: pd.DataFrame,
    *,
    rng: np.random.Generator,
    scope: str,
    student_id: str | None = None,
) -> dict[str, Any]:
    graduated = frame["graduated"].to_numpy(dtype=float)
    on_time = frame["on_time"].to_numpy(dtype=float)
    semesters = frame["semesters_to_graduation"].to_numpy(dtype=float)
    failures = frame["simulated_failures"].to_numpy(dtype=float)
    credits = frame["credits_earned"].to_numpy(dtype=float)
    feasible = frame["feasible"].to_numpy(dtype=float)
    plan_success = frame["plan_success"].to_numpy(dtype=float)

    on_time_ci = _bootstrap_mean_ci(on_time, rng=rng)
    graduation_ci = _bootstrap_mean_ci(graduated, rng=rng)
    failures_ci = _bootstrap_mean_ci(failures, rng=rng)
    credits_ci = _bootstrap_mean_ci(credits, rng=rng)
    semesters_ci = _bootstrap_mean_ci(semesters, rng=rng)
    return {
        "scope": scope,
        "student_id": student_id or "ALL",
        "strategy": str(frame["strategy"].iloc[0]),
        "runs": len(frame),
        "graduation_rate": float(graduated.mean()),
        "graduation_rate_ci_low": graduation_ci[0],
        "graduation_rate_ci_high": graduation_ci[1],
        "on_time_rate": float(on_time.mean()),
        "on_time_rate_ci_low": on_time_ci[0],
        "on_time_rate_ci_high": on_time_ci[1],
        "feasibility_rate": float(feasible.mean()),
        "plan_success_rate": float(plan_success.mean()),
        "mean_semesters_to_graduation": (
            float(np.nanmean(semesters)) if np.isfinite(semesters).any() else np.nan
        ),
        "median_semesters_to_graduation": (
            float(np.nanmedian(semesters)) if np.isfinite(semesters).any() else np.nan
        ),
        "mean_semesters_ci_low": semesters_ci[0],
        "mean_semesters_ci_high": semesters_ci[1],
        "censored_rate": float(1.0 - graduated.mean()),
        "mean_simulated_failures": float(failures.mean()),
        "mean_simulated_failures_ci_low": failures_ci[0],
        "mean_simulated_failures_ci_high": failures_ci[1],
        "mean_credits_earned": float(credits.mean()),
        "mean_credits_earned_ci_low": credits_ci[0],
        "mean_credits_earned_ci_high": credits_ci[1],
        "mean_no_eligible_semesters": float(
            frame["no_eligible_semesters"].mean()
        ),
        "mean_empty_plan_semesters": float(
            frame["empty_plan_semesters"].mean()
        ),
        "mean_idle_semesters": float(frame["idle_semesters"].mean()),
        "mean_permanently_failed_courses": float(
            frame["permanently_failed_courses"].mean()
        ),
    }


def _add_pareto_frontier(summary: pd.DataFrame, scope_column: str = "scope") -> pd.DataFrame:
    frontier = []
    for _, scope_frame in summary.groupby(scope_column, sort=False):
        for index, row in scope_frame.iterrows():
            dominated = False
            for other_index, other in scope_frame.iterrows():
                if other_index == index:
                    continue
                no_worse = (
                    other["on_time_rate"] >= row["on_time_rate"]
                    and other["mean_simulated_failures"]
                    <= row["mean_simulated_failures"]
                )
                strictly_better = (
                    other["on_time_rate"] > row["on_time_rate"]
                    or other["mean_simulated_failures"]
                    < row["mean_simulated_failures"]
                )
                if no_worse and strictly_better:
                    dominated = True
                    break
            frontier.append(not dominated)
    return summary.assign(pareto_frontier=frontier)


def _paired_differences(
    runs: pd.DataFrame,
    *,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    for baseline in ["B1", "B2", "B3"]:
        paired = runs.pivot_table(
            index=["student_id", "run"],
            columns="strategy",
            values=[
                "on_time",
                "graduated",
                "simulated_failures",
                "credits_earned",
                "semesters_to_graduation",
            ],
            aggfunc="first",
        )
        for metric in [
            "on_time",
            "graduated",
            "simulated_failures",
            "credits_earned",
        ]:
            difference = (
                paired[(metric, "ILP")] - paired[(metric, baseline)]
            ).to_numpy(dtype=float)
            low, high = _bootstrap_mean_ci(difference, rng=rng)
            rows.append(
                {
                    "comparison": f"ILP - {baseline}",
                    "metric": metric,
                    "mean_difference": float(np.nanmean(difference)),
                    "ci_low": low,
                    "ci_high": high,
                    "ci_excludes_zero": bool(low > 0 or high < 0),
                    "paired_runs": int(np.isfinite(difference).sum()),
                }
            )
        semester_difference = (
            paired[("semesters_to_graduation", "ILP")]
            - paired[("semesters_to_graduation", baseline)]
        ).to_numpy(dtype=float)
        low, high = _bootstrap_mean_ci(semester_difference, rng=rng)
        rows.append(
            {
                "comparison": f"ILP - {baseline}",
                "metric": "semesters_to_graduation",
                "mean_difference": float(np.nanmean(semester_difference)),
                "ci_low": low,
                "ci_high": high,
                "ci_excludes_zero": bool(
                    np.isfinite(low) and np.isfinite(high) and (low > 0 or high < 0)
                ),
                "paired_runs": int(np.isfinite(semester_difference).sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_pareto(summary: pd.DataFrame) -> Path:
    fig, axis = plt.subplots(figsize=(8.0, 5.5))
    colors = {
        "ILP": "#1f4e79",
        "B1": "#2e8b57",
        "B2": "#c0504d",
        "B3": "#8064a2",
    }
    for _, row in summary.iterrows():
        strategy = str(row["strategy"])
        x_error = np.array(
            [
                row["mean_simulated_failures"] - row["mean_simulated_failures_ci_low"],
                row["mean_simulated_failures_ci_high"] - row["mean_simulated_failures"],
            ]
        ).reshape(2, 1)
        y_error = np.array(
            [
                row["on_time_rate"] - row["on_time_rate_ci_low"],
                row["on_time_rate_ci_high"] - row["on_time_rate"],
            ]
        ).reshape(2, 1)
        axis.errorbar(
            row["mean_simulated_failures"],
            row["on_time_rate"],
            xerr=x_error,
            yerr=y_error,
            fmt="o",
            capsize=4,
            color=colors.get(strategy, "#444444"),
            label=STRATEGY_LABELS.get(strategy, strategy),
        )
        axis.annotate(
            strategy,
            (row["mean_simulated_failures"], row["on_time_rate"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
        )
    axis.set_xlabel("Số môn trượt kỳ vọng (thấp hơn tốt hơn)")
    axis.set_ylabel("Xác suất tốt nghiệp đúng hạn (cao hơn tốt hơn)")
    axis.set_title(
        "Pareto chiến lược đăng ký — SIMULATED, không phải bằng chứng NTU"
    )
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8)
    fig.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_pareto.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_rates(summary: pd.DataFrame) -> Path:
    labels = [STRATEGY_LABELS.get(str(s), str(s)) for s in summary["strategy"]]
    positions = np.arange(len(summary))
    fig, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.bar(
        positions - 0.2,
        summary["graduation_rate"],
        width=0.4,
        label="Tốt nghiệp trong horizon",
        color="#4f81bd",
    )
    axis.bar(
        positions + 0.2,
        summary["on_time_rate"],
        width=0.4,
        label="Tốt nghiệp đúng hạn (<= HK8)",
        color="#c0504d",
    )
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=15, ha="right", fontsize=8)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Tỷ lệ")
    axis.set_title("Tỷ lệ tốt nghiệp theo chiến lược — SIMULATED")
    axis.grid(axis="y", alpha=0.3)
    axis.legend(fontsize=8)
    fig.tight_layout()
    path = OUTPUT_DIR / "monte_carlo_rates.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _parse_students(raw: str | None, curriculum: dict[str, Any]) -> list[str]:
    if raw:
        return [value.strip() for value in raw.split(",") if value.strip()]
    profiles = curriculum["profiles"]
    active = profiles[
        pd.to_numeric(profiles["credits_remaining"], errors="coerce").fillna(0) > 0
    ]
    return [str(value) for value in active["student_id"].tolist()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Số lượt mô phỏng mỗi sinh viên mỗi chiến lược (mặc định theo config).",
    )
    parser.add_argument(
        "--students",
        default=None,
        help="Danh sách student_id cách nhau bởi dấu phẩy; mặc định lấy persona còn tín chỉ.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curriculum = load_curriculum()
    bundle = load_bundle()
    rules = load_rules()
    monte_carlo_config = rules["monte_carlo"]
    runs = int(args.runs or monte_carlo_config["repetitions"]["value"])
    base_seed = int(monte_carlo_config["seed"]["value"])
    deadline = int(monte_carlo_config["completion_deadline_semesters"]["value"])
    if deadline != DEADLINE_SEMESTER:
        raise ValueError(
            f"Cấu hình deadline={deadline} khác hằng số {DEADLINE_SEMESTER}"
        )
    student_ids = _parse_students(args.students, curriculum)
    if not student_ids:
        raise ValueError("Không có persona còn tín chỉ để mô phỏng.")

    rows: list[dict[str, Any]] = []
    for student_index, student_id in enumerate(student_ids):
        profile, progress_rows = persona_payload(curriculum, student_id)
        assessment = assess_student(
            profile, progress_rows, curriculum, bundle, rules, use_ml=True
        )
        p_pass_m3 = float(assessment["p_pass_m3_prime"] or 0.0)
        p_dropout = float(assessment["p_dropout"] or 0.0)
        p_dropout_calibrated = assessment["p_dropout_calibrated"]
        profile_with_progress = dict(profile)
        profile_with_progress["_progress_rows"] = progress_rows
        for repetition in range(runs):
            run_seed = base_seed + student_index * 1_000_003 + repetition
            for strategy in STRATEGIES:
                rows.append(
                    _simulate_path(
                        strategy,
                        student_id=student_id,
                        profile=profile_with_progress,
                        curriculum=curriculum,
                        bundle=bundle,
                        rules=rules,
                        p_pass_m3=p_pass_m3,
                        p_dropout=p_dropout,
                        p_dropout_calibrated=p_dropout_calibrated,
                        run_seed=run_seed,
                    )
                )
        print(
            f"{student_id}: {runs} lượt × {len(STRATEGIES)} chiến lược "
            f"(p_pass={p_pass_m3:.3f}, p_dropout={p_dropout:.3f})"
        )

    runs_frame = pd.DataFrame(rows)
    runs_frame.insert(2, "run", runs_frame.groupby(
        ["student_id", "strategy"], sort=False
    ).cumcount())
    runs_frame.to_csv(OUTPUT_DIR / "monte_carlo_runs.csv", index=False)

    rng = np.random.default_rng(base_seed + 991)
    summary_rows = [
        _summarize(runs_frame[runs_frame["strategy"] == strategy], rng=rng, scope="ALL")
        for strategy in STRATEGIES
    ]
    summary = _add_pareto_frontier(pd.DataFrame(summary_rows))

    student_rows = []
    for student_id in student_ids:
        student_runs = runs_frame[runs_frame["student_id"] == student_id]
        for strategy in STRATEGIES:
            student_rows.append(
                _summarize(
                    student_runs[student_runs["strategy"] == strategy],
                    rng=rng,
                    scope=student_id,
                    student_id=student_id,
                )
            )
    by_student = _add_pareto_frontier(pd.DataFrame(student_rows), "student_id")

    paired = _paired_differences(runs_frame, rng=rng)
    summary.to_csv(OUTPUT_DIR / "monte_carlo_summary.csv", index=False)
    by_student.to_csv(
        OUTPUT_DIR / "monte_carlo_by_student.csv", index=False
    )
    paired.to_csv(
        OUTPUT_DIR / "monte_carlo_paired_differences.csv", index=False
    )
    pareto_plot = _plot_pareto(summary)
    rates_plot = _plot_rates(summary)

    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_label": (
            "SIMULATED curriculum + Bernoulli course outcomes; "
            "REAL prior = UCI-697 M3' pass rates; ASSUMPTION difficulty/load/retake"
        ),
        "not_ntu_evidence": True,
        "runs_per_student_per_strategy": runs,
        "students": student_ids,
        "strategies": {
            "ILP": "build_plans, risk-aware PuLP, 18-credit budget",
            "B1": "planned-semester + failed retakes, cap 18",
            "B2": "any eligible course, cap 18",
            "B3": "any eligible course, cap 15",
        },
        "pass_probability": (
            "p_pass = M3'(HK1 ability tier) × difficulty_factor(group) × "
            "load_multiplier × retake_multiplier; clipped to [0,1]"
        ),
        "load_multiplier": (
            "exp(-lambda × max(0, units - 6)), lambda=0.1, "
            "units=round(selected_credits / mean_credits_per_course)"
        ),
        "retake_multiplier": 1.0,
        "deadline_semester": deadline,
        "horizon_semester": HORIZON_SEMESTER,
        "dropout_assumption": (
            "P(Dropout) chỉ dùng cho cảnh báo/tier; không mô phỏng dropout "
            "như hazard từng học kỳ."
        ),
        "common_random_numbers": True,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "ci": "95% percentile bootstrap over runs",
        "pareto": "min mean_simulated_failures, max on_time_rate",
        "caveats": [
            "Đây là phân tích kịch bản, không phải bằng chứng từ dữ liệu NTU.",
            "M3' là tỷ lệ đạt gộp theo tầng năng lực từ UCI-697, không phải hiệu ứng nhân quả.",
            "Difficulty/load/retake là giả định; thay đổi giả định có thể đổi xếp hạng.",
            "Kết quả phụ thuộc CTĐT SIMULATED 48 học phần/128 tín chỉ.",
        ],
        "artifacts": {
            "runs": str((OUTPUT_DIR / "monte_carlo_runs.csv").relative_to(ROOT)),
            "summary": str((OUTPUT_DIR / "monte_carlo_summary.csv").relative_to(ROOT)),
            "by_student": str(
                (OUTPUT_DIR / "monte_carlo_by_student.csv").relative_to(ROOT)
            ),
            "paired": str(
                (OUTPUT_DIR / "monte_carlo_paired_differences.csv").relative_to(ROOT)
            ),
            "pareto_plot": str(pareto_plot.relative_to(ROOT)),
            "rates_plot": str(rates_plot.relative_to(ROOT)),
        },
    }
    (OUTPUT_DIR / "monte_carlo_meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    display = summary[
        [
            "strategy",
            "graduation_rate",
            "on_time_rate",
            "feasibility_rate",
            "mean_semesters_to_graduation",
            "mean_simulated_failures",
            "mean_credits_earned",
            "pareto_frontier",
        ]
    ]
    print(display.to_string(index=False))
    print(f"Đã ghi kết quả Monte Carlo vào {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
