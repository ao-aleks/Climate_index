import ast
import json
import os
from pathlib import Path
os.environ['MPLBACKEND'] = 'Agg'
import pandas as pd

nb = json.loads(Path('dolnoslaskie_aci_workflow.ipynb').read_text(encoding='utf-8'))
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        ast.parse(''.join(cell['source']))
ns = {}
exec(''.join(nb['cells'][1]['source']), ns)
ns.update(grid=pd.read_csv(ns['GRID_FILE']), land_wide=True, QUALITY_READY=True)
exec(''.join(nb['cells'][25]['source']), ns)
# Suppress notebook iframe output in a terminal.
source = ''.join(nb['cells'][26]['source']).replace('    display(HTML(', '    ignored_display(HTML(')
ns['ignored_display'] = lambda *args: None
exec(source, ns)
annual = ns['grid_annual']
assert annual[['latitude', 'longitude']].drop_duplicates().shape[0] == 259
assert not annual.Date.str.startswith('2026').any()
assert 'ANN' in ns['payload']['Rok']['1961']
assert 'ANN' not in ns['payload']['Rok']['2026']
assert set(v for row in ns['payload']['Dekada']['1961–1970']['ANN']['n']['ACI_land5'] for v in row if v is not None) == {10}
assert set(v for row in ns['payload']['Dekada']['2021–2026']['ANN']['n']['ACI_land5'] for v in row if v is not None) == {5}
print('Annual data, complete-year counts, static maps and interactive HTML verified.', flush=True)
