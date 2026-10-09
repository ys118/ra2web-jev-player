# tests — tests

## How to run

```bash
uv run pytest                       # full suite (layout guards + 26 regression scenarios)
uv run pytest -k freeze             # a single scenario (filter by filename)
uv run pytest tests/test_layout.py  # layout/contract guards only
uv run python tests/regression/test_freeze95.py   # run one scenario script directly (equivalent)
```

## Layout

| Path | Description |
|---|---|
| `test_layout.py` | Repo-layout and package-contract guards: path constants must point at the final layout, data-asset directories must be non-empty, RA2-UNITS.json must actually load, the planner/review public APIs must stay stable, `python -m` with no arguments must not start a match, and the version number must agree in both places. **Any directory change or rename that forgot to update the code turns this red immediately** |
| `test_review_flow.py` | End-to-end review pipeline (offline sandbox, `JEV_*` env vars pointed at a temp directory): events → deterministic analysis → stub semantic review → review.md/LESSONS/doctrine tuning → `run-*/game.json` match-number link. Covers the error-fingerprint branch (the historical spot that missed `import re`) |
| `test_regression_suite.py` | Runs each scenario script under `regression/` in a subprocess and asserts exit code 0 |
| `regression/test_*.py` | **Single-variable offline scenario tests** from past iterations (accumulated over the match 30-101 arc): feed a state snapshot and assert the deterministic behavior of planner/game. The number in the filename is the match number at the time; the docstring states what it tests and why |

## Conventions

- Scenario scripts are "the file is the test case": top-level execution + per-check `PASS/FAIL`
  printing + `sys.exit(1)` on failure; `regression/conftest.py` already keeps pytest from collecting
  them directly (avoiding a SystemExit during import).
- New scenario tests go in `tests/regression/`, named `test_<topic><match>.py`, and add `src` to
  `sys.path` relative to the repo root (copy the first line of an existing file).
- Top-level scenario scripts can be driven by either `python <file>` or pytest; no fixtures needed.

## Known stale assertions (xfail, pending manual verification)

| File | Conflict |
|---|---|
| `regression/test_dog62.py` | Asserts 10 home-guard slots, while the current garrison semantics (match 84/92 iterations) give 9 — need to confirm whether the test is stale or the semantics regressed |
| `regression/test_gate.py` | Asserts the log text "factory pre-slot guard", renamed in match 67 to "opening-sequence pre-slot guard" |

Neither assertion is related to the 2026-10-09 structure refactor (both already failed before it;
the baseline is recorded). Once either one is fixed, delete it from `KNOWN_STALE`
(`tests/test_regression_suite.py`).

*(The two log strings quoted in the table are Chinese literals in the scenario scripts; they are
shown here in translation.)*
