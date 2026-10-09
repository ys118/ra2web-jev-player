# scripts — repo-level ops and data scripts

> These scripts are **not** part of the package (they are not packaged into the wheel) and are run
> from the repo root: `uv run python scripts/<name>.py`. They rely on the path constants of
> `src/ra2web_jev_player` (`paths.py`), so if a directory moves, that is the only place to edit.

## Match operations

| Script | Purpose |
|---|---|
| `preflight.py` | Pre-launch self-check (hardened from match 88): clef decision service → browser WebGL → residual-session cleanup → serial site probes. **Do not reorder** (an eval right after close hangs for 150s, verified while diagnosing match 95). Exit 0 only if everything passes |
| `site_probe.py` | Single site-recovery probe (popup dismissed + main menu rendered); exit 0 = recovered |
| `run_game.bat` | **General match launcher**: `scripts\run_game.bat 101` → starts the match once preflight passes; the console log lands in `artifacts/console/g101_console.log` |
| `runs/run_gNN.bat` | Historical launch scripts for g72-g100 (kept as an archive; their internal paths were updated with the structure refactor, so they can be re-run as-is) |
| `play_watch.sh` | Site-recovery watchdog (up to 3 hours) → starts the match automatically once recovered |
| `probe.py` | agent-browser session health probe (eval round-trip timing) |

## Data and evaluation

| Script | Purpose |
|---|---|
| `build_dataset.py` | Training-data builder (idempotent): backfills the 1-65 match history and incrementally folds each match's run directory into `dataset/`. `--check` only reports; `--skip-legacy` folds in new matches only. See `dataset/README.md` |
| `shadow_eval.py` | Shadow eval: replays historical decision tuples to the local clef-flash and compares them against the Jev answers on file (never calls the remote endpoint). Results in `artifacts/shadow_eval/` |
| `bench_opening.py` + `bench_watch.sh` | Opening-build micro-benchmark (measured in match 67 on the refinery-first chain): runs automatically after site recovery; results in `artifacts/bench/` |
| `dbg-st.json` | One state snapshot from early debugging (historical archive) |

## Conventions for new scripts

1. Always take paths from `ra2web_jev_player.paths` (or locate the repo root with
   `Path(__file__).resolve().parents[1]`); never hard-code `D:\...`;
2. Anything that writes artifacts goes into `artifacts/` (runtime artifacts) or `dataset/` (training
   data), and both READMEs must be updated in sync;
3. Avoid module-level side effects (such as opening files on import) — the historical
   `legacy/bot.py` tripped over this one.
