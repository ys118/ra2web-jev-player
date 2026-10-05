# -*- coding: utf-8 -*-
"""[第78局 防御订单节流 bug fix] 离线场景测试:
23) 确定性生产在途判重——队列快照滞后不再重复下单(77 局实锤: 六连 DEFLINE
    +三连 E2 x4, rush 期 3000 金被订单黑洞抽干, 第 30 局已知竞态复发)。"""
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


def mk_state(t=400, cash=2900, threat_n=8, def_e2=3, def_tank=2, gdef=1):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(gdef):
        mine.append(unit("g%d" % i, "NALASR", 2, (14 + i, 14)))
    for i in range(def_e2):
        mine.append(unit("e%d" % i, "E2", 3, (12 + i, 12)))
    for i in range(def_tank):
        mine.append(unit("t%d" % i, "HTNK", 7, (13, 13)))
    hos = [{"id": "h%d" % i, "n": "E2", "o": 3, "tl": [20 + (i % 3), 20 + i % 3]}
           for i in range(threat_n)]
    s = {"t": t, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: ["NALASR"], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": (1 if i == 3 else 0), "items": []}
                    for i in range(4)],   # q3 忙(坦克在建)= rush 期真实态
         "me": {"credits": cash, "power": {"total": 200, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.rush_defense = True
    mem.enemy_base = (60, 60)
    mem.v3_seen_t = -10**9   # 消除 fresh-mem 幽灵 V3 威胁(见 LESSONS 77 局观察)
    mem.long_fire_t = -10**9
    return s, mem


def count_acts(acts, name):
    return sum(1 for a in acts if a.get("name") == name and a.get("act") == "produce")


# ---- 23a 连续 6 tick 快照滞后 → 哨炮只下 1 单(77 局是 6 单) ----
s, mem = mk_state()
total = 0
for dt in range(6):
    s["t"] = 400 + dt * 2
    _st, acts, _lg = planner.checklist(s, HOME, "defend", mem)
    total += count_acts(acts, "NALASR")
check("23a 六连 tick 哨炮仅 1 单(77 局为 6 单)", total == 1, "orders=%d" % total)

# ---- 23b 超过 60gs 窗口未落地 → 允许重试(拒收自愈) ----
s["t"] = 400 + 62
_st, acts, _lg = planner.checklist(s, HOME, "defend", mem)
check("23b 60gs 未落地允许重试", count_acts(acts, "NALASR") == 1)

# ---- 23c 落地(存量 1→2) → 立即允许下第二座 ----
s2, mem2 = mk_state(t=400, gdef=1)
_st, acts, _lg = planner.checklist(s2, HOME, "defend", mem2)   # 下单第二座
check("23c 首次下单放行", count_acts(acts, "NALASR") == 1)
s2["mine"].append(unit("g9", "NALASR", 2, (15, 14)))            # 落地
s2["t"] = 404
_st, acts, _lg = planner.checklist(s2, HOME, "defend", mem2)   # 存量=2 → cap 满无单
s2["mine"] = [u for u in s2["mine"] if u["n"] != "NALASR"]      # 被拆→存量 0
s2["t"] = 406
_st, acts, _lg = planner.checklist(s2, HOME, "defend", mem2)
check("23c 哨炮被拆(存量变化) → 立即允许重下", count_acts(acts, "NALASR") == 1)

# ---- 23d E2 爆产: 连续 tick 只 1 单(77 局三连 x4) ----
s, mem = mk_state()
total = 0
for dt in range(4):
    s["t"] = 400 + dt * 2
    _st, acts, _lg = planner.checklist(s, HOME, "defend", mem)
    total += count_acts(acts, "E2")
check("23d 四连 tick E2 爆产仅 1 单(77 局为 3 单)", total == 1, "orders=%d" % total)

# ---- 23e E2 落地(存量变化) → 30gs 内也允许下一批 ----
s["mine"] += [unit("n%d" % i, "E2", 3, (40 + i, 12)) for i in range(4)]
s["t"] = 406
_st, acts, _lg = planner.checklist(s, HOME, "defend", mem)
check("23e 上批落地 → 立即允许下一批", count_acts(acts, "E2") == 1)

# ---- 23f 回归: 模式 OFF 时无爆产无哨炮 ----
s, mem = mk_state(threat_n=0)
mem.rush_defense = False
_st, acts, _lg = planner.checklist(s, HOME, "defend", mem)
check("23f 模式OFF 无E2爆产(哨炮走原闸1500合法)",
      count_acts(acts, "E2") == 0)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 6 场景通过 ===")
