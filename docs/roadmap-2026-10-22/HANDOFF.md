# Roadmap, 2026-10-22: handoff

Branch `roadmap` in `~/Optic/wt-roadmap`, on top of the live build (origin/main 04bbffd, the pitch fixes).
**Not pushed and not deployed.** The Monday pitch build is `pitch-rc-2026-10-22` / live 04bbffd; keep this
branch out of production until after the pitch and until each part has been looked at.

| Stage | Where it lives | Commit |
|---|---|---|
| 1. Audit corrections | Already live in 04bbffd (pitch-fixes) | 04bbffd |
| 2. Contract Picker | Options, Contracts and pricing (`#/SYM/options`) | e8418f3 |
| 3. Connected trade journal | Paper Desk: plan frozen at entry, revisions, review | 21e2df6 |
| 4. Research exports | Dossier, Export: printable two-page sheet (`#/SYM/sheet`) | f2a6e87 |
| 5. Nightly setup shortlist | Scan, third mode "Shortlist" (`#/scan?mode=shortlist`) | 9198b32 |
| 6. Portfolio scenarios | Optic Portfolio (after Book-level risk) and Brokerage, Holdings & Exposure | d85a2f1, 2a13e9f |
| 7. Learning replays | Paper Desk, "Replay a past decision" (`#/paper?replay=ID`) | 00e9e53 |

Full suite at 00e9e53: 6,744 passed, 1 skipped.

## Decisions waiting on the owner

1. **Brokerage scenarios vs the what-if lab.** On 2026-10-20 the owner removed the Brokerage what-if lab
   ("remove this feature entirely, useless"). Stage 6 adds something different: no tab, no form of
   hypothetical trades, a read-only section inside Holdings & Exposure that revalues the holdings as they
   stand. The removal test now pins the lab's own pieces (its tab, its form, `POST /workspace/scenario`)
   instead of the word "scenario". If the owner does not want scenarios on Brokerage at all, remove the
   `scenariosSection` call and the `scenarios` extra in `static/v2/js/pages/brokerage.js`; the Optic
   Portfolio section stands on its own.
2. **`SHORTLIST_AUTO` defaults to on.** After deploy the server builds the shortlist once per completed
   session: one two-year batch history for 87 symbols plus up to 15 news reads, about 40 s, no model call.
   Set `SHORTLIST_AUTO=false` to keep it off until wanted.

## What each stage does, and its limits

**Shortlist (5).** `app/shortlist.py`, rule version `shortlist-2026-10-22.2`: a setup qualifies when it
triggered on the last completed session with every condition met, or armed that session with all but the
trigger; one per name; at most 15, the rest named. Universe is Optic Portfolio's 86 curated names. No quota:
an empty list says so. Every stored list gets outcomes ten sessions later, failures included, shown as a
forward record that says it is not a backtest. The record is empty until ten sessions after the first list.

**Scenarios (6).** `app/analytics/scenarios.py`, one engine for both views; full revaluation with the
Options tab's pricer. Exposures kept apart: premium at risk, premium taken in (uncovered calls named),
gross and net notional, delta-adjusted, concentration, correlated groups (with the note that calm-market
correlation is not crisis protection), gamma, vega and theta. Positions it cannot price are listed with the
reason; stale prices are flagged. Closing cost at bid and ask is shown only where quotes exist (Brokerage
sends none). The classic app is unchanged. Optic Portfolio's books have no open positions right now, so
its section appears only once a trade opens. Brokerage was verified on the sandbox only.

**Replays (7).** `app/replays.py`. The server sends bars only up to the cursor; the setup reading is the
engine run on the history cut at that close. Six entries (NVDA Jan 2024, SPY Mar 2024, META Jan 2022,
AAPL Feb 2025, JPM Mar 2024, XOM Mar 2023), picked by `work/roadmap-2026-10-22/replays/pick_library.py`
from 2,790 confirmed flags, each re-checked at its decision close. Daily price and volume only; prices
are split-adjusted, and the review says so per name. Decisions live in the reader's browser
(`optic.v2.replay.v1`).

## How it was checked

- Preview `optic-roadmap` (:8114, data `~/Optic/roadmap-data`) for Scan, Paper Desk and replays.
- Preview `optic-roadmap-fixture` (:8115, data `~/Optic/roadmap-fixture-data`): sandbox brokerage, a demo
  reader, and six fixture positions in Optic Portfolio's aggressive book, built by
  `~/Optic/work/roadmap-2026-10-22/fixtures/stage6_fixture.py`. Its session was revoked after the check;
  rerun the script for a new one.
- Widths 1440, 768, 430, 390 and 360 for every new section: no sideways scroll, controls 44 px.
  Screenshots in `~/Optic/work/roadmap-2026-10-22/shots/` (s5-*, s6-*, s7-*).
