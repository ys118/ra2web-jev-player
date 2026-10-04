# -*- coding: utf-8 -*-
"""[第69局 持久战经济时序] 离线场景测试:
15) 二厂双闸拆解——精炼厂缺额优先, factory2_cash=1800 即真闸(去 build_gate 叠加);
16) 矿车门槛降档 600/900/1200。"""
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


def open_state(t, n_ref, cash, extra=()):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    for i in range(n_ref - 1):                       # BASE_BLD 已含 1 精炼厂
        mine.append(unit("r%d" % i, "NAREFN", 2, (20 + i, 10)))
    mine += [unit("h1", "HARV", 7, (12, 12))]
    for i, n in enumerate(extra):
        mine.append(unit("x%d" % i, n, 2, (30 + i, 10)))
    s = {"t": t, "mine": mine, "hostile": [], "enemy": [],
         "av": {0: ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"],
                1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": 0, "s": 0, "items": []}],
         "me": {"credits": cash, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    return s, planner.BattleMemory()


def econ_state(n_harv, cash, t=700, n_ref=1):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    for i in range(n_ref - 1):
        mine.append(unit("rr%d" % i, "NAREFN", 2, (20 + i, 10)))
    for i in range(n_harv):
        mine.append(unit("h%d" % i, "HARV", 7, (12 + i, 12)))
    s = {"t": t, "mine": mine, "hostile": [], "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    return s, planner.BattleMemory()


# ---- 15: 二厂时序 ----
s, mem = open_state(700, 2, 3000)
act = planner.opening_build(s, mem)
check("15a ref缺额+现金3000→精炼厂优先", act is not None and act["name"] == "NAREFN",
      str(act))

s, mem = open_state(700, 3, 1900)
act = planner.opening_build(s, mem)
check("15b ref满+现金1900→二厂(旧码为None)", act is not None and act["name"] == "NAWEAP",
      str(act))

s, mem = open_state(700, 3, 1700)
act = planner.opening_build(s, mem)
check("15c 现金1700<1800→不下单", act is None, str(act))

s, mem = open_state(2500, 3, 100)
act = planner.opening_build(s, mem)
check("15d late_game(t>2400)→无条件二厂", act is not None and act["name"] == "NAWEAP",
      str(act))

s, mem = open_state(700, 2, 2000)
act = planner.opening_build(s, mem)
check("15e ref买不起(2900)+现金2000→先二厂", act is not None and act["name"] == "NAWEAP",
      str(act))

# ---- 16: 矿车门槛 600/900/1200 ----
s, mem = econ_state(1, 650)
_, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
check("16a 1车+现金650→补第2车(旧门槛800不下)", any(
    a.get("act") == "produce" and a.get("name") == "HARV" for a in acts), str(logs))

s, mem = econ_state(1, 550)
_, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
check("16b 现金550<600→不补车", not any(
    a.get("name") == "HARV" for a in acts), str(logs))

s, mem = econ_state(2, 950, n_ref=2)
_, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
check("16c 2车+现金950→补第3车(旧门槛1200不下)", any(
    a.get("name") == "HARV" for a in acts), str(logs))

s, mem = econ_state(3, 1250, n_ref=2)
_, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
check("16d 3车+现金1250→补第4车(旧门槛1500不下)", any(
    a.get("name") == "HARV" for a in acts), str(logs))

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(0 if not fails else 1)
