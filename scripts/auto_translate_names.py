"""
auto_translate_names.py
================
把剩余无 name_cn 的番剧自动音译填充。

策略：
1. 已有中文字符的名字 -> 直接用作 name_cn
2. 英文/罗马字名字 -> 用简单的字符映射音译成中文
3. 优先保留手译的高质量结果（已经做过的）
"""
import json
import os
import re
import unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "data", "anime_cache.json")
NAMES = os.path.join(BASE, "data", "names_cn.json")


# 简单的罗马字 -> 中文字符 映射（音译用）
ROMAJI_MAP = {
    'a': '阿', 'b': '布', 'c': '克', 'd': '德', 'e': '艾', 'f': '弗',
    'g': '格', 'h': '赫', 'i': '伊', 'j': '杰', 'k': '克', 'l': '尔',
    'm': '姆', 'n': '恩', 'o': '欧', 'p': '普', 'q': '丘', 'r': '尔',
    's': '斯', 't': '特', 'u': '乌', 'v': '维', 'w': '沃', 'x': '克',
    'y': '伊', 'z': '兹',
    'A': '亚', 'B': '比', 'C': '科', 'D': '德', 'E': '伊', 'F': '弗',
    'G': '格', 'H': '海', 'I': '艾', 'J': '杰', 'K': '克', 'L': '拉',
    'M': '马', 'N': '恩', 'O': '欧', 'P': '普', 'Q': '丘', 'R': '尔',
    'S': '斯', 'T': '特', 'U': '于', 'V': '维', 'W': '沃', 'X': '克',
    'Y': '伊', 'Z': '兹',
}


def has_cjk(s: str) -> bool:
    for c in s:
        if '一' <= c <= '鿿':
            return True
    return False


def is_pure_latin(s: str) -> bool:
    for c in s:
        if c.isalpha() and not c.isascii():
            return False
    return True


def transliterate(text: str, max_chars: int = 30) -> str:
    out = []
    last_was_space = False
    for c in text:
        if c in ROMAJI_MAP:
            out.append(ROMAJI_MAP[c])
            last_was_space = False
        elif c == ' ':
            if not last_was_space and out:
                out.append(' ')
                last_was_space = True
        elif c in '0123456789':
            out.append(c)
            last_was_space = False
        elif c in '-_:/':
            out.append(' ')
            last_was_space = True
    result = ''.join(out).strip()
    result = re.sub(r'\s+', ' ', result)
    return result[:max_chars]


def make_cn_name(anime: dict) -> str:
    name = (anime.get('name') or '').strip()
    name_en = (anime.get('name_en') or '').strip()
    name_jp = (anime.get('name_jp') or '').strip()

    if has_cjk(name):
        return name[:30]

    source = name_en or name
    if not source:
        source = name_jp

    if not source:
        return ""

    if is_pure_latin(source):
        result = transliterate(source)
        if result:
            yr = anime.get('year')
            if yr and str(yr).isdigit() and int(yr) > 2000:
                return f"{result} ({yr})"
            return result

    return transliterate(source) or source


def main():
    with open(CACHE, "r", encoding="utf-8") as f:
        cache = json.load(f)
    with open(NAMES, "r", encoding="utf-8") as f:
        names = json.load(f)
    print(f"加载 {len(names)} 条人工翻译")
    print(f"缓存 {len(cache)} 部番剧")

    new_count = 0
    auto_count = 0
    for a in cache:
        if a.get('name_cn'):
            continue
        sid = str(a["id"])
        if sid in names:
            a["name_cn"] = names[sid]
            new_count += 1
        else:
            cn = make_cn_name(a)
            if cn:
                a["name_cn"] = cn
                new_count += 1
                auto_count += 1

    print(f"新填充: {new_count} 部（其中自动音译: {auto_count}）")
    print(f"剩余无 name_cn: {sum(1 for a in cache if not a.get('name_cn'))}")

    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print("[OK] 写回缓存")


if __name__ == "__main__":
    main()
