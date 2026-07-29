from __future__ import annotations

import argparse
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_CONFIG_FILE = "config.toml"

DEFAULT_PRIMARY_METRICS_OUTPUT = "primary_metrics_comparison.csv"
DEFAULT_CAPACITY_MIX_OUTPUT = "capacity_mix_comparison.csv"
DEFAULT_COST_COMPARISON_OUTPUT = "cost_comparison.csv"
DEFAULT_EMISSIONS_OUTPUT = "emissions_comparison.csv"
DEFAULT_CAPACITY_CHANGES_OUTPUT = "capacity_changes_comparison.csv"
DEFAULT_LOAD_OUTPUT = "load_comparison.csv"


VALID_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI",
    "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV",
    "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VA", "VT", "WA", "WI", "WV", "WY", "DC",
}


@dataclass(frozen=True)
class RunSpec:
    name: str
    path: Path


@dataclass(frozen=True)
class ProjectConfig:
    runs: list[RunSpec]

    # Shared comparison settings
    years: list[int] | str
    states: list[str]
    region_to_state_file: Path | None

    # Output paths
    primary_metrics_output_csv: Path
    capacity_mix_output_csv: Path
    cost_comparison_output_csv: Path
    emissions_output_csv: Path
    capacity_changes_output_csv: Path
    load_output_csv: Path

    # Cost settings
    dollar_year: int
    dollar_conversion_factor: float

    # Metric selection
    metric_include: list[str]

    # Capacity mix settings
    capacity_mix_unit: str

    # Capacity changes settings
    capacity_changes_unit: str

    # Cost comparison settings
    cost_comparison_unit: str
    group_cost_categories: bool

    # Emissions settings
    emissions_unit: str
    emissions_type: str

    # Load settings
    load_unit: str
    large_load_file_pattern: str
    large_load_threshold_mwh: float
    large_load_value_multiplier: float
    large_load_state_column: str | None
    large_load_region_column: str | None
    large_load_year_column: str | None
    large_load_value_column: str | None
    clip_large_load_to_total: bool


def parse_common_args(
    argv: Iterable[str],
    description: str,
    default_output: str | None = None,
) -> argparse.Namespace:
    """
    Shared CLI parser for runner scripts.

    Each runner can pass:
    - --config
    - --output
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(DEFAULT_CONFIG_FILE),
        help=f"Path to TOML config file. Defaults to {DEFAULT_CONFIG_FILE}.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional output CSV path."
            if default_output is None
            else f"Optional output CSV path. Defaults to {default_output}."
        ),
    )
    return parser.parse_args(list(argv))


def resolve_path(path_raw: str | Path, base: Path) -> Path:
    path = Path(path_raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_toml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Create {DEFAULT_CONFIG_FILE} "
            "in the current directory or pass --config path/to/config.toml."
        )

    with path.open("rb") as f:
        return tomllib.load(f)


def _parse_years(value: object) -> list[int] | str:
    if value is None:
        return "shared"

    if isinstance(value, str):
        years = value.lower()
        if years != "shared":
            raise ValueError("[general].years must be 'shared' or an array of years")
        return years

    if isinstance(value, list):
        return sorted({int(y) for y in value})

    raise ValueError("[general].years must be 'shared' or an array of years")


def _parse_states(value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("[general].states must be a non-empty array, e.g. ['NM']")

    states = [str(s).upper() for s in value]
    unknown_states = sorted(set(states) - VALID_STATES)
    if unknown_states:
        raise ValueError(f"Unknown state abbreviation(s): {unknown_states}")

    return states


def _resolve_runs(raw: dict, config_dir: Path) -> list[RunSpec]:
    general = raw.get("general", {})
    runs_root = resolve_path(general.get("runs_root", "."), config_dir)

    runs: list[RunSpec] = []

    for item in raw.get("runs", []):
        name = str(item["name"])
        run_path = Path(str(item["path"])).expanduser()

        if not run_path.is_absolute():
            run_path = runs_root / run_path

        runs.append(
            RunSpec(
                name=name,
                path=run_path.resolve(),
            )
        )

    if len(runs) != 2:
        raise ValueError(f"This version expects exactly two [[runs]], found {len(runs)}")

    return runs


def _resolve_output_path(
    config_dir: Path,
    raw_path: str | Path,
) -> Path:
    path = Path(raw_path).expanduser()

    if not path.is_absolute():
        path = config_dir / path

    return path.resolve()


def _output_with_optional_override(
    config_dir: Path,
    configured_path: str | Path,
    output_override: Path | None,
    output_kind: str | None,
    this_kind: str,
) -> Path:
    """
    Resolve an output path.

    If output_override is supplied:
    - apply it only when output_kind matches this output type;
    - if output_kind is None, apply it to all outputs for backward compatibility.

    Runner scripts should ideally call:
        load_config(..., output_override=args.output, output_kind="capacity_mix")

    That ensures only the runner's own output path is overridden.
    """
    if output_override is not None and (
        output_kind is None or output_kind == this_kind
    ):
        use_path: str | Path = output_override
    else:
        use_path = configured_path

    return _resolve_output_path(config_dir, use_path)


def _optional_str(section: dict, key: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None

    value_str = str(value).strip()
    if not value_str:
        return None

    return value_str


def load_config(
    config_path: Path,
    output_override: Path | None = None,
    output_kind: str | None = None,
) -> ProjectConfig:
    """
    Load the shared project config.

    The TOML file owns:
    - run definitions
    - run folder locations
    - state filters
    - year filters
    - output locations
    - dollar-year conversion factor
    - chart/output toggles

    Metric formulas, file-specific logic, and calculations live in Python modules.
    """
    config_path = config_path.resolve()
    config_dir = config_path.parent
    raw = load_toml(config_path)

    general = raw.get("general", {})
    metrics = raw.get("metrics", {})
    capacity_mix = raw.get("capacity_mix", {})
    capacity_changes = raw.get("capacity_changes", {})
    cost_comparison = raw.get("cost_comparison", {})
    emissions = raw.get("emissions", {})
    load = raw.get("load", {})

    runs = _resolve_runs(raw, config_dir)
    years = _parse_years(general.get("years", "shared"))
    states = _parse_states(general.get("states", []))

    region_map_raw = general.get("region_to_state_file")
    region_to_state_file = (
        resolve_path(region_map_raw, config_dir)
        if region_map_raw
        else None
    )

    primary_metrics_output_csv = _output_with_optional_override(
        config_dir=config_dir,
        configured_path=general.get(
            "primary_metrics_output_csv",
            DEFAULT_PRIMARY_METRICS_OUTPUT,
        ),
        output_override=output_override,
        output_kind=output_kind,
        this_kind="primary_metrics",
    )

    capacity_mix_output_csv = _output_with_optional_override(
        config_dir=config_dir,
        configured_path=general.get(
            "capacity_mix_output_csv",
            DEFAULT_CAPACITY_MIX_OUTPUT,
        ),
        output_override=output_override,
        output_kind=output_kind,
        this_kind="capacity_mix",
    )

    cost_comparison_output_csv = _output_with_optional_override(
        config_dir=config_dir,
        configured_path=general.get(
            "cost_comparison_output_csv",
            DEFAULT_COST_COMPARISON_OUTPUT,
        ),
        output_override=output_override,
        output_kind=output_kind,
        this_kind="cost_comparison",
    )

    emissions_output_csv = _output_with_optional_override(
        config_dir=config_dir,
        configured_path=general.get(
            "emissions_output_csv",
            DEFAULT_EMISSIONS_OUTPUT,
        ),
        output_override=output_override,
        output_kind=output_kind,
        this_kind="emissions",
    )

    capacity_changes_output_csv = _output_with_optional_override(
        config_dir=config_dir,
        configured_path=general.get(
            "capacity_changes_output_csv",
            DEFAULT_CAPACITY_CHANGES_OUTPUT,
        ),
        output_override=output_override,
        output_kind=output_kind,
        this_kind="capacity_changes",
    )

    load_output_csv = _output_with_optional_override(
        config_dir=config_dir,
        configured_path=general.get(
            "load_output_csv",
            DEFAULT_LOAD_OUTPUT,
        ),
        output_override=output_override,
        output_kind=output_kind,
        this_kind="load",
    )

    metric_include = [str(x).lower() for x in metrics.get("include", ["all"])]

    dollar_year = int(general.get("dollar_year", 2026))
    dollar_conversion_factor = float(general.get("dollar_conversion_factor", 1.0))

    return ProjectConfig(
        runs=runs,
        years=years,
        states=states,
        region_to_state_file=region_to_state_file,

        primary_metrics_output_csv=primary_metrics_output_csv,
        capacity_mix_output_csv=capacity_mix_output_csv,
        cost_comparison_output_csv=cost_comparison_output_csv,
        emissions_output_csv=emissions_output_csv,
        capacity_changes_output_csv=capacity_changes_output_csv,
        load_output_csv=load_output_csv,

        dollar_year=dollar_year,
        dollar_conversion_factor=dollar_conversion_factor,

        metric_include=metric_include,

        capacity_mix_unit=str(capacity_mix.get("unit", "MW")),

        capacity_changes_unit=str(capacity_changes.get("unit", "MW")),

        cost_comparison_unit=str(
            cost_comparison.get("unit", f"{dollar_year}$")
        ),
        group_cost_categories=bool(
            cost_comparison.get("group_cost_categories", True)
        ),

        emissions_unit=str(emissions.get("unit", "metric tons CO2")),
        emissions_type=str(emissions.get("emissions_type", "CO2")).upper(),

        load_unit=str(load.get("unit", "MWh")),
        large_load_file_pattern=str(
            load.get("large_load_file_pattern", "inputs_case/loadsite_annual.csv")
        ),
        large_load_threshold_mwh=float(
            load.get("large_load_threshold_mwh", 1_000_000.0)
        ),
        large_load_value_multiplier=float(
            load.get("large_load_value_multiplier", 1.0)
        ),
        large_load_state_column=_optional_str(load, "large_load_state_column"),
        large_load_region_column=_optional_str(load, "large_load_region_column"),
        large_load_year_column=_optional_str(load, "large_load_year_column"),
        large_load_value_column=_optional_str(load, "large_load_value_column"),
        clip_large_load_to_total=bool(
            load.get("clip_large_load_to_total", True)
        ),
    )
