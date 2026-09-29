"""Verify regional daily blocks before deleting their redundant hourly files."""
import ast
import hashlib
import json
import re
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
DATA = (ROOT / 'data/poland').resolve()
apply = '--apply' in sys.argv
report = []
for notebook in ROOT.glob('*workflow.ipynb'):
    nb = json.loads(notebook.read_text(encoding='utf-8'))
    sources = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
    if not any('def check_block(' in s for s in sources):
        continue
    ns = {'Path': Path, 'pd': pd, 'np': np, 'PROJECT_ROOT': ROOT}
    wanted = {'REGION','GRID_FILE','DATA_DIR','RAW_DIR','DAILY_DIR','START','END','CLIMATE_COLUMNS','PIPELINE_VERSION'}
    for node in ast.parse(sources[0]).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in wanted:
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<config>', 'exec'), ns)
    ns['grid'] = pd.read_csv(ns['GRID_FILE']).sort_values(['latitude','longitude']).reset_index(drop=True)
    ns['GRID_HASH'] = hashlib.sha256(ns['GRID_FILE'].read_bytes()).hexdigest()
    for s in sources:
        for node in ast.parse(s).body:
            if isinstance(node, ast.FunctionDef) and node.name in {'year_limits','check_block'}:
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<validation>', 'exec'), ns)
    raw_dir = ns['RAW_DIR'].resolve()
    assert raw_dir.is_relative_to(DATA) and raw_dir.name == 'arco_hourly'
    validated = {}
    entries = []
    for raw in sorted(raw_dir.glob('*.nc')):
        match = re.fullmatch(r'(\d{4})_arco(?:_before_repair_\d+_\d+_\d+)?(?:\.partial)?\.nc',raw.name)
        if not match:
            continue
        year = int(match[1])
        daily = ns['DAILY_DIR'] / f'{year}_daily.nc'
        if year not in validated:
            try:
                stat = daily.stat()
                if time.time() - stat.st_mtime < 120:
                    raise ValueError('Daily file recently modified; retained')
                with xr.open_dataset(daily) as ds:
                    ns['check_block'](ds, year, 'daily')
                    for variable in ns['CLIMATE_COLUMNS']:
                        if not np.isfinite(ds[variable].values).all():
                            raise ValueError(f'Daily data contains missing values: {variable}')
                    if bool((ds.TMAX < ds.TMIN).any()):
                        raise ValueError('Daily Tmax below Tmin')
                validated[year] = (True, stat.st_size, stat.st_mtime_ns)
            except Exception as exc:
                validated[year] = (False, str(exc))
        valid = validated[year]
        record = dict(region=ns['REGION'], hourly=str(raw), daily=str(daily), bytes=raw.stat().st_size)
        if not valid[0]:
            record.update(status='retained', reason=valid[1])
        elif time.time() - raw.stat().st_mtime < 120:
            record.update(status='retained', reason='Hourly file recently modified')
        else:
            resolved = raw.resolve()
            assert resolved.parent == raw_dir and resolved.is_relative_to(DATA) and not raw.is_symlink()
            stat = daily.stat()
            assert (stat.st_size,stat.st_mtime_ns) == valid[1:]
            record['status'] = 'deleted' if apply else 'eligible'
            if apply:
                raw.unlink()
        entries.append(record)
    report.extend(entries)
    print(ns['REGION'], {status:sum(r['bytes'] for r in entries if r['status']==status)/1024**3 for status in {r['status'] for r in entries}}, flush=True)
path = ROOT / 'tmp' / ('hourly_cleanup_applied.json' if apply else 'hourly_cleanup_audit.json')
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Report:',path,flush=True)
