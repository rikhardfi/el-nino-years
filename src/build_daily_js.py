"""Write per-site daily files for the app's day-range mode: app/data/daily/<site_id>.js

Only Oct–Apr days are included. Format:
  window.ENSO_DAILY=window.ENSO_DAILY||{};window.ENSO_DAILY["<site_id>"]={"start":"YYYY-MM-DD",
  "cols":["tmean","tmax","tmin","precip","snow_depth"],"rows":[[dayOffset,tmean,tmax,tmin,precip,snow_depth],...]}
"""
import json
import sys
import numpy as np
import pandas as pd
from config import PROCESSED, APPDATA

COLS = ["tmean", "tmax", "tmin", "precip", "snow_depth"]


def main():
    out = APPDATA / "daily"
    out.mkdir(parents=True, exist_ok=True)
    sites = pd.read_csv(PROCESSED / "sites.csv")
    total = 0
    for sid in sites["site_id"]:
        df = pd.read_csv(PROCESSED / "daily" / f"{sid}.csv", parse_dates=["date"])
        df = df[df["date"].dt.month.isin([10, 11, 12, 1, 2, 3, 4]) & (df["date"].dt.year >= 1949)]
        for c in COLS:
            if c not in df:
                df[c] = np.nan
        start = df["date"].min()
        off = (df["date"] - start).dt.days.to_numpy()
        vals = df[COLS].round(1).to_numpy()
        rows = [[int(o)] + [None if pd.isna(v) else float(v) for v in r] for o, r in zip(off, vals)]
        js = ("window.ENSO_DAILY=window.ENSO_DAILY||{};window.ENSO_DAILY[" + json.dumps(sid) + "]="
              + json.dumps({"start": start.strftime("%Y-%m-%d"), "cols": COLS, "rows": rows}, separators=(",", ":"))
              + ";")
        (out / f"{sid}.js").write_text(js)
        total += len(js)
    print(f"wrote {len(sites)} daily files, {total/1e6:.1f} MB total → {out}")


if __name__ == "__main__":
    sys.exit(main())
