# -*- coding: utf-8 -*-
"""``python -m ra2web_jev_player`` -- with no arguments it prints the entry-point usage; with arguments
it is equivalent to ra2web-jev-play.

There is no default action: a real match requires explicit arguments (so an accidental invocation cannot
start a whole game), and the gameplay arguments are identical to ``uv run ra2web-jev-play`` (the same
argparse).
"""
from __future__ import annotations

import sys

_USAGE = """ra2web-jev-player —— 网页红警2 的 Jev 自动对战玩家

用法:
  uv run ra2web-jev-play [选项]        # 全自动: 进局→注入→托管整局→复盘
  uv run ra2web-jev-launch [选项]      # 只进局+注入（驱动层调试）
  uv run ra2web-jev-attach [选项]      # 人工已开局时注入托管（兜底）
  uv run ra2web-jev-review [--game N]  # 复盘最后一段对局
  uv run python -m ra2web_jev_player --help    # 本说明

常用参数: --faction 苏俄 --speed 3 --credits 10000 --headed --loop N --debug
入口代码: src/ra2web_jev_player/cli.py · 文档: README.md / docs/LAYOUT.md
"""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(_USAGE)
        return 0
    from .cli import main_play
    return main_play(argv)


if __name__ == "__main__":
    raise SystemExit(main())
