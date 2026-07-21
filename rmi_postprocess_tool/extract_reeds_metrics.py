from __future__ import annotations

import argparse
import math
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal

import pandas as pd


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

DEFAULT_CONFIG_FILE = "config.toml"
DEFAULT_OUTPUT_CSV = "primary_metrics_comparison.csv"
QUADS_TO_MMBTU = 1_000_000_000.0

VALID_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "IA", "ID",
    "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT",
    "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY", "DC",
}

# These strings are excluded when approximating CAPEX + OPEX from systemcost_ba.
# Adjust if your ReEDS run uses different sys_costs labels.
COST_COMPONENT_EXCLUDE_HINTS = {
    "ptc",
    "itc",
    "tax_credit",
    "taxcredit",
    "co2_incentive",
    "h2_ptc",
    "transfer",
}

MetricName = Literal[
    "system_cost",
    "average_electricity_cost",
    "co2_emissions",
    "generation_mix",
    "capacity_additions",
    "reserve_margin",
    "transmission_utilization",
    "curtailment",
    "fuel_consumption",
]


# -----------------------------------------------------------------------------
# Dataclasses
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class RunSpec:
    name: str
    path: Path


@dataclass(frozen=True)
class Config:
    runs: list[RunSpec]
    output_csv: Path
    years: list[int] | str
    states: list[str]
    dollar_year: int
    dollar_conversion_factor: float
    metric_include: list[str]
    region_to_state_file: Path | None


@dataclass(frozen=True)
class MetricRow:
    metric: str
    state: str
    year: int
    detail: str
    unit: str
    value: float


# -----------------------------------------------------------------------------
# Config parsing
# -----------------------------------------------------------------------------

def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract and compare primary metrics from two existing ReEDS runs."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(DEFAULT_CONFIG_FILE),
        help=f"Path to TOML config file. Defaults to {DEFAULT_CONFIG_FILE} in the current working directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Optional output CSV path. Defaults to [general].output_csv or {DEFAULT_OUTPUT_CSV}.",
    )
    return parser.parse_args(list(argv))


def load_toml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Create {DEFAULT_CONFIG_FILE} in the current "
            "directory or pass --config path/to/config.toml."
        )
    with path.open("rb") as f:
        return tomllib.load(f)


def resolve_path(path_raw: str | Path, base: Path) -> Path:
    path = Path(path_raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_config(config_path: Path, output_override: Path | None = None) -> Config:
    raw = load_toml(config_path)
    config_dir = config_path.parent.resolve()
    general = raw.get("general", {})

    runs_root = resolve_path(general.get("runs_root", "."), config_dir)

    runs: list[RunSpec] = []
    for item in raw.get("runs", []):
        name = str(item["name"])
        run_path = Path(str(item["path"])).expanduser()
        if not run_path.is_absolute():
            run_path = runs_root / run_path
        runs.append(RunSpec(name=name, path=run_path.resolve()))

    if len(runs) != 2:
        raise ValueError(f"This version expects exactly two [[runs]], found {len(runs)}")

    output_raw = output_override or Path(general.get("output_csv", DEFAULT_OUTPUT_CSV))
    output_csv = output_raw if output_raw.is_absolute() else (config_dir / output_raw)

    years_raw = general.get("years", "shared")
    if isinstance(years_raw, str):
        years: list[int] | str = years_raw.lower()
        if years != "shared":
            raise ValueError("[general].years must be 'shared' or an array of years")
    else:
        years = sorted({int(y) for y in years_raw})

    states = [str(s).upper() for s in general.get("states", [])]
    if not states:
        raise ValueError("[general].states must contain at least one state abbreviation, e.g. ['NM']")
    unknown_states = sorted(set(states) - VALID_STATES)
    if unknown_states:
        raise ValueError(f"Unknown state abbreviation(s): {unknown_states}")

    region_map_raw = general.get("region_to_state_file")
    region_to_state_file = None
    if region_map_raw:
        region_to_state_file = resolve_path(region_map_raw, config_dir)

    metric_config = raw.get("metrics", {})
    include = [str(x) for x in metric_config.get("include", ["all"])]

    return Config(
        runs=runs,
        output_csv=output_csv.resolve(),
        years=years,
        states=states,
        dollar_year=int(general.get("dollar_year", 2026)),
        dollar_conversion_factor=float(general.get("dollar_conversion_factor", 1.0)),
        metric_include=include,
        region_to_state_file=region_to_state_file,
    )


# -----------------------------------------------------------------------------
# File reading helpers
# -----------------------------------------------------------------------------

def first_existing(run: RunSpec, candidates: list[str]) -> Path | None:
    for rel in candidates:
        path = run.path / "outputs" / rel
        if path.exists():
            return path
    return None


def read_reeds_output(
    run: RunSpec,
    candidates: list[str],
    default_columns: list[str],
    required: bool = False,
) -> pd.DataFrame | None:
    path = first_existing(run, candidates)
    if path is None:
        if required:
            raise FileNotFoundError(
                f"None of these files were found under {run.path / 'outputs'}: {candidates}"
            )
        return None

    # Try headered first. If required columns are missing, fall back to headerless.
    df_headered = pd.read_csv(path, comment="#")
    normalized_cols = [str(c).strip() for c in df_headered.columns]
    df_headered.columns = normalized_cols

    if set(default_columns).issubset(set(normalized_cols)):
        return df_headered

    # Some ReEDS/GAMS outputs are headerless. Re-read with supplied column order.
    df = pd.read_csv(path, header=None, names=default_columns, comment="#")
    return df


def ensure_numeric(df: pd.DataFrame, column: str = "value") -> pd.DataFrame:
    out = df.copy()
    out[column] = pd.to_numeric(out[column], errors="coerce")
    return out.dropna(subset=[column])


def ensure_year(df: pd.DataFrame, column: str = "t") -> pd.DataFrame:
    out = df.copy()
    out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=[column])
    out[column] = out[column].astype(int)
    return out


def clean_string_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    out[column] = out[column].astype(str).str.strip()
    return out


def standardize_value_frame(df: pd.DataFrame, value_column: str = "value") -> pd.DataFrame:
    out = df.copy()
    out = ensure_year(out, "t") if "t" in out.columns else out
    out = ensure_numeric(out, value_column)
    return out


# -----------------------------------------------------------------------------
# Region-to-state mapping
# -----------------------------------------------------------------------------

def infer_state_from_region(region: str) -> str | None:
    """Fallback parser for region names that contain a two-letter state token."""
    r = str(region).upper()

    # Common easy case: exactly NM, TX, CA, etc.
    if r in VALID_STATES:
        return r

    # Look for state abbreviation as a separated token.
    tokens = re.split(r"[^A-Z]+", r)
    for token in tokens:
        if token in VALID_STATES:
            return token

    # Look for abbreviation embedded at the end, e.g. p123NM or BA_NM.
    for state in VALID_STATES:
        if r.endswith(state):
            return state

    return None


def read_region_to_state_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Region-to-state mapping file not found: {path}")
    df = pd.read_csv(path, comment="#")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def region_state_columns(df: pd.DataFrame) -> tuple[str, str] | None:
    lower = {c.lower(): c for c in df.columns}

    r_candidates = ["r", "region", "reeds_region", "ba", "*r"]
    state_candidates = ["state", "st", "state_abbr", "state_code", "*st"]

    r_col = next((lower[c] for c in r_candidates if c in lower), None)
    state_col = next((lower[c] for c in state_candidates if c in lower), None)

    if r_col and state_col:
        return r_col, state_col
    return None


def load_region_to_state_map(config: Config, run: RunSpec) -> pd.DataFrame:
    """Return columns r,state. Uses explicit map, hierarchy files, or inference fallback."""
    candidate_files: list[Path] = []
    if config.region_to_state_file:
        candidate_files.append(config.region_to_state_file)

    candidate_files.extend(
        [
            run.path / "inputs_case" / "hierarchy.csv",
            run.path / "inputs_case" / "hierarchy.csv.gz",
            run.path / "inputs" / "hierarchy.csv",
            run.path / "inputs" / "hierarchy.csv.gz",
            run.path / "inputs_case" / "region_to_state.csv",
            run.path / "inputs" / "region_to_state.csv",
        ]
    )

    for path in candidate_files:
        if not path.exists():
            continue
        df = read_region_to_state_file(path)
        cols = region_state_columns(df)
        if cols:
            r_col, state_col = cols
            out = df[[r_col, state_col]].copy()
            out.columns = ["r", "state"]
            out["r"] = out["r"].astype(str).str.strip()
            out["state"] = out["state"].astype(str).str.upper().str.strip()
            out = out[out["state"].isin(VALID_STATES)]
            if not out.empty:
                return out.drop_duplicates()

    # Fallback: infer from regions present in common outputs.
    regions: set[str] = set()
    for candidates, cols in [
        (["gen_ann.csv"], ["i", "r", "t", "value"]),
        (["load_rt.csv"], ["r", "t", "value"]),
        (["prm.csv"], ["r", "t", "value"]),
        (["curt_ann.csv"], ["r", "t", "value"]),
    ]:
        df = read_reeds_output(run, candidates, cols, required=False)
        if df is not None and "r" in df.columns:
            regions.update(df["r"].astype(str).str.strip().unique())

    rows = []
    for r in regions:
        state = infer_state_from_region(r)
        if state:
            rows.append({"r": r, "state": state})

    if rows:
        return pd.DataFrame(rows).drop_duplicates()

    raise FileNotFoundError(
        "Could not find or infer a ReEDS region-to-state mapping. Add "
        "[general].region_to_state_file to config.toml. Expected columns include r/state or r/st."
    )


def add_state(df: pd.DataFrame, mapping: pd.DataFrame, state_filter: list[str]) -> pd.DataFrame:
    if "r" not in df.columns:
        raise KeyError("Expected column 'r' for state mapping")
    out = df.copy()
    out["r"] = out["r"].astype(str).str.strip()
    merged = out.merge(mapping, on="r", how="left")
    missing = merged[merged["state"].isna()]["r"].drop_duplicates().head(20).tolist()
    if missing:
        print(
            f"Warning: {len(missing)} region(s) could not be mapped to states; examples: {missing}",
            file=sys.stderr,
        )
    merged = merged[merged["state"].isin(state_filter)]
    return merged


def add_route_states(df: pd.DataFrame, mapping: pd.DataFrame, state_filter: list[str]) -> pd.DataFrame:
    """Assign transmission route rows to selected states touched by either endpoint."""
    required = {"r", "rr"}
    if not required.issubset(df.columns):
        raise KeyError("Transmission utilization requires columns 'r' and 'rr'")

    left = mapping.rename(columns={"r": "r", "state": "state_r"})
    right = mapping.rename(columns={"r": "rr", "state": "state_rr"})
    out = df.copy()
    out["r"] = out["r"].astype(str).str.strip()
    out["rr"] = out["rr"].astype(str).str.strip()
    out = out.merge(left, on="r", how="left").merge(right, on="rr", how="left")

    rows = []
    for _, row in out.iterrows():
        states = {row.get("state_r"), row.get("state_rr")}
        states = {str(s) for s in states if pd.notna(s) and str(s) in state_filter}
        for state in states:
            new_row = row.copy()
            new_row["state"] = state
            rows.append(new_row)
    if not rows:
        return pd.DataFrame(columns=list(out.columns) + ["state"])
    return pd.DataFrame(rows)


def filter_years(df: pd.DataFrame, years: list[int] | str) -> pd.DataFrame:
    if "t" not in df.columns:
        return df
    out = df.copy()
    out = ensure_year(out, "t")
    if isinstance(years, list):
        out = out[out["t"].isin(years)]
    return out


# -----------------------------------------------------------------------------
# Metric row formatting
# -----------------------------------------------------------------------------

def rows_from_grouped(
    grouped: pd.DataFrame,
    metric: str,
    unit: str,
    value_column: str = "value",
    detail_column: str | None = None,
) -> list[MetricRow]:
    rows: list[MetricRow] = []
    for _, row in grouped.iterrows():
        detail = str(row[detail_column]) if detail_column else "total"
        rows.append(
            MetricRow(
                metric=metric,
                state=str(row["state"]),
                year=int(row["t"]),
                detail=detail,
                unit=unit,
                value=float(row[value_column]),
            )
        )
    return rows


def metric_rows_to_frame(rows: list[MetricRow], run_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "metric": r.metric,
                "state": r.state,
                "year": r.year,
                "detail": r.detail,
                "unit": r.unit,
                run_name: r.value,
            }
            for r in rows
        ]
    )


# -----------------------------------------------------------------------------
# Metric calculations
# -----------------------------------------------------------------------------

def metric_system_cost(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    """CAPEX + OPEX approximation from BA-level system cost components."""
    df = read_reeds_output(
        run,
        ["systemcost_ba.csv"],
        ["sys_costs", "r", "t", "value"],
        required=False,
    )
    if df is None:
        # Fallback: no state detail. Use national raw investment and operating costs if present.
        inv = read_reeds_output(run, ["raw_inv_cost.csv"], ["t", "value"], required=False)
        op = read_reeds_output(run, ["raw_op_cost.csv"], ["t", "value"], required=False)
        if inv is None or op is None:
            return []
        inv = standardize_value_frame(inv)
        op = standardize_value_frame(op)
        total = pd.concat([inv, op], ignore_index=True)
        total = filter_years(total, config.years)
        grouped = total.groupby("t", as_index=False)["value"].sum()
        grouped["value"] *= config.dollar_conversion_factor
        rows = []
        for _, row in grouped.iterrows():
            for state in config.states:
                rows.append(
                    MetricRow("system_cost_capex_opex", state, int(row["t"]), "national_fallback", f"{config.dollar_year}$", float(row["value"]))
                )
        return rows

    df = standardize_value_frame(df)
    df = clean_string_column(df, "sys_costs")
    df = filter_years(df, config.years)

    # Keep cost components unless they look like tax credits/transfers.
    lower = df["sys_costs"].str.lower()
    exclude = pd.Series(False, index=df.index)
    for hint in COST_COMPONENT_EXCLUDE_HINTS:
        exclude = exclude | lower.str.contains(hint, regex=False, na=False)
    df = df[~exclude]

    df = add_state(df, mapping, config.states)
    grouped = df.groupby(["state", "t"], as_index=False)["value"].sum()
    grouped["value"] *= config.dollar_conversion_factor
    return rows_from_grouped(grouped, "system_cost_capex_opex", f"{config.dollar_year}$")


def metric_average_electricity_cost(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    """Average cost = state CAPEX+OPEX system cost / state annual load."""
    cost_rows = metric_system_cost(run, config, mapping)
    if not cost_rows:
        return []
    cost = pd.DataFrame([r.__dict__ for r in cost_rows])
    cost = cost.rename(columns={"value": "cost"})

    load = read_reeds_output(run, ["load_rt.csv"], ["r", "t", "value"], required=False)
    if load is None:
        return []
    load = standardize_value_frame(load)
    load = filter_years(load, config.years)
    load = add_state(load, mapping, config.states)
    load_grouped = load.groupby(["state", "t"], as_index=False)["value"].sum()
    load_grouped = load_grouped.rename(columns={"t": "year", "value": "load_mwh"})

    merged = cost.merge(load_grouped, on=["state", "year"], how="inner")
    merged = merged[merged["load_mwh"] != 0]
    merged["value"] = merged["cost"] / merged["load_mwh"]
    merged["t"] = merged["year"]
    return rows_from_grouped(merged, "average_electricity_cost", f"{config.dollar_year}$/MWh")


def metric_co2_emissions(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    df = read_reeds_output(run, ["emit_r.csv"], ["etype", "eall", "r", "t", "value"], required=False)
    if df is None:
        return []
    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "etype")
    df = df[df["etype"].str.upper().isin({"CO2", "CO2E"})]
    df = add_state(df, mapping, config.states)
    grouped = df.groupby(["state", "t", "etype"], as_index=False)["value"].sum()
    grouped["detail"] = grouped["etype"]
    return rows_from_grouped(grouped, "emissions", "metric tons", detail_column="detail")


def metric_generation_mix(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    df = read_reeds_output(run, ["gen_ann.csv"], ["i", "r", "t", "value"], required=False)
    if df is None:
        return []
    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "i")
    df = add_state(df, mapping, config.states)

    tech = df.groupby(["state", "t", "i"], as_index=False)["value"].sum()
    total = tech.groupby(["state", "t"], as_index=False)["value"].sum().rename(columns={"value": "total_gen"})
    merged = tech.merge(total, on=["state", "t"], how="inner")
    merged = merged[merged["total_gen"] != 0]
    merged["value"] = merged["value"] / merged["total_gen"] * 100.0
    merged["detail"] = merged["i"]
    return rows_from_grouped(merged, "generation_mix", "%", detail_column="detail")


def metric_capacity_additions(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    df = read_reeds_output(run, ["cap_new_ann.csv"], ["i", "r", "t", "value"], required=False)
    if df is None:
        return []
    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "i")
    df = add_state(df, mapping, config.states)
    grouped = df.groupby(["state", "t", "i"], as_index=False)["value"].sum()
    grouped["detail"] = grouped["i"]
    return rows_from_grouped(grouped, "capacity_additions", "MW", detail_column="detail")


def metric_reserve_margin(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    df = read_reeds_output(run, ["prm.csv"], ["r", "t", "value"], required=False)
    if df is None:
        return []
    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = add_state(df, mapping, config.states)
    grouped = df.groupby(["state", "t"], as_index=False)["value"].mean()
    grouped["value"] *= 100.0
    return rows_from_grouped(grouped, "reserve_margin", "%")


def _transmission_utilization(
    run: RunSpec,
    config: Config,
    mapping: pd.DataFrame,
    file_name: str,
    detail: str,
) -> list[MetricRow]:
    df = read_reeds_output(
        run,
        [file_name],
        ["r", "rr", "trtype", "t", "value"],
        required=False,
    )
    if df is None:
        return []
    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = add_route_states(df, mapping, config.states)
    if df.empty:
        return []
    grouped = df.groupby(["state", "t"], as_index=False)["value"].mean()
    grouped["value"] *= 100.0
    grouped["detail"] = detail
    return rows_from_grouped(grouped, "transmission_utilization", "%", detail_column="detail")


def metric_transmission_utilization(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    rows = []
    rows.extend(_transmission_utilization(run, config, mapping, "tran_util_ann_rep.csv", "representative"))
    rows.extend(_transmission_utilization(run, config, mapping, "tran_util_ann_stress.csv", "stress"))
    return rows


def metric_curtailment(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    rows: list[MetricRow] = []

    annual = read_reeds_output(run, ["curt_ann.csv"], ["r", "t", "value"], required=False)
    if annual is not None:
        annual = standardize_value_frame(annual)
        annual = filter_years(annual, config.years)
        annual = add_state(annual, mapping, config.states)
        grouped = annual.groupby(["state", "t"], as_index=False)["value"].sum()
        rows.extend(rows_from_grouped(grouped, "curtailment", "MWh"))

    tech = read_reeds_output(run, ["curt_tech.csv"], ["i", "r", "t", "value"], required=False)
    if tech is not None:
        tech = standardize_value_frame(tech)
        tech = filter_years(tech, config.years)
        tech = clean_string_column(tech, "i")
        tech = add_state(tech, mapping, config.states)
        grouped = tech.groupby(["state", "t", "i"], as_index=False)["value"].sum()
        grouped["detail"] = grouped["i"]
        rows.extend(rows_from_grouped(grouped, "curtailment_by_technology", "MWh", detail_column="detail"))

    return rows


def metric_fuel_consumption(run: RunSpec, config: Config, mapping: pd.DataFrame) -> list[MetricRow]:
    df = read_reeds_output(run, ["repgasquant_irt.csv"], ["i", "r", "t", "value"], required=False)
    if df is None:
        nat = read_reeds_output(run, ["repgasquant_nat.csv"], ["t", "value"], required=False)
        if nat is None:
            return []
        nat = standardize_value_frame(nat)
        nat = filter_years(nat, config.years)
        grouped = nat.groupby("t", as_index=False)["value"].sum()
        grouped["value"] *= QUADS_TO_MMBTU
        rows = []
        for _, row in grouped.iterrows():
            for state in config.states:
                rows.append(
                    MetricRow("fuel_consumption_natural_gas", state, int(row["t"]), "national_fallback", "MMBtu", float(row["value"]))
                )
        return rows

    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "i")
    df = add_state(df, mapping, config.states)
    grouped = df.groupby(["state", "t", "i"], as_index=False)["value"].sum()
    grouped["value"] *= QUADS_TO_MMBTU
    grouped["detail"] = grouped["i"]
    return rows_from_grouped(grouped, "fuel_consumption_natural_gas", "MMBtu", detail_column="detail")


METRIC_REGISTRY: dict[str, Callable[[RunSpec, Config, pd.DataFrame], list[MetricRow]]] = {
    "system_cost": metric_system_cost,
    "average_electricity_cost": metric_average_electricity_cost,
    "co2_emissions": metric_co2_emissions,
    "generation_mix": metric_generation_mix,
    "capacity_additions": metric_capacity_additions,
    "reserve_margin": metric_reserve_margin,
    "transmission_utilization": metric_transmission_utilization,
    "curtailment": metric_curtailment,
    "fuel_consumption": metric_fuel_consumption,
}


# -----------------------------------------------------------------------------
# Comparison logic
# -----------------------------------------------------------------------------

def selected_metrics(config: Config) -> list[str]:
    include = [x.lower() for x in config.metric_include]
    if include == ["all"] or "all" in include:
        return list(METRIC_REGISTRY.keys())
    unknown = sorted(set(include) - set(METRIC_REGISTRY.keys()))
    if unknown:
        raise ValueError(f"Unknown metric group(s): {unknown}. Valid options: {sorted(METRIC_REGISTRY)}")
    return include


def extract_run_metrics(run: RunSpec, config: Config) -> pd.DataFrame:
    mapping = load_region_to_state_map(config, run)
    rows: list[MetricRow] = []
    for metric_name in selected_metrics(config):
        try:
            metric_rows = METRIC_REGISTRY[metric_name](run, config, mapping)
        except FileNotFoundError as exc:
            print(f"Warning: skipping {metric_name} for {run.name}: {exc}", file=sys.stderr)
            metric_rows = []
        except KeyError as exc:
            print(f"Warning: skipping {metric_name} for {run.name}: {exc}", file=sys.stderr)
            metric_rows = []
        rows.extend(metric_rows)

    if not rows:
        return pd.DataFrame(columns=["metric", "state", "year", "detail", "unit", run.name])
    return metric_rows_to_frame(rows, run.name)


def pct_diff(second: float, first: float) -> float:
    if pd.isna(first) or pd.isna(second):
        return math.nan
    if first == 0:
        if second == 0:
            return 0.0
        return math.inf if second > 0 else -math.inf
    return (second - first) / abs(first) * 100.0


def build_comparison(config: Config) -> pd.DataFrame:
    run_frames = [extract_run_metrics(run, config) for run in config.runs]

    keys = ["metric", "state", "year", "detail", "unit"]
    merged = run_frames[0].merge(run_frames[1], on=keys, how="inner")

    # If years='shared', using an inner join already keeps only shared years/details.
    # If explicit years were supplied, the extractors filtered before this point.
    first_col = config.runs[0].name
    second_col = config.runs[1].name
    merged["diff_pct"] = [pct_diff(second, first) for first, second in zip(merged[first_col], merged[second_col])]

    merged = merged.sort_values(["metric", "state", "year", "detail"]).reset_index(drop=True)
    return merged[keys + [first_col, second_col, "diff_pct"]]


def write_output(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------

def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    config_path = args.config.resolve()
    config = load_config(config_path, output_override=args.output)

    comparison = build_comparison(config)
    write_output(comparison, config.output_csv)
    print(f"Wrote {len(comparison):,} comparison rows to {config.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
