"""
列出所有 419 个 tag，按字母排序，输出到 data/all_tags.txt
方便我对着写中英对照
"""
import json
from pathlib import Path

with open("data/anime_cache.json", "r", encoding="utf-8") as f:
    data = json.load(f)

tags = set()
for a in data:
    for t in a.get("tags", []):
        tags.add(t)

tags = sorted(tags)
print(f"共 {len(tags)} 个 tag")
out = Path("data/all_tags.txt")
with open(out, "w", encoding="utf-8") as f:
    for t in tags:
        f.write(t + "\n")
print(f"已写入 {out}")
