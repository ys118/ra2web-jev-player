@echo off
REM ============================================================
REM  通用对局启动器:  scripts\run_game.bat <局号>
REM  流程: preflight 自检(clef/webgl/会话/site, 全过才开打)
REM        -> uv run ra2web-jev-play -> artifacts\console\g<局号>_console.log
REM  说明: g72-g100 的历史脚本在 scripts\runs\ 保留存档;
REM        新局一律用本脚本, 控制台日志进入统一的 artifacts\console\。
REM ============================================================
setlocal
if "%~1"=="" (
  echo usage: scripts\run_game.bat ^<game_no^>   ^(example: scripts\run_game.bat 101^)
  exit /b 2
)
cd /d %~dp0..
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
set GN=%~1
if not exist artifacts\console mkdir artifacts\console
echo [g%GN%] preflight checking...
python scripts\preflight.py
if errorlevel 1 (
  echo [g%GN%] preflight BLOCKED - not launching
  exit /b 1
)
echo [g%GN%] preflight READY - launching
uv run ra2web-jev-play > artifacts\console\g%GN%_console.log 2>&1
echo [g%GN%] done (console log: artifacts\console\g%GN%_console.log)
