# -*- coding: utf-8 -*-
"""仓库布局与包契约守卫（结构重构后防漂移）。

这些断言把"目录布局/路径常量/对外 API"变成可执行契约：任何一次移动或改名
若忘了同步代码/文档，测试立即失败，而不是等到实战对局中途才炸。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 公开仓库只发布代码与文档；对局数据（artifacts/、dataset/）保持私有。
DATA_SHIPPED = (ROOT / "artifacts" / "games").is_dir() and \
    (ROOT / "dataset" / "MANIFEST.jsonl").is_file()

from ra2web_jev_player import paths  # noqa: E402
from ra2web_jev_player.strategy import doctrine, planner, state  # noqa: E402


def test_project_root_is_repo_root():
    assert paths.PROJECT_ROOT == ROOT


def test_layout_dirs_resolve_to_new_locations():
    """结构重构定稿布局（docs/LAYOUT.md）：路径常量必须落在新目录下。"""
    assert paths.LOG_DIR == ROOT / "artifacts" / "logs"
    assert paths.GAMES_DIR == ROOT / "artifacts" / "games"
    assert paths.CONSOLE_DIR == ROOT / "artifacts" / "console"
    assert paths.SCREENSHOTS_DIR == ROOT / "artifacts" / "screenshots"
    assert paths.DATASET_DIR == ROOT / "dataset"
    assert paths.DOCS_DIR == ROOT / "docs"
    assert paths.KNOWLEDGE_DIR == ROOT / "docs" / "knowledge"
    assert paths.LESSONS_PATH == ROOT / "docs" / "LESSONS.md"
    assert paths.DOCTRINE_OVERRIDES_PATH == ROOT / "docs" / "knowledge" / "doctrine.json"
    assert paths.REFERENCES_DIR == ROOT / "references"
    assert paths.WERHD_REF_DIR == ROOT / "references" / "werhd"
    assert paths.RESEARCH_DIR == ROOT / "references" / "research"


def test_data_dirs_exist_and_are_not_empty():
    """数据资产目录必须在位（红线：禁删/禁清空）。

    仅在维护者的完整检出里断言：公开仓库只发布代码与文档，对局数据
    （artifacts/、dataset/）保持私有，因此公开检出里该用例跳过。
    """
    if not DATA_SHIPPED:
        pytest.skip("match data is kept private and is not shipped in the public repository")
    assert (ROOT / "dataset" / "MANIFEST.jsonl").is_file()
    assert any((ROOT / "artifacts" / "games").glob("game-*-review.md"))
    assert (ROOT / "artifacts" / "logs" / "bot.log").is_file()
    assert (ROOT / "references" / "research" / "rules.ini").is_file()


def test_shipped_docs_and_derived_data_present():
    """公开检出也必须具备的东西：派生知识库、参考文档与数据目录说明。"""
    assert (ROOT / "docs" / "knowledge" / "RA2-BIBLE.md").is_file()
    assert (ROOT / "docs" / "knowledge" / "RA2-UNITS.json").is_file()
    assert (ROOT / "references" / "werhd" / "player-console-api.md").is_file()
    assert (ROOT / "artifacts" / "README.md").is_file()
    assert (ROOT / "dataset" / "README.md").is_file()


def test_knowledge_unit_db_loads():
    """RA2-UNITS.json 必须真的加载到（空库会让 ucost 全 0、债务闸失效）。"""
    assert len(state.UDB) > 50
    assert state.ucost("HARV") == 1400
    assert state.ucost("HTNK") == 900
    assert state.nm("HTNK") == "犀牛坦克"


def test_doctrine_counters_no_duplicate_keys():
    """COUNTERS 不应有重复键（历史上 special_1 被英文行静默覆盖过）。"""
    assert "special_1" in doctrine.COUNTERS
    assert doctrine.COUNTERS["special_1"][0][1].startswith("动员兵")


def test_planner_public_api_stable():
    """planner 拆包后对外 API 保持（game.py/回归测试按名调用）。"""
    for name in ("BattleMemory", "checklist", "movement", "apply_jev", "scouting",
                 "opening_build", "build_gate", "opening_next_code", "sense_events",
                 "crisis_response", "stance_overrides", "assign_squads", "forward_post",
                 "update_enemy_base", "v3_threat_active", "contact_edge", "shadow_target",
                 "kill_freeze", "myval_zero", "_hold_posts", "_OPENING_LEGACY"):
        assert hasattr(planner, name), name
    assert planner.T is doctrine.T          # 覆盖值(dict)必须同一对象
    assert planner.get_side is doctrine.get_side


def test_review_package_paths_point_into_artifacts():
    from ra2web_jev_player import review
    assert review.GAMES_DIR == paths.GAMES_DIR
    assert review.inputs.GAMES_DIR == paths.GAMES_DIR
    assert review.emit.GAMES_DIR == paths.GAMES_DIR
    assert review.tuning.OVERRIDES_PATH == paths.DOCTRINE_OVERRIDES_PATH


def test_version_consistent_between_package_and_pyproject():
    """pyproject 与 __init__.__version__ 必须一致（防两处漂移）。"""
    import ra2web_jev_player
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', text, re.M)
    assert m, "pyproject.toml 里找不到 version"
    assert ra2web_jev_player.__version__ == m.group(1)


def test_entrypoint_module_is_safe_without_args():
    """python -m ra2web_jev_player 无参不得发起对局（只打印用法）。"""
    import subprocess
    proc = subprocess.run([sys.executable, "-m", "ra2web_jev_player"], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
    assert proc.returncode == 0
    assert "ra2web-jev-play" in proc.stdout
