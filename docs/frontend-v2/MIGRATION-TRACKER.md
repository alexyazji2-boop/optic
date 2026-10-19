# Migration tracker: the 29 open capabilities

Kept current as each milestone lands. Source of truth for status: this file. The rows come from CAPABILITY-MATRIX.md (11 incomplete, 18 Classic-only after the TapeDash audit of 2026-10-18, FEATURE-AUDIT.md), and each milestone's acceptance checks are in MIGRATION.md. A row closes only when its acceptance checks pass against the real server, and both the matrix and this file are updated in the same commit. **The rebuild is not complete while any row is open.**

**Status values:**
- **open:** not started.
- **in progress:** work has started.
- **verified:** the acceptance checks passed. The date and the commit go in Notes.

## Incomplete in v2 (11)
| # | Capability | What is missing | Milestone | Status |
|---|---|---|---|---|
| I1 | Per-panel Ask Milo | The panel's own figures in Milo's context (where it was asked from is sent since Stage 0) | M5 | open |
| I2 | What Matters Today | Released results (needs the home-released-results branch) | M7 | open |
| I3 | Optic Desk | Scenarios and today's reports | M7 | open |
| I4 | Advanced research (Overview) | Pulse score, all statistics, the rest of the ticker | M3 | open |
| I5 | Swing setups | Filters, rule settings, back-tests, setup alerts | M3 | open |
| I6 | Weekly structure (Investing) | Candle style, levels menu, pan | M1 | open |
| I7 | Financials | The flow ratio chart | M7 | open |
| I8 | Scan | In-cell bars | M7 | open |
| I9 | Optic Portfolio | Header tooltips, collapsible panels | M7 | open |
| I10 | Alerts | Kind filters, unread only, "Why this fired" | M6 | open |
| I11 | Notifications | A bell with the unseen count (the backend counts exist; Classic shows a phone badge) | W2 | open (found 2026-10-18) |

## Classic-only (18 groups)
| # | Group | Items | Milestone | Status |
|---|---|---|---|---|
| C1 | Milo attachments | `#chat-attach` | M5 | open |
| C2 | Milo web search toggle | `#chat-web` | M5 | open |
| C3 | Milo research mode and pack | `#chat-research` | M5 | open |
| C4 | Milo suggestions and panel width | `#chat-suggest`, the resizable panel | M5 | open |
| C5 | Scout | the mascot | M5 | open |
| C6 | Home extras | catalyst day strip, What changed since yesterday, index and sector trends board | M7 | open |
| C7 | Overview extras | Optic Score (short term), Factors and What to look at next, Fund view; Weinstein stage chip | M3; M7 for the chip | open |
| C8 | Thesis check | Dossier thesis form and check | M3 | open |
| C9 | Track record slots | Options and Investing | M4 | open |
| C10 | Chart drawing tools | channel, Fib extension, pitchfork, arrow, ruler, risk box, position sizing, snap, moving | M1 | open |
| C11 | Chart studies | 14 studies (EMA clouds through insider marks) | M1 | in progress: insider marks verified 2026-10-19 (arrows on the price with a box naming each trade, `ui/pricechart.js` and `pages/chart-widgets.js` `insiderMarks`, browser check at 1440 and 390); the other 13 are open |
| C12 | Chart widgets and chrome | 18 widgets; colours, legend, full screen, navigator | M1 | verified 2026-10-19: the 18 widgets (`pages/chart-widgets.js`, `tests/test_v2_chart_widgets.py`, commit 724b705) and the chrome: colours, the legend, full screen and the navigator (`pages/chart-chrome.js`, `ui/pricechart.js`, `tests/test_v2_chart_chrome.py`), each checked at 1440, 1024 and 390 against the local server, signed in (112 of 112), and the widget sweep at five sizes |
| C13 | Valuation editors | DCF editor, saved models, RI, FFO, DDM, comps, SOTP, valuation Milo | M2 | open |
| C14 | Earnings this week | the page with no symbol | M3 | in progress: the workspace panel lists this week and next with consensus and on-request implied moves; the standalone page and before-open/after-close timing are open |
| C15 | Signal history | Alerts | M4 | open |
| C16 | Alerts owner controls | mark read, clear all, e-mail delivery | M6 | open |
| C17 | Glossary tooltips and Learn widget | dotted-underline definitions (`app.js:433-573`), the Learn widget. Missing from the matrix until the 2026-10-18 audit | M7 | in progress: the Learn widget is on the Chart page (2026-10-19, the glossary copied word for word and compared by test); the tooltips are open |
| C18 | Free chart read | Classic's deterministic "Chart read" popover (`app.js:23060-23135`) | M1 | verified 2026-10-19: `ui/chartread.js` on the Chart page's toolbar, the classic model and words, no model call; browser check at 1440 and 390 |

## By milestone
| Milestone | Rows | Status |
|---|---|---|
| M1 Advanced charting | I6, C10, C11, C12, C18 | open (MSB added as a new study, 2026-10-18; C18 verified 2026-10-19; C12 verified 2026-10-19, its 18 widgets and its chrome) |
| M2 Valuation editors | C13 | open |
| M3 Research tools | I4, I5, C7 (not the chip), C8, C14 | open |
| M4 Track record | C9, C15 (after the validation branch) | open |
| M5 Remaining Milo | I1, C1 to C5 (after the Milo branches) | open |
| M6 Alerts and owner tools | I10, C16 | open |
| M7 Extras restored | I2, I3, I7, I8, I9, C6, C7's stage chip, C17 | open |
| M8 Fit and finish | audit, zoom, iOS Safari, bundle and performance targets | open |
| M9 Switch and retirement | needs M1 to M8 verified; each step a separate approval | open |

## Redesign release R1: new frontend work (not migration)
Built on existing data only (NEW-PRODUCTS.md). Status is updated here as each item lands.

| # | Item | Status |
|---|---|---|
| W0 | Dark visual system, sidebar of destinations only, one page system | built locally (`v2-dark-workspace`); X1 accepted, X2 rejected and reverted, X3 resolved (2026-10-18); awaiting the owner's review of the real experience |
| W1 | Home as the research workspace: layouts, panels, linking, persistence, phone priority, freshness per panel | built locally; 52 Home checks and 18 walkthrough checks, each passing cold (straight after a restart) and cached; v2_check audit 0 faults on its 20 captures (5 Home views, desktop and phone, dark and light) |
| W1a | Market Structure Break study on the chart | built; swing formed vs swing known shown apart; prefix-stability test (a later bar never changes a recorded break); browser check |
| W2 | Notifications bell (I11) | open |
| W3 | Explainable contract suitability ranking on criteria the reader chooses (the transparent, sortable comparison is already built) | open; needs its method note |
| W4 | Ranked setups view with a dated archive and the four outcome figures | open (archive needs M4) |
| W5 | Alert timeline | open (needs update events recorded) |
| W6 | Fundamentals checklist and the XBRL financial charts | open |
| W7 | Daily and weekly report archive | open |
