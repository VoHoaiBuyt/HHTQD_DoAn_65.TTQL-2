"""Loadable risk inference for the model selected on the validation partition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from core.ml_data import ROOT


MODEL_PATH = ROOT / "models" / "early_warning.joblib"


def apply_calibration(
    probabilities: np.ndarray,
    calibrators: dict[str, Any],
    method: str,
    class_count: int,
) -> np.ndarray:
    if method not in {"platt", "isotonic", "uncalibrated"}:
        raise ValueError(f"Unsupported calibration method: {method}")
    if method == "uncalibrated":
        return probabilities.copy()
    calibrated = np.zeros_like(probabilities, dtype=float)
    columns = [1] if class_count == 2 else list(range(class_count))
    for column in columns:
        calibrator = calibrators[str(column)]
        scores = probabilities[:, column]
        if isinstance(calibrator, IsotonicRegression):
            values = calibrator.predict(scores)
        elif isinstance(calibrator, LogisticRegression):
            values = calibrator.predict_proba(scores.reshape(-1, 1))[:, 1]
        else:
            raise TypeError(f"Unsupported calibration object: {type(calibrator).__name__}")
        calibrated[:, column] = np.clip(values, 0.0, 1.0)
    if class_count == 2:
        calibrated[:, 0] = 1.0 - calibrated[:, 1]
    else:
        totals = calibrated.sum(axis=1)
        calibrated = np.divide(
            calibrated,
            totals[:, None],
            out=np.full_like(calibrated, 1.0 / class_count),
            where=totals[:, None] > 0,
        )
    return calibrated


def predict_risk(
    features: dict[str, Any],
    *,
    model_path: Path = MODEL_PATH,
) -> dict[str, Any]:
    if not model_path.exists():
        raise FileNotFoundError(f"Trained model is unavailable: {model_path}")
    bundle = joblib.load(model_path)
    missing = set(bundle["feature_columns"]) - set(features)
    if missing:
        raise ValueError(f"Missing required prediction features: {sorted(missing)}")
    frame = pd.DataFrame(
        [{column: features[column] for column in bundle["feature_columns"]}]
    )
    raw = bundle["pipeline"].predict_proba(frame)
    calibration = bundle["calibration"]
    calibrated = apply_calibration(
        raw,
        calibration["calibrators"],
        calibration["method"],
        int(bundle["class_count"]),
    )[0]
    class_names = bundle["class_names"]
    class_probs = {
        class_names[index]: float(value) for index, value in enumerate(calibrated)
    }
    probability_index = 1 if bundle["class_count"] == 2 else 0
    p_dropout = float(calibrated[probability_index])
    thresholds = bundle["warning_thresholds"]
    warning_tier = (
        "high"
        if p_dropout >= float(thresholds["high"])
        else "medium"
        if p_dropout >= float(thresholds["medium"])
        else "low"
    )
    transformed = bundle["pipeline"].named_steps["preprocess"].transform(frame)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    explainer = shap.Explainer(
        bundle["pipeline"].named_steps["model"],
        bundle["shap_background"],
        feature_names=bundle["feature_names_out"],
    )
    explanation = explainer(transformed)
    values = np.asarray(explanation.values)
    output_index = 1 if bundle["class_count"] == 2 else 0
    local_values = values[0, :, output_index] if values.ndim == 3 else values[0]
    shap_values = [
        {"feature": bundle["feature_names_out"][index], "value": float(value)}
        for index, value in enumerate(local_values)
    ]
    return {
        "p_dropout_calibrated": p_dropout,
        "class_probs": class_probs,
        "warning_tier": warning_tier,
        "threshold_used": float(bundle["threshold_used"]),
        "shap_values": shap_values,
        "model_version": bundle["model_version"],
        "scope_note": "ước lượng dựa trên kết quả học kỳ 1; hợp lệ ở mốc T1",
    }


def predict_risk_thresholds() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Trained model is unavailable: {MODEL_PATH}")
    bundle = joblib.load(MODEL_PATH)
    return {
        "threshold_used": bundle["threshold_used"],
        "warning_thresholds": bundle["warning_thresholds"],
        "selection_note": bundle["threshold_note"],
    }


def load_saved_model(model_path: Path = MODEL_PATH) -> dict[str, Any]:
    bundle = joblib.load(model_path)
    if not isinstance(bundle, dict) or "pipeline" not in bundle:
        raise ValueError(f"Invalid model bundle: {model_path}")
    return bundle
