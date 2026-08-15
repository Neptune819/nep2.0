"""
discovery_engine.py
====================
发现型推荐引擎 - 帮助用户发现冷门佳作、经典老番、口味盲区

核心理念：
    推荐系统不应该只是"推荐用户会喜欢的"，
    而应该是"推荐用户会喜欢但自己不会发现的"。

三大发现维度：
    1. 被低估发现（Underrated）：评分高但人气相对较低
    2. 经典发现（Vintage）：年代较早但质量高
    3. 盲区发现（Blind Spot）：基于心理画像预测用户可能感兴趣的未接触类型
"""
import math
import random
import re
from psych_profile import ComprehensivePsychProfile, R18_TAGS, TAG_TO_PSYCH


# ============================================================
# 配置常量
# ============================================================

# 经典老番的年份阈值
VINTAGE_YEAR_THRESHOLD = 2010

# 口味盲区预测的标签组
TASTE_BLIND_SPOTS = {
    "action_to_sports": {
        "source_tags": ["Action", "Combat", "Martial Arts"],
        "target_tags": ["Sports", "Competition"],
        "reason": "热血战斗 → 竞技体育：同样的成长与奋斗，但更贴近现实",
    },
    "isekai_to_fantasy": {
        "source_tags": ["Isekai", "Reincarnation"],
        "target_tags": ["Fantasy", "High Fantasy", "Adventure"],
        "reason": "异世界 → 传统奇幻：同样的冒险体验，但世界观更完整",
    },
    "romance_to_healing": {
        "source_tags": ["Romance", "Love Triangle"],
        "target_tags": ["Healing", "Slice of Life", "Iyashikei"],
        "reason": "恋爱 → 治愈：同样温暖人心，但更轻松无压力",
    },
    "psychological_to_sci": {
        "source_tags": ["Psychological", "Thriller"],
        "target_tags": ["Sci-Fi", "Cyberpunk", "Dystopian"],
        "reason": "心理悬疑 → 硬科幻：同样烧脑，但探索更宏大的主题",
    },
    "comedy_to_daily": {
        "source_tags": ["Comedy", "Parody"],
        "target_tags": ["Slice of Life", "Daily Life"],
        "reason": "搞笑 → 日常：同样轻松，但更有生活气息",
    },
    "battle_to_strategy": {
        "source_tags": ["Action", "Combat", "Super Power"],
        "target_tags": ["Strategy Game", "Tactical", "Political"],
        "reason": "战斗 → 策略：同样需要智慧，但更考验脑力",
    },
    "school_to_music": {
        "source_tags": ["School", "Club", "High School"],
        "target_tags": ["Music", "Band", "Idol"],
        "reason": "校园 → 音乐：同样青春热血，但更注重艺术表达",
    },
    "dark_to_philosophical": {
        "source_tags": ["Dark", "Tragedy", "Gore"],
        "target_tags": ["Philosophical", "Psychology"],
        "reason": "黑暗 → 哲学：同样直面人性，但更注重思考而非冲击",
    },
}

# 续集检测正则（与recommender.py一致）
_SEQUEL_STRIP_RE = re.compile(
    r"\s*(?:"
    r"Season\s*\d+|Part\s*\d+|Cour\s*\d+|[Ss]\d+|"
    r"\d+(?:st|nd|rd|th)\s+Season|"
    r"第\s*\d+\s*[期季幕章]|"
    r"\(\s*\d{4}\s*\)|"
    r"\b(?:OVA|OAD|Special|Movie|Recap|Final)\b|"
    r"[IVXLCDM]+\b|"
    r"[''']\w*\s*(?:Season|Part|期|季)?"
    r")\s*$",
    re.IGNORECASE,
)


def _get_base_name(name: str) -> str:
    """提取作品基础名称（去除续集标识）"""
    if not name:
        return ""
    return _SEQUEL_STRIP_RE.sub("", name).strip()


def _build_series_groups(anime_list: list) -> dict:
    """构建系列作品分组，用于续集过滤"""
    groups = {}  # base_name -> [anime_ids]
    for anime in anime_list:
        name = anime.get("name") or anime.get("name_cn") or ""
        base = _get_base_name(name)
        if base and len(base) > 1:  # 忽略太短的名称
            if base not in groups:
                groups[base] = []
            groups[base].append(anime["id"])
    # 只保留有多个作品的系列
    return {k: v for k, v in groups.items() if len(v) > 1}


# ============================================================
# 发现型推荐引擎
# ============================================================
class DiscoveryEngine:
    """发现型推荐引擎"""

    def __init__(self, anime_list: list):
        self.anime_list = anime_list
        self._id_to_anime = {a["id"]: a for a in anime_list}
        self._build_indexes()

    def _build_indexes(self):
        """构建索引"""
        # 按评分排序
        self._by_rating = sorted(
            [a for a in self.anime_list if (a.get("mean_score") or 0) >= 7.0],
            key=lambda a: -(a.get("mean_score") or 0)
        )

        # 按年份排序
        self._by_year = sorted(
            self.anime_list,
            key=lambda a: a.get("year") or a.get("season_year") or 9999
        )

        # 按人气排名（popularity越大越热门）
        self._by_popularity = sorted(
            self.anime_list,
            key=lambda a: -(a.get("popularity") or 0)
        )

        # 构建人气排名映射（排名1=最热门）
        self._pop_rank = {}
        for i, anime in enumerate(self._by_popularity):
            self._pop_rank[anime["id"]] = i + 1

        # 构建系列分组
        self._series_groups = _build_series_groups(self.anime_list)
        # 构建 anime_id -> series_name 的映射
        self._id_to_series = {}
        for base_name, ids in self._series_groups.items():
            for aid in ids:
                self._id_to_series[aid] = base_name

        # 构建OVA/Movie映射（用于探索型过滤热门番的衍生作品）
        self._ova_related = set()  # 与热门主作品关联的OVA/Movie ID
        for base_name, ids in self._series_groups.items():
            # 检查这个系列中是否有热门主作品（排名前500）
            has_hot_main = False
            for aid in ids:
                if self._pop_rank.get(aid, 999999) <= 500:
                    anime = self._id_to_anime.get(aid)
                    if anime:
                        fmt = (anime.get("format") or "").upper()
                        # 主作品通常是TV格式
                        if fmt in ["TV", "TV_SHORT", ""]:
                            has_hot_main = True
                            break
            
            # 如果有热门主作品，标记该系列的OVA/Movie
            if has_hot_main:
                for aid in ids:
                    anime = self._id_to_anime.get(aid)
                    if anime:
                        fmt = (anime.get("format") or "").upper()
                        if fmt in ["OVA", "ONA", "MOVIE", "SPECIAL"]:
                            self._ova_related.add(aid)

        print(f"[Discovery] Indexes built: {len(self.anime_list)} anime, "
              f"{len(self._series_groups)} series groups, "
              f"{len(self._ova_related)} hot-derivatives filtered")

    def _filter_sequels(self, candidates: list, shown_ids: set) -> list:
        """过滤续集：如果某系列已有作品被推荐，则过滤掉该系列的其他作品"""
        # 收集已推荐作品所属的系列
        shown_series = set()
        for aid in shown_ids:
            if aid in self._id_to_series:
                shown_series.add(self._id_to_series[aid])

        # 过滤掉已推荐系列的作品
        filtered = []
        for c in candidates:
            anime_id = c["anime"]["id"]
            series = self._id_to_series.get(anime_id)
            if series and series in shown_series:
                continue
            filtered.append(c)

        return filtered

    def _sample_candidates(self, candidates: list, limit: int) -> list:
        """从候选列表中随机采样，避免总是取top N"""
        if len(candidates) <= limit:
            return candidates

        # 将候选分成高分区和普通区
        # 从高分区取70%，从普通区取30%
        top_count = min(len(candidates), limit * 3)  # 取前3倍作为候选池
        top_pool = candidates[:top_count]
        rest_pool = candidates[top_count:]

        top_sample_size = int(limit * 0.7)
        rest_sample_size = limit - top_sample_size

        # 从高分区随机采样
        top_sample = random.sample(top_pool, min(top_sample_size, len(top_pool)))

        # 从普通区随机采样（如果有的话）
        rest_sample = []
        if rest_pool and rest_sample_size > 0:
            rest_sample = random.sample(rest_pool, min(rest_sample_size, len(rest_pool)))

        result = top_sample + rest_sample
        random.shuffle(result)
        return result[:limit]

    # ============================================================
    # 1. 高质量发现
    # ============================================================
    def find_underrated(self, psych_profile: ComprehensivePsychProfile = None,
                        limit: int = 20, style: str = "standard",
                        shown_ids: set = None) -> list:
        """发现高质量佳作

        使用数学函数计算权重分布，而非硬性筛选：
        - 保守型：指数衰减，排名越靠前权重越高
        - 探索型：对数增长，偏向冷门但不过头
        - 标准型：正态分布，中间范围权重最高
        """
        if shown_ids is None:
            shown_ids = set()

        # 基础筛选条件（放宽，让算法决定权重）
        min_score = 7.0
        min_favs = 500
        max_rank = 15000  # 只排除极度冷门的作品

        # 探索型：大幅降低门槛，挖掘真正冷门的佳作
        if style == "explore":
            min_score = 5.5
            min_favs = 30
            max_rank = 50000

        candidates = []

        for anime in self._by_rating:
            anime_id = anime["id"]
            score = anime.get("mean_score") or 0
            favs = anime.get("favourites") or 0
            pop_rank = self._pop_rank.get(anime_id, 999999)

            # 基础筛选
            if score < min_score:
                continue
            if favs < min_favs:
                continue
            if pop_rank > max_rank:
                continue

            # R18过滤
            tags = set(anime.get("tags") or [])
            if tags & R18_TAGS:
                continue

            # 探索型：过滤热门番剧的OVA/Movie/SP
            if style == "explore" and anime_id in self._ova_related:
                continue

            # 已推荐过滤
            if anime_id in shown_ids:
                continue

            # 根据风格计算排名权重（核心差异）
            rank_weight = self._calc_rank_weight(pop_rank, style)

            # 计算质量指数 = 评分 × 排名权重
            quality_score = score * rank_weight

            # 探索型：给低分段番剧"发现加分"，让 6-7 分的冷门佳作也能上榜
            if style == "explore" and score < 7.5:
                # 6.0 分 → 额外 ×1.6，6.5 分 → ×1.3，7.0 分 → ×1.1
                discovery_bonus = 1.0 + max(0, (7.5 - score)) * 0.4
                quality_score *= discovery_bonus

            # 心理匹配加成
            if psych_profile:
                psych_bonus = self._calc_psych_match(anime, psych_profile)
                if style == "conservative":
                    quality_score *= (1 + psych_bonus * 0.5)
                elif style == "explore":
                    quality_score *= (1 + psych_bonus * 0.15)
                else:
                    quality_score *= (1 + psych_bonus * 0.3)

            # 随机扰动
            quality_score *= random.uniform(0.8, 1.2)

            candidates.append({
                "anime": anime,
                "underrated_score": quality_score,
                "discovery_type": "underrated",
                "reason": self._generate_underrated_reason(anime),
            })

        # 按质量指数排序
        candidates.sort(key=lambda x: -x["underrated_score"])

        # 续集过滤
        candidates = self._filter_sequels(candidates, shown_ids)

        # 随机采样
        return self._sample_candidates(candidates, limit)

    def _calc_rank_weight(self, rank: int, style: str) -> float:
        """多层次复合权重计算算法

        五层架构：
        1. 基础层：多个分布函数并行计算
        2. 调制层：用周期函数调制，产生波浪形分布
        3. 混合层：按随机比例混合多个基础函数
        4. 门槛层：sigmoid软门槛，让范围边界更自然
        5. 扰动层：多重随机扰动叠加
        """
        # ============================================
        # 第1层：基础分布函数
        # ============================================
        
        # 指数衰减（适合热门偏好）
        def exp_decay(r, rate=200):
            return math.exp(-r / rate)
        
        # 正态分布（适合中间偏好）
        def gaussian(r, mu=800, sigma=400):
            return math.exp(-((r - mu) ** 2) / (2 * sigma ** 2))
        
        # 对数增长（适合冷门偏好）
        def log_growth(r, scale=15000):
            return math.log(max(r, 1) + 1) / math.log(scale)
        
        # Sigmoid阶梯（软门槛）
        def sigmoid(r, center=1000, steepness=0.005):
            return 1 / (1 + math.exp(-steepness * (r - center)))
        
        # 反向sigmoid（软上限）
        def inv_sigmoid(r, center=5000, steepness=0.003):
            return 1 / (1 + math.exp(steepness * (r - center)))
        
        # 幂律分布（长尾分布）
        def power_law(r, alpha=0.3, scale=100):
            return (max(r, scale) / scale) ** (-alpha)
        
        # ============================================
        # 第2层：调制函数（产生周期性波动）
        # ============================================
        
        # 用正弦波调制，让权重分布有起伏
        def modulate(base, r, freq=0.002, amp=0.15):
            wave = 1 + amp * math.sin(freq * r + random.uniform(0, 2 * math.pi))
            return base * wave
        
        # ============================================
        # 第3层：根据风格混合多个函数
        # ============================================
        
        # 随机化混合参数（每次调用不同）
        jitter1 = random.uniform(0.7, 1.3)
        jitter2 = random.uniform(0.8, 1.2)
        
        if style == "conservative":
            # 保守型：指数衰减为主 + 少量正态 + 门槛调制
            w1 = exp_decay(rank, 150 * jitter1) * random.uniform(0.6, 1.0)
            w2 = gaussian(rank, 100 * jitter2, 150) * random.uniform(0.1, 0.4)
            w3 = power_law(rank, 0.5, 50) * random.uniform(0.05, 0.2)
            
            # 混合（指数衰减主导）
            mix_ratio = [random.uniform(0.5, 0.8), random.uniform(0.1, 0.3), random.uniform(0.05, 0.15)]
            total = sum(mix_ratio)
            base = (w1 * mix_ratio[0] + w2 * mix_ratio[1] + w3 * mix_ratio[2]) / total
            
            # 软门槛：排名超过500快速衰减
            gate = inv_sigmoid(rank, 500 * jitter1, 0.008)
            base *= gate
            
        elif style == "explore":
            # 探索型：强烈偏向冷门作品
            # 对数增长（scale调大，让冷门权重更高）
            w1 = log_growth(rank, 30000 * jitter1) * random.uniform(0.6, 1.0)
            # sigmoid激活中心移到800，更快激活冷门权重
            w2 = sigmoid(rank, 800 * jitter2, 0.004) * random.uniform(0.5, 1.0)
            # 长尾分布，alpha调小让尾巴更长
            w3 = power_law(rank, 0.08, 300) * random.uniform(0.3, 0.8)
            
            # 混合（sigmoid和对数主导）
            mix_ratio = [random.uniform(0.25, 0.4), random.uniform(0.35, 0.5), random.uniform(0.15, 0.3)]
            total = sum(mix_ratio)
            base = (w1 * mix_ratio[0] + w2 * mix_ratio[1] + w3 * mix_ratio[2]) / total
            
            # 软门槛：排名低于500的作品权重压低，真正偏向冷门
            gate_low = sigmoid(rank, 500 * jitter2, 0.005)
            base *= (0.05 + 0.95 * gate_low)
            
            # 额外加成：排名1000-8000的作品获得明显奖励（冷门黄金区）
            if 1000 <= rank <= 8000:
                bonus = 1.0 + 0.5 * math.sin((rank - 1000) / 7000 * math.pi)
                base *= bonus
            
        else:
            # 标准型：多峰正态 + 调制 + 平滑过渡
            # 双峰分布（一个在500，一个在1200）
            peak1 = 500 * jitter1
            peak2 = 1200 * jitter2
            w1 = gaussian(rank, peak1, 300) * random.uniform(0.4, 0.9)
            w2 = gaussian(rank, peak2, 400) * random.uniform(0.3, 0.8)
            w3 = log_growth(rank, 8000) * random.uniform(0.1, 0.4)
            
            # 混合（双峰主导）
            mix_ratio = [random.uniform(0.3, 0.5), random.uniform(0.3, 0.5), random.uniform(0.1, 0.2)]
            total = sum(mix_ratio)
            base = (w1 * mix_ratio[0] + w2 * mix_ratio[1] + w3 * mix_ratio[2]) / total
            
            # 上下软门槛
            gate_low = sigmoid(rank, 100, 0.01)
            gate_high = inv_sigmoid(rank, 2000 * jitter1, 0.003)
            base *= gate_low * gate_high
        
        # ============================================
        # 第4层：调制（加入波浪形起伏）
        # ============================================
        
        # 不同风格用不同频率的调制
        if style == "conservative":
            freq = random.uniform(0.005, 0.015)  # 高频，让热门区间有起伏
        elif style == "explore":
            freq = random.uniform(0.001, 0.005)  # 低频，让冷门区间平滑
        else:
            freq = random.uniform(0.002, 0.008)  # 中频
        
        base = modulate(base, rank, freq, random.uniform(0.1, 0.25))
        
        # ============================================
        # 第5层：多重随机扰动
        # ============================================
        
        # 扰动1：整体随机偏移（±20%）
        offset = random.uniform(0.8, 1.2)
        base *= offset
        
        # 扰动2：局部噪声（±10%）
        noise = random.uniform(0.9, 1.1)
        base *= noise
        
        # 扰动3：小概率异常值（3%概率）
        if random.random() < 0.03:
            # 完全随机的权重，模拟"意外发现"
            base = random.uniform(0.2, 0.8)
        
        # 确保权重在合理范围
        return max(0.01, min(1.5, base))

    def _generate_underrated_reason(self, anime: dict) -> str:
        """生成推荐理由"""
        score = anime.get("mean_score") or 0
        favs = anime.get("favourites") or 0
        pop_rank = self._pop_rank.get(anime["id"], 0)

        reasons = []
        if score >= 9.0:
            reasons.append(f"评分 {score:.1f}，神作级别")
        elif score >= 8.5:
            reasons.append(f"评分 {score:.1f}，极高口碑")
        elif score >= 8.0:
            reasons.append(f"评分 {score:.1f}，广受好评")
        else:
            reasons.append(f"评分 {score:.1f}，质量优秀")

        if favs >= 50000:
            reasons.append(f"{favs}人收藏的经典之作")
        elif favs >= 10000:
            reasons.append(f"{favs}人收藏，口碑保证")
        elif favs >= 5000:
            reasons.append(f"{favs}人收藏，值得关注")

        return "；".join(reasons)

    # ============================================================
    # 2. 经典老番发现
    # ============================================================
    def find_vintage(self, psych_profile: ComprehensivePsychProfile = None,
                     limit: int = 20, style: str = "standard",
                     shown_ids: set = None) -> list:
        """发现经典老番"""
        if shown_ids is None:
            shown_ids = set()

        # 根据风格设置参数（差异拉大）
        if style == "explore":
            min_score = 6.5
            min_favs = 50
            random_factor = 0.5
            psych_weight = 0.1
        elif style == "conservative":
            min_score = 8.5  # 非常高的评分要求
            min_favs = 5000
            random_factor = 0.9
            psych_weight = 0.5
        else:  # standard
            min_score = 7.5
            min_favs = 500
            random_factor = 0.7
            psych_weight = 0.2

        candidates = []

        for anime in self._by_year:
            year = anime.get("year") or anime.get("season_year")
            score = anime.get("mean_score") or 0
            favs = anime.get("favourites") or 0
            anime_id = anime["id"]

            # 基础筛选
            if not year or year > VINTAGE_YEAR_THRESHOLD:
                continue
            if score < min_score:
                continue
            if favs < min_favs:
                continue

            # R18过滤
            tags = set(anime.get("tags") or [])
            if tags & R18_TAGS:
                continue

            # 已推荐过滤
            if anime_id in shown_ids:
                continue

            # 计算经典指数
            age = 2026 - year
            vintage_score = score * (1 + age * 0.02)  # 年代越久加分越多

            # 心理匹配加成
            if psych_profile:
                psych_bonus = self._calc_psych_match(anime, psych_profile)
                vintage_score *= (1 + psych_bonus * psych_weight)

            # 随机扰动
            vintage_score *= random.uniform(random_factor, 2.0 - random_factor)

            candidates.append({
                "anime": anime,
                "vintage_score": vintage_score,
                "discovery_type": "vintage",
                "reason": self._generate_vintage_reason(anime),
            })

        # 按经典指数排序
        candidates.sort(key=lambda x: -x["vintage_score"])

        # 续集过滤
        candidates = self._filter_sequels(candidates, shown_ids)

        # 随机采样
        return self._sample_candidates(candidates, limit)

    def _generate_vintage_reason(self, anime: dict) -> str:
        """生成经典老番推荐理由"""
        score = anime.get("mean_score") or 0
        year = anime.get("year") or anime.get("season_year") or "未知"
        favs = anime.get("favourites") or 0

        reasons = []
        reasons.append(f"{year}年的经典之作，评分 {score:.1f}")
        if favs >= 10000:
            reasons.append(f"有 {favs} 人收藏，影响力经久不衰")
        elif favs >= 5000:
            reasons.append(f"有 {favs} 人收藏，质量有保证")
        reasons.append("经受住时间考验的佳作")

        return "；".join(reasons)

    # ============================================================
    # 3. 口味盲区预测
    # ============================================================
    def find_blind_spots(self, psych_profile: ComprehensivePsychProfile,
                         user_tags: set = None,
                         limit: int = 20,
                         style: str = "standard",
                         shown_ids: set = None) -> list:
        """发现口味盲区"""
        if not user_tags:
            user_tags = set()
        if shown_ids is None:
            shown_ids = set()

        # 根据风格设置参数（差异拉大）
        if style == "explore":
            min_score = 6.0  # 探索型允许更低评分
            min_favs = 50
            random_factor = 0.5
        elif style == "conservative":
            min_score = 8.0
            min_favs = 5000
            random_factor = 0.9
        else:  # standard
            min_score = 7.0
            min_favs = 1000
            random_factor = 0.7

        candidates = []

        # 找到匹配的盲区映射
        matched_blind_spots = []
        for spot_name, spot_config in TASTE_BLIND_SPOTS.items():
            source_tags = set(spot_config["source_tags"])
            if source_tags & user_tags:
                matched_blind_spots.append(spot_config)

        if not matched_blind_spots:
            if psych_profile is not None:
                matched_blind_spots = self._infer_blind_spots_from_profile(psych_profile)
            else:
                # 如果没有心理画像，使用默认的盲区推荐
                matched_blind_spots = [
                    {"target_tags": ["Action", "Adventure"], "reason": "热门动作冒险类"},
                    {"target_tags": ["Comedy", "Slice of Life"], "reason": "轻松搞笑日常类"},
                    {"target_tags": ["Drama", "Romance"], "reason": "情感剧情类"},
                ]

        # 从每个盲区中找高质量作品
        for spot in matched_blind_spots:
            target_tags = set(spot["target_tags"])
            spot_candidates = self._find_anime_by_tags(
                target_tags,
                min_rating=min_score,
                min_favs=min_favs,
                exclude_tags=user_tags,
            )

            for anime in spot_candidates:
                anime_id = anime["id"]

                # 已推荐过滤
                if anime_id in shown_ids:
                    continue

                blind_spot_score = (anime.get("mean_score") or 0) / 10.0
                blind_spot_score *= random.uniform(random_factor, 2.0 - random_factor)

                candidates.append({
                    "anime": anime,
                    "blind_spot_score": blind_spot_score,
                    "discovery_type": "blind_spot",
                    "reason": spot["reason"],
                    "target_tags": list(target_tags),
                })

        # 去重并排序
        seen_ids = set()
        unique_candidates = []
        for c in candidates:
            if c["anime"]["id"] not in seen_ids:
                seen_ids.add(c["anime"]["id"])
                unique_candidates.append(c)

        unique_candidates.sort(key=lambda x: -x["blind_spot_score"])

        # 续集过滤
        unique_candidates = self._filter_sequels(unique_candidates, shown_ids)

        # 随机采样
        return self._sample_candidates(unique_candidates, limit)

    def _infer_blind_spots_from_profile(self, profile: ComprehensivePsychProfile) -> list:
        """基于心理画像推断可能的口味盲区"""
        blind_spots = []

        archetype_mapping = {
            "hero": ["Sports", "Competition"],
            "explorer": ["Fantasy", "Adventure"],
            "sage": ["Sci-Fi", "Philosophical"],
            "caregiver": ["Healing", "Family"],
            "lover": ["Romance", "Music"],
            "jester": ["Comedy", "Slice of Life"],
        }

        if profile.archetype in archetype_mapping:
            blind_spots.append({
                "target_tags": archetype_mapping[profile.archetype],
                "reason": f"基于你的{profile.archetype}原型，你可能会喜欢这些类型",
            })

        defense_mapping = {
            "sublimation": ["Sports", "Action"],
            "dissociation": ["Isekai", "Fantasy"],
            "intellectualization": ["Mystery", "Sci-Fi"],
            "fantasy": ["Magic", "Supernatural"],
        }

        if profile.defense_mechanisms:
            primary_defense = profile.defense_mechanisms[0]
            if primary_defense in defense_mapping:
                blind_spots.append({
                    "target_tags": defense_mapping[primary_defense],
                    "reason": f"基于你的应对方式，这些类型可能会给你带来新的体验",
                })

        return blind_spots

    def _find_anime_by_tags(self, target_tags: set,
                            min_rating: float = 7.0,
                            min_favs: int = 100,
                            exclude_tags: set = None) -> list:
        """按标签找高质量番剧"""
        if exclude_tags is None:
            exclude_tags = set()

        candidates = []
        for anime in self.anime_list:
            anime_tags = set(anime.get("tags") or [])

            # R18过滤
            if anime_tags & R18_TAGS:
                continue

            # 必须包含至少一个目标标签
            if not (anime_tags & target_tags):
                continue

            # 质量筛选
            score = anime.get("mean_score") or 0
            favs = anime.get("favourites") or 0
            if score < min_rating or favs < min_favs:
                continue

            # 排除用户已经看过的标签（如果指定）
            if exclude_tags and (anime_tags & exclude_tags):
                new_tags = anime_tags - exclude_tags
                if not (new_tags & target_tags):
                    continue

            candidates.append(anime)

        return candidates

    def _calc_blind_spot_score(self, anime: dict,
                               profile: ComprehensivePsychProfile) -> float:
        """计算盲区发现指数"""
        score = anime.get("mean_score") or 0
        rating_norm = max(0, min(1, (score - 7) / 3))
        psych_match = self._calc_psych_match(anime, profile)
        novelty = 0.5
        return rating_norm * (1 + psych_match * 0.5) * (1 + novelty)

    # ============================================================
    # 4. 综合发现推荐
    # ============================================================
    def discover(self, psych_profile: ComprehensivePsychProfile,
                 user_tags: set = None,
                 total_limit: int = 50,
                 exclude_ids: set = None,
                 style: str = "standard") -> dict:
        """综合发现推荐"""
        if exclude_ids is None:
            exclude_ids = set()

        # 根据风格调整推荐比例（老番比例进一步减少）
        if style == "explore":
            # 探索型：大量小众佳作和口味盲区，极少老番
            underrated_limit = int(total_limit * 0.45)
            vintage_limit = int(total_limit * 0.05)  # 老番仅5%
            blind_spot_limit = int(total_limit * 0.50)
        elif style == "conservative":
            # 保守型：大量热门经典，少量老番
            underrated_limit = int(total_limit * 0.65)
            vintage_limit = int(total_limit * 0.10)  # 老番仅10%
            blind_spot_limit = int(total_limit * 0.25)
        else:
            # 标准型：均衡
            underrated_limit = int(total_limit * 0.55)
            vintage_limit = int(total_limit * 0.08)  # 老番仅8%
            blind_spot_limit = int(total_limit * 0.37)

        # 获取各类推荐（多取一些用于去重和续集过滤）
        extra = len(exclude_ids) + 50  # 额外多取一些用于续集过滤
        underrated = self.find_underrated(psych_profile, underrated_limit + extra, style=style, shown_ids=exclude_ids)
        vintage = self.find_vintage(psych_profile, vintage_limit + extra, style=style, shown_ids=exclude_ids)
        blind_spot = self.find_blind_spots(psych_profile, user_tags, blind_spot_limit + extra, style=style, shown_ids=exclude_ids)

        # 去除已推荐过的番剧
        underrated = [r for r in underrated if r["anime"]["id"] not in exclude_ids][:underrated_limit]
        vintage = [r for r in vintage if r["anime"]["id"] not in exclude_ids][:vintage_limit]
        blind_spot = [r for r in blind_spot if r["anime"]["id"] not in exclude_ids][:blind_spot_limit]

        # 生成推荐总结
        summary = self._generate_discovery_summary(underrated, vintage, blind_spot)

        return {
            "underrated": underrated,
            "vintage": vintage,
            "blind_spot": blind_spot,
            "summary": summary,
        }

    def _generate_discovery_summary(self, underrated: list, vintage: list,
                                     blind_spot: list) -> str:
        """生成发现型推荐的总结"""
        parts = []
        parts.append("=== 发现型推荐 ===")
        parts.append("")

        if underrated:
            parts.append("【高质量佳作】")
            parts.append(f"为你找到 {len(underrated)} 部高质量作品。")
            parts.append("")

        if vintage:
            parts.append("【经典老番】")
            parts.append(f"为你找到 {len(vintage)} 部经典作品。")
            parts.append("")

        if blind_spot:
            parts.append("【口味盲区】")
            parts.append(f"为你找到 {len(blind_spot)} 部可能喜欢的新类型作品。")

        return "\n".join(parts)

    # ============================================================
    # 辅助方法
    # ============================================================
    def _calc_psych_match(self, anime: dict,
                          profile: ComprehensivePsychProfile) -> float:
        """计算番剧与心理画像的匹配度"""
        tags = set(anime.get("tags") or [])
        score = 0.0
        max_score = 0.0

        # 原型匹配
        max_score += 1.0
        for tag in tags:
            if tag in TAG_TO_PSYCH and "archetype" in TAG_TO_PSYCH[tag]:
                arch = TAG_TO_PSYCH[tag]["archetype"]
                if isinstance(arch, list):
                    arch = arch[0] if arch else ""
                if arch == profile.archetype:
                    score += 1.0
                    break

        # 防御机制匹配
        max_score += 1.0
        if profile.defense_mechanisms:
            primary_defense = profile.defense_mechanisms[0]
            for tag in tags:
                if tag in TAG_TO_PSYCH and "defense" in TAG_TO_PSYCH[tag]:
                    if primary_defense in TAG_TO_PSYCH[tag]["defense"]:
                        score += 1.0
                        break

        # 需求匹配
        max_score += 1.0
        if profile.sdt_needs:
            primary_need = max(profile.sdt_needs, key=profile.sdt_needs.get)
            for tag in tags:
                if tag in TAG_TO_PSYCH and "sdt" in TAG_TO_PSYCH[tag]:
                    if primary_need in TAG_TO_PSYCH[tag]["sdt"]:
                        score += 1.0
                        break

        return score / max_score if max_score > 0 else 0.0
