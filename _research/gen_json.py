# -*- coding: utf-8 -*-
"""从 rules.ini + csf 中文名生成机器可读的关键单位数据 RA2-UNITS.json。"""
import re, os, io, json, collections

D = __file__.rsplit("\\", 1)[0]
OUTDIR = os.path.dirname(D)  # gonghui-bot/
ini = io.open(os.path.join(D, "rules.ini"), "r", encoding="utf-8", errors="ignore").read()

sec, cur = collections.OrderedDict(), None
for line in ini.splitlines():
    line = line.strip()
    m = re.match(r"^\[(.+?)\]$", line)
    if m:
        cur = m.group(1); sec[cur] = {}; continue
    if cur and len(line) > 2 and not line.startswith(";") and "=" in line:
        k, v = line.split("=", 1)
        sec[cur][k.strip()] = v.split(";")[0].strip()

# 中文名
names = {}
try:
    raw = json.load(io.open(os.path.join(D, "csf_decoded.json"), encoding="utf-8"))
    if isinstance(raw, dict):
        for k, v in raw.items():
            names[k] = v
except Exception as e:
    print("csf load warn:", e)

ARMOR = ["none", "flak", "plate", "light", "medium", "heavy", "wood", "steel", "concrete", "special_1", "special_2"]

def weapon(code):
    s = sec.get(code)
    if not s:
        return None
    w = {"code": code}
    for f, t in (("Damage", "damage"), ("ROF", "rof"), ("Range", "range"), ("Burst", "burst")):
        if f in s:
            try:
                w[t] = float(s[f]) if "." in s[f] else int(s[f])
            except ValueError:
                w[t] = s[f]
    wh = s.get("Warhead")
    if wh:
        w["warhead"] = wh
        vs = sec.get(wh, {}).get("Verses")
        if vs:
            vals = [x.strip() for x in vs.replace(",", " ").split()]
            if len(vals) == len(ARMOR):
                w["verses"] = dict(zip(ARMOR, vals))
    return w

def entry(code):
    s = sec.get(code)
    if not s:
        return None
    e = {"code": code, "name": s.get("Name", "")}
    ui = s.get("UIName", "")
    key = ui.split(":", 1)[-1] if ":" in ui else ui
    e["cn"] = names.get("NAME:" + key) or names.get(key) or ""
    for f, t in (("Cost", "cost"), ("Strength", "hp"), ("Armor", "armor"), ("Speed", "speed"),
                 ("ROT", "rot"), ("Sight", "sight"), ("Power", "power"), ("Storage", "storage"),
                 ("TechLevel", "tech"), ("Prerequisite", "prereq"), ("Owner", "owner"),
                 ("BuildLimit", "build_limit")):
        if f in s:
            try:
                e[t] = int(s[f])
            except ValueError:
                e[t] = s[f]
    for f, t in (("Primary", "primary"), ("Secondary", "secondary"),
                 ("ElitePrimary", "elite_primary"), ("EliteSecondary", "elite_secondary"),
                 ("Weapon1", "primary"), ("EliteWeapon1", "elite_primary")):
        if f in s and t not in e:
            w = weapon(s[f])
            if w:
                e[t] = w
    flags = [f for f in ("Deployer", "Crusher", "SelfHealing", "DisguiseWhenStill", "Harvester",
                         "ImmuneToPsionics", "C4", "Occupier", "Powered", "Overpowerable",
                         "WeaponsFactory", "UnitRepair", "Radar", "Helipad", "OrePurifier",
                         "IsBaseDefense", "Turret", "Explodes")
             if s.get(f, "").lower() == "yes"]
    if flags:
        e["flags"] = flags
    return e

GROUPS = {
    "soviet_infantry": ["E2", "SHK", "FLAKT", "IVAN", "DESO", "ADOG", "SENGINEER", "YURI", "SPY"],
    "soviet_vehicles": ["HTNK", "APOC", "TTNK", "DRON", "V3", "HTK", "HARV", "SMCV", "ZEP", "LTNK"],
    "soviet_navy": ["SUB", "DRED", "HYD", "SQD"],
    "allied_infantry": ["E1", "JUMPJET", "GGI", "SNIPE", "TANY", "CLEG", "PTROOP"],
    "allied_vehicles": ["MTNK", "FV", "MGTK", "SREF", "CMIN", "AMCV", "SHAD", "ORCA"],
    "allied_navy": ["DEST", "AEGIS", "CARRIER", "DLPH", "LCRF"],
    "soviet_buildings": ["NACNST", "NAPOWR", "NAREFN", "NAHAND", "NAWEAP", "NARADR", "NATECH",
                         "NADEPT", "NAYARD", "NANRCT", "NAMISL", "NAIRON", "NAPSIS"],
    "soviet_defense": ["TESLA", "NAFLAK", "NALASR", "NAWALL"],
    "allied_buildings": ["GACNST", "GAPOWR", "GAREFN", "GAPILE", "GAWEAP", "GAAIRC", "GATECH",
                         "GAYARD", "GADEPT", "GASPYSAT", "GACSPH", "GAWEAT", "GAOREP"],
    "allied_defense": ["GAPILL", "NASAM", "GTGCAN"],
}

data = {"meta": {
    "game": "王二火大网页红警2 (mod id=gonghui)",
    "source": "client rules.ini @ game.gongheguozhihui.com/res/overlay/rules.ini, fetched 2026-09-20",
    "armor_classes": ARMOR,
    "notes": "verses 为弹头对 11 种护甲的伤害倍率, 顺序同 armor_classes; 伤害=damage*burst*倍率",
}, "groups": {}, "buildings": {}, "warheads": {}}

for g, codes in GROUPS.items():
    data["groups"][g] = {}
    for c in codes:
        e = entry(c)
        if e and e.get("cost") is not None:
            data["groups"][g][c] = e

for wh in ["AP", "GRIZAPE", "RHINAPE", "ApocAP", "CometWH", "SuperComet", "MirageWH", "SA", "SSA",
           "RPG", "HE", "FlakWH", "FlakTWH", "FlakGuyWH", "Electric", "Shock", "Parasite", "V3HE",
           "BlimpHE", "RadBeamWarhead", "HollowPoint", "HollowPoint2", "SAMWH", "GrandCannonWH",
           "ORCAAP", "SonicWarhead", "APSplash", "ARTYHE"]:
    vs = sec.get(wh, {}).get("Verses")
    if vs:
        vals = [x.strip() for x in vs.replace(",", " ").split()]
        if len(vals) == len(ARMOR):
            data["warheads"][wh] = dict(zip(ARMOR, vals))

g = sec.get("General", {})
data["general"] = {k: g[k] for k in ("BuildSpeed", "MultipleFactory", "RefundPercent", "RepairPercent",
                                     "HarvestersPerRefinery", "PurifierBonus", "SpyMoneyStealPercent",
                                     "VeteranArmor", "VeteranCombat", "VeteranROF", "VeteranSight",
                                     "VeteranSpeed", "VeteranRatio", "VeteranCap", "CrewEscape",
                                     "MaxLowPowerProductionSpeed", "MinLowPowerProductionSpeed")
                   if k in g}

p = os.path.join(OUTDIR, "RA2-UNITS.json")
io.open(p, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
print("written", p)
print("groups:", {k: len(v) for k, v in data["groups"].items()})
print("warheads:", len(data["warheads"]))
print("sample:", json.dumps(data["groups"]["soviet_vehicles"].get("HTNK"), ensure_ascii=False))
print("sample2:", json.dumps(data["groups"]["soviet_defense"].get("NAFLAK"), ensure_ascii=False))
