# Milo before and after: research retrieval and the Optic Desk (2026-10-13)

Seven questions, one per kind the brief names plus two about the Desk, asked after the close on Tuesday
13 October 2026 (CPI and Bank of America's results the next morning). `cases.py` lists them with what a good
answer must do.

| ID | Question | Kind |
|---|---|---|
| Q1 | Is Micron a good long-term investment at today's price? | long-term |
| Q2 | What should I watch in Bank of America's earnings tomorrow? | pre-earnings |
| Q3 | Is NVDA worth day trading tomorrow, and what matters intraday? | day trade |
| Q4 | Does a swing long in AAPL make sense over the next few weeks? | swing |
| Q5 | What does tomorrow's CPI mean for my tech stocks? (beginner) | macro |
| Q6 | Is the Desk right that recent softness has sat in the biggest names? | Desk section |
| Q7 | Why won't the Desk say whether JPMorgan beat? Did it? (beginner) | Desk section |

**Method.** `capture.py` builds each exact request with no model call, from the same browser-side context (the
open tab's snapshot, focus and view) through each version's own server path: before = tag
`desk-baseline-2026-10-13`; after = branch `desk-newsletter`. A stand-in model (Claude Sonnet, the production chat
model's family) answered from the exact system prompt and messages; a separate reviewer (Claude Opus) scored
blinded pairs against the case checks and a fact sheet (`_REVIEW-BRIEF.md`). No production API call was made.

## Results

| | Round 1 | Round 2 |
|---|---|---|
| New version better | 6 of 7 (lost Q5) | 7 of 7 |

Round 2 averages, before → after (1 to 5): Accuracy 4.29 → 4.57, Evidence 3.14 → 5.00, Reasoning 3.57 → 4.43,
Relevance 3.86 → 5.00, Adaptation 4.00 → 4.71, Risk and honesty 4.71 → 5.00.

## What round 1 found, and what changed (commit e307e27)

- **Q5 lost** on a stale figure: the macro pack gave Milo FRED's 10-year yield (dated 9 October, a day or more
  behind) and no market quote. The pack now leads with market quotes (yields in bp, the dollar, oil, the VIX, SPY,
  QQQ) with timestamps, and labels FRED's daily yields as lagging. Round 2 won Q5 on exactly that.
- **Q2's consensus never reached the model**: research steps run in parallel and were kept in completion order,
  so the context budget's 14,000-character section cap cut the consensus off the end. Items now merge in the
  plan's order (expectations first for an earnings question) and the research section gets 26,000 characters.
- **Yahoo's throttling (HTTP 401) returned empty answers silently**; an empty earnings feed is now named in
  `research.missing`, and the prompt says to report what failed.
- **Desk questions lacked the figures behind a claim** (the equal-weight and cap-weight five-session changes);
  cited evidence now carries its underlying numbers.
- A routing bug: "a good long-term investment at today's price" went to intraday retrieval because "today"
  counted as day trading. Fixed in 34402e6.

## Remaining errors the reviewer found in the after answers (round 2)

- Q1: an operating-vs-net margin left unlabelled; two figures without a source tag.
- Q2: an expiry-wide straddle (eight sessions including CPI) not flagged as covering more than the report:
  the prompt now says so (this commit).
- Q4: a 50-day SMA and EMA quoted without saying which.
- Q5: "the Fed's 2% aim" set against CPI, when the target is defined on PCE.

## Representative answers (after, round 2)

- Q1: "Strong business, unresolved price ... fiscal 2025 capex was $15.86bn, 42.4% of revenue, leaving free cash
  flow of only $1.67bn."
- Q6: "Partly. The direction checks out, but 'softness' is a strong word for what the numbers show ... RSP gained
  0.46% while SPY fell 0.14%, a gap of 0.6 percentage points."
- Q7: explains that $5.75 is a beat against $5.715 and a miss against $5.94, and why the Desk will not call it.

Full answers in `answers/before`, `answers/after` (round 1) and `answers/after2` (round 2); scores and the
unblinding key alongside.
