# -*- coding: utf-8 -*-
"""复盘引擎(包) —— 学习闭环的"记录→分析→总结→迭代"段。

闭环：实战(game.py) → 逐事件审计(audit.py) → 本包复盘 →
  ① artifacts/games/game-XXXX-review.md  每局完整复盘报告
  ② docs/LESSONS.md                      经验账本（追加式，人/agent 可读）
  ③ docs/knowledge/doctrine.json         参数覆盖（白名单+限幅+Jev 置信闸门，git 可审计）
→ 下一局 doctrine.T 加载覆盖值（doctrine.load_overrides），新局验证。

复盘分两层（METHODOLOGY 原则）：
- 确定性分析（analyze.py）：开局时序 vs 手册窗口、经济/兵力曲线、态势分布、
  危机响应、损失交换比、错误指纹——能用代码算的绝不给模型；
- Jev 语义复盘（jev_review.py，TypeSafe）：败因归类、最优先改进项、是否值得自动调参。

子模块: inputs(数据采集) · record(结构化记录) · analyze(确定性分析) ·
jev_review(语义复盘) · tuning(参数微调) · emit(产出) · 本文件(入口)。
"""
from __future__ import annotations

import re
from pathlib import Path

from ..audit import Audit
from ..jev import JevClient
from ..paths import GAMES_DIR
from .analyze import BUILD_WINDOWS, analyze
from .emit import append_lessons, link_run_dir, write_review_md
from .inputs import latest_run_dir, slice_botlog, slice_events
from .jev_review import ROOTCAUSE_CRITERIA, TOPFIX_CRITERIA, jev_review, summary_text
from .record import GameRecord
from .tuning import TUNING_RULES, auto_tune

__all__ = [
    "GameRecord", "analyze", "summary_text", "jev_review", "auto_tune",
    "write_review_md", "append_lessons", "link_run_dir", "latest_run_dir",
    "slice_events", "slice_botlog", "next_game_number", "review_last_game",
    "BUILD_WINDOWS", "TUNING_RULES", "ROOTCAUSE_CRITERIA", "TOPFIX_CRITERIA",
]

SEED_GAMES = 23            # 第 1-23 局记录在历史日志/报告中（本闭环上线前）


# ================= 入口 =================

def next_game_number() -> int:
    if GAMES_DIR.exists():
        nums = [int(m.group(1)) for p in GAMES_DIR.glob("game-*-review.md")
                if (m := re.match(r"game-(\d+)-review\.md", p.name))]
        if nums:
            return max(nums) + 1
    return SEED_GAMES + 1


def review_last_game(jev: JevClient, audit: Audit | None = None,
                     game_no: int | None = None,
                     log_path: Path | None = None) -> dict:
    """复盘最后一段对局（ run 目录 events.jsonl / jev-events.jsonl 最后一个 start → report）。

    返回 {game_no, outcome, findings, answers, changes, review_path}。
    """
    audit = audit or Audit(echo=False)
    game_no = game_no or next_game_number()
    rec = GameRecord(slice_events(), slice_botlog(log_path))
    if not rec.events:
        return {"game_no": game_no, "skipped": "no events"}
    findings = analyze(rec)
    answers, changes = {}, []
    try:
        answers = jev_review(rec, findings, jev)
        rc = (answers.get("rootcause") or {}).get("choice") or "other"
        tune = (answers.get("tune") or {}).get("noul") or 0
        changes = auto_tune(rc, tune if isinstance(tune, (int, float)) else 0,
                            game_no, "Jev复盘: %s" % rc)
    except Exception as e:
        if audit:
            audit.log("review jev ERR %s" % str(e)[:150])
    review_path = write_review_md(rec, findings, answers, changes, game_no)
    append_lessons(rec, findings, answers, changes, game_no, review_path)
    # [训练数据管道] 在 run 目录落 game.json 链接(局号↔run 目录), 供
    # scripts/build_dataset.py 把新局增量并入 dataset/（局号在复盘时才确定）
    link_run_dir(game_no, review_path)
    if audit:
        audit.log("REVIEW game#%d %s → %s | changes=%d"
                  % (game_no, rec.outcome, review_path.name, len(changes)))
    return {"game_no": game_no, "outcome": rec.outcome, "findings": findings,
            "answers": answers, "changes": changes, "review_path": str(review_path)}
