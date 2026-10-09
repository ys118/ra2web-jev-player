# -*- coding: utf-8 -*-
"""[第76局 动态早rush防御响应] 离线场景测试:
21) RUSH-DEFENSE 自适应模式(用户 75 局两反馈): 敌兵海压门(近敌≥4)且守军对不上
    → 切换防御公式: 动员兵爆产 x2 不受坦克资金线约束 + Jev INF 闸门放行;
    威胁解除自动恢复原公式。75 局实证: 敌 20 单位海 t≈360 压家时 13 E2 全灭,
    固定公式被 roll 穿透(t=485 速败)。"""
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


def rush_state(cash=500, threat_n=8, def_e2=3, def_tank=0, e2_extra=0,
               mode_pre=False):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(def_e2):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i, 12)))
    for i in range(e2_extra):
        mine.append(unit("x%d" % i, "E2", 3, (30 + i, 12)))
    for i in range(def_tank):
        mine.append(unit("t%d" % i, "HTNK", 7, (14, 14)))
    hos = [{"id": "h%d" % i, "n": "E2", "o": 3, "tl": [20 + (i % 3), 20 + i % 3]}
           for i in range(threat_n)]
    s = {"t": 400, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    if mode_pre:
        mem.rush_defense = True
    return s, mem


# ---- 21a 触发: 敌 8 压门 vs 守 3 → RUSH-DEFENSE ON + E2 x4 大爆 ----
#     [第89局] cash 提至 1200(≥HTNK 地板 900): 充裕期维持 x4 大爆语义
s, mem = rush_state(cash=1200, threat_n=8, def_e2=3)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("21a 敌8压门守3 → ON+E2爆产", mem.rush_defense is True
      and any(a.get("name") == "E2" and a.get("qty") == 4 for a in acts)
      and any("RUSH-DEFENSE ON" in l for l in logs),
      str([a for a in acts if a.get("name") == "E2"][:1]))

# ---- 21b [第89局] 现金 500(<地板900) → 降 x1 续兵(坦克资金保护) ----
s, mem = rush_state(cash=500, threat_n=8, def_e2=3, mode_pre=True)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("21b cash=500 <地板 → x1 续兵不击穿坦克线",
      any(a.get("name") == "E2" and a.get("qty") == 1 for a in acts)
      and any("资金地板续兵" in l for l in logs),
      str([a for a in acts if a.get("name") == "E2"][:1]))

# ---- 21c 威胁解除 → 自动 OFF 恢复原公式 ----
s, mem = rush_state(mode_pre=True, threat_n=0, def_e2=6)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("21c(87局改) 威胁清空 → OFF+无爆产(驻军E2合法)", mem.rush_defense is False
      and not any(a.get("name") == "E2" and a.get("qty") == 4 for a in acts)
      and any("RUSH-DEFENSE OFF" in l for l in logs))

# ---- 21d 守军充足(12 vs 8) → 不切换(避免小骚扰空转公式) ----
s, mem = rush_state(threat_n=8, def_e2=12)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("21d 守12敌8 → 不触发", mem.rush_defense is False
      and not any(a.get("name") == "E2" for a in acts))

# ---- 21e 小骚扰(敌3) → 不触发(阈值≥4) ----
s, mem = rush_state(threat_n=3, def_e2=1)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("21e 敌3压门 → 模式不触发(驻军E2合法产)", mem.rush_defense is False
      and not any(a.get("name") == "E2" and a.get("qty") == 4 for a in acts))

# ---- 21f E2 总量 30 上限 → 爆产封顶 ----
s, mem = rush_state(cash=500, threat_n=8, def_e2=4, e2_extra=26, mode_pre=True)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("21f E2 已 30 → 不再爆产",
      not any(a.get("name") == "E2" for a in acts),
      str([a.get("name") for a in acts]))

# ---- 21g Jev INF E2: 模式 ON + cash 500 + 战厂在 → 放行(原闸需 800) ----
s, mem = rush_state(cash=500, threat_n=8, def_e2=3)
planner.checklist(s, HOME, "defend", mem)          # 先置位 mode
_st, acts, logs = planner.apply_jev(
    s, {"inf": {"choice": "E2", "confidence": 0.4}}, "defend", mem)
check("21g Jev INF E2 防御模式放行",
      any(a.get("name") == "E2" for a in acts), str(logs[:1]))

# ---- 21h Jev INF E2: 模式 OFF + cash 500 + 战厂在 → 原闸 HOLD(回归语义) ----
s, mem = rush_state(cash=500, threat_n=0, def_e2=3)
_st, acts, logs = planner.apply_jev(
    s, {"inf": {"choice": "E2", "confidence": 0.4}}, "defend", mem)
check("21h 模式 OFF 原闸 HOLD", not acts, str(logs[:1]))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 8 场景通过 ===")
