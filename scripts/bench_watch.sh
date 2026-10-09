#!/bin/bash
# 站点恢复看护 + 自动跑开局微基准(最长60分钟)
cd /d/projects/ra2web-jev-player
for i in $(seq 1 30); do
  if uv run python out/site_probe.py >/dev/null 2>&1; then
    echo "[$(date +%H:%M:%S)] SITE_OK after $i tries" > out/bench_result.txt
    uv run python out/bench_opening.py >> out/bench_result.txt 2>&1
    exit 0
  fi
  echo "[$(date +%H:%M:%S)] still down (try $i)" >> out/bench_result.txt
  sleep 120
done
echo "[$(date +%H:%M:%S)] GIVE UP after 60min" >> out/bench_result.txt
exit 1
