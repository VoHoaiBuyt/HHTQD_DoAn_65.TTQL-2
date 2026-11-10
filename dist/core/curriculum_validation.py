"""Validate OFFICIAL course rows and report explicit inference assumptions."""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from core.curriculum import (
    ROOT,
    enrich_courses,
    load_curriculum,
    load_enrichment_config,
    load_program_config,
)
from core.metrics import update_metrics


OUTPUT_PATH = ROOT / "reports" / "generated" / "curriculum_validation.json"
ASSUMPTIONS_PATH = ROOT / "reports" / "generated" / "enrichment_assumptions.md"
REPORT_PATH = ROOT / "reports" / "generated" / "curriculum_summary.md"
TEXT_REPORT_PATH = ROOT / "reports" / "curriculum_validation.txt"


def _graph_summary(
    course_ids: set[str], prerequisites: list[dict[str, Any]]
) -> dict[str, Any]:
    dependents: dict[str, set[str]] = defaultdict(set)
    graph: dict[str, set[str]] = defaultdict(set)
    for row in prerequisites:
        prerequisite_id = str(row["prerequisite_id"])
        course_id = str(row["course_id"])
        graph[prerequisite_id].add(course_id)
        dependents[prerequisite_id].add(course_id)

    state: dict[str, int] = {}
    depths: dict[str, int] = {}
    path: list[str] = []
    longest_path: list[str] = []
    cycle: list[str] = []

    def visit(course_id: str) -> int:
        nonlocal cycle, longest_path
        if state.get(course_id) == 1:
            start = path.index(course_id)
            cycle = path[start:] + [course_id]
            return 0
        if state.get(course_id) == 2:
            return depths[course_id]
        state[course_id] = 1
        path.append(course_id)
        best_depth = 1
        best_child: str | None = None
        for child in sorted(graph.get(course_id, ())):
            child_depth = visit(child)
            if child_depth + 1 > best_depth:
                best_depth = child_depth + 1
                best_child = child
        path.pop()
        state[course_id] = 2
        depths[course_id] = best_depth
        if not cycle and (
            best_depth > len(longest_path)
            or not longest_path
        ):
            chain = [course_id]
            while best_child is not None:
                chain.append(best_child)
                children = sorted(graph.get(best_child, ()))
                next_children = [
                    child for child in children if depths.get(child, 0) == depths[best_child] - 1
                ]
                best_child = next_children[0] if next_children else None
            longest_path = chain
        return best_depth

    for course_id in sorted(course_ids):
        if state.get(course_id, 0) == 0:
            visit(course_id)
    most_dependent = sorted(
        (
            (course_id, len(children))
            for course_id, children in dependents.items()
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return {
        "edge_count": len(prerequisites),
        "max_depth_courses": len(longest_path),
        "longest_chain": longest_path,
        "cycle": cycle,
        "most_dependent_courses": most_dependent[:1],
    }


def validate_curriculum(
    courses: list[dict[str, Any]],
    prerequisites: list[dict[str, Any]],
    enrichment_config: dict[str, Any],
    program_config: dict[str, Any],
) -> dict[str, Any]:
    enriched = enrich_courses(courses, enrichment_config)
    checks: list[dict[str, Any]] = []

    def check(
        check_id: str,
        passed: bool,
        message: str,
        *,
        status: str | None = None,
        details: Any = None,
    ) -> None:
        checks.append(
            {
                "id": check_id,
                "status": status or ("PASS" if passed else "FAIL"),
                "message": message,
                "details": details,
            }
        )

    course_ids = [str(row["course_id"]) for row in enriched]
    course_by_id = {str(row["course_id"]): row for row in enriched}
    unique = len(course_ids) == len(set(course_ids))
    check("course_id_unique", unique, "course_id values are unique.")

    missing_references = [
        {
            "course_id": str(row["course_id"]),
            "prerequisite_id": str(row["prerequisite_id"]),
        }
        for row in prerequisites
        if row.get("course_id") not in course_by_id
        or row.get("prerequisite_id") not in course_by_id
    ]
    check(
        "prerequisite_references_exist",
        not missing_references,
        "All prerequisite endpoints reference known course IDs.",
        details=missing_references,
    )

    graph_summary = _graph_summary(set(course_ids), prerequisites)
    check(
        "prerequisite_graph_is_dag",
        not graph_summary["cycle"],
        "The prerequisite graph is acyclic.",
        details=graph_summary["cycle"] or None,
    )

    semester_errors = []
    for row in prerequisites:
        course_id = str(row.get("course_id"))
        prerequisite_id = str(row.get("prerequisite_id"))
        if course_id not in course_by_id or prerequisite_id not in course_by_id:
            continue
        course_semester = int(course_by_id[course_id]["planned_semester"])
        prerequisite_semester = int(
            course_by_id[prerequisite_id]["planned_semester"]
        )
        relation_type = str(row["type"])
        valid = (
            prerequisite_semester < course_semester
            if relation_type == "tiên quyết"
            else prerequisite_semester <= course_semester
            if relation_type == "song hành"
            else True
        )
        if not valid:
            semester_errors.append(
                {
                    "course_id": course_id,
                    "course_semester": course_semester,
                    "prerequisite_id": prerequisite_id,
                    "prerequisite_semester": prerequisite_semester,
                    "type": relation_type,
                }
            )
    check(
        "prerequisite_semester_order",
        not semester_errors,
        "Strict prerequisites precede their course; corequisites are in the same or an earlier semester.",
        details=semester_errors,
    )

    allowed_types = {"tiên quyết", "học trước", "song hành"}
    invalid_types = [
        dict(row) for row in prerequisites if row.get("type") not in allowed_types
    ]
    check(
        "prerequisite_relation_types",
        not invalid_types,
        "Prerequisite relation types use the supported vocabulary.",
        details=invalid_types,
    )

    missing_course_sources = [
        row["course_id"]
        for row in enriched
        if not str(row.get("source_label", "")).strip()
    ]
    check(
        "course_source_labels_present",
        not missing_course_sources,
        "Every course row has a source_label.",
        details=missing_course_sources,
    )
    missing_prerequisite_sources = [
        {
            "course_id": row.get("course_id"),
            "prerequisite_id": row.get("prerequisite_id"),
        }
        for row in prerequisites
        if not str(row.get("source_label", "")).strip()
    ]
    check(
        "prerequisite_source_labels_present",
        not missing_prerequisite_sources,
        "Every prerequisite row has a source_label.",
        details=missing_prerequisite_sources,
    )

    offering_errors = []
    accepted_offerings = set(enrichment_config["offering_rule"]["accepted_values"])
    for row in enriched:
        offerings = set(row["offering_rule"])
        planned_semester = int(row["planned_semester"])
        parity = "odd" if planned_semester % 2 else "even"
        if (
            not offerings
            or not offerings.issubset(accepted_offerings)
            or ("both" not in offerings and parity not in offerings)
        ):
            offering_errors.append(
                {
                    "course_id": row["course_id"],
                    "planned_semester": planned_semester,
                    "offered_semesters": sorted(offerings),
                }
            )
    check(
        "offering_rule_values",
        not offering_errors,
        "Offering values and planned-term parity are internally consistent.",
        details=offering_errors,
    )

    program = program_config["program"]
    expected_mandatory = list(program["mandatory_by_semester"])
    expected_elective = list(program["elective_by_semester"])
    semester_count = len(expected_mandatory)
    semester_totals: dict[str, Any] = {}
    credit_errors: list[dict[str, Any]] = []
    external_groups = set(program["external_groups"])
    course_type_mandatory = next(
        (row["course_type"] for row in enriched if row["course_type"] == "bắt buộc"),
        "bắt buộc",
    )
    course_type_elective = next(
        (row["course_type"] for row in enriched if row["course_type"] == "tự chọn"),
        "tự chọn",
    )
    for specialization in program["specializations"]:
        actual_mandatory: list[int] = []
        actual_elective: list[int] = []
        for semester in range(1, semester_count + 1):
            mandatory = sum(
                int(row["credits"])
                for row in enriched
                if row["counts_toward_total"]
                and row["group"] not in external_groups
                and row["course_type"] == course_type_mandatory
                and row["specialization"] in {"common", specialization}
                and int(row["planned_semester"]) == semester
            )
            elective_slots: dict[str, int] = {}
            for row in enriched:
                slot = row["elective_slot"]
                if (
                    not row["counts_toward_total"]
                    or row["group"] in external_groups
                    or slot is None
                    or row["course_type"] != course_type_elective
                    or row["graduation_slot"]
                    or row["specialization"] not in {"common", specialization}
                    or int(row["planned_semester"]) != semester
                ):
                    continue
                elective_slots[str(slot)] = int(row["slot_required_credits"])
            elective = sum(elective_slots.values())
            actual_mandatory.append(mandatory)
            actual_elective.append(elective)

        graduation_config = enrichment_config["graduation_slot"]
        graduation_slot = str(graduation_config["slot"])
        graduation_credits = int(graduation_config["required_credits"])
        graduation_semester = int(graduation_config["semester"])
        if graduation_semester <= semester_count:
            actual_mandatory[graduation_semester - 1] += graduation_credits

        expected_slots = [
            expected_elective[index]
            for index in range(semester_count)
        ]
        if actual_mandatory != expected_mandatory:
            credit_errors.append(
                {
                    "specialization": specialization,
                    "kind": "mandatory_by_semester",
                    "expected": expected_mandatory,
                    "actual": actual_mandatory,
                }
            )
        if actual_elective != expected_slots:
            credit_errors.append(
                {
                    "specialization": specialization,
                    "kind": "elective_by_semester",
                    "expected": expected_slots,
                    "actual": actual_elective,
                }
            )
        total = sum(actual_mandatory) + sum(actual_elective)
        if total != int(program["total_credits"]):
            credit_errors.append(
                {
                    "specialization": specialization,
                    "kind": "total_credits",
                    "expected": int(program["total_credits"]),
                    "actual": total,
                }
            )
        semester_totals[specialization] = {
            "mandatory": actual_mandatory,
            "elective": actual_elective,
            "total": total,
            "all_including_electives": [
                mandatory + elective
                for mandatory, elective in zip(actual_mandatory, actual_elective)
            ],
        }
    check(
        "credits_by_specialization_and_semester",
        not credit_errors,
        "Mandatory, elective-slot, and total credits match the OFFICIAL program values for every specialization.",
        details={"errors": credit_errors, "computed": semester_totals},
    )

    slot_errors = []
    slot_options: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        if row["elective_slot"] is None or row["graduation_slot"]:
            continue
        slot_options[
            (
                str(row["specialization"]),
                str(row["elective_slot"]),
                int(row["planned_semester"]),
            )
        ].append(row)
    required_slots_by_specialization = program_config["program"].get(
        "required_elective_slots", {}
    )
    for specialization in program["specializations"]:
        slots = required_slots_by_specialization.get(specialization, [])
        for slot in slots:
            matching = [
                row
                for row in enriched
                if row["elective_slot"] == slot
                and row["specialization"] in {"common", specialization}
                and not row["graduation_slot"]
            ]
            if not matching:
                slot_errors.append(
                    {
                        "specialization": specialization,
                        "slot": slot,
                        "reason": "no alternatives found",
                    }
                )
                continue
            required_choices = int(
                enrichment_config["elective_slot"]["selection_required"]
            )
            if len(matching) < required_choices:
                slot_errors.append(
                    {
                        "specialization": specialization,
                        "slot": slot,
                        "reason": "not enough alternatives",
                        "required": required_choices,
                        "found": len(matching),
                    }
                )
            expected_credits = {
                int(row["slot_required_credits"]) for row in matching
            }
            actual_credits = {int(row["credits"]) for row in matching}
            if len(expected_credits) != 1 or actual_credits != expected_credits:
                slot_errors.append(
                    {
                        "specialization": specialization,
                        "slot": slot,
                        "expected_credits": sorted(expected_credits),
                        "actual_credits": sorted(actual_credits),
                    }
                )
    graduation_rows = [
        row for row in enriched if row["elective_slot"] == graduation_slot
    ]
    if len(graduation_rows) < int(
        graduation_config["selection_required"]
    ):
        slot_errors.append(
            {
                "slot": graduation_slot,
                "reason": "not enough graduation alternatives",
                "found": len(graduation_rows),
            }
        )
    if any(
        int(row["credits"]) != graduation_credits
        or int(row["planned_semester"]) != graduation_semester
        for row in graduation_rows
    ):
        slot_errors.append(
            {
                "slot": graduation_slot,
                "reason": "graduation alternatives disagree with configured credits or semester",
            }
        )
    check(
        "elective_slot_alternatives",
        not slot_errors,
        "Each required elective slot has alternatives with the configured slot credit value.",
        details=slot_errors,
    )

    duplicate_names: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in enriched:
        normalized_name = " ".join(
            str(row["course_name"]).casefold().split()
        )
        duplicate_names[normalized_name].append(
            {
                "course_id": str(row["course_id"]),
                "specialization": str(row["specialization"]),
                "course_name": str(row["course_name"]),
            }
        )
    duplicate_warnings = [
        {"name": rows[0]["course_name"], "courses": rows}
        for rows in duplicate_names.values()
        if len(rows) > 1
    ]
    check(
        "duplicate_course_names_review",
        True,
        "Review duplicate course names; names are not used as keys.",
        status="WARN" if duplicate_warnings else "PASS",
        details=duplicate_warnings,
    )

    unknown_codes = sorted(
        row["course_id"]
        for row in enriched
        if row["code_source"] == "TEAM_ASSIGNED_OR_UNVERIFIED"
    )
    code_not_found = sorted(
        row["course_id"] for row in enriched if row["code_source"] == "UNKNOWN"
    )
    check(
        "course_code_source_confirmation",
        True,
        "Confirm which course IDs were printed in the PDF versus assigned by the team.",
        status="WARN" if unknown_codes or code_not_found else "PASS",
        details={
            "TEAM_ASSIGNED_OR_UNVERIFIED": unknown_codes,
            "UNKNOWN_source_NOT_FOUND": code_not_found,
        },
    )

    unconfirmed: list[dict[str, Any]] = []
    completeness = enrichment_config["prerequisite_semantics"]["completeness"]
    if completeness == "UNCONFIRMED":
        unconfirmed.append(
            {
                "field": "prerequisite_completeness",
                "value": "UNCONFIRMED",
                "label": "GIẢ ĐỊNH (chờ đối chiếu quy chế)",
                "message": "A missing prerequisite row is not confirmed to mean no prerequisite.",
            }
        )
    check(
        "prerequisite_completeness_confirmed",
        not unconfirmed,
        (
            "Prerequisite-list completeness is unconfirmed."
            if unconfirmed
            else "Prerequisite-list completeness is confirmed."
        ),
        status="WARN" if unconfirmed else "PASS",
        details=unconfirmed,
    )

    external_rows = [row for row in enriched if not row["counts_toward_total"]]
    course_counts = {
        "total_rows": len(enriched),
        "course_type": dict(Counter(str(row["course_type"]) for row in enriched)),
        "specialization": dict(
            Counter(str(row["specialization"]) for row in enriched)
        ),
        "counts_toward_total": sum(
            bool(row["counts_toward_total"]) for row in enriched
        ),
        "outside_total": len(external_rows),
        "elective_slots": len(
            {str(row["elective_slot"]) for row in enriched if row["elective_slot"]}
        ),
        "unknown_course_codes": unknown_codes,
        "course_code_source_not_found": code_not_found,
    }
    warnings = [
        row for row in checks if row["status"] in {"WARN", "UNKNOWN", "UNCONFIRMED"}
    ]
    failures = [row for row in checks if row["status"] == "FAIL"]
    passes = [row for row in checks if row["status"] == "PASS"]
    return {
        "source_label": "OFFICIAL (NTU)",
        "source_document": program_config["source_document"],
        "source_section": program_config["source_section"],
        "n_checks": len(checks),
        "n_pass": len(passes),
        "n_warn": len(warnings),
        "n_fail": len(failures),
        "checks": checks,
        "summary": {
            "course_counts": course_counts,
            "semester_credits_by_specialization": semester_totals,
            "prerequisite_graph": graph_summary,
            "warnings": warnings,
            "unknown": [
                {
                    "field": "course_code_source",
                    "courses": unknown_codes + code_not_found,
                }
            ]
            if unknown_codes or code_not_found
            else [],
            "unconfirmed": unconfirmed,
        },
    }


def write_assumptions(
    enrichment_config: dict[str, Any],
    validation: dict[str, Any],
) -> None:
    config = enrichment_config
    lines = [
        "# Curriculum enrichment assumptions",
        "",
        f"Label: **{config['label']}**. `courses.csv` remains unchanged; derived fields are attached at load time.",
        "",
        "## Assumptions requiring confirmation against the PDF",
        "",
        f"- **Specialization:** {config['specialization']['source']}",
        f"- **Elective slots:** {config['source']}",
        f"- **HP017:** {config['elective_slot']['general_elective_slot_hp017']['assumption']} Members: `HP017-A`, `BUA319`.",
        f"- **Graduation:** choose one of {config['graduation_slot']['slot']} alternatives for {config['graduation_slot']['required_credits']} credits in semester {config['graduation_slot']['semester']}.",
        f"- **Course-code origin:** prefixes `{config['code_source']['pdf_prefixes']}` are marked PDF; prefixes `{config['code_source']['unconfirmed_prefixes']}` remain unverified.",
        f"- **Offering:** `{config['offering_rule']['column']}` uses values {config['offering_rule']['accepted_values']}; parity interpretation is labeled `{config['offering_rule']['label']}`. {config['offering_rule']['limitation']}",
        f"- **Strict prerequisite:** {config['prerequisite_semantics']['strict_type']['meaning']} — {config['prerequisite_semantics']['strict_type']['label']}.",
        f"- **Corequisite:** {config['prerequisite_semantics']['concurrent_type']['meaning']} — {config['prerequisite_semantics']['concurrent_type']['label']}.",
        "- **Prerequisite completeness:** `UNCONFIRMED`; absence of a row is not confirmation that a course has no prerequisite.",
        "",
        "## Course IDs needing confirmation",
        "",
    ]
    unknown_codes = validation["summary"]["course_counts"]["unknown_course_codes"]
    not_found = validation["summary"]["course_counts"][
        "course_code_source_not_found"
    ]
    lines.append(
        "- `TEAM_ASSIGNED_OR_UNVERIFIED`: "
        + (", ".join(f"`{code}`" for code in unknown_codes) or "none")
    )
    lines.append(
        "- `UNKNOWN`, `source=NOT_FOUND`: "
        + (", ".join(f"`{code}`" for code in not_found) or "none")
    )
    lines.extend(
        [
            "",
            "## Derived fields and rules",
            "",
            "| Field | Rule derived from source | Label/status |",
            "|---|---|---|",
            f"| `specialization` | Match exact course ID suffix `-SE`, `-IS`, or `-NW`; otherwise `{config['specialization']['default']}`. | `{config['label']}` |",
            f"| `counts_toward_total` | False for groups `{config['counts_toward_total']['false_groups']}`; true otherwise. | `{config['label']}` |",
            f"| `elective_slot` | Prefix/exact-ID assignment from `courses_enrichment.yaml`; suffixes remain part of `course_id`. `HP017-A` and `BUA319` are one assumed slot `HP017`: {config['elective_slot']['general_elective_slot_hp017']['assumption']} | `{config['label']}` |",
            f"| `slot_required_credits` | Use configured required credits for each assigned slot, independent of course IDs. | `{config['label']}` |",
            f"| `graduation_slot` | `{config['graduation_slot']['slot']}`; select {config['graduation_slot']['selection_required']} alternative for {config['graduation_slot']['required_credits']} credits in semester {config['graduation_slot']['semester']}; counts as mandatory in the official HK8 total. | `{config['label']}` |",
            f"| `code_source` | Prefixes `{config['code_source']['pdf_prefixes']}` are marked `PDF`; prefixes `{config['code_source']['unconfirmed_prefixes']}` are `TEAM_ASSIGNED_OR_UNVERIFIED`; other prefixes remain `UNKNOWN`. | `{config['label']}` |",
            f"| `offering_rule` | Map `{config['offering_rule']['column']}` values `odd/even/both` to academic semester parity. This calendar is not present in the official plan. | `{config['offering_rule']['label']}` |",
            f"| `enrichment_label` | Copy the top-level enrichment assumption label to every loaded row. | `{config['label']}` |",
            "",
            "### Configured credit requirement for each elective slot",
            "",
            "| Slot | Required credits |",
            "|---|---:|",
            *(
                f"| `{slot}` | {credits} |"
                for slot, credits in sorted(config["slot_required_credits"].items())
            ),
            "",
            "Slot identities, prefixes, and the special HP017 pairing are inferred from the course table and must be checked against the PDF.",
            "The `offered_semesters` mapping is a planning assumption, not a confirmed NTU course-offering calendar.",
            "",
            "### Prerequisite relationship assumptions",
            "",
            f"- `{config['prerequisite_semantics']['strict_type']['value']}`: {config['prerequisite_semantics']['strict_type']['meaning']} — `{config['prerequisite_semantics']['strict_type']['label']}`.",
            f"- `{config['prerequisite_semantics']['concurrent_type']['value']}`: {config['prerequisite_semantics']['concurrent_type']['meaning']} — `{config['prerequisite_semantics']['concurrent_type']['label']}`.",
            f"- `prerequisite_completeness`: `{config['prerequisite_semantics']['completeness']}`; a missing prerequisite row is not confirmed to mean no prerequisite.",
            "",
            "## Known limitations",
            "",
            "- The source table does not establish a semester offering calendar; `odd`/`even` is interpreted as term parity only.",
            "- Summer terms are not modeled.",
            "- Retake limits, academic-warning thresholds, and per-term credit caps are `UNKNOWN`, `source=NOT_FOUND`.",
            "",
        ]
    )
    ASSUMPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ASSUMPTIONS_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_summary(validation: dict[str, Any]) -> None:
    summary = validation["summary"]
    graph = summary["prerequisite_graph"]
    lines = [
        "# Official curriculum validation summary",
        "",
        f"Source: {validation['source_label']} — {validation['source_document']}, section {validation['source_section']}.",
        "",
        "## Catalogue",
        "",
        f"- Rows: {summary['course_counts']['total_rows']}",
        f"- Course type: {summary['course_counts']['course_type']}",
        f"- Enriched specialization: {summary['course_counts']['specialization']}",
        f"- In total program: {summary['course_counts']['counts_toward_total']}; outside 130-credit program: {summary['course_counts']['outside_total']}",
        f"- Distinct elective slots in catalogue: {summary['course_counts']['elective_slots']}",
        "",
        "## Credit schedule, each specialization",
        "",
        "| Specialization | Mandatory by semester | Elective by semester | Total |",
        "|---|---|---|---:|",
    ]
    for specialization, values in summary[
        "semester_credits_by_specialization"
    ].items():
        lines.append(
            f"| {specialization} | {values['mandatory']} | {values['elective']} | {values['total']} |"
        )
    lines.extend(
        [
            "",
            "## Prerequisite graph",
            "",
            f"- Edges: {graph['edge_count']}",
            f"- Longest chain (courses): {graph['max_depth_courses']}",
            f"- Longest chain: {' -> '.join(graph['longest_chain']) or 'none'}",
            f"- Most dependents: {graph['most_dependent_courses']}",
            f"- Cycle: {graph['cycle'] or 'none'}",
            "",
            f"- Checks: {validation['n_checks']}; PASS={validation['n_pass']}, WARN={validation['n_warn']}, FAIL={validation['n_fail']}.",
            "",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    text_lines = [
        "Current OFFICIAL curriculum validation",
        (
            f"Source: {validation['source_label']}, "
            f"{validation['source_document']}, section {validation['source_section']}."
        ),
        (
            "Validator result: "
            f"n_checks={validation['n_checks']}, "
            f"n_pass={validation['n_pass']}, "
            f"n_warn={validation['n_warn']}, "
            f"n_fail={validation['n_fail']}."
        ),
        (
            f"Catalogue: {summary['course_counts']['total_rows']} rows; "
            f"course types={summary['course_counts']['course_type']}; "
            f"outside total={summary['course_counts']['outside_total']}."
        ),
        f"Prerequisite graph: {graph['edge_count']} edges; cycle={graph['cycle'] or 'none'}; longest chain={graph['max_depth_courses']} courses.",
        "Credit schedule by specialization:",
    ]
    for specialization, values in summary[
        "semester_credits_by_specialization"
    ].items():
        text_lines.append(
            f"- {specialization}: mandatory={values['mandatory']}; "
            f"elective={values['elective']}; total={values['total']}."
        )
    text_lines.extend(
        [
            "Warnings:",
            *(
                f"- {warning['id']}: {warning['message']}"
                for warning in summary["warnings"]
            ),
            "Full validation detail: reports/generated/curriculum_validation.json",
            "Enrichment assumptions: reports/generated/enrichment_assumptions.md",
        ]
    )
    TEXT_REPORT_PATH.write_text("\n".join(text_lines) + "\n", encoding="utf-8")


def main() -> int:
    curriculum = load_curriculum()
    enrichment_config = load_enrichment_config()
    program_config = load_program_config()
    result = validate_curriculum(
        curriculum["courses"],
        curriculum["prerequisites"],
        enrichment_config,
        program_config,
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    import json

    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_assumptions(enrichment_config, result)
    write_summary(result)
    update_metrics(
        {
            "source_label": "OFFICIAL (NTU)",
            "curriculum_validation": {
                "status": "PASS" if result["n_fail"] == 0 else "FAIL",
                "n_checks": result["n_checks"],
                "n_pass": result["n_pass"],
                "n_warn": result["n_warn"],
                "n_fail": result["n_fail"],
                "course_rows": result["summary"]["course_counts"]["total_rows"],
                "prerequisite_edges": result["summary"]["prerequisite_graph"][
                    "edge_count"
                ],
                "course_counts": {
                    key: value
                    for key, value in result["summary"]["course_counts"].items()
                    if key not in {"unknown_course_codes", "course_code_source_not_found"}
                },
                "semester_credits_by_specialization": result["summary"][
                    "semester_credits_by_specialization"
                ],
                "prerequisite_graph": result["summary"]["prerequisite_graph"],
                "warning_check_ids": [
                    warning["id"] for warning in result["summary"]["warnings"]
                ],
                "unknown_course_code_count": len(
                    result["summary"]["course_counts"]["unknown_course_codes"]
                )
                + len(
                    result["summary"]["course_counts"][
                        "course_code_source_not_found"
                    ]
                ),
                "unconfirmed_fields": [
                    item["field"] for item in result["summary"]["unconfirmed"]
                ],
            },
        }
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json_dump(result))
    return 1 if result["n_fail"] else 0


def json_dump(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
