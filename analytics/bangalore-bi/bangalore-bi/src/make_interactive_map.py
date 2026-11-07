"""
Interactive map of Bangalore's microBIs -- opens in any web browser, no software needed.

What the viewer can do:
  * Zoom/pan over SATELLITE imagery (default) or a street map, and compare each detected
    patch with what is really on the ground.
  * Click any microBI -> popup with ID, area, mean NDVI, pixel count, location
    (plus human-activity numbers if microBI_human_activity.csv is present).
  * Search by ID (box at top-left) -> the map flies to that microBI, outlines it in red and opens its popup.
  * Measure distances with the ruler (top-left), e.g. to check a 50 m buffer by eye.
  * Switch colouring between NDVI and human-activity score (layer control, top-right).

Run:
    python make_interactive_map.py            -> bangalore_microBIs_interactive.html
    python make_interactive_map.py 1234       -> microBI_1234.html, already zoomed on microBI 1234

Needs internet when VIEWING the map (map tiles and Leaflet are loaded from the web).
"""
import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
import folium
import branca.colormap as cm
from folium.plugins import Search, Fullscreen, MeasureControl

MICROBI_FILE  = "microBIs_full.geojson"
ACTIVITY_CSV  = "microBI_human_activity.csv"      # optional (from compute_human_activity.py)
BOUNDARY_FILE = "bbmp_boundary_FINAL.geojson"     # optional
OUT_HTML      = "bangalore_microBIs_interactive.html"

ESRI_SAT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Imagery &copy; Esri, Maxar, Earthstar Geographics"


def load_data():
    gdf = gpd.read_file(MICROBI_FILE).to_crs("EPSG:4326")
    gdf = gdf[~gdf.geometry.is_empty].copy()
    gdf["geometry"] = [shapely.set_precision(g, 1e-6) for g in gdf.geometry]   # ~0.1 m: smaller file
    gdf = gdf[~gdf.geometry.is_empty].copy()

    extra = []
    if os.path.exists(ACTIVITY_CSV):
        act = pd.read_csv(ACTIVITY_CSV)
        score_cols = [c for c in act.columns if c.startswith("score_")]
        if score_cols:
            suffix = score_cols[0][len("score_"):]
            extra = [c for c in [f"score_{suffix}", f"road_count_{suffix}", f"building_count_{suffix}",
                                 "dist_nearest_road_m", "activity_class"] if c in act.columns]
            gdf = gdf.merge(act[["ID"] + extra], on="ID", how="left")
    for c, nd in [("area_acres", 3), ("mean_ndvi", 3), ("dist_nearest_road_m", 1)]:
        if c in gdf.columns:
            gdf[c] = gdf[c].round(nd)
    # lat/lon as TEXT with 5 decimals (~1 m): popups round plain numbers to 3 decimals (~100 m)
    gdf["lat"] = gdf["lat"].map(lambda v: f"{v:.5f}")
    gdf["lon"] = gdf["lon"].map(lambda v: f"{v:.5f}")
    gdf["search_id"] = gdf["ID"].astype(str)
    return gdf, extra


def build_map(focus_id=None, out_html=OUT_HTML):
    gdf, extra = load_data()
    minx, miny, maxx, maxy = gdf.total_bounds

    m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=11,
                   tiles=None, prefer_canvas=True, control_scale=True)
    folium.TileLayer(tiles=ESRI_SAT, attr=ESRI_ATTR, name="Satellite imagery", max_zoom=20,
                     max_native_zoom=19).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Street map", max_zoom=20, max_native_zoom=19, show=False).add_to(m)

    if os.path.exists(BOUNDARY_FILE):
        folium.GeoJson(gpd.read_file(BOUNDARY_FILE).to_crs("EPSG:4326").boundary.to_json(),
                       name="City boundary (BBMP)",
                       style_function=lambda f: {"color": "#ffffff", "weight": 2.5, "fillOpacity": 0}).add_to(m)

    fields = ["ID", "area_acres", "mean_ndvi", "pixel_count", "lat", "lon"]
    aliases = ["microBI ID", "Area (acres)", "Mean NDVI", "Pixels", "Latitude", "Longitude"]
    pretty = {"dist_nearest_road_m": "Distance to nearest road (m)", "activity_class": "Activity class (relative)"}
    for c in extra:
        fields.append(c)
        if c.startswith("score_"):
            aliases.append("Human-activity score (" + c[6:] + " buffer)")
        elif c.startswith("road_count_"):
            aliases.append("Road features in buffer")
        elif c.startswith("building_count_"):
            aliases.append("Buildings in buffer")
        else:
            aliases.append(pretty.get(c, c))
    data = gdf[fields + ["search_id", "geometry"]]

    vmax = float(np.nanquantile(gdf["mean_ndvi"], 0.99))
    ndvi_cmap = cm.LinearColormap(["#fee08b", "#66bd63", "#1a9850", "#00441b"], vmin=0.4, vmax=max(vmax, 0.5),
                                  caption="Mean NDVI of microBI")
    hl = {"weight": 3, "color": "#ffff00", "fillOpacity": 0.9}
    ndvi_layer = folium.GeoJson(
        data, name="microBIs coloured by NDVI",
        style_function=lambda f: {"fillColor": ndvi_cmap(f["properties"]["mean_ndvi"]), "color": "#111111",
                                  "weight": 1, "fillOpacity": 0.75},
        highlight_function=lambda f: hl,
        tooltip=folium.GeoJsonTooltip(fields=["ID", "area_acres"], aliases=["microBI", "acres"], sticky=False),
        popup=folium.GeoJsonPopup(fields=fields, aliases=aliases, max_width=320),
        zoom_on_click=False,
    ).add_to(m)
    ndvi_cmap.add_to(m)

    score_col = next((c for c in extra if c.startswith("score_")), None)
    if score_col:
        smax = float(np.nanquantile(gdf[score_col], 0.98))
        act_cmap = cm.LinearColormap(["#ffffb2", "#fd8d3c", "#e31a1c", "#800026"], vmin=0, vmax=max(smax, 1),
                                     caption="Human-activity score (capped at 98th percentile)")
        folium.GeoJson(
            data, name="microBIs coloured by human-activity score", show=False,
            style_function=lambda f: {"fillColor": act_cmap(min(f["properties"][score_col] or 0, smax)),
                                      "color": "#111111", "weight": 1, "fillOpacity": 0.75},
            highlight_function=lambda f: hl,
            tooltip=folium.GeoJsonTooltip(fields=["ID", score_col], aliases=["microBI", "score"], sticky=False),
            popup=folium.GeoJsonPopup(fields=fields, aliases=aliases, max_width=320),
        ).add_to(m)

    Search(layer=ndvi_layer, geom_type="Polygon", search_label="search_id", search_zoom=19,
           placeholder="Search microBI ID (e.g. 123)", collapsed=False, position="topleft").add_to(m)
    # After a search: outline the patch in red and open its popup once the map has flown there.
    # (Popups are attached to the whole layer, so we "click" the patch instead of calling openPopup on it.)
    js = f"""
    window.addEventListener('load', function() {{
        var ctl = {ndvi_layer.get_name()}searchControl;
        ctl.on('search:locationfound', function(e) {{
            {ndvi_layer.get_name()}.resetStyle();
            var l = e.layer;
            l.setStyle({{color: '#ff0000', weight: 4}});
            {m.get_name()}.once('moveend', function() {{ l.fire('click', {{latlng: l.getBounds().getCenter()}}, true); }});
        }});
    }});
    """
    m.get_root().script.add_child(folium.Element(js))
    Fullscreen(position="topleft").add_to(m)
    MeasureControl(position="topleft", primary_length_unit="meters").add_to(m)

    if focus_id is not None:
        row = gdf[gdf["ID"] == focus_id]
        if row.empty:
            raise SystemExit(f"microBI {focus_id} not found")
        b = row.total_bounds
        folium.GeoJson(row[["geometry"]], name=f"Selected: microBI {focus_id}",
                       style_function=lambda f: {"color": "#ff0000", "weight": 4, "fillOpacity": 0}).add_to(m)
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]], padding=(60, 60), max_zoom=19)
    else:
        m.fit_bounds([[miny, minx], [maxy, maxx]])

    title = ("<div style='position:fixed;bottom:22px;left:10px;z-index:9999;background:rgba(255,255,255,.92);"
             "padding:8px 12px;border-radius:6px;font:13px/1.35 Arial;max-width:330px;box-shadow:0 1px 4px #0006'>"
             f"<b>Bangalore microBIs</b> (n = {len(gdf)})<br>Connected green patches, NDVI &ge; 0.4, 0.5&ndash;4 acres."
             "<br>Zoom in, click a patch for details, or search by ID (top-left).</div>")
    m.get_root().html.add_child(folium.Element(title))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(out_html)
    print(f"Saved {out_html}  ({os.path.getsize(out_html)/1e6:.1f} MB, {len(gdf)} microBIs)")
    return out_html


if __name__ == "__main__":
    if len(sys.argv) > 1:
        fid = int(sys.argv[1])
        build_map(focus_id=fid, out_html=f"microBI_{fid}.html")
    else:
        build_map()
