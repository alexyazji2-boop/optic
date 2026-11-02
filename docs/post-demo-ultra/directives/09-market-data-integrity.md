<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 09 — COMPLETE MARKET DATA INTEGRITY AND CROSS-FEATURE CONSISTENCY AUDIT
Read all previous phase reports.
Your objective is to verify that Optic displays accurate, internally consistent, appropriately timestamped information across every feature.
A visually polished terminal with incorrect financial data is unacceptable.
1. Inventory all financial-data pathways
Identify each data provider, API endpoint, cache, calculation, database table, and frontend component involved in displaying market information.
Trace the full path:
Provider → API → normalization → cache → calculation → frontend → AI context.
Document where stale, incomplete, or incorrect values could be introduced.
2. Data correctness audit
Verify supported:

* Current and delayed stock prices.
* Premarket and after-hours prices.
* Historical prices.
* Daily percentage changes.
* Price and volume charts.
* Moving averages.
* RSI.
* VWAP.
* Technical indicators.
* Market capitalization.
* Financial ratios.
* Earnings metrics.
* Revenue and profitability.
* Dividend data.
* Corporate actions.
* Company names.
* Symbol mappings.
* Portfolio totals.
* Portfolio percentages.
* Currency conversions, if supported.
* Financial news timestamps.
* Market summaries.

Do not assume all metrics or providers are supported.
Evaluate only real functionality.
3. Market-session accuracy
Test:

* Regular market hours.
* Premarket.
* After-hours.
* Weekends.
* Market holidays.
* Delayed quote conditions.
* Historical market sessions.

Ensure that timestamps, freshness labels, and session descriptions are accurate.
Do not imply market prices are live when the provider supplies delayed information.
4. Mathematical validation
Independently verify calculation logic.
Examples:
Percentage change = (current value - reference value) / reference value × 100.
Portfolio weight = holding value / total applicable portfolio value × 100.
Apply appropriate handling for zero denominators, missing values, currencies, corporate actions, and data-provider conventions.
Do not use arbitrary fallback zeros for missing data.
5. Cross-feature consistency
Test whether the same underlying data is presented consistently across:

* Homepage.
* Global charts.
* Dossier.
* Milo.
* Portfolio.
* Research.
* News.
* Other relevant features.

Different values may be valid when they represent different timestamps, sessions, or provider conventions.
Make those differences explicit rather than incorrectly forcing them to match.
6. Scenario testing
Run representative workflows:
A. Search SPY → open chart → open Dossier → ask Milo about SPY.
B. Search AAPL → switch to NVDA rapidly → verify every relevant widget displays the correct symbol.
C. Load an unavailable metric → verify the application shows an appropriate missing-data state.
D. Refresh while data is loading → verify state recovery.
E. Load cached data → verify freshness labels.
F. Simulate a provider outage → verify graceful degradation.
G. Test multiple concurrent users → verify data and preferences remain isolated.
H. Test a connected brokerage portfolio using sandbox or synthetic data → verify factual portfolio calculations.
7. Caching audit
Inspect:

* Cache keys.
* Cache expiration.
* Symbol-specific caching.
* User-specific caching.
* Authentication boundaries.
* Duplicate requests.
* Stale-while-revalidate behavior.
* Cache invalidation.
* Market-session awareness.

Prevent cross-user financial-data leakage.
Prevent one ticker's response from appearing under another ticker.
8. Reconciliation and reference testing
Compare representative application outputs to actual configured provider responses.
Record:

* Metric.
* Symbol.
* Requested timestamp.
* Provider.
* Expected value.
* Actual value.
* Difference.
* Explanation.
* Test outcome.

For values that cannot be verified, report UNVERIFIED.
Never invent reference prices.
9. Error behavior
Do not display fabricated data when a provider fails.
Do not silently substitute outdated values without communicating their age.
Use clear states such as:

* Data unavailable.
* Unable to refresh.
* Last updated at the available timestamp.
* This metric is not supported.

Keep messages simple and consistent.
Completion gate
All discovered financial-data pathways have been reviewed.
Critical calculation errors are fixed.
Known cross-feature contradictions are corrected or explained.
Stale and missing data are handled transparently.
User-specific financial information remains isolated.
Tests and provider reconciliation results are documented.
