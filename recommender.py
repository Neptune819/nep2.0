"""
recommender.py
================
番剧推荐器（两阶段：tag 向量召回 + 多因子精排）

v1.2 改动：
    - WEIGHTS 调整（multi_factor.py）+ 质量门槛（推荐质量 ↑）
    - 续集检测（recommend_by_anime_with_sequels）
    - trending 修复（season_year 优先 + _format_result 补 season/season_year）
    - VA tab 接口（search_voice_actors / get_anime_by_va）
    - _format_result 用 display_name_cn 做名称 fallback
    - get_all_tags 返回中文 tag

对外接口：
    recommend_by_anime(id, top_k)              - 模式 1（不含续集）
    recommend_by_anime_with_sequels(id, top_k) - 模式 1（含续集行）
    recommend_by_history(history, top_k)       - 模式 2
    recommend_by_tags(tags, top_k)             - 模式 3
    recommend_trending(limit, year, season)    - 本季热门
    get_anime(id)                              - 查单部
    get_all_tags()                             - 取热门标签
    search_voice_actors(q)                     - 搜声优
    get_anime_by_va(name)                      - 声优 → 番剧列表
    set_weights(dict)                          - 调权重
"""
import math
import re
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.preprocessing import normalize
from sklearn.neighbors import NearestNeighbors

import data_loader
import multi_factor
from discovery_engine import DiscoveryEngine
from psych_profile import R18_TAGS


# 标签召回时多取几倍候选，给精排留余地
RECALL_MULTIPLIER = 20  # top_k=10 -> 召回 200

# 续集归一化：去掉 "Season 2" / "Part 2" / "Cour 2" / "第2期" / "S2" / "II" / "Ⅱ" / "(2024)" / "OVA" 等
_SEQUEL_STRIP_RE = re.compile(
    r"\s*(?:"
    r"Season\s*\d+|Part\s*\d+|Cour\s*\d+|[Ss]\d+|"  # Season 2 / Part 3 / Cour 2 / S2
    r"\d+(?:st|nd|rd|th)\s+Season|"        # 2nd Season / 3rd Season
    r"第\s*\d+\s*[期季幕章]|"                # 第2期 / 第3季
    r"\(\s*\d{4}\s*\)|"                     # (2024)
    r"\b(?:OVA|OAD|Special|Movie|Recap|Final)\b|"  # OVA / OAD / Special / Movie
    r"[IVXLCDM]+\b|"                        # ASCII 罗马数字: II, III, IV, V 等
    r"[Ⅰ-ⅿ]+"                               # Unicode 罗马数字: Ⅱ, Ⅲ, Ⅳ 等
    r")\s*$",
    re.IGNORECASE,
)


class AnimeRecommender:
    """番剧推荐器。初始化即建好索引（13k 数据 < 1 秒）。"""

    def __init__(self, cache=None):
        self.anime_list = cache if cache is not None else data_loader.load_cache()
        self.weights = multi_factor.WEIGHTS
        self._build_index()
        self._build_va_index()
        # 预排序：按人气升序（pop 越小越热门），tag 搜索 hot-fill 用
        self._by_popularity = sorted(self.anime_list,
                                     key=lambda a: a.get("popularity") or 999999)
        # 初始化发现型推荐引擎
        self._discovery_engine = DiscoveryEngine(self.anime_list)
        print(f"[OK] 推荐器就绪：{len(self.anime_list)} 部番剧, "
              f"{len(self._tag_to_idx)} 个 tag, {len(self._va_index)} 位声优")

    # ========== 索引构建 ==========
    def _build_index(self):
        """建 tag-rank 矩阵 + NearestNeighbors 模型。"""
        from collections import Counter
        tag_counter = Counter()
        for a in self.anime_list:
            for t in a.get("tags_with_rank") or []:
                tag_counter[t["name"]] += 1
        sorted_tags = sorted(tag_counter.items(), key=lambda x: (-x[1], x[0]))
        self._tag_to_idx = {name: i for i, (name, _) in enumerate(sorted_tags)}
        self._idx_to_tag = [name for name, _ in sorted_tags]

        rows, cols, vals = [], [], []
        for r, a in enumerate(self.anime_list):
            for t in a.get("tags_with_rank") or []:
                name = t.get("name")
                if name in self._tag_to_idx:
                    rows.append(r)
                    cols.append(self._tag_to_idx[name])
                    vals.append((t.get("rank") or 0) / 100.0)
        n_anime = len(self.anime_list)
        n_tags = len(self._tag_to_idx)
        self.tag_matrix = csr_matrix(
            (vals, (rows, cols)),
            shape=(n_anime, n_tags),
            dtype=np.float32,
        )
        self.tag_matrix = normalize(self.tag_matrix, norm="l2", axis=1)

        self._id_to_idx = {a["id"]: i for i, a in enumerate(self.anime_list)}
        self._idx_to_id = [a["id"] for a in self.anime_list]

        self.nn = NearestNeighbors(
            metric="euclidean",
            n_neighbors=min(RECALL_MULTIPLIER * 12 + 1, n_anime),
            algorithm="brute",
            n_jobs=-1,
        )
        self.nn.fit(self.tag_matrix)

    def _build_va_index(self):
        """建 VA 索引：va_name -> [{anime_id, year, popularity, favourites}, ...]"""
        from collections import defaultdict
        idx = defaultdict(list)
        for a in self.anime_list:
            for ch in (a.get("characters") or []):
                for va in (ch.get("va") or []):
                    if isinstance(va, str) and va.strip():
                        idx[va].append({
                            "anime_id":    a["id"],
                            "year":        a.get("year") or a.get("season_year") or 0,
                            "popularity":  a.get("popularity") or 0,
                            "favourites":  a.get("favourites") or 0,
                        })
        self._va_index = dict(idx)
        # 预计算每个 VA 的"加权热度"（用于排序候选池子）
        self._va_score = {
            va: sum(1 + math.log10(x["favourites"] + 1) for x in items)
            for va, items in idx.items()
        }

    def set_weights(self, weights: dict):
        """运行时调权重。例如：recommender.set_weights({"rating": 0.25})"""
        self.weights = {**multi_factor.WEIGHTS, **weights}

    # ========== 召回（粗排）==========
    def _recall(self, query_vector, n=200) -> tuple[list, dict]:
        n = min(n, len(self.anime_list))
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        distances, indices = self.nn.kneighbors(query_vector, n_neighbors=n)
        tag_sims = {}
        candidates = []
        for dist, idx in zip(distances[0], indices[0]):
            cos = max(0.0, 1.0 - (dist ** 2) / 2.0)
            aid = self._idx_to_id[idx]
            tag_sims[aid] = cos
            candidates.append(self.anime_list[idx])
        return candidates, tag_sims

    def _user_vector(self, history) -> csr_matrix:
        """构建用户偏好向量
        
        评分逻辑：
        - 用户打分：使用用户评分
        - 未打分（rating=0）：使用番剧本身的bangumi评分
        - 权重公式：(rating - 5) / 5，5分以下为负，5分以上为正
        """
        rows, weights = [], []
        for h in history:
            aid = h.get("id")
            rating = h.get("rating", 0)
            
            # 如果用户没有打分，使用番剧本身的bangumi评分
            if rating == 0 and aid in self._id_to_idx:
                anime = self.anime_list[self._id_to_idx[aid]]
                rating = anime.get("mean_score") or 5
            
            if aid in self._id_to_idx and rating is not None:
                w = (rating - 5) / 5
                rows.append(self._id_to_idx[aid])
                weights.append(w)
        if not rows:
            return None
        sub = self.tag_matrix[rows]
        w_arr = np.array(weights, dtype=np.float32).reshape(-1, 1)
        weighted = sub.multiply(w_arr).tocsr()
        user_vec = np.asarray(weighted.sum(axis=0)).flatten()
        return csr_matrix(user_vec.reshape(1, -1), dtype=np.float32)

    def _pseudo_vector(self, tags: list[str], default_rank: int = 80) -> csr_matrix:
        n_tags = len(self._tag_to_idx)
        cols, vals = [], []
        # 中文 → 英文 反向映射（数据里 _tag_to_idx 只有英文）
        tag_trans = data_loader._get_tag_trans()
        cn_to_en = {cn: en for en, cn in tag_trans.items()}
        for t in tags:
            t = t.strip()
            # 先试原文，再试中文→英文
            en = t if t in self._tag_to_idx else cn_to_en.get(t, t)
            if en in self._tag_to_idx:
                cols.append(self._tag_to_idx[en])
                vals.append(default_rank / 100.0)
        if not cols:
            return None
        vec = csr_matrix(
            (vals, ([0] * len(cols), cols)),
            shape=(1, n_tags),
            dtype=np.float32,
        )
        return normalize(vec, norm="l2", axis=1)

    # ========== 续集检测 ==========
    @staticmethod
    def _normalize_title(title: str) -> str:
        """归一化 title 用于续集检测。"""
        if not title:
            return ""
        t = title.strip()
        # 反复 strip 直到不再变化（处理 "Title Season 2 OVA" 这种多重后缀）
        prev = None
        while prev != t:
            prev = t
            t = _SEQUEL_STRIP_RE.sub("", t).strip()
        # 去标点
        t = re.sub(r"[^\w一-鿿鿿぀-ゟ゠-ヿ]+", " ", t)
        # 去掉独立的罗马数字单词（II, III, IV 等，可能在标题中间）
        t = re.sub(r"\b[IVXLCDM]+\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"[Ⅰ-ⅿ]+", "", t)  # Unicode 罗马数字
        # 去掉多余的空格
        t = re.sub(r"\s+", " ", t).strip()
        return t.strip().lower()

    def find_sequels(self, seed: dict, candidates: list | None = None, limit: int = 12) -> list:
        """找 seed 的所有续集（同 base title + 排除自己）。"""
        base = self._normalize_title(seed.get("name") or seed.get("name_en") or seed.get("name_jp") or "")
        if not base:
            return []
        src = candidates if candidates is not None else self.anime_list
        seqs = []
        for a in src:
            if a["id"] == seed["id"]:
                continue
            cand_base = self._normalize_title(a.get("name") or a.get("name_en") or a.get("name_jp") or "")
            if not cand_base or cand_base != base:
                continue
            seqs.append(a)
        # 续集按 year 升序（S1→S2→S3）
        seqs.sort(key=lambda a: (a.get("year") or a.get("season_year") or 0, a.get("eps") or 0))
        return seqs[:limit]

    # ========== 三种推荐方法 ==========
    def recommend_by_anime(self, anime_id: int, top_k: int = 12,
                            style: str = "standard",
                            user_tuning: dict = None) -> list:
        """模式 1：找和这部番最像的 top_k 部（不含续集）。

        v3.0：支持 style（模式浮动）和 user_tuning（调参后处理）。
        """
        if anime_id not in self._id_to_idx:
            return []
        seed_idx = self._id_to_idx[anime_id]
        seed = self.anime_list[seed_idx]
        query_vec = self.tag_matrix[seed_idx]

        recall_n = min(top_k * RECALL_MULTIPLIER, len(self.anime_list))
        candidates, tag_sims = self._recall(query_vec, n=recall_n)

        query = multi_factor.build_query_from_anime(seed)
        # 排除种子自己和所有续集
        sequel_ids = {s["id"] for s in self.find_sequels(seed)}
        query["watched_ids"] |= {anime_id} | sequel_ids

        ranked = multi_factor.re_rank(candidates, query, tag_sims,
                                      weights=self.weights, top_k=top_k,
                                      style=style, user_tuning=user_tuning)
        return [self._format_result(r) for r in ranked]

    def recommend_by_anime_with_sequels(self, anime_id: int, top_k: int = 12,
                                          sequels_limit: int = 12) -> dict:
        """模式 1 增强版：返回 {main, sequels}，sequels 单独归类。"""
        if anime_id not in self._id_to_idx:
            return {"main": [], "sequels": []}
        seed = self.anime_list[self._id_to_idx[anime_id]]
        main = self.recommend_by_anime(anime_id, top_k=top_k)
        # 续集：直接搜全库（不只是召回池）
        sequels = self.find_sequels(seed, limit=sequels_limit)
        return {
            "main": main,
            "sequels": [self._format_anime(a) for a in sequels],
        }

    def recommend_by_history(self, history: list[dict], top_k: int = 12,
                              style: str = "standard",
                              user_tuning: dict = None) -> list:
        """模式 2：基于用户观看历史推荐。

        v3.0 流水线：
            数据加载 → 模式参数 → 心理模型(从历史构建) → 历史因子(40%) → 调参
        """
        user_vec = self._user_vector(history)
        if user_vec is None:
            return []

        recall_n = min(top_k * RECALL_MULTIPLIER, len(self.anime_list))
        candidates, tag_sims = self._recall(user_vec, n=recall_n)

        query = multi_factor.build_query_from_history(history, self.anime_list)
        if query is None:
            return []

        # 排除已观看番剧的所有续集
        watched_ids = query.get("watched_ids") or set()
        sequel_ids = set()
        for aid in watched_ids:
            if aid in self._id_to_idx:
                seed = self.anime_list[self._id_to_idx[aid]]
                sequel_ids.update(s["id"] for s in self.find_sequels(seed))
        query["watched_ids"] |= sequel_ids

        ranked = multi_factor.re_rank(candidates, query, tag_sims,
                                      weights=self.weights, top_k=top_k,
                                      style=style, user_tuning=user_tuning)
        return [self._format_result(r) for r in ranked]

    def recommend_by_tags(self, tags: list[str], top_k: int = 12,
                           style: str = "standard",
                           user_tuning: dict = None) -> list:
        """模式 3：基于标签推荐。

        v3.0：支持 style（模式浮动）和 user_tuning（调参后处理）。
        """
        pseudo_vec = self._pseudo_vector(tags)
        if pseudo_vec is None:
            return []

        # 召回阶段：大幅扩大候选池，让热门多tag番剧也有机会进来
        # 单tag番剧余弦相似度虚高（L2归一化），默认 RECALL_MULTIPLIER=20 不够
        recall_n = min(top_k * 60, len(self.anime_list))
        candidates, tag_sims = self._recall(pseudo_vec, n=recall_n)

        # 标签翻译
        tag_trans = data_loader._get_tag_trans()
        cn_to_en = {cn: en for en, cn in tag_trans.items()}
        query_en_set = set()
        for t in tags:
            t = t.strip()
            query_en_set.add(t if t in self._tag_to_idx else cn_to_en.get(t, t))
        n_query_tags = max(1, len(query_en_set))

        # 构建每个 anime 的英文 tag 集合
        adjusted_tag_sims = {}
        for cand in candidates:
            cid = cand["id"]
            original_sim = tag_sims.get(cid, 0.0)
            if original_sim <= 0:
                adjusted_tag_sims[cid] = original_sim
                continue
            anime_tags = set(cand.get("tags") or [])
            matched = len(query_en_set & anime_tags)
            n_anime_tags = len(anime_tags)
            match_ratio = matched / n_query_tags
            tag_richness = min(1.0, n_anime_tags / 5.0)
            if matched == 0:
                adjusted_tag_sims[cid] = 0.0
            else:
                adjusted_tag_sims[cid] = original_sim * match_ratio * tag_richness

        # ---- v1.3: 补充热门番剧 ----
        # 余弦相似度召回偏向单tag冷门番剧，热门番剧被挤出。
        # 补充：按人气排名取前 3000 热门，从中选至少匹配1个tag的加入候选。
        existing_ids = {c["id"] for c in candidates}
        popular_supplement = []
        # 从人气榜取 top 3000（已经按 popularity 排序过）
        top_3k = self._by_popularity[:3000]
        for a in top_3k:
            if a["id"] in existing_ids:
                continue
            anime_tags = set(a.get("tags") or [])
            matched = len(query_en_set & anime_tags)
            if matched == 0:
                continue
            pop = a.get("popularity") or 0
            # 只填充有一定人气的（pop < 50000）
            if pop <= 0 or pop > 50_000:
                continue
            n_anime_tags = len(anime_tags)
            match_ratio = matched / n_query_tags
            tag_richness = min(1.0, n_anime_tags / 5.0)
            # 估算 tag 相似度（热门番剧有质量保证，给一定的 tag 基础分）
            estimated_sim = match_ratio * 0.25
            adjusted_tag_sims[a["id"]] = estimated_sim * match_ratio * tag_richness
            popular_supplement.append(a)
        candidates = candidates + popular_supplement

        query = multi_factor.build_query_from_tags()

        ranked = multi_factor.re_rank(candidates, query, adjusted_tag_sims,
                                      weights=multi_factor.TAG_SEARCH_WEIGHTS,
                                      top_k=top_k, mode="tags",
                                      style=style, user_tuning=user_tuning)
        return [self._format_result(r) for r in ranked]

    # ========== 发现型推荐 ==========
    def recommend_discovery(self, anime_id: int = None,
                            history: list[dict] = None,
                            tags: list[str] = None,
                            limit: int = 50,
                            exclude_ids: set = None,
                            style: str = "standard",
                            seed: int = None) -> dict:
        """发现型推荐：推荐冷门佳作、经典老番、口味盲区

        参数：
            anime_id: 种子番剧ID（模式1）
            history: 观看历史（模式2）
            tags: 标签列表（模式3）
            limit: 总推荐数量
            exclude_ids: 已推荐过的番剧ID集合（用于去重）
            style: 推荐风格 - explore(探索型), standard(标准型), conservative(保守型)
            seed: 随机种子（用于每日推荐等需要固定结果的场景）

        返回：
            {
                "underrated": [...],  # 被低估佳作
                "vintage": [...],     # 经典老番
                "blind_spot": [...],  # 口味盲区
                "summary": "...",     # 推荐总结
            }
        """
        if exclude_ids is None:
            exclude_ids = set()

        # 如果提供了种子，设置随机状态
        if seed is not None:
            import random
            random.seed(seed)

        # 构建心理画像
        psych_profile = None
        user_tags = set()

        if anime_id and anime_id in self._id_to_idx:
            seed = self.anime_list[self._id_to_idx[anime_id]]
            psych_profile = multi_factor.ComprehensivePsychProfile()
            psych_profile.build_from_anime(seed)
            user_tags = set(seed.get("tags") or [])
        elif history:
            # 基于历史中评分最高的番剧构建画像
            id_to_anime = {a["id"]: a for a in self.anime_list}
            best_anime = None
            best_rating = 0
            for h in history:
                a = id_to_anime.get(h.get("id"))
                if a and (h.get("rating") or 0) > best_rating:
                    best_anime = a
                    best_rating = h.get("rating") or 0
            if best_anime:
                psych_profile = multi_factor.ComprehensivePsychProfile()
                psych_profile.build_from_anime(best_anime)
                user_tags = set(best_anime.get("tags") or [])
        elif tags:
            # 基于标签构建伪画像
            psych_profile = multi_factor.ComprehensivePsychProfile()
            psych_profile.build_from_anime({"tags": tags})
            user_tags = set(tags)

        # 调用发现型引擎
        result = self._discovery_engine.discover(
            psych_profile=psych_profile,
            user_tags=user_tags,
            total_limit=limit,
            exclude_ids=exclude_ids,
            style=style,
        )

        # 格式化结果
        result["underrated"] = [
            self._format_discovery_result(item) for item in result["underrated"]
        ]
        result["vintage"] = [
            self._format_discovery_result(item) for item in result["vintage"]
        ]
        result["blind_spot"] = [
            self._format_discovery_result(item) for item in result["blind_spot"]
        ]

        return result

    def _format_discovery_result(self, item: dict) -> dict:
        """格式化发现型推荐结果"""
        anime = item["anime"]
        discovery_type = item["discovery_type"]

        # 根据类型选择分数字段
        if discovery_type == "underrated":
            score = item.get("underrated_score", 0)
        elif discovery_type == "vintage":
            score = item.get("vintage_score", 0)
        else:
            score = item.get("blind_spot_score", 0)

        return {
            "id": int(anime["id"]),
            "name": anime.get("name") or "",
            "name_cn": data_loader.display_name_cn(anime),
            "name_en": anime.get("name_en") or "",
            "name_jp": anime.get("name_jp") or "",
            "tags": (anime.get("tags") or [])[:8],
            "tags_cn": (anime.get("tags_cn") or [])[:8],
            "rating": float(round(anime.get("mean_score") or 0, 1)),
            "popularity": anime.get("popularity") or 0,
            "favourites": anime.get("favourites") or 0,
            "year": int(anime["year"]) if anime.get("year") else None,
            "season": anime.get("season") or "",
            "format": anime.get("format") or "",
            "image": anime.get("cover") or "",
            "summary": (anime.get("summary") or "")[:200],
            "score": float(round(score, 4)),
            "discovery_type": discovery_type,
            "reason": item.get("reason", ""),
        }

    def recommend_trending(self, limit: int = 24, season: str | None = None,
                            year: int | None = None) -> list:
        """本季热门：按 consensus 因子排序。

        v1.2 修复：
          - year 过滤优先用 season_year（覆盖未开播的 FALL）
          - season 二次过滤（None 时不过滤，给所有季度）
          - mean_score 阈值降到 5.5；但全 0 分（未开播季）退化按 favourites 排序
        """
        candidates = self.anime_list
        if year is not None:
            candidates = [a for a in candidates
                          if (a.get("season_year") or a.get("year")) == year]
        if season is not None:
            candidates = [a for a in candidates if a.get("season") == season]
        # 检查是否有评分的数据
        scored = [a for a in candidates if (a.get("mean_score") or 0) >= 5.5]
        if scored:
            # 有评分 → 按 consensus 排
            scored.sort(
                key=lambda a: (a.get("mean_score") or 0) * math.log10((a.get("favourites") or 0) + 1) * 10,
                reverse=True,
            )
            candidates = scored
        else:
            # 全 0 分（未开播季）→ 退化按 favourites + popularity 排
            candidates.sort(
                key=lambda a: math.log10((a.get("favourites") or 0) + 1) * 100
                              - math.log10((a.get("popularity") or 1) + 1),
                reverse=True,
            )

        results = []
        for a in candidates[:limit]:
            score_val = (a.get("mean_score") or 0) / 10.0
            ms = a.get("mean_score") or 0
            reasons = []
            if ms > 0:
                reasons.append(f"⭐ {ms:.1f}/10")
            reasons.append(f"收藏 {a.get('favourites', 0)}")
            reasons.append(f"人气 #{a.get('popularity', 0)}")
            if not ms:
                reasons.append("未开播")
            results.append({
                "anime": a,
                "score": round(score_val, 4),
                "reasons": reasons,
            })
        return [self._format_result(r) for r in results]

    # ========== 声优 tab ==========
    def search_voice_actors(self, q: str, limit: int = 20) -> list:
        """搜声优：返回 [(name, weighted_score)]，按相关度+热度排。
        支持中文别名（花泽香菜 → Kana Hanazawa）。
        """
        q = (q or "").strip()
        if not q:
            return sorted(
                [(va, sc) for va, sc in self._va_score.items()],
                key=lambda x: -x[1]
            )[:limit]
        # 先把中文 query 翻成罗马字
        q_lower = q.lower()
        cn_to_en = data_loader._va_cn_to_en()
        canonical_romaji = cn_to_en.get(q) or q
        canonical_lower = canonical_romaji.lower()

        exact, prefix, contains = [], [], []
        for va, sc in self._va_score.items():
            vl = va.lower()
            # 也匹配中文别名
            va_cn = data_loader._VA_CN_ALIASES.get(va, "")
            if vl == canonical_lower or va_cn == q:
                exact.append((va, sc))
            elif vl.startswith(canonical_lower) or va_cn.startswith(q):
                prefix.append((va, sc))
            elif canonical_lower in vl or q in va_cn:
                contains.append((va, sc))
        ordered = sorted(exact, key=lambda x: -x[1]) + \
                  sorted(prefix, key=lambda x: -x[1]) + \
                  sorted(contains, key=lambda x: -x[1])
        return ordered[:limit]

    def get_anime_by_va(self, va_name: str, limit: int = 50) -> list:
        """声优 → 番剧列表，按 favourites 加权热度排序。支持中文别名。"""
        if not va_name:
            return []
        # 中文 → 罗马字
        cn_to_en = data_loader._va_cn_to_en()
        canonical = cn_to_en.get(va_name, va_name)
        items = self._va_index.get(canonical, [])
        if not items:
            return []
        # 按 favourites 降序
        items.sort(key=lambda x: -x["favourites"])
        seen = set()
        results = []
        for it in items:
            aid = it["anime_id"]
            if aid in seen:
                continue
            seen.add(aid)
            if aid in self._id_to_idx:
                results.append(self.anime_list[self._id_to_idx[aid]])
            if len(results) >= limit:
                break
        return [self._format_anime(a) for a in results]

    # ========== 辅助方法 ==========
    def get_anime(self, anime_id: int) -> dict | None:
        if anime_id in self._id_to_idx:
            return self.anime_list[self._id_to_idx[anime_id]]
        return None

    def get_all_tags(self) -> list[tuple[str, int]]:
        """返回 [(tag_cn 或 tag, count)]，优先用 tag_translations 翻译。过滤R18标签。"""
        from collections import Counter
        counter = Counter()
        for a in self.anime_list:
            for t in (a.get("tags") or []):
                # 过滤R18标签
                if t not in R18_TAGS:
                    counter[t] += 1
        tag_trans = data_loader._get_tag_trans()
        ordered = counter.most_common(100)
        return [(tag_trans.get(t, t), c) for t, c in ordered]

    # ========== 统一返回格式 ==========
    def _format_result(self, ranked: dict) -> dict:
        return self._format_anime(ranked["anime"], score=ranked["score"], reasons=ranked["reasons"])

    def _format_anime(self, a: dict, score: float | None = None, reasons: list | None = None) -> dict:
        return {
            "id":          int(a["id"]),
            "name":        a.get("name") or "",
            "name_cn":     data_loader.display_name_cn(a),
            "name_en":     a.get("name_en") or "",
            "name_jp":     a.get("name_jp") or "",
            "tags":        (a.get("tags") or [])[:8],
            "tags_cn":     (a.get("tags_cn") or [])[:8],
            "rating":      float(round(a.get("mean_score") or 0, 1)),
            "popularity":  a.get("popularity") or 0,
            "favourites":  a.get("favourites") or 0,
            "year":        int(a.get("year")) if a.get("year") else None,
            "season":      a.get("season") or "",
            "season_year": a.get("season_year") or None,
            "format":      a.get("format") or "",
            "status":      a.get("status") or "",
            "studios":     a.get("studios") or [],
            "image":       a.get("cover") or "",
            "summary":     (a.get("summary") or "")[:200],
            "score":       float(score) if score is not None else 0.0,
            "reasons":     list(reasons or []),
        }


# ========== 命令行测试入口 ==========
if __name__ == "__main__":
    print("Building recommender...")
    r = AnimeRecommender()
    print()

    print("=== 模式 1: 进击的巨人 (id=16498) ===")
    bundle = r.recommend_by_anime_with_sequels(16498, top_k=5)
    print(f"  续集 ({len(bundle['sequels'])}):")
    for x in bundle['sequels']:
        print(f"    - {x['name_cn']} ({x['year']})")
    print(f"  主推荐 ({len(bundle['main'])}):")
    for x in bundle['main']:
        print(f"    {x['name_cn'] or x['name']:30s} score={x['score']:.3f}  reasons={x['reasons']}")
    print()

    print("=== 模式 3: 标签 [Psychological, Thriller] ===")
    for x in r.recommend_by_tags(["Psychological", "Thriller"], top_k=5):
        print(f"  {x['name_cn'] or x['name']:30s} score={x['score']:.3f}")
