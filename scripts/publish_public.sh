#!/usr/bin/env bash
# Publish the code-only public history from this (private) working repository.
#
# The public repository is REGENERATED from here, so the two never drift:
#   1. clone this repo into a scratch directory
#   2. strip the private-only trees from every commit (git filter-repo)
#   3. re-add the small files that document those trees + a public .gitignore
#   4. verify (ruff + pytest) in the filtered checkout
#   5. force-push to the public repository
#
# Usage:  scripts/publish_public.sh [--dry-run]
# See docs/PUBLISHING.md for the model and the one-time setup.
set -euo pipefail

PUBLIC_REPO="${PUBLIC_REPO:-git@github.com:ys118/ra2web-jev-player.git}"
PRIVATE_REMOTE="${PRIVATE_REMOTE:-origin}"
BRANCH="${BRANCH:-master}"
SCRATCH="${SCRATCH:-$LOCALAPPDATA/Temp/ra2web-jev-player-public}"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$here"

echo "==> publishing $BRANCH from $here"
echo "    public repo : $PUBLIC_REPO"
echo "    scratch dir : $SCRATCH"
echo "    dry run     : $DRY_RUN"

# ---------- 1) fresh clone of the private repository ----------
rm -rf "$SCRATCH"
git clone --no-hardlinks --branch "$BRANCH" "$here" "$SCRATCH"
cd "$SCRATCH"

# ---------- 2) strip the private-only trees from all history ----------
uv tool run git-filter-repo --force --invert-paths \
    --path artifacts \
    --path dataset \
    --path references/research
# note: git-filter-repo drops the origin remote on purpose (history was rewritten)

# ---------- 3) re-add what the public tree should keep ----------
git checkout -b "$BRANCH"
mkdir -p artifacts dataset references/research
cp "$here/artifacts/README.md" artifacts/README.md
cp "$here/dataset/README.md" dataset/README.md
cp "$here/references/research/README.md" references/research/README.md
cat >> .gitignore <<'EOF'

# Match data is not published: keep a contributor's own runs out of commits.
# (The maintainer's data repository tracks these paths instead.)
artifacts/
dataset/
EOF
git add -A
git commit -q -m "chore: publish code-only tree (match data and third-party bulk stay private)

The public repository ships code, tests, scripts, docs, derived knowledge and the
official API reference snapshots. Recorded match data (artifacts/, dataset/) and
the data-mining material (references/research/) are kept in the private working
repository — see docs/PUBLISHING.md. This commit adds back the READMEs that
document those directories and ignores them so contributors' own match data is
never committed."

# ---------- 4) verify the public tree stands on its own ----------
echo "==> verifying the filtered checkout"
uv sync
uv run ruff check
uv run pytest -q

if [ "$DRY_RUN" = "1" ]; then
    echo "==> dry run: leaving the filtered checkout at $SCRATCH (not pushed)"
    exit 0
fi

# ---------- 5) push ----------
git remote add origin "$PUBLIC_REPO"
git push --force -u origin "$BRANCH"
echo "==> pushed. Flip visibility when ready:"
echo "    gh repo edit ys118/ra2web-jev-player --visibility public --accept-visibility-change-consequences"
