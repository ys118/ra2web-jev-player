# -*- coding: utf-8 -*-
"""仓库路径解析。

本项目是"仓库根运行"的工具：refs/knowledge/logs 等目录不打进 wheel。
从源码检出运行时，按 src 布局从本文件反推仓库根；
若包被安装到别处或目录挪动，用环境变量覆盖。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("JEV_PROJECT_ROOT")
    or Path(__file__).resolve().parents[2]  # src/ra2web_jev_player/paths.py -> 仓库根
)
LOG_DIR = Path(os.environ.get("JEV_LOG_DIR") or PROJECT_ROOT / "logs")
DOCS_DIR = Path(os.environ.get("JEV_DOCS_DIR") or PROJECT_ROOT / "refs" / "examples" / "jev")
KNOWLEDGE_DIR = Path(
    os.environ.get("JEV_KNOWLEDGE_DIR") or PROJECT_ROOT / "knowledge"
)
