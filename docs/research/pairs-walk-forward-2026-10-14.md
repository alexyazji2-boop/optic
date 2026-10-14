# Pairs trading, out of sample: twenty classic pairs (2026-10-14)

**Claim** (a trading post). When one of two related stocks runs ahead, buying the laggard and shorting the leader "tends to make money".

**Background.** The academic version is Gatev, Goetzmann and Rouwenhorst (Review of Financial Studies, 2006). They found profits in US pairs from 1962 that shrank after the 1990s.

**Method** (`app/analytics/pairs.py`; `pairs_walk_forward_study.py`).
- **Spread.** Dividend-adjusted daily closes. The spread is log A − (α + β log B), with α and β fitted by least squares on 252 sessions.
- **Rule.** Enter at |z| ≥ 2. Exit when z crosses 0. Stop at |z| 4. Give up after three half-lives.
- **Fills and costs.** Signals fill at the next close. Each leg pays 5 bp a side, and the short leg pays 0.5% a year borrow. Returns are on gross exposure.
- **Walk-forward.** Fit on 252 sessions, trade the next 126 with the fit frozen, roll forward by 126 over up to 15 years.
- **Windows with a hedge ratio at or below zero are skipped.** There, "short one, buy the other" is long or short both.
- **Two books.** Every window traded, and only windows whose formation year passed Engle-Granger at 5%.
- **Baseline.** The same number of trades and holding periods, on random days, with a coin-flip side. 500 runs.
- **Pairs.** KO/PEP, XOM/CVX, V/MA, HD/LOW, GOOGL/GOOG, COHR/LITE (named in the post's comments), JPM/BAC, UPS/FDX, MCD/YUM, WMT/TGT, MSFT/AAPL, GS/MS, LMT/NOC, CAT/DE, PG/CL, AMD/NVDA, T/VZ, UNP/CSX, SPY/IVV, EWA/EWC.

## Result

| | Every window | Only cointegrated windows |
|---|---|---|
| Pairs with a positive total | 3 of 20 | 7 of 20 |
| Pairs beating 80% of coin-flip books | 5 of 20 (chance: about 4) | 4 of 20 |
| Mean trade before any costs, pooled | 0.00% (95%: -0.07 to +0.07), 4,348 trades | +0.05% (95%: -0.05 to +0.15), 969 trades |

- **Cointegration rarely persists.** Formation years passed the 5% test 3% to 27% of the time for most pairs. The test then held into the next half-year in 0% to 50% of those cases.
- **The exceptions are near-identical assets.** GOOGL/GOOG passed 63% of the time and SPY/IVV 93%. Their gaps are smaller than the cost of trading them, so they lose too: SPY/IVV won 1% of its trades.
- **Best and worst.** GS/MS made +40% over 15 years of trading windows; WMT/TGT lost 66%.

**Reading.** The rule as the post states it has no edge in these pairs out of sample, even before costs. With costs it loses on most of them. Filtering on cointegration does not rescue it, because the relationship found in one year usually does not survive into the next.

None of this says that statistical arbitrage cannot work. Funds that run it trade hundreds of pairs, intraday, at institutional costs, with constant re-selection. It says that a handful of famous pairs, traded on daily closes at retail costs, gave nothing here.

**Verdict.** Unsupported as stated.

**A correction made during the test.** The first random baseline reused the rule's own sides. In a trending window that inherits the rule's bet against the trend, which made the rule look better than 99% of random books while it lost money. The baseline now flips a coin for each side (see `_random_book`).

**In the product.** The Pairs widget on the Chart tab shows:
- today's spread in standard deviations, the hedge ratio, the half-life and the cointegration result;
- the out-of-sample record for both books;
- how often the test held into the next half-year.

It does not present a stretched spread as a trade signal on its own.
