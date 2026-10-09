# -*- coding: utf-8 -*-
"""[第95局 击杀冻结检测] 离线场景测试:
33) kill_freeze: 94 局假僵局(enval 冻结 6600s, 90 坦克 6.4 倍战力打不到
    卡位残部)——attack/rush 态势下敌战力值 tick 间不动+我方≥2.5倍碾压
    → 冻结计时; 态势变化/敌值变化/均势任一即复位。"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))   # tests/regression/*.py -> 仓库根/src

from ra2web_jev_player.strategy import planner

fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


def mk_state(my_v_units=90, en_units=2, t=5000):
    """mine/enemy 数量近似战力: HTNK 单价近似, 直接堆单位数。"""
    mine = [unit("b0", "NACNST", 2, (10, 10)), unit("h1", "HARV", 7, (12, 16))]
    mine += [unit("t%d" % i, "HTNK", 7, (14, 14)) for i in range(my_v_units)]
    enemy = [unit("e%d" % i, "E2", 3, (60, 60)) for i in range(en_units)]
    return {"t": t, "mine": mine, "hostile": enemy, "enemy": enemy,
            "av": {0: [], 1: [], 2: [], 3: []},
            "queues": [{"t": i, "s": 0, "items": []} for i in range(4)],
            "me": {"credits": 500, "power": {"total": 200, "drain": 60},
                   "defeated": False, "country": "Russians"},
            "map": {"width": 128, "height": 128}, "players": []}


def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}


# ---- 33a defend 态势不判冻结 ----
s = mk_state(); mem = planner.BattleMemory()
f = planner.kill_freeze(mem, s, "defend")
check("33a defend 态势 → 永不冻结", f == 0, "f=%d" % f)

# ---- 33b attack+碾压+enval 不动 → 计时增长, 满阈值可触发 ----
# (首个 tick 建立基线, 第二个连续 tick 起算——连续 tick 间 1.5s, 实战无影响)
s = mk_state(); mem = planner.BattleMemory()
f1 = planner.kill_freeze(mem, s, "attack")
s["t"] += 3000
f2 = planner.kill_freeze(mem, s, "attack")
s["t"] += 3000
f3 = planner.kill_freeze(mem, s, "attack")
check("33b attack+碾压+enval不动 → 冻结计时增长至阈值",
      f1 == 0 and f2 == 0 and f3 == 3000, "f1=%d f2=%d f3=%d" % (f1, f2, f3))

# ---- 33c 敌战力值变化(在建军/被杀伤) → 复位 ----
s = mk_state(); mem = planner.BattleMemory()
planner.kill_freeze(mem, s, "attack")
s["t"] += 100
s["enemy"][0]["hp"] = 50.0                    # 敌掉血=战力变化
s["enemy"] = [dict(x) for x in s["enemy"]]
f = planner.kill_freeze(mem, s, "attack")
check("33c enval 变化 → 复位", f == 0, "f=%d" % f)

# ---- 33d 均势(我方战力<2.5倍) → 不冻结 ----
s = mk_state(my_v_units=6, en_units=10); mem = planner.BattleMemory()
planner.kill_freeze(mem, s, "attack")
s["t"] += 5000
f = planner.kill_freeze(mem, s, "attack")
check("33d 均势拉锯 → 不冻结", f == 0, "f=%d" % f)

# ---- 33e 态势回落 defend → 复位 ----
s = mk_state(); mem = planner.BattleMemory()
planner.kill_freeze(mem, s, "attack")
s["t"] += 100
f = planner.kill_freeze(mem, s, "defend")
check("33e 态势回落 defend → 复位", f == 0, "f=%d" % f)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 5 场景通过 ===")
