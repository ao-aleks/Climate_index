# Iberian Actuarial Climate Index: Python port

This directory translates the downloaded `rIACI` 1.0.0 package into readable
Python modules. The original package is licensed GPL-3; this derived port is
distributed under the same license. The original files remain in `../rIACI`.

## Files

| File | Responsibility |
| --- | --- |
| `iaci/netcdf_io.py` | Existing Python NetCDF processing and CSV conversion, copied from the R package. |
| `iaci/download.py` | ERA5-Land download through the official CDS Python client. |
| `iaci/thresholds.py` | Temperature running quantiles and wind thresholds. |
| `iaci/climate.py` | Daily date alignment, threshold setup, and missing-day masks. |
| `iaci/indices.py` | Raw temperature, precipitation, dry-day, and wind indices. |
| `iaci/standardize.py` | Monthly/seasonal aggregation and 1961–1990 standardization. |
| `iaci/pipeline.py` | Date-checked component merge, IACI, and grid CSV batch output. |

The Python files are the primary implementation. A notebook can import these
functions for exploration without duplicating the formulas.

## Install

Use Python 3.10 or later. From this directory:

```text
python -m pip install -e .
```

For the existing NetCDF processing functions, install the `netcdf` extra.
For CDS downloads, install the `download` extra. Those services and packages
are not required for CSV-to-IACI calculations.

```text
python -m pip install -e ".[netcdf,download]"
```

The CDS downloader uses the token in your `.cdsapirc` file unless `user_key`
is supplied. You must accept the dataset's terms on the CDS website first.
The download wrapper uses the current CDS Python client, a valid
north-west-south-east global area default, and the actual days in each month.
These are operational adaptations; the IACI calculation formulas are retained.

## Calculate a grid point

```python
import pandas as pd

from iaci import climate_input, iaci_output, sea_input

daily = pd.read_csv("../rIACI/inst/extdata/test_output/36.7_-5.1.csv")
ci = climate_input(
    dates=daily["time"],
    tmax=daily["TMAX"],
    tmin=daily["TMIN"],
    prec=daily["PRCP"],
    wind=daily["WP"],
    base_range=(1961, 1990),
    n=7,  # Any positive integer; default is 5.
)

# Supply actual monthly sea-level observations covering the same dates.
sea = sea_input(dates=sea_dates, values=sea_values)
monthly = iaci_output(ci, sea, freq="monthly")
seasonal = iaci_output(ci, sea, freq="seasonal")
```

For many grid point files, use `output_all(sea, input_dir, output_dir,
freq="monthly", n=7)`. The matching `Date` labels across all six components
are required. The merge reports missing or duplicate dates rather than pairing
rows by position. Missing component **values** remain missing, as in the R
package; the final IACI is then missing for that date.

## Temperature window `n`

`n` controls the number of calendar positions used around each target day.
The default five-day result follows the original C++ window. February 29 is
one calendar position. At January 1 and December 31, observations come only
from available positions; the minimum-data denominator remains the nominal
window width, as in the original implementation. For even `n`, the extra
position lies after the target date. Values of 366 or more use the full
calendar. `min_base_data_fraction_present` retains the source C++ definition:
valid observations divided by nominal calendar positions in the window.

## Source formulas retained

- Daily wind power is `0.5 * 1.23 * (daily mean wind speed) ** 3` in the
  existing `netcdf_io.py` code.
- Temperature thresholds use R's type-8 quantile interpolation.
- Wind thresholds use the reference daily mean plus the 90th-percentile
  standard normal score times the reference sample standard deviation.
- `Rx5day` replaces missing precipitation with zero before the rolling sum.
- `CDD` measures annual dry spells (`precipitation < 1 mm`) and linearly
  interpolates the annual result to monthly dates before standardization.
- Standard deviations use the sample definition (`ddof=1`). The T90p/T10p
  denominator is the average of day and night component standard deviations.
- The seasonal temperature functions retain the original R implementation's
  use of the daytime series twice. The `t90p` helper also retains its original
  monthly behavior when passed `freq="annual"`. The original leap-year
  day-of-year mapping is retained for numerical comparability.
- Final `IACI = (T90p - T10p + Rx5day + CDD + W90p + Sea) / 6`.

## Verification and limits

Run `python -m unittest discover -s tests -v` here. The tests check variable
`n`, default window behavior, date-safe merging, missing-date handling, and
both monthly and seasonal calculations on the supplied grid point CSV.

This port has not yet been numerically compared with an R run. The downloaded
R test suite primarily checks file creation and column presence, and its
sea-level integration test supplies missing values. A trusted R reference
with observed sea-level input is needed for a complete parity comparison.

The NetCDF module is copied from the original package and requires optional
dependencies; the CSV calculation tests do not exercise it. CDS download
requires account access and is not covered by the local tests.
