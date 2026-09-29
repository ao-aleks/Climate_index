import ast
import json
import os
from pathlib import Path
os.environ['MPLBACKEND']='Agg'
import geopandas as gpd
import matplotlib.pyplot as plt
nb=json.loads(Path('pomeranian_aci_workflow.ipynb').read_text(encoding='utf-8'))
for c in nb['cells']:
    if c['cell_type']=='code': ast.parse(''.join(c['source']))
ns={}
exec(''.join(nb['cells'][1]['source']),ns)
nodes=[n for n in ast.parse(''.join(nb['cells'][32]['source'])).body if isinstance(n,ast.FunctionDef)]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'notebook','exec'),ns)
boundary=gpd.read_file('data/poland/boundary/poland_nuts2_2024.geojson').to_crs('EPSG:4326')
ns['pomorskie']=boundary.loc[boundary.NUTS_ID.eq('PL63')]
exec(''.join(nb['cells'][38]['source']),ns)
ns['ignore_display']=lambda *args:None
exec(''.join(nb['cells'][39]['source']).replace('display(HTML(', 'ignore_display(HTML('),ns)
assert 'ANN' in ns['payload']['Rok']['1961']
assert 'ANN' not in ns['payload']['Rok']['2026']
print('Original Pomeranian map passed on existing data.')
