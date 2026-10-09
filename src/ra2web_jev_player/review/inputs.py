# -*- coding: utf-8 -*-
"""Review data collection: fetch the event stream and line log of the last game segment.

Data source priority: the newest run directory's events.jsonl (complete per-game mirror) >
a slice of the global jev-events.jsonl.
(Extracted verbatim from review.py: functions moved line by line, behavior unchanged; the
review conventions comments are kept at each function.)
"""
from __future__ import annotations

import json
from pathlib import Path

from ..paths import GAMES_DIR, LOG_DIR

# ================= 数据采集 =================

def latest_run_dir():
    """[training data] Newest run directory (per-game standalone archive)."""
    runs = GAMES_DIR.glob("run-*/events.jsonl")
    try:
        return max(runs, key=lambda p: p.stat().st_mtime).parent
    except ValueError:
        return None


def slice_events() -> list:
    """Fetch the jsonl events of the last game segment.

    Prefers the newest run directory's events.jsonl (training-data mirror, complete for a
    single game); falls back to a slice of the global jev-events.jsonl (everything after the
    last "start") when there is no run directory.
    """
    run_dir = latest_run_dir()
    if run_dir:
        path = run_dir / "events.jsonl"
        events = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if events:
            return events
    path = LOG_DIR / "jev-events.jsonl"
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("kind") == "start":
            return events[i:]
    return events


def slice_botlog(log_path: Path | None = None) -> list:
    """Fetch the last game segment's bot.log lines (after the last start banner)."""
    path = log_path or (LOG_DIR / "bot.log")
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=== ra2web-jev-player start" in line:
                lines = []
            lines.append(line.rstrip("\n"))
    return lines

