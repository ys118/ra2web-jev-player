# -*- coding: utf-8 -*-
"""启动前自检(第88局起固化, 2026-10-06 运维事故教训):
①clef-flash 本地决策服务健康 ②游戏 session 残留清理(会话级 close, 铁律允许)
③站点串行探测(必须无 launcher 并发, 87 局事故: probe 与 launcher 同 session
打架致 eval 挂死)。全部通过 exit 0, 否则 exit 1。
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # scripts/preflight.py -> 仓库根

# [95局事故] 自带 Chrome 151 损坏 → `agent-browser install` 重装 155 后自家
# 浏览器 WebGL 正常(终态=用自家浏览器, 不依赖系统 Chrome)。RA2WEB_CHROME_PATH
# 环境变量仍可应急指定 executable; daemon 按 session 复用, 任何 executable
# 覆盖必须在首次 open 前设好, 否则会拉起旧 daemon 毒化后续 launcher。
_CHROME = os.environ.get("RA2WEB_CHROME_PATH", "")
if _CHROME and os.path.isfile(_CHROME):
    os.environ["AGENT_BROWSER_EXECUTABLE_PATH"] = _CHROME

AB = ["C:/Program Files/nodejs/agent-browser.cmd", "--session", "ra2web"]


def ab(args, timeout=90):
    p = subprocess.Popen(AB + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, _ = p.communicate(timeout=timeout)
        return out.decode("utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        p.kill()
        return "TIMEOUT"


def step_clef():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8085/health", timeout=8) as r:
            ok = b"ok" in r.read(200).lower()
        print("[preflight] clef-flash: %s" % ("OK" if ok else "BAD-RESPONSE"))
        return ok
    except Exception as e:
        print("[preflight] clef-flash: DOWN (%s)" % e)
        return False


def step_stale_session():
    """残留会话清理: 只做会话级 close(不碰其他 session, 不按名杀进程)。"""
    r = ab(["close"], timeout=45)
    print("[preflight] stale session: %s" % ("clean" if "closed" in r.lower() or r else r[:40]))
    return True


_WEBGL_JS = ("(function(){var c=document.createElement('canvas');"
             "var g=c.getContext('webgl');"
             "if(!g) return 'NO-WEBGL';"
             "var d=g.getExtension('WEBGL_debug_renderer_info');"
             "return 'WEBGL-OK';})()")


def step_webgl():
    """[95局事故] 浏览器 WebGL 前置检查: 浏览器 WebGL 丧失时, launcher 会在
    '主选单未出现'上白耗 3 轮——这里提前拦截并给出可行动修复提示。"""
    # 注意: ①不用 open(47 局已知: open 等 window load 会卡死); ②不在 close
    # 后立即 eval(daemon 内浏览器重启路径会挂 150s, 95局排查实证)——直接对
    # 活着的浏览器 eval 探测, close 交给后面的 stale_session 步。
    r = ab(["eval", _WEBGL_JS], timeout=90)
    if "TIMEOUT" in r or not r:            # 无 daemon: 冷启动后重测一次
        r = ab(["eval", _WEBGL_JS], timeout=120)
    ok = "WEBGL-OK" in r
    print("[preflight] webgl: %s" % ("OK" if ok else
          "LOST (重装浏览器: agent-browser install; 或 RA2WEB_CHROME_PATH 指定可用 executable)"))
    return ok


def step_site():
    for i in (1, 2):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "site_probe.py")],
                           capture_output=True, timeout=240)
        if p.returncode == 0:
            print("[preflight] site: OK (attempt %d)" % i)
            return True
        print("[preflight] site: down (attempt %d), wait 90s retry" % i)
        time.sleep(90)
    print("[preflight] site: STILL DOWN after 2 attempts")
    return False


if __name__ == "__main__":
    # 顺序: webgl 探测必须在 stale_session(close) 之前——close 后立即 eval
    # 会踩 daemon 内浏览器重启挂死(95局排查实证)。
    ok = step_clef() and step_webgl() and step_stale_session() and step_site()
    print("[preflight] %s" % ("READY" if ok else "BLOCKED"))
    sys.exit(0 if ok else 1)
