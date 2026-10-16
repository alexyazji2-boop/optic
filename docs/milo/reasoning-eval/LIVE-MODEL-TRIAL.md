# Sonnet 5 against Sonnet 5.5 on the live site (2026-10-16)

The owner asked to move Milo to Sonnet 5.5 if it gives better answers, and to test it on the live site.
For one afternoon an admin-only flag (d3748ab, removed again with the switch) let the owner's account ask
one answer of `claude-sonnet-5-5` while every other reader stayed on `claude-sonnet-5`. The same 14
questions were then asked of both through the owner's signed-in browser, 12:54 to 13:08 ET, production code
at d3748ab, neutral persona, the Home page's context, no web search. Which model went first alternated per
question. The answers are not stored in this repository, because six of the questions are about the
owner's own accounts; the notes below are the record.

Each pair was read against Optic's own figures taken in the same minutes (the owner's workspace overview and
look-through, window returns from daily closes, the quotes): a factual error counts heavily, then
completeness and how well limits are stated. This is one reviewer's judgement with the figures beside it,
not a blinded panel, and one run per model.

| # | Question | Better | The difference |
|---|---|---|---|
| 1 | Portfolio review and where to diversify | Sonnet 5 | 5.5 said fund look-through does not exist and misread effective holdings; 5 misread the sync time but made fewer errors |
| 2 | The owner's "no energy" correction | Sonnet 5.5 | Both kept the classification; 5.5 explained the business's power-demand exposure, 5 repeated "close to GICS" |
| 3 | Percent in tech | Even | Both gave both denominators; each had one wrong claim (5: effective holdings; 5.5: no look-through) |
| 4 | Sell tech, buy healthcare? | Sonnet 5.5 | Both used the look-through and left the decision with the owner; 5.5 split healthcare from biotech |
| 5 | NVDA once funds are counted | Sonnet 5 | Same correct total; 5.5 called a share of long value a share of the whole account |
| 6 | Upcoming earnings | Sonnet 5.5 | Both mis-added the weights (61.5% and 61.8% for 62.8%); 5 also misstated one weight |
| 7 | Why did my portfolio fall today | Sonnet 5.5 | Same measured figures; 5.5 added the expiring option's position against its strike and the stale broker prices |
| 8 | Is the VIX cheap | Sonnet 5.5 | Neither compared with realised volatility (not in production's tools); 5.5's caveats were correct, including VIX settlement |
| 9 | Healthcare against the Nasdaq | Sonnet 5.5 | 5.5 fetched betas and volatilities and said correlation was unmeasured; 5 argued from mechanism |
| 10 | Below the gamma flip | Even | Both had the dealer assumption the right way round |
| 11 | MSFT over 3 months | Even | Both wrong (truth +31.1%): 5 said about 10%, 5.5 used a June anchor (no window-return tool in production) |
| 12 | AAPL gamma, trend, 3 months | Sonnet 5.5 | 5 said today's expiry rolls off a read that excludes it, and anchored on April; 5.5 named the expiries covered |
| 13 | AMD flow, walls, gamma | Sonnet 5.5 | Same figures; 5 made the same expiry error more explicitly |
| 14 | MSFT on EV/EBITDA | Sonnet 5.5 | Same arithmetic (20.3x); 5.5 added that EBITDA flatters a company with capex growing 80% a year |

**Result: Sonnet 5.5 better on 9, Sonnet 5 on 2, even on 3.** Total answer time 182 s against 256 s (5.5
faster on 11 of 14), output length about the same, same list price ($2 / $10 per million tokens).

What the trial also showed: errors both models made under production's code (no look-through by default,
no window returns, expiry scope, mis-added sums) are the ones the milo-reasoning branch fixes in the data and
tools, so the model switch and that branch address different things.
