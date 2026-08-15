"""
scripts/fetch_data.py
======================
一键拉取所有 Bangumi 番剧数据。

用法:
    python scripts/fetch_data.py              # 拉完所有（~8.5k，5-10分钟）
    python scripts/fetch_data.py --no-resume  # 从头开始
    python scripts/fetch_data.py --delay 0.1  # 自定义请求间隔

环境变量（在 .env 里配）:
    FETCH_CONCURRENCY  — 并发数（默认 8）
    FETCH_DELAY        — 每次请求间隔（默认 0.15s）
"""
import sys
import argparse
from pathlib import Path

# 把项目根目录加到 sys.path，让 import data_loader 能找到
sys.path.insert(0, str(Path(__file__).parent.parent))

import data_loader


def main():
    parser = argparse.ArgumentParser(description="拉取 Bangumi 番剧数据")
    parser.add_argument(
        "--no-resume", action="store_true",
        help="不从已有缓存续拉（从头开始）"
    )
    parser.add_argument(
        "--delay", type=float, default=None,
        help="每次请求间隔（秒），覆盖 .env"
    )
    parser.add_argument(
        "--concurrency", "-c", type=int, default=None,
        help="并发数，覆盖 .env"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("[FETCH] Bangumi 番剧数据拉取器")
    print("=" * 60)

    try:
        anime = data_loader.fetch_all(
            concurrency=args.concurrency,
            delay=args.delay,
            resume=not args.no_resume,
        )
        print(f"\n[OK] 数据文件: {data_loader.CACHE_FILE}")
        print(f"     共 {len(anime)} 条")
        if anime:
            sample = anime[0]
            print(f"     示例: {sample.get('name_cn') or sample.get('name')} "
                  f"(评分: {sample.get('rating')}, 排名: {sample.get('rank')})")
            print(f"           tags: {sample.get('tags', [])[:5]}")
    except KeyboardInterrupt:
        print("\n[STOP] 中断。已保存的进度在 data/anime_cache.json")
        print("       下次跑同样命令会自动续拉。")
    except Exception as e:
        print(f"\n[ERROR] 出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
