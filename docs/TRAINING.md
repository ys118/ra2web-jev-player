# TRAINING —— 决策模型后训练手册：数据资产 → SFT / RL / DPO

> 本文档把「100 局积累的对局数据如何用于小模型后训练」整理成可执行手册：语料盘点、
> 样本契约、导出脚本用法与输出 schema、实测坑、首轮配方与评测门槛。
> 配套工具：`scripts/export_training.py`（导出）、`scripts/shadow_eval.py`（回归评测）、
> `scripts/build_dataset.py`（索引入库）。数字均为 2026-10-10 在本机语料上的实时统计。

## 〇、结论速览

- 语料天生就是决策模型的师范数据：每个决策点落盘的是
  `(state 提示文本, questions 结构) → answers 结构`，与运行时发给
  `POST /v1/systemone` 的请求/响应**逐字段一致**（`src/ra2web_jev_player/jev/client.py`）。
  → **不要把样本重新渲染成聊天模板**，train/serve skew 就出在这里。
- 只差一个导出脚本，本仓库已实现：
  `uv run python scripts/export_training.py`（派生数据写 `dataset/export/`，已 gitignore）。
- 语料实测：**63 个 run / 52,107 条元组**（P50 10.4KB ≈ 2.7K token），
  其中 **Jev 强教师时代 27 局 14,045 条**、**clef 自出签时代 36 局 38,062 条**。
- 训练效果的验收**不在 loss**：过 `scripts/shadow_eval.py` 的影子评测基线（§六）
  再做实局 A/B 单变量对照。

## 一、语料盘点（什么数据 → 什么用途）

| 数据 | 位置 / 规模（实测） | 后训练用途 |
|---|---|---|
| 决策师范元组 `decisions.jsonl` | `artifacts/games/run-*/`，63 局 **52,107 条**，均 9.2KB（P95 11.8KB） | **SFT 主料**：prompt=state+questions，completion=answers |
| 事件流 `events.jsonl` | 64 个 run：`decision`(t+answers) / `action` / `produce_skip` / `obs` / `loss` / `kill` / `report` | **RL/离线 RL 轨迹**：62,989 步，按 `t` 对齐，终局在 `report` |
| `report.json` / `game.json` / 复盘头 | 每局 | **奖励与标签**：victory / defeat / stall / unknown |
| `game-XXXX-review.md` + `docs/LESSONS.md` | 64 + 1 份中文分析 | 文本 SFT（复盘风格）/ 人工分析 |
| `artifacts/shadow_eval/results.jsonl` | **828** 条 clef-vs-Jev 重放（含双方完整答案） | **DPO/偏好对**：同一 state 下 chosen=Jev、rejected=clef |

### 时代切分（决定训练目标，依据 `docs/CLEF-LOCAL.md` §8.2，已按数据复核）

| 时代 | 判定 | 范围与规模 | 训练定位 |
|---|---|---|---|
| **Jev 强教师** | 元组**无** `teacher` 字段 | 第 45–69 局，27 局 / **14,045 条** | **蒸馏**：跟强模型学，是能提升上限的部分 |
| **clef 自出签** | `teacher == "clef"` | 第 70 局起，36 局 / **38,062 条** | **行为克隆**：固化当前策略风格/稳健性，不会超过现状 |

> 边界陷阱：`run-20261004-113223` 是 Jev 花钱打光余额的**收官局**（无 teacher 字段），
> **不是** clef 冒烟局；clef 首正式局是 `run-20261004-154529`（§8.2 勘误）。

## 二、样本契约（训练格式）

运行时请求/响应（逐字保留即可训练）：

```json
请求  {"state":   {"battlefield": "…", "doctrine": "…", "faction": "…", "decision_request": "…"},
       "questions": {"build": {"type":"choice","instructions":"…","criteria":{...}}, "stance": {...},
                     "threat": {"type":"noul","instructions":"…"}}}
响应  {"build":  {"type":"choice","choice":"hold","probabilities":{"hold":1.0},"confidence":1.0},
       "stance": {"type":"choice","choice":"develop","probabilities":{...},"confidence":0.88},
       "threat": {"type":"noul","noul":0.0046}}
```

三处必须记住的契约细节：

1. **`threat` 是 noul 类**：答案键是 `noul`（不是 `probability`/`probabilities`）——文档里记过
   的老坑，训练格式写错会在服务端静默失配。
2. **问题集按 tick 条件出现**：`build`/`stance`/`threat` 每 tick 都有；`inf`/`veh` 只在
   存在对应生产建筑时才问（Jev 集 14,045 条里 inf 12,164 / veh 10,472）。
   **不要把"本 tick 没问"当成负样本**——completion 只包含 prompt 里出现过的 qid。
3. **`answers` 允许 `choice: null`**（模型弃答/解析失败）→ 导出器统计在
   `stats.sft.samples_with_null_choice`；当前语料为 **0**，可用 `--drop-null-choice` 防御。

导出格式 = **prompt-completion JSONL**（`prompt` 是上面的请求对象，`completion` 是响应对象）。
若训练框架只吃 chat 格式，再包一层 `messages` 也行，但**模板必须与 llama.cpp 服务端钉死一致**。

## 三、导出脚本 `scripts/export_training.py`

```bash
uv run python scripts/export_training.py                       # 全量（两时代），写 dataset/export/
uv run python scripts/export_training.py --era jev --out dataset/export/jev   # SFT-1 蒸馏集
uv run python scripts/export_training.py --min-conf 0.5         # 样本级置信度过滤
uv run python scripts/export_training.py --check                # 只统计不写盘
```

| 参数 | 说明 |
|---|---|
| `--era {all,jev,clef}` | 时代过滤，**对 SFT 与 RL 同时生效**；无法归属（无 `decisions.jsonl`）的 run 一并排除 |
| `--min-conf F` | 样本级：任一 choice 槽 `confidence < F` 即丢弃（noul 槽不参与）；默认 0=不过滤 |
| `--drop-null-choice` | 丢弃存在 `choice=null` 槽的样本 |
| `--val-every N` / `--val-runs` | 按 run 时序每 N 局留 1 局做验证集（默认 5）；或显式指定局名列表 |
| `--chars-per-token` | token 估算比值（仅用于 stats 长度估算，默认 4.0） |

**两个设计决定**（都是有依据的，别改）：

- **来源 = `artifacts/games/run-*/`，不走 `dataset/`**：`dataset/game-NNNN`（45–65 局）与
  `dataset/runs/` 是同一批 run 的两个区，naive 遍历会重复计数（见 `dataset/README.md`）。
- **train/val 按 run 整局切**（默认 `runs[::5]`，在过滤后的合格局集上算）：同一局的几千条
  决策高度相关，**有效样本量 ≈ 局数（63），不是 52,107**；打散到样本级会得到假好的 val loss。

### 输出文件（`dataset/export/`，派生数据，已 gitignore，勿提交）

| 文件 | 内容 |
|---|---|
| `sft_train.jsonl` / `sft_val.jsonl` | 每行 `{id, prompt, completion, meta}`；meta 含 `run / review_no / t / stance_before / teacher / result / terminal_report / schema / conf_min` |
| `rl_trajectories.jsonl` | 每局一行 `{run, review_no, teacher, result, reward, terminal_report, t_end, ticks, crisis_ticks, n_steps/n_decisions/n_actions, steps[]}`；`reward`: victory→1.0 / defeat→0.0 / 无终局→null。steps 规则：带 `t` 的事件（decision/obs/loss/kill/report）各开一步，`action`/`produce_skip` 挂到最近一步 |
| `dpo_pairs.jsonl` | 影子评测分歧处每 qid 一对：`{id, prompt, chosen(Jev), rejected(clef), meta}`；**不受 `--era` 影响**（本就是跨时代对照） |
| `stats.json` | 本次过滤参数 + 计数 + 长度分位 + teacher/胜负/问题集/置信度分布 + val 局清单 |
| `README.md` | 生成时自述：本目录是什么、用了什么参数、如何复现 |

## 四、工具链

| 环节 | 工具 | 说明 |
|---|---|---|
| 索引入库 | `scripts/build_dataset.py` | 把 run 并入 `dataset/`（SFT/RL 资产的长期索引，不是训练格式） |
| **后训练导出** | `scripts/export_training.py` | 本文档的主角：产出训练器直接吃的文件 |
| 回归评测 | `scripts/shadow_eval.py replay` + `analyze` | 把 `(state, questions)` 重放给本地 clef-flash，与存档 Jev 答案对比；结果 `artifacts/shadow_eval/results.jsonl` + 报告 |
| 训练侧 | 任意吃 prompt-completion/chat JSONL 的框架 | transformers+peft / trl / LLaMA-Factory / unsloth 均可 |
| 服务化 | llama.cpp + GGUF | LoRA 微调 → merge → 转 GGUF（建议与现部署同档 Q8_0） |

## 五、实测五个坑

1. **有效样本量 ≈ 局数**：见 §三的切分决定；val loss 会抖，别用它当唯一信号。
2. **置信度普遍偏低**：全量样本 `conf_min` 均值 **0.214**（Jev 集 0.312 / p50 0.30 / p90 0.46）——
   clef 概率尾部压缩是已量化特性（p90 0.70 vs Jev 0.82）。建议 `--min-conf` 过滤或在训练里按
   `meta.conf_min` 加权，别把低置信摆动学进去。
3. **问题集按 tick 条件化**（不是"后来才加的问题"）：completion 只含 prompt 出现的 qid。
4. **19 个无终局 run**（含 94/96 局）：可进 SFT；RL 轨迹里 `reward=null`，不能当负样本。
5. **奖励只有终局**：RL 想做稠密奖励，从 `obs`（credits/my_val/en_val/tanks…）与
   `loss`/`kill` 流自造 shaping；语料只保证终局标签。

## 六、首轮配方（建议按此推进，每步单变量）

```bash
# SFT-1 蒸馏（强教师）: 27 局 / 14,045 条 → 看能否超过 clef 基线
uv run python scripts/export_training.py --era jev --out dataset/export/jev

# SFT-2 克隆+稳健: 全量，或按置信度筛（例: conf>=0.4）
uv run python scripts/export_training.py --out dataset/export/all --min-conf 0.4

# DPO（可选）: 828 条分歧 → 1,632 对（build 590 / stance 506 / inf 296 / veh 240）
#   直接用 dataset/export/dpo_pairs.jsonl（与 SFT 集同目录生成）
```

**评测门槛**（`artifacts/shadow_eval/report.md` §四，Q8_0 基线；训练后必须重跑同一批对照）：

| 指标 | 基线（clef Q8_0 vs Jev） |
|---|---|
| choice 对齐率 | inf 58.6% / veh 58.5% / build 37.8% / stance 49.5% |
| threat noul | 相关性 r=0.815，平均偏差 -0.026 |
| stance 闸门(0.45) 一致率 | 72.9% |

影子评测只能证明"更像 Jev"，**胜负效果必须实局 A/B**（单变量纪律，见 `docs/METHODOLOGY.md`）。

## 七、红线与索引

- 原始语料（`artifacts/games/`、`dataset/` 载荷）**只增不改**（`AGENTS.md` 红线）；
  `dataset/export/` 是派生区，随时可用脚本重建，**不要提交**（已在 `.gitignore`）。
- 导出与训练**不涉及密钥**：样本只有游戏状态与 doctrine 文本，决策模型密钥只在 Python 进程内。

| 想知道什么 | 看哪 |
|---|---|
| 语料索引 / 质量分层 / 编号口径 | `dataset/README.md`、`dataset/MANIFEST.jsonl` |
| 本地 clef-flash 部署、契约对照、切换手册 | `docs/CLEF-LOCAL.md` |
| 决策模型契约与问题形态 | `docs/JEV-INTEGRATION.md`、`src/ra2web_jev_player/jev/client.py` |
| 迭代纪律（单变量、证据规则） | `docs/METHODOLOGY.md` |
| 导出脚本参数与实现 | `scripts/export_training.py`（`--help`）、`tests/test_export_training.py` |
