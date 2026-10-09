# -*- coding: utf-8 -*-
"""Engine micro-benchmark before game 67: refinery-first chain measured on the current engine:
  Q1 Is NAREFN buildable without a power plant (the real prereq POWER check)?
  Q2 Actual construction time of each of NAREFN->NAHAND->NAWEAP (vs the game-66 power-plant-first chain)?
  Q3 Does low power (isLowPower) slow construction/production?
Benchmarks only, no match management; closes the browser at the end."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
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
                 timeout=300, tag="yard")
        if not s:
            print("[bench] FATAL yard never appeared")
            return 1
        t0 = s["t"]
        print("[bench] yard@t=%s av0=%s" % (t0, av0(s)))
        print("[bench] power: %s" % json.dumps(s["me"]["power"]))
        c.micro_start()
        # 等可造列表就绪(av0 非空)——长引导会话里菜单可能滞后
        try:
            s = poll(c, lambda s: len(av0(s)) > 0, timeout=120, tag="av0")
        except Exception as e:
            print("[bench] av0 poll died: %s" % str(e)[:100])
            raise
        if not s or len(av0(s)) == 0:
            print("[bench] INCONCLUSIVE av0 never ready (t=%s)" % (s or {}).get("t"))
            return 2
        print("[bench] av0-ready t=%s av0=%s" % (s["t"], av0(s)))

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
                print("[bench] RESULT %s never completed" % name)
                res[name] = None
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
