# Methodology: how to make the AI fight better every match

> The project's most valuable output is not the code but this **replicable iteration methodology**:
> it turns the improvement of a "real-time battle AI" into an engineering loop that is auditable,
> cumulative and evolves with every match.

## 0. Automated closed loop (since 2026-09-26; the programmatic implementation of this methodology)

```
Live match (ra2web-jev-play, --loop N consecutive matches)
  → Record: jev-events.jsonl event by event (decisions/actions/losses/kills/observation snapshots) + bot.log line log
  → Review (review.py, run automatically at endgame):
      1) Deterministic analysis: opening timeline vs doctrine windows / economy·force curves / situation distribution /
         crisis response / exchange ratio / error fingerprints —— anything code can compute never goes to the model
      2) Jev semantic review: defeat rootcause + next-match top priority (topfix) +
         whether tuning is worthwhile (tune noul) —— the semantic call
      3) Bookkeeping: artifacts/games/game-XXXX-review.md (per-match report)
                    + docs/LESSONS.md (lessons ledger, append-only)
  → Iterate: rootcause hits the whitelist and tune>0.6 → docs/knowledge/doctrine.json is auto-tuned slightly
             (bounds: one step per item, with a floor; provenance and reason written into the file, git history is the audit trail)
             engineering bug/major change → goes to the LESSONS todo list, implemented by a human/agent
  → Next match: doctrine.load_overrides() loads the overridden parameters, the new match validates, loop
```

- Per-match review report: `artifacts/games/game-XXXX-review.md`; ledger: `docs/LESSONS.md`; tuning: `docs/knowledge/doctrine.json`; training data: `dataset/`.
- Manually review any match: `uv run ra2web-jev-review [--game N]`.
- The single-variable principle is unchanged: auto-tuning triggers at most one group per match (by rootcause); bounds + floors keep one match's noise from damaging the doctrine.

## 1. General principles

1. **Layered decisions**: deterministic code handles mechanism (deployment/placement/build order/production floor/throttling/thresholds), and Jev only makes the semantic calls (situation/threat/trade-offs/timing). Anything code can compute never goes to the model — and conversely the model is used only where code cannot compute.
2. **Mechanism before tactics**: first make sure orders actually execute (async queue, throttle, batching), then discuss tactical quality. This project spent a lot of time at the "the order did not take effect" layer (see `ENGINEERING-NOTES.md`).
3. **Single-variable iteration**: change only 1-3 explicit parameters per match, so results stay attributable. Write it into the docs beforehand, check the answer after the match.
4. **Complete evidence chain**: every conclusion must be traceable to a log line/screenshot/API reading. "Feelings" are rejected.

## 2. Per-match review loop (the user-mandated methodology, in force since match 18)

```
1) Result extraction   → score screen (time/destroyed/lost/built/score) + bot.log timeline
2) Defeat chain locate → follow the thread from the "earliest anomaly" (e.g.: 450s dead air at the opening → side-misjudgement bug → state layer failed to pass country)
3) bot parameter iteration → deterministic-layer changes (thresholds/order/rules), written into code annotated "from match N review"
4) jev parameter iteration → context additions / instruction wording / confidence thresholds / candidate add-remove
5) Documentation       → append to SESSION-REPORT.md (per match: result/timeline/problems exposed/evolution points)
6) Next-match validation → observe only, no mid-match restart; verify whether the last iteration took effect
```

### Loop examples (matches 18-20, one per match)

| Match | Review finding | Iteration |
|---|---|---|
| 18 | side-misjudgement bug wasted 450s of the opening | STATE_JS gains `country` + a `get_side` inference fallback (bot); jev context gains "under attack N times / 2 minutes" (jev) |
| 19 | ALARM counterattack **fed our army to the superior enemy in batches** (steady 37→0 attrition) | conditional counterattack: with force <2× the enemy, switch to TURTLE (hold the tower, no field battle) |
| 20 | defense spending devoured the tank budget (6200 gold on defense vs 0 tanks); the TURTLE threshold was too high so it never counterattacked | checklist reordered (power plant→miner→**tank**→defense); TURTLE threshold 2×→1.2×; sentry guns 4→3; add a second ore refinery right after the factory |

## 3. How to iterate the Jev call parameters

> Model capability is fixed; "what you feed it" determines decision quality. The tuning checklist this project distilled:

1. **The semantic glossary is the first lever**: internal codes must be glossed in Chinese (`NAHAND`→"Soviet barracks (war-factory prerequisite)"). Once, when the gloss carried zero information, Jev split its vote between hold(0.42) and power plant(0.40) and guessed, spending nothing for 150 game seconds.
2. **Layered context feeding**:
   - Battlefield snapshot (funds/power/buildings/units/queue/buildable list, with Chinese names + build cost);
   - **Enemy composition grouped by armor + auto-attached counter suggestions** (Grizzly = heavy armor → Rhino/tesla coil/tesla trooper);
   - **Event stream** (hit detail/losses/enemy approach distance, newest→oldest);
   - **Force comparison** (ours ≈X vs enemy ≈Y, converted from build cost) + attack frequency;
   - **Doctrine (DOCTRINE)**: iron rules / counter knowledge / target priorities / five-state situation machine, all as state fields.
3. **Judgment-point discipline**:
   - Ask all questions in one batched request (saves ~10× latency/cost versus asking one by one);
   - Options must cover everything + include `hold/wait`;
   - Confidence gates (situation switch ≥0.45; low confidence keeps the current situation against oscillation);
   - Independent questions asked in parallel (threat probability/situation/production choice are all different).
4. **Every parameter's provenance must be traceable**: the threshold table (funds lines/force gates/radar radius) annotates which match's review each value came from.

## 4. Engineering debugging method (battle-tested patterns)

1. **Prove the "order pipeline" before tuning strategy**: `produce/place` moved but `move` did not → narrow it down step by step to "wrapper failed/batch cap/throttle". Four-step verification: single unit → squad → large batch → switch API primitive.
2. **Stack dump to locate a hang**: `faulthandler.dump_traceback_later(30, repeat=True)` catches "which branch is spinning" in one shot (it once located a silent loop caused by "state missing the tick key").
3. **Restart to isolate a variable**: when the environment is suspect, use a minimal reproduction script (`scripts/probe.py`) run **in the foreground** and **in the background** separately, to prove whether it is the environment or the code.
4. **Controlled experiment to pin the root cause**: as with the junction deletion risk, "which of the two commands pierces through" — test them separately (this project: 5-tank vs 34-tank order delivery).
5. **Timeline alignment**: read real time (log timestamps) and game time (`werhd.time()`) separately — a divergence is the signal for "throttling/freeze".

## 5. Environment and hardware facts (they affect reliability; remember them)

- The page **must stay visible** (`document.visibilityState === "visible"`): hiding/minimizing stops rAF → simulated freeze; a headless-mode page is visible by default and is the first choice for long unattended runs.
- Detailed pitfall table and workarounds → `ENGINEERING-NOTES.md`.
- Protocol details of the official player and the bridge, parameter-tuning records → `JEV-INTEGRATION.md`.

## 6. Acceptance criteria (at the end of each stage)

- Functional loop: opening deployment → build order → production → scouting → defense → attack; the whole chain has log evidence;
- Stability: 0 script crashes and 0 runaway timeouts per match (timeouts must have a tree-kill fallback);
- Decision quality: sample-check Jev answers against the doctrine (e.g. "enemy Rocketeer sighted → pick anti-air");
- Auditable iteration: every parameter has a provenance, every change has a match-number reconciliation.
