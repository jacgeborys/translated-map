# china-map

NatGeo-style reference map for a July southern China trip. Hillshade substrate
+ restrained typography + curated POIs, produced from a config-driven Python
pipeline with QGIS handling cartography.

## Scope

- **Trip area (planned):** southern China, broadly Guangxi / Guizhou / Yunnan.
- **Test AOI (this session):** Yangshuo / Guilin karst, `110.2°E – 110.7°E`, `24.6°N – 25.4°N`. See `config/aoi.geojson`.
- **Target output:** printable PNG (and/or PDF), regenerable from one command.

## CRS

- **Project CRS:** `ESRI:102012` — Asia Lambert Conformal Conic. Chosen because
  a single 3° Gauss-Krüger zone can't span the full southern China extent, and
  Lambert Conformal Conic is the standard projection for regional reference
  maps at this latitude. Minor equal-area distortion is acceptable.
- **OSM source CRS:** `EPSG:4326` (no change — Overpass returns lon/lat).
- All rasters are warped to the project CRS before hillshade computation so
  units are meters.

## Pipeline

```
  config/aoi.geojson ──┐
                       ├─> fetch_dem.py   ──> data/01_raw/dem/*.tif
                       │                     data/02_interim/dem.tif        (ESRI:102012, clipped)
                       │
                       │   data/02_interim/dem.tif
                       └─> build_relief.py ──> data/03_processed/hillshade.tif  (multidirectional, single-band)

  config/aoi.geojson ──┐
  config/osm_layers.yaml┤─> fetch_osm.py  ──> data/01_raw/osm/*.gpkg         (per-layer GeoPackages)

  [future] config/name_overrides.csv
       + data/01_raw/osm ──> translate_labels.py ──> data/02_interim/osm/*.gpkg

  [future] qgis/china_map.qgz ──> render.py ──> output/*.png
```

Division of labor (already decided):
- **Python** owns data acquisition, raster math, label prep.
- **QGIS** owns styling + label placement + final layout export.
- Python drives QGIS headlessly via `qgis_process` / PyQGIS for repeatable exports.

## Data sources

- **DEM:** Copernicus GLO-30 (30 m), AWS open bucket, no auth.
  <https://registry.opendata.aws/copernicus-dem/>
- **OSM:** Overpass API (`overpass.kumi.systems`). China coverage is patchy
  for urban detail — the layer list in `config/osm_layers.yaml` is
  intentionally minimal (no residential roads, no buildings).
- **Buildings:** parked. Candidates for later: Microsoft GlobalMLBuildingFootprints, TUM EO4 Buildings of the World.

## How to run

Requires OSGeo4W / QGIS shell on PATH so `gdalwarp` and `gdaldem` resolve.
Python deps: `requests`, `geopandas`, `shapely`, `pandas`, `pyyaml`.

```bash
# from D:\QGIS\natgeo_map\china-map
make dem       # download + clip DEM to ESRI:102012
make relief    # multidirectional hillshade
make osm       # fetch all OSM layers defined in config/osm_layers.yaml
make all       # dem → relief → osm
```

Individual scripts (run in order):

```bash
python scripts/01_fetch_dem.py
python scripts/02_build_relief.py
python scripts/03_fetch_natural_earth.py
python scripts/04_fetch_esa_worldcover.py
python scripts/05_fetch_osm.py
python scripts/06_translate_places.py
python scripts/07_render_matplotlib.py
```

QGIS-specific (optional, no prefix):
```bash
python-qgis.bat scripts/apply_styles.py   # apply styles to .qgz
python-qgis.bat scripts/render.py         # headless QGIS export
```

All outputs are regenerable; delete the target file (or entire `data/01_raw/`)
to force a re-fetch.

## Config-driven decisions

| File                           | What lives here                                  |
|--------------------------------|---------------------------------------------------|
| `config/aoi.geojson`           | AOI polygon (CRS84). Everything reads from here. |
| `config/osm_layers.yaml`       | OSM layer definitions (queries + kept columns)   |
| `config/pois.csv`              | Curated POIs (manual)                            |
| `config/name_overrides.csv`    | Chinese→English name overrides (manual)          |
| `config/style_params.yaml`     | Cartographic parameters (placeholder, TODOs)     |

## Project structure

```
china-map/
├── README.md
├── Makefile
├── config/
├── data/
│   ├── 01_raw/         (gitignored)
│   ├── 02_interim/     (gitignored)
│   └── 03_processed/   (gitignored)
├── scripts/
│   ├── 01_fetch_dem.py
│   ├── 02_build_relief.py
│   ├── 03_fetch_natural_earth.py
│   ├── 04_fetch_esa_worldcover.py
│   ├── 05_fetch_osm.py
│   ├── 06_translate_places.py
│   ├── 07_render_matplotlib.py   ← main output, no QGIS needed
│   ├── apply_styles.py           ← QGIS styling tool
│   ├── render.py                 ← QGIS headless export
│   └── translate_labels.py       (stub)
├── qgis/               (empty — add .qgz later)
└── output/             (gitignored)
```

## Status

- [x] Scaffold
- [x] DEM fetch + warp
- [x] Hillshade
- [x] OSM fetch (config-driven)
- [ ] Label translation waterfall
- [ ] QGIS project + styling (done interactively)
- [ ] Headless render
