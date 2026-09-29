"""Check real regional inputs and consistent map functions without network access."""
import ast
import contextlib
import io
import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

def notebooks():
    for path in ROOT.glob('*workflow.ipynb'):
        nb=json.loads(path.read_text(encoding='utf-8'))
        if any('def prepare_daily_blocks(' in ''.join(c['source']) for c in nb['cells']):
            yield path, nb

def functions(nb):
    nodes=[]
    for cell in nb['cells']:
        if cell['cell_type']=='code':
            nodes.extend(n for n in ast.parse(''.join(cell['source'])).body
                         if isinstance(n,ast.FunctionDef) and n.name in
                         {'region_key','complete_annual_means','presentation_scale','prepare_daily_blocks'})
    ns={'pd':pd,'np':np,'unicodedata':__import__('unicodedata')}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'notebook','exec'),ns)
    return ns

class RegionalWorkflowsTests(unittest.TestCase):
    def test_real_grid_names_coordinates_and_boundaries_all_regions(self):
        boundaries=gpd.read_file(ROOT/'data/poland/boundary/poland_nuts2_2024.geojson')
        checked=0
        for path,nb in notebooks():
            with self.subTest(notebook=path.name):
                config={}
                for node in ast.parse(''.join(nb['cells'][1]['source'])).body:
                    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name):
                        if node.targets[0].id in {'REGION','NUTS_CODES'}:
                            config[node.targets[0].id]=ast.literal_eval(node.value)
                grid=pd.read_csv(ROOT/'data/poland/grid'/config['REGION']/'grid.csv')
                normalize=functions(nb)['region_key']
                self.assertTrue(grid.voivodeship.map(normalize).eq(normalize(config['REGION'])).all())
                self.assertFalse(grid[['latitude','longitude']].duplicated().any())
                self.assertTrue(np.allclose(grid[['latitude','longitude']]*10,np.round(grid[['latitude','longitude']]*10)))
                self.assertTrue(set(config['NUTS_CODES']).issubset(set(boundaries.NUTS_ID)))
                self.assertNotEqual(normalize(config['REGION']),normalize('wrong_region'))
                checked+=1
        self.assertEqual(checked,16)

    def test_shared_map_math_and_controls(self):
        frame=pd.DataFrame({'Date':pd.period_range('1961-01','1962-04',freq='M').astype(str),'index':np.arange(16.)})
        for path,nb in notebooks():
            with self.subTest(notebook=path.name):
                ns=functions(nb)
                annual=ns['complete_annual_means'](frame,['index'])
                self.assertEqual(annual.Date.tolist(),['1961-ANN'])
                self.assertEqual(annual['index'].tolist(),[5.5])
                limits,colours=ns['presentation_scale']([-2.,3.])
                green=next(p for p,c in colours if c=='#20c83a')
                self.assertAlmostEqual(limits[0]+green*(limits[1]-limits[0]),0.)
                html=next(''.join(c['source']) for c in nb['cells'] if 'const DATA=' in ''.join(c['source']))
                self.assertIn('<option value="ANN">Cały rok</option>',html)
                self.assertIn('map_data = grid_periods.copy()',html)

    def test_pomeranian_known_empty_points_only(self):
        import xarray as xr
        from unittest.mock import Mock
        nb=json.loads((ROOT/'pomorskie_independent_aci_workflow.ipynb').read_text(encoding='utf-8'))
        for case in ['known_all_empty','unknown_all_empty','known_partial']:
            with self.subTest(case=case):
                times=pd.date_range('1961-01-01',periods=25,freq='h')
                grid=pd.DataFrame({'latitude':[54.4,54.5],'longitude':[19.5,19.6]})
                values=np.ones((25,2,2))
                values[:,0,0]=np.nan
                ds=xr.Dataset({v:(('time','latitude','longitude'),values.copy()) for v in ['t2m','tp','u10','v10']},
                              coords={'time':times,'latitude':[54.4,54.5],'longitude':[19.5,19.6]})
                if case=='known_partial': ds['tp'][0,0,0]=1.
                ns=functions(nb)
                remote=Mock(open_zarr=Mock(return_value=ds),DataArray=xr.DataArray,merge=xr.merge)
                class Captured(Exception): pass
                def capture(*args): raise Captured()
                ns.update(DOWNLOAD_YEARS=[1961],DAILY_DIR=Path('daily'),RAW_DIR=Path('raw'),
                          block_exists=lambda *args:False,year_limits=lambda y:(times[0],times[0]),
                          os=Mock(environ={'CDS_API_KEY':'offline-fixture'}),STORES=[('offline',list(ds.data_vars))],
                          xr=remote,grid=grid,KNOWN_EMPTY_POINTS=set() if case=='unknown_all_empty' else {(54.4,19.5)},
                          stamp=lambda ds:ds,check_block=lambda *args:None,atomic_netcdf=capture)
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(Captured if case=='known_all_empty' else ValueError):
                    ns['prepare_daily_blocks'](download=True)

if __name__=='__main__': unittest.main()
