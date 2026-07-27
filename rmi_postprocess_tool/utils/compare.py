from __future__ import annotations

import math

import pandas as pd

from utils.config import RunSpec


def pct_diff(second: float, first: float) -> float:
    """
    Percent difference using the first run as the baseline:

        (second - first) / abs(first) * 100
    """
    if pd.isna(first) or pd.isna(second):
        return math.nan

    if first == 0:
        if second == 0:
            return 0.0
        return math.inf if second > 0 else -math.inf

    return (second - first) / abs(first) * 100.0


def compare_two_run_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    runs: list[RunSpec],
    keys: list[str],
) -> pd.DataFrame:
    """
    Inner-join two run-specific frames and calculate percent difference.

    Each frame must include:
    - all key columns
    - one value column named after the corresponding run
    """
    if len(runs) != 2:
        raise ValueError("compare_two_run_frames expects exactly two runs")

    first_col = runs[0].name
    second_col = runs[1].name

    merged = left.merge(right, on=keys, how="inner")
    merged["diff_pct"] = [
        pct_diff(second, first)
        for first, second in zip(merged[first_col], merged[second_col])
    ]

    return merged
