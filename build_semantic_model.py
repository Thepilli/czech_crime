"""Build a Power BI / Tabular star schema from the coded crime Parquet dataset.

Resolves the many-to-many `types` array into a *type-group* (combination)
dimension so the fact stays one row per incident with a single FK:

    fact_crime ──► dim_type_group ◄── bridge_group_type ──► dim_type

Outputs (under ./model):
    fact_crime.parquet     single file, one row per incident
    dim_type_group.*       one row per distinct sorted type-combination (~14.8k)
    bridge_group_type.*    (type_group_key, type_code) association (~107k)

The code-list dimensions (dim_type / dim_state / dim_relevance) are built
separately by build_dims.py from dims/*.json. Small tables are written as both
parquet and csv for easy Power BI import.
"""
import collections
import os

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

SRC = "crime_areas_parquet"
OUT = "model"
FACT_COLS = ["id", "date", "mp", "state", "relevance",
             "longitude", "latitude", "kod_zuj", "kod_obec", "kod_momc"]


def write_small(df, name):
    """Write a small dimension/bridge as both parquet and csv."""
    df.to_parquet(os.path.join(OUT, f"{name}.parquet"), index=False)
    df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False, encoding="utf-8")
    print(f"  {name}: {len(df):,} rows")


def main():
    os.makedirs(OUT, exist_ok=True)
    d = ds.dataset(SRC, partitioning="hive")

    # ---- Pass 1: distinct combinations + global per-code frequency ----
    print("Pass 1: scanning type combinations ...")
    combos = collections.Counter()      # sorted tuple -> incident count
    typefreq = collections.Counter()    # type code -> total occurrences
    for batch in d.scanner(columns=["types"]).to_batches():
        for arr in batch.column("types").to_pylist():
            combo = tuple(sorted(arr))
            combos[combo] += 1
            for c in combo:
                typefreq[c] += 1

    # Stable surrogate keys: most-frequent combination gets key 1
    ordered = sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))
    combo2key = {combo: i + 1 for i, (combo, _) in enumerate(ordered)}

    # primary_type heuristic: the globally *least* frequent member of the set
    # (most distinctive), ties broken by lowest code. Replace with the official
    # crime-type codelist's severity/hierarchy once available.
    def primary(combo):
        return min(combo, key=lambda c: (typefreq[c], c))

    key2primary = {combo2key[c]: primary(c) for c in combos}

    # ---- dim_type_group ----
    print("Building dimensions ...")
    dtg = pd.DataFrame(
        [(combo2key[c], "|".join(map(str, c)), len(c), primary(c), cnt)
         for c, cnt in ordered],
        columns=["type_group_key", "type_set_label", "n_types",
                 "primary_type", "incident_count"],
    ).astype({"type_group_key": "int32", "n_types": "int32",
              "primary_type": "int32", "incident_count": "int64"})
    write_small(dtg, "dim_type_group")

    # ---- bridge_group_type ----
    bridge = pd.DataFrame(
        [(combo2key[c], code) for c in combos for code in c],
        columns=["type_group_key", "type_code"],
    ).astype({"type_group_key": "int32", "type_code": "int32"})
    write_small(bridge, "bridge_group_type")

    # dim_type / dim_state / dim_relevance come from the real code-lists in
    # build_dims.py (dims/*.json) — this script only owns the group resolution.

    # ---- Pass 2: fact_crime, streamed into ONE parquet file ----
    # A single file is simplest for Power BI (it loads everything into VertiPaq
    # on import regardless, and gains nothing from Hive partition pruning).
    print("Pass 2: writing fact_crime.parquet ...")
    fact_path = os.path.join(OUT, "fact_crime.parquet")
    writer = None
    total = 0
    for frag in d.get_fragments():
        tbl = frag.to_table(columns=FACT_COLS + ["types"])
        df = tbl.to_pandas()
        keys = df["types"].apply(lambda a: combo2key[tuple(sorted(a))])
        df["type_group_key"] = keys.astype("int32")
        df["primary_type"] = keys.map(key2primary).astype("int32")
        df = df.drop(columns=["types"])
        # Store the date as naive LOCAL (Europe/Prague) wall-clock time — the
        # meaningful calendar for Czech data and the form Power BI handles best
        # — and derive an integer YYYYMMDD date_key for the date dimension join.
        local = df["date"].dt.tz_convert("Europe/Prague").dt.tz_localize(None)
        df["date"] = local
        df["date_key"] = (local.dt.year * 10000 + local.dt.month * 100
                          + local.dt.day).astype("int32")
        table = pa.Table.from_pandas(df, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(fact_path, table.schema, compression="zstd")
        writer.write_table(table)
        total += len(df)
    if writer is not None:
        writer.close()
    print(f"  fact_crime: {total:,} rows")
    print("\nDone.")


if __name__ == "__main__":
    main()
