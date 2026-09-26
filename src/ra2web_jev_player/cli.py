# -*- coding: utf-8 -*-
"""命令行入口：

- ra2web-jev-play    全自动：冷浏览器 → 进局 → 注入 → 托管整局 → 战报
- ra2web-jev-launch  只执行"打开网页+进局+注入"（驱动层调试）
- ra2web-jev-attach  人工已开局时注入托管（菜单自动化失效时的兜底）
"""
from __future__ import annotations

import argparse
import json
import sys

from .audit import Audit
from .config import DriverConfig, MatchConfig
from .driver.browser import Browser
from .driver.launcher import GameLauncher
from .game import BattleSession
from .jev import JevClient


def _common(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--session", default=None, help="agent-browser 会话名(默认 ra2web)")
    p.add_argument("--headed", action="store_true", help="有头窗口(默认无头, 长局首选无头)")
    p.add_argument("--faction", default="苏俄")
    p.add_argument("--speed", type=int, default=2)
    p.add_argument("--credits", type=int, default=10000)
    p.add_argument("--max-decisions", type=int, default=600)
    p.add_argument("--tick-interval", type=float, default=1.5)
    p.add_argument("--debug", action="store_true", help="launcher 每步截图")
    return p.parse_args(argv)


def _wire(args) -> tuple:
    dcfg = DriverConfig(session=args.session or DriverConfig.session, headed=args.headed)
    match = MatchConfig(faction=args.faction, speed=args.speed, credits=args.credits,
                        max_decisions=args.max_decisions,
                        tick_interval=args.tick_interval)
    b = Browser(dcfg)
    audit = Audit()
    jev = JevClient(max_calls=match.max_decisions)
    return b, audit, jev, match


def main_play(argv=None) -> int:
    args = _common(sys.argv[1:] if argv is None else argv)
    b, audit, jev, match = _wire(args)
    launcher = GameLauncher(b, match, debug=args.debug)
    audit.log("进局中(全自动)...")
    client = launcher.launch()
    report = BattleSession(client, jev, audit, match).run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("result") == "victory" else 1


def main_launch(argv=None) -> int:
    args = _common(sys.argv[1:] if argv is None else argv)
    b, audit, _, match = _wire(args)
    launcher = GameLauncher(b, match, debug=args.debug)
    client = launcher.launch()
    s = client.snapshot()
    print(json.dumps({"ok": True, "me": s["me"], "t": s["t"],
                      "mine": len(s["mine"]), "hostile": len(s["hostile"])},
                     ensure_ascii=False, indent=2))
    return 0


def main_attach(argv=None) -> int:
    args = _common(sys.argv[1:] if argv is None else argv)
    b, audit, jev, match = _wire(args)
    client = GameLauncher(b, match).attach()
    report = BattleSession(client, jev, audit, match).run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("result") == "victory" else 1


if __name__ == "__main__":
    sys.exit(main_play())
