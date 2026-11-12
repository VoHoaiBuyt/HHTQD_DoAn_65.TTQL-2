from __future__ import annotations

from core.metrics import read_metrics, write_metrics


def test_metrics_json_round_trip(tmp_path) -> None:
    path = tmp_path / "generated" / "metrics.json"
    metrics = {
        "source_label": "OFFICIAL (NTU)",
        "counts": {"courses": 101, "warnings": 3},
    }
    write_metrics(metrics, path)
    assert read_metrics(path) == metrics
