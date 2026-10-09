@echo off
cd /d D:\projects\ra2web-jev-player
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
uv run ra2web-jev-play > artifacts\console\g87_console.log 2>&1
