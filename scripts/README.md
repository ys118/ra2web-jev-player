# scripts —— 仓库级运维与数据脚本

> 这些脚本**不是**包的一部分（不进 wheel），按仓库根运行：`uv run python scripts/<名>.py`。
> 它们依赖 `src/ra2web_jev_player` 的路径常量（`paths.py`），目录挪动时只需改那一处。

## 对局运行

| 脚本 | 用途 |
|---|---|
| `preflight.py` | 启动前自检（第 88 局起固化）：clef 决策服务 → 浏览器 WebGL → 残留会话清理 → 站点串行探测。**顺序勿倒**（close 后立即 eval 会挂 150s，第 95 局排查实证）。全通过 exit 0 |
| `site_probe.py` | 单次站点恢复探测（弹窗点掉 + 主选单渲染），exit 0 = 恢复 |
| `run_game.bat` | **通用对局启动器**：`scripts\run_game.bat 101` → preflight 通过后启动对局，控制台日志落 `artifacts/console/g101_console.log` |
| `runs/run_gNN.bat` | g72-g100 的历史启动脚本（存档用；内部路径已随结构重构更新，可直接复跑） |
| `play_watch.sh` | 站点恢复看护（最长 3 小时）→ 恢复后自动开打 |
| `probe.py` | agent-browser 会话健康探针（eval 往返计时） |

## 数据与评测

| 脚本 | 用途 |
|---|---|
| `build_dataset.py` | 训练数据构建器（幂等）：1-65 局历史回填 + 每局 run 目录增量并入 `dataset/`。`--check` 只报告，`--skip-legacy` 只并入新局。详见 `dataset/README.md` |
| `shadow_eval.py` | 影子评测：把历史决策元组回放给本地 clef-flash，与存档中的 Jev 答案比对（绝不调用远端）。结果在 `artifacts/shadow_eval/` |
| `bench_opening.py` + `bench_watch.sh` | 开局建造微基准（第 67 局精炼厂先行链实测）：站点恢复后自动跑，结果在 `artifacts/bench/` |
| `dbg-st.json` | 早期调试时的一张状态快照（历史留档） |

## 新增脚本约定

1. 路径一律从 `ra2web_jev_player.paths` 取（或 `Path(__file__).resolve().parents[1]` 定位仓库根），
   不要写死 `D:\...`；
2. 需要写入产物的，写进 `artifacts/`（运行时产物）或 `dataset/`（训练数据），并同步两个 README；
3. 避免模块级副作用（如 import 时打开文件）——历史 `legacy/bot.py` 踩过这个坑。
