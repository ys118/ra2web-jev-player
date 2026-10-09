# Architecture — the self-contained ra2web-jev-player

> 2026-09-26 refactor finalized: **the bridge is gone**. This repo no longer depends on the
> official `werhd-jev-player.mjs` or on a local HTTP bridge service (`bridge.py` has been
> deleted; the protocol lives on in git history); the API definition, browser driver,
> strategy and Jev wrapper all live inside the repo.

## 1. Overall structure

```
┌─────────────────────────────────── Browser (agent-browser headless session) ───────────────────────────────────┐
│  Game page https://gonghui.k0s.cn/                                                                             │
│   ├─ window.werhd          Official player console API (see werhd/api.md + d.ts copy)                          │
│   └─ window.__rj           Project's own in-page client (client.js, injected via eval --stdin)                 │
│       └─ micro() every 150ms (zero network): focus fire / miner recovery / repair /                            │
│          ready placement / camera / stall and endgame detection                                                │
└───────────────────────────────┬────────────────────────────────────────────────────────────────────────────────┘
                               │ agent-browser CLI (eval -b / eval --stdin, subprocess)
┌───────────────────────────────▼────────────────────────────────────────────────────────────────────────────────┐
│  Python (src/ra2web_jev_player/, managed by uv)                                                                │
│   driver/browser.py    CLI wrapper: session/eval/snapshot/click/timeout tree-kill                              │
│   driver/launcher.py   launch state machine: cold browser→popup→menu→config→start→inject (automatic ~25s)      │
│   game.py              macro loop ~1.5s: snapshot→perception→checklist→opening→scout→Jev→maneuver→report       │
│   strategy/planner/    deterministic decision layer (pkg: memory/sense/checklist/                              │
│                        opening/scout/stances/maneuver/apply)                                                   │
│   strategy/            thresholds and doctrine + Jev five questions (questions) + snapshot view (state)        │
│   review/              endgame review engine (pkg: collect/record/deterministic analysis/                      │
│                        semantic review/tuning/emit)                                                            │
│   jev/client.py        decision-model /v1/systemone wrapper (batch/retry/gzip/stats; key never leaves Python)  │
│   audit.py             artifacts/logs/bot.log + jev-events.jsonl audit                                         │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Decision layers (the core principle running through the project)

| Layer | Frequency | Responsibility | Location |
|---|---|---|---|
| Micro | 150ms | focus fire, miner recovery, repair, placement, camera, stall/endgame detection | in-page client.js (zero network) |
| Mechanism | ~1.5s | opening sequence, economy floor, tank budget, anti-air insurance, defense line, low-HP retreat | strategy/planner/ (deterministic) |
| Semantic | ~1.5s | five-state situation ruling, build/infantry/vehicle choices, threat assessment | jev (TypeSafe Jev) |

- Anything code can compute never goes to the model; Jev only rules where code cannot (`docs/METHODOLOGY.md`).
- Jev answers pass through gates: a situation is adopted only at confidence ≥0.45, a threat p>0.6 forces a
  fallback to defense, and candidates beyond the limits are dropped
  (refinery≤2/barracks≤2/attack dog≥4).

## 3. Data flow

1. **Match entry**: `ra2web-jev-play` → `launcher.launch()` force-refreshes the game page (discarding a stale match) →
   a11y-snapshot-driven clicks (single player → Skirmish) → eval sets the sliders directly (Soviet / speed 2 / credits 10000) →
   start game → poll `typeof werhd === 'object'` → `eval --stdin` injects client.js.
2. **State**: every tick Python calls `__rj.snapshot()` once to get the full JSON (me/units/enemy/queue/buildable).
3. **Micro**: client.js's internal setTimeout chain reads and writes werhd directly, without going through Python.
4. **Orders**: Python decides → `__rj.o.attackMove/produce/deploy/...` → in-page everything goes through
   batches of ≤5, a 12s throttle for the same target, an 18-tick per-unit cooldown and a 45s deploy throttle
   (measured constraints, api.md §6).
5. **Audit and learning loop**: `artifacts/logs/bot.log` (line log) + `artifacts/logs/jev-events.jsonl`
   (decisions/actions/losses/kills/observation snapshots, event by event) → per-match archive
   `artifacts/games/run-<timestamp>/` (training data)
   → automatic endgame review (`review/` package: deterministic analysis + model semantic review) → `artifacts/games/game-XXXX-review.md`
   per-match report + `docs/LESSONS.md` lessons ledger + bounded auto-tuning of `docs/knowledge/doctrine.json`
   (`docs/METHODOLOGY.md` §0) → loaded and validated in the next match; on the training side `scripts/build_dataset.py` merges into `dataset/`.

## 4. Key design trade-offs

| Decision | Rationale |
|---|---|
| Drop the HTTP bridge, keep the eval channel | Self-containment was a user requirement; once the official player + proxy duties were all re-implemented in-house, the extra HTTP hop was pure cost |
| Macro in Python, micro in-page | Micro needs 150ms-class reaction (an eval round trip of 0.05-0.3s cannot sustain it); the Jev key must not enter the page (the official docs take the same position) |
| Decision core ported over from legacy_bot | The parameters and lessons from 20 matches of review are the project's biggest asset; the architecture refactor must not change behavior (single-variable principle) |
| snapshot returns everything in one call | A single eval pulls the JSON, so a macro tick costs only one round trip |
| a11y snapshot drives the menus | The official side documents no menu automation; snapshot + click + assert is the most change-resistant general approach, with the `attach` subcommand as a fallback |

## 5. Comparison with the old architecture

| | Old (official stack) | New (self-contained) |
|---|---|---|
| In-page script | official werhd-jev-player.mjs (delivered over HTTP) | own client.js (eval injection) |
| Decision service | bridge.py HTTP service (/decide /event) | direct TypeSafe calls inside the Python process |
| Match entry | manual menu clicks | fully automatic launcher (`attach` as fallback) |
| API source of truth | `references/werhd/` snapshot | werhd/api.md + d.ts copy (`references/werhd/` still keeps the official originals) |
| Micro code | official v8.3 black box | own, editable, parameters owned |

## 6. Evolution directions (not done, left to later review iterations)

- Official-style candidate-group decisions (construction/vehicles/tactics… 8 groups per request) to replace the five-question scheme;
- At the end of each match, feed the battle report to Jev for a review verdict and auto-adjust doctrine thresholds (automating the METHODOLOGY §2 loop);
- Dashboard: a static page reading jev-events.jsonl (the old SSE dashboard was retired along with the bridge);
- Login/ranked play (needs an account scheme; the driver already keeps `--restore` session persistence).
