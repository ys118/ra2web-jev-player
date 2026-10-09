# -*- coding: utf-8 -*-
"""Zombie-game guard (games 95/101): two graceful-exit detectors, kill-freeze and
no-mobile-units.

Split verbatim out of strategy/planner.py (2026-10-09 structural refactor):
code moved line by line, zero behavior change; every game-tagged iteration comment
stays at its function.
"""
from __future__ import annotations

from ..state import force_value
from .memory import BattleMemory


def myval_zero(mem: BattleMemory, s: dict) -> int:
    """[game 101] My no-mobile-units timeout (game 99 lesson): myval=0 = the defense
    is dead; when the enemy demolishes buildings slowly or the enemy AI is stuck,
    the game never declares a loss - in defend/develop stance myval=0 lasting 300gs
    means a graceful exit (no comeback path). Returns the duration in seconds
    (0 = not triggered)."""
    try:
        my_v, _ = force_value(s)
    except Exception:
        mem.myval_zero_since = None
        return 0
    if my_v > 0 or s["me"].get("defeated"):
        mem.myval_zero_since = None
        return 0
    if mem.myval_zero_since is None:
        mem.myval_zero_since = s["t"]
    return s["t"] - mem.myval_zero_since


def kill_freeze(mem: BattleMemory, s: dict, stance: str) -> int:
    """[game 95 kill-freeze detector] Game 94's false stalemate confirmed: from
    t=2127 the enemy force value stayed at 12300 / kills froze for 6600s - after the
    enemy swarm was wiped out the remnants were stuck somewhere unreachable (terrain
    block), and at 6.4x force value we physically could not end the game, burning
    100 minutes for nothing. Returns the freeze duration in game seconds (0 = not
    frozen); the caller terminates the zombie game at the threshold (3000gs).

    Freeze test: in attack/rush stance (1) the enemy force value does not move for a
    single tick and (2) our force value crushes at >= 2.5x (excluding numeric
    coincidences of an even back-and-forth). Judged only in attack stance - during
    develop/defend a static enemy value is normal; if the enemy really is building
    up, the value changes and the timer resets automatically."""
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
