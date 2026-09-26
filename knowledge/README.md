# knowledge —— 攻略与数值（AI 决策依据）

> 本目录是喂给 Jev / 决策层的**知识底座**，三份文件分工不同、来源同一套数据。
> 原始数据与复现方法见 `../_research/README.md`。

## 一、三份文件怎么用

| 文件 | 是什么 | 用法 |
|---|---|---|
| `RA2-BIBLE.md` | 全维度攻略（638 行）：基础概念/兵种图谱/经济/战斗/开局/战术/微操/**兵法映射**/**决策清单** | 长上下文知识库；做策略迭代、复盘归因、写新规则时查 |
| `AI-OPERATING-CARD.md` | 压缩操作卡（~6 KB）：十条铁律、每 tick 清单、阈值表、五态机、禁止清单 | **直接作为系统提示词**喂给决策模型（比 Bible 省 token） |
| `RA2-UNITS.json` | 机器可读数值：40+ 单位/建筑（造价·血量·护甲·武器）+ 27 种弹头 × 11 种护甲倍率 + 全局参数 | 代码 `import json` 直接读；不要从 Markdown 里解析数字 |

配合方式（本项目的实践）：`RA2-UNITS.json` → 反制/选兵逻辑；`AI-OPERATING-CARD.md` 蒸馏成固定 DOCTRINE 文本 + 实时战场文本一起喂 Jev；`RA2-BIBLE.md` 供人/agent 查阅与迭代。

## 二、出处与版本（重要）

- **数值**：游戏客户端原文件 `rules.ini` + `ra2.csf`（抓取于 **2026-09-20**，客户端 **v0.87.0-r79e73e7**，`mod id = gonghui`）。中文名由 CSF 解码得到。
- **战术**：社区攻略 43 篇（红警之家 uc129 / 游侠 / 贴吧 / 萌娘百科），原文在 `../_research/pages/`。
- **工程约束**：自研直调 werhd 的 20 局实战复盘（`../legacy-bot/`、`../docs/SESSION-REPORT.md`、`../docs/ENGINEERING-NOTES.md`）。

⚠️ **数值与版本绑定**：游戏更新后（首页可看版本号）须按 `../_research/README.md` 的流程重抓重生成，再跑 `verify.py` 对账。

## 三、使用注意（避免误用）

1. **`RA2-BIBLE.md` §8/§10 里"每批 ≤5 单位、同目标 12s 节流、部署 45s 节流"是"自研直调 werhd"时代的约束**；官方 `werhd-jev-player` 的适配层会自动分批并带单位级冷却（见 `../docs/ENGINEERING-NOTES.md` §二）。两套体系不要混着照抄。
2. **数值是"这个 mod 的这个版本"的真值**，不是原版 RA2 的通用值；社区文章的个别说法（如"共辉幻影前置低""刷钱工具"）在 rules.ini 中找不到对应实现，Bible §11.3 已单列不确定项。
3. **比例关系比绝对值更耐用**：例如"犀牛 5 炮杀犀牛、灰熊 7 炮才杀犀牛"来自 `伤害 × 弹头倍率 ÷ 血量`，即使版本微调也基本成立。
4. **`RA2-UNITS.json` 的 `verses` 顺序**固定为 `none, flak, plate, light, medium, heavy, wood, steel, concrete, special_1, special_2`（见文件内 `meta.armor_classes`），乘算即伤害：`damage × burst × verses[护甲]`。

## 四、已知不确定项（摘要，详见 `RA2-BIBLE.md` §11.3）

- 建造时间：`rules.ini` 无 `BuildTime` 字段，只能按造价推算相对快慢。
- 采矿单趟金额：ini 给"25 金/格 × 45 格"，社区实测约 1000/趟（武矿 ≈ 超时空 2 倍）——按后者用。
- 升级击杀门槛公式未在引擎里逐条验证；可靠结论是"门槛与造价成正比"。
- 防空履带车（HTK）对空数值具备（35/25/10），但**实战击杀验证**建议在复盘里记录一例。
