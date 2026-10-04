# -*- coding: utf-8 -*-
"""[第70局 反囤积+编队] 离线场景测试:
17) 威胁过期超额 HTK 回归坦克池编队出击(留2守拦截位), 威胁在场全员防空屏;
18) raid 坦克抽调饥饿保护(突击组保底 3)。"""
import sys
sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")
from ra2web_jev_player.strategy import planner

fails = []
def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond: fails.append(name)

def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}

def sq_state(htks=0, tanks=0, drons=0, v3=None, air=False, enemy_base=None):
    mine = [unit("b0", "NACNST", 2, (130, 82)), unit("b1", "NAPOWR", 2, (128, 82)),
            unit("b2", "NAREFN", 2, (126, 82)), unit("b3", "NAHAND", 2, (124, 82)),
            unit("b4", "NAWEAP", 2, (122, 82))]
    for i in range(htks):
        mine.append(unit("k%d" % i, "HTK", 7, (128 + i, 84)))
    for i in range(tanks):
        mine.append(unit("t%d" % i, "HTNK", 7, (120 + i, 84)))
    for i in range(drons):
        mine.append(unit("r%d" % i, "DRON", 7, (118, 84)))
    hostile = []
    if v3:
        hostile.append(unit("v1", "V3", 7, v3))
    if air:
        hostile.append(unit("j1", "JUMPJET", 1, (100, 60)))
    s = {"t": 2000, "mine": mine, "hostile": hostile, "enemy": [],
         "av": {0: [], 1: [], 2: [], 3: []},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": 3000, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 192, "height": 192}, "players": []}
    mem = planner.BattleMemory()
    mem.enemy_base = enemy_base
    return s, mem

# 17c: V3 威胁在场 → 全员防空屏, 不进坦克池
s, mem = sq_state(htks=4, v3=(140, 60), enemy_base=(60, 120))
mem.v3_seen_t = s["t"]            # sense_events 在真实局里每tick更新, 测试直喂
sq = planner.assign_squads(s, (130, 80), mem, "attack")
in_pool = sum(sq[r].count("k%d" % i) for r in ("raid", "assault", "guard")
              for i in range(4))
check("17c 威胁在场→4辆全aahunt", len(sq["aahunt"]) == 4 and in_pool == 0,
      str({k: sq[k] for k in ("aahunt", "assault", "raid", "guard")}))

# 17d: 威胁全无 + 6辆 → 留2拦截位, 4辆回归坦克池
s, mem = sq_state(htks=6, enemy_base=(60, 120))
sq = planner.assign_squads(s, (130, 80), mem, "attack")
folded = sum(sq[r].count("k%d" % i) for r in ("raid", "assault", "guard")
             for i in range(6))
check("17d 威胁过期→aahunt留2+4辆编队", len(sq["aahunt"]) == 2 and folded == 4,
      str({k: sq[k] for k in ("aahunt", "assault", "raid", "guard")}))

# 17e: 威胁全无 + 2辆 → 全员拦截位(不多不少)
s, mem = sq_state(htks=2, enemy_base=(60, 120))
sq = planner.assign_squads(s, (130, 80), mem, "attack")
check("17e 2辆→全员aahunt", len(sq["aahunt"]) == 2, str(sq["aahunt"]))

# 17f: 空袭在场(无V3) → [第72局 P1b改] 留屏4+超额回归对地(旧"全员屏"语义被取代:
# 70/71局实证 aav_threat 常驻真→全员钉在拦截位, 敌地面潮压家时守家零坦克)
s, mem = sq_state(htks=5, air=True, enemy_base=(60, 120))
sq = planner.assign_squads(s, (130, 80), mem, "attack")
folded_f = sum(sq[r].count("k%d" % i) for r in ("raid", "assault", "guard")
               for i in range(5))
check("17f(72局改) 空袭在场→留屏4+1辆回归对地",
      len(sq["aahunt"]) == 4 and folded_f == 1, str(len(sq["aahunt"])))

# 18a: 坦克4无drone+敌基地 → raid空, 突击3+守家1
s, mem = sq_state(tanks=4, enemy_base=(60, 120))
sq = planner.assign_squads(s, (130, 80), mem, "attack")
check("18a 坦克饥饿→raid 0辆/突击3", sq["raid"] == [] and len(sq["assault"]) == 3,
      str({k: sq[k] for k in ("raid", "assault", "guard")}))

# 18b: 坦克8+drone2 → raid 3(2drone+1坦克)/突击6
s, mem = sq_state(tanks=8, drons=2, enemy_base=(60, 120))
sq = planner.assign_squads(s, (130, 80), mem, "attack")
# 原有语义: DRON(o=7)计入坦克池长度 → n_raid=min(4,(8+2drone+2drone)//3)=4
check("18b 池子充足→raid 4含2drone", len(sq["raid"]) == 4
      and sum(1 for i in sq["raid"] if i.startswith("r")) == 2,
      str(sq["raid"]))
check("18b-2 突击5", len(sq["assault"]) == 5, str(len(sq["assault"])))

# 18c: 无敌基地情报 → raid 照旧抽坦克(骚扰优先)
s, mem = sq_state(tanks=4)
sq = planner.assign_squads(s, (130, 80), mem, "develop")
check("18c 未定位→raid不组建(原有语义: 需敌基地定位)", sq["raid"] == [],
      str(sq["raid"]))

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(0 if not fails else 1)
