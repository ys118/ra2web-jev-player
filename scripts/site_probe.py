# -*- coding: utf-8 -*-
"""站点恢复探测(单次): 弹窗点掉 + 检查主选单是否渲染。exit 0=恢复, 1=未恢复。"""
import subprocess
import sys
import time

AB = ["C:/Program Files/nodejs/agent-browser.cmd", "--session", "ra2web"]


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
