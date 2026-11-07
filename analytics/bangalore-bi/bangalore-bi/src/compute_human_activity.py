"""
Human-activity score for every microBI, from OpenStreetMap roads and buildings.

For each microBI and each buffer distance (default 50 m) it computes:
    road_count_<r>m        number of road features touching the buffer
    road_length_m_<r>m     metres of road inside the buffer      (alternative to count)
    building_count_<r>m    number of buildings touching the buffer
    building_area_m2_<r>m  building footprint area inside the buffer
    built_frac_<r>m        footprint area / buffer area
    score_<r>m             W_ROAD * road_count + W_BUILDING * building_count   (the deck's formula)
and, independent of the buffer:
    dist_nearest_road_m    distance from the microBI EDGE to the nearest road

What is calculated vs assumed:
  * calculated: the counts, lengths, areas and distances above (all in metres, UTM 43N)
  * assumed:    the 50 m distance, the 2:1 weights, and "more features = more human activity"
  * not checked: OSM completeness across Bangalore (needs validation, e.g. against satellite imagery)

Inputs: microBIs_full.geojson, plus the two caches written by overpass_resilient.py
Run:    python compute_human_activity.py
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely

MICROBI_FILE   = "microBIs_full.geojson"
ROADS_CACHE    = "osm_cache_roads"
BUILDINGS_CACHE = "osm_cache_buildings"
BOUNDARY_FILE  = "bbmp_boundary_FINAL.geojson"   # optional, only used for the map
BUFFERS_M      = [50]            # e.g. [50, 100, 200] to test sensitivity
BUFFER_FROM    = "edge"          # "edge": distance from the microBI boundary (recommended)
                                 # "centroid": distance from its centre point (what the first draft did)
W_ROAD, W_BUILDING = 2, 1
UTM_CRS        = "EPSG:32643"


def _pairs_measure(buffers, layer, measure):
    """For every buffer: how many layer features touch it, and total length/area inside it."""
    n = len(buffers)
    pairs = gpd.sjoin(buffers[["geometry"]], layer[["geometry"]], predicate="intersects", how="inner")
    if len(pairs) == 0:
        return pd.DataFrame({"count": np.zeros(n, int), "amount": np.zeros(n)})
    bi = pairs.index.to_numpy()
    li = pairs["index_right"].to_numpy()
    inter = shapely.intersection(np.asarray(layer.geometry.values)[li],
                                 np.asarray(buffers.geometry.values)[bi])
    val = shapely.length(inter) if measure == "length" else shapely.area(inter)
    out = (pd.DataFrame({"b": bi, "v": val}).groupby("b")
           .agg(count=("v", "size"), amount=("v", "sum")))
    return out.reindex(range(n), fill_value=0)


def compute_scores(micro, roads, buildings, buffers_m=None, buffer_from=None,
                   w_road=None, w_building=None):
    """All inputs must already be in a metric CRS (UTM). Returns a DataFrame aligned to `micro`.
    Settings left as None are read from the module-level constants at CALL time, so editing
    BUFFERS_M etc. in a notebook after importing still takes effect."""
    buffers_m = BUFFERS_M if buffers_m is None else buffers_m
    buffer_from = BUFFER_FROM if buffer_from is None else buffer_from
    w_road = W_ROAD if w_road is None else w_road
    w_building = W_BUILDING if w_building is None else w_building
    micro = micro.reset_index(drop=True)
    roads = roads.reset_index(drop=True)
    buildings = buildings.reset_index(drop=True)
    res = pd.DataFrame(index=micro.index)

    # Distance from each microBI edge to its nearest road
    near = gpd.sjoin_nearest(micro[["geometry"]], roads[["geometry"]], distance_col="d")
    res["dist_nearest_road_m"] = near.groupby(level=0)["d"].min().reindex(micro.index)

    base = micro.geometry if buffer_from == "edge" else micro.geometry.centroid
    for r in buffers_m:
        buf = gpd.GeoDataFrame(geometry=base.buffer(r), crs=micro.crs)
        rd = _pairs_measure(buf, roads, "length")
        bd = _pairs_measure(buf, buildings, "area")
        res[f"road_count_{r}m"] = rd["count"].astype(int).values
        res[f"road_length_m_{r}m"] = rd["amount"].round(1).values
        res[f"building_count_{r}m"] = bd["count"].astype(int).values
        res[f"building_area_m2_{r}m"] = bd["amount"].round(1).values
        res[f"built_frac_{r}m"] = (bd["amount"].values / buf.area.values).round(4)
        res[f"score_{r}m"] = (w_road * res[f"road_count_{r}m"] + w_building * res[f"building_count_{r}m"])
    return res


def add_relative_class(df, col):
    """Low / Medium / High by tercile of the score (a RELATIVE label, not an absolute threshold)."""
    ranks = df[col].rank(method="first")
    return pd.qcut(ranks, 3, labels=["Low", "Medium", "High"])


def main():
    from overpass_resilient import merge_cache
    micro_wgs = gpd.read_file(MICROBI_FILE)
    micro = micro_wgs.to_crs(UTM_CRS)
    roads = merge_cache(ROADS_CACHE).to_crs(UTM_CRS)
    roads = roads[roads.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    blds = merge_cache(BUILDINGS_CACHE).to_crs(UTM_CRS)
    blds = blds[blds.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    blds["geometry"] = blds.geometry.make_valid()
    print(f"microBIs: {len(micro)} | road features: {len(roads)} | building polygons: {len(blds)}")

    scores = compute_scores(micro, roads, blds)
    first = BUFFERS_M[0]
    out = micro_wgs.reset_index(drop=True)[["ID", "area_acres", "mean_ndvi", "lat", "lon"]].join(scores)
    out["activity_class"] = add_relative_class(out, f"score_{first}m")
    out.to_csv("microBI_human_activity.csv", index=False)
    micro_wgs.reset_index(drop=True).join(scores).to_file("microBIs_with_activity.geojson", driver="GeoJSON")
    print(out[[f"score_{first}m", "dist_nearest_road_m"]].describe().round(2))

    if len(BUFFERS_M) > 1:
        from scipy.stats import spearmanr
        for r in BUFFERS_M[1:]:
            rho = spearmanr(out[f"score_{first}m"], out[f"score_{r}m"]).correlation
            print(f"Spearman rank correlation, {first} m vs {r} m score: {rho:.3f}")

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(out[f"score_{first}m"], bins=40, color="#E8743B", edgecolor="black")
    ax.set_xlabel(f"Human-activity score ({first} m buffer)")
    ax.set_ylabel("Number of microBIs")
    ax.set_title(f"Human-activity score distribution (n={len(out)})")
    fig.tight_layout(); fig.savefig("hist_human_activity.png", dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 9))
    if os.path.exists(BOUNDARY_FILE):
        gpd.read_file(BOUNDARY_FILE).boundary.plot(ax=ax, color="black", linewidth=1)
    sc = ax.scatter(out["lon"], out["lat"], c=out[f"score_{first}m"], s=6, cmap="YlOrRd",
                    vmax=out[f"score_{first}m"].quantile(0.98))
    plt.colorbar(sc, ax=ax, fraction=0.04).set_label("Human-activity score (colour capped at 98th percentile)")
    ax.set_aspect("equal"); ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    ax.set_title("microBIs coloured by human-activity score")
    fig.tight_layout(); fig.savefig("map_human_activity.png", dpi=200); plt.close(fig)
    print("Saved: microBI_human_activity.csv, microBIs_with_activity.geojson, hist_human_activity.png, map_human_activity.png")


if __name__ == "__main__":
    main()
