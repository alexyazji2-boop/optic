# Milo on the Options tab: before and after (2026-10-13)

Seven questions on AAPL's Options tab (`cases.py`), asked against the same saved Friday 2026-10-09 close chain:

| ID | Reader | Question |
|---|---|---|
| Q1 | beginner (Simple) | Explain why this spread is expensive to trade. (bull call spread on screen) |
| Q2 | swing | Compare the 340 and 350 calls for a two-week thesis. |
| Q3 | literate | What risks am I missing? (iron condor on screen) |
| Q4 | beginner | Explain this exposure chart in plain English. |
| Q5 | advanced | How would this position react to a 5% price drop and a 10-point IV increase? |
| Q6 | literate | Is IV high right now? Should I sell premium? |
| Q7 | day trader | What's the expected move by Friday? |

**Before** = branch `strategy-pass` (Milo's reasoning fixes, no options research, old options inputs).
**After** = branch `options-pass`. Each request was built with no model call (`capture.py`); a stand-in model
(Claude Sonnet) answered from the exact system prompt and messages; a separate reviewer (Claude Opus) scored
blinded pairs against the case checks and a fact sheet (`_REVIEW-BRIEF.md`; `scores.md`, `key.json`). No production
API call was made.

A first round was discarded: the fixture server gave the old code every contract's days-to-expiry as 0 (the new
code recomputes them, the old code reads the provider's), which distorted the baseline's greeks. The fixture server
now reproduces the old provider's clock exactly, and both sides were regenerated.

## Result

| | Before | After |
|---|---|---|
| Head to head | 0 | 7 of 7 |
| Checks met | 16 of 29 | 27 of 29 |
| Accuracy / Evidence / Clarity | 3.00 / 3.29 / 3.43 | 4.86 / 5.00 / 4.43 |
| Relevance / Adaptation / Risk & honesty | 3.43 / 3.29 / 3.86 | 4.86 / 4.43 / 4.71 |

## What made the difference (from the reviewer's error list)

- **The reader's position reached the model.** Before, Milo could not see the spread or condor on screen and analysed
  the strategy-ideas cards or a single call instead (Q1, Q3, Q5). After, it priced the actual legs: $547.50 mid vs $580
  natural, the -$200.85 scenario at -5% / +10 points, the condor's $1,100.50 max loss.
- **The zero-rate artefact.** Before, Q6 said out-of-the-money calls were priced above puts (25.3% vs 24.0%): the
  put-call parity effect of r = 0. After, the 25-delta skew shows puts richer, as the corrected surface does.
- **The old GEX advice leaked into answers.** Before, Q6 cited "the setting Optic's regime note says favours premium
  selling"; the note no longer says that.
- **Expected move.** Before, Q7 gave a 1-SD move smaller than the straddle (inconsistent IVs across strikes); after,
  2.46% straddle and 3.08% 1-SD, with "what options cost, not limits".
- **Old figures.** Before used net GEX $797M (r = 0) and a flip at 323.89; after $724M and 319.33 at the bill rate.

## Remaining gaps the reviewer found in the after answers

- Q2: no vega for either strike. Q3: assignment covered, pin risk not named (no short strike was within 1% of the
  price, so the builder raised no pin flag). Q6: did not single out the Oct-16 expiry as the richest.

## Representative answers (after)

- Q1: "Buying at the asking price and selling at the bidding price (the natural price) costs $580.00 ... Optic's more
  realistic fill ... is $556.92. The best case is $952.50, so that gap is a noticeable slice."
- Q5: "-$200.85 now, against -$306.06 with IV flat ... The cushion comes from the spread being net long vega (+$6.64 per
  vol point) ... at expiry IV no longer matters."
- Q6: "Optic can't yet say whether it's high against its own history, and whether to sell premium is your call ... a
  rank appears after 20 more trading days."

Full answers in `answers/before/` and `answers/after/`.
