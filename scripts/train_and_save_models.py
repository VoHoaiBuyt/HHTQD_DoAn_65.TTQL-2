"""Fit the exploratory models once and save a serving bundle for the UI."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.risk_to_plan_exploration import (  # noqa: E402
    HK1_APPROVED,
    HK1_ENROLLED,
    HK2_APPROVED,
    HK2_ENROLLED,
    SEED,
    _ability_tiers,
    _difficulty_factors,
    _fit_dropout_model,
    _fit_pass_rate_model,
    _load_exploration_config,
    _load_real_data,
    _read_csv,
    COURSES_PATH,
)
from src.optimize.plan_risk import M3_ABILITY_ORDER  # noqa: E402

ARTIFACTS_DIR = ROOT / "artifacts"
BUNDLE_PATH = ARTIFACTS_DIR / "risk_bundle.joblib"
METADATA_PATH = ARTIFACTS_DIR / "model_metadata.json"


def _pooled_strata(data: pd.DataFrame, tiers: pd.Series) -> dict[str, dict[str, int]]:
    pooled: dict[str, dict[str, int]] = {}
    for label in M3_ABILITY_ORDER:
        subset = data[(tiers == label) & (data[HK2_ENROLLED] > 0)]
        pooled[label] = {
            "students": int(len(subset)),
            "approved_units": int(subset[HK2_APPROVED].sum()),
            "enrolled_units": int(subset[HK2_ENROLLED].sum()),
        }
    return pooled


def main() -> None:
    data, features, categories, numeric = _load_real_data()
    exploration_config = _load_exploration_config()
    dropout = _fit_dropout_model(
        data, features, categories, numeric, exploration_config
    )
    pass_rate = _fit_pass_rate_model(data, features, categories, numeric)
    difficulty_factors, _ = _difficulty_factors()

    tiers, cut_points = _ability_tiers(data)
    pooled = _pooled_strata(data, tiers)
    average_credits = float(
        pd.to_numeric(_read_csv(COURSES_PATH)["credits"]).mean()
    )

    warnings = dropout["risk_tier_validation_thresholds"]
    bundle = {
        "bundle_version": 1,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "data_label": "REAL (UCI-697)",
        "curriculum_label": "SIMULATED",
        "feature_count": len(features),
        "features": features,
        "categories": categories,
        "numeric": numeric,
        "dropout_model": dropout["full_model_for_persona_sanity_only"],
        "pass_rate_model": pass_rate["full_model_for_persona_sanity_only"],
        "risk_calibrator": warnings["risk_probability_calibrator"],
        "risk_metrics": {
            "cv_accuracy_mean": dropout["cv_accuracy_mean"],
            "cv_f1_macro_mean": dropout["cv_f1_macro_mean"],
            "cv_f1_dropout_mean": dropout["cv_f1_dropout_mean"],
            "holdout_precision_dropout": dropout["holdout_precision_dropout"],
            "holdout_recall_dropout": dropout["holdout_recall_dropout"],
            "holdout_f1_dropout": dropout["holdout_f1_dropout"],
            "brier_dropout": dropout["brier_dropout"],
        },
        "pass_rate_metrics": {
            "holdout_mae": pass_rate["holdout_mae"],
            "holdout_rmse": pass_rate["holdout_rmse"],
            "eligible_students": pass_rate["eligible_students"],
            "excluded_zero_enrollment": pass_rate["excluded_zero_enrollment"],
        },
        "ability_cut_points": [float(value) for value in cut_points],
        "pooled_strata": pooled,
        "difficulty_factors": difficulty_factors,
        "average_credits_per_unit": average_credits,
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    metadata = {
        key: value
        for key, value in bundle.items()
        if key not in {"dropout_model", "pass_rate_model", "risk_calibrator"}
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Saved bundle: {BUNDLE_PATH}")
    print(f"Saved metadata: {METADATA_PATH}")
    print(
        f"Features: {len(features)} | pass-rate n={pass_rate['eligible_students']} | "
        f"mean credits/course={average_credits:.4f}"
    )


if __name__ == "__main__":
    main()
