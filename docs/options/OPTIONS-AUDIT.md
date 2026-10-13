# Options tab: inventory, correctness audit, definitions and roadmap (2026-10-13)

Branch `options-pass` (built on `strategy-pass`; neither pushed). Research behind every decision is in
`docs/options/research/`:

| File | Covers |
|---|---|
| `PRICING-IV-EVENTS.md` | Black-Scholes conventions, delta vs probability, IV rank/percentile, term structure, skew, expected and earnings moves, expiry, settlement and assignment |
| `GEX-FLOW-LIQUIDITY.md` | Dealer gamma and vanna methods and evidence, what snapshots can and cannot show about flow, liquidity and execution, data providers and prices |
| `WORKFLOWS-STRATEGY.md` | Contract selection, strategy analysis, presentation for mixed audiences, regulation, portfolio risk, retail outcomes |

Evidence labels, as in the research: **MATH** established mathematics, **EMP** empirically supported (study cited),
**HEUR** practitioner heuristic, **MKT** marketing, **PROP** proprietary. **V** = verified here (test, fixture or
browser); **C** = code reading.

---

## 1. Inventory: what the tab shows and where each figure comes from

Data: Yahoo Finance chains through yfinance (`app/providers/yf.py:options_chain`): per contract bid, ask, last,
last-trade time, volume, open interest, Yahoo's implied vol, strike, expiry, in-the-money flag. No quote sizes,
no quote timestamps, no trade tape, no aggressor side, no open/close flags; open interest is the previous
session's; quotes are delayed ~15 minutes. Four expiries are read for the tab, picked nearest to 7, 21, 35 and 60
days (`app/providers/common.py:pick_swing_expiries`); the research table reads any one listed expiry.

| Section (top to bottom) | Figures | Source / calculation | Status after this pass |
|---|---|---|---|
| Price head | Last, change, extended-hours print, ATR(14), expected 2-week range | quote; `technicals.py` | Unchanged |
| **What options are pricing** (new) | IV30, IV rank and percentile, month straddle and 1-SD moves, term structure, 25-delta skew, report move, expiry table, as-of, rate | `vol_surface.py`, `iv_history.py`, `rates.py` | New; all figures from the corrected chain |
| What the options market is saying (below Advanced) | call/put volume per 100, GEX regime, Optic's signals | `flow.py`, `gex.py`, verdict | Wording kept; regime now descriptive |
| Optic's read line | stance, conviction | `swing.verdict` | Unchanged (unvalidated composite, labelled) |
| **Research contracts** (new) | per contract: delta, bid/ask/mid, spread % and grade, IV, breakeven at the ask and the move it needs, cost at the ask, decay per day, vega per point, N(d2), OI/volume; events before expiry | `/api/options/{T}/research`, `contracts.py`, `liquidity.py` | New |
| **Position builder** (new) | legs, entry at mid / natural / with slippage and fees, max profit and loss or "no cap/limit", breakevens, payoff at expiry vs today and halfway (model), aggregate greeks, price x IV grid at now / chosen day / expiry, flags, events, leg liquidity | `/api/options/{T}/analyze`, `position.py` | New |
| Trade setup (advBlock): example contract | example strike/expiry at the mid, pullback/breakout setups, pricing note, warnings | `entry.py` | Rewritten as a described example (was an order ticket) |
| Options brief, what's next, why moving, follow-ups | text from payload | various | Unchanged |
| Swing setups | rule table | `setups.py` | Unchanged (hypotheses, labelled) |
| Swing verdict + score table | composite and inputs | `swing.py` | Unchanged |
| Perspective, close defence, patterns, structure | bull/bear evidence, levels | `cases.py`, `defence.py`, `patterns.py`, `structure.py` | Unchanged |
| Strike & entry recommendation (Advanced) | candidates, scores | `entry.py` | Uses corrected IV and rate; wording descriptive |
| Price chart, levels, RSI, MACD | technicals | `technicals.py` | Unchanged |
| Options analytics: greeks panel | aggregated greeks, gamma by expiry | `greeks_panel.py` | Inputs corrected |
| GEX panel | net GEX per 1% move (now also % of average dollar volume), regime, flip (now with zone), walls, by strike, profile, sign note, expiries used, inputs | `gex.py` | Inputs corrected; notes descriptive; caveats shown |
| Flow panel | P/C, time value traded, by strike, **Most active contracts** (was Notable/unusual) | `flow.py` | Wording corrected; threshold scales with the chain |
| IV panel | IV/realised ratio, IV against the realised range (was "IV rank (proxy)"), a real IV rank when one exists, realised vol by window, term (now ATM) | `entry.iv_context` + surface | Relabelled; term from the surface |
| Strategy ideas | verticals, single legs, condors, straddles/strangles at the mid | `swing.build_strategy_ideas` | Adds the natural (crossing the spread) cost |
| Milo context | everything above that is loaded | `app.js:chatContextPayload` | Adds vol_surface, iv_rank, rate, options_research (filters, rows on screen, the position and its analysis) |

---

## 2. Correctness audit: findings, evidence, fix

Ordered by financial correctness first. Fixtures: saved Friday 2026-10-09 close chains (SPY all expiries to Dec-18,
2,643 contracts; AAPL four expiries), read at Sun 2026-10-11 17:39 ET.

| # | Finding | Evidence | Fix | Status |
|---|---|---|---|---|
| C1 | Risk-free rate 0% in every option price | `RISK_FREE` default (`main.py`); at r = 0 the feed IVs put calls 0.2-4.1 vol points above puts at the same strike near the money on SPY (1.3-3.8 on AAPL), which put-call parity produces on its own; the flow score scored it as a "chase bid" | 13-week bill yield (^IRX, 4.05% on 2026-10-12) unless `RISK_FREE_RATE` is set; stated in every caveat (`app/rates.py`) | Fixed, V: re-solved gap -0.3-1.0 (SPY), -0.2-0.7 (AAPL) |
| C2 | Time to expiry from the server's UTC date, floored at 6 hours | `yf.py` dte/tau; a UTC host is a calendar day ahead after 8pm ET; every expiry-day contract had 6 hours whatever the time | 4:00pm ET on the expiry date, ET calendar, floor 1 hour (`vol_surface.expiry_tau`) | Fixed, V (tests at 9pm ET, expiry morning, after close) |
| C3 | Mid fell back to the last trade; spread % priced from a zero bid | `yf.py` mid/spread_pct | Quote states (two-sided, locked, crossed, no bid, no ask, none); mid and spread only for two-sided quotes; `mark_source` says when "last" stands in | Fixed, V |
| C4 | Yahoo's IV used as given, inconsistent with Optic's own rate and yield | C1; Yahoo does not document its method | IV re-solved from each two-sided mid at Optic's r and q; out-of-the-money side per strike (no early-exercise premium read as volatility); feed IV only where nothing is quoted, flagged | Fixed, V (round trip 5-300% vol; feed fallback) |
| C5 | Term structure from the median IV of every strike | AAPL "inverted, earnings bid" at 71.9% vs 44.5% when ATM was flat (24.5% vs 25.4%) (2026-10-11) | ATM IV at the forward per expiry from OTM quotes; front = first expiry a week or more out; event named only when inside | Fixed, V (AAPL now "flat ... report inside Nov-13") |
| C6 | Skew pooled across expiries at fixed strikes | `flow.py` | 25-delta risk reversal per expiry; SPY 1.1 (1 day) to 4.1 points (68 days) | Added; flow's own skew now reads corrected IVs |
| C7 | "IV rank (proxy)" was realised-vol based under a true IV rank's definition | `entry._iv_rank_proxy`; IV exceeds RV on average (Carr & Wu 2009) so it reads high | Real rank from Cboe indices (SPY VIX, QQQ VXN, DIA VXD, GLD GVZ, USO OVX; RVX not on Yahoo) and from Optic's own daily IV30, stored from today, shown after 20 days with the count; the proxy renamed | Fixed, V (SPY rank 9.9 / pct 14.7 over 252 days) |
| C8 | GEX regime text forecast outcomes and advised strategies ("Expect mean reversion... Favours selling premium") | `gex.py` | Descriptions tied to evidence (size of moves, not direction; Baltussen et al. 2021); walls "not tested as support or resistance"; single-stock sign caveat (Lakonishok et al. 2007) vs index products (Garleanu et al. 2009) | Fixed |
| C9 | GEX total depends on which expiries are read and the rate, neither stated | SPY net GEX $430M (4 expiries) vs $2,463M (9); $430M vs $1,138M at r = 0 vs 4% (2026-10-11) | Expiries used, by-expiry shares, inputs, previous-session OI stated beside the number; % of average dollar volume | Fixed (disclosure); expiry selection unchanged |
| C10 | Flip shown to two decimals as if precise | `gex.py` | Flip zone where net gamma is within 15% of its peak | Fixed |
| C11 | Entry plan was an order ticket ("Buy the... Place a limit order at... Half size now... Respect the stop") | `entry.py` | A described example, "not a recommendation to trade"; no sizing; warnings describe; timeline text matches the code | Fixed |
| C12 | Earnings "expensive" verdicts tilted by method; "favors selling structures" | Straddle spans the report and ordinary days, compared with one or the other (2026-10-11); Gao, Xing & Zhang (2018) found pre-report straddles earned positive average returns | Baseline = sqrt(event^2 + ordinary^2); no strategy advice; same-day expiry spans an after-close report no more | Fixed |
| C13 | "Time value bought" and "unusual activity" from a snapshot with no side | `flow.py` | "Traded"; "Most active contracts" with a chain-relative floor and the list of what a snapshot cannot show | Fixed |
| C14 | Strategy ideas priced at the mid only | Retail-favoured weeklies average a 12.6% quoted spread (Bryzgalova, Pavlova & Sikorskaya 2023) | Natural cost on every idea; the builder shows mid, natural and slipped-plus-fees | Fixed |
| C15 | Milo never saw the options research and lost options blocks to the context budget | capture of 7 Options-tab questions | options_research, vol_surface, iv_rank, rate sent and prioritised on the Options tab | Fixed, V |
| C16 | Greeks used Yahoo's IV with r = 0 | as C1/C4 | Greeks from corrected IV and rate | Fixed |
| O1 | Expiry selection skips 0-5 DTE (most gamma on index products) | `pick_swing_expiries` | Not changed: stated next to GEX instead | Open (roadmap) |
| O2 | European model for American equity options | `greeks.py` | OTM-side IV limits the error for pricing; early assignment flagged in the builder | Partly mitigated; binomial with discrete dividends is roadmap |
| O3 | Composite score, setups, walls have no validated edge | 2026-10-11 analysis F8 | Labelled; not changed here | Open (validation protocol) |

---

## 3. Calculation definitions (units)

- **Time to expiry** T = (4:00pm ET on the expiry date - now) / 365 days, calendar time, floor one hour.
- **Rate** r: 13-week bill yield, continuous approximation; one rate for all expiries. **Dividend yield** q: the quote's,
  continuous.
- **Mid** (bid + ask) / 2 for two-sided quotes only. **Spread %** (ask - bid) / mid x 100.
- **IV**: Black-Scholes-Merton IV solved from the mid by bisection; per (expiry, strike) the OTM side's IV (call if K >= F,
  put if K < F, F = S e^{(r-q)T}).
- **Greeks** (`greeks.py`): delta per $1 per share; gamma per $1; vega per 1 vol point; theta per calendar day; rho per
  1%; vanna per vol point; charm per day. Per contract x 100; per position x quantity.
- **ATM IV**: total variance interpolated in log-moneyness at the forward between the OTM strikes either side.
- **IV30**: total variance interpolated linearly in time between the expiries bracketing 30 days; not extrapolated.
- **25-delta risk reversal**: IV(put at -0.25 delta) - IV(call at +0.25 delta), vol points; positive = puts richer.
- **Straddle move** ATM call mid + put mid at the strike nearest the forward, / S: about the expected absolute move.
  **1-SD move** IV x sqrt(T): straddle ~ 0.8 x 1-SD. Neither is a price limit.
- **Event move** sqrt(IV_after^2 T_after - IV_before^2 (T_after - 1 day)), shown only when positive.
- **IV rank** (today - low) / (high - low) x 100 and **IV percentile** share of days lower x 100, same window (252 days for
  a full year; Optic's own readings shown from 20 days with the count).
- **Model chance of finishing in the money** N(d2) for a call, N(-d2) for a put: risk-neutral, not a forecast; not delta
  (N(d1)); not a chance of profit.
- **Breakeven at expiry** long call K + ask; long put K - ask (research table); positions: roots of the expiry payoff
  computed from the mid entry.
- **Liquidity grade** Tight: two-sided, spread <= 5% of mid (or <= $0.05), OI >= 500, traded this session; Fair: <= 10% or
  thinner OI; Wide: <= 25%; No usable quote: one side missing, locked, crossed or > 25%. Defaults, returned with every
  grade. Cannot see quote size, quote time or the complex order book.
- **Entry prices** mid; natural = asks for bought legs, bids for sold legs; slipped = mid + share x half-spread toward the
  worse side, plus fee per contract.
- **Max profit / loss** extremes of the expiry payoff over a grid including price ~0; "no cap" or "no limit" when the slope
  as price rises is positive or negative (calendars report within the drawn range).
- **GEX per contract** s x gamma x OI x multiplier x S^2 x 0.01, s = +1 call, -1 put (assumption); dollars of dealer delta
  per 1% move. **VEX** s x vanna x OI x multiplier x S, dollars per vol point. **% of average dollar volume** |net GEX| /
  (average volume x S).

## 4. Positioning assumptions (stated on screen)

Dealers are assumed long the calls customers sold and short the puts customers bought. Open interest shows how many
contracts are open, not who holds them. For index products research broadly supports the convention; for single
stocks public customers were found net writers of both calls and puts, so the call side may be wrong in sign. Open
interest is the previous session's, so same-day (0DTE) positions are missing. The flip and walls are where hedging
would be largest if the assumption holds, not observed levels; pinning on expiry day is real but small (~16.5bp,
Ni, Pearson & Poteshman 2005).

## 5. Verification (2026-10-13)

- Unit and endpoint tests: `tests/test_options_correctness.py` (clock, quote states, IV re-solve and round trip, rate
  carry, risk reversal, constant maturity, term and event, rate source, liquidity, position maths, IV rank, Hull's
  example, finite-difference greeks with dividends, near-expiry, quote-less chains, page contract, Milo rules),
  `tests/test_options_research_api.py` (research filters and events, analyze pricing, refusal, pin risk, leg limit).
- Fixture checks: see section 2; numbers in the session work folder (CHECKPOINT.md).
- Browser (fixture-backed server, Chromium 1440px and 390px, dark): pricing card, research table, ten templates,
  payoff chart, scenario grid, phone layout. Screenshots in the work folder.
- Full suite: see the final commit message.
- Not verified: live market-hours chains (sessions ran overnight; the live chain is frozen then and correctly refused),
  real devices, broker-value comparison (no broker access), signed-in flows, production model answers for Milo.

## 6. Gaps, providers and ongoing costs

| Gap | What it needs | Options (from research, prices as published 2026-10) |
|---|---|---|
| Who bought or sold; opening vs closing; sweeps, blocks, spread legs | OPRA trades with conditions, or exchange open/close data | Cboe Open-Close ~$3,000/month (Cboe exchanges only); Databento OPRA from $199/month; display to users needs an OPRA vendor agreement and display fees |
| Quote sizes and timestamps | OPRA quotes | as above; Polygon/Massive, ThetaData (personal-use licences: not for a public app) |
| Historical IV for a real rank today | IV surface history | ORATS from ~$199/month; or wait for Optic's own daily store (free, 252 trading days to a full year) |
| Same-day OI | intraday OI | not available free; vendors above |
| Licensed display of any options data | data licence | needed before charging (2026-10-11 analysis F15) |

Ongoing cost of this pass: none (no paid data, no AI calls; the IV store is one SQLite row per symbol per day).

## 7. Roadmap (prioritised)

| Priority | Item | Why | Effort |
|---|---|---|---|
| 1 | Validate the liquidity grade against a few broker tickets during market hours; tune thresholds | Grades are heuristic | S |
| 2 | Log implied vs realised moves (straddle, 1-SD, event move) per symbol per day | Turns expected-move readings into measured calibration | S |
| 3 | Store daily OI per contract; show next-day OI change on the activity screen | The only free confirmation that volume opened positions | M |
| 4 | Read 0-5 DTE expiries into GEX for index products, shown separately | Most index gamma sits there | M |
| 5 | Reg T margin estimate beside max loss (labelled "typical minimum") | Readers confuse the two | S |
| 6 | Probability-of-profit with its model and IV named, always beside max loss, calibrated on stored snapshots | A common question; only honest with calibration | M |
| 7 | Binomial (American) pricer with discrete dividends for single stocks | Deep ITM puts, dividend calls | M |
| 8 | Paper Desk options legs analysed with the position engine; portfolio greeks and stress | "How does this affect my overall risk?" | M |
| 9 | Licensed data and OPRA-derived flow, if the product warrants it | Only way to say anything about intent | L, paid |
