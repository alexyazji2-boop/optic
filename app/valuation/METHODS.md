# Fair-value model: methods, conventions and data

Model version `dcf-1.0`. Code: `app/valuation/` (engine, inputs, classify,
defaults, analysis, service, store) and `static/valuation.js` (the workspace).
Tests: `tests/test_valuation_engine.py`, `tests/test_valuation_inputs.py`,
`tests/test_valuation_service.py`, `tests/test_valuation_page.py`.

The engine does all the arithmetic. The page only displays it, and Milo only
explains it. A reader's edit is sent back to the engine and recomputed.

## 1. Enterprise DCF (free cash flow to the firm)

For each forecast year *t* = 1..N (N = 3 to 15, default 10):

```
revenue_t      = revenue_{t-1} x (1 + g_t)
EBIT_t         = revenue_t x margin_t
taxes_t        = max(0, EBIT_t - loss carryforward used) x tax_t
NOPAT_t        = EBIT_t - taxes_t
D&A_t          = depreciation rate x net PP&E_{t-1}        (PP&E roll-forward)
PP&E_t         = PP&E_{t-1} + capex_t - D&A_t
capex_t        = revenue_t x capex share_t
NWC_t          = revenue_t x NWC share            (operating working capital)
FCFF_t         = NOPAT_t + D&A_t - capex_t - (NWC_t - NWC_{t-1})
```

* **Growth path.** Year 1 (and 2, when given) as set, then equal steps to the
  terminal rate, which the year after the forecast reaches.
* **Margin, capex and tax paths.** Each moves in equal steps from its start to
  its target over the stated number of years, then holds.
* **Loss carryforwards.** A negative EBIT pays no tax and builds a carryforward
  that shelters later EBIT in full. Losses before the base year are not
  counted (the filings' deferred-tax note would be needed), which understates
  the value of a company with large existing losses.
* **Without PP&E** (some filers do not tag it), D&A is a share of revenue, the
  three-year average. Depreciation is never assumed to be zero: the model
  refuses to run without one of the two.

### Timing

* Cash and debt are taken from the **latest balance sheet** (a 10-Q when one is
  newer than the 10-K). The cash flows counted are those **after** that date.
* The first forecast year is the fiscal year after the last 10-K (FY0). Its
  cash flow is scaled by the **stub**: the fraction of that year after the
  balance-sheet date.
* Time is measured in **fiscal years** from the valuation date (today). The
  first year-end is at (FY1 end - today) / FY1 length; each later one adds
  exactly 1.
* **Mid-year convention** (default): each year's flow is discounted from its
  middle; the stub's from its own middle. A flow that falls before the
  valuation date is counted at face value, not compounded forward.
  **End-of-year** is available.

### Terminal value

Two methods, both refused when terminal growth g >= discount rate:

* **Value driver** (default, McKinsey's key value driver formula):
  `TV = NOPAT_{N+1} x (1 - g / RONIC) / (WACC - g)`, where
  `NOPAT_{N+1} = revenue_N x (1 + g) x margin_N x (1 - long-run tax)`. Growth
  costs reinvestment at the return on new invested capital (RONIC). With
  RONIC = WACC, growth adds no value and `TV = NOPAT_{N+1} / WACC`. A
  reinvestment rate g / RONIC above 100% is refused.
* **Growing last cash flow:** `TV = FCFF_N x (1 + g) / (WACC - g)`, reported with
  the RONIC it implies (warned when implausible).

TV is valued at the end of year N. Under the mid-year convention it is
discounted half a year less, because its flows also arrive mid-year (the
standard treatment for a growing perpetuity). An **exit multiple** cross-check
(EV/EBITDA x EBITDA_N, discounted from the end of year N with no half-year
adjustment, since a multiple is a price at a date) is shown with the
perpetual growth it implies. By default it uses today's trading multiple. That
is circular as a value anchor, so it is labelled a check, never the answer.

### Enterprise value to equity

```
equity = EV + cash + short-term investments + long-term and equity-method investments
            - debt - finance leases - preferred stock - non-controlling interests
            - unfunded pension obligations
value per share = equity / diluted shares
```

| Item | Treatment | Why |
|---|---|---|
| Cash | All treated as surplus | Operating cash is not separable from the filings; slightly overstates value. |
| Investments | Book value | Their income is below EBIT, so it is not in FCFF; a listed or recently funded stake's market value can differ a lot. |
| Equity-method stakes | Assumed inside `LongTermInvestments` when that tag exists; otherwise added | Avoids counting them twice. |
| Debt | Long-term incl. current maturities + short-term borrowings and commercial paper, at book | Tag rules A-D below; market value not in filings. |
| Finance leases | Debt | Interest is below EBIT; principal is financing. Not added again when the company reports debt *with* finance leases. |
| Operating leases | **Not** debt | Their cost is inside EBIT. Subtracting the liability too would charge them twice. |
| Stock-based compensation | Expense left in EBIT, **not** added back | Awards already granted are in the diluted share count (the company's own diluted-EPS increment). Future grants are paid for through the expense. Adding it back *and* counting future dilution would charge it twice; adding it back and ignoring dilution would charge it never. |
| Preferred | Liquidation preference if tagged, else carrying value | A senior claim. |
| Non-controlling interests | Book value, subtracted | FCFF includes 100% of consolidated subsidiaries. |
| Pension | Funded status from the latest 10-K, pre-tax; a deficit is a claim, a surplus is ignored | A surplus is rarely freely available to shareholders. |

**Diluted shares** = cover-page shares outstanding (dei) + (weighted diluted -
weighted basic shares of the latest reported period, which is the
treasury-stock-method increment the company itself counted). Several share
classes leave no cover-page total, so the balance-sheet count is used. The
quote's market value implies a count, and a gap of more than 5% is flagged.

### Net-cash and loss-making companies

Net cash simply adds through the bridge. Negative FCFF in forecast years is
discounted like any other flow. When their present value is negative, the
terminal value is more than 100% of EV, and the page says so in words. A
negative equity value is reported as the model leaving nothing for
shareholders, never floored to zero. A terminal margin <= 0 is flagged as not
meaningful.

## 2. Discount rate

```
cost of equity = risk-free + beta x ERP + extra premium           (CAPM)
WACC           = E/V x cost of equity + D/V x pre-tax cost of debt x (1 - marginal tax)
```

| Input | Default | Kind |
|---|---|---|
| Risk-free | FRED DGS10, latest daily close (fallback: Yahoo ^TNX) | Market |
| Beta | Yahoo's beta (5-year monthly regression), Blume-adjusted 0.67 x raw + 0.33. When the quote has none, Optic computes the same regression from 5 years of monthly prices against SPY (at least 36 months), labelled as computed. | Market estimate |
| ERP | 4.23%, Damodaran's implied premium for the S&P 500, January 2026 | Estimate |
| Cost of debt | Risk-free + synthetic-rating spread from EBIT / interest (Damodaran's large non-financial table, January 2026). With operating losses, the filings' interest / debt instead. | Estimate |
| Weights | Equity at market (price x diluted shares), gross debt + finance leases at book | Gross, because cash is valued in the bridge |
| Tax shield | 25% marginal (US 21% federal + about 4% state) | Assumption |

The reader can override any part, set the debt weight, or set WACC directly.

## 3. Defaults (base case)

None of these is a forecast Optic makes. Each is shown with its reason and
kind.

* **Growth:** analysts' average revenue estimates for the current and next
  fiscal years (Yahoo), used only when their base year matches the filings'
  FY0 within 3%. Otherwise the three-year revenue CAGR. Fades to terminal.
* **Terminal growth:** 2.5%, kept at least 0.5 points below the risk-free rate.
* **Margin:** starts at FY0's EBIT margin and reverts to the three-year average
  over five years. For cyclicals, halfway between FY0 and the five-year
  average over three years (five years may not span a cycle). For a company
  without operating profit, a labelled 8% placeholder over seven years.
* **Capex:** halfway from FY0's share of revenue to the three-year average,
  over five years, the same rule in both directions. For a loss-maker spending
  above 8% of revenue, a labelled 8% placeholder.
* **Depreciation rate:** three-year average of D&A / prior-year net PP&E.
* **Working capital:** FY0's share of revenue, held, so there is no
  artificial first-year step.
* **Tax:** three-year average effective rate (clamped 5-35%), converging to
  halfway between it and 25%.
* **RONIC:** halfway between WACC and FY0's ROIC (capped at 40%); WACC when
  ROIC is below it.

**Scenarios** move growth (by max(3 pts, 25% of year-1 growth)), the target
margin (by max(2 pts, 10% of it)), the capex target (2 pts), terminal growth
(0.5 pts) and RONIC (bear: = WACC; bull: the same distance above base) by the
same amount in each direction. The discount rate is the same in all three,
because its uncertainty is shown separately in the sensitivity tables.

## 4. Analysis

* **Sensitivity grids:** WACC x terminal growth, target margin x growth shift,
  capex x WACC. Every cell is a full model run. A cell with growth at or above
  the discount rate is blank.
* **Tornado:** each driver moved by a stated step (WACC +/-1 pt, terminal
  growth +/-0.5, margin +/-2, growth +/-2 every year, capex +/-2, RONIC +/-2,
  tax +/-3, NWC +/-3), ranked by swing.
* **Reverse DCF:** bisection for (a) a uniform shift to the growth path,
  (b) the target margin, and (c) the discount rate that makes the model value
  equal the price, each holding everything else.
* **Upside** = value / price - 1. **Margin of safety** = 1 - price / value
  (defined only for a positive value; shown as none when the price is above).
* **What-ifs:** capex staying at FY0's level, margins holding at FY0's level,
  RONIC = WACC, WACC +1 pt.

## 5. Other methods (shown side by side, never averaged)

* **FCFE** at the cost of equity: FCFF - interest x (1 - t) + net borrowing.
  Net borrowing = debt weight x net reinvestment (Damodaran's target-ratio
  form), using the same debt weight as the WACC. Losses are not
  debt-financed. Cash and investments are added, and preferred, NCI and
  pensions subtracted. Where both fit, it lands close to the FCFF value, which
  is a consistency check.
* **Dividend discount, two stage:** five years at the base case's average
  revenue growth (capped at ROE x retention), then terminal growth, at the
  cost of equity. It fits when dividends are a steady 30-110% of earnings and
  are not outweighed by buybacks.
* **Residual income** (banks, insurers): book value per share + PV of
  (ROE - cost of equity) x opening book, with ROE fading halfway to the cost
  of equity over ten years, then justified P/B (ROE - g) / (r - g). Book grows
  along a path from what the company has retained (ROE x (1 - payout incl.
  buybacks), capped at 15%) to the long-run rate. The payout is 1 - g / ROE,
  so a high ROE cannot compound a fully retained book for a decade. Also
  reports the ROE implied by today's P/B: g + P/B x (r - g). An ROE above
  twice the cost of equity is flagged as a possible cyclical peak.
* **REIT FFO** (approximately NAREIT): net income to common + D&A +
  real-estate impairments - gains on property sales. It reports P/FFO, the
  dividend share of FFO, and today's FFO at the company's own past P/FFO
  range. D&A includes some non-property D&A. AFFO is not computed: it needs
  maintenance capex and straight-line rent, which are not consistently
  tagged.
* **Comparable companies:** the largest companies in the same Yahoo industry
  (or the reader's list). EV/EBITDA, EV/revenue, P/E and P/B at the peers'
  25th, median and 75th percentile, applied to the company's own trailing
  metric from the same source. Enterprise multiples go through that source's
  net debt. Market-relative.
* **Sum of the parts** (on request): each reported segment's operating income
  over the last four consecutive quarters (from the filings' XBRL instances,
  `app/analytics/segments.py`) x the reader's EV/EBIT. Corporate costs and
  eliminations are valued as a negative at the unallocated multiple, and the
  result goes through the same bridge. Multiples start at the DCF's implied
  EV/EBIT, which reproduces the whole. Non-consecutive quarters are refused,
  not annualised.
* **Linked three-statement forecast (condensed):** income statement, balance
  sheet and cash flow, with cash as the plug and a balance check every year.
  Its FCFF equals the DCF's when taxes are linear. Payouts give way (buybacks,
  then dividends, then a revolver) before cash falls below 2% of revenue. It
  is not used for the value.

## 6. Classification

The SEC SIC code first, then Yahoo's industry: REIT (6798), bank or lender
(602x, 603x, 6111, 614x-617x), insurer (631x-639x, not brokers), utility
(49xx), cyclical (mining, oil, metals, chemicals, shipping), not yet
profitable (latest EBIT <= 0, or two of the last three years). Banks and
insurers get no FCFF DCF. REITs get FFO first and a DCF only if EBIT is
tagged. Loss-makers get low confidence and the reverse DCF first.

## 7. Inputs and provenance

* Statements: SEC EDGAR XBRL company facts (us-gaap), one fact per concept per
  period. Flows are matched to fiscal-year ends (annual duration, 10-K family,
  within a week for 52/53-week years). Balances are matched to the exact date.
  The tag priority list is in `inputs.TAGS`. The latest filing of a period
  wins (restatements), and the change is marked `restated`.
* **EBIT without an operating-income line** (some filers, e.g. Nucor) =
  pre-tax income + interest expense - interest income, labelled derived. It
  still contains other non-operating items.
* Every fact keeps its tag, unit, period, form, filing date, accession link and
  retrieval time. Composite figures keep their parts and rule. An item a
  filing does not report is "not reported" and treated as none, said so; a
  figure the model needs and lacks blocks the model instead of being guessed.
* **Debt tag rules:** A, debt and finance leases incl. current maturities; B,
  `LongTermDebt`; C, noncurrent + current (`DebtCurrent` already includes
  short-term borrowings); D, separately tagged notes, secured, unsecured and
  credit-line debt summed (REITs), flagged. A quarter-end debt figure more
  than 40% from the last 10-K's is flagged.
* US-GAAP filers only. IFRS (20-F) filers and new registrants without annual
  history are reported as not covered.
* Data quality is checked and stated: restated years, stale annual reports,
  currency mismatch, share count vs market value, and debt jumps.

## 8. Saved models

A snapshot stores the engine's base (the reported numbers), the full
assumptions, the result and the input dates. It replays exactly on the same
engine version and says when the version has changed. Snapshots are never
edited, so saving again makes a new one. Signed-in readers get
`/api/valuation-models` (per-user, CSRF-guarded); signed-out readers keep
snapshots in `localStorage` (`optic.dcf.v1`), replayed by
`/api/valuation-models/replay`.
