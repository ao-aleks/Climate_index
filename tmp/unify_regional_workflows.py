"""Apply the checked Dolnoslaskie map cells without changing regional formulas."""
import copy
import json
from pathlib import Path

root = Path.cwd()
reference = json.loads((root / 'dolnoslaskie_aci_workflow.ipynb').read_text(encoding='utf-8'))
manifest = json.loads((root / 'tmp/regions_manifest.json').read_text(encoding='utf-8'))
manifest += [dict(region='mazowieckie', label='Mazowieckie', nuts=['PL91','PL92'], notebook='mazowieckie_aci_workflow.ipynb'),
             dict(region='pomorskie', label='Pomorskie', nuts='PL63', notebook='pomorskie_independent_aci_workflow.ipynb')]

def source(cell):
    return ''.join(cell['source'])

def setsource(cell, text):
    cell['source'] = text.splitlines(keepends=True)
    if cell['cell_type'] == 'code':
        cell['outputs'] = []
        cell['execution_count'] = None

for entry in manifest:
    region, label = entry['region'], entry['label']
    path = root / entry['notebook']
    doc = json.loads(path.read_text(encoding='utf-8'))
    pom = region == 'pomorskie'
    index = 'PomACI_land5' if pom else 'MazACI_land5' if region == 'mazowieckie' else 'ACI_land5'
    default = 'PomACI' if pom else index
    metrics = ['T90p','T10p_oriented','Rx5day','CDD','W90p',index] + (['Sea','PomACI'] if pom else [])
    labels = ['Wysokie temperatury — T90p','Niskie temperatury — −T10p','Opady — Rx5day',
              'Susza — CDD','Wiatr — W90p','Indeks land5'] + (['Poziom morza — Sea','Pełny indeks PomACI'] if pom else [])
    nuts = entry['nuts'] if isinstance(entry['nuts'],list) else [entry['nuts']]
    cfg = source(doc['cells'][1])
    cfg += '\n# Wspólna konfiguracja map regionalnych.\n'
    cfg += f'REGION_LABEL = {label!r}\nNUTS_CODES = {nuts!r}\nMETRICS = {metrics!r}\nLABELS = {labels!r}\n'
    setsource(doc['cells'][1], cfg)

    transformed = []
    for i in range(19,27):
        cell = copy.deepcopy(reference['cells'][i])
        s = source(cell).replace('dolnoslaskie', region).replace('Dolnośląskie', label).replace('ACI_land5', index)
        s = s.replace(f'    OUTPUT_DIR = PROJECT_ROOT / "output/poland/{region}"\n', '')
        s = s.replace(f'    GRID_CSV_DIR = PROJECT_ROOT / "data/poland/{region}/grid_csv"', '    GRID_CSV_DIR = DATA_DIR / "grid_csv"')
        # Definitions in each independent section work in an already-running kernel too.
        if '    METRICS = ' in s:
            lines = s.splitlines(keepends=True)
            for j, line in enumerate(lines):
                if line.startswith('    METRICS = '):
                    lines[j] = f'    METRICS = {metrics!r}\n'
                if line.startswith('    LABELS = '):
                    lines[j] = f'    LABELS = {labels!r}\n'
                    if j+1 < len(lines) and lines[j+1].startswith('              '):
                        lines[j+1] = ''
            s = ''.join(lines)
        if i == 20:
            s = s.replace('rows=6, cols=1', 'rows=len(METRICS), cols=1').replace('height=2100', 'height=350*len(METRICS)')
            if pom:
                s = s.replace('if land_wide is None', 'if globals().get("full_pomaci") is None')
                s = s.replace(f'    regional = pd.read_csv(OUTPUT_DIR / "{region}_land_components_monthly.csv")',
                              '    regional = land_wide.merge(full_pomaci[["Date", "Sea", "PomACI"]], on="Date", validate="one_to_one")')
                s = s.replace('counts[CLIMATE_COLUMNS].eq(len(grid))', 'counts[CLIMATE_COLUMNS].eq(int(availability.status.eq("used").sum()))')
        if i == 22:
            s = s.replace('    for i, point in enumerate(grid.itertuples(index=False)):',
                          '    map_grid = grid\n' + ('''    map_grid = availability.loc[availability.status.eq("used"), ["latitude", "longitude"]].copy()
    sea_for_cells = sea_component.rename(columns={"Value": "Sea"})[["Date", "Sea"]]
''' if pom else '') + '    for i, point in enumerate(map_grid.itertuples(index=False)):')
            if pom:
                s = s.replace('if land_wide is None', 'if globals().get("full_pomaci") is None')
                # Refresh marine data even when land component cache is reusable.
                s = s.replace('        seasonal = None', '''        local = local.drop(columns=["Sea", "PomACI"], errors="ignore").merge(
            sea_for_cells, on="Date", how="left", validate="one_to_one")
        if local.Sea.isna().any():
            raise ValueError("Niekompletna seria poziomu morza dla map.")
        local["PomACI"] = (5 * local["PomACI_land5"] + local["Sea"]) / 6
        tmp = target.with_suffix(".partial.csv")
        local.to_csv(tmp, index=False)
        tmp.replace(target)
        seasonal = None''')
        if i == 24:
            s = s.replace('PL51', ' + '.join(nuts))
            if pom:
                s = s.replace('stosujemy uzgodniony wariant pięcioskładnikowy', 'pokazujemy pełny sześcioskładnikowy PomACI i pomocniczy land5')
        if i == 25:
            if pom:
                s = s.replace('if land_wide is None', 'if globals().get("full_pomaci") is None')
            s = s.replace(f'    MAP_VARIABLE = "{index}"', f'    MAP_VARIABLE = "{default}"')
            s = s.replace('    for point in grid.itertuples(index=False):',
                          '    map_grid = grid\n' + ('    map_grid = availability.loc[availability.status.eq("used"), ["latitude", "longitude"]].copy()\n' if pom else '') + '    for point in map_grid.itertuples(index=False):')
            a = s.index(f'    {region} = boundary_source.loc[')
            b = s.index('    MAP_LIMITS, MAP_COLOURS', a)
            s = s[:a] + f'''    selected_boundary = boundary_source.loc[boundary_source.NUTS_ID.isin({nuts!r})].copy()
    if set(selected_boundary.NUTS_ID) != set({nuts!r}):
        raise ValueError("Brak właściwej granicy NUTS2.")
    {region} = gpd.GeoDataFrame(geometry=[selected_boundary.geometry.union_all()], crs="EPSG:4326")
''' + s[b:]
        if i == 26:
            if pom:
                s = s.replace('if land_wide is None', 'if globals().get("full_pomaci") is None')
            s = s.replace(f"el('metric').value='{index}'", f"el('metric').value='{default}'")
        setsource(cell, s)
        transformed.append(cell)
    if pom:
        # Keep sea calculation and validation sections intact, append shared maps.
        transformed[0]['source'] = ['## 8. Wykresy składników i wyniki sezonowe\n'] + transformed[0]['source'][1:]
        transformed[2]['source'] = ['## 9. Składniki i indeks osobno dla każdego punktu\n'] + transformed[2]['source'][1:]
        doc['cells'].extend(transformed)
        # Known ocean/no-data points may be absent, but only if all four variables
        # are empty for their entire hourly block. Unexpected gaps still stop.
        s = source(doc['cells'][5])
        a = s.index('                bad = {v:')
        b = s.index('                if bad:', a)
        s = s[:a] + '''                known_empty = np.array([(round(float(p.latitude),1), round(float(p.longitude),1))
                                        in KNOWN_EMPTY_POINTS for p in grid.itertuples(index=False)])
                wholly_empty = np.logical_and.reduce([
                    hourly[v].isnull().all("time").values for v in ["t2m", "tp", "u10", "v10"]])
                excluded = known_empty & wholly_empty
                bad = {v: int((~np.isfinite(hourly[v].isel(point=np.flatnonzero(~excluded)).values)).sum())
                       for v in ["t2m", "tp", "u10", "v10"]
                       if not np.isfinite(hourly[v].isel(point=np.flatnonzero(~excluded)).values).all()}
''' + s[b:]
        setsource(doc['cells'][5], s)
    else:
        doc['cells'][19:27] = transformed
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(region)

# The original Pomeranian notebook uses aggregate grid CSVs rather than per-cell
# caches. Give it the same map UI while retaining its marine and land5 columns.
path = root / 'pomeranian_aci_workflow.ipynb'
doc = json.loads(path.read_text(encoding='utf-8'))
setup = '''# Wspólna mapa dla oryginalnego pełnego PomACI oraz wariantu land5.
from IPython.display import display
END = pd.Timestamp("2026-04-30")
METRICS = ["PomACI_land5", "Sea", "PomACI"]
LABELS = ["Indeks land5", "Poziom morza — Sea", "Pełny indeks PomACI"]
map_monthly = pd.read_csv(OUTPUT_DIR / "pomerania_grid_PomACI_monthly.csv")
grid = map_monthly[["latitude", "longitude"]].drop_duplicates()
seasonal_parts, annual_parts = [], []
for (lat, lon), monthly in map_monthly.groupby(["latitude", "longitude"]):
    annual = complete_annual_means(monthly, METRICS)
    annual["latitude"], annual["longitude"] = lat, lon
    annual_parts.append(annual)
    seasonal = None
    for metric in METRICS:
        part = complete_seasonal_means(monthly.reset_index(drop=True), metric)
        seasonal = part if seasonal is None else seasonal.merge(part, on="Date", how="outer", validate="one_to_one")
    seasonal["latitude"], seasonal["longitude"] = lat, lon
    seasonal_parts.append(seasonal)
grid_seasonal = pd.concat(seasonal_parts, ignore_index=True)
grid_annual = pd.concat(annual_parts, ignore_index=True)
grid_periods = pd.concat([grid_seasonal, grid_annual], ignore_index=True)
grid_annual.to_csv(OUTPUT_DIR / "pomerania_grid_components_annual.csv", index=False)
'''
template = source(reference['cells'][25])
helper = template[:template.index('if land_wide is None')]
body = template[template.index('    MAP_LIMITS, MAP_COLOURS'):]
body = '\n'.join(line[4:] if line.startswith('    ') else line for line in body.splitlines())
body = body.replace('dolnoslaskie', 'pomorskie').replace('Dolnośląskie','Pomorskie').replace('ACI_land5','PomACI')
setup += '''MAP_PERIOD = "1961-MAM"
MAP_VARIABLE = "PomACI"
EXPORT_BENCHMARK_MAPS = False
BENCHMARK_YEARS = [1961,1971,1981,1991,2001,2011,2021,2025]
SEASONS = ["DJF","MAM","JJA","SON"]
'''
setsource(doc['cells'][38], helper+setup+body)
interactive = source(reference['cells'][26]).split('else:\n',1)[1]
interactive = '\n'.join(line[4:] if line.startswith('    ') else line for line in interactive.splitlines())
interactive = interactive.replace('dolnoslaskie','pomerania').replace('Dolnośląskie','Pomorskie').replace("el('metric').value='ACI_land5'", "el('metric').value='PomACI'")
cell = copy.deepcopy(reference['cells'][26])
setsource(cell, interactive)
doc['cells'].insert(39, cell)
path.write_text(json.dumps(doc,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
