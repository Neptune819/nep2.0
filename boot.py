"""NEP 启动脚本 (生产环境 - Railway/Render/Heroku)

启动流程：
  1. 检测 data/anime_cache.json 是否存在
  2. 不存在 → 自动从 AniList 拉取（5-10分钟）
  3. 启动 Gunicorn（生产 WSGI 服务器）
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "data" / "anime_cache.json"


def has_cache() -> bool:
    """检查缓存是否存在且非空"""
    if not CACHE_FILE.exists():
        return False
    try:
        size_mb = CACHE_FILE.stat().st_size / 1024 / 1024
        return size_mb > 1  # 至少 1MB 才算有效
    except Exception:
        return False


def fetch_data():
    """从 AniList 拉取番剧数据"""
    print("=" * 60)
    print("[BOOT] 番剧数据不存在，开始拉取（约5-10分钟）")
    print("=" * 60)
    try:
        import data_loader
        # 用 AniList 配置：更快、并发3
        os.environ.setdefault("FETCH_DELAY", "0.2")
        os.environ.setdefault("FETCH_CONCURRENCY", "3")
        data_loader.fetch_all()
        print(f"[BOOT] ✅ 数据拉取完成: {CACHE_FILE}")
    except Exception as e:
        print(f"[BOOT] ❌ 数据拉取失败: {e}")
        print("[BOOT] 继续启动服务器，可能因数据缺失而报错")


def start_server():
    """启动 Gunicorn"""
    port = os.environ.get("PORT", "5000")
    cmd = [
        "gunicorn",
        "-w", "1",                # 1 worker（scikit-learn 占用内存大）
        "-k", "gthread",          # 多线程
        "--threads", "4",         # 4 线程
        "-b", f"0.0.0.0:{port}",  # 监听所有接口
        "--timeout", "120",       # 超时 120s
        "--access-logfile", "-",  # 日志到 stdout
        "app:app",
    ]
    print("=" * 60)
    print(f"[BOOT] 启动 Gunicorn: {' '.join(cmd)}")
    print("=" * 60)
    os.execvp("gunicorn", cmd)


if __name__ == "__main__":
    print("=" * 60)
    print("  NEP 番剧推荐系统 - 生产模式")
    print("=" * 60)
    print(f"[BOOT] Python: {sys.version}")
    print(f"[BOOT] 工作目录: {ROOT}")

    if has_cache():
        print(f"[BOOT] ✅ 缓存已存在 ({CACHE_FILE.stat().st_size/1024/1024:.1f} MB)")
    else:
        fetch_data()

    start_server()
