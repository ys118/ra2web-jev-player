# 引擎与环境踩坑总集（webrhd / 浏览器 / Windows 自动化）

> 血泪换来的硬知识。每条都标注了发现过程与规避方法。按"症状 → 根因 → 解法"组织。

## 一、游戏内 API（`window.werhd`）事实

### 1.1 API 全貌（官方文档 `references/werhd/player-console-api.md`）

- 查询：`me() / players() / tick() / time() / units(relation) / unit(id) / selected() / crates() /
  map.size() / map.tile(x,y) / map.visible(x,y) / canPlace(name,x,y) / elevation(...) /
  weaponVs(a,b) / inRange(a,b) / production.queues() / production.available(queueType?) / rules(name,type)`
- 指令：`select / move / attack / attackMove / stop / gather / deploy / order / produce / cancel /
  pause / resume / place / sell / repair / superweapon / ally / ping / resign / camera.centerAt`
- `onTick(cb)` 托管回调（单拍 ~8ms 预算，超时/抛错自动关闭）。
- 枚举全部挂在 `werhd` 上（`OrderType/QueueType/QueueStatus/ObjectType/LandType/...`），不要写魔法数字。
- 离局后对象摘除，访问抛 `werhd is not available outside a running battle`。

### 1.2 units 关系与过滤

- `'self'` 自己 / `'allied'` 友军 / `'hostile'` 迷雾内可见非友方 / **`'enemy'` 其中的战斗单位（过滤掉平民等非战斗对象）**。
- `units('hostile')` 会混入 `@@NEUTRAL@@` 平民建筑 → 曾有坦克围殴 2000 血平民小屋半天。
  **首选 `units('enemy')`**；如需更严格可用 `owner.indexOf('@@AI')===0` 过滤（AI 玩家名形如 `@@AI2@@`）。

### 1.3 队列

- type: 0 建筑 / 1 防御 / 2 步兵 / 3 载具 / 4 飞机 / 5 船；status: 0 空闲 / 1 生产中 / 2 暂停 / **3 就绪待放置**。
- 建筑/防御 status=3 时必须 `place(name,x,y)` 落地（用 `canPlace` 螺旋找位），否则永远占着队列。
- `production.available(t)` 返回形态不定（字符串数组或 `{name,type}[]`）→ **采集层必须归一化**（`x.name||x`）。

### 1.4 单位对象关键字段

`id/name/type/owner/hitPoints/maxHitPoints/tile{rx,ry,z,...}/elevation/isIdle/sight/veteranLevel/
canDeploy(仅己方)/isDeployed(仅可反复切换姿态的单位)/primaryWeapon{minRange,maxRange,aa,ag,cooldownTicks}/
secondaryWeapon/ammo(己方飞机)/transport(载员)/garrison(驻扎)/hasWrenchRepair(建筑维修开关)`。

- `zone === 1` = 空中（官方玩家用它判断对空目标）。
- `weaponVs(id,id,"current")` 按当前姿态与对空限制返回能否打到 + 高地射程加成（射程加成，不是伤害倍率）。

### 1.5 指令语义（红警本体知识，务必区分）

- **`Move(0)` = 只走路不还手**；`AttackMove(4)` 才边走边打。防守/集结必须用 AttackMove——本项目曾因此出现"兵在基地旁挨打不还手"（兵被 Move 到基地后站桩）。
- `order(ids, type, targetIdOrX?, y?)`：单个数字 = 目标单位 id；两个数字 = 地图格。
  对象式目标（新版）：`order(ids, {type, target:{objectId} | {x,y,onBridge}})`。
- `deploy` 与 D 键相同；失败返回 `false` 并 console.error（不静默）。

## 二、锁步队列的四个硬约束（自研阶段实测）

1. **高频重发 = 单位瘫痪**：锁步下每 tick 重发同一指令，单位刚要起步就被新命令重置，永远 idle。
   → 同一目标 12 秒内不重发；目标变更才发新令；每单位独立冷却（官方玩家用 18 tick/单位）。
2. **大 id 数组会被静默丢弃**：34 辆坦克一条指令无效果，5 辆正常。
   → **每批 ≤5 个单位**（官方 player 的适配层会自动分批，自研直调时须自己分）。
3. **部署是异步的**：`deploy` 排队执行期间重复下令 → 基地车/建造厂无限横跳（自杀级）。
   → 只对**载具形态**（`type===7 && canDeploy`）部署，且 **45 秒节流**。（"基地重新部署"选项开启时建造厂也有 canDeploy，不要碰。）
4. **新命令会打断行军**：行军用"目标未变则 hold"的节流，每隔数十秒续令即可。

## 三、浏览器/渲染环境的坑（最阴险的一类）

### 3.1 页面隐藏 → rAF 停摆 → 模拟冻结（"SIM STALL"）

- 症状：游戏时间不动 / 指令排队不执行 / 截图超时（10060）但 eval 正常。
- 根因：页面 `visibilityState === "hidden"`（**最小化或不可见窗口**）时 Chrome 停止 rAF，游戏主循环僵死。
- 事实：**无头（headless）模式页面默认 `visible`，长时间托管最可靠**；有头窗口在本机环境会被持续最小化（还原后立即被重新最小化）→ 有头反而不可靠。
- 辅助：即使页面可见，也可加启动参数 `AGENT_BROWSER_ARGS="--disable-background-timer-throttling,--disable-backgrounding-occluded-windows"`（对 setTimeout 节流有效；对 rAF 无效）。

### 3.2 冷启动/首载不稳定

- 新浏览器 Profile 首次开游戏：黑屏、空文档（`body.innerHTML.length===0`）、about:blank 回跳都可能出现；**重载一次即恢复**。
- 开局流程正确顺序：**先清结算屏 →（需要时）再启动任何自动化 → 再点开始游戏**。结算屏开着时启动玩家脚本会被正确识别为"对局已结束"而退出。

### 3.3 页面重载的副作用

- 遭遇战设置全部重置（阵营回"随机"、速度回 6、资金回 10000）→ 开局前必须重设并确认。
- 音频授权弹窗（"确定"按钮）每次重载都出现，必须先处理。

## 四、Windows 自动化进程的坑（agent-browser / subprocess）

1. **`.cmd` shim 的 argv 切割**：`agent-browser.cmd` 经 cmd.exe 转发，多行/复杂引号的 JS 参数会被切碎。
   → **base64 传输**：`eval -b <base64>`（agent-browser 官方推荐）；>8KB 的整份脚本
   （如 client.js 注入）超 cmd.exe 8191 字符 argv 上限 → **`eval --stdin`**（Popen stdin=PIPE）。
2. **继承 stdin 导致永久挂死**：`Popen` 未设 `stdin=DEVNULL` 时，cmd.exe 解析含括号的参数会等 stdin → 永不返回。
   → 一律 `stdin=subprocess.DEVNULL`（eval --stdin 例外：显式 PIPE+communicate）。
3. **subprocess 超时杀不干净**：Windows 下孙进程持有管道会让 `subprocess.run(timeout=)` 永久卡死。
   → 用 `Popen + communicate(timeout)`，超时后 `taskkill /PID <pid> /T /F` 连树强杀
   （daemon 不在 CLI 子树里，杀 CLI 不会误伤已起的浏览器）。
4. **bytes/str 混拼**：Popen+communicate 返回 bytes，拼接时须 `.decode()`（曾让 bot 每 tick 报错空转）。
5. **中文编码**：Git Bash 发出的命令行参数可能按 GBK 编码 → 服务端 UTF-8 解码失败（0xcf）。
   → 服务端解码降级链 utf-8 → gbk → replace；测试用 `--data-binary @file`。
6. **TypeSafe 返回 gzip**：urllib 不自动解压 → 加 `Accept-Encoding: identity` + gzip magic 兜底解压。
7. **本机调试杀进程**：只杀自己拉起的（`CommandLine -like '*agent-browser*'`），绝不盲杀用户 Chrome。

## 四点五、agent-browser eval/导航契约（2026-09-26 自包含重构实测）

1. **eval 返回值一律 JSON 编码**：CLI 打印 `JSON.stringify(表达式值)`——字符串带引号、
   对象是 JSON 文本。Python 侧统一 `json.loads` 一次还原；**JS 里不要再包
   JSON.stringify**（会双重编码，isinstance(list) 判空这类静默 bug 极难查）。
2. **`open <url>` / 赋值 location.href 会卡死**：CLI 等 window load 事件，新 profile 下
   被墙的第三方资源把 load 卡到外网超时（实测 2 分钟+ 不返回）。
   → 导航用 `eval("setTimeout(()=>{location.href=...},50)")` + 自轮询 readyState
   （接受 interactive/complete）；同 URL 默认跳过，force=True 强制重载。
3. **eval 触发导航会落在不同页面**：导航竞态下注入的几个 eval 可能分别命中旧页/新页
   → 注入后必须验证 `typeof window.__rj`，失败重试（inject.py 已做）。
4. **页面 setTimeout 默认被节流**（headless 后台页 ~1s/次）：微操 150ms 循环必须带
   启动参数 `--disable-background-timer-throttling,--disable-backgrounding-occluded-windows`
   （AGENT_BROWSER_ARGS；只在浏览器冷启动生效，改后需 `agent-browser close`）。
5. **游戏 UI 滑条（设置屏）**：`input[type=range]` 真节点但 (a) 游戏在 input 事件后
   **重渲染节点**——每步必须重新查询；(b) 不能用 `HTMLInputElement.prototype` 的 value
   描述符 setter（Illegal invocation，brand 跨环境）——朴素 `s.value=v` 走元素自身原型链
   永远合法，再补方向键逐档校准。
6. **菜单点击在 SPA 初始化期会只 hover 不生效**：点击后必须断言下一屏文本出现，否则重试。
7. **resign() 会弹 canvas 确认框**（DOM/a11y 树不可见）→ 弃局唯一可靠方式是刷新页面。
8. **session 管理**：`--session <名>` 隔离；`--restore` 持久化 cookie/localStorage；
   `--idle-timeout 0` 防 1h 空闲自动关浏览器（长局必需）。

## 五、本游戏 mod 的专属事实（共和国之辉体系）

- 代码名与标准 RA2 不同：精炼厂=`NAREFN`、科技建筑（战车工厂前置）=`NAHAND`（其实叫兵营）、磁暴线圈=`TESLA`、防空履带车=`HTK`、犀牛=`HTNK`、恐怖机器人=`DRON`、矿车=`HARV`、动员兵=`E2`。
- **没有 `werhd.tick` 不存在的说法**——`tick()` 一直在，之前的"消失"是自研代码写成 `tick: w.tick`（漏括号），函数被 `JSON.stringify` 吞掉。**调用任何方法都要带括号**。
- 防空：哨戒炮/磁暴线圈**不能对空**；对空只有防空炮(NAFLAK)/防空履带车(HTK)/防空步兵(FLAKT)。美军 AI 爱用火箭飞行兵掏家。
- 伤害=弹头×护甲倍率：坦克炮对步兵仅 25%（别用坦克清步兵）；光棱拆家 200%/对重甲 50%；幻影反坦克 100%/拆家 20-30%。
- 建筑无上限扩张会拖垮引擎（曾 21 座精炼厂把模拟冻结）→ 精炼厂硬上限 2，建筑与指令频率都要设防。

## 六、本机环境速查

- `agent-browser`（Rust CLI，自带 Chrome for Testing）。技能入口 `agent-browser skills get core`。
- Python 环境（2026-09-26 起）：项目统一 **uv**——repo 根 `uv sync` 后用 `uv run <命令>`（uv 自管 CPython 3.12.10，venv 在 `.venv/`，`.python-version` 已固定）。后备：系统自带/自装的 Python 3.11+ 亦可（`uv run` 之外请勿用裸 `python` 跑本项目）。
- TypeSafe 判定 CLI：`python $TSJ_SCRIPT`（外部工具, 路径自定）（stdin 传 `{state, questions}`，criteria 形状见 `docs/JEV-INTEGRATION.md`）。
