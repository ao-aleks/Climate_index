"""Numerical checks for calculations defined in the Pomeranian notebook."""

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python_iaci"))
from iaci import climate_input  # noqa: E402


def notebook_function(name):
    notebook = json.loads((ROOT / "pomeranian_aci_workflow.ipynb").read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                namespace = {"np": np, "pd": pd, "CLIMATE_COLUMNS": ["TMAX", "TMIN", "PRCP", "WP"]}
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / "pomeranian_aci_workflow.ipynb"), "exec"), namespace)
                return namespace[name]
    raise AssertionError(f"Notebook function {name} was not found.")


class PomeranianNotebookTests(unittest.TestCase):
    def test_psmsl_reader_converts_decimal_months_and_missing_sentinel(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "station.rlrdata"
            source.write_text(
                " 1993.0417; 7000; 0; 000\n"
                " 1993.1250; -99999; 0; 000\n",
                encoding="utf-8",
            )
            result = notebook_function("read_psmsl_monthly")(source, "Station_mm")
            self.assertEqual(result["Date"].tolist(), ["1993-01", "1993-02"])
            self.assertEqual(result.loc[0, "Station_mm"], 7000)
            self.assertTrue(np.isnan(result.loc[1, "Station_mm"]))

    def test_sea_harmonisation_uses_calendar_month_offsets(self):
        dates = pd.period_range("1993-01", "2000-12", freq="M").astype(str)
        month = pd.Series(pd.PeriodIndex(dates, freq="M").month, dtype=float)
        copernicus = pd.DataFrame({"Date": dates, "Value": month})
        psmsl = pd.DataFrame({
            "Date": dates[:84],
            "Value": month.iloc[:84].to_numpy() + 100 + month.iloc[:84].to_numpy(),
        })

        harmonised, adjusted, offsets, overlap = notebook_function("harmonise_sea_level")(
            psmsl, copernicus
        )

        self.assertEqual(len(overlap), 84)
        self.assertEqual(offsets["offset_mm"].tolist(), [100 + m for m in range(1, 13)])
        january_2000 = harmonised.loc[harmonised["Date"].eq("2000-01"), "Value"].item()
        self.assertEqual(january_2000, 102)
        self.assertEqual(adjusted.loc[adjusted["Date"].eq("2000-01"), "offset_mm"].item(), 101)

    def test_monthly_cdd_is_max_run_over_calendar_days(self):
        dates = pd.date_range("1961-01-01", "1961-02-28")
        rainfall = np.full(len(dates), 2.0)
        rainfall[:3] = 0
        rainfall[9:14] = 0
        ci = climate_input(dates=dates, prec=rainfall, base_range=(1961, 1961))
        result = notebook_function("pomeranian_monthly_cdd_proportion")(ci)
        self.assertAlmostEqual(result.loc[0, "Value"], 5 / 31)
        self.assertEqual(result.loc[1, "Value"], 0)

    def test_monthly_cdd_obeys_missing_day_mask(self):
        dates = pd.date_range("1961-01-01", "1961-01-31")
        rainfall = np.full(len(dates), 2.0)
        rainfall[:4] = np.nan
        ci = climate_input(dates=dates, prec=rainfall, base_range=(1961, 1961))
        result = notebook_function("pomeranian_monthly_cdd_proportion")(ci)
        self.assertTrue(np.isnan(result.loc[0, "Value"]))

    def test_complete_winter_uses_december_of_previous_year(self):
        monthly = pd.DataFrame({
            "Date": ["1960-12", "1961-01", "1961-02", "1961-03"],
            "Index": [1.0, 2.0, 3.0, 4.0],
        })
        result = notebook_function("complete_seasonal_means")(monthly, "Index")
        self.assertEqual(result.to_dict("records"), [{"Date": "1961-DJF", "Index": 2.0}])

    def test_regional_value_is_mean_of_cell_daily_values(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            base = {"time": ["1961-01-01", "1961-01-02"]}
            pd.DataFrame({**base, "TMAX": [10, 12], "TMIN": [0, 2], "PRCP": [1, 3], "WP": [4, 6]}).to_csv(folder / "54.0_18.0.csv", index=False)
            pd.DataFrame({**base, "TMAX": [20, 22], "TMIN": [4, 6], "PRCP": [5, 7], "WP": [8, 10]}).to_csv(folder / "54.1_18.1.csv", index=False)
            selected = pd.DataFrame({"latitude": [54.0, 54.1], "longitude": [18.0, 18.1]})
            calendar = pd.date_range("1961-01-01", "1961-01-02")
            regional, coverage = notebook_function("aggregate_selected_cells")(selected, folder, calendar)
            self.assertEqual(regional["TMAX"].tolist(), [15.0, 17.0])
            self.assertEqual(regional["PRCP"].tolist(), [3.0, 5.0])
            self.assertTrue((coverage == 1).all().all())


if __name__ == "__main__":
    unittest.main()
