"""
Standalone matplotlib map — no QGIS required.
Layers: ocean, country borders, highways (motorway + trunk), railways, city labels.
Labels: two lines, both in English —
  top (half size, muted): transliteration  e.g. "Guilin"
  bottom (full size):     literal meaning  e.g. "Osmanthus Forest"

Run:
    python scripts/07_render_matplotlib.py
    python scripts/07_render_matplotlib.py --dpi 100 --out output/preview.png

Output: output/china_map_mpl.png  (default)
"""

import argparse
import warnings
from pathlib import Path

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from adjustText import adjust_text

warnings.filterwarnings("ignore")

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")

# ── Data paths ────────────────────────────────────────────────────────────────
OCEAN     = PROJECT_ROOT / "data/01_raw/ocean/ne_10m_ocean.gpkg"
COUNTRIES = PROJECT_ROOT / "data/01_raw/osm/admin_country.gpkg"
RAILWAYS  = PROJECT_ROOT / "data/01_raw/osm/railways.gpkg"
ROADS     = PROJECT_ROOT / "data/01_raw/osm/roads.gpkg"
PLACES    = PROJECT_ROOT / "data/03_processed/places_translated.gpkg"

OUTPUT_DIR = PROJECT_ROOT / "output"

# ── Projection (same as QGIS project) ─────────────────────────────────────────
CRS = "ESRI:102012"

# ── Palette (from apply_styles.py) ────────────────────────────────────────────
BG           = "#f5f0e8"   # NatGeo cream background
COL_OCEAN    = "#a9c9d6"
COL_BORDER   = "#a04060"
COL_MOTORWAY = "#ddb89a"   # very pale burnt sienna
COL_TRUNK    = "#e8dbbf"   # very pale amber
COL_RAIL_HSR = "#c0bfbc"   # pale grey, slightly warm
COL_RAIL_STD = "#ceccc8"   # lighter pale grey
COL_LABEL       = "#2a2a2a"
COL_LABEL_SMALL = "#555555"   # stronger grey for transliteration
COL_DOT         = "#222222"
COL_LEADER      = "#aaaaaa"   # leader line colour

HILLSHADE_URL = (
    "https://services.arcgisonline.com/arcgis/rest/services"
    "/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}"
)
HILLSHADE_ALPHA = 0.25   # very pale — pure shading substrate


def _load(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(CRS)


def _translation(row) -> str:
    """Primary label: Claude literal meaning translation (name_eng)."""
    v = row.get("name_eng")
    if v and str(v).strip() and str(v).strip().lower() != "nan":
        return str(v).strip()
    return ""


def _transliteration(row) -> str:
    """Secondary label (above): romanised name — name:en or pinyin, no Chinese."""
    for col in ["name:en", "name:pinyin"]:
        v = row.get(col)
        if v and str(v).strip() and str(v).strip().lower() != "nan":
            return str(v).strip()
    return ""


def _font_sizes(pop: float):
    """Return (main_pt, small_pt) label sizes. small = 0.75 × main."""
    if pop >= 5_000_000:
        main = 7
    elif pop >= 1_000_000:
        main = 6
    elif pop >= 500_000:
        main = 5
    elif pop >= 100_000:
        main = 4.5
    else:
        main = 4
    return main, round(main * 0.75, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dpi",  type=int,   default=300)
    p.add_argument("--out",  type=str,   default=None)
    args = p.parse_args()

    out_path = Path(args.out) if args.out else OUTPUT_DIR / "china_map_mpl.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Load ─────────────────────────────────────────────────────────────────
    print("Loading layers...")
    ocean     = _load(OCEAN)
    countries = _load(COUNTRIES)
    railways  = _load(RAILWAYS)
    roads     = _load(ROADS)
    places    = _load(PLACES)

    # Highways: motorway (1) + trunk (2) only
    highways = roads[roads["hierarchy"].isin([1, 2])].copy() if "hierarchy" in roads.columns else roads
    motorways = highways[highways["hierarchy"] == 1]
    trunks    = highways[highways["hierarchy"] == 2]

    # HSR vs conventional rail
    hsr_mask = (
        (railways.get("highspeed") == "yes") |
        (railways.get("maxspeed", "").str.extract(r"(\d+)")[0].astype(float, errors="ignore") >= 200)
    ) if "highspeed" in railways.columns else railways.index.isin([])
    hsr  = railways[hsr_mask]
    rail = railways[~hsr_mask]

    # Cities with known population, sorted largest-first for label z-order.
    # Only keep rows that have BOTH a Claude translation (name_eng) AND a
    # romanised name (name:en / name:pinyin) — the two label lines.
    cities = places[places["place"] == "city"].copy()
    cities = cities[cities["population"].notna() & (cities["population"] > 0)]
    cities["_translation"]     = cities.apply(_translation, axis=1)
    cities["_transliteration"] = cities.apply(_transliteration, axis=1)
    # Keep only cities where the Claude translation is present
    has_translation = cities["name_eng"].notna() & (cities["name_eng"].astype(str).str.strip() != "")
    has_translit    = cities["_transliteration"] != ""
    cities = cities[has_translation & has_translit].copy()
    cities = cities.sort_values("population", ascending=False)

    print(f"  ocean polygons:  {len(ocean)}")
    print(f"  country borders: {len(countries)}")
    print(f"  motorways:       {len(motorways)}")
    print(f"  trunks:          {len(trunks)}")
    print(f"  rail (std):      {len(rail)}")
    print(f"  rail (HSR):      {len(hsr)}")
    print(f"  cities:          {len(cities)}")

    # ── Map extent: union of OSM layers + 5 % padding ─────────────────────────
    bounds = highways.total_bounds if not highways.empty else countries.total_bounds
    for gdf in [railways, cities]:
        if not gdf.empty:
            b = gdf.total_bounds
            bounds = [
                min(bounds[0], b[0]), min(bounds[1], b[1]),
                max(bounds[2], b[2]), max(bounds[3], b[3]),
            ]
    xmin, ymin, xmax, ymax = bounds
    pad_x = (xmax - xmin) * 0.01
    pad_y = (ymax - ymin) * 0.01
    xmin -= pad_x; xmax += pad_x
    ymin -= pad_y; ymax += pad_y

    # Clip ocean to extent for speed
    from shapely.geometry import box as shapely_box
    clip_box = gpd.GeoDataFrame(geometry=[shapely_box(xmin, ymin, xmax, ymax)], crs=CRS)
    ocean_clip = gpd.clip(ocean, clip_box)

    # ── Figure ────────────────────────────────────────────────────────────────
    aspect = (xmax - xmin) / (ymax - ymin)
    fig_h = 12
    fig_w = fig_h * aspect
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=args.dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_aspect("equal")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.axis("off")

    # ── Draw layers ───────────────────────────────────────────────────────────
    if not ocean_clip.empty:
        ocean_clip.plot(ax=ax, color=COL_OCEAN, linewidth=0, zorder=1)

    # Hillshade — fetched from ArcGIS tile service, reprojected to CRS
    print("Fetching hillshade tiles...")
    try:
        ctx.add_basemap(
            ax,
            crs=CRS,
            source=HILLSHADE_URL,
            alpha=HILLSHADE_ALPHA,
            zorder=2,
            attribution=False,
        )
    except Exception as e:
        print(f"  hillshade skipped: {e}")

    countries.plot(ax=ax, facecolor="none", edgecolor=COL_BORDER,
                   linewidth=0.8, zorder=4)

    if not rail.empty:
        rail.plot(ax=ax, color=COL_RAIL_STD, linewidth=0.45, zorder=3)
    if not hsr.empty:
        hsr.plot(ax=ax, color=COL_RAIL_HSR, linewidth=0.75, zorder=3)

    if not trunks.empty:
        trunks.plot(ax=ax, color=COL_TRUNK, linewidth=0.65, zorder=5)
    if not motorways.empty:
        motorways.plot(ax=ax, color=COL_MOTORWAY, linewidth=1.1, zorder=5)

    # ── City dots + translation labels ───────────────────────────────────────
    # Strategy:
    #   1. Draw dots and place translation (main) text objects.
    #   2. Run adjustText to push overlapping labels apart (no arrows).
    #   3. Draw canvas to get final bounding boxes.
    #   4. Place each transliteration text flush against the top of its
    #      adjusted translation — they always appear as one tight unit.
    buf = [pe.withStroke(linewidth=1.5, foreground=BG)]

    trans_texts = []   # Text objects for adjust_text
    trans_meta  = []   # (sz_small, translit) paired with trans_texts
    city_xs, city_ys = [], []

    for _, row in cities.iterrows():
        pop = float(row["population"])
        x, y = row.geometry.x, row.geometry.y

        if not (xmin < x < xmax and ymin < y < ymax):
            continue

        sz_main, sz_small = _font_sizes(pop)
        translation = row["_translation"]
        translit    = row["_transliteration"]

        if not translation:
            continue

        # Dot
        dot_size = 3.0 if pop >= 1_000_000 else 1.8
        ax.plot(x, y, "o",
                markersize=dot_size,
                color=COL_DOT,
                markeredgecolor="#ffffff",
                markeredgewidth=0.35,
                zorder=8)

        # Translation text (will be repositioned by adjust_text)
        t = ax.text(x, y, translation,
                    fontsize=sz_main,
                    color=COL_LABEL,
                    fontweight="bold" if pop >= 1_000_000 else "normal",
                    ha="left", va="bottom",
                    path_effects=buf,
                    zorder=9)
        trans_texts.append(t)
        trans_meta.append((sz_small, translit))
        city_xs.append(x)
        city_ys.append(y)

    # Push overlapping labels apart (no arrowprops — FancyArrowPatch is
    # incompatible with projected transforms; we draw leader lines manually below)
    adjust_text(
        trans_texts,
        x=city_xs, y=city_ys,
        ax=ax,
        expand=(1.1, 1.2),
        force_text=(0.2, 0.4),
        force_points=(0.1, 0.2),
    )

    # Render canvas so bounding boxes are computed at final label positions
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    # Draw leader lines manually: city dot → label anchor, only when the label
    # has been pushed more than 15 km away from its city point.
    leader_threshold = (xmax - xmin) * 0.015
    for i, t in enumerate(trans_texts):
        lx, ly = t.get_position()
        ox, oy = city_xs[i], city_ys[i]
        if ((lx - ox) ** 2 + (ly - oy) ** 2) ** 0.5 > leader_threshold:
            ax.plot([ox, lx], [oy, ly],
                    color=COL_LEADER, lw=0.5, zorder=8,
                    solid_capstyle="round")

    # Place transliteration flush above each adjusted translation label
    for t, (sz_small, translit) in zip(trans_texts, trans_meta):
        if not translit or translit == t.get_text():
            continue
        bbox = t.get_window_extent(renderer=renderer)
        x_data, _ = t.get_position()
        # Convert top edge of translation bbox from display → data coords
        _, y_top = inv.transform((bbox.x0, bbox.y1))
        ax.text(x_data, y_top, translit,
                fontsize=sz_small,
                color=COL_LABEL_SMALL,
                ha=t.get_ha(), va="bottom",
                path_effects=buf,
                zorder=9)

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"Rendering → {out_path}  ({args.dpi} dpi)")
    plt.savefig(out_path, dpi=args.dpi, bbox_inches="tight",
                facecolor=BG, format="png")
    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
