from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.simulation import run_monte_carlo_simulation


TMP = Path(__file__).resolve().parent
SEED = 20261108
N_RUNS = 1000
LAMBDA = 0.1
LAMBDA_TAG = "0_1"
STUDENT = "V2-003"
POLICY = "ILP-matched"


def _row(frame: pd.DataFrame) -> pd.Series:
    selected = frame.loc[
        frame["student_id"].eq(STUDENT)
        & frame["policy"].eq(POLICY)
        & pd.to_numeric(frame["lambda"], errors="coerce").eq(LAMBDA)
    ]
    if len(selected) != 1:
        raise ValueError(f"Expected one row for {STUDENT}/{POLICY}/{LAMBDA}; got {len(selected)}")
    return selected.iloc[0]


def main() -> None:
    start = time.perf_counter()
    reproduced, _, _ = run_monte_carlo_simulation(
        n_runs=N_RUNS,
        lambdas=(LAMBDA,),
        policies=(POLICY,),
        seed=SEED,
        student_ids=[STUDENT],
        n_workers=4,
    )
    elapsed = time.perf_counter() - start
    histogram = reproduced.attrs.get("graduation_histogram")
    if not isinstance(histogram, pd.DataFrame):
        raise RuntimeError("Simulation did not return its graduation histogram")

    reference = pd.read_csv(ROOT / "reports" / "generated" / "mc_results_lambda_0_3.csv")
    stored_row, reproduced_row = _row(reference), _row(reproduced)
    numeric_columns = [
        column for column in reference.columns if pd.api.types.is_numeric_dtype(reference[column])
    ]
    comparisons = []
    for column in numeric_columns:
        saved = stored_row[column]
        actual = reproduced_row[column]
        if pd.isna(saved) and pd.isna(actual):
            same, delta = True, 0.0
        else:
            saved_number = pd.to_numeric(pd.Series([saved]), errors="coerce").iloc[0]
            actual_number = pd.to_numeric(pd.Series([actual]), errors="coerce").iloc[0]
            if pd.notna(saved_number) and pd.notna(actual_number):
                delta = abs(float(saved_number) - float(actual_number))
                same = delta <= 1e-9
            else:
                delta = None
                same = str(saved) == str(actual)
        comparisons.append(
            {
                "column": column,
                "stored": saved,
                "reproduced": actual,
                "absolute_difference": delta,
                "status": "MATCH" if same else "MISMATCH",
            }
        )
    comparison_frame = pd.DataFrame(comparisons)
    comparison_frame.to_csv(
        TMP / f"V2-003_lambda_{LAMBDA_TAG}_numeric_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metadata_differences = [
        column
        for column in reference.columns
        if column not in numeric_columns
        and str(stored_row[column]) != str(reproduced_row[column])
    ]
    row_keys_match = all(
        str(stored_row[column]) == str(reproduced_row[column])
        for column in ("student_id", "policy")
    )

    stored_hist = pd.read_csv(ROOT / "reports" / "generated" / "mc_grad_hist.csv")
    mask = (
        stored_hist["student_id"].eq(STUDENT)
        & stored_hist["policy"].eq(POLICY)
        & pd.to_numeric(stored_hist["lambda"], errors="coerce").eq(LAMBDA)
    )
    stored_hist = stored_hist.loc[mask]
    actual_hist = histogram.loc[
        histogram["student_id"].eq(STUDENT)
        & histogram["policy"].eq(POLICY)
        & pd.to_numeric(histogram["lambda"], errors="coerce").eq(LAMBDA)
    ]
    keys = ["student_id", "policy", "lambda", "outcome", "semester"]
    merged = stored_hist.merge(
        actual_hist,
        on=keys,
        how="outer",
        suffixes=("_stored", "_reproduced"),
        indicator=True,
    )
    keys_match = bool(merged["_merge"].eq("both").all())
    counts_match = all(
        (
            pd.to_numeric(merged[f"{column}_stored"])
            - pd.to_numeric(merged[f"{column}_reproduced"])
        ).abs().le(1e-9).all()
        for column in ("count", "n_total")
    )
    merged.to_csv(
        TMP / f"V2-003_lambda_{LAMBDA_TAG}_histogram_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    reproduced.to_csv(
        TMP / f"V2-003_lambda_{LAMBDA_TAG}_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    histogram.to_csv(
        TMP / f"V2-003_lambda_{LAMBDA_TAG}_grad_hist.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary = {
        "group": f"{STUDENT}/{POLICY}/lambda={LAMBDA}",
        "seed": SEED,
        "n_runs": N_RUNS,
        "policy_count": 1,
        "elapsed_seconds": elapsed,
        "result_columns": len(numeric_columns),
        "result_matches": int(comparison_frame["status"].eq("MATCH").sum()),
        "result_mismatches": int(comparison_frame["status"].ne("MATCH").sum()),
        "row_keys_match": bool(row_keys_match),
        "metadata_differences": metadata_differences,
        "histogram_rows_stored": len(stored_hist),
        "histogram_rows_reproduced": len(actual_hist),
        "histogram_keys_match": keys_match,
        "histogram_counts_n_total_match": bool(counts_match),
        "metadata_difference": "source_label excluded from gate",
    }
    (TMP / f"V2-003_lambda_{LAMBDA_TAG}_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
