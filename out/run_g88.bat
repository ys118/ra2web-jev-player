@echo off
cd /d D:\projects\ra2web-jev-player
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
echo [g88] preflight checking...
python out\preflight.py
if errorlevel 1 (
  echo [g88] preflight BLOCKED - not launching
  exit /b 1
)
echo [g88] preflight READY - launching
uv run ra2web-jev-play > out\g88_console.log 2>&1
