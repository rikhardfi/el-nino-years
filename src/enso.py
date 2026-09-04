"""Download NOAA ONI and label each winter by ENSO phase and strength.

Winter label year = year of January (winter 1997/98 -> 1998). The winter's ONI is the
DJF value. An event is >= 5 consecutive overlapping 3-month seasons with |ONI| >= 0.5.
A winter belongs to the event that contains its DJF season. "Super" = event peak >= 2.0.
"""
import io
import sys
import pandas as pd
import requests
from config import ONI_URL, PROCESSED, ENSO_THRESHOLD, SUPER_THRESHOLD, MIN_SEASONS

SEAS_ORDER = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def fetch_oni() -> pd.DataFrame:
    txt = requests.get(ONI_URL, timeout=60).text
    df = pd.read_csv(io.StringIO(txt), sep=r"\s+")
    df.columns = ["seas", "year", "total", "anom"]
    df["seas_idx"] = df["seas"].map({s: i for i, s in enumerate(SEAS_ORDER)})
    df = df.sort_values(["year", "seas_idx"]).reset_index(drop=True)
    return df


def find_events(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per event: sign, start/end index, peak ONI, peak season label."""
    sign = df["anom"].apply(lambda a: 1 if a >= ENSO_THRESHOLD else (-1 if a <= -ENSO_THRESHOLD else 0))
    events, i = [], 0
    n = len(df)
    while i < n:
        s = sign.iloc[i]
        if s == 0:
            i += 1
            continue
        j = i
        while j < n and sign.iloc[j] == s:
            j += 1
        if j - i >= MIN_SEASONS:
            seg = df.iloc[i:j]
            k = seg["anom"].abs().idxmax()
            events.append(dict(sign=int(s), start=i, end=j - 1, peak=float(df.loc[k, "anom"]),
                               peak_seas=f"{df.loc[k,'seas']} {int(df.loc[k,'year'])}",
                               first=f"{seg.iloc[0]['seas']} {int(seg.iloc[0]['year'])}",
                               last=f"{seg.iloc[-1]['seas']} {int(seg.iloc[-1]['year'])}"))
        i = j
    return pd.DataFrame(events)


def peak_winter(e) -> int:
    """Winter label year that contains the event's peak season."""
    seas, yr = e["peak_seas"].split()
    yr = int(yr)
    return yr + 1 if seas in ("SON", "OND", "NDJ") else yr


def label_winters(df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    ev_of_idx = {}
    for e_id, e in events.iterrows():
        for idx in range(int(e["start"]), int(e["end"]) + 1):
            ev_of_idx[idx] = e_id
    rows = []
    for idx, r in df[df["seas"] == "DJF"].iterrows():
        yr = int(r["year"])
        e_id = ev_of_idx.get(idx)
        if e_id is None:
            grp, peak, ev_label = "neutral", None, ""
        else:
            e = events.loc[e_id]
            peak = e["peak"]
            ev_label = f"{e['first']} – {e['last']}"
            if e["sign"] > 0:
                # "super" only for the winter that contains the event peak; a secondary
                # winter of a multi-year event (e.g. 2014/15) is classified on its own DJF value
                grp = "super" if (peak >= SUPER_THRESHOLD and peak_winter(e) == yr) else "elnino"
            else:
                grp = "lanina"
        rows.append(dict(winter=yr, label=f"{yr-1}/{str(yr)[2:]}", oni_djf=float(r["anom"]),
                         group=grp, event_peak=peak, event_span=ev_label))
    return pd.DataFrame(rows)


CPC_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"


def current_status(oni: pd.DataFrame, events: pd.DataFrame) -> dict:
    """Latest ONI, the running event (if the tail of the record is inside one, even if shorter than
    five seasons yet) and the NOAA CPC alert status line, for the app's tracker panel."""
    import datetime as dt
    import html
    import re
    last = oni.iloc[-1]
    sign = oni["anom"].apply(lambda a: 1 if a >= ENSO_THRESHOLD else (-1 if a <= -ENSO_THRESHOLD else 0))
    cur = None
    if sign.iloc[-1] != 0:
        j = len(oni) - 1
        while j > 0 and sign.iloc[j - 1] == sign.iloc[-1]:
            j -= 1
        seg = oni.iloc[j:]
        cur = dict(sign=int(sign.iloc[-1]), first=f"{seg.iloc[0]['seas']} {int(seg.iloc[0]['year'])}",
                   n_seasons=int(len(seg)), peak_so_far=float(seg["anom"].abs().max() * sign.iloc[-1]))
    status = synopsis = None
    try:
        txt = requests.get(CPC_URL, timeout=60).text
        m = re.search(r"ENSO Alert System Status:\s*</?[^>]*>?\s*([A-Za-z ñÑ]+?)\s*<", txt)
        if m:
            status = m.group(1).strip()
        m2 = re.search(r"Synopsis:\s*(.*?)</p>", txt, re.S)
        if m2:
            synopsis = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m2.group(1))).split())[:600]
    except Exception:
        pass
    return dict(fetched=dt.date.today().isoformat(), latest_season=str(last["seas"]), latest_year=int(last["year"]),
                latest_oni=float(last["anom"]), current_event=cur, cpc_status=status, cpc_synopsis=synopsis,
                source_url=CPC_URL, oni_url=ONI_URL)


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    oni = fetch_oni()
    oni.to_csv(PROCESSED / "oni.csv", index=False)
    events = find_events(oni)
    events.to_csv(PROCESSED / "enso_events.csv", index=False)
    winters = label_winters(oni, events)
    winters.to_csv(PROCESSED / "enso_winters.csv", index=False)
    import json
    status = current_status(oni, events)
    (PROCESSED / "enso_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Status:", status)
    print("ONI rows:", len(oni), "last:", oni.iloc[-1]["seas"], int(oni.iloc[-1]["year"]))
    print("Events:", len(events))
    print(events[events.sign > 0].sort_values("peak", ascending=False).head(12).to_string())
    print("\nWinter groups:\n", winters["group"].value_counts().to_string())
    print("\nSuper winters:", winters[winters.group == "super"]["label"].tolist())
    print("El Niño winters:", winters[winters.group == "elnino"]["label"].tolist())


if __name__ == "__main__":
    sys.exit(main())
