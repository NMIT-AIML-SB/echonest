"""
Download the Bengaluru (BBMP) ward boundaries and turn them into ONE clean city boundary.

Why this step exists
  * The Bangalore URBAN DISTRICT (~2,200 sq km) is much bigger than the city. Clipping to it left rural
    farmland in the results. The BBMP city limits are about 710 sq km.
  * The ward file is 243 separately drawn polygons. Their union can contain tiny slivers/gaps at the
    seams, and some polygons are invalid. Here we repair them and close gaps up to ~15 m, which changes the
    total area by only about 0.01 sq km.

Source: Data{Meet} Municipal_Spatial_Data (Bangalore/BBMP.geojson on GitHub). It is downloaded when the
script runs and is not stored in this repository -- check the source's licence before re-publishing it.

Run:  python ../src/prepare_boundary.py          ->  bbmp_boundary_FINAL.geojson
"""
import argparse
import urllib.request

import geopandas as gpd

URL = "https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Bangalore/BBMP.geojson"
UTM_CRS = "EPSG:32643"          # metres; right zone for Bengaluru (use another zone for another city)


def clean_boundary(wards_path, out_path, gap_m=15):
    wards = gpd.read_file(wards_path)
    if wards.crs is None:
        wards = wards.set_crs("EPSG:4326")
    wards = wards.to_crs(UTM_CRS)
    wards["geometry"] = wards.geometry.buffer(0)                 # repairs invalid polygons
    union = wards.union_all()
    raw_km2 = union.area / 1e6
    closed = union.buffer(gap_m).buffer(-gap_m)                  # closes tiny gaps between wards
    out = gpd.GeoDataFrame({"name": ["Bangalore (BBMP)"]}, geometry=[closed], crs=UTM_CRS).to_crs("EPSG:4326")
    out.to_file(out_path, driver="GeoJSON")
    print(f"wards: {len(wards)} | area before gap-closing: {raw_km2:.2f} sq km | after: {closed.area/1e6:.2f} sq km")
    print("saved", out_path)
    return out


def main():
    p = argparse.ArgumentParser(description="Prepare the Bengaluru city boundary.")
    p.add_argument("--wards", default=None, help="use this ward file instead of downloading")
    p.add_argument("--out", default="bbmp_boundary_FINAL.geojson")
    p.add_argument("--gap-m", type=float, default=15, help="gaps up to about this size (metres) are closed")
    a = p.parse_args()
    wards = a.wards
    if wards is None:
        wards = "BBMP_wards_raw.geojson"
        print("downloading", URL)
        urllib.request.urlretrieve(URL, wards)
    clean_boundary(wards, a.out, a.gap_m)


if __name__ == "__main__":
    main()
