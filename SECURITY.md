# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Report privately
via GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository, or by direct message to [@ys118](https://github.com/ys118).

Include: what you found, how to reproduce it, and the impact you believe it has.
You can expect an initial response within a week.

## Supported versions

Only the `master` branch is maintained. Fixes are released as commits on
`master`; there are no maintained release branches.

## What matters for this project

This is a local automation tool, but a few classes of issue are taken seriously:

| Area | Why it matters |
|---|---|
| Credential leakage | The decision-model key (`TYPESAFE_API_KEY`) must never reach the game page, logs, or the repository. It is read from the environment and attached only to the model HTTP request in `src/ra2web_jev_player/jev/client.py`. A leak of this value is a valid report. |
| Command injection | Browser interaction shells out to the `agent-browser` CLI (`src/ra2web_jev_player/driver/browser.py`) and JavaScript is passed through `eval`. Values derived from game state are interpolated into those commands. An injection path that lets game-controlled data execute arbitrary commands is a valid report. |
| Data-asset integrity | `artifacts/` and `dataset/` are append-only records (see [CONTRIBUTING.md](CONTRIBUTING.md#data-assets-read-before-touching)). Code that silently deletes, truncates, or rewrites them is treated as a defect. |
| Accidental publication of private data | Logs and console captures may contain local filesystem paths or usernames. Report anything that looks like a personal path, key, token, or cookie in a tracked file. |

## Not in scope

- The game itself, its servers, or its official API — report those to the game's
  operators.
- Anything requiring the use of this project outside its stated scope
  (single-player skirmish against the built-in AI).
- Denial of service against your own machine caused by running a match; long
  matches are expected behaviour (see `docs/ENGINEERING-NOTES.md`).
