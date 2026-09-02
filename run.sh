#!/usr/bin/env bash
# Start the terminal at http://127.0.0.1:8077
#
# For real-time quotes and options chains instead of the free ~15-min-delayed
# yfinance feed, export a Tradier access token before running this script:
#   export TRADIER_ACCESS_TOKEN=your_token_here
#   export TRADIER_SANDBOX=false   # true only if using a sandbox/paper account
# Get a token from your Tradier account: Settings -> API Access. No brokerage
# activity is required, just an account with market-data API access enabled.
set -euo pipefail
cd "$(dirname "$0")"

# Load .env the same way share.sh does. Without this the local server starts with
# no ANTHROPIC_API_KEY and no FEED_CONTACT, so Pulse silently comes up disabled
# and SEC EDGAR starts returning 403 — while the tunnelled server, which does
# source it, works fine. Two servers behaving differently for invisible reasons.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8077 --reload
