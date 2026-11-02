<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 03 — GLOBAL SEARCH, DOSSIER SEARCH, TICKER STATE, AND NAVIGATION REPAIR
Read the master instructions and existing audit findings.
This phase addresses confirmed problems from the investor demonstration.
DO NOT perform cosmetic redesign work before fixing the underlying functionality.
1. Global search audit
Find every search implementation.
Identify whether search components share a common provider, component, resolver, cache, or state-management system.
Investigate:

* Search input not accepting text.
* Search results failing to load.
* Incorrect symbol resolution.
* Results appearing too slowly.
* Input losing focus.
* Search submitting twice.
* Enter key failing.
* Clicking results doing nothing.
* Results disappearing unexpectedly.
* Search dropdown opening behind other elements.
* Search closing before selection.
* Search state resetting on navigation.
* Ticker selection failing to update downstream data.
* Search failure after refresh.
* Mobile search issues.
* Stale search responses overwriting newer results.

2. Search behavior specification
Expected behavior:

1. User focuses the search field.
2. User enters a ticker or company name.
3. Search displays relevant results as supported by the existing provider.
4. Keyboard arrows navigate available results.
5. Enter selects the highlighted result.
6. Clicking a result selects it.
7. Escape closes suggestions.
8. Clearing the search does not crash the interface.
9. Invalid symbols produce useful feedback.
10. Selection updates the correct page and dependent state.

Use debouncing where beneficial.
Handle request races using cancellation or request identity checks.
Do not allow an older request to overwrite the most recent user selection.
3. Remove Follows Ticker
Locate the exact component that displays labels such as:
"Follows INTC"
Remove this UI feature.
Trace the feature's underlying state and dependencies before removing code.
Determine whether it currently affects:

* Global ticker selection.
* Navigation.
* Dossier.
* Charts.
* Watchlists.
* Milo.
* Portfolio pages.
* Stored user preferences.

Remove the follow-ticker behavior without breaking intentional user selections.
Do not unintentionally remove a separate useful watchlist or follow feature unless it is actually the same functionality.
4. SPY default behavior
Implement SPY as the default market symbol when there is no explicit user-selected ticker.
Requirements:

* First visit defaults to SPY.
* The relevant default chart displays SPY.
* The symbol is correctly resolved.
* Dependent data requests use SPY.
* No old followed ticker overrides it.
* Selecting another ticker updates the relevant context.
* An intentional user selection does not revert unexpectedly.
* Browser navigation remains predictable.
* Existing deep links to other tickers continue working.

Establish an explicit precedence order for symbol selection, such as route parameter, intentional in-session selection, persisted preference if applicable, then SPY fallback.
Document the selected precedence rules and test them.
5. Dossier search repair
Investigate Dossier separately.
Test:

* Search by ticker.
* Search by company name.
* Lowercase input.
* Mixed-case input.
* Symbols with punctuation.
* Rapid ticker switching.
* Empty search.
* Invalid symbol.
* Provider timeout.
* Navigation away and back.
* Direct loading of a Dossier URL.
* Refresh after selecting a ticker.
* Changing the ticker during an active analysis request.

Ensure that every displayed analysis belongs to the selected ticker.
Never show AAPL analysis under an NVDA heading because of stale requests.
6. Cross-feature consistency
Test whether the selected market context is correctly handled across:

* Global terminal.
* Dossier.
* Charts.
* Research.
* News.
* Milo, where contextual symbol awareness is supported.

Use a single authoritative ticker context where appropriate.
Do not indiscriminately force all pages to share one ticker if their workflows require independent selections.
Document intentional exceptions.
7. Navigation tests
Verify:

* Browser back and forward.
* Direct links.
* Refresh.
* Opening in new tabs.
* Sidebar navigation.
* Active-page indicators.
* Search-result navigation.
* Mobile navigation.
* Authenticated and unauthenticated access.

8. Required regression scenarios
Automate or execute at least:

* 20 sequential valid ticker changes.
* 10 rapid ticker changes.
* 10 invalid or unsupported symbol searches.
* 10 browser refresh/navigation sequences.
* Keyboard-only search interaction.
* Search under simulated network latency.
* Search with a failed provider request.

Use representative real symbols and supported test data.
These are test counts, not fabricated performance claims.
Completion gate
All discovered critical search failures are corrected.
SPY is the intended default.
The Follows Ticker UI and unwanted behavior are removed.
Dossier search is reliable.
No critical stale-ticker or cross-symbol data leaks remain.
Record each scenario and result.
Do not report completion until actual interaction tests pass.
