"""
quiz_system.py
===============
心理画像问答系统 - 通过问答生成用户心理画像

两种模式：
  - 简易版（20题）：快速生成基础心理画像，约2-3分钟
  - 复杂版（60题）：深度心理画像，约8-10分钟

每道题映射到心理画像的多个维度，答题结束后加权计算最终画像。
"""

from psych_profile import ComprehensivePsychProfile


# ============================================================
# 问答题目设计
# ============================================================

# 题目类型：
#   - single: 单选（4个选项）
#   - scale: 量表（1-5分）
#   - multi: 多选（选择最多3项）

# 每个选项映射到心理维度的权重
# 格式：{dimension: {value: weight}}
# 例如：选择A选项 → big_five.O += 0.3, archetype.sage += 0.5

SIMPLE_QUIZ = {
    "title": "快速心理画像测试",
    "description": "20道精选题目，快速了解你的番剧偏好",
    "questions": [
        # === 第1-5题：基础偏好 ===
        {
            "id": 1,
            "type": "single",
            "question": "看完一部番后，你最在意的是什么？",
            "options": [
                {
                    "text": "剧情是否有深度，能引发思考",
                    "mapping": {"big_five": {"O": 0.3, "N": 0.2}, "archetype": "sage", "defense": ["intellectualization"]}
                },
                {
                    "text": "角色是否有魅力，让人喜欢",
                    "mapping": {"big_five": {"A": 0.3, "E": 0.2}, "archetype": "lover", "sdt": {"relatedness": 0.3}}
                },
                {
                    "text": "战斗/竞技场面是否精彩",
                    "mapping": {"big_five": {"E": 0.3}, "archetype": "hero", "defense": ["sublimation"]}
                },
                {
                    "text": "整体氛围是否让我放松",
                    "mapping": {"big_five": {"A": 0.3, "N": -0.3}, "archetype": "innocent", "defense": ["isolation"]}
                }
            ]
        },
        {
            "id": 2,
            "type": "single",
            "question": "你更喜欢哪种故事结局？",
            "options": [
                {
                    "text": "主角经历磨难后获得成长",
                    "mapping": {"narrative": "progressive", "archetype": "hero", "achievement": "mastery"}
                },
                {
                    "text": "温馨日常，没有太多波澜",
                    "mapping": {"narrative": "stability", "archetype": "everyman", "defense": ["isolation"]}
                },
                {
                    "text": "出人意料的反转结局",
                    "mapping": {"narrative": "contamination", "archetype": "sage", "personal_constructs": ["flexibility"]}
                },
                {
                    "text": "开放式结局，留有想象空间",
                    "mapping": {"big_five": {"O": 0.3}, "archetype": "seeker", "personal_constructs": ["complexity"]}
                }
            ]
        },
        {
            "id": 3,
            "type": "single",
            "question": "如果穿越到异世界，你希望自己是什么角色？",
            "options": [
                {
                    "text": "勇者，拯救世界的英雄",
                    "mapping": {"archetype": "hero", "sdt": {"competence": 0.3}, "moral": ["care_harm"]}
                },
                {
                    "text": "智者，掌握知识和秘密",
                    "mapping": {"archetype": "sage", "sdt": {"autonomy": 0.3}, "cognitive": ["Ni", "Ti"]}
                },
                {
                    "text": "商人或冒险者，自由自在",
                    "mapping": {"archetype": "explorer", "sdt": {"autonomy": 0.4}, "regulatory": "promotion"}
                },
                {
                    "text": "普通人，享受平静生活",
                    "mapping": {"archetype": "innocent", "sdt": {"relatedness": 0.3}, "regulatory": "prevention"}
                }
            ]
        },
        {
            "id": 4,
            "type": "single",
            "question": "你更容易被什么类型的角色吸引？",
            "options": [
                {
                    "text": "坚强勇敢，永不放弃的",
                    "mapping": {"archetype": "hero", "character_id": "self_ideal", "sdt": {"competence": 0.3}}
                },
                {
                    "text": "温柔善良，关心他人的",
                    "mapping": {"archetype": "caregiver", "big_five": {"A": 0.3}, "sdt": {"relatedness": 0.3}}
                },
                {
                    "text": "神秘复杂，有隐藏过去的",
                    "mapping": {"archetype": "outlaw", "big_five": {"N": 0.3}, "character_id": "self_shadow"}
                },
                {
                    "text": "搞笑有趣，能带来欢乐的",
                    "mapping": {"archetype": "jester", "big_five": {"E": 0.3}, "defense": ["isolation"]}
                }
            ]
        },
        {
            "id": 5,
            "type": "single",
            "question": "看番时，你更在意什么？",
            "options": [
                {
                    "text": "作画质量和视觉效果",
                    "mapping": {"big_five": {"O": 0.2}, "meaning_type": "experiential", "cognitive": ["Se"]}
                },
                {
                    "text": "剧本和台词的深度",
                    "mapping": {"big_five": {"O": 0.3, "C": 0.2}, "archetype": "sage", "defense": ["intellectualization"]}
                },
                {
                    "text": "角色之间的互动和关系",
                    "mapping": {"big_five": {"A": 0.3, "E": 0.2}, "sdt": {"relatedness": 0.4}, "archetype": "lover"}
                },
                {
                    "text": "整体氛围和音乐",
                    "mapping": {"big_five": {"O": 0.2, "N": 0.2}, "meaning_type": "experiential", "emotion_regulation": ["acceptance"]}
                }
            ]
        },

        # === 第6-10题：情感需求 ===
        {
            "id": 6,
            "type": "single",
            "question": "当你心情不好时，你会选择看什么类型的番？",
            "options": [
                {
                    "text": "热血战斗番，释放压力",
                    "mapping": {"defense": ["sublimation", "displacement"], "archetype": "hero", "big_five": {"E": 0.2}}
                },
                {
                    "text": "治愈日常番，让自己平静",
                    "mapping": {"defense": ["isolation", "acceptance"], "archetype": "innocent", "big_five": {"A": 0.3, "N": -0.3}}
                },
                {
                    "text": "搞笑番，转移注意力",
                    "mapping": {"defense": ["isolation"], "archetype": "jester", "emotion_regulation": ["reappraisal"]}
                },
                {
                    "text": "深刻的作品，让自己哭出来",
                    "mapping": {"emotion_regulation": ["rumination"], "big_five": {"N": 0.4}, "narrative": "contamination"}
                }
            ]
        },
        {
            "id": 7,
            "type": "single",
            "question": "你希望从番剧中获得什么？",
            "options": [
                {
                    "text": "逃离现实，沉浸到另一个世界",
                    "mapping": {"defense": ["dissociation", "fantasy"], "archetype": "explorer", "worldview": "magical_world"}
                },
                {
                    "text": "看到人性的复杂和真实",
                    "mapping": {"big_five": {"O": 0.3, "N": 0.2}, "archetype": "sage", "worldview": "unjust_world"}
                },
                {
                    "text": "感受温暖和希望",
                    "mapping": {"big_five": {"A": 0.4}, "archetype": "caregiver", "narrative": "redemption"}
                },
                {
                    "text": "获得刺激和快感",
                    "mapping": {"big_five": {"E": 0.3}, "defense": ["sublimation"], "regulatory": "promotion"}
                }
            ]
        },
        {
            "id": 8,
            "type": "single",
            "question": "以下哪种情感体验最打动你？",
            "options": [
                {
                    "text": "为同伴而战的羁绊",
                    "mapping": {"moral": ["loyalty_betrayal"], "sdt": {"relatedness": 0.4}, "archetype": "hero"}
                },
                {
                    "text": "克服困难后的成长",
                    "mapping": {"achievement": "mastery", "narrative": "progressive", "archetype": "hero"}
                },
                {
                    "text": "失去后的珍惜",
                    "mapping": {"existential": ["death"], "emotion_regulation": ["rumination"], "narrative": "contamination"}
                },
                {
                    "text": "平凡日常中的小确幸",
                    "mapping": {"big_five": {"A": 0.3, "N": -0.3}, "archetype": "everyman", "meaning_type": "experiential"}
                }
            ]
        },
        {
            "id": 9,
            "type": "single",
            "question": "你对虐心剧情的态度是？",
            "options": [
                {
                    "text": "喜欢，能让情感更深刻",
                    "mapping": {"big_five": {"N": 0.4}, "emotion_regulation": ["rumination"], "attachment": "anxious_preoccupied"}
                },
                {
                    "text": "可以接受，但要有好结局",
                    "mapping": {"narrative": "redemption", "big_five": {"A": 0.2}, "attachment": "secure"}
                },
                {
                    "text": "不太喜欢，更偏好轻松的",
                    "mapping": {"big_five": {"N": -0.3, "A": 0.2}, "defense": ["isolation"], "regulatory": "prevention"}
                },
                {
                    "text": "完全不接受，看番就是为了开心",
                    "mapping": {"big_five": {"N": -0.4, "E": 0.2}, "archetype": "jester", "defense": ["denial"]}
                }
            ]
        },
        {
            "id": 10,
            "type": "single",
            "question": "你更喜欢看主角是什么样的人？",
            "options": [
                {
                    "text": "天赋异禀，实力强大",
                    "mapping": {"defense": ["fantasy"], "self_object": ["mirroring"], "sdt": {"competence": 0.3}}
                },
                {
                    "text": "普通人通过努力变强",
                    "mapping": {"achievement": "mastery", "character_id": "self_real", "narrative": "progressive"}
                },
                {
                    "text": "有缺陷但真实的普通人",
                    "mapping": {"character_id": "self_real", "big_five": {"A": 0.2}, "object_relations": "integration"}
                },
                {
                    "text": "复杂的灰色角色",
                    "mapping": {"character_id": "anti_hero", "big_five": {"N": 0.3}, "object_relations": "splitting"}
                }
            ]
        },

        # === 第11-15题：题材偏好 ===
        {
            "id": 11,
            "type": "single",
            "question": "以下哪种世界观最吸引你？",
            "options": [
                {
                    "text": "魔法和超能力存在的世界",
                    "mapping": {"worldview": "magical_world", "archetype": "magician", "big_five": {"O": 0.3}}
                },
                {
                    "text": "未来科技高度发达的世界",
                    "mapping": {"worldview": "dystopian", "cognitive": ["Ti", "Ne"], "big_five": {"O": 0.3}}
                },
                {
                    "text": "和现实相似但有隐藏秘密的世界",
                    "mapping": {"worldview": "unjust_world", "archetype": "sage", "defense": ["intellectualization"]}
                },
                {
                    "text": "平静美好的日常世界",
                    "mapping": {"worldview": "just_world", "archetype": "innocent", "defense": ["isolation"]}
                }
            ]
        },
        {
            "id": 12,
            "type": "single",
            "question": "你对以下哪种题材最感兴趣？",
            "options": [
                {
                    "text": "竞技体育，热血拼搏",
                    "mapping": {"archetype": "hero", "sdt": {"competence": 0.4}, "defense": ["sublimation"]}
                },
                {
                    "text": "悬疑推理，烧脑解谜",
                    "mapping": {"archetype": "sage", "cognitive": ["Ti", "Ni"], "defense": ["intellectualization"]}
                },
                {
                    "text": "日常治愈，温馨生活",
                    "mapping": {"archetype": "innocent", "big_five": {"A": 0.3, "N": -0.3}, "defense": ["isolation"]}
                },
                {
                    "text": "奇幻冒险，探索世界",
                    "mapping": {"archetype": "explorer", "sdt": {"autonomy": 0.4}, "narrative": "exploration"}
                }
            ]
        },
        {
            "id": 13,
            "type": "single",
            "question": "你更喜欢哪种战斗/冲突描写？",
            "options": [
                {
                    "text": "热血沸腾的正面对决",
                    "mapping": {"defense": ["sublimation"], "archetype": "hero", "big_five": {"E": 0.3}}
                },
                {
                    "text": "智力博弈，策略对决",
                    "mapping": {"cognitive": ["Ti", "Te"], "archetype": "sage", "defense": ["intellectualization"]}
                },
                {
                    "text": "心理战，意志的较量",
                    "mapping": {"big_five": {"N": 0.3}, "cognitive": ["Ni", "Fi"], "defense": ["intellectualization"]}
                },
                {
                    "text": "不喜欢战斗，更喜欢和平解决",
                    "mapping": {"big_five": {"A": 0.4}, "archetype": "caregiver", "moral": ["care_harm"]}
                }
            ]
        },
        {
            "id": 14,
            "type": "single",
            "question": "你对恋爱番的看法是？",
            "options": [
                {
                    "text": "很喜欢，恋爱是美好的",
                    "mapping": {"archetype": "lover", "sdt": {"relatedness": 0.4}, "big_five": {"A": 0.3}}
                },
                {
                    "text": "喜欢看，但要有深度",
                    "mapping": {"archetype": "lover", "big_five": {"O": 0.2, "A": 0.2}, "object_relations": "integration"}
                },
                {
                    "text": "不太感兴趣，更喜欢其他题材",
                    "mapping": {"sdt": {"autonomy": 0.2, "competence": 0.2}, "big_five": {"E": -0.1}}
                },
                {
                    "text": "完全不看，觉得无聊",
                    "mapping": {"defense": ["intellectualization"], "sdt": {"autonomy": 0.3}, "attachment": "dismissive_avoidant"}
                }
            ]
        },
        {
            "id": 15,
            "type": "single",
            "question": "你更喜欢看什么年代背景的番？",
            "options": [
                {
                    "text": "现代或近未来",
                    "mapping": {"big_five": {"C": 0.1}, "worldview": "just_world"}
                },
                {
                    "text": "古代或中世纪",
                    "mapping": {"values": {"tradition": 0.3}, "archetype": "hero", "big_five": {"O": 0.2}}
                },
                {
                    "text": "未来科幻",
                    "mapping": {"cognitive": ["Ti", "Ne"], "big_five": {"O": 0.4}, "worldview": "dystopian"}
                },
                {
                    "text": "没有特别偏好",
                    "mapping": {"big_five": {"O": 0.1}}
                }
            ]
        },

        # === 第16-20题：价值观 ===
        {
            "id": 16,
            "type": "single",
            "question": "你认为什么是最重要的？",
            "options": [
                {
                    "text": "自由，做自己想做的事",
                    "mapping": {"sdt": {"autonomy": 0.4}, "moral": ["liberty_oppression"], "regulatory": "promotion"}
                },
                {
                    "text": "羁绊，与重要的人在一起",
                    "mapping": {"sdt": {"relatedness": 0.5}, "moral": ["loyalty_betrayal"], "social_identity": "in_group"}
                },
                {
                    "text": "成长，不断超越自己",
                    "mapping": {"sdt": {"competence": 0.4}, "achievement": "mastery", "narrative": "progressive"}
                },
                {
                    "text": "平静，过安稳的生活",
                    "mapping": {"regulatory": "prevention", "values": {"security": 0.4}, "defense": ["isolation"]}
                }
            ]
        },
        {
            "id": 17,
            "type": "single",
            "question": "面对不公正的事情，你会？",
            "options": [
                {
                    "text": "挺身而出，即使有风险",
                    "mapping": {"moral": ["care_harm", "fairness_cheating"], "archetype": "hero", "big_five": {"A": 0.2}}
                },
                {
                    "text": "用智慧找到解决办法",
                    "mapping": {"moral": ["fairness_cheating"], "archetype": "sage", "defense": ["intellectualization"]}
                },
                {
                    "text": "视情况而定，保护自己优先",
                    "mapping": {"regulatory": "prevention", "big_five": {"C": 0.2}, "defense": ["isolation"]}
                },
                {
                    "text": "觉得世界本就不公平",
                    "mapping": {"worldview": "unjust_world", "big_five": {"N": 0.2}, "object_relations": "splitting"}
                }
            ]
        },
        {
            "id": 18,
            "type": "single",
            "question": "你更认同哪种人生观？",
            "options": [
                {
                    "text": "人生在于不断挑战和冒险",
                    "mapping": {"archetype": "explorer", "regulatory": "promotion", "sdt": {"autonomy": 0.3}}
                },
                {
                    "text": "人生在于与人建立深刻连接",
                    "mapping": {"sdt": {"relatedness": 0.4}, "archetype": "lover", "meaning_type": "experiential"}
                },
                {
                    "text": "人生在于追求知识和真理",
                    "mapping": {"archetype": "sage", "cognitive": ["Ni", "Ti"], "meaning_type": "attitudinal"}
                },
                {
                    "text": "人生在于享受当下的美好",
                    "mapping": {"archetype": "jester", "meaning_type": "experiential", "big_five": {"E": 0.2}}
                }
            ]
        },
        {
            "id": 19,
            "type": "single",
            "question": "你希望番剧给你带来什么启发？",
            "options": [
                {
                    "text": "对人生和社会的思考",
                    "mapping": {"existential": ["meaninglessness", "freedom"], "archetype": "sage", "big_five": {"O": 0.3}}
                },
                {
                    "text": "对人性的理解和包容",
                    "mapping": {"object_relations": "integration", "big_five": {"A": 0.3}, "moral": ["care_harm"]}
                },
                {
                    "text": "面对困难的勇气",
                    "mapping": {"archetype": "hero", "narrative": "redemption", "sdt": {"competence": 0.3}}
                },
                {
                    "text": "不需要启发，纯粹享受就好",
                    "mapping": {"defense": ["isolation"], "archetype": "jester", "regulatory": "prevention"}
                }
            ]
        },
        {
            "id": 20,
            "type": "single",
            "question": "用一个词形容你理想中的番剧？",
            "options": [
                {
                    "text": "深刻",
                    "mapping": {"big_five": {"O": 0.3, "N": 0.2}, "archetype": "sage", "meaning_type": "attitudinal"}
                },
                {
                    "text": "热血",
                    "mapping": {"defense": ["sublimation"], "archetype": "hero", "big_five": {"E": 0.3}}
                },
                {
                    "text": "治愈",
                    "mapping": {"big_five": {"A": 0.4, "N": -0.3}, "archetype": "caregiver", "defense": ["isolation"]}
                },
                {
                    "text": "自由",
                    "mapping": {"sdt": {"autonomy": 0.4}, "archetype": "explorer", "regulatory": "promotion"}
                }
            ]
        },
    ]
}


# ============================================================
# 复杂版问答系统（60题）
# ============================================================

COMPLEX_QUIZ = {
    "title": "深度心理画像测试",
    "description": "60道动漫相关题目，通过你的番剧偏好全面了解你的心理画像",
    "questions": [
        # === 第1-10题：番剧类型偏好 ===
        {
            "id": 1, "type": "single",
            "question": "以下哪种番剧类型最吸引你？",
            "options": [
                {"text": "热血战斗番（如《鬼灭之刃》《咒术回战》）", "mapping": {"archetype": "hero", "defense": ["sublimation"], "big_five": {"E": 0.3}}},
                {"text": "悬疑推理番（如《命运石之门》《约定的梦幻岛》）", "mapping": {"archetype": "sage", "cognitive": ["Ti", "Ni"], "defense": ["intellectualization"]}},
                {"text": "日常治愈番（如《夏目友人帐》《摇曳露营》）", "mapping": {"archetype": "innocent", "big_five": {"A": 0.3, "N": -0.3}, "defense": ["isolation"]}},
                {"text": "奇幻冒险番（如《无职转生》《Re:Zero》）", "mapping": {"archetype": "explorer", "sdt": {"autonomy": 0.4}, "worldview": "magical_world"}}
            ]
        },
        {
            "id": 2, "type": "single",
            "question": "你更喜欢看什么题材的番？",
            "options": [
                {"text": "校园青春（如《我的青春恋爱物语果然有问题》）", "mapping": {"archetype": "orphan", "sdt": {"relatedness": 0.3}, "big_five": {"N": 0.2}}},
                {"text": "科幻未来（如《攻壳机动队》《Psycho-Pass》）", "mapping": {"cognitive": ["Ti", "Ne"], "big_five": {"O": 0.3}, "worldview": "dystopian"}},
                {"text": "历史架空（如《进击的巨人》《王者天下》）", "mapping": {"values": {"tradition": 0.2}, "archetype": "hero", "big_five": {"O": 0.2}}},
                {"text": "异世界转生（如《刀剑神域》《转生史莱姆》）", "mapping": {"defense": ["fantasy", "dissociation"], "archetype": "explorer", "worldview": "magical_world"}}
            ]
        },
        {
            "id": 3, "type": "single",
            "question": "你对恋爱番的态度是？",
            "options": [
                {"text": "非常喜欢，恋爱是美好的", "mapping": {"archetype": "lover", "sdt": {"relatedness": 0.4}, "big_five": {"A": 0.3}}},
                {"text": "喜欢看，但要有深度", "mapping": {"archetype": "lover", "big_five": {"O": 0.2, "A": 0.2}, "object_relations": "integration"}},
                {"text": "不太感兴趣，更喜欢其他题材", "mapping": {"sdt": {"autonomy": 0.2, "competence": 0.2}, "big_five": {"E": -0.1}}},
                {"text": "完全不看，觉得无聊", "mapping": {"defense": ["intellectualization"], "sdt": {"autonomy": 0.3}, "attachment": "dismissive_avoidant"}}
            ]
        },
        {
            "id": 4, "type": "single",
            "question": "你更喜欢什么节奏的番？",
            "options": [
                {"text": "快节奏，紧张刺激", "mapping": {"big_five": {"E": 0.3}, "defense": ["sublimation"]}},
                {"text": "中等节奏，张弛有度", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "慢节奏，细腻描写", "mapping": {"big_five": {"N": 0.2}, "emotion_regulation": ["acceptance"]}},
                {"text": "看题材决定", "mapping": {}}
            ]
        },
        {
            "id": 5, "type": "single",
            "question": "你更喜欢什么画风的番？",
            "options": [
                {"text": "精致细腻的画风", "mapping": {"big_five": {"O": 0.2}, "meaning_type": "experiential"}},
                {"text": "简洁有力的画风", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "独特个性的画风", "mapping": {"big_five": {"O": 0.3}, "personal_constructs": ["flexibility"]}},
                {"text": "不在意画风", "mapping": {}}
            ]
        },
        {
            "id": 6, "type": "single",
            "question": "你更喜欢看多长的番？",
            "options": [
                {"text": "短篇（12集以内）", "mapping": {"big_five": {"E": 0.1}}},
                {"text": "中篇（13-26集）", "mapping": {}},
                {"text": "长篇（26集以上）", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "无所谓", "mapping": {}}
            ]
        },
        {
            "id": 7, "type": "single",
            "question": "你对作画崩坏的态度是？",
            "options": [
                {"text": "完全不能接受", "mapping": {"big_five": {"C": 0.3}, "meaning_type": "experiential"}},
                {"text": "如果剧情好可以接受", "mapping": {"big_five": {"C": 0.1}}},
                {"text": "不太在意", "mapping": {}},
                {"text": "完全不在意", "mapping": {"big_five": {"C": -0.1}}}
            ]
        },
        {
            "id": 8, "type": "single",
            "question": "你对音乐在番剧中的作用有多看重？",
            "options": [
                {"text": "非常重要，好音乐能升华作品", "mapping": {"meaning_type": "experiential", "big_five": {"O": 0.2}}},
                {"text": "比较重要", "mapping": {}},
                {"text": "不太在意", "mapping": {}},
                {"text": "完全不在意", "mapping": {"big_five": {"O": -0.1}}}
            ]
        },
        {
            "id": 9, "type": "single",
            "question": "你更喜欢看什么年代背景的番？",
            "options": [
                {"text": "现代或近未来", "mapping": {"big_five": {"C": 0.1}, "worldview": "just_world"}},
                {"text": "古代或中世纪", "mapping": {"values": {"tradition": 0.3}, "archetype": "hero", "big_five": {"O": 0.2}}},
                {"text": "未来科幻", "mapping": {"cognitive": ["Ti", "Ne"], "big_five": {"O": 0.4}, "worldview": "dystopian"}},
                {"text": "没有特别偏好", "mapping": {"big_five": {"O": 0.1}}}
            ]
        },
        {
            "id": 10, "type": "single",
            "question": "你更喜欢什么样的叙事结构？",
            "options": [
                {"text": "线性叙事，清晰明了", "mapping": {"big_five": {"C": 0.3}, "personal_constructs": ["dichotomous"]}},
                {"text": "多线叙事，交错进行", "mapping": {"big_five": {"O": 0.3}, "personal_constructs": ["complexity"]}},
                {"text": "倒叙或插叙", "mapping": {"big_five": {"O": 0.2}, "personal_constructs": ["flexibility"]}},
                {"text": "无所谓", "mapping": {}}
            ]
        },

        # === 第11-20题：角色偏好 ===
        {
            "id": 11, "type": "single",
            "question": "你更容易被什么类型的角色吸引？",
            "options": [
                {"text": "坚强勇敢，永不放弃的", "mapping": {"archetype": "hero", "character_id": "self_ideal", "sdt": {"competence": 0.3}}},
                {"text": "温柔善良，关心他人的", "mapping": {"archetype": "caregiver", "big_five": {"A": 0.3}, "sdt": {"relatedness": 0.3}}},
                {"text": "神秘复杂，有隐藏过去的", "mapping": {"archetype": "outlaw", "big_five": {"N": 0.3}, "character_id": "self_shadow"}},
                {"text": "搞笑有趣，能带来欢乐的", "mapping": {"archetype": "jester", "big_five": {"E": 0.3}, "defense": ["isolation"]}}
            ]
        },
        {
            "id": 12, "type": "single",
            "question": "你更喜欢看主角是什么样的人？",
            "options": [
                {"text": "天赋异禀，实力强大", "mapping": {"defense": ["fantasy"], "self_object": ["mirroring"], "sdt": {"competence": 0.3}}},
                {"text": "普通人通过努力变强", "mapping": {"achievement": "mastery", "character_id": "self_real", "narrative": "progressive"}},
                {"text": "有缺陷但真实的普通人", "mapping": {"character_id": "self_real", "big_five": {"A": 0.2}, "object_relations": "integration"}},
                {"text": "复杂的灰色角色", "mapping": {"character_id": "anti_hero", "big_five": {"N": 0.3}, "object_relations": "splitting"}}
            ]
        },
        {
            "id": 13, "type": "single",
            "question": "你更容易同情什么样的角色？",
            "options": [
                {"text": "努力但失败的人", "mapping": {"character_id": "self_real", "moral": ["care_harm"], "big_five": {"A": 0.3}}},
                {"text": "被误解的天才", "mapping": {"character_id": "self_shadow", "big_five": {"N": 0.2}}},
                {"text": "善良的普通人", "mapping": {"character_id": "self_real", "archetype": "everyman"}},
                {"text": "复杂的反派", "mapping": {"character_id": "anti_hero", "object_relations": "splitting"}}
            ]
        },
        {
            "id": 14, "type": "single",
            "question": "你希望从主角身上看到什么？",
            "options": [
                {"text": "自己想成为的样子", "mapping": {"character_id": "self_ideal", "self_object": ["mirroring"]}},
                {"text": "和自己相似的影子", "mapping": {"character_id": "self_real", "self_object": ["twinship"]}},
                {"text": "完全不同的人生", "mapping": {"archetype": "explorer", "sdt": {"autonomy": 0.2}}},
                {"text": "人性的复杂面", "mapping": {"character_id": "self_shadow", "object_relations": "integration"}}
            ]
        },
        {
            "id": 15, "type": "single",
            "question": "你对天才型主角的看法是？",
            "options": [
                {"text": "很喜欢，看天才碾压很爽", "mapping": {"defense": ["fantasy"], "self_object": ["mirroring"]}},
                {"text": "喜欢，但要有成长空间", "mapping": {"achievement": "mastery"}},
                {"text": "更喜欢努力型主角", "mapping": {"character_id": "self_real", "achievement": "mastery"}},
                {"text": "无所谓", "mapping": {}}
            ]
        },
        {
            "id": 16, "type": "single",
            "question": "你更喜欢看什么样的友情描写？",
            "options": [
                {"text": "并肩作战的伙伴", "mapping": {"moral": ["loyalty_betrayal"], "social_identity": "in_group", "archetype": "hero"}},
                {"text": "互相理解的知己", "mapping": {"sdt": {"relatedness": 0.4}, "self_object": ["twinship"]}},
                {"text": "温馨的日常互动", "mapping": {"archetype": "everyman", "big_five": {"A": 0.3}}},
                {"text": "不太在意友情描写", "mapping": {"sdt": {"autonomy": 0.2}}}
            ]
        },
        {
            "id": 17, "type": "single",
            "question": "你更喜欢看什么样的恋爱描写？",
            "options": [
                {"text": "甜蜜温馨的双向奔赴", "mapping": {"attachment": "secure", "archetype": "lover", "big_five": {"A": 0.3}}},
                {"text": "虐心纠结的感情", "mapping": {"attachment": "fearful_avoidant", "big_five": {"N": 0.3}, "emotion_regulation": ["rumination"]}},
                {"text": "含蓄内敛的暗恋", "mapping": {"attachment": "dismissive_avoidant", "big_five": {"A": 0.1}}},
                {"text": "不太看恋爱番", "mapping": {"sdt": {"autonomy": 0.2}, "attachment": "dismissive_avoidant"}}
            ]
        },
        {
            "id": 18, "type": "single",
            "question": "你对反派角色的看法是？",
            "options": [
                {"text": "好的反派能让作品更精彩", "mapping": {"object_relations": "integration", "big_five": {"O": 0.2}}},
                {"text": "喜欢有魅力的反派", "mapping": {"character_id": "anti_hero", "big_five": {"N": 0.2}}},
                {"text": "更喜欢纯粹的坏人", "mapping": {"object_relations": "splitting", "moral": ["fairness_cheating"]}},
                {"text": "不太在意反派", "mapping": {}}
            ]
        },
        {
            "id": 19, "type": "single",
            "question": "你对声优有多在意？",
            "options": [
                {"text": "非常重要，会影响选择", "mapping": {"meaning_type": "experiential"}},
                {"text": "比较重要", "mapping": {}},
                {"text": "不太在意", "mapping": {}},
                {"text": "完全不在意", "mapping": {}}
            ]
        },
        {
            "id": 20, "type": "single",
            "question": "你对续作的态度是？",
            "options": [
                {"text": "期待续作", "mapping": {"values": {"security": 0.2}}},
                {"text": "看质量决定", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "更喜欢新作品", "mapping": {"big_five": {"O": 0.2}}},
                {"text": "无所谓", "mapping": {}}
            ]
        },

        # === 第21-30题：情感与剧情偏好 ===
        {
            "id": 21, "type": "single",
            "question": "看完一部番后，你最在意的是什么？",
            "options": [
                {"text": "剧情是否有深度，能引发思考", "mapping": {"big_five": {"O": 0.3, "N": 0.2}, "archetype": "sage", "defense": ["intellectualization"]}},
                {"text": "角色是否有魅力，让人喜欢", "mapping": {"big_five": {"A": 0.3, "E": 0.2}, "archetype": "lover", "sdt": {"relatedness": 0.3}}},
                {"text": "战斗/竞技场面是否精彩", "mapping": {"big_five": {"E": 0.3}, "archetype": "hero", "defense": ["sublimation"]}},
                {"text": "整体氛围是否让我放松", "mapping": {"big_five": {"A": 0.3, "N": -0.3}, "archetype": "innocent", "defense": ["isolation"]}}
            ]
        },
        {
            "id": 22, "type": "single",
            "question": "你更喜欢哪种故事结局？",
            "options": [
                {"text": "主角经历磨难后获得成长", "mapping": {"narrative": "progressive", "archetype": "hero", "achievement": "mastery"}},
                {"text": "温馨日常，没有太多波澜", "mapping": {"narrative": "stability", "archetype": "everyman", "defense": ["isolation"]}},
                {"text": "出人意料的反转结局", "mapping": {"narrative": "contamination", "archetype": "sage", "personal_constructs": ["flexibility"]}},
                {"text": "开放式结局，留有想象空间", "mapping": {"big_five": {"O": 0.3}, "archetype": "seeker", "personal_constructs": ["complexity"]}}
            ]
        },
        {
            "id": 23, "type": "single",
            "question": "当你心情不好时，你会选择看什么类型的番？",
            "options": [
                {"text": "热血战斗番，释放压力", "mapping": {"defense": ["sublimation", "displacement"], "archetype": "hero", "big_five": {"E": 0.2}}},
                {"text": "治愈日常番，让自己平静", "mapping": {"defense": ["isolation", "acceptance"], "archetype": "innocent", "big_five": {"A": 0.3, "N": -0.3}}},
                {"text": "搞笑番，转移注意力", "mapping": {"defense": ["isolation"], "archetype": "jester", "emotion_regulation": ["reappraisal"]}},
                {"text": "深刻的作品，让自己哭出来", "mapping": {"emotion_regulation": ["rumination"], "big_five": {"N": 0.4}, "narrative": "contamination"}}
            ]
        },
        {
            "id": 24, "type": "single",
            "question": "你对虐心剧情的态度是？",
            "options": [
                {"text": "喜欢，能让情感更深刻", "mapping": {"big_five": {"N": 0.4}, "emotion_regulation": ["rumination"], "attachment": "anxious_preoccupied"}},
                {"text": "可以接受，但要有好结局", "mapping": {"narrative": "redemption", "big_five": {"A": 0.2}, "attachment": "secure"}},
                {"text": "不太喜欢，更偏好轻松的", "mapping": {"big_five": {"N": -0.3, "A": 0.2}, "defense": ["isolation"], "regulatory": "prevention"}},
                {"text": "完全不接受，看番就是为了开心", "mapping": {"big_five": {"N": -0.4, "E": 0.2}, "archetype": "jester", "defense": ["denial"]}}
            ]
        },
        {
            "id": 25, "type": "single",
            "question": "你对悲剧结局的态度是？",
            "options": [
                {"text": "喜欢，更有深度", "mapping": {"big_five": {"N": 0.3}, "narrative": "contamination", "meaning_type": "attitudinal"}},
                {"text": "可以接受，但要有意义", "mapping": {"big_five": {"N": 0.1}, "object_relations": "integration"}},
                {"text": "不太喜欢，希望有好结局", "mapping": {"narrative": "redemption", "big_five": {"A": 0.2}}},
                {"text": "完全不能接受", "mapping": {"defense": ["denial"], "big_five": {"N": -0.3}}}
            ]
        },
        {
            "id": 26, "type": "single",
            "question": "以下哪种情感体验最打动你？",
            "options": [
                {"text": "为同伴而战的羁绊", "mapping": {"moral": ["loyalty_betrayal"], "sdt": {"relatedness": 0.4}, "archetype": "hero"}},
                {"text": "克服困难后的成长", "mapping": {"achievement": "mastery", "narrative": "progressive", "archetype": "hero"}},
                {"text": "失去后的珍惜", "mapping": {"existential": ["death"], "emotion_regulation": ["rumination"], "narrative": "contamination"}},
                {"text": "平凡日常中的小确幸", "mapping": {"big_five": {"A": 0.3, "N": -0.3}, "archetype": "everyman", "meaning_type": "experiential"}}
            ]
        },
        {
            "id": 27, "type": "single",
            "question": "你对救赎主题的看法是？",
            "options": [
                {"text": "非常喜欢，浪子回头最动人", "mapping": {"narrative": "redemption", "moral": ["care_harm"], "archetype": "hero"}},
                {"text": "喜欢，但要有合理铺垫", "mapping": {"narrative": "redemption", "big_five": {"C": 0.2}}},
                {"text": "无所谓", "mapping": {}},
                {"text": "不太喜欢", "mapping": {"worldview": "unjust_world"}}
            ]
        },
        {
            "id": 28, "type": "single",
            "question": "你对牺牲主题的态度是？",
            "options": [
                {"text": "为他人牺牲是最伟大的", "mapping": {"archetype": "caregiver", "moral": ["care_harm"], "big_five": {"A": 0.4}}},
                {"text": "值得尊敬，但要理性看待", "mapping": {"moral": ["care_harm"], "big_five": {"A": 0.2}}},
                {"text": "要看具体情况", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "不太喜欢这种主题", "mapping": {"values": {"security": 0.2}, "regulatory": "prevention"}}
            ]
        },
        {
            "id": 29, "type": "single",
            "question": "你更喜欢看什么样的战斗/冲突描写？",
            "options": [
                {"text": "热血沸腾的正面对决", "mapping": {"defense": ["sublimation"], "archetype": "hero", "big_five": {"E": 0.3}}},
                {"text": "智力博弈，策略对决", "mapping": {"cognitive": ["Ti", "Te"], "archetype": "sage", "defense": ["intellectualization"]}},
                {"text": "心理战，意志的较量", "mapping": {"big_five": {"N": 0.3}, "cognitive": ["Ni", "Fi"], "defense": ["intellectualization"]}},
                {"text": "不喜欢战斗，更喜欢和平解决", "mapping": {"big_five": {"A": 0.4}, "archetype": "caregiver", "moral": ["care_harm"]}}
            ]
        },
        {
            "id": 30, "type": "single",
            "question": "你更喜欢看主角面对什么样的挑战？",
            "options": [
                {"text": "强大的敌人", "mapping": {"archetype": "hero", "defense": ["sublimation"]}},
                {"text": "内心的挣扎", "mapping": {"big_five": {"N": 0.3}, "cognitive": ["Fi", "Ni"]}},
                {"text": "社会的不公", "mapping": {"moral": ["fairness_cheating", "liberty_oppression"]}},
                {"text": "生存的考验", "mapping": {"existential": ["death"], "defense": ["sublimation"]}}
            ]
        },

        # === 第31-40题：世界观与价值观 ===
        {
            "id": 31, "type": "single",
            "question": "以下哪种世界观最吸引你？",
            "options": [
                {"text": "魔法和超能力存在的世界", "mapping": {"worldview": "magical_world", "archetype": "magician", "big_five": {"O": 0.3}}},
                {"text": "未来科技高度发达的世界", "mapping": {"worldview": "dystopian", "cognitive": ["Ti", "Ne"], "big_five": {"O": 0.3}}},
                {"text": "和现实相似但有隐藏秘密的世界", "mapping": {"worldview": "unjust_world", "archetype": "sage", "defense": ["intellectualization"]}},
                {"text": "平静美好的日常世界", "mapping": {"worldview": "just_world", "archetype": "innocent", "defense": ["isolation"]}}
            ]
        },
        {
            "id": 32, "type": "single",
            "question": "你更喜欢看什么样的社会描写？",
            "options": [
                {"text": "理想化的美好社会", "mapping": {"worldview": "just_world", "defense": ["fantasy"]}},
                {"text": "真实的社会百态", "mapping": {"worldview": "unjust_world", "big_five": {"O": 0.2}}},
                {"text": "反乌托邦的批判", "mapping": {"worldview": "dystopian", "moral": ["liberty_oppression"]}},
                {"text": "奇幻的异世界社会", "mapping": {"worldview": "magical_world", "defense": ["fantasy"]}}
            ]
        },
        {
            "id": 33, "type": "single",
            "question": "你对正义在番剧中的呈现怎么看？",
            "options": [
                {"text": "正义必胜，好人有好报", "mapping": {"worldview": "just_world", "moral": ["fairness_cheating"]}},
                {"text": "正义是相对的，看立场", "mapping": {"object_relations": "integration", "big_five": {"O": 0.2}}},
                {"text": "强权即正义，现实如此", "mapping": {"worldview": "unjust_world", "values": {"power": 0.2}}},
                {"text": "正义需要争取，不是等来的", "mapping": {"moral": ["fairness_cheating", "liberty_oppression"]}}
            ]
        },
        {
            "id": 34, "type": "single",
            "question": "你对番剧中的善恶描写怎么看？",
            "options": [
                {"text": "喜欢清晰的善恶对立", "mapping": {"object_relations": "splitting", "worldview": "just_world"}},
                {"text": "喜欢灰色地带的复杂人性", "mapping": {"object_relations": "integration", "big_five": {"O": 0.2}}},
                {"text": "喜欢反派有合理动机", "mapping": {"character_id": "anti_hero", "big_five": {"N": 0.2}}},
                {"text": "不在意善恶描写", "mapping": {}}
            ]
        },
        {
            "id": 35, "type": "single",
            "question": "你对番剧中的死亡描写怎么看？",
            "options": [
                {"text": "死亡是生命的一部分，可以接受", "mapping": {"existential": ["death"], "meaning_type": "attitudinal"}},
                {"text": "不喜欢看角色死亡", "mapping": {"defense": ["isolation", "denial"], "big_five": {"A": 0.2}}},
                {"text": "死亡能让剧情更深刻", "mapping": {"existential": ["death"], "meaning_type": "experiential"}},
                {"text": "完全不能接受角色死亡", "mapping": {"existential": ["death"], "big_five": {"N": 0.3}}}
            ]
        },
        {
            "id": 36, "type": "single",
            "question": "你对番剧中的希望主题怎么看？",
            "options": [
                {"text": "希望是人生动力，喜欢看", "mapping": {"narrative": "progressive", "regulatory": "promotion"}},
                {"text": "希望有时是幻觉", "mapping": {"worldview": "unjust_world", "big_five": {"N": 0.2}}},
                {"text": "希望需要行动支撑", "mapping": {"achievement": "mastery", "cognitive": ["Te"]}},
                {"text": "希望让人坚持", "mapping": {"narrative": "redemption", "big_five": {"A": 0.2}}}
            ]
        },
        {
            "id": 37, "type": "single",
            "question": "你对番剧中的孤独主题怎么看？",
            "options": [
                {"text": "孤独是享受，喜欢看这类角色", "mapping": {"sdt": {"autonomy": 0.3}, "big_five": {"E": -0.2}}},
                {"text": "孤独有时难受但能接受", "mapping": {"existential": ["isolation"], "big_five": {"N": 0.1}}},
                {"text": "害怕孤独，不喜欢看这类剧情", "mapping": {"attachment": "anxious_preoccupied", "sdt": {"relatedness": 0.3}}},
                {"text": "孤独让人思考，有深度", "mapping": {"archetype": "sage", "meaning_type": "attitudinal"}}
            ]
        },
        {
            "id": 38, "type": "single",
            "question": "你对番剧中的自由主题怎么看？",
            "options": [
                {"text": "自由最重要，喜欢看追求自由的故事", "mapping": {"sdt": {"autonomy": 0.4}, "moral": ["liberty_oppression"], "regulatory": "promotion"}},
                {"text": "自由需要代价", "mapping": {"moral": ["liberty_oppression"], "big_five": {"C": 0.2}}},
                {"text": "自由不是最重要的", "mapping": {"values": {"security": 0.3}, "regulatory": "prevention"}},
                {"text": "不在意这个主题", "mapping": {}}
            ]
        },
        {
            "id": 39, "type": "single",
            "question": "你对番剧中的羁绊主题怎么看？",
            "options": [
                {"text": "羁绊最重要，喜欢看伙伴故事", "mapping": {"moral": ["loyalty_betrayal"], "sdt": {"relatedness": 0.5}, "social_identity": "in_group"}},
                {"text": "羁绊很重要，但也要有个人空间", "mapping": {"sdt": {"relatedness": 0.3, "autonomy": 0.2}}},
                {"text": "更看重个人成长", "mapping": {"sdt": {"autonomy": 0.3}, "achievement": "mastery"}},
                {"text": "不在意这个主题", "mapping": {}}
            ]
        },
        {
            "id": 40, "type": "single",
            "question": "你对番剧中的成长主题怎么看？",
            "options": [
                {"text": "最喜欢看从零开始的逆袭", "mapping": {"narrative": "progressive", "achievement": "mastery", "archetype": "hero"}},
                {"text": "喜欢看内心的成长和蜕变", "mapping": {"narrative": "progressive", "archetype": "orphan", "big_five": {"N": 0.2}}},
                {"text": "喜欢看技术和能力的提升", "mapping": {"achievement": "mastery", "sdt": {"competence": 0.3}}},
                {"text": "喜欢看对世界理解的加深", "mapping": {"archetype": "sage", "meaning_type": "attitudinal"}}
            ]
        },

        # === 第41-50题：发现与拓展 ===
        {
            "id": 41, "type": "single",
            "question": "你愿意尝试和平时口味不同的番吗？",
            "options": [
                {"text": "非常愿意", "mapping": {"big_five": {"O": 0.4}, "regulatory": "promotion"}},
                {"text": "偶尔会", "mapping": {"big_five": {"O": 0.2}}},
                {"text": "不太愿意", "mapping": {"big_five": {"O": -0.1}, "regulatory": "prevention"}},
                {"text": "完全不会", "mapping": {"big_five": {"O": -0.3}, "defense": ["isolation"]}}
            ]
        },
        {
            "id": 42, "type": "single",
            "question": "你如何看待老番（2010年之前的作品）？",
            "options": [
                {"text": "很多经典，值得挖掘", "mapping": {"values": {"tradition": 0.2}, "big_five": {"O": 0.2}}},
                {"text": "偶尔会看", "mapping": {}},
                {"text": "不太看，画风接受不了", "mapping": {"meaning_type": "experiential"}},
                {"text": "完全不看", "mapping": {"big_five": {"O": -0.2}}}
            ]
        },
        {
            "id": 43, "type": "single",
            "question": "你对冷门佳作的看法是？",
            "options": [
                {"text": "很喜欢挖掘冷门作品", "mapping": {"big_five": {"O": 0.3}, "archetype": "explorer"}},
                {"text": "偶尔会看", "mapping": {}},
                {"text": "更看热门作品", "mapping": {"big_five": {"O": -0.1}}},
                {"text": "无所谓", "mapping": {}}
            ]
        },
        {
            "id": 44, "type": "single",
            "question": "你希望推荐系统给你推荐什么？",
            "options": [
                {"text": "和我口味相似的", "mapping": {"regulatory": "prevention", "defense": ["isolation"]}},
                {"text": "我可能喜欢但没发现的", "mapping": {"big_five": {"O": 0.3}, "archetype": "explorer"}},
                {"text": "评分高的经典作品", "mapping": {"values": {"achievement": 0.2}}},
                {"text": "多样化的推荐", "mapping": {"big_five": {"O": 0.2}}}
            ]
        },
        {
            "id": 45, "type": "single",
            "question": "你对剧场版的态度是？",
            "options": [
                {"text": "喜欢，制作更精良", "mapping": {"meaning_type": "experiential"}},
                {"text": "看情况", "mapping": {}},
                {"text": "更喜欢TV版", "mapping": {}},
                {"text": "无所谓", "mapping": {}}
            ]
        },
        {
            "id": 46, "type": "single",
            "question": "你对原作党和动画党的看法是？",
            "options": [
                {"text": "原作更好", "mapping": {"values": {"tradition": 0.2}}},
                {"text": "动画有动画的好", "mapping": {"meaning_type": "experiential"}},
                {"text": "两者都看", "mapping": {"big_five": {"O": 0.1}}},
                {"text": "无所谓", "mapping": {}}
            ]
        },
        {
            "id": 47, "type": "single",
            "question": "你对二创和同人的态度是？",
            "options": [
                {"text": "很喜欢", "mapping": {"big_five": {"O": 0.3}, "archetype": "creator"}},
                {"text": "偶尔会看", "mapping": {}},
                {"text": "不太关注", "mapping": {}},
                {"text": "完全不关注", "mapping": {"big_five": {"O": -0.1}}}
            ]
        },
        {
            "id": 48, "type": "single",
            "question": "你更喜欢看单元剧还是连续剧？",
            "options": [
                {"text": "单元剧，每集独立", "mapping": {"big_five": {"C": 0.1}, "defense": ["isolation"]}},
                {"text": "连续剧，有完整剧情线", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "两者结合", "mapping": {}},
                {"text": "无所谓", "mapping": {}}
            ]
        },
        {
            "id": 49, "type": "single",
            "question": "你对伏笔和回收的看法是？",
            "options": [
                {"text": "非常喜欢，体现作者功力", "mapping": {"big_five": {"C": 0.3}, "cognitive": ["Ni", "Ti"]}},
                {"text": "喜欢，但不要太复杂", "mapping": {"big_five": {"C": 0.1}}},
                {"text": "不太在意", "mapping": {}},
                {"text": "完全不在意", "mapping": {"big_five": {"C": -0.1}}}
            ]
        },
        {
            "id": 50, "type": "single",
            "question": "你对内心独白的看法是？",
            "options": [
                {"text": "喜欢，能深入理解角色", "mapping": {"big_five": {"N": 0.2}, "cognitive": ["Fi", "Ni"]}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢", "mapping": {"big_five": {"E": 0.1}}},
                {"text": "完全不喜欢", "mapping": {"big_five": {"E": 0.2}}}
            ]
        },
        {
            "id": 51, "type": "single",
            "question": "你更喜欢看什么样的对话？",
            "options": [
                {"text": "深度对话，充满哲理", "mapping": {"archetype": "sage", "cognitive": ["Ti", "Ni"]}},
                {"text": "幽默对话，轻松有趣", "mapping": {"archetype": "jester", "big_five": {"E": 0.2}}},
                {"text": "自然对话，贴近生活", "mapping": {"archetype": "everyman", "big_five": {"A": 0.2}}},
                {"text": "热血对话，充满激情", "mapping": {"archetype": "hero", "defense": ["sublimation"]}}
            ]
        },
        {
            "id": 52, "type": "single",
            "question": "你对番剧中的哲理台词怎么看？",
            "options": [
                {"text": "非常喜欢，能引发思考", "mapping": {"archetype": "sage", "big_five": {"O": 0.3}, "meaning_type": "attitudinal"}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太说教", "mapping": {"big_five": {"E": 0.1}}},
                {"text": "完全不喜欢", "mapping": {"defense": ["isolation"]}}
            ]
        },
        {
            "id": 53, "type": "single",
            "question": "你对番剧中的搞笑元素怎么看？",
            "options": [
                {"text": "非常重要，能调节气氛", "mapping": {"archetype": "jester", "big_five": {"E": 0.3}, "defense": ["isolation"]}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，影响严肃性", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "完全不喜欢搞笑", "mapping": {"big_five": {"N": 0.2}}}
            ]
        },
        {
            "id": 54, "type": "single",
            "question": "你对番剧中的热血元素怎么看？",
            "options": [
                {"text": "非常喜欢，能激发斗志", "mapping": {"archetype": "hero", "defense": ["sublimation"], "big_five": {"E": 0.3}}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太中二", "mapping": {"big_five": {"C": 0.2}}},
                {"text": "完全不喜欢", "mapping": {"defense": ["intellectualization"]}}
            ]
        },
        {
            "id": 55, "type": "single",
            "question": "你对番剧中的治愈元素怎么看？",
            "options": [
                {"text": "非常喜欢，能放松心情", "mapping": {"archetype": "innocent", "big_five": {"A": 0.3, "N": -0.3}, "defense": ["isolation"]}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太慢节奏", "mapping": {"big_five": {"E": 0.2}}},
                {"text": "完全不喜欢", "mapping": {"big_five": {"N": 0.2}}}
            ]
        },
        {
            "id": 56, "type": "single",
            "question": "你对番剧中的悬疑元素怎么看？",
            "options": [
                {"text": "非常喜欢，喜欢烧脑", "mapping": {"archetype": "sage", "cognitive": ["Ti", "Ni"], "defense": ["intellectualization"]}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太累", "mapping": {"big_five": {"E": 0.1}}},
                {"text": "完全不喜欢", "mapping": {"defense": ["isolation"]}}
            ]
        },
        {
            "id": 57, "type": "single",
            "question": "你对番剧中的科幻元素怎么看？",
            "options": [
                {"text": "非常喜欢，喜欢未来感", "mapping": {"cognitive": ["Ti", "Ne"], "big_five": {"O": 0.3}, "worldview": "dystopian"}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太复杂", "mapping": {}},
                {"text": "完全不喜欢", "mapping": {"values": {"tradition": 0.2}}}
            ]
        },
        {
            "id": 58, "type": "single",
            "question": "你对番剧中的奇幻元素怎么看？",
            "options": [
                {"text": "非常喜欢，喜欢魔法世界", "mapping": {"worldview": "magical_world", "archetype": "magician", "big_five": {"O": 0.3}}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太假", "mapping": {"worldview": "just_world"}},
                {"text": "完全不喜欢", "mapping": {"big_five": {"C": 0.2}}}
            ]
        },
        {
            "id": 59, "type": "single",
            "question": "你对番剧中的日常元素怎么看？",
            "options": [
                {"text": "非常喜欢，喜欢平淡真实", "mapping": {"archetype": "everyman", "big_five": {"A": 0.3}, "defense": ["isolation"]}},
                {"text": "适量就好", "mapping": {}},
                {"text": "不太喜欢，太平淡", "mapping": {"big_five": {"E": 0.2}}},
                {"text": "完全不喜欢", "mapping": {"big_five": {"N": 0.2}}}
            ]
        },
        {
            "id": 60, "type": "single",
            "question": "你希望通过看番获得什么？",
            "options": [
                {"text": "放松和娱乐", "mapping": {"defense": ["isolation"], "archetype": "jester"}},
                {"text": "情感体验", "mapping": {"big_five": {"N": 0.2}, "emotion_regulation": ["rumination"]}},
                {"text": "思考和启发", "mapping": {"archetype": "sage", "meaning_type": "attitudinal"}},
                {"text": "审美享受", "mapping": {"meaning_type": "experiential", "big_five": {"O": 0.2}}}
            ]
        },
    ]
}


# ============================================================
# 问答处理器
# ============================================================
class QuizProcessor:
    """问答处理器 - 将答题结果转换为心理画像"""

    def __init__(self):
        pass

    def process_quiz(self, answers: list, mode: str = "simple") -> dict:
        """处理答题结果，生成心理画像

        参数：
            answers: [{"question_id": int, "answer": int/list/int}, ...]
            mode: "simple" 或 "complex"

        返回：
            {
                "profile": ComprehensivePsychProfile,
                "profile_dict": dict,
                "reasoning": str,
                "tags": list,  # 推荐的标签
            }
        """
        # 选择题库
        quiz = SIMPLE_QUIZ if mode == "simple" else COMPLEX_QUIZ
        questions = {q["id"]: q for q in quiz["questions"]}

        # 初始化累积权重
        accumulated = self._init_accumulated()

        # 处理每个答案
        for answer in answers:
            qid = answer.get("question_id")
            ans = answer.get("answer")

            if qid not in questions:
                continue

            q = questions[qid]

            if q["type"] == "single":
                self._process_single(q, ans, accumulated)
            elif q["type"] == "scale":
                self._process_scale(q, ans, accumulated)
            elif q["type"] == "multi":
                self._process_multi(q, ans, accumulated)

        # 从累积权重生成心理画像
        profile = self._build_profile_from_accumulated(accumulated)

        # 生成推荐标签
        tags = self._generate_recommendation_tags(profile)

        # 生成解读
        reasoning = self._generate_reasoning(profile, mode)

        return {
            "profile": profile,
            "profile_dict": profile.to_dict(),
            "reasoning": reasoning,
            "tags": tags,
        }

    def _init_accumulated(self) -> dict:
        """初始化累积权重"""
        return {
            "big_five": {"O": 0.5, "C": 0.5, "E": 0.5, "A": 0.5, "N": 0.5},
            "archetype": {},
            "defense": {},
            "sdt": {"autonomy": 0.33, "competence": 0.33, "relatedness": 0.34},
            "narrative": {},
            "worldview": {},
            "moral": {},
            "cognitive": {},
            "attachment": {},
            "achievement": {},
            "regulatory": {},
            "values": {},
            "meaning_type": {},
            "character_id": {},
            "object_relations": {},
            "emotion_regulation": {},
            "self_object": {},
            "personal_constructs": {},
            "social_identity": {},
            "existential": {},
        }

    def _process_single(self, question: dict, answer_idx: int, accumulated: dict):
        """处理单选题"""
        options = question.get("options", [])
        if answer_idx < 0 or answer_idx >= len(options):
            return

        mapping = options[answer_idx].get("mapping", {})
        self._apply_mapping(mapping, accumulated)

    def _process_scale(self, question: dict, answer_value: int, accumulated: dict):
        """处理量表题"""
        dimension = question.get("dimension", {})
        # answer_value 应该是 1-5
        idx = max(0, min(4, answer_value - 1))

        for dim_type, dim_values in dimension.items():
            if dim_type not in accumulated:
                accumulated[dim_type] = {}

            for dim_name, values in dim_values.items():
                if isinstance(values, list) and len(values) > idx:
                    if dim_name in accumulated[dim_type]:
                        accumulated[dim_type][dim_name] += values[idx]
                    else:
                        accumulated[dim_type][dim_name] = values[idx]

    def _process_multi(self, question: dict, answer_indices: list, accumulated: dict):
        """处理多选题"""
        options = question.get("options", [])
        for idx in answer_indices:
            if 0 <= idx < len(options):
                mapping = options[idx].get("mapping", {})
                # 多选题的权重减半
                self._apply_mapping(mapping, accumulated, weight=0.5)

    def _apply_mapping(self, mapping: dict, accumulated: dict, weight: float = 1.0):
        """应用映射到累积权重"""
        for key, value in mapping.items():
            if key not in accumulated:
                accumulated[key] = {}

            if isinstance(value, dict):
                # 嵌套字典，如 big_five, sdt
                if key not in accumulated:
                    accumulated[key] = {}
                for sub_key, sub_value in value.items():
                    if sub_key in accumulated[key]:
                        accumulated[key][sub_key] += sub_value * weight
                    else:
                        accumulated[key][sub_key] = sub_value * weight
            elif isinstance(value, list):
                # 列表，如 defense, cognitive
                for item in value:
                    if item in accumulated[key]:
                        accumulated[key][item] += 1 * weight
                    else:
                        accumulated[key][item] = 1 * weight
            elif isinstance(value, str):
                # 字符串，如 archetype, narrative
                if value in accumulated[key]:
                    accumulated[key][value] += 1 * weight
                else:
                    accumulated[key][value] = 1 * weight

    def _build_profile_from_accumulated(self, accumulated: dict) -> ComprehensivePsychProfile:
        """从累积权重构建心理画像"""
        profile = ComprehensivePsychProfile()

        # 大五人格
        profile.big_five = {
            dim: max(0.0, min(1.0, accumulated["big_five"].get(dim, 0.5)))
            for dim in ["O", "C", "E", "A", "N"]
        }

        # 原型
        if accumulated["archetype"]:
            profile.archetype = max(accumulated["archetype"], key=accumulated["archetype"].get)
        else:
            profile.archetype = "everyman"

        # 防御机制
        profile.defense_mechanisms = sorted(
            accumulated["defense"].items(), key=lambda x: -x[1]
        )
        profile.defense_mechanisms = [m for m, _ in profile.defense_mechanisms]

        # SDT需求
        sdt_total = sum(accumulated["sdt"].values())
        if sdt_total > 0:
            profile.sdt_needs = {k: v / sdt_total for k, v in accumulated["sdt"].items()}

        # 叙事类型
        if accumulated["narrative"]:
            profile.narrative_type = max(accumulated["narrative"], key=accumulated["narrative"].get)
        else:
            profile.narrative_type = "progressive"

        # 世界观
        if accumulated["worldview"]:
            profile.worldview = max(accumulated["worldview"], key=accumulated["worldview"].get)
        else:
            profile.worldview = "just_world"

        # 道德基础
        profile.moral_foundations = sorted(
            accumulated["moral"].items(), key=lambda x: -x[1]
        )
        profile.moral_foundations = [m for m, _ in profile.moral_foundations]

        # 认知功能
        if accumulated["cognitive"]:
            sorted_cog = sorted(accumulated["cognitive"].items(), key=lambda x: -x[1])
            profile.cognitive_functions = [c for c, _ in sorted_cog[:4]]

        # 依恋类型
        if accumulated["attachment"]:
            profile.attachment = max(accumulated["attachment"], key=accumulated["attachment"].get)
        else:
            profile.attachment = "secure"

        # 成就动机
        if accumulated["achievement"]:
            profile.achievement_type = max(accumulated["achievement"], key=accumulated["achievement"].get)
        else:
            profile.achievement_type = "mastery"

        # 调节焦点
        if accumulated["regulatory"]:
            profile.regulatory_focus = max(accumulated["regulatory"], key=accumulated["regulatory"].get)
        else:
            profile.regulatory_focus = "promotion"

        # 意义类型
        if accumulated["meaning_type"]:
            profile.meaning_type = max(accumulated["meaning_type"], key=accumulated["meaning_type"].get)
        else:
            profile.meaning_type = "experiential"

        # 角色认同
        if accumulated["character_id"]:
            profile.character_identification = max(accumulated["character_id"], key=accumulated["character_id"].get)
        else:
            profile.character_identification = "self_real"

        # 客体关系
        if accumulated["object_relations"]:
            profile.object_relations = max(accumulated["object_relations"], key=accumulated["object_relations"].get)
        else:
            profile.object_relations = "integration"

        # 情绪调节
        profile.emotion_regulation = sorted(
            accumulated["emotion_regulation"].items(), key=lambda x: -x[1]
        )
        profile.emotion_regulation = [e for e, _ in profile.emotion_regulation]

        # 自体客体需求
        profile.self_object_needs = sorted(
            accumulated["self_object"].items(), key=lambda x: -x[1]
        )
        profile.self_object_needs = [s for s, _ in profile.self_object_needs]

        # 个人建构
        profile.personal_constructs = sorted(
            accumulated["personal_constructs"].items(), key=lambda x: -x[1]
        )
        profile.personal_constructs = [p for p, _ in profile.personal_constructs]

        # 社会认同
        if accumulated["social_identity"]:
            profile.social_identity = max(accumulated["social_identity"], key=accumulated["social_identity"].get)
        else:
            profile.social_identity = "in_group"

        # 存在主义关怀
        profile.existential_concerns = sorted(
            accumulated["existential"].items(), key=lambda x: -x[1]
        )
        profile.existential_concerns = [e for e, _ in profile.existential_concerns]

        return profile

    def _generate_recommendation_tags(self, profile: ComprehensivePsychProfile) -> list:
        """基于心理画像生成推荐标签"""
        tags = set()

        # 基于原型
        archetype_tags = {
            "hero": ["Action", "Sports", "Adventure"],
            "sage": ["Mystery", "Sci-Fi", "Psychological"],
            "explorer": ["Adventure", "Isekai", "Fantasy"],
            "caregiver": ["Healing", "Slice of Life", "Family"],
            "lover": ["Romance", "Drama"],
            "jester": ["Comedy", "Slice of Life"],
            "orphan": ["Drama", "School", "Coming-of-Age"],
            "creator": ["Music", "Art"],
        }
        if profile.archetype in archetype_tags:
            tags.update(archetype_tags[profile.archetype])

        # 基于防御机制
        defense_tags = {
            "sublimation": ["Action", "Sports"],
            "dissociation": ["Isekai", "Fantasy"],
            "intellectualization": ["Mystery", "Sci-Fi"],
            "fantasy": ["Fantasy", "Magic"],
            "isolation": ["Slice of Life", "Healing"],
        }
        for defense in profile.defense_mechanisms[:2]:
            if defense in defense_tags:
                tags.update(defense_tags[defense])

        # 基于叙事类型
        narrative_tags = {
            "progressive": ["Coming-of-Age", "Growth"],
            "redemption": ["Drama", "Psychological"],
            "exploration": ["Adventure", "Fantasy"],
            "stability": ["Slice of Life", "Daily Life"],
        }
        if profile.narrative_type in narrative_tags:
            tags.update(narrative_tags[profile.narrative_type])

        return list(tags)[:10]

    def _generate_reasoning(self, profile: ComprehensivePsychProfile, mode: str) -> str:
        """生成问答结果解读"""
        parts = []

        if mode == "simple":
            parts.append("=== 快速心理画像测试结果 ===")
        else:
            parts.append("=== 深度心理画像测试结果 ===")

        parts.append("")
        parts.append(profile._generate_reasoning())
        parts.append("")

        # 添加推荐方向
        direction = profile.get_recommendation_direction()
        if direction.get("primary_need"):
            parts.append(f"你的核心需求：{direction['primary_need']}")
        if direction.get("secondary_need"):
            parts.append(f"次要需求：{direction['secondary_need']}")

        return "\n".join(parts)


# ============================================================
# 测试入口
# ============================================================
if __name__ == "__main__":
    processor = QuizProcessor()

    # 模拟简易版答题
    simple_answers = [
        {"question_id": 1, "answer": 0},  # 深度思考
        {"question_id": 2, "answer": 0},  # 成长结局
        {"question_id": 3, "answer": 0},  # 勇者
        {"question_id": 4, "answer": 0},  # 坚强角色
        {"question_id": 5, "answer": 1},  # 剧本深度
        {"question_id": 6, "answer": 0},  # 热血释放
        {"question_id": 7, "answer": 0},  # 逃离现实
        {"question_id": 8, "answer": 0},  # 羁绊
        {"question_id": 9, "answer": 0},  # 喜欢虐心
        {"question_id": 10, "answer": 1}, # 努力变强
        {"question_id": 11, "answer": 0}, # 魔法世界
        {"question_id": 12, "answer": 0}, # 竞技体育
        {"question_id": 13, "answer": 0}, # 正面对决
        {"question_id": 14, "answer": 0}, # 喜欢恋爱
        {"question_id": 15, "answer": 0}, # 现代
        {"question_id": 16, "answer": 0}, # 自由
        {"question_id": 17, "answer": 0}, # 挺身而出
        {"question_id": 18, "answer": 0}, # 挑战冒险
        {"question_id": 19, "answer": 0}, # 思考启发
        {"question_id": 20, "answer": 0}, # 深刻
    ]

    result = processor.process_quiz(simple_answers, mode="simple")
    print(result["reasoning"])
    print()
    print("推荐标签:", result["tags"])

