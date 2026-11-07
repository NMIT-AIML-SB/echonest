"""
BI area at every eBird hotspot.

Definition used (professor's): a BI is a connected group of green pixels (NDVI >= 0.4, 8-connectivity).
A BI can be ANY size here -- no 0.5-acre / 4-acre limits.

For every hotspot lat/long this script reports:
  Inside BI           the hotspot point lies on a green pixel -> area of THAT BI
  Nearest BI          the point is not green (e.g. on water, a road or a building); the nearest BI
                      within SEARCH_RADIUS_M is reported together with the distance to it
  No BI nearby        no green pixel within SEARCH_RADIUS_M
  Outside raster      the hotspot is outside the NDVI raster, so nothing can be said

Two versions of the BI are computed, because plain connectivity merges green patches that are only
joined by a thin strip (the known limitation):
  plain        exactly the professor's definition
  bridge-fix   thin 1-pixel bridges removed first (erosion + dilation, 1 iteration)

Run:  python hotspot_bi_area.py
"""
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy import ndimage
from pyproj import Transformer

NDVI_TIF      = "Bangalore_NDVI.tif"
HOTSPOT_XLSX  = "Bengaluru_Hotspot_Annual_Summary_2026.xlsx"
HOTSPOT_SHEET = "Annual Summary"
OUT_XLSX      = "Bengaluru_Hotspot_BI_Area_2026.xlsx"
OUT_CSV       = "Bengaluru_Hotspot_BI_Area_2026.csv"
NDVI_THRESHOLD = 0.4
SEARCH_RADIUS_M = 500          # how far to look for the nearest BI when the point is not green
UTM_CRS = "EPSG:32643"
SQM_PER_ACRE = 4046.8564224
STRUCT8 = np.ones((3, 3))


def load_utm(path):
    with rasterio.open(path) as src:
        ndvi = src.read(1).astype("float32")
        t, w, h = calculate_default_transform(src.crs, UTM_CRS, src.width, src.height, *src.bounds)
        out = np.full((h, w), np.nan, dtype="float32")
        reproject(ndvi, out, src_transform=src.transform, src_crs=src.crs, dst_transform=t,
                  dst_crs=UTM_CRS, resampling=Resampling.bilinear)
        bounds = src.bounds
    return out, t, bounds


def label_components(mask):
    lab, n = ndimage.label(mask, structure=STRUCT8)
    counts = np.bincount(lab.ravel(), minlength=n + 1)
    return lab, counts


def bi_class(area_acres):
    if area_acres < 0.5:
        return "small patch (<0.5 acre)"
    return "microBI (0.5-4 acres)" if area_acres <= 4 else "macroBI (>4 acres)"


def locate(lab, counts, ndvi, rows, cols, px_m, pix_area):
    """For each point (row, col) find the BI it is in, else the nearest BI within the search radius."""
    R = int(np.ceil(SEARCH_RADIUS_M / px_m))
    res = []
    H, W = lab.shape
    for r, c in zip(rows, cols):
        if not (0 <= r < H and 0 <= c < W):
            res.append(("Outside raster", np.nan, 0)); continue
        if lab[r, c] > 0:
            res.append(("Inside BI", 0.0, int(lab[r, c]))); continue
        r0, r1, c0, c1 = max(r - R, 0), min(r + R + 1, H), max(c - R, 0), min(c + R + 1, W)
        win = lab[r0:r1, c0:c1]
        if not win.any():
            res.append(("No BI nearby", np.nan, 0)); continue
        dist, (ir, ic) = ndimage.distance_transform_edt(win == 0, return_indices=True)
        d = dist[r - r0, c - c0] * px_m
        if d > SEARCH_RADIUS_M:
            res.append(("No BI nearby", np.nan, 0)); continue
        res.append(("Nearest BI", round(float(d), 1), int(win[ir[r - r0, c - c0], ic[r - r0, c - c0]])))
    return res


def main():
    print("Loading and reprojecting NDVI raster ...")
    ndvi, t, bounds = load_utm(NDVI_TIF)
    px_m = abs(t.a)
    pix_area = abs(t.a) * abs(t.e)
    print(f"  grid {ndvi.shape}, pixel {px_m:.2f} m, pixel area {pix_area:.2f} sq m")

    hs = pd.read_excel(HOTSPOT_XLSX, sheet_name=HOTSPOT_SHEET)
    x, y = Transformer.from_crs("EPSG:4326", UTM_CRS, always_xy=True).transform(hs["Longitude"].values, hs["Latitude"].values)
    cols, rows = np.floor(~t * (np.asarray(x), np.asarray(y))).astype(int)
    # inside the ORIGINAL raster rectangle? (the reprojected grid has empty corners)
    inside_extent = ((hs["Longitude"] >= bounds.left) & (hs["Longitude"] <= bounds.right) &
                     (hs["Latitude"] >= bounds.bottom) & (hs["Latitude"] <= bounds.top)).values

    valid = np.isfinite(ndvi)
    green = valid & (ndvi >= NDVI_THRESHOLD)
    variants = {
        "plain": green,
        "bridgefix": ndimage.binary_dilation(ndimage.binary_erosion(green, STRUCT8), STRUCT8),
    }
    out = hs[["District", "Hotspot ID", "Hotspot Name", "Latitude", "Longitude"]].copy()
    for name, mask in variants.items():
        print(f"Labelling BIs ({name}) ...")
        lab, counts = label_components(mask)
        loc = locate(lab, counts, ndvi, rows, cols, px_m, pix_area)
        match = [m for m, _, _ in loc]
        dist = [d for _, d, _ in loc]
        labels = np.array([l for _, _, l in loc])
        match = [("Outside raster" if not ie else m) for m, ie in zip(match, inside_extent)]
        area = np.where(labels > 0, counts[labels] * pix_area / SQM_PER_ACRE, np.nan)
        need = np.unique(labels[labels > 0])
        mean_ndvi = dict(zip(need, ndimage.mean(ndvi, lab, index=need)))
        sfx = "" if name == "plain" else " (bridge-fix)"
        out[f"BI match{sfx}"] = match
        out[f"Distance to BI (m){sfx}"] = dist
        out[f"BI area (acres){sfx}"] = np.round(area, 3)
        out[f"BI pixels{sfx}"] = np.where(labels > 0, counts[labels], np.nan)
        out[f"BI mean NDVI{sfx}"] = [round(float(mean_ndvi[l]), 3) if l > 0 else np.nan for l in labels]
        out[f"BI class{sfx}"] = [bi_class(a) if a == a else "" for a in area]
        out[f"BI label{sfx}"] = np.where(labels > 0, labels, np.nan)
    return out


NOTES = [
    ("What this table is", "For every eBird hotspot: the area of the biodiversity island (BI) at its lat/long, plus Uma's species and bird counts (Oct 2025 - Sep 2026)."),
    ("BI definition", "Connected green pixels, NDVI >= 0.4, 8-connectivity. Any size (no 0.5 / 4 acre limits). Areas in acres, measured in UTM zone 43N (about 96.6 sq m per pixel)."),
    ("BI match", "Inside BI = the hotspot point is on a green pixel (strongest result). Nearest BI = the point is not green (water, road, building); the nearest BI within 500 m is reported and 'Distance to BI (m)' says how far. Outside raster = the hotspot is outside the NDVI raster, so no BI information (blank)."),
    ("Two versions", "Plain = the definition as stated. (bridge-fix) = 1-pixel-wide bridges between green patches removed first, so two patches joined only by a thin strip are not merged. Plain areas can be far larger because of such merging. Both are given so the effect is visible."),
    ("BI class", "small patch (<0.5 acre), microBI (0.5-4 acres), macroBI (>4 acres), from the BI area."),
    ("BI label", "Arbitrary number identifying the BI inside one version. Hotspots with the same BI label are in the same BI."),
    ("Coverage", "The NDVI raster covers lat 12.75-13.15, lon 77.35-77.85. Hotspots outside it cannot be assessed; a larger NDVI export is needed for them."),
    ("Check before relying on it", "(1) The NDVI raster's date is not stored in the file; if it is the 2024 composite it predates the bird period. (2) 'Nearest BI' rows are an approximation, so look at the distance. (3) Hotspot pins are often on a road or a lake edge, not on the vegetation."),
    ("Total Known Bird Count", "Sum of reported counts over observation records; not unique individual birds."),
]


def write_workbook(df, path):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Hotspot BI areas", index=False)
        pd.DataFrame(NOTES, columns=["Topic", "Notes"]).to_excel(xw, sheet_name="Notes", index=False)
        for ws in xw.book.worksheets:
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F3D2B")
                c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.freeze_panes = "A2"
        ws = xw.book["Hotspot BI areas"]
        for i, col in enumerate(df.columns, 1):
            width = min(max(len(str(col)), df[col].astype(str).str.len().quantile(0.9)) + 2, 42)
            ws.column_dimensions[get_column_letter(i)].width = max(width, 10)
        ws.auto_filter.ref = ws.dimensions
        wn = xw.book["Notes"]
        wn.column_dimensions["A"].width = 26; wn.column_dimensions["B"].width = 120
        for row in wn.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")


if __name__ == "__main__":
    res = main()
    summ = pd.read_excel(HOTSPOT_XLSX, sheet_name=HOTSPOT_SHEET)[
        ["Hotspot ID", "Distinct Species", "Total Known Bird Count", "Unique Checklists"]]
    res = res.merge(summ, on="Hotspot ID", how="left")
    first = ["District", "Hotspot ID", "Hotspot Name", "Latitude", "Longitude",
             "Distinct Species", "Total Known Bird Count", "Unique Checklists"]
    res = res[first + [c for c in res.columns if c not in first]]
    res.to_csv(OUT_CSV, index=False)
    write_workbook(res, OUT_XLSX)
    print(res["BI match"].value_counts().to_string())
    print("saved", OUT_XLSX, OUT_CSV)
