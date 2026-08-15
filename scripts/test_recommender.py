"""
test_recommender.py
================
推荐器回归测试 + 边界检查。

跑法：
    cd "C:/Users/lmhNe/Desktop/新建文件夹 (5)"
    python scripts/test_recommender.py

它做什么：
    1. 三种模式各跑一个典型用例
    2. 边界（无 tag / 无 year / 不存在 id）
    3. 用 explain() 展示一条结果的 13 因子明细
"""
import sys
import os
# 允许从项目根目录直接 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recommender import AnimeRecommender
import multi_factor


def header(s):
    print()
    print("=" * 70)
    print(f"  {s}")
    print("=" * 70)


def show(results, n=None):
    """打印前 n 条结果。"""
    for x in results[:n]:
        name = x["name_cn"] or x["name"]
        print(f"  [{x['id']:5d}] {name:35s} "
              f"score={x['score']:.3f}  rating={x['rating']:.1f}  "
              f"year={x.get('year') or '-'}  fmt={x.get('format') or '-'}")
        print(f"           reasons: {x['reasons']}")


def main():
    header("正在初始化推荐器（建索引约 1-2 秒）...")
    r = AnimeRecommender()

    # ========== 模式 1: 按番剧 ==========
    header("测试 1.1: 模式 1  —  种子 = 星际牛仔 (id=1)")
    show(r.recommend_by_anime(1, top_k=8))

    header("测试 1.2: 模式 1  —  种子 = 进击的巨人 (id=16498)")
    show(r.recommend_by_anime(16498, top_k=8))

    header("测试 1.3: 模式 1  —  种子 = 化物语 (id=10162)")
    show(r.recommend_by_anime(10162, top_k=8))

    # ========== 模式 2: 按历史 ==========
    header("测试 2.1: 模式 2  —  模拟用户 = 「钢炼FA 9分, 银魂 8分, 钢炼 7分」")
    history = [
        {"id": 5114, "rating": 9},   # Fullmetal Alchemist: Brotherhood
        {"id": 165,  "rating": 8},   # Gintama (TV)
        {"id": 102,  "rating": 7},   # Fullmetal Alchemist
    ]
    show(r.recommend_by_history(history, top_k=8))

    header("测试 2.2: 模式 2  —  模拟用户 = 「全看治愈系+京阿尼+2010s」")
    history_healing = [
        {"id": 11759, "rating": 9},
        {"id": 13659, "rating": 9},
        {"id": 10379, "rating": 8},
    ]
    show(r.recommend_by_history(history_healing, top_k=8))

    # ========== 模式 3: 按标签 ==========
    # 注：数据里没有 Psychological/Thriller/Adventure/Mystery/Action/Drama 这些常见 tag
    # 改用真实存在的 tag 测试
    header("测试 3.1: 模式 3  —  标签 = [Demons, Super Power, Shounen]")
    show(r.recommend_by_tags(["Demons", "Super Power", "Shounen"], top_k=8))

    header("测试 3.2: 模式 3  —  标签 = [Isekai, Magic]")
    show(r.recommend_by_tags(["Isekai", "Magic"], top_k=8))

    header("测试 3.3: 模式 3  —  标签 = [Mecha, Military, Space]")
    show(r.recommend_by_tags(["Mecha", "Military", "Space"], top_k=8))

    # ========== 边界 ==========
    header("边界 1: 不存在的 id")
    res = r.recommend_by_anime(99999999, top_k=5)
    print(f"  返回 {len(res)} 条（应为 0）")
    assert len(res) == 0

    header("边界 2: 空历史")
    res = r.recommend_by_history([], top_k=5)
    print(f"  返回 {len(res)} 条（应为 0）")
    assert len(res) == 0

    header("边界 3: 不认识的标签")
    res = r.recommend_by_tags(["ThisDoesNotExist12345"], top_k=5)
    print(f"  返回 {len(res)} 条（应为 0）")
    assert len(res) == 0

    header("边界 4: 空标签列表")
    res = r.recommend_by_tags([], top_k=5)
    print(f"  返回 {len(res)} 条（应为 0）")
    assert len(res) == 0

    # ========== 详细分解（debug）==========
    header("分解: 模式 1 给星际牛仔的 top1 的 13 因子明细")
    seed_idx = r._id_to_idx[1]
    seed = r.anime_list[seed_idx]
    query_vec = r.tag_matrix[seed_idx]
    cands, sims = r._recall(query_vec, n=200)
    query = multi_factor.build_query_from_anime(seed)
    ranked = multi_factor.re_rank(cands, query, sims, weights=r.weights, top_k=3)
    print(f"种子: {seed.get('name_cn') or seed.get('name')} "
          f"({seed.get('year')}, {seed.get('format')}, studios={seed.get('studios')})")
    for x in ranked:
        print()
        multi_factor.explain(x, weights=r.weights)

    # ========== 权重调参测试 ==========
    header("权重测试: rating 提到 0.30 后，top3 变化？")
    r.set_weights({"rating": 0.30, "tag": 0.20})
    res1 = r.recommend_by_anime(1, top_k=3)
    print("rating↑ 后的 top3:")
    show(res1, n=3)

    r.set_weights({})  # 恢复默认
    res2 = r.recommend_by_anime(1, top_k=3)
    print("\n默认权重的 top3:")
    show(res2, n=3)

    print()
    print("=" * 70)
    print("  全部测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
