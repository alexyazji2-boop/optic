# Frontend v2: migration and feature coverage

The rebuilt frontend lives in `static/v2/` and is served at `/v2/` next to the current app, which is unchanged. A page marked **Current app** opens the classic page at the same address (`/#/...`), so every section stays reachable while pages move across. `tests/test_frontend_v2.py` fails if a navigation page is missing from the page table below.

Status words:
- **Rebuilt**: works in v2 against the real backend.
- **Current app**: v2 links to the classic page.
- **Not yet**: no v2 entry point; the classic page still has it.
- **Changed**: rebuilt, but presented differently; the note says how.

## Pages

| Group | Page | Address | Status |
|---|---|---|---|
| Home | Home | `#/` | Rebuilt |
| Dossier | Overview | `#/{SYM}` | Rebuilt |
| Dossier | Chart | `#/{SYM}/chart` | Rebuilt |
| Dossier | Options | `#/{SYM}/options` | Rebuilt |
| Dossier | Investing | `#/{SYM}/investing` | Rebuilt |
| Dossier | Earnings | `#/{SYM}/earnings` | Rebuilt |
| Dossier | Financials | `#/{SYM}/financials` | Rebuilt |
| Dossier | News | `#/{SYM}/news` | Rebuilt |
| Compare | Compare | `#/compare` | Rebuilt |
| Markets | Read | `#/read` | Rebuilt |
| Markets | Macro | `#/macro` | Rebuilt |
| Markets | Indices | `#/indices` | Rebuilt |
| Discover | Explore | `#/explore` | Rebuilt |
| Discover | Scan | `#/scan` | Rebuilt |
| Discover | Insiders | `#/insiders` | Rebuilt |
| Discover | Analysts | `#/analysts` | Rebuilt |
| Positions | Optic Portfolio | `#/portfolio` | Rebuilt |
| Positions | Paper Desk | `#/paper` | Rebuilt |
| Positions | Retirement | `#/retirement` | Rebuilt |
| Brokerage | Brokerage | `#/brokerage` | Rebuilt |
| Watchlist | Watchlist | `#/watchlist` | Rebuilt |
| Watchlist | Alerts | `#/alerts` | Rebuilt |
| Reports | Problem Reports | `#/reports` | Rebuilt |
| Reports | Claude usage | `#/usage` | Rebuilt |
| Reports | Accounts | `#/accounts` | Rebuilt |
| (rail footer) | Settings | `#/settings` | Rebuilt |
| (none) | Instrument | `#/instrument/{SYM}` | Rebuilt |

## Shell and global

| Feature | Status | Note |
|---|---|---|
| Rail with section headings Research, Tracking, Owner | Changed | Groups only. A group's pages are tabs at the top of its pages, so each name appears in one place (owner's point 1). Names unchanged. |
| Gold outlined hover pill | Rebuilt | Rail rows and the brand only. |
| Brokerage group shown only when linking is available | Rebuilt | From `/api/brokerage/status`. |
| Reports group for the owner only | Rebuilt | From `/api/auth/me` `admin`. |
| Phone bar: Home, Dossier, Markets, Discover, More | Rebuilt | More opens a sheet with the remaining groups and Settings. |
| Rail Collapse | Rebuilt | Stage 0. Same key as Classic, `optic.rail.tight.v2`. |
| Search and command palette (⌘K, `/`) | Rebuilt | Stage 0: exact page names first, symbols with their actions, saved research, screens from `/api/scanners` with the sector board, quick actions, and an Ask Milo row that drafts the typed question. |
| Ask Milo in the top bar | Rebuilt | Carries the page's context; gold outline. |
| Account menu | Changed | Name, email, plan, owner badge, links, sign out. Resending the confirmation link is in Settings. |
| Sign in and create account (email and password) | Rebuilt | `/api/auth/login`, `/api/auth/register`. |
| Passkeys, Google, Apple, forgot and reset password, verify email | Rebuilt | Stage 0. Links from e-mail (`?verify`, `?reset`) and provider callbacks (`?auth=ok`, `?auth_error`) are handled in v2; a provider sign-in started in v2 returns to v2. |
| Guest things on sign-in ("bring them in" or "leave them") | Rebuilt | Same holder and shelf logic and keys as `static/app.js` (`core/device.js`); guest lists are adopted into the account. |
| Account switch from another tab reloads this one | Rebuilt | |
| Theme (system, light, dark) | Rebuilt | `optic.theme`, set in v2 Settings or the current app's; either holds in both. |
| Text size, time zone, advanced switch | Changed | Same keys as the current app (`core/prefs.js`). Text size scales v2 from the classic Default; times on the rebuilt Settings and Reports pages follow the chosen zone. The advanced switch is saved for both apps; v2 pages already fold specialist material into tabs and details, so it does not change their layout yet. |
| Toasts with Undo | Rebuilt | |
| Footer health chip | Rebuilt | Stage 0: footer status from `/api/health`, session chip, offline bar, new-version bar (which also carries a rollback to the classic app). |

## Home

| Feature | Status | Note |
|---|---|---|
| Market strip (8 instruments, overnight futures swap, basis points for yields, as-of line) | Rebuilt | From `/api/home` `macro.groups`, same rules as `marketStripHTML`. Cells open the instrument in the current app. |
| Greeting with the account's first name, date and session | Rebuilt | |
| Search box | Rebuilt | On the welcome; the palette everywhere. |
| Recent symbols / "Or jump to" quick picks | Changed | Recent symbols are in the palette. New visitors get four names to follow instead. |
| New-visitor state | Changed | Welcome with headline and search first, a short illustration after (owner's point 2), names to follow, three ways to start. |
| "How should Optic speak to you?" (knowledge modes) | Rebuilt | `/api/knowledge/modes`, same keys. |
| What matters today (events, earnings, sectors) | Changed | `/api/priority`, grouped Now / Today / This week, three per group with Show more, filter to your names, each opens in place. |
| Catalyst day strip | Not yet | |
| Optic Desk (edition, bottom line, full read, Ask Milo) | Changed | Lead lines and the full read; scenarios and today's reports not yet. |
| What matters now (ranked cross-asset moves) | Changed | The same ranking is on Discover, Explore, under Cross-asset; "What moved most" on Home's market panel opens it. |
| What changed since yesterday (`POST /api/briefing`) | Not yet | Each watchlist row carries its own "what changed". |
| Moved most this month | Rebuilt | `/api/scanners/movers`, with the building state. |
| Your watchlist feed | Rebuilt | Rows open the company beside the list. |
| Ask Milo question chips | Changed | One contextual Ask Milo per block. |
| What's happening (Read headlines) | Changed | Home links to the rebuilt Read, which carries the summary, search and headlines. |
| Latest scan alerts | Rebuilt | From `/api/home` `alerts`. |
| Index and sector trends board | Not yet | |
| The market's expected move (statement panel) | Changed | Moved from Macro to Home's one charcoal panel: VIX-implied day, its basis, and the S&P 500's three months. |
| Portfolio value and chart | Rebuilt | Only with a linked brokerage: `/api/brokerage/workspace/overview` and `/performance`. |
| Degraded-feed line | Rebuilt | |
| Refresh while open | Changed | Every 60 seconds while the tab is visible (was 20). |

## Dossier, Overview

| Feature | Status | Note |
|---|---|---|
| Header: symbol, name, price, change, data state | Rebuilt | Compact on phones. |
| Weinstein stage chip | Not yet | |
| Watch / Watching, Alert, Ask Milo | Rebuilt | Alert opens Alerts with the symbol filled in. |
| Tabs to the other Dossier pages | Rebuilt | The only place they are listed. All seven Dossier pages are rebuilt. |
| What does it do (profile) | Changed | Under More on the company. |
| What changed lately (digest) | Rebuilt | `/api/digest`. |
| Four questions (framework) | Changed | Answered directly with stated rules; evidence and method in the drawer. |
| Optic Score (short term) | Not yet | |
| Long-term score | Changed | Shown as "Long-term trend score, from price history" beside "Long-term case, from the business and its price", with why they differ (owner's point 3). No calculation changed. |
| Year chart with earnings markers | Rebuilt | `/api/ticker` price series; markers open the report. |
| Options-implied range ahead of the price | Rebuilt | From `/api/earnings` implied move. |
| Priced against history (ratio) | Changed | Basis stated beside the ratio (owner's point 4). |
| Key figures | Rebuilt | Under More on the company. |
| Factors, What to look at next | Not yet | |
| Thesis check | Current app | Linked. |
| Advanced research (Pulse score, all statistics, rest of ticker, headlines, method) | Changed | Headlines, filings, bull and bear case under More; the rest not yet. |
| Fund view (takeaways instead of framework) | Not yet | |
| Fair value | Rebuilt | In "Is the price attractive?". |

## Dossier, Options

| Feature | Status | Note |
|---|---|---|
| Price head, key stats | Changed | The shared company header; key figures are on the Overview. |
| What options are pricing (implied move, report-day average, ratio with its basis, IV30 and rank, skew, dealer gamma) | Changed | A compact row of readings first, one expiry across them, scrolling sideways on phones (owner's point 2). |
| Plain read and pulse line | Rebuilt | The digest's one-line read under the header. |
| Position builder: 10 templates by nearest delta, legs (buy/sell, quantity, remove), costs (slippage, fee, days) | Rebuilt | Same strike picks as `optTemplate`; priced by `POST /api/options/{T}/analyze`. |
| Entry at the mid, crossing the spread, with slippage and fees; max profit and loss; breakevens | Rebuilt | The classic wording. |
| Payoff chart (at expiry, today, halfway), greeks, scenario grid by when | Rebuilt | |
| Flags, events, leg liquidity, assumptions, Ask Milo about this position | Rebuilt | |
| Research contracts: expiry, side, delta band, widest spread, least open interest, unquoted, more columns, Add | Rebuilt | Same filters key `optic.options.filters.v1`. |
| What options are pricing in full, compare expiries | Rebuilt | Tab. |
| Dealer gamma: net, regime, flip, walls, by strike, profile, near-term, vanna and charm | Rebuilt | Tab. |
| Call vs put flow, net premium by strike, most active contracts, options intelligence | Rebuilt | Tab. |
| Delta analysis, at-the-money greeks by expiry, gamma analysis | Changed | Tab; the open-interest butterfly chart is a table. |
| Buy calls or puts, strategies, idea payoff charts, budget control | Rebuilt | Tab; same budget key `optic.entry.budget.v1`. |
| Strike and entry recommendation, candidate strikes, volatility context | Rebuilt | Tab. |
| Swing verdict, breakdown, what each input measures, Optic's perspective, what's pulling hardest, what matters next, follow-ups | Rebuilt | Tab. |
| Price, averages, Fibonacci, support and resistance, RSI, MACD, structure, close defence | Changed | Tab of tables; the drawn chart is the Chart page. |
| How an option's value moves (Greeks lab) | Rebuilt | Tab. |
| Swing setups | Changed | Tab lists armed, triggered and watched setups; filters, rule settings, back-tests and setup alerts in the current app. |
| Chart patterns, seasonality, relative performance | Rebuilt | Tab. |
| Thesis | Current app | Linked from the Overview. Brokerage theses are edited in v2; a v2 save keeps the Dossier's snapshot (server fix, Stage 0). |
| Track record slots | Not yet | |
| Silent refresh | Changed | Readings every 60 seconds while the market trades (was 20). |
| Knowledge-level folding | Changed | Deeper panels are one tab away for everyone. |

## Dossier, Chart

| Feature | Status | Note |
|---|---|---|
| Bar sizes 1m to 1W, ranges, session | Rebuilt | Opens on 1h as before. |
| Candles, line, area | Rebuilt | |
| MA 20/50/200, EMA 9/21/50, Bollinger, Fibonacci, support and resistance, dealer gamma levels, earnings marks | Rebuilt | |
| Volume, RSI, MACD panes | Rebuilt | |
| Zoom (wheel, pinch, buttons), pan, fit, crosshair, OHLC readout, keyboard reading | Rebuilt | |
| Drawings: horizontal and vertical lines, trend, ray, rectangle, Fibonacci, text; select, delete, undo, remove all | Rebuilt | Same key and format `optic.chart.drawings.v2`. Kinds only the classic app makes show as a line. |
| Channel, Fib extension, pitchfork, arrow, ruler, risk box, position sizing; snap; moving a drawing | Not yet | |
| EMA clouds, MA Trend, TSO, studies (VWAP, Keltner, Donchian, regression), stages, accumulation zones, auto trends, VBP, zones, sessions | Rebuilt | 2026-10-19, in Indicators under the classic names. The classic maths where v2 computes it, the classic endpoints otherwise. Stages and MA Trend colour the candles (MA Trend wins while both are on, as in Classic); the line and area styles are not tinted. Auto trend lines draw on daily and weekly bars only. |
| Panes: ADX and DI, Stochastic, on-balance volume, money flow index, relative strength line | Rebuilt | 2026-10-19 (C19), from /api/indicators on the chart's own bars, with their reference levels; the chart grows past two panes. |
| Insider marks | Rebuilt | 2026-10-19: green and red arrows for purchases and sales, with a box naming each trade on hover, tap or the keyboard (Classic's hover text never showed, under its crosshair layer). The Insider trades overlay is on by default; Classic's is off. The payload keeps two years of filings, not the 12 latest; v2's Financials table shows the latest 20 of them. |
| Widgets: watch, alerts, news, analysts, season, notes, insiders, reports, checklist, stop check, options, levels, stats, patterns, pairs, backtest, trading, learn | Rebuilt | 2026-10-19, `pages/chart-widgets.js`: the classic rail beside the plot (a row under it on narrower screens, a strip on a phone), the same names, order and marks. Several open at once on a wide screen, one on a phone. Notes, checklist, stop check, backtest and pairs keep their inputs in the classic keys. Watch shows the account's watchlists, not a separate chart list. Reports, Options and Insiders read the payload's real fields, which three classic widgets missed (`financials.growth` and `margins`, `atm_greeks` as a list, `percent_of_float`). |
| Colours, legend, full screen, navigator | Rebuilt | 2026-10-19, `pages/chart-chrome.js`. Colours in the toolbar for the up and down candles (and their volume bars) and the line, in the classic key `optic.chart.colors.v1`, so a colour chosen in either app shows in both; v2's theme colours until one is chosen. 11 of the classic picker's 13 presets (Lime and Coral left out, to keep each row to two lines on a phone; the wheel reaches any colour). The legend sits on the plot's corner as in Classic, folded unless opened (`optic.chart.legend.v1`), with each line's value at the crosshair and a cross per overlay; it replaces the key line under the chart. Classic's eye (hide an overlay but keep its settings) is not carried over: v2's overlays have no settings to keep. Full screen hides the sidebar, top bar, phone bar and tabs and asks the browser for its own full screen (an iPhone keeps its bars). The navigator runs under the plot at its width. Fit has its own mark now: the four corners are full screen's, as in Classic. |
| Explain chart with Milo | Rebuilt | |
| Market structure breaks (MSB) | New in v2 | 2026-10-18: swing highs and lows with 3, 5 or 10 bars either side. The chart shows where a swing formed (dotted) apart from when it became known (once the bars after it closed); only a close after that can break it. A break is marked bullish or bearish with its level, an MSB label and a marker, and never changes when later bars arrive (tested on every prefix). In Milo's chart context. Not in the classic app. |

## Dossier, Investing

| Feature | Status | Note |
|---|---|---|
| The long-term picture and long-term view (score, phase, plan, factors) | Changed | Labelled "Long-term trend score, from price history", with the conflict sentence when the price is dear. |
| Return and risk | Rebuilt | |
| Weekly structure: weekly or monthly, 1Y to All, 40 and 200 averages | Changed | Line with averages; candle style, levels menu and pan not yet. |
| Drawdown | Rebuilt | |
| Revenue and the multiple, multiple and revenue history, valuation against its own history | Rebuilt | |
| Fair value, stars, analysts, dividend score, Morningstar | Rebuilt | Field chart drawn as the meter. |
| Discounted cash flow workspace | Changed | Summary: base, scenarios, what the price implies, what moves the value. Editing, saved models and other methods in the current app. |
| Valuation scenarios (bear, base, bull), fill from history, save | Rebuilt | Same arithmetic, `/api/valuations` signed in, `optic.valuation.v1` signed out. |
| Valuation and accumulation levels | Rebuilt | |

## Dossier, Earnings

| Feature | Status | Note |
|---|---|---|
| Next report or latest result, tiles, why | Rebuilt | |
| Pre-earnings brief | Changed | Loads on request, because it is a paid model call; the classic app requested it on every visit. |
| Event pricing | Rebuilt | With the basis beside the ratio. |
| Estimate revisions, surprise history, financial growth, analyst view | Rebuilt | Charts as bars. |
| Earnings this week (no symbol) | Current app | |

## Dossier, Financials

| Feature | Status | Note |
|---|---|---|
| What the statements say | Rebuilt | |
| Short interest, earnings track record, financials (charts, annual table, balance sheet) | Rebuilt | |
| Recent SEC filings, insider and institutional activity | Rebuilt | |
| Corporate actions and flow (dividends, splits, off-exchange short volume, against the index) | Rebuilt | Ratio chart not yet. |
| Congressional disclosures, segments and geography | Rebuilt | Segments re-read while filings remain, as before. |
| Funds have no Financials page | Rebuilt | |

## Dossier, News

| Feature | Status | Note |
|---|---|---|
| Tone, net sentiment, earnings warning, held-feed note | Rebuilt | |
| Timeline in two lanes | Rebuilt | Each mark is a link to the headline. |
| Catalyst types, filtering the headlines | Rebuilt | |
| Headlines about the company and market context, with tiers, tone and tags | Rebuilt | |
| How these are ranked | Rebuilt | |

## Markets, Read

| Feature | Status | Note |
|---|---|---|
| The day's Read: summary, sections, headline search | Changed | Served with `cached=true`: only what is already written. The server's own loop writes it every 20 minutes; if today's is missing, yesterday's is shown with its date, never a fresh model call. |
| Optic Desk edition, with its sources | Rebuilt | `/api/desk/edition`; citations link to each source. |
| Index strip | Rebuilt | |
| Overnight, worldwide | Rebuilt | From the Read's `global_overnight`. |
| Today's priority | Rebuilt | `/api/priority`. |
| Market catalyst | Changed | Shows the kept read only; "Write the read" is a labelled button because it is a model call. |
| Catalyst library: filters, search, scan for new | Rebuilt | "Scan for new catalysts" is a click, as before. |
| Weekly analysis | Changed | Kept copy only (`cached=true`); "Write this week's update" is a labelled button. |
| Fear and Greed, market regime | Rebuilt | |
| On the calendar: impact and range filters | Rebuilt | |
| Headlines; official releases and sources | Rebuilt | |
| Ask Milo | Rebuilt | Contextual buttons; nothing is asked until the reader sends. |

## Markets, Macro

| Feature | Status | Note |
|---|---|---|
| The market today, in brief; regime and its factors | Changed | Factors drawn as signed bars around zero with each rule beside them. |
| Expected S&P move from the VIX | Rebuilt | Also on Home's statement panel. |
| Breadth (equal weight against cap weight) | Rebuilt | |
| Yield curve | Rebuilt | |
| Rotation map | Rebuilt | Quadrants, tails and "crossed a boundary this week". |
| Economic data | Rebuilt | Series picker and chart. |
| Stock maps: templates, drill into a sector, the full table | Changed | The server's treemap layout, drawn at the slot's width; sectors open by click, Enter or Space. |
| Currencies with search, cross-asset, ratios, correlation and dispersion | Rebuilt | |
| Sector board with a Sector Read | Changed | The Sector Read is written only on click and says so; it is a model call. |
| Sector strength, themes and pairs | Rebuilt | |
| Quiet refresh during the session | Rebuilt | Every 60 seconds while the market is open. |

## Markets, Indices

| Feature | Status | Note |
|---|---|---|
| Readings: secular trend, dispersion, furthest from the high, style | Rebuilt | |
| Index fund board with an Index Read | Changed | Index Read only on click, labelled as a model call. |
| Long-run regime per index | Rebuilt | |
| Growth against the market (QQQ against SPY) | Rebuilt | |

## Instrument

| Feature | Status | Note |
|---|---|---|
| Five tiles (last, 20 days, against the 200-day, RSI, from the high) | Rebuilt | |
| Chart with range and style | Rebuilt | The Chart page's engine: line, candles, area; 1M to 5Y. |
| Reached from Home, Read, Macro and Explore | Rebuilt | |

## Discover, Explore

| Feature | Status | Note |
|---|---|---|
| What is worth a look (screenable names, biggest move, sector breadth) | Rebuilt | |
| Screens by group, each opening on Scan | Rebuilt | `#/scan?id=`. |
| Sectors against the S&P by their own week | Rebuilt | |
| Cross-asset moves against each instrument's typical day | Rebuilt | Same ranking (ATR / 1.6), index and future kept once; tested. |
| A partial page when a source is down | Rebuilt | Names what is missing; the rest still renders. |

## Discover, Scan

| Feature | Status | Note |
|---|---|---|
| Find stocks in plain words, examples, recent requests | Rebuilt | Same `optic.scan.recent.v1` key. The fixed reader is free; only words it cannot read go to Milo, and the page says so before the reader submits. |
| What was understood, what could not be asked, Edit as filters | Rebuilt | |
| Named scans: groups, scans, results, readings, blind spot, method | Changed | Same columns and formats; the in-cell bars are not drawn. |
| Ranking still building: progress and automatic retry | Rebuilt | Polls every 5 seconds while building, as before. |
| Build a screen: up to 8 bounds, states, sort, direction, funnel, ignored | Rebuilt | Same `optic.screener.v1` spec; a bound that is not a number is marked and the screen will not run. |
| Does the score work? | Rebuilt | On request, as before. |
| Ask Milo about the results | Rebuilt | |

## Discover, Insiders

| Feature | Status | Note |
|---|---|---|
| Symbol filter (also from `?symbol=`) | Rebuilt | |
| House trades: activity chart, window, most disclosed, the filings | Rebuilt | Chart drawn at its own width; most-disclosed names filter the page. |
| Insider filings (Form 4): show, refresh, read to the end for one company | Rebuilt | Reads up to 9 more rounds while filings remain, as before. |
| Federal contracts | Rebuilt | |

## Discover, Analysts

| Feature | Status | Note |
|---|---|---|
| Across covered names or one symbol | Rebuilt | |
| Show, rating and window filters | Rebuilt | A year's window for one symbol, as before. |
| Sortable table | Changed | Every column sorts; the classic table was newest first with no column sorting. |

## Compare

| Feature | Status | Note |
|---|---|---|
| Two to four tickers, add and remove boxes, suggestions while typing | Changed | Suggestions use the browser's own list (a datalist from `/api/search`) instead of a custom drop-down. |
| Recently viewed picks; nothing fetched until Compare | Rebuilt | |
| Pre-filled from the Dossier | Changed | The Dossier header has a Compare button; `#/compare?t=AAPL,MSFT` pre-fills and runs. |
| Horizon cards, Optic's take, standouts | Rebuilt | Same tie rule (5 points). |
| How they have moved (indexed to 100) | Rebuilt | |
| Where each name leads, per horizon | Rebuilt | |
| Metric table: groups, meanings, leader dots, rank reads, failures, method | Rebuilt | Same leader rule (2% of the row's spread); tested. |

## Positions, Optic Portfolio

| Feature | Status | Note |
|---|---|---|
| Three books with value, return, counts, rules, start dates | Rebuilt | |
| Run a scan now, Refresh marks, progress, cooldown messages | Rebuilt | Polls every 4 seconds while a scan runs. |
| Market-closed and rate-limit notices; risk limits (open when advanced is on) | Rebuilt | |
| Open positions: state of play, P&L chart, table with the stop-to-target gauge | Rebuilt | Same gauge arithmetic; tested. |
| Month by month: picker, tiles, closed and still-open tables, consistency chart and table | Rebuilt | |
| How the shortlist was chosen: funnel and screen ranking | Rebuilt | |
| Track record | Rebuilt | |
| Book-level risk: ratio, volatility, effective positions, money against risk, pairs, sectors | Changed | Money and risk shares in one table rather than a butterfly chart; sectors as bars. |
| Closed trades, earlier records, rules, caveats, scan history | Rebuilt | |
| Header tooltips (`data-defs`) and collapsible panels | Not yet | |

## Positions, Paper Desk

| Feature | Status | Note |
|---|---|---|
| The book in `optic.paper.v1`, 50 open, 200 closed | Rebuilt | Same key and record shape; a personal key, so it follows the person on this browser. |
| Ticket: shares or option, chain, expiry and strike, quote line, preview, validation | Rebuilt | Same checks and messages, in the same order. |
| Optic's read recorded on the trade ("Load it") | Rebuilt | From `/api/ticker`; no model call. |
| Portfolio health: lead, exposure bar, review list | Rebuilt | Same arithmetic; tested. |
| Marks from `/api/paper/mark`, Close at the mark | Rebuilt | |
| Record, R chart, with and against Optic | Rebuilt | |
| Clear the book (inline confirmation) | Rebuilt | |

## Positions, Retirement

| Feature | Status | Note |
|---|---|---|
| Inputs in `optic.roth.inputs`, Recalculate | Rebuilt | Same clamps; tested. |
| Model allocation, target weights, blended figures | Rebuilt | |
| Contribution projection with bands | Rebuilt | |
| Drift, this year's contribution, overlap, stock sleeve, Roth notes, fund universe, correlation | Rebuilt | |

## Brokerage

| Feature | Status | Note |
|---|---|---|
| Not signed in, plan upgrade, not available, switched off for non-owners | Rebuilt | The status endpoint decides, as before. |
| Six sections at their own addresses, remembered section and account scope | Rebuilt | Same keys (`optic.brokerage.section.v1`, `optic.brokerage.scope.v1`). |
| Overview: four tiles with source tags, what you own, deserves attention, coming up | Rebuilt | Refreshes every minute in the regular session. |
| Briefing: measured moves, possibly related headlines | Rebuilt | |
| "Write it up" | Rebuilt | A paid Milo message, labelled as such before the press. |
| Holdings, exposure with look-through, scorecard, options risk, cash, not counted | Rebuilt | |
| Performance: period and benchmark, returns, charts, flows, income, attribution, history | Rebuilt | |
| Events: calendar, theses (write, edit, delete), Desk items, alerts and alert settings | Rebuilt | |
| Scenarios (what-if lab) | Rebuilt | |
| Connections: consent, connect, reconnect, sync, disconnect, rename, count or not, delete all | Rebuilt | Inline confirmations. After linking, the provider returns to the current app's Brokerage page, because the callback address is the server's. |
| Ask Milo, section questions | Rebuilt | Draft only; nothing is sent until the reader presses Send. |

## Settings

| Feature | Status | Note |
|---|---|---|
| Guest account panel; sign in and create account | Rebuilt | |
| Profile: name, email confirmation, resend link | Rebuilt | |
| Security: password change or add, remove a method (never the last), passkeys add, rename, remove, Google and Apple connect and disconnect, sessions, sign out everywhere | Changed | The classic page asked with `confirm()` and `prompt()`; these are inline steps on the row. Long session lists show the five newest first. |
| Plan and billing (upgrade, manage, history, return message) | Rebuilt | Stripe returns to the current app's Settings page, because the return address is the server's. |
| Linked brokerages row | Rebuilt | Opens the rebuilt Connections section. |
| Delete account (typed email, password) | Rebuilt | |
| Appearance, text size, how much to show, time zone and market hours | Rebuilt | Same keys as the current app. |
| About this build | Rebuilt | |
| Report a problem | Rebuilt | A drawer from Settings; signed out, it asks you to sign in. |

## Reports (owner only)

| Feature | Status | Note |
|---|---|---|
| Problem Reports: open and resolved, mark resolved or reopen, resolve all (press twice) | Rebuilt | |
| Claude usage: by feature, totals, latest calls | Rebuilt | Reads the ledger only; no model call. |
| Accounts | Rebuilt | Owner session only, as before. |
| Not the owner, or signed out | Rebuilt | Same wording. |

## Watchlist

| Feature | Status | Note |
|---|---|---|
| Named lists: switch, new, rename, delete, reorder | Changed | Inline forms and an inline delete confirmation instead of browser prompts. |
| Plan limits (Free keeps 3; 12 in a browser) | Rebuilt | Same message. |
| Add a symbol | Rebuilt | |
| Summary (up and down, biggest move, changed, signals) | Rebuilt | |
| Sorts (7), filters (4), search in the list | Rebuilt | Same comparators. |
| My order with move up and down | Rebuilt | Only when unsorted and unfiltered, as before. |
| Remove with Undo | Rebuilt | |
| Rows open the company | Changed | A drawer beside the list instead of navigating. |
| Signed out: lists in this browser, same keys | Rebuilt | |
| First sign-in adopts the browser's list | Rebuilt | |

## Alerts

| Feature | Status | Note |
|---|---|---|
| What fired while you were away | Rebuilt | `/api/watches/hits`, mark all seen. |
| Your watches: builder, on and off, delete, Check now | Rebuilt | Account or browser, same keys and 40-watch limit. |
| Guest explanation and sign-in prompt | Rebuilt | |
| Signal history | Not yet | In the current app. |
| From the scheduled scan | Changed | Read-only list; kind filters, unread only and "Why this fired" not yet. |
| Owner controls (mark read, clear all, email delivery) | Current app | |

## Home as the research workspace (2026-10-18, private preview)

Home (`#/`) is the workspace (owner, 2026-10-18); `#/workspace` links land on Home. The old Home's blocks are its panels, with their copy unchanged. See WORKSPACE.md, VISUAL-SPEC-DARK.md, FEATURE-AUDIT.md and NEW-PRODUCTS.md.

## Stage 0 (2026-10-18)

Stage 0 closed the five blocking areas (Milo essentials, sign-in and account links, search and palette, legal notices, app shell and caching), and fixed the round-trip faults found when Classic and v2 shared the same data. See STAGE0-EVIDENCE.md, CAPABILITY-MATRIX.md (the three-way classification that replaces page counts), MIGRATION.md, BRANCH-REVIEW.md and PREVIEW-PROPOSAL.md beside this file.

## Validation record

See `VALIDATION.md` beside this file for the checks run on the first journey.
