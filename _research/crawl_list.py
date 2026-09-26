# -*- coding: utf-8 -*-
"""抓取 uc129 攻略/战术栏目列表页, 提取文章链接。"""
import re, os, sys, io, json
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

D = __file__.rsplit("\\", 1)[0]
LISTS = [
    "https://www.uc129.com/zhanshu/1.0/list_78_1.html",
    "https://www.uc129.com/zhanshu/1.0/list_78_2.html",
    "https://www.uc129.com/zhanshu/1.0/list_78_3.html",
    "https://www.uc129.com/zhanshu/",
    "https://gl.ali213.net/z/86703/",
    "https://gl.ali213.net/html/2025-5/1656275.html",
]
links = {}
for u in LISTS:
    try:
        r = web.S.get(u, timeout=25)
        r.encoding = r.apparent_encoding or "utf-8"
        t = r.text
        found = set()
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{4,60})</a>', t):
            href, txt = m.group(1), m.group(2).strip()
            if not re.search(r'红警|红色警戒|攻略|战术|技巧|开局|兵种|矿|坦克|微操|心得', txt):
                continue
            if href.startswith("/"):
                href = "https://www.uc129.com" + href if "uc129" in u else "https://gl.ali213.net" + href
            if href.startswith("http"):
                found.add((txt, href))
        print("### %s -> %d links" % (u, len(found)))
        for txt, href in sorted(found):
            print("   ", txt[:50], "|", href[:110])
            links[href] = txt
    except Exception as e:
        print("### %s ERR %s" % (u, e))
with io.open(os.path.join(D, "listlinks.json"), "w", encoding="utf-8") as f:
    json.dump(links, f, ensure_ascii=False, indent=1)
print("total", len(links))
