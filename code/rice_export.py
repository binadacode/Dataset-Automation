import ee
import json
import os

# -------------------------
# 0. Setup authentication & initialize Earth Engine
# -------------------------
# Optional: path to your OAuth JSON (if using local credentials)
oauth_path = r"D:\iit\2nd yr\sgdp\code\ricevision_oauth.json"
if os.path.exists(oauth_path):
    os.environ['EARTHENGINE_TOKEN_FILE'] = oauth_path

# Authenticate (opens browser once, saves token)
ee.Authenticate()  

# Initialize with your registered project
ee.Initialize(project="ricevision")
print("✅ Earth Engine authenticated & initialized!")

# -------------------------
# 1. Load AOI from local GeoJSON
# -------------------------
with open("dambulla.geojson") as f:  # replace with your file name
    gj = json.load(f)

aoi = ee.FeatureCollection(gj)

# -------------------------
# 2. Load Sentinel-2 SR Harmonized with 50% cloud filter
# -------------------------
s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate("2021-01-01", "2025-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 50))
        .select(["B1","B2","B3","B4","B5","B6","B7","B8","B8A","B9","B11","B12","SCL"]))

# -------------------------
# 3. Mask cloudy/shadow pixels using SCL
# -------------------------
def mask_scl(img):
    scl = img.select("SCL")
    mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    return img.updateMask(mask)

s2 = s2.map(mask_scl)

# -------------------------
# 4. Create random sample points within AOI
# -------------------------
points = ee.FeatureCollection.randomPoints(region=aoi, points=1000, seed=42)

# Add latitude & longitude properties
def add_lat_lon(f):
    coords = f.geometry().coordinates()
    return f.set({
        "longitude": coords.get(0),
        "latitude": coords.get(1)
    })

points = points.map(add_lat_lon)

# -------------------------
# 5. Sample Sentinel-2 images at those points
# -------------------------
def sample_image(img):
    vals = img.sampleRegions(
        collection=points,
        scale=10,
        geometries=False
    )
    # Add metadata
    def add_meta(f):
        return f.set({
            "Date": ee.Date(img.get("system:time_start")).format("YYYY-MM-dd"),
            "Satellite": "Sentinel-2",
            "CloudyPixelPercent": img.get("CLOUDY_PIXEL_PERCENTAGE"),
            "longitude": f.get("longitude"),
            "latitude": f.get("latitude")
        })
    return vals.map(add_meta)

# Flatten all image samples into one collection
sampled = s2.map(sample_image).flatten()

# -------------------------
# 6. Export to Google Drive as CSV
# -------------------------
task = ee.batch.Export.table.toDrive(
    collection=sampled,
    description="Sentinel2_Rice_Bands_With_LatLon_Cloudiness_SCL",
    folder="GEE_Exports",
    fileNamePrefix="sentinel2_rice_samples",
    fileFormat="CSV"
)

task.start()
print("🚀 Export started! Check your Google Drive → GEE_Exports folder.")
