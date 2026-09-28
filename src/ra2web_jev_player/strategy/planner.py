# -*- coding: utf-8 -*-
"""确定性决策层 —— Bible §10.1 清单 + 事件感知 + 五态机的确定性入口。

从 legacy_bot 原样迁移（第 18-20 局复盘定稿版），只做了两处架构性改动：
1. 纯函数化：函数吃 (state, home, mem) 吐 action 列表，由 game.py 经页内客户端执行，
   离线可测；
2. 职责去重：建筑落位/维修划归页内微操（150ms 级反应更快），本层不再做。

行为参数零改动 —— 每条阈值都有局次复盘背书（doctrine.T / CONF / THREAT_FORCE_DEFEND）。
"""
from __future__ import annotations

import math
import time

from .doctrine import (AIR_UNITS, CONF, HARVEST, MCV_CODES, SCOUT_DOGS,
                       THREAT_FORCE_DEFEND, T, get_side)
from .state import (all_combat, available, buildings, combat_tanks, nm,
                    pick_target, queues_by_type, ucost)


class BattleMemory:
    """单局记忆（进程内，对局结束即弃）。字段与 legacy_bot MEM 一致。"""

    def __init__(self):
        self.enemy_base = None          # 最近一次看见的敌建筑坐标
        self.last_scout = 0.0           # 上次派坦克探图的真实时刻
        self.scout_id = None            # 专职侦察单位（movement 集结时豁免它）
        self.scout_visit: dict = {}     # 路标 -> 游戏秒（持续探索用）
        self.last_alarm_pos = None      # 最近一次 ALARM 位置（前哨朝向参考）
        self.raid_wp = [(), 0.0]        # (旧字段, 由 squad_wp 取代)
        self.guard_t = 0.0              # 矿车护航令时刻（30s 节流）
        self.home_guard_t = 0.0         # (旧字段, 由 squad_wp 取代)
        self.squad_wp: dict = {}        # 各编组 {role: [目标, 重发截止]}
        self.last_squads: dict = {}     # 上 tick 编组表（危机救援抽 reserve 用）
        self.current_stance = "develop" # 当前态势（build_gate 读取: RECOVER 放开闸门）
        self.dog_sent = False           # 军犬探路是否已派出
        self.dogs_queued = False
        self.retreated: dict = {}       # unitId -> 游戏秒(每 300s 只撤一次)
        self.events: list = []          # 事件流(新→旧渲染时反转)
        self.bld_hp: dict = {}          # buildingId -> (name, hp, mhp, tl)
        self.unit_ids: dict = {}        # unitId -> 中文名(损失检测)
        self.seen_hostiles: set = set()
        self.alarm_times: list = []     # 受袭时刻(真实时间), 120s 窗口
        self.last_defend_order = 0.0    # ALARM 反击令时刻(8s 保护期)
        self.last_t = None              # 停摆检测
        self.stall_logged = False
        self.stall_t = 0.0
        self.wp = [0, 0.0, (), 0.0]     # 路标: 索引/切换时刻/当前目标/重发截止

    def log_lines(self) -> list:
        return list(self.events)


# ================= 秒级战场感知 (第 13 局引入, 1 tick 内响应) =================

def sense_events(s: dict, home, mem: BattleMemory):
    """tick 间差分：建筑掉血/单位损失/敌逼近/新敌 → 事件流 + alarm。

    建筑掉血是最早的被袭信号（比敌人进入半径更早）。返回 alarm 或 None。
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
                ev.append("受击: %s(%s) -%d血 剩%d/%d"
                          % (u["n"], nm(u["n"]), lost, int(u["hp"]), int(u["mhp"])))
                alarm = {"pos": list(u["tl"]), "what": "%s被攻击" % nm(u["n"])}
    mem.bld_hp = cur_hp
    # b) 战斗单位损失
    alive = {u["id"] for u in s["mine"] if u["o"] in (3, 7)}
    for uid, uname in list(mem.unit_ids.items()):
        if uid not in alive:
            ev.append("损失: %s" % uname)
            del mem.unit_ids[uid]
            if alarm is None:
                alarm = {"pos": list(home) if home else [0, 0], "what": "单位损失"}
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
            ev.append("敌逼近基地(%d格): %s" % (int(d), comp))
            mem.alarm_times.append(time.time())
            mem.alarm_times = [x for x in mem.alarm_times if time.time() - x < 120][-20:]
            if alarm is None:
                alarm = {"pos": list(near[0]["tl"]), "what": "敌军逼近"}
    new_ids = {h["id"] for h in s["hostile"]}
    fresh = new_ids - mem.seen_hostiles
    if fresh:
        fn = [h for h in s["hostile"] if h["id"] in fresh]
        ev.append("发现敌军: " + ",".join("%s(%s)" % (nm(h["n"]), h["tl"]) for h in fn[:4]))
        mem.seen_hostiles = new_ids
    else:
        mem.seen_hostiles |= new_ids
    mem.events = ev[-6:]
    if alarm:
        mem.last_alarm_pos = list(alarm["pos"])   # 前哨/伏击位朝向参考
    return alarm


def crisis_response(s: dict, home, alarm: dict, mem: BattleMemory,
                    stance: str = "defend") -> tuple:
    """ALARM 危机速应（第 19/20 局复盘 + 第 27/30 局用户观察）。

    - 进攻/突击态势下**不全员回撤**（第 29 局教训：ALARM 一响全军拉回=攻势中断、
      敌方回血）：家门口交火交给塔阵+微操；只有敌军压崩防线（深入 10 格且敌≥6）
      才召回主力。
    - 防守态势：兵力 ≥1.2x 才反击，否则 TURTLE 守塔阵（37→0 匀速送人头的教训）。
    - 远端告警（矿车在敌区被袭）：派最近 2-3 辆支援，不动用主力。
    返回 (actions, logline)。
    """
    defenders = [u for u in s["mine"]
                 if u["o"] in (3, 7) and u["n"] not in HARVEST
                 and u["n"] not in MCV_CODES          # 基地车不参与反击(送人头)
                 and u["n"] not in ("SENGINEER",)
                 and u["id"] != mem.scout_id          # 侦察车不被危机召回（第34局:
                                                      #   83次ALARM把侦察拽回家=敌基地定位失败）
                 and u["hp"] >= T["retreat_hp"] * (u["mhp"] or 1)]
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


# ================= §10.1 确定性清单 =================

def checklist(s: dict, home, stance: str, mem: BattleMemory) -> tuple:
    """按 §10.1 优先级产出确定性动作。返回 (stance, actions, logs)。"""
    side = get_side(s)
    cred = s["me"]["credits"]
    pw = s["me"]["power"].get("total", 0)
    drain = s["me"]["power"].get("drain", 0)
    mine, hos = s["mine"], s["hostile"]
    qs = queues_by_type(s["queues"])
    bl = buildings(mine)
    acts, logs = [], []

    # 1) 基地受袭检测（确定性, 不等 jev）：敌人进入防御半径 → 强制 DEFEND。
    #    [第30局] attack/rush 态势下不打回 defend——攻势保持（crisis_response 的
    #    压崩召回兜底），否则敌人赖在 18 格内 = 永远进不了进攻（防守陷阱复辟）。
    if home:
        near = [h for h in hos
                if math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= T["defend_radius"]]
        if near and stance not in ("defend", "attack", "rush"):
            logs.append("t=%d DEFEND trigger: %d hostiles within r=%d"
                        % (s["t"], len(near), T["defend_radius"]))
            stance = "defend"

    # 3) 部署基地车：仅 MCV 触发（页内 O.deploy 自带 type===7&&canDeploy 判别 +
    #    45s 节流）。注意不能对"任意 canDeploy 载具"部署——防空履带车等也有
    #    canDeploy 属性，反复 deploy 会白白 unload/load（第 1 局重构实测教训）。
    if any(u["o"] == 7 and u.get("dep") and u["n"] in MCV_CODES for u in mine):
        acts.append({"act": "deploy"})
        logs.append("t=%d DEPLOY mcv" % s["t"])

    # 4) 电力保底：余量 <30 → 电厂（排在大多数建造之前）
    if pw - drain < T["power_reserve"] and cred >= 600 \
            and side["powr"] in available(s["av"], 0) \
            and qs.get(0, {}).get("s") == 0:
        acts.append({"act": "produce", "name": side["powr"], "qty": 1, "q": 0})
        logs.append("t=%d POWER plant (reserve %d)" % (s["t"], pw - drain))
        cred -= 600

    # 5) 矿车补员: 每精炼厂 2 车, 第 3 辆起资金门槛 2800 (第 17 局复盘);
    #    目标上限 [第27局] 3→4 (三精炼厂经济扩张配套)
    n_harv = len([u for u in mine if u["n"] in HARVEST])
    n_ref = bl.get(side["ref"], 0)
    q3s = qs.get(3, {}).get("s", 0)
    harv_target = min(4, T["harv_per_ref"] * n_ref)
    harv_cost_gate = 1400 if n_harv < T["harv_min"] else 2800
    if q3s == 0 and n_ref >= 1 and n_harv < harv_target \
            and side["harv"] in available(s["av"], 3) and cred >= harv_cost_gate:
        acts.append({"act": "produce", "name": side["harv"], "qty": 1, "q": 3})
        logs.append("t=%d ECON harv#%d" % (s["t"], n_harv + 1))
        cred -= 1400

    # 8) 不攒钱: 产能线 (坦克预算保护, 第 20 局复盘: 防御支出让位坦克)
    if q3s == 0 and bl.get(side["weap"], 0) >= 1:
        tanks_av = [x for x in available(s["av"], 3)
                    if x not in HARVEST and x not in MCV_CODES]
        if tanks_av and cred >= T["tank_cash1"]:
            prefer = [x for x in side["tank_pref"] if x in tanks_av]
            pick = prefer[0] if prefer else tanks_av[0]
            qty = 2 if cred >= T["tank_cash2"] else 1
            if cred >= 2600:
                qty = min(4, int(cred // 900))
            acts.append({"act": "produce", "name": pick, "qty": qty, "q": 3})
            logs.append("t=%d TANK %s x%d" % (s["t"], pick, qty))
            cred -= ucost(pick) * qty

    # 6) 防空保险: 有战车工厂即保证 ≥1 防空建筑; 有空军威胁且资金富余再 +1
    #    (第 6 局: 美军火箭飞行兵掏家; 防空炮落地即造, 不等遇袭)
    air = any(h["n"] in AIR_UNITS for h in hos)
    if side["weap"] in bl and bl.get(side["aa_b"], 0) < 1 \
            and qs.get(1, {}).get("s", 0) == 0 \
            and side["aa_b"] in available(s["av"], 1) and cred >= 1000:
        acts.append({"act": "produce", "name": side["aa_b"], "qty": 1, "q": 1})
        logs.append("t=%d INSURE AA building" % s["t"])
        cred -= 1000
    elif air and bl.get(side["aa_b"], 0) < 2 \
            and qs.get(1, {}).get("s", 0) == 0 \
            and side["aa_b"] in available(s["av"], 1) and cred >= 1400:
        acts.append({"act": "produce", "name": side["aa_b"], "qty": 1, "q": 1})
        logs.append("t=%d AIR-DEFENSE 2nd AA" % s["t"])
        cred -= 1000

    # 6.5) 地面防御线: [第31局 Route A] 速攻期只留 1 座哨戒炮; [第36局 A] 之后 2 座
    #     （省现金转线圈——哨炮反步兵不反坦克, 坦克损耗大）
    gdef_cap = 1 if s["t"] < T["rush_t1"] else 2
    if side["bar"] in bl and bl.get(side["gdef"], 0) < gdef_cap \
            and qs.get(1, {}).get("s", 0) == 0 \
            and side["gdef"] in available(s["av"], 1) and cred >= 1500:
        acts.append({"act": "produce", "name": side["gdef"], "qty": 1, "q": 1})
        logs.append("t=%d DEFLINE %s (have %d)"
                    % (s["t"], side["gdef"], bl.get(side["gdef"], 0)))
        cred -= 500

    # 6.6) 磁暴线圈守家 [第36局 A]: 反坦克 200 伤替坦克挡刀——减少防守损耗,
    #     让 6 辆重拳攒得出来。前置雷达由"可造列表含 TESLA"隐式判定;
    #     现金软闸门（防守投资优先于坦克线, 但仍需可解）。
    tesla_cap = 1 if s["t"] < T["rush_t1"] else 2
    if side["weap"] in bl and bl.get("TESLA", 0) < tesla_cap \
            and qs.get(1, {}).get("s", 0) == 0 \
            and "TESLA" in available(s["av"], 1) \
            and cred >= ucost("TESLA") + 300:
        acts.append({"act": "produce", "name": "TESLA", "qty": 1, "q": 1})
        logs.append("t=%d TESLA coil (have %d)" % (s["t"], bl.get("TESLA", 0)))
        cred -= ucost("TESLA")

    # 7) 空军来袭 → 移动防空车 (苏军 HTK; 盟军靠防空建筑)
    q3 = qs.get(3, {})
    if air and side["aa_v"] and bl.get(side["weap"], 0) >= 1 and q3.get("s", 0) == 0 \
            and side["aa_v"] in available(s["av"], 3) and cred >= 500:
        acts.append({"act": "produce", "name": side["aa_v"], "qty": 2, "q": 3})
        logs.append("t=%d AA %s x2 (enemy air)" % (s["t"], side["aa_v"]))
        cred -= ucost(side["aa_v"]) * 2

    # 11.5) 矿车护航（第 27 局用户观察④）: 矿车远征(>25格)且兵力允许 → 最近的
    #       战斗坦克贴身护航（30s 节流；护卫已在矿车 6 格内则不重复派）。
    if home and len(combat_tanks(mine)) >= 4 and time.time() - mem.guard_t > 30:
        far_harv = [u for u in mine if u["n"] in HARVEST
                    and math.hypot(u["tl"][0] - home[0], u["tl"][1] - home[1]) > 25]
        if far_harv:
            h = far_harv[0]
            escorts = [u for u in combat_tanks(mine) if u["id"] != mem.scout_id]
            if escorts:
                guard = min(escorts, key=lambda u: math.hypot(
                    u["tl"][0] - h["tl"][0], u["tl"][1] - h["tl"][1]))
                if math.hypot(guard["tl"][0] - h["tl"][0], guard["tl"][1] - h["tl"][1]) > 6:
                    acts.append({"act": "attack_move", "ids": [guard["id"]],
                                 "x": h["tl"][0], "y": h["tl"][1]})
                    mem.guard_t = time.time()
                    logs.append("t=%d ESCORT 坦克#%s -> 护航矿车@%s"
                                % (s["t"], guard["id"], h["tl"]))

    # 11) 残血撤退: hp<40% → 拉回基地 (每 300s 每单位只撤一次, Move=0 逃跑不恋战)
    if home:
        rets = [u for u in mine if u["o"] in (3, 7) and u["n"] not in HARVEST
                and u["hp"] < T["retreat_hp"] * (u["mhp"] or 1)
                and mem.retreated.get(u["id"], 0) < s["t"] - 300]
        for u in rets[:4]:
            acts.append({"act": "move", "ids": [u["id"]],
                         "x": home[0], "y": home[1] + 3})
            mem.retreated[u["id"]] = s["t"]
            logs.append("t=%d RETREAT %s(%d%%)"
                        % (s["t"], u["n"], int(100 * u["hp"] / (u["mhp"] or 1))))
    return stance, acts, logs


# ================= 开局建造序列 (Bible §5.1/§5.2, 阵营感知) =================

def build_gate(s: dict, cost: int, mem: BattleMemory | None = None) -> bool:
    """建筑购买闸门（第 28 局复盘 + 第 31 局 Route A）。

    战车工厂落地后，现金必须 ≥ 造价+tank_cash1 才许买建筑——否则建筑一笔接一笔
    排队（精炼厂 1500/座、维修），坦克资金线永远够不着。
    例外：① 工厂落地前不设限（基建就是优先级）；② RECOVER 态势放开
    （rush 失败后要补经济出二波，Route A 的二波机制）。
    """
    bl = buildings(s["mine"])
    if bl.get(get_side(s)["weap"], 0) == 0:
        return True
    if mem is not None and mem.current_stance == "recover":
        return True
    return s["me"]["credits"] >= cost + T["tank_cash1"]


def opening_build(s: dict, mem: BattleMemory):
    """开局确定性序列：电厂→精炼厂→兵营→战车工厂；工厂后立即补二矿（第 20 局复盘）；
    t>rush_t1 且资金 >4500 补第二工厂。[第31局 Route A] 速攻期(t<rush_t1)精炼厂
    只建 1 座、不建第二工厂——全部现金转坦克；RECOVER 后闸门放开补经济出二波。
    返回 action 或 None。"""
    side = get_side(s)
    qs = queues_by_type(s["queues"])
    av0 = available(s["av"], 0)
    bl0 = buildings(s["mine"])
    ref_cap_now = 1 if s["t"] < T["rush_t1"] else T["ref_cap"]
    opening_next = None
    for want in side["opening"]:
        if bl0.get(want, 0) == 0:
            opening_next = want
            break
    if opening_next is None and bl0.get(side["weap"], 0) >= 1 \
            and bl0.get(side["ref"], 0) < ref_cap_now and side["ref"] in av0 \
            and build_gate(s, ucost(side["ref"]), mem):
        opening_next = side["ref"]
    if opening_next is None and s["t"] > T["rush_t1"]:
        if bl0.get(side["weap"], 0) < 2 and s["me"]["credits"] > T["factory2_cash"] \
                and side["weap"] in av0:
            opening_next = side["weap"]
        elif bl0.get(side["ref"], 0) < T["ref_cap"] and side["ref"] in av0 \
                and build_gate(s, ucost(side["ref"]), mem):
            opening_next = side["ref"]
    if opening_next and qs.get(0, {}).get("s", 0) == 0 and opening_next in av0:
        return {"act": "produce", "name": opening_next, "qty": 1, "q": 0,
                "tag": "OPENING BUILD %s" % opening_next}
    return None


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
    """军犬侦察（兵营好后 3 条）+ 专职侦察车多路标持续探图。

    第 26 局迭代（用户观察: 地图探索差、从不主动探索）：
    - 专职侦察: 选定一辆坦克后记 scout_id，movement 的集结/进攻令豁免它，
      修掉"侦察车被防守集结反复拉回家"的冲突（第 25 局复盘）；
    - 多路标轮转: 镜像角→地图中心→四角，优先最久未访，不再只看一个镜像点；
    - 间隔 150s（原 180s）；敌基地已定位后继续探索（确认+找残余分矿）。
    """
    side = get_side(s)
    qs = queues_by_type(s["queues"])
    av2 = available(s["av"], 2)
    if side["bar"] in [u["n"] for u in s["mine"] if u["o"] == 2] \
            and not mem.dogs_queued and "ADOG" in av2 and qs.get(2, {}).get("s", 0) == 0:
        mem.dogs_queued = True
        return ({"act": "produce", "name": "ADOG", "qty": 3},
                "t=%d SCOUT dogs x3" % s["t"])
    # [第31局 Route A] 军犬出厂即送镜像角——速攻必须尽早知道敌基地方位
    if not mem.dog_sent and home:
        dogs = [u for u in s["mine"] if u["n"] in SCOUT_DOGS]
        if dogs:
            mx, my = s["map"]["width"], s["map"]["height"]
            mirror = [max(mx - home[0], 8), max(my - home[1], 8)]
            mem.dog_sent = True
            return ({"act": "attack_move", "ids": [dogs[0]["id"]],
                     "x": mirror[0], "y": mirror[1]},
                    "t=%d SCOUT dog->mirror %s" % (s["t"], mirror))
    if time.time() - mem.last_scout <= 150:
        return None, None
    tanks = combat_tanks(s["mine"])
    if not tanks or not home:
        return None, None
    # 侦察车存活即续用；阵亡/失踪则重新指派
    if mem.scout_id and any(u["id"] == mem.scout_id for u in tanks):
        sid = mem.scout_id
    else:
        sid = tanks[0]["id"]
        mem.scout_id = sid
    mx, my = s["map"]["width"], s["map"]["height"]
    waypoints = [
        [max(mx - home[0], 8), max(my - home[1], 8)],   # 镜像角(敌最可能方位)
        [mx // 2, my // 2],                             # 地图中心
        [12, my // 2], [12, 12], [mx - 12, 12],
        [mx - 12, my - 12], [12, my - 12],              # 四角扫荡
    ]
    if mem.enemy_base:
        return None, None        # 已定位: 别再送单车去敌方基地喂经验
    target = min(waypoints, key=lambda w: mem.scout_visit.get(tuple(w), -1))
    mem.scout_visit[tuple(target)] = s["t"]
    mem.last_scout = time.time()
    return ({"act": "attack_move", "ids": [sid], "x": target[0], "y": target[1]},
            "t=%d SCOUT #%s->%s (visit %d)" % (s["t"], sid, target, len(mem.scout_visit)))


# ================= 五态机确定性入口 =================

def stance_overrides(s: dict, stance: str, mem: BattleMemory) -> tuple:
    """RECOVER/RUSH/ATTACK 的确定性入口（jev 投票之外的硬约束）。返回 (stance, logs)。

    [第 28 局] ATTACK 入口加 defend——第 27 局实测：ALARM 把态势锁死在 defend 后，
    27 辆坦克也永远出不去（防守陷阱）；进攻时 ALARM 的危机保护仍然生效（crisis_response）。
    """
    logs = []
    n_tank = len(combat_tanks(s["mine"]))
    if n_tank < 3 and s["t"] > 400 and stance in ("attack", "rush"):
        stance = "recover"
        logs.append("t=%d RECOVER (only %d tanks)" % (s["t"], n_tank))
    if T["rush_t0"] <= s["t"] <= T["rush_t1"] and n_tank >= T["rush_tanks"] \
            and stance in ("develop", "recover", "defend"):
        stance = "rush"
        logs.append("t=%d RUSH window (%d tanks)" % (s["t"], n_tank))
    if n_tank >= T["attack_tanks"] \
            and stance in ("develop", "rush", "recover", "defend"):
        stance = "attack"
        logs.append("t=%d ATTACK (tanks=%d)" % (s["t"], n_tank))
    return stance, logs


# ================= 进攻执行 (第 18-20 局定稿) =================

def forward_post(s: dict, home, mem: BattleMemory) -> list:
    """前哨位置：从基地朝敌情方向前出 ~12 格（路口前置优于贴家环形, Bible 防御三件套）。

    朝向优先级: 已知敌基地 > 最近 ALARM 位置 > 地图中心（镜像近似）。
    """
    mx, my = s["map"]["width"], s["map"]["height"]
    if mem.enemy_base:
        dx, dy = mem.enemy_base[0] - home[0], mem.enemy_base[1] - home[1]
    elif mem.last_alarm_pos:
        dx, dy = mem.last_alarm_pos[0] - home[0], mem.last_alarm_pos[1] - home[1]
    else:
        dx, dy = mx / 2.0 - home[0], my / 2.0 - home[1]
    norm = max(abs(dx), abs(dy), 1.0)
    r = min(12, max(T["defend_radius"] - 6, 8))
    x = int(min(max(home[0] + dx / norm * r, 4), mx - 4))
    y = int(min(max(home[1] + dy / norm * r, 4), my - 4))
    return [x, y]


def _hold_posts(s: dict, home, mem: BattleMemory) -> list:
    """两个伏击位：以基地为圆心、敌方向 ±55°、半径 14 格（卡路口/斜向布防）。"""
    mx, my = s["map"]["width"], s["map"]["height"]
    if mem.enemy_base:
        ang = math.atan2(mem.enemy_base[1] - home[1], mem.enemy_base[0] - home[0])
    elif mem.last_alarm_pos:
        ang = math.atan2(mem.last_alarm_pos[1] - home[1], mem.last_alarm_pos[0] - home[0])
    else:
        ang = math.atan2(my / 2.0 - home[1], mx / 2.0 - home[0])
    posts = []
    for da in (-0.96, 0.96):
        x = int(min(max(home[0] + 14 * math.cos(ang + da), 4), mx - 4))
        y = int(min(max(home[1] + 14 * math.sin(ang + da), 4), my - 4))
        posts.append((x, y))
    return posts


def assign_squads(s: dict, home, mem: BattleMemory) -> dict:
    """多线分组（第 31 局, 用户观察: 分职责多线执行, 步兵不再游荡）。

    RAID(坦克奇袭断经济) / ASSAULT(主攻) / HOLD(伏击把手, 步兵为主) /
    GUARD(守家) / RESERVE(机动支援池, 危机救援从这抽人)。
    分配按池子顺序切分, 单位死亡自然缩编, 新兵落到 assault。
    """
    units = [u for u in all_combat(s["mine"], keep_wounded=True)
             if u["id"] != mem.scout_id]
    tanks = [u for u in units if u["o"] == 7]
    inf = [u for u in units if u["o"] != 7]
    sq = {"raid": [], "assault": [], "hold": [], "guard": [], "reserve": []}
    # RAID=骚扰组 [第31局A++]: 敌基地一发现, 前 2 辆坦克立即成军专咬矿车
    if mem.enemy_base and len(tanks) >= 2:
        sq["raid"] = [u["id"] for u in tanks[:2]]
        tanks = tanks[2:]
    # GUARD: 2 辆坦克守家（剩余 ≥3 辆才留, 骚扰优先）
    if len(tanks) >= 3:
        sq["guard"] = [u["id"] for u in tanks[:T["keep_home"]]]
        tanks = tanks[T["keep_home"]:]
    sq["assault"] = [u["id"] for u in tanks]
    # HOLD: 步兵≥8 时分一半去伏击位, 其余进主攻/预备
    n_hold = (len(inf) // 2) if len(inf) >= 8 else 0
    sq["hold"] = [u["id"] for u in inf[:n_hold]]
    rest = inf[n_hold:]
    n_res = min(4, max(0, len(rest) - 4))     # 保底 4 人给 assault
    sq["reserve"] = [u["id"] for u in rest[:n_res]]
    sq["assault"] += [u["id"] for u in rest[n_res:]]
    return sq


def movement(s: dict, home, stance: str, mem: BattleMemory) -> tuple:
    """多线编组指挥（第 31 局重构）。返回 (actions, log)。

    各组职责与节流:
      RAID    -> 敌基地/矿区 断经济           (30s)
      ASSAULT -> 敌基地(已知)或打分目标/前哨  (12s)
      HOLD    -> 敌方向两侧伏击位             (60s)
      GUARD   -> 家门口                        (30s)
      RESERVE -> 家侧翼待机(危机救援优先从这抽人) (60s)
    目标优先级沿用 §4.3 打分; 页内集火含弹头×护甲克制加权(第31局)。
    """
    sq = assign_squads(s, home, mem)
    mem.last_squads = dict(sq)
    acts, logs = [], []
    mx, my = s["map"]["width"], s["map"]["height"]

    def order(role, ids, x, y, throttle):
        ids = list(ids or [])
        if not ids:
            return
        wp = mem.squad_wp.setdefault(role, [None, 0.0])
        if wp[0] == (x, y) and wp[1] > time.time():
            return
        wp[0] = (x, y)
        wp[1] = time.time() + throttle
        acts.append({"act": "attack_move", "ids": ids, "x": x, "y": y})
        logs.append("%s x%d -> (%d,%d)" % (role, len(ids), x, y))

    # RAID=骚扰组 [第31局A++]: 优先咬可见的最近敌矿车(断经济), 无矿车视野再打基地
    if mem.enemy_base and sq["raid"]:
        harv = [h for h in s["hostile"] if h["n"] in HARVEST]
        if harv and home:
            h = min(harv, key=lambda h: math.hypot(h["tl"][0] - home[0],
                                                   h["tl"][1] - home[1]))
            order("raid", sq["raid"], h["tl"][0], h["tl"][1], 20)
        else:
            order("raid", sq["raid"], mem.enemy_base[0], mem.enemy_base[1], 30)
    # ASSAULT: 主攻方向
    if stance in ("attack", "rush") or mem.enemy_base:
        if mem.enemy_base:
            order("assault", sq["assault"], mem.enemy_base[0], mem.enemy_base[1], 12)
        else:
            tgt_u = pick_target(s, home)
            if tgt_u:
                tgt = list(tgt_u["tl"])
            elif home:
                # [第31局 Route A] 无情报也压向镜像角（用接触找基地, 不龟缩）
                tgt = [max(mx - home[0], 8), max(my - home[1], 8)]
            else:
                tgt = forward_post(s, home, mem)
            order("assault", sq["assault"], tgt[0], tgt[1], 12)
    else:
        if home:
            inside = [h for h in s["hostile"]
                      if math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= 10]
            if inside or len(sq["assault"]) < 4:
                order("assault", sq["assault"], home[0] + 3, home[1] + 3, 12)
            else:
                p = forward_post(s, home, mem)
                order("assault", sq["assault"], p[0], p[1], 12)
    if home:
        # HOLD: 两个伏击位分兵
        posts = _hold_posts(s, home, mem)
        half = (len(sq["hold"]) + 1) // 2
        order("hold_a", sq["hold"][:half], posts[0][0], posts[0][1], 60)
        order("hold_b", sq["hold"][half:], posts[1][0], posts[1][1], 60)
        order("guard", sq["guard"], home[0] + 3, home[1] + 3, 30)
        order("reserve", sq["reserve"], home[0], home[1] + 8, 60)
    return acts, "; ".join(logs) or "no-force"


# ================= Jev 答案应用（闸门在 doctrine.CONF） =================

def apply_jev(s: dict, ans: dict, stance: str, mem: BattleMemory,
              used: dict | None = None) -> tuple:
    """把 Jev 批量答案转成动作 + 态势采信。返回 (stance, actions, logs)。

    used: 本 tick 确定性层已占用的队列 {0/1/2/3: bool} —— 生产指令异步生效,
    快照里队列状态滞后一个 tick, 不查会双造(legacy 同款竞态)。
    """
    used = used or {}
    side = get_side(s)
    qs = queues_by_type(s["queues"])
    acts, logs = [], []
    # 建造（确定性清单没花的钱由 jev 决定花法；资金闸门: 坦克资金线优先, 第28局复盘;
    # [第32局] 同类建筑 ≥2 不再买——jev 曾连续买 30 座电厂 12 座兵营）
    b = (ans.get("build") or {}).get("choice")
    if b and b != "hold" and not used.get(0) \
            and qs.get(0, {}).get("s") == 0 and b in available(s["av"], 0):
        n_ref = len([u for u in s["mine"] if u["n"] == side["ref"]])
        n_bar = len([u for u in s["mine"] if u["n"] == side["bar"]])
        bl_now = buildings(s["mine"])
        if not (b == side["ref"] and n_ref >= T["ref_cap"]) \
                and not (b == side["bar"] and n_bar >= 2) \
                and not (b != side["ref"] and bl_now.get(b, 0) >= 2):
            if build_gate(s, ucost(b), mem):
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
        bl = buildings(s["mine"])
        n_e2 = len([u for u in s["mine"] if u["n"] == "E2"])
        factory_gate = bl.get(side["weap"], 0) == 0 \
            or s["me"]["credits"] >= T["tank_cash1"] or i in SCOUT_DOGS
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
        acts.append({"act": "produce", "name": v, "qty": 1, "q": 3})
        logs.append("t=%d jev VEH %s (conf %.2f)"
                    % (s["t"], v, (ans.get("veh") or {}).get("confidence", -1)))
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
