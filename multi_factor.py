"""
multi_factor.py
=================
多因子番剧推荐打分模块（v3.0 重构）

历史：v2.1 = 15 因子（14 基础 + 心理 41%）
      v3.0 = 14 因子（13 基础 + 历史 40%）+ 心理模型独立作为乘性加成
             + 调参作为后处理乘数

为什么需要这么多因子？
    单靠"标签相似度"会推出一堆冷门 / 低分 / 老番。
    用户实际选片时是综合判断：内容像不像 + 质量高不高 + 时代对不对 +
    制作熟不熟 + 声优喜不喜欢 + 集数能不能消化。
    每个因子都贡献一点，叠加起来才像人挑片。

v3.0 心理画像角色：
    心理模型不再参与 14 因子几何平均，而是在 re_rank 之后作为乘性加成
    （带 ±5% 浮动）。调参作为最后的后处理乘数。

设计：
    每个 factor(anime, query) -> (score 0~1, reason_str|None)
    re_rank() 负责把 14 个因子按权重几何平均，再乘以心理和调参。
    调整 WEIGHTS 就能调整个性。
"""
import math
from collections import Counter
from psych_profile import ComprehensivePsychProfile, R18_TAGS


# ============================================================
# 权重配置（v3.0 重构：心理独立 + 历史 40%）
# ============================================================
# 15 因子（14 基础 + 1 历史）参与几何平均
# 心理模型独立作为乘性加成（在 re_rank 之后）
# 调参作为最后的后处理（在调参 tab 调整过时才生效）
WEIGHTS = {
    "tag":            0.10,  # 标签相似度
    "rating":         0.08,  # 质量：均分
    "popularity":     0.04,  # 热度：人气排名
    "favourites":     0.04,  # 质量：收藏数
    "era":            0.03,  # 偏好：年代匹配
    "format":         0.03,  # 偏好：格式
    "studio":         0.03,  # 偏好：制作公司
    "va":             0.03,  # 偏好：声优
    "staff":          0.02,  # 细节：监督/编剧重叠
    "eps":            0.02,  # 细节：集数分级
    "duration":       0.01,  # 细节：单集时长分级
    "recency":        0.03,  # 先验：新番优先
    "quality_signal": 0.02,  # 先验：标签数量
    "consensus":      0.12,  # 综合质量：评分 × 收藏 × 人气
    "history":        0.40,  # 历史因素（核心因子，40% 权重）
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, f"权重和 != 1.0 ({sum(WEIGHTS.values())})"

# 标签搜索专用权重（无历史、无心理）
TAG_SEARCH_WEIGHTS = {
    "tag":            0.20,
    "rating":         0.15,
    "popularity":     0.10,
    "favourites":     0.08,
    "era":            0.05,
    "format":         0.05,
    "studio":         0.04,
    "va":             0.04,
    "staff":          0.03,
    "eps":            0.04,
    "duration":       0.02,
    "recency":        0.06,
    "quality_signal": 0.08,
    "consensus":      0.06,
    "history":        0.00,  # 标签模式无历史
}
assert abs(sum(TAG_SEARCH_WEIGHTS.values()) - 1.0) < 1e-9, f"TAG_SEARCH_WEIGHTS != 1.0"


# ============================================================
# 常量配置
# ============================================================
CURRENT_YEAR = 2026  # recency 因子用，距今几年

# 格式兼容表（用户切换 TV↔TV_SHORT、MOVIE↔SPECIAL 时给个半分）
COMPATIBLE_FORMATS = {
    "TV":       {"TV", "TV_SHORT"},
    "TV_SHORT": {"TV", "TV_SHORT"},
    "MOVIE":    {"MOVIE", "SPECIAL"},
    "SPECIAL":  {"MOVIE", "SPECIAL"},
}

# 集数分级（短篇 / 标准 / 长篇）
EPS_BUCKETS = [(0, 12), (13, 26), (27, float("inf"))]
EPS_BUCKET_LABELS = ["短篇(<=12)", "标准(13-26)", "长篇(>26)"]

# 时长分级（泡面 / 标准番 / 长篇每集）
DURATION_BUCKETS = [(0, 10), (11, 40), (41, float("inf"))]
DURATION_BUCKET_LABELS = ["短泡面(<10min)", "标准(11-40min)", "长篇每集(>40min)"]


# ============================================================
# 工具函数
# ============================================================
def _bucket_of(value, buckets):
    """value 落在 buckets 哪个桶（返回 index）；落不到返回 None。"""
    for i, (lo, hi) in enumerate(buckets):
        if lo <= value <= hi:
            return i
    return None


def _share(a, b):
    """两个可迭代对象是否有交集。空集合返回 False。"""
    if not a or not b:
        return False
    return bool(set(a) & set(b))


def _extract_vas(anime):
    """从 anime.characters 里抽所有声优名字。"""
    vas = set()
    for ch in anime.get("characters") or []:
        for va in ch.get("va") or []:
            if isinstance(va, dict):
                name = va.get("name")
            else:
                name = va
            if name:
                vas.add(name)
    return vas


def _extract_staff(anime):
    """从 anime.staff 里抽所有工作人员名字。"""
    staff = set()
    for s in anime.get("staff") or []:
        if isinstance(s, dict):
            name = s.get("name")
        else:
            name = s
        if name:
            staff.add(name)
    return staff


def _eps_bucket(eps):
    if not eps or eps <= 0:
        return None
    return _bucket_of(eps, EPS_BUCKETS)


def _duration_bucket(dur):
    if not dur or dur <= 0:
        return None
    return _bucket_of(dur, DURATION_BUCKETS)


# ============================================================
# 14 个因子函数（含 history）
# 每个都返回 (score 0~1, reason_str 或 None)
# ============================================================

def rating_factor(anime):
    """(15%) 均分因子：4 分以下不推，8+ 满分。

    公式：clamp((score - 4) / 4, 0, 1)
    为什么这么映射？
        13k 数据 mean_score 中位 6.5、平均 6.3，分布集中在 5~8。
        减去 4 让 5 分对应 0.25（弱推荐），8 分对应 1.0（强推）。
    """
    score = anime.get("mean_score") or 0
    if score <= 0:
        return 0.0, None
    val = max(0.0, min(1.0, (score - 4) / 4))
    reason = f"均分 {score:.1f}/10" if val >= 0.5 else None
    return val, reason


def popularity_factor(anime):
    """(8%) 人气因子：排名越靠前分越高。

    公式：clamp(1 - log10(popularity) / 6, 0, 1)
    popularity 越小越热门。pop=10 -> 0.83, pop=1000 -> 0.5, pop=1M -> ~0。
    为什么用 log10？
        数据 P50=2562, P90=55k，跨度太大，线性压不住，必须用 log。
    """
    pop = anime.get("popularity") or 0
    if pop <= 0:
        return 0.0, None
    val = max(0.0, min(1.0, 1 - math.log10(pop) / 6))
    return val, None  # 人气不写理由（太啰嗦）


def favourites_factor(anime):
    """(5%) 收藏因子：真爱粉越多分越高。

    公式：clamp(log10(favourites) / 5, 0, 1)
    favourites 跟 popularity 的区别：
        popularity 是排名（越小越热门），而 favourites 是计数（越多越好！）。
        之前的公式 1-log10(favs)/5 反了——favs=1 得 1.0, favs=100k 得 0.0。
    修正后：favs=100 → 0.40, favs=1000 → 0.60, favs=10000 → 0.80
    """
    favs = anime.get("favourites") or 0
    if favs <= 0:
        return 0.0, None
    val = max(0.0, min(1.0, math.log10(favs) / 5))
    reason = f"{favs} 人收藏" if val >= 0.5 else None
    return val, reason


def era_factor(anime, query_year=None):
    """(8%) 年代因子：与查询年份差越小分越高。

    公式：exp(-(Δyear/σ)^2)，σ=8
    例子：query=2010，cand=2010 -> 1.0；cand=2018 -> 0.88；cand=1990 -> 0.06
    为什么高斯？
        用户对"前后 3~5 年"是宽容的，对"差 20 年"是坚决的——指数衰减正合适。
    """
    if query_year is None:
        return 0.5, None  # 没指定就中性
    yr = anime.get("year") or anime.get("season_year")
    if not yr:
        return 0.5, None
    delta = abs(yr - query_year)
    sigma = 8
    val = math.exp(-((delta / sigma) ** 2))
    reason = f"同年代 ({yr})" if delta <= 3 else None
    return val, reason


def format_factor(anime, query_format=None):
    """(7%) 格式因子：TV/MOVIE/OVA 三大类匹配度。

    同=1.0，兼容=0.5（TV<->TV_SHORT、MOVIE<->SPECIAL），不同=0.0
    为什么要兼容表？
        用户嘴上说"只看 TV"，但 TV_SHORT（泡面短番）也能接受。
        直接判 0 太严。
    """
    if query_format is None:
        return 0.5, None
    fmt = anime.get("format")
    if not fmt:
        return 0.5, None
    if fmt == query_format:
        return 1.0, f"同格式 {fmt}"
    if fmt in COMPATIBLE_FORMATS.get(query_format, set()):
        return 0.5, f"兼容格式 {fmt}"
    return 0.0, None


def studio_factor(anime, query_studios=None):
    """(5%) 制作公司因子：命中任一即 1.0。

    为什么是命中而非比例？
        用户对"京阿尼"是认厂牌的，不是看"30% 京阿尼"。
    """
    if not query_studios:
        return 0.0, None
    cand = set(anime.get("studios") or [])
    hit = cand & set(query_studios)
    if hit:
        return 1.0, f"同制作公司: {next(iter(hit))}"
    return 0.0, None


def va_factor(anime, query_vas=None):
    """(5%) 声优因子：声优重叠即 1.0。

    数据：characters[].va 是个数组，每项是 {name, ...}。
    """
    if not query_vas:
        return 0.0, None
    cand = _extract_vas(anime)
    hit = cand & query_vas
    if hit:
        return 1.0, f"同声优: {next(iter(hit))}"
    return 0.0, None


def staff_factor(anime, query_staff=None):
    """(3%) Staff 因子：监督/编剧等重叠即 1.0。

    权重低的原因：staff 列表太长（93% 有），命中概率高，给低了就乱推。
    """
    if not query_staff:
        return 0.0, None
    cand = _extract_staff(anime)
    hit = cand & query_staff
    if hit:
        return 1.0, f"同 Staff: {next(iter(hit))}"
    return 0.0, None


def eps_factor(anime, query_eps_bucket=None):
    """(4%) 集数因子：同量级 1.0，相邻 0.5，跨档 0.0。

    三档：<=12（季番）、13-26（半年番）、>26（年番/长篇）。
    为什么用桶而非精确匹配？
        12 和 13 没本质区别，但 12 和 50 完全是两种东西。
    """
    if query_eps_bucket is None:
        return 0.5, None
    eps = anime.get("eps") or 0
    if eps <= 0:
        return 0.5, None
    bucket = _eps_bucket(eps)
    if bucket is None:
        return 0.5, None
    if bucket == query_eps_bucket:
        return 1.0, f"同集数档 {EPS_BUCKET_LABELS[bucket]}"
    if abs(bucket - query_eps_bucket) == 1:
        return 0.5, None
    return 0.0, None


def duration_factor(anime, query_duration_bucket=None):
    """(2%) 时长因子：同量级 1.0，相邻 0.5，跨档 0.0。

    三档：<10min（泡面）、11-40min（标准番）、>40min（特别篇/长篇）。
    权重低：用户对时长敏感度低。
    """
    if query_duration_bucket is None:
        return 0.5, None
    dur = anime.get("duration") or 0
    if dur <= 0:
        return 0.5, None
    bucket = _duration_bucket(dur)
    if bucket is None:
        return 0.5, None
    if bucket == query_duration_bucket:
        return 1.0, f"同时长档 {DURATION_BUCKET_LABELS[bucket]}"
    if abs(bucket - query_duration_bucket) == 1:
        return 0.5, None
    return 0.0, None


def recency_factor(anime):
    """(5%) 新番优先因子：越新分越高（线性衰减）。

    公式：距今 <=2 年 -> 1.0；5 年 -> 0.5；>=10 年 -> 0.0。
    为什么不是纯按 year？
        用户有时就想看老番，recency 是"先验"不是"硬过滤"。
    """
    yr = anime.get("season_year") or anime.get("year")
    if not yr:
        return 0.5, None
    delta = CURRENT_YEAR - yr
    if delta <= 2:
        return 1.0, "新番"
    if delta >= 10:
        return 0.0, None
    val = 1.0 - (delta - 2) / 8
    return val, None


def quality_signal_factor(anime):
    """(5%) 质量信号因子：标签数量越多分越高。

    公式：min(len(tags) / 15, 1.0)
    为什么标签多 = 质量高？
        AniList 上标签由社区贡献，标签多说明被研究得多，
        通常意味着热度/口碑都不差。这是统计学先验。
    """
    n = len(anime.get("tags") or [])
    if n == 0:
        return 0.0, None
    val = min(n / 15, 1.0)
    return val, None


def consensus_factor(anime):
    """(5%) 综合质量因子 v1.1：评分 × 收藏 × 人气 三者协同。

    公式：rating × log10(favourites+1)/log10(10000) × popularity_tier
    为什么用乘性？
        单一指标会被刷分（比如高 rating 但冷门 = 偏科），
        三个维度的乘积能识别"公认的好番"。
    阈值：
        - 均分 >= 7 才返回正值（太低根本不算共识好番）
        - 收藏 < 10 视为 0（数据不足）
    """
    score = anime.get("mean_score") or 0
    favs = anime.get("favourites") or 0
    pop = anime.get("popularity") or 0

    if score < 7 or favs < 10:
        return 0.0, None

    # 收藏对数归一：以 10000 为满分
    fav_norm = min(math.log10(favs + 1) / math.log10(10001), 1.0)
    # 人气 tier：top 1000=1, top 10000=0.5, 其余=0.25
    if pop <= 0:
        pop_norm = 0.0
    elif pop <= 1000:
        pop_norm = 1.0
    elif pop <= 10000:
        pop_norm = 0.5
    else:
        pop_norm = 0.25

    # 评分归一到 0~1（7~10 分映射）
    score_norm = (score - 7) / 3

    val = score_norm * fav_norm * pop_norm
    val = max(0.0, min(1.0, val))
    reason = f"公认好番（{score:.1f}分/{favs}收藏）" if val >= 0.5 else None
    return val, reason


def history_factor(candidate, history_top_anime, history_avg_rating):
    """(40%) 历史因素因子 v3.1：复合多信号历史匹配。

    复合运算策略：
      信号 1: 标签偏好匹配（从全部历史构建加权 tag 分布）
      信号 2: 制作公司 / 声优偏好匹配
      信号 3: 评分风格匹配（用户偏好高分还是小众）
      信号 4: 格式/年代偏好匹配

    最终 = sigmoid(加权和) 映射到 0.1~1.0
    """
    if not history_top_anime or history_avg_rating is None:
        return 0.5, None

    # === 信号 1: 标签偏好匹配 ===
    # 从全部历史构建加权 tag 频率表
    tag_weights = {}  # tag -> cumulative weight
    total_weight = 0.0
    for hist_anime, hist_rating in history_top_anime:
        w = max(0.1, (hist_rating / 10.0) ** 1.5)  # 非线性权重：高评分指数级更重要
        for tag in (hist_anime.get("tags") or []):
            tag_weights[tag] = tag_weights.get(tag, 0) + w
            total_weight += w

    cand_tags = set(candidate.get("tags") or [])
    if not cand_tags or total_weight == 0:
        tag_signal = 0.5
    else:
        # 加权命中率：候选的每个 tag 在历史偏好中的权重
        hit_weight = sum(tag_weights.get(t, 0) for t in cand_tags)
        # 归一化：用候选 tag 数和历史总权重做双侧归一化
        tag_signal = min(1.0, hit_weight / (total_weight * 0.3 + 1e-6))
        # 非线性压缩：避免 tag 多的番剧过度占优
        tag_signal = tag_signal ** 0.7

    # === 信号 2: 制作公司 / 声优偏好匹配 ===
    hist_studios = set()
    hist_vas = set()
    for hist_anime, _ in history_top_anime:
        for s in (hist_anime.get("studios") or []):
            hist_studios.add(s)
        for v in _extract_vas(hist_anime):
            hist_vas.add(v)

    cand_studios = set(candidate.get("studios") or [])
    cand_vas = _extract_vas(candidate)

    studio_overlap = len(hist_studios & cand_studios) > 0 if hist_studios else False
    va_overlap = len(hist_vas & cand_vas) > 0 if hist_vas else False

    # 厂牌信号：有重叠时给强加分
    brand_signal = 0.0
    if studio_overlap:
        brand_signal += 0.4
    if va_overlap:
        brand_signal += 0.3
    brand_signal = min(1.0, brand_signal)

    # === 信号 3: 评分风格匹配 ===
    # 用户历史平均分 vs 候选番剧评分的差距
    cand_score = candidate.get("mean_score") or 0
    if cand_score > 0 and history_avg_rating > 0:
        # 差距越小越好，用高斯函数
        score_diff = abs(cand_score - history_avg_rating)
        score_signal = math.exp(-(score_diff ** 2) / 8.0)  # sigma=2
    else:
        score_signal = 0.5

    # === 信号 4: 格式/年代偏好 ===
    hist_formats = [a.get("format") for a, _ in history_top_anime if a.get("format")]
    hist_years = [a.get("year") or a.get("season_year") for a, _ in history_top_anime
                  if a.get("year") or a.get("season_year")]

    cand_fmt = candidate.get("format")
    cand_year = candidate.get("year") or candidate.get("season_year")

    fmt_signal = 0.5
    if hist_formats and cand_fmt:
        fmt_count = sum(1 for f in hist_formats if f == cand_fmt)
        fmt_signal = 0.3 + 0.7 * (fmt_count / len(hist_formats))

    year_signal = 0.5
    if hist_years and cand_year:
        avg_year = sum(hist_years) / len(hist_years)
        year_diff = abs(cand_year - avg_year)
        year_signal = max(0.2, math.exp(-(year_diff ** 2) / 50.0))  # sigma≈7年

    # === 复合运算：加权和 + sigmoid 压缩 ===
    # 各信号权重
    raw = (tag_signal * 0.45 +
           brand_signal * 0.20 +
           score_signal * 0.15 +
           fmt_signal * 0.10 +
           year_signal * 0.10)

    # sigmoid 压缩到 (0, 1)，中心在 0.35
    val = 1.0 / (1.0 + math.exp(-6.0 * (raw - 0.35)))
    val = max(0.1, min(1.0, val))

    # 生成推荐理由
    reason = None
    best_match = None
    best_sim = 0.0
    for hist_anime, _ in history_top_anime:
        hist_tags = set(hist_anime.get("tags") or [])
        if not hist_tags:
            continue
        sim = len(hist_tags & cand_tags) / max(1, len(hist_tags | cand_tags))
        if sim > best_sim:
            best_sim = sim
            best_match = hist_anime

    if best_match and best_sim > 0.15:
        bm_name = best_match.get("name_cn") or best_match.get("name") or ""
        if bm_name:
            reason = f"类似你喜欢的《{bm_name}》"
    if not reason and studio_overlap:
        reason = "你看过该公司其他作品"
    if not reason and va_overlap:
        reason = "你听过该声优其他作品"

    return val, reason


# ============================================================
# 心理模型：psych_match_factor（v3.0 作为独立乘性加成，不进几何平均）
# ============================================================
def psych_match_factor(candidate, psych_profile):
    """心理画像匹配度（v3.0 独立乘性加成）

    基于用户心理画像计算候选番剧的匹配度。
    匹配逻辑：
      1. 原型匹配：用户偏好原型 vs 候选番剧的原型
      2. 防御机制匹配：用户使用防御机制 vs 候选番剧能提供的防御
      3. 需求匹配：用户核心需求 vs 候选番剧能满足的需求
      4. 叙事匹配：用户偏好叙事 vs 候选番剧的叙事类型
      5. 世界观匹配：用户世界观认同 vs 候选番剧的世界观

    这是一个隐性因子，不直接显示给用户。
    """
    if not psych_profile:
        return 0.0, None

    score = 0.0
    max_score = 0.0

    # 1. 原型匹配（权重 0.25）
    max_score += 0.25
    candidate_archetype = _get_candidate_archetype(candidate)
    if candidate_archetype == psych_profile.archetype:
        score += 0.25
    elif _is_compatible_archetype(candidate_archetype, psych_profile.archetype):
        score += 0.12

    # 2. 防御机制匹配（权重 0.20）
    max_score += 0.20
    candidate_defense = _get_candidate_defense(candidate)
    if psych_profile.defense_mechanisms:
        primary_defense = psych_profile.defense_mechanisms[0]
        if primary_defense in candidate_defense:
            score += 0.20
        elif any(d in candidate_defense for d in psych_profile.defense_mechanisms[:2]):
            score += 0.10

    # 3. 需求匹配（权重 0.25）
    max_score += 0.25
    if psych_profile.sdt_needs:
        primary_need = max(psych_profile.sdt_needs, key=psych_profile.sdt_needs.get)
        candidate_needs = _get_candidate_needs(candidate)
        if primary_need in candidate_needs:
            score += 0.25
        elif any(n in candidate_needs for n in psych_profile.sdt_needs.keys()):
            score += 0.12

    # 4. 叙事匹配（权重 0.15）
    max_score += 0.15
    candidate_narrative = _get_candidate_narrative(candidate)
    if candidate_narrative == psych_profile.narrative_type:
        score += 0.15
    elif _is_compatible_narrative(candidate_narrative, psych_profile.narrative_type):
        score += 0.07

    # 5. 世界观匹配（权重 0.15）
    max_score += 0.15
    candidate_worldview = _get_candidate_worldview(candidate)
    if candidate_worldview == psych_profile.worldview:
        score += 0.15
    elif _is_compatible_worldview(candidate_worldview, psych_profile.worldview):
        score += 0.07

    # 归一化到 0~1
    val = score / max_score if max_score > 0 else 0.0
    val = max(0.0, min(1.0, val))

    # 不显示理由（隐性因子）
    return val, None


def _get_candidate_archetype(anime):
    """从番剧标签推断原型"""
    tags = set(anime.get("tags") or []) - R18_TAGS  # 过滤R18标签
    from psych_profile import TAG_TO_PSYCH
    for tag in tags:
        if tag in TAG_TO_PSYCH and "archetype" in TAG_TO_PSYCH[tag]:
            arch = TAG_TO_PSYCH[tag]["archetype"]
            if isinstance(arch, list):
                return arch[0] if arch else ""
            return arch
    return ""


def _get_candidate_defense(anime):
    """从番剧标签推断防御机制"""
    tags = set(anime.get("tags") or []) - R18_TAGS  # 过滤R18标签
    defense = []
    from psych_profile import TAG_TO_PSYCH
    for tag in tags:
        if tag in TAG_TO_PSYCH and "defense" in TAG_TO_PSYCH[tag]:
            defense.extend(TAG_TO_PSYCH[tag]["defense"])
    return list(set(defense))


def _get_candidate_needs(anime):
    """从番剧标签推断满足的需求"""
    tags = set(anime.get("tags") or []) - R18_TAGS  # 过滤R18标签
    needs = []
    from psych_profile import TAG_TO_PSYCH
    for tag in tags:
        if tag in TAG_TO_PSYCH and "needs" in TAG_TO_PSYCH[tag]:
            needs.extend(TAG_TO_PSYCH[tag]["needs"])
    return list(set(needs))


def _get_candidate_narrative(anime):
    """从番剧标签推断叙事类型"""
    tags = set(anime.get("tags") or []) - R18_TAGS  # 过滤R18标签
    from psych_profile import TAG_TO_PSYCH
    for tag in tags:
        if tag in TAG_TO_PSYCH and "narrative" in TAG_TO_PSYCH[tag]:
            nar = TAG_TO_PSYCH[tag]["narrative"]
            if isinstance(nar, list):
                return nar[0] if nar else ""
            return nar
    return ""


def _get_candidate_worldview(anime):
    """从番剧标签推断世界观"""
    tags = set(anime.get("tags") or []) - R18_TAGS  # 过滤R18标签
    from psych_profile import TAG_TO_PSYCH
    for tag in tags:
        if tag in TAG_TO_PSYCH and "worldview" in TAG_TO_PSYCH[tag]:
            wv = TAG_TO_PSYCH[tag]["worldview"]
            if isinstance(wv, list):
                return wv[0] if wv else ""
            return wv
    return ""


def _is_compatible_archetype(arch1, arch2):
    """判断两种原型是否兼容"""
    compatible_pairs = [
        ("hero", "rebel"),
        ("hero", "explorer"),
        ("sage", "magician"),
        ("rebel", "hero"),
        ("explorer", "hero"),
    ]
    return (arch1, arch2) in compatible_pairs or (arch2, arch1) in compatible_pairs


def _is_compatible_narrative(nar1, nar2):
    """判断两种叙事是否兼容"""
    compatible_pairs = [
        ("progressive", "redemption"),
        ("exploration", "progressive"),
        ("stability", "regressive"),
        ("contamination", "redemption"),
    ]
    return (nar1, nar2) in compatible_pairs or (nar2, nar1) in compatible_pairs


def _is_compatible_worldview(wv1, wv2):
    """判断两种世界观是否兼容"""
    compatible_pairs = [
        ("just_world", "magical_world"),
        ("unjust_world", "dystopian"),
        ("magical_world", "just_world"),
    ]
    return (wv1, wv2) in compatible_pairs or (wv2, wv1) in compatible_pairs


# ============================================================
# 上下文构建（不同模式 -> 不同的 query dict）
# ============================================================
def build_query_from_anime(seed):
    """模式 1: 从一颗种子番剧构建上下文（不构建心理画像）。

    单部番剧推荐时，直接用番剧本身的特征，无需心理画像。
    """
    return {
        "year":           seed.get("year") or seed.get("season_year"),
        "format":         seed.get("format"),
        "studios":        seed.get("studios") or [],
        "vas":            _extract_vas(seed),
        "staff":          _extract_staff(seed),
        "eps_bucket":     _eps_bucket(seed.get("eps") or 0),
        "duration_bucket": _duration_bucket(seed.get("duration") or 0),
        "watched_ids":    {seed["id"]},
        "psych_profile":  None,  # 单部番剧推荐不使用心理画像
        "history_top":    None,  # 无历史
    }


def build_query_from_history(history, anime_list):
    """模式 2: 从用户历史构建上下文（使用全部历史，低评分有权重惩罚）。

    history: [{"id": int, "rating": int(1-10), ...}, ...]
    返回 None 表示历史为空。
    """
    id_to_anime = {a["id"]: a for a in anime_list}
    watched = []
    for h in history:
        a = id_to_anime.get(h.get("id"))
        if a:
            rating = h.get("rating") or 0
            # 如果用户没有打分，使用番剧本身的bangumi评分
            if rating == 0:
                rating = a.get("mean_score") or 5
            watched.append((a, rating))
    if not watched:
        return None

    # 年份：取中位
    years = sorted([a.get("year") or a.get("season_year")
                    for a, _ in watched if a.get("year") or a.get("season_year")])
    year = years[len(years) // 2] if years else None

    # 格式：取众数
    fmts = [a.get("format") for a, _ in watched if a.get("format")]
    fmt = Counter(fmts).most_common(1)[0][0] if fmts else None

    # studios / va / staff：取并集
    studios = set()
    vas = set()
    staff = set()
    for a, _ in watched:
        for s in a.get("studios") or []:
            studios.add(s)
        vas |= _extract_vas(a)
        staff |= _extract_staff(a)

    # eps / duration：取众数对应的桶
    eps_list = [a.get("eps") for a, _ in watched if a.get("eps")]
    if eps_list:
        common_eps = Counter(eps_list).most_common(1)[0][0]
        eps_b = _eps_bucket(common_eps)
    else:
        eps_b = None
    dur_list = [a.get("duration") for a, _ in watched if a.get("duration")]
    if dur_list:
        common_dur = Counter(dur_list).most_common(1)[0][0]
        dur_b = _duration_bucket(common_dur)
    else:
        dur_b = None

    # 心理画像：使用全部历史构建，低评分番剧有权重惩罚
    # 权重计算：评分越高权重越高，但低评分也有正面影响
    psych_profile = ComprehensivePsychProfile()

    # 按评分加权构建心理画像
    # 评分高的番剧权重高，评分低的番剧权重低但不为0
    weighted_anime_list = []
    for a, rating in watched:
        # 权重公式：(rating / 10) ^ 2，最低0.1
        weight = max(0.1, (rating / 10) ** 2)
        weighted_anime_list.append((a, weight))

    # 使用加权方式构建心理画像
    psych_profile.build_from_anime_weighted(weighted_anime_list)

    # 历史 top 3（按评分降序）
    history_sorted = sorted(watched, key=lambda x: -x[1])
    history_top = [(a, r) for a, r in history_sorted if r >= 7][:5]  # 取 ≥7 分的
    if not history_top:
        history_top = [(a, r) for a, r in history_sorted[:3]]
    history_avg = sum(r for _, r in watched) / len(watched) if watched else None

    return {
        "year":           year,
        "format":         fmt,
        "studios":        list(studios),
        "vas":            vas,
        "staff":          staff,
        "eps_bucket":     eps_b,
        "duration_bucket": dur_b,
        "watched_ids":    {a["id"] for a, _ in watched},
        "psych_profile":  psych_profile,
        "history_top":    history_top,
        "history_avg":    history_avg,
    }


def build_query_from_tags():
    """模式 3: 标签模式不指定偏好，全部中性。"""
    return {
        "year":           None,
        "format":         None,
        "studios":        [],
        "vas":            set(),
        "staff":          set(),
        "eps_bucket":     None,
        "duration_bucket": None,
        "watched_ids":    set(),
        "psych_profile":  None,
        "history_top":    None,
    }


# ============================================================
# 主函数：精排
# ============================================================
def re_rank(candidates, query, tag_sims, weights=None, top_k=10, mode="similar",
            style="standard", user_tuning=None):
    """
    对粗排候选做多因子精排（v3.0 4 级流水线）。

    参数：
        candidates: list[dict] - 粗排返回的候选番剧字典列表
        query: dict - 用 build_query_* 构建的上下文
        tag_sims: dict[int, float] - 每个候选 id -> tag 相似度 0~1
        weights: dict - 可选自定义权重（默认 WEIGHTS）
        top_k: int - 返回前 K 条
        mode: str - "similar"(种子推荐) / "tags"(标签搜索) / "history"(按历史)
        style: str - "explore" / "standard" / "conservative"，影响最终浮动幅度
        user_tuning: dict|None - 用户调参 {factor_name: gain}, 仅在用户调过时传入

    返回：
        list[{anime, score, reasons, breakdown}, ...] 按 score 降序
    """
    weights = weights or WEIGHTS
    watched = query.get("watched_ids") or set()
    history_top = query.get("history_top")
    history_avg = query.get("history_avg")
    psych_profile = query.get("psych_profile")

    # 模式浮动幅度
    style_jitter = {
        "explore": 0.15,       # 探索型 ±15%
        "standard": 0.05,      # 标准型 ±5%
        "conservative": 0.02,  # 保守型 ±2%
    }.get(style, 0.05)

    # 心理模型浮动幅度（小幅）
    psych_jitter = 0.05

    # 调参的 tier 配置（全部 15 因子，三档按钮：低=-1, 中=0, 高=+1）
    # 每档对应三个具体倍率：(低, 中, 高)
    TUNING_TIERS = {
        # 低档：微调
        "low":      {"era": (0.7, 1.0, 1.3), "format": (0.7, 1.0, 1.3),
                     "eps": (0.7, 1.0, 1.3), "duration": (0.7, 1.0, 1.3),
                     "recency": (0.7, 1.0, 1.3), "quality_signal": (0.7, 1.0, 1.3)},
        # 中档：中等影响
        "mid":      {"rating": (0.8, 1.0, 1.2), "popularity": (0.8, 1.0, 1.2),
                     "favourites": (0.8, 1.0, 1.2), "consensus": (0.8, 1.0, 1.2)},
        # 高档：显著影响
        "high":     {"tag": (0.5, 1.0, 2.0), "history": (0.5, 1.0, 2.0),
                     "studio": (0.3, 1.0, 3.0), "va": (0.3, 1.0, 3.0),
                     "staff": (0.3, 1.0, 3.0)},
    }

    def tuning_multiplier(factor_name, value, breakdown=None):
        """调参复合运算 v3.1：非线性缩放 + 因子交互。

        单因子基础倍率（与 v3.0 相同）：
          gain=-1 → lo, gain=0 → 1.0, gain=+1 → hi

        复合加成（当 breakdown 可用时）：
          - studio 高 + tag 高 → 标签×厂牌协同放大
          - history 高 + tag 高 → 历史×标签共振
          - rating 高 + consensus 高 → 质量共振
          - 厂牌三因子(studio/va/staff)同时调高 → 联动放大
        """
        if not user_tuning or factor_name not in user_tuning:
            return 1.0
        gain = user_tuning[factor_name]
        gain = max(-1, min(1, int(gain)))

        # 基础倍率
        base_mult = 1.0
        for tier_dict in TUNING_TIERS.values():
            if factor_name in tier_dict:
                lo, mid, hi = tier_dict[factor_name]
                if gain < 0:
                    base_mult = lo
                elif gain > 0:
                    base_mult = hi
                else:
                    base_mult = mid
                break

        # 无 breakdown 时直接返回基础倍率
        if not breakdown:
            return base_mult

        # === 复合运算：因子交互加成 ===
        bonus = 1.0

        # 1. 标签×厂牌协同：studio 高 + tag 高 → tag 效果放大
        if factor_name == "tag" and gain > 0:
            studio_gain = user_tuning.get("studio", 0)
            if studio_gain > 0:
                # studio 也调高时，tag 的效果额外放大
                synergy = 1.0 + 0.3 * min(gain, studio_gain)
                bonus *= synergy

        # 2. 历史×标签共振：history 高 + tag 高 → 历史匹配更精准
        if factor_name == "history" and gain > 0:
            tag_gain = user_tuning.get("tag", 0)
            if tag_gain > 0:
                bonus *= 1.2  # 共振加成

        # 3. 质量共振：rating 高 + consensus 高
        if factor_name in ("rating", "consensus") and gain > 0:
            other = "consensus" if factor_name == "rating" else "rating"
            if user_tuning.get(other, 0) > 0:
                bonus *= 1.15

        # 4. 厂牌联动：studio/va/staff 同时调高
        if factor_name in ("studio", "va", "staff") and gain > 0:
            brand_count = sum(1 for f in ("studio", "va", "staff")
                             if user_tuning.get(f, 0) > 0)
            if brand_count >= 2:
                bonus *= 1.0 + 0.2 * (brand_count - 1)  # 2个→1.2, 3个→1.4

        # 5. 历史因子值高时（候选与历史高度匹配），调参效果增强
        if factor_name == "history" and breakdown:
            hist_val = breakdown.get("history", 0.5)
            if hist_val > 0.7:
                # 历史匹配度越高，调参放大越明显
                bonus *= 1.0 + 0.5 * (hist_val - 0.7)

        return base_mult * bonus

    import random
    results = []
    for cand in candidates:
        cid = cand["id"]
        if cid in watched:
            continue

        # === 质量门槛（仅种子推荐模式） ===
        cand_score = cand.get("mean_score") or 0
        cand_fav = cand.get("favourites") or 0
        cand_pop = cand.get("popularity") or 0

        if mode == "similar":
            # 严格门槛：评分太低的不推荐
            if cand_score < 4.5:
                continue
            if cand_score < 5.0 and cand_fav < 3 and cand_pop > 100_000:
                continue
        else:
            # 标签/历史模式：只过滤真正的"空数据"番剧
            if cand_score <= 0 and cand_fav <= 0 and (cand_pop <= 0 or cand_pop > 500_000):
                continue

        # 算各因子
        r_rating,  rs_rating  = rating_factor(cand)
        r_pop,     _          = popularity_factor(cand)
        r_fav,     rs_fav     = favourites_factor(cand)
        r_era,     rs_era     = era_factor(cand, query.get("year"))
        r_fmt,     rs_fmt     = format_factor(cand, query.get("format"))
        r_stu,     rs_stu     = studio_factor(cand, query.get("studios"))
        r_va,      rs_va      = va_factor(cand, query.get("vas"))
        r_staff,   rs_staff   = staff_factor(cand, query.get("staff"))
        r_eps,     _          = eps_factor(cand, query.get("eps_bucket"))
        r_dur,     _          = duration_factor(cand, query.get("duration_bucket"))
        r_rec,     _          = recency_factor(cand)
        r_q,       _          = quality_signal_factor(cand)
        r_cons,    rs_cons    = consensus_factor(cand)
        r_tag                  = tag_sims.get(cid, 0.0)
        r_hist,    rs_hist     = history_factor(cand, history_top, history_avg)

        # 因子分解
        breakdown = {
            "tag":            r_tag,
            "rating":         r_rating,
            "popularity":     r_pop,
            "favourites":     r_fav,
            "era":            r_era,
            "format":         r_fmt,
            "studio":         r_stu,
            "va":             r_va,
            "staff":          r_staff,
            "eps":            r_eps,
            "duration":       r_dur,
            "recency":        r_rec,
            "quality_signal": r_q,
            "consensus":      r_cons,
            "history":        r_hist,
        }

        # === 阶段 4: 14 因子加权几何平均（包含 history 40%）===
        base_factors = ["tag", "rating", "popularity", "favourites", "era",
                       "format", "studio", "va", "staff", "eps", "duration",
                       "recency", "quality_signal", "consensus", "history"]
        base_weight_sum = sum(weights.get(k, 0) for k in base_factors)

        if base_weight_sum > 0:
            log_sum = 0
            for k in base_factors:
                w = weights.get(k, 0)
                v = max(breakdown[k], 0.001)  # 避免log(0)
                log_sum += w * math.log(v)
            base_score = math.exp(log_sum / base_weight_sum)
        else:
            base_score = 0

        # === 阶段 5: 心理模型乘性加成（独立，±5% 浮动）===
        r_psych, _ = psych_match_factor(cand, psych_profile)
        if r_psych > 0:
            # 中心化在 0.5: <0.5 减分, >0.5 加分
            psych_mult = 1.0 + (r_psych - 0.5) * 2.0
            # 小幅浮动
            psych_mult *= (1.0 + random.uniform(-psych_jitter, psych_jitter))
            psych_mult = max(0.1, min(3.0, psych_mult))
        else:
            psych_mult = 1.0

        # === 阶段 6: 模式浮动 ===
        style_jitter_val = 1.0 + random.uniform(-style_jitter, style_jitter)

        # === 阶段 7: 调参后处理（仅当用户调过，含复合运算）===
        tuning_mult = 1.0
        if user_tuning:
            for fname in base_factors:
                tuning_mult *= tuning_multiplier(fname, user_tuning.get(fname, 0), breakdown)

        # === 组合最终分 ===
        final_score = base_score * psych_mult * style_jitter_val * tuning_mult

        # 收集理由（高分的才写出来）
        reasons = []
        if r_tag >= 0.25:
            reasons.append(f"标签相似 {r_tag:.2f}")
        if rs_rating:  reasons.append(rs_rating)
        if rs_fav and r_fav >= 0.5:  reasons.append(rs_fav)
        if rs_era:    reasons.append(rs_era)
        if rs_fmt:    reasons.append(rs_fmt)
        if rs_stu:    reasons.append(rs_stu)
        if rs_va:     reasons.append(rs_va)
        if rs_staff:  reasons.append(rs_staff)
        if rs_cons:   reasons.append(rs_cons)
        if rs_hist:   reasons.append(rs_hist)
        if r_rec >= 0.8: reasons.append("新番")
        if r_eps >= 0.95 and query.get("eps_bucket") is not None:
            reasons.append(f"集数档 {EPS_BUCKET_LABELS[query['eps_bucket']]}")
        if r_dur >= 0.95 and query.get("duration_bucket") is not None:
            reasons.append(f"时长档 {DURATION_BUCKET_LABELS[query['duration_bucket']]}")

        results.append({
            "anime":     cand,
            "score":     round(final_score, 4),
            "reasons":   reasons[:5],
            "breakdown": breakdown,
        })

    results.sort(key=lambda x: -x["score"])
    return results[:top_k]


# ============================================================
# 调试辅助：打印分数明细
# ============================================================
def explain(result, weights=None):
    """把一条 re_rank 结果的 14 个因子全打出来。"""
    weights = weights or WEIGHTS
    b = result["breakdown"]
    name = result["anime"].get("name_cn") or result["anime"].get("name")
    print(f"  {name} (id={result['anime']['id']})  total={result['score']}")
    print(f"    reasons: {result['reasons']}")
    for k, v in b.items():
        bar = "#" * int(v * 20)
        print(f"    {k:14s} w={weights[k]:.2f} v={v:.2f} contrib={weights[k]*v:.3f}  {bar}")
