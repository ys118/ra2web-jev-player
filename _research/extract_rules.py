# -*- coding: utf-8 -*-
"""解析 rules.ini -> 输出单位/建筑/武器/护甲的关键数值表 (markdown)。"""
import re, os, io, json, collections

D = __file__.rsplit("\\", 1)[0]
ini = io.open(os.path.join(D, "rules.ini"), "r", encoding="utf-8", errors="ignore").read()

sec = collections.OrderedDict()
cur = None
for line in ini.splitlines():
    line = line.strip()
    m = re.match(r"^\[(.+?)\]$", line)
    if m:
        cur = m.group(1)
        sec[cur] = {}
        continue
    if not cur or not line or line.startswith(";"):
        continue
    if "=" in line:
        k, v = line.split("=", 1)
        sec[cur][k.strip()] = v.split(";")[0].strip()

U = ["Name", "UIName", "Cost", "Strength", "Armor", "Speed", "ROT", "Sight",
     "Primary", "Secondary", "ElitePrimary", "EliteSecondary", "Prerequisite",
     "Power", "Storage", "Harvester", "TechLevel", "Owner", "Deployer", "Crewed",
     "BuildLimit", "Powered", "ImmuneToPsionics", "Selectable", "Turret", "Image"]

out = []
def dump(keys, title):
    out.append("## " + title)
    for k in keys:
        s = sec.get(k)
        if not s:
            out.append("- %s: **NOT FOUND**" % k)
            continue
        row = [x for x in U if x in s and s[x] not in ("", "no", "0")]
        out.append("- **%s** | %s" % (k, "; ".join("%s=%s" % (f, s[f]) for f in row)))
    out.append("")

# ---------- 步兵 ----------
INF = ["E1", "E2", "SHK", "FLAKT", "ADOG", "IVAN", "DESO", "BORIS", "SEAL", "TANY",
       "SNIPE", "GGI", "CLEG", "SPY", "JUMPJET", "PTROOP", "VIRUS", "YURI", "BRUTE", "INIT"]
# ---------- 载具 ----------
VEH = ["MTNK", "HTNK", "LTNK", "TTNK", "APOC", "FV", "MGTK", "SREF", "DRON", "V3", "HTK",
       "FTRK", "HARV", "CMIN", "AMCV", "SMCV", "PCV", "ZEP", "SHAD", "BPLN", "ORCA", "TELE"]
# ---------- 海军 ----------
NAVY = ["DEST", "AEGIS", "CARRIER", "DLPH", "LCRF", "SUB", "DRED", "HYD", "SQD", "SECA"]
# ---------- 苏军建筑 ----------
NB = ["NACNST", "NAPOWR", "NANRCT", "NAREFN", "NAHAND", "NAWEAP", "NAIRP", "NARADR",
      "NATECH", "NAYARD", "NAMISL", "NATSLM", "TESLA", "NAFLAK", "NALASR", "NAWALL",
      "NADEPT", "NASAM", "NAPSIS", "NAWEAP2", "NABNKR", "NAHOSP"]
# ---------- 盟军建筑 ----------
GB = ["GACNST", "GAPOWR", "GAREFN", "GAPILE", "GAWEAP", "GAAIRC", "GARADR", "GATECH",
      "GAYARD", "GADEPT", "GAPILL", "GASAM", "GAFWLL", "GAPRIS", "GTGCAN", "GASPYSAT",
      "GACSPH", "GAWEAT", "GAGATE", "GATSLM", "GAPOST", "GAOREP"]
# ---------- 中国(共辉) ----------
CN = ["CAREFN", "CAPOWR", "CAHAND", "CAWEAP", "CATECH", "CANCNST", "CAWALL", "CATESLA", "CAPILE"]

dump(INF, "步兵")
dump(VEH, "载具")
dump(NAVY, "海军")
dump(NB, "苏军建筑")
dump(GB, "盟军建筑")
dump(CN, "中国建筑")

# 全局参数
out.append("## [General] 关键参数")
g = sec.get("General", {})
for k in sorted(g):
    if re.search(r"Build|Ore|Gem|Harvest|Refund|Multi|Speed|Repair|Sell|Veteran|Crew|Bounty|Power", k, re.I):
        out.append("- %s = %s" % (k, g[k]))
out.append("")

# 武器表: 对所有出现的 Primary/Secondary 引用
weapons = set()
for name, s in sec.items():
    for f in ("Primary", "Secondary", "ElitePrimary", "EliteSecondary"):
        v = s.get(f)
        if v and v in sec:
            weapons.add(v)
out.append("## 武器")
for w in sorted(weapons):
    s = sec[w]
    row = [x for x in ("Damage", "ROF", "Range", "Warhead", "Burst", "Projectile",
                       "Speed", "MinimumRange", "Report", "CellRangefinding") if x in s]
    out.append("- **%s** | %s" % (w, "; ".join("%s=%s" % (f, s[f]) for f in row)))
out.append("")

# 弹头 Verses 矩阵
warheads = set()
for w in weapons:
    v = sec[w].get("Warhead")
    if v and v in sec:
        warheads.add(v)
out.append("## 弹头 Verses (护甲倍率)")
out.append("顺序: none, flak, plate, light, medium, heavy, wood, steel, concrete, special_1, special_2")
for wh in sorted(warheads):
    v = sec[wh].get("Verses")
    if v:
        out.append("- **%s** | %s" % (wh, v))
out.append("")

io.open(os.path.join(D, "rules_extract.md"), "w", encoding="utf-8").write("\n".join(out))
print("sections:", len(sec), "weapons:", len(weapons), "warheads:", len(warheads))
print("chars:", len("\n".join(out)))
