# -*- coding: utf-8 -*-
"""Snapshot access and knowledge base: extract tactical views from the shape of
__rj.snapshot() plus the RA2-UNITS.json glossary.

For the snapshot shape see werhd/client.js snapshot(): elements of the
mine/enemy/hostile arrays are {id,n,o,tl:[rx,ry],hp,mhp,idle,dep,depd,z}, where
o = ObjectType (2 building / 3 infantry / 7 vehicle / 1 aircraft).
"""
from __future__ import annotations

import json
import math

from ..paths import KNOWLEDGE_DIR
from .doctrine import AIR_UNITS, COUNTERS, COUNTERS_EN, HARVEST, MCV_CODES, SCOUT_DOGS, TARGET_SCORE

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
    """Code -> Chinese name (the lifeline of Jev's semantic glossary: a
    zero-information gloss makes the model split its vote and guess blindly)."""
    u = UDB.get(code)
    return ("%s" % u["cn"]) if u else (code or "")


def nm_en(code: str) -> str:
    """Code -> English name ([game 63] English prompts for Jev: better English
    comprehension than Chinese, user directive)."""
    u = UDB.get(code) or {}
    return u.get("name") or (code or "")


def ucost(code: str) -> int:
    u = UDB.get(code)
    return u["cost"] if u else 0


# ================= 视图提取 =================

def buildings(mine: list) -> dict:
    """Building code -> count."""
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
    """Mobile combat vehicles (harvesters/MCV excluded; wounded filtered on demand)."""
    out = []
    for u in mine:
        if u["o"] != 7 or u["n"] in HARVEST or u["n"] in MCV_CODES:
            continue
        if not keep_wounded and u["hp"] < 0.40 * (u["mhp"] or 1):
            continue
        out.append(u)
    return out


def all_combat(mine: list, keep_wounded: bool = True) -> list:
    """All commandable combat units: tanks + infantry (harvesters/MCV/scout
    dogs/engineers excluded; wounded optional).

    [game 30, user observation] movement used to command tanks only - infantry never
    received macro orders, so dozens of conscripts stood around at the base or got
    herded about by micro. Attack waves must include infantry.
    """
    out = []
    for u in mine:
        if u["o"] not in (3, 7):
            continue
        if u["n"] in HARVEST or u["n"] in MCV_CODES or u["n"] in SCOUT_DOGS:
            continue
        if u["n"] in ("SENGINEER",):
            continue
        if not keep_wounded and u["hp"] < 0.40 * (u["mhp"] or 1):
            continue
        out.append(u)
    return out


def yard_tile(s: dict):
    """Base/construction yard position (first NACNST/GACNST in mine; at game start
    it may be a vehicle-form MCV)."""
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
    """Both sides' mobile strength valued by cost: (mine, visible enemy)."""
    my_val = sum(ucost(u["n"]) for u in s["mine"]
                 if u["o"] in (3, 7) and u["n"] not in HARVEST)
    en_val = sum(ucost(h["n"]) for h in s["hostile"])
    return my_val, en_val


def pick_target(s: dict, home):
    """§4.3 target priority scoring: harvester > defense tower > production
    building > ...; distance decay. Returns an enemy unit or None."""
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
    """Enemy intel grouped by armor + automatic counter suggestions (key context
    fed to Jev)."""
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


def enemy_intel_lines_en(hostile: list) -> str:
    """English enemy intel [game 63]: grouped by armor + English counter
    suggestions."""
    if not hostile:
        return "No enemy units in view"
    byarm: dict = {}
    for h in hostile:
        a = UDB.get(h["n"], {}).get("armor", "?")
        byarm.setdefault(a, []).append(h)
    lines = []
    for a, items in sorted(byarm.items(), key=lambda kv: -len(kv[1])):
        cnt: dict = {}
        for h in items:
            cnt[h["n"]] = cnt.get(h["n"], 0) + 1
        comp = ",".join("%s(%s)x%d@%s" % (k, nm_en(k), v, items[0]["tl"])
                        for k, v in cnt.items())
        cts = COUNTERS_EN.get(a, [])
        cts_txt = "; ".join("%s=%s" % (c, d) for c, d in cts[:3]) or "no known counter"
        lines.append("- [%s armor] %s -> counters: %s" % (a, comp, cts_txt))
    return "\n".join(lines)
