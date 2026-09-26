# -*- coding: utf-8 -*-
"""批量搜索 v2: 更贴近战术/数据内容的查询词。"""
import json, io, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

QUERIES = [
    "红色警戒2 苏军 开局流程 电厂 矿厂 兵营 战车工厂 顺序",
    "红警2 犀牛坦克 快攻 战术 打法",
    "红色警戒2 单位数据 表 犀牛 灰熊 血量 攻击 造价",
    "红警2 经济 矿车 采矿 效率 技巧",
    "红色警戒2 微操 技巧 集火 拉扯 坦克",
    "红警2 对战 心得 高手 战术 大局观",
    "红色警戒2 盟军 战术 光棱 幻影 飞行兵",
    "红警2 防御 建筑 磁暴线圈 防空炮 布局",
]

out = {}
for q in QUERIES:
    try:
        res = web.search_bing(q)
    except Exception as e:
        res = [{"error": str(e)}]
    out[q] = res
    print("###", q)
    for r in res:
        if "error" in r:
            print("  ERR", r["error"]); continue
        print("  -", r["title"][:75])
        print("    ", r["url"][:135])
        if r.get("snippet"):
            print("    ", r["snippet"][:170].replace("\n", " "))
with io.open(__file__.rsplit("\\", 1)[0] + "\\search2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved search2.json")
