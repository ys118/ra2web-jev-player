# -*- coding: utf-8 -*-
"""Single-shot site recovery probe: dismiss dialogs + check whether the main menu rendered.
exit 0 = recovered, 1 = not recovered."""
import os
import shutil
import subprocess
import sys
import time


def _agent_browser():
    """agent-browser CLI path: env AGENT_BROWSER_CMD wins, else PATH."""
    env = os.environ.get("AGENT_BROWSER_CMD")
    if env:
        return env
    for name in ("agent-browser", "agent-browser.cmd", "agent-browser.exe"):
        found = shutil.which(name)
        if found:
            return found
    return "agent-browser"


AB = [_agent_browser(), "--session", os.environ.get("RA2WEB_SESSION", "ra2web")]


def run(args, timeout=90):
    p = subprocess.Popen(AB + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=timeout)
        return out.decode("utf-8", "replace").strip(), err.decode("utf-8", "replace").strip()[:150]
    except subprocess.TimeoutExpired:
        p.kill()
        return "TIMEOUT", ""


o, _ = run(["open", "https://gonghui.k0s.cn/"], timeout=100)
time.sleep(12)
for _ in range(6):                      # 最多 60s: 点弹窗 + 等菜单
    o, _ = run(["eval", "(function(){if(document.body.innerText.indexOf('单机模式')>=0) return 'MENU-OK';"
                        "var b=[...document.querySelectorAll('button')].filter(function(x){"
                        "return x.innerText.trim()=='确定'});"
                        "if(b.length){b[b.length-1].click();return 'dismissed'}"
                        "return 'blank:'+document.body.innerText.length})()"])
    if "MENU-OK" in o:
        print("SITE_OK")
        sys.exit(0)
    time.sleep(10)
print("SITE_DOWN:", o[:60])
sys.exit(1)
