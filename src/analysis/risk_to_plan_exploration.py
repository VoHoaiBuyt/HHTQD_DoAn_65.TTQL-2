"""Exploratory REAL (UCI-697) models and SIMULATED plan sanity checks."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
)
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    cross_validate,
    cross_val_predict,
    train_test_split,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.optimize.plan_risk import (  # noqa: E402
    credits_to_curricular_units,
    m3_prime_probability,
    plan_risk,
)

SEED = 20261105
DATA_PATH = ROOT / "data" / "raw" / "uci_697" / "data.csv"
DICTIONARY_PATH = ROOT / "reports" / "data_dictionary.csv"
COURSES_PATH = ROOT / "data" / "simulated" / "courses.csv"
PREREQUISITES_PATH = ROOT / "data" / "simulated" / "prerequisites.csv"
PROGRESS_PATH = ROOT / "data" / "simulated" / "student_progress.csv"
PROFILE_PATH = ROOT / "data" / "simulated" / "student_profile.csv"
CONFIG_PATH = ROOT / "src" / "config" / "credit_rules.yaml"

CATEGORICAL_FEATURES = {
    "Marital status",
    "Application mode",
    "Application order",
    "Course",
    "Daytime/evening attendance",
    "Previous qualification",
    "Nacionality",
    "Mother's qualification",
    "Father's qualification",
    "Mother's occupation",
    "Father's occupation",
    "Displaced",
    "Educational special needs",
    "Gender",
    "International",
}
HK1_APPROVED = "Curricular units 1st sem (approved)"
HK1_ENROLLED = "Curricular units 1st sem (enrolled)"
HK1_GRADE = "Curricular units 1st sem (grade)"
HK2_ENROLLED = "Curricular units 2nd sem (enrolled)"
HK2_APPROVED = "Curricular units 2nd sem (approved)"
HK2_WITHOUT_EVALUATIONS = "Curricular units 2nd sem (without evaluations)"
UNVERIFIED_FEATURES = {
    "Debtor",
    "Tuition fees up to date",
    "Scholarship holder",
    "Unemployment rate",
    "Inflation rate",
    "GDP",
}
LOAD_BANDS = ["0", "1-5", "6-7", "8+"]
ABILITY_LABELS = ["Thấp", "Trung bình", "Cao"]

def _load_exploration_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    exploration = config["risk_to_plan_exploration"]
    values = config["scenario_credit_targets"]["values"]
    return {
        "base_load_lambda": float(exploration["base_load_lambda"]["value"]),
        "load_lambdas": [float(value) for value in exploration["load_lambda_sensitivity"]["values"]],
        "difficulty_multipliers": [
            float(value)
            for value in exploration["difficulty_multiplier_sensitivity"]["values"]
        ],
        "retake_multipliers": [
            float(value)
            for value in exploration["retake_multiplier_sensitivity"]["values"]
        ],
        "scenario_credits": [int(value) for value in values],
        "m3_minimum_students": int(
            exploration["m3_prime"]["minimum_students"]["value"]
        ),
        "restriction_minimum_ppv": float(
            config["rule_engine"]["risk_restriction"]["minimum_ppv"]["value"]
        ),
        "restriction_minimum_count": int(
            config["rule_engine"]["risk_restriction"]["minimum_count"]["value"]
        ),
        "restriction_minimum_probability": float(
            config["rule_engine"]["risk_restriction"]["minimum_probability"]["value"]
        ),
        "restriction_probability_grid": [
            float(value)
            for value in config["rule_engine"]["risk_restriction"][
                "probability_grid"
            ]["values"]
        ],
    }


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_real_data() -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    data = pd.read_csv(DATA_PATH, sep=";")
    data.columns = data.columns.str.strip()
    with DICTIONARY_PATH.open(encoding="utf-8-sig", newline="") as file:
        dictionary = list(csv.DictReader(file))
    features = [
        row["attribute_name"]
        for row in dictionary
        if row["available_at"] in {"T0", "T1_known"}
    ]
    if not features:
        raise ValueError("Không tìm thấy feature T0 + T1_known trong data_dictionary.csv")
    forbidden = UNVERIFIED_FEATURES | {
        "Curricular units 2nd sem (credited)",
        HK2_ENROLLED,
        "Curricular units 2nd sem (evaluations)",
        HK2_APPROVED,
        "Curricular units 2nd sem (grade)",
        HK2_WITHOUT_EVALUATIONS,
        "Target",
    }
    if forbidden.intersection(features):
        raise ValueError(f"Feature leakage/không rõ thời điểm: {sorted(forbidden.intersection(features))}")
    categories = [name for name in features if name in CATEGORICAL_FEATURES]
    numeric = [name for name in features if name not in categories]
    return data, features, categories, numeric


def _preprocessor(categories: list[str], numeric: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categories),
            ("numeric", StandardScaler(), numeric),
        ]
    )


def _dropout_f1(estimator: Any, x: pd.DataFrame, y: pd.Series) -> float:
    predicted = estimator.predict(x)
    return float(f1_score(y.eq("Dropout"), predicted == "Dropout", zero_division=0))


def _fit_dropout_model(
    data: pd.DataFrame,
    features: list[str],
    categories: list[str],
    numeric: list[str],
    exploration_config: dict[str, Any],
) -> dict[str, Any]:
    x = data[features]
    y = data["Target"]
    train_indices, test_indices = train_test_split(
        np.arange(len(data)),
        test_size=0.2,
        random_state=SEED,
        stratify=y,
    )
    train_x, train_y = x.iloc[train_indices], y.iloc[train_indices]
    test_x, test_y = x.iloc[test_indices], y.iloc[test_indices]
    model = make_pipeline(
        _preprocessor(categories, numeric),
        LogisticRegression(max_iter=2000, random_state=SEED),
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    class_names = sorted(train_y.unique().tolist())
    dropout_index = class_names.index("Dropout")
    oof_probabilities = cross_val_predict(
        model,
        train_x,
        train_y,
        cv=cv,
        method="predict_proba",
        n_jobs=1,
    )[:, dropout_index]

    def threshold_for_recall(target_recall: float) -> float:
        actual_dropout = train_y.eq("Dropout").to_numpy()
        feasible = [
            float(threshold)
            for threshold in np.unique(oof_probabilities)
            if recall_score(
                actual_dropout,
                oof_probabilities >= threshold,
                zero_division=0,
            )
            >= target_recall
        ]
        if not feasible:
            raise ValueError(f"No validation threshold meets recall={target_recall}")
        return max(feasible)

    high_threshold = threshold_for_recall(0.90)
    medium_threshold = threshold_for_recall(0.98)
    binary_dropout = train_y.eq("Dropout").to_numpy(dtype=float)
    risk_calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        oof_probabilities,
        binary_dropout,
    )
    calibrated_oof_probabilities = np.clip(
        risk_calibrator.predict(oof_probabilities), 0.0, 1.0
    )

    def warning_tier_table() -> pd.DataFrame:
        tiers = np.select(
            [
                oof_probabilities < medium_threshold,
                oof_probabilities < high_threshold,
            ],
            ["Thấp", "Trung bình"],
            default="Cao",
        )
        frame = pd.DataFrame(
            {
                "tier": tiers,
                "dropout": binary_dropout,
            }
        )
        result = frame.groupby("tier", sort=False).agg(
            students=("dropout", "size"),
            dropout_count=("dropout", "sum"),
            observed_dropout_rate=("dropout", "mean"),
        )
        result["student_share"] = result["students"] / len(frame)
        result["ppv"] = result["observed_dropout_rate"]
        result.insert(0, "data_label", "REAL (UCI-697), train OOF")
        return result.reset_index()

    def choose_restriction_threshold() -> tuple[float | None, pd.DataFrame]:
        valid = [
            threshold
            for threshold in exploration_config["restriction_probability_grid"]
            if threshold >= exploration_config["restriction_minimum_probability"]
        ]
        rows = []
        for threshold in valid:
            selected = calibrated_oof_probabilities >= threshold
            count = int(selected.sum())
            if count < exploration_config["restriction_minimum_count"]:
                continue
            rows.append(
                {
                    "data_label": "REAL (UCI-697), train OOF calibrated",
                    "threshold": float(threshold),
                    "students": count,
                    "student_share": float(selected.mean()),
                    "dropout_count": int(binary_dropout[selected].sum()),
                    "ppv": float(binary_dropout[selected].mean()),
                    "recall": float(
                        recall_score(
                            binary_dropout,
                            selected,
                            zero_division=0,
                        )
                    ),
                }
            )
        table = pd.DataFrame(rows)
        qualified = table.loc[
            table["ppv"] >= exploration_config["restriction_minimum_ppv"]
        ]
        threshold = (
            float(qualified.iloc[0]["threshold"])
            if not qualified.empty
            else None
        )
        return threshold, table

    restriction_threshold, restriction_sensitivity = (
        choose_restriction_threshold()
    )
    base_rate = float(binary_dropout.mean())
    near_base = (
        (calibrated_oof_probabilities >= base_rate - 0.02)
        & (calibrated_oof_probabilities <= base_rate + 0.02)
    )
    restriction_validation = {
        "base_dropout_rate": base_rate,
        "near_base_count": int(near_base.sum()),
        "near_base_restricted_count": int(
            np.sum(
                near_base
                & (
                    calibrated_oof_probabilities
                    >= (
                        restriction_threshold
                        if restriction_threshold is not None
                        else 1.0
                    )
                )
            )
        ),
        "near_base_probability_band": [base_rate - 0.02, base_rate + 0.02],
    }
    cv_result = cross_validate(
        model,
        train_x,
        train_y,
        cv=cv,
        scoring={
            "accuracy": "accuracy",
            "f1_macro": "f1_macro",
            "f1_dropout": _dropout_f1,
        },
        n_jobs=1,
    )
    model.fit(train_x, train_y)
    predictions = model.predict(test_x)
    probabilities = model.predict_proba(test_x)
    class_names = list(model[-1].classes_)
    dropout_index = class_names.index("Dropout")
    true_dropout = test_y.eq("Dropout")
    p_dropout = probabilities[:, dropout_index]
    observed_fraction, predicted_mean = _quantile_calibration(true_dropout, p_dropout)
    metrics = {
        "seed": SEED,
        "feature_count": len(features),
        "features": features,
        "train_size": len(train_indices),
        "test_size": len(test_indices),
        "cv_accuracy_mean": float(cv_result["test_accuracy"].mean()),
        "cv_f1_macro_mean": float(cv_result["test_f1_macro"].mean()),
        "cv_f1_dropout_mean": float(cv_result["test_f1_dropout"].mean()),
        "holdout_precision_dropout": float(
            precision_score(true_dropout, predictions == "Dropout", zero_division=0)
        ),
        "holdout_recall_dropout": float(
            recall_score(true_dropout, predictions == "Dropout", zero_division=0)
        ),
        "holdout_f1_dropout": float(
            f1_score(true_dropout, predictions == "Dropout", zero_division=0)
        ),
        "confusion_matrix": confusion_matrix(
            test_y,
            predictions,
            labels=["Dropout", "Enrolled", "Graduate"],
        ),
        "confusion_labels": ["Dropout", "Enrolled", "Graduate"],
        "brier_dropout": float(brier_score_loss(true_dropout, p_dropout)),
        "risk_tier_validation_thresholds": {
            "low_max_p_dropout": medium_threshold,
            "medium_max_p_dropout": high_threshold,
            "medium_recall_target": 0.98,
            "high_recall_target": 0.90,
            "validation_method": "5-fold stratified OOF on training split",
            "validation_recall_medium": float(
                recall_score(
                    train_y.eq("Dropout"),
                    oof_probabilities >= medium_threshold,
                    zero_division=0,
                )
            ),
            "validation_recall_high": float(
                recall_score(
                    train_y.eq("Dropout"),
                    oof_probabilities >= high_threshold,
                    zero_division=0,
                )
            ),
            "oof_warning_distribution": warning_tier_table(),
            "calibrated_restriction_threshold": restriction_threshold,
            "restriction_minimum_ppv": exploration_config[
                "restriction_minimum_ppv"
            ],
            "restriction_threshold_sensitivity": restriction_sensitivity,
            "restriction_near_base_check": restriction_validation,
            "calibrated_oof_probabilities": calibrated_oof_probabilities,
            "oof_binary_dropout": binary_dropout,
            "risk_probability_calibrator": risk_calibrator,
        },
        "calibration": pd.DataFrame(
            {
                "predicted_mean": predicted_mean,
                "observed_dropout_rate": observed_fraction,
            }
        ),
        "test_probabilities": p_dropout,
        "test_true_dropout": true_dropout,
        "test_indices": test_indices,
        "train_indices": train_indices,
        "test_y": test_y,
        "test_predictions": predictions,
        "model": model,
    }
    full_model = make_pipeline(
        _preprocessor(categories, numeric),
        LogisticRegression(max_iter=2000, random_state=SEED),
    ).fit(x, y)
    metrics["full_model_for_persona_sanity_only"] = full_model
    return metrics


def _quantile_calibration(
    actual: pd.Series | np.ndarray,
    predicted: np.ndarray,
    bins: int = 10,
) -> tuple[list[float], list[float]]:
    calibration = pd.DataFrame(
        {"actual": np.asarray(actual, dtype=float), "predicted": predicted}
    )
    calibration["bin"] = pd.qcut(
        calibration["predicted"].rank(method="first"),
        q=bins,
        labels=False,
        duplicates="drop",
    )
    grouped = calibration.groupby("bin", observed=True).agg(
        predicted_mean=("predicted", "mean"),
        observed_rate=("actual", "mean"),
    )
    return grouped["observed_rate"].tolist(), grouped["predicted_mean"].tolist()


def _fit_pass_rate_model(
    data: pd.DataFrame,
    features: list[str],
    categories: list[str],
    numeric: list[str],
) -> dict[str, Any]:
    enrolled = data[HK2_ENROLLED]
    eligible = enrolled > 0
    x = data.loc[eligible, features]
    y = (
        data.loc[eligible, HK2_APPROVED]
        / enrolled.loc[eligible]
    ).clip(0, 1)
    train_indices, test_indices = train_test_split(
        np.arange(len(x)),
        test_size=0.2,
        random_state=SEED,
    )
    train_x, train_y = x.iloc[train_indices], y.iloc[train_indices]
    test_x, test_y = x.iloc[test_indices], y.iloc[test_indices]
    model = make_pipeline(
        _preprocessor(categories, numeric),
        RandomForestRegressor(
            n_estimators=160,
            min_samples_leaf=8,
            max_features=0.8,
            random_state=SEED,
            n_jobs=-1,
        ),
    )
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_result = cross_validate(
        model,
        train_x,
        train_y,
        cv=cv,
        scoring={
            "mae": "neg_mean_absolute_error",
            "rmse": "neg_root_mean_squared_error",
        },
        n_jobs=1,
    )
    oof_prediction = np.clip(
        cross_val_predict(
            model,
            train_x,
            train_y,
            cv=cv,
            method="predict",
            n_jobs=1,
        ),
        0.0,
        1.0,
    )
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        oof_prediction, train_y.to_numpy()
    )
    model.fit(train_x, train_y)
    test_prediction = np.clip(model.predict(test_x), 0.0, 1.0)
    calibrated_prediction = np.clip(
        calibrator.predict(test_prediction), 0.0, 1.0
    )

    def calibration_deciles(actual: pd.Series, predicted: np.ndarray) -> pd.DataFrame:
        frame = pd.DataFrame(
            {"actual": actual.to_numpy(dtype=float), "predicted": predicted}
        )
        frame["decile"] = pd.qcut(
            frame["predicted"].rank(method="first"),
            q=10,
            labels=False,
            duplicates="drop",
        )
        grouped = frame.groupby("decile", observed=True).agg(
            student_count=("actual", "size"),
            mean_predicted=("predicted", "mean"),
            mean_observed=("actual", "mean"),
        )
        grouped.insert(0, "data_label", "REAL (UCI-697), holdout calibration")
        return grouped.reset_index()

    raw_calibration = calibration_deciles(test_y, test_prediction)
    calibrated_calibration = calibration_deciles(test_y, calibrated_prediction)

    def calibration_mae(table: pd.DataFrame) -> float:
        return float(
            np.average(
                np.abs(table["mean_predicted"] - table["mean_observed"]),
                weights=table["student_count"],
            )
        )

    full_model = make_pipeline(
        _preprocessor(categories, numeric),
        RandomForestRegressor(
            n_estimators=160,
            min_samples_leaf=8,
            max_features=0.8,
            random_state=SEED,
            n_jobs=-1,
        ),
    ).fit(x, y)
    return {
        "seed": SEED,
        "eligible_students": int(eligible.sum()),
        "excluded_zero_enrollment": int((~eligible).sum()),
        "cv_mae_mean": float(-cv_result["test_mae"].mean()),
        "cv_rmse_mean": float(-cv_result["test_rmse"].mean()),
        "holdout_mae": float(mean_absolute_error(test_y, test_prediction)),
        "holdout_rmse": float(mean_squared_error(test_y, test_prediction) ** 0.5),
        "holdout_mse_raw": float(
            mean_squared_error(test_y, test_prediction)
        ),
        "holdout_calibration_mae_raw": calibration_mae(raw_calibration),
        "holdout_mae_isotonic": float(
            mean_absolute_error(test_y, calibrated_prediction)
        ),
        "holdout_rmse_isotonic": float(
            mean_squared_error(test_y, calibrated_prediction) ** 0.5
        ),
        "holdout_mse_isotonic": float(
            mean_squared_error(test_y, calibrated_prediction)
        ),
        "holdout_calibration_mae_isotonic": calibration_mae(
            calibrated_calibration
        ),
        "calibration_deciles_raw": raw_calibration,
        "calibration_deciles_isotonic": calibrated_calibration,
        "calibration_choice": "Không áp dụng isotonic; giữ mô hình thô nếu không cải thiện holdout.",
        "model": model,
        "full_model_for_persona_sanity_only": full_model,
    }


def _ability_tiers(data: pd.DataFrame) -> tuple[pd.Series, tuple[float, float]]:
    first_enrolled = data[HK1_ENROLLED].to_numpy(dtype=float)
    rate = np.divide(
        data[HK1_APPROVED].to_numpy(dtype=float),
        first_enrolled,
        out=np.zeros(len(data), dtype=float),
        where=first_enrolled > 0,
    )
    cut_points = tuple(float(value) for value in np.quantile(rate, [1 / 3, 2 / 3]))
    tiers = pd.cut(
        rate,
        bins=[-np.inf, cut_points[0], cut_points[1], np.inf],
        labels=ABILITY_LABELS,
        include_lowest=True,
        right=False,
    )
    return pd.Series(tiers, index=data.index, name="ability_tier"), cut_points


def _load_band(values: pd.Series) -> pd.Series:
    return pd.cut(
        values,
        bins=[-1, 0, 5, 7, np.inf],
        labels=LOAD_BANDS,
        include_lowest=True,
        right=True,
    )


def _stratified_load_analysis(data: pd.DataFrame) -> dict[str, Any]:
    tiers, cuts = _ability_tiers(data)
    load = _load_band(data[HK2_ENROLLED])
    table_data = pd.DataFrame(
        {
            "ability_tier": tiers,
            "load_band": load,
            "enrolled_2": data[HK2_ENROLLED],
            "approved_2": data[HK2_APPROVED],
            "without_evaluations_2": data[HK2_WITHOUT_EVALUATIONS],
            "dropout": data["Target"].eq("Dropout").astype(int),
        },
        index=data.index,
    )
    rows = []
    for (ability, band), group in table_data.groupby(
        ["ability_tier", "load_band"], observed=True, sort=False
    ):
        denominator = int(group["enrolled_2"].sum())
        rows.append(
            {
                "data_label": "REAL (UCI-697)",
                "hk1_ability": str(ability),
                "hk2_enrolled_band": str(band),
                "student_count": int(len(group)),
                "students_with_hk2_enrollment": int(group["enrolled_2"].gt(0).sum()),
                "hk2_enrolled_units": denominator,
                "hk2_approved_units": int(group["approved_2"].sum()),
                "hk2_without_evaluations_units": int(group["without_evaluations_2"].sum()),
                "pass_rate_2": (
                    float(group["approved_2"].sum() / denominator)
                    if denominator > 0
                    else np.nan
                ),
                "dropout_rate": float(group["dropout"].mean()),
            }
        )
    table = pd.DataFrame(rows)
    m3_prime_rows = []
    for ability, group in table_data.groupby("ability_tier", observed=True, sort=False):
        enrolled_units = int(group["enrolled_2"].sum())
        m3_prime_rows.append(
            {
                "data_label": "REAL (UCI-697)",
                "hk1_ability": str(ability),
                "student_count_with_hk2_enrollment": int(
                    group["enrolled_2"].gt(0).sum()
                ),
                "hk2_enrolled_units": enrolled_units,
                "hk2_approved_units": int(group["approved_2"].sum()),
                "m3_prime_pass_rate": (
                    float(group["approved_2"].sum() / enrolled_units)
                    if enrolled_units > 0 else np.nan
                ),
            }
        )
    m3_prime_table = pd.DataFrame(m3_prime_rows)
    non_dropout_rows = []
    for ability, group in table_data.loc[table_data["dropout"].eq(0)].groupby(
        "ability_tier", observed=True, sort=False
    ):
        enrolled_units = int(group["enrolled_2"].sum())
        non_dropout_rows.append(
            {
                "data_label": "REAL (UCI-697), Target != Dropout",
                "hk1_ability": str(ability),
                "student_count_with_hk2_enrollment": int(
                    group["enrolled_2"].gt(0).sum()
                ),
                "hk2_enrolled_units": enrolled_units,
                "hk2_approved_units": int(group["approved_2"].sum()),
                "pass_rate_2": (
                    float(group["approved_2"].sum() / enrolled_units)
                    if enrolled_units > 0
                    else np.nan
                ),
            }
        )
    non_dropout_m3_prime_table = pd.DataFrame(non_dropout_rows)
    # Adjusted association only: standardized T1-known controls, raw unit change in
    # HK2 enrollment. This is descriptive regression, not a causal estimate.
    control_columns = [
        HK1_APPROVED,
        HK1_ENROLLED,
        HK1_GRADE,
        "Age at enrollment",
    ]
    x = pd.DataFrame(
        {
            HK2_ENROLLED: data[HK2_ENROLLED],
            "hk1_approval_rate": np.divide(
                data[HK1_APPROVED],
                data[HK1_ENROLLED],
                out=np.zeros(len(data), dtype=float),
                where=data[HK1_ENROLLED].to_numpy() > 0,
            ),
            **{column: data[column] for column in control_columns},
        },
        index=data.index,
    )
    preprocessor = ColumnTransformer(
        [
            ("load", "passthrough", [HK2_ENROLLED]),
            (
                "baseline_controls",
                StandardScaler(),
                ["hk1_approval_rate", *control_columns],
            ),
        ]
    )
    adjusted_model = make_pipeline(
        preprocessor,
        LogisticRegression(C=1e6, max_iter=2000, random_state=SEED),
    ).fit(x, data["Target"].eq("Dropout").astype(int))
    load_coefficient = float(adjusted_model[-1].coef_[0][0])
    adjusted_or = float(np.exp(load_coefficient))
    overall = pd.DataFrame(
        [
            {
                "data_label": "REAL (UCI-697)",
                "students": len(data),
                "students_with_hk2_enrollment": int(data[HK2_ENROLLED].gt(0).sum()),
                "students_zero_hk2_enrollment": int(data[HK2_ENROLLED].eq(0).sum()),
                "hk2_pass_rate_pooled": float(
                    data.loc[data[HK2_ENROLLED].gt(0), HK2_APPROVED].sum()
                    / data.loc[data[HK2_ENROLLED].gt(0), HK2_ENROLLED].sum()
                ),
                "dropout_rate": float(data["Target"].eq("Dropout").mean()),
                "adjusted_dropout_odds_ratio_per_extra_hk2_unit": adjusted_or,
            }
        ]
    )
    return {
        "table": table,
        "m3_prime_table": m3_prime_table,
        "non_dropout_m3_prime_table": non_dropout_m3_prime_table,
        "overall": overall,
        "ability_cut_points": cuts,
        "ability_tiers": tiers,
        "adjusted_model": adjusted_model,
        "adjusted_or_per_hk2_unit": adjusted_or,
        "adjusted_log_odds_coefficient": load_coefficient,
    }


def _m1_counterfactual(
    data: pd.DataFrame,
    features: list[str],
    categories: list[str],
    numeric: list[str],
    dropout: dict[str, Any],
) -> dict[str, Any]:
    """Deliberately diagnostic model with T1_decision enrollment added."""
    m1_features = [*features, HK2_ENROLLED]
    m1_numeric = [*numeric, HK2_ENROLLED]
    train_indices = dropout["train_indices"]
    test_indices = dropout["test_indices"]
    x, y = data[m1_features], data["Target"]
    model = make_pipeline(
        _preprocessor(categories, m1_numeric),
        LogisticRegression(max_iter=2000, random_state=SEED),
    ).fit(x.iloc[train_indices], y.iloc[train_indices])
    classes = list(model[-1].classes_)
    dropout_index = classes.index("Dropout")
    holdout_p = model.predict_proba(x.iloc[test_indices])[:, dropout_index]
    holdout_y = y.iloc[test_indices].eq("Dropout")

    sample = x.iloc[test_indices].copy()
    numeric_median = sample[m1_numeric].median()
    categorical_modes = sample[categories].mode(dropna=True).iloc[0]
    row: dict[str, Any] = {
        column: (
            numeric_median[column] if column in m1_numeric else categorical_modes[column]
        )
        for column in m1_features
    }
    row[HK2_ENROLLED] = float(data.iloc[test_indices][HK2_ENROLLED].median())
    counterfactual_rows = []
    for load in [1, 3, 5, 6, 8, 10, 12]:
        row[HK2_ENROLLED] = load
        p_dropout = float(
            model.predict_proba(pd.DataFrame([row], columns=m1_features))[0][dropout_index]
        )
        counterfactual_rows.append(
            {
                "data_label": "REAL (UCI-697), diagnostic M1",
                "counterfactual_hk2_enrolled": load,
                "predicted_p_dropout": p_dropout,
            }
        )
    representative_probabilities = [
        row["predicted_p_dropout"] for row in counterfactual_rows
    ]
    logit_effective_or = float(
        np.exp(
            (
                np.log(representative_probabilities[-1] / (1 - representative_probabilities[-1]))
                - np.log(representative_probabilities[0] / (1 - representative_probabilities[0]))
            )
            / (12 - 1)
        )
    )

    binary_model = make_pipeline(
        _preprocessor(categories, m1_numeric),
        LogisticRegression(max_iter=2000, random_state=SEED),
    ).fit(
        x.iloc[train_indices],
        y.iloc[train_indices].eq("Dropout").astype(int),
    )
    binary_feature_names = binary_model[0].get_feature_names_out()
    enrolled_feature_index = next(
        index
        for index, name in enumerate(binary_feature_names)
        if name.endswith(HK2_ENROLLED)
    )
    binary_enrolled_or = float(
        np.exp(binary_model[-1].coef_[0][enrolled_feature_index])
    )
    baseline = dropout["model"]
    base_index = list(baseline[-1].classes_).index("Dropout")
    base_p = baseline.predict_proba(data.iloc[test_indices][features])[:, base_index]
    return {
        "counterfactual_table": pd.DataFrame(counterfactual_rows),
        "holdout_brier_with_t1_decision": float(brier_score_loss(holdout_y, holdout_p)),
        "holdout_brier_without_t1_decision": float(brier_score_loss(holdout_y, base_p)),
        "binary_same_controls_or_per_enrolled_unit": binary_enrolled_or,
        "multiclass_effective_counterfactual_or_per_enrolled_unit": logit_effective_or,
        "binary_same_controls_model": binary_model,
        "model_with_t1_decision": model,
    }


def _difficulty_factors() -> tuple[dict[str, float], pd.DataFrame]:
    courses = _read_csv(COURSES_PATH)
    progress = _read_csv(PROGRESS_PATH)
    graded = progress.loc[progress["grade_10"].notna()].merge(
        courses[["course_id", "group"]],
        on="course_id",
        how="left",
        validate="many_to_one",
    )
    if graded.empty:
        raise ValueError("Không có điểm SIMULATED để suy ra difficulty factors")
    graded["grade_10"] = pd.to_numeric(graded["grade_10"])
    overall_median = float(graded["grade_10"].median())
    group_medians = graded.groupby("group", observed=True)["grade_10"].median()
    raw_factors = group_medians / overall_median
    lower, upper = raw_factors.quantile([0.1, 0.9])
    clipped = raw_factors.clip(float(lower), float(upper))
    factors = clipped.to_dict()
    table = pd.DataFrame(
        {
            "data_label": "SIMULATED",
            "group": group_medians.index,
            "median_grade_10": group_medians.values,
            "raw_relative_factor": raw_factors.values,
            "difficulty_factor_clipped_q10_q90": clipped.values,
        }
    )
    return factors, table


def _next_semester_courses(
    student_id: str,
    profile: pd.Series,
    courses: pd.DataFrame,
    progress: pd.DataFrame,
    prerequisites: pd.DataFrame,
) -> list[dict[str, Any]]:
    student_progress = progress[progress["student_id"] == student_id].set_index("course_id")
    status_by_course = student_progress["status"].to_dict()
    current_semester = int(profile["current_semester"])
    next_semester = current_semester + 1
    offered = "odd" if next_semester % 2 else "even"
    prerequisite_map: dict[str, list[dict[str, str]]] = {}
    for row in prerequisites.to_dict("records"):
        prerequisite_map.setdefault(row["course_id"], []).append(row)

    eligible = []
    for course in courses.to_dict("records"):
        course_id = course["course_id"]
        status = status_by_course.get(course_id, "not_taken")
        if status not in {"failed", "not_taken"}:
            continue
        offerings = set(course["offered_semesters"].split(","))
        if "both" not in offerings and offered not in offerings:
            continue
        prerequisites_met = True
        for requirement in prerequisite_map.get(course_id, []):
            prerequisite_status = status_by_course.get(
                requirement["prerequisite_id"], "not_taken"
            )
            if requirement["type"] == "tiên quyết" and prerequisite_status != "completed":
                prerequisites_met = False
            elif requirement["type"] == "học trước" and prerequisite_status not in {
                "completed",
                "failed",
            }:
                prerequisites_met = False
        if not prerequisites_met:
            continue
        eligible.append(
            {
                **course,
                "credits": int(course["credits"]),
                "status": status,
                "attempt_count": int(
                    student_progress.loc[course_id, "attempt_count"]
                    if course_id in student_progress.index
                    else 0
                ),
            }
        )
    eligible.sort(
        key=lambda item: (
            0 if item["status"] == "failed" else 1,
            int(item["planned_semester"]),
            item["course_id"],
        )
    )
    return eligible


def _choose_plan(candidates: list[dict[str, Any]], credit_budget: int) -> list[dict[str, Any]]:
    states: dict[int, tuple[int, ...]] = {0: ()}
    for index, course in enumerate(candidates):
        credits = int(course["credits"])
        for current_credits, selected_indices in list(states.items()):
            new_credits = current_credits + credits
            if new_credits <= credit_budget and new_credits not in states:
                states[new_credits] = (*selected_indices, index)
    best_credit = max(states)
    return [candidates[index] for index in states[best_credit]]


def _choose_nested_plans(
    candidates: list[dict[str, Any]],
    credit_budgets: list[int],
) -> dict[int, list[dict[str, Any]]]:
    """Build progressively larger fixture plans without dropping prior courses."""
    selected: list[dict[str, Any]] = []
    plans: dict[int, list[dict[str, Any]]] = {}
    selected_ids: set[str] = set()
    for budget in sorted(credit_budgets):
        remaining_budget = budget - sum(int(course["credits"]) for course in selected)
        remaining_courses = [
            course
            for course in candidates
            if course["course_id"] not in selected_ids
        ]
        if remaining_budget > 0:
            added = _choose_plan(remaining_courses, remaining_budget)
            selected.extend(added)
            selected_ids.update(course["course_id"] for course in added)
        plans[budget] = list(selected)
    return plans


def _scenario_load_band(equivalent_units: float) -> str:
    rounded_units = max(1, int(np.floor(equivalent_units + 0.5)))
    if rounded_units <= 5:
        return "1-5"
    if rounded_units <= 7:
        return "6-7"
    return "8+"


def _ability_for_profile(rate: float, cut_points: tuple[float, float]) -> str:
    if rate < cut_points[0]:
        return "Thấp"
    if rate < cut_points[1]:
        return "Trung bình"
    return "Cao"


def _persona_sanity(
    data: pd.DataFrame,
    features: list[str],
    dropout: dict[str, Any],
    pass_rate: dict[str, Any],
    stratified: dict[str, Any],
    difficulty_factors: dict[str, float],
    exploration_config: dict[str, Any],
) -> dict[str, Any]:
    courses = _read_csv(COURSES_PATH)
    progress = _read_csv(PROGRESS_PATH)
    profiles = _read_csv(PROFILE_PATH)
    prerequisites = _read_csv(PREREQUISITES_PATH)
    average_credits = float(pd.to_numeric(courses["credits"]).mean())
    real_load_median = float(
        data.loc[data[HK2_ENROLLED] > 0, HK2_ENROLLED].median()
    )

    band_rate_lookup = stratified["table"].set_index(
        ["hk1_ability", "hk2_enrolled_band"]
    )["pass_rate_2"]
    pooled_strata = {
        row["hk1_ability"]: {
            "students": int(row["student_count_with_hk2_enrollment"]),
            "approved_units": int(row["hk2_approved_units"]),
            "enrolled_units": int(row["hk2_enrolled_units"]),
        }
        for row in stratified["m3_prime_table"].to_dict("records")
    }
    outputs = []
    sensitivity = []
    for _, profile in profiles.iterrows():
        student_id = str(profile["student_id"])
        row = profile[features].to_frame().T
        p_student_pass = float(
            np.clip(
                pass_rate["full_model_for_persona_sanity_only"].predict(row)[0],
                0,
                1,
            )
        )
        p_dropout = float(
            dropout["full_model_for_persona_sanity_only"]
            .predict_proba(row)[0][
                list(dropout["full_model_for_persona_sanity_only"][-1].classes_).index(
                    "Dropout"
                )
            ]
        )
        hk1_enrolled = int(profile[HK1_ENROLLED])
        hk1_approved = int(profile[HK1_APPROVED])
        ability_rate = hk1_approved / hk1_enrolled if hk1_enrolled > 0 else 0.0
        ability = _ability_for_profile(ability_rate, stratified["ability_cut_points"])
        candidates = _next_semester_courses(
            student_id,
            profile,
            courses,
            progress,
            prerequisites,
        )
        nested_plans = _choose_nested_plans(
            candidates,
            exploration_config["scenario_credits"],
        )
        for target in exploration_config["scenario_credits"]:
            selected = nested_plans[target]
            actual_credits = sum(course["credits"] for course in selected)
            equivalent_units = actual_credits / average_credits
            load_multiplier = float(
                np.exp(
                    -exploration_config["base_load_lambda"]
                    * max(0.0, equivalent_units - real_load_median)
                )
            )
            m2 = plan_risk(
                student_id,
                selected,
                p_student_pass=p_student_pass,
                difficulty_factors=difficulty_factors,
                load_multiplier=load_multiplier,
                retake_multiplier=1.0,
                average_credits_per_unit=average_credits,
            )
            rounded_units = credits_to_curricular_units(
                actual_credits,
                average_credits,
            )
            band = _scenario_load_band(rounded_units) if actual_credits else "0"
            p_m3_prime = m3_prime_probability(
                ability,
                pooled_strata,
                minimum_students=exploration_config["m3_minimum_students"],
            )
            rate_value = (
                band_rate_lookup.loc[(ability, band)] if actual_credits else np.nan
            )
            p_m3_band = float(rate_value) if not pd.isna(rate_value) else None
            m3 = (
                plan_risk(
                    student_id,
                    selected,
                    p_student_pass=p_m3_prime,
                    difficulty_factors={},
                    load_multiplier=1.0,
                    retake_multiplier=1.0,
                    average_credits_per_unit=average_credits,
                )
                if selected and p_m3_prime is not None
                else None
            )
            outputs.append(
                {
                    "data_label": "SIMULATED",
                    "student_id": student_id,
                    "persona": profile["persona"],
                    "ability_tier_from_real_hk1": ability,
                    "scenario_credit_budget": target,
                    "planned_credits_actual": actual_credits,
                    "eligible_course_count": len(candidates),
                    "selected_course_ids": ", ".join(
                        course["course_id"] for course in selected
                    ),
                    "p_dropout_student_level": p_dropout,
                    "p_student_pass_rate_model": p_student_pass,
                    "m2_expected_credits_passed": m2["expected_credits_passed"],
                    "m2_expected_failed_courses": m2["expected_failed_courses"],
                    "m2_plan_risk_index": m2["plan_risk_index"],
                    "m3_prime_p_pass_by_ability": p_m3_prime,
                    "m3_non_dropout_p_pass_by_ability": float(
                        stratified["non_dropout_m3_prime_table"]
                        .set_index("hk1_ability")
                        .loc[ability, "pass_rate_2"]
                    ),
                    "m3_band_p_pass_selection_bias_reference": p_m3_band,
                    "m3_expected_failed_courses": (
                        m3["expected_failed_courses"] if m3 else None
                    ),
                    "m3_plan_risk_index": m3["plan_risk_index"] if m3 else None,
                    "status": (
                        "Không đủ học phần đủ điều kiện để đạt ngân sách"
                        if actual_credits < target
                        else "Đạt ngân sách mô phỏng"
                    ),
                }
            )
            for load_lambda in exploration_config["load_lambdas"]:
                for difficulty_multiplier in exploration_config[
                    "difficulty_multipliers"
                ]:
                    adjusted_difficulty_factors = {
                        group: factor * difficulty_multiplier
                        for group, factor in difficulty_factors.items()
                    }
                    for retake_factor in exploration_config["retake_multipliers"]:
                        g_load = float(
                            np.exp(
                                -load_lambda
                                * max(0.0, equivalent_units - real_load_median)
                            )
                        )
                        result = plan_risk(
                            student_id,
                            selected,
                            p_student_pass=p_student_pass,
                            difficulty_factors=adjusted_difficulty_factors,
                            load_multiplier=g_load,
                            retake_multiplier=retake_factor,
                            average_credits_per_unit=average_credits,
                        )
                        sensitivity.append(
                            {
                                "data_label": "SIMULATED + GIẢ ĐỊNH kịch bản",
                                "student_id": student_id,
                                "scenario_credit_budget": target,
                                "planned_credits_actual": actual_credits,
                                "lambda_load_assumption": load_lambda,
                                "difficulty_multiplier_assumption": difficulty_multiplier,
                                "retake_multiplier_assumption": retake_factor,
                                "expected_failed_courses": result["expected_failed_courses"],
                                "expected_credits_passed": result["expected_credits_passed"],
                                "plan_risk_index": result["plan_risk_index"],
                            }
                        )
    result_table = pd.DataFrame(outputs)
    sensitivity_raw = pd.DataFrame(sensitivity)
    sensitivity_summary = (
        sensitivity_raw.groupby(
            ["student_id", "scenario_credit_budget"], as_index=False, observed=True
        )
        .agg(
            planned_credits_actual=("planned_credits_actual", "first"),
            expected_failed_min=("expected_failed_courses", "min"),
            expected_failed_max=("expected_failed_courses", "max"),
            expected_credits_min=("expected_credits_passed", "min"),
            expected_credits_max=("expected_credits_passed", "max"),
            risk_index_min=("plan_risk_index", "min"),
            risk_index_max=("plan_risk_index", "max"),
        )
    )
    real_pooled_pass_rate = float(
        data.loc[data[HK2_ENROLLED] > 0, HK2_APPROVED].sum()
        / data.loc[data[HK2_ENROLLED] > 0, HK2_ENROLLED].sum()
    )
    load_sensitivity_rows = []
    for credit_budget in exploration_config["scenario_credits"]:
        equivalent_units = credit_budget / average_credits
        rounded_units = credits_to_curricular_units(credit_budget, average_credits)
        for load_lambda in exploration_config["load_lambdas"]:
            multiplier = float(
                np.exp(-load_lambda * max(0.0, equivalent_units - real_load_median))
            )
            load_sensitivity_rows.append(
                {
                    "data_label": "REAL baseline + GIẢ ĐỊNH kịch bản",
                    "credit_budget": credit_budget,
                    "simulated_average_credits_per_unit": average_credits,
                    "equivalent_curricular_units": equivalent_units,
                    "nearest_integer_units_for_band": rounded_units,
                    "real_median_hk2_units": real_load_median,
                    "lambda_assumption": load_lambda,
                    "g_load": multiplier,
                    "reference_p_pass_real_pooled": real_pooled_pass_rate,
                    "scenario_p_pass_one_course": real_pooled_pass_rate * multiplier,
                }
            )
    return {
        "table": result_table,
        "sensitivity_raw": sensitivity_raw,
        "sensitivity_summary": sensitivity_summary,
        "load_sensitivity": pd.DataFrame(load_sensitivity_rows),
        "difficulty_factors_table": None,
        "average_credits_per_unit": average_credits,
        "real_median_hk2_enrolled": real_load_median,
        "real_pooled_pass_rate": real_pooled_pass_rate,
    }


def run_exploration() -> dict[str, Any]:
    """Run all exploratory analysis; no final model or optimizer is produced."""
    data, features, categories, numeric = _load_real_data()
    exploration_config = _load_exploration_config()
    dropout = _fit_dropout_model(
        data,
        features,
        categories,
        numeric,
        exploration_config,
    )
    pass_rate = _fit_pass_rate_model(data, features, categories, numeric)
    stratified = _stratified_load_analysis(data)
    m1 = _m1_counterfactual(data, features, categories, numeric, dropout)
    difficulty_factors, difficulty_table = _difficulty_factors()
    persona = _persona_sanity(
        data,
        features,
        dropout,
        pass_rate,
        stratified,
        difficulty_factors,
        exploration_config,
    )
    persona["difficulty_factors_table"] = difficulty_table
    persona["difficulty_factors"] = difficulty_factors

    without_evaluations = int(data[HK2_WITHOUT_EVALUATIONS].sum())
    enrolled_units = int(data.loc[data[HK2_ENROLLED] > 0, HK2_ENROLLED].sum())
    dropout_within_load = (
        stratified["table"]
        .pivot(index="hk1_ability", columns="hk2_enrolled_band", values="dropout_rate")
        .reindex(index=ABILITY_LABELS, columns=LOAD_BANDS)
    )
    return {
        "data_label": "REAL (UCI-697)",
        "seed": SEED,
        "exploration_config": exploration_config,
        "feature_count": len(features),
        "features": features,
        "dropout_model": dropout,
        "pass_rate_model": pass_rate,
        "stratified_load": stratified,
        "m1": m1,
        "persona": persona,
        "without_evaluation_units_hk2": without_evaluations,
        "enrolled_units_hk2_when_n_gt_0": enrolled_units,
        "dropout_rate_by_tier_load": dropout_within_load,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run_exploration()
    dropout = result["dropout_model"]
    pass_rate = result["pass_rate_model"]
    stratified = result["stratified_load"]
    m1 = result["m1"]
    persona = result["persona"]
    output_dir = ROOT / "reports" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    dropout["risk_tier_validation_thresholds"][
        "oof_warning_distribution"
    ].to_csv(
        output_dir / "risk_warning_tier_oof.csv",
        index=False,
        encoding="utf-8-sig",
    )
    dropout["risk_tier_validation_thresholds"][
        "restriction_threshold_sensitivity"
    ].to_csv(
        output_dir / "risk_restriction_threshold_oof.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pass_rate["calibration_deciles_raw"].to_csv(
        output_dir / "pass_rate_calibration_deciles.csv",
        index=False,
        encoding="utf-8-sig",
    )
    stratified["m3_prime_table"].to_csv(
        output_dir / "m3_prime_by_hk1_tier.csv",
        index=False,
        encoding="utf-8-sig",
    )
    stratified["non_dropout_m3_prime_table"].to_csv(
        output_dir / "m3_prime_non_dropout_by_hk1_tier.csv",
        index=False,
        encoding="utf-8-sig",
    )
    persona["table"].to_csv(
        output_dir / "risk_to_plan_persona_scenarios.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print("EXPLORATORY — chưa phải mô hình cuối")
    print(f"Seed={SEED}; T1 feature count={result['feature_count']}")
    print("C1 dropout model:")
    for key in [
        "cv_accuracy_mean",
        "cv_f1_macro_mean",
        "cv_f1_dropout_mean",
        "holdout_precision_dropout",
        "holdout_recall_dropout",
        "holdout_f1_dropout",
        "brier_dropout",
    ]:
        print(f"  {key}={dropout[key]:.6f}")
    print("C1 confusion matrix labels=Dropout,Enrolled,Graduate:")
    print(dropout["confusion_matrix"])
    print("C1 risk-tier thresholds selected from stratified OOF validation:")
    thresholds = dropout["risk_tier_validation_thresholds"]
    print(
        {
            key: value
            for key, value in thresholds.items()
            if key
            in {
                "low_max_p_dropout",
                "medium_max_p_dropout",
                "validation_recall_medium",
                "validation_recall_high",
                "calibrated_restriction_threshold",
                "restriction_minimum_ppv",
            }
        }
    )
    print("C1 warning tier distribution and PPV (REAL train OOF):")
    print(
        dropout["risk_tier_validation_thresholds"][
            "oof_warning_distribution"
        ].to_string(index=False)
    )
    print("C1 calibrated soft-restriction threshold (REAL train OOF):")
    print(
        "  threshold="
        f"{dropout['risk_tier_validation_thresholds']['calibrated_restriction_threshold']}; "
        f"near-base check={dropout['risk_tier_validation_thresholds']['restriction_near_base_check']}"
    )
    print("C1 restriction threshold sensitivity:")
    print(
        dropout["risk_tier_validation_thresholds"][
            "restriction_threshold_sensitivity"
        ].to_string(index=False)
    )
    print("C2 pass-rate model:")
    for key in [
        "eligible_students",
        "excluded_zero_enrollment",
        "cv_mae_mean",
        "cv_rmse_mean",
        "holdout_mae",
        "holdout_rmse",
        "holdout_mae_isotonic",
        "holdout_rmse_isotonic",
        "holdout_calibration_mae_raw",
        "holdout_calibration_mae_isotonic",
    ]:
        value = pass_rate[key]
        print(f"  {key}={value:.6f}" if isinstance(value, float) else f"  {key}={value}")
    print("C2 holdout calibration deciles (raw RF):")
    print(pass_rate["calibration_deciles_raw"].to_string(index=False))
    print(f"C2 calibration decision: {pass_rate['calibration_choice']}")
    print("C3 REAL stratified table:")
    print(stratified["table"].to_string(index=False))
    print("C3 M3-prime REAL pooled table by HK1 ability:")
    print(stratified["m3_prime_table"].to_string(index=False))
    print("C3 REAL pooled table among non-Dropout students:")
    print(stratified["non_dropout_m3_prime_table"].to_string(index=False))
    print(
        "C3 adjusted observational OR per extra HK2 unit="
        f"{stratified['adjusted_or_per_hk2_unit']:.6f}"
    )
    print("M1 diagnostic:")
    print(m1["counterfactual_table"].to_string(index=False))
    print(
        "M1 heldout Brier with T1_decision="
        f"{m1['holdout_brier_with_t1_decision']:.6f}; without="
        f"{m1['holdout_brier_without_t1_decision']:.6f}"
    )
    print(
        "M1 same-controls binary OR per unit="
        f"{m1['binary_same_controls_or_per_enrolled_unit']:.6f}; "
        "M1 3-class effective counterfactual OR="
        f"{m1['multiclass_effective_counterfactual_or_per_enrolled_unit']:.6f}"
    )
    print("C6 SIMULATED persona scenarios:")
    print(persona["table"].to_string(index=False))
    print("C7 SIMULATED sensitivity summary:")
    print(persona["sensitivity_summary"].to_string(index=False))
    print("C7 load-factor sensitivity at requested scenario loads:")
    print(persona["load_sensitivity"].to_string(index=False))


if __name__ == "__main__":
    main()
