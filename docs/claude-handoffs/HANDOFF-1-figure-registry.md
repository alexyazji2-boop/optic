# Handoff 1: one value for each financial figure (the canonical figure registry)

Branch `handoff-1-figure-registry`, cut from `main` at c623c264 on 2026-11-03. Not deployed.

## What was wrong

The authenticated audit of 2026-11-03 found the same AAPL figure printed with different values on different pages,
under labels that did not say why. Each conflict traced to a cause in the code:

| Figure | Values seen | Cause in the code |
|---|---|---|
| Net debt | $62.7B and $44.0B | The Financials chart caption (`core/finviz.js netCashLine`) subtracted cash and equivalents only; the block beside it (`fundamentals.py net_cash`) subtracted cash and short-term investments. Milo's research pack (`app/desk/research.py`) used the first definition, the research framework (`quality.py`) a third (with finance leases), and the comps bridge a fourth (enterprise value less market cap). |
| Net margin | 26.9% and 27.6% | The Overview fell back from the statements' fiscal-year margin to the feed's own twelve-month `profitMargins`, and printed both under labels that did not say which period each covered. |
| Forward P/E | 30.9 and 31.2 | Compare read the long-term model's copy, worked from the feed's `forwardPE` at another moment's price; the Dossier read the quote. |
| Free cash flow, operating cash flow | several | The Dossier read Yahoo's statements, which still ended at fiscal 2025 on 2026-11-03, while the valuation workspace read the fiscal 2026 10-K, filed that morning. |

## What was verified in the codebase

- No figure registry existed. Each page computed or read its own copy (listed above), and v2 printed raw fields
  (`quote.forward_pe`, `quote.profit_margin`, `financials.margins.net_pct`, `balance_sheet.net_cash`) on eight pages.
- Definitions existed only as glossary text (`static/v2/js/ui/term.js`), with no formula, period or source.
- SEC filings were already read, with tags, forms, filing dates, links and restatement detection, by
  `app/valuation/inputs.py` (the valuation workspace and the research framework). Loading a company's facts takes
  0.2 to 0.9 seconds cold and is cached for a day.
- Milo's tools return JSON with a `meta` block per lookup; the answer's "Data Milo retrieved" list comes from
  `milo_tools.Record.public()`.

## What the registry is

`app/figures/registry.py` holds one entry per figure: name, plain-English definition at each of the five knowledge
levels, formula in words and symbols, inputs, period type, accounting basis, what it cannot tell you, and the related
entry. Served as data at `GET /api/figures/registry`, fetched once per session (an hour's cache).

| Id | Name | Period | Formula |
|---|---|---|---|
| `net_margin_fy` | Net margin, fiscal year | Fiscal year | Net income / revenue x 100 |
| `net_margin_ttm` | Net margin, last 12 months | 12 months | The same over the last four reported quarters |
| `forward_pe` | Forward P/E | Forward estimate | Price / forward EPS |
| `free_cash_flow_fy`, `_ttm` | Free cash flow | Fiscal year, 12 months | Operating cash flow - capital expenditure |
| `operating_cash_flow_fy`, `_ttm` | Operating cash flow | Fiscal year, 12 months | Net cash provided by operating activities |
| `net_debt` | Net debt | Balance sheet date | Debt + finance leases - cash - short-term investments |
| `net_debt_with_leases` | Net debt including operating leases | Balance sheet date | Net debt + operating lease liabilities |

Where two definitions are both legitimate (fiscal year or twelve months; with or without operating leases) they are
two entries, and a page that shows both labels both.

## How a value is computed, once

`app/figures/compute.py resolve()` computes every registered figure for one company:

- **Statements:** the company's SEC filings (XBRL company facts, us-gaap) through `app/valuation/inputs.py`, the
  reader the valuation workspace already uses. Twelve months are the last fiscal year plus this year to date, less
  the same months a year earlier, with the four quarters listed. A company with no usable US-GAAP filings (a foreign
  issuer filing IFRS) falls back to Yahoo's statements, and every figure says so: provider named, no filing link,
  restatement history unavailable. If the filings stop 300 days or more before the provider's latest year (a company
  now filing under a new CIK), the provider's statements win.
- **Forward P/E:** the price on the page divided by the feed's forward EPS, so it cannot be another minute's price.
  Which fiscal year the estimate covers is shown as "not disclosed by the provider". For a foreign listing, whose EPS
  currency the feed does not state, the provider's own ratio is shown and said to be the provider's.
- **Text:** every value carries its formatted `text`, one rounding for every surface.
- **Edge cases:** a restated input carries the filing date and the earlier value ("Restated in a filing on DATE; the
  earlier filing gave X"); a margin on zero or negative revenue, or a P/E on a forecast loss, is "Not meaningful"; a
  missing line is "Not reported", never zero; money carries its reporting currency; a failed source is "Temporarily
  unavailable" figure by figure, never another page's value.

The research framework's balance-sheet check calls the same `net_debt_value()`.

## Where it is read

| Surface | How |
|---|---|
| Dossier (`/api/ticker`) | `figures` block, built beside the snapshot's other fetches (`include_figures=True`) |
| Overview, Simple and Advanced | Net margin and forward P/E from the block; key statistics' labels and values open the definition |
| Financials | Summary cards, readings and the latest block; the chart caption states cash and debt, no net figure of its own |
| Research sheet, Thesis check, workspace widget, chart widgets, Investing | From the block or the long-term model's registry figures |
| Compare (`/api/compare`) | Each row's forward P/E is the snapshot's registry figure |
| Milo | `get_quote`, `get_fundamentals`, `get_valuation`, `get_assessment` and `compare` carry a `figures` set; the research pack carries the registry's items in place of its own; page context sends `figures` and drops the raw copies; the answer's sources list each figure as a control that opens the same definition |
| Long-term model | Its forward P/E and net margin notes are the registry's |

Pressing any registry figure opens its definition: on a wide screen beside the figure, on a phone as a sheet from the
bottom with the page in view above it. If the definitions cannot be loaded, every figure on the page says "(definition
unavailable)" and the panel offers a retry; a figure the server could not work out says "Temporarily unavailable" and
its panel's Retry asks for the company's figures again. Nothing older is shown in its place.

## The check that fails the build

`tests/test_figure_registry.py`:

- every entry has every field and a definition at every level, and no definition judges a reading;
- no v2 page reads one of these figures from a raw field (only `core/figures.js`, and the fiscal-year history charts on
  Financials and in Milo's figures, are allowed);
- every figure id a page names is registered;
- the check itself is shown to catch a raw read and an unregistered id;
- the five figures match across the Dossier's block, Compare's row, Milo's tools, the research pack and the long-term
  model, on one company's data;
- the edge cases above.

## Live check, 2026-11-03 after the close (local server on this branch, real data)

AAPL on `/api/ticker`, `/api/figures/AAPL`, `/api/compare` and `/api/longterm`: forward P/E 31.1, net margin 27.6%
(fiscal year ended Sep 26, 2026), free cash flow $136.1B, operating cash flow $145.1B, net debt $24.8B, net debt
including operating leases $37.8B, from the 10-K filed that day. The same text on every endpoint.

## Found and not fixed here (the backfill's next steps)

1. **Brokerage scorecard** (`app/brokerage/scorecard.py`): "Free cash flow margin" divides Yahoo's `freeCashflow`, a
   provider-estimated levered figure, by revenue: a different definition of free cash flow under the same name.
2. **Stock maps** (`app/analytics/stockmaps.py`): forward P/E and profit margin across the universe from the feed's own
   fields.
3. **History series** on Financials and in Milo's figures: Yahoo's statements, which can be a year behind the filings
   for a few days after a 10-K (AAPL, 2026-11-03). Registering series is the next step.
4. **Revenue and net income growth** on the Overview still read Yahoo's latest fiscal year; when it is older than the
   registry's, the Overview now says which year the margin is for.
5. **Research framework texts** (`quality.py`) print their own multi-year free cash flow sums and format net cash in
   whole dollars; same values, different text.
6. **Compare's row note** says forward P/E is against "next year's expected earnings"; the provider does not say which
   year.
7. **Classic** (`/classic`) is untouched, under the owner's rule that it takes security fixes only.
