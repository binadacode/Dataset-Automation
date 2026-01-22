import ee
import calendar

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

GRID_SPACING = 200
ANOMALY_SPACING = 100
NDVI_THRESHOLD = 0.25

# =====================================================
# LOAD ROI
# =====================================================
roi = ee.FeatureCollection(ROI_ASSET)
print('Total paddy polygons:', roi.size().getInfo())

# =====================================================
# BASE GRID
# =====================================================
base_grid = (
    ee.Image.pixelLonLat()
    .sample(
        region=roi.geometry(),
        scale=GRID_SPACING,
        geometries=True
    )
)
print('Base grid points:', base_grid.size().getInfo())

# =====================================================
# SCL MASK
# =====================================================
def maskSCL(img):
    scl = img.select('SCL')
    mask = (
        scl.neq(3)
           .And(scl.neq(8))
           .And(scl.neq(9))
           .And(scl.neq(10))
           .And(scl.neq(11))
    )
    return img.updateMask(mask)

# =====================================================
# HYBRID POINTS (GRID + ANOMALY)
# =====================================================
def build_sampling_points(img):
    ndvi = img.normalizedDifference(['B8', 'B4'])
    anomaly_mask = ndvi.lt(NDVI_THRESHOLD).selfMask()

    anomaly_points = anomaly_mask.sample(
        region=roi.geometry(),
        scale=ANOMALY_SPACING,
        geometries=True
    )

    return base_grid.merge(anomaly_points)

# =====================================================
# EXPORT FUNCTION — EXACT COLUMN NAMES
# =====================================================
def export_image(img, year, month, week_idx):

    img = ee.Image(img)

    image_id = img.get('system:index')
    date = ee.Date(img.get('system:time_start'))
    date_str = date.format('YYYY-MM-dd')
    cloud_pct = img.get('CLOUDY_PIXEL_PERCENTAGE')

    coords = ee.Image.pixelLonLat().rename(['longitude', 'latitude'])

    final_image = (
        img.select([
            'B1','B11','B12','B2','B3','B4',
            'B5','B6','B7','B8','B8A','B9','SCL'
        ])
        .addBands(coords)
        .set({
            'system:index': image_id,
            'CloudPercent': cloud_pct,
            'Date': date_str,
            'Satellite': 'Sentinel-2'
        })
    )

    sample_points = build_sampling_points(img)

    table = (
        final_image
        .sampleRegions(
            collection=sample_points,
            scale=10,
            geometries=True
        )
        .map(lambda f: f.set({
            'system:index': image_id,
            'CloudPercent': cloud_pct,
            'Date': date_str,
            'Satellite': 'Sentinel-2'
        }))
    )

    description = (
        f'{DISTRICT_NAME}_{year}_'
        f'{month:02d}_W{week_idx}_'
        f'{date_str.getInfo()}_HYBRID_S2'
    )

    ee.batch.Export.table.toDrive(
        collection=table,
        description=description,
        folder=str(year),
        fileFormat='CSV'
    ).start()

    print(f'🚀 Submitted: {description}')

# =====================================================
# MAIN LOOP — STRICT CALENDAR WEEKS (MEMORY SAFE)
# =====================================================
for year in YEARS:
    print(f'\n==============================')
    print(f'📅 PROCESSING YEAR {year}')
    print(f'==============================')

    base_images = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(roi)
        .filterDate(f'{year}-01-01', f'{year}-12-31')
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))
        .map(maskSCL)
    )

    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]

        week_ranges = [
            (1, 7),
            (8, 14),
            (15, 21),
            (22, last_day)
        ]

        print(f'\n📆 {year}-{month:02d}')

        for w_idx, (start_day, end_day) in enumerate(week_ranges, start=1):

            w_start = ee.Date.fromYMD(year, month, start_day)

            if end_day == last_day:
                w_end = ee.Date.fromYMD(year, month, 1).advance(1, 'month')
            else:
                w_end = ee.Date.fromYMD(year, month, end_day + 1)

            weekly = (
                base_images
                .filterDate(w_start, w_end)
                .sort('CLOUDY_PIXEL_PERCENTAGE')
            )

            # ✅ MEMORY-SAFE EXISTENCE CHECK
            try:
                img = ee.Image(weekly.first())
                img.get('system:time_start').getInfo()
            except Exception:
                print(f'  → Week {w_idx}: no valid image')
                continue

            print(f'  → Week {w_idx}: exporting')
            export_image(img, year, month, w_idx)

print('\n✅ ALL STRICT-WEEK EXPORTS SUBMITTED')
