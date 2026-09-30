# -*- coding: utf-8 -*-
"""第 62 局反馈修复测试: Jev 产犬封禁 + 规避罚站死锁 + 休整后最安全向再出发。"""
import math
from ra2web_jev_player.strategy import planner
from ra2web_jev_player.strategy.planner import BattleMemory

home = [70, 125]


def H(pid, x, y):
    return {"id": pid, "n": "E2", "o": 3, "tl": [x, y], "hp": 100, "mhp": 100}


def mk(t, dogs=(), hostile=()):
    mine = [{"id": 500 + i, "n": "ADOG", "o": 2, "tl": p, "hp": hp, "mhp": 100}
            for i, (p, hp) in enumerate(dogs)]
    return {"t": t, "mine": mine, "hostile": list(hostile), "queues": [], "av": [],
            "me": {"credits": 5000},
            "map": {"width": 200, "height": 208}}


def ans_inf(choice):
    return {"build": {"choice": "hold"}, "inf": {"choice": choice, "confidence": 0.5},
            "veh": {"choice": "hold"}, "stance": {"choice": "develop", "confidence": 0.5}}


# S1: Jev 产犬被封禁
s1 = mk(300, dogs=())
AV = {"2": ["ADOG", "E2"]}
s1["av"] = dict(AV)
st, a1, l1 = planner.apply_jev(s1, ans_inf("ADOG"), "develop", BattleMemory())
assert a1 == [] and any("犬由侦察线专管" in x for x in l1), (a1, l1)
print("S1: Jev 产犬封禁 ✓", l1)

# S2: 完整罚站死锁场景复现——敌围家, 犬规避→到家→休整→最安全向再出发
mem = BattleMemory()
siege = [H(1, 74, 122), H(2, 66, 128)]          # 敌贴家门
a1, l1 = planner.scouting(mk(200, dogs=(([70, 125], 100),), hostile=(siege)), home, mem)
assert a1 and a1[0]["x"] == home[0] and "规避" in l1, "遇敌应规避撤家"
print("S2a: 遇敌规避 ✓", l1)

# 到家(70,125) 敌仍在(8-14格之间: 敌在74,122 距家~5 格 → 犬在家=敌也在 5 格) → 仍规避
a2, l2 = planner.scouting(mk(260, dogs=(([71, 124], 100),), hostile=(siege)), home, mem)
assert a2 is None, "到家但敌仍近: 处于 hold 或继续规避, 不应远行"
print("S2b: 到家转入休整 ✓")

# 休整 60gs 后(t≥320) → 必须再出发, 且选最安全路标(远离敌)
a3, l3 = planner.scouting(mk(330, dogs=(([71, 124], 100),), hostile=(siege)), home, mem)
print("S3:", l3)
assert a3 and a3[0]["act"] == "move" and "休整毕" in l3, "休整毕必须再出发(不罚站)"
tgt = (a3[0]["x"], a3[0]["y"])
# 最安全 = 离敌(74,122)/(66,128)最远 → 西缘远点如 (12,120) 距敌 ~54; 东缘 (188,y) 距 ~115
assert math.hypot(tgt[0] - 74, tgt[1] - 122) > 60, f"应选远离敌的路标, 实得 {tgt}"

# S4: 出发后遇敌 → 再次规避(循环推进不死)
a4, l4 = planner.scouting(mk(340, dogs=(([80, 120], 100),), hostile=(siege)), home, mem)
assert a4 and "规避" in l4, "再次遇敌应再次规避"
print("S4: 循环推进 ✓", l4)

# S5: 探到基地撤回(回归测试)
mem5 = BattleMemory()
a5, _ = planner.scouting(mk(200, dogs=(([70, 125], 100),)), home, mem5)
mem5.enemy_base = [131, 80]
a5b, l5b = planner.scouting(mk(400, dogs=(([100, 60], 100),)), home, mem5)
assert a5b and a5b[0]["x"] == home[0] and "撤回" in l5b
print("S5: 探到即撤回 ✓")
print("=== 全部 5 场景通过 ===")
