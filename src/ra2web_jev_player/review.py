# -*- coding: utf-8 -*-
"""复盘引擎 —— 学习闭环的"记录→分析→总结→迭代"段。

闭环：实战(game.py) → 逐事件审计(audit.py) → 本模块复盘 →
  ① logs/games/game-XXXX-review.md  每局完整复盘报告
  ② docs/LESSONS.md                 经验账本（追加式，人/agent 可读）
  ③ knowledge/doctrine.json         参数覆盖（白名单+限幅+Jev 置信闸门，git 可审计）
→ 下一局 doctrine.T 加载覆盖值（doctrine.load_overrides），新局验证。

复盘分两层（METHODOLOGY 原则）：
- 确定性分析（本模块代码）：开局时序 vs 手册窗口、经济/兵力曲线、态势分布、
  危机响应、损失交换比、错误指纹——能用代码算的绝不给模型；
- Jev 语义复盘（TypeSafe）：败因归类、最优先改进项、是否值得自动调参——语义拍板。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .audit import Audit
from .jev import JevClient
from .paths import LOG_DIR, PROJECT_ROOT
from .strategy.doctrine import T, load_overrides

GAMES_DIR = LOG_DIR / "games"
LESSONS_PATH = PROJECT_ROOT / "docs" / "LESSONS.md"
OVERRIDES_PATH = PROJECT_ROOT / "knowledge" / "doctrine.json"
SEED_GAMES = 23            # 第 1-23 局记录在历史日志/报告中（本闭环上线前）
_REVIEW_SEED = "RA2WEB_GAME_SEED"

# 复盘时间窗参照（Bible §5.4）：开局 60s 内电厂、~300s 前首坦克
BUILD_WINDOWS = {"NAPOWR": 45, "NAREFN": 120, "NAHAND": 240, "NAWEAP": 330}

# 自动调参白名单与限幅（缺省值边界）：只允许小幅收紧/放宽，防单局噪声破坏 doctrine
TUNING_RULES = {
    "no_target":   [("attack_tanks", -1, 5), ("rush_tanks", -1, 3)],
    "starve":      [("tank_cash1", -100, 800), ("tank_cash2", -200, 1200)],
    "def overrun": [("defend_radius", +2, 26)],
    "attrition":   [("retreat_hp", +0.05, 0.60)],
}


# ================= 数据采集 =================

def _latest_run_dir():
    """[训练数据] 最新的 run 目录（每局独立存档）。"""
    runs = LOG_DIR.glob("games/run-*/events.jsonl")
    try:
        return max(runs, key=lambda p: p.stat().st_mtime).parent
    except ValueError:
        return None


def _slice_events() -> list:
    """取最后一段对局的 jsonl 事件。

    优先读最新 run 目录的 events.jsonl（训练数据镜像, 单局完整）;
    无 run 目录时回退到全局 jev-events.jsonl 切片（最后一个 start 之后）。
    """
    run_dir = _latest_run_dir()
    if run_dir:
        path = run_dir / "events.jsonl"
        events = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if events:
            return events
    path = LOG_DIR / "jev-events.jsonl"
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("kind") == "start":
            return events[i:]
    return events


def _slice_botlog(log_path: Path | None = None) -> list:
    """取最后一段对局的 bot.log 行（最后一个 start banner 之后）。"""
    path = log_path or (LOG_DIR / "bot.log")
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=== ra2web-jev-player start" in line:
                lines = []
            lines.append(line.rstrip("\n"))
    return lines


class GameRecord:
    """一局的结构化记录（从事件流 + 行日志解析）。"""

    def __init__(self, events: list, loglines: list):
        self.events = events
        self.loglines = loglines
        self.started_ts = next((e.get("ts") for e in events if e.get("kind") == "start"), None)
        report = next((e for e in events if e.get("kind") == "report"), None)
        self.report = report or {}
        self.outcome = self.report.get("result", "unknown")
        self.t_end = self.report.get("t")
        # 事件分类
        self.decisions = [e for e in events if e.get("kind") == "decision"]
        self.actions = [e for e in events if e.get("kind") == "action"]
        self.obs = [e for e in events if e.get("kind") == "obs"]
        self.losses = [e for e in events if e.get("kind") == "loss"]
        self.kills = [e for e in events if e.get("kind") == "kill"]
        self.places = [e for e in events if e.get("kind") == "place"]
        # 行日志分类（[第47局] 排除 "HOLD" 行——被资金闸门拒绝的意图不算建造）
        # [第53局复盘] "POWER plant (reserve)" 是电力保底路径的真实下单, 旧正则
        # 看不见 → 误报"开局缺 NAPOWR/慢 502%"。阵营由其他建造码推断
        # (NAREFN 族→NAPOWR / GAREFN 族→GAPOWR), 之后按 t 重排。
        self.build_order = [(int(m.group(1)), m.group(2)) for ln in loglines
                            if "HOLD" not in ln
                            and (m := re.search(r"t=(\d+) (?:OPENING BUILD|jev BUILD) (\w+)", ln))]
        _codes = {c for _, c in self.build_order}
        _powr = "GAPOWR" if {"GAREFN", "GAPILE", "GAWEAP"} & _codes else "NAPOWR"
        self.build_order += [(int(m.group(1)), _powr) for ln in loglines
                             if "POWER plant (reserve" in ln
                             and (m := re.search(r"t=(\d+) POWER plant", ln))]
        self.build_order.sort(key=lambda x: x[0])
        self.tanks_built = [(int(m.group(1)), m.group(2), int(m.group(3))) for ln in loglines
                            if (m := re.search(r"t=(\d+) TANK (\w+) x(\d+)", ln))]
        self.first_tank_t = self.tanks_built[0][0] if self.tanks_built else None
        self.alarms = [ln for ln in loglines if "ALARM" in ln]
        self.turtles = [ln for ln in loglines if "TURTLE" in ln]
        self.counters = [ln for ln in loglines if "-> counter" in ln]
        self.stalls = [ln for ln in loglines if "SIM STALL" in ln]
        self.stance_changes = [(m.group(1), m.group(2), m.group(3)) for ln in loglines
                               if (m := re.search(r"jev STANCE (\w+)->(\w+) \(conf ([\d.]+)\)", ln))]
        self.err_lines = [ln for ln in loglines if re.search(r"\b\w+ ERR ", ln)]
        self.enemy_base = re.search(r"ENEMY BASE spotted @\[(\d+), ?(\d+)\]", "\n".join(loglines))

    # ---------- 派生统计 ----------

    def stance_distribution(self) -> dict:
        dist = {}
        for e in self.obs:
            st = e.get("stance")
            dist[st] = dist.get(st, 0) + 1
        total = sum(dist.values()) or 1
        return {k: round(v / total, 2) for k, v in sorted(dist.items(), key=lambda kv: -kv[1])}

    def economy(self) -> dict:
        creds = [e.get("credits", 0) for e in self.obs]
        if not creds:
            return {}
        return {"avg": round(sum(creds) / len(creds)),
                "starve_frac": round(sum(1 for c in creds if c < 200) / len(creds), 2),
                "max": max(creds)}

    def army_curve(self) -> dict:
        if not self.obs:
            return {}
        return {"my_val_peak": max(e.get("my_val", 0) for e in self.obs),
                "en_val_peak": max(e.get("en_val", 0) for e in self.obs),
                "tanks_peak": max(e.get("tanks", 0) for e in self.obs)}

    def loss_kill(self) -> dict:
        from collections import Counter
        return {"losses": len(self.losses),
                "loss_top": Counter(e.get("n") for e in self.losses).most_common(5),
                "kills_visible": len(self.kills)}


# ================= 确定性分析 =================

def analyze(rec: GameRecord) -> list:
    """确定性发现：每条 (severity, 标题, 证据)。"""
    out = []
    # 1) 开局时序 vs 手册窗口（build_order 元素是 (t, code)，取每个代号首次建成时间）
    built: dict = {}
    for t, code in rec.build_order:
        built.setdefault(code, t)
    for code, window in BUILD_WINDOWS.items():
        t = built.get(code)
        if t is None:
            out.append(("high", "开局缺 %s（%ds 窗口内未建成）" % (code, window), "build_order"))
        elif t > window * 1.5:
            out.append(("med", "%s 建成于 t=%ds，手册窗口 ~%ds（慢 %.0f%%）"
                        % (code, t, window, 100 * (t / max(window, 1) - 1)), "build_order"))
    # 2) 首坦克时间
    if rec.first_tank_t is None:
        out.append(("high", "整局没有一辆坦克下线", "TANK lines"))
    elif rec.first_tank_t > 400:
        out.append(("med", "首坦克 t=%ds（Bible 时间窗 180-320s）" % rec.first_tank_t, "TANK lines"))
    # 3) 侦察
    if not rec.enemy_base:
        out.append(("high", "敌基地全程未定位 → ATTACK/RUSH 无目标，无法取胜",
                    "ENEMY BASE line"))
    # 4) 经济
    eco = rec.economy()
    if eco and eco.get("starve_frac", 0) > 0.6:
        out.append(("med", "资金长期见底（<200 金占比 %.0f%%），坦克生产线被步兵/防御挤占"
                    % (eco["starve_frac"] * 100), "obs credits"))
    # 5) 步兵/坦克失衡
    curve = rec.army_curve()
    if curve and curve.get("tanks_peak", 0) < 5 and rec.t_end and rec.t_end > 900:
        out.append(("med", "15 分钟后坦克峰值仅 %d 辆（总攻门槛 %d）——产能/资金被别处吃掉"
                    % (curve.get("tanks_peak", 0), T["attack_tanks"]), "obs tanks"))
    # 6) 防守占比
    dist = rec.stance_distribution()
    if dist.get("defend", 0) >= 0.7 and rec.outcome != "victory":
        out.append(("high", "态势 %.0f%% 时间在 defend：纯被动挨打，缺进攻闭环"
                    % (dist.get("defend", 0) * 100), "obs stance"))
    # 7) 危机响应
    if rec.report:
        ct = rec.report.get("crisis_ticks") or 0
        tk = rec.report.get("ticks") or 1
        if ct / max(tk, 1) > 0.3:
            out.append(("med", "危机 tick 占比 %.0f%%（%d/%d）——长期处于被袭状态"
                        % (100 * ct / tk, ct, tk), "report"))
    # 8) 错误指纹
    errs = {}
    for ln in rec.err_lines:
        key = re.search(r"(\w+) ERR", ln)
        errs[key.group(1)] = errs.get(key.group(1), 0) + 1 if key else 1
    for k, v in errs.items():
        out.append(("high" if v > 10 else "med", "%s ERR ×%d（工程缺陷，逐 tick 失效）" % (k, v),
                    "log"))
    if len(rec.stalls) > 0:
        out.append(("low", "模拟停摆 %d 次" % len(rec.stalls), "log"))
    return out


# ================= Jev 语义复盘 =================

def summary_text(rec: GameRecord, findings: list) -> str:
    """战报 → 紧凑中文复盘素材（喂 Jev 的 state）。"""
    eco, curve, lk = rec.economy(), rec.army_curve(), rec.loss_kill()
    bo = " → ".join("%s@%ds" % (n, t) for t, n in rec.build_order[:10]) or "无建筑建成"
    lines = [
        "== 对局结果 ==",
        "结果:%s 时长:%s游戏秒 ticks:%d 危机tick:%d" % (
            rec.outcome, rec.t_end, rec.report.get("ticks"), rec.report.get("crisis_ticks")),
        "开局建造: " + bo,
        "首坦克: t=%ss" % rec.first_tank_t,
        "敌基地定位: %s" % ("已定位" if rec.enemy_base else "全程未发现"),
        "== 数据曲线 ==",
        "兵力价值峰值: 我方%s vs 敌%s | 坦克峰值: %s" % (
            curve.get("my_val_peak"), curve.get("en_val_peak"), curve.get("tanks_peak")),
        "资金: 平均%s 峰值%s 见底率%.0f%%" % (
            eco.get("avg"), eco.get("max"), (eco.get("starve_frac") or 0) * 100),
        "损失/可见击杀: %d/%d  top损失: %s" % (
            lk["losses"], lk["kills_visible"], lk["loss_top"]),
        "态势分布: %s | ALARM:%d(反击%d/守塔%d) 停摆:%d" % (
            rec.stance_distribution(), len(rec.alarms), len(rec.counters),
            len(rec.turtles), len(rec.stalls)),
        "== 确定性发现 ==",
        "\n".join("·[%s] %s" % (sev, txt) for sev, txt, _ in findings) or "·无",
    ]
    return "\n".join(lines)


ROOTCAUSE_CRITERIA = {
    "no_target": "侦察失败/敌基地未定位, 进攻态势无目标可打, 全程被动",
    "starve": "经济或产能断粮: 坦克上不了产线, 资金长期见底, 步兵/防御吃掉预算",
    "def overrun": "防守体系被消耗/压垮: 塔阵被打穿, 波次强于防御恢复",
    "attrition": "野战/微操交换比劣势: 兵力换亏, 残血不撤或反击送人头",
    "bug": "工程缺陷: 某 tick 层逐帧报错失效(如侦察/感知)",
    "timing": "开局时序过慢: 建造/出兵晚于手册窗口, 被早期 rush 打崩",
    "other": "以上都不是或混合原因之外的因素",
}

TOPFIX_CRITERIA = {
    "fix_scout": "修侦察链路: 保证敌基地定位(军犬+坦克镜像探图), 让进攻有目标",
    "boost_econ": "加强经济时序: 二矿/矿车更早, 坦克预算优先级更高",
    "attack_earlier": "降低进攻门槛: 更早换家/rush, 不等大军团",
    "deepen_def": "加强防御纵深: 更多塔/前置阵地/修复优先级",
    "fix_bugs": "优先修工程 bug, 策略不动",
    "keep": "保持现状, 本局原因属偶然",
}


def jev_review(rec: GameRecord, findings: list, jev: JevClient) -> dict:
    """Jev 语义复盘：败因归类 + 最优先改进 + 是否值得自动调参。"""
    state = summary_text(rec, findings)
    answers = jev.ask(state, {
        "rootcause": {"type": "choice",
                      "instructions": ("对战复盘裁判: 从数据曲线和确定性发现判断本局失利的"
                                       "首要根因（单选最主要的一个）。"),
                      "criteria": ROOTCAUSE_CRITERIA},
        "topfix": {"type": "choice",
                   "instructions": "下一局最应该优先做的一件事（单选，对胜率提升最大）。"
                                   "注意与根因对应, 但也要考虑性价比。",
                   "criteria": TOPFIX_CRITERIA},
        "tune": {"type": "noul",
                 "instructions": ("基于本局数据, 是否支持对 doctrine 参数做一次小幅自动微调"
                                  "（白名单内限幅, 如进攻门槛/坦克资金线）? "
                                  "数据噪声大或根因是工程bug时说不。")},
    })
    return answers


# ================= 迭代：参数自动微调（白名单+限幅） =================

def _clamp(v: float, lo: float) -> float:
    return max(v, lo)


def auto_tune(rootcause: str, tune_conf: float, game_no: int, reason: str) -> list:
    """根因 → 白名单参数微调（限幅）。tune_conf > 0.6 才执行。返回变更描述。"""
    if tune_conf <= 0.6 or rootcause not in TUNING_RULES:
        return []
    applied = load_overrides()
    changes = []
    for key, delta, floor in TUNING_RULES[rootcause]:
        cur = T[key]
        new = _clamp(round(cur + delta, 2), floor)
        if new == cur:
            continue
        T[key] = new
        changes.append({"key": key, "from": cur, "to": new,
                        "reason": "%s@game%d: %s" % (rootcause, game_no, reason)})
    if changes:
        _save_overrides(changes, game_no, reason)
    return changes


def _save_overrides(changes: list, game_no: int, reason: str) -> None:
    try:
        ov = json.load(open(OVERRIDES_PATH, encoding="utf-8")) if OVERRIDES_PATH.exists() else {}
    except Exception:
        ov = {}
    t_ov = ov.setdefault("T", {})
    for c in changes:
        t_ov[c["key"]] = c["to"]
    hist = ov.setdefault("history", [])
    hist.append({"game": game_no, "ts": time.strftime("%Y-%m-%d %H:%M"),
                 "reason": reason,
                 "changes": [{k: c[k] for k in ("key", "from", "to")} for c in changes]})
    ov["history"] = hist[-20:]
    ov["_provenance"] = "由 review.py 复盘自动写入（白名单+限幅+Jev 置信>0.6 闸门）；可直接人工编辑"
    OVERRIDES_PATH.write_text(json.dumps(ov, ensure_ascii=False, indent=2), encoding="utf-8")


# ================= 输出 =================

def _fmt_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def write_review_md(rec: GameRecord, findings: list, answers: dict,
                    changes: list, game_no: int) -> Path:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    path = GAMES_DIR / ("game-%04d-review.md" % game_no)
    eco, curve, lk = rec.economy(), rec.army_curve(), rec.loss_kill()
    rc = (answers.get("rootcause") or {}).get("choice")
    fix = (answers.get("topfix") or {}).get("choice")
    lines = [
        "# 第 %d 局复盘 —— %s" % (game_no, _fmt_ts()),
        "",
        "- **结果**: %s（t=%s 游戏秒, %d ticks, 危机 %d ticks）" % (
            rec.outcome, rec.t_end, rec.report.get("ticks", 0) or 0,
            rec.report.get("crisis_ticks", 0) or 0),
        "- **开局建造**: %s" % (" → ".join("%s@%ds" % (n, t) for t, n in rec.build_order) or "无"),
        "- **首坦克**: t=%s | 敌基地: %s" % (
            rec.first_tank_t, "已定位" if rec.enemy_base else "未定位"),
        "- **经济**: 平均 %s / 峰值 %s / 见底率 %.0f%%" % (
            eco.get("avg"), eco.get("max"), (eco.get("starve_frac") or 0) * 100),
        "- **兵力**: 峰值我方 %s vs 敌 %s | 坦克峰值 %s | 损失 %d / 可见击杀 %d" % (
            curve.get("my_val_peak"), curve.get("en_val_peak"), curve.get("tanks_peak"),
            lk["losses"], lk["kills_visible"]),
        "- **态势分布**: %s | ALARM %d（反击 %d / TURTLE %d）| 停摆 %d" % (
            rec.stance_distribution(), len(rec.alarms), len(rec.counters),
            len(rec.turtles), len(rec.stalls)),
        "- **Jev**: %d 次决策, %d 错误, P50 %sms / P95 %sms, 态势变更 %d 次" % (
            rec.report.get("jev", {}).get("decisions", 0),
            rec.report.get("jev", {}).get("errors", 0),
            rec.report.get("jev", {}).get("p50_ms"), rec.report.get("jev", {}).get("p95_ms"),
            len(rec.stance_changes)),
        "",
        "## 确定性发现",
        "",
        "\n".join("- [%s] %s" % (sev, txt) for sev, txt, _ in findings) or "- 无",
        "",
        "## Jev 复盘",
        "",
        "- **根因**: %s — %s（置信 %.2f）" % (
            rc, ROOTCAUSE_CRITERIA.get(rc, "?"),
            (answers.get("rootcause") or {}).get("confidence", -1)),
        "- **下局优先**: %s — %s（置信 %.2f）" % (
            fix, TOPFIX_CRITERIA.get(fix, "?"),
            (answers.get("topfix") or {}).get("confidence", -1)),
        "- **调参支持度**: %s" % ((answers.get("tune") or {}).get("noul")),
        "",
        "## 参数迭代（自动, 白名单+限幅）",
        "",
        "\n".join("- `%s`: %s → %s" % (c["key"], c["from"], c["to"]) for c in changes) or "- 无",
        "",
        "## 待办改进（人工/下个 session）",
        "",
        "- [ ] 按上表核对下局验证点",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 事件切片留档
    (GAMES_DIR / ("game-%04d-events.jsonl" % game_no)).write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in rec.events) + "\n",
        encoding="utf-8")
    return path


def append_lessons(rec: GameRecord, findings: list, answers: dict,
                   changes: list, game_no: int, review_path: Path) -> None:
    rc = (answers.get("rootcause") or {}).get("choice")
    fix = (answers.get("topfix") or {}).get("choice")
    entry = [
        "",
        "## 第 %d 局 —— %s | %s | t=%s | 详见 %s" % (
            game_no, _fmt_ts(), rec.outcome, rec.t_end, review_path.name),
        "",
        "- **教训**: %s" % "；".join(txt for _, txt, _ in findings[:4]) or "-（无确定性发现）",
        "- **根因(Jev)**: %s | **下局优先**: %s" % (
            ROOTCAUSE_CRITERIA.get(rc, rc), TOPFIX_CRITERIA.get(fix, fix)),
    ]
    if changes:
        entry.append("- **已自动调参**: " + "；".join(
            "`%s` %s→%s" % (c["key"], c["from"], c["to"]) for c in changes))
    entry.append("- **待验证**: 下局检验上述调参与改进是否生效")
    with open(LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(entry) + "\n")


# ================= 入口 =================

def next_game_number() -> int:
    if GAMES_DIR.exists():
        nums = [int(m.group(1)) for p in GAMES_DIR.glob("game-*-review.md")
                if (m := re.match(r"game-(\d+)-review\.md", p.name))]
        if nums:
            return max(nums) + 1
    return SEED_GAMES + 1


def review_last_game(jev: JevClient, audit: Audit | None = None,
                     game_no: int | None = None,
                     log_path: Path | None = None) -> dict:
    """复盘最后一段对局（ jev-events.jsonl 最后一个 start → report）。

    返回 {game_no, outcome, findings, answers, changes, review_path}。
    """
    audit = audit or Audit(echo=False)
    game_no = game_no or next_game_number()
    rec = GameRecord(_slice_events(), _slice_botlog(log_path))
    if not rec.events:
        return {"game_no": game_no, "skipped": "no events"}
    findings = analyze(rec)
    answers, changes = {}, []
    try:
        answers = jev_review(rec, findings, jev)
        rc = (answers.get("rootcause") or {}).get("choice") or "other"
        tune = (answers.get("tune") or {}).get("noul") or 0
        changes = auto_tune(rc, tune if isinstance(tune, (int, float)) else 0,
                            game_no, "Jev复盘: %s" % rc)
    except Exception as e:
        if audit:
            audit.log("review jev ERR %s" % str(e)[:150])
    review_path = write_review_md(rec, findings, answers, changes, game_no)
    append_lessons(rec, findings, answers, changes, game_no, review_path)
    if audit:
        audit.log("REVIEW game#%d %s → %s | changes=%d"
                  % (game_no, rec.outcome, review_path.name, len(changes)))
    return {"game_no": game_no, "outcome": rec.outcome, "findings": findings,
            "answers": answers, "changes": changes, "review_path": str(review_path)}
