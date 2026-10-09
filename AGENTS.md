# AGENTS.md — project conventions for maintainers and AI agents

> Repository layout is defined in `docs/LAYOUT.md`: code in `src/`, docs in
> `docs/` (including `docs/knowledge/`), runtime record in `artifacts/`, training
> data in `dataset/`, external material in `references/`, scripts in `scripts/`,
> tests in `tests/`.
>
> Language policy: public-facing docs, docstrings and commit messages are
> English; historical ledgers, per-match inline annotations and runtime log
> strings stay Chinese (see `docs/README.md`).

## Match reporting rule (user-mandated, 2026-09-26)

**After every match — win or loss, and including every match inside a `--loop`
run — stop immediately and report to the user. Wait for feedback before playing
another match or starting an iteration.**

The report must contain at least:

1. Match report: result, duration, key timeline (opening build, first tank, enemy
   base located, final situation);
2. Review highlights: the deterministic findings from
   `artifacts/games/game-XXXX-review.md` plus the model's root-cause verdict;
3. What this match taught us and the proposed next iteration (single variable),
   to be confirmed by the user before execution.

Forbidden: running several matches without reporting, skipping the report and
iterating directly, starting the next match without the user's go-ahead.

## Training-data assets (user-mandated, 2026-09-29, top priority)

The user will fine-tune a base model on this data (SFT/RL) — every match is a
training asset:

1. **Every match is archived automatically** to `artifacts/games/run-<timestamp>/`:
   - `decisions.jsonl` — decision tuples (full state + questions + answers +
     situation context), the core SFT data;
   - `events.jsonl` — the full event stream of the match (decisions, actions,
     losses, kills, observation snapshots);
   - `report.json` — the end-of-match report (the review later writes
     `game.json`, linking the archive to its review number);
2. The review output `artifacts/games/game-XXXX-review.md` and the ledger
   `docs/LESSONS.md` are data assets too and must be persisted. The curated
   training-data export is `dataset/` (rebuild with
   `uv run python scripts/build_dataset.py`, which is idempotent; conventions and
   numbering caveats are in `dataset/README.md`);
3. **Red line: never clean, overwrite or delete any historical data under
   `artifacts/` or `dataset/`.** Data directories are not gitignored; they are
   persisted and pushed with git;
4. If a report finds data missing, corrupted or unarchived, tell the user
   immediately;
5. Data-format changes (adding/removing fields in `decisions`, changes to
   dataset metadata) must be reported first and must keep old data readable.

## Other standing rules (aligned with `docs/HANDOFF.md` §4)

- Use only the game's public werhd API; play single-player skirmish only, never
  ranked or multiplayer;
- The decision-model key lives only inside the Python process — never in the
  page, logs, or code;
- Never delete a working directory that has not been confirmed for archiving
  (data directories are protected by default);
- Learning-loop parameter changes go through `docs/knowledge/doctrine.json`
  (whitelist + capped deltas + confidence gate); structural changes must be
  reported first;
- Structural refactors (directory moves, module splits) must satisfy: `uv run
  pytest` fully green (26 scenarios + layout guards; stale assertions are listed
  in `tests/README.md`) and zero change in decision behaviour;
- Commit messages are English (user-mandated, 2026-10-09).
