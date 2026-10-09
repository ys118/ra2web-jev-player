# Jev 玩家示例

完整启动步骤、密钥配置、实验记录与限制见 [Jev 本地接入](../../jev-player-local.md)。

| 文件 | 用途 |
| --- | --- |
| [werhd-jev-player.mjs](werhd-jev-player.mjs) | 收集公开状态、请求模型、复查并执行动作 |
| [werhd-jev-catalog.mjs](werhd-jev-catalog.mjs) | 根据公开规则构建单位与建筑目录 |
| [werhd-jev-strategy.mjs](werhd-jev-strategy.mjs) | 经济、兵力、科技、防御与恢复候选 |
| [werhd-jev-special.mjs](werhd-jev-special.mjs) | 驻扎、载员、桥梁等组合行动 |
| [werhd-jev-camera.mjs](werhd-jev-camera.mjs) | 本地观察镜头 |
| [werhd-jev-dashboard.html](werhd-jev-dashboard.html) | 本地代理提供的实时看板源码 |

模型 key 由源工程 `tools/werhd-jev-server.mjs` 本地代理持有。代理仍通过 `http://127.0.0.1:5174/player.mjs` 提供入口，页面内挂载方式保持不变；看板请通过代理的 `http://127.0.0.1:5174/` 访问，静态副本不会提供 `/events` 或模型请求服务。

这里发布的是文档附带的示例源码。仅下载这些文件不会自动启动代理、挂载玩家脚本或发起付费模型请求。
