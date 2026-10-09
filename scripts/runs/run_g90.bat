@echo off
cd /d "%~dp0..\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
echo [g90] preflight checking...
python scripts\preflight.py
if errorlevel 1 (
  echo [g90] preflight BLOCKED - not launching
  exit /b 1
)
echo [g90] preflight READY - launching
uv run ra2web-jev-play > artifacts\console\g90_console.log 2>&1
