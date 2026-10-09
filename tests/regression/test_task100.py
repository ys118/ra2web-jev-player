# -*- coding: utf-8 -*-
"""[第100局 步兵任务化+护矿拦截(用户反馈)] 离线场景测试:
35) ①AA 自保: 火箭人被敌战车护航 → aahunt 后撤待坦克清场, 无护航才猎杀
    ②敌矿车入侵家门口(≤22 格) → 主力 INTRUDER-HUNT 点名拦截
    ③步兵任务化: 坦克未出击时超额步兵一半编扫荡队(咬敌矿车/前哨),
    rush_defense 例外全员驻塔线。"""
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


def mk_state(inf_n=8, tank_n=4, hostile=(), mode_pre=False, cash=3000):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(inf_n):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i % 4, 12 + i // 4)))
    for i in range(tank_n):
        mine.append(unit("t%d" % i, "HTNK", 7, (14 + i % 3, 14 + i // 3)))
    for i in range(2):                                # 防空车 2 辆(aahunt 组源)
        mine.append(unit("k%d" % i, "HTK", 7, (16 + i, 16)))
    s = {"t": 900, "mine": mine, "hostile": list(hostile), "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV", "HTK"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    if mode_pre:
        mem.rush_defense = True
    return s, mem


# ---- 35a AA 自保: 火箭人 J1 带敌战车护航(在 aahunt 14 格内) → AA-HOLD 后撤 ----
hostile = [{"id": "j1", "n": "JUMPJET", "o": 7, "tl": [30, 30]},
           {"id": "g1", "n": "HTNK", "o": 7, "tl": [34, 30]}]
s, mem = mk_state(hostile=hostile)
acts, logs = planner.movement(s, HOME, "defend", mem)
log_s = logs if isinstance(logs, str) else "; ".join(logs)
hold = [a for a in acts if a.get("act") == "attack_move"
        and a.get("x") == 16 and a.get("y") == 16]
check("35a 敌战车护航火箭人 → aahunt 后撤待清场(AA-HOLD)",
      bool(hold) and "AA-HOLD" in log_s, log_s[:110])

# ---- 35b 无护航 → aahunt 正常点名猎火箭人 ----
hostile = [{"id": "j1", "n": "JUMPJET", "o": 7, "tl": [30, 30]}]
s, mem = mk_state(hostile=hostile)
acts, logs = planner.movement(s, HOME, "defend", mem)
ff = [a for a in acts if a.get("act") == "attack_obj" and a.get("tid") == "j1"]
check("35b 火箭人无护航 → 正常猎杀", bool(ff),
      str([a.get("tid") for a in ff if a.get("act") == "attack_obj"]))

# ---- 35c 敌矿车入侵家门口(≤22 格) → 主力 INTRUDER-HUNT ----
hostile = [{"id": "iv1", "n": "HARV", "o": 7, "tl": [25, 22]}]   # 距家 ~19
s, mem = mk_state(hostile=hostile)
acts, logs = planner.movement(s, HOME, "defend", mem)
ff = [a for a in acts if a.get("act") == "attack_obj" and a.get("tid") == "iv1"]
log_s = logs if isinstance(logs, str) else "; ".join(logs)
check("35c 敌矿车入侵 → INTRUDER-HUNT 点名拦截",
      bool(ff) and "INTRUDER-HUNT" in log_s, log_s[:110])

# ---- 35d 步兵任务化: 坦克未出击(敌基地未知) → sweep 组存在且出动 ----
s, mem = mk_state(inf_n=12, tank_n=0, hostile=[])
mem.enemy_base = None
acts, logs = planner.movement(s, HOME, "develop", mem)
sq = mem.last_squads
sw = [a for a in acts if a.get("act") == "attack_move"
      and a.get("ids") == sq["sweep"]]
check("35d 坦克未出击 → 超额步兵一半编扫荡队出动",
      len(sq["sweep"]) == 4 and bool(sw) and len(sq["hold"]) == 8,
      "sweep=%d hold=%d" % (len(sq["sweep"]), len(sq["hold"])))

# ---- 35e rush_defense → 不组扫荡队(全员驻塔线) ----
s, mem = mk_state(inf_n=12, tank_n=4, mode_pre=True)
acts, logs = planner.movement(s, HOME, "defend", mem)
sq = mem.last_squads
check("35e rush_defense → 无扫荡队(保命优先)",
      sq["sweep"] == [] and len(sq["hold"]) == 12,
      "sweep=%d hold=%d" % (len(sq["sweep"]), len(sq["hold"])))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 5 场景通过 ===")
