# 第 35 局复盘 —— 2026-09-28 16:02

- **结果**: defeat（t=1484 游戏秒, 953 ticks, 危机 152 ticks）
- **开局建造**: NAREFN@33s → NAHAND@119s → NAWEAP@139s → NAPOWR@224s → NAREFN@249s → NAREFN@251s → NAREFN@253s → NAREFN@254s → NAREFN@256s → NAREFN@257s → NAREFN@259s → NAREFN@260s → NAREFN@262s → NAHAND@263s → NAREFN@290s → NAREFN@292s → NAREFN@382s → NAREFN@548s → NAREFN@670s → NAREFN@671s → NAREFN@798s → NAREFN@892s → NAREFN@998s
- **首坦克**: t=224 | 敌基地: 已定位
- **经济**: 平均 1209 / 峰值 9294 / 见底率 61%
- **兵力**: 峰值我方 4940 vs 敌 34130 | 坦克峰值 6 | 损失 54 / 可见击杀 70
- **态势分布**: {'defend': 0.68, 'develop': 0.21, 'attack': 0.11} | ALARM 37（反击 3 / TURTLE 21）| 停摆 0
- **Jev**: 952 次决策, 0 错误, P50 829ms / P95 1024ms, 态势变更 33 次

## 确定性发现

- [med] NAPOWR 建成于 t=224s，手册窗口 ~45s（慢 398%）
- [med] 资金长期见底（<200 金占比 61%），坦克生产线被步兵/防御挤占
- [med] scout ERR ×5（工程缺陷，逐 tick 失效）

## Jev 复盘

- **根因**: starve — 经济或产能断粮: 坦克上不了产线, 资金长期见底, 步兵/防御吃掉预算（置信 0.91）
- **下局优先**: boost_econ — 加强经济时序: 二矿/矿车更早, 坦克预算优先级更高（置信 0.69）
- **调参支持度**: 0.42

## 参数迭代（自动, 白名单+限幅）

- 无

## 待办改进（人工/下个 session）

- [ ] 按上表核对下局验证点
