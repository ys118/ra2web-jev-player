# -*- coding: utf-8 -*-
"""[第92局 进攻协同包(用户两条战术指示)] 离线场景测试:
31) ①步坦协同: 坦克编队出击 → 步兵留守 4(rush_defense 抬到驻军地板 8),
    超出全部编入突击组跟随——91 局实证 defend 态势下坦克波次出击而步兵
    14-15 全程蹲伏击位看戏, 坦克被敌步兵白打(步坦脱节);
    ②坦克点名集中火力: 敌单位距编组重心 ≤14 → 全组 order_obj 点名同一
    目标(敌步行单位优先, 一个一个歼灭), 目标存活续打不换。
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


BASE_BLD = ["NACNST", "NAPOWR", "NAREFN", "NAHAND", "NAWEAP"]
HOME = (10, 10)


def mk_state(inf_n=12, tank_n=6, threat=(), enemy_base=(60, 60),
             mode_pre=False, extra_hostile=()):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(inf_n):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i % 4, 12 + i // 4)))
    for i in range(tank_n):
        mine.append(unit("t%d" % i, "HTNK", 7, (14 + i % 3, 14 + i // 3)))
    hos = [dict(h) for h in threat]
    hos += [dict(h) for h in extra_hostile]
    s = {"t": 900, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": 3000, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    if enemy_base:
        mem.enemy_base = enemy_base
    if mode_pre:
        mem.rush_defense = True
    return s, mem


# ---- 31a 步坦协同(非 rush_defense): 12 步兵 → hold 4 + 突击组含 8 步兵 ----
s, mem = mk_state(inf_n=12, tank_n=6)
_acts, _log = planner.movement(s, HOME, "defend", mem)
sq = mem.last_squads
check("31a 坦克出击(敌基地定位)+defend 态势 → 步兵留守 4 超出跟随",
      len(sq["hold"]) == 4 and len([i for i in sq["assault"]
                                    if any(u["id"] == i and u["n"] == "E2"
                                           for u in s["mine"])]) == 8,
      "hold=%d assault=%d" % (len(sq["hold"]), len(sq["assault"])))

# ---- 31b 步坦协同(rush_defense): 留守抬到 8, 超出 4 跟随 ----
# (rush_defense 时坦克不进 raid → guard 抽 1, 突击 5 坦克 + 4 步兵)
s, mem = mk_state(inf_n=12, tank_n=6, mode_pre=True)
_acts, _log = planner.movement(s, HOME, "defend", mem)
sq = mem.last_squads
_inf_in_assault = len([i for i in sq["assault"]
                       if any(u["id"] == i and u["n"] == "E2" for u in s["mine"])])
check("31b rush_defense 时留守 8(驻军地板)超出 4 跟随",
      len(sq["hold"]) == 8 and _inf_in_assault == 4,
      "hold=%d assault=%d(含步兵%d)" % (len(sq["hold"]),
                                        len(sq["assault"]), _inf_in_assault))

# ---- 31c 点名: 敌步兵+敌坦克近旁 → 全组攻击敌步兵(优先)同一 id ----
threat = [{"id": "x1", "n": "E2", "o": 3, "tl": [20, 20]},      # 敌步兵(近)
          {"id": "x2", "n": "HTNK", "o": 7, "tl": [24, 20]}]   # 敌坦克(稍远)
s, mem = mk_state(inf_n=4, tank_n=6, threat=threat)
_acts, log = planner.movement(s, HOME, "defend", mem)
ff = [a for a in _acts if a.get("act") == "attack_obj"]
check("31c 野战点名 → 全组 attack_obj 同一目标(敌步兵 x1 优先)",
      ff and ff[0].get("tid") == "x1" and len(ff[0].get("ids", [])) >= 3
      and "FOCUS-FIRE" in log,
      str([a.get("tid") for a in ff]) + " | " + log[:80])

# ---- 31d 目标存活 → 续打同一目标(12s 节流内可静默不重发) ----
_acts2, log2 = planner.movement(s, HOME, "defend", mem)
ff2 = [a for a in _acts2 if a.get("act") == "attack_obj"]
check("31d 目标存活续打(节流内静默或同 id 重发)",
      not any("FOCUS-FIRE" in l for l in [log2])
      and (not ff2 or ff2[0].get("tid") == "x1"),
      str([a.get("tid") for a in ff2]))

# ---- 31e 目标死亡 → 换池内下一个 ----
s["hostile"] = [h for h in s["hostile"] if h["id"] != "x1"]
_acts3, log3 = planner.movement(s, HOME, "defend", mem)
ff3 = [a for a in _acts3 if a.get("act") == "attack_obj"]
check("31e 目标死亡换下一个(x2)",
      ff3 and ff3[0].get("tid") == "x2", str([a.get("tid") for a in ff3]))

# ---- 31f 无近旁敌单位 → 落回推进逻辑(敌基地点名非防御建筑) ----
s, mem = mk_state(inf_n=4, tank_n=6,
                  extra_hostile=[{"id": "w1", "n": "GAWEAP", "o": 2,
                                  "tl": [60, 60]}])
_acts4, log4 = planner.movement(s, HOME, "defend", mem)
ff4 = [a for a in _acts4 if a.get("act") == "attack_obj"]
am = [a for a in _acts4 if a.get("act") == "attack_move"]
check("31f 无近旁敌单位 → 无 FOCUS-FIRE, 走建筑点名/推进",
      not any("FOCUS-FIRE" in l for l in [log4]) and (ff4 or am),
      log4[:80])

# ---- 31g SIEGE 时不点名(拔壳链优先) ----
s, mem = mk_state(inf_n=4, tank_n=9, threat=threat)
mem.siege_mode = True
_acts5, log5 = planner.movement(s, HOME, "attack", mem)
check("31g 围城阶段不走野战点名",
      not any("FOCUS-FIRE" in l for l in [_acts5[0].get("tag", "") if _acts5 else "",
                                          log5]),
      log5[:80])

# ---- 31h 坦克未出击(无敌基地+坦克全守家) → 步兵全员驻家(62 局规则保持) ----
s, mem = mk_state(inf_n=8, tank_n=1, enemy_base=None)
_acts6, _log6 = planner.movement(s, HOME, "develop", mem)
sq = mem.last_squads
_inf_out = len([i for i in sq["assault"]
                if any(u["id"] == i and u["n"] == "E2" for u in s["mine"])])
check("31h(100局改) 坦克未出击 → 守备6+扫荡队2(步兵任务化, 不蜷家)",
      len(sq["hold"]) == 6 and len(sq["sweep"]) == 2,
      "hold=%d sweep=%d" % (len(sq["hold"]), len(sq["sweep"])))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 8 场景通过 ===")
