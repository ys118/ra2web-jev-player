# -*- coding: utf-8 -*-
"""agent-browser CLI 封装 —— 浏览器驱动的唯一通道。

本机实测要点（详见 docs/ENGINEERING-NOTES.md §四）：
- `.cmd` shim 走 cmd.exe：参数一律 ASCII；复杂 JS 用 `eval -b <base64>`（agent-browser
  官方文档推荐的传输方式）；
- Popen 必须 `stdin=DEVNULL`（继承 stdin 会永久挂死）；超时后 `taskkill /T /F` 连树强杀；
- 每个命名 session 一个常驻 daemon，浏览器跨命令存活；`--idle-timeout 0`（env
  AGENT_BROWSER_IDLE_TIMEOUT_MS）防止长局被 1h 空闲超时自动关闭；
- `--restore`（env AGENT_BROWSER_RESTORE）把 cookie/localStorage 落盘并在下次导航前恢复。
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from urllib.parse import urlparse

AGENT_BROWSER = os.environ.get("AGENT_BROWSER_CMD",
                               "C:/Program Files/nodejs/agent-browser.cmd")


class BrowserError(RuntimeError):
    """agent-browser 命令失败或挂死。"""


def agent_browser_version() -> str:
    p = subprocess.Popen([AGENT_BROWSER, "--version"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate(timeout=15)
    return (out or b"").decode("utf-8", "replace").strip()


class Browser:
    """一个命名 session 的浏览器通道。所有方法线程不安全（单线程循环使用）。"""

    def __init__(self, config=None):
        from ..config import DriverConfig
        self.cfg = config or DriverConfig()
        self._env = dict(os.environ,
                         AGENT_BROWSER_SESSION=self.cfg.session,
                         AGENT_BROWSER_RESTORE=self.cfg.restore,
                         # [第47局] headless 显式覆盖全局 config 的 "headed": true——
                         # 有头窗口在本机会被持续最小化/还原折腾, eval 间歇挂死;
                         # 无头页面默认 visible, 长局托管最可靠（ENGINEERING-NOTES §3.1）
                         AGENT_BROWSER_HEADED="false",
                         AGENT_BROWSER_IDLE_TIMEOUT_MS="0",
                         AGENT_BROWSER_DEFAULT_TIMEOUT=str(self.cfg.default_timeout_ms),
                         # headless 页面默认会被 Chrome 做 setTimeout 节流(~1s/次)，
                         # 微操 150ms 循环必须禁掉；对 rAF 无效，但 headless 页面 rAF 本就正常
                         AGENT_BROWSER_ARGS=self.cfg.chrome_args)

    # 启动参数只在浏览器冷启动时生效；改过之后需要 agent-browser close 再重启会话
    DEFAULT_CHROME_ARGS = ("--disable-background-timer-throttling,"
                           "--disable-backgrounding-occluded-windows")

    # ---------- 底层 ----------

    def run(self, *args: str, timeout: float | None = None, check: bool = True) -> str:
        """执行一条 agent-browser 命令，返回 stdout 文本。

        Popen 偶发 WinError 2（第 28 局实测 15 连发后自愈）→ 重试一次。
        """
        timeout = timeout or self.cfg.default_timeout_ms / 1000.0 + 5
        argv = [AGENT_BROWSER] + [str(a) for a in args]
        p = None
        for attempt in range(2):
            try:
                p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=self._env)
                break
            except OSError:
                if attempt:
                    raise
                time.sleep(0.5)
        try:
            out, errb = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
            raise BrowserError("agent-browser hang: %s (killed tree)" % " ".join(args[:3]))
        text = (out or b"").decode("utf-8", "replace").strip()
        err = (errb or b"").decode("utf-8", "replace").strip()
        if check and p.returncode != 0:
            raise BrowserError("agent-browser[%s] rc=%d: %s"
                               % (args[0] if args else "?", p.returncode, err[:300]))
        return text

    # ---------- 页面生命周期 ----------

    def launch(self, timeout: float = 120) -> str:
        """只启动浏览器（停在 about:blank，不导航）。首次冷启动可能要几十秒。"""
        return self.run("open", timeout=timeout, check=False)

    def goto(self, url: str, deadline_s: float = 45, force: bool = False) -> dict:
        """eval 导航 + 自轮询 readyState。

        不用 `open <url>`：它会等 window load 事件，新 profile 下被墙的第三方
        资源会把 load 卡到外网超时（本机实测 2 分钟+ 不返回）。
        轮询接受 interactive/complete（SPA 永远等不到 complete 也放行到超时）。
        force=True 时同 URL 也强制重载（弃掉进行中的对局回到主选单）。
        """
        # setTimeout 延迟跳转：直接赋值 location.href 会触发导航，CLI 的 eval 会等
        # 页面稳定而卡死（同 open 的 load 等待问题）；延迟 50ms 让 eval 先返回。
        try:
            cur = self.eval("location.href", timeout=8)
        except BrowserError:
            self.launch()                      # 浏览器未起/会话刚关闭，冷启动可达 ~1min
            cur = self.eval("location.href", timeout=15)
        if isinstance(cur, str) and cur == url and not force:
            return {"ok": True, "elapsed_s": 0.0, "rs": "same-url", "u": cur}
        self.eval("setTimeout(()=>{location.href=%s},50)" % json.dumps(url))
        want = urlparse(url).netloc
        t0 = time.time()
        last = {}
        while time.time() - t0 < deadline_s:
            time.sleep(0.5)
            try:
                last = self.eval("JSON.stringify({rs:document.readyState,u:location.href})") or {}
            except BrowserError:
                continue                       # 导航中途页面销毁，下轮再试
            if isinstance(last, str):
                try:
                    last = json.loads(last)
                except json.JSONDecodeError:
                    last = {"raw": last}
            if last.get("rs") in ("interactive", "complete") and want in str(last.get("u", "")):
                return {"ok": True, "elapsed_s": round(time.time() - t0, 1), **last}
        return {"ok": False, "elapsed_s": round(time.time() - t0, 1), **last}

    def open(self, url: str) -> dict:
        self.launch()
        return self.goto(url)

    def wait(self, ms: float) -> str:
        return self.run("wait", ms)

    def wait_fn(self, js_expr: str, timeout_ms: int | None = None) -> str:
        """等待 JS 表达式为真。"""
        args = ["wait", "--fn", js_expr]
        if timeout_ms:
            args += ["--timeout", timeout_ms]
        return self.run(*args)

    def screenshot(self, path: str) -> str:
        return self.run("screenshot", path)

    def console_errors(self) -> str:
        return self.run("errors")

    def close(self) -> str:
        return self.run("close")

    # ---------- eval（游戏页指令/状态通道） ----------

    def eval_raw(self, code: str, timeout: float | None = None) -> str:
        """执行 JS 表达式，返回 stdout 原文。"""
        b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
        return self.run("eval", "-b", b64, timeout=timeout or self.cfg.eval_timeout_s + 5)

    def eval_stdin(self, code: str, timeout: float | None = None) -> str:
        """大段 JS 经 stdin（`eval --stdin`）传输——cmd.exe 有 8191 字符 argv 上限，
        注入整份页内客户端必须走这条通道。"""
        timeout = timeout or self.cfg.eval_timeout_s + 5
        p = subprocess.Popen([AGENT_BROWSER, "eval", "--stdin"], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._env)
        try:
            out, errb = p.communicate(input=code.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
            raise BrowserError("agent-browser eval --stdin hang (killed tree)")
        text = (out or b"").decode("utf-8", "replace").strip()
        err = (errb or b"").decode("utf-8", "replace").strip()
        if p.returncode != 0:
            raise BrowserError("eval --stdin rc=%d: %s" % (p.returncode, err[:300]))
        return text

    def eval(self, code: str, timeout: float | None = None):
        """执行 JS 表达式并返回 Python 对象。

        契约（实测）：agent-browser 总是打印 `JSON.stringify(表达式值)` ——
        字符串会带引号、对象是 JSON 文本。这里统一 json.loads 一次还原原值；
        调用方再自行 JSON.stringify 的（如 call()），拿到的是内层 JSON 字符串。
        """
        text = self.eval_raw(code, timeout=timeout)
        if not text or text in ("null", "undefined"):
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text                   # 兜底返回原文（多行输出等）

    def eval_json(self, js_body: str, timeout: float | None = None):
        """便捷封装：把 JS 语句包进 IIFE 并 JSON.stringify 后 eval。"""
        return self.eval("JSON.stringify((()=>{%s})())" % js_body, timeout=timeout)

    # ---------- UI 自动化（launcher 菜单状态机用） ----------

    def snapshot(self, interactive_only: bool = True) -> str:
        args = ["snapshot"]
        if interactive_only:
            args.append("-i")
        return self.run(*args)

    def click(self, ref: str) -> str:
        return self.run("click", ref)

    def fill(self, ref: str, text: str) -> str:
        return self.run("fill", ref, text)

    def press(self, key: str) -> str:
        return self.run("press", key)
