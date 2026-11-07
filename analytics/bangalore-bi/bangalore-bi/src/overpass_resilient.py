"""
Resilient OSM download for a big area (e.g. all Bengaluru roads).

What it fixes (from your log: cells 1-5 fine, cell 6 timed out on two servers):
  1. A cell that is too heavy is SPLIT into 4 smaller cells instead of retried forever.
  2. Every finished cell is saved to disk, so a crash or re-run RESUMES where it stopped.
  3. Retries use exponential backoff + random jitter and rotate between servers.
  4. Only the road types you need are requested (not every footpath), so queries are lighter.
  5. Features that cross cell edges are de-duplicated when the pieces are merged.

Usage (in your notebook):
    from overpass_resilient import make_cells, download_cells, merge_cache, ROADS, BUILDINGS
    cells = make_cells(boundary_wgs84, cell_deg=0.02)
    failed = download_cells(cells, "osm_cache_roads", **ROADS)
    roads = merge_cache("osm_cache_roads")
    failed_b = download_cells(cells, "osm_cache_buildings", **BUILDINGS)
    buildings = merge_cache("osm_cache_buildings")
"""
import os
import time
import random
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

HIGHWAY_TYPES = [
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
    "residential", "living_street", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
]
ENDPOINTS = ["https://overpass-api.de/api", "https://overpass.kumi.systems/api"]


def make_cells(boundary_geom, cell_deg=0.02):
    """Grid of (minx, miny, maxx, maxy) cells (lon/lat) that touch the boundary."""
    minx, miny, maxx, maxy = boundary_geom.bounds
    cells = []
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            b = (x, y, min(x + cell_deg, maxx), min(y + cell_deg, maxy))
            if boundary_geom.intersects(box(*b)):
                cells.append(b)
            y += cell_deg
        x += cell_deg
    return cells


def make_fetch(tags):
    """Build a fetch function for any OSM tags. bbox = (west, south, east, north) for osmnx 2.x."""
    def fetch(bbox, endpoint, timeout):
        import osmnx as ox
        ox.settings.overpass_url = endpoint
        ox.settings.requests_timeout = timeout
        return ox.features_from_bbox(bbox, tags=tags)
    return fetch


# Ready-made presets: pass as  download_cells(cells, cache_dir, **BUILDINGS)
ROADS = dict(fetch=make_fetch({"highway": HIGHWAY_TYPES}),
             keep=["element", "id", "highway", "name", "geometry"])
BUILDINGS = dict(fetch=make_fetch({"building": True}),
                 keep=["element", "id", "building", "name", "geometry"])
osmnx_fetch = ROADS["fetch"]  # backward compatible name


def _fetch_with_fallback(bbox, fetch, endpoints, attempts, base_wait, timeout, sleep):
    last = None
    for attempt in range(attempts):
        for ep in endpoints:
            try:
                return fetch(bbox, ep, timeout)
            except Exception as e:
                if type(e).__name__ == "InsufficientResponseError":
                    return None  # server answered: genuinely no roads in this cell
                last = e
                sleep(base_wait * (2 ** attempt) + random.uniform(0, 3))
    raise last


def _key(bbox):
    return "_".join(f"{v:.5f}" for v in bbox)


def _process(bbox, depth, cache_dir, fetch, endpoints, attempts, base_wait, timeout,
             max_depth, sleep, failed, log, keep):
    base = os.path.join(cache_dir, _key(bbox))
    if os.path.exists(base + ".gpkg") or os.path.exists(base + ".empty"):
        return  # already done
    if not os.path.exists(base + ".split"):
        try:
            gdf = _fetch_with_fallback(bbox, fetch, endpoints, attempts, base_wait, timeout, sleep)
            if gdf is None or len(gdf) == 0:
                open(base + ".empty", "w").close()
            else:
                gdf = gdf.reset_index()
                cols = [c for c in keep if c in gdf.columns]
                gdf[cols].to_file(base + ".gpkg", driver="GPKG")
            log(f"ok    depth={depth} {bbox}")
            return
        except Exception as e:
            if depth >= max_depth:
                log(f"GIVE UP depth={depth} {bbox}: {type(e).__name__}")
                failed.append(bbox)
                return
            log(f"split depth={depth} {bbox}: {type(e).__name__}")
            open(base + ".split", "w").close()
    minx, miny, maxx, maxy = bbox
    mx, my = (minx + maxx) / 2, (miny + maxy) / 2
    for sub in [(minx, miny, mx, my), (mx, miny, maxx, my), (minx, my, mx, maxy), (mx, my, maxx, maxy)]:
        _process(sub, depth + 1, cache_dir, fetch, endpoints, attempts, base_wait, timeout,
                 max_depth, sleep, failed, log, keep)


def download_cells(cells, cache_dir, fetch=osmnx_fetch, keep=ROADS["keep"], endpoints=ENDPOINTS,
                   attempts=2, base_wait=5, timeout=180, max_depth=3, pause=1.0,
                   sleep=time.sleep, log=print):
    """Download every cell. Returns the list of cells that still failed (hopefully empty)."""
    os.makedirs(cache_dir, exist_ok=True)
    failed = []
    for i, bbox in enumerate(cells, 1):
        log(f"cell {i}/{len(cells)}")
        _process(bbox, 0, cache_dir, fetch, endpoints, attempts, base_wait, timeout,
                 max_depth, sleep, failed, log, keep)
        sleep(pause)  # be polite to the public servers
    return failed


def merge_cache(cache_dir):
    """Merge all cached cells into one GeoDataFrame, removing duplicates from cell edges."""
    parts = [gpd.read_file(os.path.join(cache_dir, f))
             for f in sorted(os.listdir(cache_dir)) if f.endswith(".gpkg")]
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    merged = pd.concat(parts, ignore_index=True)
    merged = merged.drop_duplicates(subset=["element", "id"])
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=parts[0].crs)
