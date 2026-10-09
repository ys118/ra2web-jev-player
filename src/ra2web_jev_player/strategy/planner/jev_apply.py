# -*- coding: utf-8 -*-
"""Applying Jev answers (gates in doctrine.CONF): batched answers -> actions +
stance adoption.

Split verbatim out of strategy/planner.py (2026-10-09 structural refactor):
code moved line by line, zero behavior change; every game-tagged iteration comment
stays at its function.
"""
from __future__ import annotations

from ..doctrine import CONF, SCOUT_DOGS, THREAT_FORCE_DEFEND, T, get_side
from ..state import available, buildings, queues_by_type, ucost
from .memory import BattleMemory
from .opening import build_gate, opening_next_code

# ================= Jev 答案应用（闸门在 doctrine.CONF） =================

def apply_jev(s: dict, ans: dict, stance: str, mem: BattleMemory,
              used: dict | None = None) -> tuple:
    """Convert batched Jev answers into actions + stance adoption. Returns
    (stance, actions, logs).

    used: queues already claimed by the deterministic layer this tick
    {0/1/2/3: bool} - production orders take effect asynchronously, so the queue
    state in the snapshot lags one tick; without this check items get built twice
    (same race as legacy).
    """
    used = used or {}
    side = get_side(s)
    qs = queues_by_type(s["queues"])
    acts, logs = [], []
    # 建造（确定性清单没花的钱由 jev 决定花法；资金闸门: 坦克资金线优先, 第28局复盘;
    # [第32局] 同类建筑 ≥2 不再买——jev 曾连续买 30 座电厂 12 座兵营）
    b = (ans.get("build") or {}).get("choice")
    if b and b != "hold" and not used.get(0) \
            and qs.get(0, {}).get("s", 0) == 0 and b in available(s["av"], 0):
        # [第58局] 工厂前置位保护; [第67局] 扩展为整个开局序列前置位保护——
        # 精炼厂先行链下兵营/战厂之间同样不容插单(Jev 曾插 4 栋把战工推到 398);
        # 开局序列全部建成后 opening_next_code=None, Jev 恢复自由买建筑。
        _onext = opening_next_code(s, mem)
        if _onext is not None:
            logs.append("t=%d jev BUILD %s HOLD (开局序列前置位保护: 等 %s)"
                        % (s["t"], b, _onext))
        else:
            n_ref = len([u for u in s["mine"] if u["n"] == side["ref"]])
            n_bar = len([u for u in s["mine"] if u["n"] == side["bar"]])
            bl_now = buildings(s["mine"])
            if not (b == side["ref"] and n_ref >= T["ref_cap"]) \
                    and not (b == side["bar"] and n_bar >= 2) \
                    and not (b != side["ref"] and b != side["weap"]
                             and bl_now.get(b, 0) >= 2) \
                    and not (b == side["weap"] and bl_now.get(b, 0) >= 3):
                # [第83局] 战车工厂豁免"同类≥2"通用帽(2→3): 6 矿车收入下产能
                # 翻倍; 其余建筑帽不变([第32局] jev 曾连买 30 电厂的防线保留)
                if build_gate(s, ucost(b), mem, b):
                    acts.append({"act": "produce", "name": b, "qty": 1, "q": 0})
                    logs.append("t=%d jev BUILD %s (conf %.2f)"
                                % (s["t"], b, (ans.get("build") or {}).get("confidence", -1)))
                else:
                    logs.append("t=%d jev BUILD %s HOLD (资金闸门: 坦克优先, cash=%d)"
                                % (s["t"], b, s["me"]["credits"]))
    # 步兵 —— 坦克预算保护（第 24 局复盘：jev 每 tick 产 E2 共 62 个，现金见底率 71%，
    # 坦克峰值仅 5。规则：有战车工厂后，步兵生产不得动用坦克资金线（≥tank_cash1 才许造）；
    # 动员兵 ≥30 停产（性价比之王也会过饱和）；侦察犬不受限（便宜且是眼睛）。
    i = (ans.get("inf") or {}).get("choice")
    if i and i != "hold" and not used.get(2) \
            and qs.get(2, {}).get("s", 0) == 0 and i in available(s["av"], 2):
        # [第62局用户反馈] 军犬由侦察线专管(只养 1 只), Jev 不得插手产犬——
        # 旧豁免(i in SCOUT_DOGS 不限预算)致 Jev 连产 4+ 犬全站基地
        if i in SCOUT_DOGS:
            logs.append("t=%d jev INF %s HOLD (犬由侦察线专管)" % (s["t"], i))
        else:
            bl = buildings(s["mine"])
            n_e2 = len([u for u in s["mine"] if u["n"] == "E2"])
            factory_gate = bl.get(side["weap"], 0) == 0 \
                or s["me"]["credits"] >= T["tank_cash1"] \
                or mem.rush_defense   # [第76局] 防御模式下 E2 不受坦克资金线
            e2_gate = not (i == "E2" and n_e2 >= 30)
            if factory_gate and e2_gate:
                acts.append({"act": "produce", "name": i, "qty": 1, "q": 2})
                logs.append("t=%d jev INF %s (conf %.2f)"
                            % (s["t"], i, (ans.get("inf") or {}).get("confidence", -1)))
            else:
                logs.append("t=%d jev INF %s HOLD (预算保护 gate=%s e2=%d)"
                            % (s["t"], i, factory_gate, n_e2))
    # 载具
    v = (ans.get("veh") or {}).get("choice")
    if v and v != "hold" and not used.get(3) \
            and qs.get(3, {}).get("s", 0) == 0 and v in available(s["av"], 3):
        # [第72局 P1] 载具预算保护+防空存量帽——第 70/71 局实证: clef 经 VEH
        # 通道点名 HTK 58/74 次(无任何资金闸), 细流现金全被 500 级载具吃光,
        # HTNK 每局仅 7 辆且 t<1719 全灭 → 敌潮时刻守家零重坦。与 INF 同款:
        # 载具只在坦克资金线之上买; HTK 另受存量帽(防空补充由确定性 AA 线
        # 专管, 模式同"犬由侦察线专管")
        n_aav_j = len([u for u in s["mine"] if u["n"] == side["aa_v"]]) \
            if side["aa_v"] else 0
        veh_gate = s["me"]["credits"] >= ucost(v) + T["tank_cash1"]
        aav_cap_ok = v != side["aa_v"] or n_aav_j < T["aa_htk_cap"]
        if veh_gate and aav_cap_ok:
            acts.append({"act": "produce", "name": v, "qty": 1, "q": 3})
            logs.append("t=%d jev VEH %s (conf %.2f)"
                        % (s["t"], v, (ans.get("veh") or {}).get("confidence", -1)))
        else:
            logs.append("t=%d jev VEH %s HOLD (预算保护 cash=%d aav帽=%s aav=%d)"
                        % (s["t"], v, s["me"]["credits"],
                           "ok" if aav_cap_ok else "hit", n_aav_j))
    # 态势裁决: ≥0.45 采信（低置信保持原态势防摇摆）
    st_raw = ans.get("stance") or {}
    if st_raw.get("choice") and st_raw.get("confidence", 0) >= CONF["stance"]:
        if st_raw["choice"] != stance:
            logs.append("t=%d jev STANCE %s->%s (conf %.2f)"
                        % (s["t"], stance, st_raw["choice"], st_raw.get("confidence", -1)))
        stance = st_raw["choice"]
    # 威胁概率强制回防
    th = (ans.get("threat") or {})
    th = th.get("noul", th.get("probability", 0)) if isinstance(th, dict) else 0
    if isinstance(th, (int, float)) and th > THREAT_FORCE_DEFEND and stance != "defend":
        logs.append("t=%d THREAT %.2f -> force defend" % (s["t"], th))
        stance = "defend"
    return stance, acts, logs
