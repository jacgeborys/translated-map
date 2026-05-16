"""
Input:  data/01_raw/osm/*.gpkg, config/name_overrides.csv
Output: data/02_interim/osm/*.gpkg with added `label` column
Purpose: Resolve English display names via waterfall: override → name:en → pinyin → translit.

STUB — not implemented this session. Waterfall order:
  1. config/name_overrides.csv (name_zh → name_en) — manual curation
  2. OSM tag `name:en`
  3. OSM tag `name:pinyin` / `name:zh_pinyin`
  4. Transliterate `name` (zh → pinyin) — library TBD (pypinyin?)
  5. Fallback: raw `name`
Optionally: feed unresolved names to Claude Haiku for meaning translation.
"""


def main():
    raise SystemExit("translate_labels.py: not implemented yet.")


if __name__ == "__main__":
    main()
