"""
一次性分析脚本：盘点 data/anime_cache.json
"""
import json
import sys
import io
from collections import Counter, defaultdict
from pathlib import Path

# 强制 UTF-8 输出（Windows 默认 GBK 会乱码）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

CACHE = Path("data/anime_cache.json")
LOG = Path("data/fetch_log.txt")

# ============ 加载 ============
print("加载缓存...")
with open(CACHE, "r", encoding="utf-8") as f:
    data = json.load(f)
n = len(data)
print(f"总条数: {n}\n")

# ============ 1. 字段完整度 ============
print("=" * 60)
print("[1] 字段完整度")
print("=" * 60)
key_fields = ["id", "name", "name_jp", "name_en", "summary", "tags", "rating",
              "popularity", "favourites", "year", "eps", "format", "status",
              "studios", "staff", "characters", "cover"]
for k in key_fields:
    miss = sum(1 for a in data if not a.get(k) or a.get(k) == 0 or a.get(k) == [])
    pct = miss / n * 100
    print(f"  {k:14s} 缺失/为0: {miss:5d} ({pct:5.1f}%)")

# ============ 2. 覆盖率推算 ============
print("\n" + "=" * 60)
print("[2] 覆盖率推算 (基于 fetch_log 的 lastPage)")
print("=" * 60)
# log 里的页数 → 实际总条数 = lastPage * 50
import re
log_text = LOG.read_text(encoding="utf-8")
# 匹配 "[SORT_NAME] page X/Y"
# 用 lastPage (Y) 来推算 AniList 该 sort 下的总条数
sort_totals = {}
for sort in ["ID", "ID_DESC", "POPULARITY_DESC", "FAVOURITES_DESC"]:
    # 找该 sort 块里最后出现的 "page X/Y"
    pattern = rf"\[{sort:20s}\] page \d+/(\d+)"
    matches = re.findall(pattern, log_text)
    if matches:
        last_page = max(int(m) for m in matches)
        # lastPage 是 AniList 的页数估计，但 100 页后是空的 → AniList 每个 sort 上限 ~5000
        # AniList 单 sort 上限就是 5000（100 页 × 50）
        # 但 lastPage 可能显示 100 即被截断
        sort_totals[sort] = min(last_page * 50, 5000)
        print(f"  sort={sort:20s} lastPage={last_page} → ~{sort_totals[sort]} 条")

# ID 升序 + ID_DESC 降序 = 老番 + 新番 = 几乎全覆盖 ID 维度
# POPULARITY_DESC = 热门 top5000
# FAVOURITES_DESC = 高收藏 top5000
# 去重后应该是 ID ∪ ID_DESC（基本 100% 覆盖 ID 排序的所有）
# + 一些 POPULARITY/FAVOURITES 漏掉的

# 我们的 4 个 sort 加起来理论上能覆盖多少 unique ID?
# AniList 总 anime 数（公开数据）约 30,000-35,000 条
# ID 排序可拿 5000 老 + 5000 新 = 10000 unique（但 ID 中段可能漏）

# ============ 3. "没人看" vs "没拉取" ============
print("\n" + "=" * 60)
print("[3] 区分 '没人看' vs '没拉取'")
print("=" * 60)
zero_pop = sum(1 for a in data if (a.get("popularity") or 0) == 0)
zero_fav = sum(1 for a in data if (a.get("favourites") or 0) == 0)
zero_rating = sum(1 for a in data if (a.get("rating") or 0) == 0)
low_pop = sum(1 for a in data if (a.get("popularity") or 0) < 100)
print(f"  popularity=0:  {zero_pop} ({zero_pop/n*100:.1f}%)  ← 缓存里有但确实没人看")
print(f"  favourites=0:  {zero_fav} ({zero_fav/n*100:.1f}%)")
print(f"  rating=0:      {zero_rating} ({zero_rating/n*100:.1f}%)")
print(f"  popularity<100:{low_pop} ({low_pop/n*100:.1f}%)")

# AniList 总 anime 数（根据 2024 公开统计约 30,000-35,000，2025 应该更多）
# 缓存 4900 多 = 远低于总池
# 但我们只拉了 4 个 sort，每个 sort top 5000
print(f"\n  缓存 {n} 条 vs AniList 总池 (估计 30000+):")
print(f"  → 覆盖率 ≈ {n/35000*100:.1f}% (按 35k 估) / {n/30000*100:.1f}% (按 30k 估)")

# ============ 4. format 分布 ============
print("\n" + "=" * 60)
print("[4] format 分布 (TV / Movie / OVA / ONA / TV_SHORT / SPECIAL / MUSIC)")
print("=" * 60)
fmt = Counter(a.get("format") for a in data)
for k, v in fmt.most_common():
    print(f"  {str(k):12s} {v:5d} ({v/n*100:5.1f}%)")

# ============ 5. year 分布 ============
print("\n" + "=" * 60)
print("[5] 年份分布")
print("=" * 60)
years = Counter(a.get("year") for a in data)
# 五年一段
bins = defaultdict(int)
for y, c in years.items():
    if not y:
        bins["未知"] += c
    else:
        bins[(y // 5) * 5] += c
for k in sorted(bins.keys(), key=str):
    if isinstance(k, int):
        print(f"  {k}-{k+4}    {bins[k]:5d}")
    else:
        print(f"  {k:10s} {bins[k]:5d}")

# ============ 6. status 分布 ============
print("\n" + "=" * 60)
print("[6] status 分布 (RELEASING / FINISHED / NOT_YET_RELEASED / CANCELLED / HIATUS)")
print("=" * 60)
st = Counter(a.get("status") for a in data)
for k, v in st.most_common():
    print(f"  {str(k):20s} {v:5d} ({v/n*100:5.1f}%)")

# ============ 7. top tags ============
print("\n" + "=" * 60)
print("[7] top 30 tags (按出现频次)")
print("=" * 60)
tag_counter = Counter()
for a in data:
    for t in a.get("tags", []):
        tag_counter[t] += 1
for tag, c in tag_counter.most_common(30):
    print(f"  {tag:25s} {c:5d}")

print(f"\n  共 {len(tag_counter)} 个不同 tag")

# ============ 8. 热门 vs 长尾 ============
print("\n" + "=" * 60)
print("[8] 热度分布 (按 popularity 分桶)")
print("=" * 60)
buckets = [(0, 0), (1, 100), (100, 1000), (1000, 10000), (10000, 50000), (50000, 999999)]
for lo, hi in buckets:
    if hi == 0:
        c = sum(1 for a in data if (a.get("popularity") or 0) == 0)
    else:
        c = sum(1 for a in data if lo <= (a.get("popularity") or 0) < hi)
    print(f"  popularity [{lo:6d}, {hi:6d}): {c:5d} ({c/n*100:5.1f}%)")
