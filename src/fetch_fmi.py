"""Fetch FMI daily observations (multipointcoverage), one calendar year per request.

Cache: data/raw/fmi/<fmisid>.csv with columns date, tday, tmax, tmin, rrday, snow.
Re-running only fetches years not yet cached (the current year is always refreshed).
rrday / snow of -1 mean "none" and are converted to 0.
"""
import re
import sys
import time
import datetime as dt
import pandas as pd
import requests
from config import FMI_STATIONS, FMI_PARAMS, RAW_FMI, END_DATE

BASE = ("https://opendata.fmi.fi/wfs?service=WFS&version=2.0.0&request=getFeature"
        "&storedquery_id=fmi::observations::weather::daily::multipointcoverage")
NUM = re.compile(r"<gml:doubleOrNilReasonTupleList>(.*?)</gml:doubleOrNilReasonTupleList>", re.S)
POS = re.compile(r"<gmlcov:positions>(.*?)</gmlcov:positions>", re.S)
FIELDS = re.compile(r'<swe:field name="(\w+)"')


def fetch_year(fmisid: int, year: int) -> pd.DataFrame:
    end = min(dt.date(year, 12, 31), dt.date.fromisoformat(END_DATE))
    url = (f"{BASE}&fmisid={fmisid}&starttime={year}-01-01T00:00:00Z"
           f"&endtime={end}T00:00:00Z&parameters={','.join(FMI_PARAMS)}")
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"FMI request failed {fmisid} {year}")
    txt = r.text
    m_num, m_pos = NUM.search(txt), POS.search(txt)
    if not m_num or not m_pos:
        return pd.DataFrame(columns=["date", *FMI_PARAMS])
    fields = FIELDS.findall(txt)
    vals = m_num.group(1).split()
    pos = m_pos.group(1).split()
    epochs = [int(pos[i]) for i in range(2, len(pos), 3)]
    ncol = len(fields)
    rows = [vals[i:i + ncol] for i in range(0, len(vals), ncol)]
    df = pd.DataFrame(rows, columns=fields).apply(pd.to_numeric, errors="coerce")
    df.insert(0, "date", pd.to_datetime(epochs, unit="s").normalize())
    for c in ("rrday", "snow"):
        if c in df:
            df.loc[df[c] < 0, c] = 0.0
    return df[["date", *[c for c in FMI_PARAMS if c in df]]]


def fetch_station(fmisid: int, first_year: int) -> pd.DataFrame:
    RAW_FMI.mkdir(parents=True, exist_ok=True)
    path = RAW_FMI / f"{fmisid}.csv"
    have = pd.read_csv(path, parse_dates=["date"]) if path.exists() else pd.DataFrame(columns=["date"])
    this_year = dt.date.fromisoformat(END_DATE).year
    done_years = set(pd.DatetimeIndex(have["date"]).year) if len(have) else set()
    parts = [have[pd.DatetimeIndex(have["date"]).year != this_year]] if len(have) else []
    todo = [y for y in range(first_year, this_year + 1) if y not in done_years or y == this_year]
    for i, y in enumerate(todo):
        df = fetch_year(fmisid, y)
        if len(df):
            parts.append(df)
        if (i + 1) % 10 == 0:
            print(f"  {fmisid}: {y} ({i+1}/{len(todo)})", flush=True)
        time.sleep(0.3)
    out = pd.concat(parts, ignore_index=True) if parts else have
    out = out.drop_duplicates("date").sort_values("date")
    out.to_csv(path, index=False)
    return out


def main():
    for sid, (name, first, _lat, _lon) in FMI_STATIONS.items():
        t = time.time()
        df = fetch_station(sid, first)
        yrs = pd.DatetimeIndex(df["date"]).year
        print(f"{name} ({sid}): {len(df)} days, {yrs.min()}–{yrs.max()}, "
              f"tday n={df['tday'].notna().sum()}, rrday n={df['rrday'].notna().sum()}, "
              f"snow n={df['snow'].notna().sum()}  [{time.time()-t:.0f}s]", flush=True)


if __name__ == "__main__":
    sys.exit(main())
