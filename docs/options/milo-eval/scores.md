# Scores: blinded Options-tab Milo answers (review2)

Scores are Acc/Evd/Clr/Rel/Adp/Risk, 1-5.

| Case | A scores | A checks | B scores | B checks | Better | Reason |
|---|---|---|---|---|---|---|
| Q1 (beginner) | 3/3/4/2/3/4 | 3/4 | 5/5/4/4/3/4 | 4/4 | B | B uses the on-screen 340/355 spread with the correct $547.50 mid, $580 natural and $65 leg cost; A analyses the 335/355 strategy idea but calls it "the spread on this page". |
| Q2 (swing) | 5/5/4/5/4/4 | 3/4 | 3/3/3/3/3/4 | 2/4 | A | A gives correct quotes, breakevens, decay, liquidity and the report timing for both Nov-13 strikes, but leaves out vega. B moves to Oct-30, works out costs from flow averages, has no decay or vega, and uses an old GEX figure. |
| Q3 (literate) | 5/5/4/5/5/5 | 6/6 | 3/3/3/2/2/3 | 2/6 | A | A covers the on-screen iron condor fully: report inside expiry, short strikes near the straddle, natural $347 vs mid, negative vega, assignment, max loss vs margin. B analyses the long-call ideas instead and drifts into the verdict score. |
| Q4 (beginner) | 5/5/5/5/5/5 | 4/4 | 3/4/4/5/4/4 | 2/4 | A | A is plain and short, with the correct $724M net and 319.33 flip, the assumption caveat and the single-stock caveat. B has old figures, gives the flip to four decimals for a beginner, skips the single-stock caveat and says rallies "tend to stall". |
| Q5 (advanced) | 5/5/5/5/5/5 | 4/4 | 4/3/3/3/4/4 | 2/4 | A | A quotes the grid (-$200.86 now), works out the vega cushion correctly, gives the spread's delta and vega and labels the fixed-IV model. B can't see the spread, so it works through the 340 call with older greeks and its own Black-Scholes (disclosed, and checks out near 6.8). |
| Q6 (literate) | 4/5/4/5/4/5 | 3/4 | 2/3/3/4/3/4 | 2/4 | A | A gives IV30 27.09%, says there is no IV rank, notes the ~3.8% event move and does not say should. B has no IV30, gets the skew direction backwards against the put skew, says realised vol is contracting, and runs long. |
| Q7 (day) | 5/5/5/5/5/5 | 3/3 | 3/4/4/5/4/4 | 3/3 | A | A's straddle 2.46%, 1-SD 3.08%, range and IV 31.2% all match the data, with cost-not-limit and Friday-snapshot caveats. B's IV-based 1-SD of 2.2% comes from wrong IVs and is smaller than the straddle. |

## Errors by case

### Q1
- A: "The spread on this page buys the Nov 13 $335 call and sells the $355 call" - the on-screen spread is the 340/355 ($547.50 mid, $580 natural). A has analysed the strategy-ideas spread and presents it as the user's.
- B: no factual errors found. It never states outright that a mid is an estimate, not a fill; that only comes through in "the prices you can actually trade at".

### Q2
- A: no factual errors found. The check asks for vega on each strike, and A gives none.
- B: "With net GEX at +$797.053m per 1%" - the current figure is +$724M; this is a stale value presented as current.
- B: "dealer hedging leans against rallies into it" - this treats the call wall as resistance on the strength of a dealer-positioning assumption that is weak for single stocks.
- B: changes the question to Oct-30 contracts and reports "no bid or ask", so it cannot give decay, vega or spread cost for the contracts on screen.

### Q3
- A: no factual errors found. It names assignment but not pin risk at expiry.
- B: "I'm assuming you mean the long call and bull call spread ideas" - the position on screen is an iron condor. Short strikes, negative vega and margin all go unaddressed.
- B: "Apple has beaten 8 of 8 quarters, so a beat is the base case" - a beat history says nothing about the size or direction of the price reaction, which is the actual risk.
- B: "The Nov 13 340 call loses 0.1719 a day" - the current decay is -$18.47/day per contract (0.1847/share); this is a stale figure.

### Q4
- B: "Under the model, rallies into it tend to stall" - this presents the wall as resistance; the brief requires no support/resistance claim.
- B: "+$797.053m per 1% move" / "flip point is 323.8945" - these differ from the current +$724M and 319.33. The four-decimal precision also does not suit a beginner.
- B: leaves out the caveat that the dealer-sign assumption is weaker for single stocks.

### Q5
- B: "I'm assuming 'this position' is the Nov 13 340 call" - the position is the 340/355 bull call spread. The grid figure (about -$201) is missing.
- B: "delta 0.465" and "flip point 323.89" - these differ from the current 0.48 delta and 319.33 flip; they are stale inputs.
- B: "+10 points ... is large without an event" - the Nov-2 report falls inside the Nov-13 expiry, so there is an event in the window.

### Q6
- A: "no expiry stands out as richest apart from the event" - this ignores Oct-16 at 31.2% ATM IV, which is clearly the richest expiry. A cites that figure itself in Q7.
- B: "Realized vol is contracting" - 10-day realised (19.5%) is above 20-day (16.5%), so recent realised vol is rising, not contracting.
- B: "OTM call IV (25.33%) sits above OTM put IV (23.98%)" - this contradicts the chain's skew: Nov-13 25-delta puts are about 2.3-2.5 points richer than calls.
- B: "At-the-money IVs run 24.1% to 25.3% on the Oct 16 expiry" - the Oct-16 ATM IV is 31.2%.
- B: "which is the setting Optic's regime note says favours premium selling" - this leans toward a recommendation, against the no-should requirement.

### Q7
- B: "printed IVs of 24.11% and 25.33% average 24.72% ... 2.2%, about $7.5 for one standard deviation" - Oct-16 ATM IV is 31.2%, which gives a 1-SD of about 3.1%. A 1-SD also cannot be smaller than the straddle (the straddle is roughly 0.8 x 1-SD), so the "2.2% to 2.5%" range understates the move.
- A: no factual errors found.
