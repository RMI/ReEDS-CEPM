from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from utils.compare import compare_two_run_frames
from utils.config import ProjectConfig, RunSpec
from utils.filters import clean_string_column, filter_years, standardize_value_frame
from utils.geography import add_route_states, add_state, load_region_to_state_map
from utils.io import read_reeds_output


QUADS_TO_MMBTU = 1_000_000_000.0

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


@dataclass(frozen=True)
class MetricRow:
    metric: str
    state: str
    year: int
    detail: str
    unit: str
    value: float


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
                "metric": row.metric,
                "state": row.state,
                "year": row.year,
                "detail": row.detail,
                "unit": row.unit,
                run_name: row.value,
            }
            for row in rows
        ]
    )


def metric_system_cost(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    """
    CAPEX + OPEX approximation from BA-level system cost components.

    Primary source:
    - systemcost_ba.csv

    Fallback:
    - raw_inv_cost.csv + raw_op_cost.csv
    """
    df = read_reeds_output(
        run,
        ["systemcost_ba.csv"],
        ["sys_costs", "r", "t", "value"],
        required=False,
    )

    if df is None:
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

        rows: list[MetricRow] = []
        for _, row in grouped.iterrows():
            for state in config.states:
                rows.append(
                    MetricRow(
                        metric="system_cost_capex_opex",
                        state=state,
                        year=int(row["t"]),
                        detail="national_fallback",
                        unit=f"{config.dollar_year}$",
                        value=float(row["value"]),
                    )
                )
        return rows

    df = standardize_value_frame(df)
    df = clean_string_column(df, "sys_costs")
    df = filter_years(df, config.years)

    lower = df["sys_costs"].str.lower()
    exclude = pd.Series(False, index=df.index)

    for hint in COST_COMPONENT_EXCLUDE_HINTS:
        exclude = exclude | lower.str.contains(hint, regex=False, na=False)

    df = df[~exclude]
    df = add_state(df, mapping, config.states)

    grouped = df.groupby(["state", "t"], as_index=False)["value"].sum()
    grouped["value"] *= config.dollar_conversion_factor

    return rows_from_grouped(
        grouped,
        metric="system_cost_capex_opex",
        unit=f"{config.dollar_year}$",
    )


def metric_average_electricity_cost(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    """
    Average electricity cost = CAPEX + OPEX system cost / annual load.

    Because system cost is converted using dollar_conversion_factor, this returns
    the configured dollar year per MWh.
    """
    cost_rows = metric_system_cost(run, config, mapping)
    if not cost_rows:
        return []

    cost = pd.DataFrame([row.__dict__ for row in cost_rows])
    cost = cost.rename(columns={"value": "cost"})

    load = read_reeds_output(run, ["load_rt.csv"], ["r", "t", "value"], required=False)
    if load is None:
        return []

    load = standardize_value_frame(load)
    load = filter_years(load, config.years)
    load = add_state(load, mapping, config.states)

    load_grouped = (
        load.groupby(["state", "t"], as_index=False)["value"]
        .sum()
        .rename(columns={"t": "year", "value": "load_mwh"})
    )

    merged = cost.merge(load_grouped, on=["state", "year"], how="inner")
    merged = merged[merged["load_mwh"] != 0]
    merged["value"] = merged["cost"] / merged["load_mwh"]
    merged["t"] = merged["year"]

    return rows_from_grouped(
        merged,
        metric="average_electricity_cost",
        unit=f"{config.dollar_year}$/MWh",
    )


def metric_co2_emissions(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    df = read_reeds_output(
        run,
        ["emit_r.csv"],
        ["etype", "eall", "r", "t", "value"],
        required=False,
    )

    if df is None:
        return []

    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "etype")
    df = df[df["etype"].str.upper().isin({"CO2", "CO2E"})]
    df = add_state(df, mapping, config.states)

    grouped = df.groupby(["state", "t", "etype"], as_index=False)["value"].sum()
    grouped["detail"] = grouped["etype"]

    return rows_from_grouped(
        grouped,
        metric="emissions",
        unit="metric tons",
        detail_column="detail",
    )


def metric_generation_mix(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    df = read_reeds_output(
        run,
        ["gen_ann.csv"],
        ["i", "r", "t", "value"],
        required=False,
    )

    if df is None:
        return []

    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "i")
    df = add_state(df, mapping, config.states)

    tech = df.groupby(["state", "t", "i"], as_index=False)["value"].sum()
    total = (
        tech.groupby(["state", "t"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "total_gen"})
    )

    merged = tech.merge(total, on=["state", "t"], how="inner")
    merged = merged[merged["total_gen"] != 0]
    merged["value"] = merged["value"] / merged["total_gen"] * 100.0
    merged["detail"] = merged["i"]

    return rows_from_grouped(
        merged,
        metric="generation_mix",
        unit="%",
        detail_column="detail",
    )


def metric_capacity_additions(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    df = read_reeds_output(
        run,
        ["cap_new_ann.csv"],
        ["i", "r", "t", "value"],
        required=False,
    )

    if df is None:
        return []

    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "i")
    df = add_state(df, mapping, config.states)

    grouped = df.groupby(["state", "t", "i"], as_index=False)["value"].sum()
    grouped["detail"] = grouped["i"]

    return rows_from_grouped(
        grouped,
        metric="capacity_additions",
        unit="MW",
        detail_column="detail",
    )


def metric_reserve_margin(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    df = read_reeds_output(run, ["prm.csv"], ["r", "t", "value"], required=False)

    if df is None:
        return []

    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = add_state(df, mapping, config.states)

    grouped = df.groupby(["state", "t"], as_index=False)["value"].mean()
    grouped["value"] *= 100.0

    return rows_from_grouped(
        grouped,
        metric="reserve_margin",
        unit="%",
    )


def _transmission_utilization(
    run: RunSpec,
    config: ProjectConfig,
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

    return rows_from_grouped(
        grouped,
        metric="transmission_utilization",
        unit="%",
        detail_column="detail",
    )


def metric_transmission_utilization(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    rows: list[MetricRow] = []
    rows.extend(
        _transmission_utilization(
            run,
            config,
            mapping,
            file_name="tran_util_ann_rep.csv",
            detail="representative",
        )
    )
    rows.extend(
        _transmission_utilization(
            run,
            config,
            mapping,
            file_name="tran_util_ann_stress.csv",
            detail="stress",
        )
    )
    return rows


def metric_curtailment(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    rows: list[MetricRow] = []

    annual = read_reeds_output(
        run,
        ["curt_ann.csv"],
        ["r", "t", "value"],
        required=False,
    )

    if annual is not None:
        annual = standardize_value_frame(annual)
        annual = filter_years(annual, config.years)
        annual = add_state(annual, mapping, config.states)

        grouped = annual.groupby(["state", "t"], as_index=False)["value"].sum()
        rows.extend(
            rows_from_grouped(
                grouped,
                metric="curtailment",
                unit="MWh",
            )
        )

    tech = read_reeds_output(
        run,
        ["curt_tech.csv"],
        ["i", "r", "t", "value"],
        required=False,
    )

    if tech is not None:
        tech = standardize_value_frame(tech)
        tech = filter_years(tech, config.years)
        tech = clean_string_column(tech, "i")
        tech = add_state(tech, mapping, config.states)

        grouped = tech.groupby(["state", "t", "i"], as_index=False)["value"].sum()
        grouped["detail"] = grouped["i"]

        rows.extend(
            rows_from_grouped(
                grouped,
                metric="curtailment_by_technology",
                unit="MWh",
                detail_column="detail",
            )
        )

    return rows


def metric_fuel_consumption(
    run: RunSpec,
    config: ProjectConfig,
    mapping: pd.DataFrame,
) -> list[MetricRow]:
    df = read_reeds_output(
        run,
        ["repgasquant_irt.csv"],
        ["i", "r", "t", "value"],
        required=False,
    )

    if df is None:
        nat = read_reeds_output(
            run,
            ["repgasquant_nat.csv"],
            ["t", "value"],
            required=False,
        )

        if nat is None:
            return []

        nat = standardize_value_frame(nat)
        nat = filter_years(nat, config.years)
        grouped = nat.groupby("t", as_index=False)["value"].sum()
        grouped["value"] *= QUADS_TO_MMBTU

        rows: list[MetricRow] = []
        for _, row in grouped.iterrows():
            for state in config.states:
                rows.append(
                    MetricRow(
                        metric="fuel_consumption_natural_gas",
                        state=state,
                        year=int(row["t"]),
                        detail="national_fallback",
                        unit="MMBtu",
                        value=float(row["value"]),
                    )
                )

        return rows

    df = standardize_value_frame(df)
    df = filter_years(df, config.years)
    df = clean_string_column(df, "i")
    df = add_state(df, mapping, config.states)

    grouped = df.groupby(["state", "t", "i"], as_index=False)["value"].sum()
    grouped["value"] *= QUADS_TO_MMBTU
    grouped["detail"] = grouped["i"]

    return rows_from_grouped(
        grouped,
        metric="fuel_consumption_natural_gas",
        unit="MMBtu",
        detail_column="detail",
    )


METRIC_REGISTRY: dict[str, Callable[[RunSpec, ProjectConfig, pd.DataFrame], list[MetricRow]]] = {
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


def selected_metrics(config: ProjectConfig) -> list[str]:
    include = [x.lower() for x in config.metric_include]

    if include == ["all"] or "all" in include:
        return list(METRIC_REGISTRY.keys())

    unknown = sorted(set(include) - set(METRIC_REGISTRY.keys()))
    if unknown:
        raise ValueError(
            f"Unknown metric group(s): {unknown}. "
            f"Valid options: {sorted(METRIC_REGISTRY)}"
        )

    return include


def extract_run_metrics(run: RunSpec, config: ProjectConfig) -> pd.DataFrame:
    mapping = load_region_to_state_map(config, run)
    rows: list[MetricRow] = []

    for metric_name in selected_metrics(config):
        try:
            metric_rows = METRIC_REGISTRY[metric_name](run, config, mapping)
        except FileNotFoundError as exc:
            print(f"Warning: skipping {metric_name} for {run.name}: {exc}")
            metric_rows = []
        except KeyError as exc:
            print(f"Warning: skipping {metric_name} for {run.name}: {exc}")
            metric_rows = []

        rows.extend(metric_rows)

    if not rows:
        return pd.DataFrame(
            columns=["metric", "state", "year", "detail", "unit", run.name]
        )

    return metric_rows_to_frame(rows, run.name)


def build_primary_metrics_comparison(config: ProjectConfig) -> pd.DataFrame:
    run_frames = [extract_run_metrics(run, config) for run in config.runs]

    keys = ["metric", "state", "year", "detail", "unit"]
    comparison = compare_two_run_frames(
        run_frames[0],
        run_frames[1],
        runs=config.runs,
        keys=keys,
    )

    return comparison[
        keys + [config.runs[0].name, config.runs[1].name, "diff_pct"]
    ].sort_values(["metric", "state", "year", "detail"])
