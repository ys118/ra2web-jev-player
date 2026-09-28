# 第 36 局复盘 —— 2026-09-28 20:13

- **结果**: victory（t=3013 游戏秒, 1822 ticks, 危机 63 ticks）
- **开局建造**: NAREFN@33s → NAHAND@119s → NAWEAP@143s → NAPOWR@268s → NAREFN@292s → NAHAND@429s → NAHAND@434s → NAHAND@444s → NAHAND@491s → NAHAND@590s → NAREFN@600s → NAWEAP@808s → NAWEAP@953s → NAWEAP@955s → NAWEAP@956s → NAWEAP@958s → NAWEAP@961s → NAWEAP@1019s → NAWEAP@1153s → NAWEAP@1159s
- **首坦克**: t=268 | 敌基地: 已定位
- **经济**: 平均 1048 / 峰值 9293 / 见底率 49%
- **兵力**: 峰值我方 9000 vs 敌 19360 | 坦克峰值 10 | 损失 71 / 可见击杀 66
- **态势分布**: {'attack': 0.42, 'rush': 0.29, 'develop': 0.18, 'defend': 0.1, 'recover': 0.01} | ALARM 62（反击 0 / TURTLE 6）| 停摆 0
- **Jev**: 1200 次决策, 0 错误, P50 722ms / P95 817ms, 态势变更 6 次

## 确定性发现

- [med] NAPOWR 建成于 t=268s，手册窗口 ~45s（慢 496%）
- [med] scout ERR ×1（工程缺陷，逐 tick 失效）

## Jev 复盘

- **根因**: timing — 开局时序过慢: 建造/出兵晚于手册窗口, 被早期 rush 打崩（置信 0.35）
- **下局优先**: boost_econ — 加强经济时序: 二矿/矿车更早, 坦克预算优先级更高（置信 0.19）
- **调参支持度**: 0.4

## 参数迭代（自动, 白名单+限幅）

- 无

## 待办改进（人工/下个 session）

- [ ] 按上表核对下局验证点
