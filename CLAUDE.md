# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Pipeline that turns Czech Police crime open-data (monthly GeoJSON point files) into a Power BI star-schema semantic model (`powerbi/kriminalita.pbip`). No test suite or linter. The project venv is `.venv` (`uv venv .venv && uv pip install --python .venv -e .`; src layout, deps in `requirements.txt`) — use `.venv/Scripts/python`, the global `python` has no geopandas/pyarrow. Commands and layout are in `README.md`; run modules from the repo root as `python -m czech_crime.<pkg>.<module>`.

## Architecture notes

- **Paths/range live in `src/czech_crime/config.py`** (`START`/`END` download range, data layer dirs, GPKG). Shared `write_small` (parquet + csv) is in `io.py`. Don't re-hardcode paths in scripts.
- **Stages**: `ingest/download_months` → `transform/assign_areas` (point-in-polygon vs `data/raw/uzemi.gpkg` layer `voronoi`, hive-partitioned `data/interim/crime_areas_parquet`, resumable per month) → `build_dims` → `build_fact_and_groups` → `build_date_dim` (reads `fact_crime`, so run last). `run_all` chains them. `ingest/load_demographics` (f_populace) is separate; its 2026 rows are a copy of 2025.
- **Many-to-many types**: each incident has a *set* of type codes. The fact keeps one row per incident with a single FK to `dim_type_group` (one row per distinct sorted combination); `bridge_group_type` links groups to `dim_type`. Don't fan out the fact by type — it double-counts. See `docs/semantic-model.md`.
- Python converts timestamps to Europe/Prague and writes `fact_crime.crime_date` (DATE → `dim_date[Date]`) and `time_key` (minute of day → `d_time[TimeKey]`); `dim_date` columns already carry their final model names. The Fabric lake views in `powerbi/create_mv_lake_views_crime.ipynb` should stay thin projections/renames — put derivations in Python. The interim parquet has UTC timestamps plus `year`/`month` partition columns.
- Unmatched points (outside every polygon) get null `kod_zuj/obec/momc`.
- **`geodata/split*` paths are referenced by raw.githubusercontent.com URLs built in the `crime.mv_d_uzemi` lake view (`kraj_json_url`, `okres_json_url`)** — renaming/moving breaks the Power BI maps (and the URLs only resolve for what's pushed to `main`).
- Power BI reads Fabric DirectLake tables (lakehouse `LH_JP_data`, schema `crime`), not local files; the lakehouse load is outside this repo. `data/` and `logs/` are gitignored.
- The data is dominated by minor traffic misdemeanors (category 97 Přestupky); slice on `category_name` to separate serious crime.
