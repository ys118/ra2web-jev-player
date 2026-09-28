# -*- coding: utf-8 -*-
"""作战手册与阈值常量 —— 20 局实战复盘的全部沉淀，从 legacy_bot 原样迁移。

来源标注：
- T 阈值表 = knowledge/RA2-BIBLE.md §10.2（每局复盘逐条迭代，第 18-20 局定稿）
- COUNTERS = Bible §1.6/§2 弹头×护甲克制
- TARGET_SCORE = Bible §4.3 进攻目标优先级
- DOCTRINE = knowledge/AI-OPERATING-CARD.md 蒸馏文本（喂 Jev 的作战手册）
改任何一条都必须有新对局的复盘证据（docs/METHODOLOGY.md）。

参数迭代机制：knowledge/doctrine.json 的覆盖值在 import 时加载进 T（复盘驱动的
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
    ref_cap=3,           # 精炼厂上限（速攻期实际只建 1 座, 见 opening_build 的 ref_cap_now）
    factory2_cash=3000,  # 第二工厂资金门槛 [第40局①] 4500→3000（对局证据: 敌方经济
                         #   boom>12000 时单工厂产能追不上; 速攻期 t<rush_t1 仍不建）
    tank_cash1=1000,     # 坦克资金保底线 [第31局] 1200→1000
    tank_cash2=1400,     # 双倍出车线 [第31局] 1600→1400
    power_reserve=30,    # 电力余量 <30 先补电厂
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
)

# 复盘驱动的参数迭代（学习闭环）：knowledge/doctrine.json 里的覆盖值加载到 T。
# 文件由 review.py 在复盘后按"白名单+限幅+Jev 置信闸门"自动写入（或人工编辑），
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

# ================= 作战手册 (AI-OPERATING-CARD 蒸馏, 喂 Jev 的 state 字段) =================
DOCTRINE = """[作战手册·苏军·骚扰+重拳版(A++)]
本局战略(用户拍板): 前2辆坦克=骚扰组, 专咬敌方矿车断其经济、逼其分兵回防; 主力憋到8辆坦克(约10-12分钟)一波推平敌基地. 期间塔阵(1哨戒炮+1防空)守家, 10分钟后放开三矿+第二工厂加速产能. 防守没有胜利条件, 骚扰拖经济+重拳终结.
铁律: 生存>经济>产能>兵力>进攻; 现金>2000必须转化(坦克/矿车); 防空必须有(飞行兵是历史死因); 电力余量<30先补电厂.
克制常识: 坦克炮对步兵仅25%(别用坦克清步兵堆); 坦克对坦克满伤(犀牛5炮杀犀牛/4炮杀灰熊); 光棱拆家不拆坦克, 幻影反坦克不拆家; 恐怖机器人专咬载具(秒矿车); 飞行兵怕防空炮(150%倍率).
进攻目标优先级: 1矿车(断经济) 2工兵 3防空/反坦克塔 4战车工厂>兵营>精炼厂>电厂 5建造厂(最后拆). 例外: 己方基地被空军偷袭→抽守家单位回防+补防空.
五态态势: DEVELOP(建造序列+骚扰组咬矿车+探图) DEFEND(基地受威胁,守塔阵) RUSH(坦克≥8,与ATTACK同为总攻) ATTACK(坦克≥8,一波推平敌基地) RECOVER(坦克<3,收缩补经济,骚扰组继续).
进攻纪律: 总攻时≥6辆留2守家继续拆生产建筑; 残血(<40%)撤后保老兵; 骚扰组打完矿车就打基地周边生产建筑, 不恋战不送死.
时间窗: 3分钟首坦克→2辆即去咬矿车; 10分钟放开经济; 10-12分钟8辆重拳."""

# Jev 答案采信闸门 (仅态势强制; 生产类收到非 hold 即执行, 见 SESSION-REPORT 18-20 局复盘)
CONF = {"build": 0.40, "inf": 0.35, "veh": 0.35, "stance": 0.45}
THREAT_FORCE_DEFEND = 0.6   # 威胁概率 >0.6 强制回防 (第 5-19 局多次 0.7-0.9 正确预警)

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
                "opening": ["NAPOWR", "NAREFN", "NAHAND", "NAWEAP"],
                "tank_pref": ["HTNK", "APOC", "TTNK"], "harv": "HARV", "gdef": "NALASR"}
    return {"side": "allied", "powr": "GAPOWR", "ref": "GAREFN", "bar": "GAPILE",
            "weap": "GAWEAP", "aa_b": "NASAM", "aa_v": None, "radar": "GAAIRC",
            "opening": ["GAPOWR", "GAPILE", "GAREFN", "GAWEAP"],
            "tank_pref": ["MTNK"], "harv": "CMIN", "country": country, "gdef": "GAPILL"}
