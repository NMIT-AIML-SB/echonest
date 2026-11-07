import numpy as np
import rasterio
from rasterio.transform import from_origin

import detect_lakes_ndwi as lakes


def test_lake_found_and_speck_ignored(tmp_path):
    ndvi = np.zeros((300, 300), dtype="float32")
    ndwi = np.full((300, 300), -0.3, dtype="float32")
    ndwi[100:120, 100:120] = 0.5     # about 4 acres of water
    ndwi[10:12, 10:12] = 0.5         # a 2 x 2 pixel speck
    path = tmp_path / "two_band.tif"
    with rasterio.open(path, "w", driver="GTiff", height=300, width=300, count=2, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(77.5, 13.05, 0.0001, 0.0001)) as dst:
        dst.write(ndvi, 1)
        dst.write(ndwi, 2)
    gdf = lakes.run(str(path), min_acres=1.0, write=False)
    assert len(gdf) == 1
    assert gdf["area_acres"].iloc[0] > 1.0 and abs(gdf["mean_ndwi"].iloc[0] - 0.5) < 0.05
