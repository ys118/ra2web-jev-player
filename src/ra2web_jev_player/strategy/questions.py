# -*- coding: utf-8 -*-
"""Jev 五问构造（build/inf/veh/stance/threat）。

[第63局用户指示] 全部投喂改为英文（Jev 对英文理解优于中文），并补充战场
动态上下文（趋势/告警史/损失交换/侦察进度/敌军方位/态势史）——原先只有
静态快照+最近 5 条事件，Jev "不知道战场动态"。内部代号仍走 nm_en() 英文名。
"""
from __future__ import annotations

import math

from .doctrine import DOCTRINE_EN, T, get_side
from .state import (UDB, available, buildings, enemy_intel_lines_en, force_value,
                    nm_en, ucost)


def _en(code: str) -> str:
    u = UDB.get(code) or {}
    return "%s [%s]" % (u.get("name") or code, code)


def build_dynamic_section(s: dict, home, mem) -> str:
    """[第63局] 战场动态上下文: 趋势曲线/告警史/交换比/侦察进度/敌军方位/态势史。"""
    lines = []

    # 1) 经济与兵力趋势(最近 6 个观测点, ~37 游戏秒一个)
    if mem.val_history:
        pts = ["[t%d: $%d, mine %d, enemy-visible %d]" % r for r in mem.val_history[-5:]]
        lines.append("Trend (t, credits, my force value, visible enemy value): " + " ".join(pts))
        if len(mem.val_history) >= 2:
            old, new = mem.val_history[-2], mem.val_history[-1]
            d_cred, d_en = new[1] - old[1], new[3] - old[3]
            lines.append("Since last check: credits %s%d, visible enemy value %s%d%s"
                         % ("+" if d_cred >= 0 else "", d_cred,
                            "+" if d_en >= 0 else "", d_en,
                            "  <-- ENEMY ARMY GROWING" if d_en > 500 else ""))

    # 2) 最近告警(类型+位置)
    if mem.alarm_log:
        al = ["[t%d %s @%s]" % r for r in mem.alarm_log[-4:]]
        lines.append("Recent alarms: " + " ".join(al))

    # 3) 交换比(近 120 游戏秒)
    recent_loss = [n for t, n in mem.loss_log if s["t"] - t <= 120]
    recent_kill = [n for t, n in mem.kill_log if s["t"] - t <= 120]
    lines.append("Last 120s exchanges: lost %d units (%s) / killed %d (%s)"
                 % (len(recent_loss), ",".join(recent_loss[:5]) or "-",
                    len(recent_kill), ",".join(recent_kill[:5]) or "-"))

    # 4) 敌军方位(相对基地的方位角+距离)
    if s["hostile"] and home:
        bs = []
        for h in s["hostile"][:8]:
            dx, dy = h["tl"][0] - home[0], h["tl"][1] - home[1]
            dist = math.hypot(dx, dy)
            ang = math.degrees(math.atan2(dy, dx)) % 360
            bs.append("%s@%d tiles(%d°)" % (h["n"], int(dist), int(ang)))
        lines.append("Visible enemy bearing from base: " + ", ".join(bs))

    # 5) 侦察状态
    if mem.dog_task:
        for kid, task in list(mem.dog_task.items())[:2]:
            lines.append("Scout dog #%s: %s, target %s since t%d"
                         % (kid, task.get("mode"), task.get("wp"), task.get("t")))
    else:
        lines.append("Scout dog: none active")

    # 6) 态势史
    cur_for = s["t"] - mem.stance_since
    hist = " ".join("[%t%d %s]".replace("%t", "t") % r for r in mem.stance_hist[-3:]) or "-"
    lines.append("Stance %s held for %ds | history: %s"
                 % (mem.current_stance, cur_for, hist))

    # 7) V3 威胁状态 [第66局 V3反制]
    v3_seen_ago = s["t"] - mem.v3_seen_t
    fire_ago = s["t"] - mem.long_fire_t
    if v3_seen_ago <= 600 or fire_ago <= 120:
        parts = []
        if v3_seen_ago <= 600:
            parts.append("launcher spotted %ds ago @%s"
                         % (v3_seen_ago, mem.v3_pos))
        if fire_ago <= 120:
            parts.append("buildings took long-range fire %ds ago "
                         "(no visible attacker = V3 signature)" % fire_ago)
        lines.append("V3 THREAT ACTIVE: %s. Response: keep Flak Tracks between "
                     "the threat and my production buildings (they intercept V3 "
                     "rockets in flight and chase down the launcher)."
                     % "; ".join(parts))
    return "\n".join(lines)


def build_state_text(s: dict, home, mem) -> str:
    """战场快照 → 分层英文战报（[第63局] 英文投喂 + 动态上下文段）。"""
    cred = s["me"]["credits"]
    pw = s["me"]["power"].get("total", 0)
    drain = s["me"]["power"].get("drain", 0)
    bl = buildings(s["mine"])
    units: dict = {}
    for u in s["mine"]:
        if u["o"] != 2:
            units[u["n"]] = units.get(u["n"], 0) + 1
    qs = {q["t"]: q for q in s["queues"]}

    def ql(t):
        q = qs.get(t)
        if not q:
            return "idle"
        st = {0: "idle", 1: "building", 2: "paused", 3: "READY-TO-PLACE"}.get(q.get("s"), "?")
        its = ",".join("%s%%%d" % (i["n"], i["p"]) for i in q.get("items", [])) or "-"
        return "%s[%s]" % (st, its)

    my_val, en_val = force_value(s)
    ev_txt = "\n".join("· " + e for e in reversed((mem.events or [])[-5:])) or "none"
    lines = [
        "== RECENT EVENTS (newest first, live combat feed) ==",
        ev_txt,
        "== DYNAMIC SITUATION ==",
        build_dynamic_section(s, home, mem),
        "Force value: mine ~%d vs visible enemy ~%d | alarms last 2min: %d"
        % (my_val, en_val, len(mem.alarm_times)),
        "== STATUS ==",
        "Time %ds (~%d min) | cash %d | power %s (margin %d, drain %d / cap %d) | radar %s" % (
            s["t"], s["t"] // 60, cred,
            "LOW POWER!" if s["me"]["power"].get("isLowPower") else "ok",
            pw - drain, drain, pw,
            "disabled" if s["me"].get("radarDisabled") else "ok"),
        "My buildings: %s" % (", ".join("%s x%d" % (_en(k), v)
                                        for k, v in sorted(bl.items())) or "none"),
        "My units: %s" % (", ".join("%s x%d" % (_en(k), v)
                                    for k, v in sorted(units.items())) or "none"),
        "Queues building:%s | defense:%s | infantry:%s | vehicle:%s" % (
            ql(0), ql(1), ql(2), ql(3)),
        "Buildable structures: %s" % _avl(s, 0),
        "Buildable defenses: %s" % _avl(s, 1),
        "Buildable infantry: %s" % _avl(s, 2),
        "Buildable vehicles: %s" % _avl(s, 3),
        "== ENEMY INTEL ==",
        enemy_intel_lines_en(s["hostile"]),
        "Enemy base coordinates: %s" % (mem.enemy_base or "NOT FOUND yet"),
        "My base position: %s" % (home,),
    ]
    return "\n".join(lines)


def _avl(s: dict, t: int) -> str:
    return ", ".join("%s(%dcr)" % (_en(n), ucost(n)) for n in available(s["av"], t)) or "none"


def build_questions(s: dict, home, mem, stance: str = "develop") -> tuple:
    """返回 (state, questions)。候选里已剔除超限项（精炼厂≤3/兵营≤2）。"""
    side = get_side(s)
    n_ref = len([u for u in s["mine"] if u["n"] == side["ref"]])
    n_bar = len([u for u in s["mine"] if u["n"] == side["bar"]])
    av0 = [n for n in available(s["av"], 0)
           if not (n == side["ref"] and n_ref >= T["ref_cap"])
           and not (n == side["bar"] and n_bar >= 2)]
    av2 = available(s["av"], 2)
    av2 = [x for x in av2 if x not in ("ADOG", "DOG")]   # [第62局] 犬由侦察线专管
    av3 = available(s["av"], 3)
    txt = build_state_text(s, home, mem)
    faction = "%s side. Opening sequence: %s" % (
        side["side"], " -> ".join(side["opening"]))
    if side.get("country") == "French":
        faction += (" France special: Grand Cannon GTGCAN (2000cr, 150dmg/range 15, "
                    "needs radar) - strongly consider 1-2 guarding base approaches "
                    "after 3 harvesters.")
    state = {"battlefield": txt, "doctrine": DOCTRINE_EN, "faction": faction,
             "decision_request": (
                 "You are the strategic commander of this battle. Decide the best next "
                 "action based on ALL information above, especially the DYNAMIC "
                 "SITUATION section (trends, alarms, exchanges, enemy bearing). "
                 "Enemy base located: %s. If my force value clearly beats visible "
                 "enemies, or the enemy base is exposed, choose rush/attack and hit "
                 "the enemy base and refineries (cutting economy = harvesters first); "
                 "choose defend ONLY when my base buildings are being attacked AND the "
                 "enemy outnumbers us. Pure defense has no victory condition - hoarding "
                 "troops = losing slowly."
                 % (mem.enemy_base or "not located"))}

    Q = {}
    crit_b = {"hold": "do not start a new building this tick"}
    for n in av0:
        crit_b[n] = "%s (%dcr)" % (_en(n), ucost(n))
    Q["build"] = {"type": "choice",
                  "instructions": ("Build advisor: pick the next structure to start "
                                   "(one per queue). Manual priority: power plant when "
                                   "low > refinery economy (max 3) > barracks (prereq of "
                                   "war factory, produces infantry) > war factory > "
                                   "radar/air command (unlocks tech) > AA > tech center. "
                                   "Weigh the timing window, cash and matchup. When cash "
                                   "is healthy and the queue is idle, NEVER pick hold."),
                  "criteria": crit_b}
    if av2:
        crit_i = {"hold": "no infantry now"}
        for n in av2:
            crit_i[n] = "%s (%dcr)" % (_en(n), ucost(n))
        Q["inf"] = {"type": "choice",
                    "instructions": ("Pick one infantry type to produce. Conscript: 90cr "
                                     "best value, garrisons buildings, defends towers at "
                                     "home. Tesla trooper: anti-armor + charges coils. "
                                     "Flak trooper: mobile AA. Engineer: capture/repair. "
                                     "NOTE: scout dogs are managed by the recon system - "
                                     "do not pick them. Choose per enemy comp and cash; "
                                     "hold when unnecessary."),
                    "criteria": crit_i}
    if av3:
        crit_v = {"hold": "no vehicle now"}
        for n in av3:
            crit_v[n] = "%s (%dcr)" % (_en(n), ucost(n))
        Q["veh"] = {"type": "choice",
                    "instructions": ("Pick one vehicle type. Rhino heavy tank: core "
                                     "mainforce (900cr, 5 shots per Rhino / 4 per "
                                     "Grizzly). Terror drone: assassin vs harvesters/"
                                     "vehicles (400cr, useless vs buildings). Flak "
                                     "track: only mobile AA + anti-infantry "
                                     "(500cr); FIRST RESPONSE to enemy V3 "
                                     "launchers - intercepts V3 rockets in "
                                     "flight and hunts the launcher (game-65 "
                                     "lesson). "
                                     "Apocalypse: tanky AA wall (expensive, slow). V3: "
                                     "buildings only, useless vs units. Tesla tank: "
                                     "short range, kited easily. Choose per strategy "
                                     "and enemy composition."),
                    "criteria": crit_v}
    Q["stance"] = {"type": "choice",
                   "instructions": ("Five-stance arbiter (currently executing: %s). "
                                    "DEVELOP = opening ~5min, no contact: build, scout, "
                                    "save. DEFEND = base threatened: hold tower line. "
                                    "RUSH = within first 10 min with 4+ tanks: strike "
                                    "the enemy base (base swap). ATTACK = 7+ tanks AND "
                                    "enemy base located: flatten production buildings "
                                    "(keep 2 home). RECOVER = main force destroyed: "
                                    "shrink and rebuild economy. "
                                    "Notes: within first 10 min never pick recover "
                                    "unless the main force is wiped; high alarm rate "
                                    "(3+/2min) means the AI is pressuring us - prefer "
                                    "DEFEND over develop; but pure defense has no "
                                    "victory condition - if force value beats visible "
                                    "enemies or the enemy base is located, switch to "
                                    "the attack." % stance),
                   "criteria": {"develop": "develop and save",
                                "defend": "hold base defense",
                                "rush": "early base-swap strike",
                                "attack": "total assault",
                                "recover": "shrink and rebuild"}}
    Q["threat"] = {"type": "noul",
                   "instructions": ("Based on visible enemy count/composition/distance "
                                    "to my base coordinates, judge whether the base is "
                                    "under REAL threat right now (enemies about to hit "
                                    "or already hitting base buildings). Stray units "
                                    "passing far away do not count.")}
    return state, Q
