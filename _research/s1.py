# -*- coding: utf-8 -*-
"""批量搜索: 把查询词写在文件里(UTF-8), 结果存 JSON。"""
import json, io, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

QUERIES = [
    "红警2 苏军 攻略 开局 建造顺序",
    "红色警戒2 兵种 数据大全 血量 攻击力 造价",
    "红警2 高手 战术 快攻 犀牛 心得",
    "红色警戒2 盟军 攻略 战术",
    "红警2 经济 采矿 矿车 技巧",
    "红色警戒2 微操 技巧 集火 拉扯",
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
        print("  -", r["title"][:70])
        print("    ", r["url"][:130])
        if r.get("snippet"):
            print("    ", r["snippet"][:160].replace("\n", " "))
with io.open(__file__.rsplit("\\", 1)[0] + "\\search1.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved search1.json")
