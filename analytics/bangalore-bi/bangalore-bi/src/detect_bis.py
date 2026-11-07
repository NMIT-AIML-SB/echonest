"""
Detect biodiversity islands (BIs) from an NDVI GeoTIFF.

Algorithm (works for any area, nothing is specific to Bangalore):
  1. Read the NDVI raster and reproject it to a metric CRS (UTM zone picked automatically),
     so that areas are in real square metres / acres.
  2. Optionally clip to a boundary polygon (e.g. the city limits); pixels outside become "no data".
  3. Green pixel = NDVI >= THRESHOLD (default 0.4).
  4. Optional "thin-bridge fix": erosion followed by dilation removes 1-pixel-wide strips, so two
     patches joined only by a thin strip are not merged into one BI (see README, "Known limitations").
  5. Connected components with 8-connectivity: touching green pixels (including diagonals) = one BI.
  6. For every BI: pixel list, boundary polygon, area (acres), mean NDVI, centroid (lat/lon).
  7. microBI = area from MICRO_MIN to MICRO_MAX acres (default 0.5 - 4);  macroBI = larger than MICRO_MAX.

Run (from your working folder):
    python ../src/detect_bis.py --ndvi Bangalore_NDVI.tif --boundary bbmp_boundary_FINAL.geojson
Writes:  microBIs_full.geojson, macroBIs.geojson, microBIs_summary.csv, macroBIs_summary.csv
"""
import argparse
import os
from collections import defaultdict

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.io
from rasterio.features import shapes
from rasterio.mask import mask as rio_mask
from rasterio.warp import Resampling, calculate_default_transform, reproject
from scipy import ndimage
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

SQM_PER_ACRE = 4046.8564224
STRUCT8 = np.ones((3, 3))          # 8-connectivity: all 8 neighbours, diagonals included


def utm_crs_for_bounds(bounds):
    """UTM zone for a lon/lat bounding box (left, bottom, right, top)."""
    lon = (bounds[0] + bounds[2]) / 2
    lat = (bounds[1] + bounds[3]) / 2
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def load_raster_utm(path, band=1, utm_crs="auto"):
    """Read one band and reproject it to UTM. Returns (array, transform, crs_string)."""
    with rasterio.open(path) as src:
        data = src.read(band).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            data[data == src.nodata] = np.nan
        crs = utm_crs
        if utm_crs == "auto":
            crs = utm_crs_for_bounds(src.bounds) if src.crs.is_geographic else src.crs.to_string()
        if src.crs.to_string() == crs:
            return data, src.transform, crs
        t, w, h = calculate_default_transform(src.crs, crs, src.width, src.height, *src.bounds)
        out = np.full((h, w), np.nan, dtype="float32")
        reproject(data, out, src_transform=src.transform, src_crs=src.crs, dst_transform=t,
                  dst_crs=crs, resampling=Resampling.bilinear)
    return out, t, crs


def read_boundary(boundary_path, crs):
    """One boundary geometry (all polygons unioned) in the given CRS."""
    b = gpd.read_file(boundary_path)
    if b.crs is None:
        b = b.set_crs("EPSG:4326")
    return b.to_crs(crs).geometry.union_all()


def clip_to_boundary(arr, transform, crs, boundary_geom):
    """Pixels outside the boundary become NaN; the array is cropped to the boundary's bounding box."""
    profile = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                   dtype="float32", crs=crs, transform=transform)
    with rasterio.io.MemoryFile() as mf:
        with mf.open(**profile) as ds:
            ds.write(arr[np.newaxis])
        with mf.open() as ds:
            clipped, t = rio_mask(ds, [mapping(boundary_geom)], crop=True, nodata=np.nan)
    return clipped[0], t


def break_thin_bridges(mask, iterations=1):
    """Morphological opening: removes strips thinner than about 2*iterations+1 pixels."""
    eroded = ndimage.binary_erosion(mask, structure=STRUCT8, iterations=iterations)
    return ndimage.binary_dilation(eroded, structure=STRUCT8, iterations=iterations)


def detect_patches(mask, value_raster, min_acres, max_acres, transform, pixel_area_sqm):
    """
    Connected components (8-connectivity) of `mask`, kept if min_acres <= area <= max_acres
    (max_acres=None means no upper limit). Returns a list of dicts, one per BI:
    id, pixel_count, area_acres, mean_value, boundary (shapely polygon), pixels [(row, col), ...].
    Statistics are computed for all components at once (vectorised), polygons only for the kept ones.
    """
    labeled, n = ndimage.label(mask.astype("uint8"), structure=STRUCT8)
    if n == 0:
        return []
    ids = np.arange(1, n + 1)
    counts = ndimage.sum(mask, labeled, index=ids)
    acres = counts * pixel_area_sqm / SQM_PER_ACRE
    keep = acres >= min_acres if max_acres is None else (acres >= min_acres) & (acres <= max_acres)
    valid = ids[keep]
    if len(valid) == 0:
        return []
    means = ndimage.mean(value_raster, labeled, index=valid)
    lookup = np.zeros(n + 1, dtype=bool)
    lookup[valid] = True
    filtered = np.where(lookup[labeled], labeled, 0).astype(labeled.dtype)
    polys = defaultdict(list)
    for geom, v in shapes(filtered, mask=filtered > 0, transform=transform):
        polys[int(v)].append(shape(geom))
    objects = ndimage.find_objects(labeled)
    out = []
    for i, lab in enumerate(valid):
        parts = polys.get(int(lab))
        slc = objects[lab - 1]
        if not parts or slc is None:
            continue
        rows, cols = np.where(labeled[slc] == lab)
        out.append({
            "id": i + 1,
            "pixel_count": int(counts[lab - 1]),
            "area_acres": float(acres[lab - 1]),
            "mean_value": float(means[i]),
            "boundary": parts[0] if len(parts) == 1 else unary_union(parts),
            "pixels": list(zip((rows + slc[0].start).tolist(), (cols + slc[1].start).tolist())),
        })
    return out


def to_geodataframe(patches, crs, value_name="mean_ndvi"):
    """GeoDataFrame in lat/lon with ID, area, mean value, pixel count and centroid lat/lon."""
    cols = ["ID", "area_acres", value_name, "pixel_count", "lat", "lon", "geometry"]
    if not patches:
        return gpd.GeoDataFrame({c: [] for c in cols}, geometry="geometry", crs="EPSG:4326")
    g = gpd.GeoDataFrame([{"ID": p["id"], "area_acres": round(p["area_acres"], 3),
                           value_name: round(p["mean_value"], 4), "pixel_count": p["pixel_count"],
                           "geometry": p["boundary"]} for p in patches], crs=crs)
    c = gpd.GeoSeries(g.geometry.centroid, crs=crs).to_crs("EPSG:4326")   # centroid in metres, then lat/lon
    g["lat"], g["lon"] = c.y.values, c.x.values
    return g.to_crs("EPSG:4326")


def run(ndvi_path, boundary_path=None, out_dir=".", threshold=0.4, micro_min=0.5, micro_max=4.0,
        bridge_fix=True, bridge_iterations=1, utm_crs="auto", write=True):
    ndvi, t, crs = load_raster_utm(ndvi_path, utm_crs=utm_crs)
    boundary = None
    if boundary_path:
        boundary = read_boundary(boundary_path, crs)
        ndvi, t = clip_to_boundary(ndvi, t, crs, boundary)
    pixel_area = abs(t.a * t.e)
    print(f"grid {ndvi.shape}, CRS {crs}, pixel area {pixel_area:.2f} sq m")

    green = np.isfinite(ndvi) & (ndvi >= threshold)
    if bridge_fix:
        green = break_thin_bridges(green, bridge_iterations)
    micro = detect_patches(green, ndvi, micro_min, micro_max, t, pixel_area)
    macro = detect_patches(green, ndvi, micro_max, None, t, pixel_area)
    micro_gdf = to_geodataframe(micro, crs)
    macro_gdf = to_geodataframe(macro, crs)
    print(f"microBIs ({micro_min}-{micro_max} acres): {len(micro_gdf)} | macroBIs (> {micro_max} acres): {len(macro_gdf)}")

    result = {"micro": micro_gdf, "macro": macro_gdf, "micro_patches": micro, "macro_patches": macro}
    if boundary is not None and len(micro_gdf):
        b_ll = gpd.GeoSeries([boundary], crs=crs).to_crs("EPSG:4326").iloc[0]
        for name, g in (("microBIs", micro_gdf), ("macroBIs", macro_gdf)):
            pts = gpd.GeoSeries(gpd.points_from_xy(g["lon"], g["lat"]), crs="EPSG:4326")
            n_out = int((~pts.within(b_ll)).sum())
            print(f"check: {name} with centroid outside the boundary: {n_out} of {len(g)}")
            result[f"{name}_outside"] = n_out
    if write:
        os.makedirs(out_dir, exist_ok=True)
        cols = ["ID", "area_acres", "mean_ndvi", "pixel_count", "lat", "lon"]
        micro_gdf.to_file(os.path.join(out_dir, "microBIs_full.geojson"), driver="GeoJSON")
        macro_gdf.to_file(os.path.join(out_dir, "macroBIs.geojson"), driver="GeoJSON")
        micro_gdf[cols].to_csv(os.path.join(out_dir, "microBIs_summary.csv"), index=False)
        macro_gdf[cols].to_csv(os.path.join(out_dir, "macroBIs_summary.csv"), index=False)
        print("saved microBIs_full.geojson, macroBIs.geojson, microBIs_summary.csv, macroBIs_summary.csv ->", out_dir)
    return result


def main():
    p = argparse.ArgumentParser(description="Detect microBIs and macroBIs from an NDVI GeoTIFF.")
    p.add_argument("--ndvi", default="Bangalore_NDVI.tif", help="NDVI GeoTIFF (band 1 = NDVI)")
    p.add_argument("--boundary", default=None, help="optional boundary GeoJSON/shapefile to clip to")
    p.add_argument("--out", default=".", help="output folder")
    p.add_argument("--threshold", type=float, default=0.4, help="NDVI threshold for a green pixel")
    p.add_argument("--micro-min", type=float, default=0.5, help="smallest microBI (acres)")
    p.add_argument("--micro-max", type=float, default=4.0, help="largest microBI (acres); bigger = macroBI")
    p.add_argument("--no-bridge-fix", action="store_true", help="plain connectivity (no thin-bridge removal)")
    p.add_argument("--bridge-iterations", type=int, default=1)
    a = p.parse_args()
    run(a.ndvi, a.boundary, a.out, a.threshold, a.micro_min, a.micro_max,
        not a.no_bridge_fix, a.bridge_iterations)


if __name__ == "__main__":
    main()
