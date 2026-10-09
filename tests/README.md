# tests —— 测试

## 怎么跑

```bash
uv run pytest                       # 全套（布局守卫 + 26 个回归场景）
uv run pytest -k freeze             # 单个场景（按文件名过滤）
uv run pytest tests/test_layout.py  # 只跑布局/契约守卫
uv run python tests/regression/test_freeze95.py   # 直接跑某个场景脚本（等价）
```

## 结构

| 路径 | 说明 |
|---|---|
| `test_layout.py` | 仓库布局与包契约守卫：路径常量必须指向定稿布局、数据资产目录必须非空、RA2-UNITS.json 必须真加载、planner/ review 对外 API 稳定、`python -m` 无参不发起对局、版本号两处一致。**任何一次目录/改名忘了同步代码，这里立刻红** |
| `test_review_flow.py` | 复盘链路端到端（离线沙箱，`JEV_*` 环境变量指向临时目录）：events → 确定性分析 → stub 语义复盘 → review.md/LESSONS/doctrine 调参 → `run-*/game.json` 局号链接。覆盖错误指纹分支（历史漏 `import re` 缺陷点） |
| `test_regression_suite.py` | 把 `regression/` 下的场景脚本逐个子进程执行并断言退出码 0 |
| `regression/test_*.py` | 历次迭代的**单变量离线场景测试**（第 30-101 局弧线积累）：喂 state 快照，断言 planner/game 的确定性行为。文件名里的数字=当时局次，docstring 写清"测什么、为什么" |

## 约定

- 场景脚本是"文件即用例"：顶层执行 + 逐条打印 `PASS/FAIL` + 失败 `sys.exit(1)`；
  `regression/conftest.py` 已让 pytest 不直接收集它们（避免 import 期 SystemExit）。
- 新增场景测试：放 `tests/regression/`，文件名 `test_<主题><局次>.py`，
  用仓库根相对方式加 `src` 到 `sys.path`（照抄既有文件头部一行）。
- 顶层执行的场景脚本用 `python <file>` 或 pytest 驱动均可，无需 fixture。

## 已知陈旧断言（xfail，待人工核对）

| 文件 | 冲突点 |
|---|---|
| `regression/test_dog62.py` | 断言驻家名额为 10，现行 garrison 语义（第 84/92 局迭代）给 9 —— 需确认是"测试过时"还是"语义回退" |
| `regression/test_gate.py` | 断言日志文案 `工厂前置位保护`，第 67 局改名为 `开局序列前置位保护` |

两者与 2026-10-09 的结构重构无关（重构前即失败，已记录基线）。修好任一条后
从 `KNOWN_STALE`（`tests/test_regression_suite.py`）里删掉即可。
