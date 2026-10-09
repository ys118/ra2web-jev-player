# -*- coding: utf-8 -*-
"""工厂前置位保护测试（第 59 局单变量）。"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))   # tests/regression/*.py -> 仓库根/src
from ra2web_jev_player.strategy import planner
from ra2web_jev_player.strategy.planner import BattleMemory

AV = {"0": ["NAPOWR", "NAREFN", "NAWEAP", "NAHAND"], "2": ["E2", "ADOG"], "3": ["HARV"]}


def mk(t, blds):
    mine = [{"id": 300 + i, "n": c, "o": 2, "tl": [70, 120 + i], "hp": 100, "mhp": 100}
            for i, c in enumerate(blds)]
    mine.append({"id": 999, "n": "HARV", "o": 7, "tl": [70, 126], "hp": 100, "mhp": 100})
    return {"t": t, "mine": mine, "hostile": [], "queues": [], "av": dict(AV),
            "me": {"credits": 5000}, "map": {"width": 200, "height": 208}}


def ans(build):
    return {"build": {"choice": build, "confidence": 0.7},
            "inf": {"choice": "hold"}, "veh": {"choice": "hold"},
            "stance": {"choice": "develop", "confidence": 0.5}}


s1 = mk(300, ["NAPOWR", "NAREFN"])
st1, a1, l1 = planner.apply_jev(s1, ans("NAREFN"), "develop", BattleMemory())
assert a1 == [] and any("工厂前置位保护" in x for x in l1), "S1 fail: %r | %r" % (a1, l1)
print("S1 战工位次插单 HOLD ✓", l1)

s2 = mk(300, ["NAPOWR", "NAREFN", "NAWEAP"])
st2, a2, l2 = planner.apply_jev(s2, ans("NAHAND"), "develop", BattleMemory())
assert any(a["act"] == "produce" and a["name"] == "NAHAND" for a in a2), "S2 fail: %r" % (a2,)
print("S2 战工建成后放行 ✓", l2)

s3 = mk(300, ["NAPOWR"])
st3, a3, l3 = planner.apply_jev(s3, ans("NAREFN"), "develop", BattleMemory())
assert any(a["act"] == "produce" for a in a3), "S3 fail: %r" % (a3,)
print("S3 矿厂位次放行 ✓", l3)

s4 = mk(300, ["NAPOWR", "NAREFN", "NAHAND"])
st4, a4, l4 = planner.apply_jev(s4, ans("NAHAND"), "develop", BattleMemory())
assert a4 == [] and any("工厂前置位保护" in x for x in l4), "S4 fail: %r | %r" % (a4, l4)
print("S4 战工被拆重建期保护 ✓", l4)
print("=== 全部 4 场景通过 ===")
