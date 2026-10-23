# Audit, Milo and motion session, 2026-10-22: handoff

- **Branch:** `audit-motion` in `~/Optic/wt-audit`, from the live build `2e90288` (the shipped roadmap).
- **Candidate:** tag `audit-rc-2026-10-23` (the commit carrying this file). **Not pushed, not deployed.**
- **Preview:** `optic-audit` launch config, http://localhost:8116, isolated data in `~/Optic/audit-data`, Milo on the
  stand-in model (:8113). Test account `audit-tester@example.test` (isolated data only, session token in that folder).
- **Tests:** full suite 6,760 passed, 1 skipped, at the candidate. 13 regression tests for this session's fixes in
  `tests/test_audit_motion_fixes.py`, plus a design-standard test for the motion system.

## What changed, with evidence

The coverage matrix (`COVERAGE.md`) lists every item as PASS, FAIL, BLOCKED or NOT TESTED, with its evidence.

1. **Financials and Earnings figures** (f39889a). Reproduced on live data:
   - SIEB showed a $0 estimate with no analysts behind it.
   - RIVN showed "+20.8% EPS growth" from a negative base.
   - RIVN showed two consensus figures for one quarter.
   - ESP's single analyst was read as agreement.
   - CRCL's average surprise read +249% because one estimate was negative.
   - The "last 8 reports" ran back to 2013.
   - "Historically precedes beats" had nothing behind it.
   - A swing from a profit to a loss was worded as a margin change.
   - RIVN printed −66.6% and −66.5% for the same margin.
   - The EPS basis was not labelled.
2. **Scenarios and Brokerage** (b33c119), reconciled with synthetic holdings by an independent script:
   - Coverage read 100% when only 1 of 5 positions was priced.
   - Names that couldn't be priced showed 0 exposure.
   - A stock with no current quote was silently valued at the broker's price.
   - The dividend yield and the option price times were missing.
   - An unpriced option, cash with no exchange rate, and a partial sync were each dropped without a word.

   Performance (TWR, XIRR, benchmark) reconciled and was left alone.
3. **Front-end defects** (bef02f9, 1139d0f):
   - The Paper Desk lost what you typed after changing the ticker.
   - The Overview trend card showed a skeleton forever when the price history failed.
   - Under Large text the Chart scrolled sideways (39 to 67 px).
   - The daily chart was missing the latest bar with no notice.
   - The watchlist and alerts accepted ZZZZQX.
   - Back lost a scroll made just before leaving.
   - Scan's row targets were 33 × 14 px.
   - AAPL's report-day pricing was missing.
4. **Milo** (372918a). See `MILO-EVAL.md`.
5. **Motion and loading** (f7490d9, e8e48b4). See below.

## Milo evaluation

A 26-case set (`milo_eval_set.json`) was driven through the real panel against the stand-in model. All plumbing checks pass after these fixes:
- the cross-company "About" line;
- unknown symbols;
- extra lookups shown as "also looked up";
- source labels;
- Stop, failure, cut-off, Ask again, copy, history, drafts and focus.

The fixes:
- **"About" line:** it now follows what the question named.
- **Unknown symbol:** "About ZZZZQX, a symbol Optic has no data for" replaces Home's MSFT.
- **Sources:** they carry their instrument and readable times, and headlines say they are headline-only.
- **Stop:** a double-click on Send no longer stops the answer.
- **Prompt:** three rules added (headlines aren't articles, percentage points aren't percent, no figures from memory).

**Blocked:** the real model's answer quality. There is no dedicated test key, and the owner's allowance was not used. The set and runner are ready.

## Motion states and timings

The tokens live in `tokens.css`, and the logic in `ui/motion.js` and `ui/milo.js`.

| Use | Token | Value |
|---|---|---|
| A control's own press | `--m-press` | 90 ms, `--ease-out` |
| Content arriving (Dossier tab body) | `--m-content` | 150 ms, opacity only |
| Drawer, panel, tab bar slide | `--m-panel` | 200 ms, `--ease-drawer` / `--ease-out` |
| Anything leaving | `--m-exit` | 130 ms |

- **Page line:** a thin gold line under the top bar, shown only while a skeleton is on screen. It appears after 220 ms, so fast loads never flash, and stops when work completes or fails.
- **Milo** shows only states backed by an event:
  - **submitted:** "Sending your question"
  - **preparing:** after the server accepts the request
  - **retrieving:** the server's own tool words
  - **streaming:** text arriving, with what was looked up listed as it arrives
  - **complete, stopped or failed:** the activity line runs from Send until one of these.
  - The question you sent enters once, at 150 ms. Scout is unchanged.
- **Dossier tabs:** the bar slides and the body fades, between tabs of one symbol only. A new symbol keeps its own skeleton. There are no full-page fades.
- **Reduced motion** (verified): no tab or content motion; the line stands still at full width and 55% opacity; the drawer appears at once.

## Screenshots

`~/Optic/work/audit-motion-2026-10-22/shots/`:
- `rehearsal-{desktop,phone}-*` (Home, Overview, Financials, Earnings, Chart, Milo working, Milo done)
- `a11y-*` (light theme, Large text, 200% zoom, landscape)
- `milo-390.png`, `s5/s6/s7` from earlier stages

## Limits

- **Devices:** viewport emulation in Chromium at 360, 390, 430, 768 and 1440, plus 844 × 390 and 720 × 450. No physical iPhone Safari or Android Chrome, and no touch gestures or software keyboard: device access is not authorised here.
- **Market data:** Yahoo had not published the Oct 22 daily bar at the time of testing, so daily figures end Oct 21; the chart now says so.

## Before Monday

- **This branch is not live.** Live is `2e90288`. Shipping `audit-rc-2026-10-23` needs the owner's go-ahead, then a fast-forward of origin/main and a check of the live deploy.
- **Rehearse on whichever build is live,** and say which one. These results are for this candidate only.
- **Open decisions:**
  - a dedicated key for the real-model Milo run;
  - whether the desktop drawer should block background clicks.
