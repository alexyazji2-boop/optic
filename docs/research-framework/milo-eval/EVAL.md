# Milo with the research framework: evaluation (2026-10-14)

Seven questions, one per framework mode plus a short question and a
loss-making company (`cases.py`). For each, the exact Milo request was built
with no model call (`capture.py`) from two worktrees: `before` (origin/main
be19feb) and `after` (research-framework at the time of capture). Both saw the
same page data; the after version's server also added the `framework`
assessment and the block for the question's mode. Stand-in answers were written
by Sonnet agents following each request's system prompt exactly
(`STANDIN-BRIEF.md`), paired at random as A and B (`blind.py`, key in
`review/key.json`), and scored blind by a reviewer who saw only a brief of
facts and the pairs. These are stand-in answers, not production calls.

| Round | After won | "Must" checks met (after / before) | Mean scores, after vs before |
|---|---|---|---|
| 1 (`review/`) | 7 of 7 | 36 / 22 of 38 | Evidence 4.86 vs 3.29, Reasoning 4.71 vs 3.43, Separation 5.00 vs 4.00 |
| 2 (`review2/`) | 7 of 7 | 36 / 22 of 38 | Accuracy 4.43 vs 3.57, Evidence 4.86 vs 3.29, Reasoning 4.86 vs 3.29, Relevance 4.57 vs 4.00, Separation 5.00 vs 3.86, Risk 4.14 vs 4.00 |

Round 1's brief had two errors, both against the after version: it said no
earnings date reached either swing read (the after version's had 30 October,
confirmed), and it asserted NVDA's net cash. The second turned out to be a real
bug in the filings reader (NVDA's current marketable securities moved to the
`DebtSecuritiesCurrent` tag, so $34bn read as zero), fixed on the valuation
branch as ffc2c03. Round 2 used a corrected brief (`_REVIEW-BRIEF2.md`).

Errors both versions shared, from the reviewer:
- XOM's RSI quoted at about 75 (it includes today's unfinished session; about
  71.5 on completed bars) without saying so.
- JPM called a miss against $5.94 with no mention of the feed's other figure,
  $5.715. By the time of capture the calendar had moved to the next quarter, so
  the framework's two-consensus check could not see it.
