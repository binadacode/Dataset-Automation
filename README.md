# Dataset-Automation

**Satellite-driven paddy field dataset pipeline for Sri Lanka — built on Google Earth Engine.**

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Google Earth Engine](https://img.shields.io/badge/Google%20Earth%20Engine-API-34a853?logo=google&logoColor=white)
![Sentinel-2](https://img.shields.io/badge/Sentinel--2-ESA%20Copernicus-00529B)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Overview

This pipeline automates the construction of labelled, georeferenced rice paddy datasets across Sri Lankan districts using ESA's WorldCereal model outputs and Sentinel-2 satellite imagery — all via the Google Earth Engine Python API.

It is the data backend for the [RiceVision](https://github.com/binadacode) project, which builds AI-powered crop monitoring tools for Sri Lanka's agricultural sector.

---

## The Problem

Training a reliable crop detection or yield-monitoring model for Sri Lanka requires:

- Spatially accurate paddy field boundaries at district scale
- Time-series spectral data tied to those boundaries (Sentinel-2 bands)
- Clean, export-ready formats (CSV, SHP, GeoJSON) compatible with ML pipelines

Manually sourcing and preparing this data is impractical. This pipeline removes that bottleneck entirely.

---

## What It Does

- **Paddy field detection** — Uses ESA WorldCereal (class `100` = paddy) on top of district GeoJSON boundaries to extract and vectorise rice field polygons at 10 m resolution
- **Field enrichment** — Computes area (ha) and mean crop confidence per polygon; filters out sub-threshold noise
- **Sentinel-2 sampling** — Exports weekly spectral data (13 bands: B1–B12, SCL) sampled from paddy ROIs using a hybrid grid + anomaly-point strategy
- **Boundary export** — Downloads Sri Lanka Divisional Secretariat (DS) boundaries from FAO GAUL Level-2, exports them as GeoJSON and Shapefile
- **GeoJSON merging** — Combines per-district shapefiles into a single merged national GeoJSON for upload
- **Folium visualisation** — Renders exported DS boundaries as an interactive HTML map

---

## Architecture

```
ESA WorldCereal / Copernicus S2
         │
         ▼
  Google Earth Engine API
         │
  ┌──────┴──────────────────────┐
  │                             │
  ▼                             ▼
Paddy Detection              Sentinel-2 Sampling
(raster → vector,            (13-band, weekly,
 area + confidence)           grid + anomaly points)
  │                             │
  ▼                             ▼
 SHP export               CSV export per week
  └──────────────┬──────────────┘
                 ▼
         Google Drive / GEE Assets
                 │
                 ▼
        Folium Map (HTML preview)
```

> All exports are batched via `ee.batch.Export` and run asynchronously on GEE's servers. No local compute required post-submission.

---

## Tech Stack

| Layer | Tools |
|---|---|
| Satellite data | ESA WorldCereal, Copernicus Sentinel-2 SR Harmonized |
| Compute | Google Earth Engine Python API (`earthengine-api`) |
| Vector processing | GeoPandas, Shapely |
| Visualisation | Folium |
| Data formats | GeoJSON, SHP, CSV |
| Auth | GEE OAuth2 service account |

---

## Setup

**Prerequisites:** Python 3.11+, a GEE project, OAuth credentials JSON.

```bash
# Clone the repo
git clone https://github.com/binadacode/Dataset-Automation.git
cd Dataset-Automation

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Authenticate Earth Engine (first run only)
earthengine authenticate
```

Set your OAuth credentials path in `ee_auth.py` before running any script.

---

## Usage

### 1. Export paddy field vectors (shapefiles) per district

```bash
python code/map_fields.py
```

Iterates over district GeoJSONs, detects paddy polygons using WorldCereal, enriches them with area and confidence, and queues export tasks to Google Drive as shapefiles.

### 2. Export weekly Sentinel-2 spectral data (CSV)

```bash
python code/rice_export.py
```

Samples all 13 Sentinel-2 bands across weekly windows for a configured district/year. Uses a hybrid sampling strategy: regular grid (200 m) + anomaly-targeted points (100 m, NDVI < 0.25). Exports one CSV per valid weekly image.

### 3. Map Sri Lanka DS boundary divisions

```bash
python code/map_ds.py
```

Downloads all DS divisions from FAO GAUL Level-2, exports the full GeoJSON and individual features, generates a Shapefile, and opens an interactive Folium map.

### 4. Merge district shapefiles into one GeoJSON

```bash
python code/merge_geojsons.py
```

Reads all shapefiles from `district_shapefiles/`, merges them, reprojects to EPSG:4326, and writes a single `sri_lanka_districts.geojson`.

---

## Configuration

Key parameters in `rice_export.py`:

| Variable | Default | Description |
|---|---|---|
| `DISTRICT_NAME` | `'Ampara'` | Target district |
| `ROI_ASSET` | GEE asset path | Paddy polygon FeatureCollection |
| `YEARS` | `[2025]` | Years to process |
| `GRID_SPACING` | `200` (m) | Base sampling grid resolution |
| `ANOMALY_SPACING` | `100` (m) | Dense sampling in low-NDVI zones |
| `NDVI_THRESHOLD` | `0.25` | Anomaly detection cutoff |

---

## Output Structure

```
Google Drive/
├── RicePipeline/
│   └── {district}_paddy.shp        # Paddy polygons with area + confidence
└── {year}/
    └── {district}_{year}_{month}_W{n}_{date}_HYBRID_S2.csv   # Spectral samples
```

Each CSV row = one sampling point with columns: `B1–B12`, `SCL`, `longitude`, `latitude`, `Date`, `CloudPercent`, `Satellite`.

---

## Future Improvements

- [ ] Add multi-district parallelism (batch across all districts simultaneously)
- [ ] Automated cloud-cover fallback — composite from multiple images per window instead of best single image
- [ ] GEE Asset upload automation for paddy vectors (currently manual)
- [ ] Output validation — schema checks on exported CSVs before downstream use
- [ ] GitHub Actions schedule for annual dataset refresh

---

## Why This Exists

Sri Lanka's rice sector lacks accessible, structured remote sensing datasets at divisional granularity. This pipeline closes that gap by automating the extraction and formatting of satellite data into ML-ready formats — directly informing crop health monitoring, yield estimation, and early warning systems like RiceVision.

---

## Author

**Binada Matara Arachchige**  
CS Undergraduate · University of Westminster  
[GitHub](https://github.com/binadacode)

---

*Part of the RiceVision project — AI-powered rice crop monitoring for Sri Lanka.*
