"""
Rebuild data/01_raw/osm/places.gpkg for the full AOI (now 97-135E, 18-55N).
Reuses the tile cache from 05_fetch_osm.py — cached tiles are skipped,
only missing tiles are fetched from Overpass.

Run this before 08_translate_china_1m.py.
"""

import importlib.util
import yaml
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load 05_fetch_osm as a module (numbered filename requires importlib)
_spec = importlib.util.spec_from_file_location(
    "fetch_osm", PROJECT_ROOT / "scripts" / "05_fetch_osm.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

AOI_PATH    = PROJECT_ROOT / "config" / "aoi.geojson"
LAYERS_YAML = PROJECT_ROOT / "config" / "osm_layers.yaml"
OUT_FILE    = PROJECT_ROOT / "data" / "01_raw" / "osm" / "places.gpkg"


def main():
    aoi_bbox = _mod.load_aoi_bbox(AOI_PATH)
    print(f"AOI (S,W,N,E): {_mod.bbox_to_overpass(aoi_bbox)}\n")

    with open(LAYERS_YAML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    spec = cfg["layers"]["places"]

    if OUT_FILE.exists():
        OUT_FILE.unlink()
        print(f"Deleted existing {OUT_FILE.name} — will rebuild from cache + Overpass\n")

    gdf = _mod.fetch_layer("places", spec, aoi_bbox)

    if gdf is None or gdf.empty:
        print("No data returned.")
        return

    if "osm_id" in gdf.columns:
        before = len(gdf)
        gdf = gdf.drop_duplicates(subset=["osm_id"], keep="first")
        if before != len(gdf):
            print(f"Deduped {before} -> {len(gdf)}")

    if "population" in gdf.columns:
        gdf["population"] = pd.to_numeric(gdf["population"], errors="coerce").astype("Int64")

    gdf = gdf[gdf.geometry.notnull()]
    gdf.to_file(OUT_FILE, driver="GPKG")
    print(f"\nSaved {len(gdf)} places -> {OUT_FILE.name}")

    cities_1m = gdf[gdf["population"] >= 1_000_000]
    print(f"Cities >= 1M population: {len(cities_1m)}")
    if not cities_1m.empty:
        top = cities_1m.sort_values("population", ascending=False).head(10)
        print(top[["name", "population"]].to_string(index=False))


if __name__ == "__main__":
    main()
