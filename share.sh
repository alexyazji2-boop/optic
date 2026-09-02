#!/usr/bin/env bash
# Launch Optic Terminal behind a public HTTPS tunnel so other people can test it.
#
#   ./share.sh
#
# Prints a https://<random>.trycloudflare.com URL. There is no sign-in: anyone
# with the URL can use the terminal. Both the server and the tunnel run on this
# machine, so closing the laptop or stopping this script ends the session.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8077}"

# .env is the same file the app reads; source it so anything configured there
# (e.g. ANTHROPIC_API_KEY) reaches the server process.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Install it with: brew install cloudflared" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi

mkdir -p .share
: > .share/tunnel.log

cleanup() {
  # Kill the whole process group so the tunnel dies with the server rather than
  # leaving a public URL pointing at a port nothing is listening on.
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null || true
  [ -n "${TUNNEL_PID:-}" ] && kill "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# No --reload: this is a shared instance, and a file-watcher restart would drop
# every connected tester mid-request.
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
  > .share/server.log 2>&1 &
SERVER_PID=$!

printf 'Waiting for the server'
for _ in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz" || true)
  case "$code" in
    200) echo " ready."; break ;;
  esac
  printf '.'
  sleep 0.5
done

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo; echo "Server failed to start. Last lines of .share/server.log:" >&2
  tail -20 .share/server.log >&2
  exit 1
fi

# Pull the assigned quick-tunnel hostname out of cloudflared's log.
#
# The naive pattern for this was 'https://[a-z0-9-]+\.trycloudflare\.com', which
# also matches https://api.trycloudflare.com — a host cloudflared prints while
# registering, not the tunnel it hands you. With `head -1` that sometimes won the
# race, and the shared link became the API endpoint: it answered HTTP 405, the
# watchdog counted three failures and rotated an otherwise healthy tunnel. That
# happened for real at 2026-08-04T08:55Z and cost four minutes of downtime.
#
# Assigned hostnames are always several hyphen-separated words, so requiring at
# least one hyphen in the label excludes 'api' and the region hosts by
# construction rather than by keeping a denylist in sync.
extract_tunnel_url() {
  grep -oE 'https://[a-z0-9]+(-[a-z0-9]+)+\.trycloudflare\.com' .share/tunnel.log \
    | head -1
}

# --edge-ip-version 4 is not cosmetic. Left to itself cloudflared picked an IPv6
# edge here and lost the connection every three or four minutes; a free quick
# tunnel holds exactly one connection (--ha-connections is accepted and ignored),
# so each of those was a total outage and the browser saw 502/520/530. Measured
# on an IPv4 edge over the same span: zero drops, 53/53 probes at 200.
cloudflared tunnel --url "http://127.0.0.1:$PORT" \
  --edge-ip-version "${TUNNEL_EDGE_IP:-4}" --no-autoupdate \
  > .share/tunnel.log 2>&1 &
TUNNEL_PID=$!

printf 'Opening tunnel'
URL=""
for _ in $(seq 1 60); do
  URL=$(extract_tunnel_url || true)
  [ -n "$URL" ] && break
  printf '.'
  sleep 0.5
done
echo

if [ -z "$URL" ]; then
  echo "Tunnel did not report a URL. Last lines of .share/tunnel.log:" >&2
  tail -20 .share/tunnel.log >&2
  exit 1
fi

cat <<MSG

  ┌────────────────────────────────────────────────────────────┐
     Optic Terminal is live for testers

     URL:       $URL
     Access:    open — no sign-in required

     Logs:      .share/server.log  .share/tunnel.log
     Stop:      Ctrl-C (ends the tunnel and the server together)
  └────────────────────────────────────────────────────────────┘

MSG

# Supervise both halves.
#
# The server almost never dies. The *tunnel* does: a Cloudflare quick tunnel gets
# dropped from their side after an hour or so, and cloudflared does not recover on
# its own — it sits in a reconnect loop logging "control stream encountered a
# failure while serving" every ~64s while the hostname stops resolving. Observed
# three times in a row, roughly hourly. So the tunnel is probed and relaunched
# rather than waiting for it to exit, because it never does exit; it just stops
# working while still running.
#
# Relaunching means a NEW hostname — quick tunnels can't keep one. So the current
# URL is always written to .share/url.txt, and every rotation is logged with a
# timestamp, so whoever is sharing the link can see it moved and why.
#
# Polled rather than `wait -n`: macOS ships bash 3.2, where that flag doesn't
# exist and the script would exit instantly, tripping the cleanup trap.

PROBE_EVERY="${PROBE_EVERY:-60}"     # seconds between health probes
PROBE_FAILS="${PROBE_FAILS:-3}"      # consecutive failures before relaunching
fails=0

log_rotation() {
  printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >> .share/rotations.log
}
log_rotation "tunnel up at $URL"

while kill -0 "$SERVER_PID" 2>/dev/null; do
  sleep "$PROBE_EVERY"

  # The server is the thing testers actually need; if it has gone, stop.
  kill -0 "$SERVER_PID" 2>/dev/null || break

  # Probe via a dig-resolved IP rather than the system resolver.
  #
  # macOS caches negative DNS answers, and a brand-new quick-tunnel hostname gets
  # queried before its record exists — which poisons that cache for minutes. The
  # first version of this probe used the OS resolver and read "could not resolve"
  # as "tunnel is dead", so it rotated a perfectly healthy tunnel and then
  # rotated the replacement too. dig queries a nameserver directly, and --resolve
  # pins the connection to that answer, so the probe tests reachability instead of
  # this machine's cache.
  code="000"
  ip=$(dig +short "${URL#https://}" 2>/dev/null | grep -E '^[0-9.]+$' | head -1 || true)
  if [ -n "$ip" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
      --resolve "${URL#https://}:443:$ip" "$URL/healthz" || true)
  fi
  if [ "$code" = "200" ]; then
    fails=0
    continue
  fi

  fails=$((fails + 1))
  echo "Tunnel probe failed ($fails/$PROBE_FAILS), HTTP '$code'." >&2
  [ "$fails" -lt "$PROBE_FAILS" ] && continue

  # Confirm it is the tunnel and not the app before touching anything.
  #
  # This used to `break` on a single bad local probe, which ended supervision
  # permanently while the server carried on running — one slow request during a
  # universe scan (the probe allows 10s) was enough to retire the supervisor for
  # the rest of the session. The message said "not rotating the tunnel", which
  # reads as "will try again", and it never did.
  #
  # A transient local failure is now tolerated: the tunnel is left alone for this
  # pass and the next probe re-checks. The only condition that ends the loop is
  # the server process actually being gone, which the `while kill -0` at the top
  # already tests — so there is no need for a second, weaker exit here.
  local_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    "http://127.0.0.1:$PORT/healthz" || true)
  if [ "$local_code" != "200" ]; then
    echo "Local probe returned '$local_code' — leaving the tunnel alone this pass." >&2
    # Reset, so a spell of local slowness cannot bank three strikes and then
    # rotate a healthy tunnel the moment the app recovers.
    fails=0
    continue
  fi

  log_rotation "tunnel dead at $URL (public HTTP '$code', local 200) — relaunching"
  echo "Relaunching the tunnel…" >&2
  kill "$TUNNEL_PID" 2>/dev/null || true
  sleep 3
  : > .share/tunnel.log
  cloudflared tunnel --url "http://127.0.0.1:$PORT" \
  --edge-ip-version "${TUNNEL_EDGE_IP:-4}" --no-autoupdate \
    > .share/tunnel.log 2>&1 &
  TUNNEL_PID=$!

  NEW=""
  for _ in $(seq 1 60); do
    NEW=$(extract_tunnel_url || true)
    [ -n "$NEW" ] && break
    sleep 1
  done

  if [ -n "$NEW" ]; then
    URL="$NEW"
    echo "$URL" > .share/url.txt
    log_rotation "new URL $URL"
    echo "  New public link: $URL" >&2
    fails=0
    # Grace period: a fresh hostname is not resolvable everywhere for a little
    # while, and probing straight away rotates a tunnel that was about to work.
    sleep 45
  else
    log_rotation "relaunch failed to report a URL"
    echo "Relaunch produced no URL; will retry on the next probe." >&2
  fi
done
echo "Server exited — shutting down." >&2
