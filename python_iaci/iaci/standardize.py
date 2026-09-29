"""Monthly and seasonal standardization against a reference period."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .climate import ClimateInput
from .indices import cdd, rx5day, tn10p, tn90p, tx10p, tx90p, w90p


def _checked_frame(df: pd.DataFrame) -> pd.DataFrame:
    if not {"Date", "Value"}.issubset(df.columns):
        raise ValueError("Expected Date and Value columns.")
    return df[["Date", "Value"]].copy()


def monthly_to_seasonal(data: pd.DataFrame) -> pd.DataFrame:
    """Average months into DJF, MAM, JJA, SON; December belongs to next year."""
    frame = _checked_frame(data)
    parts = frame["Date"].str.extract(r"^(\d{4})-(\d{2})$")
    if parts.isna().any().any():
        raise ValueError("Monthly dates must use YYYY-MM.")
    frame["year"] = parts[0].astype(int)
    frame["month"] = parts[1].astype(int)
    if not frame["month"].between(1, 12).all():
        raise ValueError("Month must be between 01 and 12.")
    seasons = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
               6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
    frame["season"] = pd.Categorical(frame["month"].map(seasons), ["DJF", "MAM", "JJA", "SON"], ordered=True)
    frame["season_year"] = frame["year"] + frame["month"].eq(12).astype(int)
    seasonal = frame.groupby(["season_year", "season"], observed=True, sort=True)["Value"].mean().reset_index()
    seasonal["Date"] = seasonal["season_year"].astype(str) + "-" + seasonal["season"].astype(str)
    return seasonal[["Date", "Value"]]


def _groups(frame: pd.DataFrame, freq: str) -> tuple[pd.DataFrame, str]:
    if freq not in ("monthly", "seasonal"):
        raise ValueError("freq must be 'monthly' or 'seasonal'.")
    df = _checked_frame(frame) if freq == "monthly" else monthly_to_seasonal(frame)
    df["year"] = df["Date"].str.slice(0, 4).astype(int)
    df["period"] = df["Date"].str.slice(5)
    return df, "period"


def calculate_standardized(
    df: pd.DataFrame,
    freq: str,
    base_range: tuple[int, int],
) -> pd.DataFrame:
    """Use the R sample standard deviation (ddof=1) per month or season."""
    frame, key = _groups(df, freq)
    reference = frame.loc[frame["year"].between(*base_range)]
    stats = reference.groupby(key)["Value"].agg(ref_mean="mean", ref_sd="std")
    frame = frame.join(stats, on=key)
    frame["Value"] = (frame["Value"] - frame["ref_mean"]) / frame["ref_sd"]
    return frame[["Date", "Value"]]


def cdd_std(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    frame, _ = _groups(cdd(ci, monthly=True), freq)
    reference = frame.loc[frame["year"].between(*ci.base_range), "Value"]
    frame["Value"] = (frame["Value"] - reference.mean()) / reference.std(ddof=1)
    return frame[["Date", "Value"]]


def _temperature_std(ci: ClimateInput, freq: str, upper: bool) -> pd.DataFrame:
    day = tx90p(ci) if upper else tx10p(ci)
    night = tn90p(ci) if upper else tn10p(ci)
    if freq == "seasonal":
        day = monthly_to_seasonal(day)
        # Preserve rIACI's seasonal formula: it uses the daytime series twice.
        night = monthly_to_seasonal(tx90p(ci) if upper else tx10p(ci))
    elif freq != "monthly":
        raise ValueError("freq must be 'monthly' or 'seasonal'.")
    pair = day.merge(night, on="Date", how="outer", suffixes=("_day", "_night"))
    pair["combined"] = (pair["Value_day"] + pair["Value_night"]) / 2
    pair["year"] = pair["Date"].str.slice(0, 4).astype(int)
    pair["period"] = pair["Date"].str.slice(5)
    reference = pair.loc[pair["year"].between(*ci.base_range)]
    stats = reference.groupby("period").agg(
        mean=("combined", "mean"),
        day_sd=("Value_day", "std"),
        night_sd=("Value_night", "std"),
    )
    stats["denominator"] = (stats["day_sd"] + stats["night_sd"]) / 2
    pair = pair.join(stats[["mean", "denominator"]], on="period")
    pair["Value"] = (pair["combined"] - pair["mean"]) / pair["denominator"]
    return pair[["Date", "Value"]]


def t90p_std(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _temperature_std(ci, freq, upper=True)


def t10p_std(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _temperature_std(ci, freq, upper=False)


def rx5day_std(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return calculate_standardized(rx5day(ci), freq, ci.base_range)


def w90p_std(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return calculate_standardized(w90p(ci), freq, ci.base_range)


def sea_input(dates, values=np.nan) -> pd.DataFrame:
    """Build a sea-level series with YYYY-MM date labels."""
    dates = list(dates)
    if not all(isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}", date) for date in dates):
        raise ValueError("All sea-level dates must use YYYY-MM.")
    if np.isscalar(values):
        values = [values] * len(dates)
    if len(values) != len(dates):
        raise ValueError("Sea-level dates and values must have equal length.")
    return pd.DataFrame({"Date": dates, "Value": np.asarray(values, dtype=float)})


def sea_std(si: pd.DataFrame, ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return calculate_standardized(si, freq, ci.base_range)
