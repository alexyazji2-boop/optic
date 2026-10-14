# Has the straddle priced the move? Ten names (2026-10-14)

**Question.** The Options tab says what the at-the-money straddle is priced for. Has that been a fair price for each stock?

**Data.** DoltHub's `option_chain` table, which has a few strikes and one monthly expiry per date, and no ETFs except SPY in practice (QQQ and IWM returned nothing). Sampled each Monday from 2024-10-07 to 2026-08-31: the first expiry 21 to 50 days out (a median of 25 days) and the strike nearest the close (median 0.3% away). Implied move = straddle mid / price. Realised = |close at expiry / price − 1| (`straddle_calibration.py`).

**What is fair.** An at-the-money straddle costs about the expected absolute move. So at a fair price, the mean of realised / implied is about 1, and the move beats the straddle about 42% of the time, not 50%: for normal moves, P(|Z| > 0.798) is 42.5%.

## Result

| | Samples | Mean realised / implied (95%) | Moved further than the straddle |
|---|---|---|---|
| SPY | 99 | 0.81 (0.55 to 1.06) | 39% |
| NVDA | 99 | 0.80 (0.53 to 1.07) | 31% |
| KO | 100 | 0.92 (0.59 to 1.24) | 35% |
| XOM | 99 | 0.94 (0.63 to 1.26) | 40% |
| JPM | 99 | 0.95 (0.67 to 1.22) | 42% |
| AMZN | 99 | 0.98 (0.69 to 1.26) | 46% |
| META | 100 | 1.01 (0.72 to 1.31) | 43% |
| TSLA | 100 | 1.03 (0.68 to 1.39) | 42% |
| PLTR | 99 | 1.07 (0.70 to 1.44) | 42% |
| AAPL | 100 | 1.18 (0.90 to 1.46) | 56% |

The intervals use a quarter of the samples: weekly samples on a 25-day horizon overlap about four times.

**Reading.**
- Pooled, the straddle was about fair: a mean of 0.97.
- SPY and NVDA lean dear and AAPL leans cheap, but no single name's interval excludes 1. Two years of monthly options cannot tell one stock's straddles from fair.
- The Options tab says exactly that, per name, beside the straddle.

**In the product** (`app/analytics/straddle_calibration.py`, data in `app/analytics/straddle_calibration.json`, behind `OPTIC_DOLTHUB` with attribution). A lean is stated only when the interval clears 1.
