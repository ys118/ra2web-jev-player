# -*- coding: utf-8 -*-
"""第 62 局军犬单骑侦察新规 + 步兵驻家 测试。"""
import math
from ra2web_jev_player.strategy import planner
from ra2web_jev_player.strategy.planner import BattleMemory
from ra2web_jev_player.strategy.doctrine import DEF_BUILDINGS

home = [70, 125]


def mk(t, dogs=(), hostile=(), tanks=0, inf=(), base=None):
    mine = [{"id": 500 + i, "n": "ADOG", "o": 2, "tl": p, "hp": hp, "mhp": 100}
            for i, (p, hp) in enumerate(dogs)]
    mine += [{"id": 700 + i, "n": "HTNK", "o": 7, "tl": [70, 126 + i], "hp": 100, "mhp": 100}
             for i in range(tanks)]
    mine += [{"id": 800 + i, "n": "E2", "o": 3, "tl": p, "hp": 100, "mhp": 100}
             for i, p in enumerate(inf)]
    return {"t": t, "mine": mine, "hostile": list(hostile), "queues": [], "av": [],
            "map": {"width": 200, "height": 208}}


def H(pid, x, y):
    return {"id": pid, "n": "E2", "o": 3, "tl": [x, y], "hp": 100, "mhp": 100}


# S1: 1 犬无敌情 → move 指令(非 attack_move)派往网格点
mem = BattleMemory()
a1, l1 = planner.scouting(mk(200, dogs=(([70, 125], 100),)), home, mem)
print("S1:", l1)
assert a1 and a1[0]["act"] == "move", "犬必须用 move(不主动攻击)"

# S2: 遇敌(8 格内) → 立即规避撤家
a2, l2 = planner.scouting(mk(260, dogs=(([100, 110], 100),),
                             hostile=(H(1, 104, 108),)), home, mem)
print("S2:", l2)
assert a2 and a2[0]["act"] == "move" and a2[0]["x"] == home[0] and "规避" in l2

# S3: 规避中(敌 10 格) → 继续撤, 不改派
a3, l3 = planner.scouting(mk(270, dogs=(([90, 118], 100),),
                             hostile=(H(1, 98, 112),)), home, mem)
assert a3 is None, "敌仍在 14 格内应继续撤"
print("S3: 规避中不折腾 ✓")

# S4: [新语义] 规避=回家→休整 60gs→最安全向再出发
a4, l4 = planner.scouting(mk(280, dogs=(([85, 115], 100),),
                             hostile=(H(1, 140, 60),)), home, mem)
assert a4 is None, "规避途中应先回家"
a4b, l4b = planner.scouting(mk(380, dogs=(([71, 124], 100),),
                               hostile=(H(1, 140, 60),)), home, mem)
assert a4b is None, "到家应进入 60gs 休整"
a4c, l4c = planner.scouting(mk(470, dogs=(([71, 124], 100),),
                               hostile=(H(1, 140, 60),)), home, mem)
print("S4:", l4c)
assert a4c and a4c[0]["act"] == "move" and "休整毕" in l4c, "休整毕应最安全向再出发"

# S5: 敌基地定位 → 犬立即撤回(一次性)
mem.enemy_base = [131, 80]
a5, l5 = planner.scouting(mk(400, dogs=(([100, 60], 100),)), home, mem)
print("S5:", l5)
assert a5 and a5[0]["act"] == "move" and a5[0]["x"] == home[0] and "撤回" in l5

# S6: 撤回到家(≤12 格) → 任务清除
a6, l6 = planner.scouting(mk(450, dogs=(([75, 128], 100),)), home, mem)
assert 500 not in mem.dog_task, "到家应清任务"
print("S6: 到家清任务 ✓")

# S7: 阵亡 → 清任务(补员由 replenish 分支处理, 这里验证不崩)
mem7 = BattleMemory()
a7, _ = planner.scouting(mk(200, dogs=(([70, 125], 100),)), home, mem7)
a7b, _ = planner.scouting(mk(260, dogs=()), home, mem7)
assert 500 not in mem7.dog_task
print("S7: 阵亡清理 ✓")

# S8: 步兵全员驻家(assign_squads) — hold=全部步兵, assault=纯坦克
s8 = mk(1000, tanks=6, inf=(([72, 126],) * 10))
mem8 = BattleMemory(); mem8.enemy_base = [131, 80]
sq = planner.assign_squads(s8, home, mem8)
assert len(sq["hold"]) == 10 and sq["reserve"] == [] \
    and len(sq["assault"]) == 2 and len(sq["raid"]) == 2 and len(sq["guard"]) == 2, \
    (len(sq["hold"]), len(sq["assault"]), len(sq["raid"]), len(sq["guard"]), sq["reserve"])
print("S8: 步兵 10 人全驻家, 坦克 6=raid2+guard2+assault2 ✓")

# S9: 二厂门槛 2400
from ra2web_jev_player.strategy.doctrine import T
assert T["factory2_cash"] == 2400, T["factory2_cash"]
print("S9: 二厂门槛 2400 ✓")
print("=== 全部 9 场景通过 ===")
