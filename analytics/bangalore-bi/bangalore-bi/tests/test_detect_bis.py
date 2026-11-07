"""Tests for the BI engine on small synthetic data where the right answer is known."""
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy import ndimage
from shapely.geometry import box

import detect_bis as d

T = from_origin(0, 1000, 10, 10)      # 10 m pixels -> 100 sq m each
PIX = 100.0


def patches(mask, min_acres=0.0, max_acres=None):
    return d.detect_patches(mask, mask.astype(float) * 0.6, min_acres, max_acres, T, PIX)


def test_diagonal_pixels_are_one_bi_with_8_connectivity():
    m = np.array([[1, 0], [0, 1]], dtype=bool)
    assert len(patches(m)) == 1
    assert ndimage.label(m, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])[1] == 2   # 4-connectivity would give 2


def test_area_filter_pixel_count_and_mean():
    m = np.zeros((30, 30), dtype=bool)
    m[2:10, 2:10] = True            # 8x8 = 64 px = 6400 sq m = 1.58 acres
    m[20:22, 20:22] = True          # 4 px = 0.1 acre
    found = patches(m, min_acres=1.0)
    assert len(found) == 1
    assert found[0]["pixel_count"] == 64
    assert abs(found[0]["area_acres"] - 6400 / d.SQM_PER_ACRE) < 1e-9
    assert abs(found[0]["mean_value"] - 0.6) < 1e-6


def test_bridge_fix_separates_two_blocks_joined_by_a_thin_strip():
    m = np.zeros((20, 40), dtype=bool)
    m[4:16, 2:14] = True
    m[4:16, 26:38] = True
    m[9, 14:26] = True              # 1-pixel-wide strip joining them
    assert ndimage.label(m, structure=d.STRUCT8)[1] == 1
    assert ndimage.label(d.break_thin_bridges(m, 1), structure=d.STRUCT8)[1] == 2


def _write_tif(path, bands, res=0.0001, west=77.50, north=13.05):
    with rasterio.open(path, "w", driver="GTiff", height=bands[0].shape[0], width=bands[0].shape[1],
                       count=len(bands), dtype="float32", crs="EPSG:4326",
                       transform=from_origin(west, north, res, res)) as dst:
        for i, b in enumerate(bands, 1):
            dst.write(b.astype("float32"), i)


def test_end_to_end_micro_macro_and_boundary_clip(tmp_path):
    ndvi = np.full((400, 400), 0.1, dtype="float32")
    ndvi[50:58, 50:56] = 0.6        # about 1.2 acres  -> microBI
    ndvi[150:165, 150:165] = 0.6    # about 6 acres    -> macroBI
    ndvi[50:58, 300:306] = 0.6      # microBI-sized, but OUTSIDE the boundary
    _write_tif(tmp_path / "ndvi.tif", [ndvi])
    # boundary covers lon 77.500-77.522 only (columns 0-220)
    gpd.GeoDataFrame(geometry=[box(77.500, 13.0, 77.522, 13.06)], crs="EPSG:4326").to_file(tmp_path / "b.geojson", driver="GeoJSON")
    r = d.run(str(tmp_path / "ndvi.tif"), str(tmp_path / "b.geojson"), bridge_fix=False, write=False)
    assert len(r["micro"]) == 1 and len(r["macro"]) == 1
    assert 0.5 <= r["micro"]["area_acres"].iloc[0] <= 4.0
    assert r["macro"]["area_acres"].iloc[0] > 4.0
    assert r["microBIs_outside"] == 0 and r["macroBIs_outside"] == 0
