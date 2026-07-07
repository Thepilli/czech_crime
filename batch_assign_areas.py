"""Batch point-in-polygon assignment over all monthly GeoJSON files.

Loads the Voronoi territory polygons ONCE, then for every data/YYYYMM.geojson:
  - spatially joins each crime point to its territory (kod_zuj/kod_obec/kod_momc),
  - assembles a flat table (original properties + coords + codes),
  - appends it to a single Parquet dataset partitioned by year / month.

Resumable: months whose partition already exists are skipped.
"""
import glob
import os
import re

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DATA_DIR = "data"
GPKG = "uzemi.gpkg"
LAYER = "voronoi"
OUT_DIR = "crime_areas_parquet"

# Output schema (partition cols year/month are added separately)
SCHEMA = pa.schema([
    ("id", pa.int64()),
    ("date", pa.timestamp("us", tz="UTC")),
    ("mp", pa.bool_()),
    ("state", pa.int32()),
    ("relevance", pa.int32()),
    ("types", pa.list_(pa.int32())),
    ("longitude", pa.float64()),
    ("latitude", pa.float64()),
    ("kod_zuj", pa.int32()),
    ("kod_obec", pa.int32()),
    ("kod_momc", pa.int32()),
])


def month_done(ym):
    """A partition dir with at least one file means this month is written."""
    d = os.path.join(OUT_DIR, f"year={ym[:4]}", f"month={int(ym[4:6])}")
    return os.path.isdir(d) and any(os.scandir(d))


def to_int_list(v):
    if v is None:
        return None
    try:
        return [int(x) for x in v]
    except TypeError:
        return None


def process(ym, poly, poly_crs):
    path = os.path.join(DATA_DIR, f"{ym}.geojson")
    pts = gpd.read_file(path)
    if len(pts) == 0:
        return 0
    if pts.crs != poly_crs:
        pts = pts.to_crs(poly_crs)

    pts["longitude"] = pts.geometry.x
    pts["latitude"] = pts.geometry.y

    joined = gpd.sjoin(pts, poly, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]

    df = pd.DataFrame({
        "id": joined["id"].astype("int64"),
        "date": pd.to_datetime(joined["date"], utc=True),
        "mp": joined["mp"].astype("bool"),
        "state": joined["state"].astype("int32"),
        "relevance": joined["relevance"].astype("int32"),
        "types": joined["types"].apply(to_int_list),
        "longitude": joined["longitude"].astype("float64"),
        "latitude": joined["latitude"].astype("float64"),
        "kod_zuj": joined["kod_zuj"].astype("Int32"),
        "kod_obec": joined["kod_obec"].astype("Int32"),
        "kod_momc": joined["kod_momc"].astype("Int32"),
    })
    df["year"] = int(ym[:4])
    df["month"] = int(ym[4:6])

    full = SCHEMA.append(pa.field("year", pa.int32())) \
                 .append(pa.field("month", pa.int32()))
    table = pa.Table.from_pandas(df, schema=full, preserve_index=False)
    pq.write_to_dataset(table, root_path=OUT_DIR,
                        partition_cols=["year", "month"],
                        compression="zstd")
    return len(df)


def main():
    print("Loading territory polygons ...")
    poly = gpd.read_file(GPKG, layer=LAYER,
                         columns=["kod_zuj", "kod_obec", "kod_momc"])
    poly_crs = poly.crs
    print(f"  {len(poly)} polygons, crs={poly_crs}")

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.geojson")))
    months = [re.search(r"(\d{6})\.geojson$", f).group(1) for f in files]

    total = done = skipped = 0
    for i, ym in enumerate(months, 1):
        if month_done(ym):
            skipped += 1
            continue
        n = process(ym, poly, poly_crs)
        total += n
        done += 1
        print(f"[{i}/{len(months)}] {ym}: {n:,} points")

    print(f"\nDone. months_written={done} skipped={skipped} "
          f"points_written={total:,}")


if __name__ == "__main__":
    main()
