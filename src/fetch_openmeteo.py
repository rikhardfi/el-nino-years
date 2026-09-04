"""Fetch ERA5 daily series (and hourly snow depth → daily mean) from Open-Meteo, 1940 onward.

Cache: data/raw/openmeteo/<id>_daily.csv and <id>_snow.csv. Calls are paced and retried with
back-off on HTTP 429 (Open-Meteo weights long requests heavily against its minute quota).
"""
import sys
import time
import pandas as pd
import requests
from config import OM_POINTS, RAW_OM, END_DATE

URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
              "precipitation_sum", "rain_sum", "snowfall_sum"]
START = "1940-01-01"
PACE = 20          # seconds between successful heavy calls
BACKOFF = [65, 130, 300, 600, 1800, 3600]


def get(params: dict) -> dict:
    for i, wait in enumerate(BACKOFF + [None]):
        try:
            r = requests.get(URL, params=params, timeout=600)
        except requests.RequestException as e:
            print("  network error, retrying:", e, flush=True)
            time.sleep(wait or 60)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 and wait:
            print(f"  429 rate-limited, sleeping {wait}s", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"Open-Meteo {r.status_code}: {r.text[:200]}")
    raise RuntimeError("Open-Meteo: gave up after back-off")


def fetch_daily(lat, lon) -> pd.DataFrame:
    j = get(dict(latitude=lat, longitude=lon, start_date=START, end_date=END_DATE,
                 daily=",".join(DAILY_VARS), timezone="UTC", models="era5"))
    d = j["daily"]
    df = pd.DataFrame({"date": pd.to_datetime(d["time"]), **{v: d[v] for v in DAILY_VARS}})
    df.attrs["elevation"] = j.get("elevation")
    return df


SNOW_CHUNK_YEARS = 10


def fetch_snow(pid, lat, lon) -> pd.DataFrame:
    """Hourly snow depth in 10-year chunks (cached per chunk) → daily mean in cm."""
    part_dir = RAW_OM / f"{pid}_snow_parts"
    part_dir.mkdir(exist_ok=True)
    end_year = int(END_DATE[:4])
    parts = []
    for y0 in range(int(START[:4]), end_year + 1, SNOW_CHUNK_YEARS):
        y1 = min(y0 + SNOW_CHUNK_YEARS - 1, end_year)
        pp = part_dir / f"{y0}_{y1}.csv"
        if not pp.exists():
            e = END_DATE if y1 == end_year else f"{y1}-12-31"
            j = get(dict(latitude=lat, longitude=lon, start_date=f"{y0}-01-01", end_date=e,
                         hourly="snow_depth", timezone="UTC", models="era5"))
            h = j["hourly"]
            s = pd.Series(h["snow_depth"], index=pd.to_datetime(h["time"]), dtype="float")
            d = s.resample("D").mean().mul(100.0).rename("snow_depth_cm").reset_index().rename(columns={"index": "date"})
            d.to_csv(pp, index=False, float_format="%.2f")
            time.sleep(PACE)
        parts.append(pd.read_csv(pp, parse_dates=["date"]))
    return pd.concat(parts, ignore_index=True).drop_duplicates("date").sort_values("date")


def main(only=None):
    RAW_OM.mkdir(parents=True, exist_ok=True)
    ids = [only] if only else list(OM_POINTS)
    for pid in ids:
        name, cc, lat, lon = OM_POINTS[pid]
        p_daily, p_snow = RAW_OM / f"{pid}_daily.csv", RAW_OM / f"{pid}_snow.csv"
        if not p_daily.exists():
            t = time.time()
            df = fetch_daily(lat, lon)
            df.to_csv(p_daily, index=False)
            print(f"{name} ({cc}) daily: {len(df)} days, elev {df.attrs.get('elevation')} m [{time.time()-t:.0f}s]", flush=True)
            time.sleep(PACE)
        else:
            print(f"{name} ({cc}) daily: cached", flush=True)
    for pid in ids:
        name, cc, lat, lon = OM_POINTS[pid]
        p_snow = RAW_OM / f"{pid}_snow.csv"
        if pid.startswith("fi_"):
            continue    # Finland: snow depth comes from FMI stations
        if not p_snow.exists():
            t = time.time()
            df = fetch_snow(pid, lat, lon)
            df.to_csv(p_snow, index=False)
            print(f"{name} ({cc}) snow: {len(df)} days [{time.time()-t:.0f}s]", flush=True)
            time.sleep(PACE)
        else:
            print(f"{name} ({cc}) snow: cached", flush=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
