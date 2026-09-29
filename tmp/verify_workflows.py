import ast
import json
import os
from pathlib import Path
import pandas as pd
import numpy as np

os.environ['MPLBACKEND'] = 'Agg'
root = Path(__file__).resolve().parents[1]
os.chdir(root)
for path in root.glob('*workflow.ipynb'):
    notebook = json.loads(path.read_text(encoding='utf-8'))
    for i, cell in enumerate(notebook['cells']):
        if cell['cell_type'] == 'code':
            ast.parse(''.join(cell['source']), filename=f'{path.name}:{i}')
print('All workflow cells parse.', flush=True)
nb = json.loads((root / 'dolnoslaskie_aci_workflow.ipynb').read_text(encoding='utf-8'))
ns = {}
for i in [1, 13]:
    exec(''.join(nb['cells'][i]['source']), ns)
grid = pd.read_csv(ns['GRID_FILE']).sort_values(['latitude', 'longitude']).reset_index(drop=True)
counts = pd.read_csv(ns['OUTPUT_DIR'] / 'dolnoslaskie_daily_cell_counts.csv')
assert counts[ns['CLIMATE_COLUMNS']].eq(len(grid)).all().all()
assert pd.DatetimeIndex(pd.to_datetime(counts['date'])).equals(ns['EXPECTED_DAYS'])
regional = pd.read_csv(ns['OUTPUT_DIR'] / 'dolnoslaskie_land_components_monthly.csv')
ns.update(grid=grid, land_wide=regional, QUALITY_READY=True)
# Reproduce running section 8 without section 7 or its globals.
ns.pop('METRICS', None)
exec(''.join(nb['cells'][22]['source']), ns)
assert ns['grid_seasonal'][['latitude', 'longitude']].drop_duplicates().shape[0] == len(grid)
assert not np.isinf(ns['grid_seasonal'][ns['METRICS']].to_numpy()).any()
print('Section 8 passed for all points without section 7.', flush=True)
import plotly.graph_objects as go
go.Figure.show = lambda self, *args, **kwargs: None
exec(''.join(nb['cells'][20]['source']), ns)
print('Section 7 exported charts.', flush=True)
