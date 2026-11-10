"""Train, validate, explain, and optionally evaluate the protected UCI-697 holdout."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier

from core.ml_data import (
    ROOT,
    SEED,
    TARGET,
    create_split_manifest,
    load_manifest,
    load_split,
    read_source,
    source_feature_columns,
)
from core.metrics import update_metrics
from core.pass_prob import (
    fit_pass_probability,
    pass_probability_table,
)
from core.models import apply_calibration


CLASS_NAMES = ["Dropout", "Enrolled", "Graduate"]
CLASS_TO_NUMBER = {name: index for index, name in enumerate(CLASS_NAMES)}
NUMBER_TO_CLASS = {index: name for name, index in CLASS_TO_NUMBER.items()}
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "early_warning.joblib"
METRICS_PATH = ROOT / "reports" / "generated" / "metrics.json"
COMPARISON_PATH = ROOT / "reports" / "generated" / "model_comparison.csv"
FIGURES_DIR = ROOT / "reports" / "figures"
TEST_METRICS_PATH = ROOT / "reports" / "generated" / "test_evaluation.json"
PROTOCOL_PATH = ROOT / "reports" / "ml_protocol.md"
OOF_SPLITS = 5


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def _label_numbers(labels: pd.Series, *, binary: bool = False) -> np.ndarray:
    if binary:
        return (labels.astype(str).to_numpy() == "Dropout").astype(int)
    unknown = set(labels.astype(str)) - set(CLASS_TO_NUMBER)
    if unknown:
        raise ValueError(f"Unknown target labels: {sorted(unknown)}")
    return labels.astype(str).map(CLASS_TO_NUMBER).to_numpy(dtype=int)


def _feature_schema(columns: list[str]) -> tuple[list[str], list[str]]:
    dictionary = pd.read_csv(ROOT / "reports" / "data_dictionary.csv", encoding="utf-8-sig")
    dictionary["attribute_name"] = dictionary["attribute_name"].astype(str).str.strip()
    types = dict(zip(dictionary["attribute_name"], dictionary["data_type"]))
    categorical = [
        column
        for column in columns
        if str(types.get(column, "")).startswith("Danh mục")
    ]
    numeric = [column for column in columns if column not in categorical]
    return categorical, numeric


def _preprocessor(columns: list[str]) -> ColumnTransformer:
    categorical, numeric = _feature_schema(columns)
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            )
        )
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    return ColumnTransformer(transformers, remainder="drop")


def _make_model(name: str, class_count: int, parameters: dict[str, Any] | None = None) -> Any:
    params = dict(parameters or {})
    if name == "LogisticRegression":
        return LogisticRegression(
            max_iter=2500,
            solver="lbfgs",
            random_state=SEED,
            **params,
        )
    if name == "RandomForest":
        defaults = {
            "n_estimators": 250,
            "min_samples_leaf": 2,
            "class_weight": None,
            "random_state": SEED,
            "n_jobs": 4,
        }
        defaults.update(params)
        return RandomForestClassifier(**defaults)
    if name == "XGBoost":
        defaults = {
            "objective": "multi:softprob" if class_count == 3 else "binary:logistic",
            "num_class": class_count if class_count == 3 else None,
            "eval_metric": "mlogloss" if class_count == 3 else "logloss",
            "tree_method": "hist",
            "n_estimators": 180,
            "learning_rate": 0.05,
            "max_depth": 3,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_lambda": 1.0,
            "n_jobs": 4,
            "random_state": SEED,
            "verbosity": 0,
        }
        defaults.update(params)
        return XGBClassifier(**defaults)
    raise ValueError(f"Unsupported model: {name}")


def _pipeline(columns: list[str], model: Any) -> Pipeline:
    return Pipeline([("preprocess", _preprocessor(columns)), ("model", model)])


def _grid(name: str, binary: bool) -> dict[str, list[Any]]:
    if name == "LogisticRegression":
        return {"model__C": [0.1, 1.0]}
    if name == "RandomForest":
        return {"model__max_depth": [None, 12]}
    if name == "XGBoost":
        return {"model__max_depth": [3, 5]}
    raise ValueError(f"Unsupported model: {name}")


def _metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    class_count: int,
    *,
    threshold: float | None = None,
) -> dict[str, Any]:
    if class_count == 3:
        labels = list(range(3))
        predicted = probabilities.argmax(axis=1)
        report = classification_report(
            y_true,
            predicted,
            labels=labels,
            target_names=CLASS_NAMES,
            output_dict=True,
            zero_division=0,
        )
        one_hot = np.eye(3)[y_true]
        per_class_ap = {
            CLASS_NAMES[index]: float(average_precision_score(one_hot[:, index], probabilities[:, index]))
            for index in labels
        }
        per_class_roc = {
            CLASS_NAMES[index]: float(roc_auc_score(one_hot[:, index], probabilities[:, index]))
            for index in labels
        }
        dropout_probability = probabilities[:, CLASS_TO_NUMBER["Dropout"]]
        dropout_brier = float(brier_score_loss((y_true == 0).astype(int), dropout_probability))
        class_labels = CLASS_NAMES
        pr_auc_macro = float(np.mean(list(per_class_ap.values())))
        try:
            roc_auc = float(roc_auc_score(y_true, probabilities, multi_class="ovr", average="macro"))
        except ValueError:
            roc_auc = None
    else:
        labels = [0, 1]
        dropout_probability = probabilities[:, 1]
        threshold = 0.5 if threshold is None else threshold
        predicted = (dropout_probability >= threshold).astype(int)
        report = classification_report(
            y_true,
            predicted,
            labels=labels,
            target_names=["Non-Dropout", "Dropout"],
            output_dict=True,
            zero_division=0,
        )
        ap = float(average_precision_score(y_true, dropout_probability))
        per_class_ap = {"Dropout": ap}
        per_class_roc = {"Dropout": float(roc_auc_score(y_true, dropout_probability))}
        dropout_brier = float(brier_score_loss(y_true, dropout_probability))
        class_labels = ["Non-Dropout", "Dropout"]
        pr_auc_macro = ap
        roc_auc = float(roc_auc_score(y_true, dropout_probability))
    return {
        "accuracy": float(accuracy_score(y_true, predicted)),
        "macro_f1": float(f1_score(y_true, predicted, average="macro", zero_division=0)),
        "per_class": {
            name: {
                "precision": float(report[name]["precision"]),
                "recall": float(report[name]["recall"]),
                "f1": float(report[name]["f1-score"]),
                "support": int(report[name]["support"]),
            }
            for name in class_labels
        },
        "pr_auc_one_vs_rest": per_class_ap,
        "roc_auc_one_vs_rest": per_class_roc,
        "pr_auc_macro": pr_auc_macro,
        "roc_auc_ovr_macro": roc_auc,
        "brier_dropout": dropout_brier,
        "confusion_matrix": confusion_matrix(y_true, predicted, labels=labels).tolist(),
        "threshold": threshold,
    }


def _dropout_probability(probabilities: np.ndarray, class_count: int) -> np.ndarray:
    return probabilities[:, 1] if class_count == 2 else probabilities[:, 0]


def _recall_at_precision(
    y_true: np.ndarray,
    probability: np.ndarray,
    minimum_precision: float = 0.5,
) -> dict[str, float | None]:
    precision, recall, thresholds = precision_recall_curve(y_true, probability)
    candidates = [
        index
        for index, threshold in enumerate(thresholds)
        if precision[index] >= minimum_precision
    ]
    if not candidates:
        return {"precision_floor": minimum_precision, "recall": 0.0, "threshold": 1.0, "precision": 0.0}
    chosen = max(candidates, key=lambda index: (recall[index], thresholds[index]))
    return {
        "precision_floor": minimum_precision,
        "recall": float(recall[chosen]),
        "threshold": float(thresholds[chosen]),
        "precision": float(precision[chosen]),
    }


def _calibration_threshold(probability: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
    constraints = [0.5, 0.7]
    result: dict[str, Any] = {}
    for floor in constraints:
        result[str(floor)] = _recall_at_precision(y_true, probability, floor)
    for target_recall in (0.98, 0.90, 0.70):
        precision, recall, thresholds = precision_recall_curve(y_true, probability)
        possible = [
            index
            for index, threshold in enumerate(thresholds)
            if recall[index] >= target_recall
        ]
        threshold = (
            float(max(thresholds[possible]))
            if possible
            else 0.0
        )
        pred = probability >= threshold
        result[f"recall_{target_recall:.2f}"] = {
            "threshold": threshold,
            "recall": float(recall_score(y_true, pred, zero_division=0)),
            "precision": float(precision_score(y_true, pred, zero_division=0)),
            "n_alerted": int(pred.sum()),
            "n_total": int(len(y_true)),
        }
    return result


def _warning_tier_metrics(
    probability: np.ndarray,
    y_true: np.ndarray,
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    medium = float(thresholds["recall_0.90"]["threshold"])
    high = float(thresholds["recall_0.70"]["threshold"])
    buckets = (
        ("low", probability < medium, None, medium),
        ("medium", (probability >= medium) & (probability < high), medium, high),
        ("high", probability >= high, high, None),
    )
    results = []
    for name, mask, lower, upper in buckets:
        count = int(mask.sum())
        dropout_count = int(y_true[mask].sum())
        results.append(
            {
                "tier": name,
                "lower_threshold_inclusive": lower,
                "upper_threshold_exclusive": upper,
                "n_students": count,
                "dropout_count": dropout_count,
                "dropout_share_in_tier": dropout_count / count if count else None,
                "interpretation": (
                    "Group dropout rate; low tier is not a positive alert."
                    if name == "low"
                    else "Validation positive predictive value for this alert tier."
                ),
            }
        )
    return results


def _alert_metrics(
    y_true: np.ndarray,
    dropout_probability: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    predicted = dropout_probability >= threshold
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "n_alerted": int(predicted.sum()),
        "confusion_matrix": confusion_matrix(y_true, predicted, labels=[False, True]).tolist(),
    }


def _fit_calibrators(
    oof_probability: np.ndarray,
    y_train: np.ndarray,
    validation_probability: np.ndarray,
    y_validation: np.ndarray,
    class_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    class_targets = (
        [(y_train == 1).astype(int)]
        if class_count == 2
        else [(y_train == index).astype(int) for index in range(class_count)]
    )
    calibrators: dict[str, dict[str, Any]] = {"platt": {}, "isotonic": {}}
    validation_scores: dict[str, Any] = {
        "uncalibrated_brier": float(
            brier_score_loss(
                (y_validation == 1).astype(int) if class_count == 2 else (y_validation == 0).astype(int),
                _dropout_probability(validation_probability, class_count),
            )
        )
    }
    for method in ("platt", "isotonic"):
        columns = [1] if class_count == 2 else list(range(class_count))
        for column, target in zip(columns, class_targets):
            scores = oof_probability[:, column]
            if method == "platt":
                calibrator = LogisticRegression(solver="lbfgs", random_state=SEED)
                calibrator.fit(scores.reshape(-1, 1), target)
            else:
                calibrator = IsotonicRegression(out_of_bounds="clip")
                calibrator.fit(scores, target)
            calibrators[method][str(column)] = calibrator
        calibrated = apply_calibration(validation_probability, calibrators[method], method, class_count)
        binary_target = (y_validation == 1).astype(int) if class_count == 2 else (y_validation == 0).astype(int)
        validation_scores[f"{method}_brier"] = float(
            brier_score_loss(binary_target, _dropout_probability(calibrated, class_count))
        )
        validation_scores[f"{method}_multiclass_brier"] = float(
            np.mean(np.sum((calibrated - np.eye(class_count)[y_validation]) ** 2, axis=1))
        )
    best_method = min(
        ("uncalibrated", "platt", "isotonic"),
        key=lambda method: (
            validation_scores["uncalibrated_brier"]
            if method == "uncalibrated"
            else validation_scores[f"{method}_brier"],
            (
                float(
                    np.mean(
                        np.sum(
                            (
                                validation_probability
                                - np.eye(class_count)[y_validation]
                            )
                            ** 2,
                            axis=1,
                        )
                    )
                )
                if method == "uncalibrated" and class_count > 2
                else validation_scores.get(
                    f"{method}_multiclass_brier",
                    validation_scores["uncalibrated_brier"],
                )
            ),
        ),
    )
    validation_scores["selected_method"] = best_method
    if best_method == "uncalibrated":
        return {}, validation_scores
    return calibrators[best_method], validation_scores


def _train_search(
    name: str,
    features: pd.DataFrame,
    labels: np.ndarray,
    class_count: int,
    *,
    binary: bool,
) -> tuple[Pipeline, dict[str, Any], float]:
    pipeline = _pipeline(list(features.columns), _make_model(name, class_count))
    cv = StratifiedKFold(n_splits=OOF_SPLITS, shuffle=True, random_state=SEED)
    search = GridSearchCV(
        pipeline,
        _grid(name, binary),
        scoring="f1_macro",
        cv=cv,
        n_jobs=1,
        refit=True,
        error_score="raise",
        return_train_score=False,
    )
    started = time.perf_counter()
    search.fit(features, labels)
    return (
        search.best_estimator_,
        {
            "best_params": {
                key.removeprefix("model__"): value
                for key, value in search.best_params_.items()
            },
            "best_cv_macro_f1": float(search.best_score_),
            "cv_folds": OOF_SPLITS,
            "grid_size": sum(len(values) for values in _grid(name, binary).values()),
            "elapsed_seconds": time.perf_counter() - started,
        },
        time.perf_counter() - started,
    )


def _calibrate_pipeline(
    pipeline: Pipeline,
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    x_validation: pd.DataFrame,
    y_validation: np.ndarray,
    class_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cv = StratifiedKFold(n_splits=OOF_SPLITS, shuffle=True, random_state=SEED)
    oof = cross_val_predict(
        clone(pipeline),
        x_train,
        y_train,
        cv=cv,
        method="predict_proba",
        n_jobs=1,
    )
    validation_raw = pipeline.predict_proba(x_validation)
    calibrators, scores = _fit_calibrators(
        oof, y_train, validation_raw, y_validation, class_count
    )
    method = str(scores["selected_method"])
    calibrated_validation = apply_calibration(
        validation_raw, calibrators, method, class_count
    )
    thresholds = _calibration_threshold(
        _dropout_probability(calibrated_validation, class_count),
        (y_validation == 1).astype(int) if class_count == 2 else (y_validation == 0).astype(int),
    )
    selected_threshold = float(thresholds["0.5"]["threshold"])
    scores["oof_fit_rows"] = int(len(y_train))
    scores["oof_test_rows_used"] = 0
    scores["validation_calibrated"] = _metrics(
        y_validation,
        calibrated_validation,
        class_count,
        threshold=selected_threshold if class_count == 2 else None,
    )
    dropout_truth = (
        (y_validation == 1).astype(int)
        if class_count == 2
        else (y_validation == 0).astype(int)
    )
    scores["validation_dropout_alert"] = _alert_metrics(
        dropout_truth,
        _dropout_probability(calibrated_validation, class_count),
        selected_threshold,
    )
    warning_tiers = _warning_tier_metrics(
        _dropout_probability(calibrated_validation, class_count),
        dropout_truth,
        thresholds,
    )
    return (
        {
            "method": method,
            "calibrators": calibrators,
            "validation_scores": scores,
            "thresholds": thresholds,
            "warning_tiers": warning_tiers,
        },
        calibrated_validation,
    )


def _write_protocol(
    features: list[str],
    selected_name: str,
    is_binary: bool,
    calibration: dict[str, Any],
    test_metrics: dict[str, Any] | None,
) -> None:
    lines = [
        "# UCI-697 ML protocol",
        "",
        "- Dataset: UCI-697; target `Target`; seed `20261105`.",
        "- Split: stratified 60/20/20; train only for fitting and 5-fold tuning; "
        "validation only for model/threshold/calibration selection.",
        "- Test access: `ALLOW_TEST_EVAL=1`, one-shot loader with JSONL use log; "
        "must be run only after model and threshold selection.",
        "- Preprocessing (imputation, one-hot encoding, scaling) is fitted inside "
        "each train-only CV pipeline.",
        f"- Main feature set ({len(features)}): {', '.join(features)}.",
        "- Main features use only `available_at` T0/T1_known; excludes semester 2, "
        "Debtor, Tuition fees up to date, Scholarship holder, Unemployment rate, "
        "Inflation rate, GDP. Timestamps for the macro variables are unverified.",
        "- P1 sensitivity adds the excluded feature group separately; it is not "
        "used for the final model. A separate P1 run drops `Course` because it is "
        "a Portuguese program code with no NTU IT meaning.",
        f"- Selected early-warning model: `{selected_name}` "
        f"({'binary Dropout/Non-Dropout' if is_binary else 'three-class'}).",
        f"- Calibration chosen on validation after fitting on train OOF predictions: "
        f"`{calibration['method']}`. Validation Brier comparison: "
        f"`{json.dumps(calibration['validation_scores'], ensure_ascii=False)}`.",
        "- Dropout threshold maximizes recall subject to the 0.50 PPV floor when "
        "feasible; otherwise validation F2 fallback. No test-set tuning.",
        "- SHAP values explain model outputs, not causality; correlated features "
        "can share/redistribute attribution.",
        "- Enrolled is right-censored at data collection end, not necessarily a "
        "final outcome; it is not interpreted as a known dropout/graduate label.",
    ]
    if test_metrics is None:
        lines.extend(["", "Test evaluation: not run yet."])
    else:
        lines.extend(
            [
                "",
                "## One-time test evaluation",
                "",
                f"- Result: `{json.dumps(test_metrics, ensure_ascii=False)}`",
                "- Test was used once after all choices above were frozen.",
            ]
        )
    PROTOCOL_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pass_baselines(train: pd.DataFrame) -> dict[str, Any]:
    model = fit_pass_probability(train)
    non_dropout_model = fit_pass_probability(train[train[TARGET] != "Dropout"])
    pooled_table = {
        row["tier"]: row for row in pass_probability_table(model)
    }
    rows = []
    non_dropout_rows = []
    for tier in ("Thấp", "Trung bình", "Cao"):
        pool = model["strata"][tier]
        n = pool["students"]
        pooled = pooled_table[tier]
        rows.append(
            {
                "tier": tier,
                "low_max": model["thresholds"]["low_max"],
                "medium_max": model["thresholds"]["medium_max"],
                "n_students_raw_tier_with_hk2": n,
                "n_students_pooled": pooled["n_students"],
                "merged_tiers": "|".join(pooled["merged_tiers"]),
                "approved_units_hk2_pooled": pooled["approved_units_hk2"],
                "enrolled_units_hk2_pooled": pooled["enrolled_units_hk2"],
                "pooled_pass_rate": pooled["pooled_pass_rate"],
                "estimable": pooled["estimable"],
                "includes_later_dropout": True,
            }
        )
        sensitivity = non_dropout_model["strata"][tier]
        non_dropout_rows.append(
            {
                "tier": tier,
                "n_students_with_hk2": sensitivity["students"],
                "approved_units_hk2": sensitivity["approved_units"],
                "enrolled_units_hk2": sensitivity["enrolled_units"],
                "pooled_pass_rate": (
                    sensitivity["approved_units"] / sensitivity["enrolled_units"]
                    if sensitivity["enrolled_units"]
                    else None
                ),
                "warning": "P1 sensitivity only; survivorship bias because later Dropout students are removed.",
            }
        )
    output = ROOT / "reports" / "generated"
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "m3_prime_by_hk1_tier.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(non_dropout_rows).to_csv(
        output / "m3_prime_non_dropout_by_hk1_tier.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return {
        "model": model,
        "table": rows,
        "non_dropout_sensitivity": non_dropout_rows,
        "non_dropout_note": "P1 only; removing later Dropout students creates survivorship bias.",
    }


def _sensitivity_experiments(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    feature_columns: list[str],
    chosen_model_name: str,
    chosen_model_params: dict[str, Any],
    class_count: int,
) -> dict[str, Any]:
    y_train = _label_numbers(train[TARGET], binary=class_count == 2)
    y_validation = _label_numbers(validation[TARGET], binary=class_count == 2)
    excluded = [
        column
        for column in read_source().columns
        if column in {
            "Debtor",
            "Tuition fees up to date",
            "Scholarship holder",
            "Unemployment rate",
            "Inflation rate",
            "GDP",
        }
        or column.startswith("Curricular units 2nd sem")
    ]
    sensitivity: dict[str, Any] = {}
    for name, columns in (
        ("add_excluded_variables_P1", feature_columns + [item for item in excluded if item not in feature_columns]),
        ("drop_Course_P1", [item for item in feature_columns if item != "Course"]),
    ):
        model = _make_model(chosen_model_name, class_count, chosen_model_params)
        pipeline = _pipeline(columns, model)
        pipeline.fit(train[columns], y_train)
        probabilities = pipeline.predict_proba(validation[columns])
        sensitivity[name] = {
            "feature_count": len(columns),
            "metrics": _metrics(y_validation, probabilities, class_count),
        }
    sensitivity["excluded_variables"] = excluded
    sensitivity["course_domain_note"] = (
        "UCI Course is a Portuguese study-program code and has no direct NTU IT meaning."
    )
    return sensitivity


def _save_figures(
    y_validation: np.ndarray,
    raw_probabilities: np.ndarray,
    calibrated_probabilities: np.ndarray,
    class_count: int,
    feature_importance: pd.DataFrame,
) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    if class_count == 3:
        predicted = calibrated_probabilities.argmax(axis=1)
        labels = list(range(3))
        names = CLASS_NAMES
        actual_dropout = (y_validation == 0).astype(int)
    else:
        predicted = (calibrated_probabilities[:, 1] >= 0.5).astype(int)
        labels = [0, 1]
        names = ["Non-Dropout", "Dropout"]
        actual_dropout = y_validation
    matrix = confusion_matrix(y_validation, predicted, labels=labels)
    fig, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xticks(range(len(names)), names, rotation=25, ha="right")
    axis.set_yticks(range(len(names)), names)
    axis.set_xlabel("Predicted")
    axis.set_ylabel("Actual")
    axis.set_title("Validation confusion matrix")
    for (row, column), value in np.ndenumerate(matrix):
        axis.text(column, row, str(value), ha="center", va="center")
    fig.colorbar(image, ax=axis)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "confusion_matrix_validation.png", dpi=150)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6, 5))
    if class_count == 3:
        curves = [(index, CLASS_NAMES[index]) for index in range(3)]
        for index, name in curves:
            precision, recall, _ = precision_recall_curve(
                (y_validation == index).astype(int), raw_probabilities[:, index]
            )
            axis.plot(recall, precision, label=name)
    else:
        precision, recall, _ = precision_recall_curve(actual_dropout, raw_probabilities[:, 1])
        axis.plot(recall, precision, label="Dropout")
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precision")
    axis.set_title("Validation precision-recall curves (uncalibrated)")
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "precision_recall_validation.png", dpi=150)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6, 5))
    if class_count == 3:
        for index, name in enumerate(CLASS_NAMES):
            false_positive_rate, true_positive_rate, _ = roc_curve(
                (y_validation == index).astype(int), raw_probabilities[:, index]
            )
            axis.plot(false_positive_rate, true_positive_rate, label=name)
    else:
        false_positive_rate, true_positive_rate, _ = roc_curve(
            actual_dropout, raw_probabilities[:, 1]
        )
        axis.plot(false_positive_rate, true_positive_rate, label="Dropout")
    axis.plot([0, 1], [0, 1], "--", color="gray")
    axis.set_xlabel("False positive rate")
    axis.set_ylabel("True positive rate")
    axis.set_title("Validation ROC curves (uncalibrated)")
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "roc_validation.png", dpi=150)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6, 5))
    raw_dropout = _dropout_probability(raw_probabilities, class_count)
    calibrated_dropout = _dropout_probability(calibrated_probabilities, class_count)
    actual = (y_validation == 1).astype(int) if class_count == 2 else (y_validation == 0).astype(int)
    for values, label in ((raw_dropout, "Uncalibrated"), (calibrated_dropout, "Calibrated")):
        bins = np.linspace(0.0, 1.0, 11)
        means, observed = [], []
        for lower, upper in zip(bins[:-1], bins[1:]):
            selected = (values >= lower) & (values < upper if upper < 1 else values <= upper)
            if selected.any():
                means.append(float(values[selected].mean()))
                observed.append(float(actual[selected].mean()))
        axis.plot(means, observed, marker="o", label=label)
    axis.plot([0, 1], [0, 1], "--", color="gray")
    axis.set_xlabel("Mean predicted P(Dropout)")
    axis.set_ylabel("Observed dropout fraction")
    axis.set_title("Validation calibration")
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "calibration_validation.png", dpi=150)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8, 6))
    top = feature_importance.head(20).sort_values("mean_abs_shap")
    axis.barh(top["feature"], top["mean_abs_shap"])
    axis.set_title("Global SHAP importance (Dropout output)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "shap_global_validation.png", dpi=150)
    plt.close(fig)


def train_and_validate() -> dict[str, Any]:
    create_split_manifest()
    train = load_split("train")
    validation = load_split("validation")
    feature_columns = source_feature_columns()
    if len(feature_columns) != 24:
        raise ValueError(
            f"Expected 24 T0 + T1_known features, found {len(feature_columns)}: {feature_columns}"
        )
    forbidden = {"post_outcome", "T1_decision"} & set(feature_columns)
    if forbidden:
        raise ValueError(f"Forbidden post-outcome features selected: {sorted(forbidden)}")
    x_train = train[feature_columns]
    x_validation = validation[feature_columns]
    y_train = _label_numbers(train[TARGET])
    y_validation = _label_numbers(validation[TARGET])
    y_train_binary = _label_numbers(train[TARGET], binary=True)
    y_validation_binary = _label_numbers(validation[TARGET], binary=True)

    m3 = _pass_baselines(train)
    names = ("LogisticRegression", "RandomForest", "XGBoost")
    multiclass_pipelines: dict[str, Pipeline] = {}
    binary_pipelines: dict[str, Pipeline] = {}
    fit_details: dict[str, Any] = {"multiclass": {}, "binary": {}}
    validation_results: dict[str, Any] = {"multiclass": {}, "binary": {}}
    comparison_rows: list[dict[str, Any]] = []
    for name in names:
        pipe, details, _ = _train_search(
            name, x_train, y_train, 3, binary=False
        )
        multiclass_pipelines[name] = pipe
        fit_details["multiclass"][name] = details
        probabilities = pipe.predict_proba(x_validation)
        metrics = _metrics(y_validation, probabilities, 3)
        metrics["dropout_recall_at_precision_0.50"] = _recall_at_precision(
            y_validation_binary, probabilities[:, 0], 0.5
        )
        validation_results["multiclass"][name] = metrics
        comparison_rows.append(
            {
                "task": "three_class",
                "model": name,
                "accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "dropout_precision": metrics["per_class"]["Dropout"]["precision"],
                "dropout_recall": metrics["per_class"]["Dropout"]["recall"],
                "dropout_f1": metrics["per_class"]["Dropout"]["f1"],
                "dropout_pr_auc": metrics["pr_auc_one_vs_rest"]["Dropout"],
                "pr_auc_macro": metrics["pr_auc_macro"],
                "dropout_brier": metrics["brier_dropout"],
                "elapsed_seconds": details["elapsed_seconds"],
            }
        )
        binary_pipe, binary_details, _ = _train_search(
            name, x_train, y_train_binary, 2, binary=True
        )
        binary_pipelines[name] = binary_pipe
        fit_details["binary"][name] = binary_details
        binary_probabilities = binary_pipe.predict_proba(x_validation)
        binary_metrics = _metrics(
            y_validation_binary, binary_probabilities, 2, threshold=0.5
        )
        binary_metrics["dropout_recall_at_precision_0.50"] = _recall_at_precision(
            y_validation_binary, binary_probabilities[:, 1], 0.5
        )
        validation_results["binary"][name] = binary_metrics
        comparison_rows.append(
            {
                "task": "binary_dropout",
                "model": name,
                "accuracy": binary_metrics["accuracy"],
                "macro_f1": binary_metrics["macro_f1"],
                "dropout_precision": binary_metrics["per_class"]["Dropout"]["precision"],
                "dropout_recall": binary_metrics["per_class"]["Dropout"]["recall"],
                "dropout_f1": binary_metrics["per_class"]["Dropout"]["f1"],
                "dropout_pr_auc": binary_metrics["pr_auc_one_vs_rest"]["Dropout"],
                "pr_auc_macro": binary_metrics["pr_auc_macro"],
                "dropout_brier": binary_metrics["brier_dropout"],
                "elapsed_seconds": binary_details["elapsed_seconds"],
            }
        )

    class_weighted = _pipeline(
        feature_columns,
        _make_model("RandomForest", 3, {"class_weight": "balanced"}),
    )
    started = time.perf_counter()
    class_weighted.fit(x_train, y_train)
    class_weighted_seconds = time.perf_counter() - started
    weighted_probabilities = class_weighted.predict_proba(x_validation)
    weighted_metrics = _metrics(y_validation, weighted_probabilities, 3)
    ovr_model = OneVsRestClassifier(
        LogisticRegression(max_iter=2500, solver="lbfgs", random_state=SEED)
    )
    ovr_pipeline = _pipeline(feature_columns, ovr_model)
    started = time.perf_counter()
    ovr_pipeline.fit(x_train, y_train)
    ovr_seconds = time.perf_counter() - started
    ovr_probabilities = ovr_pipeline.predict_proba(x_validation)
    ovr_metrics = _metrics(y_validation, ovr_probabilities, 3)

    chosen_multiclass_name = max(
        names,
        key=lambda name: (
            validation_results["multiclass"][name]["macro_f1"],
            validation_results["multiclass"][name]["pr_auc_one_vs_rest"]["Dropout"],
        ),
    )
    chosen_binary_name = max(
        names,
        key=lambda name: (
            validation_results["binary"][name]["pr_auc_one_vs_rest"]["Dropout"],
            validation_results["binary"][name]["macro_f1"],
        ),
    )
    multi_score = validation_results["multiclass"][chosen_multiclass_name]
    binary_score = validation_results["binary"][chosen_binary_name]
    multi_recall = multi_score["dropout_recall_at_precision_0.50"]["recall"]
    binary_recall = binary_score["dropout_recall_at_precision_0.50"]["recall"]
    binary_brier = binary_score["brier_dropout"]
    multi_brier = multi_score["brier_dropout"]
    choose_binary = (binary_recall, -binary_brier) >= (multi_recall, -multi_brier)
    chosen_name = chosen_binary_name if choose_binary else chosen_multiclass_name
    class_count = 2 if choose_binary else 3
    chosen_pipeline = (
        binary_pipelines[chosen_name] if choose_binary else multiclass_pipelines[chosen_name]
    )
    chosen_y_train = y_train_binary if choose_binary else y_train
    chosen_y_validation = y_validation_binary if choose_binary else y_validation
    calibration, calibrated_validation = _calibrate_pipeline(
        chosen_pipeline,
        x_train,
        chosen_y_train,
        x_validation,
        chosen_y_validation,
        class_count,
    )
    raw_validation = chosen_pipeline.predict_proba(x_validation)
    calibration["validation_raw_metrics"] = _metrics(
        chosen_y_validation, raw_validation, class_count
    )
    calibration["validation_calibrated_metrics"] = _metrics(
        chosen_y_validation, calibrated_validation, class_count
    )

    chosen_params = fit_details["binary" if choose_binary else "multiclass"][chosen_name]["best_params"]
    p1 = _sensitivity_experiments(
        train,
        validation,
        feature_columns,
        chosen_name,
        chosen_params,
        class_count,
    )

    background_raw = x_train.sample(
        n=min(100, len(x_train)), random_state=SEED
    )
    preprocessor = chosen_pipeline.named_steps["preprocess"]
    background = preprocessor.transform(background_raw)
    validation_transformed = preprocessor.transform(x_validation)
    if hasattr(background, "toarray"):
        background = background.toarray()
    if hasattr(validation_transformed, "toarray"):
        validation_transformed = validation_transformed.toarray()
    feature_names = preprocessor.get_feature_names_out().tolist()
    shap_explainer = shap.Explainer(
        chosen_pipeline.named_steps["model"],
        background,
        feature_names=feature_names,
    )
    shap_indices: list[int] = []
    actual_y = _label_numbers(validation[TARGET])
    class_prob = chosen_pipeline.predict_proba(x_validation)
    dropout_prob = _dropout_probability(class_prob, class_count)
    candidates = [
        int(np.argmax(np.where(actual_y == 0, dropout_prob, -1))),
        int(np.argmin(np.where(actual_y == 0, dropout_prob, 2))),
        int(np.argmax(np.where(actual_y == 1, class_prob[:, 1] if class_count == 3 else class_prob[:, 0], -1))),
        int(np.argmax(np.where(actual_y == 2, class_prob[:, 2] if class_count == 3 else 0, -1))),
        int(np.argmin(np.where(actual_y == 2, class_prob[:, 2] if class_count == 3 else 0, 2))),
    ]
    for index in candidates:
        if index not in shap_indices:
            shap_indices.append(index)
    explanations = shap_explainer(validation_transformed[shap_indices])
    values = np.asarray(explanations.values)
    dropout_output = 1 if class_count == 2 else 0
    if values.ndim == 3:
        dropout_values = values[:, :, dropout_output]
    elif values.ndim == 2:
        dropout_values = values
    else:
        raise ValueError(f"Unexpected SHAP output dimensions: {values.shape}")
    feature_importance = pd.DataFrame(
        {
            "feature": feature_names,
            "mean_abs_shap": np.mean(np.abs(dropout_values), axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False)
    feature_importance.to_csv(
        ROOT / "reports" / "generated" / "shap_global.csv",
        index=False,
        encoding="utf-8-sig",
    )
    local_explanations = []
    for local_index, validation_index in enumerate(shap_indices):
        top_indices = np.argsort(np.abs(dropout_values[local_index]))[::-1][:10]
        local_explanations.append(
            {
                "row_id": str(validation.iloc[validation_index]["_row_id"]),
                "actual": str(validation.iloc[validation_index][TARGET]),
                "p_dropout": float(dropout_prob[validation_index]),
                "top_shap": [
                    {
                        "feature": feature_names[index],
                        "shap_value": float(dropout_values[local_index, index]),
                    }
                    for index in top_indices
                ],
            }
        )
    (ROOT / "reports" / "generated" / "shap_local_examples.json").write_text(
        json.dumps(local_explanations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _save_figures(
        chosen_y_validation,
        raw_validation,
        calibrated_validation,
        class_count,
        feature_importance,
    )

    distribution_rows = []
    for column in feature_columns:
        if pd.api.types.is_numeric_dtype(validation[column]):
            values_by_class = {
                name: validation.loc[validation[TARGET] == name, column].astype(float)
                for name in CLASS_NAMES
            }
            enrolled = values_by_class["Enrolled"]
            for other in ("Dropout", "Graduate"):
                comparison = values_by_class[other]
                pooled_sd = float(
                    np.sqrt((enrolled.var(ddof=1) + comparison.var(ddof=1)) / 2)
                )
                difference = float(enrolled.mean() - comparison.mean())
                distribution_rows.append(
                    {
                        "feature": column,
                        "comparison": f"Enrolled_vs_{other}",
                        "enrolled_mean": float(enrolled.mean()),
                        "comparison_mean": float(comparison.mean()),
                        "standardized_mean_difference": difference / pooled_sd if pooled_sd else 0.0,
                    }
                )
    enrolled_overlap = sorted(
        distribution_rows,
        key=lambda row: abs(row["standardized_mean_difference"]),
    )[:10]
    target_counts = validation[TARGET].value_counts().reindex(CLASS_NAMES, fill_value=0)
    enrolled_summary = {
        "validation_target_counts": target_counts.astype(int).to_dict(),
        "multiclass_models": {
            name: {
                "enrolled_precision": validation_results["multiclass"][name]["per_class"]["Enrolled"]["precision"],
                "enrolled_recall": validation_results["multiclass"][name]["per_class"]["Enrolled"]["recall"],
                "enrolled_f1": validation_results["multiclass"][name]["per_class"]["Enrolled"]["f1"],
                "enrolled_pr_auc": validation_results["multiclass"][name]["pr_auc_one_vs_rest"]["Enrolled"],
                "enrolled_roc_auc": validation_results["multiclass"][name]["roc_auc_one_vs_rest"]["Enrolled"],
            }
            for name in names
        },
        "random_forest_class_weight_balanced": {
            "elapsed_seconds": class_weighted_seconds,
            "enrolled": weighted_metrics["per_class"]["Enrolled"],
            "pr_auc": weighted_metrics["pr_auc_one_vs_rest"]["Enrolled"],
            "roc_auc": weighted_metrics["roc_auc_one_vs_rest"]["Enrolled"],
            "confusion_matrix": weighted_metrics["confusion_matrix"],
        },
        "logistic_one_vs_rest": {
            "elapsed_seconds": ovr_seconds,
            "enrolled": ovr_metrics["per_class"]["Enrolled"],
            "pr_auc": ovr_metrics["pr_auc_one_vs_rest"]["Enrolled"],
            "roc_auc": ovr_metrics["roc_auc_one_vs_rest"]["Enrolled"],
            "confusion_matrix": ovr_metrics["confusion_matrix"],
        },
        "selected_multiclass_confusion_matrix": multi_score["confusion_matrix"],
        "enrolled_numeric_mean_overlap": enrolled_overlap,
        "interpretation": (
            "Enrolled recall is low because observed validation Enrolled cases overlap "
            "in numeric T1 features with both other classes, and the class is smaller. "
            "The label is right-censored at collection end, not a confirmed final outcome."
        ),
    }
    enrolled_lines = [
        "# Enrolled-class analysis (validation only)",
        "",
        f"- Validation counts: `{json.dumps(enrolled_summary['validation_target_counts'])}`.",
        "- Enrolled is right-censored at the collection endpoint and may later become Graduate or Dropout.",
        "- PR-AUC and ROC-AUC are one-vs-rest on validation; confusion matrix follows class order Dropout, Enrolled, Graduate.",
        "",
        "| Model | Enrolled precision | Enrolled recall | Enrolled F1 | Enrolled PR-AUC | Enrolled ROC-AUC |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in names:
        row = enrolled_summary["multiclass_models"][name]
        enrolled_lines.append(
            f"| {name} | {row['enrolled_precision']:.4f} | {row['enrolled_recall']:.4f} | "
            f"{row['enrolled_f1']:.4f} | {row['enrolled_pr_auc']:.4f} | {row['enrolled_roc_auc']:.4f} |"
        )
    enrolled_lines.extend(
        [
            "",
            f"- Balanced Random Forest: `{json.dumps(enrolled_summary['random_forest_class_weight_balanced'], ensure_ascii=False)}`.",
            f"- One-vs-rest Logistic Regression: `{json.dumps(enrolled_summary['logistic_one_vs_rest'], ensure_ascii=False)}`.",
            f"- Selected three-class confusion matrix: `{json.dumps(enrolled_summary['selected_multiclass_confusion_matrix'])}`.",
            "- Smallest absolute standardized mean differences for numeric features are reported as overlap evidence:",
            "",
            "| Feature | Comparison | Enrolled mean | Other-class mean | Standardized difference |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in enrolled_overlap:
        enrolled_lines.append(
            f"| {row['feature']} | {row['comparison']} | {row['enrolled_mean']:.4f} | "
            f"{row['comparison_mean']:.4f} | {row['standardized_mean_difference']:.4f} |"
        )
    enrolled_lines.extend(
        [
            "",
            "These comparisons are descriptive evidence of overlap, not causal explanations. "
            "Class weighting/one-vs-rest do not guarantee that the censored Enrolled class is separable.",
            "",
        ]
    )
    (ROOT / "reports" / "generated" / "enrolled_analysis.md").write_text(
        "\n".join(enrolled_lines),
        encoding="utf-8",
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    chosen_threshold = calibration["thresholds"]["0.5"]["threshold"]
    bundle = {
        "model_version": "uci697-t1-20261105-v1",
        "model_name": chosen_name,
        "task": "binary_dropout" if choose_binary else "three_class",
        "class_count": class_count,
        "class_names": ["Non-Dropout", "Dropout"] if choose_binary else CLASS_NAMES,
        "feature_columns": feature_columns,
        "pipeline": chosen_pipeline,
        "calibration": calibration,
        "threshold_used": float(chosen_threshold),
        "warning_tiers_validation": calibration["warning_tiers"],
        "warning_thresholds": {
            "medium": calibration["thresholds"]["recall_0.90"]["threshold"],
            "high": calibration["thresholds"]["recall_0.70"]["threshold"],
        },
        "feature_names_out": feature_names,
        "shap_background": background,
        "threshold_note": "Selected on validation; prioritize recall subject to PPV >= 0.50 when feasible.",
        "scope_note": "ước lượng dựa trên kết quả học kỳ 1; hợp lệ ở mốc T1",
    }
    joblib.dump(bundle, MODEL_PATH)

    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    metrics = {
        "ml": {
            "protocol": {
                "seed": SEED,
                "split_counts": {
                    split: len(load_manifest()["splits"][split])
                    for split in ("train", "validation", "test")
                },
                "features": feature_columns,
                "feature_count": len(feature_columns),
                "model_fit_scope": "train_only",
                "test_rows_used_for_selection_or_calibration": 0,
                "cv_folds": OOF_SPLITS,
                "test_evaluations": 0,
            },
            "validation": validation_results,
            "model_selection": {
                "best_multiclass_by_macro_f1": chosen_multiclass_name,
                "best_binary_by_dropout_pr_auc": chosen_binary_name,
                "multi_recall_at_precision_0.5": multi_recall,
                "binary_recall_at_precision_0.5": binary_recall,
                "selected_model": chosen_name,
                "selected_task": "binary_dropout" if choose_binary else "three_class",
                "selection_reason": (
                    "Validation recall at precision >= 0.50 was prioritized; Brier breaks ties."
                ),
            },
            "fit_details": fit_details,
            "calibration": calibration["validation_scores"],
            "thresholds_and_tiers": calibration["thresholds"],
            "warning_tiers_validation": calibration["warning_tiers"],
            "dropout_alert_validation": calibration["validation_scores"]["validation_dropout_alert"],
            "m3_prime": m3,
            "enrolled_overlap_top_10": enrolled_overlap,
            "enrolled_analysis": enrolled_summary,
            "p1_sensitivity": p1,
            "shap": {
                "interpretation_note": "SHAP explains model behavior, not causality; correlated features can share attribution.",
                "top_20": feature_importance.head(20).to_dict(orient="records"),
                "five_representative_examples": local_explanations,
            },
        }
    }
    update_metrics(metrics, METRICS_PATH)
    _write_protocol(feature_columns, chosen_name, choose_binary, calibration, None)
    return metrics["ml"]


def evaluate_test_once() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Train and select a model first: {MODEL_PATH}")
    bundle = joblib.load(MODEL_PATH)
    test = load_split("test")
    x_test = test[bundle["feature_columns"]]
    class_count = int(bundle["class_count"])
    y_test = _label_numbers(test[TARGET], binary=class_count == 2)
    raw = bundle["pipeline"].predict_proba(x_test)
    calibration = bundle["calibration"]
    calibrated = apply_calibration(
        raw,
        calibration["calibrators"],
        calibration["method"],
        class_count,
    )
    metrics = _metrics(
        y_test,
        calibrated,
        class_count,
        threshold=float(bundle["threshold_used"]) if class_count == 2 else None,
    )
    metrics.update(
        {
            "model_name": bundle["model_name"],
            "task": bundle["task"],
            "calibration": calibration["method"],
            "test_rows": int(len(test)),
            "evaluation_count": 1,
            "test_access_log": "reports/generated/test_evaluation_log.jsonl",
            "dropout_alert": _alert_metrics(
                (y_test == 1).astype(int) if class_count == 2 else (y_test == 0).astype(int),
                _dropout_probability(calibrated, class_count),
                float(bundle["threshold_used"]),
            ),
            "warning_tiers": _warning_tier_metrics(
                _dropout_probability(calibrated, class_count),
                (y_test == 1).astype(int) if class_count == 2 else (y_test == 0).astype(int),
                calibration["thresholds"],
            ),
        }
    )
    TEST_METRICS_PATH.write_text(
        json.dumps(_jsonable(metrics), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    current = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    current["ml"]["protocol"]["test_evaluations"] = 1
    current["ml"]["test_once"] = metrics
    validation_metrics = current["ml"]["calibration"]["validation_calibrated"]
    current["ml"]["validation_test_delta"] = {
        "accuracy": metrics["accuracy"] - validation_metrics["accuracy"],
        "macro_f1": metrics["macro_f1"] - validation_metrics["macro_f1"],
        "dropout_precision": (
            metrics["per_class"]["Dropout"]["precision"]
            - validation_metrics["per_class"]["Dropout"]["precision"]
        ),
        "dropout_recall": (
            metrics["per_class"]["Dropout"]["recall"]
            - validation_metrics["per_class"]["Dropout"]["recall"]
        ),
        "dropout_f1": (
            metrics["per_class"]["Dropout"]["f1"]
            - validation_metrics["per_class"]["Dropout"]["f1"]
        ),
        "dropout_pr_auc": (
            metrics["pr_auc_one_vs_rest"]["Dropout"]
            - validation_metrics["pr_auc_one_vs_rest"]["Dropout"]
        ),
        "pr_auc_macro": metrics["pr_auc_macro"] - validation_metrics["pr_auc_macro"],
        "dropout_brier": metrics["brier_dropout"] - validation_metrics["brier_dropout"],
        "dropout_alert_precision": (
            metrics["dropout_alert"]["precision"]
            - current["ml"]["calibration"]["validation_dropout_alert"]["precision"]
        ),
        "dropout_alert_recall": (
            metrics["dropout_alert"]["recall"]
            - current["ml"]["calibration"]["validation_dropout_alert"]["recall"]
        ),
    }
    METRICS_PATH.write_text(
        json.dumps(_jsonable(current), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_protocol(
        bundle["feature_columns"],
        bundle["model_name"],
        bundle["class_count"] == 2,
        calibration,
        metrics,
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluate-test", action="store_true")
    parser.add_argument("--skip-test", action="store_true")
    args = parser.parse_args()
    if args.evaluate_test:
        print(json.dumps(evaluate_test_once(), ensure_ascii=False, indent=2))
        return 0
    result = train_and_validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.skip_test:
        print("Test evaluation not run. Use --evaluate-test after reviewing validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
