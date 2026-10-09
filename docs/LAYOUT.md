# LAYOUT — repository layout and migration mapping (2026-10-09 structure refactor)

> This refactor took the repo from a "flat root directory" to a standard uv Python project:
> **code in `src/`, documentation in `docs/` (including knowledge), data split into `artifacts/`
> (runtime working state) and `dataset/` (training data), external material merged into
> `references/`, scripts in `scripts/`, tests in `tests/`.**
> This document is the single source of truth for the layout; historical per-match review text
> (`LESSONS.md` etc.) keeps the path style of its time — when reading old records, convert with
> the mapping table at the end of this file.

## 1. Final layout

```
ra2web-jev-player/
├── pyproject.toml / uv.lock / .python-version    # uv project (src layout, uv_build)
├── README.md / AGENTS.md                          # overview / collaboration red lines
├── src/ra2web_jev_player/                         # Python package (the project's only code source)
│   ├── __main__.py            # python -m ra2web_jev_player (prints usage when called with no args)
│   ├── paths.py               # project-wide path constants (single source, env-overridable)
│   ├── config.py              # MatchConfig / DriverConfig
│   ├── cli.py                 # the four command entry points
│   ├── audit.py               # line log + event-stream audit
│   ├── game.py                # BattleSession match orchestration (1.5s macro loop)
│   ├── driver/                # browser (agent-browser wrapper) + launcher (match-entry state machine)
│   ├── jev/                   # decision-model client (clef-flavored Jev contract)
│   ├── werhd/                 # game API: api.md + client.js + inject.py + d.ts
│   ├── strategy/              # doctrine (thresholds/manual) + questions (the five questions) + state (view)
│   │   └── planner/           # deterministic decision layer (was a 1642-line single file, split by responsibility)
│   ├── review/                # review engine (was a 497-line single file, split) + game-number↔run links
│   └── legacy/bot.py          # the in-house main loop for matches 1-20 (historical reference, not evolved)
├── scripts/                   # repo-level ops/data scripts (see scripts/README.md)
│   ├── run_game.bat           # general match launcher (use this for new matches)
│   └── runs/run_g72..g100.bat # archived historical launch scripts
├── tests/                     # pytest: layout guards + regression scenario driver (see tests/README.md)
│   └── regression/            # 26 single-variable offline scenario scripts (was out/test_*.py)
├── artifacts/                 # runtime working state (the data part of the old logs/ + out/)
│   ├── logs/                  # bot.log · jev-events.jsonl · process stdout · .play.lock
│   ├── games/                 # game-XXXX-review.md · game-XXXX-events.jsonl · run-<ts>/
│   ├── console/               # gNN_console.log (match console output)
│   ├── screenshots/ · bench/ · shadow_eval/
├── dataset/                   # training-data assets (see dataset/README.md)
│   ├── game-NNNN/             # backfilled from matches 1-65
│   ├── runs/run-<ts>/         # index entry per archived match (meta + review; payload stays in artifacts/games/)
│   ├── MANIFEST.jsonl · run-links.json
├── docs/                      # all documentation
│   ├── ARCHITECTURE.md · METHODOLOGY.md · ENGINEERING-NOTES.md
│   ├── JEV-INTEGRATION.md · CLEF-LOCAL.md · SESSION-REPORT.md · LESSONS.md
│   └── knowledge/             # the three strategy guides + doctrine (was knowledge/)
└── references/                # external material (old refs/ + _research/ merged)
    ├── werhd/                 # API documentation snapshots + official examples (was refs/)
    └── research/              # numeric ground truth + data-mining pipeline (was _research/)
```

## 2. Migration mapping (old → new)

| Old path | New path | Notes |
|---|---|---|
| `logs/bot.log`, `logs/jev-events.jsonl`, `logs/play*-run.log` | `artifacts/logs/…` | contents unchanged |
| `logs/games/` | `artifacts/games/` | per-match review and run archives |
| `logs/screenshots/` | `artifacts/screenshots/` | |
| `out/*.log` (gNN_console etc.) | `artifacts/console/` | |
| `out/bench_result.txt` | `artifacts/bench/` | |
| `out/shadow_eval/` | `artifacts/shadow_eval/` | |
| `out/test_*.py` | `tests/regression/` | scenario scripts; driven by pytest |
| `out/preflight.py`, `out/site_probe.py`, `out/bench_opening.py`, `out/shadow_eval.py` | `scripts/…` | internal paths now relative to the repo root |
| `out/run_gNN.bat` | `scripts/runs/run_gNN.bat` | historical archive; for new matches use `scripts/run_game.bat <game number>` |
| `out/play68_watch.sh`, `out/bench_watch.sh` | `scripts/play_watch.sh`, `scripts/bench_watch.sh` | |
| `scripts/build_training_assets.py` | `scripts/build_dataset.py` | same responsibility + incremental indexing of new matches |
| `knowledge/` | `docs/knowledge/` | strategy guides and doctrine |
| `refs/` (API docs + examples) | `references/werhd/` | |
| `_research/` (numbers/mining) | `references/research/` | same as above; reproduction flow in its README |
| `src/ra2web_jev_player/legacy_bot.py` | `src/ra2web_jev_player/legacy/bot.py` | how to run: `python -m ra2web_jev_player.legacy.bot` |
| `src/ra2web_jev_player/planner.py` (single file) | `src/ra2web_jev_player/strategy/planner/` (package) | public API unchanged (`planner.checklist` etc. as before) |
| `src/ra2web_jev_player/review.py` (single file) | `src/ra2web_jev_player/review/` (package) | public names such as `review.review_last_game` unchanged |

The environment variables (`JEV_*`) were updated along with the move: `JEV_ARTIFACTS_DIR` / `JEV_LOG_DIR` / `JEV_GAMES_DIR` /
`JEV_DATASET_DIR` / `JEV_DOCS_DIR` / `JEV_KNOWLEDGE_DIR` / `JEV_REFERENCES_DIR`,
all optional; when unset, the defaults above apply. `JEV_PROJECT_ROOT` remains the master switch
for when the repo is not in its default location.

## 3. Red lines and invariants that did not change

1. **Data must not be deleted**: `artifacts/`, `dataset/` and `docs/knowledge/doctrine.json` are all assets,
   persisted with git (`AGENTS.md`); before cleaning any directory tree, run the link check required by the user-level red line.
2. **The match-running path is unchanged**: `uv run ra2web-jev-play` is fully automatic; the pre-launch self-check runs `scripts/preflight.py`;
   the single-instance lock is `artifacts/logs/.play.lock`.
3. **Zero change to decision behavior**: this refactor is a move and a re-organization (function bodies preserved line by line); no threshold,
   match-number comment or behavior parameter was changed; 26 regression scenario scripts + layout guard tests protect this.
4. **No hard-coded paths in code**: every directory is taken from `paths.py` (the only exception is `cd /d %~dp0..`
   in `scripts/*.bat`, which locates the repo root by itself).
