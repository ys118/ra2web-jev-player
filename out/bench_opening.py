# -*- coding: utf-8 -*-
"""[第67局前引擎微基准] 精炼厂先行链实测(当前引擎):
  Q1 无电厂时 NAREFN 是否可造(prereq POWER 的真实判定)?
  Q2 NAREFN→NAHAND→NAWEAP 各建筑实际建造时长(对比第66局电厂先行链)?
  Q3 低电力(isLowPower)是否拖慢建造/生产?
只做基准不托管对战, 结束关浏览器。"""
import json
import sys
import time

sys.path.insert(0, r"D:\projects\ra2web-jev-player\src")
from ra2web_jev_player.config import DriverConfig, MatchConfig
from ra2web_jev_player.driver.browser import Browser
from ra2web_jev_player.driver.launcher import GameLauncher


def av0(s):
    v = (s.get("av") or {})
    return v.get(0) or v.get("0") or []


def qstate(s):
    for q in s.get("queues") or []:
        if q.get("t") == 0:
            st = {0: "idle", 1: "building", 2: "paused", 3: "READY"}.get(q.get("s"), "?")
            its = ",".join("%s%%%d" % (i["n"], i["p"]) for i in q.get("items", [])) or "-"
            return "%s[%s]" % (st, its)
    return "none"


def poll(c, cond, timeout=240, tag=""):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        s = c.snapshot()
        if s and not s.get("dead") and "t" in s:
            last = s
            if cond(s):
                return s
        time.sleep(1.2)
    return last


def main():
    match = MatchConfig(speed=6, credits=10000)
    b = Browser(DriverConfig(headed=False))
    try:
        c = GameLauncher(b, match).launch()
        print("[bench] launched")
        # 等基地车落成(有 NACNST)
        s = poll(c, lambda s: any(u["n"] == "NACNST" for u in s.get("mine", [])),
                 timeout=180, tag="yard")
        if not s:
            print("[bench] FATAL yard never appeared"); return 1
        t0 = s["t"]
        print("[bench] yard@t=%s av0=%s" % (t0, av0(s)))
        print("[bench] power: %s" % json.dumps(s["me"]["power"]))
        c.micro_start()

        res = {}
        for name in ("NAREFN", "NAHAND", "NAWEAP"):
            s = c.snapshot()
            avail = name in av0(s)
            c.produce(name, 1)
            time.sleep(1.0)
            s2 = c.snapshot()
            accepted = name in qstate(s2) or qstate(s2).startswith(("building", "READY"))
            print("[bench] ORDER %s @t=%s avail=%s accepted(q0=%s)"
                  % (name, s["t"], avail, qstate(s2)))
            if not accepted:
                print("[bench] RESULT %s NOT BUILDABLE (无电厂先行被拒)" % name)
                res[name] = None
                break
            done = poll(c, lambda s, n=name: any(u["n"] == n for u in s.get("mine", [])
                                                 if u["o"] == 2), timeout=300)
            if not done or not any(u["n"] == name for u in done.get("mine", [])
                                   if u["o"] == 2):
                print("[bench] RESULT %s never completed" % name); res[name] = None
                break
            res[name] = {"order_t": s["t"], "done_t": done["t"],
                         "dur": done["t"] - s["t"]}
            print("[bench] DONE %s t=%s (dur %sgs) power=%s low=%s"
                  % (name, done["t"], done["t"] - s["t"],
                     json.dumps(done["me"]["power"]),
                     done["me"]["power"].get("isLowPower")))
        print("[bench] SUMMARY %s" % json.dumps(res))
        return 0
    finally:
        try:
            c.micro_stop()
        except Exception:
            pass
        try:
            b.close()
            print("[bench] browser closed")
        except Exception as e:
            print("[bench] close ERR %s" % e)


if __name__ == "__main__":
    sys.exit(main())
