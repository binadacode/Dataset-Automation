import geopandas as gpd
import glob
import pandas as pd

# Get all shapefiles
files = glob.glob("district_shapefiles/*.shp")

# Read and combine
gdf_list = [gpd.read_file(file) for file in files]

merged = gpd.GeoDataFrame(pd.concat(gdf_list, ignore_index=True))

# Ensure correct CRS
merged = merged.to_crs("EPSG:4326")

# Save as single GeoJSON
merged.to_file("sri_lanka_districts.geojson", driver="GeoJSON")

print("All districts merged successfully")
