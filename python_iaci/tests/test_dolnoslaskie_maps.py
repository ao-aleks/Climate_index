import ast
import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

def functions():
    nb = json.loads((ROOT / 'dolnoslaskie_aci_workflow.ipynb').read_text(encoding='utf-8'))
    nodes = []
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            nodes.extend(n for n in ast.parse(''.join(cell['source'])).body
                         if isinstance(n, ast.FunctionDef) and n.name in
                         {'complete_annual_means', 'presentation_scale'})
    ns = {'pd': pd, 'np': np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'notebook', 'exec'), ns)
    return ns

class MapTests(unittest.TestCase):
    def test_calendar_year_requires_twelve_months_per_metric(self):
        frame = pd.DataFrame({'Date': pd.period_range('1961-01', '1962-04', freq='M').astype(str),
                              'ACI_land5': np.arange(16, dtype=float), 'CDD': np.ones(16)})
        frame.loc[2, 'CDD'] = np.nan
        result = functions()['complete_annual_means'](frame, ['ACI_land5', 'CDD'])
        self.assertEqual(result.Date.tolist(), ['1961-ANN'])
        self.assertEqual(result.ACI_land5.iloc[0], 5.5)
        self.assertTrue(pd.isna(result.CDD.iloc[0]))

    def test_duplicate_month_cannot_count_as_complete_year(self):
        frame = pd.DataFrame({'Date': ['1961-01'] * 12, 'ACI_land5': np.ones(12)})
        with self.assertRaises(ValueError):
            functions()['complete_annual_means'](frame, ['ACI_land5'])

    def test_reference_colours_keep_absolute_values_for_wider_data_range(self):
        limits, scale = functions()['presentation_scale']([-2, 3, np.nan])
        self.assertEqual(limits, [-2, 3])
        anchors = {colour: position for position, colour in scale[1:-1]}
        for value, colour in [(0, '#20c83a'), (.30, '#ffe000'), (.55, '#f49a00')]:
            self.assertAlmostEqual(limits[0] + anchors[colour] * (limits[1]-limits[0]), value)
        self.assertEqual(scale[0][0], 0)
        self.assertEqual(scale[-1][0], 1)

if __name__ == '__main__':
    unittest.main()
