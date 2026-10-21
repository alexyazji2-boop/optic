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
| B1.2 | Saved research opens the page that holds it | Account sheet | v2's Saved research at `#/research` (B4d; before it, a link to Classic's `#/scan`) | Same | none | none | none | b1 B1.2 | done |
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
| B2a.1 | Measure between two dates on any shared chart | `ui/chart.js` `measured()`, the Measure button, `[data-ms-say]` | Shift-drag, or the Measure button then a drag; M then the arrows from the keys; Escape clears; a plain drag and the wheel do what they did | The Measure button (always shown on touch screens), then a drag; hold then slide outside iOS Safari | Nothing: a measurement is a reading, not saved (Classic kept none) | A one-bar measurement says "Drag to the other date"; the result is announced once it ends | none | b2a desk: plain drag, Shift-drag, button on and off, wheel, keys, Tab, no click ring; phones: hold, quick slide, the button's place; RSI reads in points; iOS: the button and a drag | done. Shipped with an iOS difference, which B2b-1 removed: while a finger is on a chart nothing on the page is selectable (`html.pc-touching`), so hold-to-measure works in iOS Safari too (simulator: "+68.50 (+27.58%) Jan 22, 2026 to Aug 31, 2026", no selection or loupe) |
| B2a.2 | Two fingers measure on touch | Same | n/a | Two fingers on the chart measure between them; pinch-zoom is off over a chart only | none | Lifting announces it | none | b2a phones at 360, 390 and 430; iOS Safari two fingers | done |
| B2a.3 | The readout sits above the finger and on the screen | `place()` in `ui/chart.js` | The tip centres on the point and stays inside the chart | Above the finger; one wider than the chart stacks its dates on a second line | none | n/a | none | b2a phones: tip above the finger, measurement inside the chart and the screen at 360; screenshots in `out-b2a/` | done |
| B2a.4 | An insider marker opens Insiders | Moved to B2b: insider markers live on the price charts (`ui/pricechart.js`) | | | | | | | moved to B2b.11 |
| B2a.5 | A freshness label from the feed's own times | Moved to B2b: it belongs with the Chart tab's live ticks | | | | | | | moved to B2b.7 |

## B2b. Chart tab (`ui/pricechart.js`) and other price charts
B2b ships in two parts. Part 2 evidence: `b2b2_check.py` 17 of 17 (live ticks on a fake clock with served quotes, the Options price chart at 1440, 390 and 360, the rotation map at 1440 and 390, touch emulated); `tests/test_v2_parity_b2b2.py`. Part 1 shipped on 2026-10-21 as dc98fa0. Its rollback point is b38ae02. Live v2 build dc389bfd058b matches the candidate, and `b2b_live.py` passed 5 of 5, run read-only as a guest.
- **Part 1:** the price chart's own interactions, on the Chart tab, Investing's weekly chart and the Instrument page.
- **Part 2:** live ticks and the freshness label, a price chart on Options, and the rotation chart.

The precedence is in `docs/frontend-v2/CHART-GESTURES.md`.

Part 1 evidence:
- `b2b_check.py`: 55 of 55 at 1440, 430, 390 and 360 in headless Chrome, with touch emulated.
- Mobile Safari on the iPhone 17 simulator (iOS 27):
  - a vertical swipe on the chart scrolls the page and leaves no reading;
  - a sideways slide pans (Jul to Oct became May to Aug) and the page holds still;
  - hold then slide reads the bars with no text selection or loupe;
  - a two-finger pinch zooms (May to Aug became Jul 2 to 27) and the page never zooms;
  - zoom out and in step the view;
  - Measure then a drag measures ("+50.04 (+18.14%)", dates on two lines, clear of the legend);
  - a drag on the price scale stretches it (a 52-point range became 32).
- `tests/test_v2_parity_b2b.py`.

Not tested:
- Hold then a second finger (the simulator puts both fingers down at once), emulated only.
- Safari's trackpad gesture events (macOS Safari is not available here; the code path stands aside for touch).
- A physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B2b.1 | Wheel, trackpad and pinch as in Classic | `onDocWheel` and the chart's wheel handle in `ui/pricechart.js` | A notch zooms 1.15, a trackpad stroke by its distance, ctrl + wheel at the pinch rate, sideways or Shift pans; one owner a gesture for 200 ms; zoomed fully out, a wheel down is the page's | n/a | The view survives a rebuild on the same bars, as before | n/a | none | b2b desk: notch 449 to 390, stroke 390 to 349, pinch 349 to 316, pans; Investing: a page scroll started above the chart scrolls over it, one started on it zooms | done |
| B2b.2 | Safari trackpad pinch | `gesturestart` / `gesturechange` / `gestureend` on the chart | Zooms from the pinch's start, about the pointer; the page never zooms | Stands aside for a touch pinch | none | n/a | none | Source test only: Chrome cannot send gesture events and macOS Safari is not available | untested |
| B2b.3 | Touch: direction lock, hold to read, pinch and pan with two fingers | `touchDown` / `touchMove` in `ui/pricechart.js`; `html.pc-touching` | n/a | Tap reads; sideways pans, up and down scrolls; held 300 ms reads; two fingers zoom about their midpoint and pan; the finger left pans | none | A cancelled touch drops its reading | none | b2b phones at 360, 390, 430; iOS Safari swipe, pan, hold, pinch | done |
| B2b.4 | Measure by Shift-drag, by hold and a second finger, by the Measure button, or by M | `measuredBars`, `msSvg`, `fitPlate`, the Measure button | Shift-drag, or Measure then a drag (no pan); M then the arrows; announced at the end; Escape clears | Measure then a drag; hold then a second finger | none (a reading) | One bar: a line only | none | b2b desk and phones (plate holds its text, clear of the legend); iOS Measure and drag | done |
| B2b.5 | Stretch the price scale; double-click, Fit or Reset zoom resets | `.pc-scale` strip, `yZoom` | Drag up stretches, down squeezes; Up and Down keys; double-click fits | A drag on the axis strip (`touch-action: none`) | Kept through a rebuild (`keep()`) | n/a | none | b2b desk (range to under 70%, double-click and Fit restore); iOS drag (52 to 32 points) | done |
| B2b.6 | Zoom out and in on touch screens | `.pc-ctl` buttons, bottom left of the price | Hidden (wheel and keys) | 44 px, about the latest bar; after the Volume label where the band is short | none | n/a | none | b2b phones; iOS (−, −, + stepped Jul 2, Jun 22, Jun 3, Jun 22) | done |
| B2b.7 | Live ticks every 15 s, the price in the tab title, never moving the view; freshness from the feed's own times (was B2a.5) | Chart tab: `onQuote`, `refetchQuiet` in `pages/chart.js`; `chart.tick()`; `sessionFreshness` in `core/marketTime.js`; server `trade_time` and `delayed_minutes` (Yahoo's `exchangeDataDelayedBy`) | The header and the newest forming bar take each quote in the regular session; the title reads "AAPL 345.67 (+0.50%), Chart, Optic"; a closed bar brings the next in with no loading state; a view at the live edge follows it, any other stays | Same | The zoom and price-scale stretch survive the refetch | A dropped tick keeps what is shown; nothing is drawn under a drag or touch | `/api/quote` every 15 s in the trading day, 5 min outside; `/api/intraday` when a bar closes | b2b2 live (fake clock, served quotes): bar and title, zoom kept, held press waits, the next bar arrives; "Live, last trade" only for a feed stating no delay and a trade under 2 min old, "Delayed 15 minutes" for a stated 15 | differs: the freshness is a text label, not Classic's pulsing point (owner's amendment); "Live" is earned from the feed's stated delay and the trade's age, never the refresh rate |
| B2b.8 | Draw a two-point shape in one drag; Escape mid-drag puts it back | `place()`, `cancelDrag()` | One drag places both points (or two presses); Escape mid-drag restores the drawing, the view or the scale | Same with a finger (the chart takes the touch while a tool is chosen) | Drawings in `optic.chart.drawings.v2`, Classic's format, unchanged | n/a | none | b2b desk: a trend line in one drag, Escape restores the points | done |
| B2b.9 | Undo, redo and Delete page-wide, never in fields | `pageKey`, `keyIsFree` (the Chart tab passes `pageKeys`) | Cmd or Ctrl + Z, Shift or Y to redo, Delete, from the page or a toolbar button | n/a | Undo history survives a rebuild, as before | n/a | none | b2b desk: undo and redo from a button, nothing from the Find field, Delete only outside fields | done |
| B2b.10 | Indicator search; × on each pane; a grabbing cursor | Find in Indicators (`findIndicators`), `.pc-px`, `data-drag` | Find by name or what it is also called (RSI, volume profile), across overlays and panes; × takes a pane off and unticks it everywhere; grabbing while panning | Same Find; × at 44 px | The overlay and pane choices in `optic.v2.chart.v1`, as before | "Nothing here is called ..." | none | b2b desk | done |
| B2b.11 | A price chart on Options (pan, zoom, measure, insider markers); an insider marker opens Insiders (was B2a.4) | Options, Setups and strategy: a Price panel (`mountPrice` in `pages/options.js`); `onInsider` on it and on the Chart tab | Daily candles with the 20, 50 and 200-day averages, earnings and insider arrows; every gesture of the Chart tab; a press (not a pan) on an arrow, or Enter on its bar, opens `#/insiders?symbol=AAPL&view=insiders`; the hover box says so | A tap on an arrow opens it | The zoom survives a payload refresh on the same bars | "No daily bars" when the history is missing | the ticker payload (already loaded) | b2b2 at 1440, 390 and 360: drawn with 16 arrows, fits; zoom and measure; a press and a tap open AAPL's insider filings | done |
| B2b.12 | Measure on Investing's weekly chart | The same chart (`pages/investing.js`) | Shift-drag, Measure, keys | As on the Chart tab | none | n/a | none | b2b Investing: "+82.83 (+53.61%) Week of Jan 30, 2023 to Week of Nov 25, 2024, 95 bars" | done |
| B2b.13 | Hover and focus on the sector rotation chart | Macro, Rotation (`rrgChart` in `pages/macro.js`) | Hover a sector: its path lights and a box gives its quadrant, where it came from, strength, momentum and the change; each sector is a Tab stop with the same words for screen readers; Escape or leaving closes | A tap reads; a second tap or a tap elsewhere closes; labels never print over each other | none | n/a | `/api/rotation` (as before) | b2b2 desk (hover, leave, focus, Escape, 11 stops) and 390 (tap, tap elsewhere, no label overlap, fits); iOS Safari: labels apart | done; the iOS tap is emulated only (the simulator's Safari interface got in the way) |

## B3. Long-page navigation
`ui/sections.js` (folds, the strip, Expand and Collapse all, Panels, the knowledge level) and `ui/strips.js` (every sideways strip). Pages, under Classic's view names so its saved choices carry over: Overview (`overview`), Investing (`long`), Earnings (`earnings`), Financials (`financials`, its own strip kept) and the Options groups (`swing`).
Evidence:
- `b3_check.py`: 24 of 24 in headless Chrome at 1440, 390 and 360, with touch emulated; six phone pages swept for sideways rows.
- Mobile Safari on the iPhone 17 simulator: the strip's end arrow scrolls it, a tapped jump lands under the top bar, and a tap on a folded heading opens it.
- The B1, B2a, B2b and B2b-2 checks rerun with B3 in place: 78, 46, 55 and 17, all passing.
- `tests/test_v2_parity_b3.py`.
Not tested on a physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B3.1 | A sticky "Jump to a section" strip on long pages | `.sec-index` on pages with 6 or more sections (Investing, Earnings) | Sticky under the header; jumps land below it (`--secidx-h` in the scroll padding) | Scrolls with the page, as the header does (B1.8) | none | Fewer than 6 sections: the bulk row only | none | b3 desk and phones | done |
| B3.2 | The strip scrolls sideways by wheel and drag, with edge fades | `ui/strips.js` | A wheel moves it sideways while it can move that way, then the page's; a mouse drag scrolls it and never clicks the chip it ends on | Native swipe | none | n/a | none | b3 desk (wheel 300 px, page still; drag 200 px; arrow 630 px) | differs: an arrow button at each edge instead of a fade, since the design standard allows only two gradients; the arrow also gives a reader without a wheel a way to the far end |
| B3.3 | It highlights the section on screen; a jump opens a folded section | `current()`, `openSection()` | The lit chip is underlined in gold like the tabs and kept in view; a jump opens, scrolls (smooth for a short hop, instant for a long one or reduced motion) and focuses the heading | A tap does the same | The opened state is saved | n/a | none | b3: the jump opened "The multiple against its own history" 8 px under the strip, focus on it; phones 8 px under the top bar; iOS Safari jump | done |
| B3.4 | Fold sections, remembered (`optic.panels.open`); Expand all and Collapse all | Every top-level section with a heading | The heading or its button folds it; a folded section is its heading line alone | 44 px button; the heading is a target too | `optic.panels.open` `{"view|title": bool}`, Classic's key, format and ids (`panelId`), read and written as Classic does; company names and fiscal years taken out of the ids | Applied again after every redraw, before paint | none | b3: fold, label, reload kept, Collapse and Expand all; Financials read a Classic-format record; Options' fold kept across groups; iOS tap | done |
| B3.5 | A Panels chooser per tab | Panels in the bulk row | Untick to take a section off the page and the strip; Show every section | Same menu | `optic.panels.hidden.v1` `{"view|title": true}`, deleted on show, as Classic | "N off" on the button | none | b3: off, kept through a reload, restored | done |
| B3.6 | The knowledge level folds the specialist sections | `levels` per page; `prefs.knowledge()` | Above the reader's rung a section starts folded and says "Advanced"; a choice the reader made wins; changing the level re-applies at once | Same | The level is Classic's `optic.knowledge.v1` | n/a | none | b3: folded at Literate (the default), open at Advanced | done (Investing's two and Earnings' implied move, as Classic's tables; Options keeps its group tabs, where choosing a group is the request) |
| B3.7 | Edge fades on sideways strips (Home, phone) | `ui/strips.js` on `.tabs`, `.tabset`, `.mstrip`, `.drail`, `.bk-tabs`, `.chw-rail`, `.ch-draw`, `.ws-presets`, `.chips-scroll` and the section strip | Arrows show only while there is more | Same; six phone pages swept: every row that scrolls sideways shows its arrow | none | n/a | none | b3 phone sweep; Chart rail arrow (0 to 264 px, back arrow shown); iOS Safari | differs: arrows instead of fades (as B3.2) |
| B3.8 | Insider tables capped in height, with sticky headers | Financials' insider and Congress tables; the Insiders page | Capped at the smaller of 62% of the window and 560 px; the header stays as the rows scroll | Same | none | n/a | none | b3: 558 px cap, 969 px of rows, header at the top after scrolling | done |

## B4. Milo
### B4a. Docking and context
Evidence:
- `b4a_check.py`: 16 of 16 in headless Chrome at 1440, 1200 and 390 (touch emulated), against the stand-in model (one question sent, nothing billed).
- `b4a_widths.py`: Milo docked at 1316, 1160 (rail folded) and 1440; 15 pages each, nothing spills and no page-wide overflow. The same sweep at 1024 with Milo over the page.
- Mobile Safari on the iPhone 17 simulator: Milo opens as the full sheet, not docked.
- `tests/test_v2_parity_b4a.py`.
Not tested:
- The phone keyboard with a signed-in session in real Safari: the guest sees the sign-in prompt instead of the box, and B4a leaves the keyboard-fitting code unchanged.
- A physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B4a.1 | Docked panel, only when the research column keeps its usable width | `ui/milo.js` `dockFit`, `layout`; `makeDrawer` in `ui/drawer.js` | Beside the page while it keeps 760 px (`CONTENT_MIN`, measured on 15 pages); Milo narrows to fit, to 320 px; below that, over the page as a dialog. A resize across the line moves it | The full sheet, as before | The chosen width in Classic's `optic.chat.width.v2`, as before; the docked width is never saved | n/a | none | b4a: docked at 1440 (page 760, Milo 444), over the page at 1200 and back; widths sweep | differs: the line is the page's usable width (760 px), not Classic's 240 px left over (owner's amendment 8) |
| B4a.2 | The panel stays open across pages; no focus trap while docked | Same | Docked: no scrim, `role="complementary"`, no `aria-modal`, Tab moves on to the page, a page link beside it works, it stays open and its context follows the page; another drawer opens over it; Escape inside it closes it, focus back; over the page it is the dialog it was and closes with the page | n/a | none | n/a | none | b4a desk and 1200 | done |
| B4a.3 | Ask Milo from a panel sends that panel's own figures | `panelFigures` in `ui/milo.js`, read at the press by `app.js` | Every panel's Ask Milo: the heading, the value tiles, the finding line and the first table rows that are on screen go as `panel` in the context; the box says "attached, with its N figures" | Same | none | A panel with nothing to read sends none | `/api/chat` $ only on Send | b4a: Investing's Fair value and stars, the figures sent equal to those shown | differs: read from what the panel shows rather than wired by hand at each of Classic's 44 call sites, so every panel has it and the figures are the ones on screen |
| B4a.4 | Suggestions as quiet buttons; a "Use this example" button | `suggestHTML`, `exampleAsk`, `OPTIONS_FOLLOWUPS` | After an answer: on Options, Classic's six follow-ups; on every page, the example and "Use this example"; each drafts into the box and focuses it, never sends; Tab moves on as usual | Same | none | Hidden while typing, answering or blocked | none | b4a: six follow-ups, the example drafted and focused, no message sent, Tab to Send | differs: quiet buttons, not chips (amendment 3); a button, not Tab, takes the example (amendment 7) |
| B4a.5 | A 1024 window, found by the width sweep | `pages.css`, `components.css` | The Watchlist drops volume and earnings under 1100 px (they are in each row's detail); the Dossier header puts its actions on a row of their own between 861 and 1100 px; the top bar's Ask Milo no longer wraps; end-aligned menus open leftward (the B3 Panels menu had widened the page by 128 px) | n/a | none | n/a | none | b4a widths at 1024; b3 desk overflow 0 | done |

### B4b. Attachments
Evidence:
- `b4b_check.py`: 11 of 11 in headless Chrome at 1440 and 390, with real files on disk.
  - The file picker and drag and drop.
  - Refusals: a renamed file, a 6 MB file, a text file and a fifth file.
  - Removal, sending, and the saved conversation.
  - The server's own checks, by a direct request that skips the browser's.
- Against the stand-in model, whose log shows the image and document blocks that reached it. This is stand-in verification only: the model provider's own handling of the files has not been exercised.
- `tests/test_v2_parity_b4b.py`.

Retention, as the panel says it ("Sent with your next question to Milo's model provider. Optic does not keep them."):
- **In the browser:** a file is held in the tab's memory until it is sent or removed. It is never written to the saved conversation (`optic.pulse.history.v1` keeps role and text only). Its name shows under the question in this tab only.
- **On Optic's server:** the file arrives base64 in the `/api/chat` request and is checked by `app/ai.py` `attachment_blocks`. It is passed to the model provider (Anthropic) in that one request. Nothing is written to disk and nothing is logged.
- **At the provider:** its own API data-retention terms apply.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B4b.1 | Attach files (button, drop); type, size and count checked in the browser and on the server | The clip beside Milo's box; file tiles above it; `attachProblem`, `bytesMatch` in `ui/milo.js`; `attachment_blocks` in `app/ai.py` | The clip or a drop on the panel; PNG, JPEG, GIF, WebP or PDF, up to 4 of 5 MB; each refused file says why on its tile ("not a PNG file, whatever its name says", "larger than the 5 MB limit"); the server checks the type, the decoded size and the file's own first bytes again, and its refusals stay under the answer | The clip and the remove buttons at 44 px | Nothing: see retention | A send that fails gives the files back with the question | `/api/chat` $ on Send (files add to the cost) | b4b desk and 390 | done (stand-in verification; the provider's handling of the files is untested) |

### B4c. Web search, Deep research and the modes
Evidence:
- `b4c_check.py`: 10 of 10 in headless Chrome at 1440 and 390, against the stand-in model. Its log shows the web tool on the request and the research route used.
- This is stand-in verification: no real web search or research has run.
- `tests/test_v2_parity_b4c.py`.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B4c.1 | Web search toggle ($, on send) | "Search the web" in the row above Milo's box | Off until pressed; on, the next questions go with web search, and each answer says "Web search was on for this answer"; its label says searches add to the cost | 44 px | Not saved: off again when the panel closes | Off while answering | `/api/chat` with `web` $ per search, on Send | b4c: off by default, the web tool on the request, the note, off after reopening | differs: off by default (Classic had it on). v2's Milo looks Optic's own data up with its tools, so the web is the reader's spend to choose |
| B4c.2 | Deep research and the modes row ($, on send) | "Deep research" and "Modes" in the same row | Modes: Classic's research modes for the page (company, chart, Brokerage, portfolio or watchlist, Scan, the market), word for word, each only writing its question into the box; the Deep research mode points at the Deep research button. Deep research runs the box's question, or the symbol on screen, or the market, by `/api/research`, and the answer says it read live web sources | 44 px; the menu opens upward | none | Off while answering | `/api/research` $ (one question and several searches), on a press | b4c: five company modes, drafting only, the hint, Deep research on an empty box as "Deep research: AAPL", Brokerage's five modes | differs: the modes sit in a Modes menu rather than a row of chips (amendment 3, and room beside a docked page) |

### B4d. Saved research
Evidence:
- `b4d_check.py`: 10 of 10 in headless Chrome at 1440 and 390, signed in (rows in the local test database) and as a guest (Classic-format browser records).
- `tests/test_v2_parity_b4d.py`.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B4d.1 | Save a question; Saved research hub | Save under each question in Milo; `#/research` (`pages/saved.js`, `core/research.js`), from the Account sheet, the palette and Milo's Open Saved research | Save keeps a question with the account (or this browser), says where, and refuses a duplicate; the hub lists the questions with their symbol and date; Ask again puts the question in Milo's box and sends nothing; Forget with Undo; Classic's four ways to start an investigation | Same; 44 px buttons; one column | Signed in: `/api/saved-research` rows as Classic writes them (`research_type: 'pulse'`); a guest: `optic.research.v1` `[{question, ticker, at}]`, 40 at most, Classic's format and key, old and partial records read | Empty: how to save one; a failed load: Retry | `/api/saved-research` (free) | b4d: save, duplicate, the hub from the Account sheet, Ask again, Forget and Undo, the palette, a guest's Classic records | done. Differs in where it lives: a page of its own rather than inside Scan, with no new sidebar item (sidebar changes need the owner's approval) |


## B5. Alerts and signals
Evidence:
- `b5_check.py`: 38 of 38 in headless Chrome at 1440, 1024, 430, 390 and 360 (touch emulated at the phone sizes; light at 430), signed in as the local owner and as a guest.
  - Every inbox and signal-history answer is a fixture served in the browser, so nothing was marked read, cleared or emailed on any server, and no notification was sent.
  - The one real write was a swing-setup alert on the local test account, deleted at the end of the run.
- `tests/test_v2_parity_b5.py`: the urgency groups, readings, filters and query; the browser store in Classic's format, with old, partial and malformed records.

Not tested:
- A real scheduled check that fires a swing-setup alert and records it on the server (`watch_runner`). The page's own check was driven against a fixture.
- The follow-up endpoint's own candle reading; it was answered by a fixture.
- Real Safari and a physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B5.1 | Inbox: kind filters, unread only, urgency groups | Alerts, "From Optic's paper book" (`ledger`, `bookGroups` in `pages/alerts.js`) | Grouped as Classic's `ALERT_URGENCY`: Needs attention, Worth knowing, For the record, each with its count, time ordering each group; a filter per kind present (squared toggles, counts), focus kept; Unread only for the owner | Same; 44 px toggles, nothing off the page at 360 | Nothing (Classic kept the filters in memory too) | Empty: what fills it and that empty is the common case; no match: Show all; a failed load: Retry | `/api/alerts?limit=50` (free) | b5: groups, kind filter, Unread only | done. Differs: unread marks and Unread only are shown to the owner alone. The read state is the deployment's, which is the owner's, so to a reader the marks would only say what the owner has read (Classic showed them to everyone) |
| B5.2 | "Why this fired"; mark read; Clear all; the e-mail delivery note | Same (`bookRow`, `readings`, `deliveryNote`) | Why this fired opens the kind's rule and the alert's own readings, ids left out (`aria-expanded`); the owner: Mark read on a row (`{ids}`), Mark all read (`{}`), Clear all after an in-page confirmation that says it clears for every reader, focus to the heading after; the delivery note: what email is set to do and what it last did, or the missing settings folded | Same | Nothing | Refused by the server: says nothing was marked | `/api/alerts/seen`, `/api/alerts/clear` (owner only, behind the write guard) | b5: why open and closed, mark read, mark all read, confirm then keep, clear, both delivery notes; a reader sees none of the owner's controls | done. Differs: Clear all asks first (Classic cleared at once) |
| B5.3 | Setup alerts | Options, Setups and strategy, "Setups and patterns" (`options-panels.js` `setups`); `addAlert` in `core/watches.js`; the Alerts form's "A swing setup triggers" | Alert me on each armed, triggered or watched setup sets a `swing_setup` alert naming its preset, as Classic's `addWatchDef`; says where a trigger lands; Alert set after, kept across the panel's repaints, pressed again sends nothing; a duplicate is refused | Same; 44 px | Signed in: `/api/watches`; a guest: `optic.watches.v1` in Classic's format and key, 40 at most | Refused (duplicate, 40, another account's browser): says why | `/api/setups` (free) | b5: account (real, then deleted) and browser; duplicate after a reload; the form opened at the swing-setup condition | done. The full Swing setups tool (scope, filters, rules, back-tests) is B6b |
| B5.4 | Signal history and follow-up | Alerts, "Signal history" (`pages/signals.js`) | One folded record per trigger: date, symbol, setup, side, status, and the close after 1, 5, 10 and 20 candles (not yet or unknown in words, never a number); open: the record as it fired, what followed, its conditions, and readings, parameters and assumptions folded; filters for status, side, symbol and setup (the account's asked of the server); an open record stays open across repaints | Same; filters two to a row with labels above | Signed in: the account's (`/api/signals`); a guest: `optic.signals.v1` `{signals: [<=200], events}` in Classic's format: records kept as built, what followed appended once each, the first reading never replaced, another browser's keys ignored | Empty: how to set a swing setup alert (opens the form there); no match: Show all; unreadable store: an empty history; a failed follow-up: says the horizons show as unknown | `/api/signals`, `/api/signals/followup` (free, stores nothing) | b5: the account's list, a record opened, a status filter on the server, the open record kept; a guest's Classic records followed up and merged; a malformed store; a page check that fires one | done. Differs: an old record without a label is named from the condition list rather than by its rule id |

## B6. Research tools
### B6a. The thesis check and the Overview's advanced research
Evidence:
- `b6a_thesis_check.py`: 19 of 19 in headless Chrome at 1440 (a guest, with Classic's records seeded) and 390 (the local owner account; real writes to the local test database, deleted at the end). A source held back in the browser makes the page redraw while a note is typed.
- `b6a_research_check.py`: 21 of 21 at 1440, 1024, 390 and 360, a guest, on the preview's own data, with one fixture: a later quote, to make the header redraw.
- `tests/test_v2_parity_b6a.py`: the seven conditions, the stored record against Classic's shapes (old, partial and Brokerage-written ones), the factor rules, the Pulse read, the scores and the statistics.

Not tested:
- Real Safari and a physical phone.
- The live site's data for these sections (they read the same payloads as the preview).

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B6a.1 | Thesis check (`optic.thesis.v1`) | Overview, "Your thesis check" (`pages/thesis.js`), in place of the link to Classic | Start, then Classic's seven conditions with how each reads today; a level in dollars ("$1,200" read as 1200); a note; Save. Then: a headline ("2 of your 3 conditions hold"), each condition now, what flipped since it was written, the note, the next report's date; Edit, Ask Milo to stress-test it (Classic's question, drafted only), Delete with Undo | Same; 44 px rows, 16 px fields | `optic.thesis.v1` in Classic's format as a backing copy on both paths; signed in, `/api/theses` (authoritative once loaded); a save keeps what Brokerage's form wrote in the same record (risks, watching, the reader's own reassess line, horizon, assumptions) | Waiting for data: says so; a figure missing: "could not check this just now"; an unknown rule: not invented; a failed account save: kept here and said so | `/api/ticker`, `/api/longterm` (free) | b6a_thesis: the form, a redraw while typing (note, ticks, focus and caret kept), refusals, Classic's format, the view, Milo's draft, Delete and Undo, a flipped Classic record, prose kept, account save, failed save, fund | done. Differs, to protect data: the note starts from the record's own words, and an existing reassess line is kept (Classic started empty and overwrote both); a ticked level with no level is refused (Classic dropped it); "its sector" said once (Classic printed "its its") |
| B6a.2 | Pulse score | Overview, Advanced research, "Optic's short-term read" (`pages/overview-research.js`) | The lede, the catalyst lines, the five inputs as diverging bars with their weights, the scale and skill notes, conviction and agreement, the lead story; "Why it reads this way" folded: what carries it (score times weight), the other side, what conviction means, the limits and the sources | Same; bars narrower | Nothing | No inputs: the block is left out | `/api/ticker` `pulse`, `digest` (free) | b6a_research: five rows with weights, the fold's content | done |
| B6a.3 | All statistics and the method note | Advanced research, "All key statistics", "The rest of this ticker", How this works | Classic's eighteen figures, the feed's missing ones left out, each label opening Classic's definition (`stat:` terms in `ui/term.js`); one reading from each tab, each a link; the method folded | Two cards to a row | Nothing | A missing figure is left out, not dashed | `/api/ticker`, `/api/fair-value` (free) | b6a_research: 17 shown with definitions, six tab cards, the fold | done |
| B6a.4 | Short-term Optic Score | Advanced research, "Optic Score, both horizons" | Short term (the swing composite) beside long term on one 0 to 100 scale, their words and bases, the disagreement note, and the price note when a high long-term score sits beside a stretched P/E | One column | Nothing | Long term still loading: says so | `/api/ticker`, `/api/longterm` | b6a_research: both tiles | done |
| B6a.5 | Factors and "What to look at next" | Overview, "What to look at next"; `factors()` in `overview-research.js` | Coming up: the report by its date and days only (no time of day: B1), the week's releases (positioning reports at Advanced); research steps to each tab and Compare; Ask Milo drafts a question; "What has been moving it recently" folded. Classic's rule-based factors drive the steps and the fund's risk | One column | Nothing | No dates: says so | `/api/ticker` | b6a_research: events, steps, the fold, Milo's draft, no timing words | done. Differs: the company's bull and bear lists stay the server's `cases` under More (already in v2), so Classic's client-side lists are not shown a second time |
| B6a.6 | Fund takeaways and the risk card | Overview, under a fund's four answers (`fundRisk`) | "A risk to weigh", the first point against it, with its evidence's tab; a fund has no Financials card or step and no thesis check | Same | Nothing | No point against: nothing shown | `/api/ticker` | b6a_research: SPY | done |
| B6a.7 | Stage label in the header | The Overview's header line (`dossier-frame.js` `header({stage})`) | "Stage 2, advancing" as text, opening what it means for the symbol and its limits; kept when the live price redraws the line | Same | Nothing | Unavailable: no label | `/api/stage` (free) | b6a_research: the label, its explanation, after a redraw, at every width | done |

### B6b. Swing setups in full, and chart patterns with their base rates
Evidence:
- `b6b_check.py`: 19 of 19 in headless Chrome at 1440, 1024, 390 and 360, a guest, on the preview's own data. Classic's saved view and rule settings were seeded; the one write is a guest alert in the browser.
- `b5_check.py` (38 of 38) now presses the alert in the opened row.
- `tests/test_v2_parity_b6b.py`: Classic's stored shapes, partial and junk values included; the scan's request; the rules form; the base-rate reading.

Not tested:
- A watchlist scan of 40 symbols against the live feed (it is the same request with more symbols).
- Real Safari and a physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B6b.1 | Swing setups: scope, filters, rules form (`optic.setups.*`) | Options, Setups and strategy, "Swing setups" (`pages/setups.js`), in place of the compact list and its link to Classic | Symbols (this one or a watchlist), direction, timeframe (4-hour for one symbol), strategy and status as selects, each rescanning with focus kept; the summary line (the candles, through when, the count in each state); Rule settings: the shared context and each preset's parameters and on-off, Apply keeping only changes, Back to the defaults; a row on changed settings says "your settings" | Filters two to a row; the scan as a list, no sideways scroll | `optic.setups.view.v1`, `optic.setups.params.v1`, Classic's keys and formats | Reading; failed: Retry; an empty watchlist; nothing matches: says how to see everything | `/api/setups`, `/api/setups/catalogue` (free) | b6b: the saved view and settings read, the request, filters, scope, the rules form, the reset | done. Differs: a row opened under old settings closes when they change (Classic left it reading forever) |
| B6b.2 | Setup detail, back-test table, contract finder | A row's Details | The rule, Alert me when this triggers (B5's alert), the chart (the close, the rule's own lines, trigger and invalidation, where it armed, triggered or ended, a legend), the conditions met, the readings and volume, the back-test (all, earlier 70%, held out 30%, in R, with its assumptions), and the contract finder (days to expiry, open interest, volume, spread; what passed and why; the tab's budget) | The detail as wide as the screen | Opened rows and the contract filters survive the group's redraws (one node for the visit) | Each part loads on its own; a failed chain says so | `/api/setups/{T}/detail`, `/api/setups/{T}/options` (free) | b6b: a row opened, chart drawn, back-test rows, contracts asked with the typed filters, the alert, a group switch | done. The chart is v2's line chart with the levels, not Classic's candles |
| B6b.3 | Chart patterns with measured base rates | Options, "Chart patterns and seasonality" | Structure, supply and demand zones, and recent candles, each beside the hit rate of its conventional reading over 21 sessions across 43 names and ten years, and its edge over the stock's own drift; Classic's caveats; the base rates' method folded; relative performance and seasonality as before | Same; tables scroll inside their box | Nothing | Base rates loading (the server may build them for 90 s): says so; failed: says so | `/api/patterns/base-rates` (free, the same for every symbol) | b6b: rates beside patterns | done |

### B6c. The track record
**The `validation` branch, reviewed (2026-10-21).** 20 commits and 39 files (about 8,000 lines) on 76ad67d, 15 October, never pushed. What it holds:
- **Research code and its record.** `app/validation/*.py`, the historical validation program's engines, about 2,200 lines. Its docs: `docs/validation/`, the protocol, the report and the inventories, about 4,700 lines. Its tests: five files.
- **The program's result.** `app/validation/history.json`: 11 rules, each with a verdict line and its sample. 0 of 82 supported; the IV "rich" verdict is the one clear result.
- **`/api/validation` gains `history`.** It reads that file in `app/main.py`, 14 lines.
- **Product changes unrelated to the slots:**
  - the retirement planner moves to total returns (`app/analytics/retirement.py`, 130 lines, and `retirement_history.json`), with Classic's Roth "What history did with this mix";
  - wording edits in `regime.py`, `pulse.py`, `longterm.py` and `swing.py`, with `test_pulse.py`;
  - Classic's own history slots and Milo context (`static/app.js`).

**Taken, and verified alone:** the 14 lines in `main.py` and `history.json`, byte for byte (`tests/test_v2_parity_b6c.py` compares it with the branch). Nothing else. The research package, the docs, the retirement change, the wording edits and Classic's slots stay on the branch for the owner: each changes what readers are told or how a figure is computed, and none is needed for the slots.

Evidence:
- `b6c_check.py`: 13 of 13 in headless Chrome at 1440 and 390, a guest, on the preview's `/api/validation`.
  - Held back once: each slot says "not yet tested" meanwhile.
  - Refused once: the slots imply nothing and the history lines stay hidden.
- `tests/test_v2_parity_b6c.py`: the endpoint with history, a missing or broken file, the file against the branch's own, and the words in Classic's own terms.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B6c.1 | `validation` branch reviewed; only the compatible work it needs taken | `app/main.py` `_validation_history`; `app/validation/history.json` | n/a | n/a | n/a | A missing or unreadable file is `history: null`, never an error | none | b6c tests | done. The rest of the branch is listed above for the owner's decision |
| B6c.2 | Track-record slots on Options and Investing | `core/track.js`, and each place below | Options: the composite (Swing verdict, with its chart input's history); dealer gamma and the walls (their forward record; no history of open interest exists); the swing setups (their 17 presets replayed); the IV verdict's history; the candles' history. Investing: the long-term score's history. Also: the Chart tab's back-test, the Read page's index regime, and the Overview's stage explanation. Milo is given the record on Options and Investing | Same | Nothing (the record is cached 30 minutes) | Before it answers: "not yet tested"; failed: the same, history hidden | `/api/validation` (free) | b6c: every slot, delayed and refused | done |

## B7. Valuation
| Row | Task | Status |
|---|---|---|
| B7a.1, B7a.2 | See B7a below | done |

### B7a. The fair-value model's editor
Evidence:
- `b7a_check.py`: 18 of 18 in headless Chrome at 1440, 390 and 360, a guest, on the preview's own model. Every run is POST `/run` (free), whose bodies the check read.
- `tests/test_v2_parity_b7a.py`: Classic's store with bad copies, a box's text to an edit, the formats, the methods side by side.

Not tested:
- A bank, insurer or REIT, where the cash-flow model does not suit and residual income or FFO leads; their sentences are ported, and B7c brings their forms.
- Real Safari and a physical phone.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B7a.1 | DCF editor: inputs and per-year overrides, recomputed as you type (`optic.dcf.v1`) | Investing, "Fair-value model, discounted cash flow" (`pages/dcf.js`), in place of the summary and its link to Classic | The assumptions form, folded: Classic's 25 fields in six groups, each with its default and why, edited ones marked; the method choices; set individual years; Reset to the defaults. Typing recalculates after 350 ms and repaints only the results, so the box and its caret are untouched; a bad number is marked and said and runs nothing; a missing reported line can be typed in from the filing (B, M, K), with the filing's own candidates offered | Fields stack, 44 px, 16 px type | `optic.dcf.v1` edits per symbol in Classic's format, the other symbols and the saved models left as they are; read back and run on the next visit | Loading; failed: Try again; the last good figures stay while a run fails, and say so | `/api/valuation/{T}`, POST `/run` (free) | b7a: one run per edit with the value sent, the caret kept, Classic's store, a bad number, an override, a method switch, a page redraw while typing, a reload, reset | done |
| B7a.2 | Sensitivity, forecast, bridge, statements and formulas | The same section | The sentence and the four figures that frame it, the terminal share, the checks; what moves the value most (each assumption stepped down and up); the methods side by side on one axis, never averaged; what today's price implies; three sensitivity tables (a pressed choice of pair, shaded against the price with the number always printed); bear, base and bull; then folded: the forecast year by year with the terminal value and the exit-multiple cross-check, the discount rate, the bridge (a line can be left out), the linked statements, the sources and the formulas; Classic's questions as quiet buttons that draft into Milo | One column | Folds opened stay open across reruns | A method that does not suit says why and what leads instead | as above | b7a: the summary, each part, a sensitivity pair, the forecast staying open, the bridge sent | done |
| B7b.1 | Saved models: list, save, compare, replay, use | done (see B7b below) |
| B7c.1, B7c.2 | See B7c below | done |
| B7d.1 | Valuation Milo card: Preview, Apply, Undo | done, stand-in verification (see B7d below) |

### B7b. Saved models
Evidence:
- `b7b_check.py`: 13 of 13 in headless Chrome, as a guest at 1440 and on the local account at 390 (real writes to the local test database, deleted at the end). Covered: save, list, rerun exactly, compare with now, use these assumptions, and delete with its confirmation.
- `tests/test_v2_parity_b7b.py`: the snapshot, a guest's models in Classic's format, the compare.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B7b.1 | Saved models: list, save, compare, replay, use | The fair-value model, "Saved models for {T}" (`dcf.js` `savedHTML`) | Name and Save a snapshot (the reported figures, the assumptions and the result together); each saved model with its value then, its inputs' date and what it changed; Rerun exactly (the same as when saved, or how it differs and whether the engine moved); Compare with now (the assumptions that differ, newer filings, the price); Use these assumptions on today's figures; Delete, confirmed in the page | Same; 44 px | Signed in: `/api/valuation-models`; a guest: `optic.dcf.v1` `models`, Classic's format, newest first, 40 at most | Nothing to save without a result; a failed load or save says so | `/api/valuation-models*` (free) | b7b, both paths | done. Differs: Delete asks in the page, as v2's other deletes do (Classic used the browser's confirm dialog); a price that rounds alike is shown in cents |

### B7c. The other methods
Evidence:
- `b7c_check.py`: 13 of 13 in headless Chrome at 1440 and 390, a guest, on the preview's own model and feeds. Covered:
  - AAPL: the methods, Optic's peers and the reader's, the segments with a changed multiple, the dividend model's form;
  - JPM: residual income leads;
  - O: FFO among the methods.
- `tests/test_v2_parity_b7c.py`.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B7c.1 | RI, FFO, DDM, FCFE | The fair-value model, "Other valuation methods and when each fits" (`methodsHTML`), and "Assumptions for the dividend model" (`equityForm`) | Each method with its fit and why, and what it gives: the equity DCF at its cost of equity, the dividend model's path, residual income's book and return on equity against its cost (and the return the price implies), a REIT's FFO and its own past multiples; the equity models' own assumptions, with the cost of equity when the cash-flow model does not suit | Same; one column | `optic.dcf.v1` `edits.equity`, Classic's format | When the cash-flow model does not suit, the methods and the equity form open, and the sentence leads with what does | `/api/valuation/{T}`, POST `/run` | b7c: the methods, the dividend model's edit sent, a bank, a REIT | done |
| B7c.2 | Comps and SOTP | The same fold | Compare with peers (Optic's, or the reader's comma-separated list, said to be theirs): each multiple against the peers' quartiles and what it implies a share, the peers and those set aside; Value the segments: each segment's operating income at a multiple (starting at the DCF's own, which reproduces the whole), reconciled with the company's, a value a share; Recalculate with the reader's multiples. Peers' readable multiples and the parts join the methods side by side | Tables scroll inside their boxes | Typed peers and multiples survive a rerun | Reading; failed: says so, with Try again for the segments | `/api/valuation/{T}/comps`, POST `/api/valuation/{T}/sotp` (free) | b7c | done |

### B7d. Milo's proposal card
Evidence (stand-in verification; the real model's proposals are not exercised):
- `b7d_check.py`: 10 of 10 in headless Chrome, signed in as the local owner, with Milo docked beside Investing at 1440 and overlaid at 360 and 430. The STAND-IN model (:8098) wrote the proposals; the engine runs behind Show the effect and Apply are Optic's own and free. Covered:
  - the whole model sent to Milo as context;
  - the card's label and reason;
  - Show the effect runs on a copy, so the screen and the store are unchanged;
  - Apply changes the working assumptions only, reads "Applied", focuses Undo, and leaves the saved models alone;
  - Undo puts it back;
  - a key the model lacks is not offered;
  - a proposal for AAPL is refused while MSFT's model is on screen (reached by in-app navigation, Milo staying docked);
  - away from Investing it says where the card works;
  - on phones the card fits the overlay with 44 px buttons.
- `tests/test_v2_parity_b7d.py`: Classic's parseAction rules, the shared field list, how a change lands in the edits, the context.
- Not verified: a proposal written by the production model. That needs an authorized real-model run.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B7d.1 | Valuation Milo card: Preview, Apply, Undo | Milo's answer, when it proposes `[[action valuation KEY=VALUE ... "reason"]]` (`core/milo-text.js` `valuationAction`, `ui/milo.js` `valuationPress`); the model on Investing registers itself while on screen (`dcf.js` `VAL_API`) | What it would change and Milo's reason; Show the effect gives the base value before and after and the terminal share, computed by Optic's engine; Apply waits for that, then changes the working assumptions (the form, the store), reads Applied, and offers Undo with focus; Undo restores the edits as they were. Milo is given the whole model: each assumption by key with its source and reason, the base case, what moves it, the reverse DCF, the other methods | Milo overlays the page; the card fits, 44 px | `optic.dcf.v1` edits only, Classic's format; saved models are never changed | No model on screen: says to open the company's Investing tab; another company's model: says whose it was for; a key the model lacks or a missing reason: not offered, says why; a failed run: says so | Milo (paid, only on Send); `/api/valuation/{T}/run` (free) | b7d (stand-in) | done, stand-in verification. Differs: Classic named the symbol in the label ("Try on the AAPL model"); v2 says "the model on screen" and checks the symbol on press. With no pair at all v2 keeps its earlier "Open the valuation model" link, where Classic said the proposal named nothing |

## B8. Home, Desk and Markets extras
| Row | Task | Status |
|---|---|---|
| B8.1 | Desk: bottom line, scenarios, calendar, limits | done (see B8a below) |
| B8.2 | Catalyst day strip | done (see B8a below) |
| B8.3 | What changed since yesterday | done (see B8b below) |
| B8.4 | Index and sector trends board on Home | done (see B8b below) |
| B8.5 | Questions worth asking | done (see B8b below) |
| B8.6 | `home-released-results` reviewed; released results in What Matters Today | done (see B8a below) |
| B8.7 | Today's Read built on request ($, labelled) | done (see B8c below) |
| B8.8 | Earnings this week page (dates; timing only when sourced) | done in B1 (row B1.1) |
| B8.9 | Markets opens on its last page | done in B1 (row B1.4: Markets returns to Macro) |
| B8.10 | Ticker suggestions on Analysts and Compare | done (see B8c below) |

### B8a. What matters today and the Desk
The `home-released-results` branch, reviewed (2026-10-21). It holds two commits on a base from 2026-10-15 (bf8d0bf):
- f888236, released results: `app/priority.py` (`_event_result`, `_earnings_result`, past-tense titles), Classic's display in `static/app.js` and `styles.css`, and `tests/test_home_results.py`, with assertions in two other tests about Classic's display.
- d90bbd3, unrelated: Classic's "what Milo reads" menu made opaque, with its test.

Taken: `app/priority.py` exactly as the branch has it (main had not changed the file since the base), and the server half of `tests/test_home_results.py`. Left on the branch for the owner:
- Classic's display of the results: Classic's `app.js` and `styles.css` have changed by about 1,950 lines since the base, so it would need a hand merge, and v2 does not need it;
- the branch's Classic page tests and its two edits to other tests;
- d90bbd3.

Since the results come from the server, Classic keeps showing "Out" until that display is merged.

A cost: each board build now also reads the surprise table for this week's reported names. It is free (Yahoo) and cached for six hours with the Earnings tab's own read, so an earlier day's report can say its figures are late for up to six hours after Yahoo has them.

Evidence:
- `b8a_check.py`: 15 of 15 in headless Chrome, signed in as the local owner, at 1440 and on phones at 390 and 360 (touch emulated). Two passes:
  - the preview's own board, rebuilt with the new server code: ABT this morning "In line", GM, ISRG, NOC and RTX yesterday "Beat", IBM after today's close still "reports";
  - a FIXTURE board and Desk: a released PPI with its BLS headline, a release still waiting, scenarios, an edition, a written version set aside because the market moved.
- `tests/test_v2_parity_b8a.py`: placement, result words, a row's key across "reports" to "reported", the Desk. `tests/test_home_results.py`: the server rules.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B8.1 | The Desk in full | Home's Optic Desk panel (`home.js` `deskBody`) | The edition when one is kept (today's, or the latest with its date), with a link to it on the Read; the bottom line first, then the first lead line; folded under The whole desk: the rest of the lead, What could happen next, the note, Today's reports; What this does not tell you, folded with its count; which voice wrote it, and at the foot why the written version is not showing (the market moved since, with a new one being written; or it could not be produced) | Same; the branches stack | The folds stay open across the panel's refresh | The panel's own reason when there is no Desk | `/api/home` (already loaded; its prose already paid for) | b8a, both passes | done. Differs: no glossary marks yet (B9) |
| B8.2 | The week as days | What matters today, above its list (`home.js` `catalystStrip`) | The trading days the board looks at, from Today, a market holiday drawn as closed; two items a day, high impact first, the rest as "N more"; an item opens its note under the strip, one at a time (its result, its description, Open the company); a warm left edge for high impact and a dashed one for a company's report, said in a key; reports by ticker; nothing placed that the feed does not date; no time invented | A sideways strip with its arrows (ui/strips.js); a swipe moves it, not the page; 44 px | The open note, the open rows and the open groups survive the panel's repaint, by each item's key | Nothing placed: no strip | `/api/priority` (free) | b8a: placement, a note, the repaint, the phone swipe | done. Differs: "N more" opens the day's rest under the strip, where Classic jumped to the columns; the strip is hidden under Your names |
| B8.6 | Released results | The strip, the list's rows and their notes | A release that is out shows what it printed where Out was (FRED's figure only when it is this release's), with the agency's headline and link when published that day, and what it is measured against (the previous print); one still waiting says Out and that its figures are on their way; a company that has reported reads in the past tense with Beat, Missed or In line (within 1%), its EPS against the estimate and the source | Same | as B8.2 | as B8.2 | `/api/priority`, `app/priority.py` from the branch | b8a; the server's rules in test_home_results | done |

### B8b. What changed, questions worth asking, the trends board
All three are new Home panels, each one Add panel away in Customize. Market Overview keeps the owner's order (2026-10-19, pinned by `tests/test_v2_navigation_layout.py`); putting any of them on it by default waits for the owner's yes.

Evidence:
- `b8b_check.py`: 12 of 12 in headless Chrome, signed in as the local owner, at 1440 and on phones at 390 and 360. Covered:
  - the preview's own briefing (free, fixed rules) and trend board, the board added through Add panel;
  - a FIXTURE briefing: five items, a held name, a link to Options' Swing setups, names still being read;
  - a question press: it drafts into Milo and nothing is sent (no `/api/chat` request).
- `tests/test_v2_parity_b8b.py`: the questions, the holdings, the briefing's rows, the board's basis line, where the panels sit.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B8.3 | What changed since yesterday | Home, "What changed since yesterday" (`home.js` `changesBlock`) | The two sessions compared, the summary; four changes and All N changes; each with its symbol once, Held when it is a holding, the detail, why it may matter (once per kind) and a button to where it shows (Chart, Earnings, Financials, Investing, or Swing setups, which opens Options at that group with the section unfolded and held in view until the reader moves); the names with no meaningful change and their moves, what could not be checked, a name with no candles, names still being read (asked once more 25 s later) | Same, 44 px | All N changes and the method fold survive the panel's repaint | No names: the server's reason | POST `/api/briefing` with the reader's names and, as symbols only, the open paper trades, the planner's holdings and a linked brokerage's (Classic sent the first two) (free; the server keeps the names asked about, with no owner) | b8b, both passes | done. Differs: one Add panel away, where Classic had it on Home |
| B8.4 | Index and sector trends | Home, "Index and sector trends" (`home.js` `trendsBlock`) | SPY, QQQ, IWM and the 11 sector funds against the prior session's range: price, Uptrend, Downtrend or Neutral (v2's words, as on Macro's board), how far from the level that matters, what would change it; the basis line (which session's levels, which print, when, who is delayed); each opens its fund; the full board on Markets | Two columns, 44 px | Refreshed with the market panels in session, repainting only when it changed | The board's reason | `/api/trends/board` (free) | b8b | done. Differs: one Add panel away; Classic's "Overnight Uptrend" is v2's "Uptrend" |
| B8.5 | Questions worth asking | Home, "Questions worth asking" (`core/market-questions.js`) | Up to five, Classic's questions word for word: the day's biggest move against its own typical day, the session when shut, the top story, a release due today or tomorrow, other moves past their typical range, then the pool rotated by the market day; each names a real figure; each a quiet button that drafts into Milo | Same, 44 px | n/a | No figures: says so | `/api/home` (already loaded; free) | b8b: drafted, nothing sent | done. Differs: one Add panel away |

### B8c. The Read on request, ticker suggestions
Evidence:
- `b8c_check.py`: 13 of 13 in headless Chrome. The Read was checked as a guest at 1440 and 390, with a FIXTURE cached Read (none yet today, then yesterday's on show); the build went to the preview's server, whose model is the STAND-IN. The suggestions were checked on Analysts at 1440 and on Compare at 1440, 390 and 360, using the preview's own search with real key and mouse events and emulated touch.
- `tests/test_v2_parity_b8c.py`.
- Not verified: a build written by the production model. That needs an authorized real-model run.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B8.7 | Today's Read built on request | The Read (`read.js` `buildRead`) | Loading the page never builds (it asks for the cached Read only). With none ready, "Build today's Read", with its cost said first: the day's moves, the calendar and the wires are gathered and an AI model writes the summary, one model call for this edition, kept and shared by every reader. With yesterday's or an aged Read on show, a quiet "Build today's Read now" or "Update it now" beside its line, with the same cost. On the press: "Building", one request, then the Read with its heading focused; when the server is still building behind an aged Read, asked again every 8 s for about two minutes, then "still being built" | Same, 44 px | n/a | A failure says so in a toast; the page keeps what it had | GET `/api/brief` without `cached` ($: one write per edition, shared) | b8c (stand-in) | done, stand-in verification. Differs: Classic built on opening the tab; v2 only on the press, and replaces its link to Classic |
| B8.10 | Ticker suggestions | Analysts' symbol box, each of Compare's boxes (`ui/typeahead.js`, a combobox) | Optic's search as the reader types, the typed text in bold; arrow keys move the highlight (said to a screen reader), Enter takes it; Enter with nothing highlighted takes a company whose name was typed, and takes a symbol as typed; Escape closes and leaves the box as typed; a click takes a row without leaving the box; Compare moves on to the next empty box; funds say so | The list stays on screen (a box at the right of the row opens it leftward); a tap takes a row; 44 px rows | n/a | Search failing: no list; the box still takes what is typed | `/api/search` (free) | b8c | done. Differs: no logos (Classic's came from two outside services keyed by each symbol typed; v2 shows no outside logos anywhere); Compare's native suggestions replaced |

## B9. Glossary and the rest
| Row | Task | Status |
|---|---|---|
| B9.1 | Glossary marking on eligible text, with hover, tap and keys; "Explain this with Milo" | open |
| B9.2 | Optic Portfolio header definitions; collapsible panels | folds done (see B9a below); header definitions with B9.1 |
| B9.3 | Financials flow-ratio chart, dividend columns, excess-return bars | done (see B9a below) |
| B9.4 | Bars inside Scan's table cells | done (see B9a below) |

### B9a. The Portfolio page's folds, Financials' charts, Scan's bars
Evidence:
- `b9a_check.py`: 8 of 8 in headless Chrome, as a guest, on the preview's own feeds, at 1440 and 390.
- `tests/test_v2_parity_b9a.py`.

| Row | Task | Where | Desktop | Phone | Keeps | States | Deps | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| B9.2 (folds) | The Optic Portfolio page's sections fold | `tracker.js` with `ui/sections.js`, which gains `open` (Classic's PANELS_OPEN_BY_DEFAULT) | Every section folds by its heading; Classic's four open at first (Optic Portfolio, Open positions, the three accounts, No trades yet), the record's detail folded; Expand all, Collapse all and Panels as on the other long pages | 44 px fold buttons | `optic.panels.open` `{"tracker\|<heading>": bool}`, Classic's key; kept across a reload | n/a | none | b9a | done. Differs: Classic's "three books" is v2's "Three simulated accounts", so a choice saved for it in Classic does not carry over |
| B9.3 | The stock against the index; dividends as columns | Financials, Corporate actions and flow (`financials.js` `extraCharts`) | The stock divided by SPY as one line from 100, the line at 100 drawn and named as even; a year's dividends a share as columns, the table folded under them; the five excess returns stay as figures | Same, fits | n/a | No dividends: says so; too little history: no line | `/api/extras/{T}?benchmark=SPY` (already loaded; free) | b9a (AAPL) | done. Differs: the excess returns are not drawn as bars; bars without their values would repeat the five figures beside them |
| B9.4 | Bars in Scan's ranked column | Scan's results (`scan.js` `rankBars`, `cellBar`) | A bar beside the figure in the ranked column, only when the rows spread by a third or more (the month's movers yes, momentum scores of 74 to 82 no): from zero either way for a signed measure, from the left for one that only runs up, a share against its whole and a percentile against 100; hidden from a screen reader, since the figure says it | The table scrolls inside its box | n/a | A missing value has no bar | none | b9a: movers, momentum, volume leaders | done |

## Not ported
| Row | What | Why |
|---|---|---|
| N.1 | Classic's section fade-in on load | The owner's motion rule: motion only in answer to an action |
| N.2 | Before-open and after-close earnings timing as a feature | Neither app has a data source (yfinance gives dates). A new source is a separate decision |
| N.3 | Pulsing live point | Replaced by a static freshness label (owner's amendment) |
| N.4 | Tab takes the placeholder question | Replaced by a "Use this example" button (keeps Tab navigation) |
| N.5 | Things Classic doesn't have: swipe between tabs, pull-to-refresh, column resize, CSV, print | Nothing to port |
