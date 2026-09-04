"""Bundle processed results into app/data/enso_data.js (window.ENSO_DATA) for the offline app.

Tables are stored column-oriented ({"columns": [...], "rows": [[...], ...]}) to keep the file small.
NaN -> null, floats rounded to 3 decimals.
"""
import json
import math
import sys
import numpy as np
import pandas as pd
from config import PROCESSED, APPDATA, SEASONS, COUNTRY_NAMES, SUPER_THRESHOLD, BASE_START, BASE_END
from metrics import METRICS
import enso

SEASON_LABELS = {"DJF": "Winter (Dec–Feb)", "JFM": "Late winter (Jan–Mar)", "NDJFM": "Extended winter (Nov–Mar)"}
GROUP_LABELS = {"super": "Super El Niño", "elnino": "El Niño", "neutral": "Neutral", "lanina": "La Niña"}


def r3(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    if isinstance(x, (np.floating, float)):
        return round(float(x), 3)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def table(df: pd.DataFrame, cols=None) -> dict:
    cols = cols or list(df.columns)
    rows = [[r3(v) for v in row] for row in df[cols].itertuples(index=False, name=None)]
    return {"columns": cols, "rows": rows}


def series_map(df: pd.DataFrame, unit_col: str) -> dict:
    """{unit: {season: {metric: [[winter, value, anom, anom_dt], ...]}}}"""
    out = {}
    df = df.sort_values("winter")
    for (u, s, m), g in df.groupby([unit_col, "season", "metric"]):
        out.setdefault(u, {}).setdefault(s, {})[m] = [
            [int(w), r3(v), r3(a), r3(d)] for w, v, a, d in zip(g.winter, g.value, g.anom, g.anom_dt)]
    return out


OLOS_SITE = "ghcn_FIE00146423"     # Muonio Alamuonio, 5 km from Olos
MONTH_ORDER = [10, 11, 12, 1, 2, 3, 4]   # winter window order: Oct .. Apr


def monthly_map() -> dict:
    """{site_id: {metric: {winter: [v_oct, v_nov, v_dec, v_jan, v_feb, v_mar, v_apr]}}} from monthly_metrics.csv.
    A month is null when absent (metrics.py already applies the 90 % completeness rule)."""
    path = PROCESSED / "monthly_metrics.csv"
    if not path.exists():
        print("  monthly_metrics.csv not found; custom month windows will be unavailable in the app")
        return {}
    mm = pd.read_csv(path)
    mm = mm[(mm.winter >= 1950) & mm.month.isin(MONTH_ORDER)]
    pos = {m: i for i, m in enumerate(MONTH_ORDER)}
    out = {}
    for (sid, met, w), g in mm.groupby(["site_id", "metric", "winter"]):
        arr = [None] * 7
        for m, v in zip(g.month, g.value):
            arr[pos[int(m)]] = r3(v)
        out.setdefault(sid, {}).setdefault(met, {})[int(w)] = arr
    return out


def status_json() -> dict:
    path = PROCESSED / "enso_status.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def winters_with_peak_flag() -> pd.DataFrame:
    oni = pd.read_csv(PROCESSED / "oni.csv")
    events = enso.find_events(oni)
    winters = pd.read_csv(PROCESSED / "enso_winters.csv")
    peak_years = {enso.peak_winter(e) for _, e in events.iterrows() if e["sign"] > 0}
    winters["is_peak_winter"] = winters["winter"].isin(peak_years)
    return winters


def main():
    APPDATA.mkdir(parents=True, exist_ok=True)
    sites = pd.read_csv(PROCESSED / "sites.csv")
    sm = pd.read_csv(PROCESSED / "season_metrics.csv")
    comp = pd.read_csv(PROCESSED / "composites.csv")
    contr = pd.read_csv(PROCESSED / "contrasts.csv")
    corr = pd.read_csv(PROCESSED / "oni_corr.csv")
    cw = pd.read_csv(PROCESSED / "country_winters.csv")
    winters = winters_with_peak_flag()
    oni = pd.read_csv(PROCESSED / "oni.csv")

    # keep only winters with an ENSO label (1950+) in the per-winter series to limit size
    sm = sm[sm.winter >= 1950]
    cw = cw[cw.winter >= 1950]

    units_country = [c for c in ["FI", "SE", "NO", "DK", "IS", "NORDIC"] if c in set(cw.country)]
    units_country += sorted(c for c in set(cw.country) if c.endswith("-ERA5"))
    unit_labels = {**COUNTRY_NAMES, "NORDIC": "Nordic mean (5 countries)"}
    for c in units_country:
        if c.endswith("-ERA5"):
            unit_labels[c] = f"{COUNTRY_NAMES.get(c[:-5], c[:-5])} (ERA5 cross-check)"

    # which sites form each country unit (mirrors analysis.py: FMI for Finland, GHCN elsewhere, ERA5 as *-ERA5)
    site_units = {}
    for _, r in sites.iterrows():
        if r.source == "ERA5":
            site_units.setdefault(f"{r.country}-ERA5", []).append(r.site_id)
        elif (r.country == "FI" and r.source == "FMI") or (r.country != "FI" and r.source == "GHCN"):
            site_units.setdefault(r.country, []).append(r.site_id)
    site_units["NORDIC"] = ["FI", "SE", "NO", "DK", "IS"]

    data = {
        "meta": {
            "built": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "super_threshold_default": SUPER_THRESHOLD,
            "baseline": [BASE_START, BASE_END],
            "seasons": list(SEASONS.keys()),
            "season_labels": SEASON_LABELS,
            "metrics": METRICS,
            "groups": ["super", "elnino", "neutral", "lanina"],
            "group_labels": GROUP_LABELS,
            "country_names": COUNTRY_NAMES,
            "country_units": units_country,
            "unit_labels": unit_labels,
            "olos_site": OLOS_SITE,
            "month_order": MONTH_ORDER,
            "site_units": site_units,
        },
        "sites": table(sites),
        "winters": table(winters, ["winter", "label", "oni_djf", "group", "event_peak", "event_span", "is_peak_winter"]),
        "oni": table(oni, ["seas", "year", "anom"]),
        "site_series": series_map(sm, "site_id"),
        "country_series": series_map(cw, "country"),
        "country_nsites": {c: int(g.n_sites.max()) for c, g in cw.groupby("country")},
        "composites": table(comp),
        "contrasts": table(contr, ["level", "unit", "season", "metric", "variant", "g1", "g2", "n1", "n2",
                                   "diff", "ci_lo", "ci_hi", "p_perm", "p_welch", "cohen_d"]),
        "oni_corr": table(corr),
        "monthly": monthly_map(),
        "status": status_json(),
    }
    out = APPDATA / "enso_data.js"
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    out.write_text("// Generated by src/build_app_data.py. Do not edit.\nwindow.ENSO_DATA = " + js + ";\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1e6:.2f} MB); sites={len(sites)}, country units={units_country}, "
          f"monthly sites={len(data['monthly'])}, status={'yes' if data['status'] else 'no'}")


if __name__ == "__main__":
    sys.exit(main())
