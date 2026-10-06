# -*- coding: utf-8 -*-
"""[第90局 统一生产账本] 离线场景测试:
30) 全局债务闸(_exec 执行入口): 同 tick 三决策器(checklist/opening/jev)各自
    读原始现金互不知晓 → 队列债务失控。88/89 局实证: 同 tick HARV(1400)+
    HTNK x4(3600)+NAHAND(500) 叠 5500 债 vs 现金 ~2600 → q3 僵尸订单饿死堵死
    (下单即锁队列, 现金不足全线暂停不退款) → 坦克全程绝产(峰值 0) → 守住
    900s 仍无进攻能力耗死。债务闸=有效现金(credits-tick_debt)≥造价才放行。
"""
import sys
import time
sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")

from ra2web_jev_player.game import BattleSession as Game
from ra2web_jev_player.strategy.planner import BattleMemory

fails = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail)
    if not cond:
        fails.append(name)


class StubC:
    """client stub: 记录 produce 调用。"""
    def __init__(self):
        self.calls = []

    def produce(self, name, qty):
        self.calls.append((name, qty))


class StubAudit:
    def __init__(self):
        self.logs = []
        self.events = []

    def log(self, line):
        self.logs.append(line)

    def event(self, e):
        self.events.append(e)


def mk_game(credits):
    g = object.__new__(Game)          # 裸实例: 跳过 __init__ 的 browser 依赖
    g.c = StubC()
    g.audit = StubAudit()
    g.mem = BattleMemory()
    g._q_cd = {}
    g._q_used = {0: False, 1: False, 2: False, 3: False}
    g._s = {"t": 400, "me": {"credits": credits}}
    return g


def produce_acts(*items):
    """items: (name, qty) → produce 动作列表(队列号 3/0 交替模拟)。"""
    return [{"act": "produce", "name": n, "qty": qy, "q": 3 if n != "NAHAND" else 0}
            for n, qy in items]


def run(g, acts):
    g._exec(g._s, acts)


# ---- 30a 89局死因场景: 现金 2600, 同 tick HARV+HTNK x4+NAHAND ----
g = mk_game(2600)
run(g, produce_acts(("HARV", 1), ("HTNK", 4), ("NAHAND", 1)))
# HARV 1400 过 → HTNK 3600 被拒(eff 1200) → NAHAND 500 过
check("30a HTNK x4 被债务闸拒绝",
      ("HARV", 1) in g.c.calls and ("HTNK", 4) not in g.c.calls
      and ("NAHAND", 1) in g.c.calls,
      str(g.c.calls))
check("30a 债务累计=1900(≤现金2600)", g.mem.tick_debt == 1900,
      "debt=%d" % g.mem.tick_debt)
check("30a 拒单留 DEBT-GATE 日志",
      any("DEBT-GATE HTNK" in l for l in g.audit.logs), str(g.audit.logs[:2]))

# ---- 30b 现金充足: 全过, 债务=总额 ----
g = mk_game(99999)
run(g, produce_acts(("HARV", 1), ("HTNK", 4), ("NAHAND", 1)))
check("30b 充裕期三单全放行", len(g.c.calls) == 3, str(g.c.calls))
check("30b 债务=1400+3600+500", g.mem.tick_debt == 5500,
      "debt=%d" % g.mem.tick_debt)

# ---- 30c 拒单不设冷却: 现金恢复后同单立即重发可过 ----
g = mk_game(2600)
run(g, produce_acts(("HTNK", 4)))          # 3600 > 2600 → 拒
run(g, produce_acts(("HTNK", 4)))          # 仍拒
g._s["me"]["credits"] = 99999              # 现金恢复
run(g, produce_acts(("HTNK", 4)))          # 应放行(无 25s 冷却残留)
check("30c 拒单不留冷却, 恢复后可重发", ("HTNK", 4) in g.c.calls, str(g.c.calls))

# ---- 30d 逐单扣减: 现金 3000, 两连 HTNK x2(1800x2): 第二单被拒 ----
g = mk_game(3000)
run(g, produce_acts(("HTNK", 2), ("HTNK", 2)))
check("30d 第一单过第二单拒(3000<3600)",
      g.c.calls == [("HTNK", 2)] and g.mem.tick_debt == 1800,
      "calls=%s debt=%d" % (g.c.calls, g.mem.tick_debt))

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("=== 全部 4 场景通过 ===")
