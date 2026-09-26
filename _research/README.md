# _research —— 攻略与数值的研究存档（可复现）

> 本目录是 `knowledge/` 三件套的**上游**：原始数据、抓取/提取脚本、社区攻略原文与检索留档。
> 结论已经蒸馏进 `../knowledge/RA2-BIBLE.md` / `AI-OPERATING-CARD.md` / `RA2-UNITS.json`；
> 本文件负责回答"这些结论从哪来、怎么重新生成、有什么坑"。

## 一、这里得出了什么

| 产出 | 文件 | 说明 |
|---|---|---|
| 数值真值 | `rules.ini`（401 KB，1258 section） | 游戏客户端原文件：单位/建筑/武器/弹头/全局参数 |
| 中文名表 | `csf_decoded.json`（4523 条，4519 非空） | 代号→中文（`NAME:HTNK`→`犀牛坦克`），由 `ra2.csf` 解码 |
| 提取表 | `rules_extract.md` / `rules_extract2.md` | 单位·建筑·武器·**弹头×护甲倍率矩阵**·超武冷却·经济参数 |
| 机器可读 | `../knowledge/RA2-UNITS.json` | 40+ 单位/建筑的数据表，供代码读取（由 `gen_json.py` 生成） |
| 战术来源 | `pages/*.txt`（43 篇） | 红警之家/游侠/贴吧/萌娘百科社区攻略原文 → 蒸馏进 RA2-BIBLE |

**已确认的关键机制**（写进文档的硬结论，均可在此目录复核）：
- 弹头×护甲倍率（`rules.ini` 的 `Verses=`）：坦克炮对步兵 25%、光棱对建筑 200%/对重甲 50%、幻影对重甲 100%/对建筑 20-30%、防空炮对空 150%。
- 防空炮/爱国者**只打空**：`LandTargeting=1`；引擎枚举 `app.js` 中 `LandOk=0 / LandNotOk=1 / LandSecondary=2`。
- 电力：磁能电厂 +150 / 盟军电厂 +200；精炼厂 -50、兵营 -10、工厂 -25、雷达 -50、线圈 -75、防空炮 -50、**哨戒炮 0**。
- 缺电惩罚：生产速度上限 ×0.5（最差 ×0.1），`Powered=yes` 的防御塔离线。
- 多工厂加速 `MultipleFactory=0.5`；出售返还 50%；官方配比 `HarvestersPerRefinery=2`。
- 矿：黄矿 25 金/格、彩矿 50 金/格；矿车容量 45（苏）/25（盟）；矿石精炼器 +25%；间谍偷 50% 现金。
- 升级：`VeteranROF=0.6`、速度/视野 ×1.2、装甲 ×1.5，门槛与造价成正比（`VeteranRatio=3`）。

## 二、复现 / 刷新流程（照抄即可）

> 前提：本机只能访问国内站点。Python 统一走项目 uv 环境：repo 根 `uv sync --all-groups`
> 之后，任意目录 `uv run python ...`（research 依赖组自带 requests）；miniconda python
> （`C:/Users/15652/miniconda3/python.exe`）作后备。
> 游戏版本变化后（首页可见，如 v0.87.0-r79e73e7）按此流程整体刷新。

```bash
cd D:/projects/ra2web-jev-player/_research

# 1) 抓客户端数据（rules.ini 是关键；ra2.csf 是中文名；app.js 用于查引擎语义）
curl -s -A "Mozilla/5.0" -o rules.ini https://game.gongheguozhihui.com/res/overlay/rules.ini
curl -s -A "Mozilla/5.0" -o ra2.csf   https://game.gongheguozhihui.com/res/overlay/ra2.csf
#    app.js / art.ini / version.json / config.json 同站（具体路径看首页 <script src>）

# 2) 中文名表
uv run python decode_csf.py                 # ra2.csf -> csf_decoded.json（4523 条）
uv run python decode_csf.py --compare       # 与现有文件比对（自检）

# 3) 数值提取表
uv run python extract_rules.py && uv run python extract2.py   # -> rules_extract.md / rules_extract2.md

# 4) 机器可读表（写入 ../knowledge/RA2-UNITS.json；重生成应与归档逐字节一致）
uv run python gen_json.py

# 5) 对账校验（56 项：单位/武器/建筑/弹头倍率/全局参数）
uv run python verify.py

# 6) 战术抓取（可选，media 站点结构可能变）
uv run python web.py search "红警2 苏军 战术"      # 搜索（Bing RSS 通道）
uv run python fetch_pages.py                       # 按清单抓文章 -> pages/
```

## 三、本目录独有的坑（血泪）

1. **Bash 传中文参数会被 GBK 转码**（Git Bash → curl/Bing 收到乱码，搜出"红色文化"之类无关结果）。
   → 中文一律写进 `.py` 脚本（用编辑器/Write 工具写 UTF-8）再执行；命令行只传 ASCII。
2. **外网不可达**（google/fandom/github/wiki 超时）→ 用 `cn.bing.com` 的 **`format=rss`** 通道，最稳。
   `baidu.com` 可访问；`sogou` 302；`baike.baidu.com` 对脚本 403。
3. **Bing RSS 会降级长查询**：查询词太长会返回泛结果 → 用**短查询 + `site:` 前缀**（如 `site:uc129.com 战术`）。
4. **CSF 解码三个坑**（`decode_csf.py` 已处理）：
   - 值区是 UTF-16LE，**每个码元 XOR 0xFFFF**（`\xff\xa0` → `开`）；
   - `LBL` 记录里比标准多一个 int32（值个数=1）；
   - 带 `W` 标记的记录（`WRTS`）值后还跟一段 `int32 长度 + ASCII`（如 `VOX:CEVA001` → `ceva001` 音频名）。
   旧版解码漏了第 3 点 → 1204 条语音为空；现版覆盖 4523/4523。
5. **`rules.ini` 没有 `BuildTime` 字段**：建造时间按造价累计（`app.js`: `cost/buildSpeed*multi, 54`），只能给相对值。
6. **`app.js` 里另有一张"竞速模式"参数表**（`HTNK:{health:1080,maxSpeed:221,...}`），**不要与 rules.ini 混用**。
7. `werhd.help()` / 控制台 API 的事实以 `../refs/player-console-api.md` 为准（本目录不重复）。

## 四、`pages/` 来源索引（43 篇社区攻略）

| 文件 | 来源/主题 | 关键结论 |
|---|---|---|
| `su-yilake-zhanhs.txt` | 苏军(主伊拉克)战术 | 坦克<8 不进攻；双线骚扰 10 坦克分两队；防偷家/反履带车；卖家极限进攻；蜘蛛上牛时机 |
| `allied-tactics.txt` | 1.006 盟军战术 | 空指流 vs 坦克流；4 蚊+1 机（打建筑需同时攻击）；法国巨炮最晚三矿车后；幻影打矿车是盟军内战本质 |
| `unit-ranking.txt` | 1.06 坦克排行 | 超时空 > 天启 > 坦克杀手 > 幻影 > 犀牛 > 灰熊 > 光棱 |
| `soviet-units*.txt`（5 页） | 苏联兵种大全 | 各兵种用法与数值；超武/油井/维修等细节 |
| `rhino-cross.txt` | 犀牛"死亡十字架" | 犀牛射程近似正圆、比地堡远一格 → 静止单位被完克 |
| `miner-efficiency.txt` | 矿车效率 | 武矿 ≈1000 金/趟 vs 超时空 ≈500；精炼器 ×1.25；"手牛"技巧 |
| `online-tips.txt` | 高手心得（YG/Archon） | 冰天开局；抢中后须"一边出兵一边发展"；连输多局当天停 |
| `team-tips.txt` / `practical-guide.txt` | 战队技巧/实用攻略 | 快捷键（U 选血、Ctrl+Alt 保护）；耗电表；颜色学；履带车别贸然收基地 |
| `stance-modes.txt` | 单位姿态机制 | 移动攻击/警戒/巡逻/保护/防御的差异；同射程对峙的先手规则 |
| `tank-ops*.txt`（3 页） | 坦克操作大全 | 躲炮弹四法（山崖/矿场/T 字/掉头）；碉堡死角；黑鹰轰炸基地流程 |
| `tank-wheel-pull.txt` | 坦克轮拉 | 轮流后拉诱敌跟进，制造输出窗口 |
| `apoc-rad.txt` | 天启+辐射 | 相持期用；盟军用"灰熊+飞兵"即可破 |
| `strongest-nation*.txt`（3 页） | 两阵营科技对比 | 逐项胜方（电力苏/空军盟/资源收集盟/防御塔盟…），结论"各有特长" |
| `infant-test.txt` | 大兵 vs 动员兵实测 | 同价值动员兵完胜；大兵靠"部署站位+近身改姿态"可翻盘 |
| `spider-miner.txt` | 蜘蛛上牛 | 倒矿时出手；正后方 100% 成功；借建筑掩护 |
| `skills-buff.txt` | 间接技能与 buff | 幻影真正价值=让对方坦克无法自动攻击；无限连射机制 |
| `ice-map-1v1.txt` | 冰天雪地 1v1/2v2 | 信息量最大：苏军"电兵矿重矿矿电重重"、11 苏军开局、混战 <4000 出矿场/≥4000 出重工 |
| `b2map.txt` | B2 地图 | 跑狗 4 只；重工流 A/B 区别；无畏别碰基地；小岛 8000 金 |
| `cuba-boom.txt` / `libya.txt` | 古巴/利比亚 | 伊文炸弹车（车尾贴住建筑）；铁幕运输船+自爆卡车 |
| `1v7cold.txt` | 1v7 冷酷 | 速灭最近一家；复制中心免费出兵 |
| `ghost-tank.txt` | 共辉幻影 | 完全隐形；前期袭矿车；后期幻影+光棱组合 |
| `quick-start.txt` / `vs-tips.txt` / `ali213-guide.txt` | 共辉速成/对战/技巧 | 标准开局；反中国=爆蜘蛛+6-7 辐射工兵；磁暴步兵给线圈充能 |
| `fly-tactics.txt` | 共辉飞兵流 | 磁力场→矿场→兵营→空指→堆飞兵；对手一般不先造防空 |
| `hongjing-xinjing.txt` | 《红警心经》 | 对位口诀（坦杀+黑鹰打矿场；防海豹捣龙庭等） |
| `zatan-summary.txt` | 攻略战术杂谈 | 与 `online-tips` 同源，汇总版 |
| `moegirl-prism.txt` / `moegirl-grizzly.txt` | 萌娘百科 | 光棱（1200/150/射程 10）与灰熊（700/300/速 7/翻车机制）详细数据 |
| `moegirl-apoc/drone/ifv.txt` | 萌娘百科 | **抓取失败占位**（200-230 字节），需重抓 |
| `yili-tactics.txt` | uc129 尤里栏目 | 仅栏目页标题，无正文 |

## 五、校验记录

| 日期 | 项 | 结果 |
|---|---|---|
| 2026-09-20 | `verify.py` 56 项对账（对 `../knowledge/RA2-UNITS.json`） | **56/56 通过** |
| 2026-09-20 | 引擎语义（`app.js` grep）：`LandTargeting` 枚举、建造时间公式、导弹/武器字段 | 已确认并写入文档 |
| 2026-09-26 | `decode_csf.py` 重写并全量复验 | 4523/4523 覆盖；非空 4519（旧版 3315）；1204 条差异全为 `WRTS` 语音条目 |
| 2026-09-26 | `gen_json.py` 重生成 `RA2-UNITS.json` | 与归档**逐字节一致**（管道可复现） |
| 2026-09-26 | 路径适配 | `gen_json.py` / `verify.py` 已适配"repo 根 + knowledge/"布局 |
| 2026-09-26 | `decode_csf.py --compare` NameError 修复（`v` 未定义，自检模式此前从未跑通） | 修复后比对：4523 共同键全部一致 |

## 六、与其它目录的关系

- 结论成品 → `../knowledge/`（攻略三件套）
- 引擎/浏览器/API 的坑 → `../docs/ENGINEERING-NOTES.md`（本目录只记"研究"层面的坑）
- 官方 API 原文 → `../refs/player-console-api.md`
- 实战复盘与方法论 → `../docs/SESSION-REPORT.md`、`../docs/METHODOLOGY.md`
