# -*- coding: utf-8 -*-
"""复盘数据采集: 取最后一段对局的事件流与行日志。

数据源优先级: 最新 run 目录的 events.jsonl(每局完整镜像) > 全局 jev-events.jsonl 切片。
(自 review.py 原样拆出: 函数逐行搬运, 行为零改动; 复盘口径注释保留在各函数处。)
"""
from __future__ import annotations

import json
from pathlib import Path

from ..paths import GAMES_DIR, LOG_DIR

# ================= 数据采集 =================

def latest_run_dir():
    """[训练数据] 最新的 run 目录（每局独立存档）。"""
    runs = GAMES_DIR.glob("run-*/events.jsonl")
    try:
        return max(runs, key=lambda p: p.stat().st_mtime).parent
    except ValueError:
        return None


def slice_events() -> list:
    """取最后一段对局的 jsonl 事件。

    优先读最新 run 目录的 events.jsonl（训练数据镜像, 单局完整）;
    无 run 目录时回退到全局 jev-events.jsonl 切片（最后一个 start 之后）。
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
    """取最后一段对局的 bot.log 行（最后一个 start banner 之后）。"""
    path = log_path or (LOG_DIR / "bot.log")
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=== ra2web-jev-player start" in line:
                lines = []
            lines.append(line.rstrip("\n"))
    return lines

