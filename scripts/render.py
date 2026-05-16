"""
Input:  china-map.qgz (created in QGIS and styled via apply_styles.py)
Output: output/china_map.png  (or --out path)
Purpose: Headless PyQGIS map export — no QGIS GUI needed.

Run under QGIS's bundled Python:
  "C:\\Program Files\\QGIS 3.xx\\bin\\python-qgis.bat" scripts/render.py

Optional arguments:
  --width-mm   paper width  in mm  (default 420, A3 landscape)
  --height-mm  paper height in mm  (default 297)
  --dpi        output DPI          (default 300)
  --out        output PNG path     (default output/china_map.png)
"""

import argparse
import sys
from pathlib import Path

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    # Running inside QGIS Python console where __file__ is not defined.
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")

QGZ_PATH   = PROJECT_ROOT / "china-map.qgz"
OUTPUT_DIR = PROJECT_ROOT / "output"

BACKGROUND = "#f5f0e8"   # NatGeo cream


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm / 25.4 * dpi))


def parse_args():
    p = argparse.ArgumentParser(description="Headless PyQGIS map export")
    p.add_argument("--width-mm",  type=float, default=420,
                   help="Paper width in mm (default 420 = A3 landscape)")
    p.add_argument("--height-mm", type=float, default=297,
                   help="Paper height in mm (default 297)")
    p.add_argument("--dpi",       type=int,   default=300,
                   help="Output DPI (default 300)")
    p.add_argument("--out",       type=str,   default=None,
                   help="Output PNG path (default output/china_map.png)")
    return p.parse_args()


def main():
    args = parse_args()
    out_path = Path(args.out) if args.out else OUTPUT_DIR / "china_map.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    from qgis.core import (
        QgsApplication, QgsProject,
        QgsMapSettings, QgsMapRendererParallelJob,
        QgsRectangle,
    )
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor

    standalone = QgsApplication.instance() is None
    if standalone:
        QgsApplication.setPrefixPath(str(Path(sys.executable).parent.parent), True)
        app = QgsApplication([], False)
        app.initQgis()

    project = QgsProject.instance()

    if standalone:
        if not QGZ_PATH.exists():
            raise SystemExit(
                f"Missing: {QGZ_PATH}\n"
                "Open QGIS, load your layers, save as china-map.qgz, "
                "then run apply_styles.py before rendering."
            )
        if not project.read(str(QGZ_PATH)):
            raise SystemExit(f"Failed to read: {QGZ_PATH}")
        print(f"Project:  {QGZ_PATH}")
    else:
        print(f"Running inside QGIS: {project.fileName()}")

    layers = list(project.mapLayers().values())
    print(f"Layers ({len(layers)}): {[l.name() for l in layers]}")

    # Build map settings
    settings = QgsMapSettings()
    settings.setLayers(layers)
    settings.setBackgroundColor(QColor(BACKGROUND))
    settings.setOutputDpi(args.dpi)
    settings.setDestinationCrs(project.crs())

    w_px = mm_to_px(args.width_mm, args.dpi)
    h_px = mm_to_px(args.height_mm, args.dpi)
    settings.setOutputSize(QSize(w_px, h_px))

    # Use the project's stored view extent; fall back to union of all layer extents.
    try:
        extent = project.viewSettings().fullExtent()
    except AttributeError:
        extent = QgsRectangle()
    if extent.isEmpty():
        for lyr in layers:
            if lyr.isValid():
                try:
                    extent.combineExtentWith(lyr.extent())
                except Exception:
                    pass
    settings.setExtent(extent)

    print(f"Extent:   {extent.toString(4)}")
    print(f"Rendering {w_px} x {h_px} px @ {args.dpi} dpi  ->  {out_path}")

    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()

    img = job.renderedImage()
    if img.isNull():
        raise SystemExit("Render failed — image is null. Check that all layer sources exist.")

    img.save(str(out_path))
    print(f"Saved:    {out_path}")

    if standalone:
        app.exitQgis()


if __name__ == "__main__":
    main()
