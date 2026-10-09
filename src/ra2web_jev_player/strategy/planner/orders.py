# -*- coding: utf-8 -*-
"""§10.1 确定性清单: 按优先级产出确定性动作(建造/造兵/防御/撤退),
以及 V3 威胁活跃判定(生产闸门)。

自 strategy/planner.py 原样拆出（2026-10-09 结构重构）:
代码逐行搬运, 行为零改动; 每条局次标注的迭代注释保留在各函数处。
"""
from __future__ import annotations

import math
import time

from ..doctrine import AA_VEHICLES, AIR_UNITS, HARVEST, MCV_CODES, T, get_side
from ..state import available, buildings, combat_tanks, queues_by_type, ucost
from .memory import BattleMemory
from .opening import opening_next_code

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

    # 7.7) [第97局 用户反馈②] 空军反制生产: 可见敌空中单位(JUMPJET 火箭
    #     飞行兵等) → HTK 优先补产(帽内)——96 局实证: 敌空军压制下 aav=0,
    #     坦克每次出击都被 AIR-EVADE 赶回家 = "出击→回家"死循环僵持。
    #     反制到位后 AIR-EVADE 窗口自然关闭, 进攻恢复。结构与 V3-RESPONSE
    #     一致(插在坦克线之前)。
    air_on = any(h["n"] in AIR_UNITS for h in s["hostile"])
    if air_on and side["aa_v"] and bl.get(side["weap"], 0) >= 1 and q3s == 0 \
            and not v3_on \
            and side["aa_v"] in available(s["av"], 3):
        aav_cost = ucost(side["aa_v"])
        if n_aav < T["aa_htk_cap"] and cred >= aav_cost:
            qty = max(1, min(2 if cred >= aav_cost * 2 else 1,
                             T["aa_htk_cap"] - n_aav))
            acts.append({"act": "produce", "name": side["aa_v"], "qty": qty, "q": 3})
            logs.append("t=%d AIR-RESPONSE %s x%d (alive %d, 敌空军在场)"
                        % (s["t"], side["aa_v"], qty, n_aav))
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
        # [第100局 用户反馈②] 塔建在迎敌面前沿: home→敌方向 10 格(游戏自动
        # 落点在基地后方=塔够不着来敌); canPlace 不行由 _exec 向 home 回退。
        _ax, _ay = home
        _dir = None
        if mem.enemy_base:
            _dir = (mem.enemy_base[0] - home[0], mem.enemy_base[1] - home[1])
        elif mem.last_alarm_pos:
            _dir = (mem.last_alarm_pos[0] - home[0], mem.last_alarm_pos[1] - home[1])
        if _dir:
            _n = max(math.hypot(_dir[0], _dir[1]), 1.0)
            acts.append({"act": "produce", "name": side["gdef"], "qty": 1, "q": 1,
                         "x": int(home[0] + _dir[0] / _n * 10),
                         "y": int(home[1] + _dir[1] / _n * 10)})
        else:
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
