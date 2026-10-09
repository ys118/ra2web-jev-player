#!/usr/bin/env bash
# Publish the code-only public mirror from this (private) working repository.
#
# The public repository is REGENERATED from here, so the two never drift:
#   1. clone this repo into a scratch directory (the branch you want to publish)
#   2. strip the private-only trees from every commit (git filter-repo)
#   3. re-add the small files that document those trees + the public .gitignore
#   4. verify (ruff + pytest) in the filtered checkout
#   5. push to the public repository
#
# Usage:
#   scripts/publish_public.sh                  # publish master (fast-forward expected)
#   scripts/publish_public.sh --dry-run        # build + verify locally, do not push
#   scripts/publish_public.sh --branch NAME    # publish a feature branch (for a public PR)
#   scripts/publish_public.sh --force          # allow a non-fast-forward push
#
# The rewrite is deterministic (same inputs + same rules => same commit ids), so a
# normal publish is a fast-forward. A rejected push means the public repository has
# commits this one does not (for example a PR merged only there): pull them into the
# private repository first, or pass --force if you really mean to discard them.
# See docs/PUBLISHING.md for the model, the workflow and the one-time setup.
set -euo pipefail

PUBLIC_REPO="${PUBLIC_REPO:-git@github.com:ys118/ra2web-jev-player.git}"
BRANCH="${BRANCH:-master}"
SCRATCH="${SCRATCH:-${TMPDIR:-/tmp}/ra2web-jev-player-public}"
DRY_RUN=0
FORCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --force)   FORCE=1 ;;
        --branch)  BRANCH="${2:?--branch needs a name}"; shift ;;
        -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$here"

echo "==> publishing branch '$BRANCH' from $here"
echo "    public repo : $PUBLIC_REPO"
echo "    scratch dir : $SCRATCH"
echo "    dry run     : $DRY_RUN   force: $FORCE"

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
# (git-filter-repo keeps the branch name, so no checkout needed)
mkdir -p artifacts dataset references/research
cp "$here/artifacts/README.md" artifacts/README.md
cp "$here/dataset/README.md" dataset/README.md
cp "$here/references/research/README.md" references/research/README.md
# .gitignore: use the published-repository variant (data paths ignored)
cp "$here/scripts/public.gitignore" .gitignore
git add -A
git add -f artifacts/README.md dataset/README.md references/research/README.md
if ! git diff --cached --quiet; then
    git commit -q -m "chore: publish code-only tree (match data and third-party bulk stay private)

The public repository ships code, tests, scripts, docs, derived knowledge and the
official API reference snapshots. Recorded match data (artifacts/, dataset/) and
the data-mining material (references/research/) are kept in the private working
repository — see docs/PUBLISHING.md. This commit adds back the READMEs that
document those directories and ignores them so contributors' own match data is
never committed."
fi

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
if [ "$FORCE" = "1" ]; then
    git push --force -u origin "$BRANCH"
else
    if ! git push -u origin "$BRANCH"; then
        cat >&2 <<'EOF'

==> push rejected: the public repository has commits this repository does not.
    Either bring them in first (recommended):

        git remote add public git@github.com:ys118/ra2web-jev-player.git
        git fetch public && git merge public/master     # data-free by construction
        scripts/publish_public.sh

    or re-run with --force to replace them (their history is then lost).
EOF
        exit 1
    fi
fi
echo "==> pushed branch '$BRANCH' to $PUBLIC_REPO"
