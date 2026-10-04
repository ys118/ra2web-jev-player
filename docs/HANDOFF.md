# HANDOFF —— 新 session 冷启动指南

> 本文件由上一个 session 在收尾时更新（2026-09-30 深夜）。按 `README.md` 看全貌、
> `docs/ARCHITECTURE.md` 看架构；本文件只讲**从哪继续、怎么跑起来、注意什么**。

## 一、当前状态（截至交接时）

| 项 | 状态 |
|---|---|
| 项目 | `D:/projects/ra2web-jev-player`，GitHub 私有库 `ys118/ra2web-jev-player`（master，最新提交见 `git log -1`） |
| 战绩 | **72 局：14 胜**（[70]clef首局defeat(多变量)/[71]精炼厂豁免defeat/[72]P1资金分配校正defeat——帽侧验证全过但矿车骚扰断收入新死法, 存活2556; 66-69 四局单变量连胜链, 详见 LESSONS 尾部归因） |
| **暂停(2026-10-04 用户指示)** | **暂停开新局**: 用户 Jev 服务余额耗尽, 另一 session 正在接**本地部署 clef-flash 替代 Jev**; 恢复对战前先确认新后端接入+联调。→ **已就绪(2026-10-04)**: 本地引擎+影子评测完成, 全档见 **`docs/CLEF-LOCAL.md`**；**切流已实施(同日 §八)**: 端点/threat 0.55/预算分流/teacher 四项落盘, 服务 q8 重启在驻, **待用户号令开第 70 局** |
| **clef 接入指引** | JevClient 已环境变量驱动(`src/ra2web_jev_player/jev/client.py`): `JEV_BASE_URL`(默认 api.typesafe.ai/v1, 端点契约 POST {base_url}/systemone, body {state,questions,model}) / `JEV_MODEL` / `JEV_MAX_CALLS` / 密钥 `TYPESAFE_API_KEY`(绝不入库)。本地 clef 若实现同契约→零代码改; 若是 OpenAI 兼容 API→client.py 加适配层。决策预算上限由 CLI `--max-decisions`(现 1200)传入, 长局触顶候选上调。✅ **已实测(2026-10-04)**: llama.cpp 的 clef 实现=同契约, 逐字段核对一致(noul 答案键=`noul`), `JEV_BASE_URL=http://127.0.0.1:8085/v1`+dummy key 即零代码切; 阈值建议(threat 0.6→0.55 / stance 0.45 保持)与切换手册见 `docs/CLEF-LOCAL.md` §四.4/§五。**2026-10-04 已切流**: client.py 默认端点/模型改本地(`127.0.0.1:8085`/`clef-flash`), Jev 云端两行注释保留可回切 |
| 速度定谳 | 前 50 局速度滑条未生效(已修为真实方向键)。3 档=1.33x(用户定谳默认), 墙钟完整局 20-30 分钟 |
| 数据分层 | 第 1-50 局=6 档 / 51=1 档 / 52=2 档 / **53 起=3 档**。节奏类结论跨层不可比 |
| Jev 投喂 | 63 局起全面英文化 + DYNAMIC SITUATION 动态上下文段; **[第69局] Jev 决策预算 1200 触顶(长局后半纯确定性)——已实施(2026-10-04): 预算按后端分流, 本地 clef 实质不限/云 Jev 保持 1200, 第70局实证全局无断崖** |
| 遗留(下一局主攻) | **第73局候选(待用户拍板)**: 修正版 P2=矿车存活与再生(72局矿车9死/存活仅2-3辆→重坦线断供; 手段: 补车门槛降档/路线避敌影/护航门槛降档) + 重坦前出纪律(72局6辆t=741-791团灭=无敌影确认集群前出); P1 帽侧验证全过(HTK 58/74→2次/拦截位屏4), 反驳条件兑现→收入链实锤; **运维: 对局已改脱离会话独立控制台启动(out/run_g72.bat, session 中断免疫), 进程清理铁律见 LESSONS 第72局条** |

## 一.2、本 session 关键教训（均已入 docs/LESSONS.md，此处防重蹈）

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
tail -f logs/bot.log                       # 行日志
tail -f logs/games/run-*/events.jsonl      # 当前局的逐事件（jsonl）
# 或读最近 run 目录: ls -dt logs/games/run-* | head -1

# 3) 复盘/数据
uv run ra2web-jev-review                   # 手动补复盘最后一段对局
uv run python scripts/build_training_assets.py   # 重建 dataset/（含新局）
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
2. **训练数据持续积累**：每局后跑一次 `scripts/build_training_assets.py` 把新局
   并入 `dataset/`；sft-full 元组是后续 SFT/RL 的核心燃料。
3. **策略演进（下一局主攻 = V3 反制, 待用户拍板）**：
   - 第 65 局敌方 V3 导弹车（射程 12+ 塔射程 8）远程拆战厂 → 坦克峰值 0;
   - 候选方案：视野内出现 V3 / 基地被 V3 攻击 → 产 2×HTK 防空车（可拦截 V3
     火箭+贴脸速拆发射车）；
   - rush 型 roll（敌 t≈300-400 步兵海）是当前主要败因，防守层修复(§一.2.3/4)
     后待复测；改动走单变量原则（`docs/METHODOLOGY.md`）。
4. **调参观察**：本 session 支持度 0.39-0.59 均未过闸，tank_cash1=900/cash2=1200
   维持；`knowledge/doctrine.json` 的 history 字段有完整出处。
5. **数据刷新（游戏更新后必做）**：按 `_research/README.md` 重抓数值；同时对照
   `werhd/werhd-player-api.d.ts` 是否有 API 变化。
6. **站点故障处理**：`gonghui.k0s.cn` 偶发故障（页面加载完成但游戏引擎不启动,
   `window.werhd` undefined + 白屏）。探测脚本 `out/site_probe.py`（exit 0=恢复）;
   处理=等恢复后重开, 不是代码问题。

## 四、红线（不要越过）

- **每局必须停下汇报，等用户反馈**（AGENTS.md §1，用户明确指定）；
- **禁止清理/覆盖/删除 `logs/` 下任何历史数据**（训练资产）；
- **活局期间绝不从外部 agent-browser CLI 连游戏 session**（会抢绑空白页弄断
  eval 通道；活体观察只读 events.jsonl）；
- 只用官方公开的 werhd API；不打排位/联机（只打单机遭遇战）；
- Jev 密钥只在 Python 进程内，绝不写进页面/日志/代码；
- 学习闭环调参走 `knowledge/doctrine.json`；结构性改动先汇报。

## 五、关键文件索引

| 想知道什么 | 看哪 |
|---|---|
| 项目全貌 / 快速跑 | `README.md` |
| 架构定稿（分层/数据流/取舍） | `docs/ARCHITECTURE.md` |
| **逐局战史与全部教训（最重要）** | `docs/LESSONS.md` |
| 训练数据资产结构与分层 | `dataset/README.md` + `dataset/MANIFEST.jsonl` |
| 自有 API 定义（含实测约束） | `src/ra2web_jev_player/werhd/api.md`（类型真相源: 同目录 d.ts） |
| 怎么迭代 / 怎么调 Jev | `docs/METHODOLOGY.md` |
| 所有引擎/环境坑 | `docs/ENGINEERING-NOTES.md` |
| 桥接协议史 / 官方候选组设计 | `docs/JEV-INTEGRATION.md` |
| 20 局自研时代进化史 | `docs/SESSION-REPORT.md` |
| 官方 API 原文 | `refs/player-console-api.md` |
| 攻略/数值真值 | `knowledge/RA2-BIBLE.md`、`knowledge/RA2-UNITS.json` |
| 数值/攻略的复现与刷新 | `_research/README.md` |
| 站点恢复探测 | `out/site_probe.py`（exit 0=恢复） |
| **Clef 本地决策后端全档** | **`docs/CLEF-LOCAL.md`**（引擎/模型/契约实测/828 条影子评测/阈值建议/切换手册/踩坑；影子工具 `out/shadow_eval.py`） |
