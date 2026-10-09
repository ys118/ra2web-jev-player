# -*- coding: utf-8 -*-
"""审计：artifacts/logs/bot.log 行日志 + artifacts/logs/jev-events.jsonl 逐事件审计。

沿用既有日志格式（legacy/bot.py 的 bot.log 行格式、官方体系时代的 jev-events.jsonl
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
        """挂载每局独立镜像文件（run 目录），log/event 双写。"""
        with self._lock:
            if self._mirror:
                try:
                    self._mirror.close()
                except OSError:
                    pass
            self._mirror = open(path, "a", buffering=1, encoding="utf-8")

    def log(self, msg: str) -> None:
        """[训练数据] 文本行日志只进全局 bot.log——run 镜像保持纯 jsonl
        （第 45 局: 混写导致 events.jsonl 无法解析）。"""
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
