"""Verify compressed-only data and writable media paths for serverless hosts."""
import gzip
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ServerlessChecks(unittest.TestCase):
    def test_compressed_snapshot_needs_no_expansion(self):
        import data_loader
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "anime_cache.json"
            record = {"id": 1, "name_jp": "テスト", "format": "TV", "country": "JP"}
            with gzip.open(cache.with_suffix(".json.gz"), "wt", encoding="utf-8") as target:
                json.dump([record], target)
            with patch.object(data_loader, "CACHE_FILE", cache):
                self.assertEqual(data_loader.load_cache()[0]["id"], 1)
            self.assertFalse(cache.exists())

    def test_media_upload_and_retrieval_use_temporary_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"VERCEL": "1", "NEP_MEDIA_DIR": directory}):
                import app
                client = app.app.test_client()
                self.assertEqual(client.get("/api/bgm/list").status_code, 200)
                response = client.post("/api/background/upload", data={
                    "file": (io.BytesIO(b"image-fixture"), "测试背景.png")
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json["url"].startswith("/api/media/"))
                with client.get(response.json["url"]) as image_response:
                    self.assertEqual(image_response.data, b"image-fixture")
                response = client.post("/api/background/select", json={"file": "测试背景.png"})
                self.assertEqual(response.status_code, 200)
                current = client.get("/api/background/current").json["url"]
                with client.get(current) as image_response:
                    self.assertEqual(image_response.status_code, 200)
                rejected = client.post("/api/bgm/upload", data={
                    "file": (io.BytesIO(b"invalid"), "../escaped.mp3")
                })
                self.assertEqual(rejected.status_code, 400)
                self.assertFalse((Path(directory).parent / "escaped.mp3").exists())


if __name__ == "__main__":
    unittest.main()
