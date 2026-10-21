# Classic to v2 parity ledger

The owner's request (2026-10-21) was "add all of these into v2. take all other UI features as well, from dragging and scrolling in certain areas and etc".

- **The approved plan:** `~/.claude/plans/pasted-content-id-f1e2-the-redesigns-jiggly-glade.md`.
- **The two audits behind it:** `~/Optic/work/classic-parity/AUDIT.md`, saved verbatim at origin/main f939ddc.

A row is **done** only when a browser check exercised the interaction. A matching endpoint, a visible button or a passing pure-logic test is not enough. Evidence names the check script in `~/Optic/work/classic-parity/` and says whether touch was emulated (headless Chrome) or real (Mobile Safari on the iOS simulator). Physical devices are untested unless the owner tests them.

**Status values:**
- `done`: migrated and verified.
- `differs`: migrated, with a documented difference.
- `blocked`: a data source or dependency is missing.
- `not ported`: intentional, with the reason given.
- `untested`.
- `open`: not started.

**Columns:**
- Task: what the reader can do.
- Where: the v2 location.
- Desktop: the desktop interaction.
- Phone: the phone interaction.
- Keeps: what persists, as storage key and format.
- States: loading, empty and error.
- Deps: data and model dependencies; $ marks a paid call.
- Evidence: what proved it works.

## B1. Shell, quick fixes and claim audit
Shipped 2026-10-21 as db6702c. The rollback point is f939ddc. Live v2 build e661fedfbe4b matches the candidate. The live read-only check (`b1_live.py`, as a guest) passed 6 of 6, and the owner's signed-in bell was checked in the browser pane (0 unread, hidden).
Evidence: `b1_check.py`, 78 of 78 at 1440, 1024, 430, 390 and 360 in headless Chrome, with touch emulated; `tests/test_v2_parity_b1.py`. Not tested on a physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B1.1 | `#/earnings` opens the week's earnings by day, not a ticker called EARNINGS | `pages/earningsweek.js`; Markets highlighted; Home's earnings panel links to it | Last, This and Next week buttons; a report opens `#/SYM/earnings` | One column of rows | The week is kept in the address (`?week=`) | Skeleton; the API's reason; a retry on failure | `/api/earnings-week` (free) | b1 B1.1 at all 5 sizes, no overflow | done |
| B1.2 | Saved research opens the page that holds it | Account sheet | Link to Classic `#/scan` until B4d builds v2's hub | Same | none | none | none | b1 B1.2 | done (B4d replaces it) |
| B1.3 | Milo's stage, MA-trend and TSO actions open v2's chart | `core/milo-text.js` STUDIES; Chart `show=` | The study switched on; stages and MA trend switch the chart to candles | Same | none | none | none | b1 B1.3 (the control is pressed and candles chosen) | done |
| B1.4 | A section returns to the page last used in it | `ui/shell.js` NAV_LAST (memory, this visit, as in Classic) | Rail rows | Phone bar and More | In memory only (Classic kept no key) | n/a | none | b1 B1.4: Markets returns to Macro; Dossier returns to AAPL Financials | done |
| B1.5 | More says what each page is for; a guest can sign in from it | More sheet | n/a | Rows of 44 px or more, grouped by section | none | none | none | b1 B1.5, guest and signed in | done |
| B1.6 | Unread alerts are visible without opening Alerts | Top-bar bell; the phone bar's Watchlist tab | The bell shows only when something is unread and opens Alerts; its name says the count | A count on Watchlist, where Alerts lives, named "Watchlist. N unread alerts" | none | Hidden at 0; guests have none (their watches stay in the browser) | `/api/watches/hits?limit=1`, every 2 min in the trading day, 10 min outside it, again after "Mark all as seen" | b1 B1.6 (3 unread, then 0) | differs: the count is on Watchlist, not More, because v2's Alerts lives under Watchlist |
| B1.7 | Pages refresh without disturbing the reader | `core/poll.js`; `livePrice` on every Dossier tab; Home's market panels; Options; Macro | The header price updates in place; open sections, scroll and menus are kept; nothing repaints when nothing changed | Same | none | A failed refresh keeps what is on screen | `/api/quote`, `/api/session` | b1 B1.7 (a fake 12:30 ET clock; served quote) at 1440 and 390; jsc: no overlap, paused while hidden, one catch-up on return | differs: prices every 20 s as in Classic; Options readings and the Macro boards every 60 s (a full option read; boards change slowly); catch-up on return covered by jsc only |
| B1.8 | The Dossier header stays in view | `.dstick` on Overview, Options, Investing, Earnings, Financials and News | Ticker, price and tabs under the top bar; jumps land below them (scroll padding from measured heights) | Scrolls away under 641 px wide or 561 px tall, to keep the screen for the work | none | n/a | none | b1 B1.8 at 1440 and 1024 (sticky, jump lands below), phones static | differs: not sticky on phones or the Chart tab, whose plot fills the window |
| B1.9 | Earnings timing and "confirmed" only where the source supports them | `core/reports.js` on Overview, Earnings, Home and Brokerage; server `_next_report`, `earnings_calendar`, `_ws_earnings_calendar` | "date confirmed by Yahoo Finance" (Yahoo's `isEarningsDateEstimate`), "date listed by Yahoo Finance" (only one date, no flag), or "date not confirmed"; the habit "Its last 4 reports came after the close." from reported quarters; no session for a report not yet made | Same | none | No date: "No date yet" | Yahoo quote flag; earnings history | b1 B1.9 (NVDA); a live probe on 2026-10-21 found Yahoo's upcoming-row time wrong for AAPL and NVDA ("before the open"; both report after the close); past rows correct (AAPL, NVDA, HOOD after; JPM, WMT before) | done; the implied move now always uses the expiry after the report date |

## B2a. Shared chart (`ui/chart.js`)
Shipped 2026-10-21 as b38ae02. The rollback point is db6702c. Live v2 build aa32fc5eb19e matches the candidate. The live read-only check (`b2a_live.py`, as a guest) passed 4 of 4.
The precedence was written first, in `docs/frontend-v2/CHART-GESTURES.md`, and the checks assert it. It covers about 20 charts: Overview's year chart, RSI and MACD, drawdown and P/E, short volume, Macro, Indices, Compare, Brokerage, Retirement, Home's panels and Milo's price chart.
Evidence:
- `b2a_check.py`: 46 of 46 at 1440, 430, 390 and 360 in headless Chrome, with touch emulated.
- Mobile Safari on the iPhone 17 simulator (iOS 27), real WebKit touch:
  - a vertical swipe on the chart scrolls the page and leaves no reading;
  - a tap reads;
  - hold then slide reads without selecting text;
  - the Measure button then a drag measures ("+74.04 (+28.58%) Jan 8, 2026 to Sep 14, 2026");
  - two fingers measure ("+39.16 (+14.41%) Dec 17, 2025 to Aug 5, 2026");
  - the pressed button covers no price label.
- `tests/test_v2_parity_b2a.py`.
Not tested on a physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B2a.1 | Measure between two dates on any shared chart | `ui/chart.js` `measured()`, the Measure button, `[data-ms-say]` | Shift-drag, or the Measure button then a drag; M then the arrows from the keys; Escape clears; a plain drag and the wheel do what they did | The Measure button (always shown on touch screens), then a drag; hold then slide outside iOS Safari | Nothing: a measurement is a reading, not saved (Classic kept none) | A one-bar measurement says "Drag to the other date"; the result is announced once it ends | none | b2a desk: plain drag, Shift-drag, button on and off, wheel, keys, Tab, no click ring; phones: hold, quick slide, the button's place; RSI reads in points; iOS: the button and a drag | differs: in iOS and iPadOS Safari a long press is the system's text selection, so hold-to-measure is off there and the Measure button or two fingers measure |
| B2a.2 | Two fingers measure on touch | Same | n/a | Two fingers on the chart measure between them; pinch-zoom is off over a chart only | none | Lifting announces it | none | b2a phones at 360, 390 and 430; iOS Safari two fingers | done |
| B2a.3 | The readout sits above the finger and on the screen | `place()` in `ui/chart.js` | The tip centres on the point and stays inside the chart | Above the finger; one wider than the chart stacks its dates on a second line | none | n/a | none | b2a phones: tip above the finger, measurement inside the chart and the screen at 360; screenshots in `out-b2a/` | done |
| B2a.4 | An insider marker opens Insiders | Moved to B2b: insider markers live on the price charts (`ui/pricechart.js`) | | | | | | | moved to B2b.11 |
| B2a.5 | A freshness label from the feed's own times | Moved to B2b: it belongs with the Chart tab's live ticks | | | | | | | moved to B2b.7 |

## B2b. Chart tab (`ui/pricechart.js`) and other price charts
| Row | Task | Status |
|---|---|---|
| B2b.1 | Wheel, trackpad and pinch as in Classic (200 ms gesture lock; page scroll kept) | open |
| B2b.2 | Safari trackpad pinch | open |
| B2b.3 | Touch: direction lock, hold to read, two-finger pan and pinch about the midpoint | open |
| B2b.4 | Measure by Shift-drag, by hold, or with the Measure button | open |
| B2b.5 | Stretch the price scale; double-click or Fit to reset | open |
| B2b.6 | − and + on touch screens | open |
| B2b.7 | Live ticks every 15 s, the price in the tab title, never moving the view; a freshness label from the feed's own times (was B2a.5) | open |
| B2b.8 | Draw a two-point shape in one drag; Escape cancels a drag | open |
| B2b.9 | Undo, redo and Delete page-wide, never in fields | open |
| B2b.10 | Indicator search; × on each pane; a grabbing cursor | open |
| B2b.11 | A price chart on Options (pan, zoom, measure, insider markers); an insider marker opens Insiders (was B2a.4) | open |
| B2b.12 | Measure on Investing's weekly chart | open |
| B2b.13 | Hover and focus on the sector rotation chart | open |

## B3. Long-page navigation
| Row | Task | Status |
|---|---|---|
| B3.1 | A sticky "Jump to a section" strip on long pages | open |
| B3.2 | The strip scrolls sideways by wheel and drag, with edge fades | open |
| B3.3 | It highlights the section on screen; a jump opens a folded section | open |
| B3.4 | Fold sections, remembered (`optic.panels.open`); Expand all and Collapse all | open |
| B3.5 | A Panels chooser per tab | open |
| B3.6 | The knowledge level folds the specialist panels | open |
| B3.7 | Edge fades on sideways strips (Home, phone) | open |
| B3.8 | Insider tables capped in height, with sticky headers | open |

## B4. Milo
| Row | Task | Status |
|---|---|---|
| B4a.1 | Docked panel, only when the research column keeps its usable width | open |
| B4a.2 | The panel stays open across pages; no focus trap while docked | open |
| B4a.3 | Ask Milo from a panel sends that panel's own figures | open |
| B4a.4 | Suggestions as quiet buttons; a "Use this example" button | open |
| B4b.1 | Attach files (button, drop); type, size and count checked in the browser and on the server | open |
| B4c.1 | Web search toggle ($, on send) | open |
| B4c.2 | Deep research and the modes row ($, on send) | open |
| B4d.1 | Save a question; Saved research hub | open |

## B5. Alerts and signals
| Row | Task | Status |
|---|---|---|
| B5.1 | Inbox: kind filters, unread only, urgency groups | open |
| B5.2 | "Why this fired"; mark read; Clear all; the e-mail delivery note | open |
| B5.3 | Setup alerts | open |
| B5.4 | Signal history and follow-up | open |

## B6. Research tools
| Row | Task | Status |
|---|---|---|
| B6a.1 | Thesis check (`optic.thesis.v1`) | open |
| B6a.2 | Pulse score | open |
| B6a.3 | All statistics and the method note | open |
| B6a.4 | Short-term Optic Score | open |
| B6a.5 | Factors and "What to look at next" | open |
| B6a.6 | Fund takeaways and the risk card | open |
| B6a.7 | Stage label in the header | open |
| B6b.1 | Swing setups: scope, filters, rules form (`optic.setups.*`) | open |
| B6b.2 | Setup detail, back-test table, contract finder | open |
| B6b.3 | Chart patterns with measured base rates | open |
| B6c.1 | `validation` branch reviewed; only the compatible work it needs taken | open |
| B6c.2 | Track-record slots on Options and Investing | open |

## B7. Valuation
| Row | Task | Status |
|---|---|---|
| B7a.1 | DCF editor: inputs and per-year overrides, recomputed as you type (`optic.dcf.v1`) | open |
| B7a.2 | Sensitivity, forecast, bridge, statements and formulas | open |
| B7b.1 | Saved models: list, save, compare, replay, use | open |
| B7c.1 | RI, FFO, DDM, FCFE | open |
| B7c.2 | Comps and SOTP | open |
| B7d.1 | Valuation Milo card: Preview, Apply, Undo | open |

## B8. Home, Desk and Markets extras
| Row | Task | Status |
|---|---|---|
| B8.1 | Desk: bottom line, scenarios, calendar, limits | open |
| B8.2 | Catalyst day strip | open |
| B8.3 | What changed since yesterday | open |
| B8.4 | Index and sector trends board on Home | open |
| B8.5 | Questions worth asking | open |
| B8.6 | `home-released-results` reviewed; released results in What Matters Today | open |
| B8.7 | Today's Read built on request ($, labelled) | open |
| B8.8 | Earnings this week page (dates; timing only when sourced) | open |
| B8.9 | Markets opens on its last page | open |
| B8.10 | Ticker suggestions on Analysts and Compare | open |

## B9. Glossary and the rest
| Row | Task | Status |
|---|---|---|
| B9.1 | Glossary marking on eligible text, with hover, tap and keys; "Explain this with Milo" | open |
| B9.2 | Optic Portfolio header definitions; collapsible panels | open |
| B9.3 | Financials flow-ratio chart, dividend columns, excess-return bars | open |
| B9.4 | Bars inside Scan's table cells | open |

## Not ported
| Row | What | Why |
|---|---|---|
| N.1 | Classic's section fade-in on load | The owner's motion rule: motion only in answer to an action |
| N.2 | Before-open and after-close earnings timing as a feature | Neither app has a data source (yfinance gives dates). A new source is a separate decision |
| N.3 | Pulsing live point | Replaced by a static freshness label (owner's amendment) |
| N.4 | Tab takes the placeholder question | Replaced by a "Use this example" button (keeps Tab navigation) |
| N.5 | Things Classic doesn't have: swipe between tabs, pull-to-refresh, column resize, CSV, print | Nothing to port |
