"""
批量翻译番剧简介 v5 — deep-translator 多线程并发

使用 deep-translator GoogleTranslator，5 线程并发，无延迟。
"""
import json
import re
import time
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

BASE = Path(__file__).parent.parent
CACHE_FILE = BASE / 'data' / 'anime_cache.json'
OUTPUT_FILE = BASE / 'data' / 'summary_translations.json'

CONCURRENCY = 5
SAVE_EVERY = 200
MAX_LEN = 1500


def clean_text(s: str) -> str:
    s = s.replace('<br>', '\n').replace('<i>', '').replace('</i>', '')
    s = s.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', "'")
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\(Source:\s*(AniList|Anime News Network|MAL|Wikipedia|Official Site|ANN|Crunchyroll|Funimation)\)', '', s)
    s = re.sub(r'\[Written by .*?\]', '', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r' {2,}', ' ', s)
    return s.strip()


def has_chinese(s: str) -> bool:
    return any('\u4e00' <= c <= '\u9fff' for c in s)


def is_japanese(s: str) -> bool:
    ja = sum(1 for c in s if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
    en = sum(1 for c in s if c.isascii() and c.isalpha())
    if en == 0:
        return True
    return ja > en


# 线程局部 translator（每个线程一个实例，避免共享状态问题）
import threading
_tls = threading.local()


def get_translator():
    if not hasattr(_tls, 'translator'):
        from deep_translator import GoogleTranslator
        _tls.translator = GoogleTranslator(source='en', target='zh-CN')
    return _tls.translator


def translate_one(sid: str, text: str) -> tuple[str, str] | None:
    """翻译单条。"""
    try:
        t = get_translator()
        result = t.translate(text)
        if result and has_chinese(result) and result != text:
            return (sid, result)
    except Exception:
        pass
    return None


def main():
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f'总条目: {len(data)}')

    pending = []
    for item in data:
        summary = (item.get('summary') or '').strip()
        if not summary or has_chinese(summary) or is_japanese(summary):
            continue
        pending.append((str(item['id']), summary, item.get('popularity', 0)))
    pending.sort(key=lambda x: -x[2])
    print(f'需要翻译: {len(pending)} (按热度)')

    existing = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        print(f'已有翻译: {len(existing)}')

    to_do = [(sid, clean_text(s)[:MAX_LEN]) for sid, s, _ in pending if sid not in existing]
    to_do = [(sid, s) for sid, s in to_do if s and len(s) >= 20]
    print(f'待翻译: {len(to_do)}')

    if not to_do:
        print('全部完成！')
        return

    total = len(to_do)
    done = 0
    ok = 0
    fail = 0
    lock = Lock()
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(translate_one, sid, text): sid for sid, text in to_do}

        for future in as_completed(futures):
            result = future.result()
            with lock:
                done += 1
                if result:
                    existing[result[0]] = result[1]
                    ok += 1
                else:
                    fail += 1

                if done % SAVE_EVERY == 0:
                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(existing, f, ensure_ascii=False, indent=2)

            if done % 100 == 0:
                with lock:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    print(f'[{done}/{total}] {done/total*100:.1f}% | '
                          f'OK:{ok} F:{fail} | {rate:.1f}条/s | ETA:{eta/60:.0f}分')

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f'\n完成！翻译:{ok} 失败:{fail} 总计:{len(existing)} 耗时:{elapsed/60:.1f}分')


if __name__ == '__main__':
    main()
