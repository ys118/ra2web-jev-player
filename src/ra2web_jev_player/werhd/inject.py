# -*- coding: utf-8 -*-
"""In-page client injector: injects client.js into the game page (attached as window.__rj) and provides the
Python-side proxy.

Injection goes through `agent-browser eval --stdin` (client.js is ~15KB, over cmd.exe's 8191-character
argv limit, so `eval -b` cannot carry it). All later scattered calls are small expressions and go through
`eval -b`.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..driver.browser import Browser, BrowserError

CLIENT_PATH = Path(__file__).with_name("client.js")


class WerhdClient:
    """Python-side proxy for the in-page __rj client (thin wrapper)."""

    def __init__(self, browser: Browser):
        self.b = browser
        self.version = None

    # ---------- 生命周期 ----------

    def inject(self, timeout: float = 90, retries: int = 3) -> dict:
        """Inject client.js and verify that __rj exists. Must be called while a match is in progress.

        While page navigation/reload is in progress an eval may land on the old page or in a gap; retry
        when verification fails.
        """
        src = CLIENT_PATH.read_text(encoding="utf-8")
        last = None
        for i in range(retries):
            self.b.eval_stdin(src, timeout=timeout)
            kind = self.b.eval("typeof window.__rj")
            if kind == "object":
                self.version = self.call("window.__rj.version")
                return {"version": self.version}
            last = kind
            time.sleep(1.0)
        raise BrowserError("注入后未找到 window.__rj (typeof=%r)——页面是否在对局中？" % (last,))

    def has_battle(self) -> bool:
        try:
            return self.b.eval("typeof window.werhd === 'object' && !!window.werhd") is True
        except BrowserError:
            return False

    # ---------- 通用调用 ----------

    def call(self, expr: str, timeout: float | None = None):
        """Evaluate an expression on __rj and return the restored Python value.

        No extra JSON.stringify wrapper is needed: agent-browser's eval itself prints
        JSON.stringify(expression value), and b.eval already restores it uniformly.
        """
        return self.b.eval(expr, timeout=timeout)

    # ---------- 状态 ----------

    def snapshot(self, timeout: float | None = None) -> dict:
        data = self.call("__rj.snapshot()", timeout=timeout or self.b.cfg.eval_timeout_s + 5)
        if isinstance(data, str):                     # 兜底：老通道可能返回 JSON 文本
            data = json.loads(data)
        return data

    def status(self) -> dict:
        return self.call("__rj.status()") or {}

    # ---------- 指令（经页内节流封装） ----------

    def attack_move(self, ids, x, y):
        return self.call("__rj.o.attackMove(%s,%d,%d)" % (json.dumps(ids), x, y))

    def move(self, ids, x, y):
        return self.call("__rj.o.move(%s,%d,%d)" % (json.dumps(ids), x, y))

    def attack(self, ids, enemy_id):
        return self.call("__rj.o.attack(%s,%d)" % (json.dumps(ids), enemy_id))

    def deploy(self, ids):
        return self.call("__rj.o.deploy(%s)" % json.dumps(ids))

    def produce(self, name, qty=1):
        return self.call("__rj.o.produce(%s,%d)" % (json.dumps(name), qty))

    def can_place(self, name, x, y):
        """[game 100] Can-build check at a given tile (used to pre-position buildings facing the enemy)."""
        return self.call("__rj.o.canPlace(%s,%d,%d)" % (json.dumps(name), x, y))

    def place(self, name, x, y):
        """[game 100] Place a building at a given tile (replaces automatic placement)."""
        return self.call("__rj.o.place(%s,%d,%d)" % (json.dumps(name), x, y))

    def micro_start(self, rally=None, camera=True, cfg=None):
        args = []
        if cfg:
            args.append("cfg:%s" % json.dumps(cfg))
        if rally:
            args.append("rally:{x:%d,y:%d}" % (rally[0], rally[1]))
        args.append("camera:%s" % ("true" if camera else "false"))
        return self.call("__rj.micro.start({%s})" % ",".join(args))

    def micro_stop(self):
        return self.call("__rj.micro.stop()")

    def set_rally(self, x=None, y=None, label=""):
        return self.call("__rj.setRally(%s,%s,%s)" % (
            "null" if x is None else str(x), "null" if y is None else str(y), json.dumps(label)))

    def set_enemy_base(self, x=None, y=None):
        return self.call("__rj.setEnemyBase(%s,%s)" % (
            "null" if x is None else str(x), "null" if y is None else str(y)))
