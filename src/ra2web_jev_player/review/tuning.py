# -*- coding: utf-8 -*-
"""参数自动微调: 根因 → 白名单参数(限幅) · Jev 置信 >0.6 才执行。

写入 docs/knowledge/doctrine.json, 由 doctrine.load_overrides() 在新局加载。
git 历史即调参审计轨迹。
(自 review.py 原样拆出: 函数逐行搬运, 行为零改动; 复盘口径注释保留在各函数处。)
"""
from __future__ import annotations

import json
import time

from ..paths import DOCTRINE_OVERRIDES_PATH as OVERRIDES_PATH
from ..strategy.doctrine import T, load_overrides

# 自动调参白名单与限幅（缺省值边界）：只允许小幅收紧/放宽，防单局噪声破坏 doctrine
TUNING_RULES = {
    "no_target":   [("attack_tanks", -1, 5), ("rush_tanks", -1, 3)],
    "starve":      [("tank_cash1", -100, 800), ("tank_cash2", -200, 1200)],
    "def overrun": [("defend_radius", +2, 26)],
    "attrition":   [("retreat_hp", +0.05, 0.60)],
}


# ================= 迭代：参数自动微调（白名单+限幅） =================

def _clamp(v: float, lo: float) -> float:
    return max(v, lo)


def auto_tune(rootcause: str, tune_conf: float, game_no: int, reason: str) -> list:
    """根因 → 白名单参数微调（限幅）。tune_conf > 0.6 才执行。返回变更描述。"""
    if tune_conf <= 0.6 or rootcause not in TUNING_RULES:
        return []
    load_overrides()          # 副作用: 覆盖值写入 T
    changes = []
    for key, delta, floor in TUNING_RULES[rootcause]:
        cur = T[key]
        new = _clamp(round(cur + delta, 2), floor)
        if new == cur:
            continue
        T[key] = new
        changes.append({"key": key, "from": cur, "to": new,
                        "reason": "%s@game%d: %s" % (rootcause, game_no, reason)})
    if changes:
        _save_overrides(changes, game_no, reason)
    return changes


def _save_overrides(changes: list, game_no: int, reason: str) -> None:
    try:
        ov = json.load(open(OVERRIDES_PATH, encoding="utf-8")) if OVERRIDES_PATH.exists() else {}
    except Exception:
        ov = {}
    t_ov = ov.setdefault("T", {})
    for c in changes:
        t_ov[c["key"]] = c["to"]
    hist = ov.setdefault("history", [])
    hist.append({"game": game_no, "ts": time.strftime("%Y-%m-%d %H:%M"),
                 "reason": reason,
                 "changes": [{k: c[k] for k in ("key", "from", "to")} for c in changes]})
    ov["history"] = hist[-20:]
    ov["_provenance"] = "由 review 包复盘自动写入（白名单+限幅+置信>0.6 闸门）；可直接人工编辑"
    OVERRIDES_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding="utf-8")
