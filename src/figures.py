"""Report figures (PDF → report/figures, PNG → graphs_export) and LaTeX tables/macros (report/generated)."""
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
from matplotlib.lines import Line2D
from config import PROCESSED, FIGDIR, PNGDIR, ROOT, COUNTRY_NAMES
from metrics import METRICS

GROUPS = ["super", "elnino", "neutral", "lanina"]
GLAB = {"super": "Super El Niño", "elnino": "El Niño", "neutral": "Neutral", "lanina": "La Niña"}
GCOL = {"super": "#b3262c", "elnino": "#eb6834", "neutral": "#8a8983", "lanina": "#2a78d6"}
UNITS = ["FI", "SE", "NO", "DK", "IS", "NORDIC"]
ULAB = {**COUNTRY_NAMES, "NORDIC": "Nordic mean"}
GEN = ROOT / "report" / "generated"

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelweight": "bold", "axes.edgecolor": "black", "axes.linewidth": 0.8,
    "axes.grid": False, "xtick.direction": "out", "ytick.direction": "out",
    "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 150, "savefig.bbox": "tight",
})


def export_plot(fig, name):
    FIGDIR.mkdir(parents=True, exist_ok=True)
    PNGDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGDIR / f"{name}.pdf")
    fig.savefig(PNGDIR / f"{name}.png", dpi=200)
    plt.close(fig)
    print("  saved", name)


def load():
    d = dict(
        sm=pd.read_csv(PROCESSED / "season_metrics.csv"),
        sites=pd.read_csv(PROCESSED / "sites.csv"),
        cw=pd.read_csv(PROCESSED / "country_winters.csv"),
        comp=pd.read_csv(PROCESSED / "composites.csv"),
        contr=pd.read_csv(PROCESSED / "contrasts.csv"),
        corr=pd.read_csv(PROCESSED / "oni_corr.csv"),
        win=pd.read_csv(PROCESSED / "enso_winters.csv"),
        oni=pd.read_csv(PROCESSED / "oni.csv"),
    )
    return d


# ── 1. ONI timeline ──────────────────────────────────────────────────────────
def fig_oni(d):
    oni, win = d["oni"], d["win"]
    t = oni["year"] + (oni["seas_idx"] + 1) / 12.0
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.fill_between(t, 0, oni["anom"], where=oni["anom"] >= 0.5, color=GCOL["elnino"], alpha=0.85, lw=0)
    ax.fill_between(t, 0, oni["anom"], where=oni["anom"] <= -0.5, color=GCOL["lanina"], alpha=0.85, lw=0)
    ax.plot(t, oni["anom"], color="black", lw=0.6)
    for y in (0.5, -0.5):
        ax.axhline(y, color="#8a8983", lw=0.6, ls=":")
    ax.axhline(2.0, color=GCOL["super"], lw=0.8, ls="--")
    ax.text(1950.5, 2.05, "super threshold (2.0)", color=GCOL["super"], fontsize=7, va="bottom")
    for _, r in win[win.group == "super"].iterrows():
        ax.annotate(r["label"], (r["winter"] - 0.1, r["event_peak"]), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=7, color=GCOL["super"], fontweight="bold")
    ax.set_xlim(1950, t.max() + 0.5)
    ax.set_ylabel("ONI (°C)")
    ax.set_xlabel("Year")
    ax.set_title("Oceanic Niño Index, 3-month running mean, 1950 to present")
    ax.spines[["top", "right"]].set_visible(False)
    export_plot(fig, "fig01_oni_timeline")


# ── 2. Composite dot + CI, small multiples by country ────────────────────────
def composite_panel(ax, comp, cw, unit, season, metric, variant, show_points=True):
    c = comp[(comp.level == "country") & (comp.unit == unit) & (comp.season == season)
             & (comp.metric == metric) & (comp.variant == variant)].set_index("group")
    w = cw[(cw.country == unit) & (cw.season == season) & (cw.metric == metric)].dropna(subset=[variant])
    rng = np.random.default_rng(1)
    for i, g in enumerate(GROUPS):
        if g not in c.index:
            continue
        r = c.loc[g]
        pts = w[w.group == g][variant].to_numpy()
        if show_points:
            ax.scatter(pts, i + rng.uniform(-0.18, 0.18, len(pts)), s=7, color=GCOL[g], alpha=0.45, lw=0)
        ax.plot([r["ci_lo"], r["ci_hi"]], [i, i], color=GCOL[g], lw=2, solid_capstyle="round")
        ax.scatter([r["mean"]], [i], s=36, color=GCOL[g], edgecolor="white", lw=0.8, zorder=5)
        ax.text(1.02, i, f"n={int(r['n'])}", transform=ax.get_yaxis_transform(), va="center", fontsize=7,
                color="#52514e")
    ax.axvline(0, color="#8a8983", lw=0.6, ls=":")
    ax.set_yticks(range(len(GROUPS)))
    ax.set_yticklabels([GLAB[g] for g in GROUPS])
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)


def fig_composites(d, metric, season, variant, name, xlabel):
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.2), sharex=True)
    for ax, u in zip(axes.flat, UNITS):
        composite_panel(ax, d["comp"], d["cw"], u, season, metric, variant)
        ax.set_title(ULAB[u])
    for ax in axes[1]:
        ax.set_xlabel(xlabel)
    for ax in axes[:, 1:].flat:
        ax.tick_params(labelleft=False)
    fig.suptitle(f"{METRICS[metric]}, {season}: group means with 95% CI", x=0.01, ha="left",
                 fontsize=10, fontweight="bold")
    fig.tight_layout()
    export_plot(fig, name)


# ── 3. Time series, national mean ────────────────────────────────────────────
def fig_timeseries(d, unit, metric, season, variant, name, ylabel):
    w = d["cw"][(d["cw"].country == unit) & (d["cw"].season == season) & (d["cw"].metric == metric)]
    w = w.dropna(subset=[variant]).sort_values("winter")
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ax.plot(w["winter"], w[variant], color="#c3c2b7", lw=0.8, zorder=1)
    for g in GROUPS:
        s = w[w.group == g]
        ax.scatter(s["winter"], s[variant], s=18 if g != "super" else 40, color=GCOL[g], label=GLAB[g],
                   edgecolor="white", lw=0.5, zorder=3)
    for _, r in w[w.group == "super"].iterrows():
        lab = d["win"].set_index("winter").loc[r["winter"], "label"]
        ax.annotate(lab, (r["winter"], r[variant]), xytext=(0, 7), textcoords="offset points", ha="center",
                    fontsize=7, color=GCOL["super"], fontweight="bold")
    ax.axhline(0, color="#8a8983", lw=0.6, ls=":")
    ax.set_xlabel("Winter (year of January)")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{ULAB[unit]}: {METRICS[metric]}, {season}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=4)
    ax.spines[["top", "right"]].set_visible(False)
    export_plot(fig, name)


# ── 4. ONI scatter ───────────────────────────────────────────────────────────
def fig_oni_scatter(d, metric, season, variant, name, ylabel):
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.4), sharex=True)
    for ax, u in zip(axes.flat, UNITS):
        w = d["cw"][(d["cw"].country == u) & (d["cw"].season == season) & (d["cw"].metric == metric)]
        w = w.dropna(subset=[variant, "oni_djf"])
        for g in GROUPS:
            s = w[w.group == g]
            ax.scatter(s["oni_djf"], s[variant], s=14, color=GCOL[g], edgecolor="white", lw=0.4)
        if len(w) > 5:
            b, a = np.polyfit(w["oni_djf"], w[variant], 1)
            xx = np.array([w["oni_djf"].min(), w["oni_djf"].max()])
            ax.plot(xx, a + b * xx, color="black", lw=0.8)
        cr = d["corr"][(d["corr"].level == "country") & (d["corr"].unit == u) & (d["corr"].season == season)
                       & (d["corr"].metric == metric) & (d["corr"].variant == variant)]
        if len(cr):
            r = cr.iloc[0]
            ax.text(0.03, 0.95, f"ρ = {r['spearman_rho']:.2f}, p = {r['p']:.2f}", transform=ax.transAxes,
                    va="top", fontsize=7.5)
        ax.axhline(0, color="#8a8983", lw=0.6, ls=":")
        ax.axvline(0, color="#8a8983", lw=0.6, ls=":")
        ax.set_title(ULAB[u])
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axes[1]:
        ax.set_xlabel("ONI, DJF (°C)")
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    fig.suptitle(f"{METRICS[metric]} vs ONI, {season} (Spearman)", x=0.01, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout()
    export_plot(fig, name)


# ── 5. Map of site-level contrasts ───────────────────────────────────────────
def _iter_polys(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        yield c[0], c[1:]
    elif t == "MultiPolygon":
        for poly in c:
            yield poly[0], poly[1:]


def _ring_path(ext, holes):
    verts, codes = [], []
    for ring in [ext, *holes]:
        ring = list(ring)
        verts.extend(ring + [ring[0]])
        codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 1) + [MplPath.CLOSEPOLY])
    return MplPath(verts, codes)


def draw_nordics(ax, view=(-25, 32, 54, 71.5)):
    lo, hi, la, ha = view
    for c in ("finland", "sweden", "norway", "denmark", "iceland"):
        gj = json.load(open(ROOT / "data" / "geo" / f"{c}.geojson", encoding="utf-8"))
        for f in gj["features"]:
            for ext, holes in _iter_polys(f["geometry"]):
                arr = np.asarray(ext)
                clon, clat = arr[:, 0].mean(), arr[:, 1].mean()
                if not (lo <= clon <= hi and la <= clat <= ha) or (-12 < clon < -2 and clat > 69):
                    continue
                ax.add_patch(PathPatch(_ring_path(ext, holes), facecolor="#f0efec", edgecolor="#b5b4ae", lw=0.4))
    ax.set_xlim(lo, hi)
    ax.set_ylim(la, ha)
    ax.set_aspect(1 / np.cos(np.deg2rad(63)))
    ax.axis("off")


def fig_map(d, metric, season, g1, g2, name, unit_label):
    ct = d["contr"][(d["contr"].level == "site") & (d["contr"].season == season) & (d["contr"].metric == metric)
                    & (d["contr"].variant == "anom_dt") & (d["contr"].g1 == g1) & (d["contr"].g2 == g2)]
    ct = ct.merge(d["sites"], left_on="unit", right_on="site_id")
    ct = ct[ct.source.isin(["FMI", "GHCN"])]
    vmax = max(0.5, np.nanpercentile(ct["diff"].abs(), 95))
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    draw_nordics(ax)
    sig = ct.p_perm < 0.05
    sc = ax.scatter(ct["lon"], ct["lat"], c=ct["diff"], cmap="RdBu_r", vmin=-vmax, vmax=vmax, s=55,
                    edgecolor=np.where(sig, "black", "white"), linewidths=np.where(sig, 1.4, 0.6), zorder=5)
    cb = fig.colorbar(sc, ax=ax, shrink=0.55, pad=0.02)
    cb.set_label(f"{GLAB[g1]} minus {GLAB[g2]} ({unit_label})", fontweight="bold")
    ax.set_title(f"{METRICS[metric]}, {season}: detrended difference of group means by station")
    ax.legend(handles=[Line2D([], [], marker="o", ls="", markerfacecolor="#f0efec", markeredgecolor="black",
                              markeredgewidth=1.4, label="permutation p < 0.05"),
                       Line2D([], [], marker="o", ls="", markerfacecolor="#f0efec", markeredgecolor="white",
                              markeredgewidth=0.6, label="not significant")],
              loc="lower left", fontsize=7)
    export_plot(fig, name)


# ── 6. Heatmap of Cohen's d, station × metric ────────────────────────────────
def fig_heatmap(d, season, g1, g2, name):
    metrics = ["tmean", "tmin_mean", "tmax_mean", "precip", "precip_days", "snow_depth", "snow_cover_days",
               "frost_days", "ice_days", "thaw_days", "rain_on_snow_days"]
    ct = d["contr"][(d["contr"].level == "site") & (d["contr"].season == season) & (d["contr"].variant == "anom_dt")
                    & (d["contr"].g1 == g1) & (d["contr"].g2 == g2) & (d["contr"].metric.isin(metrics))]
    ct = ct.merge(d["sites"], left_on="unit", right_on="site_id")
    ct = ct[ct.source.isin(["FMI", "GHCN"])].copy()
    ct["country"] = pd.Categorical(ct["country"], ["FI", "SE", "NO", "DK", "IS"])
    order = ct.sort_values(["country", "lat"], ascending=[True, False])["name"].unique()
    piv = ct.pivot_table(index="name", columns="metric", values="cohen_d").reindex(index=order, columns=metrics)
    pv = ct.pivot_table(index="name", columns="metric", values="p_perm").reindex(index=order, columns=metrics)
    fig, ax = plt.subplots(figsize=(7.2, 0.26 * len(order) + 1.6))
    im = ax.imshow(piv.to_numpy(float), cmap="RdBu_r", vmin=-1.5, vmax=1.5, aspect="auto")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            p = pv.iat[i, j]
            if pd.notna(p) and p < 0.05:
                ax.text(j, i, "*", ha="center", va="center", fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([METRICS[m].split(" (")[0] for m in metrics], rotation=40, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=7.5)
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label(f"Cohen's d, {GLAB[g1]} minus {GLAB[g2]}", fontweight="bold")
    ax.set_title(f"{season}, detrended anomalies: effect size by station and metric (* permutation p < 0.05)")
    export_plot(fig, name)


# ── LaTeX tables and macros ──────────────────────────────────────────────────
def fmt(x, nd=1):
    return "" if pd.isna(x) else f"{x:.{nd}f}"


def table_composites(d, season, variant, metrics, fname):
    comp = d["comp"][(d["comp"].level == "country") & (d["comp"].season == season) & (d["comp"].variant == variant)]
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Metric & Region & Super El Niño & El Niño & Neutral & La Niña \\", r"\midrule"]
    for m in metrics:
        first = True
        for u in UNITS:
            c = comp[(comp.unit == u) & (comp.metric == m)].set_index("group")
            if c.empty:
                continue
            cells = []
            for g in GROUPS:
                if g in c.index:
                    r = c.loc[g]
                    cells.append(f"{fmt(r['mean'])} ({fmt(r['ci_lo'])} to {fmt(r['ci_hi'])})")
                else:
                    cells.append("")
            label = METRICS[m].replace("°", r"\textdegree{}").replace("≥", r"$\geq$").replace("<", "$<$").replace(">", "$>$") if first else ""
            lines.append(f"{label} & {ULAB[u]} & " + " & ".join(cells) + r" \\")
            first = False
        lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (GEN / fname).write_text("\n".join(lines), encoding="utf-8")


def table_contrasts(d, season, variant, metrics, fname):
    ct = d["contr"][(d["contr"].level == "country") & (d["contr"].season == season) & (d["contr"].variant == variant)]
    pairs = [("super", "elnino"), ("super", "neutral"), ("elnino", "neutral"), ("lanina", "neutral")]
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Metric & Region & Super $-$ El Niño & Super $-$ Neutral & El Niño $-$ Neutral & La Niña $-$ Neutral \\",
             r"\midrule"]
    for m in metrics:
        first = True
        for u in UNITS:
            cells = []
            any_ = False
            for g1, g2 in pairs:
                r = ct[(ct.unit == u) & (ct.metric == m) & (ct.g1 == g1) & (ct.g2 == g2)]
                if r.empty:
                    cells.append("")
                    continue
                any_ = True
                r = r.iloc[0]
                star = r"$^{*}$" if r["p_perm"] < 0.05 else ""
                cells.append(f"{fmt(r['diff'])} ({fmt(r['ci_lo'])} to {fmt(r['ci_hi'])}), p={fmt(r['p_perm'], 2)}{star}")
            if not any_:
                continue
            label = METRICS[m].replace("°", r"\textdegree{}").replace("≥", r"$\geq$").replace("<", "$<$").replace(">", "$>$") if first else ""
            lines.append(f"{label} & {ULAB[u]} & " + " & ".join(cells) + r" \\")
            first = False
        lines.append(r"\addlinespace")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (GEN / fname).write_text("\n".join(lines), encoding="utf-8")


def table_sites(d, fname):
    s = d["sites"][d["sites"].source.isin(["FMI", "GHCN"])].copy()
    s["country"] = pd.Categorical(s["country"], ["FI", "SE", "NO", "DK", "IS"])
    s = s.sort_values(["country", "lat"], ascending=[True, False])
    lines = [r"\begin{tabular}{llllrr}", r"\toprule", r"Country & Station & Source & Coordinates & First & Last \\", r"\midrule"]
    for _, r in s.iterrows():
        lines.append(f"{COUNTRY_NAMES[r['country']]} & {r['name']} & {r['source']} & {r['lat']:.2f}\\textdegree{{}}N, {r['lon']:.2f}\\textdegree{{}}E & {int(r['first_year'])} & {int(r['last_year'])} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (GEN / fname).write_text("\n".join(lines), encoding="utf-8")


def macros(d):
    win = d["win"]
    ct = d["contr"]
    def val(unit, metric, g1, g2, col, season="DJF", variant="anom_dt", nd=1):
        r = ct[(ct.level == "country") & (ct.unit == unit) & (ct.season == season) & (ct.metric == metric)
               & (ct.variant == variant) & (ct.g1 == g1) & (ct.g2 == g2)]
        return fmt(r.iloc[0][col], nd) if len(r) else "NA"
    m = {
        "nSuper": (win.group == "super").sum(), "nElnino": (win.group == "elnino").sum(),
        "nNeutral": (win.group == "neutral").sum(), "nLanina": (win.group == "lanina").sum(),
        "superWinters": ", ".join(win[win.group == "super"]["label"]),
        "lastWinter": win["label"].iloc[-1],
        "nStationsFI": int((d["sites"].source == "FMI").sum()),
        "nStationsGHCN": int((d["sites"].source == "GHCN").sum()),
    }
    for u in UNITS:
        for met, key in [("tmean", "T"), ("precip", "P"), ("snow_depth", "S"), ("thaw_days", "Thaw"), ("frost_days", "Frost")]:
            for g1, g2, pk in [("super", "elnino", "SvE"), ("super", "neutral", "SvN"), ("elnino", "neutral", "EvN")]:
                m[f"{u.lower()}{key}{pk}diff"] = val(u, met, g1, g2, "diff")
                m[f"{u.lower()}{key}{pk}lo"] = val(u, met, g1, g2, "ci_lo")
                m[f"{u.lower()}{key}{pk}hi"] = val(u, met, g1, g2, "ci_hi")
                m[f"{u.lower()}{key}{pk}p"] = val(u, met, g1, g2, "p_perm", nd=2)
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in m.items()]
    (GEN / "numbers.tex").write_text("\n".join(lines), encoding="utf-8")


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    d = load()
    fig_oni(d)
    fig_composites(d, "tmean", "DJF", "anom_dt", "fig02_composite_tmean_djf", "Detrended anomaly (°C)")
    fig_composites(d, "precip", "DJF", "anom_dt", "fig03_composite_precip_djf", "Detrended anomaly (mm)")
    fig_composites(d, "snow_depth", "DJF", "anom_dt", "fig04_composite_snow_djf", "Detrended anomaly (cm)")
    fig_composites(d, "thaw_days", "DJF", "anom_dt", "fig05_composite_thaw_djf", "Detrended anomaly (days)")
    fig_composites(d, "tmean", "JFM", "anom_dt", "fig06_composite_tmean_jfm", "Detrended anomaly (°C)")
    fig_timeseries(d, "FI", "tmean", "DJF", "anom_dt", "fig07_timeseries_fi_tmean_djf", "Detrended anomaly (°C)")
    fig_timeseries(d, "NORDIC", "tmean", "DJF", "anom_dt", "fig08_timeseries_nordic_tmean_djf", "Detrended anomaly (°C)")
    fig_oni_scatter(d, "tmean", "DJF", "anom_dt", "fig09_oni_scatter_tmean_djf", "Detrended anomaly (°C)")
    fig_map(d, "tmean", "DJF", "super", "neutral", "fig10_map_tmean_super_neutral", "°C")
    fig_map(d, "precip", "DJF", "super", "neutral", "fig11_map_precip_super_neutral", "mm")
    fig_heatmap(d, "DJF", "super", "neutral", "fig12_heatmap_super_neutral_djf")
    fig_heatmap(d, "DJF", "elnino", "neutral", "fig13_heatmap_elnino_neutral_djf")
    fig_composites(d, "tmean", "DJF", "value", "figS1_composite_tmean_djf_raw", "Mean temperature (°C)")
    table_composites(d, "DJF", "anom_dt", ["tmean", "precip", "snow_depth", "thaw_days", "frost_days"], "table_composites_djf.tex")
    table_contrasts(d, "DJF", "anom_dt", ["tmean", "precip", "snow_depth", "thaw_days", "frost_days"], "table_contrasts_djf.tex")
    table_contrasts(d, "JFM", "anom_dt", ["tmean", "precip", "snow_depth", "thaw_days", "frost_days"], "table_contrasts_jfm.tex")
    table_sites(d, "table_sites.tex")
    macros(d)


if __name__ == "__main__":
    sys.exit(main())
