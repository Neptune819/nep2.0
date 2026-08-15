"""
扫描 anime_cache.json，识别低质量中文名翻译。
检测规则：
1. 包含年份后缀 (YYYY) —— 数据噪声
2. 拼音音译（拉丁字母转汉字）—— 硬翻译
3. 全英文/全拉丁字母 —— 未翻译
"""
import json
import re
from pathlib import Path

BASE = Path(r'C:\Users\SEASUN\Desktop\新建文件夹 (5)\新建文件夹 (5)')
CACHE_FILE = BASE / 'data' / 'anime_cache.json'

with open(CACHE_FILE, encoding='utf-8') as f:
    data = json.load(f)

print(f'总番剧数: {len(data)}')

# 年份后缀
year_suffix_re = re.compile(r'[(（]\s*(19|20)\d{2}\s*[)）]')

# 全英文字母+空格+数字+括号
all_letters_re = re.compile(r'^[A-Za-z\s\.\-\d\(\)（）]+$')

# 拼音音译常见字符集（拉丁字母逐字母映射到中文产生的字符）
pinyin_chars = set('弗尔阿伊乌恩克姆斯特奥欧韦德海尔赫金莱蒙纳帕普奇萨塔瓦维沃希雅泽兹')

# 检测是否为拼音音译：
# 1) 含 2+ 个空格分隔的词（典型音译模式）
# 2) 拼音字符占比 >= 35% 且不含常用汉字
# 3) 整体长度 >= 4
def looks_like_pinyin(cn):
    parts = cn.split()
    if len(parts) < 2:
        return False
    pinyin_count = sum(1 for c in cn if c in pinyin_chars)
    if len(cn) >= 4 and pinyin_count / len(cn) >= 0.35:
        common_words = set('的了一是在我有和就都但也这那一个上下来过他你么说们')
        has_common = any(c in common_words for c in cn)
        return not has_common
    return False

count_year = 0
count_pinyin = 0
count_all_letters = 0
samples = {'year': [], 'pinyin': [], 'all_letters': []}

for a in data:
    cn = (a.get('name_cn') or '').strip()
    if not cn:
        continue

    if year_suffix_re.search(cn):
        count_year += 1
        if len(samples['year']) < 15:
            samples['year'].append((a['id'], cn, a.get('name_en', '')))
        continue

    if all_letters_re.match(cn):
        count_all_letters += 1
        if len(samples['all_letters']) < 15:
            samples['all_letters'].append((a['id'], cn, a.get('name_en', '')))
        continue

    if looks_like_pinyin(cn):
        count_pinyin += 1
        if len(samples['pinyin']) < 20:
            samples['pinyin'].append((a['id'], cn, a.get('name_en', '')))

print(f'\n=== 检测结果 ===')
print(f'年份后缀 (噪声):   {count_year}')
print(f'纯英文字母:         {count_all_letters}')
print(f'拼音音译（硬翻）:   {count_pinyin}')
print(f'总低质量:           {count_year + count_all_letters + count_pinyin}')

print(f'\n=== 年份后缀示例 ===')
for sid, cn, en in samples['year']:
    print(f'  [{sid}] {cn!r}   ←  原名: {en!r}')

print(f'\n=== 拼音音译示例 ===')
for sid, cn, en in samples['pinyin']:
    print(f'  [{sid}] {cn!r}   ←  原名: {en!r}')

print(f'\n=== 纯英文字母示例 ===')
for sid, cn, en in samples['all_letters']:
    print(f'  [{sid}] {cn!r}   ←  原名: {en!r}')