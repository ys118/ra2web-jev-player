# -*- coding: utf-8 -*-
"""确定性决策层(包) —— 原单文件 planner.py(1642 行)按职责拆分, 行为零改动。

从 legacy_bot 原样迁移（第 18-20 局复盘定稿版）后, 只做过两处架构性改动：
1. 纯函数化：函数吃 (state, home, mem) 吐 action 列表，由 game.py 经页内客户端执行，
   离线可测；
2. 职责去重：建筑落位/维修划归页内微操（150ms 级反应更快），本层不再做。

行为参数零改动 —— 每条阈值都有局次复盘背书（doctrine.T / CONF / THREAT_FORCE_DEFEND）。

子模块（依赖方向单向, 无环）:
- memory    单局记忆 BattleMemory（其余模块的地基）
- sense     秒级战场感知: ALARM 识别与危机速应
- scout     侦察与敌基地定位（军犬路标网/坦克镜像探图/敌影反推）
- orders    §10.1 确定性清单 + V3 威胁判定
- opening   开局建造序列（阵营感知, 含引擎拒收自愈回退）
- guard     僵尸局守卫（击杀冻结/无机动单位优雅退出）
- combat    五态机确定性入口 + 进攻执行（前哨/编组/机动指挥）
- jev_apply Jev 批量答案 → 动作 + 态势采信

对外 API 与原 planner.py 完全一致（game.py 与回归测试按名调用）; 本文件把
子模块的名字统一转出, 调用方 `from .strategy import planner` 无需改动。
"""
from __future__ import annotations

from ..doctrine import (
                        AA_VEHICLES,
                        AIR_UNITS,
                        CONF,
                        DEF_BUILDINGS,
                        HARVEST,
                        MCV_CODES,
                        SCOUT_DOGS,
                        THREAT_FORCE_DEFEND,
                        V3_CODES,
                        T,
                        get_side,
)
from ..state import all_combat, available, buildings, combat_tanks, force_value, nm, pick_target, queues_by_type, ucost
from .combat import _hold_posts, assign_squads, forward_post, movement, stance_overrides
from .guard import kill_freeze, myval_zero
from .jev_apply import apply_jev
from .memory import BattleMemory
from .opening import _OPENING_LEGACY, build_gate, opening_build, opening_next_code
from .orders import checklist, v3_threat_active
from .scout import contact_edge, scouting, shadow_target, update_enemy_base
from .sense import crisis_response, sense_events

__all__ = [
    "BattleMemory",
    # sense
    "crisis_response", "sense_events",
    # scout
    "contact_edge", "scouting", "shadow_target", "update_enemy_base",
    # orders
    "checklist", "v3_threat_active",
    # opening
    "_OPENING_LEGACY", "build_gate", "opening_build", "opening_next_code",
    # guard
    "kill_freeze", "myval_zero",
    # combat
    "_hold_posts", "assign_squads", "forward_post", "movement", "stance_overrides",
    # jev_apply
    "apply_jev",
    # doctrine/state 转发（原 planner.py 的历史对外符号, 保留兼容）
    "AA_VEHICLES", "AIR_UNITS", "CONF", "DEF_BUILDINGS", "HARVEST", "MCV_CODES",
    "SCOUT_DOGS", "THREAT_FORCE_DEFEND", "T", "V3_CODES", "get_side",
    "all_combat", "available", "buildings", "combat_tanks", "force_value", "nm",
    "pick_target", "queues_by_type", "ucost",
]
