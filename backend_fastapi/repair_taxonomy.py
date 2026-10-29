DORM_BUILDING_GROUPS = {
    "学生公寓": [f"公寓{i}栋" for i in range(1, 11)],
    "公共区域": [
        "启航楼（教学楼）", "远航楼（交流中心）", "领航楼（行政楼）",
        "思航轩", "护航轩", "训航轩（小平房）", "博航楼", '大国之翼',
        "文体馆", "食堂", "图书馆", "运营中心", "操场", "其他",
    ],
}
DORM_BUILDINGS = [building for group in DORM_BUILDING_GROUPS.values() for building in group]
DORM_APARTMENT_BUILDINGS = set(DORM_BUILDING_GROUPS["学生公寓"])

# 叶子故障分类 → 维修员技能大类。
# 技能键沿用旧账号中已保存的 water/electricity/furniture/other 值。
CATEGORY_TO_SKILL = {
    # 综合类：综合维修由水电、设施/家具技能共同覆盖
    "lamp": "electricity",
    "trip": "electricity",
    "sink": "water",
    "cistern": "water",
    "wardrobe": "furniture",
    "bed": "furniture",
    "desk": "furniture",
    "lock": "furniture",
    "ceiling": "furniture",
    "leak": "water",
    "toilet_clog": "water",
    "cold_faucet": "water",
    "cold_pipe": "water",
    "floor_tile": "furniture",
    "wall": "furniture",
    "door_frame": "furniture",
    "glass_window": "furniture",
    "curtain": "furniture",
    "screen_window": "furniture",
    "drying_rack": "furniture",
    "outlet": "electricity",
    "switch": "electricity",
    # 热水类
    "heat_pump": "water",
    "shower": "water",
    # 家电类
    "ac": "electricity",
    # 洗衣机暂停报修，因此不进入可派单分类
    # 其他类
    "office": "other",
    "other_item": "other",
}

SKILL_LABELS = {
    "water": "热水类",
    "electricity": "家电类",
    "furniture": "综合类",
    "other": "其他类",
}
VALID_REPAIRMAN_SKILLS = set(SKILL_LABELS)

VALID_CATEGORIES = set(CATEGORY_TO_SKILL.keys())
LEGACY_CATEGORIES = {"water", "electricity", "furniture", "other"}
