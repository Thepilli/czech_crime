"""Assign kod_zuj / kod_obec (and kod_momc) to crime points via point-in-polygon.

Reads the point features from a GeoJSON and the Voronoi territory polygons from a
GeoPackage, performs a spatial join (point within polygon), and writes a flat
tabular file with the original point properties plus the assigned territory codes.
"""
import argparse
import geopandas as gpd
import numpy as np
import pandas as pd


def main(points_path: str, gpkg_path: str, out_path: str, layer: str = "voronoi") -> None:
    # --- Load points ---
    pts = gpd.read_file(points_path)

    # Explicit lon/lat columns from the point geometry
    pts["longitude"] = pts.geometry.x
    pts["latitude"] = pts.geometry.y

    # --- Load territory polygons (only the columns we need) ---
    poly = gpd.read_file(gpkg_path, layer=layer,
                         columns=["kod_zuj", "kod_obec", "kod_momc"])

    # Align CRS (both are EPSG:4326, but be safe)
    if pts.crs != poly.crs:
        pts = pts.to_crs(poly.crs)

    # --- Spatial join: each point within its territory polygon ---
    joined = gpd.sjoin(pts, poly, how="left", predicate="within")

    # A point exactly on a shared border can match >1 polygon -> keep the first
    joined = joined[~joined.index.duplicated(keep="first")]

    unmatched = int(joined["kod_zuj"].isna().sum())
    if unmatched:
        print(f"WARNING: {unmatched} point(s) fell outside every polygon.")

    # --- Flatten list-valued `types` for tabular output ---
    if "types" in joined.columns:
        joined["types"] = joined["types"].apply(
            lambda v: ",".join(map(str, v))
            if isinstance(v, (list, tuple, np.ndarray)) else v
        )

    # Territory codes are integer identifiers; keep them as nullable ints
    for c in ("kod_zuj", "kod_obec", "kod_momc"):
        if c in joined.columns:
            joined[c] = joined[c].astype("Int64")

    # --- Assemble the output table (drop geometry + join bookkeeping) ---
    cols = ["id", "date", "mp", "state", "relevance", "types",
            "longitude", "latitude", "kod_zuj", "kod_obec", "kod_momc"]
    cols = [c for c in cols if c in joined.columns]
    out = pd.DataFrame(joined[cols])

    out.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Wrote {len(out)} rows -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default="202607.geojson")
    ap.add_argument("--gpkg", default="uzemi.gpkg")
    ap.add_argument("--out", default="202607_with_areas.csv")
    ap.add_argument("--layer", default="voronoi")
    args = ap.parse_args()
    main(args.points, args.gpkg, args.out, args.layer)
