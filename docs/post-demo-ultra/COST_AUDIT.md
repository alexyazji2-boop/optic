# API cost and scalability audit (Phase 10, 2026-10-30)

> **Checked and acted on in Phase 10** (the rest of this file is the audit as written by a separate read-only agent;
> its prices were read on official pages on 2026-10-30 and each figure carries its label).
>
> - The price table's one wrong cell (C3) is fixed: Sonnet 5.5 cache hits are $0.10 per million tokens (0.05x input),
>   confirmed on platform.claude.com's pricing page on 2026-10-30; `app/ai_store.py` and its test now say so.
> - C4 is fixed: Classic asks for the kept catalyst read on load (`cached=true`) and writes one only when the reader
>   presses "Write the read", as v2 does (the owner's rule: reading a page costs nothing).
> - The server-wide Milo ceiling no longer refuses or counts paying readers (section 9.2's observation); D-076.
> - C10 was traced: a visible browser makes one `/api/session` request per Home load; the second appears only in
>   headless Chrome, so it is the measuring setup, not the app.
> - C1 (cache Milo's CONTEXT turn across tool rounds) is proposed, not done: it changes the request every Milo answer
>   sends, and with the local key refused (BL-01) it cannot be checked against the real API before it ships. C2 (a
>   cancelled round missing from the ledger) and a dollar ceiling are proposals for the owner.

Directive 10, section 3. Repository `~/Optic/wt-ultra`, branch `post-demo-ultra`, committed state `3698975` (Phase 09) plus the uncommitted Phase 10 edits present on 2026-10-30 between 07:00 and 07:40 ET. Review date 2026-10-30.

**Method.** Read the source. Measured prompt and tool-definition sizes with a static Python script that parses the source and imports nothing from the app (`phase10/cost/scripts/prompt_sizes.py`, `tool_specs_size.py` in the work folder). Listed the table names in the four `data/*.db` files with SQLite in read-only immutable mode. Read public pricing pages on 2026-10-30. Reused earlier research where it says so. Every scenario figure comes from one script, `phase10/cost/scripts/model.py` in the work folder, whose inputs are the assumptions in section 8. No file in the checkout was changed, no server was started, no test was run, no request was made to Optic's production site or to any provider API, no `.env` file was opened, nothing under `~/Optic/ultra-data/` was opened, and no secret was printed.

The scripts were copied from the session's scratch folder to `~/Optic/work/post-demo-ultra-2026-10-29/phase10/cost/scripts/`.

**Line numbers** are from the working tree at that time. These cited files carried uncommitted edits and their numbers may move: `app/main.py`, `app/ai.py`, `app/metrics.py`, `app/auth/store.py`, `app/auth/routes.py`, `app/auth/ratelimit.py`, `app/auth/mailer.py`, `app/billing.py`, `app/feeds.py`, `app/universe.py`, `app/providers/yf.py`, `app/brief.py`, `app/catalysts.py`, `app/brokerage/snaptrade.py`, `app/brokerage/workspace_routes.py`, `static/app.js`, `static/v2/js/pages/read.js`. Each citation names the function or constant beside it so it can be found after a move. Every other cited file matches `HEAD`.

**Labels.** VERIFIED: read on an official page on 2026-10-30. PROVISIONAL: not verifiable from an official page today, contradicted by the page itself, or depending on a setting I cannot see (Railway plan, Anthropic tier, production environment variables). MEASURED: from a production usage ledger. ESTIMATE: computed from the stated assumptions. CODE: a cap, schedule or default in the source.

## 1. Summary

1. **Largest cost driver: Milo chat** (`/api/chat` on `claude-sonnet-5-5` with up to six model calls per question). It is 65% of all model spend at 100 monthly active users, 82% at 1,000, and 80% to 85% at 10,000. Per question it is an ESTIMATE of $0.14 (cached prefix warm) to $0.18 (cold) for a typical Dossier question, and up to about $1.44 when a question hits every limit at once. The only production measurement, $0.107 per call on 2026-10-11, predates the tool loop, Sonnet 5.5 and the current context budget.
2. **Monthly totals (all PROVISIONAL; arithmetic in section 8):**

   | | 100 MAU | 1,000 MAU | 10,000 MAU |
   |---|---|---|---|
   | Model spend (Milo + scheduled + open writers) | $139 | $981 | $1,441 at the 300-a-day Milo ceiling; $8,362 if the ceiling is raised to meet demand |
   | Everything else as built (SnapTrade Launch, Stripe, Railway, email) | $124 | $172 to $198 | $803 to $893 |
   | Total as built | **about $263** (about $161 if SnapTrade's free Build plan can carry the one or two linked readers) | **about $1,150 to $1,180** | **about $2,240 to $2,330** at the ceiling, **about $9,170 to $9,260** with demand served |
   | Licensed market data, if the owner adopts it (not in the totals above) | $2,049 to $2,399 a month whatever the user count | same | same |

3. **First scaling limits, in the order they are reached (ESTIMATE, section 9):** the Anthropic organisation's monthly spend cap if it is on the Start tier ($500, at about 500 MAU) or the Build tier ($1,000, at about 1,000 MAU), which pauses every AI feature until the first of the next month; then the server-wide Milo ceiling of 300 questions a day (about 1,500 MAU, earlier on busy days), which refuses Pro readers too; then Yahoo pacing at 2 requests a second during market hours (about 2,000 MAU, or about 800 if peak concurrency is three times my assumption). SQLite is not near a limit at 10,000 MAU at the write rates estimated. The single process is not measured for CPU and is tied to the Yahoo limit: a second worker would double Yahoo traffic and split every cache.
4. **Largest safe saving: cache Milo's CONTEXT turn across tool rounds** (new finding C1, section 12). Each round re-sends the 50,000 to 60,000 characters of page context at the full input price because the only cache breakpoint sits on the system prompt. ESTIMATE: a typical tool-using question falls from $0.14 to $0.10, and Milo spend falls 22% to 24% ($920 to $703 a month at 1,000 MAU).
5. **Accounting gaps:** the usage ledger skips the model round a reader cancels mid-answer (C2), and its price table charges Sonnet 5.5 cache reads at twice the published rate (C3). Neither changes the bill; both make `/api/ai/usage` disagree with the Claude Console.
6. **The Milo ceiling bounds the number of questions, not their cost.** 300 a day is about $1,335 a month at the typical mix, but about $13,100 a month if every question used every limit (long client-sent history, six rounds, web search). A dollar ceiling computed from the ledger, plus a spend limit in the Anthropic console, would bound cost directly (section 9.2).

## 2. Prices used

| Item | Price | Source and date read | Label |
|---|---|---|---|
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | $2 input, $2.50 5-minute cache write, $4 1-hour write, **$0.10** cache hit, $10 output, per million tokens | platform.claude.com/docs/en/about-claude/pricing (footnote 2: cache hits on Opus 5.5 and Sonnet 5.5 are 0.05x input), 2026-10-30 | VERIFIED |
| Claude Opus 5.5 (`claude-opus-5-5`) | $4 input, $5 5-minute write, $8 1-hour write, $0.20 hit, $20 output | same | VERIFIED |
| Claude Haiku 4.5, Haiku 5.5 (comparison only) | Haiku 4.5: $1 / $1.25 / $2 / $0.10 / $5. Haiku 5.5 under 100,000-token prompts: $0.10 / $0.125 / $0.20 / $0.01 / $0.50 | same | VERIFIED |
| Web search tool | $10 per 1,000 searches, plus result content billed as input tokens, including in later iterations of the same turn | same | VERIFIED |
| Thinking tokens | billed as output tokens (`usage.output_tokens_details.thinking_tokens` reports the share); on 4.6 and later models, earlier thinking blocks passed back are kept in context and billed as input | platform.claude.com/docs/en/build-with-claude/extended-thinking, 2026-10-30 | VERIFIED |
| Tool-use system prompt | 286 tokens on Sonnet 5.5 (`tool_choice` auto) | pricing page, 2026-10-30 | VERIFIED |
| Minimum cacheable prefix | 512 tokens on Opus 5.5 and Sonnet 5.5; top-level automatic caching exists; at most 4 breakpoints | Claude API reference bundled with Claude Code (cached 2026-10-06), which itself says to check the live caching page | PROVISIONAL (not re-read live) |
| Anthropic tier spend caps | Start $500, Build $1,000, Scale $200,000 a month; Sonnet 5.5 and Opus 5.5 each 1,000 RPM, 2,000,000 input and 400,000 output tokens a minute on Start; cache reads do not count toward input limits | platform.claude.com/docs/en/api/rate-limits, 2026-10-30 | VERIFIED (which tier Optic's organisation is on: unknown) |
| Railway | Hobby $5 a month including $5 of usage; Pro $20 a workspace including $20; vCPU $20 a month, memory $10 per GB-month, volume $0.15 per GB-month, egress $0.05 per GB; Hobby volume at most 5 GB; log retention 7 days on Hobby, 30 on Pro | railway.com/pricing, 2026-10-30 | VERIFIED prices; Optic's plan and bill PROVISIONAL |
| SnapTrade | Build: free, up to 5 connections, for developing and testing. Launch: $100 a month plus $2 per connected user (Real-time) or $1 (Daily, read-only); manual sync $0.05 per connection per sync on Daily, included on Real-time. A user with several connections counts once. No rate limits stated. | snaptrade.com/pricing, 2026-10-30 (no page date shown) | VERIFIED |
| Stripe | 2.9% + $0.30 per domestic card charge; +1.5% international; +1% conversion; $15 per dispute; Billing pay-as-you-go 0.7% of billing volume | stripe.com/pricing and stripe.com/billing/pricing, 2026-10-30 | VERIFIED |
| SEC EDGAR | free; "Current max request rate: 10 requests/second"; declare a User-Agent | sec.gov, Accessing EDGAR Data, 2026-10-30 | VERIFIED |
| Sentry (option) | Developer free (1 user, 5k errors, 1 uptime monitor, 30-day lookback); Team $29 a month ($26 annual) | sentry.io/pricing, 2026-10-30 | VERIFIED |
| Better Stack (option) | Free: 10 monitors and heartbeats, 1 status page, 3 GB of logs kept 3 days; responder $34 a month ($29 annual); smallest telemetry bundle $45 a month US ($38 annual) | betterstack.com/pricing, 2026-10-30 | VERIFIED |
| Resend (option) | Free 3,000 emails a month, 100 a day; Pro $20 for 50,000, $0.90 per 1,000 over | resend.com/pricing, 2026-10-30 | VERIFIED |
| Twelve Data Venture (option) | the business page shows **$499** a month on the plan card and **$149** in its own structured data; external display allowed | twelvedata.com/pricing-business, 2026-10-30 | PROVISIONAL (page contradicts itself; the 2026-10-24 research read $149, $124 billed yearly) |
| Intrinio Enterprise, delayed OPRA (option) | from $1,250 a month and $650 a month (query-only redistribution); recommended bundle "from $2,024"; planning band $2,000 to $3,600 | `~/Optic/work/data-provider-2026-10-24/REPORT.md` lines 36 and 133, checked 2026-10-24 | PROVISIONAL (not re-read today; Intrinio's Enterprise floor is a sales figure) |
| Cloudflare | plan not known; assumed free | not checked | PROVISIONAL |

**The app's own price table is out of date for one cell.** `app/ai_store.py:112-119` (`PRICES`, "as read on 2026-09-30") prices `claude-sonnet-5-5` cache hits at $0.20; the page now says $0.10. The comment above it (`ai_store.py:106-111`) says only Opus 5.5 has the 0.05x rate. Every other cell for the two models in use matches today's page, and `WEB_SEARCH_USD = 0.01` (`ai_store.py:121`) matches.

## 3. Every model call

All model client code is in `app/ai.py` (no other file imports `anthropic`). Two model constants: `MODEL = "claude-opus-5-5"` for written pieces (`ai.py:55`) and `PULSE_MODEL = "claude-sonnet-5-5"` for Milo (`ai.py:60`). Every non-streamed call goes through `_ask` (`ai.py:1029`), which adds the advice policy to the system prompt and writes one ledger row per call (`ai_store.record`). The streamed calls record from the final message (`_streamed`, `ai.py:1069`). The client retries 429 and 5xx up to five times (`ai.py:1002`); the writers use their own sync clients with 2 to 3 retries. Server-side refusal fallback is on for chat and research (`FALLBACK_BETA`, `ai.py:65`, `fallbacks: "default"`); a fallback re-run is billed under the fallback model and is not modelled here.

| Feature (ledger id) | Model | Who triggers it, how often | Output cap | Input cap | Rounds and web search | Caching | Ceilings | Where |
|---|---|---|---|---|---|---|---|---|
| Milo chat (`pulse`) | Sonnet 5.5, adaptive thinking, effort medium | a signed-in reader's question | 8,000 tokens per call | page CONTEXT 60,000 characters, 14,000 per section (research 26,000, framework 18,000, named symbols 24,000, linked portfolio 30,000); history 24 turns or 60,000 characters; question 8,000 characters | up to 4 tool rounds, 10 tool calls, 12,000 characters per tool result, 30 s per call, 75 s in all; up to 3 `pause_turn` resumes; so up to 6 model calls, more with pauses; web search 5 per call when the reader turns it on | one breakpoint, on the system block (prompt + format rules + policy, 51,609 characters); tools (16 or 17 definitions) sit before it in the prefix; **nothing marks the CONTEXT turn** | plan allowance, hourly burst, server-wide ceiling | `build_chat_request` `ai.py:3372-3499` (web search `:3461`, `max_tokens` `:3473`, breakpoint `:3484`, effort `:3493`); loop `stream_chat` `ai.py:3575-3786` (pause `:3705`, round limit `:3714`, appends `:3708`, `:3737`); caps `ai.py:1397-1404`, `:1567-1580`; `milo_tools.py:46-50` |
| Deep research (`research`) | Sonnet 5.5, adaptive, effort high | a signed-in reader | 12,000 | the same 60,000-character context plus the question | one call, server-side search up to 10 | breakpoint on its system block (prompt + policy, 4,640 characters) | as chat | `deep_research` `ai.py:3789-3897`, `:3823-3838` |
| Scan request (`scan`) | Sonnet 5.5 | only the words `/api/screener/ask` could not read itself, for a reader with Milo allowance | 600 | vocabulary JSON + 300-character request (`SCAN_REQUEST_MAX`) | one | the reading is kept per request text in `kept` (14 days, `ai_store.py:125`) | counts as a Milo question | `read_scan_request` `ai.py:3308-3350`; route `main.py:6720` |
| Portfolio briefing (`portfolio_brief`) | Sonnet 5.5 | a linked Pro reader presses Write it up | 1,600 (`ai.py:2039`) | facts JSON cut at 40,000 characters (`ai.py:2060`) | one | kept per reader, facts and level, sealed (`workspace_routes.py:127-148`) | counts as a Milo question | `write_portfolio_brief` `ai.py:2042` |
| Earnings brief (`earnings`) | Opus 5.5 | a signed-in reader presses Write (POST, one Milo message) | 4,000 (`ai.py:1955`) | facts cut at 60,000 characters (`ai.py:2177`) | one | kept 6 hours per ticker and report date for every reader (`EARNINGS_TTL`, `ai.py:1953`) | 30 new briefs a rolling day for the whole server | `_write_earnings_brief` `ai.py:2155`; routes `main.py:1406`, `:1441` |
| Sector read (`sector`) | Opus 5.5 | anyone opening a sector or index read, no account (GET) | 1,600 (`ai.py:2289`) | facts cut at 40,000 (`ai.py:2346`) | one | kept 1 hour per symbol (`ai.py:2287`) | 30 a day | `_write_sector_read` `ai.py:2299`; `main.py:4790` |
| Catalyst read (`catalyst_read`) | Opus 5.5 | anyone opening catalyst mode on a release not yet read (GET; Classic asks on view, v2 on request) | 3,000 (`ai.py:2822`) | facts cut at 40,000 (`ai.py:2818`) | one | kept 1 hour per release (`CATREAD_TTL`, `ai.py:2771`) | 24 a day | `_write_catalyst_read` `ai.py:2790`; `main.py:5092` |
| Optic's Read (`read`) | Opus 5.5 | scheduled: once per edition, three a trading day and two on a closed day, 19 a week; at most 3 attempts an edition, an hour apart | 4,000 (`ai.py:2973`) | facts cut at 60,000 (`ai.py:3234`) | one | kept per edition on disk | attempts claimed on disk | `write_morning_read` `ai.py:3202`; `brief.py:63-92`, `read_edition` `brief.py:925` |
| Optic Desk (`desk`) | Opus 5.5 | once per desk date (2 attempts, an hour apart), then rewritten when the tape moves past the written one, on a reader's request, at most once per 30 minutes and 12 times a day | 4,000 (`ai.py:2974`) | facts cut at 60,000 (`ai.py:3147`) | one | kept per day on disk | `DESK_MAX_ATTEMPTS` 2, `DESK_REWRITES_PER_DAY` 12 | `write_morning_desk` `ai.py:3112`; `main.py:3152-3243` |
| Weekly update (`weekly`) | Opus 5.5 | once per week; a failed write retried after 10 minutes | 6,000 (`ai.py:2439`) | facts cut at 80,000 (`ai.py:2513`) | one | kept a week | `WEEKLY_RETRY_SECONDS` 600 (`ai.py:2447`) | `_write_weekly` `ai.py:2511`; `main.py:4849` |
| Desk daily edition (`edition`) | Opus 5.5 | **off** unless `DESK_EDITION_AUTO` (`main.py:4324`); then 2 slots a trading day, 1 on a closed day, 2 attempts, each a draft and at most one repair | 8,000 (`ai.py:3050`) | outline and evidence | one or two | kept per slot | `MAX_ATTEMPTS` 2 (`desk/edition.py:40-42`) | `write_edition` `ai.py:3053` |
| Catalyst scan (`catalyst_scan`) | Opus 5.5 | **off**: the scan reads stories with rules unless `CATALYST_READER=model` (`catalysts.py:105`); with the model, every 6 hours (`catalysts.py:113`) | 8,000 (`ai.py:2715`) | 120 stories of 280 characters plus 40 stored catalysts (`catalysts.py:129`) | one | n/a | n/a | `extract_catalysts` `ai.py:2674` |
| Key check | Models API, free | at most once per 15 minutes (`KEY_CHECK_TTL`, `ai.py:1236`) | n/a | n/a | n/a | n/a | n/a | `key_usable` `ai.py:1244` |

**Allowances and ceilings around the paid calls** (CODE):

- Plans (`app/auth/store.py:658-692`): Free 3 Milo messages a day; Pro 15 a day and 100 in any 30 days; Enterprise 4,000 a day. Guests 0 (`GUEST_AI_CALLS_PER_DAY`, `main.py:7626`), so Milo needs an account. The comment at `auth/store.py:677-682` records the measured "~$0.11 a message" that set Pro's caps.
- Hourly burst: 30 messages per address per hour, in memory (`AI_CALLS_PER_HOUR`, `main.py:7611`).
- **Server-wide ceiling: 300 questions in any 24 hours** (`MILO_QUESTIONS_PER_DAY`, `main.py:7632`, checked at `:7746` before either allowance is charged), counted from `milo_questions` excluding the owner (`questions_since`, `metrics.py:64-75`). Working tree only, decision D-076. Every kind counts: chat, research, scan, portfolio and `earnings_brief` (`main.py:1472`).
- Open writers: earnings 30, sector 30, catalyst 24 new pieces in a rolling day, counted from the ledger (`OPEN_WRITE_LIMITS`, `ai.py:1890`); the comment beside it puts the three at "roughly $9 a day together" at their token caps.
- Spend guard order: question length (413), then the ceiling, then the monthly and daily allowance, then the burst cap (`_spend_guard`, `main.py:7725`; the chat route `main.py:8165-8213` checks the length first).

## 4. Token usage: what is measured and what is estimated

### 4.1 No local usage ledger

The ledger is `ai.db` under `TRACKER_DATA_DIR` (`ai_store.py:56-60`), by default `~/Optic/wt-ultra/data/ai.db`. **It does not exist.** `data/` holds `accounts.db` (no tables), `alerts.db` (`alerts`), `brief.db` (`briefs`) and `desk_editions.db` (`editions`), read with `?mode=ro&immutable=1`. There is therefore no local median or p90 per feature to report. It would also not represent production: the local key is refused (BLOCKERS BL-01), so local runs use a stand-in model.

### 4.2 The only production measurement available offline (MEASURED, old)

`~/Optic/work/analysis-2026-10-11/MEASURED.md`: the live `/api/ai/usage` totals read on 2026-10-11, 146 calls over 10.6 days. Averages per call (the ledger page gives totals, not medians or p90):

| Feature | Calls | Input per call | Output per call | Cost per call |
|---|---|---|---|---|
| Desk | 91 | 7,203 | 2,006 | $0.069 |
| Read | 29 | 17,425 | 2,359 | $0.117 |
| Catalyst read | 14 (4 unused) | 1,646 | 1,962 | $0.046 |
| Earnings brief | 5 | 6,042 | 3,419 | $0.093 |
| Weekly | 1 | 3,700 | 2,699 | $0.069 |
| Milo chat | 6 | 32,752 uncached + about 11,700 cache write | 1,254 | $0.107 |

Cache reads were zero in every call: each chat wrote its prefix and none read it back, consistent with sparse traffic and a 5-minute cache life. Web searches: zero. **Limits of this evidence:** it is before Milo's tools (2026-10-15), before Sonnet 5.5 (2026-10-16), before the 60,000-character context budget (2026-10-12), before the policy text was added to every writer's prompt (Phase 02, about 630 tokens), and six chat calls is no sample. It is used below only for the writers, plus the policy text.

### 4.3 Sizes measured from the source today

| Block | Characters | Tokens (assumption: prose 4 characters a token, JSON 3.5) |
|---|---|---|
| Chat system block: `SYSTEM_PROMPT` 34,492 + `FORMAT_PROMPT` 14,592 + `POLICY_TEXT` 2,523 | 51,609 | about 12,900 |
| Milo tool definitions, 17 (16 without `get_my_portfolio`, which is offered only from the Brokerage page or a question about the reader's holdings, `main.py:8024`) | 12,288 (10,895) | about 3,500 (3,100) + 286 tool system prompt |
| Research system block: `RESEARCH_PROMPT` 2,115 + `POLICY_TEXT` 2,523 | 4,640 | about 1,160 |
| Writer prompts: edition 5,059; catalyst scan 3,467; desk 3,356; earnings 3,118; weekly 2,509; sector 2,181; morning Read 1,985; catalyst read 1,926; portfolio 1,293; scan 1,217 (each plus the 2,523-character policy) | | 300 to 1,300 each, plus about 630 |

The characters-per-token ratios are assumptions, not counts: the token-counting endpoint needs a working key (BL-01). The production ledger can settle them: a cold question's first call records the whole prefix as `cache_write_tokens`.

### 4.4 Per-question estimates (ESTIMATE)

Assumptions for a **typical Milo question** asked from a Dossier: cached prefix 16,300 tokens (tools + system); 500 tokens of level, horizon, framework and lens blocks after the breakpoint; CONTEXT 15,700 tokens (55,000 characters, near the budget, as the 2026-10-11 calls were); history 1,000 tokens; two model calls always and a third half the time; round 1 tool results 3,400 tokens and round 2 another 1,700; 800 tokens of assistant content (thinking and tool calls) carried into each later round and billed as input; output 800 tokens on a tool round and 2,000 on the answering round.

| Profile | Calls | Cost | With the CONTEXT turn cached (C1) |
|---|---|---|---|
| Typical, prefix cold (traffic sparse) | 2.5 | $0.18 | $0.13 |
| Typical, prefix warm | 2.5 | $0.14 | $0.10 |
| Light: a definition from Home, no tools, 2,300-token context | 1 | $0.06 cold, $0.02 warm | no change |
| Every limit at once: 6 calls, full context and history, 8,000-character question, 10 tool results of 12,000 characters, 8,000 output tokens a call, 5 web searches | 6 | about $1.44 | about $0.88 |
| Deep research, typical: 6 searches of about 2,500 result tokens each, results cached and re-read over about 7 iterations, 6,000 output tokens | 1 | about $0.21 | n/a |
| Deep research at its caps: 10 searches, 12,000 output tokens | 1 | about $0.39 | n/a |
| Scan request (2,000 in, 300 out) | 1 | about $0.01 | n/a |
| Portfolio briefing (4,500 in, 900 out; at caps 12,500 and 1,600) | 1 | about $0.02 (cap $0.04) | n/a |
| Earnings brief (measured average plus policy text; at caps) | 1 | $0.10 (cap $0.15) | n/a |
| Sector read (6,200 in, 1,000 out; at caps 11,200 and 1,600) | 1 | $0.04 (cap $0.08) | n/a |
| Catalyst read (measured; at caps) | 1 | $0.05 (cap $0.08) | n/a |

Why warm and cold differ: the 16,300-token prefix costs $0.041 to write and $0.0016 to read. At 20 questions a day nearly every first call writes it; at a few hundred a day most read it. The scenarios use a Poisson estimate over 14 active hours and 1.5 prefix variants (web search on or off, portfolio tool or not).

## 5. Scheduled and shared writers (independent of the number of users)

| Writer | Frequency | Cost per call | Per month | At attempt and rewrite caps |
|---|---|---|---|---|
| Optic's Read | 19 editions a week (CODE) | $0.12 (MEASURED + policy) | $9.83 | 3 attempts an edition at the 4,000-token cap: $35 |
| Optic Desk | about 9 a day (MEASURED 2026-10-04 to 11: 62 in 7 days) | $0.07 (MEASURED + policy) | $19.55 | 13 a day at the token cap: $59 |
| Weekly update | once a week | $0.07 (MEASURED, n = 1) | $0.31 | $0.90 at the 6,000-token cap |
| Desk edition | off | | $0 | if switched on: 51 slots a month at about $0.15 to $0.25 with at most one repair (`main.py:4319-4323` comment): $8 to $26 |
| Catalyst scan | off (rules) | | $0 | with the model: 4 scans a day, at most about $0.24 each (about 20,000 tokens in, 8,000 out): about $29 |
| **Fixed total** | | | **about $30** | about $95 at every cap (writers as configured today) |

The fixed total matches the run rate measured on 2026-10-11 ($7.28 a week, about $31 a month). Readers do not change it, except that desk rewrites happen only when someone loads Home after the tape has moved.

**Reader-triggered writers with global ceilings.** Their caches bound the cost per piece; the daily ceilings bound the total. At the ceilings every day: earnings $87, sector $41 and catalyst $35 a month at typical cost per call (about $163), or about $261 at the token caps. Earnings briefs are also Milo questions, so the scenarios count them under Milo; sector and catalyst reads are counted separately.

## 6. Market data and other providers

All market data caches are on the server and shared by every reader (public data; DATA_PATHWAYS Part 2 lists the 75 caches). Brokerage data and the reader's own context are the per-reader exceptions.

| Provider | What Optic asks for | How often, cache | Limits | Cost today | Risk at scale |
|---|---|---|---|---|---|
| Yahoo Finance through yfinance (`app/providers/yf.py`) | quotes, history, options chains, fundamentals, calendars, news, holders | quote stack 30 s (`info:`, `q7:`, `quote:`), summary 15 min, history 5 min, intraday 30 s, chain 60 s, expiries 30 min, fundamentals 1 to 24 h, news 10 min (DATA_PATHWAYS S03 to S10). A cold Dossier is 11 to 12 requests (`yf.py:234-236`); a snapshot 16 and a thirty-name scan 480 (`yf.py:208-209`) | **Optic's own limiter:** burst 24, sustained 2.0 requests a second, halving on a 429 to a floor of 0.25 (`YF_BURST`, `YF_RATE`, `YF_RATE_FLOOR`, `yf.py:241-243`); background jobs yield to readers (`MAX_YIELD_WAIT`, `yf.py:323`). Yahoo's own limit is undocumented. | $0 | Unofficial and unlicensed for redistribution (BUG-023, P0; BLOCKERS BL-09). The 2 requests a second is the first data limit (section 9). |
| Robinhood overnight quotes (`app/providers/overnight.py`) | overnight prints | 20 s (S14) | undocumented endpoint | $0 | on by default (`enabled`, `overnight.py:163-171`); BUG-022, P0 |
| SEC EDGAR | companyfacts, submissions, ticker map, Form 4, N-PORT, full-text search | facts and ticker map 24 h, extraction 7 days, submissions 1 h, filings 30 days, Form 4 index 2 min (S18, S44, S45); shared feed cache 15 min (`feeds.py:107`) | SEC: 10 requests a second with a declared User-Agent (VERIFIED). Optic sends `OpticTerminal/1.0 (<contact or site>)` (`user_agent`, `feeds.py:85-95`) and spaces requests to one host 0.6 s apart (`POLITE_GAP_SECONDS`, `feeds.py:109`), under 2 a second | $0 | grows with distinct companies, not readers |
| FRED `fredgraph.csv` (`app/fred.py:37-42`) | release actuals, 10-year rate, HY spread | 6 h | no key; no limit stated in code | $0 | fixed load |
| Nasdaq Trader symbol files (`app/universe.py`) | every US-listed symbol | once per Eastern day; a failed refresh retried after 15 minutes (`REFRESH_RETRY_SECONDS`, `universe.py:407`, working tree, S19) | none stated | $0 | fixed load |
| Treasury | none in this tree: the risk-free and 10-year rates come from Yahoo `^IRX` and `^TNX` (`rates.py:10-13`), cached 6 h | | | $0 | |
| Tradier (`app/providers/tradier.py`) | real-time quotes and chains | only with `TRADIER_ACCESS_TOKEN`; unset in production per DATA_PATHWAYS S13 | account-holder display terms (2026-10-24 research) | $0 | not a production option as noted there |
| Logos (`_LOGO_SOURCES`, `main.py:1937`) | Parqet and Financial Modeling Prep image hosts | disk 14 days, a miss 2 days, browser one week (DATA_PATHWAYS H5); at most 600 outside fetches an hour for the whole server (`_LOGO_FETCHES_PER_HOUR`, `main.py:1946`, working tree) | none published to Optic | $0 | no agreement with either host (terms not checked: PROVISIONAL) |
| DoltHub (`dolthub_vol.py:52`) | options volatility history | off unless `OPTIC_DOLTHUB`; then about 1,000 requests once and a few a day | CC BY-SA 4.0 | $0 | off |
| Cboe daily index CSVs (`analytics/dispersion.py:42-58`) | VIX, VIXEQ, COR1M, DSPX history | off unless `OPTIC_CBOE_HISTORY`; 18 h | | $0 | off |
| RSS and agency calendars (`feeds.py` sources, `events.py`) | wires, release calendars | 15 min, shared | | $0 | fixed load |
| FINRA, USAspending, House Clerk | short volume, contract awards, disclosures | 6 h, 1 h, 6 h (S31, S38, S42) | | $0 | fixed load |
| **SnapTrade** (`app/brokerage/snaptrade.py`) | accounts, positions, balances, activities | four background pulls a trading day per connection at 09:00, 12:30, 16:15 and 20:15 ET (`SYNC_SLOTS_ET`, `brokerage/service.py:58`), one per 20 h on closed days (`:52`); webhook pulls at most 4 a day per reader (`:533`); manual sync 1 a day on Pro; a pull is 2 requests plus 2 per account | 250 requests a minute per client id and 4 background pulls per user a day (docs read 2026-10-12, `snaptrade.py:28-29`) | $0 today: owner only, test key on the free plan (project notes, not re-checked live) | Launch pricing applies once readers link (section 8). Manual "Sync now" on the Daily plan calls the paid refresh (`request_refresh`, `service.py:503-530`) |
| **Stripe** (`app/billing.py`) | Checkout, portal, webhooks | per subscription event | | $0: billing is off and live keys are refused without `BILLING_LIVE_APPROVED` (`billing.py:66-78`) | 5.1% of a $20 charge (section 8) |
| **Mail relay** (`app/auth/mailer.py:34-62`) | verification, reset, alerts | per event | | $0: no `SMTP_HOST`, links go to the log (BUG-021) | needs a provider before inviting readers |

**Licensed market data (owner decision, PROVISIONAL).** The 2026-10-24 report recommends Intrinio Enterprise from $1,250 a month, delayed OPRA query-only redistribution $650, and Twelve Data Venture; "from $2,024" a month, the same at 20 or 200 users on a delayed-only setup, planning band $2,000 to $3,600 (REPORT.md lines 36, 41, 133). Today's Twelve Data page lists Venture at $499 on the plan card, which would make the floor $2,399. The report also notes Intrinio's terms count sending data to an LLM as redistribution, so Milo would need to be named in the order form, and that licensed SPX and VIX values may add about $1,500 plus $4.85 per user (Cboe's own estimate). None of this is in the totals.

## 7. Infrastructure and database operations

- **One process.** `uvicorn --workers 1` on purpose, because the Yahoo limiter and every cache live in the process (`Dockerfile:50-55`); one replica (`railway.json`, `numReplicas: 1`), health check `/healthz`, restart policy ALWAYS. GZip above 800 bytes (`main.py:341`).
- **Memory.** A scan peaks at about 700 MB; the service was OOM-killed twice on a low limit on 2026-09-02 (`DEPLOY.md:105-129`). The Yahoo adapter cache had no eviction (S01); the working tree now sweeps entries older than a day and caps it at 20,000 entries (`CACHE_MAX`, `sweep_cache`, `yf.py:81-100`) and refuses unknown chart periods (`_DAILY_PERIODS`, `main.py:415`).
- **Storage.** SQLite and JSON files on the Railway volume at `/app/data`: `accounts.db` (accounts, sessions, rate-limit rows, metrics rows, brokerage rows), `ai.db` (kept pieces, ledger), `brief.db`, `desk_editions.db`, `weekly.db`, `alerts.db`, `briefing.db`, `analysts.db`, `iv_history.db`, `feed_cache.json` (871 KB locally), `symbols.json`, `sec_facts/`, `logos/`, `lookthrough/`, and 7 daily copies of `accounts.db` (`KEEP_ACCOUNTS`, `snapshots.py:47`).
- **Connections.** Every accounts-database call opens a connection and runs three PRAGMAs (`_connect`, `db.py:79-88`); writes are serialised by one process lock (`cursor`, `db.py:92-110`); busy timeout 15 s.
- **Writes per request, where notable:**
  - each signed-in `/api/auth/me` (page load): 2 write transactions, `touch_session` and `note_active` (`auth/routes.py:163-164`);
  - each Milo question: 1 to 2 allowance rows (`ai_day`, and `ai_month` on Pro), 1 `milo_questions` row (`metrics.py:55-61`), 1 ledger row per model call in `ai.db` (about 2.5), plus a COUNT over the last 24 hours of `milo_questions` joined to `users` for the ceiling (`metrics.py:64-75`) and the allowance COUNTs;
  - each sign-in attempt: 2 `auth_attempts` rows, cleared on success (`guard`, `auth/ratelimit.py:146-167`);
  - each brokerage sync: account upserts and one sealed snapshot, then a prune that reads all of that reader's snapshots (`brokerage/store.py:270-300`);
  - each feed store rewrites the whole `feed_cache.json` (`_store`, `feeds.py:760-772`).
- **Growth.** `activity_days` and `milo_questions` are kept 400 days (`METRICS_KEEP_DAYS`, `db.py:1059-1066`); ledger 92 days and kept pieces 14 (`ai_store.py:125-126`); brokerage snapshots, the newest 30 plus one a day for 400 days per linked reader (`brokerage/store.py:270-271`), copied seven times by the daily backups. At 180 linked readers and an assumed 5 KB per sealed snapshot that is about 0.4 GB, about 3 GB with the copies, inside Pro's 1,000 GB and close to Hobby's 5 GB volume limit. The Metrics page reads every `activity_days` and `milo_questions` row into Python per view (`metrics.py:113`, `:157`): about a million rows at 10,000 MAU (assumption: 8 active days a month for 13 months), seconds per view, owner only.
- **Monitoring: none.** No error tracker, no uptime monitor, no alerting. Railway's health check, `/api/health` (status, commit, uptime, `main.py:1147`) and the platform log (7 days on Hobby, 30 on Pro) are all there is.

## 8. Scenarios: 100, 1,000 and 10,000 monthly active users

### 8.1 Assumptions

| # | Assumption | Value | Note |
|---|---|---|---|
| A1 | Active user | loads Optic at least once in the month (MAU) | the directive's "active users" |
| A2 | Daily actives | 25% of MAU | used for page-load writes and concurrency |
| A2b | Signed in | half of daily actives | guests cannot ask Milo (`GUEST_AI_CALLS_PER_DAY` 0, `main.py:7626`), so Milo volume comes from A3 alone; the share matters here only for the two writes each signed-in page load makes |
| A3 | Readers who ask Milo on a given day | 10% of MAU | Milo needs a free account (`GUEST_AI_CALLS_PER_DAY` 0) |
| A4 | Questions per asker per day | 2 | bounded by Free 3 a day and Pro 15 a day, 100 in 30 |
| A5 | Mix of questions | chat 85%, research 8%, scan 3%, earnings brief writes 2%, portfolio briefings 2% | all count toward the 300-a-day ceiling |
| A6 | Per-question cost | section 4.4; the warm share of the chat prefix from question volume | ESTIMATE |
| A7 | Sector reads and catalyst reads a day | 2 and 3; 12 and 10; 30 and 24 (the ceilings) | reader-triggered |
| A8 | Paid (Pro) share of MAU | 2%, 2%, 3% | billing is off today; the $20 price is the code's default label, not an approved price |
| A9 | Pro readers who link a brokerage | 60%, with 1.5 connections each and 10 manual syncs a month, each refreshing one connection | Free links nothing; Pro allows one manual sync a day per reader |
| A10 | Railway resources (average) | RAM 0.7, 1.5, 4 GB; vCPU 0.3, 0.8, 2; volume 2, 4, 15 GB; egress 5, 50, 500 GB | about 50 MB of egress per MAU a month; Cloudflare caching not counted |
| A11 | Peak concurrent readers in market hours | 1.5% of MAU | for section 9; 70% of them on a symbol page; distinct symbols are 60% of those pages; each reader opens a new symbol every 4 minutes; half of those miss the cache |

### 8.2 Arithmetic

Milo, per month (questions a day × 30.4 days × mix × cost per question):

| | 100 MAU | 1,000 MAU | 10,000 MAU at the ceiling | 10,000 MAU, demand served |
|---|---|---|---|---|
| Questions a day (demand) | 20 | 200 | 2,000 asked, 300 served | 2,000 |
| Chat prefix warm share | 8% | 55% | 70% | about 100% |
| Chat | 517 × $0.17 = $89.76 | 5,168 × $0.16 = $802 | 7,752 × $0.15 = $1,159 | 51,680 × $0.14 = $7,109 |
| Deep research | 49 × $0.21 = $10.25 | 486 × $0.21 = $102 | 730 × $0.21 = $154 | 4,864 × $0.21 = $1,025 |
| Scan requests | 18 × $0.01 = $0.13 | 182 × $0.01 = $1.28 | 274 × $0.01 = $1.92 | 1,824 × $0.01 = $12.77 |
| Earnings brief writes | 12 × $0.10 = $1.16 | 122 × $0.10 = $11.56 | 182 × $0.10 = $17.34 | 912 (the 30-a-day cap) × $0.10 = $86.70 |
| Portfolio briefings | 12 × $0.02 = $0.22 | 122 × $0.02 = $2.19 | 182 × $0.02 = $3.28 | 1,216 × $0.02 = $21.89 |
| **Milo total** | **$102** | **$920** | **$1,335** | **$8,256** |
| Milo total with C1 (CONTEXT cached) | $80 | $703 | $1,010 | $6,092 |

All costs, per month:

| Line | 100 MAU | 1,000 MAU | 10,000 MAU | Label |
|---|---|---|---|---|
| Milo (above) | $102 | $920 | $1,335 (ceiling) or $8,256 | ESTIMATE on VERIFIED prices |
| Scheduled writers (section 5) | $30 | $30 | $30 | MEASURED rates, CODE schedules |
| Sector and catalyst reads (A7 × $0.04 and $0.05) | $7 | $31 | $76 | ESTIMATE |
| **Model spend** | **$139** | **$981** | **$1,441 or $8,362** | |
| SnapTrade Launch: $100 + linked readers × ($1 + 10 syncs × $0.05) on Daily, or × $2 on Real-time | 1.2 linked: $102 | 12 linked: $118 to $124 | 180 linked: $370 to $460 | VERIFIED prices; Custom-plan discounts not listed |
| Stripe: paid readers × ($20 × 3.6% + $0.30) = $1.02 each, domestic cards | 2: $2 | 20: $20 | 300: $306 | VERIFIED prices |
| Railway: RAM × $10 + vCPU × $20 + volume × $0.15 + egress × $0.05, at least $20 on Pro | $14 usage, $20 on Pro | $34 | $107 | PROVISIONAL (plan and real usage unseen) |
| Email | $0 (log mode; Resend free would cover it) | $0 to $20 | $20 (Resend Pro) | VERIFIED prices, ESTIMATE volume |
| Monitoring | $0 (none) | $0 | $0 | options in section 10 |
| Market data | $0 | $0 | $0 as built, but not servable (section 9) | |
| **Total** | **about $263** | **about $1,150 to $1,180** | **about $2,240 to $2,330**, or **$9,170 to $9,260** with demand served | PROVISIONAL |
| Licensed data if adopted | +$2,049 to $2,399 | same | same | PROVISIONAL |

Notes on the table:
- At 100 MAU the SnapTrade platform fee is most of the non-model cost. Whether the free Build plan may carry real readers is SnapTrade's call; its page calls Build "for developing and testing before going live". On Build the 100-MAU total is about $161.
- If 5% of MAU ask Milo instead of 10%, halve the Milo rows. If a typical question costs $0.11 (the old measurement) instead of $0.14 to $0.18, take about 30% off them.
- **The heaviest Pro reader** (100 typical questions in 30 days, 3 connections, the one manual sync a day Pro allows): about $15.80 of model spend, $2.50 on SnapTrade Daily (or $2 on Real-time) and $1.02 to Stripe, so **about $19 against a $20 price on either plan.** The 2026-10-12 brokerage model expected such a reader to contribute about $5, using $0.107 a message. ESTIMATE; the production ledger can settle it.

## 9. Where it breaks first

### 9.1 Limits as users grow (ESTIMATE under section 8.1)

| Order | Limit | Where | Reached at | What happens |
|---|---|---|---|---|
| 1 | Anthropic monthly spend cap of the organisation's tier | Console (tier unknown) | Start, $500: about 500 MAU. Build, $1,000: about 1,000 MAU | every AI feature answers 429 until 00:00 UTC on the first of the next month; retries fail too (rate-limits page) |
| 2 | Server-wide Milo ceiling, 300 a day | `main.py:7632`, `:7746` | about 1,500 MAU at 0.2 questions per MAU a day; earlier on busy days | every non-owner reader is refused, Pro included, once 300 questions are in the last 24 hours |
| 3 | Yahoo pacing, 2 requests a second | `yf.py:241-243` | about 2,000 MAU; about 800 if peak concurrency is three times A11 | cold pages wait at the limiter, background scans and watches fall behind, and a Yahoo 429 halves the rate |
| 4 | Watch runner, 60 symbols a pass every 30 minutes | `watch_runner.py:50`, `main.py:3805` | as soon as more than 60 distinct symbols are watched; at 600, each is checked every 5 hours | alerts arrive late; no extra cost |
| 5 | Brokerage background sync, 10 connections per 10-minute loop | `auto_sync_due`, `brokerage/service.py:835`; `background_loop`, `brokerage/routes.py:358` | about 210 connections in the 3.5 hours between the 09:00 and 12:30 slots; about 7,800 to 11,700 MAU under A8 and A9 | fewer than four pulls a day per reader |
| 6 | SnapTrade rate limit, 250 requests a minute | `snaptrade.py:28` | about 40 syncs a minute; four slots a day stop fitting at about 8,000 connections | 429s from SnapTrade |
| 7 | SQLite | `db.py:79-110` | not before 10,000 MAU: about 18,000 to 26,000 small writes a day, peaks of a few a second (assumption: half of daily actives signed in, 3 `/api/auth/me` a day each at 2 writes; 5 writes per question; 8 per sync) | not a near-term limit; the Metrics page slows first |
| n/a | One Python process | `Dockerfile:50-55` | CPU per request is not measured (Server-Timing has a process CPU field) | the chat context work blocks the event loop for tens of milliseconds (BUG-113, Phase 10); adding workers needs a shared cache and a shared Yahoo limiter first |

How row 3 was worked out: a distinct symbol open in a Dossier costs Yahoo about 3 requests a minute however many readers watch it (the header polls `/api/quote` every 20 s and `/api/session` every 60 s, `dossier-frame.js:75-86`, but the server answers from its 30-second and 60-second entries), and a cold symbol costs 11 to 12. With A11, reader demand is about 2.8 requests a minute per concurrent reader, or 0.041 per MAU at peak. Leaving about 20 a minute for the background jobs, the 120-a-minute budget is reached near 2,400 MAU; I round down to 2,000 for the bursts the average hides. At 10,000 MAU demand is about 410 a minute, three to four times the budget. Serving that needs licensed data with higher limits, or a shared cache across processes, both owner decisions.

### 9.2 What the server-wide Milo ceiling implies

- **Capacity:** 300 questions in any 24 hours is about 9,100 a month: 100 Free accounts using all 3 a day, or 20 Pro accounts using 15. At 0.2 questions per MAU a day it serves about 1,500 MAU.
- **Spend:** it bounds questions, not tokens. At the typical mix it is about $44 a day ($1,335 a month); the code comment's $33 a day uses the older $0.11. If every question used every limit (a script can send a 60,000-character history; the question is capped at 8,000 characters; tool rounds are the model's choice), the bound is about $430 a day, about $13,100 a month.
- **Fairness:** Free and Pro share it, so Free accounts can use up the day for paying readers.
- **Options (owner decisions, no new service needed):** a dollar ceiling counted from the ledger, which already prices every call (`ai_store.usage`), for example "no new non-owner Milo calls once today's estimated spend passes $X"; separate ceilings per plan; a spend limit set in the Anthropic console, which is the only bound on the owner's own use; and knowing the organisation's tier before launch.

## 10. Options that need the owner's approval

None of these is recommended as approved. Each is listed with its price and what it changes.

| Option | Price (label) | What it buys | Also needs |
|---|---|---|---|
| Know and, if needed, raise the Anthropic tier; set a console spend limit | no charge for the limit; tier is by usage history (VERIFIED) | avoids the month-long stop at the tier cap; bounds the owner's own use | owner's Console access |
| Licensed market data (Intrinio + OPRA + Twelve Data, or the fallback) | $2,049 to $2,399 a month floor; band $2,000 to $3,600 (PROVISIONAL) | licence for display, higher limits than Yahoo pacing allows | counsel; Milo named in the order form |
| SnapTrade Launch | $100 a month + $1 or $2 per connected user (VERIFIED) | real readers linking | KYC and billing at SnapTrade |
| Railway Pro, if the service is on Hobby | $20 a month including $20 of usage (VERIFIED) | 30-day logs instead of 7, volumes up to 1,000 GB instead of 5 | |
| Error tracking (Sentry Developer free, Team $29) | VERIFIED | errors with stack traces | Privacy policy names it; it receives request data |
| Uptime and logs (Better Stack free, or $34 a responder) | VERIFIED | outage alerts, longer log search | same |
| Mail relay (Resend free 3,000 a month, Pro $20) | VERIFIED | verification, reset and alert mail | DNS records; policy names it (the policy says it will) |
| A shared cache for more than one worker (a Redis service on Railway, billed by its resources) | PROVISIONAL | horizontal scaling without doubling Yahoo traffic | code work; only worth it with licensed data |
| A model-based advice check per answer (BL-07) | at Haiku 5.5 prices about $0.0003 an answer (ESTIMATE: 2,000 in, 100 out) | a second reading of each answer | BL-01 to measure |
| Ceilings: raise or split `MILO_QUESTIONS_PER_DAY`, add a dollar ceiling | no charge | capacity versus bounded spend | the owner's numbers |

## 11. What would replace the estimates with measurements

1. The owner's Claude usage page (`/api/ai/usage`, owner only, free, `main.py:6097`) gives per-feature calls, tokens, cache reads, web searches and estimated cost; with the Metrics page's question counts (`/api/admin/metrics`) it gives calls per question and cost per question. Replace sections 4.2 and 4.4 with those figures.
2. The Claude Console: the organisation's tier, spend cap, cache hit rate and the billed total (the ledger's figure is an estimate at list prices).
3. Railway's usage page: CPU, RAM, egress, volume size and the plan. Replace A10 and the Railway row.
4. The `Server-Timing` header on `/api/ticker` and `/api/quote` reports, per build, the queue time for a worker thread, the process CPU used, and each leg's wait at the limiter (`main.py:459-476`); a sample of cold and warm loads at busy times would size the single process and show the queue growing before readers notice.
5. The Yahoo limiter: the `Server-Timing` header's per-leg `gate` time is how long each fetch waited at the limiter, the direct sign that row 3 of section 9.1 is being reached. The limiter's own state is not exposed today: `pace_state` (`yf.py`) has no caller and `throttle_state` is read only by the tracker scan (`paper.py:977`).
6. Recording thinking tokens (`usage.output_tokens_details.thinking_tokens`) in the ledger would show how much of Milo's output is reasoning, which is what the effort level trades.

## 12. Redundant calls and safe caching opportunities

| ID | Finding | Where | Status | Expected saving |
|---|---|---|---|---|
| C1 | **Milo re-sends the CONTEXT turn at full price on every tool round.** The only breakpoint is on the system block; each round appends the assistant content and tool results and sends the whole conversation again. Mark the newest user turn (an explicit breakpoint on its last block) or use top-level automatic caching, keeping the system breakpoint. The prompt does not change, so answers do not change. A single-call answer pays 1.25x on its uncached part, about $0.0015 for a light question. | `ai.py:3484` (only breakpoint), `:3708`, `:3737` (appends) | **built 2026-11-02 on `phase-12-writing-milo-security`, not deployed**: top-level automatic caching beside the system breakpoint (`build_chat_request`); DECISIONS D-117 | typical tool-using question $0.14 to $0.10 (warm), $0.18 to $0.13 (cold); worst case $1.44 to $0.88; Milo spend down 22% to 24%: about $22 a month at 100 MAU, $217 at 1,000, $325 at the 300-a-day ceiling. Check with the ledger's `cache_read_tokens`. |
| C2 | **The ledger misses a round the reader cancels.** `_streamed` runs only after `get_final_message()`; the `except Exception` does not catch `asyncio.CancelledError`, which is what a disconnect raises in the response generator (Starlette 0.49.3). Anthropic bills the tokens generated before the cut. Same in deep research. | `ai.py:3669`, `:3779-3783`; `:3855`, `:3893-3897` | new; from code reading, not tested | no dollars; makes `/api/ai/usage` match the Console. A `finally` that records the partial usage, or a "cancelled" row, would do it. |
| C3 | **Sonnet 5.5 cache hits are priced at $0.20 in the app; the page says $0.10.** | `ai_store.py:112-119` | new | no dollars; the usage page overstates Milo's cache-read cost by about $0.0016 per prefix read |
| C4 | **Classic writes the catalyst read when its panel is opened.** It calls `/api/catalyst-mode` without `cached=true`; v2 asks for the cached read on load and writes only on request. | `static/app.js:18815`; v2 `read.js:325`, `:357`; route `main.py:5092` | new; Classic is changed only with the owner's say | up to 24 Opus calls a day, about $35 a month at the ceiling |
| C5 | **Duplicate Yahoo reads (S09).** The calendar was read twice for the next report date and the consensus band; fund facts and the futures contract month each made a second three-request `.info` read. Now one shared `cal:` entry and the quote's own `.info`. | `_calendar` `yf.py:1314-1317`, `earnings_date` `:1319`, `earnings_calendar` `:1808`; `contract_month` `:1297`; `fund_meta` `:1789` | in progress in the working tree | one calendar request per symbol per hour of reads, three per fund per day, three per futures symbol per 6 hours. No dollars; less pressure on the 2-a-second budget |
| C6 | **No memory of a dead feed host (S16).** Now 60 s (`HOST_DOWN_SECONDS`). Left: every store rewrites the whole `feed_cache.json` (871 KB locally). | `feeds.py:116-119`; `_store` `feeds.py:760-772` | in progress; the rewrite is not addressed | no dollars (Railway does not bill volume I/O); CPU and disk writes per feed refresh |
| C7 | **Symbol directory retried on every search after a failed refresh, under its lock (S19).** Now retried after 15 minutes. | `universe.py:405-407` | in progress | no dollars; stops two 25-second downloads per search during an outage |
| C8 | **Unbounded Yahoo adapter cache (S01).** Now swept and capped at 20,000 entries; unknown chart periods refused. | `yf.py:81-100`; `main.py:415` | in progress | RAM at $10 per GB-month, and fewer OOM restarts, each of which re-pays the warm-up and cold loads |
| C9 | **The Dossier header polls `/api/quote` every 20 s, forced past the browser cache, but the server's quote lives 30 s.** One poll in three gets the same server entry. Polling every 30 s would not change Yahoo traffic or the data's age by more than 10 s. | `dossier-frame.js:75-86`; S03 | owner decision (freshness wording) | a third of quote polls to Optic, about 1 request a minute per open Dossier tab |
| C10 | **Home requests `/api/session` twice** in the Phase 10 performance baseline (`duplicate_api: [["session", 2]]`, 2026-10-30 02:52). | `phase10/perf/perf-baseline.json` | cause not traced here | one request per Home load |
| C11 | Writers carry no cache markers. Their prefixes (prompt plus policy, about 900 to 1,900 tokens) are above the 512-token minimum, but a reuse inside 5 minutes happens only when several briefs or sector reads are written in a row. | `_ask` callers in `ai.py` | low value | about $0.005 per reuse on Opus |

Not counted as redundant: the per-answer tool memo already collapses repeated tool calls (`Toolbox._memo`, `milo_tools.py:807-868`); open writers wait for an in-flight write of the same piece instead of paying twice (`main.py:1441-1480`, `_write_lock` `ai.py:2144`); the Read and the desk are claimed on disk so a deploy does not pay again (`ai_store.claim`).

**Other cost levers, which trade quality and need the owner's decision and an evaluation** (blocked locally by BL-01): Milo's effort level (chat medium, `ai.py:3493`; research high, `:3834`); a cheaper model for scan reading, portfolio briefings or catalyst reads; a smaller context budget for deep research, which leans on web results. The Batch API (half price) suits none of the writers except the weekly update, where it would save about $0.15 a month.
