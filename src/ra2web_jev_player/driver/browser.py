# -*- coding: utf-8 -*-
"""agent-browser CLI wrapper -- the single channel for browser driving.

Measured on this machine (details in docs/ENGINEERING-NOTES.md §4):
- the `.cmd` shim goes through cmd.exe: keep all arguments ASCII; use `eval -b <base64>` for complex JS
  (the transport method recommended by the agent-browser docs);
- Popen MUST use `stdin=DEVNULL` (inheriting stdin hangs forever); on timeout, `taskkill /T /F` kills the
  whole process tree;
- each named session has a resident daemon, so the browser survives across commands; `--idle-timeout 0`
  (env AGENT_BROWSER_IDLE_TIMEOUT_MS) keeps a long game from being auto-closed by the 1h idle timeout;
- `--restore` (env AGENT_BROWSER_RESTORE) persists cookies/localStorage to disk and restores them before
  the next navigation.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from urllib.parse import urlparse


def resolve_agent_browser() -> str:
    """Locate the agent-browser CLI: env AGENT_BROWSER_CMD wins, else PATH lookup.

    Windows ships it as a .cmd shim, which CreateProcess cannot launch by bare
    name, so PATH lookup must go through shutil.which (which honours PATHEXT).
    """
    env = os.environ.get("AGENT_BROWSER_CMD")
    if env:
        return env
    for name in ("agent-browser", "agent-browser.cmd", "agent-browser.exe"):
        found = shutil.which(name)
        if found:
            return found
    return "agent-browser"          # not installed: let the OS error surface


AGENT_BROWSER = resolve_agent_browser()


class BrowserError(RuntimeError):
    """An agent-browser command failed or hung."""


def agent_browser_version() -> str:
    p = subprocess.Popen([AGENT_BROWSER, "--version"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate(timeout=15)
    return (out or b"").decode("utf-8", "replace").strip()


class Browser:
    """Browser channel for one named session. All methods are thread-unsafe (used from a single loop)."""

    def __init__(self, config=None):
        from ..config import DriverConfig
        self.cfg = config or DriverConfig()
        # [95局事故] agent-browser 自带 Chrome 151.0.7922.77 突发 WebGL 丧失+
        # headless 挂死(升级残留损坏); `agent-browser install` 重装为 155 后
        # 自带浏览器 WebGL 正常(真 GPU RTX 4060 Ti)——**终态=用自家浏览器,
        # 不依赖系统 Chrome**。环境变量 RA2WEB_CHROME_PATH 仍可显式指定
        # executable(应急), 未设则用 agent-browser 自带的。
        _chrome = os.environ.get("RA2WEB_CHROME_PATH", "")
        _env_exec = {"AGENT_BROWSER_EXECUTABLE_PATH": _chrome} \
            if _chrome and os.path.isfile(_chrome) else {}
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
                         AGENT_BROWSER_ARGS=self.cfg.chrome_args,
                         **_env_exec)

    # 启动参数只在浏览器冷启动时生效；改过之后需要 agent-browser close 再重启会话
    DEFAULT_CHROME_ARGS = ("--disable-background-timer-throttling,"
                           "--disable-backgrounding-occluded-windows")

    # ---------- 底层 ----------

    def run(self, *args: str, timeout: float | None = None, check: bool = True) -> str:
        """Run one agent-browser command and return its stdout text.

        Popen occasionally raises WinError 2 (measured in game 28: it healed after 15 consecutive
        failures) -> retry once.
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
        """Only start the browser (it stops at about:blank, no navigation). The first cold start can take
        tens of seconds."""
        return self.run("open", timeout=timeout, check=False)

    def goto(self, url: str, deadline_s: float = 45, force: bool = False) -> dict:
        """Navigate via eval + self-polled readyState.

        `open <url>` is not used: it waits for the window load event, and under a fresh profile blocked
        third-party resources push load out to the external-network timeout (measured on this machine:
        2+ minutes without returning).
        Polling accepts interactive/complete (an SPA never reaches complete, so it is let through at
        timeout). force=True reloads even for the same URL (abandons the match in progress and returns
        to the main menu).
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
        """Wait until the JS expression becomes true."""
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
        """Evaluate a JS expression and return the raw stdout."""
        b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
        return self.run("eval", "-b", b64, timeout=timeout or self.cfg.eval_timeout_s + 5)

    def eval_stdin(self, code: str, timeout: float | None = None) -> str:
        """Large JS is transported over stdin (`eval --stdin`) -- cmd.exe has an 8191-character argv
        limit, so injecting the whole in-page client must go through this channel."""
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
        """Evaluate a JS expression and return a Python object.

        Contract (measured): agent-browser always prints `JSON.stringify(expression value)` -- strings
        come back quoted and objects come back as JSON text. This uniformly restores the original value
        with a single json.loads; callers that JSON.stringify again themselves (such as call()) receive
        the inner JSON string.
        """
        text = self.eval_raw(code, timeout=timeout)
        if not text or text in ("null", "undefined"):
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text                   # 兜底返回原文（多行输出等）

    def eval_json(self, js_body: str, timeout: float | None = None):
        """Convenience helper: wrap JS statements in an IIFE, JSON.stringify the result, then eval."""
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
