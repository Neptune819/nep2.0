"""
app.py
=========
Flask 应用入口（v1.2）

新增端点：
  GET  /api/recommend/anime?with_sequels=1
  GET  /api/voice-actors?q=
  GET  /api/anime-by-va?name=
分页：所有 recommend 端点支持 offset/limit
trending：支持 year/season 服务端过滤
"""
import os
import io
import csv
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file

import data_loader
from recommender import AnimeRecommender
from quiz_system import QuizProcessor, SIMPLE_QUIZ, COMPLEX_QUIZ
from psych_profile import R18_TAGS

app = Flask(__name__)

# 全局单例 recommender（懒加载）
_recommender: AnimeRecommender | None = None
_quiz_processor = QuizProcessor()


def get_recommender() -> AnimeRecommender:
    global _recommender
    if _recommender is None:
        _recommender = AnimeRecommender()
    return _recommender


@app.route("/")
def welcome():
    return render_template("welcome.html")


@app.route("/app")
def index():
    return render_template("index.html")


@app.route("/mylist")
def mylist():
    return render_template("mylist.html")


@app.route("/quiz")
def quiz():
    return render_template("quiz.html")


@app.route("/api/search")
def api_search():
    """按名称搜索番剧（本地缓存）。"""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    cache = data_loader.load_cache()
    results = data_loader.search(q, cache, limit=15)
    return jsonify({"results": [{
        "id": a["id"],
        "name": a.get("name") or "",
        "name_cn": a.get("name_cn") or "",
        "name_en": a.get("name_en") or "",
        "name_jp": a.get("name_jp") or "",
        "rating": a.get("mean_score") or 0,
        "image": a.get("cover") or "",
        "year": a.get("year") or a.get("season_year"),
        "format": a.get("format") or "",
        "status": a.get("status") or "",
        "eps": a.get("eps") or 0,
        "tags": [t for t in (a.get("tags") or [])[:15] if t not in R18_TAGS][:8],
        "tags_cn": [t for t in (a.get("tags_cn") or [])[:15] if t not in R18_TAGS][:8],
        "popularity": a.get("popularity") or 0,
        "favourites": a.get("favourites") or 0,
    } for a in results]})


@app.route("/api/anime/<int:anime_id>")
def api_anime(anime_id: int):
    """获取单部番剧完整详情（用于详情页弹窗）。"""
    r = get_recommender()
    anime = r.get_anime(anime_id)
    if not anime:
        return jsonify({"error": "not found"}), 404
    tag_trans = data_loader._get_tag_trans()
    cn_map = data_loader._get_cn_mapping()
    mal_cn_map = data_loader._get_mal_cn_mapping()
    va_trans = data_loader._get_va_trans()

    name_cn = data_loader.display_name_cn(anime)
    # 原名（罗马字/英文）
    name_original = anime.get("name") or anime.get("name_en") or ""
    if name_original == name_cn:
        name_original = ""

    # tags 中英对照（过滤R18标签）
    tags_en = [t for t in (anime.get("tags") or [])[:30] if t not in R18_TAGS][:20]
    tags_display = [{"en": t, "cn": tag_trans.get(t, t)} for t in tags_en]

    # 声优（去重，取前 20）
    va_set = set()
    va_list = []
    for ch in (anime.get("characters") or []):
        for va_name in (ch.get("va") or []):
            if va_name and va_name not in va_set:
                va_set.add(va_name)
                cn_alias = va_trans.get(va_name, "")
                va_list.append({
                    "name": va_name,
                    "cn": cn_alias,
                    "character": ch.get("name", ""),
                    "role": ch.get("role", ""),
                })
    va_list = va_list[:20]

    # staff（角色名翻译）
    role_cn = getattr(data_loader, "_ROLE_CN", {})
    staff_list = []
    for s in (anime.get("staff") or [])[:8]:
        role_en = s.get("role", "")
        role_zh = role_cn.get(role_en, role_en)
        staff_list.append({"name": s.get("name", ""), "role": role_en, "role_cn": role_zh})

    # 类似番剧（quick similar，来自 recommender，已是格式化结果）
    try:
        similar = r.recommend_by_anime(anime_id, top_k=6)
    except Exception:
        similar = []

    # 续集（来自 find_sequels，是原始 dict，需格式化）
    try:
        raw_sequels = r.find_sequels(anime, limit=12)
    except Exception:
        raw_sequels = []

    return jsonify({
        "anime": {
            "id": int(anime["id"]),
            "name_cn": name_cn,
            "name_original": name_original,
            "name_jp": anime.get("name_jp") or "",
            "image": anime.get("cover") or "",
            "banner": anime.get("banner") or "",
            "summary": data_loader.get_summary_cn(anime),
            "rating": round(float(anime.get("mean_score") or 0), 1),
            "avg_rating": round(float(anime.get("rating") or 0), 1),
            "popularity": int(anime.get("popularity") or 0),
            "favourites": int(anime.get("favourites") or 0),
            "year": anime.get("year") or anime.get("season_year"),
            "season": anime.get("season") or "",
            "format": anime.get("format") or "",
            "eps": int(anime.get("eps") or 0),
            "duration": int(anime.get("duration") or 0),
            "status": anime.get("status") or "",
            "studios": (anime.get("studios") or [])[:5],
            "tags": tags_display,
            "staff": staff_list,
            "va": va_list,
        },
        "similar": similar,
        "sequels": [r._format_anime(a) for a in raw_sequels],
    })


@app.route("/api/tags")
def api_tags():
    """获取热门标签（已翻译成中文）。"""
    r = get_recommender()
    return jsonify({"tags": r.get_all_tags()})


def _parse_tuning_arg(raw):
    """解析 URL query 中的 tuning 参数（JSON 字符串）。"""
    if not raw:
        return None
    try:
        import json
        data = json.loads(raw)
        if isinstance(data, dict) and data:
            return data
    except Exception:
        pass
    return None


@app.route("/api/recommend/anime")
def api_recommend_anime():
    """模式 1：基于番剧相似度推荐。
    Query: id, limit, offset, with_sequels=1, style, user_tuning (JSON)
    """
    anime_id = request.args.get("id", type=int)
    if not anime_id:
        return jsonify({"error": "missing id"}), 400
    limit = request.args.get("limit", default=12, type=int)
    offset = request.args.get("offset", default=0, type=int)
    with_sequels = request.args.get("with_sequels", default="0") in ("1", "true", "yes")
    style = request.args.get("style", default="standard")
    user_tuning = _parse_tuning_arg(request.args.get("tuning"))
    try:
        r = get_recommender()
        if with_sequels:
            # 返回 {main, sequels} 结构
            bundle = r.recommend_by_anime_with_sequels(anime_id, top_k=200)
            main = bundle["main"][offset:offset + limit]
            return jsonify({
                "results": main,
                "sequels": bundle["sequels"],
                "has_more": len(bundle["main"]) > offset + limit,
                "total": len(bundle["main"]),
            })
        else:
            results = r.recommend_by_anime(anime_id, top_k=200,
                                           style=style, user_tuning=user_tuning)
            page = results[offset:offset + limit]
            return jsonify({
                "results": page,
                "has_more": len(results) > offset + limit,
                "total": len(results),
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend/history", methods=["POST"])
def api_recommend_history():
    """模式 2：基于看番历史的用户画像推荐。
    Body: {"history": [{"id": 123, "rating": 8}, ...], "limit": N, "offset": N, "style": "...", "tuning": {...}}
    """
    body = request.get_json(silent=True) or {}
    history = body.get("history", [])
    if not history:
        return jsonify({"error": "history is empty"}), 400
    limit = body.get("limit", 12)
    offset = body.get("offset", 0)
    style = body.get("style", "standard")
    user_tuning = body.get("tuning") or None
    try:
        r = get_recommender()
        results = r.recommend_by_history(history, top_k=200,
                                         style=style, user_tuning=user_tuning)
        page = results[offset:offset + limit]
        return jsonify({
            "results": page,
            "has_more": len(results) > offset + limit,
            "total": len(results),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend/tags", methods=["POST"])
def api_recommend_tags():
    """模式 3：基于标签的推荐。
    Body: {"tags": ["热血", "科幻"], "limit": N, "offset": N, "style": "...", "tuning": {...}}
    """
    body = request.get_json(silent=True) or {}
    tags = body.get("tags", [])
    if not tags:
        return jsonify({"error": "tags is empty"}), 400
    limit = body.get("limit", 12)
    offset = body.get("offset", 0)
    style = body.get("style", "standard")
    user_tuning = body.get("tuning") or None
    try:
        r = get_recommender()
        results = r.recommend_by_tags(tags, top_k=200,
                                      style=style, user_tuning=user_tuning)
        page = results[offset:offset + limit]
        return jsonify({
            "results": page,
            "has_more": len(results) > offset + limit,
            "total": len(results),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== 扩展端点 ==========

@app.route("/api/recommend/trending")
def api_recommend_trending():
    """本季热门：按 consensus 因子排序。
    Query: year, season, limit, offset  (year/season 不传则全库)
    """
    limit = request.args.get("limit", default=24, type=int)
    offset = request.args.get("offset", default=0, type=int)
    season = request.args.get("season", default=None)
    year = request.args.get("year", default=None, type=int)
    try:
        r = get_recommender()
        # 一次取大些用于分页
        all_results = r.recommend_trending(limit=200, season=season, year=year)
        page = all_results[offset:offset + limit]
        return jsonify({
            "results": page,
            "has_more": len(all_results) > offset + limit,
            "total": len(all_results),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend/discovery")
def api_recommend_discovery():
    """发现型推荐：冷门佳作、经典老番、口味盲区
    Query: id (种子番剧), limit
    """
    anime_id = request.args.get("id", type=int)
    limit = request.args.get("limit", default=30, type=int)
    try:
        r = get_recommender()
        result = r.recommend_discovery(anime_id=anime_id, limit=limit)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend/discovery/history", methods=["POST"])
def api_recommend_discovery_history():
    """发现型推荐（基于历史）
    Body: {"history": [{"id": 123, "rating": 8}, ...], "limit": N}
    """
    body = request.get_json(silent=True) or {}
    history = body.get("history", [])
    limit = body.get("limit", 30)
    try:
        r = get_recommender()
        result = r.recommend_discovery(history=history, limit=limit)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommend/discovery/tags", methods=["POST"])
def api_recommend_discovery_tags():
    """发现型推荐（基于标签）
    Body: {"tags": ["热血", "科幻"], "limit": N}
    """
    body = request.get_json(silent=True) or {}
    tags = body.get("tags", [])
    limit = body.get("limit", 30)
    try:
        r = get_recommender()
        result = r.recommend_discovery(tags=tags, limit=limit)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/weights", methods=["GET", "POST"])
def api_weights():
    """读取/保存多因子权重（运行时调参）。"""
    r = get_recommender()
    if request.method == "GET":
        return jsonify({"weights": r.weights})

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "weights must be a dict"}), 400
    try:
        r.set_weights(body)
        return jsonify({"weights": r.weights, "ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== 声优 tab v1.2 ==========

@app.route("/api/voice-actors")
def api_voice_actors():
    """搜声优。Query: q, limit"""
    q = request.args.get("q", default="", type=str)
    limit = request.args.get("limit", default=20, type=int)
    try:
        r = get_recommender()
        items = r.search_voice_actors(q, limit=limit)
        return jsonify({
            "results": [{"name": name, "score": float(sc)} for name, sc in items]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anime-by-va")
def api_anime_by_va():
    """声优 → 番剧列表。Query: name, limit"""
    name = request.args.get("name", default="", type=str)
    limit = request.args.get("limit", default=50, type=int)
    if not name:
        return jsonify({"error": "missing name"}), 400
    try:
        r = get_recommender()
        results = r.get_anime_by_va(name, limit=limit)
        return jsonify({"results": results, "va": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 常见番剧别名映射（用户常用名 → 搜索关键词）- 按长度降序排列，优先匹配长的
_ANIME_ALIASES = {
    "关于邻家的天使大人不知不觉把我变成废柴这档事": "お隣の天使様",
    "关于邻家的天使大人": "お隣の天使様",
    "我家女友可不只是可爱呢": "可愛いだけじゃない式守さん",
    "末日时在做什么？有没有空？可以拯救吗？": "終末なにしてますか？",
    "末日时在做什么": "終末なにしてますか？",
    "只要长得可爱，即使是变态你也喜欢吗？": "可愛い子ならいるよね",
    "只要长得可爱": "可愛い子ならいるよね",
    "一脸嫌弃表情给你看裤裆": "嫌な顔されながらおパンツ見せてもらいたい",
    "青梅竹马绝对不会败的恋爱喜剧": "幼なじみが絶対に負けないラブコメ",
    "这个美术社大有问题！": "この美術部には問題がある！",
    "这个美术社大有问题": "この美術部には問題がある！",
    "没有黄段子的无聊世界": "下ネタという概念が存在しない退屈な世界",
    "天才王子的赤字国家重生术": "天才王子の赤字国家再生術",
    "我的女友是个过度认真的处女bitch": "ギャルが度々俺を處女扱いする",
    "我的女友是个过度认真的处女": "ギャルが度々俺を處女扱いする",
    "野良与皇女与流浪猫之心": "のらと皇女と野良猫のハート",
    "千岁君在波子汽水瓶中": "千歳くんはラムネ瓶の中で",
    "声优广播的幕前幕后": "声優ラジオのウラオモテ",
    "Lord·埃尔梅罗二世事件簿": "ロード・エルメロイII世の事件簿",
    "君主·埃尔梅罗二世事件簿": "ロード・エルメロイII世の事件簿",
    "埃尔梅罗二世事件簿": "ロード・エルメロイII世の事件簿",
    "偶像活动10th STORY ～偶像活动on Parade!～": "アイカツ10th",
    "偶像活动10th STORY": "アイカツ10th",
    "偶像活动10th Story": "アイカツ10th",
    "偶像活动on Parade": "アイカツオンパレード",
    "偶像活动Friends": "アイカツフレンズ",
    "偶像活动Stars": "アイカツスターズ",
    "偶像活动Planet": "アイカツプラネット",
    "偶像活动10周年": "アイカツ10th",
    "偶像活动10th": "アイカツ10th",
    "偶像活动": "アイカツ",
    "LoveLive! SuperStar!!": "ラブライブ！スーパースター!!",
    "LoveLive! SuperStar": "ラブライブ！スーパースター!!",
    "异世界 Suicide Squad": "異世界スクワッド",
    "异世界suicide squad": "異世界スクワッド",
    "异世界自杀小队": "異世界スクワッド",
    "荒野的科特布奇飞行队": "荒野のコトブキ飛行隊",
    "上伊那牡丹，醉于百合之花": "上伊那ぼたん",
    "一叠间漫画咖啡厅": "一畳間まんが喫茶",
    "女高中生的虚度日常": "女子高生の無駄づかい",
    "前进吧！登山少女": "ヤマノススメ",
    "鹿乃子乃子虎视眈眈": "鹿の子ものは虎視眈々",
    "人马少女的烦恼": "セントールの悩み",
    "女孩的钓鱼慢活": "Slow Loop",
    "哭泣少女乐队": "ガールズバンドクライ",
    "龙的牙医": "龍の歯医者",
    "黄昏少女×失忆": "黄昏乙女×アムネジア",
    "香格里拉·开拓异境": "シャングリラ・フロンティア",
    "转生成蜘蛛又怎样": "蜘蛛ですが、なにか？",
    "不过是蜘蛛什么的": "蜘蛛ですが、なにか？",
    "铳皇无尽的法夫纳": "ユーレイデッド・キングダム",
    "野良与皇女": "のらと皇女",
    "刀剑乱舞 花丸": "刀剣乱舞-花丸-",
    "主播女孩重度依赖": "NEEDY GIRL OVERDOSE",
    "武装少女Machiavellism": "武装少女マキャヴェリズム",
    "3年Z组银八老师": "銀魂",
    "香格里拉边境": "シャングリラ・フロンティア",
    "碧蓝档案": "ブルーアーカイブ",
    "沉默魔女的秘密": "サイレント・ウィッチ",
    "正相反的你与我": "正反対な君と僕",
    "白沙的水族馆": "白い砂のアクアトープ",
    "命运/冠位指定": "Fate/Grand Order",
    "青春豚草少年": "青春ブタ野郎",
    "青春期猪头少年": "青春ブタ野郎",
    "青春猪头少年": "青春ブタ野郎",
    "青春豚野郎": "青春ブタ野郎",
    "我们无法一起学习": "ぼくたちは勉強ができない",
    "模拟后宫体验": "疑似ハーレム",
    "法纳纳": "ユーレイデッド・キングダム",
    "出包王女": "To LOVE-Ru",
    "猫娘乐园": "NEKOPARA",
    "命运石之门": "Steins;Gate",
    "鬼灭之刃": "Kimetsu no Yaiba",
    "间谍过家家": "SPY×FAMILY",
    "进击的巨人": "Shingeki no Kyojin",
    "无职转生": "Mushoku Tensei",
    "转生成蜘蛛": "蜘蛛ですが、なにか？",
    "食戟之灵": "食戟のソーマ",
    "食棘之灵": "食戟のソーマ",
    "东京食尸鬼": "東京喰種",
    "心理测量者": "Psycho-Pass",
    "游戏人生": "No Game No Life",
    "莉可丽丝": "Lycoris Recoil",
    "恶魔高校D×D": "High School DxD",
    "天才王子": "天才王子の赤字国家再生術",
    "Re:从零开始": "Re:Zero",
    "电锯人": "Chainsaw Man",
    "轻音少女": "K-ON!",
    "斩服少女": "Kill la Kill",
    "迷糊餐厅": "WORKING!!",
    "妄想学生会": "生徒会役員共",
    "夏日口袋": "Summer Pockets",
    "绯弹的亚莉亚": "緋弾のアリア",
    "人形电脑天使心": "Chobits",
    "利兹与青鸟": "リズと青い鳥",
    "柑橘味香气": "citrus",
    "徒然喜欢你": "徒然チルドレン",
    "惊爆游戏": "BTOOOM!",
    "谎言游戏": "Liar Liar",
    "不道德公会": "不徳のギルド",
    "回复术士": "回復術士のやり直し",
    "魔女与使魔": "魔女と使魔",
    "沉默魔女": "サイレント・ウィッチ",
    "秋日天空": "あかね色に染まる坂",
    "秋色之空": "あかね色に染まる坂",
    "雀魂": "麻雀",
    "吊带裤天使": "だいてん",
    "深夜冲击": "真夜中オチ",
    "婚姻剧毒": "婚姻毒素",
    "格林笔记": "グリムノーツ",
    "小城日常": "CITY",
    "登山少女": "ヤマノススメ",
    "上伊那牡丹": "上伊那ぼたん",
    "剑网3": "剣網3",
    "沈剑心": "沈剣心",
    "日本动画人": "日本アニメ（ーター）見本市",
    "sin 七大罪": "sin 七つの大罪",
    "MEGALOBOX": "メガロボクス",
    "Comic Girls": "コミックガールズ",
    "漫画女孩": "コミックガールズ",
    "OVERLORD": "オーバーロード",
    "不死者之王": "オーバーロード",
    "Engage Kiss": "エンゲージキス",
    "契约之吻": "エンゲージキス",
    "AYAKA": "AYAKA -あやか-",
    "绫岛奇谭": "AYAKA -あやか-",
    "BTOOOM!": "ブトゥーム",
    "黄昏少女": "黄昏乙女",
    "FGO": "Fate/Grand Order",
    "银魂": "銀魂",
    "新石纪": "Dr.STONE",
    "夏洛特": "Charlotte",
    "天降女子": "天から女の子",
    "宅饮": "宅飲み",
    "刀剑乱舞": "刀剣乱舞",
    "包揽": "To LOVE-Ru",
}

# 缓存相关
_cache_data = None
_cache_time = 0
_CACHE_TTL = 60  # 缓存60秒

def get_cached_cache():
    """带缓存的cache加载"""
    global _cache_data, _cache_time
    import time
    now = time.time()
    if _cache_data is None or (now - _cache_time) > _CACHE_TTL:
        _cache_data = data_loader.load_cache()
        _cache_time = now
    return _cache_data


@app.route("/api/parse-history", methods=["POST"])
def api_parse_history():
    """批量解析追番历史文本。
    Body: {"text": "番剧1\n番剧2\n..."}
    返回匹配到的番剧列表。
    """
    import re as re_module
    body = request.get_json(silent=True) or {}
    text = body.get("text", "")
    if not text:
        return jsonify({"error": "text is empty"}), 400

    cache = get_cached_cache()

    # 按行分割，过滤空行，去重
    lines = list(dict.fromkeys(line.strip() for line in text.split("\n") if line.strip()))

    # 去掉行首的序号、评分等
    cleaned_lines = []
    for line in lines:
        # 去掉序号：1. / 1、/ 1) / 1：/ • / -
        name = re_module.sub(r"^[\d]+[\.\、\)\：\:\s]+", "", line)
        name = re_module.sub(r"^[•\-\*·]\s*", "", name)
        # 去掉评分：8分 / ★8 / ⭐8 等
        name = re_module.sub(r"[\s]*[\★\⭐]*\d+(\.\d+)?[\s]*[分]?$", "", name)
        # 去掉状态标签
        name = re_module.sub(r"[\s]*[\[【\(](看过|看完|在看|想看|搁置|抛弃|听过|读过|玩过)[\]】\)]", "", name)
        # 去掉首尾标点和多余空格
        name = re_module.sub(r'^[\s\-—・·|｜]+', '', name)
        name = re_module.sub(r'[\s\-—・·|｜]+$', '', name)
        name = name.strip()
        if name and len(name) >= 2:
            cleaned_lines.append(name)

    if not cleaned_lines:
        return jsonify({"error": "无法解析出番剧名称", "lines": lines}), 400

    # 预处理别名表：按长度降序，用于快速匹配
    sorted_aliases = sorted(_ANIME_ALIASES.items(), key=lambda x: -len(x[0]))

    def extract_names(line):
        """从一行中提取所有可能的番剧名称"""
        names = []
        seen = set()
        
        def add_name(n):
            n = n.strip()
            if n and len(n) >= 2 and n.lower() not in seen:
                seen.add(n.lower())
                names.append(n)
        
        # 1. 提取括号内的内容（中文括号和英文括号）
        bracket_pattern = r'[\(（]([^)）]+)[\)）]'
        brackets = re_module.findall(bracket_pattern, line)
        
        # 去掉括号后的主名称
        main_name = re_module.sub(bracket_pattern, '', line).strip()
        # 清理多余符号
        main_name = re_module.sub(r'[/|｜~～]', ' ', main_name).strip()
        main_name = re_module.sub(r'\s+', ' ', main_name).strip()
        
        if main_name and len(main_name) >= 2:
            add_name(main_name)
        
        # 2. 处理括号内的名称（可能是别名）
        for b in brackets:
            # 跳过非番剧名的括号内容
            if re_module.match(r'^(系列|第|季|期|版|ova|movie|剧场版|含|等)', b, re_module.IGNORECASE):
                continue
            b_clean = re_module.sub(r'[/|｜~～]', ' ', b).strip()
            b_clean = re_module.sub(r'\s+', ' ', b_clean).strip()
            if b_clean and len(b_clean) >= 2:
                add_name(b_clean)
        
        # 3. 如果有 / 分隔，也分开尝试
        if '/' in line or '｜' in line:
            parts = re_module.split(r'[/|｜]', line)
            for p in parts:
                p_clean = re_module.sub(bracket_pattern, '', p).strip()
                p_clean = p_clean.strip(" \t\n\r\f\v-—・·~～")
                if p_clean and len(p_clean) >= 2:
                    add_name(p_clean)
        
        # 4. 检查别名映射 - 按长度降序匹配，避免短别名误匹配
        line_lower = line.lower()
        for alias, search_term in sorted_aliases:
            alias_lower = alias.lower()
            if alias_lower in line_lower:
                add_name(search_term)
                break  # 只取第一个匹配的别名
        
        return names

    def try_search(name, cache):
        """搜索番剧，返回最佳匹配"""
        results = data_loader.search(name, cache, limit=5)
        if not results:
            return None
        
        # 优先选择 name_cn 完全匹配的
        name_lower = name.lower()
        for r in results:
            cn = (r.get("name_cn") or "").lower()
            if name_lower == cn or name_lower in cn or cn in name_lower:
                return r
        
        # 其次检查 name_en
        for r in results:
            en = (r.get("name_en") or "").lower()
            if name_lower == en or name_lower in en:
                return r
        
        return results[0]

    # 搜索匹配
    matched = []
    unmatched = []
    matched_ids = set()
    
    for line in cleaned_lines:
        names_to_try = extract_names(line)
        found = False
        
        for name in names_to_try:
            result = try_search(name, cache)
            if result and result["id"] not in matched_ids:
                matched_ids.add(result["id"])
                matched.append({
                    "id": result["id"],
                    "name": result.get("name") or "",
                    "name_cn": result.get("name_cn") or "",
                    "name_en": result.get("name_en") or "",
                    "image": result.get("cover") or "",
                    "rating": result.get("mean_score") or 0,
                    "query": line,  # 原始查询
                })
                found = True
                break
        
        if not found:
            unmatched.append(line)

    return jsonify({
        "matched": matched,
        "unmatched": unmatched,
        "total_input": len(cleaned_lines),
        "total_matched": len(matched),
    })


@app.route("/api/parse-file", methods=["POST"])
def api_parse_file():
    """解析上传的文件（Word/PDF/文本），提取文字后解析番剧。
    Body: multipart/form-data with 'file' field
    """
    import os
    
    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件"}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400
    
    # 获取文件扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    
    try:
        text = ""
        
        if ext in ['.docx', '.doc']:
            # Word文档
            text = extract_text_from_docx(file)
        elif ext in ['.pdf']:
            # PDF文档
            text = extract_text_from_pdf(file)
        elif ext in ['.txt', '.md', '.csv']:
            # 纯文本
            text = file.read().decode('utf-8', errors='ignore')
        else:
            return jsonify({"error": f"不支持的文件格式: {ext}，支持 DOCX/PDF/TXT"}), 400
        
        if not text or len(text.strip()) < 2:
            return jsonify({"error": "无法从文件中提取文字"}), 400
        
        # 调用parse-history进行解析
        return api_parse_history_internal(text)
        
    except Exception as e:
        return jsonify({"error": f"文件解析失败: {str(e)}"}), 500


def api_parse_history_internal(text):
    """内部函数，用于文件解析后调用"""
    import re as re_module
    
    cache = get_cached_cache()
    
    # 按行分割，过滤空行，去重
    lines = list(dict.fromkeys(line.strip() for line in text.split("\n") if line.strip()))
    
    # 去掉行首的序号、评分等
    cleaned_lines = []
    for line in lines:
        name = re_module.sub(r"^[\d]+[\.\、\)\：\:\s]+", "", line)
        name = re_module.sub(r"^[•\-\*·]\s*", "", name)
        name = re_module.sub(r"[\s]*[\★\⭐]*\d+(\.\d+)?[\s]*[分]?$", "", name)
        name = re_module.sub(r"[\s]*[\[【\(](看过|看完|在看|想看|搁置|抛弃|听过|读过|玩过)[\]】\)]", "", name)
        name = re_module.sub(r'^[\s\-—・·|｜]+', '', name)
        name = re_module.sub(r'[\s\-—・·|｜]+$', '', name)
        name = name.strip()
        if name and len(name) >= 2:
            cleaned_lines.append(name)
    
    if not cleaned_lines:
        return jsonify({"error": "无法解析出番剧名称", "extracted_text": text[:500]})
    
    sorted_aliases = sorted(_ANIME_ALIASES.items(), key=lambda x: -len(x[0]))
    
    def extract_names(line):
        names = []
        seen = set()
        
        def add_name(n):
            n = n.strip()
            if n and len(n) >= 2 and n.lower() not in seen:
                seen.add(n.lower())
                names.append(n)
        
        bracket_pattern = r'[\(（]([^)）]+)[\)）]'
        brackets = re_module.findall(bracket_pattern, line)
        
        main_name = re_module.sub(bracket_pattern, '', line).strip()
        main_name = re_module.sub(r'[/|｜~～]', ' ', main_name).strip()
        main_name = re_module.sub(r'\s+', ' ', main_name).strip()
        
        if main_name and len(main_name) >= 2:
            add_name(main_name)
        
        for b in brackets:
            if re_module.match(r'^(系列|第|季|期|版|ova|movie|剧场版|含|等)', b, re_module.IGNORECASE):
                continue
            b_clean = re_module.sub(r'[/|｜~～]', ' ', b).strip()
            b_clean = re_module.sub(r'\s+', ' ', b_clean).strip()
            if b_clean and len(b_clean) >= 2:
                add_name(b_clean)
        
        if '/' in line or '｜' in line:
            parts = re_module.split(r'[/|｜]', line)
            for p in parts:
                p_clean = re_module.sub(bracket_pattern, '', p).strip()
                p_clean = p_clean.strip(" \t\n\r\f\v-—・·~～")
                if p_clean and len(p_clean) >= 2:
                    add_name(p_clean)
        
        line_lower = line.lower()
        for alias, search_term in sorted_aliases:
            alias_lower = alias.lower()
            if alias_lower in line_lower:
                add_name(search_term)
                break
        
        return names
    
    def try_search(name, cache):
        results = data_loader.search(name, cache, limit=5)
        if not results:
            return None
        
        name_lower = name.lower()
        for r in results:
            cn = (r.get("name_cn") or "").lower()
            if name_lower == cn or name_lower in cn or cn in name_lower:
                return r
        
        for r in results:
            en = (r.get("name_en") or "").lower()
            if name_lower == en or name_lower in en:
                return r
        
        return results[0]
    
    matched = []
    unmatched = []
    matched_ids = set()
    
    for line in cleaned_lines:
        names_to_try = extract_names(line)
        found = False
        
        for name in names_to_try:
            result = try_search(name, cache)
            if result and result["id"] not in matched_ids:
                matched_ids.add(result["id"])
                matched.append({
                    "id": result["id"],
                    "name": result.get("name") or "",
                    "name_cn": result.get("name_cn") or "",
                    "name_en": result.get("name_en") or "",
                    "image": result.get("cover") or "",
                    "rating": result.get("mean_score") or 0,
                    "query": line,
                })
                found = True
                break
        
        if not found:
            unmatched.append(line)
    
    return jsonify({
        "matched": matched,
        "unmatched": unmatched,
        "total_input": len(cleaned_lines),
        "total_matched": len(matched),
    })


def extract_text_from_docx(file):
    """从Word文档中提取文字"""
    try:
        from docx import Document
        import io
        
        # 读取docx文件
        doc = Document(io.BytesIO(file.read()))
        
        # 提取所有段落文字
        text_lines = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_lines.append(para.text.strip())
        
        # 提取表格中的文字
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_lines.append(cell.text.strip())
        
        return '\n'.join(text_lines)
    except ImportError:
        raise Exception("python-docx库未安装，请运行: pip install python-docx")


def extract_text_from_pdf(file):
    """从PDF文档中提取文字"""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise Exception("PyPDF2 / pypdf 库未安装，请运行: pip install pypdf")
    import io

    reader = PdfReader(io.BytesIO(file.read()))

    text_lines = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_lines.append(text)

    return '\n'.join(text_lines)


# ========== BGM 音乐功能 ==========
BGM_DIR = Path(__file__).parent / "static" / "bgm"

@app.route("/api/bgm/list")
def api_bgm_list():
    """获取BGM列表"""
    if not BGM_DIR.exists():
        BGM_DIR.mkdir(parents=True, exist_ok=True)
        return jsonify({"tracks": []})
    
    tracks = []
    for f in sorted(BGM_DIR.iterdir()):
        if f.suffix.lower() in ['.mp3', '.wav', '.ogg', '.m4a']:
            # 从文件名提取显示名称（去掉扩展名）
            name = f.stem
            # 尝试解码 URL 编码的中文
            try:
                from urllib.parse import unquote
                name = unquote(name)
            except:
                pass
            tracks.append({
                "name": name,
                "file": f.name,
                "url": f"/static/bgm/{f.name}",
                "size": f.stat().st_size,
            })
    
    return jsonify({"tracks": tracks})


@app.route("/api/bgm/upload", methods=["POST"])
def api_bgm_upload():
    """上传BGM文件"""
    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件"}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.mp3', '.wav', '.ogg', '.m4a']:
        return jsonify({"error": "不支持的格式，仅支持 MP3/WAV/OGG/M4A"}), 400
    
    # 确保目录存在
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    filename = file.filename
    filepath = BGM_DIR / filename
    file.save(str(filepath))
    
    return jsonify({
        "ok": True,
        "name": filepath.stem,
        "file": filename,
        "url": f"/static/bgm/{filename}",
    })


@app.route("/api/bgm/delete", methods=["POST"])
def api_bgm_delete():
    """删除BGM文件"""
    body = request.get_json(silent=True) or {}
    filename = body.get("file", "")
    
    if not filename:
        return jsonify({"error": "缺少文件名"}), 400
    
    # 安全检查：只允许删除bgm目录下的文件
    filepath = BGM_DIR / filename
    if not filepath.exists():
        return jsonify({"error": "文件不存在"}), 404
    
    # 确保文件在bgm目录下
    if not str(filepath.resolve()).startswith(str(BGM_DIR.resolve())):
        return jsonify({"error": "无效的文件路径"}), 400

    filepath.unlink()
    return jsonify({"ok": True})


# ========== 背景图片管理 ==========
BACKGROUND_DIR = Path(__file__).parent / "static" / "backgrounds"
BACKGROUND_STATE_FILE = Path(__file__).parent / "data" / "background_state.json"
ALLOWED_BG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _load_bg_state() -> dict:
    """读取当前选中的背景（{selected: filename|null}）"""
    try:
        if BACKGROUND_STATE_FILE.exists():
            import json
            return json.loads(BACKGROUND_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"selected": None}


def _save_bg_state(state: dict):
    """保存背景选择到磁盘"""
    import json
    BACKGROUND_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKGROUND_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@app.route("/api/background/list")
def api_background_list():
    """列出所有可用背景 + 当前选中的"""
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(BACKGROUND_DIR.iterdir()):
        if f.suffix.lower() in ALLOWED_BG_EXT and f.is_file():
            items.append({
                "name": f.stem,
                "file": f.name,
                "url": f"/static/backgrounds/{f.name}",
                "size": f.stat().st_size,
            })
    state = _load_bg_state()
    return jsonify({"backgrounds": items, "selected": state.get("selected")})


@app.route("/api/background/upload", methods=["POST"])
def api_background_upload():
    """上传背景图片"""
    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"error": "文件名为空"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_BG_EXT:
        return jsonify({"error": f"不支持的格式，仅支持 {', '.join(sorted(ALLOWED_BG_EXT))}"}), 400

    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    # 防止文件名冲突：自动加序号
    target = BACKGROUND_DIR / f.filename
    if target.exists():
        stem, suf = os.path.splitext(f.filename)
        i = 2
        while True:
            candidate = BACKGROUND_DIR / f"{stem}_{i}{suf}"
            if not candidate.exists():
                target = candidate
                break
            i += 1
    f.save(str(target))
    return jsonify({"ok": True, "file": target.name, "url": f"/static/backgrounds/{target.name}"})


@app.route("/api/background/delete", methods=["POST"])
def api_background_delete():
    """删除背景图片"""
    body = request.get_json(silent=True) or {}
    filename = body.get("file", "")
    if not filename:
        return jsonify({"error": "缺少文件名"}), 400
    filepath = BACKGROUND_DIR / filename
    if not filepath.exists():
        return jsonify({"error": "文件不存在"}), 404
    if not str(filepath.resolve()).startswith(str(BACKGROUND_DIR.resolve())):
        return jsonify({"error": "无效的文件路径"}), 400
    # 如果删的是当前选中的，清除选择
    state = _load_bg_state()
    if state.get("selected") == filename:
        state["selected"] = None
        _save_bg_state(state)
    filepath.unlink()
    return jsonify({"ok": True})


@app.route("/api/background/select", methods=["POST"])
def api_background_select():
    """选择一张背景作为当前显示。
    Body: {"file": "xxx.jpg"} 或 {"file": null} 取消选择（用默认渐变）
    """
    body = request.get_json(silent=True) or {}
    filename = body.get("file")
    state = _load_bg_state()

    if filename is None or filename == "":
        state["selected"] = None
    else:
        filepath = BACKGROUND_DIR / filename
        if not filepath.exists():
            return jsonify({"error": "文件不存在"}), 404
        if not str(filepath.resolve()).startswith(str(BACKGROUND_DIR.resolve())):
            return jsonify({"error": "无效的文件路径"}), 400
        state["selected"] = filename

    _save_bg_state(state)
    return jsonify({"ok": True, "selected": state["selected"]})


@app.route("/api/background/current")
def api_background_current():
    """获取当前选中背景的 URL（前端初次加载时用）"""
    state = _load_bg_state()
    sel = state.get("selected")
    if not sel:
        return jsonify({"url": None})
    filepath = BACKGROUND_DIR / sel
    if not filepath.exists():
        return jsonify({"url": None})
    return jsonify({"url": f"/static/backgrounds/{sel}"})


@app.route("/api/recommend/by-quiz", methods=["POST"])
def api_recommend_by_quiz():
    """根据问答结果推荐番剧。
    Body: {"tags": ["tag1", "tag2"], "factors": {"rating": 0.8, ...}}
    """
    body = request.get_json(silent=True) or {}
    tags = body.get("tags", [])
    factors = body.get("factors", {})
    
    if not tags:
        return jsonify({"error": "缺少标签"}), 400
    
    try:
        r = get_recommender()
        cache = data_loader.load_cache()
        
        # 使用标签推荐，但获取更多候选
        tag_trans = data_loader._get_tag_trans()
        cn_to_en = {cn: en for en, cn in tag_trans.items()}
        
        # 将标签转为英文
        en_tags = []
        for t in tags:
            en = cn_to_en.get(t, t)
            if en in r._tag_to_idx:
                en_tags.append(en)
        
        if not en_tags:
            en_tags = tags
        
        # 使用标签推荐获取候选
        candidates = r.recommend_by_tags(tags, top_k=100)
        
        # 过滤和排序：优先推荐质量好、人气高的作品
        def score_anime(a):
            s = a.get("score", 0)
            rating = a.get("rating", 0)
            fav = a.get("favourites", 0)
            pop = a.get("popularity", 0)
            
            # 基础分 = 推荐分数
            base_score = s
            
            # 质量加成：评分 >= 7.5 的作品加分
            quality_bonus = 0
            if rating >= 8.0:
                quality_bonus = 0.3
            elif rating >= 7.5:
                quality_bonus = 0.2
            elif rating >= 7.0:
                quality_bonus = 0.1
            
            # 人气加成：收藏数 > 5000 的作品加分
            pop_bonus = 0
            if fav >= 20000:
                pop_bonus = 0.25
            elif fav >= 10000:
                pop_bonus = 0.2
            elif fav >= 5000:
                pop_bonus = 0.15
            elif fav >= 1000:
                pop_bonus = 0.1
            
            # 惩罚：太冷门的作品扣分
            penalty = 0
            if fav < 100:
                penalty = -0.3
            elif fav < 500:
                penalty = -0.15
            elif fav < 1000:
                penalty = -0.05
            
            # 评分惩罚：低分作品扣分
            if rating < 6.0:
                penalty -= 0.2
            elif rating < 6.5:
                penalty -= 0.1
            
            return base_score + quality_bonus + pop_bonus + penalty
        
        # 计算综合分数并排序
        for a in candidates:
            a["_final_score"] = score_anime(a)
        
        candidates.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
        
        # 取前12个
        results = candidates[:12]
        
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== 问答系统 API ==========

@app.route("/api/quiz/questions")
def api_quiz_questions():
    """获取问答题目
    Query: mode=simple/complex
    """
    mode = request.args.get("mode", default="simple")
    if mode == "complex":
        return jsonify({
            "title": COMPLEX_QUIZ["title"],
            "description": COMPLEX_QUIZ["description"],
            "questions": COMPLEX_QUIZ["questions"],
            "total": len(COMPLEX_QUIZ["questions"]),
        })
    else:
        return jsonify({
            "title": SIMPLE_QUIZ["title"],
            "description": SIMPLE_QUIZ["description"],
            "questions": SIMPLE_QUIZ["questions"],
            "total": len(SIMPLE_QUIZ["questions"]),
        })


@app.route("/api/quiz/submit", methods=["POST"])
def api_quiz_submit():
    """提交问答结果，生成心理画像
    Body: {
        "mode": "simple" 或 "complex",
        "style": "explore", "standard", "conservative",
        "answers": [{"question_id": 1, "answer": 0}, ...]
    }
    """
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "simple")
    style = body.get("style", "standard")
    answers = body.get("answers", [])

    if not answers:
        return jsonify({"error": "缺少答案"}), 400

    try:
        # 处理问答结果
        result = _quiz_processor.process_quiz(answers, mode)

        # 基于心理画像推荐番剧
        r = get_recommender()
        profile = result["profile"]
        tags = result["tags"]

        # 使用发现型推荐引擎
        discovery_result = r.recommend_discovery(tags=tags, limit=50, style=style)

        return jsonify({
            "profile": result["profile_dict"],
            "reasoning": result["reasoning"],
            "tags": tags,
            "recommendations": {
                "underrated": discovery_result["underrated"],
                "vintage": discovery_result["vintage"],
                "blind_spot": discovery_result["blind_spot"],
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/quiz/recommend", methods=["POST"])
def api_quiz_recommend():
    """基于心理画像推荐番剧
    Body: {
        "profile": {...},  # 心理画像
        "style": "explore", "standard", "conservative",
        "limit": 50,
        "exclude_ids": [...]  # 已推荐过的番剧ID
    }
    """
    body = request.get_json(silent=True) or {}
    profile_dict = body.get("profile", {})
    style = body.get("style", "standard")
    limit = body.get("limit", 50)
    exclude_ids = set(body.get("exclude_ids", []))

    try:
        # 从字典重建心理画像
        from psych_profile import ComprehensivePsychProfile
        profile = ComprehensivePsychProfile()

        # 手动设置属性
        if "personality" in profile_dict:
            p = profile_dict["personality"]
            if "big_five" in p:
                profile.big_five = p["big_five"]
            if "mbti" in p:
                profile.mbti = p["mbti"]
            if "enneagram" in p:
                profile.enneagram = p["enneagram"]
            if "cognitive_functions" in p:
                profile.cognitive_functions = p["cognitive_functions"]

        if "needs" in profile_dict:
            n = profile_dict["needs"]
            if "sdt_needs" in n:
                profile.sdt_needs = n["sdt_needs"]
            if "regulatory_focus" in n:
                profile.regulatory_focus = n["regulatory_focus"]
            if "achievement_type" in n:
                profile.achievement_type = n["achievement_type"]

        if "emotion" in profile_dict:
            e = profile_dict["emotion"]
            if "attachment" in e:
                profile.attachment = e["attachment"]
            if "defense_mechanisms" in e:
                profile.defense_mechanisms = e["defense_mechanisms"]

        if "narrative" in profile_dict:
            n = profile_dict["narrative"]
            if "archetype" in n:
                profile.archetype = n["archetype"]
            if "narrative_type" in n:
                profile.narrative_type = n["narrative_type"]
            if "worldview" in n:
                profile.worldview = n["worldview"]

        # 生成推荐标签
        tags = _quiz_processor._generate_recommendation_tags(profile)

        # 使用发现型推荐
        r = get_recommender()
        result = r.recommend_discovery(tags=tags, limit=limit, exclude_ids=exclude_ids, style=style)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily-recommend", methods=["POST"])
def api_daily_recommend():
    """每日推荐 v3.0：每天推荐100部，一周内不重复

    流水线：模式参数 → 心理模型(从 quiz) → 历史因素(可选) → 调参后处理

    Body: {
        "profile": {...},          # 心理画像（来自 quiz）
        "style": "explore"/"standard"/"conservative",
        "history": [{"id": 123, "rating": 8}, ...],  # 可选，从 localStorage
        "tuning": {factor: gain, ...}  # 可选，用户调参
    }
    """
    body = request.get_json(silent=True) or {}
    profile_dict = body.get("profile", {})
    style = body.get("style", "standard")
    history = body.get("history") or None
    user_tuning = body.get("tuning") or None

    try:
        from datetime import datetime, timedelta
        import hashlib

        # 重建心理画像
        from psych_profile import ComprehensivePsychProfile
        profile = ComprehensivePsychProfile()

        # 如果有profile数据，设置属性
        if profile_dict:
            if "personality" in profile_dict:
                p = profile_dict["personality"]
                if "big_five" in p:
                    profile.big_five = p["big_five"]
                if "mbti" in p:
                    profile.mbti = p["mbti"]
                if "enneagram" in p:
                    profile.enneagram = p["enneagram"]
                if "cognitive_functions" in p:
                    profile.cognitive_functions = p["cognitive_functions"]

            if "needs" in profile_dict:
                n = profile_dict["needs"]
                if "sdt_needs" in n:
                    profile.sdt_needs = n["sdt_needs"]
                if "regulatory_focus" in n:
                    profile.regulatory_focus = n["regulatory_focus"]

            if "emotion" in profile_dict:
                e = profile_dict["emotion"]
                if "attachment" in e:
                    profile.attachment = e["attachment"]
                if "defense_mechanisms" in e:
                    profile.defense_mechanisms = e["defense_mechanisms"]

            if "narrative" in profile_dict:
                n = profile_dict["narrative"]
                if "archetype" in n:
                    profile.archetype = n["archetype"]
                if "narrative_type" in n:
                    profile.narrative_type = n["narrative_type"]
                if "worldview" in n:
                    profile.worldview = n["worldview"]

        # 生成推荐标签
        print(f"[DEBUG] profile type: {type(profile)}")
        print(f"[DEBUG] profile.archetype: {repr(profile.archetype)}")
        tags = _quiz_processor._generate_recommendation_tags(profile)
        print(f"[DEBUG] tags: {tags}")

        # 使用日期作为随机种子的一部分，确保同一天推荐相同
        today = datetime.now().strftime("%Y-%m-%d")
        seed_str = f"{today}-{style}-{','.join(sorted(tags[:5]))}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)

        # 获取过去7天的日期，用于排除已推荐的番剧
        exclude_dates = []
        for i in range(7):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            exclude_dates.append(d)

        # 收集过去7天推荐过的番剧ID（使用内存缓存）
        if not hasattr(app, '_daily_recommend_cache'):
            app._daily_recommend_cache = {}

        exclude_ids = set()
        for d in exclude_dates:
            cache_key = f"{d}-{style}"
            if cache_key in app._daily_recommend_cache:
                exclude_ids.update(app._daily_recommend_cache[cache_key])

        # 使用发现型推荐（v3.0：可选传入 history 用于更精准的 psych profile）
        r = get_recommender()
        result = r.recommend_discovery(
            tags=tags,
            history=history,  # v3.0: 可选，融合用户历史
            limit=100,
            exclude_ids=exclude_ids,
            style=style,
            seed=seed
        )

        # v3.0 后处理：调参（仅当用户调过）
        if user_tuning:
            import multi_factor
            for category in ('underrated', 'vintage', 'blind_spot'):
                for item in result.get(category, []):
                    # 调参乘数（仅作用于 result.score）
                    if 'score' in item:
                        orig = item['score']
                        # 这里只能粗略应用：调用 multi_factor 的 tuning_multiplier
                        # 由于 discovery 结果没有 factor breakdown，只能做有限调整
                        # 实际生产中，recommend_discovery 内部已经按 style 处理了
                        # user_tuning 主要影响 history/daily re_rank 流程
                        pass

        # 缓存今天的推荐结果
        today_key = f"{today}-{style}"
        recommended_ids = set()
        for category in ['underrated', 'vintage', 'blind_spot']:
            for item in result.get(category, []):
                recommended_ids.add(item['id'])
        app._daily_recommend_cache[today_key] = recommended_ids

        # 清理超过7天的缓存
        keys_to_remove = []
        for key in app._daily_recommend_cache:
            date_str = key.split('-')[0:3]
            try:
                cache_date = datetime.strptime('-'.join(date_str), "%Y-%m-%d")
                if (datetime.now() - cache_date).days > 7:
                    keys_to_remove.append(key)
            except:
                pass
        for key in keys_to_remove:
            del app._daily_recommend_cache[key]

        return jsonify({
            "date": today,
            "style": style,
            "total": sum(len(v) for v in result.values() if isinstance(v, list)),
            "recommendations": {
                "underrated": result.get("underrated", []),
                "vintage": result.get("vintage", []),
                "blind_spot": result.get("blind_spot", []),
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export", methods=["POST"])
def api_export():
    """导出番剧列表为多种格式。
    Body: {"list": [...], "format": "docx"|"txt"|"csv"|"image"}
    """
    from datetime import datetime
    body = request.get_json(force=True)
    anime_list = body.get("list", [])
    fmt = body.get("format", "txt")

    if not anime_list:
        return jsonify({"error": "列表为空"}), 400

    timestamp = datetime.now().strftime("%Y%m%d")

    if fmt == "txt":
        lines = []
        for i, a in enumerate(anime_list, 1):
            name = a.get("name_cn") or a.get("name") or ""
            rating = a.get("rating") or 0
            r = f" {rating}分" if rating > 0 else ""
            lines.append(f"{i}. {name}{r}")
        content = "\n".join(lines)
        buf = io.BytesIO(content.encode("utf-8"))
        buf.name = f"anime_list_{timestamp}.txt"
        return send_file(buf, mimetype="text/plain",
                         as_attachment=True,
                         download_name=f"番剧列表_{timestamp}.txt")

    elif fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["序号", "名称", "原名", "评分", "年份", "格式", "标签"])
        for i, a in enumerate(anime_list, 1):
            writer.writerow([
                i,
                a.get("name_cn") or a.get("name") or "",
                a.get("name_en") or a.get("name") or "",
                a.get("rating") or "",
                a.get("year") or "",
                a.get("format") or "",
                ", ".join((a.get("tags_cn") or a.get("tags") or [])[:5]),
            ])
        content = buf.getvalue()
        buf = io.BytesIO(content.encode("utf-8-sig"))
        buf.name = f"anime_list_{timestamp}.csv"
        return send_file(buf, mimetype="text/csv",
                         as_attachment=True,
                         download_name=f"番剧列表_{timestamp}.csv")

    elif fmt == "docx":
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(10.5)
        style.element.rPr.rFonts.set(
            __import__("docx.oxml.ns", fromlist=["qn"]).qn("w:eastAsia"),
            "Microsoft YaHei")

        title = doc.add_heading("我的番剧列表", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}  |  共 {len(anime_list)} 部")
        doc.add_paragraph()

        # 表格
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for j, t in enumerate(["序号", "名称", "评分", "年份", "标签"]):
            hdr[j].text = t
            for p in hdr[j].paragraphs:
                for r in p.runs:
                    r.font.bold = True
                    r.font.size = Pt(9.5)

        for i, a in enumerate(anime_list, 1):
            row = table.add_row().cells
            row[0].text = str(i)
            row[1].text = a.get("name_cn") or a.get("name") or ""
            rating = a.get("rating") or 0
            row[2].text = f"{rating}分" if rating > 0 else "未打分"
            row[3].text = str(a.get("year") or "")
            row[4].text = ", ".join((a.get("tags_cn") or a.get("tags") or [])[:3])
            for cell in row:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9)

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        buf.name = f"anime_list_{timestamp}.docx"
        return send_file(buf,
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                         as_attachment=True,
                         download_name=f"番剧列表_{timestamp}.docx")

    elif fmt == "image":
        from PIL import Image, ImageDraw, ImageFont
        import requests as req

        # 下载封面并拼接
        covers = []
        for a in anime_list[:100]:  # 最多100部
            url = a.get("image") or a.get("cover") or ""
            if not url:
                continue
            try:
                r = req.get(url, timeout=5)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content)).resize((150, 210))
                    covers.append(img)
            except Exception:
                pass

        if not covers:
            return jsonify({"error": "无法获取封面图片"}), 400

        # 计算网格
        cols = min(8, len(covers))
        rows = (len(covers) + cols - 1) // cols
        w, h = 150, 210
        padding = 10
        header_h = 80
        poster = Image.new("RGB",
            (cols * (w + padding) + padding, rows * (h + padding) + padding + header_h),
            (11, 15, 26))

        # 标题
        draw = ImageDraw.Draw(poster)
        try:
            font = ImageFont.truetype("msyh.ttc", 24)
            font_sm = ImageFont.truetype("msyh.ttc", 14)
        except Exception:
            font = ImageFont.load_default()
            font_sm = font
        draw.text((padding, 15), "我的番剧列表", fill=(232, 236, 244), font=font)
        draw.text((padding, 50), f"共 {len(anime_list)} 部  |  {datetime.now().strftime('%Y-%m-%d')}",
                  fill=(136, 146, 168), font=font_sm)

        # 拼接封面
        for i, img in enumerate(covers):
            r = i // cols
            c = i % cols
            x = padding + c * (w + padding)
            y = header_h + padding + r * (h + padding)
            poster.paste(img, (x, y))

        buf = io.BytesIO()
        poster.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        buf.name = f"anime_poster_{timestamp}.jpg"
        return send_file(buf, mimetype="image/jpeg",
                         as_attachment=True,
                         download_name=f"番剧海报_{timestamp}.jpg")

    return jsonify({"error": f"不支持的格式: {fmt}"}), 400


if __name__ == "__main__":
    # debug=True 开发时用，发布时关掉
    app.run(debug=True, port=5000, host="127.0.0.1", use_reloader=False)
