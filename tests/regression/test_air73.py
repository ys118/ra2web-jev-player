# -*- coding: utf-8 -*-
"""[第73局 用户反馈防空包] 离线场景测试:
19) ①防空接触规避: 可见空中单位距突击组 ≤air_evade(14) → 全组撤回 AA/塔火力圈
    (坦克打不到空中, 不挨火箭飞行兵白打);
    ②③防空主动猎杀: aahunt 显式攻击最近可见空中单位(不龟缩拦截位), V3 优先级保留。"""
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


def mv_state(airs=(), v3s=(), assault_at=(60, 60), n_htk=4, n_htnk=2):
    mine = [unit("b%d" % i, n, 2, (10 + i, 10)) for i, n in enumerate(BASE_BLD)]
    for i in range(n_htk):
        mine.append(unit("k%d" % i, "HTK", 7, (15 + i, 12)))
    for i in range(n_htnk):
        mine.append(unit("t%d" % i, "HTNK", 7, list(assault_at)))
    hos = [{"id": "eh%d" % i, "n": n, "o": 7, "tl": list(pos)}
           for i, (n, pos) in enumerate(airs)] + \
          [{"id": "v3", "n": "V3", "o": 7, "tl": list(pos)} for pos in v3s]
    s = {"t": 700, "mine": mine, "hostile": hos, "enemy": [],
         "av": {0: [], 1: ["NALASR"], 2: ["E2"], 3: ["HTNK", "HTK", "HARV"]},
         "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
         "me": {"credits": 2000, "power": {"total": 150, "drain": 60},
                "defeated": False, "country": "Russians"},
         "map": {"width": 128, "height": 128}, "players": []}
    mem = planner.BattleMemory()
    mem.enemy_base = (60, 60)
    return s, mem


# ---- 19a aahunt 主动猎杀: 可见 JUMPJET → 显式攻击目标 ----
s, mem = mv_state(airs=[("JUMPJET", (20, 20))])
acts, logs = planner.movement(s, HOME, "attack", mem)
hunt = [a for a in acts if a.get("act") == "attack_obj" and a.get("tid") == "eh0"
        and "k" in str(a.get("ids"))]
check("19a aahunt 显式攻击可见 JUMPJET", bool(hunt),
      str([a for a in acts if a.get("act") == "attack_obj"][:1]))

# ---- 19b 无可见空中 → aahunt 回拦截位(不追假想敌) ----
s, mem = mv_state()
acts, logs = planner.movement(s, HOME, "attack", mem)
check("19b 无空中 → aahunt 走拦截位(无 attack_obj)",
      not any(a.get("act") == "attack_obj" and "k" in str(a.get("ids")) for a in acts),
      str([a.get("act") for a in acts]))

# ---- 19c 防空接触规避: 空中 8 格贴脸突击组 → 全组撤回家+3 ----
s, mem = mv_state(airs=[("JUMPJET", (36, 36))], assault_at=(30, 30))
acts, logs = planner.movement(s, HOME, "attack", mem)
evade = [a for a in acts if a.get("act") == "attack_move"
         and a.get("x") == 13 and a.get("y") == 13 and "t" in str(a.get("ids"))]
check("19c 空中贴脸 → AIR-EVADE 撤回 (13,13)",
      bool(evade) and "AIR-EVADE" in logs,
      str([a for a in acts if a.get("x") == 13][:1]))

# ---- 19d 空中 20+ 格外 → 正常推进(不误伤进攻节奏) ----
s, mem = mv_state(airs=[("JUMPJET", (60, 80))], assault_at=(30, 30))
acts, logs = planner.movement(s, HOME, "attack", mem)
push = [a for a in acts if a.get("act") == "attack_move"
        and a.get("x") == 60 and a.get("y") == 60 and "t" in str(a.get("ids"))]
check("19d 空中远离 → 突击组正常压向敌基地",
      bool(push) and "AIR-EVADE" not in logs,
      str([a.get("act") for a in acts]))

# ---- 19e V3 与空中同时在视野 → V3 显式攻击优先(火箭更致命, 原语义保留) ----
s, mem = mv_state(airs=[("JUMPJET", (20, 20))], v3s=[(18, 18)])
acts, logs = planner.movement(s, HOME, "attack", mem)
v3h = [a for a in acts if a.get("act") == "attack_obj" and a.get("tid") == "v3"
       and "k" in str(a.get("ids"))]
check("19e V3 在 26 格内 → aahunt 优先攻击 V3",
      bool(v3h), str(v3h[:1]))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 5 场景通过 ===")
