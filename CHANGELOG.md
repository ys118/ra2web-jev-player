# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Open-source governance files: `LICENSE`, `THIRD_PARTY_NOTICES.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.editorconfig`,
  `.gitattributes`, issue/PR templates and a CI workflow.
- `docs/README.md`, a documentation index that states which documents are English
  and which are Chinese by design.

### Changed

- **Two-repository model**: the public repository is regenerated from the private
  working repository with `scripts/publish_public.sh` and ships code, docs, derived
  knowledge and official API snapshots only; recorded match data (`artifacts/`,
  `dataset/`) and data-mining material (`references/research/`) stay private. See
  `docs/PUBLISHING.md`.
- Recorded data files no longer contain the maintainer's local user path
  (`C:\Users\<user>` in 298 traceback lines).
- Public-facing documentation translated to English: `README.md`,
  `docs/ARCHITECTURE.md`, `docs/LAYOUT.md`, `docs/METHODOLOGY.md`, the
  per-directory READMEs, and all module/class/function docstrings in the package.
  Historical ledgers and per-match inline annotations remain Chinese on purpose.
- Hardcoded local tool paths removed: the `agent-browser` CLI is now resolved
  from `AGENT_BROWSER_CMD` / `PATH` (`driver.browser.resolve_agent_browser`),
  `TSJ_SCRIPT` is environment-only, and the historical launch scripts use a
  repository-relative working directory.
- `dataset/runs/<run>/` entries are now index-only (`meta.json` + `review.md`
  with a `source_dir` pointer) instead of duplicating payload files, removing
  ~340 MB of duplicated data from the repository.

## [0.2.0] - 2026-10-09

### Added

- Repository restructured as a standard `uv` project: `src/` package,
  `scripts/`, `tests/`, `docs/`, `artifacts/`, `dataset/`, `references/`
  (migration table in `docs/LAYOUT.md`).
- `tests/` suite runnable with `uv run pytest`: layout/contract guards, a
  sandboxed end-to-end review test, and a driver for the 26 offline regression
  scenario scripts.
- `scripts/build_dataset.py`: idempotent training-data builder (historical
  backfill + per-run incremental ingest, `dataset/run-links.json` link table).
- Review now writes `run-*/game.json`, linking a per-match archive to its review
  number for the dataset pipeline.
- `python -m ra2web_jev_player` entry point; `paths.py` is the single source of
  truth for repository paths (`JEV_*` overrides).
- `ruff` and `pytest` development dependency group, with lint/test configuration.

### Changed

- `strategy/planner.py` (1642 lines) split into the `strategy/planner/` package;
  `review.py` (497 lines) split into the `review/` package; `legacy_bot.py` moved
  to `legacy/bot.py`. The public API and all decision behaviour are unchanged.
- Logs and outputs merged into `artifacts/`; `knowledge/` moved under `docs/`;
  `refs/` and `_research/` merged into `references/`.

### Fixed

- `review/analyze.py` was missing `import re`, which raised `NameError` when
  reviewing any match that logged error lines.
- `game.py`'s scouting-error traceback handler referenced an undefined variable.
- `doctrine.COUNTERS["special_1"]` was silently overridden by a duplicate key.
- `legacy/bot.py` opened its log file at import time, so importing the module
  failed when the log directory did not exist.

## [0.1.0] - 2026-09-26

### Added

- Initial self-contained architecture: in-page client over the game's official
  player console API, `agent-browser` driver with a fully automated match
  launcher, deterministic strategy layer distilled from 20 matches, decision
  model client (TypeSafe Jev contract), per-match audit log and event stream,
  and the automatic review loop (deterministic analysis + semantic review +
  capped doctrine tuning).
