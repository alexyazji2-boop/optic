# Opening-range break with a VWAP retest: first test (2026-10-14)

**Rule** (from a trading post, implemented in `app/analytics/session_rules.py`). The price must:
1. close outside the first 30 minutes' range;
2. run at least one range width past the break;
3. not close back through VWAP on the way.

The entry is the first touch of VWAP after that. The post gives no exit. This test uses:
- a stop 0.5 range widths beyond the entry;
- a target at 2R;
- flat by the close;
- one trade a session, long and short.

**Data.** Regular-session 5-minute bars from Yahoo, the last 60 sessions (2026-07-21 to 2026-10-13), for 20 liquid names and ETFs: SPY QQQ IWM DIA XLF AAPL MSFT NVDA AMZN META TSLA PLTR AMD GOOGL JPM XOM UNH COST AVGO NFLX. The cost is 5 bp a side. Fills are cautious: entries rest at VWAP as of the previous close, and a bar that reaches both the stop and the target counts as stopped.

## Result

| Exits | Trades | Mean per trade | 95% interval | Winners |
|---|---|---|---|---|
| 0.5-range stop, 2R target (default) | 60 | -0.11% | -0.20 to -0.02 | 35% |
| No target, flat at the close | 60 | -0.13% | -0.22 to -0.03 | 30% |
| 1-range stop, 2R target | 60 | -0.15% | -0.28 to -0.03 | 32% |
| 1-range stop, no target | 60 | -0.16% | -0.28 to -0.04 | 32% |
| Extension of 0.5 ranges (default exits) | 249 | -0.10% | -0.16 to -0.03 | 36% |

- **The plain break**: the same sessions, entered on the first close outside the range with the same exits. It averaged -0.17% a trade per symbol, and it lost on all 20 symbols. The qualified retest lost less than the plain break on all 20.
- **Random timing**: the same trades entered at random times on the same days. Only 4 of 20 symbols beat 80% of those books.

**Reading.** In this window the three conditions filter out most bad breakouts: there are about 3 setups per symbol in 60 sessions, against about 52 plain breaks. That is the visible effect. What survives the filter still lost money on average, under every exit tried. Treat this as unsupported in this window.

**Limits.** The intervals are naive. The 60 trades share days and market moves, so they are not independent, and the true uncertainty is wider. Sixty sessions is one market regime. The validation program should re-test the rule on a longer intraday archive before it is classified.
