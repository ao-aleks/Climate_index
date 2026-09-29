import ast,json
from pathlib import Path
old = '''            if not block_years:
                continue
            missing_raw ='''
new = '''            # Verified daily files are sufficient; hourly archives may be removed.
            block_years = [year for year in block_years
                           if not block_exists(DAILY_DIR / f"{year}_daily.nc", year, "daily")]
            if not block_years:
                continue
            missing_raw ='''
for path in Path('.').glob('*workflow.ipynb'):
    nb=json.loads(path.read_text(encoding='utf-8'))
    changed=False
    for cell in nb['cells']:
        source=''.join(cell['source'])
        if cell['cell_type']=='code' and 'def prepare_daily_blocks(' in source and old in source:
            source=source.replace(old,new,1)
            ast.parse(source)
            cell['source']=source.splitlines(keepends=True)
            changed=True
    if changed:
        temp=path.with_suffix('.ipynb.tmp')
        temp.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
        temp.replace(path)
        print(path)
p=Path('python_iaci/tests/test_regional_download.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace("self.assertIn(call(Path('raw/1961_arco.nc'), 1961, 'hourly'),", "self.assertNotIn(call(Path('raw/1961_arco.nc'), 1961, 'hourly'),")
p.write_text(s,encoding='utf-8')
