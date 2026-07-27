from __future__ import annotations

import re

import pandas as pd

from utils.config import ProjectConfig, RunSpec
from utils.filters import clean_string_column, filter_years, standardize_value_frame
from utils.geography import add_state, load_region_to_state_map
from utils.io import read_reeds_output


def normalize_cost_category(category: str) -> str:
    """
    Normalize detailed ReEDS system cost category strings for matching.
    """
    out = str(category).strip().lower()
    out = out.replace("_", "-")
    out = out.replace(" ", "-")
    out = re.sub(r"-+", "-", out).strip("-")
    return out


def group_system_cost_category(category: str) -> str:
    """
    Map detailed ReEDS systemcost labels into broader chart categories.

    This is intentionally conservative. Unmatched labels are preserved so that
    new/unexpected ReEDS categories remain visible in the output CSV.
    """
    raw = str(category).strip()
    c = normalize_cost_category(raw)

    # Capital / investment / depreciation-like categories.
    if (
        "depreciation" in c
        or "depr" in c
        or "capital" in c
        or "capex" in c
        or "investment" in c
        or c.startswith("inv")
        or "-inv" in c
    ):
        return "Capital / Depreciation"

    # Fixed O&M.
    if (
        "fixed-om" in c
        or "fixed-o-m" in c
        or "fom" in c
        or "fixom" in c
        or "fixed" in c and ("om" in c or "o-m" in c)
    ):
        return "Fixed O&M"

    # Variable O&M.
    if (
        "variable-om" in c
        or "variable-o-m" in c
        or "vom" in c
        or "varom" in c
        or "variable" in c and ("om" in c or "o-m" in c)
    ):
        return "Variable O&M"

    # Fuel.
    if (
        "fuel" in c
        or "gas" in c and "cost" in c
        or "coal" in c and "cost" in c
    ):
        return "Fuel"

    # Transmission.
    if (
        "trans" in c
        or "spur" in c
        or "intertie" in c
    ):
        return "Transmission"

    # Storage-related costs, if reported separately.
    if (
        "storage" in c
        or "battery" in c
    ):
        return "Storage"

    # Operating reserve / reliability / capacity adequacy style costs.
    if (
        "reserve" in c
        or "oper-res" in c
        or "planning-reserve" in c
        or "capacity-credit" in c
        or "reliability" in c
        or "neue" in c
    ):
        return "Reliability / Reserves"

    # Emissions / policy / compliance costs.
    if (
        "co2" in c
        or "carbon" in c
        or "emission" in c
        or "rps" in c
        or "ces" in c
        or "policy" in c
        or "standard" in c
    ):
        return "Policy / Emissions"

    # Tax credits and incentives. Keep separate because these may be negative.
    if (
        "ptc" in c
        or "itc" in c
        or "tax-credit" in c
        or "taxcredit" in c
        or "incentive" in c
    ):
        return "Tax Credits / Incentives"

    # H2 / DAC / production activity costs, if present.
    if (
        c.startswith("h2")
        or "hydrogen" in c
        or "dac" in c
        or "electrolyzer" in c
    ):
        return "Hydrogen / Production"

    # Existing/fallback O&M labels sometimes use broader op-cost naming.
    if (
        "operating" in c
        or "operation" in c
        or c.startswith("op")
        or "-op" in c
    ):
        return "Other Operating"

    return raw


def build_cost_comparison_for_run(
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Build a long-form state/year/category cost table for one run.

    Primary source:
    - outputs/systemcost_ba.csv

    Expected columns:
    - sys_costs
    - r
    - t
    - value

    Output columns:
    - run
    - state
    - year
    - cost_category
    - value
    - unit
    """
    mapping = load_region_to_state_map(config, run)

    costs = read_reeds_output(
        run,
        ["systemcost_ba.csv"],
        ["sys_costs", "r", "t", "value"],
        required=True,
    )

    if costs is None:
        raise FileNotFoundError(f"systemcost_ba.csv not found for run {run.name}")

    costs = standardize_value_frame(costs)
    costs = filter_years(costs, config.years)
    costs = clean_string_column(costs, "sys_costs")
    costs = add_state(costs, mapping, config.states)

    if config.group_cost_categories:
        costs["cost_category"] = costs["sys_costs"].apply(group_system_cost_category)
    else:
        costs["cost_category"] = costs["sys_costs"]

    grouped = (
        costs.groupby(["state", "t", "cost_category"], as_index=False)["value"]
        .sum()
        .rename(columns={"t": "year"})
    )

    grouped["value"] = grouped["value"] * config.dollar_conversion_factor
    grouped["run"] = run.name
    grouped["unit"] = config.cost_comparison_unit

    return grouped[["run", "state", "year", "cost_category", "value", "unit"]]


def build_cost_comparison_long(config: ProjectConfig) -> pd.DataFrame:
    frames = [
        build_cost_comparison_for_run(run, config)
        for run in config.runs
    ]

    if not frames:
        return pd.DataFrame(
            columns=["run", "state", "year", "cost_category", "value", "unit"]
        )

    out = pd.concat(frames, ignore_index=True)
    return (
        out.sort_values(["state", "year", "run", "cost_category"])
        .reset_index(drop=True)
    )


def build_cost_comparison_wide(config: ProjectConfig) -> pd.DataFrame:
    """
    Build a chart-ready wide table.

    Columns look like:

        cost_category,unit,Run1 + NM + 2026,Run2 + NM + 2026,Run1 + NM + 2032,Run2 + NM + 2032
    """
    long_df = build_cost_comparison_long(config)

    if long_df.empty:
        return pd.DataFrame(columns=["cost_category", "unit"])

    long_df = long_df.copy()
    long_df["chart_column"] = (
        long_df["run"].astype(str)
        + " + "
        + long_df["state"].astype(str)
        + " + "
        + long_df["year"].astype(str)
    )

    wide = (
        long_df.pivot_table(
            index=["cost_category", "unit"],
            columns="chart_column",
            values="value",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )

    wide.columns = [str(col) for col in wide.columns]

    desired_value_columns = []
    years = sorted(long_df["year"].dropna().unique())
    states = config.states
    runs = [run.name for run in config.runs]

    for year in years:
        for state in states:
            for run_name in runs:
                col = f"{run_name} + {state} + {year}"
                if col in wide.columns:
                    desired_value_columns.append(col)

    ordered_columns = ["cost_category", "unit"] + desired_value_columns
    remaining_columns = [
        col for col in wide.columns
        if col not in ordered_columns
    ]

    return wide[ordered_columns + remaining_columns]


def build_cost_comparison(config: ProjectConfig) -> pd.DataFrame:
    """
    Public builder used by build_cost_comparison.py.

    Returns wide/chart-ready output by default.
    """
    return build_cost_comparison_wide(config)
