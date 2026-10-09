# -*- coding: utf-8 -*-
"""Second-level battlefield awareness (introduced in game 13, responds within 1
tick): ALARM event recognition and crisis response.

Split verbatim out of strategy/planner.py (2026-10-09 structural refactor):
code moved line by line, zero behavior change; every game-tagged iteration comment
stays at its function.
"""
from __future__ import annotations

import math
import time

from ..doctrine import HARVEST, MCV_CODES, V3_CODES, T
from ..state import nm
from .memory import BattleMemory

# ================= 秒级战场感知 (第 13 局引入, 1 tick 内响应) =================

def sense_events(s: dict, home, mem: BattleMemory):
    """Inter-tick diff: building damage / unit losses / enemy closing in / new
    enemies -> event stream + alarm.

    Building damage is the earliest under-attack signal (earlier than enemies
    entering the radius). Returns alarm or None.
    """
    ev = mem.events
    alarm = None
    # a) 我方建筑掉血
    cur_hp = {}
    for u in s["mine"]:
        if u["o"] == 2:
            cur_hp[u["id"]] = (u["n"], u["hp"], u["mhp"], tuple(u["tl"]))
            prev = mem.bld_hp.get(u["id"])
            if prev and u["hp"] < prev[1] - 1:
                lost = int(prev[1] - u["hp"])
                ev.append("Under attack: %s -%dhp (%d/%d left) @%s"
                          % (u["n"], lost, int(u["hp"]), int(u["mhp"]),
                             list(u["tl"])))
                # [第66局 V3反制] 远程火力签名: 建筑掉血但 13 格内无可见攻击者
                # ——V3 射程 18 >> 我方视野/塔射程, 第 65 局战厂被点名即此形态。
                # 签名照常触发 ALARM 危机响应, 同时点亮 V3 反制生产闸门。
                near_att = [h for h in s["hostile"]
                            if math.hypot(h["tl"][0] - u["tl"][0],
                                          h["tl"][1] - u["tl"][1]) <= 13]
                if not near_att:
                    mem.long_fire_t = s["t"]
                    alarm = {"pos": list(u["tl"]),
                             "what": "long-range fire (likely V3)"}
                elif alarm is None:
                    alarm = {"pos": list(u["tl"]), "what": "%s under attack" % u["n"]}
    mem.bld_hp = cur_hp
    # b) 战斗单位损失
    alive = {u["id"] for u in s["mine"] if u["o"] in (3, 7)}
    for uid, uname in list(mem.unit_ids.items()):
        if uid not in alive:
            ev.append("Unit lost: %s" % uname)
            mem.loss_log.append((s["t"], uname))
            mem.loss_log = mem.loss_log[-12:]
            del mem.unit_ids[uid]
            if alarm is None:
                alarm = {"pos": list(home) if home else [0, 0], "what": "unit lost"}
    for u in s["mine"]:
        if u["o"] in (3, 7) and u["id"] not in mem.unit_ids:
            mem.unit_ids[u["id"]] = nm(u["n"])
    # c) 敌逼近基地 + 受袭频率
    if home:
        near = [h for h in s["hostile"]
                if math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= T["defend_radius"]]
        if near:
            comp = ",".join(nm(h["n"]) for h in near[:4])
            d = min(math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) for h in near)
            ev.append("Enemy closing on base (%d tiles): %s" % (int(d), comp))
            mem.alarm_times.append(time.time())
            mem.alarm_times = [x for x in mem.alarm_times if time.time() - x < 120][-20:]
            if alarm is None:
                alarm = {"pos": list(near[0]["tl"]), "what": "enemy approaching"}
            mem.alarm_log.append((s["t"], alarm["what"], list(alarm["pos"])))
            mem.alarm_log = mem.alarm_log[-8:]
    new_ids = {h["id"] for h in s["hostile"]}
    fresh = new_ids - mem.seen_hostiles
    if fresh:
        fn = [h for h in s["hostile"] if h["id"] in fresh]
        ev.append("Spotted: " + ",".join("%s@%s" % (h["n"], h["tl"]) for h in fn[:4]))
        mem.seen_hostiles = new_ids
    else:
        mem.seen_hostiles |= new_ids
    # [第66局 V3反制] V3 目击记录(持续更新, 生产/猎杀共用的威胁源)
    v3_now = [h for h in s["hostile"] if h["n"] in V3_CODES]
    if v3_now:
        mem.v3_seen_t = s["t"]
        mem.v3_pos = list(v3_now[0]["tl"])
        if any(h["id"] in fresh for h in v3_now):
            ev.append("V3 LAUNCHER spotted @%s - range 18 sniper, outranges all "
                      "towers; Flak Tracks intercept its rockets and hunt it"
                      % mem.v3_pos)
    # [第37局 敌影推定] 首次看见敌军的位置 = 基地方向的最强线索
    if s["hostile"] and mem.first_hostile_pos is None:
        mem.first_hostile_pos = list(s["hostile"][0]["tl"])
    mem.events = ev[-6:]
    if alarm:
        mem.last_alarm_pos = list(alarm["pos"])   # 前哨/伏击位朝向参考
        mem.last_alarm_t = s["t"]                 # [第49局] 侦察反推时效用
    return alarm


def crisis_response(s: dict, home, alarm: dict, mem: BattleMemory,
                    stance: str = "defend") -> tuple:
    """ALARM crisis response (games 19/20 reviews + games 27/30 user observations).

    - In attack/rush stance do **not** recall everyone (game 29 lesson: pulling the
      whole army home the moment ALARM rings = offense interrupted, enemy
      regenerates): fights at the door are left to the tower line + micro; the main
      force is recalled only if the enemy collapses the line (10 tiles deep and
      6+ enemies).
    - Defend stance: counter only at >= 1.2x strength, otherwise TURTLE on the tower
      line (lesson of feeding kills at a steady 37->0).
    - Remote alarm (harvesters hit in enemy territory): send the nearest 2-3 units
      as support, without touching the main force.
    Returns (actions, logline).
    """
    defenders = [u for u in s["mine"]
                 if u["o"] in (3, 7) and u["n"] not in HARVEST
                 and u["n"] not in MCV_CODES          # 基地车不参与反击(送人头)
                 and u["n"] not in ("SENGINEER",)
                 and u["id"] != mem.scout_id          # 侦察车不被危机召回（第34局:
                                                      #   83次ALARM把侦察拽回家=敌基地定位失败）
                 and u["hp"] >= T["retreat_hp"] * (u["mhp"] or 1)
                 and not (mem.enemy_base and math.hypot(
                     u["tl"][0] - mem.enemy_base[0],
                     u["tl"][1] - mem.enemy_base[1]) <= 18)]
                 # [第57局换家, 用户观察] 在敌基地 18 格内的前线部队不被召回——
                 # 敌 14 单位压我家时, 主力继续捅他基地逼其回防, 缩回家=两头空
    if not defenders or time.time() - mem.last_defend_order <= 8:
        return [], None
    d_home = math.hypot(alarm["pos"][0] - home[0], alarm["pos"][1] - home[1]) if home else 0.0
    # 远端告警(矿车远征被袭): 预备队驰援（第31局: 优先 reserve, 不拆前线）
    if home and d_home > 20 and not any(u["o"] == 2 for u in s["mine"]
                                        if math.hypot(u["tl"][0] - alarm["pos"][0],
                                                      u["tl"][1] - alarm["pos"][1]) <= 12):
        alive = {u["id"] for u in s["mine"]}
        res_ids = [i for i in (mem.last_squads.get("reserve") or []) if i in alive]
        if not res_ids:
            res_ids = [u["id"] for u in sorted(
                defenders, key=lambda u: math.hypot(
                    u["tl"][0] - alarm["pos"][0], u["tl"][1] - alarm["pos"][1]))[:3]]
        if res_ids:
            mem.last_defend_order = time.time()
            return ([{"act": "attack_move", "ids": res_ids[:4],
                      "x": alarm["pos"][0], "y": alarm["pos"][1]}],
                    ("t=%d ALARM %s -> RESCUE 预备队 %d 人驰援远端 %s"
                     % (s["t"], alarm["what"], min(4, len(res_ids)), alarm["pos"])))
    if stance in ("attack", "rush"):
        # 攻势保持: 塔阵+微操守家; 敌深入 10 格且 ≥6 个才召回主力（压崩风险）
        inside = [h for h in s["hostile"]
                  if home and math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= 10]
        if len(inside) < 6:
            return [], ("t=%d ALARM %s -> 攻势保持（塔阵守家, 前线 %d 个单位继续进攻）"
                        % (s["t"], alarm["what"], len(defenders)))
        ids = [u["id"] for u in defenders]
        acts = []
        if home:
            acts.append({"act": "attack_move", "ids": ids,
                         "x": home[0], "y": home[1] + 3})
        mem.last_defend_order = time.time()
        return acts, ("t=%d ALARM %s -> 全军回防（敌 %d 深入, 压崩风险）"
                      % (s["t"], alarm["what"], len(inside)))
    mem.last_defend_order = time.time()
    n_en = max(1, len(s["hostile"]))
    ids = [u["id"] for u in defenders]
    if len(defenders) >= 1.2 * n_en or n_en <= 2:
        act = {"act": "attack_move", "ids": ids,
               "x": alarm["pos"][0], "y": alarm["pos"][1]}
        return [act], ("t=%d ALARM %s -> counter %d vs %d -> %s"
                       % (s["t"], alarm["what"], len(defenders), n_en, alarm["pos"]))
    acts = []
    if home:
        acts.append({"act": "attack_move", "ids": ids,
                     "x": home[0], "y": home[1] + 3})
    return acts, ("t=%d ALARM %s -> TURTLE (%d v %d, 守塔阵不打野战)"
                  % (s["t"], alarm["what"], len(defenders), n_en))
