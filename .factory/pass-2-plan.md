# Pass 2 plan: every feature works, the data drawn, and the workspace

Branch `factory/pass-2-works-data-workspace` on the fork, cut from `factory/pass-1-v2-levels-milo-signals` at 2ed9722
(the Pass 1 pull request, #19, is open and unmerged as of 2026-11-17, so this branch carries Pass 1 underneath it).
Scope: the nine items of round 2 in "Optic: what each round delivers" (2026-11-17). The suite stays green before and
after every commit: `python -m pytest -q` with outbound HTTP pinned to a closed port (TESTING.md).

Order of work: items 1 and 2 first (they fix what exists and record what is tested), then 3 and 4 (the reader's place
and the provenance every later item draws on), then 5 to 8 (new data drawn and the workspace), then 9 (billing stubs).

## 1. The eight workflows end to end, one look for loading, empty, stale and failed

The eight of 2026-11-07: research a company, what moved today, watch names, screen, practise or model, brokerage,
ask Milo from each page, account.

- Files: `static/v2/js/ui/states.js` (the four shared states), the pages each workflow crosses
  (`pages/workspace.js`, `home.js`, `dossier.js`, `chart.js`, `investing.js`, `earnings.js`, `financials.js`,
  `news.js`, `options.js`, `read.js`, `macro.js`, `indices.js`, `instrument.js`, `earningsweek.js`, `watchlist.js`,
  `alerts.js`, `explore.js`, `scan.js`, `paper.js`, `tracker.js`, `retirement.js`, `brokerage.js`, `settings.js`,
  `saved.js`, `signin.js`, `notfound.js`), `core/router.js` (unknown paths), `static/v2/css` for the brief
  transitions on the shared skeleton.
- Tests: `tests/e2e/test_pass2_workflows.py`, one real-browser journey per workflow walking every screen in order, each
  screen checked for: no uncaught page error, no raw error text or `undefined`/`NaN`/`[object Object]` on screen, no
  block left loading once its requests settle, every block that could not load drawn with the shared failed state
  (and a Try again where the request can be retried), a way forward from every screen. Run with the feeds refused
  (the outage case) and with fixtures (the loaded case). `tests/test_pass2_states_contract.py` reads the pages as text
  and fails when a page writes its own error or loading markup instead of `states.js`.
- Defects the walk finds are fixed in the page that owns them and recorded in `.factory/pass-2-workflow-record.md`.

## 2. The six features untested on the test site, tested, results recorded

Deep Research custom question, Index Read, exports, passkeys, brokerage link, alert delivery.

- Files: `app/ai.py` and `ui/milo.js` (deep research), `pages/read.js`, `pages/indices.js` and `app/brief.py` (Index
  Read), `pages/sheet.js` and the CSV and research exports, `app/auth/` and `core/passkey.js` (passkeys),
  `app/brokerage/` and `pages/brokerage.js` (brokerage link), `app/alerts.py`, `app/watch_runner.py` and the mailer
  (alert delivery).
- Tests: `tests/test_pass2_six_features.py` (route level: each feature's request, its answer, its refusal paths) and
  journeys in `tests/e2e/test_pass2_six_features.py` (each feature pressed in a real browser; passkeys through
  Chromium's virtual authenticator over CDP; alert delivery read back from the outbox).
- Results: `.factory/pass-2-six-features-record.md`, one row per feature: what was exercised, where (suite or the
  evaluation copy through the gate), the result, and anything that cannot be tested there and why (the brokerage link
  needs SnapTrade test credentials).

## 3. Ticker and place kept across tabs, Milo given the view

- Files: `core/store.js` (current ticker and per-tab place), `core/router.js`, `core/scrollmem.js`,
  `pages/tabs.js`, `pages/dossier-frame.js`, `ui/milo-context.js`, `ui/milo.js`, `pages/chart.js` (timeframe in the
  context), `pages/financials.js` (metric in the context); server `app/ai.py` context fields.
- Tests: `tests/test_pass2_place.py` (JavaScriptCore: the store keeps ticker, tab, timeframe, metric), journey in
  `tests/e2e/test_pass2_place.py` (move across tabs and back, the ticker and scroll kept; the Milo request carries the
  chart's timeframe or the metric in view, read from the Anthropic stub).

## 4. Source and timestamp on every figure; full SEC insider history

- Files: `ui/figure.js`, `core/figures.js`, `app/figures/registry.py` (source and as-of on every figure), `ui/milo.js`
  (reported facts marked apart from Milo's reading), `app/insiders.py`, `app/form4_store.py`, `app/insider_fill.py`
  (full Form 4 history from EDGAR, paged), `pages/insiders.js`.
- Tests: `tests/test_pass2_provenance.py` (every figure the registry emits has a source and a timestamp),
  `tests/test_pass2_insiders.py` (EDGAR pages read past the feed's last batch, from recorded fixtures), a journey that
  opens the source of a figure on the stock page.

## 5. Intraday sparklines on Home, a one-day range, the live price dot

- Files: `app/main.py` (one batched `/api/sparklines` route), `app/providers/` (five-minute bars since the open behind
  one provider interface, so a licensed feed slots in), `app/delays.py` (delayed or closed status), `ui/strips.js`,
  `pages/workspace.js` and `home.js` (ticker rows, headline chart one-day range), `ui/pricechart.js` (the price dot).
- Tests: `tests/test_pass2_sparklines.py` (batching, refresh interval in session, fallback to the 30-session daily
  line, delayed labelling), a journey drawing the rows red and green from fixtures.

## 6. Financials as charts

- Files: `app/sec_facts.py`, `app/segment_store.py` and the financials route (quarterly balance sheet and cash flow,
  analyst target ranges), `pages/financials.js`, `ui/finfigs.js`, `ui/xychart.js`, `ui/bars.js`.
- Tests: `tests/test_pass2_financials.py` (series shapes, periods, sources), a journey with fixtures drawing each chart,
  axe on the drawn page.

## 7. The Optic Desk right side; less scrolling on Home and Desk

- Files: `pages/workspace.js` (Desk panel), `pages/read.js`, `ui/library.js` and `core/library.js` (saved research),
  `ui/milo.js` (follow-ups), `static/v2/css`.
- Tests: `tests/e2e/test_pass2_desk.py` (the right side shows sources, saved research and follow-ups; page height at
  1440 by 900 measured against the Pass 1 baseline).

## 8. Link groups, named layouts on the account, the same grid on the stock page; shareable later

- Files: `pages/workspace.js` (colour-coded groups replacing the single linked ticker; named layouts; reset; save
  feedback through `ui/toast.js`), `pages/dossier.js` (the grid on the stock page), `app/account.py` and `app/db.py`
  (a `layouts` table with an owner column and room for a later group owner, also used by watchlists and saved
  research), `app/main.py` (layout routes with the CSRF and owner checks).
- Tests: `tests/test_pass2_layouts.py` (no user, wrong user, the owner: the three legs), `tests/e2e/test_pass2_workspace.py`
  (a ticker chosen in one group changes that group only; a named layout saved in one browser opens in another; reset).

## 9. Billing switched on by variables, off by default

- Files: `app/billing.py` (keys and price ids read from the platform's variables; nothing set means nothing shows),
  `pages/settings.js` (the plan section only when billing is on), `.env.example` (names only), `docs/turning-billing-on.md`.
- Tests: `tests/test_billing.py` extended (off with nothing set, on with test values, no key value ever in a page or
  log).

## Status, 2026-11-17 (end of the build session)

Every item below is built on this branch, with its tests; nothing is deployed to the test site yet (it still runs the
Pass 1 head, 2ed9722). What is open is listed under each item, and none of it blocks the gauntlet.

| # | Item | State | Commit | Open |
| --- | --- | --- | --- | --- |
| 1 | Eight workflows end to end, one look for the four states | DONE | f69ddd4, 717b97b, bac13c9 | the walk runs on this machine with the feeds refused; the walk on the test site is the gauntlet's |
| 2 | Six untested features tested, results recorded | DONE in the suite; Index Read also on the test site | 632ad22 | on the test site: Deep Research and passkeys wait on an `evaluator=` line in the key file (operator); the brokerage link waits on SnapTrade test keys (Alexander); alert email is off there and, as built, goes to the owner's address only (a question for Alexander) |
| 3 | Ticker and place kept across tabs, Milo given the view | DONE | c7110cd | the metric in view is wired on Financials; Investing and Earnings send their tab, not yet the chart in view |
| 4 | Source and timestamp per figure, reported facts apart, full SEC insider history | DONE | d9337fc | registry figures already carried source and as-of (Handoff 1); the insider history fills in the background, so a first visit to a busy filer shows "still being read" for a few minutes |
| 5 | Intraday sparklines, 1D range, the live dot | DONE | dfca035 | the free feed stays the source (personal use only); a licensed vendor is one class in app/sparklines.py SOURCES |
| 6 | Financials as charts | DONE | da71263 | the sector or holdings donut and the market-weighted sector treemap from the 2026-11-11 inventory are not built in this pass |
| 7 | The Desk's right side | DONE on Home | 18426df | the Read page's Desk keeps its own layout |
| 8 | Link groups (Blue, Gold, Teal), named layouts on the account, the grid on the stock page | DONE | 18426df, b9c005b | the stock page's grid is reached from its More menu at Advanced, not a tab, so the stock page's tabs are unchanged |
| 9 | Billing switched on by variables, nothing shown when unset | DONE | 011ddf9 | his tiers (more than one price) are round 3 |

Also: the stray "." under the Earnings week notice was traced: it is not on the page. It was pytest's own progress
dot printed after a probe's output during this session's walk; the page's DOM holds no text node that is a lone period.

Full suite at the end of the session, 2026-11-17, at b9c005b: 9165 passed, 1 skipped, 0 failed (32 min), outbound
HTTP pinned to a closed port. The run before it found 7 earlier tests reading code this pass changed on purpose, and
one real defect (a purple link-group colour against the house palette); all fixed in b9c005b. Baseline before the
pass: 9101 passed, 1 failed (a dated fixture, fixed in c522377).
