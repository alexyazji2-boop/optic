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
| `TRADIER_ACCESS_TOKEN` | Optional | Real-time chains instead of the ~15-min-delayed feed. |
| `PORT` | No | Railway sets it; the Dockerfile honours it. |

`ANTHROPIC_API_KEY` on a public URL means visitors spend your credits. The
per-IP cap in `_spend_guard` limits the damage but is not access control.

### 4. Sleep

Check the service cannot scale to zero. A sleeping container runs no timers, so
the scans and the morning brief never fire and the app is only as fresh as its
last visitor.

### 5. Domain

Settings → Networking → **Generate Domain** for a `*.up.railway.app` URL, or
**Custom Domain** and add the CNAME it gives you at your registrar.

## Updates are automatic after the first deploy

Railway watches the connected branch. `git push` → rebuild → live. There is no
separate deploy step.

Two things a push does *not* carry, both gitignored on purpose:

- **`.env`** — set variables in the dashboard instead.
- **`data/tracker.db`** — production keeps its own ledger on the volume. Local
  and hosted paper trades are separate records and never merge.

Returning visitors see changes immediately: `index.html` is served
`Cache-Control: no-cache`, so the browser revalidates instead of reusing a
cached copy. See `tests/test_asset_cache.py` — this regressed once, and a
stale-HTML bug presents as a deploy that appears to have done nothing.
