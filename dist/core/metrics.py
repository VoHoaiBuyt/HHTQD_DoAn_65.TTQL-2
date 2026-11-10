"""Read and write generated project metrics."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "reports" / "generated" / "metrics.json"


def read_metrics(path: Path = METRICS_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Metrics document must be a JSON object: {path}")
    return value


def write_metrics(metrics: dict[str, Any], path: Path = METRICS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as file:
        temporary_path = Path(file.name)
        json.dump(metrics, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")
    try:
        os.replace(temporary_path, path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


def update_metrics(updates: dict[str, Any], path: Path = METRICS_PATH) -> None:
    current = read_metrics(path) if path.exists() else {}
    current.update(updates)
    write_metrics(current, path)
