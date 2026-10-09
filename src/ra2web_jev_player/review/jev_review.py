# -*- coding: utf-8 -*-
"""Jev semantic review: defeat-cause classification + top-priority improvement + whether
auto-tuning is worthwhile (the semantic call).

state = summary_text(deterministic material), questions = the rootcause/topfix/tune trio.
(Extracted verbatim from review.py: functions moved line by line, behavior unchanged; the
review conventions comments are kept at each function.)
"""
from __future__ import annotations

from ..jev import JevClient
from .record import GameRecord

# ================= Jev 语义复盘 =================

def summary_text(rec: GameRecord, findings: list) -> str:
    """Battle report -> compact Chinese review material (the state fed to Jev)."""
    eco, curve, lk = rec.economy(), rec.army_curve(), rec.loss_kill()
    bo = " → ".join("%s@%ds" % (n, t) for t, n in rec.build_order[:10]) or "无建筑建成"
    lines = [
        "== 对局结果 ==",
        "结果:%s 时长:%s游戏秒 ticks:%d 危机tick:%d" % (
            rec.outcome, rec.t_end, rec.report.get("ticks"), rec.report.get("crisis_ticks")),
        "开局建造: " + bo,
        "首坦克: t=%ss" % rec.first_tank_t,
        "敌基地定位: %s" % ("已定位" if rec.enemy_base else "全程未发现"),
        "== 数据曲线 ==",
        "兵力价值峰值: 我方%s vs 敌%s | 坦克峰值: %s" % (
            curve.get("my_val_peak"), curve.get("en_val_peak"), curve.get("tanks_peak")),
        "资金: 平均%s 峰值%s 见底率%.0f%%" % (
            eco.get("avg"), eco.get("max"), (eco.get("starve_frac") or 0) * 100),
        "损失/可见击杀: %d/%d  top损失: %s" % (
            lk["losses"], lk["kills_visible"], lk["loss_top"]),
        "态势分布: %s | ALARM:%d(反击%d/守塔%d) 停摆:%d" % (
            rec.stance_distribution(), len(rec.alarms), len(rec.counters),
            len(rec.turtles), len(rec.stalls)),
        "== 确定性发现 ==",
        "\n".join("·[%s] %s" % (sev, txt) for sev, txt, _ in findings) or "·无",
    ]
    return "\n".join(lines)


ROOTCAUSE_CRITERIA = {
    "no_target": "侦察失败/敌基地未定位, 进攻态势无目标可打, 全程被动",
    "starve": "经济或产能断粮: 坦克上不了产线, 资金长期见底, 步兵/防御吃掉预算",
    "def overrun": "防守体系被消耗/压垮: 塔阵被打穿, 波次强于防御恢复",
    "attrition": "野战/微操交换比劣势: 兵力换亏, 残血不撤或反击送人头",
    "bug": "工程缺陷: 某 tick 层逐帧报错失效(如侦察/感知)",
    "timing": "开局时序过慢: 建造/出兵晚于手册窗口, 被早期 rush 打崩",
    "other": "以上都不是或混合原因之外的因素",
}

TOPFIX_CRITERIA = {
    "fix_scout": "修侦察链路: 保证敌基地定位(军犬+坦克镜像探图), 让进攻有目标",
    "boost_econ": "加强经济时序: 二矿/矿车更早, 坦克预算优先级更高",
    "attack_earlier": "降低进攻门槛: 更早换家/rush, 不等大军团",
    "deepen_def": "加强防御纵深: 更多塔/前置阵地/修复优先级",
    "fix_bugs": "优先修工程 bug, 策略不动",
    "keep": "保持现状, 本局原因属偶然",
}


def jev_review(rec: GameRecord, findings: list, jev: JevClient) -> dict:
    """Jev semantic review: defeat-cause classification + top-priority improvement + whether
    auto-tuning is worthwhile."""
    state = summary_text(rec, findings)
    answers = jev.ask(state, {
        "rootcause": {"type": "choice",
                      "instructions": ("对战复盘裁判: 从数据曲线和确定性发现判断本局失利的"
                                       "首要根因（单选最主要的一个）。"),
                      "criteria": ROOTCAUSE_CRITERIA},
        "topfix": {"type": "choice",
                   "instructions": "下一局最应该优先做的一件事（单选，对胜率提升最大）。"
                                   "注意与根因对应, 但也要考虑性价比。",
                   "criteria": TOPFIX_CRITERIA},
        "tune": {"type": "noul",
                 "instructions": ("基于本局数据, 是否支持对 doctrine 参数做一次小幅自动微调"
                                  "（白名单内限幅, 如进攻门槛/坦克资金线）? "
                                  "数据噪声大或根因是工程bug时说不。")},
    })
    return answers
