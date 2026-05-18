"""
build_itinerary_gpkg.py
-----------------------
Reads config/pois.csv and writes data/03_processed/china_itinerary.gpkg
with a single point layer: "itinerary_stops".

Run from the project root:
    python scripts/build_itinerary_gpkg.py
"""

from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "config" / "pois.csv"
OUT  = ROOT / "data" / "03_processed" / "china_itinerary.gpkg"

def main():
    df = pd.read_csv(SRC, dtype={"day_from": int, "day_to": int,
                                  "priority": int, "visit_order": int})

    geometry = [Point(row.lon, row.lat) for row in df.itertuples()]

    gdf = gpd.GeoDataFrame(
        df.drop(columns=["lon", "lat"]),
        geometry=geometry,
        crs="EPSG:4326",
    )

    # Column order that makes sense in QGIS attribute table
    cols = [
        "visit_order", "day_from", "day_to", "date_from",
        "name_en", "name_zh", "category", "priority",
        "notes", "geometry",
    ]
    gdf = gdf[cols]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, layer="itinerary_stops", driver="GPKG")
    print(f"Written {len(gdf)} features → {OUT}")


if __name__ == "__main__":
    main()
