# -*- coding: utf-8 -*-
"""回归测试套件驱动：把 tests/regression/ 下的场景脚本逐个子进程执行。

场景脚本是历次迭代的"单变量离线测试"（喂 state 快照断言 planner/game 行为），
各自打印 PASS/FAIL 并以退出码报结果。本驱动把它们纳入 pytest 统一入口：

    uv run pytest                                   # 全部回归
    uv run pytest -k freeze                         # 单个场景
    uv run python tests/regression/test_freeze95.py  # 直接跑脚本（等价）

KNOWN_STALE 是与结构重构无关的历史陈旧断言（见 tests/README.md），标记 xfail
以便全套回归不被历史噪音染红，同时显式暴露"待人工核对"，不做静默跳过。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "tests" / "regression"

KNOWN_STALE = {
    "test_dog62.py": "第 62 局驻家名额断言(9 vs 10)与第 84/92 局 garrison 迭代冲突, 待人工核对",
    "test_gate.py": "断言日志文案'工厂前置位保护', 现行文案为'开局序列前置位保护'(第 67 局改名)",
}

SCRIPTS = sorted(REG.glob("test_*.py"))


def _tail(text: str, n: int = 25) -> str:
    lines = (text or "").strip().splitlines()
    return "\n".join(lines[-n:])


@pytest.mark.parametrize("script", SCRIPTS, ids=[p.name for p in SCRIPTS])
def test_scenario(script: Path):
    """场景脚本必须退出码 0（其内部逐条打印 PASS/FAIL）。"""
    if script.name in KNOWN_STALE:
        pytest.xfail(KNOWN_STALE[script.name])
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=900)
    assert proc.returncode == 0, (
        "场景失败 rc=%d\n--- stdout tail ---\n%s\n--- stderr tail ---\n%s"
        % (proc.returncode, _tail(proc.stdout), _tail(proc.stderr)))
