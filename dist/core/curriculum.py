"""Load OFFICIAL curriculum rows and attach explicitly labeled enrichments."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
COURSES_PATH = ROOT / "data" / "official" / "courses.csv"
PREREQUISITES_PATH = ROOT / "data" / "official" / "prerequisites.csv"
ENRICHMENT_CONFIG_PATH = ROOT / "config" / "courses_enrichment.yaml"
PROGRAM_CONFIG_PATH = ROOT / "config" / "program_official.yaml"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = yaml.safe_load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def load_curriculum() -> dict[str, list[dict[str, Any]]]:
    return {
        "courses": read_csv(COURSES_PATH),
        "prerequisites": read_csv(PREREQUISITES_PATH),
    }


def load_enrichment_config() -> dict[str, Any]:
    return read_yaml(ENRICHMENT_CONFIG_PATH)


def load_program_config() -> dict[str, Any]:
    return read_yaml(PROGRAM_CONFIG_PATH)


def enrich_courses(
    courses: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    label = str(config["label"])
    specialization_rules = config["specialization"]["suffix_rules"]
    false_groups = set(config["counts_toward_total"]["false_groups"])
    exact_slots = config["elective_slot"]["exact"]
    slot_prefixes = config["elective_slot"]["prefixes"]
    slot_credits = config["slot_required_credits"]
    pdf_prefixes = tuple(config["code_source"]["pdf_prefixes"])
    unconfirmed_prefixes = tuple(config["code_source"]["unconfirmed_prefixes"])
    unknown_code_source = config["code_source"]["otherwise"]

    enriched: list[dict[str, Any]] = []
    for source_row in courses:
        row = dict(source_row)
        course_id = str(row["course_id"])
        group = str(row.get("group", ""))
        specialization = str(config["specialization"]["default"])
        for suffix, value in specialization_rules.items():
            if re.search(rf"(?:^|){re.escape(suffix)}(?:-|$)", course_id):
                specialization = str(value)
                break

        elective_slot = exact_slots.get(course_id)
        if elective_slot is None:
            for prefix, slot in sorted(
                slot_prefixes.items(), key=lambda item: len(item[0]), reverse=True
            ):
                if course_id.startswith(prefix):
                    elective_slot = slot
                    break

        if course_id.startswith(pdf_prefixes):
            code_source = "PDF"
        elif course_id.startswith(unconfirmed_prefixes):
            code_source = "TEAM_ASSIGNED_OR_UNVERIFIED"
        else:
            code_source = unknown_code_source["value"]

        offerings = {
            value.strip()
            for value in str(row.get("offered_semesters", "")).split(",")
            if value.strip()
        }
        row.update(
            {
                "specialization": specialization,
                "counts_toward_total": group not in false_groups,
                "elective_slot": elective_slot,
                "slot_required_credits": (
                    slot_credits[elective_slot] if elective_slot is not None else None
                ),
                "graduation_slot": elective_slot
                == config["graduation_slot"]["slot"],
                "code_source": code_source,
                "offering_rule": sorted(offerings),
                "enrichment_label": label,
            }
        )
        enriched.append(row)
    return enriched


def load_enriched_curriculum() -> dict[str, Any]:
    curriculum = load_curriculum()
    enrichment_config = load_enrichment_config()
    curriculum["courses"] = enrich_courses(
        curriculum["courses"], enrichment_config
    )
    curriculum["enrichment_config"] = enrichment_config
    curriculum["program_config"] = load_program_config()
    return curriculum


def load_rules_config() -> dict[str, Any]:
    from core.regulation import load_regulation_config

    return {
        "enrichment": load_enrichment_config(),
        "program": load_program_config(),
        "regulation": load_regulation_config(),
    }
