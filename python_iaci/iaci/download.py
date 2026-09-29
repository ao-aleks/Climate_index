"""Download hourly ERA5-Land files from the Climate Data Store.

This is the Python equivalent of rIACI's ``download_data`` wrapper. It uses
the official CDS Python client; authentication normally comes from the user's
``.cdsapirc`` file. A client can be supplied for testing.
"""

from __future__ import annotations

import calendar
import time
from pathlib import Path
from getpass import getpass

DEFAULT_VARIABLES = (
    "10m_u_component_of_wind", "10m_v_component_of_wind",
    "2m_temperature", "total_precipitation",
)


def download_data(
    start_year: int,
    end_year: int,
    *,
    start_month: int = 1,
    end_month: int = 12,
    variables=DEFAULT_VARIABLES,
    dataset: str = "reanalysis-era5-land",
    area: tuple[float, float, float, float] = (90, -180, -90, 180),
    output_dir: str | Path = "cds_data",
    user_id: str | None = None,
    user_key: str | None = None,
    max_retries: int = 3,
    retry_delay: float = 5,
    client=None,
) -> list[Path]:
    """Retrieve one NetCDF file per month in the requested year range.

    ``area`` uses north, west, south, east order. Modern CDS credentials are
    a personal token; ``user_id`` is accepted for API familiarity but unused.
    """
    if start_year > end_year or not 1 <= start_month <= end_month <= 12:
        raise ValueError("Invalid year or month range.")
    if max_retries < 1:
        raise ValueError("max_retries must be at least one.")
    if client is None:
        import cdsapi

        client = cdsapi.Client(
            url="https://cds.climate.copernicus.eu/api",
            key=getpass("CDS API token: "),
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for year in range(start_year, end_year + 1):
        for month in range(start_month, end_month + 1):
            request = {
                "variable": list(variables),
                "year": str(year),
                "month": f"{month:02d}",
                "day": [f"{day:02d}" for day in range(1, calendar.monthrange(year, month)[1] + 1)],
                "time": [f"{hour:02d}:00" for hour in range(24)],
                "area": list(area),
                "data_format": "netcdf",
                "download_format": "unarchived",
            }
            target = destination / f"{year}_{month:02d}.nc"
            for attempt in range(max_retries):
                try:
                    client.retrieve(dataset, request, str(target))
                    written.append(target)
                    break
                except Exception:
                    if attempt + 1 == max_retries:
                        raise
                    time.sleep(retry_delay)
    return written
