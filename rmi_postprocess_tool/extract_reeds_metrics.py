from __future__ import annotations

import argparse
import csv
import math
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


# Defines class for reeds run
@dataclass(frozen=True)
class RunSpec:
    name: str
    path: Path


# Defines class for metric extractin from reeds output csvs
@dataclass(frozen=True)
class MetricSpec:
    name: str
    file: str
    value_column: str
    columns: list[str] | None
    filters: dict[str, Any]
    group_by: list[str]
    aggregation: str
    scale: float
    output_unit: str | None
    missing_ok: bool


SUPPORTED_AGGREGATIONS = {"sum", "mean", "min", "max", "first"}


# Load config.toml
def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


# Reads the [[runs]] and converts them to RunSpec objects
def resolve_run_specs(config: dict[str, Any], config_dir: Path) -> list[RunSpec]:
    general = config.get("general", {})
    runs_root_raw = general.get("runs_root", ".")
    runs_root = Path(runs_root_raw)
    if not runs_root.is_absolute():
        runs_root = (config_dir / runs_root).resolve()

    runs = []
    for item in config.get("runs", []):
        name = str(item["name"])
        run_path = Path(str(item["path"]))
        if not run_path.is_absolute():
            run_path = runs_root / run_path
        runs.append(RunSpec(name=name, path=run_path.resolve()))

    if len(runs) != 2:
        raise ValueError(
            f"Basic version expects exactly two [[runs]], found {len(runs)}"
        )
    return runs


# Reads the [[metrics]] and converts them to MetricSpec
def resolve_metric_specs(config: dict[str, Any]) -> list[MetricSpec]:
    metrics = []
    for item in config.get("metrics", []):
        aggregation = str(item.get("aggregation", "sum")).lower()
        if aggregation not in SUPPORTED_AGGREGATIONS:
            raise ValueError(
                f"Metric {item.get('name')} uses unsupported aggregation {aggregation!r}. "
                f"Supported: {sorted(SUPPORTED_AGGREGATIONS)}"
            )

        columns = item.get("columns")
        metrics.append(
            MetricSpec(
                name=str(item["name"]),
                file=str(item["file"]),
                value_column=str(item.get("value_column", "value")),
                columns=[str(c) for c in columns] if columns else None,
                filters=dict(item.get("filters", {})),
                group_by=[str(c) for c in item.get("group_by", [])],
                aggregation=aggregation,
                scale=float(item.get("scale", 1.0)),
                output_unit=item.get("output_unit"),
                missing_ok=bool(item.get("missing_ok", False)),
            )
        )

    if not metrics:
        raise ValueError("Config must contain at least one [[metrics]] block")
    return metrics


# Reads outputs from reeds output csvs. Allows for either Headered or Headerless csvs
def read_reeds_csv(path: Path, columns: list[str] | None) -> pd.DataFrame:
    """Read either headered or headerless ReEDS CSV output."""
    if not path.exists():
        raise FileNotFoundError(path)

    if columns:
        # Headerless GAMS-style CSV. The config supplies the full column order.
        return pd.read_csv(path, header=None, names=columns, comment="#")

    # Headered CSV. This is common for postprocessed outputs.
    return pd.read_csv(path, comment="#")


# Allows config to use either one allowed value or many
def normalize_filter_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


# Trims csv to only relevant rows
def apply_filters(
    df: pd.DataFrame, filters: dict[str, Any], metric_name: str
) -> pd.DataFrame:
    out = df.copy()
    for col, raw_allowed in filters.items():
        if col not in out.columns:
            raise KeyError(
                f"Metric {metric_name}: filter column {col!r} not found in CSV columns {list(out.columns)}"
            )
        allowed = normalize_filter_values(raw_allowed)
        # Compare as strings unless exact numeric matching is possible. This avoids
        # superficial int/string mismatches for model years like 2032.
        allowed_str = {str(x) for x in allowed}
        out = out[out[col].astype(str).isin(allowed_str)]
    return out


# Defines how to aggregate each metric and name each row
def aggregate_metric(df: pd.DataFrame, spec: MetricSpec) -> pd.Series:
    if spec.value_column not in df.columns:
        raise KeyError(
            f"Metric {spec.name}: value_column {spec.value_column!r} not found in CSV columns {list(df.columns)}"
        )

    for col in spec.group_by:
        if col not in df.columns:
            raise KeyError(
                f"Metric {spec.name}: group_by column {col!r} not found in CSV columns {list(df.columns)}"
            )

    work = df.copy()
    work[spec.value_column] = (
        pd.to_numeric(work[spec.value_column], errors="coerce") * spec.scale
    )
    work = work.dropna(subset=[spec.value_column])

    if spec.group_by:
        grouped = work.groupby(spec.group_by, dropna=False)[spec.value_column]
        if spec.aggregation == "sum":
            result = grouped.sum()
        elif spec.aggregation == "mean":
            result = grouped.mean()
        elif spec.aggregation == "min":
            result = grouped.min()
        elif spec.aggregation == "max":
            result = grouped.max()
        elif spec.aggregation == "first":
            result = grouped.first()
        else:  # guarded earlier
            raise AssertionError(spec.aggregation)

        if isinstance(result.index, pd.MultiIndex):
            result.index = [
                "|".join(f"{k}={v}" for k, v in zip(spec.group_by, idx))
                for idx in result.index
            ]
        else:
            gb = spec.group_by[0]
            result.index = [f"{gb}={idx}" for idx in result.index]
        return result.sort_index()

    values = work[spec.value_column]
    if spec.aggregation == "sum":
        value = values.sum()
    elif spec.aggregation == "mean":
        value = values.mean()
    elif spec.aggregation == "min":
        value = values.min()
    elif spec.aggregation == "max":
        value = values.max()
    elif spec.aggregation == "first":
        value = values.iloc[0] if len(values) else math.nan
    else:  # guarded earlier
        raise AssertionError(spec.aggregation)
    return pd.Series({"total": value})


# Runs the aggregation and metric creation from above and creates each row
def extract_one_metric(run: RunSpec, spec: MetricSpec) -> pd.Series:
    csv_path = run.path / "outputs" / spec.file
    try:
        df = read_reeds_csv(csv_path, spec.columns)
    except FileNotFoundError:
        if spec.missing_ok:
            return pd.Series(dtype="float64")
        raise

    df = apply_filters(df, spec.filters, spec.name)
    return aggregate_metric(df, spec)


# Creates row labels
def metric_key(spec: MetricSpec, subkey: str) -> str:
    unit_suffix = f" [{spec.output_unit}]" if spec.output_unit else ""
    return f"{spec.name}|{subkey}{unit_suffix}"


# Does pct diff calculation on each column
def pct_diff(new: float, old: float) -> float:
    if pd.isna(new) or pd.isna(old):
        return math.nan
    if old == 0:
        if new == 0:
            return 0.0
        return math.inf if new > 0 else -math.inf
    return (new - old) / abs(old) * 100.0


# Loops through the configured metrics and creates the comparison rows
def build_comparison(runs: list[RunSpec], metrics: list[MetricSpec]) -> pd.DataFrame:
    rows: dict[str, dict[str, float]] = {}

    for spec in metrics:
        extracted = [extract_one_metric(run, spec) for run in runs]
        common_keys = sorted(
            set(extracted[0].index).intersection(set(extracted[1].index))
        )
        for subkey in common_keys:
            key = metric_key(spec, str(subkey))
            v0 = float(extracted[0].loc[subkey])
            v1 = float(extracted[1].loc[subkey])
            rows[key] = {
                runs[0].name: v0,
                runs[1].name: v1,
                "diff_pct": pct_diff(v1, v0),
            }

    return pd.DataFrame.from_dict(
        rows, orient="index", columns=[runs[0].name, runs[1].name, "diff_pct"]
    )


# Writes output csvs
def write_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep three data columns. The metric id is stored as row index.
    df.to_csv(output_path, index=True, index_label="metric")


# Does arg parsing of the function, defines defaults in path and config name
def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract and compare configured metrics from two ReEDS runs."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to TOML config file. Defaults to config.toml in the current working directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output CSV path overriding [general].output_csv",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    config_path = args.config.resolve()
    config = load_config(config_path)
    runs = resolve_run_specs(config, config_path.parent)
    metrics = resolve_metric_specs(config)

    output_raw = args.output or Path(
        config.get("general", {}).get("output_csv", "reeds_metric_comparison.csv")
    )
    output_path = (
        output_raw if output_raw.is_absolute() else (config_path.parent / output_raw)
    )

    comparison = build_comparison(runs, metrics)
    write_csv(comparison, output_path)
    print(f"Wrote {len(comparison):,} comparison rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
