"""Focused numerical and alignment checks for the Python port."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iaci import climate_input, merge_components, temperature_quantiles  # noqa: E402


class ThresholdTests(unittest.TestCase):
    def test_n_changes_the_full_window(self):
        dates = pd.date_range("1961-01-01", "1961-01-09")
        values = pd.Series(np.arange(1, 10, dtype=float), index=dates)
        q1 = temperature_quantiles(values, (1961, 1961), n=1, probabilities=(0.5,))
        q5 = temperature_quantiles(values, (1961, 1961), n=5, probabilities=(0.5,))
        jan1 = lambda frame: frame.set_index("month_day").loc["01-01", "Q50.0"]
        self.assertEqual(jan1(q1), 1)
        self.assertEqual(jan1(q5), 2)

    def test_default_window_uses_five_calendar_positions(self):
        dates = pd.date_range("1961-01-01", "1961-01-09")
        values = pd.Series(np.arange(1, 10, dtype=float), index=dates)
        q = temperature_quantiles(values, (1961, 1961), n=5, probabilities=(0.5,))
        self.assertEqual(q.set_index("month_day").loc["01-05", "Q50.0"], 5)

    def test_even_window_and_invalid_n(self):
        dates = pd.date_range("1961-01-01", "1961-01-04")
        values = pd.Series([1., 2., 3., 4.], index=dates)
        q = temperature_quantiles(values, (1961, 1961), n=2, probabilities=(0.5,))
        self.assertEqual(q.set_index("month_day").loc["01-01", "Q50.0"], 1.5)
        with self.assertRaises(ValueError):
            temperature_quantiles(values, (1961, 1961), n=0)

    def test_leap_day_is_a_calendar_position(self):
        dates = pd.date_range("1964-02-27", "1964-03-02")
        values = pd.Series([1., 2., 3., 4., 5.], index=dates)
        q = temperature_quantiles(values, (1964, 1964), n=5, probabilities=(0.5,))
        self.assertEqual(q.set_index("month_day").loc["02-29", "Q50.0"], 2.5)

    def test_boundary_completeness_uses_nominal_window_width(self):
        dates = pd.date_range("1961-01-01", "1961-01-05")
        values = pd.Series([1., np.nan, np.nan, np.nan, np.nan], index=dates)
        q = temperature_quantiles(
            values, (1961, 1961), n=5, probabilities=(0.5,), min_fraction=0.3,
        )
        self.assertTrue(np.isnan(q.set_index("month_day").loc["01-01", "Q50.0"]))


class MergeTests(unittest.TestCase):
    def test_merge_uses_dates_not_row_positions(self):
        a = pd.DataFrame({"Date": ["1961-01", "1961-02"], "Value": [1, 2]})
        b = pd.DataFrame({"Date": ["1961-02", "1961-01"], "Value": [20, 10]})
        merged = merge_components({"A": a, "B": b})
        self.assertEqual(merged["B"].tolist(), [10, 20])

    def test_merge_rejects_missing_and_duplicate_dates(self):
        a = pd.DataFrame({"Date": ["1961-01", "1961-02"], "Value": [1, 2]})
        missing = pd.DataFrame({"Date": ["1961-01"], "Value": [3]})
        repeated = pd.DataFrame({"Date": ["1961-01", "1961-01"], "Value": [3, 4]})
        with self.assertRaisesRegex(ValueError, "dates differ"):
            merge_components({"A": a, "B": missing})
        with self.assertRaisesRegex(ValueError, "duplicate Date"):
            merge_components({"A": a, "B": repeated})
        other_dates = pd.DataFrame({"Date": ["1961-01", "1961-03"], "Value": [3, 4]})
        with self.assertRaisesRegex(ValueError, "dates differ"):
            merge_components({"A": a, "B": other_dates})


class ClimateInputTests(unittest.TestCase):
    def test_fills_missing_dates_and_marks_month(self):
        ci = climate_input(
            dates=["1961-01-01", "1961-01-03"], tmax=[1, 3],
            base_range=(1961, 1961), n=3,
        )
        self.assertEqual(len(ci.dates), 3)
        self.assertTrue(np.isnan(ci.data["tmax"].iloc[1]))
        self.assertEqual(ci.na_masks["monthly"]["tmax"].loc["1961-01"], 1)


if __name__ == "__main__":
    unittest.main()
