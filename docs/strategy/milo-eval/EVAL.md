# Milo evaluation, strategy pass (2026-10-12/13)

## What was measured, and how

- **21 cases** (`cases.py`): beginners (B1-B3), day traders (D1-D2), swing traders (S1-S2), long-term
  investors (L1-L2), advanced researchers (A1-A2), options misconceptions (O1-O2), ambiguous requests (X1-X2),
  conflicting signals (C1), stale data (T1), follow-ups including a ticker switch (F1-F2), a paper portfolio
  (P1) and a market question (M1). Each case lists what a good answer must do.
- **Data flow, no model call** (`capture.py`): the real `stream_chat` assembly runs with the model client
  replaced by a recorder, on saved API responses for AAPL and NVDA captured 2026-10-13 ~00:00 ET (overnight
  session). It records the level, horizon and humour decisions, what reached the model, and its size.
  "before" = origin/main d7528d0; "after" = branch `strategy-pass`.
- **Answers**: a stand-in model (Claude Sonnet, the same family as Milo's production model but not the same
  call path) wrote each reply from the exact captured system prompt and messages. **No production API call
  was made** and no credit was spent; a live run on this set is in the roadmap.
- **Blinded review** (`blind.py`, `_REVIEW-BRIEF*.md`): a separate Opus reviewer scored randomised A/B pairs
  on accuracy, evidence, clarity, relevance, adaptation and risk (1-5) plus check coverage, with a fact sheet.
  Keys and full scores are in `reviews/`.

## 1. Data flow (deterministic)

See `dataflow.md` for every case. Summary:

| | Before | After |
|---|---|---|
| Requests cut mid-JSON at 90,000 chars | 21 of 21 | 0 |
| Reader's watchlist / digest reached the model | 0 of 21 | 21 of 21 (where present) |
| Paper holdings + portfolio summary reached the portfolio question | no | yes |
| Valuation history on an Overview question | only if Investing had been opened | yes |
| Beginner questions put in the Advanced register by page data | 5 (B1, B3, X1, X2, F1) | 0 |
| Humour block suppressed by page data | 20 of 21 | 0 (it rides about one reply in two) |
| Market session stated to the model | never | always |
| Est. input tokens per message (chars / 3.6) | ~31,400 | ~23,900 (about 24% fewer) |

## 2. Answer quality, three rounds

| Round | Change tested | Head to head (new / old / tie) | Checks met (new vs old, of 74) | Mean scores, new vs old |
|---|---|---|---|---|
| 1 | Data-flow fixes + new reasoning standards | 12 / 7 / 2 | 72 vs 62 | higher on 5 of 6; clarity flat (3.95 vs 3.90) |
| 2 | + a strict length rule, no internal labels | 8 / 12 / 1 | 66 vs 65 | higher on 5 of 6, risk equal |
| 3 | Length rule rebalanced; catalyst direction; no "CONTEXT" in horizon prompts | 8 / 7 / 6 | 65 vs 61 | higher on 5 of 6 (accuracy 4.57 vs 4.48, evidence 4.67 vs 4.38, clarity 4.52 vs 4.05, relevance 4.76 vs 4.52, adaptation 4.71 vs 4.57); risk 4.48 vs 4.62 |

Round 1's reviewer scored "that figure did not reach me" as a factual error, which penalised the old version
for an honest statement; rounds 2-3 were told the versions received different data and to score the cost as
lower usefulness instead. Scores are not comparable across rounds, only within one.

**What held in every round:** the new version wins the cases where the old one never received the data:
B1/B2 (P/E against its own history for a beginner), L1/L2 (ten-year question; the conviction-vs-valuation
reconciliation), F1 (horizon switch in a follow-up), P1 (portfolio concentration), X1 (asks the timeframe
instead of claiming a base rate).

**What did not settle:** day-trade, swing, options and advanced cases swung between rounds (D1, D2, S1, S2,
A2, O1, O2). With one reviewer and 21 cases, those differences are within noise. Round 2 showed a strict word
cap costs content on these (spreads, stronger-evidence lists); round 3 restored full reads for plans and
evidence questions, which turned most of those into ties.

**Measured side effects fixed along the way:** round 1's prompt made Milo say "CONTEXT" to the reader in 11
of 21 answers (old: 1) and run 22% longer (8,833 vs 7,264 words); round 3: 0 leaks, 5,880 words. Round 2's
catalyst note made two answers say a headline tag raised the short-term score (it lowers the chart's weight);
the note now states the direction.

**Added after round 3, not re-evaluated:** "Shortening never drops the main thing that argues against the read
or the condition that would change it", aimed at round 3's slightly lower risk score.

## 3. Reasoning errors the review caught (both versions)

- Recalling a valuation history "from memory" when the data did not include it (old version, B1/B2/L1).
- "The base rate favours continuation" with no base rate in the data (old X1).
- Dealer-gamma model output stated as behaviour ("rallies into the wall stall") without the assumption.
- Expiry labels: calling Nov 13 the monthly (Nov 20 is); placing the October monthly on Oct 14.
- Data age misread (238/256 minutes for 231) and "+23.5 out of 100" mixing the composite's +/-100 scale with
  the 0-100 Optic Score; the prompt now states the mapping.
- Passing on a catalyst adjustment triggered by a Q3-recap headline: an Optic method issue (the long-term score
  adds 12 points for it), listed in the roadmap.

## 4. Limits

- Stand-in model, not production calls; one reviewer model; 21 cases; AAPL and NVDA only; one overnight
  snapshot. A live run with the production model needs the owner's approval to spend (~$3-5).
- One stand-in saw a case's checks inside its request file (B1, round 1); `capture.py` no longer writes them.
- Latency was not measured (no model calls). Cost is estimated from characters, not from the API ledger.
