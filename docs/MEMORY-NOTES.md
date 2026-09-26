---
name: gonghui-chrono-divide-bot
description: 王二火大(Chrono Divide)网页红警2的 jev 自动对战 bot — werhd 控制台
  API、agent-browser base64 eval 技巧、bot.py 架构与实战教训
metadata:
  node_type: memory
  type: project
  originSessionId: sess_67d1447d-b688-4025-98ee-96db74d0dbee
---

网页红警2《王二火大 CHRONO DIVIDE》(https://gonghui.k0s.cn/, 2026-09-20 实测) 全自动对战项目。

**核心资产：游戏自带 `window.werhd` 玩家控制台 API**（只读本地视野，指令走锁步队列）：
- 查询: `werhd.me()/players()/units('self'|'hostile')/unit(id)/production.queues()/production.available(0-3)/map.size()/canPlace(name,x,y)`
- 指令: `werhd.move/attack/attackMove/stop/deploy(ids)/produce(name,qty)/place(name,x,y)/sell/repair/resign()/camera.centerAt(x,y)`
- 队列: type 0建筑/1防御/2步兵/3载具; status 0空闲/1生产/2暂停/3待放置(建筑需 place)
- 敌我判定: `units('hostile')` 混入 `@@NEUTRAL@@` 平民建筑，必须按 `u.owner.indexOf('@@AI')===0` 过滤
- 本 mod 代码名与标准 RA2 不同: 精炼厂=NAREFN(非NAAREF), 战车工厂前置科技=NAHAND, 载具 HTNK=犀牛/DRON=恐怖机器人/HTK=疑似对空(未验证), 采矿车=HARV

**坑**: agent-browser 是 .cmd shim（走 cmd.exe），多行/复杂引号 JS 传参会被切碎 → 必须 base64: `eval(atob('<b64>'))` 单行传输。agent-browser 全路径 `C:/Program Files/nodejs/agent-browser.cmd`。

**bot**: `~/.zcode/workspace/default/gonghui-bot/bot.py`（miniconda python 跑），架构=快循环（~2s/tick）：单次 eval 拉 JSON 状态 → tsj 批量问 jev（态势/威胁/步兵/建筑，~0.7s）→ werhd 执行。确定性规则管机制（部署基地车只能 `type===7` 且 45s 节流（deploy 异步生效重发会车/厂横跳）、开局序列、经济保底、危险自动防），jev 管语义决策。

**实战教训（12 局迭代：败因次次不同）**: 简单 AI 会快攻，bot 必须从 t=0 就位（开局挂载等待加载期）；AI 波次随时间变大致胜点是早期 4-5 坦克 rush 换家（晚了撞 AI 基防）；美军 AI 爱用火箭飞行兵掏家，苏军哨炮不能对空、需防空炮前置+对空载具；第 9 局坚持 27 分钟击杀 19。第 10-12 局新增引擎坑：①move/attack 封装失效→原始 `werhd.order(ids,4,x,y)`；②大 id 数组被静默丢弃→≤5/批；③**模拟时钟会间歇冻结**（窗口最小化/后台节流）→冻结期队列恒"空闲"会指令垃圾（12 条动员兵/23 条军犬），已加 SIM STALL 守卫（tick 不动就不发指令）；④**rAF 停摆=游戏主循环死亡**，无头合成器不出帧→用 `open --headed` 有头窗口（截图挂起 10060 是冻结前兆）；⑤页面重载后遭遇战配置重置（阵营回随机/速度回6），开局前必须重设；⑥Noul 答案键是 `noul` 非 `probability`。第 11 局随机 roll 到法国/盟军→bot 已加 get_side 阵营自适应（GA*/NA* 代码表+开局序列+法国巨炮提示）。
**v2 攻略驱动版（2026-09-21）**: RA2-UNITS.json 加载为 UNIT_DB（代号→中文名/造价/血量/护甲），克制矩阵反制建议，五态态势机（DEVELOP/DEFEND/RUSH/ATTACK/RECOVER），AI-OPERATING-CARD 蒸馏为 DOCTRINE 常量连同实时战场文本喂 jev（~3k token/次），兵法阈值表 §10.2 全部落码。jev 决策质量实测显著提升（开局序列完全对齐 Bible §5.1，见敌飞行兵→选 HTK 对空 0.61）。
**快响应体系（2026-09-21 下午）**: 防守用攻击移动（Move(0)在红警里"走路不还手"=站桩挨打）；sense_events 事件差分层（建筑掉血即 ALARM）；危机跳过 jev 先打；循环提速至 ~1.6s/tick；TURTLE 条件反击（敌军优势时不送人头，2×兵力才出击，后迭代为1.2×）；坦克预算保护（电厂→矿车→坦克→防御的 checklist 顺序）。
**每局复盘方法论（用户指定）**: 局后 ①战果/时间线 → ②败因链 → ③bot 参数迭代 → ④jev 上下文/指令迭代 → ⑤REPORT.md → ⑥下局验证。第 18-20 局已执行三轮。
**坑续（18-20局）**: ①STATE_JS 漏传 country → get_side 默认盟军 → 开局序列静默失效 450 秒（已修+推断兜底）；②werhd.tick() 已被引擎移除（返回undefined）→ 基于 tick 的守卫误杀正常对局，改用 time()；③防守集结无节流+与 ALARM 反击令互扯（12s 节流+8s 保护期）；④结算屏开着时启 bot 会被正确识别"对局结束"而退出（设计行为，先回设置页再启）。
**官方 API 文档位置（重要）**: `D:/projects/ra2web.github.io/docs/` —— `player-console-api.md`（werhd 完整 API：rules()/inRange(id,id,"current")/units('enemy')/onTick 托管回调/order 对象式目标/桥接/摄像机）、`jev-player-local.md`（官方 Jev 玩家接入规格：本机代理 127.0.0.1:5174，/decide {state,groups}→TypeSafe /v1/systemone，官方曾 16:24 获胜）、`examples/jev/werhd-jev-player.mjs`（官方玩家：页内 150ms micro 微操 + 600ms jev 决策双循环）。**纠错**: werhd.tick() 一直存在（我曾漏写括号）；units('enemy') 比 owner 过滤更准。
**架构升级（2026-09-21 晚）**: 弃自研主循环，改用官方 werhd-jev-player.mjs + 自建 Python 桥接 `gonghui-bot/bridge.py`（GET /player.mjs 服务官方模块；POST /decide→TypeSafe 批量提问；POST /event 审计；SSE /events；GET / 官方看板；GET /status）。挂载：`const {attachJevPlayer}=await import('http://127.0.0.1:5174/player.mjs'); window.werhdJev=await attachJevPlayer(window.werhd)`。实测 P50 1000ms/决策、~1900 tokens/决策、0 错误。桥接坑：TypeSafe 响应 gzip（加 Accept-Encoding: identity + gzip 解压兜底）；请求体解码降级链 utf-8→gbk（Git Bash 测试会发 GBK）。
**完整进化日志**: `~/.zcode/workspace/default/gonghui-bot/REPORT.md`（二十局复盘+架构+路线图），决策日志 `bot.log`/`bridge.log`/`jev-events.jsonl`。第 19 局 27:15/击杀98（最长最烈），第 20 局 17:40/TURTLE 首测通过，第 21 局起用官方体系。

**攻略文档三件套（2026-09-20 建）**: `gonghui-bot/RA2-BIBLE.md`（全维度攻略+兵法+决策清单，56KB）、`AI-OPERATING-CARD.md`（压缩操作卡，可直接当 system prompt）、`RA2-UNITS.json`（机器可读数值表，含弹头×护甲倍率矩阵）。
**数值真值来源（可复用）**: 客户端 `https://game.gongheguozhihui.com/res/overlay/rules.ini`（401KB，1258 section，单位/建筑/武器/全局参数）+ `ra2.csf`（中文名，UTF-16LE 逐字 XOR 0xFFFF 解码）；本地副本与提取表在 `gonghui-bot/_research/`（`rules_extract.md`、`rules_extract2.md`、`csf_decoded.json`、`pages/*.txt` 40+ 篇社区攻略）。引擎语义可从同目录 `app.js`（2.76MB）grep 确认（如 `LandTargeting=1` → 防空炮不能对地）。
**关键修正**: NAHAND 是"苏军兵营"（非科技建筑），战车工厂前置=PROC+NAHAND+NACNST；精炼厂官方配比 `HarvestersPerRefinery=2`；单电厂 150 只够"2 精炼厂+兵营+工厂(135)"；防空炮 1000 金/40 伤害/12 射程/只打空。
