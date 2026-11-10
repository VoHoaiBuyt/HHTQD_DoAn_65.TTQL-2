from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from scripts.final_claims import GENERATED, ROOT, plan_signatures, risk_level


CLAIMS_PATH = GENERATED / "prose_claims.csv"
PLANS_PATH = GENERATED / "plans_by_student.csv"


def _read_claims() -> list[dict[str, str]]:
    with CLAIMS_PATH.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _read_plans() -> list[dict[str, str]]:
    with PLANS_PATH.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _resolve_json(path: Path, key: str) -> object:
    value: object = json.loads(path.read_text(encoding="utf-8-sig"))
    tokens = key.split(".")

    def resolve(current: object, offset: int) -> object:
        if offset == len(tokens):
            return current
        if not isinstance(current, dict):
            raise AssertionError(f"JSON key {key!r} missing in {path}")
        for end in range(len(tokens), offset, -1):
            candidate = ".".join(tokens[offset:end])
            if candidate in current:
                return resolve(current[candidate], end)
        raise AssertionError(f"JSON key {key!r} missing in {path}")

    return resolve(value, 0)


def _resolve_claim(claim: dict[str, str]) -> object:
    source = claim["source_file"]
    key = claim["key"]
    if key.startswith("derived:"):
        if key == "derived:confidence_level_percent":
            config = yaml.safe_load(
                (ROOT / source).read_text(encoding="utf-8-sig")
            )
            return config["monte_carlo"]["confidence_level"] * 100
        plans = _read_plans()
        identical, distinct, _ = plan_signatures(plans)
        if key == "derived:identical_profile_count":
            return identical
        if key == "derived:distinct_plan_signatures":
            return distinct
        if key == "derived:profile_count":
            return len({row["student_id"] for row in plans})
        if key == "derived:plan_row_count":
            return len(plans)
        if key == "derived:high_risk_plan_count":
            return sum(risk_level(row) == "CAO" for row in plans)
        if key == "derived:mc_profile_count":
            with (GENERATED / "mc_results.csv").open(encoding="utf-8-sig", newline="") as stream:
                mc_rows = list(csv.DictReader(stream))
            return len({row["student_id"] for row in mc_rows})
        raise AssertionError(f"Unknown derived claim key: {key}")

    path = ROOT / source
    if path.suffix.lower() == ".json":
        return _resolve_json(path, key)
    if path.suffix.lower() in {".yaml", ".yml"}:
        value: object = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        tokens = key.split(".")
        for token in tokens:
            if isinstance(value, dict) and token in value:
                value = value[token]
            elif isinstance(value, list) and token.isdigit():
                value = value[int(token)]
            else:
                raise AssertionError(f"YAML key {key!r} missing in {path}")
        return value
    if path.suffix.lower() == ".csv":
        if source.endswith("plans_by_student.csv"):
            rows = _read_plans()
        else:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        parts = dict(part.split("=", 1) for part in key.split(";"))
        field = parts.pop("field")
        matches = [
            row for row in rows
            if all(row.get(name) == value for name, value in parts.items())
        ]
        if len(matches) != 1:
            raise AssertionError(f"Expected one source row for claim {claim}, got {len(matches)}")
        return matches[0][field]
    raise AssertionError(f"Unsupported claim source: {source}")


def test_every_prose_claim_matches_its_source() -> None:
    claims = _read_claims()
    assert len(claims) >= 30, f"Expected at least 30 claims, got {len(claims)}"
    assert all(claim["location"] and claim["number"] and claim["source_file"] and claim["key"] for claim in claims)
    for claim in claims:
        value = _resolve_claim(claim)
        expected = claim["source_value"]
        if isinstance(value, (int, float)):
            assert abs(float(value) - float(expected)) <= 1e-12, claim
            assert abs(float(claim["number"]) - float(value)) <= 0.0000500001, claim
        else:
            assert str(value) == expected, claim


def test_all_plan_risk_levels_match_documented_thresholds() -> None:
    plans = _read_plans()
    risk_path = GENERATED / "final_risk_levels.csv"
    with risk_path.open(encoding="utf-8-sig", newline="") as stream:
        risk_rows = list(csv.DictReader(stream))
    expected = {
        (row["student_id"], row["plan_type"]): risk_level(row)
        for row in plans
    }
    actual = {
        (row["student_id"], row["plan_type"]): row["risk_level"]
        for row in risk_rows
    }
    assert len(risk_rows) == len(plans) == 27
    assert actual == expected


def test_identical_profile_statement_matches_plan_outputs() -> None:
    plans = _read_plans()
    identical, distinct, repeated = plan_signatures(plans)
    assert identical == 3
    assert distinct == 7
    assert repeated == ["V2-001", "V2-002", "V2-004"]


def main() -> None:
    test_every_prose_claim_matches_its_source()
    test_all_plan_risk_levels_match_documented_thresholds()
    test_identical_profile_statement_matches_plan_outputs()
    print(f"PROSE_CLAIMS: PASS ({len(_read_claims())} sourced rows)")
    print("RISK_LEVELS: PASS (27/27 plans)")
    print("PLAN_SIGNATURES: PASS (3 identical profiles; 7 distinct result patterns)")


if __name__ == "__main__":
    main()
