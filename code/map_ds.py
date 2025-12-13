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
# 2. LOAD SRI LANKA DS DIVISIONS (GAUL LEVEL-2)
# -----------------------------
print("📡 Loading Sri Lanka DS Divisions (GAUL Level-2)...")

ds_fc = (
    ee.FeatureCollection("FAO/GAUL/2015/level2")
    .filter(ee.Filter.eq("ADM0_NAME", "Sri Lanka"))
)

# Geometry bounds
ds_geom = ds_fc.geometry()
center = ds_geom.centroid().coordinates().getInfo()
bounds = ds_geom.bounds().getInfo()['coordinates'][0]
min_lon = min([c[0] for c in bounds])
max_lon = max([c[0] for c in bounds])
min_lat = min([c[1] for c in bounds])
max_lat = max([c[1] for c in bounds])

print("📍 DS divisions loaded!")

# -----------------------------
# 3. Create export folders
# -----------------------------
export_dir = r"C:\Temp\DS_Divisions"
shp_dir = os.path.join(export_dir, "shapefile")
os.makedirs(export_dir, exist_ok=True)
os.makedirs(shp_dir, exist_ok=True)
print(f"📁 Export folders ready: {export_dir}")

# -----------------------------
# 4. Export DS divisions locally as GeoJSON
# -----------------------------
print("💾 Exporting DS divisions GeoJSON...")

local_geojson_path = os.path.join(export_dir, "sri_lanka_ds.geojson")

geojson_export = ds_fc.getInfo()
with open(local_geojson_path, "w") as f:
    json.dump(geojson_export, f)

print(f"🟩 DS GeoJSON saved → {local_geojson_path}")

# -----------------------------
# 5. Convert GeoJSON → Shapefile
# -----------------------------
print("💾 Converting to Shapefile...")

gdf = gpd.read_file(local_geojson_path)
shp_path = os.path.join(shp_dir, "sri_lanka_ds.shp")
gdf.to_file(shp_path, driver='ESRI Shapefile')

print(f"✅ Shapefile saved → {shp_path}")

# -----------------------------
# 6. Make a simple PNG thumbnail of DS divisions
# -----------------------------
print("🖼 Generating PNG preview...")

ds_rgb = ds_fc.style(
    color="00FFFF",
    width=1,
    fillColor="00000000"
)

png_url = ds_rgb.getThumbURL({
    "region": ds_geom,
    "scale": 2000,
    "format": "png"
})

png_path = os.path.join(export_dir, "ds_preview.png")
with open(png_path, "wb") as f:
    f.write(requests.get(png_url).content)

print(f"🖼 DS preview image saved → {png_path}")

# -----------------------------
# 7. Folium Map
# -----------------------------
print("🌍 Creating Folium map...")

m = folium.Map(location=[center[1], center[0]], zoom_start=7)

folium.raster_layers.ImageOverlay(
    name="DS Divisions",
    image=png_path,
    bounds=[[min_lat, min_lon], [max_lat, max_lon]],
    opacity=0.9
).add_to(m)

m.add_child(folium.LayerControl())

html_path = os.path.join(export_dir, "ds_map.html")
m.save(html_path)
webbrowser.open(html_path)

print(f"🌐 Folium map saved → {html_path}")

print("🎉 DONE! Sri Lanka DS Divisions mapped successfully.")
