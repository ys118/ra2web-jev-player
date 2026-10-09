# -*- coding: utf-8 -*-
"""Reconnaissance and enemy base location: scout-dog waypoint net + tank mirror
scouting + enemy-shadow/ALARM inference.

Split verbatim out of strategy/planner.py (2026-10-09 structural refactor):
code moved line by line, zero behavior change; every game-tagged iteration comment
stays at its function.
"""
from __future__ import annotations

import math
import time

from ..doctrine import AA_VEHICLES, SCOUT_DOGS, get_side
from ..state import available, combat_tanks, queues_by_type
from .memory import BattleMemory


def contact_edge(s: dict, home, pos):
    """Probe point ~92% of the way to the map edge, along the unit vector from home
    toward a contact point.

    [shared by game 37 enemy-shadow inference / game 49 ALARM inference] dist < 3
    counts as no direction information (contact right at the door).
    """
    if not home or pos is None:
        return None
    mx, my = s["map"]["width"], s["map"]["height"]
    dx = pos[0] - home[0]
    dy = pos[1] - home[1]
    dist = math.hypot(dx, dy)
    if dist < 3:
        return None                                  # 接触点就在家门口, 无方向信息
    ux, uy = dx / dist, dy / dist
    cand = []
    if ux > 1e-6:
        cand.append((mx - 4 - home[0]) / ux)
    if ux < -1e-6:
        cand.append((4 - home[0]) / ux)
    if uy > 1e-6:
        cand.append((my - 4 - home[1]) / uy)
    if uy < -1e-6:
        cand.append((4 - home[1]) / uy)
    cand = [c for c in cand if c > 0]
    if not cand:
        return None
    t = min(cand) * 0.92
    return [int(min(max(home[0] + ux * t, 4), mx - 4)),
            int(min(max(home[1] + uy * t, 4), my - 4))]


def shadow_target(s: dict, home, mem: BattleMemory):
    """Enemy-shadow inference [game 37, Jev 0.88]: infer the base direction from
    where enemies first appeared. Returns None without a contact record."""
    return contact_edge(s, home, mem.first_hostile_pos)


# ================= 侦察与敌基地定位 =================

def update_enemy_base(s: dict, mem: BattleMemory) -> bool:
    for h in s["hostile"]:
        if h["o"] == 2:
            if mem.enemy_base is None:
                pass  # 首次发现的日志由 game.py 打（本层不持 logger）
            mem.enemy_base = list(h["tl"])   # 持续更新到最新看见的建筑
            return True
    return False


def scouting(s: dict, home, mem: BattleMemory):
    """Single scout dog + dedicated scout-vehicle grid mapping.

    [game 62 user itemized directive] Dogs: keep exactly 1, task = map the terrain to
    find the enemy base; always move orders (never attack on the way); evade home
    immediately when an enemy is within 8 tiles, set out again once 14 tiles are
    clear; retreat immediately when the enemy base is found; on death a replacement
    is queued. Waypoints = lawnmower grid (row spacing 18 = vision 9 x 2, seamless).
    Scout vehicles: multi-waypoint rotation with a 150s throttle + ALARM inference
    breaking the throttle ([game 49]) + a second vehicle ([game 37]).
    """
    side = get_side(s)
    qs = queues_by_type(s["queues"])
    av2 = available(s["av"], 2)
    last_edge = contact_edge(s, home, mem.last_alarm_pos)  # [第49局] ALARM 来向反推
    # [第62局用户指示] 只养 1 只侦察犬(不需要太多), 阵亡再补 1 只
    if side["bar"] in [u["n"] for u in s["mine"] if u["o"] == 2]             and not mem.dogs_queued and "ADOG" in av2 and qs.get(2, {}).get("s", 0) == 0:
        mem.dogs_queued = True
        # 返回必须是动作列表（第40局: 单 dict 被 _exec 迭代成键字符串 → 'str' object
        # has no attribute 'get'）
        return ([{"act": "produce", "name": "ADOG", "qty": 1}],
                "t=%d SCOUT dog x1" % s["t"])
    dogs_alive = [u for u in s["mine"] if u["n"] in SCOUT_DOGS]
    if side["bar"] in [u["n"] for u in s["mine"] if u["o"] == 2] \
            and len(dogs_alive) < 1 and "ADOG" in av2 and qs.get(2, {}).get("s", 0) == 0 \
            and time.time() - mem.last_dog_replenish > 60:
        mem.last_dog_replenish = time.time()
        return ([{"act": "produce", "name": "ADOG", "qty": 1}],
                "t=%d SCOUT dog replenish x1 (alive %d)" % (s["t"], len(dogs_alive)))
    # [第62局用户逐条指示] 军犬单骑侦察新规:
    #  只 1 犬; 任务=探图找敌基地, 中途绝不主动攻击(一律 move 指令, 非 attack_move);
    #  遇敌(8 格内)立即规避撤回家, 脱险(14 格无敌)再出发; 探到敌基地立即撤回;
    #  阵亡由补员补 1 只再出发。割草机网格(行距 18=视野 9×2 无缝)仍是路标来源。
    if mem.enemy_base and mem.dog_task:
        alive = {u["id"]: u for u in s["mine"] if u["n"] in SCOUT_DOGS}
        rec = []
        for kid, task in list(mem.dog_task.items()):
            if kid not in alive:
                del mem.dog_task[kid]
                continue
            if task.get("mode") != "retreat":
                rec.append({"act": "move", "ids": [kid], "x": home[0], "y": home[1]})
                mem.dog_task[kid] = {"wp": (home[0], home[1]), "t": s["t"], "mode": "retreat"}
            elif math.hypot(alive[kid]["tl"][0] - home[0],
                            alive[kid]["tl"][1] - home[1]) <= 12:
                del mem.dog_task[kid]            # 已到家
        if rec:
            return rec, "t=%d SCOUT dog 探到敌基地→立即撤回" % s["t"]
        return None, None
    if home and not mem.enemy_base:
        mx, my = s["map"]["width"], s["map"]["height"]
        waypoints = []
        for _y in range(12, my - 10, 18):                # 行距 18 = 2×犬视野 9
            waypoints += [[12, _y], [mx - 12, _y]]
        # [第93局 fix_scout(Jev 连续 4 局 0.9 置信)] 路标网注入腹部+镜像锚点:
        # 原两列边缘网探不到地图腹部(87-91 局敌基地全在 (67,115) 一带=腹部);
        # 且敌兵海压家时"最安全"悖论把军犬吸去远角(92 局犬探 (188,*) 死角,
        # 敌基地近在镜像区却永无访次) → raid/assault 无目标断不了敌经济。
        _mirror = [max(mx - home[0], 8), max(my - home[1], 8)]
        waypoints += [_mirror,                            # 镜像角(31局 Route A 假设)
                      [mx // 2, my // 2],                 # 地图中心
                      [mx // 3, my // 3], [2 * mx // 3, my // 3],
                      [mx // 3, 2 * my // 3], [2 * mx // 3, 2 * my // 3],
                      [max(mx - home[0], 8), 12], [12, max(my - home[1], 8)]]
        acts, logs = [], []

        def dispatch(d, target, tag, evade=False):
            mem.dog_task[d["id"]] = {"wp": tuple(target), "t": s["t"],
                                     "mode": "evade" if evade else "go"}
            acts.append({"act": "move", "ids": [d["id"]], "x": target[0], "y": target[1]})
            logs.append("t=%d %s #%s->%s%s" % (s["t"], tag, d["id"], target,
                                               " (遇敌规避)" if evade else ""))

        def safety(w):
            """Waypoint safety: distance to the nearest visible enemy (large enough
            when no enemy is visible)."""
            if not s["hostile"]:
                return 999.0
            return min(math.hypot(w[0] - h["tl"][0], w[1] - h["tl"][1])
                       for h in s["hostile"])

        dogs_ok = [u for u in s["mine"] if u["n"] in SCOUT_DOGS
                   and u["hp"] >= 0.30 * (u["mhp"] or 1)]
        alive_ids = {u["id"] for u in dogs_ok}
        for kid in [k for k in mem.dog_task if k not in alive_ids]:
            del mem.dog_task[kid]                        # 阵亡犬任务清理(补员自动再出发)
        if dogs_ok:
            lead = shadow_target(s, home, mem) or last_edge
            lead_fresh = lead and (s["t"] - mem.scout_visit.get(tuple(lead), -10 ** 9) > 240)
            used = set()
            for i, d in enumerate(dogs_ok):
                near = [h for h in s["hostile"]
                        if math.hypot(h["tl"][0] - d["tl"][0],
                                      h["tl"][1] - d["tl"][1]) <= 8]
                task = mem.dog_task.get(d["id"])
                mode = task.get("mode") if task else None
                # [第62局反馈] 罚站死锁修复: 规避撤到家 → 短暂休整 60gs →
                # 从最安全的未访路标再出发(绝不无限罚站); 再遇敌再规避, 循环推进
                if mode == "evade":
                    if math.hypot(d["tl"][0] - home[0],
                                  d["tl"][1] - home[1]) > 12:
                        if s["t"] - task["t"] <= 60:
                            used.add(task["wp"])         # 撤退途中: 继续回家
                            continue
                        # [第68局] 撤退 60gs 仍未到家 = 卡死(地形卡住/指令丢失,
                        # 第 67 局军犬 t=153 后永久沉默即此形态): 不再罚站,
                        # 落到下方重派逻辑去最安全未访路标
                    else:
                        task["mode"], task["hold_until"] = "hold", s["t"] + 60
                        mode = "hold"                    # 到家: 休整 60gs
                if mode == "hold":
                    if s["t"] < task["hold_until"]:
                        continue                         # 休整中(短暂驻家, 非罚站)
                    cands = [w for w in waypoints if tuple(w) not in used]
                    if cands:
                        tgt = max(cands, key=lambda w: (min(safety(w), 60),
                                                        -mem.scout_visit.get(tuple(w), -1)))
                        task["mode"], task["wp"], task["t"] = "go", tuple(tgt), s["t"]
                        mem.scout_visit[tuple(tgt)] = s["t"]
                        used.add(tuple(tgt))
                        acts.append({"act": "move", "ids": [d["id"]],
                                     "x": tgt[0], "y": tgt[1]})
                        logs.append("t=%d SCOUT dog 休整毕 #%s->%s (最安全向)"
                                    % (s["t"], d["id"], tgt))
                    continue
                if near:                                 # [用户指示] 遇敌立即规避
                    dispatch(d, [home[0], home[1]], "SCOUT dog 遭遇规避", evade=True)
                    continue
                if task and mode == "go":
                    dist = math.hypot(d["tl"][0] - task["wp"][0],
                                      d["tl"][1] - task["wp"][1])
                    if dist > 6 and s["t"] - task["t"] <= 240:
                        used.add(task["wp"])             # 在途: 不打断
                        continue
                    mem.scout_visit[task["wp"]] = s["t"]  # 到达/超时: 记访问
                if i == 0 and lead and lead_fresh:
                    tgt, tag = list(lead), "SCOUT dog*"
                else:
                    cands = [w for w in waypoints if tuple(w) not in used]
                    if not cands:
                        continue
                    tgt = min(cands, key=lambda w: (mem.scout_visit.get(tuple(w), -1),
                                                    math.hypot(w[0] - d["tl"][0],
                                                               w[1] - d["tl"][1])))
                    tag = "SCOUT dog"
                dispatch(d, tgt, tag)
            if acts:
                return acts, "; ".join(logs)

    tanks = [u for u in combat_tanks(s["mine"]) if u["n"] not in AA_VEHICLES]
    if not tanks or not home:
        return None, None
    alive1 = bool(mem.scout_id) and any(u["id"] == mem.scout_id for u in tanks)
    alive2 = bool(mem.scout2_id) and any(u["id"] == mem.scout2_id for u in tanks)
    shadow = shadow_target(s, home, mem)
    mx, my = s["map"]["width"], s["map"]["height"]
    waypoints = [
        [max(mx - home[0], 8), max(my - home[1], 8)],   # 镜像角
        [mx // 2, my // 2],                             # 地图中心
        [12, my // 2], [12, 12], [mx - 12, 12],
        [mx - 12, my - 12], [12, my - 12],              # 四角
    ]
    acts, logs = [], []

    def pick_wp(exclude=None):
        wps = [w for w in waypoints if tuple(w) != exclude]
        return min(wps, key=lambda w: mem.scout_visit.get(tuple(w), -1))

    def dispatch(sid, target, tag):
        mem.scout_visit[tuple(target)] = s["t"]
        acts.append({"act": "attack_move", "ids": [sid], "x": target[0], "y": target[1]})
        logs.append("t=%d %s #%s->%s%s" % (s["t"], tag, sid, target,
                                           " (敌影)" if shadow == target else ""))

    # 主侦察: 死车立即重派(不受节流); 活车按 150s 节流换路标; 已定位则停;
    # [第49局] 新鲜 ALARM(≤150 游戏秒, 距上次反推 ≥60s)破节流即时沿来向反推
    # [第68局] 敌影推定降级为"仅新鲜时用": 第 67 局 5 次反复沿 first_hostile_pos
    # 奔同一错误边缘(首接触方向 ≠ 基地方向), 侦察全程空转——改为 visit 记录
    # 240gs 内去重, 否则回退未访路标轮转(第 63 局网格扫荡定位的成功路径)。
    def shadow_fresh():
        return bool(shadow) and (s["t"] - mem.scout_visit.get(tuple(shadow), -10 ** 9) > 240)

    if not alive1 and tanks:
        mem.scout_id = tanks[0]["id"]
        dispatch(mem.scout_id, last_edge or (shadow if shadow_fresh() else None)
                 or pick_wp(), "SCOUT")
    elif alive1 and not mem.enemy_base:
        if (last_edge and s["t"] - mem.last_alarm_t <= 150
                and s["t"] - mem.alarm_scout_t >= 60):
            mem.alarm_scout_t = s["t"]
            dispatch(mem.scout_id, last_edge, "SCOUT*")
        elif time.time() - mem.last_scout > 150:
            dispatch(mem.scout_id, shadow if shadow_fresh() else pick_wp(), "SCOUT")
    mem.last_scout = time.time() if acts else mem.last_scout

    # 第二侦察车: 坦克池≥4 且未定位时补位, 跑与主侦察不同的路标
    if not alive2 and len(tanks) >= 4 and not mem.enemy_base:
        rest = [t for t in tanks if t["id"] != mem.scout_id]
        if rest:
            mem.scout2_id = rest[0]["id"]
            dispatch(mem.scout2_id, pick_wp(exclude=tuple(shadow) if shadow else None),
                     "SCOUT2")
    if not acts:
        return None, None
    return acts, "; ".join(logs)
