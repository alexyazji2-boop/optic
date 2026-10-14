# Research framework: methods

Version `research-1.0`, policy `policy-2026-10-14`. Code in `app/research/`;
routes `/api/framework/{T}?mode=`, `/api/framework/{T}/forecasts`,
`/api/framework-quality`, `/api/framework-policy`.

Optic's promise is "complex analysis, presented simply". The framework's job is
to keep four conclusions apart, because they have different evidence and often
different answers:

| Question | Graded by | Scale |
|---|---|---|
| Is it a strong business? | `quality.business_quality` | A to F, or Insufficient Data |
| Is the price attractive? | `quality.valuation_grade` | Attractive, Fair, Full, Stretched, or Insufficient Data |
| Is there a trade? | `swing_setup.assess` | S, A, B, Avoid, No Setup, Insufficient Data |
| What about earnings? | `earnings_view.pre_earnings` / `post_earnings` | three predictions with qualitative confidence; after a release, an A to F report grade |

Long-term conviction (High Conviction, Constructive, Neutral, Weak Structure,
Not Investable, Insufficient Data) combines the first two with the chart, by
the rules below. Nothing is averaged across questions.

**Every threshold is a rule in `policy.py`**, marked either `framework` (a
grading convention) or `assumption` (a working value that needs validating on
our data). None is an established probability or a measured edge. An operator
can change any of them with `OPTIC_RESEARCH_POLICY` (a JSON object); the output
then carries a `+custom` policy version and names what changed.

Insufficient Data is never scored as unfavourable: a missing figure is a gap in
the evidence, not evidence against the company.

## Inputs and provenance

- Statements: SEC EDGAR XBRL company facts through the valuation workspace
  (`app/valuation/inputs.py`). Every figure carries its tag, period, form,
  filing date and a link to the filing. GAAP figures, in USD.
- Prices: Yahoo Finance daily bars (two years for the swing read, twelve for
  the long-term chart) and the quote, delayed about 15 minutes in session.
  Indicators use completed bars only: today's forming bar is dropped while the
  session is open. Quote freshness is checked against the session clock
  (`service.quote_freshness`): stale beyond 30 minutes plus the feed's delay.
- Estimates: Yahoo Finance consensus (adjusted, the Street's basis), the
  estimate-trend table (7/30/90-day revisions) and the surprise history. The
  feed does not timestamp individual estimates.
- Options: the at-the-money straddle on the first expiry after the release
  (`app/analytics/earnings.py`), and the event-isolated move from the volatility
  surface when the page has one (`vol_surface.event_move`).
- Not available, and said so: company guidance text, call transcripts,
  segment-level consensus, whisper numbers, positioning, debt maturities beyond
  the next year.

## Business quality (A to F)

Seven components, each scored 0 to 4 against the rubric in `quality.RUBRICS`,
weighted (returns 22, cash 18, health 14, margins 13, growth 13, durability 12,
dilution 8) over the components that could be scored. Letters: A at 3.5 or more,
B at 2.75, C at 2.0, D at 1.25, F below. Fewer than four scored components
(`quality_min_components`) is Insufficient Data.

- **Returns on capital.** Average ROIC over the last three fiscal years minus
  WACC. ROIC = EBIT x (1 - tax) / prior-year invested capital (equity + debt +
  leases - cash and investments). When invested capital is near zero or
  negative for most years (heavy buybacks, cash larger than debt and equity),
  every year switches to after-tax EBIT over prior-year equity plus debt, so one
  average never mixes two definitions. WACC is the valuation workspace's: CAPM
  cost of equity (FRED 10-year, Blume-adjusted beta, 4.23% ERP) and an after-tax
  cost of debt from a synthetic rating, weighted at market values. Banks and
  insurers: return on equity against the cost of equity. REITs: not applicable.
- **Margins.** Latest operating margin, one point off for a range wider than 8
  points across the years read. The driver check splits the change into gross
  margin (price and mix) and the operating cost ratio (spending), and reports
  stock-based pay's share. Years with revenue under a tenth of the latest are
  left out (a launch year's margin describes nothing).
- **Growth.** Revenue CAGR over the years read.
- **Cash generation and earnings quality.** Over three years
  (`cash_conversion_years`): operating cash flow / net income and free cash flow
  (CFO - capex) / revenue. Each year where cash is below 80% of profit is
  investigated (working capital is checked as the cause) before anything is
  concluded; one year is called a question, two or more a pattern. Free cash flow
  after stock-based pay is reported beside it.
- **Balance sheet.** Net debt / EBITDA and EBIT / interest against the policy
  limits (3.0x and 4.0x, both `assumption`); current ratio and debt due within a
  year as evidence. A loss-maker is measured on runway instead: cash and
  short-term investments over last year's cash burn. Not applied to banks,
  insurers or REITs.
- **Dilution.** Diluted share count CAGR, split-adjusted (each filing's count
  multiplied by every split dated after its filing date), with stock-based pay
  as a share of revenue.
- **Durability (moat evidence).** Four measurable tests, one point each: returns
  above the cost of capital in 80% of years; operating margin range within 6
  points; gross margin of 40% or more (operating margin of 20% where gross profit
  is not tagged); revenue up in 75% of years without the margin falling more
  than 3 points. Needs three tests with data. These are traces a durable
  advantage leaves; what the advantage is needs the annual report.
- **Rule of 40** is reported only for companies growing revenue 15% or more
  (`rule_of_40_min_growth`).

## Valuation (graded separately)

Each measure 0 to 4 (4 is cheapest), averaged; Attractive at 3.0 or more, Fair
at 2.25, Full at 1.5, Stretched below. Fewer than two is Insufficient Data.

- **Intrinsic value**: the base-case value from the model that fits (DCF, or
  residual income for a bank) against the price; graded only when that model is
  the primary fit at normal confidence, otherwise shown and not graded.
- **Against its own history**: the P/E's percentile in its five-year range.
- **Cash yield, matched measures**: free cash flow to equity over market value
  (equity over equity), against the 10-year yield; free cash flow to the firm
  over enterprise value reported beside it.
- **What the price assumes**: the reverse DCF's implied revenue growth against
  the company's own record.
- **Peers**: trailing P/E (EV/EBITDA when earnings are negative) against the
  peer median. Read for long-term questions; left out of the Overview's combined
  read because it costs eight quote lookups.

## Conviction

1. Quality not graded: Insufficient Data.
2. Quality D or F: Not Investable (under this framework's quality bar).
3. Quality below `quality_cap_grade` (B): Neutral at best, Weak Structure if
   the long-term trend is broken. The rule is named in the output.
4. Quality A or B with a broken trend (below the 40- and 200-week averages):
   Weak Structure, described as technical weakness, not a failed thesis.
5. Otherwise by valuation: Attractive or Fair gives High Conviction for an A and
   Constructive for a B; Full gives Constructive for an A, Neutral for a B;
   Stretched gives Neutral. An intermediate pullback stops High Conviction at
   Constructive.

Accumulation zones are offered only at Constructive or above, from the 40- and
200-week averages, weekly support and the DCF bear value below the price, as
conditional levels to reassess at. No allocation is implied.

Two ways the investment could lose money over three years are chosen from
computed candidates, largest first: multiple compression to the five-year median
P/E, margin reversion to the average, growth the price needs above the record,
leverage, dilution, cyclical earnings, and the stock's own worst drawdown.

## Swing (S / A / B / Avoid / No Setup / Insufficient Data)

Readings on completed daily bars: 20- and 50-day EMA, 200-day SMA, RSI(14),
MACD(12,26,9), ATR(14), relative volume (today against the prior 20 sessions),
support and resistance (`technicals.support_resistance_levels`), weekly bars
(10- and 40-week averages). Relative strength is the stock's return minus SPY's
(and the sector ETF's) over 21 and 63 sessions; RSI is a different measure.

Setups: a **breakout** (within half an ATR of a level scoring 40 or more, with
levels stacked within half an ATR treated as one ceiling) and a **pullback** (to
the 20- or 50-day EMA, RSI reset). Extended price (more than 2.5 ATRs from the
20-day EMA, or RSI beyond 75 or 25) is No Setup, with what would change it.

- **Stop**: structural invalidation (a close back inside the base for a
  breakout; the pullback's low or the support band under entry for a pullback),
  widened to 1.5 daily ATRs (`atr_stop_multiple`, an assumption) when structure
  is closer. Never tightened.
- **Targets**: the next levels at least one ATR away with strength 40 or more, or
  the 52-week extreme; nearer levels are reported as obstacles. With nothing
  overhead: a measured move (the 20-session range added to the breakout level)
  or a three-ATR projection, both labelled projections.
- **Reward-to-risk**: long (target - entry) / (entry - stop); short (entry -
  target) / (stop - entry). Sensitivity: best and worst fill in the entry zone,
  and after half the spread plus 10bp slippage each way.
- **Holding period**: the target's distance in ATRs at 0.4 ATR of net progress a
  day, capped at 20 sessions; a pace estimate.

Grading (`decide_grade`), after listing the objections:

- Avoid: reward-to-risk below 1.5 (`rr_avoid_below`), or three or more serious
  objections.
- S: every criterion (daily and weekly aligned, reward-to-risk 2.5 or more, no
  earnings in the window, a clear invalidation, outperforming SPY over one and
  three months, sufficient data) and no serious caveat.
- A: at most one serious caveat and reward-to-risk 2.0 or more. B otherwise.
- Caps: reward-to-risk from 1.5 to below 2.0 caps at B; an earnings release
  inside the holding window caps at B unless an event strategy is separately
  evaluated.

## Pre-earnings

- **Hurdle**: evidence points that push the bar up or down (run-up against SPY,
  the P/E's place in its range, estimate revisions, the beat record, the revenue
  growth consensus implies against the latest quarter's). Demanding at +2 or
  more, conservative at -2 or less, balanced between; fewer than two points is
  insufficient.
- **Three predictions**, each with its evidence and confidence: results against
  consensus (beat record, revisions, implied growth, revenue trend; wide
  analyst dispersion lowers confidence), guidance (next-quarter revisions and
  margins; always low confidence, because guidance text is not in the data), and
  the reaction (the hurdle, past reactions to beats, the market backdrop).
- **Basis check**: a surprise record that is uniformly one sign by 10% or more
  over six quarters is treated as a basis mismatch (REIT FFO against GAAP is the
  usual cause) and no results call is made.
- **Options**: the straddle's move covers every day to expiry and is called an
  earnings move only when the event is isolated.
- **No probabilities**: none is validated. Confidence is low, low to moderate,
  or moderate, with the reasons.

## Forecast snapshots and scoring

`forecasts.py` stores each pre-earnings read once per ticker, release date,
method and ET day, only before the release cutoff (06:00 ET for a release before
the open, 16:00 ET after the close, midnight ET when unknown). SQLite triggers
abort any UPDATE or DELETE. Outcomes are separate rows, recorded once when the
reaction session has completed. `quality()` scores results, guidance and the
reaction separately and reports a hit rate only from 20 scored forecasts, beside
naive baselines (always predicting a beat; a coin flip on direction).

## Post-earnings

EPS against consensus with an in-line band of 1% (`inline_band_pct`), so a
marginal miss is in line; revenue against the saved pre-release consensus (the
feed replaces it after the release); GAAP diluted EPS from the 10-Q beside the
adjusted figure. The reaction session is the release day for a release before
the open, the next session after the close, and, when the timing is unknown,
whichever of the two carried the volume spike. Gap, continuation or fade,
relative volume and the move against SPY are reported with the kind of
observation (after-hours, intraday, completed session). The report grade
(A to F) averages the known criteria (EPS, revenue, growth trend, EPS against a
year earlier, operating margin against a year earlier, guidance when known),
needs three, and never reads the stock's reaction.

## Modes (`modes.py`)

The question decides first: words about a release that happened, a coming one,
more than one horizon, owning the business, or a trade. An earnings question
without tense reads the calendar (results within 10 days: post; a release within
21 days: pre). A buy-or-sell question with no timeframe is `unclear`, and Milo
gives a two-line read for each horizon or asks one question. A question under
about 28 words without "analysis", "breakdown", "full" and the like is answered
short.
