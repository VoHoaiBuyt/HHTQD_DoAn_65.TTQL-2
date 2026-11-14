"""Benchmark dropout-risk models on REAL UCI-697 data.

Protocol (no test leakage):
1. Stratified 60/20/20 train/validation/test split.
2. 5-fold stratified CV on train only (model comparison + spread).
3. Probability calibration (isotonic) and decision threshold are fitted
   on validation only.
4. Test is scored once with the frozen calibration + threshold.

Tasks: 3-class (Dropout/Enrolled/Graduate) and binary (Dropout/Non-Dropout).
Models: Logistic Regression, Random Forest, LightGBM.
Outputs: reports/generated/ml_benchmark_*.csv, shap_*.csv/.png, meta JSON.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd
import shap
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import make_pipeline

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.risk_to_plan_exploration import (
    SEED,
    _load_real_data,
    _preprocessor,
)

OUTPUT_DIR = ROOT / "reports" / "generated"
POSITIVE_LABEL = "Dropout"
THREE_CLASS_LABELS = ["Dropout", "Enrolled", "Graduate"]
BINARY_LABELS = ["Dropout", "Non-Dropout"]
THRESHOLD_GRID = np.round(np.linspace(0.05, 0.95, 181), 3)


def _make_estimators() -> dict[str, Any]:
    return {
        "LogisticRegression": LogisticRegression(
            max_iter=3000,
            class_weight="balanced",
            random_state=SEED,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=400,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=SEED,
            n_jobs=-1,
        ),
        "LightGBM": LGBMClassifier(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.9,
            colsample_bytree=0.8,
            class_weight="balanced",
            random_state=SEED,
            n_jobs=-1,
            verbose=-1,
        ),
    }


def _positive_probability(estimator: Any, features: pd.DataFrame) -> np.ndarray:
    classes = list(estimator.classes_)
    return estimator.predict_proba(features)[:, classes.index(POSITIVE_LABEL)]


def _scorer_dropout_f1(estimator: Any, features: pd.DataFrame, target: pd.Series) -> float:
    return float(
        f1_score(
            target.eq(POSITIVE_LABEL),
            _positive_probability(estimator, features) >= 0.5,
            zero_division=0,
        )
    )


def _scorer_dropout_pr_auc(estimator: Any, features: pd.DataFrame, target: pd.Series) -> float:
    return float(
        average_precision_score(
            target.eq(POSITIVE_LABEL),
            _positive_probability(estimator, features),
        )
    )


def _scorer_dropout_brier(estimator: Any, features: pd.DataFrame, target: pd.Series) -> float:
    return float(
        brier_score_loss(
            target.eq(POSITIVE_LABEL),
            _positive_probability(estimator, features),
        )
    )


def _cross_validation(
    pipeline: Any,
    features: pd.DataFrame,
    target: pd.Series,
) -> tuple[dict[str, float], pd.DataFrame]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    result = cross_validate(
        pipeline,
        features,
        target,
        cv=cv,
        scoring={
            "accuracy": "accuracy",
            "f1_macro": "f1_macro",
            "f1_dropout": _scorer_dropout_f1,
            "pr_auc_dropout": _scorer_dropout_pr_auc,
            "brier_dropout": _scorer_dropout_brier,
        },
        n_jobs=1,
    )
    summary = {
        f"cv_{metric}_mean": float(result[f"test_{metric}"].mean())
        for metric in (
            "accuracy",
            "f1_macro",
            "f1_dropout",
            "pr_auc_dropout",
            "brier_dropout",
        )
    }
    summary.update(
        {
            f"cv_{metric}_std": float(result[f"test_{metric}"].std())
            for metric in (
                "accuracy",
                "f1_macro",
                "f1_dropout",
                "pr_auc_dropout",
                "brier_dropout",
            )
        }
    )
    folds = pd.DataFrame(
        {
            "fold": np.arange(1, len(result["test_accuracy"]) + 1),
            "accuracy": result["test_accuracy"],
            "f1_macro": result["test_f1_macro"],
            "f1_dropout": result["test_f1_dropout"],
            "pr_auc_dropout": result["test_pr_auc_dropout"],
            "brier_dropout": result["test_brier_dropout"],
        }
    )
    return summary, folds


def _decision_predictions(
    probabilities: np.ndarray,
    classes: list[str],
    threshold: float,
) -> np.ndarray:
    dropout_index = classes.index(POSITIVE_LABEL)
    other_indices = [index for index, name in enumerate(classes) if name != POSITIVE_LABEL]
    other_best = np.asarray(classes)[other_indices][
        np.argmax(probabilities[:, other_indices], axis=1)
    ]
    return np.where(probabilities[:, dropout_index] >= threshold, POSITIVE_LABEL, other_best)


def _select_threshold(
    target: pd.Series,
    probabilities: np.ndarray,
    classes: list[str],
) -> tuple[float, pd.DataFrame]:
    actual_dropout = target.eq(POSITIVE_LABEL)
    rows = []
    for threshold in THRESHOLD_GRID:
        predicted = _decision_predictions(probabilities, classes, float(threshold))
        rows.append(
            {
                "threshold": float(threshold),
                "macro_f1": float(f1_score(target, predicted, average="macro", zero_division=0)),
                "dropout_f1": float(
                    f1_score(actual_dropout, predicted == POSITIVE_LABEL, zero_division=0)
                ),
                "dropout_recall": float(
                    recall_score(actual_dropout, predicted == POSITIVE_LABEL, zero_division=0)
                ),
            }
        )
    table = pd.DataFrame(rows)
    ranked = table.sort_values(
        ["macro_f1", "dropout_f1", "threshold"],
        ascending=[False, False, True],
    )
    best = ranked.iloc[0]
    return float(best["threshold"]), table


def _fit_calibrator(target: pd.Series, probabilities: np.ndarray) -> IsotonicRegression:
    return IsotonicRegression(out_of_bounds="clip").fit(
        probabilities,
        target.eq(POSITIVE_LABEL).astype(float),
    )


def _calibrate(calibrator: IsotonicRegression, probabilities: np.ndarray) -> np.ndarray:
    return np.clip(calibrator.predict(probabilities), 0.0, 1.0)


def _reliability_table(
    target: pd.Series,
    probabilities: np.ndarray,
    bins: int = 10,
) -> tuple[pd.DataFrame, float]:
    frame = pd.DataFrame(
        {
            "probability": probabilities,
            "actual": target.eq(POSITIVE_LABEL).astype(int),
        }
    )
    frame["bin"] = pd.qcut(
        frame["probability"].rank(method="first"),
        q=bins,
        labels=False,
    )
    grouped = frame.groupby("bin", sort=True)
    table = grouped.agg(
        n=("actual", "size"),
        predicted_mean=("probability", "mean"),
        observed_rate=("actual", "mean"),
    ).reset_index()
    table["gap"] = (table["observed_rate"] - table["predicted_mean"]).abs()
    ece = float((table["n"] / table["n"].sum() * table["gap"]).sum())
    return table, ece


def _classification_metrics(
    target: pd.Series,
    predicted: np.ndarray,
    probabilities: np.ndarray,
    classes: list[str],
    threshold: float,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    actual_dropout = target.eq(POSITIVE_LABEL)
    predicted_dropout = predicted == POSITIVE_LABEL
    precision, recall, f1, support = precision_recall_fscore_support(
        target,
        predicted,
        labels=classes,
        zero_division=0,
    )
    per_class = pd.DataFrame(
        {
            "class": classes,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "predicted_count": [int((predicted == label).sum()) for label in classes],
        }
    )
    matrix = confusion_matrix(target, predicted, labels=classes)
    confusion = pd.DataFrame(
        [
            {
                "true_label": true_label,
                "predicted_label": predicted_label,
                "count": int(matrix[true_index, predicted_index]),
            }
            for true_index, true_label in enumerate(classes)
            for predicted_index, predicted_label in enumerate(classes)
        ]
    )
    metrics = {
        "accuracy": float(accuracy_score(target, predicted)),
        "macro_f1": float(f1_score(target, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(
            f1_score(target, predicted, average="weighted", zero_division=0)
        ),
        "dropout_precision": float(
            precision[classes.index(POSITIVE_LABEL)]
        ),
        "dropout_recall": float(recall[classes.index(POSITIVE_LABEL)]),
        "dropout_f1": float(f1[classes.index(POSITIVE_LABEL)]),
        "dropout_pr_auc": float(
            average_precision_score(actual_dropout, probabilities)
        ),
        "dropout_roc_auc": float(roc_auc_score(actual_dropout, probabilities)),
        "brier_dropout": float(brier_score_loss(actual_dropout, probabilities)),
        "log_loss": float(
            log_loss(
                actual_dropout,
                np.column_stack([1.0 - probabilities, probabilities]),
            )
        ),
        "threshold_selected_on_validation": threshold,
        "test_dropout_predicted_share": float(predicted_dropout.mean()),
    }
    return metrics, per_class, confusion


def _enrolled_analysis(
    target: pd.Series,
    predicted: np.ndarray,
    per_class: pd.DataFrame,
) -> dict[str, Any]:
    enrolled = target.eq("Enrolled")
    enrolled_recall = float(per_class.loc[per_class["class"].eq("Enrolled"), "recall"].iloc[0])
    return {
        "enrolled_support": int(enrolled.sum()),
        "enrolled_recall": enrolled_recall,
        "enrolled_predicted_as_dropout": int((enrolled & (predicted == "Dropout")).sum()),
        "enrolled_predicted_as_graduate": int((enrolled & (predicted == "Graduate")).sum()),
        "note": (
            "Enrolled là trạng thái quan sát tại T1, không phải kết cục cuối; "
            "recall thấp là kỳ vọng và không dùng làm chỉ số an toàn."
        ),
    }


def _fit_and_evaluate(
    task: str,
    model_name: str,
    pipeline: Any,
    train_x: pd.DataFrame,
    train_y: pd.Series,
    validation_x: pd.DataFrame,
    validation_y: pd.Series,
    test_x: pd.DataFrame,
    test_y: pd.Series,
    classes: list[str],
) -> tuple[dict[str, Any], dict[str, pd.DataFrame], Any]:
    cv_summary, cv_folds = _cross_validation(pipeline, train_x, train_y)
    pipeline.fit(train_x, train_y)

    dropout_index = classes.index(POSITIVE_LABEL)
    validation_probabilities = pipeline.predict_proba(validation_x)
    calibrator = _fit_calibrator(validation_y, validation_probabilities[:, dropout_index])
    validation_calibrated = _calibrate(
        calibrator, validation_probabilities[:, dropout_index]
    )
    validation_probabilities[:, dropout_index] = validation_calibrated
    threshold, threshold_table = _select_threshold(
        validation_y, validation_probabilities, classes
    )
    validation_predicted = _decision_predictions(
        validation_probabilities, classes, threshold
    )
    validation_metrics, _, _ = _classification_metrics(
        validation_y,
        validation_predicted,
        validation_calibrated,
        classes,
        threshold,
    )

    test_probabilities = pipeline.predict_proba(test_x)
    test_calibrated = _calibrate(
        calibrator, test_probabilities[:, dropout_index]
    )
    test_probabilities[:, dropout_index] = test_calibrated
    test_predicted = _decision_predictions(test_probabilities, classes, threshold)
    test_metrics, per_class, confusion = _classification_metrics(
        test_y,
        test_predicted,
        test_calibrated,
        classes,
        threshold,
    )
    reliability, ece = _reliability_table(test_y, test_calibrated)

    summary = {
        "task": task,
        "model": model_name,
        "protocol": "60/20/20 stratified; CV on train; calibration+threshold on validation; test scored once",
        "classes": "|".join(classes),
        "train_size": len(train_x),
        "validation_size": len(validation_x),
        "test_size": len(test_x),
        "validation_macro_f1_at_threshold": validation_metrics["macro_f1"],
        "validation_dropout_f1_at_threshold": validation_metrics["dropout_f1"],
        "validation_dropout_pr_auc": validation_metrics["dropout_pr_auc"],
        "test_ece": ece,
        **cv_summary,
        **test_metrics,
    }
    frames = {
        "per_class": per_class.assign(task=task, model=model_name),
        "confusion": confusion.assign(task=task, model=model_name),
        "cv_folds": cv_folds.assign(task=task, model=model_name),
        "calibration": reliability.assign(task=task, model=model_name),
        "threshold_curve": threshold_table.assign(task=task, model=model_name),
    }
    extra = {
        "pipeline": pipeline,
        "calibrator": calibrator,
        "threshold": threshold,
        "test_probabilities": test_calibrated,
        "test_predictions": test_predicted,
    }
    return summary, frames, extra


def _select_dropout_shap_values(raw_values: Any, dropout_index: int) -> np.ndarray:
    if isinstance(raw_values, list):
        return np.asarray(raw_values[dropout_index])
    array = np.asarray(raw_values)
    if array.ndim == 3:
        return array[:, :, dropout_index]
    return array


def _shap_importance(
    values: np.ndarray,
    feature_names: list[str],
    model_label: str,
    plot_name: str,
) -> tuple[pd.DataFrame, Path]:
    importance = pd.DataFrame(
        {
            "feature": feature_names,
            "mean_abs_shap": np.abs(values).mean(axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False)
    importance.insert(0, "rank", np.arange(1, len(importance) + 1))
    importance["caveat"] = (
        "SHAP chỉ mô tả mức đóng góp của feature vào dự đoán của mô hình, "
        "không phải quan hệ nhân quả."
    )

    plot_path = OUTPUT_DIR / plot_name
    top = importance.head(15).iloc[::-1]
    fig, axis = plt.subplots(figsize=(8.0, 5.5))
    axis.barh(top["feature"], top["mean_abs_shap"], color="#2f6f9f")
    axis.set_xlabel("mean(|SHAP value|) cho lớp Dropout")
    axis.set_title(f"{model_label} – 15 feature ảnh hưởng mạnh nhất (REAL UCI-697)")
    fig.tight_layout()
    fig.savefig(plot_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return importance, plot_path


def _shap_for_lightgbm(
    pipeline: Any,
    explain_x: pd.DataFrame,
) -> tuple[pd.DataFrame, Path]:
    preprocessor = pipeline.named_steps["columntransformer"]
    model = pipeline.named_steps["lgbmclassifier"]
    explain = preprocessor.transform(explain_x)
    if hasattr(explain, "toarray"):
        explain = explain.toarray()
    feature_names = [str(name) for name in preprocessor.get_feature_names_out()]
    dropout_index = list(model.classes_).index(POSITIVE_LABEL)
    explainer = shap.TreeExplainer(model)
    raw_values = explainer.shap_values(explain, check_additivity=False)
    values = _select_dropout_shap_values(raw_values, dropout_index)
    return _shap_importance(
        values, feature_names, "LightGBM", "shap_dropout_top15.png"
    )


def _shap_for_logistic(
    pipeline: Any,
    background_x: pd.DataFrame,
    explain_x: pd.DataFrame,
) -> tuple[pd.DataFrame, Path]:
    preprocessor = pipeline.named_steps["columntransformer"]
    model = pipeline.named_steps["logisticregression"]
    background = preprocessor.transform(background_x)
    explain = preprocessor.transform(explain_x)
    if hasattr(background, "toarray"):
        background = background.toarray()
    if hasattr(explain, "toarray"):
        explain = explain.toarray()
    feature_names = [str(name) for name in preprocessor.get_feature_names_out()]
    dropout_index = list(model.classes_).index(POSITIVE_LABEL)
    masker = shap.maskers.Independent(background, max_samples=200)
    explainer = shap.LinearExplainer(model, masker)
    raw_values = explainer.shap_values(explain)
    values = _select_dropout_shap_values(raw_values, dropout_index)
    return _shap_importance(
        values, feature_names, "LogisticRegression", "shap_dropout_top15_lr.png"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data, features, categories, numeric = _load_real_data()
    target_three = data["Target"].astype(str)

    indices = np.arange(len(data))
    train_indices, temporary_indices = train_test_split(
        indices,
        test_size=0.4,
        random_state=SEED,
        stratify=target_three,
    )
    validation_indices, test_indices = train_test_split(
        temporary_indices,
        test_size=0.5,
        random_state=SEED,
        stratify=target_three.iloc[temporary_indices],
    )

    tasks = {
        "3-class": {
            "labels": THREE_CLASS_LABELS,
            "target": target_three,
        },
        "binary": {
            "labels": BINARY_LABELS,
            "target": np.where(target_three.eq(POSITIVE_LABEL), "Dropout", "Non-Dropout"),
        },
    }
    tasks["binary"]["target"] = pd.Series(
        tasks["binary"]["target"], index=target_three.index
    )

    summary_rows: list[dict[str, Any]] = []
    per_class_frames: list[pd.DataFrame] = []
    confusion_frames: list[pd.DataFrame] = []
    cv_frames: list[pd.DataFrame] = []
    calibration_frames: list[pd.DataFrame] = []
    threshold_frames: list[pd.DataFrame] = []
    enrolled_rows: list[dict[str, Any]] = []
    shap_pipeline = None
    linear_pipeline = None

    for task, config in tasks.items():
        labels = config["labels"]
        target = config["target"]
        train_x = data[features].iloc[train_indices]
        train_y = target.iloc[train_indices]
        validation_x = data[features].iloc[validation_indices]
        validation_y = target.iloc[validation_indices]
        test_x = data[features].iloc[test_indices]
        test_y = target.iloc[test_indices]

        for model_name, estimator in _make_estimators().items():
            pipeline = make_pipeline(_preprocessor(categories, numeric), estimator)
            summary, frames, extra = _fit_and_evaluate(
                task,
                model_name,
                pipeline,
                train_x,
                train_y,
                validation_x,
                validation_y,
                test_x,
                test_y,
                labels,
            )
            summary_rows.append(summary)
            per_class_frames.append(frames["per_class"])
            confusion_frames.append(frames["confusion"])
            cv_frames.append(frames["cv_folds"])
            calibration_frames.append(frames["calibration"])
            threshold_frames.append(frames["threshold_curve"])
            if task == "3-class":
                enrolled_rows.append(
                    {
                        "task": task,
                        "model": model_name,
                        **_enrolled_analysis(test_y, extra["test_predictions"], frames["per_class"]),
                    }
                )
            if task == "3-class" and model_name == "LightGBM":
                shap_pipeline = extra["pipeline"]
            if task == "3-class" and model_name == "LogisticRegression":
                linear_pipeline = extra["pipeline"]

            print(
                f"{task:8s} {model_name:20s} test macro-F1={summary['macro_f1']:.4f} "
                f"dropout-F1={summary['dropout_f1']:.4f} "
                f"PR-AUC={summary['dropout_pr_auc']:.4f} "
                f"Brier={summary['brier_dropout']:.4f} thr={summary['threshold_selected_on_validation']:.2f}"
            )

    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(OUTPUT_DIR / "ml_benchmark_summary.csv", index=False)
    pd.concat(per_class_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "ml_benchmark_per_class.csv", index=False
    )
    pd.concat(confusion_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "ml_benchmark_confusion.csv", index=False
    )
    pd.concat(cv_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "ml_benchmark_cv_folds.csv", index=False
    )
    pd.concat(calibration_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "ml_benchmark_calibration.csv", index=False
    )
    pd.concat(threshold_frames, ignore_index=True).to_csv(
        OUTPUT_DIR / "ml_benchmark_threshold_curve.csv", index=False
    )
    pd.DataFrame(enrolled_rows).to_csv(
        OUTPUT_DIR / "ml_benchmark_enrolled_analysis.csv", index=False
    )

    shap_path = None
    if shap_pipeline is not None:
        importance, shap_path = _shap_for_lightgbm(
            shap_pipeline,
            data[features].iloc[test_indices],
        )
        importance.to_csv(OUTPUT_DIR / "shap_dropout_importance.csv", index=False)
        print("SHAP LightGBM top-10:")
        print(importance.head(10)[["rank", "feature", "mean_abs_shap"]].to_string(index=False))

    linear_shap_path = None
    if linear_pipeline is not None:
        linear_importance, linear_shap_path = _shap_for_logistic(
            linear_pipeline,
            data[features].iloc[train_indices],
            data[features].iloc[test_indices],
        )
        linear_importance.to_csv(
            OUTPUT_DIR / "shap_dropout_importance_lr.csv", index=False
        )
        print("SHAP LogisticRegression top-10:")
        print(
            linear_importance.head(10)[
                ["rank", "feature", "mean_abs_shap"]
            ].to_string(index=False)
        )
    print(
        "Lưu ý: SHAP chỉ là mức đóng góp của feature vào dự đoán, "
        "không chứng minh quan hệ nhân quả."
    )

    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": SEED,
        "data_label": "REAL (UCI-697)",
        "target_label": "Target (Dropout/Enrolled/Graduate), dự đoán tại T1",
        "feature_count": len(features),
        "features": features,
        "split": {
            "train": len(train_indices),
            "validation": len(validation_indices),
            "test": len(test_indices),
            "strategy": "stratified 60/20/20 on 3-class target",
        },
        "cross_validation": "5-fold stratified on train only",
        "calibration": "isotonic fitted on validation predictions only",
        "threshold": "selected on validation macro-F1 (tie-break dropout F1); test never used",
        "metrics": "accuracy, macro-F1, per-class P/R/F1, dropout PR-AUC/ROC-AUC, Brier, log-loss, confusion matrix",
        "caveats": [
            "Enrolled là trạng thái quan sát tại T1, không phải kết cục cuối.",
            "SHAP mô tả đóng góp vào dự đoán của mô hình, không phải nhân quả.",
            "Dữ liệu REAL của UCI-697; CTĐT và kịch bản ILP là SIMULATED/ASSUMPTION.",
        ],
        "versions": {
            "lightgbm": lgb.__version__,
            "shap": shap.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "shap_plot_lightgbm": (
            str(shap_path.relative_to(ROOT)) if shap_path else None
        ),
        "shap_plot_logistic": (
            str(linear_shap_path.relative_to(ROOT)) if linear_shap_path else None
        ),
    }
    (OUTPUT_DIR / "ml_benchmark_meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Đã ghi kết quả vào {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
