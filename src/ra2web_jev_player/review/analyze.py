# -*- coding: utf-8 -*-
"""Deterministic analysis: anything computable in code is never handed to the model
(METHODOLOGY principle).

Produces a list of (severity, title, evidence) triples, fed to the Jev semantic review and
the review md.
(Extracted verbatim from review.py: functions moved line by line, behavior unchanged; the
review conventions comments are kept at each function.)
"""
from __future__ import annotations

import re

from ..strategy.doctrine import T
from .record import GameRecord

# 复盘时间窗参照（Bible §5.4）：开局 60s 内电厂、~300s 前首坦克
BUILD_WINDOWS = {"NAPOWR": 45, "NAREFN": 120, "NAHAND": 240, "NAWEAP": 330}


# ================= 确定性分析 =================

def analyze(rec: GameRecord) -> list:
    """Deterministic findings: each entry is a (severity, title, evidence) triple."""
    out = []
    # 1) 开局时序 vs 手册窗口（build_order 元素是 (t, code)，取每个代号首次建成时间）
    built: dict = {}
    for t, code in rec.build_order:
        built.setdefault(code, t)
    for code, window in BUILD_WINDOWS.items():
        t = built.get(code)
        if t is None:
            out.append(("high", "开局缺 %s（%ds 窗口内未建成）" % (code, window), "build_order"))
        elif t > window * 1.5:
            out.append(("med", "%s 建成于 t=%ds，手册窗口 ~%ds（慢 %.0f%%）"
                        % (code, t, window, 100 * (t / max(window, 1) - 1)), "build_order"))
    # 2) 首坦克时间
    if rec.first_tank_t is None:
        out.append(("high", "整局没有一辆坦克下线", "TANK lines"))
    elif rec.first_tank_t > 400:
        out.append(("med", "首坦克 t=%ds（Bible 时间窗 180-320s）" % rec.first_tank_t, "TANK lines"))
    # 3) 侦察
    if not rec.enemy_base:
        out.append(("high", "敌基地全程未定位 → ATTACK/RUSH 无目标，无法取胜",
                    "ENEMY BASE line"))
    # 4) 经济
    eco = rec.economy()
    if eco and eco.get("starve_frac", 0) > 0.6:
        out.append(("med", "资金长期见底（<200 金占比 %.0f%%），坦克生产线被步兵/防御挤占"
                    % (eco["starve_frac"] * 100), "obs credits"))
    # 5) 步兵/坦克失衡
    curve = rec.army_curve()
    if curve and curve.get("tanks_peak", 0) < 5 and rec.t_end and rec.t_end > 900:
        out.append(("med", "15 分钟后坦克峰值仅 %d 辆（总攻门槛 %d）——产能/资金被别处吃掉"
                    % (curve.get("tanks_peak", 0), T["attack_tanks"]), "obs tanks"))
    # [第72局 P4] 敌潮时刻对地 mass 缺失检测(70/71 局败因: 守家零重坦)
    dc = curve.get("death_comp")
    if rec.outcome == "defeat" and dc is not None and (dc.get("armor") or 0) <= 2:
        out.append(("high", "敌潮时刻防线重坦仅 %d 辆（防空车 %d/步兵 %s）——对地 mass 缺失"
                    % (dc.get("armor"), dc.get("aav", -1), dc.get("inf", "?")), "obs armor"))
    # 6) 防守占比
    dist = rec.stance_distribution()
    if dist.get("defend", 0) >= 0.7 and rec.outcome != "victory":
        out.append(("high", "态势 %.0f%% 时间在 defend：纯被动挨打，缺进攻闭环"
                    % (dist.get("defend", 0) * 100), "obs stance"))
    # 7) 危机响应
    if rec.report:
        ct = rec.report.get("crisis_ticks") or 0
        tk = rec.report.get("ticks") or 1
        if ct / max(tk, 1) > 0.3:
            out.append(("med", "危机 tick 占比 %.0f%%（%d/%d）——长期处于被袭状态"
                        % (100 * ct / tk, ct, tk), "report"))
    # 8) 错误指纹
    errs = {}
    for ln in rec.err_lines:
        key = re.search(r"(\w+) ERR", ln)
        errs[key.group(1)] = errs.get(key.group(1), 0) + 1 if key else 1
    for k, v in errs.items():
        out.append(("high" if v > 10 else "med", "%s ERR ×%d（工程缺陷，逐 tick 失效）" % (k, v),
                    "log"))
    if len(rec.stalls) > 0:
        out.append(("low", "模拟停摆 %d 次" % len(rec.stalls), "log"))
    return out
