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
| Compare | Compare | `#/compare` | Current app |
| Markets | Read | `#/read` | Current app |
| Markets | Macro | `#/macro` | Current app |
| Markets | Indices | `#/indices` | Current app |
| Discover | Explore | `#/explore` | Current app |
| Discover | Scan | `#/scan` | Current app |
| Discover | Insiders | `#/insiders` | Current app |
| Discover | Analysts | `#/analysts` | Current app |
| Positions | Optic Portfolio | `#/portfolio` | Current app |
| Positions | Paper Desk | `#/paper` | Current app |
| Positions | Retirement | `#/retirement` | Current app |
| Brokerage | Brokerage | `#/brokerage` | Current app |
| Watchlist | Watchlist | `#/watchlist` | Rebuilt |
| Watchlist | Alerts | `#/alerts` | Rebuilt |
| Reports | Problem Reports | `#/reports` | Current app |
| Reports | Claude usage | `#/usage` | Current app |
| Reports | Accounts | `#/accounts` | Current app |
| (rail footer) | Settings | `#/settings` | Current app |
| (none) | Instrument | `#/instrument/{SYM}` | Current app |

## Shell and global

| Feature | Status | Note |
|---|---|---|
| Rail with section headings Research, Tracking, Owner | Changed | Groups only. A group's pages are tabs at the top of its pages, so each name appears in one place (owner's point 1). Names unchanged. |
| Gold outlined hover pill | Rebuilt | Rail rows and the brand only. |
| Brokerage group shown only when linking is available | Rebuilt | From `/api/brokerage/status`. |
| Reports group for the owner only | Rebuilt | From `/api/auth/me` `admin`. |
| Phone bar: Home, Dossier, Markets, Discover, More | Rebuilt | More opens a sheet with the remaining groups and Settings. |
| Rail Collapse | Not yet | |
| Search and command palette (⌘K, `/`) | Changed | Symbols from `/api/search`, recent symbols and the navigation's pages. Not yet: saved research, screens from `/api/scanners`, quick actions. |
| Ask Milo in the top bar | Rebuilt | Carries the page's context; gold outline. |
| Account menu | Changed | Name, email, plan, owner badge, links, sign out. Not yet in v2: resend verification. |
| Sign in and create account (email and password) | Rebuilt | `/api/auth/login`, `/api/auth/register`. |
| Passkeys, Google, Apple, forgot and reset password, verify email | Current app | Linked from the v2 sign-in page. |
| Guest things on sign-in ("bring them in" or "leave them") | Rebuilt | Same holder and shelf logic and keys as `static/app.js` (`core/device.js`); guest lists are adopted into the account. |
| Account switch from another tab reloads this one | Rebuilt | |
| Theme (system, light, dark) | Rebuilt | Reads `optic.theme`; changed in Settings in the current app. |
| Text size, time zone, knowledge level, advanced switch | Not yet | Set in Settings in the current app. |
| Toasts with Undo | Rebuilt | |
| Footer health chip | Not yet | |

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
| What matters now (ranked cross-asset moves) | Not yet | |
| What changed since yesterday (`POST /api/briefing`) | Not yet | Each watchlist row carries its own "what changed". |
| Moved most this month | Rebuilt | `/api/scanners/movers`, with the building state. |
| Your watchlist feed | Rebuilt | Rows open the company beside the list. |
| Ask Milo question chips | Changed | One contextual Ask Milo per block. |
| What's happening (Read headlines) | Not yet | |
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
| Thesis | Current app | Linked from the Overview. |
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
| EMA clouds, MA Trend, TSO, studies (VWAP, Keltner, Donchian, regression), stages, accumulation zones, auto trends, VBP, zones, sessions, insider marks | Current app | Linked. |
| Widgets: watch, alerts, news, analysts, season, notes, insiders, reports, checklist, stop check, options, levels, stats, patterns, pairs, backtest, trading, learn | Current app | Linked. |
| Colours, legend, full screen, navigator | Not yet | |
| Explain chart with Milo | Rebuilt | |

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

## Validation record

See `VALIDATION.md` beside this file for the checks run on the first journey.
