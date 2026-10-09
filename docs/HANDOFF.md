# HANDOFF —— 新 session 冷启动指南

> 本文件由上一个 session 在收尾时更新（**2026-10-07, 100 局里程碑收官+101 局
> 迭代包就绪**）。按 `README.md` 看全貌、`docs/ARCHITECTURE.md` 看架构；本文件只讲
> **从哪继续、怎么跑起来、注意什么**。**下一局=第 101 局（三修复实战验证局, 已就绪）**。

## 一、当前状态（截至交接时）

| 项 | 状态 |
|---|---|
| **结构重构(2026-10-09)** | **仓库整理为标准 uv 工程(代码/文档/数据/资料分区; planner 与 review 拆包; `uv run pytest` 26 场景 + 布局守卫全过)——操作路径全部变更, 对照表见 `docs/LAYOUT.md`; 决策行为零改动** |
| 项目 | `D:/projects/ra2web-jev-player`，GitHub 私有库 `ys118/ra2web-jev-player`（master，最新提交见 `git log -1`） |
| 战绩 | **100 局：21 胜**（milestone 达成）。近期弧线: 87 防御纵深包🏆→88-90 经济三连修(坦克资金地板/统一生产账本/收入负债豁免)→91 🏆矿车7辆翻盘→92-93 步坦协同+FOCUS-FIRE+侦察路标网(用户战术反馈)→94 矿车+1容错→95 击杀冻结检测器🏆→96 用户叫停僵持局→97-98 打破僵局包两连胜→99 大roll消耗战partial→100 收官defeat(老死法复现)。详见 LESSONS 尾部 |
| **暂停(2026-10-04 用户指示)** | **暂停开新局**: 用户 Jev 服务余额耗尽, 另一 session 正在接**本地部署 clef-flash 替代 Jev**; 恢复对战前先确认新后端接入+联调。→ **已就绪(2026-10-04)**: 本地引擎+影子评测完成, 全档见 **`docs/CLEF-LOCAL.md`**；**切流已实施(同日 §八)**: 端点/threat 0.55/预算分流/teacher 四项落盘, 服务 q8 重启在驻, **待用户号令开第 70 局** |
| **clef 接入指引** | JevClient 已环境变量驱动(`src/ra2web_jev_player/jev/client.py`): `JEV_BASE_URL`(默认 api.typesafe.ai/v1, 端点契约 POST {base_url}/systemone, body {state,questions,model}) / `JEV_MODEL` / `JEV_MAX_CALLS` / 密钥 `TYPESAFE_API_KEY`(绝不入库)。本地 clef 若实现同契约→零代码改; 若是 OpenAI 兼容 API→client.py 加适配层。决策预算上限由 CLI `--max-decisions`(现 1200)传入, 长局触顶候选上调。✅ **已实测(2026-10-04)**: llama.cpp 的 clef 实现=同契约, 逐字段核对一致(noul 答案键=`noul`), `JEV_BASE_URL=http://127.0.0.1:8085/v1`+dummy key 即零代码切; 阈值建议(threat 0.6→0.55 / stance 0.45 保持)与切换手册见 `docs/CLEF-LOCAL.md` §四.4/§五。**2026-10-04 已切流**: client.py 默认端点/模型改本地(`127.0.0.1:8085`/`clef-flash`), Jev 云端两行注释保留可回切 |
| 速度定谳 | 前 50 局速度滑条未生效(已修为真实方向键)。3 档=1.33x(用户定谳默认), 墙钟完整局 20-30 分钟 |
| 数据分层 | 第 1-50 局=6 档 / 51=1 档 / 52=2 档 / **53 起=3 档**。节奏类结论跨层不可比 |
| Jev 投喂 | 63 局起全面英文化 + DYNAMIC SITUATION 动态上下文段; **[第69局] Jev 决策预算 1200 触顶(长局后半纯确定性)——已实施(2026-10-04): 预算按后端分流, 本地 clef 实质不限/云 Jev 保持 1200, 第70局实证全局无断崖** |
| 遗留(下一局主攻) | **第101局: 三修复实战验证(已实施+测试+push)**——①矿车重建通道(DEBT-GATE豁免分层: n_harv<2时HARV全额/单厂期二厂1900) ②rush_defense协防期坦克镜像探图常态化(_order_raw独立槽) ③myval_zero 300gs优雅退出; test_rebuild101 5场景+全套回归14文件全过; **最深残留裂缝: 敌大roll下收入死循环+rush窗口×侦察缺失复合死法(100局复现)** |

## 一.1、本 session(87-101 局)新增运维定谳（均已入 LESSONS，防重蹈）

- **agent-browser 自带 Chrome 151 损坏事故**: WebGL 全丧失+headless 挂死
  (升级残留), `agent-browser install` 重装 155.0.8059.39 修复(真 GPU 确认);
  旧版 428MB 已清理。RA2WEB_CHROME_PATH 仅应急。
- **站点 0.87.0 更新三件套**: ①音频许可弹窗(goto 后 ~10s)——根治=chrome_args
  加 --autoplay-policy=no-user-gesture-required(env 会覆盖全局 config args);
  launcher 前置轮询点确定兜底 ②资金滑条应用内上限 9100(DOM max 仍 10000)
  ——launcher 接受 ≥9000 ③弹窗期 body 仅 53 字符曾被误判"站点白屏故障"。
- **preflight 启动自检**(out/preflight.py, g88 起): clef→webgl(eval 探测)
  →stale close→site 串行——close 后立即 eval 会挂 150s(daemon 内浏览器
  重启路径), 顺序勿倒; open 命令挂=47 局老问题, 测健康用 eval。
- **对局启动统一走 out/run_gNN.bat**(含 preflight); watcher 后台轮询
  REVIEW 行; 僵尸局两检测器: kill_freeze(attack态 3000gs)/myval_zero(300gs)。

## 一.2、本 session 关键教训（均已入 docs/LESSONS.md，此处防重蹈）

**最近 session（2026-10-04/05, clef 切流+连迭代两弧线）速览**:
- **切流**: 默认后端=本地 clef-flash(8085), Jev 端点注释保留; teacher 字段溯源
  (无字段=Jev 时代), 预算按后端分流(本地不限/云 1200); 详见 CLEF-LOCAL.md §八。
- **四胜机制链(全部实战闭环)**: RUSH-DEFENSE 动态防御(76)→防空主动猎杀(73)→
  SIEGE 总攻围城(78 首验)→幻影识别(82)→经济军备竞速(81/84: 6矿车+三厂);
  开局驻军 GARRISON(84)。
- **铁律新增**: ①矿车 8→6 回滚(85 局矿区枯竭: 扩容有度, 矿区是有限资源);
  ②跨 session agent-browser 互杀——只许会话级 close/锁 PID 精确杀, 禁按名按树
  (79 局条); ③对局必须脱离会话独立控制台启动(现: `scripts\run_game.bat <局号>`; 历史脚本存 `scripts/runs/`)。
- **残留最大方差**: 开局 rush 窗口(t<400, 6 败中 4 局死于此)——第 87 局防御
  纵深包(双兵营+驻军8+哨炮3)待验证。

1. **动建造序列前必查 prereq 链**(RA2-UNITS.json): 第 59 局"开局换位"违反
   NAWEAP 需 NAHAND 前置, Jev 插单 masking 5 局后拆补丁即死锁完败——**单变量
   "验证成功"必须做归因核查**。
2. **军犬演进终态(用户逐条指示)**: 只养 1 只/纯 move 绝不攻击/遇敌 8 格规避→
   到家休整 60gs→从最安全未访路标再出发(安全度=距可见敌距离, 循环推进绝不罚站)/
   探到敌基地立即撤回/阵亡补 1。**Jev 产犬一律 HOLD**(第 24 局预算豁免曾让
   Jev 绕过规则连产 4+ 犬全站基地)。
3. **防守层(63/64 局用户反馈驱动)**: 敌基地定位+总攻态势→步兵留 4 守家、余者
   全部编入突击组(总战争模式); 守家坦克 2→1; 伏击位半径 14→8 贴塔线(前出售头
   实证 14 动员兵被逐个点名); power_reserve 30→60+DEFLINE 上塔需余量≥40
   (缺电=塔全瞎)。
4. **经济**: 矿车门槛 1400/1500/2800→800/1200/1500(收入死螺旋解药, 65 局
   见底率 0% 历史首次全场不见底)。
5. **运维铁律**: 活局期间绝不从外部 agent-browser CLI 连游戏 session(会抢绑
   空白页弄断 eval 通道, 第 51 局事故); 活体观察只读游戏进程自己写的
   events.jsonl(obs 快照含 power_low/credits/兵力)。Git Bash 下 taskkill 用
   `//PID //T //F`。僵尸局(t>2×正常局长且无翻盘路径)可主动终止(partial 存档)。

## 二、恢复运行（照抄即可）

```bash
# 1) 一条命令全自动（需 TYPESAFE_API_KEY 环境变量，已配用户级）
cd D:/projects/ra2web-jev-player
uv sync                        # 首次/依赖变更后
uv run ra2web-jev-play         # 进局→注入→托管整局→终局自动复盘→账本+调参

# 2) 监控（另开终端）
tail -f artifacts/logs/bot.log                       # 行日志
tail -f artifacts/games/run-*/events.jsonl      # 当前局的逐事件（jsonl）
# 或读最近 run 目录: ls -dt artifacts/games/run-* | head -1

# 3) 复盘/数据
uv run ra2web-jev-review                   # 手动补复盘最后一段对局
uv run python scripts/build_dataset.py   # 重建 dataset/（含新局）
```

4. **浏览器 daemon 挂死恢复**（eval 超时/挂死时）：
   ```bash
   # 定位并杀掉 agent-browser daemon 树（注意别杀用户自己的 Chrome：
   # 用户 Chrome 的父进程是 explorer，agent-browser 的父进程是 agent-browser-win32-x64.exe）
   powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -like 'agent-browser*' } | Select-Object ProcessId,Name"
   # 然后静态诊断（会跑 launch 自测）: agent-browser doctor
   ```
   杀干净后直接重跑 `ra2web-jev-play` 即可（冷启动首局会重建会话）。

**踩坑快速提醒**（详见 `docs/ENGINEERING-NOTES.md`）：
- 页面必须 `visibilityState === "visible"`；**无头模式是长局首选**（已强制，勿回退）；
- 结算屏开着时注入会被识别为"对局已结束"——launcher 的强制刷新天然规避；
- 全局 agent-browser 配置 `~/.agent-browser/config.json` 里若有 `"headed": true`，
  代码里的 `AGENT_BROWSER_HEADED=false` 已覆盖，不需要改全局配置。

## 三、后续任务（建议优先级）

1. **继续实战训练闭环**（用户指定主任务）：`uv run ra2web-jev-play` 逐局跑，
   **每局结束必须停下向用户汇报**（AGENTS.md 规则），等反馈再继续。
   参考基线：近 5 局 3 胜；对手是"AI-简单"随机阵营 roll。
2. **训练数据持续积累**：每局后跑一次 `scripts/build_dataset.py` 把新局
   并入 `dataset/`；sft-full 元组是后续 SFT/RL 的核心燃料。
3. **策略演进（下一局主攻 = V3 反制, 待用户拍板）**：
   - 第 65 局敌方 V3 导弹车（射程 12+ 塔射程 8）远程拆战厂 → 坦克峰值 0;
   - 候选方案：视野内出现 V3 / 基地被 V3 攻击 → 产 2×HTK 防空车（可拦截 V3
     火箭+贴脸速拆发射车）；
   - rush 型 roll（敌 t≈300-400 步兵海）是当前主要败因，防守层修复(§一.2.3/4)
     后待复测；改动走单变量原则（`docs/METHODOLOGY.md`）。
4. **调参观察**：本 session 支持度 0.39-0.59 均未过闸，tank_cash1=900/cash2=1200
   维持；`knowledge/doctrine.json` 的 history 字段有完整出处。
5. **数据刷新（游戏更新后必做）**：按 `references/research/README.md` 重抓数值；同时对照
   `werhd/werhd-player-api.d.ts` 是否有 API 变化。
6. **站点故障处理**：`gonghui.k0s.cn` 偶发故障（页面加载完成但游戏引擎不启动,
   `window.werhd` undefined + 白屏）。探测脚本 `scripts/site_probe.py`（exit 0=恢复）;
   处理=等恢复后重开, 不是代码问题。

## 四、红线（不要越过）

- **每局必须停下汇报，等用户反馈**（AGENTS.md §1，用户明确指定）；
- **禁止清理/覆盖/删除 `artifacts/`、`dataset/` 下任何历史数据**（训练资产）；
- **活局期间绝不从外部 agent-browser CLI 连游戏 session**（会抢绑空白页弄断
  eval 通道；活体观察只读 events.jsonl）；
- 只用官方公开的 werhd API；不打排位/联机（只打单机遭遇战）；
- Jev 密钥只在 Python 进程内，绝不写进页面/日志/代码；
- 学习闭环调参走 `docs/knowledge/doctrine.json`；结构性改动先汇报。

## 五、关键文件索引

| 想知道什么 | 看哪 |
|---|---|
| 项目全貌 / 快速跑 | `README.md` |
| 架构定稿（分层/数据流/取舍） | `docs/ARCHITECTURE.md` |
| 测试与已知陈旧断言 | `tests/README.md`（`uv run pytest`） |
| **逐局战史与全部教训（最重要）** | `docs/LESSONS.md` |
| 训练数据资产结构与分层 | `dataset/README.md` + `dataset/MANIFEST.jsonl` |
| **仓库布局与迁移对照** | **`docs/LAYOUT.md`** |
| 自有 API 定义（含实测约束） | `src/ra2web_jev_player/werhd/api.md`（类型真相源: 同目录 d.ts） |
| 怎么迭代 / 怎么调 Jev | `docs/METHODOLOGY.md` |
| 所有引擎/环境坑 | `docs/ENGINEERING-NOTES.md` |
| 桥接协议史 / 官方候选组设计 | `docs/JEV-INTEGRATION.md` |
| 20 局自研时代进化史 | `docs/SESSION-REPORT.md` |
| 官方 API 原文 | `references/werhd/player-console-api.md` |
| 攻略/数值真值 | `docs/knowledge/RA2-BIBLE.md`、`docs/knowledge/RA2-UNITS.json` |
| 数值/攻略的复现与刷新 | `references/research/README.md` |
| 站点恢复探测 | `scripts/site_probe.py`（exit 0=恢复） |
| **Clef 本地决策后端全档** | **`docs/CLEF-LOCAL.md`**（引擎/模型/契约实测/828 条影子评测/阈值建议/切换手册/踩坑；影子工具 `scripts/shadow_eval.py`） |
