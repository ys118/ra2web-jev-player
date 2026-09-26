# -*- coding: utf-8 -*-
"""快照访问与知识库：从 __rj.snapshot() 的形状提取战术视图 + RA2-UNITS.json 术语表。

snapshot 形状见 werhd/client.js snapshot()：mine/enemy/hostile 数组的元素是
{id,n,o,tl:[rx,ry],hp,mhp,idle,dep,depd,z}，o = ObjectType（2 建筑/3 步兵/7 载具/1 飞机）。
"""
from __future__ import annotations

import json
import math

from ..paths import KNOWLEDGE_DIR
from .doctrine import AIR_UNITS, COUNTERS, HARVEST, MCV_CODES, TARGET_SCORE

# ================= RA2-UNITS.json 术语表 (代号→中文名/造价/护甲) =================
_UDB_RAW = {}
try:
    _UDB_RAW = json.load(open(KNOWLEDGE_DIR / "RA2-UNITS.json", encoding="utf-8"))
except Exception:
    _UDB_RAW = {"groups": {}, "warheads": {}}

UDB: dict = {}
for _g, _members in (_UDB_RAW.get("groups") or {}).items():
    for _c, _u in _members.items():
        UDB[_c] = {"cn": _u.get("cn") or _u.get("name") or _c,
                   "cost": _u.get("cost", 0), "hp": _u.get("hp", 0),
                   "armor": (_u.get("armor") or "").lower(),
                   "group": _g}
WH: dict = _UDB_RAW.get("warheads") or {}


def nm(code: str) -> str:
    """代号→中文名（Jev 语义术语表的生命线：零信息 gloss 会让模型分票瞎蒙）。"""
    u = UDB.get(code)
    return ("%s" % u["cn"]) if u else (code or "")


def ucost(code: str) -> int:
    u = UDB.get(code)
    return u["cost"] if u else 0


# ================= 视图提取 =================

def buildings(mine: list) -> dict:
    """建筑代号→数量。"""
    bl = {}
    for u in mine:
        if u["o"] == 2:
            bl[u["n"]] = bl.get(u["n"], 0) + 1
    return bl


def unit_counts(mine: list) -> dict:
    uc = {}
    for u in mine:
        if u["o"] != 2:
            uc[u["n"]] = uc.get(u["n"], 0) + 1
    return uc


def queues_by_type(queues: list) -> dict:
    return {q["t"]: q for q in (queues or [])}


def available(av: dict, t: int) -> list:
    v = (av or {}).get(t) or (av or {}).get(str(t)) or []
    return v if isinstance(v, list) else []


def combat_tanks(mine: list, keep_wounded: bool = True) -> list:
    """可机动作战载具（排除矿车/MCV；残血按需过滤）。"""
    out = []
    for u in mine:
        if u["o"] != 7 or u["n"] in HARVEST or u["n"] in MCV_CODES:
            continue
        if not keep_wounded and u["hp"] < 0.40 * (u["mhp"] or 1):
            continue
        out.append(u)
    return out


def yard_tile(s: dict):
    """基地/建造厂位置（mine 里第一座 NACNST/GACNST；开局可能是载具形态 MCV）。"""
    for u in s["mine"]:
        if u["o"] == 2 and u["n"] in ("NACNST", "GACNST"):
            return list(u["tl"])
    for u in s["mine"]:                     # 兜底: 基地车形态
        if u["o"] == 7 and u["n"] in MCV_CODES:
            return list(u["tl"])
    return None


def enemy_air_present(hostile: list) -> bool:
    return any(h["n"] in AIR_UNITS for h in hostile)


def force_value(s: dict) -> tuple:
    """双方机动力量按造价折算: (我方, 视野内敌方)。"""
    my_val = sum(ucost(u["n"]) for u in s["mine"]
                 if u["o"] in (3, 7) and u["n"] not in HARVEST)
    en_val = sum(ucost(h["n"]) for h in s["hostile"])
    return my_val, en_val


def pick_target(s: dict, home):
    """§4.3 目标优先级打分: 矿车>防御塔>生产建筑>…; 距离衰减。返回敌单位或 None。"""
    best, bestv = None, -1
    for h in s["hostile"]:
        base = TARGET_SCORE.get(h["n"], 50 if h["o"] != 2 else 45)
        if home:
            d = math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1])
            base -= d * 0.5
        if base > bestv:
            best, bestv = h, base
    return best


def enemy_intel_lines(hostile: list) -> str:
    """敌情按护甲归类 + 自动附克制建议（喂 Jev 的关键上下文）。"""
    if not hostile:
        return "视野内无敌军"
    byarm: dict = {}
    for h in hostile:
        a = UDB.get(h["n"], {}).get("armor", "?")
        byarm.setdefault(a, []).append(h)
    lines = []
    for a, items in sorted(byarm.items(), key=lambda kv: -len(kv[1])):
        cnt: dict = {}
        for h in items:
            cnt[h["n"]] = cnt.get(h["n"], 0) + 1
        comp = ",".join("%s(%s)x%d@%s" % (k, nm(k), v, items[0]["tl"])
                        for k, v in cnt.items())
        cts = COUNTERS.get(a, [])
        cts_txt = "; ".join("%s=%s" % (nm(c), d) for c, d in cts[:3]) or "无已知克制"
        lines.append("·[%s甲] %s → 克制: %s" % (a, comp, cts_txt))
    return "\n".join(lines)
