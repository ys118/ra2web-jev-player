# -*- coding: utf-8 -*-
"""Training-data asset builder: organizes match data into the canonical dataset/ structure (idempotent,
safe to re-run).

dataset/ is the main directory for training data (SFT/RL); the two sources occupy two sub-areas:

  A. dataset/game-NNNN/     historical backfill (games 1-65, from global event-stream slices and a
                            manually verified mapping)
  B. dataset/runs/run-<ts>/ incremental ingest (the per-game run dirs from game 45 onward, see below)

A. game-NNNN structure (historical):
  meta.json      per-game metadata (game number / date / result / data tier / file pointers)
  events.jsonl   that game's event stream (stored only when a source exists)
  review.md      review report (stored only when a source exists)
  run.log        process stdout log (stored only when filename and game number can be matched)
  decisions.jsonl  SFT tuples (stored only when a source exists)

B. runs/run-<ts> structure (incremental, one canonical copy per game):
  meta.json      holds the report triple + review link (review_no is a **serial number**, see
                 dataset/README.md)
  events.jsonl / decisions.jsonl / report.json / review.md

  Two ways to link run -> serial number:
    (1) run-*/game.json -- written back by review when a new game is reviewed (authoritative)
    (2) report.json (result,t,ticks,crisis_ticks) exactly matches the triple in the header of
        game-XXXX-review.md (back-linking for historical runs; accepted only when the alignment
        resolves to a single candidate, multiple candidates are never guessed)

Data tiers:
  rl-trajectory  complete event stream + known outcome (RL trajectories + return labels)
  sft-full       complete run dir (including the (state,questions,answers) tuples in decisions.jsonl)
  partial        aborted or concurrency-polluted games -- events partly usable
  legacy-meta    games 1-22 (old architecture) metadata only; raw line logs in artifacts/logs/bot.log

Usage:
  uv run python scripts/build_dataset.py            # full build (idempotent)
  uv run python scripts/build_dataset.py --check    # report current state only, no writes
"""
import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "artifacts" / "logs"
GAMES = ROOT / "artifacts" / "games"
OUT = ROOT / "dataset"

# 分段 → 局号 映射（2026-09-29 人工核对: 按 report 内容逐段对账）
# seg 0=官方体系(21-22混合); seg 10/11=无法归属的无报告会话(保留不丢)
SEG_MAP = {1: 23, 2: 24, 3: 25, 4: 26, 5: 27, 6: 28, 7: 29, 8: 30, 9: 31,
           12: 32, 13: 33, 14: 34, 15: 35, 16: 36, 17: 37, 18: 38, 19: 39,
           20: 40, 21: 41, 22: 42, 23: 43, 24: 44}
SEG0_NOTE = "官方体系时代（第21-22局混合, 旧格式事件）"

# 第 1-22 局元数据（旧架构, 结果出自 docs/SESSION-REPORT.md）
LEGACY = {
    1: ("defeat", "771", "全手动侦察, 基地车闲置"),
    2: ("defeat", "533", "半手动, 布完电厂无人值守"),
    3: ("defeat", "437", "部署指令重发横跳自杀"),
    4: ("defeat", "425", "jev 异常阻塞确定性 tick"),
    5: ("defeat", "833", "经济单薄被拆精炼厂"),
    6: ("defeat", "1452", "美军飞行兵掏家, 无防空"),
    7: ("defeat", "546", "大集群直推"),
    8: ("defeat", "1619", "rush 战略首验, 击杀 19"),
    9: ("defeat", "4806", "引擎过载技术冻结"),
    10: ("unknown", None, "未重启"),
    11: ("defeat", "589", "阵营盲区+模拟冻结"),
    12: ("defeat", "1288", "中盘调试空窗"),
    13: ("defeat", None, "工程夭折"),
    14: ("defeat", None, "工程夭折"),
    15: ("defeat", None, "工程夭折"),
    16: ("defeat", None, "工程夭折"),
    17: ("defeat", "1920", "快响应体系验证, 32 分钟最长"),
    18: ("defeat", "850", "阵营误判 450s 空窗"),
    19: ("defeat", "1550", "反击分批送人头, 击杀 98"),
    20: ("defeat", "1060", "防御支出吞噬坦克预算"),
    21: ("unknown", None, "官方体系首局, 渲染中断"),
    22: ("unknown", None, "官方体系, 0 失败验证"),
}

# 复盘文件 → 局号（内容已人工核对; 编号跳位见 docs/LESSONS.md）
REVIEW_MAP = {23: "0023", 24: "0024", 25: "0025", 26: "0026", 28: "0028", 29: "0029",
              33: "0030", 34: "0031", 36: "0032", 37: "0033", 38: "0034", 39: "0035",
              40: "0036", 42: "0037", 43: "0038", 44: "0039",
              45: "0040", 47: "0041", 48: "0042", 49: "0043", 50: "0044", 53: "0045",
              54: "0046", 55: "0047", 56: "0048", 58: "0049", 59: "0050", 60: "0051",
              61: "0052", 62: "0053", 63: "0054", 64: "0055", 65: "0056"}
REVIEW_DEGRADED = {29: "并发期数据, 与第 32 局事件混写"}
# [训练数据管道] 第 45 局起每局独立 run 目录（含 decisions.jsonl SFT 元组）
RUN_GAMES = {45: "run-20260929-132512", 46: "run-20260929-134527",
             47: "run-20260929-152348", 48: "run-20260929-153835",
             49: "run-20260929-214905", 50: "run-20260929-221730",
             53: "run-20260929-231736", 54: "run-20260930-134816", 55: "run-20260930-142623",
             56: "run-20260930-145311", 57: "run-20260930-152832", 58: "run-20260930-161817",
             59: "run-20260930-170418", 60: "run-20260930-171716", 61: "run-20260930-172827",
             62: "run-20260930-175039", 63: "run-20260930-194316", 64: "run-20260930-200759",
             65: "run-20260930-201929"}
# 进程 stdout 日志 → 局号（尾行 report 与局表对账）
RUNLOG_MAP = {23: "play-run.log", 24: "play24-run.log", 25: "play25-run.log",
              26: "play26-run.log", 28: "play28-run.log", 29: "play29-run.log",
              30: "play30-run.log", 31: "play31-run.log", 32: "play32-run.log",
              33: "play33-run.log", 34: "play34-run.log", 35: "play35-run.log",
              36: "play36-run.log", 37: "play37-run.log", 38: "play38-run.log",
              39: "play39-run.log", 40: "play40-run.log", 41: "play41-run.log",
              42: "play42-run.log", 43: "play43-run.log", 44: "play44-run.log"}

REVIEW_HEAD = re.compile(r"# 第 (\d+) 局复盘 —— (\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
REVIEW_RESULT = re.compile(
    r"- \*\*结果\*\*: (\w+)（t=(\S+) 游戏秒, (\d+) ticks, 危机 (\d+) ticks）")


# ================= 通用 =================

def split_segments():
    """Split the global event stream on kind==start. Returns [(idx, events)]."""
    segs, cur = [], None
    with open(LOGS / "jev-events.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("kind") == "start":
                if cur:
                    segs.append(cur)
                cur = []
            if cur is None:
                continue
            cur.append(ev)
    if cur:
        segs.append(cur)
    return segs


def seg_meta(events):
    """Extract metadata from a segment."""
    meta = {"events_count": len(events)}
    for ev in events:
        if ev.get("kind") == "report":
            meta["result"] = ev.get("result")
            meta["duration_s"] = ev.get("t")
            meta["ticks"] = ev.get("ticks")
        if ev.get("kind") == "start":
            meta["policy"] = ev.get("policy")
    kinds = {}
    for ev in events:
        kinds[ev.get("kind")] = kinds.get(ev.get("kind"), 0) + 1
    meta["event_kinds"] = kinds
    return meta


def read_jsonl(path):
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def write_jsonl(path, events, dry):
    if dry:
        return
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
                    encoding="utf-8")


def write_json(path, obj, dry):
    if dry:
        return
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file(src, dst, dry):
    if dry or not src.exists():
        return
    shutil.copy(src, dst)


# ================= A. 历史回填（1-65 局） =================

def review_result_index():
    """Serial number -> (result, t, ticks, crisis_ticks): the triple in the review file header (used for
    back-linking)."""
    idx = {}
    for p in sorted(GAMES.glob("game-*-review.md")):
        txt = p.read_text(encoding="utf-8")
        head, res = REVIEW_HEAD.search(txt), REVIEW_RESULT.search(txt)
        if head and res:
            idx[int(head.group(1))] = (res.group(1), res.group(2),
                                       int(res.group(3)), int(res.group(4)))
    return idx


def link_runs(dry):
    """Align run dirs -> serial numbers (game.json first, otherwise exact report-triple matching).

    Returns {run_name: {"review_no": N|None, "match": "...", "year": ...}}.
    Multiple candidates (identical result triples) are never guessed: they are recorded as ambiguous and
    left for a human to register in the alignment table in dataset/README.
    """
    by_triple = {}
    for rev_no, triple in review_result_index().items():
        by_triple.setdefault(triple, []).append(rev_no)
    links = {}
    for d in sorted(GAMES.glob("run-*")):
        rec = {"review_no": None, "match": "none"}
        link = d / "game.json"          # ① 复盘时写回的权威链接
        if link.exists():
            try:
                rec["review_no"] = int(json.loads(link.read_text(encoding="utf-8"))["game_no"])
                rec["match"] = "game.json"
            except (ValueError, KeyError, json.JSONDecodeError):
                rec["match"] = "game.json-unreadable"
        elif (d / "report.json").exists():   # ② 历史 run: 结果三元组精确匹配
            r = json.loads((d / "report.json").read_text(encoding="utf-8"))
            triple = (r.get("result"), str(r.get("t")), r.get("ticks"), r.get("crisis_ticks"))
            cands = by_triple.get(triple, [])
            if len(cands) == 1:
                rec["review_no"], rec["match"] = cands[0], "report-triple"
            elif cands:
                rec["match"] = "ambiguous:%s" % ",".join(str(c) for c in sorted(cands))
        links[d.name] = rec
    if not dry:
        write_json(OUT / "run-links.json",
                   {"_provenance": "由 scripts/build_dataset.py 生成: run 目录 → 复盘流水号"
                                   "（game.json 权威链接优先, 历史 run 用 report 三元组精确匹配;"
                                   " ambiguous 不猜, 留人工）",
                    "links": links}, dry)
    return links


def backfill_legacy(manifest, dry):
    """Games 1-65: global event-stream slices + manually verified mapping (existing assets; existing
    results are never rewritten)."""
    segs = split_segments()

    # 1-22: legacy/official 元数据层
    for g in range(1, 23):
        result, dur, note = LEGACY[g]
        meta = {"game": g, "kind": "game-legacy",
                "date": "2026-09-20~21" if g <= 20 else "2026-09-21",
                "era": "legacy-bot" if g <= 20 else "official-player",
                "result": result, "duration_s": dur,
                "tier": "legacy-meta", "note": note,
                "raw": "artifacts/logs/bot.log (旧架构行日志, 未结构化)"}
        d = OUT / ("game-%04d" % g)
        if not dry:
            d.mkdir(exist_ok=True)
        write_json(d / "meta.json", meta, dry)
        manifest.append(meta)

    # 23-44: 事件流层
    for idx, events in enumerate(segs):
        g = SEG_MAP.get(idx)
        if g is None:
            d = OUT / "unattributed"
            if not dry:
                d.mkdir(exist_ok=True)
            write_jsonl(d / ("seg-%d-events.jsonl" % idx), events, dry)
            continue
        sm = seg_meta(events)
        result = sm.get("result")
        tier = "rl-trajectory" if result else "partial"
        note = ""
        if g == 29:
            tier = "partial"
            note = REVIEW_DEGRADED[29]
        if g == 32:
            result = "victory"
            note = "结算屏被客户端重载跳过, 由进攻态势+敌全歼推断（第32局复盘）"
        d = OUT / ("game-%04d" % g)
        if not dry:
            d.mkdir(exist_ok=True)
        meta = {"game": g, "kind": "game-events",
                "date": "2026-09-26" if g <= 26 else ("2026-09-27" if g <= 33 else "2026-09-28"),
                "era": "self-contained", "result": result,
                "duration_s": sm.get("duration_s"), "ticks": sm.get("ticks"),
                "tier": tier, "policy": sm.get("policy"),
                "events_count": sm["events_count"],
                "event_kinds": sm["event_kinds"], "note": note}
        write_json(d / "meta.json", meta, dry)
        write_jsonl(d / "events.jsonl", events, dry)
        if g in REVIEW_MAP:
            copy_file(GAMES / ("game-%s-review.md" % REVIEW_MAP[g]), d / "review.md", dry)
        if g in RUNLOG_MAP:
            copy_file(LOGS / RUNLOG_MAP[g], d / "run.log", dry)
        manifest.append(meta)

    # 45-65: run 目录层（完整 SFT 元组）
    for g, run_name in RUN_GAMES.items():
        run = GAMES / run_name
        if not run.exists():
            continue
        d = OUT / ("game-%04d" % g)
        if not dry:
            d.mkdir(exist_ok=True)
        evs = read_jsonl(run / "events.jsonl")
        sm = seg_meta(evs)
        n_sft = len(read_jsonl(run / "decisions.jsonl"))
        meta = {"game": g, "kind": "game-run", "date": "2026-09-29", "era": "self-contained",
                "result": sm.get("result"), "duration_s": sm.get("duration_s"),
                "ticks": sm.get("ticks"), "tier": "sft-full" if n_sft else "partial",
                "policy": sm.get("policy"), "events_count": len(evs),
                "event_kinds": sm.get("event_kinds"), "sft_tuples": n_sft,
                "run": run_name,
                "note": "完整 (state,questions,answers) SFT 元组" if n_sft else "run 无终局报告"}
        write_json(d / "meta.json", meta, dry)
        write_jsonl(d / "events.jsonl", evs, dry)
        if n_sft:
            copy_file(run / "decisions.jsonl", d / "decisions.jsonl", dry)
        if (run / "report.json").exists():
            copy_file(run / "report.json", d / "report.json", dry)
        if g in REVIEW_MAP:
            copy_file(GAMES / ("game-%s-review.md" % REVIEW_MAP[g]), d / "review.md", dry)
        manifest.append(meta)


# ================= B. 增量并入（每局 run 目录） =================

def ingest_runs(manifest, links, dry):
    """Register each artifacts/games/run-*/ as an index entry under dataset/runs/<run>/ (idempotent).

    Criterion = the run dir carries a payload (events.jsonl / decisions.jsonl). A game that ended
    with a terminal report gets tier sft-full; a run terminated externally (no report.json: user
    stop, stall guard, killed process) is still a training asset -- its (state,questions,answers)
    tuples are complete and only the outcome label is missing -- so it is ingested as tier
    `partial` with result=null. Only a run with no payload at all is skipped (nothing to train on).

    Only meta.json + review.md (small text) are written; the payloads (events/decisions/report) are
    **not copied** -- meta.source_dir points at artifacts/games/<run>/ (single source, avoiding two
    copies of multi-MB decisions.jsonl inside the repository -- public-repo size considerations).
    """
    ingested, partial_nodes, empty = 0, [], []
    runs_dir = OUT / "runs"
    for d in sorted(GAMES.glob("run-*")):
        rec = links.get(d.name, {"review_no": None, "match": "none"})
        evs = read_jsonl(d / "events.jsonl")
        n_sft = len(read_jsonl(d / "decisions.jsonl"))
        report = d / "report.json"
        if not evs and not n_sft:
            empty.append(d.name)
            continue
        rep = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
        dest = runs_dir / d.name
        if not dry:
            dest.mkdir(parents=True, exist_ok=True)
        rev_no = rec["review_no"]
        rev_file = "game-%04d-review.md" % rev_no if rev_no else None
        terminal = report.exists()
        if terminal:
            tier = "sft-full" if n_sft else "partial"
            note = "索引条目: 载荷在 source_dir（不重复存储）; 局号口径见 dataset/README.md"
        else:
            tier = "partial"
            note = ("无终局 report.json（对局被外部终止: 用户叫停/停摆守卫/进程被杀）——"
                    "事件流与 (state,questions,answers) 元组完整, 无胜负标签"
                    + ("; 复盘 %s 记为 unknown" % rev_file if rev_file else ""))
            partial_nodes.append(d.name)
        meta = {"run": d.name, "kind": "run-ingest",
                "review_no": rev_no,             # 流水号（artifacts/games 命名口径）
                "review_file": rev_file,          # 该局复盘文件（有则指向）
                "review_link": rec["match"],      # game.json | report-triple | ambiguous:… | none
                "source_dir": "artifacts/games/%s" % d.name,   # 载荷单一来源
                "payloads": [p for p in ("events.jsonl", "decisions.jsonl", "report.json")
                             if (d / p).exists()],
                "terminal_report": terminal,      # False = 外部终止, 无胜负标签
                "result": rep.get("result"), "t": rep.get("t"),
                "ticks": rep.get("ticks"), "crisis_ticks": rep.get("crisis_ticks"),
                "stance": rep.get("stance"), "ts": rep.get("ts"),
                "sft_tuples": n_sft, "events_count": len(evs),
                "tier": tier, "note": note}
        write_json(dest / "meta.json", meta, dry)
        if rev_no and rev_file:
            copy_file(GAMES / rev_file, dest / "review.md", dry)
        manifest.append(meta)
        ingested += 1
    return ingested, partial_nodes, empty


# ================= 入口 =================

def main(argv=None):
    ap = argparse.ArgumentParser(description="构建 dataset/ 训练数据资产（幂等）")
    ap.add_argument("--check", action="store_true", help="只报告, 不写盘")
    ap.add_argument("--skip-legacy", action="store_true", help="跳过 1-65 局历史回填")
    args = ap.parse_args(argv)
    dry = args.check

    if not dry:
        OUT.mkdir(parents=True, exist_ok=True)
    links = link_runs(dry)
    manifest = []
    if not args.skip_legacy:
        backfill_legacy(manifest, dry)
    n_ingest, partial_nodes, empty = ingest_runs(manifest, links, dry)

    # 排序: game-NNNN 在前（按局号）, run 条目在后（按 run 名）
    def sort_key(m):
        return (1, m["run"]) if m.get("kind") == "run-ingest" else (0, "%04d" % m.get("game", 0))
    manifest.sort(key=sort_key)
    if not dry:
        with open(OUT / "MANIFEST.jsonl", "w", encoding="utf-8") as f:
            for m in manifest:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

    tiers, results = {}, {}
    for m in manifest:
        tiers[m["tier"]] = tiers.get(m["tier"], 0) + 1
        results[m["result"]] = results.get(m["result"], 0) + 1
    unmatched = [n for n, r in links.items() if r["review_no"] is None]
    ambiguous = [n for n, r in links.items() if str(r["match"]).startswith("ambiguous")]
    print("dataset %s: %d 条 (历史 %d + run 增量 %d) | tiers=%s | results=%s"
          % ("[check]" if dry else "生成完毕", len(manifest),
             len(manifest) - n_ingest, n_ingest, tiers, results))
    print("run 目录: %d 个 | 并入 dataset %d (无终局报告 partial %d%s) | 无载荷丢弃 %d" % (
        len(links), n_ingest, len(partial_nodes),
        (": " + ", ".join(partial_nodes[:3]) + ("…" if len(partial_nodes) > 3 else ""))
        if partial_nodes else "",
        len(empty)))
    print("run→复盘流水号: 已链 %d, 未链 %d%s%s" % (
        len(links) - len(unmatched), len(unmatched),
        (" | 歧义 %s" % ambiguous) if ambiguous else "",
        "" if dry else " → dataset/run-links.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
