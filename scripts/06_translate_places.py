"""
Translate Chinese city names literally to English and Polish using Claude Sonnet.
Reads: china-map/data/01_raw/osm/places.gpkg
Writes: china-map/data/03_processed/places_translated.gpkg (new columns: name_eng, name_pol)
"""

import os
import re
import json
import time
import subprocess
import geopandas as gpd
import anthropic

INPUT  = "D:/QGIS/natgeo_map/china-map/data/01_raw/osm/places.gpkg"
OUTPUT = "D:/QGIS/natgeo_map/china-map/data/03_processed/places_translated.gpkg"
BATCH  = 50

# Fall back to reading the key from Windows environment if not in process env
if not os.environ.get("ANTHROPIC_API_KEY"):
    key = subprocess.check_output(
        ["powershell", "-Command",
         "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"],
        text=True
    ).strip()
    if not key:
        key = subprocess.check_output(
            ["powershell", "-Command",
             "[System.Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','Machine')"],
            text=True
        ).strip()
    os.environ["ANTHROPIC_API_KEY"] = key

client = anthropic.Anthropic()

SYSTEM = (
    "You are an expert in Classical and Modern Chinese, English, and Polish. "
    "For each Chinese city name, give a literal English and Polish translation of its semantic meaning — "
    "not pinyin, not the standard Western name, but what the characters actually mean. "
    "Rules:\n"
    "- Strip trailing administrative suffixes (市, 县, 区, 區, 省, 镇, 自治区) — do not translate them.\n"
    "- Translate all remaining characters faithfully, including 城 (walled city), 京 (capital), "
    "山 (mountain), 江 (river), 阳 (sunny/south-facing side), 阴 (shady/north-facing side), "
    "桂 (osmanthus, not cassia — in place names it always refers to the osmanthus tree), "
    "州 (prefecture), 杭 (to cross water by boat).\n"
    "- For mixed-script names like '香港 Hong Kong', translate only the Chinese characters.\n"
    "Return ONLY a JSON object, no extra text:\n"
    "{\"<input name>\": {\"en\": \"<English>\", \"pl\": \"<Polish>\"}, ...}"
)


def has_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text))) if text else False


def translate_batch(names):
    prompt = "Translate these Chinese place names literally to both English and Polish:\n" + json.dumps(names, ensure_ascii=False)
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
    print("Reading GeoPackage…")
    gdf = gpd.read_file(INPUT)

    mask = (gdf["population"] > 500_000) & gdf["name"].apply(has_chinese)
    print(f"Cities >500k with Chinese primary names: {mask.sum()}")

    unique_names = gdf.loc[mask, "name"].dropna().unique().tolist()
    print(f"Unique names to translate: {len(unique_names)}")

    translations = {}
    batches = [unique_names[i : i + BATCH] for i in range(0, len(unique_names), BATCH)]

    for i, batch in enumerate(batches):
        print(f"  Batch {i+1}/{len(batches)} ({len(batch)} names)…", end=" ", flush=True)
        try:
            result = translate_batch(batch)
            translations.update(result)
            print(f"OK ({len(result)} translated)")
        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(3)
            try:
                result = translate_batch(batch)
                translations.update(result)
                print(f"  Retry OK ({len(result)} translated)")
            except Exception as e2:
                print(f"  Retry failed: {e2} — skipping batch")
        time.sleep(0.3)

    print(f"\nTotal translations collected: {len(translations)}")

    gdf["name_eng"] = gdf["name"].map(lambda n: translations.get(n, {}).get("en"))
    gdf["name_pol"] = gdf["name"].map(lambda n: translations.get(n, {}).get("pl"))

    print(f"Rows with name_eng filled: {gdf['name_eng'].notna().sum()}")
    print(f"Rows with name_pol filled: {gdf['name_pol'].notna().sum()}")
    print("\nSample:")
    sample = gdf.loc[mask, ["name", "name_eng", "name_pol", "population"]].sort_values(
        "population", ascending=False
    ).head(20)
    print(sample.to_string(index=False))

    print(f"\nSaving to {OUTPUT} …")
    gdf.to_file(OUTPUT, driver="GPKG")
    print("Done.")


if __name__ == "__main__":
    main()
