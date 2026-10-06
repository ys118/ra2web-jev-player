@echo off
cd /d D:\projects\ra2web-jev-player
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
echo [g89] preflight checking...
python out\preflight.py
if errorlevel 1 (
  echo [g89] preflight BLOCKED - not launching
  exit /b 1
)
echo [g89] preflight READY - launching
uv run ra2web-jev-play > out\g89_console.log 2>&1
