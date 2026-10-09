# dataset — training-data assets (SFT / RL)

> This directory is the canonical export of match data **for model fine-tuning**.
> **Red line: never clean, overwrite or delete anything in here** (see
> `AGENTS.md`). The builder is idempotent, so the directory can always be
> regenerated with `uv run python scripts/build_dataset.py`.

> **Public repository note.** The public repository ships **only this README**: the corpus and the
> per-match archives stay in the maintainer's private checkout (see
> [docs/PUBLISHING.md](../docs/PUBLISHING.md)). In a fresh clone, `scripts/build_dataset.py`
> builds this directory from whatever match data exists under `artifacts/games/`.

## Two zones

| Zone | Path | Source | Coverage |
|---|---|---|---|
| Historical backfill | `game-NNNN/` | slices of the global event stream plus hand-verified mappings (`SEG_MAP` / `REVIEW_MAP` / `RUN_GAMES` inside `scripts/build_dataset.py`) | games 1–65 |
| Incremental index | `runs/run-<timestamp>/` | one entry per archived match under `artifacts/games/run-*/` | from the first archived run (game 45) onwards, grows every match |

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
                           and source_dir pointing at artifacts/games/<run>/
  review.md                copy of the match review
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
| `partial` | aborted or concurrency-tainted match; events partially usable | use with care |
| `legacy-meta` | games 1–22: metadata only (raw line log in `artifacts/logs/bot.log`) | statistics only |

## Numbering (read this before joining data)

Three numbering schemes coexist and **none of them is equal to another**. Always
key off the manifest fields (`game` for the backfill zone; `run` + `review_no`
for the index zone):

| Scheme | Carrier | Example (the 2026-10-07 closing match) |
|---|---|---|
| Match ordinal ("match N" in the ledgers) | `docs/HANDOFF.md`, `docs/LESSONS.md` | match 100 |
| Console / launch ordinal | `artifacts/console/gNN_console.log`, `scripts/runs/run_gNN.bat` | g100 |
| Review number | `artifacts/games/game-XXXX-review.md`, `meta.review_no` | XXXX = 87 |

The gaps come from aborted runs and from the early architecture switch (details
in `docs/HANDOFF.md`). **Scripts never guess a number**: an index entry is keyed
by its run directory name, and the link to a review number comes either from
`run-*/game.json` (written by the review itself, authoritative) or from an exact
match of the `report.json` triple `(result, t, ticks, crisis_ticks)` against the
review file header. Multiple candidates are marked `ambiguous` and left for a
human instead of being silently resolved.

## Build and verify

```bash
uv run python scripts/build_dataset.py              # idempotent rebuild (backfill + index)
uv run python scripts/build_dataset.py --check      # report only, write nothing
uv run python scripts/build_dataset.py --skip-legacy  # only index new runs
```

- `run-links.json` — the run → review-number alignment table, with the `match`
  field recording how each link was established, so it can be audited.
- New training fields (for example a change to the `decisions` shape) must be
  reported before they are introduced and must keep old data readable
  (`AGENTS.md`).
