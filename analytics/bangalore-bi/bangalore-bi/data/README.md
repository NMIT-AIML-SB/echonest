# Data (not stored in this repository)

| File | What it is | Where it comes from |
|---|---|---|
| `Bangalore_NDVI.tif` | NDVI raster, band 1, 10 m pixels, lat/lon | Export with `gee/export_ndvi_ndwi.js` (about 110 MB, over GitHub's 100 MB limit) |
| `bbmp_boundary_FINAL.geojson` | One clean city boundary (BBMP) | Created by `src/prepare_boundary.py` (downloads the ward file at run time) |
| eBird files (`ebd_*.txt`, hotspot lists) | Bird observations and hotspots | eBird -- check eBird's data terms before sharing or committing any of it |
| OpenStreetMap roads/buildings | Human-activity layers | Created by `src/overpass_resilient.py` (OpenStreetMap contributors, ODbL licence) |

Put the files you need in your working folder (see the main README, "Quick start").
