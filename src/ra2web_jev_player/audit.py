# -*- coding: utf-8 -*-
"""Audit: artifacts/logs/bot.log line log + artifacts/logs/jev-events.jsonl per-event audit.

Keeps the existing log formats (legacy/bot.py's bot.log line format, the official-stack-era
jev-events.jsonl event format) so historical tools and the review flow keep working.
Contains no network component.
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
    def __init__(self, log_dir=None, echo: bool = True, mirror_path=None):
        self.dir = str(log_dir or LOG_DIR)
        os.makedirs(self.dir, exist_ok=True)
        self.echo = echo
        self._lock = threading.Lock()
        self._bot = open(os.path.join(self.dir, "bot.log"), "a", buffering=1, encoding="utf-8")
        self._events = open(os.path.join(self.dir, "jev-events.jsonl"), "a",
                            buffering=1, encoding="utf-8")
        self._mirror = open(mirror_path, "a", buffering=1, encoding="utf-8") \
            if mirror_path else None   # [训练数据] 每局独立镜像（run 目录）

    def attach_mirror(self, path) -> None:
        """Attach the per-game mirror file (run directory); log/event lines are dual-written."""
        with self._lock:
            if self._mirror:
                try:
                    self._mirror.close()
                except OSError:
                    pass
            self._mirror = open(path, "a", buffering=1, encoding="utf-8")

    def log(self, msg: str) -> None:
        """[training data] Text line logs go only to the global bot.log -- the run mirror stays
        pure jsonl (game 45: mixed writes made events.jsonl unparsable)."""
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
            if self._mirror:
                self._mirror.write(line + "\n")
        if self.echo and ev.get("kind") in ECHO_KINDS:
            print("[%s] %s" % (ev["ts"], line[:300]), flush=True)

    def close(self) -> None:
        with self._lock:
            try:
                self._bot.close()
            finally:
                self._events.close()
                if self._mirror:
                    self._mirror.close()
