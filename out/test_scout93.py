# -*- coding: utf-8 -*-
"""[第93局 fix_scout] 离线场景测试:
32) 军犬路标网注入腹部+镜像锚点(Jev 连续 4 局 0.9 置信): 原两列边缘网探不到
    地图腹部(87-91 局敌基地全在 (67,115) 一带), 且敌兵海压家时"最安全"悖论
    把军犬吸去远角(92 局犬探 (188,*) 而敌基地近在镜像区)。路标集扩充, 军犬
    行为规则(规避/休整/安全度)全部不动。
"""
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


HOME = (10, 10)


def mk_state(dog_pos=(14, 100), hostile=()):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in
            enumerate(["NACNST", "NAPOWR", "NAREFN", "NAHAND", "NAWEAP"])]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    mine.append(unit("dog1", "ADOG", 7, dog_pos))       # 军犬(满血)
    s = {"t": 600, "mine": mine, "hostile": list(hostile), "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": 3000, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    return s, mem


# ---- 32a 无可见敌: 军犬派发目标应在路标网内(含腹部/镜像点) ----
s, mem = mk_state()
acts, logs = planner.scouting(s, HOME, mem)
moves = [a for a in acts if a.get("act") == "move"]
check("32a 军犬被派发探图", bool(moves), str(logs)[:80])

# 模拟多轮派发, 收集所有目标点: 网格腹部点必须出现
mem2 = planner.BattleMemory()
seen_targets = set()
s2, mem2 = mk_state()
# 军犬瞬移到各路标(模拟多轮探图), 收集派发目标
for round_i in range(40):
    a, lg = planner.scouting(s2, HOME, mem2)
    for act in (a or []):
        if act.get("act") == "move":
            seen_targets.add((act["x"], act["y"]))
    if a:
        for act in a:
            if act.get("act") == "move":
                # 军犬瞬移到目标(模拟到达, 触发下一轮新派发)
                for u in s2["mine"]:
                    if u["id"] == "dog1" and u["n"] == "ADOG":
                        u["tl"] = [act["x"], act["y"]]
    s2["t"] += 250                                   # 推进时间避免在途/节流

abdomen_hit = any(abs(x - 128 // 2) <= 45 and abs(y - 128 // 2) <= 45
                  for x, y in seen_targets)
mirror_hit = any(x >= 100 and y >= 100 for x, y in seen_targets)
check("32b 路标网覆盖地图腹部(中心±45)", abdomen_hit,
      str(sorted(seen_targets)[:8]))
check("32c 路标网含镜像锚点(≥100,≥100)", mirror_hit,
      str(sorted(seen_targets)[:8]))

# ---- 32d 敌兵压家时军犬仍规避(用户铁律不破) ----
s3, mem3 = mk_state(dog_pos=(30, 30),
                    hostile=[{"id": "h1", "n": "E2", "o": 3,
                              "tl": [33, 33]}])
acts3, logs3 = planner.scouting(s3, HOME, mem3)
evade = any("规避" in l for l in (logs3 or []))
go_home = any(a.get("act") == "move" and a.get("x") == HOME[0]
              and a.get("y") == HOME[1] for a in (acts3 or []))
check("32d 军犬遇敌立即规避(铁律保持)", evade or go_home, str(logs3)[:80])

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 4 场景通过 ===")
