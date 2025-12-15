import ee
import os
import json

# -----------------------------
# 1. Authenticate Earth Engine
# -----------------------------
os.environ['GOOGLE_OAUTH_CREDENTIALS'] = r"D:\iit\2nd yr\sgdp\code\ricevision_oauth.json"
ee.Authenticate()
ee.Initialize(project='ricevision')
print("✅ Earth Engine authenticated!")

# -----------------------------
# 2. Setup folders and paths
# -----------------------------
geojson_folder = r"D:\iit\2nd yr\sgdp\geojsons"  # folder with all district GeoJSONs
export_folder_drive = "RicePipeline"  # Google Drive folder
export_dir_local = r"C:\Temp\RicePipeline"
os.makedirs(export_dir_local, exist_ok=True)
print(f"📁 Local folder ready: {export_dir_local}")

# -----------------------------
# 3. Process each district
# -----------------------------
for geojson_file in os.listdir(geojson_folder):
    if not geojson_file.endswith(".geojson"):
        continue

    district_name = os.path.splitext(geojson_file)[0]
    print(f"\n🌍 Processing district: {district_name}")

    # Load ROI from local GeoJSON
    geojson_path = os.path.join(geojson_folder, geojson_file)
    with open(geojson_path) as f:
        geojson_data = json.load(f)

    roi = ee.FeatureCollection(geojson_data)
    roi_geom = roi.geometry()

    # -----------------------------
    # 4. Load WorldCereal temporary crops
    # -----------------------------
    wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100") \
            .filter(ee.Filter.eq("product", "temporarycrops")) \
            .mosaic() \
            .clip(roi_geom)

    class_img = wc.select("classification")
    conf_img = wc.select("confidence")
    mask = class_img.eq(100).selfMask()

    # Compute estimated area
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
    # 5. Convert mask to vectors
    # -----------------------------
    vectors = mask.reduceToVectors(
        geometry=roi_geom,
        scale=10,
        geometryType='polygon',
        eightConnected=True,
        labelProperty='paddy',
        maxPixels=1e13
    )

    # Enrich polygons with area and confidence
    def enrich_feature(f):
        area_ha = f.geometry().area(maxError=1).divide(10000)
        conf_mean = conf_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=f.geometry(),
            scale=10,
            maxPixels=1e12
        ).get("confidence")
        return f.set({"area_ha": area_ha, "mean_conf": conf_mean})

    vectors_fc = vectors.map(enrich_feature).filter(ee.Filter.gt('area_ha', 0.01))

    # -----------------------------
    # 6. Export vectors to Google Drive
    # -----------------------------
    task_vectors = ee.batch.Export.table.toDrive(
        collection=vectors_fc,
        description=f"{district_name}_paddy_vectors",
        folder=export_folder_drive,
        fileNamePrefix=f"{district_name}_paddy",
        fileFormat="GeoJSON"
    )
    task_vectors.start()
    print(f"🚀 Export started to Drive for {district_name} (vectors)")

    # -----------------------------
    # 7. Export high-res Sentinel-2 image to Google Drive
    # -----------------------------
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(roi_geom)
            .filterDate("2024-01-01", "2024-12-31")
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .median()
            .clip(roi_geom))

    rgb = s2.select(["B4", "B3", "B2"]).visualize(min=0, max=3000)

    task_image = ee.batch.Export.image.toDrive(
        image=rgb,
        description=f"{district_name}_Sentinel2",
        folder=export_folder_drive,
        fileNamePrefix=f"{district_name}_sentinel2_10m",
        region=roi_geom,
        scale=10,
        maxPixels=1e13,
        fileFormat="GeoTIFF"
    )
    task_image.start()
    print(f"🚀 Export started to Drive for {district_name} (Sentinel-2)")

print("🎉 ALL districts queued for export!")
