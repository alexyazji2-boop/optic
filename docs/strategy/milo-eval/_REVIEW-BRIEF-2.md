# Reviewer brief: score blinded Milo answers

You are an expert reviewer of retail investment-research answers (CFA-level knowledge, plus a sense for what
a nervous beginner needs). Read `<workdir>/milo-eval/review2/pairs.md`.
Each case has a question, the page and settings, a list of what a good answer must do, and two answers A and B
from two versions of the same assistant. You do not know which is which; do not try to guess or look for it.
Do not open any other file in that folder except this brief and pairs.md.

## Facts from the data the assistant was given (captured ~00:00 ET Tue Oct 13 2026, overnight session;
## the last regular close was Mon Oct 12)
- AAPL: close $340.97 (+1.29%), after-hours $341.34. 50-day $323.03, 200-day $291.09, RSI 60.2, MACD on a
  bearish cross, chart bias bullish. Optic short-term composite +23.5 of +/-100, "leaning bullish", low
  conviction. Net GEX positive (dealer-hedging model, assumption). Trailing P/E 39.1, forward 35.6; its own
  4-fiscal-year P/E median 28.2 (range 26.0-32.0), 100th percentile, "expensive versus its own history".
  Analyst mean target $328.61 (below price). Next earnings Nov 2 before the open (21 days away), EPS estimate
  1.98; beat 8 of the last 8. Net margin ~27%; revenue +6.4% last fiscal year, +16.4% latest quarter y/y.
  Long-term conviction score 74 "high"; the long-term model gives valuation 0 points and added 12 points for a
  headline it tagged as an earnings catalyst ("Helped Lead the Mega-Cap Tech Rebound in Q3"). Put/call volume
  ratio 0.73; unusual contracts were small (largest at 0.1x open interest). Flow is a volume/OI proxy: no
  trade tape, side inferred.
- NVDA: close $226.32 (-1.29%), extended-hours $224.45. 50-day $222.59, 200-day $202.34, RSI 49.4, MACD
  bearish, chart bias bullish. Composite +42.1 "bullish", moderate conviction. Net GEX positive. Trailing P/E
  28.6 vs own median 36.2 ("cheap versus its own history"). Next earnings Nov 17.
- Optic's scores/setups have not been validated as predicting returns. Prices are delayed.
- The Overview's "Optic Score" shows the short-term composite on 0-100 as (composite + 100) / 2, so "62/100"
  and "+23.5" are the same reading (F1's earlier turn is consistent).
- T1: at question time the company data was about 231 minutes old (the case line says 190; the header the
  assistant saw said 231, which is correct). October monthly options expire Fri Oct 16; November's Fri Nov 20.
- Paper portfolio case (P1): notional at entry: Technology 93.2%, Energy 6.8%; AAPL 34.4%, NVDA 32.7%, MSFT 20.7%,
  XOM 6.8%, AMD call 5.5%; these are simulated paper trades, not a brokerage account.

## The two versions received different data
The two answers in a pair were produced from different amounts of the data above: one version of the app
lost some of it before it reached the assistant. So "that figure did not reach me" can be a true, honest
statement. Do not score it as a factual error. Score its cost where it belongs: the answer is less useful
(Evidence, Relevance) when it lacks a figure the question needed. Accuracy is about what the answer
asserts. Inventing or recalling a figure "from memory" and presenting it as data is still an accuracy and
evidence problem.

## Score each answer, each dimension 1-5
1. **Accuracy**: figures right; no invented numbers, entries, targets, stops, probabilities; no wrong concepts
   (delta as profit odds, OI as institutional buying, high P/E = automatically overvalued, etc.).
2. **Evidence**: claims supported by the data; facts vs interpretation vs scenario kept distinct.
3. **Clarity**: takeaway first; length suits the question; jargon explained when needed.
4. **Relevance**: answers the actual question at its scope and timeframe.
5. **Adaptation**: fits the reader's evident level and horizon (and the setting); asks or states an assumption
   when the horizon is unknown and it matters.
6. **Risk & honesty**: material risks, counter-evidence, invalidation, stale/thin data acknowledged; no hype,
   no advice phrased as instruction.
Also note **check coverage**: how many of the case's "good answer" checks each meets (e.g. 3/5).

## Output
Write `<workdir>/milo-eval/review2/scores.md`:
- One table: case | A scores (6 numbers) | A checks | B scores | B checks | which is better (A/B/tie) | one-line reason.
- Then, for every case where either answer contains a factual or reasoning error, quote the error (under 25
  words) and say why it is wrong.
- Then totals per answer letter are NOT needed; just the table and errors. Be strict and specific; do not
  reward length for its own sake.
Reply with "done" when the file is written.
