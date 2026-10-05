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

s, mem = open_state(700, 4, 1900)
act = planner.opening_build(s, mem)
check("15b(85局改) ref满+现金1900→二厂", act is not None and act["name"] == "NAWEAP",
      str(act))

s, mem = open_state(700, 4, 1700)
act = planner.opening_build(s, mem)
check("15c(85局改) 现金1700<1800→不下单", act is None, str(act))

s, mem = open_state(2500, 4, 100)
act = planner.opening_build(s, mem)
check("15d(85局改) late_game(t>2400)→无条件二厂", act is not None and act["name"] == "NAWEAP",
      str(act))

s, mem = open_state(700, 2, 2000)
act = planner.opening_build(s, mem)
# [第71局] 精炼厂缺额豁免后旧语义被取代: ref 缺额(存量<ref_cap)不再"买不起",
# 无条件优先于二厂(收入>吞吐); ref=cap 时才回落二厂(见 15d)
check("15e(71局改) ref缺额豁免: 现金2000<旧闸2900→先补矿厂",
      act is not None and act["name"] == "NAREFN", str(act))

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

# ---- 18: [第81局 经济军备竞速] 矿车硬顶 4→6 ----
# 80 局实锤: 敌被杀 66 矿车仍滚 25k 大军, 4 车收入天花板追不平产能差。
s, mem = econ_state(n_harv=4, cash=1400, n_ref=3)
act = planner.opening_build(s, mem) or planner.checklist(s, (10, 10), "develop", mem)[1]
_st, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
h4 = [a for a in acts if a.get("name") == "HARV" and a.get("act") == "produce"]
check("18a 4车+ref3 → 第5车放行(旧cap4不放)",
      bool(h4), str([l for l in logs if "ECON" in l][:1]))

s, mem = econ_state(n_harv=6, cash=1400, n_ref=3)
_st, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
h6 = [a for a in acts if a.get("name") == "HARV" and a.get("act") == "produce"]
check("18b ref3 目标6 → 6车封顶不补", not h6)

s, mem = econ_state(n_harv=7, cash=1400, n_ref=4)
_st, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
h8 = [a for a in acts if a.get("name") == "HARV" and a.get("act") == "produce"]
check("18d(85局) ref4 目标8 → 第8车放行", bool(h8), str([l for l in logs if "ECON" in l][:1]))

s, mem = econ_state(n_harv=5, cash=1400, n_ref=2)
_st, acts, logs = planner.checklist(s, (10, 10), "develop", mem)
h5 = [a for a in acts if a.get("name") == "HARV" and a.get("act") == "produce"]
check("18c ref2(目标4) 5车超target → 不补", not h5)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部场景通过(含 18 系列 3 场景) ===")
