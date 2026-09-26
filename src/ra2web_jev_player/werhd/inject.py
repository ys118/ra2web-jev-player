# -*- coding: utf-8 -*-
"""页内客户端注入器：把 client.js 注入游戏页（挂 window.__rj）并提供 Python 侧代理。

注入走 `agent-browser eval --stdin`（client.js ~15KB，超过 cmd.exe 8191 字符
argv 上限，`eval -b` 装不下）。之后的零散调用都是小表达式，走 `eval -b`。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..driver.browser import Browser, BrowserError

CLIENT_PATH = Path(__file__).with_name("client.js")


class WerhdClient:
    """页内 __rj 客户端的 Python 侧代理（thin wrapper）。"""

    def __init__(self, browser: Browser):
        self.b = browser
        self.version = None

    # ---------- 生命周期 ----------

    def inject(self, timeout: float = 90, retries: int = 3) -> dict:
        """注入 client.js 并验证 __rj 存在。必须在对局进行中调用。

        页面导航/重载进行中 eval 可能落到旧页或空档，验证失败时重试。
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
        """求值 __rj 上的表达式并返回还原后的 Python 值。

        不需要再包 JSON.stringify：agent-browser 的 eval 本身就打印
        JSON.stringify(表达式值)，b.eval 已统一还原。
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
