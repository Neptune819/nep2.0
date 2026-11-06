"""Targeted offline checks for Bangumi collection import and global filters."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
import bangumi_import


class FakeResponse:
    status_code = 200
    ok = True

    def json(self):
        return {
            "total": 2,
            "data": [
                {"subject_id": 253, "subject_type": 2, "type": 2, "rate": 9,
                 "subject": {"name": "カウボーイビバップ", "name_cn": "星际牛仔", "date": "1998-04-03"}},
                {"subject_id": 1234, "subject_type": 2, "type": 2, "rate": 0,
                 "subject": {"name": "非本地作品", "name_cn": "非本地作品", "date": "2000-01-01"}},
            ],
        }


class BangumiImportChecks(TestCase):
    def test_public_collection_is_paginated_and_unmatched_is_reported(self):
        catalogue = [{"id": 1, "name": "Cowboy Bebop", "name_jp": "カウボーイビバップ",
                      "name_cn": "星际牛仔", "year": 1998, "tags": ["Space"], "tags_cn": ["太空"]}]
        with patch("bangumi_import.requests.Session") as session_class:
            session_class.return_value.get.return_value = FakeResponse()
            result = bangumi_import.import_public_watched("sai", catalogue)
            self.assertEqual(result["counts"], {"matched": 1, "ambiguous": 0, "unmatched": 1})
            self.assertEqual(result["matched"][0]["rating"], 9)
            self.assertEqual(result["matched"][0]["id"], 1)
            self.assertEqual(result["unmatched"][0]["bgm_subject_id"], 1234)
            params = session_class.return_value.get.call_args.kwargs["params"]
            self.assertEqual(params["type"], 2)
            self.assertEqual(params["subject_type"], 2)

    def test_global_filters_use_full_tags_and_maintain_pagination(self):
        client = app.app.test_client()
        baseline = client.get("/api/recommend/anime?id=1&limit=12")
        self.assertEqual(baseline.status_code, 200)
        first_id = baseline.json["results"][0]["id"]
        filtered = client.get(f"/api/recommend/anime?id=1&limit=12&exclude_ids={first_id}&min_year=2000")
        self.assertEqual(filtered.status_code, 200)
        self.assertNotIn(first_id, [item["id"] for item in filtered.json["results"]])
        self.assertTrue(all((item["year"] or 0) >= 2000 for item in filtered.json["results"]))
        self.assertGreaterEqual(filtered.json["total"], len(filtered.json["results"]))

    def test_excluded_tag_is_checked_beyond_public_eight_tag_preview(self):
        anime = {"id": 7, "year": 2020, "tags": [f"Tag{i}" for i in range(10)] + ["Mecha"]}
        recommender = SimpleNamespace(_id_to_idx={7: 0}, anime_list=[anime])
        preview = {"id": 7, "year": 2020, "tags": anime["tags"][:8]}
        self.assertEqual(app._filter_recommendations([preview], (set(), {"mecha"}, 0), recommender), [])


if __name__ == "__main__":
    main()
