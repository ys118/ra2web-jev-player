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

from .doctrine import (AA_VEHICLES, AIR_UNITS, CONF, DEF_BUILDINGS, HARVEST,
                       MCV_CODES, SCOUT_DOGS, THREAT_FORCE_DEFEND, T,
                       V3_CODES, get_side)
from .state import (all_combat, available, buildings, combat_tanks, nm,
                    pick_target, queues_by_type, ucost, force_value)


class BattleMemory:
    """单局记忆（进程内，对局结束即弃）。字段与 legacy_bot MEM 一致。"""

    def __init__(self):
        self.enemy_base = None          # 最近一次看见的敌建筑坐标
        self.last_scout = 0.0           # 上次派坦克探图的真实时刻
        self.scout_id = None            # 专职侦察单位（movement 集结时豁免它）
        self.scout_visit: dict = {}     # 路标 -> 游戏秒（持续探索用）
        self.last_alarm_pos = None      # 最近一次 ALARM 位置（前哨朝向参考）
        self.last_alarm_t = 0           # [第49局] 最近 ALARM 游戏秒（侦察反推时效）
        self.alarm_scout_t = 0          # [第49局] 上次 ALARM 反推侦察游戏秒（60s 防刷）
        self.raid_wp = [(), 0.0]        # (旧字段, 由 squad_wp 取代)
        self.guard_t = 0.0              # 矿车护航令时刻（30s 节流）
        self.home_guard_t = 0.0         # (旧字段, 由 squad_wp 取代)
        self.squad_wp: dict = {}        # 各编组 {role: [目标, 重发截止]}
        self.last_squads: dict = {}     # 上 tick 编组表（危机救援抽 reserve 用）
        self.current_stance = "develop" # 当前态势（build_gate 读取: RECOVER 放开闸门）
        self.dog_task: dict = {}        # [第60局] dogId -> {wp, t}: 军犬任务表——
                                        # 原"60gs 一轮×最多 2 犬"致多产犬永远站基地
                                        # (用户反馈), 改为全员出动+任务制不打断在途
        self.last_dog_replenish = 0.0   # [第42局] 军犬补员时刻（60s 节流）
        self.first_hostile_pos = None   # [第37局] 首次看见敌军的位置（敌影推定用）
        self.scout2_id = None           # [第37局] 第二侦察车（双车并行）
        self.dogs_queued = False
        self.retreated: dict = {}       # unitId -> 游戏秒(每 300s 只撤一次)
        self.gdef_order = (-1, -999)    # [第78局] 哨炮在途判重 (下单时存量, 时刻)
        self.e2_burst = (-1, -999)      # [第78局] RUSH-DEFENSE E2 爆产在途判重
        self.e2_garrison = (-1, -999)   # [第84局] 开局驻军 E2 在途判重
        self.ghost_ids: set = set()     # [第82局] 幻影建筑拉黑(攻击150gs不倒=假目标)
        self.siege_target_hist: dict = {}  # [第82局] 围城目标首攻时刻 {id: t}
        self.gap_seen = False           # [第82局] 本局见过裂缝产生器(拉黑清空闸)
        self.tick_debt: int = 0         # [第90局 统一生产账本] 本 tick 已承诺
                                        # 队列债务(同 tick 三决策器共享)——88/89
                                        # 局死因: 各决策器独立读原始现金, 同 tick
                                        # HARV+HTNK x4+NAHAND 叠 5500 债 vs 现金
                                        # ~2600 → q3 僵尸订单饿死堵死, 坦克绝产
        self.focus_id = None            # [第92局 用户反馈②] 坦克点名集火目标 id
        self.focus_t = 0                # [第92局] 点名目标选定时刻(重选节流用)
        self.enval_freeze_since = None  # [第95局 击杀冻结检测] 冻结起始游戏秒
        self.last_en_val = None         # [第95局] 上个 tick 敌战力值
        self.rush_defense = False       # [第76局 用户反馈] 动态早rush防御模式:
                                        # 敌兵海压门且守军对不上 → 动员兵爆产
                                        # (不受坦克资金线约束); 威胁解除自动恢复
                                        # 原公式——第一个"按态势切换公式"的自适应机制
        self.siege_mode = False         # [第75局 用户拍板] 终局围城锁存: 敌基地
                                        # 已定位+敌经济死亡+战力≥1.5倍 → 全军总攻
                                        # (74 局实证: "绝不打塔"铁律把 31 辆坦克锁在
                                        # 机枪堡壳外 45 分钟零击杀的无限撤退循环)
        self.events: list = []          # 事件流(新→旧渲染时反转)
        self.bld_hp: dict = {}          # buildingId -> (name, hp, mhp, tl)
        self.unit_ids: dict = {}        # unitId -> 中文名(损失检测)
        self.seen_hostiles: set = set()
        self.alarm_times: list = []     # 受袭时刻(真实时间), 120s 窗口
        self.alarm_log: list = []       # [第63局] (游戏秒, 类型, 位置) 动态上下文
        self.loss_log: list = []        # [第63局] (游戏秒, 单位名) 我方损失
        self.kill_log: list = []        # [第63局] (游戏秒, 单位名) 击杀
        self.val_history: list = []     # [第63局] (游戏秒, 资金, 我值, 敌值) 趋势
        self.stance_hist: list = []     # [第63局] (游戏秒, 态势) 态势史
        self.stance_since = 0           # 当前态势起始游戏秒
        self.last_defend_order = 0.0    # ALARM 反击令时刻(8s 保护期)
        self.last_t = None              # 停摆检测
        self.stall_logged = False
        self.stall_t = 0.0
        self.wp = [0, 0.0, (), 0.0]     # 路标: 索引/切换时刻/当前目标/重发截止
        # [第66局 V3反制] V3 威胁记忆: 最后目击/位置 + 远程火力签名时刻
        self.v3_seen_t = -10 ** 9       # 最后看见 V3 的游戏秒(600gs 内视为活跃)
        self.v3_pos = None              # V3 最后目击位置
        self.long_fire_t = -10 ** 9     # 远程火力签名(建筑掉血+视野内无攻击者)
        # [第67局] 开局自愈回退网: 引擎拒收检测(40gs 无进展) + 黑名单 + 整体回退
        self.open_order = None          # 最近下的开局建筑单
        self.open_order_t = -1          # 下单游戏秒
        self.open_blacklist: set = set()  # 被引擎拒收的建筑(本局跳过)
        self.open_fallback = False      # True=回退旧合法序(NAPOWR 先行)
        self.open_events: list = []     # 自愈事件(由 game.py 排空进 audit)

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


# ================= §10.1 确定性清单 =================

def v3_threat_active(s: dict, mem: BattleMemory) -> bool:
    """[第66局 V3反制] V3 威胁是否活跃: 600gs 内目击过 V3, 或 120gs 内有
    远程火力签名(建筑掉血+视野内无攻击者)。任一命中即开生产闸门。"""
    return (s["t"] - mem.v3_seen_t <= T["v3_seen_window"]
            or s["t"] - mem.long_fire_t <= T["v3_fire_window"])


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

    def _order_once(key, cur_n, window):
        """[第78局 bug fix] 确定性生产在途判重: 队列快照滞后(引擎受理延迟)使
        同一订单在连续 tick 上重复下发——77 局实锤六连 DEFLINE(3000 金被订单
        黑洞抽干, 第 30 局已知竞态在 checklist 分支复发)。存量未变且未过窗口
        → 视为在途, 拒绝重下; 存量变化(落地/被拆)或超窗口(疑似拒收, 允许重试)。"""
        last_n, last_t = getattr(mem, key)
        if cur_n == last_n and s["t"] - last_t < window:
            return False
        setattr(mem, key, (cur_n, s["t"]))
        return True

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
    # [第76局 用户反馈①②] 动态早rush防御响应——首个"按战场态势切换公式"的
    # 自适应机制: 敌兵海压门(近敌≥4)且门口守军对不上(守<1.2x敌) → RUSH-DEFENSE
    # 模式(动员兵爆产不受坦克资金线约束; 75局实证: 20单位海压家时 13 E2 全灭、
    # 坦克线来不及, 固定公式被 roll 穿透); 威胁解除自动恢复原公式。
    threat_n = len(near) if home else 0
    def_n = 0
    if home:
        def_n = len([u for u in mine
                     if u["o"] in (3, 7) and u["n"] not in HARVEST
                     and math.hypot(u["tl"][0] - home[0], u["tl"][1] - home[1]) <= 30])
    if threat_n >= 4 and def_n < 1.2 * threat_n:
        if not mem.rush_defense:
            mem.rush_defense = True
            logs.append("t=%d RUSH-DEFENSE ON (敌%d压门 vs 守%d) 动员兵爆产"
                        % (s["t"], threat_n, def_n))
    elif threat_n == 0 and mem.rush_defense:
        mem.rush_defense = False
        logs.append("t=%d RUSH-DEFENSE OFF (威胁解除) 恢复原公式" % s["t"])

    # 3) 部署基地车：仅 MCV 触发（页内 O.deploy 自带 type===7&&canDeploy 判别 +
    #    45s 节流）。注意不能对"任意 canDeploy 载具"部署——防空履带车等也有
    #    canDeploy 属性，反复 deploy 会白白 unload/load（第 1 局重构实测教训）。
    if any(u["o"] == 7 and u.get("dep") and u["n"] in MCV_CODES for u in mine):
        acts.append({"act": "deploy"})
        logs.append("t=%d DEPLOY mcv" % s["t"])

    # 4) 电力保底：余量 <30 → 电厂（排在大多数建造之前）
    #    [第67局] 战厂未建成前不开闸: 精炼厂先行链(电厂排第4)下开局 0 电容是
    #    预期状态, 不能让本闸门在 t=1 抢先插电厂架空开局序列; 战厂立起后
    #    (或电厂本就是开局下一项时)恢复应急职能。
    fac_up = bl.get(side["weap"], 0) >= 1
    if pw - drain < T["power_reserve"] \
            and (fac_up or opening_next_code(s, mem) == side["powr"]) \
            and cred >= 600 \
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
    # [第85局 收入再扩容→第86局回滚] 8 车过度开采实证: 85 局 t≈2400 本地矿区
    # 枯竭(6 矿车在场但现金冻结=无矿可采), 中盘收入断绝致败; 78/82/84 三胜
    # 全为 6 车配置。矿车目标回滚 6(保留 ref_cap=4 的扩产弹性)。
    # [第94局 单变量] 公式 +1 容错: min(6, 2×n_ref+1)——88/92/93 三局第二
    # 精炼厂在敌第一波 rush 时段夭折, n_ref=1 时 2 车采集力撑不起爆产消耗
    # (93 局 t=442 起 cash=0 防线断粮)。一矿 3 车=+收入 20-30%+被杀 1 车
    # 不致收入崩盘(87-91 局矿车 2→7 的胜负分界全在这条曲线上)。
    harv_target = min(6, T["harv_per_ref"] * n_ref + 1)
    # [第45局复盘] 第3辆门槛 2800→1500: 见底率69% 的根源是"现金到不了 2800→矿车
    # 不补→收入上不去"死循环（矿车曲线全程仅 2 辆）; 第4辆仍 2800 防抢坦克线
    # [第63局用户反馈] 门槛 1400/1500/2800 → 800/1200/1500: 资金见底时
    # 矿车永远攒不够门槛=收入死螺旋(活局实挂 $0 长期, 第 4 车从未上路)
    # [第69局 boost_econ] 再降一档 800/1200/1500 → 600/900/1200: 第 67/68 局
    # 见底率 68%/41%, 矿车折损(68局损2车)在现金细流期补不上; 低于 tank_cash1
    # 的闲钱转收入, harv_reserve 同步降低=坦克线也更早解锁
    harv_cost_gate = 600 if n_harv < 2 else (900 if n_harv == 2 else 1200)
    # [第94局] 敌兵海压门期(rush_defense)矿车补员让位防线——1400 大件插在
    # 爆产段之前会把现金抽穿(21a/27e 回归暴露), 威胁解除后自动恢复补员。
    if q3s == 0 and n_ref >= 1 and n_harv < harv_target \
            and not mem.rush_defense \
            and side["harv"] in available(s["av"], 3) and cred >= harv_cost_gate:
        acts.append({"act": "produce", "name": side["harv"], "qty": 1, "q": 3})
        logs.append("t=%d ECON harv#%d" % (s["t"], n_harv + 1))
        cred -= 1400

    # 5.5) 磁暴线圈守家 [第36局 A]: 反坦克 200 伤替坦克挡刀——减少防守损耗,
    #     让 6 辆重拳攒得出来。前置雷达由"可造列表含 TESLA"隐式判定。
    #     [实测] 必须排在坦克线之前: 线圈 1800 软闸门永远抢不过 1000 的坦克线,
    #     第 36 局线圈难产即此因; 无线圈时第一优先建, 建成后坦克恢复优先。
    tesla_cap = 1 if s["t"] < T["rush_t1"] else 2
    if side["weap"] in bl and bl.get("TESLA", 0) < tesla_cap \
            and qs.get(1, {}).get("s", 0) == 0 \
            and "TESLA" in available(s["av"], 1) \
            and cred >= ucost("TESLA") + 300:
        acts.append({"act": "produce", "name": "TESLA", "qty": 1, "q": 1})
        logs.append("t=%d TESLA coil (have %d)" % (s["t"], bl.get("TESLA", 0)))
        cred -= ucost("TESLA")

    # 7.5) 骚扰组换装 [第41局, Jev 0.79]: 恐怖机器人(400金/秒矿车刺客)作骚扰主力——
    #     敌基地已知且存活机器人 <2 时补 2 只, 坦克伤亡换便宜的。
    n_dron = len([u for u in mine if u["n"] == "DRON"])
    if mem.enemy_base and n_dron < T["harass_dron"] \
            and qs.get(3, {}).get("s", 0) == 0 \
            and "DRON" in available(s["av"], 3) \
            and cred >= ucost("DRON") * 2:
        acts.append({"act": "produce", "name": "DRON", "qty": 2, "q": 3})
        logs.append("t=%d HARASS DRON x2 (have %d)" % (s["t"], n_dron))
        cred -= ucost("DRON") * 2

    # 7.6) V3 反制 [第66局]: V3 活跃且 HTK 存量 <cap → 优先产 HTK(插在坦克
    #     线之前——战厂被 V3 点名时坦克线本身就会断供, 保厂=保产能; 第 65 局
    #     坦克峰值 0 的真因即战厂两建两拆)。HTK 500cr, 拦火箭+贴脸拆车。
    #     [第70局反囤积] 存量帽 aa_htk_cap=4 与 AA 闸门共享, qty 按余量封顶。
    v3_on = v3_threat_active(s, mem)
    n_aav = len([u for u in mine if u["n"] == side["aa_v"]]) if side["aa_v"] else 0
    if v3_on and side["aa_v"] and bl.get(side["weap"], 0) >= 1 and q3s == 0 \
            and side["aa_v"] in available(s["av"], 3):
        aav_cost = ucost(side["aa_v"])
        if n_aav < T["aa_htk_cap"] and cred >= aav_cost:
            qty = max(1, min(2 if cred >= aav_cost * 2 else 1,
                             T["aa_htk_cap"] - n_aav))
            acts.append({"act": "produce", "name": side["aa_v"], "qty": qty, "q": 3})
            logs.append("t=%d V3-RESPONSE %s x%d (alive %d, seen t%d fire t%d)"
                        % (s["t"], side["aa_v"], qty, n_aav,
                           max(0, s["t"] - mem.v3_seen_t),
                           max(0, s["t"] - mem.long_fire_t)))
            cred -= aav_cost * qty

    # 8) 不攒钱: 产能线 (坦克预算保护, 第 20 局复盘: 防御支出让位坦克)
    # [第76局 RUSH-DEFENSE] 动员兵爆产: 模式激活时 q2 空闲即产, 只受造价
    # 约束(生存>一切), 排在坦克线之前吃现金——75 局 13 E2 对 20 海全灭实证。
    # [第77局 防御深化II] x2→x4/单: 连续两局苏联 20+ 兵海(75/76)实证 x2 爆产
    # 速度跟不上敌爆兵速度(E2 击杀 17 仍被磨穿)。
    # [第89局 坦克资金地板] 88 局死因链: 敌 17+ 大兵海下 x4 爆产(360/波, 先于
    #     坦克线执行且无地板)把现金钉死在坦克出手价(800)之下 → 全场坦克峰值 0
    #     → 守住 900s 仍无进攻能力耗死。地板=HTNK 造价(900): cred≥900 维持 x4
    #     大爆(开局现金充裕期行为不变); 跌破降 x1 续兵(防线不断兵, 30s 一兵),
    #     现金蓄回 900 坦克线即恢复出手——坦克+步兵双线并行。
    e2_burst_floor = ucost("HTNK")
    if mem.rush_defense \
            and qs.get(2, {}).get("s", 0) == 0 \
            and "E2" in available(s["av"], 2) and cred >= ucost("E2") \
            and len([u for u in mine if u["n"] == "E2"]) < 30 \
            and _order_once("e2_burst",
                            len([u for u in mine if u["n"] == "E2"]), 30):
        e2_qty = 4 if cred >= e2_burst_floor else 1
        acts.append({"act": "produce", "name": "E2", "qty": e2_qty, "q": 2})
        logs.append("t=%d RUSH-DEFENSE E2 x%d (敌%d压门 守%d%s)"
                    % (s["t"], e2_qty, threat_n, def_n,
                       "" if e2_qty == 4 else ", 资金地板续兵"))

    # 7.9) [第84局 防守起手] 开局步兵前置: 兵营落地且坦克场真空(无机动坦克
    #     ——涵盖首坦成熟前 t<273 硬窗口与坦克全灭后的自愈)时, 常备 ≥[第87局
    #     4→8] 动员兵守塔线。83 局实证: 大 roll 兵海在首坦成熟前磨穿防线,
    #     反应式 RUSH-DEFENSE 触发时已 late, 常驻驻军是硬窗口唯一保险;
    #     [第86局] 86 局 20+ 驻军仍被 20 单位海磨穿 → 地板 4→8 加厚。
    e2_alive = len([u for u in mine if u["n"] == "E2"])
    tanks_out = any(u["o"] == 7 and u["n"] not in HARVEST
                    and u["n"] not in MCV_CODES for u in mine)
    if bl.get(side["bar"], 0) >= 1 and not tanks_out \
            and not mem.rush_defense \
            and qs.get(2, {}).get("s", 0) == 0 \
            and "E2" in available(s["av"], 2) and cred >= ucost("E2") \
            and e2_alive < 8 and _order_once("e2_garrison", e2_alive, 30):
        acts.append({"act": "produce", "name": "E2", "qty": 2, "q": 2})
        logs.append("t=%d GARRISON E2 x2 (坦克真空期常驻驻军, have %d)"
                    % (s["t"], e2_alive))

    # 8) 不攒钱: 产能线 (坦克预算保护, 第 20 局复盘: 防御支出让位坦克)
    # [第46局复盘] 矿车补员期给坦克线让路: 矿车数低于下限时坦克线需同时覆盖
    # 矿车造价才出手——否则坦克在 1000 金抢走现金, 矿车(1400)永远补不上,
    # 第 46 局矿车掉到 1 辆后全程没补(收入腰斩 → 见底死循环)
    harv_reserve = (harv_cost_gate if n_harv < T["harv_min"] else 0)
    if q3s == 0 and bl.get(side["weap"], 0) >= 1:
        tanks_av = [x for x in available(s["av"], 3)
                    if x not in HARVEST and x not in MCV_CODES]
        if tanks_av and cred >= T["tank_cash1"] + harv_reserve:
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

    # 6.5) 地面防御线: [第36局 A] 之后 2 座; [第42局①] 速攻期也保 2 座——
    #     1 座哨炮撑不住重开局 rush（第 42 局 25 分钟速败的直接原因）,
    #     多花 500 金换开局生存, rush 推迟 ~30s 可接受
    #     [第87局 防御纵深] 2→3 座: 75/76/83/86 四局 rush 死法实证双塔纵深
    #     不足, 第三座补死角(rush_defense 时现金闸 500 已有)。
    gdef_cap = 3
    # [第77局 防御深化II] RUSH-DEFENSE 激活时第二哨炮插单: 现金闸 1500→500
    # (75/76 局双速败实证: 兵海压门时第二塔被 1500 闸卡死, 防线无纵深);
    # 电力余量闸不放松(缺电=塔全瞎, 第 64 局教训)。
    gdef_cash = 500 if mem.rush_defense else 1500
    if side["bar"] in bl and bl.get(side["gdef"], 0) < gdef_cap \
            and qs.get(1, {}).get("s", 0) == 0 \
            and side["gdef"] in available(s["av"], 1) and cred >= gdef_cash \
            and (pw - drain) >= 40 \
            and _order_once("gdef_order", bl.get(side["gdef"], 0), 60):
        # [第64局] 余量<40 不上塔: NALASR 吃电, 缺电=塔全瞎(rush 到来瞬间
        # power_low=True 的活局实证), 电厂优先, 塔晚 ~25s 但上线即有效
        acts.append({"act": "produce", "name": side["gdef"], "qty": 1, "q": 1})
        logs.append("t=%d DEFLINE %s (have %d)"
                    % (s["t"], side["gdef"], bl.get(side["gdef"], 0)))
        cred -= 500

    # 7) 空军来袭 → 移动防空车 (苏军 HTK; 盟军靠防空建筑)
    #    [第70局反囤积] 存量帽 aa_htk_cap=4: 第 69 局 JUMPJET 海期间无上限
    #    刷出 18 辆 HTK 囤积基地(用户实证), 4 辆+塔线足够防空
    q3 = qs.get(3, {})
    if air and side["aa_v"] and bl.get(side["weap"], 0) >= 1 and q3.get("s", 0) == 0 \
            and side["aa_v"] in available(s["av"], 3) and cred >= 500 \
            and n_aav < T["aa_htk_cap"]:
        qty = max(1, min(2, T["aa_htk_cap"] - n_aav))
        acts.append({"act": "produce", "name": side["aa_v"], "qty": qty, "q": 3})
        logs.append("t=%d AA %s x%d (enemy air, alive %d)" % (s["t"], side["aa_v"], qty, n_aav))
        cred -= ucost(side["aa_v"]) * qty

    # 11.5) 矿车护航（第 27 局用户观察④）: 矿车远征(>25格)且兵力允许 → 最近的
    #       战斗坦克贴身护航（30s 节流；护卫已在矿车 6 格内则不重复派）。
    if home and len(combat_tanks(mine)) >= 4 and time.time() - mem.guard_t > 30:
        far_harv = [u for u in mine if u["n"] in HARVEST
                    and math.hypot(u["tl"][0] - home[0], u["tl"][1] - home[1]) > 25]
        if far_harv:
            h = far_harv[0]
            # [第66局] HTK 不出远门护航: V3 活跃期它是基地防空屏, 远征=送头
            escorts = [u for u in combat_tanks(mine)
                       if u["id"] != mem.scout_id and u["n"] not in AA_VEHICLES]
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

# [第67局] 旧合法序(自愈回退目标): NAPOWR 先行, 第 18-59 局实证可行
_OPENING_LEGACY = ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"]


def build_gate(s: dict, cost: int, mem: BattleMemory | None = None,
               code: str | None = None) -> bool:
    """建筑购买闸门（第 28 局复盘 + 第 31 局 Route A）。

    战车工厂落地后，现金必须 ≥ 造价+tank_cash1 才许买建筑——否则建筑一笔接一笔
    排队（精炼厂 1500/座、维修），坦克资金线永远够不着。
    例外：① 工厂落地前不设限（基建就是优先级）；② RECOVER 态势放开
    （rush 失败后要补经济出二波，Route A 的二波机制）；
    ③ [第71局] 精炼厂缺额豁免——存量<ref_cap 时不受坦克资金线约束。
      第 70 局(clef 首局)实证: 见底率 67% 下现金永远凑不齐 造价+tank_cash1,
      确定性两线与 Jev 线三路同闸 → 三矿厂死锁、收入端饿死(坦克峰值 14 vs
      69 局 26)。本条把第 69 局"收入>吞吐"原则补全到闸门本身;
      ref_cap=3 封顶控制暴露面, 非精炼厂建筑闸门行为不变。
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
    """开工序列第一个未建成项（建造序列真相源）。[第58局] 工厂前置位保护用;
    [第67局] 感知自愈回退: open_fallback 时按旧合法序, 黑名单项跳过。"""
    side = get_side(s)
    bl0 = buildings(s["mine"])
    opening = _OPENING_LEGACY if (mem and mem.open_fallback) else side["opening"]
    blkl = mem.open_blacklist if mem else set()
    for want in opening:
        if bl0.get(want, 0) == 0 and want not in blkl:
            return want
    return None


def opening_build(s: dict, mem: BattleMemory):
    """开局确定性序列：[第67局] 精炼厂→兵营→战车工厂→电厂(精炼厂先行链, 老
    33-37 局快开局同构, 首坦克 430→~350); 引擎拒收自愈网: 下单后 40gs q0 仍
    idle 且建筑未落地 = 拒收 → 拉黑该建筑; NAREFN 被拒 = 无电厂精炼厂先行不可
    行 → 整体回退旧合法序(NAPOWR 先行, 第 18-59 局实证)。电厂后置的电力缺口
    由电厂应急闸门(战厂条件)与 DEFLINE 余量闸兜底。工厂后立即补二矿（第 20 局
    复盘）；t>rush_t1 且资金 >4500 补第二工厂。[第31局 Route A] 速攻期(t<rush_t1)
    精炼厂只建 1 座、不建第二工厂——全部现金转坦克；RECOVER 后闸门放开补经济
    出二波。返回 action 或 None。"""
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


def kill_freeze(mem: BattleMemory, s: dict, stance: str) -> int:
    """[第95局 击杀冻结检测] 94 局假僵局定谳: t=2127 起敌战力值恒 12300/
    击杀冻结 6600s——敌兵海被全歼后残部卡在打不到的位置(地形卡位), 我方
    6.4 倍战力物理上无法结束游戏, 白耗 100 分钟。返回冻结持续游戏秒
    (0=未冻结), 调用方按阈值(3000gs)终止僵尸局。

    冻结判定: attack/rush 态势下 ①敌战力值一个 tick 都不动 ②我方战力
    ≥2.5 倍碾压(排除均势拉锯的数值巧合)。只在进攻态判——发展/防守期
    敌值不动是常态; 敌真在建军战力值会变化即自动复位。"""
    try:
        my_v, en_v = force_value(s)
    except Exception:
        mem.enval_freeze_since = None
        return 0
    frozen = (stance in ("attack", "rush") and en_v > 0
              and my_v >= 2.5 * max(en_v, 1)
              and mem.last_en_val == en_v)
    mem.last_en_val = en_v
    if not frozen:
        mem.enval_freeze_since = None
        return 0
    if mem.enval_freeze_since is None:
        mem.enval_freeze_since = s["t"]
    return s["t"] - mem.enval_freeze_since


def contact_edge(s: dict, home, pos):
    """从家沿接触点方向的单位向量延伸到地图边缘（~92% 处）的探查点。

    [第37局 敌影推定 / 第49局 ALARM 反推共用] dist<3 视为家门口无方向信息。
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
    """敌影推定 [第37局, Jev 0.88]: 敌人最早出现的位置反推基地方向。
    无接触记录返回 None。"""
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
    """军犬单骑侦察 + 专职侦察车网格探图。

    [第62局用户逐条指示] 军犬: 只养 1 只, 任务=探图找敌基地; 一律 move 指令
    (中途绝不主动攻击); 遇敌 8 格内立即规避撤回家, 脱险 14 格再出发; 探到敌基地
    立即撤回; 阵亡由补员补 1 只。路标=割草机网格(行距 18=视野 9×2 无缝)。
    坦克侦察车: 多路标轮转 150s 节流 + ALARM 反推破节流([第49局]) + 双车([第37局])。
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
        rec, done = [], False
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
                done = True
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
            """路标安全度: 距所有可见敌军的最近距离(无可见敌=足够大)。"""
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
        # [第42局②] 策略自适应: 开局被重压(t<600 内受袭≥3次/2分钟)时暂缓 rush——
        # 速攻期单矿经济正面撞重开局 rush = 第 42 局 25 分钟速败的根源;
        # 转 RECOVER 补经济+塔阵, Rush 窗口顺延到压力缓解
        if len(mem.alarm_times) >= 3 and s["t"] < T["rush_t1"] and stance != "recover":
            logs.append("t=%d RUSH deferred (受袭 %d 次/2分钟, 转补经济)" % (s["t"], len(mem.alarm_times)))
        else:
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
    """两个伏击位：以基地为圆心、敌方向 ±55°。

    [第64局] 半径 14→8: 伏击位贴塔线(哨戒炮射程内), 原先前出 14-20 格正好卡在
    敌 rush 行军线上——14 个动员兵被逐个点名(活局损失曲线实证)。
    """
    mx, my = s["map"]["width"], s["map"]["height"]
    if mem.enemy_base:
        ang = math.atan2(mem.enemy_base[1] - home[1], mem.enemy_base[0] - home[0])
    elif mem.last_alarm_pos:
        ang = math.atan2(mem.last_alarm_pos[1] - home[1], mem.last_alarm_pos[0] - home[0])
    else:
        ang = math.atan2(my / 2.0 - home[1], mx / 2.0 - home[0])
    posts = []
    for da in (-0.96, 0.96):
        x = int(min(max(home[0] + 8 * math.cos(ang + da), 4), mx - 4))
        y = int(min(max(home[1] + 8 * math.sin(ang + da), 4), my - 4))
        posts.append((x, y))
    return posts


def assign_squads(s: dict, home, mem: BattleMemory, stance: str = "defend") -> dict:
    """多线分组（第 31 局, 用户观察: 分职责多线执行, 步兵不再游荡）。

    RAID(坦克奇袭断经济) / ASSAULT(主攻) / HOLD(伏击把手, 步兵为主) /
    GUARD(守家) / RESERVE(机动支援池, 危机救援从这抽人)。
    分配按池子顺序切分, 单位死亡自然缩编, 新兵落到 assault。
    [第63局用户反馈] 敌基地已定位+总攻态势 → 步兵留 4 人守家、其余全部编入
    突击组参战（动员兵蹲伏击位看戏=浪费; 动员兵海拆无防御建筑很强）。
    """
    units = [u for u in all_combat(s["mine"], keep_wounded=True)
             if u["id"] != mem.scout_id]
    # [第66局 V3反制] HTK(防空履带车)从 raid/assault/guard 坦克池剥离, 走专属
    # aahunt 组——它是基地防空屏(拦截 V3 火箭), 混进突击组=被塔区点名送头。
    # [第70局用户反馈 反囤积+编队] 威胁过期(V3/空中/远程火力全无)且存量 >2 时
    # 只留 2 辆守拦截位, 其余战车回归坦克池随大部队编队出击——第 69 局 18 辆
    # HTK 全程囤在基地(用户实证); 威胁在场时仍全员防空屏。
    side = get_side(s)
    aav_units = [u for u in units if side["aa_v"] and u["n"] == side["aa_v"]]
    aav_ids = []                                     # 盟军侧(aa_v=None)无 HTK
    aav_threat = (v3_threat_active(s, mem)
                  or any(h["n"] in AIR_UNITS for h in s["hostile"])
                  or s["t"] - mem.long_fire_t <= T["v3_fire_window"])
    if side["aa_v"]:
        # [第72局 P1b] 拦截位是屏不是仓库(统一式): 威胁在场留 aa_screen(4) 辆屏,
        # 无威胁留 2, 超额一律回归对地编队——第 70/71 局实证: JUMPJET 骚扰使
        # aav_threat 常驻真, "威胁=全员防空屏"分支把 13 辆 HTK 钉死在拦截位,
        # 敌 22 单位地面潮压家时守家部队零坦克(64 秒 my_val 9080→1080)
        keep_n = min(len(aav_units), T["aa_screen"] if aav_threat else 2)
        aav_ids = [u["id"] for u in aav_units[:keep_n]]
        keep = set(aav_ids)
        units = [u for u in units
                 if u["n"] != side["aa_v"] or u["id"] not in keep]
    tanks = [u for u in units if u["o"] == 7]
    inf = [u for u in units if u["o"] != 7]
    sq = {"raid": [], "assault": [], "hold": [], "guard": [], "reserve": [],
          "aahunt": aav_ids}
    # RAID=骚扰组 [第31局A++, 第40局②规模, 第41局换装]: DRON 刺客优先入组
    # （400金秒矿车, 死了不心疼）, 坦克补足; 规模随池子 2→4。
    dron_ids = [u["id"] for u in units if u["n"] == "DRON"]
    if getattr(mem, "siege_mode", False):
        # [第75局] 围城: 机器人打不了建筑, 全部坦克归突击编队(用户"集结大军")
        sq["raid"] = list(dron_ids)
    elif getattr(mem, "rush_defense", False) and mem.enemy_base:
        # [第77局 防御深化II] 防御模式: 坦克不外出骚扰, 全部留塔线协防
        sq["raid"] = list(dron_ids)
    elif mem.enemy_base and (len(tanks) >= 2 or dron_ids):
        n_raid = min(4, max(2, (len(tanks) + len(dron_ids)) // 3))
        # [第70局用户反馈 编队] 突击饥饿保护: 敌基地已定位且坦克池抽完 raid
        # 后突击组 <3 → raid 只用恐怖机器人, 坦克全部留给突击编队——
        # 第 69 局 raid x4 + assault x1(258 次!)碎片化出击实证
        if len(tanks) - n_raid < 3:
            n_raid = min(n_raid, len(dron_ids))
        chosen = (dron_ids + [u["id"] for u in tanks])[:n_raid]
        chosen_set = set(chosen)
        sq["raid"] = chosen
        tanks = [u for u in tanks if u["id"] not in chosen_set]
    # GUARD: 1 辆坦克守家（[第63局] 2→1, 用户反馈闲站坦克太多; 剩余≥2 才留）
    # [第75局] 围城时不留守家坦克——全编入突击(动员兵+塔守家足够)
    if len(tanks) >= 2 and not getattr(mem, "siege_mode", False):
        sq["guard"] = [u["id"] for u in tanks[:max(1, T["keep_home"] - 1)]]
        tanks = tanks[max(1, T["keep_home"] - 1):]
    sq["assault"] = [u["id"] for u in tanks]
    if getattr(mem, "siege_mode", False) \
            and not any(u.get("o") == 2 and u["n"] in DEF_BUILDINGS
                        for u in s["hostile"]):
        # [第80局 用户反馈"总攻决心"] 围城扫荡阶段(防御壳已清): 步兵全员跟上
        # 参战拆建筑——30 动员兵蹲家看戏=79 局教训; 壳未清时步兵仍留守(磁暴/
        # 机枪堡屠步兵, 由坦克 mass-push 先拔壳)
        sq["hold"] = []
        sq["assault"] += [u["id"] for u in inf]
    elif sq["assault"] and not getattr(mem, "siege_mode", False) \
            and (mem.enemy_base or stance in ("attack", "rush")):
        # [第92局 用户反馈① 步坦协同] 坦克编队出击 → 步兵跟随, 不再要求
        # stance=attack(91 局实证: defend 态势下坦克照常波次出击, 步兵 14-15
        # 全程蹲伏击位看戏, 坦克被敌步兵白打——这就是"步坦脱节")。
        # 围城阶段不适用(80 局规则: 壳未清步兵留守防磁暴屠步兵)。
        # 留守 escort_home_n(4)守家伏击, 超出全部编入突击组跟随坦克:
        # 敌步兵打我坦克时, 我方步兵上前反制(动员兵海反步兵强)。
        # rush_defense 时留守抬到驻军地板(8)守塔线——敌兵海压门时塔线火力
        # 优先, 但超出地板的步兵仍随坦克协防反步兵, 不再全员蹲伏击位。
        keep = T["escort_home_n"] if not getattr(mem, "rush_defense", False) \
            else max(T["escort_home_n"], 8)
        sq["hold"] = [u["id"] for u in inf[:keep]]
        sq["assault"] += [u["id"] for u in inf[keep:]]
    else:
        # 防守/发展期(坦克未出击): 步兵全员驻家([第62局用户指示])
        sq["hold"] = [u["id"] for u in inf]
    sq["reserve"] = []
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
    acts, logs = [], []
    # [第75局 用户拍板] 终局围城锁存: 敌基地已定位+进攻态势+敌经济死亡(视野内
    # 无矿车)+我方战力≥1.5倍 → SIEGE。"绝不打塔"铁律的终局例外——铁律防的是
    # 中盘白给, 不是终局放生: 74 局 31 辆坦克 45 分钟零击杀(打残→撤退→再派循环)
    if not mem.siege_mode and mem.enemy_base and stance in ("attack", "rush") \
            and not mem.rush_defense:
        # [第77局] 防御模式激活时围城让位(生存优先: 兵海压门时先守, 威胁解除
        # 后围城锁存自然生效)
        try:
            my_v, en_v = force_value(s)
        except Exception:
            my_v, en_v = 0, 0
        if not any(h["n"] in HARVEST for h in s["hostile"]) \
                and my_v >= 1.5 * max(en_v, 1):
            mem.siege_mode = True
            logs.append("t=%d SIEGE LOCK-ON (my %d >= 1.5x en %d, 敌经济死亡) 全军集结总攻"
                        % (s["t"], my_v, en_v))
    sq = assign_squads(s, home, mem, stance=stance)
    mem.last_squads = dict(sq)
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

    def order_obj(role, ids, tid, x, y, throttle):
        """[第57局] 显式攻击指定目标(建筑/载具 id), 走 order type 2——
        attack_move 会被防御塔吸火, 显式目标让坦克只打该打的东西。"""
        ids = list(ids or [])
        if not ids or not tid:
            return
        wp = mem.squad_wp.setdefault(role, [None, 0.0])
        if wp[0] == (tid, x, y) and wp[1] > time.time():
            return
        wp[0] = (tid, x, y)
        wp[1] = time.time() + throttle
        acts.append({"act": "attack_obj", "ids": ids, "tid": tid})
        logs.append("%s x%d -> 攻击目标#%s@(%d,%d)" % (role, len(ids), tid, x, y))

    def squad_ref(ids):
        """编组平均位置(选最近目标用, 减少穿过塔区的路程)。"""
        idset = set(ids or [])
        pts = [u["tl"] for u in s["mine"] if u["id"] in idset]
        if not pts:
            return None
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    def _assault_advance(logs):
        """[第92局] 无近旁敌单位时的突击组行为(原推进/协防分支收拢至此)。
        优先级: rush_defense 塔线协防 > 敌基地已知点名非防御建筑 >
        attack/rush 前出(打分目标/镜像角) > 回防/前哨。"""
        if getattr(mem, "rush_defense", False) and home:
            order("assault", sq["assault"], home[0] + 3, home[1] + 3, 12)
            logs.append("t=%d RUSH-DEFENSE tanks x%d -> 塔线协防"
                        % (s["t"], len(sq["assault"])))
        elif mem.enemy_base:
            blds = [h for h in s["hostile"] if h["o"] == 2
                    and h["n"] not in DEF_BUILDINGS]
            ref = squad_ref(sq["assault"])
            if blds and ref:
                b = min(blds, key=lambda h: math.hypot(h["tl"][0] - ref[0],
                                                       h["tl"][1] - ref[1]))
                order_obj("assault", sq["assault"], b["id"], b["tl"][0], b["tl"][1], 12)
            else:
                order("assault", sq["assault"], mem.enemy_base[0], mem.enemy_base[1], 12)
        elif stance in ("attack", "rush"):
            tgt_u = pick_target(s, home)
            if tgt_u:
                tgt = list(tgt_u["tl"])
            elif home:
                # [第31局 Route A] 无情报也压向镜像角（用接触找基地, 不龟缩）
                tgt = [max(mx - home[0], 8), max(my - home[1], 8)]
            else:
                tgt = forward_post(s, home, mem)
            order("assault", sq["assault"], tgt[0], tgt[1], 12)
        elif home:
            inside = [h for h in s["hostile"]
                      if math.hypot(h["tl"][0] - home[0],
                                    h["tl"][1] - home[1]) <= 10]
            if inside or len(sq["assault"]) < 4:
                order("assault", sq["assault"], home[0] + 3, home[1] + 3, 12)
            else:
                p = forward_post(s, home, mem)
                order("assault", sq["assault"], p[0], p[1], 12)

    # RAID=骚扰组 [第31局A++]: 优先咬可见的最近敌矿车(断经济) — [第57局] 无矿车
    # 视野时咬最近的敌载具(机器人打不了建筑, 塔区站桩=白给), 再无则随突击组行动
    if mem.enemy_base and sq["raid"]:
        harv = [h for h in s["hostile"] if h["n"] in HARVEST]
        if harv and home:
            h = min(harv, key=lambda h: math.hypot(h["tl"][0] - home[0],
                                                   h["tl"][1] - home[1]))
            order("raid", sq["raid"], h["tl"][0], h["tl"][1], 20)
        else:
            veh = [h for h in s["hostile"] if h["o"] == 7]
            ref = squad_ref(sq["raid"])
            if veh and ref:
                v = min(veh, key=lambda h: math.hypot(h["tl"][0] - ref[0],
                                                      h["tl"][1] - ref[1]))
                order("raid", sq["raid"], v["tl"][0], v["tl"][1], 20)
            else:
                order("raid", sq["raid"], mem.enemy_base[0], mem.enemy_base[1], 30)
    # ASSAULT: 主攻方向 — [第57局用户拍板] 打经济不打塔: 显式攻击视野内最近的
    # 无攻击力敌建筑(order type 2), 绝不攻击防御塔; 无可见经济建筑才退回基地中心
    # [第73局 用户反馈①] 防空接触规避: 可见空中单位距突击组任一成员 ≤ air_evade(14)
    # → 全组后撤到 AA/塔火力圈, 不被火箭飞行兵白打(坦克打不到空中);
    # 空威胁由 aahunt 主动猎杀解除后恢复推进。
    air_units = [h for h in s["hostile"] if h["n"] in AIR_UNITS]
    assault_set = set(sq["assault"])
    air_threat_near = bool(air_units) and sq["assault"] and any(
        math.hypot(h["tl"][0] - u["tl"][0], h["tl"][1] - u["tl"][1]) <= T["air_evade"]
        for h in air_units for u in s["mine"] if u["id"] in assault_set)
    if air_threat_near and home:
        order("assault", sq["assault"], home[0] + 3, home[1] + 3, 12)
        logs.append("t=%d AIR-EVADE assault x%d -> home (坦克打不到空中, 等AA猎杀)"
                    % (s["t"], len(sq["assault"])))
    elif not getattr(mem, "siege_mode", False) and sq["assault"]:
        # [第92局 用户反馈②] 坦克编队野战点名集中火力: 敌单位距编组重心
        # ≤focus_radius → 全组 order_obj 点名同一目标。打分: 敌步行单位(o!=7,
        # 动员兵等反坦克步兵)优先——坦克被步兵缠斗时逐个挨打无还手, 全组先
        # 歼灭步兵; 同级取距重心最近。mem.focus_id 存活且在视野内则续打
        # (一个一个歼灭, 不每 tick 换目标), 死亡/出视野/12s 超时才重选。
        # 围城阶段不适用(拔壳/清建筑目标链优先); 无近旁敌单位落回原推进逻辑。
        ref = squad_ref(sq["assault"])
        _units = [h for h in s["hostile"]
                  if h.get("o") in (3, 7)
                  and not str(h.get("n", "")).startswith("GHOST")]
        _near = [h for h in _units
                 if ref and math.hypot(h["tl"][0] - ref[0],
                                       h["tl"][1] - ref[1]) <= T["focus_radius"]]
        cur = next((h for h in _near if h["id"] == mem.focus_id), None)
        if cur and s["t"] - mem.focus_t <= 12:
            order_obj("assault", sq["assault"], cur["id"],
                      cur["tl"][0], cur["tl"][1], 12)
        elif _near:
            b = min(_near, key=lambda h: (h.get("o") == 7,
                                          math.hypot(h["tl"][0] - ref[0],
                                                     h["tl"][1] - ref[1])))
            mem.focus_id, mem.focus_t = b["id"], s["t"]
            order_obj("assault", sq["assault"], b["id"],
                      b["tl"][0], b["tl"][1], 12)
            logs.append("t=%d FOCUS-FIRE x%d -> #%s@(%d,%d)%s"
                        % (s["t"], len(sq["assault"]), b["id"],
                           b["tl"][0], b["tl"][1],
                           "(敌步兵优先)" if b.get("o") != 7 else ""))
        else:
            mem.focus_id = None
            _assault_advance(logs)
    elif getattr(mem, "siege_mode", False) and mem.enemy_base:
        # [第75局 围城] 防御壳优先——拔壳=解除对己方火力圈(机枪堡是钢甲, 坦克炮
        # 正克制; 中盘"绕开塔"的保命规则至此解除), 壳清后按距离清建筑群
        # [第80局 用户反馈"总攻决心"] ①SIEGE 时 rush_defense 让位(79 局实证:
        #   敌残兵赖在防御半径内使 RUSH-DEFENSE 常驻 ON, 38 单位被按在家里);
        # ②mass-push: 突击组 <8 辆先在集结点攒兵(3 辆一组添油喂磁暴=79 局
        #   9 分钟只拔 1 座线圈), 攒齐一波齐冲, 磁暴塔逐个点名跟不上集火;
        # ③壳清空(清建筑阶段)步兵全员跟上扫荡(总动员, 快速取胜)。
        if getattr(mem, "rush_defense", False):
            mem.rush_defense = False
            logs.append("t=%d SIEGE overrides RUSH-DEFENSE (总攻决心)" % s["t"])
        # [第82局 幻影识别] 裂缝产生器(CANRCT)投影 GHOST* 假建筑——81 局实证:
        # 63 辆坦克对幻影打了 20 分钟零伤害(击杀冻结, 敌值永不动)。
        canrcpt = any(h.get("n") == "CANRCT" for h in s["hostile"])
        if canrcpt:
            mem.gap_seen = True
        # 停滞拉黑: 同一建筑持续集火 >150gs 仍在场 = 幻影(真建筑在 8+ 坦克
        # 集火下秒级倒), 拉黑换下一个
        for h in [x for x in s["hostile"] if x.get("o") == 2]:
            ft = mem.siege_target_hist.get(h["id"])
            if ft is not None and s["t"] - ft > 150 \
                    and h["id"] not in mem.ghost_ids:
                mem.ghost_ids.add(h["id"])
                mem.siege_target_hist.pop(h["id"], None)
                logs.append("t=%d GHOST detected #%s@%s (集火150gs不倒, 拉黑)"
                            % (s["t"], h["id"], list(h["tl"])))
        if mem.gap_seen and not canrcpt \
                and (mem.ghost_ids or mem.siege_target_hist):
            mem.ghost_ids.clear()
            mem.siege_target_hist.clear()   # 源头已灭, 幻影消散, 全目标重扫
            mem.gap_seen = False
        ref = squad_ref(sq["assault"])
        def _ghostfree(units):
            # GHOST* 假目标与已拉黑 id 不入目标池
            return [h for h in units
                    if not str(h.get("n", "")).startswith("GHOST")
                    and h["id"] not in mem.ghost_ids]
        defb = _ghostfree([h for h in s["hostile"]
                           if h.get("o") == 2 and h["n"] in DEF_BUILDINGS])
        bldg = _ghostfree([h for h in s["hostile"] if h.get("o") == 2])
        # 裂缝产生器优先(源头拆掉=幻影消散, 真建筑显形)
        gap = [h for h in (defb or bldg)
               if "NRCT" in str(h.get("n", ""))]
        pool = gap or defb or bldg
        if sq["assault"] and len(sq["assault"]) < T["siege_push_n"] and defb:
            order("assault", sq["assault"], home[0] + 3, home[1] + 3, 12)
            logs.append("t=%d SIEGE STAGING x%d/%d (攒兵团, 齐冲再上)"
                        % (s["t"], len(sq["assault"]), T["siege_push_n"]))
        elif pool and ref and sq["assault"]:
            b = min(pool, key=lambda h: math.hypot(h["tl"][0] - ref[0],
                                                   h["tl"][1] - ref[1]))
            mem.siege_target_hist.setdefault(b["id"], s["t"])
            order_obj("assault", sq["assault"], b["id"], b["tl"][0], b["tl"][1], 12)
            tag = ("拔裂缝产生器" if gap else "拔防御壳" if defb else "清建筑")
            logs.append("t=%d SIEGE %s x%d -> #%s@(%d,%d)"
                        % (s["t"], tag, len(sq["assault"]),
                           b["id"], b["tl"][0], b["tl"][1]))
        else:
            order("assault", sq["assault"], mem.enemy_base[0], mem.enemy_base[1], 12)
    # [第92局] 原 rush_defense 协防 / attack 推进 / 回防 三分支已收拢进
    # _assault_advance(点名分支的 else 路径), 行为保持不变。
    if home:
        # HOLD: 两个伏击位分兵
        posts = _hold_posts(s, home, mem)
        half = (len(sq["hold"]) + 1) // 2
        order("hold_a", sq["hold"][:half], posts[0][0], posts[0][1], 60)
        order("hold_b", sq["hold"][half:], posts[1][0], posts[1][1], 60)
        order("guard", sq["guard"], home[0] + 3, home[1] + 3, 30)
        order("reserve", sq["reserve"], home[0], home[1] + 8, 60)
        # [第66局 V3反制] AA 屏: 有可见 V3(26 格内) → 全组显式攻击最近家的那台
        # (速度 8 追速度 4, 途中顺带拦火箭); 否则守威胁方向 10 格拦截位
        # (塔线内侧, 等火箭进拦截射程)。同一 tick 只发一种指令防打架。
        if sq["aahunt"]:
            tgt_v3 = None
            v3s = [h for h in s["hostile"] if h["n"] in V3_CODES]
            if v3s:
                v = min(v3s, key=lambda h: math.hypot(
                    h["tl"][0] - home[0], h["tl"][1] - home[1]))
                if math.hypot(v["tl"][0] - home[0], v["tl"][1] - home[1]) <= 26:
                    tgt_v3 = v
            if tgt_v3:
                order_obj("aahunt", sq["aahunt"], tgt_v3["id"],
                          tgt_v3["tl"][0], tgt_v3["tl"][1], 12)
            else:
                # [第73局 用户反馈②③] 防空主动猎杀: 可见空中单位 → 全组显式
                # 攻击最近的一台(上前消灭, 不龟缩拦截位); 无可见空中才守拦截位
                airs = [h for h in s["hostile"] if h["n"] in AIR_UNITS]
                a = min(airs, key=lambda h: math.hypot(
                    h["tl"][0] - home[0], h["tl"][1] - home[1])) if airs else None
                if a:
                    order_obj("aahunt", sq["aahunt"], a["id"],
                              a["tl"][0], a["tl"][1], 12)
                else:
                    if mem.enemy_base:
                        dx, dy = mem.enemy_base[0] - home[0], mem.enemy_base[1] - home[1]
                    elif mem.last_alarm_pos:
                        dx, dy = (mem.last_alarm_pos[0] - home[0],
                                  mem.last_alarm_pos[1] - home[1])
                    else:
                        dx, dy = mx / 2.0 - home[0], my / 2.0 - home[1]
                    nrm = max(math.hypot(dx, dy), 1.0)
                    ix = int(min(max(home[0] + dx / nrm * 10, 4), mx - 4))
                    iy = int(min(max(home[1] + dy / nrm * 10, 4), my - 4))
                    order("aahunt", sq["aahunt"], ix, iy, 30)
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
