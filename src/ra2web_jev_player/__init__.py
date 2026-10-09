# -*- coding: utf-8 -*-
"""ra2web-jev-player: 网页红警2《王二火大/Chrono Divide》的自动对战玩家。

自包含架构（无 HTTP 桥接、无官方播放器依赖）：
- werhd: 游戏 API 层 —— 自有定义（api.md + 官方类型副本）+ 页内客户端 client.js
- driver: 浏览器驱动 —— agent-browser 封装 + 游戏启动状态机（全自动进局）
- jev: 决策模型调用封装（与 TypeSafe Jev 同契约；密钥只在 Python 侧）
- strategy: 策略层 —— 复盘沉淀的 doctrine/questions/state + planner 确定性决策包
- review: 复盘引擎 —— 确定性分析 + 模型语义复盘 + 限幅调参（学习闭环的收口）
- game: 对局编排（宏观 1.5s 主循环）× 页内 150ms 微操
- paths: 仓库路径常量（唯一来源；布局见 docs/LAYOUT.md）
- legacy.bot: 第 1-20 局的自研主循环，保留作历史参照

入口: ra2web-jev-play / ra2web-jev-launch / ra2web-jev-attach / ra2web-jev-review
      （见 cli.py）；`python -m ra2web_jev_player` 打印用法。
文档: README.md、docs/ARCHITECTURE.md、docs/HANDOFF.md、docs/LAYOUT.md。
"""

__version__ = "0.2.0"
