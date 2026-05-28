"""
Quick diagnostic: generates a GeoPackage showing the expected ESA WorldCover
tile grid for the project AOI, with each tile marked as cached or missing.

Output: data/03_processed/<project>/esa_tile_status.gpkg
Load this in QGIS and style by the 'status' column to spot gaps.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
from shapely.geometry import box

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="china")
    args = parser.parse_args()

    aoi_path = PROJECT_ROOT / "config" / args.project / "aoi.geojson"
    interim  = PROJECT_ROOT / "data" / "02_interim" / args.project / "esa"
    out_gpkg = PROJECT_ROOT / "data" / "03_processed" / args.project / "esa_tile_status.gpkg"
    out_gpkg.parent.mkdir(parents=True, exist_ok=True)

    gdf_aoi = gpd.read_file(aoi_path).to_crs("EPSG:4326")
    minx, miny, maxx, maxy = gdf_aoi.total_bounds

    cached = {p.stem.replace("clip_", "") for p in interim.glob("clip_*.tif")}

    rows = []
    for lat in range(int(miny // 3) * 3, int(maxy // 3) * 3 + 3, 3):
        for lon in range(int(minx // 3) * 3, int(maxx // 3) * 3 + 3, 3):
            te_west  = max(lon,     minx)
            te_south = max(lat,     miny)
            te_east  = min(lon + 3, maxx)
            te_north = min(lat + 3, maxy)
            if te_east <= te_west or te_north <= te_south:
                continue
            lat_s = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            lon_s = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            name = f"{lat_s}{lon_s}"
            rows.append({
                "tile":     name,
                "status":   "cached" if name in cached else "missing",
                "geometry": box(lon, lat, lon + 3, lat + 3),
            })

    result = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    result.to_file(out_gpkg, driver="GPKG")

    total   = len(result)
    missing = (result["status"] == "missing").sum()
    print(f"Total expected tiles: {total}")
    print(f"Cached:  {total - missing}")
    print(f"Missing: {missing}")
    if missing:
        print("\nMissing tiles:")
        for t in result.loc[result["status"] == "missing", "tile"]:
            print(f"  {t}")
    print(f"\nSaved -> {out_gpkg}")


if __name__ == "__main__":
    main()
