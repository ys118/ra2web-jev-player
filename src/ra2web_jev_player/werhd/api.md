# werhd 玩家控制台 API —— 本项目自有定义

> 真相源三件套：
> 1. [`werhd-player-api.d.ts`](./werhd-player-api.d.ts) —— 官方构建自动生成的完整类型定义（本目录副本，
>    取自官方仓库 `ra2web.github.io` 根目录；`refs/` 快照里没有这份）；
> 2. [`../../refs/player-console-api.md`](../../refs/player-console-api.md) —— 官方文档原文快照
>    （游戏 v0.87.0，抓取于 2026-09-20）；
> 3. 本文 —— 官方语义提炼 + **本项目 20 局实测补充**（标 `[实测]`）。与官方冲突时以官方为准并回改本文。

## 一、访问模型与红线

- 对局进行中 `window.werhd` 才存在；离局即摘除，访问抛
  `werhd is not available outside a running battle`。
- 指令进与人类玩家（鼠标）**同一条 ActionQueue 锁步队列，异步生效**；`order()` 返回 true
  只表示"已入队"，不保证执行结果，必须靠后续观察核验。
- 红线：只读"本地玩家看得见的"视野；不透雾、不读隐藏敌方状态、不改模拟、不碰
  `Game`/`GameApi`；隐身未侦测、迷雾未探开的物体一律 `undefined`。
- 页面必须 `document.visibilityState === "visible"`，否则 rAF 停摆 → 模拟冻结
  （截图 10060 超时但 eval 仍响应是冻结前兆）`[实测]`。

## 二、查询 API（签名以 d.ts 的 `PlayerConsolePublicApi` 为准）

| 方法 | 返回 | 要点 |
|---|---|---|
| `me()` | `{name,country,credits,power:{total,drain,isLowPower},radarDisabled,defeated,...}` | 己方完整状态 |
| `players()` | 玩家数组 `{allied,combatant,isAi,defeated,isObserver,name,country?}` | **非盟友没有 credits/power** |
| `units(relation?)` | 单位数组 | `'self'`/`'allied'`/`'hostile'`(含非战斗物)/`'enemy'`(hostile 的战斗单位子集，**首选**) |
| `unit(id)` | 单位或 `undefined` | 无效/已毁/不可见都是 undefined（判空即存在性） |
| `map.size()` / `map.tile(x,y)` / `map.visible(x,y)` | 地图/格 | `tile.landType===LandType.Tiberium(9)` 是找矿判据；迷雾中 tile 为 undefined |
| `canPlace(name,x,y)` | bool | 落位搜索用（页内螺旋找位） |
| `weaponVs(a,b,mode?)` / `inRange(a,b,mode?)` | 射程判定 | `mode:'current'` 按当前姿态与对空限制；高地是**射程加成**不是伤害倍率 |
| `production.queues()` | 六条队列 | `status` 见下；`items[]` 含 progress/quantity/creditsEach |
| `production.available(qt?)` | 可造列表 | 返回形态不定（字符串数组或 `{name,type}[]`）→ **归一化 `x.name??x`** `[实测]` |
| `rules(name,type)` | 对局实际规则副本 | 造价/工厂/前置/armor/武器/deploysInto 等动态真值，胜过静态表 |
| `tick()` / `time()` | 拍号 / 游戏秒 | 停摆判定用 time 不动 `[实测]`；**调用必须带括号**（函数引用会被 JSON.stringify 吞掉） |
| `crates()` / `selected()` / `elevation(t)` / `camera.state()` | 杂项 | |

单位对象关键字段：`id/name/type/owner/tile{rx,ry,z}/elevation/zone(1=空中)/isIdle/sight/
veteranLevel/hitPoints/maxHitPoints/primaryWeapon|secondaryWeapon{minRange,maxRange,aa,ag,cooldownTicks}`；
己方专属：`canDeploy`(能力，非地形保证)/`isDeployed`(仅可反复切换姿态者)/`ammo`(飞机)/
`hasWrenchRepair`(建筑维修开关)/`transport`/`garrison`(驻扎)。

## 三、指令 API

| 方法 | 语义 | 要点 |
|---|---|---|
| `move(ids,x,y)` | 走路**不还手** `[实测]` | 防守/集结/进攻一律不用它 |
| `attackMove(ids,x,y)` | 边走边打 | 防守集结、进攻行军的标准指令 |
| `attack(ids,targetId)` | 攻击目标 | 目标必须可见 |
| `stop/gather/deploy(ids)` | 停/集矿(须给地格)/展开(D键) | `deploy` 失败返回 false 并 console.error |
| `order(ids,command)` | 原始指令（结构化目标或位置参数兼容） | `OrderType.AttackMove=4` 等；真值见 d.ts |
| `produce(name,qty?)` / `cancel(name,qty?)` / `pause/resume(qt)` | 生产 | |
| `place(name,x,y)` | 落地就绪建筑 | 队列 `status===Ready(3)` 时必须 place，否则占死队列 |
| `sell(id)` / `repair(id)` | 变卖 / 维修开关 | repair 切换 `hasWrenchRepair` |
| `superweapon(type,x,y,x2?,y2?)` / `ally(name,on)` / `ping` / `resign()` / `select(ids)` | 杂项 | |
| `camera.centerAt(x,y)` | 镜头导播 | 不算游戏指令，观察者可用 |

## 四、枚举（完整数值见 d.ts）

- `OrderType`：Move=0、ForceMove=1、Attack=2、ForceAttack=3、**AttackMove=4**、Guard=5、
  GuardArea=6、Capture=7、Occupy=8、Deploy=9、DeploySelected=10、Stop=11、Gather=14、Repair=15…
- `QueueType`：Structures=0 / Armory=1 / Infantry=2 / Vehicles=3 / Aircrafts=4 / Ships=5；
- `QueueStatus`：Idle=0 / Active=1 / OnHold=2 / **Ready=3（就绪待放置）**；
- `ObjectType`：Aircraft=1 / Building=2 / Infantry=3 / **Vehicle=7（载具形态，deploy 判据）**；
- `LandType.Tiberium=9`；`ZoneType.Air=1`；`ArmorType`：None…Special_2 共 11 类
  （与 `knowledge/RA2-UNITS.json` 的 `meta.armor_classes` 顺序一致）。

## 五、onTick 契约

- 每拍模拟成功走完后回调 `({tick,time})=>{}`；**约 8ms 预算，抛错或超时即被关闭**（console.warn）；
- 新 `onTick` 替换旧回调（非叠加），`offTick()` 取消；除 onTick 外**没有任何事件订阅 API**；
- **网络调用绝不能在 onTick 里 await**（官方文档明令）。
- 本项目微操循环因此用 `setTimeout` 链（150ms）而非 onTick。

## 六、本项目实测约束（`client.mjs` 与 Python 侧共同遵守）

1. **≤5 单位/批**：34 辆坦克一条 order 静默无效，5 辆正常 `[实测]`。指令封装内置分批。
   （官方文档没有批量上限——这条与下面所有节流都是本项目实证的**用户侧策略**。）
2. **同目标 12s 节流**：锁步下高频重发同一指令 = 单位刚起步就被重置、永远 idle `[实测]`。
3. **deploy 只认载具形态**（`type===7 && canDeploy`）+ **45s 节流**：deploy 异步，重复下令
   = 基地车↔建造厂无限横跳 `[实测]`。"基地重新部署"选项开启时建造厂也有 canDeploy，不要碰。
4. **敌情过滤**：`units('hostile')` 混入 `@@NEUTRAL@@` 平民 → 用 `units('enemy')`，
   更严时按 `owner.indexOf('@@AI')===0` 过滤（AI 玩家名形如 `@@AI2@@`）。
5. **新命令打断行军**：行军用"目标未变则 hold"，每隔数十秒续令即可。
6. **建筑无上限扩张会拖垮引擎**（21 精炼厂冻结模拟）→ 精炼厂硬上限等在策略层设防 `[实测]`。
7. 本 mod（共和国之辉/gonghui）代码名与标准 RA2 不同（精炼厂=NAREFN、战车工厂前置=NAHAND、
   犀牛=HTNK、矿车=HARV、动员兵=E2），数值以 `knowledge/RA2-UNITS.json` 为准。

## 七、页内客户端契约（`client.mjs`，注入后挂 `window.__rj`）

| 入口 | 职责 |
|---|---|
| `__rj.snapshot()` | 单次调用返回全量 JSON 快照（me/单位/队列/可造/敌情/时间），Python 宏观循环唯一状态来源 |
| `__rj.orders.move/attackMove/attack/stop/gather/produce/place/deploy/repair/sell(...)` | 指令封装：内置 ≤5 分批、同目标 12s 节流、per-unit 冷却、deploy 载具判别+45s 节流 |
| `__rj.micro.start(opts)` / `__rj.micro.stop()` | 150ms 微操循环（集火/矿车恢复/维修/就绪落位/镜头），setTimeout 链 |
| `__rj.status` / `__rj.stop()` | 运行状态 / 全停 |

数据流：Python 每宏观 tick 调 `__rj.snapshot()` 一次；微操不回传数据，只通过
`__rj.orders` 在页内直接行动（零网络）；审计事件由 Python 侧写入 `logs/jev-events.jsonl`。
