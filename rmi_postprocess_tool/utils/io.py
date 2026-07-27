from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.config import RunSpec


def first_existing(run: RunSpec, candidates: list[str]) -> Path | None:
    """
    Find the first candidate output file under <run>/outputs.
    """
    for rel_path in candidates:
        path = run.path / "outputs" / rel_path
        if path.exists():
            return path

    return None


def read_reeds_output(
    run: RunSpec,
    candidates: list[str],
    default_columns: list[str],
    required: bool = False,
) -> pd.DataFrame | None:
    """
    Read a ReEDS output CSV.

    Tries to support both:
    - headered CSVs
    - headerless GAMS-style CSVs

    If the first row looks like a real header and contains the expected columns,
    the header is used. Otherwise, the file is re-read with `default_columns`.
    """
    path = first_existing(run, candidates)

    if path is None:
        if required:
            raise FileNotFoundError(
                f"None of these files were found under {run.path / 'outputs'}: {candidates}"
            )
        return None

    df_headered = pd.read_csv(path, comment="#")
    df_headered.columns = [str(c).strip() for c in df_headered.columns]

    if set(default_columns).issubset(set(df_headered.columns)):
        return df_headered

    return pd.read_csv(path, header=None, names=default_columns, comment="#")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
