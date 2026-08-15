"""
下载 bangumi-data 的所有 items/*.json，按 anilist_id → zh-Hans 建立映射
"""
import json
import time
import requests
from pathlib import Path

OUT_DIR = Path("data/bangumi_data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = list(range(1943, 2027))  # 1943-2026

BASE_RAW = "https://raw.githubusercontent.com/bangumi-data/bangumi-data/master/data/items/{year}/{month:02d}.json"

# ============ 1. 下载所有文件 ============
all_items = []
for year in YEARS:
    for month in range(1, 13):
        url = BASE_RAW.format(year=year, month=month)
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and r.text.strip():
                items = r.json()
                if items:
                    all_items.extend(items)
                    if year >= 2020:
                        print(f"  {year}-{month:02d}: {len(items)} 条")
            elif r.status_code == 404:
                continue
            else:
                print(f"  {year}-{month:02d}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  {year}-{month:02d}: error {e}")
        time.sleep(0.05)

print(f"\n总下载 {len(all_items)} 条")

# ============ 2. 提取映射 ============
id_to_cn, id_to_jp, id_to_en, id_to_year = {}, {}, {}, {}
for item in all_items:
    sites = {}
    for s in item.get("sites", []):
        if "site" in s and "id" in s:
            sites[s["site"]] = s["id"]
    anilist_id = sites.get("aniList")
    if not anilist_id:
        continue
    try:
        anilist_id = int(anilist_id)
    except (ValueError, TypeError):
        continue

    zh = (item.get("titleTranslate") or {}).get("zh-Hans") or []
    if zh:
        id_to_cn[anilist_id] = zh[0]

    jp = item.get("title")
    if jp:
        id_to_jp[anilist_id] = jp

    en = (item.get("titleTranslate") or {}).get("en") or []
    if en:
        id_to_en[anilist_id] = en[0]

    begin = item.get("begin", "")
    if begin:
        try:
            id_to_year[anilist_id] = int(begin[:4])
        except (ValueError, TypeError):
            pass

# ============ 3. 保存 ============
mapping = {
    "id_to_cn": {str(k): v for k, v in id_to_cn.items()},
    "id_to_jp": {str(k): v for k, v in id_to_jp.items()},
    "id_to_en": {str(k): v for k, v in id_to_en.items()},
    "id_to_year": {str(k): v for k, v in id_to_year.items()},
}
out_file = Path("data/bangumi_cn_mapping.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)

print(f"\n映射文件: {out_file}")
print(f"  含中文名: {len(id_to_cn)}")
print(f"  含日文名: {len(id_to_jp)}")
print(f"  含英文名: {len(id_to_en)}")
print(f"  含年份: {len(id_to_year)}")
