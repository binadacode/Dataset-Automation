import ee

# Initialize Earth Engine
ee.Initialize()

# Load your shapefile collection
shapefile = ee.FeatureCollection("users/binada2005/sri_lanka_ds")

# Field that contains GN division names or codes
GN_FIELD = "ADM2_NAME"

# Get all GN names
gn_list = shapefile.aggregate_array(GN_FIELD).getInfo()
total_gns = len(gn_list)

print(f"Total GN divisions: {total_gns}")
print(f"First 5 GN names: {gn_list[:5]}")

# Loop over all GN divisions
for i, gn_name in enumerate(gn_list, start=1):
    # Filter the collection to this GN
    gn_fc = shapefile.filter(ee.Filter.eq(GN_FIELD, gn_name))
    
    # You can fetch other properties as needed
    features = gn_fc.limit(1).getInfo().get('features', [])
    
    if features:
        props = features[0]['properties']
        print(f"{i}. GN: {gn_name} | ADM1: {props.get('ADM1_NAME')} | Status: {props.get('STATUS')} | Area: {props.get('Shape_Area')}")
    else:
        print(f"{i}. GN: {gn_name} | No features found")
