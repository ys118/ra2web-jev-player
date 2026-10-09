@echo off
cd /d D:\projects\ra2web-jev-player
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
echo [g92] preflight checking...
python scripts\preflight.py
if errorlevel 1 (
  echo [g92] preflight BLOCKED - not launching
  exit /b 1
)
echo [g92] preflight READY - launching
uv run ra2web-jev-play > artifacts\console\g92_console.log 2>&1
