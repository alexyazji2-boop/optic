# Migration sequence: every remaining capability into v2

Stage 0, 2026-10-18. Classic is a temporary bridge, not the destination. Each milestone below moves a group of Classic-only or incomplete capabilities (CAPABILITY-MATRIX.md) into v2 and ends with acceptance checks run against the real local server. Nothing is decluttered away: a capability that does not belong on a page's first screen goes to a secondary view, a drawer or an "Advanced" section, and the matrix records where.

**Every milestone must pass the same baseline checks:**
- the v2_check audit at 0 faults on the affected views, desktop and phone, light and dark;
- the full test suite green;
- the paid-call probe: 0 message calls on page load;
- the data round trip in both directions for any key or endpoint the milestone writes;
- the page's notice and legal footer still present;
- no em dashes in user-facing copy, and names in the rail and phone bar unchanged.

## Sequence from 2026-10-18 (TapeDash direction)
Order of work. Each step is local or staging until the owner approves a deploy; Classic stays the bridge throughout. **The next deploy, when approved, is a private preview only** (PREVIEW-PACKAGE.md); public rollout follows visual acceptance, functional verification and the migration requirements below.

1. **Owner decisions, made 2026-10-18:** X1 accepted (v2 opens dark); X2 rejected (navigation is never repeated: the sidebar lists destinations, a destination's tabs are its views); X3 resolved (Home is the workspace, with Market Overview as its default layout and My Desk as the reader's saved one).
2. **W0 and W1:** the dark system and Home as the workspace, built locally on `v2-dark-workspace`. The owner reviews the real experience in the preview before any further features; they join the private preview only with the owner's approval.
3. **M1, advanced charting:** the largest Classic-only area, including C18's free chart read. MSB is already built as a new study.
4. **W2 and M6:** the notifications bell, with alert filters, "Why this fired" and the owner controls.
5. **M3 with W3 and W4:** research tools, guided contract comparison and the ranked setups view.
6. **M4 with W4's archive:** the track record, after the `validation` branch.
7. **M2:** valuation editors.
8. **M5:** the remaining Milo features, after the Milo branches.
9. **M7 with W6 and W7:** the restored extras, glossary tooltips (C17), the financial charts and the report archive.
10. **M8:** fit and finish, including performance targets T2 and T6 and a production measurement.
11. **M9:** the switch and retirement, each step a separate approval.

New products P1 to P12 (NEW-PRODUCTS.md) are outside this sequence. Each needs its own data decision and budget.

## M1. Advanced charting
**Scope:**
- **Drawing tools:** channel, Fib extension, pitchfork, arrow, ruler, risk box and position sizing, plus snap and moving a drawing.
- **Studies:** EMA clouds 9/21 and 21/50, MA Trend, TSO, VWAP, Keltner, Donchian, regression, stages, accumulation zones, auto trends, VBP, zones, sessions and insider marks.
- **Chart chrome:** colours, legend, full screen and the navigator. Built 2026-10-19 (C12, `pages/chart-chrome.js`), in the classic keys for the colours and the legend.
- **Weekly structure** (Investing): candles, the levels menu and pan.
- **The 18 chart widgets:** each becomes a v2 side panel. Built 2026-10-19 as a rail beside the plot rather than the "Tools" drawer first planned, because the owner asked where the side widgets had gone: the rail is where the classic app shows them. The default chart stays uncluttered because nothing is open until the reader opens it.

**Acceptance:**
- **Study values:** each study's series matches Classic's on the fixture day (`work/hover-fix/fixtures`) within 1e-6, compared numerically from both apps' computed arrays, not by eye.
- **Drawings:** every Classic drawing kind round-trips through `optic.chart.drawings.v2`, and moving or deleting one in either app shows in the other.
- **Input:** touch drags on a phone (synthetic events, per the browser-pane gesture notes), and keyboard reading of every study.
- **Chart height:** no drift on resize (the hig-pass finding).
- **Widgets:** each one opens, closes and returns focus.

## M2. Valuation editors
**Scope:** the DCF editor, saved models, the other methods (RI, FFO, DDM, comps, SOTP) and valuation Milo. In v2 these sit behind "Edit the model" on Investing; the summary stays the default view.

**Acceptance:**
- **Outputs:** for the six fixture companies, outputs equal valuation.js to the cent.
- **Round trip:** save in v2 and open in Classic, then the reverse, for both `optic.dcf.v1` (guest) and the server's saved models (signed in).
- **Isolation:** account isolation holds for saved models.
- **Milo:** a valuation question carries the model (the budget fix from milo-valuation-context).

## M3. Research tools
**Scope:**
- **Dossier:** the thesis check; the Optic Score (short term); Factors and What to look at next; the Fund view for ETFs; and the rest of Advanced research (Pulse score, all statistics, the rest of the ticker), in an "Advanced" section on the Overview.
- **Earnings this week:** a page with no symbol, under Dossier, Earnings.
- **Swing setups:** filters, rule settings, back-tests and setup alerts.

**Acceptance:**
- **Figures:** same figures as Classic on the fixture day.
- **Thesis:** a saved thesis round-trips between the apps (`optic.thesis.v1` and the server).
- **Setup alerts:** created in v2, they fire in the scheduled scan and show in both apps' Alerts.
- **ETFs:** the Fund view replaces the framework, as in Classic.

## M4. Track record and signal history
**Scope:**
- **Integrate the validation branch first** (BRANCH-REVIEW.md).
- **Then:** the track record slots on Options and Investing, and Signal history on Alerts (`historyText`, `historySlot`, `trackRecordText`, `trackRecordForward`).

**Acceptance:**
- **Report agreement:** the same statements as the validation report.
- **No overclaiming:** no wording that claims Optic is validated (the validation protocol forbids it).
- **Milo:** `track_record` is in Milo's context for does-it-work questions.

## M5. Remaining Milo features
**Scope:**
- **Panel features:** attachments, the web search toggle, research mode and the research pack, suggested questions and a resizable width on desktop.
- **Scout:** the mascot.
- **Per-panel Ask chips** that carry the panel's own figures.
- **Order:** the Milo branches from BRANCH-REVIEW.md land first, so v2 is built against the final tools.

**Acceptance:**
- **Stubbed-stream tests:** each feature tested through a stubbed stream, as in Stage 0.
- **Labels:** web and research calls are labelled as paid where they are.
- **Allowance:** counted correctly.
- **Attachments:** size and type limits enforced the same as Classic.
- **No paid calls on load:** the probe stays at 0 with every feature switched on.
- **Context:** stays correct after navigation, re-checked with the AAPL-to-MSFT test.

## M6. Alerts and owner tools
**Scope:**
- **Scheduled-scan alerts:** kind filters, unread only, and "Why this fired".
- **Owner controls:** mark read, clear all and e-mail delivery.

**Acceptance:**
- **Alerts round trip:** an alert marked read in v2 shows as read in Classic, and the reverse.
- **Owner-only:** the owner controls are hidden from, and refused for, other accounts (server check, not only hidden).

## M7. Decluttered extras restored as secondary views
**Scope:**
- **Home:** the catalyst day strip, What changed since yesterday, and the index and sector trends board, in a "More from today" section folded by default (its state kept per browser); the Desk scenarios and today's reports, in the Desk's full read.
- **Dossier:** the Weinstein stage chip, beside the long-term score.
- **Optic Portfolio:** header tooltips and collapsible panels.
- **Scan:** in-cell bars.
- **Financials:** the flow ratio chart.
- **Home's What Matters Today:** released results, with the home-released-results branch.

**Acceptance:**
- **Placement:** each item is reachable in at most two steps from its page, and listed in the matrix with its new place.
- **Accessibility:** folded sections are keyboard and screen-reader operable.
- **First-screen budget:** Home's first screen word count does not grow beyond the Stage 0 baseline.

## M8. Fit and finish
- **Classic findings:** table column alignment and chart height drift (hig-pass).
- **Zoom and devices:**
  - 200% zoom on every page;
  - real iOS Safari on the iOS 27 simulators (audit.js and the replay server);
  - the SE at 549px tall.
- **Load budget:** v2's cold-load module bytes must stay within 10% of the Stage 0 figure in STAGE0-EVIDENCE.md, measured with the same throttled profiles.
- **Performance targets T1 to T7 in PERFORMANCE.md, all met** (9 runs per cell, same throttling). Two were open on 2026-10-18:
  - **T2:** the phone warm Dossier, 0.92 s against Classic's 0.80 s.
  - **T6:** the spread on desktop cold Home. The slow request has to be found first.
- **A production measurement** from the owner preview.

## M9. Default switch and Classic retirement

1. **Owner-only preview on production** (separate approval): `OPTIC_V2_ACCESS=owner` (also what unset means; any unreadable value means `off`), `OPTIC_DEFAULT_UI=classic`. The package is PREVIEW-PACKAGE.md. The emergency shutdown at every stage is `OPTIC_V2_ACCESS=off`. The owner uses v2 at `/v2/` with the checklist in PREVIEW-PROPOSAL.md.
2. **Opt-in for everyone** (separate approval): `OPTIC_V2_ACCESS=all`. Classic's footer offers "Try the new design"; v2's offers "Use the classic app".
3. **v2 as the default** (separate approval), only after M1 to M8 pass: `OPTIC_DEFAULT_UI=v2`. Classic stays at `/classic` and through the cookie.
4. **Observation period:** at least four weeks with v2 as the default. Problem reports are triaged weekly, and no Classic-only capability remains in the matrix.
5. **Retire Classic** (separate approval), only when both hold:
   - every retained capability is migrated and verified;
   - the observation period is complete.

   Elapsed time alone is never enough. Retirement keeps `/classic` serving a notice with links to the v2 equivalents for one more release.
