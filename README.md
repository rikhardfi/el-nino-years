# El Niño years: Nordic winters by ENSO strength

Do super El Niño winters (event peak ONI ≥ 2.0 °C: 1982/83, 1997/98, 2015/16) differ from ordinary
El Niño, neutral and La Niña winters in Finland and the other Nordic countries? Temperature,
precipitation, snow depth, frost/ice/thaw days and rain-on-snow days, DJF and JFM, 1950 onward.

## Outputs
- `report/report.pdf`: XeLaTeX report (build: `cd report && latexmk -xelatex report.tex`).
- `app/index.html`: offline interactive app. Double-click it; no server needed.
- `graphs_export/*.png`, `report/figures/*.pdf`: figures.
- `data/processed/*.csv`: ENSO labels, seasonal metrics, composites, contrasts.

## Pipeline
```bash
python3.13 -m pip install -r requirements.txt
python3.13 src/run_all.py            # fetch (cached) → metrics → analysis → figures → app data
python3.13 src/run_all.py --no-fetch # offline rebuild
```
Steps: `enso.py` (NOAA ONI → winter labels) → `fetch_fmi.py` (FMI WFS, one year per request) →
`fetch_ghcn.py` (NOAA GHCN-Daily, Nordic stations) → `fetch_openmeteo.py` (ERA5 cross-check,
quota-limited) → `metrics.py` → `analysis.py` → `figures.py` → `build_app_data.py`.

## Data sources and their limits
- **FMI open data**: daily obs from 1959 for most stations (Kaisaniemi 1900, Sodankylä 1908).
  Max 8928 h per request. `rrday`/`snow` of -1 = none (set to 0). Airport stations lose
  precipitation and snow around 2008.
- **GHCN-Daily** (NOAA NCEI, public): Sweden, Norway, Denmark, Iceland station series. Denmark is
  thin after 2000. `tmean` = TAVG or (TMAX+TMIN)/2.
- **Open-Meteo ERA5 archive**: one "call" = 2 weeks × ≤10 variables per location, so an 86-year
  series ≈ 2 260 calls against a free quota of 10 000/day. Only a few cross-check points are fetched;
  the fetcher caches and resumes, so re-running on later days extends coverage.
- **ONI**: NOAA CPC, ERSSTv5. Event = ≥5 consecutive overlapping seasons with |ONI| ≥ 0.5.

## Method summary
Seasonal metrics per station and winter (≥90 % daily completeness) → anomaly vs 1991–2020 →
detrended anomaly (OLS residual over all winters of that station/season/metric; primary) →
group means with bootstrap 95 % CI, pairwise differences with permutation p, Welch t,
Mann-Whitney U, Cohen's d; Spearman ρ against DJF ONI. National series = mean of station anomalies.

## Publishing the app on rikhard.fi (GitHub Pages + Squarespace embed)
Squarespace cannot serve the data bundle from a code block, so the app is hosted on GitHub Pages and
embedded in the blog post.
1. Repository: https://github.com/rikhardfi/el-nino-years (public; Pages on the free plan needs a public
   repo). `data/raw/` is ignored; `app/` is what gets published (~25 MB with the daily files).
2. Pages source = "GitHub Actions". The workflow in `.github/workflows/pages.yml` publishes `app/` on
   every push to `main`. Live app: https://rikhardfi.github.io/el-nino-years/
   Deep links: `?preset=olos` opens the Muonio (Olos) November view, `?lang=fi` the Finnish UI.
3. Optional custom subdomain: add a `CNAME` file in `app/` with e.g. `elnino.rikhard.fi` and a DNS CNAME
   record `elnino → <user>.github.io` at the registrar; enable "Enforce HTTPS" in Pages.
4. In Squarespace, add a Code block to the post:
   `<iframe src="https://rikhardfi.github.io/el-nino-years/?preset=olos" style="width:100%;height:1400px;border:0" loading="lazy" title="Nordic winters and El Niño strength"></iframe>`
   and a plain link to the full-screen version above it for phones.
5. To update: rerun the pipeline, commit, push. Pages redeploys in about a minute.
