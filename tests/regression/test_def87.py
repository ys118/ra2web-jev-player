# -*- coding: utf-8 -*-
"""[第87局 防御纵深包] 离线场景测试(用户拍板三优化点全执行):
28) ①第二兵营前置(首厂落地即补, 步兵双队列对爆 rush 产能, cash>=1200 闸)
    ②GARRISON 地板 4→8(86 局 20+ 驻军仍被磨穿) ③哨炮 2→3 座(75/76/83/86
    四局 rush 死法实证双塔纵深不足)。"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))   # tests/regression/*.py -> 仓库根/src

from ra2web_jev_player.strategy import planner

fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}


def mk_state(cash=2000, n_weap=1, n_bar=1, n_ref=4, gdef=2, e2_n=2,
             tanks=0, rush=False, threat=0):
    BASE = ["NACNST", "NAPOWR", "NAREFN"]
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE)]
    for i in range(n_ref):
        mine.append(unit("r%d" % i, "NAREFN", 2, (15 + i, 12)))
    for i in range(n_weap):
        mine.append(unit("w%d" % i, "NAWEAP", 2, (20 + i, 10)))
    for i in range(n_bar):
        mine.append(unit("h%d" % i, "NAHAND", 2, (25 + i, 10)))
    for i in range(gdef):
        mine.append(unit("g%d" % i, "NALASR", 2, (30 + i, 14)))
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(e2_n):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i, 18)))
    for i in range(tanks):
        mine.append(unit("t%d" % i, "HTNK", 7, (35 + i, 14)))
    hos = [{"id": "h%d" % i, "n": "E2", "o": 3, "tl": [22 + (i % 3), 22 + (i % 3)]}
           for i in range(threat)]
    s = {"t": 700, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"],
                1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 300, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.rush_defense = rush
    mem.v3_seen_t = -10**9
    mem.long_fire_t = -10**9
    return s, mem


# ---- 28a 第二兵营前置: 首厂+单兵营+cash1500 → OPENING BUILD NAHAND ----
s, mem = mk_state(cash=1500, n_weap=1, n_bar=1)
act = planner.opening_build(s, mem)
check("28a 首厂+单兵营 → 第二兵营", bool(act) and act.get("name") == "NAHAND",
      str(act))

# ---- 28b 首厂未落地 → 不前置(工厂优先) ----
s, mem = mk_state(cash=1500, n_weap=0, n_bar=1)
act = planner.opening_build(s, mem)
check("28b 无厂 → 不前置兵营", not (act and act.get("name") == "NAHAND"),
      str(act))

# ---- 28c 双兵营 → 封顶不再下 ----
s, mem = mk_state(cash=1500, n_weap=1, n_bar=2)
act = planner.opening_build(s, mem)
check("28c 双兵营封顶", not (act and act.get("name") == "NAHAND"), str(act))

# ---- 28d 哨炮 2→3: rush 模式 cash600 → 第三座 DEFLINE ----
s, mem = mk_state(cash=600, gdef=2, rush=True, threat=6)
_st, acts, logs = planner.checklist(s, (10, 10), "defend", mem)
d = [l for l in logs if "DEFLINE" in l]
check("28d rush 模式哨炮2 → 第三座", bool(d), str(d[:1]))

# ---- 28e 哨炮 3 → 封顶 ----
s, mem = mk_state(cash=600, gdef=3, rush=True, threat=6)
_st, acts, logs = planner.checklist(s, (10, 10), "defend", mem)
check("28e 哨炮3封顶", not any("DEFLINE" in l for l in logs))

# ---- 28f GARRISON 地板 8: e2=4 → 仍产(旧地板 4 不产) ----
s, mem = mk_state(e2_n=4)
_st, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
o = [a for a in acts if a.get("name") == "E2" and a.get("act") == "produce"]
check("28f e2=4 < 新地板8 → 驻军补产", len(o) == 1,
      str([l for l in logs if "GARRISON" in l][:1]))

# ---- 28g e2=8 → 达标不产 ----
s, mem = mk_state(e2_n=8)
_st, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
o = [a for a in acts if a.get("name") == "E2" and a.get("act") == "produce"]
check("28g e2=8 达标 → 不产", not o)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 7 场景通过 ===")
