# Reconciliation against the providers (Phase 09)

Optic's figures, read through its own API on the local server (live delayed data), against the same figures read
from the configured providers directly: Yahoo Finance through a separate yfinance client with its own cache, and
the SEC's companyfacts API. Derived figures (the day's change, moving averages, RSI, MACD, Bollinger bands, an
anchored VWAP, dividend yields, the 52-week range, trailing revenue, the market read's inputs) are recomputed
from the providers' raw values. A figure with no independent reference is UNVERIFIED with the reason; no
reference value is invented. Tool: `~/Optic/work/post-demo-ultra-2026-10-29/tools/phase09_recon.py`; raw rows
and every API answer: `phase09/recon/`.

**Result: 278 rows: 277 PASS, 1 UNVERIFIED.**

## How the run got here

The first run (2026-10-30, about 2 AM ET, 248 rows) found 9 failures. Six were the reference's own mistakes, and
the reference was corrected to the definition Optic states:

- a trailing dividend window that caught five quarterly payments;
- one share class's shares for BRK-B's market cap (implied shares count both);
- a forward yield checked against a trailing one;
- four quarterly revenue facts where the fiscal fourth quarter is filed only inside the 10-K (the reference
  is now the textbook trailing twelve months: the fiscal year, plus this year's year to date, less last
  year's).

Three were Optic's (KO, JPM, TSM): the dividend yield was Yahoo's own percent, worked at another moment's price
and rounded to two places, beside a price it did not match (2.31% beside 2.12 / 92.82 = 2.28%). It is now the
dividend rate over the price shown (BUG-136, D-068).

Later rows (MACD, Bollinger, VWAP, earnings dates, news, the market read) were added afterwards. Their first
run's two rows needing changes were also reference mistakes:

- KO's report date had passed, and the right expectation is that no passed date is shown as next;
- yfinance's `Ticker.news` came back empty, so the provider's headlines are read through its search.

| Metric | Symbol | Requested (UTC) | Provider | Expected | Actual (Optic) | Difference | Explanation | Outcome |
|---|---|---|---|---|---|---|---|---|
| price (last regular trade) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 769.36 | 769.36 | 0 |  | PASS |
| previous close | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 772.31 | 772.31 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client), recomputed | -0.382 | -0.381973 | 2.7e-05 |  | PASS |
| day high | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 770.76 | 770.76 | 0 |  | PASS |
| day low | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 766.62 | 766.62 | 0 |  | PASS |
| volume | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 39377091 | 39,377,091 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) |  |  |  | passed through from the feed | PASS |
| trailing P/E | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 24.4263 | 24.4263 | 0 |  | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 0.0099 | 0.0099 | -1.73472e-18 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| distribution yield against the last four distributions / price | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client), recomputed | 0.009856 | 0.0099 | 4.4e-05 | Optic calls a fund's figure the trailing distribution yield | PASS |
| 52-week high | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 781.62 | 781.62 | 0 |  | PASS |
| 52-week low | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 629.28 | 629.28 | 0 |  | PASS |
| 52-week high against the year's daily highs | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client), recomputed | 781.62 | 781.62 | 4.88281e-06 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 764.73 | 764.73 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 0 | 0 | 0 |  | PASS |
| last trade time (UTC) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:00 | 2026-10-29T20:00:00 |  |  | PASS |
| company name | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | State Street SPDR S&P 500 ETF Trust | State Street SPDR S&P 500 ETF Trust |  | long name, else short name | PASS |
| quote currency | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 771.164 | 771.164 | 0 |  | PASS |
| SMA 50 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 767.632 | 767.632 | 0 |  | PASS |
| SMA 200 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 728.527 | 728.527 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 50.5697 | 50.5697 | 1.6e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 50.5697 | 50.5697 | 1.6e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 769.36 | 769.36 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 772.31 | 772.31 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | 759.97 | 759.97 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | [["2026-06-18", 1.904], ["2026-09-18", 1.889]] | [["2026-06-18", 1.904], ["2026-09-18", 1.889]] |  |  | PASS |
| last split (date, ratio) | SPY | 2026-10-30T06:42:29Z | Yahoo Finance (yfinance, separate client) | [] | [] |  |  | PASS |
| MACD (12, 26) | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 0.042141 | 0.042141 | 0 | exponential averages seeded at the first close, as Optic's; the frame's length moves the last digits | PASS |
| MACD signal (9) | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 0.378316 | 0.378316 | 0 |  | PASS |
| Bollinger upper (20, 2, population deviation) | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 781.989 | 781.989 | 0 |  | PASS |
| Bollinger lower (20, 2, population deviation) | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 760.339 | 760.339 | 0 |  | PASS |
| anchored VWAP from 2026-07-01 (typical price x volume) | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) daily bars, recomputed | 760.96 | 760.96 | 0 | Optic rounds the line to cents | PASS |
| next earnings date | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) calendar |  |  |  | Yahoo's calendar gave no date to compare | UNVERIFIED |
| news headlines found in the provider's own feed | SPY | 2026-10-30T06:43:11Z | Yahoo Finance (yfinance, separate client) news | 6 | 6 | 0 | every Optic headline should be one of Yahoo's (Optic may add other sources' items, which would show here) | PASS |
| price (last regular trade) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 348.91 | 348.91 | 0 |  | PASS |
| previous close | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 343.83 | 343.83 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client), recomputed | 1.4775 | 1.47748 | -2e-05 |  | PASS |
| day high | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 351.43 | 351.43 | 0 |  | PASS |
| day low | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 347.3 | 347.3 | 0 |  | PASS |
| volume | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 41340227 | 41,340,227 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 5092055449600 | 5,092,055,449,600 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client), recomputed | 5,092,055,343,800 | 5,092,055,449,600 | 105,800 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 40.0126 | 40.0126 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client), recomputed | 40.0126 | 40.0126 | 3.21101e-07 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 0.0031 | 0.00309535 | -4.6459e-06 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| dividend yield against the dividend rate / price | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client), recomputed | 0.003095 | 0.00309535 | 3.54103e-07 | Optic's definition (a year of dividends at the current rate); Yahoo rounds its percent to two places | PASS |
| 52-week high | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 351.73 | 351.73 | 0 |  | PASS |
| 52-week low | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 243.42 | 243.42 | 0 |  | PASS |
| 52-week high against the year's daily highs | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client), recomputed | 351.73 | 351.73 | -1.09863e-05 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 352.05 | 352.05 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 15 | 15 | 0 |  | PASS |
| last trade time (UTC) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:01 | 2026-10-29T20:00:01 |  |  | PASS |
| company name | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | Apple Inc. | Apple Inc. |  | long name, else short name | PASS |
| quote currency | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 341.537 | 341.537 | 0 |  | PASS |
| SMA 50 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 332.374 | 332.374 | 0 |  | PASS |
| SMA 200 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 296.133 | 296.133 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 61.3854 | 61.3854 | 1.4e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 61.3854 | 61.3854 | 1.4e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 348.91 | 348.91 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 343.83 | 343.83 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | 347.73 | 347.73 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | [["2026-05-11", 0.27], ["2026-08-10", 0.27]] | [["2026-05-11", 0.27], ["2026-08-10", 0.27]] |  |  | PASS |
| last split (date, ratio) | AAPL | 2026-10-30T06:42:33Z | Yahoo Finance (yfinance, separate client) | [["2020-08-31", 4.0]] | [["2020-08-31", 4.0]] |  |  | PASS |
| MACD (12, 26) | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 4.05912 | 4.05912 | 0 | exponential averages seeded at the first close, as Optic's; the frame's length moves the last digits | PASS |
| MACD signal (9) | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 4.06146 | 4.06146 | 0 |  | PASS |
| Bollinger upper (20, 2, population deviation) | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 350.975 | 350.975 | 0 |  | PASS |
| Bollinger lower (20, 2, population deviation) | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 332.098 | 332.098 | 0 |  | PASS |
| anchored VWAP from 2026-07-01 (typical price x volume) | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) daily bars, recomputed | 324.79 | 324.79 | 0 | Optic rounds the line to cents | PASS |
| next earnings date | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) calendar | 2026-11-02 | 2026-11-02 |  | Yahoo's calendar; a company confirms its own date in a press release | PASS |
| news headlines found in the provider's own feed | AAPL | 2026-10-30T06:43:09Z | Yahoo Finance (yfinance, separate client) news | 12 | 12 | 0 | every Optic headline should be one of Yahoo's (Optic may add other sources' items, which would show here) | PASS |
| revenue, trailing twelve months | AAPL | 2026-10-30T06:43:15Z | SEC companyfacts, RevenueFromContractWithCustomerExcludingAssessedTax (FY to 2025-09-27 plus the year to 2026-06-27, less the year before's same span) | 466,823,000,000 | 466,823,000,000 | 0 | the textbook TTM, independent of Optic's quarter-by-quarter method | PASS |
| price (last regular trade) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 213.66 | 213.66 | 0 |  | PASS |
| previous close | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 215.38 | 215.38 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client), recomputed | -0.7986 | -0.798589 | 1.1e-05 |  | PASS |
| day high | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 215.32 | 215.32 | 0 |  | PASS |
| day low | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 212.08 | 212.08 | 0 |  | PASS |
| volume | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 75456091 | 75,456,091 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 5159248199680 | 5,159,248,199,680 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client), recomputed | 5,159,248,020,000 | 5,159,248,199,680 | 179,680 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 27.0114 | 27.0114 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client), recomputed | 27.0114 | 27.0114 | 1.99747e-06 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 0.0046 | 0.00468033 | 8.03332e-05 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| dividend yield against the dividend rate / price | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client), recomputed | 0.00468 | 0.00468033 | 3.3324e-07 | Optic's definition (a year of dividends at the current rate); Yahoo rounds its percent to two places | PASS |
| 52-week high | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 243.37 | 243.37 | 0 |  | PASS |
| 52-week low | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 164.27 | 164.27 | 0 |  | PASS |
| 52-week high against the year's daily highs | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client), recomputed | 243.37 | 243.37 | 4.88281e-06 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 210.147 | 210.147 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 15 | 15 | 0 |  | PASS |
| last trade time (UTC) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:00 | 2026-10-29T20:00:00 |  |  | PASS |
| company name | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | NVIDIA Corporation | NVIDIA Corporation |  | long name, else short name | PASS |
| quote currency | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 222.925 | 222.925 | 0 |  | PASS |
| SMA 50 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 221.993 | 221.993 | 0 |  | PASS |
| SMA 200 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 204.277 | 204.277 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 42.2691 | 42.2691 | -4.7e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 42.2691 | 42.2691 | -4.7e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 213.66 | 213.66 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 215.38 | 215.38 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | 210.96 | 210.96 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | [["2026-06-04", 0.25], ["2026-09-10", 0.25]] | [["2026-06-04", 0.25], ["2026-09-10", 0.25]] |  |  | PASS |
| last split (date, ratio) | NVDA | 2026-10-30T06:42:36Z | Yahoo Finance (yfinance, separate client) | [["2024-06-10", 10.0]] | [["2024-06-10", 10.0]] |  |  | PASS |
| MACD (12, 26) | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | -2.84042 | -2.84042 | 0 | exponential averages seeded at the first close, as Optic's; the frame's length moves the last digits | PASS |
| MACD signal (9) | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | -1.81147 | -1.81147 | 0 |  | PASS |
| Bollinger upper (20, 2, population deviation) | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 241.131 | 241.131 | 0 |  | PASS |
| Bollinger lower (20, 2, population deviation) | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 204.719 | 204.719 | 0 |  | PASS |
| anchored VWAP from 2026-07-01 (typical price x volume) | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) daily bars, recomputed | 216.15 | 216.15 | 0 | Optic rounds the line to cents | PASS |
| next earnings date | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) calendar | 2026-11-17 | 2026-11-17 |  | Yahoo's calendar; a company confirms its own date in a press release | PASS |
| news headlines found in the provider's own feed | NVDA | 2026-10-30T06:43:10Z | Yahoo Finance (yfinance, separate client) news | 5 | 5 | 0 | every Optic headline should be one of Yahoo's (Optic may add other sources' items, which would show here) | PASS |
| revenue, trailing twelve months | NVDA | 2026-10-30T06:43:17Z | SEC companyfacts, Revenues (FY to 2026-01-25 plus the year to 2026-07-26, less the year before's same span) | 302,970,000,000 | 302,969,000,000 | -1e+06 | the textbook TTM, independent of Optic's quarter-by-quarter method | PASS |
| price (last regular trade) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 530.14 | 530.14 | 0 |  | PASS |
| previous close | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 531.01 | 531.01 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client), recomputed | -0.1638 | -0.163838 | -3.8e-05 |  | PASS |
| day high | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 540.97 | 540.97 | 0 |  | PASS |
| day low | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 519.56 | 519.56 | 0 |  | PASS |
| volume | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 39119013 | 39,119,013 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 3936578961408 | 3,936,578,961,408 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client), recomputed | 3,936,578,686,599 | 3,936,578,961,408 | 274,809 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 27.6691 | 27.6691 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client), recomputed | 27.6691 | 27.6691 | 1.70355e-06 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 0.0074 | 0.00739427 | -5.72679e-06 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| dividend yield against the dividend rate / price | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client), recomputed | 0.007394 | 0.00739427 | 2.73211e-07 | Optic's definition (a year of dividends at the current rate); Yahoo rounds its percent to two places | PASS |
| 52-week high | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 551.15 | 551.15 | 0 |  | PASS |
| 52-week low | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 349.2 | 349.2 | 0 |  | PASS |
| 52-week high against the year's daily highs | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client), recomputed | 551.15 | 551.15 | -2.44141e-05 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 529.052 | 529.052 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 15 | 15 | 0 |  | PASS |
| last trade time (UTC) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:01 | 2026-10-29T20:00:01 |  |  | PASS |
| company name | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | Microsoft Corporation | Microsoft Corporation |  | long name, else short name | PASS |
| quote currency | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 530.762 | 530.762 | 0 |  | PASS |
| SMA 50 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 512.095 | 512.095 | 0 |  | PASS |
| SMA 200 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 437.614 | 437.614 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 55.351 | 55.351 | -2.6e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 55.351 | 55.351 | -2.6e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 530.14 | 530.14 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 531.01 | 531.01 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | 524.51 | 524.51 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | [["2026-05-21", 0.91], ["2026-08-20", 0.91]] | [["2026-05-21", 0.91], ["2026-08-20", 0.91]] |  |  | PASS |
| last split (date, ratio) | MSFT | 2026-10-30T06:42:40Z | Yahoo Finance (yfinance, separate client) | [["2003-02-18", 2.0]] | [["2003-02-18", 2.0]] |  |  | PASS |
| revenue, trailing twelve months | MSFT | 2026-10-30T06:43:16Z | SEC companyfacts, RevenueFromContractWithCustomerExcludingAssessedTax (FY to 2026-06-30 plus the year to 2026-09-30, less the year before's same span) | 346,445,000,000 | 346,445,000,000 | 0 | the textbook TTM, independent of Optic's quarter-by-quarter method | PASS |
| price (last regular trade) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 92.82 | 92.82 | 0 |  | PASS |
| previous close | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 91.73 | 91.73 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client), recomputed | 1.1883 | 1.18827 | -3e-05 |  | PASS |
| day high | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 93.16 | 93.16 | 0 |  | PASS |
| day low | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 92.03 | 92.03 | 0 |  | PASS |
| volume | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 15376443 | 15,376,443 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 399302557696 | 399,302,557,696 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client), recomputed | 399,302,574,735 | 399,302,557,696 | -17,038.7 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 27.3805 | 27.3805 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client), recomputed | 27.3805 | 27.3805 | -9.73451e-07 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 0.0231 | 0.0228399 | -0.000260095 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| dividend yield against the dividend rate / price | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client), recomputed | 0.02284 | 0.0228399 | -9.48072e-08 | Optic's definition (a year of dividends at the current rate); Yahoo rounds its percent to two places | PASS |
| 52-week high | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 95.37 | 95.37 | 0 |  | PASS |
| 52-week low | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 67.27 | 67.27 | 0 |  | PASS |
| 52-week high against the year's daily highs | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client), recomputed | 95.37 | 95.37 | -2.74658e-06 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 94.0982 | 94.0982 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 20 | 20 | 0 |  | PASS |
| last trade time (UTC) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:02 | 2026-10-29T20:00:02 |  |  | PASS |
| company name | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | The Coca-Cola Company | The Coca-Cola Company |  | long name, else short name | PASS |
| quote currency | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 90.681 | 90.681 | 0 |  | PASS |
| SMA 50 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 89.3928 | 89.3928 | 0 |  | PASS |
| SMA 200 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 82.023 | 82.023 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 58.6513 | 58.6513 | -1.9e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 58.6513 | 58.6513 | -1.9e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 92.82 | 92.82 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 91.73 | 91.73 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | 92.71 | 92.71 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | [["2026-06-15", 0.53], ["2026-09-15", 0.53]] | [["2026-06-15", 0.53], ["2026-09-15", 0.53]] |  |  | PASS |
| last split (date, ratio) | KO | 2026-10-30T06:42:45Z | Yahoo Finance (yfinance, separate client) | [["2012-08-13", 2.0]] | [["2012-08-13", 2.0]] |  |  | PASS |
| MACD (12, 26) | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 1.26178 | 1.26178 | 0 | exponential averages seeded at the first close, as Optic's; the frame's length moves the last digits | PASS |
| MACD signal (9) | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 1.25919 | 1.25919 | 0 |  | PASS |
| Bollinger upper (20, 2, population deviation) | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 96.5415 | 96.5415 | 0 |  | PASS |
| Bollinger lower (20, 2, population deviation) | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 84.8205 | 84.8205 | 0 |  | PASS |
| anchored VWAP from 2026-07-01 (typical price x volume) | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) daily bars, recomputed | 87.7 | 87.7 | 0 | Optic rounds the line to cents | PASS |
| next earnings date (Yahoo still lists the report of 2026-10-27) | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) calendar | no passed date shown as next | no passed date shown as next |  | a passed date is not the next report | PASS |
| news headlines found in the provider's own feed | KO | 2026-10-30T06:43:12Z | Yahoo Finance (yfinance, separate client) news | 12 | 12 | 0 | every Optic headline should be one of Yahoo's (Optic may add other sources' items, which would show here) | PASS |
| revenue, trailing twelve months | KO | 2026-10-30T06:43:18Z | SEC companyfacts, Revenues (FY to 2025-12-31 plus the year to 2026-10-02, less the year before's same span) | 51,054,000,000 | 51,054,000,000 | 0 | the textbook TTM, independent of Optic's quarter-by-quarter method | PASS |
| price (last regular trade) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 343.58 | 343.58 | 0 |  | PASS |
| previous close | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 339.3 | 339.3 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client), recomputed | 1.2614 | 1.26142 | 2e-05 |  | PASS |
| day high | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 345.733 | 345.733 | 0 |  | PASS |
| day low | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 342.36 | 342.36 | 0 |  | PASS |
| volume | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 5792758 | 5.79276e+06 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 912411066368 | 912,411,066,368 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client), recomputed | 912,411,048,000 | 912,411,066,368 | 18,368 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 14.4119 | 14.4119 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client), recomputed | 14.4119 | 14.4119 | -7.51678e-07 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 0.0195 | 0.0192095 | -0.0002905 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| dividend yield against the dividend rate / price | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client), recomputed | 0.019209 | 0.0192095 | 4.99971e-07 | Optic's definition (a year of dividends at the current rate); Yahoo rounds its percent to two places | PASS |
| 52-week high | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 366.5 | 366.5 | 0 |  | PASS |
| 52-week low | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 279.1 | 279.1 | 0 |  | PASS |
| 52-week high against the year's daily highs | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client), recomputed | 366.5 | 366.5 | 0 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 345.25 | 345.25 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 20 | 20 | 0 |  | PASS |
| last trade time (UTC) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:02 | 2026-10-29T20:00:02 |  |  | PASS |
| company name | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | JPMorgan Chase & Co. | JPMorgan Chase & Co. |  | long name, else short name | PASS |
| quote currency | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 334.555 | 334.555 | 0 |  | PASS |
| SMA 50 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 343.577 | 343.577 | 0 |  | PASS |
| SMA 200 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 322.802 | 322.802 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 58.0668 | 58.0668 | 4e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 58.0668 | 58.0668 | 4e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 343.58 | 343.58 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 339.3 | 339.3 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | 331.58 | 331.58 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | [["2026-07-06", 1.5], ["2026-10-06", 1.65]] | [["2026-07-06", 1.5], ["2026-10-06", 1.65]] |  |  | PASS |
| last split (date, ratio) | JPM | 2026-10-30T06:42:52Z | Yahoo Finance (yfinance, separate client) | [["2000-06-12", 1.5]] | [["2000-06-12", 1.5]] |  |  | PASS |
| revenue, trailing twelve months | JPM | 2026-10-30T06:43:19Z | SEC companyfacts, RevenuesNetOfInterestExpense (FY to 2025-12-31 plus the year to 2026-06-30, less the year before's same span) | 199,408,000,000 | 199,408,000,000 | 0 | the textbook TTM, independent of Optic's quarter-by-quarter method | PASS |
| price (last regular trade) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 541.96 | 541.96 | 0 |  | PASS |
| previous close | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 540.34 | 540.34 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client), recomputed | 0.2998 | 0.29981 | 1e-05 |  | PASS |
| day high | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 548.769 | 548.769 | 0 |  | PASS |
| day low | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 541.81 | 541.81 | 0 |  | PASS |
| volume | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 4148843 | 4.14884e+06 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 1160179089408 | 1,160,179,089,408 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client), recomputed | 1,160,179,079,956 | 1,160,179,089,408 | 9,451.76 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 13.6308 | 13.6308 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client), recomputed | 13.6308 | 13.6308 | 1.29175e-06 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 0 | 0 | 0 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| 52-week high | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 549.96 | 549.96 | 0 |  | PASS |
| 52-week low | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 464.01 | 464.01 | 0 |  | PASS |
| 52-week high against the year's daily highs | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client), recomputed | 549.96 | 549.96 | -2.19727e-05 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 545.05 | 545.05 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 20 | 20 | 0 |  | PASS |
| last trade time (UTC) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:02 | 2026-10-29T20:00:02 |  |  | PASS |
| company name | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | Berkshire Hathaway Inc. | Berkshire Hathaway Inc. |  | long name, else short name | PASS |
| quote currency | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 527.083 | 527.083 | 0 |  | PASS |
| SMA 50 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 514.199 | 514.199 | 0 |  | PASS |
| SMA 200 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 495.497 | 495.497 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 66.4415 | 66.4415 | 2e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 66.4415 | 66.4415 | 2e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 541.96 | 541.96 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 540.34 | 540.34 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | 542.19 | 542.19 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | [] | [] |  |  | PASS |
| last split (date, ratio) | BRK-B | 2026-10-30T06:43:04Z | Yahoo Finance (yfinance, separate client) | [["2010-01-21", 50.0]] | [["2010-01-21", 50.0]] |  |  | PASS |
| price (last regular trade) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 431.81 | 431.81 | 0 |  | PASS |
| previous close | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 439.51 | 439.51 | 0 |  | PASS |
| change % (price / previous close - 1) x 100 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client), recomputed | -1.752 | -1.75195 | 5e-05 |  | PASS |
| day high | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 436.225 | 436.225 | 0 |  | PASS |
| day low | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 428.43 | 428.43 | 0 |  | PASS |
| volume | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 8315268 | 8.31527e+06 | 0 | Yahoo revises the day's volume after the close | PASS |
| market cap | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 2239571427328 | 2,239,571,427,328 | 0 | passed through from the feed | PASS |
| market cap against implied shares outstanding x price | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client), recomputed | 2,239,571,343,554 | 2,239,571,427,328 | 83,774.5 | implied shares count every share class (BRK: A and B) | PASS |
| trailing P/E | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 27.9851 | 27.9851 | 0 |  | PASS |
| trailing P/E against price / trailing EPS | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client), recomputed | 27.9851 | 27.9851 | 2.72197e-08 | Yahoo computes the ratio at its own last price | PASS |
| dividend yield (Optic fraction against Yahoo percent / 100) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 0.0086 | 0.00873069 | 0.000130692 | units: Yahoo percent, Optic fraction. Yahoo works its percent at another moment's price and rounds it to two places; Optic works the rate over its own price (Phase 09), so they agree to about 0.05 points | PASS |
| dividend yield against the dividend rate / price | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client), recomputed | 0.008731 | 0.00873069 | -3.08261e-07 | Optic's definition (a year of dividends at the current rate); Yahoo rounds its percent to two places | PASS |
| 52-week high | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 487.47 | 487.47 | 0 |  | PASS |
| 52-week low | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 266.82 | 266.82 | 0 |  | PASS |
| 52-week high against the year's daily highs | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client), recomputed | 487.47 | 487.47 | -1.2207e-06 | Yahoo's range uses intraday highs over its own 52 weeks | PASS |
| post-market price | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 419.5 | 419.5 | 0 | the feed's own extended-hours print | PASS |
| stated exchange delay (minutes) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 20 | 20 | 0 |  | PASS |
| last trade time (UTC) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 2026-10-29T20:00:02 | 2026-10-29T20:00:02 |  |  | PASS |
| company name | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | Taiwan Semiconductor Manufacturing Company Limited | Taiwan Semiconductor Manufacturing Company Limited |  | long name, else short name | PASS |
| quote currency | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| SMA 20 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 440.966 | 440.966 | 0 |  | PASS |
| SMA 50 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 435.115 | 435.115 | 0 |  | PASS |
| SMA 200 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 399.767 | 399.767 | 0 |  | PASS |
| RSI 14 (Wilder, simple-mean seed) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 48.148 | 48.148 | -3.3e-05 | Optic seeds Wilder's smoothing exponentially; the two converge after a few hundred bars | PASS |
| RSI 14 (Wilder, exponential seed, Optic's method) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) daily closes, recomputed | 48.148 | 48.148 | -3.3e-05 | same method; any gap is the frame's length | PASS |
| daily close 2026-10-29 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 431.81 | 431.81 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-28 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 439.51 | 439.51 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| daily close 2026-10-23 | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | 418.51 | 418.51 | 0 | split-adjusted, not dividend-adjusted, on both sides | PASS |
| last two dividends (date, amount) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | [["2026-06-11", 0.955], ["2026-09-16", 1.107]] | [["2026-06-11", 0.955], ["2026-09-16", 1.107]] |  |  | PASS |
| last split (date, ratio) | TSM | 2026-10-30T06:43:07Z | Yahoo Finance (yfinance, separate client) | [["2009-07-15", 1.005]] | [["2009-07-15", 1.005]] |  |  | PASS |
| market read: S&P 500 20-day change (%) | ^GSPC | 2026-10-30T06:43:13Z | Yahoo Finance ^GSPC daily closes, recomputed | 0.704 | 0.704 | 0 | twenty sessions back; the read is built at its own time | PASS |
| price | ^GSPC | 2026-10-30T06:43:20Z | Yahoo Finance (yfinance, separate client) | 7,720.39 | 7,720.39 | 0 |  | PASS |
| previous close | ^GSPC | 2026-10-30T06:43:20Z | Yahoo Finance (yfinance, separate client) | 7,743.98 | 7,743.98 | 0 |  | PASS |
| quote currency | ^GSPC | 2026-10-30T06:43:20Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |
| market read: VIX level | ^VIX | 2026-10-30T06:43:13Z | Yahoo Finance ^VIX | 17.2 | 17.2 | 0 | the read is built at its own time and rounded to one place | PASS |
| price | BTC-USD | 2026-10-30T06:43:20Z | Yahoo Finance (yfinance, separate client) | 78,391.9 | 78,391.9 | 0 | a 24-hour market moves between the two reads | PASS |
| previous close | BTC-USD | 2026-10-30T06:43:20Z | Yahoo Finance (yfinance, separate client) | 77,791.4 | 77,791.4 | 0 |  | PASS |
| quote currency | BTC-USD | 2026-10-30T06:43:20Z | Yahoo Finance (yfinance, separate client) | USD | USD |  |  | PASS |

## Not reconciled, and why

- **Real-time quotes:** not supported without a Tradier token, which this deployment does not have.
- **Intraday open interest and option bid/ask times:** Yahoo gives neither.
- **Currency conversion:** only inside Brokerage totals, covered by scenario H.
- **Brokerage figures:** a sandbox account's, recomputed in scenario H (TEST_RESULTS, Phase 09).
- **Regular-session freshness labels:** the run fell outside market hours (overnight, Friday 2026-10-30), so
  in-session quotes were not compared live. The session rules are tested against NYSE's published calendar
  instead.

