# artifacts — runtime artifacts (the old `logs/` + `out/` merged)

> **Red line: this directory is a data asset on par with `dataset/`; no historical content may be
> cleaned, overwritten or deleted** (see the "training-data assets" clause in `AGENTS.md`).
> Only `logs/.play.lock` is a runtime lock file (gitignored).

> **This directory ships only this README.** Recorded match data is not published; running a
> match in a fresh clone creates `logs/`, `games/`, `console/` and `screenshots/` locally on
> demand, and the ignore rules keep them out of commits.

## Layout

| Path | Contents | Written by |
|---|---|---|
| `logs/bot.log` | Global line log (decisions / construction / combat / review), a continuous stream stamped with hh:mm:ss | `audit.Audit` |
| `logs/jev-events.jsonl` | Global per-event audit stream (start/decision/action/loss/kill/obs/report) | `audit.Audit` |
| `logs/play*-run.log` | stdout of past match processes (matches 23-44, old naming) | launch-script redirection |
| `logs/bot-fault.log`, `logs/bridge.log`, `logs/bot-run.log` | Archives from the fault / bridge era | historical processes |
| `logs/.play.lock` | Single-instance lock (stores a PID; `--force` / `RA2WEB_NO_LOCK=1` bypass it) | `cli._acquire_lock` |
| `games/run-<timestamp>/` | **Per-match archive**: `decisions.jsonl` (SFT tuples) + `events.jsonl` (mirror) + `report.json` (+ the `game.json` match-number link written back by review) | `game.BattleSession` / `review.emit` |
| `games/game-XXXX-review.md` | Per-match review report (XXXX = review number) | `review.emit.write_review_md` |
| `games/game-XXXX-events.jsonl` | Event slice for that match (saved separately at review time, early matches) | `review.emit` |
| `console/gNN_console.log` | Console output of the per-match launch scripts (written by `scripts/runs/run_gNN.bat`) | launch script |
| `screenshots/` | In-process screenshot evidence (menu debugging, battlefield snapshots) | driver / manual |
| `bench/` | Opening-build micro-benchmark results | `scripts/bench_watch.sh` |
| `shadow_eval/` | Shadow eval (clef vs Jev decision agreement) results and report | `scripts/shadow_eval.py` |

## Data flow (the learning loop)

```
game.py run → logs/ + games/run-<ts>/   (live audit + per-match archive)
        ↓ endgame
review (automatic) → games/game-XXXX-review.md + docs/LESSONS.md + docs/knowledge/doctrine.json
        ↓ training side
scripts/build_dataset.py → dataset/runs/run-<ts>/ (normalized copy, with SFT tuples)
```

## Common commands

```bash
tail -f artifacts/logs/bot.log                 # line log
tail -f artifacts/logs/jev-events.jsonl        # per-event
ls -dt artifacts/games/run-* | head -1         # the current match's archive directory
uv run python scripts/build_dataset.py         # fold new matches into dataset/
```
