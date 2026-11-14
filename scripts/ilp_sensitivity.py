"""One-at-a-time sensitivity of the ILP plan to beta, gamma and load lambda.

Each parameter is varied while the others stay at their baseline values, so the
rows are readable as a scenario analysis, not as a factorial experiment. All
curriculum, persona and prerequisite data are SIMULATED; beta/gamma/lambda are
ASSUMPTIONS. Outputs `reports/generated/ilp_sensitivity.csv` and
`reports/generated/ilp_unlock_values.csv`.
"""

from __future__ import annotations

import copy
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.optimize.ilp_prototype import compute_unlock_values
from src.services.assessment import (
    assess_student,
    build_plans,
    default_rules,
    load_bundle,
    load_curriculum,
    persona_payload,
)

OUTPUT_DIR = ROOT / "reports" / "generated"
STUDENTS = ("S001", "S003", "S005")
BUDGETS = (12, 18)
BETA_VALUES = (0.0, 0.125, 0.5)
GAMMA_VALUES = (0.0, 1.0, 3.0)
LAMBDA_VALUES = (0.0, 0.1, 0.3)


def _rules_with(rules: dict, *, beta: float, gamma: float) -> dict:
    varied = copy.deepcopy(rules)
    varied["optimization"]["beta_unlock_value"]["value"] = beta
    varied["optimization"]["gamma_failure_penalty"]["value"] = gamma
    return varied


def _row(
    student_id: str,
    parameter: str,
    value: float,
    budget: int,
    plan: dict,
) -> dict:
    result = plan["result"]
    course_ids = result.get("selected_course_ids", [])
    return {
        "student_id": student_id,
        "parameter": parameter,
        "value": value,
        "budget": budget,
        "status": result.get("status"),
        "selected_credits": result.get("selected_credits", 0),
        "expected_credits_passed": round(
            float(result.get("expected_credits_passed", 0.0)), 4
        ),
        "expected_failed_courses": round(
            float(result.get("expected_failed_courses", 0.0)), 4
        ),
        "n_courses": len(course_ids),
        "selected_course_ids": ";".join(course_ids),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curriculum = load_curriculum()
    bundle = load_bundle()
    rules = default_rules()
    baseline_beta = float(rules["optimization"]["beta_unlock_value"]["value"])
    baseline_gamma = float(rules["optimization"]["gamma_failure_penalty"]["value"])

    sensitivity_rows: list[dict] = []
    unlock_rows: list[dict] = []
    for student_id in STUDENTS:
        profile, progress_rows = persona_payload(curriculum, student_id)
        assessment = assess_student(
            profile,
            progress_rows,
            curriculum,
            bundle,
            rules,
            use_ml=True,
        )
        rule_result = assessment["rule_result"]
        statuses = {
            str(row["course_id"]): str(row.get("status", "not_taken"))
            for row in progress_rows
        }
        credits_by_course = {
            course["course_id"]: float(course["credits"])
            for course in curriculum["courses"]
        }
        unlock = compute_unlock_values(
            [course["course_id"] for course in rule_result["eligible_courses"]],
            curriculum["prerequisites"],
            statuses,
            credits_by_course=credits_by_course,
            discount_per_edge=float(
                rules["optimization"]["unlock_discount_per_edge"]["value"]
            ),
        )
        for course in rule_result["eligible_courses"]:
            unlock_rows.append(
                {
                    "student_id": student_id,
                    "course_id": course["course_id"],
                    "course_name": course["course_name"],
                    "credits": course["credits"],
                    "status": course["status"],
                    "unlock_value": round(unlock.get(course["course_id"], 0.0), 4),
                }
            )

        variations = (
            [("beta", value, baseline_gamma) for value in BETA_VALUES]
            + [("gamma", value, value) for value in GAMMA_VALUES]
            + [("load_lambda", value, baseline_gamma) for value in LAMBDA_VALUES]
        )
        for parameter, value, gamma in variations:
            if parameter == "beta":
                varied_rules = _rules_with(
                    rules, beta=value, gamma=baseline_gamma
                )
                load_lambda = 0.1
            elif parameter == "gamma":
                varied_rules = _rules_with(
                    rules, beta=baseline_beta, gamma=value
                )
                load_lambda = 0.1
            else:
                varied_rules = rules
                load_lambda = value
            plans = build_plans(
                assessment,
                curriculum,
                bundle,
                varied_rules,
                budgets=list(BUDGETS),
                load_lambda=load_lambda,
            )
            for plan in plans:
                sensitivity_rows.append(
                    _row(student_id, parameter, value, plan["budget"], plan)
                )

    sensitivity_path = OUTPUT_DIR / "ilp_sensitivity.csv"
    with sensitivity_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(sensitivity_rows[0]))
        writer.writeheader()
        writer.writerows(sensitivity_rows)

    unlock_path = OUTPUT_DIR / "ilp_unlock_values.csv"
    with unlock_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(unlock_rows[0]))
        writer.writeheader()
        writer.writerows(unlock_rows)

    print("Sensitivity (student, parameter, value, budget -> credits, failures, status):")
    for row in sensitivity_rows:
        print(
            f"{row['student_id']} {row['parameter']}={row['value']:<5} "
            f"budget={row['budget']:<2} -> {row['selected_credits']:>2} credits, "
            f"{row['expected_failed_courses']:.2f} failures, {row['status']}"
        )
    print(f"\nWrote {sensitivity_path}")
    print(f"Wrote {unlock_path}")


if __name__ == "__main__":
    main()
