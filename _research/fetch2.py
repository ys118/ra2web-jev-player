# -*- coding: utf-8 -*-
"""抓取补充页面: 单位数据/多页文章/萌娘百科单位页。"""
import os, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

D = __file__.rsplit("\\", 1)[0]
OUT = os.path.join(D, "pages")
MORE = [
    ("soviet-units-p2", "https://www.uc129.com/zhanshu/1.006/27283_2.html"),
    ("soviet-units-p3", "https://www.uc129.com/zhanshu/1.006/27283_3.html"),
    ("soviet-units-p4", "https://www.uc129.com/zhanshu/1.006/27283_4.html"),
    ("soviet-units-p5", "https://www.uc129.com/zhanshu/1.006/27283_5.html"),
    ("tank-ops-p2", "https://www.uc129.com/zhanshu/1.006/20631_2.html"),
    ("tank-ops-p3", "https://www.uc129.com/zhanshu/1.006/20631_3.html"),
    ("strongest-nation-p2", "https://www.uc129.com/zhanshu/1.006/29121_2.html"),
    ("strongest-nation-p3", "https://www.uc129.com/zhanshu/1.006/29121_3.html"),
    ("moegirl-rhino", "https://zh.moegirl.org.cn/犀牛坦克"),
    ("moegirl-apoc", "https://zh.moegirl.org.cn/天启坦克"),
    ("moegirl-prism", "https://zh.moegirl.org.cn/光棱坦克"),
    ("moegirl-grizzly", "https://zh.moegirl.org.cn/灰熊坦克"),
    ("moegirl-drone", "https://zh.moegirl.org.cn/恐怖机器人"),
    ("moegirl-ifv", "https://zh.moegirl.org.cn/多功能步兵车"),
]
for name, url in MORE:
    try:
        web.get(url, os.path.join(OUT, name + ".txt"))
    except Exception as e:
        print("ERR", name, e)
