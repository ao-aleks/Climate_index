"""Extend the existing land5 workflow to the two remaining regional grids."""
import copy
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

root = Path(__file__).resolve().parents[1]
template = json.loads((root / 'podlaskie_aci_workflow.ipynb').read_text(encoding='utf-8'))
boundaries = gpd.read_file(root / 'data/poland/boundary/poland_nuts2_2024.geojson')
manifest_path = root / 'tmp/regions_manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
for region, label, nuts in [
    ('warminsko_mazurskie', 'Warmińsko-mazurskie', 'PL62'),
    ('zachodniopomorskie', 'Zachodniopomorskie', 'PL42'),
]:
    grid = pd.read_csv(root / 'data/poland/grid' / region / 'grid.csv')
    boundary = boundaries.loc[boundaries.NUTS_ID.eq(nuts)].to_crs('EPSG:4326').geometry.union_all()
    points = gpd.GeoSeries(gpd.points_from_xy(grid.longitude, grid.latitude), crs='EPSG:4326')
    inside = int(points.intersects(boundary).sum())
    assert inside == len(grid)
    notebook = copy.deepcopy(template)
    for cell in notebook['cells']:
        source = ''.join(cell['source'])
        source = source.replace('podlaskie', region).replace('Podlaskie', label).replace('PL84', nuts)
        source = source.replace('272 punkt', f'{len(grid)} punkt')
        source = source.replace('adaptacja dla regionów śródlądowych', 'wariant lądowy dla województwa')
        cell['source'] = source.splitlines(keepends=True)
        if cell['cell_type'] == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
    name = f'{region}_aci_workflow.ipynb'
    (root / name).write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    manifest = [entry for entry in manifest if entry['region'] != region]
    manifest.append(dict(region=region, label=label, grid_points=len(grid), inside_boundary=inside,
                         nuts=nuts, notebook=name))
    print(region, len(grid), 'points')
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
