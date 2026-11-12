"""HK1-stratified pooled pass-rate baseline, fitted only on training rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from core.ml_data import ROOT


MODEL_PATH = ROOT / "models" / "pass_probability.json"
TIERS = ("Thấp", "Trung bình", "Cao")
APPROVED = "Curricular units 1st sem (approved)"
ENROLLED = "Curricular units 1st sem (enrolled)"
APPROVED_2 = "Curricular units 2nd sem (approved)"
ENROLLED_2 = "Curricular units 2nd sem (enrolled)"


def _tier(value: float, thresholds: list[float]) -> str:
    if value < thresholds[0]:
        return TIERS[0]
    if value < thresholds[1]:
        return TIERS[1]
    return TIERS[2]


def fit_pass_probability(train_frame: Any) -> dict[str, Any]:
    required = {APPROVED, ENROLLED, APPROVED_2, ENROLLED_2}
    missing = required - set(train_frame.columns)
    if missing:
        raise ValueError(f"Missing pass-rate fields: {sorted(missing)}")
    enrolled = train_frame[ENROLLED].to_numpy(dtype=float)
    approved = train_frame[APPROVED].to_numpy(dtype=float)
    ratios = np.divide(
        approved,
        enrolled,
        out=np.zeros_like(approved, dtype=float),
        where=enrolled > 0,
    )
    eligible = enrolled > 0
    if not eligible.any():
        raise ValueError("No training students have HK1 enrollment")
    cut_points = np.quantile(ratios[eligible], [1 / 3, 2 / 3]).tolist()
    tier_labels = np.array([_tier(value, cut_points) for value in ratios])
    strata: dict[str, dict[str, int]] = {}
    for tier in TIERS:
        rows = (tier_labels == tier) & (train_frame[ENROLLED_2].to_numpy() > 0)
        strata[tier] = {
            "students": int(rows.sum()),
            "approved_units": int(train_frame.loc[rows, APPROVED_2].sum()),
            "enrolled_units": int(train_frame.loc[rows, ENROLLED_2].sum()),
        }
    model = {
        "fit_scope": "train_only",
        "hk1_ability_feature": "approved / enrolled in semester 1",
        "thresholds": {"low_max": float(cut_points[0]), "medium_max": float(cut_points[1])},
        "minimum_students_per_stratum": 30,
        "strata": strata,
        "includes_later_dropout": True,
        "dropout_note": "M3' gồm cả sinh viên sau đó Dropout; sinh viên không còn quan sát HK2 bị loại khỏi mẫu HK2.",
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return model


def _pooled_rate(model: dict[str, Any], tier: str) -> float | None:
    center = TIERS.index(tier)
    for radius in range(len(TIERS)):
        names = [
            TIERS[index]
            for index in range(len(TIERS))
            if abs(index - center) <= radius
        ]
        selected = [model["strata"][name] for name in names]
        students = sum(int(item["students"]) for item in selected)
        enrolled = sum(int(item["enrolled_units"]) for item in selected)
        approved = sum(int(item["approved_units"]) for item in selected)
        if students >= int(model["minimum_students_per_stratum"]) and enrolled > 0:
            return approved / enrolled
    return None


def pass_probability_table(model: dict[str, Any]) -> list[dict[str, Any]]:
    table = []
    for tier in TIERS:
        center = TIERS.index(tier)
        pooled_tiers: list[str] = []
        pooled_students = 0
        pooled_approved = 0
        pooled_enrolled = 0
        for radius in range(len(TIERS)):
            pooled_tiers = [
                TIERS[index]
                for index in range(len(TIERS))
                if abs(index - center) <= radius
            ]
            selected = [model["strata"][name] for name in pooled_tiers]
            pooled_students = sum(int(item["students"]) for item in selected)
            pooled_approved = sum(int(item["approved_units"]) for item in selected)
            pooled_enrolled = sum(int(item["enrolled_units"]) for item in selected)
            if (
                pooled_students >= int(model["minimum_students_per_stratum"])
                and pooled_enrolled > 0
            ):
                break
        table.append(
            {
                "tier": tier,
                "merged_tiers": pooled_tiers,
                "n_students": pooled_students,
                "approved_units_hk2": pooled_approved,
                "enrolled_units_hk2": pooled_enrolled,
                "pooled_pass_rate": (
                    pooled_approved / pooled_enrolled if pooled_enrolled else None
                ),
                "estimable": (
                    pooled_students >= int(model["minimum_students_per_stratum"])
                    and pooled_enrolled > 0
                ),
            }
        )
    return table


def p_student_pass(
    features: dict[str, Any],
    *,
    model: dict[str, Any] | None = None,
) -> float | None:
    if model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Train the baseline before prediction: {MODEL_PATH}"
            )
        model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    approved = float(features.get(APPROVED, 0) or 0)
    enrolled = float(features.get(ENROLLED, 0) or 0)
    if enrolled <= 0:
        return None
    ability = min(1.0, max(0.0, approved / enrolled))
    tier = _tier(ability, [model["thresholds"]["low_max"], model["thresholds"]["medium_max"]])
    return _pooled_rate(model, tier)
