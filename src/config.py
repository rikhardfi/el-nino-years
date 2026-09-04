"""Project configuration: paths, sites, seasons, ENSO thresholds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_FMI = ROOT / "data" / "raw" / "fmi"
RAW_OM = ROOT / "data" / "raw" / "openmeteo"
PROCESSED = ROOT / "data" / "processed"
FIGDIR = ROOT / "report" / "figures"
PNGDIR = ROOT / "graphs_export"
APPDATA = ROOT / "app" / "data"

END_DATE = "2026-08-31"

# ENSO
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
ENSO_THRESHOLD = 0.5      # |ONI| >= 0.5 for >= 5 consecutive overlapping seasons
SUPER_THRESHOLD = 2.0     # event peak ONI >= 2.0 → "super" El Niño
MIN_SEASONS = 5

# Climatology baseline for anomalies
BASE_START, BASE_END = 1991, 2020

# Seasons: name -> list of (month, year_offset) relative to the winter label year
# Winter label year = year of January (e.g. winter 1997/98 -> 1998)
SEASONS = {
    "DJF": [(12, -1), (1, 0), (2, 0)],
    "JFM": [(1, 0), (2, 0), (3, 0)],
    "NDJFM": [(11, -1), (12, -1), (1, 0), (2, 0), (3, 0)],
}

# FMI stations: fmisid -> (short name, first year to fetch, lat, lon)
FMI_STATIONS = {
    100971: ("Helsinki Kaisaniemi", 1900, 60.17523, 24.94459),
    101065: ("Turku lentoasema", 1959, 60.515647, 22.279155),
    101104: ("Jokioinen Ilmala", 1959, 60.813972, 23.498250),
    101118: ("Tampere-Pirkkala", 1980, 61.419402, 23.622561),
    101237: ("Lappeenranta lentoasema", 1959, 61.040298, 28.129162),
    101462: ("Vaasa lentoasema", 1959, 63.058578, 21.754597),
    101520: ("Ähtäri Inha", 1959, 62.554614, 24.142386),
    101572: ("Kuopio Maaninka", 1959, 63.143426, 27.313171),
    101725: ("Kajaani lentoasema", 1959, 64.282904, 27.671137),
    101786: ("Oulu lentoasema", 1959, 64.935034, 25.339195),
    101933: ("Rovaniemi Apukka", 1959, 66.579444, 26.010944),
    101932: ("Sodankylä Tähtelä", 1908, 67.36663, 26.62901),
    102035: ("Utsjoki Kevo", 1962, 69.756365, 27.006784),
}
FMI_PARAMS = ["tday", "tmax", "tmin", "rrday", "snow"]

# Open-Meteo ERA5 points: id -> (name, country, lat, lon)
OM_POINTS = {
    "stockholm": ("Stockholm", "SE", 59.33, 18.07),
    "goteborg": ("Göteborg", "SE", 57.71, 11.97),
    "malmo": ("Malmö", "SE", 55.60, 13.00),
    "ostersund": ("Östersund", "SE", 63.18, 14.64),
    "lulea": ("Luleå", "SE", 65.58, 22.15),
    "kiruna": ("Kiruna", "SE", 67.86, 20.23),
    "oslo": ("Oslo", "NO", 59.91, 10.75),
    "bergen": ("Bergen", "NO", 60.39, 5.32),
    "trondheim": ("Trondheim", "NO", 63.43, 10.40),
    "lillehammer": ("Lillehammer", "NO", 61.12, 10.47),
    "tromso": ("Tromsø", "NO", 69.65, 18.96),
    "copenhagen": ("Copenhagen", "DK", 55.68, 12.57),
    "aarhus": ("Aarhus", "DK", 56.16, 10.20),
    "aalborg": ("Aalborg", "DK", 57.05, 9.92),
    "reykjavik": ("Reykjavík", "IS", 64.15, -21.94),
    "akureyri": ("Akureyri", "IS", 65.68, -18.09),
    "egilsstadir": ("Egilsstaðir", "IS", 65.26, -14.39),
}
# Also fetch ERA5 at the FMI station coordinates (cross-check + extends to 1940)
for _sid, (_n, _y, _lat, _lon) in FMI_STATIONS.items():
    OM_POINTS[f"fi_{_sid}"] = (_n, "FI", _lat, _lon)

COUNTRY_NAMES = {"FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "IS": "Iceland"}

# GHCN-Daily (NOAA NCEI) stations for the other Nordic countries: id -> (name, country)
# Chosen for long, continuous TMAX/TMIN/PRCP records. Denmark's coverage in GHCN is patchy;
# four stations are combined and ERA5 (Open-Meteo) is queued as the cross-check.
GHCN_STATIONS = {
    "SWM00002485": ("Stockholm", "SE"),
    "SWE00138198": ("Göteborg", "SE"),
    "SWE00137620": ("Kristianstad", "SE"),
    "SW000010537": ("Falun", "SE"),
    "SW000002361": ("Härnösand", "SE"),
    "SWE00140492": ("Piteå", "SE"),
    "SWE00140886": ("Vittangi", "SE"),
    "NOM00001492": ("Oslo Blindern", "NO"),
    "NOE00110653": ("Bergen Flesland", "NO"),
    "NOE00109680": ("Stavanger Sola", "NO"),
    "NOE00112071": ("Trondheim Værnes", "NO"),
    "NO000001026": ("Tromsø", "NO"),
    "NOE00109394": ("Bardufoss", "NO"),
    "DAM00006030": ("Aalborg", "DK"),
    "DA000030380": ("København Landbohøjskolen", "DK"),
    "DA000021100": ("Vestervig", "DK"),
    "DA000032020": ("Hammer Odde", "DK"),
    "IC000004030": ("Reykjavík", "IS"),
    "IC000004013": ("Stykkishólmur", "IS"),
    "IC000004063": ("Akureyri", "IS"),
    "IC000004097": ("Dalatangi", "IS"),
    "FI000007501": ("Sodankylä (GHCN)", "FI"),
    "FIE00146423": ("Muonio Alamuonio", "FI"),   # nearest long record to Olos (5 km)
}
RAW_GHCN = ROOT / "data" / "raw" / "ghcn"
GHCN_STATIONS_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
