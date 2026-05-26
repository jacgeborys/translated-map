"""
Translate Chinese city names (population >= 1,000,000) to English and Polish.

Reads:
  data/01_raw/osm/places.gpkg              (full AOI, rebuilt by 07_rebuild_places.py)
  data/03_processed/places_translated.gpkg (existing — prior translations are preserved)

Writes:
  data/03_processed/places_translated.gpkg (overwrites; all prior translations kept,
                                            new 1M+ cities appended)
"""

import os
import re
import json
import time
import subprocess
from pathlib import Path

import geopandas as gpd
import pandas as pd
import anthropic

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT  = PROJECT_ROOT / "data" / "01_raw" / "osm" / "places.gpkg"
OUTPUT = PROJECT_ROOT / "data" / "03_processed" / "places_translated.gpkg"
POP_MIN = 1_000_000
BATCH = 50

# Read API key from Windows environment if not already set
if not os.environ.get("ANTHROPIC_API_KEY"):
    for scope in ("User", "Machine"):
        key = subprocess.check_output(
            ["powershell", "-Command",
             f"[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','{scope}')"],
            text=True,
        ).strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            break

client = anthropic.Anthropic()

SYSTEM = (
    "You are an expert in Classical and Modern Chinese, English, and Polish. "
    "For each Chinese city name, give a literal English and Polish translation of its semantic meaning — "
    "not pinyin, not the standard Western name, but what the characters actually mean. "
    "Rules:\n"
    "- Strip trailing administrative suffixes (市, 县, 区, 區, 省, 镇, 自治区) — do not translate them.\n"
    "- Translate all remaining characters faithfully, including 城 (walled city), 京 (capital), "
    "山 (mountain), 江 (river), 阳 (sunny/south-facing side), 阴 (shady/north-facing side), "
    "桂 (osmanthus), 州 (prefecture), 杭 (to cross water by boat), 哈 (ha, phonetic), "
    "尔 (er, phonetic suffix), 沈 (to sink/Shen), 春 (spring), 长 (long/eternal).\n"
    "- For mixed-script names like '香港 Hong Kong', translate only the Chinese characters.\n"
    "- For phonetic transliterations (Manchu/Mongolian/Tibetan origin), provide the best semantic "
    "approximation or note the language of origin if meaning is unknown.\n"
    "Return ONLY a JSON object, no extra text:\n"
    "{\"<input name>\": {\"en\": \"<English>\", \"pl\": \"<Polish>\"}, ...}"
)


def has_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text))) if text else False


def translate_batch(names):
    prompt = ("Translate these Chinese place names literally to both English and Polish:\n"
              + json.dumps(names, ensure_ascii=False))
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def main():
    print(f"Reading {INPUT.name}...")
    gdf = gpd.read_file(INPUT)
    if "population" in gdf.columns:
        gdf["population"] = pd.to_numeric(gdf["population"], errors="coerce").astype("Int64")

    # Load existing translations to avoid re-translating
    existing = {}
    if OUTPUT.exists():
        print(f"Loading existing translations from {OUTPUT.name}...")
        prev = gpd.read_file(OUTPUT)
        for _, row in prev.iterrows():
            name = row.get("name")
            en = row.get("name_eng")
            pl = row.get("name_pol")
            if name and pd.notna(en) and pd.notna(pl) and (en or pl):
                existing[name] = {"en": en or "", "pl": pl or ""}
        print(f"  {len(existing)} names already translated")

    # Identify cities needing translation
    mask = (gdf["population"] >= POP_MIN) & gdf["name"].apply(has_chinese)
    candidates = gdf.loc[mask, "name"].dropna().unique().tolist()
    new_names = [n for n in candidates if n not in existing]

    print(f"\nCities >= {POP_MIN:,} with Chinese names: {mask.sum()}")
    print(f"Already translated: {len(candidates) - len(new_names)}")
    print(f"New to translate:   {len(new_names)}")

    new_translations = {}
    if new_names:
        batches = [new_names[i:i + BATCH] for i in range(0, len(new_names), BATCH)]
        for i, batch in enumerate(batches):
            print(f"  Batch {i + 1}/{len(batches)} ({len(batch)} names)...", end=" ", flush=True)
            try:
                result = translate_batch(batch)
                new_translations.update(result)
                print(f"OK ({len(result)} translated)")
            except Exception as e:
                print(f"ERROR: {e}")
                time.sleep(3)
                try:
                    result = translate_batch(batch)
                    new_translations.update(result)
                    print(f"  Retry OK ({len(result)} translated)")
                except Exception as e2:
                    print(f"  Retry failed: {e2} — skipping batch")
            time.sleep(0.3)

    all_translations = {**existing, **new_translations}
    print(f"\nTotal translations available: {len(all_translations)}")
    print(f"New translations this run:    {len(new_translations)}")

    gdf["name_eng"] = gdf["name"].map(lambda n: all_translations.get(n, {}).get("en"))
    gdf["name_pol"] = gdf["name"].map(lambda n: all_translations.get(n, {}).get("pl"))

    print(f"\nRows with name_eng filled: {gdf['name_eng'].notna().sum()}")
    print(f"Rows with name_pol filled: {gdf['name_pol'].notna().sum()}")

    if new_translations:
        print("\nNewly translated (sample):")
        sample_names = list(new_translations.keys())[:20]
        for n in sample_names:
            t = new_translations[n]
            print(f"  {n:20s} -> {t.get('en', '?'):30s} / {t.get('pl', '?')}")

    print(f"\nSaving to {OUTPUT}...")
    gdf.to_file(OUTPUT, driver="GPKG")
    print("Done.")


if __name__ == "__main__":
    main()
