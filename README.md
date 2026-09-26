# ra2web-jev-player

> 网页版红色警戒2《王二火大 / Chrono Divide》的 **AI（Jev 模型）自动对战玩家**。
> 全自包含：自有 API 定义与页内客户端、全自动进局（浏览器驱动）、自有策略资产、
> TypeSafe Jev 调用封装 —— 无 HTTP 桥接、无官方播放器依赖。
> 一条命令从冷浏览器打到终局战报：`uv run ra2web-jev-play`。

- **游戏**: https://gonghui.k0s.cn/ （网页版红警2引擎，v0.87.0）
- **决策模型**: TypeSafe Jev（`jev-latest`，Python 侧直调，P50 ≈ 0.8-1s/批）
- **操作通道**: 游戏内 `window.werhd` 官方控制台 API（与鼠标同一条锁步指令队列）
- **架构**: `docs/ARCHITECTURE.md`（去桥接化重构，2026-09-26 定稿）

## 一分钟上手

> Python 环境用 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + `uv.lock`）；
> 首次或依赖变更后先 `uv sync`，之后所有命令用 `uv run`（uv 自管 CPython 3.12）。
> 需要环境变量 `TYPESAFE_API_KEY`（已配用户级）。

```bash
uv sync                                  # 首次/依赖变更后
uv run ra2web-jev-play                   # 全自动: 进局→注入→托管整局→战报
#   ra2web-jev-launch                    # 只进局+注入（驱动层调试, --debug 每步截图）
#   ra2web-jev-attach                    # 人工已开局时注入托管（兜底）
# 常用参数: --faction 苏俄 --speed 2 --credits 10000 --headed --session <名>

tail -f logs/bot.log                     # 行日志（决策/建造/攻防）
tail -f logs/jev-events.jsonl            # 逐决策审计（jsonl）
```

## 目录结构

| 路径 | 内容 |
|---|---|
| `src/ra2web_jev_player/` | Python 包（uv 管理，src 布局）：`werhd/`（自有 API 定义 api.md + 官方类型副本 d.ts + 页内客户端 client.js + 注入器）；`driver/`（agent-browser 封装 + 全自动进局状态机）；`jev/`（TypeSafe 调用封装）；`strategy/`（20 局复盘沉淀的 doctrine/planner/questions）；`game.py`（对局编排）；`cli.py`（三个入口）；`audit.py`；`config.py`；`legacy_bot.py`（第 1-20 局自研主循环，历史参照） |
| `pyproject.toml` / `uv.lock` | uv 项目配置与锁文件；依赖组 `research`（`_research/` 抓取脚本用 requests） |
| `knowledge/` | 攻略三件套 + 用法说明：`RA2-BIBLE.md`（全维度攻略+兵法）、`AI-OPERATING-CARD.md`（可执行的压缩操作卡，可直接当系统提示词）、`RA2-UNITS.json`（rules.ini 真值：单位/建筑/弹头×护甲矩阵）；`README.md` 讲清楚三者的分工、出处与**版本绑定关系** |
| `refs/` | 游戏官方文档快照（从 `D:/projects/ra2web.github.io/docs` 复制）：`player-console-api.md`（werhd 完整 API 原文）、`jev-player-local.md`、`examples/`（官方播放器源码，作参考保留）。**运行时已不依赖**；本项目自有 API 定义在 `src/ra2web_jev_player/werhd/api.md` |
| `docs/` | `ARCHITECTURE.md` 架构定稿 · `SESSION-REPORT.md` 二十局进化史 · `METHODOLOGY.md` 方法论 · `ENGINEERING-NOTES.md` 引擎/环境坑总集 · `JEV-INTEGRATION.md` Jev 接入与参数迭代 · `HANDOFF.md` 冷启动交接 |
| `logs/` | `bot.log`（决策日志）、`jev-events.jsonl`（逐决策审计）、`screenshots/`（过程截图证据） |
| `_research/` | 数值真值源与可复现流水线：`rules.ini` / `ra2.csf`、提取表、`decode_csf.py`（代号→中文名）、`gen_json.py`（生成 RA2-UNITS.json）、`verify.py`（56 项对账）、社区攻略原文（`pages/` 43 篇）；**复现/刷新照 `_research/README.md` 抄** |

## 架构一瞥

```
浏览器（agent-browser 无头会话）
  └─ 游戏页: window.werhd(官方 API) + window.__rj(自有页内客户端)
       └─ micro() 每 150ms: 集火/矿车/维修/落位/镜头（零网络）
Python (src/ra2web_jev_player/, uv)
  ├─ driver: 冷浏览器→弹窗→菜单→配置→开局 全自动(~25s)
  ├─ game.py 宏观 ~1.5s: 快照→感知→确定性清单→Jev 五问→机动
  ├─ strategy: 20 局复盘的 doctrine/阈值/五态机（确定性管机制）
  └─ jev: TypeSafe 直调（密钥不出 Python）
```

**决策分工**（贯穿全项目的核心原则）：
- **确定性代码管机制**：部署/落位/建造序列/产量保底/指令节流/集结与撤退阈值；
- **Jev 管语义拍板**：态势转换、威胁评估、兵种搭配、进攻时机；
- 置信度闸门（态势 ≥0.45 采信）、一次请求批量问全部问题、页内节流防指令抖动。

## 现状快照

- **自研循环时代（第 1-20 局）**：从"开局 12 分钟被拆"进化到"27:15 拉锯、单局击杀 98"；全部引擎坑沉淀在 `docs/ENGINEERING-NOTES.md`。
- **官方体系时代（第 21-22 局）**：官方播放器 + 自建桥接验证了"页内微操 + 模型宏观"的分层（P50 1000ms、0 失败），但依赖 HTTP 桥接与官方脚本。
- **自包含时代（2026-09-26 重构起）**：去桥接化——自有 API 层/页内客户端/全自动进局/自有策略；行为参数与决策核心原样平移，跑通整局后按 `docs/METHODOLOGY.md` 复盘闭环继续迭代。

## 红线与合规

- 只使用游戏**公开的**玩家控制台 API（官方文档明确：读取本地可见视野，指令走与鼠标相同的锁步队列）；
- 不修改模拟、不透雾、不读隐藏敌方状态；不做外挂；
- 自动化仅用于**单机遭遇战**（AI 对手）；未接入排位/联机（涉及平台规则与他人体验）。
