# Handoff 2: fiscal-period and definition labels (Segments and statements)

Branch `handoff-2-fiscal-labels`, cut from `handoff-1-figure-registry` (d4ff4100) on 2026-11-03, because Handoff 2 builds
on the figure registry. Not deployed.

## What was wrong

The authenticated audit of 2026-11-03 (defect 2) found Apple's Segments block labelled "FY26" for "a fiscal year ended
Sep 30, 2025". Reproduced on a local server with that day's data:

| What the page said | What was true | Why |
|---|---|---|
| "Summary, FY25", "The fiscal year to Sep 30, 2025" | Apple's fiscal 2025 ended on Saturday, Sep 27, 2025 | The date was Yahoo Finance's, which dates every period to the last day of its month. |
| Segments: "FY26", no date, under that Summary | Fiscal 2026, ended Sep 26, 2026, from the 10-K filed that morning | Segments read the filings, a year ahead of the provider's statements, and nothing on the block said which year it covered. |
| Every "FY" name | Each company's own name for its year | Names were worked out from a date, assuming every company names its year after the calendar year it ends in (`fundamentals.fiscal_label`, `financials.js fiscalLabel`). Home Depot names its years by their start: its 10-K for the year to Feb 1, 2026 is fiscal 2025, and Optic printed FY26. |
| Earnings quarters ("Q1 FY26") | Apple's Q1 FY26 ended Dec 27, 2025 | Quarter ends were stepped back from the provider's month-end year date on a 91-day grid (`reported_quarter`). |
| Apple's revenue by product "add to $834.4B" | $478.8B | The reconciliation needed a reported total for fiscal 2026, which the provider's statements did not have; without one, the filing's Products subtotal was counted on top of iPhone, Mac and the rest. |
| Geography: missing | Apple files it in its 10-K only | A breakdown with no quarterly figures was dropped, from the fiscal-year view too. |

## What was verified in the codebase

- The Segments block is `segments()` in `static/v2/js/pages/financials.js`, fed by `/api/segments/{ticker}`
  (`app/analytics/segments.py`), which reads each 10-K's and 10-Q's XBRL instance. Its labels came from
  `fiscalLabel()` over the provider's `fiscal_year_end`; its reconciliation total from the provider's statements.
- The statements are Yahoo Finance's (`app/analytics/fundamentals.py analyse_financials`), dated to month ends.
- SEC company facts, which Handoff 1's registry already loads for every Dossier (`app/valuation/inputs.py Filings`),
  record with every fact the filing it came from and the fiscal year and period the company assigned that filing.
- v2 printed fiscal names on Financials, the Overview (revenue line, Simple analysis, research view), Earnings, the
  research sheet, Milo's figure cards, the research framework's evidence and the DCF page's reported years.

## What was built

**The calendar, from the filings** (`app/figures/periods.py`). A 10-K's own period ends on the last date it reports, so
each 10-K gives a fiscal year exactly: start, end, the company's own name for it, and the filing. Each 10-Q gives a
quarter; the fourth quarter is the 10-K's year after the third. Names are taken from each period's own filing, never a
comparative in a later one, and an amendment or a cover-page name outside the possible years names nothing. The calendar
says how the year is set ("the last Saturday of September", "June 30", "the Sunday nearest the end of January"),
which years had 53 weeks, and each change of year end with its transition period (a 10-KT, or a 10-QT for a short one).
Measured on real filings, 2026-11-03: AAPL, MSFT, JPM, NVDA, HD, VFC (10-QT, 2018), CMP (10-KT, 2021), TSM (IFRS: no
calendar, dates only).

**A description for every period** (`describe()`): its type and badge, exact start and end, the company's short name
("FY25", "Q3 FY26"; "2025" for a calendar year), a plain label ("Fiscal year ended Sep 27, 2025"), its length when it
had 53 weeks or 14, and the filing. A provider's month-end date is matched to the filing's own (within ten days). A
period no filing reports is dated only ("Year to Mar 31, 2026, as Yahoo Finance dates it"); a period with no date is
"Period labels unavailable". The one exception is the period right after the latest filed one, because results come
out days or weeks before the 10-Q or 10-K (Apple's fiscal 2026 on Oct 30, its 10-K on Nov 3). It is named by its place
in the company's own calendar: the quarter after the third is the fourth. It is dated by how the year is set ("about"
for a 52- or 53-week year, whose extra week may fall in it), and it says "not yet filed".

**Where they reach the pages, with no new feed:**

| Payload | What it carries |
|---|---|
| `/api/ticker` `figures.periods` | The calendar and a description for every column of the provider's statements; every registry figure's period gains its name (`fiscal`) and badge |
| `/api/segments` | A description and the filing read from for every period; each table's reported totals from the company facts for the same periods (a fourth quarter as the year less nine months); tables filed only in the 10-K, kept in their own `annual_only_tables` list (Classic and the sum of the parts read `tables` as quarterly grids, and are unchanged) |
| `/api/earnings` | Each report's quarter from the filings (`period`, `fiscal`), each growth row's period, the statements' basis; no name when the filings cannot be read, and the reason |
| Milo | Tool figures name the year ("Fiscal year ended Sep 26, 2026 (FY26)"); page context drops the provider's guessed names and sends the filings' |
| Research framework, DCF | Each year as its 10-K names it, with its end date; forecast years by month and year |

**The period line** (`static/v2/js/ui/period.js`, `core/periods.js`): beside the title of Financials' Summary, Statements
and Segments and Earnings' two blocks. It shows a period-type badge (Annual, Quarter, TTM) and an accounting-basis badge
(GAAP, IFRS, Analysts' basis, Basis not stated). Then the period in words with its end date, the filing it was read
from, and what else must be said: a 53-week year, a derived fourth quarter, a change of year end, a block a year ahead of
the statements. Badges are words in squared tags. Free cash flow, EBITDA and net debt carry a Non-GAAP badge where the
rest is GAAP. Every fiscal name on a page comes with its date: under it in a table heading, after it in a sentence, as a
chart tick's second line, and in full in the tick's tip and the chart's description.

**Segment reconciliation, until Top 25 #13:** every breakdown says what its parts add to against the filing's own total
for the same period, which way and by how much they miss it, or that it was not reconciled and why.

## Acceptance tests (Handoff 2)

`tests/test_fiscal_periods.py`, drawn by the pages' own code in JavaScriptCore from payloads the server's own code builds:

- **AAPL Segments block** (`test_acceptance_1_*`): reads "FY26, fiscal year ended Sep 26, 2026", the correct current-year
  equivalent at test time, with Annual and GAAP badges (Quarter and GAAP in the quarters view; TTM is the registry's
  twelve-month figures' badge) and the 10-K link, beside the title.
- **No bare FY label** (`test_acceptance_2_*`): no "FY##" without an end date in Financials (both views), the Overview,
  Earnings and the research sheet for the test set (AAPL, MSFT, JPM, HD, a company with no filings); Compare prints none.
  The check is shown to catch the labels the pages printed before.
- **Non-December year ends** (`test_acceptance_3_*`): AAPL (September, 52/53 weeks), MSFT (June), HD (late January,
  named by its start) and JPM (December).
- Edge cases: 52/53-week years, a change of year end (10-KT and 10-QT), annual-only segments, missing fiscal metadata.
- The CI check: no v2 page reads the provider's guessed names or builds one from a date.

## Live check, 2026-11-03 after the close (local server on this branch, real data)

AAPL Financials: Summary "FY25, fiscal year ended Sep 27, 2025, from the 10-K filed Oct 31, 2025", noting that free cash
flow, net margin and net debt are from FY26's 10-K. Statements "Fiscal years ended Sep 24, 2022 to Sep 27, 2025 (FY22 to
FY25)" with FY23's 53 weeks. Segments "FY26, fiscal year ended Sep 26, 2026, from the 10-K filed Nov 3, 2026", every table
"The parts add to the $478.8B the 10-K reports"; geography shown again. Quarters view: "Q4 FY26, quarter ended Sep 26,
2026", reconciled against the year less its first three quarters. Earnings: "Q1 FY25 to Q4 FY26". HD: "FY25, fiscal year
ended Feb 1, 2026". MSFT: Q1 FY27 for the quarter to Sep 30, 2026. No sideways scroll at 375px; the line wraps under the
title. The calendar costs 4 to 5 ms per Dossier load and about 9.5KB of a 290KB `/api/ticker` payload.

## Found and not fixed here

1. **Home's What Matters Today** (`app/earnings_result.py`) still names a report's quarter with the old rule
   (`reported_quarter`). It is not a Dossier or Compare page; the fix is the same `periods.for_report`.
2. **Investing's valuation history** labels each year with the provider's month-end date ("Sep 30 2025"): a date, not a
   name, but not the filing's day.
3. **The statements are still the provider's**, a year behind the filings for a few days after a 10-K (Handoff 1's
   follow-up 3). The Summary and Segments now say so; registering statement series would remove it.
4. **Full segment reconciliation and resegmentation flags** remain Top 25 #13. This handoff states the reconciliation
   line, or that there is none, on every breakdown.
5. **Classic** (`/classic`) is untouched, under the owner's rule that it takes security fixes only.
