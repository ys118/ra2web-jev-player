# references — external references (the old `refs/` + `_research/` merged)

> This directory is an **archive of external material**: upstream documentation snapshots and
> data-mining material. Runtime (matches) does not depend on it; the canonical copies of the
> distilled knowledge live in `docs/knowledge/` (the three strategy guides and the operating card).

## Layout

| Path | Origin | Contents |
|---|---|---|
| `werhd/` | was `refs/` | Snapshots and examples of the game's official player API documentation: `player-console-api.md` (the original werhd API text), `jev-player-local.md`, `jev-player-goal-audit.md`, `examples/` (official player source, including the `jev/` subdirectory of examples) |
| `research/` | was `_research/` | Numeric ground truth and a reproducible pipeline: `rules.ini` (the original game-client file), `ra2.csf` + `csf_decoded.json` (codename → Chinese name), `rules_extract*.md` (extraction tables), `app.js` / `worker.js` (engine-semantics verification), `pages/` (43 community guide articles in their original wording), scraping/decoding scripts (`web.py` / `fetch_pages.py` / `decode_csf.py` / `gen_json.py` / `verify.py` and others) |

## Correspondence

- `research/` is the **upstream** of the `docs/knowledge/` trio: raw data and generation scripts live
  here, and the conclusions are distilled into `docs/knowledge/RA2-BIBLE.md` /
  `AI-OPERATING-CARD.md` / `RA2-UNITS.json`. Follow `research/README.md` for the reproduce/refresh
  flow (including the full-refresh steps after a game version upgrade).
- Facts about engine/site semantics are governed by the official documentation in `werhd/`; this
  project's own API definitions and in-page client live in `src/ra2web_jev_player/werhd/`
  (`api.md` + `client.js` + a copy of the official `.d.ts` types).

## Running notes

- The scraping scripts under `research/` depend on `requests`: after `uv sync --group research`, run
  `uv run python references/research/<script>.py`.
- This directory is excluded from static checks and tests (ruff `extend-exclude` in
  `pyproject.toml`) and is not packaged into the wheel (it is run from the repo root).
