# -*- coding: utf-8 -*-
"""RA2 研究用抓取工具: 搜索(Bing/Baidu) + 网页转文本。
用法:
  python web.py search "查询词"            -> 打印搜索结果(标题|URL)
  python web.py get <url> <outfile>        -> 抓取网页并转纯文本存文件
中文通过 UTF-8 源文件传入, 避免 shell 编码问题。
"""
import sys, os, re, html, json, io
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})


def search_bing(q, n=15):
    """Bing 的 RSS 输出, 最稳的解析通道。"""
    r = S.get("https://cn.bing.com/search", params={"q": q, "format": "rss", "count": 30}, timeout=25)
    r.encoding = "utf-8"
    out = []
    for it in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<description>(.*?)</description>", it, re.S)
        if not (t and l):
            continue
        out.append({
            "title": html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1))).strip(),
            "url": html.unescape(l.group(1)).strip(),
            "snippet": html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", d.group(1))).strip()[:220] if d else "",
        })
        if len(out) >= n:
            break
    return out


def search_baidu(q, n=15):
    r = S.get("https://www.baidu.com/s", params={"wd": q, "rn": 20}, timeout=25)
    t = r.text
    out, seen = [], set()
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        u, ti = html.unescape(m.group(1)), re.sub(r'<[^>]+>', '', html.unescape(m.group(2))).strip()
        if u in seen or not ti:
            continue
        seen.add(u)
        out.append({"title": ti, "url": u, "snippet": ""})
        if len(out) >= n:
            break
    return out


def to_text(h):
    h = re.sub(r'(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?is)<!--.*?-->', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>', '\n', h)
    h = re.sub(r'(?i)</(p|div|li|tr|h[1-6]|td|th)>', '\n', h)
    h = re.sub(r'(?i)<(p|div|li|tr|h[1-6])[^>]*>', '\n', h)
    t = re.sub(r'<[^>]+>', ' ', h)
    t = html.unescape(t)
    t = re.sub(r'[ \t\u00a0]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t)
    return t.strip()


def get(url, out):
    r = S.get(url, timeout=30)
    if not r.encoding or r.encoding.lower() in ("iso-8859-1",):
        r.encoding = r.apparent_encoding or "utf-8"
    txt = to_text(r.text)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write("URL: %s\nSTATUS: %s\n\n%s" % (url, r.status_code, txt))
    print("saved %s (%d chars, status %s)" % (out, len(txt), r.status_code))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "search":
        q = sys.argv[2]
        eng = sys.argv[3] if len(sys.argv) > 3 else "bing"
        res = search_bing(q) if eng == "bing" else search_baidu(q)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif cmd == "get":
        get(sys.argv[2], sys.argv[3])
