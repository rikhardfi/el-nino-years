"""Group composites and tests: super El Niño vs El Niño vs neutral vs La Niña winters.

Outputs (data/processed):
  composites.csv   per level (site or country), season, metric, variant (value|anom|anom_dt), group:
                   n, mean, median, sd, ci_lo, ci_hi (bootstrap of the mean)
  contrasts.csv    per level/season/metric/variant, pairs of groups: diff of means, CI, permutation p,
                   Welch p, Mann-Whitney p, Cohen's d
  oni_corr.csv     Spearman correlation of anomaly with ONI DJF per level/season/metric/variant
  country_winters.csv  country-mean anomalies per winter (input to the country-level composites)
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats
from config import PROCESSED, COUNTRY_NAMES

GROUPS = ["super", "elnino", "neutral", "lanina"]
PAIRS = [("super", "elnino"), ("super", "neutral"), ("elnino", "neutral"), ("super", "lanina"), ("lanina", "neutral")]
VARIANTS = ["value", "anom", "anom_dt"]
RNG = np.random.default_rng(20260904)
N_BOOT, N_PERM = 4000, 5000


SMALL_N = 6


def boot_ci(x: np.ndarray):
    """95% CI of the mean: percentile bootstrap, or a t-interval when n < SMALL_N
    (a bootstrap of three values has only ten distinct resamples and understates the uncertainty)."""
    if len(x) < 2:
        return np.nan, np.nan
    if len(x) < SMALL_N:
        h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
        return x.mean() - h, x.mean() + h
    idx = RNG.integers(0, len(x), size=(N_BOOT, len(x)))
    means = x[idx].mean(axis=1)
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def diff_ci(a: np.ndarray, b: np.ndarray):
    """95% CI of the difference of means: bootstrap, or Welch t-interval when either n < SMALL_N."""
    if min(len(a), len(b)) < SMALL_N:
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        df = se**4 / ((a.var(ddof=1) / len(a))**2 / (len(a) - 1) + (b.var(ddof=1) / len(b))**2 / (len(b) - 1))
        h = stats.t.ppf(0.975, df) * se
        return a.mean() - b.mean() - h, a.mean() - b.mean() + h
    bi = RNG.integers(0, len(a), size=(N_BOOT, len(a)))
    bj = RNG.integers(0, len(b), size=(N_BOOT, len(b)))
    d = a[bi].mean(axis=1) - b[bj].mean(axis=1)
    return np.percentile(d, 2.5), np.percentile(d, 97.5)


def perm_p(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sided permutation test of the difference in means (vectorised)."""
    if len(a) < 2 or len(b) < 2:
        return np.nan
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    n = len(a)
    perms = RNG.permuted(np.tile(pool, (N_PERM, 1)), axis=1)
    diffs = perms[:, :n].mean(axis=1) - perms[:, n:].mean(axis=1)
    return (np.sum(np.abs(diffs) >= abs(obs) - 1e-12) + 1) / (N_PERM + 1)


def cohen_d(a, b):
    if len(a) < 2 or len(b) < 2:
        return np.nan
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return (a.mean() - b.mean()) / sp if sp > 0 else np.nan


def composites_for(df: pd.DataFrame, level: str, unit_col: str):
    comp, contr, corr = [], [], []
    for (unit, season, metric), g in df.groupby([unit_col, "season", "metric"]):
        for variant in VARIANTS:
            gg = g.dropna(subset=[variant])
            if gg.empty:
                continue
            arrays = {grp: gg[gg.group == grp][variant].to_numpy(float) for grp in GROUPS}
            for grp, x in arrays.items():
                if len(x) == 0:
                    continue
                lo, hi = boot_ci(x)
                comp.append(dict(level=level, unit=unit, season=season, metric=metric, variant=variant,
                                 group=grp, n=len(x), mean=x.mean(), median=np.median(x),
                                 sd=x.std(ddof=1) if len(x) > 1 else np.nan, ci_lo=lo, ci_hi=hi))
            for g1, g2 in PAIRS:
                a, b = arrays[g1], arrays[g2]
                if len(a) < 2 or len(b) < 2:
                    continue
                diff = a.mean() - b.mean()
                lo, hi = diff_ci(a, b)
                w = stats.ttest_ind(a, b, equal_var=False).pvalue
                u = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
                contr.append(dict(level=level, unit=unit, season=season, metric=metric, variant=variant,
                                  g1=g1, g2=g2, n1=len(a), n2=len(b), diff=diff,
                                  ci_lo=lo, ci_hi=hi,
                                  p_perm=perm_p(a, b), p_welch=w, p_mwu=u, cohen_d=cohen_d(a, b)))
            gv = gg.dropna(subset=["oni_djf"])
            if len(gv) >= 10:
                rho, p = stats.spearmanr(gv["oni_djf"], gv[variant])
                corr.append(dict(level=level, unit=unit, season=season, metric=metric, variant=variant,
                                 n=len(gv), spearman_rho=rho, p=p))
    return comp, contr, corr


def main():
    sm = pd.read_csv(PROCESSED / "season_metrics.csv")
    sites = pd.read_csv(PROCESSED / "sites.csv")
    sm = sm[sm.group.isin(GROUPS)]
    sm = sm.merge(sites[["site_id", "country", "source"]], on="site_id")

    # Country-level: mean of site anomalies per winter (FMI for Finland, GHCN elsewhere)
    nat = sm[((sm.country == "FI") & (sm.source == "FMI")) | ((sm.country != "FI") & (sm.source == "GHCN"))]
    cw = (nat.groupby(["country", "winter", "season", "metric"])
             .agg(value=("value", "mean"), anom=("anom", "mean"), anom_dt=("anom_dt", "mean"),
                  n_sites=("site_id", "nunique"), group=("group", "first"), oni_djf=("oni_djf", "first"))
             .reset_index())
    cw = cw[cw.n_sites >= 2]
    # ERA5 (Open-Meteo) points as separate cross-check "countries" per country code
    era = sm[sm.source == "ERA5"]
    if len(era):
        cw2 = (era.groupby(["country", "winter", "season", "metric"])
                  .agg(value=("value", "mean"), anom=("anom", "mean"), anom_dt=("anom_dt", "mean"),
                       n_sites=("site_id", "nunique"), group=("group", "first"), oni_djf=("oni_djf", "first"))
                  .reset_index())
        cw2["country"] = cw2["country"] + "-ERA5"
        cw = pd.concat([cw, cw2], ignore_index=True)
    # Nordic-wide mean of the five national series
    nordic = (cw[cw.country.isin(["FI", "SE", "NO", "DK", "IS"])]
                .groupby(["winter", "season", "metric"])
                .agg(value=("value", "mean"), anom=("anom", "mean"), anom_dt=("anom_dt", "mean"),
                     n_sites=("n_sites", "sum"), group=("group", "first"), oni_djf=("oni_djf", "first"))
                .reset_index().assign(country="NORDIC"))
    cw = pd.concat([cw, nordic], ignore_index=True)
    cw.to_csv(PROCESSED / "country_winters.csv", index=False, float_format="%.3f")

    comp_s, contr_s, corr_s = composites_for(sm, "site", "site_id")
    comp_c, contr_c, corr_c = composites_for(cw, "country", "country")
    pd.DataFrame(comp_s + comp_c).to_csv(PROCESSED / "composites.csv", index=False, float_format="%.4f")
    pd.DataFrame(contr_s + contr_c).to_csv(PROCESSED / "contrasts.csv", index=False, float_format="%.4f")
    pd.DataFrame(corr_s + corr_c).to_csv(PROCESSED / "oni_corr.csv", index=False, float_format="%.4f")
    c = pd.DataFrame(contr_c)
    show = c[(c.season == "DJF") & (c.variant == "anom_dt") & (c.metric.isin(["tmean", "precip", "snow_depth"]))
             & (c.g1 == "super") & (c.g2.isin(["elnino", "neutral"]))]
    print(show[["unit", "metric", "g1", "g2", "n1", "n2", "diff", "ci_lo", "ci_hi", "p_perm", "cohen_d"]].to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
