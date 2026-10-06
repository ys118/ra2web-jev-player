@echo off
cd /d D:\projects\ra2web-jev-player
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
echo [g93] preflight checking...
python out\preflight.py
if errorlevel 1 (
  echo [g93] preflight BLOCKED - not launching
  exit /b 1
)
echo [g93] preflight READY - launching
uv run ra2web-jev-play > out\g93_console.log 2>&1
