"""
Input:  data/02_interim/dem.tif (projected DEM in ESRI:102012)
Output: data/03_processed/hillshade.tif (single-band multidirectional hillshade)
Purpose: Produce a gray hillshade substrate for the NatGeo-style base; no color relief.

Use as a subtle gray substrate in QGIS — load the layer, set blend mode
(multiply) and opacity interactively per style_params.yaml.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def ensure_gdal_on_path():
    """Prepend a QGIS/OSGeo4W bin dir to PATH if gdaldem isn't already there.
    Override with env var GDAL_BIN=<dir>."""
    if shutil.which("gdaldem"):
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
    for parent in [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]:
        if parent.exists():
            for d in parent.glob("QGIS*/bin"):
                candidates.append(d)
    for c in candidates:
        if (c / "gdaldem.exe").exists() or (c / "gdaldem").exists():
            os.environ["PATH"] = str(c) + os.pathsep + os.environ.get("PATH", "")
            print(f"  [gdal] using {c}")
            return

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEM_IN = PROJECT_ROOT / "data" / "02_interim" / "dem.tif"
OUT_DIR = PROJECT_ROOT / "data" / "03_processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)
HILLSHADE_OUT = OUT_DIR / "hillshade.tif"

# TODO: tune z-factor after first visual check in QGIS (karst may need z>1.0).
Z_FACTOR = 1.0
# TODO: altitude/azimuth are overridden by -multidirectional; keep for reference.


def run(cmd: List[str]):
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {cmd[0]}")


def main():
    if not DEM_IN.exists():
        raise SystemExit(f"Missing {DEM_IN}. Run fetch_dem.py first.")

    print(f"Input DEM: {DEM_IN}")
    print(f"Output:    {HILLSHADE_OUT}")

    run([
        "gdaldem", "hillshade",
        str(DEM_IN),
        str(HILLSHADE_OUT),
        "-multidirectional",
        "-z", str(Z_FACTOR),
        "-compute_edges",
        "-of", "GTiff",
        "-co", "COMPRESS=DEFLATE",
        "-co", "TILED=YES",
    ])

    print(f"\n✓ Hillshade ready: {HILLSHADE_OUT}")
    print("  Load in QGIS; set blend mode (multiply) + opacity via style_params.yaml.")


if __name__ == "__main__":
    ensure_gdal_on_path()
    if shutil.which("gdaldem") is None:
        raise SystemExit(
            "gdaldem not found. Install QGIS/OSGeo4W or set env var GDAL_BIN="
            "<path to bin dir containing gdaldem.exe>."
        )
    main()
