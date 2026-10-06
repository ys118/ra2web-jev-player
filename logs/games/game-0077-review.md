# 第 77 局复盘 —— 2026-10-06 15:50

- **结果**: victory（t=8218 游戏秒, 3170 ticks, 危机 399 ticks）
- **开局建造**: NAPOWR@43s → NAREFN@69s → NAHAND@161s → NAWEAP@185s → NAHAND@275s → NAPOWR@301s → NAREFN@325s → NAREFN@506s → NAPOWR@672s → NAREFN@697s → NAREFN@699s → NAREFN@701s → NAREFN@703s → NAREFN@706s → NAREFN@708s → NAREFN@710s → NAREFN@713s → NAREFN@715s → NAREFN@717s → NAREFN@720s → NAREFN@722s → NAREFN@724s → NAREFN@727s → NAREFN@729s → NAREFN@731s → NAREFN@734s → NAREFN@736s → NAREFN@738s → NAREFN@741s → NAREFN@743s → NAREFN@745s → NAREFN@747s → NAREFN@750s → NAREFN@752s → NAREFN@754s → NAREFN@757s → NAREFN@759s → NAREFN@761s → NAREFN@764s → NAREFN@766s → NAREFN@769s → NAREFN@771s → NAREFN@774s → NAREFN@776s → NAREFN@779s → NAREFN@781s → NAREFN@784s → NAREFN@786s → NAREFN@789s → NAREFN@791s → NAWEAP@977s → NAWEAP@1061s → NAPOWR@1202s → NARADR@3604s → NARADR@3607s → NAPOWR@4482s
- **首坦克**: t=275 | 敌基地: 已定位
- **经济**: 平均 834 / 峰值 9778 / 见底率 33%
- **兵力**: 峰值我方 12180 vs 敌 27650 | 坦克峰值 13(重坦口径) | 损失 230 / 可见击杀 239
- **终局构成**: 重坦 5 / 防空车 0 / 步兵 2
- **态势分布**: {'defend': 0.51, 'attack': 0.37, 'recover': 0.06, 'develop': 0.03, 'rush': 0.02} | ALARM 219（反击 31 / TURTLE 32）| 停摆 1
- **Jev**: 3168 次决策, 0 错误, P50 1633ms / P95 1713ms, 态势变更 2 次

## 确定性发现

- [low] 模拟停摆 1 次

## Jev 复盘

- **根因**: attrition — 野战/微操交换比劣势: 兵力换亏, 残血不撤或反击送人头（置信 0.18）
- **下局优先**: boost_econ — 加强经济时序: 二矿/矿车更早, 坦克预算优先级更高（置信 0.30）
- **调参支持度**: 0.5060661438795567

## 参数迭代（自动, 白名单+限幅）

- 无

## 待办改进（人工/下个 session）

- [ ] 按上表核对下局验证点
