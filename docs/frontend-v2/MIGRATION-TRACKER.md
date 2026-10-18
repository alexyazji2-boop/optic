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
| C11 | Chart studies | 14 studies (EMA clouds through insider marks) | M1 | open |
| C12 | Chart widgets and chrome | 18 widgets; colours, legend, full screen, navigator | M1 | open |
| C13 | Valuation editors | DCF editor, saved models, RI, FFO, DDM, comps, SOTP, valuation Milo | M2 | open |
| C14 | Earnings this week | the page with no symbol | M3 | in progress: the workspace panel lists this week and next with consensus and on-request implied moves; the standalone page and before-open/after-close timing are open |
| C15 | Signal history | Alerts | M4 | open |
| C16 | Alerts owner controls | mark read, clear all, e-mail delivery | M6 | open |
| C17 | Glossary tooltips and Learn widget | dotted-underline definitions (`app.js:433-573`), the Learn widget. Missing from the matrix until the 2026-10-18 audit | M7 | open |
| C18 | Free chart read | Classic's deterministic "Chart read" popover (`app.js:23060-23135`); v2's only read is the paid Milo one | M1 | open |

## By milestone
| Milestone | Rows | Status |
|---|---|---|
| M1 Advanced charting | I6, C10, C11, C12, C18 | open (MSB added as a new study, 2026-10-18) |
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
| W0 | Dark visual system, expandable sidebar, workspace button | built in preview (`v2-dark-workspace`), owner decisions X1 to X3 pending |
| W1 | Research workspace: presets, panels, linking, persistence | built in preview; 45 interaction checks; audit 0 faults |
| W1a | Market Structure Break study on the chart | built; unit test; browser check |
| W2 | Notifications bell (I11) | open |
| W3 | Guided contract comparison, without a composite grade | open |
| W4 | Ranked setups view with a dated archive and the four outcome figures | open (archive needs M4) |
| W5 | Alert timeline | open (needs update events recorded) |
| W6 | Fundamentals checklist and the XBRL financial charts | open |
| W7 | Daily and weekly report archive | open |
