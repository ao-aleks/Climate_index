"""Offline end-to-end smoke run using synthetic hourly data, never production outputs."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import xarray as xr
os.environ['MPLBACKEND'] = 'Agg'
import matplotlib.pyplot as plt
import plotly.graph_objects as go

root = Path.cwd()
testroot = root / 'tmp/regional_workflow_smoke_v2'
testroot.mkdir(exist_ok=True)
manifest = json.loads((root/'tmp/regions_manifest.json').read_text(encoding='utf-8'))
manifest += [dict(region='mazowieckie',notebook='mazowieckie_aci_workflow.ipynb'),
             dict(region='pomorskie',notebook='pomorskie_independent_aci_workflow.ipynb')]
results = []

for entry in manifest:
    region = entry['region']
    nb = json.loads((root/entry['notebook']).read_text(encoding='utf-8'))
    for cell in nb['cells']:
        if cell['cell_type']=='code': ast.parse(''.join(cell['source']))
    ns = {}
    log = io.StringIO()
    def run(i):
        text = ''.join(nb['cells'][i]['source'])
        text = text.replace('EXPORT_BENCHMARK_MAPS = True', 'EXPORT_BENCHMARK_MAPS = False')
        text = text.replace('from IPython.display import HTML, display', 'from IPython.display import HTML\n    display = lambda *args: None')
        with contextlib.redirect_stdout(log):
            exec(compile(text, f'{entry["notebook"]}:cell{i}', 'exec'),ns)
    with patch.object(plt,'show',lambda:plt.close('all')), patch.object(go.Figure,'show',lambda *a,**kw:None):
        run(1)
        directory = testroot/region
        directory.mkdir(exist_ok=True)
        sample = pd.read_csv(ns['GRID_FILE']).sort_values(['latitude','longitude']).head(2)
        gridfile = directory/'grid.csv'
        sample.to_csv(gridfile,index=False)
        start,end = pd.Timestamp('1961-01-01'),pd.Timestamp('1965-12-31')
        ns.update(GRID_FILE=gridfile, DATA_DIR=directory/'data',RAW_DIR=directory/'data/arco_hourly',
                  DAILY_DIR=directory/'data/daily_grid',OUTPUT_DIR=directory/'output',
                  START=start,END=end,BASE_RANGE=(1961,1965), YEARS=range(1961,1966),DOWNLOAD_YEARS=range(1961,1966),
                  EXPECTED_DAYS=pd.date_range(start,end),EXPECTED_MONTHS=pd.period_range(start,end,freq='M').astype(str),
                  RUN_ARCO_DOWNLOAD=True, display=lambda *a:None)
        ns['OUTPUT_DIR'].mkdir(exist_ok=True)
        run(3)
        times=pd.date_range(start,end+pd.Timedelta(days=1),freq='h')
        lat=np.sort(sample.latitude.unique())[::-1]
        lon=np.sort(sample.longitude.unique())
        shape=(len(times),len(lat),len(lon))
        rng=np.random.default_rng(78)
        year_shift=(times.year.to_numpy()-1961)[:,None,None]
        temp=280+3*year_shift+rng.normal(0,7,shape)
        # All hours on dry days are zero; wet-day amounts vary by day and year.
        rain=np.repeat(rng.choice([0.,0.,0.,.0002,.0005,.001],size=(len(times)//24+1,len(lat),len(lon))),24,axis=0)[:len(times)]
        remote=xr.Dataset({v:(('time','latitude','longitude'), a) for v,a in
                           [('t2m',temp),('tp',rain),('u10',rng.normal(3,2,shape)+year_shift),('v10',rng.normal(1,2,shape))]},
                          coords={'time':times,'latitude':lat,'longitude':lon})
        with patch.object(xr,'open_zarr',return_value=remote) as opened, patch.dict(os.environ,{'CDS_API_KEY':'offline-fixture'}):
            run(5)
            # A fresh fixture run uses 3 stores, regardless of number of years.
            assert opened.call_count in (0,3)
        with patch.object(xr,'open_zarr',side_effect=AssertionError('Completed years must not download')):
            with contextlib.redirect_stdout(log): ns['prepare_daily_blocks'](download=True)
        run(9); run(11); run(13); run(14)
        assert ns['QUALITY_READY']
        if region=='pomorskie':
            ns['sea_harmonised']=pd.DataFrame({'Date':ns['EXPECTED_MONTHS'],'Value':rng.normal(size=len(ns['EXPECTED_MONTHS']))})
            run(17)
            point_i,map_i,html_i=25,28,29
        else:
            point_i,map_i,html_i=22,25,26
        run(point_i-2)  # component plots, season table
        run(point_i); run(map_i); run(html_i)
        assert ns['grid_annual'].shape[0]==10
        assert 'ANN' in ns['payload']['Rok']['1961']
        assert all(v==5 for row in ns['payload']['Dekada']['1961–1965']['ANN']['n'][ns['METRICS'][-1]] for v in row if v is not None)
        assert ns['map_path'].exists()
        results.append(dict(region=region,download='offline hourly fixture + cache reuse',
                            workflow='daily CSV, regional + point indices, annual + seasonal maps, HTML passed'))
    (directory/'verification.log').write_text(log.getvalue(),encoding='utf-8')
    print(region, 'PASS',flush=True)
(testroot/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'All {len(results)} regional workflows passed.',flush=True)
