"""
Distributions of the microBIs: by AREA and by mean NDVI, plus the mean +/- k standard deviation counts.

Outputs
  hist_area_distribution.png    x = area in acres (0.1-acre bins from 0.5 to 4), y = number of microBIs
  microBI_area_bins.csv         the count in every area bin
  hist_ndvi_distribution.png    x = mean NDVI of the microBI, y = number of microBIs
  microBI_ndvi_statistics.csv   mean, standard deviation, and how many microBIs lie within
                                mean +/- 1, 2 and 3 standard deviations

Run:  python ../src/bi_distributions.py            (reads microBIs_summary.csv)
"""
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def area_histogram(df, lo=0.5, hi=4.0, width=0.1, out_png="hist_area_distribution.png", out_csv="microBI_area_bins.csv"):
    edges = np.round(np.arange(lo, hi + width / 2, width), 6)
    counts, edges = np.histogram(df["area_acres"], bins=edges)
    table = pd.DataFrame({"bin_start_acres": edges[:-1].round(2), "bin_end_acres": edges[1:].round(2), "count": counts})
    table.to_csv(out_csv, index=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(edges[:-1], counts, width=width, align="edge", color="#f57c00", edgecolor="black")
    ax.set_xlabel("microBI area (acres)")
    ax.set_ylabel("Number of microBIs")
    ax.set_title(f"microBI area distribution (n = {len(df)}, bin width {width} acre)")
    fig.tight_layout(); fig.savefig(out_png, dpi=200); plt.close(fig)
    return table


def ndvi_histogram_and_stats(df, bins=30, out_png="hist_ndvi_distribution.png", out_csv="microBI_ndvi_statistics.csv"):
    v = df["mean_ndvi"]
    mean, sd, n = v.mean(), v.std(), len(v)
    row = {"n_microBIs": n, "mean_ndvi": round(mean, 4), "std_ndvi": round(sd, 4)}
    for k in (1, 2, 3):
        inside = int(((v >= mean - k * sd) & (v <= mean + k * sd)).sum())
        row[f"n_within_{k}sd"] = inside
        row[f"pct_within_{k}sd"] = round(100 * inside / n, 2)
        row[f"range_{k}sd"] = f"{mean - k * sd:.3f} to {mean + k * sd:.3f}"
    stats = pd.DataFrame([row])
    stats.to_csv(out_csv, index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(v, bins=bins, color="#2e7d32", edgecolor="black")
    ax.axvline(mean, color="red", linestyle="--", label=f"mean {mean:.3f}")
    ax.set_xlabel("Mean NDVI of the microBI")
    ax.set_ylabel("Number of microBIs")
    ax.set_title(f"microBI mean-NDVI distribution (n = {n})")
    ax.legend()
    fig.tight_layout(); fig.savefig(out_png, dpi=200); plt.close(fig)
    return stats


def main():
    p = argparse.ArgumentParser(description="Area and NDVI distributions of the microBIs.")
    p.add_argument("--summary", default="microBIs_summary.csv", help="CSV with columns area_acres and mean_ndvi")
    a = p.parse_args()
    df = pd.read_csv(a.summary)
    table = area_histogram(df)
    stats = ndvi_histogram_and_stats(df)
    print("area bins with the most microBIs:\n", table.sort_values("count", ascending=False).head(5).to_string(index=False))
    print("\nNDVI statistics:\n", stats.T.to_string(header=False))


if __name__ == "__main__":
    main()
