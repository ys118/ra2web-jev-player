# -*- coding: utf-8 -*-
"""回归场景脚本目录：不进 pytest 直接收集。

本目录的 ``*.py`` 是"文件即用例"的场景脚本（顶层执行 + sys.exit 报结果，
无 pytest 测试函数），若要被 pytest 收集会在 import 阶段触发 SystemExit。
它们由 ``tests/test_regression_suite.py`` 以子进程方式统一驱动：

    uv run pytest                                  # 全套回归
    uv run python tests/regression/test_xxx.py     # 单脚本直跑
"""
collect_ignore_glob = ["*.py"]
