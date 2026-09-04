"""Fetch GHCN-Daily station files from NOAA NCEI (public, no key).

Cache: data/raw/ghcn/<id>.csv with date, tmean, tmax, tmin, precip, snow_depth (cm).
tmean = TAVG when reported, else (TMAX + TMIN) / 2. Values with a quality flag are dropped.
Station coordinates are read from ghcnd-stations.txt (cached once).
"""
import gzip
import io
import sys
import time
import pandas as pd
import requests
from config import GHCN_STATIONS, RAW_GHCN, GHCN_STATIONS_URL

BY_STATION = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/{id}.csv.gz"
COLS = ["id", "date", "elem", "value", "mflag", "qflag", "sflag", "obstime"]


def station_meta() -> pd.DataFrame:
    p = RAW_GHCN / "ghcnd-stations.txt"
    if not p.exists():
        p.write_text(requests.get(GHCN_STATIONS_URL, timeout=120).text)
    st = pd.read_fwf(p, widths=[11, 9, 10, 7, 3, 31, 4, 4, 6], header=None,
                     names=["id", "lat", "lon", "elev", "state", "name", "gsn", "hcn", "wmo"])
    return st.set_index("id")


def fetch_station(sid: str) -> pd.DataFrame:
    r = requests.get(BY_STATION.format(id=sid), timeout=300)
    r.raise_for_status()
    raw = pd.read_csv(io.BytesIO(gzip.decompress(r.content)), header=None, names=COLS,
                      dtype={"date": str, "qflag": str, "mflag": str, "sflag": str})
    raw = raw[raw.elem.isin(["TMAX", "TMIN", "TAVG", "PRCP", "SNWD"]) & raw.qflag.isna()]
    wide = raw.pivot_table(index="date", columns="elem", values="value", aggfunc="first")
    wide.index = pd.to_datetime(wide.index, format="%Y%m%d")
    df = pd.DataFrame(index=wide.index)
    for src, dst in [("TMAX", "tmax"), ("TMIN", "tmin"), ("TAVG", "tavg")]:
        df[dst] = wide[src] / 10.0 if src in wide else pd.NA
    df["precip"] = wide["PRCP"] / 10.0 if "PRCP" in wide else pd.NA
    df["snow_depth"] = wide["SNWD"] / 10.0 if "SNWD" in wide else pd.NA     # mm → cm
    df = df.apply(pd.to_numeric, errors="coerce")
    df["tmean"] = df["tavg"].where(df["tavg"].notna(), (df["tmax"] + df["tmin"]) / 2)
    df = df.drop(columns="tavg").reset_index().rename(columns={"index": "date"})
    return df[["date", "tmean", "tmax", "tmin", "precip", "snow_depth"]]


def main():
    RAW_GHCN.mkdir(parents=True, exist_ok=True)
    meta = station_meta()
    rows = []
    for sid, (name, cc) in GHCN_STATIONS.items():
        p = RAW_GHCN / f"{sid}.csv"
        if not p.exists():
            df = fetch_station(sid)
            df.to_csv(p, index=False, float_format="%.1f")
            time.sleep(0.5)
        else:
            df = pd.read_csv(p, parse_dates=["date"])
        m = meta.loc[sid]
        yrs = df["date"].dt.year
        rows.append(dict(id=sid, name=name, country=cc, lat=m.lat, lon=m.lon, elev=m.elev,
                         first=yrs.min(), last=yrs.max(), n_tmean=int(df.tmean.notna().sum()),
                         n_precip=int(df.precip.notna().sum()), n_snow=int(df.snow_depth.notna().sum())))
        print(f"{name} ({sid}, {cc}): {yrs.min()}–{yrs.max()}, tmean n={rows[-1]['n_tmean']}, "
              f"precip n={rows[-1]['n_precip']}, snow n={rows[-1]['n_snow']}", flush=True)
    pd.DataFrame(rows).to_csv(RAW_GHCN / "stations.csv", index=False)


if __name__ == "__main__":
    sys.exit(main())
