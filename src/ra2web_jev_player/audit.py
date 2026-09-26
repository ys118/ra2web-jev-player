# -*- coding: utf-8 -*-
"""审计：logs/bot.log 行日志 + logs/jev-events.jsonl 逐事件审计。

沿用既有日志格式（legacy_bot 的 bot.log 行格式、官方体系时代的 jev-events.jsonl
事件格式），保证历史工具与复盘流程继续可用。无任何网络组件。
"""
from __future__ import annotations

import json
import os
import threading
import time

from .paths import LOG_DIR

# 值得在控制台回显的事件种类（其余只落盘）
ECHO_KINDS = {"action", "outcome", "place", "micro", "start", "stop", "stale",
              "error", "battle", "report"}


class Audit:
    def __init__(self, log_dir=None, echo: bool = True):
        self.dir = str(log_dir or LOG_DIR)
        os.makedirs(self.dir, exist_ok=True)
        self.echo = echo
        self._lock = threading.Lock()
        self._bot = open(os.path.join(self.dir, "bot.log"), "a", buffering=1, encoding="utf-8")
        self._events = open(os.path.join(self.dir, "jev-events.jsonl"), "a",
                            buffering=1, encoding="utf-8")

    def log(self, msg: str) -> None:
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
        with self._lock:
            self._bot.write(line + "\n")
        if self.echo:
            print(line, flush=True)

    def event(self, ev: dict) -> None:
        ev = dict(ev)
        ev.setdefault("ts", time.strftime("%H:%M:%S"))
        line = json.dumps(ev, ensure_ascii=False)
        with self._lock:
            self._events.write(line + "\n")
        if self.echo and ev.get("kind") in ECHO_KINDS:
            print("[%s] %s" % (ev["ts"], line[:300]), flush=True)

    def close(self) -> None:
        with self._lock:
            try:
                self._bot.close()
            finally:
                self._events.close()
