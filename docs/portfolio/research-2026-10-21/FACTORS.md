# Optic's inputs: what they are, where they come from, and what history exists

Audit of origin/main 2728171 plus branch portfolio-triggers (2026-10-21). Code read by an audit pass and the
load-bearing claims re-checked by hand (marked ✔). "Replay" means rebuildable on past daily bars with only the
information available at that date.

## Price structure and momentum (category 1 and 2)

| Input | Definition (code) | Source, refresh | Timestamp | Missing data | Replay | Limits |
|---|---|---|---|---|---|---|
| Support/resistance levels | Pivots by `argrelextrema(order=4)` over 252 bars, clustered within 0.6 ATR, 2+ pivots, scored by touches, rejection, volume, recency (`analytics/technicals.py:196`) | yfinance or Tradier daily, 5-min cache | payload `generated_at` only | `[]` under 18 bars | yes | ✔ **Repaints.** `argrelextrema` clips at the edge, so the last 4 bars can be pivots with no right-side confirmation. Measured: 221 of the levels in 240 sampled windows rested on such a pivot, and 223 of 240 windows had a level gone 5 sessions later. The paper ledger's stop (`paper._pick_stop`) uses these levels. During the session the last bar is the forming bar (`main.py:665`). |
| Swing highs/lows, trend lines, patterns | 120-bar extremes; trendlines and patterns need `order` bars to the right (`patterns.py:175`) | same | none | skipped | yes | patterns carry a `confirmed` flag |
| Setups engine levels and triggers | 17 presets; prior channel excludes the current bar; pivots used only from `i+right`; forming candle dropped (`analytics/setups.py:725-987`) | same | per signal | NaN volume read as 0 | yes, causal | validation H-T03: no preset beat an average day at 20 sessions |
| RSI, MACD, SMA/EMA, slopes | Wilder RSI14, MACD 12/26/9, SMA 20/50/100/200, EMA 9/21/50 (`technicals.py:18-60`) | same | none | NaN | yes | one family: they all read the same closes, so they count as one piece of evidence |
| Relative strength | ratio to SPY over 1w to 6m and a 60-bar z (`series_stats.py:188`); 21/63-session excess vs SPY and sector (`research/swing_setup.py:116`) | same | none | None | yes | |
| Volume, relative volume | volume over the mean of the prior 20 bars, current bar excluded (`setups.py:1037`) | same | none | 0 | yes | intraday the day's volume is partial |
| Anchored VWAP | cumulative typical price x volume from a confirmed swing (`setups.py:955`) | same | anchor date | n/a | yes | a manual anchor is flagged as hindsight |
| Session VWAP, opening range | 5-minute bars (`session_rules.py`) | yfinance 5-min, about 60 sessions | bar times | n/a | **no**: no intraday archive | |

## Options flow and positioning (category 3): forward only

| Input | Definition | Source | Timestamp | Replay | Limits |
|---|---|---|---|---|---|
| Flow | Premium = volume x 100 x time value; put/call by volume and OI; volume above OI as "new"; "unusual" = volume ≥ 50 and premium ≥ max($25k, 1% of chain) (`analytics/flow.py`) | chain snapshot: day-to-date volume, prior-session OI; yfinance 60 s, Tradier 8 s | chain `fetched_at` not carried into the payload | **no** | ✔ **No trade side.** "Free data has no trade tape, so there is no true bid/ask side per print" (`flow.py:3`). Nothing is a sweep or a block; calls are not "bought". Volume is partial intraday, OI a session old. |
| GEX, flip, walls | `gex = sign x gamma x OI x 100 x S² x 0.01`, sign +1 call, −1 put (`analytics/gex.py:142-149`) | chain OI and IV re-solved from mids | none | **no** (no OI history) | ✔ **Assumed dealer book:** dealers long every call and short every put. Open interest does not say who holds what, so this is a model, not observed positioning. |
| VEX | `sign x vanna x OI x 100 x S`, vanna per vol point = `−e^(−qT)·φ(d1)·d2/σ/100` (`gex.py:157`, `greeks.py:110`) | same | none | **no** | ✔ same assumed dealer book; shown as text only, not in any score; no "vanna flip" |
| CEX, DEX, pin, near-term GEX share | same construction with charm and delta | same | none | no | max pain is not computed anywhere |
| Signal archive | first read per symbol per ET weekday between 09:45 and 16:00: composite and its five parts, gamma regime, net GEX, flip, walls, placebo strikes, IV30 (`signal_archive.py`) | live server | yes | forward | since 2026-10-14 live: **197 reads over 6 days** (live `/api/validation`, 2026-10-21); only symbols someone loads; flow kept as a score only; VEX not kept |

## Volatility and options pricing

| Input | Definition | Source | Replay | Limits |
|---|---|---|---|---|
| Realised vol | log-return std x √252 over 10/20/30/60 bars | daily bars | yes | |
| IV verdict | ATM IV (median within ±5%) over RV20: rich ≥ 1.35, slightly rich ≥ 1.1, fair ≥ 0.9, cheap below (`entry.py:152`) | live chain | partial: DoltHub 30-day ATM IV from 2024-10 | validation: "rich" robust; "cheap" roughly fair, not cheap |
| Surface: ATM by forward, 25-delta risk reversal, term, straddle, expected move (`vol_surface.py`) | | live chain | no | ✔ `event_move` never receives the report's timing from `main.py`, so an after-close report on an expiry's own date is counted inside that expiry |
| IV rank | own first-of-day IV30 since 2026-10-13; Cboe index histories for SPY, QQQ, DIA, GLD, USO | live | partial | a year of visits before a stock's rank is real |
| DoltHub option chains | per-contract bid, ask, IV, delta, gamma, theta, vega, rho; **no volume or open interest** | DoltHub SQL API | **yes for pricing**, weekly snapshots in 2019, daily later | cannot rebuild flow or GEX; one symbol-day per query |

## Market and sector context (category 4)

| Input | Definition | Replay | Limits |
|---|---|---|---|
| Regime score | trend 0.30, breadth 0.25, VIX 0.20, small caps 0.15, leadership 0.10; ±12 and ±40 bands (`regime.py:82`) | yes | ✔ breadth is labelled "% of sectors above the 200-day" but `brief.py` passes the share of sectors **up today**, the same quantity as leadership (also found by the validation program) |
| Macro risk score | VIX steps, 20-day moves, 10-year yield, HY spread, curve inversion (`macro.py:381`) | partial | FRED values are today's vintage, so history is revised |
| Breadth, index trend, sector trend | computable from sector and index ETF closes | yes | |

## Catalysts and fundamentals (category 5)

| Input | Definition | Source, refresh | Replay | Limits |
|---|---|---|---|---|
| Next earnings date | first date of yfinance `Ticker.calendar`, 1 h cache | Yahoo | **no** (today's calendar) | no before-open/after-close tag; `earnings_week.py` refuses to guess |
| Past report timing | ≥ 16:00 ET after close, midnight unknown (`yf.py:652`) | Yahoo | partial | |
| Earnings results and surprise | EPS estimate, actual, surprise, 6 h cache | Yahoo | **no** (no archive of the estimate as it stood) | |
| SEC earnings releases (new, this round) | 8-K items 2.02 (12 before 2004) with EDGAR acceptance time, 3,681 releases for 40 stocks since 2003 (`research-round/earnings_events.py`) | data.sec.gov | **yes, point in time** | acceptance time can lag the press release; 466 were accepted mid-session (often preannouncements or late filings) and are flagged uncertain. No consensus, so no surprise against expectations |
| News | yfinance news, 10 min cache; recency weight `max(0.15, 1/(1+age/36))`; swing news score `clip(net x 12, ±70)` (`news.py:854`) | Yahoo | **no** | no publication-time archive; repeats not deduplicated across sources |
| Filings | EDGAR submissions, 1 h, `filingDate` only | SEC | yes | acceptance time not used by the app |
| Macro calendar | BLS ICS, FOMC page, CFTC rule (`events.py`) | live | **no** archive of the calendar as it stood | |
| SEC facts | latest restated value, `available_from` = first filing date | SEC | **lookahead** | a replay would see restated numbers on the first filing date |
| Valuation, quality, long-term | quote multiples, DCF, quality weights, 40/200-week trend | live, SEC | partial | |
| Observations archive | next earnings, last report, TTM figures, shares (since 2026-10-06) | live | forward | |

## Optic's own scores

| Score | Definition | Replay | Record |
|---|---|---|---|
| Swing composite | technicals 0.34, gamma 0.24, flow 0.20, news 0.12, macro 0.10, renormalised over present inputs; a material catalyst halves technicals (`swing.py:927`) | no | signal archive (6 days), paper ledger (since 2026-08) |
| Setups | a "conditions met" count, not a score | yes | signal_history since 2026-10-05 |
| Research grade S/A/B/Avoid | reward-to-risk ≥ 2.5 for S; earnings in the window caps at B (`research/swing_setup.py:462`) | yes with earnings dates | research_forecasts since 2026-10-14 |

## What this means for testing

* **Can be tested on history now:** price structure, momentum, participation, market and sector context, earnings
  timing and the price and volume reaction to it, option prices for entries from 2019 (weekly) and later (daily).
* **Forward only:** flow, GEX, flip, walls, VEX, the composite, news, the earnings calendar and estimates as they
  stood, intraday VWAP. Strategies E (positioning) and F (flow) and any news-conditioned rule need prospective
  collection. The signal archive collects some of it only for names a reader opens; the forward research book
  (below) collects it for every candidate it watches.
* **Repaint to avoid in research:** Optic's support/resistance levels. The research uses levels known the session
  before and swing pivots only once confirmed.
