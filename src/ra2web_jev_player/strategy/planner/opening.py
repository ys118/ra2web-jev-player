# -*- coding: utf-8 -*-
"""Opening build sequence (Bible §5.1/§5.2, faction aware): sequence advance +
building purchase gate + engine-rejection self-heal fallback.

Split verbatim out of strategy/planner.py (2026-10-09 structural refactor):
code moved line by line, zero behavior change; every game-tagged iteration comment
stays at its function.
"""
from __future__ import annotations

from ..doctrine import T, get_side
from ..state import available, buildings, queues_by_type, ucost
from .memory import BattleMemory

# ================= 开局建造序列 (Bible §5.1/§5.2, 阵营感知) =================

# [第67局] 旧合法序(自愈回退目标): NAPOWR 先行, 第 18-59 局实证可行
_OPENING_LEGACY = ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"]


def build_gate(s: dict, cost: int, mem: BattleMemory | None = None,
               code: str | None = None) -> bool:
    """Building purchase gate (game 28 review + game 31 Route A).

    After the war factory lands, cash must be >= cost + tank_cash1 before buying a
    building - otherwise buildings queue up one after another (refinery 1500 each,
    repairs) and the tank funding line is never reached.
    Exceptions: (1) no limit before the factory lands (infrastructure is the
    priority); (2) the RECOVER stance opens it up (after a failed rush the economy
    must be rebuilt for a second wave, Route A's second-wave mechanism);
    (3) [game 71] refinery shortfall exemption - while stock < ref_cap it is not
    bound by the tank funding line. Game 70 (clef's first game) proved it: at a 67%
    bottom-out rate cash never reaches cost + tank_cash1, and the two deterministic
    lines plus the Jev line share the same gate -> triple-refinery deadlock and a
    starved income side (tank peak 14 vs 26 in game 69). This completes game 69's
    "income > throughput" principle in the gate itself; the ref_cap=3 cap bounds the
    exposure, and the gate behavior for non-refinery buildings is unchanged.
    """
    bl = buildings(s["mine"])
    side = get_side(s)
    if bl.get(side["weap"], 0) == 0:
        return True
    if mem is not None and mem.current_stance == "recover":
        return True
    if code == side["ref"] and bl.get(side["ref"], 0) < T["ref_cap"]:
        return True
    # [第83局] 战车工厂(2→3 扩产)与确定性线同闸: factory2_cash, 不再要求
    # 造价+tank_cash1(两条路径统一阈值, 第三厂=产能翻倍配套)
    if code == side["weap"] and bl.get(side["weap"], 0) < 3:
        return s["me"]["credits"] >= T["factory2_cash"]
    return s["me"]["credits"] >= cost + T["tank_cash1"]


def opening_next_code(s: dict, mem: BattleMemory | None = None):
    """First not-yet-built item of the opening sequence (source of truth for the
    build order). [game 58] Used by the factory front-slot protection;
    [game 67] aware self-heal fallback: with open_fallback follow the legacy legal
    order, skipping blacklisted items."""
    side = get_side(s)
    bl0 = buildings(s["mine"])
    opening = _OPENING_LEGACY if (mem and mem.open_fallback) else side["opening"]
    blkl = mem.open_blacklist if mem else set()
    for want in opening:
        if bl0.get(want, 0) == 0 and want not in blkl:
            return want
    return None


def opening_build(s: dict, mem: BattleMemory):
    """Deterministic opening sequence: [game 67] refinery -> barracks -> war factory
    -> power plant (refinery-first chain, isomorphic to the fast openings of games
    33-37, first tank 430 -> ~350); engine-rejection self-heal net: 40gs after
    ordering q0 is still idle and the building has not landed = rejected ->
    blacklist that building; NAREFN rejected = refinery-first without a power plant
    is impossible -> fall back wholesale to the legacy legal order (NAPOWR first,
    proven in games 18-59). The power gap from deferring the plant is covered by
    the power emergency gate (war factory condition) and the DEFLINE margin gate.
    Right after the factory, top up a second refinery (game 20 review); when
    t > rush_t1 and cash > 4500, add the second factory. [game 31 Route A] During
    the rush window (t < rush_t1) build only 1 refinery and no second factory - all
    cash goes to tanks; after RECOVER the gates open to rebuild the economy for a
    second wave. Returns an action or None."""
    side = get_side(s)
    qs = queues_by_type(s["queues"])
    av0 = available(s["av"], 0)
    bl0 = buildings(s["mine"])
    # ---- [第67局] 引擎拒收检测(自愈网) ----
    if mem.open_order:
        built = bl0.get(mem.open_order, 0) > 0
        q0s = qs.get(0, {}).get("s", 0)
        if built or q0s != 0:
            mem.open_order = None                    # 已落地 / 已受理
        elif s["t"] - mem.open_order_t >= 40:
            mem.open_blacklist.add(mem.open_order)
            mem.open_events.append("t=%d OPENING REJECT %s (40gs 无进展, 拉黑)"
                                   % (s["t"], mem.open_order))
            if mem.open_order == "NAREFN" and not mem.open_fallback:
                mem.open_fallback = True
                mem.open_blacklist.clear()
                mem.open_events.append("t=%d OPENING FALLBACK -> legacy NAPOWR-first"
                                       % s["t"])
            mem.open_order = None
    ref_cap_now = 1 if s["t"] < T["rush_t1"] else T["ref_cap"]
    opening_next = None
    for want in (_OPENING_LEGACY if mem.open_fallback else side["opening"]):
        if bl0.get(want, 0) == 0 and want not in mem.open_blacklist:
            opening_next = want
            break
    # [第67局死锁修复] 引擎把下一项挡在可造列表外(如无电厂时 NAREFN 不进 av0)
    # → opening_build 永远不下单, 旧自愈网(依赖"已下单")永不触发, 三方互等
    # (opening 等 av0 / 电厂闸被压制 / Jev 被前置位保护 HOLD)开局冻死——
    # 第 67 局 t=124 零建筑活局实证。修法: 下一项选出即武装守望, 不管单有没有
    # 发得出去; 40gs 无进展统一走拒收+回退。
    if opening_next and mem.open_order is None:
        mem.open_order = opening_next
        mem.open_order_t = s["t"]
    if opening_next is None and bl0.get(side["weap"], 0) >= 1 \
            and bl0.get(side["ref"], 0) < ref_cap_now and side["ref"] in av0 \
            and build_gate(s, ucost(side["ref"]), mem, side["ref"]):
        opening_next = side["ref"]
    # [第87局 防御纵深] 第二兵营前置: 首厂落地即补——步兵双队列对爆 rush
    # 硬窗口产能(86 局 20+ 驻军仍被单队列补给速度磨穿); 兵营 500cr,
    # cash>=1200 闸不夺坦克线。
    if opening_next is None and bl0.get(side["weap"], 0) >= 1 \
            and bl0.get(side["bar"], 0) < 2 and side["bar"] in av0 \
            and s["me"]["credits"] >= 1200:
        opening_next = side["bar"]
    if opening_next is None and s["t"] > T["rush_t1"]:
        # [第42局②] 后期产能解锁: t>2400s 仍单工厂时无条件补第二座——
        # 第 41 局 80 分钟拉锯暴露: 敌方后期波次无上限, 单工厂补充速度跟不上。
        # [第69局 boost_econ] 经济时序重构: ①精炼厂缺额优先于二厂(收入>吞吐);
        # ②二厂去掉 build_gate 叠加(2400+2900 双闸在资金饥饿长局不可逾越,
        # 第 68 局 606-2402 现金从未破 2900 实证), factory2_cash=1800 即真闸,
        # 自带坦克资金线(tank_cash1=900)保护。
        late_game = s["t"] > 2400
        if bl0.get(side["ref"], 0) < T["ref_cap"] and side["ref"] in av0 \
                and build_gate(s, ucost(side["ref"]), mem, side["ref"]):
            opening_next = side["ref"]
        # [第83局 经济军备竞速II] 战车工厂 2→3: 6 矿车收入(81局)下双厂产坦克
        # 追不上敌产能(80局实锤), 第三厂=产能翻倍; 资金闸沿用 factory2_cash。
        elif bl0.get(side["weap"], 0) < 3 and side["weap"] in av0 \
                and (late_game or s["me"]["credits"] > T["factory2_cash"]):
            opening_next = side["weap"]
    if opening_next and qs.get(0, {}).get("s", 0) == 0 and opening_next in av0:
        mem.open_order = opening_next            # [第67局] 自愈网: 记录在途订单
        mem.open_order_t = s["t"]
        return {"act": "produce", "name": opening_next, "qty": 1, "q": 0,
                "tag": "OPENING BUILD %s" % opening_next}
    return None
