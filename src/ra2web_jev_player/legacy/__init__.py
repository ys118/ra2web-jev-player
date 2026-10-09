# -*- coding: utf-8 -*-
"""Historical archive: the homegrown main loop for games 1-20 (legacy-bot), kept for comparison after the
official system went live.

- Run (historical reproduction only, not the engineering mainline):
  ``uv run python -m ra2web_jev_player.legacy.bot``
- Comparison material: ``docs/SESSION-REPORT.md`` (the twenty-game evolution history), head of
  ``docs/LESSONS.md``
- The engineering mainline is ``game.py`` + ``strategy/planner/`` (the self-contained system); this package
  does not evolve -- it is kept as it was so reviews of games 1-20 can compare against the implementation
  of that time.
"""
