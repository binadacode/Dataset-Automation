import ee
import os
import json
import requests
import geopandas as gpd
import folium
import webbrowser

# -----------------------------
# 1. Authenticate Earth Engine
# -----------------------------
os.environ['GOOGLE_OAUTH_CREDENTIALS'] = r"D:\iit\2nd yr\sgdp\code\ricevision_oauth.json"
ee.Authenticate()
ee.Initialize(project='ricevision')
print("✅ Earth Engine authenticated!")

# -----------------------------
# 2. Load ROI
# -----------------------------
geojson_path = r"D:\iit\2nd yr\sgdp\code\my_roi.geojson"
with open(geojson_path) as f:
    geojson_data = json.load(f)

roi = ee.FeatureCollection(geojson_data)
roi_geom = roi.geometry()
center = roi_geom.centroid(maxError=1).coordinates().getInfo()
bounds = roi_geom.bounds().getInfo()['coordinates'][0]
min_lon = min([c[0] for c in bounds])
max_lon = max([c[0] for c in bounds])
min_lat = min([c[1] for c in bounds])
max_lat = max([c[1] for c in bounds])

# -----------------------------
# 3. Create export folders
# -----------------------------
export_dir = r"C:\Temp\RicePipeline"
shp_dir = os.path.join(export_dir, "shapefile")
os.makedirs(export_dir, exist_ok=True)
os.makedirs(shp_dir, exist_ok=True)
print(f"📁 Export folders ready: {export_dir} and {shp_dir}")

# -----------------------------
# 4. WORLD CEREAL — TEMPORARY CROPS
# -----------------------------
print("📡 Loading WorldCereal temporary crops (2021)...")
wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100") \
        .filter(ee.Filter.eq("product", "temporarycrops")) \
        .mosaic() \
        .clip(roi_geom)

class_img = wc.select("classification")   # 0 or 100
conf_img  = wc.select("confidence")       # 0–100

mask = class_img.eq(100).selfMask()       # Only paddy/seasonal crops

# -----------------------------
# 5. Compute Crop Area
# -----------------------------
pixel_area = mask.multiply(ee.Image.pixelArea())
stats = pixel_area.reduceRegion(
    reducer=ee.Reducer.sum(),
    geometry=roi_geom,
    scale=10,
    maxPixels=1e13
)
area_m2 = stats.get("classification").getInfo() if stats.get("classification") else 0
area_ha = area_m2 / 10000
print(f"📏 Estimated temporary-crop (paddy) area: {area_ha:.2f} hectares")

# -----------------------------
# 6. Convert mask to vectors
# -----------------------------
print("📦 Converting detected area to vector polygons...")
vectors = mask.reduceToVectors(
    geometry=roi_geom,
    scale=10,
    geometryType='polygon',
    eightConnected=True,
    labelProperty='paddy',
    maxPixels=1e13
)

# -----------------------------
# 7. Enrich polygons with area & confidence
# -----------------------------
print("📦 Enriching polygons with area and mean confidence...")
def enrich_feature(f):
    area_ha = f.geometry().area(maxError=1).divide(10000)
    conf_mean = conf_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=f.geometry(),
        scale=10,
        maxPixels=1e12
    ).get("confidence")
    return f.set({"area_ha": area_ha, "mean_conf": conf_mean})

vectors_fc = vectors.map(enrich_feature)
vectors_fc = vectors_fc.filter(ee.Filter.gt('area_ha', 0.01))  # filter tiny polygons

# -----------------------------
# 8. Export GeoJSON to local
# -----------------------------
print("💾 Exporting polygons as GeoJSON locally...")
geojson_path = os.path.join(export_dir, "paddy_detected.geojson")
geojson_data = vectors_fc.getInfo()  # small/medium ROI only
with open(geojson_path, "w") as f:
    json.dump(geojson_data, f)
print(f"🟩 GeoJSON saved → {geojson_path}")

# -----------------------------
# 9. Convert GeoJSON to Shapefile for GEE
# -----------------------------
print("💾 Converting GeoJSON to Shapefile...")
gdf = gpd.read_file(geojson_path)
shp_path = os.path.join(shp_dir, "paddy_detected.shp")
gdf.to_file(shp_path, driver='ESRI Shapefile')
print(f"✅ Shapefile saved → {shp_path}")

# -----------------------------
# 10. Download Sentinel-2 satellite image
# -----------------------------
print("🛰️ Fetching Sentinel-2 satellite view...")
s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi_geom)
        .filterDate("2024-01-01", "2024-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .median()
        .clip(roi_geom))

rgb = s2.select(["B4","B3","B2"]).visualize(min=0, max=3000)
sat_url = rgb.getDownloadURL({"scale":10,"region":roi_geom,"format":"png"})
sat_path = os.path.join(export_dir, "satellite.png")
with open(sat_path, "wb") as f:
    f.write(requests.get(sat_url).content)
print(f"🛰️ Satellite image saved → {sat_path}")

# -----------------------------
# 11. Download Paddy mask PNG
# -----------------------------
print("⬇️ Downloading WorldCereal paddy mask...")
mask_rgb = mask.visualize(min=0, max=1, palette=["000000","00FF00"])
mask_url = mask_rgb.getDownloadURL({"scale":10,"region":roi_geom,"format":"png"})
mask_path = os.path.join(export_dir, "wc_mask.png")
with open(mask_path, "wb") as f:
    f.write(requests.get(mask_url).content)
print(f"🟩 Paddy mask saved → {mask_path}")

# -----------------------------
# 12. Create Folium map
# -----------------------------
print("🌍 Creating combined satellite + mask map...")
m = folium.Map(location=[center[1], center[0]], zoom_start=14)

# Satellite base
folium.raster_layers.ImageOverlay(
    name="Satellite View",
    image=sat_path,
    bounds=[[min_lat, min_lon], [max_lat, max_lon]],
    opacity=1.0
).add_to(m)

# Paddy mask overlay
folium.raster_layers.ImageOverlay(
    name="Paddy Mask",
    image=mask_path,
    bounds=[[min_lat, min_lon], [max_lat, max_lon]],
    opacity=0.55
).add_to(m)

m.add_child(folium.LayerControl())
map_path = os.path.join(export_dir, "satellite_with_mask.html")
m.save(map_path)
webbrowser.open(map_path)
print(f"🌐 Map saved → {map_path}")

print("🎉 DONE! GeoJSON, Shapefile, satellite image, mask, and Folium map generated.")
