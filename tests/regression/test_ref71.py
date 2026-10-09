# -*- coding: utf-8 -*-
"""[第71局 精炼厂缺额豁免] 离线场景测试:
17) build_gate 例外③——存量<ref_cap 的精炼厂不受坦克资金线约束。
    第 70 局(clef 首局)实证: 见底率 67% 下现金永远凑不齐 造价+tank_cash1,
    确定性两线与 Jev 线三路同闸 → 三矿厂死锁、收入端饿死(坦克峰值 14 vs 69 局 26);
    本单变量把第 69 局"收入>吞吐"原则补全到闸门本身, ref_cap=3 封顶。"""
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


def open_state(t, n_ref, cash):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    for i in range(n_ref - 1):                       # BASE_BLD 已含 1 精炼厂
        mine.append(unit("r%d" % i, "NAREFN", 2, (20 + i, 10)))
    mine.append(unit("h1", "HARV", 7, (12, 12)))
    s = {"t": t, "mine": mine, "hostile": [], "enemy": [],
         "av": {0: ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP", "NARADR"],
                1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    return s, planner.BattleMemory()


# ---- 17a 缺额豁免: ref=2, cash=0 → 精炼厂放行 ----
s, mem = open_state(700, 2, 0)
check("17a ref=2 cash=0 NAREFN 放行",
      planner.build_gate(s, planner.ucost("NAREFN"), mem, "NAREFN") is True)

# ---- 17b 封顶: ref=4(=cap, 85局扩容) → 仍受坦克资金线约束 ----
s, mem = open_state(700, 4, 0)
check("17b ref=4 封顶后 cash=0 仍 HOLD",
      planner.build_gate(s, planner.ucost("NAREFN"), mem, "NAREFN") is False)

# ---- 17c 非精炼厂建筑闸门行为不变 ----
s, mem = open_state(700, 2, 0)
check("17c NARADR cash=0 仍 HOLD",
      planner.build_gate(s, planner.ucost("NARADR"), mem, "NARADR") is False)

# ---- 17d 原例外② RECOVER 放开不变 ----
s, mem = open_state(700, 3, 0)
mem.current_stance = "recover"
check("17d RECOVER 放开不变",
      planner.build_gate(s, planner.ucost("NARADR"), mem, "NARADR") is True)

# ---- 17e Jev 路径端到端: ref=3(<cap4) cash=0 → 下单精炼厂(不再 HOLD) ----
s, mem = open_state(500, 3, 0)
_st, acts, logs = planner.apply_jev(
    s, {"build": {"choice": "NAREFN", "confidence": 0.30}}, "develop", mem)
check("17e Jev 路径 ref=2 cash=0 → produce NAREFN",
      any(a.get("name") == "NAREFN" and a.get("act") == "produce" for a in acts),
      str(logs[:1]))

# ---- 17f Jev 路径封顶: ref=4 → 无动作(外层 cap 拦截) ----
s, mem = open_state(500, 4, 0)
_st, acts, logs = planner.apply_jev(
    s, {"build": {"choice": "NAREFN", "confidence": 0.30}}, "develop", mem)
check("17f Jev 路径 ref=3 → 不下单", not acts, str(logs[:1]))

# ---- 17g 确定性线端到端: t=700 ref=2 cash=0 → 补第三矿厂 ----
s, mem = open_state(700, 2, 0)
act = planner.opening_build(s, mem)
check("17g 确定性线 ref=2 cash=0 → OPENING BUILD NAREFN",
      bool(act) and act.get("name") == "NAREFN", str(act))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 7 场景通过 ===")
