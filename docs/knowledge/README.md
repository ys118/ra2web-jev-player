# knowledge — strategy guides and numbers (the AI's decision basis)

> This directory is the **knowledge base** fed to Jev / the decision layer: three files with
> different roles, all from the same data set.
> Raw data and reproduction method: `references/research/README.md`.

## 1. How to use the three files

| File | What it is | How to use it |
|---|---|---|
| `RA2-BIBLE.md` | All-dimension strategy guide (638 lines): basic concepts / unit catalog / economy / combat / opening / tactics / micro / **Art of War mapping** / **decision checklist** | Long-context knowledge base; consult it when iterating strategy, attributing a review, or writing new rules |
| `AI-OPERATING-CARD.md` | Compressed operating card (~6 KB): ten iron rules, per-tick checklist, threshold table, five-state machine, forbidden list | Fed to the decision model **directly as the system prompt** (cheaper in tokens than the Bible) |
| `RA2-UNITS.json` | Machine-readable numbers: 40+ units/buildings (cost, HP, armor, weapon) + 27 warheads × 11 armor multipliers + global parameters | Read directly from code with `import json`; never parse numbers out of the Markdown |

How they fit together (this project's practice): `RA2-UNITS.json` → counter/pick logic;
`AI-OPERATING-CARD.md` distilled into the fixed DOCTRINE text and fed to Jev together with the live
battlefield text; `RA2-BIBLE.md` for humans/agents to consult and iterate on.

The directory also holds `doctrine.json`: the override values written back by the automatic review
tuning (bounded, one step per item, with a floor; provenance and reason are recorded in the file and
git history is the audit trail — see `docs/METHODOLOGY.md`).

## 2. Provenance and version (important)

- **Numbers**: the original game-client files `rules.ini` + `ra2.csf` (scraped on **2026-09-20**,
  client **v0.87.0-r79e73e7**, `mod id = gonghui`). The Chinese names come from decoding the CSF.
- **Tactics**: 43 community guide articles (the Red Alert Home site uc129, Youxia, Tieba, Moegirlpedia),
  originals in `references/research/pages/`.
- **Engineering constraints**: reviews of 20 real matches played through the in-house direct werhd
  integration (`src/ra2web_jev_player/legacy/bot.py`, `docs/SESSION-REPORT.md`,
  `docs/ENGINEERING-NOTES.md`).

⚠️ **The numbers are bound to the version**: after a game update (the version number is visible on the
home page) you must re-scrape and regenerate following the flow in `references/research/README.md`,
then run `verify.py` to reconcile.

## 3. Usage caveats (avoid misusing them)

1. The "at most 5 units per batch, 12s per-target throttle, 45s deploy throttle" rules in
   `RA2-BIBLE.md` §8/§10 are constraints from the era of the **in-house direct werhd integration**;
   the official `werhd-jev-player` adapter batches automatically and carries per-unit cooldowns (see
   `docs/ENGINEERING-NOTES.md` §2). Do not copy rules from one system into the other.
2. The numbers are ground truth for **this version of this mod**, not generic stock-RA2 values; a few
   claims in community articles (e.g. "this mod's Mirage Tank has a low prerequisite", "money-farming
   tools") have no corresponding implementation in rules.ini, and Bible §11.3 lists them separately
   as uncertain items.
3. **Ratios are more durable than absolute values**: for example, "a Rhino kills a Rhino in 5 shots,
   a Grizzly needs 7 shots to kill a Rhino" follows from `damage × warhead multiplier ÷ HP`, and
   holds even under small version tweaks.
4. The `verses` order in `RA2-UNITS.json` is fixed as
   `none, flak, plate, light, medium, heavy, wood, steel, concrete, special_1, special_2`
   (see `meta.armor_classes` in the file); the multiplier is the damage:
   `damage × burst × verses[armor]`.

## 4. Known uncertainties (summary; details in `RA2-BIBLE.md` §11.3)

- Build time: `rules.ini` has no `BuildTime` field, so relative speed can only be inferred from cost.
- Ore per trip: the ini gives "25 credits/cell × 45 cells", while community measurements say about
  1000 per trip (war miner ≈ 2× chrono miner) — the latter is what the project uses.
- The kill-threshold formula for promotion has not been verified in the engine line by line; the
  reliable conclusion is that the threshold is proportional to cost.
- Anti-air tracked vehicle (HTK): the anti-air values are present (35/25/10), but a **real-combat
  kill verification** is recommended to be recorded as one instance in a review.
