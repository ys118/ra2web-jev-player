# LAYOUT —— 仓库布局与迁移对照（2026-10-09 结构重构）

> 本次重构把仓库从"根目录平铺"整理为标准 uv Python 工程：**代码在 `src/`，
> 文档在 `docs/`（含 knowledge），数据分 `artifacts/`（运行现场）与 `dataset/`
> （训练数据），外部资料合并在 `references/`，脚本在 `scripts/`，测试在 `tests/`。**
> 本文是布局的单一事实来源；历史的局次复盘文字（`LESSONS.md` 等）保留当时路径写法，
> 读旧记录时按文末对照表换算。

## 一、定稿布局

```
ra2web-jev-player/
├── pyproject.toml / uv.lock / .python-version    # uv 工程（src 布局, uv_build）
├── README.md / AGENTS.md                          # 全貌 / 协作红线
├── src/ra2web_jev_player/                         # Python 包（工程的唯一代码源）
│   ├── __main__.py            # python -m ra2web_jev_player（无参只打印用法）
│   ├── paths.py               # 全项目路径常量（唯一来源, env 可覆盖）
│   ├── config.py              # MatchConfig / DriverConfig
│   ├── cli.py                 # 四个命令入口
│   ├── audit.py               # 行日志 + 事件流审计
│   ├── game.py                # BattleSession 对局编排（1.5s 宏观循环）
│   ├── driver/                # browser(agent-browser 封装) + launcher(进局状态机)
│   ├── jev/                   # 决策模型客户端（clef-flavored Jev 契约）
│   ├── werhd/                 # 游戏 API：api.md + client.js + inject.py + d.ts
│   ├── strategy/              # doctrine(阈值/手册) + questions(五问) + state(视图)
│   │   └── planner/           # 确定性决策层（原 1642 行单文件按职责拆包）
│   ├── review/                # 复盘引擎（原 497 行单文件拆包）+ 局号↔run 链接
│   └── legacy/bot.py          # 第 1-20 局的自研主循环（历史对照, 不演进）
├── scripts/                   # 仓库级运维/数据脚本（见 scripts/README.md）
│   ├── run_game.bat           # 通用对局启动器（新局用这个）
│   └── runs/run_g72..g100.bat # 历史启动脚本存档
├── tests/                     # pytest：布局守卫 + 回归场景驱动（见 tests/README.md）
│   └── regression/            # 26 个单变量离线场景脚本（原 out/test_*.py）
├── artifacts/                 # 运行现场（原 logs/ + out/ 的数据部分）
│   ├── logs/                  # bot.log · jev-events.jsonl · 进程 stdout · .play.lock
│   ├── games/                 # game-XXXX-review.md · game-XXXX-events.jsonl · run-<ts>/
│   ├── console/               # gNN_console.log（对局控制台输出）
│   ├── screenshots/ · bench/ · shadow_eval/
├── dataset/                   # 训练数据资产（见 dataset/README.md）
│   ├── game-NNNN/             # 1-65 局历史回填
│   ├── runs/run-<ts>/         # 每局 run 目录的规范化增量副本（含 SFT 元组）
│   ├── MANIFEST.jsonl · run-links.json
├── docs/                      # 全部文档
│   ├── ARCHITECTURE.md · METHODOLOGY.md · ENGINEERING-NOTES.md · HANDOFF.md
│   ├── JEV-INTEGRATION.md · CLEF-LOCAL.md · SESSION-REPORT.md · LESSONS.md
│   └── knowledge/             # 攻略三件套 + 作战手册（原 knowledge/）
└── references/                # 外部资料（原 refs/ + _research/ 合并）
    ├── werhd/                 # API 文档快照 + 官方示例（原 refs/）
    └── research/              # 数值真值 + 数据挖掘流水线（原 _research/）
```

## 二、迁移对照（旧 → 新）

| 旧路径 | 新路径 | 备注 |
|---|---|---|
| `logs/bot.log`、`logs/jev-events.jsonl`、`logs/play*-run.log` | `artifacts/logs/…` | 内容不变 |
| `logs/games/` | `artifacts/games/` | 每局复盘与 run 存档 |
| `logs/screenshots/` | `artifacts/screenshots/` | |
| `out/*.log`（gNN_console 等） | `artifacts/console/` | |
| `out/bench_result.txt` | `artifacts/bench/` | |
| `out/shadow_eval/` | `artifacts/shadow_eval/` | |
| `out/test_*.py` | `tests/regression/` | 场景脚本；由 pytest 驱动 |
| `out/preflight.py`、`out/site_probe.py`、`out/bench_opening.py`、`out/shadow_eval.py` | `scripts/…` | 内部路径改为仓库根相对 |
| `out/run_gNN.bat` | `scripts/runs/run_gNN.bat` | 历史存档；新局用 `scripts/run_game.bat <局号>` |
| `out/play68_watch.sh`、`out/bench_watch.sh` | `scripts/play_watch.sh`、`scripts/bench_watch.sh` | |
| `scripts/build_training_assets.py` | `scripts/build_dataset.py` | 同一职责 + 新增增量并入 |
| `knowledge/` | `docs/knowledge/` | 攻略与作战手册 |
| `refs/`（API 文档+示例） | `references/werhd/` | |
| `_research/`（数值/挖掘） | `references/research/` | 同上，复现流程见其 README |
| `src/ra2web_jev_player/legacy_bot.py` | `src/ra2web_jev_player/legacy/bot.py` | 运行方式：`python -m ra2web_jev_player.legacy.bot` |
| `src/ra2web_jev_player/planner.py`（单一文件） | `src/ra2web_jev_player/strategy/planner/`（包） | 对外 API 不变（`planner.checklist` 等照旧） |
| `src/ra2web_jev_player/review.py`（单一文件） | `src/ra2web_jev_player/review/`（包） | `review.review_last_game` 等对外名不变 |

环境变量（`JEV_*`）也已随之更新：`JEV_ARTIFACTS_DIR` / `JEV_LOG_DIR` / `JEV_GAMES_DIR` /
`JEV_DATASET_DIR` / `JEV_DOCS_DIR` / `JEV_KNOWLEDGE_DIR` / `JEV_REFERENCES_DIR`，
全部可选，未设时按上表默认；`JEV_PROJECT_ROOT` 仍是"仓库不在默认位置"时的总开关。

## 三、不变的红线与不变量

1. **数据不可删**：`artifacts/`、`dataset/`、`docs/knowledge/doctrine.json` 都是资产，
   随 git 持久化（`AGENTS.md`）；清理任何目录树前先按用户级红线做链接检查。
2. **对局运行链路不变**：`uv run ra2web-jev-play` 全自动；启动前自检走 `scripts/preflight.py`；
   单实例锁在 `artifacts/logs/.play.lock`。
3. **决策行为零改动**：本次重构是搬运与组织（函数体逐行保留），所有阈值、
   局次注释、行为参数均未改；26 个回归场景脚本 + 布局守卫测试守护这一点。
4. **代码里不许出现写死路径**：所有目录从 `paths.py` 取（唯一例外是 `scripts/*.bat` 的
   `cd /d %~dp0..`，它自己定位仓库根）。
