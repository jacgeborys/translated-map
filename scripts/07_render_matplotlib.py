"""
Standalone matplotlib map — no QGIS required.
Layers: ocean, country borders, highways (motorway + trunk), railways, city labels.
Labels: English translation (from places_translated.gpkg) with original Chinese above at half size.

Run:
    python scripts/render_matplotlib.py
    python scripts/render_matplotlib.py --dpi 100 --out output/preview.png

Output: output/china_map_mpl.png  (default)
"""

import argparse
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

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
COL_MOTORWAY = "#a03d10"   # burnt sienna
COL_TRUNK    = "#d49a60"   # amber
COL_RAIL_HSR = "#1a1a1a"   # near-black, thicker
COL_RAIL_STD = "#2a2a2a"   # dark grey, thin
COL_LABEL    = "#2a2a2a"
COL_LABEL_ZH = "#888888"   # muted grey for Chinese name
COL_DOT      = "#222222"


def _load(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(CRS)


def _label_en(row) -> str:
    """Waterfall: Claude translation → name:en → name:pinyin → name."""
    for col in ["name_eng", "name:en", "name:pinyin", "name"]:
        v = row.get(col)
        if v and str(v).strip() and str(v).strip().lower() != "nan":
            return str(v).strip()
    return ""


def _font_sizes(pop: float):
    """Return (en_pt, zh_pt) label sizes for a city population."""
    if pop >= 5_000_000:
        return 11, 5.5
    if pop >= 1_000_000:
        return 9, 4.5
    if pop >= 500_000:
        return 7.5, 3.8
    if pop >= 100_000:
        return 6.5, 3.3
    return 5.5, 2.8


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dpi",  type=int,   default=150)
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

    # Cities with known population, sorted largest-first for label z-order
    cities = places[places["place"] == "city"].copy()
    cities = cities[cities["population"].notna() & (cities["population"] > 0)]
    cities = cities.sort_values("population", ascending=False)
    cities["_label_en"] = cities.apply(_label_en, axis=1)
    cities["_label_zh"] = cities["name"].fillna("").astype(str)

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
    pad_x = (xmax - xmin) * 0.05
    pad_y = (ymax - ymin) * 0.05
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

    # ── City dots + labels ────────────────────────────────────────────────────
    buf = [pe.withStroke(linewidth=2.5, foreground=BG)]

    for _, row in cities.iterrows():
        pop = float(row["population"])
        x, y = row.geometry.x, row.geometry.y

        # Skip if outside visible extent
        if not (xmin < x < xmax and ymin < y < ymax):
            continue

        sz_en, sz_zh = _font_sizes(pop)
        bold  = pop >= 1_000_000
        label_en = row["_label_en"]
        label_zh = row["_label_zh"]

        if not label_en:
            continue

        dot_size = 3.5 if pop >= 1_000_000 else 2.0

        # Dot
        ax.plot(x, y, "o",
                markersize=dot_size,
                color=COL_DOT,
                markeredgecolor="#ffffff",
                markeredgewidth=0.4,
                zorder=8)

        # Chinese name above (only when it differs from the English label)
        if label_zh and label_zh != label_en:
            ax.annotate(
                label_zh, xy=(x, y),
                xytext=(4, sz_en * 1.55),
                textcoords="offset points",
                fontsize=sz_zh,
                color=COL_LABEL_ZH,
                ha="left", va="bottom",
                path_effects=buf,
                zorder=9,
            )

        # English name
        ax.annotate(
            label_en, xy=(x, y),
            xytext=(4, 2),
            textcoords="offset points",
            fontsize=sz_en,
            color=COL_LABEL,
            fontweight="bold" if bold else "normal",
            ha="left", va="bottom",
            path_effects=buf,
            zorder=9,
        )

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"Rendering → {out_path}  ({args.dpi} dpi)")
    plt.savefig(out_path, dpi=args.dpi, bbox_inches="tight",
                facecolor=BG, format="png")
    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
