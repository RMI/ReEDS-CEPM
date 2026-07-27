from __future__ import annotations

import re

import pandas as pd

from utils.config import ProjectConfig, RunSpec
from utils.filters import clean_string_column, filter_years, standardize_value_frame
from utils.geography import add_state, load_region_to_state_map
from utils.io import read_reeds_output


def normalize_resource_name(resource: str) -> str:
    """
    Normalize ReEDS technology strings for pattern matching.

    This keeps enough structure to distinguish broad technology families while
    removing common ReEDS bin/class/vintage suffixes.

    Examples:
    - wind-ons_5 -> wind-ons
    - wind-ons-5 -> wind-ons
    - battery_4 -> battery
    - lfill-gas_p63_1 -> lfill-gas
    - gas-cc_re-cc_p63_4 -> gas-cc-re-cc
    """
    out = str(resource).strip().lower()
    out = out.replace("_", "-")
    out = out.replace(" ", "-")

    # Remove common ReEDS supply-curve / plant-bin suffixes.
    # Examples: _5, -5, _p63_4, -p63-4, p64_2 after underscore replacement.
    out = re.sub(r"-p\d+(-\d+)?$", "", out)
    out = re.sub(r"-\d+$", "", out)

    # Collapse repeated separators.
    out = re.sub(r"-+", "-", out).strip("-")

    return out


def group_capacity_resource(resource: str) -> str:
    """
    Map detailed ReEDS resource names to broader human-readable capacity categories.

    The mapping is intentionally conservative:
    - Known ReEDS families are grouped.
    - Unknown names are preserved rather than hidden in Other.
    """
    raw = str(resource).strip()
    r = normalize_resource_name(raw)

    # ------------------------------------------------------------
    # Hydropower
    # ReEDS hydropower names commonly include hyd, hydED, hydEND,
    # hydNPD, hydNSD, hydUD, psh, pumped-hydro, etc.
    # ------------------------------------------------------------
    if (
        r.startswith("hyd")
        or r in {"hydro", "hyded", "hydend", "hydnpd", "hydnsd", "hydud"}
        or r.startswith("hyded")
        or r.startswith("hydend")
        or r.startswith("hydnpd")
        or r.startswith("hydnsd")
        or r.startswith("hydud")
    ):
        return "Hydro"

    # Pumped storage is often charted separately from conventional hydro.
    # Put this before the generic Storage block if you want a separate category.
    if (
        r in {"psh", "pumped-hydro", "pumped-storage", "pumpback-hydro"}
        or "pumped-hydro" in r
        or "pumped-storage" in r
        or "pumpback" in r
    ):
        return "Pumped Storage"

    # ------------------------------------------------------------
    # Wind
    # ReEDS land-based wind often appears as wind-ons with classes/bins.
    # Offshore wind can appear as wind-ofs, offshore-wind, osw, fixed/floating.
    # ------------------------------------------------------------
    if (
        r.startswith("wind")
        or r.startswith("wind-ons")
        or r.startswith("wind-ofs")
        or r.startswith("offshore-wind")
        or r in {"osw", "wind-onshore", "wind-offshore"}
        or "wind-ons" in r
        or "wind-ofs" in r
        or "offshore-wind" in r
    ):
        return "Wind"

    # ------------------------------------------------------------
    # Solar
    # ReEDS differentiates UPV, PVB, and distPV; CSP is solar thermal.
    # For a broad stacked capacity chart, group them together as Solar.
    # If you want CSP separate later, split it here.
    # ------------------------------------------------------------
    if (
        r in {"upv", "dupv", "distpv", "pv", "pvb", "csp"}
        or r.startswith("upv")
        or r.startswith("dupv")
        or r.startswith("distpv")
        or r.startswith("pvb")
        or r.startswith("csp")
        or "solar" in r
    ):
        return "Solar"

    # ------------------------------------------------------------
    # Storage
    # Includes battery and other electricity storage technologies.
    # Pumped storage is handled above so it can remain separate.
    # ------------------------------------------------------------
    if (
        r.startswith("battery")
        or r.startswith("batteries")
        or r.startswith("storage")
        or r.startswith("beccs-storage")
        or r in {"battery", "bess", "li-ion", "lib"}
        or "battery" in r
        or "storage" in r
    ):
        return "Storage"

    # ------------------------------------------------------------
    # Nuclear
    # ------------------------------------------------------------
    if (
        r.startswith("nuclear")
        or r.startswith("nuc")
        or r in {"nuclear-smr", "smr"}
        or "nuclear" in r
    ):
        return "Nuclear"

    # ------------------------------------------------------------
    # Gas
    # Combined cycle, combustion turbine, gas with CCS, H2-retrofitted
    # combustion technologies if named from gas families.
    # ------------------------------------------------------------
    if (
        r.startswith("gas")
        or r.startswith("ng")
        or r.startswith("ngcc")
        or r.startswith("ngct")
        or r.startswith("ct")
        or r.startswith("cc")
        or r.startswith("combustion-turbine")
        or "gas-cc" in r
        or "gas-ct" in r
        or "ngcc" in r
        or "ngct" in r
        or "re-cc" in r
        or "re-ct" in r
    ):
        return "Gas"

    # ------------------------------------------------------------
    # Oil / Gas Steam
    # ReEDS documentation uses OGS for oil-gas steam.
    # Values may show up as o-g-s, ogs, oil-gas-steam, etc.
    # ------------------------------------------------------------
    if (
        r in {"ogs", "o-g-s", "oil-gas-steam", "oilgassteam", "gas-oil-steam"}
        or "oil-gas-steam" in r
        or "o-g-s" in r
    ):
        return "Oil/Gas Steam"

    # ------------------------------------------------------------
    # Coal
    # ------------------------------------------------------------
    if (
        r.startswith("coal")
        or r.startswith("igcc")
        or "coal" in r
        or "cofire" in r
    ):
        return "Coal"

    # ------------------------------------------------------------
    # Oil / diesel, excluding Oil/Gas Steam handled above.
    # ------------------------------------------------------------
    if (
        r.startswith("oil")
        or r.startswith("diesel")
        or "diesel" in r
        or r in {"distillate", "petroleum"}
    ):
        return "Oil"

    # ------------------------------------------------------------
    # Geothermal
    # ------------------------------------------------------------
    if (
        r.startswith("geo")
        or r.startswith("egs")
        or "geothermal" in r
    ):
        return "Geothermal"

    # ------------------------------------------------------------
    # Biomass / biopower / landfill gas
    # ReEDS documentation discusses biopower and landfill gas separately;
    # grouping them together can be useful for chart readability.
    # If you want landfill gas separate, return "Landfill Gas" here instead.
    # ------------------------------------------------------------
    if (
        r.startswith("bio")
        or "biomass" in r
        or "biopower" in r
        or "lfill" in r
        or "landfill" in r
        or r in {"lfg", "landfill-gas", "lfill-gas"}
    ):
        return "Biomass / Landfill Gas"

    # ------------------------------------------------------------
    # Hydrogen
    # ------------------------------------------------------------
    if (
        r.startswith("h2")
        or "hydrogen" in r
        or r in {"electrolyzer", "electrolyzers"}
    ):
        return "Hydrogen"

    # ------------------------------------------------------------
    # Demand-side / demand response
    # ------------------------------------------------------------
    if (
        r.startswith("dr")
        or "demand-response" in r
        or "demandresponse" in r
        or "flex" in r
    ):
        return "Demand Response"

    # ------------------------------------------------------------
    # Transmission / converter-like entries.
    # These should not usually appear in cap.csv as generation capacity,
    # but keeping this prevents them from looking like unknown resources.
    # ------------------------------------------------------------
    if (
        r.startswith("trans")
        or "transmission" in r
        or "converter" in r
        or r.startswith("acdc")
        or r.startswith("dc")
    ):
        return "Transmission"

    # Fallback: preserve the original detailed label so unmapped categories
    # remain visible and can be added later.
    return raw


def build_installed_capacity_mix_for_run(
    run: RunSpec,
    config: ProjectConfig,
) -> pd.DataFrame:
    """
    Build a long/tidy installed capacity mix table for one run.

    Intermediate output columns:
    - run
    - state
    - year
    - resource
    - value
    - unit

    Detailed ReEDS technologies are grouped into broad resource categories.
    """
    mapping = load_region_to_state_map(config, run)

    cap = read_reeds_output(
        run,
        ["cap.csv"],
        ["i", "r", "t", "value"],
        required=True,
    )

    if cap is None:
        raise FileNotFoundError(f"cap.csv not found for run {run.name}")

    cap = standardize_value_frame(cap)
    cap = filter_years(cap, config.years)
    cap = clean_string_column(cap, "i")
    cap = add_state(cap, mapping, config.states)

    cap["resource_detail"] = cap["i"]
    cap["resource"] = cap["resource_detail"].apply(group_capacity_resource)

    grouped = (
        cap.groupby(["state", "t", "resource"], as_index=False)["value"]
        .sum()
        .rename(columns={"t": "year"})
    )

    grouped["run"] = run.name
    grouped["unit"] = config.capacity_mix_unit

    return grouped[["run", "state", "year", "resource", "value", "unit"]]


def build_installed_capacity_mix_long(config: ProjectConfig) -> pd.DataFrame:
    """
    Build the installed capacity mix table across all configured runs
    in long/tidy format.

    Columns:
    - run
    - state
    - year
    - resource
    - value
    - unit
    """
    frames = [
        build_installed_capacity_mix_for_run(run, config)
        for run in config.runs
    ]

    if not frames:
        return pd.DataFrame(
            columns=["run", "state", "year", "resource", "value", "unit"]
        )

    out = pd.concat(frames, ignore_index=True)

    return (
        out.sort_values(["state", "year", "run", "resource"])
        .reset_index(drop=True)
    )


def build_installed_capacity_mix_wide(config: ProjectConfig) -> pd.DataFrame:
    """
    Build a chart-ready wide installed capacity mix table.

    Output columns look like:

        resource,unit,Run1 + NM + 2026,Run2 + NM + 2026,Run1 + NM + 2032,Run2 + NM + 2032

    Each value column is one stacked bar, and each resource row is a stack segment.
    """
    long_df = build_installed_capacity_mix_long(config)

    if long_df.empty:
        return pd.DataFrame(columns=["resource", "unit"])

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
            index=["resource", "unit"],
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

    ordered_columns = ["resource", "unit"] + desired_value_columns
    remaining_columns = [
        col for col in wide.columns
        if col not in ordered_columns
    ]

    return wide[ordered_columns + remaining_columns]


def build_installed_capacity_mix(config: ProjectConfig) -> pd.DataFrame:
    """
    Public builder used by build_capacity_mix.py.

    Returns wide/chart-ready output by default.
    """
    return build_installed_capacity_mix_wide(config)
