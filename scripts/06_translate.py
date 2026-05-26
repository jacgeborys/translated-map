"""
Translate place names to English (and optionally other languages) using Claude.

Reads settings from config/<project>/project.yaml:
  translate.layer          — which OSM layer to translate (e.g. places)
  translate.population_min — only translate cities above this population
  translate.languages      — list of language codes (e.g. [en] or [en, pl])

Translation cache:  data/03_processed/translations_cache.csv
  Append-only. Delete this file to force re-translation from scratch.

Input:   data/01_raw/osm/<layer>.gpkg
Output:  data/03_processed/<layer>_translated.gpkg
"""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml
import anthropic

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_CSV = PROJECT_ROOT / "data" / "03_processed" / "translations_cache.csv"

SYSTEM = (
    "You are an expert in Classical and Modern Chinese and multiple modern languages. "
    "For each Chinese place name, give a literal translation of its semantic meaning — "
    "not pinyin, not the standard Western name, but what the characters actually mean.\n"
    "Rules:\n"
    "- Strip trailing administrative suffixes (市, 县, 区, 區, 省, 镇, 自治区) before translating.\n"
    "- Translate all remaining characters faithfully, e.g.: "
    "城 (walled city), 京 (capital), 山 (mountain), 江 (river), "
    "阳 (sunny/south-facing), 阴 (shady/north-facing), 桂 (osmanthus), "
    "州 (prefecture), 春 (spring), 长 (long/eternal), 沈 (to sink).\n"
    "- For phonetic transliterations (Manchu/Mongolian/Tibetan origin), "
    "provide the best semantic approximation or note the source language.\n"
    "Return ONLY a JSON object, no extra text:\n"
    "{\"<input name>\": {\"en\": \"<English>\", \"pl\": \"<Polish>\"}, ...}\n"
    "Omit keys for languages not requested."
)


def has_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text))) if text else False


def load_api_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    for scope in ("User", "Machine"):
        key = subprocess.check_output(
            ["powershell", "-Command",
             f"[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','{scope}')"],
            text=True,
        ).strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            return


def translate_batch(client, names, languages):
    lang_list = ", ".join(languages)
    prompt = (
        f"Translate these Chinese place names literally. "
        f"Include only these language keys: {lang_list}.\n"
        + json.dumps(names, ensure_ascii=False)
    )
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


def load_cache(languages):
    """Load existing translation cache CSV. Returns dict: name -> {lang: translation}."""
    cache = {}
    if not CACHE_CSV.exists():
        return cache
    df = pd.read_csv(CACHE_CSV, dtype=str).fillna("")
    for _, row in df.iterrows():
        name = row.get("name", "")
        if not name:
            continue
        cache[name] = {lang: row.get(lang, "") for lang in languages if lang in df.columns}
    return cache


def save_cache(cache):
    """Write the full cache back to CSV."""
    rows = [{"name": k, **v} for k, v in cache.items()]
    pd.DataFrame(rows).to_csv(CACHE_CSV, index=False, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Translate OSM place names via Claude.")
    parser.add_argument("--project", default="china",
                        help="Project name — subfolder of config/ (default: china)")
    parser.add_argument("--batch", type=int, default=50,
                        help="Names per API call (default: 50)")
    args = parser.parse_args()

    project_dir = PROJECT_ROOT / "config" / args.project
    with open(project_dir / "project.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    translate_cfg = cfg.get("translate")
    if not translate_cfg:
        print("No 'translate' section in project.yaml — nothing to do.")
        return

    layer      = translate_cfg["layer"]
    pop_min    = int(translate_cfg.get("population_min", 0))
    languages  = translate_cfg.get("languages", ["en"])

    input_gpkg = PROJECT_ROOT / "data" / "01_raw" / "osm" / f"{layer}.gpkg"
    output_gpkg = PROJECT_ROOT / "data" / "03_processed" / f"{layer}_translated.gpkg"

    print(f"Project:   {args.project}")
    print(f"Layer:     {layer}  (pop >= {pop_min:,})")
    print(f"Languages: {languages}")
    print(f"Cache:     {CACHE_CSV.name}")

    load_api_key()
    client = anthropic.Anthropic()

    print(f"\nReading {input_gpkg.name}...")
    gdf = gpd.read_file(input_gpkg)
    if "population" in gdf.columns:
        gdf["population"] = pd.to_numeric(gdf["population"], errors="coerce").astype("Int64")

    # Load translation cache
    cache = load_cache(languages)
    print(f"Cache loaded: {len(cache)} existing translations")

    # Find candidates
    if pop_min > 0 and "population" in gdf.columns:
        mask = (gdf["population"] >= pop_min) & gdf["name"].apply(has_chinese)
    else:
        mask = gdf["name"].apply(has_chinese)

    candidates = gdf.loc[mask, "name"].dropna().unique().tolist()
    new_names = [n for n in candidates if n not in cache]

    print(f"\nCandidates (pop >= {pop_min:,}, Chinese name): {len(candidates)}")
    print(f"Already in cache:  {len(candidates) - len(new_names)}")
    print(f"New to translate:  {len(new_names)}")

    if new_names:
        batches = [new_names[i:i + args.batch] for i in range(0, len(new_names), args.batch)]
        for i, batch in enumerate(batches):
            print(f"  Batch {i + 1}/{len(batches)} ({len(batch)} names)...", end=" ", flush=True)
            try:
                result = translate_batch(client, batch, languages)
                cache.update(result)
                print(f"OK ({len(result)} translated)")
            except Exception as e:
                print(f"ERROR: {e} — retrying...")
                time.sleep(3)
                try:
                    result = translate_batch(client, batch, languages)
                    cache.update(result)
                    print(f"  Retry OK ({len(result)})")
                except Exception as e2:
                    print(f"  Retry failed: {e2} — skipping batch")
            time.sleep(0.3)

        save_cache(cache)
        print(f"\nCache saved: {len(cache)} total translations -> {CACHE_CSV.name}")

        print("\nNewly translated (sample):")
        for name in list(new_names)[:15]:
            t = cache.get(name, {})
            parts = "  /  ".join(f"{l}: {t.get(l, '?')}" for l in languages)
            print(f"  {name:20s}  {parts}")

    # Apply translations to full GeoDataFrame
    for lang in languages:
        col = f"name_{lang}"
        gdf[col] = gdf["name"].map(lambda n: cache.get(n, {}).get(lang))

    filled = {lang: gdf[f"name_{lang}"].notna().sum() for lang in languages}
    print(f"\nTranslated rows: { {f'name_{l}': n for l, n in filled.items()} }")

    print(f"Saving -> {output_gpkg.name}...")
    gdf.to_file(output_gpkg, driver="GPKG")
    print("Done.")


if __name__ == "__main__":
    main()
