# Capability matrix: v2 against the classic app

Stage 0, 2026-10-18. Every capability of the classic app falls into exactly one of three classes. "27 of 27 pages rebuilt" counts pages; this counts capabilities.

- **Implemented and tested:** v2 has it, and it was exercised in a browser against the real local server: the journey checks in VALIDATION.md, the Stage 0 checks in STAGE0-EVIDENCE.md, and the v2_check audit at 0 faults.
- **Incomplete:** v2 has an entry point and part of the capability. The gap is named.
- **Classic-only:** no v2 entry point beyond a link to the classic page. Each one has a milestone in MIGRATION.md; none is dropped.

Row-level detail per page is in COVERAGE.md.

## Shell, account and global

| Capability | Class | Evidence or gap |
|---|---|---|
| Rail, groups, page tabs, phone bar (names unchanged) | Implemented and tested | v2_check, 40 views × 2 sizes |
| Rail Collapse (`optic.rail.tight.v2`, shared with Classic) | Implemented and tested | Stage 0 |
| Command palette: exact page names, symbols with actions, saved research, screens, Ask Milo row, quick actions | Implemented and tested | Stage 0 (palette) |
| Home as the research workspace: layouts (Market Overview the default, My Desk the reader's own), panels, move, resize, hide, lock, reset, save, linked ticker, phone priority, state kept on Back (new) | Implemented and tested (private preview) | WORKSPACE.md; `ws_verify_home.py` 52 checks and `walkthrough.py` 18 checks, cold and cached; v2_check audit 0 faults on its 20 captures (5 Home views, desktop and phone, dark and light) |
| Dark visual system, a sidebar of destinations only, one page system across every page (new direction; dark accepted 2026-10-18) | Implemented and tested (private preview) | VISUAL-SPEC-DARK.md; `style_audit.py` on 8 pages × 2 sizes; v2_check audit 0 faults on 168 captures (42 views, desktop and phone, dark and light), 2026-10-18 |
| Notifications bell with unseen count | Incomplete | Backend counts exist; v2 has no bell (I11, W2) |
| Glossary tooltips and Learn widget | Incomplete | C17. The Learn widget is on the Chart page since 2026-10-19, with the classic glossary word for word (`core/glossary.js`, compared with `static/app.js` by `tests/test_v2_chart_widgets.py`). The dotted-underline tooltips are M7 |
| Sign in, create account, forgot and reset password, verify email | Implemented and tested | Stage 0 (auth), real local flows |
| Google and Apple sign-in (start, callback, error) | Implemented and tested, locally | The callback returns to v2. Providers are not configured locally, so the real Google and Apple round trip is an owner check in the preview (LAUNCH-REQUIREMENTS L7) |
| Passkeys: sign in, add, rename, remove | Implemented and tested | Stage 0, through Chrome's virtual authenticator |
| Recovery: reset link, sign out everywhere, guest data on sign-in | Implemented and tested | Stage 0, plus the earlier journey |
| Billing and brokerage return links, alert e-mail links | Implemented and tested | Stage 0 (landing checks) |
| Footer health, session chip, offline bar, new-version bar | Implemented and tested | Stage 0 (app shell) |
| Legal footer, full disclaimer, page notices, Milo notice | Implemented and tested | Stage 0 (legal), 9 page types |
| Use the classic app / Try the new design | Implemented and tested | Stage 0 (switch) |
| Theme, text size, time zone, knowledge level (shared keys) | Implemented and tested | Round trip in STAGE0-EVIDENCE.md §7 |

## Milo

| Capability | Class | Evidence or gap |
|---|---|---|
| Conversations and saved history (`optic.pulse.history.v1`, shared with Classic) | Implemented and tested | Stage 0 and the round trip |
| Rendered answers: sources, charts in answers, follow-ups, action cards | Implemented and tested | Stage 0, through a stubbed stream |
| Ask Milo from a Home panel through to the answer, with Optic's own tools | Implemented and tested with a stand-in model | `milo_e2e.py`, 7 of 7 (2026-10-18): the route, the allowance, CONTEXT naming the panel and ticker, a real `get_quote` round trip, the streamed answer and its sources. **Not tested: a real model's answers.** That needs the key and is a private-preview check (PREVIEW-PACKAGE.md section 7) |
| Page and ticker context; no leak from the previous page | Implemented and tested | Stage 0 (AAPL to MSFT Options) |
| Scope (this page, market only, none), Level, Analyst, Timeframe | Implemented and tested | Stage 0 |
| Allowance, switched off, sign-in required, spent | Implemented and tested | Stage 0 |
| Stop, cut-off and interrupted answers, offline, server down | Implemented and tested | Stage 0 |
| Phone keyboard (visual viewport) | Implemented, partly tested | Tested in Chrome's phone emulation. A real iOS Safari keyboard check is an owner check in the preview |
| Attachments (`#chat-attach`) | Classic-only | M5 |
| Web search toggle (`#chat-web`) | Classic-only | M5 |
| Research mode and research pack (`#chat-research`) | Classic-only | M5 |
| Suggested questions (`#chat-suggest`), resizable panel width | Classic-only | M5 |
| Scout (the mascot) | Classic-only | M5 |
| Per-panel "Ask Milo" chips with the panel's figures | Incomplete | Each block's Ask Milo sends where it was asked from (`focus.asked_from`, and the block's symbol on a page without one; Stage 0). The panel's own figures in the context: M5 |

## Home

| Capability | Class | Evidence or gap |
|---|---|---|
| Market strip, greeting, new and returning states, watchlist feed, scan alerts, movers, expected move, portfolio | Implemented and tested | v2_check; since 2026-10-18 these are Home's panels (Indices, Watchlist, Latest scan alerts, Moved most this month, Expected move, Your portfolio), checked by `ws_verify_home.py` |
| What matters today | Incomplete | Released results (home-released-results branch) not yet shown |
| Optic Desk | Incomplete | Scenarios and today's reports: M7 |
| What matters now (ranked moves) | Implemented and tested | On Explore, Cross-asset; linked from Home |
| Catalyst day strip, What changed since yesterday, index and sector trends board | Classic-only | M7, as secondary views |

## Dossier

| Capability | Class | Evidence or gap |
|---|---|---|
| Overview: header, digest, four questions, long-term score, year chart, implied range, fair value, key figures | Implemented and tested | v2_check |
| Advanced research | Incomplete | Headlines, filings and the bull and bear case are in; the Pulse score, all statistics and the rest of the ticker are M3 |
| Optic Score (short term), Weinstein stage chip, Factors and What to look at next, Fund view | Classic-only | M3 (score, factors, fund view), M7 (stage chip) |
| Thesis check | Classic-only | M3 |
| Options: builder, payoff, greeks, research contracts, pricing, dealer gamma, flow, strategies, swing verdict, Greeks lab, patterns | Implemented and tested | v2_check, plus the builder check |
| Swing setups | Incomplete | Lists armed, triggered and watched; filters, rule settings, back-tests and setup alerts are M3 |
| Track record slots | Classic-only | M4 |
| Chart: bar sizes, styles, MA, EMA, Bollinger, Fib, S/R, GEX levels, earnings marks, panes, zoom, pan, crosshair, 7 drawing tools | Implemented and tested | v2_check, plus drawings shared with Classic (round trip §7) |
| Chart: Market structure breaks (new study) | Implemented and tested | `marketStructure` unit test; prefix-stability test (a later bar never changes a recorded break); browser check (strength 3, 5, 10; formed vs known drawn apart; Milo context) |
| Chart: free deterministic chart read | Implemented and tested | C18, carried over 2026-10-19 (`ui/chartread.js`, the classic `chartReadModel` and its words): the Chart read button beside the plot; daily trend and its facts, nearest support and resistance, RSI and MACD, from the ticker payload already loaded, no model call. Browser check at 1440 and 390; `tests/test_v2_p3.py` |
| Chart: channel, Fib extension, pitchfork, arrow, ruler, risk box, position sizing, snap, moving a drawing | Classic-only | M1 |
| Chart: insider trades on the price | Implemented and tested | C11's insider marks, 2026-10-19: a green arrow under the bar for a purchase, a red one over it for a sale (option exercises, grants and gifts left out, as in Classic), one arrow per side per bar; pointing at or tapping one, or reaching its bar with the keyboard, opens a box naming each trade (who, role, shares, value, the filing's own words) and the screen-reader line reads it. From the ticker payload's filings of the last two years (at most 200; it kept the 12 latest until 2026-10-19, about a month): 81 for AAPL, Nov 2024 to Oct 2026, which the Insiders panel states. The longer list is shared with Classic: its chart's insider marks go back as far, and its Financials table lists every row in its scroll box; the watches still read the 12 latest (`tests/test_insider_history.py`). The Insider trades overlay, on by default, in Indicators and the Insiders panel. `tests/test_v2_chart_widgets.py`; browser check on AAPL (sales) and FUL (purchases) at 1440 and 390 |
| Chart studies: EMA clouds, MA Trend, TSO, VWAP, Keltner, Donchian, regression, stages, accumulation, auto trends, VBP, zones, sessions | Implemented and tested | C11, 2026-10-19, under the classic names in Indicators (grouped: averages and bands, levels, structure and events, candle colours; TSO a pane). What v2 works out from the bars (EMA clouds, MA Trend, TSO, volume by price, session dividers, the stage of each bar) is the classic code ported line for line and run against it on the same bars (`tests/test_v2_studies.py`); Keltner, Donchian, the regression channel and VWAP come from /api/indicators on the chart's own bars, the stages from /api/stage, trend lines from /api/trendlines, accumulation zones from /api/longterm and supply and demand from the ticker payload, each fetched only while on. A line under the chart gives each one's reading or why it draws nothing (trend lines on daily and weekly bars, dividers on intraday). The price pane is clipped, so nothing runs into the panes under it. Browser check on AAPL daily and hourly at 1440 with every study on; the sweep at five sizes on AAPL and SPY |
| Chart: the 18 side widgets (Watch, Alerts, News, Analysts, Season, Notes, Insiders, Reports, Checklist, Stop check, Options, Key levels, Stats, Patterns, Pairs, Backtest, Trading, Learn) | Implemented and tested | C12, carried over 2026-10-19 (`pages/chart-widgets.js`): a rail beside the plot with the classic names, order and marks; any number open on a wide screen, one at a time on a phone; nothing open to start, the open ones remembered. Nine read the ticker payload the page already loads (Analysts and Stop check also ask a free endpoint once open); Alerts, Season, Pairs, Backtest and Trading ask their own free endpoints once open; Watch uses the watchlists; Notes, Checklist and Learn ask the server nothing. The backtest's trades and the stop check's lines are drawn on the price. Inputs kept in the classic keys. `tests/test_v2_chart_widgets.py` (each widget drawn from a real AAPL payload, trade placement by day, minute and week); browser check at 1440, 1024 and 390 against the local server (keyboard along the rail, focus kept through a redraw, no sideways scroll), and the sweep with all 18 open on AAPL and SPY at 1440, 1280, 768, 390 and 375 × 549: no console errors, raw text, small text, em dashes or overflow, and the launch audit at 0 faults |
| Chart indicator panes: ADX and DI, Stochastic, OBV, MFI, relative strength line | Classic-only | C19, M1 (found 2026-10-19: the classic chart's own panes from /api/indicators, missing from this matrix until now) |
| Chart: colours, legend, full screen, navigator | Implemented and tested | C12's chrome, carried over 2026-10-19 (`pages/chart-chrome.js`, drawn by `ui/pricechart.js`): Colours in the toolbar (candle up, candle down and the line, with presets, any colour from the wheel, a note under 3:1 against the chart background, Default and Reset), kept in the classic key `optic.chart.colors.v1`; the legend on the plot's corner, folded to its count unless opened (`optic.chart.legend.v1`, shared), a row per overlay with its value at the crosshair and a cross that takes it off; full screen (the page takes the window, the browser's own full screen on top where it is allowed; Escape, the button or leaving the page goes back); the navigator under the plot (drag the window, drag an edge, press outside to jump; a slider for the keyboard). `tests/test_v2_chart_chrome.py`; browser check at 1440, 1024 and 390 against the local server, signed in, with real pointer, touch and key events (112 of 112, no sideways scroll after any step); the widget sweep on AAPL at 1440, 1280, 768, 390 and 375 × 549, and again on AAPL and SPY with the legend open and a chosen colour, and in full screen: no faults |
| Investing: long-term view, return and risk, drawdown, valuation history, fair value, scenarios (saved, shared with Classic) | Implemented and tested | v2_check, plus the round trip |
| Weekly structure | Incomplete | Candle style, levels menu and pan: M1 |
| DCF editor, saved models, RI, FFO, DDM, comps, SOTP, valuation Milo | Classic-only | v2 shows the summary. Editing: M2 |
| Earnings (per company) | Implemented and tested | The pre-earnings brief loads on request, because it is a paid call |
| Earnings this week (no symbol) | Classic-only | M3 |
| Financials | Incomplete | The flow ratio chart: M7 |
| News | Implemented and tested | |

## Markets, Discover, Compare

| Capability | Class | Evidence or gap |
|---|---|---|
| Read, Macro (regime, maps, sectors, rotation), Indices, Instrument | Implemented and tested | Model-written reads are cached or on request, never on load (paid-call probe) |
| Explore, Insiders, Analysts, Compare | Implemented and tested | v2_check |
| Scan: named scans, builder, ask | Incomplete | In-cell bars: M7 |

## Positions, Brokerage, Watchlist, Alerts, Settings, Reports

| Capability | Class | Evidence or gap |
|---|---|---|
| Optic Portfolio | Incomplete | Header tooltips and collapsible panels: M7 |
| Paper Desk, Retirement (browser keys shared with Classic) | Implemented and tested | Round trip §7 |
| Brokerage, six sections, owner flash, events | Implemented and tested | v2_check, sandbox provider. Real accounts: owner preview |
| Watchlists: named lists, reorder, follow, drawer | Implemented and tested | Round trip §7 |
| Alerts: price alerts, scheduled scan list | Incomplete | Kind filters, unread only and "Why this fired": M6 |
| Signal history | Classic-only | M4 |
| Alerts owner controls (mark read, clear all, e-mail delivery) | Classic-only | M6 |
| Settings, all of Security | Implemented and tested | v2_check, Stage 0 passkeys |
| Reports, Claude usage, Accounts (owner) | Implemented and tested | v2_check |

## Count

Lines in this matrix:

| Class | Lines |
|---|---|
| Implemented and tested (including partly tested) | 42 |
| Incomplete | 12 |
| Classic-only | 15 |

Many lines are groups. Counted one by one, the Classic-only capabilities are:
- 7 chart drawing tools, plus snap and moving a drawing;
- 5 chart indicator panes (found 2026-10-19);
- 8 valuation editors and methods;
- 6 Milo features;
- 11 others (research tools, Home extras, alerts). The free chart read (C18) moved across on 2026-10-19, and so did the 18 chart widgets with the Learn widget (part of C17) and the chart's colours, legend, full screen and navigator (all of C12), and the 14 chart studies (C11).

All of them are scheduled in MIGRATION.md.
