#!/bin/bash
# Keep the public link alive.
#
# Quick tunnels drop their control stream for no reason a user can act on, and
# when that happens the link is dead until somebody notices. Twice in one session
# it was down for hours. This watches the PUBLIC url rather than the local
# server, because the local server being up is exactly the case where the outage
# is invisible from here.
#
# It cannot keep the hostname stable — quick tunnels get a fresh random name on
# every start, and that is a property of the free tier, not something a script
# can fix. What it does is make the dead window a minute instead of an evening,
# and record the new URL where the rest of the tooling looks for it.
set -uo pipefail
cd "$(dirname "$0")"

URL_FILE=".share/url.txt"
LOG=".share/watchdog.log"
TUNNEL_LOG=".share/tunnel.log"
CHECK_EVERY="${WATCHDOG_INTERVAL:-60}"
# How long to give a fresh tunnel before calling it failed. Measured: a new
# hostname took 75s once and over 90s another time, so 90 was too tight and the
# watchdog kept declaring failure on tunnels that were about to work.
STARTUP_GRACE="${WATCHDOG_GRACE:-210}"

# Minimum gap between restart ATTEMPTS, regardless of what the checks say.
#
# Without this the watchdog defeats itself: every restart mints a fresh random
# hostname, DNS takes a minute or two to propagate, and a watchdog that gives up
# before then restarts again — churning through hostnames forever and never
# letting one settle. Observed doing exactly that: three hostnames in four
# minutes, none of which lived long enough to resolve.
RESTART_COOLDOWN="${WATCHDOG_COOLDOWN:-420}"
LAST_RESTART=0

log() { printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$LOG"; }

origin_up() {
  local code
  code=$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    "http://127.0.0.1:${PORT:-8077}/" 2>/dev/null)
  [ "$code" = "200" ]
}

public_up() {
  local url code
  [ -s "$URL_FILE" ] || return 1
  url=$(cat "$URL_FILE")
  code=$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$url/" 2>/dev/null)
  [ "$code" = "200" ]
}

# Measured, not assumed. --protocol http2 was pinned here after an earlier
# outage got blamed on QUIC; the actual cause that time turned out to be an
# expired tunnel, and the flag stuck around. On http2 cloudflared picked an IPv6
# edge and lost the connection every three or four minutes. cloudflared's own
# precheck reports QUIC healthy on this network, and on QUIC over an IPv4 edge it
# ran clean. Both are set explicitly so a recovery reproduces the configuration
# that was tested rather than whatever the default happens to be.
#
# --ha-connections is deliberately absent: a free quick tunnel accepts the flag
# and still opens exactly one connection, so there is no redundancy to ask for.
# That is why a drop is a full outage, and why the front end retries reads.
EDGE_IP_VERSION="${WATCHDOG_EDGE_IP:-4}"

restart_tunnel() {
  log "restarting tunnel"
  # TERM first, then make sure. A cloudflared stuck in its retry loop can ignore
  # TERM, and the old code slept four seconds and started a second process
  # regardless — two tunnels, two hostnames, and the url file naming whichever
  # one lost the race.
  pkill -f "cloudflared tunnel" 2>/dev/null
  local waited=0
  while pgrep -f "cloudflared tunnel" >/dev/null && [ "$waited" -lt 10 ]; do
    sleep 1; waited=$((waited + 1))
  done
  if pgrep -f "cloudflared tunnel" >/dev/null; then
    log "cloudflared ignored TERM after ${waited}s — sending KILL"
    pkill -9 -f "cloudflared tunnel" 2>/dev/null
    sleep 2
  fi
  : > "$TUNNEL_LOG"
  nohup cloudflared tunnel --url "http://127.0.0.1:${PORT:-8077}" \
    --edge-ip-version "$EDGE_IP_VERSION" --no-autoupdate \
    >> "$TUNNEL_LOG" 2>&1 &

  # Wait for a hostname, then for DNS to catch up with it.
  local waited=0 url="" recorded=""
  while [ "$waited" -lt "$STARTUP_GRACE" ]; do
    sleep 6; waited=$((waited + 6))
    url=$(grep -oE "https://[a-z0-9]+-[a-z0-9-]+\.trycloudflare\.com" "$TUNNEL_LOG" | tail -1)
    [ -n "$url" ] || continue

    # Record the hostname the moment cloudflared prints it, not once it serves.
    #
    # This was the bug that made the watchdog worse than useless. If the grace
    # ran out before the new hostname resolved, the url file still named the
    # DEAD one — so every later check tested a hostname nothing was listening
    # on, failed, and restarted again on the next cooldown. The live tunnel was
    # sitting there working the whole time under a name nothing had written
    # down, and the watchdog churned through hostnames on top of it.
    if [ "$url" != "$recorded" ]; then
      printf '%s\n' "$url" > "$URL_FILE"
      recorded="$url"
      log "new hostname $url — recorded, waiting for it to answer"
    fi

    if [ "$(/usr/bin/curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url/")" = "200" ]; then
      log "back up at $url after ${waited}s"
      return 0
    fi
  done
  # The hostname is already in the url file, so a tunnel that comes up late is
  # simply found healthy by the next ordinary check rather than restarted again.
  log "tunnel did not answer within ${STARTUP_GRACE}s (hostname ${url:-none} recorded anyway)"
  return 1
}

# Refuse to run alongside share.sh.
#
# share.sh has its own probe loop, and it is the better of the two: it waits for
# three consecutive failures instead of acting on one, and it resolves the
# hostname with dig and pins the request with --resolve, which is the only way to
# get a truthful answer on macOS — the OS caches negative DNS results, so a
# brand-new quick-tunnel hostname reads as "does not exist" for minutes after it
# starts working. This script uses the system resolver, so run alongside share.sh
# it declares a healthy new tunnel dead and rotates it. Observed doing exactly
# that: started at 21:20:27, and at 21:20:27 killed the tunnel share.sh had just
# raised, leaving two cloudflared processes and costing three minutes and two
# hostnames to get back to where it started.
#
# This script is for a bare `cloudflared` started by hand, with nothing else
# supervising it.
if pgrep -f "share\.sh" >/dev/null 2>&1; then
  echo "share.sh is running and already supervises its tunnel — not starting." >&2
  echo "Stop it with ./stop-share.sh first if you want this watchdog instead." >&2
  exit 1
fi

log "watchdog started, checking every ${CHECK_EVERY}s"
while true; do
  if ! origin_up; then
    # Nothing to expose. Restarting the tunnel would only produce a new URL
    # pointing at a dead port, so say so and wait.
    log "origin on :${PORT:-8077} is down — not touching the tunnel"
  elif ! public_up; then
    now=$(date +%s)
    if [ $((now - LAST_RESTART)) -lt "$RESTART_COOLDOWN" ]; then
      # Still inside the cooldown. The most recent restart may simply not have
      # propagated yet, and restarting again would throw away a hostname that is
      # about to start working.
      log "public link still down, but a restart was $((now - LAST_RESTART))s ago — waiting"
    else
      log "public link is down while the origin is up"
      LAST_RESTART=$now
      restart_tunnel
    fi
  fi
  sleep "$CHECK_EVERY"
done
