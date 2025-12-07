import ee

# Initialize Earth Engine with your registered project
ee.Initialize(project="ricevision")

# Simple test
print(ee.Number(1).getInfo())  # Should print 1
