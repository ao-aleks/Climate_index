import json
from pathlib import Path
for path in Path('.').glob('*workflow.ipynb'):
    nb=json.loads(path.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        s=''.join(cell['source'])
        if 'for year in YEARS:' in s and 'def prepare_daily_blocks' in s:
            s=s.replace('for year in YEARS:', 'for year in (DOWNLOAD_YEARS if "DOWNLOAD_YEARS" in globals() else YEARS):')
            old='''                bad = {v: int((~np.isfinite(hourly[v].values)).sum())
                       for v in ["t2m", "tp", "u10", "v10"]
                       if not np.isfinite(hourly[v].values).all()}
'''
            new='''                excluded = np.zeros(len(grid), dtype=bool)
                if "KNOWN_EMPTY_POINTS" in globals():
                    known = {(round(float(p.latitude), 1), round(float(p.longitude), 1))
                             for p in grid.itertuples(index=False)}
                    for i, p in enumerate(grid.itertuples(index=False)):
                        if (round(float(p.latitude), 1), round(float(p.longitude), 1)) in KNOWN_EMPTY_POINTS:
                            excluded[i] = all(hourly[v].isel(point=i).isnull().all().item()
                                              for v in ["t2m", "tp", "u10", "v10"])
                active_points = np.flatnonzero(~excluded)
                bad = {v: int((~np.isfinite(hourly[v].isel(point=active_points).values)).sum())
                       for v in ["t2m", "tp", "u10", "v10"]
                       if not np.isfinite(hourly[v].isel(point=active_points).values).all()}
'''
            s=s.replace(old,new)
            cell['source']=s.splitlines(keepends=True); cell['outputs']=[];cell['execution_count']=None
            break
    path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
