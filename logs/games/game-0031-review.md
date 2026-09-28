# 第 31 局复盘 —— 2026-09-28 09:02

- **结果**: defeat（t=2390 游戏秒, 1592 ticks, 危机 579 ticks）
- **开局建造**: NAREFN@26s → NAHAND@113s → NAWEAP@137s → NAPOWR@224s → NAREFN@248s → NAREFN@250s → NAREFN@251s → NAREFN@253s → NAREFN@254s → NAREFN@256s → NAREFN@257s → NAREFN@259s → NAREFN@260s → NAHAND@262s → NAREFN@550s → NAREFN@849s → NAREFN@1039s → NAREFN@1043s → NAREFN@1045s → NAREFN@1069s → NAREFN@1094s → NAREFN@1096s → NAREFN@1389s → NAREFN@1402s → NAREFN@1404s → NAREFN@1563s → NAREFN@1566s → NAREFN@1739s → NAREFN@1784s → NAREFN@2046s
- **首坦克**: t=224 | 敌基地: 未定位
- **经济**: 平均 814 / 峰值 9148 / 见底率 59%
- **兵力**: 峰值我方 7430 vs 敌 12450 | 坦克峰值 7 | 损失 58 / 可见击杀 109
- **态势分布**: {'defend': 0.87, 'develop': 0.13} | ALARM 83（反击 21 / TURTLE 61）| 停摆 0
- **Jev**: 1200 次决策, 0 错误, P50 730ms / P95 797ms, 态势变更 18 次

## 确定性发现

- [med] NAPOWR 建成于 t=224s，手册窗口 ~45s（慢 398%）
- [high] 敌基地全程未定位 → ATTACK/RUSH 无目标，无法取胜
- [high] 态势 87% 时间在 defend：纯被动挨打，缺进攻闭环
- [med] 危机 tick 占比 36%（579/1592）——长期处于被袭状态

## Jev 复盘

- **根因**: no_target — 侦察失败/敌基地未定位, 进攻态势无目标可打, 全程被动（置信 1.00）
- **下局优先**: fix_scout — 修侦察链路: 保证敌基地定位(军犬+坦克镜像探图), 让进攻有目标（置信 0.99）
- **调参支持度**: 0.5

## 参数迭代（自动, 白名单+限幅）

- 无

## 待办改进（人工/下个 session）

- [ ] 按上表核对下局验证点
