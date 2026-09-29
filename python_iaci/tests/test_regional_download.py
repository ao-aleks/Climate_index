"""Offline regression checks for annual ARCO selection and cache reuse."""
import ast
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, call

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]


def downloader_namespace(path):
    nb = json.loads(path.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        text = ''.join(cell['source'])
        if 'def prepare_daily_blocks(' in text:
            node = next(n for n in ast.parse(text).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'prepare_daily_blocks')
            ns = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), ns)
            return ns


class RegionalDownloadTests(unittest.TestCase):
    def test_all_regional_downloaders_reuse_complete_daily_cache(self):
        checked = 0
        for path in ROOT.glob('*workflow.ipynb'):
            ns = downloader_namespace(path)
            if ns is None:
                continue
            with self.subTest(notebook=path.name):
                ns.update(YEARS=[1961], DOWNLOAD_YEARS=[1961],
                          DAILY_DIR=Path('daily'), RAW_DIR=Path('raw'),
                          block_exists=Mock(return_value=True))
                # No token, network client or data conversion globals supplied.
                ns['prepare_daily_blocks'](download=True)
                self.assertIn(call(Path('daily/1961_daily.nc'), 1961, 'daily'),
                              ns['block_exists'].call_args_list)
                self.assertNotIn(call(Path('raw/1961_arco.nc'), 1961, 'hourly'),
                              ns['block_exists'].call_args_list)
                checked += 1
        self.assertEqual(checked, 16)

    def test_rectangular_read_matches_paired_selection_in_both_axis_orders(self):
        first, last = pd.Timestamp('1961-01-01'), pd.Timestamp('1961-01-02')
        times = pd.date_range(first, last + pd.Timedelta(days=1), freq='h')
        grid = pd.DataFrame({'latitude': [50.1, 50.2], 'longitude': [16.1, 16.3]})
        for descending in [False, True]:
            lat = np.array([50., 50.1, 50.2, 50.3])
            if descending:
                lat = lat[::-1]
            shape = (len(times), 4, 5)
            ds = xr.Dataset({v: (('time', 'latitude', 'longitude'),
                                np.arange(np.prod(shape)).reshape(shape) + i)
                             for i, v in enumerate(['t2m', 'tp', 'u10', 'v10'])},
                            coords={'time': times, 'latitude': lat,
                                    'longitude': [16., 16.1, 16.2, 16.3, 16.4]})
            expected = ds.sel(latitude=xr.DataArray(grid.latitude.to_numpy(), dims='point'),
                              longitude=xr.DataArray(grid.longitude.to_numpy(), dims='point'),
                              method='nearest', tolerance=1e-5)
            ns = downloader_namespace(ROOT / 'dolnoslaskie_aci_workflow.ipynb')
            saved = []
            remote = Mock()
            remote.open_zarr.return_value = ds
            remote.DataArray = xr.DataArray
            remote.merge = xr.merge
            # Capture the hourly dataset and stop before disk-based daily conversion.
            class Captured(Exception):
                pass
            def capture(data, path):
                saved.append(data)
                raise Captured()
            ns.update(YEARS=[1961], DAILY_DIR=Path('daily'), RAW_DIR=Path('raw'),
                      block_exists=lambda *args: False, year_limits=lambda year: (first, last),
                      os=Mock(environ={'CDS_API_KEY': 'test-only'}),
                      STORES=[('offline', list(ds.data_vars))], xr=remote, pd=pd, np=np,
                      grid=grid, stamp=lambda data: data, check_block=lambda *args: None,
                      atomic_netcdf=capture)
            with self.assertRaises(Captured):
                ns['prepare_daily_blocks'](download=True)
            xr.testing.assert_equal(saved[0], expected)


if __name__ == '__main__':
    unittest.main()

