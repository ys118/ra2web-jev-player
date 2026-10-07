# -*- coding: utf-8 -*-
"""[第97局 打破僵局包(用户反馈)] 离线场景测试:
34) ①AIR-RESPONSE: 可见敌空中单位 → HTK 优先补产(帽内, 插坦克线之前)
    ——96 局实证: 敌空军压制+我方 aav=0 → 坦克每次出击被 AIR-EVADE 赶回家
    = 死循环僵持; ②STAGING 前沿集结(不再回基地转圈)+阈值 8→5。
"""
import sys
sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")

from ra2web_jev_player.strategy import planner

fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}


BASE_BLD = ["NACNST", "NAPOWR", "NAREFN", "NAHAND", "NAWEAP"]
HOME = (10, 10)


def mk_state(cash=3000, air=(), tanks=6):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(tanks):
        mine.append(unit("t%d" % i, "HTNK", 7, (14 + i % 3, 14 + i // 3)))
    hos = list(air)
    hos.append({"id": "w0", "n": "GAWEAP", "o": 2, "tl": [60, 60]})
    s = {"t": 900, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV", "HTK"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.enemy_base = (60, 60)
    return s, mem


# ---- 34a 可见敌空军(火箭飞行兵) → AIR-RESPONSE 产 HTK ----
air = [{"id": "j1", "n": "JUMPJET", "o": 7, "tl": [40, 40]}]
s, mem = mk_state(cash=3000, air=air)
_st, acts, logs = planner.checklist(s, HOME, "attack", mem)
htk = [a for a in acts if a.get("name") == "HTK"]
check("34a 敌火箭飞行兵在场 → HTK 反制生产",
      htk and htk[0].get("qty") >= 1
      and any("AIR-RESPONSE" in l for l in logs),
      str(htk[:1]) + str([l for l in logs if "AIR-RESPONSE" in l][:1]))

# ---- 34b 无敌空军 → 不触发 AIR-RESPONSE ----
s, mem = mk_state(cash=3000)
_st, acts, logs = planner.checklist(s, HOME, "attack", mem)
check("34b 无敌空军 → 无 AIR-RESPONSE",
      not any("AIR-RESPONSE" in l for l in logs),
      str([l for l in logs if "RESPONSE" in l][:1]))

# ---- 34c HTK 已到帽(4) → 不再产 ----
s, mem = mk_state(cash=3000, air=air, tanks=2)
for i in range(4):
    s["mine"].append(unit("k%d" % i, "HTK", 7, (18 + i, 18)))
_st, acts, logs = planner.checklist(s, HOME, "attack", mem)
htk = [a for a in acts if a.get("name") == "HTK"]
check("34c HTK 帽满 → 不产", not htk, str(htk[:1]))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 3 场景通过 ===")
