# -*- coding: utf-8 -*-
"""Jev 五问构造（build/inf/veh/stance/threat）——从 legacy_bot jev_decide 原样迁移。

语义术语表是第一杠杆：内部代码全部经 nm() 翻译成中文再进 criteria；
一次请求批量问全部问题（比逐问省 ~10x 延迟/费用）。
"""
from __future__ import annotations

from .doctrine import DOCTRINE, T, get_side
from .state import (UDB, available, buildings, enemy_intel_lines, force_value,
                    nm, ucost)


def build_state_text(s: dict, home, mem) -> str:
    """战场快照 → 分层中文战报（20 局验证的投喂顺序：事件→力量对比→状态→敌情）。"""
    cred = s["me"]["credits"]
    pw = s["me"]["power"].get("total", 0)
    drain = s["me"]["power"].get("drain", 0)
    bl = buildings(s["mine"])
    units: dict = {}
    for u in s["mine"]:
        if u["o"] != 2:
            units[u["n"]] = units.get(u["n"], 0) + 1
    qs = {q["t"]: q for q in s["queues"]}

    def ql(t):
        q = qs.get(t)
        if not q:
            return "无"
        st = {0: "空闲", 1: "生产中", 2: "暂停", 3: "待放置"}.get(q.get("s"), "?")
        its = ",".join("%s%%%d" % (i["n"], i["p"]) for i in q.get("items", [])) or "-"
        return "%s[%s]" % (st, its)

    my_val, en_val = force_value(s)
    ev_txt = "\n".join("· " + e for e in reversed((mem.events or [])[-5:])) or "无"
    lines = [
        "== 最近事件(新→旧, 即时战况) ==",
        ev_txt,
        "兵力价值对比: 我方≈%d vs 视野内敌军≈%d | 近期受袭 %d 次/2分钟"
        % (my_val, en_val, len(mem.alarm_times)),
        "== 战场状态 ==",
        "时间%ds(约%d分钟) 资金%d 电力:%s(余量%d,需求%d/容量%d) 雷达:%s" % (
            s["t"], s["t"] // 60, cred,
            "缺电!" if s["me"]["power"].get("isLowPower") else "正常",
            pw - drain, drain, pw,
            "不可用" if s["me"].get("radarDisabled") else "正常"),
        "我方建筑: %s" % (", ".join("%s(%s)x%d" % (k, nm(k), v)
                                    for k, v in sorted(bl.items())) or "无"),
        "我方部队: %s" % (", ".join("%s(%s)x%d" % (k, nm(k), v)
                                    for k, v in sorted(units.items())) or "无"),
        "队列 建筑:%s | 防御:%s | 步兵:%s | 载具:%s" % (ql(0), ql(1), ql(2), ql(3)),
        "可造建筑: %s" % _avl(s, 0),
        "可造防御: %s" % _avl(s, 1),
        "可造步兵: %s" % _avl(s, 2),
        "可造载具: %s" % _avl(s, 3),
        "== 敌情 ==",
        enemy_intel_lines(s["hostile"]),
        "敌基地坐标: %s" % (mem.enemy_base or "未侦察到"),
        "基地位置:%s" % (home,),
    ]
    return "\n".join(lines)


def _avl(s: dict, t: int) -> str:
    return ", ".join("%s(%s,%d金)" % (n, nm(n), ucost(n)) for n in available(s["av"], t)) or "无"


def build_questions(s: dict, home, mem, stance: str = "develop") -> tuple:
    """返回 (state, questions)。候选里已剔除超限项（精炼厂≤2/兵营≤2/军犬≥4）。"""
    side = get_side(s)
    n_ref = len([u for u in s["mine"] if u["n"] == side["ref"]])
    n_bar = len([u for u in s["mine"] if u["n"] == side["bar"]])
    n_dog = len([u for u in s["mine"] if u["n"] in ("ADOG", "DOG")])
    av0 = [n for n in available(s["av"], 0)
           if not (n == side["ref"] and n_ref >= T["ref_cap"])
           and not (n == side["bar"] and n_bar >= 2)]
    av2 = available(s["av"], 2)
    if n_dog >= 4:
        av2 = [x for x in av2 if x not in ("ADOG", "DOG")]   # 第 12 局: 军犬失控 23 条
    av3 = available(s["av"], 3)
    txt = build_state_text(s, home, mem)
    faction = "%s侧·国家%s 开局序列: %s" % (
        side["side"], side.get("country", "?"), "→".join(side["opening"]))
    if side.get("country") == "French":
        faction += ("。法国专属: 巨炮GTGCAN(2000金,150伤/射程15,需雷达)"
                    "——三矿车之后强烈建议造1-2座守基地方向路口")
    state = {"battlefield": txt, "doctrine": DOCTRINE, "faction": faction}

    Q = {}
    crit_b = {n: "%s(%d金)" % (nm(n), ucost(n)) for n in av0}
    crit_b["hold"] = "本tick不开新建筑"
    Q["build"] = {"type": "choice",
                  "instructions": ("建造参谋: 选下一个开始生产的建筑(队列一次一个)。"
                                   "按手册优先级: 补电力>经济精炼厂(≤2座)>兵营(战车工厂前置,出步兵)"
                                   ">战车工厂>雷达或空指部(开图解锁科技)>对空建筑>实验室。"
                                   "结合当前时间窗、资金和阵营判断。资金充裕且队列空闲时绝不选hold。"),
                  "criteria": crit_b}
    if av2:
        crit_i = {n: "%s(%d金)" % (nm(n), ucost(n)) for n in av2}
        crit_i["hold"] = "不造步兵"
        Q["inf"] = {"type": "choice",
                    "instructions": ("选一种步兵生产。军犬=侦察+预警(视野9); "
                                     "动员兵90金性价比之王(同价完胜大兵),可进驻建筑; "
                                     "磁爆步兵反装甲+可给线圈充能; 防空步兵机动防空; "
                                     "工程师占家/修车。按敌情和资金选,无需时hold。"),
                    "criteria": crit_i}
    if av3:
        crit_v = {n: "%s(%d金)" % (nm(n), ucost(n)) for n in av3}
        crit_v["hold"] = "不造载具"
        Q["veh"] = {"type": "choice",
                    "instructions": ("选一种载具生产。犀牛=绝对主力(900金,5炮杀犀牛/4炮杀灰熊); "
                                     "恐怖机器人=刺客专咬矿车/载具(400金,别啃建筑); "
                                     "防空履带车=唯一移动防空+反步兵(500金); "
                                     "天启=肉盾自带对空(贵且慢); V3只拆家打单位无效; "
                                     "磁能坦克射程短怕风筝。按战略和敌构成选。"),
                    "criteria": crit_v}
    Q["stance"] = {"type": "choice",
                   "instructions": ("五态态势机裁决(当前执行态势:%s)。"
                                    "DEVELOP=开局~5分钟无敌情,建造探图攒兵; "
                                    "DEFEND=基地受威胁,回防补防空; "
                                    "RUSH=开局8分钟内且坦克≥4-5,直扑敌基地换家; "
                                    "ATTACK=坦克≥8且已侦察到敌目标,集火拆生产建筑(留2守家); "
                                    "RECOVER=主力被歼,收缩抢经济。"
                                    "注意: 开局8分钟内除非主力全灭否则不要选recover; "
                                    "近期受袭次数高(≥3次/2分钟)说明AI正在施压,应选DEFEND而非develop。"
                                    % stance),
                   "criteria": {"develop": "发展攒兵探图", "defend": "回防基地",
                                "rush": "早期换家快攻", "attack": "军团总攻",
                                "recover": "收缩重建"}}
    Q["threat"] = {"type": "noul",
                   "instructions": ("根据视野内敌方单位数量/兵种/与基地坐标的距离,"
                                    "判断基地当前是否正遭受实际威胁"
                                    "(敌人即将打到或正在打基地建筑)。远处路过的散兵不算。")}
    return state, Q
