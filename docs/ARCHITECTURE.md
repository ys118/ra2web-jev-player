# 架构 —— 自包含的 ra2web-jev-player

> 2026-09-26 重构定稿：**去桥接化**。本 repo 不再依赖官方 `werhd-jev-player.mjs`
> 和本地 HTTP 桥接服务（`bridge.py` 已删除，协议存于 git 历史）；
> API 定义、浏览器驱动、策略、Jev 封装全部在 repo 内。

## 一、总体结构

```
┌─────────────────────────── 浏览器（agent-browser 无头会话）───────────────────────────┐
│  游戏页 https://gonghui.k0s.cn/                                                      │
│   ├─ window.werhd            官方玩家控制台 API（定义见 werhd/api.md + d.ts 副本）    │
│   └─ window.__rj             本项目自有页内客户端（client.js，经 eval --stdin 注入）  │
│       └─ micro() 每 150ms：集火/矿车恢复/维修/就绪落位/镜头/停摆与终局检测（零网络）   │
└──────────────────────────────┬─────────────────────────────────────────────────────┘
                               │ agent-browser CLI（eval -b / eval --stdin，子进程）
┌──────────────────────────────▼─────────────────────────────────────────────────────┐
│  Python（src/ra2web_jev_player/，uv 管理）                                          │
│   driver/browser.py   CLI 封装：会话/eval/快照/点击/超时树杀                          │
│   driver/launcher.py  启动状态机：冷浏览器→弹窗→菜单→配置→开局→注入（全自动 ~25s）    │
│   game.py             宏观循环 ~1.5s：快照→感知→清单→开局→侦察→Jev→机动→战报         │
│   strategy/planner/   确定性决策层（包: 记忆/感知/清单/开局/侦察/五态/机动/答案应用）  │
│   strategy/           阈值与作战手册(doctrine) + Jev 五问(questions) + 快照视图(state)│
│   review/             终局复盘引擎（包: 采集/记录/确定性分析/语义复盘/调参/产出）      │
│   jev/client.py       决策模型 /v1/systemone 封装（批量/重试/gzip/统计，密钥不出Python）│
│   audit.py            artifacts/logs/bot.log + jev-events.jsonl 审计                 │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 二、决策分层（贯穿项目的核心原则）

| 层 | 频率 | 职责 | 位置 |
|---|---|---|---|
| 微操 | 150ms | 集火、矿车恢复、维修、落位、镜头、停摆/终局检测 | 页内 client.js（零网络） |
| 机制 | ~1.5s | 开局序列、经济保底、坦克预算、防空保险、防御线、残血撤退 | strategy/planner/（确定性） |
| 语义 | ~1.5s | 态势五态裁决、建造/步兵/载具选择、威胁评估 | jev（TypeSafe Jev） |

- 能用代码算的绝不给模型；Jev 只在代码算不出的地方拍板（`docs/METHODOLOGY.md`）。
- Jev 答案带闸门：态势置信 ≥0.45 才采信、威胁 p>0.6 强制回防、候选剔除超限项
  （精炼厂≤2/兵营≤2/军犬≥4）。

## 三、数据流

1. **进局**：`ra2web-jev-play` → `launcher.launch()` 强制刷新游戏页（弃掉残局）→
   a11y snapshot 驱动点击（单机模式→遭遇战）→ eval 直设滑条（苏俄/速度2/资金10000）→
   开始游戏 → 轮询 `typeof werhd === 'object'` → `eval --stdin` 注入 client.js。
2. **状态**：Python 每 tick 调 `__rj.snapshot()` 一次拿全量 JSON（me/单位/敌情/队列/可造）。
3. **微操**：client.js 内部 setTimeout 链直接读写 werhd，不经 Python。
4. **指令**：Python 决策 → `__rj.o.attackMove/produce/deploy/...` → 页内统一走
   ≤5 分批、同目标 12s 节流、per-unit 18 tick 冷却、deploy 45s 节流（api.md §六实测约束）。
5. **审计与学习闭环**：`artifacts/logs/bot.log`（行日志）+ `artifacts/logs/jev-events.jsonl`
   （决策/动作/损失/击杀/观测快照逐事件）→ 每局存档 `artifacts/games/run-<时间戳>/`（训练数据）
   → 终局自动复盘（`review/` 包：确定性分析 + 模型语义复盘）→ `artifacts/games/game-XXXX-review.md`
   每局报告 + `docs/LESSONS.md` 经验账本 + `docs/knowledge/doctrine.json` 限幅自动调参
   （`docs/METHODOLOGY.md` §〇）→ 下一局加载验证；训练侧由 `scripts/build_dataset.py` 并入 `dataset/`。

## 四、关键设计取舍

| 决策 | 理由 |
|---|---|
| 弃 HTTP 桥接，eval 通道 | 用户要求自包含；官方播放器+代理的职责全部自研后，HTTP 一跳只剩成本 |
| 宏观在 Python、微操在页内 | 微操需要 150ms 级反应（eval 往返 0.05-0.3s 扛不住）；Jev 密钥不能进页面（官方文档同立场） |
| 决策核心从 legacy_bot 平移 | 20 局复盘的参数与教训是项目最大资产，架构重构不改行为（单变量原则） |
| snapshot 一发全量 | 单次 eval 拉 JSON，宏观 tick 只花一次往返 |
| a11y snapshot 驱动菜单 | 官方无菜单自动化文档；快照+点击+断言是最抗改版的通用方案，attach 子命令兜底 |

## 五、与旧架构的对照

| | 旧（官方体系） | 新（自包含） |
|---|---|---|
| 页内脚本 | 官方 werhd-jev-player.mjs（HTTP 下发） | 自有 client.js（eval 注入） |
| 决策服务 | bridge.py HTTP 服务（/decide /event） | Python 进程内直调 TypeSafe |
| 进局方式 | 人工点菜单 | launcher 全自动（attach 兜底） |
| API 真相源 | `references/werhd/` 快照 | werhd/api.md + d.ts 副本（references/werhd/ 仍留作官方原文） |
| 微操代码 | 官方 v8.3 黑盒 | 自有、可改、参数自有化 |

## 六、演进方向（未做，留给后续复盘迭代）

- 官方风格的候选组决策（construction/vehicles/tactics… 一次请求 8 组）替代五问制；
- 每局终局把战报喂 Jev 做复盘判定，自动调整 doctrine 阈值（METHODOLOGY §二闭环的自动化）；
- 看板：静态页读 jev-events.jsonl（旧 SSE 看板随桥接废弃）；
- 登录/排位（需要账号方案；driver 已留 `--restore` 会话持久化）。
