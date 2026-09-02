#!/usr/bin/env bash
# Publish whatever is on disk to the live site.
#
#   ./publish.sh "what changed"
#   ./publish.sh                  # writes a generic message
#
# Editing a file does not publish it. The local server picks changes up straight
# away because it runs with --reload, which makes it easy to believe the site has
# them too. It has not: the deploy is driven by a push, and until then the change
# exists only on this machine.
#
# So this does the whole chain in one command and then *verifies* it, rather than
# assuming: the live /api/health reports its own commit, and this waits for that
# to match what was just pushed. A green build is not the same as a live change,
# and a webhook that quietly stopped firing looks exactly like a slow build.
set -euo pipefail
cd "$(dirname "$0")"

LIVE="${OPTIC_LIVE_URL:-https://optic-terminal-production.up.railway.app}"
MSG="${1:-Update $(date -u +%Y-%m-%dT%H:%MZ)}"

if [ -z "$(git status --porcelain)" ]; then
  echo "Nothing to publish — no uncommitted changes."
  echo "Live is on $(curl -s --max-time 20 "$LIVE/api/health" | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p')"
  exit 0
fi

# Tests before the push, not after.
#
# The deploy is automatic, so a broken commit is a broken *website* about sixty
# seconds later. There is no review step between this command and strangers
# loading the page, which is exactly why the gate belongs here.
echo "Running tests…"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if ! .venv/bin/python -m pytest -q > /tmp/optic-publish-tests.log 2>&1; then
  echo
  echo "Tests failed — not publishing. Last lines:" >&2
  tail -20 /tmp/optic-publish-tests.log >&2
  exit 1
fi
echo "  $(tail -1 /tmp/optic-publish-tests.log)"

# Refuse to ship secrets. .gitignore already covers these, but `git add -A` plus
# a mistaken `git add -f` in some earlier session is all it would take.
if git status --porcelain | grep -qE '(^|/)\.env|tracker\.db|\.share/'; then
  echo "Refusing to publish: something sensitive is staged." >&2
  git status --porcelain | grep -E '(^|/)\.env|tracker\.db|\.share/' >&2
  exit 1
fi

git add -A
git commit -q -m "$MSG"
SHA=$(git rev-parse HEAD | cut -c1-12)
git push -q origin "$(git rev-parse --abbrev-ref HEAD)"
echo "Pushed $SHA. Waiting for the deploy…"

for i in $(seq 1 40); do
  LIVE_SHA=$(curl -s --max-time 20 "$LIVE/api/health" 2>/dev/null \
    | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p')
  if [ "$LIVE_SHA" = "$SHA" ]; then
    echo "Live: $LIVE is now running $SHA (took ~$((i*15))s)."
    exit 0
  fi
  sleep 15
done

echo >&2
echo "Pushed, but $LIVE is still on '${LIVE_SHA:-unknown}' after 10 minutes." >&2
echo "The commit is safe on GitHub. Check Railway's deploy log — a build this" >&2
echo "slow usually means it failed, or the GitHub webhook stopped firing." >&2
exit 1
