#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export the match corpus into post-training files (SFT / RL / DPO).

Source of truth = the per-run archives under ``artifacts/games/run-*/`` (decisions.jsonl,
events.jsonl, report.json). This script deliberately reads the run directories instead of
``dataset/runs/`` + ``dataset/game-NNNN``, because those two zones overlap for matches 45-65
(see dataset/README.md) and walking them naively double-counts the corpus.

Contract note: a decision sample is the verbatim runtime envelope --

    request   {"state": <rendered prompt sections>, "questions": {qid: {type, instructions, criteria}}}
    response  {qid: {choice, probabilities, confidence} | {noul}}

i.e. exactly the JSON the bot posts to ``/v1/systemone`` (src/ra2web_jev_player/jev/client.py).
Do not re-render or re-template it: train/serve skew comes from exactly that.

Teacher eras (docs/CLEF-LOCAL.md §8.2): a tuple without a ``teacher`` field is a Jev-era
product (matches 45-69, the strong teacher); ``teacher == "clef"`` is the local model signing
its own answers (match 70 onwards). Train on the first for distillation, on the second for
behaviour cloning.

Outputs under ``--out`` (default ``dataset/export/``, gitignored: derived data, regenerate
instead of committing):

    sft_train.jsonl / sft_val.jsonl   prompt-completion samples, split BY RUN (no in-match leak)
    rl_trajectories.jsonl             one run per line: step list + terminal reward
    dpo_pairs.jsonl                   preference pairs from artifacts/shadow_eval/results.jsonl
    stats.json                        counts, length percentiles, distributions
    README.md                         generated: what this directory is + how to reproduce it

Usage:
  uv run python scripts/export_training.py                        # full corpus, both eras
  uv run python scripts/export_training.py --era jev --out dataset/export/jev
  uv run python scripts/export_training.py --min-conf 0.6
  uv run python scripts/export_training.py --check                # report only, write nothing

See ``docs/TRAINING.md`` for the recipe (which subset to train first, how to evaluate).
"""
import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "artifacts" / "games"
LINKS = ROOT / "dataset" / "run-links.json"
SHADOW = ROOT / "artifacts" / "shadow_eval" / "results.jsonl"
OUT = ROOT / "dataset" / "export"

CHOICE_QIDS = ("build", "stance", "inf", "veh")
STEP_KINDS = {"decision", "obs", "loss", "kill", "report"}   # carry a game-second `t`
ATTACH_KINDS = {"action", "produce_skip"}                    # belong to the tick before them
OBS_FIELDS = ("credits", "my_val", "en_val", "stance", "hostile",
              "tanks", "armor", "aav", "inf", "harv", "power_low")


def read_jsonl(path):
    """Stream a jsonl file, skipping blank/malformed lines."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_json_doc(path):
    """Read a single (pretty-printed) JSON document such as report.json."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_links(path=None):
    """run -> review_no (the dataset's audited alignment table)."""
    try:
        links = json.loads((path or LINKS).read_text(encoding="utf-8"))["links"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}
    return {run: rec.get("review_no") for run, rec in links.items()}


def list_runs(games_dir):
    """Chronological (name-sorted) run inventory: tuples count, terminal report, teacher era.

    A run's tuples all come from one backend (the Jev→clef switch happened between runs), so the
    first tuple's ``teacher`` field fixes the run's era without reading the whole file.
    """
    runs = []
    for d in sorted(games_dir.glob("run-*")):
        dec = d / "decisions.jsonl"
        n = sum(1 for _ in read_jsonl(dec)) if dec.exists() else 0
        first = next(read_jsonl(dec), None) if n else None
        runs.append({"run": d.name, "dir": d, "tuples": n,
                     "report": (d / "report.json").exists(),
                     "teacher": teacher_of(first) if first else None})
    return runs


def teacher_of(rec):
    """Era label per docs/CLEF-LOCAL.md §8.2: missing teacher field == Jev era."""
    return "clef" if rec.get("teacher") == "clef" else "jev"


def conf_min(answers):
    """Minimum confidence over choice slots (noul slots carry no confidence)."""
    vals = [a.get("confidence") for a in answers.values()
            if isinstance(a, dict) and a.get("confidence") is not None]
    return min(vals) if vals else None


def null_choice_qids(answers):
    return [q for q, a in answers.items()
            if isinstance(a, dict) and a.get("type") == "choice" and not a.get("choice")]


def make_sample(run, idx, rec, meta):
    return {"id": "%s:%d" % (run, idx),
            "prompt": {"state": rec["state"], "questions": rec["questions"]},
            "completion": rec["answers"],
            "meta": meta}


# ---------------- SFT ----------------

def export_sft(runs, args, links, dry):
    """Stream each eligible run's decisions.jsonl into sft_train/sft_val (split BY RUN).

    The val split is computed over the runs that actually contribute under the active filters
    (era), so ``--era jev`` holds out ~1/5 of the Jev-era runs rather than 1/5 of all runs.
    """
    eligible = [r for r in runs if r["tuples"] > 0
                and (args.era == "all" or r["teacher"] == args.era)]
    val_runs = set(r["run"] for r in eligible[::args.val_every]) if args.val_every > 0 else set()
    if args.val_runs:
        val_runs = set(args.val_runs.split(","))
    out = {"filters": {"era": args.era, "min_conf": args.min_conf,
                       "drop_null_choice": args.drop_null_choice,
                       "val_every": args.val_every, "val_runs": sorted(val_runs)},
           "train": [], "val": [], "samples": 0, "chars": [], "skipped": {},
           "teacher": {}, "qids": {}, "results": {}, "conf_min": [], "null_choice": 0}
    for r in runs:
        if r["tuples"] == 0:
            out["skipped"]["no_tuples_run"] = out["skipped"].get("no_tuples_run", 0) + 1
        elif args.era != "all" and r["teacher"] != args.era:
            out["skipped"]["run_era_filter"] = out["skipped"].get("run_era_filter", 0) + 1
    fh = {}
    if not dry:
        fh["train"] = open(args.out / "sft_train.jsonl", "w", encoding="utf-8")
        fh["val"] = open(args.out / "sft_val.jsonl", "w", encoding="utf-8")
    for r in eligible:
        run, d = r["run"], r["dir"]
        report = read_json_doc(d / "report.json") or {}
        n_run = 0
        for idx, rec in enumerate(read_jsonl(d / "decisions.jsonl")):
            if not rec.get("state") or not rec.get("questions") or not rec.get("answers"):
                out["skipped"]["incomplete_record"] = out["skipped"].get("incomplete_record", 0) + 1
                continue
            teacher = teacher_of(rec)
            if args.era != "all" and teacher != args.era:      # 防御: run 内混入异时代样本
                out["skipped"]["era_filter"] = out["skipped"].get("era_filter", 0) + 1
                continue
            cmin = conf_min(rec["answers"])
            nulls = null_choice_qids(rec["answers"])
            if nulls:
                out["null_choice"] += 1
                if args.drop_null_choice:
                    out["skipped"]["null_choice"] = out["skipped"].get("null_choice", 0) + 1
                    continue
            if args.min_conf > 0 and (cmin is None or cmin < args.min_conf):
                out["skipped"]["min_conf"] = out["skipped"].get("min_conf", 0) + 1
                continue
            meta = {"run": run, "review_no": links.get(run), "t": rec.get("t"),
                    "stance_before": rec.get("stance_before"), "teacher": teacher,
                    "result": report.get("result"), "terminal_report": bool(report),
                    "schema": "+".join(q for q in CHOICE_QIDS if q in rec["questions"])
                              + ("+threat" if "threat" in rec["questions"] else ""),
                    "conf_min": cmin}
            line = json.dumps(make_sample(run, idx, rec, meta), ensure_ascii=False)
            if not dry:
                fh["val" if run in val_runs else "train"].write(line + "\n")
            n_run += 1
            out["chars"].append(len(line))
            if cmin is not None:
                out["conf_min"].append(cmin)
            out["teacher"][teacher] = out["teacher"].get(teacher, 0) + 1
            for q in rec["questions"]:
                out["qids"][q] = out["qids"].get(q, 0) + 1
            if report:
                out["results"][report.get("result")] = out["results"].get(report.get("result"), 0) + 1
        out["val" if run in val_runs else "train"].append({"run": run, "samples": n_run})
        out["samples"] += n_run
    for handle in fh.values():
        handle.close()
    return out


# ---------------- RL ----------------

def build_steps(events):
    """Group the event stream into per-tick steps.

    Rule: every event carrying a game-second `t` (decision / obs / loss / kill / report) opens a
    new step; `action` / `produce_skip` events attach to the newest step (they belong to the tick
    that just decided). Wall-clock `ts` is dropped (the run name already fixes the date/time).
    """
    steps = []
    for e in events:
        kind = e.get("kind")
        if kind in STEP_KINDS:
            step = {"t": e.get("t")}
            if kind == "decision":
                step["decision"] = e.get("answers")
            elif kind == "obs":
                step["obs"] = {k: e.get(k) for k in OBS_FIELDS if k in e}
            elif kind in ("loss", "kill"):
                step[kind] = e.get("n")
            elif kind == "report":
                step["report"] = {k: e.get(k) for k in
                                  ("result", "t", "ticks", "crisis_ticks", "stance", "enemy_base")
                                  if k in e}
            steps.append(step)
        elif kind in ATTACH_KINDS and steps:
            key = "actions" if kind == "action" else "produce_skip"
            item = {k: v for k, v in e.items() if k not in ("kind", "ts")}
            steps[-1].setdefault(key, []).append(item)
    return steps


def export_rl(runs, args, links, dry):
    out = {"runs": 0, "steps": 0, "decisions": 0, "actions": 0, "results": {},
           "skipped_no_steps": [], "skipped_era": []}
    fh = None if dry else open(args.out / "rl_trajectories.jsonl", "w", encoding="utf-8")
    for r in runs:
        d = r["dir"]
        events = list(read_jsonl(d / "events.jsonl"))
        if not events:
            continue
        first_tuple = next(read_jsonl(d / "decisions.jsonl"), None)
        teacher = r["teacher"] if r["teacher"] else (teacher_of(first_tuple) if first_tuple else None)
        if args.era != "all" and teacher != args.era:      # --era 对 RL 同样生效
            out["skipped_era"].append(r["run"])
            continue
        steps = build_steps(events)
        if not steps:
            out["skipped_no_steps"].append(r["run"])
            continue
        report = read_json_doc(d / "report.json") or \
            next((e for e in reversed(events) if e.get("kind") == "report"), None) or {}
        result = report.get("result")
        rec = {"run": r["run"], "review_no": links.get(r["run"]),
               "teacher": teacher,
               "result": result, "terminal_report": bool(r["report"]),
               "reward": 1.0 if result == "victory" else (0.0 if result == "defeat" else None),
               "t_end": report.get("t"), "ticks": report.get("ticks"),
               "crisis_ticks": report.get("crisis_ticks"),
               "n_steps": len(steps),
               "n_decisions": sum(1 for s in steps if "decision" in s),
               "n_actions": sum(len(s.get("actions", [])) for s in steps),
               "steps": steps}
        if fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out["runs"] += 1
        out["steps"] += len(steps)
        out["decisions"] += rec["n_decisions"]
        out["actions"] += rec["n_actions"]
        out["results"][result] = out["results"].get(result, 0) + 1
    if fh:
        fh.close()
    return out


# ---------------- DPO ----------------

def export_dpo(runs, args, links, dry):
    """Preference pairs from the shadow eval: chosen = archived Jev answer, rejected = clef's.

    results.jsonl rows carry ``_key = run:line``; the prompt is re-read from that run's
    decisions.jsonl, so the pair uses the byte-identical envelope of the original decision.
    """
    if not args.shadow_eval.exists():
        return {"pairs": 0, "by_qid": {}, "rows": 0, "note": "no shadow-eval results"}
    needed = {}
    rows = 0
    for row in read_jsonl(args.shadow_eval):
        clef = row.get("clef")
        if not isinstance(clef, dict) or "error" in clef:
            continue
        rows += 1
        run, _, idx = str(row.get("_key", "")).rpartition(":")
        if not run or not idx.isdigit():
            continue
        needed.setdefault(run, set()).add(int(idx))
    # read the referenced tuples (prompt side) per run
    prompts = {}
    for run, idxs in needed.items():
        for i, rec in enumerate(read_jsonl(args.games_dir / run / "decisions.jsonl")):
            if i in idxs:
                prompts["%s:%d" % (run, i)] = {"state": rec.get("state"),
                                               "questions": rec.get("questions")}
    out = {"rows": rows, "pairs": 0, "by_qid": {}}
    fh = None if dry else open(args.out / "dpo_pairs.jsonl", "w", encoding="utf-8")
    for row in read_jsonl(args.shadow_eval):
        clef, jev = row.get("clef"), row.get("jev")
        if not isinstance(clef, dict) or "error" in clef or not isinstance(jev, dict):
            continue
        prompt = prompts.get(str(row.get("_key")))
        if not prompt or not prompt["state"]:
            continue
        run = row.get("_run")
        for qid, c in clef.items():
            j = jev.get(qid)
            if not isinstance(c, dict) or not isinstance(j, dict):
                continue
            if c.get("type") != "choice" or j.get("type") != "choice":
                continue
            if not c.get("choice") or c.get("choice") == j.get("choice"):
                continue
            pair = {"id": "%s:%s" % (row.get("_key"), qid),
                    "prompt": prompt,
                    "chosen": j,        # Jev (teacher) answer
                    "rejected": c,      # clef (current model) answer
                    "meta": {"run": run, "review_no": links.get(run), "qid": qid,
                             "t": row.get("t"), "stance_before": row.get("stance_before"),
                             "era": row.get("_era"), "choice_jev": j.get("choice"),
                             "choice_clef": c.get("choice"),
                             "conf_jev": j.get("confidence"), "conf_clef": c.get("confidence")}}
            if fh:
                fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
            out["pairs"] += 1
            out["by_qid"][qid] = out["by_qid"].get(qid, 0) + 1
    if fh:
        fh.close()
    return out


# ---------------- reporting ----------------

def pct(values, p):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def write_docs(args, sft, rl, dpo, dry):
    cpt = args.chars_per_token
    stats = {
        "generated_by": "scripts/export_training.py",
        "source": "artifacts/games/run-*/ (run directories are the single source of truth)",
        "filters": sft["filters"],
        "sft": {"samples": sft["samples"],
                "train_runs": len(sft["train"]), "val_runs": len(sft["val"]),
                "train_samples": sum(r["samples"] for r in sft["train"]),
                "val_samples": sum(r["samples"] for r in sft["val"]),
                "teacher": sft["teacher"], "results": sft["results"], "qids": sft["qids"],
                "skipped": sft["skipped"], "samples_with_null_choice": sft["null_choice"],
                "line_chars": {"p50": pct(sft["chars"], 0.5), "p95": pct(sft["chars"], 0.95),
                               "max": max(sft["chars"]) if sft["chars"] else None},
                "est_tokens_per_sample": {"p50": round((pct(sft["chars"], 0.5) or 0) / cpt),
                                          "p95": round((pct(sft["chars"], 0.95) or 0) / cpt),
                                          "chars_per_token": cpt},
                "conf_min": {"p10": pct(sft["conf_min"], 0.1), "p50": pct(sft["conf_min"], 0.5),
                             "p90": pct(sft["conf_min"], 0.9),
                             "mean": round(statistics.mean(sft["conf_min"]), 3)
                             if sft["conf_min"] else None},
                "val_run_list": sorted(r["run"] for r in sft["val"])},
        "rl": rl,
        "dpo": dpo,
    }
    readme = [
        "# dataset/export — 后训练导出（派生数据，勿提交）",
        "",
        "本目录由 `uv run python scripts/export_training.py` 生成，**全部内容可随时重建**，",
        "因此被 `.gitignore` 忽略（原始语料在 `artifacts/games/run-*/`，索引在 `dataset/`）。",
        "",
        "| 文件 | 内容 |",
        "|---|---|",
        "| `sft_train.jsonl` / `sft_val.jsonl` | prompt-completion 样本（按 run 整局切分），"
        "格式见 `docs/TRAINING.md` §二 |",
        "| `rl_trajectories.jsonl` | 每局一行：逐 tick 的 decision/action/obs + 终局奖励 |",
        "| `dpo_pairs.jsonl` | 影子评测分歧处的偏好对（chosen=Jev，rejected=clef） |",
        "| `stats.json` | 计数、长度分位、teacher/胜负/问题集分布 |",
        "",
        "本次生成使用的过滤参数见 `stats.json` 的 `filters` 字段；复现命令：",
        "",
        "```bash",
        "uv run python scripts/export_training.py %s --out %s" % (
            " ".join(a for a in [
                "--era %s" % args.era if args.era != "all" else "",
                "--min-conf %g" % args.min_conf if args.min_conf else "",
                "--val-every %d" % args.val_every if args.val_every != 5 else "",
                "--drop-null-choice" if args.drop_null_choice else "",
            ] if a),
            args.out.relative_to(ROOT).as_posix() if str(args.out).startswith(str(ROOT)) else args.out),
        "```",
        "",
        "实施配方与评测门槛：`docs/TRAINING.md`。",
    ]
    if dry:
        return stats
    (args.out / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="把对局语料导出为后训练文件（SFT/RL/DPO）")
    ap.add_argument("--out", type=Path, default=OUT, help="输出目录（默认 dataset/export/）")
    ap.add_argument("--era", choices=("all", "jev", "clef"), default="all",
                    help="teacher 时代过滤: jev=无 teacher 字段的强教师局(45-69 局)")
    ap.add_argument("--min-conf", type=float, default=0.0,
                    help="样本级过滤: 任 choice 槽置信度低于该值即丢弃（默认 0=不过滤）")
    ap.add_argument("--drop-null-choice", action="store_true",
                    help="丢弃存在 choice=null 槽的样本（模型弃答/解析失败）")
    ap.add_argument("--val-every", type=int, default=5,
                    help="按 run 时序每 N 局留一局做验证集（0=不切分，全部进 train）")
    ap.add_argument("--val-runs", default=None, help="显式指定验证集 run 名（逗号分隔，覆盖 --val-every）")
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="token 估算用的字符/token 比（仅用于 stats 的长度估算）")
    ap.add_argument("--games-dir", type=Path, default=GAMES, help="run 目录根（默认 artifacts/games）")
    ap.add_argument("--links", type=Path, default=LINKS,
                    help="run→复盘流水号对齐表（默认 dataset/run-links.json）")
    ap.add_argument("--shadow-eval", type=Path, default=SHADOW,
                    help="影子评测结果（DPO 对来源，默认 artifacts/shadow_eval/results.jsonl）")
    ap.add_argument("--check", action="store_true", help="只统计不写盘")
    args = ap.parse_args(argv)
    dry = args.check

    runs = list_runs(args.games_dir)
    links = load_links(args.links)
    if not dry:
        args.out.mkdir(parents=True, exist_ok=True)
    sft = export_sft(runs, args, links, dry)
    rl = export_rl(runs, args, links, dry)
    dpo = export_dpo(runs, args, links, dry)
    stats = write_docs(args, sft, rl, dpo, dry)

    dest = "[check]" if dry else "→ %s" % args.out
    summary = json.dumps({
        "sft_samples": sft["samples"],
        "train": stats["sft"]["train_samples"], "val": stats["sft"]["val_samples"],
        "rl_runs": rl["runs"], "rl_steps": rl["steps"],
        "dpo_pairs": dpo["pairs"], "skipped": sft["skipped"],
    }, ensure_ascii=False)
    print("export %s: %s" % (dest, summary))
    if sft["chars"]:
        print("样本 P50 %.1fKB / P95 %.1fKB | 估算 token P50≈%s / P95≈%s | conf_min 均值 %s"
              % (pct(sft["chars"], 0.5) / 1024, pct(sft["chars"], 0.95) / 1024,
                 stats["sft"]["est_tokens_per_sample"]["p50"],
                 stats["sft"]["est_tokens_per_sample"]["p95"],
                 stats["sft"]["conf_min"]["mean"]))
    print("teacher: %s | 结果: %s | choice=null 样本: %d"
          % (sft["teacher"], sft["results"], sft["null_choice"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
