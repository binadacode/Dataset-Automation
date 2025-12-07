import ee
import os

# Tell EE where your OAuth JSON is
os.environ['EARTHENGINE_TOKEN_FILE'] = r'D:\iit\2nd yr\sgdp\code\ricevision_oauth.json'

# Authenticate (will use your OAuth credentials)
ee.Authenticate()

# Initialize with your project
ee.Initialize(project="ricevision")

print("✅ Earth Engine authenticated & initialized successfully!")
