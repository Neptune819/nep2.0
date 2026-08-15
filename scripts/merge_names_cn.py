"""
merge_names_cn.py
================
把 names_cn.json 合并到 anime_cache.json，给每部番补/更新 name_cn 字段。

用法：
    cd "C:/Users/lmhNe/Desktop/新建文件夹 (5)"
    python scripts/merge_names_cn.py
"""
import json
import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "data", "names_cn.json")
CACHE = os.path.join(BASE, "data", "anime_cache.json")
BAK = os.path.join(BASE, "data", "anime_cache.json.bak3")


def main():
    if not os.path.exists(SRC):
        print(f"[ERROR] 找不到 {SRC}")
        return
    if not os.path.exists(CACHE):
        print(f"[ERROR] 找不到 {CACHE}")
        return

    with open(SRC, "r", encoding="utf-8") as f:
        cn = json.load(f)
    print(f"[INFO] 加载 {len(cn)} 条中文名")

    with open(CACHE, "r", encoding="utf-8") as f:
        cache = json.load(f)
    print(f"[INFO] 主缓存共 {len(cache)} 部番剧")

    if not os.path.exists(BAK):
        shutil.copy2(CACHE, BAK)
        print(f"[OK] 备份到 {BAK}")

    # 注意：键是字符串（JSON 强制），要转 int 比较
    new_count = 0
    update_count = 0
    for d in cache:
        sid = str(d["id"])
        if sid in cn:
            old = d.get("name_cn") or ""
            new = cn[sid]
            if not old:
                new_count += 1
            elif old != new:
                update_count += 1
            d["name_cn"] = new

    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"[OK] 新增 {new_count} 部的中文名")
    print(f"[OK] 覆盖 {update_count} 部的中文名")
    print(f"[OK] 写入 {CACHE}")


if __name__ == "__main__":
    main()
