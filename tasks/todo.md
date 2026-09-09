# El Niño years — Nordic winter climate vs ENSO strength

Goal: PDF report (XeLaTeX) + offline HTML5 app comparing Finnish/Nordic winter
temperature, precipitation, snow, frost/thaw days in super El Niño winters vs
normal El Niño, neutral and La Niña winters. ENSO groups from NOAA ONI (1950+).

## Plan
- [x] Verify data sources (FMI WFS daily, Open-Meteo ERA5 archive 1940+, NOAA ONI)
- [x] Pick stations: 13 FMI stations (Kaisaniemi 1900+, Sodankylä 1908+, rest 1959+);
      Nordic ERA5 points (SE 6, NO 5, DK 3, IS 3) + ERA5 at FMI coordinates
- [x] `src/enso.py` — download ONI, define events, label winters (super / El Niño / neutral / La Niña)
- [x] `src/fetch_fmi.py` — year-by-year multipointcoverage, cache CSV per station
- [x] `src/fetch_openmeteo.py` — daily (tmean/tmax/tmin/precip/rain/snowfall) + hourly snow depth → daily, paced
- [x] `src/metrics.py` — seasonal (DJF, JFM) metrics per site-winter; anomalies vs 1991–2020; detrended anomalies
- [x] `src/analysis.py` — group composites, bootstrap CIs, permutation tests, effect sizes
- [x] `src/figures.py` — matplotlib figures → report/figures (PDF) + graphs_export (PNG)
- [x] `src/build_app_data.py` — write app/data/*.js
- [x] `app/index.html` — offline D3 app: group selector, metric, season, site, map, ONI timeline
- [x] `report/report.tex` — XeLaTeX report, build with latexmk
- [x] README, journal entry

## Notes
- FMI daily query max 8928 h → one calendar year per request. rrday/snow = -1 means none → 0.
- Open-Meteo minute rate limit hit quickly on 86-year calls → pace ~10 s between calls, retry on 429.
- Turku/Oulu/Vaasa/Kajaani/Lappeenranta airports: precipitation & snow stop ~2008 (AWOS). Temperature continues.
- Tampere-Pirkkala only from 1980. No usable Jyväskylä temperature record pre-2010 in the open API; Ähtäri Inha + Kuopio Maaninka cover central Finland.

## Done 2026-09-04
- Nordic (non-FI) data switched from Open-Meteo ERA5 to NOAA GHCN-Daily station files after the
  Open-Meteo quota turned out to be ~2 260 weighted calls per 86-year series (10 000/day free).
  ERA5 kept as cross-check units (3 Swedish points fetched); `fetch_openmeteo.py` resumes on rerun.
- Detrending fitted on 1950+ only (long GHCN records would otherwise leave post-1990 warming in residuals).
- t-intervals for groups with n < 6 (bootstrap of three values is degenerate), in pipeline and app.
- Result: super winters ~+1 °C (DJF, detrended) vs neutral in FI/SE/NO/DK, Iceland cooler, FI precipitation
  +26 mm; nothing p < 0.05 by permutation; no JFM signal; Spearman rho with ONI ≈ 0.

## Open
- Run `python3.13 src/fetch_openmeteo.py` on later days to extend ERA5 cross-check points (quota).
- Consider adding SMHI / MET Norway Frost APIs for homogenised national series.

## Done 2026-09-04 (round 2)
- Muonio Alamuonio (GHCN FIE00146423) added as the Olos station (site level; FI national mean still FMI only).
- App: month-range window (Oct–Apr, presets DJF/JFM/NDJFM/November/Custom), day-range mode per site
  (per-site daily JS files, 18 MB), Olos/November preset with generated summary, 2026/27 tracker panel
  (enso_status.json from ONI + CPC synopsis), PNG export per chart, FI/EN toggle, how-to box.
- blog/olos_intro.md (EN, ~200 words + sources). GitHub Pages workflow + README publishing steps. Git repo
  initialised and staged, not committed or pushed (user decision).
- Not verified: PNG download itself (browser sandbox); file:// launch (no fetch used, should work).

## Done 2026-09-09
- App: dark theme default + light toggle, publication-style chart scaffolding, PNG export in light palette.
- Deep links `?preset=olos`, `?lang=fi|en`. Verified headless (no console errors).
- Repo public, Pages via Actions on push, release v1.0.0. Live: https://rikhardfi.github.io/el-nino-years/
- Blog numbers for Muonio Nov 1997 / Nov 2015 verified against monthly_metrics.csv.
