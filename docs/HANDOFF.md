# HANDOFF —— 新 session 冷启动指南

> 本文件由上一个 session 在收尾时更新（2026-09-29）。按 `README.md` 看全貌、
> `docs/ARCHITECTURE.md` 看架构；本文件只讲**从哪继续、怎么跑起来、注意什么**。

## 一、当前状态（截至交接时）

| 项 | 状态 |
|---|---|
| 项目 | `D:/projects/ra2web-jev-player`，GitHub 私有库 `ys118/ra2web-jev-player`（master，最新提交见 `git log -1`） |
| 战绩 | **48 局：8 胜**（近 5 个完整局 3 胜）。当前打法 **A++（骚扰+重拳）**：2 坦骚扰组咬矿车断经济 + 8 辆坦克重拳推平；完整战史见 `docs/LESSONS.md` |
| 学习闭环 | **全自动运转**：每局终局自动复盘（确定性分析 + Jev 语义复盘）→ `docs/LESSONS.md` 账本 → `knowledge/doctrine.json` 限幅自动调参（白名单+Jev 置信>0.6 闸门，**第 48 局首次放行**：tank_cash1→900, tank_cash2→1200） |
| 训练数据 | **第 45 局起每局完整 SFT 元组**（`logs/games/run-<时间戳>/decisions.jsonl`，~300-1200 条/局）；`dataset/` 已重建为 48 局规范结构（4 局 sft-full / 17 局 rl-trajectory / 5 partial / 22 legacy-meta），重建命令 `uv run python scripts/build_training_assets.py` |
| 运行环境 | **headless 已强制**（代码内 `AGENT_BROWSER_HEADED=false`；有头模式在桌面环境会导致 eval 间歇挂死）；浏览器 daemon 挂死时的恢复见 §二.4 |
| 遗留 | 无敌方信息类 bug；主要变量是敌方开局 roll（boom 型局胜率低，属真实对抗方差） |

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
3. **策略演进（有数据支撑的方向）**：
   - 敌方 boom 型开局（经济峰值 >15000）仍是主要败因——可考虑更早的骚扰升级
     或双线骚扰（当前 2 辆坦克）；
   - 侦察链路已验证（敌影推定+双车），可观察是否再加一路军犬常驻巡逻。
   改动走单变量原则（`docs/METHODOLOGY.md`），在 `docs/LESSONS.md` 记录来历。
4. **调参观察**：第 48 局自动调参首次放行（tank_cash1=900），下几局注意观察
   坦克产量与见底率，验证该参数方向是否正确；`knowledge/doctrine.json` 的
   history 字段有完整出处。
5. **数据刷新（游戏更新后必做）**：按 `_research/README.md` 重抓数值；同时对照
   `werhd/werhd-player-api.d.ts` 是否有 API 变化。

## 四、红线（不要越过）

- **每局必须停下汇报，等用户反馈**（AGENTS.md §1，用户明确指定）；
- **禁止清理/覆盖/删除 `logs/` 下任何历史数据**（训练资产）；
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
