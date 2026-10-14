# Reviewer brief: blinded Milo answers, research framework

You are an expert reviewer: a buy-side analyst and swing trader who also teaches retail investors. Read only this
brief and `review2/pairs.md`. Each case gives a question, the page, what a good answer must do, and two answers A
and B from two versions of the same assistant. Do not try to infer which is which; do not open any other file.

## What differs between the versions
Both saw the same page data (a technical and options snapshot, news, the research pack of filings and estimates).
One version's server also added a deterministic assessment (business-quality and valuation grades, a swing grade
with a plan, an earnings view) plus instructions for the type of question. "I can't see X" can be an honest
answer: score its cost as usefulness (Evidence, Relevance), not Accuracy. Anything invented, or a figure presented
as data without a source, is an accuracy and evidence problem. Web search was off for both.

## Facts (14 October 2026, about 13:10 ET, regular session, prices delayed about 15 minutes)
- NVDA about $222.3. Fiscal year to January 2026: operating margin 60.4%, five-year margin range about 47 points
  (fiscal 2023 was a downturn year), diluted share count roughly flat after adjusting for the June 2024 10-for-1
  split. Balance sheet at 26 July 2026: cash $22.4bn plus $34.1bn of current marketable debt securities against
  $33.4bn of long-term debt, so about $23bn of net cash. P/E low in its own five-year range. Next report 17 November.
- XOM $177.0, daily ATR about $3.46, 52-week high $176.41, a resistance level near $175.65, strong relative
  strength against the S&P 500 over three months. RSI about 71.5 on completed daily bars to 13 October, about 75
  including today's unfinished session. Exxon reports 30 October 2026 (confirmed in the feed), inside a two- to
  three-week swing window.
- AAPL about $343.6. Next release 2 November 2026 before the open per the feed (confirmed there), consensus EPS
  about $1.98, revenue about $113.6bn; the straddle to the 6 November expiry prices about 5.5% (that spans more than
  the release). Apple beat EPS consensus in all of the last eight quarters; the P/E is at the top of its five-year
  range.
- JPM about $333.7. Reported 13 October. EPS $5.75; the free feed has two consensus figures, $5.94 (its surprise
  table) and $5.715 (its calendar), so whether it beat depends on which. The stock gapped up about 1.7% at the open
  on the reaction day and closed about -0.9%. Guidance text and transcripts are not in the data.
- RIVN about $12.90. Operating losses (fiscal 2025 operating margin about -66%), negative free cash flow, cash
  covers roughly two years of last year's burn, diluted shares up about 9% a year over three years, stock-based pay
  about 14% of revenue. No P/E (negative earnings).
- None of Optic's grades or scores has been shown to predict returns.

## Score each answer 1-5 on
Accuracy, Evidence (uses the right evidence for the question type and cites it), Reasoning (the chain, the opposing
evidence, what would change the view), Relevance (answers the question asked at the scope asked; a short question
gets a short answer), Separation (keeps business quality, valuation, the trade setup and the earnings reaction
apart where the question touches more than one), Risk & honesty (no invented figures, no instructions, limits said).
Note how many of the "must" checks each answer meets (e.g. 4/6).

## Output
Write `review2/scores.md`: a table (case | A scores as Acc/Evd/Rsn/Rel/Sep/Risk | A checks | B scores | B checks |
better A/B/tie | one-line reason), whole numbers, then for each case any factual or reasoning error quoted (under
25 words) with why it is wrong. Reply "done".
