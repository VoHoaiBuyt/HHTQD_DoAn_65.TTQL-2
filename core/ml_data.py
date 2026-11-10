"""Reproducible, manifest-backed splits for the independent UCI-697 task."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "uci_697" / "data.csv"
DICTIONARY_PATH = ROOT / "reports" / "data_dictionary.csv"
MANIFEST_PATH = ROOT / "data" / "processed" / "split_manifest.json"
TEST_LOG_PATH = ROOT / "reports" / "generated" / "test_evaluation_log.jsonl"
SEED = 20261105
TARGET = "Target"
EXCLUDED_FEATURES = {
    "Debtor",
    "Tuition fees up to date",
    "Scholarship holder",
    "Unemployment rate",
    "Inflation rate",
    "GDP",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_source() -> pd.DataFrame:
    frame = pd.read_csv(DATA_PATH, sep=";", encoding="utf-8-sig")
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def source_feature_columns(*, include_sensitivity_features: bool = False) -> list[str]:
    dictionary = pd.read_csv(DICTIONARY_PATH, encoding="utf-8-sig")
    dictionary["attribute_name"] = dictionary["attribute_name"].astype(str).str.strip()
    available = set(
        dictionary.loc[
            dictionary["available_at"].isin(["T0", "T1_known"]),
            "attribute_name",
        ]
    )
    source_columns = set(read_source().columns)
    candidates = sorted(available.intersection(source_columns) - {TARGET})
    excluded = set() if include_sensitivity_features else EXCLUDED_FEATURES
    columns = [
        column
        for column in candidates
        if column not in excluded
        and not column.startswith("Curricular units 2nd sem")
    ]
    if "post_outcome" in columns or "T1_decision" in columns:
        raise ValueError("Leakage feature found in selected model inputs")
    return columns


def _row_id(index: int) -> str:
    return f"uci697_row_{index:05d}"


def _row_hash(row: pd.Series) -> str:
    normalized = json.dumps(
        [None if pd.isna(value) else value for value in row.tolist()],
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()


def create_split_manifest(*, path: Path = MANIFEST_PATH) -> dict[str, Any]:
    frame = read_source()
    labels = frame[TARGET]
    row_indices = list(range(len(frame)))
    train_ids, remainder_ids = train_test_split(
        row_indices,
        test_size=0.4,
        random_state=SEED,
        stratify=labels,
    )
    val_ids, test_ids = train_test_split(
        remainder_ids,
        test_size=0.5,
        random_state=SEED,
        stratify=labels.iloc[remainder_ids],
    )
    splits = {
        "train": sorted(int(index) for index in train_ids),
        "validation": sorted(int(index) for index in val_ids),
        "test": sorted(int(index) for index in test_ids),
    }
    manifest = {
        "source": str(DATA_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _sha256_file(DATA_PATH),
        "seed": SEED,
        "fractions": {"train": 0.6, "validation": 0.2, "test": 0.2},
        "row_count": len(frame),
        "splits": {
            name: [
                {"id": _row_id(index), "row_hash": _row_hash(frame.iloc[index])}
                for index in indices
            ]
            for name, indices in splits.items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return create_split_manifest(path=path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["source_sha256"] != _sha256_file(DATA_PATH):
        raise ValueError("UCI-697 source hash differs from split_manifest.json")
    frame = read_source()
    all_ids: set[str] = set()
    for split_name, rows in manifest["splits"].items():
        for item in rows:
            row_id = str(item["id"])
            try:
                index = int(row_id.rsplit("_", 1)[1])
            except (ValueError, IndexError) as error:
                raise ValueError(f"Invalid manifest row ID: {row_id}") from error
            if not 0 <= index < len(frame) or row_id in all_ids:
                raise ValueError(f"Invalid or overlapping split ID: {row_id}")
            if item["row_hash"] != _row_hash(frame.iloc[index]):
                raise ValueError(f"Row hash mismatch for {row_id}")
            all_ids.add(row_id)
    if len(all_ids) != len(frame):
        raise ValueError("Split manifest does not cover every source row exactly once")
    return manifest


def load_split(
    split_name: str,
    *,
    manifest_path: Path = MANIFEST_PATH,
    test_log_path: Path = TEST_LOG_PATH,
) -> pd.DataFrame:
    manifest = load_manifest(manifest_path)
    if split_name not in {"train", "validation", "test"}:
        raise ValueError(f"Unsupported split name: {split_name}")
    if split_name == "test":
        if os.environ.get("ALLOW_TEST_EVAL") != "1":
            raise PermissionError("Test evaluation requires ALLOW_TEST_EVAL=1")
        if test_log_path.exists() and test_log_path.stat().st_size:
            raise RuntimeError(
                "The test split has already been used; this project permits one test evaluation."
            )
        test_log_path.parent.mkdir(parents=True, exist_ok=True)
        with test_log_path.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "split": "test",
                        "manifest_sha256": hashlib.sha256(
                            json.dumps(manifest, sort_keys=True).encode("utf-8")
                        ).hexdigest(),
                    }
                )
                + "\n"
            )
    indices = [
        int(item["id"].rsplit("_", 1)[1])
        for item in manifest["splits"][split_name]
    ]
    frame = read_source().iloc[indices].copy()
    frame.insert(0, "_row_id", [_row_id(index) for index in indices])
    return frame.reset_index(drop=True)


def labels_and_row_ids(split_name: str) -> tuple[list[str], list[str]]:
    frame = load_split(split_name)
    return frame[TARGET].astype(str).tolist(), frame["_row_id"].astype(str).tolist()
