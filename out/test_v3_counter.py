# -*- coding: utf-8 -*-
"""[第66局 V3反制] 离线场景测试: 生产闸门/猎杀编组/归位/盟军侧无害/远程火力签名。"""
import sys
sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")

from ra2web_jev_player.strategy import planner
from ra2web_jev_player.strategy.state import queues_by_type


def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}


def base_state(t=600, hostile=None, factory=True, side="soviet"):
    mine = [unit("h1", "HARV", 7, (10, 10)),
            unit("e1", "E2", 3, (11, 11))]
    if factory:
        mine += [unit("b1", "NAPOWR", 2, (10, 12)), unit("b2", "NAREFN", 2, (12, 10)),
                 unit("b3", "NAHAND", 2, (8, 10)), unit("b4", "NAWEAP", 2, (14, 12))]
    av = {0: ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"],
          1: ["NALASR", "NAFLAK"], 2: ["E2", "ADOG"],
          3: (["HTNK", "HTK", "DRON", "V3"] if factory else ["HTNK"])}
    if side == "allied":
        av = {0: ["GAPOWR"], 1: ["GAPILL"], 2: ["GI"], 3: ["MTNK"]}
        mine = [unit("b1", "GAPOWR", 2, (10, 12))]
    return {"t": t, "mine": mine, "hostile": hostile or [], "enemy": [],
            "av": av, "queues": [],
            "me": {"credits": 2000, "power": {"total": 200, "drain": 60},
                   "defeated": False, "country": "Russians" if side == "soviet" else "Americans"},
            "map": {"width": 128, "height": 128}, "players": []}


home = (10, 10)
v3_far = unit("v1", "V3", 7, (26, 10))       # 16 格外: 射程 18 内, 塔够不着
v3_deep = unit("v2", "V3", 7, (60, 60))      # 敌区深处(>26 格): 不猎杀
tank = unit("t1", "HTNK", 7, (12, 10))
htk1 = unit("k1", "HTK", 7, (11, 11))
htk2 = unit("k2", "HTK", 7, (12, 11))

fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


# ---- 场景 1: 视野内 V3 → checklist 产 2×HTK (插在坦克线前) ----
mem = planner.BattleMemory()
s = base_state(hostile=[v3_far, tank])
planner.sense_events(s, home, mem)
_, acts, logs = planner.checklist(s, home, "defend", mem)
prod = [a for a in acts if a["act"] == "produce" and a.get("name") == "HTK"]
check("1a V3可见→产HTK", len(prod) == 1 and prod[0]["qty"] == 2, str(logs))
check("1b V3-RESPONSE 日志", any("V3-RESPONSE" in l for l in logs))
check("1c v3_seen_t 更新", mem.v3_seen_t == s["t"] and mem.v3_pos == [26, 10])

# ---- 场景 2: V3 已离开视野但 600gs 内目击过 → 仍产 ----
mem = planner.BattleMemory()
mem.v3_seen_t = 580; mem.v3_pos = [26, 10]
s = base_state(hostile=[tank])
_, acts, logs = planner.checklist(s, home, "defend", mem)
prod = [a for a in acts if a.get("name") == "HTK"]
check("2 V3目击记忆窗内→仍产HTK", len(prod) == 1, str(logs))

# ---- 场景 2b: 远程火力签名(建筑掉血+视野内无攻击者) → 触发 ----
mem = planner.BattleMemory()
s = base_state(hostile=[])                 # 完全看不到敌人
s["mine"] = [unit("b4", "NAWEAP", 2, (14, 12), hp=140, mhp=1500)]
planner.sense_events(s, home, mem)         # 首帧建基线(不产alarm)
s["mine"][0]["hp"] = 90                    # 掉 50hp, 无可见敌
alarm = planner.sense_events(s, home, mem)
check("2b-1 远程火力签名→alarm", alarm is not None
      and "long-range" in alarm["what"], str(alarm))
_, acts, logs = planner.checklist(s, home, "defend", mem)
prod = [a for a in acts if a.get("name") == "HTK"]
check("2b-2 签名→产HTK", len(prod) == 1, str(logs))

# ---- 场景 3: 无 V3 / 无签名 → 不产 ----
mem = planner.BattleMemory()
s = base_state(hostile=[tank])
_, acts, logs = planner.checklist(s, home, "defend", mem)
check("3 无威胁→不产HTK", not any(a.get("name") == "HTK" for a in acts))

# ---- 场景 4: HTK 存量达 cap → 不再产 ----
mem = planner.BattleMemory()
mem.v3_seen_t = 590
s = base_state(hostile=[v3_far])
s["mine"] += [dict(htk1), dict(htk2), unit("k3", "HTK", 7, (13, 11))]
_, acts, logs = planner.checklist(s, home, "defend", mem)
check("4 HTK=3达cap→不产", not any(a.get("name") == "HTK" for a in acts))

# ---- 场景 5: 猎杀编组 ----
mem = planner.BattleMemory()
s = base_state(hostile=[v3_far, tank])
s["mine"] += [dict(htk1), dict(htk2)]
acts, log = planner.movement(s, home, "defend", mem)
hunt = [a for a in acts if a["act"] == "attack_obj" and set(a["ids"]) == {"k1", "k2"}]
check("5a aahunt 显式攻击V3", len(hunt) == 1 and hunt[0]["tid"] == "v1", str(log))
sq = planner.assign_squads(s, home, mem, "defend")
check("5b HTK不进坦克池", all("k1" not in sq[r] for r in ("raid", "assault", "guard")),
      str({k: sq[k] for k in ("raid", "assault", "guard", "aahunt")}))

# ---- 场景 5c: V3 在敌区深处(>26格) → 不猎杀, 守拦截位 ----
mem = planner.BattleMemory()
s = base_state(hostile=[v3_deep])
s["mine"] += [dict(htk1)]
acts, log = planner.movement(s, home, "defend", mem)
attack_obj = [a for a in acts if a["act"] == "attack_obj"]
check("5c 深处V3→不猎杀", not attack_obj, str(log))

# ---- 场景 6: 无 V3 → 拦截位(威胁方向 10 格) ----
mem = planner.BattleMemory()
mem.enemy_base = [30, 10]
s = base_state(hostile=[tank])
s["mine"] += [dict(htk1)]
acts, log = planner.movement(s, home, "attack", mem)
mv = [a for a in acts if a["act"] == "attack_move" and a["ids"] == ["k1"]]
check("6 无V3→拦截位move", len(mv) == 1 and abs(mv[0]["x"] - 20) <= 1, str(log))

# ---- 场景 7: 盟军侧(aa_v=None)无害 ----
mem = planner.BattleMemory()
mem.v3_seen_t = 590
s = base_state(hostile=[v3_far], side="allied")
_, acts, logs = planner.checklist(s, home, "defend", mem)
check("7 盟军侧无HTK生产", not any(a.get("name") == "HTK" for a in acts))
s["mine"] += [unit("k1", "HTK", 7, (11, 11))]
acts, log = planner.movement(s, home, "defend", mem)
check("7b 盟军侧movement不炸", True, str(log)[:80])

# ---- 场景 8: 威胁过期(>600gs) → 不产 ----
mem = planner.BattleMemory()
mem.v3_seen_t = 580; s_t = 1300
s = base_state(t=s_t, hostile=[tank])
_, acts, logs = planner.checklist(s, home, "defend", mem)
check("8 威胁过期→不产HTK", not any(a.get("name") == "HTK" for a in acts))

# ---- 场景 9: Jev 投喂含 V3 段 ----
from ra2web_jev_player.strategy.questions import build_state_text
mem = planner.BattleMemory()
mem.v3_seen_t = 560; mem.v3_pos = [26, 10]
s = base_state(hostile=[v3_far])
txt = build_state_text(s, home, mem)
check("9 投喂含V3 THREAT段", "V3 THREAT ACTIVE" in txt)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(0 if not fails else 1)
