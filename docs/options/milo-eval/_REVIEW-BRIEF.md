# Reviewer brief: blinded Options-tab Milo answers

You are an expert options reviewer (market-maker-level knowledge of pricing, greeks, liquidity, and what option
chain data can and cannot show) with a sense for what a nervous beginner needs. Read only this brief and
`<workdir>/milo-eval/review2/pairs.md`. Each case: a question asked on the
AAPL Options tab, the reader's knowledge setting, what a good answer must do, and two answers A and B from two
versions of the same assistant. Do not try to infer which is which; do not open any other file.

## The two versions received different data
One version had the contract table and position builder on screen, the corrected volatility figures and the rate;
the other had only the older options panels (GEX, flow, an entry plan, strategy ideas). "I can't see the position"
can be an honest statement. Score its cost as usefulness (Evidence, Relevance), not Accuracy. Anything invented,
or recalled "from memory" and presented as data, is an accuracy and evidence problem.

## Facts (saved Friday-close chain, AAPL spot $336.64; question asked overnight, market closed)
- Rate 4.05% (13-week bill). IV30 27.1%. No IV rank (no history yet). ATM IV: Oct-16 31.2%, Oct-30 24.4%,
  Nov-13 27.3%, Dec-18 25.3%. Straddle moves: Oct-16 +/-2.5% (1-SD 3.1%), Oct-30 4.4% (5.4%), Nov-13 6.4% (8.0%),
  Dec-18 8.6% (10.8%). Report on Nov 2, inside the Nov-13 expiry; event move priced ~3.8%.
- 25-delta skew at Nov-13: puts ~2.3-2.5 vol points richer than calls.
- Nov-13 340 call: bid 9.50 / ask 9.75, delta 0.48, breakeven at ask 349.75 (+3.9%), decay -$18.47/day per
  contract, vega $39.44/pt, model chance ITM (N(d2)) 45%, OI 168, liquidity "Fair". Nov-13 350 call: 5.40 / 5.80,
  delta 0.34, breakeven 355.80 (+5.7%), decay -$16.22, vega $36.13, N(d2) 31%, OI 263, "Fair".
- Bull call spread on screen (Q1, Q5): buy Nov-13 340 call / sell 355 call. Mid $547.50 debit, natural (ask/bid)
  $580.00, with slippage and fees $556.92; legs' combined spread $65; max profit $952.50; max loss $547.50;
  breakeven $345.48; delta +21 shares, theta -$3.96/day, vega +$6.64/pt. Model P/L now at -5% price and +10 vol
  points: about -$201 (sticky-strike Black-Scholes estimate).
- Iron condor on screen (Q3): Nov-13 long 300P / short 315P / short 360C / long 375C. Credit $399.50 at mid,
  $347 natural; max profit $399.50, max loss $1,100.50; breakevens $311 and $364; vega -$24.30/pt, theta +$10.30/day;
  legs' spreads 9-20% of mid; report inside the expiry.
- GEX: net +$724M per 1% (positive), largest call-side strike 340; under the model's assumption (dealers long
  customer-sold calls, short customer-bought puts), which research finds weaker for single stocks.
- Options figures are model estimates; quotes delayed; the market is closed so quotes are Friday's.

## Score each answer 1-5 on
Accuracy, Evidence, Clarity, Relevance, Adaptation (to the setting and the question), Risk & honesty. Note check
coverage (e.g. 3/4).

## Output
Write `<workdir>/milo-eval/review2/scores.md`: a table (case | A scores as
Acc/Evd/Clr/Rel/Adp/Risk | A checks | B scores | B checks | better A/B/tie | one-line reason), using whole numbers,
then for each case any factual or reasoning error quoted (under 25 words) with why it is wrong. Reply "done".
