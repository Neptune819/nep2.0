"""
psych_profile.py
=================
基于一部番剧推断用户完整心理画像的系统

24个心理维度，按依赖顺序执行：
  第一层（人格）：big_five, mbti, enneagram, cognitive_functions
  第二层（需求）：maslow, sdt, regulatory_focus, achievement, existential, meaning
  第三层（情感）：attachment, emotion_regulation, defense, self_object, object_relations
  第四层（叙事）：archetype, narrative, hero_journey, character_id, worldview
  第五层（价值）：values, moral, social_identity, personal_constructs
"""

# ============================================================
# R18标签过滤列表
# ============================================================
# 这些标签会被过滤掉，不会用于心理画像分析
R18_TAGS = {
    # 性行为相关（英文）
    "Ecchi", "Hentai", "Erotica", "Sexual Content",
    "Nudity", "Fan Service", "Sexual Themes",
    "Adult Cast", "Mature",
    "Oral Sex", "Vaginal Sex", "Anal Sex", "Masturbation",
    "Group Sex", "Threesome", "Gangbang",
    "Incest", "Rape", "Sexual Abuse",
    
    # 性行为相关（简体中文）
    "口交", "中出", "强奸", "强奷", "性行为", "性交", "做爱",
    "肛交", "乳交", "足交", "手交", "舔阴", "口爆", "颜射",
    "群交", "轮奸", "迷奸",
    
    # 性行为相关（繁体中文）
    "強姦", "強暴", "性行為", "性交", "做愛",
    "肛交", "乳交", "足交", "手交", "舔陰", "口爆", "顏射",
    "群交", "輪姦", "迷姦",
    
    # 色情相关
    "色情", "成人", "R18", "限制级", "裸露", "性暗示", "擦边",
    "巨乳", "爆乳", "贫乳", "美乳", "胸部",
    "臀部", "屁股", "肥臀",
    "内裤", "胖次", "情趣内衣",
    "调教", "SM", "捆绑", "束缚",
    
    # 暴力/血腥（极端）
    "Gore", "Extreme Violence", "Graphic Violence",
    "Torture", "Body Horror",
    "血腥", "极端暴力", "酷刑", "肢解",
    
    # 其他敏感内容
    "Drug Use", "Substance Abuse",
    "毒品", "药物滥用",
}

# ============================================================
# 番剧特征到心理维度的映射表
# ============================================================

# 标签 → 心理特征的映射
TAG_TO_PSYCH = {
    # ========= 动作/战斗类 =========
    "Action": {
        "big_five": {"E": 0.3, "N": 0.2, "A": -0.1},
        "defense": ["sublimation", "displacement"],
        "sdt": {"competence": 0.4},
        "archetype": "hero",
        "moral": ["care_harm"],
    },
    "Combat": {
        "big_five": {"E": 0.3, "C": 0.1},
        "defense": ["sublimation", "displacement"],
        "sdt": {"competence": 0.5},
        "archetype": "hero",
        "regulatory": "promotion",
    },
    "Martial Arts": {
        "big_five": {"C": 0.3, "E": 0.2},
        "sdt": {"competence": 0.6, "autonomy": 0.2},
        "achievement": "mastery",
        "archetype": "hero",
    },
    "Military": {
        "big_five": {"C": 0.4, "E": 0.1},
        "values": {"conformity": 0.4, "security": 0.3},
        "moral": ["loyalty_betrayal", "authority_subversion"],
    },
    "Samurai": {
        "big_five": {"C": 0.3, "O": 0.2},
        "values": {"tradition": 0.4, "achievement": 0.3},
        "archetype": "hero",
    },
    "Survival": {
        "big_five": {"N": 0.4, "C": 0.3},
        "existential": ["death"],
        "defense": ["sublimation"],
        "archetype": "hero",
    },

    # ========= 冒险类 =========
    "Adventure": {
        "big_five": {"O": 0.4, "E": 0.3},
        "archetype": "explorer",
        "sdt": {"autonomy": 0.5},
        "narrative": "exploration",
    },
    "Exploration": {
        "big_five": {"O": 0.5},
        "archetype": "explorer",
        "sdt": {"autonomy": 0.6},
        "hero_journey": "departure",
    },
    "Quest": {
        "big_five": {"C": 0.3, "O": 0.3},
        "archetype": "hero",
        "hero_journey": "initiation",
        "achievement": "mastery",
    },
    "Travel": {
        "big_five": {"O": 0.4, "E": 0.2},
        "archetype": "explorer",
        "sdt": {"autonomy": 0.5},
    },
    "Isekai": {
        "big_five": {"O": 0.5, "N": 0.2},
        "defense": ["dissociation", "fantasy"],
        "archetype": "explorer",
        "worldview": "magical_world",
        "self_object": ["mirroring"],
    },

    # ========= 悬疑/推理类 =========
    "Mystery": {
        "big_five": {"O": 0.3, "C": 0.3},
        "cognitive": ["Ni", "Ti"],
        "defense": ["intellectualization"],
        "archetype": "sage",
        "mbti_weight": {"INTJ": 0.3, "INTP": 0.3, "INFJ": 0.2},
    },
    "Detective": {
        "big_five": {"C": 0.4, "O": 0.2},
        "cognitive": ["Ti", "Te"],
        "defense": ["intellectualization"],
        "archetype": "sage",
        "moral": ["fairness_cheating"],
    },
    "Psychological": {
        "big_five": {"N": 0.5, "O": 0.4},
        "cognitive": ["Ni", "Fi"],
        "defense": ["intellectualization", "projection"],
        "archetype": "sage",
        "existential": ["meaninglessness", "freedom"],
        "emotion_regulation": ["rumination"],
        "object_relations": "splitting",
    },
    "Thriller": {
        "big_five": {"N": 0.4, "E": 0.2},
        "defense": ["sublimation"],
        "emotion_regulation": ["suppression"],
        "moral": ["care_harm"],
    },
    "Mind Game": {
        "big_five": {"O": 0.5, "N": 0.3},
        "cognitive": ["Ni", "Ne", "Ti"],
        "defense": ["intellectualization"],
        "personal_constructs": ["complexity"],
    },
    "Plot Twist": {
        "big_five": {"O": 0.4},
        "cognitive": ["Ne", "Ni"],
        "personal_constructs": ["flexibility"],
    },

    # ========= 科幻类 =========
    "Sci-Fi": {
        "big_five": {"O": 0.5, "C": 0.2},
        "cognitive": ["Ti", "Ne"],
        "archetype": "sage",
        "worldview": "unjust_world",
        "mbti_weight": {"INTP": 0.4, "INTJ": 0.3},
    },
    "Mecha": {
        "big_five": {"C": 0.3, "E": 0.2},
        "cognitive": ["Te", "Se"],
        "defense": ["sublimation"],
        "values": {"achievement": 0.3, "power": 0.2},
    },
    "Space": {
        "big_five": {"O": 0.5},
        "archetype": "explorer",
        "existential": ["isolation", "meaninglessness"],
    },
    "Cyberpunk": {
        "big_five": {"O": 0.4, "N": 0.3},
        "archetype": "outlaw",
        "worldview": "dystopian",
        "moral": ["liberty_oppression"],
    },
    "Time Manipulation": {
        "big_five": {"O": 0.5, "C": 0.3},
        "cognitive": ["Ni", "Ti"],
        "existential": ["freedom", "meaninglessness"],
    },

    # ========= 奇幻类 =========
    "Fantasy": {
        "big_five": {"O": 0.5},
        "archetype": "magician",
        "defense": ["fantasy"],
        "worldview": "magical_world",
    },
    "Magic": {
        "big_five": {"O": 0.5},
        "archetype": "magician",
        "defense": ["fantasy"],
        "sdt": {"competence": 0.3},
    },
    "Supernatural": {
        "big_five": {"O": 0.4, "N": 0.2},
        "archetype": "magician",
        "worldview": "magical_world",
    },
    "Mythology": {
        "big_five": {"O": 0.4},
        "values": {"tradition": 0.4},
        "archetype": "sage",
    },
    "Super Power": {
        "big_five": {"E": 0.3, "O": 0.3},
        "defense": ["fantasy", "identification"],
        "self_object": ["mirroring"],
        "sdt": {"competence": 0.5},
    },
    "Vampire": {
        "big_five": {"O": 0.3, "N": 0.3},
        "archetype": ["lover", "outlaw"],
        "moral": ["sanctity_degradation"],
    },
    "Demons": {
        "big_five": {"N": 0.4, "O": 0.3},
        "archetype": "outlaw",
        "moral": ["sanctity_degradation"],
        "defense": ["projection"],
    },
    "Ghosts": {
        "big_five": {"N": 0.3, "O": 0.3},
        "existential": ["death"],
        "defense": ["projection"],
    },

    # ========= 治愈/日常类 =========
    "Slice of Life": {
        "big_five": {"A": 0.4, "N": -0.3},
        "archetype": ["everyman", "innocent"],
        "defense": ["isolation", "denial"],
        "emotion_regulation": ["acceptance"],
        "object_relations": "containment",
    },
    "Healing": {
        "big_five": {"A": 0.5, "N": -0.4},
        "archetype": "caregiver",
        "defense": ["sublimation"],
        "emotion_regulation": ["acceptance"],
        "attachment": "secure",
        "self_object": ["mirroring", "twinship"],
    },
    "Iyashikei": {
        "big_five": {"A": 0.5, "N": -0.5, "E": -0.3},
        "archetype": "innocent",
        "defense": ["isolation"],
        "emotion_regulation": ["acceptance"],
        "maslow": 2,  # 安全需求
    },
    "Cute Girls Doing Cute Things": {
        "big_five": {"A": 0.4, "E": 0.1, "N": -0.3},
        "archetype": "innocent",
        "defense": ["regression"],
        "self_object": ["twinship"],
    },
    "Daily Life": {
        "big_five": {"A": 0.3, "C": 0.2},
        "archetype": "everyman",
        "defense": ["isolation"],
        "narrative": "stability",
    },

    # ========= 搞笑类 =========
    "Comedy": {
        "big_five": {"E": 0.4, "A": 0.3, "N": -0.3},
        "archetype": "jester",
        "defense": ["isolation", "displacement"],
        "emotion_regulation": ["reappraisal"],
    },
    "Parody": {
        "big_five": {"O": 0.3, "E": 0.2},
        "archetype": "jester",
        "defense": ["isolation"],
        "personal_constructs": ["flexibility"],
    },
    "Satire": {
        "big_five": {"O": 0.4, "A": -0.1},
        "cognitive": ["Ti", "Ne"],
        "archetype": "jester",
        "moral": ["fairness_cheating"],
    },
    "Slapstick": {
        "big_five": {"E": 0.5, "N": -0.4},
        "archetype": "jester",
        "defense": ["displacement"],
    },
    "Absurd Humor": {
        "big_five": {"O": 0.5, "E": 0.3},
        "archetype": ["jester", "fool"],
        "personal_constructs": ["flexibility"],
    },

    # ========= 恋爱类 =========
    "Romance": {
        "big_five": {"A": 0.3, "E": 0.2},
        "archetype": "lover",
        "sdt": {"relatedness": 0.6},
        "self_object": ["mirroring", "twinship"],
    },
    "Love Triangle": {
        "big_five": {"N": 0.3, "A": 0.1},
        "attachment": "anxious_preoccupied",
        "defense": ["projection"],
        "emotion_regulation": ["rumination"],
    },
    "Romantic Comedy": {
        "big_five": {"E": 0.3, "A": 0.4, "N": -0.2},
        "archetype": ["lover", "jester"],
        "attachment": "secure",
        "defense": ["reaction_formation"],
    },
    "Tragic Romance": {
        "big_five": {"N": 0.5, "O": 0.3},
        "attachment": "fearful_avoidant",
        "narrative": "contamination",
        "existential": ["death", "meaninglessness"],
    },
    "Harem": {
        "big_five": {"E": 0.2, "A": 0.1},
        "defense": ["fantasy"],
        "self_object": ["mirroring"],
        "attachment": "anxious_preoccupied",
    },
    "Reverse Harem": {
        "big_five": {"E": 0.2, "A": 0.2},
        "defense": ["fantasy"],
        "self_object": ["mirroring"],
    },
    "Yuri": {
        "big_five": {"O": 0.3, "A": 0.3},
        "archetype": "lover",
        "values": {"benevolence": 0.3},
    },
    "Boys Love": {
        "big_five": {"O": 0.3, "A": 0.3},
        "archetype": "lover",
        "values": {"benevolence": 0.3},
    },

    # ========= 学园类 =========
    "School": {
        "big_five": {"E": 0.2, "A": 0.2},
        "archetype": "everyman",
        "sdt": {"relatedness": 0.4},
        "social_identity": "in_group",
    },
    "Club": {
        "big_five": {"E": 0.3, "A": 0.3},
        "sdt": {"relatedness": 0.5},
        "social_identity": "in_group",
        "moral": ["loyalty_betrayal"],
    },
    "High School": {
        "big_five": {"E": 0.2, "N": 0.1},
        "archetype": "orphan",
        "sdt": {"relatedness": 0.4},
    },
    "University": {
        "big_five": {"O": 0.2, "C": 0.2},
        "archetype": "seeker",
    },

    # ========= 音乐类 =========
    "Music": {
        "big_five": {"O": 0.4, "E": 0.2},
        "archetype": "creator",
        "emotion_regulation": ["reappraisal"],
        "meaning_type": "experiential",
    },
    "Idol": {
        "big_five": {"E": 0.4, "A": 0.3},
        "archetype": "creator",
        "self_object": ["mirroring"],
        "achievement": "performance",
    },
    "Band": {
        "big_five": {"O": 0.3, "E": 0.3},
        "archetype": ["creator", "everyman"],
        "sdt": {"relatedness": 0.5},
    },
    "Performance": {
        "big_five": {"E": 0.4, "O": 0.3},
        "archetype": "creator",
        "achievement": "performance",
    },

    # ========= 体育/竞技类 =========
    "Sports": {
        "big_five": {"E": 0.4, "C": 0.3},
        "defense": ["sublimation"],
        "sdt": {"competence": 0.6},
        "achievement": "mastery",
        "archetype": "hero",
        "moral": ["loyalty_betrayal"],
    },
    "Competition": {
        "big_five": {"E": 0.3, "C": 0.3},
        "sdt": {"competence": 0.5},
        "achievement": "performance",
        "regulatory": "promotion",
    },
    "Racing": {
        "big_five": {"E": 0.4, "C": 0.3},
        "defense": ["sublimation"],
        "sdt": {"competence": 0.4, "autonomy": 0.3},
    },
    "Game": {
        "big_five": {"C": 0.4, "O": 0.3},
        "cognitive": ["Ti", "Ni"],
        "sdt": {"competence": 0.6},
        "defense": ["intellectualization"],
    },
    "Strategy Game": {
        "big_five": {"C": 0.5, "O": 0.3},
        "cognitive": ["Te", "Ni"],
        "archetype": "ruler",
        "mbti_weight": {"INTJ": 0.5, "ENTJ": 0.3},
    },

    # ========= 职场类 =========
    "Work": {
        "big_five": {"C": 0.4, "E": 0.1},
        "maslow": 4,  # 尊重需求
        "achievement": "mastery",
        "values": {"achievement": 0.4},
    },
    "Office": {
        "big_five": {"C": 0.3, "A": 0.2},
        "archetype": "everyman",
        "defense": ["intellectualization"],
    },
    "Business": {
        "big_five": {"C": 0.4, "E": 0.2},
        "archetype": "ruler",
        "values": {"achievement": 0.5, "power": 0.3},
    },

    # ========= 历史/战争类 =========
    "Historical": {
        "big_five": {"O": 0.3, "C": 0.2},
        "values": {"tradition": 0.5},
        "archetype": "sage",
    },
    "War": {
        "big_five": {"N": 0.3, "C": 0.2},
        "existential": ["death", "freedom"],
        "moral": ["loyalty_betrayal", "care_harm"],
        "defense": ["sublimation"],
    },
    "Political": {
        "big_five": {"C": 0.3, "E": 0.1},
        "cognitive": ["Te", "Ni"],
        "archetype": "ruler",
        "moral": ["authority_subversion", "liberty_oppression"],
    },

    # ========= 美食类 =========
    "Cooking": {
        "big_five": {"A": 0.3, "C": 0.3},
        "archetype": "caregiver",
        "sdt": {"competence": 0.3},
        "meaning_type": "creative",
    },
    "Gourmet": {
        "big_five": {"O": 0.3, "A": 0.2},
        "archetype": "sage",
        "meaning_type": "experiential",
    },

    # ========= 萌/后宫类 =========
    "Otaku Culture": {
        "big_five": {"O": 0.3, "E": -0.1},
        "defense": ["fantasy", "identification"],
        "self_object": ["twinship"],
        "social_identity": "in_group",
    },
    "Anthropomorphism": {
        "big_five": {"O": 0.4},
        "defense": ["fantasy"],
        "archetype": "magician",
    },

    # ========= 儿童/家庭类 =========
    "Kids": {
        "big_five": {"A": 0.5, "N": -0.5},
        "archetype": "innocent",
        "defense": ["regression"],
        "attachment": "secure",
    },
    "Family": {
        "big_five": {"A": 0.4, "E": 0.1},
        "archetype": "caregiver",
        "sdt": {"relatedness": 0.6},
        "attachment": "secure",
        "values": {"benevolence": 0.5},
    },
    "Parenting": {
        "big_five": {"A": 0.5, "C": 0.3},
        "archetype": "caregiver",
        "self_object": ["mirroring"],
        "values": {"benevolence": 0.6},
    },

    # ========= 哲学/思想类 =========
    "Philosophical": {
        "big_five": {"O": 0.6, "N": 0.2},
        "cognitive": ["Ni", "Ti"],
        "archetype": "sage",
        "existential": ["meaninglessness", "freedom"],
        "meaning_type": "attitudinal",
        "mbti_weight": {"INFJ": 0.4, "INTJ": 0.3, "INTP": 0.3},
    },
    "Psychology": {
        "big_five": {"O": 0.4, "N": 0.3},
        "cognitive": ["Ni", "Fi"],
        "defense": ["intellectualization"],
        "emotion_regulation": ["rumination"],
    },

    # ========= 黑暗/悲剧类 =========
    "Dark": {
        "big_five": {"N": 0.5, "A": -0.3},
        "archetype": ["outlaw", "destroyer"],
        "defense": ["projection"],
        "worldview": "unjust_world",
        "object_relations": "splitting",
    },
    "Tragedy": {
        "big_five": {"N": 0.5, "O": 0.2},
        "narrative": "contamination",
        "existential": ["death", "meaninglessness"],
        "emotion_regulation": ["rumination"],
    },
    "Horror": {
        "big_five": {"N": 0.5, "O": 0.2},
        "defense": ["sublimation"],
        "existential": ["death"],
        "emotion_regulation": ["suppression"],
    },
    "Gore": {
        "big_five": {"N": 0.6, "A": -0.4},
        "defense": ["displacement", "projection"],
        "moral": ["sanctity_degradation"],
    },
    "Psychopaths": {
        "big_five": {"N": 0.5, "A": -0.5},
        "archetype": "outlaw",
        "defense": ["projection"],
        "object_relations": "splitting",
    },
    "Dystopian": {
        "big_five": {"N": 0.4, "O": 0.3},
        "worldview": "dystopian",
        "moral": ["liberty_oppression"],
        "archetype": "outlaw",
    },

    # ========= 成长/励志类 =========
    "Coming-of-Age": {
        "big_five": {"O": 0.3, "A": 0.2},
        "archetype": "orphan",
        "hero_journey": "initiation",
        "narrative": "progressive",
        "sdt": {"competence": 0.4, "relatedness": 0.3},
    },
    "Growth": {
        "big_five": {"C": 0.3, "O": 0.2},
        "achievement": "mastery",
        "narrative": "progressive",
        "hero_journey": "initiation",
    },
    "Motivational": {
        "big_five": {"E": 0.3, "C": 0.3},
        "archetype": "hero",
        "narrative": "redemption",
        "regulatory": "promotion",
    },

    # ========= 羁绊/友情类 =========
    "Friendship": {
        "big_five": {"A": 0.5, "E": 0.3},
        "sdt": {"relatedness": 0.7},
        "social_identity": "in_group",
        "moral": ["loyalty_betrayal"],
        "self_object": ["twinship"],
    },
    "Bromance": {
        "big_five": {"A": 0.4, "E": 0.3},
        "sdt": {"relatedness": 0.6},
        "archetype": "everyman",
    },
    "Teamwork": {
        "big_five": {"A": 0.4, "C": 0.3},
        "sdt": {"relatedness": 0.5},
        "moral": ["loyalty_betrayal"],
        "social_identity": "in_group",
    },

    # ========= 复仇/正义类 =========
    "Revenge": {
        "big_five": {"N": 0.4, "A": -0.3},
        "archetype": "outlaw",
        "defense": ["displacement"],
        "moral": ["fairness_cheating", "care_harm"],
        "regulatory": "prevention",
    },
    "Justice": {
        "big_five": {"C": 0.3, "A": 0.2},
        "archetype": "hero",
        "moral": ["fairness_cheating"],
        "values": {"universalism": 0.4},
    },
    "Anti-Hero": {
        "big_five": {"N": 0.3, "A": -0.3},
        "archetype": "outlaw",
        "character_id": "anti_hero",
        "moral": ["fairness_cheating"],
        "object_relations": "splitting",
    },

    # ========= 转生/穿越类 =========
    "Reincarnation": {
        "big_five": {"O": 0.4, "N": 0.1},
        "defense": ["fantasy"],
        "archetype": "explorer",
        "narrative": "redemption",
    },
    "Virtual World": {
        "big_five": {"O": 0.4, "N": 0.2},
        "defense": ["dissociation"],
        "archetype": "explorer",
        "worldview": "magical_world",
    },
    "Video Game": {
        "big_five": {"O": 0.3, "C": 0.2},
        "sdt": {"competence": 0.5},
        "defense": ["dissociation"],
    },

    # ========= 机器人/AI类 =========
    "AI": {
        "big_five": {"O": 0.4, "C": 0.3},
        "cognitive": ["Ti", "Ni"],
        "existential": ["meaninglessness"],
        "archetype": "sage",
    },
    "Robot": {
        "big_five": {"C": 0.3, "O": 0.3},
        "cognitive": ["Ti"],
        "existential": ["meaninglessness"],
    },

    # ========= 异能/超自然类 =========
    "Superhero": {
        "big_five": {"E": 0.3, "A": 0.3},
        "archetype": "hero",
        "moral": ["care_harm"],
        "self_object": ["idealizing"],
    },
    "Witchcraft": {
        "big_five": {"O": 0.5},
        "archetype": "magician",
        "defense": ["fantasy"],
    },

    # ========= 末日/废土类 =========
    "Post-Apocalyptic": {
        "big_five": {"N": 0.4, "C": 0.2},
        "existential": ["death", "meaninglessness"],
        "worldview": "dystopian",
        "defense": ["sublimation"],
    },

    # ========= 水族馆/动物类 =========
    "Animal": {
        "big_five": {"A": 0.4, "N": -0.3},
        "archetype": "innocent",
        "defense": ["regression"],
        "emotion_regulation": ["acceptance"],
    },
    "Nature": {
        "big_five": {"O": 0.3, "A": 0.3},
        "archetype": "explorer",
        "meaning_type": "experiential",
    },

    # ========= 补充标签（v2.0） =========
    # 战斗策略
    "Tactical": {
        "big_five": {"C": 0.4, "O": 0.2},
        "cognitive": ["Te", "Ni"],
        "archetype": "ruler",
        "achievement": "mastery",
    },
    "Strategy": {
        "big_five": {"C": 0.5, "O": 0.3},
        "cognitive": ["Te", "Ni"],
        "archetype": "ruler",
        "mbti_weight": {"INTJ": 0.4, "ENTJ": 0.3},
    },
    # 竞技对战
    "Battle Royale": {
        "big_five": {"N": 0.4, "E": 0.3},
        "existential": ["death"],
        "defense": ["sublimation"],
        "archetype": "hero",
    },
    "Tournament": {
        "big_five": {"E": 0.4, "C": 0.3},
        "sdt": {"competence": 0.6},
        "achievement": "performance",
        "archetype": "hero",
    },
    # 悬疑推理补充
    "Whodunit": {
        "big_five": {"C": 0.4, "O": 0.3},
        "cognitive": ["Ti", "Ni"],
        "defense": ["intellectualization"],
        "archetype": "sage",
    },
    "Locked Room Mystery": {
        "big_five": {"C": 0.5, "O": 0.3},
        "cognitive": ["Ti"],
        "defense": ["intellectualization"],
    },
    "Police": {
        "big_five": {"C": 0.4, "E": 0.1},
        "moral": ["fairness_cheating"],
        "values": {"conformity": 0.3, "security": 0.3},
    },
    "Crime": {
        "big_five": {"N": 0.3, "C": 0.2},
        "moral": ["fairness_cheating"],
        "defense": ["projection"],
    },
    # 科幻补充
    "Dystopia": {
        "big_five": {"N": 0.4, "O": 0.3},
        "worldview": "dystopian",
        "moral": ["liberty_oppression"],
        "archetype": "outlaw",
    },
    "Utopia": {
        "big_five": {"O": 0.4, "A": 0.3},
        "worldview": "just_world",
        "values": {"universalism": 0.4},
    },
    "Apaocalyptic": {
        "big_five": {"N": 0.5, "C": 0.2},
        "existential": ["death", "meaninglessness"],
        "worldview": "dystopian",
    },
    "Time Travel": {
        "big_five": {"O": 0.5, "C": 0.3},
        "cognitive": ["Ni", "Ti"],
        "existential": ["freedom"],
    },
    "Parallel World": {
        "big_five": {"O": 0.5},
        "archetype": "explorer",
        "defense": ["fantasy"],
        "worldview": "magical_world",
    },
    # 奇幻补充
    "Fairy Tale": {
        "big_five": {"O": 0.4, "A": 0.3},
        "archetype": "innocent",
        "defense": ["fantasy"],
        "narrative": "progressive",
    },
    "Folklore": {
        "big_five": {"O": 0.3},
        "values": {"tradition": 0.5},
        "archetype": "sage",
    },
    "Dark Fantasy": {
        "big_five": {"N": 0.4, "O": 0.4},
        "archetype": "outlaw",
        "worldview": "unjust_world",
        "defense": ["projection"],
    },
    "High Fantasy": {
        "big_five": {"O": 0.5},
        "archetype": "hero",
        "worldview": "magical_world",
        "narrative": "progressive",
    },
    "Low Fantasy": {
        "big_five": {"O": 0.3, "N": 0.2},
        "archetype": "everyman",
        "defense": ["fantasy"],
    },
    "Sword and Sorcery": {
        "big_five": {"E": 0.3, "O": 0.3},
        "archetype": "hero",
        "defense": ["sublimation"],
    },
    # 日常补充
    "Iyashikei": {
        "big_five": {"A": 0.5, "N": -0.5, "E": -0.3},
        "archetype": "innocent",
        "defense": ["isolation"],
        "emotion_regulation": ["acceptance"],
        "maslow": 2,
    },
    "CGDCT": {
        "big_five": {"A": 0.4, "E": 0.1, "N": -0.3},
        "archetype": "innocent",
        "defense": ["regression"],
        "self_object": ["twinship"],
    },
    "Moe": {
        "big_five": {"A": 0.4, "N": -0.3},
        "defense": ["regression"],
        "self_object": ["mirroring"],
    },
    # 恋爱补充
    "Shoujo": {
        "big_five": {"A": 0.3, "E": 0.2},
        "archetype": "lover",
        "sdt": {"relatedness": 0.5},
    },
    "Shounen": {
        "big_five": {"E": 0.3, "C": 0.2},
        "archetype": "hero",
        "sdt": {"competence": 0.4},
    },
    "Josei": {
        "big_five": {"O": 0.2, "N": 0.2},
        "archetype": "everyman",
        "emotion_regulation": ["rumination"],
    },
    "Seinen": {
        "big_five": {"N": 0.3, "O": 0.2},
        "archetype": "seeker",
        "defense": ["intellectualization"],
    },
    # 身份认同
    "Identity": {
        "big_five": {"O": 0.3, "N": 0.3},
        "archetype": "orphan",
        "existential": ["meaninglessness"],
        "self_object": ["mirroring"],
    },
    "Self-Discovery": {
        "big_five": {"O": 0.4, "N": 0.2},
        "archetype": "explorer",
        "hero_journey": "initiation",
        "narrative": "progressive",
    },
    "Personal Growth": {
        "big_five": {"C": 0.3, "O": 0.2},
        "achievement": "mastery",
        "narrative": "progressive",
        "hero_journey": "initiation",
    },
    # 社会相关
    "Social Commentary": {
        "big_five": {"O": 0.4, "C": 0.2},
        "cognitive": ["Ni", "Ti"],
        "moral": ["fairness_cheating", "liberty_oppression"],
        "archetype": "sage",
    },
    "Class Struggle": {
        "big_five": {"N": 0.3, "O": 0.2},
        "moral": ["fairness_cheating", "liberty_oppression"],
        "worldview": "unjust_world",
    },
    "Bullying": {
        "big_five": {"N": 0.4, "A": -0.2},
        "moral": ["care_harm"],
        "archetype": "orphan",
        "existential": ["isolation"],
    },
    "Redemption": {
        "big_five": {"O": 0.3, "A": 0.2},
        "archetype": "hero",
        "narrative": "redemption",
        "moral": ["care_harm"],
    },
    "Sacrifice": {
        "big_five": {"A": 0.4, "N": 0.2},
        "archetype": "caregiver",
        "moral": ["care_harm"],
        "existential": ["death"],
    },
    "Loyalty": {
        "big_five": {"A": 0.4, "C": 0.3},
        "moral": ["loyalty_betrayal"],
        "sdt": {"relatedness": 0.6},
        "social_identity": "in_group",
    },
    "Betrayal": {
        "big_five": {"N": 0.5, "A": -0.3},
        "moral": ["loyalty_betrayal"],
        "attachment": "fearful_avoidant",
    },
    "Trust": {
        "big_five": {"A": 0.4, "N": -0.2},
        "attachment": "secure",
        "sdt": {"relatedness": 0.5},
    },
    # 战斗风格补充
    "Swordplay": {
        "big_five": {"E": 0.3, "C": 0.3},
        "defense": ["sublimation"],
        "sdt": {"competence": 0.5},
        "archetype": "hero",
    },
    "Guns": {
        "big_five": {"E": 0.3, "N": 0.2},
        "defense": ["sublimation"],
        "archetype": "outlaw",
    },
    "Martial Arts": {
        "big_five": {"C": 0.3, "E": 0.2},
        "sdt": {"competence": 0.6, "autonomy": 0.2},
        "achievement": "mastery",
        "archetype": "hero",
    },
    # 特殊题材
    "Trapped in a Game": {
        "big_five": {"O": 0.4, "N": 0.2},
        "defense": ["dissociation"],
        "sdt": {"competence": 0.5},
        "archetype": "explorer",
    },
    "Game of Death": {
        "big_five": {"N": 0.5, "C": 0.3},
        "existential": ["death"],
        "defense": ["sublimation"],
    },
    "Mind Control": {
        "big_five": {"N": 0.4, "O": 0.3},
        "existential": ["freedom"],
        "moral": ["liberty_oppression"],
    },
    "Body Swapping": {
        "big_five": {"O": 0.5, "N": 0.2},
        "defense": ["dissociation"],
        "archetype": "magician",
    },
    "Aging": {
        "big_five": {"O": 0.2, "N": 0.2},
        "existential": ["death", "meaninglessness"],
        "meaning_type": "attitudinal",
    },
    "Amnesia": {
        "big_five": {"O": 0.3, "N": 0.3},
        "archetype": "explorer",
        "existential": ["meaninglessness"],
    },
    "Clone": {
        "big_five": {"O": 0.4, "N": 0.3},
        "existential": ["meaninglessness", "isolation"],
        "archetype": "seeker",
    },
    "Doppelganger": {
        "big_five": {"O": 0.4, "N": 0.4},
        "existential": ["meaninglessness"],
        "object_relations": "splitting",
    },
}

# ========= 番剧类型到心理特征的映射 =========
GENRE_TO_PSYCH = {
    "Action": {"big_five": {"E": 0.3}, "defense": ["sublimation"]},
    "Adventure": {"big_five": {"O": 0.4}, "archetype": "explorer"},
    "Comedy": {"big_five": {"E": 0.3, "A": 0.3, "N": -0.3}, "archetype": "jester"},
    "Drama": {"big_five": {"N": 0.2, "O": 0.2}, "emotion_regulation": ["rumination"]},
    "Fantasy": {"big_five": {"O": 0.5}, "defense": ["fantasy"]},
    "Horror": {"big_five": {"N": 0.5}, "existential": ["death"]},
    "Mystery": {"big_five": {"O": 0.3, "C": 0.3}, "cognitive": ["Ni", "Ti"]},
    "Psychological": {"big_five": {"N": 0.4, "O": 0.4}, "defense": ["intellectualization"]},
    "Romance": {"big_five": {"A": 0.3}, "archetype": "lover"},
    "Sci-Fi": {"big_five": {"O": 0.5}, "cognitive": ["Ti", "Ne"]},
    "Slice of Life": {"big_five": {"A": 0.4, "N": -0.3}, "defense": ["isolation"]},
    "Sports": {"big_five": {"E": 0.3, "C": 0.3}, "achievement": "mastery"},
    "Supernatural": {"big_five": {"O": 0.4}, "worldview": "magical_world"},
    "Thriller": {"big_five": {"N": 0.4}, "defense": ["sublimation"]},
}

# ========= 情绪标签到心理特征的映射 =========
EMOTION_TO_PSYCH = {
    "bittersweet": {"big_five": {"N": 0.3, "O": 0.2}, "narrative": "contamination"},
    "dark": {"big_five": {"N": 0.5, "A": -0.3}, "archetype": "destroyer"},
    "emotional": {"big_five": {"N": 0.4}, "emotion_regulation": ["rumination"]},
    "heartwarming": {"big_five": {"A": 0.5, "N": -0.4}, "archetype": "caregiver"},
    "hopeful": {"big_five": {"A": 0.3, "N": -0.2}, "narrative": "redemption"},
    "intense": {"big_five": {"E": 0.3, "N": 0.3}, "defense": ["sublimation"]},
    "melancholic": {"big_five": {"N": 0.4, "O": 0.2}, "emotion_regulation": ["rumination"]},
    "nostalgic": {"big_five": {"O": 0.2, "N": 0.1}, "defense": ["regression"]},
    "peaceful": {"big_five": {"A": 0.4, "N": -0.4}, "emotion_regulation": ["acceptance"]},
    "suspenseful": {"big_five": {"N": 0.3, "C": 0.2}, "defense": ["sublimation"]},
    "thought-provoking": {"big_five": {"O": 0.5}, "cognitive": ["Ni", "Ti"]},
    "uplifting": {"big_five": {"A": 0.3, "E": 0.2}, "narrative": "progressive"},
    "wholesome": {"big_five": {"A": 0.5, "N": -0.5}, "archetype": "innocent"},
    "bizarre": {"big_five": {"O": 0.6}, "personal_constructs": ["flexibility"]},
    "surreal": {"big_five": {"O": 0.6, "N": 0.2}, "defense": ["dissociation"]},
}


# ============================================================
# 心理画像类
# ============================================================
class ComprehensivePsychProfile:
    """完整心理画像 - 24个维度"""

    def __init__(self):
        # 第一层：人格（基础，无依赖）
        self.big_five = {"O": 0.5, "C": 0.5, "E": 0.5, "A": 0.5, "N": 0.5}
        self.mbti = ""
        self.enneagram = ""
        self.cognitive_functions = []

        # 第二层：需求（依赖第一层）
        self.maslow_level = 3
        self.sdt_needs = {"autonomy": 0.33, "competence": 0.33, "relatedness": 0.34}
        self.regulatory_focus = ""
        self.achievement_type = ""
        self.existential_concerns = []
        self.meaning_type = ""

        # 第三层：情感（依赖第一、二层）
        self.attachment = ""
        self.emotion_regulation = []
        self.defense_mechanisms = []
        self.self_object_needs = []
        self.object_relations = ""

        # 第四层：叙事（依赖前三层）
        self.archetype = ""
        self.narrative_type = ""
        self.hero_journey_stage = ""
        self.character_identification = ""
        self.worldview = ""

        # 第五层：价值（依赖前四层）
        self.values = {}
        self.moral_foundations = []
        self.social_identity = ""
        self.personal_constructs = []

    def build_from_anime(self, anime: dict) -> "ComprehensivePsychProfile":
        """从一部番剧构建完整心理画像"""
        features = self._analyze_anime(anime)

        # 第一层：人格（相互独立，可并行）
        self._infer_big_five(features)
        self._infer_mbti(features)
        self._infer_enneagram(features)
        self._infer_cognitive_functions(features)

        # 第二层：需求（依赖 big_five）
        self._infer_maslow(features)
        self._infer_sdt(features)
        self._infer_regulatory_focus(features)
        self._infer_achievement(features)
        self._infer_existential(features)
        self._infer_meaning(features)

        # 第三层：情感（依赖 big_five, sdt, defense）
        self._infer_attachment(features)
        self._infer_emotion_regulation(features)
        self._infer_defense(features)
        self._infer_self_object(features)
        self._infer_object_relations(features)

        # 第四层：叙事（依赖前三层）
        self._infer_archetype(features)
        self._infer_narrative(features)
        self._infer_hero_journey(features)
        self._infer_character_id(features)
        self._infer_worldview(features)

        # 第五层：价值（依赖前四层）
        self._infer_values(features)
        self._infer_moral(features)
        self._infer_social_identity(features)
        self._infer_personal_constructs(features)

        return self

    def build_from_anime_weighted(self, weighted_anime_list: list) -> "ComprehensivePsychProfile":
        """从多部番剧加权构建心理画像
        
        weighted_anime_list: [(anime_dict, weight), ...]
        权重越高的番剧对心理画像影响越大
        """
        # 初始化累积分数
        big_five_scores = {"O": 0, "C": 0, "E": 0, "A": 0, "N": 0}
        big_five_weights = {"O": 0, "C": 0, "E": 0, "A": 0, "N": 0}
        
        archetype_scores = {}
        defense_scores = {}
        sdt_scores = {"autonomy": 0, "competence": 0, "relatedness": 0}
        narrative_scores = {}
        worldview_scores = {}
        
        # 遍历所有番剧，加权累积
        for anime, weight in weighted_anime_list:
            features = self._analyze_anime(anime)
            
            # 累加大五人格
            for tag in features["tags"]:
                if tag in TAG_TO_PSYCH and "big_five" in TAG_TO_PSYCH[tag]:
                    for dim, delta in TAG_TO_PSYCH[tag]["big_five"].items():
                        big_five_scores[dim] += delta * weight
                        big_five_weights[dim] += weight
            
            # 累加其他维度...
            for tag in features["tags"]:
                if tag not in TAG_TO_PSYCH:
                    continue
                psych = TAG_TO_PSYCH[tag]
                
                # 原型
                if "archetype" in psych:
                    arch = psych["archetype"]
                    if isinstance(arch, list):
                        arch = arch[0] if arch else ""
                    if arch:
                        archetype_scores[arch] = archetype_scores.get(arch, 0) + weight
                
                # 防御机制
                if "defense" in psych:
                    for d in psych["defense"]:
                        defense_scores[d] = defense_scores.get(d, 0) + weight
                
                # SDT需求
                if "sdt" in psych:
                    for need, val in psych["sdt"].items():
                        sdt_scores[need] += val * weight
                
                # 叙事
                if "narrative" in psych:
                    nar = psych["narrative"]
                    narrative_scores[nar] = narrative_scores.get(nar, 0) + weight
                
                # 世界观
                if "worldview" in psych:
                    wv = psych["worldview"]
                    worldview_scores[wv] = worldview_scores.get(wv, 0) + weight
        
        # 计算最终大五人格
        for dim in big_five_scores:
            if big_five_weights[dim] > 0:
                self.big_five[dim] = self._clamp(big_five_scores[dim] / big_five_weights[dim])
        
        # 设置其他维度
        if archetype_scores:
            self.archetype = max(archetype_scores, key=archetype_scores.get)
        
        if defense_scores:
            self.defense_mechanisms = sorted(defense_scores.items(), key=lambda x: -x[1])
            self.defense_mechanisms = [m for m, _ in self.defense_mechanisms]
        
        # 推断其他依赖大五人格的维度
        self._infer_mbti({"tags": set()})
        self._infer_enneagram({"tags": set()})
        self._infer_cognitive_functions({"tags": set()})
        
        # 需求
        total_sdt = sum(sdt_scores.values())
        if total_sdt > 0:
            self.sdt_needs = {k: v / total_sdt for k, v in sdt_scores.items()}
        
        # 叙事和世界观
        if narrative_scores:
            self.narrative_type = max(narrative_scores, key=narrative_scores.get)
        if worldview_scores:
            self.worldview = max(worldview_scores, key=worldview_scores.get)
        
        return self

    def _analyze_anime(self, anime: dict) -> dict:
        """分析番剧特征，提取所有可用的心理信号"""
        tags = set(anime.get("tags") or [])
        tags_cn = set(anime.get("tags_cn") or [])
        
        # 过滤R18标签
        tags = {t for t in tags if t not in R18_TAGS}
        tags_cn = {t for t in tags_cn if t not in R18_TAGS}
        
        # 获取标签权重（主tag权重高，副tag权重低）
        tags_with_rank = anime.get("tags_with_rank") or []
        tag_weights = {}
        for t in tags_with_rank:
            name = t.get("name")
            rank = t.get("rank") or 50
            if name and name not in R18_TAGS:
                # rank越高，权重越高（主tag的rank通常更高）
                # 权重公式：1.0 + (rank - 50) / 100，范围0.5-1.5
                tag_weights[name] = 1.0 + (rank - 50) / 100
        
        format_type = anime.get("format") or ""
        rating = anime.get("mean_score") or 0
        popularity = anime.get("popularity") or 0
        favourites = anime.get("favourites") or 0
        eps = anime.get("eps") or 0
        duration = anime.get("duration") or 0
        year = anime.get("year") or anime.get("season_year") or 2020
        summary = (anime.get("summary") or "").lower()

        return {
            "tags": tags,
            "tags_cn": tags_cn,
            "tag_weights": tag_weights,
            "format": format_type,
            "rating": rating,
            "popularity": popularity,
            "favourites": favourites,
            "eps": eps,
            "duration": duration,
            "year": year,
            "summary": summary,
        }

    def _clamp(self, val: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, val))

    # ============================================================
    # 第一层：人格推断
    # ============================================================

    def _infer_big_five(self, f: dict):
        """推断大五人格（主tag权重高，副tag权重低）"""
        scores = {"O": 0.5, "C": 0.5, "E": 0.5, "A": 0.5, "N": 0.5}
        count = {"O": 1, "C": 1, "E": 1, "A": 1, "N": 1}
        
        tag_weights = f.get("tag_weights", {})

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "big_five" in TAG_TO_PSYCH[tag]:
                # 主tag权重高（1.0-1.5），副tag权重低（0.5-1.0）
                weight = tag_weights.get(tag, 1.0)
                for dim, delta in TAG_TO_PSYCH[tag]["big_five"].items():
                    scores[dim] += delta * weight
                    count[dim] += weight

        for genre in f["tags"]:
            if genre in GENRE_TO_PSYCH and "big_five" in GENRE_TO_PSYCH[genre]:
                weight = tag_weights.get(genre, 1.0) * 0.5  # 类型标签权重减半
                for dim, delta in GENRE_TO_PSYCH[genre]["big_five"].items():
                    scores[dim] += delta * weight
                    count[dim] += weight

        self.big_five = {
            dim: self._clamp(scores[dim] / count[dim])
            for dim in scores
        }

    def _infer_mbti(self, f: dict):
        """推断MBTI类型"""
        type_scores = {
            "INTJ": 0, "INTP": 0, "ENTJ": 0, "ENTP": 0,
            "INFJ": 0, "INFP": 0, "ENFJ": 0, "ENFP": 0,
            "ISTJ": 0, "ISFJ": 0, "ESTJ": 0, "ESFJ": 0,
            "ISTP": 0, "ISFP": 0, "ESTP": 0, "ESFP": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "mbti_weight" in TAG_TO_PSYCH[tag]:
                for mbti_type, weight in TAG_TO_PSYCH[tag]["mbti_weight"].items():
                    type_scores[mbti_type] += weight

        if self.big_five["E"] < 0.45:
            for t in type_scores:
                if t[0] == "I":
                    type_scores[t] += 0.3
        else:
            for t in type_scores:
                if t[0] == "E":
                    type_scores[t] += 0.3

        if self.big_five["N"] > 0.55:
            for t in type_scores:
                if "N" in t and "F" in t:
                    type_scores[t] += 0.2
        if self.big_five["O"] > 0.6:
            for t in type_scores:
                if "N" in t:
                    type_scores[t] += 0.2

        self.mbti = max(type_scores, key=type_scores.get)

    def _infer_enneagram(self, f: dict):
        """推断九型人格"""
        scores = {str(i): 0 for i in range(1, 10)}

        for tag in f["tags"]:
            psych = TAG_TO_PSYCH.get(tag, {})
            archetype = psych.get("archetype", "")
            if isinstance(archetype, list):
                archetype = archetype[0] if archetype else ""

            archetype_to_enneagram = {
                "hero": "3", "sage": "5", "explorer": "7",
                "outlaw": "8", "magician": "9", "caregiver": "2",
                "lover": "4", "jester": "7", "orphan": "4",
                "creator": "4", "ruler": "8", "innocent": "9",
                "everyman": "6", "seeker": "5", "destroyer": "8",
                "fool": "7",
            }
            if archetype in archetype_to_enneagram:
                scores[archetype_to_enneagram[archetype]] += 0.3

        if self.big_five["N"] > 0.6:
            scores["4"] += 0.3
            scores["6"] += 0.2
        if self.big_five["E"] > 0.6:
            scores["3"] += 0.2
            scores["7"] += 0.3
        if self.big_five["A"] > 0.6:
            scores["2"] += 0.3
            scores["9"] += 0.2
        if self.big_five["C"] > 0.6:
            scores["1"] += 0.3
            scores["3"] += 0.2

        self.enneagram = max(scores, key=scores.get)

    def _infer_cognitive_functions(self, f: dict):
        """推断认知功能栈"""
        func_scores = {
            "Ti": 0, "Te": 0, "Fi": 0, "Fe": 0,
            "Ni": 0, "Ne": 0, "Si": 0, "Se": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "cognitive" in TAG_TO_PSYCH[tag]:
                for func in TAG_TO_PSYCH[tag]["cognitive"]:
                    func_scores[func] += 0.5

        if self.big_five["O"] > 0.6:
            func_scores["Ni"] += 0.2
            func_scores["Ne"] += 0.3
        if self.big_five["C"] > 0.6:
            func_scores["Ti"] += 0.2
            func_scores["Te"] += 0.2
        if self.big_five["E"] > 0.6:
            func_scores["Se"] += 0.2
            func_scores["Fe"] += 0.2

        sorted_funcs = sorted(func_scores.items(), key=lambda x: -x[1])
        self.cognitive_functions = [f[0] for f in sorted_funcs[:4]]

    # ============================================================
    # 第二层：需求推断
    # ============================================================

    def _infer_maslow(self, f: dict):
        """推断马斯洛需求层次"""
        level_scores = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "maslow" in TAG_TO_PSYCH[tag]:
                level_scores[TAG_TO_PSYCH[tag]["maslow"]] += 1

        if any(t in f["tags"] for t in ["Slice of Life", "Healing", "Iyashikei"]):
            level_scores[2] += 2
        if any(t in f["tags"] for t in ["Friendship", "School", "Club"]):
            level_scores[3] += 2
        if any(t in f["tags"] for t in ["Sports", "Competition", "Work"]):
            level_scores[4] += 2
        if any(t in f["tags"] for t in ["Sci-Fi", "Mystery", "Detective"]):
            level_scores[5] += 2
        if any(t in f["tags"] for t in ["Music", "Art"]):
            level_scores[6] += 2
        if any(t in f["tags"] for t in ["Growth", "Coming-of-Age", "Motivational"]):
            level_scores[7] += 2
        if any(t in f["tags"] for t in ["Philosophical", "Psychology"]):
            level_scores[8] += 2

        self.maslow_level = max(level_scores, key=level_scores.get)

    def _infer_sdt(self, f: dict):
        """推断自我决定理论需求"""
        needs = {"autonomy": 0.33, "competence": 0.33, "relatedness": 0.34}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "sdt" in TAG_TO_PSYCH[tag]:
                for need, val in TAG_TO_PSYCH[tag]["sdt"].items():
                    needs[need] += val

        total = sum(needs.values())
        self.sdt_needs = {k: v / total for k, v in needs.items()}

    def _infer_regulatory_focus(self, f: dict):
        """推断调节焦点"""
        promotion = 0
        prevention = 0

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH:
                if TAG_TO_PSYCH[tag].get("regulatory") == "promotion":
                    promotion += 1
                elif TAG_TO_PSYCH[tag].get("regulatory") == "prevention":
                    prevention += 1

        if any(t in f["tags"] for t in ["Action", "Adventure", "Sports"]):
            promotion += 2
        if any(t in f["tags"] for t in ["Slice of Life", "Healing", "Iyashikei"]):
            prevention += 2

        self.regulatory_focus = "promotion" if promotion >= prevention else "prevention"

    def _infer_achievement(self, f: dict):
        """推断成就动机类型"""
        scores = {"mastery": 0, "performance": 0, "avoidance": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "achievement" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["achievement"]] += 1

        if self.sdt_needs.get("competence", 0) > 0.4:
            scores["mastery"] += 2
        if self.big_five["E"] > 0.6:
            scores["performance"] += 1
        if self.big_five["N"] > 0.6:
            scores["avoidance"] += 1

        self.achievement_type = max(scores, key=scores.get)

    def _infer_existential(self, f: dict):
        """推断存在主义关怀"""
        concerns = {"death": 0, "freedom": 0, "isolation": 0, "meaninglessness": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "existential" in TAG_TO_PSYCH[tag]:
                for concern in TAG_TO_PSYCH[tag]["existential"]:
                    concerns[concern] += 1

        if self.big_five["N"] > 0.6:
            concerns["death"] += 1
            concerns["meaninglessness"] += 1
        if self.big_five["O"] > 0.6:
            concerns["freedom"] += 1
            concerns["meaninglessness"] += 1
        if self.sdt_needs.get("relatedness", 0) < 0.3:
            concerns["isolation"] += 1

        self.existential_concerns = [
            c for c, v in sorted(concerns.items(), key=lambda x: -x[1])
            if v > 0
        ]

    def _infer_meaning(self, f: dict):
        """推断意义类型（Frankl）"""
        scores = {"creative": 0, "experiential": 0, "attitudinal": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "meaning_type" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["meaning_type"]] += 1

        if any(t in f["tags"] for t in ["Music", "Art", "Creator"]):
            scores["creative"] += 2
        if any(t in f["tags"] for t in ["Travel", "Adventure", "Nature"]):
            scores["experiential"] += 2
        if any(t in f["tags"] for t in ["Tragedy", "Growth", "Coming-of-Age"]):
            scores["attitudinal"] += 2

        self.meaning_type = max(scores, key=scores.get)

    # ============================================================
    # 第三层：情感推断
    # ============================================================

    def _infer_attachment(self, f: dict):
        """推断依恋类型"""
        scores = {
            "secure": 0,
            "anxious_preoccupied": 0,
            "dismissive_avoidant": 0,
            "fearful_avoidant": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "attachment" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["attachment"]] += 1

        if self.big_five["A"] > 0.6:
            scores["secure"] += 2
        if self.big_five["N"] > 0.6:
            scores["anxious_preoccupied"] += 2
            scores["fearful_avoidant"] += 1
        if self.big_five["A"] < 0.4:
            scores["dismissive_avoidant"] += 2
        if "Love Triangle" in f["tags"] or "Tragic Romance" in f["tags"]:
            scores["fearful_avoidant"] += 2
            scores["anxious_preoccupied"] += 1

        self.attachment = max(scores, key=scores.get)

    def _infer_emotion_regulation(self, f: dict):
        """推断情绪调节策略"""
        strategies = {
            "reappraisal": 0,
            "suppression": 0,
            "acceptance": 0,
            "rumination": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "emotion_regulation" in TAG_TO_PSYCH[tag]:
                for s in TAG_TO_PSYCH[tag]["emotion_regulation"]:
                    strategies[s] += 1

        if self.big_five["O"] > 0.6:
            strategies["reappraisal"] += 1
        if self.big_five["E"] > 0.6:
            strategies["suppression"] += 1
        if self.big_five["A"] > 0.6:
            strategies["acceptance"] += 1
        if self.big_five["N"] > 0.6:
            strategies["rumination"] += 2

        self.emotion_regulation = [
            s for s, v in sorted(strategies.items(), key=lambda x: -x[1])
            if v > 0
        ]

    def _infer_defense(self, f: dict):
        """推断防御机制"""
        mechanisms = {}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "defense" in TAG_TO_PSYCH[tag]:
                for mech in TAG_TO_PSYCH[tag]["defense"]:
                    mechanisms[mech] = mechanisms.get(mech, 0) + 1

        self.defense_mechanisms = [
            m for m, v in sorted(mechanisms.items(), key=lambda x: -x[1])
        ]

    def _infer_self_object(self, f: dict):
        """推断自体客体需求"""
        needs = {"mirroring": 0, "idealizing": 0, "twinship": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "self_object" in TAG_TO_PSYCH[tag]:
                for need in TAG_TO_PSYCH[tag]["self_object"]:
                    needs[need] += 1

        if self.big_five["E"] < 0.4:
            needs["mirroring"] += 1
        if self.sdt_needs.get("competence", 0) > 0.4:
            needs["idealizing"] += 1
        if self.sdt_needs.get("relatedness", 0) > 0.4:
            needs["twinship"] += 1

        self.self_object_needs = [
            n for n, v in sorted(needs.items(), key=lambda x: -x[1])
            if v > 0
        ]

    def _infer_object_relations(self, f: dict):
        """推断客体关系模式"""
        scores = {"splitting": 0, "integration": 0, "containment": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "object_relations" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["object_relations"]] += 1

        if self.big_five["A"] < 0.4 and self.big_five["N"] > 0.6:
            scores["splitting"] += 2
        if self.big_five["O"] > 0.6 and self.big_five["A"] > 0.5:
            scores["integration"] += 2
        if self.big_five["A"] > 0.6 and self.big_five["N"] < 0.4:
            scores["containment"] += 2

        self.object_relations = max(scores, key=scores.get)

    # ============================================================
    # 第四层：叙事推断
    # ============================================================

    def _infer_archetype(self, f: dict):
        """推断主导原型"""
        archetype_scores = {
            "hero": 0, "sage": 0, "explorer": 0, "outlaw": 0,
            "magician": 0, "caregiver": 0, "lover": 0, "jester": 0,
            "orphan": 0, "creator": 0, "ruler": 0, "innocent": 0,
            "everyman": 0, "seeker": 0, "destroyer": 0, "fool": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "archetype" in TAG_TO_PSYCH[tag]:
                arch = TAG_TO_PSYCH[tag]["archetype"]
                if isinstance(arch, list):
                    for a in arch:
                        if a in archetype_scores:
                            archetype_scores[a] += 1
                elif arch in archetype_scores:
                    archetype_scores[arch] += 1

        self.archetype = max(archetype_scores, key=archetype_scores.get)

    def _infer_narrative(self, f: dict):
        """推断叙事类型"""
        scores = {
            "redemption": 0, "contamination": 0,
            "exploration": 0, "stability": 0,
            "progressive": 0, "regressive": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "narrative" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["narrative"]] += 1

        if self.defense_mechanisms and "regression" in self.defense_mechanisms:
            scores["regressive"] += 1
        if self.big_five["N"] > 0.6:
            scores["contamination"] += 1
        if self.big_five["A"] > 0.6:
            scores["stability"] += 1
        if self.archetype in ["hero", "explorer"]:
            scores["progressive"] += 1
        if self.archetype == "outlaw":
            scores["redemption"] += 1

        self.narrative_type = max(scores, key=scores.get)

    def _infer_hero_journey(self, f: dict):
        """推断英雄之旅阶段"""
        scores = {"departure": 0, "initiation": 0, "return": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "hero_journey" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["hero_journey"]] += 1

        if self.archetype == "explorer":
            scores["departure"] += 2
        if self.archetype == "hero":
            scores["initiation"] += 2
        if self.narrative_type == "redemption":
            scores["return"] += 2

        self.hero_journey_stage = max(scores, key=scores.get)

    def _infer_character_id(self, f: dict):
        """推断角色认同模式"""
        scores = {
            "self_ideal": 0,
            "self_real": 0,
            "self_shadow": 0,
            "anti_hero": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "character_id" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["character_id"]] += 1

        if self.sdt_needs.get("competence", 0) > 0.4:
            scores["self_ideal"] += 2
        if self.big_five["N"] > 0.6:
            scores["self_shadow"] += 1
        if self.archetype == "everyman":
            scores["self_real"] += 2
        if self.archetype == "outlaw":
            scores["anti_hero"] += 2

        self.character_identification = max(scores, key=scores.get)

    def _infer_worldview(self, f: dict):
        """推断世界观认同"""
        scores = {
            "just_world": 0,
            "unjust_world": 0,
            "magical_world": 0,
            "dystopian": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "worldview" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["worldview"]] += 1

        if self.big_five["A"] > 0.6:
            scores["just_world"] += 2
        if self.big_five["N"] > 0.6:
            scores["unjust_world"] += 1
        if self.defense_mechanisms and "fantasy" in self.defense_mechanisms:
            scores["magical_world"] += 2
        if any(t in f["tags"] for t in ["Dystopian", "Post-Apocalyptic"]):
            scores["dystopian"] += 2

        self.worldview = max(scores, key=scores.get)

    # ============================================================
    # 第五层：价值推断
    # ============================================================

    def _infer_values(self, f: dict):
        """推断价值取向（Schwartz）"""
        val_scores = {
            "self_direction": 0, "stimulation": 0, "hedonism": 0,
            "achievement": 0, "power": 0, "security": 0,
            "conformity": 0, "tradition": 0, "benevolence": 0,
            "universalism": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "values" in TAG_TO_PSYCH[tag]:
                for v, s in TAG_TO_PSYCH[tag]["values"].items():
                    val_scores[v] += s

        if self.big_five["O"] > 0.6:
            val_scores["self_direction"] += 0.3
            val_scores["stimulation"] += 0.2
        if self.big_five["E"] > 0.6:
            val_scores["stimulation"] += 0.2
            val_scores["hedonism"] += 0.2
        if self.big_five["C"] > 0.6:
            val_scores["conformity"] += 0.2
            val_scores["security"] += 0.2
        if self.big_five["A"] > 0.6:
            val_scores["benevolence"] += 0.3
            val_scores["universalism"] += 0.2

        total = sum(val_scores.values()) or 1
        self.values = {k: v / total for k, v in val_scores.items()}

    def _infer_moral(self, f: dict):
        """推断道德基础"""
        foundations = {
            "care_harm": 0, "fairness_cheating": 0,
            "loyalty_betrayal": 0, "authority_subversion": 0,
            "sanctity_degradation": 0, "liberty_oppression": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "moral" in TAG_TO_PSYCH[tag]:
                for m in TAG_TO_PSYCH[tag]["moral"]:
                    foundations[m] += 1

        if self.big_five["A"] > 0.6:
            foundations["care_harm"] += 2
        if self.big_five["C"] > 0.6:
            foundations["fairness_cheating"] += 1
        if self.sdt_needs.get("relatedness", 0) > 0.4:
            foundations["loyalty_betrayal"] += 1

        self.moral_foundations = [
            m for m, v in sorted(foundations.items(), key=lambda x: -x[1])
            if v > 0
        ]

    def _infer_social_identity(self, f: dict):
        """推断社会认同"""
        scores = {"in_group": 0, "out_group": 0, "individual": 0}

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "social_identity" in TAG_TO_PSYCH[tag]:
                scores[TAG_TO_PSYCH[tag]["social_identity"]] += 1

        if self.big_five["E"] > 0.6:
            scores["in_group"] += 2
        if self.big_five["E"] < 0.4:
            scores["out_group"] += 1
            scores["individual"] += 1
        if self.sdt_needs.get("relatedness", 0) > 0.4:
            scores["in_group"] += 1
        if self.sdt_needs.get("autonomy", 0) > 0.4:
            scores["individual"] += 1

        self.social_identity = max(scores, key=scores.get)

    def _infer_personal_constructs(self, f: dict):
        """推断个人建构方式"""
        scores = {
            "dichotomous": 0,
            "complexity": 0,
            "flexibility": 0,
            "permeability": 0,
        }

        for tag in f["tags"]:
            if tag in TAG_TO_PSYCH and "personal_constructs" in TAG_TO_PSYCH[tag]:
                for p in TAG_TO_PSYCH[tag]["personal_constructs"]:
                    scores[p] += 1

        if self.big_five["O"] > 0.6:
            scores["complexity"] += 1
            scores["flexibility"] += 1
            scores["permeability"] += 1
        if self.big_five["O"] < 0.4:
            scores["dichotomous"] += 2
        if self.object_relations == "splitting":
            scores["dichotomous"] += 1
        if self.object_relations == "integration":
            scores["complexity"] += 1

        self.personal_constructs = [
            p for p, v in sorted(scores.items(), key=lambda x: -x[1])
            if v > 0
        ]

    # ============================================================
    # 输出方法
    # ============================================================

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "personality": {
                "big_five": self.big_five,
                "mbti": self.mbti,
                "enneagram": self.enneagram,
                "cognitive_functions": self.cognitive_functions,
            },
            "needs": {
                "maslow_level": self.maslow_level,
                "sdt_needs": self.sdt_needs,
                "regulatory_focus": self.regulatory_focus,
                "achievement_type": self.achievement_type,
                "existential_concerns": self.existential_concerns,
                "meaning_type": self.meaning_type,
            },
            "emotion": {
                "attachment": self.attachment,
                "emotion_regulation": self.emotion_regulation,
                "defense_mechanisms": self.defense_mechanisms,
                "self_object_needs": self.self_object_needs,
                "object_relations": self.object_relations,
            },
            "narrative": {
                "archetype": self.archetype,
                "narrative_type": self.narrative_type,
                "hero_journey_stage": self.hero_journey_stage,
                "character_identification": self.character_identification,
                "worldview": self.worldview,
            },
            "values": {
                "values": self.values,
                "moral_foundations": self.moral_foundations,
                "social_identity": self.social_identity,
                "personal_constructs": self.personal_constructs,
            },
        }

    def get_recommendation_direction(self) -> dict:
        """基于心理画像生成推荐方向"""
        direction = {
            "primary_need": "",
            "secondary_need": "",
            "preferred_archetype": self.archetype,
            "preferred_narrative": self.narrative_type,
            "avoid_tags": [],
            "seek_tags": [],
            "reasoning": "",
        }

        # 确定主要需求
        need_priority = []
        if self.attachment in ["anxious_preoccupied", "fearful_avoidant"]:
            need_priority.append(("被爱与安全感", 3))
        if self.defense_mechanisms and "dissociation" in self.defense_mechanisms:
            need_priority.append(("逃避现实", 3))
        if self.existential_concerns and "isolation" in self.existential_concerns:
            need_priority.append(("连接与归属", 2))
        if self.sdt_needs.get("competence", 0) > 0.4:
            need_priority.append(("成就感", 2))
        if self.big_five["N"] > 0.6:
            need_priority.append(("情绪稳定", 1))
        if self.big_five["A"] > 0.6:
            need_priority.append(("温暖治愈", 1))

        need_priority.sort(key=lambda x: -x[1])
        if need_priority:
            direction["primary_need"] = need_priority[0][0]
        if len(need_priority) > 1:
            direction["secondary_need"] = need_priority[1][0]

        # 确定推荐标签
        if self.defense_mechanisms and "dissociation" in self.defense_mechanisms:
            direction["seek_tags"].extend(["Isekai", "Fantasy", "Adventure"])
        if self.big_five["N"] > 0.6:
            direction["seek_tags"].extend(["Healing", "Slice of Life"])
        if self.sdt_needs.get("competence", 0) > 0.4:
            direction["seek_tags"].extend(["Sports", "Action"])
        if self.attachment in ["anxious_preoccupied"]:
            direction["seek_tags"].extend(["Romance", "Healing"])

        # 生成推荐理由
        direction["reasoning"] = self._generate_reasoning()

        return direction

    def _generate_reasoning(self) -> str:
        """生成详细的心理画像解读"""
        parts = []

        # 第一层：人格特征解读
        personality_insights = []

        # 大五人格详细解读
        o = self.big_five["O"]
        c = self.big_five["C"]
        e = self.big_five["E"]
        a = self.big_five["A"]
        n = self.big_five["N"]

        if o > 0.65:
            personality_insights.append("你对新奇事物有强烈的好奇心，喜欢探索未知领域")
        elif o < 0.35:
            personality_insights.append("你更偏好熟悉的事物，喜欢稳定和可预测的内容")

        if c > 0.65:
            personality_insights.append("你重视逻辑和秩序，喜欢有结构的内容")
        elif c < 0.35:
            personality_insights.append("你更随性自由，不喜欢被规则束缚")

        if e > 0.65:
            personality_insights.append("你外向活泼，喜欢热闹和社交元素")
        elif e < 0.35:
            personality_insights.append("你偏向内敛，更享受独处和深度思考")

        if a > 0.65:
            personality_insights.append("你重视和谐与温暖，喜欢治愈和善意的内容")
        elif a < 0.35:
            personality_insights.append("你能接受更复杂和灰色的内容，不回避冲突")

        if n > 0.65:
            personality_insights.append("你情感敏感，能深度体验作品中的情绪波动")
        elif n < 0.35:
            personality_insights.append("你情绪稳定，更偏好轻松无压力的内容")

        if personality_insights:
            parts.append("【性格特征】" + "；".join(personality_insights[:3]))

        # 第二层：MBTI与认知风格
        mbti_insight = ""
        mbti_desc = {
            "INTJ": "你有战略思维，喜欢深度分析和长远规划",
            "INTP": "你是逻辑思考者，喜欢探索理论和可能性",
            "ENTJ": "你喜欢掌控和效率，偏好有目标的内容",
            "ENTP": "你思维敏捷，喜欢辩论和创新",
            "INFJ": "你有直觉洞察力，追求深度意义和理想",
            "INFP": "你重视内在价值，喜欢有情感深度的故事",
            "ENFJ": "你关注他人成长，喜欢有温度的人际关系",
            "ENFP": "你充满热情，喜欢探索各种可能性",
            "ISTJ": "你务实可靠，喜欢有条理的内容",
            "ISFJ": "你温暖体贴，喜欢保护和照顾他人",
            "ESTJ": "你有组织能力，喜欢高效和秩序",
            "ESFJ": "你重视和谐，喜欢温暖的社交互动",
            "ISTP": "你喜欢独立思考，偏好实操性强的内容",
            "ISFP": "你审美敏锐，喜欢美好和治愈的事物",
            "ESTP": "你行动力强，喜欢刺激和即时反馈",
            "ESFP": "你乐观开朗，喜欢轻松快乐的体验",
        }
        if self.mbti in mbti_desc:
            mbti_insight = mbti_desc[self.mbti]
            parts.append("【认知风格】" + mbti_insight)

        # 第三层：需求与动机
        need_insights = []

        # SDT需求
        primary_need = max(self.sdt_needs, key=self.sdt_needs.get)
        need_desc = {
            "autonomy": "你追求自由和自主，喜欢有选择权的内容",
            "competence": "你追求成长和掌握，喜欢有挑战和进步的故事",
            "relatedness": "你追求连接和归属，喜欢有深度人际关系的内容",
        }
        if primary_need in need_desc:
            need_insights.append(need_desc[primary_need])

        # 依恋类型
        attachment_desc = {
            "secure": "你有健康的亲密关系观，能接受温暖的情感表达",
            "anxious_preoccupied": "你渴望被爱和确认，喜欢明确的情感表达",
            "dismissive_avoidant": "你重视独立，更喜欢含蓄的情感表达",
            "fearful_avoidant": "你对亲密关系有矛盾心理，喜欢复杂的情感纠葛",
        }
        if self.attachment in attachment_desc:
            need_insights.append(attachment_desc[self.attachment])

        if need_insights:
            parts.append("【情感需求】" + "；".join(need_insights))

        # 第四层：防御机制与应对方式
        defense_insights = []
        defense_desc = {
            "sublimation": "你善于将压力转化为正向动力，喜欢热血和励志内容",
            "dissociation": "你需要暂时逃离现实，喜欢沉浸式的幻想世界",
            "intellectualization": "你喜欢用理性分析来理解事物，偏好悬疑和推理",
            "fantasy": "你享受沉浸在幻想世界中，喜欢奇幻和超现实内容",
            "projection": "你能接受复杂的角色和道德灰色地带",
            "isolation": "你需要情感上的安全感，喜欢轻松无压力的内容",
            "regression": "你有时需要回到 simpler times，喜欢怀旧和萌系内容",
            "denial": "你偏好积极正向的内容，回避过于沉重的主题",
        }
        if self.defense_mechanisms:
            primary_defense = self.defense_mechanisms[0]
            if primary_defense in defense_desc:
                defense_insights.append(defense_desc[primary_defense])

        # 情绪调节策略
        emotion_desc = {
            "reappraisal": "你能从不同角度看问题，喜欢有深度反思的内容",
            "suppression": "你倾向于压抑情绪，需要通过热血内容释放",
            "acceptance": "你能接纳自己的情绪，喜欢治愈和平静的内容",
            "rumination": "你有时会反复思考，喜欢有情感共鸣的故事",
        }
        if self.emotion_regulation:
            primary_emotion = self.emotion_regulation[0]
            if primary_emotion in emotion_desc:
                defense_insights.append(emotion_desc[primary_emotion])

        if defense_insights:
            parts.append("【应对方式】" + "；".join(defense_insights))

        # 第五层：原型与叙事偏好
        narrative_insights = []

        # 原型解读
        archetype_desc = {
            "hero": "你认同英雄的成长与奋斗，喜欢主角逆袭的故事",
            "sage": "你追求智慧和真相，喜欢有深度思考的内容",
            "explorer": "你渴望自由和探索，喜欢冒险和发现新世界",
            "outlaw": "你有反叛精神，喜欢挑战权威和规则的故事",
            "magician": "你喜欢 transformation，渴望超越现实的限制",
            "caregiver": "你重视保护和治愈，喜欢温暖和守护的故事",
            "lover": "你追求深度的情感连接，喜欢真挚的爱情故事",
            "jester": "你享受轻松和快乐，喜欢幽默和吐槽",
            "orphan": "你渴望被理解和接纳，喜欢有共鸣的角色",
            "creator": "你追求创造和自我表达，喜欢艺术和创作题材",
            "ruler": "你喜欢掌控和秩序，偏好权力和战略题材",
            "innocent": "你保持纯真，喜欢美好和治愈的世界",
            "everyman": "你能认同普通人，喜欢真实和接地气的故事",
            "seeker": "你在寻找人生意义，喜欢有哲学深度的内容",
            "destroyer": "你能接受黑暗和破坏，喜欢有冲击力的内容",
        }
        if self.archetype in archetype_desc:
            narrative_insights.append(archetype_desc[self.archetype])

        # 叙事类型
        narrative_desc = {
            "progressive": "你喜欢主角不断成长进步的叙事",
            "redemption": "你喜欢救赎和浪子回头的故事",
            "exploration": "你喜欢探索未知世界的叙事",
            "stability": "你喜欢平和稳定的日常叙事",
            "contamination": "你能接受悲剧和失去的叙事",
            "regressive": "你喜欢怀旧和回归的叙事",
        }
        if self.narrative_type in narrative_desc:
            narrative_insights.append(narrative_desc[self.narrative_type])

        if narrative_insights:
            parts.append("【故事偏好】" + "；".join(narrative_insights))

        # 第六层：世界观与价值取向
        value_insights = []

        # 世界观
        worldview_desc = {
            "just_world": "你相信善有善报，喜欢正义必胜的故事",
            "unjust_world": "你能接受现实的残酷，喜欢有深度的作品",
            "magical_world": "你喜欢奇幻设定，享受超现实的想象",
            "dystopian": "你关注社会问题，喜欢有批判性的作品",
        }
        if self.worldview in worldview_desc:
            value_insights.append(worldview_desc[self.worldview])

        # 道德基础
        if self.moral_foundations:
            primary_moral = self.moral_foundations[0]
            moral_desc = {
                "care_harm": "你重视关怀和避免伤害，喜欢有温度的故事",
                "fairness_cheating": "你重视公平正义，喜欢揭露真相的故事",
                "loyalty_betrayal": "你重视忠诚和信任，喜欢羁绊深刻的故事",
                "authority_subversion": "你关注权力关系，喜欢挑战权威的故事",
                "sanctity_degradation": "你能接受黑暗题材，不回避禁忌话题",
                "liberty_oppression": "你追求自由，喜欢反抗压迫的故事",
            }
            if primary_moral in moral_desc:
                value_insights.append(moral_desc[primary_moral])

        if value_insights:
            parts.append("【价值取向】" + "；".join(value_insights))

        # 组合生成最终解读
        if not parts:
            return "你的观看偏好正在被分析中，我们将为你推荐多样化的内容。"

        # 输出所有维度，生成更详细的评语
        result = "。".join(parts) + "。"

        # 添加个性化推荐总结
        summary_parts = []
        summary_parts.append("\n\n【推荐总结】")
        summary_parts.append(f"综合你的心理画像，你是一个{self._get_personality_summary()}的人。")
        summary_parts.append(f"在番剧选择上，你倾向于{self._get_preference_summary()}。")
        summary_parts.append(f"我们为你推荐的内容将兼顾你已有的偏好，同时适度拓展你的视野，帮助你发现更多可能喜欢的作品。")

        return result + "".join(summary_parts)

    def _get_personality_summary(self) -> str:
        """生成性格总结"""
        traits = []
        o = self.big_five["O"]
        c = self.big_five["C"]
        e = self.big_five["E"]
        a = self.big_five["A"]
        n = self.big_five["N"]

        if o > 0.6:
            traits.append("富有想象力和好奇心")
        elif o < 0.4:
            traits.append("务实稳重")

        if c > 0.6:
            traits.append("有条理且自律")
        elif c < 0.4:
            traits.append("随性自由")

        if e > 0.6:
            traits.append("外向热情")
        elif e < 0.4:
            traits.append("内敛沉静")

        if a > 0.6:
            traits.append("温暖体贴")
        elif a < 0.4:
            traits.append("理性独立")

        if n > 0.6:
            traits.append("情感细腻敏感")
        elif n < 0.4:
            traits.append("情绪稳定从容")

        return "、".join(traits[:3]) if traits else "独特"

    def _get_preference_summary(self) -> str:
        """生成偏好总结"""
        prefs = []

        # 基于原型
        archetype_pref = {
            "hero": "热血励志的成长故事",
            "sage": "有深度思考和哲理的作品",
            "explorer": "充满冒险和探索的奇幻世界",
            "caregiver": "温暖治愈的守护故事",
            "lover": "真挚动人的感情故事",
            "jester": "轻松愉快的幽默内容",
            "orphan": "能引起共鸣的现实题材",
            "creator": "富有创意和艺术感的作品",
            "innocent": "美好纯真的理想世界",
            "everyman": "贴近生活的真实故事",
            "seeker": "有哲学深度的意义探索",
            "outlaw": "挑战规则的叛逆故事",
        }
        if self.archetype in archetype_pref:
            prefs.append(archetype_pref[self.archetype])

        # 基于叙事偏好
        narrative_pref = {
            "progressive": "主角不断成长的励志叙事",
            "redemption": "有救赎和转变的深刻故事",
            "exploration": "世界观宏大的冒险叙事",
            "stability": "温馨平和的日常叙事",
            "contamination": "能触动深层情感的作品",
        }
        if self.narrative_type in narrative_pref:
            prefs.append(narrative_pref[self.narrative_type])

        return "、".join(prefs[:2]) if prefs else "多样化的作品"

    def get_detailed_profile_text(self) -> str:
        """生成详细的心理画像文本（用于展示给用户）"""
        lines = []

        # 标题
        lines.append("=== 你的心理画像 ===")
        lines.append("")

        # 人格维度
        lines.append("【人格特征】")
        lines.append(f"  开放性: {'高' if self.big_five['O'] > 0.6 else '中' if self.big_five['O'] > 0.4 else '低'}")
        lines.append(f"  尽责性: {'高' if self.big_five['C'] > 0.6 else '中' if self.big_five['C'] > 0.4 else '低'}")
        lines.append(f"  外向性: {'高' if self.big_five['E'] > 0.6 else '中' if self.big_five['E'] > 0.4 else '低'}")
        lines.append(f"  随和性: {'高' if self.big_five['A'] > 0.6 else '中' if self.big_five['A'] > 0.4 else '低'}")
        lines.append(f"  神经质: {'高' if self.big_five['N'] > 0.6 else '中' if self.big_five['N'] > 0.4 else '低'}")
        lines.append(f"  MBTI类型: {self.mbti}")
        lines.append(f"  九型人格: {self.enneagram}")
        lines.append("")

        # 需求维度
        lines.append("【核心需求】")
        maslow_desc = {
            1: "生理需求", 2: "安全需求", 3: "归属需求", 4: "尊重需求",
            5: "认知需求", 6: "审美需求", 7: "自我实现", 8: "超越需求"
        }
        lines.append(f"  马斯洛层次: {maslow_desc.get(self.maslow_level, '未知')}")
        primary_sdt = max(self.sdt_needs, key=self.sdt_needs.get)
        sdt_desc = {"autonomy": "自主", "competence": "能力", "relatedness": "关系"}
        lines.append(f"  核心动机: {sdt_desc.get(primary_sdt, '未知')}")
        lines.append(f"  调节焦点: {'进取型' if self.regulatory_focus == 'promotion' else '防御型'}")
        lines.append("")

        # 情感维度
        lines.append("【情感模式】")
        attachment_desc = {
            "secure": "安全型依恋",
            "anxious_preoccupied": "焦虑型依恋",
            "dismissive_avoidant": "回避型依恋",
            "fearful_avoidant": "恐惧型依恋"
        }
        lines.append(f"  依恋类型: {attachment_desc.get(self.attachment, '未知')}")
        if self.defense_mechanisms:
            lines.append(f"  主要防御: {self.defense_mechanisms[0]}")
        lines.append("")

        # 叙事维度
        lines.append("【叙事偏好】")
        archetype_desc = {
            "hero": "英雄", "sage": "智者", "explorer": "探索者",
            "outlaw": "叛逆者", "magician": "魔法师", "caregiver": "照顾者",
            "lover": "情人", "jester": "弄臣", "orphan": "孤儿",
            "creator": "创造者", "ruler": "统治者", "innocent": "天真者",
            "everyman": "普通人", "seeker": "追寻者", "destroyer": "毁灭者"
        }
        lines.append(f"  主导原型: {archetype_desc.get(self.archetype, '未知')}")
        narrative_desc = {
            "progressive": "进步叙事", "redemption": "救赎叙事",
            "exploration": "探索叙事", "stability": "稳定叙事",
            "contamination": "悲剧叙事", "regressive": "怀旧叙事"
        }
        lines.append(f"  叙事类型: {narrative_desc.get(self.narrative_type, '未知')}")
        worldview_desc = {
            "just_world": "公正世界", "unjust_world": "不公世界",
            "magical_world": "魔法世界", "dystopian": "反乌托邦"
        }
        lines.append(f"  世界观: {worldview_desc.get(self.worldview, '未知')}")

        return "\n".join(lines)


# ============================================================
# 测试入口
# ============================================================
if __name__ == "__main__":
    test_anime = {
        "tags": ["Psychological", "Sci-Fi", "Thriller", "Drama"],
        "tags_cn": ["心理", "科幻", "悬疑", "剧情"],
        "format": "TV",
        "mean_score": 8.5,
        "popularity": 500,
        "favourites": 10000,
    }

    profile = ComprehensivePsychProfile()
    profile.build_from_anime(test_anime)

    import json
    print(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False))
    print("\n推荐方向:")
    print(json.dumps(profile.get_recommendation_direction(), indent=2, ensure_ascii=False))
