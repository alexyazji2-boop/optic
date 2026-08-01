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
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8077 --reload
