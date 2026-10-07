# -*- coding: utf-8 -*-
"""[第101局 下弧线三修复(用户授权全量优化)] 离线场景测试:
36) ①矿车重建通道: n_harv<2 时 HARV 全额负债豁免(0 现金可下单);
    ②单厂期二厂豁免 1900: n_ref==1 且 t>500 → NAREFN eff≥100 即放行
    (99 局死环: 二厂被拦 → n_ref 卡 1 → 矿车上限卡死);
    ③myval_zero: 我方无机动单位 300gs → 优雅退出(99 局拖 15 分钟)。"""
import sys
sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")

from ra2web_jev_player.game import BattleSession as Game
from ra2web_jev_player.strategy import planner

fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


class StubC:
    def __init__(self):
        self.calls = []
    def produce(self, name, qty):
        self.calls.append((name, qty))

class StubAudit:
    def __init__(self):
        self.logs = []; self.events = []
    def log(self, line):
        self.logs.append(line)
    def event(self, e):
        self.events.append(e)


def mk_game(credits, mine, t=900):
    g = object.__new__(Game)
    g.c = StubC(); g.audit = StubAudit()
    g.mem = planner.BattleMemory()
    g._q_cd = {}; g._q_used = {0: False, 1: False, 2: False, 3: False}
    g._s = {"t": t, "me": {"credits": credits}, "mine": mine}
    return g


def unit(uid, n, o, tl, hp=100, mhp=100):
    return {"id": uid, "n": n, "o": o, "tl": list(tl), "hp": hp, "mhp": mhp,
            "idle": True, "dep": False, "depd": None, "z": 0}


def p_act(name, qty=1):
    return {"act": "produce", "name": name, "qty": qty, "q": 3}


# ---- 36a 矿车重建: 矿车 1 辆(n_harv<2)+现金 50 → HARV 全额豁免下单 ----
mine = [unit("h1", "HARV", 7, (12, 16))]
g = mk_game(50, mine)
g._exec(g._s, [p_act("HARV")])
check("36a 矿车重建期 0 现金 → HARV 全额豁免下单",
      ("HARV", 1) in g.c.calls, str(g.c.calls))

# ---- 36b 矿车充足(3 辆) → HARV 仍走 1200 豁免(50 现金不够) ----
mine = [unit("h%d" % i, "HARV", 7, (12 + i, 16)) for i in range(3)]
g = mk_game(50, mine)
g._exec(g._s, [p_act("HARV")])
check("36b 矿车充足时 0 现金 → 不放行(防 89 局债务失控)",
      ("HARV", 1) not in g.c.calls, str(g.c.calls))

# ---- 36c 单厂期二厂: n_ref=1, t=900, eff=150 → NAREFN 豁免 1900 放行 ----
mine = [unit("b0", "NACNST", 2, (10, 10)), unit("r1", "NAREFN", 2, (12, 12))]
g = mk_game(150, mine, t=900)
g._exec(g._s, [p_act("NAREFN")])
check("36c 单厂期 eff=150 → NAREFN 豁免 1900 放行",
      ("NAREFN", 1) in g.c.calls, str(g.c.calls))

# ---- 36d 双厂期: n_ref=2 → NAREFN 回到 1200 豁免(eff=150 < 800 门槛拒) ----
mine = [unit("r1", "NAREFN", 2, (12, 12)), unit("r2", "NAREFN", 2, (14, 12))]
g = mk_game(150, mine, t=900)
g._exec(g._s, [p_act("NAREFN")])
check("36d 双厂期 eff=150 → 拒(1200 豁免不够 2000-150)",
      ("NAREFN", 1) not in g.c.calls, str(g.c.calls))

# ---- 36e myval_zero: 无机动单位 → 计时增长至 300 优雅退出判定 ----
mine = [unit("b0", "NACNST", 2, (10, 10))]        # 只有建筑, 无机动单位
s = {"t": 5000, "mine": mine, "hostile": [], "enemy": [],
     "me": {"credits": 0, "defeated": False}}
mem = planner.BattleMemory()
f1 = planner.myval_zero(mem, s)
s["t"] += 300
f2 = planner.myval_zero(mem, s)
s["t"] += 100
s["mine"].append(unit("t1", "HTNK", 7, (14, 14)))  # 坦克复活
f3 = planner.myval_zero(mem, s)
check("36e myval=0 计时 300gs 后复活单位即复位",
      f1 == 0 and f2 == 300 and f3 == 0, "f1=%d f2=%d f3=%d" % (f1, f2, f3))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 5 场景通过 ===")
