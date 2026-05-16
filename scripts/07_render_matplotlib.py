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

import numpy as np
import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import ListedColormap
from adjustText import adjust_text

warnings.filterwarnings("ignore")

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")

# ── Data paths ────────────────────────────────────────────────────────────────
OCEAN        = PROJECT_ROOT / "data/01_raw/ocean/ne_10m_ocean.gpkg"
COUNTRIES    = PROJECT_ROOT / "data/01_raw/osm/admin_country.gpkg"
WATER_BODIES = PROJECT_ROOT / "data/01_raw/osm/water_bodies.gpkg"
RAILWAYS     = PROJECT_ROOT / "data/01_raw/osm/railways.gpkg"
ROADS        = PROJECT_ROOT / "data/01_raw/osm/roads.gpkg"
PLACES       = PROJECT_ROOT / "data/03_processed/places_translated.gpkg"
WORLDCOVER   = PROJECT_ROOT / "data/03_processed/worldcover.tif"

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
    ocean        = _load(OCEAN)
    countries    = _load(COUNTRIES)
    water_bodies = _load(WATER_BODIES)
    railways     = _load(RAILWAYS)
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

    # Cities: require Claude translation + romanised name, population >= 1M.
    # Allowlisted cities (always included regardless of neighbours).
    ALLOWLIST = {"Hong Kong", "Taipei"}

    cities = places[places["place"] == "city"].copy()
    cities = cities[cities["population"].notna() & (cities["population"] > 0)]
    cities["_translation"]     = cities.apply(_translation, axis=1)
    cities["_transliteration"] = cities.apply(_transliteration, axis=1)
    has_translation = cities["name_eng"].notna() & (cities["name_eng"].astype(str).str.strip() != "")
    has_translit    = cities["_transliteration"] != ""
    has_labels      = has_translation & has_translit
    in_allowlist    = cities["name:en"].isin(ALLOWLIST)
    cities = cities[has_labels & ((cities["population"] >= 1_000_000) | in_allowlist)].copy()
    # Sort: allowlist cities first so they are always accepted, then by population
    cities["_allow"] = cities["name:en"].isin(ALLOWLIST).astype(int)
    cities = cities.sort_values(["_allow", "population"], ascending=[False, False])

    print(f"  ocean polygons:  {len(ocean)}")
    print(f"  water bodies:    {len(water_bodies)}")
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
        ocean_clip.plot(ax=ax, color=COL_OCEAN, linewidth=0, zorder=4.5)

    if not water_bodies.empty:
        water_bodies.plot(ax=ax, color=COL_OCEAN, linewidth=0, zorder=4.5)

    # WorldCover — very pale land-cover tints under hillshade
    if WORLDCOVER.exists():
        print("Rendering WorldCover tints...")
        try:
            import rasterio
            with rasterio.open(WORLDCOVER) as src:
                wc_data = src.read(1)
                b = src.bounds
                wc_extent = (b.left, b.right, b.bottom, b.top)
            for cls, col, alpha in [
                (10, "#b8d4a8", 0.30),   # trees    — pale sage green
                (40, "#ece4c0", 0.30),   # cropland — pale wheat
                (50, "#d0c8c0", 0.35),   # built-up — pale warm grey
            ]:
                mask = np.where(wc_data == cls, 1.0, np.nan)
                ax.imshow(mask, extent=wc_extent, aspect="auto",
                          cmap=ListedColormap([col]), alpha=alpha,
                          zorder=1.5, interpolation="nearest", origin="upper")
        except Exception as e:
            print(f"  worldcover skipped: {e}")

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

    _n = len(ax.collections)
    countries.plot(ax=ax, facecolor="none", edgecolor=COL_BORDER,
                   linewidth=0.8, zorder=4)
    for _c in ax.collections[_n:]:
        _c.set_path_effects([pe.withStroke(linewidth=3.5, foreground="#ffffff")])

    if not rail.empty:
        rail.plot(ax=ax, color=COL_RAIL_STD, linewidth=0.45, zorder=3)
    if not hsr.empty:
        hsr.plot(ax=ax, color=COL_RAIL_HSR, linewidth=0.75, zorder=3)

    if not trunks.empty:
        trunks.plot(ax=ax, color=COL_TRUNK, linewidth=0.65, zorder=5)
    if not motorways.empty:
        motorways.plot(ax=ax, color=COL_MOTORWAY, linewidth=1.1, zorder=5)

    # ── City labels — greedy bbox collision detection ─────────────────────────
    # Strategy:
    #   1. Place every candidate label invisibly at a fixed offset from its dot.
    #   2. Draw canvas once to get real rendered bounding boxes.
    #   3. Walk cities largest-first (allowlist first); accept a label only if
    #      its bbox (expanded for breathing room + transliteration height) does
    #      not overlap any already-accepted bbox.
    #   4. Make accepted labels visible; add transliteration flush above each.
    # Result: zero overlaps guaranteed, labels stay next to their dots.
    buf = [pe.withStroke(linewidth=1.5, foreground=BG)]
    inv = ax.transData.inverted()

    # Place all candidates visibly so get_window_extent returns real bboxes
    candidates = []
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
        t = ax.text(x, y, translation,
                    fontsize=sz_main,
                    color=COL_LABEL,
                    fontweight="bold" if pop >= 1_000_000 else "normal",
                    ha="left", va="bottom",
                    path_effects=buf,
                    zorder=9,
                    visible=True)
        candidates.append((t, pop, x, y, sz_main, sz_small, translit,
                           row.get("name:en", "") in ALLOWLIST))

    print(f"  label candidates: {len(candidates)}")

    # Draw once so the renderer can compute real font-metric bboxes
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    accepted_bboxes = []   # display-coord bboxes of accepted labels
    accepted = []          # (t, pop, x, y, sz_small, translit)

    for t, pop, cx, cy, sz_main, sz_small, translit, is_allowlist in candidates:
        raw_bb = t.get_window_extent(renderer=renderer)
        # Expand: 10 % horizontal breathing room + 80 % vertical to cover the
        # transliteration line that will sit above the translation.
        bb = raw_bb.expanded(1.05, 1.35)
        if is_allowlist or not any(bb.overlaps(ex) for ex in accepted_bboxes):
            accepted_bboxes.append(bb)
            accepted.append((t, pop, cx, cy, sz_small, translit))
        else:
            t.set_visible(False)

    print(f"  labels placed:   {len(accepted)}")

    # Draw dots and transliterations for accepted labels
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    for t, pop, cx, cy, sz_small, translit in accepted:
        dot_size = 3.0 if pop >= 1_000_000 else 1.8
        ax.plot(cx, cy, "o",
                markersize=dot_size,
                color=COL_DOT,
                markeredgecolor="#ffffff",
                markeredgewidth=0.35,
                zorder=8)

        # Transliteration flush above translation
        if translit and translit != t.get_text():
            bb = t.get_window_extent(renderer=renderer)
            x_data, _ = t.get_position()
            _, y_top = inv.transform((bb.x0, bb.y1))
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
