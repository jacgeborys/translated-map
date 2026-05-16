"""
Download Natural Earth vector layers needed by this project.

Outputs:
  data/01_raw/ocean/ne_10m_ocean.gpkg         → layer 'ocean'    (below hillshade)
  data/01_raw/urban/ne_10m_urban_areas.gpkg   → layer 'urban_areas' (above hillshade)
"""

import io
import shutil
import zipfile
from pathlib import Path

import requests
import geopandas as gpd

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")

LAYERS = [
    {
        "url": "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_ocean.zip",
        "out": PROJECT_ROOT / "data" / "01_raw" / "ocean" / "ne_10m_ocean.gpkg",
        "hint": "layer 'ocean', place below hillshade",
    },
    {
        "url": "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_urban_areas.zip",
        "out": PROJECT_ROOT / "data" / "01_raw" / "urban" / "ne_10m_urban_areas.gpkg",
        "hint": "layer 'urban_areas', place above hillshade",
    },
]


def fetch_layer(url, out_path, hint):
    if out_path.exists():
        print(f"✓ already exists: {out_path.name}")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"↓ {out_path.name} ...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    tmp = out_path.parent / "_tmp"
    tmp.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        zf.extractall(tmp)
        shp = next(p for p in tmp.rglob("*.shp"))

    gpd.read_file(shp).to_file(out_path, driver="GPKG")
    shutil.rmtree(tmp)
    print(f"  ✓ saved → {out_path}")
    print(f"  → Add as {hint}")


def main():
    for layer in LAYERS:
        fetch_layer(layer["url"], layer["out"], layer["hint"])


if __name__ == "__main__":
    main()
