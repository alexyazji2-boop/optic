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
| `EARNINGS_BRIEFS_PER_DAY` / `SECTOR_READS_PER_DAY` / `CATALYST_READS_PER_DAY` | Optional | Ceilings on new model-written earnings briefs, sector reads and catalyst reads over a rolling 24 hours, counted from the ledger. Defaults 30 / 30 / 24. Writing an earnings brief also needs an account and spends one of its assistant messages (`POST /api/earnings/{T}/brief`); reading a written one is free. Kept pieces are always served; `0` switches a writer off. |
| `OPTIC_WRITE_TOKEN` | **Yes, in practice** | Gates the four endpoints that change the record, and `force` on the weekly update. Unset on a hosting platform, they refuse with 503 rather than accepting anonymous writes. Generate with `openssl rand -hex 24`. |
| `TRADIER_ACCESS_TOKEN` | Optional | Real-time chains instead of the ~15-min-delayed feed. |
| `LEDGER_SNAPSHOT_HOURS` | Optional | Ledger snapshot interval, default 24. `0` disables. |
| `LEDGER_SNAPSHOT_KEEP` | Optional | How many snapshots to retain, default 7. |
| `PORT` | No | Railway sets it; the Dockerfile honours it. |

`ANTHROPIC_API_KEY` on a public URL means visitors spend your credits. Accounts
change the shape of that exposure rather than removing it: a guest now gets a small
daily allowance and an account gets its plan's, so a stranger with the URL can spend
a few messages instead of the balance. Still not access control.

### 3a. Variables for accounts

Sign-in works with **none** of these set: email and password accounts and passkeys
need no third party. Each provider reports what it is missing and its button stays
hidden until it has it, the same contract `ANTHROPIC_API_KEY` already uses.

| Variable | Needed? | Notes |
|---|---|---|
| `APP_URL` | **Yes, with a custom domain** | `https://theopticterminal.com`, no trailing slash. The OAuth redirect URIs, the WebAuthn RP id and the links inside verification emails all derive from it. Not read from the Host header on purpose: that header is attacker-controlled, and a reset link built from one can be aimed elsewhere. **Set it even though the site currently works without it.** Unset, `base_url()` tries `RAILWAY_PUBLIC_DOMAIN` before falling back to the hardcoded domain, and that variable is empty on this project only by chance. If Railway ever populates it the WebAuthn RP id silently becomes the `railway.app` host, which invalidates every passkey already registered and breaks the OAuth redirect. |
| `ADMIN_EMAILS` | For the owner | Comma-separated addresses that own this deployment. A listed account whose address is **confirmed** may run the four write endpoints without `OPTIC_WRITE_TOKEN`, and is not metered against the assistant's daily cap. The confirmation half is the security: anyone can type any address into the signup form, so without it the first stranger to register with your address would own the deployment. Not a column on `users`, so a restored backup cannot mint an owner. Unset, nothing changes. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | For Google | Cloud console, OAuth client ID, Web application. Authorised redirect URI must be exactly `https://theopticterminal.com/api/auth/google/callback`. |
| `APPLE_CLIENT_ID` / `APPLE_TEAM_ID` / `APPLE_KEY_ID` / `APPLE_PRIVATE_KEY` | For Apple | Needs a paid Apple Developer membership. `APPLE_CLIENT_ID` is the **Service ID**, not the App ID. The private key is the whole `.p8` contents; a literal `\n` from a dashboard paste is accepted and converted, which is the most common reason the token exchange fails with an unhelpful `invalid_client`. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `EMAIL_FROM` | **Yes, before inviting readers** | Verification and reset links. When these are unset, nothing is emailed and the UI says so instead of claiming mail was sent. On a host, only links for `ADMIN_EMAILS` addresses are written to the server log, so the owner can still confirm their own address; other readers' links and addresses are withheld, because a logged reset link is a sign-in for anyone who can read the log. Locally every link is logged. Port 465 is implicit TLS; anything else opens in the clear and upgrades with STARTTLS. `EMAIL_FROM` must be an address on a domain the relay is allowed to send for (SPF and DKIM set up at the provider), or messages land in spam or are refused. |
| `MAIL_LOG_LINKS` | Rarely | `true` logs every reader's link on a host as well; `false` logs none, including the owner's. Unset follows the rule in the row above. |
| `GUEST_AI_CALLS_PER_DAY` | Optional | Assistant messages a guest gets per day. Default **0**, which means Pulse takes a free account. Set it above zero to re-open Pulse to guests. Signing in gives the plan's allowance (Free is 5). |
| `WEBAUTHN_RP_ID` / `WEBAUTHN_ORIGIN` | Rarely | Both derive from `APP_URL`. Set `RP_ID` only to bind passkeys to a parent domain; `WEBAUTHN_ORIGIN` takes extra comma-separated origins, which is what a DNS move needs so assertions from the old domain still verify. |
| `SESSION_TTL_SECONDS` | Optional | Default 30 days, slid forward on use. |
| `COOKIE_SECURE` | No | Decided by whether a hosting platform is present. Secure on the live site, not on `http://localhost` where the browser would silently drop the cookie. |

Google's redirect URI has to match **character for character**, including the scheme
and any trailing slash. A mismatch is rejected by Google before the app is reached,
so there is nothing in the server log to find.

Apple needs HTTPS and a real domain and therefore cannot be tested on localhost.
Passkeys can, but only at `http://localhost:8000` and not at `http://127.0.0.1:8000`:
an IP address is not a valid WebAuthn RP id and the browser rejects the ceremony with
a `SecurityError` before any request is sent.

### 3b. Migrations

There is no deploy step. The schema is brought up to date by a startup handler in
`app/main.py`, because the deploy *is* a `git push` and there is no place to run a
command between the build finishing and the container serving traffic. The runner is
idempotent and forward-only, and it records what it has applied in
`schema_migrations`.

To run it by hand:

    .venv/bin/python -m app.db migrate
    .venv/bin/python -m app.db status

A failure is logged and does **not** take the site down: every research endpoint works
without the accounts database, and sign-in is the only thing that stops.

### 3c. Memory, and why the restart policy is ALWAYS

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
screen is for. The default, `curated` (86 large names and index funds, since
2026-09-29), still runs the NASDAQ-wide screen on each scan, because the Scan,
Explore and Priority pages read its ranking; `watchlist` skips it, and those
pages then show a ranking that ages.

### 4. Sleep

Check the service cannot scale to zero. A sleeping container runs no timers, so
the scans and the morning brief never fire and the app is only as fresh as its
last visitor.

### 5. Domain

Settings → Networking → **Generate Domain** for a `*.up.railway.app` URL, or
**Custom Domain** and add the CNAME it gives you at your registrar.

## Reads are open, writes are not

Every research endpoint answers anybody, with or without an account. Accounts exist so
a watchlist and saved research can be *kept*; they gate nothing that worked before.

The one thing that **takes** an account is the assistant, because it spends money
per call and an address is the only thing that can be metered: metered by IP it
was also the easiest thing here to get more of, since a new address is a new
allowance. A guest gets `GUEST_AI_CALLS_PER_DAY` messages a day, which defaults
to 0 and refuses with a 401 naming the way in; an account gets its plan's
allowance (Free is 5); and the per-address hourly cap sits over both as the
burst limit. Set `GUEST_AI_CALLS_PER_DAY` above zero to re-open it to guests.

Four endpoints change the shared paper-trading record and are gated by
`OPTIC_WRITE_TOKEN` rather than by an account, because that record belongs to the
operator and not to any user:

    POST /api/tracker/scan       opens paper positions
    POST /api/tracker/mark       re-marks open positions
    POST /api/alerts/clear       deletes the alert inbox
    POST /api/catalysts/refresh  spends requests and writes to the store

Without that gate the hosted ledger is a shared scratchpad: a stranger adding
trades is indistinguishable from the owner doing it, which destroys the only
thing a track record is for.

`GET /api/weekly?force=true` is behind the same guard. It writes the week's
update again, a model call of up to 6,000 output tokens and about 56 seconds
(measured 2026-09-28), and replaces it for every reader, so while it was open
anyone could spend on the operator's key and change the week's headline. A
refused `force` gets the guard's status and a sentence saying what it needs,
rather than the kept update served as if nothing was asked. A plain
`GET /api/weekly` stays open to everyone, and the week's first write is still
whichever reader loads it first. To force it:

    curl -H "X-Optic-Token: $OPTIC_WRITE_TOKEN" "https://theopticterminal.com/api/weekly?force=true"

A signed-in owner can do it from the browser console on the site, which can
send the page's CSRF header:
`fetch('/api/weekly?force=true', {headers: {'X-Optic-CSRF': OpticAuth.csrf()}})`.
Typed into the address bar it is refused with 403, because a link from another
site looks exactly the same.

The unset case fails closed on a host and open locally, decided by whether a
platform announces itself in the environment (`RAILWAY_ENVIRONMENT` and
friends). Refusing outright would break a laptop checkout that never had a
token; allowing outright would leave a forgotten deployment wide open.

The browser prompts for the token once on the first 401 and keeps it in
localStorage. Scheduled scans are unaffected — the gate is on HTTP, not on the
background loop, so the record keeps building whether or not a token is set.

## What is on the volume now

    /app/data/tracker.db     the shared paper-trading ledger
    /app/data/alerts.db      the alert inbox
    /app/data/accounts.db    accounts, sessions, passkeys, watchlists, saved research
    /app/data/snapshots/     dated copies of the ledger and of accounts.db

`accounts.db` is a separate file from the ledger on purpose. The ledger is the
*system's* record, identical for every visitor; `accounts.db` is *people's* data.
Different blast radius, different backup story, and a migration that takes a write
lock on one must not stall the other.

**Both are snapshotted daily, on the same volume.** `accounts.db` gained its copy in
the readiness work of 2026-10-23 (F-40) and 2026-10-27: `accounts-<stamp>.db`, the
last 7 kept (`ACCOUNTS_SNAPSHOT_KEEP`), on the ledger's schedule
(`LEDGER_SNAPSHOT_HOURS`). They are not listed by the open `GET /api/snapshots`.

Each accounts copy has every brokerage data key blanked and is vacuumed, because
deleting a reader's wrapped key is how their brokerage data is deleted, backups
included (`app/vault.py`). Restoring one brings back accounts, plans, watchlists and
saved research. Linked readers then reconnect their broker; the provider user ids
are kept, so the old provider users can be removed. An account deleted before a
snapshot is not in it; one deleted after stays in the older copies until they are
pruned, at most `ACCOUNTS_SNAPSHOT_KEEP` days later.

**Check a restore, without touching the live file**, from a shell on the running
service, where the volume is mounted (`railway ssh`, or the service's shell in the
dashboard; `railway run` executes on your own machine and cannot see the volume):

    python -m app.snapshots verify            # the newest accounts snapshot
    python -m app.snapshots verify /app/data/snapshots/accounts-<stamp>.db

It copies the snapshot to a temporary directory, runs SQLite's integrity check,
confirms every accounts migration this code knows is already applied, counts users,
sessions, watchlists and the rest, confirms the brokerage data keys are blank, and
deletes the copy. Exit status 0 means it would restore. Tested locally in
`tests/test_accounts_restore.py`; it has not been run against production's files.

**Still missing: an off-host copy, and it is the owner's to set up.** These snapshots
cover corruption and an accidental wipe, not loss of the volume or the Railway
project. What it needs:

1. A destination the owner controls and pays for (an S3-compatible bucket such as
   Cloudflare R2 or Backblaze B2, with versioning or object lock on).
2. A scheduled copy of the newest `snapshots/accounts-*.db` and `snapshots/tracker-*.db`
   there, daily, encrypted at rest. A Railway cron service running
   `rclone copy /app/data/snapshots remote:optic-backups` is one way; it needs the
   bucket's credentials as Railway variables.
3. `OPTIC_DATA_KEY` (and `OPTIC_WRITE_TOKEN`) stored somewhere else again, such as a
   password manager. Never in the bucket beside the files. Without the key a restored
   copy still has accounts and watchlists but no brokerage data, by design.
4. A restore drill into a separate Railway environment or a laptop, using the command
   above, once after setup and then on a schedule. Until one has succeeded, this is
   not disaster recovery.

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

- **`.env`** — set variables in the dashboard instead. `.env.example` is committed and
  lists every name with what it adds.
- **`data/tracker.db`** and **`data/accounts.db`** — production keeps its own ledger and
  its own accounts on the volume. Local and hosted records are separate and never
  merge. There is no path that copies accounts anywhere.

Returning visitors see changes immediately: `index.html` is served
`Cache-Control: no-cache`, so the browser revalidates instead of reusing a
cached copy. See `tests/test_asset_cache.py` — this regressed once, and a
stale-HTML bug presents as a deploy that appears to have done nothing.
