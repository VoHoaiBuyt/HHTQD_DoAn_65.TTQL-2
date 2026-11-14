from __future__ import annotations

import csv
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any

import yaml

from core.risk_labels import risk_level
from scripts.final_claims import build_risk_rows, plan_signatures


ROOT = Path(__file__).resolve().parents[1]
CLAIMS_PATH = ROOT / "reports" / "generated" / "prose_claims.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _source_value(source_file: str, key: str) -> str:
    source_path = ROOT / source_file
    assert source_path.is_file(), f"Missing claim source: {source_file}"
    if source_path.suffix.lower() == ".csv":
        rows = _read_csv(source_path)
        parts = dict(part.split("=", 1) for part in key.split(";"))
        field = parts.pop("field")
        matches = [
            row for row in rows
            if all(row.get(name) == value for name, value in parts.items())
        ]
        assert len(matches) == 1, f"Claim selector is not unique: {key}"
        return matches[0][field]

    if source_path.suffix.lower() == ".yaml":
        value: Any = yaml.safe_load(source_path.read_text(encoding="utf-8-sig"))
    else:
        value = json.loads(source_path.read_text(encoding="utf-8-sig"))
    components = key.split(".")
    index = 0
    while index < len(components):
        if isinstance(value, list):
            value = value[int(components[index])]
            index += 1
            continue
        matching_end = next(
            (
                end
                for end in range(len(components), index, -1)
                if ".".join(components[index:end]) in value
            ),
            None,
        )
        assert matching_end is not None, f"Claim path not found: {key}"
        value = value[".".join(components[index:matching_end])]
        index = matching_end
    return str(value)


def _derived_value(key: str, source_file: str) -> str:
    plans = _read_csv(ROOT / "reports" / "generated" / "plans_by_student.csv")
    profile_ids = {row["student_id"] for row in plans}
    if key == "derived:plan_row_count":
        return str(len(plans))
    if key == "derived:profile_count":
        return str(len(profile_ids))
    if key == "derived:mc_profile_count":
        return str(
            len({
                row["student_id"]
                for row in _read_csv(ROOT / "reports" / "generated" / "mc_results.csv")
            })
        )
    if key == "derived:high_risk_plan_count":
        return str(sum(row["risk_level"] == "CAO" for row in build_risk_rows(plans)))
    if key in {"derived:identical_profile_count", "derived:distinct_plan_signatures"}:
        identical, distinct, _ = plan_signatures(plans)
        return str(
            identical if key == "derived:identical_profile_count" else distinct
        )
    if key == "derived:confidence_level_percent":
        config = yaml.safe_load(
            (ROOT / source_file).read_text(encoding="utf-8-sig")
        )["monte_carlo"]
        return str(config["confidence_level"] * 100)
    raise AssertionError(f"Unrecognized derived claim key: {key}")


def test_every_prose_claim_matches_its_source() -> None:
    claims = _read_csv(CLAIMS_PATH)
    assert len(claims) >= 30
    required = {"location", "number", "source_file", "key", "source_value"}
    assert claims and required <= set(claims[0])

    for claim in claims:
        source_value = (
            _derived_value(claim["key"], claim["source_file"])
            if claim["key"].startswith("derived:")
            else _source_value(claim["source_file"], claim["key"])
        )
        assert claim["source_value"] == source_value, claim
        try:
            claim_number = Decimal(claim["number"])
            raw_number = Decimal(source_value)
            rounded_number = Decimal(f"{float(source_value):.4f}")
            assert claim_number in {raw_number, rounded_number}, claim
        except InvalidOperation:
            assert claim["number"] == source_value, claim

    questions = (
        ROOT / "reports" / "generated" / "final_questions_for_co.md"
    ).read_text(encoding="utf-8-sig")
    assert "Dropout recall 0,6655 ở nhị phân, chênh 0,0458" not in questions
    assert "0,0458" not in questions


def test_saved_risk_levels_match_required_thresholds() -> None:
    for row in _read_csv(ROOT / "reports" / "generated" / "final_risk_levels.csv"):
        assert row["risk_level"] == risk_level(row)
