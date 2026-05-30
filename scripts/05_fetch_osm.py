"""
Input:  config/aoi.geojson, config/osm_layers.yaml
Output: data/01_raw/osm/<layer>.gpkg (merged), data/01_raw/osm/_tiles/<layer>/*.gpkg (cache)
Purpose: Fetch OSM layers from Overpass using a stable global grid + per-tile cache.

Design (ported from dual_carriageways/fetch_roads.py):
  * Tiles live on a GLOBAL grid with origin (-180, -90). IDs are stable across
    runs and projects — a 1° tile at (24°N, 110°E) is always N24p00_E110p00.
    If you fetch the same tile in another project, you can reuse it.
  * Per-layer cache at data/01_raw/osm/_tiles/<layer>/<tile_id>.gpkg.
    A `<tile_id>.empty` sidecar marks "fetched, no features".
  * Multi-server rotation: overpass-api.de (with /status slot checker), kumi,
    fr. Bad servers (403 / non-JSON) blacklisted for the session.
  * Adaptive subdivision: on query_timeout the tile is split 2x2 and retried.
    Max depth = 2 (so worst-case 16 sub-queries per parent tile).
"""

import argparse
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import yaml
from shapely.geometry import (LineString, MultiLineString, MultiPolygon, Point,
                              Polygon, box as shapely_box)

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "01_raw" / "osm"
TILE_CACHE_ROOT = OUT_DIR / "_tiles"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TILE_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_TILE_SIZE_DEG = 1.0
MAX_SUBDIVISION_DEPTH = 2
MAX_BLOCK_SIDE = 8   # max side length (in tiles) of a rectangular fetch block
MAX_BLOCK_TILES = 32  # max total tiles per block query
PER_TILE_SLEEP = 1.0  # seconds between tile requests (politeness)

# Server rotation. Primary: overpass-api.de (slot checker supported, most capable).
# Fallbacks: kumi and French mirror. Add more if needed.
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
]


# -----------------------------------------------------------------------------
# Geometry parsing (ported from Warsaw fetcher)
# -----------------------------------------------------------------------------

def join_ways(ways):
    """Join way segments into closed rings. Bridges gaps with straight lines."""
    if not ways:
        return []
    if len(ways) == 1:
        coords = list(ways[0])
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return [coords]

    segments = [list(c) for c in ways if len(c) >= 2]
    if not segments:
        return []

    rings = []
    used = set()
    for start in range(len(segments)):
        if start in used:
            continue
        ring = list(segments[start])
        used.add(start)
        for _ in range(len(segments) * 2):
            if ((ring[0][0] - ring[-1][0]) ** 2 +
                    (ring[0][1] - ring[-1][1]) ** 2) ** 0.5 < 1e-5:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                rings.append(ring)
                break
            best_idx, best_dist, reverse = None, float("inf"), False
            for idx in range(len(segments)):
                if idx in used:
                    continue
                s = segments[idx]
                d_start = ((s[0][0] - ring[-1][0]) ** 2 +
                           (s[0][1] - ring[-1][1]) ** 2) ** 0.5
                d_end = ((s[-1][0] - ring[-1][0]) ** 2 +
                         (s[-1][1] - ring[-1][1]) ** 2) ** 0.5
                if d_start < best_dist:
                    best_dist, best_idx, reverse = d_start, idx, False
                if d_end < best_dist:
                    best_dist, best_idx, reverse = d_end, idx, True
            if best_idx is None:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                if len(ring) >= 4:
                    rings.append(ring)
                break
            seg = segments[best_idx]
            if reverse:
                seg = list(reversed(seg))
            ring.extend(seg[1:] if best_dist < 1e-5 else seg)
            used.add(best_idx)
    return rings


def parse_geometry(element):
    """OSM element → Shapely geometry (or None)."""
    etype = element.get("type")

    if etype == "node" and "lat" in element and "lon" in element:
        return Point(element["lon"], element["lat"])

    if etype == "way" and "geometry" in element:
        coords = [(n["lon"], n["lat"]) for n in element["geometry"]]
        if len(coords) < 2:
            return None
        if coords[0] == coords[-1] and len(coords) > 3:
            try:
                return Polygon(coords)
            except Exception:
                return LineString(coords)
        return LineString(coords)

    if etype == "relation" and "members" in element:
        outer, inner, lines = [], [], []
        for m in element["members"]:
            if "geometry" not in m or m.get("type") != "way":
                continue
            coords = [(n["lon"], n["lat"]) for n in m["geometry"]]
            if len(coords) < 2:
                continue
            role = m.get("role", "")
            if role == "outer":
                outer.append(coords)
            elif role == "inner":
                inner.append(coords)
            else:
                lines.append(coords)

        if outer:
            try:
                outer_rings = join_ways(outer)
                inner_rings = join_ways(inner) if inner else []
                if not outer_rings:
                    return None
                if len(outer_rings) == 1:
                    return Polygon(outer_rings[0], inner_rings or None)
                polys = []
                for ring in outer_rings:
                    try:
                        op = Polygon(ring)
                        holes = []
                        for ir in inner_rings:
                            try:
                                if op.contains(Polygon(ir)):
                                    holes.append(ir)
                            except Exception:
                                pass
                        polys.append(Polygon(ring, holes or None))
                    except Exception:
                        continue
                if not polys:
                    return None
                return polys[0] if len(polys) == 1 else MultiPolygon(polys)
            except Exception:
                return None
        if lines:
            try:
                ls = [LineString(c) for c in lines if len(c) > 1]
                return MultiLineString(ls) if ls else None
            except Exception:
                return None
    return None


# -----------------------------------------------------------------------------
# Overpass fetch
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Overpass client with server rotation + slot checking
# (pattern borrowed from dual_carriageways/fetch_roads.py)
# -----------------------------------------------------------------------------

_server_idx = 0
_bad_servers = set()


def _next_server():
    """Round-robin across working servers."""
    global _server_idx
    available = [s for s in OVERPASS_SERVERS if s not in _bad_servers]
    if not available:
        _bad_servers.clear()
        available = OVERPASS_SERVERS
    url = available[_server_idx % len(available)]
    _server_idx += 1
    return url


def _wait_for_slot(server_url):
    """Check overpass-api.de /status; sleep the reported wait. No-op for others."""
    if "overpass-api.de" not in server_url:
        return 0.0
    status_url = server_url.replace("/interpreter", "/status")
    try:
        resp = requests.get(status_url, timeout=10)
        text = resp.text
        if "available now" in text.lower():
            return 0.0
        m = re.search(r"in (\d+) seconds", text)
        if m:
            wait = int(m.group(1)) + 1
            print(f"slot wait {wait}s...", end=" ", flush=True)
            time.sleep(wait)
            return float(wait)
    except Exception:
        pass
    return 0.0


def query_overpass(query: str, columns=None, retries=None, delay=3):
    """Rotate servers, wait for slots, retry on failure.

    Returns (gdf, status) where status is one of:
      "ok"      — non-empty GeoDataFrame returned
      "empty"   — successful fetch, zero features (empty GeoDataFrame)
      "timeout" — query_timeout or repeated 504; caller should subdivide
      "fail"    — other failures; caller should retry later
    """
    if retries is None:
        retries = max(6, len(OVERPASS_SERVERS) * 3)

    saw_timeout = False

    for attempt in range(retries):
        url = _next_server()
        _wait_for_slot(url)
        host = url.split("/")[2]

        try:
            r = requests.post(url, data={"data": query}, timeout=90)

            if r.status_code == 403:
                _bad_servers.add(url)
                print(f"403@{host}(blk)", end=" ", flush=True)
                continue
            if r.status_code == 429:
                print(f"429@{host}", end=" ", flush=True)
                time.sleep(delay * 2)
                continue
            if r.status_code == 406:
                # Overpass out-of-memory for this query — treat as timeout to trigger block splitting
                saw_timeout = True
                print(f"406(oom)@{host}", end=" ", flush=True)
                time.sleep(delay)
                continue
            if r.status_code == 504:
                saw_timeout = True
                print(f"504@{host}", end=" ", flush=True)
                time.sleep(delay)
                continue
            if r.status_code in (500, 502, 503):
                print(f"{r.status_code}@{host}", end=" ", flush=True)
                time.sleep(delay)
                continue
            if r.status_code != 200:
                print(f"HTTP{r.status_code}@{host}", end=" ", flush=True)
                time.sleep(delay)
                continue

            ct = r.headers.get("Content-Type", "")
            if "json" not in ct and "javascript" not in ct:
                _bad_servers.add(url)
                print(f"non-JSON@{host}(blk)", end=" ", flush=True)
                continue

            try:
                data = r.json()
            except ValueError:
                print(f"bad-JSON@{host}", end=" ", flush=True)
                time.sleep(delay)
                continue

            remark = data.get("remark", "")
            if remark and "timed out" in remark.lower():
                saw_timeout = True
                print(f"qry-timeout@{host}", end=" ", flush=True)
                continue

            geoms, props = [], []
            for el in data.get("elements", []):
                g = parse_geometry(el)
                if g is None:
                    continue
                tags = el.get("tags", {})
                if columns:
                    row = {c: tags.get(c) for c in columns}
                else:
                    row = dict(tags)
                row["osm_id"] = el.get("id")
                row["osm_type"] = el.get("type")
                geoms.append(g)
                props.append(row)

            if not geoms:
                return (
                    gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
                    "empty",
                )
            return (
                gpd.GeoDataFrame(props, geometry=geoms, crs="EPSG:4326"),
                "ok",
            )

        except requests.exceptions.Timeout:
            saw_timeout = True
            print(f"timeout@{host}", end=" ", flush=True)
            time.sleep(delay)
        except Exception as e:
            print(f"err@{host}:{str(e)[:30]}", end=" ", flush=True)
            time.sleep(delay)

    return (None, "timeout" if saw_timeout else "fail")


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------

def aoi_from_project(project_cfg: dict) -> dict:
    """Return {south, west, north, east} from a loaded project.yaml dict."""
    aoi = project_cfg["aoi"]
    return {k: float(aoi[k]) for k in ("south", "west", "north", "east")}


def bbox_to_overpass(b) -> str:
    """dict → 'south,west,north,east' string for Overpass."""
    return f"{b['south']:.6f},{b['west']:.6f},{b['north']:.6f},{b['east']:.6f}"


# -----------------------------------------------------------------------------
# Global grid — stable tile IDs across runs and projects
# -----------------------------------------------------------------------------

def tile_id(sw_lat: float, sw_lon: float, tile_size: float) -> str:
    """Stable filename-safe ID for a grid tile. Examples:
       sz1p00_N24p00_E110p00  (1° tile, SW corner at 24N 110E)
       sz0p50_S02p50_W034p00
    """
    def fmt_lat(v):
        return f"{'N' if v >= 0 else 'S'}{abs(v):05.2f}".replace(".", "p")
    def fmt_lon(v):
        return f"{'E' if v >= 0 else 'W'}{abs(v):06.2f}".replace(".", "p")
    sz = f"{tile_size:04.2f}".replace(".", "p")
    return f"sz{sz}_{fmt_lat(sw_lat)}_{fmt_lon(sw_lon)}"


def global_grid_tiles(aoi_bbox, tile_size: float):
    """Enumerate global-grid tiles that intersect the AOI bbox.
    Grid aligned to integer multiples of tile_size from (-180, -90).
    Returns list of dicts: {south, west, north, east, id}.
    """
    # Snap AOI to grid edges (outward).
    west = math.floor(aoi_bbox["west"] / tile_size) * tile_size
    east = math.ceil(aoi_bbox["east"] / tile_size) * tile_size
    south = math.floor(aoi_bbox["south"] / tile_size) * tile_size
    north = math.ceil(aoi_bbox["north"] / tile_size) * tile_size

    tiles = []
    lat = south
    while lat < north - 1e-9:
        lon = west
        while lon < east - 1e-9:
            tiles.append({
                "south": round(lat, 6),
                "west": round(lon, 6),
                "north": round(lat + tile_size, 6),
                "east": round(lon + tile_size, 6),
                "id": tile_id(lat, lon, tile_size),
            })
            lon += tile_size
        lat += tile_size
    return tiles


def split_tile(tile):
    """Split a tile into 2x2 sub-tiles (no global-grid alignment)."""
    mid_lat = (tile["south"] + tile["north"]) / 2
    mid_lon = (tile["west"] + tile["east"]) / 2
    return [
        {"south": tile["south"], "west": tile["west"],  "north": mid_lat,        "east": mid_lon},
        {"south": tile["south"], "west": mid_lon,       "north": mid_lat,        "east": tile["east"]},
        {"south": mid_lat,       "west": tile["west"],  "north": tile["north"],  "east": mid_lon},
        {"south": mid_lat,       "west": mid_lon,       "north": tile["north"],  "east": tile["east"]},
    ]


# -----------------------------------------------------------------------------
# Per-tile fetch with adaptive subdivision
# -----------------------------------------------------------------------------

def fetch_tile_recursive(spec, tile, cols, depth=0):
    """Fetch one tile. On query_timeout, split 2x2 and recurse.
    Returns (gdf or None, status).
    """
    query = spec["query"].format(bbox=bbox_to_overpass(tile))
    gdf, status = query_overpass(query, columns=cols)

    if status in ("ok", "empty"):
        return gdf, status

    if status == "timeout" and depth < MAX_SUBDIVISION_DEPTH:
        print(f"[split d{depth + 1}]", end=" ", flush=True)
        parts = []
        any_fail = False
        for sub in split_tile(tile):
            g, s = fetch_tile_recursive(spec, sub, cols, depth + 1)
            if s == "ok" and g is not None and not g.empty:
                parts.append(g)
            elif s == "fail" or (s == "timeout" and depth + 1 >= MAX_SUBDIVISION_DEPTH):
                any_fail = True
        if parts:
            merged = gpd.GeoDataFrame(
                pd.concat(parts, ignore_index=True),
                geometry="geometry",
                crs="EPSG:4326",
            )
            return merged, "ok"
        if any_fail:
            return None, "fail"
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), "empty"

    return None, status  # fail or max-depth timeout


# -----------------------------------------------------------------------------
# Block batching — group adjacent uncached tiles into rectangles for fewer queries
# -----------------------------------------------------------------------------

def _form_blocks(tiles, tile_size):
    """Group tiles into rectangular blocks so each block gets one Overpass query.
    Returns a list of blocks; each block is a list of tile dicts.
    """
    pos_map = {}
    for tile in tiles:
        i = round(tile["south"] / tile_size)
        j = round(tile["west"] / tile_size)
        pos_map[(i, j)] = tile

    remaining = set(pos_map.keys())
    groups = []

    # Try largest rectangles first (greedy)
    shapes = sorted(
        [(w, h) for w in range(1, MAX_BLOCK_SIDE + 1)
         for h in range(1, MAX_BLOCK_SIDE + 1) if 2 <= w * h <= MAX_BLOCK_TILES],
        key=lambda wh: wh[0] * wh[1],
        reverse=True,
    )
    for w, h in shapes:
        for pos in sorted(remaining):
            if pos not in remaining:
                continue
            i, j = pos
            block_pos = [(i + di, j + dj) for di in range(w) for dj in range(h)]
            if all(p in remaining for p in block_pos):
                groups.append([pos_map[p] for p in block_pos])
                remaining -= set(block_pos)

    for pos in sorted(remaining):
        groups.append([pos_map[pos]])

    return groups


def _block_bbox(tiles):
    """Bounding box covering all tiles in a block."""
    return {
        "south": min(t["south"] for t in tiles),
        "west":  min(t["west"]  for t in tiles),
        "north": max(t["north"] for t in tiles),
        "east":  max(t["east"]  for t in tiles),
    }


def _clip_to_tile(gdf, tile):
    """Return rows whose geometry intersects the tile bbox."""
    tile_box = shapely_box(tile["west"], tile["south"], tile["east"], tile["north"])
    return gdf[gdf.geometry.intersects(tile_box)].copy()


def fetch_block_recursive(spec, tiles, cols, depth=0):
    """Fetch a block of tiles with a single bbox query.
    On timeout: split block in half and recurse.
    At single tile: delegate to fetch_tile_recursive (2×2 subdivision).
    Returns list of (tile_dict, gdf_or_None, status_str).
    """
    if len(tiles) == 1:
        gdf, status = fetch_tile_recursive(spec, tiles[0], cols, depth=0)
        return [(tiles[0], gdf, status)]

    bbox = _block_bbox(tiles)
    query = spec["query"].format(bbox=bbox_to_overpass(bbox))
    # Fail fast on block queries (2 attempts) so we split quickly on OOM/timeout.
    # Full retries are reserved for single-tile fetches in fetch_tile_recursive.
    gdf, status = query_overpass(query, columns=cols, retries=2)

    if status == "ok" and gdf is not None and not gdf.empty:
        results = []
        for tile in tiles:
            tile_gdf = _clip_to_tile(gdf, tile)
            results.append((
                tile,
                tile_gdf if not tile_gdf.empty else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"),
                "ok" if not tile_gdf.empty else "empty",
            ))
        return results

    if status == "empty":
        return [(tile, gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), "empty")
                for tile in tiles]

    if status == "timeout":
        mid = len(tiles) // 2
        print(f"[block-split {len(tiles)}→{mid}+{len(tiles) - mid}]", end=" ", flush=True)
        results = []
        results.extend(fetch_block_recursive(spec, tiles[:mid], cols, depth))
        results.extend(fetch_block_recursive(spec, tiles[mid:], cols, depth))
        return results

    # fail
    return [(tile, None, "fail") for tile in tiles]


# -----------------------------------------------------------------------------
# Layer driver — walks the global grid, caches per tile, merges at the end
# -----------------------------------------------------------------------------

def fetch_layer(name, spec, aoi_bbox):
    """Iterate global-grid tiles, use per-tile cache, return merged GeoDataFrame."""
    tile_size = float(spec.get("tile_size_deg", DEFAULT_TILE_SIZE_DEG))
    tiles = global_grid_tiles(aoi_bbox, tile_size)
    tile_dir = TILE_CACHE_ROOT / name
    tile_dir.mkdir(parents=True, exist_ok=True)

    cols = spec.get("columns")
    parts = []
    fails = 0
    uncached = []

    # ── Load cached tiles ────────────────────────────────────────────────────
    for idx, tile in enumerate(tiles, 1):
        tid = tile["id"]
        cache_gpkg = tile_dir / f"{tid}.gpkg"
        cache_empty = tile_dir / f"{tid}.empty"

        if cache_gpkg.exists():
            try:
                gdf = gpd.read_file(cache_gpkg)
                if not gdf.empty:
                    parts.append(gdf)
                print(f"  [{idx:>3}/{len(tiles)}] {tid} ⊙ cached ({len(gdf)})")
                continue
            except Exception:
                cache_gpkg.unlink(missing_ok=True)

        if cache_empty.exists():
            print(f"  [{idx:>3}/{len(tiles)}] {tid} ⊙ empty")
            continue

        uncached.append(tile)

    if not uncached:
        if not parts:
            return None
        return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:4326")

    # ── Fetch uncached tiles in blocks ───────────────────────────────────────
    blocks = _form_blocks(uncached, tile_size)
    total = len(uncached)
    fetched_n = 0

    print(f"[{len(tiles)} tiles @ {tile_size}°, {total} uncached → {len(blocks)} block(s)]")

    for block in blocks:
        if len(block) > 1:
            print(f"  block×{len(block)} [{block[0]['id']}…] ", end="", flush=True)
        else:
            print(f"  [{fetched_n + 1:>3}/{total}] {block[0]['id']} ", end="", flush=True)

        results = fetch_block_recursive(spec, block, cols, depth=0)
        print()  # newline after inline status output from query_overpass

        for tile, gdf, status in results:
            tid = tile["id"]
            cache_gpkg = tile_dir / f"{tid}.gpkg"
            cache_empty = tile_dir / f"{tid}.empty"
            fetched_n += 1

            if status == "ok" and gdf is not None and not gdf.empty:
                try:
                    gdf.to_file(cache_gpkg, driver="GPKG")
                    parts.append(gdf)
                    print(f"    [{fetched_n:>3}/{total}] {tid} ✓ {len(gdf)}")
                except Exception as e:
                    print(f"    [{fetched_n:>3}/{total}] {tid} ✗ save: {e}")
                    fails += 1
            elif status == "empty":
                cache_empty.touch()
                print(f"    [{fetched_n:>3}/{total}] {tid} ○ empty")
            else:
                print(f"    [{fetched_n:>3}/{total}] {tid} ✗ fail (will retry next run)")
                fails += 1

        time.sleep(PER_TILE_SLEEP)

    if fails:
        print(f"  ⚠ {fails} tile(s) failed — re-run to retry them")

    if not parts:
        return None
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs="EPSG:4326")


def main():
    parser = argparse.ArgumentParser(description="Fetch OSM layers for a project.")
    parser.add_argument("--project", default="china",
                        help="Project name — subfolder of config/ (default: china)")
    parser.add_argument("--layer", default=None,
                        help="Only fetch this one layer (default: all layers)")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing merged .gpkg and rebuild from cache + Overpass")
    args = parser.parse_args()

    project_dir = PROJECT_ROOT / "config" / args.project
    with open(project_dir / "project.yaml", encoding="utf-8") as f:
        project_cfg = yaml.safe_load(f)

    aoi_bbox = aoi_from_project(project_cfg)

    layers_yaml = project_dir / project_cfg.get("fetch", {}).get("layers_config", "osm_layers.yaml")
    with open(layers_yaml, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    all_layers = cfg["layers"]

    if args.layer:
        if args.layer not in all_layers:
            print(f"Unknown layer '{args.layer}'. Available: {list(all_layers)}")
            return
        layers = {args.layer: all_layers[args.layer]}
    else:
        layers = all_layers

    out_dir = PROJECT_ROOT / "data" / "01_raw" / "osm" / args.project
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"OSM Fetcher  |  project: {args.project}")
    print(f"Servers: {[s.split('/')[2] for s in OVERPASS_SERVERS]}")
    print(f"Output:  {out_dir}")
    print(f"AOI (S,W,N,E): {bbox_to_overpass(aoi_bbox)}\n")

    t0 = datetime.now()
    success = skipped = 0
    total = len(layers)

    for i, (name, spec) in enumerate(layers.items(), 1):
        out_file = out_dir / f"{name}.gpkg"

        if out_file.exists():
            if args.force:
                out_file.unlink()
                print(f"[{i}/{total}] {name}... force-deleted, rebuilding")
            else:
                print(f"[{i}/{total}] {name}... exists, skip  (--force to rebuild)")
                skipped += 1
                continue

        print(f"[{i}/{total}] {name}...", end=" ", flush=True)

        gdf = fetch_layer(name, spec, aoi_bbox)

        if gdf is None or gdf.empty:
            print("no data")
            continue

        if "osm_id" in gdf.columns:
            before = len(gdf)
            gdf = gdf.drop_duplicates(subset=["osm_id"], keep="first")
            if before != len(gdf):
                print(f"dedup {before}->{len(gdf)}...", end=" ")

        hierarchy = spec.get("hierarchy")
        if hierarchy and "highway" in gdf.columns:
            gdf["hierarchy"] = gdf["highway"].map(hierarchy).fillna(99).astype(int)

        for col in spec.get("int_columns", []):
            if col in gdf.columns:
                gdf[col] = pd.to_numeric(gdf[col], errors="coerce").astype("Int64")

        gdf = gdf[gdf.geometry.notnull()]
        if gdf.empty:
            print("no geoms")
            continue

        try:
            gdf.to_file(out_file, driver="GPKG")
            print(f"{len(gdf)} -> {out_file.name}")
            success += 1
        except Exception as e:
            print(f"save error: {e}")

        time.sleep(3)

    elapsed = (datetime.now() - t0).total_seconds()
    print(f"\nDone. {success} new, {skipped} skipped in {elapsed/60:.1f} min")
    print(f"Use --force --layer <name> to rebuild a single layer.")


if __name__ == "__main__":
    main()
