# Do stocks sweep stops past round numbers? (2026-10-14)

**Claim** (a trading post). Stop losses cluster at round numbers. Price runs through the level, triggers the stops just past it, then reverses. So buffer the stop past the round number by a fraction of ATR.

The post cites a New York Fed staff report. Carol Osler's work there (Journal of Finance, 2003) found stop-loss orders clustered just beyond round numbers, but in currency order books. This note checks the idea on stocks.

**Method** (`stops_round_numbers_study.py`).
- **Data.** Regular-session 5-minute bars from Yahoo for the 60 sessions to 2026-10-13. Twenty liquid US names and ETFs: SPY QQQ IWM DIA XLF AAPL MSFT NVDA AMZN META TSLA PLTR AMD GOOGL JPM XOM UNH COST AVGO NFLX.
- **What was measured.** For each level, take its first cross in each session. Record how far price went past the level before the first 5-minute close back on the near side, capped at the session's end. The distance is in units of the prior 14-day ATR, known before the session.
- **Round levels.** Multiples of $10 above $100, of $5 from $20 to $100, and of $1 below $20.
- **Control.** The same grid shifted by 0.37 of a step: arbitrary prices with the same spacing.

## Result

Share of crosses that overshot by more than b ATR:

| b (ATR) | Round, falling | Control, falling | Round, rising | Control, rising |
|---|---|---|---|---|
| 0.05 | 53.8% | 44.6% | 50.3% | 48.9% |
| 0.10 | 36.9% | 28.2% | 34.0% | 32.4% |
| 0.15 | 27.9% | 22.9% | 25.9% | 24.9% |
| 0.25 | 18.9% | 14.1% | 16.7% | 17.7% |
| 0.50 | 7.1% | 4.9% | 7.1% | 7.0% |
| Came back the same session | 86.2% | 91.0% | 88.9% | 88.4% |
| Crosses | 567 | 554 | 576 | 571 |

**Reading.**
- **Falls through round numbers overshoot more.** At 0.10 ATR the gap is about 9 points (37% against 28%). That fits stop-loss sells resting just below round numbers.
- **Rises show no clear difference.**
- **The general effect is bigger.** At every level, most crosses came back within the session. So a stop sitting right at a level is mostly taken by a move that then reverses.
- **Buffering pays off steeply.** Moving a stop from 0.10 to 0.25 ATR past the level roughly halves how often a cross reaches it, and 0.5 ATR cuts it to about 7%. The cost is more loss a share when the stop is hit.

**Verdict.** Partly supported. There is a round-number effect in stocks, but it is modest and one-sided. The advice to buffer a stop past a level is well supported in this sample, round number or not.

**Limits.**
- The crosses are not independent: the same sessions and the same market moves run across symbols.
- Sixty sessions is one regime.
- Where orders actually rest is not public. Round numbers are a proxy for it.

The validation program should repeat this on a longer intraday archive and on daily swing stops.

**In the product.** The Stop check widget on the Chart tab (`app/analytics/stops.py`, `/api/stop-check`) uses these figures:
- A round number within 0.25 ATR of a stop counts as at the stop.
- The stop is moved a buffer past it, 0.25 ATR by default, and never closer to the price.
- The panel shows both shares above and the extra risk a share.
