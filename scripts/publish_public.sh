#!/usr/bin/env bash
# Publish the code-only public mirror from this (private) working repository.
#
# The public repository is REGENERATED from here, so the two never drift:
#   1. clone this repo into a scratch directory (the branch you want to publish)
#   2. strip the private-only trees from every commit (git filter-repo)
#   3. re-add the small files that document those trees + the public .gitignore
#   4. verify (ruff + pytest) in the filtered checkout
#   5. push the filtered history as a branch and open/update a pull request
#      (master is protected: PR + review + CI, no direct pushes)
#
# Usage:
#   scripts/publish_public.sh                  # publish master (fast-forward expected)
#   scripts/publish_public.sh --dry-run        # build + verify locally, do not push
#   scripts/publish_public.sh --branch NAME    # publish a feature branch (for a public PR)
#   scripts/publish_public.sh --force          # allow a non-fast-forward push
#
# Merging that pull request with a merge commit keeps the filtered commits as
# ancestors, so the next publish only contains what actually changed. --force pushes
# straight to the branch and is reserved for filter-rule changes.
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

# ---------- 5) publish through a pull request ----------
# master on the public repository is protected: a pull request, one approving
# review and passing CI are required, and direct pushes are blocked. So the mirror
# is published as a branch plus a pull request that the maintainer merges (merge
# commit only — the filtered commits must become ancestors, otherwise every later
# publish would show the whole history as "new commits").
HEAD_BRANCH="${HEAD_BRANCH:-mirror/sync}"
[ "$BRANCH" != "master" ] && HEAD_BRANCH="$BRANCH"

git remote add origin "$PUBLIC_REPO" 2>/dev/null || true

if [ "$FORCE" = "1" ]; then
    git push --force origin "$BRANCH"
    echo "==> force-pushed '$BRANCH' to $PUBLIC_REPO (rule change; public history replaced)"
    exit 0
fi

# nothing new to publish? compare the filtered tree with the public master tree
git fetch --quiet "$PUBLIC_REPO" master 2>/dev/null || true
if git rev-parse --verify --quiet FETCH_HEAD >/dev/null && git diff --quiet FETCH_HEAD "$BRANCH"; then
    echo "==> public repository is already up to date (nothing to publish)"
    exit 0
fi

git push --force origin "$BRANCH:$HEAD_BRANCH"
echo "==> pushed the filtered history as branch '$HEAD_BRANCH'"

PR_URL="$(gh pr list --repo "$PUBLIC_REPO" --head "$HEAD_BRANCH" --state open --json url --jq '.[0].url' 2>/dev/null || true)"
if [ -n "$PR_URL" ]; then
    echo "==> pull request updated: $PR_URL"
else
    PR_URL="$(gh pr create --repo "$PUBLIC_REPO" --base master --head "$HEAD_BRANCH" \
        --title "chore: mirror sync from the private repository ($(date +%Y-%m-%d))" \
        --body "Code-only sync of the private working repository (source of truth).

Filtered with \`git filter-repo\`: match data (\`artifacts/\`, \`dataset/\`) and the
data-mining material (\`references/research/\`) never enter this history — see
docs/PUBLISHING.md.

The pull request exists because \`master\` is protected (pull request + review + CI,
no direct pushes). Merging it with a merge commit keeps the filtered commits as
ancestors, so later syncs only contain what actually changed.")"
    echo "==> pull request opened: $PR_URL"
fi
echo
echo "    next: review and merge it with a merge commit once CI is green:"
echo "      gh pr checks $PR_URL"
echo "      gh pr merge --merge $PR_URL"
