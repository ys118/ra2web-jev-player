#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shadow eval: replay logged ra2web decisions against LOCAL clef-flash.

Replays (state, questions) tuples recorded in artifacts/games/run-*/decisions.jsonl
to the local llama.cpp systemone endpoint (default http://127.0.0.1:8085/v1),
and compares the model's answers with the Jev answers ALREADY STORED in the
log. It NEVER calls any remote API - Jev answers are historical records.

Usage:
  uv run python scripts/shadow_eval.py replay  [--limit N] [--port 8085]
  uv run python scripts/shadow_eval.py analyze

Output: artifacts/shadow_eval/results.jsonl (+ report.md from analyze)
Resume: replay skips (run, line) pairs already present in results.jsonl.
"""
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "artifacts", "shadow_eval")
RESULTS = os.path.join(OUTDIR, "results.jsonl")
TARGET = 800          # sample size (requests), stratified per game file
PORT = 8085


def load_records():
    """All sft_tuple records, tagged with run name + era."""
    recs = []
    for path in sorted(glob.glob(os.path.join(ROOT, "artifacts", "games", "run-*", "decisions.jsonl"))):
        run = os.path.basename(os.path.dirname(path))
        era = "en" if run.split("-")[1] >= "20260930" else "early"
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("kind") != "sft_tuple" or not rec.get("state"):
                    continue
                rec["_key"] = "%s:%d" % (run, i)
                rec["_run"] = run
                rec["_era"] = era
                recs.append(rec)
    return recs


def sample(recs):
    """Proportional per-file stride sampling, ~TARGET records."""
    by_run = {}
    for r in recs:
        by_run.setdefault(r["_run"], []).append(r)
    n_total = len(recs)
    picked = []
    for run, rs in sorted(by_run.items()):
        want = max(2, round(TARGET * len(rs) / n_total))
        step = max(1, len(rs) // want)
        picked.extend(rs[step // 2::step])
    return picked[:]


def done_keys():
    if not os.path.exists(RESULTS):
        return set()
    keys = set()
    with open(RESULTS, encoding="utf-8") as fh:
        for line in fh:
            try:
                keys.add(json.loads(line)["_key"])
            except Exception:
                pass
    return keys


def ask(payload, port, retries=3):
    url = "http://127.0.0.1:%d/v1/systemone" % port
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {"error": "HTTP %d" % e.code}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {"error": str(e)}
    return {"error": "unreachable"}


def replay(argv):
    os.makedirs(OUTDIR, exist_ok=True)
    recs = sample(load_records())
    skip = done_keys()
    todo = [r for r in recs if r["_key"] not in skip]
    print("total logged records: sampled %d, already done %d, to replay %d"
          % (len(recs), len(skip), len(todo)))
    t0 = time.time()
    with open(RESULTS, "a", encoding="utf-8") as out:
        for n, rec in enumerate(todo, 1):
            resp = ask({"state": rec["state"], "questions": rec["questions"]}, PORT)
            row = {"_key": rec["_key"], "_run": rec["_run"], "_era": rec["_era"],
                   "t": rec.get("t"), "ts": rec.get("ts"),
                   "stance_before": rec.get("stance_before"),
                   "questions": {k: v.get("type") for k, v in rec["questions"].items()},
                   "jev": rec["answers"], "clef": resp.get("answers", resp)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            if n % 25 == 0 or n == len(todo):
                rate = n / max(time.time() - t0, 1)
                print("  %d/%d  (%.1f req/s, eta %.1f min)"
                      % (n, len(todo), rate, (len(todo) - n) / max(rate, 0.01) / 60))
    print("replay done ->", RESULTS)


# ---------------- analysis ----------------

def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if sx == 0 or sy == 0:
        return float("nan")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def analyze():
    rows = [json.loads(ln) for ln in open(RESULTS, encoding="utf-8") if ln.strip()]
    ok = [r for r in rows if isinstance(r["clef"], dict) and "error" not in r["clef"]]
    err = len(rows) - len(ok)
    L = []
    L.append("# Shadow eval: 本地 clef-flash vs 存档 Jev（%d 条重放，失败 %d）" % (len(rows), err))
    L.append("")
    for era in ("all", "en"):
        sub = ok if era == "all" else [r for r in ok if r["_era"] == "en"]
        if not sub:
            continue
        title = "全部样本" if era == "all" else "英文投喂时代（63局起，run>=20260930）"
        L.append("## %s（n=%d）" % (title, len(sub)))
        L.append("")
        # choice agreement per qid
        L.append("### choice 各题对齐率")
        L.append("")
        L.append("| qid | n | 答案对齐率 | Jev所选选项在clef下的概率 | conf平均差 |")
        L.append("|---|---|---|---|---|")
        for qid in ("build", "inf", "veh", "stance"):
            pairs = [r for r in sub if qid in r["jev"] and qid in r["clef"]
                     and r["jev"][qid].get("type") == "choice"
                     and r["clef"][qid].get("type") == "choice"]
            if not pairs:
                continue
            agree = sum(r["clef"][qid]["choice"] == r["jev"][qid]["choice"] for r in pairs)
            p_jev = [r["clef"][qid].get("probabilities", {}).get(r["jev"][qid]["choice"])
                     for r in pairs]
            p_jev = [p for p in p_jev if p is not None]
            cd = [abs(r["clef"][qid].get("confidence", 0) - r["jev"][qid].get("confidence", 0))
                  for r in pairs]
            L.append("| %s | %d | %.1f%% | %s | %.3f |" % (
                qid, len(pairs), 100.0 * agree / len(pairs),
                ("%.3f" % (sum(p_jev) / len(p_jev))) if p_jev else "-",
                sum(cd) / len(cd)))
        L.append("")
        # stance gate 0.45
        GATE = 0.45
        pairs = [r for r in sub if "stance" in r["jev"] and "stance" in r["clef"]
                 and r["jev"]["stance"].get("type") == "choice"]
        if pairs:
            def eff(r, side):
                a = r[side]["stance"]
                if a.get("confidence", 0) > GATE:
                    return a["choice"]
                return r["stance_before"]
            same = sum(eff(r, "clef") == eff(r, "jev") for r in pairs)
            jev_switch = [r for r in pairs
                          if r["jev"]["stance"]["confidence"] > GATE
                          and r["jev"]["stance"]["choice"] != r["stance_before"]]
            miss = sum(eff(r, "clef") == r["stance_before"] for r in jev_switch)
            jconf = [r["jev"]["stance"]["confidence"] for r in pairs]
            cconf = [r["clef"]["stance"].get("confidence", 0) for r in pairs]
            L.append("### stance 阈值 0.45 闸门")
            L.append("")
            L.append("- 生效态势一致率（含低置信沿用原态势的闸门语义）: **%.1f%%**（n=%d）"
                     % (100.0 * same / len(pairs), len(pairs)))
            L.append("- Jev 决定切态势 %d 次，clef 沿用原态势（漏切换）%d 次（%.1f%%）"
                     % (len(jev_switch), miss, 100.0 * miss / len(jev_switch) if jev_switch else 0))
            L.append("- confidence: Jev 均值 %.3f / clef 均值 %.3f（clef 若系统性偏低，"
                     "0.45 闸门将变保守，切换变少）" % (sum(jconf) / len(jconf), sum(cconf) / len(cconf)))
            L.append("")
        # threat 0.6
        pairs = [r for r in sub if "threat" in r["jev"] and "threat" in r["clef"]
                 and r["jev"]["threat"].get("type") == "noul"
                 and isinstance(r["clef"]["threat"], dict) and "noul" in r["clef"]["threat"]]
        if pairs:
            jn = [r["jev"]["threat"]["noul"] for r in pairs]
            cn = [r["clef"]["threat"]["noul"] for r in pairs]
            TH = 0.6
            fire_j = [x > TH for x in jn]
            fire_c = [x > TH for x in cn]
            both = sum(a and b for a, b in zip(fire_j, fire_c))
            miss = sum(a and not b for a, b in zip(fire_j, fire_c))
            false = sum(not a and b for a, b in zip(fire_j, fire_c))
            diffs = [c - j for j, c in zip(jn, cn)]
            L.append("### threat 阈值 0.6（强制回防触发）")
            L.append("")
            L.append("- noul 相关性 r = %.3f；平均偏差(clef-Jev) %+.3f；平均绝对偏差 %.3f"
                     % (pearson(jn, cn), sum(diffs) / len(diffs),
                        sum(abs(d) for d in diffs) / len(diffs)))
            L.append("- 0.6 阈值翻转率: **%.1f%%**（n=%d）" %
                     (100.0 * (miss + false) / len(pairs), len(pairs)))
            L.append("- 触发分布: 双方都触发 %d | Jev触发clef漏报 %d | clef误报 %d | 都不触发 %d"
                     % (both, miss, false, len(pairs) - both - miss - false))
            jn_ = sorted(jn)
            cn_ = sorted(cn)
            L.append("- 分位: Jev p50=%.3f p90=%.3f | clef p50=%.3f p90=%.3f" % (
                jn_[len(jn_) // 2], jn_[int(len(jn_) * 0.9)],
                cn_[len(cn_) // 2], cn_[int(len(cn_) * 0.9)]))
            L.append("")
        if era == "all":
            L.append("---")
            L.append("")
    report = os.path.join(OUTDIR, "report.md")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))
    print("\nreport ->", report)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "replay"
    if cmd == "replay":
        replay(sys.argv[2:])
    elif cmd == "analyze":
        analyze()
    else:
        print(__doc__)
