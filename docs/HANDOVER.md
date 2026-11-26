# Handover: czech_crime

## State
- **Repo:** restructured and refactored, but nothing is committed. All changes are staged or in the working tree, so review `git status` before committing.
- **Pipeline:** full rebuild done (2026-11-25). All 179 months are in `data/interim` (the last partition of an interrupted run, 2025-03, was deleted and rewritten). `data/processed` holds `fact_crime` (18,536,745 rows, 2012-01-04 .. 2026-11-28), `dim_type_group` (15,151), `bridge_group_type` (109,982), `dim_date` (5,479, 2012–2026) and the code-list dims. Logs: `logs/assign_areas.log`, `logs/build_fact_date.log`.
- **Source data quirk:** one incident in `202611.geojson` is dated 2026-11-28, after the download date.
- **Deployed (2026-11-26):** lakehouse tables reloaded, lake-view notebook re-run and the semantic model published, all without errors. The report was checked and works.

## Layout
```
src/czech_crime/   config.py (all paths + START/END), io.py (write_small)
  ingest/          download_months.py, load_demographics.py
  transform/       assign_areas.py, build_dims.py, build_fact_and_groups.py, build_date_dim.py
  run_all.py       chains the crime pipeline (demographics are separate)
data/{raw,interim,processed}   gitignored      logs/   gitignored
reference/         codelists/ + territory/ (tracked inputs)
geodata/           split/, split_okres/  <- DO NOT RENAME
powerbi/           PBIP project, tabular-editor/, measures/*.dax
docs/              semantic-model.md, report-ideas.md, HANDOVER.md
```
Setup: `uv venv .venv && uv pip install --python .venv -e .`, then run steps as `.venv/Scripts/python -m czech_crime.<pkg>.<module>` (the global `python` has no geopandas/pyarrow). `README.md` and `CLAUDE.md` have the full commands.

## Key facts
- **Many-to-many crime types:** the fact has one row per incident and a single FK to `dim_type_group`. Don't join the fact to types directly, because it double-counts.
- **Dates/times:** Python converts to Europe/Prague and writes `fact_crime.crime_date` (→ `dim_date[Date]`) and `time_key` (minute of day → `d_time[TimeKey]`). `dim_date` columns already have their model names. Keep the lake views in `powerbi/create_mv_lake_views_crime.ipynb` as thin projections.
- **Map URLs:** `geodata/split*` is loaded by Power BI through hard-coded `raw.githubusercontent.com/.../main/...` URLs built in the `crime.mv_d_uzemi` lake view (`kraj_json_url`, `okres_json_url`). Moving or renaming those folders breaks the maps, and the URLs only work for what's pushed to `main`.
- **Power BI source:** the model reads Fabric DirectLake tables (lakehouse `LH_JP_data`, schema `crime`), not local files. The load from `data/processed` into the lakehouse isn't in this repo.
- **Demographics:** `load_demographics` needs the CZSO Excel folder as an argument, and its 2026 rows are a placeholder copied from 2025.

## What changed
- **Restructure:**
  - Scripts moved into the package.
  - Paths and the date range centralised in `config.py`.
  - The two `assign_areas` scripts merged into one.
  - The notebook turned into `load_demographics.py`.
  - Dead `geodata/split_kraj_okres/`, tracked `__pycache__` and tracked logs removed.
- **Refactor:**
  - Fixed a startup bug in `download_months` (`"data".mkdir`) introduced in the move.
  - Atomic file writes for downloads.
  - `build_fact_and_groups` split into three functions, with the sort memoised.
  - Deprecated pandas calls replaced.
  - On 2026 data the new fact build matched the old script exactly.
- **Download range:** `START` was reset to `(2012, 1)`. The previous uncommitted edit had it at 2026.
- **Model simplification:**
  - `H_Map` / `H_Map_okres` (91 hard-coded URLs, two two-way relationships) replaced by `kraj_json_url` / `okres_json_url` on `mv_d_uzemi`; the two `SELECTEDVALUE of …_topojson` measures moved there and the two map visuals were repointed.
  - `H_Icons` (two-way relationship) replaced by `d_type[category_color]` / `[category_svg]`, built by `build_dims` from `reference/codelists/category_icons.json`.
  - Fact joins `d_time` on the integer `TimeKey` instead of an `"HH:mm"` string; `CrimeTime` and `DateKey` are gone; `YearMonthNumber` is an integer; `MonthLetterCs` no longer repeats L (leden/listopad) and Č (červen/červenec); `DayNameCs` sorts by `DayofWeek`.
  - Demographics measures use three shared functions (`Common.Demo.InSelectedYears`, `.AtYear`, `.YearAvg`) instead of repeating the year-matching logic; stale comments removed from `Crime rate`.

## Deploy order (for future model changes that add lakehouse columns)
1. Reload the lakehouse tables from `data/processed`: `f_crime` (new `crime_date`, `time_key`; no `date`/`date_key`), `d_date` (new column names), `d_type` (new `category_color`, `category_svg`), `d_type_group`, `b_group_type`.
2. Re-run `powerbi/create_mv_lake_views_crime.ipynb` (`mv_d_uzemi` gains the URL columns; `mv_f_crime` and `mv_d_date` are now pass-through).
3. Publish / open the semantic model and check the map, icon, hour-band and demographics visuals.

## Open items
1. Open `powerbi/kriminalita.pbip` in Power BI Desktop to confirm it loads after the `PBI/` → `powerbi/` rename.
2. Optional:
   - Add the lakehouse load step.
   - Add a guard in `assign_areas` for partially written month partitions. A crash mid-write currently looks "done" to the skip check.
   - Replace the `primary_type` heuristic (the least frequent type in the set) with a real severity ranking.
