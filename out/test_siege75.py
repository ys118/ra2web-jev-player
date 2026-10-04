# -*- coding: utf-8 -*-
"""[第75局 终局围城] 离线场景测试:
20) SIEGE 锁存(敌基地定位+敌经济死亡+战力≥1.5x) → 全军集结(无guard/raid只留
    机器人) + 拔防御壳优先(74 局实证: "绝不打塔"铁律把 31 辆坦克锁在机枪堡壳外
    45 分钟零击杀的无限撤退循环——用户反馈: 兵力强盛为何不集结大军直接消灭)。"""
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
HOME = (10, 10)


def siege_state(armor_n=16, enemy_harv=False, en_armor_n=2, defb=True,
                econ_b=True, force_ratio=3.0):
    """我方 armor_n 辆 HTNK(900) 在场; 敌方: 防御壳(GAPILL 500)+经济建筑
    (GAWEAP 2000)+en_armor_n 辆 MTNK(700)[+敌矿车 HARV] 。战力比由 armor_n 控制。"""
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    for i in range(armor_n):
        mine.append(unit("t%d" % i, "HTNK", 7, (40 + i, 60)))
    hos = []
    if defb:
        for i in range(3):
            hos.append({"id": "p%d" % i, "n": "GAPILL", "o": 2, "tl": [100, 70]})
    if econ_b:
        hos.append({"id": "w0", "n": "GAWEAP", "o": 2, "tl": [100, 76]})
    for i in range(en_armor_n):
        hos.append({"id": "e%d" % i, "n": "MTNK", "o": 7, "tl": [95 + i, 72]})
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
    if force_ratio == 3.0:
        pass  # 16x900=14400 vs 3x500+2000+2x700=4900 → ~2.9x 触发
    return s, mem


def assault_obj_target(acts):
    for a in acts:
        if a.get("act") == "attack_obj" and any(str(i).startswith("t") for i in a.get("ids", [])):
            return a.get("tid")
    return None


# ---- 20a 触发: 经济死+3倍战力 → SIEGE 拔防御壳(GAPILL 优先于 GAWEAP) ----
s, mem = siege_state(armor_n=16)
acts, logs = planner.movement(s, HOME, "attack", mem)
tid = assault_obj_target(acts)
check("20a SIEGE 触发且首目标=防御壳", "SIEGE LOCK-ON" in logs
      and tid in ("p0", "p1", "p2"), "tid=%s" % tid)

# ---- 20b 锁存: 第二次调用保持 siege(即使敌重建矿车也不解除) ----
acts2, logs2 = planner.movement(s, HOME, "attack", mem)
check("20b SIEGE 锁存(不因敌矿车再现解除)", mem.siege_mode is True
      and "SIEGE LOCK-ON" not in logs2)

# ---- 20c 敌经济存活(有矿车) → 不触发, 正常打经济建筑 ----
s, mem = siege_state(armor_n=16, enemy_harv=True)
acts, logs = planner.movement(s, HOME, "attack", mem)
tid = assault_obj_target(acts)
check("20c 敌矿车在 → 不触发, 目标=经济建筑", mem.siege_mode is False
      and tid == "w0", "tid=%s" % tid)

# ---- 20d 战力不足 1.5x → 不触发 ----
s, mem = siege_state(armor_n=4, en_armor_n=6)   # 3600 vs 7400 → 反而劣势
acts, logs = planner.movement(s, HOME, "attack", mem)
check("20d 战力劣势 → 不触发", mem.siege_mode is False)

# ---- 20e 围城编组: 全坦克入突击(无 guard, raid 只剩机器人) ----
s, mem = siege_state(armor_n=16)
s["mine"] += [unit("d0", "DRON", 7, (20, 20))]        # 1 台机器人
acts, logs = planner.movement(s, HOME, "attack", mem)
sq = mem.last_squads
tanks_in_assault = sum(1 for i in sq["assault"] if str(i).startswith("t"))
check("20e 围城: 16 坦克全突击+无 guard+raid 仅机器人",
      tanks_in_assault == 16 and sq["guard"] == [] and set(sq["raid"]) == {"d0"},
      "assault=%d guard=%s raid=%s" % (tanks_in_assault, sq["guard"], sq["raid"]))

# ---- 20f 壳清空后 → 清经济建筑 ----
s, mem = siege_state(armor_n=16, defb=False)
mem.siege_mode = True
acts, logs = planner.movement(s, HOME, "attack", mem)
tid = assault_obj_target(acts)
check("20f 无壳 → 目标=经济建筑", tid == "w0", "tid=%s" % tid)

# ---- 20g 非围城时 guard 保留(回归语义不变) ----
s, mem = siege_state(armor_n=16, enemy_harv=True)
acts, logs = planner.movement(s, HOME, "attack", mem)
sq = mem.last_squads
check("20g 非围城: guard 保留 1 辆", len(sq["guard"]) == 1,
      "guard=%s" % sq["guard"])

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 7 场景通过 ===")
