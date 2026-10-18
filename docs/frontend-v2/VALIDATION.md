# Frontend v2: validation of the first journey (Home, Dossier, Watchlist)

Run on 2026-10-17 against the real backend: a local server on :8075 with the seeded demo account, the sandbox brokerage, and no AI key (nothing can spend). Market data was live from the providers, as of Friday Oct 16's close (weekend).

## What was exercised

| Check | How | Result |
|---|---|---|
| New-visitor Home | Fresh browser: welcome, starters with real prices, Follow, knowledge modes, See your Home | Works; follows write the classic guest keys |
| Returning Home, guest and signed in | Browser list and account list | Strip, market panel, watchlist rows, What matters today, Desk, movers, scan alerts all from live endpoints |
| Portfolio block | Sandbox brokerage | Shown only when a connection exists; not linked in this run |
| Dossier Overview (AAPL, NVDA) | Header, chart, cone, four answers, drawers, two long-term views, verdict, digest, More | Figures equal to the API (price 343.46, trend score 82, case Neutral, fair value 243 to 306, ±5.71%, ±2.46%, 1.05×); the current app shows the same 82/100 |
| NVDA, a range too wide to rate | Fair value payload with `wide: true` | Says "No verdict" and quotes the reason; no meter |
| Watchlist, guest | Add, sort (7), filter (4), search, My order, remove with Undo, new, rename, delete | All correct; stored in the classic format |
| Watchlist, signed in | Same, through `/api/watchlists*` with the CSRF header | All writes reach the server; Free plan's 3-list cap shows the classic message |
| Alerts, signed in | Prefilled from the Dossier's Alert button, add two watches, Check now, mark seen | Server stores them; Check now reports met and not met with evidence |
| Sign in, guest things, sign out | Sign in with guest list present; "Bring them in"; sign out | Question survives navigation; guest names adopted into the account; sign-out shelves the account's keys and reloads, as in the classic app |
| Milo | Dossier Ask Milo, signed out and in | Context line shown; signed out: sign-in prompt; signed in: the server's refusal shown plainly (no key here) |
| Keyboard | Real key presses | ⌘K, type, Enter opens the company; focus lands on the page heading; chart arrows read prices; markers reachable by Tab; Escape closes drawers and returns focus to the opener |
| Screen reader | Accessibility tree read in the browser | One h1 per page, named landmarks, rail links named with "opens in the current app", answers labelled by question and answer, charts with a text summary |
| Automated audit | `launch-audit-2026-10-16/tools/audit.js` on 14 views × ivory and charcoal × desktop 1440 and phone 390, plus the drawers | 0 faults after fixes (contrast, unnamed controls, 24px targets, heading order, duplicate ids, overflow) |
| Loading, empty, error | fetch forced to hang, fail with 502, or return empty, on Home, Dossier and Watchlist, desktop and phone | Each block shows its own skeleton, error with Try again, or empty state; the rest of the page still renders |
| Mobile Safari | iOS 27 simulator, iPhone 17 | Home and Dossier render as in Chrome |
| Performance (warm server) | Navigation and resource timing, cache off | v2's own files: 29 requests, 86 KB transferred (232 KB decoded). The current app's Home: 1,144 KB (3.7 MB decoded). Home makes 8 API requests, the Dossier 11 |
| Test suite | `pytest -q` | 6182 passed, 1 skipped |

## Known limits of this run

- The slowest sources are slow cold: `/api/priority` timed out past 2 minutes while the server was being rate-limited by the data provider after a restart. Home shows a loading line after 8 seconds and the rest of the page is unaffected.
- VoiceOver itself was not driven; the accessibility tree was inspected instead.
- Milo could not produce an answer locally because there is no key; streaming was tested only up to the server's error event.
- The brokerage portfolio block was later checked with a linked sandbox account: figures labelled by source (value now, the broker's own total, provider estimates).

## Second round: the Dossier (2026-10-18)

| Check | Result |
|---|---|
| Options, Chart, Investing, Earnings, Financials, News against the live backend | Render with no console errors. Each block has loading and error states in code; the forced loading/empty/error run covered the first journey only |
| Position builder (bull call spread) | $635 at the mid, max profit $865, breakeven 351.35, from `/analyze` |
| Valuation scenarios | Matches a hand calculation; saving to this browser tested; the account route (`PUT /api/valuations/{SYM}`) is wired but was not exercised |
| Indicators (SMA, EMA, RSI) and scenario arithmetic | In `tests/test_frontend_v2.py` |
| Drawings | Saved in `optic.chart.drawings.v2` with the classic kind names |
| Audit, 52 views and 4 drawers | 0 faults after fixes |
| Mobile Safari (iPhone 17) | Options builder and the chart start on the first screen |
| Suite | 6183 passed, 1 skipped |
| Paid calls | The pre-earnings brief loads only on request |

## Third round: Markets and Discover (2026-10-18)

Read, Macro, Indices, the Instrument page, Explore, Scan, Insiders and Analysts, against the same local server (no AI key).

| Check | Result |
|---|---|
| Every page against the live backend | Renders with no console errors; Macro's 12 tabs and Read's 10 open and fill |
| Scan, in plain words | "Near 52-week highs on heavy volume" read by the free parser (top tenth of the range, volume 30% above normal): 2 of 733, the same rows `/api/screener` returns; "Edit as filters" carries the bounds (90, 1.3) into Build a screen |
| Scan, built screen | Funnel 733 → 56 → 2; bounds kept in `optic.screener.v1` |
| Scan, named scans | `#/scan?id=pullback` opens that scan: 26 matched, first 25, columns in the classic formats |
| Insiders | House trades (2,973 disclosures, chart, most disclosed), Form 4 filings after EDGAR answers, federal contracts |
| Analysts | Upgrades filter (20 in 7 days), one-symbol search with the year window, column sort |
| Macro stock map | Drills into a sector by click, Enter or a sector button |
| Forced loading, error and empty | All eight pages, desktop and phone: a skeleton while loading, a named error with Try again on failure, the ranking-still-building state on Scan |
| Automated audit | 11 views × light and dark × desktop and phone: 0 faults after fixes (a 21px map tile and ticker buttons under 44px) |
| Mobile Safari (iPhone 17) | Scan renders as in Chrome |
| Explore ranking and Scan cell formats | In `tests/test_frontend_v2.py` |
| Suite | 6188 passed, 1 skipped |

### Paid calls

Nothing on these pages spends on load. Read asks for its summary, the weekly update and the catalyst read with `cached=true`, which returns only what is already written (`tests/test_cached_reads.py` proves those paths never call a model). Writing a missing piece, a Sector Read, an Index Read and a Scan request with words the free parser cannot read are all clicks, labelled before the reader clicks.

### Backend change in this round

`/api/brief`, `/api/weekly` and `/api/catalyst-mode` accept `cached=true`. Without it they behave exactly as before.

### Known limits

- Macro's `/api/market` is about 40 seconds cold; the page shows its own loading state and the tabs load beside it.
- The forced empty state only covers Scan's building ranking; the other pages' empty states were seen only with a real empty answer on Analysts (NVDA with the Upgrades filter on).

## Fourth round: Compare, Positions, Brokerage, Settings and Reports (2026-10-18)

Same local server, no AI key. The local Optic Portfolio ledger has no trades, so its layout was checked against a read-only snapshot of the live ledger (`GET /api/tracker` and `/api/portfolio-risk`, no model call), served locally from a git-ignored folder that is removed before the commit. Brokerage used the local sandbox connection.

| Check | Result |
|---|---|
| Settings | Theme, text size and time zone switched and reset, writing the classic keys (`optic.theme`, `optic.ui.scale.v1`, `optic.timezone`); market hours converted to London; signed-in profile, security, sessions (the five newest, then "Show all"), plan; a report sent from the drawer, focus back on its button |
| Reports | The test report resolved and shown under Resolved; usage ledger and accounts against the owner endpoints |
| Compare | AAPL, MSFT, NVDA from `#/compare?t=`: take, indexed chart, bars, table; Mobile Safari renders it |
| Optic Portfolio | Snapshot with 13 open and 18 closed trades; book switch keeps focus through the background risk repaint |
| Paper Desk | 10 AAPL at 340, stop 330, target 360: costs $3.4K, risks $100, 2.00 to 1; priced +0.35R by `/api/paper/mark`; closed, record shown, book cleared. Option ticket: 6 expiries, 44 strikes, quote line |
| Retirement | Holdings and two candidates: every section, projection with both bands; inputs kept in `optic.roth.inputs` |
| Brokerage | All six sections; a scenario adding $5,000 of NVDA; focus moves to the result. "Write it up" was not pressed |
| Arithmetic | Compare leaders and ties, the stop-to-target gauge and held days, Paper Desk cost, risk, R, agreement and health, Retirement clamps, Brokerage money and percent formats, in `tests/test_frontend_v2.py` |
| Audit | 16 new views × light and dark × desktop and phone: 0 faults after two fixes (Compare header links under 32px, a squeezed checkbox) |
| Forced loading, error, empty | Every new page has a loading state and a named error with Try again, except where the page is local data (Paper Desk) or keeps working with partial data (Settings shows the failing part inline) |

### Fixes that reach earlier rounds

- Warning notes (`.stale`) with bold text inside broke into one word per line; they now flow as one paragraph everywhere.
- v2 sends the CSRF header on reads as well, because the owner's pages check it on GET.
- Settings' segmented controls name their attributes literally, for the dead-controls test.

### Known limits

- The provider's callback after linking a brokerage, and Stripe's return, land in the current app (the addresses are the server's).
- The local server was stopped by the app during this round; every check above was re-run after the restart.

## Stage 0, 2026-10-18

Run against the local server; the detail and every figure are in STAGE0-EVIDENCE.md.

| Check | Tool (in `~/Optic/work/v2-2026-10-17/stage0/`) | Result |
|---|---|---|
| Paid model calls on page load | `paid_call_probe.py` (recording SDK, fake key, :8077) | v2 0 in 90 loads; Classic 3 in 27 (L11) |
| Load speed, throttled phone and desktop, cold and warm | `load_perf.py` | v2 cold code 330 KB vs Classic 1,349 KB; phone content ready 4.0 s vs 8.0 s (Home) |
| Data round trips, both directions, with account isolation | `roundtrip.py` | 61 of 61 after nine v2 fixes (one check is a recorded gap) |
| Rollback | `rollback_rehearsal.py` (:8079) | 20 of 20 |
| Passkeys | `passkey_check.py` (virtual authenticator) | Sign-in and registration pass |
| Audit, 15 views × desktop and phone × light and dark | `tools/v2_check.py --audit` | 60 captures, 0 faults |
