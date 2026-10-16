# The Brokerage workspace

A first-class sidebar destination for a reader's linked brokerage accounts,
read-only, built on the SnapTrade integration. Branch `brokerage-workspace`;
see `PLAN.md` for the build plan and checkpoints.

## What a reader can do

| Section | What it answers |
|---|---|
| **Overview** | What do I own, what changed, what deserves attention: total value (broker), today's move measured per holding (market data), change since the last sync, unrealised gain, largest holdings, a short list of things that deserve attention, what is coming up, a briefing that keeps measured contributions apart from headlines matched by timing, and an optional written briefing. |
| **Holdings & Exposure** | Every holding with the broker's price beside Optic's quote; exposure by sector (direct only or looking through ETFs), asset class, issuer country and pricing currency; companies held directly and through funds; the five-part Optic scorecard; option Greeks and expiry risk; cash and what could not be counted. |
| **Performance** | Time-weighted and money-weighted returns over 1M, 3M, YTD, 1Y or all, against a chosen benchmark's total return over the same dates; deposits, withdrawals and transfers between linked accounts; dividends, interest, fees and taxes; contributions by holding over the days Optic has snapshots for; what history the figures rest on. |
| **Events & Research** | A personal calendar (earnings, confirmed or estimated, with timing where known; ex-dividend dates; option expiries) with the share of the portfolio each affects and links to earnings analysis; position theses (why I own it, horizon, assumptions, what would make me reassess) with developments since each was saved; the Optic Desk edition read for this portfolio; alerts and their settings. |
| **Scenarios** | A what-if lab: add to, reduce or set the weight of holdings, paid for by cash, new money or selling the rest evenly, with before/after weights, concentration, sectors, historical volatility, beta, drawdown and a beta-implied stress line. Nothing is traded. |
| **Connections** | Linking, each connection and its accounts (choose which count, rename them), sync, reconnect, disconnect, and delete everything. Also reached from Settings. |

Every section can be narrowed to one account; the choice is kept per reader
and passed to Milo. Every section is its own address (`#/brokerage/holdings`),
survives a refresh and steps with Back and Forward.

**Milo** has a `get_my_portfolio` tool (summary, exposure, events,
performance, scorecard, options, briefing) bound to the signed-in reader and
the account in view, and is told which section the reader is on. It answers
"where am I concentrated", "why did my portfolio move today", "which earnings
affect me this week", "how exposed am I to technology" and "what deserves more
research" by fetching the part it needs. It describes; it never advises a
trade and never rewrites a thesis.

## Where each figure comes from

Each figure carries one of three tags in the page:

- **Broker-reported**: quantities, prices, cost basis, cash and totals from the
  broker at its last sync, with the account's sync time and the broker's own
  "as of" where it gives one.
- **Market data**: Optic's quotes, calendars, fundamentals and history, with
  the quote's own time and delay.
- **Optic calculation**: everything computed from the two, with a method and a
  version string.

Account sync time and quote freshness are shown as two separate chips, never as
one "updated".

## Calculation definitions

### Performance (`app/brokerage/performance.py`, `performance-2026-10-15.1`)

- **External flows**: CONTRIBUTION, WITHDRAWAL, TRANSFER and in-kind transfers.
  Dividends, interest, fees and taxes are investment results, not flows. An
  in-kind transfer is valued at its amount, else units x price (flagged as an
  estimate), else returns are not measured across its date.
- **Transfers between linked accounts**: an outflow from one in-scope account
  and an equal inflow (within 1 cent or 0.1%) into another within 3 days is one
  internal transfer and is left out.
- **Values**: the provider's estimated daily balance history where every
  in-scope account has it, then Optic's own daily snapshots, then today's
  value. Gaps are not interpolated; the page says which source it used.
- **Time-weighted return**: daily sub-period returns chained,
  `(V_t - F_t) / V_(t-1) - 1` with flows at the end of their day; across a gap
  of more than one day, Modified Dietz. Annualised only over a year or more.
- **Money-weighted return**: XIRR of the reader's cash flows (start value in,
  each external flow on its date, end value out), Newton with a bisection
  fallback; both annualised and for the period.
- **Benchmark**: closes with dividends reinvested at the ex-date close, measured
  over exactly the portfolio's dates. The difference is a plain difference of
  two time-weighted returns, not risk-adjusted. A balance chart is never
  compared with a benchmark; the value-and-deposits chart is labelled as not a
  return.
- **Attribution**: for each pair of consecutive collected days, quantity held on
  the first day times the price change; contributions plus flows plus the
  remainder equal the measured change.

### Exposure (`app/brokerage/exposure.py`, `lookthrough.py`)

- **Fund holdings** come from SEC Form N-PORT (public, quarterly, about 60 days
  behind), with the report date, the filing and the share of the fund itemised.
  Leveraged and inverse funds are not looked through.
- **Look-through** splits each fund's value across what it holds; it never adds
  to the total. Company exposure = direct value + fund value x weight in fund.
- **Issuer country** is where a company is organised or based, not where it
  earns revenue. **Pricing currency** is the currency a security trades in,
  not its economic currency exposure.

### Scorecard (`app/brokerage/scorecard.py`, `scorecard-2026-10-15.1`)

Five separate assessments, no overall score. Only diversification and
financial quality carry a 0-100 score; valuation, volatility and event exposure
are described against a reference with their numbers.

- **Diversification**: effective holdings (1/HHI), largest position, largest
  sector, banded and weighted 0.4 / 0.3 / 0.3; look-through when available.
- **Financial quality**: return on equity, operating margin, free cash flow
  margin, debt to equity, revenue growth, each 0-4 against written bands; at
  least three of five required; value-weighted over assessed stocks. Funds and
  missing data are listed as not assessed, never scored low.
- **Valuation**: value-weighted earnings yield of assessed stocks against the
  S&P 500's (in line within 15%); negative earnings are never "cheap".
- **Volatility**: covariance-based annualised volatility of today's weights over
  about a year, beta to the benchmark, and the drawdown today's weights would
  have had, labelled as history.
- **Event exposure**: share of value with an event in 14 days, confirmed and
  estimated separately, plus options expiring within 7 days.

### Options risk (`app/brokerage/options_risk.py`, `options-risk-2026-10-15.1`)

Implied volatility is solved from the broker's option price and Optic's
underlying quote (Barone-Adesi-Whaley where early exercise matters, else
Black-Scholes); Greeks are scaled by contracts x multiplier. Delta is in
share-equivalents (positive gains when the underlying rises), dollar gamma is
the P&L from gamma on a 1% move, theta is currency per calendar day, vega is
currency per volatility point. Adjusted contracts are excluded from totals;
a contract whose price cannot give a volatility shows no Greeks and says why.

### Scenarios (`app/brokerage/scenarios.py`, `scenarios-2026-10-15.1`)

Sells apply before buys and cannot exceed what is held. "Cash" spends cash
including sale proceeds and scales buys down if it runs short (the shortfall is
shown); "new money" adds to the total; "pro rata" sells every other holding in
proportion. Volatility, beta and drawdown are a year of history at the
hypothetical weights, not a forecast.

## Data, history and privacy

- Transactions (`/accounts/{id}/activities`) and the provider's balance history
  (`/balanceHistory`) are fetched at most once a day per account during a sync,
  never on a page view, sealed per account under the reader's data key, and
  deleted with the account. Page views read only stored data.
- Optic keeps the newest 30 snapshots plus the last of each day for 400 days:
  collected history, labelled apart from the provider's reconstruction.
  Disconnecting an account removes it from every stored snapshot.
- Alerts and the written briefing are sealed like holdings; alert dedupe keys
  are hashes. Email is opt-in and carries only a count.
- Every workspace route reads the reader from the session, filters `accounts=`
  to the reader's own accounts, and answers like "not switched on" to anyone it
  is closed to (owner-only mode).

## Verification

- The full suite passes on the branch (6,167 tests at the last run), including:
  brokerage 61, data foundation 12, workspace routes, pieces and hard cases 22,
  performance 32, exposure 40, options risk 26, scorecard 9, scenarios 8,
  page wiring 14, SnapTrade client 22, Milo tools 21.
- Reference cases are worked by hand or from published sources: Microsoft's
  XIRR example, hand-worked TWR and Modified Dietz, a benchmark total return
  with a dividend, Hull's Greeks example (Options, Futures, and Other
  Derivatives, the chapter on the Greek letters), 1/HHI by hand, a beta of a series
  built as 1.5x its benchmark, funding rules by hand.
- Mutation checks in a scratch copy: a dropped internal-transfer match, an
  ignored multiplier, a dropped short sign, a double-counted fund, missing
  fundamentals scored as zero and a flipped in-kind direction were each caught.
- In a browser, against the sandbox provider with live market data: every
  section, account narrowing (persisted, sent to Milo), the thesis editor,
  scenarios, alerts raised by the background job, routing (refresh, tab clicks,
  Back), arrow keys on the tabs, and phone width (375px, no horizontal scroll).

## What still depends on something outside the code

| Feature | Needs |
|---|---|
| Performance before Optic's own snapshots | SnapTrade's balance-history add-on, switched on in the SnapTrade dashboard (free; up to a year of estimated daily values). Without it, returns start from Optic's first daily snapshot. |
| Transactions on the live account | The first sync after deploy fetches them; how far back depends on the broker (SnapTrade's `first_transaction_date`). |
| Look-through for funds that do not file N-PORT | No source. Shown as not looked through, with the reason. |
| Revenue geography, economic currency exposure | No source in Optic. Issuer country and pricing currency are shown and labelled as what they are. |
| Dividend pay dates and declared amounts | No source; the last amount paid is shown, labelled. |
| The Optic Desk section | A published edition (`DESK_EDITION_AUTO` or a manual publish). Without one, the section says so. |
| The written briefing | The assistant key; metered as one Milo message, cached per facts. |
| Email alerts | SMTP configured, and the reader's opt-in. |
| Current option prices for Greeks | Greeks rest on the broker's option price at its last sync and Optic's delayed underlying quote, and say when the two are far apart in time. A live option quote per held contract is not fetched. |

## Deploying

Migrations 15 (history) and 16 (theses fields, alerts, briefings) apply on
boot and only add columns and tables. No new environment variables. The
workspace inherits `BROKERAGE_OWNER_ONLY`. Rollback: the previous build ignores
the new columns and tables.
