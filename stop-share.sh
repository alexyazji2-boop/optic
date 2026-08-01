#!/usr/bin/env bash
# Take the public test link down.
#
# Kills the detached share.sh, which runs its own cleanup trap and takes the
# server and tunnel with it. Falls back to matching on the command line if the
# pid file is missing or stale, so a link can always be shut off.
set -uo pipefail
cd "$(dirname "$0")"

stopped=0

if [ -f .share/detached.pid ]; then
  PID=$(cat .share/detached.pid)
  if kill -0 "$PID" 2>/dev/null; then
    # Signal the whole process group: share.sh, its uvicorn, and cloudflared all
    # share one, so a single TERM lets the trap tear the set down together.
    kill -TERM -- "-$(ps -o pgid= -p "$PID" | tr -d ' ')" 2>/dev/null || kill -TERM "$PID" 2>/dev/null
    stopped=1
  fi
  rm -f .share/detached.pid
fi

sleep 2

# Belt and braces: anything still holding the port or the tunnel goes now.
pkill -f 'caffeinate -is ./share.sh' 2>/dev/null && stopped=1
pkill -f 'cloudflared tunnel --url http://127.0.0.1:8077' 2>/dev/null && stopped=1
lsof -ti:8077 2>/dev/null | xargs -r kill -9 2>/dev/null && stopped=1

rm -f .share/url.txt
sleep 1

remaining=$(( $(lsof -ti:8077 2>/dev/null | wc -l) + $(pgrep -f 'cloudflared tunnel' | wc -l) ))
if [ "$remaining" -eq 0 ]; then
  echo "Stopped. The public link is dead and the port is free."
else
  echo "Warning: $remaining process(es) still alive on port 8077 or in cloudflared." >&2
  exit 1
fi
