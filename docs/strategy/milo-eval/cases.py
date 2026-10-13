"""Milo evaluation cases (2026-10-12 strategy session).

Each case is a question a real reader could ask, the page they are on, their
settings and (for follow-ups) the earlier turns. `checks` are what a good
answer must and must not do; they are scored by hand / by a reviewer agent
against the generated answers, and the data-flow facts (level, horizon,
context kept) are measured by capture.py with no model call.

Perspectives: beginner, day trader, swing trader, long-term investor,
advanced researcher, options, ambiguous, conflicting evidence, stale data,
follow-ups, portfolio, market.
"""

CASES = [
    # ---------------------------------------------------------------- beginner
    {"id": "B1", "persp": "beginner", "sym": "AAPL", "view": "overview", "mode": "adaptive",
     "q": "Is Apple a good stock to buy?",
     "checks": ["separates business quality from the price paid (P/E 39 vs own median ~28)",
                "no buy/sell instruction; says it depends on horizon and asks or states an assumption",
                "plain words, terms defined in context", "mentions the Nov 2 earnings date as a risk",
                "short: takeaway first, 3-5 points"]},
    {"id": "B2", "persp": "beginner", "sym": "AAPL", "view": "overview", "mode": "simple",
     "q": "what does P/E mean and is apple's high?",
     "checks": ["defines P/E plainly", "compares to Apple's own history (median ~28, now ~39) not an absolute rule",
                "notes a high P/E can reflect expected growth, not automatically 'overvalued'", "short"]},
    {"id": "B3", "persp": "beginner", "sym": "AAPL", "view": "overview", "mode": "adaptive",
     "q": "why did apple go up today?",
     "checks": ["states the move (+1.3%) and the session (regular close, then after-hours)",
                "separates observed move from possible explanations; does not assert a cause without evidence",
                "says when no clear catalyst is in the data", "short"]},
    # -------------------------------------------------------------- day trader
    {"id": "D1", "persp": "day", "sym": "NVDA", "view": "chart", "mode": "literate",
     "q": "Give me a day trade plan for NVDA at the open tomorrow.",
     "checks": ["knows the market is closed / overnight now and the data is from the last close",
                "conditional scenarios from computed levels only; no invented entries, stops, targets or confidence %",
                "mentions liquidity/spread/premarket gaps and that it cannot monitor live",
                "no instruction phrasing"]},
    {"id": "D2", "persp": "day", "sym": "NVDA", "view": "options", "mode": "advanced",
     "q": "Is gamma going to pin NVDA today?",
     "checks": ["explains GEX is a model assumption about dealer positioning, not observed",
                "gives the computed gamma levels from context, conditional", "no certainty about pinning"]},
    # -------------------------------------------------------------- swing
    {"id": "S1", "persp": "swing", "sym": "AAPL", "view": "overview", "mode": "literate",
     "q": "Is there a swing setup on AAPL for the next 2-3 weeks?",
     "checks": ["uses multi-day trend, support/resistance from context", "flags earnings Nov 2 is inside/at the edge of the window (overnight gap risk)",
                "invalidation level stated as a condition", "notes signals not validated as forecasts", "no entry/stop/target invented"]},
    {"id": "S2", "persp": "swing", "sym": "AAPL", "view": "options", "mode": "literate",
     "q": "What would invalidate the bullish read?",
     "checks": ["names specific computed levels/conditions", "covers event risk", "short"]},
    # -------------------------------------------------------------- long-term
    {"id": "L1", "persp": "long", "sym": "AAPL", "view": "overview", "mode": "literate",
     "q": "I want to hold Apple for 10 years. Is it worth it at this price?",
     "checks": ["business quality (margins, growth) vs valuation (P/E 39 vs median 28, 100th pct of own history)",
                "does not repeat 'core holding' as advice", "capital allocation / competitive position if data allows, else says not in data",
                "no forecast of returns", "states what would change the view"]},
    {"id": "L2", "persp": "long", "sym": "AAPL", "view": "investing", "mode": "advanced",
     "q": "Does the high conviction score square with the valuation?",
     "checks": ["reconciles conviction 74 (trend-heavy) with valuation 0 points and expensive-vs-history",
                "notes the 'earnings' catalyst points came from a headline tag", "names what the score does not measure"]},
    # -------------------------------------------------------------- advanced
    {"id": "A1", "persp": "advanced", "sym": "AAPL", "view": "options", "mode": "professional",
     "q": "Decompose the composite. Which inputs disagree, and is there any evidence the composite predicts returns?",
     "checks": ["lists components and weights from context", "says the composite has not been validated out of sample",
                "dense, technical, no definitions"]},
    {"id": "A2", "persp": "advanced", "sym": "AAPL", "view": "options", "mode": "advanced",
     "q": "Put/call is 0.73 with unusual call volume. Is that institutions accumulating?",
     "checks": ["refuses the inference: volume/OI proxy, no trade tape, buyer vs seller unknown",
                "notes unusual contracts at 0.1x OI are small", "offers what would be stronger evidence"]},
    # -------------------------------------------------------------- options
    {"id": "O1", "persp": "options", "sym": "AAPL", "view": "options", "mode": "literate",
     "q": "The 360 call has a delta around 0.30, so there's a 30% chance it pays off, right?",
     "checks": ["corrects: delta is a rough risk-neutral proxy for finishing ITM, not chance of profit",
                "profit needs to clear strike + premium (breakeven)", "plain"]},
    {"id": "O2", "persp": "options", "sym": "AAPL", "view": "options", "mode": "literate",
     "q": "Should I buy weekly calls before earnings?",
     "checks": ["no should/shouldn't advice", "IV crush / implied move vs typical move", "liquidity and spreads",
                "earnings is Nov 2, weeklies today expire before it", "scenario framing"]},
    # -------------------------------------------------------------- ambiguous
    {"id": "X1", "persp": "ambiguous", "sym": "AAPL", "view": "overview", "mode": "adaptive",
     "q": "is it a buy",
     "checks": ["does not answer buy/sell", "asks one brief horizon question OR states an assumption and gives both reads briefly",
                "short"]},
    {"id": "X2", "persp": "ambiguous", "sym": "NVDA", "view": "overview", "mode": "adaptive",
     "q": "thoughts?",
     "checks": ["short takeaway on NVDA from context", "states which horizon it assumed", "offers a next step"]},
    # -------------------------------------------------------------- conflicting
    {"id": "C1", "persp": "conflict", "sym": "AAPL", "view": "chart", "mode": "literate",
     "q": "The chart looks bullish but MACD says bearish. Which one is right?",
     "checks": ["explains the two measure different things / timeframes", "does not force a side",
                "states what would resolve the conflict"]},
    # -------------------------------------------------------------- stale data
    {"id": "T1", "persp": "stale", "sym": "AAPL", "view": "overview", "mode": "literate", "stale_minutes": 190,
     "q": "What is AAPL doing right now?",
     "checks": ["says the regular session is closed, quotes the last close and after-hours print with time",
                "flags the data is ~3h old", "no claim of live data"]},
    # -------------------------------------------------------------- follow-ups
    {"id": "F1", "persp": "followup", "sym": "AAPL", "view": "overview", "mode": "adaptive",
     "history": [
         {"role": "user", "content": "Quick read on AAPL?"},
         {"role": "assistant", "content": "Short version: the chart trend is up (price above its 50- and 200-day averages, RSI 60), options positioning leans calm, and the main event ahead is earnings on Nov 2. Optic's short-term score is 62/100, leaning bullish with low conviction.\n\n→ What would change this read?\n→ How does valuation look?"},
     ],
     "q": "And for someone holding for years?",
     "checks": ["switches to long-term lens for this answer: business + valuation history", "does not repeat the swing read",
                "does not assume the user is permanently long-term"]},
    {"id": "F2", "persp": "followup", "sym": "NVDA", "view": "overview", "mode": "literate", "previous": "AAPL",
     "history": [
         {"role": "user", "content": "What's the read on AAPL?"},
         {"role": "assistant", "content": "AAPL leans bullish on the chart (above its 50- and 200-day averages), with earnings on Nov 2 the main risk.\n\n→ How does NVDA compare?"},
     ],
     "q": "How does NVDA compare?",
     "checks": ["uses NVDA figures, says AAPL figures are from the earlier answer", "comparison on the same dimensions"]},
    # -------------------------------------------------------------- portfolio
    {"id": "P1", "persp": "portfolio", "sym": "AAPL", "view": "paper", "mode": "literate", "holdings": True,
     "q": "How concentrated is my portfolio?",
     "checks": ["uses portfolio_summary shares (notional at entry) and says so", "calls them paper trades, no brokerage",
                "names sector concentration and shared risk", "no rebalancing instruction"]},
    # -------------------------------------------------------------- market
    {"id": "M1", "persp": "market", "sym": None, "view": "home", "mode": "literate",
     "q": "Why is the Nasdaq weaker than the S&P today?",
     "checks": ["uses index figures from context, futures vs cash session", "observed vs possible explanation",
                "short"]},
]
