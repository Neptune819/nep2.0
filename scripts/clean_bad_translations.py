"""
清理 anime_cache.json 中的低质量中文名翻译。
规则：
1. 删除年份后缀 + 音译（最严重，约 3300 部）
2. 删除拼音音译（拉丁字母逐字母映射，约 1300 部）
3. 纯英文字母名保留（这些是合理的英文原名）

策略：将 name_cn 设为空，让 display_name_cn() 自动回退到 name_en / name_jp。
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

# 全英文字母+空格+数字+括号（保留不动）
all_letters_re = re.compile(r'^[A-Za-z\s\.\-\d\(\)（）]+$')

# 拼音字符集
pinyin_chars = set('弗尔阿伊乌恩克姆斯特奥欧韦德海尔赫金莱蒙纳帕普奇萨塔瓦维沃希雅泽兹')

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

cleaned_year = 0
cleaned_pinyin = 0
samples_kept = []
samples_cleaned = []

for a in data:
    cn = (a.get('name_cn') or '').strip()
    if not cn:
        continue

    should_clean = False
    reason = None

    if year_suffix_re.search(cn):
        should_clean = True
        reason = '年份后缀（音译）'
        cleaned_year += 1
    elif looks_like_pinyin(cn):
        should_clean = True
        reason = '拼音音译'
        cleaned_pinyin += 1

    if should_clean:
        # 记录要清理的样本
        if len(samples_cleaned) < 10:
            samples_cleaned.append({
                'id': a['id'],
                'before': cn,
                'name_en': a.get('name_en', ''),
                'reason': reason,
            })
        # 清空 name_cn，让 display_name_cn 回退到 name_en
        a['name_cn'] = ''

print(f'\n=== 清理统计 ===')
print(f'清理年份后缀:   {cleaned_year}')
print(f'清理拼音音译:   {cleaned_pinyin}')
print(f'总清理:         {cleaned_year + cleaned_pinyin}')

print(f'\n=== 清理示例 ===')
for s in samples_cleaned:
    print(f'  [{s["id"]}] {s["before"]!r}')
    print(f'       ↓ 改为空，回退到原名: {s["name_en"]!r}')
    print(f'       原因: {s["reason"]}')

# 写入清理后的数据
print(f'\n正在写入...')
with open(CACHE_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'✅ 已写入 {CACHE_FILE}')