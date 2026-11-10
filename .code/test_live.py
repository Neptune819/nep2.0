"""Read-only smoke checks against the published NEP service."""
import json
import requests

BASE = "https://nep-anime-recommend.vercel.app"
session = requests.Session()
report = {}


def api(path, method="GET", **kwargs):
    response = session.request(method, BASE + path, timeout=90, **kwargs)
    response.raise_for_status()
    data = response.json()
    assert "error" not in data, (path, data)
    return data


for title in ("星际牛仔", "カウボーイビバップ", "Cowboy Bebop"):
    results = api("/api/search", params={"q": title})["results"]
    assert any(item["id"] == 1 for item in results), title
report["title_search_languages"] = 3

baseline = api("/api/recommend/anime", params={"id": 1, "limit": 6})["results"]
assert len(baseline) == 6
excluded = baseline[0]["id"]
filters = {"exclude_ids": str(excluded), "exclude_tags": "机战", "min_year": 2015}
filtered = api("/api/recommend/anime", params={"id": 1, "limit": 6, **filters})["results"]
assert filtered
assert all(a["id"] != excluded and (a.get("year") or 0) >= 2015 for a in filtered)
for anime in filtered:
    detail = api(f"/api/anime/{anime['id']}")
    # The detail endpoint wraps the catalogue object in `anime`.
    detail = detail.get("anime", detail)
    tags = {str(t).casefold() for t in detail.get("tags", [])}
    assert not tags.intersection({"mecha", "robots", "real robot", "super robot"})
report["anime_recommendations"] = len(baseline)
report["filtered_recommendations"] = len(filtered)

history = api("/api/recommend/history", "POST", json={
    "history": [{"id": 1, "rating": 9}, {"id": 5, "rating": 8}],
    "limit": 6, "exclude_ids": [1, 5, excluded], "min_year": 2015,
})["results"]
assert history and all(a["id"] not in {1, 5, excluded} and (a.get("year") or 0) >= 2015
                       for a in history)
report["history_recommendations"] = len(history)

for path in ("/api/bgm/list", "/api/background/list", "/api/background/current"):
    api(path)
report["media_endpoints"] = 3

imported = api("/api/bangumi/import", "POST", json={"username": "sai"})
assert imported["counts"]["matched"] > 0
assert sum(imported["counts"].values()) > 0
report["bangumi_import"] = imported["counts"]
print(json.dumps(report, ensure_ascii=False, indent=2))
