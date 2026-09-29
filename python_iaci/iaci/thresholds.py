"""Calendar-day thresholds used by the original rIACI calculations.

The temperature calculation follows running_quantile.cpp, including its
calendar-day treatment of leap years and its type-8 quantile definition.
``n`` now controls the full window width. At the calendar boundaries the
window is truncated, as the original five-day window was.
"""

from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd


def _type8_quantile(values: np.ndarray, probability: float) -> float:
    """Return the sorted-sample quantile used by the package's C++ code."""
    if not 0 <= probability <= 1:
        raise ValueError("A quantile probability must be between 0 and 1.")
    x = np.sort(values)
    if len(x) == 0:
        return np.nan
    h = (len(x) + 1 / 3) * probability + 1 / 3
    j = int(np.floor(h))
    if j <= 0:
        return float(x[0])
    if j >= len(x):
        return float(x[-1])
    return float(x[j - 1] + (h - j) * (x[j] - x[j - 1]))


def temperature_quantiles(
    values: pd.Series,
    base_range: tuple[int, int] = (1961, 1990),
    n: int = 5,
    probabilities: tuple[float, ...] = (0.10, 0.90),
    min_fraction: float = 0.1,
) -> pd.DataFrame:
    """Compute thresholds for each of the 366 calendar dates.

    ``n`` is any positive integer. For an even ``n``, the target day has one
    more day after it than before it. An ``n`` of 366 or more uses all 366
    days. ``min_fraction`` retains the source C++ definition: number of valid
    observations divided by the nominal number of calendar positions in the
    window, even at January/December boundaries.
    """
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError("n must be a positive integer.")
    if not 0 <= min_fraction <= 1:
        raise ValueError("min_fraction must be between 0 and 1.")
    if len(base_range) != 2 or base_range[0] > base_range[1]:
        raise ValueError("base_range must contain an increasing pair of years.")

    values = pd.Series(values, copy=False)
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("values must have a DatetimeIndex.")
    in_base = (values.index.year >= base_range[0]) & (values.index.year <= base_range[1])
    if not np.any(in_base):
        raise ValueError("No dates fall within the specified base range.")

    base = values.loc[in_base]
    day_numbers = base.index.dayofyear.to_numpy(dtype=float)
    leap_day = (base.index.month == 2) & (base.index.day == 29)
    day_numbers[leap_day] = 59.5
    # Deliberately retain the source's day-of-year assignment after Feb 29.
    calendar_days = list(range(1, 366))
    calendar_days.insert(59, 59.5)
    day_vector = np.asarray(calendar_days)
    month_day = []
    for day in day_vector:
        date = (pd.Timestamp(2000, 2, 29) if day == 59.5
                else pd.Timestamp(2001, 1, 1) + pd.Timedelta(days=int(day) - 1))
        month_day.append(date.strftime("%m-%d"))
    base_values = base.to_numpy(dtype=float)
    by_day = {day: base_values[day_numbers == day] for day in day_vector}
    width = min(int(n), len(day_vector))
    left = (width - 1) // 2
    right = width - left - 1
    result = {"month_day": month_day}
    for probability in probabilities:
        result[f"Q{probability * 100:.1f}"] = []
    for i in range(len(day_vector)):
        window = (day_vector if width == len(day_vector) else
                  day_vector[max(0, i - left): min(len(day_vector), i + right + 1)])
        sample = np.concatenate([by_day[day] for day in window])
        sample = sample[~np.isnan(sample)]
        enough = len(sample) / width >= min_fraction and len(sample) > 0
        for probability in probabilities:
            result[f"Q{probability * 100:.1f}"].append(
                _type8_quantile(sample, probability) if enough else np.nan
            )
    return pd.DataFrame(result)


def wind_quantiles(
    values: pd.Series,
    base_range: tuple[int, int] = (1961, 1990),
    probability: float = 0.90,
) -> pd.DataFrame:
    """Use daily reference mean + normal z-score times sample SD, as in R."""
    if not 0 < probability < 1:
        raise ValueError("Wind probability must lie strictly between 0 and 1.")
    values = pd.Series(values, copy=False)
    mask = (values.index.year >= base_range[0]) & (values.index.year <= base_range[1])
    frame = pd.DataFrame({"month_day": values.index.strftime("%m-%d"), "wind": values.to_numpy()})
    stats = frame.loc[mask].groupby("month_day", sort=True)["wind"].agg(["mean", "std"])
    stats["threshold"] = stats["mean"] + NormalDist().inv_cdf(probability) * stats["std"]
    return stats[["threshold"]].reset_index()
