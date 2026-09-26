# -*- coding: utf-8 -*-
"""ra2web-jev-player: 网页红警2《王二火大/Chrono Divide》的 Jev 自动对战玩家。

自包含架构（无 HTTP 桥接、无官方播放器依赖）：
- werhd: 游戏 API 层 —— 自有定义（api.md + 官方类型副本）+ 页内客户端 client.js
- driver: 浏览器驱动 —— agent-browser 封装 + 游戏启动状态机（全自动进局）
- jev: TypeSafe/Jev 调用封装（密钥只在 Python 侧）
- strategy: 策略层 —— 20 局复盘沉淀的 doctrine/planner + Jev 五问
- game: 对局编排（宏观 1.5s 主循环）× 页内 150ms 微操
- legacy_bot: 第 1-20 局的自研主循环，保留作历史参照

入口: ra2web-jev-play / ra2web-jev-launch / ra2web-jev-attach（见 cli.py）。
文档: README.md、docs/ARCHITECTURE.md、docs/HANDOFF.md。
"""

__version__ = "0.2.0"
