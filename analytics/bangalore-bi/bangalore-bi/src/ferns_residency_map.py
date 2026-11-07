"""
Biodiversity islands (BIs) around Ferns Residency, drawn on top of satellite imagery.

Produces
  ferns_residency_map.html   interactive: zoom/pan, area label on every BI, click for details,
                             toggle between the two BI versions (top-right)
  ferns_residency_map.png    static picture for slides (satellite background needs internet)
  ferns_residency_BIs.csv    one row per BI in the box: area, class, pixels, mean NDVI, location

Box: BOX_W_M x BOX_H_M metres centred on the given lat/long (400 x 520 m, as in the professor's diagram).

A BI = connected green pixels (NDVI >= 0.4, 8-connectivity). Two versions are drawn because plain
connectivity merges patches that are joined only by a thin strip:
  plain          the definition as stated
  thin bridges   1-pixel-wide bridges removed first (this is how our microBI list was built)
Areas are always the area of the WHOLE BI, even when the drawn shape is clipped to the map window.

Run:  python ferns_residency_map.py
"""
import os
from math import cos, radians
import numpy as np
import pandas as pd
import rasterio
import folium
from affine import Affine
from folium.plugins import Fullscreen, MeasureControl
from pyproj import Transformer
from rasterio.features import shapes
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy import ndimage
from shapely.geometry import Point as shapely_point, Polygon, shape
from shapely.ops import unary_union, transform as shp_transform
import geopandas as gpd

NDVI_TIF       = "Bangalore_NDVI.tif"
CENTER_LAT, CENTER_LON = 13.057712, 77.640010          # Ferns Residency (given by the professor)
HOTSPOT_XLSX   = "Bengaluru_Hotspot_Annual_Summary_2026.xlsx"   # optional: also marks the eBird hotspot pin
HOTSPOT_NAME   = "Ferns Residency"
BOX_W_M, BOX_H_M = 400, 520
MARGIN_M       = 100             # drawn area extends this far beyond the box
NDVI_THRESHOLD = 0.4
UTM_CRS        = "EPSG:32643"
SQM_PER_ACRE   = 4046.8564224
STRUCT8        = np.ones((3, 3))
ESRI_SAT  = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Imagery &copy; Esri, Maxar, Earthstar Geographics"
CLASS_COLOR = {"microBI (0.5-4 acres)": "#ffeb3b", "macroBI (>4 acres)": "#ff9800", "small patch (<0.5 acre)": "#cfd8dc"}


def bi_class(a):
    if a < 0.5:
        return "small patch (<0.5 acre)"
    return "microBI (0.5-4 acres)" if a <= 4 else "macroBI (>4 acres)"


def load_utm(path):
    with rasterio.open(path) as src:
        ndvi = src.read(1).astype("float32")
        t, w, h = calculate_default_transform(src.crs, UTM_CRS, src.width, src.height, *src.bounds)
        out = np.full((h, w), np.nan, dtype="float32")
        reproject(ndvi, out, src_transform=src.transform, src_crs=src.crs, dst_transform=t,
                  dst_crs=UTM_CRS, resampling=Resampling.bilinear)
    return out, t


def bis_in_view(ndvi, t, mask, box_m, window_m):
    """BIs touching the box. Returns a GeoDataFrame (UTM) with the whole-BI area and the drawn shape."""
    lab, n = ndimage.label(mask, structure=STRUCT8)
    counts = np.bincount(lab.ravel(), minlength=n + 1)

    def rc(b):   # (minx, miny, maxx, maxy) -> row/col slices
        c0 = int(np.floor((b[0] - t.c) / t.a)); c1 = int(np.ceil((b[2] - t.c) / t.a))
        r0 = int(np.floor((b[3] - t.f) / t.e)); r1 = int(np.ceil((b[1] - t.f) / t.e))
        return max(r0, 0), min(r1, lab.shape[0]), max(c0, 0), min(c1, lab.shape[1])

    R0, R1, C0, C1 = rc(window_m.bounds)
    win = lab[R0:R1, C0:C1].astype("int32")
    wt = t * Affine.translation(C0, R0)
    parts = {}
    for geom, v in shapes(win, mask=win > 0, transform=wt, connectivity=8):
        parts.setdefault(int(v), []).append(shape(geom))
    geoms = {l: unary_union(g) for l, g in parts.items()}
    keep = [l for l, g in geoms.items() if g.intersects(box_m)]          # BIs touching the box
    mean_ndvi = dict(zip(keep, ndimage.mean(ndvi, lab, index=keep))) if keep else {}
    pix_area = abs(t.a * t.e)
    rows = []
    for l in keep:
        area = counts[l] * pix_area / SQM_PER_ACRE
        rows.append({"BI label": l, "area_acres": round(area, 3), "pixels": int(counts[l]),
                     "mean_ndvi": round(float(mean_ndvi[l]), 3), "class": bi_class(area),
                     "shape_clipped_to_view": bool((win == l).sum() < counts[l]), "geometry": geoms[l]})
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=UTM_CRS)


def label_div(text, size=12, color="#fff"):
    return folium.DivIcon(html=(f"<div style='font:bold {size}px Arial;color:{color};white-space:nowrap;"
                                "transform:translate(-50%,-50%);text-shadow:-1px -1px 2px #000,1px -1px 2px #000,"
                                f"-1px 1px 2px #000,1px 1px 2px #000'>{text}</div>"))


def main():
    print("Loading and reprojecting NDVI raster ...")
    ndvi, t = load_utm(NDVI_TIF)
    to_utm = Transformer.from_crs("EPSG:4326", UTM_CRS, always_xy=True)
    to_wgs = Transformer.from_crs(UTM_CRS, "EPSG:4326", always_xy=True)
    cx, cy = to_utm.transform(CENTER_LON, CENTER_LAT)
    # rectangle aligned to true north-south / east-west (like the professor's diagram), sides in metres on the ground
    ph = radians(CENTER_LAT)
    m_lat = 111132.95 - 559.82 * cos(2 * ph) + 1.175 * cos(4 * ph)             # metres per degree latitude
    m_lon = 111412.84 * cos(ph) - 93.5 * cos(3 * ph) + 0.118 * cos(5 * ph)     # metres per degree longitude
    dlat, dlon = BOX_H_M / 2 / m_lat, BOX_W_M / 2 / m_lon
    box_ll = [(CENTER_LON - dlon, CENTER_LAT - dlat), (CENTER_LON + dlon, CENTER_LAT - dlat),
              (CENTER_LON + dlon, CENTER_LAT + dlat), (CENTER_LON - dlon, CENTER_LAT + dlat)]
    box_m = Polygon([to_utm.transform(lo, la) for lo, la in box_ll])
    window_m = box_m.envelope.buffer(MARGIN_M, join_style=2)

    green = np.isfinite(ndvi) & (ndvi >= NDVI_THRESHOLD)
    masks = {"thin bridges removed (as in our microBI list)": ndimage.binary_dilation(ndimage.binary_erosion(green, STRUCT8), STRUCT8),
             "plain connectivity (as defined)": green}
    results = {}
    for name, mk in masks.items():
        print("Labelling:", name)
        results[name] = bis_in_view(ndvi, t, mk, box_m, window_m)

    # ---- table ----
    tab = []
    for name, g in results.items():
        w = g.to_crs("EPSG:4326")
        c = g.geometry.representative_point()
        cw = gpd.GeoSeries(c, crs=UTM_CRS).to_crs("EPSG:4326")
        for (i, r), lat, lon in zip(w.iterrows(), cw.y, cw.x):
            tab.append({"version": name, "BI label": r["BI label"], "area_acres": r["area_acres"], "class": r["class"],
                        "pixels": r["pixels"], "mean_ndvi": r["mean_ndvi"], "lat": round(lat, 6), "lon": round(lon, 6),
                        "shape_clipped_to_view": r["shape_clipped_to_view"]})
    pd.DataFrame(tab).sort_values(["version", "area_acres"], ascending=[True, False]).to_csv("ferns_residency_BIs.csv", index=False)

    # ---- interactive map ----
    m = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=17, tiles=None, control_scale=True)
    folium.TileLayer(tiles=ESRI_SAT, attr=ESRI_ATTR, name="Satellite imagery", max_zoom=21, max_native_zoom=19).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Street map", max_zoom=21, max_native_zoom=19, show=False).add_to(m)

    for k, (name, g) in enumerate(results.items()):
        fg = folium.FeatureGroup(name="BIs: " + name, show=(k == 0))
        w = g.to_crs("EPSG:4326")
        for (i, r), pt in zip(w.iterrows(), g.geometry.representative_point()):
            col = CLASS_COLOR[r["class"]]
            note = "<br><i>Shape clipped to the map window; area is of the whole BI.</i>" if r["shape_clipped_to_view"] else ""
            pop = (f"<b>{r['class']}</b><br>Area: <b>{r['area_acres']:.3f} acres</b><br>Pixels: {r['pixels']}"
                   f"<br>Mean NDVI: {r['mean_ndvi']:.3f}<br>Version: {name}{note}")
            folium.GeoJson(r["geometry"].__geo_interface__, style_function=lambda f, c=col: {
                "color": c, "weight": 3, "fillColor": c, "fillOpacity": 0.22},
                popup=folium.Popup(pop, max_width=300)).add_to(fg)
            lon, lat = to_wgs.transform(pt.x, pt.y)
            folium.Marker([lat, lon], icon=label_div(f"{r['area_acres']:.2f} ac"), interactive=False).add_to(fg)
        fg.add_to(m)

    # red box with dimension labels (like the professor's diagram)
    folium.PolyLine([(la, lo) for lo, la in box_ll + [box_ll[0]]], color="#ff1744", weight=3,
                    tooltip=f"{BOX_W_M} m x {BOX_H_M} m").add_to(m)
    folium.Marker([CENTER_LAT + dlat, CENTER_LON], icon=label_div(f"{BOX_W_M} m", 13, "#ffd54f"), interactive=False).add_to(m)
    folium.Marker([CENTER_LAT, CENTER_LON - dlon], icon=label_div(f"{BOX_H_M} m", 13, "#ffd54f"), interactive=False).add_to(m)

    folium.CircleMarker([CENTER_LAT, CENTER_LON], radius=8, color="#ffffff", weight=2, fill=True, fill_color="#ff1744",
                        fill_opacity=1, tooltip=f"Ferns Residency, given lat/long ({CENTER_LAT}, {CENTER_LON})").add_to(m)
    if os.path.exists(HOTSPOT_XLSX):
        hs = pd.read_excel(HOTSPOT_XLSX, sheet_name="Annual Summary")
        hs = hs[hs["Hotspot Name"].str.contains(HOTSPOT_NAME, case=False, na=False)]
        for _, h in hs.iterrows():
            if abs(h["Latitude"] - CENTER_LAT) < 0.01 and abs(h["Longitude"] - CENTER_LON) < 0.01:
                folium.CircleMarker([h["Latitude"], h["Longitude"]], radius=8, color="#ffffff", weight=2, fill=True, fill_color="#2962ff",
                                    fill_opacity=1, tooltip=f"eBird hotspot: {h['Hotspot Name']} ({h['Latitude']:.6f}, {h['Longitude']:.6f})").add_to(m)

    Fullscreen(position="topleft").add_to(m)
    MeasureControl(position="topleft", primary_length_unit="meters").add_to(m)
    legend = ("<div style='position:fixed;bottom:22px;left:10px;z-index:9999;background:rgba(255,255,255,.93);padding:8px 12px;"
              "border-radius:6px;font:13px/1.4 Arial;max-width:300px;box-shadow:0 1px 4px #0006'><b>BIs around Ferns Residency</b><br>"
              + "".join(f"<span style='background:{c};padding:0 9px;border:1px solid #555'></span> {n}<br>" for n, c in CLASS_COLOR.items())
              + "<span style='border:2px solid #ff1744;padding:0 8px'></span> box "
              f"{BOX_W_M} x {BOX_H_M} m<br><span style='color:#ff1744'>&#9679;</span> given lat/long &nbsp;<span style='color:#2962ff'>&#9679;</span> eBird hotspot pin"
              "<br><small>Areas in acres. Switch BI version at top-right.</small></div>")
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds([[CENTER_LAT - dlat, CENTER_LON - dlon], [CENTER_LAT + dlat, CENTER_LON + dlon]], padding=(30, 30))
    m.save("ferns_residency_map.html")
    print("Saved ferns_residency_map.html, ferns_residency_BIs.csv")
    save_png(results, box_m, window_m, cx, cy)
    for name, g in results.items():
        print(f"\n{name}:")
        print(g[["BI label", "area_acres", "class", "pixels", "mean_ndvi"]].sort_values("area_acres", ascending=False).to_string(index=False))


def save_png(results, box_m, window_m, cx, cy):
    """Static picture for slides (north-up). Uses the first (default) version. Satellite background needs internet."""
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    W = "EPSG:3857"
    name, g = next(iter(results.items()))
    g = g.to_crs(W)
    box_w = gpd.GeoSeries([box_m], crs=UTM_CRS).to_crs(W).iloc[0]
    win_w = gpd.GeoSeries([window_m], crs=UTM_CRS).to_crs(W).iloc[0]
    ctr = gpd.GeoSeries([shapely_point(CENTER_LON, CENTER_LAT)], crs="EPSG:4326").to_crs(W).iloc[0]
    minx, miny, maxx, maxy = win_w.bounds
    fig, ax = plt.subplots(figsize=(8, 8 * (maxy - miny) / (maxx - minx)))
    ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy); ax.set_aspect("equal"); ax.axis("off")
    try:
        import contextily as ctx
        ctx.add_basemap(ax, crs=W, source=ctx.providers.Esri.WorldImagery, attribution_size=7)
    except Exception as e:
        ax.set_facecolor("#37474f"); fig.patch.set_facecolor("#37474f")
        print("  (no satellite background in this PNG: could not download tiles ->", type(e).__name__, ")")
    halo = [pe.withStroke(linewidth=2.5, foreground="black")]
    for _, r in g.iterrows():
        col = CLASS_COLOR[r["class"]]
        gg = gpd.GeoSeries([r["geometry"]], crs=W)
        gg.plot(ax=ax, facecolor=col, alpha=0.25, edgecolor="none")
        gg.boundary.plot(ax=ax, color=col, linewidth=2)
        p = r["geometry"].representative_point()
        ax.text(p.x, p.y, f"{r['area_acres']:.2f} ac", color="white", ha="center", va="center", fontsize=9, weight="bold", path_effects=halo)
    bx, by = box_w.exterior.xy
    ax.plot(bx, by, color="#ff1744", linewidth=2.5)
    ax.plot(ctr.x, ctr.y, marker="o", color="#ff1744", markeredgecolor="white", markersize=9)
    ax.text(ctr.x, ctr.y - 18, "Ferns Residency", color="white", ha="center", va="top", fontsize=10, weight="bold", path_effects=halo)
    bminx, bminy, bmaxx, bmaxy = box_w.bounds
    ax.text(ctr.x, bmaxy + 12, f"{BOX_W_M} m", color="#ffd54f", ha="center", va="bottom", fontsize=10, weight="bold", path_effects=halo)
    ax.text(bminx - 12, ctr.y, f"{BOX_H_M} m", color="#ffd54f", ha="right", va="center", fontsize=10, weight="bold", rotation=90, path_effects=halo)
    dark = ax.get_facecolor()[0] < .5
    ax.set_title(f"BIs around Ferns Residency | {name}", fontsize=10, color="white" if dark else "black")
    fig.tight_layout(); fig.savefig("ferns_residency_map.png", dpi=200, facecolor=fig.get_facecolor()); plt.close(fig)
    print("Saved ferns_residency_map.png")


if __name__ == "__main__":
    main()
