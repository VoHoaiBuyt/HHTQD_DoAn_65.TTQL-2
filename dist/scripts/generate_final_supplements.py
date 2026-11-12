from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from app.risk_labels import PLAN_DISPLAY_LABELS, RISK_THRESHOLDS, risk_level
from core.run_dss import _context, run_dss


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
SCENARIOS_PATH = ROOT / "data" / "scenarios" / "student_profile_v2.csv"
MC_RESULTS_PATH = GENERATED / "mc_results.csv"
MC_PAIRWISE_PATH = GENERATED / "mc_pairwise.csv"
MC_PARETO_PATH = GENERATED / "mc_pareto.csv"
OPTIMIZER_CONFIG_PATH = ROOT / "config" / "optimizer_scenario_v2.yaml"
MC_CONFIG_PATH = ROOT / "config" / "monte_carlo_scenario.yaml"

BUDGET_FIELDS = (
    "student_id",
    "persona",
    "regime",
    "budget_mode",
    "scenario_budget",
    "lambda",
    "plan_type",
    "display_label",
    "status",
    "selected_course_ids",
    "selected_credits",
    "expected_credits_passed",
    "expected_failed_courses",
    "p_at_least_one_failure",
    "p_warning_W1",
    "p_warning_W2",
    "retake_credits_total",
    "estimated_graduation_semester",
    "graduation_estimate_source",
    "risk_level",
    "advisor_recommendation",
    "source_label",
)

EXPLANATION_FIELDS = (
    "section",
    "student_id",
    "policy",
    "lambda",
    "metric",
    "value",
    "ci95_lower",
    "ci95_upper",
    "pareto_label",
    "explanation",
    "source_files",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _profile_budget_mode(credit_regime: dict[str, Any], config: dict[str, Any]) -> tuple[str, list[int]]:
    if credit_regime.get("cmin") == 15 and credit_regime.get("cmax") == 27:
        return "15–27", [int(value) for value in config["scenario_budgets"]["NORMAL"]]
    return "12–18", [int(value) for value in config["scenario_budgets"]["WEAK_OR_POOR"]]


def _plan_outcome_signature(plan: dict[str, Any]) -> tuple[Any, ...]:
    fields = (
        "status",
        "selected_course_ids",
        "selected_credits",
        "expected_credits_passed",
        "expected_failed_courses",
        "p_at_least_one_failure",
        "p_warning_W1",
        "p_warning_W2",
        "retake_credits_total",
        "estimated_graduation_semester",
        "risk_level",
    )
    signature: list[Any] = []
    for field in fields:
        value = plan.get(field)
        if isinstance(value, float):
            signature.append(round(value, 12))
        elif isinstance(value, list):
            signature.append(tuple(value))
        else:
            signature.append(value)
    return tuple(signature)


def _budget_sweep_signature(rows: list[dict[str, Any]]) -> tuple[Any, ...]:
    ordered = sorted(rows, key=lambda row: (int(row["scenario_budget"]), row["plan_type"]))
    return tuple(
        (
            int(row["scenario_budget"]),
            row["plan_type"],
            row["status"],
            row["selected_course_ids"],
            round(float(row["selected_credits"]), 12),
            round(float(row["expected_credits_passed"]), 12),
            round(float(row["expected_failed_courses"]), 12),
            round(float(row["p_at_least_one_failure"]), 12),
            round(float(row["p_warning_W1"]), 12),
            round(float(row["p_warning_W2"]), 12),
            (
                round(float(row["retake_credits_total"]), 12)
                if row["retake_credits_total"] != "UNKNOWN"
                else "UNKNOWN"
            ),
            row["estimated_graduation_semester"],
            row["risk_level"],
        )
        for row in ordered
    )


def build_budget_outputs() -> dict[str, Any]:
    optimizer = _read_yaml(OPTIMIZER_CONFIG_PATH)["optimizer"]
    scenarios = _read_csv(SCENARIOS_PATH)
    if len(scenarios) != 9:
        raise ValueError(f"Expected nine SCENARIO profiles; found {len(scenarios)}")

    output_rows: list[dict[str, Any]] = []
    per_profile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scenario in scenarios:
        student_id = scenario["student_id"]
        regime_probe = run_dss(student_id, {"lambda": 0.1, "include_plans": False})
        mode, budgets = _profile_budget_mode(regime_probe["credit_regime"], optimizer)
        for budget in budgets:
            result = run_dss(student_id, {"budget": budget, "lambda": 0.1})
            regime = result["credit_regime"]
            if not result.get("plans"):
                raise ValueError(f"{student_id} budget {budget}: DSS returned no plan rows")
            for plan in result["plans"]:
                level = risk_level(plan)
                graduation = plan.get("estimated_graduation")
                if graduation is not None and (
                    not isinstance(graduation, dict) or "semester" not in graduation
                ):
                    raise ValueError(
                        f"{student_id} {plan['plan_type']}: unexpected graduation estimate "
                        f"{graduation!r}"
                    )
                graduation_semester = (
                    graduation["semester"] if graduation is not None else "UNKNOWN"
                )
                row = {
                    "student_id": student_id,
                    "persona": scenario.get("persona", ""),
                    "regime": regime.get("regime", "UNKNOWN"),
                    "budget_mode": mode,
                    "scenario_budget": budget,
                    "lambda": 0.1,
                    "plan_type": plan["plan_type"],
                    "display_label": PLAN_DISPLAY_LABELS.get(
                        plan["plan_type"], plan["plan_type"]
                    ),
                    "status": plan.get("status", "UNKNOWN"),
                    "selected_course_ids": json.dumps(
                        plan.get("selected_course_ids", []), ensure_ascii=False
                    ),
                    "selected_credits": plan["selected_credits"],
                    "expected_credits_passed": plan["expected_credits_passed"],
                    "expected_failed_courses": plan["expected_failed_courses"],
                    "p_at_least_one_failure": plan["p_at_least_one_failure"],
                    "p_warning_W1": plan["p_warning_W1"],
                    "p_warning_W2": plan["p_warning_W2"],
                    "retake_credits_total": plan.get("retake_credits_total", "UNKNOWN"),
                    "estimated_graduation_semester": graduation_semester,
                    "graduation_estimate_source": (
                        graduation.get("assumption", "GIẢ ĐỊNH (core.run_dss)")
                        if graduation is not None
                        else "UNKNOWN: core.run_dss returned null"
                    ),
                    "risk_level": level,
                    "advisor_recommendation": (
                        "khuyến nghị trao đổi với cố vấn học tập" if level == "CAO" else ""
                    ),
                    "source_label": "SCENARIO / GIẢ ĐỊNH (DSS, λ=0,1)",
                }
                output_rows.append(row)
                per_profile[student_id].append(row)

    expected_rows = sum(3 * len(_profile_budget_mode(
        run_dss(row["student_id"], {"lambda": 0.1, "include_plans": False})["credit_regime"],
        optimizer,
    )[1]) for row in scenarios)
    if len(output_rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} budget-plan rows, got {len(output_rows)}")
    _write_csv(GENERATED / "plans_by_budget.csv", BUDGET_FIELDS, output_rows)

    profile_patterns: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    profiles_budget_sensitive: list[str] = []
    all_three_same_at_any_budget: list[str] = []
    all_three_same_at_every_budget: list[str] = []
    for student_id, rows in per_profile.items():
        budgets = sorted({int(row["scenario_budget"]) for row in rows})
        by_budget: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_budget[int(row["scenario_budget"])].append(row)
        signatures = [
            tuple(
                (row["plan_type"], _plan_outcome_signature(row))
                for row in sorted(by_budget[budget], key=lambda item: item["plan_type"])
            )
            for budget in budgets
        ]
        if len(set(signatures)) > 1:
            profiles_budget_sensitive.append(student_id)
        profile_patterns[_budget_sweep_signature(rows)].append(student_id)

        same_budgets = []
        for budget, budget_rows in by_budget.items():
            outcomes = {_plan_outcome_signature(row) for row in budget_rows}
            if len(budget_rows) == 3 and len(outcomes) == 1:
                same_budgets.append(budget)
        if same_budgets:
            all_three_same_at_any_budget.append(student_id)
        if len(same_budgets) == len(budgets):
            all_three_same_at_every_budget.append(student_id)

    repeated_groups = [
        sorted(group)
        for group in profile_patterns.values()
        if len(group) > 1
    ]
    summary = {
        "source_label": "SCENARIO / GIẢ ĐỊNH (DSS)",
        "lambda": 0.1,
        "profile_count": len(per_profile),
        "plan_budget_row_count": len(output_rows),
        "profiles_with_three_strategy_outcomes_identical_at_any_budget": (
            len(all_three_same_at_any_budget)
        ),
        "profiles_with_three_strategy_outcomes_identical_at_any_budget_ids": (
            sorted(all_three_same_at_any_budget)
        ),
        "profiles_with_three_strategy_outcomes_identical_at_every_budget": (
            len(all_three_same_at_every_budget)
        ),
        "profiles_with_three_strategy_outcomes_identical_at_every_budget_ids": (
            sorted(all_three_same_at_every_budget)
        ),
        "profiles_with_budget_sensitivity": len(profiles_budget_sensitive),
        "profiles_with_budget_sensitivity_ids": sorted(profiles_budget_sensitive),
        "distinct_budget_sweep_patterns": len(profile_patterns),
        "identical_budget_sweep_groups": sorted(
            repeated_groups, key=lambda group: (group[0], len(group))
        ),
        "definition": (
            "Strategy outcomes compare status, selected course IDs/credits, expected "
            "credits passed/failures, failure and W1/W2 probabilities, retake credits, "
            "graduation estimate, and risk level. Budget-sweep profiles compare the "
            "ordered outcomes over their configured three-budget grid."
        ),
    }
    (GENERATED / "final_budget_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _mean_nw_credits() -> float:
    metadata = _context()["metadata"]
    courses = metadata["program_courses"]
    if not courses:
        raise ValueError("The configured NW program contains no courses")
    return sum(int(row["credits"]) for row in courses) / len(courses)


def build_mc_explanations() -> dict[str, Any]:
    mc_rows = _read_csv(MC_RESULTS_PATH)
    pairwise_rows = _read_csv(MC_PAIRWISE_PATH)
    pareto_rows = _read_csv(MC_PARETO_PATH)
    optimizer = _read_yaml(OPTIMIZER_CONFIG_PATH)["optimizer"]
    mc_config = _read_yaml(MC_CONFIG_PATH)["monte_carlo"]
    mean_credits = _mean_nw_credits()
    lambdas = [0.1, 0.3]
    loads = [15, 18, 21, 24]
    threshold_units = int(mc_config["probability_model"]["load_factor_threshold_units"])
    load_rows: list[dict[str, Any]] = []
    for load_lambda in lambdas:
        for credits in loads:
            units = math.floor(credits / mean_credits + 0.5)
            g_load = math.exp(-load_lambda * max(0, units - threshold_units))
            load_rows.append(
                {
                    "lambda": load_lambda,
                    "credits_L": credits,
                    "mean_credits_NW": mean_credits,
                    "units_L": units,
                    "g_load": g_load,
                    "penalized": units > threshold_units,
                }
            )
    max_unpenalized = max(
        load for load in range(0, 100)
        if math.floor(load / mean_credits + 0.5) <= threshold_units
    )

    expected_policies = ["ILP-matched", "B1", "B2", "B3"]
    policy_rows: list[dict[str, Any]] = []
    for load_lambda in lambdas:
        lambda_rows = [
            row for row in mc_rows
            if math.isclose(float(row["lambda"]), load_lambda)
        ]
        for policy in expected_policies:
            matching = [row for row in lambda_rows if row["policy"] == policy]
            values = [float(row["selected_load_mean"]) for row in matching]
            policy_rows.append(
                {
                    "policy": policy,
                    "lambda": load_lambda,
                    "profile_rows": len(matching),
                    "mean_credits_per_semester": (
                        sum(values) / len(values) if values else "không có"
                    ),
                    "source_label": "GIẢ ĐỊNH (Monte Carlo)",
                }
            )

    focus_lambdas = {0.0, 0.1}
    focus_students = {"V2-001", "V2-003"}
    paired: list[dict[str, Any]] = []
    for row in pairwise_rows:
        sid = row["student_id"]
        lam = float(row["lambda"])
        if sid not in focus_students or lam not in focus_lambdas:
            continue
        paired.append(
            {
                "student_id": sid,
                "lambda": lam,
                "comparison": row["comparison"],
                "policy_a": row["policy_a"],
                "policy_b": row["policy_b"],
                "p_graduated_on_time_difference": float(row["diff_p_graduated_on_time"]),
                "p_graduated_on_time_ci95": [
                    float(row["ci_p_graduated_on_time_lower"]),
                    float(row["ci_p_graduated_on_time_upper"]),
                ],
                "expected_failed_courses_difference": float(row["diff_expected_failed_courses"]),
                "expected_failed_courses_ci95": [
                    float(row["ci_expected_failed_courses_lower"]),
                    float(row["ci_expected_failed_courses_upper"]),
                ],
            }
        )
    pareto = [
        {
            "student_id": row["student_id"],
            "lambda": float(row["lambda"]),
            "policy_a": row["policy_a"],
            "policy_b": row["policy_b"],
            "pareto_label": row["dominance"],
        }
        for row in pareto_rows
        if row["student_id"] in focus_students and float(row["lambda"]) in focus_lambdas
    ]

    by_student: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mc_rows:
        by_student[row["student_id"]].append(row)
    expulsion_threshold = 0.95
    consecutive_limit = int(mc_config["regulatory"]["consecutive_warning_limit"])
    expulsion_profiles = []
    for student_id, rows in sorted(by_student.items()):
        rates = [float(row["p_expelled_regulatory"]) for row in rows]
        if rates and min(rates) >= expulsion_threshold:
            failures = [float(row["expected_failed_courses"]) for row in rows]
            completion_16 = [float(row["p_graduated_16"]) for row in rows]
            expulsion_profiles.append(
                {
                    "student_id": student_id,
                    "policy_lambda_rows": len(rows),
                    "p_expelled_min": min(rates),
                    "p_expelled_max": max(rates),
                    "expected_failed_courses_min": min(failures),
                    "expected_failed_courses_max": max(failures),
                    "p_graduated_16_min": min(completion_16),
                    "p_graduated_16_max": max(completion_16),
                    "consecutive_warning_limit": consecutive_limit,
                    "interpretation": (
                        "In the stored scenarios, all policy/lambda rows exceed the "
                        "threshold. The model's rule is a consecutive-warning limit; "
                        "these associations are simulated outcomes, not causal evidence."
                    ),
                }
            )

    source_files = [
        "reports/generated/mc_results.csv",
        "reports/generated/mc_pairwise.csv",
        "reports/generated/mc_pareto.csv",
        "config/monte_carlo_scenario.yaml",
        "config/optimizer_scenario_v2.yaml",
        "data/official/courses.csv",
        "config/program_official.yaml",
        "config/courses_enrichment.yaml",
    ]
    result = {
        "source_label": "GIẢ ĐỊNH (Monte Carlo)",
        "sources": source_files,
        "nw_mean_credits": mean_credits,
        "nw_course_count": len(_context()["metadata"]["program_courses"]),
        "load_rounding": optimizer["load"]["rounding"],
        "load_factor_threshold_units": threshold_units,
        "largest_integer_load_without_penalty": max_unpenalized,
        "load_penalties": load_rows,
        "average_selected_credits_per_semester": policy_rows,
        "paired_95_ci": paired,
        "pareto_labels": pareto,
        "profiles_with_expulsion_probability_at_least_0_95_under_all_rows": expulsion_profiles,
    }

    explanation_rows: list[dict[str, Any]] = []

    def add_row(
        section: str,
        metric: str,
        value: Any,
        *,
        student_id: str = "",
        policy: str = "",
        load_lambda: Any = "",
        lower: Any = "",
        upper: Any = "",
        pareto_label: str = "",
        explanation: str = "",
    ) -> None:
        explanation_rows.append(
            {
                "section": section,
                "student_id": student_id,
                "policy": policy,
                "lambda": load_lambda,
                "metric": metric,
                "value": value,
                "ci95_lower": lower,
                "ci95_upper": upper,
                "pareto_label": pareto_label,
                "explanation": explanation,
                "source_files": "; ".join(source_files),
            }
        )

    add_row(
        "NW load",
        "mean_credits_NW",
        mean_credits,
        explanation=f"Mean credit value over {len(_context()['metadata']['program_courses'])} selected NW program course IDs.",
    )
    add_row(
        "NW load",
        "largest_integer_L_without_load_penalty",
        max_unpenalized,
        explanation=f"Half-up units(L) stays at or below {threshold_units}.",
    )
    for row in load_rows:
        add_row(
            "NW load",
            "g_load",
            row["g_load"],
            load_lambda=row["lambda"],
            explanation=(
                f"L={row['credits_L']}; units(L)={row['units_L']}; "
                f"penalized={row['penalized']}."
            ),
        )
    for row in policy_rows:
        add_row(
            "Mean selected credits per semester",
            "selected_load_mean",
            row["mean_credits_per_semester"],
            policy=row["policy"],
            load_lambda=row["lambda"],
            explanation=f"Mean across {row['profile_rows']} saved profile rows.",
        )
    for row in paired:
        for metric, ci_name in (
            ("p_graduated_on_time_difference", "p_graduated_on_time_ci95"),
            ("expected_failed_courses_difference", "expected_failed_courses_ci95"),
        ):
            add_row(
                "Paired comparison",
                metric,
                row[metric],
                student_id=row["student_id"],
                policy=row["comparison"],
                load_lambda=row["lambda"],
                lower=row[ci_name][0],
                upper=row[ci_name][1],
            )
    for row in pareto:
        add_row(
            "Pareto",
            "dominance",
            row["pareto_label"],
            student_id=row["student_id"],
            policy=f"{row['policy_a']} - {row['policy_b']}",
            load_lambda=row["lambda"],
            pareto_label=row["pareto_label"],
        )
    for row in expulsion_profiles:
        add_row(
            "Expulsion risk",
            "p_expelled_regulatory_range",
            f"{row['p_expelled_min']:.3f}–{row['p_expelled_max']:.3f}",
            student_id=row["student_id"],
            explanation=(
                f"Across {row['policy_lambda_rows']} saved policy/lambda rows; "
                f"expected failures {row['expected_failed_courses_min']:.3f}–"
                f"{row['expected_failed_courses_max']:.3f}; "
                f"P(graduated by 16) {row['p_graduated_16_min']:.3f}–"
                f"{row['p_graduated_16_max']:.3f}; consecutive warning limit "
                f"{row['consecutive_warning_limit']}."
            ),
        )
    _write_csv(
        GENERATED / "mc_explanations.csv",
        EXPLANATION_FIELDS,
        explanation_rows,
    )
    (GENERATED / "mc_explanations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    summary = build_budget_outputs()
    explanations = build_mc_explanations()
    print(
        "PLANS_BY_BUDGET: "
        f"{summary['profile_count']} profiles; {summary['plan_budget_row_count']} rows; "
        f"{summary['profiles_with_budget_sensitivity']}/9 budget-sensitive; "
        f"{summary['distinct_budget_sweep_patterns']} distinct budget-sweep patterns"
    )
    print(
        "MC_EXPLANATIONS: "
        f"NW mean credits={explanations['nw_mean_credits']:.6f}; "
        f"max unpenalized L={explanations['largest_integer_load_without_penalty']}; "
        f"{len(explanations['paired_95_ci'])} paired rows; "
        f"high-expulsion profiles="
        f"{[row['student_id'] for row in explanations['profiles_with_expulsion_probability_at_least_0_95_under_all_rows']]}"
    )
    print("MONTE_CARLO_RERUNS=0")


if __name__ == "__main__":
    main()
