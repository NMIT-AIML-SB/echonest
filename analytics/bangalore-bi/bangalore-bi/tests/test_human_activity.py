"""Hand-checkable case: one 40 x 40 m microBI, roads and buildings at known distances."""
import geopandas as gpd
from shapely.geometry import LineString, box

import compute_human_activity as c

CRS = "EPSG:32643"


def layers():
    micro = gpd.GeoDataFrame(geometry=[box(0, 0, 40, 40)], crs=CRS)
    roads = gpd.GeoDataFrame(geometry=[LineString([(-100, 60), (140, 60)]),      # 20 m from the edge
                                       LineString([(-100, 140), (140, 140)])], crs=CRS)   # 100 m away
    blds = gpd.GeoDataFrame(geometry=[box(50, 10, 60, 20), box(85, 10, 95, 20),
                                      box(88, 10, 98, 20), box(120, 10, 130, 20)], crs=CRS)
    return micro, roads, blds


def test_edge_buffer_counts_and_distance():
    r = c.compute_scores(*layers(), buffers_m=[50], buffer_from="edge")
    assert r.loc[0, "road_count_50m"] == 1 and r.loc[0, "building_count_50m"] == 3
    assert r.loc[0, "score_50m"] == 2 * 1 + 3
    assert abs(r.loc[0, "dist_nearest_road_m"] - 20) < 1e-6


def test_centroid_buffer_reaches_less_far():
    r = c.compute_scores(*layers(), buffers_m=[50], buffer_from="centroid")
    assert r.loc[0, "building_count_50m"] == 1     # the choice of buffer origin changes the result


def test_settings_read_at_call_time():
    c.BUFFERS_M = [50, 100]
    try:
        r = c.compute_scores(*layers())
        assert "score_100m" in r.columns
    finally:
        c.BUFFERS_M = [50]
