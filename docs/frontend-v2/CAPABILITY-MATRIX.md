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
| Research workspace: presets, panels, move, resize, hide, lock, reset, linked ticker, open at Home (new) | Implemented and tested (preview) | WORKSPACE.md; 45 checks; audit 0 faults |
| Dark visual system and expandable sidebar (new direction) | Implemented and tested (preview) | VISUAL-SPEC-DARK.md; audit 0 faults on 64 captures |
| Notifications bell with unseen count | Incomplete | Backend counts exist; v2 has no bell (I11, W2) |
| Glossary tooltips and Learn widget | Classic-only | C17, M7 (found by the 2026-10-18 audit) |
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
| Market strip, greeting, new and returning states, watchlist feed, scan alerts, movers, expected move, portfolio | Implemented and tested | v2_check |
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
| Chart: Market structure breaks (new study) | Implemented and tested | `marketStructure` unit test; browser check (strength 3, 5, 10; Milo context) |
| Chart: free deterministic chart read | Classic-only | C18, M1 |
| Chart: channel, Fib extension, pitchfork, arrow, ruler, risk box, position sizing, snap, moving a drawing | Classic-only | M1 |
| Chart studies: EMA clouds, MA Trend, TSO, VWAP, Keltner, Donchian, regression, stages, accumulation, auto trends, VBP, zones, sessions, insider marks | Classic-only | M1 |
| Chart widgets (18), colours, legend, full screen, navigator | Classic-only | M1 |
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
| Implemented and tested (including partly tested) | 37 |
| Incomplete | 11 |
| Classic-only | 18 |

Many lines are groups. Counted one by one, the Classic-only capabilities are:
- 7 chart drawing tools, plus snap and moving a drawing;
- 14 chart studies;
- 18 chart widgets;
- 8 valuation editors and methods;
- 6 Milo features;
- 12 others (research tools, Home extras, alerts).

All of them are scheduled in MIGRATION.md.
