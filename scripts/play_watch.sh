#!/bin/bash
# 站点恢复看护(最长3小时) → 恢复后自动开打第68局
cd /d/projects/ra2web-jev-player
for i in $(seq 1 90); do
  if uv run python out/site_probe.py >/dev/null 2>&1; then
    echo "[$(date +%H:%M:%S)] SITE_OK (try $i) -> launching game 68" 
    sleep 20   # 探测通过后再稳一下
    uv run python out/site_probe.py >/dev/null 2>&1 || { echo "flap, keep waiting"; sleep 120; continue; }
    uv run ra2web-jev-play
    exit $?
  fi
  echo "[$(date +%H:%M:%S)] still down (try $i)"
  sleep 120
done
echo "GIVE UP after 3h"
exit 1
