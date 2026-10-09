# ra2web-jev-player —— 工作区指令

> 仓库布局（2026-10-09 结构重构定稿）见 `docs/LAYOUT.md`：代码在 `src/`，文档在 `docs/`
> （含 `docs/knowledge/`），运行现场在 `artifacts/`，训练数据在 `dataset/`，
> 外部资料在 `references/`，脚本在 `scripts/`，测试在 `tests/`。

## 对局汇报规则（用户指定，2026-09-26）

**每执行完一局（无论胜败、无论是否 `--loop` 连跑中的中间局），必须立即停下来，
向用户做汇报，等用户给出反馈后才能继续下一局或进行迭代。**

汇报至少包含：
1. 战报：结果、时长、关键时间线（开局建造/首坦克/敌基地定位/终局态势）；
2. 复盘要点：`artifacts/games/game-XXXX-review.md` 的确定性发现 + 模型根因判定；
3. 本局学到了什么、拟议的下一步迭代（单变量），交由用户确认后再执行。

禁止：连跑多局不等反馈、跳过汇报直接迭代、未经用户同意自动开始下一局。

## 训练数据资产（用户指定，2026-09-29，最高优先级之一）

用户将在基座模型之上做**模型后训练（SFT/RL）**——每局对战数据都是训练资产：

1. **每局自动存档**至 `artifacts/games/run-<时间戳>/`：
   - `decisions.jsonl`——决策元组（完整 state + questions + answers + 态势上下文），SFT 核心数据；
   - `events.jsonl`——本局全事件流（决策/动作/损失/击杀/观测快照）；
   - `report.json`——终局战报（复盘后另写 `game.json`：局号↔run 目录链接）；
2. 复盘产物 `artifacts/games/game-XXXX-review.md` 与账本 `docs/LESSONS.md` 同为数据资产，
   一并持久化；训练侧规范化出口是 `dataset/`（`uv run python scripts/build_dataset.py` 幂等并入，
   规范与编号口径见 `dataset/README.md`）；
3. **红线：禁止清理/覆盖/删除 `artifacts/`、`dataset/` 下任何历史数据**；
   数据目录不进 .gitignore，随 git 持久化推送；
4. 汇报时发现数据缺失/损坏/未存档，立即向用户报告；
5. 涉及数据格式变更（如 decisions 字段增删、dataset 字段变化）需先汇报再改，保证旧数据可读。

## 其他既有红线（与 docs/HANDOFF.md §四 一致）

- 只用游戏公开的 werhd API；只打单机遭遇战，不打排位/联机；
- 决策模型密钥只在 Python 进程内，绝不写进页面/日志/代码；
- 未经确认入库不删除任何工作目录（数据目录默认禁删）；
- 学习闭环的调参走 `docs/knowledge/doctrine.json`（白名单+限幅+置信闸门），结构性改动先汇报；
- 结构性重构（目录搬迁/模块拆分）必须先保证：`uv run pytest` 全过（26 场景 + 布局守卫，
  陈旧断言在 `tests/README.md` 登记）、决策行为零改动。
