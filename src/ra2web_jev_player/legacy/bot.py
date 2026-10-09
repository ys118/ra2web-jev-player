# -*- coding: utf-8 -*-
"""王二火大 (Chrono Divide) jev automated match driver v2 -- strategy-guide driven
Knowledge sources: RA2-BIBLE.md / AI-OPERATING-CARD.md / RA2-UNITS.json (rules.ini ground truth)
loop: eval pulls state -> deterministic rules (tactics checklist §10.1) -> jev semantic decisions ->
execute raw werhd orders
History: the main loop for games 1-20 (originally legacy-bot/bot.py), kept for comparison after the
official system went live, see docs/SESSION-REPORT.md
Run: uv run python -m ra2web_jev_player.legacy.bot
"""
import json, subprocess, time, sys, os, base64, math

from ..paths import LOG_DIR, KNOWLEDGE_DIR

WS = str(LOG_DIR)
TSJ = os.environ.get("TSJ_SCRIPT", "")      # external judge CLI (required for this legacy path)
AB = [os.environ.get("AGENT_BROWSER_CMD") or "agent-browser", "--session", "gonghui"]
_LOG_FH = None


def _logfile():
    """Lazily open bot.log (the original implementation opened the file at import time, so a missing
    directory broke even the import)."""
    global _LOG_FH
    if _LOG_FH is None:
        os.makedirs(WS, exist_ok=True)
        _LOG_FH = open(os.path.join(WS, "bot.log"), "a", buffering=1, encoding="utf-8")
    return _LOG_FH


def log(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    _logfile().write(line + "\n")
    print(line, flush=True)

def js(code, timeout=25):
    # .cmd shim 走 cmd.exe, 多行/复杂引号 argv 会被切碎 -> base64 单行传输
    # Popen+taskkill /T /F: subprocess.run 超时后孙进程持管道会永久卡死, 必须连树强杀
    b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    argv = AB + ["eval", "eval(atob('%s'))" % b64]
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, errb = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                       capture_output=True, timeout=10)
        raise RuntimeError("eval hang (killed tree)")
    err = (errb or b"").decode("utf-8", "replace")
    s = (out or b"").decode("utf-8", "replace").strip()
    if not s or s == "null":
        raise RuntimeError("eval empty: " + err[:200])
    if s.startswith('"'):
        s = json.loads(s)
    return s

def exec_js(code):
    return js("JSON.stringify((()=>{%s})())" % code)

def tsj(state, questions, timeout=40):
    req = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
    # 标注来源：本循环一天几千次会把账本淹没，需与 agent 判断区分开
    env = dict(os.environ, TSJ_SOURCE="bot")
    p = subprocess.Popen(["python", TSJ], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        out, errb = p.communicate(input=req.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                       capture_output=True, timeout=10)
        raise RuntimeError("tsj hang (killed tree)")
    if p.returncode != 0:
        raise RuntimeError("tsj fail: " + (errb or b"").decode("utf-8", "replace")[:300])
    return json.loads(out.decode("utf-8", "replace"))["answers"]

# ================= 知识库: RA2-UNITS.json =================
try:
    _UDB_RAW = json.load(open(os.path.join(KNOWLEDGE_DIR, "RA2-UNITS.json"), encoding="utf-8"))
except Exception as e:
    log("UNITS.json load fail: %s" % e); _UDB_RAW = {"groups": {}}
UDB = {}
for _g, _members in _UDB_RAW.get("groups", {}).items():
    for _c, _u in _members.items():
        UDB[_c] = {"cn": _u.get("cn") or _u.get("name") or _c,
                   "cost": _u.get("cost", 0), "hp": _u.get("hp", 0),
                   "armor": (_u.get("armor") or "").lower(),
                   "group": _g}
WH = _UDB_RAW.get("warheads", {})

def nm(code):
    u = UDB.get(code)
    return ("%s" % u["cn"]) if u else code

def ucost(code):
    u = UDB.get(code)
    return u["cost"] if u else 0

# 护甲克制速查: 敌方护甲 -> 我方克制手段(名称+说明), 来自 Bible §1.6/§2
COUNTERS = {
    "none":     [("NALASR", "哨戒炮(100%)"), ("E2", "动员兵海(100%)"), ("HTK", "防空车对地(150%)"), ("DESO", "辐射工兵(100%)")],
    "flak":     [("E2", "动员兵海(80%)"), ("HTK", "防空车对地(150%无甲)"), ("NALASR", "哨戒炮(80%)"), ("DESO", "辐射工兵(100%)")],
    "plate":    [("SHK", "磁爆步兵(100%)"), ("E2", "动员兵(70%)"), ("NALASR", "哨戒炮(70%)")],
    "light":    [("HTK", "防空车(对空100%/对地60%)"), ("NAFLAK", "防空炮(只对空100%)"), ("SHK", "磁爆步兵(85%)"), ("TTNK", "磁能坦克(85%)")],
    "medium":   [("HTNK", "犀牛(100%)"), ("DRON", "恐怖机器人(专咬载具)"), ("TTNK", "磁能坦克(100%)")],
    "heavy":    [("HTNK", "犀牛(100%,5炮杀犀牛)"), ("TESLA", "磁暴线圈(100%,2炮)"), ("SHK", "磁爆步兵(100%)"), ("APOC", "天启(100%×2)")],
    "special_2":[("NAFLAK", "防空炮(150%,射程12)"), ("HTK", "防空车(150%,射程10)"), ("FLAKT", "防空步兵(100%)")],
    "special_1":[("E2", "动员兵枪(100%)"), ("NALASR", "哨戒炮(100%)")],  # 蜘蛛: 只怕机枪
    "concrete": [("HTNK", "犀牛(60%)"), ("APOC", "天启(70%)"), ("V3", "V3火箭(30%)")],
    "wood":     [("HTNK", "犀牛(65%)"), ("APOC", "天启(100%)")],
    "steel":    [("APOC", "天启(100%)"), ("V3", "V3火箭(50%)")],
}
AIR_UNITS = {"JUMPJET", "ZEP", "SHAD", "ORCA", "HORNOR"}
# 进攻目标优先级分 (Bible §4.3): 矿车 > 工兵 > 防空/反坦克防御 > 生产建筑 > 兵营 > 精炼厂 > 电厂 > 建造厂(最后)
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

# ================= 兵法阈值 (Bible §10.2) =================
T = dict(harv_per_ref=2, harv_min=2, ref_cap=2, factory2_cash=4500,
         tank_cash1=1200, tank_cash2=1600, power_reserve=30, cash_idle=2000,
         rush_t0=240, rush_t1=480, rush_tanks=5, attack_tanks=8, keep_home=2,
         retreat_hp=0.40, defend_radius=18)

# ================= jev 上下文: 作战手册 (AI-OPERATING-CARD 蒸馏) =================
DOCTRINE = """[作战手册·苏军]
铁律: 生存>经济>产能>兵力>进攻; 现金>2000必须转化(矿车/工厂/坦克/防御); 没侦察到敌基地不总攻; 防空必须有(哨戒炮/线圈不能打飞机); 电力余量<30先补电厂(缺电=生产减半+防御塔哑火).
克制常识: 坦克炮对步兵仅25%(别用坦克清步兵堆,用哨戒炮/动员兵/防空车/辐射); 坦克对坦克满伤(犀牛5炮杀犀牛/4炮杀灰熊); 光棱拆家不拆坦克(对建筑200%/对重甲50%), 幻影反坦克不拆家; 恐怖机器人专咬载具(秒矿车); 飞行兵怕防空炮(150%倍率,3发击落).
进攻目标优先级: 1矿车(断经济) 2工兵 3防空/反坦克塔 4战车工厂>兵营>精炼厂>电厂 5建造厂(最后拆). 例外: 己方基地被空军偷袭→一切让位回防+补防空.
五态态势: DEVELOP(开局~5分钟无敌情,建造+探图+攒兵) DEFEND(基地受威胁,回防补防空修塔) RUSH(开局8分钟内且坦克≥4-5,直扑敌基地/矿区换家) ATTACK(坦克≥8,集火拆生产建筑/矿车,留2守家) RECOVER(主力被歼,收缩抢经济).
进攻纪律: 兵力≥8才总攻(早期rush例外≥4-5); ≥6辆留2守家; 主力70%+佯动30%; 残血(<40%)撤后保老兵.
防御三件套: 哨戒炮(反步兵,不耗电)+防空炮(对空,射程12)+磁暴线圈(反坦克200伤,需雷达和电力). 路口前置优于贴家环形.
时间窗: 3-5分钟首批坦克; 8分钟8坦克成军; 10分钟后AI波次变强→10分钟前必须换家/断经济/抢中."""

# ================= 状态采集 =================
STATE_JS = r"""
JSON.stringify((()=>{const w=werhd;
 const me=w.me();
 const msize=(()=>{try{const s=w.map.size();return [s.width||s.w||s, s.height||s.h||0]}catch(e){return [200,200]}})();
 const mine=w.units('self').map(u=>({id:u.id,n:u.name,o:u.type,tl:[u.tile.rx,u.tile.ry],hp:u.hitPoints,mhp:u.maxHitPoints,idle:!!u.isIdle,dep:!!u.canDeploy}));
 const hos=w.units('hostile').filter(u=>u.owner&&u.owner.indexOf('@@AI')===0).map(u=>({id:u.id,n:u.name,o:u.type,tl:[u.tile.rx,u.tile.ry],hp:u.hitPoints,mhp:u.maxHitPoints}));
 const q=w.production.queues();
 const av={}; for(const t of [0,1,2,3]){ try{ av[t]=(w.production.available(t)||[]).map(x=>typeof x==='string'?x:(x.name||'')) }catch(e){ av[t]=[] } }
 return {t:Math.round(w.time()),map:msize,
  me:{credits:me.credits,power:me.power,defeated:me.defeated,low:!!me.radarDisabled,country:(me.country||'')},
  players:w.players().map(p=>({n:p.name,ai:!!p.isAi,def:!!p.defeated,ally:!!p.allied,country:p.country||''})),
  mine,hostile:hos,
  queues:q.map(x=>({t:x.t??x.type,s:x.s??x.status,items:(x.items||[]).map(i=>({n:i.name,p:Math.round((i.progress||0)*100),qty:i.quantity||1,each:i.creditsEach||0}))})),
  av};
})())
"""

def get_state():
    s = json.loads(js(STATE_JS))
    if not s:
        raise RuntimeError("battle-ended")
    return s

def page_finished():
    try:
        t = js("document.body.innerText.slice(0,600)")
        return ("失败！" in t) or ("胜利" in t)
    except Exception:
        return False

# ================= 执行原语 =================
_last_deploy = [0.0]

def deploy_all():
    # 仅载具形态(type=7); deploy异步生效, 45s节流(重发=车厂横跳)
    if time.time() - _last_deploy[0] < 45:
        return []
    r = exec_js("const d=werhd.units('self').filter(u=>u.canDeploy&&u.type===7).map(u=>u.id); if(d.length) werhd.deploy(d); return d")
    d = json.loads(r)
    if d:
        _last_deploy[0] = time.time()
    return d

def place_ready(qtype):
    """Queue ready -> spiral around the base to find a placement tile (faction-agnostic: accepts both
    NACNST and GACNST)"""
    code = r"""
const w=werhd; const q=w.production.queues().find(x=>(x.t??x.type)===%d);
if(!q||(q.s??q.status)!==3) return null;
const name=q.items[0].name; const yard=w.units('self').find(u=>u.type===2&&(u.name==='NACNST'||u.name==='GACNST'));
if(!yard) return null; const {rx,ry}=yard.tile;
for(let r=2;r<=14;r++){for(let dx=-r;dx<=r;dx++){for(let dy=-r;dy<=r;dy++){
 if(Math.max(Math.abs(dx),Math.abs(dy))!==r) continue;
 const x=rx+dx,y=ry+dy;
 try{ if(w.canPlace(name,x,y)){ w.place(name,x,y); return {name:name,at:[x,y]} } }catch(e){}
}}}
return {name:name,at:null}
""" % qtype
    return json.loads(exec_js(code))

def produce(name, qty=1):
    return json.loads(exec_js("werhd.produce(%s,%d); return 'ok'" % (json.dumps(name), qty)))

def raw_order(ids, otype, x, y):
    """Raw order primitive; <=5 per batch; the wrapped move/attackMove is broken in this game version"""
    for i in range(0, len(ids), 5):
        exec_js("werhd.order(%s, %d, %d, %d); return 'ok'" % (json.dumps(ids[i:i + 5]), otype, x, y))

def yard_tile(state):
    for u in state["mine"]:
        if u["o"] == 2 and u["n"] in ("NACNST", "GACNST"):
            return u["tl"]
    return None

# ================= 阵营自适应 (随机阵营可能 roll 到盟军) =================
SOVIET_COUNTRIES = {"Russians", "Confederation", "Africans", "Arabs"}

def get_side(s):
    """Return the faction code table from me().country; when country is missing, fall back to inferring it
    from the buildings/buildable list"""
    country = (s.get("me", {}).get("country") or "")
    if not country:
        probe = " ".join([u.get("n", "") for u in (s.get("mine") or [])] +
                         [(x if isinstance(x, str) else "") for k, v in (s.get("av") or {}).items() for x in v])
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

# ================= 态势记忆 (进程内) =================
MEM = {"enemy_base": None, "last_scout": 0.0, "scout_sent": False,
       "retreated": {}, "last_repair": 0.0, "dogs_queued": False,
       "last_move_tgt": None, "last_move_at": 0.0,
       "events": [], "bld_hp": {}, "unit_ids": {}, "alarm_times": [],
       "alarm": None, "last_defend_order": 0.0}

# ================= 确定性兵法层 (Bible §10.1 清单) =================
def checklist(s, home, stance):
    """Execute deterministic actions in §10.1 priority order; returns an overriding stance or None"""
    side = get_side(s)
    cred = s["me"]["credits"]
    pw, drain = s["me"]["power"].get("total", 0), s["me"]["power"].get("drain", 0)
    mine, hos = s["mine"], s["hostile"]
    qs = {q["t"]: q for q in s["queues"]}
    av = {int(k): v for k, v in (s["av"] or {}).items()}
    bl = {}
    for u in mine:
        if u["o"] == 2:
            bl[u["n"]] = bl.get(u["n"], 0) + 1
    acts = []
    # 1) 基地受袭检测 (确定性, 不等jev): 敌人出现在基地半径内
    if home:
        near = [h for h in hos if home and math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= T["defend_radius"]]
        if near and stance != "defend":
            log("t=%d DEFEND trigger: %d hostiles within r=%d" % (s["t"], len(near), T["defend_radius"]))
            stance = "defend"
    # 2) 就绪建筑放置
    for qt in (0, 1):
        try:
            r = place_ready(qt)
            if r:
                acts.append("PLACE %s" % r)
        except Exception as e:
            acts.append("placeERR %s" % str(e)[:40])
    # 3) 部署基地车
    dep = deploy_all()
    if dep:
        acts.append("DEPLOY mcv")
    # 4) 电力保底 (余量<30 → 电厂; 排在大多数建造之前)
    if pw - drain < T["power_reserve"] and cred >= 600 and side["powr"] in av.get(0, []) \
            and qs.get(0, {}).get("s") == 0:
        produce(side["powr"]); acts.append("POWER plant (reserve %d)" % (pw - drain))
        cred -= 600
    # 5) 矿车补员: 每精炼厂2车, 下限2
    n_harv = len([u for u in mine if u["n"] in HARVEST])
    n_ref = bl.get(side["ref"], 0)
    q3s = qs.get(3, {}).get("s", 0)
    harv_target = min(3, T["harv_per_ref"] * n_ref)
    harv_cost_gate = 1400 if n_harv < T["harv_min"] else 2800
    if q3s == 0 and n_ref >= 1 and n_harv < harv_target \
            and side["harv"] in av.get(3, []) and cred >= harv_cost_gate:
        produce(side["harv"], 1); acts.append("ECON harv#%d" % (n_harv + 1))
        cred -= 1400
    # 8) 不攒钱: 产能线
    n_tank = len([u for u in mine if u["o"] == 7 and u["n"] not in HARVEST and u["n"] not in MCV_CODES])
    if q3s == 0 and bl.get(side["weap"], 0) >= 1:
        tanks_av = [x for x in av.get(3, []) if x not in HARVEST and x not in MCV_CODES]
        if tanks_av and cred >= T["tank_cash1"]:
            prefer = [x for x in side["tank_pref"] if x in tanks_av]
            pick = prefer[0] if prefer else tanks_av[0]
            qty = 2 if cred >= T["tank_cash2"] else 1
            if cred >= 2600:
                qty = min(4, int(cred // 900))
            produce(pick, qty)
            acts.append("TANK %s x%d" % (pick, qty))
            cred -= ucost(pick) * qty
    # 6) 防空保险: 有战车工厂即保证≥1防空建筑; 有空军威胁且资金富余再+1
    air = any(h["n"] in AIR_UNITS for h in hos)
    if side["weap"] in bl and bl.get(side["aa_b"], 0) < 1 and qs.get(1, {}).get("s", 0) == 0 \
            and side["aa_b"] in av.get(1, []) and cred >= 1000:
        produce(side["aa_b"], 1); acts.append("INSURE AA building")
        cred -= 1000
    elif air and bl.get(side["aa_b"], 0) < 2 and qs.get(1, {}).get("s", 0) == 0 \
            and side["aa_b"] in av.get(1, []) and cred >= 1400:
        produce(side["aa_b"], 1); acts.append("AIR-DEFENSE 2nd AA")
        cred -= 1000
    # 6.5) 地面防御线: 有兵营即把哨戒炮补到4座 (反步兵,不耗电; Bible防御三件套)
    if side["bar"] in bl and bl.get(side["gdef"], 0) < 3 and qs.get(1, {}).get("s", 0) == 0             and side["gdef"] in av.get(1, []) and cred >= 1500:
        produce(side["gdef"], 1); acts.append("DEFLINE %s (have %d)" % (side["gdef"], bl.get(side["gdef"], 0)))
        cred -= 500
    # 7) 空军来袭 → 移动防空车 (苏军HTK; 盟军靠防空建筑)
    q3 = qs.get(3, {})
    if air and side["aa_v"] and bl.get(side["weap"], 0) >= 1 and q3.get("s", 0) == 0 \
            and side["aa_v"] in av.get(3, []) and cred >= 500:
        produce(side["aa_v"], 2); acts.append("AA %s x2 (enemy air)" % side["aa_v"])
        cred -= ucost(side["aa_v"]) * 2
    # 9) 不攒钱: 第二工厂 (由外层 opening 逻辑用 side 代码处理, 此处跳过)
    # 10) 维修: 关键建筑 hp<70% 且钱>1000 (30s节流)
    dmg = [u for u in mine if u["o"] == 2 and u["hp"] < 0.7 * u["mhp"]]
    if dmg and cred > 1000 and time.time() - MEM["last_repair"] > 30:
        worst = min(dmg, key=lambda u: u["hp"] / u["mhp"])
        try:
            exec_js("werhd.repair(%d); return 'ok'" % worst["id"])
            MEM["last_repair"] = time.time()
            acts.append("REPAIR %s(%d%%)" % (worst["n"], int(100 * worst["hp"] / worst["mhp"])))
        except Exception:
            pass
    # 11) 残血撤退: 战斗单位 hp<40% → 拉回基地 (每单位只撤一次, 防 spam)
    if home:
        rets = [u for u in mine if u["o"] in (3, 7) and u["n"] not in HARVEST
                and u["hp"] < T["retreat_hp"] * u["mhp"] and MEM["retreated"].get(u["id"], 0) < s["t"] - 300]
        for u in rets[:4]:
            raw_order([u["id"]], 0, home[0], home[1] + 3)
            MEM["retreated"][u["id"]] = s["t"]
            acts.append("RETREAT %s(%d%%)" % (u["n"], int(100 * u["hp"] / u["mhp"])))
    for a in acts:
        log("t=%d %s" % (s["t"], a))
    return stance

# ================= 侦察与敌基地定位 =================
def sense_events(s, home):
    """Inter-tick diffing: second-granularity perception of battlefield dynamics -> MEM.events / MEM.alarm"""
    ev = MEM["events"]
    alarm = None
    # a) 我方建筑掉血 = 正在被攻击 (最早信号, 比敌人进入半径更早)
    cur_hp = {}
    for u in s["mine"]:
        if u["o"] == 2:
            cur_hp[u["id"]] = (u["n"], u["hp"], u["mhp"], tuple(u["tl"]))
            prev = MEM["bld_hp"].get(u["id"])
            if prev and u["hp"] < prev[1] - 1:
                lost = int(prev[1] - u["hp"])
                ev.append("受击: %s(%s) -%d血 剩%d/%d" % (u["n"], nm(u["n"]), lost, int(u["hp"]), int(u["mhp"])))
                alarm = {"pos": u["tl"], "what": "%s被攻击" % nm(u["n"])}
    MEM["bld_hp"] = cur_hp
    # b) 战斗单位损失
    alive = set()
    for u in s["mine"]:
        if u["o"] in (3, 7):
            alive.add(u["id"])
    for uid, uname in list(MEM["unit_ids"].items()):
        if uid not in alive:
            ev.append("损失: %s" % uname)
            del MEM["unit_ids"][uid]
            if alarm is None:
                alarm = {"pos": home or [0, 0], "what": "单位损失"}
    for u in s["mine"]:
        if u["o"] in (3, 7) and u["id"] not in MEM["unit_ids"]:
            MEM["unit_ids"][u["id"]] = nm(u["n"])
    # c) 新敌军进入视野 / 敌逼近基地
    if home:
        near = [h for h in s["hostile"]
                if math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) <= T["defend_radius"]]
        if near:
            comp = ",".join("%s x%d" % (nm(h["n"]), 1) for h in near[:4])
            d = min(math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1]) for h in near)
            ev.append("敌逼近基地(%d格): %s" % (int(d), comp))
            MEM.setdefault("alarm_times", []).append(time.time())
            MEM["alarm_times"] = [x for x in MEM["alarm_times"] if time.time() - x < 120][-20:]
            if alarm is None:
                alarm = {"pos": near[0]["tl"], "what": "敌军逼近"}
    new_ids = set(h["id"] for h in s["hostile"])
    fresh = new_ids - MEM.get("seen_hostiles", set())
    if fresh:
        fn = [h for h in s["hostile"] if h["id"] in fresh]
        ev.append("发现敌军: " + ",".join("%s(%s)" % (nm(h["n"]), h["tl"]) for h in fn[:4]))
        MEM["seen_hostiles"] = new_ids
    else:
        MEM.setdefault("seen_hostiles", set()).update(new_ids)
    # 事件流只留最近6条
    MEM["events"] = ev[-6:]
    MEM["alarm"] = alarm
    return alarm

def update_enemy_base(s):
    for h in s["hostile"]:
        if h["o"] == 2:
            if MEM["enemy_base"] is None:
                log("t=%d ENEMY BASE spotted @%s (%s)" % (s["t"], h["tl"], h["n"]))
            MEM["enemy_base"] = h["tl"]  # 持续更新到最新看见的建筑
            return True
    return False

def scouting(s, home):
    """Attack-dog scouting + tank map exploration; records last_scout"""
    side = get_side(s)
    seen = MEM["enemy_base"] is not None
    # 兵营好后第一批: 3军犬 (视野9, 最便宜的情报)
    qs = {q["t"]: q for q in s["queues"]}
    av2 = s["av"].get("2") or []
    if side["bar"] in [u["n"] for u in s["mine"] if u["o"] == 2] \
            and not MEM["dogs_queued"] and "ADOG" in av2 and qs.get(2, {}).get("s", 0) == 0:
        produce("ADOG", 3)
        MEM["dogs_queued"] = True
        log("t=%d SCOUT dogs x3" % s["t"])
        return
    # 每3分钟无新情报 → 派1辆坦克探未知
    if time.time() - MEM["last_scout"] > 180 and not seen:
        tanks = [u for u in s["mine"] if u["o"] == 7 and u["n"] not in HARVEST and u["n"] not in MCV_CODES]
        if tanks and home:
            mx, my = s["map"]
            mirror = [max(mx - home[0], 8), max(my - home[1], 8)]
            raw_order([tanks[0]["id"]], 4, mirror[0], mirror[1])
            MEM["last_scout"] = time.time()
            log("t=%d SCOUT tank->mirror %s" % (s["t"], mirror))

# ================= 进攻执行 =================
def pick_target(s, home):
    """§4.3 target priority scoring: ore miner > defense tower > production building > ...; distance decay"""
    best, bestv = None, -1
    for h in s["hostile"]:
        base = TARGET_SCORE.get(h["n"], 50 if h["o"] != 2 else 45)
        if home:
            d = math.hypot(h["tl"][0] - home[0], h["tl"][1] - home[1])
            base -= d * 0.5
        if base > bestv:
            best, bestv = h, base
    return best

def unit_move_attack(stance, s, home, wp):
    mine, hos = s["mine"], s["hostile"]
    combat = [u for u in mine if u["o"] == 7 and u["n"] not in HARVEST and u["n"] not in MCV_CODES
              and u["hp"] >= T["retreat_hp"] * u["mhp"]]  # 残血不参与进攻
    if stance in ("attack", "rush"):
        if len(combat) >= 6:
            combat = combat[:-T["keep_home"]]  # 留2守家
    ids = [u["id"] for u in combat]
    if not ids:
        return "no-force"
    if stance not in ("attack", "rush"):
        if home:
            # 防守必须用攻击移动; 同样12s节流防指令瘫痪
            tgt_h = (home[0] + 3, home[1] + 3)
            if wp[2] == tgt_h and wp[3] > time.time():
                return "defend-rally (hold)"
            wp[2] = tgt_h; wp[3] = time.time() + 12
            raw_order(ids, 4, tgt_h[0], tgt_h[1])
            return "defend-rally@base(%d)" % len(ids)
        return "no-home"
    # 目标: 可见敌建筑/单位打分优先; 否则已知敌基地; 否则镜像扫描
    tgt_u = pick_target(s, home)
    if tgt_u:
        tgt = tgt_u["tl"]
    elif MEM["enemy_base"]:
        tgt = MEM["enemy_base"]
    else:
        mx, my = s["map"]
        if home:
            mirror = [max(mx - home[0], 8), max(my - home[1], 8)]
        else:
            mirror = [mx // 2, my // 2]
        corners = [mirror, [mx // 2, my // 2], [12, my // 2], [12, 12], [mx - 12, 12], [mx - 12, my - 12], [12, my - 12]]
        tgt = corners[wp[0] % len(corners)]
        if wp[1] <= time.time():
            wp[0] += 1; wp[1] = time.time() + 40
    if wp[2] == tuple(tgt) and wp[3] > time.time():
        return "march->%s (hold)" % (tgt,)
    wp[2] = tuple(tgt); wp[3] = time.time() + 12
    raw_order(ids, 4, tgt[0], tgt[1])
    return "attack->%s x%d" % (tgt, len(ids))

# ================= jev 决策 =================
def build_state_text(s, home):
    cred = s["me"]["credits"]
    pw, drain = s["me"]["power"].get("total", 0), s["me"]["power"].get("drain", 0)
    bl, units = {}, {}
    for u in s["mine"]:
        if u["o"] == 2:
            bl[u["n"]] = bl.get(u["n"], 0) + 1
        else:
            units[u["n"]] = units.get(u["n"], 0) + 1
    qs = {q["t"]: q for q in s["queues"]}
    def ql(t):
        q = qs.get(t)
        if not q:
            return "无"
        st = {0: "空闲", 1: "生产中", 2: "暂停", 3: "待放置"}[q.get("s", 0)]
        its = ",".join("%s%%%d" % (i["n"], i["p"]) for i in q.get("items", [])) or "-"
        return "%s[%s]" % (st, its)
    # 敌情: 按护甲归类 + 克制建议
    hos = s["hostile"]
    if hos:
        byarm = {}
        for h in hos:
            a = UDB.get(h["n"], {}).get("armor", "?")
            byarm.setdefault(a, []).append(h["n"])
        en_lines = []
        for a, names in sorted(byarm.items(), key=lambda kv: -len(kv[1])):
            cnt = {}
            for n in names:
                cnt[n] = cnt.get(n, 0) + 1
            comp = ",".join("%s(%s)x%d@%s" % (k, nm(k), v, next(h["tl"] for h in hos if h["n"] == k)) for k, v in cnt.items())
            cts = COUNTERS.get(a, [])
            cts_txt = "; ".join("%s=%s" % (nm(c), d) for c, d in cts[:3]) or "无已知克制"
            en_lines.append("·[%s甲] %s → 克制: %s" % (a, comp, cts_txt))
        hos_txt = "\n".join(en_lines)
    else:
        hos_txt = "视野内无敌军"
    av = {int(k): v for k, v in (s["av"] or {}).items()}
    def avl(t, glosser):
        return ", ".join("%s(%s,%d金)" % (n, glosser(n), ucost(n)) for n in av.get(t, [])) or "无"
    my_val = sum(ucost(u["n"]) for u in s["mine"] if u["o"] in (3, 7) and u["n"] not in HARVEST)
    en_val = sum(ucost(h["n"]) for h in s["hostile"])
    ev_txt = "\n".join("· " + e for e in reversed(MEM.get("events", [])[-5:])) or "无"
    lines = [
        "== 最近事件(新→旧, 即时战况) ==",
        ev_txt,
        "兵力价值对比: 我方≈%d vs 视野内敌军≈%d | 近期受袭 %d 次/2分钟" % (my_val, en_val, len(MEM.get("alarm_times", []))),
        "== 战场状态 ==",
        "时间%ds(约%d分钟) 资金%d 电力:%s(余量%d,需求%d/容量%d) 雷达:%s" % (
            s["t"], s["t"] // 60, cred,
            "缺电!" if s["me"]["power"].get("isLowPower") else "正常", pw - drain, drain, pw,
            "不可用" if s["me"].get("low") else "正常"),
        "我方建筑: %s" % (", ".join("%s(%s)x%d" % (k, nm(k), v) for k, v in sorted(bl.items())) or "无"),
        "我方部队: %s" % (", ".join("%s(%s)x%d" % (k, nm(k), v) for k, v in sorted(units.items())) or "无"),
        "队列 建筑:%s | 防御:%s | 步兵:%s | 载具:%s" % (ql(0), ql(1), ql(2), ql(3)),
        "可造建筑: %s" % avl(0, nm),
        "可造防御: %s" % avl(1, nm),
        "可造步兵: %s" % avl(2, nm),
        "可造载具: %s" % avl(3, nm),
        "== 敌情 ==",
        hos_txt,
        "敌基地坐标: %s" % (MEM["enemy_base"] or "未侦察到"),
        "基地位置:%s" % (home,),
    ]
    return "\n".join(lines)

def jev_decide(s, home, stance_prev):
    side = get_side(s)
    n_ref = len([u for u in s["mine"] if u["n"] == side["ref"]])
    n_bar = len([u for u in s["mine"] if u["n"] == side["bar"]])
    n_dog = len([u for u in s["mine"] if u["n"] in ("ADOG", "DOG")])
    av0 = [n for n in (s["av"].get("0") or []) if not (n == side["ref"] and n_ref >= T["ref_cap"])
           and not (n == side["bar"] and n_bar >= 2)]
    av2 = s["av"].get("2") or []
    if n_dog >= 4:
        av2 = [x for x in av2 if x not in ("ADOG", "DOG")]
    av3 = s["av"].get("3") or []
    txt = build_state_text(s, home)
    faction = "%s侧·国家%s 开局序列: %s" % (side["side"], side.get("country", "?"), "→".join(side["opening"]))
    if side.get("country") == "French":
        faction += "。法国专属: 巨炮GTGCAN(2000金,150伤/射程15,需雷达)——三矿车之后强烈建议造1-2座守基地方向路口"
    state = {"battlefield": txt, "doctrine": DOCTRINE, "faction": faction}
    Q = {}
    crit_b = {n: "%s(%d金)" % (nm(n), ucost(n)) for n in av0}
    crit_b["hold"] = "本tick不开新建筑"
    Q["build"] = {"type": "choice",
        "instructions": "建造参谋: 选下一个开始生产的建筑(队列一次一个)。按手册优先级: 补电力>经济精炼厂(≤2座)>兵营(战车工厂前置,出步兵)>战车工厂>雷达或空指部(开图解锁科技)>对空建筑>实验室。结合当前时间窗、资金和阵营判断。资金充裕且队列空闲时绝不选hold。",
        "criteria": crit_b}
    if av2:
        crit_i = {n: "%s(%d金)" % (nm(n), ucost(n)) for n in av2}
        crit_i["hold"] = "不造步兵"
        Q["inf"] = {"type": "choice",
            "instructions": "选一种步兵生产。军犬=侦察+预警(视野9); 动员兵90金性价比之王(同价完胜大兵),可进驻建筑; 磁爆步兵反装甲+可给线圈充能; 防空步兵机动防空; 工程师占家/修车。按敌情和资金选,无需时hold。",
            "criteria": crit_i}
    if av3:
        crit_v = {n: "%s(%d金)" % (nm(n), ucost(n)) for n in av3}
        crit_v["hold"] = "不造载具"
        Q["veh"] = {"type": "choice",
            "instructions": "选一种载具生产。犀牛=绝对主力(900金,5炮杀犀牛/4炮杀灰熊); 恐怖机器人=刺客专咬矿车/载具(400金,别啃建筑); 防空履带车=唯一移动防空+反步兵(500金); 天启=肉盾自带对空(贵且慢); V3只拆家打单位无效; 磁能坦克射程短怕风筝。按战略和敌构成选。",
            "criteria": crit_v}
    Q["stance"] = {"type": "choice",
        "instructions": "五态态势机裁决(当前执行态势:%s)。DEVELOP=开局~5分钟无敌情,建造探图攒兵; DEFEND=基地受威胁,回防补防空; RUSH=开局8分钟内且坦克≥4-5,直扑敌基地换家; ATTACK=坦克≥8且已侦察到敌目标,集火拆生产建筑(留2守家); RECOVER=主力被歼,收缩抢经济。注意: 开局8分钟内除非主力全灭否则不要选recover; 近期受袭次数高(≥3次/2分钟)说明AI正在施压,应选DEFEND而非develop。" % stance_prev,
        "criteria": {"develop": "发展攒兵探图", "defend": "回防基地", "rush": "早期换家快攻", "attack": "军团总攻", "recover": "收缩重建"}}
    Q["threat"] = {"type": "noul",
        "instructions": "根据视野内敌方单位数量/兵种/与基地坐标的距离,判断基地当前是否正遭受实际威胁(敌人即将打到或正在打基地建筑)。远处路过的散兵不算。"}
    return tsj(state, Q)

CONF = {"build": 0.40, "inf": 0.35, "veh": 0.35, "stance": 0.45}

# ================= 主循环 =================
def main():
    import faulthandler
    faulthandler.dump_traceback_later(30, repeat=True,
                                      file=open(os.path.join(WS, "bot-fault.log"), "w"))
    log("=== bot v2 (doctrine) start pid=%d ===" % os.getpid())
    stance = "develop"
    ended = 0
    wp = [0, 0.0, (), 0.0, False]  # 路标索引/切换时刻/当前目标/重发截止/已派侦察
    tick_n = 0
    while True:
        tick_n += 1
        _t0 = time.time()
        try:
            s = get_state()
        except RuntimeError as e:
            if "battle-ended" in str(e) or "eval empty" in str(e):
                ended += 1
                if ended % 10 == 1:
                    log("waiting battle (%d): %s" % (ended, str(e)[:100]))
                if ended > 200 or page_finished():
                    log("### battle finished, exiting (%d tries)" % ended)
                    break
                time.sleep(3); continue
            log("state ERR %s" % e); time.sleep(3); continue
        except Exception as e:
            log("state ERR %s" % e); time.sleep(3); continue
        ended = 0
        if tick_n <= 3:
            log("hb tick#%d state %.2fs t=%s" % (tick_n, time.time() - _t0, s.get("t")))
        # 模拟停摆保护: 游戏tick不动时(窗口最小化/节流), 不发任何指令(防指令垃圾与重复扣款)
        if "t" not in s or "me" not in s:
            ended += 1
            if ended > 8 or page_finished():
                log("### battle finished, exiting (%d tries)" % ended)
                break
            time.sleep(3); continue
        # 模拟停摆保护: 游戏秒数不动 = 窗口被节流/冻结, 不发指令(防指令垃圾)
        if MEM.get("last_t") == s["t"]:
            if not MEM.get("stall_logged") or time.time() - MEM.get("stall_t", 0) > 15:
                log("t=%d SIM STALL (time frozen) - skip actions" % s["t"])
                MEM["stall_logged"] = True; MEM["stall_t"] = time.time()
            time.sleep(1.0); continue
        MEM["last_t"] = s["t"]; MEM["stall_logged"] = False
        if s["me"]["defeated"]:
            log("### DEFEATED at t=%ds" % s["t"]); break
        ais = [p for p in s["players"] if p["ai"]]
        if ais and all(p["def"] for p in ais):
            log("### VICTORY at t=%ds  ***" % s["t"]); break
        home = yard_tile(s)
        # 秒级战场感知: tick间差分(建筑掉血/敌逼近/损失) -> 危机速应不等jev
        crisis = False
        try:
            alarm = sense_events(s, home)
            if alarm:
                crisis = True
                stance = "defend"
                defenders = [u["id"] for u in s["mine"] if u["o"] in (3, 7)
                             and u["n"] not in HARVEST and u["n"] not in ("SENGINEER",)
                             and u["hp"] >= T["retreat_hp"] * u["mhp"]]
                n_en = max(1, len(s["hostile"]))
                if defenders and time.time() - MEM["last_defend_order"] > 8:
                    # 第19局复盘: 敌军优势时反击=分批送人头; 需2倍兵力优势或敌≤2才出击
                    if len(defenders) >= 1.2 * n_en or n_en <= 2:
                        raw_order(defenders, 4, alarm["pos"][0], alarm["pos"][1])
                        log("t=%d ALARM %s -> counter %d vs %d -> %s" % (s["t"], alarm["what"], len(defenders), n_en, alarm["pos"]))
                    else:
                        if home:
                            raw_order(defenders, 4, home[0], home[1] + 3)
                        log("t=%d ALARM %s -> TURTLE (%d v %d, 守塔阵不打野战)" % (s["t"], alarm["what"], len(defenders), n_en))
                    MEM["last_defend_order"] = time.time()
        except Exception as e:
            log("sense ERR %s" % str(e)[:120])
        # §10.1 确定性清单 (含防御/电力/经济/产能/维修/撤退)
        try:
            new_st = checklist(s, home, stance)
            if new_st:
                stance = new_st
        except Exception as e:
            log("checklist ERR %s" % str(e)[:150])
        # 侦察与敌基地记忆
        try:
            update_enemy_base(s)
            scouting(s, home) if home else None
        except Exception as e:
            log("scout ERR %s" % str(e)[:100])
        # 开局确定性建造序列 (阵营感知, 不依赖jev; Bible §5.1/§5.2)
        side = get_side(s)
        qs = {q["t"]: q for q in s["queues"]}
        av0 = s["av"].get("0") or []
        bl0 = {}
        for u in s["mine"]:
            if u["o"] == 2:
                bl0[u["n"]] = bl0.get(u["n"], 0) + 1
        opening_next = None
        for want in side["opening"]:
            if bl0.get(want, 0) == 0:
                opening_next = want; break
        # 第20局复盘: 工厂落地后立即补二矿(经济优先), 不再等 t>500
        if opening_next is None and bl0.get(side["weap"], 0) >= 1                 and bl0.get(side["ref"], 0) < T["ref_cap"] and side["ref"] in av0:
            opening_next = side["ref"]
        if opening_next is None and s["t"] > 500:
            if bl0.get(side["weap"], 0) < 2 and s["me"]["credits"] > T["factory2_cash"] and side["weap"] in av0:
                opening_next = side["weap"]
            elif bl0.get(side["ref"], 0) < T["ref_cap"] and side["ref"] in av0:
                opening_next = side["ref"]
        if opening_next and qs.get(0, {}).get("s") == 0 and opening_next in av0:
            produce(opening_next, 1)
            log("t=%d OPENING BUILD %s" % (s["t"], opening_next))
        # jev 语义决策 (危机时先打后想, 跳过本tick省1秒)
        if crisis:
            ans = {}
        else:
            try:
                ans = jev_decide(s, home, stance)
            except Exception as e:
                log("jev ERR %s" % str(e)[:150]); ans = {}
        cred = s["me"]["credits"]
        av0 = s["av"].get("0") or []
        # jev 建筑 (确定性清单没花的钱由 jev 决定花法)
        q0 = qs.get(0, {})
        b = ans.get("build", {}).get("choice")
        n_bar_now = len([u for u in s["mine"] if u["n"] == side["bar"]])
        if b and b != "hold" and q0.get("s") == 0 and b in av0 \
                and not (b == side["ref"] and len([u for u in s["mine"] if u["n"] == side["ref"]]) >= T["ref_cap"]) \
                and not (b == side["bar"] and n_bar_now >= 2):
            produce(b, 1)
            log("t=%d jev BUILD %s (conf %.2f)" % (s["t"], b, ans.get("build", {}).get("confidence", -1)))
        # jev 步兵
        q2 = qs.get(2, {})
        i = ans.get("inf", {}).get("choice")
        if i and i != "hold" and q2.get("s", 0) == 0 and i in (s["av"].get("2") or []):
            produce(i, 1)
            log("t=%d jev INF %s (conf %.2f)" % (s["t"], i, ans.get("inf", {}).get("confidence", -1)))
        # 态势裁决: jev 投票 (≥0.45 采信), 确定性威胁/受袭已在上游强制
        st_raw = ans.get("stance", {})
        if st_raw.get("choice") and st_raw.get("confidence", 0) >= CONF["stance"]:
            if st_raw["choice"] != stance:
                log("t=%d jev STANCE %s->%s (conf %.2f)" % (s["t"], stance, st_raw["choice"], st_raw.get("confidence", -1)))
            stance = st_raw["choice"]
        th = ans.get("threat", {})
        th = th.get("probability", th.get("noul", 0)) if isinstance(th, dict) else 0
        if th > 0.6 and stance != "defend":
            log("t=%d THREAT %.2f -> force defend" % (s["t"], th))
            stance = "defend"
        # RECOVER 判定: 主力被歼
        n_tank = len([u for u in s["mine"] if u["o"] == 7 and u["n"] not in HARVEST])
        if n_tank < 3 and s["t"] > 400 and stance in ("attack", "rush"):
            stance = "recover"
            log("t=%d RECOVER (only %d tanks)" % (s["t"], n_tank))
        # RUSH 窗口: 4-8分钟且坦克≥5
        if T["rush_t0"] <= s["t"] <= T["rush_t1"] and n_tank >= T["rush_tanks"] and stance in ("develop", "recover"):
            stance = "rush"
            log("t=%d RUSH window (%d tanks)" % (s["t"], n_tank))
        # ATTACK 门槛: 坦克≥8 (或后期≥15)
        if n_tank >= T["attack_tanks"] and stance in ("develop", "rush", "recover"):
            stance = "attack"
            log("t=%d ATTACK (tanks=%d)" % (s["t"], n_tank))
        # 进攻执行 (ALARM反击令8秒保护期内不被集结覆盖)
        try:
            if time.time() - MEM.get("last_defend_order", 0) < 8:
                r = "alarm-active (hold moves)"
            else:
                r = unit_move_attack(stance, s, home, wp)
            if not r.endswith("(hold)"):
                log("t=%d MOVE %s" % (s["t"], r))
        except Exception as e:
            log("move ERR %s" % str(e)[:120])
        if tick_n % 25 == 0:
            log("t=%d tick#%d credits=%d stance=%s tanks=%d" % (s["t"], tick_n, cred, stance, n_tank))
        time.sleep(1.5)

if __name__ == "__main__":
    main()
