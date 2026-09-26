# HANDOFF —— 新 session 冷启动指南

> 本文件由上一个 session 在收尾时编写（2026-09-26）。
> 按 `README.md` 了解项目全貌；本文件只讲**从哪继续、怎么跑起来**。

## 一、当前状态（截至交接时）

| 项 | 状态 |
|---|---|
| 项目 | `D:/projects/ra2web-jev-player`，已推送 GitHub 私有库 `ys118/ra2web-jev-player`（master） |
| 桥接 | `bridge/bridge.py`（127.0.0.1:5174）。**新 session 需要重新启动**（上个进程随 session 结束） |
| 浏览器 | agent-browser 会话 `gonghui`（自带 Chrome for Testing）。交接时处于闲置/半开状态，**建议重开**（见下方流程） |
| 官方体系整局 | **尚未完成一整局**（第 21 局被浏览器渲染问题打断，只验证到"85+ 次决策 0 失败、动作覆盖 deploy/生产/侦察/防御"） |
| 自研体系（legacy-bot） | 20 局完整记录在 `docs/SESSION-REPORT.md`；最佳 27:15 / 击杀 98 |

## 二、恢复运行（照抄即可)

```bash
# 1) 启动桥接（需 TYPESAFE_API_KEY 环境变量，已配用户级）
cd D:/projects/ra2web-jev-player
python bridge/bridge.py        # 或 miniconda python；监听 127.0.0.1:5174

# 2) 打开游戏（无头模式页面默认可见，是长局首选；见 ENGINEERING-NOTES §3.1）
agent-browser --session gonghui open https://gonghui.k0s.cn/
#    → 点"确定"过音频弹窗 → 单机模式 → 遭遇战
#    → 重设：阵营苏俄、速度 2、资金 10000（页面重载后配置会重置！）
#    → 开始游戏

# 3) 挂载官方 Jev 玩家（浏览器控制台，或 agent-browser eval）
const { attachJevPlayer } = await import('http://127.0.0.1:5174/player.mjs')
window.werhdJev = await attachJevPlayer(window.werhd)

# 4) 监控
curl http://127.0.0.1:5174/status          # 决策数/延迟/token
tail -f logs/jev-events.jsonl              # 逐决策审计（若桥接从项目目录启动）
# 看板: http://127.0.0.1:5174/
```

**踩坑快速提醒**（详见 `docs/ENGINEERING-NOTES.md`）：
- 冷启动首载可能黑屏/空文档几秒到几十秒 → **重载一次即恢复**；结算屏开着时不要启动任何玩家脚本。
- 页面必须 `visibilityState === "visible"`，否则 rAF 停摆=模拟冻结；有头窗口在本机会被持续最小化，**用无头**。
- 桥接连 TypeSafe 的 gzip 解压、GBK 请求体、subprocess 树杀等坑已修复，不要回退。

## 三、后续任务（建议优先级）

1. **跑通官方体系完整一局**：无头 + 桥接 + attach，只观察不中途重启；终局后按方法论复盘（`docs/METHODOLOGY.md` 六步闭环），并把结果追加到 `docs/SESSION-REPORT.md`。
2. **官方策略本地化调参**：官方玩家源码在 `refs/examples/jev/`（只读参考；如需改策略，改本地副本并在 `JEV-INTEGRATION.md` 记录改动理由与效果）。
3. **桥接增强（可选）**：`/status` 持久化多局统计；把 `jev-events.jsonl` 的结构化指标（决策/置信度/拒绝原因）做成小结工具。
4. **对照实验（可选）**：同一局面下 legacy-bot vs 官方体系的行为差异记录，为策略库沉淀证据。

## 四、红线（不要越过）

- 只用官方公开的 werhd API；不打排位/联机（只打单机遭遇战）。
- 别在未确认内容已入库的情况下删除任何工作目录（本次清理过程见 git 历史与记忆文件）。

## 五、关键文件索引

| 想知道什么 | 看哪 |
|---|---|
| 项目全貌 / 快速跑 | `README.md` |
| 20 局进化史（每局败因+迭代） | `docs/SESSION-REPORT.md` |
| 怎么迭代 / 怎么调 Jev | `docs/METHODOLOGY.md` |
| 所有引擎/环境坑 | `docs/ENGINEERING-NOTES.md` |
| 桥接协议 / 参数来历 | `docs/JEV-INTEGRATION.md` |
| 官方 API 原文 | `refs/player-console-api.md`、`refs/jev-player-local.md` |
| 攻略/数值真值 | `knowledge/RA2-BIBLE.md`、`knowledge/RA2-UNITS.json` |
| 游戏历史数据 | `logs/bot.log`（自研 20 局）、`logs/jev-events.jsonl`（官方体系审计） |
