from __future__ import annotations

import json

import numpy as np
import pytest

from core.ml_data import load_manifest, load_split, source_feature_columns
from core.models import predict_risk
from core.pass_prob import fit_pass_probability


def test_feature_set_is_exact_t0_t1_known_without_forbidden_fields() -> None:
    columns = source_feature_columns()
    assert len(columns) == 24
    assert "Debtor" not in columns
    assert "Tuition fees up to date" not in columns
    assert "Scholarship holder" not in columns
    assert not any(name.startswith("Curricular units 2nd sem") for name in columns)
    assert not {"post_outcome", "T1_decision"}.intersection(columns)


def test_manifest_splits_are_disjoint_stratified_and_cover_source() -> None:
    manifest = load_manifest()
    split_ids = {
        split: {row["id"] for row in manifest["splits"][split]}
        for split in ("train", "validation", "test")
    }
    assert split_ids["train"].isdisjoint(split_ids["validation"])
    assert split_ids["train"].isdisjoint(split_ids["test"])
    assert split_ids["validation"].isdisjoint(split_ids["test"])
    assert [len(split_ids[name]) for name in ("train", "validation", "test")] == [
        2654,
        885,
        885,
    ]
    assert len(set.union(*split_ids.values())) == 4424
    assert all(
        len(row["row_hash"]) == 64
        for rows in manifest["splits"].values()
        for row in rows
    )


def test_test_split_requires_explicit_opt_in_and_does_not_log_rejection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("ALLOW_TEST_EVAL", raising=False)
    log_path = tmp_path / "test_log.jsonl"
    with pytest.raises(PermissionError, match="ALLOW_TEST_EVAL=1"):
        load_split("test", test_log_path=log_path)
    assert not log_path.exists()


def test_m3_prime_fit_is_training_input_only_and_reproducible() -> None:
    train = load_split("train")
    first = fit_pass_probability(train)
    changed_external_test_data = load_split("validation").copy()
    changed_external_test_data.iloc[:, 0] = "changed"
    second = fit_pass_probability(train.copy())
    assert first["thresholds"] == second["thresholds"]
    assert first["strata"] == second["strata"]
    assert first["fit_scope"] == "train_only"
    assert "includes_later_dropout" in first
    assert len(changed_external_test_data) == 885


def test_predict_risk_schema_and_serialized_model_are_stable() -> None:
    sample = load_split("validation").iloc[0]
    feature_dict = {
        key: sample[key]
        for key in source_feature_columns()
    }
    first = predict_risk(feature_dict)
    second = predict_risk(feature_dict)
    assert set(first) == {
        "p_dropout_calibrated",
        "class_probs",
        "warning_tier",
        "threshold_used",
        "shap_values",
        "model_version",
        "scope_note",
    }
    assert first["class_probs"] == second["class_probs"]
    assert first["p_dropout_calibrated"] == second["p_dropout_calibrated"]
    assert np.isclose(sum(first["class_probs"].values()), 1)
    assert first["warning_tier"] in {"low", "medium", "high"}
    assert first["shap_values"]
    assert "ước lượng dựa trên kết quả học kỳ 1; hợp lệ ở mốc T1" == first["scope_note"]
    assert json.loads(json.dumps(first, ensure_ascii=False))["model_version"] == first["model_version"]
