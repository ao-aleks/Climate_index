from pathlib import Path
p = Path('tmp/verify_all_regions.py')
s = p.read_text(encoding='utf-8').replace('results = []', 'manifest = [e for e in manifest if e["region"] in ("warminsko_mazurskie", "zachodniopomorskie")]\nresults = []')
s = s.replace("regional_workflow_smoke_v2", "new_regions_smoke")
exec(compile(s, str(p), 'exec'))
