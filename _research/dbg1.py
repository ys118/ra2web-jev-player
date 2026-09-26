# -*- coding: utf-8 -*-
"""调试: Bing RSS/HTML 结构 + 百度结构, 找出可解析的搜索通道。"""
import re, html, io, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

q = "红警2 苏军 攻略 开局"

# 1) Bing RSS
try:
    r = web.S.get("https://cn.bing.com/search", params={"q": q, "format": "rss"}, timeout=25)
    print("RSS status", r.status_code, "len", len(r.text))
    items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
    print("RSS items:", len(items))
    for it in items[:8]:
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<description>(.*?)</description>", it, re.S)
        print("  -", html.unescape(t.group(1))[:60] if t else "?")
        print("   ", html.unescape(l.group(1))[:120] if l else "?")
        if d:
            print("   ", html.unescape(d.group(1))[:120].replace("\n", " "))
except Exception as e:
    print("RSS ERR", e)

# 2) Bing HTML structure probe
try:
    r = web.S.get("https://cn.bing.com/search", params={"q": q}, timeout=25)
    r.encoding = "utf-8"
    t = r.text
    print("\nHTML status", r.status_code, "len", len(t))
    print("b_algo count:", t.count("b_algo"))
    i = t.find("b_algo")
    print("snippet:", t[i-100:i+500].replace("\n", " ") if i > 0 else "not found")
except Exception as e:
    print("HTML ERR", e)
