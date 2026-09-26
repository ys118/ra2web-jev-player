# Jev 接入：桥接协议、官方玩家架构与参数迭代

> 两个时代的接入方式都记录在此：自研直连（第 1-20 局）与官方体系（第 21 局起）。
> 当前推荐：**官方 `werhd-jev-player.mjs`（页内）+ 自建 `bridge/bridge.py`**。

## 一、为什么切到官方体系

自研 Python 循环（`legacy-bot/bot.py`）的教训：
- 每 tick 一个 Python 往返（状态 eval ≈ 0.05-0.3s + jev ≈ 1s + 指令 ≈ 0.2s），微操反应在 **秒级**；
- 所有微操都要过网络/进程，天然被节流与冻结放大。

官方体系把两类循环分层：
- **`micro()` 每 150ms 在页内跑（零网络）**：可见射程内集火（按威胁评分）、空闲矿车恢复采矿（`map.tile` 扫描 `LandType.Tiberium`）、建筑 <80% 自动维修、`canPlace` 落位、GI 类单位展开/收起姿态、镜头导播；
- **`decide()` 每 600ms 请求模型**：只做宏观选择（建什么/造什么/打哪/集结还是撤退），带**任务连续性**（同任务 5 格内 180 tick 不重发）、**过期快照丢弃**（180 tick）、**执行前复查**（单位还在不在/队列/资金有没有变）。

实测（第 21 局，本机桥接）：
| 指标 | 值 |
|---|---|
| 决策批延迟 | P50 1000ms / P95 1343ms |
| 单批 token | ≈1900（state+候选组） |
| 失败 | 0（85+ 批） |
| 覆盖动作 | deploy/produce(NAPOWR,SHK,HTNK,HTK,NARADR)/落位/侦察/防御/装运 |

## 二、桥接协议（`bridge/bridge.py` 实现）

| 端点 | 方法 | 说明 |
|---|---|---|
| `/player.mjs` | GET | 官方玩家入口（以及 `/werhd-jev-*.mjs` 同目录模块），从 `refs/examples/jev/` 服务 |
| `/decide` | POST | 请求 `{state, groups:{gid:{instructions, criteria}}}` → 单次 TypeSafe 批量提问 → `{answers:{gid:{choice,confidence,probabilities}}, latencyMs, model, usage}` |
| `/event` | POST | 逐条事件审计（写 `logs/jev-events.jsonl` + 控制台摘要） |
| `/events` | GET | SSE 实时事件流（官方看板用） |
| `/` | GET | 官方看板页面 |
| `/status` | GET | 决策数/错误/延迟 P50/P95/token 统计 |

- **每个候选组=一道 Choice 题**：`instructions` 即组说明，`criteria` 即"选项→该选项的详细描述"（官方脚本天然长这样，与 TypeSafe choice 完美匹配）。
- **一次请求问完所有组**（官方设计如此，与 tsj 批量原则一致）。
- 依赖环境变量：`TYPESAFE_API_KEY`（必填）、`JEV_BASE_URL`、`JEV_MODEL`、`JEV_MAX_CALLS`。
- 踩坑：TypeSafe 响应 gzip（`Accept-Encoding: identity` + gzip 解压兜底）；请求体解码降级链 utf-8→gbk→replace。

挂载（游戏页控制台或自动化 eval）：
```js
const { attachJevPlayer } = await import('http://127.0.0.1:5174/player.mjs')
window.werhdJev = await attachJevPlayer(window.werhd)
// 查看/停止: werhdJev.status / werhdJev.stop()
// 摄像机: werhdJev.setAutoCamera(false)
```

## 三、自研时代的 Jev 调用参数（仍然有效，供调优参考）

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

`refs/` 下所有内容复制自 `D:/projects/ra2web.github.io/docs/`（游戏官方文档仓库）：
`player-console-api.md`（werhd 完整 API）、`jev-player-local.md`（官方 Jev 玩家接入规格、启动步骤、六局实测记录——**官方曾以 16:24 获胜：摧毁 40/损失 3**）、`jev-player-goal-audit.md`（阶段验收）、`examples/`（玩家/目录/策略/特殊行动/摄像机/看板源码，v8.3）。
