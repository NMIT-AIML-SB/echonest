// ============================================================================
// Export NDVI (band 1) and NDWI (band 2) for Bangalore from Sentinel-2, on the SAME grid.
// Run in the Google Earth Engine Code Editor: https://code.earthengine.google.com
// Then: Tasks tab -> Run -> the GeoTIFF appears in your Google Drive (folder GEE_exports).
//
// STATUS: not testable outside Earth Engine. The dates and region below are the ones used for the raster
// we analysed (an annual median composite, 10 m). CHECK that your existing Bangalore_NDVI.tif was made with
// the same settings before relying on this.
//
// To match the eBird study period change the dates to 2025-10-01 ... 2026-09-30.
// To cover every hotspot (many Bengaluru Rural hotspots lie outside the box below) enlarge REGION so that it
// contains the minimum/maximum latitude and longitude of the hotspot list.
// ============================================================================
var START  = '2024-01-01';
var END    = '2024-12-31';
var REGION = ee.Geometry.Rectangle([77.35, 12.75, 77.85, 13.15]);   // [west, south, east, north]
var MAX_CLOUD = 20;                                                  // % cloudy pixels allowed per scene

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(REGION)
  .filterDate(START, END)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD));

function maskClouds(image) {
  var qa = image.select('QA60');
  var cloud = 1 << 10, cirrus = 1 << 11;
  var clear = qa.bitwiseAnd(cloud).eq(0).and(qa.bitwiseAnd(cirrus).eq(0));
  return image.updateMask(clear).divide(10000).copyProperties(image, ['system:time_start']);
}

var composite = s2.map(maskClouds).median().clip(REGION);
var ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI');   // (NIR - Red) / (NIR + Red)
var ndwi = composite.normalizedDifference(['B3', 'B8']).rename('NDWI');   // (Green - NIR) / (Green + NIR)
var stacked = ndvi.addBands(ndwi);                                        // band 1 = NDVI, band 2 = NDWI

Map.centerObject(REGION, 10);
Map.addLayer(ndvi, {min: -1, max: 1, palette: ['blue', 'white', 'green']}, 'NDVI');
Map.addLayer(ndwi, {min: -1, max: 1, palette: ['brown', 'white', 'blue']}, 'NDWI');

Export.image.toDrive({
  image: stacked,
  description: 'Bangalore_NDVI_NDWI',
  folder: 'GEE_exports',
  fileNamePrefix: 'Bangalore_NDVI_NDWI',
  region: REGION,
  scale: 10,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
});
