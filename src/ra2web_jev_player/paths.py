# -*- coding: utf-8 -*-
"""Repository path resolution (the project's single source of truth for path constants).

This project is a "run from the repository root" tool: directories such as artifacts/dataset/docs/references
are not packaged into the wheel. When running from a source checkout, the repository root is derived from
this file following the src layout; if the package is installed elsewhere or the directories move, override
with environment variables.

Repository layout (structure refactor finalized 2026-10-09, see docs/LAYOUT.md)::

    artifacts/          # runtime outputs: logs / per-game archives / screenshots / console (was logs/ + out/)
      ├─ logs/          #   bot.log · jev-events.jsonl · process stdout
      ├─ games/         #   per-game data assets: game-XXXX-review.md · run-<ts>/
      ├─ console/       #   match console logs (gNN_console.log)
      └─ screenshots/
    dataset/            # training data assets (SFT/RL, see dataset/README.md)
    docs/               # all documentation; docs/knowledge/ = strategy guides and battle manuals
    references/         # reference material: references/werhd/ (API + examples) · research/ (data mining)
    scripts/            # repository-level ops/data scripts
    src/ra2web_jev_player/  # Python package
    tests/              # regression tests
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("JEV_PROJECT_ROOT")
    or Path(__file__).resolve().parents[2]  # src/ra2web_jev_player/paths.py -> 仓库根
)

# ---------- 运行时产物（原 logs/ + out/ 合并） ----------
ARTIFACTS_DIR = Path(
    os.environ.get("JEV_ARTIFACTS_DIR") or PROJECT_ROOT / "artifacts"
)
LOG_DIR = Path(os.environ.get("JEV_LOG_DIR") or ARTIFACTS_DIR / "logs")
GAMES_DIR = Path(os.environ.get("JEV_GAMES_DIR") or ARTIFACTS_DIR / "games")
CONSOLE_DIR = ARTIFACTS_DIR / "console"
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"

# ---------- 训练数据 ----------
DATASET_DIR = Path(os.environ.get("JEV_DATASET_DIR") or PROJECT_ROOT / "dataset")

# ---------- 文档与知识 ----------
DOCS_DIR = Path(os.environ.get("JEV_DOCS_DIR") or PROJECT_ROOT / "docs")
KNOWLEDGE_DIR = Path(os.environ.get("JEV_KNOWLEDGE_DIR") or DOCS_DIR / "knowledge")
LESSONS_PATH = DOCS_DIR / "LESSONS.md"
DOCTRINE_OVERRIDES_PATH = KNOWLEDGE_DIR / "doctrine.json"

# ---------- 参考资料（原 refs/ + _research/ 合并） ----------
REFERENCES_DIR = Path(
    os.environ.get("JEV_REFERENCES_DIR") or PROJECT_ROOT / "references"
)
WERHD_REF_DIR = REFERENCES_DIR / "werhd"
RESEARCH_DIR = REFERENCES_DIR / "research"
