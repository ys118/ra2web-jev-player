# -*- coding: utf-8 -*-
"""[第77局 防御深化包 II] 离线场景测试:
22) ①RUSH-DEFENSE 爆产 x2→x4/单 ②第二哨炮插单(现金闸 1500→500, 电力闸不动)
    ③早期坦克驻塔线协防(不前出) + 步兵全员驻家 + raid 仅机器人。
    依据: 75/76 局连续苏联镜像 20+ 兵海速败(t=485/668), x2 爆产+2 塔纵深
    跟不上消耗; 75 局唯一首坦前出阵亡。"""
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


def mk_state(cash=600, threat_n=8, def_e2=3, def_tank=2, gdef=1,
             mode=False, enemy_bld=True, extra=()):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    if gdef:
        for i in range(gdef):
            mine.append(unit("g%d" % i, "NALASR", 2, (14 + i, 14)))
    for i in range(def_e2):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i, 12)))
    for i in range(def_tank):
        mine.append(unit("t%d" % i, "HTNK", 7, (13, 13)))
    hos = [{"id": "h%d" % i, "n": "E2", "o": 3, "tl": [20 + (i % 3), 20 + i % 3]}
           for i in range(threat_n)]
    if enemy_bld:
        hos.append({"id": "w0", "n": "GAWEAP", "o": 2, "tl": [60, 60]})
    for n, pos in extra:
        hos.append({"id": "x_%s" % n, "n": n, "o": 7, "tl": list(pos)})
    s = {"t": 400, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: ["NALASR"], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": cash, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.rush_defense = mode
    mem.enemy_base = (60, 60)
    return s, mem


# ---- 22a 爆产 x4/单 ----
s, mem = mk_state(mode=True)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
b = [a for a in acts if a.get("name") == "E2"]
check("22a RUSH-DEFENSE E2 x4", b and b[0].get("qty") == 4,
      str(b[:1]))

# ---- 22b 防御模式: 第二哨炮插单(cash 600 < 1500 旧闸) ----
s, mem = mk_state(mode=True, cash=600, gdef=1)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("22b 模式ON 哨炮插单", any(a.get("name") == "NALASR" for a in acts),
      str([l for l in logs if "DEFLINE" in l][:1]))

# ---- 22c 非模式: cash 600 < 1500 → 无哨炮(原闸回归) ----
s, mem = mk_state(mode=False, cash=600, gdef=1, threat_n=0)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("22c 模式OFF+无威胁 原闸1500生效", not any(a.get("name") == "NALASR" for a in acts))

# ---- 22d 哨炮已满 2 → 不再加 ----
s, mem = mk_state(mode=True, cash=600, gdef=2)
_st, acts, logs = planner.checklist(s, HOME, "defend", mem)
check("22d gdef=2 封顶", not any(a.get("name") == "NALASR" for a in acts))

# ---- 22e 防御模式: 坦克驻塔线协防(不前出) + raid 仅机器人 ----
s, mem = mk_state(mode=True, def_tank=3)
s["mine"].append(unit("d0", "DRON", 7, (18, 18)))
s["hostile"].append({"id": "hv", "n": "HARV", "o": 7, "tl": [90, 90]})  # 敌经济活着
acts, logs = planner.movement(s, HOME, "attack", mem)
sq = mem.last_squads
log_s = logs if isinstance(logs, str) else "; ".join(logs)
home_push = [a for a in acts if a.get("act") == "attack_move"
             and a.get("x") == 13 and a.get("y") == 13
             and any(str(i).startswith("t") for i in a.get("ids", []))]
tanks_in = sum(1 for i in sq["assault"] if str(i).startswith("t"))
check("22e 模式ON 坦克驻塔(13,13)+raid仅机器人+SIEGE让位",
      bool(home_push) and sq["raid"] == ["d0"] and tanks_in == 2
      and "RUSH-DEFENSE tanks" in log_s and "SIEGE LOCK-ON" not in log_s,
      "raid=%s tanks_in=%d" % (sq["raid"], tanks_in))

# ---- 22f 防御模式: 步兵全员驻家(总战争模式不适用) ----
s, mem = mk_state(mode=True, def_e2=6, def_tank=2)
acts, logs = planner.movement(s, HOME, "attack", mem)
sq = mem.last_squads
inf_ids = [i for i in sq["hold"]] + [i for i in sq["assault"]
                                     if str(i).startswith("e")]
check("22f 步兵全员在 hold(无步兵入突击)",
      all(str(i).startswith("e") for i in sq["hold"])
      and not any(str(i).startswith("e") for i in sq["assault"]),
      "hold=%d assault=%s" % (len(sq["hold"]), sq["assault"]))

# ---- 22g 非模式: 坦克正常前出(回归语义) ----
s, mem = mk_state(mode=False, def_tank=3, threat_n=0)
acts, logs = planner.movement(s, HOME, "attack", mem)
push = [a for a in acts if a.get("act") == "attack_obj"
        and any(str(i).startswith("t") for i in a.get("ids", []))]
check("22g 模式OFF 坦克前出打目标", bool(push))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 7 场景通过 ===")
