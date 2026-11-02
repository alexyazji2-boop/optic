# API routes (generated 2026-10-29 from app.main.app.routes at 9fa0f36)

Guards are read from each handler body (they are called inside handlers, not FastAPI dependencies), so a guard
reached through a helper the scan does not name (for example `_reader` in the brokerage workspace, `_is_operator`
cooldowns, webhook signature checks) shows as "open" here; FEATURE_REGISTRY Part 6 lists the ones checked by hand.

232 routes.

| Area | Path | Methods | Handler | Access | Guard calls seen |
|---|---|---|---|---|---|
| /healthz | `/healthz` | GET | app/main.py:261 | open |  |
| admin | `/api/admin/accounts` | GET | app/main.py:5914 | owner/operator | _owner_session_guard |
| admin | `/api/admin/metrics` | GET | app/main.py:5949 | owner/operator | _owner_session_guard |
| ai | `/api/ai/usage` | GET | app/main.py:5896 | owner/operator | _write_guard |
| ai-allowance | `/api/ai-allowance` | GET | app/main.py:7561 | open |  |
| alerts | `/api/alerts` | GET | app/main.py:5697 | owner/operator | _is_owner |
| alerts | `/api/alerts/clear` | POST | app/main.py:5737 | owner/operator | _write_guard |
| alerts | `/api/alerts/seen` | POST | app/main.py:5719 | owner/operator | _write_guard |
| analysts | `/api/analysts/latest` | GET | app/main.py:6489 | open |  |
| analysts | `/api/analysts/{ticker}` | GET | app/main.py:6501 | open |  |
| auth | `/api/auth/apple/callback` | GET | app/auth/routes.py:913 | open |  |
| auth | `/api/auth/apple/callback` | POST | app/auth/routes.py:899 | open |  |
| auth | `/api/auth/change-password` | POST | app/auth/routes.py:449 | account, CSRF | csrf_guard, guard, require_user |
| auth | `/api/auth/delete-account` | POST | app/auth/routes.py:720 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/forgot-password` | POST | app/auth/routes.py:297 | open | guard |
| auth | `/api/auth/google/callback` | GET | app/auth/routes.py:856 | open |  |
| auth | `/api/auth/identities` | GET | app/auth/routes.py:543 | account | require_user |
| auth | `/api/auth/identities/{provider}` | DELETE | app/auth/routes.py:559 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/login` | POST | app/auth/routes.py:213 | open | guard |
| auth | `/api/auth/logout` | POST | app/auth/routes.py:257 | CSRF | csrf_guard |
| auth | `/api/auth/logout-all` | POST | app/auth/routes.py:274 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/me` | GET | app/auth/routes.py:138 | open | issue_csrf |
| auth | `/api/auth/passkeys` | GET | app/auth/routes.py:591 | account | require_user |
| auth | `/api/auth/passkeys/login/options` | POST | app/auth/routes.py:637 | open | guard |
| auth | `/api/auth/passkeys/login/verify` | POST | app/auth/routes.py:646 | open | guard |
| auth | `/api/auth/passkeys/register/options` | POST | app/auth/routes.py:600 | account, CSRF | csrf_guard, guard, require_user |
| auth | `/api/auth/passkeys/register/verify` | POST | app/auth/routes.py:611 | account, CSRF | csrf_guard, guard, require_user |
| auth | `/api/auth/passkeys/{passkey_id}` | DELETE | app/auth/routes.py:675 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/passkeys/{passkey_id}` | PATCH | app/auth/routes.py:663 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/preferences` | GET | app/auth/routes.py:693 | account | require_user |
| auth | `/api/auth/preferences` | PATCH | app/auth/routes.py:700 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/profile` | PATCH | app/auth/routes.py:425 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/providers` | GET | app/auth/routes.py:131 | open |  |
| auth | `/api/auth/register` | POST | app/auth/routes.py:168 | open | guard |
| auth | `/api/auth/resend-verification` | POST | app/auth/routes.py:408 | account, CSRF | csrf_guard, guard, require_user |
| auth | `/api/auth/reset-password` | POST | app/auth/routes.py:347 | open | guard |
| auth | `/api/auth/reset/check` | GET | app/auth/routes.py:335 | open |  |
| auth | `/api/auth/sessions` | GET | app/auth/routes.py:504 | account | require_user |
| auth | `/api/auth/sessions/{session_id}` | DELETE | app/auth/routes.py:524 | account, CSRF | csrf_guard, require_user |
| auth | `/api/auth/subscription` | GET | app/auth/routes.py:708 | account | require_user |
| auth | `/api/auth/verify-email` | POST | app/auth/routes.py:393 | open |  |
| auth | `/api/auth/{provider}/start` | GET | app/auth/routes.py:785 | account | guard, require_user |
| backtest | `/api/backtest/strategies` | GET | app/main.py:6030 | open |  |
| backtest | `/api/backtest/{ticker}` | GET | app/main.py:6038 | open |  |
| billing | `/api/billing/checkout` | POST | app/billing.py:120 | account, CSRF | csrf_guard, require_user |
| billing | `/api/billing/portal` | POST | app/billing.py:162 | account, CSRF | csrf_guard, require_user |
| billing | `/api/billing/status` | GET | app/billing.py:110 | open | current_user |
| billing | `/api/billing/webhook` | POST | app/billing.py:177 | open |  |
| brief | `/api/brief` | GET | app/main.py:3413 | open |  |
| brief | `/api/brief/search` | GET | app/main.py:3424 | open |  |
| briefing | `/api/briefing` | POST | app/main.py:2035 | open | current_user |
| brokerage | `/api/brokerage/accounts/{account_id}` | PATCH | app/brokerage/routes.py:197 | account, CSRF | csrf_guard, require_user |
| brokerage | `/api/brokerage/callback` | GET | app/brokerage/routes.py:134 | open | current_user |
| brokerage | `/api/brokerage/connect` | POST | app/brokerage/routes.py:118 | account, CSRF | csrf_guard, require_user |
| brokerage | `/api/brokerage/connections/{connection_id}/disconnect` | POST | app/brokerage/routes.py:187 | account, CSRF | csrf_guard, require_user |
| brokerage | `/api/brokerage/connections/{connection_id}/sync` | POST | app/brokerage/routes.py:159 | account, CSRF | csrf_guard, require_user |
| brokerage | `/api/brokerage/delete-data` | POST | app/brokerage/routes.py:216 | account, CSRF | csrf_guard, require_user |
| brokerage | `/api/brokerage/portfolio` | GET | app/brokerage/routes.py:223 | account | require_user |
| brokerage | `/api/brokerage/sandbox/abandon` | POST | app/brokerage/routes.py:345 | open |  |
| brokerage | `/api/brokerage/sandbox/authorize` | POST | app/brokerage/routes.py:334 | open |  |
| brokerage | `/api/brokerage/sandbox/portal` | GET | app/brokerage/routes.py:285 | open |  |
| brokerage | `/api/brokerage/status` | GET | app/brokerage/routes.py:90 | open | current_user |
| brokerage | `/api/brokerage/webhook` | POST | app/brokerage/routes.py:242 | open |  |
| brokerage | `/api/brokerage/workspace/alerts` | GET | app/brokerage/workspace_routes.py:139 | open |  |
| brokerage | `/api/brokerage/workspace/alerts/refresh` | POST | app/brokerage/workspace_routes.py:148 | CSRF | csrf_guard |
| brokerage | `/api/brokerage/workspace/alerts/seen` | POST | app/brokerage/workspace_routes.py:158 | CSRF | csrf_guard |
| brokerage | `/api/brokerage/workspace/alerts/settings` | PUT | app/brokerage/workspace_routes.py:167 | CSRF | csrf_guard |
| brokerage | `/api/brokerage/workspace/briefing` | GET | app/brokerage/workspace_routes.py:105 | open |  |
| brokerage | `/api/brokerage/workspace/briefing/written` | POST | app/brokerage/workspace_routes.py:116 | CSRF | csrf_guard, guard |
| brokerage | `/api/brokerage/workspace/events` | GET | app/brokerage/workspace_routes.py:100 | open |  |
| brokerage | `/api/brokerage/workspace/holdings` | GET | app/brokerage/workspace_routes.py:70 | open |  |
| brokerage | `/api/brokerage/workspace/options` | GET | app/brokerage/workspace_routes.py:80 | open |  |
| brokerage | `/api/brokerage/workspace/overview` | GET | app/brokerage/workspace_routes.py:65 | open |  |
| brokerage | `/api/brokerage/workspace/performance` | GET | app/brokerage/workspace_routes.py:90 | open |  |
| brokerage | `/api/brokerage/workspace/scenarios` | GET | app/brokerage/workspace_routes.py:85 | open |  |
| brokerage | `/api/brokerage/workspace/scorecard` | GET | app/brokerage/workspace_routes.py:75 | open |  |
| build | `/api/build` | GET | app/main.py:8189 | owner/operator | _is_owner |
| catalyst-mode | `/api/catalyst-mode` | GET | app/main.py:4883 | open |  |
| catalysts | `/api/catalysts` | GET | app/main.py:4792 | open |  |
| catalysts | `/api/catalysts/refresh` | POST | app/main.py:4837 | open |  |
| chain | `/api/chain/{ticker}` | GET | app/main.py:1407 | open |  |
| chat | `/api/chat` | POST | app/main.py:7848 | spends (metered) | _spend_guard |
| compare | `/api/compare` | GET | app/main.py:5360 | open |  |
| congress | `/api/congress` | GET | app/main.py:4721 | open |  |
| contracts | `/api/contracts` | GET | app/main.py:2775 | open |  |
| crypto-sentiment | `/api/crypto-sentiment` | GET | app/main.py:5677 | open |  |
| daily-bars | `/api/daily-bars/{ticker}` | GET | app/main.py:5547 | open |  |
| desk | `/api/desk/edition` | GET | app/main.py:3382 | open |  |
| desk | `/api/desk/edition/publish` | POST | app/main.py:3402 | owner/operator | _write_guard |
| desk | `/api/desk/edition/{key}` | GET | app/main.py:3394 | open |  |
| desk | `/api/desk/editions` | GET | app/main.py:3389 | open |  |
| digest | `/api/digest` | POST | app/main.py:2108 | open |  |
| digest | `/api/digest/{ticker}` | GET | app/main.py:2086 | open |  |
| dispersion | `/api/dispersion` | GET | app/main.py:4943 | open |  |
| earnings | `/api/earnings/{ticker}` | GET | app/main.py:1174 | open |  |
| earnings | `/api/earnings/{ticker}/brief` | GET | app/main.py:1282 | open |  |
| earnings | `/api/earnings/{ticker}/brief` | POST | app/main.py:1317 | spends (metered), CSRF | _spend_guard, csrf_guard |
| earnings-week | `/api/earnings-week` | GET | app/main.py:5335 | open |  |
| econ | `/api/econ` | GET | app/main.py:5983 | open |  |
| econ | `/api/econ/{code}` | GET | app/main.py:5989 | open |  |
| evaluate | `/api/evaluate` | GET | app/main.py:4910 | open |  |
| extras | `/api/extras/{ticker}` | GET | app/main.py:5656 | open |  |
| fair-value | `/api/fair-value/{ticker}` | GET | app/main.py:5423 | open |  |
| feedback | `/api/feedback` |  | app/main.py:5779 | open |  |
| feedback | `/api/feedback` | GET | app/main.py:5847 | owner/operator | _write_guard |
| feedback | `/api/feedback` | POST | app/main.py:5794 | CSRF | csrf_guard, current_user, guard |
| feedback | `/api/feedback/resolve-all` | POST | app/main.py:5963 | owner/operator | _write_guard |
| feedback | `/api/feedback/{report_id}/resolve` | POST | app/main.py:5969 | owner/operator | _write_guard |
| forex | `/api/forex` | GET | app/main.py:5630 | open |  |
| framework | `/api/framework/{ticker}` | GET | app/main.py:1205 | open |  |
| framework | `/api/framework/{ticker}/forecasts` | GET | app/main.py:1215 | open |  |
| framework-policy | `/api/framework-policy` | GET | app/main.py:1230 | open |  |
| framework-quality | `/api/framework-quality` | GET | app/main.py:1224 | open |  |
| global | `/api/global` | GET | app/main.py:6180 | open |  |
| health | `/api/health` | GET | app/main.py:1033 | open |  |
| home | `/api/home` | GET | app/main.py:2865 | open |  |
| implied-correlation | `/api/implied-correlation` | GET | app/main.py:4954 | open |  |
| indicators | `/api/indicators/{ticker}` | GET | app/main.py:6300 | open |  |
| indices | `/api/indices` | GET | app/main.py:1801 | open |  |
| indices | `/api/indices/board` | GET | app/main.py:4555 | open |  |
| insiders | `/api/insiders/latest` | GET | app/main.py:6472 | open |  |
| instrument | `/api/instrument` | GET | app/main.py:6232 | open |  |
| intraday | `/api/intraday/{ticker}` | GET | app/main.py:4370 | open |  |
| knowledge | `/api/knowledge/modes` | GET | app/main.py:7572 | open |  |
| legal | `/api/legal` | GET | app/main.py:3302 | open |  |
| logo | `/api/logo/{symbol}` | GET | app/main.py:1860 | open |  |
| longterm | `/api/longterm/{ticker}` | GET | app/main.py:1738 | open |  |
| macro | `/api/macro` | GET | app/main.py:1709 | open |  |
| market | `/api/market` | GET | app/main.py:1719 | open |  |
| news | `/api/news/{ticker}` | GET | app/main.py:3370 | open |  |
| options | `/api/options/{ticker}/analyze` | POST | app/main.py:1590 | open |  |
| options | `/api/options/{ticker}/picker` | GET | app/main.py:1465 | open |  |
| options | `/api/options/{ticker}/research` | GET | app/main.py:1516 | open |  |
| pairs | `/api/pairs/{ticker}` | GET | app/main.py:6141 | open |  |
| pairs | `/api/pairs/{ticker}/peers` | GET | app/main.py:6105 | open |  |
| paper | `/api/paper/mark` | POST | app/main.py:2814 | open |  |
| patterns | `/api/patterns/base-rates` | GET | app/main.py:6388 | open |  |
| patterns | `/api/patterns/{ticker}` | GET | app/main.py:6402 | open |  |
| pe-history | `/api/pe-history/{ticker}` | GET | app/main.py:5397 | open |  |
| personas | `/api/personas` | GET | app/main.py:7155 | open |  |
| portfolio-risk | `/api/portfolio-risk` | GET | app/main.py:4965 | open |  |
| portfolio-scenarios | `/api/portfolio-scenarios` | GET | app/main.py:5046 | open |  |
| priority | `/api/priority` | GET | app/main.py:5215 | open |  |
| quote | `/api/quote/{ticker}` | GET | app/main.py:1144 | open |  |
| relperf | `/api/relperf/{ticker}` | GET | app/main.py:5995 | open |  |
| relperf-scan | `/api/relperf-scan/{kind}` | GET | app/main.py:6008 | open |  |
| replays | `/api/replays` | GET | app/main.py:5074 | open |  |
| replays | `/api/replays/{rid}` | GET | app/main.py:5080 | open |  |
| research | `/api/research` | POST | app/main.py:7898 | spends (metered) | _spend_guard |
| retirement | `/api/retirement` | POST | app/main.py:1772 | open |  |
| rotation | `/api/rotation` | GET | app/main.py:6020 | open |  |
| saved-research | `/api/saved-research` | GET | app/account.py:412 | account | require_user |
| saved-research | `/api/saved-research` | POST | app/account.py:440 | account, CSRF | csrf_guard, require_user |
| saved-research | `/api/saved-research/{research_id}` | DELETE | app/account.py:478 | account, CSRF | csrf_guard, require_user |
| saved-research | `/api/saved-research/{research_id}` | GET | app/account.py:430 | account | require_user |
| scanners | `/api/scanners` | GET | app/main.py:6442 | open |  |
| scanners | `/api/scanners/groups` | GET | app/main.py:6424 | open |  |
| scanners | `/api/scanners/{scan_id}` | GET | app/main.py:6649 | open |  |
| screener | `/api/screener` | POST | app/main.py:6611 | open |  |
| screener | `/api/screener/ask` | POST | app/main.py:6517 | spends (metered) | _spend_guard |
| screener | `/api/screener/fields` | GET | app/main.py:6600 | open |  |
| search | `/api/search` | GET | app/main.py:1875 | open |  |
| seasonality | `/api/seasonality/{ticker}` | GET | app/main.py:6156 | open |  |
| sectors | `/api/sectors` | GET | app/main.py:1714 | open |  |
| sectors | `/api/sectors/board` | GET | app/main.py:4545 | open |  |
| sectors | `/api/sectors/{symbol}/read` | GET | app/main.py:4581 | open |  |
| segments | `/api/segments/{ticker}` | GET | app/main.py:6459 | open |  |
| sentiment | `/api/sentiment` | GET | app/main.py:4613 | open |  |
| session | `/api/session` | GET | app/main.py:3310 | open |  |
| session | `/api/session/{ticker}` | GET | app/main.py:3316 | open |  |
| setups | `/api/setups` | GET | app/main.py:2496 | open |  |
| setups | `/api/setups/catalogue` | GET | app/main.py:2490 | open |  |
| setups | `/api/setups/{ticker}/detail` | GET | app/main.py:2535 | open |  |
| setups | `/api/setups/{ticker}/options` | GET | app/main.py:2593 | open |  |
| shortlist | `/api/shortlist` | GET | app/main.py:2478 | open |  |
| signals | `/api/signals` | GET | app/main.py:2220 | account | require_user |
| signals | `/api/signals/followup` | POST | app/main.py:2236 | open |  |
| snapshots | `/api/snapshots` | GET | app/main.py:5683 | open |  |
| stage | `/api/stage` | GET | app/main.py:6203 | open |  |
| stockmap | `/api/stockmap` | GET | app/main.py:5640 | open |  |
| stop-check | `/api/stop-check/{ticker}` | GET | app/main.py:6079 | open |  |
| take-chart | `/api/take-chart/{ticker}` | GET | app/main.py:5612 | open |  |
| theses | `/api/theses` | GET | app/account.py:564 | account | require_user |
| theses | `/api/theses/adopt` | POST | app/account.py:657 | account, CSRF | csrf_guard, require_user |
| theses | `/api/theses/{symbol}` | DELETE | app/account.py:646 | account, CSRF | csrf_guard, require_user |
| theses | `/api/theses/{symbol}` | PUT | app/account.py:582 | account, CSRF | csrf_guard, require_user |
| ticker | `/api/ticker/{ticker}` | GET | app/main.py:1086 | open |  |
| tracker | `/api/tracker` | GET | app/main.py:3463 | open |  |
| tracker | `/api/tracker/mark` | POST | app/main.py:3476 | open |  |
| tracker | `/api/tracker/scan` | POST | app/main.py:3538 | open |  |
| trendlines | `/api/trendlines/{ticker}` | GET | app/main.py:5574 | open |  |
| trends | `/api/trends/board` | GET | app/main.py:4565 | open |  |
| validation | `/api/validation` | GET | app/main.py:2181 | open |  |
| validation | `/api/validation/levels` | GET | app/main.py:2202 | owner/operator | _write_guard |
| valuation | `/api/valuation/{ticker}` | GET | app/main.py:5430 | open |  |
| valuation | `/api/valuation/{ticker}/comps` | GET | app/main.py:5487 | open |  |
| valuation | `/api/valuation/{ticker}/run` | POST | app/main.py:5441 | open |  |
| valuation | `/api/valuation/{ticker}/sotp` | POST | app/main.py:5456 | open |  |
| valuation-inputs | `/api/valuation-inputs/{ticker}` | GET | app/main.py:5407 | open |  |
| valuation-models | `/api/valuation-models` | GET | app/valuation/store.py:104 | account | require_user |
| valuation-models | `/api/valuation-models` | POST | app/valuation/store.py:127 | account, CSRF | csrf_guard, require_user |
| valuation-models | `/api/valuation-models/replay` | POST | app/valuation/store.py:158 | open |  |
| valuation-models | `/api/valuation-models/{model_id}` | DELETE | app/valuation/store.py:148 | account, CSRF | csrf_guard, require_user |
| valuation-models | `/api/valuation-models/{model_id}` | GET | app/valuation/store.py:116 | account | require_user |
| valuations | `/api/valuations` | GET | app/account.py:804 | account | require_user |
| valuations | `/api/valuations/adopt` | POST | app/account.py:850 | account, CSRF | csrf_guard, require_user |
| valuations | `/api/valuations/{symbol}` | DELETE | app/account.py:839 | account, CSRF | csrf_guard, require_user |
| valuations | `/api/valuations/{symbol}` | PUT | app/account.py:813 | account, CSRF | csrf_guard, require_user |
| watches | `/api/watches` | GET | app/account.py:1002 | account | require_user |
| watches | `/api/watches` | POST | app/account.py:1054 | account, CSRF | csrf_guard, require_user |
| watches | `/api/watches/catalogue` | GET | app/main.py:2650 | open |  |
| watches | `/api/watches/check` | POST | app/main.py:2656 | open | current_user |
| watches | `/api/watches/hits` | GET | app/account.py:1016 | account | require_user |
| watches | `/api/watches/hits/seen` | POST | app/account.py:1043 | account, CSRF | csrf_guard, require_user |
| watches | `/api/watches/run` | POST | app/main.py:2755 | owner/operator | _write_guard |
| watches | `/api/watches/seen` | POST | app/account.py:1182 | account, CSRF | csrf_guard, require_user |
| watches | `/api/watches/{watch_id}` | DELETE | app/account.py:1156 | account, CSRF | csrf_guard, require_user |
| watches | `/api/watches/{watch_id}` | PATCH | app/account.py:1106 | account, CSRF | csrf_guard, require_user |
| watches | `/api/watches/{watch_id}/restore` | POST | app/account.py:1169 | account, CSRF | csrf_guard, require_user |
| watchlist | `/api/watchlist` | GET | app/main.py:2837 | open |  |
| watchlist | `/api/watchlist/earnings` | GET | app/main.py:2855 | open |  |
| watchlists | `/api/watchlists` | GET | app/account.py:122 | account | require_user |
| watchlists | `/api/watchlists` | POST | app/account.py:130 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/adopt` | POST | app/account.py:333 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/order` | PUT | app/account.py:228 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/{watchlist_id}` | DELETE | app/account.py:258 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/{watchlist_id}` | PATCH | app/account.py:159 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/{watchlist_id}/items` | POST | app/account.py:302 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/{watchlist_id}/items/{symbol}` | DELETE | app/account.py:320 | account, CSRF | csrf_guard, require_user |
| watchlists | `/api/watchlists/{watchlist_id}/order` | PUT | app/account.py:176 | account, CSRF | csrf_guard, require_user |
| weekly | `/api/weekly` | GET | app/main.py:4640 | owner/operator | _write_guard |
| weekly-bars | `/api/weekly-bars/{ticker}` | GET | app/main.py:5515 | open |  |
