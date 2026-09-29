"""Join standardized components by date and process grid point CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .climate import ClimateInput, climate_input
from .standardize import cdd_std, rx5day_std, sea_std, t10p_std, t90p_std, w90p_std


def _validated_component(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if not {"Date", "Value"}.issubset(frame.columns):
        raise ValueError(f"{name} needs Date and Value columns.")
    if frame["Date"].isna().any():
        raise ValueError(f"{name} has missing Date labels.")
    repeated = frame.loc[frame["Date"].duplicated(), "Date"].unique()
    if len(repeated):
        raise ValueError(f"{name} has duplicate Date labels: {list(repeated[:5])}.")
    result = frame[["Date", "Value"]].copy()
    result["Date"] = result["Date"].astype(str)
    return result.rename(columns={"Value": name})


def merge_components(components: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Require exactly the same unique dates in every component.

    NaN component values remain NaN, as in R. Date mismatches raise an
    informative error instead of silently combining unrelated rows.
    """
    names = list(components)
    if not names:
        raise ValueError("No components were supplied.")
    prepared = {name: _validated_component(name, frame) for name, frame in components.items()}
    dates = set(prepared[names[0]]["Date"])
    for name in names[1:]:
        other = set(prepared[name]["Date"])
        if other != dates:
            missing = sorted(dates - other)[:5]
            extra = sorted(other - dates)[:5]
            raise ValueError(f"{name} dates differ from {names[0]}: missing {missing}; extra {extra}.")
    result = prepared[names[0]]
    for name in names[1:]:
        result = result.merge(prepared[name], on="Date", how="inner", validate="one_to_one", sort=False)
    return result.sort_values("Date", kind="stable").reset_index(drop=True)


def iaci_output(ci: ClimateInput, si: pd.DataFrame, freq: str = "monthly") -> pd.DataFrame:
    """Calculate the six standardized components and their equal-weight IACI."""
    if freq not in ("monthly", "seasonal"):
        raise ValueError("freq must be 'monthly' or 'seasonal'.")
    result = merge_components({
        "T90p": t90p_std(ci, freq),
        "T10p": t10p_std(ci, freq),
        "Rx5day": rx5day_std(ci, freq),
        "CDD": cdd_std(ci, freq),
        "W90p": w90p_std(ci, freq),
        "Sea": sea_std(si, ci, freq),
    })
    result["IACI"] = (
        result["T90p"] - result["T10p"] + result["Rx5day"]
        + result["CDD"] + result["W90p"] + result["Sea"]
    ) / 6
    return result


def output_all(
    si: pd.DataFrame,
    input_dir: str | Path,
    output_dir: str | Path,
    freq: str = "monthly",
    base_range: tuple[int, int] = (1961, 1990),
    time_span: tuple[int, int] = (1961, 2022),
    n: int = 5,
) -> list[Path]:
    """Calculate one output CSV per input grid point, preserving filenames."""
    if freq not in ("monthly", "seasonal"):
        raise ValueError("freq must be 'monthly' or 'seasonal'.")
    source = Path(input_dir)
    destination = Path(output_dir) / freq
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for csv_file in sorted(source.glob("*.csv")):
        daily = pd.read_csv(csv_file)
        needed = {"time", "TMAX", "TMIN", "PRCP", "WP"}
        missing = needed - set(daily.columns)
        if missing:
            raise ValueError(f"{csv_file.name} is missing columns {sorted(missing)}.")
        ci = climate_input(
            dates=daily["time"], tmax=daily["TMAX"], tmin=daily["TMIN"],
            prec=daily["PRCP"], wind=daily["WP"], base_range=base_range, n=n,
        )
        result = iaci_output(ci, si, freq)
        years = result["Date"].str.slice(0, 4).astype(int)
        result = result.loc[years.between(*time_span)]
        target = destination / csv_file.name
        result.to_csv(target, index=False)
        written.append(target)
    return written
