from __future__ import annotations

import pandas as pd

from utils.config import ProjectConfig, RunSpec
from utils.filters import clean_string_column, filter_years, standardize_value_frame
from utils.geography import add_state, load_region_to_state_map
from utils.io import read_reeds_output


def build_emissions_for_run(
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Build annual state-level emissions rows for one ReEDS run.

    Primary source:
    - outputs/emit_r.csv

    Expected columns:
    - etype: emissions source/category, e.g. upstream, process
    - eall: emissions type/species, e.g. CO2, CO2E
    - r: ReEDS region
    - t: model year
    - value: emissions value

    Output columns:
    - run
    - state
    - year
    - emissions
    - unit
    """
    mapping = load_region_to_state_map(config, run)

    emissions = read_reeds_output(
        run,
        ["emit_r.csv"],
        ["etype", "eall", "r", "t", "value"],
        required=True,
    )

    if emissions is None:
        raise FileNotFoundError(f"emit_r.csv not found for run {run.name}")

    emissions = standardize_value_frame(emissions)
    emissions = filter_years(emissions, config.years)

    emissions = clean_string_column(emissions, "etype")
    emissions = clean_string_column(emissions, "eall")

    # Important:
    # In emit_r.csv, etype is the emissions source/category, such as
    # "upstream" or "process". The pollutant/species such as CO2 or CO2E
    # is stored in eall.
    emissions = emissions[
        emissions["eall"].str.upper() == config.emissions_type.upper()
    ]

    emissions = add_state(emissions, mapping, config.states)

    grouped = (
        emissions.groupby(["state", "t"], as_index=False)["value"]
        .sum()
        .rename(columns={"t": "year", "value": "emissions"})
    )

    grouped["run"] = run.name
    grouped["unit"] = config.emissions_unit

    return grouped[["run", "state", "year", "emissions", "unit"]]


def build_emissions_long(config: ProjectConfig) -> pd.DataFrame:
    """
    Build line-chart-ready annual emissions output for all configured runs.

    Output columns:
    - run
    - state
    - year
    - emissions
    - unit
    """
    frames = [
        build_emissions_for_run(run, config)
        for run in config.runs
    ]

    if not frames:
        return pd.DataFrame(
            columns=["run", "state", "year", "emissions", "unit"]
        )

    out = pd.concat(frames, ignore_index=True)

    return (
        out.sort_values(["state", "run", "year"])
        .reset_index(drop=True)
    )


def build_emissions(config: ProjectConfig) -> pd.DataFrame:
    """
    Public builder used by build_emissions.py.

    Returns long/tidy output for line charts.
    """
    return build_emissions_long(config)
