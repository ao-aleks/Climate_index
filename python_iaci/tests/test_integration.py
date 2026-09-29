"""Run the complete index on one daily sample supplied with rIACI."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from iaci import climate_input, iaci_output, output_all, sea_input  # noqa: E402


class SampleGridPointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sample = PROJECT.parent / "rIACI" / "inst" / "extdata" / "test_output" / "36.7_-5.1.csv"
        cls.daily = pd.read_csv(sample)
        months = pd.period_range("1960-01", "2023-12", freq="M")
        cls.sea = sea_input(months.strftime("%Y-%m"), np.arange(len(months), dtype=float))
        cls.ci = climate_input(
            dates=cls.daily["time"], tmax=cls.daily["TMAX"],
            tmin=cls.daily["TMIN"], prec=cls.daily["PRCP"],
            wind=cls.daily["WP"], n=5,
        )

    def test_monthly_pipeline(self):
        result = iaci_output(self.ci, self.sea, "monthly")
        self.assertEqual(result["Date"].iloc[0], "1960-01")
        self.assertEqual(result["Date"].iloc[-1], "2023-12")
        self.assertEqual(len(result), 64 * 12)
        self.assertEqual(result["Date"].nunique(), len(result))
        self.assertTrue(result.loc[result["Date"] == "2000-07", "IACI"].notna().all())

    def test_seasonal_pipeline(self):
        result = iaci_output(self.ci, self.sea, "seasonal")
        self.assertEqual(result["Date"].iloc[0], "1960-DJF")
        self.assertEqual(result["Date"].iloc[-1], "2024-DJF")
        self.assertEqual(result["Date"].nunique(), len(result))

    def test_batch_output_accepts_nondefault_n(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input"
            source.mkdir()
            self.daily.to_csv(source / "sample.csv", index=False)
            written = output_all(self.sea, source, Path(directory) / "results", n=7)
            self.assertEqual(len(written), 1)
            result = pd.read_csv(written[0])
            self.assertEqual(result["Date"].iloc[0], "1961-01")
            self.assertEqual(result["Date"].iloc[-1], "2022-12")
            self.assertEqual(len(result), 62 * 12)


if __name__ == "__main__":
    unittest.main()
