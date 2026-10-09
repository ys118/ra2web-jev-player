# -*- coding: utf-8 -*-
"""[第83局 经济军备竞速II] 离线场景测试:
26) 战车工厂上限 2→3——6 矿车收入(81局)下双厂产能追不上敌军(80局实锤),
    第三厂=产能翻倍; 资金闸沿用 factory2_cash; 其余建筑"同类≥2"帽不变
    ([第32局] jev 连买 30 电厂防线保留)。"""
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


def fac_state(cash, n_weap, extra_av=None, n_bar=1):
    BASE = ["NACNST", "NAPOWR", "NAREFN"]   # 兵营数由 n_bar 控制
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE)]
    for i in range(3):                       # 4 矿厂(满足 ref_cap=4, 85局扩容)
        mine.append(unit("r%d" % i, "NAREFN", 2, (15 + i, 12)))
    for i in range(n_weap):
        mine.append(unit("w%d" % i, "NAWEAP", 2, (20 + i, 10)))
    for i in range(n_bar):
        mine.append(unit("h%d" % i, "NAHAND", 2, (25 + i, 10)))
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    av0 = ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"] + (extra_av or [])
    s = {"t": 700, "mine": mine, "hostile": [], "enemy": [],
         "av": {0: av0, 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 300, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    return s, planner.BattleMemory()


# ---- 26a [87局改] 双厂+现金2000 → 第二兵营前置(防御纵深优先于三厂) ----
s, mem = fac_state(2000, 2)
act = planner.opening_build(s, mem)
check("26a(87局改) 双厂+单兵营 → 第二兵营优先",
      bool(act) and act.get("name") == "NAHAND", str(act))

# ---- 26b 双厂+现金 1000(<1800闸) → 不下(资金闸保留) ----
s, mem = fac_state(1000, 2)
act = planner.opening_build(s, mem)
check("26b cash1000<1800 → 不下单", act is None, str(act))

# ---- 26c [87局改] 三厂+双兵营均满 → 无单 ----
s, mem = fac_state(3000, 3, n_bar=2)
act = planner.opening_build(s, mem)
check("26c(87局改) 三厂双营封顶 → 不下单", act is None, str(act))

# ---- 26d Jev 路径: 双厂存在 → BUILD NAWEAP 放行(原通用帽拦) ----
s, mem = fac_state(2600, 2)
_st, acts, logs = planner.apply_jev(
    s, {"build": {"choice": "NAWEAP", "confidence": 0.30}}, "develop", mem)
check("26d Jev BUILD NAWEAP 第三厂放行",
      any(a.get("name") == "NAWEAP" for a in acts), str(logs[:1]))

# ---- 26e Jev 路径: 电厂帽不变(已有 2 电厂 → BUILD NAPOWR HOLD) ----
s, mem = fac_state(2600, 2)
s["mine"] += [unit("p1", "NAPOWR", 2, (30, 10)), unit("p2", "NAPOWR", 2, (31, 10))]
_st, acts, logs = planner.apply_jev(
    s, {"build": {"choice": "NAPOWR", "confidence": 0.30}}, "develop", mem)
check("26e 电厂同类≥2帽不变 → 无动作",
      not any(a.get("name") == "NAPOWR" for a in acts), str(logs[:1]))

# ---- 26f Jev 路径: 三厂已满 → 不再放行 ----
s, mem = fac_state(2600, 3)
_st, acts, logs = planner.apply_jev(
    s, {"build": {"choice": "NAWEAP", "confidence": 0.30}}, "develop", mem)
check("26f 三厂封顶 → Jev 路径不放行",
      not any(a.get("name") == "NAWEAP" for a in acts), str(logs[:1]))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 6 场景通过 ===")
