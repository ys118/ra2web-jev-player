# ra2web-jev-player

[![CI](https://github.com/ys118/ra2web-jev-player/actions/workflows/ci.yml/badge.svg)](https://github.com/ys118/ra2web-jev-player/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A self-contained bot that plays **single-player skirmish matches** in the
browser game *Chrono Divide* (《王二火大》, `gonghui.k0s.cn`) — a web remake of
Red Alert 2 — and gets better at it match by match.

One command takes it from a cold browser to a finished match report:

```bash
uv run ra2web-jev-play
```

It drives a headless browser, injects its own in-page client over the game's
**official** player console API, plays the match with a mix of deterministic
mechanics and semantic model decisions, writes a structured record of every
match, and then reviews itself — the review feeds capped parameter tuning for
the next match. Every match also produces training data (complete
`state → questions → answers` tuples) for later SFT/RL work.

> **Documentation language.** Public-facing docs, docstrings and commit messages
> are English. `docs/LESSONS.md`, `docs/HANDOFF.md`, `docs/SESSION-REPORT.md`,
> `docs/ENGINEERING-NOTES.md`, `docs/CLEF-LOCAL.md`, `docs/JEV-INTEGRATION.md`
> and the game-strategy content under `docs/knowledge/` are **Chinese by design** —
> they are the project's per-match engineering log. See
> [docs/README.md](docs/README.md) for the index.

## Highlights

- **No bridge, no fork of the game.** Everything runs through the game's public
  player console API (`window.werhd`); the bot's in-page client is injected at
  match start and throttles orders exactly like a human would.
- **Two-layer decisions.** Deterministic code owns mechanics (build order,
  economy floors, scouting routes, retreat thresholds, production debt gate);
  the decision model only makes the semantic calls (stance, threat assessment,
  unit mix, attack timing).
- **A real learning loop.** Audit → deterministic analysis → semantic review →
  capped, whitelisted parameter tuning in `docs/knowledge/doctrine.json`, which
  the next match loads. Every parameter carries the match number that justified
  it.
- **Training data as a first-class asset.** Per-match archives
  (`decisions.jsonl`, `events.jsonl`, `report.json`) plus a curated
  `dataset/` index, both append-only.
- **Offline-testable strategy layer.** 26 scenario regression tests plus layout
  guards run in seconds with `uv run pytest`, no browser and no model required.

## Requirements

| Requirement | Why |
|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.11+ and dependency management |
| `agent-browser` CLI | the only browser channel. Put it on `PATH` or set `AGENT_BROWSER_CMD` |
| Decision-model endpoint | a local `llama.cpp` server exposing the `/v1/systemone` contract (`JEV_BASE_URL`, default `http://127.0.0.1:8085/v1`), or the TypeSafe Jev cloud API |
| `TYPESAFE_API_KEY` | only for the cloud endpoint; read from the environment, never stored |

Installation of `agent-browser` and the local model server is outside this
repository; see [CONTRIBUTING.md](CONTRIBUTING.md#runtime-requirements) for the
environment variables that configure them.

## Quick start

```bash
git clone https://github.com/ys118/ra2web-jev-player
cd ra2web-jev-player
uv sync                       # install (dev group includes pytest + ruff)

uv run ra2web-jev-play        # full auto: launch → play → report → self-review
#   ra2web-jev-launch         # only enter a match and inject (driver debugging)
#   ra2web-jev-attach         # attach to a match you started by hand
#   ra2web-jev-review         # review the most recent match again
# common flags: --faction 苏俄 --speed 3 --credits 10000 --headed --loop N
#   (faction names are the game's own Chinese UI strings; 苏俄 = Soviet)

uv run pytest                 # regression suite (no browser needed)
uv run ruff check             # lint
```

On Windows, `scripts\run_game.bat <n>` wraps pre-flight checks (model service,
browser WebGL, stale session, site reachability) around a match and writes the
console log to `artifacts/console/`.

Monitoring a live match:

```bash
tail -f artifacts/logs/bot.log                  # line log
tail -f artifacts/games/run-*/events.jsonl      # per-event stream
ls -dt artifacts/games/run-* | head -1          # current match archive
```

## How it works

```
Browser (headless, via agent-browser)
  └─ game page: window.werhd (official API) + window.__rj (this project's in-page client)
       └─ micro loop every 150 ms: focus fire, harvester recovery, repair, placement, camera

Python (src/ra2web_jev_player/)
  ├─ driver/      cold browser → dialogs → menu → match config → match start (~25 s)
  ├─ game.py      macro loop ~1.5 s: snapshot → sense → deterministic checklist → model questions → manoeuvre
  ├─ strategy/    doctrine (thresholds + manual), questions, state view, planner/ (deterministic decisions)
  ├─ review/      end-of-match review: deterministic analysis + semantic root cause + capped tuning
  └─ jev/         decision-model client (key never leaves the Python process)
```

| Layer | Cadence | Responsibility |
|---|---|---|
| Micro | 150 ms | focus fire, harvester recovery, repair, placement, camera, stall/end detection (in-page, zero network) |
| Mechanics | ~1.5 s | opening build order, economy floors, tank budget, AA insurance, defence line, wounded retreat (`strategy/planner/`) |
| Semantics | ~1.5 s | stance arbitration, build/infantry/vehicle choice, threat assessment (`jev/`) |

Decision policy, in one line: **anything that can be computed is computed; the
model only decides what cannot be computed** — with confidence gates on the
model's answers and page-side throttling so orders never thrash.

## Repository layout

The layout contract is [docs/LAYOUT.md](docs/LAYOUT.md); every top-level data
directory has its own README.

| Path | Contents |
|---|---|
| `src/ra2web_jev_player/` | the package: `werhd/` (own API definition + in-page client), `driver/`, `jev/`, `strategy/` (+ `planner/`), `review/`, `game.py`, `cli.py`, `paths.py`, `legacy/` |
| `scripts/` | repo-level tooling: match launcher, pre-flight, training-data builder, shadow evaluation ([README](scripts/README.md)) |
| `tests/` | layout guards, sandboxed review test, 26 offline scenario scripts ([README](tests/README.md)) |
| `artifacts/` | runtime record: logs, per-match archives, console output, screenshots ([README](artifacts/README.md)) |
| `dataset/` | training-data index and curated corpus ([README](dataset/README.md)) |
| `docs/` | architecture, layout, methodology, hand-off notes, per-match lessons, game knowledge ([index](docs/README.md)) |
| `references/` | external material: official API docs and examples, game data-mining pipeline ([README](references/README.md)) |

**Public repository vs. maintainer checkout.** The public repository ships code,
tests, scripts, docs, the derived knowledge base and the official API reference
snapshots. Recorded match data (`artifacts/`, `dataset/`) and the data-mining
material (`references/research/`) are kept in the maintainer's private working
repository — those directories contain only their README here. See
[docs/PUBLISHING.md](docs/PUBLISHING.md).

## The learning loop

```
match (game.py) ──► live audit (artifacts/logs/) + per-match archive (artifacts/games/run-<ts>/)
      │
      └─ end of match ─► review: deterministic findings + semantic root cause
                          ├─ artifacts/games/game-XXXX-review.md   per-match report
                          ├─ docs/LESSONS.md                       append-only lesson ledger
                          └─ docs/knowledge/doctrine.json          capped parameter overrides
      │
      └─ training side ─► scripts/build_dataset.py (idempotent)
                          └─ dataset/ index + curated corpus (SFT tuples, events, reports)
```

Parameter changes are whitelisted, bounded, and gated on model confidence; the
tuning history is auditable in git. The reasoning behind single-variable
iteration is in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Status

Developed in public from match 1: **100 matches played, 21 won**, against the
game's built-in AI on random factions. The interesting part is not the win rate
but the trace: `docs/LESSONS.md` records what broke, why, and what changed —
including the matches that were lost to the same mistake twice.

## Scope and compliance

This project deliberately stays inside a narrow, legitimate envelope:

- **Single-player skirmish only.** No ranked, no multiplayer, no ladder play.
- **Official public API only.** Orders go through the same lock-step queue the
  mouse uses; the bot reads only what a human player could see in their view.
- **No simulation patching, no fog-of-war bypass, no hidden-state reads.** No
  memory editing, no packet manipulation, no input injection outside the API.
- **No redistribution of the game.** Game assets under `references/` are
  included for research/reference only — see
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This project is not
  affiliated with or endorsed by the game's authors.
- **Secrets stay local.** The model API key lives in the environment and is
  attached only to the model request inside the Python process.

If you use this code, keep it inside that envelope.

## Contributing

Issues and pull requests are welcome — start with
[CONTRIBUTING.md](CONTRIBUTING.md). Two regression scenarios are marked `xfail`
because their assertions went stale in earlier iterations; fixing either is a
good first contribution. Behaviour changes need evidence from a real match
(single-variable rule). Please also read the
[Code of Conduct](CODE_OF_CONDUCT.md) and the
[security policy](SECURITY.md).

## License

[MIT](LICENSE) for the code and documentation authored here. Third-party
material bundled under `references/` and the recorded game data under
`artifacts/`/`dataset/` are covered by
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), not by the MIT license.
