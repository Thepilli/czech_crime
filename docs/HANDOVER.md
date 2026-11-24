# Handover: czech_crime

## State
- **Repo:** restructured and refactored, but nothing is committed. All changes are staged or in the working tree, so review `git status` before committing.
- **Pipeline run:** a full rebuild was started in the background (`assign_areas` → `build_dims` → `build_fact_and_groups` → `build_date_dim`), logging to `logs/*.log`. Completion was not confirmed at the time of writing, and the full-history numbers (17.9M facts, 2012–2026) are unverified against the new output.
- **Check first:** `logs/build_fact.log` should show about 18M `fact_crime` rows and `logs/build_date.log` should show `dim_date` for 2012–2026. If the run died partway, re-run it. It resumes per month.

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
Setup: `python -m pip install -e .`. Run steps as `python -m czech_crime.<pkg>.<module>`. `README.md` and `CLAUDE.md` have the full commands.

## Key facts
- **Many-to-many crime types:** the fact has one row per incident and a single FK to `dim_type_group`. Don't join the fact to types directly, because it double-counts.
- **Dates:** `fact_crime.date` is naive Europe/Prague time, and `date_key` (`YYYYMMDD`) joins `dim_date`.
- **Map URLs:** `geodata/split*` is loaded by Power BI through hard-coded `raw.githubusercontent.com/.../main/...` URLs in `powerbi/**/H_Map*.tmdl`. Moving or renaming those folders breaks the maps, and the URLs only work for what's pushed to `main`.
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

## Open items
1. Confirm the background run finished and the row counts look right.
2. Open `powerbi/kriminalita.pbip` in Power BI Desktop to confirm it loads after the `PBI/` → `powerbi/` rename.
3. Commit, and push if you want the map URLs to stay in sync.
4. Optional:
   - Add the lakehouse load step.
   - Add a guard in `assign_areas` for partially written month partitions. A crash mid-write currently looks "done" to the skip check.
   - Replace the `primary_type` heuristic (the least frequent type in the set) with a real severity ranking.
