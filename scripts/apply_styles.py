"""
Input:  china-map.qgz (existing, user-created with raster + osm layers loaded)
Output: china-map.qgz (styles applied in place), qgis/styles/*.qml (per-layer backups)
Purpose: Apply NatGeo-style rule-based renderers + labeling to every layer in the project.

Run under QGIS's bundled Python:
  "C:\\Program Files\\QGIS 3.28.3\\bin\\python-qgis.bat" scripts/apply_styles.py

The script is idempotent — re-run after re-fetching data to refresh styles.
Edit the constants at the top (colors, widths, fonts) rather than tweaking layer
symbology in the GUI, so styles stay config-driven.

Layer lookup is by NAME. Expected names in the project:
  hillshade, water_bodies, rivers, protected_areas, roads, railways,
  train_stations, places, tourism
Layers not present in the project are logged and skipped — no error.
"""

import sys
from pathlib import Path

from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsLineSymbol, QgsFillSymbol, QgsMarkerSymbol,
    QgsSimpleLineSymbolLayer, QgsSimpleFillSymbolLayer, QgsSimpleMarkerSymbolLayer,
    QgsSymbolLayer,
    QgsSingleSymbolRenderer, QgsRuleBasedRenderer,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling, QgsRuleBasedLabeling, QgsProperty,
    QgsUnitTypes,
    QgsHillshadeRenderer,
    QgsSingleBandGrayRenderer, QgsContrastEnhancement, QgsRasterTransparency,
    QgsRasterRange, QgsLabeling, QgsPalettedRasterRenderer,
)
from qgis.PyQt.QtGui import QColor, QFont, QPainter
from qgis.PyQt.QtCore import Qt

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    # Running in QGIS Python console where __file__ is not defined
    PROJECT_ROOT = Path(r"D:\QGIS\natgeo_map\china-map")

QGZ_PATH = PROJECT_ROOT / "china-map.qgz"
STYLES_DIR = PROJECT_ROOT / "qgis" / "styles"
STYLES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Palette — NatGeo-ish muted substrate.
# Tweak here. Everything else derives from these.
# ---------------------------------------------------------------------------
COL_WATER      = "#a9c9d6"
COL_WATER_EDGE = "#7fa8b8"
COL_RIVER      = "#7fa8b8"
COL_PROTECTED  = "#c7d8b5"   # muted green

# Roads: burnt ochre family, cased.
# Hierarchy runs dark→light (motorway darkest, tertiary lightest).
COL_MOTORWAY_CASE = "#ffffff"   # near-black brown — maximum contrast
COL_MOTORWAY_FILL = "#a03d10"   # deep burnt sienna
COL_TRUNK_CASE    = "#ffffff"   # lighter than motorway case
COL_TRUNK_FILL    = "#d49a60"   # lighter amber
COL_PRIMARY_CASE  = "#ffffff"
COL_PRIMARY_FILL  = "#eabe90"   # light ochre
COL_SECONDARY     = "#c8aa88"   # muted tan
COL_TERTIARY      = "#d4c4ac"   # very light tan

# Railways
COL_RAIL_STD      = "#2a2a2a"
COL_RAIL_HSR      = "#1a1a1a"

# Text
COL_LABEL         = "#2a2a2a"
COL_LABEL_WATER   = "#3d6b7d"
COL_LABEL_BUFFER  = "#ffffff"

FONT_FAMILY = "Trebuchet MS"  # swap to any installed NatGeo-ish serif/sans


# ---------------------------------------------------------------------------
# Label expression: English waterfall
# ---------------------------------------------------------------------------
LABEL_EN = 'coalesce("name:en", "name:pinyin", "name")'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg):
    print(f"[apply_styles] {msg}", flush=True)


def _line_flags(*flags):
    """Combine QgsPalLayerSettings line placement flags safely across QGIS versions."""
    combined = 0
    for f in flags:
        combined |= int(f)
    try:
        return QgsLabeling.LinePlacementFlags(combined)
    except (AttributeError, TypeError):
        return combined


def simple_line(color, width_mm, style="solid"):
    sym = QgsLineSymbol.createSimple({
        "color": color,
        "width": str(width_mm),
        "line_style": style,
        "capstyle": "round",
        "joinstyle": "round",
    })
    return sym


def cased_line(case_color, fill_color, case_w, fill_w):
    """Two symbol layers: thicker casing under a thinner fill."""
    sym = QgsLineSymbol()
    sym.deleteSymbolLayer(0)
    case_layer = QgsSimpleLineSymbolLayer.create({
        "color": case_color,
        "width": str(case_w),
        "capstyle": "round",
        "joinstyle": "round",
    })
    fill_layer = QgsSimpleLineSymbolLayer.create({
        "color": fill_color,
        "width": str(fill_w),
        "capstyle": "round",
        "joinstyle": "round",
    })
    sym.appendSymbolLayer(case_layer)
    sym.appendSymbolLayer(fill_layer)
    return sym


def motorway_symbol():
    """Three symbol layers: dark casing → orange fill → thin white median stripe."""
    sym = QgsLineSymbol()
    sym.deleteSymbolLayer(0)
    sym.appendSymbolLayer(QgsSimpleLineSymbolLayer.create({
        "color": COL_MOTORWAY_CASE,
        "width": "0.9",
        "capstyle": "round",
        "joinstyle": "round",
    }))
    sym.appendSymbolLayer(QgsSimpleLineSymbolLayer.create({
        "color": COL_MOTORWAY_FILL,
        "width": "0.7",
        "capstyle": "round",
        "joinstyle": "round",
    }))
    sym.appendSymbolLayer(QgsSimpleLineSymbolLayer.create({
        "color": "#ffffff",
        "width": "0.12",
        "capstyle": "flat",
        "joinstyle": "miter",
    }))
    return sym


def simple_fill(color, stroke=None, stroke_w=0):
    props = {"color": color, "style": "solid"}
    if stroke:
        props["outline_color"] = stroke
        props["outline_width"] = str(stroke_w)
        props["outline_style"] = "solid"
    else:
        props["outline_style"] = "no"
    return QgsFillSymbol.createSimple(props)


def marker(shape, size_mm, color, stroke_color="#222", stroke_w=0.2):
    return QgsMarkerSymbol.createSimple({
        "name": shape,
        "color": color,
        "outline_color": stroke_color,
        "outline_width": str(stroke_w),
        "size": str(size_mm),
    })


def label_format(size_pt, *, bold=False, italic=False, color=COL_LABEL,
                 buffer_size=0.8, buffer_color=COL_LABEL_BUFFER):
    fmt = QgsTextFormat()
    font = QFont(FONT_FAMILY)
    font.setBold(bold)
    font.setItalic(italic)
    fmt.setFont(font)
    fmt.setSize(size_pt)
    fmt.setColor(QColor(color))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(buffer_size)
    buf.setColor(QColor(buffer_color))
    fmt.setBuffer(buf)
    return fmt


def apply_labeling(layer, settings):
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def build_rule_renderer(default_symbol, rules):
    """
    rules: list of dicts with keys: label, filter, symbol.
    An 'else' rule (filter='ELSE') should be last.
    """
    renderer = QgsRuleBasedRenderer(default_symbol)
    root = renderer.rootRule()
    for r in rules:
        rule = QgsRuleBasedRenderer.Rule(r["symbol"])
        rule.setFilterExpression(r["filter"])
        rule.setLabel(r["label"])
        root.appendChild(rule)
    # Drop the default auto-rule that QgsRuleBasedRenderer adds (index 0 if present).
    # Keep our explicit rules only.
    if root.children() and len(root.children()) > len(rules):
        root.removeChildAt(0)
    return renderer


def save_qml(layer, name):
    out = STYLES_DIR / f"{name}.qml"
    layer.saveNamedStyle(str(out))
    log(f"    .qml → {out.relative_to(PROJECT_ROOT)}")


def find_layer(project, name):
    lyrs = project.mapLayersByName(name)
    if not lyrs:
        log(f"  ⚠ layer '{name}' not in project — skipping")
        return None
    return lyrs[0]


# ---------------------------------------------------------------------------
# Per-layer styling
# ---------------------------------------------------------------------------

def style_hillshade(layer):
    provider = layer.dataProvider()

    # Mark 0 as nodata at the provider level (gdaldem default for ocean/nodata areas)
    provider.setUserNoDataValue(1, [QgsRasterRange(0.0, 0.0)])

    renderer = QgsSingleBandGrayRenderer(provider, 1)

    # Render nodata pixels as white. With Multiply blend, white × anything = anything,
    # so nodata areas become fully invisible regardless of what's below.
    renderer.setNodataColor(QColor(255, 255, 255))

    ce = QgsContrastEnhancement(provider.dataType(1))
    ce.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    ce.setMinimumValue(0)
    ce.setMaximumValue(215)
    renderer.setContrastEnhancement(ce)

    layer.setRenderer(renderer)
    layer.brightnessFilter().setContrast(00)
    layer.setOpacity(0.80)
    layer.setBlendMode(QPainter.CompositionMode_Multiply)
    layer.triggerRepaint()


def style_water_bodies(layer):
    sym = simple_fill(COL_WATER, stroke=COL_WATER_EDGE, stroke_w=0.1)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)


def style_rivers(layer):
    sym = simple_line(COL_RIVER, 0.4)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)


def style_protected_areas(layer):
    sym = simple_fill(COL_PROTECTED)
    # Make translucent by setting alpha on the symbol
    sym.setOpacity(0.35)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))


def _admin_fill(stroke_color, stroke_w, stroke_style="solid"):
    """No-fill polygon with only an outline — for admin boundary layers."""
    props = {
        "color": "0,0,0,0",
        "style": "no",
        "outline_color": stroke_color,
        "outline_width": str(stroke_w),
        "outline_style": stroke_style,
    }
    return QgsFillSymbol.createSimple(props)


def style_admin_country(layer):
    sym = QgsFillSymbol()
    sym.deleteSymbolLayer(0)
    # Bottom: wide, bright, semi-transparent glow
    glow = QgsSimpleFillSymbolLayer.create({
        "color": "0,0,0,0",
        "style": "no",
        "outline_color": "220,80,130,90",  # bright pink, ~35% opacity
        "outline_width": "3.0",
        "outline_style": "solid",
    })
    # Top: current sharp thin line
    line = QgsSimpleFillSymbolLayer.create({
        "color": "0,0,0,0",
        "style": "no",
        "outline_color": "#a04060",
        "outline_width": "0.8",
        "outline_style": "solid",
    })
    sym.appendSymbolLayer(glow)
    sym.appendSymbolLayer(line)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))


def style_admin_province(layer):
    layer.setRenderer(QgsSingleSymbolRenderer(_admin_fill("#b86080", 0.45)))


def style_admin_prefecture(layer):
    layer.setRenderer(QgsSingleSymbolRenderer(_admin_fill("#c88098", 0.25, "dash")))


def style_ocean(layer):
    sym = simple_fill(COL_WATER, stroke=COL_WATER_EDGE, stroke_w=0.1)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))


def style_roads(layer):
    default = simple_line(COL_TERTIARY, 0.1)
    rules = [
        {
            "label": "motorway",
            "filter": '"hierarchy" = 1',
            "symbol": motorway_symbol(),
        },
        {
            "label": "trunk",
            "filter": '"hierarchy" = 2',
            "symbol": cased_line(COL_TRUNK_CASE, COL_TRUNK_FILL, 0.43, 0.26),
        },
        {
            "label": "primary",
            "filter": '"hierarchy" = 3',
            "symbol": cased_line(COL_PRIMARY_CASE, COL_PRIMARY_FILL, 0.31, 0.18),
        },
        {
            "label": "secondary",
            "filter": '"hierarchy" = 4',
            "symbol": simple_line(COL_SECONDARY, 0.11),
        },
        {
            "label": "tertiary",
            "filter": '"hierarchy" = 5',
            "symbol": simple_line(COL_TERTIARY, 0.07),
        },
    ]
    renderer = build_rule_renderer(default, rules)

    # Symbol levels — two-band system keeps casing joints clean AND ensures
    # higher-hierarchy roads always render above lower ones:
    #   Passes 0–4: casings  (tertiary has none; primary=2, trunk=3, motorway=4)
    #   Passes 5–9: fills    (tertiary=5, secondary=6, primary=7, trunk=8, motorway=9)
    #   Pass 10:    motorway median stripe (always on top)
    pass_cfg = {
        "motorway": (4, 9, 10),   # casing, fill, median
        "trunk":    (3, 8),
        "primary":  (2, 7),
        "secondary":(6,),          # single-layer fill
        "tertiary": (5,),
    }
    renderer.setUsingSymbolLevels(True)
    for rule in renderer.rootRule().children():
        sym = rule.symbol()
        if not sym:
            continue
        passes = pass_cfg.get(rule.label(), (5,))
        for i, p in enumerate(passes):
            if i < sym.symbolLayerCount():
                sym.symbolLayer(i).setRenderingPass(p)

    layer.setRenderer(renderer)
    layer.setLabelsEnabled(False)


def _cased_rail(line_color, line_width, line_style="solid"):
    """White casing (1.0mm) under a rail line — same symbol-level pattern as roads."""
    sym = QgsLineSymbol()
    sym.deleteSymbolLayer(0)
    sym.appendSymbolLayer(QgsSimpleLineSymbolLayer.create({
        "color": "#ffffff",
        "width": "1.0",
        "capstyle": "flat",
        "joinstyle": "miter",
    }))
    sym.appendSymbolLayer(QgsSimpleLineSymbolLayer.create({
        "color": line_color,
        "width": str(line_width),
        "line_style": line_style,
        "capstyle": "flat",
        "joinstyle": "miter",
    }))
    return sym


def style_railways(layer):
    hsr_filter = (
        '"highspeed" = \'yes\' OR '
        '(try(to_int(regexp_substr("maxspeed", \'[0-9]+\')), 0) >= 200)'
    )
    default = _cased_rail(COL_RAIL_STD, 0.35)
    rules = [
        {
            "label": "high-speed rail",
            "filter": hsr_filter,
            "symbol": _cased_rail(COL_RAIL_HSR, 0.7),
        },
        {
            "label": "conventional rail",
            "filter": "ELSE",
            "symbol": _cased_rail(COL_RAIL_STD, 0.35),
        },
    ]
    renderer = build_rule_renderer(default, rules)
    renderer.setUsingSymbolLevels(True)
    for rule in renderer.rootRule().children():
        sym = rule.symbol()
        if sym and sym.symbolLayerCount() >= 2:
            sym.symbolLayer(0).setRenderingPass(0)  # white casing
            sym.symbolLayer(1).setRenderingPass(1)  # rail line
    layer.setRenderer(renderer)


def style_train_stations(layer):
    layer.setSubsetString("\"train\" = 'yes'")
    sym = marker("square", 1.8, "#1a1a1a", stroke_color="#ffffff", stroke_w=0.3)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)


def style_places(layer):
    # Single marker with data-defined size so points scale with their label.
    # Max size (2.5mm) matches the largest label tier (pop >= 5M, 15pt).
    # Use coalesce("population", 0) directly — population is stored as float64
    # so to_int() is unnecessary and can silently fail.
    pop = 'coalesce("population", 0)'
    marker_size_expr = (
        f'CASE '
        f' WHEN {pop} >= 5000000 THEN 2.5 '
        f' WHEN {pop} >= 1000000 THEN 2.0 '
        f' WHEN {pop} >=  500000 THEN 1.6 '
        f' WHEN {pop} >=  100000 THEN 1.0 '
        f' ELSE 0.7 '
        f'END'
    )
    sym = QgsMarkerSymbol()
    sym.deleteSymbolLayer(0)
    sl = QgsSimpleMarkerSymbolLayer.create({
        "name": "circle",
        "color": "#222222",
        "outline_color": "#ffffff",
        "outline_width": "0.35",
        "size": "2.5",
    })
    sl.setDataDefinedProperty(
        QgsSymbolLayer.PropertySize,
        QgsProperty.fromExpression(marker_size_expr),
    )
    sym.appendSymbolLayer(sl)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))

    # Labels: two-line minimalistic layout.
    #   Line 1 (top):    original Chinese name — half the size, muted grey
    #   Line 2 (bottom): English/pinyin name   — full size, normal colour
    # HTML rendering enables different font sizes within a single label.
    size_expr = (
        f'CASE '
        f' WHEN {pop} >= 5000000 THEN 15 '
        f' WHEN {pop} >= 1000000 THEN 12 '
        f' WHEN {pop} >=  500000 THEN 10 '
        f' WHEN {pop} >=  100000 THEN 7 '
        f' ELSE 8 '
        f'END'
    )
    half_size_expr = (
        f'CASE '
        f' WHEN {pop} >= 5000000 THEN 8 '
        f' WHEN {pop} >= 1000000 THEN 6 '
        f' WHEN {pop} >=  500000 THEN 5 '
        f' WHEN {pop} >=  100000 THEN 4 '
        f' ELSE 4 '
        f'END'
    )
    # Priority = placement priority (which label is placed first when space is tight).
    # ZIndex   = render order (which label draws on top when two labels overlap).
    # Both use the same population scale so larger cities always win.
    priority_expr = (
        f'CASE '
        f' WHEN {pop} >= 5000000 THEN 10 '
        f' WHEN {pop} >= 1000000 THEN 8 '
        f' WHEN {pop} >=  500000 THEN 6 '
        f' WHEN {pop} >=  100000 THEN 4 '
        f' ELSE 2 '
        f'END'
    )
    bold_expr = f'CASE WHEN {pop} >= 1000000 THEN True ELSE False END'

    # HTML label: Chinese name above (half size, muted) only when it differs
    # from the resolved English label; English name inherits the base text format.
    name_en = 'coalesce("name:en", "name:pinyin", "name")'
    html_label = (
        f"concat("
        f"  if(\"name\" IS NOT NULL AND \"name\" != {name_en},"
        f"    concat('<span style=\"font-size:', to_string({half_size_expr}), 'pt; color:#888888\">', \"name\", '</span><br>'),"
        f"    ''"
        f"  ),"
        f"  {name_en}"
        f")"
    )

    lbl = QgsPalLayerSettings()
    lbl.isExpression = True
    lbl.useHtml = True
    lbl.fieldName = html_label
    lbl.setFormat(label_format(8.0, bold=False))
    lbl.placement = QgsPalLayerSettings.OverPoint
    lbl.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.Size, QgsProperty.fromExpression(size_expr)
    )
    lbl.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.Priority, QgsProperty.fromExpression(priority_expr)
    )
    # ZIndex: use raw population (millions) so Guangzhou (14M) beats Foshan (9.5M).
    lbl.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.ZIndex, QgsProperty.fromExpression(f'{pop} / 1000000')
    )
    lbl.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.Bold, QgsProperty.fromExpression(bold_expr)
    )
    lbl.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.Show,
        QgsProperty.fromExpression('"place" = \'city\''),
    )
    apply_labeling(layer, lbl)


def style_tourism(layer):
    # For now: render as tiny unobtrusive markers; we'll filter & restyle later.
    sym = marker("circle", 1.2, "#b25a2a", "#fff", 0.2)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    # No labels yet. TODO: filter out hotel/info/gallery etc., then label curated set.


# ---------------------------------------------------------------------------
# places_translated — rule-based density labeling
# ---------------------------------------------------------------------------
# Label offset distances (mm) per neighbour-density tier.
# Tier is determined by the count of other features within PLACES_TR_RADIUS degrees.
PLACES_TR_DIST_ISOLATED = 2.0   # 0 neighbours
PLACES_TR_DIST_FEW      = 6.0   # 1–2 neighbours
PLACES_TR_DIST_CROWDED  = 16.0  # >2 neighbours
PLACES_TR_CALLOUT_MIN   = 4.0   # show callout line when dist exceeds this (mm)
PLACES_TR_RADIUS        = 0.2   # neighbour-search radius in degrees


def _places_tr_lbl(dist_mm):
    """Return QgsPalLayerSettings for one density tier of places_translated."""
    pop = 'coalesce("population", 0)'

    size_expr = (
        f'CASE'
        f' WHEN {pop} >= 5000000 THEN 15'
        f' WHEN {pop} >= 1000000 THEN 12'
        f' WHEN {pop} >=  500000 THEN 10'
        f' WHEN {pop} >=  100000 THEN 7'
        f' ELSE 8'
        f' END'
    )
    half_size_expr = (
        f'CASE'
        f' WHEN {pop} >= 5000000 THEN 8'
        f' WHEN {pop} >= 1000000 THEN 6'
        f' WHEN {pop} >=  500000 THEN 5'
        f' WHEN {pop} >=  100000 THEN 4'
        f' ELSE 4'
        f' END'
    )
    priority_expr = (
        f'CASE'
        f' WHEN {pop} >= 5000000 THEN 10'
        f' WHEN {pop} >= 1000000 THEN 8'
        f' WHEN {pop} >=  500000 THEN 6'
        f' WHEN {pop} >=  100000 THEN 4'
        f' ELSE 2'
        f' END'
    )
    bold_expr = f'CASE WHEN {pop} >= 1000000 THEN True ELSE False END'

    # Line 1 (big):   name_eng semantic translation — inherits full label size
    # Line 2 (small): name:en transliteration — only shown when translation exists
    html_label = (
        f"concat("
        f"  coalesce(\"name_eng\", \"name:en\", \"name:pinyin\", \"name\"),"
        f"  if(\"name_eng\" IS NOT NULL AND \"name:en\" IS NOT NULL,"
        f"    concat('<br><span style=\"font-size:', to_string({half_size_expr}), 'pt; color:#888888\">', \"name:en\", '</span>'),"
        f"    ''"
        f"  )"
        f")"
    )

    lbl = QgsPalLayerSettings()
    lbl.isExpression = True
    lbl.useHtml = True
    lbl.fieldName = html_label
    lbl.setFormat(label_format(8.0))
    lbl.placement = QgsPalLayerSettings.OverPoint
    lbl.dist = dist_mm
    lbl.distUnits = QgsUnitTypes.RenderMillimeters

    props = lbl.dataDefinedProperties()
    props.setProperty(QgsPalLayerSettings.Size,     QgsProperty.fromExpression(size_expr))
    props.setProperty(QgsPalLayerSettings.Priority, QgsProperty.fromExpression(priority_expr))
    props.setProperty(QgsPalLayerSettings.ZIndex,   QgsProperty.fromExpression(f'{pop} / 1000000'))
    props.setProperty(QgsPalLayerSettings.Bold,     QgsProperty.fromExpression(bold_expr))
    props.setProperty(QgsPalLayerSettings.Show,     QgsProperty.fromExpression('"place" = \'city\''))

    if dist_mm > PLACES_TR_CALLOUT_MIN:
        try:
            from qgis.core import QgsSimpleLineCallout
            callout = QgsSimpleLineCallout()
            callout.lineSymbol().setColor(QColor("#2a2a2a"))
            callout.lineSymbol().setWidth(0.2)
            lbl.setCallout(callout)
            lbl.calloutEnabled = True
        except Exception as e:
            log(f"    callout unavailable: {e}")

    return lbl


def style_places_translated(layer):
    # ---- marker: same size-scaled circle as style_places ----
    pop = 'coalesce("population", 0)'
    marker_size_expr = (
        f'CASE'
        f' WHEN {pop} >= 5000000 THEN 2.5'
        f' WHEN {pop} >= 1000000 THEN 2.0'
        f' WHEN {pop} >=  500000 THEN 1.6'
        f' WHEN {pop} >=  100000 THEN 1.0'
        f' ELSE 0.7'
        f' END'
    )
    sym = QgsMarkerSymbol()
    sym.deleteSymbolLayer(0)
    sl = QgsSimpleMarkerSymbolLayer.create({
        "name": "circle",
        "color": "#222222",
        "outline_color": "#ffffff",
        "outline_width": "0.35",
        "size": "2.5",
    })
    sl.setDataDefinedProperty(
        QgsSymbolLayer.PropertySize,
        QgsProperty.fromExpression(marker_size_expr),
    )
    sym.appendSymbolLayer(sl)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))

    # ---- rule-based labeling: 3 density tiers ----
    r = PLACES_TR_RADIUS
    nc = (
        f"aggregate('places_translated','count',$id,"
        f"distance($geometry,geometry(@parent))<{r}"
        f" AND $id!=attribute(@parent,'fid'))"
    )

    root = QgsRuleBasedLabeling.Rule(None)
    for desc, expr, dist in [
        ("isolated",      f"{nc} = 0",               PLACES_TR_DIST_ISOLATED),
        ("few neighbors", f"{nc} > 0 AND {nc} <= 2",  PLACES_TR_DIST_FEW),
        ("crowded",       f"{nc} > 2",                PLACES_TR_DIST_CROWDED),
    ]:
        rule = QgsRuleBasedLabeling.Rule(_places_tr_lbl(dist))
        rule.setFilterExpression(expr)
        rule.setDescription(desc)
        root.appendChild(rule)

    layer.setLabeling(QgsRuleBasedLabeling(root))
    layer.setLabelsEnabled(True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _wc_styler(esa_class, hex_color, opacity=0.30):
    """Return a style function that shows exactly one ESA WorldCover class."""
    def _style(layer):
        classes = [QgsPalettedRasterRenderer.Class(esa_class, QColor(hex_color), "")]
        renderer = QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes)
        renderer.setNodataColor(QColor(0, 0, 0, 0))
        layer.setRenderer(renderer)
        layer.setOpacity(opacity)
        layer.triggerRepaint()
    return _style

# Each points to the same worldcover.tif but shows a single class.
# Load worldcover.tif five times in QGIS, naming each layer as below.
style_wc_trees     = _wc_styler(10, "#7aaa68", 0.12)   # forests & plantations — very pale green
style_wc_cropland  = _wc_styler(40, "#e0d4a0", 0.12)   # rice paddies & farmland — very pale wheat
style_wc_builtup   = _wc_styler(50, "#9e9389", 0.20)   # cities & urban areas — pale warm grey
style_wc_wetland   = _wc_styler(90, "#9ec4b8", 0.15)   # herbaceous wetlands
style_wc_mangroves = _wc_styler(95, "#5fa882", 0.18)   # mangroves


def style_urban_areas(layer):
    # Muted warm grey — distinct from terrain but not jarring.
    # Placed above hillshade so it reads clearly regardless of slope.
    props = {
        "color": "#ddd5c0",
        "style": "solid",
        "outline_style": "no",
    }
    layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(props)))


STYLERS = [
    ("ocean",            style_ocean),          # Natural Earth — below everything
    ("wc_trees",         style_wc_trees),        # ESA class 10 — forests & plantations
    ("wc_cropland",      style_wc_cropland),     # ESA class 40 — farmland
    ("wc_builtup",       style_wc_builtup),      # ESA class 50 — cities
    ("wc_wetland",       style_wc_wetland),      # ESA class 90 — wetlands
    ("wc_mangroves",     style_wc_mangroves),    # ESA class 95 — mangroves
    ("hillshade",        style_hillshade),      # Multiply blend — shades all layers below
    ("urban_areas",      style_urban_areas),    # Natural Earth — above hillshade
    ("water_bodies",     style_water_bodies),
    ("rivers",           style_rivers),
    ("protected_areas",  style_protected_areas),
    ("admin_country",    style_admin_country),
    ("admin_province",   style_admin_province),
    ("admin_prefecture", style_admin_prefecture),
    ("roads",            style_roads),
    ("railways",         style_railways),
    ("train_stations",   style_train_stations),
    ("places",             style_places),
    ("places_translated",  style_places_translated),
    ("tourism",            style_tourism),
]


def main():
    # Detect whether we're inside a running QGIS instance or standalone
    standalone = QgsApplication.instance() is None

    if standalone:
        QgsApplication.setPrefixPath(str(Path(sys.executable).parent.parent), True)
        app = QgsApplication([], False)
        app.initQgis()

    project = QgsProject.instance()

    if standalone:
        if not QGZ_PATH.exists():
            log(f"ERROR: {QGZ_PATH} does not exist. Create it in QGIS first, load the layers, save, then re-run.")
            app.exitQgis()
            sys.exit(1)
        if not project.read(str(QGZ_PATH)):
            log(f"ERROR: failed to read {QGZ_PATH}")
            app.exitQgis()
            sys.exit(1)
        log(f"opened project: {QGZ_PATH}")
    else:
        log(f"running inside QGIS, using open project: {project.fileName()}")

    log(f"layers in project: {[l.name() for l in project.mapLayers().values()]}")

    for name, fn in STYLERS:
        layer = find_layer(project, name)
        if layer is None:
            continue
        log(f"  → {name}")
        try:
            fn(layer)
            save_qml(layer, name)
        except Exception as e:
            log(f"    ✗ {type(e).__name__}: {e}")

    # Save project
    if project.write():
        log(f"✓ project saved: {QGZ_PATH}")
    else:
        log(f"✗ project.write() failed")

    # Refresh canvas if running inside QGIS
    if not standalone:
        try:
            iface.mapCanvas().refreshAllLayers()
        except Exception:
            pass

    if standalone:
        app.exitQgis()


if __name__ == "__main__":
    main()
