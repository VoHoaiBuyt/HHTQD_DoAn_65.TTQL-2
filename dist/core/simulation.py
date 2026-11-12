"""Reproducible Monte Carlo policy simulations with paired uncertainty estimates."""

from __future__ import annotations

import copy
import importlib
import json
import math
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pulp
from scipy import stats

from core.curriculum import ROOT, read_yaml
from core.gpa import semester_gpa
from core.metrics import update_metrics
from core.optimizer import (
    DEFAULT_LAMBDA,
    LOAD_BUDGETS,
    RETAKE_POLICY,
    compute_unlock_values,
)
from core.rules import coreq_constraints
from core.run_dss import run_dss
from core.scenario_v2 import generate_scenario_rows


SIMULATION_CONFIG = read_yaml(ROOT / "config" / "monte_carlo_scenario.yaml")
_MC_CONFIG = SIMULATION_CONFIG["monte_carlo"]
DEFAULT_MC_SEED = int(_MC_CONFIG["seed"])
MAX_SEMESTERS = int(_MC_CONFIG["main_semester_horizon"])
MAX_ATTEMPTS_PER_COURSE = MAX_SEMESTERS + 2
BOOTSTRAP_REPLICATES = int(_MC_CONFIG["paired_bootstrap_replicates"])
CONFIDENCE_LEVEL = float(_MC_CONFIG["confidence_level"])
WARNING_STREAK_LIMIT = int(_MC_CONFIG["regulatory"]["consecutive_warning_limit"])
FIXED_PLANNER_LAMBDA = float(
    _MC_CONFIG["ilp_comparison"]["fixed_planner_lambda"]
)
BASELINE_POLICIES = tuple(
    str(value) for value in _MC_CONFIG["policies"] if str(value) != "ILP"
)
POLICIES = ("ILP-matched", "ILP-fixed", *BASELINE_POLICIES)
RESULTS_PATH = ROOT / "reports" / "generated" / "mc_results.csv"
PAIRWISE_PATH = ROOT / "reports" / "generated" / "mc_pairwise.csv"
PARETO_PATH = ROOT / "reports" / "generated" / "mc_pareto.csv"
RUNTIME_PATH = ROOT / "reports" / "generated" / "mc_runtime.json"
FIGURES_DIR = ROOT / "reports" / "figures"
_WORKER_CONTEXT: dict[str, Any] | None = None


def compute_p_pass(
    p_student: float,
    selected_load_credits: int,
    mean_credits: float,
    load_lambda: float,
    is_retake: bool,
    attempt_count: int,
) -> float:
    """Apply the scenario load and retake factors for a single attempt."""
    if not 0 <= p_student <= 1 or load_lambda < 0:
        raise ValueError("Invalid pass probability or load penalty")
    mean = max(float(mean_credits), 1e-9)
    units = math.floor(selected_load_credits / mean + 0.5)
    load_factor = math.exp(-load_lambda * max(0, units - 6))
    retake_multiplier = 1.0
    if is_retake:
        retake_multiplier = (
            float(RETAKE_POLICY["first_retake"])
            if attempt_count == 2
            else float(RETAKE_POLICY["repeated_attempt"])
        )
    return min(1.0, max(0.0, p_student * load_factor * retake_multiplier))


def common_random_matrix(seed: int, run_index: int, n_courses: int) -> np.ndarray:
    """Return the common U[semester, course, attempt] block for one replicate."""
    if run_index < 0 or n_courses < 1:
        raise ValueError("run_index must be non-negative and n_courses positive")
    rng = np.random.default_rng(np.random.SeedSequence([seed, run_index]))
    return rng.random((MAX_SEMESTERS, n_courses, MAX_ATTEMPTS_PER_COURSE))


def warning_streak(previous_count: int, w1: bool, w2: bool) -> tuple[int, bool]:
    """Return updated consecutive-warning count and third-warning expulsion flag."""
    if previous_count < 0:
        raise ValueError("previous_count must be non-negative")
    count = previous_count + 1 if w1 or w2 else 0
    return count, count > WARNING_STREAK_LIMIT


def _course_bundle(
    course_id: str,
    candidates: dict[str, dict[str, Any]],
    completed: set[str],
    required_peers: dict[str, set[str]],
) -> set[str] | None:
    bundle: set[str] = set()
    pending = [course_id]
    while pending:
        current = pending.pop()
        if current in completed or current in bundle:
            continue
        if current not in candidates:
            return None
        bundle.add(current)
        pending.extend(required_peers.get(current, set()) - completed - bundle)
    return bundle


def _bundle_fits(
    bundle: set[str],
    candidates: dict[str, dict[str, Any]],
    selected: set[str],
    selected_slots: set[str],
    credits_used: int,
    credit_cap: int,
) -> bool:
    additions = bundle - selected
    slots = [
        str(candidates[cid]["elective_slot"])
        for cid in additions
        if candidates[cid].get("elective_slot") is not None
    ]
    if len(slots) != len(set(slots)) or any(slot in selected_slots for slot in slots):
        return False
    return credits_used + sum(int(candidates[cid]["credits"]) for cid in additions) <= credit_cap


def select_policy_courses(
    policy_name: str,
    eligible_courses: list[dict[str, Any]],
    credit_limits: dict[str, Any],
    p_student: float,
    mean_credits: float,
    load_lambda: float,
    prerequisites: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    unlock_values: dict[str, float],
    ilp_cache: dict[Any, tuple[list[str], str]],
    scenario_budget: int | None = None,
    dss_result: dict[str, Any] | None = None,
    planner_lambda: float | None = None,
) -> tuple[list[str], str]:
    """Select a legal course set for ILP or one of the three baselines."""
    if policy_name not in {"ILP", "ILP-matched", "ILP-fixed", "B1", "B2", "B3"}:
        raise ValueError(f"Unknown policy name: {policy_name}")
    if not eligible_courses:
        return [], "no_eligible_courses"

    candidates = {str(row["course_id"]): dict(row) for row in eligible_courses}
    if len(candidates) != len(eligible_courses):
        raise ValueError("eligible_courses contains duplicate course IDs")
    max_raw = credit_limits.get("cmax")
    min_raw = credit_limits.get("cmin")
    if str(credit_limits.get("regime")) == "UNRESTRICTED_FINAL":
        cmax = sum(int(row["credits"]) for row in eligible_courses)
    else:
        cmax = 27 if max_raw in (None, "UNKNOWN") else int(max_raw)
    cmin = 0 if min_raw in (None, "UNKNOWN") else int(min_raw)
    if scenario_budget is not None:
        cmax = min(cmax, scenario_budget)
    if cmax < 0 or cmin < 0:
        raise ValueError("Credit limits must be non-negative")

    completed = {
        course_id
        for course_id, row in progress.items()
        if row.get("status") in {"completed", "in_progress"}
    }
    required_peers: dict[str, set[str]] = {}
    for dependent, peer in coreq_constraints(prerequisites):
        if dependent not in completed:
            required_peers.setdefault(dependent, set()).add(peer)

    forced_ids = {
        course_id for course_id, row in candidates.items() if row.get("must_register")
    }
    state_key = tuple(
        sorted(
            (course_id, str(row.get("status")), int(row.get("attempt_count", 0)))
            for course_id, row in progress.items()
        )
    )
    cache_key = (
        policy_name,
        state_key,
        tuple(sorted(candidates)),
        cmin,
        cmax,
        scenario_budget,
        float(load_lambda),
        float(p_student),
        None if planner_lambda is None else float(planner_lambda),
        tuple(LOAD_BUDGETS.get(str(credit_limits.get("regime")), ())),
    )
    if policy_name.startswith("ILP") and cache_key in ilp_cache:
        ids, cached_status = ilp_cache[cache_key]
        return list(ids), cached_status

    forced_order = sorted(
        forced_ids,
        key=lambda cid: (
            -float(unlock_values.get(cid, 0.0)),
            int(candidates[cid].get("planned_semester", 99)),
            cid,
        ),
    )
    selected: set[str] = set()
    selected_slots: set[str] = set()
    credits_used = 0
    forced_conflict = False

    def try_add(course_id: str, cap: int) -> bool:
        nonlocal credits_used
        bundle = _course_bundle(course_id, candidates, completed, required_peers)
        if bundle is None or not _bundle_fits(
            bundle, candidates, selected, selected_slots, credits_used, cap
        ):
            return False
        for cid in bundle - selected:
            selected.add(cid)
            credits_used += int(candidates[cid]["credits"])
            slot = candidates[cid].get("elective_slot")
            if slot is not None:
                selected_slots.add(str(slot))
        return True

    for course_id in forced_order:
        if not try_add(course_id, cmax):
            forced_conflict = True

    if policy_name.startswith("ILP"):
        if policy_name == "ILP-matched" and planner_lambda is not None and not math.isclose(
            float(planner_lambda), float(load_lambda)
        ):
            raise ValueError(
                "planner_lambda and simulation load_lambda must match for ILP-matched"
            )
        plans = (dss_result or {}).get("plans", [])
        if plans:
            plan = next(
                (row for row in plans if row.get("plan_type") == "balanced"),
                plans[0],
            )
            chosen = list(plan.get("selected_course_ids", []))
            status = str(plan.get("status", "optimal"))
        else:
            # A missing DSS plan is a data/state failure, not permission to invent one.
            status = "no_eligible_courses"
            chosen = []
        if forced_conflict:
            status = "regulatory_conflict"
        result = (chosen, status)
        ilp_cache[cache_key] = (list(chosen), status)
        return result

    if forced_conflict:
        # Keep the highest unlock-value forced retakes that fit; do not disguise the conflict.
        selected.clear()
        selected_slots.clear()
        credits_used = 0
        for course_id in forced_order:
            try_add(course_id, cmax)

    remaining = [row for cid, row in candidates.items() if cid not in selected]
    if policy_name == "B1":
        ordered = sorted(
            remaining,
            key=lambda row: (
                int(row.get("planned_semester", 99)),
                str(row["course_id"]),
            ),
        )
        target = cmax
    elif policy_name == "B3":
        target = min(cmax, max(cmin, 15))
        ordered = sorted(
            remaining,
            key=lambda row: (
                int(row.get("planned_semester", 99)),
                str(row["course_id"]),
            ),
        )
    else:
        target = cmax
        # The B2 MILP maximizes actual registered credits, with semester order as a tie-break.
        problem = pulp.LpProblem("baseline_b2_max_credits", pulp.LpMaximize)
        variables = {
            cid: problem.add_variable(f"x_{index}", cat="Binary")
            for index, cid in enumerate(candidates)
        }
        problem += pulp.lpSum(
            (
                int(row["credits"]) * 10000
                - int(row.get("planned_semester", 99))
            )
            * variables[cid]
            for cid, row in candidates.items()
        )
        problem += (
            pulp.lpSum(
                int(candidates[cid]["credits"]) * variable
                for cid, variable in variables.items()
            )
            <= cmax
        )
        for cid in selected:
            problem += variables[cid] == 1
        if forced_conflict:
            for cid in forced_ids - selected:
                problem += variables[cid] == 0
        for slot in {
            str(row["elective_slot"])
            for row in candidates.values()
            if row.get("elective_slot") is not None
        }:
            slot_ids = [
                cid
                for cid, row in candidates.items()
                if str(row.get("elective_slot")) == slot
            ]
            problem += pulp.lpSum(variables[cid] for cid in slot_ids) <= 1
        for dependent, peers in required_peers.items():
            if dependent not in candidates:
                continue
            for peer in peers:
                if peer in completed:
                    continue
                if peer not in candidates:
                    problem += variables[dependent] == 0
                else:
                    problem += variables[dependent] <= variables[peer]
        solver_result = problem.solve(pulp.HiGHS(msg=False))
        solver_status = getattr(
            getattr(solver_result, "status", None),
            "name",
            str(solver_result),
        )
        if solver_status.lower() != "optimal":
            return sorted(selected), "regulatory_conflict" if forced_conflict else "best_effort"
        chosen = {
            cid for cid, variable in variables.items() if float(variable.value() or 0) > 0.5
        }
        chosen_credits = sum(int(candidates[cid]["credits"]) for cid in chosen)
        if chosen_credits < cmin:
            return sorted(chosen), "regulatory_conflict" if forced_conflict else "best_effort"
        return sorted(chosen), "regulatory_conflict" if forced_conflict else "optimal"

    for row in ordered:
        cid = str(row["course_id"])
        # Forced retakes may already exceed the B3 target; never remove a forced course.
        if credits_used >= target:
            break
        try_add(cid, target)
    if credits_used < cmin and target < cmin:
        target = cmin
        for row in ordered:
            try_add(str(row["course_id"]), target)
    status = "regulatory_conflict" if forced_conflict else (
        "optimal" if credits_used >= cmin else "best_effort"
    )
    return sorted(selected), status


def _validate_selected(
    selected_ids: list[str],
    eligible: list[dict[str, Any]],
    progress: dict[str, dict[str, Any]],
    prerequisites: list[dict[str, Any]],
    limits: dict[str, Any],
) -> None:
    eligible_by_id = {str(row["course_id"]): row for row in eligible}
    if not set(selected_ids).issubset(eligible_by_id):
        raise ValueError("Policy selected a course outside the DSS eligible set")
    total = sum(int(eligible_by_id[cid]["credits"]) for cid in selected_ids)
    cmax = limits.get("cmax")
    if cmax not in (None, "UNKNOWN") and total > int(cmax):
        raise ValueError(f"Selected {total} credits above cmax={cmax}")
    slots = [
        str(eligible_by_id[cid]["elective_slot"])
        for cid in selected_ids
        if eligible_by_id[cid].get("elective_slot") is not None
    ]
    if len(slots) != len(set(slots)):
        raise ValueError("Policy selected multiple courses from an elective slot")
    selected = set(selected_ids)
    completed = {
        cid
        for cid, row in progress.items()
        if row.get("status") in {"completed", "in_progress"}
    }
    for relation in prerequisites:
        dependent = str(relation["course_id"])
        prerequisite = str(relation["prerequisite_id"])
        if dependent not in selected:
            continue
        if relation.get("type") == "tiên quyết" and prerequisite not in completed:
            raise ValueError(f"Selected {dependent} without completed prerequisite {prerequisite}")
        if relation.get("type") == "song hành" and prerequisite not in completed | selected:
            raise ValueError(f"Selected {dependent} without concurrent course {prerequisite}")


def simulate_student_trajectory(
    student_record: dict[str, Any],
    profile: dict[str, Any],
    policy_name: str,
    load_lambda: float,
    curriculum: dict[str, Any],
    rules_config: dict[str, Any],
    slot_credits: dict[str, int],
    random_matrix: np.ndarray,
    course_index_map: dict[str, int],
    ilp_cache: dict[Any, tuple[list[str], str]],
    planner_lambda: float | None = None,
) -> dict[str, Any]:
    """Simulate one student through the 16-term limit using a shared DSS evaluation."""
    courses = curriculum["courses"]
    prerequisites = curriculum["prerequisites"]
    course_by_id = {str(row["course_id"]): row for row in courses}
    program_ids = set(student_record["program_course_ids"])
    mean_credits = sum(int(course_by_id[cid]["credits"]) for cid in program_ids) / len(program_ids)
    progress = copy.deepcopy(student_record["progress"])
    progress = {
        cid: {
            "status": row["status"],
            "grade_10": row["grade_10"],
            "attempt_count": int(row.get("attempt_count", 0)),
            "semester_taken": row.get("semester_taken"),
        }
        for cid, row in progress.items()
    }
    start_semester = int(profile["last_completed_semester"]) + 1
    last_known_gpa = profile.get("previous_semester_gpa")
    p_student = float(profile["p_student_pass"])
    consecutive_warnings = 0
    graduated = False
    expelled = False
    graduation_semester = MAX_SEMESTERS
    failures = 0
    optimal_decisions = 0
    best_effort_decisions = 0
    conflict_decisions = 0
    no_eligible_decisions = 0
    decisions = 0
    credits_after_four_terms: int | None = None
    simulated_terms = 0
    term_gpa_by_semester: dict[int, float] = {}
    selected_credits_by_semester: dict[int, int] = {}
    regime_by_semester: dict[int, str] = {}
    constraint_satisfied_decisions = 0

    for semester in range(start_semester, MAX_SEMESTERS + 1):
        previous_semester_gpa = last_known_gpa
        profile_override = {
            "last_completed_semester": semester - 1,
            "target_semester": semester,
            "simulation_mode": "pass_fail",
            "grade_data_available": False,
            "graduation_outcomes": {
                "gdtc": True,
                "qpan": True,
                "foreign_language": True,
                "informatics": True,
            },
            "registration_previous_semester_gpa": previous_semester_gpa,
            "duration_main_semesters": semester - 1,
            "consecutive_warning_count": consecutive_warnings,
        }
        evaluation_options = {
            "profile_override": profile_override,
            "progress_override": progress,
            "target_semester": semester,
            "include_plans": False,
            "bypass_cache": False,
        }
        dss = run_dss(str(profile["student_id"]), evaluation_options)
        stats_row = dss["progress"]["stats"]
        if bool(stats_row["graduation_ready"]):
            graduated = True
            graduation_semester = semester - 1
            break
        eligible = dss["eligible"]
        limits = dss["credit_regime"]

        # Exempt the regulatory minimum when all outstanding program courses can be
        # registered together; this is the explicitly labeled final-term assumption.
        completed_ids = {
            cid for cid, row in progress.items() if row.get("status") == "completed"
        }
        outstanding = sorted(program_ids - completed_ids)
        eligible_ids = {str(row["course_id"]) for row in eligible}
        if outstanding and set(outstanding).issubset(eligible_ids):
            final_options = {
                **evaluation_options,
                "profile_override": {
                    **profile_override,
                    "registration_plan_course_ids": outstanding,
                },
            }
            final_dss = run_dss(str(profile["student_id"]), final_options)
            if final_dss["credit_regime"]["regime"] == "UNRESTRICTED_FINAL":
                dss = final_dss
                eligible = dss["eligible"]
                limits = dss["credit_regime"]

        active_slots = {
            str(course_by_id[cid].get("elective_slot"))
            for cid, row in progress.items()
            if cid in course_by_id
            and course_by_id[cid].get("elective_slot")
            and row.get("status") in {"completed", "in_progress"}
        }
        required_slots = set(
            curriculum["program_config"]["program"]["required_elective_slots"][
                str(profile["specialization"])
            ]
        )
        required_slots.add(str(curriculum["enrichment_config"]["graduation_slot"]["slot"]))
        unlock = compute_unlock_values(
            [str(row["course_id"]) for row in eligible],
            prerequisites,
            {cid: row["status"] for cid, row in progress.items()},
            credits_by_course={cid: int(row["credits"]) for cid, row in course_by_id.items()},
            elective_slots_by_course={
                cid: row.get("elective_slot") for cid, row in course_by_id.items()
            },
            missing_slots=required_slots - active_slots,
            slot_credits=slot_credits,
        )
        if policy_name.startswith("ILP"):
            plan_options = {
                **evaluation_options,
                "include_plans": True,
                "lambda": load_lambda if planner_lambda is None else planner_lambda,
            }
            if limits.get("regime") == "UNRESTRICTED_FINAL":
                plan_options["profile_override"] = {
                    **profile_override,
                    "registration_plan_course_ids": outstanding,
                }
            dss = run_dss(str(profile["student_id"]), plan_options)
        selected_ids, decision_status = select_policy_courses(
            policy_name,
            eligible,
            limits,
            p_student,
            mean_credits,
            load_lambda,
            prerequisites,
            progress,
            unlock,
            ilp_cache,
            dss_result=dss if policy_name.startswith("ILP") else None,
            planner_lambda=planner_lambda,
        )
        if not policy_name.startswith("ILP") and limits.get("regime") == "UNRESTRICTED_FINAL":
            # B1/B2/B3 are still evaluated against the official final-term exemption.
            pass
        _validate_selected(selected_ids, eligible, progress, prerequisites, limits)
        decisions += 1
        if decision_status == "optimal":
            optimal_decisions += 1
        elif decision_status == "regulatory_conflict":
            conflict_decisions += 1
        elif decision_status != "no_eligible_courses":
            best_effort_decisions += 1
        else:
            no_eligible_decisions += 1

        selected_credits = sum(int(course_by_id[cid]["credits"]) for cid in selected_ids)
        selected_credits_by_semester[semester] = selected_credits
        regime_by_semester[semester] = str(limits.get("regime", "UNKNOWN"))
        forced_ids = {
            str(row["course_id"]) for row in eligible if row.get("must_register")
        }
        selected_set = set(selected_ids)
        hard_limit_ok = (
            limits.get("cmax") in (None, "UNKNOWN")
            or selected_credits <= int(limits["cmax"])
        ) and (
            limits.get("cmin") in (None, "UNKNOWN")
            or selected_credits >= int(limits["cmin"])
            or limits.get("regime") == "UNRESTRICTED_FINAL"
        )
        if hard_limit_ok and forced_ids.issubset(selected_set):
            constraint_satisfied_decisions += 1
        failed_term_credits = 0
        for cid in selected_ids:
            course_index = course_index_map[cid]
            old_attempts = int(progress[cid].get("attempt_count", 0))
            next_attempt = old_attempts + 1
            probability = compute_p_pass(
                p_student,
                selected_credits,
                mean_credits,
                load_lambda,
                progress[cid]["status"] == "failed",
                next_attempt,
            )
            draw = float(random_matrix[semester - 1, course_index, min(old_attempts, MAX_ATTEMPTS_PER_COURSE - 1)])
            progress[cid]["attempt_count"] = next_attempt
            progress[cid]["semester_taken"] = semester
            if draw < probability:
                progress[cid]["status"] = "completed"
                progress[cid]["grade_10"] = float(
                    _MC_CONFIG["pass_fail_proxy"][
                        "passed_course_grade_for_graduation_gpa"
                    ]
                )
            else:
                progress[cid]["status"] = "failed"
                progress[cid]["grade_10"] = float(
                    _MC_CONFIG["pass_fail_proxy"][
                        "failed_course_grade_for_transcript_state"
                    ]
                )
                failed_term_credits += int(course_by_id[cid]["credits"])
                failures += 1
        term_gpa = semester_gpa(
            courses,
            progress,
            semester,
            rules_config["regulation"],
        )
        if term_gpa is not None:
            term_gpa_by_semester[semester] = term_gpa
            last_known_gpa = term_gpa
        simulated_terms += 1

        # This is deliberately pass/fail only; W3/W4 are not evaluated here.
        debt_credits = sum(
            int(course_by_id[cid]["credits"])
            for cid, row in progress.items()
            if cid in program_ids and row.get("status") == "failed"
        )
        w1 = debt_credits > 24
        w2 = selected_credits > 0 and failed_term_credits / selected_credits > 0.5
        consecutive_warnings, expelled_now = warning_streak(consecutive_warnings, w1, w2)
        if expelled_now:
            expelled = True
            break

        accumulated = sum(
            int(course_by_id[cid]["credits"])
            for cid, row in progress.items()
            if cid in program_ids and row.get("status") == "completed"
        )
        if simulated_terms == 4:
            credits_after_four_terms = accumulated

    final_completed = {
        cid for cid, row in progress.items() if row.get("status") == "completed"
    }
    final_credits = sum(
        int(course_by_id[cid]["credits"])
        for cid in final_completed
        if cid in program_ids and bool(course_by_id[cid].get("counts_toward_total", True))
    )
    if not graduated and not expelled and start_semester <= MAX_SEMESTERS:
        # Completing the 16th main term without graduation exceeds the regulation limit.
        expelled = True
    if credits_after_four_terms is None:
        credits_after_four_terms = final_credits
    if not graduated and not expelled and start_semester <= MAX_SEMESTERS:
        final_profile = {
            "last_completed_semester": MAX_SEMESTERS,
            "target_semester": MAX_SEMESTERS,
            "simulation_mode": "pass_fail",
            "grade_data_available": False,
            "graduation_outcomes": {
                "gdtc": True,
                "qpan": True,
                "foreign_language": True,
                "informatics": True,
            },
            "registration_previous_semester_gpa": last_known_gpa,
            "duration_main_semesters": MAX_SEMESTERS,
            "consecutive_warning_count": consecutive_warnings,
        }
        final_dss = run_dss(
            str(profile["student_id"]),
            {
                "profile_override": final_profile,
                "progress_override": progress,
                "target_semester": MAX_SEMESTERS,
                "include_plans": False,
            },
        )
        if final_dss["progress"]["stats"]["graduation_ready"]:
            graduated = True
            graduation_semester = MAX_SEMESTERS
    return {
        "graduated_on_time": int(graduated and graduation_semester <= 8),
        "graduated_16": int(graduated and graduation_semester <= MAX_SEMESTERS),
        "graduation_semester": min(MAX_SEMESTERS, graduation_semester),
        "total_failures": failures,
        "credits_accumulated_4": credits_after_four_terms,
        "credits_accumulated_final": final_credits,
        "expelled_regulatory": int(expelled),
        "forced_withdrawal": int(expelled),
        "feasible_ratio": optimal_decisions / decisions if decisions else 1.0,
        "constraint_satisfied_ratio": (
            constraint_satisfied_decisions / decisions if decisions else 1.0
        ),
        "constraint_satisfied_decisions": constraint_satisfied_decisions,
        "best_effort_ratio": best_effort_decisions / decisions if decisions else 0.0,
        "regulatory_conflict_ratio": conflict_decisions / decisions if decisions else 0.0,
        "no_eligible_ratio": no_eligible_decisions / decisions if decisions else 0.0,
        "selected_load_mean": (
            float(np.mean(list(selected_credits_by_semester.values())))
            if selected_credits_by_semester
            else 0.0
        ),
        "normal_semesters": sum(
            value == "NORMAL" for value in regime_by_semester.values()
        ),
        "weak_semesters": sum(
            value == "WEAK_OR_POOR" for value in regime_by_semester.values()
        ),
        **{
            f"selected_credits_semester_{semester}": selected_credits_by_semester.get(
                semester, 0
            )
            for semester in range(1, MAX_SEMESTERS + 1)
        },
        "optimal_decisions": optimal_decisions,
        "best_effort_decisions": best_effort_decisions,
        "regulatory_conflict_decisions": conflict_decisions,
        "no_eligible_decisions": no_eligible_decisions,
        "decisions": decisions,
    }


def wilson_score_interval(
    successes: int,
    total: int,
    confidence: float = CONFIDENCE_LEVEL,
) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    z = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))
    p = successes / total
    denominator = 1.0 + z**2 / total
    centre = (p + z**2 / (2.0 * total)) / denominator
    margin = (z / denominator) * math.sqrt(
        p * (1.0 - p) / total + z**2 / (4.0 * total**2)
    )
    lower = 0.0 if successes == 0 else max(0.0, centre - margin)
    upper = 1.0 if successes == total else min(1.0, centre + margin)
    return lower, upper


def mean_t_interval(
    values: np.ndarray,
    confidence: float = CONFIDENCE_LEVEL,
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if not len(values):
        return 0.0, 0.0
    if len(values) < 2:
        return float(values[0]), float(values[0])
    half_width = float(stats.sem(values)) * float(
        stats.t.ppf((1 + confidence) / 2, len(values) - 1)
    )
    return float(np.mean(values) - half_width), float(np.mean(values) + half_width)


def build_graduation_histogram(
    raw: dict[tuple[str, str, float, str], np.ndarray],
    student_ids: list[str],
    policies: tuple[str, ...],
    lambdas: tuple[float, ...],
    n_total: int,
) -> pd.DataFrame:
    if n_total < 1:
        raise ValueError("n_total must be positive")
    rows: list[dict[str, Any]] = []
    for student_id in student_ids:
        for policy in policies:
            for load_lambda in lambdas:
                graduated = np.asarray(
                    raw[(student_id, policy, float(load_lambda), "graduated_16")],
                    dtype=bool,
                )
                forced = np.asarray(
                    raw[(student_id, policy, float(load_lambda), "forced_withdrawal")],
                    dtype=bool,
                )
                semester = np.asarray(
                    raw[(student_id, policy, float(load_lambda), "graduation_semester")],
                    dtype=float,
                )
                if not (len(graduated) == len(forced) == len(semester) == n_total):
                    raise ValueError("graduation histogram arrays must match n_total")
                bins: dict[tuple[str, int | None], int] = {}
                for did_graduate, was_forced, grad_semester in zip(
                    graduated, forced, semester, strict=True
                ):
                    if did_graduate:
                        key = ("graduated", int(grad_semester))
                    elif was_forced:
                        key = ("forced_withdrawal", None)
                    else:
                        key = ("not_finished_16", None)
                    bins[key] = bins.get(key, 0) + 1
                if sum(bins.values()) != n_total:
                    raise ValueError("graduation histogram does not partition all runs")
                for (outcome, grad_semester), count in bins.items():
                    rows.append(
                        {
                            "student_id": student_id,
                            "policy": policy,
                            "lambda": float(load_lambda),
                            "outcome": outcome,
                            "semester": grad_semester,
                            "count": count,
                            "n_total": n_total,
                            "source_label": "SCENARIO / GIẢ ĐỊNH (Monte Carlo)",
                        }
                    )
    return pd.DataFrame(
        rows,
        columns=[
            "student_id",
            "policy",
            "lambda",
            "outcome",
            "semester",
            "count",
            "n_total",
            "source_label",
        ],
    )


def validate_graduation_histogram(
    histogram: pd.DataFrame,
    results: pd.DataFrame,
) -> None:
    if histogram.empty and not results.empty:
        raise ValueError("graduation histogram is empty")
    for _, result in results.iterrows():
        group = histogram
        for column in ("student_id", "policy", "lambda"):
            group = group.loc[group[column].eq(result[column])]
        if int(group["count"].sum()) != int(result["n_runs"]):
            raise ValueError("graduation histogram does not partition all runs")
        on_time = group.loc[
            group["outcome"].eq("graduated")
            & pd.to_numeric(group["semester"], errors="coerce").le(8),
            "count",
        ].sum() / int(result["n_runs"])
        if not math.isclose(
            float(on_time), float(result["p_graduated_on_time"]), abs_tol=1e-12
        ):
            raise ValueError("graduation histogram probability mismatch")


def paired_bootstrap_difference(
    a_values: np.ndarray,
    b_values: np.ndarray,
    n_boot: int = BOOTSTRAP_REPLICATES,
    confidence: float = CONFIDENCE_LEVEL,
    seed: int = DEFAULT_MC_SEED,
) -> tuple[float, float, float]:
    a_values = np.asarray(a_values, dtype=float)
    b_values = np.asarray(b_values, dtype=float)
    if a_values.shape != b_values.shape or not len(a_values):
        raise ValueError("Paired bootstrap arrays must be non-empty and same length")
    differences = a_values - b_values
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(differences), size=(n_boot, len(differences)))
    means = np.mean(differences[indices], axis=1)
    alpha = (1 - confidence) / 2
    return (
        float(np.mean(differences)),
        float(np.quantile(means, alpha)),
        float(np.quantile(means, 1 - alpha)),
    )


def evaluate_pareto_dominance(
    pairwise_diffs: dict[str, tuple[float, float, float]],
    higher_is_better_keys: list[str],
    lower_is_better_keys: list[str],
) -> str:
    significantly_worse = False
    significantly_better = False
    for key in higher_is_better_keys:
        if key not in pairwise_diffs:
            continue
        _, low, high = pairwise_diffs[key]
        significantly_better |= low > 0
        significantly_worse |= high < 0
    for key in lower_is_better_keys:
        if key not in pairwise_diffs:
            continue
        _, low, high = pairwise_diffs[key]
        significantly_better |= high < 0
        significantly_worse |= low > 0
    if significantly_worse and significantly_better:
        return "đánh đổi"
    if significantly_better:
        return "ILP vượt trội"
    if significantly_worse:
        return "ILP bị vượt trội"
    return "chưa phân biệt"


_METRICS = {
    "graduated_on_time": "p_graduated_on_time",
    "graduated_16": "p_graduated_16",
    "graduation_semester": "mean_graduation_semester",
    "total_failures": "expected_failed_courses",
    "credits_accumulated_4": "credits_accumulated_4_sem",
    "credits_accumulated_final": "credits_accumulated_final",
    "expelled_regulatory": "p_expelled_regulatory",
    "feasible_ratio": "feasible_decision_ratio",
    "best_effort_ratio": "best_effort_decision_ratio",
    "regulatory_conflict_ratio": "regulatory_conflict_decision_ratio",
    "no_eligible_ratio": "no_eligible_decision_ratio",
    "constraint_satisfied_ratio": "constraint_satisfied_ratio",
    "selected_load_mean": "selected_load_mean",
    "normal_semesters": "normal_semesters",
    "weak_semesters": "weak_semesters",
    **{
        f"selected_credits_semester_{semester}": f"selected_credits_semester_{semester}"
        for semester in range(1, MAX_SEMESTERS + 1)
    },
}
_PROPORTIONS = {
    "graduated_on_time",
    "graduated_16",
    "expelled_regulatory",
    "feasible_ratio",
    "best_effort_ratio",
    "regulatory_conflict_ratio",
    "no_eligible_ratio",
    "constraint_satisfied_ratio",
}


def _init_worker(context: dict[str, Any]) -> None:
    global _WORKER_CONTEXT
    _WORKER_CONTEXT = context
    dss_module = importlib.import_module("core.run_dss")

    dss_module._DATA_CONTEXT = {
        "profiles": context["profiles"],
        "metadata": context["metadata"],
        "curriculum": context["metadata"]["curriculum"],
        "rules_config": context["metadata"]["rules_config"],
    }
    dss_module._DSS_CACHE.clear()
    dss_module._RISK_CACHE.clear()


def _simulate_cell(
    task: tuple[str, str, float, int, int],
) -> tuple[str, str, float, dict[str, np.ndarray]]:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("Monte Carlo worker was not initialized")
    student_id, policy, load_lambda, n_runs, seed = task
    context = _WORKER_CONTEXT
    profile = context["profiles"][student_id]
    record = context["metadata"]["scenario_records"][student_id]
    courses = context["metadata"]["curriculum"]["courses"]
    course_index = {str(row["course_id"]): index for index, row in enumerate(courses)}
    arrays: dict[str, list[float]] = {}
    cache: dict[Any, tuple[list[str], str]] = {}
    n_courses = len(courses)
    for run_index in range(n_runs):
        random_matrix = common_random_matrix(seed, run_index, n_courses)
        planner_lambda = (
            load_lambda
            if policy == "ILP-matched"
            else FIXED_PLANNER_LAMBDA
            if policy == "ILP-fixed"
            else None
        )
        result = simulate_student_trajectory(
            record,
            profile,
            policy,
            load_lambda,
            context["metadata"]["curriculum"],
            context["metadata"]["rules_config"],
            context["metadata"]["slot_credits"],
            random_matrix,
            course_index,
            cache,
            planner_lambda=planner_lambda,
        )
        for key, value in result.items():
            arrays.setdefault(key, []).append(float(value))
    return student_id, policy, load_lambda, {
        key: np.asarray(values, dtype=float) for key, values in arrays.items()
    }


def run_monte_carlo_simulation(
    n_runs: int = 1000,
    lambdas: tuple[float, ...] = (0.1,),
    policies: tuple[str, ...] = POLICIES,
    seed: int = DEFAULT_MC_SEED,
    student_ids: list[str] | None = None,
    n_workers: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run paired policies with a common, deterministic uniform matrix per replicate."""
    if n_runs < 1:
        raise ValueError("n_runs must be positive")
    if not lambdas or any(float(value) < 0 for value in lambdas):
        raise ValueError("lambdas must be non-empty and non-negative")
    profiles_list, _, metadata = generate_scenario_rows()
    profiles = {str(row["student_id"]): row for row in profiles_list}
    targets = list(student_ids) if student_ids is not None else sorted(profiles)
    unknown = sorted(set(targets) - set(profiles))
    if unknown:
        raise ValueError(f"Unknown student IDs: {unknown}")
    context = {"profiles": profiles, "metadata": metadata}
    tasks = [
        (sid, policy, float(load_lambda), n_runs, seed)
        for load_lambda in lambdas
        for sid in targets
        for policy in policies
    ]
    workers = n_workers or min(4, os.cpu_count() or 1, len(tasks))
    workers = max(1, min(int(workers), len(tasks)))
    if workers == 1:
        _init_worker(context)
        cells = [_simulate_cell(task) for task in tasks]
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=mp.get_context("spawn"),
            initializer=_init_worker,
            initargs=(context,),
        ) as executor:
            cells = list(executor.map(_simulate_cell, tasks, chunksize=1))

    profile_map = profiles
    raw: dict[tuple[str, str, float, str], np.ndarray] = {}
    for sid, policy, load_lambda, values in cells:
        for metric, array in values.items():
            raw[(sid, policy, load_lambda, metric)] = array

    results: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    pareto: list[dict[str, Any]] = []
    for load_lambda in lambdas:
        for sid in targets:
            persona = str(profile_map[sid]["persona"])
            for policy in policies:
                data = {
                    metric: raw[(sid, policy, float(load_lambda), metric)]
                    for metric in _METRICS
                }
                decisions = int(np.sum(raw[(sid, policy, float(load_lambda), "decisions")]))
                row: dict[str, Any] = {
                    "student_id": sid,
                    "persona": persona,
                    "policy": policy,
                    "lambda": float(load_lambda),
                    "planner_lambda": (
                        float(load_lambda)
                        if policy == "ILP-matched"
                        else FIXED_PLANNER_LAMBDA
                        if policy == "ILP-fixed"
                        else None
                    ),
                    "n_runs": n_runs,
                    "source_label": "SCENARIO",
                    "probability_scope": "GIẢ ĐỊNH (Monte Carlo; M3-prime/UCI-697 is exploratory, not NTU-validated)",
                    "w3_w4_scope": "not modeled (pass/fail simulation has no grades)",
                    "dropout_hazard": "off; M3-prime already includes later dropout",
                    "decision_count_mean": float(
                        np.mean(raw[(sid, policy, float(load_lambda), "decisions")])
                    ),
                    "optimal_decisions": int(
                        np.sum(raw[(sid, policy, float(load_lambda), "optimal_decisions")])
                    ),
                    "best_effort_decisions": int(
                        np.sum(raw[(sid, policy, float(load_lambda), "best_effort_decisions")])
                    ),
                    "regulatory_conflict_decisions": int(
                        np.sum(raw[(sid, policy, float(load_lambda), "regulatory_conflict_decisions")])
                    ),
                    "no_eligible_decisions": int(
                        np.sum(raw[(sid, policy, float(load_lambda), "no_eligible_decisions")])
                    ),
                    "constraint_satisfied_decisions": int(
                        np.sum(
                            raw[(sid, policy, float(load_lambda), "constraint_satisfied_decisions")]
                        )
                    ),
                }
                for metric, column in _METRICS.items():
                    values = data[metric]
                    average = float(np.mean(values))
                    row[column] = average
                    if metric in _PROPORTIONS:
                        if metric == "feasible_ratio" and decisions:
                            successes = row["optimal_decisions"]
                            total = decisions
                        elif metric == "best_effort_ratio" and decisions:
                            successes = row["best_effort_decisions"]
                            total = decisions
                        elif metric == "regulatory_conflict_ratio" and decisions:
                            successes = row["regulatory_conflict_decisions"]
                            total = decisions
                        elif metric == "no_eligible_ratio" and decisions:
                            successes = row["no_eligible_decisions"]
                            total = decisions
                        elif metric == "constraint_satisfied_ratio" and decisions:
                            successes = row["constraint_satisfied_decisions"]
                            total = decisions
                        else:
                            successes = int(np.sum(values))
                            total = n_runs
                        row[column] = successes / total if total else 0.0
                        low, high = wilson_score_interval(successes, total)
                        row[f"ci_{column}_lower"] = low
                        row[f"ci_{column}_upper"] = high
                    else:
                        low, high = mean_t_interval(values)
                        row[f"ci_{column}_lower"] = low
                        row[f"ci_{column}_upper"] = high
                results.append(row)

            if "ILP-matched" not in policies:
                continue
            comparisons = [
                (ilp_policy, baseline)
                for ilp_policy in ("ILP-matched",)
                for baseline in ("B1", "B2", "B3", "ILP-fixed")
                if baseline in policies
            ]
            for ilp_policy, baseline in comparisons:
                differences: dict[str, tuple[float, float, float]] = {}
                pair_row: dict[str, Any] = {
                    "student_id": sid,
                    "persona": persona,
                    "comparison": f"{ilp_policy} - {baseline}",
                    "policy_a": ilp_policy,
                    "policy_b": baseline,
                    "lambda": float(load_lambda),
                    "n_runs": n_runs,
                    "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                }
                for metric in _METRICS:
                    a_values = raw[(sid, ilp_policy, float(load_lambda), metric)]
                    b_values = raw[(sid, baseline, float(load_lambda), metric)]
                    stable_offset = sum(
                        (index + 1) * ord(char)
                        for index, char in enumerate(f"{sid}|{ilp_policy}|{baseline}|{load_lambda}|{metric}")
                    )
                    difference = paired_bootstrap_difference(
                        a_values,
                        b_values,
                        n_boot=BOOTSTRAP_REPLICATES,
                        seed=seed + stable_offset,
                    )
                    differences[metric] = difference
                    column = _METRICS[metric]
                    pair_row[f"diff_{column}"] = difference[0]
                    pair_row[f"ci_{column}_lower"] = difference[1]
                    pair_row[f"ci_{column}_upper"] = difference[2]
                pairs.append(pair_row)
                pareto.append(
                    {
                        "student_id": sid,
                        "persona": persona,
                        "policy_a": ilp_policy,
                        "policy_b": baseline,
                        "lambda": float(load_lambda),
                        "dominance": evaluate_pareto_dominance(
                            differences,
                            ["graduated_on_time", "graduated_16", "credits_accumulated_4"],
                            ["graduation_semester", "total_failures"],
                        ),
                        "interpretation": (
                            "Pareto dùng 5 chỉ tiêu chính; constraint_satisfied và solver status "
                            "được báo riêng, không dùng làm tiêu chí Pareto."
                        ),
                    }
                )
    results_frame = pd.DataFrame(results)
    histogram = build_graduation_histogram(
        raw,
        targets,
        policies,
        tuple(float(value) for value in lambdas),
        n_runs,
    )
    validate_graduation_histogram(histogram, results_frame)
    results_frame.attrs["graduation_histogram"] = histogram
    return results_frame, pd.DataFrame(pairs), pd.DataFrame(pareto)


def write_monte_carlo_outputs(
    results: pd.DataFrame,
    pairwise: pd.DataFrame,
    pareto: pd.DataFrame,
    *,
    elapsed_seconds: float,
    seed: int,
    n_workers: int,
) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    pareto.to_csv(PARETO_PATH, index=False, encoding="utf-8-sig")
    histogram = results.attrs.get("graduation_histogram")
    if not isinstance(histogram, pd.DataFrame):
        raise ValueError("Monte Carlo results are missing the per-run graduation histogram")
    histogram.to_csv(
        ROOT / "reports" / "generated" / "mc_grad_hist.csv",
        index=False,
        encoding="utf-8-sig",
    )
    runtime = {
        "status": "PASS",
        "seed": seed,
        "n_runs": int(results["n_runs"].max()) if not results.empty else 0,
        "n_profiles": int(results["student_id"].nunique()) if not results.empty else 0,
        "policies": sorted(results["policy"].unique().tolist()) if not results.empty else [],
        "lambdas": sorted(float(value) for value in results["lambda"].unique()) if not results.empty else [],
        "n_workers": n_workers,
        "elapsed_seconds": elapsed_seconds,
        "mean_seconds_per_profile_policy_lambda": (
            elapsed_seconds / max(1, len(results))
        ),
        "scope": "SCENARIO only; model probabilities are exploratory and not evidence of NTU effectiveness",
        "limitations": [
            "Pass/fail outcomes are independent between courses.",
            "No explicit dropout hazard; the M3-prime baseline includes later dropout.",
            "Future term credit regime is recomputed from credit-weighted pass=7.0/fail=4.0 proxy grades (GIẢ ĐỊNH).",
            "Graduation GPA uses nominal 7.0 for simulated passes; this is a scenario proxy, not observed performance.",
            "Learning outcomes are assumed achieved (GIẢ ĐỊNH).",
            "Summer terms and class availability are not modeled.",
        ],
    }
    RUNTIME_PATH.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_outputs(results, histogram)
    update_metrics(
        {
            "monte_carlo": {
                "status": "PASS",
                "seed": seed,
                "runs_per_profile_policy_lambda": runtime["n_runs"],
                "profiles": runtime["n_profiles"],
                "policies": runtime["policies"],
                "lambdas": runtime["lambdas"],
                "elapsed_seconds": elapsed_seconds,
                "results_rows": len(results),
                "pairwise_rows": len(pairwise),
                "pareto_rows": len(pareto),
            }
        }
    )


def _plot_outputs(results: pd.DataFrame, histogram: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    if results.empty:
        raise ValueError("Cannot plot empty Monte Carlo results")
    lambda_mid = min(results["lambda"].unique(), key=lambda value: abs(value - DEFAULT_LAMBDA))
    subset = results[results["lambda"] == lambda_mid]
    histogram = histogram.loc[histogram["lambda"].eq(lambda_mid)]
    figure, axis = plt.subplots(figsize=(8, 5))
    graduated = histogram.loc[
        histogram["outcome"].eq("graduated")
        & pd.to_numeric(histogram["semester"], errors="coerce").notna()
    ]
    for policy in POLICIES:
        policy_histogram = graduated.loc[graduated["policy"].eq(policy)]
        if not policy_histogram.empty:
            counts = policy_histogram.groupby("semester")["count"].sum()
            total_runs = int(subset.loc[subset["policy"].eq(policy), "n_runs"].sum())
            axis.plot(
                counts.index.astype(int),
                counts.to_numpy() / total_runs,
                marker="o",
                label=policy,
            )
    axis.set(
        xlabel="Main semester of graduation",
        ylabel="Probability per simulated run",
        xlim=(1, MAX_SEMESTERS),
    )
    axis.legend()
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "mc_graduation_distribution.png", dpi=150)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5))
    for policy in POLICIES:
        policy_rows = subset[subset["policy"] == policy]
        axis.errorbar(
            policy_rows["p_graduated_16"],
            policy_rows["expected_failed_courses"],
            xerr=[
                np.maximum(
                    0.0,
                    policy_rows["p_graduated_16"]
                    - policy_rows["ci_p_graduated_16_lower"],
                ),
                np.maximum(
                    0.0,
                    policy_rows["ci_p_graduated_16_upper"]
                    - policy_rows["p_graduated_16"],
                ),
            ],
            yerr=[
                np.maximum(
                    0.0,
                    policy_rows["expected_failed_courses"]
                    - policy_rows["ci_expected_failed_courses_lower"],
                ),
                np.maximum(
                    0.0,
                    policy_rows["ci_expected_failed_courses_upper"]
                    - policy_rows["expected_failed_courses"],
                ),
            ],
            fmt="o",
            label=policy,
            alpha=0.75,
        )
    axis.set(xlabel="P(graduate by 16 terms)", ylabel="Expected failed attempts")
    axis.legend()
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "mc_confidence_intervals.png", dpi=150)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5))
    for student_id, profile_rows in subset.groupby("student_id"):
        points = profile_rows[
            ["policy", "p_graduated_16", "expected_failed_courses"]
        ].to_dict("records")
        frontier = [
            point
            for point in points
            if not any(
                other["p_graduated_16"] >= point["p_graduated_16"]
                and other["expected_failed_courses"] <= point["expected_failed_courses"]
                and (
                    other["p_graduated_16"] > point["p_graduated_16"]
                    or other["expected_failed_courses"] < point["expected_failed_courses"]
                )
                for other in points
            )
        ]
        frontier.sort(key=lambda point: point["p_graduated_16"])
        if frontier:
            axis.plot(
                [point["p_graduated_16"] for point in frontier],
                [point["expected_failed_courses"] for point in frontier],
                marker="o",
                alpha=0.65,
                label=student_id,
            )
    axis.set(
        xlabel="P(graduate by 16 terms; maximize)",
        ylabel="Expected failed attempts (minimize)",
        title="Per-profile two-metric Pareto projection",
    )
    axis.legend()
    figure.tight_layout()
    figure.savefig(FIGURES_DIR / "mc_pareto.png", dpi=150)
    plt.close(figure)


def run_and_write_monte_carlo(
    n_runs: int = 1000,
    lambdas: tuple[float, ...] = (0.1,),
    *,
    seed: int = DEFAULT_MC_SEED,
    student_ids: list[str] | None = None,
    n_workers: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    start = time.perf_counter()
    results, pairwise, pareto = run_monte_carlo_simulation(
        n_runs=n_runs,
        lambdas=lambdas,
        seed=seed,
        student_ids=student_ids,
        n_workers=n_workers,
    )
    elapsed = time.perf_counter() - start
    workers = n_workers or min(4, os.cpu_count() or 1)
    write_monte_carlo_outputs(
        results, pairwise, pareto,
        elapsed_seconds=elapsed, seed=seed, n_workers=workers,
    )
    return results, pairwise, pareto, elapsed
