# HANDOFF —— 新 session 冷启动指南

> 本文件由上一个 session 在收尾时编写（2026-09-26，自包含架构重构版）。
> 按 `README.md` 了解项目全貌、`docs/ARCHITECTURE.md` 看架构定稿；本文件只讲**从哪继续、怎么跑起来**。

## 一、当前状态（截至交接时）

| 项 | 状态 |
|---|---|
| 项目 | `D:/projects/ra2web-jev-player`，GitHub 私有库 `ys118/ra2web-jev-player`（master） |
| 工程形态 | **uv 管理的标准 Python 项目**（src 布局 `src/ra2web_jev_player/`，pyproject.toml+uv.lock）；2026-09-26 完成去桥接化重构：自有 API 层 + 页内客户端 + 全自动进局，`bridge.py` 与官方播放器依赖已移除 |
| 跑法 | `uv run ra2web-jev-play`（全自动整局）/ `ra2web-jev-launch`（只进局）/ `ra2web-jev-attach`（人工开局兜底） |
| agent-browser | 会话名 `ra2web`（`--restore` 持久化、`--idle-timeout 0` 保长局）；由 Python 自动拉起，**无需手动开** |
| 自包含架构整局 | 见 `docs/SESSION-REPORT.md` 追加记录（重构后首局跑在 logs/play-run.log / bot.log） |
| 历史 | legacy 自研 20 局（SESSION-REPORT）+ 官方体系 2 局（P50 1000ms/0 失败） |

## 二、恢复运行（照抄即可）

```bash
# 1) 一条命令全自动（需 TYPESAFE_API_KEY 环境变量，已配用户级）
cd D:/projects/ra2web-jev-player
uv sync                        # 首次/依赖变更后
uv run ra2web-jev-play         # 冷浏览器→进局→注入→托管整局→终局战报(json)
#   常用: --faction 苏俄 --speed 2 --credits 10000 --headed --debug

# 2) 监控（另开终端）
tail -f logs/bot.log           # 决策/建造/攻防行日志
tail -f logs/jev-events.jsonl  # 逐决策审计
```

**踩坑快速提醒**（详见 `docs/ENGINEERING-NOTES.md` 与 `werhd/api.md` §六）：
- launcher 会强制刷新页面弃掉残局（resign 的 canvas 确认框 DOM 不可见，刷新是唯一可靠弃局方式）；
- 页面必须 `visibilityState === "visible"`（无头模式天然满足）；浏览器启动参数已含反 setTimeout 节流（微操 150ms 依赖它，改配置后需 `agent-browser close` 重启会话生效）；
- agent-browser 的 eval 一律 JSON 编码返回值（Python 侧已统一还原，别在 JS 里再包一层 stringify）；
- 结算屏开着时注入会被识别为"对局已结束"——launcher 的强制刷新天然规避。

## 三、后续任务（建议优先级）

1. **跑第 24 局验证闭环**：`uv run ra2web-jev-play`（终局自动复盘）或 `--loop 3` 连跑三局；
   第 23 局复盘的修复项（侦察解包/双造竞态/deploy 收紧）逐项对账，见 `docs/LESSONS.md`。
2. **学习闭环运营**：每局看 `logs/games/game-XXXX-review.md` + `docs/LESSONS.md`；
   自动调参落在 `knowledge/doctrine.json`（白名单+限幅+Jev 闸门，可人工修订）；
   大改进项进 LESSONS 待办由人/agent 实施（METHODOLOGY §〇）。
3. **策略演进**：官方风格的候选组决策（8 组一次请求）替代五问制——官方源码在 `refs/examples/jev/`（只读参考），候选组/复查/冷却设计见 `docs/JEV-INTEGRATION.md` §四。
4. **看板（可选）**：静态页读 `jev-events.jsonl` / game 切片（旧 SSE 看板随桥接废弃）。
5. **对照实验（可选）**：同局面 legacy-bot（`src/ra2web_jev_player/legacy_bot.py`，历史参照）vs 新体系行为差异。
6. **数据刷新（游戏更新后必做）**：按 `_research/README.md` 重抓数值；同时对照 `werhd/werhd-player-api.d.ts` 是否有 API 变化（官方仓库根每次构建重新生成）。

## 四、红线（不要越过）

- 只用官方公开的 werhd API；不打排位/联机（只打单机遭遇战）。
- 别在未确认内容已入库的情况下删除任何工作目录（本次清理过程见 git 历史与记忆文件）。
- Jev 密钥只在 Python 进程内，绝不写进页面/日志/代码。

## 五、关键文件索引

| 想知道什么 | 看哪 |
|---|---|
| 项目全貌 / 快速跑 | `README.md` |
| 架构定稿（分层/数据流/取舍） | `docs/ARCHITECTURE.md` |
| 自有 API 定义（含实测约束） | `src/ra2web_jev_player/werhd/api.md`（类型真相源: 同目录 d.ts） |
| 20 局进化史（每局败因+迭代） | `docs/SESSION-REPORT.md` |
| 怎么迭代 / 怎么调 Jev | `docs/METHODOLOGY.md` |
| 所有引擎/环境坑 | `docs/ENGINEERING-NOTES.md` |
| 桥接协议史 / 官方候选组设计 | `docs/JEV-INTEGRATION.md` |
| 官方 API 原文 | `refs/player-console-api.md` |
| 攻略/数值真值 | `knowledge/RA2-BIBLE.md`、`knowledge/RA2-UNITS.json` |
| 数值/攻略的复现与刷新 | `_research/README.md` |
| 游戏历史数据 | `logs/bot.log`、`logs/jev-events.jsonl` |
