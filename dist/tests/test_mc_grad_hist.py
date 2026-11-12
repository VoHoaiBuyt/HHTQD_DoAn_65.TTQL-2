from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.simulation import (
    build_graduation_histogram,
    validate_graduation_histogram,
)


TEST_FIXTURE = "TEST_FIXTURE"


def _raw_results() -> dict[tuple[str, str, float, str], np.ndarray]:
    student_id = f"{TEST_FIXTURE}-001"
    policy = "TEST_FIXTURE_POLICY"
    load_lambda = 0.1
    return {
        (student_id, policy, load_lambda, "graduated_16"): np.array(
            [1, 1, 1, 0, 0], dtype=bool
        ),
        (student_id, policy, load_lambda, "forced_withdrawal"): np.array(
            [0, 0, 0, 1, 0], dtype=bool
        ),
        (student_id, policy, load_lambda, "graduation_semester"): np.array(
            [7, 9, 16, 16, 16], dtype=float
        ),
    }


def test_histogram_counts_partition_all_runs_and_match_on_time_probability() -> None:
    student_id = f"{TEST_FIXTURE}-001"
    policy = "TEST_FIXTURE_POLICY"
    load_lambda = 0.1
    result = pd.DataFrame(
        [
            {
                "student_id": student_id,
                "policy": policy,
                "lambda": load_lambda,
                "n_runs": 5,
                "p_graduated_on_time": 0.2,
            }
        ]
    )
    histogram = build_graduation_histogram(
        _raw_results(),
        [student_id],
        (policy,),
        (load_lambda,),
        n_total=5,
    )
    validate_graduation_histogram(histogram, result)

    assert histogram["count"].sum() == 5
    assert histogram.loc[
        histogram["outcome"].eq("graduated")
        & histogram["semester"].le(8),
        "count",
    ].sum() / 5 == result.loc[0, "p_graduated_on_time"]
    assert set(histogram["outcome"]) == {
        "graduated",
        "forced_withdrawal",
        "not_finished_16",
    }
    assert histogram.loc[
        histogram["outcome"].eq("graduated"), "semester"
    ].tolist() == [7, 9, 16]
    assert histogram.loc[
        histogram["outcome"].ne("graduated"), "semester"
    ].isna().all()


def test_histogram_validation_rejects_nonmatching_on_time_probability() -> None:
    student_id = f"{TEST_FIXTURE}-001"
    policy = "TEST_FIXTURE_POLICY"
    histogram = build_graduation_histogram(
        _raw_results(),
        [student_id],
        (policy,),
        (0.1,),
        n_total=5,
    )
    result = pd.DataFrame(
        [
            {
                "student_id": student_id,
                "policy": policy,
                "lambda": 0.1,
                "n_runs": 5,
                "p_graduated_on_time": 0.4,
            }
        ]
    )
    with pytest.raises(ValueError, match="probability mismatch"):
        validate_graduation_histogram(histogram, result)
