"""
Input:  qgis/*.qgz, config/style_params.yaml
Output: output/*.png (and/or PDF)
Purpose: Headless export of the QGIS project via qgis_process / PyQGIS.

STUB — do not implement yet. The QGIS project file does not exist; styling
is done interactively first. Once the .qgz is ready, this script will call
qgis_process runalgorithm native:printlayouttoimage (or similar).
"""


def main():
    raise SystemExit("render.py: not implemented yet.")


if __name__ == "__main__":
    main()
