"""
Download all roads and buildings inside the city boundary from OpenStreetMap (one-time job, saved to disk).

Uses overpass_resilient.py, which splits cells that time out, retries with waiting, and RESUMES if you stop
and run it again. Buildings are far more numerous than roads, so that part can take much longer.

Run:  python ../src/download_osm_layers.py --boundary bbmp_boundary_FINAL.geojson
Creates the folders osm_cache_roads/ and osm_cache_buildings/ (used by compute_human_activity.py).
Needs internet access to the public Overpass servers.
"""
import argparse

import geopandas as gpd

from overpass_resilient import BUILDINGS, ROADS, download_cells, make_cells


def main():
    p = argparse.ArgumentParser(description="Download OSM roads and buildings for the city.")
    p.add_argument("--boundary", default="bbmp_boundary_FINAL.geojson")
    p.add_argument("--cell-deg", type=float, default=0.02, help="size of one download cell in degrees")
    p.add_argument("--only", choices=["roads", "buildings"], default=None)
    a = p.parse_args()
    boundary = gpd.read_file(a.boundary).to_crs("EPSG:4326").union_all()
    cells = make_cells(boundary, cell_deg=a.cell_deg)
    print(f"{len(cells)} download cells")
    jobs = [("roads", "osm_cache_roads", ROADS), ("buildings", "osm_cache_buildings", BUILDINGS)]
    for name, folder, preset in jobs:
        if a.only in (None, name):
            print(f"\n== {name} ==")
            failed = download_cells(cells, folder, **preset)
            print(f"{name}: {len(failed)} cells still failed" + (" -- run again later" if failed else ""))


if __name__ == "__main__":
    main()
