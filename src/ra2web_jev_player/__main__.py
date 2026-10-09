# -*- coding: utf-8 -*-
"""``python -m ra2web_jev_player`` —— 无参打印入口说明；带参等价于 ra2web-jev-play。

不设默认动作：真要对局必须显式给参数（避免误触发起一整局），
玩法参数与 ``uv run ra2web-jev-play`` 完全一致（同一 argparse）。
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
入口代码: src/ra2web_jev_player/cli.py · 文档: README.md / docs/HANDOFF.md
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
