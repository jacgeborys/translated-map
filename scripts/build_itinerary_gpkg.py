"""
build_itinerary_gpkg.py
-----------------------
Reads config/pois.csv and writes data/03_processed/china_itinerary.gpkg
with a single point layer: "itinerary_stops".

Run from the project root:
    python scripts/build_itinerary_gpkg.py

Column reference (from Google Sheet Attractions tab):
  priority   1=Must-do  2=High  3=Nice  4=Optional  5=Skip
  cat_id     1=City/Skyline  2=Nature  3=Temple/Heritage
             4=Museum  5=Activity  6=Food/Market  7=Transport
  status_id  1=Confirmed  2=Optional  3=Missed/NextTrip  4=Archived
  detour     0=On route  1=Requires dedicated detour
  half_day   0=Full day  1=Half day (~3-5h)  2=Quick visit (1-2h)
  visit_order  Sequential integer for confirmed route stops; 0 = not on route
"""

from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "config" / "pois.csv"
OUT  = ROOT / "data" / "03_processed" / "china_itinerary.gpkg"

LAYER = "itinerary_stops"

COL_ORDER = [
    "id", "visit_order", "day",
    "name_en", "city",
    "priority", "cat_id", "cat_name",
    "status_id", "status_name",
    "detour", "half_day",
    "notes", "geometry",
]

def main():
    df = pd.read_csv(SRC, encoding="utf-8", dtype={
        "id": int, "day": int, "visit_order": int,
        "priority": int, "cat_id": int,
        "status_id": int, "detour": int, "half_day": int,
    })

    geometry = [Point(row.lon, row.lat) for row in df.itertuples()]

    gdf = gpd.GeoDataFrame(
        df.drop(columns=["lon", "lat"]),
        geometry=geometry,
        crs="EPSG:4326",
    )

    gdf = gdf[COL_ORDER]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, layer=LAYER, driver="GPKG")

    confirmed = (gdf["status_id"] == 1).sum()
    print(f"Written {len(gdf)} features ({confirmed} confirmed) → {OUT}")


if __name__ == "__main__":
    main()
