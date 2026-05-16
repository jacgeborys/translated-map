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
    xmin += 300_000   # crop 300 km from the left edge

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
        _c.set_path_effects([pe.withStroke(linewidth=3.5, foreground="#f0c0d0")])

    if not rail.empty:
        rail.plot(ax=ax, color=COL_RAIL_STD, linewidth=0.45, zorder=3)
    if not hsr.empty:
        hsr.plot(ax=ax, color=COL_RAIL_HSR, linewidth=0.75, zorder=3)

    if not trunks.empty:
        trunks.plot(ax=ax, color=COL_TRUNK, linewidth=0.65, zorder=3.2)
    if not motorways.empty:
        motorways.plot(ax=ax, color=COL_MOTORWAY, linewidth=1.1, zorder=3.2)

    # ── City labels — force-directed placement ────────────────────────────────
    # Stage 1: spatial thinning (60 km) — suppress weaker city when two are
    #          too close, so dense clusters are pre-reduced.
    # Stage 2: place every surviving label at its preferred NE position,
    #          measure bboxes in data units (metres, ESRI:102012), then run
    #          N_ITER rounds of physics:
    #            • Repulsion: overlapping pairs are pushed apart symmetrically
    #              along the axis of smaller penetration — both labels move.
    #            • Spring: each label is weakly pulled back toward its preferred
    #              position so labels don't drift further than necessary.
    # Stage 3: update text anchors to final positions, flip ha left↔right if a
    #          label drifted past its dot, draw leader lines dot→bbox edge.
    # Result: all labels separated with symmetric displacement; dense coastal
    #         clusters (PRD) naturally spill into the adjacent sea.

    THIN_M   = 60_000   # thinning radius (m)
    N_ITER   = 150      # physics iterations
    SPRING_K = 0.06     # fraction pulled toward preferred each iteration
    BUF_M    = 1_000    # extra separation buffer beyond bbox edge (m)
    PAD      = 0.12     # additional fractional padding on half-extents

    buf = [pe.withStroke(linewidth=1.5, foreground=BG)]
    inv = ax.transData.inverted()

    # ── Stage 1: spatial thinning ─────────────────────────────────────────────
    # cities already sorted: allowlist first, then population descending.
    geoms_all = list(cities.geometry)
    excl = set()
    for i in range(len(cities)):
        if i in excl:
            continue
        for j in range(i + 1, len(cities)):
            if j not in excl and geoms_all[i].distance(geoms_all[j]) < THIN_M:
                if cities.iloc[j]["name:en"] not in ALLOWLIST:
                    excl.add(j)
    cities_thin = cities.iloc[[k for k in range(len(cities)) if k not in excl]]
    print(f"  cities after thinning: {len(cities_thin)}")

    # Preferred label offset from dot (NE direction)
    off_x = (xmax - xmin) * 0.006
    off_y = (ymax - ymin) * 0.004

    # ── Stage 2: place at preferred positions and measure bboxes ──────────────
    city_info = []
    texts = []
    for _, row in cities_thin.iterrows():
        pop  = float(row["population"])
        x, y = row.geometry.x, row.geometry.y
        if not (xmin < x < xmax and ymin < y < ymax):
            continue
        sz_main, sz_small = _font_sizes(pop)
        translation = row["_translation"]
        translit    = row["_transliteration"]
        if not translation:
            continue
        t = ax.text(x + off_x, y + off_y, translation,
                    fontsize=sz_main, color=COL_LABEL,
                    fontweight="bold" if pop >= 1_000_000 else "normal",
                    ha="left", va="bottom",
                    path_effects=buf, zorder=9, visible=True)
        texts.append(t)
        city_info.append({"cx": x, "cy": y, "translit": translit,
                           "pop": pop, "sz_small": sz_small})

    print(f"  label candidates: {len(texts)}")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # Convert display bboxes → data-unit centres and half-extents
    lbl_cx, lbl_cy = [], []       # label box centre (data units)
    lbl_hw, lbl_hh = [], []       # half-width / half-height (padded)
    pref_cx, pref_cy = [], []     # preferred centre (spring target)

    for t, d in zip(texts, city_info):
        bb   = t.get_window_extent(renderer=renderer)
        x0d, y0d = inv.transform((bb.x0, bb.y0))
        x1d, y1d = inv.transform((bb.x1, bb.y1))
        w, h = abs(x1d - x0d), abs(y1d - y0d)
        # anchor is bottom-left (ha=left, va=bottom) → centre offset by (w/2, h/2)
        cx = d["cx"] + off_x + w / 2
        cy = d["cy"] + off_y + h / 2
        lbl_cx.append(cx);   lbl_cy.append(cy)
        lbl_hw.append(w / 2 * (1 + PAD))
        lbl_hh.append(h / 2 * (1 + PAD))
        pref_cx.append(cx);  pref_cy.append(cy)

    # ── Physics loop ──────────────────────────────────────────────────────────
    n = len(texts)
    print(f"  running {N_ITER} physics iterations for {n} labels...")
    for _ in range(N_ITER):
        # Pairwise repulsion: push overlapping pairs apart symmetrically
        for i in range(n):
            for j in range(i + 1, n):
                dx = lbl_cx[i] - lbl_cx[j]
                dy = lbl_cy[i] - lbl_cy[j]
                ox = (lbl_hw[i] + lbl_hw[j]) - abs(dx)
                oy = (lbl_hh[i] + lbl_hh[j]) - abs(dy)
                if ox > 0 and oy > 0:
                    # Resolve along the axis with less penetration
                    if ox <= oy:
                        push = ox / 2 + BUF_M
                        sign = 1 if dx >= 0 else -1
                        lbl_cx[i] += sign * push
                        lbl_cx[j] -= sign * push
                    else:
                        push = oy / 2 + BUF_M
                        sign = 1 if dy >= 0 else -1
                        lbl_cy[i] += sign * push
                        lbl_cy[j] -= sign * push
        # Spring: pull each label back toward its preferred position
        for i in range(n):
            lbl_cx[i] += (pref_cx[i] - lbl_cx[i]) * SPRING_K
            lbl_cy[i] += (pref_cy[i] - lbl_cy[i]) * SPRING_K

    # ── Stage 3: update text positions, draw dots / leaders / translits ───────
    for i, (t, d) in enumerate(zip(texts, city_info)):
        hw = lbl_hw[i] / (1 + PAD)   # actual (unpadded) half-extents
        hh = lbl_hh[i] / (1 + PAD)
        # Flip ha if label drifted to the other side of the dot
        ha    = "left"  if lbl_cx[i] >= d["cx"] else "right"
        ax_x  = lbl_cx[i] - hw if ha == "left" else lbl_cx[i] + hw
        ax_y  = lbl_cy[i] - hh   # va="bottom"
        t.set_position((ax_x, ax_y))
        t.set_ha(ha)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    print(f"  labels placed: {n}")

    for i, (t, d) in enumerate(zip(texts, city_info)):
        hw = lbl_hw[i] / (1 + PAD)
        hh = lbl_hh[i] / (1 + PAD)
        cx_dot, cy_dot = d["cx"], d["cy"]

        # City dot
        dot_size = 3.0 if d["pop"] >= 1_000_000 else 1.8
        ax.plot(cx_dot, cy_dot, "o",
                markersize=dot_size, color=COL_DOT,
                markeredgecolor="#ffffff", markeredgewidth=0.35, zorder=8)

        # Leader line: dot → nearest point on label bbox edge
        bx0, bx1 = lbl_cx[i] - hw, lbl_cx[i] + hw
        by0, by1 = lbl_cy[i] - hh, lbl_cy[i] + hh
        near_x = max(bx0, min(cx_dot, bx1))
        near_y = max(by0, min(cy_dot, by1))
        ax.plot([cx_dot, near_x], [cy_dot, near_y],
                color=COL_LEADER, linewidth=1.0,
                solid_capstyle="round", zorder=7)

        # Transliteration always above translation
        if d["translit"] and d["translit"] != t.get_text():
            bb = t.get_window_extent(renderer=renderer)
            _, y_top = inv.transform((bb.x0, bb.y1))
            ax.text(t.get_position()[0], y_top, d["translit"],
                    fontsize=d["sz_small"], color=COL_LABEL_SMALL,
                    ha=t.get_ha(), va="bottom",
                    path_effects=buf, zorder=9)

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"Rendering → {out_path}  ({args.dpi} dpi)")
    plt.savefig(out_path, dpi=args.dpi, bbox_inches="tight",
                facecolor=BG, format="png")
    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
