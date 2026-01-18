import ee
import time

# =====================================================
# AUTH & INIT
# =====================================================
ee.Authenticate()
ee.Initialize(project='ricevision')

# =====================================================
# CONFIG
# =====================================================
YEARS = [2025]

DISTRICT_NAME = 'Ampara'
ROI_ASSET = 'projects/ricevision/assets/Ampara_paddy2'

N_POINTS = 4000          # fixed points → same lat/lon for all images
SEED = 42

IMAGES_PER_MONTH = 4     # 👈 key scalability control
MAX_WAIT_MINUTES = 30
POLL_INTERVAL = 30
WIFI_RETRY_WAIT = 60

# =====================================================
# LOAD ROI
# =====================================================
roi = ee.FeatureCollection(ROI_ASSET)
print('Total paddy polygons:', roi.size().getInfo())

# =====================================================
# FIXED SAMPLE POINTS (ONCE)
# =====================================================
points = ee.FeatureCollection.randomPoints(
    region=roi.geometry(),
    points=N_POINTS,
    seed=SEED
)

print('Sample points generated:', points.size().getInfo())

# =====================================================
# SCL MASK (EXACTLY AS REQUESTED)
# =====================================================
def maskSCL(img):
    scl = img.select('SCL')
    mask = (
        scl.neq(3)    # cloud shadow
           .And(scl.neq(8))    # medium cloud
           .And(scl.neq(9))    # high cloud
           .And(scl.neq(10))   # cirrus
           .And(scl.neq(11))   # snow/ice
    )
    return img.updateMask(mask)

# =====================================================
# TASK WAIT (30 MIN + WIFI GUARD)
# =====================================================
def wait_for_task(task):
    start = time.time()

    while True:
        try:
            status = task.status()
            state = status['state']
        except Exception:
            print('⚠️ Network issue — retrying in 60s')
            time.sleep(WIFI_RETRY_WAIT)
            continue

        if state == 'COMPLETED':
            print('✔ Task completed')
            return

        if state == 'FAILED':
            print('❌ Task failed')
            return

        elapsed = (time.time() - start) / 60
        if elapsed >= MAX_WAIT_MINUTES:
            print('⚠️ 30-minute timeout — moving on')
            return

        print(f'⏳ {state} — waiting {POLL_INTERVAL}s')
        time.sleep(POLL_INTERVAL)

# =====================================================
# EXPORT FUNCTION
# =====================================================
def export_image(img, year, month):

    img = ee.Image(img)

    date = ee.Date(img.get('system:time_start'))
    date_str = date.format('YYYY-MM-dd').getInfo()
    image_id = img.get('system:index').getInfo()
    cloud_pct = img.get('CLOUDY_PIXEL_PERCENTAGE')

    coords = ee.Image.pixelLonLat().rename(['longitude', 'latitude'])

    final_image = (
        img.select([
            'B1','B11','B12','B2','B3','B4',
            'B5','B6','B7','B8','B8A','B9','SCL'
        ])
        .addBands(coords)
        .set({
            'Date': date_str,
            'CloudyPixelPercent': cloud_pct,
            'Satellite': 'Sentinel-2',
            'District': DISTRICT_NAME
        })
    )

    table = (
        final_image.sampleRegions(
            collection=points,
            scale=10,
            geometries=True
        )
        .map(lambda f: f.set({
            'Date': date_str,
            'CloudyPixelPercent': cloud_pct,
            'Satellite': 'Sentinel-2',
            'District': DISTRICT_NAME
        }))
    )

    description = f'{DISTRICT_NAME}_{year}_{month:02d}_{date_str}_PTS_S2'

    task = ee.batch.Export.table.toDrive(
        collection=table,
        description=description,
        folder=str(year),
        fileFormat='CSV'
    )

    task.start()
    print(f'🚀 Started export: {description}')
    return task

# =====================================================
# MAIN LOOP — YEAR → MONTH → 4 IMAGES
# =====================================================
for year in YEARS:
    print(f'\n==============================')
    print(f'📅 PROCESSING YEAR {year}')
    print(f'==============================')

    for month in range(1, 13):
        start_date = f'{year}-{month:02d}-01'
        end_date   = f'{year}-{month:02d}-28'

        print(f'\n📆 {year}-{month:02d}')

        images = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(roi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))
            .map(maskSCL)
            .sort('CLOUDY_PIXEL_PERCENTAGE')
            .limit(IMAGES_PER_MONTH)   # 👈 critical
        )

        img_list = images.toList(IMAGES_PER_MONTH)

        img_count = images.size().getInfo()   # small (≤4), safe
        print(f'  Found {img_count} valid images')

        for i in range(img_count):
            img = img_list.get(i)
            print(f'  → Image {i+1}/{img_count}')
            task = export_image(img, year, month)
            wait_for_task(task)


print('\n✅ ALL YEARS COMPLETED SAFELY')
