"""
fetch_missing_from_anilist.py
================
Bangumi 有但 cache 缺的 1410 部番剧，批量从 AniList 拉详情加入 cache。

AniList GraphQL 用 type:Media, query: id_in 批量 50 个。
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "data", "anime_cache.json")
NAMES = os.path.join(BASE, "data", "names_cn.json")
BAK = os.path.join(BASE, "data", "anime_cache.json.bak_pre_missing")


ANILIST_URL = "https://graphql.anilist.co"

# 28 字段 (跟 data_loader._normalize 一致)
QUERY = """
query ($ids: [Int!]) {
  Page(perPage: 50) {
    media(id_in: $ids, type: ANIME) {
      id idMal
      title { romaji english native userPreferred }
      description(asHtml: false)
      tags { name rank }
      averageScore meanScore popularity favourites
      startDate { year month day }
      endDate { year month day }
      episodes duration status format
      coverImage { extraLarge large medium color }
      bannerImage
      season seasonYear
      studios(isMain: true) { nodes { name } }
      staff(perPage: 8) { edges { role node { name { full } } } }
      characters(perPage: 12) { edges { role node { name { full } } voiceActors { name { full } } } }
    }
  }
}
"""


def fetch_batch(ids):
    """一次 GraphQL 请求取 50 部。"""
    body = json.dumps({"query": QUERY, "variables": {"ids": ids}}).encode()
    req = urllib.request.Request(
        ANILIST_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AnimeRecommender/1.0",
        },
        method="POST",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
                return data.get("data", {}).get("Page", {}).get("media", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"  429 rate limit, wait {wait}s")
                time.sleep(wait)
            elif e.code == 403:
                wait = 10 * (attempt + 1)
                print(f"  403 forbidden, wait {wait}s")
                time.sleep(wait)
            else:
                print(f"  HTTP {e.code}, retry")
                time.sleep(3)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  network: {e}, retry")
            time.sleep(3)
    return []


def normalize(m):
    """跟 data_loader._normalize 类似的简化版。"""
    title = m.get("title") or {}
    name = title.get("userPreferred") or title.get("romaji") or ""
    name_jp = title.get("native") or ""
    name_en = title.get("english") or ""

    desc = m.get("description") or ""
    if desc:
        desc = desc.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        # 去掉 [i]...[/i] [b]...[/b] 等
        import re
        desc = re.sub(r"\[/?[a-z]+\]", "", desc)
    desc = (desc or "")[:1000]

    tags = []
    tags_with_rank = []
    for t in m.get("tags") or []:
        if t.get("name"):
            tags.append(t["name"])
            tags_with_rank.append({"name": t["name"], "rank": t.get("rank") or 0})

    sd = m.get("startDate") or {}
    ed = m.get("endDate") or {}
    year = sd.get("year") if sd.get("year") else (ed.get("year") if ed.get("year") else None)
    air_date = ""
    if sd.get("year"):
        air_date = f"{sd['year']:04d}-{sd.get('month', 1):02d}-{sd.get('day', 1):02d}"
    elif year:
        air_date = f"{year:04d}"

    studios = [s["name"] for s in (m.get("studios") or {}).get("nodes", []) if s.get("name")]

    staff = []
    for e in (m.get("staff") or {}).get("edges", []):
        node = e.get("node") or {}
        nm = (node.get("name") or {}).get("full") or ""
        if nm:
            staff.append({"name": nm, "role": e.get("role") or ""})

    characters = []
    for e in (m.get("characters") or {}).get("edges", []):
        node = e.get("node") or {}
        nm = (node.get("name") or {}).get("full") or ""
        if not nm:
            continue
        vas = []
        for va in node.get("voiceActors") or []:
            van = (va.get("name") or {}).get("full") or ""
            if van:
                vas.append(van)
        characters.append({"name": nm, "role": e.get("role") or "", "va": vas})

    cover = (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or ""

    return {
        "id": m["id"],
        "id_mal": m.get("idMal"),
        "name": name,
        "name_jp": name_jp,
        "name_en": name_en,
        "summary": desc,
        "tags": tags,
        "tags_with_rank": tags_with_rank,
        "rating": (m.get("averageScore") or 0) / 10.0,
        "mean_score": (m.get("meanScore") or 0) / 10.0,
        "popularity": m.get("popularity") or 0,
        "favourites": m.get("favourites") or 0,
        "year": year,
        "air_date": air_date,
        "eps": m.get("episodes") or 0,
        "duration": m.get("duration") or 0,
        "status": m.get("status") or "UNKNOWN",
        "format": m.get("format") or "UNKNOWN",
        "cover": cover,
        "banner": m.get("bannerImage") or "",
        "season": m.get("season") or "",
        "season_year": m.get("seasonYear") or year,
        "studios": studios,
        "staff": staff,
        "characters": characters,
        "name_cn": "",  # 后面补
        "tags_cn": [],
    }


def main():
    with open(CACHE, "r", encoding="utf-8") as f:
        cache = json.load(f)
    with open("data/bangumi_cn_mapping.json", "r", encoding="utf-8") as f:
        bangumi = json.load(f)

    cache_ids = set(a["id"] for a in cache)
    bangumi_ids = set(int(k) for k in bangumi["id_to_cn"].keys())
    missing = sorted(bangumi_ids - cache_ids)
    print(f"Cache 缺 {len(missing)} 部（Bangumi 有但 cache 没有）")

    # 备份
    if not os.path.exists(BAK):
        import shutil
        shutil.copy2(CACHE, BAK)
        print(f"[OK] 备份 {BAK}")

    # 批量拉
    added = 0
    failed = []
    for i in range(0, len(missing), 50):
        batch = missing[i:i+50]
        media = fetch_batch(batch)
        for m in media:
            try:
                entry = normalize(m)
                cache.append(entry)
                added += 1
            except Exception as e:
                print(f"  normalize error {m.get('id')}: {e}")
                failed.append(m.get("id"))
        if (i // 50) % 5 == 0:
            print(f"  进度 {i+50}/{len(missing)} 已加 {added}")
        time.sleep(1.5)

    print(f"\n[OK] 新增 {added} 部")
    print(f"[FAIL] 失败 {len(failed)} 部: {failed[:20]}")

    # 写回
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"[OK] 写回 {CACHE}")
    print(f"总条目: {len(cache)}")


if __name__ == "__main__":
    main()
