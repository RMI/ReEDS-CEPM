from __future__ import annotations

import pandas as pd

from utils.capacity_mix import build_installed_capacity_mix_long
from utils.config import ProjectConfig


def build_capacity_changes_long(config: ProjectConfig) -> pd.DataFrame:
    """
    Build waterfall-ready capacity change rows.

    Output columns:
    - waterfall_column
    - capacity_category
    - capacity_mw

    For each configured state/year, this compares the two configured runs
    in TOML order:

        run_1 base -> reductions -> additions -> run_2 base

    Base columns are broken out by capacity category, not represented as a
    separate Total row. The chart should stack those capacity categories to
    show the total capacity for each base run.

    Reductions and additions compare run_2 against run_1 for the same state,
    year, and capacity category.

    Reductions are negative.
    Additions are positive.
    """
    if len(config.runs) != 2:
        raise ValueError(
            f"Capacity changes expects exactly two runs, found {len(config.runs)}"
        )

    run_1, run_2 = config.runs
    comparison = f"{run_1.name} to {run_2.name}"

    # Reuse the exact same installed capacity logic and capacity category
    # grouping from utils/capacity_mix.py.
    capacity = build_installed_capacity_mix_long(config)

    if capacity.empty:
        return pd.DataFrame(
            columns=["waterfall_column", "capacity_category", "capacity_mw"]
        )

    required_columns = {"run", "state", "year", "resource", "value"}
    missing = required_columns - set(capacity.columns)
    if missing:
        raise KeyError(
            "Capacity mix output is missing required column(s): "
            f"{sorted(missing)}"
        )

    left = capacity[capacity["run"] == run_1.name].copy()
    right = capacity[capacity["run"] == run_2.name].copy()

    left = left.rename(columns={"value": "value_run_1"})
    right = right.rename(columns={"value": "value_run_2"})

    compare = left[["state", "year", "resource", "value_run_1"]].merge(
        right[["state", "year", "resource", "value_run_2"]],
        on=["state", "year", "resource"],
        how="outer",
    )

    compare["value_run_1"] = compare["value_run_1"].fillna(0.0)
    compare["value_run_2"] = compare["value_run_2"].fillna(0.0)
    compare["change"] = compare["value_run_2"] - compare["value_run_1"]

    rows: list[dict] = []

    for (state, year), group in compare.groupby(["state", "year"], sort=True):
        year_int = int(year)

        # First base column: run_1 capacity by category.
        run_1_base = group[group["value_run_1"] != 0].copy()
        run_1_base = run_1_base.sort_values("resource")

        for _, row in run_1_base.iterrows():
            rows.append(
                {
                    "waterfall_column": f"{year_int} + {state} + {run_1.name} + base",
                    "capacity_category": row["resource"],
                    "capacity_mw": float(row["value_run_1"]),
                }
            )

        # Reductions column: categories where run_2 has less capacity than run_1.
        reductions = group[group["change"] < 0].copy()
        reductions = reductions.sort_values("change")

        for _, row in reductions.iterrows():
            rows.append(
                {
                    "waterfall_column": (
                        f"{year_int} + {state} + {comparison} + reductions"
                    ),
                    "capacity_category": row["resource"],
                    "capacity_mw": float(row["change"]),
                }
            )

        # Additions column: categories where run_2 has more capacity than run_1.
        additions = group[group["change"] > 0].copy()
        additions = additions.sort_values("change", ascending=False)

        for _, row in additions.iterrows():
            rows.append(
                {
                    "waterfall_column": (
                        f"{year_int} + {state} + {comparison} + additions"
                    ),
                    "capacity_category": row["resource"],
                    "capacity_mw": float(row["change"]),
                }
            )

        # Final base column: run_2 capacity by category.
        run_2_base = group[group["value_run_2"] != 0].copy()
        run_2_base = run_2_base.sort_values("resource")

        for _, row in run_2_base.iterrows():
            rows.append(
                {
                    "waterfall_column": f"{year_int} + {state} + {run_2.name} + base",
                    "capacity_category": row["resource"],
                    "capacity_mw": float(row["value_run_2"]),
                }
            )

    return pd.DataFrame(
        rows,
        columns=["waterfall_column", "capacity_category", "capacity_mw"],
    )


def build_capacity_changes(config: ProjectConfig) -> pd.DataFrame:
    """
    Public builder used by build_capacity_changes.py.

    Returns waterfall-ready output.
    """
    return build_capacity_changes_long(config)
