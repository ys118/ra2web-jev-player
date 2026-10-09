# -*- coding: utf-8 -*-
"""仓库路径解析（全项目唯一的路径常量来源）。

本项目是"仓库根运行"的工具：artifacts/dataset/docs/references 等目录不打进
wheel。从源码检出运行时，按 src 布局从本文件反推仓库根；若包被安装到别处或
目录挪动，用环境变量覆盖。

仓库布局（2026-10-09 结构重构定稿, 详见 docs/LAYOUT.md）::

    artifacts/          # 运行时产物: 日志/每局存档/截图/控制台输出 (原 logs/ + out/)
      ├─ logs/          #   bot.log · jev-events.jsonl · 进程 stdout
      ├─ games/         #   每局数据资产: game-XXXX-review.md · run-<ts>/
      ├─ console/       #   对局控制台日志 (gNN_console.log)
      └─ screenshots/
    dataset/            # 训练数据资产 (SFT/RL, 见 dataset/README.md)
    docs/               # 全部文档; docs/knowledge/ = 攻略与作战手册
    references/         # 参考资料: references/werhd/ (API+示例) · research/ (数据挖掘)
    scripts/            # 仓库级运维/数据脚本
    src/ra2web_jev_player/  # Python 包
    tests/              # 回归测试
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
