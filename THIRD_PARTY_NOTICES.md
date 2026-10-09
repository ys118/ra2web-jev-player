# Third-party notices

The MIT license in [LICENSE](LICENSE) covers the source code and documentation
authored in this repository. It does **not** cover the material listed below,
which is bundled for research, interoperability and reference purposes. All
rights in that material remain with its respective owners.

If you are a rights holder and want something removed, open an issue or contact
the maintainer — it will be deleted promptly.

## 1. Game data extracted from the client (`references/research/`)

| File(s) | Origin | Notes |
|---|---|---|
| `rules.ini`, `art.ini`, `ra2.csf`, `zh-CN.json` | The web game client (Chrono Divide / 《王二火大》, `gonghui.k0s.cn`) resource bundle | Game configuration and localization data, fetched from the game's public static resources. Included as the numeric ground truth behind `docs/knowledge/RA2-UNITS.json`. |
| `app.js`, `worker.js`, `bot3.js` | Same bundle, minified engine/bot bundles | Included only for engine-semantics verification (how the engine evaluates prerequisites, targeting, etc.). |
| `csf_decoded.json`, `rules_extract*.md`, `listlinks.json`, `search*.json`, `page*.html` | Derived from the files above | Decoded/extracted tables produced by the scripts in the same directory. |
| `pages/*.txt` (43 files) | Community strategy guides from public sites (uc129.com / Red Alert Home, Youxia `gl.ali213.net`, Baidu Tieba, Moegirlpedia) | Archived text copies, used as the source material for `docs/knowledge/RA2-BIBLE.md`. |
| `crawl_list.py`, `fetch*.py`, `web.py`, `decode_csf.py`, `extract*.py`, `gen_json.py`, `verify.py`, `s1.py`–`s3.py`, `dbg1.py` | This project | Scripts (MIT). |

Red Alert 2 and its assets are trademarks/copyright of their respective owners
(Electronic Arts and the Chrono Divide project authors). This repository is not
affiliated with, endorsed by, or sponsored by them.

## 2. Official player-API documentation and examples (`references/werhd/`)

| File(s) | Origin |
|---|---|
| `player-console-api.md`, `jev-player-local.md`, `jev-player-goal-audit.md` | Snapshots of the game's official documentation (project `ra2web-werhd`) |
| `examples/**` (`werhd-user-script.mjs`, `examples/jev/*.mjs`, `werhd-jev-dashboard.html`) | Official example sources from the same project |

Included as read-only reference so that the API surface used by this project can
be audited. `src/ra2web_jev_player/werhd/api.md` and
`src/ra2web_jev_player/werhd/werhd-player-api.d.ts` are likewise derived from
that official documentation.

## 3. Runtime data (`artifacts/`, `dataset/`)

Game state snapshots, decision logs, event streams, review reports and
screenshots recorded while playing single-player skirmish matches against the
built-in AI. These are this project's own recordings (MIT), but they may contain
game names, unit names and UI text owned by the game's rights holders.

## 4. Third-party tools referenced (not bundled)

`agent-browser` (browser automation CLI), `uv`, and the decision-model endpoint
(local `clef-flash` via `llama.cpp`, or the TypeSafe Jev cloud API) are external
dependencies, each under its own license. See
[CONTRIBUTING.md](CONTRIBUTING.md#runtime-requirements).
