from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from utils.config import ProjectConfig, RunSpec, VALID_STATES
from utils.io import read_reeds_output


def infer_state_from_region(region: str) -> str | None:
    """
    Fallback parser for ReEDS regions that contain a state token.

    This is not preferred. A hierarchy or explicit region-to-state map is better.
    """
    region_upper = str(region).upper().strip()

    if region_upper in VALID_STATES:
        return region_upper

    tokens = re.split(r"[^A-Z]+", region_upper)
    for token in tokens:
        if token in VALID_STATES:
            return token

    for state in VALID_STATES:
        if region_upper.endswith(state):
            return state

    return None


def _read_mapping_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, comment="#")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _region_state_columns(df: pd.DataFrame) -> tuple[str, str] | None:
    lower = {c.lower(): c for c in df.columns}

    r_candidates = ["r", "region", "reeds_region", "ba", "*r"]
    state_candidates = ["state", "st", "state_abbr", "state_code", "*st"]

    r_col = next((lower[c] for c in r_candidates if c in lower), None)
    state_col = next((lower[c] for c in state_candidates if c in lower), None)

    if r_col and state_col:
        return r_col, state_col

    return None


def _candidate_mapping_files(config: ProjectConfig, run: RunSpec) -> list[Path]:
    candidates: list[Path] = []

    if config.region_to_state_file:
        candidates.append(config.region_to_state_file)

    candidates.extend(
        [
            run.path / "inputs_case" / "hierarchy.csv",
            run.path / "inputs_case" / "hierarchy.csv.gz",
            run.path / "inputs" / "hierarchy.csv",
            run.path / "inputs" / "hierarchy.csv.gz",
            run.path / "inputs_case" / "region_to_state.csv",
            run.path / "inputs" / "region_to_state.csv",
        ]
    )

    return candidates


def _standardize_mapping(df: pd.DataFrame, r_col: str, state_col: str) -> pd.DataFrame:
    out = df[[r_col, state_col]].copy()
    out.columns = ["r", "state"]
    out["r"] = out["r"].astype(str).str.strip()
    out["state"] = out["state"].astype(str).str.upper().str.strip()
    out = out[out["state"].isin(VALID_STATES)]
    return out.drop_duplicates()


def _infer_mapping_from_outputs(run: RunSpec) -> pd.DataFrame | None:
    regions: set[str] = set()

    common_region_outputs = [
        (["gen_ann.csv"], ["i", "r", "t", "value"]),
        (["load_rt.csv"], ["r", "t", "value"]),
        (["prm.csv"], ["r", "t", "value"]),
        (["curt_ann.csv"], ["r", "t", "value"]),
        (["cap.csv"], ["i", "r", "t", "value"]),
    ]

    for candidates, columns in common_region_outputs:
        df = read_reeds_output(run, candidates, columns, required=False)
        if df is not None and "r" in df.columns:
            regions.update(df["r"].astype(str).str.strip().unique())

    rows = []
    for region in regions:
        state = infer_state_from_region(region)
        if state:
            rows.append({"r": region, "state": state})

    if not rows:
        return None

    return pd.DataFrame(rows).drop_duplicates()


def load_region_to_state_map(config: ProjectConfig, run: RunSpec) -> pd.DataFrame:
    """
    Return a mapping DataFrame with columns:
    - r
    - state

    Order of preference:
    1. explicit [general].region_to_state_file
    2. common ReEDS hierarchy files
    3. fallback inference from region names in outputs
    """
    for path in _candidate_mapping_files(config, run):
        if not path.exists():
            continue

        df = _read_mapping_file(path)
        cols = _region_state_columns(df)

        if not cols:
            continue

        r_col, state_col = cols
        mapping = _standardize_mapping(df, r_col, state_col)

        if not mapping.empty:
            return mapping

    inferred = _infer_mapping_from_outputs(run)
    if inferred is not None and not inferred.empty:
        return inferred

    raise FileNotFoundError(
        "Could not find or infer a ReEDS region-to-state mapping. Add "
        "[general].region_to_state_file to config.toml. Expected columns include "
        "r/state, r/st, region/state, or similar."
    )


def add_state(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
    state_filter: list[str],
) -> pd.DataFrame:
    """
    Attach a state column based on the ReEDS region column `r`,
    then filter to selected states.
    """
    if "r" not in df.columns:
        raise KeyError("Expected column 'r' for state mapping")

    out = df.copy()
    out["r"] = out["r"].astype(str).str.strip()

    merged = out.merge(mapping, on="r", how="left")

    missing_regions = (
        merged.loc[merged["state"].isna(), "r"]
        .drop_duplicates()
        .head(20)
        .tolist()
    )

    if missing_regions:
        print(
            f"Warning: some regions could not be mapped to states. "
            f"Examples: {missing_regions}",
            file=sys.stderr,
        )

    return merged[merged["state"].isin(state_filter)]


def add_route_states(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
    state_filter: list[str],
) -> pd.DataFrame:
    """
    Assign transmission route rows to selected states touched by either endpoint.

    If a route goes from NM to AZ and both states are requested, that route
    contributes one row to NM and one row to AZ.
    """
    required = {"r", "rr"}
    if not required.issubset(df.columns):
        raise KeyError("Transmission utilization requires columns 'r' and 'rr'")

    left = mapping.rename(columns={"state": "state_r"})
    right = mapping.rename(columns={"r": "rr", "state": "state_rr"})

    out = df.copy()
    out["r"] = out["r"].astype(str).str.strip()
    out["rr"] = out["rr"].astype(str).str.strip()

    out = out.merge(left, on="r", how="left")
    out = out.merge(right, on="rr", how="left")

    rows = []
    for _, row in out.iterrows():
        route_states = {row.get("state_r"), row.get("state_rr")}
        route_states = {
            str(state)
            for state in route_states
            if pd.notna(state) and str(state) in state_filter
        }

        for state in route_states:
            new_row = row.copy()
            new_row["state"] = state
            rows.append(new_row)

    if not rows:
        return pd.DataFrame(columns=list(out.columns) + ["state"])

    return pd.DataFrame(rows)
