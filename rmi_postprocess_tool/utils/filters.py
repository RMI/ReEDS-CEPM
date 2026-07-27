from __future__ import annotations

import pandas as pd


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


def standardize_value_frame(
    df: pd.DataFrame,
    value_column: str = "value",
    year_column: str = "t",
) -> pd.DataFrame:
    out = df.copy()

    if year_column in out.columns:
        out = ensure_year(out, year_column)

    out = ensure_numeric(out, value_column)
    return out


def filter_years(
    df: pd.DataFrame,
    years: list[int] | str,
    year_column: str = "t",
) -> pd.DataFrame:
    if year_column not in df.columns:
        return df

    out = ensure_year(df, year_column)

    if isinstance(years, list):
        out = out[out[year_column].isin(years)]

    return out
