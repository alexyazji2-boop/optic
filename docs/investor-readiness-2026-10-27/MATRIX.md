# Investor readiness audit: route and feature coverage matrix

Inventory taken from the code on 27 October 2026 (`static/v2/js/core/router.js`, `nav.js`, `app.js` PAGES,
`static/index.html` for Classic, every `@app`/`@router` decorator in `app/`):

- **v2** (served at "/" to guests and by default): **36 views**, reached at **41 addresses** (Brokerage has five
  sections). The crawl used **51 addresses**, adding a fund, a dot share class, a coin, three instruments, an
  unknown ticker, a mistyped address, a prefilled Compare and next week's calendar.
- **Classic** (at `/classic`, linked from v2's footer "Use the classic app"): **27 views**.
- **Server:** **235 API routes**; about 150 environment settings.

Statuses: **Passed**, **Failed**, **Fixed and verified**, **Blocked** (external dependency), **Not implemented**,
**Not applicable**, **Not tested** (in this audit). Defect IDs (D, O) are in `DEFECTS.md`.

How things were checked (column "Method"):
- **Crawl:** headless Chrome load of the address, settle on skeletons and network, then a probe for stuck loaders,
  error states, placeholder text (`undefined`, `NaN`, `n/a (n/a)`, raw field names), sideways overflow, clipped
  text, missing heading, console errors and exceptions, failed and duplicate requests, plus contrast, unnamed
  controls and small targets. Run as a guest and signed in, at 1440 and 390 px; cold (first pass) and warm.
- **Visual:** full-page screenshots read by three reviewers (Dossier desktop, other desktop, every phone page),
  each finding re-checked against the page or the code before it was logged.
- **Suite:** the project's own v2 browser checks (`~/Optic/work/v2-backlog`, run against this audit's server, quick
  mode at 390 and 1440). Results quoted as passed/total; failures traced to checks written before a later
  redesign are said to be stale only where the check's selector was compared with the current code.
- **Journey:** scripted end-to-end runs written for this audit (first use, Milo, sandbox brokerage).
- **Click pass:** every visible button, tab and menu on a page pressed once with a real mouse event; a control
  that changes nothing (no DOM change, request, address, focus or state) is listed. Destructive and sending
  controls are skipped by label.
- **Live:** the same crawl against theopticterminal.com as a signed-out visitor, every request that could start a
  paid model write answered 503 inside the browser before it left (Home's `/api/home`, writes to the Read, sector
  reads, catalyst feed, earnings briefs, any non-GET). Live build `a783dc562dcc`.

## Shell and app-wide features

| # | Feature | Entry, implementation | Expected | Needs | States | Method | Initial | Issue, fix | Retest | Limits |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | Rail navigation | rail, `ui/shell.js`, `nav.js` | each group opens its page; current one marked | none | guest, signed in, owner | Crawl (51 addresses x 4), suite navigation | Passed | | Passed | Names fixed by owner rule |
| S2 | Rail collapse | rail foot, `data-v2-rail-collapse` | narrows rail, kept | none | | | Not tested | | | |
| S3 | Search and command palette (⌘K, `/`) | top bar, `ui/palette.js` | exact names first, Enter opens, Escape closes, latest query wins | none | guest, signed in | Suite search 39/42 | Passed with one open case | "movers" + Enter at 390 stayed on Read (not reproduced by hand); 2 failures are an expectation for "spx" | Open | |
| S4 | Ask Milo (top bar) | `ui/milo.js` | opens panel, focus in the box (not on touch), drafts only | account for answers | signed in | Journey (Milo) | Passed | | Passed | Stand-in model |
| S5 | Account menu, sign out | `app.js` `accountBody` | name, plan, links, sign out ends session | account | signed in | Journey (first use) | Passed | | Passed | |
| S6 | Phone bar and More | `MOBILE_TABS` | Home, Markets, Watchlist, Dossier, More | none | guest, signed in at 390 | Crawl at 390, suite phone sweep | Passed | | Passed | Guest phone sweep did not finish (harness timeout) |
| S7 | Keyboard shortcuts dialog (`?`) | `ui/shortcuts.js` | lists shortcuts | none | | | Not tested | | | Keyboard focus covered by suite release-extra |
| S8 | Report a problem | footer, Settings | sends a report | none | | | Not tested | | | Would submit a report |
| S9 | Footer: Terms, Privacy, full disclaimer, Use the classic app | `core/legal.js` | links work | none | guest | Crawl, live, suite release-extra 13/13 (links) | Passed | | Passed | Classic itself: see C1 |
| S10 | New version notice | `core/build.js` | "A new version is ready. Reload / Later" after a deploy | none | | Observed during the audit | Passed | | | |
| S11 | Glossary terms | `ui/glossmark.js`, `ui/term.js` | press opens definition with Explain with Milo | none | guest, signed in | Click pass | Failed | D10 | Fixed and verified | |
| S12 | Symbol typeahead | `ui/typeahead.js` | suggestions under symbol boxes | none | | Suite watchlists, compare | Passed | | | |
| S13 | Sideways strips | `ui/strips.js` | edge arrows when there is more | none | 390, Large text | Crawl, phone sweep | Passed | chips past the edge at Large text are inside scrollers (O10) | | |
| S14 | Scroll kept on Back | `core/scrollmem.js` | Back returns to the same place | none | | Suite navigation | Passed | | | |
| S15 | Guest lists into the account | `core/device.js` | "Bring them into my account" adopts lists | account | guest to signed in | Suite adopt 1/1 | Passed | | | |
| S16 | Links from email (`?verify`, `?reset`) | `core/authlinks.js` | confirm address; open reset form; bad link says so | mail | guest | Journey (first use), bad tokens | Failed | D16 | Fixed and verified | |
| S17 | Theme, text size, motion | `core/prefs.js` | applied app-wide | none | dark only | Crawl (dark) | Not tested (light, sizes) | | | Phone sweep covered Large text and 200% zoom |
| S18 | Unknown address | `pages/bridge.js` | says so with Search and Home | none | guest | Crawl, live | Failed | D09 | Fixed and verified | Live until deploy |
| S19 | Share-class addresses (`#/BRK.B`) | `core/router.js` | open BRK-B | none | guest | Crawl, live | Failed | D03 | Fixed and verified | Live until deploy |

## Click pass

Run on 14 pages signed in at 1440, up to 45 distinct controls each, every control found afresh before it was
pressed: Home 28, Overview 32, Options 23, Investing 27, Earnings 25, Financials 31, News 23, Compare 9, Read 12,
Macro 13, Scan 39, Insiders 5, Watchlist 17, Alerts 10 controls with an effect. Controls that did nothing: each
page's own current tab (expected), Scan's empty "Find symbols now" (D23, fixed), and two glossary terms that open
on a real click (harness artefact, checked by hand). Destructive, sending and paid controls were skipped by label.
Not run on the other pages; Insiders reached only 5 of its 83 controls before its rows redrew.

## Pages (v2)

| # | Page, address | Implementation | Primary actions and expected result | Needs | States | Method | Initial | Issue, fix | Retest | Limits |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | Home `#/` | `pages/workspace.js`, `home.js` | layouts, Customize, linked panels follow one ticker, panels say source and time | none | new guest, returning guest, signed in | Crawl, visual, suite workspace 21/24 | Passed | D07 (recents), D24 (futures tiles overnight) | Fixed and verified | Local jobs off: Desk prose, calendar, earnings scan, movers not built. Live Home not loaded (can start a paid Desk write). 3 workspace checks not re-traced |
| P2 | Sign in, create account, forgot, reset `#/signin` | `pages/signin.js` | create (double press safe), confirm email, sign in, wrong password said, reset | mail for links | guest | Journey (first use) 14/14 | Passed | D16 | Fixed and verified | Mail through a local relay; production mail is in log mode (owner). Passkeys, Google, Apple not tested (Google and Apple not configured) |
| P3 | Settings `#/settings` | `pages/settings.js` | preferences, account, security, data | account for most | guest, signed in | Crawl, click pass | Passed | | | Delete data and delete account not pressed |
| P4 | Terms `#/terms`, Privacy `#/privacy` | `pages/legalpages.js` | drafts in force, linked from every footer | none | guest | Crawl, live | Passed | owner items O15 | | Legal review is the owner's |
| P5 | Dossier start `#/dossier` | `pages/dossierstart.js` | recent and well-known names | none | guest, signed in | Crawl | Passed | | | |
| P6 | Overview `#/SYM` | `pages/dossier.js`, `overview-research.js` | header, past year chart, four questions, score, cases, what's next | none | stock, fund, coin, share class, unknown | Crawl, visual, live | Failed | D03, D05, D06, D18, D20, D21, D22; open O02, O04, O05, O07 | Fixed and verified (D items) | |
| P7 | Chart `#/SYM/chart` | `pages/chart.js`, `ui/pricechart.js` | ranges, intervals, types, studies, drawings, full screen | none | | Suite chart 19/19 (drawings, bar sizes, touch, full screen), crawl | Passed | | Passed | Real iOS Safari not run this audit |
| P8 | Options `#/SYM/options` | `pages/options.js`, `options-panels.js` | research table, picker, builder, readings | delayed chain | NVDA, SPY | Suite options 34/36, crawl, live | Failed | D01, D11; open O06 | Fixed and verified | Suite ran on the live chain, not its fixture |
| P9 | Investing `#/SYM/investing` | `pages/investing.js`, `dcf.js` | long-term score, fair value, DCF editor | SEC filings | NVDA, SPY | Crawl, visual | Failed | D19 | Fixed and verified | |
| P10 | Earnings `#/SYM/earnings` | `pages/earnings.js` | record, reaction, expectations; brief written on press | none to read | NVDA | Crawl, visual | Failed | D13 (copy) | Fixed and verified | Writing a brief (paid) not pressed |
| P11 | Financials `#/SYM/financials` | `pages/financials.js` | statements, segments, ownership, Congress | SEC, Yahoo | NVDA, SPY | Crawl, visual, API | Failed | D04 | Fixed and verified | Suite financials 18/26: Earnings-tab checks stale (table moved under View data); 3 others not re-traced |
| P12 | News `#/SYM/news` | `pages/news.js` | relevant headlines, fetched time | none | NVDA | Crawl, visual | Passed | open O14 | | |
| P13 | Research sheet `#/SYM/sheet` | `pages/sheet.js` | printable two pages | none | NVDA | Crawl, live | Failed | D02, D20 | Fixed and verified | Live until deploy |
| P14 | Instrument `#/instrument/SYM` | `pages/instrument.js` | index, rate, future chart and tiles | none | ^GSPC, ^TNX, CL=F; futures in session and overnight | Crawl, visual, frozen-clock tests | Failed | D24; open O12 | Fixed and verified (D24) | Overnight state checked by adjusting the server's answer in the browser; the timing rule by tests |
| P15 | Compare `#/compare` | `pages/compare.js` | 2 to 4 names, horizons, table, Ask Milo with figures | none | empty, NVDA+MSFT | Suite compare 22/26, crawl, live | Passed | D14 (copy) | Fixed and verified | 4 compare checks not re-traced |
| P16 | Read `#/read` | `pages/read.js` | the kept edition; calendar; search; Build on press | none to read | | Crawl, live (kept edition only) | Passed | | | Build today's Read (paid) not pressed |
| P17 | Macro `#/macro` | `pages/macro.js` | regime, breadth, rotation, maps | none | | Crawl, click pass, live | Failed | D10, D13 | Fixed and verified | |
| P18 | Indices `#/indices` | `pages/indices.js` | index funds, regime | none | | Crawl, live | Failed | D13 ("A Index Read") | Fixed and verified | |
| P19 | Earnings week `#/earnings` | `pages/earningsweek.js` | last, this, next week | none | | Crawl | Failed | D13 (heading) | Fixed and verified | open O09 |
| P20 | Explore `#/explore` | `pages/explore.js` | sectors, themes, lists | none | | Crawl, live | Passed | | | |
| P21 | Scan `#/scan` | `pages/scan.js` | choose a scan, rows open chart, watch, compare; Find stocks in plain words | none | | Suite scan 16/18 (stale selector), crawl, click pass (39 controls), live | Failed | D23 | Fixed and verified | Plain-words requests that need Milo not run (paid) |
| P22 | Insiders `#/insiders` | `pages/insiders.js` | House trades, Form 4s, federal contracts | SEC, House Clerk, USAspending | | Suite ownership 13/14, crawl, live | Passed | D12; open O10 | Fixed and verified (D12) | 1 ownership check not re-traced |
| P23 | Analysts `#/analysts` | `pages/analysts.js` | rating changes feed | feed | | Crawl, live | Passed | D12 | Fixed and verified | |
| P24 | Optic Portfolio `#/portfolio` | `pages/tracker.js` | three simulated books, hypothetical notice | none | | Crawl, suite positions (stale), live | Passed | | | |
| P25 | Paper Desk `#/paper` | `pages/paper.js` | test trades, totals reconcile | none | test book | Suite positions | Passed | | | |
| P26 | Retirement `#/retirement` | `pages/retirement.js` | model allocation and projection | none | | Crawl | Passed | open O08 | | Live blocked by the audit's own POST rule |
| P27 | Brokerage `#/brokerage` and 5 sections | `pages/brokerage.js`, `app/brokerage/` | link, holdings, exposure, performance, events, connections, sync, disconnect | account, provider | sandbox: standard, edge, partial, expired, outage; cancel | Journey (sandbox) | Failed | D17 | Fixed and verified | Real SnapTrade not tested; owner's live accounts not opened; "unsupported" not linked (the audit hit Optic's connect limit, 429) |
| P28 | Watchlist `#/watchlist` | `pages/watchlist.js` | lists, add, remove, reorder, undo, persist | none (account keeps) | guest, signed in | Suite watchlists 27/28, journey | Passed | | Passed | Guest storage-refused message not confirmed (check timed out) |
| P29 | Alerts `#/alerts` | `pages/alerts.js` | create, edit, pause, delete with undo, why it fired | none | guest, signed in | Suite alerts 23/26 | Passed with issue | open O11 (phone focus after edit) | | No notification delivered |
| P30 | Saved research `#/research` | `pages/saved.js` | saved Milo answers | account | | Crawl | Passed | | | Saving not exercised |
| P31 | Problem Reports `#/reports` | `pages/reports.js` | owner list | owner | owner (local), guest | Crawl | Passed | | | Not opened live |
| P32 | Claude usage `#/usage` | `pages/reports.js` | owner ledger | owner | | Crawl | Passed | | | Not opened live |
| P33 | Accounts `#/accounts` | `pages/reports.js` | owner list | owner | | Crawl | Passed | | | Not opened live |
| P34 | Metrics `#/metrics` | `pages/reports.js` | owner metrics | owner | | Crawl | Passed | | | Not opened live |
| P35 | Not found | `pages/bridge.js` | see S18 | | | | Failed | D09 | Fixed and verified | |
| P36 | Instruments from Markets | see P14 | | | | | | | | |

## Milo

| # | Feature | Method | Initial | Issue, fix | Retest | Limits |
|---|---|---|---|---|---|---|
| M1 | Open, focus, Escape, focus back to opener | Journey (Milo) desktop and phone | Passed | | | |
| M2 | Suggested prompts | Journey | Passed | | | |
| M3 | Send, stream, finish, progress line ends | Journey | Passed | | | Stand-in model |
| M4 | Stop mid-answer, marked incomplete | Journey (slow answer) | Passed | | | |
| M5 | Double press of Send sends once | Journey | Passed | | | |
| M6 | Follow-up in the same thread | Journey | Passed | | | |
| M7 | Copy | Journey | Passed | | | |
| M8 | New conversation | Journey | Passed | | | |
| M9 | 12,000-character question | Journey | Passed | | | |
| M10 | Moving page mid-answer (docked on desktop, sheet on phone) | Journey | Passed | | | |
| M11 | 429 and 503 end loading and give the question back | Journey (simulated responses) | Passed | | | |
| M12 | Context sent: instrument, page, timeframe, persona, symbol switch | Suite milo 19/19 | Passed | | | Stand-in |
| M13 | Compare figures attached | Suite milo-eval 4/5 (stale path) | Passed | | | |
| M14 | Share-class symbols in tools | Unit | Failed | D03 | Fixed and verified | |
| M15 | Portfolio tool offered only where it belongs | Code, earlier live finding | Failed | O03 (fix on `milo-portfolio-privacy`, owner holds it) | | |
| M16 | Answer quality, citations, figures against retrieved data, refusals | | Blocked | needs paid calls on production; no permission asked in this audit | | |
| M17 | History, rename, delete; attachments; persona menu | | Not tested | | | |

## Integrations

| # | Integration | How it was exercised | Result |
|---|---|---|---|
| I1 | Yahoo Finance (quotes, history, chains, statements, news) | Real, local and live, read-only | Verified with real integration; D01 found in it |
| I2 | SEC EDGAR (filings, Form 4, segments) | Real, local | Verified with real integration |
| I3 | House Clerk, USAspending, FRED, Treasury | Real, local | Rendered; not separately validated |
| I4 | Sandbox brokerage | Provider sandbox, six scenarios | Verified in provider sandbox |
| I5 | SnapTrade (real brokerages) | Not exercised | Blocked: real accounts are the owner's; no test credentials |
| I6 | Anthropic (Milo, written reads) | Local stand-in; nothing sent live | Verified using a mocked dependency; real answers Blocked |
| I7 | Email (verify, reset) | Local relay that keeps messages | Verified using a mocked dependency; production mail is in log mode (owner) |
| I8 | Stripe billing | Not exercised | Not implemented on production ("not on sale") |
| I9 | Google, Apple sign-in | Provider status | Not implemented (not configured) |
| I10 | Passkeys | Not exercised | Not tested (needs an authenticator) |

## Investor journeys

| Journey | Result | Evidence | Limits |
|---|---|---|---|
| A. New visitor to account to a first result | Passed | first-use journey 14/14 | Mail through a local relay |
| B. Search, Dossier, chart, research, Milo | Passed | suite search, chart 19/19; crawl; Milo journey 20/20 | Stand-in model |
| C. Portfolio, holdings, position, Milo | Partly | sandbox journey (holdings, exposure, cash, missing cost basis, CAD, partial, expired, outage) | Milo portfolio answer not run; real brokerage not tested |
| D. Watchlist persistence | Passed | suite watchlists 27/28; first-use (followed company kept after reload) | |
| E. Every desk, controls, recovery | Passed with issues | crawl (all routes), suite release-extra 13/13 (failure and recovery), click pass | see DEFECTS.md |
| F. Compact screen | Passed with issues | crawl at 390 (all routes), phone sweep 108/160 rows clean, Milo at 390 | O10 |
| G. Free exploration | Passed with issues | crawl of secondary views, click pass, visual review | Classic not covered (C1) |

## Classic

| # | Feature | Result |
|---|---|---|
| C1 | Classic app at `/classic` (27 views), linked from v2's footer | Error-level crawl only, as a guest at 1440: all 26 view addresses tried render their view with no script errors, broken values or sideways overflow; Chart and Options were still loading at 9 s. Not visually reviewed, not signed in, no controls pressed. It shares the server, so the server fixes here (D01, D04, server copy in D13, D19, D20's source) apply to it. |

## Server routes (235), grouped

The pages above call these; each group is covered by the pages that use it, not by direct calls:
quotes, history, chains, options research and picker, ticker build; fundamentals, segments, valuation, framework;
news, catalysts, briefs, desk, weekly; macro, market, sectors, indices, rotation, stock maps, econ, earnings
week, priority; scanners, screener, setups, patterns, signals, tracker, paper, retirement; insiders, Congress,
contracts, analysts; watchlists, watches, alerts, saved research, theses, valuations, preferences; auth
(login, register, verify, reset, passkeys, providers, sessions, identities); brokerage (status, connect, callback,
sandbox, sync, disconnect, portfolio, workspace sections); billing; admin and owner; health, build, logo, legal.
Write and paid routes were exercised only locally.
