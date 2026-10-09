# -*- coding: utf-8 -*-
"""[第66局 V3反制] 离线场景测试: 生产闸门/猎杀编组/归位/盟军侧无害/远程火力签名。"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))   # tests/regression/*.py -> 仓库根/src

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
s["mine"] += [dict(htk1), dict(htk2), unit("k3", "HTK", 7, (13, 11)),
              unit("k4", "HTK", 7, (14, 11))]
_, acts, logs = planner.checklist(s, home, "defend", mem)
check("4 HTK=4达cap→不产", not any(a.get("name") == "HTK" for a in acts))

# ---- 场景 4b: HTK=3(帽4)→按余量补 1 ----
mem = planner.BattleMemory()
mem.v3_seen_t = 590
s = base_state(hostile=[v3_far])
s["mine"] += [dict(htk1), dict(htk2), unit("k3", "HTK", 7, (13, 11))]
_, acts, logs = planner.checklist(s, home, "defend", mem)
prod = [a for a in acts if a.get("name") == "HTK"]
check("4b HTK=3→补1(按余量封顶)", len(prod) == 1 and prod[0]["qty"] == 1, str(logs))

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


# ---- 场景 10: 电厂应急闸门战厂条件(第67局配套, 两开局下行为验证) ----
from ra2web_jev_player.strategy.doctrine import get_side

IDLE_Q = [{"t": i, "s": 0, "items": []} for i in range(4)]

def pow_case(bl_names, t=300):
    mem = planner.BattleMemory()
    mine = [unit("b0", "NACNST", 2, (10, 10))]
    for i, n in enumerate(bl_names):
        mine.append(unit("b%d" % (i + 1), n, 2, (12 + i, 10)))
    s = base_state(t=t)
    s["mine"] = mine
    s["me"]["power"] = {"total": 0, "drain": 0}   # 0 电容
    s["queues"] = [dict(q) for q in IDLE_Q]       # 真实快照恒含4条队列
    s["av"][0] = list(s["av"][0]) + ["NARADR"]    # 场景11需要
    return s, mem

# 10a: 默认精炼厂先行(开局下一项=NAREFN) → 应急闸不开闸(0电容是预期)
s, mem = pow_case([])
_, acts, _ = planner.checklist(s, home, "develop", mem)
check("10a-1 精炼厂先行开局应急闸不开", not any(a.get("name") == "NAPOWR" for a in acts))
# 10a-2: 回退态(NAPOWR 先行)下电厂是下一项 → 开闸
mem.open_fallback = True
_, acts, _ = planner.checklist(s, home, "develop", mem)
check("10a-2 回退态电厂是下一项→开闸", any(a.get("name") == "NAPOWR" for a in acts))

# 10b: 精炼厂先行序列(电厂排第4) → 战厂建成前应急闸不抢 q0
import ra2web_jev_player.strategy.planner as _P

_real_gs = _P.get_side
def _rf_get_side(s):
    d = _real_gs(s)
    d["opening"] = ["NAREFN", "NAHAND", "NAWEAP", "NAPOWR"]
    return d
_P.get_side = _rf_get_side
s, mem = pow_case(["NAREFN"])               # 新序下 opening_next=NAHAND
_, acts, _ = planner.checklist(s, home, "develop", mem)
ob = planner.opening_build(s, mem)
check("10b-1 精炼厂先行: 闸门不抢电厂", not any(a.get("name") == "NAPOWR" for a in acts))
check("10b-2 精炼厂先行: opening_build 出兵营", ob is not None and ob["name"] == "NAHAND",
      str(ob))
_P.get_side = _real_gs

# 10c: 战厂已建成 + 缺电 → 应急开闸
s, mem = pow_case(["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"])
s["me"]["power"] = {"total": 150, "drain": 130}   # 余量 20 < 60
_, acts, _ = planner.checklist(s, home, "develop", mem)
check("10c 战厂后缺电→应急开闸", any(a.get("name") == "NAPOWR" for a in acts))

# 10d: 中途电厂被拆(战厂在) → 开闸重建
s, mem = pow_case(["NAREFN", "NAHAND", "NAWEAP"])
_, acts, _ = planner.checklist(s, home, "develop", mem)
check("10d 电厂被拆战厂在→开闸", any(a.get("name") == "NAPOWR" for a in acts))


# ---- 场景 11: Jev 插单保护扩展到整个开局序列(第67局配套) ----
_P.get_side = _rf_get_side   # 精炼厂先行
s, mem = pow_case(["NAREFN"])                  # opening_next=NAHAND
ans = {"build": {"choice": "NAPOWR", "confidence": 0.9}}
_, acts, logs = planner.apply_jev(s, ans, "develop", mem, used={})
check("11a 开局期Jev插单被HOLD", not acts and any("前置位保护" in l for l in logs),
      str(logs))
s2, mem2 = pow_case(["NAREFN", "NAHAND", "NAWEAP", "NAPOWR"])   # 序列走完
s2["me"]["power"] = {"total": 200, "drain": 120}
ans2 = {"build": {"choice": "NARADR", "confidence": 0.9}}
_, acts2, logs2 = planner.apply_jev(s2, ans2, "develop", mem2, used={})
check("11b 序列建成后Jev自由建造", any(a.get("name") == "NARADR" for a in acts2),
      str(logs2))
_P.get_side = _real_gs


# ---- 场景 12: 开局自愈回退网(第67局) ----
def open_state(mine_names, q0s=0, t=100):
    mem = planner.BattleMemory()
    mine = [unit("b0", "NACNST", 2, (10, 10))]
    for i, n in enumerate(mine_names):
        mine.append(unit("b%d" % (i + 1), n, 2, (12 + i, 10)))
    s = base_state(t=t)
    s["mine"] = mine
    s["queues"] = [{"t": 0, "s": q0s, "items": []}] + [dict(q) for q in IDLE_Q[1:]]
    s["av"][0] = ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"]
    return s, mem

# 12a: NAREFN 下单后 40gs 无进展 → 拒收 + 整体回退旧序
s, mem = open_state([])
act = planner.opening_build(s, mem)
check("12a-1 首单=NAREFN(精炼厂先行)", act is not None and act["name"] == "NAREFN", str(act))
mem.open_order_t = s["t"] - 50
act2 = planner.opening_build(s, mem)
check("12a-2 40gs无进展→拒收+回退", mem.open_fallback
      and any("FALLBACK" in e for e in mem.open_events), str(mem.open_events))
check("12a-3 回退后首单=NAPOWR", act2 is not None and act2["name"] == "NAPOWR", str(act2))
check("12a-4 opening_next_code 感知回退(NAPOWR 在途未建成=仍下一项)",
      planner.opening_next_code(s, mem) == "NAPOWR",
      planner.opening_next_code(s, mem))

# 12b: NAREFN 受理(q0 building) → 不拒收, 不回退
s, mem = open_state([], q0s=1)
mem.open_order, mem.open_order_t = "NAREFN", s["t"] - 10
planner.opening_build(s, mem)
check("12b 受理中→不拒收不回退(重arming刷新计时)",
      not mem.open_fallback and not mem.open_events
      and mem.open_order_t == s["t"], str(mem.open_events))

# 12c: NAREFN 已建成 → 订单清除, 下一单=NAHAND
s, mem = open_state(["NAREFN", "NAPOWR"])
mem.open_order, mem.open_order_t = "NAREFN", s["t"] - 60
act = planner.opening_build(s, mem)
check("12c 精炼厂落地→下一单兵营", act is not None and act["name"] == "NAHAND", str(act))

# ---- 场景 12d: 引擎把下一项挡在 av0 外(死锁形态, 第67局活局实证) ----
s, mem = open_state([])
s["av"][0] = ["NAPOWR"]                       # NAREFN 不在可造列表(无电厂)
act = planner.opening_build(s, mem)
check("12d-1 av0 无 NAREFN→不下单但武装守望", act is None
      and mem.open_order == "NAREFN", str(act))
mem.open_order_t = s["t"] - 50
act2 = planner.opening_build(s, mem)
check("12d-2 40gs无进展→拒收+回退", mem.open_fallback
      and any("FALLBACK" in e for e in mem.open_events), str(mem.open_events))
check("12d-3 回退后立刻下 NAPOWR", act2 is not None and act2["name"] == "NAPOWR",
      str(act2))
