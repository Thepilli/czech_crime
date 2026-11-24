"""Batch point-in-polygon assignment over all monthly GeoJSON files.

Loads the Voronoi territory polygons ONCE, then for every data/raw/YYYYMM.geojson:
  - spatially joins each crime point to its territory (kod_zuj/kod_obec/kod_momc),
  - assembles a flat table (original properties + coords + codes),
  - appends it to a Parquet dataset partitioned by year / month.

Resumable: months whose partition already exists are skipped.
Pass month(s) as arguments (YYYYMM) to restrict the run.
"""
import argparse

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..config import AREAS_DIR, GPKG, GPKG_LAYER, RAW_DIR

TERRITORY_COLS = ["kod_zuj", "kod_obec", "kod_momc"]

# Output schema incl. the hive partition columns
SCHEMA = pa.schema([
    ("id", pa.int64()),
    ("date", pa.timestamp("us", tz="UTC")),
    ("mp", pa.bool_()),
    ("state", pa.int32()),
    ("relevance", pa.int32()),
    ("types", pa.list_(pa.int32())),
    ("longitude", pa.float64()),
    ("latitude", pa.float64()),
    *[(c, pa.int32()) for c in TERRITORY_COLS],
    ("year", pa.int32()),
    ("month", pa.int32()),
])


def month_done(ym: str) -> bool:
    """A partition dir with at least one file means this month is written."""
    d = AREAS_DIR / f"year={ym[:4]}" / f"month={int(ym[4:6])}"
    return d.is_dir() and any(d.iterdir())


def to_int_list(v):
    try:
        return [int(x) for x in v]
    except TypeError:  # None / NaN
        return None


def assign_month(ym: str, poly: gpd.GeoDataFrame) -> int:
    """Join one month's points to territories and write its partition."""
    pts = gpd.read_file(RAW_DIR / f"{ym}.geojson")
    if pts.empty:
        return 0
    if pts.crs != poly.crs:
        pts = pts.to_crs(poly.crs)
    pts["longitude"] = pts.geometry.x
    pts["latitude"] = pts.geometry.y

    joined = gpd.sjoin(pts, poly, how="left", predicate="within")
    # a point exactly on a shared border can match >1 polygon -> keep the first
    joined = joined[~joined.index.duplicated(keep="first")]
    unmatched = int(joined["kod_zuj"].isna().sum())
    if unmatched:
        print(f"  WARNING {ym}: {unmatched} point(s) outside every polygon")

    df = pd.DataFrame({
        "id": joined["id"],
        "date": pd.to_datetime(joined["date"], utc=True),
        "mp": joined["mp"],
        "state": joined["state"],
        "relevance": joined["relevance"],
        "types": joined["types"].apply(to_int_list),
        "longitude": joined["longitude"],
        "latitude": joined["latitude"],
        **{c: joined[c].astype("Int32") for c in TERRITORY_COLS},
        "year": int(ym[:4]),
        "month": int(ym[4:6]),
    })
    # SCHEMA does the dtype casting
    table = pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False)
    pq.write_to_dataset(table, root_path=str(AREAS_DIR),
                        partition_cols=["year", "month"], compression="zstd")
    return len(df)


def main(only=None):
    print("Loading territory polygons ...")
    poly = gpd.read_file(GPKG, layer=GPKG_LAYER, columns=TERRITORY_COLS)
    print(f"  {len(poly)} polygons, crs={poly.crs}")

    months = sorted(f.stem for f in RAW_DIR.glob("??????.geojson"))
    if only:
        missing = set(only) - set(months)
        if missing:
            raise SystemExit(f"No raw file for: {', '.join(sorted(missing))}")
        months = [m for m in months if m in only]

    total = done = skipped = 0
    for i, ym in enumerate(months, 1):
        if month_done(ym):
            skipped += 1
            continue
        n = assign_month(ym, poly)
        total += n
        done += 1
        print(f"[{i}/{len(months)}] {ym}: {n:,} points")

    print(f"\nDone. months_written={done} skipped={skipped} "
          f"points_written={total:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("months", nargs="*", help="YYYYMM (default: all)")
    main(set(ap.parse_args().months) or None)
