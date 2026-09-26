# -*- coding: utf-8 -*-
"""抓取选定的红警2 攻略文章 -> _research/pages/*.txt"""
import os, sys, io, json
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import web

D = __file__.rsplit("\\", 1)[0]
OUT = os.path.join(D, "pages")
os.makedirs(OUT, exist_ok=True)

ARTICLES = [
    ("su-yilake-zhanhs", "zhanshu/1.006/30050.html"),      # 苏军(主伊拉克)战术技巧
    ("allied-tactics", "zhanshu/1.006/29817.html"),        # 盟军战术分享
    ("unit-ranking", "zhanshu/1.006/27999.html"),          # 兵种对比排行榜
    ("zatan-summary", "zhanshu/1.006/23536.html"),         # 攻略战术杂谈汇总大全
    ("soviet-units", "zhanshu/1.006/27283.html"),          # 苏联兵种及攻略大全
    ("rhino-cross", "zhanshu/1.006/27267.html"),           # 犀牛坦克死亡十字架
    ("miner-efficiency", "zhanshu/1.006/22902.html"),      # 矿车效率
    ("online-tips", "zhanshu/1.006/29543.html"),           # 联机对战攻略技巧
    ("team-tips", "zhanshu/1.006/29924.html"),             # 战队玩家技巧分享
    ("stance-modes", "zhanshu/1.006/27513.html"),          # 移动攻击/警戒/巡逻/保护/防御
    ("hongjing-xinjing", "zhanshu/1.006/29345.html"),      # 红警心经
    ("tank-wheel-pull", "zhanshu/1.006/20623.html"),       # 坦克大战轮拉操作
    ("tank-ops", "zhanshu/1.006/20631.html"),              # 坦克操作方法
    ("apoc-rad", "zhanshu/1.006/23077.html"),              # 天启+辐射战术
    ("strongest-nation", "zhanshu/1.006/29121.html"),      # 最强国家 科技对比
    ("infant-test", "zhanshu/1.006/27355.html"),           # 美国大兵vs动员兵 能力测试
    ("fly-tactics", "zhanshu/1.0/26730.html"),             # 飞行兵战术(共辉)
    ("practical-guide", "zhanshu/1.006/27652.html"),       # 实用攻略秘籍
    ("spider-miner", "zhanshu/1.006/24110.html"),          # 蜘蛛上牛(矿车)
    ("skills-buff", "zhanshu/1.006/26269.html"),           # 间接技能和buff
    ("ice-map-1v1", "zhanshu/1.006/26756.html"),           # 冰天雪地2v2新手攻略
    ("libya", "zhanshu/1.006/24247.html"),                 # 利比亚使用攻略
    ("cuba-boom", "zhanshu/1.006/26259.html"),             # 古巴爆破战术
    ("b2map", "zhanshu/1.006/21180.html"),                 # B2地图攻略
    ("1v7cold", "zhanshu/1.0/20141.html"),                 # 1v7冷酷电脑
    ("ghost-tank", "zhanshu/1.0/7421.html"),               # 幻影坦克使用
    ("quick-start", "zhanshu/1.0/5371.html"),              # 共辉玩法速成
    ("vs-tips", "zhanshu/1.0/21846.html"),                 # 共辉对战技巧秘籍
    ("yili-tactics", "zhanshu/yuri/"),                      # 尤里攻略列表
    ("ali213-guide", "https://gl.ali213.net/html/2025-5/1656275.html"),  # 共辉攻略技巧大全
]

for name, path in ARTICLES:
    url = path if path.startswith("http") else "https://www.uc129.com/" + path
    out = os.path.join(OUT, name + ".txt")
    try:
        web.get(url, out)
    except Exception as e:
        print("ERR", name, url, e)
