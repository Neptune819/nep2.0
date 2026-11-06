"""
data_loader.py
================
番剧数据加载器 — 改用 AniList GraphQL 公开 API。

为什么不用 Bangumi？
    - next.bgm.tv 生成的 token 不被 api.bgm.tv 接受（401）
    - 老 bgm.tv 整个 520 挂了
    - Bangumi v0 API 即使有 token 也只放开了 1, 2 两个 ID 公开

为什么用 AniList？
    - 公开 GraphQL API，无需 token
    - 数据字段比 Bangumi 老 API 更全：真 tags、声优、staff、年份、cover
    - 通过不同 sort 组合可拿 10,000+ 部不同时段的番剧

字段对照：
    Bangumi 老 API   →  AniList
    ──────────────     ───────
    name_cn            title.native / userPreferred
    tags (无)          tags[].name  ←─ 真 tag！
    summary            description
    rating.score       averageScore
    air_date           startDate.year
    eps                episodes
    (无)               staff[] / characters[].voiceActors  ←─ 导演+声优！
    (无)               studios  ←─ 制作公司

限制：
    - 每个 sort 最多 5,000 条（用 sort: ID + sort: ID_DESC 组合）
    - 100 页 × 2 sort = 200 次请求，约 1-2 分钟
"""
import os
import re
import json
import time
import unicodedata
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dotenv import load_dotenv

load_dotenv()

ANILIST_URL = "https://graphql.anilist.co"
FETCH_DELAY = float(os.getenv("FETCH_DELAY", "0.3"))
FETCH_CONCURRENCY = int(os.getenv("FETCH_CONCURRENCY", "3"))
ANIME_PER_PAGE = 50  # AniList 单页上限

CACHE_FILE = Path(__file__).parent / "data" / "anime_cache.json"
CN_MAPPING_FILE = Path(__file__).parent / "data" / "bangumi_cn_mapping.json"
TAG_TRANS_FILE = Path(__file__).parent / "data" / "tag_translations.json"
VA_TRANS_FILE = Path(__file__).parent / "data" / "va_translations.json"
SUMMARY_TRANS_FILE = Path(__file__).parent / "data" / "summary_translations.json"

# ============== 本地增强数据 ==============

def _load_cn_mapping() -> dict:
    if not CN_MAPPING_FILE.exists():
        return {}
    with open(CN_MAPPING_FILE, "r", encoding="utf-8") as f:
        m = json.load(f)
    return {int(k): v for k, v in m.get("id_to_cn", {}).items()}


def _load_tag_translations() -> dict:
    if not TAG_TRANS_FILE.exists():
        return {}
    with open(TAG_TRANS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_va_translations() -> dict:
    """声优中文译名映射（罗马字 → 中文）。合并 hard-coded 字典和外部 JSON。"""
    base = dict(_VA_CN_ALIASES)
    if VA_TRANS_FILE.exists():
        try:
            with open(VA_TRANS_FILE, "r", encoding="utf-8") as f:
                ext = json.load(f)
            # 外部 JSON 优先级高
            for k, v in ext.items():
                if v and any('\u4e00' <= c <= '\u9fff' for c in v):
                    base[k] = v
        except Exception:
            pass
    return base


_CN_MAPPING = None
_MAL_CN_MAPPING = None
_BANGUMI_TITLES = None
_TAG_TRANS = None
_VA_TRANS = None


def _get_cn_mapping() -> dict:
    global _CN_MAPPING
    if _CN_MAPPING is None:
        _CN_MAPPING = _load_cn_mapping()
    return _CN_MAPPING


def _get_mal_cn_mapping() -> dict:
    """MAL id → 中文名（兜底用）"""
    global _MAL_CN_MAPPING
    if _MAL_CN_MAPPING is None:
        if not CN_MAPPING_FILE.exists():
            return {}
        with open(CN_MAPPING_FILE, "r", encoding="utf-8") as f:
            m = json.load(f)
        _MAL_CN_MAPPING = {int(k): v for k, v in m.get("id_to_cn_mal", {}).items()}
    return _MAL_CN_MAPPING


def _get_bangumi_titles() -> dict:
    """读取随项目提供的 bangumi-data 译名和别名，不依赖运行时网络。"""
    global _BANGUMI_TITLES
    if _BANGUMI_TITLES is None:
        if CN_MAPPING_FILE.exists():
            with open(CN_MAPPING_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            _BANGUMI_TITLES = {
                field: mapping.get(field, {})
                for field in ("id_to_cn", "id_to_jp", "id_to_en")
            }
        else:
            _BANGUMI_TITLES = {}
    return _BANGUMI_TITLES


def _get_tag_trans() -> dict:
    global _TAG_TRANS
    if _TAG_TRANS is None:
        _TAG_TRANS = _load_tag_translations()
    return _TAG_TRANS


def _get_va_trans() -> dict:
    """声优罗马字 → 中文译名（合并 hard-coded + 外部 JSON）。"""
    global _VA_TRANS
    if _VA_TRANS is None:
        _VA_TRANS = _load_va_translations()
    return _VA_TRANS


def _load_summary_translations() -> dict:
    """简介中文翻译（anime_id → 中文简介）。"""
    if not SUMMARY_TRANS_FILE.exists():
        return {}
    with open(SUMMARY_TRANS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_summary_cn(anime: dict) -> str:
    """获取番剧的中文简介。优先用预翻译，否则返回原文。"""
    summary = (anime.get("summary") or "").strip()
    if not summary:
        return ""
    # 如果已经是中文，直接返回
    if any('\u4e00' <= c <= '\u9fff' for c in summary):
        return summary
    # 查翻译缓存
    trans = _load_summary_translations()
    return trans.get(str(anime.get("id", "")), summary)


# ============== Staff 角色名翻译 ==============

_ROLE_CN = {
    # 主创
    "Director": "监督",
    "Series Director": "系列监督",
    "Chief Director": "总监督",
    "Assistant Director": "副监督",
    "Episode Director": "分镜",
    # 原作
    "Original Story": "原作",
    "Original Creator": "原案",
    "Original Character Design": "角色原案",
    "Original Work": "原作",
    # 脚本
    "Script": "脚本",
    "Screenplay": "编剧",
    "Series Composition": "系列构成",
    # 角色设计/作画
    "Character Design": "角色设计",
    "Sub Character Design": "副角色设计",
    "Chief Animation Director": "总作监",
    "Animation Director": "作画监督",
    # 音乐
    "Music": "音乐",
    # 制作
    "Producer": "制作人",
    "Executive Producer": "总制作人",
    "Planning": "企划",
    "Production": "制作",
    "Production Cooperation": "协力",
    # 美术
    "Art Director": "美术监督",
    "Art Design": "美术设计",
    "Color Design": "色彩设计",
    # 摄影/SFX
    "Director of Photography": "摄影监督",
    "Sound Director": "音响监督",
    "Sound Effects": "音效",
    "Editing": "剪辑",
    # 主题歌
    "Theme Song Performance": "主题歌",
    "Theme Song": "主题歌",
    "Theme Song Lyrics": "主题歌作词",
    "Theme Song Composition": "主题歌作曲",
    "Insert Song Performance": "插入歌",
    # 其他
    "2nd Key Animation": "第二原画",
    "Key Animation": "原画",
    "In-Between Animation": "动画",
}


# ============================================================
# 知名声优中文别名表（罗马字 → 中文）
# 数据源：AniList 不给中文名，这些是用户常见搜法
# 没用到的 VA 还是只有英文名（搜不到就引导用罗马字）
# ============================================================
_VA_CN_ALIASES = {
    "Kana Hanazawa":      "花泽香菜",
    "Rie Kugimiya":       "钉宫理惠",
    "Tomokazu Sugita":    "杉田智和",
    "Takahiro Sakurai":   "樱井孝宏",
    "Jun Fukuyama":       "福山润",
    "Hiroshi Kamiya":     "神谷浩史",
    "Mamoru Miyano":      "宫野真守",
    "Daisuke Ono":        "小野大辅",
    "Yuichi Nakamura":    "中村悠一",
    "Hiro Shimono":       "下野纮",
    "Junichi Suwabe":     "诹访部顺一",
    "Kazuya Nakai":       "中井和哉",
    "Akira Ishida":       "石田彰",
    "Megumi Hayashibara": "林原惠",
    "Kotono Watanabe":    "渡边久美子",
    "Aya Endo":           "远藤绫",
    "Ai Kayano":          "茅野爱衣",
    "Saori Hayami":       "早见沙织",
    "Ayana Taketatsu":    "竹达彩奈",
    "Inori Minase":       "水濑祈",
    "Mikako Komatsu":     "小松未可子",
    "Ami Koshimizu":      "小清水亚美",
    "Rina Satou":         "佐藤利奈",
    "Yui Horie":          "堀江由衣",
    "Rie Tanaka":         "田中理惠",
    "Nana Mizuki":        "水树奈奈",
    "Yukana":             "ゆかな",
    "Aya Hisakawa":       "久川绫",
    "Satsuki Yukino":     " yukino  ",
    "Tomoko Kawakami":    "川上とも子",
    "Yuko Minaguchi":     "皆口裕子",
    "Akemi Kanda":        "神田朱未",
    "Yuko Goto":          "后藤邑子",
    "Chieko Higashiyama": "东山奈央",
    "Ayako Kawasumi":     "川澄绫子",
    "Ryoka Yuzuki":       "柚木凉香",
    "Yukari Tamura":      "田村ゆかり",
    "Rina Hidaka":        "日高里菜",
    "Eri Kitamura":       "喜多村英梨",
    "Aoi Yuki":           "悠木碧",
    "Ayumi Fujimura":     "藤村步",
    "Minori Chihara":     "茅原实里",
    "Yoko Hikasa":        "日笠阳子",
    "Shizuka Ito":        "伊藤静",
    "Emiri Kato":         "加藤英美里",
    "Satomi Akesaka":     "明坂聪美",
    "Kaori Nazuka":       "名塚佳织",
    "Mai Nakahara":       "中原麻衣",
    "Ryoko Shiraishi":    "白石凉子",
    "Akiko Yajima":       "矢岛晶子",
    "Asami Tan":          "丹下樱",
}


def _va_cn_to_en() -> dict:
    """中文名 → 罗马字。"""
    return {cn: romaji for romaji, cn in _VA_CN_ALIASES.items()}


def _build_va_search_index() -> dict:
    """VA 搜索索引：搜任何"中/英/罗马字"都能命中。"""
    idx = {}
    for romaji, cn in _VA_CN_ALIASES.items():
        idx[romaji] = romaji
        idx[cn] = romaji
    return idx

# ============== GraphQL 查询 ==============

MEDIA_LIST_QUERY = """
query ($page: Int, $perPage: Int, $sort: MediaSort) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total currentPage lastPage hasNextPage }
    media(type: ANIME, sort: [$sort]) {
      id
      idMal
      title { romaji english native userPreferred }
      description(asHtml: false)
      tags { name rank isMediaSpoiler }
      averageScore
      meanScore
      popularity
      favourites
      startDate { year month day }
      endDate { year month day }
      episodes
      duration
      status
      format
      coverImage { extraLarge large medium color }
      bannerImage
      season
      seasonYear
      studios(isMain: true) { nodes { name } }
      staff(perPage: 8, sort: [RELEVANCE]) {
        edges { role node { name { full native } } }
      }
      characters(perPage: 10, sort: [ROLE, RELEVANCE]) {
        edges {
          role
          node { name { full native } }
          voiceActors(language: JAPANESE) { name { full native } }
        }
      }
    }
  }
}
"""


# ============== 拉取 ==============

def _fetch_page(page: int, sort: str, max_retries: int = 3) -> dict | None:
    """拉一页 AniList 数据。"""
    variables = {"page": page, "perPage": ANIME_PER_PAGE, "sort": sort}
    for attempt in range(max_retries):
        try:
            r = requests.post(ANILIST_URL,
                              json={"query": MEDIA_LIST_QUERY, "variables": variables},
                              headers={"Content-Type": "application/json"},
                              timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:  # 限流
                wait = (attempt + 1) * 2
                print(f"  限流，等 {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code == 500:
                # 偶尔的 500，重试
                time.sleep(1)
                continue
        except Exception as e:
            print(f"  page={page} 异常: {e}")
            time.sleep(1)
    return None


def _normalize(media: dict) -> dict:
    """把 AniList 原始数据转成统一格式（带中文增强）。"""
    title = media.get("title") or {}
    media_id = media["id"]
    id_mal = media.get("idMal")
    tag_trans = _get_tag_trans()
    cn_map = _get_cn_mapping()
    mal_cn_map = _get_mal_cn_mapping()

    # 中文名：先查 anilist id，再查 mal id 兜底
    name_cn = cn_map.get(media_id, "")
    if not name_cn and id_mal:
        name_cn = mal_cn_map.get(id_mal, "")

    # 英文/日文 tag → 中文 tag
    tags_en = [t["name"] for t in (media.get("tags") or []) if not t.get("isMediaSpoiler")]
    tags_cn = [tag_trans.get(t, t) for t in tags_en]

    # 规范化 air_date
    start = media.get("startDate") or {}
    air = ""
    if start.get("year"):
        if start.get("month"):
            air = f"{start['year']}-{start['month']:02d}"
            if start.get("day"):
                air += f"-{start['day']:02d}"
        else:
            air = str(start["year"])

    return {
        "id": media_id,
        "id_mal": id_mal,
        "name": title.get("userPreferred") or title.get("romaji") or title.get("native") or title.get("english") or "",
        "name_jp": title.get("native") or title.get("romaji") or "",
        "name_en": title.get("english") or title.get("romaji") or "",
        "name_cn": name_cn,  # ← 新增
        "summary": (media.get("description") or "").replace("<br>", "\n").replace("<i>", "").replace("</i>", "")[:1000],
        "tags": tags_en,
        "tags_cn": tags_cn,  # ← 新增
        "tags_with_rank": [{"name": t["name"], "rank": t.get("rank", 0)}
                           for t in (media.get("tags") or []) if not t.get("isMediaSpoiler")],
        "rating": ((media.get("averageScore") or 0) / 10),
        "mean_score": ((media.get("meanScore") or 0) / 10),
        "popularity": media.get("popularity") or 0,
        "favourites": media.get("favourites") or 0,
        "year": start.get("year"),
        "air_date": air,
        "eps": media.get("episodes") or 0,
        "duration": media.get("duration") or 0,
        "status": media.get("status"),
        "format": media.get("format"),
        "cover": (media.get("coverImage") or {}).get("extraLarge") or (media.get("coverImage") or {}).get("large") or "",
        "banner": media.get("bannerImage") or "",
        "season": media.get("season"),
        "season_year": media.get("seasonYear"),
        "studios": [s["name"] for s in ((media.get("studios") or {}).get("nodes") or [])],
        "staff": [{"name": e["node"]["name"]["full"], "role": e["role"]}
                  for e in ((media.get("staff") or {}).get("edges") or [])],
        "characters": [{
            "name": e["node"]["name"]["full"],
            "role": e["role"],
            "va": [va["name"]["full"] for va in (e.get("voiceActors") or [])]
        } for e in ((media.get("characters") or {}).get("edges") or [])],
    }


def fetch_all(concurrency: int | None = None, delay: float | None = None, resume: bool = True) -> list[dict]:
    """
    拉取所有番剧详情。用 AniList GraphQL，多 sort 组合。

    策略：
    - sort: ID (1-5000, 主要是 80-2000s 老番)
    - sort: ID_DESC (新番)
    - sort: POPULARITY_DESC (热门)
    - sort: FAVOURITES_DESC (高收藏)
    - 去重合并
    """
    if concurrency is None:
        concurrency = FETCH_CONCURRENCY
    if delay is None:
        delay = FETCH_DELAY

    # 加载已有缓存
    existing: dict[int, dict] = {}
    if resume and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                existing_list = json.load(f)
            existing = {a["id"]: a for a in existing_list}
            print(f"[CACHE] 已有 {len(existing)} 条")
        except (json.JSONDecodeError, IOError):
            print("[WARN] 缓存损坏，从头开始")

    all_anime: dict[int, dict] = dict(existing)
    save_lock = Lock()
    last_save = time.time()

    def save():
        with save_lock:
            _save(list(all_anime.values()))

    # 要拉的 sort 组合
    sorts = ["ID", "ID_DESC", "POPULARITY_DESC", "FAVOURITES_DESC"]

    print("=" * 60)
    print("[FETCH] AniList 番剧数据拉取器")
    print(f"[SORT] {', '.join(sorts)}")
    print(f"[CONC] 并发={concurrency}, 间隔={delay}s")
    print("=" * 60)

    def fetch_sort(sort: str):
        """拉一个 sort 下的所有页."""
        page = 1
        last_page = None
        while True:
            if last_page and page > last_page:
                break
            data = _fetch_page(page, sort)
            if not data or not data.get("data"):
                break
            page_data = data["data"]["Page"]
            page_info = page_data["pageInfo"]
            media_list = page_data.get("media") or []
            last_page = page_info.get("lastPage", last_page)

            new_count = 0
            for m in media_list:
                if m["id"] not in all_anime:
                    all_anime[m["id"]] = _normalize(m)
                    new_count += 1
                else:
                    # 已存在，但可以更新（其他 sort 可能更新 tags/staff）
                    existing_m = all_anime[m["id"]]
                    new_m = _normalize(m)
                    # 保留更完整的（tags 多的赢）
                    if len(new_m.get("tags") or []) > len(existing_m.get("tags") or []):
                        all_anime[m["id"]] = new_m

            print(f"  [{sort:20s}] page {page}/{last_page} +{new_count} 总 {len(all_anime)}")
            page += 1
            time.sleep(delay)

            # 定期保存
            if time.time() - last_save > 15:
                save()
                last_save_locals = time.time()

    # 顺序跑每个 sort（避免同时请求限流）
    for sort in sorts:
        print(f"\n[RUN] sort={sort}")
        try:
            fetch_sort(sort)
        except KeyboardInterrupt:
            print("\n[STOP] 中断，保存进度...")
            save()
            return list(all_anime.values())
        save()

    save()
    print("=" * 60)
    print(f"[DONE] 共 {len(all_anime)} 条")
    return list(all_anime.values())


def _save(data: list):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_mb = CACHE_FILE.stat().st_size / 1024 / 1024
    print(f"  [SAVE] {len(data)} 条 ({size_mb:.1f} MB)")


# ============== 加载 / 搜索 ==============

def _normalized_title(value: str) -> str:
    """统一全半角、大小写与标题标点，保留中日韩文字及数字。"""
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(c for c in value if unicodedata.category(c)[0] in ("L", "N"))


def _title_variants(anime: dict):
    """按展示名、其他标题、Bangumi 别名顺序生成不重复的检索词。"""
    seen = set()
    for field in ("name_cn", "name", "name_jp", "name_en", "name_aliases"):
        raw_values = anime.get(field) or []
        if isinstance(raw_values, str):
            raw_values = [raw_values]
        for raw in raw_values:
            if not isinstance(raw, str):
                continue
            title = raw.strip()
            key = _normalized_title(title)
            if not key or key in seen:
                continue
            seen.add(key)
            yield field, title, key


def display_name_cn(anime: dict) -> str:
    """返回番剧的"显示用中文名"。

    规则：
      1. name_cn 非空、且不等于 name_en / name → 用 name_cn
      2. 否则优先找含中文的字段（name_jp / name_en / name）
      3. 都没有则用 name_en / name_jp / name 首个非空

    为什么不用 name_cn 一把梭？
      - 1,403 部 P2 番剧 name_cn 为空
      - 245 部 name_cn == name_en（fate 等英文原名被"硬翻"成同字）
      - 268 部 name_cn == name（罗马字复用，没有中文段）
      - 1 部 name_cn 含 U+FFFD 替换符
    用这个函数统一处理后，前端不需要各自回退。
    """
    cn = (anime.get("name_cn") or "").strip()
    if cn and "�" not in cn:
        ne = (anime.get("name_en") or "").strip()
        nm = (anime.get("name") or "").strip()
        if cn != ne and cn != nm:
            return cn

    # 检测中文字符（含中文段）
    def has_cn(s: str) -> bool:
        return any("\u4e00" <= c <= "\u9fff" for c in s)

    # name_jp 中常有国产番剧的中文原名（AniList 给国产动画的 name_jp 是中文）
    for k in ("name_jp", "name_en", "name"):
        v = (anime.get(k) or "").strip()
        if v and has_cn(v):
            return v
    # 全无中文则按英文优先回退
    for k in ("name_en", "name_jp", "name"):
        v = (anime.get(k) or "").strip()
        if v:
            return v
    return ""


# 有效的番剧格式（排除 MUSIC——歌曲/MV、None——未发布项目）
_VALID_ANIME_FORMATS = frozenset({"TV", "OVA", "MOVIE", "ONA", "SPECIAL", "TV_SHORT"})


def _is_chinese_anime(anime: dict) -> bool:
    """判断是否为国漫（中国动画）。

    多维度识别（任一命中即为国漫）：
      1. Studio 白名单：制作公司命中已知中国动画公司列表。
      2. 名字特征：name_jp / name / name_en 任意一个全部由中文字符组成
         （允许空格/标点）且没有任何日文假名。
    """
    name_jp = (anime.get("name_jp") or "").strip()
    name_cn = (anime.get("name_cn") or "").strip()
    name = (anime.get("name") or "").strip()
    name_en = (anime.get("name_en") or "").strip()
    studios = anime.get("studios") or []

    def _has_jp_kana(s: str) -> bool:
        """是否包含日文假名（平假名/片假名）"""
        return any('぀' <= c <= 'ゟ' or '゠' <= c <= 'ヿ' for c in s)

    def _is_chinese_only(s: str) -> bool:
        """去除常见标点/空格后，是否全部由中文字符组成"""
        if not s:
            return False
        cleaned = re.sub(r'[ ·ー～！？!:,。、《》【】()\-—_/\\.,\'"]+', '', s)
        if not cleaned:
            return False
        return all('一' <= c <= '鿿' for c in cleaned)

    # ============ 维度 1: Studio 白名单 ============
    for s in studios:
        if not isinstance(s, str):
            continue
        s_stripped = s.strip()
        # 如果是已知日漫 studio → 直接判 False,避免误杀(日漫中含汉字标题的)
        if s_stripped in _JAPANESE_STUDIOS:
            return False
        # 排除已知的韩国 studio
        if s_stripped in _KOREAN_STUDIOS:
            continue
        # 命中中国 studio 白名单
        if s_stripped in _CHINESE_STUDIOS:
            return True

    # ============ 维度 2: 名字特征 ============
    candidate_name_fields = [name_jp, name, name_en]
    for field in candidate_name_fields:
        if not field:
            continue
        if _has_jp_kana(field):
            continue
        if _is_chinese_only(field):
            return True

    # name_jp 和 name_cn 完全相同(且都是中文)→ 国漫
    if name_jp and name_cn and name_jp == name_cn and _is_chinese_only(name_jp):
        return True

    return False


# 已知中国动画公司白名单（精确匹配）
# 来源:实际数据扫描 + 公开资料
_CHINESE_STUDIOS = frozenset({
    # 一线动画公司
    "Studio LAN", "Haoliners Animation League", "Haoliners Animation",
    "Original Force", "Original Force Animation", "Pb Animation", "Sunflowers",
    "L2 Animation", "B.COOL Pictures", "Paper Plane Animation Studio",
    "Bingtang Animation", "Boutique Animation", "Mainland Animation",
    "Wit Studio China", "Wonder Cat Animation", "Elephant Animation",
    "Fenghua Animation", "Lemon Jam", "CG Land Animation",
    "Studio DURIAN", "Mili Pictures", "Yao-China", "Fenghua Qingyu",
    "Weiying Technology", "Rocen", "San Xian", "GZ Yingqi",
    "Rocen Animation", "Yunbei Animation", "Baimiao Animation",
    "Lans Studio", "Ling Media", "AhaWorld",
    "Haoliners Animation League Co.", "Fenghua Animation Co.",
    "Original Force Pictures", "Pb Animation Co.", "L2 Pictures",

    # 平台/出品
    "Bilibili Animation", "iQIYI Animation", "Tencent Animation",
    "Tencent Penguin Pictures", "Tencent Penguin", "AHA Entertainment",
    "Beijing Enlight Pictures", "Beijing Enlight Animation", "Enlight Media",

    # 老牌美术片厂
    "Shanghai Animation Film Studio",

    # 实际数据中识别出的中国动画公司
    "Ruo Hong Culture",          # 若鸿文化
    "Sparkly Key Animation",     # 在本数据中均为中国动画(牧神记/吞噬星空/斗罗大陆/师兄)
    "HMCH",                      # 汉恩动画(罗小黑战记/万圣街)
    "YHKT Entertainment",         # 灵笼制作方
    "Coco Cartoon",              # 彩条屋
    "Red Dog Culture House",     # 红狗文化(天官赐福)
    "Samsara Studio",            # 雾山五行
    "B&T",                       # 大鱼海棠
    "Liyu Culture",              # 栗子文化(仙王)
    "miHoYo Anime",              # 米哈游动画
    "CCTV Animation",            # 央视动画
    "CICF",                      # 中国国际动漫节
    "VASOUN Animation",
    "Haoliners Animation",
    "Ruo Hong",
    "Hanmu Animation",
    "Hanmu",
    # 2026-08-12 第二轮扩充
    "Motion Magic",              # 斗破苍穹/武动乾坤/元尊
    "Foch",                      # 全职法师/完美世界(福煦动画)
    "Pili International Multimedia",  # 霹雳国际(台湾/中文)
    "Fantasier Animation",       # 米哈游旗下(崩坏:星穹铁道)
    "Lingsanwu Animation",       # 灵三午(全职高手4/是王者啊)
    "Shenman Entertainment",     # 神漫娱乐(莽荒纪/战神/择天记)
    "Yien Animation",            # 艺恩(光影之外/云深不知梦)
    "Success",                   # 成功动画(中国惊奇先生/超游世界)
    "Light Chaser Animation",    # 追光动画(白蛇/聊斋)
    "Big Firebird Cultural Media",  # 大火鸟(一人之下3/崩坏)
    "Shengying Animation",       # 升影(是王者啊/成何体统/剑网3)
    "Jade Animation",            # 玉皇朝(神雕侠侣)
    "Heart & Soul Animation",    # 心魂(左手上篮)
    "Qiyuan Yinghua",            # 起源映画(一人之下6)
    "Qingxiang",                 # 青响(百炼成神)
    "Colored Pencil Animation",  # 彩铅动画(全职高手2/3)
    "G.CMay Animation & Film",   # 骏豪映画(喂哥哥/诡秘之主)
    "Kung Fu Frog Animation",    # 功夫青蛙(在下野怪)
    "Wawayu Animation",          # 蛙与鱼(蜀山奇仙录)
    "Nice Boat Animation",       # 良船动画(大理寺日志)
    "Yi Animation",              # 艺动画(雄狮少年)
    "HuaMei Animation",          # 华美动画(黄金庭院)
    "Yofox Culture",             # 妖狐文化(绝顶)
    "DC Impression Vision",      # 视美影业(武动乾坤4)
    "Yinhe Changxing Culture",   # 银河长兴(三国演义)
    "Transcendence Picture",     # 超越影业(雄兵连)
    "Tang Kirin Culture",        # 唐麒麟(修罗武神)
    "Dancing CG Studio",         # 舞之CG(万古至尊)
    "FENZ",                      # 芬兹(非人哉)
    "Build Dream",               # 创梦(自川/仙逆)
    "Motherland Entertainment",  # 母国娱乐
    "Gravity Well",              # 重力井(李时珍)
    "Flint Sugar",               # 糖葫芦(崩坏)
    "Studio Tumble",             # 翻车(崩坏)
    "Block 12",                  # 第12区块
    "Barnum Studio",             # 巴纳姆
    "Chuangqi Studio",           # 创奇(杀手古德)
    "L² Studio",                 # L2 Studio
    "DC Impression Vision",
    "Colored Pencil Animation Japan",  # 彩铅动画日本分部
    "Cloud Art",                 # 云之艺术
    "Foch Films",
    "Big Firebird",
    "Original Penguin",

    # 大写别名(数据中偶有)
    "Haoliners", "iQIYI", "BILIBILI", "Bilibili", "Tencent", "Yinhe Shanshui",
})

# 必须排除的韩国动画公司（数据中误标为国漫 studio）
_KOREAN_STUDIOS = frozenset({
    "Studio Mir",  # 韩国 (DOTA 龙之血, 希曼等)
    "Sanjin Animation",  # 韩国
})

# 已知日漫 studio 黑名单
# 作用:当 studio 是这些时,即使名字看起来像中文(汉字),也判定为日漫
# 避免误杀像 银魂/犬夜叉/圣斗士星矢 这种用汉字标题的日漫
_JAPANESE_STUDIOS = frozenset({
    "Toei Animation", "Sunrise", "J.C.STAFF", "MADHOUSE", "Studio DEEN",
    "Production I.G", "OLM", "TMS Entertainment", "A-1 Pictures",
    "Studio Pierrot", "AIC", "bones", "Nippon Animation", "Shin-Ei Animation",
    "SILVER LINK.", "Kyoto Animation", "Shaft", "Tatsunoko Production",
    "Xebec", "LIDENFILMS", "GONZO", "MAPPA", "Satelight", "Brain's Base",
    "T-REX", "Seven", "WIT STUDIO", "Doga Kobo", "DLE", "Tokyo Movie Shinsha",
    "Group TAC", "Bandai Namco Pictures", "Ashi Productions", "Kinema Citrus",
    "Lerche", "Tezuka Productions", "8-bit", "P.A.WORKS", "Fanworks", "feel.",
    "ufotable", "SynergySP", "ZEXCS", "Magic Bus", "Ajiado", "Gainax",
    "diomedéa", "Studio Gallop", "Studio Comet", "ARMS", "Studio 4°C",
    "david production", "POLYGON PICTURES", "Actas", "Studio Gokumi",
    "project No.9", "Telecom Animation Film", "SANZIGEN", "Studio Hibari",
    "Passione", "TNK", "Animate Film", "Zero-G", "Studio Ghibli",
    "WHITE FOX", "EMT Squared", "Hal Film Maker", "Nomad", "Asahi Production",
    "CoMix Wave", "Artland", "Signal.MD", "A.C.G.T.", "GoHands",
    "Bridge", "C-Station", "Lerche", "Studio 3Hz", "Studio Bind",
    "Studio Deen", "SILVER LINK.", "Trigger", "Lay-duce", "Marza Animation Planet",
    "Production IMS", "Dogakobo", "Doga Kobo", "WAO World", "Trans Arts",
    "BEE MEDIA", "8bit", "Science SARU", "Drive", "GoHands",
    "Fanworks", "A-Real", "Arms Corporation", "Artland", "Bee Train",
    "Bee Media", "CINEMATOGRAPH", "Eiken", "feel.", "Frontier Works",
    "JAM", "Kitty Films", "Lantis", "Manglobe", "NAZ", "Office Academy",
    "Palm Studio", "Pioneer LDC", "Plum", "Production Reed", "Rabbit House",
    "Sega Sammy Entertainment", "Seven Arcs", "SHAFT", "Shogakukan Music",
    "Sony Music Entertainment", "Sunrise Music", "Tatsunoko Production",
    "TMS", "TMS-Sony", "Topcraft", "Triangle Staff", "TYO Animations",
    "Ufotable", "Wao World", "Wit Studio", "Yumeta Company",
    # 大小写变体
    "Toei", "Sunrise Inc.", "BONES", "Tatsunoko", "MAPPA Co., Ltd.",
    "Madhouse", "Pierrot", "AIC ASTA", "AIC Build", "AIC Classic",
    "AIC Plus+", "APPP", "ASATSU-DK", "Ashi Production", "Bee Train",
    "Bridge", "C-Station", "Chiba TV", "CloverWorks", "D.I.D.",
    "Digital Frontier", "Doga Kobo", "Eiken", "Encourage Films", "ENGI",
    "Feel", "Frontier Works", "Gathering", "GEMBA", "Graphinica",
    "Hoods Entertainment", "IMAGE", "IMAGIN", "J.C.Staff", "JAM",
    "Khara", "Kitty Films", "Knack Productions", "Larx Entertainment",
    "Liden Films", "LIDENFILMS", "LMS", "Lune", "M2",
    "Madhouse", "Manglobe", "Millepensee", "NAZ", "Nihon Ad Systems",
    "Office Academy", "Okuradono Nobori", "OLM", "Orange", "Palm Studio",
    "Pine Jam", "Platinum Vision", "Plum", "Polygon Pictures", "PP Project",
    "PRA", "Production Ace", "Production GoodBook", "Production IMS",
    "Production I.G", "Production Reed", "Project No.9", "Puzzle Animation Studio",
    "Robot", "Sakura Production", "SANZIGEN", "Science SARU", "Sega",
    "Seven Arcs", "SHAFT", "Shin-Ei Animation", "Shin-Ei",
    "Signal.MD", "SILVER LINK.", "Studio 3Hz", "Studio Bind", "Studio Chizu",
    "Studio Comet", "Studio Deen", "Studio Ghibli", "Studio Gokumi",
    "Studio Hibari", "Studio Kai", "Studio Live", "Studio Moriken",
    "Studio Nue", "Studio Pierrot", "Studio Signpost", "Studio VOLN",
    "Sublimation", "Sunrise", "SynergySP", "Tatsunoko Production",
    "Tear Studio", "Telecom Animation Film", "Tengu Kobo", "Tezuka Productions",
    "The Answerstudio", "TMS Entertainment", "TNK", "Toei Animation",
    "Topcraft", "TROYCA", "Tsuburaya Productions", "TYO Animations",
    "Ufotable", "UNLIMITED", "WAO World", "Wit Studio", "Woo Productions",
    "Xebec", "Yokohama Animation Lab", "Yumeta Company", "Zero-G", "ZEXCS",
})


def load_cache() -> list:
    if not CACHE_FILE.exists():
        raise FileNotFoundError(
            f"缓存不存在: {CACHE_FILE}\n"
            f"请先运行: python scripts/fetch_data.py"
        )
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 运行时二次过滤：排除非番剧格式 + 排除国漫
    titles = _get_bangumi_titles()
    result = []
    for anime in data:
        if anime.get("format") not in _VALID_ANIME_FORMATS or _is_chinese_anime(anime):
            continue
        key = str(anime.get("id", ""))
        mapped_cn = (titles.get("id_to_cn", {}).get(key) or "").strip()
        mapped_jp = (titles.get("id_to_jp", {}).get(key) or "").strip()
        mapped_en = (titles.get("id_to_en", {}).get(key) or "").strip()
        # Some mapping IDs point to a different season or work. Trust a Chinese
        # title only when its Japanese title matches this exact cache record.
        verified_title = (bool(mapped_jp) and _normalized_title(mapped_jp) == _normalized_title(anime.get("name_jp") or ""))
        if not mapped_jp and mapped_en:
            verified_title = _normalized_title(mapped_en) in {
                _normalized_title(anime.get("name") or ""),
                _normalized_title(anime.get("name_en") or ""),
            }
        aliases = []
        if mapped_cn and verified_title:
            anime["name_cn"] = mapped_cn
        if verified_title:
            aliases.extend((mapped_jp, mapped_en))
        if aliases:
            anime["name_aliases"] = aliases
        result.append(anime)
    return result


def find_by_name(name: str, cache: list | None = None, limit: int = 10) -> list:
    """按名称模糊搜索。"""
    if cache is None:
        cache = load_cache()
    key = _normalized_title(name)
    if not key:
        return []
    matches = []
    for a in cache:
        best = 0
        for _, _, title in _title_variants(a):
            score = 3 if key == title else 2 if title.startswith(key) else 1 if key in title else 0
            best = max(best, score)
        if best:
            matches.append((best, a))
    matches.sort(key=lambda item: (-item[0], -(item[1].get("popularity") or 0)))
    return [a for _, a in matches[:limit]]


def search(query: str, cache: list | None = None, limit: int = 20) -> list:
    """
    统一搜索函数 —— 同时支持：
      - 中文名（如"孤独摇滚"、"葬送的芙莉莲"）
      - 日文名（如"ぼっち・ざ・ろっく"）
      - 英文名（如"Bocchi the Rock"）
      - 中文 tag（如"异世界"、"校园"、"魔法"）
      - 英文 tag（如"Isekai"、"School"）

    返回带 _match / _score 字段的结果，按相关度排序。
    """
    if cache is None:
        cache = load_cache()
    q = query.strip().casefold()
    if not q:
        return []
    q_norm = _normalized_title(q)
    if not q_norm:
        return []

    exact, prefix, name_in, tag_in = [], [], [], []

    for a in cache:
        # 名称字段（中/英/日）
        name_score, name_field = 0, None
        for field, _, v_norm in _title_variants(a):
            base = {"name_cn": 10, "name_aliases": 9, "name": 8,
                    "name_jp": 7, "name_en": 7}[field]
            if q_norm == v_norm:
                s = base * 3
            elif v_norm.startswith(q_norm):
                s = base * 2
            elif q_norm in v_norm:
                s = base
            else:
                continue
            if s > name_score:
                name_score = s
                name_field = field

        # tag 字段（中英都搜）
        tag_score, tag_field = 0, None
        for field, base in [("tags_cn", 6), ("tags", 5)]:
            for t in (a.get(field) or []):
                tl = t.lower()
                if q == tl:
                    s = base * 3
                elif tl.startswith(q):
                    s = base * 2
                elif q in tl:
                    s = base
                else:
                    continue
                if s > tag_score:
                    tag_score = s
                    tag_field = field
                break

        best = max(name_score, tag_score)
        if best == 0:
            continue

        if name_score >= tag_score and name_field:
            entry = (a, name_score, f"name:{name_field}")
        else:
            entry = (a, tag_score, f"tag:{tag_field}")

        # 桶分类
        if best >= 24:
            exact.append(entry)
        elif best >= 12:
            prefix.append(entry)
        elif "name" in entry[2]:
            name_in.append(entry)
        else:
            tag_in.append(entry)

    def key(t):
        a, s, _ = t
        return (-s, -(a.get("popularity") or 0))

    ordered = sorted(exact, key=key) + sorted(prefix, key=key) + \
              sorted(name_in, key=key) + sorted(tag_in, key=key)

    results = []
    for a, s, mt in ordered[:limit]:
        item = dict(a)
        item["_match"] = mt
        item["_score"] = s
        results.append(item)
    return results


# ============== 批量导入 ==============

def batch_match_anime(text: str, cache: list | None = None) -> list:
    """从自由文本中批量识别番剧名称。

    算法：在文本中搜索所有已知番剧名（子串匹配），按名称长度降序排列
    长名字优先（如"进击的巨人 最终季"优先于"进击的巨人"），再去重。

    支持任意格式：换行分隔、逗号分隔、自然语言描述均可。

    返回：[{id, name, name_cn, rating, image, match_name, confidence}, ...]
    """
    if cache is None:
        cache = load_cache()

    if not text or not text.strip():
        return []

    # 与单条搜索使用相同的全半角、大小写和标点规范化规则。
    text_norm = _normalized_title(text)
    if len(text_norm) < 2:
        return []

    # 第一步：在文本中搜索已知番剧名
    # 每个番剧检查展示名、其他标题和社区别名，取第一个匹配的字段。
    raw_matches = []  # [(anime, field, name_len, name_raw), ...]

    # 预计算名称缓存，避免重复 strip/lower
    name_cache = {}  # aid -> [(field, name_raw, name_norm, length), ...]
    for a in cache:
        aid = a["id"]
        variants = [(field, raw, norm, len(norm))
                    for field, raw, norm in _title_variants(a) if len(norm) >= 2]
        if variants:
            name_cache[aid] = variants

    for a in cache:
        aid = a["id"]
        variants = name_cache.get(aid)
        if not variants:
            continue

        for field, name_raw, name_norm, name_len in variants:
            if name_norm in text_norm:
                raw_matches.append((a, field, name_len, name_raw))
                break  # 同一作品只取优先级最高的匹配字段。

    if not raw_matches:
        return []

    # 第二步：按名称长度降序排列（长的优先，因为更具体）
    raw_matches.sort(key=lambda x: -x[2])

    # 第三步：去重 —— 如果较短的名称是较长名称的子串（标准化后），则丢弃短的那个
    seen_ids = set()
    kept_norms = []  # [(aid, name_norm), ...]
    deduped = []

    for anime, field, name_len, name_raw in raw_matches:
        aid = anime["id"]
        if aid in seen_ids:
            continue
        name_norm = _normalized_title(name_raw)

        # 检查是否被已保留的更长的名称"包含"
        is_subset = False
        for kept_id, kept_norm in kept_norms:
            if kept_id == aid:
                is_subset = True
                break
            if name_norm in kept_norm:
                is_subset = True
                break
        if is_subset:
            continue

        seen_ids.add(aid)
        kept_norms.append((aid, name_norm))
        deduped.append((anime, field, name_raw))

    # 第四步：尝试从文本中提取评分
    results = []
    for anime, field, name_raw in deduped:
        rating = _extract_rating_near_name(text, name_raw)

        results.append({
            "id": int(anime["id"]),
            "name": anime.get("name") or "",
            "name_cn": anime.get("name_cn") or "",
            "display_name": display_name_cn(anime),
            "rating": round(float(anime.get("mean_score") or 0), 1),
            "image": anime.get("cover") or "",
            "year": anime.get("year") or anime.get("season_year") or 0,
            "format": anime.get("format") or "",
            "status": anime.get("status") or "",
            "match_name": name_raw,
            "match_field": field,
            "user_rating": rating,  # 从文本中提取的用户评分
        })

    return results


def _extract_rating_near_name(text: str, name: str) -> int | None:
    """尝试从文本中提取番剧名附近的评分。

    匹配模式：
      - "进击的巨人 9分"  → 9
      - "鬼灭之刃 - 8"    → 8
      - "咒术回战 (7.5)"  → 8 (取整)
      - "Re:0 10/10"      → 10
    """
    if not name:
        return None
    # 在文本中定位名称位置
    idx = text.find(name)
    if idx == -1:
        # 标点不同时记录规范化字符对应的原始位置，避免把规范化索引用在原文上。
        chars, positions = [], []
        for pos, char in enumerate(text):
            for normalized in _normalized_title(char):
                chars.append(normalized)
                positions.append(pos)
        name_norm = _normalized_title(name)
        normalized_idx = "".join(chars).find(name_norm)
        if normalized_idx == -1:
            return None
        end = positions[normalized_idx + len(name_norm) - 1] + 1
        text_after = text[end:end + 30]
    else:
        text_after = text[idx + len(name):idx + len(name) + 30]

    # 匹配评分模式
    patterns = [
        r'[\s\-—–]*(\d+)\s*分',      # "9分", "- 9分"
        r'[\s\-—–]*(\d+)\s*/\s*10',  # "8/10"
        r'[\s\-—–\(（]*(\d+(?:\.\d+)?)\s*[\)）]',  # "(7.5)"
        r'[\s\-—–:：]+(\d+)\s*$',    # " - 8" at end
    ]
    for pat in patterns:
        m = re.search(pat, text_after)
        if m:
            val = float(m.group(1))
            if 1 <= val <= 10:
                return int(round(val))
    return None


if __name__ == "__main__":
    fetch_all()
