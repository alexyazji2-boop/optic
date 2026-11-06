# Writing corrections

The library of approved corrections (directive 14 Part 3.3). Each row has the text as it was, as it is now, why,
where it appears, and the rule of `OPTIC_WRITING_STANDARDS.md` it follows. New copy and new prompts are written
against these, not against memory. Nothing here retrains a model: Milo and the writers change only through their
instructions, which section A records.

Phase 12, 2026-11-02, branch `phase-12-writing-milo-security`. Findings came from three sources:
- the deterministic checker, over 18,366 texts;
- a line-by-line read of Home, the Overview, the Milo panel and the server writers;
- an independent copy editor's read of 25 more pages from captures at three levels (43 findings, each checked
  against the code before it was applied).

`{…}` marks a value the code fills in.

## A. Model instructions (Milo and the AI writers)

| Was | Now | Why | Where | Rule |
|---|---|---|---|---|
| Each writer prompt carried its own voice rules ("a market newsletter someone reads because they enjoy it", four times) | One block, `app/editorial.py WRITING_RULES`, appended to every model request before the advice policy | One set of rules cannot drift; the policy still reads last | every model request | 7 |
| "* A short **What could go wrong** or **What argues against it** section before the close. * Close with a short **Bottom line** that says what would change the read." | "* Give the main thing that argues against the read its own short paragraph, under a heading only when the answer has others. * End on what would change the read: a level on a closing basis, an event or a figure in the next report. That is the last line of the answer, not a summary of it, and it needs no **Bottom line** label." | A fixed closing heading invites a restatement and gives every long answer the same shape; the risk and the condition stay | Milo, `FORMAT_PROMPT` | 10, 4 |
| "Lead with the takeaway ... then a useful next step when there is one." and, later, "**Lead with the assessment.** Open with a clear answer in a sentence or two. Then the strongest evidence for it, then the strongest evidence against it, then what would change the view." | The second now points to the first ("The order under How to answer holds at every level and length") | The prompt said the same thing twice | Milo, `SYSTEM_PROMPT` | 4 |
| "Ellipses are fine as a pacing device...sparingly." | removed | A chatbot tic in a research brief | deep research, `RESEARCH_PROMPT` | 7 |
| "\"Woohoo! The U.S. labor market isn't doing well. Wait, what?\" is the register ... Ellipses are fine as a pacing device ... Emphatic capitals for the single conditional the week hinges on, used ONCE." | "Open with the most surprising thing the week's figures show, then explain it. A rhetorical question only when the next sentence answers it." | Exclamations, capitals and ellipses read as a template's enthusiasm, not a desk's | the weekly update, `WEEKLY_PROMPT` | 2, house rules |
| "Occasional ellipses for pacing are fine." | removed | as above | the morning note, `MORNING_PROMPT` | 7 |

## B. Home

| Was | Now | Why | Rule |
|---|---|---|---|
| "Search by its name, such as Apple, or by its ticker, the short code it trades under, such as AAPL." | "Search by name, such as Apple, or by ticker, such as AAPL. A ticker is the short code a stock trades under." | Four commas around a nested definition | 3 |
| A hidden description, "Panels with a ticker beside their name show this one", read to a screen reader before the visible hint said the same | The field is described by the visible hint itself | Said twice to one reader | 4 |
| "Traders expect the Federal Reserve's interest rate to {rise} a little over {January 2027}, before the Fed has said anything about it." | "Traders are betting that the Federal Reserve's interest rate will be a little {higher} on average over {January 2027}." | The closing clause is true of every futures price | 2 |
| "The next one is {JOLTS} {tomorrow}, which is what this week is building up to." | "The next one is {JOLTS} {tomorrow}." | A claim no rule checks: the next report is often not the week's main event | 15, 12 |
| "... which shows what big traders were already betting on rather than anything new about the economy" | "It shows how big traders were already positioned, not anything new about the economy." | Shorter, the same meaning | 5 |
| "... so prices are moving on their own." | "... so no scheduled release is moving prices." | Precise | 5 |
| "It comes in about the same: The most common result. Markets then tend to carry on with whatever they were already doing, and early moves often reverse." | "Then the report adds little that is new, and prices tend to follow whatever was moving them before." | A frequency nobody measured, and a contradiction inside one sentence | 15, 11 |
| "... the dollar is flat, but one of the two has barely moved, so together they do not tell a clear story" | "... the dollar is flat, so together they give no clear signal" | The move words already say which one is flat | 4 |
| "With no big news today, moves are mostly traders shuffling their bets, so where prices actually end up matters more than any explanation for them." | "With no big report today, where prices close says more than any move during the day." | A platitude | 9, 10 |
| "The first reaction to news is the least reliable part of the day. The real verdict usually shows up over the next few days." | "The first reaction to a report is the least reliable part of the day; the next few days usually settle what it meant." | Tighter | 5 |
| "No consensus estimates, meaning no economists' predictions. Each report is compared with its own last reading, because those predictions are sold under licence and this site does not carry them." | "No consensus estimates. Economists' forecasts are sold under licence and Optic does not carry them, so each report is compared with its own last reading." | Cause before consequence; "this site" for "Optic" | 3, 14 |

The Desk lines are `app/analytics/morning_desk.py`, the first-visit card and the linked row
`static/v2/js/pages/workspace.js`. Four Home sentences pinned by the beginner brief's tests were left exactly as
they were: the SPY sentence, "it does not buy shares or spend money", "Your open watchlist is empty" and the
linked-panels hint.

## C. The Overview (Simple analysis)

| Was | Now | Why | Rule |
|---|---|---|---|
| "A risk to weigh: optic star rating 1 of 5: above its usual valuation range. Optic's fair-value model places the price above the range it treats as usual for this company. A model estimate, not a verdict." | "A risk to weigh: Optic's star rating is 1 of 5 (above its usual valuation range). The rating compares the price with the range Optic's fair-value model treats as usual for this company. A model estimate, not a verdict." | A name lowercased, two colons in one line, and a reason that repeated the rating | 4, 14 |
| "It reports today." (7:25 PM, after an after-close report) | "Its report was due today." (after 4 PM in New York, at every level) | The sentence outlived the event | 13 |
| (fund) "A {kind} from {State Street}, its holdings at {23.9} times trailing earnings, with a {0.99}% distribution yield." | "A {kind} from {State Street}. Its holdings trade at {23.9} times trailing earnings, and it has a {0.99}% distribution yield." | A verbless list | 3 |
| "Annualised volatility is about {N}%, and it is {3.5}% below its highest close." under an answer that had said "{3.0}% below their highest close" | The second distance is left out when the first answer gave one | Two different figures under the same words | 4, 14 |

Source: `static/v2/js/pages/overview-simple.js`, `overview-research.js`.

## D. The Milo panel

| Was | Now | Why | Rule |
|---|---|---|---|
| "Ask me anything: about the company or the page you have open, about the market as a whole, or about how Optic works something out. I read Optic's own figures for what is on your screen, and look up more of Optic's data when a question needs it." | "Ask about the company or page you have open, the market as a whole, or how Optic calculates a figure. I start from the figures on your screen and look up more of Optic's data when a question needs it." | Five commas; "works something out" | 3, 5 |

The example questions and personas are Classic's, word for word, and stay so (the owner's rule).

## E. Advice in fixed copy

| Was | Now | Where |
|---|---|---|
| "VIX {x}. Complacent tape, trend-following works, hedges are cheap" | "VIX {x}. Low: options are pricing small daily moves" | Macro, `app/analytics/macro.py` |
| "VIX {x}. Normal vol regime" | "VIX {x}. In its normal range" | same |
| "VIX {x}. Elevated; size down and widen stops" | "VIX {x}. Elevated: options are pricing wider daily swings" | same |
| "VIX {x}. Stressed; premium selling favored over directional longs" | "VIX {x}. Stressed: options are pricing large daily swings" | same |
| "VIX {x}. Panic regime; mean-reversion bounces are violent both ways" | "VIX {x}. Panic level: daily swings are very large in both directions" | same |
| "Wide daily ranges, both directions. Sizing matters more than the setup." | "Wide daily ranges, in both directions: the move behind a setup can also reverse it." | Explore, `app/analytics/scanners.py` |
| "Labelled as risk rather than opportunity because that is the honest framing: the setup and the danger are the same property." | "Labelled as risk: the wide range behind the setup is also its danger." | same |
| "Mixed global regime. US and international indices are diverging. Favor the strongest." (and the other two bands) | "{n} of {m} major indices are above their 200-week averages: US and international indices are diverging." | Indices, `app/analytics/longterm.py` |
| "Keep it to a handful of funds" | "A few broad funds already diversify" | Retirement, `app/analytics/retirement.py` |

Rule: the advice policy. Fixed copy may describe a level or a measure, never tell a reader what to do about it.

## F. Templates that broke on real data

| Was | Now | Where |
|---|---|---|
| "AAPL reports on Mon Nov 2, in 0 days" | "AAPL reports today, Mon Nov 2" | Earnings |
| "Reports in 0 days. Inside the event window." | "Reports today. Inside the event window." | `app/analytics/earnings.py` |
| "All 2 days, the Nov 2 report included." | "Over 2 days, including the Nov 2 report." | Options |
| "the typical ±{x}% for 1 sessions" | "the typical ±{x}% over 1 session" | Options |
| "typical for the same 1 sessions" | "typical for the same 1 session" | Dossier |
| "1 buys and 3 sales", "13 buys, 1 sales, 1 members" | plural() on every count | Financials, Insiders |
| "Estimates and reported EPS on the basis analysts use, usually adjusted; it can differ ..." | "Estimates and reported EPS are on the basis analysts use, usually adjusted, so they can differ ..." | Earnings |
| "Its diluted EPS against the average closing price across the year ... four points can show a direction" | "the year's average closing price over its diluted EPS ... {n} points can show a direction" | Investing |
| "Needs revenue growth, net margin, share count change, exit p/e, years ahead." | "Fill in revenue growth, net margin, share count change, exit P/E and years ahead to see this case." | Valuation scenarios |
| "Model dcf-1.0, filings retrieved Nov 3, 2026" (the fold: "Nov 2, 2026, 7:18 PM EST") | A timestamp dated in New York, as the fold is | Valuation, `dcf.js` |
| "Left out: 0 filler, 4 off-topic and 0 site index pages." | "Left out: 4 off-topic." | News |

## G. One thing, one name

| Was | Now | Where |
|---|---|---|
| "Tight: ... Wide: up to 25%. No usable quote: ... or wider than 25%." | "Liquid: ... Thin: up to 25%. Too wide to trade: wider than 25%. No usable quote: one side missing, locked or crossed." | Options, `app/analytics/liquidity.py` |
| "Net debt of $62.7B at the end of FY25" beside a tile reading "Net debt $44.0B" | "Counting cash and equivalents only, net debt was $62.7B at the end of FY25: ..." | Financials, `core/finviz.js` |
| "Optic Portfolio: One shared simulated ledger, no real money" | "Three shared simulated books, no real money" | Settings |
| "these fire on the paper book Optic keeps for its scans" | "these fire on the Optic Portfolio's simulated books" | Alerts |
| "Regular session bars only, at 60m resolution" beside a toolbar reading "1h" | unchanged | (left: pinned by `tests/test_extended_hours.py`'s opening; the interval word is the provider's) |

## H. Said twice

| Was | Now | Where |
|---|---|---|
| "AAPL reports Monday after the close Monday, After close, high impact. An earnings report resets the estimate the price is built on ..." on each of 8 rows | The day and time only when the title does not already say them; a reason every row shares said once, under the list | Read, `pages/read.js` |
| "The market leans cautious (risk-off): The market score's inputs, taken together, lean mildly toward caution." | The stance sentence alone | Macro |
| "Strongest and weakest sector right now: X and Y. the widest gap in the current rotation." | "... X and Y." | Macro |
| "The price rose after 3 of 8 reports and fell after 5; after the 8 beats it fell 6 times." (the fourth telling) | "The price rose after 3 of 8 reports and fell after 5." | Earnings |
| "... written by an AI model when a reader asks, then kept for six hours per report date for everyone." | "... written by an AI model when a reader asks." | Earnings (the empty state says the rest) |
| "Pick a template or press Add in the table." | removed | Options (the empty state below says it) |
| "... kept only if price touched them more than twice. On daily and weekly bars." under "Drawn on daily and weekly bars only." | the second sentence removed | Chart studies |
| "Supply and demand: a narrow base ..." under the label "Supply and demand" | "A narrow base ..." | Chart studies |
| "The line is this symbol divided by SPY, indexed to 100 at the start." under a caption saying the same | the note starts at "Rising means ..." | Financials, relative strength |
| "The ranking is still loading. Each scan fills when it finishes; this page checks every 5 seconds." beside a progress bar | "The ranking is still being built; this page checks every 5 seconds." | Scan |

## I. Claims the data cannot carry

| Was | Now | Where |
|---|---|---|
| "Ahead of the index over both ... Money has been moving here, not just visiting." | "Ahead of the index over both the past week and the past month." | Read, sector board |
| "Behind the index over both windows, which is money leaving rather than a single bad session." | "Behind the index over both the past week and the past month." | same |
| "Broad participation: {n}% of sectors above their 200-day. Breakouts have follow-through." | "Broad participation: {n}% of sectors above their 200-day." | Macro |
| "The average stock is ahead of the index. Broad participation, a healthier advance." | "The average stock is ahead of the index: the advance is broad." | Macro |
| "... Protection is dear against what the tape is doing." | removed | Macro |
| "the equal-weight S&P 500 is keeping up with the cap-weighted index" for any non-negative change | "ahead of" above +2 points, "behind" below -2, else "in line with" | Macro |
| "Growth is leading ... Long-duration, higher-multiple names are in favor, which typically needs falling or stable rates to persist." | "Growth is leading the broad market by {x}% over 3 months." | Indices |
| "Growth is lagging ... often a sign rates or margins are the market's main worry." | "Growth is lagging the broad market by {x}% over 3 months." | Indices |
| "Analysts disagree widely on this quarter. A bigger surprise either way is likely." | "Analysts disagree widely on this quarter, so the result could land far from the average either way." | Earnings |
| "A straddle's price and one standard deviation are what options cost, not limits on the price: a move that size or larger happens about a third of the time." | "... not limits on the price." | Options (a straddle is not one standard deviation, so the third was wrong for it) |
| "Premarket movers, short-squeeze watch and quality screens are deliberately absent: they need ... none of which this terminal has at 700-name scale." | "... are not offered: Optic has no premarket quotes, short interest or fundamentals for every name it screens." | Explore and Scan, beside a count of 2,983 symbols |
| "Extended-hours volume is a fraction of the regular session, so this level is struck by far fewer participants and can retrace once the open provides real liquidity. It is the market's first read, not its settled one." | "Far fewer shares trade outside the regular session, so this price can reverse once the regular session opens." | Earnings |

## J. Empty and error states

| Was | Now | Where |
|---|---|---|
| "The board is not available" (no reason) | "... It did not load this time. Reload the page to try again." | Indices, Markets |
| "Nothing to preview right now." | "No stock matches this right now." | Explore |
| "No alerts yet. A price level, a day's move, an RSI line, a change in Optic's stance or an earnings date." | "No alerts yet. Press New alert to watch a price level, a day's move, an RSI line, a change in Optic's stance or an earnings date." | Alerts |
| "The chart above has a Try again." | "Press Try again on the chart above." | Overview, failed load |

## K. Settings and Retirement

| Was | Now | Why |
|---|---|---|
| "Both themes are hand-picked rather than one flipped into the other, so contrast and colour-vision separation hold either way." | "Both themes are checked for contrast and for colour-vision separation." | Development history in reader copy |
| "Default is 15% larger than the terminal shipped with. Compact is that original density, for a small screen or a reader who wants more on it at once." | "Default is 15% larger than Compact. Compact fits more on a small screen." | as above |
| "New York. Eastern (market time)", "Los Angeles. Pacific" | "New York: Eastern (market time)", "Los Angeles: Pacific" | Punctuation (v2; Classic's copy of the list is flagged) |
| "Reasoning specific to a Roth, as opposed to generic allocation advice." | "Reasoning specific to a Roth account." | It implied the rest of the page was advice |
| "... The comparison above shows how your holdings differ from the example's weights." with no holdings entered | The sentence only when holdings are entered | A comparison that was not there |

## L. The level's definitions (New to Markets)

| Was | Now |
|---|---|
| "No consensus (the average of what analysts forecast) estimates" | The definition goes in only where the phrase ends; inside "consensus estimates" the mark alone explains it |
| "gamma (how fast an option's directional exposure (its delta (how much an option's price moves ...)) changes" | A definition shown inline is never marked again, and its own parentheses become commas: "gamma (how fast an option's directional exposure, its delta, changes as the stock price moves)" |
| "Reported EPS (earnings Per Share)" | "Reported EPS (Earnings Per Share)" |
| "Implied move (how big a move the options market is pricing ...) through Nov 4" | A tile's label keeps its mark without a definition inside it |

Source: `static/v2/js/ui/glossmark.js`. Tests: `tests/test_editorial_standards.py`.

## M. Flagged, not changed

| Finding | Why it was left | Who decides |
|---|---|---|
| Earnings and Retirement print a disclaimer right under a sentence that says the same | Legal notices are not rewritten here | Counsel (BL-02) |
| The brokerage consent: "You choose which accounts count towards your Optic portfolio" | Consent text, versioned (BL-08) | The owner and counsel |
| The glossary's "oversold: a stock has fallen quickly enough that it may be due for a bounce" reads as a forecast | The glossary is Classic's, word for word, and a test holds the two copies together | The owner |
| Classic's own copy: its time zone labels, "the honest framing" (Classic's scan note), and its stock phrases | Classic is left as it is unless the owner asks; the server-written notes above change in both apps | The owner |
| `core/api.js`: "If the data source is refusing requests, it shows here as soon as it answers." | Pinned by `tests/test_contract_picker.py` | The owner, with the test |
| The Optic Portfolio page calls its books accounts, books, ledgers and rule sets | The page is waiting on counsel (BUG-026); a rename is the owner's | The owner |
| `app/paper.py`: "No more than two or three positions may report earnings within the same few days" | The rules text that shipped today; the exact caps are in the code | The owner |
| The Investing page's "trend, strength against the S&P 500 and risk" | Accurate for the model in general; a page without risk rows is the data's state | none |
