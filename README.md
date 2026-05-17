# china-map

NatGeo-style reference map for a July southern China trip. Hillshade substrate
+ restrained typography + curated POIs, produced from a config-driven Python
pipeline with QGIS handling cartography.

## Scope

- **Trip area (planned):** southern China, broadly Guangxi / Guizhou / Yunnan.
- **Current AOI:** all of China (large-scale). Fetched OSM data covers the full country. `config/aoi.geojson` holds the AOI polygon.
- **Target output:** printable PNG (and/or PDF), regenerable from one command.

## CRS

- **Project CRS:** `ESRI:102012` — Asia Lambert Conformal Conic.
- **OSM source CRS:** `EPSG:4326`.

## Pipeline

```
config/aoi.geojson ──┐
                     ├─> 01_fetch_dem.py        ──> data/01_raw/dem/*.tif
                     │                              data/02_interim/dem.tif  (ESRI:102012, clipped)
                     │   data/02_interim/dem.tif
                     └─> 02_build_relief.py     ──> data/03_processed/hillshade.tif

config/aoi.geojson ──┐
config/osm_layers.yaml┤─> 05_fetch_osm.py       ──> data/01_raw/osm/*.gpkg

                       03_fetch_natural_earth.py ──> data/01_raw/ocean/ne_10m_ocean.gpkg
                                                      data/01_raw/ne/ne_10m_admin_0_countries.gpkg

                       04_fetch_esa_worldcover.py──> data/03_processed/worldcover.tif

data/01_raw/osm/places.gpkg
  ──> 06_translate_places.py (Claude API) ──> data/03_processed/places_translated.gpkg
        adds: name_eng (literal English meaning), name_pol (Polish)
        run for cities with population > 500k

data/03_processed/places_translated.gpkg + OSM layers
  ──> 07_render_matplotlib.py ──> output/china_map_mpl.png
        standalone render: no QGIS required
```

## Label design (07_render_matplotlib.py)

Two-line city labels, English only — no Chinese characters:
- **Top line** (0.75× size, muted grey `#555555`): romanised name from `name:en` or `name:pinyin`
- **Bottom line** (full size, dark `#2a2a2a`, bold for ≥5M pop): literal English translation from `name_eng` (e.g. "Osmanthus Forest" for Guilin)

Font scale: 5 pt (1–3M pop) → 6 pt (3–5M) → 7 pt (5–10M) → 8 pt (10M+).

Only cities shown that have **both** `name_eng` (Claude translation) **and** `name:en` or `name:pinyin` (romanisation), with population ≥ 1M (or in allowlist: Hong Kong, Taipei).

**Label placement — current state and open problem:**

Labels are placed in two stages:

1. **Spatial thinning** (50 km radius): when two cities are closer than 50 km, the smaller one is dropped. Reduces ~180 candidates to ~141.
2. **Cluster detection** (union-find, 150 km threshold): cities within 150 km form clusters (e.g. Pearl River Delta, Yangtze Delta). Each label gets a preferred direction — outward from its cluster centroid. Singletons fall back to the sparsest 45° density sector.
3. **Physics**: labels are placed at `dot + clear_direction × INIT_OFFSET`, bboxes measured from the real renderer post-draw (important: `inv = ax.transData.inverted()` must be captured *after* `fig.canvas.draw()` due to `set_aspect("equal")` finalising the transform). Then a centrifugal attractor pulls cluster labels radially outward while pairwise repulsion resolves overlaps.

**Known problem:** 141 two-line labels at China scale is too many for fully non-overlapping placement. The centrifugal approach gives good results for well-separated clusters (PRD goes south into the South China Sea) but dense central-China cities (Wuhan / Changsha / Nanchang belt) still overlap. The force-directed pairwise repulsion tends to push text boxes vertically (because text boxes are wide and short, so vertical is always the minimum-penetration axis), giving predominantly vertical leader lines regardless of the intended radial direction. This is the unsolved problem to continue in the next session.

**Approaches tried and abandoned:**
- `adjustText` library: too weak for this density
- Greedy 4-quadrant placement with invisible texts: zero bboxes bug (must draw canvas first)
- Force-directed repulsion without directional bias: all leaders end up vertical
- Angular sweep (polar coordinates, 24 angles × 8 rounds): converges to one direction (north or east for everyone) because short text-box height makes N/S directions cheapest
- Angular sweep with high angle cost (80k m/radian): forces preferred direction too strongly, all labels pile up in same region
- Centrifugal attractor (current): better direction diversity for clusters, still has overlap in dense areas

## Palette

| Element | Colour |
|---|---|
| Background | `#f5f0e8` (NatGeo cream) |
| Ocean | `#a9c9d6` |
| Country border | `#a04060` |
| Motorway | `#ddb89a` |
| Trunk road | `#e8dbbf` |
| HSR rail | `#c0bfbc` |
| Standard rail | `#ceccc8` |
| Label (main) | `#2a2a2a` |
| Label (translit) | `#555555` |
| City dot | `#222222` |

Hillshade: ArcGIS World Hillshade tile service, alpha 0.25.

## How to run

```bash
# from D:\QGIS\natgeo_map\china-map
make all       # full pipeline: dem → relief → natearth → worldcover → osm → translate → render

# or individually:
python scripts/01_fetch_dem.py
python scripts/02_build_relief.py
python scripts/03_fetch_natural_earth.py
python scripts/04_fetch_esa_worldcover.py
python scripts/05_fetch_osm.py
python scripts/06_translate_places.py   # requires ANTHROPIC_API_KEY
python scripts/07_render_matplotlib.py
python scripts/07_render_matplotlib.py --dpi 100 --out output/preview.png
```

QGIS-specific (optional):
```bash
python-qgis.bat scripts/apply_styles.py   # apply styles to .qgz
python-qgis.bat scripts/render.py         # headless QGIS export
```

## Config

| File | Purpose |
|---|---|
| `config/aoi.geojson` | AOI polygon (CRS84). Everything reads from here. |
| `config/osm_layers.yaml` | OSM layer definitions (queries + kept columns) |
| `config/pois.csv` | Curated POIs (manual) |
| `config/name_overrides.csv` | Chinese→English name overrides (manual) |
| `config/style_params.yaml` | Cartographic parameters (placeholder) |

## Data sources

- **DEM:** Copernicus GLO-30 (30 m), AWS open bucket.
- **OSM:** Overpass API (`overpass.kumi.systems`).
- **Natural Earth:** 10m ocean polygons + country boundaries.
- **ESA WorldCover:** land cover raster.
- **Translations:** Claude API (`claude-sonnet-4-6`), run via `06_translate_places.py`.

## Project structure

```
china-map/
├── README.md
├── Makefile
├── requirements.txt
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
│   ├── 06_translate_places.py       ← Claude API translation (name_eng, name_pol)
│   ├── 07_render_matplotlib.py      ← main output render (no QGIS needed)
│   ├── apply_styles.py              ← QGIS styling tool
│   └── render.py                    ← QGIS headless export
├── qgis/
└── output/             (gitignored; *.png excluded — renders exceed 100 MB)
```

## .gitignore notes

- `data/01_raw/`, `data/02_interim/`, `data/03_processed/`, `output/` are gitignored.
- `*.png` is gitignored — renders are 115+ MB and exceed GitHub's 100 MB file limit.

## Status

- [x] Scaffold + Makefile
- [x] DEM fetch + warp (Copernicus GLO-30)
- [x] Multidirectional hillshade
- [x] OSM fetch (config-driven, tile-cached)
- [x] Natural Earth ocean + country borders
- [x] ESA WorldCover land cover
- [x] Claude translation pipeline (`06_translate_places.py`) — run for cities >500k pop
- [x] Standalone matplotlib render (`07_render_matplotlib.py`)
  - [x] Hillshade basemap via ArcGIS tile service (contextily)
  - [x] Two-line English labels (transliteration + literal translation)
  - [x] Allowlist for Hong Kong, Taipei
  - [x] Cluster-aware centrifugal label placement (radial leaders from cluster centroid)
  - [x] Leader lines: dot → nearest bbox edge, skipped if < 10 km, linewidth 0.75
  - [ ] **Label overlap in dense areas not fully solved** — see "Known problem" above
  - [ ] Road density tuning (secondary roads currently too noisy at China scale)
  - [ ] Province labels
  - [ ] River labels
- [ ] QGIS project styling (done interactively, not yet scripted)
- [ ] Headless QGIS render
