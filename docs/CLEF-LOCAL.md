# CLEF-LOCAL —— 本地 clef-flash 决策后端：调研、部署、影子评测与切换手册

> 本文档记录 2026-10-04 一个独立 session 完成的 Clef 本地化全链路：模型调研 →
> llama.cpp 引擎升级与自编译 → 双量化档部署 → 828 条历史决策影子评测 → 阈值
> 漂移结论与切换手册。**对应 HANDOFF §一"暂停开新局（Jev 余额耗尽）"的解法。**
> 全程未调用 Jev 云 API（账号已无余额，所有 Jev 对照答案取自 `logs/games/run-*/`
> 的历史落盘记录）。

## 〇、当前状态速览

| 项 | 状态 |
|---|---|
| 本地服务 | ✅ 已部署并留驻：`http://127.0.0.1:8085/v1/systemone`（llama.cpp） |
| 契约 | ✅ 与 TypeSafe 逐字段核对一致（answers 按 qid 键控 / choice+confidence+probabilities / **noul 答案键是 `noul` 不是 `probability`**） |
| 影子评测 | ✅ 完成：828/828 条重放零失败，报告 `out/shadow_eval/report.md` |
| 切换 | ✅ **已切流（2026-10-04）**：`client.py` 默认 base_url/model 改 `127.0.0.1:8085` + `clef-flash`，Jev 云端两行注释保留可回切；threat 0.55 与 max_decisions 上调仍**待用户拍板** |
| 默认档 | Q8_0（最佳校准精度）；Q4_K_M 保留为共存档 |

## 一、Clef 是什么（调研结论，2026-10-04）

Cloudflare 开源的**决策模型**（Apache-2.0），本质是 Jev/SystemOne 的开源对等物，
README 明说 API fully compatible。**不是聊天模型**：输入 state（文本/JSON）+
类型化问题（choice/noul/score——与本项目 `jev/client.py` 用的三种题型一致），
**单次前向直接输出每个选项的 logit/概率**，无文本生成、无输出解析。

- 两个尺寸：**clef** 27B（Qwen3.8-27B 底座，多模态）与 **clef-flash** 9B（Qwen3.5-9B 底座）。
- 官方 Decision Index 0.2.1（41 项基准，Cloudflare 自家跑分）：clef-flash 单项冠军
  16 行居首，BFCL 98.8（Jev 95.8）；但重推理项（BBH/MMLU-Pro/GPQA）Jev 明显更强。
  对本项目的意义：bot 的克制建议/DOCTRINE 是预计算注入 state 的，Jev 只做
  "带注释候选里选择 + 出校准概率"——正是 clef 系的甜点区，Jev 的推理优势基本被架构绕开。
- 时间线（时效关键）：2026-10-02 Cloudflare 发布 + llama.cpp 当天合入
  [/v1/systemone 决策端点（PR #29818）](https://github.com/ggml-org/llama.cpp/pull/29818)；
  clef 架构支持随后合入（[PR #29831](https://github.com/ggml-org/llama.cpp/pull/29831)，**text-only**，
  图片输入待上游跟进——本项目纯文本投喂，不受影响）；ggml-org 同日发布官方
  [Clef-Flash-GGUF](https://huggingface.co/ggml-org/Clef-Flash-GGUF) /
  [Clef-GGUF](https://huggingface.co/ggml-org/Clef-GGUF)。
- **正式 release v0.5.0（09-23）不含 clef，必须用 master ≥ 10-02**（本机因此自编译，见 §二）。
- 27B 的 clef Q4 就要 17.9GB，超 4060 Ti 16GB 显存——本机只考虑 clef-flash。

## 二、本机部署定谳（2026-10-04 实测）

### 2.1 引擎：llama.cpp master 自编译

| 项 | 值 |
|---|---|
| 现役 | `D:\Tools\llama-cuda` = master **11fe021**（2026-10-04 拉取，含 #29818+#29831），CUDA 12.9 + MSVC 19.44 + Ninja，**sm89-only**（4060 Ti Ada，单架构省一半编译时间） |
| 旧版 | `D:\Tools\llama-cuda-b11206`（9 月底版，**不含 clef**，仅作回滚备份——其他 8080 脚本仍可用它回滚） |
| 源码/重编 | `D:\Tools\llama.cpp-src`，重编译跑其中 `build_local.bat`（约 3-5 分钟） |
| 换装方式 | 直接覆盖 PATH 里的 `D:\Tools\llama-cuda`（gemma/ornith 等 8080 脚本无缝受益新版） |

### 2.2 模型（E:\models，来自 hf-mirror.com/ggml-org/Clef-Flash-GGUF）

| 档位 | 文件 | 大小 | 显存实测 | 定位 |
|---|---|---|---|---|
| **q8（默认）** | `Clef-Flash-Q8_0.gguf` | 9.0 GiB | **10.8 GB** / 16GB | 最佳校准精度（最贴参考实现） |
| q4 | `Clef-Flash-Q4_K_M.gguf` | 6.0 GiB | 8.2 GB / 16GB | 共存档（与 ComfyUI 等其他 CUDA 大活并行时用） |

字节数均与 HF 仓库一致（Q8_0=9657260096 / Q4_K_M=6486448192）。

### 2.3 启停脚本（D:\model-scripts）

| 脚本 | 说明 |
|---|---|
| `start_clef-flash.bat [q8\|q4]` | 前台控制台启动（同 start_laya/gemma 惯例），**参数选档，缺省 q8**；含 8085 端口清理与文件存在性检查；冷加载 40-70s |
| `stop_clef-flash.bat` | 按 8085 端口杀进程树（**绝不能** taskkill /IM llama-server.exe，会误杀 8080 的实例） |
| `status_clef-flash.bat` | health + models + GPU 一览 |

GPU 关键参数（脚本注释有逐条理由）：`-ngl 99`（全层常驻 GPU，i5-11400F 纯旁观）、
`-fa on`、`-c 16384`（决策 payload ~2-3K tok 的 5 倍余量；**不要开模型默认 256K**，KV 白吃显存）、
**KV 保 f16 不量化**（决策模型的价值就是校准概率，不省这笔）、`-b/-ub 4096`（≥单请求体，
规避 llama.cpp #29902 同路径的多问批量 n_ubatch 中止）。热请求延迟 **0.5-0.7s**（单次 prefill，
GPU 100% 脉冲），优于云端 Jev 的 ~1.1s RTT。

### 2.4 端口地图（防冲突）

laya=8000 / gemma+ornith=8080 / **clef-flash=8085** / SemIf=8122。

## 三、API 契约实测（与 TypeSafe 一致性）

- 端点：`POST http://127.0.0.1:8085/v1/systemone`，body `{state, questions}` 与
  `jev/client.py` 现行格式完全一致（state 允许字符串或对象——63 局后的 DYNAMIC
  SITUATION 结构化 dict 实测可过）。
- 响应：`answers[qid] = {type, choice|noul, confidence, probabilities}`；
  **noul 的答案键是 `noul`**（client.py 注释里强调的坑，llama.cpp 实现与 TypeSafe 对齐）。
- 切换成本：`client.py` 本来就读 `JEV_BASE_URL` 环境变量——本地模式设
  `JEV_BASE_URL=http://127.0.0.1:8085/v1` 即可；`TYPESAFE_API_KEY` 本地不校验，
  配任意 dummy 值过必填检查（**真实密钥照旧只留 Python 进程内，绝不写盘**）。
- 单次前向确定性：同请求两次结果逐位一致。

## 四、影子评测（2026-10-04，Q8_0）

### 4.1 方法

- 数据源：27 个 run 目录的 `decisions.jsonl`（sft_tuple：完整 state+questions+Jev 答案），
  共 14045 条，**分层等步抽样 828 条**（按局按时间均匀覆盖，t 从 11 到 6727 游戏秒，
  含 63 局前中文投喂与 63 局后英文投喂两时代）。
- 重放：原始 (state, questions) 原样打本地 Q8_0，与存档 Jev 答案对照。零失败。
- 工具：`out/shadow_eval.py`（replay/analyze 两段式，results.jsonl 断点续跑；
  全量重放约 4 小时，跑 `python out/shadow_eval.py replay` 自动补齐）。

### 4.2 主结果（en 时代 n=535，全样本趋势一致）

| 维度 | 结果 |
|---|---|
| choice 对齐率 | inf 58.6% / veh 58.5% / build 37.8% / stance 49.5%（随机基线 25-40%；inf/veh 是真信号） |
| threat noul | 相关性 **r=0.815**，平均偏差 -0.026（几乎无偏），平均绝对偏差 0.112 |
| stance 闸门(0.45) | 生效态势一致率 **72.9%**；Jev 切态势 23 次 clef 沿用原态势 16 次 |
| threat 0.6 触发 | 双触发 73 / **Jev 触发 clef 漏报 53** / clef 误报 26 / 双不触发 383 |

### 4.3 深挖发现

1. **clef 概率尾部压缩**：Jev p90=0.820 vs clef p90=0.700——clef 不爱给极端值。
2. **threat 0.6 漏报不对称**：漏报是误报的 2 倍；**Jev 高烈度威胁(>0.75)有 26% 被
   clef 压到 0.6 以下**（降 0.55 后漏 18%，漏/误平衡 44/38）。rush 型 roll 是当前主要
   败因，漏报代价（基地被打）≫ 误报代价（坦克白跑）。
3. **clef 置信度系统性偏低**（stance conf 均值 0.482 vs Jev 0.725），0.45 闸门天然
   变保守——恰是"防摇摆"设计的保守方向；闸门扫描证明**下调反而降低一致率**
   （0.45=72.9% 已是最优）；clef conf>0.45 占 45%，闸门功能完好。
4. **build 低对齐是风格差不是噪声**：hold 率 Jev 36% vs clef 6%——clef 几乎从不停建
   （hold→造精炼厂/电厂/兵营各 ~46 次），扩张明显更激进；veh 主力一致（HTNK→HTNK
   51%）；inf clef 更谨慎（hold 51% vs 29%）。

### 4.4 结论与建议（2026-10-04 用户拍板，实施状态见右列，实施记录见 §八）

| 项 | 建议 | 依据 | 实施 |
|---|---|---|---|
| threat 触发阈值 | **0.6 → 0.55** | 尾部压缩导致漏报主导；rush 是当前主要败因 | ✅ `doctrine.py` THREAT_FORCE_DEFEND=0.55 |
| stance 闸门 | **0.45 保持** | clef 低置信+保守正是防摇摆本意，扫描证明 0.45 最优 | ✅ 未动 |
| 接入方式 | `JEV_BASE_URL=http://127.0.0.1:8085/v1` + dummy key | client.py 现成开关，契约零改动 | ✅ 更进一步: client.py 默认值直切本地，Jev 两行注释保留 |
| 实局流程 | 先 q4 冒烟一局（显存可与浏览器共存）→ q8 正式 A/B | 单变量纪律；影子评测只能量化分歧，**质量优劣必须实局定论** | ⏸ q8 已重启在驻，冒烟/开局待用户号令 |
| 决策预算 | clef 本地无按量成本，可放开或大幅上调 | 本地调用零边际成本 | ✅ 按后端分流: 本地实质不限 / **云 Jev 保持 1200**（用户定谳） |
| teacher 字段 | §五.7 建议: sft_tuple 区分 jev/clef | SFT 资产溯源 | ✅ 已加，约定见 §八 |

### 4.5 局限性声明

- 影子评测只能回答"clef 与 Jev 差在哪"，**不能回答"clef 打得更好吗"**——风格差异
  （更激进扩张/更谨慎补兵）的胜负效果只能实局 A/B。
- 单量化档（Q8_0）；Q4_K_M 未做对照重放（架构同源，契约已另验）。
- 样本 6%，两时代混叠（09-29/30 恰是中→英切换期）；统计置信 ±3% 量级。

## 五、切换手册（恢复对战 checklist；2026-10-04 已按此执行，实施记录见 §八）

1. `D:\model-scripts\start_clef-flash.bat`（默认 q8；要与 ComfyUI 并存就先 `q4`）；
2. 对局进程环境：`JEV_BASE_URL=http://127.0.0.1:8085/v1` + `TYPESAFE_API_KEY=dummy`；
3. 按用户拍板调 `threat` 触发阈值（0.55 建议）——在 `strategy/planner.py` 的闸门处，
   走单变量纪律；
4. `JEV_MAX_CALLS` 上调（本地零成本）；
5. 先跑一局 q4/或直接 q8，**每局照旧停下汇报**；
6. 回滚 = 去掉 `JEV_BASE_URL`（回云端）——但注意 Jev 云账号余额已耗尽，回滚前先确认；
7. 账本与复盘照旧，`decisions.jsonl` 照常落盘（本地 clef 的标签同样进 SFT 资产，
   **建议给 sft_tuple 加 teacher 字段区分 jev/clef**——属数据格式变更，动前先汇报）。

## 六、踩坑记录（本 session 实证，机器级教训）

1. **bat 文件必须纯 ASCII**：UTF-8 中文注释会被 GBK cmd 解析器撕碎（行断裂成命令，
   连 chcp 65001 都救不了）。本项目三个 clef 脚本已全 ASCII，中文说明在 README.md。
2. llama.cpp 新版日志参数是 **`--log-file`**（旧 `--logfile` 已删，报 invalid argument；
   若藏在 start /min 最小化窗口里极难发现）。
3. Git Bash 调 bat 的坑：MSYS timeout/curl 遮蔽同名 Windows exe（脚本内 sleep 用
   `ping -n 3`、curl 用 `%SystemRoot%\System32\curl.exe` 绝对路径）；bash→cmd 长引号串
   易碎，测 bat 用探针 bat 文件而非内联。
4. VS Build Tools 2022 装在 **x86 Program Files**（`C:\Program Files (x86)\...`），
   排查编译器别只扫 `C:\Program Files`；VS 生成器缺 CUDA MSBuild 集成时报
   "No CUDA toolset found"，用 Ninja 生成器绕过（BuildTools 自带 ninja.exe）。
5. CUDA 12.9 + MSVC 19.44 兼容（无版本闸门拦截），sm89-only 编译 3-5 分钟。
6. HF 下载走 hf-mirror.com（国内直连快，6GB≈3 分钟）；huggingface.co 直连被 DNS 污染。

## 七、文件与来源索引

| 项 | 位置 |
|---|---|
| 影子评测工具 | `out/shadow_eval.py` |
| 影子评测结果 | `out/shadow_eval/results.jsonl`（828 条，可续跑全量） |
| 影子评测报告 | `out/shadow_eval/report.md`（含本文件 §四 全部数字） |
| 启停脚本 | `D:\model-scripts\{start,stop,status}_clef-flash.bat`（说明：`D:\model-scripts\README.md`） |
| 引擎 | `D:\Tools\llama-cuda`（master 11fe021）/ 备份 `llama-cuda-b11206` / 源码 `D:\Tools\llama.cpp-src` |
| 模型 | `E:\models\Clef-Flash-{Q8_0,Q4_K_M}.gguf` |
| 模型卡 | https://huggingface.co/Cloudflare/clef 、https://huggingface.co/Cloudflare/clef-flash |
| GGUF | https://huggingface.co/ggml-org/Clef-Flash-GGUF |
| llama.cpp 决策端点 | PR #29818（/v1/systemone，2026-10-02 合并）、PR #29831（clef 架构，text-only） |
| Decision Index 跑分 | https://clef-evals.workers-ai-mle.workers.dev |
| Cloudflare 公告 | https://blog.cloudflare.com/clef-decision-models |

## 八、切流实施记录（2026-10-04，用户拍板执行）——历史查证锚点

> 本节回答" clef-flash 到底是哪天、改了哪些文件、从哪局开始生效、历史数据怎么归属"。

### 8.1 实施清单（全部已落盘）

| # | 改动 | 位置 | 说明 |
|---|---|---|---|
| 1 | 默认端点/模型切本地 | `src/ra2web_jev_player/jev/client.py` `DEFAULT_BASE_URL`/`DEFAULT_MODEL` | `127.0.0.1:8085` + `clef-flash`；**Jev 云端两行注释原样保留**，回切=交换注释（先确认云余额）；全仓唯一硬编码端点 |
| 2 | threat 阈值 0.6→0.55 | `src/ra2web_jev_player/strategy/doctrine.py` `THREAT_FORCE_DEFEND` | 依据 §四（clef 尾部压缩→漏报主导）；代码注释含完整依据链 |
| 3 | 决策预算按后端分流 | `client.py`（`CLOUD_MAX_CALLS=1200`/`LOCAL_MAX_CALLS=999999`）+ `cli.py`（`--max-decisions` 缺省 None→按后端解析） | **本地实质不限、云 Jev 保持 1200**（用户定谳"对于 jev 保持上限"）；env `JEV_MAX_CALLS` 或显式 `--max-decisions` 可覆盖 |
| 4 | sft_tuple 加 `teacher` | `src/ra2web_jev_player/game.py` `_jev_ask` | 值 = `JevClient.backend`（`"clef"`/`"jev"`），约定见 8.2 |
| 5 | 服务重启 q8 | `D:\model-scripts\start_clef-flash.bat q8` | 健康检查通过；真实 `JevClient` 全链路实测（choice 含校准概率，~0.5s 级延迟，优于云端 ~1.1s） |

### 8.2 `teacher` 字段与历史数据归属约定（SFT 资产查证用）

- `decisions.jsonl` 的 sft_tuple **自切流后首局（第 70 局）起**新增 `"teacher"` 字段：
  `"clef"`=本地 clef-flash 出签，`"jev"`=云端 TypeSafe Jev 出签。
- **凡无 `teacher` 字段的 sft_tuple 一律为 Jev 时代产物（第 1-69 局，2026-09-26 起）**
  ——该期仅单教师，无歧义；旧读取器忽略未知键即可兼容（纯增量变更）。
- `teacher` 只区分后端家族；同族内细分（clef q8/q4 量化档、未来模型升级）以
  run 目录时间戳 + 对应日期 git 提交 + 本节为准，不逐次加字段。
- 数据格式红线（AGENTS.md：格式变更动前汇报）已履行：用户 2026-10-04 批准
  （"听从你的建议，加上 teacher，并在文档中记录背景"）。
- **勘误（2026-10-04 晚）**：曾疑 run-20261004-113223 为"无 teacher 的 clef 冒烟局"，
  实为**全局第 69 局（Jev 收官局，花光最后余额，e667680 存档）**——流水号/全局号
  双轨编号所致误判；"无 teacher 字段 = Jev 时代"约定**无例外成立**。全局第 70 局
  （run-20261004-154529）才是 clef 首正式局，1287 条决策全部带 teacher=clef。

### 8.3 生效起点与归因纪律

- 切流后首局（第 70 局）同时生效三项：clef-flash 教师 + threat 0.55 + 预算实质不限；
  另有 e115be9 反囤积+编队出击包（早已实施、同样待实战验证）。
- **该局对第 69 局基线是多变量对照，严格单变量归因不成立**——后端切换本身即最大
  变量。threat 0.55 的独立效果需 clef 稳定后另行单变量验证。
- 影子评测（§四）已完成 clef-vs-Jev 分歧量化；质量优劣以实局 A/B 为准。
