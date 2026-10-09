# -*- coding: utf-8 -*-
"""[第82局 幻影识别] 离线场景测试:
25) 裂缝产生器(CANRCT)投影 GHOST* 假建筑——81 局实证: 63 辆坦克对幻影打了
    20 分钟零伤害(击杀冻结 191, 敌 630 永不掉)。修法: ①GHOST*/已拉黑 id 不入
    目标池 ②裂缝产生器优先(源头拆掉幻影消散) ③同目标集火 >150gs 不倒=幻影
    拉黑 ④源头灭后拉黑清空全目标重扫。"""
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


def ghost_state(ghost=True, gap=True, defb=False, t=2000):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    mine += [unit("h1", "HARV", 7, (12, 16)), unit("h2", "HARV", 7, (13, 16))]
    for i in range(10):
        mine.append(unit("t%d" % i, "HTNK", 7, (40 + i, 60)))
    hos = [{"id": "w0", "n": "GAWEAP", "o": 2, "tl": [100, 76]}]
    if ghost:
        hos.append({"id": "gh1", "n": "GHOST2", "o": 2, "tl": [98, 74]})   # 假目标(更近)
    if gap:
        hos.append({"id": "gp", "n": "CANRCT", "o": 2, "tl": [96, 72]})
    if defb:
        hos.append({"id": "p0", "n": "GAPILL", "o": 2, "tl": [100, 70]})
    s = {"t": t, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": 2000, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.enemy_base = (100, 74)
    mem.siege_mode = True
    return s, mem


def tank_obj(acts):
    for a in acts:
        if a.get("act") == "attack_obj" and any(str(i).startswith("t") for i in a.get("ids", [])):
            return a
    return None


# ---- 25a GHOST* 不入目标池: 假目标更近也选真建筑 ----
s, mem = ghost_state(ghost=True, gap=False)
acts, logs = planner.movement(s, HOME, "attack", mem)
a = tank_obj(acts)
check("25a GHOST2 被滤除 → 目标=真建筑 w0",
      a is not None and a.get("tid") == "w0", str(a and a.get("tid")))

# ---- 25b 裂缝产生器优先: CANRCT 存在 → 先拆源头 ----
s, mem = ghost_state(gap=True)
acts, logs = planner.movement(s, HOME, "attack", mem)
a = tank_obj(acts)
check("25b CANRCT 优先(源头)", a is not None and a.get("tid") == "gp",
      str(a and a.get("tid")))

# ---- 25c 停滞拉黑: 同目标 >150gs 仍在 → 拉黑换下一个 ----
s, mem = ghost_state(gap=False, t=2000)
acts, _ = planner.movement(s, HOME, "attack", mem)          # 首攻 w0@2000
s["t"] = 2160                                                # +160gs, w0 未倒
acts, logs = planner.movement(s, HOME, "attack", mem)
log_s = logs if isinstance(logs, str) else "; ".join(logs)
check("25c 集火160gs不倒 → GHOST 拉黑(池空走 base)",
      "w0" in mem.ghost_ids or mem.ghost_ids,
      "ghost_ids=%s" % mem.ghost_ids)

# ---- 25d 源头灭 → 拉黑清空重扫 ----
s, mem = ghost_state(gap=True, t=2000)
mem.ghost_ids = {"w0"}                                       # 预拉黑 w0
acts, _ = planner.movement(s, HOME, "attack", mem)           # CANRCT 在场, 首攻 gp
s["hostile"] = [h for h in s["hostile"] if h["n"] != "CANRCT"]  # 源头被拆
s["t"] = 2012
acts, logs = planner.movement(s, HOME, "attack", mem)
check("25d CANRCT 灭 → ghost_ids 清空, w0 可再入选",
      mem.ghost_ids == set() and tank_obj(acts) is not None
      and tank_obj(acts).get("tid") == "w0",
      "ghost=%s tid=%s" % (mem.ghost_ids, tank_obj(acts) and tank_obj(acts).get("tid")))

# ---- 25e 拔壳池同样滤幻影(有真 GAPILL + 假 GHOST 塔更近) ----
s, mem = ghost_state(ghost=True, gap=False, defb=True, t=2000)
s["hostile"].append({"id": "ghp", "n": "GHOST2", "o": 2, "tl": [99, 71]})  # 假塔更近
acts, _ = planner.movement(s, HOME, "attack", mem)
a = tank_obj(acts)
check("25e 拔壳池滤幻影 → 真 GAPILL", a is not None and a.get("tid") == "p0",
      str(a and a.get("tid")))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 5 场景通过 ===")
