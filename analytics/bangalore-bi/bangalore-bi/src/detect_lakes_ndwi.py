"""
Detect lakes / water bodies from an NDWI band, using the same connected-component engine as the BIs.

NDWI = (Green - NIR) / (Green + NIR)   (McFeeters). Water is positive; vegetation and soil are negative.
NDVI alone is a poor water detector (shadows and dark roofs also have low NDVI), so lakes use NDWI.

Input: a GeoTIFF whose band 2 is NDWI (the Earth Engine script gee/export_ndvi_ndwi.js writes
band 1 = NDVI, band 2 = NDWI on the same grid).

    python ../src/detect_lakes_ndwi.py --raster Bangalore_NDVI_NDWI.tif --boundary bbmp_boundary_FINAL.geojson

Options worth knowing
  --threshold 0.0   standard water threshold. Marsh and damp ground can also be > 0 and get merged with the
                    lake next to them; 0.2 was tried to keep open water only.
  --bridge-iterations 2   removes thin channels that join two separate waterbodies (default 0 = off).

Status: tested on synthetic data only (tests/test_detect_bis.py). It has NOT yet been run on the real NDWI band.
The detected area is "pixels classified as open water in the composite", which is not the same thing as an
official lake boundary or tank-bed area -- see README, "Known limitations".
"""
import argparse
import os

import numpy as np

from detect_bis import (break_thin_bridges, clip_to_boundary, detect_patches, load_raster_utm,
                        read_boundary, to_geodataframe)


def run(raster, boundary_path=None, out_dir=".", band=2, threshold=0.0, min_acres=1.0,
        bridge_iterations=0, write=True):
    ndwi, t, crs = load_raster_utm(raster, band=band)
    if boundary_path:
        ndwi, t = clip_to_boundary(ndwi, t, crs, read_boundary(boundary_path, crs))
    pixel_area = abs(t.a * t.e)
    water = np.isfinite(ndwi) & (ndwi > threshold)
    if bridge_iterations > 0:
        water = break_thin_bridges(water, bridge_iterations)
    lakes = detect_patches(water, ndwi, min_acres, None, t, pixel_area)
    gdf = to_geodataframe(lakes, crs, value_name="mean_ndwi").sort_values("area_acres", ascending=False)
    print(f"lakes >= {min_acres} acre (NDWI > {threshold}): {len(gdf)}")
    if len(gdf):
        print("largest:\n", gdf[["ID", "area_acres", "mean_ndwi", "lat", "lon"]].head(5).to_string(index=False))
    if write:
        os.makedirs(out_dir, exist_ok=True)
        gdf.to_file(os.path.join(out_dir, "lakes.geojson"), driver="GeoJSON")
        gdf.drop(columns="geometry").to_csv(os.path.join(out_dir, "lakes_summary.csv"), index=False)
        print("saved lakes.geojson, lakes_summary.csv ->", out_dir)
    return gdf


def main():
    p = argparse.ArgumentParser(description="Detect lakes from an NDWI band.")
    p.add_argument("--raster", required=True, help="GeoTIFF with NDWI in --band")
    p.add_argument("--band", type=int, default=2)
    p.add_argument("--boundary", default=None)
    p.add_argument("--out", default=".")
    p.add_argument("--threshold", type=float, default=0.0)
    p.add_argument("--min-acres", type=float, default=1.0, help="ignore waterbodies smaller than this")
    p.add_argument("--bridge-iterations", type=int, default=0)
    a = p.parse_args()
    run(a.raster, a.boundary, a.out, a.band, a.threshold, a.min_acres, a.bridge_iterations)


if __name__ == "__main__":
    main()
