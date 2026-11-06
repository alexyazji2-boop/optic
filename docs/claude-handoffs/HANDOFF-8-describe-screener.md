# Handoff 8: the Describe-It Screener

Branch `handoff-8-describe-screener`, cut from `handoff-5-research-library` (Handoff 5, PR #13) on 2026-11-04, because
a screen saves to the library. Its PR is based on that branch, so the diff shows this handoff alone. Not deployed.

## What existed, verified first

| The handoff asks to verify | What the code has |
|---|---|
| The screener and its catalogue | `app/analytics/screener.py`: 15 fields and 3 states over a cached ranking of NASDAQ-listed stocks (`screen.py`: 2,979 symbols, 750 past the price and liquidity gates). Price and volume only: its own text said no fundamentals. |
| The translation layer | `scan_request.py`: fixed rules, free, with Milo (one question, kept) for the words they leave over. Vague words became fixed thresholds. |
| What a request did | `POST /api/screener/ask` read the request and ran it in one call; the page showed the reading as read-only pills, after the fact. |
| What a result said | Matched and considered counts and the ranking's age in hours: no date for the data, no record, no fingerprint. Leftover words listed one by one, not as phrases. |
| Saving a screen | None: the built screen lived in one browser's storage. |
| Handoff 1's registry | Nine company figures (margins, forward P/E, cash flow, net debt), one company at a time. None is a screener field. |

So the handoff's own example, "positive revenue growth and below-average debt ratios", had nothing to land on.

## What was built

**Two fundamentals from SEC** (`app/analytics/sec_frames.py`), from SEC's XBRL frames. A frame is one concept for every
filer and one period in one file: free, the same filings the Financials tab reads, and no new provider.
- **Revenue growth.** The latest fiscal year SEC's calendar-year frame holds against the year before.
  - That is the fiscal year that falls mostly in that calendar year: Apple's to September 2025, or Nvidia's to January
    2026.
  - Both years come from the same XBRL tag for the same company.
  - The latest year is last year's from May, when every annual report is due.
- **Debt ratio.** Total liabilities over total assets on the latest balance sheet every filer has had time to file:
  a quarter-end at least 75 days back. Where a company tags no total liabilities, it is liabilities-and-equity less
  equity.
- **Coverage.** About ten files a day, cached on disk; a failure falls back to the last copy. Real coverage on
  2026-11-04 was revenue growth for 4,511 tickers and the debt ratio for 6,583.
- **No US-GAAP figure, no value.** A company that files in IFRS, or a fund, has no value. It never passes a filter on
  it, and the result counts it.
- **The first screen of the day waits.** Its run reads the frames in the background. The page says so and asks again
  every 5 seconds (with Stop waiting), and nothing partial is shown.

**The screener** (`screener.py`).
- The two new fields carry their periods.
- A bound can be strict ("above 0%").
- A bound can be against the universe: "below the median" (or the mean). It is resolved over the stocks that report the
  figure and said with its value and count ("below 54.48%, the median of the 698 stocks in the universe that report
  it").
- Every result carries:
  - `as_of`: the bars' date, or the ranking's age before a rebuild records it, and the fundamentals' periods;
  - `sources` and `peers`;
  - each filter in plain English;
  - a `fingerprint` of the filters and the data;
  - the symbols, in a fixed order (the symbol breaks ties).
- An empty result names its `binding` filter and works out a looser bound: the value that would let five of the
  stocks that reached the filter through it.
- The ranking build now records the date of its newest bar.

**The reading** (`scan_request.py`).
- Rules for the two fundamentals, written before the price rules so "revenue growth of 10%" is never a price move.
- "Below-average", "low", "less debt than peers" read as the universe's median, a stated rule the reader sees and can
  change.
- A business quality nothing can screen for ("a strong moat", "good management", "a solid balance sheet") is taken
  whole and named. It is never half-read: "strong" is not a strong price trend. It is not sent to Milo either, who
  would find no figure for it.
- What the rules leave is returned as phrases, not words.

**The routes** (`app/main.py`).
- `POST /api/screener/read` proposes without running: each filter with its plain English, label and family; the
  states; the unmapped phrases; and whether SEC's figures are needed (it starts reading them, so Run does not wait).
  The reading is shared with the old one-step route.
- `POST /api/screener` reads the fundamentals when a screen asks for them, and keeps every run in
  `app/analytics/screen_log.py`.
  - The log is a file in the data folder, trimmed to its last 2,500 lines past 5,000.
  - Each line holds the request, the filters as applied (a peer bound with its value), the data, the fingerprint and
    the symbols.
  - Nothing about the reader is kept.

**The page** (Scan, Find stocks: `pages/scan.js`).
1. **Describe.** "Read my request" reads, and nothing runs.
2. **Review.** "The filters, before anything runs":
   - each filter in plain English with its period;
   - its bounds as inputs, or for a peer bound "against the universe's median, mean or a number";
   - Remove, Add a filter, and Open in Build a screen;
   - each unmapped phrase: "Couldn't map “strong moat” to a filter, so it was left out. Nothing was put in its place."
   - With nothing to screen on, it says so and offers the builder.
3. **Run.** The result pins, once, above the list:
   - what it ran on: the filters, the universe, the dates, a peer bound's value and count, the sources and the
     fingerprint;
   - the count of stocks with no SEC figure, and a warning under 30 stocks;
   - "Screening is not investment advice: being on a list is not a recommendation. Check the figures before acting on
     them."
   - The list shows 25 at a time.
   - An empty result names the filter that emptied it and offers the looser bound. "Use this bound" edits the filter;
     Run is still the reader's.
   - Save screen sits beside the count.
- **On a phone**, each filter stacks above its controls and the pinned facts stack.

**The library** (Handoff 5's, `app/library.py` and `core/library.js`).
- A new kind, `screen`, keeps the request's words and the filters exactly as confirmed (checked against the
  screener's vocabulary), with their plain English for the list.
- Its key is the filters' canonical form hashed with FNV-1a, the same on both sides, so Save knows a screen is
  already saved and a second save asks first.
- Saved research lists it with its words. "Open and run" goes to `#/scan?saved=<id>`, which runs it at once (a screen
  costs nothing to run) and keeps that address.

## Acceptance tests (Handoff 8)

`tests/test_describe_screener.py`, with the ranking and SEC's frames stood in (40 stocks; 36 with US-GAAP figures):

- **"Positive revenue growth and below-average debt ratios": visible, editable filters, reproducible results on
  re-run.** `test_acceptance_1_*`:
  - both filters are read by the rules, with nothing unmapped, in plain English with their periods;
  - the page renders each with its controls, and reading runs nothing;
  - the run states the universe, the dates, the median (46.25% of 36) and the sources;
  - it returns exactly the five stocks that grew and sit under the median;
  - run again, it gives the same list and fingerprint, and both runs are in the log.
- **An unmappable phrase is flagged, not guessed; no invented tickers.** `test_acceptance_2_*`:
  - "strong moat" is flagged whole, and "strong" adds no trend;
  - a request of qualities alone gives no filters and the builder;
  - an invented field never reaches a run;
  - every symbol returned is in the universe.
- **The empty-result state names the binding filter.** `test_acceptance_3_*`:
  - "Revenue growth at least 500%" is named, with 40 reached;
  - the looser bound (19%) lets exactly five through when run;
  - approving it only edits.
- **A saved filter set reopens from the library and re-runs.** `test_acceptance_4_*`:
  - saved through the real library route, keyed the same in Python and JavaScript;
  - a second save is a 409;
  - read back exactly, it runs to the same list and fingerprint;
  - it is listed as a screen, and another account gets a 404.
- **Edge cases:**
  - SEC's two measures, their tag fallbacks and their periods by date;
  - the wait for SEC, with nothing partial, and its failure;
  - a mean as the peer basis, strictly below;
  - the page and the server saying a filter identically;
  - the pinned facts, the disclaimer, the paging and the phone layout;
  - a deterministic order;
  - the log keeping no reader and trimming itself.

Four existing tests changed with the same intent:
- `test_scan_link_consent`: a linked request now reads before it runs.
- `test_v2_search_nav`: one request at a time.
- `conftest.py`: the frames cache and the run log are disposable, as every other data file is.

## Live check, 2026-11-04

A local server on this branch, the local test account, the real ranking (Nov 3) and SEC's real frames.

- **Read.** "Positive revenue growth and below-average debt ratios" read as the two filters by the fixed rules.
- **The first run.** It waited while the frames downloaded (eight files, 2.7 MB), then:
  - **"249 of 750 match"**;
  - "Debt ratio below 54.48%, the median of the 698 stocks in the universe that report it";
  - as of: revenue growth for fiscal years in 2025 against 2024, balance sheets at Jun 30, 2026, and a ranking 25.5
    hours old, said to be stale;
  - 139 stocks counted as having no revenue growth in US-GAAP filings, and 52 no debt ratio.
- **Figures checked against the companies' reports:**
  - Apple fiscal 2025 revenue $416.2B against $391.0B (+6.43%), debt ratio 71.95%;
  - Microsoft +14.93%;
  - Nvidia +65.47%, its year to January 2026.
- **Run again:** the same fingerprint (a869439306).
- **Saved:** "Saved to Saved research as “Positive revenue growth and below-average debt ratios, Nov 4, 2026”".
  Saved research listed it, and Open and run reran it to the same 249 and fingerprint, at `#/scan?saved=…`.
- **"Revenue growth of at least 900% near 52-week highs":**
  - "Nothing matched. The filter that left nothing: Position in 52-week range at least 90% (2 stocks reached it)";
  - "Use this bound" changed it to "at least 25%" without running.
- **Phone, 390 px:** the filters and the pinned facts stack, and nothing scrolls sideways.

## Decisions for review

1. **SEC's frames for the two fundamentals.** They are free and already Optic's source for filings, but they are
   annual revenue and a quarterly balance sheet, not twelve months to date. Each is labelled with its period
   everywhere.
2. **"Below average" is the universe's median,** stated with its value and count, and switchable to the mean or a
   number. The median is used because a few very indebted companies pull a mean up.
3. **The debt ratio is liabilities over assets,** the textbook ratio, because it is tagged by almost every filer.
   Debt-to-equity would need debt tags that filers use inconsistently.
4. **A Milo card's "Find stocks" now reads the request for review** instead of running it, like every request here.
5. **The universe stays NASDAQ-listed** (the existing ranking). It is said on every result; widening it is a separate
   decision.

## Found and not fixed here

1. **The ranking's dates.** A ranking built before this branch has no bar date, so its result shows the ranking's age.
   The next rebuild records it.
2. **The scanner help text** says 21 and 61 sessions where the code compares 20 and 60 (found by the code read; not
   this handoff's).
3. **Handoff 1's registry** defines company figures one at a time and has none of the screener's fields. When it is
   merged, the two fundamentals' definitions could move into it.
4. **The model's reading** (for words the rules leave over) is unchanged, and its prompt does not yet know the peer and
   strict bounds. The rules read both.
