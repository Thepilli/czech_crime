# czech_crime

Czech Police crime open-data (monthly GeoJSON points) → territory-coded Parquet → Power BI star schema (`powerbi/kriminalita.pbip`).

## Setup
```
python -m pip install -e .      # installs czech_crime + geopandas/pandas/pyarrow/numpy
```

## Pipeline (run from the repo root)
```
python -m czech_crime.ingest.download_months        # data/raw/YYYYMM.geojson (range in config.py)
python -m czech_crime.transform.assign_areas [YYYYMM ...]   # -> data/interim/crime_areas_parquet/
python -m czech_crime.transform.build_dims          # code-list dims
python -m czech_crime.transform.build_fact_and_groups   # fact_crime + type-group dim/bridge
python -m czech_crime.transform.build_date_dim      # needs fact_crime
python -m czech_crime.run_all                       # all of the above
python -m czech_crime.ingest.load_demographics INPUT_DIR   # separate: f_populace from CZSO Excel files
```
`data/raw/uzemi.gpkg` (Voronoi territory polygons) must be present. Steps are resumable; to refresh a still-growing month delete `data/interim/crime_areas_parquet/year=YYYY/month=M` first.

## Layout
- `src/czech_crime/` — pipeline code; `config.py` holds every path and the download range.
- `data/{raw,interim,processed}` — gitignored data layers. `logs/` — gitignored.
- `reference/` — small tracked inputs (code lists, territory registers).
- `geodata/` — per-kraj / per-okres GeoJSON served to Power BI via raw.githubusercontent.com URLs hard-coded in `powerbi/**/H_Map*.tmdl`. **Do not rename or move.**
- `powerbi/` — PBIP project, Tabular Editor macros, DAX measure drafts.
- `docs/` — semantic-model notes, report ideas.

The Power BI model reads Fabric DirectLake tables (lakehouse `LH_JP_data`), not `data/processed` directly; the load into the lakehouse is not part of this repo.
