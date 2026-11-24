"""Single source of truth for paths and run parameters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# --- data layers (all gitignored) ---
RAW_DIR = ROOT / "data" / "raw"                 # YYYYMM.geojson + uzemi.gpkg
INTERIM_DIR = ROOT / "data" / "interim"
AREAS_DIR = INTERIM_DIR / "crime_areas_parquet"  # hive: year=/month=
PROCESSED_DIR = ROOT / "data" / "processed"     # star-schema outputs

# --- small tracked inputs ---
CODELISTS_DIR = ROOT / "reference" / "codelists"
TERRITORY_DIR = ROOT / "reference" / "territory"

GPKG = RAW_DIR / "uzemi.gpkg"
GPKG_LAYER = "voronoi"

# --- download range (inclusive) ---
START = (2012, 1)
END = (2026, 11)
