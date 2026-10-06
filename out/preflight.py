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

# [95局事故] agent-browser 自带 Chrome WebGL 丧失 → 全部调用统一走系统 Chrome
# (与 src browser.py 的 RA2WEB_CHROME_PATH 逻辑一致; daemon 按 session 复用,
#  必须在首次 open 前设好, 否则会拉起坏 daemon 毒化后续 launcher)
_CHROME = os.environ.get(
    "RA2WEB_CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe")
if os.path.isfile(_CHROME):
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
    """[95局事故] 浏览器 WebGL 前置检查: agent-browser 自带 Chrome 突发
    WebGL 丧失时, launcher 会在'主选单未出现'上白耗 3 轮——这里提前拦截
    并给出可行动修复(切系统 Chrome RA2WEB_CHROME_PATH)。"""
    ab(["open", "about:blank"], timeout=90)
    time.sleep(3)
    r = ab(["eval", _WEBGL_JS], timeout=45)
    ab(["close"], timeout=45)
    ok = "WEBGL-OK" in r
    print("[preflight] webgl: %s" % ("OK" if ok else
          "LOST (95局事故形态; 修复=设 RA2WEB_CHROME_PATH 指向系统 Chrome 或重装 agent-browser)"))
    return ok


def step_site():
    for i in (1, 2):
        p = subprocess.run([sys.executable, "out/site_probe.py"],
                           capture_output=True, timeout=240)
        if p.returncode == 0:
            print("[preflight] site: OK (attempt %d)" % i)
            return True
        print("[preflight] site: down (attempt %d), wait 90s retry" % i)
        time.sleep(90)
    print("[preflight] site: STILL DOWN after 2 attempts")
    return False


if __name__ == "__main__":
    ok = step_clef() and step_stale_session() and step_webgl() and step_site()
    print("[preflight] %s" % ("READY" if ok else "BLOCKED"))
    sys.exit(0 if ok else 1)
