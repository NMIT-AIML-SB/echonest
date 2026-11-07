# Biodiversity islands (BIs) of Bengaluru from satellite NDVI

This project finds patches of green vegetation ("biodiversity islands") in Bengaluru from a satellite
vegetation map (NDVI), measures their size, and links them to eBird hotspots and to signs of human activity
(roads and buildings). It is research code, written step by step with our professor's feedback.

## In plain words

1. A satellite image is turned into an **NDVI** map: every 10 m x 10 m pixel gets a "greenness" value.
2. Pixels with NDVI of **0.4 or more** are called *green*.
3. Green pixels that touch each other (sideways or diagonally) form one **BI**.
4. We measure each BI: area in acres, average NDVI, outline, and centre point.

## Definitions used

| Term | Meaning |
|---|---|
| NDVI | (NIR - Red) / (NIR + Red). Higher means more vegetation. |
| BI | A connected group of green pixels (NDVI >= 0.4, 8-connectivity). Any size. |
| microBI | A BI of 0.5 to 4 acres. |
| macroBI | A BI larger than 4 acres. |
| Lake | A connected group of water pixels, found from NDWI = (Green - NIR) / (Green + NIR), NDWI > 0. |
| Thin-bridge fix | Removes 1-pixel-wide strips first, so two patches joined only by a thin strip are not merged. |

## Folder layout

```
src/      the scripts (one job each, described below)
gee/      Google Earth Engine script that creates the NDVI raster
tests/    automatic checks on small made-up data (run: python -m pytest)
data/     notes about the input data (the data itself is NOT in this repo)
```

## Setup

Python 3.10 or newer.
```
pip install -r requirements.txt
```

## Quick start

Work in one folder, for example `work/`, and run the scripts from inside it. Put your input files there.
Scripts read and write in the current folder.

```
mkdir work && cd work

# 1. City boundary (downloads the ward file, repairs it, writes bbmp_boundary_FINAL.geojson)
python ../src/prepare_boundary.py

# 2. NDVI raster: run gee/export_ndvi_ndwi.js in Google Earth Engine,
#    then copy the downloaded GeoTIFF into this folder (we call it Bangalore_NDVI.tif).

# 3. Find the microBIs and macroBIs
python ../src/detect_bis.py --ndvi Bangalore_NDVI.tif --boundary bbmp_boundary_FINAL.geojson

# 4. Check them and describe them
python ../src/plot_bis_in_boundary.py --bis microBIs_full.geojson     # are all inside the city?
python ../src/bi_distributions.py                                     # size and NDVI distributions

# 5. Zoomable map of all microBIs (open the .html in a browser, needs internet)
python ../src/make_interactive_map.py
```

More steps:

```
# BI area at every eBird hotspot (needs the hotspot workbook from the eBird analysis)
python ../src/hotspot_bi_area.py

# Map of the BIs around Ferns Residency (outlines + areas on satellite imagery)
python ../src/ferns_residency_map.py

# Human activity around each microBI (roads and buildings from OpenStreetMap)
python ../src/download_osm_layers.py --boundary bbmp_boundary_FINAL.geojson
python ../src/compute_human_activity.py

# Lakes (needs a raster whose band 2 is NDWI)
python ../src/detect_lakes_ndwi.py --raster Bangalore_NDVI_NDWI.tif --boundary bbmp_boundary_FINAL.geojson
```

## What each script does

| Script | Does | Needs | Creates | How it was checked |
|---|---|---|---|---|
| `prepare_boundary.py` | One clean BBMP city boundary (about 710 sq km) | internet | `bbmp_boundary_FINAL.geojson` | Run on the real data |
| `detect_bis.py` | Finds microBIs and macroBIs | NDVI raster, boundary | `microBIs_full.geojson`, `macroBIs.geojson`, summary CSVs | Real data; reproduces our earlier results (see below); tests |
| `plot_bis_in_boundary.py` | Counts and maps BIs inside / outside the boundary | BI file, boundary | `*_in_boundary.png` | Real data |
| `bi_distributions.py` | Area histogram (0.1-acre bins), NDVI histogram, mean and standard deviation counts | `microBIs_summary.csv` | PNGs and CSVs | Real data |
| `make_interactive_map.py` | Zoomable map: click a microBI, search by ID, satellite view | `microBIs_full.geojson` | `bangalore_microBIs_interactive.html` | Opened in a headless browser (search and popup work); real map tiles not tested offline |
| `hotspot_bi_area.py` | Area of the BI at every eBird hotspot | NDVI raster, hotspot workbook | `Bengaluru_Hotspot_BI_Area_2026.xlsx` | Real data |
| `ferns_residency_map.py` | BIs in a 400 x 520 m box around Ferns Residency, on satellite imagery | NDVI raster | `ferns_residency_map.html` / `.png`, CSV | Real data; satellite download not tested offline |
| `download_osm_layers.py`, `overpass_resilient.py` | Downloads OSM roads and buildings, survives timeouts, resumes | internet | `osm_cache_roads/`, `osm_cache_buildings/` | Simulated failing server (the live servers could not be reached while testing) |
| `compute_human_activity.py` | Per microBI: roads, buildings and distance to the nearest road within a buffer (default 50 m) and a score | OSM layers, microBIs | `microBI_human_activity.csv`, plots | Hand-checked case and a speed test on made-up data; not yet run on real OSM data |
| `detect_lakes_ndwi.py` | Lakes from NDWI | raster with NDWI in band 2 | `lakes.geojson` | Made-up data only; not yet run on real NDWI |
| `gee/export_ndvi_ndwi.js` | Creates the NDVI + NDWI raster | Google Earth Engine account | GeoTIFF in Google Drive | Cannot be tested outside Earth Engine |

## Example results (our Bengaluru run)

These come from our `Bangalore_NDVI.tif`, clipped to the BBMP boundary, NDVI >= 0.4, thin-bridge fix on.
Re-running with another raster gives different numbers.

* microBIs: **4,845**; macroBIs: **765**; none outside the boundary.
* microBI mean NDVI **0.535**, standard deviation **0.048**. Within +/-1, 2, 3 standard deviations:
  3,245 (67.0 %), 4,660 (96.2 %), 4,838 (99.9 %).
* Most microBIs are small: the most common size bin is 0.5 to 0.6 acres (950 microBIs), and the counts fall
  steadily towards 4 acres.
* eBird hotspots (744): 218 lie on a green pixel, 384 do not (the nearest BI is reported with its distance),
  and 142 are outside the raster.
* Ferns Residency: the BI at the hotspot is 13.06 acres with plain connectivity, but only 1.36 acres with the
  thin-bridge fix, which shows how much the limitation below matters.

## Known limitations (read before using the numbers)

1. **Thin strips merge patches.** Two large green areas joined by even a 1-pixel-wide strip become one BI.
   `--no-bridge-fix` gives plain connectivity; the default removes thin bridges. The two give very different areas
   (median BI area at hotspots: 5.2 acres plain vs 2.6 acres with the fix). Which one is "right" is still an open
   question for the professor.
2. **NDVI cannot tell crops from natural vegetation.** Farmland can pass the 0.4 threshold. We clip to the city
   boundary to limit this, but parks, gardens, lawns and crops can all be counted. NDVI >= 0.4 is a common
   vegetation threshold, not a measured "percent vegetation cover".
3. **The raster has a date.** Check which period your NDVI composite covers; it may not match the bird data period.
4. **Boundary matters.** The Bangalore Urban district is about three times the size of the city. Everyone
   comparing results (for example in R and Python) must use the same boundary file. Our boundary closes gaps of
   up to 15 m between ward polygons. Our first published lists used the boundary without that step: 3 of the
   4,845 microBIs and 10 of the 765 macroBIs differ. To reproduce the first lists exactly, run
   `prepare_boundary.py --gap-m 0`.
5. **Hotspot pins are not always on vegetation** (roads, lake edges). For those we report the nearest BI and the
   distance; read the distance before using the area.
6. **OpenStreetMap may be incomplete** in some parts of the city, so human-activity scores can be too low there.
7. **Lake area is not the official lake area.** It is the water seen in one composite image.

## Tests

```
python -m pytest
```
The tests use small made-up data with known answers (for example: diagonal pixels form one BI; the thin-bridge fix
splits two blocks joined by a strip; the downloader resumes without downloading again).

## Data and licences

Data is not stored in this repository (see `data/README.md`). The city boundary comes from Data{Meet}
Municipal_Spatial_Data, roads and buildings from OpenStreetMap contributors (ODbL), bird data from eBird.
Check each source's terms before sharing the data. No licence has been chosen for the code yet.

## Authors

Fill in the names of the team members and the professor.