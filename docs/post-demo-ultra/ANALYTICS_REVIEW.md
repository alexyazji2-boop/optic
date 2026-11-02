# User analytics review (Phase 10, 2026-10-30)

> **Acted on in Phase 10:** the access log now blanks search text (`q=`) as well as one-time tokens, and the Metrics
> page labels earnings briefs ("Earnings briefs") instead of showing the raw id. The event design below is a proposal:
> it needs Privacy policy and Metrics page wording, counsel's review and the owner's decisions (BLOCKERS BL-02).

Directive 10, section 9. Repository `~/Optic/wt-ultra`, branch `post-demo-ultra`, committed state `3698975` (Phase 09) plus the uncommitted Phase 10 edits present on 2026-10-30 between 07:00 and 08:00 ET. Review date 2026-10-30.

**Method.** Read the server and both front ends; searched `static/v2/js` and `static/app.js` for `sendBeacon`, beacon, analytics, telemetry, track, `PerformanceObserver`, `performance.mark`, error hooks and every analytics vendor name I know; read the Privacy page source. Nothing was implemented, no file in the checkout was changed, no server was started and no request was made to the production site. Line numbers are from the working tree at that time; `app/main.py`, `app/ai.py`, `app/metrics.py`, `app/auth/routes.py`, `app/auth/store.py`, `app/auth/ratelimit.py`, `app/feedback.py` and `static/app.js` carried uncommitted edits and their numbers may move, so each citation names the function or constant beside it.

## 1. Summary

1. **No front-end telemetry exists.** Neither front end sends beacons, page views, timings, errors or events to Optic or to anyone else. The only client-to-server reports are Problem Reports the reader writes, including Milo's "report this answer". The one analytics script on the site is Cloudflare's Web Analytics, which Cloudflare adds to pages at the edge, not in Optic's source; the Privacy page discloses it, and its source comment records seeing it on the live site on 2026-10-26 (`legalpages.js:46-48`). I made no request to the live site to re-check.
2. **What Optic measures itself:** which days an account used Optic and one row per Milo question by surface (`app/metrics.py`), one row per model call with its tokens and outcome but no account (`app/ai_store.py`), the brokerage connection's current state, rate-limit rows that are hashed and gone within a day, and the server log (IP, path, query string, status; one timing line per Milo answer).
3. **The seven event families:** none is fully measurable. Milo submission success and failure, brokerage connection failures, Dossier usage and feature engagement are **partly** measurable. Onboarding completion, search success and failure, and abandoned flows are **not** measurable, apart from the count of accounts that never confirmed their email.
4. **Recommendation (not implemented):** one table of daily counts by family, event and coarse outcome, with no account id, no IP, no symbol, no free text, no holdings and no account numbers; incremented on the server wherever the server already knows the outcome, plus a small allow-list route for the few facts only the browser knows (the first-visit card, whether a search result was opened, which page or Dossier tab is open, and a Milo send that never reached the server); kept 400 days like the existing metrics; shown only on the owner's Metrics page.
5. **It needs a Privacy policy change and counsel's review** before it ships: the policy says Optic "adds no tracking scripts of its own" (`legalpages.js:44`) and the Metrics page says "nothing records which pages were viewed" (`reports.js:133`), and Optic is hosted in Amsterdam (`legalpages.js:74`), so EU rules apply to some readers. The owner decides whether to count at all, whether to keep Cloudflare's script, whether guests are counted, and the retention period (section 8).

## 2. What is measured today

| Source | What it records | Identifiers | Kept | Who sees it | Where |
|---|---|---|---|---|---|
| `activity_days` | one row per account per UTC day on which it loaded Optic while signed in, or signed in | account id | 400 days | owner (Metrics) | written by `note_active`, `metrics.py:44-52`, on `/api/auth/me` (`auth/routes.py:163-164`) and sign-in (`touch_login`, `auth/store.py:119-129`); table `db.py:939-956`; sweep `db.py:1059-1066` |
| `milo_questions` | one row per question that passed the allowance: time and kind (`chat`, `research`, `scan`, `portfolio`, `earnings_brief`) | account id, or none for a guest | 400 days | owner (Metrics) | `note_question`, `metrics.py:55-61`, called from `_count_question`, `main.py:7714`; kinds at `main.py:1472`, `:6751`, `:8179`, `:8290`, `:8494` |
| Model-call ledger, `ai.db` table `calls` | per call: feature, model, input, output, cache read and write tokens, web searches, stop reason, whether the answer was used, a note | none | 92 days | owner (Claude usage) | schema `ai_store.py:72-85`; `record` `ai_store.py:293-326`; `/api/ai/usage` `main.py:6097` |
| Problem Reports, table `feedback` | the reader's message, the page (hash route), user agent, reporter email and id, resolved time | email, account id | no sweep; email and account dropped on account deletion (Privacy page) | owner (Problem Reports) | `app/feedback.py`; table `db.py:526-568`; route `main.py:6011` |
| Milo "report this answer" | a Problem Report carrying the question and Milo's answer text | as above | as above | owner | `milo.js:423-439` |
| Brokerage state | each connection's status (`pending`, `active`, `partial`, `outage`, `expired`, `closed`), status reason, last attempt and last sync; each account's sync state and note; consent rows with terms version and a hashed IP; webhook event ids and types; owed provider deletions | account id | while linked; webhook ids 30 days; link states until expiry | the reader; owner via the database only | tables `db.py:693-800`; consent `brokerage/routes.py:119-131`; callback outcomes `brokerage/routes.py:135-156` |
| `auth_attempts` | one row per guarded attempt (sign-in, register, reset, passkey, OAuth, feedback, Milo allowance, brokerage connect and sync) | bucket hashed with SHA-256 (`_bucket`, `auth/ratelimit.py:118-123`) | 1 day; 31 days for the monthly Milo count | nobody (counters) | `LIMITS` `auth/ratelimit.py:38-52`; `guard` `:146-169`; cleared on a successful sign-in (`clear`, `:172`); sweep `db.py:1039-1048` |
| Account tables | `users` (created, last sign-in, email confirmed, active), `sessions` (created, last used, user agent, IP), `user_preferences.knowledge_level`, passkeys | account id | sessions until expiry; the rest for the account's life | the reader (Settings); owner (Accounts) | `db.py:155-306`, `:351`, `:963` |
| Saved objects | watchlists and items, saved research, watches and their hits, theses, valuations, signals, portfolio alert settings, alerts and briefings, each with timestamps | account id | for the account's life | the reader | tables in `db.py` (`watchlist_items` `:323`, `watches` `:418`, and the rest) |
| Server access log (uvicorn) | every request: client IP, method, path, full query string with `token`, `code`, `state`, `id_token`, `access_token` and `secret` values redacted, status | IP | Railway's log retention: 7 days on Hobby, 30 on Pro (railway.com/pricing, read 2026-10-30) | the owner in Railway | `_SECRET_QUERY` and `_RedactQuery`, `main.py:232-243` |
| Application log lines | per Milo answer, `milo timing` with stage times, tool names and model rounds, no text (`StreamClock.summary`, `ai.py:1810`; logged `ai.py:3760`); `chat failed` with the exception; the ceiling reached (`main.py:7750`); advice-policy removals by rule; `brokerage provider error` with the provider's reason (`brokerage/routes.py:80`); OAuth failures by provider; mail attempts with the address masked | none, except masked addresses | as above | owner in Railway | as cited |
| `Server-Timing` header | per request timing on `/api/ticker` and `/api/quote` | none | not stored | anyone who loads the page | `main.py:1243`, `:1294` |
| Cloudflare Web Analytics | page visits, collected by Cloudflare's script | Cloudflare's own | Cloudflare's | owner in Cloudflare | disclosed at `legalpages.js:46-48`; not in Optic's source |
| Browser only, never sent | onboarding done (`optic.v2.onboard.v1`, `workspace.js:820-821`), recent searches (`optic.recent.v1`, `store.js:16`), Milo conversations, paper trades, chart drawings and the other personal keys (`PERSONAL_KEYS`, `device.js:17-47`) | n/a | until cleared | the reader | as cited |

**Searches that found nothing:** no `sendBeacon`, no analytics SDK (Google Analytics, Tag Manager, Plausible, PostHog, Mixpanel, Segment, Amplitude, Umami, Matomo, Clarity, Hotjar), no error reporter (Sentry, Datadog, New Relic), no `PerformanceObserver` or `performance.mark` posting, no `window.onerror` or `unhandledrejection` reporting, no CSP report endpoint.

### 2.1 The owner's pages

`/api/admin/metrics` (`main.py:6150`, owner session only) returns `metrics.overview` (`metrics.py:100-199`), drawn by the Metrics page (`static/v2/js/pages/reports.js:96-139`):
- accounts in total, verified, deactivated, active in 7 and 30 days (active means a recorded day, a sign-in or a session use);
- sign-ups, verified sign-ups and weekly active accounts for 12 weeks, Mondays in UTC, recorded from the day migration 18 ran;
- 4-week retention by sign-up week;
- Milo questions by kind for 7 days, 30 days and since counting began, accounts that asked in 7 days, and guest questions;
- model calls by feature for 7 and 30 days, from the ledger, including the owner's own and the scheduled writers;
- accounts by plan as the limits read them.

The owner's own accounts (`ADMIN_EMAILS`) are left out and reported as left out. Two small defects: the `earnings_brief` kind is recorded (`main.py:1472`) but missing from `KINDS` (`metrics.py:38-39`), so the page prints the raw id; and the page computes everything by reading every `activity_days` and `milo_questions` row into Python (`metrics.py:113`, `:157`), which slows as the tables grow.

The owner's other pages: Claude usage (`/api/ai/usage`), Problem Reports and Accounts (`reports.js:1-5`).

## 3. The seven event families

| Family | Status | How, today | What is missing |
|---|---|---|---|
| 1. Onboarding completion | **Not measurable** | The first-visit card's done flag lives only in the browser (`workspace.js:820-821`). For signed-in readers the server has proxies: account created (`users.created_at`), email confirmed (`users.email_verified`, near zero while mail is in log mode, BUG-021), explanation level chosen (`user_preferences.knowledge_level`, migration 19), first watchlist item | whether the card was finished, dismissed or ignored; anything about guests, who are most first visits |
| 2. Search success and failure | **Not measurable** | `/api/search` (`main.py:2043`) answers matches and an `available` flag but counts nothing; the access log has each query's text with the client IP for 7 to 30 days, which is not a privacy-conscious source; recent searches stay in the browser | searches with zero matches, a result opened or not, the directory being unavailable |
| 3. Dossier usage | **Partly** | indirectly from the access log (`/api/ticker/{T}`, `/api/quote/{T}`, `/api/options/...`), inflated by the 20-second header poll (`dossier-frame.js:75-86`); Cloudflare may count page views, but Optic's routes are hash routes (`#/NVDA`) and whether Cloudflare counts those is not verified | Dossier opens, which tab, Simple or Advanced analysis, from where (search, watchlist, Milo) |
| 4. Milo submission success and failure | **Partly** | `milo_questions` counts questions that passed the allowance, by kind; the ledger records each model call's stop reason (`error`, `refusal`, `max_tokens`, `end_turn`, `tool_use`) and whether the answer was used; the `milo timing` line times each finished answer | refusals before the allowance (401 no account, 413 too long, 429 daily, monthly, hourly or ceiling) leave only an access-log status (the ceiling also logs a warning, `main.py:7750`); ledger rows carry no question id, so "the question failed" cannot be computed from calls; a round the reader cancels is not recorded (cost audit C2); network failures in the browser are invisible |
| 5. Brokerage connection failures | **Partly, current state only** | connection status and reason, account sync state and note, provider errors logged with the provider's reason (`brokerage/routes.py:62-86`); webhook event types | the connect flow's outcome (`abandoned`, `error`, `unsupported`, `notreadonly`, `limit`, `expired`, `linked`, `nothing`) exists only as a redirect code (`brokerage/routes.py:135-156`) and an access-log line; a failure later repaired leaves no trace, so failure rates over time cannot be counted |
| 6. Abandoned flows | **Not measurable**, with one exception | accounts that never confirmed their email (`users.email_verified = 0`) | sign-up forms started and left; reset links and brokerage link states deleted unused at expiry without being counted (`sweep`, `db.py:1030-1037`); Milo answers stopped mid-stream; the first-visit card dismissed; Checkout left (Stripe's dashboard will show this once billing is on) |
| 7. Feature engagement | **Partly** | Milo questions by kind; model calls by feature; saved objects per account (watchlists, watches, theses, valuations, saved research, alerts) countable from existing tables; explanation level chosen; plan | which pages and tabs are used (Compare, Options, Chart, Markets, Scan, Brokerage sections), the density switch (browser only), web search turned on (only visible as searches in the ledger), persona |

## 4. Privacy observations on what exists today

- **Search text in the access log.** `_SECRET_QUERY` (`main.py:232`) redacts one-time tokens but not `q`, so every `/api/search?q=...` request writes what the reader typed next to their IP, as they type (the box asks after each 120 ms pause, `palette.js:263`; `typeahead.js:73`). Adding `q` to the redacted names, or logging only its length, would remove the most personal free text the log holds. Owner decision, since it costs some debugging detail.
- **Log retention wording.** The Privacy page says Railway keeps server logs "for up to 90 days" (`legalpages.js:80`); Railway's pricing page (2026-10-30) lists 7 days on Hobby and 30 on Pro. The policy's figure is an upper bound and may be deliberate; counsel and the owner can decide whether to state the plan's figure.
- **The Metrics page's own sentence.** "Nothing is sent to an analytics service, and nothing records which pages were viewed or what was asked" (`reports.js:133`) is true of Optic's counts. It is not true of the site, where Cloudflare's script records page visits. The `metrics.py` docstring says the same (`metrics.py:17-19`).
- **Milo answer reports** carry the question and the answer text (`milo.js:423-439`). The reader presses the button and the Privacy page covers "your message, the page you were on" (`legalpages.js:36`); whether that covers the question and answer included automatically is for counsel. Reports are kept with no end date.
- **What already holds up:** the ledger stores no account (`ai_store.py:72-85`); rate-limit buckets and the consent IP are hashed (`auth/ratelimit.py:112-123`); Milo conversations never leave the browser; the Metrics page leaves the owner out and shows counts only; question rows record the kind, not the text.

## 5. Recommended minimal design (a proposal; nothing implemented)

### 5.1 Rules

1. First party only: Optic's own server and database, no new vendor.
2. Counts by day and coarse category only. No account id, no IP, no user agent, no session, no symbol or ticker, no query text, no question or answer text, no holdings, values, account names or account numbers, no institution names (unless the owner decides otherwise, section 8).
3. The server counts what it already knows when a request finishes. The browser reports only what the server cannot see, through a route that accepts a fixed list of values and nothing else.
4. Counting can never break a page: a failed count is logged once and dropped, like `note_active` today.
5. Kept 400 days, the same figure the Privacy page already states for the existing metrics (`METRICS_KEEP_DAYS`, `db.py:1066`).

### 5.2 Events

| Family | Event | Outcomes (the only values accepted) | Counted by |
|---|---|---|---|
| Onboarding | `first_visit_card` | `shown`, `done`, `dismissed`, `level_chosen`, `followed_a_company` | browser (route) |
| Search | `symbol_search` | `matches`, `no_match`, `directory_unavailable`, `rate_limited` | server (`/api/search`) |
| Search | `search_result` | `opened`, `left_without_opening` | browser (route) |
| Dossier | `dossier_open` | the entry point: `search`, `watchlist`, `home`, `milo`, `link`, `other` | browser (route) |
| Dossier | `dossier_view` | `overview_simple`, `overview_advanced`, `options`, `chart`, `financials`, `earnings`, `news` | browser (route) |
| Milo | `milo_question` | `answered`, `refused_no_account`, `refused_too_long`, `refused_daily`, `refused_monthly`, `refused_hourly`, `refused_ceiling`, `model_error`, `classifier_declined`, `cut_off`, `cancelled` | server (`/api/chat`, `/api/research`, `_spend_guard`, `stream_chat`) |
| Milo | `milo_rounds` | `1`, `2`, `3`, `4_plus` | server |
| Milo | `milo_send` | `network_failed` | browser (route), the one failure the server never sees |
| Brokerage | `brokerage_connect` | `started`, `linked`, `nothing_linked`, `abandoned`, `error`, `unsupported`, `not_read_only`, `over_limit`, `expired` | server (`/connect`, `/callback`) |
| Brokerage | `brokerage_sync` | `ok`, `partial`, `expired`, `outage`, `error` | server (`sync_connection`) |
| Abandoned | `reset_link`, `verify_link`, `brokerage_link_state` | `used`, `expired_unused` | server (`db.sweep`, counting before it deletes) |
| Engagement | `page_open` | the route name only: `home`, `dossier`, `markets`, `read`, `scan`, `compare`, `brokerage`, `settings`, and the rest of the router's names | browser (route) |
| Engagement | `milo_option` | `web_search_on`, `persona_changed`, `level_changed` | server, from the request body |

Guests and signed-in readers are not told apart unless the owner wants one more value (`signed_in`, `guest`) on each row.

### 5.3 What it needs

- **A table**, added by a migration: `usage_counts(day TEXT, family TEXT, event TEXT, outcome TEXT, n INTEGER NOT NULL, PRIMARY KEY (day, family, event, outcome))`.
- **Counting in memory, flushed once a minute** with `INSERT ... ON CONFLICT DO UPDATE SET n = n + excluded.n`, so a busy page costs no database write per event; the existing startup tasks show the pattern (`_flush_feedback`, `main.py:4276`). A crash loses at most a minute of counts.
- **A route**, `POST /api/usage`, that takes `{family, event, outcome}`, refuses any value not in the table above, never looks up the session, stores nothing per request, and is rate-limited per address in memory like `/api/search` (`_search_allowed`, `main.py:2026-2042`). The browser sends it with `navigator.sendBeacon` so leaving a page is counted, and does not send it when the browser signals Global Privacy Control (`navigator.globalPrivacyControl`); the server also ignores a request carrying `Sec-GPC: 1`. The access log will still show these POST lines with the IP, like every request, unless the route is left out of the log.
- **The sweep**: `db.sweep` deletes rows older than 400 days and counts the unused links before deleting them.
- **A Usage section on the Metrics page**, owner only behind the same guard (`_owner_session_guard`), with daily and 30-day totals. Cells under 5 can be shown as "fewer than 5".
- **Tests**: values outside the list are refused; no identifier reaches the table; a failed write never fails the request; the sweep keeps 400 days; GPC is honoured.
- **Copy and policy**: a Privacy policy paragraph describing the counts, their retention and what is never recorded; the "adds no tracking scripts of its own" sentence (`legalpages.js:44`) and the Metrics page sentence (`reports.js:133`) reworded to stay true; the `metrics.py` docstring updated.
- **Counsel's review** of all of the above before it ships (section 7).

## 6. What it would cost

No new service and no new paid infrastructure. One table with at most about 80 rows a day (one per family, event and outcome seen that day), at most about 32,000 rows over 400 days; one write a minute; one small route. The beacon adds one request per counted browser event to Optic's own server.

## 7. What counsel must review

The Privacy page is `#/privacy`, written in `static/v2/js/pages/legalpages.js` (in force from 2026-10-19, not yet reviewed by a lawyer, per its own header at `legalpages.js:1-5`; BLOCKERS BL-02).

1. The new paragraph describing usage counts, and whether a first-party beacon sent from the reader's browser is a "tracking script" in the sense of the current sentence.
2. Readers in the EU and UK (Optic is hosted in Railway's Amsterdam region, `legalpages.js:74`): whether counting from the browser needs consent under the ePrivacy rules on reading or storing information on a device, or fits an exemption for first-party audience measurement, and what notice server-side counts need.
3. California and other US state privacy laws: notice at collection for the counts.
4. Cloudflare Web Analytics: whether its disclosure is enough, or whether it should be switched off once first-party counts exist.
5. Milo answer reports: whether the policy's description covers the question and answer text the report carries.
6. The server log: what it holds (search text, IPs) and the retention the policy states.

## 8. Decisions for the owner

1. Whether to add first-party counts at all.
2. Whether to keep Cloudflare Web Analytics (a setting in Cloudflare, not in the code).
3. Whether guests are counted, and whether rows say signed in or guest.
4. The retention period (400 days proposed, matching the existing metrics).
5. Whether to honour Global Privacy Control by not counting (proposed).
6. Whether brokerage failure counts may name the institution (useful for broker-specific outages; it is not an account detail, but it is closer to one than anything else proposed).
7. Whether to redact search text from the access log.
8. Whether to fix the two Metrics page defects (the `earnings_brief` label and the full-table reads), which need no policy change.
