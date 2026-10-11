# -*- coding: utf-8 -*-
"""后训练导出脚本的沙箱测试（不碰真实语料）。

在临时目录里造 3 个合成 run（Jev 时代有终局 / clef 时代无终局 / 只有事件流），
用子进程驱动 scripts/export_training.py，断言：
- SFT 按 run 切 train/val，样本是运行时信封（prompt=state+questions，completion=answers）；
- teacher 时代标注（无字段=jev，teacher=clef）与 --era 过滤；
- RL 轨迹的终局奖励（victory→1.0 / 无终局→null）与空轨迹跳过；
- DPO 对取自影子评测分歧（chosen=Jev, rejected=clef），prompt 回读自原 tuple；
- --check 不写盘。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_training.py"


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def _tuple(t, teacher=None, stance="develop"):
    rec = {"kind": "sft_tuple", "t": t, "ts": "2026-01-01 00:00:0%d" % (t % 10),
           "stance_before": stance,
           "state": {"battlefield": "bf %d" % t, "doctrine": "manual", "faction": "soviet",
                     "decision_request": "decide"},
           "questions": {"stance": {"type": "choice", "instructions": "pick", "criteria": {}},
                         "threat": {"type": "noul", "instructions": "level"}},
           "answers": {"stance": {"type": "choice", "choice": "develop",
                                  "probabilities": {"develop": 0.9}, "confidence": 0.9},
                       "threat": {"type": "noul", "noul": 0.1}}}
    if teacher:
        rec["teacher"] = teacher
    return rec


def _make_corpus(sbx):
    games = sbx / "games"
    # run A: Jev 时代（无 teacher 字段），有终局 report.json（victory）
    a = games / "run-20260101-000001"
    a.mkdir(parents=True)
    _write_jsonl(a / "decisions.jsonl", [_tuple(1), _tuple(50)])
    _write_jsonl(a / "events.jsonl", [
        {"kind": "start", "policy": "p/1.0", "ts": "00:00:00"},
        {"kind": "decision", "t": 1, "answers": {"stance": {"choice": "develop", "confidence": 0.9}},
         "ts": "00:00:01"},
        {"kind": "action", "what": "build", "name": "NAPOWR", "ts": "00:00:02"},
        {"kind": "obs", "t": 50, "credits": 800, "my_val": 100, "en_val": 200,
         "stance": "develop", "hostile": 1, "tanks": 0, "armor": 0, "aav": 0, "inf": 2,
         "harv": 1, "power_low": False, "ts": "00:00:50"},
        {"kind": "loss", "t": 60, "n": "E2", "ts": "00:01:00"},
        {"kind": "kill", "t": 70, "n": "ADOG", "ts": "00:01:10"},
        {"kind": "action", "what": "deploy", "ids": [7], "ts": "00:01:11"},
        {"kind": "report", "result": "victory", "t": 900, "ticks": 40, "crisis_ticks": 5,
         "stance": "attack", "ts": "00:15:00"},
    ])
    (a / "report.json").write_text(json.dumps(
        {"result": "victory", "t": 900, "ticks": 40, "crisis_ticks": 5, "stance": "attack"},
        ensure_ascii=False, indent=2), encoding="utf-8")
    # run B: clef 时代，无 report.json（外部终止）
    b = games / "run-20260101-000002"
    b.mkdir(parents=True)
    _write_jsonl(b / "decisions.jsonl", [_tuple(3, teacher="clef")])
    _write_jsonl(b / "events.jsonl", [
        {"kind": "start", "policy": "p/1.0", "ts": "00:00:00"},
        {"kind": "decision", "t": 3, "answers": {"stance": {"choice": "defend", "confidence": 0.4}},
         "ts": "00:00:03"},
        {"kind": "action", "what": "build", "name": "NAREFN", "ts": "00:00:04"},
    ])
    # run C: 只有 start（无决策步），应被 RL 跳过
    c = games / "run-20260101-000003"
    c.mkdir(parents=True)
    _write_jsonl(c / "events.jsonl", [{"kind": "start", "policy": "p/1.0", "ts": "00:00:00"}])
    # 影子评测：run A 第 0 条 stance 分歧（Jev=attack / clef=develop）
    _write_jsonl(sbx / "shadow.jsonl", [{
        "_key": "run-20260101-000001:0", "_run": "run-20260101-000001", "_era": "early",
        "t": 1, "ts": "2026-01-01 00:00:01", "stance_before": "develop",
        "questions": {"stance": "choice"},
        "jev": {"stance": {"type": "choice", "choice": "attack",
                           "probabilities": {"attack": 0.8}, "confidence": 0.8}},
        "clef": {"stance": {"type": "choice", "choice": "develop",
                            "probabilities": {"develop": 0.7}, "confidence": 0.5}},
    }])
    (sbx / "links.json").write_text(json.dumps(
        {"links": {"run-20260101-000001": {"review_no": 7, "match": "game.json"}}}),
        encoding="utf-8")
    return games


def _run(sbx, games, *extra, out_name="out"):
    out = sbx / out_name
    cmd = [sys.executable, str(SCRIPT), "--games-dir", str(games), "--out", str(out),
           "--links", str(sbx / "links.json"), "--shadow-eval", str(sbx / "shadow.jsonl"), *extra]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=str(ROOT), timeout=120), out


def test_export_training_end_to_end(tmp_path):
    sbx = tmp_path / "sbx"
    games = _make_corpus(sbx)
    proc, out = _run(sbx, games, "--val-every", "3")   # runs[::3] = 只有 run A 进验证集
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]

    train = [json.loads(x) for x in (out / "sft_train.jsonl").read_text(encoding="utf-8").splitlines()]
    val = [json.loads(x) for x in (out / "sft_val.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(train) == 1 and train[0]["meta"]["teacher"] == "clef"      # run B 进训练集
    assert len(val) == 2 and all(s["meta"]["teacher"] == "jev" for s in val)
    assert all(s["meta"]["result"] == "victory" for s in val)
    assert val[0]["meta"]["review_no"] == 7                              # links.json 生效
    assert val[0]["prompt"]["state"]["battlefield"] == "bf 1"            # 信封逐字保留
    assert "questions" in val[0]["prompt"] and "threat" in val[0]["completion"]
    assert val[0]["meta"]["schema"] == "stance+threat"

    # RL：run A 有终局奖励，run B 无标签，run C（无决策步）被跳过
    rl = [json.loads(x) for x in (out / "rl_trajectories.jsonl").read_text(encoding="utf-8").splitlines()]
    by_run = {r["run"]: r for r in rl}
    assert set(by_run) == {"run-20260101-000001", "run-20260101-000002"}
    assert by_run["run-20260101-000001"]["reward"] == 1.0
    assert by_run["run-20260101-000002"]["reward"] is None
    a = by_run["run-20260101-000001"]
    assert [s["t"] for s in a["steps"]] == [1, 50, 60, 70, 900]
    assert a["steps"][0]["actions"][0]["name"] == "NAPOWR"               # action 挂到本 tick
    assert a["steps"][1]["obs"]["credits"] == 800

    # DPO：chosen=Jev(attack) / rejected=clef(develop)，prompt 回读自原 tuple
    dpo = [json.loads(x) for x in (out / "dpo_pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(dpo) == 1
    assert dpo[0]["meta"]["qid"] == "stance"
    assert dpo[0]["chosen"]["choice"] == "attack" and dpo[0]["rejected"]["choice"] == "develop"
    assert dpo[0]["prompt"]["state"]["battlefield"] == "bf 1"

    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert stats["filters"]["val_every"] == 3
    assert stats["sft"]["train_samples"] == 1 and stats["sft"]["val_samples"] == 2
    assert stats["rl"]["runs"] == 2 and stats["rl"]["skipped_no_steps"] == ["run-20260101-000003"]
    assert (out / "README.md").is_file()

    # --era 过滤（SFT 与 RL 同时生效）+ 幂等（重跑覆盖，字节一致）
    proc2, _ = _run(sbx, games, "--era", "jev", "--val-every", "3")
    assert proc2.returncode == 0, proc2.stdout[-2000:]
    assert (out / "sft_train.jsonl").read_text(encoding="utf-8") == ""
    assert len([x for x in (out / "sft_val.jsonl").read_text(encoding="utf-8").splitlines()]) == 2
    stats2 = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert stats2["rl"]["runs"] == 1
    # clef 局被过滤；无 tuple 的 run 无法归属时代，一并排除
    assert set(stats2["rl"]["skipped_era"]) == {"run-20260101-000002", "run-20260101-000003"}
    proc3, _ = _run(sbx, games, "--val-every", "3")
    assert proc3.returncode == 0
    assert len([x for x in (out / "sft_train.jsonl").read_text(encoding="utf-8").splitlines()]) == 1

    # --check 不写盘
    proc4, out4 = _run(sbx, games, "--check", out_name="check_out")
    assert proc4.returncode == 0 and "[check]" in proc4.stdout
    assert not out4.exists()
