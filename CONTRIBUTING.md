# Contributing

Thanks for your interest in this project. This document explains how to set up
a development environment, what the project's conventions are, and which rules
must not be broken.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## What this project is

A fully self-contained bot that plays single-player skirmish matches in the
browser game *Chrono Divide* (《王二火大》, `gonghui.k0s.cn`) by:

1. driving a headless browser through the `agent-browser` CLI,
2. injecting an in-page client that talks to the game's **official** player
   console API (`window.werhd`),
3. deciding with a mix of deterministic code (build order, economy, scouting,
   retreat thresholds) and a semantic decision model (local `clef-flash`, or the
   TypeSafe Jev cloud API — same request contract).

Scope limits are non-negotiable (see [README](README.md#scope-and-compliance)):
single-player skirmish only, official public API only, no simulation patching,
no fog-of-war bypass.

## Runtime requirements

| Requirement | Notes |
|---|---|
| [uv](https://docs.astral.sh/uv/) | manages Python 3.11+ and the lockfile |
| `agent-browser` CLI | browser automation. Install it and make sure `agent-browser` is on `PATH`, or point `AGENT_BROWSER_CMD` at the executable |
| A decision-model endpoint | local `llama.cpp` server exposing the `/v1/systemone` contract (default `http://127.0.0.1:8085/v1`), or the TypeSafe Jev cloud API. Override with `JEV_BASE_URL` / `JEV_MODEL` |
| `TYPESAFE_API_KEY` | only needed for the cloud endpoint; never commit it |

Environment variables that affect behaviour are documented in
`src/ra2web_jev_player/config.py` (`RA2WEB_*`), `paths.py` (`JEV_*` directory
overrides) and `driver/browser.py` (`AGENT_BROWSER_*`).

## Development setup

```bash
git clone https://github.com/ys118/ra2web-jev-player
cd ra2web-jev-player
uv sync                      # dev group includes pytest + ruff
uv run pytest                # full suite: layout guards + regression scenarios
uv run ruff check            # lint
```

Two regression scenarios are marked `xfail` on purpose (stale assertions from
earlier iterations — see [tests/README.md](tests/README.md#known-stale-assertions)).
Fixing either one is a welcome first contribution.

## Repository conventions

- **All paths come from `src/ra2web_jev_player/paths.py`.** Never hardcode an
  absolute path in code or scripts. The layout contract is
  [docs/LAYOUT.md](docs/LAYOUT.md).
- **English in public surfaces**: README, governance docs, packaging metadata,
  CI, and module/class/function docstrings. **Chinese is intentional** in
  `docs/LESSONS.md`, `docs/SESSION-REPORT.md`,
  `docs/ENGINEERING-NOTES.md`, `docs/CLEF-LOCAL.md`, `docs/JEV-INTEGRATION.md`,
  the game-strategy content under `docs/knowledge/`, and in inline comments that
  record per-match lessons (e.g. `# [game 67] ...`). Runtime log messages are
  Chinese and are parsed by the review engine — do not translate them.
- **Commit messages are English** (`type: summary`, imperative mood).
- **Tests**: offline scenario tests live in `tests/regression/` and are executed
  by `tests/test_regression_suite.py`; layout/contract guards live in
  `tests/test_layout.py`. Add a scenario script when you change planner or game
  behaviour, and cite the match number that motivated the change.
- **Single-variable changes.** Threshold/behaviour changes must come with
  evidence from a real match, and the change itself must be isolated enough to
  attribute the outcome — see [docs/METHODOLOGY.md](docs/METHODOLOGY.md).
- **Lint scope**: `ruff` runs with a deliberately small rule set (real bugs:
  undefined names, unused imports, import order). Style rules are off because the
  code carries dense Chinese annotations.

## Data assets: read before touching

`artifacts/` and `dataset/` hold recorded match data. They are **not part of this
repository** — only their READMEs are, and the `.gitignore` keeps a contributor's
own match data out of commits. Treat them as append-only wherever they exist:

- Never delete, truncate or rewrite files under those directories.
- `artifacts/` is the runtime record (logs, per-match archives, screenshots).
  `dataset/` is the curated training-data index/corpus; rebuild it with
  `uv run python scripts/build_dataset.py` (idempotent) instead of editing files
  by hand. See [dataset/README.md](dataset/README.md).
- Changes to the shape of decision records (`decisions.jsonl`) or dataset
  metadata must be backwards compatible and called out in the pull request.

## Pull requests

1. Fork, branch from `master`, keep the diff focused.
2. Run `uv run pytest` and `uv run ruff check` — both must be clean.
3. In the description, state: what changed, the evidence (match number,
   scenario test, or reasoning), and any behaviour/format change.
4. Add an entry to [CHANGELOG.md](CHANGELOG.md) under `Unreleased` for
   user-visible changes.

Small, evidence-backed changes are much easier to review than broad refactors.
If you plan a large restructuring, open an issue first so the approach can be
discussed.

## Third-party material

`references/` contains game assets, official documentation snapshots and
community guide copies — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Do not add material you do not have the right to redistribute.
