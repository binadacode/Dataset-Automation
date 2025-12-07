import ee
import folium
import os
import json

# ------------------------------
# Step 1: Set OAuth JSON path
# ------------------------------
os.environ['GOOGLE_OAUTH_CREDENTIALS'] = r'D:\iit\2nd yr\sgdp\code\ricevision_oauth.json'

# ------------------------------
# Step 2: Authenticate & Initialize with project
# ------------------------------
ee.Authenticate()
ee.Initialize(project='ricevision')
print("✅ Earth Engine authenticated & initialized with project 'ricevision'!")

# ------------------------------
# Step 3: Load ROI from GeoJSON
# ------------------------------
geojson_path = r'D:\iit\2nd yr\sgdp\code\my_roi.geojson'  # <-- replace with your file
with open(geojson_path) as f:
    geojson_data = json.load(f)

roi = ee.FeatureCollection(geojson_data)

# ------------------------------
# Step 4: Simplify geometry for centroid and export
# ------------------------------
roi_geom = ee.Geometry(roi.geometry().bounds())

# Compute centroid with maxError
center = roi_geom.centroid(maxError=1).coordinates().getInfo()

# ------------------------------
# Step 5: Load Sentinel-2 dataset & filter
# ------------------------------
collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(roi_geom)
              .filterDate('2025-01-01', '2025-12-31')
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
             )

image = collection.median().clip(roi_geom)

# ------------------------------
# Step 6: NDVI calculation
# ------------------------------
ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

# Threshold NDVI for rice fields (NDVI > 0.5)
rice_mask = ndvi.gt(0.5)
rice_field = ndvi.updateMask(rice_mask)  # single-band NDVI for visualization

# ------------------------------
# Step 7: Visualization parameters
# ------------------------------
rgb_vis = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000, 'gamma': 1.4}
ndvi_vis = {'min': 0, 'max': 1, 'palette': ['white', 'green']}

# ------------------------------
# Step 8: Map / display with folium
# ------------------------------
m = folium.Map(location=[center[1], center[0]], zoom_start=12)

def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=name,
        overlay=True,
        control=True
    ).add_to(self)

folium.Map.add_ee_layer = add_ee_layer
m.add_ee_layer(image, rgb_vis, 'Sentinel-2 RGB')
m.add_ee_layer(rice_field, ndvi_vis, 'Rice Fields (NDVI>0.5)')

m.add_child(folium.LayerControl())
m.save('map_fields.html')
print("🌍 Map saved as map_fields.html")

# ------------------------------
# Step 9: Calculate rice-field area (hectares)
# ------------------------------
pixel_area = rice_field.multiply(ee.Image.pixelArea())
total_area_m2 = pixel_area.reduceRegion(
    reducer=ee.Reducer.sum(),
    geometry=roi_geom,
    scale=10,
    maxPixels=1e9
).get('NDVI')

total_area_ha = ee.Number(total_area_m2).divide(10000)
print("📏 Total rice-field area (ha):", total_area_ha.getInfo())

# ------------------------------
# Step 10: Export rice-field NDVI mask to Google Drive
# ------------------------------
export_task = ee.batch.Export.image.toDrive(
    image=rice_field,
    description='Rice_Field_Export',
    folder='GEE_Exports',
    fileNamePrefix='rice_fields',
    region=roi_geom,
    scale=10,
    maxPixels=1e9
)

export_task.start()
print("🚀 Export started! Check your Google Drive → GEE_Exports folder.")
