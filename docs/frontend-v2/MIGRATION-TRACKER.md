# Migration tracker: the 26 open capabilities

Kept current as each milestone lands. Source of truth for status: this file. The rows come from CAPABILITY-MATRIX.md (10 incomplete, 16 Classic-only on 2026-10-18), and each milestone's acceptance checks are in MIGRATION.md. A row closes only when its acceptance checks pass against the real server, and both the matrix and this file are updated in the same commit. **The rebuild is not complete while any row is open.**

**Status values:**
- **open:** not started.
- **in progress:** work has started.
- **verified:** the acceptance checks passed. The date and the commit go in Notes.

## Incomplete in v2 (10)
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

## Classic-only (16 groups)
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
| C11 | Chart studies | 14 studies (EMA clouds through insider marks) | M1 | open |
| C12 | Chart widgets and chrome | 18 widgets; colours, legend, full screen, navigator | M1 | open |
| C13 | Valuation editors | DCF editor, saved models, RI, FFO, DDM, comps, SOTP, valuation Milo | M2 | open |
| C14 | Earnings this week | the page with no symbol | M3 | open |
| C15 | Signal history | Alerts | M4 | open |
| C16 | Alerts owner controls | mark read, clear all, e-mail delivery | M6 | open |

## By milestone
| Milestone | Rows | Status |
|---|---|---|
| M1 Advanced charting | I6, C10, C11, C12 | open |
| M2 Valuation editors | C13 | open |
| M3 Research tools | I4, I5, C7 (not the chip), C8, C14 | open |
| M4 Track record | C9, C15 (after the validation branch) | open |
| M5 Remaining Milo | I1, C1 to C5 (after the Milo branches) | open |
| M6 Alerts and owner tools | I10, C16 | open |
| M7 Extras restored | I2, I3, I7, I8, I9, C6, C7's stage chip | open |
| M8 Fit and finish | audit, zoom, iOS Safari, bundle and performance targets | open |
| M9 Switch and retirement | needs M1 to M8 verified; each step a separate approval | open |
