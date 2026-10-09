# ra2web-jev-player

> 网页版红色警戒2《王二火大 / Chrono Divide》的 **AI（TypeSafe Jev / 本地 clef-flash）自动对战玩家**。
> 全自包含：自有 API 定义与页内客户端、全自动进局（浏览器驱动）、自有策略资产、
> 决策模型调用封装 —— 无 HTTP 桥接、无官方播放器依赖。
> 一条命令从冷浏览器打到终局战报：`uv run ra2web-jev-play`。

- **游戏**: https://gonghui.k0s.cn/ （网页版红警2引擎）
- **决策模型**: 本地 `clef-flash`（与 TypeSafe Jev 同契约，Python 侧直调；端点可用 `JEV_BASE_URL` 切回云端 Jev，见 `docs/CLEF-LOCAL.md`）
- **操作通道**: 游戏内 `window.werhd` 官方控制台 API（与鼠标同一条锁步指令队列）
- **架构**: `docs/ARCHITECTURE.md`（去桥接化重构定稿）· **仓库布局**: `docs/LAYOUT.md`

## 一分钟上手

> Python 环境用 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + `uv.lock`）；
> 首次或依赖变更后先 `uv sync`，之后所有命令用 `uv run`（uv 自管 CPython 3.12）。

```bash
uv sync                                  # 首次/依赖变更后（dev 组含 pytest/ruff）
uv run ra2web-jev-play                   # 全自动: 进局→注入→托管整局→战报+自动复盘
#   ra2web-jev-launch                    # 只进局+注入（驱动层调试, --debug 每步截图）
#   ra2web-jev-attach                    # 人工已开局时注入托管（兜底）
#   ra2web-jev-review                    # 复盘最后一段对局
# 常用参数: --faction 苏俄 --speed 3 --credits 10000 --headed --loop N

# 对局统一启动器（含 preflight 自检, 控制台日志落 artifacts/console/）:
#   scripts\run_game.bat 101

uv run pytest                            # 回归测试（26 个场景 + 布局守卫）
uv run ruff check                        # 静态检查

tail -f artifacts/logs/bot.log           # 行日志（决策/建造/攻防）
tail -f artifacts/logs/jev-events.jsonl  # 逐决策审计（jsonl）
```

## 目录结构（定稿布局，迁移对照见 `docs/LAYOUT.md`）

| 路径 | 内容 |
|---|---|
| `src/ra2web_jev_player/` | Python 包（src 布局）：`werhd/`（自有 API 定义 `api.md` + 官方类型副本 + 页内客户端 `client.js` + 注入器）；`driver/`（agent-browser 封装 + 全自动进局状态机）；`jev/`（决策模型调用封装）；`strategy/`（攻略沉淀的 doctrine/questions/state + `planner/` 确定性决策包）；`review/`（复盘引擎包：确定性分析 + Jev 语义复盘 + 限幅调参）；`game.py`（对局编排）；`cli.py`/`__main__.py`（入口）；`paths.py`（路径常量唯一来源）；`legacy/bot.py`（第 1-20 局主循环，历史对照） |
| `scripts/` | 仓库级运维/数据脚本：`run_game.bat`（统一启动器）、`preflight.py`（启动前自检）、`build_dataset.py`（训练数据构建，幂等）、`shadow_eval.py`（影子评测）、`runs/`（历史启动脚本存档）—— 清单见 `scripts/README.md` |
| `tests/` | pytest：布局/契约守卫 + `regression/` 26 个单变量离线场景测试（详见 `tests/README.md`） |
| `artifacts/` | **运行现场**（原 `logs/` + `out/`）：`logs/`（bot.log、jev-events.jsonl、进程 stdout）、`games/`（每局复盘 + `run-<时间戳>/` 存档：SFT 元组/事件流/战报）、`console/`、`screenshots/`、`bench/`、`shadow_eval/` —— 见 `artifacts/README.md` |
| `dataset/` | **训练数据资产**：1-65 局历史回填 + `runs/` 每局增量并入（SFT/RL），`MANIFEST.jsonl` 索引、`run-links.json` 对齐表 —— 见 `dataset/README.md` |
| `docs/` | `ARCHITECTURE.md` 架构定稿 · `LAYOUT.md` 布局与迁移对照 · `HANDOFF.md` 冷启动交接 · `LESSONS.md` 逐局经验账本 · `METHODOLOGY.md` 方法论 · `ENGINEERING-NOTES.md` 引擎/环境坑总集 · `JEV-INTEGRATION.md` 模型接入与参数迭代 · `CLEF-LOCAL.md` 本地决策服务 · `SESSION-REPORT.md` 二十局进化史 |
| `docs/knowledge/` | 攻略三件套 + 用法说明：`RA2-BIBLE.md`（全维度攻略+兵法）、`AI-OPERATING-CARD.md`（可执行操作卡）、`RA2-UNITS.json`（rules.ini 真值：单位/建筑/弹头×护甲矩阵）；`doctrine.json` 为复盘自动调参的覆盖值（git 可审计） |
| `references/` | 外部资料（原 `refs/` + `_research/`）：`werhd/` 官方 API 文档与示例；`research/` 数值真值（`rules.ini`/`ra2.csf`）与可复现挖掘流水线（`README.md` 抄流程）—— 见 `references/README.md` |

## 架构一瞥

```
浏览器（agent-browser 无头会话）
  └─ 游戏页: window.werhd(官方 API) + window.__rj(自有页内客户端)
       └─ micro() 每 150ms: 集火/矿车/维修/落位/镜头（零网络）
Python (src/ra2web_jev_player/, uv)
  ├─ driver: 冷浏览器→弹窗→菜单→配置→开局 全自动(~25s)
  ├─ game.py 宏观 ~1.5s: 快照→感知→确定性清单→Jev 五问→机动
  ├─ strategy/planner: 确定性管机制（清单/开局序列/侦察/五态/机动）
  ├─ strategy/doctrine: 阈值与作战手册（每局复盘迭代, 覆盖值入 docs/knowledge/doctrine.json）
  ├─ review: 终局自动复盘 → artifacts/games/game-XXXX-review.md + docs/LESSONS.md + 调参
  └─ jev: 决策模型直调（密钥只在 Python 进程内）
```

**决策分工**（贯穿全项目的核心原则）：
- **确定性代码管机制**：部署/落位/建造序列/产量保底/指令节流/集结与撤退阈值；
- **模型管语义拍板**：态势转换、威胁评估、兵种搭配、进攻时机；
- 置信度闸门（态势 ≥0.45 采信）、一次请求批量问全部问题、页内节流防指令抖动。

## 学习闭环（实战→数据→训练）

```
对局(game.py) → 实时审计(artifacts/logs/) + 每局存档(artifacts/games/run-<ts>/)
      ↓ 终局自动复盘
review: 确定性分析 + 语义复盘 → game-XXXX-review.md · LESSONS.md · doctrine.json 限幅调参
      ↓ 训练侧
dataset/: build_dataset.py 幂等并入每局 run（SFT 元组 (state,questions,answers) + 事件流 + 战报）
```

## 现状快照

- **自研循环时代（第 1-20 局）**：从"开局 12 分钟被拆"进化到"27:15 拉锯、单局击杀 98"；全部引擎坑沉淀在 `docs/ENGINEERING-NOTES.md`。
- **官方体系时代（第 21-22 局）**：官方播放器 + 自建桥接验证了"页内微操 + 模型宏观"的分层（P50 1000ms、0 失败），但依赖 HTTP 桥接与官方脚本。
- **自包含时代（2026-09-26 去桥接化重构起）**：自有 API 层/页内客户端/全自动进局/自有策略；**截至 100 局 21 胜**，打法 A++（骚扰断经济 + 重拳推平 + 双刃自适应），学习闭环全自动运转；每局产出完整 SFT 决策元组并入 `dataset/`。逐局教训见 `docs/LESSONS.md`，交接见 `docs/HANDOFF.md`。
- **2026-10-09 结构重构**：仓库整理为标准 uv 工程（代码/文档/数据/资料分区，planner 与 review 拆包，测试可 `uv run pytest`），**决策行为零改动**，见 `docs/LAYOUT.md`。

## 红线与合规

- 只使用游戏**公开的**玩家控制台 API（官方文档明确：读取本地可见视野，指令走与鼠标相同的锁步队列）；
- 不修改模拟、不透雾、不读隐藏敌方状态；不做外挂；
- 自动化仅用于**单机遭遇战**（AI 对手）；未接入排位/联机（涉及平台规则与他人体验）。
- 数据资产（`artifacts/`、`dataset/`）**禁删禁清**，随 git 持久化；密钥只在环境变量/Python 进程内，绝不入库。
