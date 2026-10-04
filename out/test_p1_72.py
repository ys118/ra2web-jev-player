# -*- coding: utf-8 -*-
"""[第72局 P1 资金分配校正] 离线场景测试:
18) clef VEH 通道预算保护+防空存量帽 / 拦截位屏统一(威胁4/无威胁2)。
    第 70/71 局实证: clef 经 VEH 点名 HTK 58/74 次(无资金闸)挤占重坦现金线,
    HTNK 每局仅 7 辆且 t<1719 全灭, 敌潮时刻守家零重坦(64 秒 my_val 9080→1080)。"""
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


def open_state(cash, n_htk=1, n_htnk=1, air=False):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    for i in range(n_htk):
        mine.append(unit("k%d" % i, "HTK", 7, (20 + i, 12)))
    for i in range(n_htnk):
        mine.append(unit("t%d" % i, "HTNK", 7, (30 + i, 12)))
    mine += [unit("h1", "HARV", 7, (12, 12)), unit("h2", "HARV", 7, (13, 12))]
    hos = [{"n": "JUMPJET", "tl": [50, 50]}] if air else []
    s = {"t": 700, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"],
                1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HTK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    return s, planner.BattleMemory()


# ---- 18a VEH→HTK 存量帽: 已有 4 辆 → HOLD ----
s, mem = open_state(2000, n_htk=4)
_st, acts, logs = planner.apply_jev(
    s, {"veh": {"choice": "HTK", "confidence": 0.40}}, "defend", mem)
check("18a VEH→HTK 帽(存量4) → 不下单", not acts, str(logs[:1]))

# ---- 18b VEH→HTNK 预算保护: cash 800 < 900+800 → HOLD ----
s, mem = open_state(800, n_htk=1)
_st, acts, logs = planner.apply_jev(
    s, {"veh": {"choice": "HTNK", "confidence": 0.40}}, "defend", mem)
check("18b VEH→HTNK 预算保护(cash=800) → 不下单", not acts, str(logs[:1]))

# ---- 18c VEH→HTNK 现金充足(2000≥1700) → 正常下单 ----
s, mem = open_state(2000, n_htk=1)
_st, acts, logs = planner.apply_jev(
    s, {"veh": {"choice": "HTNK", "confidence": 0.40}}, "defend", mem)
check("18c VEH→HTNK cash=2000 → produce",
      any(a.get("name") == "HTNK" and a.get("act") == "produce" for a in acts),
      str(logs[:1]))

# ---- 18d 拦截位屏(威胁在场): 6 HTK → 留 4, 2 辆回归对地编队 ----
s, mem = open_state(2000, n_htk=6, n_htnk=2, air=True)
sq = planner.assign_squads(s, (10, 10), mem, "defend")
ground_htk = sum(1 for g in ("raid", "assault", "guard", "reserve")
                 for uid in sq.get(g, []) if uid.startswith("k"))
check("18d 威胁在场: aahunt=4 且 2 辆 HTK 回归对地",
      len(sq.get("aahunt", [])) == 4 and ground_htk == 2,
      "aahunt=%d ground_htk=%d" % (len(sq.get("aahunt", [])), ground_htk))

# ---- 18e 拦截位屏(无威胁): 6 HTK → 留 2, 4 辆回归 ----
s, mem = open_state(2000, n_htk=6, n_htnk=2, air=False)
sq = planner.assign_squads(s, (10, 10), mem, "defend")
ground_htk = sum(1 for g in ("raid", "assault", "guard", "reserve")
                 for uid in sq.get(g, []) if uid.startswith("k"))
check("18e 无威胁: aahunt=2 且 4 辆 HTK 回归对地",
      len(sq.get("aahunt", [])) == 2 and ground_htk == 4,
      "aahunt=%d ground_htk=%d" % (len(sq.get("aahunt", [])), ground_htk))

# ---- 18f 确定性 AA 补充线: 威胁+存量3+cash600 → 补 1 辆(500 门槛保留) ----
s, mem = open_state(600, n_htk=3, air=True)
_st, acts, logs = planner.checklist(s, (10, 10), "defend", mem)
check("18f 确定性 AA 线 stock=3 cash=600 → 补充 HTK",
      any(a.get("name") == "HTK" and a.get("act") == "produce" for a in acts),
      str([l for l in logs if "AA" in l][:1]))

# ---- 18g 确定性 AA 补充线: 存量4 → 不补(帽) ----
s, mem = open_state(600, n_htk=4, air=True)
_st, acts, logs = planner.checklist(s, (10, 10), "defend", mem)
check("18g 确定性 AA 线 stock=4 → 不下单",
      not any(a.get("name") == "HTK" for a in acts),
      str([l for l in logs if "AA" in l][:1]))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 7 场景通过 ===")
