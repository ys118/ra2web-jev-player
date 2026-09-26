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
    speed: int = 2               # 游戏速度（页面默认 6，太快反应不过来）
    credits: int = 10000
    difficulty: str = "简单"
    opponents: int = 1
    max_decisions: int = 600     # 单局 Jev 决策预算
    tick_interval: float = 1.5   # 宏观循环真实秒


@dataclass
class DriverConfig:
    """agent-browser 会话参数。"""

    session: str = os.environ.get("RA2WEB_SESSION", "ra2web")
    # cookie/localStorage 持久化（为将来接入登录预留；单机遭遇战当前无需登录）
    restore: str = os.environ.get("RA2WEB_RESTORE", "ra2web")
    headed: bool = os.environ.get("RA2WEB_HEADED", "") != ""
    chrome_args: str = ("--disable-background-timer-throttling,"
                        "--disable-backgrounding-occluded-windows")
    idle_timeout: str = "0"      # 0 = 禁用空闲自动关浏览器（长局保活）
    default_timeout_ms: int = 25000
    eval_timeout_s: float = 25.0
    debug_dir: str = ""          # 非空则 launcher 每步截图到该目录
