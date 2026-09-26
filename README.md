# ra2web-jev-player

> 网页版红色警戒2《王二火大 / Chrono Divide》的 **AI（Jev 模型）自动对战玩家**。
> 用 TypeSafe 的 Jev 模型做战术决策，通过游戏官方的 `werhd` 玩家控制台 API 操作部队，
> 自动完成基地建设、侦察、生产、防御与总攻。

- **游戏**: https://gonghui.k0s.cn/ （网页版红警2引擎，v0.87.0）
- **决策模型**: TypeSafe Jev（`jev-1.13.x`，经 `bridge.py` 接入，P50 ≈ 1s/批）
- **操作通道**: 游戏内 `window.werhd` 官方控制台 API（与鼠标同一条锁步指令队列）
- **状态**: 已实跑 20+ 局（自研循环）→ 已切换到官方 werhd-jev-player 体系 + 自建桥接

## 一分钟上手

```bash
# 1. 启动本地桥接（持有 TYPESAFE_API_KEY 环境变量）
python bridge/bridge.py            # 监听 127.0.0.1:5174

# 2. 打开游戏（agent-browser 无头会话推荐，见 docs/ENGINEERING-NOTES.md）
#    https://gonghui.k0s.cn/ → 单机模式 → 遭遇战 → 开始游戏

# 3. 对局内挂载官方 Jev 玩家（浏览器控制台 / 自动化 eval）
const { attachJevPlayer } = await import('http://127.0.0.1:5174/player.mjs')
window.werhdJev = await attachJevPlayer(window.werhd)

# 4. 观察：GET http://127.0.0.1:5174/ （官方看板）
#         GET http://127.0.0.1:5174/status （统计）
#         logs/jev-events.jsonl （逐决策审计）
```

## 目录结构

| 路径 | 内容 |
|---|---|
| `bridge/bridge.py` | **本机桥接**：向页面服务官方玩家模块（`/player.mjs`）、把候选组转发 TypeSafe jev（`/decide`）、事件审计（`/event`、SSE `/events`）、看板与统计 |
| `legacy-bot/bot.py` | 前 20 局使用的自研 Python 主循环（"状态→jev→执行"快循环），保留作对照与备份 |
| `knowledge/` | 攻略三件套：`RA2-BIBLE.md`（全维度攻略+兵法）、`AI-OPERATING-CARD.md`（可执行的压缩操作卡）、`RA2-UNITS.json`（rules.ini 真值：单位/建筑/弹头×护甲矩阵） |
| `refs/` | 游戏官方资料（从 `D:/projects/ra2web.github.io/docs` 复制）：`player-console-api.md`（werhd 完整 API）、`jev-player-local.md`（官方 Jev 玩家接入规格与实测）、`examples/`（官方玩家/策略/特殊行动/看板源码） |
| `docs/` | `SESSION-REPORT.md` 二十局进化史 · `METHODOLOGY.md` 方法论 · `ENGINEERING-NOTES.md` 引擎/环境坑总集 · `JEV-INTEGRATION.md` Jev 接入与参数迭代 · `MEMORY-NOTES.md` 长期记忆快照 |
| `logs/` | `bot.log`（自研 bot 决策日志）、`bridge.log`、`jev-events.jsonl`（逐决策审计）、`screenshots/`（全部过程截图证据） |
| `_research/` | 数值真值源：`rules.ini` 提取表、`csf_decoded.json`（代号→中文名）、社区攻略原文 |

## 架构

```
┌─────────────────────────── 游戏页（浏览器内）───────────────────────────┐
│ 官方 werhd-jev-player.mjs                                              │
│  ├─ micro()  每 150ms（零网络）: 集火/矿车恢复/维修/落位/姿态/镜头      │
│  └─ decide() 每 600ms: 生成候选组 → POST 本机桥接 → 复查 → 执行        │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ HTTP (127.0.0.1:5174, CORS)
┌──────────────────────────────▼─────────────────────────────────────────┐
│ bridge.py                                                              │
│  /player.mjs 服务官方模块 · /decide {state,groups} → TypeSafe /systemone│
│  /event 审计 + SSE /events · / 看板 · /status 统计                     │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ HTTPS
                     TypeSafe Jev（jev-1.13.x）
```

**决策分工**（贯穿全项目的核心原则）：
- **确定性代码管机制**：部署/落位/建造序列/产量保底/指令节流/集结与撤退阈值；
- **Jev 管语义拍板**：态势转换、威胁评估、兵种搭配、进攻时机、侦察目标选择；
- 判断置信度闸门（<0.45 不切换态势）、同批问题一次请求、防指令抖动（12s 节流、任务连续性）。

## 现状快照

- **自研循环时代（第 1-20 局）**：从"开局 12 分钟被拆"进化到"27:15 拉锯、单局击杀 98 个 AI 单位"；期间沉淀了全部引擎坑（见 `docs/ENGINEERING-NOTES.md`）。
- **官方体系时代（第 21 局起）**：接入官方 `werhd-jev-player.mjs` + 自建 `bridge.py`，实测单批决策 P50 1000ms / P95 1343ms、~1900 tokens/次、0 调用失败；微操回到页内 150ms 级。
- **下一步**：完整跑通并记录官方体系整局结果；按 `docs/METHODOLOGY.md` 的复盘闭环继续迭代。

## 红线与合规

- 只使用游戏**公开的**玩家控制台 API（官方文档明确：读取本地可见视野，指令走与鼠标相同的锁步队列）；
- 不修改模拟、不透雾、不读隐藏敌方状态；不做外挂；
- 自动化仅用于**单机遭遇战**（AI 对手）；未接入排位/联机（涉及平台规则与他人体验）。
