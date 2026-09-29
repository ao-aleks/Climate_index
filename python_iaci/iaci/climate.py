"""Daily input alignment, thresholds, and completeness masks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from .thresholds import temperature_quantiles, wind_quantiles


@dataclass
class ClimateInput:
    dates: pd.DatetimeIndex
    data: dict[str, pd.Series]
    quantiles: dict[str, pd.DataFrame]
    na_masks: dict[str, dict[str, pd.Series]]
    base_range: tuple[int, int]
    max_missing_days: dict[str, int]

    @property
    def month_day(self) -> pd.Index:
        return pd.Index(self.dates.strftime("%m-%d"))


def climate_input(
    *,
    dates,
    tmax=None,
    tmin=None,
    prec=None,
    wind=None,
    base_range: tuple[int, int] = (1961, 1990),
    n: int = 5,
    quantiles: Mapping[str, pd.DataFrame] | None = None,
    temp_quantiles: tuple[float, ...] = (0.10, 0.90),
    wind_quantile: float = 0.90,
    max_missing_days: Mapping[str, int] | None = None,
    min_base_data_fraction_present: float = 0.1,
) -> ClimateInput:
    """Make a complete daily series from input dates and calculate thresholds.

Missing dates become NaN. If an input date occurs twice, the last value wins,
    matching R's assignment into a date-indexed vector.
    """
    parsed = pd.to_datetime(dates, errors="raise")
    parsed = pd.DatetimeIndex(parsed).normalize()
    if len(parsed) == 0 or parsed.isna().any():
        raise ValueError("dates must contain valid calendar dates.")
    if len(base_range) != 2 or base_range[0] > base_range[1]:
        raise ValueError("base_range must contain an increasing pair of years.")
    missing_limits = dict(max_missing_days or {"annual": 15, "monthly": 3})
    if set(missing_limits) != {"annual", "monthly"}:
        raise ValueError("max_missing_days needs annual and monthly limits.")
    complete_dates = pd.date_range(parsed.min(), parsed.max(), freq="D")
    inputs = {"tmax": tmax, "tmin": tmin, "prec": prec, "wind": wind}
    if all(value is None for value in inputs.values()):
        raise ValueError("Provide at least one weather variable.")

    aligned: dict[str, pd.Series] = {}
    for name, value in inputs.items():
        if value is None:
            continue
        if len(value) != len(parsed):
            raise ValueError(f"{name} and dates must have equal length.")
        series = pd.Series(np.asarray(value, dtype=float), index=parsed)
        series = series.loc[~series.index.duplicated(keep="last")]
        aligned[name] = series.reindex(complete_dates)

    if quantiles is None:
        calculated = {}
        for name in ("tmax", "tmin"):
            if name in aligned:
                calculated[name] = temperature_quantiles(
                    aligned[name], base_range, n, temp_quantiles,
                    min_base_data_fraction_present,
                )
        if "wind" in aligned:
            calculated["wind"] = wind_quantiles(aligned["wind"], base_range, wind_quantile)
    else:
        calculated = dict(quantiles)

    masks: dict[str, dict[str, pd.Series]] = {"annual": {}, "monthly": {}}
    for frequency, labels in (
        ("annual", complete_dates.strftime("%Y")),
        ("monthly", complete_dates.strftime("%Y-%m")),
    ):
        for name, series in aligned.items():
            counts = pd.Series(series.isna().to_numpy()).groupby(labels, sort=True).sum()
            masks[frequency][name] = counts.le(missing_limits[frequency]).astype(float).replace(0, np.nan)
    return ClimateInput(complete_dates, aligned, calculated, masks, tuple(base_range), missing_limits)
