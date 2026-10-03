# -*- coding: utf-8 -*-
"""[第68局 侦察链加固] 离线场景测试:
13) 坦克侦察旋转化——敌影仅在 240gs 未访时用, 否则未访路标轮转;
14) 军犬撤退 60gs 限时——超时卡死重派, 未超时保持沉默。"""
import sys
sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")

from ra2web_jev_player.strategy import planner

HOME = (130, 80)
fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}


def scout_state(hostile=None, first_pos=None, tanks=("t1",), dog=False):
    mine = [unit("b0", "NACNST", 2, (130, 82)), unit("b1", "NAPOWR", 2, (128, 82)),
            unit("b2", "NAREFN", 2, (126, 82)), unit("h1", "HARV", 7, (120, 80))]
    for i, tid in enumerate(tanks):
        mine.append(unit(tid, "HTNK", 7, (132 + i, 84)))
    if dog:
        mine.append(unit("d1", "ADOG", 3, (110, 60)))
    s = {"t": 600, "mine": mine, "hostile": hostile or [], "enemy": [],
         "av": {0: [], 1: [], 2: [], 3: []}, "queues": [{"t": i, "s": 0, "items": []}
                                                        for i in range(4)],
         "me": {"credits": 3000, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    if first_pos:
        s["hostile"] = [unit("x1", "E2", 3, first_pos)]
    return s


# ---- 13: 坦克侦察旋转化 ----
# 13a: 无敌影无告警 → 首选镜像角路标
mem = planner.BattleMemory()
s = scout_state()
acts, logs = planner.scouting(s, HOME, mem)
check("13a 无敌影→路标轮转(镜像角)", acts and acts[0]["x"] == 8 and acts[0]["y"] == 48,
      str(acts[:1]) + str(logs[:1]))

# 13b: 敌影存在但 240gs 内已访过 → 不再去敌影, 转未访路标
mem = planner.BattleMemory()
mem.first_hostile_pos = [104, 13]
s = scout_state(first_pos=[104, 13])
acts, logs = planner.scouting(s, HOME, mem)
shadow = planner.shadow_target(s, HOME, mem)      # [104,13] 边缘投影
check("13b-1 敌影投影存在", shadow is not None, str(shadow))
mem2 = planner.BattleMemory()                    # 新mem: 避开150s节流
mem2.first_hostile_pos = [104, 13]
mem2.scout_visit[tuple(shadow)] = s["t"] - 100    # 100gs 前刚去过
acts2, logs2 = planner.scouting(s, HOME, mem2)
check("13b-2 敌影已访→转路标", acts2 and not (acts2[0]["x"] == shadow[0]
                                              and acts2[0]["y"] == shadow[1]),
      str(acts2[:1]) + str(logs2[:1]))

# 13c: 敌影存在且未访过 → 走敌影(保留有效启发)
mem = planner.BattleMemory()
mem.first_hostile_pos = [104, 13]
s = scout_state(first_pos=[104, 13])
acts, logs = planner.scouting(s, HOME, mem)
check("13c 敌影未访→走敌影", acts and (acts[0]["x"], acts[0]["y"]) == tuple(shadow),
      str(acts[:1]) + str(logs[:1]))

# ---- 14: 军犬撤退限时 ----
# 14a: evade 超 60gs 未到家(无敌近身) → 超时重派最安全路标
mem = planner.BattleMemory()
s = scout_state(tanks=(), dog=True)
mem.dog_task = {"d1": {"wp": (104, 13), "t": s["t"] - 70, "mode": "evade"}}
acts, logs = planner.scouting(s, HOME, mem)
check("14a 撤退超时→重派", bool(acts) and "SCOUT dog" in (logs or ""),
      str(acts[:1]) + str(logs[:1]))
check("14a-2 任务已转 go", mem.dog_task.get("d1", {}).get("mode") == "go",
      str(mem.dog_task))

# 14b: evade 未超 60gs → 沉默(继续回家), 且无坦克时不产生任何指令
mem = planner.BattleMemory()
s = scout_state(tanks=(), dog=True)
mem.dog_task = {"d1": {"wp": (104, 13), "t": s["t"] - 30, "mode": "evade"}}
r = planner.scouting(s, HOME, mem)
check("14b 撤退未超时→沉默", r == (None, None), str(r))

# 14c: evade 超时且敌在 8 格内 → 重新规避(不能傻站)
mem = planner.BattleMemory()
s = scout_state(tanks=(), dog=True, hostile=[unit("e1", "E2", 3, (108, 58))])
mem.dog_task = {"d1": {"wp": (104, 13), "t": s["t"] - 70, "mode": "evade"}}
acts, logs = planner.scouting(s, HOME, mem)
check("14c 超时+敌近→重新规避回家", bool(acts) and acts[0]["act"] == "move"
      and abs(acts[0]["x"] - HOME[0]) < 2, str(acts[:1]) + str(logs[:1]))

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(0 if not fails else 1)
