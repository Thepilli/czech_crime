# Crime semantic model (Power BI / Tabular)

A star schema over the Czech Police crime open-data, with the many-to-many
`types` attribute resolved via a **type-group (combination) dimension** instead
of a raw fact↔type bridge.

## Why a type-group, not a raw bridge

Each incident carries a *set* of type codes (mean ~2.9, up to 27). A flat
`fact_id ↔ type_code` bridge would be **52.8M rows** and would fan the 17.9M
facts out ~3×, double-counting any additive measure.

But there are only **14,807 distinct combinations** (one covers 56% of all
rows). So we key a dimension on the *combination*: the fact keeps **one row per
incident with a single FK** (no fan-out, incident counts are trivially correct),
and a compact bridge explodes to individual type codes only when a query slices
by type.

## Tables

| Table | Grain | Rows | Role |
|---|---|---|---|
| `fact_crime` | one incident | 17.9M | fact |
| `dim_type_group` | one type-combination | 14,807 | dimension (direct FK from fact) |
| `bridge_group_type` | group × member type | 107,262 | bridge |
| `dim_type` | one type code | 132 | dimension (4-level hierarchy) |
| `dim_state` | clearance status | 4 | dimension → `fact_crime[state]` |
| `dim_relevance` | locality relevance | 6 | dimension → `fact_crime[relevance]` |
| `dim_date` | one calendar day | ~5,479 | **Date table** → `fact_crime[date_key]` |

`fact_crime` also carries `primary_type` (single-valued) for the common
"one category per incident" slice without touching the bridge.

### `dim_type` hierarchy
Built from `dims/types.json`. Every code rolls up to one of **12 top
categories** (Násilná/violent, Krádeže/theft, Podvody/fraud, Přestupky/
misdemeanors, …). Columns: `type_code, type_name, type_class, parent_code,
level (1-4), category_code, category_name`. Use
`category_name → type_class → type_name` as a Power BI drill-down hierarchy.

> Note on the data: the single most common combination `(74, 97, 120)` — 56% of
> all rows — sits entirely under category **97 Přestupky** (traffic/BESIP
> misdemeanors), so a large share of this "crime" dataset is minor offences, not
> serious crime. Slice on `category_name` to separate them.

### `fact_crime` columns
`id, date, date_key, mp, state, relevance, longitude, latitude, kod_zuj,
kod_obec, kod_momc, type_group_key, primary_type` — single parquet file.

`date` is **naive local (Europe/Prague)** wall-clock time (the calendar Czech
analysts expect; the source offsets were +01:00/+02:00). `date_key` is the
integer `YYYYMMDD` of that local date and is the join to `dim_date`. There are
no `year`/`month` columns on the fact — get those from `dim_date`.

### `dim_date`
Contiguous daily table over full calendar years spanning the data (2012–2026),
keyed by `date_key`. Attributes: `date, year, quarter, year_quarter, month,
month_name(_cs), year_month, month_start, day, day_of_week (1=Mon), day_name(_cs),
day_of_year, iso_week, iso_year, is_weekend`. In Power BI, **Table tools → Mark
as date table** (using `date`), and build a `year → quarter → month → date`
drill hierarchy. Czech month/day names are included alongside the English ones.

> Still open: join `kod_obec` / `kod_zuj` to a territory dimension (from
> `struktura_uzemi_cr.csv` / `CIS0051_CS.csv`) when you want obec/okres/kraj
> names. `primary_type` uses a "least globally-frequent member of the set"
> heuristic — with the hierarchy now available you can instead roll it up to
> `category_name` via `dim_type`, or redefine it on a severity ordering.

## Relationships

| From (many) | To (one) | Cross-filter |
|---|---|---|
| `fact_crime[type_group_key]` | `dim_type_group[type_group_key]` | Single (→ fact) |
| `bridge_group_type[type_group_key]` | `dim_type_group[type_group_key]` | **Both** |
| `bridge_group_type[type_code]` | `dim_type[type_code]` | Single (→ bridge) |
| `fact_crime[primary_type]` | `dim_type[type_code]` | Single — *inactive* (avoids ambiguity with the bridge path; activate via `USERELATIONSHIP` in primary-type measures) |
| `fact_crime[state]` | `dim_state[state_code]` | Single (→ fact) |
| `fact_crime[relevance]` | `dim_relevance[relevance_code]` | Single (→ fact) |
| `fact_crime[date_key]` | `dim_date[date_key]` | Single (→ fact) |

Filter propagation when slicing by an individual type:
`dim_type → bridge → (bidirectional) dim_type_group → fact_crime`.

Only the `bridge ↔ dim_type_group` relationship is bidirectional; everything
else is single-direction.

## Core DAX measures

```DAX
-- Correct incident count regardless of how types are sliced.
Incidents := DISTINCTCOUNT ( fact_crime[id] )

-- Incidents whose PRIMARY type is the selected type (no bridge, no overlap).
Incidents by primary type :=
CALCULATE ( [Incidents], USERELATIONSHIP ( fact_crime[primary_type], dim_type[type_code] ) )

-- Share of all incidents in the current filter context.
Incident share :=
DIVIDE ( [Incidents], CALCULATE ( [Incidents], REMOVEFILTERS ( dim_type ) ) )
```

### Counting semantics — read this
With the type-group model, slicing `Incidents` by `dim_type[type_name]` shows,
for each type, every incident whose set contains that type. An incident with
3 types therefore appears under all 3 type rows — this is correct ("how many
incidents involved type X"), but the **column will not sum to the grand total**
because incidents overlap across types. `[Incidents]` uses `DISTINCTCOUNT`, so
each subtotal/total is itself always correct; just don't expect type rows to add
up. When you need a clean, additive, non-overlapping split, use
`[Incidents by primary type]` (via `primary_type`) instead.

## Loading into Power BI
Get Data → Parquet, one per table (`fact_crime.parquet` is a single file). The
smaller dimension/bridge tables are also provided as CSV for convenience.

## Regenerating
- `build_semantic_model.py` → `fact_crime.parquet`, `dim_type_group`, `bridge_group_type`
- `build_dims.py` → `dim_type`, `dim_state`, `dim_relevance` (from `dims/*.json`)
- `build_date_dim.py` → `dim_date` (run after the fact exists — it reads its date span)
