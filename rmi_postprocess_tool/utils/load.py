from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd

from utils.config import ProjectConfig, RunSpec
from utils.filters import filter_years, standardize_value_frame
from utils.geography import add_state, load_region_to_state_map
from utils.io import read_reeds_output


YEAR_COLUMN_RE = re.compile(r"^\d{4}$")


def _normalize_column_lookup(columns: list[str]) -> dict[str, str]:
    """
    Return a lower/stripped column lookup:
        normalized_name -> original_name
    """
    return {str(col).strip().lower(): col for col in columns}


def _pick_column(
    df: pd.DataFrame,
    configured_column: str | None,
    candidates: list[str],
    file_path: Path,
    purpose: str,
    required: bool = True,
) -> str | None:
    """
    Choose a column from a DataFrame.

    Priority:
    1. configured_column from config.toml, if supplied
    2. first matching candidate, case-insensitive
    """
    columns = [str(col) for col in df.columns]
    lookup = _normalize_column_lookup(columns)

    if configured_column:
        key = str(configured_column).strip().lower()
        if key in lookup:
            return lookup[key]
        if required:
            raise KeyError(
                f"Configured {purpose} column {configured_column!r} was not found "
                f"in {file_path}. Available columns: {columns}"
            )
        return None

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lookup:
            return lookup[key]

    if required:
        raise KeyError(
            f"Could not identify {purpose} column in {file_path}. "
            f"Tried candidates {candidates}. Available columns: {columns}"
        )

    return None


def _configured_years_as_set(config: ProjectConfig) -> set[int] | None:
    if isinstance(config.years, str):
        return None
    return {int(year) for year in config.years}


def _find_wide_year_columns(
    df: pd.DataFrame,
    config: ProjectConfig,
) -> list[str]:
    """
    Identify wide year columns such as 2026, 2032, 2035.

    If config.years is a specific list, keep only those years.
    If config.years == "shared", keep all 4-digit year columns.
    """
    requested_years = _configured_years_as_set(config)
    year_columns: list[str] = []

    for col in df.columns:
        col_str = str(col).strip()
        if not YEAR_COLUMN_RE.match(col_str):
            continue

        year = int(col_str)
        if requested_years is not None and year not in requested_years:
            continue

        year_columns.append(str(col))

    return year_columns


def _find_large_load_files(
    run: RunSpec,
    config: ProjectConfig,
) -> list[Path]:
    """
    Find generated large-load input_case files inside one run folder.

    Default pattern:
        inputs_case/loadsite_annual.csv

    The fallback also supports:
        inputs_case/loadsite_annual.csv.gz
        input_case/loadsite_annual.csv
        input_case/loadsite_annual.csv.gz

    The input_case spelling is included only as a defensive fallback.
    ReEDS normally uses inputs_case.
    """
    patterns = [config.large_load_file_pattern]

    fallback_patterns = [
        "inputs_case/loadsite_annual.csv",
        "inputs_case/loadsite_annual.csv.gz",
        "input_case/loadsite_annual.csv",
        "input_case/loadsite_annual.csv.gz",
    ]

    for pattern in fallback_patterns:
        if pattern not in patterns:
            patterns.append(pattern)

    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(run.path.glob(pattern)))

    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique_files: list[Path] = []
    for path in files:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        unique_files.append(path)

    return unique_files


def _read_loadsite_annual_file(
    file_path: Path,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Read one inputs_case/loadsite_annual.csv file and return normalized rows:

        state, t, value

    Supported shapes:

    1. Long:
        st,t,value
        AZ,2026,5000000

    2. Long with region instead of state:
        r,t,value
        p36,2026,5000000

       Region rows are mapped to state later.

    3. Wide:
        st,2026,2032
        AZ,5000000,8000000

    4. Wide with region instead of state:
        r,2026,2032
        p36,5000000,8000000
    """
    df = pd.read_csv(file_path)

    if df.empty:
        return pd.DataFrame(columns=["state", "r", "t", "value"])

    state_col = _pick_column(
        df=df,
        configured_column=config.large_load_state_column,
        candidates=["st", "state", "state_abbr", "state_code"],
        file_path=file_path,
        purpose="large-load state",
        required=False,
    )

    region_col = _pick_column(
        df=df,
        configured_column=config.large_load_region_column,
        candidates=[
            "*loadsitereg",
            "loadsitereg",
            "loadsite_reg",
            "loadsite_region",
            "r",
            "region",
            "reeds_region",
            "ba",
            "balancing_area",
        ],
        file_path=file_path,
        purpose="large-load region",
        required=False,
    )

    if state_col is None and region_col is None:
        raise KeyError(
            f"Could not identify either a state or region column in {file_path}. "
            f"Available columns: {list(df.columns)}"
        )

    year_col = _pick_column(
        df=df,
        configured_column=config.large_load_year_column,
        candidates=["t", "year", "model_year"],
        file_path=file_path,
        purpose="large-load year",
        required=False,
    )

    value_col = _pick_column(
        df=df,
        configured_column=config.large_load_value_column,
        candidates=[
            "value",
            "load",
            "load_mwh",
            "annual_mwh",
            "mwh",
            "mw",
            "load_mw",
            "loadsite",
            "loadsite_mw",
            "loadsite_mwh",
        ],
        file_path=file_path,
        purpose="large-load value",
        required=False,
    )

    id_columns = []
    rename: dict[str, str] = {}

    if state_col is not None:
        id_columns.append(state_col)
        rename[state_col] = "state"

    if region_col is not None:
        id_columns.append(region_col)
        rename[region_col] = "r"

    # Long format: state/region + year + value columns.
    if year_col is not None and value_col is not None:
        out = df[id_columns + [year_col, value_col]].copy()
        rename[year_col] = "t"
        rename[value_col] = "value"
        out = out.rename(columns=rename)

        for col in ["state", "r"]:
            if col not in out.columns:
                out[col] = pd.NA

        return out[["state", "r", "t", "value"]]

    # Wide format: state/region column + one column per model year.
    wide_year_columns = _find_wide_year_columns(df, config)
    if wide_year_columns:
        out = df[id_columns + wide_year_columns].copy()
        out = out.rename(columns=rename)

        id_vars = [col for col in ["state", "r"] if col in out.columns]
        out = out.melt(
            id_vars=id_vars,
            value_vars=wide_year_columns,
            var_name="t",
            value_name="value",
        )

        for col in ["state", "r"]:
            if col not in out.columns:
                out[col] = pd.NA

        return out[["state", "r", "t", "value"]]

    raise KeyError(
        f"Could not read large-load values from {file_path}. Expected either "
        "long format with state/region + year + value columns or wide format "
        f"with 4-digit year columns. Available columns: {list(df.columns)}"
    )


def _add_state_to_large_loads(
    large: pd.DataFrame,
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Ensure large-load rows have a state column.

    If inputs_case/loadsite_annual.csv already has state/st, use it.
    If it only has ReEDS/loadsite region r, map r to state using the shared
    geography logic.
    """
    large = large.copy()

    if "state" in large.columns:
        state_as_text = large["state"].astype("string").str.strip()
        has_state = state_as_text.notna().any() and state_as_text.ne("").any()
    else:
        has_state = False

    if has_state:
        large["state"] = large["state"].astype(str).str.strip().str.upper()
        if config.states:
            large = large[large["state"].isin(config.states)]
        return large

    if "r" not in large.columns:
        raise KeyError(
            "Large-load file did not include a usable state column or region column."
        )

    # Important: drop the empty placeholder state column before calling add_state().
    # add_state() expects to create the state column from r + the region mapping.
    large = large.drop(columns=["state"], errors="ignore")

    mapping = load_region_to_state_map(config, run)
    large = add_state(large, mapping, config.states)

    return large


def _read_large_loads_for_run(
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Read and aggregate large loads for one run.

    Output columns:
    - state
    - year
    - large_load
    """
    files = _find_large_load_files(run, config)

    if not files:
        warnings.warn(
            f"No generated large-load file found for run {run.name}. Tried pattern "
            f"{config.large_load_file_pattern!r} plus inputs_case/loadsite_annual.csv. "
            "Large Load will be zero.",
            stacklevel=2,
        )
        return pd.DataFrame(columns=["state", "year", "large_load"])

    frames = []
    for file_path in files:
        frame = _read_loadsite_annual_file(file_path, config)
        frame["source_file"] = str(file_path)
        frames.append(frame)

    large = pd.concat(frames, ignore_index=True)

    large["t"] = pd.to_numeric(large["t"], errors="coerce")
    large["value"] = pd.to_numeric(large["value"], errors="coerce")
    large = large.dropna(subset=["t", "value"])
    large["t"] = large["t"].astype(int)

    large = _add_state_to_large_loads(large, run, config)

    # Convert raw loadsite values into the same units as load_rt.csv.
    # Default is 1.0, assuming loadsite_annual.csv is already annual MWh.
    large["value"] = large["value"] * config.large_load_value_multiplier

    large = filter_years(large, config.years)

    # Threshold is applied at the individual row level before aggregation.
    # Set threshold to 0 in config.toml to include every loadsite row.
    large = large[large["value"] >= config.large_load_threshold_mwh]

    grouped = (
        large.groupby(["state", "t"], as_index=False)["value"]
        .sum()
        .rename(columns={"t": "year", "value": "large_load"})
    )

    return grouped[["state", "year", "large_load"]]


def _build_total_load_for_run(
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Build total annual load by state/year from outputs/load_rt.csv.

    Expected load_rt.csv columns:
    - r
    - t
    - value

    Output columns:
    - state
    - year
    - total_load
    """
    mapping = load_region_to_state_map(config, run)

    load = read_reeds_output(
        run,
        ["load_rt.csv"],
        ["r", "t", "value"],
        required=True,
    )

    if load is None:
        raise FileNotFoundError(f"load_rt.csv not found for run {run.name}")

    load = standardize_value_frame(load)
    load = filter_years(load, config.years)
    load = add_state(load, mapping, config.states)

    grouped = (
        load.groupby(["state", "t"], as_index=False)["value"]
        .sum()
        .rename(columns={"t": "year", "value": "total_load"})
    )

    return grouped[["state", "year", "total_load"]]


def build_load_for_run(
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Build long-form load rows for one run.

    Logic:
        Base Load = Total Load - Large Load

    Total Load comes from:
        outputs/load_rt.csv

    Large Load comes from:
        inputs_case/loadsite_annual.csv

    Output columns:
    - run
    - state
    - year
    - load_category
    - value
    - unit
    """
    total = _build_total_load_for_run(run, config)
    large = _read_large_loads_for_run(run, config)

    merged = total.merge(
        large,
        on=["state", "year"],
        how="left",
    )

    merged["large_load"] = merged["large_load"].fillna(0.0)

    too_large = merged["large_load"] > merged["total_load"]
    if too_large.any():
        problem_rows = merged.loc[
            too_large,
            ["state", "year", "total_load", "large_load"],
        ]

        message = (
            f"For run {run.name}, large load exceeds total load for some "
            f"state/year rows. This usually means a unit mismatch or that "
            f"load_rt.csv does not include the same load component.\n"
            f"{problem_rows.to_string(index=False)}"
        )

        if config.clip_large_load_to_total:
            warnings.warn(
                message + "\nClipping Large Load to Total Load.",
                stacklevel=2,
            )
            merged.loc[too_large, "large_load"] = merged.loc[too_large, "total_load"]
        else:
            warnings.warn(message, stacklevel=2)

    merged["base_load"] = merged["total_load"] - merged["large_load"]

    rows: list[dict] = []

    for _, row in merged.iterrows():
        rows.append(
            {
                "run": run.name,
                "state": row["state"],
                "year": int(row["year"]),
                "load_category": "Base Load",
                "value": float(row["base_load"]),
                "unit": config.load_unit,
            }
        )
        rows.append(
            {
                "run": run.name,
                "state": row["state"],
                "year": int(row["year"]),
                "load_category": "Large Load",
                "value": float(row["large_load"]),
                "unit": config.load_unit,
            }
        )

    return pd.DataFrame(
        rows,
        columns=["run", "state", "year", "load_category", "value", "unit"],
    )


def build_load_long(config: ProjectConfig) -> pd.DataFrame:
    """
    Build chart-ready annual load output for all configured runs.

    Output columns:
    - run
    - state
    - year
    - load_category
    - value
    - unit
    """
    frames = [build_load_for_run(run, config) for run in config.runs]

    if not frames:
        return pd.DataFrame(
            columns=["run", "state", "year", "load_category", "value", "unit"]
        )

    out = pd.concat(frames, ignore_index=True)

    return (
        out.sort_values(["state", "run", "year", "load_category"])
        .reset_index(drop=True)
    )


def build_load(config: ProjectConfig) -> pd.DataFrame:
    """
    Public builder used by build_load.py.

    Returns long/tidy output by default.
    """
    return build_load_long(config)
