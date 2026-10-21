# Research rounds R1 and R2: confluence setups and catalysts

Pre-registered 2026-10-21, before any run. Rules, parameters, benchmarks and acceptance criteria below are fixed. A
change after a result is read gets a dated section of its own and is reported as post hoc. Every run is logged in
`log/experiments.jsonl`, failures included.

## Why another round

Optic's validation program (2026-10-14) found no single technical rule with an edge (0 of 82). This round tests what
it did not: whether a precisely defined price trigger **plus support from at least two independent evidence
categories** changes the outcome, judged as complete trades with stops, exits and costs rather than fixed-horizon
returns; on a wider fund universe; and with point-in-time earnings releases from SEC filings. The single-factor
versions are run beside it as controls, so a null result is read against them.

## Data

* Prices: snapshot `data/prices-2026-10-21` (hash-checked), 43 funds and 40 large stocks, daily, split-adjusted
  closes as Optic reads them, to 2026-10-20.
* Earnings: `data/earnings_events.csv`, SEC 8-K item 2.02 (item 12 before 2004) acceptance times for the 40 stocks,
  2003-10 on. Mid-session acceptances are flagged `during_session` and treated as reacting the same session.
* Not available on history, so not in these rounds: options flow, GEX, flip, walls, VEX, news, the earnings calendar
  and estimates as they stood, macro calendars. Strategies E and F are forward only (see FACTORS.md).

## Universes and eligibility

* **Funds (primary):** 43 funds. **Stocks (secondary):** 40 large stocks, survivor-biased (today's names), never
  enough on their own to advance a candidate.
* A symbol is eligible at the close of day t when it has at least 260 bars and a 20-day median dollar volume of at
  least $20 million (dollar volume is unchanged by splits, so this is point in time).

## Periods

Development to 2012-12-31; validation 2013-01-01 to 2018-12-31; final 2019-01-01 to 2026-10-20. The final period is
not untouched in general: the validation program and the portfolio replay (PT-1) used it for other rules. It has not
been used for any rule in this protocol, and it is run once, after the validation decisions. A trade belongs to the
period of its entry; a trade still open at a period's last session is closed at that close, so no outcome crosses a
boundary.

## Inputs at the close of day t (data to t only)

ATR14 (Wilder, as Optic), SMA20/50/200, relative volume RVOL = V_t / mean(V_{t-20..t-1}), RS63 = (C_t/C_{t-63}) /
(SPY_t/SPY_{t-63}) - 1, breadth = share of the nine sector SPDRs above their 200-day average (from 1999-12), SPY
above its 200-day average. Levels are rolling extremes known before the trigger bar; no clustered pivot level is
used, because Optic's levels repaint (FACTORS.md).

## Evidence categories

* **C1 price location and structure:** the setup itself (below). Required, and not counted toward the two.
* **C2 participation:** RVOL on the trigger bar at least 1.25. (RSI, MACD and moving averages are not counted
  separately: they read the same closes as the trigger.)
* **C4 market and sector context:** SPY above its 200-day average and breadth at least 50%.
* **C5 catalyst and fundamental context (stocks only):** an earnings reaction in the 15 sessions before t whose
  reaction-session return beat SPY's by at least 2 points, with C_t still above the close before the release.
  Missing earnings data is not support.
* **C3 flow and positioning:** not available on history.

A category that cannot be evaluated (breadth before 1999-12, earnings before 2004) makes the event ineligible for
**every** variant, so all variants are compared on the same events.

## Setups (long only)

All stops: setup level minus 0.25 ATR, moved out to at least 1.5 ATR below the entry; a setup whose stop would be
more than 4 ATR away is skipped. Entry: the next session's open; skipped when that open is more than 1 ATR above the
signal close, or at or below the stop. A trigger condition that holds on several bars counts on its first bar only.

* **A. Trend pullback.** Context: C > SMA200 and SMA50 > SMA200. Location: within bars t-4..t the low came within
  0.5 ATR of SMA50 (or below it), after a fall of at least 2 ATR from the highest high of t-20..t-1. Trigger:
  C_t > H_{t-1} and C_t > O_t. Stop level: lowest low of t-4..t.
* **B. Breakout and retest.** Level R = highest high of t-65..t-6. Breakout: a close above R + 0.25 ATR on some bar
  j in t-10..t-1. Retest: a bar k after j and before t whose low came within 0.5 ATR of R and whose close held
  above R - 0.25 ATR. Trigger: C_t > H_k for the latest such k. Room: if the 252-day high is above C_t it must be at
  least 2R away. Stop level: lowest low from k to t.
* **C. Failed breakdown and reclaim.** Level S = lowest low of t-65..t-6. Break: a close below S - 0.25 ATR on a bar
  j in t-5..t-1. Trigger: C_t > S + 0.1 ATR and C_t > H_{t-1}. Stop level: lowest low from j to t.
* **D. Range mean reversion.** Range over t-60..t-1: width W = highest high - lowest low L at most 8 ATR, and the
  net change over the 60 bars at most 0.25 W. Location: L_t at most L + 0.15 W and at least L - 0.5 ATR. Trigger:
  C_t > O_t and C_t > H_{t-1}. Stop level: L - 0.25 ATR (so 0.5 ATR under the range in all).

## Variants (the controls are the point)

* K1 price trigger only; K2 + C2; K3 + C4; K4 + C5 (stocks).
* FULL: funds C2 and C4; stocks at least two of C2, C4, C5.
* Leave one out (stocks): C4+C5, C2+C5, C2+C4.
* Random entries: for every FULL trade, a random eligible symbol and date from the same universe and period,
  entered at the next open with the same stop distance in ATR and the same exits; 20 repetitions.
* Neighbouring parameters (robustness only, never selection): RVOL 1.1 and 1.5; A's fall 1.5 and 2.5 ATR; B's and
  C's 60-bar window 40 and 80; D's width 6 and 10 ATR.

## Exits

* E1 (reference, the ledger's): stop, 2R target, 45 calendar days.
* E2: stop, 3R target, 45 days. E3: no target, stop trails 3 ATR (at entry) under the highest close, 45 days.
* E4: E1 plus an early exit at the 10th session's close if the trade never reached +0.5R.
* E5: half at +1R with the stop moved to the entry, the rest at 3R, stop or 45 days.
* E6 (D only): the range midpoint as the target.
* Order inside a bar: the stop first when both are inside it; a gap through a level fills at the open. Every trade
  records its maximum favourable and adverse move in R, sessions to exit, and the profit given back from its best
  close.

## Costs

Per side: 10 bp for a fund, 15 bp for a stock (5 or 10 bp plus 5 of slippage). Sensitivity: 0x, 2x, 3x. In R:
cost x (entry + exit) / risk per share.

## Measures

Per variant, universe, exit and period: trades, independent months, win rate after costs (a win is a net R above
zero at the actual exit), mean and median win and loss, mean net R with a standard error clustered by calendar
month, profit factor, tail (5th percentile R), longest losing streak, MFE, MAE, time to target and to stop,
giveback. **Incremental value:** within the K1 events, a regression of net R on an indicator for meeting the
confluence (month-clustered t). Benchmarks at portfolio level: SPY held, SPY held when above its 200-day average,
and random-entry books.

## Portfolio check (candidates only)

0.5% of equity at risk per trade, gross at most 1x, at most 10 open positions, one per symbol, realised equity for
sizing, the same costs; compared with random-entry books under the same rules and with the benchmarks above.

## Acceptance (for each setup and universe, FULL with E1)

1. Validation: mean net R > 0 with t ≥ 2.0; the incremental coefficient > 0 with t ≥ 1.5; FULL minus random > 0
   with t ≥ 2.0.
2. Benjamini-Hochberg at q = 0.10 across the round's eight primary tests (four setups, two universes), on the
   validation p-values of test 1's first part.
3. Final, run once: mean net R > 0 with t ≥ 1.5, and the incremental coefficient of the same sign.
4. Robustness: at least 55% of symbols with 5 or more trades have a positive mean in validation plus final; the
   development period is not significantly negative (t > -2); neighbouring parameters keep the sign of the mean.
5. At twice the costs, the validation plus final mean net R stays above zero.
6. Portfolio check: maximum drawdown at most 20% in validation and in final, and return-to-drawdown above the
   median random-entry book.
7. At least 100 FULL trades in validation plus final.

**Advance to forward paper testing** when 1 to 7 all pass, for a fund candidate (a stock-only pass is "investigate
further" because of survivorship). **Investigate further** when 1 passes but others fail, or when 3 and 4 pass with
test 1 at 1.5 ≤ t < 2.0. **Reject** otherwise. If nothing advances, the report says "no validated strategy found".

## R2: catalysts (stocks), registered with R1

* **Event timing.** Reaction session r: the release day if accepted before 09:30 ET, otherwise the next session.
  Reaction return = C_r / C_{r-1} minus SPY's, in points.
* **G1 post-event continuation.** Reaction ≥ +3 points, RVOL_r ≥ 2, C_r in the upper half of the session's range.
  Entry r+1 open. Stop: L_r - 0.25 ATR, floor 1.5 ATR. FULL adds C4. Control: reaction ≥ +3 only.
* **G2 post-event reversal (long).** Reaction ≤ -3 points, RVOL_r ≥ 2, C_r in the upper half of the range (the
  drop was bought), and C_{r-1} above its 200-day average. Entry r+1 open, same stop rule. FULL adds C4. Control:
  reaction ≤ -3 only.
* **Event policies for R1's stock trades**, reported separately, never blended: (a) hold through; (b) do not enter
  when the estimated next release (previous release + 81 to 101 days) begins within 10 sessions; (c) exit at the
  close before the estimated window begins. The estimate uses only past releases; how often it missed the actual
  date is reported. Trades are tagged opened-before, held-through and entered-after for every report.
* G1 and G2 use the same exits, costs, measures and acceptance tests as R1 (their BH family is their own two tests),
  and at most "investigate further" because the stocks are survivor-biased.

## Options (section 7), descriptive

For FULL and K1 trades on symbols DoltHub covers, entered from 2019 on: the call nearest 0.50 delta with 30 to 60
days to expiry on the signal date's end-of-day chain, bought at the ask and sold at the bid on the exit date's chain,
against the shares from the same close to the same exit close, at the same dollar risk (premium for the option).
Split by Optic's IV verdict computed from DoltHub's 30-day IV over 30-day realised (cheap below 0.9). Weekly
snapshots before 2024 leave many dates without a chain: those trades are reported as not priced, not estimated.
Nothing here can promote a candidate; it says whether "cheap IV, so buy the call" survives observed quotes.
