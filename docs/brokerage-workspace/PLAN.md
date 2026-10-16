# Brokerage workspace: build plan and checkpoints

Branch `brokerage-workspace` (worktree `~/Optic/wt-workspace`), baseline tag
`brokerage-workspace-baseline` = origin/main `5468c24`. Not deployed: the
owner's brief says no public deploy without explicit authorisation.

## What the brief asks for

A first-class **Brokerage** sidebar destination with six sections (Overview,
Holdings & Exposure, Performance, Events & Research, Scenarios, Connections),
built on the existing read-only SnapTrade integration, with portfolio-aware
Milo, an explainable scorecard, ETF look-through, a personal events calendar,
performance and attribution, a thesis tracker, a what-if lab, an options risk
dashboard, a portfolio-aware Optic Desk section and in-app alerts.
Subscriptions and billing are out of scope. Read-only throughout.

## Decisions

- **One view, six sections.** The workspace stays the single view
  `brokerage`, so `focus.view == "brokerage"` keeps Milo attaching the linked
  portfolio on every section. Sections are `#/brokerage/<section>` routes
  (overview, holdings, performance, events, scenarios, connections), with the
  last one remembered in `optic.brokerage.section.v1`.
- **Sidebar.** Brokerage leaves the Positions group and becomes its own rail
  row (group `brokerage`, section "Tracking"), shown only when the server
  says linking is available to this reader (owner-only mode keeps it hidden
  from everyone else). The six sections are in-page tabs, not fly-out items:
  no extra navigation layer.
- **Account scope.** The server-side `selected` flag (ticked in Connections)
  is the canonical "accounts counted". The workspace header can narrow the
  view to one account; that choice is kept in `optic.brokerage.scope.v1`, sent
  as `accounts=` to workspace endpoints and as `brokerage_scope` to Milo,
  and always intersected server-side with the reader's own accounts.
- **Sources stay separate.** Every figure is labelled as broker-reported,
  market data (with its quote time), or an Optic calculation. Account sync
  time and quote freshness are shown separately.
- **History.** Transactions and the provider's daily balance estimate are
  fetched once a day (data foundation, commit 8b86336). Optic's own daily
  snapshots are "collected history"; the provider's balance history is
  "reconstructed by the provider". The two are never blended silently.
- **Costs.** Nothing AI runs on page load. The written briefing is a button,
  metered like a Milo message and cached per reader and holdings state.
  Shared market research (fundamentals, look-through, history) is cached per
  symbol, not per reader.
- **Theses** reuse the existing `theses` table (one per reader and symbol),
  adding `horizon` and `assumptions`; the Dossier and the workspace read and
  write the same row. Milo can suggest, never write.
- **Alerts** are in-app, per reader, with thresholds and dedup; email only
  with an explicit opt-in, and only where SMTP is configured.

## Module interfaces (backend, `app/brokerage/`)

All analytics modules are pure: data in, dict out; network and storage are
injected by `workspace.py`. Money figures are rounded to cents, percentages to
2 dp. Every output carries `limitations` (list of sentences) and, where a
method is involved, `definitions` or `method` text.

### performance.py (agent A)

```python
def build(accounts, activities, histories, snapshots, current, benchmark, today, period="1y") -> dict
```
- `accounts`: `[{"id", "name", "currency", "transactions_first_date", "activities_state", "history_state"}]`
  (the scope's accounts only).
- `activities`: `{account_id: [Activity dicts]}` (fields of `providers.Activity`).
- `histories`: `{account_id: {"currency", "points": [[YYYY-MM-DD, value], ...]}}`.
- `snapshots`: `store.daily_snapshots(uid)` (each has `taken_at`, `by_account`
  `{aid: {"total": {ccy: v}, "positions": {key: {...}}}}`).
- `current`: `{account_id: {"value": float, "currency": str, "as_of": iso}}`.
- `benchmark`: `{"symbol", "closes": [[date, close]], "dividends": [[ex_date, amount]]}` or None.
- Returns time-weighted and money-weighted returns, the benchmark's
  time-weighted return over the same dates, flows (deposits, withdrawals,
  internal transfers matched between in-scope accounts, in-kind transfers),
  income (dividends, interest, fees, taxes), attribution over the collected
  window, a chartable cumulative-return series (never balances vs a
  benchmark), the value source used, and limitations.

### lookthrough.py and exposure.py (agent B)

```python
lookthrough.constituents(symbol, fetch_json=..., fetch_text=..., cache=...) -> dict
exposure.build(holdings, lookthrough, sector_of, max_lookups=40) -> dict
```
- Constituents from SEC N-PORT where the fund files it, with the report
  period date, filing date and source URL; coverage, leveraged/inverse
  detection; a clear `available: False, reason` otherwise.
- Exposure: direct vs look-through company exposure without double counting
  portfolio value, sectors (direct only and look-through, with coverage),
  asset class, issuer country (labelled as issuer location, not revenue
  geography), pricing currency (not economic currency exposure).

### options_risk.py, scorecard.py, scenarios.py (agent C)

```python
options_risk.build(options, stock_shares, spot_of, rate, div_of, now) -> dict
scorecard.build(holdings, exposure, fundamentals_of, closes, benchmark_closes, events, today) -> dict
scenarios.run(holdings, cash, changes, funding, price_of, sector_of, closes, benchmark_closes, exposure=None) -> dict
```
- Options: IV solved from the broker's option price, Black-Scholes/BAW Greeks
  scaled by contracts x multiplier, aggregated per underlying with the stock
  shares, expiration buckets, assignment/settlement considerations, units
  stated, freshness of every input.
- Scorecard: five separate assessments (diversification, financial quality,
  valuation, volatility, event exposure), each with `version`, inputs,
  method, weights, coverage, drivers and the holdings it could not assess.
  No overall score; nothing implies a return forecast.
- Scenarios: hypothetical buys, sells and weight targets with a stated
  funding rule (cash, new money, pro rata), before/after weights,
  concentration, sector exposure, and historical volatility/beta labelled as
  history, not a guarantee.

### Lead-owned (workspace orchestration and the rest)

`workspace.py` (assembles each section with caching and lookups),
`events.py` (personal calendar), `briefing.py` (measured contributions plus
timing-matched headlines; optional written summary), `alerts.py` (portfolio
alerts), `desk.py` (portfolio section from the canonical Desk edition),
theses fields, the Milo `get_my_portfolio` tool, routes, the front end.

## Checkpoints

| # | What | Commit | State |
|---|---|---|---|
| 0 | Discovery (nav, services, Milo/brokerage/SnapTrade) | n/a | done |
| 1 | Data foundation: transactions, balance history, daily snapshots, scrub on disconnect, cross-connection identity, cash-equivalent fix | 8b86336 | done, 117 brokerage tests |
