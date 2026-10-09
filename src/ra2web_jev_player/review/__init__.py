# -*- coding: utf-8 -*-
"""Review engine (package) -- the "record -> analyze -> summarize -> iterate" leg of the
learning loop.

The loop: live play (game.py) -> per-event audit (audit.py) -> review by this package ->
  1) artifacts/games/game-XXXX-review.md  full per-game review report
  2) docs/LESSONS.md                      lessons ledger (append-only, human/agent readable)
  3) docs/knowledge/doctrine.json         parameter overrides (whitelist + clamps + Jev
                                          confidence gate, git-auditable)
-> the next game loads the override values into doctrine.T (doctrine.load_overrides), and the
new game validates them.

Review has two layers (METHODOLOGY principle):
- Deterministic analysis (analyze.py): opening timeline vs. playbook windows, economy/army
  curves, stance distribution, crisis response, loss exchange ratio, error fingerprints --
  anything computable in code is never handed to the model;
- Jev semantic review (jev_review.py, TypeSafe): defeat-cause classification, top-priority
  improvement, whether auto-tuning is worthwhile.

Submodules: inputs (data collection) - record (structured record) - analyze (deterministic
analysis) - jev_review (semantic review) - tuning (parameter tuning) - emit (output) -
this file (entry point).
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
    """Review the last game segment (the last start -> report in the run directory's
    events.jsonl / jev-events.jsonl).

    Returns {game_no, outcome, findings, answers, changes, review_path}.
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
