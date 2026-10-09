# -*- coding: utf-8 -*-
"""作战手册与阈值常量 —— 20 局实战复盘的全部沉淀，从 legacy_bot 原样迁移。

来源标注：
- T 阈值表 = docs/knowledge/RA2-BIBLE.md §10.2（每局复盘逐条迭代，第 18-20 局定稿）
- COUNTERS = Bible §1.6/§2 弹头×护甲克制
- TARGET_SCORE = Bible §4.3 进攻目标优先级
- DOCTRINE = docs/knowledge/AI-OPERATING-CARD.md 蒸馏文本（喂 Jev 的作战手册）
改任何一条都必须有新对局的复盘证据（docs/METHODOLOGY.md）。

参数迭代机制：docs/knowledge/doctrine.json 的覆盖值在 import 时加载进 T（复盘驱动的
学习闭环）；每条覆盖带局次出处与理由，git 历史即调参审计轨迹。
"""
import json
import os

from ..paths import KNOWLEDGE_DIR

# 兵法阈值 (Bible §10.2) —— 基线与 legacy_bot 第 20 局后版本一致；
# 带 [第31局] 标注的是 Route A（极限速攻流, 用户拍板）迭代值：
# 24-30 局七连败的结论=防守换不来胜利（AI 波次指数增长, 产能跟不上损耗）,
# 一切资源转为第一波坦克拳头, 3 辆即 rush, 失败进 RECOVER 补经济打二波。
T = dict(
    harv_per_ref=2,      # 每精炼厂 2 矿车 (rules.ini 官方配比)
    harv_min=2,          # 矿车下限
    ref_cap=4,           # 精炼厂上限 [第85局] 3→4: 三厂产能(83局)需匹配收入,
                         # 84 局见底率 52% 实证 6 矿车喂不饱三厂（速攻期实际只
                         # 建 1 座, 见 opening_build 的 ref_cap_now）
    factory2_cash=1800,  # 第二工厂资金门槛 [第40局①] 4500→3000→[第62局用户指示
                         #   "提升出兵速度和规模"]→2400→[第69局 boost_econ]→1800:
                         #   第 68 局实证二厂实为 2900 双闸(factory2_cash 2400 +
                         #   build_gate 2900 叠加), 606-2402 现金从未破 2900,
                         #   二厂只能等 late_game 2402 旁路——去掉叠加后本值即真闸
    tank_cash1=1000,     # 坦克资金保底线 [第31局] 1200→1000
    tank_cash2=1400,     # 双倍出车线 [第31局] 1600→1400
    power_reserve=60,    # 电力余量 <60 先补电厂 [第64局] 30→60: rush 到来瞬间
                         # 缺电致双塔全瞎(活局实证), 塔是吃电单位必须留足余量
    cash_idle=2000,      # 现金 >2000 必须转化
    rush_t0=180,         # RUSH 窗口起点 (3 分钟)
    rush_t1=600,         # RUSH 窗口终点 (10 分钟, 之后放开经济)
    rush_tanks=8,        # [第31局A++] 早期3辆rush已证伪(撞27单位防守军)——不再早rush
    attack_tanks=6,      # 总攻最低坦克数 [第36局 A+B] 8→6（防守损耗矛盾: 与其憋8辆,
                         #   不如6辆+线圈守家提前出击, 单测见 checklist TESLA）
    keep_home=2,         # ≥6 辆时留 2 守家
    harass_dron=2,       # 骚扰组恐怖机器人配额 [第41局, Jev 0.79]: 400金/秒矿车刺客,
                         # 替坦克挨刀——坦克伤亡换便宜的, 断经济效率更高
    retreat_hp=0.40,     # 残血撤退线 (40%)
    defend_radius=18,    # 基地防御半径 (格)
    aa_htk_cap=4,        # [第66局 V3反制] HTK 存量上限(防刷); [第70局用户反馈
                         # 反囤积] V3 响应与 AA 闸门共用此帽——第 69 局 AA 闸门
                         # 无上限刷出 18 辆 HTK 全部囤在基地(用户实证), 4 辆足够
                         # 拦截+防空, 产能让给主战坦克
    aa_screen=4,         # [第72局 P1b] 拦截位屏上限(威胁在场): 屏是防空不是仓库,
                         # 超额 HTK 回归对地编队; 无威胁仍留 2(原第 70 局语义)
    air_evade=14,        # [第73局 用户反馈①] 防空接触规避半径: 可见空中单位距
                         # 突击组 ≤14 格 → 全组后撤到 AA/塔火力圈(坦克打不到空中,
                         # 不挨火箭飞行兵白打; 空威胁由 aahunt 主动猎杀解除)
    siege_push_n=5,      # [第97局 用户反馈"不要空等待"] 8→5: 攒兵太久=在
                         # 基地附近转圈僵持(96 局实证); 前沿集结+5 辆即冲,
                         # 配合 AIR-RESPONSE 反制空军解除回家循环
    v3_seen_window=600,  # [第66局] 见过 V3 后 600gs 内视为威胁活跃(生产响应)
    v3_fire_window=120,  # [第66局] 远程火力签名(建筑掉血+视野内无攻击者)有效窗
    focus_radius=14,     # [第92局 用户反馈②] 坦克点名集火半径: 敌单位距编组
                         # 重心 ≤14 格 → 全组 order_obj 点名同一目标(敌步兵
                         # 优先——坦克被步兵缠斗时白挨打; 一个一个歼灭)
    escort_home_n=4,     # [第92局 用户反馈①] 步坦协同: 坦克出击时步兵留守
                         # 4 人(63 局定值), 超出全部编入突击组跟随;
                         # rush_defense 时留守抬到 GARRISON 地板(8)守塔线
)

# 复盘驱动的参数迭代（学习闭环）：docs/knowledge/doctrine.json 里的覆盖值加载到 T。
# 文件由 review 包（review/tuning.py）在复盘后按"白名单+限幅+置信闸门"自动写入（或人工编辑），
# 每条覆盖带局次出处与理由；git 历史即调参审计轨迹。加载失败/键名不认→静默用默认值。
_DOCTRINE_OVERRIDES = KNOWLEDGE_DIR / "doctrine.json"
_T_DEFAULTS = dict(T)


def load_overrides() -> dict:
    """重新加载 doctrine.json 覆盖到 T（新对局开始时调用，保证 --loop 生效）。"""
    try:
        with open(_DOCTRINE_OVERRIDES, encoding="utf-8") as f:
            ov = json.load(f) or {}
    except Exception:
        ov = {}
    t_ov = ov.get("T") or {}
    applied = {}
    for k, v in t_ov.items():
        if k in _T_DEFAULTS and isinstance(v, (int, float)):
            T[k] = v
            applied[k] = v
        else:
            T[k] = _T_DEFAULTS[k]
    return applied


if os.environ.get("RA2WEB_NO_OVERRIDES", "") == "":
    load_overrides()

# 护甲克制速查: 敌方护甲 -> 我方克制手段(名称+说明), 来自 Bible §1.6/§2
COUNTERS = {
    "none":      [("NALASR", "哨戒炮(100%)"), ("E2", "动员兵海(100%)"), ("HTK", "防空车对地(150%)"), ("DESO", "辐射工兵(100%)")],
    "flak":      [("E2", "动员兵海(80%)"), ("HTK", "防空车对地(150%无甲)"), ("NALASR", "哨戒炮(80%)"), ("DESO", "辐射工兵(100%)")],
    "plate":     [("SHK", "磁爆步兵(100%)"), ("E2", "动员兵(70%)"), ("NALASR", "哨戒炮(70%)")],
    "light":     [("HTK", "防空车(对空100%/对地60%)"), ("NAFLAK", "防空炮(只对空100%)"), ("SHK", "磁爆步兵(85%)"), ("TTNK", "磁能坦克(85%)")],
    "medium":    [("HTNK", "犀牛(100%)"), ("DRON", "恐怖机器人(专咬载具)"), ("TTNK", "磁能坦克(100%)")],
    "heavy":     [("HTNK", "犀牛(100%,5炮杀犀牛)"), ("TESLA", "磁暴线圈(100%,2炮)"), ("SHK", "磁爆步兵(100%)"), ("APOC", "天启(100%×2)")],
    "special_2": [("NAFLAK", "防空炮(150%,射程12)"), ("HTK", "防空车(150%,射程10)"), ("FLAKT", "防空步兵(100%)")],
    "special_1": [("E2", "动员兵枪(100%)"), ("NALASR", "哨戒炮(100%)")],  # 蜘蛛: 只怕机枪
    "concrete":  [("HTNK", "犀牛(60%)"), ("APOC", "天启(70%)"), ("V3", "V3火箭(30%)")],
    "wood":      [("HTNK", "犀牛(65%)"), ("APOC", "天启(100%)")],
    "steel":     [("APOC", "天启(100%)"), ("V3", "V3火箭(50%)")],
}

AIR_UNITS = {"JUMPJET", "ZEP", "SHAD", "ORCA", "HORNOR"}

# [第63局] 英文克制建议(英文投喂用): 护甲 -> [(反制单位码, 英文说明)]
COUNTERS_EN = {
    "none":      [("NALASR", "sentry gun (100%)"), ("E2", "conscript swarm (100%)"), ("HTK", "flak track vs ground (150%)"), ("DESO", "desolator (100%)")],
    "flak":      [("E2", "conscript swarm (80%)"), ("HTK", "flak track vs ground (150% no-armor)"), ("NALASR", "sentry gun (80%)"), ("DESO", "desolator (100%)")],
    "plate":     [("SHK", "tesla trooper (100%)"), ("E2", "conscripts (70%)"), ("NALASR", "sentry gun (70%)")],
    "light":     [("HTK", "flak track (AA 100%/AG 60%)"), ("NAFLAK", "flak cannon (AA only 100%)"), ("SHK", "tesla trooper (85%)"), ("TTNK", "tesla tank (85%)")],
    "medium":    [("HTNK", "rhino (100%)"), ("DRON", "terror drone (anti-vehicle)"), ("TTNK", "tesla tank (100%)")],
    "heavy":     [("HTNK", "rhino (100%, 5 shots per rhino)"), ("TESLA", "tesla coil (100%, 2 shots)"), ("SHK", "tesla trooper (100%)"), ("APOC", "apocalypse (100% x2)")],
    "special_2": [("NAFLAK", "flak cannon (150%, range 12)"), ("HTK", "flak track (150%, range 10)"), ("FLAKT", "flak trooper (100%)")],
    "special_1": [("E2", "conscript rifle (100%)"), ("NALASR", "sentry gun (100%)")],
}


# 进攻目标优先级分 (Bible §4.3): 矿车 > 防空/反坦克防御 > 生产建筑 > 兵营 > 精炼厂 > 电厂 > 建造厂(最后)
TARGET_SCORE = {
    "HARV": 100, "CMIN": 100,
    "NAFLAK": 90, "NASAM": 90, "GTGCAN": 90, "TESLA": 88, "NALASR": 80, "GAPILL": 80,
    "NAWEAP": 82, "GAWEAP": 82, "NAHAND": 76, "GAPILE": 76,
    "NAREFN": 72, "GAREFN": 72, "NAPOWR": 66, "GAPOWR": 66,
    "NATECH": 60, "GATECH": 60, "NARADR": 58, "GAAIRC": 58,
    "NACNST": 40, "GACNST": 40,  # 最后拆(对手可能有基地车重建)
}

HARVEST = {"HARV", "CMIN"}
MCV_CODES = {"SMCV", "AMCV"}
SCOUT_DOGS = ("ADOG", "DOG")
# [第66局 V3反制] 苏军 V3 火箭发射车(射程 18, 塔射程 5.5-12 够不着)远程点名生产
# 建筑——第 65 局战车工厂两建两拆, 坦克峰值 0 的真因。反制 = HTK 防空车
# (500cr, 可拦截 V3 火箭弹道 + 速度 8 能贴脸拆速度 4 的 V3)。
V3_CODES = {"V3"}
AA_VEHICLES = {"HTK"}
# [第57局用户反馈] 防御塔代码表——坦克严禁主动攻击这些(攻击移动会被塔吸火送头),
# 进攻目标只选无攻击力建筑(经济/生产), 塔交给微操/射程外处理
DEF_BUILDINGS = {"TESLA", "NAFLAK", "NALASR", "NAWALL",
                 "GAPILL", "NASAM", "GTGCAN"}

# ================= 作战手册 (AI-OPERATING-CARD 蒸馏, 喂 Jev 的 state 字段) =================
DOCTRINE = """[作战手册·苏军·骚扰+重拳版(A++)]
本局战略(用户拍板): 前2辆坦克=骚扰组, 专咬敌方矿车断其经济、逼其分兵回防; 主力憋到8辆坦克(约10-12分钟)一波推平敌基地. 期间塔阵(1哨戒炮+1防空)守家, 10分钟后放开三矿+第二工厂加速产能. 防守没有胜利条件, 骚扰拖经济+重拳终结.
铁律: 生存>经济>产能>兵力>进攻; 现金>2000必须转化(坦克/矿车); 防空必须有(飞行兵是历史死因); 电力余量<30先补电厂.
克制常识: 坦克炮对步兵仅25%(别用坦克清步兵堆); 坦克对坦克满伤(犀牛5炮杀犀牛/4炮杀灰熊); 光棱拆家不拆坦克, 幻影反坦克不拆家; 恐怖机器人专咬载具(秒矿车); 飞行兵怕防空炮(150%倍率).
进攻目标优先级: 1矿车(断经济) 2工兵 3战车工厂>精炼厂>电厂>兵营(无攻击力建筑) 4建造厂(最后拆). **铁律[用户拍板]: 绝不主动攻击防御塔/哨戒炮/磁暴线圈——攻击移动靠近它们=被吸火送头; 打不到塔就绕开, 只打经济和生产建筑**. 例外: 己方基地被空军偷袭→抽守家单位回防+补防空.
五态态势: DEVELOP(建造序列+骚扰组咬矿车+探图) DEFEND(基地受威胁,守塔阵) RUSH(坦克≥8,与ATTACK同为总攻) ATTACK(坦克≥8,一波推平敌基地) RECOVER(坦克<3,收缩补经济,骚扰组继续).
进攻纪律: 总攻时≥6辆留2守家继续拆生产建筑; 残血(<40%)撤后保老兵; 骚扰组打完矿车就打基地周边生产建筑, 不恋战不送死.
时间窗: 3分钟首坦克→2辆即去咬矿车; 10分钟放开经济; 10-12分钟8辆重拳."""

# [第63局用户指示] Jev 对英文理解优于中文——作战手册/问题/状态全部提交英文版
DOCTRINE_EN = """[Battlefield Manual · Soviet · Harass+Hammer doctrine (A++)]
Strategy (user-approved): first 2 tanks = harass squad, bite enemy harvesters to cut
income and force splits; main force saves up to 8 tanks (~10-12 min) then flattens the
enemy base in one push. Meanwhile tower line (1 sentry gun + 1 flak) defends home; after
minute 10 unlock third refinery + second war factory to ramp production. Defense alone
has NO victory condition: harass their economy + finish with the hammer.
Iron rules: SURVIVAL > economy > production > army > attack; cash > 2000 must be
converted (tanks/harvesters); anti-air is mandatory (rocketeers are a historical death
cause); power margin < 30 -> build power plant first.
Matchup common sense: tank guns only 25% vs infantry (never clear infantry blobs with
tanks); tank vs tank full damage (Rhino 5 shots kills Rhino / 4 kills Grizzly); terror
drone bites vehicles/harvesters only (cannot hurt buildings); flak trooper shreds
rocketeers (150%).
Attack target priority: 1 harvester (cut income) 2 engineer 3 war factory > refinery >
power plant > barracks (undefended buildings) 4 construction yard (last). **IRON RULE
[user-mandated]: NEVER attack defense towers / sentry guns / tesla coils on purpose —
attack-moving into them = free kills for them; if unreachable, go around, only hit
economy and production buildings.** Exception: base under air raid -> pull home guard +
build AA. **ENDGAME SIEGE EXCEPTION [user-mandated 2026-10-04]: when the enemy base is
located, their economy is dead (no harvesters) and our force value >= 1.5x theirs,
SIEGE: the whole army mass-attacks — destroy defensive buildings (pillboxes/towers)
first to silence their guns, then every remaining building. Do not cycle at the shell.**
ADAPTIVE DEFENSE [user-mandated 2026-10-04]: do not execute the build formula blindly.
If an enemy swarm (4+) reaches your door before your army forms and defenders are
outnumbered, switch to RUSH-DEFENSE: spam conscripts (E2) for tower-line defense,
ignoring the tank cash line — survival outranks the formula. Resume the normal
formula the moment the threat clears.
Five stances: DEVELOP (opening ~5min no contact: build, scout, save) DEFEND (base
threatened: hold towers) RUSH (first 10 min with 4+ tanks: swap-base strike) ATTACK
(7+ tanks and enemy base located: focus production buildings, keep 2 home) RECOVER
(main force destroyed: shrink and rebuild economy).
Attack discipline: on total attack keep 2 tanks home, rest hit production buildings;
wounded (<40%) fall back and survive; harass squad hits harvesters then undefended
production buildings, never lingers in tower zones.
Timing windows: first tank by 3min -> 2 tanks go harass; economy unlocked at 10min;
8-tank hammer at 10-12min.
V3 COUNTER (from game 65 loss): enemy V3 launcher range 18 outranges ALL my towers
(sentry 5.5 / tesla 7 / flak 12) and snipes production buildings from stand-off - my
war factory died twice this way, tank count stayed 0. Response is mandatory: when a V3
is spotted OR buildings take fire with no visible attacker (long-range signature),
produce 2x Flak Track (500cr) at once - Flak Tracks shoot V3 rockets out of the air
and their speed 8 catches the launcher (speed 4). Keep Flak Tracks between the threat
direction and my production buildings; they are AA escorts, NOT hammer tanks - never
send them deep into enemy tower zones."""

# Jev 答案采信闸门 (仅态势强制; 生产类收到非 hold 即执行, 见 SESSION-REPORT 18-20 局复盘)
CONF = {"build": 0.40, "inf": 0.35, "veh": 0.35, "stance": 0.45}
# [2026-10-04] 0.6→0.55, 配套决策后端切本地 clef-flash。依据: 828 条影子评测
# (docs/CLEF-LOCAL.md §四)——clef 概率尾部压缩(Jev p90=0.820 vs clef 0.700),
# 0.6 档漏报主导(Jev 触发 clef 漏报 53 vs clef 误报 26; Jev 高烈度>0.75 有 26%
# 被压到 0.6 以下), rush 是当前主要败因, 漏报代价(基地被打)≫误报(坦克白跑)。
# 原 0.6 依据: 第 5-19 局多次 0.7-0.9 正确预警(针对 Jev 校准)。待实战验证。
THREAT_FORCE_DEFEND = 0.55

# ================= 阵营自适应 =================
SOVIET_COUNTRIES = {"Russians", "Confederation", "Africans", "Arabs"}


def get_side(s: dict) -> dict:
    """按 me().country 返回阵营代码表; country 缺失时按建筑/可造列表推断兜底。

    (第 18 局复盘: country 漏传导致开局序列静默失效 450 秒, 推断兜底是必修保险)
    """
    country = (s.get("me", {}).get("country") or "")
    if not country:
        probe = " ".join([u.get("n", "") for u in (s.get("mine") or [])] +
                         [(x if isinstance(x, str) else "")
                          for v in (s.get("av") or {}).values() for x in v])
        if "NAPOWR" in probe or "NAREFN" in probe or "NAHAND" in probe:
            country = "Russians"
        elif "GAPOWR" in probe or "GAREFN" in probe or "GAPILE" in probe:
            country = "Americans"
    if country in SOVIET_COUNTRIES:
        return {"side": "soviet", "powr": "NAPOWR", "ref": "NAREFN", "bar": "NAHAND",
                "weap": "NAWEAP", "aa_b": "NAFLAK", "aa_v": "HTK", "radar": "NARADR",
                # [第59局完败自复盘] 序列必须遵守引擎前置链(NAWEAP prereq 含 NAHAND,
                # 见 RA2-UNITS.json)——第 54 局换位 [.., NAWEAP, NAHAND] 违规, 靠 Jev
                # 插单建兵营 masking 了 5 局, 第 59 局插单门控拆掉补丁后死锁完败。
                # [第67局] 精炼厂先行链 NAREFN→NAHAND→NAWEAP→NAPOWR: NAWEAP 依赖
                # PROC(=精炼厂)+NAHAND 均在前 ✓; 老 33-37 局快开局同构(首坦 230s);
                # 电厂后置由电厂应急闸门(战厂条件)+DEFLINE 余量闸兜底。若引擎拒收
                # NAREFN(无电厂不可造), opening_build 自愈回退旧合法序(见 planner
                # _OPENING_LEGACY), 走 open_fallback。
                "opening": ["NAREFN", "NAHAND", "NAWEAP", "NAPOWR"],
                "tank_pref": ["HTNK", "APOC", "TTNK"], "harv": "HARV", "gdef": "NALASR"}
    return {"side": "allied", "powr": "GAPOWR", "ref": "GAREFN", "bar": "GAPILE",
            "weap": "GAWEAP", "aa_b": "NASAM", "aa_v": None, "radar": "GAAIRC",
            "opening": ["GAPOWR", "GAPILE", "GAREFN", "GAWEAP"],
            "tank_pref": ["MTNK"], "harv": "CMIN", "country": country, "gdef": "GAPILL"}
