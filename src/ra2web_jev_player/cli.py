# -*- coding: utf-8 -*-
"""命令行入口：

- ra2web-jev-play    全自动：冷浏览器 → 进局 → 注入 → 托管整局 → 复盘入账本
                     （--loop N 连跑 N 局，构成"实战→记录→复盘→调参→实战"闭环）
- ra2web-jev-launch  只执行"打开网页+进局+注入"（驱动层调试）
- ra2web-jev-attach  人工已开局时注入托管（菜单自动化失效时的兜底）
- ra2web-jev-review  复盘最后一段对局（也可用于补复盘历史局）
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
    p.add_argument("--max-decisions", type=int, default=1200)
    p.add_argument("--tick-interval", type=float, default=1.5)
    p.add_argument("--loop", type=int, default=1, help="连续对局数(每局之间自动复盘+调参)")
    p.add_argument("--no-review", action="store_true", help="终局后跳过自动复盘")
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
    from . import review
    loop = max(1, args.loop)
    results = []
    for i in range(loop):
        if loop > 1:
            audit.log("=== LOOP game %d/%d ===" % (i + 1, loop))
        audit.log("进局中(全自动)...")
        client = launcher.launch()
        report = BattleSession(client, jev, audit, match).run()
        if not args.no_review:
            try:  # 复盘闭环: 记录→分析→Jev 语义复盘→账本+参数迭代
                # 独立小预算客户端: 对局本体可能刚好耗尽预算(第24局实测)
                r = review.review_last_game(JevClient(max_calls=4), audit)
                report["review"] = {"game_no": r.get("game_no"),
                                    "rootcause": (r.get("answers") or {})
                                    .get("rootcause", {}).get("choice"),
                                    "auto_tuned": len(r.get("changes") or [])}
            except Exception as e:
                audit.log("review ERR %s" % str(e)[:200])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        results.append(report)
    return 0 if any(r.get("result") == "victory" for r in results) else 1


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


def main_review(argv=None) -> int:
    p = argparse.ArgumentParser(description="复盘最后一段对局（生成 review.md + LESSONS + 调参）")
    p.add_argument("--game", type=int, default=None, help="局号(默认自动: 已有最大局号+1)")
    p.add_argument("--log", default=None, help="指定 bot.log 路径(默认 logs/bot.log)")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    from pathlib import Path

    from . import review
    r = review.review_last_game(JevClient(), None, game_no=args.game,
                                log_path=Path(args.log) if args.log else None)
    if r.get("skipped"):
        print(json.dumps(r, ensure_ascii=False))
        return 1
    print(json.dumps({"game_no": r["game_no"], "outcome": r["outcome"],
                      "findings": len(r["findings"]),
                      "rootcause": (r.get("answers") or {}).get("rootcause", {}).get("choice"),
                      "auto_tuned": len(r.get("changes") or []),
                      "review_path": r["review_path"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main_play())
