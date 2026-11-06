"""Production startup for hosts with an ephemeral filesystem.

The public anime snapshot is stored in git as a compressed file. Expand it
before starting Gunicorn so a cold start does not depend on AniList being up.
"""

import gzip
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "data" / "anime_cache.json"
SNAPSHOT_FILE = ROOT / "data" / "anime_cache.json.gz"


def ensure_cache() -> None:
    if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 1024 * 1024:
        print(f"[BOOT] Anime cache ready: {CACHE_FILE.stat().st_size:,} bytes", flush=True)
        return

    if not SNAPSHOT_FILE.exists():
        raise FileNotFoundError(
            f"Neither {CACHE_FILE} nor {SNAPSHOT_FILE} exists. "
            "Bundle a compressed anime snapshot before deployment."
        )

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_FILE.with_suffix(".json.tmp")
    try:
        with gzip.open(SNAPSHOT_FILE, "rb") as source, temporary.open("wb") as target:
            shutil.copyfileobj(source, target)
        if temporary.stat().st_size <= 1024 * 1024:
            raise ValueError("Bundled anime snapshot is unexpectedly small")
        temporary.replace(CACHE_FILE)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"[BOOT] Expanded anime snapshot: {CACHE_FILE.stat().st_size:,} bytes", flush=True)


def start_server() -> None:
    port = int(os.environ.get("PORT", "5000"))
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid PORT: {port}")
    command = [
        "gunicorn",
        "-w", "1",
        "-k", "gthread",
        "--threads", "2",
        "-b", f"0.0.0.0:{port}",
        "--timeout", "120",
        "--access-logfile", "-",
        "app:app",
    ]
    print(f"[BOOT] Python {sys.version.split()[0]} | {' '.join(command)}", flush=True)
    os.execvp(command[0], command)


if __name__ == "__main__":
    ensure_cache()
    start_server()
