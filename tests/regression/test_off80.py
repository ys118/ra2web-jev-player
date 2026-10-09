# -*- coding: utf-8 -*-
"""[第80局 总攻决心包] 离线场景测试:
24) 用户反馈"我方优势时兵力龟缩基地不主动出击, 需一鼓作气歼灭敌人":
    ①SIEGE 盖过 RUSH-DEFENSE(79 局: 敌残兵赖在防御半径使防御模式常驻 ON,
      38 单位被按在家里) ②mass-push: 突击组攒够 siege_push_n(8) 辆再齐冲
      (3 辆添油喂磁暴=79 局 9 分钟只拔 1 座线圈) ③壳清空后步兵全员跟上扫荡
      (30 动员兵蹲家看戏教训)。"""
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


def siege_state(assault_n=12, defb=True, enemy_harv=False, e2_n=6):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(assault_n):
        mine.append(unit("t%d" % i, "HTNK", 7, (40 + i, 60)))
    for i in range(e2_n):
        mine.append(unit("e%d" % i, "E2", 3, (20 + i, 14)))
    hos = []
    if defb:
        hos.append({"id": "p0", "n": "GAPILL", "o": 2, "tl": [100, 70]})
    hos.append({"id": "w0", "n": "GAWEAP", "o": 2, "tl": [100, 76]})
    if enemy_harv:
        hos.append({"id": "hv", "n": "HARV", "o": 7, "tl": [90, 90]})
    s = {"t": 2000, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": 2000, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.enemy_base = (100, 72)
    mem.siege_mode = True
    return s, mem


def assault_obj_of_tanks(acts):
    for a in acts:
        if a.get("act") == "attack_obj" and any(str(i).startswith("t") for i in a.get("ids", [])):
            return a
    return None


# ---- 24a SIEGE 盖过 RUSH-DEFENSE: 模式被强制 OFF + 兵团照常出击 ----
s, mem = siege_state(assault_n=12)
mem.rush_defense = True                     # 敌残兵赖门导致的常驻 ON
acts, logs = planner.movement(s, HOME, "attack", mem)
log_s = logs if isinstance(logs, str) else "; ".join(logs)
check("24a SIEGE 覆盖 rush_defense: 强制 OFF+拔壳出击",
      mem.rush_defense is False and "SIEGE overrides" in log_s
      and assault_obj_of_tanks(acts) is not None,
      log_s[:120])

# ---- 24b [97局改] 3辆<5 且有防御壳 → STAGING 前沿集结(不再回基地转圈) ----
s, mem = siege_state(assault_n=3)
acts, logs = planner.movement(s, HOME, "attack", mem)
log_s = logs if isinstance(logs, str) else "; ".join(logs)
stage = [a for a in acts if a.get("act") == "attack_move"
         and a.get("x") == 59 and a.get("y") == 44]
check("24b(97局改) 3辆<5 → STAGING 前沿集结(59,44)",
      bool(stage) and "SIEGE STAGING" in log_s, log_s[:120])

# ---- 24c [97局改] 攒齐 5 辆 → 齐冲拔壳 ----
s, mem = siege_state(assault_n=5)
acts, logs = planner.movement(s, HOME, "attack", mem)
a = assault_obj_of_tanks(acts)
check("24c(97局改) 5辆≥阈值 → 齐冲防御壳",
      bool(a) and a.get("tid") == "p0" and len(a.get("ids", [])) == 5,
      str(bool(a)))

# ---- 24d 扫荡阶段(壳清空): 步兵全员编入突击 ----
s, mem = siege_state(assault_n=10, defb=False)
acts, logs = planner.movement(s, HOME, "attack", mem)
sq = mem.last_squads
inf_in_assault = sum(1 for i in sq["assault"] if str(i).startswith("e"))
check("24d 壳清 → 步兵全员参战(hold=空)",
      sq["hold"] == [] and inf_in_assault == 6,
      "hold=%s inf_in=%d" % (sq["hold"], inf_in_assault))

# ---- 24e 壳还在时步兵留守(不喂磁暴) ----
s, mem = siege_state(assault_n=10, defb=True)
acts, logs = planner.movement(s, HOME, "attack", mem)
sq = mem.last_squads
check("24e 壳还在 → 步兵留守", len(sq["hold"]) == 6,
      "hold=%d" % len(sq["hold"]))

# ---- 24f STAGING 只在有防御壳时(清建筑阶段不满编也照样清) ----
s, mem = siege_state(assault_n=5, defb=False)
acts, logs = planner.movement(s, HOME, "attack", mem)
a = assault_obj_of_tanks(acts)
check("24f 清建筑阶段 5 辆也出击", bool(a) and a.get("tid") == "w0",
      str(bool(a)))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 6 场景通过 ===")
