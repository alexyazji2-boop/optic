# Deploying Optic Terminal

The app is a single FastAPI process that serves its own front end. It needs a
persistent disk for the ledger and it must not sleep, and those two constraints
rule out most of the free static hosts.

## Why not Netlify / Vercel

`netlify.toml` in this repo deploys the *front end only*, proxying `/api/*`
somewhere else. Three structural reasons it cannot host the whole thing:

1. **Request-scoped functions.** The 4-hourly scan loop and the 09:00 ET brief
   are background timers in a long-lived process. Serverless functions exist
   only while a request is open, so neither would ever fire.
2. **Ephemeral filesystem.** The paper-trading ledger is SQLite on disk. Each
   invocation gets a fresh container, so every position would vanish.
3. **10-second timeout.** A cold scan across the ranked universe takes longer.

## Railway

One service, built from the `Dockerfile` (`railway.json` pins this so the
builder cannot guess wrong).

### 1. Service

New Project → **Deploy from GitHub repo** → `alexyazji2-boop/optic`.

Deployed 2026-09-02 as the service `optic-terminal`, live at
<https://optic-terminal-production.up.railway.app>. The service name differs
from the repository name; only the repository the service is linked to decides
what a push deploys.

### 2. Volume — do this before the first real use

Service → **Data** → add a volume mounted at **`/app/data`**.

That path is not arbitrary: `TRACKER_DATA_DIR` already defaults to `/app/data`
in the Dockerfile, so mounting there needs no extra variable. Without a volume
the container still runs, but the ledger lives in the container filesystem and
resets on every deploy — a tracker that silently forgets.

### 3. Variables

| Variable | Needed? | Notes |
|---|---|---|
| `FEED_CONTACT` | Yes | Any contact email. SEC EDGAR returns 403 without a User-Agent that has one. |
| `ANTHROPIC_API_KEY` | Optional | Only Pulse needs it. Leave it unset and everything else works; Pulse reports it needs a key. |
| `AI_CALLS_PER_HOUR` | Optional | Per-visitor cap on assistant messages. Defaults to 30. `0` disables it. |
| `OPTIC_WRITE_TOKEN` | **Yes, in practice** | Gates the four endpoints that change the record. Unset on a hosting platform, they refuse with 503 rather than accepting anonymous writes. Generate with `openssl rand -hex 24`. |
| `TRADIER_ACCESS_TOKEN` | Optional | Real-time chains instead of the ~15-min-delayed feed. |
| `LEDGER_SNAPSHOT_HOURS` | Optional | Ledger snapshot interval, default 24. `0` disables. |
| `LEDGER_SNAPSHOT_KEEP` | Optional | How many snapshots to retain, default 7. |
| `PORT` | No | Railway sets it; the Dockerfile honours it. |

`ANTHROPIC_API_KEY` on a public URL means visitors spend your credits. The
per-IP cap in `_spend_guard` limits the damage but is not access control.

### 3b. Memory, and why the restart policy is ALWAYS

A scan screens the NASDAQ in chunks of 150 symbols, so it does not hold every
symbol's bars at once — `absorb()` reduces each chunk to a small metric dict and
the frames are then garbage. Peak is one chunk plus the ranking, which measured
around 700MB locally (`fly.toml` records the same figure).

On 2026-09-02 the service was OOM-killed twice on a low container limit. The
ledger survived both — it is on the volume — and the site served normally
between scans, which is what makes this easy to miss: the app is only fat while
scanning, so the symptom is a restart every four hours rather than a site that
is visibly down.

`restartPolicyType` is `ALWAYS`, not `ON_FAILURE` with a retry cap. A cap is
right for a startup crashloop and wrong here: the crash is periodic, so three
retries would be spent within half a day and the service would then stay down.
A genuine crashloop is still visible — `/api/health` reports `uptime_seconds`,
and an uptime that keeps resetting is the signal.

If OOM recurs on adequate memory, `TRACKER_UNIVERSE=watchlist` drops the screen
to ten megacaps and removes the peak entirely, at the cost of the thing the
screen is for.

### 4. Sleep

Check the service cannot scale to zero. A sleeping container runs no timers, so
the scans and the morning brief never fire and the app is only as fresh as its
last visitor.

### 5. Domain

Settings → Networking → **Generate Domain** for a `*.up.railway.app` URL, or
**Custom Domain** and add the CNAME it gives you at your registrar.

## Reads are open, writes are not

There is no sign-in and every research endpoint answers anybody. Four endpoints
change stored state and are gated by `OPTIC_WRITE_TOKEN`:

    POST /api/tracker/scan       opens paper positions
    POST /api/tracker/mark       re-marks open positions
    POST /api/alerts/clear       deletes the alert inbox
    POST /api/catalysts/refresh  spends requests and writes to the store

Without that gate the hosted ledger is a shared scratchpad: a stranger adding
trades is indistinguishable from the owner doing it, which destroys the only
thing a track record is for.

The unset case fails closed on a host and open locally, decided by whether a
platform announces itself in the environment (`RAILWAY_ENVIRONMENT` and
friends). Refusing outright would break a laptop checkout that never had a
token; allowing outright would leave a forgotten deployment wide open.

The browser prompts for the token once on the first 401 and keeps it in
localStorage. Scheduled scans are unaffected — the gate is on HTTP, not on the
background loop, so the record keeps building whether or not a token is set.

## Ledger snapshots

The tracker loop copies the ledger to `snapshots/` beside it once a day via
sqlite's backup API, keeping the last 7. `GET /api/snapshots` lists them.

They cover corruption and accidental wipes, not loss of the volume — the copies
live on the same disk. Off-host backup needs somewhere to put them and is a
separate job.

## Updates are automatic after the first deploy

Railway watches the connected branch. `git push` → rebuild → live in about a
minute. There is no separate deploy step.

Use `./publish.sh "what changed"` rather than pushing by hand: it runs the tests
first (the deploy is automatic, so a broken commit is a broken website sixty
seconds later), refuses to ship anything sensitive, and then waits for the live
`/api/health` to report the pushed commit. A green build is not the same as a
live change, and a webhook that has stopped firing looks exactly like a slow
build.

Two things a push does *not* carry, both gitignored on purpose:

- **`.env`** — set variables in the dashboard instead.
- **`data/tracker.db`** — production keeps its own ledger on the volume. Local
  and hosted paper trades are separate records and never merge.

Returning visitors see changes immediately: `index.html` is served
`Cache-Control: no-cache`, so the browser revalidates instead of reusing a
cached copy. See `tests/test_asset_cache.py` — this regressed once, and a
stale-HTML bug presents as a deploy that appears to have done nothing.
