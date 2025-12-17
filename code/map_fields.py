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
geojson_folder = r"D:\iit\2nd yr\sgdp\geojsons"  # District GeoJSONs
export_folder_drive = "RicePipeline"            # Google Drive folder
print("📁 Export folder (Drive):", export_folder_drive)

# -----------------------------
# 3. Process each district
# -----------------------------
for geojson_file in os.listdir(geojson_folder):
    if not geojson_file.endswith(".geojson"):
        continue

    district_name = os.path.splitext(geojson_file)[0]
    print(f"\n🌍 Processing district: {district_name}")

    # Load ROI
    geojson_path = os.path.join(geojson_folder, geojson_file)
    with open(geojson_path) as f:
        geojson_data = json.load(f)

    roi = ee.FeatureCollection(geojson_data)
    roi_geom = roi.geometry()

    # -----------------------------
    # 4. Load WorldCereal temporary crops
    # -----------------------------
    wc = (ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
          .filter(ee.Filter.eq("product", "temporarycrops"))
          .mosaic()
          .clip(roi_geom))

    class_img = wc.select("classification")
    conf_img = wc.select("confidence")

    # Paddy class = 100
    mask = class_img.eq(100).selfMask()

    # -----------------------------
    # 5. Convert raster mask to vectors
    # -----------------------------
    vectors = mask.reduceToVectors(
        geometry=roi_geom,
        scale=10,
        geometryType='polygon',
        eightConnected=True,
        labelProperty='paddy',
        maxPixels=1e13
    )

    # Add area (ha) and mean confidence
    def enrich_feature(f):
        area_ha = f.geometry().area(maxError=1).divide(10000)
        mean_conf = conf_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=f.geometry(),
            scale=10,
            maxPixels=1e12
        ).get("confidence")
        return f.set({
            "area_ha": area_ha,
            "mean_conf": mean_conf
        })

    vectors_fc = (
        vectors
        .map(enrich_feature)
        .filter(ee.Filter.gt("area_ha", 0.01))  # remove tiny polygons
    )

    # -----------------------------
    # 6. Export vectors to Google Drive (SHP)
    # -----------------------------
    task = ee.batch.Export.table.toDrive(
        collection=vectors_fc,
        description=f"{district_name}_paddy_vectors",
        folder=export_folder_drive,
        fileNamePrefix=f"{district_name}_paddy",
        fileFormat="SHP"
    )

    task.start()
    print(f"🚀 Shapefile export started for {district_name}")

print("\n🎉 All districts queued — shapefiles only!")
