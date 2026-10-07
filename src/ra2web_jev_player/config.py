# -*- coding: utf-8 -*-
"""配置：对局参数与浏览器驱动参数（环境变量可覆盖）。

对局设置（阵营/速度/资金）在页面重载后会全部重置，每局都必须重设 ——
见 docs/ENGINEERING-NOTES.md §3.3。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

GAME_URL = os.environ.get("RA2WEB_GAME_URL", "https://gonghui.k0s.cn/")


@dataclass
class MatchConfig:
    """单机遭遇战设置。"""

    faction: str = "苏俄"        # 苏俄 / 盟军 / ...
    speed: int = 3               # 游戏速度档（2026-09-29 用户定谳: 3 档。
                                 # 实测: 1 档=0.82x 墙钟偏慢, 6 档=~4x 过快;
                                 # 注意: launcher 旧滑条设值从未生效, 前 50
                                 # 局一直跑在 6 档, 已修为真实方向键设值）
    credits: int = 10000
    difficulty: str = "简单"
    opponents: int = 1
    max_decisions: int = 1200    # 单局决策预算（cli 每局以 JevClient 解析值覆盖本字段:
                                 # 本地 clef 实质不限 999999 / 云端 Jev 1200, 2026-10-04
                                 # 用户定谳。历史注: [第28局] 600→1200, 成本 ~$0.1/局）
    tick_interval: float = 1.5   # 宏观循环真实秒


@dataclass
class DriverConfig:
    """agent-browser 会话参数。"""

    session: str = os.environ.get("RA2WEB_SESSION", "ra2web")
    # cookie/localStorage 持久化（为将来接入登录预留；单机遭遇战当前无需登录）
    restore: str = os.environ.get("RA2WEB_RESTORE", "ra2web")
    headed: bool = os.environ.get("RA2WEB_HEADED", "") != ""
    chrome_args: str = ("--disable-background-timer-throttling,"
                        "--disable-backgrounding-occluded-windows,"
                        # [第95局] 站点 0.87.0 音频许可弹窗(游戏需要您的许可来
                        # 播放音频)的根治: 允许站点免手势自动播放——AGENT_BROWSER_
                        # ARGS env 会覆盖全局 config 的 args, 所以必须写在这里;
                        # launcher 的弹窗点击轮询保留作兜底。
                        "--autoplay-policy=no-user-gesture-required")
    idle_timeout: str = "0"      # 0 = 禁用空闲自动关浏览器（长局保活）
    default_timeout_ms: int = 25000
    eval_timeout_s: float = 25.0
    debug_dir: str = ""          # 非空则 launcher 每步截图到该目录
