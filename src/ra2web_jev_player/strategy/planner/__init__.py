# -*- coding: utf-8 -*-
"""Deterministic decision layer (package) - the former single-file planner.py
(1642 lines) split by responsibility, zero behavior change.

After migrating verbatim from legacy_bot (the version finalized by the games 18-20
reviews), only two architectural changes were made:
1. Pure functions: functions take (state, home, mem) and emit action lists, executed
   by game.py through the in-page client, so they are testable offline;
2. Responsibility dedup: building placement/repair moved to in-page micro (faster
   reaction at the 150ms level), no longer done in this layer.

Behavior parameters unchanged - every threshold is backed by a game review
(doctrine.T / CONF / THREAT_FORCE_DEFEND).

Submodules (dependency direction is one-way, no cycles):
- memory    per-game memory BattleMemory (the foundation of the other modules)
- sense     second-level battlefield awareness: ALARM recognition and crisis response
- scout     reconnaissance and enemy base location (dog waypoint net / tank mirror
            scouting / enemy-shadow inference)
- orders    §10.1 deterministic checklist + V3 threat test
- opening   opening build sequence (faction aware, with engine-rejection self-heal fallback)
- guard     zombie-game guard (kill-freeze / graceful exit with no mobile units)
- combat    five-stance machine deterministic entry + attack execution
            (forward post / squad assignment / movement command)
- jev_apply Jev batched answers -> actions + stance adoption

The public API is identical to the original planner.py (game.py and the regression
tests call it by name); this file re-exports the submodule names, so callers doing
`from .strategy import planner` need no changes.
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
