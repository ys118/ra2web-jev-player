# -*- coding: utf-8 -*-
"""对账: 文档关键数值 vs rules.ini 生成的 RA2-UNITS.json / 原始 ini。

RA2-UNITS.json 位置：优先 repo 根的 knowledge/（归档布局），其次 repo 根。
"""
import json, io, os, re, collections

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cand = [os.path.join(B, "knowledge", "RA2-UNITS.json"), os.path.join(B, "RA2-UNITS.json")]
_path = next((p for p in _cand if os.path.exists(p)), _cand[0])
data = json.load(io.open(_path, encoding="utf-8"))
print("对账数据源:", _path)
G = data["groups"]; W = data["warheads"]; GEN = data["general"]

def u(code):
    for g in G.values():
        if code in g:
            return g[code]
    return None

CHECKS = []
def ck(desc, got, want):
    ok = got == want
    CHECKS.append((ok, desc, got, want))

# 单位核心数值 (文档 §2 使用的数字)
ck("犀牛 造价/血", (u("HTNK")["cost"], u("HTNK")["hp"]), (900, 400))
ck("天启 造价/血", (u("APOC")["cost"], u("APOC")["hp"]), (1700, 800))
ck("灰熊 造价/血", (u("MTNK")["cost"], u("MTNK")["hp"]), (750, 300))
ck("蜘蛛 造价/血/速", (u("DRON")["cost"], u("DRON")["hp"], u("DRON")["speed"]), (400, 50, 12))
ck("防空履带车 造价/血", (u("HTK")["cost"], u("HTK")["hp"]), (500, 180))
ck("矿车 造价/血/容量", (u("HARV")["cost"], u("HARV")["hp"], u("HARV")["storage"]), (1400, 1000, 45))
ck("超时空矿车 容量", u("CMIN")["storage"], 25)
ck("动员兵 造价/血", (u("E2")["cost"], u("E2")["hp"]), (90, 130))
ck("美国大兵 造价/血", (u("E1")["cost"], u("E1")["hp"]), (180, 125))
ck("基洛夫 造价/血", (u("ZEP")["cost"], u("ZEP")["hp"]), (2000, 1600))
ck("光棱 造价/血", (u("SREF")["cost"], u("SREF")["hp"]), (1200, 150))
ck("幻影 造价/血", (u("MGTK")["cost"], u("MGTK")["hp"]), (1000, 200))
ck("辐射 造价/血", (u("DESO")["cost"], u("DESO")["hp"]), (600, 150))
ck("磁暴步兵 造价/血", (u("SHK")["cost"], u("SHK")["hp"]), (500, 200))

# 武器
ck("犀牛炮 伤害/射程", (u("HTNK")["primary"]["damage"], u("HTNK")["primary"]["range"]), (90, 5.75))
ck("灰熊炮 伤害/射程", (u("MTNK")["primary"]["damage"], u("MTNK")["primary"]["range"]), (65, 5))
ck("光棱炮 伤害/射程", (u("SREF")["primary"]["damage"], u("SREF")["primary"]["range"]), (100, 10))
ck("幻影炮 伤害/射程", (u("MGTK")["primary"]["damage"], u("MGTK")["primary"]["range"]), (100, 7))
ck("天启炮 伤害×发数", (u("APOC")["primary"]["damage"], u("APOC")["primary"].get("burst")), (100, 2))
ck("天启对空 射程", u("APOC")["secondary"]["range"], 8)
ck("防空履带车 对空射程", u("HTK")["secondary"]["range"], 10)
ck("基洛夫炸弹 伤害", u("ZEP")["primary"]["damage"], 250)

# 建筑/防御
ck("磁能电厂 造价/电力", (u("NAPOWR")["cost"], u("NAPOWR")["power"]), (600, 150))
ck("盟军电厂 造价/电力", (u("GAPOWR")["cost"], u("GAPOWR")["power"]), (800, 200))
ck("精炼厂 造价/电力/库存", (u("NAREFN")["cost"], u("NAREFN")["power"], u("NAREFN")["storage"]), (2000, -50, 200))
ck("兵营 造价/电力", (u("NAHAND")["cost"], u("NAHAND")["power"]), (500, -10))
ck("战车工厂 造价/电力/前置", (u("NAWEAP")["cost"], u("NAWEAP")["power"], u("NAWEAP")["prereq"]), (2000, -25, "PROC,NAHAND,NACNST"))
ck("雷达 造价/电力", (u("NARADR")["cost"], u("NARADR")["power"]), (800, -50))
ck("作战实验室 造价/电力", (u("NATECH")["cost"], u("NATECH")["power"]), (2000, -100))
ck("磁暴线圈 造价/血/电力", (u("TESLA")["cost"], u("TESLA")["hp"], u("TESLA")["power"]), (1500, 600, -75))
ck("防空炮 造价/血/电力", (u("NAFLAK")["cost"], u("NAFLAK")["hp"], u("NAFLAK")["power"]), (1000, 900, -50))
ck("哨戒炮 造价/血", (u("NALASR")["cost"], u("NALASR")["hp"]), (500, 400))
ck("哨戒炮 不耗电(power=0)", (u("NALASR") or {}).get("power"), 0)
ck("巨炮 造价/电力", (u("GTGCAN")["cost"], u("GTGCAN")["power"]), (2000, -200))
ck("巨炮 射程/伤害", (u("GTGCAN")["primary"]["range"], u("GTGCAN")["primary"]["damage"]), (15, 150))
ck("线圈 伤害/射程", (u("TESLA")["primary"]["damage"], u("TESLA")["primary"]["range"]), (200, 7))
ck("防空炮 伤害/射程", (u("NAFLAK")["primary"]["damage"], u("NAFLAK")["primary"]["range"]), (40, 12))
ck("哨戒炮 伤害/射程", (u("NALASR")["primary"]["damage"], u("NALASR")["primary"]["range"]), (50, 5.5))

# 弹头倍率结论
ck("AP 对重甲=100%", W["AP"]["heavy"], "100%")
ck("AP 对无甲步兵=25%", W["AP"]["none"], "25%")
ck("CometWH 对建筑(wood)=200%", W["CometWH"]["wood"], "200%")
ck("CometWH 对重甲=50%", W["CometWH"]["heavy"], "50%")
ck("MirageWH 对重甲=100%", W["MirageWH"]["heavy"], "100%")
ck("MirageWH 对建筑(wood)=30%", W["MirageWH"]["wood"], "30%")
ck("小枪SA 对重甲=25%", W["SA"]["heavy"], "25%")
ck("FlakWH 对飞行兵(special_2)=150%", W["FlakWH"]["special_2"], "150%")
ck("Parasite 对建筑(wood)=0%", W["Parasite"]["wood"], "0%")
ck("RadBeam 对重甲=10%", W["RadBeamWarhead"]["heavy"], "10%")

# 全局参数
ck("BuildSpeed=.7", GEN["BuildSpeed"], ".7")
ck("MultipleFactory=0.5", GEN["MultipleFactory"], "0.5")
ck("HarvestersPerRefinery=2", GEN["HarvestersPerRefinery"], "2")
ck("PurifierBonus=.25", GEN["PurifierBonus"], ".25")
ck("SpyMoneyStealPercent=.5", GEN["SpyMoneyStealPercent"], ".5")
ck("VeteranROF/速度/视野/装甲", (GEN["VeteranROF"], GEN["VeteranSpeed"], GEN["VeteranSight"], GEN["VeteranArmor"]), ("0.6", "1.2", "1.2", "1.5"))
ck("缺电生产上限 .5", GEN["MaxLowPowerProductionSpeed"], ".5")
ck("出售返还 50%", GEN["RefundPercent"], "50%")

bad = [c for c in CHECKS if not c[0]]
for ok, desc, got, want in CHECKS:
    print(("OK  " if ok else "FAIL"), desc, "| 实得:", got, "| 期望:", want)
print("\n合计 %d 项, 通过 %d, 失败 %d" % (len(CHECKS), len(CHECKS) - len(bad), len(bad)))
