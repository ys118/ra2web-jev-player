# Publishing: the two-repository model

The project is maintained in two GitHub repositories:

| Repository | Visibility | Contents |
|---|---|---|
| `ys118/ra2web-jev-player` | **public** | Code, tests, scripts, docs, derived knowledge (`docs/knowledge/`), official API reference snapshots (`references/werhd/`). No recorded match data, no scraped third-party bulk. |
| `ys118/ra2web-jev-player-data` | private | Everything above **plus** the recorded match data (`artifacts/`, `dataset/`) and the data-mining material (`references/research/`). This is the working repository and the data archive. |

Why two repositories:

- **Data volume.** `artifacts/` (≈620 MB) and `dataset/` (≈100 MB) grow with every
  match. GitHub recommends repositories under 1 GB, and a public clone should not
  carry the maintainer's match archive.
- **Rights.** `references/research/` redistributes game assets (`rules.ini`,
  `ra2.csf`, engine bundles) and archived community guides. Keeping that out of
  the public tree removes the redistribution question entirely; the derived
  facts (`docs/knowledge/RA2-UNITS.json`) and the provenance description
  (`references/research/README.md`) are published instead.
- **Red lines.** `AGENTS.md` requires recorded data to be persisted with git and
  never deleted. The private repository keeps that guarantee; the public
  repository simply never contains it.

## Development workflow (user-mandated, 2026-10-09)

The rule, in one line: **the private repository is the source of truth and every
change is reviewed there first; the public repository is a regenerated mirror that
receives the same change through its own pull request.**

1. **Develop privately first.** Branch off `master` in the private repository, open
   a pull request there, merge it. All data-producing work (matches, dataset
   rebuilds) happens only here.
2. **Publish the mirror.** `scripts/publish_public.sh` regenerates the public
   history. The rewrite is deterministic, so this is normally a fast-forward and
   the public commit ids line up with the filtered private ones.
3. **The same change as a public pull request.** `scripts/publish_public.sh
   --branch <name>` pushes a data-free copy of that branch to the public
   repository; open the pull request there against `master` and merge it. The
   public review therefore sees exactly the change that was already reviewed
   privately, with no match data attached.
4. **Never let the two diverge.** A push rejected as non-fast-forward means the
   public repository has commits the private one does not (typically a pull
   request merged only there). Bring them in first —
   `git fetch public && git merge public/master` — then publish again. Use
   `--force` only when you intend to discard the public-side history.
5. **Keep code and data commits separate.** The filter drops the data part of a
   commit silently, which is correct but makes the public history harder to read if
   the two are mixed in one commit.

## Publishing a revision

The public history is **regenerated** from the private repository, so the two
never drift and no manual cherry-picking is needed. `scripts/publish_public.sh`
does it in one command (run from the private checkout):

```bash
scripts/publish_public.sh            # rebuild the public history locally and push
scripts/publish_public.sh --dry-run  # build and verify, do not push
```

What the script does:

1. Clones the private repository (with `--no-hardlinks`) into a scratch directory.
2. Runs `git filter-repo --invert-paths --path artifacts --path dataset
   --path references/research` to strip the private-only trees from **all**
   commits — including history, not just the tip.
3. Re-adds the small files that document the excluded trees (`artifacts/README.md`,
   `dataset/README.md`, `references/research/README.md`) and a public-only
   `.gitignore` that keeps a contributor's own match data out of commits.
4. Runs the test suite and the linter in the filtered checkout — the public tree
   must be green on its own (`tests/test_layout.py` skips the data assertions
   when the private data is absent).
5. Pushes the result to the public repository (force, because the history is
   rewritten by design).

Requirements: `git-filter-repo` (run through `uv tool run`, so no global install
is needed) and an authenticated `gh`/git for the push.

## One-time repository setup

```bash
# 1) rename the private working repository (old URLs redirect automatically)
gh repo rename ra2web-jev-player-data --repo ys118/ra2web-jev-player --yes
git remote set-url origin git@github.com:ys118/ra2web-jev-player-data.git

# 2) create the public repository and push the filtered history
gh repo create ys118/ra2web-jev-player --private \
  --description "Self-contained bot that plays single-player skirmish matches in the browser game Chrono Divide (web Red Alert 2)"
cd /path/to/scratch/ra2web-jev-player-public
git remote add origin git@github.com:ys118/ra2web-jev-player.git
git push -u origin master

# 3) when ready, make it public (this is the irreversible step)
gh repo edit ys118/ra2web-jev-player --visibility public --accept-visibility-change-consequences
```

After going public, finish the repository settings:

- Add topics: `red-alert-2`, `chrono-divide`, `game-bot`, `browser-automation`, `llm-agent`.
- Enable **Discussions** (the issue template's contact link points there).
- Enable **private vulnerability reporting** (referenced by `SECURITY.md`).
- Confirm the license is detected as MIT (GitHub reads `LICENSE`).
- CI runs on `master`; the badge in `README.md` starts reporting after the first
  public run.

## What the public tree deliberately excludes

| Excluded | Why | Where it lives |
|---|---|---|
| `artifacts/**` | recorded match data, ~620 MB | private repository |
| `dataset/**` (except its README) | training corpus and index | private repository |
| `references/research/**` (except its README) | game assets and archived community guides | private repository |

Everything else — including the per-match lesson ledger (`docs/LESSONS.md`) and
the operational hand-off notes (`docs/HANDOFF.md`) — is published. Those
documents reference data paths that do not exist in a public clone; that is
expected and stated in `docs/README.md`.
