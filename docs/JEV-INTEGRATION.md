# Jev 接入：调用封装、参数迭代与官方候选组参考

> 三个时代的接入方式都记录在此：自研直连（第 1-20 局）→ 官方播放器+HTTP 桥接
> （第 21-22 局，`bridge.py` 已删除，协议存 git 历史）→ **自包含架构（2026-09-26 起）**。

## 一、现行架构：Python 直调 TypeSafe（`src/ra2web_jev_player/jev/client.py`）

- 端点 `{JEV_BASE_URL:-https://api.typesafe.ai/v1}/systemone`，POST `{state, questions, model}`；
  环境变量：`TYPESAFE_API_KEY`（必填）、`JEV_BASE_URL`、`JEV_MODEL`（默认 jev-latest）、
  `JEV_MAX_CALLS`（默认 1500，进程内预算）。
- **[2026-10-04 已切本地]** `client.py` 代码默认已改 `http://127.0.0.1:8085/v1` + `clef-flash`
  （本地 llama.cpp，不校验密钥），Jev 云端两行以注释保留在 `client.py`，回切即恢复；
  本节环境变量覆盖关系不变（设 `JEV_BASE_URL` 仍可指回云端）。详见 `CLEF-LOCAL.md`。
- 三题型：choice（criteria=选项→描述字典）/ score（有序档位数组）/ noul（概率；
  **答案键是 `noul` 不是 `probability`**）。一次请求批量问全部问题。
- 429/5xx 指数退避重试（4 次）；gzip 兜底解压；决策/错误/token/延迟统计进程内维护。
- **密钥只在 Python 进程内**，绝不进页面/日志/代码（官方文档同立场）。

## 二、页内执行层（`src/ra2web_jev_player/werhd/client.js`）

- `eval --stdin` 注入（~15KB，超 cmd.exe 8191 argv 上限）；`window.__rj` 暴露
  snapshot/orders/micro。指令统一过 ≤5 分批、同目标 12s 节流、per-unit 18 tick 冷却、
  deploy 45s 节流——实测约束全文见 `../src/ra2web_jev_player/werhd/api.md` §六。
- 微操 setTimeout 链 150ms（不用 onTick，避开 8ms 预算）；浏览器启动参数必须含
  `--disable-background-timer-throttling`（否则 headless 页面 setTimeout 被节流到 ~1s/次）。

## 三、Jev 调用参数（20 局验证，仍全面有效）

### 3.1 上下文投喂清单（`strategy/questions.py`，顺序经 20 局验证）

1. 战场快照：时间/资金/电力余量/雷达/建筑清单（中文名+数量）/部队/四类队列状态/可造列表（中文名+造价）
2. 敌情：按护甲归类 + **自动附克制建议**（"灰熊=重甲 → 犀牛/磁暴线圈/磁暴步兵(100%)"）
3. 事件流（新→旧）：受击明细（-X 血）/单位损失/敌逼近距离与编成
4. 力量对比：我方≈X 金 vs 视野内敌军≈Y 金（按造价折算）+ 受袭频率（N 次/2 分钟）
5. DOCTRINE（作战手册蒸馏，~1.5k 字符）：铁律/克制常识/目标优先级/五态态势机/时间窗

### 3.2 参数迭代记录（闭环产物）

| 参数 | 初值 | 现值 | 来历 |
|---|---|---|---|
| 态势切换置信度闸门 | 0.45 | 0.45（保持） | 防摇摆；低置信沿用原态势 |
| 威胁强制回防 | p>0.6 | p>0.6（保持） | 实测多次 0.7-0.9 正确预警 |
| 建造队列问题 | 全选项 | 精炼厂 ≤2 座后从候选中剔除 | 防赤字扩张致引擎过载 |
| 造兵问题 | 全选项 | 军犬 ≥4 只后剔除；兵营 ≥2 后剔除 | 曾失控造 23 条狗/多兵营 |
| 态势选项 | develop/defend/attack | 五态（+rush/recover） | 对齐攻略状态机 |
| stance 指令纪律 | 无 | "8 分钟内除非主力全灭不选 recover；受袭≥3次/2分钟选 DEFEND" | 第 18 局复盘 |
| 反击条件 | 无条件全军反击 | 兵力 ≥1.2× 敌军才反击，否则守塔(TURTLE) | 第 19/20 局复盘 |

### 3.3 经济学事实（用于成本核算）

- Jev 定价 $0.042/Mtok 输入、输出免费；一次五问批量 ≈ $0.001 级。
- 官方体系实测 ≈1900 tok/决策 × 600 决策上限/局 ≈ 114 万 tok/局 ≈ **$0.05/局**。

## 四、官方候选组设计（未来演进参考）

官方 `werhd-jev-player.mjs` v8.3（`references/werhd/examples/jev/`，只读参考）把决策组织成
**候选组**：construction/vehicles/infantry/deployment/tactics/scouting 六个基础组，
special 层按需注入 garrison/transport/engineering/salvage/defenses/navy/aircraft；
每次请求**筛出 criteria>1 的组、按优先级+最久未问排序、取前 8 组**一次发出。
每组 `{instructions, criteria:{wait:"…", <key>:"…"}, actions:{<key>: action}}`，
answer→action 类型：produce/set_deployed/mission(rally|defend|attack|retreat|explore)/
special/cancel/sell/deploy/attack/move。

官方的执行纪律值得抄：
- **执行前复查**：单位还在/队列仍空/可造仍含该名/资金≥minCredits/目标仍可见；
- **任务连续性**：同 mode 且目标点差 <5 格且 <180 tick → 跳过（防指令抖动）；
- **过期快照丢弃**：决策返回时快照已老 >180 tick → 丢弃；
- **冷却全是用户侧 Map**（特种 450 tick / 姿态 20 tick / 微操补发 18 tick / 放置 20 tick）。
- 官方教训：vehicle 组连续 wait → 生产问题必须带**兵力目标与可支付性**判断
  （strategy.mjs operationalGoals：地面战车 min(24, max(12, nearby*1.5))、进攻门槛 8）。

## 五、官方资料的复制来源

`references/werhd/` 内容复制自 the official documentation repository (ra2web-werhd / ra2web.github.io)；
**类型真相源** `werhd-player-api.d.ts` 在官方仓库根（refs 快照没有，已复制到
`src/ra2web_jev_player/werhd/`）。官方曾在本地 v6 完整获胜 16:24（摧毁 40/损失 3），
v8.3-recovery-naval 为当前版本线。


### 3.1 TypeSafe 请求形状（tsj 直连）

```json
{"state": "<文本或对象>", "questions": {
  "qid": {"type": "choice",  "instructions": "...", "criteria": {"选项A": "描述A", "hold": "不做"}},
  "qid2":{"type": "noul",    "instructions": "..."},
  "qid3":{"type": "score",   "instructions": "...", "criteria": ["档1","档2","档3"]}}}
```
- criteria：choice=对象（键即选项）、score=有序数组（≥2 档）、noul 可省。
- 返回：`answers[qid] = {type, choice|noul|score, confidence, probabilities}`；**noul 的键是 `noul` 不是 `probability`**。

### 3.2 上下文投喂清单（经 20 局验证的顺序）

1. 战场快照：时间/资金/电力余量/雷达/建筑清单（中文名+数量）/部队/四类队列状态/可造列表（中文名+造价）
2. 敌情：按护甲归类 + **自动附克制建议**（"灰熊=重甲 → 犀牛/磁暴线圈/磁暴步兵(100%)"）
3. 事件流（新→旧）：受击明细（-X 血）/单位损失/敌逼近距离与编成
4. 力量对比：我方≈X 金 vs 视野内敌军≈Y 金（按造价折算）+ 受袭频率（N 次/2 分钟）
5. DOCTRINE（作战手册蒸馏，~1.5k 字符）：铁律/克制常识/目标优先级/五态态势机/时间窗

### 3.3 参数迭代记录（闭环产物）

| 参数 | 初值 | 现值 | 来历 |
|---|---|---|---|
| 态势切换置信度闸门 | 0.45 | 0.45（保持） | 防摇摆；低置信沿用原态势 |
| 威胁强制回防 | p>0.6 | p>0.6（保持） | 实测多次 0.7-0.9 正确预警 |
| 建造队列问题 | 全选项 | 精炼厂 ≤2 座后从候选中剔除 | 防赤字扩张致引擎过载 |
| 造兵问题 | 全选项 | 军犬 ≥4 只后剔除；兵营 ≥2 后剔除 | 曾失控造 23 条狗/多兵营 |
| 态势选项 | develop/defend/attack | 五态（+rush/recover） | 对齐攻略状态机 |
| stance 指令纪律 | 无 | "8 分钟内除非主力全灭不选 recover；受袭≥3次/2分钟选 DEFEND" | 第 18 局复盘 |
| 反击条件 | 无条件全军反击 | 兵力 ≥1.2× 敌军才反击，否则守塔(TURTLE) | 第 19/20 局复盘 |

### 3.4 经济学事实（用于成本核算）

- Jev 定价 $0.042/Mtok 输入、输出免费；一次八问批量 ≈ $0.001 级。
- 官方体系实测 ≈1900 tok/决策 × 600 决策上限/局 ≈ 114 万 tok/局 ≈ **$0.05/局**。

## 四、官方资料的复制来源

`references/werhd/` 下所有内容复制自 the official documentation repository (ra2web-werhd / ra2web.github.io)：
`player-console-api.md`（werhd 完整 API）、`jev-player-local.md`（官方 Jev 玩家接入规格、启动步骤、六局实测记录——**官方曾以 16:24 获胜：摧毁 40/损失 3**）、`jev-player-goal-audit.md`（阶段验收）、`examples/`（玩家/目录/策略/特殊行动/摄像机/看板源码，v8.3）。

## 六、本地 clef-flash 候选后端（2026-10-04，影子评测完成）

Jev 云账号余额耗尽后的替代后端已落地：Cloudflare 开源决策模型 clef-flash（9B，
Jev/SystemOne 兼容），经 llama.cpp（master 11fe021 自编译）跑在本机 4060 Ti 上，
端点 `http://127.0.0.1:8085/v1/systemone`，**与本文件 §3.1 的请求/响应契约逐字段
一致**（含 noul 答案键 = `noul`），`JEV_BASE_URL=http://127.0.0.1:8085/v1` +
dummy key 即零代码切换。影子评测（828 条历史 decisions.jsonl 重放 vs 存档 Jev
答案）：threat noul r=0.815 但尾部压缩致 0.6 阈值漏报主导（建议 0.55）、stance
0.45 闸门保持、build/inf/veh 对齐率与分歧风格详见报告。

**全量档案（部署定谳/GPU 预算/影子评测/阈值建议/切换手册/踩坑）：
`docs/CLEF-LOCAL.md`；影子评测工具 `scripts/shadow_eval.py`，报告
`artifacts/shadow_eval/report.md`。**
