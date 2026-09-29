"""Unstandardized rIACI climate indices.

Every public function returns a DataFrame with ``Date`` and ``Value``.
Missing daily observations do not enter percentage denominators. A monthly
result is NaN when more than three days are missing by default; the annual
limit is fifteen days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .climate import ClimateInput


def _labels(ci: ClimateInput, freq: str) -> pd.Index:
    if freq == "monthly":
        return pd.Index(ci.dates.strftime("%Y-%m"))
    if freq == "annual":
        return pd.Index(ci.dates.strftime("%Y"))
    raise ValueError("freq must be 'monthly' or 'annual'.")


def _frame(values: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"Date": values.index.astype(str), "Value": values.to_numpy(dtype=float)})


def _masked(ci: ClimateInput, variable: str, freq: str, values: pd.Series) -> pd.DataFrame:
    mask = ci.na_masks[freq][variable].reindex(values.index)
    return _frame(values * mask)


def _percent(ci: ClimateInput, variable: str, quantile: float, op: str, freq: str) -> pd.DataFrame:
    if variable not in ci.data:
        raise ValueError(f"{variable} data are missing.")
    threshold_column = f"Q{quantile * 100:.1f}"
    thresholds = ci.quantiles[variable].set_index("month_day")[threshold_column]
    daily_thresholds = pd.Series(ci.month_day.map(thresholds).to_numpy(dtype=float), index=ci.dates)
    daily = ci.data[variable]
    flags = daily.gt(daily_thresholds) if op == ">" else daily.lt(daily_thresholds)
    flags = flags.astype(float).mask(daily.isna() | daily_thresholds.isna())
    grouped = pd.Series(flags.to_numpy()).groupby(_labels(ci, freq), sort=True).mean() * 100
    return _masked(ci, variable, freq, grouped)


def tx90p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _percent(ci, "tmax", 0.90, ">", freq)


def tx10p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _percent(ci, "tmax", 0.10, "<", freq)


def tn90p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _percent(ci, "tmin", 0.90, ">", freq)


def tn10p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _percent(ci, "tmin", 0.10, "<", freq)


def _average(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    paired = left.merge(right, on="Date", how="outer", suffixes=("_day", "_night"))
    paired["Value"] = (paired["Value_day"] + paired["Value_night"]) / 2
    return paired[["Date", "Value"]]


def t90p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    # The R function accepts freq but always computes monthly components.
    if freq not in ("monthly", "annual"):
        raise ValueError("freq must be 'monthly' or 'annual'.")
    return _average(tx90p(ci, "monthly"), tn90p(ci, "monthly"))


def t10p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    return _average(tx10p(ci, freq), tn10p(ci, freq))


def rx5day(
    ci: ClimateInput,
    freq: str = "monthly",
    center_mean_on_last_day: bool = False,
) -> pd.DataFrame:
    """Maximum five-day precipitation sum, grouped by the last window day."""
    if "prec" not in ci.data:
        raise ValueError("Precipitation data are missing.")
    prec = ci.data["prec"].fillna(0)
    runsum = prec.rolling(5, min_periods=5).sum()
    if center_mean_on_last_day:
        runsum = runsum.shift(2, fill_value=0)
    grouped = pd.Series(runsum.to_numpy()).groupby(_labels(ci, freq), sort=True).max()
    return _masked(ci, "prec", freq, grouped)


def _annual_dry_spells(ci: ClimateInput, spells_can_span_years: bool) -> pd.Series:
    prec = ci.data["prec"].to_numpy(dtype=float)
    labels = _labels(ci, "annual")
    dry = np.where(np.isnan(prec), None, prec < 1)
    years = labels.unique()
    result = {}
    def is_dry(flag) -> bool:
        return flag is not None and bool(flag)

    if spells_can_span_years:
        ending_lengths = np.zeros(len(dry), dtype=float)
        run_start = None
        for i, flag in enumerate(dry):
            if is_dry(flag):
                if run_start is None:
                    run_start = i
            elif run_start is not None:
                ending_lengths[i - 1] = i - run_start
                run_start = None
        if run_start is not None:
            ending_lengths[-1] = len(dry) - run_start
        for year in years:
            positions = np.flatnonzero(labels == year)
            maximum = float(ending_lengths[positions].max())
            year_flags = dry[positions]
            # R's all(): any FALSE wins; otherwise an NA makes it unknown.
            any_false = any(flag is not None and not is_dry(flag) for flag in year_flags)
            all_true_or_unknown = not any_false
            result[year] = np.nan if maximum == 0 and all_true_or_unknown else maximum
    else:
        for year in years:
            year_flags = dry[np.flatnonzero(labels == year)]
            longest = current = 0
            for flag in year_flags:
                current = current + 1 if is_dry(flag) else 0
                longest = max(longest, current)
            result[year] = float(longest) if longest else -np.inf
    return pd.Series(result, dtype=float)


def cdd(
    ci: ClimateInput,
    spells_can_span_years: bool = True,
    monthly: bool = True,
) -> pd.DataFrame:
    """Annual longest dry spell; monthly values interpolate annual results.

    The interpolation is part of the R implementation and is retained here.
    """
    if "prec" not in ci.data:
        raise ValueError("Precipitation data are missing.")
    annual = _annual_dry_spells(ci, spells_can_span_years)
    annual = annual * ci.na_masks["annual"]["prec"].reindex(annual.index)
    if not monthly:
        return _frame(annual)
    years = annual.index.astype(int).to_numpy()
    target_dates = pd.date_range(f"{years.min()}-01-01", f"{years.max()}-12-01", freq="MS")
    target = target_dates.year + (target_dates.month - 1) / 12
    source = years + 11 / 12
    valid = np.isfinite(annual.to_numpy())
    if valid.sum() < 2:
        raise ValueError("CDD interpolation requires at least two valid annual values.")
    interpolated = np.interp(target, source[valid], annual.to_numpy()[valid])
    return pd.DataFrame({"Date": target_dates.strftime("%Y-%m"), "Value": interpolated})


def w90p(ci: ClimateInput, freq: str = "monthly") -> pd.DataFrame:
    if "wind" not in ci.data:
        raise ValueError("Wind data are missing.")
    thresholds = ci.quantiles["wind"].set_index("month_day")["threshold"]
    daily_thresholds = pd.Series(ci.month_day.map(thresholds).to_numpy(dtype=float), index=ci.dates)
    daily = ci.data["wind"]
    flags = daily.gt(daily_thresholds).astype(float).mask(daily.isna() | daily_thresholds.isna())
    grouped = pd.Series(flags.to_numpy()).groupby(_labels(ci, freq), sort=True).mean() * 100
    return _masked(ci, "wind", freq, grouped)
