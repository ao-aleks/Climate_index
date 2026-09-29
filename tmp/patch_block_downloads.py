import json
from pathlib import Path

root = Path.cwd()
function = '''def prepare_daily_blocks(download=False):
    """Download ARCO in decade-sized blocks, then split and process locally."""
    token = None
    years = list(DOWNLOAD_YEARS if "DOWNLOAD_YEARS" in globals() else YEARS)
    try:
        for block_start in range(min(years), max(years) + 1, 10):
            block_years = [year for year in years if block_start <= year < block_start + 10]
            if not block_years:
                continue
            missing_raw = [year for year in block_years
                           if not block_exists(RAW_DIR / f"{year}_arco.nc", year, "hourly")]
            if missing_raw:
                if not download:
                    continue
                token = os.environ.get("CDS_API_KEY") or getpass("Token CDS (ukryty): ")
                if not token.strip():
                    raise ValueError("Nie podano tokenu CDS.")
                block_first = year_limits(min(block_years))[0]
                block_last = year_limits(max(block_years))[1]
                groups = []
                for url, variables in STORES:
                    last_error = None
                    for attempt in range(1, 4):
                        source = None
                        try:
                            source = xr.open_zarr(url, consolidated=True, chunks={},
                                storage_options={"headers": {"Authorization": f"Bearer {token}"}})
                            low, high = grid.latitude.min() - 0.05, grid.latitude.max() + 0.05
                            lon_low, lon_high = grid.longitude.min() - 0.05, grid.longitude.max() + 0.05
                            selection = {"time": slice(block_first, block_last + pd.Timedelta(days=1))}
                            selection["latitude"] = (slice(low, high) if source.indexes["latitude"].is_monotonic_increasing
                                                      else slice(high, low))
                            selection["longitude"] = (slice(lon_low, lon_high) if source.indexes["longitude"].is_monotonic_increasing
                                                       else slice(lon_high, lon_low))
                            boxed = source[variables].sel(**selection).compute()
                            groups.append(boxed.sel(
                                latitude=xr.DataArray(grid.latitude.to_numpy(), dims="point"),
                                longitude=xr.DataArray(grid.longitude.to_numpy(), dims="point"),
                                method="nearest", tolerance=1e-5,
                            ))
                            del boxed
                            break
                        except Exception as exc:
                            last_error = exc
                            print(f"Blok {block_start}–{block_start + 9}: próba {attempt}/3 nieudana dla {variables}: {exc}", flush=True)
                            if attempt == 3:
                                raise RuntimeError(f"Blok {block_start}–{block_start + 9}: nie udało się pobrać {variables}") from last_error
                        finally:
                            if source is not None:
                                source.close()
                block = stamp(xr.merge(groups, join="exact"))
                excluded = np.zeros(len(grid), dtype=bool)
                if "KNOWN_EMPTY_POINTS" in globals():
                    for i, point in enumerate(grid.itertuples(index=False)):
                        key = (round(float(point.latitude), 1), round(float(point.longitude), 1))
                        if key in KNOWN_EMPTY_POINTS:
                            excluded[i] = all(block[v].isel(point=i).isnull().all().item()
                                              for v in ["t2m", "tp", "u10", "v10"])
                active = np.flatnonzero(~excluded)
                bad = {v: int((~np.isfinite(block[v].isel(point=active).values)).sum())
                       for v in ["t2m", "tp", "u10", "v10"]
                       if not np.isfinite(block[v].isel(point=active).values).all()}
                if bad:
                    raise ValueError(f"Blok {block_start}–{block_start + 9}: ARCO zwróciło braki {bad}; blok nie został zapisany.")
                for year in block_years:
                    first, last = year_limits(year)
                    yearly = stamp(block.sel(time=slice(first, last + pd.Timedelta(days=1))))
                    check_block(yearly, year, "hourly")
                    atomic_netcdf(yearly, RAW_DIR / f"{year}_arco.nc")
                print(f"Blok {block_start}–{block_start + 9}: pobrano i rozdzielono lokalnie", flush=True)
            for year in block_years:
                daily_path = DAILY_DIR / f"{year}_daily.nc"
                if block_exists(daily_path, year, "daily"):
                    print(year, "— gotowe dane dzienne", flush=True)
                    continue
                first, last = year_limits(year)
                with xr.open_dataset(RAW_DIR / f"{year}_arco.nc") as hourly:
                    check_block(hourly, year, "hourly")
                    daily = stamp(daily_from_hourly(hourly, first, last))
                    check_block(daily, year, "daily")
                    atomic_netcdf(daily, daily_path)
                print(year, "— zapisano dane dzienne", flush=True)
    finally:
        token = None

'''
for path in root.glob('*workflow.ipynb'):
    if path.name == 'pomeranian_aci_workflow.ipynb':
        continue
    nb=json.loads(path.read_text(encoding='utf-8'))
    changed=False
    for cell in nb['cells']:
        text=''.join(cell['source'])
        if 'def prepare_daily_blocks(' not in text:
            continue
        a=text.index('def prepare_daily_blocks(')
        b=text.index('\nprepare_daily_blocks(download=',a)
        cell['source']=(text[:a]+function+text[b:]).splitlines(keepends=True)
        cell['outputs']=[];cell['execution_count']=None
        changed=True;break
    if changed:
        path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
        print(path.name)
