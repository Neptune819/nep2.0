"""NEP 启动脚本 (生产环境 - Railway/Render/Heroku)

启动流程：
  1. 检查数据缓存是否存在
  2. 不存在 → **后台线程**慢慢拉取（不阻塞服务器启动）
  3. 立即启动 Gunicorn（生产 WSGI 服务器）
  4. 数据未就绪时返回友好提示页面
"""
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "data" / "anime_cache.json"


def has_cache() -> bool:
    """检查缓存是否存在且非空"""
    if not CACHE_FILE.exists():
        return False
    try:
        size_mb = CACHE_FILE.stat().st_size / 1024 / 1024
        return size_mb > 1
    except Exception:
        return False


def fetch_data_background():
    """后台线程从 AniList 拉取番剧数据"""
    print("=" * 60)
    print("[BOOT-BG] 番剧数据不存在，后台开始拉取（约5-10分钟）")
    print("=" * 60)
    try:
        import data_loader
        os.environ.setdefault("FETCH_DELAY", "0.2")
        os.environ.setdefault("FETCH_CONCURRENCY", "3")
        data_loader.fetch_all()
        size = CACHE_FILE.stat().st_size / 1024 / 1024
        print(f"[BOOT-BG] ✅ 数据拉取完成 ({size:.1f} MB)")
    except Exception as e:
        print(f"[BOOT-BG] ❌ 数据拉取失败: {e}")


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
        size = CACHE_FILE.stat().st_size / 1024 / 1024
        print(f"[BOOT] ✅ 缓存已存在 ({size:.1f} MB)")
    else:
        # 后台拉数据（不阻塞启动）
        print("[BOOT] 启动后台数据拉取线程...")
        t = threading.Thread(target=fetch_data_background, daemon=True)
        t.start()
        print("[BOOT] 服务器先启动，数据慢慢拉")

    start_server()
