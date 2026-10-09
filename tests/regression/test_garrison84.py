# -*- coding: utf-8 -*-
"""[第84局 防守起手·开局步兵前置] 离线场景测试:
27) 兵营落地+坦克场真空 → 常备 ≥4 动员兵(首坦成熟前 t<273 硬窗口保险,
    83 局: 大 roll 兵海在首坦成熟前磨穿防线, 反应式触发来不及);
    坦克出场/数量达标/rush_defense 激活时不重复产(各自语义分离)。"""
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


BASE_BLD = ["NACNST", "NAPOWR", "NAREFN", "NAHAND", "NAWEAP"]
HOME = (10, 10)


def gar_state(t=250, cash=2000, e2_n=2, tanks=0, threat_n=0, rush=False):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(e2_n):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i, 12)))
    for i in range(tanks):
        mine.append(unit("t%d" % i, "HTNK", 7, (30 + i, 14)))
    hos = [{"id": "h%d" % i, "n": "E2", "o": 3, "tl": [40 + i, 40]} for i in range(threat_n)]
    s = {"t": t, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.rush_defense = rush
    mem.v3_seen_t = -10**9
    mem.long_fire_t = -10**9
    return s, mem


def e2_orders(acts):
    return [a for a in acts if a.get("name") == "E2" and a.get("act") == "produce"]


# ---- 27a 兵营+坦克真空+e2=2 → GARRISON E2 x2 ----
s, mem = gar_state(e2_n=2)
_st, acts, logs = planner.checklist(s, HOME, "develop", mem)
o = e2_orders(acts)
check("27a 真空期 e2=2 → x2 常驻驻军", len(o) == 1 and o[0].get("qty") == 2,
      str([l for l in logs if "GARRISON" in l][:1]))

# ---- 27b 连续 tick 节流: 30gs 内不重复下单(全新状态) ----
s, mem = gar_state(e2_n=2)
total = 0
for dt in range(4):
    s["t"] = 250 + dt * 2
    _st, acts, _ = planner.checklist(s, HOME, "develop", mem)
    total += len(e2_orders(acts))
check("27b 连续 tick 仅 1 单", total == 1, "orders=%d" % total)

# ---- 27c [87局改] 地板 4→8: e2=4 仍补产, e2=8 才达标 ----
s, mem = gar_state(e2_n=4)
_st, acts, _ = planner.checklist(s, HOME, "develop", mem)
check("27c(87局改) e2=4<8 → 驻军补产", len(e2_orders(acts)) == 1)
s, mem = gar_state(e2_n=8)
_st, acts, _ = planner.checklist(s, HOME, "develop", mem)
check("27c-2 e2=8 达标 → 不产", not e2_orders(acts))

# ---- 27d 坦克在场 → 不产(真空期语义) ----
s, mem = gar_state(e2_n=2, tanks=1)
_st, acts, _ = planner.checklist(s, HOME, "develop", mem)
check("27d 坦克在场 → 不产", not e2_orders(acts))

# ---- 27e rush_defense ON → 驻军分支让位(爆产分支 x4 负责) ----
s, mem = gar_state(e2_n=2, rush=True, threat_n=8)
for i, h in enumerate(s["hostile"]):        # 敌情挪进防御半径 26 内
    h["tl"] = [22 + (i % 3), 22 + (i % 3)]
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
o = e2_orders(acts)
check("27e rush ON → 爆产 x4 而非驻军 x2",
      len(o) == 1 and o[0].get("qty") == 4,
      str([l for l in logs if "E2 x" in l][:1]))

# ---- 27f 坦克全灭自愈: 曾有坦克后真空 → 驻军补充 ----
s, mem = gar_state(t=800, e2_n=1)      # 中局真空(坦克全灭场景)
_st, acts, _ = planner.checklist(s, HOME, "develop", mem)
o = e2_orders(acts)
check("27f 中局真空 → 驻军自愈补充", len(o) == 1 and o[0].get("qty") == 2)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 6 场景通过 ===")
