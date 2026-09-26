# -*- coding: utf-8 -*-
"""定向提取: 关键武器的弹头倍率、超武、矿石/经济参数、未展开的关键 section。"""
import re, os, io, collections, sys

D = __file__.rsplit("\\", 1)[0]
ini = io.open(os.path.join(D, "rules.ini"), "r", encoding="utf-8", errors="ignore").read()
sec, cur = collections.OrderedDict(), None
for line in ini.splitlines():
    line = line.strip()
    m = re.match(r"^\[(.+?)\]$", line)
    if m:
        cur = m.group(1); sec[cur] = {}; continue
    if cur and line and not line.startswith(";") and "=" in line:
        k, v = line.split("=", 1)
        sec[cur][k.strip()] = v.split(";")[0].strip()

out = []
def full(name):
    s = sec.get(name)
    if not s:
        out.append("### %s NOT FOUND" % name); return
    out.append("### %s" % name)
    for k, v in s.items():
        if k in ("Image", "Cameo", "CrushSound", "Voice", "MoveSound", "DieSound",
                 "CreateSound", "Report", "Occupier", "PipScale", "AltCameo",
                 "WaterEquivalent", "Spawned", "Turret", "DeploySound", "UndeploySound"):
            continue
        out.append("  %s=%s" % (k, v))

out.append("# 武器/弹头/超武/经济 定向提取")
for w in ["120mm", "120mmE", "120mmx", "105mm", "M60", "M60E", "M1Carbine", "M1CarbineE",
          "FlakGuyGun", "FlakGuyAAGun", "ElectricBolt", "AssaultBolt", "DroneJump",
          "PrismShot", "HoverMissile", "MirageGun", "GrandCannonWeapon", "FlakWeapon",
          "Vulcan", "Vulcan2", "RedEye2", "BlimpBomb", "V3Launcher", "SubTorpedo",
          "20mm", "20mmRapid", "RadBeamWeapon", "RadEruptionWeapon", "GuardianPara",
          "GuardianMissile", "DoublePistols", "AWP", "IvanBomber", "NeutronRifle",
          "Sapper", "AegisWeapon", "Medusa", "HornetLauncher", "DredLauncher", "SquidGrab",
          "SquidPunch", "SonicZap", "155mm", "ASWLauncher", "MammothTusk", "TankBolt",
          "CoilBolt", "OPCoilBolt", "GoodTeeth", "Maverick", "BlackHawkCannon"]:
    full(w)

for wh in ["AP", "GRIZAPE", "SmallArms", "Flak", "HE", "SABOT", "Parasite", "RadBeam",
           "RadEruption", "Pistol", "Sniper", "Fire", "Super", "Nuke", "IvanBomb",
           "Laser", "Prism", "Tesla", "Mech", "HollowPoint", "ArmorPiercing"]:
    if wh in sec:
        out.append("- **%s** Verses=%s" % (wh, sec[wh].get("Verses", "?")))
        for k in ("Wall", "Wood", "CellSpread", "PercentAtMax", "InfDeath", "ProneDamage"):
            if k in sec[wh]:
                out.append("    %s=%s" % (k, sec[wh][k]))

out.append("\n# 超武与特殊")
for s in list(sec.keys()):
    low = s.lower()
    if any(t in low for t in ("special", "super", "nuke", "ironcurtain", "chrono", "weather",
                              "iron", "sw.")) and len(s) < 40:
        d = sec[s]
        keys = [k for k in d if re.search(r"Recharge|Cost|Damage|Range|Duration|Type|Time|Radius|Verses|Warhead|Action", k, re.I)]
        if keys:
            out.append("- **%s** | %s" % (s, "; ".join("%s=%s" % (k, d[k]) for k in keys)))

out.append("\n# 矿石/经济相关")
for s in list(sec.keys()):
    if re.search(r"ore|gem|gold|harvest|refin|purif|bail|storage|money|credit", s, re.I) and len(sec[s]) > 2:
        d = sec[s]
        keys = [k for k in d if re.search(r"Value|Bail|Storage|Harvest|Purif|Growth|Amount|Rate|Steps|Tiberium|Ore|Gem", k, re.I)]
        if keys:
            out.append("- **%s** | %s" % (s, "; ".join("%s=%s" % (k, d[k]) for k in keys)))
g = sec.get("General", {})
for k, v in g.items():
    if re.search(r"ore|gem|gold|bail|harvest|purif|credit|money|refin", k, re.I):
        out.append("- [General] %s=%s" % (k, v))

out.append("\n# 剩余未提取的关键 section (SREF/MGTK/防御/步兵武器等)")
for s in ["SREF", "MGTK", "NAPOWR", "GAPOWR", "NANRCT", "GAAIRC", "GAOREP", "GAPILL",
          "NALASR", "NAFLAK", "TESLA", "GTGCAN", "NASAM", "GAWEAP", "NAWEAP", "GADEPT", "NADEPT"]:
    d = sec.get(s)
    if d:
        out.append("- **%s**: %s" % (s, "; ".join("%s=%s" % (k, d[k]) for k in d if k not in ("Image", "Cameo", "Report", "Voice", "Sound"))))

io.open(os.path.join(D, "rules_extract2.md"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out[:120]))
print("...")
print("total chars", len("\n".join(out)))
