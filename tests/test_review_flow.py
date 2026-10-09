# -*- coding: utf-8 -*-
"""复盘链路端到端（离线沙箱）：events → 确定性分析 → 语义复盘 → 产出 → 局号链接。

不碰真实数据：子进程里用 JEV_* 环境变量把 artifacts/docs 指到临时目录，
用一个 stub 决策客户端（.ask 返回固定答案）替掉模型调用。
覆盖点：
- `review/analyze.py` 的错误指纹分支（历史缺陷：漏 `import re` → 有 ERR 行时 NameError）；
- `write_review_md` / `append_lessons` / `auto_tune` 写盘（含 doctrine.json 限幅）；
- `link_run_dir` 在 run 目录写 `game.json`（dataset 增量并入的链接来源）。
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import json, os, sys
from pathlib import Path

from ra2web_jev_player import review
from ra2web_jev_player.paths import ARTIFACTS_DIR, DOCS_DIR, GAMES_DIR, LOG_DIR

assert str(ARTIFACTS_DIR).startswith(os.environ["SANDBOX"]), ARTIFACTS_DIR
assert str(DOCS_DIR).startswith(os.environ["SANDBOX"]), DOCS_DIR

# ---- 造一局的 run 目录 + 全局 bot.log（含一行 ERR 触发错误指纹分支）----
run = GAMES_DIR / "run-20260101-000000"
run.mkdir(parents=True)
events = [
    {"kind": "start", "ts": "00:00:00", "policy": "ra2web-jev-player/1.0"},
    {"kind": "action", "ts": "00:00:01", "what": "produce", "name": "NAPOWR", "qty": 1},
    {"kind": "loss", "ts": "00:00:02", "t": 100, "n": "E2"},
    {"kind": "obs", "ts": "00:00:03", "t": 300, "credits": 150, "my_val": 200,
     "en_val": 900, "stance": "defend", "hostile": 3, "tanks": 1, "armor": 0, "aav": 0,
     "inf": 4, "harv": 1, "power_low": False},
    {"kind": "report", "ts": "00:00:04", "result": "defeat", "t": 900, "ticks": 40,
     "crisis_ticks": 20, "stance": "defend", "jev": {"decisions": 5, "errors": 0,
     "p50_ms": 900, "p95_ms": 1200, "input_tokens": 1, "output_tokens": 1},
     "enemy_base": None},
]
(run / "events.jsonl").write_text(
    "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
(run / "report.json").write_text(json.dumps(events[-1], ensure_ascii=False), encoding="utf-8")
LOG_DIR.mkdir(parents=True, exist_ok=True)
(LOG_DIR / "bot.log").write_text(
    "=== ra2web-jev-player start (tick=1.5s, max_decisions=999999) ===\n"
    "t=45 OPENING BUILD NAPOWR\n"
    "t=120 scout ERR boom\n"
    "t=130 scout ERR boom\n"
    "t=900 REVIEW game#1 defeat\n", encoding="utf-8")

# ---- stub 决策客户端：只提供 .ask，返回固定语义复盘答案 ----
class StubJev:
    backend = "stub"
    def ask(self, state, questions, timeout=40):
        assert "对局结果" in state
        return {
            "rootcause": {"type": "choice", "choice": "starve", "confidence": 0.9},
            "topfix": {"type": "choice", "choice": "boost_econ", "confidence": 0.8},
            "tune": {"type": "noul", "noul": 0.8, "confidence": 0.8},
        }

out = review.review_last_game(StubJev(), None, game_no=1)

# ---- 断言产出 ----
md = Path(out["review_path"])
assert md.name == "game-0001-review.md" and md.parent == GAMES_DIR, md
text = md.read_text(encoding="utf-8")
assert "第 1 局复盘" in text and "确定性发现" in text, text[:200]
assert "scout ERR ×2" in text, "错误指纹分支必须命中(历史 NameError 缺陷点)"
assert "参数迭代" in text, text[:400]

lessons = (DOCS_DIR / "LESSONS.md").read_text(encoding="utf-8")
assert "## 第 1 局" in lessons and "已自动调参" in lessons

doc = json.loads((DOCS_DIR / "knowledge" / "doctrine.json").read_text(encoding="utf-8"))
assert doc["T"]["tank_cash1"] == 900, doc["T"]          # 1000 + (-100) 限幅内
assert doc["T"]["tank_cash2"] == 1200, doc["T"]         # 1400 + (-200)
assert doc["history"][-1]["game"] == 1

link = json.loads((run / "game.json").read_text(encoding="utf-8"))
assert link["game_no"] == 1 and link["review"] == "game-0001-review.md", link

# ---- 幂等性：再来一次仍可跑（复盘按局号追加, 不炸）----
review.review_last_game(StubJev(), None, game_no=2)
assert (GAMES_DIR / "game-0002-review.md").exists()
print("REVIEW-FLOW-OK")
'''


def test_review_flow_end_to_end(tmp_path):
    sandbox = tmp_path / "sbx"
    env = dict(
        **__import__("os").environ,
        JEV_PROJECT_ROOT=str(ROOT),
        JEV_ARTIFACTS_DIR=str(sandbox / "artifacts"),
        JEV_DOCS_DIR=str(sandbox / "docs"),
        JEV_GAMES_DIR=str(sandbox / "artifacts" / "games"),
        JEV_LOG_DIR=str(sandbox / "artifacts" / "logs"),
        SANDBOX=str(sandbox),
        PYTHONPATH=str(ROOT / "src"),
    )
    (sandbox / "docs" / "knowledge").mkdir(parents=True)
    proc = subprocess.run([sys.executable, "-c", textwrap.dedent(SCRIPT)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, cwd=str(ROOT), timeout=300)
    assert proc.returncode == 0, "rc=%d\n%s\n%s" % (proc.returncode, proc.stdout[-3000:], proc.stderr[-3000:])
    assert "REVIEW-FLOW-OK" in proc.stdout
