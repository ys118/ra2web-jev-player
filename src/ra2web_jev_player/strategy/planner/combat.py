# -*- coding: utf-8 -*-
"""五态机确定性入口 + 进攻执行(第 18-20 局定稿): 前哨/编组/机动指挥。

自 strategy/planner.py 原样拆出（2026-10-09 结构重构）:
代码逐行搬运, 行为零改动; 每条局次标注的迭代注释保留在各函数处。
"""
from __future__ import annotations

import math
import time

from ..doctrine import AIR_UNITS, DEF_BUILDINGS, HARVEST, V3_CODES, T, get_side
from ..state import all_combat, combat_tanks, force_value, pick_target
from .memory import BattleMemory
from .orders import v3_threat_active

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
    # [第100局 用户反馈①] 伏击位前移到迎敌正面(半径 12、±30°)——
    # 原半径 8±55° 躲在基地两侧后面, 敌来时接敌慢; 12 格仍在塔火力圈边缘。
    posts = []
    for da in (-0.5, 0.5):
        x = int(min(max(home[0] + 12 * math.cos(ang + da), 4), mx - 4))
        y = int(min(max(home[1] + 12 * math.sin(ang + da), 4), my - 4))
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
          "aahunt": aav_ids, "sweep": []}
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
        # [第100局 用户反馈③] 步兵任务化: 坦克未出击时步兵也不蜷家——
        # 守备 4 + 超额的一半编扫荡队(咬敌矿车/守前哨); rush_defense 例外
        # (全员驻塔线, 保命优先; 62 局"全员驻家"由本条升级)。
        if getattr(mem, "rush_defense", False)                 or getattr(mem, "siege_mode", False):
            # 围城壳未清时步兵留守(80 局规则: 防磁暴屠步兵)
            sq["hold"] = [u["id"] for u in inf]
        else:
            extra = inf[4:]
            half = (len(extra) + 1) // 2
            sq["sweep"] = [u["id"] for u in extra[:half]] if len(extra) >= 2 else []
            sq["hold"] = ([u["id"] for u in inf[:4]]
                          + [u["id"] for u in extra[half:]])
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

    def _order_raw(role, ids, x, y, throttle):
        """[第101局] 绕过 role 槽节流的直接下令(mirror-scout 与协防
        同 tick 并发, 共享槽会互相覆盖丢指令)。"""
        ids = list(ids or [])
        if not ids:
            return
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
            # [第101局 fix_scout 深化(Jev 连续 6 局 0.9 置信)] 敌基地未知时
            # 抽 1 辆坦克常态化镜像探图(120s 节流, 不再等军犬独自探)——
            # 99/100 局"侦察缺失+无目标"复合死法的对攻解。
            if not mem.enemy_base and len(sq["assault"]) >= 2                     and s["t"] - mem.mirror_scout_t > 120:
                _mx, _my = s["map"]["width"], s["map"]["height"]
                _m = [max(_mx - home[0], 8), max(_my - home[1], 8)]
                # 独立 role: 与协防指令不同 squad_wp 槽, 互不覆盖
                _order_raw("mscout", sq["assault"][:1], _m[0], _m[1], 120)
                mem.mirror_scout_t = s["t"]
                logs.append("t=%d MIRROR-SCOUT x1 -> %s (协防期镜像探图)"
                            % (s["t"], _m))
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
    # [第100局 用户反馈②] 敌采矿车摸进我方基地/矿区 → 拦截目标
    inv_harv = None
    if home:
        _inv = [h for h in s["hostile"] if h["n"] in HARVEST
                and math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= 22]
        if _inv:
            inv_harv = min(_inv, key=lambda h: math.hypot(
                h["tl"][0] - home[0], h["tl"][1] - home[1]))
    if air_threat_near and home:
        order("assault", sq["assault"], home[0] + 3, home[1] + 3, 12)
        logs.append("t=%d AIR-EVADE assault x%d -> home (坦克打不到空中, 等AA猎杀)"
                    % (s["t"], len(sq["assault"])))
    elif inv_harv and (sq["assault"] or sq["raid"]):
        # [第100局 用户反馈②] 敌矿车入侵拦截: 敌采矿车摸进我方矿区(≤22 格)
        # → 主力先集中火力消灭它(断敌经济+护我矿区), 优先于点名/STAGING。
        order_obj("assault", sq["assault"] or sq["raid"], inv_harv["id"],
                  inv_harv["tl"][0], inv_harv["tl"][1], 12)
        logs.append("t=%d INTRUDER-HUNT x%d -> 敌矿车#%s@%s (护矿拦截)"
                    % (s["t"], len(sq["assault"] or sq["raid"]),
                       inv_harv["id"], inv_harv["tl"]))
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
        # [第97局 用户反馈①] STAGING 不再撤回基地门口攒兵(=在基地转圈)——
        # 集结点改为敌基地方向前沿(home→敌基地连线 55% 处, 前出待命), 攒齐
        # 直接齐冲; 阈值 siege_push_n 8→5(用户: 不要空等待)。
        if sq["assault"] and len(sq["assault"]) < T["siege_push_n"] and defb:
            dx, dy = mem.enemy_base[0] - home[0], mem.enemy_base[1] - home[1]
            fx = int(home[0] + dx * 0.55)
            fy = int(home[1] + dy * 0.55)
            order("assault", sq["assault"], fx, fy, 12)
            logs.append("t=%d SIEGE STAGING x%d/%d (前沿集结, 齐冲再上)"
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
        # [第100局] guard 前移到迎敌方向 6 格(不再蹲基地正中心)
        _gx, _gy = home[0] + 3, home[1] + 3
        if mem.enemy_base:
            _d = (mem.enemy_base[0] - home[0], mem.enemy_base[1] - home[1])
            _gn = max(math.hypot(_d[0], _d[1]), 1.0)
            _gx = int(home[0] + _d[0] / _gn * 6)
            _gy = int(home[1] + _d[1] / _gn * 6)
        order("guard", sq["guard"], _gx, _gy, 30)
        order("reserve", sq["reserve"], home[0], home[1] + 8, 60)
        # [第100局 用户反馈③] 扫荡队: 优先咬可见敌矿车(距家 ≤60 格),
        # 无可见矿车则占前哨要点——步兵始终有任务, 不蜷家。
        if sq.get("sweep"):
            _sh = [h for h in s["hostile"] if h["n"] in HARVEST and home
                   and math.hypot(h["tl"][0] - home[0],
                                  h["tl"][1] - home[1]) <= 60]
            if _sh:
                _h = min(_sh, key=lambda h: math.hypot(
                    h["tl"][0] - home[0], h["tl"][1] - home[1]))
                order("sweep", sq["sweep"], _h["tl"][0], _h["tl"][1], 30)
            elif mem.enemy_base:
                order("sweep", sq["sweep"], mem.enemy_base[0], mem.enemy_base[1], 60)
            else:
                _p = forward_post(s, home, mem)
                order("sweep", sq["sweep"], _p[0], _p[1], 60)
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
                # [第100局 用户反馈①] AA 自保: 火箭人附近(≤12 格)有敌地面
                # 战车护航时, 防空车不上去送死——先退回坦克线后方, 让克制
                # 地面战车的我方坦克(FOCUS-FIRE 会点名)先清场, 再猎火箭人。
                airs = [h for h in s["hostile"] if h["n"] in AIR_UNITS]
                a = min(airs, key=lambda h: math.hypot(
                    h["tl"][0] - home[0], h["tl"][1] - home[1])) if airs else None
                if a:
                    escort = [h for h in s["hostile"]
                              if h.get("o") == 7 and h["n"] not in HARVEST
                              and h["n"] not in AIR_UNITS
                              and math.hypot(h["tl"][0] - a["tl"][0],
                                             h["tl"][1] - a["tl"][1]) <= 12]
                    # 判据=火箭人附近有护航(接近途中必被集火), 而非护航已贴近
                    if escort and sq["assault"]:
                        order("aahunt", sq["aahunt"], home[0] + 6, home[1] + 6, 12)
                        logs.append("t=%d AA-HOLD x%d (敌战车护航火箭人, 待坦克清场)"
                                    % (s["t"], len(sq["aahunt"])))
                    else:
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
