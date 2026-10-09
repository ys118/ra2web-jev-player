## What changed

<!-- One paragraph. What behaviour or file changed, and why. -->

## Evidence

<!-- Match number, log excerpt, scenario test, or the engine/API fact behind this change. -->

## Checklist

- [ ] `uv run pytest` is clean (34 passed, 2 xfail expected)
- [ ] `uv run ruff check` is clean
- [ ] Decision behaviour is either unchanged, or the change is single-variable and evidence-backed (`docs/METHODOLOGY.md`)
- [ ] No secrets (API keys, cookies) or personal paths added to tracked files
- [ ] Data assets (`artifacts/`, `dataset/`) untouched, or the change is additive and backwards compatible
- [ ] English commit message; `CHANGELOG.md` updated under `Unreleased` for user-visible changes
- [ ] If this changes planner/game behaviour: a scenario test under `tests/regression/` cites the match that motivated it
