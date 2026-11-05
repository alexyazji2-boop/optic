# Handoff 9: the Company Event Timeline

Branch `handoff-9-event-timeline`, cut from `main` (c623c264) on 2026-11-04. It depends on no other handoff, so its
PR is based on main. Not deployed.

## What existed, verified first

The handoff asks to verify, per source, what the date is. Each was read in the code:

| Source | Where Optic reads it | The date it gives | A link |
|---|---|---|---|
| News | `news.analyse` over Yahoo Finance's feeds (`/api/ticker`'s `news`, `/api/news/{t}`) | `published`: when the story was published, an instant in UTC. Its own note: "the event itself may be earlier or later" | The article |
| Earnings | the provider's `earnings_history` and `earnings_calendar`; `analytics/earnings.py` `_next_report` | the report's New York day, with before the open or after the close where the feed has it; the next date is an estimate or confirmed | None in the feed; Optic cites Yahoo's earnings calendar page |
| Insiders | the provider's `insiders` (Yahoo's Form 4 list), filled from SEC Form 4s by `insider_fill` | the transaction date. Yahoo gives no filing date; "an insider has two business days to report" (`insiders.py`) | None from Yahoo; an SEC row has its accession |
| Congress | `analytics/congress.py`, the Clerk of the House's filings, current year, House only | `filed` (the day the House received it) and `traded`, with the days between | The filing's PDF |
| Analysts | `analysts.for_symbol` over Yahoo's upgrades and downgrades | when Yahoo recorded the action (UTC), "usually the day it was announced" | None; Optic cites Yahoo's analysis page |
| Filings | `analytics/filings.py`, EDGAR's submissions | the filing date | The document |

Two things in the provider mattered:
- **Failure read as empty.** A failed fetch came back as an empty list or dict (`_Failed` unwrapped in `_fill`), and a failed news fetch was caught inside `news()` and returned `[]`. A timeline built on those would have shown a silent gap.
- **No per-company aggregation in v2.** The closest existing aggregator, `catalysts.ticker_catalysts`, is Classic's.

## What was built

- **`app/timeline.py`**:
  - one function per source, each calling what the Dossier already calls (the same cache keys, so mostly cache hits);
  - each source normalised to entries of one shape: date, type, title, summary, source, source_url, delay_note, the date's kind and the detail an entry opens to;
  - sources run side by side, and one that has not answered in 25 seconds is said to have timed out;
  - the build is kept 5 minutes, or 30 seconds when a source failed.
- **`app/providers/yf.py` `noting_failures()`**: on one thread, lists the cache keys whose fetch failed, whether it raised or came back as the failure marker. The timeline wraps each source's calls in it, so a failed feed is a failure, not "none".
- **`GET /api/timeline/{ticker}?days=30|90|365&type=all|news|...&page=&per=`**: one page of entries, newest first, with every source's state, count, coverage, the meaning of its dates and its empty-state words.
  - **Deduplication:** only by the same source's same item (a story's link, a filing's or a Form 4's accession).
  - **Nothing is merged across sources:** an 8-K announcing results and the earnings entry for the same report stay two entries.
- **The Overview's Company events section** (`ui/timeline.js`, between the analysis and the disclaimer, in both views):
  - **Controls:** 30 days, 90 days or 1 year, and All, News, Earnings, Insiders, Congress, Analysts and Filings, each with its count.
  - **An entry:** its date (a time in the reader's zone with its name, or the day as the source dates it), what the date is, its kind as a word beside an icon, a one-line title and summary, the delay note, and its source with a link.
  - **Details:** the figures with their definitions and periods, what the date means, and a link to the Dossier section it comes from.
  - **50 at a time,** then "Show 50 older".
  - **A failed source** is said above the list with Try again. A kind with nothing says so in the handoff's words.
  - **Loading:** it reads only once `/api/ticker` has answered, so the Dossier's first load is unchanged. It is kept through the Overview's redraws as the thesis check is.
- **Where entries link back:**
  - news to the News tab;
  - earnings to the Earnings tab;
  - insider trades and filings to their sections of Financials (`?section=fin-ownership`, `fin-filings`, which the page now opens at, focus included);
  - congressional trades to the Insiders page's House view;
  - analyst actions to the Analysts page (`?symbol=`, which it now opens on, a year shown).
- **Wording:**
  - "Sale of 129,963 shares by COOK TIMOTHY D, Chief Executive Officer", "Hon. Pete Sessions disclosed a sale of $250,001 to $500,000".
  - Delay notes say when it became public: "Disclosed Oct 27, 2026; the trade occurred on or around Oct 2, 2026. Members may disclose a trade up to 45 days after it."
  - Nothing calls a trade a signal; the method says it is not one.

## Acceptance tests (Handoff 9)

`tests/test_event_timeline.py`, every source stood in (no feed is reached), the clock pinned to Nov 4, 2026, 4 PM New
York:

- **AAPL shows news, earnings, insider and analyst events in date order with sources; congressional entries carry
  disclosure-lag notes.** `test_acceptance_1_*`:
  - all six kinds;
  - newest first, the scheduled report on top;
  - every entry with its source and a link;
  - the figures as given;
  - each congressional entry with "Disclosed …; the trade occurred on or around …. Members may disclose a trade up to 45 days after it", the 73-day one saying so, the mistyped one saying which date is impossible;
  - drawn on the page with its words.
- **Type filters work; empty-type states render.** `test_acceptance_2_*`:
  - each type returns only its own entries;
  - the counts are the period's whatever the filter;
  - MSFT's congress is "No congressional trades reported for this company in this period.";
  - a source that does not apply says why;
  - bad parameters are refused.
- **One-source failure renders a partial timeline and a note, not a silent gap.** `test_acceptance_3_*`:
  - the analyst feed refusing: "Analyst actions temporarily unavailable…", the other five kinds drawn, the chip saying unavailable, Try again;
  - the news and earnings feeds failing inside the provider's own cache, where the provider returns empty, still caught as failures;
  - a slow source said to have timed out, the rest not held for it.
- **Date-type labels are correct per source.** `test_acceptance_4_*`:
  - Published, Reported and Scheduled, Transaction date, Disclosed (on the filing day, not the trade day), Recorded, Filed;
  - a 2 AM UTC story on its New York day;
  - an analyst record with no time kept on its day;
  - times in the reader's zone with its name (6:00 PM PST, 9:00 PM EST);
  - a dated record never moved by a zone.
- **Edge cases:**
  - the same story or filing twice is one entry, and two sources stay two;
  - indistinguishable rows are both kept with their own ids;
  - a passed report date with no results;
  - pages of 50 and the three periods;
  - coverage shorter than the period said;
  - neutral wording;
  - the provider's failure notes, accessibility and the phone layout;
  - the Overview reading only after its own figures.

## Live check, 2026-11-04

A local server on this branch, the real feeds (Yahoo, SEC EDGAR, the House archive), AAPL:
- **Built from cold in 2.6 s** (a script on this branch):
  - 81 events in 90 days: 11 news, 2 earnings, 23 insider, 14 congressional, 29 analyst and 2 filings;
  - 230 in a year;
  - all six sources answered.
- **The request order:** `/api/timeline` went out after `/api/ticker` answered.
- **The entries:**
  - the scheduled report on top: "Scheduled, not yet reported. The date is an estimate, not confirmed by the company";
  - "Reported quarterly results for Q4 FY26";
  - "Sale of 2,399 shares by NEWSTEAD JENNIFER, Officer", Transaction date;
  - "Hon. Pete Sessions disclosed a sale of $250,001 to $500,000", Disclosed Oct 27 with the trade date and the 45 days.
- **Coverage said:**
  - "The headline feed holds its latest 11 stories about the company, which reach back to Nov 4, 2026";
  - over a year, "Optic reads the House's filings for 2026 only".
- **The controls:**
  - the Congress filter showed its 14 and kept focus;
  - Details opened the definitions and the Earnings tab link;
  - "Show 31 older" appended the rest and moved focus to the first new one.
- **The link targets:**
  - `#/AAPL/financials?section=fin-ownership` landed on Insider and institutional activity with focus on its heading;
  - `#/analysts?symbol=AAPL` opened AAPL's year of actions.
- **Phone:**
  - at 390 and 375 by 549: one column, filters wrapping, 44 px targets;
  - nothing sideways.

## Decisions for review

1. **The section is on the Overview, in both views,** below the analysis. The Dossier's tabs are navigation and stay as they are; a new tab would need the owner's yes.
2. **Congressional trades are placed on the day they were disclosed,** with the trade date in the delay note, as the handoff's note reads ("disclosed DATE; trade occurred on/around DATE"). Insider trades are placed on their transaction date because Yahoo's list carries no filing date; the note says it became public up to two business days later.
3. **Yahoo's earnings and analyst entries link the Yahoo pages Optic already cites** (the earnings calendar and the analysis page), since the feed gives no link of its own. Their Dossier links are in the details.
4. **Market-context headlines are left to the News tab.** Only stories about the company are events.
5. **The provider gained a failure recorder** rather than changing what its methods return. Every existing caller is unchanged.
6. **The design checklist forbids `IntersectionObserver`,** so the section reads after `/api/ticker` rather than when scrolled near.

## Found along the way

1. **The Financials redraw lost focus** after a jump (its own jump list too). Fixed here in passing: a jumped-to heading keeps focus while later figures redraw.
2. **The House archive covers the current year only.** Not changed: older years would need a backfill. The timeline says it as a coverage note.
3. **Yahoo's insider rows with no description** (on Oct 1, 2026, four officers' rows of 99,878 shares each) say "The feed does not say what kind of transaction this is; the filing does", with a link to the company's Form 4 list. The filing itself would name it.
