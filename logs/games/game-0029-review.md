# 第 29 局复盘 —— 2026-09-27 21:30

- **结果**: battle-ended（t=None 游戏秒, 492 ticks, 危机 26 ticks）
- **开局建造**: NAREFN@33s → NAHAND@120s → NAWEAP@144s → NAPOWR@231s → NAREFN@257s → NAPOWR@343s → NAPOWR@345s → NAPOWR@346s → NAPOWR@348s → NAPOWR@349s → NAPOWR@352s → NAPOWR@354s → NAPOWR@355s → NAPOWR@357s → NAPOWR@358s → NAPOWR@360s → NAPOWR@361s → NAPOWR@363s → NAPOWR@364s → NAPOWR@366s → NAPOWR@367s → NAPOWR@369s → NAPOWR@370s → NAPOWR@372s → NAPOWR@373s → NAPOWR@375s → NAPOWR@376s → NAPOWR@378s → NAPOWR@379s → NAPOWR@381s → NAPOWR@382s → NAPOWR@384s → NAPOWR@385s → NAHAND@413s → NAHAND@414s → NAHAND@416s → NAHAND@417s → NAHAND@419s → NAHAND@420s → NAHAND@422s → NAHAND@423s → NAHAND@425s → NAHAND@426s → NAHAND@428s → NAHAND@429s → NAHAND@431s → NAREFN@435s → NAHAND@437s → NAREFN@462s → NAWEAP@464s → NAWEAP@465s → NAREFN@468s → NAPOWR@469s → NAPOWR@495s → NAPOWR@496s → NAPOWR@498s → NAPOWR@499s → NAPOWR@501s → NAPOWR@502s → NAPOWR@504s → NAPOWR@505s → NARADR@507s → NAPOWR@508s → NAPOWR@510s → NAPOWR@511s → NAREFN@533s → NAPOWR@572s → NAPOWR@574s → NAPOWR@575s → NAPOWR@592s → NAPOWR@593s → NAPOWR@596s → NAPOWR@597s → NAPOWR@599s → NAPOWR@600s → NAPOWR@602s → NARADR@603s → NARADR@605s → NAPOWR@606s → NAPOWR@608s → NAPOWR@609s → NAPOWR@611s → NAPOWR@612s → NAPOWR@614s → NAPOWR@625s
- **首坦克**: t=231 | 敌基地: 已定位
- **经济**: 平均 2797 / 峰值 9256 / 见底率 32%
- **兵力**: 峰值我方 8600 vs 敌 1130 | 坦克峰值 9 | 损失 12 / 可见击杀 91
- **态势分布**: {'develop': 0.63, 'rush': 0.26, 'attack': 0.11} | ALARM 20（反击 0 / TURTLE 0）| 停摆 0
- **Jev**: 467 次决策, 24 错误, P50 1017ms / P95 1343ms, 态势变更 8 次

## 确定性发现

- [med] NAPOWR 建成于 t=231s，手册窗口 ~45s（慢 413%）
- [high] jev ERR ×24（工程缺陷，逐 tick 失效）
- [med] exec ERR ×3（工程缺陷，逐 tick 失效）

## Jev 复盘

- **根因**: None — ?（置信 -1.00）
- **下局优先**: None — ?（置信 -1.00）
- **调参支持度**: None

## 参数迭代（自动, 白名单+限幅）

- 无

## 待办改进（人工/下个 session）

- [ ] 按上表核对下局验证点
