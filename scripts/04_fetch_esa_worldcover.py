"""
Fetch ESA WorldCover 2021 (v200) land cover for the project AOI.

Uses GDAL /vsicurl/ streaming so only the pixels covering the AOI are
transferred — no 400 MB full tiles saved locally.

Each 3°×3° clip is saved immediately to data/02_interim/<project>/esa/.
If the script is interrupted, already-downloaded clips are preserved and
reused on the next run. The final merge only re-runs when new clips appear.

Outputs:
  data/03_processed/<project>/worldcover.tif
    Single-band Byte, ESRI:102012, all ESA classes preserved.
    Styling (which classes are shown) is handled in apply_styles.py.

Key classes used by this map:
  10 = Tree cover      40 = Cropland
  50 = Built-up        90 = Herbaceous wetland
  95 = Mangroves

Add the resulting file as a layer named 'worldcover' in your QGIS project,
placed between the ocean layer and the hillshade layer.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")

BASE_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com"
    "/v200/2021/map"
)

REPROJECT_RES_M = 500  # output pixel size in metres for the reprojected raster


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_gdal():
    if shutil.which("gdalwarp"):
        return
    candidates = []
    env = os.environ.get("GDAL_BIN")
    if env:
        candidates.append(Path(env))
    candidates += [
        Path(r"C:\Program Files\QGIS 3.28.3\bin"),
        Path(r"C:\Program Files\QGIS 3.34.0\bin"),
        Path(r"C:\Program Files\QGIS 3.38.0\bin"),
        Path(r"C:\OSGeo4W\bin"),
    ]
    for parent in [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]:
        if parent.exists():
            for d in parent.glob("QGIS*/bin"):
                candidates.append(d)
    for c in candidates:
        if (c / "gdalwarp.exe").exists() or (c / "gdalwarp").exists():
            os.environ["PATH"] = str(c) + os.pathsep + os.environ.get("PATH", "")
            print(f"  [gdal] using {c}")
            return


def run(cmd):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, text=True, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {cmd[0]}")


def tile_names(minx, miny, maxx, maxy):
    """Return list of (tile_name, sw_lat, sw_lon) for ESA WorldCover tiles covering bbox."""
    tiles = []
    for lat in range(int(miny // 3) * 3, int(maxy // 3) * 3 + 3, 3):
        for lon in range(int(minx // 3) * 3, int(maxx // 3) * 3 + 3, 3):
            lat_s = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            lon_s = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            tiles.append((f"{lat_s}{lon_s}", lat, lon))
    return tiles


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch ESA WorldCover for a project AOI.")
    parser.add_argument("--project", default="china",
                        help="Project name — subfolder of config/ (default: china)")
    args = parser.parse_args()

    aoi_path = PROJECT_ROOT / "config" / args.project / "aoi.geojson"
    interim  = PROJECT_ROOT / "data" / "02_interim" / args.project / "esa"
    out_file = PROJECT_ROOT / "data" / "03_processed" / args.project / "worldcover.tif"
    interim.mkdir(parents=True, exist_ok=True)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    ensure_gdal()
    if not shutil.which("gdalwarp"):
        raise SystemExit("gdalwarp not found. Install QGIS/OSGeo4W or set GDAL_BIN.")

    gdf = gpd.read_file(aoi_path).to_crs("EPSG:4326")
    minx, miny, maxx, maxy = gdf.total_bounds
    all_tiles = tile_names(minx, miny, maxx, maxy)

    print(f"Project: {args.project}")
    print(f"AOI: {minx:.1f} {miny:.1f} {maxx:.1f} {maxy:.1f}  |  {len(all_tiles)} ESA tiles\n")

    new_clips = 0
    for i, (tile, lat, lon) in enumerate(all_tiles, 1):
        te_west  = max(lon,     minx)
        te_south = max(lat,     miny)
        te_east  = min(lon + 3, maxx)
        te_north = min(lat + 3, maxy)
        if te_east <= te_west or te_north <= te_south:
            continue

        out = interim / f"clip_{tile}.tif"
        if out.exists():
            print(f"  [{i:>3}/{len(all_tiles)}] {tile}  cached")
            continue

        url = f"{BASE_URL}/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        print(f"  [{i:>3}/{len(all_tiles)}] {tile}  downloading...", end=" ", flush=True)
        r = subprocess.run(
            [
                "gdalwarp",
                "-te", str(te_west), str(te_south), str(te_east), str(te_north),
                "-te_srs", "EPSG:4326",
                "-of", "GTiff",
                "-co", "COMPRESS=DEFLATE",
                "-co", "TILED=YES",
                f"/vsicurl/{url}", str(out),
            ],
            text=True, stderr=subprocess.PIPE,
        )
        if r.returncode != 0:
            if "404" in r.stderr or "Failed to open" in r.stderr:
                print("not in dataset (ocean/missing)")
                out.unlink(missing_ok=True)
            else:
                print("FAILED", file=sys.stderr)
                print(r.stderr, file=sys.stderr)
                raise SystemExit(f"gdalwarp failed for {tile}")
            continue

        new_clips += 1
        print(f"done ({out.stat().st_size / (1 << 20):.0f} MB)")

    # Collect all available clips — including those from previous interrupted runs
    clipped = sorted(interim.glob("clip_*.tif"))
    if not clipped:
        raise SystemExit("No clips available — check AOI / network.")

    if out_file.exists() and new_clips == 0:
        print(f"\nAll tiles cached and {out_file.name} is up to date — nothing to do.")
        return

    print(f"\nMerging {len(clipped)} clip(s) + reprojecting to ESRI:102012 @ {REPROJECT_RES_M}m...")
    run([
        "gdalwarp",
        "--config", "GDAL_CACHEMAX", "1024",
        "-overwrite",
        "-t_srs", "ESRI:102012",
        "-tr", str(REPROJECT_RES_M), str(REPROJECT_RES_M),
        "-r", "near",
        "-ot", "Byte",
        "-multi",
        "-wm", "512",
        "-of", "GTiff",
        "-co", "COMPRESS=DEFLATE",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=IF_SAFER",
    ] + [str(p) for p in clipped] + [str(out_file)])

    print("Building overviews...")
    run([
        "gdaladdo",
        "--config", "COMPRESS_OVERVIEW", "DEFLATE",
        "-r", "nearest",
        str(out_file),
        "2", "4", "8", "16", "32", "64", "128", "256", "512", "1024",
    ])

    print(f"\nWorldCover ready: {out_file}")
    print("Load into QGIS five times, naming the layers:")
    print("  wc_trees  wc_cropland  wc_builtup  wc_wetland  wc_mangroves")
    print("Then run apply_styles.py to apply per-class paletted renderers.")


if __name__ == "__main__":
    main()
