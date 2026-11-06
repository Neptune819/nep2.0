"""Import a public Bangumi user's completed anime into the local AniList catalogue.

Only exact title matches are accepted automatically. Similar titles are returned
for review so that a remake, sequel, or different season is not silently marked
as watched.
"""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
import re
import unicodedata
from urllib.parse import quote

import requests

import data_loader


API_BASE = "https://api.bgm.tv/v0/users"
USER_AGENT = "Neptune19/NEP/2.0 (https://github.com/Neptune-ux-sys/nep2.0)"
MAX_COLLECTIONS = 5000
_USERNAME_PATTERN = re.compile(r"^[\w-]{1,64}$", re.UNICODE)


class BangumiImportError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(ch for ch in value if unicodedata.category(ch)[0] in "LN")


def _anime_summary(anime: dict, rating: int = 0, subject_id: int | None = None) -> dict:
    return {
        "id": int(anime["id"]),
        "name": anime.get("name") or "",
        "name_cn": data_loader.display_name_cn(anime),
        "image": anime.get("cover") or "",
        "year": anime.get("year") or anime.get("season_year") or 0,
        "format": anime.get("format") or "",
        "tags": (anime.get("tags") or [])[:20],
        "tags_cn": (anime.get("tags_cn") or [])[:20],
        "rating": rating,
        "user_rating": rating or None,
        "bgm_subject_id": subject_id,
    }


def _local_index(catalogue: list[dict]) -> tuple[dict[str, list[dict]], dict[str, set[str]]]:
    exact = defaultdict(list)
    bigrams = defaultdict(set)
    for anime in catalogue:
        names = {
            normalize_title(anime.get(key) or "")
            for key in ("name", "name_cn", "name_en", "name_jp")
        }
        names.add(normalize_title(data_loader.display_name_cn(anime)))
        names.update(normalize_title(alias) for alias in (anime.get("name_aliases") or []))
        for name in names - {""}:
            exact[name].append(anime)
            for i in range(len(name) - 1):
                bigrams[name[i:i + 2]].add(name)
    return dict(exact), dict(bigrams)


def _year(subject: dict) -> int | None:
    match = re.match(r"^(\d{4})", str(subject.get("date") or ""))
    return int(match.group(1)) if match else None


def _choose_exact(anime_list: list[dict], year: int | None) -> list[dict]:
    unique = {int(a["id"]): a for a in anime_list}
    values = list(unique.values())
    if len(values) > 1 and year:
        same_year = [a for a in values if abs(int(a.get("year") or a.get("season_year") or 0) - year) <= 1]
        if same_year:
            values = same_year
    return values


def _suggest(names: list[str], year: int | None, exact: dict, bigrams: dict) -> list[dict]:
    scores = {}
    for name in names:
        possible = set()
        for i in range(len(name) - 1):
            possible.update(bigrams.get(name[i:i + 2], ()))
        # Keep fuzzy search bounded for generic short names.
        if len(possible) > 1200:
            continue
        for alias in possible:
            if abs(len(alias) - len(name)) > max(5, len(name) // 3):
                continue
            similarity = SequenceMatcher(None, name, alias).ratio()
            if similarity < 0.77:
                continue
            for anime in exact[alias]:
                aid = int(anime["id"])
                anime_year = int(anime.get("year") or anime.get("season_year") or 0)
                if year and anime_year and abs(anime_year - year) > 3:
                    continue
                candidate_score = similarity - (0.03 * abs(anime_year - year) if year and anime_year else 0)
                if candidate_score > scores.get(aid, (-1, None))[0]:
                    scores[aid] = (candidate_score, anime)
    ordered = sorted(scores.values(), key=lambda item: item[0], reverse=True)
    return [item[1] for item in ordered[:5]]


def _match_collection(item: dict, exact: dict, bigrams: dict) -> tuple[str, dict]:
    subject = item.get("subject") or {}
    subject_id = int(item.get("subject_id") or subject.get("id") or 0)
    title = subject.get("name_cn") or subject.get("name") or f"Bangumi #{subject_id}"
    rating = int(item.get("rate") or 0)
    if rating < 0 or rating > 10:
        rating = 0
    year = _year(subject)
    names = list(dict.fromkeys(filter(None, (normalize_title(subject.get("name") or ""), normalize_title(subject.get("name_cn") or "")))))
    candidates = {}
    for name in names:
        for anime in exact.get(name, ()):
            candidates[int(anime["id"])] = anime
    exact_matches = _choose_exact(list(candidates.values()), year)
    if len(exact_matches) == 1:
        return "matched", _anime_summary(exact_matches[0], rating, subject_id)

    common = {"bgm_subject_id": subject_id, "name": title, "rating": rating, "year": year}
    if exact_matches:
        return "ambiguous", {**common, "reason": "同名作品有多个版本，请确认", "candidates": [_anime_summary(a, rating, subject_id) for a in exact_matches[:5]]}
    suggestions = _suggest(names, year, exact, bigrams) if names else []
    if suggestions:
        return "ambiguous", {**common, "reason": "未找到完全一致的标题，请确认相近作品", "candidates": [_anime_summary(a, rating, subject_id) for a in suggestions]}
    return "unmatched", {**common, "reason": "本地片库中未找到对应作品"}


def import_public_watched(username: str, catalogue: list[dict]) -> dict:
    username = (username or "").strip()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise BangumiImportError("请输入有效的 Bangumi 用户名或数字 UID", 400)

    exact, bigrams = _local_index(catalogue)
    url = f"{API_BASE}/{quote(username, safe='')}/collections"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    matched, ambiguous, unmatched = [], [], []
    offset, total = 0, None
    session = requests.Session()
    while total is None or offset < total:
        try:
            response = session.get(
                url,
                params={"subject_type": 2, "type": 2, "limit": 50, "offset": offset},
                headers=headers,
                timeout=15,
            )
        except requests.RequestException as exc:
            raise BangumiImportError("无法连接 Bangumi API，请稍后重试") from exc
        if response.status_code == 404:
            raise BangumiImportError("Bangumi 用户不存在，或公开收藏不可访问", 404)
        if response.status_code == 429:
            raise BangumiImportError("Bangumi API 请求过于频繁，请稍后再试", 429)
        if not response.ok:
            raise BangumiImportError(f"Bangumi API 返回 HTTP {response.status_code}")
        try:
            page = response.json()
            entries = page["data"]
            total = int(page["total"])
        except (ValueError, KeyError, TypeError) as exc:
            raise BangumiImportError("Bangumi API 返回的数据格式不正确") from exc
        if total > MAX_COLLECTIONS:
            raise BangumiImportError(f"公开看过条目超过 {MAX_COLLECTIONS} 项，暂无法一次导入", 400)
        if not entries:
            break
        for item in entries:
            kind, value = _match_collection(item, exact, bigrams)
            {"matched": matched, "ambiguous": ambiguous, "unmatched": unmatched}[kind].append(value)
        offset += len(entries)

    return {
        "username": username,
        "total": total or 0,
        "matched": matched,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "counts": {"matched": len(matched), "ambiguous": len(ambiguous), "unmatched": len(unmatched)},
        "note": "仅导入公开的动画「看过」收藏；私有收藏需要 Bangumi 授权。相近标题须手动确认。",
    }
