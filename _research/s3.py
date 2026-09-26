# -*- coding: utf-8 -*-
"""定向检索: site: 短查询 + 直接抓取候选页。"""
import json, io, sys, os
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

D = __file__.rsplit("\\", 1)[0]
QUERIES = [
    "红警2 攻略 战术", "红警2 战术 教学", "红警2 苏军 开局",
    "红警2 兵种 克制", "红警2 单位数据", "红警2 经济 矿车",
    "红警2 微操 技巧", "红警2 快攻 rush", "红警2 大兵团 作战",
    "site:uc129.com 战术", "site:uc129.com 攻略", "site:zhihu.com 红警2 战术",
    "site:bilibili.com 红警2 教学", "site:baike.baidu.com 犀牛坦克",
    "红警2 共和国之辉 攻略", "红色警戒2 开局 建造顺序",
]
out = {}
for q in QUERIES:
    try:
        res = web.search_bing(q, n=10)
    except Exception as e:
        res = [{"error": str(e)}]
    out[q] = res
    print("###", q)
    for r in res:
        if "error" in r:
            print("  ERR", r["error"]); continue
        print("  -", r["title"][:70], "|", r["url"][:110])
with io.open(os.path.join(D, "search3.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved search3.json")
