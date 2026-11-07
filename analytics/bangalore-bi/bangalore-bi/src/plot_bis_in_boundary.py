"""
Check, and show on a map, that every BI lies inside the city boundary.

Each BI is classified by its centroid: inside (blue) or outside (red). Use it for microBIs, macroBIs or lakes.
Both people checking results (for example in Python and in R) must use the SAME boundary file, otherwise a
few BIs at the edge will disagree -- see README, "Known limitations".

Run:  python ../src/plot_bis_in_boundary.py --bis microBIs_full.geojson --boundary bbmp_boundary_FINAL.geojson
Writes <name>_in_boundary.png and prints the inside / outside counts.
"""
import argparse
import os

import geopandas as gpd
import matplotlib.pyplot as plt

UTM_CRS = "EPSG:32643"


def classify(bis, boundary):
    """Adds a boolean 'inside' column (centroid computed in metres, then compared in lat/lon)."""
    cen = gpd.GeoSeries(bis.to_crs(UTM_CRS).geometry.centroid, crs=UTM_CRS).to_crs("EPSG:4326")
    b = boundary.to_crs("EPSG:4326").union_all()
    bis = bis.copy()
    bis["inside"] = cen.within(b).values
    bis["cx"], bis["cy"] = cen.x.values, cen.y.values
    return bis


def main():
    p = argparse.ArgumentParser(description="Plot BIs against the city boundary.")
    p.add_argument("--bis", default="microBIs_full.geojson")
    p.add_argument("--boundary", default="bbmp_boundary_FINAL.geojson")
    a = p.parse_args()
    bis = classify(gpd.read_file(a.bis), gpd.read_file(a.boundary))
    n, n_in = len(bis), int(bis["inside"].sum())
    print(f"total {n} | inside {n_in} | outside {n - n_in}")

    fig, ax = plt.subplots(figsize=(9, 9))
    gpd.read_file(a.boundary).to_crs("EPSG:4326").boundary.plot(ax=ax, color="black", linewidth=1.5)
    ins, out = bis[bis["inside"]], bis[~bis["inside"]]
    ax.scatter(ins["cx"], ins["cy"], s=4, color="blue", alpha=0.6, label="Inside boundary")
    if len(out):
        ax.scatter(out["cx"], out["cy"], s=15, color="red", edgecolor="black", linewidth=0.5, label="Outside boundary")
    ax.set_title(f"{os.path.basename(a.bis)}: total {n} | inside {n_in} | outside {n - n_in}", fontweight="bold")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude"); ax.set_aspect("equal"); ax.grid(alpha=0.3)
    ax.legend(loc="upper right")
    fig.tight_layout()
    png = os.path.splitext(os.path.basename(a.bis))[0] + "_in_boundary.png"
    fig.savefig(png, dpi=200); plt.close(fig)
    print("saved", png)


if __name__ == "__main__":
    main()
