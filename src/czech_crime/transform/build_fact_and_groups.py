"""Build the crime fact + type-group dimension and bridge from the coded Parquet.

Resolves the many-to-many `types` array into a *type-group* (combination)
dimension so the fact stays one row per incident with a single FK:

    fact_crime ──► dim_type_group ◄── bridge_group_type ──► dim_type

Outputs (under data/processed):
    fact_crime.parquet     single file, one row per incident
    dim_type_group.*       one row per distinct sorted type-combination (~14.8k)
    bridge_group_type.*    (type_group_key, type_code) association (~107k)

dim_type / dim_state / dim_relevance are built by build_dims.py.
"""
import collections

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from ..config import AREAS_DIR, PROCESSED_DIR
from ..io import write_small

FACT_COLS = ["id", "date", "mp", "state", "relevance",
             "longitude", "latitude", "kod_zuj", "kod_obec", "kod_momc"]


def scan_combinations(dataset):
    """Return (combo -> incident count, type code -> total occurrences)."""
    combos, typefreq = collections.Counter(), collections.Counter()
    for batch in dataset.scanner(columns=["types"]).to_batches():
        for arr in batch.column("types").to_pylist():
            combo = tuple(sorted(arr))
            combos[combo] += 1
            typefreq.update(combo)
    return combos, typefreq


def build_group_tables(combos, typefreq):
    """Write dim_type_group + bridge; return the lookups the fact pass needs."""
    # Stable surrogate keys: most-frequent combination gets key 1
    ordered = sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))
    combo2key = {combo: i for i, (combo, _) in enumerate(ordered, 1)}

    # primary_type heuristic: the globally *least* frequent member of the set
    # (most distinctive), ties broken by lowest code. Replace with the official
    # crime-type codelist's severity/hierarchy once available.
    primary = {c: min(c, key=lambda t: (typefreq[t], t)) for c in combos}

    dtg = pd.DataFrame(
        [(combo2key[c], "|".join(map(str, c)), len(c), primary[c], n)
         for c, n in ordered],
        columns=["type_group_key", "type_set_label", "n_types",
                 "primary_type", "incident_count"],
    ).astype({"type_group_key": "int32", "n_types": "int32",
              "primary_type": "int32", "incident_count": "int64"})
    write_small(dtg, "dim_type_group")

    bridge = pd.DataFrame(
        [(combo2key[c], code) for c in combos for code in c],
        columns=["type_group_key", "type_code"],
    ).astype("int32")
    write_small(bridge, "bridge_group_type")

    key2primary = {combo2key[c]: p for c, p in primary.items()}
    return combo2key, key2primary


def write_fact(dataset, combo2key, key2primary):
    """Stream every fragment into ONE parquet file (simplest for Power BI)."""
    fact_path = PROCESSED_DIR / "fact_crime.parquet"
    # types arrays are usually already sorted; memoise on the raw tuple so
    # sorted() runs once per distinct raw array, not once per incident
    raw2key = {}

    def group_key(arr):
        raw = tuple(arr)
        key = raw2key.get(raw)
        if key is None:
            key = raw2key[raw] = combo2key[tuple(sorted(raw))]
        return key

    writer, total = None, 0
    try:
        for frag in dataset.get_fragments():
            df = frag.to_table(columns=FACT_COLS + ["types"]).to_pandas()
            keys = df.pop("types").map(group_key)
            df["type_group_key"] = keys.astype("int32")
            df["primary_type"] = keys.map(key2primary).astype("int32")
            # naive LOCAL (Europe/Prague) wall-clock time, plus an integer
            # YYYYMMDD date_key for the dim_date join
            local = df["date"].dt.tz_convert("Europe/Prague").dt.tz_localize(None)
            df["date"] = local
            df["date_key"] = (local.dt.year * 10000 + local.dt.month * 100
                              + local.dt.day).astype("int32")
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(str(fact_path), table.schema,
                                          compression="zstd")
            writer.write_table(table)
            total += len(df)
    finally:
        if writer is not None:
            writer.close()
    print(f"  fact_crime: {total:,} rows")


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dataset = ds.dataset(str(AREAS_DIR), partitioning="hive")

    print("Pass 1: scanning type combinations ...")
    combos, typefreq = scan_combinations(dataset)
    print("Building type-group dimension + bridge ...")
    combo2key, key2primary = build_group_tables(combos, typefreq)

    print("Pass 2: writing fact_crime.parquet ...")
    write_fact(dataset, combo2key, key2primary)
    print("\nDone.")


if __name__ == "__main__":
    main()
