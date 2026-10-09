# Documentation index

Two kinds of documents live here, deliberately in two languages:

- **English** — the parts a newcomer or contributor needs: architecture, layout
  contract, methodology.
- **Chinese** — the project's own working log: per-match lessons, hand-off
  notes, engine pitfalls, and the game-strategy knowledge base. These are dense,
  match-by-match records written while playing; they are kept in their original
  language on purpose. Translating them would lose the shorthand the project's
  iteration loop depends on.

| Document | Language | What it is |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | English | The self-contained architecture: layers, data flow, design trade-offs, and how it differs from the earlier bridge-based design. |
| [LAYOUT.md](LAYOUT.md) | English | Repository layout contract, the old → new migration table, and the invariants that must not be broken. |
| [METHODOLOGY.md](METHODOLOGY.md) | English | How the project iterates: single-variable changes, the evidence rule, the review loop, and how a threshold may be changed. |
| [HANDOFF.md](HANDOFF.md) | Chinese | Cold-start hand-off for the maintainer: current state, how to resume, operational rules learned the hard way. |
| [LESSONS.md](LESSONS.md) | Chinese | Append-only ledger, one entry per match: what failed, the root cause, the parameter change, the follow-up. The most valuable file in the repository. |
| [SESSION-REPORT.md](SESSION-REPORT.md) | Chinese | History of the first 20 matches (the in-house bot era) and the reasoning that produced the current strategy layer. |
| [ENGINEERING-NOTES.md](ENGINEERING-NOTES.md) | Chinese | Engine, browser and environment pitfalls: page lifecycle, throttling, eval transport limits, daemon hangs. |
| [JEV-INTEGRATION.md](JEV-INTEGRATION.md) | Chinese | Decision-model integration: request contract, question shapes, confidence gates, parameter-iteration mechanism. |
| [CLEF-LOCAL.md](CLEF-LOCAL.md) | Chinese | Dossier for running the decision model locally (llama.cpp + clef-flash): contract parity, shadow-evaluation numbers, thresholds, switch-over manual. |
| [knowledge/](knowledge/README.md) | Chinese | Game knowledge base: `RA2-BIBLE.md` (full strategy guide), `AI-OPERATING-CARD.md` (condensed operating manual fed to the model), `RA2-UNITS.json` (unit/building/warhead ground truth from `rules.ini`), `doctrine.json` (tuned thresholds, audited in git). |

Related material outside `docs/`:

- [README.md](../README.md) — project overview, quick start, scope rules.
- [dataset/README.md](../dataset/README.md) — training-data index, quality
  tiers, and the numbering caveats.
- [artifacts/README.md](../artifacts/README.md) — what the runtime record holds.
- [references/README.md](../references/README.md) — external material and the
  data-mining pipeline behind `knowledge/RA2-UNITS.json`.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — conventions, including which files are
  English and which stay Chinese.
