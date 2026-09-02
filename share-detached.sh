#!/usr/bin/env bash
# Start the public test link in its own session, detached from this terminal.
#
#   ./share-detached.sh          # start, print the URL, return
#   ./stop-share.sh              # stop it
#
# Why this exists: ./share.sh runs in the foreground and dies with whatever
# launched it — a terminal, an editor, an agent session. Worse, its cleanup trap
# fires on SIGTERM, so a parent shutting down deliberately takes the tunnel with
# it. That trap is correct (a live URL pointing at a dead port is worse than no
# URL), so this doesn't remove it — it moves share.sh into a *new session* via
# setsid, where the parent's teardown signal can't reach it. The trap still runs
# if share.sh itself exits, so the cleanup guarantee survives.
#
# What this does NOT do: survive a reboot or a full system sleep. For that you
# want a LaunchAgent, which is a different trade — a public URL coming back up
# unattended every time you log in.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .share/detached.pid ] && kill -0 "$(cat .share/detached.pid)" 2>/dev/null; then
  echo "Already running (pid $(cat .share/detached.pid))." >&2
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' .share/tunnel.log 2>/dev/null | head -1 >&2 || true
  echo "Stop it with ./stop-share.sh first." >&2
  exit 1
fi

mkdir -p .share
: > .share/tunnel.log

# macOS has no setsid(1), so Python provides it. start_new_session=True calls
# setsid(2) in the child, giving it a fresh session and process group.
#
# caffeinate -is keeps the machine awake while it runs; without it the tunnel
# drops the moment the display sleeps.
.venv/bin/python - <<'PY'
import os, subprocess
proc = subprocess.Popen(
    ["caffeinate", "-is", "./share.sh"],
    # Appended, not truncated. This log is the only record of why the
    # supervisor did what it did, and opening it "wb" wiped the evidence for the
    # previous incident every time the share was restarted — which is precisely
    # when you restart, so the post-mortem was never available.
    stdout=open(".share/share-stdout.log", "ab"),
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    start_new_session=True,
)
with open(".share/detached.pid", "w") as fh:
    fh.write(str(proc.pid))
print("started pid", proc.pid)
PY

printf 'Opening tunnel'
URL=""
for _ in $(seq 1 90); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' .share/tunnel.log 2>/dev/null | head -1 || true)
  [ -n "$URL" ] && break
  printf '.'
  sleep 1
done
echo

if [ -z "$URL" ]; then
  echo "No URL appeared. Last lines of .share/tunnel.log:" >&2
  tail -20 .share/tunnel.log >&2
  exit 1
fi

echo "$URL" > .share/url.txt

# No watchdog started here, deliberately.
#
# share.sh already supervises its own tunnel: it probes /healthz every 60s via a
# dig-resolved IP and rotates after three consecutive failures. tunnel-watchdog.sh
# is the standalone alternative for when share.sh is NOT running, and it refuses
# to start alongside it — correctly, since two supervisors racing to remint the
# same tunnel is how you churn through hostnames.
#
# Tried starting it here and it declined with "share.sh is running and already
# supervises its tunnel", which is the right answer. Leaving the note so the next
# person does not repeat the attempt.

echo
echo "  Public link:  $URL"
echo
echo "  Detached — survives closing this terminal. Stop it with ./stop-share.sh"
echo "  Dies on reboot or full system sleep. The URL changes on every restart."
