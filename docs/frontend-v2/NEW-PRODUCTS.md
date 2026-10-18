# What the redesign delivers, and what would be new products

The TapeDash reference mixes two kinds of feature:
- **Interface:** presenting data Optic already has.
- **New products:** these need data, calculations, storage and operations that Optic does not have.

A redesign builds the first kind. It cannot create the second. This file keeps the two apart, so that no screen implies data Optic does not hold.

## Rules for every surface (redesign or product)
- **No proxy shown as the real thing.** A proxy is never presented as live execution data. Optic's "most active contracts" comes from one option-chain snapshot (volume and open interest); it is labelled so. FINRA off-exchange short volume is labelled short volume, never "dark pool prints".
- **No invented figures.** No win rate, probability, grade, live status or performance record is invented. A figure appears only when a stored, reproducible calculation produced it, and its method is one click away.
- **Outcomes are kept apart.** Wherever an idea, signal or alert shows an outcome, these four are separate figures, never merged into one "win":
  - **target touched:** whether, and when, price reached the target;
  - **peak excursion:** the best move before expiry, stop or exit;
  - **current return:** from entry to now, for an open idea;
  - **realised or simulated exit return:** from entry to the recorded exit, saying which it is.
- **Nothing hidden.** Losses, open signals, sample sizes, the timestamps of entry and exit, and the methodology stay visible next to any summary.
- **Paid model calls stay deliberate:** a labelled button, under the existing allowance (the paid-call probe stays at 0 on load).

## Release R1, the redesign (frontend only, existing data)
These need no new feed. The workspace preview is the first piece.

| Item | Status | Data it uses |
|---|---|---|
| Dark visual system, expandable sidebar, compact top bar | Built (preview) | n/a |
| Workspace: presets, panels, linking, persistence | Built (preview, 45 checks) | existing APIs |
| Market Overview panels (indices, regime, sentiment, expected move, heatmap, calendar with actual and prior, earnings week with implied move on request, movers, watchlist, quote and chart, news, economy) | Built (preview) | existing APIs |
| Options Research panels (contracts at one expiry with Optic's liquidity label, no grades) | Built (preview) | `/api/options/{t}/research` |
| Market Structure Break on the chart | Built | bars Optic already loads |
| Guided contract comparison (direction, holding period, budget, optional target → contracts compared on spread, liquidity, delta, expiry fit, time decay and earnings exposure, each shown separately) | Planned, W3 | the existing contract table. **No composite grade:** Optic's research decided against a ranking (`contracts.py:1-12`), and changing that is an owner decision with its own method note |
| Ranked setups view: trigger, invalidation, target, timeframe, R:R, evidence, status, and a dated archive showing the four outcome figures | Planned, W4 | the existing setups and paper ledger. The archive needs the outcome store from the `validation` branch |
| Alert timeline: signal, entry conditions, updates, stop and target changes, close, with times | Planned, W5 | the existing alerts and ledger, plus recording update events (a small backend change) |
| Notifications bell with unseen count | Planned, W2 | the existing unseen counts |
| Fundamentals checklist; financial charts for capex, SBC, buybacks, interest, FCF; buyback against dilution | Planned, W6 | the existing payload and XBRL fields. Receivables, opex breakdown and debt maturities need more XBRL tags, which is ingestion, not a feed |
| Daily and weekly report archive | Planned, W7 | the existing `/api/desk/editions` and the weekly store |
| Every Classic capability (M1 to M8) | Tracked in MIGRATION-TRACKER.md | existing |

## Later products: each needs its own decision, data and budget

| # | Product | Feed or data required | Historical coverage | Method to define | Storage | Operating cost and duties |
|---|---|---|---|---|---|---|
| P1 | **True options flow:** unusual prints, sweeps and blocks, market tide, DTE tide, flow search, flow map | OPRA trades with condition codes and the NBBO at each trade (aggressor side). Opening vs closing needs Cboe Open-Close or ISE Trade Profile | at least 1 year to set "unusual" baselines | sweep and block detection, the aggressor rule, the premium floor, de-duplication of multi-leg trades | every trade of the day (tens of millions of rows); a rolled-up store per contract and day | **Feed:** Databento OPRA from about $199 a month. **Open-close data:** Cboe Open-Close about $3,000 a month. **Licence:** OPRA vendor agreement and display fees (finding F15). **Engineering:** intraday ingestion and monitoring |
| P2 | **Tracked flow and signal outcomes** (a "golden flow" style record) | P1, plus option quotes over each signal's life | from the start of recording; nothing back-filled unless bought | entry price rule, the four outcome figures above, how expiries settle | one row per signal, plus a quote history | P1's costs, plus a published methodology page; the history must never be edited |
| P3 | **Dark-pool prints and levels** | a licensed equities trades feed with TRF/ADF prints | 1 year | print size and venue filters; what makes a "level" | every off-exchange print | an equities trades licence (SIP, or a vendor such as Polygon or Databento). FINRA's free ATS data cannot do this (weekly, 2 to 4 weeks late) |
| P4 | **Economic consensus** | a licensed economic-calendar feed | 2 years for surprise history | how surprise is defined | per release | the licence; FRED cannot supply it |
| P5 | **True market breadth** (A/D line, new highs and lows, McClellan, put/call) | exchange breadth and Cboe put/call statistics | 5 years | the standard formulas | daily | the licence |
| P6 | **ETF flows** | daily shares outstanding or creations and redemptions | 2 years | flow = Δshares × NAV | daily per fund | issuer files (scraping) or a vendor |
| P7 | **Historical replay and chart drills** | intraday bars (and P1 for flow replay) for the sessions offered | the replay library | grading rules for a reader's decisions, which must be fair and documented | sessions plus each reader's attempts | **Model:** a learning product with its own design. **Grading:** needs review before any score is shown |
| P8 | **Structured lessons (academy)** | none | n/a | lesson content, links from each metric to its lesson, checks of understanding | lessons plus each reader's progress | **Content writing and review:** the largest cost. **Starting point:** the Classic glossary (C17) |
| P9 | **Skill ratings, challenges, leaderboards, funded challenges** | P7 | n/a | the rating model | ratings history | **Prerequisite:** only after P7 grading is reliable. **Funded challenges:** bring money handling, terms and regulatory questions, so they need legal review first |
| P10 | **Squawk (audio)** | a real-time news wire licensed for redistribution, or a human squawk service | n/a | n/a | n/a | the licence and real-time operations |
| P11 | **Community** | none | n/a | moderation policy | posts and reports | **Ongoing:** moderation, abuse handling and terms (L1). **Priority:** low until R1 is complete |
| P12 | **Senate trades** | efdsearch.senate.gov (form-gated, fragile scraping) or a vendor such as Quiver | 2 years | n/a | per filing | scraping upkeep, or a vendor fee |

**None of P1 to P12 is in the redesign.** Their panels do not appear until their data exists. The panel catalogue has no place-holder "coming soon" flow table.
