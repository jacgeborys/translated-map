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
COL_LEADER      = "#666666"   # leader line colour

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
    """Return (main_pt, small_pt). Scale anchored at 1 M pop minimum."""
    if pop >= 10_000_000:
        main = 8
    elif pop >= 5_000_000:
        main = 7
    elif pop >= 3_000_000:
        main = 6
    else:   # 1 M – 3 M
        main = 5
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

    # ── City labels — polar-coordinate angular sweep placement ───────────────
    # Stage 1: spatial thinning — suppress weaker city within THIN_M radius.
    # Stage 2: compute each city's preferred direction (outward from its local
    #          cluster centroid; singletons use sparsest density sector).
    #          Place labels there, measure bboxes, then run N_SWEEP rounds of
    #          angular sweep: for each of N_ANGLES candidate directions, compute
    #          via interval arithmetic the minimum polar distance needed to clear
    #          all other current label positions; score by distance + deviation
    #          from preferred direction; keep the best angle each round.
    # Stage 3: update text anchors, draw leader lines dot→bbox edge.
    # Result: each label finds the nearest clear position in the direction that
    #         most naturally exits its cluster (ocean for coastal cities).

    THIN_M   = 50_000   # thinning radius (m)
    PAD      = 0.12     # fractional padding on half-extents

    buf = [pe.withStroke(linewidth=1.5, foreground=BG)]

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

    # ── Compute clear direction for each city ─────────────────────────────────
    # Cities within CLUSTER_R of each other form a cluster (union-find).
    # Each city's clear direction = from its cluster centroid to itself, so
    # coastal clusters (PRD, Yangtze Delta) point labels toward the ocean.
    # Singletons fall back to the sparsest 45° density sector.
    CLUSTER_R   = 150_000   # 150 km clustering threshold
    INIT_OFFSET = min(xmax - xmin, ymax - ymin) * 0.014

    geom_list = [(row.geometry.x, row.geometry.y)
                 for _, row in cities_thin.iterrows()]
    m = len(geom_list)

    # Union-Find
    parent = list(range(m))
    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i in range(m):
        for j in range(i + 1, m):
            if np.hypot(geom_list[i][0] - geom_list[j][0],
                        geom_list[i][1] - geom_list[j][1]) < CLUSTER_R:
                ri, rj = _find(i), _find(j)
                if ri != rj:
                    parent[ri] = rj

    from collections import defaultdict
    _cluster_members = defaultdict(list)
    for i in range(m):
        _cluster_members[_find(i)].append(i)
    _cluster_centroid = {
        root: (np.mean([geom_list[k][0] for k in mems]),
               np.mean([geom_list[k][1] for k in mems]))
        for root, mems in _cluster_members.items()
    }

    # Sector fallback (for singletons or cities exactly at centroid)
    N_SECTORS  = 8
    SECTOR_ANG = [i * 2 * np.pi / N_SECTORS for i in range(N_SECTORS)]
    SECTOR_R   = 600_000

    clear_dirs = []
    for i, (xi, yi) in enumerate(geom_list):
        root = _find(i)
        mems = _cluster_members[root]
        if len(mems) > 1:
            cx_c, cy_c = _cluster_centroid[root]
            dx, dy = xi - cx_c, yi - cy_c
            dist = np.hypot(dx, dy)
            if dist > 500:
                clear_dirs.append((dx / dist, dy / dist))
                continue
        # Singleton or at centroid: use sparsest sector
        counts = np.zeros(N_SECTORS)
        for j, (xj, yj) in enumerate(geom_list):
            if j == i:
                continue
            d = np.hypot(xj - xi, yj - yi)
            if d < SECTOR_R:
                ang = np.arctan2(yj - yi, xj - xi) % (2 * np.pi)
                sec = int(ang / (2 * np.pi) * N_SECTORS) % N_SECTORS
                counts[sec] += 1.0 - d / SECTOR_R
        best_sec = int(np.argmin(counts))
        clear_dirs.append((np.cos(SECTOR_ANG[best_sec]),
                           np.sin(SECTOR_ANG[best_sec])))

    # ── Stage 2: place at preferred positions and measure bboxes ──────────────
    city_info = []
    texts = []
    for idx, (_, row) in enumerate(cities_thin.iterrows()):
        pop  = float(row["population"])
        x, y = row.geometry.x, row.geometry.y
        if not (xmin < x < xmax and ymin < y < ymax):
            continue
        sz_main, sz_small = _font_sizes(pop)
        translation = row["_translation"]
        translit    = row["_transliteration"]
        if not translation:
            continue
        cd    = clear_dirs[idx]
        off_x = cd[0] * INIT_OFFSET
        off_y = cd[1] * INIT_OFFSET
        t = ax.text(x + off_x, y + off_y, translation,
                    fontsize=sz_main, color=COL_LABEL,
                    fontweight="bold" if pop >= 5_000_000 else "normal",
                    ha="left", va="bottom",
                    path_effects=buf, zorder=9, visible=True)
        texts.append(t)
        city_info.append({"cx": x, "cy": y, "translit": translit,
                           "pop": pop, "sz_small": sz_small, "clear_dir": cd})

    print(f"  label candidates: {len(texts)}")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # Capture inv AFTER draw so set_aspect("equal") has finalised the transform
    inv = ax.transData.inverted()

    # Convert display bboxes → data-unit centres and half-extents.
    # Use actual measured corners (not analytic) for accuracy.
    # Expand height by ~1.8× to account for the transliteration line drawn above.
    lbl_cx, lbl_cy = [], []   # label box centre (data units)
    lbl_hw, lbl_hh = [], []   # half-width / half-height (padded)

    for t, d in zip(texts, city_info):
        bb = t.get_window_extent(renderer=renderer)
        x0d, y0d = inv.transform((bb.x0, bb.y0))
        x1d, y1d = inv.transform((bb.x1, bb.y1))
        w  = abs(x1d - x0d)
        h  = abs(y1d - y0d)
        cx = (x0d + x1d) / 2
        cy = (y0d + y1d) / 2
        # Expand upward to cover the translit line (≈ 0.8 × main height + gap)
        combined_h = h * 1.85
        cy += (combined_h - h) / 2   # shift centre upward
        lbl_cx.append(cx);  lbl_cy.append(cy)
        lbl_hw.append(w / 2 * (1 + PAD))
        lbl_hh.append(combined_h / 2 * (1 + PAD))

    # ── Angular sweep: polar-coordinate placement ─────────────────────────────
    # For each label, sweep N_ANGLES directions (polar coords from city dot).
    # At each angle, use interval arithmetic on axis projections to compute the
    # exact minimum distance d needed so the label bbox clears every other label.
    # Score = d + angle_deviation_from_preferred × ANGLE_COST (in metres).
    # Repeat N_SWEEP rounds; each round updates positions greedily so subsequent
    # labels see already-improved placements.
    N_ANGLES     = 24                    # 15° resolution
    SWEEP_ANGLES = [i * 2 * np.pi / N_ANGLES for i in range(N_ANGLES)]
    BUF_ANG      = 12_000               # clearance gap appended after overlap (m)
    ANGLE_COST   = 80_000               # m-equivalent per radian of deviation
    MIN_DIST     = 35_000               # minimum label displacement from dot (m)
    N_SWEEP      = 8

    n = len(texts)
    pref_angles = [np.arctan2(d["clear_dir"][1], d["clear_dir"][0])
                   for d in city_info]

    def _clear_dist(dot_x, dot_y, hw_i, hh_i, angle, skip_i):
        """Min d ≥ 0 along angle so bbox(i) centred at dot+(d·cos,d·sin) clears all."""
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        intervals = []
        for j in range(n):
            if j == skip_i:
                continue
            HW = hw_i + lbl_hw[j]
            HH = hh_i + lbl_hh[j]
            Dx = lbl_cx[j] - dot_x
            Dy = lbl_cy[j] - dot_y
            # X projection: |d·cos_a − Dx| < HW
            if abs(cos_a) > 1e-9:
                lo_x, hi_x = sorted([(Dx - HW) / cos_a, (Dx + HW) / cos_a])
            elif abs(Dx) < HW:
                lo_x, hi_x = -1e15, 1e15
            else:
                continue
            # Y projection: |d·sin_a − Dy| < HH
            if abs(sin_a) > 1e-9:
                lo_y, hi_y = sorted([(Dy - HH) / sin_a, (Dy + HH) / sin_a])
            elif abs(Dy) < HH:
                lo_y, hi_y = -1e15, 1e15
            else:
                continue
            lo, hi = max(lo_x, lo_y), min(hi_x, hi_y)
            if lo < hi and hi > 0:
                intervals.append((max(0.0, lo), hi))
        if not intervals:
            return 0.0
        intervals.sort()
        d, pushed = 0.0, False
        for lo, hi in intervals:
            if lo > d + 1e-3:
                break
            if hi > d:
                d, pushed = hi, True
        return d + BUF_ANG if pushed else 0.0

    print(f"  angular sweep ({N_ANGLES} angles × {N_SWEEP} rounds) for {n} labels...")
    for sweep_round in range(N_SWEEP):
        total_moved = 0.0
        for i in range(n):
            dot_x, dot_y = city_info[i]["cx"], city_info[i]["cy"]
            pref_a       = pref_angles[i]
            best_score   = float("inf")
            best_cx, best_cy = lbl_cx[i], lbl_cy[i]
            for angle in SWEEP_ANGLES:
                dist = max(_clear_dist(dot_x, dot_y, lbl_hw[i], lbl_hh[i], angle, i),
                           MIN_DIST)
                cx_try = dot_x + dist * np.cos(angle)
                cy_try = dot_y + dist * np.sin(angle)
                if not (xmin + lbl_hw[i] <= cx_try <= xmax - lbl_hw[i] and
                        ymin + lbl_hh[i] <= cy_try <= ymax - lbl_hh[i]):
                    continue
                ang_dev = abs(np.arctan2(np.sin(angle - pref_a),
                                         np.cos(angle - pref_a)))
                score = dist + ang_dev * ANGLE_COST
                if score < best_score:
                    best_score = score
                    best_cx, best_cy = cx_try, cy_try
            old_cx, old_cy = lbl_cx[i], lbl_cy[i]
            lbl_cx[i], lbl_cy[i] = best_cx, best_cy
            total_moved += np.hypot(lbl_cx[i] - old_cx, lbl_cy[i] - old_cy)
        avg_km = total_moved / n / 1000
        print(f"    round {sweep_round + 1}: avg movement {avg_km:.1f} km")
        if avg_km < 0.5:
            print(f"  converged after {sweep_round + 1} rounds")
            break

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

        # Leader line: dot → nearest point on label bbox edge.
        # Skip if the dot is already touching or nearly touching the label.
        bx0, bx1 = lbl_cx[i] - hw, lbl_cx[i] + hw
        by0, by1 = lbl_cy[i] - hh, lbl_cy[i] + hh
        near_x = max(bx0, min(cx_dot, bx1))
        near_y = max(by0, min(cy_dot, by1))
        leader_len = np.hypot(near_x - cx_dot, near_y - cy_dot)
        if leader_len > 10_000:   # skip leader if dot is within ~10 km of label
            ax.plot([cx_dot, near_x], [cy_dot, near_y],
                    color=COL_LEADER, linewidth=0.75,
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
