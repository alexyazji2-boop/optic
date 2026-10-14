# Is a low IV rank a time to buy options? (2026-10-14)

**Claim** (a trading post). Buy options when IV rank is 30 or below, when they are cheap.

**Data.** DoltHub's `post-no-preference/options` daily volatility history: 30-day at-the-money IV and trailing 30-day realised volatility. Calibrated before use: on SPY its IV tracks the VIX at 0.987. Coverage: 1,423 symbols with a full year of history before each day, 304,314 stock-days from 2025-10-01 to 2026-09-10 (`ivrank_cheapness_study.py`).

**Method.**
- **IV rank.** Today's IV within its prior 252-session range.
- **Outcome.** The realised volatility of the 30 days that followed, which is the store's trailing HV 21 sessions later.
- **Cheap after the fact** means the realised vol that followed beat implied. A delta-hedged long option earns roughly in proportion to realised² − implied², so the mean variance ratio is shown as well.
- **Overlap.** Days overlap about 21 times, so read the differences between bands, not significance tests.

## Result

| IV rank | Stock-days | Median IV | Median realised after | Realised beat implied | Mean variance ratio |
|---|---|---|---|---|---|
| 0-10 | 20,278 | 26.6% | 25.5% | 38.1% | 1.09 |
| 10-20 | 45,693 | 30.6% | 28.1% | 32.9% | 0.96 |
| 20-30 | 58,519 | 34.2% | 30.3% | 28.7% | 0.92 |
| 30-50 | 96,042 | 38.6% | 33.7% | 28.1% | 0.90 |
| 50-70 | 51,141 | 44.6% | 38.6% | 29.1% | 0.91 |
| 70-90 | 23,246 | 50.3% | 43.2% | 27.5% | 0.89 |
| 90-100 | 9,395 | 61.3% | 51.2% | 25.0% | 0.83 |
| All | 304,314 | | | 29.6% | |

- **Implied usually beats realised.** It beat the volatility that followed on about 70% of days.
- **IV below recent realised vol** (IV under the trailing 30-day HV) was followed by more movement than implied on 45.4% of days, against 22.5% otherwise.
- **The regime matters.** By month, the share of days where realised beat implied ranged from 16% (September 2026) to 49% (January 2026).

**Reading.**
- Options usually cost more than the moves they insured: the variance risk premium.
- A low IV rank narrows the premium but rarely reverses it. Even in the lowest tenth, realised beat implied only 38% of the time; in variance terms that band came out about fair (1.09), because of fat tails.
- IV below recent realised volatility was the stronger sign of cheapness, and still under half.

**Verdict.** "Buy when IV rank ≤ 30" is unsupported as a reason options are cheap. Rank 20–30 days were followed by more movement than implied only 29% of the time, about the same as all days.

**Limits.** One year, which is one regime. The ETFs' history is included but the sample is mostly single stocks. These are outcomes for at-the-money vol, not for any particular trade.

**In the product** (`app/analytics/iv_cheapness.py`, behind `OPTIC_DOLTHUB`). The Options tab's "Cheap or dear?" line gives:
- the band's measured share for today's rank;
- whether IV sits above or below realised vol, with the share for that;
- the stock's own record of implied against what followed.

It does not call options cheap.
