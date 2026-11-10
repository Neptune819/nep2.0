"""Copy Flask's static assets to Vercel's CDN output without changing their URLs."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
shutil.copytree(root / "static", root / "public" / "static", dirs_exist_ok=True)
print("NEP: static assets prepared for Vercel CDN")
