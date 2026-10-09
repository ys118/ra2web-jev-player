# -*- coding: utf-8 -*-
"""Per-game memory (BattleMemory) - fields identical to legacy_bot MEM, discarded
when the game ends.

Split verbatim out of strategy/planner.py (2026-10-09 structural refactor):
code moved line by line, zero behavior change; every game-tagged iteration comment
stays at its function.
"""
from __future__ import annotations


class BattleMemory:
    """Per-game memory (in-process, discarded when the game ends). Fields identical
    to legacy_bot MEM."""

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
        self.mirror_scout_t = 0         # [第101局] 塔线协防期镜像探图时刻(120s 节流)
        self.myval_zero_since = None    # [第101局] 我方无机动单位起始时刻(终局判定)
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
