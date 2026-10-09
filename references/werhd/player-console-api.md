# 玩家战场控制台 `window.werhd`

对局开始后，浏览器开发者工具控制台可以使用 `window.werhd` 读取**本地玩家看得见的**战场，并下发与鼠标、键盘相同的锁步指令。全局名是王二火大的缩写，不是红警，也没有 `window.ra`。

离局后对象会摘掉。再访问会抛 `werhd is not available outside a running battle`。观战或已投降只能读，不能下战斗指令。

```js
werhd.help()
```

会在控制台打印一份速查，并返回同一段文本。

## 能做什么

- 读己方、盟友、迷雾内可见的敌方单位与箱子
- 读地图可见格子、高程、能否落建筑
- 用 `weaponVs` / `inRange` 判断射程，以及「以高打低」的射程加成
- 读己方生产队列
- 选中、移动、攻击、展开、采矿、生产、放置、卖修、超武、结盟、投降
- 用 `onTick` 每拍跑一段自己的逻辑

指令进入人类 `ActionQueue`，联机与回放和点鼠标同一条路径。不要用它们去改模拟或揭迷雾。

## 玩家脚本怎么和 API 交互

对局开始后，游戏页上已经有 `window.werhd`。你自己写的 JS 跑在**同一页**里，直接函数调用。没有插件通道，也没有 CEF 桥。Jev 或其它模型不能自己碰 `werhd`：它们只是你的脚本可以去问的决策接口。

```
你的脚本  --werhd.units()/deploy()-->  window.werhd
你的脚本  --可选 evaluate-->  Jev
```

把脚本送进游戏页的方式：

1. **控制台粘贴**（最贴近会编程的玩家）：进局后先执行 `werhd.help()`，再贴下面的循环或 `import`。
2. **本机模块**：把 [examples/werhd-user-script.mjs](examples/werhd-user-script.mjs) 拷到自己的静态目录，控制台 `import('http://127.0.0.1:5500/werhd-user-script.mjs')`。开发服也可以：

```js
const { attachWerhdPlayer } = await import('/docs/examples/werhd-user-script.mjs')
attachWerhdPlayer(werhd)
```

3. **油猴**：只是自动完成第 1 步，仍然是页内 `werhd.xxx()`。

`onTick` 单次大约 8ms。问 Jev（网络）必须在回调外异步做，下一拍再 `werhd.move/attack`。在 `onTick` 里 `await` 模型会把回调掐掉。

完整示例（写死规则，也可换成你的 `askJev`）见 [examples/werhd-user-script.mjs](examples/werhd-user-script.mjs)。控制台最小闭环：

```js
werhd.onTick(() => {
  const mcv = werhd.units('self').find((unit) => ['AMCV', 'SMCV', 'CMCV'].includes(unit.name))
  if (mcv) werhd.deploy([mcv.id])
  const idle = werhd.units('self').filter((unit) => unit.isIdle && unit.name === 'E1')
  const enemy = werhd.units('enemy')[0]
  if (!mcv && idle.length === 0) werhd.produce('E1')
  if (idle.length && enemy) werhd.attack(idle.map((unit) => unit.id), enemy.id)
})
```

## 开局示例：选中基地车并展开

```js
const mcv = werhd.units('self').find((unit) => ['AMCV', 'SMCV', 'CMCV'].includes(unit.name))
if (!mcv) throw new Error('找不到基地车')
werhd.deploy([mcv.id])
```

不必先 `select`。`deploy` 与 D 键相同，走 `DeploySelected`。失败会 `console.error` 并返回 `false`，不会静默丢掉。

## 查询

| 调用 | 返回 | 说明 |
| --- | --- | --- |
| `werhd.me()` | 自己 | 名字、阵营、钱、电、雷达、是否观战/战败 |
| `werhd.players()` | 玩家列表 | 敌方**没有**金钱、电力、雷达 |
| `werhd.tick()` | 整数 | 当前模拟拍 |
| `werhd.time()` | 秒 | 当前对局时间 |
| `werhd.units(relation?)` | 单位数组 | 默认 `'self'`。见下方关系 |
| `werhd.unit(id)` | 单位或 `undefined` | 无效、已消失、已摧毁或不可见的 id 均返回 `undefined` |
| `werhd.selected()` | 单位数组 | 当前选中 |
| `werhd.crates()` | 箱子数组 | 仅本地可见 |
| `werhd.map.size()` | `{ width, height }` | 地图尺寸副本，修改返回值不会改变地图 |
| `werhd.map.tile(x, y)` | 格子或 `undefined` | 迷雾中为 `undefined` |
| `werhd.map.visible(x, y)` | 布尔 | 该格是否可见 |
| `werhd.canPlace(name, x, y)` | 布尔 | 可见格子上能否放该建筑 |
| `werhd.elevation(id)` | 数字或 `undefined` | 单位有效高度 `tile.z + tileElevation` |
| `werhd.elevation({ x, y })` | 数字或 `undefined` | 可见格子的 `z` |
| `werhd.weaponVs(a, b)` | 射程对照或 `undefined` | 见下方 |
| `werhd.inRange(a, b)` | 布尔 | `weaponVs` 的 `inRange` |
| `werhd.production.queues()` | 六条队列 | 建筑/兵营/战车等 |
| `werhd.production.available(queueType?)` | `{ name, type }[]` | 当前能造的 |

`units` 的 `relation`：

- `'self'`：自己的单位
- `'allied'`：自己和盟友
- `'hostile'`：迷雾内可见的非友方
- `'enemy'`：其中的战斗单位（过滤掉非战斗对象）

看不见、未探开、隐身未侦测的单位，`unit(id)` 返回 `undefined`，不能靠扫 id 透视。

观察和执行之间，目标可能被摧毁或变卖。再次查询该 id 不会抛异常；`weaponVs` 返回 `undefined`，`inRange` 返回 `false`。`order` 过滤已消失的己方单位，物体目标失效或没有剩余可操作单位时返回 `false`；`select` 跳过无效 id。`deploy` 全部失效时返回 `false` 并输出诊断。上述行为不改变正常锁步指令在模拟执行时的合法性检查。

### 单位对象

```js
{
  id, name, type, owner,
  hitPoints, maxHitPoints,
  tile: { rx, ry, z, rampType, landType, onBridge },
  tileElevation,          // 相对格子的高度
  elevation,              // tile.z + tileElevation，用于以高打低
  worldPosition: { x, y, z },
  onBridge, zone, direction, velocity,
  isIdle, sight, veteranLevel,
  canDeploy: true,       // 仅己方；能力判断，当前地形仍可能阻止展开
  isDeployed: false,     // 仅己方可反复展开的单位；基地车等形态转换单位为 undefined
  primaryWeapon: { minRange, maxRange, subjectToElevation, cooldownTicks },
  secondaryWeapon
}
```

`type` 对应 `werhd.ObjectType`。坐标 `rx/ry` 是地图格，`worldPosition` 是世界坐标。

### 自己 / 玩家对象

`me()`：

```js
{ name, country, credits, power, radarDisabled, defeated, isObserver, combatant }
```

`power` 为 `{ total, drain, isLowPower }`。`players()` 对非盟友不带 `credits`、`power`、`radarDisabled`。

### 箱子 / 格子

```js
werhd.crates()
// { id, name, water, tile }

werhd.map.tile(x, y)
// { rx, ry, z, rampType, landType, onBridge }
```

### 射程与以高打低

`weaponVs` 走引擎 `RangeHelper`，用攻击者主武器。以高打低是**射程加成**，不是伤害倍率。

```js
{
  distance,          // 格
  minRange, maxRange,
  inRange,
  hasHighGround,     // 弹道吃高程，且攻击者更高
  elevationBonus     // 因高程多出来的射程
}
```

任一方不可见、或攻击者没有主武器时返回 `undefined`。

```js
const me = werhd.units('self').find((unit) => unit.primaryWeapon)
const them = werhd.units('enemy')[0]
if (me && them) console.log(werhd.weaponVs(me.id, them.id))
```

## 指令

这些方法在观战/战败时不会入队，并 `console.warn`。`deploy` / `order` 另外返回 `boolean`。

| 调用 | 作用 |
| --- | --- |
| `werhd.select(ids)` | 选中己方单位 |
| `werhd.move(ids, x, y)` | 移动到格子 |
| `werhd.attack(ids, targetId)` | 攻击目标 |
| `werhd.attackMove(ids, x, y)` | 攻击移动 |
| `werhd.stop(ids)` | 停止 |
| `werhd.gather(ids, x, y)` | 采矿到明确地格；缺失或非法坐标不下令。矿区搜索与选择由用户脚本完成 |
| `werhd.deploy(ids)` | 展开 / 部署，与 D 键相同 |
| `werhd.order(ids, type, targetIdOrX?, y?)` | 原始指令 |
| `werhd.produce(name, qty?)` | 入队生产，默认 1 |
| `werhd.cancel(name, qty?)` | 取消生产 |
| `werhd.pause(queueType)` | 暂停队列 |
| `werhd.resume(queueType)` | 继续队列 |
| `werhd.place(name, x, y)` | 放置已就绪建筑 |
| `werhd.sell(id)` | 卖 |
| `werhd.repair(id)` | 切换维修扳手 |
| `werhd.superweapon(type, x, y, x2?, y2?)` | 超武；超时空可带第二点 |
| `werhd.ally(name, on)` | 结盟 / 解盟 |
| `werhd.ping(x, y)` | 地图标记 |
| `werhd.resign()` | 投降 |

`order` 的目标：只传一个数字当目标单位 id；传 `x, y` 当地图格。无目标的 `OrderType.Deploy` 会改成 `DeploySelected`。

`produce` / `cancel` 找不到该名字时 `console.warn`，例如 `werhd.produce: E1 is not available`。

`weaponVs(a, b)` / `inRange(a, b)` 保持主武器语义。显式传第三个参数 `"current"` 时，查询引擎按当前姿态和目标实际选择的武器，包含部署和对空限制；无兼容武器时分别返回 `undefined` / `false`。部署是切换操作，脚本应在调用前重新读取 `isDeployed`，避免迟到响应反向切换。

### `deploy` 失败原因

会 `console.error` 并返回 `false`：

- 没有单位 id
- 找不到单位
- 不是己方单位
- 该单位不能部署
- 没有格子
- 当前位置不能展开（基地车落不下建筑）

能部署的包括：基地车（`deploysInto`）、GI 一类展开步兵、运输卸载、切换主厂、清空驻军、TickTank 收起。

## 托管逻辑

每成功走完一拍模拟后回调一次。

```js
werhd.onTick(({ tick, time }) => {
  const idle = werhd.units('self').filter((unit) => unit.isIdle && unit.name === 'E1')
  const enemy = werhd.units('enemy')[0]
  if (idle.length && enemy) werhd.attack(idle.map((unit) => unit.id), enemy.id)
})
werhd.offTick()
```

回调抛错或单次超过约 8ms 会被关掉，并 `console.warn`，避免卡死主线程。新的 `onTick` 会替换旧回调，不是叠加。问 Jev 等网络请求不要写在这个回调里同步等待，见上文「玩家脚本怎么和 API 交互」。

## 枚举

挂在 `werhd` 上，不要自己填魔法数字（除非你明确知道值）。

### `werhd.OrderType`

| 名字 | 值 | 常见用途 |
| --- | --- | --- |
| `Move` | 0 | `move` |
| `ForceMove` | 1 | 强制移动 |
| `Attack` | 2 | `attack` |
| `ForceAttack` | 3 | 强制攻击 |
| `AttackMove` | 4 | `attackMove` |
| `Guard` | 5 | 警戒 |
| `GuardArea` | 6 | 区域警戒 |
| `Capture` | 7 | 工程师占领 |
| `Occupy` | 8 | 进入建筑 |
| `Deploy` | 9 | 需要点单位自己；无目标时 `order` 会改成下一项 |
| `DeploySelected` | 10 | D 键 / `deploy` |
| `Stop` | 11 | `stop` |
| `Cheer` | 12 | 欢呼 |
| `Dock` | 13 | 进船坞等 |
| `Gather` | 14 | `gather` |
| `Repair` | 15 | 修理目标 |
| `Scatter` | 16 | 散开 |
| `EnterTransport` | 17 | 上运输工具 |
| `PlaceBomb` | 18 | 伊文炸弹 |

```js
werhd.order([id], werhd.OrderType.AttackMove, 20, 21)
```

### `werhd.QueueType`

| 名字 | 值 |
| --- | --- |
| `Structures` | 0 |
| `Armory` | 1 |
| `Infantry` | 2 |
| `Vehicles` | 3 |
| `Aircrafts` | 4 |
| `Ships` | 5 |

```js
werhd.pause(werhd.QueueType.Infantry)
werhd.production.available(werhd.QueueType.Vehicles)
```

### `werhd.ObjectType`

| 名字 | 值 |
| --- | --- |
| `None` | 0 |
| `Aircraft` | 1 |
| `Building` | 2 |
| `Infantry` | 3 |
| `Overlay` | 4 |
| `Smudge` | 5 |
| `Terrain` | 6 |
| `Vehicle` | 7 |
| `Animation` | 8 |
| `Projectile` | 9 |
| `VoxelAnim` | 10 |
| `Debris` | 11 |

### `werhd.SuperWeaponType`

| 名字 | 值 |
| --- | --- |
| `MultiMissile` | 0 |
| `IronCurtain` | 1 |
| `LightningStorm` | 2 |
| `ChronoSphere` | 3 |
| `ChronoWarp` | 4 |
| `ParaDrop` | 5 |
| `AmerParaDrop` | 6 |

```js
werhd.superweapon(werhd.SuperWeaponType.ChronoSphere, 30, 40)
```

## 更多例子

巡逻己方空闲矿车：

```js
const { width, height } = werhd.map.size()
let ore
for (let x = 0; x < width && !ore; x++) {
  for (let y = 0; y < height; y++) {
    const tile = werhd.map.tile(x, y)
    if (tile?.landType === werhd.LandType.Tiberium) { ore = tile; break }
  }
}
if (ore) werhd.units('self')
  .filter(u => u.isIdle && werhd.rules(u.name, u.type)?.harvester)
  .forEach(u => werhd.gather([u.id], ore.rx, ore.ry))
```

造兵并放置基地：

```js
werhd.produce('E1', 5)
if (werhd.canPlace('GACNST', 20, 22)) werhd.place('GACNST', 20, 22)
```

## 红线

- 没有全图透视，不能扫隐身 id，不能读敌人钱电
- 不暴露 `Game` / 完整 `GameApi`，也不挂 `window.ra`
- 不消耗对局 PRNG
- 调试作弊仍走单机 `r.cheats`
- 这是给会写脚本的玩家用的本机控制台，不是给外挂改模拟的接口


## 精确类型与组合行动

每次 werhd 构建自动生成根目录 `/werhd-player-api.d.ts`，开发服同一路径也可读取。下载该文件即可通过 `import type { PlayerConsolePublicApi } from './werhd-player-api'` 引用；无需安装或重新构建机器人 SDK。声明包含 `Window.werhd`（离局时为 `undefined`）。公开枚举为 `ObjectType`、`OrderType`、`LandType`、`ZoneType`、`VeteranLevel`、`QueueType`、`QueueStatus`、`FactoryType`、`BuildCat`、`ArmorType` 和 `SuperWeaponType`。

`rules(name, type)` 返回当前对局实际解析的单位规则副本，包括地图/MOD 覆盖、价格、工厂类型、容量、驻扎/部署能力、主副武器参数等。没有此类型的规则则返回 `undefined`。只暴露单位规则字段，不导出地图物体列表、出生位置、触发器或整份地图 INI；规则分类、经济计算、候选排序由用户脚本完成。

单位新增状态：`ammo` 为己方飞机剩余弹药；`hasWrenchRepair` 为己方建筑维修开关；`transport` 为己方载具容量、占用槽数和载员 ID；可见建筑的 `garrison` 提供人数、容量和可驻扎状态，具体驻兵 ID 仅对己方提供。所有数组都是副本。`canDeploy` 表示支持 D 键行为，不承诺当前地形合法；`isDeployed` 只适用于可反复切换姿态的己方单位。

统一 `order` 接受按命令种类区分的目标类型，旧的位置参数形式仍可用：

```ts
api.order(infantryIds, { type: api.OrderType.Occupy, target: { objectId: civilianBuildingId } })
api.order(infantryIds, { type: api.OrderType.EnterTransport, target: { objectId: transportId } })
api.order([transportId], { type: api.OrderType.DeploySelected }) // 卸载
api.order([occupiedBuildingId], { type: api.OrderType.DeploySelected }) // 撤出驻军
api.order(engineerIds, { type: api.OrderType.Repair, target: { objectId: visibleBridgeHutId } })
api.order(attackers, { type: api.OrderType.ForceAttack, target: { x, y, onBridge: true } })
api.order(units, { type: api.OrderType.Move, target: { x, y, onBridge: true } })
```

`map.tile(x,y)?.bridge` 返回已揭示格上的桥段 ID、高度、低桥标记和生命值。`onBridge: true` 明确指定可见桥面，省略时目标为地面。侦察移动可以指向迷雾，物体目标必须可见。目标检查、己方单位过滤和分批下令只作用于玩家适配层，未修改机器人共用的 `ActionsApi` 或订单执行器。

`order` 的 `true` 仅表示已经加入普通锁步队列，后续仍由正常游戏规则判定和执行。用户脚本需要通过后续状态核验入驻、载员、弹药、部署、桥段等变化，不能把命令提交当成行动完成。
## 本地摄像机

```js
werhd.camera.centerAt(60, 45); // 整数地图坐标；仅移动本地视野
const state = werhd.camera.state(); // { pan: { x, y }, limits?: { x, y, width, height } }
```

`centerAt` 使用与地图定位相同的等距投影，接受地图范围内的整数坐标，遵守正常摄像机边界；靠近边缘时目标不一定能落在屏幕正中。非法坐标或没有渲染器时返回 `false`，成功交给本地摄像机时返回 `true`。迷雾中位置按基准高度定位，不借镜头偏移泄露隐藏地形高度。

`state` 返回摄像机投影偏移和边界的数据副本，单位是投影屏幕像素，不是地图格坐标；无渲染器时返回 `undefined`。两项方法均不修改单位选择、锁步队列、迷雾或战场状态，观察者也可调用。自动跟随、切换战区、镜头停留时间由用户侧实现。
