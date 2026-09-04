"""Run the whole pipeline: ENSO labels → (cached) data fetch → metrics → analysis → figures → app data.

    python3.13 src/run_all.py            # everything, using cached raw data where present
    python3.13 src/run_all.py --no-fetch # skip the network steps
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["enso.py", "fetch_fmi.py", "fetch_ghcn.py", "fetch_openmeteo.py", "metrics.py", "analysis.py",
         "figures.py", "build_app_data.py", "build_daily_js.py"]


def main(argv):
    skip_fetch = "--no-fetch" in argv
    for step in STEPS:
        if skip_fetch and step.startswith("fetch_"):
            continue
        print(f"\n=== {step} ===", flush=True)
        r = subprocess.run([sys.executable, str(HERE / step)])
        if r.returncode != 0:
            if step == "fetch_openmeteo.py":
                print("Open-Meteo fetch failed or was quota-limited; continuing with cached data.", flush=True)
                continue
            sys.exit(f"{step} failed with code {r.returncode}")


if __name__ == "__main__":
    main(sys.argv[1:])
