# Feature registry

The inventory later phases refer to instead of rediscovering. Part 1 is the architecture, Part 2 the routes
(index here, full per-route entries in [registry/](registry/)), Part 3 the API, Part 4 journeys, Part 5 shared
state and dependencies, Part 6 the security baseline, Part 7 unshipped work on other branches.

Evidence labels: **Source** = read from code at 9fa0f36; **Rendered** = seen in headless Chrome on the local
server (`optic-ultra`, :8250) at a stated size, in the crawl of 2026-10-29 (`~/Optic/work/post-demo-ultra-2026-10-29/crawl1`).

## Part 1. Architecture (Source unless marked)

### Front end

| Area | What exists | Notes |
|---|---|---|
| Frameworks | None. Two complete front ends served by the same FastAPI app. **v2** (`static/v2`, default at `/` since 2026-10-19 via `OPTIC_DEFAULT_UI=v2`): vanilla ES modules, no build; 112 JS files, about 24,500 lines (49 pages, 33 ui, 30 core) and 4 CSS files (tokens 9 KB, base 4 KB, components 117 KB, pages 210 KB). **Classic** (`/classic`): `static/app.js` (2.66 MB, one script), `charts.js`, `styles.css` (844 KB), `auth.js`, `brokerage.js`, `research.js`, `valuation.js`, `components/knowledge.js`. | Both are live; Classic stays until a separate retirement approval (owner, 2026-10-21). The iPhone app (unmerged `ios-app`) bundles v2. |
| Fonts | Inter Variable and Space Grotesk Variable from cdn.jsdelivr.net (`@fontsource-variable`). | BUG-019 |
| Charting | Own SVG engines, no library. v2: `ui/pricechart.js` (candles, drawings, studies, panes, gestures), `ui/chart.js` (lines), `ui/bars.js`, `ui/xychart.js`, `ui/drawings.js`, `ui/studies.js`, `ui/timeaxis.js`. Classic: `charts.js`. | Gesture rules: `docs/frontend-v2/CHART-GESTURES.md` |
| Animation | No library. CSS transitions on tokens (`--m-press`, `--m-content`, `--m-panel`, `--m-exit`, `--ease-out`) and `ui/motion.js` (a loading line tied to on-screen skeletons; the Dossier tab bar slide; fade of tab content). Reduced motion turns them off. | |
| Routing | Hash router `core/router.js` using Classic's address scheme; the navigation model is `nav.js` (9 rail groups, 27 pages, phone bar of 5). | Part 2 |
| Client state | `core/store.js` (watchlist, recent companies `optic.recent.v1`, lists), `core/prefs.js` (theme, scale, time zone, knowledge level `optic.knowledge.v1`), `core/device.js` (signed-in readers' local data kept with the account), per-page module state. No framework store. | Part 5 |
| Design system | `css/tokens.css`, `docs/frontend-v2/DESIGN-STANDARD.md`, guarded by `tests/test_v2_design_standard.py` and `tests/test_v2_checklist.py`; the `optic-frontend` skill holds the owner's standing UI rules. | |
| Milo UI | `ui/milo.js` (panel, 1,335 lines), `core/milo-text.js` (Markdown), `static/components/scout.js` (the mascot, shared with Classic). | Phase 07 |

### Back end

| Area | What exists | Notes |
|---|---|---|
| Service | One FastAPI app, one uvicorn worker (`Dockerfile`: yfinance access is serialised in-process). 241 routes, 231 under `/api`; `app/main.py` (8,336 lines) defines 141, routers add auth 32, account 29, brokerage 25, valuation store 5, billing 4. A static mount at `/` serves the front ends. 189 Python modules, about 94,600 lines. | `baseline/api-routes.json` |
| Guards | Called inside handlers, not FastAPI dependencies: `require_user` (60 handlers), `csrf_guard` (50), `_write_guard` (10), `_is_owner`/`_owner_session_guard` (7), `_spend_guard` (4: Milo chat, deep research, the pre-earnings brief write, the plain-English scan `/api/screener/ask`), `_is_operator` cooldowns on public scans. | Part 6 |
| Background work | In-process loops: tracker (scans every four hours, the morning Read at 09:00 ET), watch runner, catalysts, Desk edition, shortlist, brokerage sync slots. Switches `WATCH_AUTO`, `TRACKER_AUTO`, `BRIEF_AUTO`, `CATALYST_AUTO`, `DESK_EDITION_AUTO`, `SHORTLIST_AUTO`. | |
| Authentication | `app/auth/`: email and password (Argon2id), Google and Apple sign-in (ID tokens checked against their JWKS), passkeys (py_webauthn), server sessions in SQLite. Cookie `optic_session` HttpOnly, Secure when hosted, SameSite=Lax; CSRF double submit (`optic_csrf` cookie read by the page, `X-Optic-CSRF` header). Admin = `ADMIN_EMAILS` plus a confirmed address. Plans in `app/auth/store.py` (`PLANS`; Free has three Milo questions a day). Guests get 401 on paid endpoints. | CLAUDE.md "Things that will bite you" |
| Persistence | 18 SQLite files under `TRACKER_DATA_DIR` (a Railway volume): `accounts.db` (users, identities, passwords, sessions, resets, verifications, passkeys, OAuth states, watchlists, saved research, `user_preferences` with time zone / default market / default landing only, subscriptions, sign-in attempts, watches and hits, theses, feedback, signals, valuations, seven brokerage tables, webhook events, valuation models, portfolio alerts and briefings, activity days, `milo_questions` holding time, user and kind only), `ai.db` (call ledger, kept writes), `brief.db`, `catalysts.db`, `desk_editions.db`, the paper ledger, `alerts.db`, `analysts.db`, `observations.db`, `iv_history.db`, `index_daily.db`, `research_forecasts.db`, `segments.db`, `signal_archive.db`, `shortlist.db`, `weekly.db`, `optic.db`, `dolthub_vol.db`; JSON caches (`feed_cache.json`, `symbols.json`, `universe_nasdaq.json`, `screen_ranking.json`, `earnings_consensus.json`, others). Daily scrubbed `accounts.db` snapshots (`app/snapshots.py`). | No server-side store of Milo conversations exists. |
| Brokerage | `app/brokerage/`: SnapTrade provider (`api.snaptrade.com`) and a sandbox provider with synthetic accounts; credentials encrypted with `OPTIC_DATA_KEY` (`app/vault`); consent records, purges, webhooks with signature checks; read-only (no order placement anywhere). Workspace: overview, holdings, performance, events, connections; look-through, exposure, options risk, scorecard, alerts; an AI portfolio brief (`ai.write_portfolio_brief`). `BROKERAGE_OWNER_ONLY` limits linking to the owner in production. | Phase 02 (advice), 09 |
| Market data | Yahoo Finance through `yfinance` (quotes delayed about 15 minutes, history, option chains, fundamentals, profiles, insiders, news): unlicensed. An undocumented Robinhood endpoint for overnight prints (`app/providers/overnight.py`, no flag at this commit). SEC EDGAR (company facts, filings, Form 4), FRED, Treasury, BLS, Census, EIA, Federal Reserve, USAspending, the House Clerk's disclosures, Nasdaq Trader's symbol directory, Cboe, CFTC, CME, DoltHub (behind a flag), news RSS (CNBC, BBC, Dow Jones, WSJ, FT, The Economist and more), logos through Optic's own `/api/logo` proxy. | BUG-022, BLOCKERS |
| AI | Anthropic SDK. `MODEL = claude-opus-5-5` for the writers, `PULSE_MODEL = claude-sonnet-5-5` for Milo. Every call goes through `app/ai.py`: `_ask(client, feature, ...)` (recorded in the ledger) or `client.beta.messages.stream` (`stream_chat`, `deep_research`). Twelve features, all prompts in `app/ai.py`: Milo (`SYSTEM_PROMPT`, `FORMAT_PROMPT`, `PERSONAS`, `FLAVOUR_PROMPT`), deep research (`RESEARCH_PROMPT`), pre-earnings brief (`EARNINGS_PROMPT`), linked-portfolio brief (`PORTFOLIO_BRIEF_PROMPT`), sector read (`SECTOR_PROMPT`), weekly update (`WEEKLY_PROMPT`), catalyst extraction and read (`CATALYST_PROMPT`, `CATALYST_READ_PROMPT`), morning Read (`MORNING_PROMPT`), Desk note (`DESK_PROMPT`), Desk edition (`EDITION_PROMPT`), plain-English scan (`SCAN_PROMPT`). Knowledge modes in `app/knowledge.py` (simple 0, literate 1, advanced 2, professional 3, adaptive = 1 with per-answer adaptation). Tools in `app/milo_tools.py`. Prices in `app/ai_store.py`. | Phases 02, 05, 07, 08 |
| Streaming | Server-sent events over `StreamingResponse` (`text/event-stream`) for `/api/chat` and `/api/research`. Events seen (Rendered, stand-in): `assumed` (level, horizon), `status` (what is being fetched), `retrieved` (sources with `as_of`), `delta` (text), `done` (model, citations, sources read). The whole context is built before the response starts. | TEST_RESULTS Milo probe |
| Logging and monitoring | Python logging (`optic` logger); mail in log mode writes `[mail:log]` lines; `/healthz` (Railway's health check), `/api/health`, `/api/build` (build ids for open tabs); owner pages Problem Reports (`/api/feedback`), Claude usage (`/api/ai/usage`), Accounts, Metrics (`/api/admin/metrics`); Cloudflare injects its Web Analytics beacon at the edge (named on the Privacy page). | Phase 10 |
| Tests | 516 files in `tests/`, 7,108 tests: v2 (64 files), chart (27), pulse/Milo (34), home (12), auth (10), brokerage (9), session (8) and more. Client behaviour is asserted by reading JS as text or running pure functions under JavaScriptCore; no browser end-to-end suite in the repository. | TEST_RESULTS |
| Build and deploy | `Dockerfile` (python:3.12-slim) built by Railway (`railway.json`: health check `/healthz`, one replica, restart always), auto-deployed from `origin/main`. Front-end switch: `OPTIC_DEFAULT_UI` (classic or v2), `OPTIC_V2_ACCESS` (all, owner, off). | |

### Duplicate, abandoned or conflicting systems (do not delete yet; directive 01)

1. **Two front ends** (v2 and Classic), both maintained; Classic is the fallback at `/classic` by the owner's decision.
2. **Three homes for the knowledge level** (`app/knowledge.py`, Classic's `components/knowledge.js`, v2's `core/prefs.js`) plus a density switch ("Show advanced analysis") that rewrites the same key (BUG-002).
3. **Two market-session models**: `app/session.py` is authoritative; Classic's `marketSessionFromClock()` is a pre-load fallback (CLAUDE.md).
4. **Several search entry points**: the top-bar palette, the shared typeahead (`data-v2-ta`) on the Dossier start page, Compare and Analysts, the Home workspace's ticker box, and Classic's search. Shared parts are mapped in Part 2.
5. **Two scoring models with overlapping horizons** (Overview's Optic Score vs Compare's swing setup), giving different numbers for one company (BUG-011).
6. **Several daily AI notes**: the morning Read, the Desk note, the Desk edition and the weekly update overlap in what they cover.
7. **Abandoned hosting files**: `render.yaml`, `fly.toml`, `netlify.toml`, `run.sh`, `share.sh`, `share-detached.sh`, `stop-share.sh`, `tunnel-watchdog.sh` (last touched 2026-08-01 to 2026-09-02; production is Railway) and `publish.sh` (superseded by worktree pushes; do not use).
8. **Parallel unshipped implementations** of the same areas on other branches (Part 7).

*Phase 04 updates:* item 2's density switch is now a setting of its own, apart from the knowledge level (D-019). A
ninth item was found and resolved: an unrouted second Home page in `pages/home.js` (welcome card, starters, strip,
scene, loaders, its own search box), kept alive only as an import for its blocks and edited as if live. It was
removed with the workspace's handlers for controls nothing draws (D-021, SIMPLICITY_AUDIT.md section 8).

*Phase 05 updates:* the knowledge level now has one home for its styles (`app/knowledge.py`, five levels: New to Markets, Beginner, Intermediate, Advanced, Expert, D-026) and one value: Classic's key `optic.knowledge.v1` in the browser, which both front ends read, and `user_preferences.knowledge_level` for a signed-in reader (migration 19), kept in step by one rule in each front end (D-028). One slider (`static/v2/js/ui/levelslider.js`) sets it on Home's first-visit card, in Settings and in Milo's Response settings; Milo's own Level select is gone. Density stays apart (D-019).

*Phase 06 updates:* the Dossier Overview shows one analysis view at a time in `#ov-analysis`: the Simple Analysis (`static/v2/js/pages/overview-simple.js`, three answers by fixed rules at the reader's level) or the Advanced Analysis (Classic's research from `pages/overview-research.js`, word for word, in twelve sections). "Show advanced analysis" and "Show simple analysis" swap them through the density setting (D-035). Every response is tied to its visit (D-039). The pipeline is mapped in DOSSIER_PIPELINE.md.

*Phase 07 updates:* Milo's chat route starts its response at once and names each step (`status` gathering, writing, then a tool by name), and the `done` event carries the answer's own timing (`StreamClock`, D-043). The panel draws an answer as it arrives: the finished part once, appended where drawing in pieces equals drawing whole (`settledEnd`), the arriving paragraph as markdown (`streamingHTML`), the chart once (D-044). New output follows only a reader at the end (D-045). New conversation and history wait for an answer with the reason, Close leaves it running, and the panel reopens where the reader was (D-046). Conversations stay in the browser, per account (D-047). The 14 stages and their measured times are in STREAMING_PIPELINE.md.

*Phase 09 updates:*
- **Delay wording:** quotes are said to be "delayed up to 15 minutes" everywhere, and each quote keeps its own trade time and stated delay.
- **Dividend yield:** a stock's is its dividend rate over the price shown.
- **Indicators:** the RSI's warm-up is empty, and VWAP needs volume.
- **Market session:** the calendar matches NYSE's for 2026 and 2027; half days and holiday evenings read as closed, each saying why.
- **Pattern study:** the panel's sentences state the study's own figures in both apps.
- **Scores:** each score reads one way on every page, and the Overview and Compare say why their numbers differ.
- **Freshness:** stale stand-ins, corporate actions and watchlist rows say their age.
- **Privacy:** signed-in API answers are private, and deleted brokerage data leaves memory at once.
- **Where it is written down:** the pathways, caches and the reconciliation are in DATA_PATHWAYS.md and RECONCILIATION.md.

*Phase 08 updates:* Milo has seventeen tools. The four new ones are `lookup_company`, `get_price_history`, `get_filings` and `get_financials` (`app/milo_data.py`, from the milo-upgrade branch). Every tool result carries a `meta` freshness block, and quotes carry the trade's own time. The research pack, framework and chart levels follow the symbol the question names. Figures loaded for a symbol the question named have their own source, "Loaded for your question" (`[[src auto_loaded]]`), in both front ends. A plain definition fetches nothing before the model starts. The tool contracts and what Milo cannot reach are in MILO_TOOLS.md. The evaluation suite (`tests/milo_eval`, 137 cases) runs with every test run, and `tests/milo_eval/run_model.py` runs it against the real model when a key is accepted (BL-01).

## Part 2. Routes and features: the index

Every route the v2 router accepts (`static/v2/js/core/router.js`) and every global component, with its feature id,
where its source-level entry is (controls with handlers, inputs, charts, tables, AI sections, tooltips, menus,
loading/error/empty states, API calls, storage keys, auth needs, risks, all with file:line) and where its rendered
inventory is (what a guest and a signed-in reader actually see at 1440). Totals: 56 crawled route variants, 31 global
and account entries, 27 Home panel kinds, 9 Dossier entries, 15 tracking and owner entries, 26 Classic views mapped.

| Feature id | Route or component | Auth | Source entry | Rendered |
|---|---|---|---|---|
| F-SHELL-01..11 | Boot, router and loader, rail, top bar, phone bar and More, drawer, legal footer, not found and failure views, banners and live regions, click and key delegation, scroll memory | all | registry/A A1-A11 | rendered-inventory "App shell"; `#/thisisnotavalidpage` |
| F-SEARCH-01..04 | Search palette (Ctrl/Cmd K, "/"), shared typeahead (`data-v2-ta`), every other symbol box, search backend (`/api/search`, `/api/logo`, `/api/scanners`) | all | registry/A A12-A15 | `#/dossier`, palette checked by hand (FEATURE_REGISTRY Part 4) |
| F-MILO-01..05 | Milo panel, answer renderer, Scout, chat and research endpoints, levels/personas/timeframes | guest sees the account prompt; asking needs an account | registry/A A16-A20 | panel opened by hand as a guest |
| F-ACCT-01..11 | Sign in / up / forgot / reset (`#/signin`), email and provider links and passkeys, Settings (`#/settings`), Terms and Privacy (`#/terms`, `#/privacy`), Dossier start (`#/dossier`), Saved research (`#/research`), device session, preferences/store/API client, auth endpoints, storage key table, synced vs device settings | mixed | registry/A A21-A31 | `#/signin`, `#/settings`, `#/terms`, `#/privacy`, `#/dossier`, `#/research` |
| F-HOME-00 | Home `#/` (and the old `#/workspace`): layouts, Customize, linked ticker and "Follows" chip, first-visit band, density | all; more panels when signed in | registry/B section 2 | `#/`, `#/workspace` |
| F-HOME-01..27 | Home panels: portfolio, priority, desk, changes, questions, trends, alerts, indices, regime, expected, sectors, calendar, earnings, movers, watch, quote, cnews, news, economy, contracts, value, vol, gex, tearn, biz, fin, own | per panel | registry/B section 3 | `#/` |
| F-MKT-01..05 | Read `#/read`, Macro `#/macro`, Indices `#/indices`, Instrument `#/instrument/<SYM>`, Earnings week `#/earnings` (`?week=1`) | all | registry/B 4.1-4.5 | `#/read`, `#/macro`, `#/indices`, `#/instrument/^GSPC`, `^TNX`, `CL=F`, `#/earnings`, `?week=1` |
| F-DISC-01..04 | Explore `#/explore`, Scan `#/scan` (`?q=`), Insiders `#/insiders`, Analysts `#/analysts` | all | registry/B 4.6-4.9 | same routes |
| F-CMP-01 | Compare `#/compare`, `?t=A,B` | all | registry/B 4.10 | `#/compare`, `#/compare?t=NVDA,MSFT` |
| F-DOSSIER-00..08 | Dossier frame; Overview `#/<SYM>`; Chart, Options, Investing, Earnings, Financials, News tabs; printable Sheet `#/<SYM>/sheet`; plus the "Show advanced analysis" trace and the Dossier pipeline map | all | registry/C | NVDA (all tabs), SPY (all tabs), BRK.B, BTC-USD, ZZZZQ |
| F-POS-01..03 | Optic Portfolio `#/portfolio`, Paper Desk `#/paper` (`?replay=`), Retirement `#/retirement` | all (Paper Desk and Retirement keep data in the browser) | registry/D section 1 | same routes |
| F-BRK-00..05 | Brokerage gate and frame, Overview, Holdings and exposure, Performance, Events and research, Connections (`#/brokerage/<section>`) | account; linking owner-only in production | registry/D section 2 | `#/brokerage` and its five sections, guest and signed in |
| F-FOL-01..02 | Watchlist `#/watchlist`, Alerts `#/alerts` | guest lists in the browser; account lists on the server | registry/D section 3 | same routes |
| F-OWN-01..04 | Problem Reports `#/reports`, Claude usage `#/usage`, Accounts `#/accounts`, Metrics `#/metrics` | owner | registry/D section 4 | guest (refused) and owner |
| F-CLASSIC | 26 Classic views at `/classic`, each mapped to its v2 page | as v2 | registry/D section 5 | Classic crawl 1440 and 390 |
| F-API | 232 API routes with method, handler and guards | per route | registry/api-routes.md | n/a |

## Part 3. API (Source)

[registry/api-routes.md](registry/api-routes.md) lists all 232 routes (231 under `/api` plus `/healthz`) with method,
handler (file:line) and the guard calls its body makes. Summary: 148 open by design, 43 need a session and CSRF, 17 a
session, 14 owner or operator, 6 CSRF only (sign-in steps), 4 metered spend (`POST /api/chat`, `POST /api/research`,
`POST /api/earnings/{ticker}/brief`, `POST /api/screener/ask`), 2 streaming (`/api/chat`, `/api/research`). Each page's own calls are in its
registry entry and its rendered-inventory block.

## Part 4. Core journeys as they work at 9fa0f36 (Rendered on :8250 unless marked Source)

| Journey | Steps today | Where it breaks or overloads | Context that should persist |
|---|---|---|---|
| First-time visit | `/` serves v2 Home: "Good morning", a "New to Optic? Three ways to start" card (search a company, read today's market, follow a company: 8 buttons), four layout tabs plus Customize, then 12 panels (Markets at a glance, Market conditions, Expected move, Sector heatmap, Quote and chart, Watchlist, Economic calendar, Earnings this week, What matters today, Market news, Optic Desk, Moved most this month). 187 controls and 1,135 words at 1440. | No sentence says what Optic is; no question about how Optic should explain things (Classic asked); jargon in the first screens (VIX ÷ 16, 14-day ATR, "Optic's market score 19 from −100"). BUG-005. | The reader's knowledge level (Phase 05); SPY as the market context (Phase 03). |
| Onboarding | No account is needed to read. "Not now" dismisses the welcome card (and marks the knowledge question asked). Sign-in at `#/signin`: email and password, Google, Apple, passkey; sign-up agreement line. Free plan: 3 Milo questions a day. | Production mail is in log mode, so a non-admin never receives the confirmation or reset link (BUG-021, owner-side). | Guest watchlist and recents move into the account on sign-in (`core/device.js`). |
| Ticker search | Three boxes: the top-bar palette (Ctrl/Cmd K; companies, funds, pages, "ask Milo"), the Dossier start box (shared typeahead), the Home workspace's ticker box. "nvidia" + Enter and "amd" + immediate Enter opened the right Dossier; "msft" in the palette offers "Open MSFT" first. | Basic cases pass; the demo's inconsistency needs the Phase 03 scenario matrix (rapid changes, invalid, punctuation, refresh, latency, failure). | The chosen symbol becomes the head of `optic.recent.v1`, which Home then follows (BUG-003). |
| Research and Dossier | `#/SYM` Overview: header (logo, price, change, close time, overnight print, Stage label + Explain, Alert, Compare, Export, Watch, Ask about SYM, more), seven tabs, the "Show advanced analysis" switch, a section jump bar with Expand all / Collapse all / Panels, then 11 sections and 21 folds (1,384 words for NVDA). | The switch appends instead of replacing and rewrites the knowledge level (BUG-001, BUG-002); reading load (BUG-004). | Symbol in the URL across tabs; advanced-mode state should not leak into the knowledge level. |
| Chart exploration | `#/SYM/chart`: own SVG engine; Indicators, Layers, Chart read, Reset; bar size, session hours, range, Fit, Reset zoom, style; a 15-tool drawing rail; side widget rail. 99 controls at 1440 for SPY. | Density on first open (Phase 04); no symbol-free chart route, so "the default chart" for SPY is Home's Quote and chart panel or `#/SPY/chart` (Phase 03 decides). | Drawings per symbol (`optic.chart.drawings.v2`), chart settings (`optic.v2.chart.v1`). |
| Milo conversation | Top-bar "Ask Milo", or "Ask Milo about X" buttons on panels, or the palette. The panel states the context ("SPY / Overview", "What is attached: 10 parts"), the persona menu, "Response settings", a delayed-data and not-advice line, history and close buttons. Guests are asked to make a free account. Server: SSE stream with honest status and sources (TEST_RESULTS). | No New Chat control (Phase 07); first byte waits for the full context (1.5 to 2.2 s cold with the stand-in, before the model); real-model answers never checked (BL-01). | Conversation across page changes and after closing the panel; the knowledge level. |
| Brokerage connection | `#/brokerage`: consent record, "Connect a brokerage" (SnapTrade portal; sandbox locally), "What Optic can and cannot see", connections, holdings, performance, events. Guests see a sign-in prompt. Production: `BROKERAGE_OWNER_ONLY`. | Sandbox connections are lost when the local server restarts (reconnect needed for tests). | Which accounts count; sync state. |
| Portfolio research | Brokerage overview and holdings (look-through, exposure, options risk, scorecard, alerts, an AI portfolio brief); Optic Portfolio `#/portfolio` (Optic's own tracked book, shared by every visitor); Paper Desk `#/paper` (browser-only book); Retirement `#/retirement`. | Milo's portfolio tool offered on every page (BUG-007, P0); advice risk in the portfolio brief and scorecard wording (Phase 02). | Portfolio facts only when the reader asks about their own portfolio. |
| Account settings | `#/settings` (signed in, 992 words, 48 controls): Profile, Security (password, passkeys, connected accounts, 30 active sessions with Revoke, sign out of all devices), Plan, Delete account, Appearance (Dark / Light / Follow system), motion, Text size (Compact / Default / Large), Keyboard shortcuts, "How Milo explains things" (one switch, "Advanced answers from Milo": on means Advanced or Professional, off means Simple, Financially Literate or Adaptive; it also opens the paper portfolio's risk rules), Time zone (17 choices), About this build, Report a problem. Guests see a shorter page (634 words). | The five-way level exists only in Milo's Response settings; Settings offers a binary switch, and the Dossier's advanced switch writes the same key (three writers, one key). | One authoritative preference (Phase 05). |

## Part 5. Shared state and dependencies (Source; regressions start here)

Module fan-in in `static/v2/js` (files importing each): `core/api.js` 56, `core/store.js` 39, `ui/milo.js` 35,
`core/device.js` 19, `core/prefs.js` 12, `core/poll.js` 6, `core/track.js` 6, `ui/palette.js` 2,
`ui/typeahead.js` 1. A change to any of the first five reaches most pages.

| Shared thing | Where it lives | Who writes it | Who reads it | Regression risk |
|---|---|---|---|---|
| The open company | the route (`#/SYM/...`), parsed by `core/router.js` (share classes canonicalised, `BRK.B` to `BRK-B`) | navigation, search results, links | every Dossier tab, the header, Milo's context | low: URL is authoritative per page |
| Companies opened before | `optic.recent.v1` (localStorage, shared with Classic, restored on sign-in) via `store.pushRecent` / `store.recent()`; `store.openedNow()` for this visit (memory only) | every Dossier tab on load (chart.js:702, options.js:469, earnings.js:230, financials.js:400, news.js:81, investing.js:300), the Home ticker box (workspace.js:935) | Home's linked ticker (workspace.js:189), the palette's default symbol (palette.js:85), Compare's suggestions and first slot (compare.js:152, 264), the Dossier start page (dossierstart.js:29), the shell's Dossier link (shell.js:98, 135) | high: this is how "Follows <T>" and the missing SPY default arise (BUG-003) |
| Home's linked ticker | `S.link` in the workspace state (`optic.v2.workspace.v1`) | the ticker box and the ticker buttons (workspace.js:934) | every "linked" Home panel and its "Follows" chip (workspace.js:747-758) | Phase 03 removes it |
| Knowledge level | `optic.knowledge.v1` (+ `optic.knowledge.basic.v1` remembering the lower rung, `optic.knowledge.asked.v1` for the first-visit question) | Settings, the Milo panel, Home's first-visit question (home.js:493, 632; workspace.js:1058, 1105), the "Show advanced analysis" switch (dossier-frame.js), Classic's `components/knowledge.js` | glossary marks (`ui/glossmark.js`), folds (`ui/sections.js`), Milo requests (`mode`), the server (`app/knowledge.py` normalises) | high: one key, three writers, two meanings (BUG-002) |
| Other display preferences | `optic.theme`, `optic.ui.scale.v1`, `optic.timezone`, `optic.v2.motion.v1` (`core/prefs.js`); server `user_preferences` holds time zone, default market, default landing only | Settings | the whole shell | medium |
| Milo settings and conversation | `optic.pulse.persona.v1`, `optic.milo.horizon.v1`, `optic.chat.width.v1/.v2`, history in `optic.pulse.history.v1` (localStorage); no server-side conversation store exists (`milo_questions` keeps time, user and kind only) | the Milo panel | the Milo panel, `/api/chat` payload (`mode`, `persona`, `horizon`, `context`) | high for Phases 05, 07, 08 |
| Sign-in state | `store.state` from `/api/auth/me`; `signedIn()`, `plan()`; CSRF header from the `optic_csrf` cookie in `core/api.js` | sign-in, sign-out, `core/device.js` (moves guest things into the account and back) | 39 importers of the store; Milo allowance (`/api/ai-allowance`) | high |
| Guest things kept with the account | `core/device.js` list of keys (watchlists, watches, theses, research, valuations, drawings, notes, Paper Desk, Retirement inputs, snapshots, the owner's write token) | sign-in and sign-out | every page that keeps reader work | medium (privacy on shared devices) |
| Financial data | server caches per provider call (yfinance wrappers with TTLs, refusal memo; `ai.db` kept writes); client `api.get(url, {ttl})` memory cache keyed by URL | the provider layer | every page; Milo's tools call the same server functions | high for Phase 09 (cross-feature consistency) |
| AI prompts and policy | server only, `app/ai.py` (12 features) plus `app/knowledge.py` registers and `app/milo_tools.py`; the client sends level, persona, horizon and page context | n/a | every AI surface | Phase 02 centralises the policy here |
| Polling | `core/poll.js` (shared, stale-response guarded), `core/build.js` (new-version check), `core/status.js` (market session), `ui/strips.js` | the shell | pages that refresh | medium (Phase 10 duplicate requests) |

Where context should persist and does not, today: the market context on Home (should default to SPY rather than
the last company opened); the presentation choice on the Dossier (should be its own state, not the knowledge
level); a Milo conversation across closing and reopening the panel (Phase 07 verifies); the knowledge level for a
signed-in reader across devices (no server column; Phase 05).

## Part 6. Security baseline (non-destructive, 2026-10-29)

Method: read the guards each handler calls (`baseline/route-guards.json`), read every handler the scan could
not place, read cookie and header code, grep the front end for secrets and the back end for sensitive logging,
and three read-only GETs against production. No intrusive testing.

| Area | Finding | Evidence | Status |
|---|---|---|---|
| Route authorisation | 232 API routes: 148 open by design (research answers a guest exactly as before accounts existed, `tests/test_auth_authorization.py`), 60 need a session (43 also CSRF), 14 owner/operator, 4 metered spend. 18 handlers had no guard the scan could name; each was read: stateless computations on the posted body (`/api/digest`, `/api/signals/followup`, `/api/paper/mark`, `/api/options/{t}/analyze`, `/api/retirement`, `/api/valuation/{t}/run|sotp`, `/api/screener`, `/valuation-models/replay`), Optic's own shared book (`/api/tracker`, `/api/portfolio-risk`, `/api/portfolio-scenarios`), cooldown-limited public scans (`/api/tracker/mark|scan`, `/api/catalysts/refresh`, which can spend when `CATALYST_READER=model`), signature-checked webhooks (brokerage, Stripe), sandbox-only routes, and `_reader`-guarded brokerage workspace routes. | Source | no unguarded user-data route found |
| Session cookie | `optic_session`: HttpOnly, Secure when hosted, SameSite=Lax, path `/`. CSRF double submit: `optic_csrf` (readable by the page by design) plus `X-Optic-CSRF`. | app/auth/config.py:73-88, app/auth/deps.py:121 | ok |
| Security headers | Enforced: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, CSP `frame-ancestors 'none'; object-src 'none'; base-uri 'self'`. Live adds HSTS 180 days (Cloudflare). The full CSP is report-only and allows `'unsafe-inline'` scripts, so cross-site scripting defence rests on the templates' escaping. | app/main.py:8303-8332; curl -I local and live | P2 hardening (Phase 10) |
| API schema exposure | `/docs`, `/redoc`, `/openapi.json` served publicly in production. | live GETs 200/200/200 | BUG-006 |
| Secrets in the browser | None found. `STRIPE_SECRET_KEY` appears in `core/format.js` only as the name of a setting in a comment; non-owners never see setting names (`billingOff`). | grep of static/ | ok |
| Sensitive logging | OAuth failures log up to 400 characters of the provider's error body (client id at most); mail in log mode writes the recipient, masked unless the address is an admin's, and withholds links unless `MAIL_LOG_LINKS`. Milo's question log stores time, user and kind, never text. | app/auth/oauth.py:195-200, app/auth/mailer.py:69-132, app/db.py:948 | ok |
| Brokerage data | Read-only provider access; credentials encrypted with `OPTIC_DATA_KEY`; consent and purge records. One exposure path known: Milo's portfolio tool offered on every page (BUG-007, P0). | app/brokerage/, investor-readiness O03 | BUG-007 |
| Third parties in the page | Fonts from cdn.jsdelivr.net; Cloudflare's analytics beacon injected at the edge (named on the Privacy page). | static/v2/index.html:17-19 | BUG-019 |
| Data licensing | Unlicensed Yahoo data; undocumented Robinhood overnight endpoint without a switch. | app/providers/yf.py, app/providers/overnight.py | BUG-022, BUG-023 |
| Repository | Public, no LICENSE file (readiness audit). Local `.git/info/exclude` keeps the owner's private business-model drafts out. | memory, readiness audit | owner decision |

## Part 7. Unshipped work on other local branches (inputs, not merged; DECISIONS D-006)

Counted with `git cherry origin/main <branch>` (patch-equivalent commits already on main do not count), 2026-10-29.

| Branch | Unshipped commits | What it holds | Relevant to |
|---|---|---|---|
| milo-portfolio-privacy | 1 (2236205) | Milo offers or attaches the linked portfolio only for questions about the reader's own portfolio; tests NOT_ABOUT_THEM / ABOUT_THEM. Owner held it ("don't push"). | Phase 02, 08 (BUG-007) |
| milo-upgrade | 8 (to 55721f6) | Milo knowledge base (`app/guide/`), grounded data tools (`app/milo_data.py`, freshness envelope), context fixes, playbooks, and a 215-case evaluation harness (`tests/milo_eval`) whose answer checks were blocked by the refused key. From 9a40c55, owner-staged. | Phase 08 |
| milo-reasoning | 18 | Portfolio views, `get_returns` / `get_correlations`, concept cards, caret symbols; needs a rebase. | Phase 08 |
| milo-voice, validation | 32, 19 | Older Milo evaluation and track-record work; superseded in part. | Phase 08 (reference only) |
| polish-rebased (stack of 8 passes) | 11 | Interface-audit remediation of 2026-10-24: research consistency, content accuracy (session-aware Desk), navigation (renames the owner approved: Scan to Screener, Positions to Portfolios, My Desk to My layout), Home simplification, Overview consolidation, chart defaults, Milo simplification, polish. Owner reviewing. | Phase 04, 06, 07 |
| source-foundation | 15 | Provenance states, Yahoo refusal handling, SEC pacing, Treasury curve, P/E guards; owner approval pending. | Phase 09 |
| p0-readiness | 1 (rest shipped in a783dc5) | F-02: `OPTIC_OVERNIGHT_FEED`, default off. | Phase 02 (BUG-022) |
| earnings-view-wording | 2 | Earnings view wording and a clock-pinned test. | Phase 02 (BUG-008) |
| input-defects | 2 | Report time of day reaching the volatility surface (regime breadth part shipped). | Phase 09 |
| portfolio-triggers | 6 | Portfolio rule repairs, research watch, SEC release clock. | Phase 09 |
| ios-app | 6 | The iPhone app (bundles v2). Owner rule: web and app changes ship together. | All front-end phases (note only) |
| others (home-declutter, plate-system, desk-redesign, simplify-pass, hig-pass, ux-redesign, paywall, pulse-phone, motion-video, v2-viz-rest, v2-refine, v2-dark-workspace, brokerage-link, chart-clarity, home-simplify, milo-simplify, nav-clarity, overview-consolidate, research-consistency, content-accuracy, overview-classic-port, read-conviction-wording, polish) | 1 to 16 each | Superseded drafts, stacked copies of polish-rebased, rejected designs (desk-redesign), or work already folded into later releases. | reference only |

## Part 8. First-pass visual audit (Rendered; no UI changed)

Evidence: every route captured at 1440x900, 1280x800, 768x1024 and 390x844 for a guest and a signed-in reader
(`crawl1/<state>-<size>/<label>.png` and `-full.png`), Classic at 1440 and 390; reviewed in the main session as
labelled contact sheets (`sheets/guest-w390-*.jpg`, `sheets/guest-w1440-*.jpg`, `sheets/full1440-*.jpg`, the last
for Home, NVDA Overview, Options, Investing, Financials, Read, Compare, Scan, Analysts), plus the measurements of
the crawl (overflow, clipped text, contrast, unnamed controls and small targets from `audit.js`, word and control
counts). The two screenshot-review agents stopped at the usage limit before writing anything (DECISIONS D-007).

| # | Finding | Where (size) | P | Bug |
|---|---|---|---|---|
| V-01 | Competing elements on the first screen: welcome card with 8 actions, 4 layout tabs and Customize, then 12 panels whose headers each carry About, Ask Milo, options and Refresh (about 48 icon buttons) | Home (1440, 1280; on 390 the welcome card fills most of the first screen) | P1 | BUG-005 |
| V-02 | Very long pages with sections of equal weight: NVDA Overview about 6,000 px, Investing and Financials past the 6,000 px capture cap, Analysts 2,648 words, Compare's side-by-side table | 1440 full pages | P1 | BUG-004 |
| V-03 | Jargon on first screens without a plain lead: "VIX 16.91 ÷ 16, about ±82 points", "14-day ATR 0.90% ÷ 1.6", "Priced against typical 1.89×" (Home Expected move); implied move, delta, open interest, gamma (Options); "Stage 2 · Advancing", "Grade B", scores 50 and 87 (Overview) | Home, Options, Overview | P1 | BUG-004/005 (Phase 04) |
| V-04 | The same explanatory sentence repeated on every row: each of the Read's 20 earnings rows ends "An earnings report resets the estimate the price is built on, which is why the option market charges more into it" | Read (1440) | P1 | BUG-076 |
| V-05 | Notices placed after the content they qualify: Options' "Not a recommendation. The strikes, limit prices, stops and targets ... are model output" sits at the foot of a long page | Options (1440) | P1 | BUG-063 |
| V-06 | Loud colour where no direction is implied: the saturated green and red sector heatmap is the strongest element on Home; coloured analyst ratings (Buy green, Underweight red) in a long table | Home, Analysts (1440) | P2 | BUG-077 |
| V-07 | Several empty panels at once on a fresh server ("Today's Read is not ready yet", "The first build scans about 150 companies and takes a minute or two", "No wire headlines"): honest wording, but a first visitor after a deploy sees a page of waiting boxes (locally the jobs are off, so this is exaggerated here) | Home, Read (1440) | P2 | BUG-016 |
| V-08 | Header while loading: placeholder logo and a lone ticker at the right edge | cold Dossier (800) | P2 | BUG-031 |
| V-09 | No sideways overflow on any route at any size; 13 ellipsis truncations on Compare and 8 to 12 on Home (labels in tiles) | all | ok / P2 | |
| V-10 | Small touch targets at 390: 30 on NVDA Overview and Investing, 24 on BRK-B, 12 on BTC (audit script) | phone | P2 | BUG-014 |
| V-11 | Consistent shell, type and card chrome across every v2 route; the dark theme and gold accents read as one product; contrast and unnamed-control checks were 0 on every load | all | ok | |

