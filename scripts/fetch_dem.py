"""
Input:  config/aoi.geojson (CRS84 polygon)
Output: data/01_raw/dem/*.tif, data/02_interim/dem.tif (clipped+warped to ESRI:102012)
Purpose: Download Copernicus GLO-30 DEM tiles intersecting the AOI, mosaic and warp.

Copernicus GLO-30 is distributed as 1°x1° COG tiles on AWS open data bucket:
  https://copernicus-dem-30m.s3.amazonaws.com/
Tile naming: Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/
             Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif
No auth required. Tiles near ocean may be absent — skip 404s silently.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import requests


def ensure_gdal_on_path():
    """Prepend a QGIS/OSGeo4W bin dir to PATH if gdalwarp isn't already there.
    Override with env var GDAL_BIN=<dir>."""
    if shutil.which("gdalwarp"):
        return
    candidates = []
    env_override = os.environ.get("GDAL_BIN")
    if env_override:
        candidates.append(Path(env_override))
    candidates += [
        Path(r"C:\Program Files\QGIS 3.28.3\bin"),
        Path(r"C:\Program Files\QGIS 3.34.0\bin"),
        Path(r"C:\Program Files\QGIS 3.38.0\bin"),
        Path(r"C:\OSGeo4W\bin"),
        Path(r"C:\OSGeo4W64\bin"),
    ]
    # also any "C:\Program Files\QGIS *\bin"
    for parent in [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]:
        if parent.exists():
            for d in parent.glob("QGIS*/bin"):
                candidates.append(d)
    for c in candidates:
        if (c / "gdalwarp.exe").exists() or (c / "gdalwarp").exists():
            os.environ["PATH"] = str(c) + os.pathsep + os.environ.get("PATH", "")
            print(f"  [gdal] using {c}")
            return

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = PROJECT_ROOT / "config" / "aoi.geojson"
RAW_DIR = PROJECT_ROOT / "data" / "01_raw" / "dem"
INTERIM_DIR = PROJECT_ROOT / "data" / "02_interim"
RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

# --- Config ---
# Project CRS: Asia Lambert Conformal Conic (ESRI:102012).
# TODO: confirm target resolution; 30 m matches native GLO-30.
PROJECT_CRS = "ESRI:102012"
TARGET_RES = 300  # meters

BUCKET_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"


def load_aoi_bbox(path: Path):
    """Return (west, south, east, north) in EPSG:4326."""
    with open(path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    feat = gj["features"][0]
    coords = feat["geometry"]["coordinates"][0]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def tiles_for_bbox(west, south, east, north):
    """List 1x1 deg tile (lat, lon) integer origins covering the bbox.
    Tile origin is the SW corner (floor)."""
    lat_start = math.floor(south)
    lat_end = math.floor(north - 1e-9) + 1  # inclusive
    lon_start = math.floor(west)
    lon_end = math.floor(east - 1e-9) + 1
    tiles = []
    for lat in range(lat_start, lat_end):
        for lon in range(lon_start, lon_end):
            tiles.append((lat, lon))
    return tiles


def tile_url(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    lat_s = f"{ns}{abs(lat):02d}_00"
    lon_s = f"{ew}{abs(lon):03d}_00"
    name = f"Copernicus_DSM_COG_10_{lat_s}_{lon_s}_DEM"
    return f"{BUCKET_BASE}/{name}/{name}.tif"


def download_tile(lat: int, lon: int, retries: int = 3) -> Optional[Path]:
    url = tile_url(lat, lon)
    fname = url.rsplit("/", 1)[-1]
    out = RAW_DIR / fname
    if out.exists() and out.stat().st_size > 0:
        print(f"  ⊙ {fname} (cached)")
        return out

    for attempt in range(1, retries + 1):
        suffix = f" (retry {attempt})" if attempt > 1 else ""
        print(f"  ↓ {fname}{suffix} ... ", end="", flush=True)
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code == 404:
                    print("404 (ocean/missing)")
                    return None
                r.raise_for_status()
                expected = int(r.headers.get("Content-Length", "0"))
                with open(out, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            actual = out.stat().st_size
            if expected and actual != expected:
                print(f"SIZE MISMATCH {actual}/{expected} — will retry")
                out.unlink()
                continue
            print(f"{actual // (1 << 20)} MB ✓")
            return out
        except Exception as e:
            print(f"FAIL {e}")
            if out.exists():
                out.unlink()
    return None


def run(cmd: List[str]):
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {cmd[0]}")


def run_capture(cmd: List[str]) -> subprocess.CompletedProcess:
    """Like run() but returns the process so the caller can inspect stderr."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)


def parse_corrupt_tiles_from_stderr(stderr_text: str) -> List[Path]:
    """Extract .tif paths from TIFFReadEncodedTile / IReadBlock error messages.
    Matches lines like:
      ERROR 1: D:\\path\\Copernicus_DSM_COG_10_N22_00_E104_00_DEM.tif, band 1: IReadBlock failed ...
    """
    paths = set()
    for m in re.finditer(r"ERROR 1:\s+([^,\r\n]+\.tif),\s+band", stderr_text):
        p = Path(m.group(1).strip())
        # Only consider files inside RAW_DIR — never the output file itself
        if p.exists() and RAW_DIR in p.parents:
            paths.add(p)
    return sorted(paths)


def parse_tile_latlon(filename: str) -> Optional[Tuple[int, int]]:
    """Copernicus_DSM_COG_10_N22_00_E104_00_DEM.tif → (22, 104)."""
    m = re.search(r"([NS])(\d+)_\d+_([EW])(\d+)", filename)
    if not m:
        return None
    lat = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lon = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    return lat, lon


def main():
    print(f"AOI: {AOI_PATH}")
    west, south, east, north = load_aoi_bbox(AOI_PATH)
    print(f"BBox (4326): W={west} S={south} E={east} N={north}")

    tiles = tiles_for_bbox(west, south, east, north)
    print(f"Tiles to fetch: {len(tiles)}")
    downloaded = []
    for lat, lon in tiles:
        p = download_tile(lat, lon)
        if p:
            downloaded.append(p)

    if not downloaded:
        raise SystemExit("No DEM tiles downloaded — check AOI / network.")

    vrt_path = INTERIM_DIR / "dem_4326.vrt"
    out_tif = INTERIM_DIR / "dem.tif"
    warp_cmd = [
        "gdalwarp",
        "-overwrite",
        "-t_srs", PROJECT_CRS,
        "-tr", str(TARGET_RES), str(TARGET_RES),
        "-r", "bilinear",
        "-cutline", str(AOI_PATH),
        "-crop_to_cutline",
        "-dstnodata", "-9999",
        "-co", "COMPRESS=DEFLATE",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=YES",
        str(vrt_path),
        str(out_tif),
    ]

    # Build VRT + warp with self-healing: if gdalwarp fails because a source
    # tile is corrupt (TIFFReadEncodedTile error), delete the bad tile(s),
    # re-download them, and retry. Up to 3 attempts total.
    MAX_ATTEMPTS = 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\nBuilding VRT → {vrt_path.name}")
        run(["gdalbuildvrt", "-overwrite", str(vrt_path), *map(str, downloaded)])

        print(f"Warping → {out_tif.name}  [{PROJECT_CRS}, {TARGET_RES} m]")
        proc = run_capture(warp_cmd)
        if proc.returncode == 0:
            break

        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)

        corrupt = parse_corrupt_tiles_from_stderr(proc.stderr)
        if not corrupt:
            raise SystemExit("gdalwarp failed (no corrupt tiles detected; see stderr above)")

        print(f"\n  ⚠ {len(corrupt)} corrupt source tile(s) detected — self-healing:")
        for cp in corrupt:
            print(f"    deleting {cp.name}")
            cp.unlink(missing_ok=True)
            ll = parse_tile_latlon(cp.name)
            if ll is None:
                print(f"    ? could not parse lat/lon from {cp.name}")
                continue
            lat, lon = ll
            new_p = download_tile(lat, lon)
            if new_p is None:
                raise SystemExit(f"re-download failed for {cp.name}")

        # Refresh downloaded list from disk (order matters for deterministic VRT)
        downloaded = sorted(RAW_DIR.glob("*.tif"))
        print(f"  retrying warp (attempt {attempt + 1}/{MAX_ATTEMPTS})")
    else:
        raise SystemExit(f"gdalwarp still failing after {MAX_ATTEMPTS} self-heal attempts")

    print(f"\n✓ DEM ready: {out_tif}")
    print(f"  (source tiles: {RAW_DIR})")


if __name__ == "__main__":
    ensure_gdal_on_path()
    if shutil.which("gdalwarp") is None:
        raise SystemExit(
            "gdalwarp not found. Install QGIS/OSGeo4W or set env var GDAL_BIN="
            "<path to bin dir containing gdalwarp.exe>."
        )
    main()
