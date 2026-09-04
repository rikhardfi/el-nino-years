"""Build per-site daily tables, seasonal winter metrics, anomalies and detrended anomalies.

Outputs (data/processed):
  sites.csv            site_id, name, country, source, lat, lon, first_year, last_year
  daily/<site_id>.csv  date, tmean, tmax, tmin, precip, snow_depth (cm)
  season_metrics.csv   long: site_id, winter, season, metric, value, anom, anom_dt, group, oni_djf
"""
import sys
import numpy as np
import pandas as pd
from config import (FMI_STATIONS, OM_POINTS, GHCN_STATIONS, RAW_FMI, RAW_OM, RAW_GHCN,
                    PROCESSED, SEASONS, BASE_START, BASE_END)

METRICS = {
    "tmean": "Mean temperature (°C)",
    "tmax_mean": "Mean daily maximum (°C)",
    "tmin_mean": "Mean daily minimum (°C)",
    "precip": "Precipitation sum (mm)",
    "precip_days": "Wet days, ≥1 mm (days)",
    "snow_depth": "Mean snow depth (cm)",
    "snow_max": "Maximum snow depth (cm)",
    "snow_cover_days": "Snow-cover days, ≥1 cm (days)",
    "frost_days": "Frost days, Tmin < 0 °C (days)",
    "ice_days": "Ice days, Tmax < 0 °C (days)",
    "thaw_days": "Thaw days, Tmax > 0 °C (days)",
    "rain_on_snow_days": "Rain-on-snow days (days)",
}
MIN_COMPLETENESS = 0.9
TREND_START = 1950


def load_fmi(sid: int) -> pd.DataFrame:
    p = RAW_FMI / f"{sid}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"])
    return df.rename(columns={"tday": "tmean", "rrday": "precip", "snow": "snow_depth"})


def load_om(pid: str) -> pd.DataFrame:
    p = RAW_OM / f"{pid}_daily.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"]).rename(columns={
        "temperature_2m_mean": "tmean", "temperature_2m_max": "tmax", "temperature_2m_min": "tmin",
        "precipitation_sum": "precip", "rain_sum": "rain", "snowfall_sum": "snowfall"})
    ps = RAW_OM / f"{pid}_snow.csv"
    if ps.exists():
        snow = pd.read_csv(ps, parse_dates=["date"])
        df = df.merge(snow, on="date", how="left")
    else:
        df["snow_depth_cm"] = np.nan
    df = df.rename(columns={"snow_depth_cm": "snow_depth"})
    return df[["date", "tmean", "tmax", "tmin", "precip", "snow_depth", "rain"]]


def load_ghcn(sid: str) -> pd.DataFrame:
    p = RAW_GHCN / f"{sid}.csv"
    if not p.exists():
        return None
    return pd.read_csv(p, parse_dates=["date"])


def season_metrics(df: pd.DataFrame, winter: int, months) -> dict:
    mask = np.zeros(len(df), dtype=bool)
    d = df["date"]
    for m, off in months:
        mask |= (d.dt.month == m) & (d.dt.year == winter + off)
    s = df[mask]
    ndays = sum(pd.Period(f"{winter+off}-{m:02d}").days_in_month for m, off in months)
    out = {}
    def ok(col):
        return col in s and s[col].notna().sum() >= MIN_COMPLETENESS * ndays
    if ok("tmean"):
        out["tmean"] = s["tmean"].mean()
    if ok("tmax"):
        out["tmax_mean"] = s["tmax"].mean()
        out["thaw_days"] = (s["tmax"] > 0).sum() * ndays / s["tmax"].notna().sum()
        out["ice_days"] = (s["tmax"] < 0).sum() * ndays / s["tmax"].notna().sum()
    if ok("tmin"):
        out["tmin_mean"] = s["tmin"].mean()
        out["frost_days"] = (s["tmin"] < 0).sum() * ndays / s["tmin"].notna().sum()
    if ok("precip"):
        out["precip"] = s["precip"].sum() * ndays / s["precip"].notna().sum()
        out["precip_days"] = (s["precip"] >= 1).sum() * ndays / s["precip"].notna().sum()
    if ok("snow_depth"):
        out["snow_depth"] = s["snow_depth"].mean()
        out["snow_max"] = s["snow_depth"].max()
        out["snow_cover_days"] = (s["snow_depth"] >= 1).sum() * ndays / s["snow_depth"].notna().sum()
        if ok("precip"):
            liquid = s["rain"] if "rain" in s and s["rain"].notna().any() else s["precip"].where(s["tmean"] > 0.5, 0)
            ros = ((liquid >= 1) & (s["snow_depth"] >= 1))
            out["rain_on_snow_days"] = ros.sum() * ndays / s["snow_depth"].notna().sum()
    return out


WINTER_MONTHS = [(10, -1), (11, -1), (12, -1), (1, 0), (2, 0), (3, 0), (4, 0)]


def monthly_metrics(df: pd.DataFrame, winter: int) -> list:
    """Per-month metrics (Oct–Apr) for one winter; same definitions as season_metrics."""
    rows = []
    d = df["date"]
    for m, off in WINTER_MONTHS:
        s = df[(d.dt.month == m) & (d.dt.year == winter + off)]
        ndays = pd.Period(f"{winter+off}-{m:02d}").days_in_month
        vals = season_metrics(df, winter, [(m, off)])
        nvalid = int(s["tmean"].notna().sum()) if len(s) else 0
        for metric, val in vals.items():
            rows.append(dict(site_id=None, winter=winter, month=m, metric=metric, value=val,
                             ndays_valid=nvalid, ndays_month=ndays))
    return rows


def add_anomalies(g: pd.DataFrame) -> pd.DataFrame:
    base = g[(g.winter >= BASE_START) & (g.winter <= BASE_END)]["value"]
    g = g.copy()
    g["anom"] = g["value"] - base.mean() if len(base) >= 20 else np.nan
    # Trend fitted on the ENSO-labelled period (1950 onward) so that stations with 19th-century
    # records are detrended over the same window as the 1959+ FMI stations.
    v = g.dropna(subset=["value"])
    v = v[v.winter >= TREND_START]
    if len(v) >= 20:
        slope, intercept = np.polyfit(v["winter"], v["value"], 1)
        g["anom_dt"] = g["value"] - (slope * g["winter"] + intercept)
        g["trend_per_decade"] = slope * 10
    else:
        g["anom_dt"] = np.nan
        g["trend_per_decade"] = np.nan
    return g


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "daily").mkdir(exist_ok=True)
    enso = pd.read_csv(PROCESSED / "enso_winters.csv")
    sites, rows, mrows = [], [], []
    sources = [(f"fmi_{sid}", n, "FI", "FMI", lat, lon, load_fmi(sid)) for sid, (n, _y, lat, lon) in FMI_STATIONS.items()]
    ghcn_meta = pd.read_csv(RAW_GHCN / "stations.csv").set_index("id") if (RAW_GHCN / "stations.csv").exists() else None
    if ghcn_meta is not None:
        sources += [(f"ghcn_{sid}", n, cc, "GHCN", ghcn_meta.loc[sid, "lat"], ghcn_meta.loc[sid, "lon"], load_ghcn(sid))
                    for sid, (n, cc) in GHCN_STATIONS.items() if sid in ghcn_meta.index]
    sources += [(f"om_{pid}", n, cc, "ERA5", lat, lon, load_om(pid)) for pid, (n, cc, lat, lon) in OM_POINTS.items()]
    for site_id, name, cc, src, lat, lon, df in sources:
        if df is None or not len(df):
            print("  missing:", site_id)
            continue
        df = df.sort_values("date").reset_index(drop=True)
        df.to_csv(PROCESSED / "daily" / f"{site_id}.csv", index=False, float_format="%.2f")
        y0, y1 = df["date"].dt.year.min(), df["date"].dt.year.max()
        sites.append(dict(site_id=site_id, name=name, country=cc, source=src, lat=lat, lon=lon,
                          first_year=y0, last_year=y1))
        for winter in range(y0 + 1, y1 + 1):
            for sname, months in SEASONS.items():
                for metric, val in season_metrics(df, winter, months).items():
                    rows.append(dict(site_id=site_id, winter=winter, season=sname, metric=metric, value=val))
            if winter >= 1950:
                for r in monthly_metrics(df, winter):
                    r["site_id"] = site_id
                    mrows.append(r)
        print(f"  {site_id} {name}: {y0}–{y1}", flush=True)
    sm = pd.DataFrame(rows)
    sm = pd.concat([add_anomalies(g) for _, g in sm.groupby(["site_id", "season", "metric"])], ignore_index=True)
    sm = sm.merge(enso[["winter", "group", "oni_djf", "event_peak"]], on="winter", how="left")
    sm["group"] = sm["group"].fillna("pre-ONI")
    pd.DataFrame(mrows).to_csv(PROCESSED / "monthly_metrics.csv", index=False, float_format="%.3f")
    pd.DataFrame(sites).to_csv(PROCESSED / "sites.csv", index=False)
    sm.to_csv(PROCESSED / "season_metrics.csv", index=False, float_format="%.3f")
    print(f"sites: {len(sites)}, season-metric rows: {len(sm)}")


if __name__ == "__main__":
    sys.exit(main())
