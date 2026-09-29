import json
from pathlib import Path

root=Path.cwd()
for path in root.glob('*workflow.ipynb'):
    nb=json.loads(path.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        text=''.join(cell['source'])
        if 'def prepare_daily_blocks(' not in text:
            continue
        a=text.index('def prepare_daily_blocks(')
        b=text.index('\nprepare_daily_blocks(download=',a)
        fn='''def prepare_daily_blocks(download=False):
    """Build annual files with retryable, bounded ARCO reads.

    A source is opened for one year only. This avoids stale aiohttp streams
    after a long run; incomplete HTTP responses are retried from a clean
    client and never become cache files.
    """
    token = None
    try:
        for year in YEARS:
            daily_path = DAILY_DIR / f"{year}_daily.nc"
            raw_path = RAW_DIR / f"{year}_arco.nc"
            if block_exists(daily_path, year, "daily"):
                print(year, "— gotowe dane dzienne", flush=True)
                continue
            first, last = year_limits(year)
            if not block_exists(raw_path, year, "hourly"):
                if not download:
                    continue
                token = os.environ.get("CDS_API_KEY") or getpass("Token CDS (ukryty): ")
                if not token.strip():
                    raise ValueError("Nie podano tokenu CDS.")
                groups = []
                for url, variables in STORES:
                    low = grid.latitude.min() - 0.05
                    high = grid.latitude.max() + 0.05
                    lon_low = grid.longitude.min() - 0.05
                    lon_high = grid.longitude.max() + 0.05
                    last_error = None
                    for attempt in range(1, 4):
                        source = None
                        try:
                            source = xr.open_zarr(url, consolidated=True, chunks={},
                                storage_options={"headers": {"Authorization": f"Bearer {token}"}})
                            selection = {"time": slice(first, last + pd.Timedelta(days=1))}
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
                            print(f"{year}: ARCO próba {attempt}/3 nieudana dla {variables}: {exc}", flush=True)
                            if attempt == 3:
                                raise RuntimeError(f"{year}: nie udało się pobrać {variables} po 3 próbach") from last_error
                        finally:
                            if source is not None:
                                source.close()
                print(year, "— pobieranie danych godzinowych zakończone", flush=True)
                hourly = stamp(xr.merge(groups, join="exact"))
                check_block(hourly, year, "hourly")
                bad = {v: int((~np.isfinite(hourly[v].values)).sum())
                       for v in ["t2m", "tp", "u10", "v10"]
                       if not np.isfinite(hourly[v].values).all()}
                if bad:
                    raise ValueError(f"{year}: ARCO zwróciło braki {bad}. Nie zapisano roku; ponów ten rok.")
                atomic_netcdf(hourly, raw_path)
            with xr.open_dataset(raw_path) as hourly:
                check_block(hourly, year, "hourly")
                daily = stamp(daily_from_hourly(hourly, first, last))
                check_block(daily, year, "daily")
                atomic_netcdf(daily, daily_path)
            print(year, "— zapisano dane dzienne", flush=True)
    finally:
        token = None

'''
        cell['source']=(text[:a]+fn+text[b:]).splitlines(keepends=True)
        cell['outputs']=[]; cell['execution_count']=None
        break
    path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
