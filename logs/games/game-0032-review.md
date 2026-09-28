# 第 32 局复盘 —— 2026-09-28 14:06

- **结果**: defeat（t=1206 游戏秒, 802 ticks, 危机 368 ticks）
- **开局建造**: NAREFN@33s → NAHAND@119s → NAWEAP@143s → NAPOWR@230s → NAREFN@254s → NAREFN@256s → NAREFN@257s → NAREFN@259s → NAREFN@260s → NAREFN@262s → NAREFN@263s → NAREFN@265s → NAREFN@266s → NAREFN@268s → NAREFN@269s → NAREFN@271s → NAREFN@272s → NAREFN@274s → NAREFN@275s → NAREFN@280s → NAREFN@281s → NAHAND@284s → NAREFN@605s → NAREFN@721s
- **首坦克**: t=230 | 敌基地: 未定位
- **经济**: 平均 1478 / 峰值 9293 / 见底率 66%
- **兵力**: 峰值我方 3340 vs 敌 4810 | 坦克峰值 2 | 损失 46 / 可见击杀 60
- **态势分布**: {'defend': 0.88, 'develop': 0.12} | ALARM 48（反击 7 / TURTLE 41）| 停摆 0
- **Jev**: 801 次决策, 0 错误, P50 838ms / P95 1020ms, 态势变更 1 次

## 确定性发现

- [med] NAPOWR 建成于 t=230s，手册窗口 ~45s（慢 411%）
- [high] 敌基地全程未定位 → ATTACK/RUSH 无目标，无法取胜
- [med] 资金长期见底（<200 金占比 66%），坦克生产线被步兵/防御挤占
- [med] 15 分钟后坦克峰值仅 2 辆（总攻门槛 6）——产能/资金被别处吃掉
- [high] 态势 88% 时间在 defend：纯被动挨打，缺进攻闭环
- [med] 危机 tick 占比 46%（368/802）——长期处于被袭状态

## Jev 复盘

- **根因**: no_target — 侦察失败/敌基地未定位, 进攻态势无目标可打, 全程被动（置信 0.93）
- **下局优先**: fix_scout — 修侦察链路: 保证敌基地定位(军犬+坦克镜像探图), 让进攻有目标（置信 0.89）
- **调参支持度**: 0.56

## 参数迭代（自动, 白名单+限幅）

- 无

## 待办改进（人工/下个 session）

- [ ] 按上表核对下局验证点
