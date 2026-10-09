# -*- coding: utf-8 -*-
"""僵尸局守卫(第 95/101 局): 击杀冻结与无机动单位两个优雅退出检测器。

自 strategy/planner.py 原样拆出（2026-10-09 结构重构）:
代码逐行搬运, 行为零改动; 每条局次标注的迭代注释保留在各函数处。
"""
from __future__ import annotations

from ..state import force_value
from .memory import BattleMemory


def myval_zero(mem: BattleMemory, s: dict) -> int:
    """[第101局] 我方无机动单位超时(99 局教训): myval=0=防线已亡, 敌拆建筑
    拖沓或敌方 AI 卡住时游戏永不判负——defend/develop 态势下 myval=0 持续
    300gs 即优雅退出(无翻盘路径)。返回持续秒数(0=未触发)。"""
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
