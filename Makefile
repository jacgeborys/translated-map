# china-map pipeline
# Requires OSGeo4W / QGIS shell on PATH (gdalwarp, gdaldem).

PY := python

.PHONY: all dem relief osm worldcover clean-mosaics clean-all

all: dem relief osm worldcover

dem:
	$(PY) scripts/fetch_dem.py

relief: dem
	$(PY) scripts/build_relief.py

osm:
	$(PY) scripts/fetch_osm.py

worldcover:
	$(PY) scripts/fetch_esa_worldcover.py

# Delete per-AOI outputs only — raw tile caches (DEM, OSM _tiles, NE) are kept.
# Run this before re-running `make all` after changing config/aoi.geojson.
clean-mosaics:
	@echo "Removing AOI-dependent outputs (tile caches preserved)..."
	rm -f data/02_interim/dem.tif
	rm -f data/03_processed/hillshade.tif
	rm -f data/01_raw/osm/*.gpkg
	rm -f data/02_interim/esa/clip_*.tif
	rm -f data/02_interim/esa/merged.vrt data/02_interim/esa/merged.tif
	rm -f data/03_processed/worldcover.tif
	@echo "Done. Run: make all"

# Full wipe including raw tile caches — forces complete re-download.
clean-all: clean-mosaics
	@echo "Removing all raw tile caches..."
	rm -rf data/01_raw/dem/
	rm -rf data/01_raw/osm/_tiles/
	rm -rf data/02_interim/esa/
	@echo "Done. Run: make all"
