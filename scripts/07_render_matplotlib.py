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
    """Return (main_pt, small_pt). Three tiers anchored at 1 M pop minimum."""
    if pop >= 10_000_000:
        main = 7
    elif pop >= 5_000_000:
        main = 6
    else:   # 1 M – 5 M
        main = 5
    return main, round(main * 0.75, 1)


def _best_split(text: str) -> str:
    """Split a multi-word string at the space nearest its character midpoint.

    Returns the original string unchanged if it has fewer than two words or
    no spaces.  The returned string contains a single '\\n' at the split point.
    """
    words = text.split()
    if len(words) < 2:
        return text
    mid = len(text) / 2
    pos, best_i, best_dist = 0, 1, float("inf")
    for i in range(1, len(words)):
        pos += len(words[i - 1]) + 1   # +1 for the space
        dist = abs(pos - mid)
        if dist < best_dist:
            best_dist, best_i = dist, i
    return " ".join(words[:best_i]) + "\n" + " ".join(words[best_i:])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dpi",  type=int,   default=200)
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

    # ── City labels — discrete candidate-position greedy placement ───────────
    # Imhof (1975) / PAL-style algorithm:
    # 1. Spatial thinning: suppress weaker city within THIN_M radius.
    # 2. Cluster detection (union-find at CLUSTER_R): each label gets a clear
    #    direction pointing away from its cluster centroid; singletons use the
    #    sparsest 45° density sector.
    # 3. Measure label bboxes by rendering invisible placeholder texts.
    # 4. Greedy placement in priority order (population desc):
    #    • generate N_ANG angles × len(C_MULTS) clearance rings per dot
    #    • score: overlap count + leader-crosses-label + distance + dir deviation
    #    • pick lowest-score candidate; record bbox as occupied
    # 5. Draw: city dot → leader (only when displaced > LEADER_MIN) → label.

    THIN_M     = 50_000    # thinning radius (m)
    CLUSTER_R  = 150_000   # cluster radius for clear-direction (m)
    PAD        = 0.05      # fractional padding on measured half-extents
    DOT_GAP    = 5_000     # clearance: dot centre → label-bbox near edge (m)
    LEADER_MIN = 10_000    # draw leader only when dot→bbox-edge exceeds this (m)
    MAX_LEADER = 500_000   # revert to natural pos if leader would exceed this (m)
    WRAP_THRESH_M = 200_000  # wrap translation to two lines if single-line width exceeds this (m)
    N_ANG      = 24        # candidate angles (every 15° around dot)
    C_MULTS    = [1.0, 1.8, 3.0, 5.0]   # clearance multipliers: r = k×r_edge(θ)+DOT_GAP

    # Scoring weights (all additive; lower = better)
    W_OVERLAP  = 500.0   # per overlapping placed label
    W_CROSS    = 60.0    # per leader segment that crosses a placed label bbox
    W_DIST     = 8.0     # per unit of C_MULTS (strongly prefer adjacent slot)
    W_DIR      = 4.0     # per π-radian deviation from preferred clear direction
    W_AMBIG    = 300.0   # per other city dot closer to this label than own dot is

    buf = [pe.withStroke(linewidth=1.5, foreground=BG)]

    # ── Stage 1: spatial thinning ─────────────────────────────────────────────
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

    # ── Stage 2: preferred direction (centrifugal from cluster centroid) ──────
    from collections import defaultdict
    geom_list = [(row.geometry.x, row.geometry.y)
                 for _, row in cities_thin.iterrows()]
    m = len(geom_list)

    parent = list(range(m))
    def _find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]; v = parent[v]
        return v
    for i in range(m):
        for j in range(i + 1, m):
            if np.hypot(geom_list[i][0] - geom_list[j][0],
                        geom_list[i][1] - geom_list[j][1]) < CLUSTER_R:
                ri, rj = _find(i), _find(j)
                if ri != rj:
                    parent[ri] = rj

    _cluster_members = defaultdict(list)
    for i in range(m):
        _cluster_members[_find(i)].append(i)
    _cluster_centroid = {
        root: (np.mean([geom_list[k][0] for k in mems]),
               np.mean([geom_list[k][1] for k in mems]))
        for root, mems in _cluster_members.items()
    }

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
        # Singleton or at centroid: sparsest density sector
        counts = np.zeros(N_SECTORS)
        for j, (xj, yj) in enumerate(geom_list):
            if j == i:
                continue
            d_ij = np.hypot(xj - xi, yj - yi)
            if d_ij < SECTOR_R:
                ang = np.arctan2(yj - yi, xj - xi) % (2 * np.pi)
                sec = int(ang / (2 * np.pi) * N_SECTORS) % N_SECTORS
                counts[sec] += 1.0 - d_ij / SECTOR_R
        best_sec = int(np.argmin(counts))
        clear_dirs.append((np.cos(SECTOR_ANG[best_sec]),
                           np.sin(SECTOR_ANG[best_sec])))

    # ── Stage 3: collect label metadata ───────────────────────────────────────
    city_info = []
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
        city_info.append({
            "cx": x, "cy": y, "pop": pop,
            "sz_main": sz_main, "sz_small": sz_small,
            "translation": translation, "translit": translit,
            "clear_dir": clear_dirs[idx],
            "bold": pop >= 5_000_000,
        })
    print(f"  label candidates: {len(city_info)}")

    # ── Stage 4: measure bboxes (with optional two-line wrapping) ────────────
    # Pass A: render single-line translations and draw once so matplotlib
    # sets internal renderers (invisible texts return near-zero bboxes).
    temp_texts = []
    for d in city_info:
        t = ax.text(d["cx"], d["cy"], d["translation"],
                    fontsize=d["sz_main"], color=COL_LABEL,
                    fontweight="bold" if d["bold"] else "normal",
                    ha="left", va="bottom",
                    path_effects=buf, zorder=9)
        temp_texts.append(t)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    # Pass B: wrap any translation whose single-line width exceeds WRAP_THRESH_M.
    # Using \n in the text string halves the horizontal footprint at the cost
    # of a taller bbox — a good trade in dense label clusters.
    wrapped_any = False
    for t, d in zip(temp_texts, city_info):
        bb = t.get_window_extent(renderer=renderer)
        x0d, _ = inv.transform((bb.x0, bb.y0))
        x1d, _ = inv.transform((bb.x1, bb.y1))
        w = abs(x1d - x0d)
        if w > WRAP_THRESH_M and " " in d["translation"]:
            wrapped = _best_split(d["translation"])
            if "\n" in wrapped:
                d["translation"] = wrapped
                t.set_text(wrapped)
                wrapped_any = True

    if wrapped_any:
        fig.canvas.draw()   # one extra draw to update extents for wrapped texts
    n_wrapped = sum(1 for d in city_info if "\n" in d["translation"])
    if n_wrapped:
        print(f"  wrapped {n_wrapped} wide labels to two lines")

    # Pass C: final bbox measurement for all labels.
    label_hw = []   # padded half-width in data units
    label_hh = []   # padded combined half-height (main + translit line)
    for t, d in zip(temp_texts, city_info):
        bb = t.get_window_extent(renderer=renderer)
        x0d, y0d = inv.transform((bb.x0, bb.y0))
        x1d, y1d = inv.transform((bb.x1, bb.y1))
        w = abs(x1d - x0d)
        h = abs(y1d - y0d)
        # For single-line labels multiply by 1.85 to cover the transliteration
        # line above.  For two-line labels the measured height already spans
        # two lines, so a smaller factor (1.35) is enough.
        h_factor = 1.35 if "\n" in d["translation"] else 1.85
        label_hw.append(w / 2 * (1 + PAD))
        label_hh.append(h * h_factor / 2 * (1 + PAD))

    for t in temp_texts:
        t.remove()

    # ── Stage 5: greedy candidate-position placement ──────────────────────────
    def _seg_clips_box(x1, y1, x2, y2, bx0, by0, bx1, by1):
        """Liang-Barsky: True if segment (x1,y1)→(x2,y2) intersects AABB."""
        dx, dy = x2 - x1, y2 - y1
        tmin, tmax = 0.0, 1.0
        for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1),
                     (-dy, y1 - by0), (dy, by1 - y1)):
            if abs(p) < 1e-12:
                if q < 0:
                    return False
            elif p < 0:
                tval = q / p
                if tval > tmin:
                    tmin = tval
            else:
                tval = q / p
                if tval < tmax:
                    tmax = tval
            if tmin > tmax:
                return False
        return True

    ANGLES  = [k * 2 * np.pi / N_ANG for k in range(N_ANG)]

    # All dot positions for ambiguity constraint (built once, used in closure).
    all_dots = [(d["cx"], d["cy"]) for d in city_info]

    def _best_candidate(hw, hh, dot_x, dot_y, pref_angle, other_placed, dot_idx=None):
        """Return (best_cx, best_cy, best_score) over all C_MULTS × ANGLES.

        dot_idx: index of this label in all_dots (excluded from ambiguity check).
        Ambiguity rule: no other city's dot may be closer to this label bbox
        than the label's own dot is — ensures unambiguous dot-label association.
        """
        hw_u = hw / (1 + PAD)   # unpadded half-extents for r_edge computation
        hh_u = hh / (1 + PAD)
        best_score = float("inf")
        best_cx = best_cy = None
        for k_mult in C_MULTS:
            for angle in ANGLES:
                cos_a, sin_a = np.cos(angle), np.sin(angle)
                # Distance from bbox centre to its edge in direction (cos_a, sin_a).
                # At k_mult=1 the near edge lands exactly DOT_GAP from the dot
                # regardless of angle — no leader needed.
                r_edge = min(hw_u / max(abs(cos_a), 1e-10),
                             hh_u / max(abs(sin_a), 1e-10))
                r  = k_mult * r_edge + DOT_GAP
                cx = dot_x + r * cos_a
                cy = dot_y + r * sin_a

                if not (xmin + hw < cx < xmax - hw and
                        ymin + hh < cy < ymax - hh):
                    continue

                overlap_pen = sum(
                    1.0 for (px, py, phw, phh) in other_placed
                    if abs(cx - px) < hw + phw and abs(cy - py) < hh + phh
                )

                near_x = max(cx - hw, min(dot_x, cx + hw))
                near_y = max(cy - hh, min(dot_y, cy + hh))
                leader_len = np.hypot(near_x - dot_x, near_y - dot_y)

                cross_pen = 0.0
                if leader_len > LEADER_MIN:
                    for (px, py, phw, phh) in other_placed:
                        if _seg_clips_box(dot_x, dot_y, near_x, near_y,
                                          px - phw, py - phh,
                                          px + phw, py + phh):
                            cross_pen += 1.0

                # Ambiguity: count other dots closer to this label bbox than
                # the label's own dot is. Each such dot makes the label
                # visually ambiguous — heavily penalise.
                ambiguity_pen = 0.0
                for j, (ox, oy) in enumerate(all_dots):
                    if j == dot_idx:
                        continue
                    bx = max(cx - hw, min(ox, cx + hw))
                    by = max(cy - hh, min(oy, cy + hh))
                    if np.hypot(bx - ox, by - oy) < leader_len:
                        ambiguity_pen += 1.0

                ang_diff = abs(((angle - pref_angle + np.pi) % (2 * np.pi)) - np.pi)
                dir_pen  = ang_diff / np.pi

                score = (overlap_pen    * W_OVERLAP
                         + cross_pen   * W_CROSS
                         + k_mult      * W_DIST
                         + dir_pen     * W_DIR
                         + ambiguity_pen * W_AMBIG)

                if score < best_score:
                    best_score = score
                    best_cx, best_cy = cx, cy
        return best_cx, best_cy, best_score

    # ── Natural placement (k_mult=1.0, preferred direction, no avoidance) ────────
    def _natural_pos(hw, hh, dot_x, dot_y, pref_angle):
        """Place label at k_mult=1.0 in preferred direction.
        Tries angles in order of deviation from preferred; falls back to
        k_mult=1.8 if every k_mult=1.0 slot is out-of-bounds."""
        hw_u = hw / (1 + PAD)
        hh_u = hh / (1 + PAD)
        angles_by_pref = sorted(ANGLES,
            key=lambda a: abs(((a - pref_angle + np.pi) % (2 * np.pi)) - np.pi))
        for k_mult in [1.0, 1.8]:
            for angle in angles_by_pref:
                cos_a, sin_a = np.cos(angle), np.sin(angle)
                r_edge = min(hw_u / max(abs(cos_a), 1e-10),
                             hh_u / max(abs(sin_a), 1e-10))
                r  = k_mult * r_edge + DOT_GAP
                cx = dot_x + r * cos_a
                cy = dot_y + r * sin_a
                if xmin + hw < cx < xmax - hw and ymin + hh < cy < ymax - hh:
                    return cx, cy
        return dot_x, dot_y   # last resort

    placed  = []   # (cx, cy, hw, hh)  — parallel to city_info / results
    results = []   # (cx, cy, hw, hh, d)

    for i, d in enumerate(city_info):
        hw = label_hw[i]
        hh = label_hh[i]
        pref_angle = np.arctan2(d["clear_dir"][1], d["clear_dir"][0])
        cx, cy = _natural_pos(hw, hh, d["cx"], d["cy"], pref_angle)
        placed.append((cx, cy, hw, hh))
        results.append((cx, cy, hw, hh, d))

    # ── Conflict detection: BFS connected components of overlapping labels ─────
    n = len(results)
    adj = [[] for _ in range(n)]
    for i in range(n):
        cx1, cy1, hw1, hh1 = placed[i]
        for j in range(i + 1, n):
            cx2, cy2, hw2, hh2 = placed[j]
            if abs(cx1 - cx2) < hw1 + hw2 and abs(cy1 - cy2) < hh1 + hh2:
                adj[i].append(j)
                adj[j].append(i)

    visited  = [False] * n
    groups   = []          # list of sorted index lists (conflicted)
    isolated = set()       # indices with no conflicts at natural position

    for start in range(n):
        if visited[start]:
            continue
        visited[start] = True
        if not adj[start]:
            isolated.add(start)
            continue
        group, queue = [], [start]
        while queue:
            node = queue.pop(0)
            group.append(node)
            for nb in adj[node]:
                if not visited[nb]:
                    visited[nb] = True
                    queue.append(nb)
        groups.append(group)

    conflicted = {i for g in groups for i in g}

    # ── Report conflict groups ─────────────────────────────────────────────────
    print(f"\n  Natural placement: {len(isolated)} isolated  |  "
          f"{len(groups)} conflict groups  |  {len(conflicted)} conflicted labels")
    for g_idx, group in enumerate(sorted(groups, key=len, reverse=True)):
        names = [results[i][4]["translation"] for i in
                 sorted(group, key=lambda i: -results[i][4]["pop"])]
        print(f"  group {g_idx + 1:2d} ({len(group):2d}): {', '.join(names)}")

    # ── Resolve only conflicted labels (isolated labels are immovable) ─────────
    # Multiple rounds of Gauss-Seidel: remove label i from placed, find best
    # candidate against all others (including immovable isolated labels), accept
    # if it reduces overlap or leader length.
    RESOLVE_ITER = 30
    print(f"\n  Resolving {len(conflicted)} conflicted labels "
          f"({RESOLVE_ITER} max rounds)...")
    for round_num in range(RESOLVE_ITER):
        improved = 0
        # Process in population order (big cities first) so they claim best slots
        priority = sorted(conflicted, key=lambda i: -results[i][4]["pop"])
        for i in priority:
            cx_cur, cy_cur, hw, hh, d = results[i]
            others = [placed[j] for j in range(n) if j != i]
            dot_x, dot_y = d["cx"], d["cy"]
            pref_angle = np.arctan2(d["clear_dir"][1], d["clear_dir"][0])

            best_cx, best_cy, best_score = _best_candidate(
                hw, hh, dot_x, dot_y, pref_angle, others, dot_idx=i)

            if best_cx is None:
                best_cx, best_cy = dot_x, dot_y

            if best_cx != cx_cur or best_cy != cy_cur:
                results[i] = (best_cx, best_cy, hw, hh, d)
                placed[i]  = (best_cx, best_cy, hw, hh)
                improved  += 1

        if improved == 0:
            print(f"    converged after {round_num + 1} rounds")
            break
    else:
        print(f"    did not converge after {RESOLVE_ITER} rounds")

    # ── Post-process: revert outlier leaders to natural position ──────────────
    # A label whose leader would be > MAX_LEADER is reverted so that no single
    # line is an extreme outlier compared to the rest.  We accept the overlap
    # rather than showing a 10× longer leader than every other city.
    reverted = 0
    for i in range(n):
        cx, cy, hw, hh, d = results[i]
        nx = max(cx - hw, min(d["cx"], cx + hw))
        ny = max(cy - hh, min(d["cy"], cy + hh))
        llen = np.hypot(nx - d["cx"], ny - d["cy"])
        if llen > MAX_LEADER:
            pref_angle = np.arctan2(d["clear_dir"][1], d["clear_dir"][0])
            nat_cx, nat_cy = _natural_pos(hw, hh, d["cx"], d["cy"], pref_angle)
            results[i] = (nat_cx, nat_cy, hw, hh, d)
            placed[i]  = (nat_cx, nat_cy, hw, hh)
            reverted  += 1
    if reverted:
        print(f"  reverted {reverted} outlier-leader labels to natural position")

    # ── Placement summary ──────────────────────────────────────────────────────
    with_leaders = []
    for cx, cy, hw, hh, d in results:
        nx = max(cx - hw, min(d["cx"], cx + hw))
        ny = max(cy - hh, min(d["cy"], cy + hh))
        llen = np.hypot(nx - d["cx"], ny - d["cy"])
        if llen > LEADER_MIN:
            with_leaders.append((llen / 1000, d["translation"]))
    with_leaders.sort(reverse=True)
    print(f"  labels with leader lines: {len(with_leaders)}")
    for llen_km, name in with_leaders:
        print(f"    {name}: {llen_km:.0f} km")

    # ── Stage 6: draw dots, leaders, labels, transliterations ─────────────────
    renderer = fig.canvas.get_renderer()

    for cx, cy, hw, hh, d in results:
        hw_a = hw / (1 + PAD)   # unpadded half-extents for text anchor
        hh_a = hh / (1 + PAD)
        dot_x, dot_y = d["cx"], d["cy"]

        # City dot
        dot_sz = 3.0 if d["pop"] >= 1_000_000 else 1.8
        ax.plot(dot_x, dot_y, "o",
                markersize=dot_sz, color=COL_DOT,
                markeredgecolor="#ffffff", markeredgewidth=0.35, zorder=8)

        # Leader line (only when label is genuinely displaced from dot)
        near_x = max(cx - hw, min(dot_x, cx + hw))
        near_y = max(cy - hh, min(dot_y, cy + hh))
        leader_len = np.hypot(near_x - dot_x, near_y - dot_y)
        if leader_len > LEADER_MIN:
            ax.plot([dot_x, near_x], [dot_y, near_y],
                    color=COL_LEADER, linewidth=0.75,
                    solid_capstyle="round", zorder=7)

        # Text anchor position
        ha = "left" if cx >= dot_x else "right"
        tx = cx - hw_a if ha == "left" else cx + hw_a
        ty = cy - hh_a   # va = "bottom"

        # Main translation label
        t = ax.text(tx, ty, d["translation"],
                    fontsize=d["sz_main"], color=COL_LABEL,
                    fontweight="bold" if d["bold"] else "normal",
                    ha=ha, va="bottom",
                    path_effects=buf, zorder=9)

        # Transliteration line above main label
        if d["translit"] and d["translit"] != d["translation"]:
            bb = t.get_window_extent(renderer=renderer)
            _, y_top = inv.transform((bb.x0, bb.y1))
            ax.text(tx, y_top, d["translit"],
                    fontsize=d["sz_small"], color=COL_LABEL_SMALL,
                    ha=ha, va="bottom",
                    path_effects=buf, zorder=9)

    print(f"  labels drawn: {len(results)}")

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"Rendering → {out_path}  ({args.dpi} dpi)")
    plt.savefig(out_path, dpi=args.dpi, bbox_inches="tight",
                facecolor=BG, format="png")
    plt.close()
    print("Done.")


if __name__ == "__main__":
    main()
