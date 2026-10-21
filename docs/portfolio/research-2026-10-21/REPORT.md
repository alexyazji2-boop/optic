# Optic entries, exits and portfolio management: research report

2026-10-21. Branch `portfolio-triggers` in `~/Optic/wt-portfolio` (from origin/main 2728171), commits 2750801
(the five approved book rules) and d5235c9 (the repairs and the research watch). Nothing pushed or deployed. This
folder holds the plan (PROTOCOL.md, hashes in PROTOCOL.registered), the decisions sealed before the final period
(DECISIONS-validation.md), the factor inventory (FACTORS.md) and the comparison tables. The research code, frozen
data and every result file are on the owner's machine in `~/Optic/work/research-round-2026-10-21` (`harness/`,
`data/`, `results/`, `log/experiments.jsonl`).

## The answer

**No validated strategy found.** Four price setups (trend pullback, breakout and retest, failed breakdown, range
reversion) were tested with and without a confluence requirement, and two earnings setups (continuation and
reversal) on top. All of it was pre-registered and run on 1993-2026 history: 43 funds and 40 large stocks, three
chronological periods, costs charged, against single-factor and random-entry controls. None passed. Requiring two
independent supporting categories did not improve any setup; in fund pullbacks it made results significantly worse.

One lead is worth a next round. After an earnings release whose reaction beat SPY by 3 points or more, buying the
next open earned +0.33R a trade in 2013-2018 (t 2.45, 164 trades) and +0.31R in 2019-2026 (t 2.87, 293 trades),
after costs. It is a single-factor rule on survivor-biased stocks. Its confluence version did worse, so it does not
meet the multiple-confluence standard and is not promoted.

The safeguards in the approved book rules held up: long only, a gross cap, a stop floor, one position per idea, and
costs. Three more are now on the branch: options paused, exposure counted by what it moves, and an event-cluster
cap. Lower risk per trade and an unleveraged ceiling were then approved and built.

## 1. Audit of the current logic

* **The books' entry is the swing composite** (technicals 0.34, gamma 0.24, flow 0.20, news 0.12, macro 0.10). Only
  its technical part can be replayed, and the validation program found no edge in it. Gamma, flow and news have no
  history. The ledger is the composite's only test, and it has lost in both records so far (Aggressive -9.7% in
  September, -7.95% from 2026-09-29).
* **Factors, as coded** (FACTORS.md): dealer gamma, walls and VEX assume dealers are long every call and short every
  put. Open interest says nothing about who holds what, so these are models, not observed positions. VEX is that
  sign times vanna times open interest. Options flow has no trade side ("no true bid/ask side per print", flow.py).
  Support and resistance levels repaint: in 223 of 240 sampled windows a level was gone five sessions later. The
  regime's "breadth" is labelled sectors above their 200-day but computed as sectors up today. The earnings move
  never receives the report's timing.
* **Forward record of Optic's own reads:** the signal archive holds 197 reads over 6 days (live, 2026-10-21), only
  for names somebody opened. Far too few to test anything.

## 2. Factor inventory and coverage

See FACTORS.md for definitions, sources, refresh, timestamps, missing-data behaviour and limits. In short:

| Evidence category | On history | Forward only | Collected now by |
|---|---|---|---|
| Price structure, momentum, participation | yes (daily bars) | | research watch (every setup daily) |
| Market and sector context | yes | | research watch |
| Earnings timing and reaction | yes, from SEC 8-K acceptance times (3,681 releases since 2003) | estimates and consensus | research watch, observations.db |
| Options flow, GEX, flip, walls, VEX, IV verdict | no (DoltHub has quotes but no OI or volume) | yes | research watch (every trigger), signal archive (opened names) |
| News, macro calendar | no | yes | research watch (snapshot), catalysts table |
| Option prices | partly: DoltHub bid/ask, weekly snapshots in 2019, daily later | | research watch keeps the recommended contract |

## 3. Specifications

The full rules (entry, categories, catalyst policies, stops, exits, sizing, costs, state progression, missing-data
behaviour, cooldown) are PROTOCOL.md. The live version is `app/research_book.py`, rules `rb-2026-10-21`. It matches
the harness on 2,762 trigger days and 516 shadow trades. States run watching → armed → triggered → shadow trade
(intended → open → closed, or skipped). A trigger counts on its first bar only. A signal is unique by rules, symbol,
setup and date, so repeated scans cannot duplicate it, and there is a five-session cooldown after each trade.

## 4. Research log

| Run | What | Result |
|---|---|---|
| PT-1 (registered) + addenda A-C | The books' trade rules replayed, 58 symbols, 1993-2026 | Old rules lost in every period for every book. Long only, stop floor and gross cap helped (earlier report) |
| PT-1 addendum D | Risk per trade 0.25-2% x gross cap 1x/2x, Aggressive | Lower risk and 1x roughly halved drawdowns at equal or better return-to-drawdown |
| R1 development + validation | Setups A-D, 8 variants each, 6 exits, 4 cost levels, neighbours, random controls | All 8 primary tests fail validation; BH: none |
| R2 development + validation | G1, G2, event policies | G1 FULL t 1.96 (fails 2.0); G1 control t 2.45; G2 fails |
| Decisions sealed | DECISIONS-validation.md, hashed | All R1 rejected; G1 FULL can at best be "investigate further"; G2 rejected |
| R1, R2 final (once) | 2019-2026 | Nothing changes. G1 FULL t 1.23 (fails); G1 control +0.31R, t 2.87 |
| Equivalence | App rules against harness | 0 differences in 2,762 triggers and 516 shadow trades |
| Live stress | Today's books | See section 6 |
| Options (descriptive) | Shares against calls on DoltHub quotes, 593 sampled trades | **Not completed.** DoltHub serves about 7 lookups a minute; 27 priced so far (6 of the earnings lead), too few to judge. Nothing is estimated in place of the missing quotes |

## 5. Comparison (net of costs; trades · mean R · t)

| Candidate | Variant | 1993-2012 | 2013-2018 | 2019-2026 | Win (val) | PF (val) | Confluence adds (t val, final) | Against random (t val, final) | Decision |
|---|---|---|---|---|---|---|---|---|---|
| A trend pullback, funds | price only | 1605 · -0.01 · -0.2 | 1195 · +0.06 · +0.9 | 1492 · -0.01 · -0.1 | 44% | 1.11 | | | |
| | FULL | 500 · -0.05 · -0.6 | 495 · -0.11 · -1.2 | 512 · -0.03 · -0.3 | 38% | 0.83 | -2.6, +0.8 | -0.7, -1.0 | reject |
| B breakout retest, funds | FULL | 202 · +0.11 · +0.8 | 153 · -0.19 · -1.2 | 169 · +0.06 · +0.5 | 35% | 0.75 | +0.9, +2.1 | -0.7, -0.1 | reject |
| C failed breakdown, funds | FULL | 69 · +0.07 · +0.3 | 92 · +0.11 · +0.4 | 77 · -0.10 · -0.5 | 45% | 1.18 | +0.9, -1.5 | +0.7, -0.8 | reject |
| D range reversion, funds | FULL | 24 · -0.47 · -2.0 | 22 · +0.17 · +0.6 | 15 · -0.00 · -0.0 | 55% | 1.36 | +0.6, +0.1 | +0.5, +0.1 | reject |
| A, stocks | FULL | 514 · -0.01 · -0.1 | 406 · +0.10 · +1.1 | 458 · +0.10 · +1.4 | 46% | 1.19 | +0.9, -0.0 | +0.0, +0.2 | reject |
| B, stocks | FULL | 209 · +0.01 · +0.1 | 179 · +0.02 · +0.2 | 188 · +0.03 · +0.4 | 42% | 1.03 | +2.0, -1.0 | -0.5, -0.8 | reject |
| C, stocks | FULL | 73 · -0.11 · -0.7 | 66 · +0.08 · +0.5 | 83 · +0.05 · +0.3 | 44% | 1.15 | +0.3, -0.5 | -0.1, -0.1 | reject |
| D, stocks | FULL | 27 · -0.51 · -2.7 | 20 · +0.42 · +1.4 | 17 · +0.71 · +2.0 | 65% | 2.18 | +1.0, +2.2 | +0.9, +2.0 | reject (tiny, and negative in 1993-2012) |
| G1 continuation | control | 236 · +0.12 · +1.0 | 164 · +0.33 · +2.5 | 293 · +0.31 · +2.9 | 51% | 1.65 | | | investigate further (not a candidate) |
| | FULL | 88 · +0.18 · +1.1 | 78 · +0.30 · +2.0 | 112 · +0.18 · +1.2 | 49% | 1.62 | -0.2, -0.9 | +1.4, +0.9 | reject |
| G2 reversal | FULL | 25 · -0.36 · -1.4 | 27 · +0.17 · +0.5 | 35 · -0.23 · -1.0 | 44% | 1.29 | +0.5, -1.1 | +0.6, -1.2 | reject |

Benchmarks: random entries under the same stops and exits earned about -0.08 to +0.16R a trade (funds and stocks,
by period). Before costs most price-only versions were +0.05 to +0.17R; costs of 0.06 to 0.12R a trade took that
away. Holding SPY returned +224%, +71% and +208% in the three periods (PT-1). The full table, with medians, tails,
losing streaks, MFE, MAE and giveback, is in `results/` (`comparison-table.csv`, `r1-*.json`, `r2-*.json`).

## 6. Portfolio repairs, audited

| Repair | Evidence | Status |
|---|---|---|
| Long only | PT-1 registered: helped every book; held on funds alone | kept (2750801) |
| Gross cap | Cut the worst drawdown in every period | kept; **1x for every book**, approved and built |
| Stop at least 1.5 ATR | PT-1 registered: helped Aggressive and Balanced; mixed on funds alone | kept |
| One position per idea | the record's doubled legs | kept |
| Options when IV is cheap | Not validated; "cheap" alone is no reason to prefer a call | **paused** (d5235c9): shares only until an option implementation is validated |
| Costs on new trades | Costs turned a flat book into a losing one in the replay | kept |
| Every book has a ceiling | Conservative had none | added, 1x (d5235c9) |
| Exposure by what it moves | Aggressive: 3.0x at market value, 3.4x counting 3x funds and option delta | added (d5235c9) |
| Event clusters | 5 of Conservative's 6 open positions report by 2026-11-04 (Balanced 8 of 14, Aggressive 6 of 12); trades held through a release lost more than 1.5R through a gap 3 to 5 times as often | cap of 2 or 3 positions reporting within 3 days of one another (d5235c9) |
| Over a limit | | the book stops adding, it never sells to fit (stated in the payload and caveats) |

**Lower risk per trade and an unleveraged ceiling (approved and built after this report, see Decisions).** On the approved rule
set, Aggressive at 0.5% risk and 1x gross had worst drawdowns of -12.6% (2013-2018) and -20.6% (2019-2026). At 2%
and 2x the figures were -25.7% and -45.4%, with similar or better return-to-drawdown. On funds alone the 0.5%/1x
drawdowns were -15.9% and -17.1%, against -41.2% and -38.7%. Suggested: Conservative 0.25%, Balanced 0.5%,
Aggressive 1%, all at most 1x, until an entry signal is shown to work.

**Live stress, today's books:** a 10% overnight gap on every holding costs Conservative 4.4%, Balanced 12.5% and
Aggressive 17.8% of the account. Technology down 15% with everything else down 5% costs 5.2%, 9.2% and 18.1%. The
open CVX call would lose 91% of its premium if CVX fell 5% and IV 20% over ten days.

## 7. Options selection

"Cheap IV" no longer turns a share trade into a call: every book takes shares. The historical comparison on DoltHub
quotes was not finished (section 4). The research watch now keeps Optic's recommended contract, with its quote and
IV verdict, beside every trigger, so the comparison continues forward on observed quotes. No short-premium strategy
was added.

## 8. Exits

On the price-only trades, a 3-ATR trailing stop or a 3R target beat the 2R reference in all four later-period
cells (funds and stocks, 2013-2018 and 2019-2026). Stocks: trailing +0.11 to +0.12R against +0.05 to +0.06R. Funds:
+0.03 to +0.04R against +0.01 to +0.02R. Partial exits and the early "no progress" exit did not help. Trades gave
back 0.85R on average from their best close. Maximum favourable move averaged 1.1 to 1.2R, maximum adverse -0.9R.
The trailing exit is a candidate for the next round, not a change now: in PT-1 it was mixed at book level.

## 9. Catalysts

* SEC filings give point-in-time release times. The release-cadence estimate (previous + 81 to 101 days) held the
  next release 84% of the time.
* Trades held through a release averaged more (+0.31 to +0.40R) but had fatter tails: 1st percentile -2.0 to -2.4R
  against about -1.5R. The higher average comes from today's survivors and is not evidence. The tail is why the
  event-cluster cap exists.
* Avoiding entries just before a release, or exiting before it, lowered results on these stocks, so neither is
  adopted as a return rule.
* No consensus estimates exist on history, so "surprise" is the price reaction, which is known only after the fact.

## 10. What each factor added

* **Participation (relative volume ≥ 1.25):** hurt fund pullbacks (t -2.2 and -2.6); otherwise inconsistent.
* **Market context (SPY above its 200-day, breadth ≥ 50%):** no consistent change.
* **Catalyst support (a recent strong earnings reaction):** positive in every period for setups A and B on stocks
  (+0.07 to +0.28R), on small samples. It is the same effect as G1.
* **Flow and positioning:** untestable on history; the research watch records them for every trigger.
* **More confluence** cut samples to about a third and did not improve outcomes.

## 11. Implementation and verification

* 2750801: the approved five rules (long only, 2x gross cap for Balanced and Aggressive, 1.5-ATR stop floor, one
  leg per idea, costs on new trades), the dated "Rules changed" line in v2 and Classic, and the disclaimer
  correction.
* d5235c9: options paused, explicit ceilings, leverage and delta in exposure, the event-cluster cap, the over-limit
  policy, the research watch (`app/research_book.py`, `/api/research-book`, off unless `OPTIC_RESEARCH_BOOK` is set)
  and its v2 section.
* Then: folds stay open across the page's redraws, and the section renderer is exported for checks.
* **Verified:**
  * Full suite 6,667 passed, 1 skipped, on the final branch.
  * Harness equivalence, as above.
  * A real daily pass on 2026-10-21: 89 symbols, 88 setups recorded, 20 triggers with snapshots.
  * The v2 page in the desktop pane and in 375x812 mobile emulation: no horizontal overflow, folds open by tap,
    loading, error, off and empty states.
* **Not verified:** a physical phone, Classic's new line in a browser (asserted by tests only), and the research
  watch's loop on a running server over several days.

## 12. Data blockers and what remains unproven

* No history of options flow, open interest, GEX or VEX, news timestamps, earnings estimates or macro calendars as
  they stood: strategies E and F, and any news rule, can only be tested forward.
* No survivorship-free stock universe. The earnings lead needs point-in-time index membership, with delisted names,
  before it means anything.
* DoltHub option quotes are slow to query, so an options comparison on history needs a bulk copy or a long
  background run.
* The forward record needs hundreds of independent trades. At about 20 triggers a day it reaches 300 closed shadow
  trades in a few months, but triggers cluster in time, so independence is lower than the count.

## 13. Recommendations

| Candidate | Recommendation |
|---|---|
| A-D, funds and stocks, all variants | **Reject** |
| G1 with confluence | **Reject** |
| G1 control (strong positive earnings reaction) | **Investigate further:** round R3, pre-registered, on a survivorship-free stock universe with point-in-time index membership, at least 1,000 events, with the trailing exit as a registered variant. The research watch already records it forward. |
| G2 | **Reject** |
| E positioning-conditioned, F flow-confirmed | **Forward only:** test once the research watch holds at least 300 triggers with snapshots, against the same setups without them |
| Advance to forward paper testing | **None qualifies.** The research watch records shadow trades for every setup (frozen rules) so a forward test exists, but nothing is promoted to a portfolio |

## Decisions

Recorded 2026-10-21, the owner's words: "Approve d5235c9 and also build the recommended lower risk: 0.25%, 0.5%
and 1% per trade, every book at most 1x. Don't push yet."

1. d5235c9 approved: options paused, Conservative's 1x ceiling, exposure counted by leverage and delta, the
   earnings-cluster cap.
2. Lower risk built (next commit on the branch): 0.25%, 0.5% and 1% per trade, every book at most 1x.
3. Still open: switch on the research watch (`OPTIC_RESEARCH_BOOK=true`) when the branch is deployed.
4. Still open: push, on the owner's word, when Railway builds are back.
5. Started as their own sessions: round R3 on the earnings-reaction lead, and the fixes for three input defects
   found in the audit (repainting levels, the regime's breadth label, the earnings move's timing).
