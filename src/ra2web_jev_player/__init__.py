# -*- coding: utf-8 -*-
"""ra2web-jev-player: automated Jev-driven match player for the web Red Alert 2 game
"Chrono Divide" (王二火大).

Self-contained architecture (no HTTP bridge, no dependency on the official player):
- werhd: game API layer -- our own definition (api.md + copies of the official types) + in-page client client.js
- driver: browser driver -- agent-browser wrapper + game launch state machine (fully automatic match join)
- jev: decision-model call wrapper (same contract as TypeSafe Jev; the key stays on the Python side only)
- strategy: strategy layer -- doctrine/questions/state distilled from reviews + planner deterministic package
- review: review engine -- deterministic analysis + model semantic review + clamped tuning (closes the loop)
- game: match orchestration (macroscopic 1.5s main loop) x in-page 150ms micro control
- paths: repository path constants (single source of truth; layout in docs/LAYOUT.md)
- legacy.bot: the homegrown main loop for games 1-20, kept as historical reference

Entry points: ra2web-jev-play / ra2web-jev-launch / ra2web-jev-attach / ra2web-jev-review
      (see cli.py); `python -m ra2web_jev_player` prints usage.
Docs: README.md, docs/ARCHITECTURE.md, docs/LAYOUT.md.
"""

__version__ = "0.2.0"
