# -*- coding: utf-8 -*-
"""复盘产出: 每局 review.md + 事件切片 + LESSONS 账本追加（追加式, 不覆盖）。

(自 review.py 原样拆出: 函数逐行搬运, 行为零改动; 复盘口径注释保留在各函数处。)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..paths import GAMES_DIR, LESSONS_PATH
from .inputs import latest_run_dir
from .jev_review import ROOTCAUSE_CRITERIA, TOPFIX_CRITERIA
from .record import GameRecord

# ================= 输出 =================

def _fmt_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def write_review_md(rec: GameRecord, findings: list, answers: dict,
                    changes: list, game_no: int) -> Path:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    path = GAMES_DIR / ("game-%04d-review.md" % game_no)
    eco, curve, lk = rec.economy(), rec.army_curve(), rec.loss_kill()
    rc = (answers.get("rootcause") or {}).get("choice")
    fix = (answers.get("topfix") or {}).get("choice")
    lines = [
        "# 第 %d 局复盘 —— %s" % (game_no, _fmt_ts()),
        "",
        "- **结果**: %s（t=%s 游戏秒, %d ticks, 危机 %d ticks）" % (
            rec.outcome, rec.t_end, rec.report.get("ticks", 0) or 0,
            rec.report.get("crisis_ticks", 0) or 0),
        "- **开局建造**: %s" % (" → ".join("%s@%ds" % (n, t) for t, n in rec.build_order) or "无"),
        "- **首坦克**: t=%s | 敌基地: %s" % (
            rec.first_tank_t, "已定位" if rec.enemy_base else "未定位"),
        "- **经济**: 平均 %s / 峰值 %s / 见底率 %.0f%%" % (
            eco.get("avg"), eco.get("max"), (eco.get("starve_frac") or 0) * 100),
        "- **兵力**: 峰值我方 %s vs 敌 %s | 坦克峰值 %s(重坦口径) | 损失 %d / 可见击杀 %d" % (
            curve.get("my_val_peak"), curve.get("en_val_peak"), curve.get("tanks_peak"),
            lk["losses"], lk["kills_visible"]),
        "- **终局构成**: 重坦 %s / 防空车 %s / 步兵 %s" % (
            (curve.get("death_comp") or {}).get("armor", "—"),
            (curve.get("death_comp") or {}).get("aav", "—"),
            (curve.get("death_comp") or {}).get("inf", "—")),
        "- **态势分布**: %s | ALARM %d（反击 %d / TURTLE %d）| 停摆 %d" % (
            rec.stance_distribution(), len(rec.alarms), len(rec.counters),
            len(rec.turtles), len(rec.stalls)),
        "- **Jev**: %d 次决策, %d 错误, P50 %sms / P95 %sms, 态势变更 %d 次" % (
            rec.report.get("jev", {}).get("decisions", 0),
            rec.report.get("jev", {}).get("errors", 0),
            rec.report.get("jev", {}).get("p50_ms"), rec.report.get("jev", {}).get("p95_ms"),
            len(rec.stance_changes)),
        "",
        "## 确定性发现",
        "",
        "\n".join("- [%s] %s" % (sev, txt) for sev, txt, _ in findings) or "- 无",
        "",
        "## Jev 复盘",
        "",
        "- **根因**: %s — %s（置信 %.2f）" % (
            rc, ROOTCAUSE_CRITERIA.get(rc, "?"),
            (answers.get("rootcause") or {}).get("confidence", -1)),
        "- **下局优先**: %s — %s（置信 %.2f）" % (
            fix, TOPFIX_CRITERIA.get(fix, "?"),
            (answers.get("topfix") or {}).get("confidence", -1)),
        "- **调参支持度**: %s" % ((answers.get("tune") or {}).get("noul")),
        "",
        "## 参数迭代（自动, 白名单+限幅）",
        "",
        "\n".join("- `%s`: %s → %s" % (c["key"], c["from"], c["to"]) for c in changes) or "- 无",
        "",
        "## 待办改进（人工/下个 session）",
        "",
        "- [ ] 按上表核对下局验证点",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 事件切片留档
    (GAMES_DIR / ("game-%04d-events.jsonl" % game_no)).write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in rec.events) + "\n",
        encoding="utf-8")
    return path


def append_lessons(rec: GameRecord, findings: list, answers: dict,
                   changes: list, game_no: int, review_path: Path) -> None:
    rc = (answers.get("rootcause") or {}).get("choice")
    fix = (answers.get("topfix") or {}).get("choice")
    entry = [
        "",
        "## 第 %d 局 —— %s | %s | t=%s | 详见 %s" % (
            game_no, _fmt_ts(), rec.outcome, rec.t_end, review_path.name),
        "",
        "- **教训**: %s" % "；".join(txt for _, txt, _ in findings[:4]) or "-（无确定性发现）",
        "- **根因(Jev)**: %s | **下局优先**: %s" % (
            ROOTCAUSE_CRITERIA.get(rc, rc), TOPFIX_CRITERIA.get(fix, fix)),
    ]
    if changes:
        entry.append("- **已自动调参**: " + "；".join(
            "`%s` %s→%s" % (c["key"], c["from"], c["to"]) for c in changes))
    entry.append("- **待验证**: 下局检验上述调参与改进是否生效")
    with open(LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")


def link_run_dir(game_no: int, review_path: Path) -> None:
    """[训练数据管道] 在最新 run 目录落 game.json：局号 ↔ run 目录 链接。

    局号在复盘时才确定（run 目录创建于开局），因此由复盘侧写回；
    scripts/build_dataset.py 依此把新局增量并入 dataset/。
    链接只是训练数据管道的辅助件，写失败不阻断复盘。
    """
    try:
        run_dir = latest_run_dir()
        if not run_dir:
            return
        (run_dir / "game.json").write_text(json.dumps(
            {"game_no": game_no, "review": review_path.name,
             "linked_ts": time.strftime("%Y-%m-%d %H:%M:%S")},
            ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
