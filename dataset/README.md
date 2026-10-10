# dataset — training-data assets (SFT / RL)

> This directory is the canonical export of match data **for model fine-tuning**.
> **Red line: never clean, overwrite or delete anything in here** (see
> `AGENTS.md`). The builder is idempotent, so the directory can always be
> regenerated with `uv run python scripts/build_dataset.py`.

> **This directory ships only this README.** The corpus and the per-match archives are not
> published. In a fresh clone, `scripts/build_dataset.py` builds this directory from whatever
> match data exists under `artifacts/games/`.

## Two zones

| Zone | Path | Source | Coverage |
|---|---|---|---|
| Historical backfill | `game-NNNN/` | slices of the global event stream plus hand-verified mappings (`SEG_MAP` / `REVIEW_MAP` / `RUN_GAMES` inside `scripts/build_dataset.py`) | games 1–65, frozen (the maps are hardcoded; nothing extends this zone) |
| Incremental index | `runs/run-<timestamp>/` | one entry per archived run under `artifacts/games/run-*/` (runs without a terminal `report.json` are ingested too, as `tier: partial`) | every archived run, from game 45 onwards — grows every match |

`MANIFEST.jsonl` holds one metadata line per entry (mixed kinds: `game-legacy`,
`game-events`, `game-run`, `run-ingest`) and is the single index for anything
consuming this directory.

### Contents

```
game-NNNN/                 curated corpus — payload included
  meta.json                result / duration / quality tier / provenance pointers
  events.jsonl             full event stream (present for the rl-trajectory tier)
  decisions.jsonl          SFT tuples (state, questions, answers) (sft-full tier)
  report.json              end-of-match report
  review.md                copy of the match review
  run.log                  process stdout, when it can be attributed to the match

runs/run-<timestamp>/      index entry — payload NOT duplicated
  meta.json                result, ticks, tier, sft tuple count, review link,
                           terminal_report, and source_dir pointing at artifacts/games/<run>/
  review.md                copy of the match review (present when a review number is linked)
```

Payloads are deliberately **not** duplicated into `runs/`: a single match's
`decisions.jsonl` can be tens of megabytes, and the archive under
`artifacts/games/<run>/` is already the authoritative copy. `meta.source_dir`
plus `meta.payloads` tell a training script where to read them.

### Quality tiers (`tier`)

| Tier | Meaning | Usable for |
|---|---|---|
| `sft-full` | event stream + complete `(state, questions, answers)` tuples + known outcome | SFT / RL trajectories |
| `rl-trajectory` | complete event stream + known outcome (no decision tuples) | RL trajectories with return labels |
| `partial` | no terminal `report.json` (user stop, stall guard, killed process) or concurrency-tainted match; tuples and events are complete but the outcome label is missing | SFT; RL only with return labels you supply yourself |
| `legacy-meta` | games 1–22: metadata only (raw line log in `artifacts/logs/bot.log`) | statistics only |

`meta.terminal_report` (index zone) separates the two `partial` cases: `false` means the run was
terminated externally, so `result` / `t` / `ticks` are `null` and the match's review records
`unknown`. The run is still a training asset — its tuples are complete, only the label is missing.

## Reading the corpus (games 66+ are in the index zone, not in `game-NNNN/`)

`game-NNNN/` stops at 65 **by design**: those directories come from the hardcoded backfill maps, and
from game 45 onwards every match is addressed through the index zone instead. Recommended reading
path for any consumer, for the whole history:

1. Iterate `MANIFEST.jsonl`; branch on `kind`.
2. For `kind == "run-ingest"` (game 45 onward), read the payload from `meta.source_dir` +
   `meta.payloads` — the payload is deliberately not copied into this directory (a match's
   `decisions.jsonl` can be tens of megabytes).
3. For `kind == "game-run"` (games 45–65) the payload sits in `game-NNNN/` as a copy.
   **These overlap**: matches 45–65 appear in both zones (same `run`), so de-duplicate by `run` /
   `review_no` before summing tuples or counting matches.
4. `game-events` (23–44) has events only; `game-legacy` (1–22) has metadata only.

## Numbering (read this before joining data)

Three numbering schemes coexist and **none of them is equal to another**. Always
key off the manifest fields (`game` for the backfill zone; `run` + `review_no`
for the index zone):

| Scheme | Carrier | Example (the 2026-10-07 closing match) |
|---|---|---|
| Match ordinal ("match N" in the ledgers) | the ledgers (`docs/LESSONS.md`) | match 100 |
| Console / launch ordinal | `artifacts/console/gNN_console.log`, `scripts/runs/run_gNN.bat` | g100 |
| Review number | `artifacts/games/game-XXXX-review.md`, `meta.review_no` | XXXX = 87 |

The gaps come from aborted runs and from the early architecture switch (details
in the maintainer's hand-off notes). **Scripts never guess a number**: an index entry is keyed
by its run directory name, and the link to a review number comes either from
`run-*/game.json` (written by the review itself, authoritative) or from an exact
match of the `report.json` triple `(result, t, ticks, crisis_ticks)` against the
review file header. Multiple candidates are marked `ambiguous` and left for a
human instead of being silently resolved.

## Repairs and known quirks (2026-10-09)

- **`run-20261006-165307` (match 94) and `run-20261007-113759` (match 96)** were terminated
  externally, so no `report.json` exists and no triple could be matched. Their `game.json` links
  (reviews 80 and 82) were written by hand after machine-checking the time chain — the run's last
  event minute equals the review header minute, cross-checked against the console ordinal and the
  ledger — and the evidence is recorded in the `source` field of each link. Before this repair both
  runs, 4 643 tuples in total, were absent from the dataset entirely.
- **`game-0086-review.md` duplicates `game-0085-review.md`**: at discovery the two files were
  byte-identical and only the title line differed (the ledger has no match entry for review 86).
  The duplicate used to make the linker mark `run-20261007-140353` (match 99) `ambiguous`; that run
  now links to review 85. The duplicate file is kept, with an append-only note at the top recording
  this.
- **Ingestion criterion relaxed**: a run is ingested whenever it carries a payload
  (`events.jsonl` / `decisions.jsonl`), as `tier: partial` when it has no terminal report. This
  recovered 19 externally-terminated runs, 17 049 tuples in total, that were previously skipped.

## Build and verify

```bash
uv run python scripts/build_dataset.py              # idempotent rebuild (backfill + index)
uv run python scripts/build_dataset.py --check      # report only, write nothing
uv run python scripts/build_dataset.py --skip-legacy  # only index new runs
```

- `run-links.json` — the run → review-number alignment table, with the `match`
  field recording how each link was established, so it can be audited.
- Ingestion criterion (index zone): payload present → ingested; terminal report
  present → `sft-full`, otherwise `partial` (`terminal_report: false`). Nothing
  with a payload is silently dropped; only a run with no `events.jsonl` and no
  `decisions.jsonl` is skipped.
- New training fields (for example a change to the `decisions` shape) must be
  reported before they are introduced and must keep old data readable
  (`AGENTS.md`).
