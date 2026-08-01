/* Optic Terminal — view layer. */

const ASSISTANT_NAME = 'Pulse';

const STATE = {
  // No ticker until the user picks one — the terminal opens on the home page
  // rather than silently deciding SPY is what you wanted to look at.
  ticker: null,
  view: 'home',
  trackerScanning: false,
  trackerMonth: null,
  swing: null,
  scalp: null,
  earnings: null,
  market: null,
  indices: null,
  long: null,
  roth: null,
  tracker: null,
  session: null,
  // Roth inputs live in STATE so they survive tab switches.
  rothInputs: { years: 30, risk: 'balanced', annual: 7000, holdings: '', stock_candidates: '' },
};

const $ = (sel) => document.querySelector(sel);
const views = {
  home: $('#view-home'),
  swing: $('#view-swing'), scalp: $('#view-scalp'), earnings: $('#view-earnings'),
  market: $('#view-market'), indices: $('#view-indices'), long: $('#view-long'),
  roth: $('#view-roth'), tracker: $('#view-tracker'),
  settings: $('#view-settings'),
};

/* ------------------------------------------------------------- glossary
   Beginner-facing jargon gets a dotted underline; hovering (or tabbing to it
   with a keyboard) shows a plain-English definition using the same tooltip
   the charts use. Applied to narrative text (summaries, rationale, notes) —
   not to table headers or labels, where it would just add visual noise. */

const GLOSSARY = {
  'liquidity': "How easily something can be bought or sold without moving its price. A stock trading a few hundred thousand dollars a day is illiquid: your own order becomes the market, and the price you get is nothing like the price you saw.",
  'dollar volume': "Share price multiplied by shares traded — the actual money changing hands each day. A better liquidity measure than share count, since a million shares of a $2 stock is a far smaller market than a million shares of a $200 one.",
  'screen': "A first-pass filter over a large list of stocks, used to decide which few deserve real analysis. A screen ranks candidates; it does not decide whether a trade is good.",
  'universe': "The full set of stocks a strategy is allowed to consider before any filtering. A strategy that only ever looks at ten names has a ten-name universe, however sophisticated the rest of it is.",
  'paper trading': "Placing trades on record without real money, so the results can be measured later. The prices are real; the positions are not.",
  'expectancy': "The average profit or loss per trade across every completed trade. Positive means the approach made money on average; negative means it lost, no matter how good the win rate looks.",
  'profit factor': "Total money made by the winners divided by total money lost by the losers. Above 1.0 is profitable; below 1.0 is not.",
  'win rate': "The share of completed trades that made money. On its own it says very little — a 30% win rate is excellent if the winners are five times the size of the losers.",
  'stop loss': "A price set in advance where you exit if the trade goes against you. It defines the loss before entering, instead of deciding in the moment.",
  'time stop': "Closing a trade because it hasn't worked within a set number of days, rather than because it hit a price. Capital sitting in an idea that isn't moving has a cost.",
  'realised p&l': "Profit and loss from trades that have already closed. This is the number that is final.",
  'unrealised p&l': "Profit and loss on positions still open. It changes every time the price moves and only becomes real when the position closes.",
  'slippage': "The gap between the price you expected and the price you actually got. It always works against you, and it's why simulated results tend to beat live ones.",
  'mid price': "The midpoint between the best buy and sell price. Filling at the mid is optimistic — in practice you usually pay closer to the worse side, especially on options.",
  'risk-on': "Investors are feeling confident and buying riskier assets (stocks, crypto) instead of safe ones (bonds, cash).",
  'risk-off': "Investors are nervous and moving money into safe assets (bonds, cash, gold) instead of risky ones like stocks.",
  'gamma': "How fast an option's directional exposure (its delta) changes as the stock price moves. High gamma means the trade's behavior can flip quickly.",
  'dealer gamma': "A measure of how much stock market-maker dealers must buy or sell to stay hedged as the price moves. It hints at whether trading will feel calm or wild.",
  'gamma flip': "The price level where dealers switch from calming price swings down to amplifying them, or the reverse.",
  'flip point': "The price level where dealers switch from calming price swings down to amplifying them, or the reverse.",
  'gex': "Gamma Exposure — an estimate of dealer hedging pressure at each price level, used to guess whether a stock will feel calm (range-bound) or wild (trending).",
  'delta': "How much an option's price moves for every $1 move in the stock. A delta of 0.50 means the option gains about $0.50 when the stock gains $1.",
  'theta': "How much value an option loses every single day just from time passing, even if the stock doesn't move. Often called ‘time decay’.",
  'theta decay': "The steady loss of an option's value simply from time passing, even if the stock price doesn't move.",
  'vega': "How much an option's price changes when the market's expectation of future volatility (movement) changes.",
  'implied volatility': "The market's guess at how much a stock will move in the future, baked into the option's price. Higher implied volatility means more expensive options.",
  'iv rank': "Where today's implied volatility sits between its own highest and lowest point over roughly the past year, on a 0-100 scale. High IV rank means options are historically expensive right now; low means they're historically cheap.",
  'iv percentile': "The percentage of days over roughly the past year where implied volatility was lower than it is today. Similar to IV rank, but counts days instead of measuring the full high-low range.",
  'realized volatility': "How much a stock has actually moved, measured from its real price history — as opposed to implied volatility, which is a forward-looking guess baked into option prices.",
  'open interest': "The total number of option contracts at a given strike that are currently open — bought or sold but not yet closed or expired.",
  'breakeven': "The stock price an option needs to reach for you to not lose money on the trade, ignoring commissions.",
  'iron condor': "A strategy that profits if the stock stays inside a price range. You sell options on both sides of the range and buy further-out options to cap your risk.",
  'iron butterfly': "Like an iron condor, but the options you sell are both at today's price instead of spread apart — collects more money upfront but needs the stock to stay very still.",
  'straddle': "Buying a call and a put at the same strike price — a bet that the stock will move a lot, in either direction.",
  'strangle': "Like a straddle, but the call and put are at different (further out) strike prices — cheaper, but needs a bigger move to make money.",
  'put/call ratio': "How many put options (bets a stock will fall) are being traded compared to call options (bets it will rise). A high ratio can mean traders are nervous.",
  'relative strength': "How a stock or sector is performing compared to a benchmark like the S&amp;P 500 — not just whether it's up, but whether it's beating the market.",
  'z-score': "A way to measure how unusual a value is compared to its recent normal range. A z-score of +2 or higher (or -2 or lower) means it's unusually stretched.",
  'basis points': "A tiny unit for measuring rates — 100 basis points equals 1%.",
  'rsi': "Relative Strength Index — a 0-100 gauge of whether a stock has been bought or sold too aggressively recently. Above 70 often means overbought, below 30 often means oversold.",
  'macd': "A trend-following indicator that compares two moving averages to help spot when momentum is shifting up or down.",
  'atr': "Average True Range — a measure of how much a stock typically moves in a single day. A higher ATR means a more volatile stock.",
  'fibonacci retracement': "A charting tool that marks likely support and resistance price levels using a mathematical ratio, meant to guess where a pullback might stop.",
  'support': "A price level where a falling stock has tended to stop falling and bounce.",
  'resistance': "A price level where a rising stock has tended to stop rising and pull back.",
  'short interest': "The percentage of a stock's available shares that have been sold short — bet against — by traders expecting the price to fall.",
  'days to cover': "How many days it would take, at average trading volume, for all short sellers to buy back their shares. A proxy for how ‘trapped’ short sellers might be.",
  'pair trade': "Betting on one stock or asset relative to another — going long the one you think will do better and short the one you think will do worse.",
  'moving average': "The average closing price over a set number of past days, used to smooth out day-to-day noise and show the underlying trend.",
  'overbought': "A stock has risen quickly enough that it may be due for a pause or pullback.",
  'oversold': "A stock has fallen quickly enough that it may be due for a bounce.",
  'liquidity': "How easily a stock or option can be bought or sold without moving its price much. Low liquidity means wide bid/ask spreads and harder fills.",
  'bid/ask spread': "The gap between the highest price a buyer will pay (bid) and the lowest price a seller will accept (ask). A wide spread makes a trade more expensive to enter and exit.",
  'vwap': "Volume-Weighted Average Price — the average price paid today, weighted by how much volume traded at each price. Above VWAP is generally considered strong for the day; below is weak.",
  'opening range': "The high and low price set in the first few minutes after the market opens. Breaking above or below it is a common early signal of the day's direction.",
  'relative volume': "How much a stock is trading today compared to how much it normally trades at this same point in the day. Well above 1x means unusually heavy activity.",
  'rvol': "Relative Volume — how much a stock is trading today compared to its normal volume at this same point in the day. Well above 1x means unusually heavy activity.",
  'pivot point': "A price level calculated from yesterday's high, low, and close, used intraday as a quick reference for where a stock might find support or resistance today.",
  '0dte': "Zero Days to Expiry — an option expiring the same day it's traded. Its price can swing very fast since there's no time left for the bet to play out.",
  'gamma squeeze': "A rapid, self-reinforcing price move that happens when dealers who sold options must keep buying (or selling) the stock to stay hedged as the price moves, which pushes the price further in the same direction.",
  'short squeeze': "A rapid price rise that forces traders who bet against a stock (short sellers) to buy it back to limit their losses — and that buying pushes the price up even more.",
  'call wall': "The strike with the largest call open interest / gamma exposure above the price. Dealers hedging those calls tend to sell as the stock rallies into it, so it often acts like a ceiling.",
  'put wall': "The strike with the largest put open interest / gamma exposure below the price. Dealers hedging those puts tend to buy as the stock falls into it, so it often acts like a floor.",
  'gamma pin': "The single strike with the largest gamma exposure in either direction — the level dealer hedging tends to pull price toward, especially as expiry gets close.",
  'r1': "First resistance — a level derived from yesterday's high/low/close where an intraday rally often stalls first, before testing R2.",
  'r2': "Second resistance — a level derived from yesterday's high/low/close, further above price than R1 and a tougher ceiling to break through.",
  's1': "First support — a level derived from yesterday's high/low/close where an intraday decline often stalls first, before testing S2.",
  's2': "Second support — a level derived from yesterday's high/low/close, further below price than S1 and a tougher floor to break through.",
  'eps': "Earnings Per Share — the company's profit divided by its share count. It's the single number analysts forecast and the market judges the report against.",
  'consensus': "The average of what analysts forecast. Beating it isn't automatically good news — what matters is whether the market had already priced in more.",
  'implied move': "How big a move the options market is pricing for a stock, read from the cost of buying a call and a put at the same strike. If it costs 6% of the share price, traders expect roughly a 6% move.",
  'straddle cost': "The combined price of a call and a put at the same strike. It's what you pay to bet on a big move in either direction, and doubles as the market's estimate of that move's size.",
  'beat rate': "How often a company has reported earnings above the analyst consensus. A high rate usually means management guides conservatively, so a beat is already expected.",
  'surprise': "The gap between reported earnings and what analysts expected, in percent. Positive is a beat, negative is a miss.",
  'event premium': "The extra cost baked into option prices ahead of a known event like earnings. It evaporates the moment the event passes, which is why long options can lose money even when the stock moves your way.",
  'price target': "Where an analyst thinks the stock will trade, usually 12 months out. Useful as a sentiment gauge, unreliable as a forecast — targets sit above the current price in almost every market.",
  'gross margin': "What proportion of revenue is left after the direct cost of making the product. Rising gross margin means pricing power or cheaper inputs.",
  'operating margin': "What proportion of revenue is left after all the running costs of the business. It's the cleanest read on whether growth is actually becoming more profitable.",
  'year over year': "Comparing a quarter with the same quarter twelve months earlier, rather than the one just before it. This strips out seasonality — most businesses aren't supposed to have equal quarters.",
  'glidepath': "The practice of shifting from stocks toward bonds as your horizon shortens, so a crash close to when you need the money can't undo decades of growth.",
  'expense ratio': "The annual percentage a fund charges to run it, taken automatically from your returns. 0.03% is $3 a year per $10,000; 1% is $100 — over decades the difference compounds into real money.",
  'cagr': "Compound Annual Growth Rate — the steady yearly rate that would produce the same end result as the actual bumpy path. It smooths over crashes rather than hiding them, so read it alongside the worst drawdown.",
  'rebalance': "Selling some of what has grown and buying what has lagged, to return to your target weights. Inside a Roth this triggers no tax, which makes it far easier than in a taxable account.",
  'correlation': "How closely two investments move together, from -1 (opposite) to +1 (identical). Two funds with correlation near 1 are effectively the same bet.",
  'dte': "Days to expiry — how many calendar days until the option stops trading and either pays out or expires worthless.",
  'oi': "Open interest — the number of contracts at that strike currently held open by someone. High open interest means a lot of money is already positioned there.",
  'itm': "In the money — the option already has real value if exercised today: a call below the stock price, or a put above it.",
  'otm': "Out of the money — the option has no value if exercised today, and needs the stock to move before it does.",
  'atm': "At the money — the strike sits closest to where the stock is trading right now.",
  'sma': "Simple moving average — the plain average closing price over a number of days, used to define the trend.",
  'ema': "Exponential moving average — like a moving average but weighted toward recent days, so it turns faster than the simple version.",
  'yoy': "Year over year — comparing a period with the same period a year earlier, which removes seasonal distortion from the comparison.",
};

// Sort longest-first so multi-word terms (e.g. "put/call ratio") match
// before a shorter substring (e.g. "ratio") would otherwise win.
const GLOSSARY_KEYS = Object.keys(GLOSSARY).sort((a, b) => b.length - a.length);
const GLOSSARY_RE = new RegExp(
  '\\b(' + GLOSSARY_KEYS.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b',
  'gi',
);

/** Escape text, then wrap recognised jargon in a hoverable/focusable term.
 *
 * Also sentence-cases the first letter. Most of this prose is composed in Python
 * — reasons, notes, caveats, factor explanations — and every call site here
 * begins its own phrase (verified: none is spliced mid-sentence), so this is the
 * one place that catches all of it. Glossary matching is case-insensitive, so a
 * capitalised first word still resolves. */
function gloss(rawText) {
  const escaped = esc(cap(rawText));
  return escaped.replace(GLOSSARY_RE, (match) => {
    const def = GLOSSARY[match.toLowerCase()];
    if (!def) return match;
    return `<dfn class="gloss-term" tabindex="0" data-def="${esc(def)}">${match}</dfn>`;
  });
}

/* ------------------------------------------------------- section headings
   Every panel and sub-section heading gets a one-line "what is this, and why
   does it matter to the market" definition on hover. Kept separate from
   GLOSSARY because these are whole-heading lookups, not words spotted inside
   prose — the entire heading underlines as one term. */
const HEADER_DEFS = {
  // ---- swing / options
  'swing verdict': "The terminal's combined read on this stock: chart signals, dealer gamma, options flow, news tone and the macro backdrop blended into one score from -100 (bearish) to +100 (bullish).",
  'quote': "The current price and where it sits inside today's range and the past year's range — the baseline every other panel is measured against.",
  'options analytics': 'The options-market side of the analysis: greeks, dealer gamma exposure and call-versus-put flow.',
  'strike & entry recommendation': "Which option contract the terminal would pick given the current read, and the price level where entering makes sense instead of chasing.",
  'price, moving averages & fibonacci': "The price history with trend lines and common pullback levels drawn on — used to judge whether the trend is intact and where a move is likely to pause.",
  'rsi (14)': 'A momentum gauge from 0-100 showing whether the stock has been bought or sold too hard recently. Above 70 is stretched, below 30 is washed out.',
  'macd (12, 26, 9)': 'A trend gauge comparing two moving averages, used to spot momentum turning up or down before the price move is obvious.',
  'delta analysis': "How much directional exposure sits in this stock's options — a read on whether the options market is positioned long or short.",
  'gamma analysis': 'Where option positions are most sensitive to price moves, which tells you which price levels are likely to attract or repel the stock.',
  'gex — dealer gamma exposure': 'An estimate of how much stock market-makers must buy or sell to stay hedged as price moves. It hints at whether the tape will feel calm and range-bound or fast and trending.',
  'call vs put flow': "Whether today's options activity leans toward bullish bets (calls) or bearish bets (puts) — a read on positioning, not a promise of direction.",
  'net premium by strike': 'How much money is actually being spent at each strike price, showing where traders are placing real bets rather than just quoting.',
  'buy calls / puts': 'Straightforward directional trades — buying a call to bet the stock rises, or a put to bet it falls. Simple, but all the premium is at risk.',
  'options strategies': 'Multi-leg trades that profit from a price range, a change in volatility, or one asset moving relative to another, rather than pure direction.',
  'news & catalysts': 'Recent headlines scored for tone, plus scheduled events like earnings that tend to move the stock and keep options expensive.',

  // ---- company data
  'company data': 'The business behind the ticker — revenue, profit, how heavily it is bet against, and who owns the shares.',
  'short interest': 'How much of the stock has been sold short (bet against) and how long those bets would take to unwind. Heavy short interest is fuel for a squeeze.',
  'financials': 'Revenue, profit and cash flow across recent years — whether the underlying business is growing or shrinking.',
  'earnings track record': 'How the company has done versus expectations in past quarters, which sets how much the market trusts its guidance.',
  'insider & institutional activity': 'Whether company executives and large funds have been buying or selling — occasionally an early signal of confidence or concern.',

  // ---- scalps
  'scalps': 'Very short-term trading, minutes to hours, where intraday levels and dealer hedging matter far more than company fundamentals.',
  'squeeze read': 'How likely a sharp self-reinforcing move is right now — either from dealers hedging options (gamma squeeze) or short sellers being forced to buy back (short squeeze).',
  'session snapshot': "Where the stock sits today against the levels intraday traders actually watch: the average price paid, the opening range, and yesterday's pivots.",
  'intraday price, vwap & fast emas': "Today's minute-by-minute price with the average price paid and fast trend lines — the chart a scalper trades off.",
  'near-term gamma': 'Dealer hedging pressure at the nearest option expiry, which shapes how the price behaves for the rest of today.',
  'liquidity & short interest': 'Whether you can get in and out of these options cheaply, and how heavily the stock is bet against.',

  // ---- earnings
  'latest result': "The quarter the company just reported: what it delivered against what analysts expected. A beat is only half the story — the session after the print is what says whether the market cared, and a company can beat and still sell off.",
  'reported eps': "Earnings per share the company actually delivered for the quarter, next to the figure analysts had modelled. The gap between them is the surprise.",
  'next report': "When the company next reports results, what analysts expect, and how much movement the options market is charging for the event.",
  'event pricing': "Whether the options are expensive or cheap for the period they cover, measured against how far this stock has actually moved over the same span. Expensive favors selling premium; cheap favors buying it.",
  'estimate revisions': "Whether analysts have been raising or cutting their forecasts recently. Estimates move in response to company guidance, so the direction of travel is the closest public read on guidance you can get from free data.",
  'surprise history': "How reported earnings compared with consensus in past quarters, and — more usefully — what the stock actually did the session afterwards. A company can beat every quarter and still sell off.",
  'financial growth': "Revenue, profit and margin trends versus the same quarter a year earlier, so seasonality doesn't distort the comparison. Expanding margins mean growth is getting more profitable, not just bigger.",
  'forward estimates': "What analysts model for coming quarters and fiscal years, and how many of them are covering the name. Fewer analysts means a less reliable consensus.",
  'annual growth': "Full-year revenue, profit and margins, which show the multi-year trajectory a single quarter can easily disguise.",
  'analyst view': "Where the sell side thinks the stock is going and how the ratings are split. Best treated as a sentiment and positioning gauge — targets sit above spot in almost every market.",

  // ---- macro & sectors
  'macro regime': 'Whether the overall market is currently rewarding risk-taking or punishing it, scored from cross-asset signals like the VIX, credit, the dollar and oil. It sets how aggressive to be, not what to buy.',
  'market breadth': 'How many parts of the market are joining a move. A rally with broad participation tends to keep going; one carried by a handful of names is fragile.',
  'cross-asset dashboard': 'Key markets outside stocks — volatility, the dollar, bonds, commodities, credit and crypto — because these usually move before equities do.',
  'cross-asset ratios': 'One market divided by another, which exposes relative shifts (like small caps versus large caps) that a single price chart hides.',
  'sector relative strength': "Which sectors are beating or lagging the S&P 500 — showing where money is actually flowing, not just what's green today.",
  'themes & sub-industries': 'Narrower baskets than sectors, like clean energy or cybersecurity, ranked against the broad market.',
  'niche industries': 'Very specific industry baskets, like semiconductors or memory chips, where strength often shows up before a broad sector average reflects it.',
  'breakout candidates': 'Groups coiled near the top of their range with improving relative strength — statistically the most likely to break out next.',
  'ratio pair trades': "Going long one thing and short another, so the profit comes from the gap between them and you're far less exposed to the market's overall direction.",

  // ---- long-term & indices
  // ---- roth
  'roth ira model allocation': "A rules-based target mix built from your horizon and risk tolerance, measured against ten years of fund data. A starting point to compare your own plan against — not advice, and it knows nothing about your income, taxes or other accounts.",
  'target weights': "The model's suggested split, with what each fund costs to own, what it yields, and how badly it has fallen in the past. Weights are targets to rebalance toward, not prices to chase.",
  'contribution projection': "What steady annual contributions would compound to at the blended historical return of these funds. Arithmetic on the past, not a forecast — the band shows uncertainty in the average rate, not the risk of a bad decade arriving early.",
  'what the roth wrapper changes': "Reasoning that applies specifically because this is a Roth: growth and distributions are never taxed, losses aren't deductible, and the annual limit is small.",
  'fund universe': "Every candidate fund measured over its full history — return, cost, volatility and worst drawdown — so you can see why the model picked what it picked, and what it left out.",
  'correlation': "How closely two funds move together, from -1 to +1. Near +1 means owning both adds little diversification; the low pairs are what actually reduce risk.",
  'drift from target': "How far your actual holdings have wandered from the model weights. Markets cause this on their own — whatever grows fastest ends up overweight, quietly making the portfolio riskier than you chose.",
  "where to put this year's contribution": "A buy-only rebalancing plan: point new money at whatever is underweight and drift closes without selling anything. The simplest maintenance there is.",
  'overlap in your holdings': "Pairs of your holdings that move almost identically. Owning both feels like diversification but isn't — it's one bet at double the size, with twice the paperwork.",
  'individual stock sleeve': "An optional slice for single companies, capped by your risk setting and horizon, with each candidate gated on its long-run record. The concentrated part of the portfolio, sized so a single blow-up can't derail the plan.",

  // ---- optic's positions
  "optic's positions": "The terminal's own simulated trading record. Whenever a scan finds a setup that clears the conviction bar, it takes the trade on paper — both as shares and as the option contract it recommended — and holds it until a stop, target, time limit or expiry closes it. It exists so the recommendations can be judged on results instead of on how confident they sound.",
  'track record': "Results across every closed trade. Win rate on its own is close to meaningless — a strategy can win 70% of the time and still lose money if the losses are bigger. Expectancy, the average result per trade, is the number that decides whether an edge exists.",
  'open positions': "Trades the terminal currently holds on paper, marked at the latest available price. These P&L numbers move with the market and are not final — nothing counts until the position closes.",
  'closed trades': "Every completed trade with the reason it ended. The exit reasons are the honest part: a record full of time stops means the signals were early or wrong, not just unlucky.",
  'scan history': "When the terminal last looked for trades, how many tickers it considered and how many it actually took. Most scans should open nothing — a system that finds a trade every time it looks isn't being selective.",
  'how the shortlist was chosen': "The funnel behind every scan. The universe is the whole NASDAQ, but running the full analysis on 3,000 stocks would take hours, so a cheap price-and-volume screen ranks them first and only the top names get the real work. This panel shows what was dropped at each step and why, so \"we scan the whole exchange\" and \"we analysed thirty names\" are both visible at once rather than one standing in for the other.",
  'screen ranking': "The screen's own ordering — a trend and momentum score built from price and volume alone. It is not the terminal's verdict and carries no options, news or fundamental input; its only job is to choose what gets a closer look. A name at the top of this table can still be rejected outright by the full analysis.",
  'month by month': "The record split by calendar month, so consistency is visible rather than hidden inside one all-time total. Six steady months and one lucky month can produce the same headline number and mean completely different things — and splitting by month also lines each result up against the market conditions it was trading in.",
  'consistency': "Every month since the record began, including months with no trades at all. Equity carries forward, so each month's return is measured against what the account was worth when that month started. Watch the shape of the run, not the best month.",
  'closed in this month': "Trades that finished during the selected month. These are the only results that count toward that month's realised figures.",
  'opened in this month and still held': "Positions started in the selected month that haven't closed yet. Their profit or loss is unrealised and will land in whichever month they eventually close.",
  'how these positions are taken': "The fixed rules the ledger follows: what it will take, how big, and when it gets out. They're set in advance and applied identically to every ticker, so the record can't be improved after the fact by changing its mind.",
  'position sizing': "How the size of each trade is decided. Shares are sized so that being stopped out costs a fixed fraction of the account, which means a volatile stock with a wide stop gets a smaller position. Options are sized on the whole premium, because a long option really can go to zero.",

  'growth vs the broad market (qqq / spy)': "Whether high-growth megacaps are leading or lagging the wider market. Rising means money favors long-duration growth; falling means it's rotating to value and cyclicals. A style-leadership read, not a direction call.",
  'index regime': 'Where the major indices sit in their own long-run cycle — the backdrop every individual stock trades against. A great company in a falling index still usually falls.',
  'long-term view': 'The multi-year picture for owning the shares outright: structural trend, drawdown history, and whether current prices are a reasonable place to accumulate. Options play no part at this horizon.',
  'weekly structure': 'Price history in weekly bars, which strips out daily noise so the underlying multi-year trend is visible.',
  'drawdown': "How far below its all-time high the asset sits now, and how deep past declines went — the downside you'd have had to sit through.",
  'return & risk': 'Long-run returns alongside how much volatility you had to endure to earn them. High returns from a wild ride are not the same as steady ones.',
  'valuation & accumulation': 'Whether the stock looks expensive or cheap versus its own history, and the price zones where long-term buyers have stepped in before.',

  // ---- sub-sections
  'fundamental momentum': "Which way the company's numbers are trending — whether analysts are raising or cutting forecasts, how recent quarters landed against expectations, and whether revenue and margins are expanding. It is shown next to the composite rather than inside it: revision trends do carry signal over a few weeks, but the composite is a technicals-led read and folding fundamentals in would move every score in the terminal. Valuation is left out entirely, because at a two-to-eight-week horizon it tells you nothing about direction.",
  'component scores': 'The individual inputs behind the overall verdict and the weight each one carries, so you can see what is driving the number.',
  "what's driving it": 'The specific readings that pushed the score to where it is.',
  'what makes up this score': "Every factor the model weighed and the points each contributed, so you can see where the number came from. The weightings are the author's judgement, not a fitted model \u2014 read the factors, not just the total.",
  'volatility context': 'Whether options are currently expensive or cheap compared with how much the stock has actually been moving. Expensive options favor selling premium over buying it.',
  'what would create a trade': 'The price levels that would turn the current no-trade read into an actionable setup.',
  'where to enter': 'The price zone the terminal considers a reasonable entry, as opposed to chasing a move already underway.',
  'entry zone levels': 'The specific prices that bound the suggested entry area.',
  'target & risk': 'Where the trade is aiming, and the level that would prove the idea wrong.',
  'candidate strikes, ranked': 'Option contracts scored against each other on cost, liquidity and probability of working out.',
  'notable contracts': 'Individual option contracts with unusual volume or open interest relative to their own normal — often where new positioning is showing up.',
  'at-the-money greeks by expiry': 'How sensitive the closest-to-price options are, broken out by expiry date.',
  'gamma concentration by expiry': 'Which expiry dates hold the most dealer hedging pressure. Near-dated concentration makes price moves sharper.',
  'net gex by strike': 'Dealer hedging pressure at each individual strike price.',
  'gamma profile across spot': 'How dealer hedging pressure would change if the stock moved up or down from here — where the tape flips from calm to fast.',
  'key levels': 'The strikes acting most like a ceiling or a floor because of how options are positioned there.',
  'fibonacci levels': 'Pullback prices derived from a mathematical ratio, used as rough guesses for where a move might pause. Widely watched, which is part of why they sometimes work.',
  'support & resistance': "Price levels the stock has genuinely reversed at, scored on four things: how many times price turned there, how firmly it was rejected (long wicks beat bars that closed at their extreme), how much volume traded across the level, and how recently it was last defended. Unlike Fibonacci, these come from actual candle history rather than a ratio.",
  'moving averages': 'Average prices over various periods, used to define the trend and act as moving support or resistance.',
  'rotation': 'Which sectors money is moving into and out of right now — the shift beneath a flat-looking index.',
  'equal-weight vs cap-weight (rsp / spy)': 'Whether the average stock is keeping up with the megacaps. When it is not, the index is being carried by a few names and the rally is narrower than it looks.',
  'accumulation zones': 'Price areas where long-term buyers have historically stepped in — useful for staging purchases rather than buying all at once.',
  'headlines': 'Recent news articles, each scored for tone.',
  'catalyst types detected': 'The kinds of events the headlines mention — earnings, guidance, product news, legal, or M&A.',
  'next report': 'When the company next reports earnings. Options usually stay expensive into that date and cheapen sharply after it.',
  'recent insider transactions': 'Buying and selling by the company’s own executives and directors.',
  'largest reported holders': 'The biggest institutional shareholders, from their most recent filings.',
  'why': 'The specific readings behind this verdict, so you can judge the reasoning rather than trusting the score.',
  'why the chart reads': 'The individual technical signals behind the bias, and which way each one is pointing.',

  // ---- cross-asset dashboard group headings
  'volatility': "How much movement the market expects. Rising volatility means traders are paying up for protection — usually a warning sign for stocks.",
  'rates': 'Government bond yields. Rising yields make future company profits worth less today, which pressures growth stocks hardest.',
  'fx': 'Currencies. A strong US dollar tightens global financial conditions and squeezes overseas earnings; a fast-falling yen can force a global unwind.',
  'commodities': 'Raw materials. Oil and copper strength can signal real demand, but a spike becomes a cost shock that squeezes profit margins.',
  'credit': "Corporate bonds. Credit markets usually crack before stocks do, so weakness here is one of the earliest warnings you'll get.",
  'equity': 'The major stock indices themselves, for direct comparison against everything else on this dashboard.',
  'crypto': 'Bitcoin and friends, treated here as a pure risk-appetite gauge — it tends to move first and hardest when speculative money shifts.',
};

/** Wrap a section heading so hovering it explains what the section is and how
 *  it relates to the market. Unknown headings pass through as plain text. */
function hg(title) {
  const def = HEADER_DEFS[String(title).toLowerCase().replace(/\s+/g, ' ').trim()];
  if (!def) return esc(title);
  return `<dfn class="gloss-term" tabindex="0" data-def="${esc(def)}">${esc(title)}</dfn>`;
}

function initGlossaryTooltips() {
  const show = (el, evt) => {
    const def = el.getAttribute('data-def');
    if (!def) return;
    const fakeEvt = (evt && typeof evt.clientX === 'number')
      ? evt
      : (() => {
        const r = el.getBoundingClientRect();
        return { clientX: r.left + r.width / 2, clientY: r.top };
      })();
    showTip(`<div class="t-title">${el.textContent}</div><div class="t-row" style="max-width:220px;white-space:normal">${def}</div>`, fakeEvt);
  };
  document.addEventListener('mouseover', (evt) => {
    const el = evt.target.closest && evt.target.closest('.gloss-term');
    if (el) show(el, evt);
  });
  document.addEventListener('mouseout', (evt) => {
    if (evt.target.closest && evt.target.closest('.gloss-term')) hideTip();
  });
  document.addEventListener('focusin', (evt) => {
    const el = evt.target.closest && evt.target.closest('.gloss-term');
    if (el) show(el, null);
  });
  document.addEventListener('focusout', (evt) => {
    if (evt.target.closest && evt.target.closest('.gloss-term')) hideTip();
  });
}

/* ------------------------------------------------------------------ utils */

function esc(str) {
  return String(str === null || str === undefined ? '' : str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* Mount a chart into its container.
 *
 * `node` may be a ready-made element, or a factory taking the container's real
 * pixel width. SVG charts use a viewBox with `preserveAspectRatio: meet`, so a
 * hardcoded viewBox width narrower than the container leaves the drawing
 * letterboxed and centered instead of filling the panel — building the viewBox
 * at the measured width is what actually makes charts full-width.
 */
function mount(id, node) {
  const host = document.getElementById(id);
  if (!host) return;
  let el = node;
  if (typeof node === 'function') {
    // clientWidth is 0 for a host inside a hidden (inactive) view; fall back to
    // the old fixed width so off-screen tabs still render something sane.
    const w = Math.round(host.clientWidth) || 720;
    el = node(Math.max(w, 320));
  }
  if (el) { host.innerHTML = ''; host.appendChild(el); }
}

/* ------------------------------------------------------------------ reveal */

const REVEAL_STEP_MS = 60;   // gap between consecutive panels
const REVEAL_CAP_MS = 560;   // past this, later panels share a delay so a long
                             // view doesn't take multiple seconds to finish

/** Cascade the panels of a freshly rendered view into place, top to bottom.
 *
 * Only called on foreground loads. Panels are visible by default, so if this
 * never runs (reduced motion, or a JS failure) the dashboard still shows.
 */
/* Definitions for whole column headers. Short labels keep a six-column table
 * inside a third-width panel; the explanation lives on hover instead of in the
 * header text, which is what was dragging a 320px column out to 565px. */
const TH_HINTS = {
  'distance': 'How far this level sits from the current price, as a percentage. Negative means the level is below the stock.',
  'strength': 'A 0-100 score for how much this level has actually mattered: how many pivots cluster there, how firmly price was rejected, how much volume traded across it, and how recently it was last defended.',
  'touches': 'How many separate times price reversed at this level, and how long ago it was last tested. More touches means more traders are watching it; a level untouched for a long time matters less.',
  'last': 'How long ago the level was last tested, in bars — so 17w means seventeen weeks ago on a weekly chart.',
  'role': 'Whether this level sits below the current price (support, a potential floor) or above it (resistance, a potential ceiling).',
  'value': 'The current value of the average, in dollars.',
  'price vs': 'Where the stock is trading relative to that average, as a percentage. Positive means price is above it.',
  '10-day slope': 'Whether the average itself is rising or falling over the last ten days — the direction of the trend, not just where price sits.',
  'level': 'The Fibonacci retracement percentage this line is drawn at.',
  'level ($)': 'The price of the level, with whether it sits below the current price (support) or above it (resistance).',
  'spread': 'The gap between the best bid and the best ask, as a percentage of the mid price. Wider spreads cost more to get in and out of.',
  'type': 'Call or put.',
  'setup': 'What the numbers suggest doing, if anything.',
  'thesis': 'The reasoning behind the pair — why one side should outperform the other.',
};

/** Give table headers the same hover definitions as prose.
 *
 * Column headers are the one place with no room to explain an abbreviation, and
 * "DTE", "OI" and "Δ" are exactly where a reader stalls. Done as a post-render
 * pass so every table is covered without wrapping eighty inline <th> literals. */
function glossHeaders(host) {
  if (!host) return;
  host.querySelectorAll('th').forEach((th) => {
    if (th.querySelector('.gloss-term')) return;      // already processed
    const text = th.textContent;
    if (!text || !text.trim()) return;
    const whole = TH_HINTS[text.trim().toLowerCase()];
    if (whole) {
      th.innerHTML = `<dfn class="gloss-term" tabindex="0" data-def="${esc(whole)}">${esc(text)}</dfn>`;
      return;
    }
    const marked = gloss(text);
    if (marked !== esc(text)) th.innerHTML = marked;   // only if a term matched
  });
}

/** Underline each definition once per panel, not once per mention.
 *
 * "delta" appears six times in the Delta Analysis panel and every one of them was
 * getting a dotted underline, which turns a helpful affordance into visual noise
 * — the eye reads the repeated marks as emphasis that isn't there. The first
 * mention in a panel keeps its definition; later ones become plain text.
 *
 * Keyed on the definition rather than the word, so two different terms that share
 * a definition collapse together while "DTE" (a column-header hint) and "delta"
 * (a glossary word) never interfere. Scoped per panel because panels are read
 * independently: a term explained in one shouldn't arrive bare in the next.
 */
function dedupeGlossTerms(host) {
  if (!host) return;
  // Treat the host itself as a scope when it holds no panels — the session strip
  // and the home page are single blocks of prose rather than panel grids.
  const scopes = host.querySelectorAll('.panel').length
    ? host.querySelectorAll('.panel') : [host];
  scopes.forEach((panel) => {
    const seen = new Set();
    panel.querySelectorAll('dfn.gloss-term').forEach((term) => {
      const def = term.getAttribute('data-def');
      if (!def) return;
      if (!seen.has(def)) { seen.add(def); return; }
      // Unwrap: keep the words, drop the marking.
      term.replaceWith(document.createTextNode(term.textContent));
    });
  });
}

function revealPanels(host) {
  if (!host) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  host.classList.remove('revealing');
  // Reading offsetWidth forces a reflow, so re-adding the class restarts the
  // animation instead of the browser collapsing the remove/add into a no-op.
  void host.offsetWidth;
  host.classList.add('revealing');

  host.querySelectorAll('.panel').forEach((el, i) => {
    el.style.animationDelay = `${Math.min(i * REVEAL_STEP_MS, REVEAL_CAP_MS)}ms`;
    el.classList.add('reveal');
  });
}

function setStatus(parts) {
  $('#statusline').innerHTML = parts.map((p) => `<span>${p}</span>`).join('');
}

/* Sentence case for anything rendered as a label, value or chip.
 *
 * Applied here rather than by rewriting several hundred string literals, because
 * a lot of this text arrives from the API — exit reasons, mark sources, stances,
 * revision directions — and capitalising at the source would mean the same fix in
 * two languages. Three things are left alone on purpose:
 *
 *   - strings that start with markup, since `<span>` must not become `<Span>`;
 *   - anything already starting with a capital, digit, or symbol (+12%, −6.3%);
 *   - the GLOSSARY and HEADER_DEFS *keys*, which are lowercase lookup keys and
 *     never rendered — only their values reach the page.
 */
/** A price, with its currency and a fixed two decimals.
 *
 * "12.54", "330.0" and "342.43" all appeared in the UI as bare numbers, where a
 * reader has to work out whether they're dollars, a strike, a percentage or a
 * ratio. Every level and premium goes through here instead. */
function usd(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return '$' + Number(value).toLocaleString('en-US', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
}

/** A strike, which is nearly always whole dollars — "330.0" reads like a typo. */
function strikeLabel(value) {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  return '$' + n.toLocaleString('en-US', {
    minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

function cap(text) {
  if (text === null || text === undefined) return text;
  const str = String(text);
  if (!str || str[0] === '<') return str;
  const first = str[0];
  if (first !== first.toLowerCase()) return str;      // already capitalised
  if (!/[a-z]/.test(first)) return str;               // digit, symbol, entity
  return first.toUpperCase() + str.slice(1);
}

function toneChip(tone) {
  const t = (tone || '').toLowerCase();
  let cls = 'neutral';
  if (t.includes('bull')) cls = 'bull';
  else if (t.includes('bear')) cls = 'bear';
  else if (t.includes('risk-off') || t.includes('weak')) cls = 'bear';
  else if (t.includes('risk-on') || t.includes('strong')) cls = 'bull';
  return `<span class="chip ${cls}"><span class="dot"></span>${esc(cap(tone) || 'n/a')}</span>`;
}

/** Conviction words from the long-term model don't contain "bull"/"bear", so
 *  toneChip's keyword matching can't classify them. */
function toneChipConviction(conviction) {
  const c = (conviction || '').toLowerCase();
  let cls = 'neutral';
  if (c === 'high') cls = 'bull';
  else if (c === 'moderate') cls = 'bull';
  else if (c === 'low' || c === 'cautious') cls = 'bear';
  return `<span class="chip ${cls}"><span class="dot"></span>${esc(cap(conviction) || 'n/a')}</span>`;
}

function kv(pairs) {
  return `<dl class="kv">${pairs
    .filter(Boolean)
    .map(([k, v, cls]) => `<dt>${gloss(cap(k))}</dt><dd class="${cls || ''}">${cap(v)}</dd>`)
    .join('')}</dl>`;
}

function tile(label, value, note, cls) {
  return `<div class="tile"><span class="label">${gloss(cap(label))}</span>
    <span class="value ${cls || ''}">${cap(value)}</span>
    ${note ? `<span class="note">${cap(note)}</span>` : ''}</div>`;
}

function loadingHTML(what) {
  return `<div class="loading"><span class="spinner"></span>Loading ${esc(what)}…</div>`;
}

function errorHTML(msg) {
  return `<div class="error-box"><strong>Could not load.</strong> ${esc(msg)}</div>`;
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json();
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json();
}

/* ----------------------------------------------------------------- settings
 *
 * Two preferences, both cosmetic in the sense that neither changes a number:
 * the theme, and which time zone the session clock is displayed in. Market hours
 * are defined in Eastern Time and stay that way — the zone setting converts how
 * they're *shown*, it does not move the market.
 *
 * Stored in localStorage, so a visitor's choice survives a reload without any
 * server-side account. The theme is also stamped by an inline script in the head
 * before first paint; this module keeps them in step afterwards.
 */
const THEME_KEY = 'optic.theme';
const TZ_KEY = 'optic.timezone';

// A short list rather than the full IANA database: these cover where a US-market
// retail trader is realistically sitting, and a 400-entry select is worse than a
// missing option. "auto" resolves to whatever the browser reports.
const TIMEZONES = [
  { id: 'auto', label: 'My device\u2019s time zone' },
  { id: 'America/New_York', label: 'New York — Eastern (market time)' },
  { id: 'America/Chicago', label: 'Chicago — Central' },
  { id: 'America/Denver', label: 'Denver — Mountain' },
  { id: 'America/Los_Angeles', label: 'Los Angeles — Pacific' },
  { id: 'America/Toronto', label: 'Toronto' },
  { id: 'America/Sao_Paulo', label: 'S\u00e3o Paulo' },
  { id: 'Europe/London', label: 'London' },
  { id: 'Europe/Paris', label: 'Paris / Berlin / Madrid' },
  { id: 'Europe/Istanbul', label: 'Istanbul' },
  { id: 'Asia/Dubai', label: 'Dubai' },
  { id: 'Asia/Kolkata', label: 'Mumbai' },
  { id: 'Asia/Singapore', label: 'Singapore' },
  { id: 'Asia/Hong_Kong', label: 'Hong Kong' },
  { id: 'Asia/Tokyo', label: 'Tokyo' },
  { id: 'Australia/Sydney', label: 'Sydney' },
  { id: 'UTC', label: 'UTC' },
];

const SETTINGS = {
  theme: 'system',      // 'system' | 'light' | 'dark'
  timezone: 'auto',
};

function loadSettings() {
  try {
    const t = localStorage.getItem(THEME_KEY);
    // The head script writes a resolved 'light'/'dark'; absence means follow the OS.
    SETTINGS.theme = (t === 'light' || t === 'dark') ? t : 'system';
    const tz = localStorage.getItem(TZ_KEY);
    if (tz && (tz === 'auto' || TIMEZONES.some((z) => z.id === tz))) SETTINGS.timezone = tz;
  } catch (e) { /* private mode: defaults stand */ }
}

/** The zone actually used for formatting. */
function activeZone() {
  if (SETTINGS.timezone !== 'auto') return SETTINGS.timezone;
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch (e) {
    return 'UTC';
  }
}

/** Format an ISO instant as a clock time in a given zone. */
function timeIn(iso, zone, opts = {}) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('en-US', {
      hour: 'numeric', minute: '2-digit', timeZone: zone, ...opts,
    }).replace(':00 ', ' ').toLowerCase();
  } catch (e) {
    return '';
  }
}

/** Weekday in a given zone.
 *
 * Needed because the server's weekday is the *Eastern* one, and pairing it with a
 * converted time produced "Sat 2:19 am GMT+9" for a moment that is Sunday in
 * Tokyo — the day and the clock disagreeing by a whole date. Whichever zone the
 * time is shown in has to supply the day too.
 */
function dayIn(iso, zone) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', timeZone: zone });
  } catch (e) {
    return '';
  }
}

/** Short zone abbreviation, e.g. "ET", "BST", "GMT+5:30". */
function zoneAbbrev(zone, iso) {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: zone, timeZoneName: 'short',
    }).formatToParts(iso ? new Date(iso) : new Date());
    const found = parts.find((p) => p.type === 'timeZoneName');
    return found ? found.value : zone;
  } catch (e) {
    return zone;
  }
}

/** True when the viewer is already on market time — then there's nothing to convert. */
function viewerOnMarketTime() {
  const zone = activeZone();
  if (zone === 'America/New_York') return true;
  try {
    const now = new Date();
    const a = now.toLocaleString('en-US', { timeZone: zone });
    const b = now.toLocaleString('en-US', { timeZone: 'America/New_York' });
    return a === b;
  } catch (e) {
    return false;
  }
}

function applyTheme() {
  const resolved = SETTINGS.theme === 'system'
    ? (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light' : 'dark')
    : SETTINGS.theme;
  document.documentElement.dataset.theme = resolved;
  try {
    if (SETTINGS.theme === 'system') localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, SETTINGS.theme);
  } catch (e) { /* private mode */ }
  syncChartTheme();
  rerenderActiveView();
  renderSessionBar();
}

function saveTimezone() {
  try { localStorage.setItem(TZ_KEY, SETTINGS.timezone); } catch (e) { /* private mode */ }
  renderSessionBar();
  if (STATE.view === 'settings') renderSettings();
}

/* ------------------------------------------------------------------- legal
 *
 * Mirrors app/legal.py. Held here as well as server-side so the footer renders
 * before any request completes — a disclaimer that waits on the network is a
 * disclaimer that is absent exactly when a page first appears.
 *
 * Not a lawyer's work. These are the standard disclosures for a tool that prints
 * strike prices and a simulated track record; counsel should review before this
 * goes further than people you know.
 */
const LEGAL = {
  full: [
    'Optic Terminal is an independent research tool. It is not financial, investment, tax or legal advice, and nothing in it is a recommendation, solicitation or offer to buy or sell any security, option or other instrument. It is provided for informational and educational purposes only.',
    'The operator is not a broker-dealer, not a registered investment adviser, and not licensed to give investment advice. No output here is personalised: the tool knows nothing about your finances, tax position, time horizon, obligations or risk tolerance, and cannot take them into account.',
    'Every figure is generated from third-party data that may be delayed, incomplete or wrong, and from models whose assumptions are stated but not guaranteed. Verify anything you intend to act on against primary sources.',
    'Trading involves substantial risk of loss and is not suitable for everyone. Options carry additional risks and can expire worthless, losing the entire premium; short positions can lose more than the amount invested. Past performance does not predict future results. You may lose some or all of your capital.',
    'Consult a licensed financial professional before making any investment decision. The operator accepts no liability for any loss arising from use of this tool.',
  ],
  // Per-view notice, naming the specific way that view's output could be taken
  // for advice. Generic boilerplate gets skimmed; a specific sentence doesn't.
  areas: {
    swing: '<strong>Not a recommendation.</strong> The strikes, limit prices, stops and targets on this tab are model output, not advice to place any trade. Options can expire worthless and lose the entire premium.',
    long: '<strong>Not a recommendation.</strong> A conviction score summarises historical data. It says nothing about whether this holding suits your horizon, taxes or existing exposure.',
    roth: '<strong>Not retirement or tax advice.</strong> A rules-based illustration to compare against your own plan. It is not tailored to your income, tax situation, other accounts or goals, and contribution limits and eligibility change — confirm current rules with the IRS and a licensed professional.',
    earnings: '<strong>Not a recommendation.</strong> Event pricing describes what the market is charging, not what you should do about it. Holding an option through a report can lose money even when the direction is right.',
    tracker: '<strong>Hypothetical performance.</strong> These positions were never placed with real money. Simulated results are prepared with the benefit of hindsight, assume fills at the mid price, and bear no commission, slippage, financing, borrow cost or tax. No real account would necessarily achieve results resembling these, and simulated performance does not indicate future results.',
    market: '<strong>Not a recommendation.</strong> A regime read on the market as a whole — not a view on any individual security, and not advice to change your positioning.',
    indices: '<strong>Not a recommendation.</strong> Long-run index context, not advice to buy, sell or hold any index fund.',
  },
};

/** The per-view notice, as markup to prepend to a view. */
function legalBanner(view) {
  const text = LEGAL.areas[view];
  if (!text) return '';
  return `<div class="legal-area" role="note">${text}</div>`;
}

function initLegalFooter() {
  const btn = $('#legal-more');
  const full = $('#legal-full');
  if (!btn || !full) return;
  full.innerHTML = LEGAL.full.map((p) => `<p>${esc(p)}</p>`).join('');
  btn.addEventListener('click', () => {
    full.hidden = !full.hidden;
    btn.textContent = full.hidden ? 'Full disclaimer' : 'Hide disclaimer';
  });
}

/* ===================================================================== HOME */

/* Views listed here keep all their code but disappear from the UI — the nav tab,
 * the home card, and the auto-refresh tick. Delete a name to bring it back. */
const HIDDEN_VIEWS = new Set(['scalp']);

const NOTICE_KEY = 'optic.notice.dismissed';
const CHART_MODE_KEY = 'optic.chart.mode';
const SHOW_FIB_KEY = 'optic.chart.fib';
const SHOW_SR_KEY = 'optic.chart.sr';
const CHART_RANGE_KEY = 'optic.chart.range';

const CHART_INTERVAL_KEY = 'optic.chart.interval';

// Bar counts per interval, so "3M" means 63 daily bars or 13 weekly ones rather
// than 63 of whatever is selected.
const CHART_RANGES = [
  { key: '1m', label: '1M', daily: 21, weekly: 5 },
  { key: '3m', label: '3M', daily: 63, weekly: 13 },
  { key: '6m', label: '6M', daily: 126, weekly: 26 },
  { key: '1y', label: '1Y', daily: 252, weekly: 52 },
  { key: 'all', label: 'All', daily: Infinity, weekly: Infinity },
];

const CHART_INTERVALS = [
  { key: 'daily', label: 'Daily' },
  { key: 'weekly', label: 'Weekly' },
];

/* ---------------------------------------------------- client-side indicators
 *
 * Recomputed here rather than resampling the server's daily values, because a
 * weekly chart wants genuinely weekly indicators. Sampling a 14-day RSI at each
 * Friday would look plausible and mean something different — a 14-*week* RSI is
 * a slower measure, and mislabelling one as the other is the kind of error a
 * reader can't catch. */

function smaSeries(values, period) {
  const out = new Array(values.length).fill(null);
  let sum = 0, count = 0;
  for (let i = 0; i < values.length; i += 1) {
    const v = values[i];
    if (v === null || v === undefined || !isFinite(v)) { sum = 0; count = 0; continue; }
    sum += v; count += 1;
    if (count > period) { sum -= values[i - period]; count = period; }
    if (count === period) out[i] = sum / period;
  }
  return out;
}

function emaSeries(values, period) {
  const out = new Array(values.length).fill(null);
  const k = 2 / (period + 1);
  let prev = null;
  for (let i = 0; i < values.length; i += 1) {
    const v = values[i];
    if (v === null || v === undefined || !isFinite(v)) continue;
    prev = prev === null ? v : v * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

/** Wilder's RSI — the smoothing the standard uses, not a simple average. */
function rsiSeries(closes, period = 14) {
  const out = new Array(closes.length).fill(null);
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i < closes.length; i += 1) {
    const change = closes[i] - closes[i - 1];
    const gain = Math.max(change, 0);
    const loss = Math.max(-change, 0);
    if (i <= period) {
      avgGain += gain / period;
      avgLoss += loss / period;
      if (i === period) {
        out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
      }
      continue;
    }
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

function macdSeries(closes, fast = 12, slow = 26, signalPeriod = 9) {
  const fastE = emaSeries(closes, fast);
  const slowE = emaSeries(closes, slow);
  const macd = closes.map((_, i) =>
    (fastE[i] === null || slowE[i] === null ? null : fastE[i] - slowE[i]));
  const signal = emaSeries(macd.map((v) => (v === null ? null : v)), signalPeriod);
  const hist = macd.map((v, i) => (v === null || signal[i] === null ? null : v - signal[i]));
  return { macd, signal, hist };
}

/* ------------------------------------------------- support / resistance (client)
 *
 * Ported from the Python version so levels follow the chart's own interval. A
 * retail trader reading a weekly chart wants levels drawn from weekly bars —
 * structural shelves that took months to form — not the daily levels resampled.
 * Switching interval genuinely changes which levels exist, which is the point.
 *
 * Same four inputs as the server: clustered pivots, how much of each pivot bar
 * was rejection wick, volume traded across the level, and recency. */

/** Indices of local extrema, comparing each bar against `order` neighbours on
 *  both sides. Equivalent to scipy's argrelextrema with greater_equal/less_equal. */
function localExtrema(values, order, wantHigh) {
  const out = [];
  for (let i = order; i < values.length - order; i += 1) {
    const v = values[i];
    if (v === null || !isFinite(v)) continue;
    let isExtreme = true;
    for (let k = 1; k <= order && isExtreme; k += 1) {
      const a = values[i - k], b = values[i + k];
      if (a === null || b === null) { isExtreme = false; break; }
      isExtreme = wantHigh ? (v >= a && v >= b) : (v <= a && v <= b);
    }
    if (isExtreme) out.push(i);
  }
  return out;
}

/** Average true range over the last `period` bars — sets the clustering width. */
function atrValue(high, low, close, period = 14) {
  const trs = [];
  for (let i = 1; i < close.length; i += 1) {
    if ([high[i], low[i], close[i - 1]].some((v) => v === null || !isFinite(v))) continue;
    trs.push(Math.max(
      high[i] - low[i],
      Math.abs(high[i] - close[i - 1]),
      Math.abs(low[i] - close[i - 1]),
    ));
  }
  if (!trs.length) return null;
  const tail = trs.slice(-period);
  return tail.reduce((a, c) => a + c, 0) / tail.length;
}

function computeSRLevels(ps, spot, opts = {}) {
  const { order = 4, maxLevels = 8 } = opts;
  const high = ps.high || [], low = ps.low || [], close = ps.close || [];
  const open = ps.open || [], volume = ps.volume || [];
  const bars = close.length;
  if (bars < order * 2 + 10 || !spot) return [];

  let tol = atrValue(high, low, close);
  tol = tol && isFinite(tol) ? tol * 0.6 : spot * 0.012;
  if (!(tol > 0)) tol = spot * 0.012;

  const pivots = [];
  const push = (i, price, kind, rejection) => pivots.push({
    price, kind, rejection, barsAgo: bars - 1 - i,
  });
  localExtrema(high, order, true).forEach((i) => {
    const rng = high[i] - low[i];
    push(i, high[i], 'swing high',
      rng > 0 ? (high[i] - Math.max(open[i], close[i])) / rng : 0);
  });
  localExtrema(low, order, false).forEach((i) => {
    const rng = high[i] - low[i];
    push(i, low[i], 'swing low',
      rng > 0 ? (Math.min(open[i], close[i]) - low[i]) / rng : 0);
  });
  if (!pivots.length) return [];

  pivots.sort((a, b) => a.price - b.price);
  const clusters = [];
  pivots.forEach((piv) => {
    const hit = clusters.find((c) => Math.abs(piv.price - c.mean) <= tol);
    if (hit) {
      hit.pivots.push(piv);
      hit.mean = hit.pivots.reduce((a, p) => a + p.price, 0) / hit.pivots.length;
    } else {
      clusters.push({ mean: piv.price, pivots: [piv] });
    }
  });

  const totalVolume = volume.reduce((a, c) => a + (c || 0), 0) || 1;
  const levels = [];
  clusters.forEach((c) => {
    if (c.pivots.length < 2) return;   // one pivot is a spike, not a level
    const level = c.mean;
    let volAt = 0;
    for (let i = 0; i < bars; i += 1) {
      if (high[i] >= level && low[i] <= level) volAt += volume[i] || 0;
    }
    const volShare = volAt / totalVolume;
    const freshest = Math.min(...c.pivots.map((p) => p.barsAgo));
    const recency = Math.exp(-freshest / (bars / 3));
    const avgRejection = c.pivots.reduce((a, p) => a + p.rejection, 0) / c.pivots.length;
    const strength = Math.min(c.pivots.length, 6) / 6 * 40
      + Math.min(avgRejection, 1) * 25
      + Math.min(volShare * 4, 1) * 20
      + recency * 15;
    const kinds = new Set(c.pivots.map((p) => p.kind));
    levels.push({
      price: Math.round(level * 100) / 100,
      touches: c.pivots.length,
      role: level > spot ? 'resistance' : 'support',
      distance_pct: Math.round((level / spot - 1) * 10000) / 100,
      strength: Math.round(strength * 10) / 10,
      rejection_pct: Math.round(avgRejection * 100),
      volume_share_pct: Math.round(volShare * 1000) / 10,
      last_touch_bars_ago: freshest,
      origin: kinds.size > 1 ? 'both' : [...kinds][0],
      band_low: Math.round((level - tol / 2) * 100) / 100,
      band_high: Math.round((level + tol / 2) * 100) / 100,
    });
  });
  levels.sort((a, b) => b.strength - a.strength);
  return levels.slice(0, maxLevels);
}

/** Roll daily bars up into weekly ones: first open, highest high, lowest low,
 *  last close, summed volume. Keyed by ISO week so a short holiday week still
 *  forms one bar rather than being merged into its neighbour. */
function aggregateWeekly(ps) {
  const dates = ps.dates || [];
  if (!dates.length) return ps;
  const weekKey = (iso) => {
    const d = new Date(iso + 'T00:00:00Z');
    const day = (d.getUTCDay() + 6) % 7;           // Monday = 0
    d.setUTCDate(d.getUTCDate() - day);            // back to that week's Monday
    return d.toISOString().slice(0, 10);
  };
  const out = { dates: [], open: [], high: [], low: [], close: [], volume: [] };
  let key = null;
  for (let i = 0; i < dates.length; i += 1) {
    const k = weekKey(dates[i]);
    if (k !== key) {
      key = k;
      out.dates.push(dates[i]);
      out.open.push(ps.open ? ps.open[i] : null);
      out.high.push(ps.high ? ps.high[i] : null);
      out.low.push(ps.low ? ps.low[i] : null);
      out.close.push(ps.close ? ps.close[i] : null);
      out.volume.push(ps.volume ? ps.volume[i] : 0);
    } else {
      const j = out.dates.length - 1;
      out.dates[j] = dates[i];                     // label the bar by its last session
      if (ps.high) out.high[j] = Math.max(out.high[j], ps.high[i]);
      if (ps.low) out.low[j] = Math.min(out.low[j], ps.low[i]);
      if (ps.close) out.close[j] = ps.close[i];
      if (ps.volume) out.volume[j] += ps.volume[i] || 0;
    }
  }
  // Weekly moving averages from weekly closes. 200 periods needs ~4 years of
  // weeks and only ~2 are fetched, so the long line is 50-week here — shown in
  // the legend so the chart never claims a length it isn't.
  out.sma20 = smaSeries(out.close, 20);
  out.sma50 = smaSeries(out.close, 50);
  out.sma200 = new Array(out.close.length).fill(null);
  out.weekly = true;
  return out;
}

// 'line' or 'candle'. Persisted because it's a viewing preference, not state
// belonging to a particular ticker.
let chartMode = 'line';
let chartRange = '6m';
let chartInterval = 'daily';
// Level families are independently switchable. Both default on — they're the
// point of the panel — but a chart with fifteen horizontal lines is hard to read
// when you only want the price action, so each can be turned off and the choice
// sticks like the other viewing preferences.
let showFib = true;
let showSR = true;
try {
  chartMode = localStorage.getItem(CHART_MODE_KEY) === 'candle' ? 'candle' : 'line';
  const savedRange = localStorage.getItem(CHART_RANGE_KEY);
  if (CHART_RANGES.some((r) => r.key === savedRange)) chartRange = savedRange;
  const savedInterval = localStorage.getItem(CHART_INTERVAL_KEY);
  if (CHART_INTERVALS.some((i) => i.key === savedInterval)) chartInterval = savedInterval;
  showFib = localStorage.getItem(SHOW_FIB_KEY) !== 'off';
  showSR = localStorage.getItem(SHOW_SR_KEY) !== 'off';
} catch (e) { /* private mode */ }

// Bars shown in the MACD panel. Capped independently of the price chart: a
// crossover is a short-horizon event, and at 500 bars two lines a few points
// apart are one thick stroke. Roughly a quarter of a trading year on dailies.
const MACD_WINDOW = 70;

// Period for the RSI's own signal line. 9 is the same length the MACD uses for
// its signal, which keeps the two panels comparable rather than each having its
// own arbitrary smoothing.
const RSI_SIGNAL_PERIOD = 9;

/** The most recent MACD/signal crossover in a window, and how far back it was.
 *
 * This is the question the panel exists to answer — "has momentum turned yet?" —
 * and it was left to the reader to spot by eye on a chart where the two lines
 * overlap. Returns null when no cross happened inside the window, which is itself
 * worth saying: a long stretch with no cross means the trend hasn't been
 * challenged.
 */
function lastMacdCross(macd, signal) {
  if (!Array.isArray(macd) || !Array.isArray(signal)) return null;
  for (let i = macd.length - 1; i > 0; i -= 1) {
    const a = macd[i - 1] - signal[i - 1];
    const b = macd[i] - signal[i];
    if (a === null || b === null || !isFinite(a) || !isFinite(b)) continue;
    // Sign change between consecutive bars is the crossing.
    if ((a <= 0 && b > 0) || (a >= 0 && b < 0)) {
      return { index: i, bullish: b > 0, barsAgo: macd.length - 1 - i };
    }
  }
  return null;
}

/** Plain-language read on a crossover: has momentum turned, and how recently.
 *
 * Shared by the MACD and RSI panels — both ask the same question of a fast line
 * against its own average, so they should answer it in the same words. */
function macdCrossSentence(cross, wk, dates, weekly, zoom, what = 'MACD') {
  const unit = weekly ? 'week' : 'day';
  const gap = wk.macd[wk.macd.length - 1] - wk.signal[wk.signal.length - 1];
  const prevGap = wk.macd.length > 1
    ? wk.macd[wk.macd.length - 2] - wk.signal[wk.signal.length - 2] : gap;
  const widening = Math.abs(gap) > Math.abs(prevGap);

  if (!cross) {
    return `<p class="caveat" style="margin:6px 0 0">No crossover in the last ${zoom} ${unit}s —
      ${what} has stayed ${gap >= 0 ? 'above' : 'below'} its signal line throughout, so momentum has
      not changed direction in this window. The gap is currently
      ${widening ? 'widening' : 'narrowing'}${widening ? '' : ', which is what precedes a cross'}.</p>`;
  }
  const when = cross.barsAgo === 0
    ? `on the latest ${unit}`
    : `${cross.barsAgo} ${unit}${cross.barsAgo === 1 ? '' : 's'} ago`;
  const date = dates[cross.index] ? ` (${esc(dates[cross.index])})` : '';
  return `<p class="caveat" style="margin:6px 0 0">Last crossover: ${what} crossed
    <strong>${cross.bullish ? 'above' : 'below'}</strong> its signal line ${when}${date} — a
    ${cross.bullish ? 'bullish' : 'bearish'} momentum shift, marked on the chart. The gap has
    ${widening ? 'widened since' : 'narrowed since'}, meaning the shift is
    ${widening ? 'still building' : 'losing conviction and could cross back'}.</p>`;
}

/** Take the last n items. Used to keep the oscillator panels index-aligned with
 *  the sliced price series — a mismatch would offset every date label. */
function tailTo(arr, n) {
  if (!Array.isArray(arr) || !n) return arr;
  return arr.length > n ? arr.slice(arr.length - n) : arr;
}

/** Tail-slice every array in a price_series to the selected range, keeping the
 *  arrays aligned. Moving averages were computed on full history upstream, so
 *  slicing here doesn't corrupt them. */
function sliceSeries(rawPs, rangeKey, intervalKey) {
  // Aggregate first, then slice: rolling up after slicing would cut a partial
  // week at the boundary and produce a misleading first bar.
  const ps = intervalKey === 'weekly' ? aggregateWeekly(rawPs) : rawPs;
  const spec = CHART_RANGES.find((r) => r.key === rangeKey) || CHART_RANGES[2];
  const want = intervalKey === 'weekly' ? spec.weekly : spec.daily;
  const total = (ps.dates || []).length;
  const take = want === Infinity ? total : Math.min(want, total);
  const cut = (arr) => (Array.isArray(arr) ? arr.slice(total - take) : arr);
  return {
    ...ps,
    dates: cut(ps.dates), close: cut(ps.close), open: cut(ps.open),
    high: cut(ps.high), low: cut(ps.low), volume: cut(ps.volume),
    sma20: cut(ps.sma20), sma50: cut(ps.sma50),
    sma200: cut(ps.sma200), ema21: cut(ps.ema21),
    shown_bars: take, total_bars: total, weekly: !!ps.weekly,
  };
}

// A handful of liquid, recognisable starting points rather than a "top movers"
// list, which would need its own endpoint and would be stale outside market hours.
const HOME_QUICK_PICKS = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'AMD', 'MSFT', 'IWM'];

const HOME_CARDS = [
  {
    view: 'swing',
    color: 'var(--s1)',
    title: 'Swing / Options',
    body: 'Composite verdict from technicals, dealer gamma, flow and news — plus a strike and expiry recommendation with an entry trigger.',
  },
  {
    view: 'scalp',
    color: 'var(--s6)',
    title: 'Scalps',
    body: 'Intraday session read: VWAP, opening range, pivots, relative volume, near-term gamma, and separate gamma- and short-squeeze scores.',
  },
  {
    view: 'earnings',
    color: 'var(--s5)',
    title: 'Earnings',
    body: 'Consensus versus what the company actually delivered, estimate-revision trend, margin and growth history, and whether the options market is overcharging for the event.',
  },
  {
    view: 'market',
    color: 'var(--s3)',
    title: 'Macro & Sectors',
    body: 'Cross-asset regime from VIX, the dollar, rates and commodities, with sector, theme and niche-industry relative strength ranked against SPY.',
  },
  {
    view: 'indices',
    color: 'var(--s7)',
    title: 'Indices',
    body: 'Where the major indices sit in their own long-run cycle: multi-year returns, weekly trend, drawdown from the high, and whether the average stock is keeping pace with the megacaps.',
  },
  {
    view: 'long',
    color: 'var(--s4)',
    title: 'Long-Term Shares',
    body: 'For buying and holding the shares themselves: ten-year structure, drawdown history, accumulation zones, valuation and a conviction score. No options here.',
  },
  {
    view: 'roth',
    color: 'var(--s8)',
    title: 'Roth IRA',
    body: 'A rules-based model allocation of low-cost index funds from your horizon and risk tolerance, with cost, correlation and a contribution projection. Not advice — a baseline to compare your own plan against.',
  },
  {
    view: 'tracker',
    color: 'var(--s2)',
    title: "Optic's Positions",
    body: "The terminal's own paper-traded record. When a scan finds a setup good enough, it takes the trade — as shares and as the option it recommended — with a stop, a target and a size, then holds it to the exit. Same ledger for everyone, so the calls can be judged on results.",
  },
];

function renderHome() {
  hideTip();
  const quick = HOME_QUICK_PICKS
    .map((t) => `<button type="button" data-pick="${t}">${t}</button>`)
    .join('');

  const cards = HOME_CARDS
    .filter((c) => !HIDDEN_VIEWS.has(c.view))
    .map((c) => `<div class="home-card" style="--accent:${c.color}">
      <h3>${esc(c.title)}</h3>
      <p>${esc(c.body)}</p>
    </div>`).join('');

  views.home.innerHTML = `
  <div class="home">
    <svg class="home-logo" viewBox="0 0 32 32" aria-label="Optic Terminal logo" role="img">
      <circle cx="16" cy="16" r="14.2" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.28"/>
      <path d="M2.6 16C6.3 8.9 10.9 5.4 16 5.4S25.7 8.9 29.4 16C25.7 23.1 21.1 26.6 16 26.6S6.3 23.1 2.6 16Z"
            fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" opacity="0.7"/>
      <path d="M7.4 20.2 11.4 15.6 14.6 17.8 18.6 11.6 21.6 14 23.9 11.4" fill="none" stroke="var(--s1)"
            stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="23.9" cy="11.4" r="1.5" fill="var(--s1)"/>
    </svg>

    <h1 class="home-title">Optic <span>Terminal</span></h1>
    <p class="home-lede">
      A market research workbench, from a multi-week swing to a multi-year hold. Load a ticker
      and it works through the technical structure, options positioning, earnings and financial
      growth, analyst estimates, news tone and the macro backdrop — then puts them together into
      one read, and tells you where the inputs disagree.
    </p>

    <div class="home-notice" id="home-notice">
      <strong>This is an early prototype — thanks for trying it.</strong>
      <ul>
        <li><b>Start by typing a ticker below</b> (a stock symbol like <code>NVDA</code> or
          <code>AAPL</code>), then look through the tabs along the top.</li>
        <li><b>Hover any underlined word</b> for a plain-English explanation. Most of the jargon
          is explained that way, including every panel heading.</li>
        <li><b>Prices are about 15 minutes behind</b> the real market — this uses a free data
          feed, so don't trade off these numbers.</li>
        <li><b>Macro &amp; Sectors and Indices take 10–20 seconds</b> to load. They pull about 40
          symbols each. Nothing is broken, it's just slow.</li>
        <li><b>Optic's Positions is the terminal trading its own signals on paper</b> — one shared
          record, no real money. It screens every NASDAQ-listed stock, then takes trades in the few
          that clear the bar, so the calls can be checked against results.</li>
        <li><b>Pulse (the assistant) is switched off</b> for now. Everything else works.</li>
      </ul>
      <p class="home-notice-foot">Nothing here is financial advice — it's an analysis tool.
        Anything you type stays in your own browser.
        <button type="button" id="home-notice-hide">Got it, hide this</button></p>
    </div>

    <form class="home-search" id="home-form">
      <div class="combo">
        <input id="home-input" placeholder="Search a ticker or company — e.g. NVDA or Apple"
               spellcheck="false" autocomplete="off"
               aria-label="Ticker symbol or company name"
               role="combobox" aria-expanded="false" aria-autocomplete="list"
               aria-controls="home-results">
        <ul class="combo-list" id="home-results" role="listbox" hidden></ul>
      </div>
      <button class="btn primary" type="submit">Analyze</button>
    </form>

    <div class="home-quick">
      <span class="label">Or jump to</span>
      ${quick}
    </div>

    <div class="home-cards">${cards}</div>

    <div class="home-foot" id="home-foot">
      <span class="dot-sep"><span class="chip neutral" style="padding:1px 7px"><span class="dot"></span>Checking data source…</span></span>
    </div>
  </div>`;

  // Returning testers shouldn't be re-briefed every visit.
  const notice = $('#home-notice');
  if (notice) {
    if (localStorage.getItem(NOTICE_KEY) === 'hidden') notice.hidden = true;
    const hide = $('#home-notice-hide');
    if (hide) {
      hide.addEventListener('click', () => {
        notice.hidden = true;
        try { localStorage.setItem(NOTICE_KEY, 'hidden'); } catch (e) { /* private mode */ }
      });
    }
  }

  // Autofocus the ticker box: on this page there is exactly one thing to do.
  const input = $('#home-input');
  if (input) input.focus();
  // renderHome rebuilds this markup, so the typeahead is re-attached each time.
  attachTypeahead('home-input', 'home-results');
}

/** Fill in the footer once /api/health is known — real-time vs delayed feed and
 *  whether the assistant has credentials. Written separately from renderHome so
 *  the page paints immediately and doesn't wait on a request. */
function renderHomeStatus(health) {
  const foot = $('#home-foot');
  if (!foot) return;
  const realtime = health && health.realtime_chain;
  const provider = (health && health.provider) || 'unknown';
  const assistantOn = !!(health && health.assistant && health.assistant.enabled);
  foot.innerHTML = [
    `<span class="dot-sep"><span class="chip ${realtime ? 'bull' : 'neutral'}" style="padding:1px 7px"><span class="dot"></span>${
      realtime ? `real-time chains via ${esc(provider)}` : `${esc(provider)} feed · quotes delayed ~15 min`}</span></span>`,
    `<span class="dot-sep"><span class="chip ${assistantOn ? 'bull' : 'neutral'}" style="padding:1px 7px"><span class="dot"></span>${
      assistantOn ? `${ASSISTANT_NAME} ready` : `${ASSISTANT_NAME} needs an API key`}</span></span>`,
    '<span>Greeks computed locally via Black-Scholes. Analysis only — not investment advice.</span>',
  ].join('');
}

/* ==================================================================== SWING */

function renderSwing(d) {
  // A glossary tooltip left open over an element that's about to be replaced
  // never gets its mouseout — the browser doesn't fire one when the hovered
  // node is removed from the DOM out from under the cursor. Clear it explicitly
  // whenever we're about to repaint, or it's stuck on screen until the next hover.
  hideTip();
  const q = d.quote || {};
  const em = d.earnings_momentum || {};
  // Outside regular hours the "Last" price is a settled close, and the stock may
  // be trading somewhere quite different. Showing only the close is how a 6%
  // after-hours gap goes unnoticed on the very panel that reports the price.
  const extQ = (() => {
    const inRegular = STATE.session && STATE.session.session
      && STATE.session.session.is_regular;
    if (inRegular) return null;
    if (q.post_market_change_pct !== null && q.post_market_change_pct !== undefined) {
      return { kind: 'After hours', price: q.post_market_price, pct: q.post_market_change_pct };
    }
    if (q.pre_market_change_pct !== null && q.pre_market_change_pct !== undefined) {
      return { kind: 'Pre-market', price: q.pre_market_price, pct: q.pre_market_change_pct };
    }
    return null;
  })();
  const v = d.verdict || {};
  const t = d.technicals || {};
  // Sliced for display before the template is built — the panel heading reads
  // shown_bars, and `const` has no hoisting, so this must precede it.
  // Support/resistance and Fibonacci stay computed server-side on full history,
  // so narrowing the view never changes the levels.
  const ps = sliceSeries(d.technicals && d.technicals.price_series ? d.technicals.price_series : {}, chartRange, chartInterval);
  // Full weekly aggregate, unsliced. The oscillators need more history than the
  // window shows so their warm-up happens off-screen instead of leaving a gap at
  // the left edge of the chart.
  const weeklyAll = chartInterval === 'weekly'
    ? aggregateWeekly((d.technicals || {}).price_series || {}) : null;
  // Levels come from the full series at this interval, so zooming changes what's
  // visible but never which levels exist. Pivot strictness drops on weekly:
  // `order` counts neighbouring bars, and 4 weeks either side of a pivot is a
  // far coarser filter than 4 days.
  const srSource = sliceSeries(
    d.technicals && d.technicals.price_series ? d.technicals.price_series : {},
    'all', chartInterval,
  );
  const srSpot = (d.quote || {}).price
    || (srSource.close || []).filter((v) => v !== null).slice(-1)[0];
  const srComputed = computeSRLevels(srSource, srSpot, {
    order: chartInterval === 'weekly' ? 2 : 4,
  });
  // Bars-ago is in the interval's own units, so the table has to say which.
  const srUnit = chartInterval === 'weekly' ? 'w' : 'd';
  const gex = d.gex || {};
  const gk = d.greeks || {};
  const flow = d.flow || {};
  const news = d.news || {};

  const comp = v.components || {};
  const compRows = Object.entries(comp).filter(([, val]) => val !== null && val !== undefined);
  const maxComp = Math.max(100, ...compRows.map(([, val]) => Math.abs(val)));

  const html = `
  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Swing verdict')} — ${esc(d.ticker)}</h2>
      <p class="sub">${gloss(v.summary || '')}</p>
      <div style="display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap">
        <div>
          <div class="hero-label">Composite</div>
          <div class="hero ${Math.round(v.composite_score || 0) === 0
    ? 'flat' : signClass(v.composite_score)}">${
  Math.round(v.composite_score || 0) > 0 ? '+' : ''}${fmt(v.composite_score, 0)}</div>
          <div class="note" style="color:var(--ink-muted);font-size:12px">Out of ±100</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          ${toneChip(v.stance)}
          <span class="chip neutral"><span class="dot"></span>Conviction: ${esc(v.conviction || 'n/a')}</span>
          ${v.signal_agreement_pct !== null && v.signal_agreement_pct !== undefined
    ? `<span class="chip neutral"><span class="dot"></span>${fmt(v.signal_agreement_pct, 0)}% signal agreement</span>` : ''}
        </div>
      </div>

      <h3>${hg('What makes up this score')}</h3>
      <p class="sub">${gloss(v.scale_note || '')}</p>
      <table class="data">
        <thead><tr><th>Input</th><th>Score</th><th>Weight</th><th>Adds</th><th></th></tr></thead>
        <tbody>
        ${(v.breakdown || []).map((b) => `<tr${b.unavailable ? ' style="opacity:0.5"' : ''}>
          <td class="name">${esc(cap(b.component))}</td>
          <td class="${signClass(b.score)}">${b.unavailable ? 'n/a'
    : (b.score > 0 ? '+' : '') + fmt(b.score, 0)}</td>
          <td>${b.unavailable ? '—' : fmt(b.weight_pct, 0) + '%'}</td>
          <td class="${signClass(b.contribution)}">${b.unavailable ? '—'
    : (b.contribution > 0 ? '+' : '') + fmt(b.contribution, 1)}</td>
          <td>${b.unavailable ? '' : `<span data-bar="${b.score}"></span>`}</td>
        </tr>`).join('')}
        <tr style="border-top:1px solid var(--border-strong)">
          <td class="name"><strong>Composite</strong></td><td></td><td></td>
          <td class="${signClass(v.composite_score)}"><strong>${v.composite_score > 0 ? '+' : ''}${fmt(v.composite_score, 1)}</strong></td>
          <td></td>
        </tr>
        </tbody>
      </table>
      <p class="sub" style="margin-top:6px">Bullish at +30, leaning at +10, and the mirror
        image on the downside.</p>
      <!-- Explanations sit below rather than in a table column: this panel is half-width,
           and a prose column there truncated instead of wrapping. -->
      <dl class="factor-defs">
        ${(v.breakdown || []).map((b) => `<dt>${esc(cap(b.component))}</dt>
          <dd>${gloss(b.measures)}</dd>`).join('')}
      </dl>
      ${(v.conflicts || []).map((c) => `<div class="callout">${gloss(c)}</div>`).join('')}
      ${em.available ? `
        <h3 style="margin-top:14px">${hg('Fundamental momentum')} <span class="chip ${
    em.tone === 'good' ? 'bull' : em.tone === 'bad' ? 'bear' : 'neutral'}"
          style="margin-left:6px"><span class="dot"></span>${esc(cap(em.read))}</span></h3>
        <p class="sub"><strong>Not part of the score above.</strong> Shown because revisions and
          surprise history do carry signal over a few weeks — read alongside the composite, not
          folded into it.</p>
        <table class="data narrow">
          <thead><tr><th>Input</th><th>Reading</th></tr></thead>
          <tbody>${(em.signals || []).map((sig) => `<tr>
            <td class="name">${esc(sig.label)}</td>
            <td class="${sig.tone === 'good' ? 'up' : sig.tone === 'bad' ? 'down' : ''}">${
    esc(cap(sig.read))}</td>
          </tr>`).join('')}</tbody>
        </table>
        <dl class="factor-defs">
          ${(em.signals || []).map((sig) => `<dt>${esc(sig.label)}</dt>
            <dd>${gloss(sig.detail)}</dd>`).join('')}
        </dl>
        <p class="caveat">${gloss(em.excluded_note || '')}</p>
      ` : ''}
      <p class="caveat">${esc(d.data_caveat || '')}</p>
    </div>

    <div class="panel">
      <h2>${hg('Quote')}</h2>
      <p class="sub">${esc(q.name || '')}${q.exchange ? ' · ' + esc(q.exchange) : ''}</p>
      <div style="display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:10px">
        <div>
          <div class="hero-label">${extQ ? 'Regular close' : 'Last'}</div>
          <div class="hero">${fmt(q.price, 2)}</div>
        </div>
        <div class="${signClass(q.change_pct)}" style="font-size:18px;font-weight:600">
          ${q.change !== null && q.change !== undefined ? (q.change > 0 ? '▲ ' : q.change < 0 ? '▼ ' : '') + fmt(q.change, 2) : ''}
          (${fmtPct(q.change_pct, 2)})
        </div>
        ${extQ ? `<div>
          <div class="hero-label">${esc(extQ.kind)}</div>
          <div class="hero ${signClass(extQ.pct)}" style="font-size:26px">${fmt(extQ.price, 2)}</div>
          <div class="${signClass(extQ.pct)}" style="font-size:12.5px">${
    fmtPct(extQ.pct, 2)} vs the close</div>
        </div>` : ''}
      </div>
      ${extQ ? `<p class="caveat" style="margin:-4px 0 10px">Extended-hours trade, on a fraction of
        regular-session volume. Every other number in this panel — and every level on the chart —
        is measured from the ${usd(q.price)} close, not from here.</p>` : ''}
      ${kv([
    ["Today's range", `${usd(q.day_low)} – ${usd(q.day_high)}`],
    ['52-week range', `${usd(q.fifty_two_low)} – ${usd(q.fifty_two_high)}`],
    ['Volume vs 3m avg', q.volume && q.avg_volume ? `${fmtCompact(q.volume)} (${fmt(q.volume / q.avg_volume * 100, 0)}%)` : '—'],
    ['ATR (14)', `${fmt((t.volatility || {}).atr14, 2)} (${fmt((t.volatility || {}).atr_pct, 2)}%)`],
    ['20-day realized vol', `${fmt((t.volatility || {}).realised_vol_20d, 1)}%`],
    ['Expected 2-week range', `±${fmt((t.volatility || {}).expected_2w_move_pct, 1)}%`],
    ['Market cap', fmtCompact(q.market_cap)],
    ['Sector', esc(q.sector || '—')],
  ])}
    </div>
  </div>

  ${renderEntryPlan(d.entry_plan)}

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel span2">
      <h2>${hg('Price, moving averages & Fibonacci')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— ${ps.weekly ? 'weekly' : 'daily'} bars, ${ps.shown_bars} of ${ps.total_bars} shown</span></h2>
      <p class="sub">Bias <strong>${esc(t.bias || 'n/a')}</strong> — ${fibDirectionSentence(t)}
        Dashed lines are Fib levels; the golden 50%/61.8% pair is highlighted.</p>
      <div class="chart-toolbar">
        <label class="range-pick">Interval
          <select id="chart-interval">
            ${CHART_INTERVALS.map((i) => `<option value="${i.key}"${
  i.key === chartInterval ? ' selected' : ''}>${i.label}</option>`).join('')}
          </select>
        </label>
        <label class="range-pick">Timeframe
          <select id="chart-range">
            ${CHART_RANGES.map((r) => `<option value="${r.key}"${
  r.key === chartRange ? ' selected' : ''}>${r.label}</option>`).join('')}
          </select>
        </label>
        <div class="seg" role="group" aria-label="Chart style">
          <button type="button" data-chart-mode="line"
            aria-pressed="${chartMode === 'line'}">Line</button>
          <button type="button" data-chart-mode="candle"
            aria-pressed="${chartMode === 'candle'}">Candles</button>
        </div>
        <div class="seg" role="group" aria-label="Level visibility">
          <button type="button" data-toggle-levels="fib" aria-pressed="${showFib}"
            title="Show or hide the Fibonacci retracement levels">
            <span class="lvl-key fib"></span>Fib levels</button>
          <button type="button" data-toggle-levels="sr" aria-pressed="${showSR}"
            title="Show or hide the support and resistance levels">
            <span class="lvl-key sr"></span>Support / resistance</button>
        </div>
      </div>
      <div id="legend-price"></div>
      <div id="chart-price"></div>
      <div id="chart-price-note"></div>
      <div class="grid c3" style="margin-top:12px">
        <div>
          <h3>${hg('Support & resistance')}</h3>
          <p class="sub" style="margin-bottom:6px">From ${chartInterval} candles, matching the
            chart above — ranked by strength, not just how often price visited.</p>
          <table class="data">
            <!-- Four columns, not six. This table lives in a third-width panel, and
                 role reads naturally under the price while "5 touches, last 17w ago"
                 is one fact, not two — six columns simply could not fit and the
                 table was overflowing into the panel beside it. -->
            <thead><tr><th>Level ($)</th><th>Distance</th><th>Strength</th><th>Touches</th></tr></thead>
            <tbody>${srComputed.map((l) => `<tr>
              <td class="name">${usd(l.price)}
                <div style="color:var(--ink-muted);font-size:11px">${esc(cap(l.role))}</div></td>
              <td class="${signClass(l.distance_pct)}">${fmtPct(l.distance_pct, 1)}</td>
              <td><strong>${fmt(l.strength, 0)}</strong><span data-bar="${l.strength}" data-bar-max="100"></span></td>
              <td>${fmt(l.touches, 0)}
                <div style="color:var(--ink-muted);font-size:11px">${l.last_touch_bars_ago === 0
    ? 'testing now' : 'last ' + l.last_touch_bars_ago + srUnit + ' ago'}</div></td>
            </tr>`).join('') || '<tr><td colspan="4" style="color:var(--ink-muted)">Not enough repeated reversals in the lookback window.</td></tr>'}</tbody>
          </table>
          <p class="caveat">Strength blends four things: how many pivots cluster there, how much
            of each pivot bar was rejection wick rather than body, the share of total volume that
            traded across the level, and how recently it was last defended. Merge width scales
            with ATR, so a level is really a band — the table shows its midpoint. Switching the
            chart to weekly recomputes these from weekly bars, which surfaces bigger structural
            shelves and drops the minor daily ones.</p>
        </div>
        <div>
          <h3>${hg('Fibonacci levels')} <span class="chip ${
    ((t.fibonacci || {}).direction || '').toLowerCase() === 'bearish' ? 'bear' : 'bull'}"
            style="margin-left:6px"><span class="dot"></span>${
    ((t.fibonacci || {}).direction || '').toLowerCase() === 'bearish'
      ? 'High → low' : 'Low → high'}</span></h3>
          <p class="sub" style="margin-bottom:6px">${
    ((t.fibonacci || {}).direction || '').toLowerCase() === 'bearish'
      ? `Drawn down from the swing high of ${usd((t.fibonacci || {}).anchor_high)} to the swing low
         of ${usd((t.fibonacci || {}).anchor_low)}, so retracements rise into resistance.`
      : `Drawn up from the swing low of ${usd((t.fibonacci || {}).anchor_low)} to the swing high
         of ${usd((t.fibonacci || {}).anchor_high)}, so retracements fall into support.`}</p>
          <table class="data">
            <thead><tr><th>Level</th><th>Price ($)</th><th>Distance</th><th>Role</th></tr></thead>
            <tbody>${((t.fibonacci || {}).levels || []).map((l) => `<tr>
              <td class="name">${esc(l.label)}${l.is_golden ? ' ★' : ''}</td>
              <td>${fmt(l.price, 2)}</td>
              <td class="${signClass(l.distance_pct)}">${fmtPct(l.distance_pct, 1)}</td>
              <td class="name" style="color:var(--ink-muted)">${esc(cap(l.role))}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>
        <div>
          <h3>${hg('Moving averages')}</h3>
          <table class="data">
            <thead><tr><th>MA</th><th>Value</th><th>Price vs</th><th>10-day slope</th></tr></thead>
            <tbody>${Object.entries(t.moving_averages || {}).map(([name, m]) => `<tr>
              <td class="name">${esc(name.toUpperCase())}</td>
              <td>${fmt(m.value, 2)}</td>
              <td class="${signClass(m.distance_pct)}">${fmtPct(m.distance_pct, 2)}</td>
              <td class="${signClass(m.slope_10d_pct)}">${fmtPct(m.slope_10d_pct, 2)}</td>
            </tr>`).join('')}</tbody>
          </table>
          ${(t.structure || {}).cross_event ? `<div class="callout info">${esc(t.structure.cross_event)}</div>` : ''}
        </div>
      </div>
      <h3>${hg('Why the chart reads')} ${esc(t.bias || '')}</h3>
      <ul class="reasons">${(t.reasons || []).map((r) => `<li>${gloss(r)}</li>`).join('')}</ul>
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('RSI (14)')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— last ${
    Math.min(MACD_WINDOW, ps.shown_bars || MACD_WINDOW)} ${ps.weekly ? 'weeks' : 'days'}</span></h2>
      <p class="sub">${fmt((t.rsi || {}).value, 1)} out of 100 — ${esc((t.rsi || {}).state || 'n/a')}.
        Above 70 is overbought, below 30 oversold; 50 divides bullish from bearish momentum.</p>
      <div id="legend-rsi"></div>
      <div id="chart-rsi"></div>
      <div id="rsi-cross-note"></div>
    </div>
    <div class="panel">
      <h2>${hg('MACD (12, 26, 9)')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— last ${
    Math.min(MACD_WINDOW, ps.shown_bars || MACD_WINDOW)} ${ps.weekly ? 'weeks' : 'days'}</span></h2>
      <p class="sub">MACD ${fmt((t.macd || {}).macd, 3)} vs signal ${fmt((t.macd || {}).signal, 3)} —
        ${esc((t.macd || {}).state || 'n/a')}${(t.macd || {}).event ? `, ${esc(t.macd.event)}` : ''}.</p>
      <div id="legend-macd"></div>
      <div id="chart-macd"></div>
      <div id="macd-cross-note"></div>
    </div>
  </div>

  ${gex.error ? `<div class="panel" style="margin-bottom:14px"><h2>${hg('Options analytics')}</h2><div class="callout bad">${esc(gex.error)}</div></div>` : `
  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Delta analysis')}</h2>
      <p class="sub">${esc((gk.delta || {}).read || '')}</p>
      ${kv([
    ['Net delta (share equiv.)', fmtCompact((gk.delta || {}).net_delta_shares)],
    ['Net delta notional', '$' + fmtCompact((gk.delta || {}).net_delta_notional)],
    ['Call delta exposure', fmtCompact((gk.delta || {}).call_delta_shares)],
    ['Put delta exposure', fmtCompact((gk.delta || {}).put_delta_shares)],
    ['OI-weighted call delta', fmt((gk.delta || {}).oi_weighted_call_delta, 3)],
    ['OI-weighted put delta', fmt((gk.delta || {}).oi_weighted_put_delta, 3)],
    ['Total open interest', fmtCompact((gk.delta || {}).total_open_interest)],
    ['Dealer delta exposure (DEX)', '$' + fmtCompact((gex.totals || {}).net_dex)],
  ])}
      <h3>${hg('At-the-money greeks by expiry')}</h3>
      <div class="scroll-y">
      <table class="data">
        <thead><tr><th>Expiry</th><th>Days left</th><th>Strike ($)</th><th>Call delta</th><th>Put delta</th><th>Gamma</th><th>Implied vol</th><th>Theta ($/day)</th><th>Theta (%/day)</th></tr></thead>
        <tbody>${(gk.atm_greeks || []).map((r) => `<tr>
          <td class="name">${esc(r.expiry)}</td><td>${r.dte}</td>
          <td>${fmt((r.call || r.put || {}).strike, 1)}</td>
          <td>${fmt((r.call || {}).delta, 3)}</td>
          <td>${fmt((r.put || {}).delta, 3)}</td>
          <td>${fmt((r.call || {}).gamma, 4)}</td>
          <td>${fmt(((r.call || {}).iv || 0) * 100, 1)}%</td>
          <td class="down">${fmt((r.call || {}).theta_per_day, 3)}</td>
          <td class="down">${fmt((r.call || {}).theta_pct_daily, 2)}%</td>
        </tr>`).join('')}</tbody>
      </table></div>
    </div>

    <div class="panel">
      <h2>${hg('Gamma analysis')}</h2>
      <p class="sub">${esc((gk.gamma || {}).read || '')}</p>
      ${kv([
    ['Peak gamma strike', `${fmt((gk.gamma || {}).peak_gamma_strike, 1)} (${fmtPct((gk.gamma || {}).peak_gamma_distance_pct, 1)})`],
    ['Gamma within ±2% of spot', `${fmt((gk.gamma || {}).gamma_within_2pct_share, 1)}%`],
    ['Total chain gamma (OI-weighted)', fmtCompact((gk.gamma || {}).total_gamma_oi)],
    ['Net vanna exposure', fmtCompact((gk.second_order || {}).net_vanna)],
    ['Net charm exposure', fmtCompact((gk.second_order || {}).net_charm)],
  ])}
      <p class="caveat">${esc((gk.second_order || {}).note || '')}</p>
      <h3>${hg('Gamma concentration by expiry')}</h3>
      <table class="data">
        <thead><tr><th>Expiry</th><th>DTE</th><th>Gamma (OI)</th><th>Share</th><th>Open interest</th></tr></thead>
        <tbody>${((gk.gamma || {}).by_expiry || []).map((r) => `<tr>
          <td class="name">${esc(r.expiry)}</td><td>${r.dte}</td>
          <td>${fmtCompact(r.gamma_oi)}</td><td>${fmt(r.share_pct, 1)}%</td>
          <td>${fmtCompact(r.open_interest)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel span2">
      <h2>${hg('GEX — dealer gamma exposure')}</h2>
      <p class="sub">Net ${(gex.totals || {}).net_gex >= 0 ? '+' : ''}$${fmtCompact((gex.totals || {}).net_gex)} of dealer delta per 1% move.
        Regime: <strong>${esc((gex.regime || {}).state || '')}</strong>.
        ${(gex.regime || {}).flip_point ? `Gamma flip at <strong>${fmt(gex.regime.flip_point, 2)}</strong> (${fmtPct((gex.regime || {}).flip_distance_pct, 2)} away).` : ''}</p>
      <div class="callout info">${gloss((gex.regime || {}).note || '')}<br><br><strong>For swings:</strong> ${gloss((gex.regime || {}).swing_implication || '')}</div>

      <div class="grid c2" style="margin-top:12px">
        <div>
          <h3>${hg('Net GEX by strike')}</h3>
          <div id="legend-gex"></div>
          <div id="chart-gex"></div>
        </div>
        <div>
          <h3>${hg('Gamma profile across spot')}</h3>
          <p class="sub">Where the curve crosses zero is the flip point — above it dealers dampen moves, below it they amplify them.</p>
          <div id="chart-gamma-profile"></div>
          <h3>${hg('Key levels')}</h3>
          <table class="data">
            <thead><tr><th>Level</th><th>Strike ($)</th><th>Distance</th><th>Exposure</th></tr></thead>
            <tbody>
              ${(gex.levels || {}).call_wall ? `<tr><td class="name">${gloss('Call wall')} (resistance)</td><td>${fmt(gex.levels.call_wall.strike, 1)}</td><td class="${signClass(gex.levels.call_wall.distance_pct)}">${fmtPct(gex.levels.call_wall.distance_pct, 1)}</td><td>$${fmtCompact(gex.levels.call_wall.gex)}</td></tr>` : ''}
              ${(gex.levels || {}).put_wall ? `<tr><td class="name">${gloss('Put wall')} (support)</td><td>${fmt(gex.levels.put_wall.strike, 1)}</td><td class="${signClass(gex.levels.put_wall.distance_pct)}">${fmtPct(gex.levels.put_wall.distance_pct, 1)}</td><td>$${fmtCompact(gex.levels.put_wall.gex)}</td></tr>` : ''}
              ${(gex.levels || {}).gamma_pin ? `<tr><td class="name">${gloss('Gamma pin')} (max |GEX|)</td><td>${fmt(gex.levels.gamma_pin.strike, 1)}</td><td class="${signClass(gex.levels.gamma_pin.distance_pct)}">${fmtPct(gex.levels.gamma_pin.distance_pct, 1)}</td><td>$${fmtCompact(gex.levels.gamma_pin.abs_gex)}</td></tr>` : ''}
              ${(gex.levels || {}).max_oi_strike ? `<tr><td class="name">Max open interest</td><td>${fmt(gex.levels.max_oi_strike.strike, 1)}</td><td>—</td><td>${fmtCompact(gex.levels.max_oi_strike.total_oi)} contracts</td></tr>` : ''}
            </tbody>
          </table>
        </div>
      </div>
      <p class="caveat">Sign convention: ${esc(gex.assumption || '')}. This is the standard retail assumption and it is sometimes wrong.</p>
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Call vs put flow')}</h2>
      <p class="sub">${toneChip(flow.stance)} score ${flow.flow_score > 0 ? '+' : ''}${fmt(flow.flow_score, 0)}</p>
      ${kv([
    ['Call volume', fmtCompact((flow.volume || {}).calls)],
    ['Put volume', fmtCompact((flow.volume || {}).puts)],
    ['Put/call volume ratio', fmt((flow.volume || {}).put_call_ratio, 2)],
    ['Put/call OI ratio', fmt((flow.open_interest || {}).put_call_ratio, 2)],
    ['Call premium', '$' + fmtCompact((flow.premium || {}).calls)],
    ['Put premium', '$' + fmtCompact((flow.premium || {}).puts)],
    ['Call share of premium', `${fmt((flow.premium || {}).call_share_pct, 1)}%`],
    ['New-position premium (calls)', '$' + fmtCompact((flow.new_positions || {}).call_premium)],
    ['New-position premium (puts)', '$' + fmtCompact((flow.new_positions || {}).put_premium)],
    ['OTM put IV − call IV', `${fmt((flow.iv_skew || {}).put_minus_call_vol_pts, 1)} vol pts`],
  ])}
      <ul class="reasons">${(flow.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>
      <p class="caveat">${esc(flow.method || '')}</p>
    </div>

    <div class="panel">
      <h2>${hg('Net premium by strike')}</h2>
      <p class="sub">Calls positive, puts negative — where today's money actually went.</p>
      <div id="legend-flow"></div>
      <div id="chart-flow"></div>
      <h3>${hg('Notable contracts')}</h3>
      <div class="scroll-y">
      <table class="data">
        <thead><tr><th>Contract</th><th>Type</th><th>Strike ($)</th><th>Days left</th><th>Volume today</th><th>Open interest</th><th>Volume ÷ OI</th><th>Premium ($)</th><th>Implied vol</th></tr></thead>
        <tbody>${(flow.unusual || []).map((r) => `<tr>
          <td class="name">${esc(r.moneyness)}${r.is_new_position ? ' · new' : ''}</td>
          <td class="name" style="color:${r.type === 'CALL' ? 'var(--pos)' : 'var(--neg)'}">${esc(r.type)}</td>
          <td>${fmt(r.strike, 1)}</td><td>${fmt(r.dte, 0)}</td>
          <td>${fmtCompact(r.volume)}</td><td>${fmtCompact(r.open_interest)}</td>
          <td>${fmt(r.vol_oi_ratio, 1)}</td><td>$${fmtCompact(r.premium)}</td>
          <td>${fmt((r.iv || 0) * 100, 1)}%</td>
        </tr>`).join('') || '<tr><td colspan="9" style="color:var(--ink-muted)">No unusual activity above the volume and premium thresholds.</td></tr>'}</tbody>
      </table></div>
    </div>
  </div>

  <div class="panel" style="margin-bottom:14px">
    <h2>${hg('Buy calls / puts')}</h2>
    <p class="sub">Naked directional options — quick-glance card in the same format as the strategies below.
      For a fully ranked set of strikes scored against a projected target, see the Strike &amp; Entry
      Recommendation panel above. Strikes and premiums are live from the chain, filtered for liquidity.
      Not recommendations — the sizing decision is yours.</p>
    ${(d.naked_ideas || []).length
    ? (d.naked_ideas || []).map(renderIdea).join('')
    : '<div class="callout">No naked directional idea — the composite read is neutral, so buying a call or put outright has no edge. See the strategies below for range-bound or volatility-driven setups instead.</div>'}
  </div>

  <div class="panel" style="margin-bottom:14px">
    <h2>${hg('Options strategies')}</h2>
    <p class="sub">Multi-leg and cross-underlying structures — spreads, condors, straddles/strangles, and sector
      pair trades — matched to the stance, the gamma regime, and (where relevant) implied-vol pricing.</p>
    ${(d.strategy_ideas || []).length
    ? (d.strategy_ideas || []).map(renderIdea).join('')
    : '<div class="callout">No strategy generated — the chain lacked liquid contracts at the target deltas.</div>'}
  </div>
  `}

  ${renderCompany(d.company)}

  <div class="panel">
    <h2>${hg('News & catalysts')}</h2>
    <p class="sub">${toneChip(news.overall_tone)} net sentiment ${fmt(news.net_sentiment, 2)} across ${news.article_count || 0} headlines
      ${news.earnings_date ? `· earnings ${esc(news.earnings_date)}${news.days_to_earnings !== null ? ` (${news.days_to_earnings}d)` : ''}` : ''}</p>
    ${news.earnings_warning ? `<div class="callout">${esc(news.earnings_warning)}</div>` : ''}
    ${(news.catalyst_summary || []).length ? `<h3>${hg('Catalyst types detected')}</h3>
      <div class="legend">${news.catalyst_summary.map((c) => `<span class="chip neutral"><span class="dot"></span>${esc(cap(c.type))} ×${c.mentions}</span>`).join('')}</div>` : ''}
    <h3>${hg('Headlines')}</h3>
    <div class="scroll-y">
      ${(news.articles || []).map((a) => `<div style="padding:8px 0;border-bottom:1px solid var(--grid)">
        <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">
          ${toneChip(a.tone)}
          <a href="${esc(a.url)}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none;flex:1;min-width:240px">${esc(a.title)}</a>
          <span style="color:var(--ink-muted);font-size:11.5px">${esc(a.publisher)}${a.age_hours !== null ? ` · ${fmt(a.age_hours, 0)}h ago` : ''}</span>
        </div>
        ${a.summary ? `<div style="color:var(--ink-2);font-size:12.5px;margin-top:3px">${esc(a.summary.slice(0, 220))}</div>` : ''}
        ${(a.catalysts || []).length ? `<div style="margin-top:4px">${a.catalysts.map((c) => `<span class="chip neutral" style="margin-right:4px"><span class="dot"></span>${esc(cap(c.type))}</span>`).join('')}</div>` : ''}
      </div>`).join('') || '<div style="color:var(--ink-muted)">No headlines returned for this ticker.</div>'}
    </div>
    <p class="caveat">${esc(news.method || '')}. Use “Deep research” in the assistant for a live, sourced brief.</p>
  </div>
  `;

  views.swing.innerHTML = html;

  // ---- charts
  views.swing.querySelectorAll('[data-bar]').forEach((host) => {
    host.appendChild(inlineBar(Number(host.dataset.bar), maxComp, 70, 9));
  });

  if (ps.close && ps.close.length) {
    // Drop near-duplicate labels (levels within 1.2% are the same shelf as far
    // as the eye is concerned); lineChart handles the remaining pixel-level
    // collisions itself, since only it knows how tall the chart ended up.
    const labeledPrices = [];
    const claimLabel = (price) => {
      if (!isFinite(price)) return false;
      if (labeledPrices.some((p) => Math.abs(price / p - 1.0) * 100.0 < 1.2)) return false;
      labeledPrices.push(price);
      return true;
    };
    // The whole 0-100% retracement grid between the swing low and the swing high,
    // plus the extensions above it. The extensions used to be dropped, which meant
    // a stock at its highs showed no ceiling at all — those projected levels are
    // the only resistance that exists once price has cleared every historical
    // pivot, so they're drawn and labelled as projections.
    // Every ratio gets a line; only some get text. Labelling all nine turned the
    // right-hand side into a wall of type — the lines themselves plus the table
    // below already carry the full grid.
    let fibResistanceLabels = 0;
    const fibLabelBudget = (l) => {
      if (l.is_golden || l.role === 'target') return true;      // always worth naming
      if (l.role !== 'resistance') return false;
      // The two nearest ceilings, which is what a reader actually trades against.
      if (fibResistanceLabels >= 2) return false;
      fibResistanceLabels += 1;
      return true;
    };
    const fibRefs = !showFib ? [] : ((t.fibonacci || {}).levels || [])
      .filter((l) => l.price !== null)
      // Nearest-first, so the budget above spends itself on the closest ceilings.
      .sort((a, b) => Math.abs(a.price - (t.spot || 0)) - Math.abs(b.price - (t.spot || 0)))
      .map((l) => ({
        value: l.price,
        label: fibLabelBudget(l) && claimLabel(l.price)
          ? `Fib ${l.label}${l.role === 'target' ? ' projected' : ''}${
            l.role === 'resistance' ? ' resistance' : ''} · ${usd(l.price)}` : '',
        color: C.refFib,
        // Same dash as support/resistance — colour carries the distinction, weight
        // doesn't. Projections keep a looser dash because they haven't happened yet.
        pattern: l.role === 'target' ? '2 5' : '6 4',
        emphasis: !!l.is_golden,
        // Non-golden ratios are drawn dimmer via the shared opacity rule rather
        // than in structural grey, which made them read as gridlines.
        dim: !l.is_golden && l.role !== 'target' && l.role !== 'resistance',
      }));
    // Touch count first, so the strongest levels win a label when space is tight.
    // Spelled out with the price: "S (3x)" told you nothing about where the level
    // actually was, or what S stood for.
    const srLevels = srComputed.slice();
    // When price is at or near its highs, every detected pivot sits below it and
    // the chart shows nothing but support. The 52-week and all-time highs are the
    // only real ceilings left, so they're added as resistance rather than leaving
    // the reader to conclude there is none.
    const hasResistance = srLevels.some((l) => l.price > (t.spot || 0));
    const fibAnchorHigh = (t.fibonacci || {}).anchor_high;
    const ceilingRefs = (!showSR || hasResistance) ? [] : [
      { price: q.fifty_two_high, name: '52-week high' },
    ].filter((c) => c.price && c.price > (t.spot || 0)
      // Don't double-draw a level another family already covers: the 52-week high
      // is often the same print as the Fibonacci swing high.
      && !srLevels.some((l) => Math.abs(l.price / c.price - 1) < 0.005)
      && !(showFib && fibAnchorHigh && Math.abs(fibAnchorHigh / c.price - 1) < 0.005))
      .map((c) => ({
        value: c.price,
        label: claimLabel(c.price) ? `${c.name} · ${usd(c.price)} — nothing above this` : '',
        color: C.refSR,
        pattern: '6 4',
      }));
    let srLabelled = 0;
    const srRefs = (!showSR ? [] : srLevels).map((l) => {
      const shouldLabel = srLabelled < 3 && claimLabel(l.price);
      if (shouldLabel) srLabelled += 1;
      const role = l.role === 'support' ? 'Support' : 'Resistance';
      return {
        value: l.price,
        label: shouldLabel ? `${role} ${usd(l.price)} · strength ${fmt(l.strength, 0)}` : '',
        color: C.refSR,
        pattern: '6 4',
        emphasis: srLabelled === 1,
      };
    });
    const candleMode = chartMode === 'candle' && ps.open && ps.high && ps.low;
    // Candles own green and red; in candle mode the averages take hues that
    // can't be mistaken for a bar's direction.
    // Candle mode reassigns the averages because the candles themselves own the
    // aqua/red pair. The mid average used to take violet, which sat ΔE 7 from the
    // Fibonacci lines — indistinguishable, and worse under colour-vision
    // simulation. Orange is free in candle mode, so it takes that instead.
    const maColors = candleMode
      ? { fast: C.s1, mid: C.s2, slow: C.s4 }
      : { fast: C.s2, mid: C.s3, slow: C.s4 };

    mount('legend-price', legend([
      ...(candleMode
        ? [{ name: ps.weekly ? 'Up week' : 'Up day', color: C.s3 },
          { name: ps.weekly ? 'Down week' : 'Down day', color: C.s8 }]
        : [{ name: 'Close', color: C.s1 }]),
      ...(ps.weekly
        ? [{ name: '20-week SMA', color: maColors.fast },
          { name: '50-week SMA', color: maColors.mid }]
        : [{ name: '20-day SMA', color: maColors.fast },
          { name: '50-day SMA', color: maColors.mid },
          { name: '200-day SMA', color: maColors.slow }]),
      showFib ? { name: 'Fibonacci level', color: C.refFib, dash: true } : null,
      showSR ? { name: 'Support / resistance', color: C.refSR, dash: true } : null,
    ].filter(Boolean)));
    mount('chart-price', (w) => lineChart({
      width: w,
      height: 420,
      labels: ps.dates || [],
      // In candle mode the close series is kept but not stroked: the hover
      // crosshair and tooltip read from the series list, so dropping it would
      // silently disable them.
      series: [
        { name: 'Close', values: ps.close, color: C.s1, hidden: candleMode, fill: !candleMode },
        { name: ps.weekly ? '20-week SMA' : '20-day SMA', values: ps.sma20 || [], color: maColors.fast, width: 1.5, marker: false },
        { name: ps.weekly ? '50-week SMA' : '50-day SMA', values: ps.sma50 || [], color: maColors.mid, width: 1.5, marker: false },
        { name: '200-day SMA', values: ps.sma200 || [], color: maColors.slow, width: 1.5, marker: false },
      ],
      candles: candleMode
        ? { open: ps.open, high: ps.high, low: ps.low, close: ps.close }
        : null,
      refLines: [...fibRefs, ...srRefs, ...ceilingRefs],
      refLineFit: 'clip',
      yFormat: (x) => fmt(x, 0),
      valueFormat: (x) => fmt(x, 2),
    }));

    // 'clip' drops levels outside the plotted price range — without that, a level
    // 25% away compresses the actual price action into a band in the middle. But
    // a silently missing line looks like a bug, so the count is reported.
    // Mirrors lineChart's own rule (data span plus 16% slack) so the count can't
    // disagree with what actually got drawn.
    const priced = (ps.close || []).filter((v) => v !== null && isFinite(v));
    const dLo = Math.min(...priced);
    const dHi = Math.max(...priced);
    const slack = (dHi - dLo) * 0.16;
    const offScale = [...fibRefs, ...srRefs, ...ceilingRefs].filter(
      (r) => isFinite(r.value) && (r.value < dLo - slack || r.value > dHi + slack));
    const note = document.getElementById('chart-price-note');
    if (note) {
      const one = offScale.length === 1;
      note.innerHTML = offScale.length
        ? `<p class="caveat" style="margin:6px 0 0">${offScale.length} level${one ? '' : 's'} ${
          one ? 'sits' : 'sit'} too far outside the price range on screen to draw, so ${
          one ? "it isn't" : "they aren't"} shown here — ${one ? 'it is' : 'they are'} still
          listed in the tables below. Widen the timeframe to bring ${
          one ? 'it' : 'them'} into view.</p>`
        : '';
    }
  }

  if ((t.rsi || {}).series) {
    // Same window as the MACD beside it. Two oscillators side by side read as one
    // pair sharing a time axis; zooming only one made that read wrong.
    // Untailed: both the RSI and its 9-period average are computed over all the
    // history available, and only then cut to the window. Slicing first meant the
    // averages warmed up *inside* the visible range and the signal line began
    // nine bars in — the same gap the RSI line itself used to have.
    const rsiSource = ps.weekly
      ? rsiSeries((weeklyAll || {}).close || [], 14)
      : (t.rsi.series || []);
    const rsiSignalSource = smaSeries(rsiSource, RSI_SIGNAL_PERIOD);
    const rsiZoom = Math.min(MACD_WINDOW, ps.shown_bars || MACD_WINDOW, rsiSource.length);
    const rsiVals = tailTo(rsiSource, rsiZoom);
    // Signal line: a 9-period average of RSI itself, the same idea as the MACD's
    // signal. RSI crossing its own average is the earlier, noisier read on a
    // momentum turn — it usually leads the MACD cross, which is why both panels
    // are worth having side by side.
    const rsiSignal = tailTo(rsiSignalSource, rsiZoom);
    const rsiCross = lastMacdCross(rsiVals, rsiSignal);
    const rsiDates = tailTo(ps.dates || [], rsiZoom);

    mount('legend-rsi', legend([
      { name: ps.weekly ? 'RSI(14) weekly' : 'RSI(14)', color: C.s1 },
      { name: `Signal (${RSI_SIGNAL_PERIOD}-period average)`, color: C.s4 },
      { name: 'Overbought / oversold', color: C.refSR, dash: true },
      { name: 'Midline 50', color: C.muted, dash: true },
      rsiCross ? { name: rsiCross.bullish ? 'Bullish cross' : 'Bearish cross',
        color: rsiCross.bullish ? C.good : C.critical } : null,
    ].filter(Boolean)));

    mount('chart-rsi', (w) => lineChart({
      width: w,
      height: 210,
      labels: rsiDates,
      // On weekly, recompute from weekly closes — a 14-week RSI is a genuinely
      // slower measure than the 14-day one, not the same line resampled.
      series: [
        { name: ps.weekly ? 'RSI(14) weekly' : 'RSI(14)', values: rsiVals, color: C.s1 },
        { name: 'Signal', values: rsiSignal, color: C.s4, width: 1.5, marker: false },
      ],
      // RSI is bounded 0-100, so the axis is fixed. Auto-scaling it put the
      // overbought band at the very top edge and the oversold band in dead space,
      // which made "how close to a band" impossible to judge. 10-90 keeps both
      // bands comfortably inside with room for their labels.
      yDomain: [10, 90],
      // Unlabelled on purpose: the y-axis already reads 30/50/70 and the sub-line
      // above says what they mean, so the text was duplication that collided with
      // the very line it was annotating.
      refLines: [
        { value: 70, label: '', color: C.refSR, emphasis: true },
        // The midline was drawn in the gridline colour, which is deliberately
        // near-invisible — 1.24:1 on dark, 1.29:1 on light — so the one level that
        // says "bullish above, bearish below" couldn't be seen in either theme.
        // ink-muted is the single ink the palette holds constant across both
        // surfaces (4.85:1 dark, 3.50:1 light), so one value covers each mode
        // without a theme branch, and being neutral it stays subordinate to the
        // RSI line and the two bands.
        { value: 50, label: '', color: C.muted },
        { value: 30, label: '', color: C.refSR, emphasis: true },
      ],
      vMarkers: rsiCross ? [{
        index: rsiCross.index,
        value: rsiVals[rsiCross.index],
        color: rsiCross.bullish ? C.good : C.critical,
        label: `${rsiCross.bullish ? 'Bullish' : 'Bearish'} cross${rsiCross.barsAgo
          ? ` · ${rsiCross.barsAgo} ${ps.weekly ? 'week' : 'day'}${
            rsiCross.barsAgo === 1 ? '' : 's'} ago` : ' · latest bar'}`,
      }] : [],
      yFormat: (x) => fmt(x, 0),
    }));

    const rsiNote = document.getElementById('rsi-cross-note');
    if (rsiNote) {
      rsiNote.innerHTML = macdCrossSentence(
        rsiCross, { macd: rsiVals, signal: rsiSignal }, rsiDates, ps.weekly, rsiZoom, 'RSI',
      );
    }
  }

  if ((t.macd || {}).series) {
    const full = ps.weekly
      ? (() => {
        const m = macdSeries(weeklyAll.close);
        return {
          macd: tailTo(m.macd, ps.shown_bars),
          signal: tailTo(m.signal, ps.shown_bars),
          hist: tailTo(m.hist, ps.shown_bars),
        };
      })()
      : {
        macd: tailTo(t.macd.series.macd, ps.shown_bars),
        signal: tailTo(t.macd.series.signal, ps.shown_bars),
        hist: tailTo(t.macd.series.hist, ps.shown_bars),
      };
    // Zoomed to its own window rather than the price chart's, so the two lines
    // are far enough apart to see which side of the other they're on.
    const zoom = Math.min(MACD_WINDOW, full.macd.length);
    const wk = {
      macd: tailTo(full.macd, zoom),
      signal: tailTo(full.signal, zoom),
      hist: tailTo(full.hist, zoom),
    };
    const macdDates = tailTo(ps.dates || [], zoom);
    const cross = lastMacdCross(wk.macd, wk.signal);

    mount('legend-macd', legend([
      { name: 'MACD', color: C.s1 },
      { name: 'Signal', color: C.s4 },
      { name: 'Histogram', color: C.pos, boxed: true },
      cross ? { name: cross.bullish ? 'Bullish cross' : 'Bearish cross',
        color: cross.bullish ? C.good : C.critical } : null,
    ].filter(Boolean)));
    mount('chart-macd', (w) => macdChart(
      wk.macd, wk.signal, wk.hist, macdDates, w,
      { cross, unit: ps.weekly ? 'week' : 'day' },
    ));

    const note = document.getElementById('macd-cross-note');
    if (note) note.innerHTML = macdCrossSentence(cross, wk, macdDates, ps.weekly, zoom);
  }

  if ((gex.by_strike || []).length) {
    const rows = gex.by_strike.slice().sort((a, b) => b.strike - a.strike);
    const spotIdx = rows.findIndex((r) => r.strike < d.quote.price);
    mount('legend-gex', legend([
      { name: 'Positive GEX (call-dominated)', color: C.pos, boxed: true },
      { name: 'Negative GEX (put-dominated)', color: C.neg, boxed: true },
    ], true));
    mount('chart-gex', (w) => divergingBars({
      width: w,
      rows: rows.map((r) => ({
        label: fmt(r.strike, 0),
        value: r.net_gex,
        detail: [
          ['Net GEX', '$' + fmtCompact(r.net_gex)],
          ['Call GEX', '$' + fmtCompact(r.call_gex)],
          ['Put GEX', '$' + fmtCompact(r.put_gex)],
          ['Call OI', fmtCompact(r.call_oi)],
          ['Put OI', fmtCompact(r.put_oi)],
          ['Call / put volume', `${fmtCompact(r.call_vol)} / ${fmtCompact(r.put_vol)}`],
        ],
      })),
      markerRow: spotIdx >= 0 ? spotIdx : null,
      markerLabel: `spot ${fmt(d.quote.price, 0)}`,
      format: (x) => '$' + fmtCompact(x),
      axisLabel: 'dealer $ delta per 1% move',
    }));
  }

  const prof = (gex.profile || {});
  if (prof.spots && prof.net_gex) {
    mount('chart-gamma-profile', (w) => lineChart({
      width: w,
      height: 200,
      labels: prof.spots.map((x) => fmt(x, 0)),
      series: [{ name: 'Net GEX', values: prof.net_gex, color: C.s1, fill: true }],
      refLines: [
        prof.flip_point ? { value: 0, label: `flip ≈ ${fmt(prof.flip_point, 2)}`, color: C.warn } : { value: 0, label: '', color: C.baseline },
      ],
      zeroLine: true,
      yFormat: (x) => '$' + fmtCompact(x),
    }));
  }

  if ((flow.by_strike || []).length) {
    const rows = flow.by_strike.slice().sort((a, b) => b.strike - a.strike);
    mount('legend-flow', legend([
      { name: 'Net call premium', color: C.pos, boxed: true },
      { name: 'Net put premium', color: C.neg, boxed: true },
    ], true));
    mount('chart-flow', (w) => divergingBars({
      width: w,
      rows: rows.map((r) => ({
        label: fmt(r.strike, 0),
        value: r.net_premium,
        detail: [
          ['Net premium', '$' + fmtCompact(r.net_premium)],
          ['Call premium', '$' + fmtCompact(r.call_premium)],
          ['Put premium', '$' + fmtCompact(r.put_premium)],
          ['Call / put volume', `${fmtCompact(r.call_volume)} / ${fmtCompact(r.put_volume)}`],
        ],
      })),
      format: (x) => '$' + fmtCompact(x),
      axisLabel: 'net premium traded today',
    }));
  }
}

/* --------------------------------------------------------- entry plan panel */

/** Which way the Fibonacci grid was drawn, and what that makes the levels.
 *
 * "Drawn for the bearish leg" left the reader to work out the order of the two
 * anchors and, more importantly, whether the lines are floors or ceilings. A
 * grid measured down from a high produces resistance above; one measured up from
 * a low produces support below. That's the whole point of knowing the direction.
 */
function fibDirectionSentence(t) {
  const fib = t.fibonacci || {};
  const sw = t.swing_points || {};
  const bearish = (fib.direction || '').toLowerCase() === 'bearish';
  const hi = usd(fib.anchor_high);
  const lo = usd(fib.anchor_low);
  const hiDate = sw.swing_high_date ? ` (${esc(sw.swing_high_date)})` : '';
  const loDate = sw.swing_low_date ? ` (${esc(sw.swing_low_date)})` : '';
  const pct = fmt(fib.retracement_pct, 0);

  if (bearish) {
    return `<strong>bearish retracement</strong>, measured swing high → swing low:
      down from ${hi}${hiDate} to ${lo}${loDate}. Price has since recovered
      ${pct}% of that fall, so these levels sit <strong>above</strong> price and act as
      resistance — places a bounce has a reason to stall.`;
  }
  return `<strong>bullish retracement</strong>, measured swing low → swing high:
    up from ${lo}${loDate} to ${hi}${hiDate}. Price has since given back
    ${pct}% of that rise, so these levels sit <strong>below</strong> price and act as
    support — places a pullback has a reason to hold.`;
}

function renderEntryPlan(p) {
  if (!p) return '';

  if (!p.actionable) {
    return `<div class="panel" style="margin-bottom:14px">
      <h2>${hg('Strike & entry recommendation')}</h2>
      <p class="sub">${esc(p.headline || '')}</p>
      ${(p.reasoning || []).map((r) => `<div class="callout">${gloss(r)}</div>`).join('')}
      ${(p.waiting_for || []).filter(Boolean).length ? `<h3>${hg('What would create a trade')}</h3>
        <table class="data"><thead><tr><th>Trigger</th><th>Result</th></tr></thead><tbody>
        ${(p.waiting_for || []).filter(Boolean).map((w) => `<tr>
          <td class="name">${esc(w.condition)}</td><td class="name" style="color:var(--ink-2)">${esc(w.then)}</td>
        </tr>`).join('')}</tbody></table>` : ''}
      ${(p.iv_context || {}).available ? `<h3>${hg('Volatility context')}</h3>
        <p class="sub">${gloss(p.iv_context.guidance || '')}</p>` : ''}
    </div>`;
  }

  const r = p.recommended || {};
  const t = p.target || {};
  const o = p.order_guidance || {};
  const risk = p.risk || {};
  const iv = p.iv_context || {};

  return `<div class="panel" style="margin-bottom:14px">
    <h2>${hg('Strike & entry recommendation')}</h2>
    <p class="sub">Derived from the ${esc(p.stance)} read at ${esc(p.conviction)} conviction. Candidates are repriced with
      Black-Scholes at the projected target, so the ranking reflects payoff — not just a convenient delta.</p>

    <div class="callout info" style="font-size:14px;border-left-color:var(--good)">
      <strong>${esc(p.headline)}</strong>
    </div>

    <div class="grid c4" style="margin:14px 0">
      ${tile('Contract', `${strikeLabel(r.strike)} ${p.direction === 'long' ? 'call' : 'put'}`,
    `Expires ${esc(r.expiry || '')} · ${r.dte || 0} days left · ${
      r.moneyness === 'ITM' ? 'already in the money' : 'not yet in the money'}`)}
      ${tile('Limit price', usd(o.limit_price), `Per share — never pay above ${
    usd(o.never_pay_more_than)}`)}
      ${tile('Cost per contract', usd(r.capital_per_contract, 0),
    `What one contract costs · the stock must clear ${usd(r.breakeven)} to break even`)}
      ${tile('If the target is hit', fmtPct(r.return_at_target_pct, 0),
    `Return on the premium if the stock reaches ${usd(t.target_price)}, roughly ${
      t.estimated_calendar_days || '?'} days out`, signClass(r.return_at_target_pct))}
    </div>

    <div class="grid c2">
      <div>
        <h3>${hg('Where to enter')}</h3>
        ${(p.entry_options || []).map((e) => `<div style="padding:8px 0;border-bottom:1px solid var(--grid)">
          <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">
            <strong style="font-size:13px">${esc(e.style)}</strong>
            ${e.zone ? `<span class="chip neutral"><span class="dot"></span>${usd(e.zone[0])} – ${usd(e.zone[1])}</span>` : ''}
          </div>
          <div style="color:var(--ink-2);font-size:12.5px;margin-top:3px">${gloss(e.detail)}</div>
          <div style="color:var(--ink-muted);font-size:12px;margin-top:2px">Confirmation: ${gloss(e.confirmation)}</div>
        </div>`).join('')}

        <h3>${hg('Entry zone levels')}</h3>
        <table class="data">
          <thead><tr><th>Level</th><th>Price ($)</th></tr></thead>
          <tbody>${((p.entry_zone || {}).levels || []).map((z) => `<tr>
            <td class="name">${esc(cap(z.label))}</td><td>${usd(z.price)}</td>
          </tr>`).join('') || '<tr><td colspan="2" style="color:var(--ink-muted)">No structural levels below spot.</td></tr>'}</tbody>
        </table>
      </div>

      <div>
        <h3>${hg('Target & risk')}</h3>
        ${kv([
    ['Price target', `${usd(t.target_price)} — a ${fmtPct(t.move_required_pct, 1)} move from here`],
    ['Where that target comes from', esc(t.target_source || '')],
    ['Expected time to get there', `${t.estimated_trading_days || '?'} trading days (about ${
      t.estimated_calendar_days || '?'} calendar days)`],
    ['Stop on the stock', `${usd(risk.underlying_stop)} — exit if the stock closes past this`],
    ['How that stop was set', esc(risk.stop_basis || '')],
    ['Average daily range (14 days)', `${usd(t.atr14)} a day`],
  ])}
        <div class="caveat">${gloss(risk.invalidation || '')} ${gloss(risk.position_sizing || '')}</div>

        <h3>${hg('Volatility context')}</h3>
        ${kv([
    ['Implied volatility, at the money', fmt(iv.atm_iv_pct, 1) + '% a year — what options are pricing in'],
    ['Realized volatility, last 20 days', fmt(iv.realised_vol_20d_pct, 1) + '% a year — what the stock actually did'],
    ['Implied ÷ realized', fmt(iv.iv_to_realised_ratio, 2) + 'x — above 1.0 means options look expensive'],
    ['Read', esc(iv.verdict || '')],
    iv.iv_rank_proxy !== null && iv.iv_rank_proxy !== undefined
      ? ['IV rank (proxy)', fmt(iv.iv_rank_proxy, 0) + ' out of 100 — where today sits in the past year'] : null,
    iv.realised_vol_rank_pct !== null && iv.realised_vol_rank_pct !== undefined
      ? ['Realized vol rank', fmt(iv.realised_vol_rank_pct, 0) + ' out of 100 across the last 52 weeks'] : null,
    iv.realised_vol_percentile_pct !== null && iv.realised_vol_percentile_pct !== undefined
      ? ['Realized vol percentile', fmt(iv.realised_vol_percentile_pct, 0) + '% of the last 52 weeks were calmer'] : null,
    iv.realised_vol_52w_low !== null && iv.realised_vol_52w_low !== undefined
      ? ['Realized vol range, 52 weeks', `${fmt(iv.realised_vol_52w_low, 1)}% to ${fmt(iv.realised_vol_52w_high, 1)}%`] : null,
  ])}
        <div class="callout ${iv.verdict === 'rich' ? '' : 'info'}">${gloss(iv.guidance || '')}</div>
        ${iv.rank_guidance ? `<div class="callout info">${gloss(iv.rank_guidance)}</div>` : ''}
        ${iv.term_structure ? `<div class="caveat">${gloss(iv.term_structure)}</div>` : ''}
        ${iv.iv_rank_proxy !== null && iv.iv_rank_proxy !== undefined ? `<p class="caveat">${gloss(iv.method || '')}</p>` : ''}
      </div>
    </div>

    <h3>${hg('Candidate strikes, ranked')}</h3>
    <p class="sub">Every column after the greeks is a repriced scenario at ${usd(t.target_price)} in about
      ${t.estimated_calendar_days || '?'} days. “Flat” is what you lose if the move simply doesn't happen — the most
      common outcome, and the reason deep-OTM contracts score badly here.</p>
    <table class="data">
      <thead><tr>
        <th>#</th><th>Strike ($)</th><th>Expiry</th><th>Days left</th><th>Mid ($)</th><th>Spread</th><th>Delta</th><th>Theta ($/day)</th>
        <th>Breakeven</th><th>At target</th><th>IV −20%</th><th>If flat</th><th>Half against</th><th>OI</th>
      </tr></thead>
      <tbody>${(p.candidates || []).map((c) => `<tr${c.rank === 1 ? ' style="background:var(--surface-2)"' : ''}>
        <td>${c.rank}${c.rank === 1 ? ' ★' : ''}</td>
        <td class="name">${fmt(c.strike, 1)} <span style="color:var(--ink-muted)">${esc(c.moneyness)}</span></td>
        <td class="name">${esc(c.expiry)}</td>
        <td>${c.dte}</td>
        <td>${fmt(c.entry_mid, 2)}</td>
        <td class="${(c.spread_pct || 0) > 5 ? 'down' : ''}">${fmt(c.spread_pct, 1)}%</td>
        <td>${fmt(c.delta, 3)}</td>
        <td class="down">${fmt(c.theta_per_day, 3)}</td>
        <td>${fmt(c.breakeven, 2)}</td>
        <td class="up">${fmtPct(c.return_at_target_pct, 0)}</td>
        <td class="${signClass(c.return_if_iv_drops_20pct)}">${fmtPct(c.return_if_iv_drops_20pct, 0)}</td>
        <td class="${signClass(c.return_if_flat_pct)}">${fmtPct(c.return_if_flat_pct, 0)}</td>
        <td class="${signClass(c.return_if_half_against_pct)}">${fmtPct(c.return_if_half_against_pct, 0)}</td>
        <td>${fmtCompact(c.open_interest)}</td>
      </tr>`).join('')}</tbody>
    </table>

    ${(p.warnings || []).map((w) => `<div class="callout">${gloss(w)}</div>`).join('')}
    ${o.note ? `<div class="caveat">Order handling: ${esc(o.note)}</div>` : ''}
    <div class="caveat">${(p.assumptions || []).map(esc).join(' ')}</div>
  </div>`;
}

/* ------------------------------------------------------------ company panel */

function renderCompany(co) {
  if (!co || co.error) {
    return co && co.error ? `<div class="panel" style="margin-bottom:14px"><h2>${hg('Company data')}</h2>
      <div class="callout bad">${esc(co.error)}</div></div>` : '';
  }
  const si = co.short_interest || {};
  const fn = co.financials || {};
  const eh = co.earnings_history || {};
  const ow = co.ownership || {};
  const ap = fn.annual_periods || [];
  const an = fn.annual || {};

  const finRow = (label, values, money) => `<tr>
    <td class="name">${esc(label)}</td>
    ${(ap || []).map((_, i) => `<td>${values && values[i] !== null && values[i] !== undefined
    ? (money ? '$' + fmtCompact(values[i]) : fmt(values[i], 2)) : '—'}</td>`).join('')}
  </tr>`;

  return `
  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Short interest')}</h2>
      ${si.available ? `
        <p class="sub">Squeeze potential: <strong>${esc(si.squeeze_potential)}</strong>${si.settlement_date ? ` · settled ${esc(si.settlement_date)}` : ''}</p>
        <div class="grid c3" style="margin-bottom:10px">
          ${tile('% of float short', si.percent_of_float !== null ? fmt(si.percent_of_float * 100, 2) + '%' : '—')}
          ${tile('Days to cover', fmt(si.days_to_cover, 2))}
          ${tile('vs prior period', fmtPct(si.change_vs_prior_pct, 1), null, signClass(si.change_vs_prior_pct))}
        </div>
        ${kv([
    ['Shares short', fmtCompact(si.shares_short)],
    ['Prior settlement', fmtCompact(si.shares_short_prior)],
    ['Float', fmtCompact(si.float_shares)],
  ])}
        <ul class="reasons">${(si.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>
        <p class="caveat">${esc(si.caveat || '')}</p>`
    : '<div class="callout">No short-interest data for this security.</div>'}
    </div>

    <div class="panel">
      <h2>${hg('Earnings track record')}</h2>
      ${eh.available ? `
        <p class="sub">Beat consensus in ${eh.beat_count} of the last ${eh.sample_size} quarters
          (${fmt(eh.beat_rate_pct, 0)}%), average surprise ${fmtPct(eh.avg_surprise_pct, 1)}.</p>
        <table class="data">
          <thead><tr><th>Quarter</th><th>EPS est.</th><th>EPS actual</th><th>Surprise</th></tr></thead>
          <tbody>${(eh.quarters || []).map((q) => `<tr>
            <td class="name">${esc(q.date)}</td>
            <td>${fmt(q.eps_estimate, 2)}</td>
            <td>${fmt(q.eps_reported, 2)}</td>
            <td class="${signClass(q.surprise_pct)}">${fmtPct(q.surprise_pct, 1)}</td>
          </tr>`).join('')}</tbody>
        </table>
        ${(eh.upcoming || []).length ? `<h3>${hg('Next report')}</h3>${kv((eh.upcoming || []).map((u) => [u.date, 'consensus EPS ' + fmt(u.eps_estimate, 2)]))}` : ''}
        <ul class="reasons">${(eh.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>`
    : '<div class="callout">No earnings history — typical for ETFs and index products.</div>'}
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Financials')}</h2>
      ${fn.available ? `
        <p class="sub">Annual statements, most recent first.</p>
        <div class="grid c3" style="margin-bottom:10px">
          ${tile('Revenue growth (y/y)', fmtPct((fn.growth || {}).revenue_yoy_pct, 1), null, signClass((fn.growth || {}).revenue_yoy_pct))}
          ${tile('Net income growth', fmtPct((fn.growth || {}).net_income_yoy_pct, 1), null, signClass((fn.growth || {}).net_income_yoy_pct))}
          ${tile('Net margin', fmt((fn.margins || {}).net_pct, 1) + '%')}
        </div>
        <table class="data">
          <thead><tr><th>Line</th>${(ap || []).map((p2) => `<th>${esc(p2)}</th>`).join('')}</tr></thead>
          <tbody>
            ${finRow('Revenue', an.revenue, true)}
            ${finRow('Gross profit', an.gross_profit, true)}
            ${finRow('Operating income', an.operating_income, true)}
            ${finRow('Net income', an.net_income, true)}
            ${finRow('Free cash flow', an.free_cash_flow, true)}
            ${finRow('Diluted EPS', an.diluted_eps, false)}
          </tbody>
        </table>
        ${kv([
    ['Cash', '$' + fmtCompact((fn.balance_sheet || {}).cash)],
    ['Total debt', '$' + fmtCompact((fn.balance_sheet || {}).total_debt)],
    ['Net cash position', '$' + fmtCompact((fn.balance_sheet || {}).net_cash)],
    ['Debt / equity', fmt((fn.balance_sheet || {}).debt_to_equity, 2)],
    ['Gross margin', fmt((fn.margins || {}).gross_pct, 1) + '%'],
    ['Operating margin', fmt((fn.margins || {}).operating_pct, 1) + '%'],
  ])}
        <ul class="reasons">${(fn.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>`
    : `<div class="callout">${esc(fn.note || 'No financial statements for this security.')}</div>`}
    </div>

    <div class="panel">
      <h2>${hg('Insider & institutional activity')}</h2>
      ${ow.available ? `
        <p class="sub">Insiders are net <strong>${esc(ow.insider_signal)}</strong> over the last six months.</p>
        <div class="grid c3" style="margin-bottom:10px">
          ${tile('Insider net (6m)', fmtCompact((ow.insider_6m || {}).net_shares) + ' sh', null, signClass((ow.insider_6m || {}).net_shares))}
          ${tile('Institutional held', ow.institutional_pct_held !== null && ow.institutional_pct_held !== undefined ? fmt(ow.institutional_pct_held * 100, 1) + '%' : '—')}
          ${tile('Top holders', `${ow.holders_adding} adding / ${ow.holders_trimming} trimming`)}
        </div>
        ${kv([
    ['Insider purchases (6m)', `${fmtCompact((ow.insider_6m || {}).purchase_shares)} sh in ${fmt((ow.insider_6m || {}).purchase_count, 0)} trades`],
    ['Insider sales (6m)', `${fmtCompact((ow.insider_6m || {}).sale_shares)} sh in ${fmt((ow.insider_6m || {}).sale_count, 0)} trades`],
    ['Insider-held float', ow.insider_pct_held !== null && ow.insider_pct_held !== undefined ? fmt(ow.insider_pct_held * 100, 2) + '%' : '—'],
  ])}
        <h3>${hg('Recent insider transactions')}</h3>
        <div class="scroll-y" style="max-height:200px">
        <table class="data">
          <thead><tr><th>Insider</th><th>Position</th><th>Date</th><th>Action</th><th>Shares</th><th>Value</th></tr></thead>
          <tbody>${(ow.recent_transactions || []).map((tx) => `<tr>
            <td class="name">${esc(tx.insider)}</td>
            <td class="name" style="color:var(--ink-muted)">${esc(tx.position)}</td>
            <td class="name">${esc(tx.date)}</td>
            <td class="name ${tx.action === 'purchase' ? 'up' : tx.action === 'sale' ? 'down' : ''}">${esc(cap(tx.action))}</td>
            <td>${fmtCompact(tx.shares)}</td>
            <td>${tx.value ? '$' + fmtCompact(tx.value) : '—'}</td>
          </tr>`).join('') || '<tr><td colspan="6" style="color:var(--ink-muted)">No recent filings.</td></tr>'}</tbody>
        </table></div>
        <h3>${hg('Largest reported holders')}</h3>
        <table class="data">
          <thead><tr><th>Holder</th><th>As of</th><th>Shares</th><th>% held</th><th>Change</th></tr></thead>
          <tbody>${(ow.top_holders || []).slice(0, 6).map((hd) => `<tr>
            <td class="name">${esc(hd.holder)}</td>
            <td class="name">${esc(hd.date_reported)}</td>
            <td>${fmtCompact(hd.shares)}</td>
            <td>${hd.pct_held !== null ? fmt(hd.pct_held * 100, 2) + '%' : '—'}</td>
            <td class="${signClass(hd.pct_change)}">${hd.pct_change !== null ? fmtPct(hd.pct_change * 100, 1) : '—'}</td>
          </tr>`).join('')}</tbody>
        </table>
        <ul class="reasons">${(ow.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>
        <p class="caveat">${esc(ow.caveat || '')}</p>`
    : '<div class="callout">No ownership data for this security.</div>'}
    </div>
  </div>`;
}

function renderIdea(idea) {
  if (idea.conceptual) return renderConceptualIdea(idea);

  const rp = idea.risk_plan || {};
  const breakevenText = Array.isArray(idea.breakeven)
    ? idea.breakeven.map((v) => fmt(v, 2)).join(' / ')
    : idea.breakeven ? fmt(idea.breakeven, 2) + (idea.breakeven_move_pct ? ` (${fmtPct(idea.breakeven_move_pct, 1)})` : '') : null;

  return `<div class="idea">
    <div class="idea-head">
      <span class="idea-name">${esc(idea.name)}</span>
      <span class="chip neutral"><span class="dot"></span>${esc(cap(idea.structure))}</span>
      <span style="color:var(--ink-muted);font-size:12px">${esc(idea.expiry)} · ${idea.dte}d</span>
    </div>
    <div class="idea-why">${gloss(idea.rationale)}</div>
    ${(idea.legs || []).map((l) => `<div class="leg">
      <span class="${l.action === 'BUY' ? 'buy' : 'sell'}">${esc(l.action)}</span>
      <span>${esc(l.type)}</span>
      <span>${fmt(l.strike, 1)} @ ${fmt(l.mid, 2)} <span class="muted">(${fmt(l.bid, 2)}/${fmt(l.ask, 2)})</span></span>
      <span class="muted">Δ ${fmt(l.delta, 3)}</span>
      <span class="muted">Γ ${fmt(l.gamma, 4)}</span>
      <span class="muted">θ ${fmt(l.theta_per_day, 3)}</span>
      <span class="muted">IV ${fmt((l.iv || 0) * 100, 1)}%</span>
    </div>`).join('')}
    <div style="margin-top:9px">${kv([
    idea.net_debit !== undefined && idea.net_debit !== null ? ['Net debit', '$' + fmt(idea.net_debit, 2)] : null,
    idea.net_credit !== undefined && idea.net_credit !== null ? ['Net credit', '$' + fmt(idea.net_credit, 2)] : null,
    ['Max profit', typeof idea.max_profit === 'string' ? esc(idea.max_profit) : '$' + fmt(idea.max_profit, 2)],
    ['Max loss', '$' + fmt(idea.max_loss, 2)],
    idea.risk_reward ? ['Risk / reward', `1 : ${fmt(idea.risk_reward, 2)}`] : null,
    breakevenText ? ['Breakeven', breakevenText] : null,
    idea.profit_zone ? ['Profit zone', `${fmt(idea.profit_zone[0], 1)} – ${fmt(idea.profit_zone[1], 1)}`] : null,
    ['Net delta', fmt(idea.net_delta, 3)],
    idea.net_theta_per_day ? ['Net theta / day', fmt(idea.net_theta_per_day, 3)] : null,
    idea.theta_pct_of_premium_daily ? ['Theta burn', fmt(idea.theta_pct_of_premium_daily, 2) + '% of premium/day'] : null,
    idea.assignment_note ? ['Assignment', esc(idea.assignment_note)] : null,
    rp.underlying_stop ? ['Stop on the stock', `${usd(rp.underlying_stop)} — ${esc(rp.stop_basis || '')}`] : null,
    rp.first_target ? ['First target', fmt(rp.first_target, 2)] : null,
  ])}</div>
    ${rp.invalidation ? `<div class="caveat">Invalidation: ${gloss(rp.invalidation)} ${gloss(rp.sizing_note || '')}</div>` : ''}
  </div>`;
}

function renderConceptualIdea(idea) {
  const p = idea.pair || {};
  return `<div class="idea">
    <div class="idea-head">
      <span class="idea-name">${esc(idea.name)}</span>
      <span class="chip neutral"><span class="dot"></span>${esc(cap(idea.structure))}</span>
    </div>
    <div class="idea-why">${esc(idea.rationale)}</div>
    <div style="margin-top:9px">${kv([
    ['Long side', esc(p.long)],
    ['Short side', esc(p.short)],
    p.rs_1m_pct !== null && p.rs_1m_pct !== undefined ? ['Relative strength (1m)', fmtPct(p.rs_1m_pct, 1)] : null,
    p.rs_3m_pct !== null && p.rs_3m_pct !== undefined ? ['Relative strength (3m)', fmtPct(p.rs_3m_pct, 1)] : null,
    p.ratio_zscore_60d !== null && p.ratio_zscore_60d !== undefined ? ['Ratio z-score (60d)', fmt(p.ratio_zscore_60d, 2)] : null,
  ])}</div>
    <div class="caveat">${esc(idea.note || '')}</div>
  </div>`;
}

/* =================================================================== MARKET */

function renderMarket(d) {
  hideTip();
  const m = d.macro || {};
  const s = d.sectors || {};
  const evc = (s.breadth || {}).equal_vs_cap || {};
  const inst = m.instruments || {};
  // 'equity' is deliberately absent: index levels and short-horizon momentum are
  // covered by the Indices tab and the status bar, and this dashboard exists for
  // the non-equity markets that tend to move before stocks do. The Russell/S&P
  // ratio still appears under Cross-asset ratios, where it says something new.
  const groupOrder = ['volatility', 'rates', 'fx', 'commodities', 'credit', 'crypto'];

  const sectorMax = Math.max(10, ...(s.sectors || []).map((r) => Math.abs(r.composite || 0)));

  const instRow = (r) => `<tr>
    <td class="name">${esc(cap(r.label))}<div style="color:var(--ink-muted);font-size:11px">${esc(cap(r.note) || '')}</div></td>
    <td>${fmt(r.last, r.last && r.last < 10 ? 4 : 2)}</td>
    <td class="${signClass(r.chg_1d)}">${fmtPct(r.chg_1d, 2)}</td>
    <td class="${signClass(r.chg_5d)}">${fmtPct(r.chg_5d, 2)}</td>
    <td class="${signClass(r.chg_20d)}">${fmtPct(r.chg_20d, 2)}</td>
    <td class="${signClass(r.vs_sma200)}">${fmtPct(r.vs_sma200, 1)}</td>
    <td>${fmt(r.rsi, 0)}</td>
    <td><span data-spark='${esc(JSON.stringify(r.series || []))}'></span></td>
  </tr>`;

  views.market.innerHTML = `
  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Macro regime')}</h2>
      <p class="sub">${esc(m.stance || '')}</p>
      <div style="display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap">
        <div>
          <div class="hero-label">Risk score</div>
          <div class="hero ${signClass(m.risk_score)}">${m.risk_score > 0 ? '+' : ''}${fmt(m.risk_score, 0)}</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          ${toneChip(m.regime)}
          ${m.curve_3m10y !== null && m.curve_3m10y !== undefined
    ? `<span class="chip ${m.curve_3m10y < 0 ? 'bear' : 'neutral'}"><span class="dot"></span>3m/10y curve ${fmt(m.curve_3m10y, 2)}</span>` : ''}
          <span class="chip neutral"><span class="dot"></span>VIX ${fmt((inst['^VIX'] || {}).last, 1)}</span>
        </div>
      </div>
      <h3>${hg('What\'s driving it')}</h3>
      <ul class="reasons">${(m.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>
    </div>

    <div class="panel">
      <h2>${hg('Market breadth')}</h2>
      <p class="sub">${gloss((s.breadth || {}).note || '')}</p>
      <div class="grid c2">
        ${tile('Sectors above 200-day', fmt((s.breadth || {}).pct_sectors_above_200sma, 0) + '%')}
        ${tile('Sectors above 50-day', fmt((s.breadth || {}).pct_sectors_above_50sma, 0) + '%')}
      </div>
      ${evc.note ? `
      <h3>${hg('Equal-weight vs cap-weight (RSP / SPY)')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— daily</span></h3>
      <p class="sub">${gloss(evc.note)}</p>
      <div class="grid c2" style="margin-bottom:6px">
        ${tile('RSP / SPY over 3 months', fmtPct(evc.chg_3m_pct, 1), 'equal-weight vs cap-weight', signClass(evc.chg_3m_pct))}
        ${tile('Over 1 year', fmtPct(evc.chg_1y_pct, 1), 'equal-weight vs cap-weight', signClass(evc.chg_1y_pct))}
      </div>
      <div id="chart-breadth"></div>` : ''}
      <h3>${hg('Rotation')}</h3>
      <p style="color:var(--ink-2);font-size:13px;margin:0">${gloss(s.rotation_note || '')}</p>
      ${(s.suggested_pair || {}).long ? `<div class="callout info">Cleanest expression right now:
        <strong>long ${esc(s.suggested_pair.long)} / short ${esc(s.suggested_pair.short)}</strong>. ${esc(s.suggested_pair.note)}</div>` : ''}
    </div>
  </div>

  <div class="panel" style="margin-bottom:14px">
    <h2>${hg('Cross-asset dashboard')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— daily bars</span></h2>
    <p class="sub">Level, momentum across three horizons, position versus the 200-day, and a 90-day trace.</p>
    ${groupOrder.filter((g) => (m.groups || {})[g]).map((g) => `
      <h3>${hg(g)}</h3>
      <table class="data">
        <thead><tr><th>Instrument</th><th>Last</th><th>1d</th><th>5d</th><th>20d</th><th>vs 200d</th><th>RSI</th><th>90-day</th></tr></thead>
        <tbody>${m.groups[g].filter((r) => !r.error).map(instRow).join('')}</tbody>
      </table>`).join('')}
  </div>

  <div class="panel" style="margin-bottom:14px">
    <h2>${hg('Cross-asset ratios')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— daily bars</span></h2>
    <p class="sub">Ratio lines carry the regime signal that absolute levels hide.</p>
    <div class="grid c2">
      ${(m.ratios || []).map((r, i) => `<div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px">
          <strong style="font-size:13px">${esc(r.name)}</strong>
          ${toneChip(r.signal)}
        </div>
        <div style="color:var(--ink-muted);font-size:12px;margin:2px 0 6px">${esc(r.reads)}</div>
        <div style="display:flex;gap:14px;font-size:12px;font-variant-numeric:tabular-nums;margin-bottom:4px">
          <span>5d <span class="${signClass(r.chg_5d)}">${fmtPct(r.chg_5d, 1)}</span></span>
          <span>20d <span class="${signClass(r.chg_20d)}">${fmtPct(r.chg_20d, 1)}</span></span>
          <span>60d <span class="${signClass(r.chg_60d)}">${fmtPct(r.chg_60d, 1)}</span></span>
        </div>
        <div id="ratio-chart-${i}"></div>
      </div>`).join('')}
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel span2">
      <h2>${hg('Sector relative strength')}</h2>
      <p class="sub">Ranked on the ratio line against ${esc(s.benchmark || 'SPY')} — leadership, not beta. Composite blends 1-week to 6-month relative strength with trend confirmation.</p>
      <table class="data">
        <thead><tr><th>#</th><th>Sector</th><th>Composite</th><th></th><th>RS 1w</th><th>RS 1m</th><th>RS 3m</th><th>RS 6m</th><th>RSI</th><th>vs 50d</th><th>vs 200d</th><th>Strength</th></tr></thead>
        <tbody>${(s.sectors || []).map((r) => `<tr>
          <td>${r.rank}</td>
          <td class="name">${esc(r.name)} <span style="color:var(--ink-muted)">${esc(r.symbol)}</span></td>
          <td class="${signClass(r.composite)}">${fmt(r.composite, 1)}</td>
          <td><span data-bar-max="${sectorMax}" data-bar="${r.composite}"></span></td>
          <td class="${signClass((r.rs || {}).rs_1w)}">${fmtPct((r.rs || {}).rs_1w, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_1m)}">${fmtPct((r.rs || {}).rs_1m, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_3m)}">${fmtPct((r.rs || {}).rs_3m, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_6m)}">${fmtPct((r.rs || {}).rs_6m, 1)}</td>
          <td>${fmt(r.rsi, 0)}</td>
          <td class="${signClass(r.vs_sma50)}">${fmtPct(r.vs_sma50, 1)}</td>
          <td class="${signClass(r.vs_sma200)}">${fmtPct(r.vs_sma200, 1)}</td>
          <td class="name">${toneChip(r.strength)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Themes & sub-industries')}</h2>
      <p class="sub">Same ranking method applied to narrower baskets, where rotation shows up first.</p>
      <table class="data">
        <thead><tr><th>#</th><th>Theme</th><th>Composite</th><th>RS 1m</th><th>RS 3m</th><th>RSI</th><th>Breakout</th></tr></thead>
        <tbody>${(s.themes || []).map((r) => `<tr>
          <td>${r.rank}</td>
          <td class="name">${esc(r.name)} <span style="color:var(--ink-muted)">${esc(r.symbol)}</span></td>
          <td class="${signClass(r.composite)}">${fmt(r.composite, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_1m)}">${fmtPct((r.rs || {}).rs_1m, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_3m)}">${fmtPct((r.rs || {}).rs_3m, 1)}</td>
          <td>${fmt(r.rsi, 0)}</td>
          <td>${fmt(r.breakout_score, 0)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>

    <div class="panel">
      <h2>${hg('Breakout candidates')}</h2>
      <p class="sub">Coiled near a range high, in a volatility squeeze, with momentum in the constructive band. All three together — any one alone is noise.</p>
      ${(s.breakout_candidates || []).map((r) => `<div style="padding:8px 0;border-bottom:1px solid var(--grid)">
        <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline">
          <strong>${esc(r.symbol)} <span style="color:var(--ink-2);font-weight:400">${esc(r.name)}</span></strong>
          <span class="chip ${r.breakout_ready ? 'bull' : 'neutral'}"><span class="dot"></span>Score ${fmt(r.breakout_score, 0)}</span>
        </div>
        <ul class="reasons">${(r.breakout_reasons || []).map((x) => `<li>${gloss(x)}</li>`).join('')}</ul>
      </div>`).join('') || '<div style="color:var(--ink-muted)">Nothing is set up cleanly right now — that is itself information.</div>'}
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Niche industries')}</h2>
      <p class="sub">One level narrower than the themes above — single sub-industries and thematic baskets
        (memory chips, uranium, cybersecurity, rare earths...) that rotation often reaches before it shows
        up in the broader sector or theme ETFs.</p>
      <table class="data">
        <thead><tr><th>#</th><th>Niche</th><th>Composite</th><th>RS 1m</th><th>RS 3m</th><th>RSI</th><th>Breakout</th></tr></thead>
        <tbody>${(s.niche || []).map((r) => `<tr>
          <td>${r.rank}</td>
          <td class="name">${esc(r.name)} <span style="color:var(--ink-muted)">${esc(r.symbol)}</span></td>
          <td class="${signClass(r.composite)}">${fmt(r.composite, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_1m)}">${fmtPct((r.rs || {}).rs_1m, 1)}</td>
          <td class="${signClass((r.rs || {}).rs_3m)}">${fmtPct((r.rs || {}).rs_3m, 1)}</td>
          <td>${fmt(r.rsi, 0)}</td>
          <td>${fmt(r.breakout_score, 0)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h2>${hg('Ratio pair trades')}</h2>
    <p class="sub">Each row is one ratio line. A z-score beyond ±2 is a mean-reversion setup; a trending ratio above its 50-day is a momentum setup. Sorted by how stretched they are.</p>
    <table class="data">
      <thead><tr><th>Pair</th><th>Thesis</th><th>Ratio</th><th>z (60d)</th><th>5d</th><th>20d</th><th>60d</th><th>Setup</th></tr></thead>
      <tbody>${(s.pairs || []).map((p) => `<tr>
        <td class="name"><strong>${esc(p.pair)}</strong></td>
        <td class="name" style="color:var(--ink-2);white-space:normal;max-width:230px">${esc(cap(p.thesis))}</td>
        <td>${fmt(p.ratio, 4)}</td>
        <td class="${Math.abs(p.zscore_60d) >= 2 ? signClass(-p.zscore_60d) : 'flat'}">${fmt(p.zscore_60d, 2)}</td>
        <td class="${signClass(p.chg_5d)}">${fmtPct(p.chg_5d, 1)}</td>
        <td class="${signClass(p.chg_20d)}">${fmtPct(p.chg_20d, 1)}</td>
        <td class="${signClass(p.chg_60d)}">${fmtPct(p.chg_60d, 1)}</td>
        <td class="name" style="white-space:normal;max-width:260px;color:var(--ink-2)">${esc(cap(p.setup))}</td>
      </tr>`).join('')}</tbody>
    </table>
    <p class="caveat">Ratio z-scores are computed on a 60-day window; a persistent regime shift will read as "stretched" for a long time before it reverts, if it reverts at all.</p>
  </div>
  `;

  views.market.querySelectorAll('[data-spark]').forEach((host) => {
    try { host.appendChild(sparkline(JSON.parse(host.dataset.spark), 96, 24, C.s1)); } catch (e) { /* skip */ }
  });
  views.market.querySelectorAll('[data-bar]').forEach((host) => {
    host.appendChild(inlineBar(Number(host.dataset.bar), Number(host.dataset.barMax) || sectorMax, 70, 9));
  });
  (m.ratios || []).forEach((r, i) => {
    mount(`ratio-chart-${i}`, (w) => lineChart({
      width: w,
      height: 130, labels: r.dates || [], markerLast: true,
      series: [{ name: r.name, values: r.series || [], color: C.s1, fill: true }],
      yFormat: (x) => fmt(x, x < 1 ? 4 : 2),
    }));
  });

  if (evc.series) {
    mount('chart-breadth', (w) => lineChart({
      width: w,
      height: 190,
      labels: evc.dates || [],
      series: [{ name: 'RSP / SPY', values: evc.series, color: C.s3, fill: true }],
      yFormat: (x) => fmt(x, 3),
    }));
  }
}

/* =================================================================== SCALP */

function meterHTML(score, color) {
  const pct = Math.max(0, Math.min(100, score || 0));
  return `<div style="background:var(--surface-2);height:8px;border-radius:4px;overflow:hidden;margin-top:4px">
    <div style="width:${pct}%;height:100%;background:${color};transition:width 0.3s ease"></div>
  </div>`;
}

function renderScalp(d) {
  hideTip();

  if (d.error) {
    views.scalp.innerHTML = `<div class="panel"><h2>${hg('Scalps')}</h2><div class="callout bad">${esc(d.error)}</div>
      <p class="caveat">Minute bars need an active session — this is usually empty outside 9:30am–4:00pm ET on a trading day, or for a symbol with no intraday history.</p></div>`;
    return;
  }

  const sq = d.squeeze || {};
  const gex = d.near_term_gex || {};
  const liq = d.liquidity || {};
  const mo = d.momentum || {};
  const orz = d.opening_range || {};
  const piv = d.pivots || {};
  const rv = d.rvol || {};
  const si = d.short_interest || {};
  const front = d.front_expiry || {};

  const html = `
  <div class="callout ${d.realtime ? 'info' : 'bad'}" style="margin-bottom:14px">
    <strong>${d.realtime ? 'Real-time (Tradier).' : 'Not real-time.'}</strong> ${gloss(d.data_caveat || '')}
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Squeeze read')}</h2>
      <p class="sub">${gloss(sq.headline || '')}</p>

      <div style="margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--ink-2)">
          <span class="gloss-term" tabindex="0" data-def="${esc(GLOSSARY['gamma squeeze'])}">Gamma squeeze</span>
          <span>${fmt(sq.gamma_squeeze_score, 0)} / 100</span>
        </div>
        ${meterHTML(sq.gamma_squeeze_score, C.s1)}
        <ul class="reasons">${(sq.gamma_squeeze_notes || []).map((n) => `<li>${gloss(n)}</li>`).join('') || '<li style="color:var(--ink-muted)">No gamma-squeeze conditions detected.</li>'}</ul>
      </div>

      <div>
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--ink-2)">
          <span class="gloss-term" tabindex="0" data-def="${esc(GLOSSARY['short squeeze'])}">Short squeeze</span>
          <span>${fmt(sq.short_squeeze_score, 0)} / 100</span>
        </div>
        ${meterHTML(sq.short_squeeze_score, C.s8)}
        <ul class="reasons">${(sq.short_squeeze_notes || []).map((n) => `<li>${gloss(n)}</li>`).join('') || '<li style="color:var(--ink-muted)">No short-squeeze conditions detected.</li>'}</ul>
      </div>
    </div>

    <div class="panel">
      <h2>${hg('Session snapshot')}</h2>
      <p class="sub">Session ${esc(d.session_date || '')} · ${d.bars_so_far || 0} one-minute bars so far.</p>
      <div class="grid c2" style="margin-bottom:10px">
        ${tile('Last', fmt(d.spot, 2))}
        ${tile('vs VWAP', fmtPct(d.price_vs_vwap_pct, 2), `VWAP ${fmt(d.vwap, 2)}`, signClass(d.price_vs_vwap_pct))}
        ${tile('Fast trend (1m)', mo.trend === 'up' ? 'Up' : mo.trend === 'down' ? 'Down' : '—', `9-EMA ${fmt(mo.ema9, 2)} / 20-EMA ${fmt(mo.ema20, 2)}`, mo.trend === 'up' ? 'up' : mo.trend === 'down' ? 'down' : '')}
        ${tile('Fast RSI (7, 1m)', fmt(mo.fast_rsi_7, 0))}
      </div>
      ${kv([
    ['Opening range (15m)', orz.high ? `${fmt(orz.low, 2)} – ${fmt(orz.high, 2)}${orz.complete ? '' : ' (forming)'}` : '—'],
    ['Prior close / pivot', piv.pivot ? `${fmt(piv.prior_close, 2)} / ${fmt(piv.pivot, 2)}` : '—'],
    ['R1 / R2', piv.r1 ? `${fmt(piv.r1, 2)} / ${fmt(piv.r2, 2)}` : '—'],
    ['S1 / S2', piv.s1 ? `${fmt(piv.s1, 2)} / ${fmt(piv.s2, 2)}` : '—'],
    ['Relative volume', rv.rvol !== undefined && rv.rvol !== null ? `${fmt(rv.rvol, 2)}x` : '—'],
  ])}
    </div>
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Intraday price, VWAP & fast EMAs')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— 1-minute bars, today's session</span></h2>
    <p class="sub">Dashed lines are the opening range and yesterday's pivot — the levels an intraday trade actually reacts to.</p>
    <div id="legend-scalp"></div>
    <div id="chart-scalp-price"></div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Near-term gamma')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— ${front.expiry ? esc(front.expiry) : '—'}${front.is_0dte ? ' (0DTE)' : front.dte !== undefined ? ` (${front.dte} DTE)` : ''}</span></h2>
      ${gex.error ? `<div class="callout">${esc(gex.error)}</div>` : `
      <p class="sub">${!front.is_0dte && front.dte ? `This ticker doesn't list same-day options — nearest expiry is ${front.dte} day${front.dte === 1 ? '' : 's'} out.` : 'Gamma at the nearest listed expiry — this is what dealer hedging looks like for the rest of today.'}</p>
      <div class="grid c2" style="margin-bottom:10px">
        ${tile('Regime', esc(gex.regime || '—'), null, gex.regime === 'negative' ? 'down' : 'up')}
        ${tile('Flip point', fmt(gex.flip_point, 2), gex.flip_distance_pct !== null ? fmtPct(gex.flip_distance_pct, 2) + ' away' : null)}
        ${tile('Call wall', fmt(gex.call_wall, 2))}
        ${tile('Put wall', fmt(gex.put_wall, 2))}
      </div>
      <p class="caveat">${gex.regime === 'negative'
    ? gloss('Negative gamma — dealer hedging amplifies moves in either direction.')
    : gloss('Positive gamma — dealer hedging dampens moves, favoring chop over follow-through.')}</p>`}
    </div>

    <div class="panel">
      <h2>${hg('Liquidity & short interest')}</h2>
      ${liq.quality ? `<p class="sub">Near-the-money spreads are <strong>${esc(liq.quality)}</strong>. ${gloss(liq.note || '')}</p>
        ${kv([
    ['Median spread', fmt(liq.median_spread_pct, 1) + '%'],
    ['Avg open interest', fmtCompact(liq.avg_open_interest)],
    ['Avg volume', fmtCompact(liq.avg_volume)],
  ])}` : '<div class="callout">No near-term chain to judge liquidity from.</div>'}
      <h3>${hg('Short interest')}</h3>
      ${si.available ? kv([
    ['% of float short', si.percent_of_float !== null ? fmt(si.percent_of_float * 100, 2) + '%' : '—'],
    ['Days to cover', fmt(si.days_to_cover, 2)],
  ]) : '<div class="callout">No short-interest data for this security.</div>'}
    </div>
  </div>
  `;

  views.scalp.innerHTML = html;

  if ((mo.series || {}).close) {
    // Pivot R2/S2 can sit well outside today's actual range on a calm day —
    // including them unconditionally would stretch the y-axis until the
    // price action itself (the point of this chart) reads as a flat line.
    // Only draw a level if it's within half a day's range of what's printed.
    const closeVals = (mo.series.close || []).filter((v) => v !== null);
    const seriesLo = Math.min(...closeVals);
    const seriesHi = Math.max(...closeVals);
    const band = (seriesHi - seriesLo) * 0.5 || seriesHi * 0.01;
    const inRange = (v) => v !== null && v !== undefined && v >= seriesLo - band && v <= seriesHi + band;

    // Labels spell out what each level is and where it sits: "R1" alone means
    // nothing to anyone who hasn't memorised floor-trader pivot notation.
    const refLines = [
      orz.high ? { value: orz.high, label: `Opening range high ${fmt(orz.high, 2)}`, color: C.s7 } : null,
      orz.low ? { value: orz.low, label: `Opening range low ${fmt(orz.low, 2)}`, color: C.s7 } : null,
      inRange(piv.pivot) ? { value: piv.pivot, label: `Pivot ${fmt(piv.pivot, 2)}`, color: C.baseline } : null,
      inRange(piv.r1) ? { value: piv.r1, label: `R1 resistance ${fmt(piv.r1, 2)}`, color: C.s6 } : null,
      inRange(piv.r2) ? { value: piv.r2, label: `R2 resistance ${fmt(piv.r2, 2)}`, color: C.s6 } : null,
      inRange(piv.s1) ? { value: piv.s1, label: `S1 support ${fmt(piv.s1, 2)}`, color: C.s6 } : null,
      inRange(piv.s2) ? { value: piv.s2, label: `S2 support ${fmt(piv.s2, 2)}`, color: C.s6 } : null,
    ].filter(Boolean);

    mount('legend-scalp', legend([
      { name: 'Price', color: C.s1 },
      { name: 'VWAP', color: C.s4 },
      { name: '9-EMA', color: C.s3 },
      { name: '20-EMA', color: C.s2 },
      { name: 'Opening range', color: C.s7, dash: true },
      { name: 'Pivot S/R', color: C.s6, dash: true },
    ]));
    mount('chart-scalp-price', (w) => lineChart({
      width: w,
      height: 280,
      labels: mo.series.times || [],
      series: [
        { name: 'Price', values: mo.series.close, color: C.s1 },
        { name: 'VWAP', values: mo.series.vwap, color: C.s4, width: 1.5, marker: false },
        { name: '9-EMA', values: mo.series.ema9, color: C.s3, width: 1.5, marker: false },
        { name: '20-EMA', values: mo.series.ema20, color: C.s2, width: 1.5, marker: false },
      ],
      refLines,
      yFormat: (x) => fmt(x, 2),
    }));
  }
}

/* ================================================================= EARNINGS */

function renderEarnings(d) {
  hideTip();
  if (d.error) {
    views.earnings.innerHTML = `<div class="panel"><h2>${hg('Next report')}</h2>
      <div class="callout bad">${esc(d.error)}</div></div>`;
    return;
  }
  if (d.not_applicable) {
    views.earnings.innerHTML = `<div class="panel"><h2>No earnings for ${esc(d.ticker || '')}</h2>
      <div class="callout info">${esc(d.reason)}</div>
      <p class="sub" style="margin-top:10px">The Swing / Options, Scalps and Macro tabs all work
        normally for this ticker.</p></div>`;
    return;
  }

  const nr = d.next_report || {};
  const sp = d.surprise || {};
  const rev = d.revisions || {};
  const gr = d.growth || {};
  const imp = d.implied || {};
  const pr = d.pricing || {};
  const an = d.analyst || {};
  const v = d.verdict || {};
  const lr = d.latest_result || {};
  const ext = d.extended_hours || {};
  // A report that has already been released changes what this panel is *for*:
  // the countdown and the consensus band describe a decision that's now closed,
  // and the result is the news. Same data, led differently.
  const reported = !!lr.just_reported;

  const stanceCls = pr.stance === 'expensive' ? 'bear' : pr.stance === 'cheap' ? 'bull' : 'neutral';
  const revCls = rev.direction === 'rising' ? 'bull' : rev.direction === 'falling' ? 'bear' : 'neutral';

  // A countdown is the first thing you want, so it leads.
  const reactionChip = reported && ext.available && ext.move_pct !== null
    ? `<span class="chip ${ext.move_pct > 0 ? 'bull' : 'bear'}"><span class="dot"></span>${
      esc(cap(ext.kind))} ${fmtPct(ext.move_pct, 1)}</span>`
    : '';

  const daysChip = reported
    ? `<span class="chip ${lr.beat ? 'bull' : 'bear'}"><span class="dot"></span>${
      lr.age_days === 0 ? 'Reported today' : `Reported ${lr.age_days}d ago`}</span>`
    : nr.days_away === null || nr.days_away === undefined
      ? '<span class="chip neutral"><span class="dot"></span>No date scheduled</span>'
      : `<span class="chip ${nr.days_away <= 7 ? 'bear' : 'neutral'}"><span class="dot"></span>${
        nr.days_away === 0 ? 'Reports today' : `${nr.days_away} day${nr.days_away === 1 ? '' : 's'} away`}</span>`;

  const surpriseRows = (sp.rows || []).map((r) => `<tr>
    <td class="name">${esc(r.date)}</td>
    <td>${fmt(r.eps_estimate, 2)}</td>
    <td>${fmt(r.eps_reported, 2)}</td>
    <td class="${signClass(r.surprise_pct)}">${fmtPct(r.surprise_pct, 1)}</td>
    <td class="${signClass(r.next_day_move_pct)}">${fmtPct(r.next_day_move_pct, 1)}</td>
  </tr>`).join('');

  const revRows = (rev.rows || []).map((r) => `<tr>
    <td class="name">${esc(r.label)}</td>
    <td>${fmt(r.current, 2)}</td>
    <td class="${signClass(r.chg_30d_pct)}">${fmtPct(r.chg_30d_pct, 1)}</td>
    <td class="${signClass(r.chg_90d_pct)}">${fmtPct(r.chg_90d_pct, 1)}</td>
    <td>${r.analysts_up_30d !== null && r.analysts_up_30d !== undefined
    ? `<span class="up">${r.analysts_up_30d}↑</span> / <span class="down">${r.analysts_down_30d || 0}↓</span>` : '—'}</td>
  </tr>`).join('');

  const fwdRows = (gr.forward || []).map((r) => `<tr>
    <td class="name">${esc(r.label)}</td>
    <td>${fmt(r.eps_avg, 2)}</td>
    <td class="${signClass(r.eps_growth_pct)}">${fmtPct(r.eps_growth_pct, 0)}</td>
    <td>${r.revenue_label ? esc(r.revenue_label) : '—'}</td>
    <td class="${signClass(r.revenue_growth_pct)}">${fmtPct(r.revenue_growth_pct, 0)}</td>
    <td>${r.eps_analysts || '—'}</td>
  </tr>`).join('');

  const qRows = (gr.quarterly || []).map((r) => `<tr>
    <td class="name">${esc(r.period)}</td>
    <td>$${fmtCompact(r.revenue)}</td>
    <td class="${signClass(r.revenue_yoy_pct)}">${fmtPct(r.revenue_yoy_pct, 1)}</td>
    <td>$${fmtCompact(r.net_income)}</td>
    <td class="${signClass(r.net_income_yoy_pct)}">${fmtPct(r.net_income_yoy_pct, 1)}</td>
    <td>${fmt(r.gross_margin_pct, 1)}%</td>
    <td>${fmt(r.operating_margin_pct, 1)}%</td>
  </tr>`).join('');

  const aRows = (gr.annual || []).map((r) => `<tr>
    <td class="name">${esc(r.period)}</td>
    <td>$${fmtCompact(r.revenue)}</td>
    <td class="${signClass(r.revenue_yoy_pct)}">${fmtPct(r.revenue_yoy_pct, 1)}</td>
    <td>$${fmtCompact(r.net_income)}</td>
    <td class="${signClass(r.net_income_yoy_pct)}">${fmtPct(r.net_income_yoy_pct, 1)}</td>
    <td>${fmt(r.gross_margin_pct, 1)}%</td>
    <td>${fmt(r.operating_margin_pct, 1)}%</td>
  </tr>`).join('');

  const ratingRows = (an.ratings || []).map((r) => `<tr>
    <td class="name">${esc(r.period === '0m' ? 'Now' : r.period)}</td>
    <td>${fmt(r.strong_buy, 0)}</td><td>${fmt(r.buy, 0)}</td>
    <td>${fmt(r.hold, 0)}</td><td>${fmt(r.sell, 0)}</td><td>${fmt(r.strong_sell, 0)}</td>
  </tr>`).join('');

  views.earnings.innerHTML = `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg(reported ? 'Latest result' : 'Next report')} — ${esc(d.ticker || '')}</h2>
    <p class="sub">${gloss(v.headline || '')}</p>
    <div class="hero-row" style="display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:12px">
      <div>
        <span class="hero-label">${hg(reported ? 'Reported EPS' : 'Next report')}</span>
        <div class="hero ${reported ? signClass(lr.surprise_pct) : ''}" style="font-size:34px">${
  reported ? fmt(lr.eps_reported, 2) : (nr.date ? esc(nr.date) : '—')}</div>
        <span class="note" style="color:var(--ink-muted);font-size:11.5px">${
  reported
    ? `Vs ${fmt(lr.eps_estimate, 2)} expected · reported ${esc(lr.date || '')}`
    : nr.confirmed === false ? 'estimated date — not yet confirmed by the company' : 'confirmed date'}</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${daysChip}
        ${reactionChip}
        <span class="chip ${revCls}"><span class="dot"></span>Estimates ${esc(rev.direction || 'unknown')}</span>
        ${pr.available ? `<span class="chip ${stanceCls}"><span class="dot"></span>Event ${esc(pr.stance)}</span>` : ''}
      </div>
    </div>
    <div class="grid c4" style="margin-bottom:10px">
      ${reported
    ? tile('Surprise', fmtPct(lr.surprise_pct, 1),
      lr.beat ? 'came in above consensus' : 'came in below consensus', signClass(lr.surprise_pct))
    : tile('EPS consensus', fmt(nr.eps_consensus, 2), nr.eps_low && nr.eps_high
      ? `range ${fmt(nr.eps_low, 2)} – ${fmt(nr.eps_high, 2)}` : null)}
      ${reported && !nr.date
    ? tile('Next report', 'not scheduled yet',
      'the feed has no confirmed date for the coming quarter')
    : tile('Revenue consensus', nr.revenue_consensus_label ? esc(nr.revenue_consensus_label) : '—',
      nr.revenue_low && nr.revenue_high ? `range $${fmtCompact(nr.revenue_low)} – $${fmtCompact(nr.revenue_high)}` : null)}
      ${reported
    ? (lr.next_day_move_pct !== null && lr.next_day_move_pct !== undefined
      ? tile('Move after', fmtPct(lr.next_day_move_pct, 1), 'the session after the print',
        signClass(lr.next_day_move_pct))
      : ext.available
        ? tile('Reaction', fmtPct(ext.move_pct, 1),
          `${esc(cap(ext.kind))} · ${usd(ext.price)}`, signClass(ext.move_pct))
        : tile('Reaction', 'no quote yet', 'nothing traded outside the session'))
    : tile('Implied move', imp.available ? fmt(imp.implied_move_pct, 1) + '%' : '—',
      imp.available ? `${imp.dte}-day straddle · ${fmt(imp.strike, 2)} strike` : (imp.reason || null))}
      ${tile('Beat rate', sp.beat_rate_pct !== null && sp.beat_rate_pct !== undefined
    ? fmt(sp.beat_rate_pct, 0) + '%' : '—', sp.quarters ? `last ${sp.quarters} quarters` : null)}
    </div>
    ${nr.dispersion_note && !reported ? `<div class="callout info">${gloss(nr.dispersion_note)}</div>` : ''}
    ${reported && ext.available && lr.reaction_fights_result ? `<div class="callout bad">
      <strong>The stock is ${ext.move_pct > 0 ? 'up' : 'down'} ${fmt(Math.abs(ext.move_pct), 1)}%
      ${esc(ext.kind)} despite ${lr.beat ? 'a beat' : 'a miss'}.</strong> This is the case a beat
      rate can't warn you about — the result was fine and the market sold it anyway. Whatever moved
      the price is in the guidance or on the call, not in the headline number.</div>` : ''}
    <h3>${hg('Why')}</h3>
    <ul class="reasons">${(v.reasons || []).map((r) => `<li>${gloss(r)}</li>`).join('')}</ul>
    ${reported && ext.available ? `<p class="caveat">${gloss(ext.caveat || '')}${
  ext.as_of ? ` Last ${esc(ext.kind)} print ${new Date(ext.as_of).toLocaleString()}.` : ''}</p>` : ''}
    <p class="caveat">${esc(d.data_caveat || '')}</p>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Event pricing')}</h2>
      ${reported && !pr.available ? `<div class="callout">The report is out, so there's no event left
        to price. Straddle cost only means something ahead of the print — once the numbers land the
        premium collapses, which is the whole reason it was expensive going in.</div>` : ''}
      ${pr.stale ? `<div class="callout">${gloss(pr.stale_note || '')}</div>` : ''}
      ${pr.available ? `
        <p class="sub">${gloss(pr.note || '')}</p>
        <div class="grid c2" style="margin-bottom:10px">
          ${tile('Options imply', fmt(pr.implied_move_pct, 1) + '%', `${imp.dte}-day straddle`)}
          ${tile('Stock actually moves', fmt(pr.baseline_move_pct, 1) + '%',
    pr.baseline_kind === 'event-day' ? 'avg after past reports' : `avg over ${pr.baseline_sessions} sessions`)}
          ${tile('Ratio', fmt(pr.ratio, 2) + 'x', 'implied ÷ actual',
    pr.stance === 'expensive' ? 'down' : pr.stance === 'cheap' ? 'up' : '')}
          ${tile('ATM implied vol', imp.atm_iv_pct ? fmt(imp.atm_iv_pct, 1) + '%' : '—', imp.expiry ? `expiry ${esc(imp.expiry)}` : null)}
        </div>
        ${pr.event_day_note ? `<div class="callout info">${gloss(pr.event_day_note)}</div>` : ''}
        <p class="caveat">${gloss(pr.caveat || '')}</p>
      ` : reported ? '' : `<div class="callout">${esc(pr.note || imp.reason || 'Not available.')}</div>`}
    </div>

    <div class="panel">
      <h2>${hg('Estimate revisions')}</h2>
      <p class="sub">${gloss(rev.note || '')}</p>
      ${rev.available ? `
      <table class="data">
        <thead><tr><th>Period</th><th>EPS est.</th><th>30d</th><th>90d</th><th>Analysts</th></tr></thead>
        <tbody>${revRows}</tbody>
      </table>` : ''}
      <p class="caveat">${gloss(rev.caveat || '')}</p>
    </div>
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Surprise history')}</h2>
    ${sp.available ? `
    <p class="sub">Reported EPS against consensus, and what the stock actually did the session after.</p>
    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Average surprise', fmtPct(sp.avg_surprise_pct, 1), 'reported vs consensus', signClass(sp.avg_surprise_pct))}
      ${tile('Avg move after report', fmt(sp.avg_abs_move_pct, 1) + '%', 'absolute, either direction')}
      ${tile('Avg move on a beat', fmtPct(sp.avg_move_on_beat_pct, 1),
    sp.avg_move_on_beat_pct === null || sp.avg_move_on_beat_pct === undefined
      ? 'no beats in sample' : 'next session', signClass(sp.avg_move_on_beat_pct))}
      ${tile('Avg move on a miss', fmtPct(sp.avg_move_on_miss_pct, 1),
    sp.avg_move_on_miss_pct === null || sp.avg_move_on_miss_pct === undefined
      ? 'no misses in sample' : 'next session', signClass(sp.avg_move_on_miss_pct))}
    </div>
    ${(sp.notes || []).map((n) => `<div class="callout info">${gloss(n)}</div>`).join('')}
    <table class="data">
      <thead><tr><th>Report date</th><th>EPS est.</th><th>EPS reported</th><th>Surprise</th><th>Next session</th></tr></thead>
      <tbody>${surpriseRows}</tbody>
    </table>` : '<div class="callout">No reported earnings history available for this ticker.</div>'}
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Financial growth')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— quarterly, year over year</span></h2>
    ${(gr.notes || []).map((n) => `<div class="callout info">${gloss(n)}</div>`).join('')}
    ${qRows ? `<table class="data">
      <thead><tr><th>Quarter</th><th>Revenue</th><th>YoY</th><th>Net income</th><th>YoY</th><th>Gross margin</th><th>Op margin</th></tr></thead>
      <tbody>${qRows}</tbody>
    </table>
    <p class="caveat">The free feed carries only five quarters of statements, so year-over-year
      growth is computable for the most recent quarter alone. Earlier rows still show the level and
      margin trend; the annual table below covers multi-year growth.</p>` : '<div class="callout">No quarterly statements available.</div>'}
    ${aRows ? `<h3>${hg('Annual growth')}</h3>
    <table class="data">
      <thead><tr><th>Fiscal year</th><th>Revenue</th><th>YoY</th><th>Net income</th><th>YoY</th><th>Gross margin</th><th>Op margin</th></tr></thead>
      <tbody>${aRows}</tbody>
    </table>` : ''}
    ${fwdRows ? `<h3>${hg('Forward estimates')}</h3>
    <table class="data">
      <thead><tr><th>Period</th><th>EPS est.</th><th>EPS growth</th><th>Revenue est.</th><th>Rev growth</th><th>Analysts</th></tr></thead>
      <tbody>${fwdRows}</tbody>
    </table>` : ''}
  </div>

  <div class="panel span2">
    <h2>${hg('Analyst view')}</h2>
    ${(an.notes || []).map((n) => `<div class="callout info">${gloss(n)}</div>`).join('')}
    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Mean analyst target', usd(an.target_mean), an.target_low && an.target_high
    ? `Individual targets range ${usd(an.target_low)} – ${usd(an.target_high)}` : null)}
      ${tile('Implied upside', fmtPct(an.upside_pct, 0), 'to mean target', signClass(an.upside_pct))}
      ${tile('Buy share', an.buy_share_pct !== null && an.buy_share_pct !== undefined
    ? fmt(an.buy_share_pct, 0) + '%' : '—', an.analyst_count ? `${an.analyst_count} analysts` : null)}
      ${tile('Split', `${an.buys ?? '—'} / ${an.holds ?? '—'} / ${an.sells ?? '—'}`, 'buy / hold / sell')}
    </div>
    ${ratingRows ? `<table class="data">
      <thead><tr><th>Period</th><th>Strong buy</th><th>Buy</th><th>Hold</th><th>Sell</th><th>Strong sell</th></tr></thead>
      <tbody>${ratingRows}</tbody>
    </table>` : ''}
    <p class="caveat">Price targets are sentiment, not forecasts — they cluster above spot in almost every market.</p>
  </div>
  `;
}

/* Roth inputs persist in localStorage rather than on the server: holdings are the
 * user's own financial data, and this app has no account system to protect it
 * with. Storing it locally keeps the only copy on their machine. */
const ROTH_STORE_KEY = 'optic.roth.inputs';

function saveRothInputs() {
  try { localStorage.setItem(ROTH_STORE_KEY, JSON.stringify(STATE.rothInputs)); }
  catch (e) { /* private mode or quota — the inputs just won't persist */ }
}

function loadRothInputs() {
  try {
    const saved = JSON.parse(localStorage.getItem(ROTH_STORE_KEY) || 'null');
    if (saved && typeof saved === 'object') Object.assign(STATE.rothInputs, saved);
  } catch (e) { /* corrupt entry — fall back to defaults */ }
}

/* ================================================================= ROTH IRA */

/** Render a {symbol: value} holdings map back into the textarea's line format. */
function rothHoldingsText(holdings) {
  if (!holdings || typeof holdings !== 'object') return '';
  return Object.entries(holdings).map(([sym, val]) => `${sym} ${val}`).join('\n');
}

function renderRoth(d) {
  hideTip();
  if (d.error) { views.roth.innerHTML = errorHTML(d.error); return; }

  const inp = d.inputs || {};
  const alloc = d.allocation || {};
  const bl = d.blended || {};
  const pr = d.projection || {};
  const corr = d.correlations || {};
  const dr = d.drift || {};
  const rb = d.rebalance || {};
  const ov = d.overlap || {};
  const sl = d.stock_sleeve || {};

  const money = (v) => (v === null || v === undefined ? '—' : '$' + Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 }));

  const allocRows = (d.rows || []).map((r) => `<tr>
    <td class="name"><strong>${esc(r.symbol)}</strong><div style="color:var(--ink-muted);font-size:11px">${esc(r.name)}</div></td>
    <td><strong>${fmt(r.weight_pct, 1)}%</strong></td>
    <td>${money(r.annual_dollars)}</td>
    <td>${fmt(r.expense_ratio_pct, 2)}%</td>
    <td>${fmt(r.yield_pct, 2)}%</td>
    <td>${fmtPct(r.cagr_10y_pct, 1)}</td>
    <td>${fmt(r.volatility_pct, 1)}%</td>
    <td class="down">${fmtPct(r.max_drawdown_pct, 0)}</td>
  </tr>`).join('');

  const fundRows = (d.funds || []).map((r) => `<tr${r.in_model_pct ? ' style="background:var(--surface-2)"' : ''}>
    <td class="name"><strong>${esc(r.symbol)}</strong><div style="color:var(--ink-muted);font-size:11px">${esc(r.note || '')}</div></td>
    <td>${r.in_model_pct ? fmt(r.in_model_pct, 1) + '%' : '—'}</td>
    <td>${fmt(r.expense_ratio_pct, 2)}%</td>
    <td>${fmtPct(r.cagr_full_pct, 1)}</td>
    <td>${fmtPct(r.cagr_5y_pct, 1)}</td>
    <td>${fmt(r.volatility_pct, 1)}%</td>
    <td>${fmt(r.return_per_vol, 2)}</td>
    <td class="down">${fmtPct(r.max_drawdown_pct, 0)}</td>
    <td>${fmt(r.years_of_history, 0)}y</td>
  </tr>`).join('');

  // Correlation heat: the closer to 1.00, the less a second fund diversifies.
  const corrTable = (corr.symbols || []).length ? `
    <table class="data">
      <thead><tr><th></th>${corr.symbols.map((s) => `<th>${esc(s)}</th>`).join('')}</tr></thead>
      <tbody>${corr.symbols.map((s, i) => `<tr>
        <td class="name">${esc(s)}</td>
        ${corr.matrix[i].map((v, j) => {
    if (i === j) return '<td style="color:var(--ink-muted)">—</td>';
    const hot = v !== null && v >= 0.85;
    const cool = v !== null && v <= 0.35;
    return `<td style="color:${hot ? 'var(--s2)' : cool ? 'var(--s3)' : 'var(--ink-2)'}">${fmt(v, 2)}</td>`;
  }).join('')}
      </tr>`).join('')}</tbody>
    </table>` : '';

  views.roth.innerHTML = `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Roth IRA model allocation')}</h2>
    <p class="sub">Set your horizon and risk tolerance — the model is derived from those, not assumed.</p>

    <form class="roth-controls" id="roth-form">
      <label>Years until you'd draw on it
        <input type="number" id="roth-years" min="1" max="45" value="${inp.years}">
      </label>
      <label>Risk tolerance
        <select id="roth-risk">
          ${['conservative', 'balanced', 'growth'].map((r) => `<option value="${r}"${r === inp.risk ? ' selected' : ''}>${cap(r)}</option>`).join('')}
        </select>
      </label>
      <label>Annual contribution ($)
        <input type="number" id="roth-annual" min="0" max="100000" step="500" value="${inp.annual_contribution}">
      </label>
      <label style="flex:1 1 240px">Individual stock candidates (optional)
        <input type="text" id="roth-stocks" placeholder="e.g. AAPL, KO, MSFT"
               value="${esc((inp.stock_candidates || []).join(', '))}">
      </label>
      <label style="flex:1 1 100%">Your current holdings — one per line, symbol then dollar value
        <textarea id="roth-holdings" rows="4" spellcheck="false"
          placeholder="VTI 12000&#10;VXUS 4000&#10;BND 1500">${esc(rothHoldingsText(inp.holdings))}</textarea>
      </label>
      <button class="btn primary" type="submit">Recalculate</button>
    </form>
    <p class="caveat" style="margin-top:6px">Holdings stay on this device — saved in your browser
      and posted only to your own local server to compute the numbers. Nothing is stored server-side.</p>
    <p class="caveat" style="margin-top:8px">${gloss(d.limit_note || '')}</p>

    <div class="grid c4" style="margin:12px 0">
      ${tile('Equity', fmt(alloc.equity_pct, 0) + '%', 'stocks and REITs')}
      ${tile('Bonds', fmt(alloc.bond_pct, 0) + '%', 'ballast')}
      ${tile('Blended expense ratio', fmt(bl.expense_ratio_pct, 2) + '%',
    bl.expense_ratio_pct !== null ? `about ${money(Math.round((bl.expense_ratio_pct / 100) * 100000))} per $100k a year` : null)}
      ${tile('Blended yield', fmt(bl.yield_pct, 2) + '%', 'untaxed inside a Roth')}
    </div>

    <h3>${hg('Target weights')}</h3>
    <table class="data">
      <thead><tr><th>Fund</th><th>Weight</th><th>Per year</th><th>Expense</th><th>Yield</th><th>10y CAGR</th><th>Volatility</th><th>Worst drawdown</th></tr></thead>
      <tbody>${allocRows}</tbody>
    </table>
    <p class="caveat">${gloss(bl.caveat || '')}</p>
    <div class="callout bad" style="margin-top:10px">${esc(d.disclaimer || '')}</div>
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Contribution projection')}</h2>
    ${pr.available ? `
      <p class="sub">Contributing ${money(pr.annual_contribution)} a year for ${pr.years} years at
        a blended ${fmt(pr.rate_pct, 1)}% — the weighted historical return of the funds above.</p>
      <div class="grid c4" style="margin-bottom:12px">
        ${tile('You put in', money(pr.total_contributed), `${pr.years} × ${money(pr.annual_contribution)}`)}
        ${tile('Lower band', money(pr.balance_low), `at ${fmt(pr.rate_low_pct, 1)}%`)}
        ${tile('Central estimate', money(pr.balance_base), `at ${fmt(pr.rate_pct, 1)}%`, 'up')}
        ${tile('Upper band', money(pr.balance_high), `at ${fmt(pr.rate_high_pct, 1)}%`)}
      </div>
      <div id="legend-roth"></div>
      <div id="chart-roth"></div>
      <p class="caveat">${gloss(pr.caveat || '')}</p>
    ` : `<div class="callout">${esc(pr.note || 'Projection unavailable.')}</div>`}
  </div>

  ${dr.available ? `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Drift from target')}</h2>
    <p class="sub">Portfolio value ${money(dr.total_value)}. ${gloss(dr.summary || '')}</p>
    ${dr.unmapped_note ? `<div class="callout">${gloss(dr.unmapped_note)}</div>` : ''}
    <table class="data">
      <thead><tr><th>Exposure</th><th>You hold</th><th>Current</th><th>Target</th><th>Drift</th><th></th></tr></thead>
      <tbody>${(dr.rows || []).map((r) => `<tr>
        <td class="name">${esc(r.label)}</td>
        <td>${money(r.current_value)}</td>
        <td>${fmt(r.current_pct, 1)}%</td>
        <td>${fmt(r.target_pct, 1)}%</td>
        <td class="${signClass(r.drift_pct)}">${fmtPct(r.drift_pct, 1)}</td>
        <td><span data-bar="${r.drift_pct}" data-bar-max="25"></span></td>
      </tr>`).join('')}</tbody>
    </table>
    <p class="caveat">Funds that track the same thing are counted as one exposure — holding VOO
      where the model lists VTI isn't drift, it's the same bet under a different ticker.</p>
  </div>` : ''}

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Where to put this year\'s contribution')}</h2>
    ${rb.available ? `
      <p class="sub">${gloss(rb.note || '')}</p>
      ${(rb.rows || []).length ? `<table class="data">
        <thead><tr><th>Buy</th><th>Exposure</th><th>Amount</th><th>Share of contribution</th><th></th></tr></thead>
        <tbody>${rb.rows.map((r) => `<tr>
          <td class="name"><strong>${esc(r.symbol || '—')}</strong></td>
          <td>${esc(r.label)}</td>
          <td><strong>${money(r.dollars)}</strong></td>
          <td>${fmt(r.pct_of_contribution, 1)}%</td>
          <td><span data-bar="${r.pct_of_contribution}" data-bar-max="100"></span></td>
        </tr>`).join('')}</tbody>
      </table>` : ''}
      ${rb.overweight_note ? `<div class="callout">${gloss(rb.overweight_note)}</div>` : ''}
      <p class="caveat">Buy-only by design: directing new money at the underweights fixes drift
        without selling anything. Selling inside a Roth is tax-free, so it's an option — just not
        the default.</p>
    ` : `<div class="callout">${esc(rb.note || 'Enter your holdings above.')}</div>`}
  </div>

  ${ov.available ? `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Overlap in your holdings')}</h2>
    <p class="sub">${gloss(ov.note || '')}</p>
    ${(ov.pairs || []).length ? (ov.pairs.map((p) => `<div class="callout ${p.same_role ? 'bad' : ''}">
      <strong>${esc(p.a)} + ${esc(p.b)}</strong> — correlation ${fmt(p.correlation, 2)}.
      ${gloss(p.note)}</div>`).join('')) : '<div class="callout info">Nothing is doubled up.</div>'}
  </div>` : ''}

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Individual stock sleeve')}</h2>
    <p class="sub">${gloss(sl.note || '')}</p>
    ${(sl.rows || []).length ? `<table class="data">
      <thead><tr><th>Stock</th><th>Conviction</th><th>Score</th><th>10y CAGR</th><th>Worst drawdown</th><th>History</th><th>Suggested</th></tr></thead>
      <tbody>${sl.rows.map((r) => `<tr${r.eligible ? '' : ' style="opacity:0.62"'}>
        <td class="name"><strong>${esc(r.symbol)}</strong><div style="color:var(--ink-muted);font-size:11px">${esc(r.name || '')}</div></td>
        <td>${r.error ? '<span class="down">Error</span>' : toneChipConviction(r.conviction)}</td>
        <td class="${signClass(r.conviction_score)}">${fmt(r.conviction_score, 0)}</td>
        <td>${fmtPct(r.cagr_10y_pct, 1)}</td>
        <td class="down">${fmtPct(r.max_drawdown_pct, 0)}</td>
        <td>${fmt(r.years_of_history, 0)}y</td>
        <td>${r.eligible ? `<strong>${fmt(r.suggested_pct, 1)}%</strong>` : '—'}</td>
      </tr>`).join('')}</tbody>
    </table>
    ${sl.rows.filter((r) => r.reject_reason || r.error).map((r) => `<div class="callout">
      <strong>${esc(r.symbol)}</strong> — ${esc(r.reject_reason || r.error)}</div>`).join('')}
    ${sl.rows.flatMap((r) => (r.warnings || []).map((w) => `<div class="callout bad">
      <strong>${esc(r.symbol)}</strong> — ${gloss(w)}</div>`)).join('')}
    ` : ''}
    <div class="callout bad" style="margin-top:8px">${gloss(sl.caveat || '')}</div>
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('What the Roth wrapper changes')}</h2>
    <p class="sub">Reasoning specific to a Roth, as opposed to generic allocation advice.</p>
    ${(d.roth_notes || []).map((n) => `<div class="callout info">
      <strong>${esc(n.title)}</strong><br>${gloss(n.body)}</div>`).join('')}
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Fund universe')}</h2>
    <p class="sub">Every candidate measured over its full available history. Highlighted rows are in the model above.</p>
    <table class="data">
      <thead><tr><th>Fund</th><th>In model</th><th>Expense</th><th>CAGR (full)</th><th>5y CAGR</th><th>Volatility</th><th>Return / vol</th><th>Worst drawdown</th><th>History</th></tr></thead>
      <tbody>${fundRows}</tbody>
    </table>
  </div>

  ${corrTable ? `
  <div class="panel span2">
    <h2>${hg('Correlation')}</h2>
    <p class="sub">Daily-return correlation over ten years. Values near 1.00 (orange) mean two funds
      are the same bet in different wrappers; low values (green) are what actually diversifies.</p>
    ${corrTable}
  </div>` : ''}
  `;

  views.roth.querySelectorAll('[data-bar]').forEach((host) => {
    const max = Number(host.dataset.barMax) || 25;
    host.appendChild(inlineBar(Number(host.dataset.bar), max, 70, 9));
  });

  if (pr.available && pr.series) {
    mount('legend-roth', legend([
      { name: 'Central estimate', color: C.s1 },
      { name: 'Lower band', color: C.s2, dash: true },
      { name: 'Upper band', color: C.s3, dash: true },
      { name: 'Contributions only', color: C.s4, dash: true },
    ]));
    mount('chart-roth', (w) => lineChart({
      width: w,
      height: 300,
      labels: pr.series.map((p) => `yr ${p.year}`),
      series: [
        { name: 'Central estimate', values: pr.series.map((p) => p.balance), color: C.s1 },
        { name: 'Lower band', values: pr.series_low, color: C.s2, width: 1.5, marker: false },
        { name: 'Upper band', values: pr.series_high, color: C.s3, width: 1.5, marker: false },
        { name: 'Contributions only', values: pr.series.map((p) => p.contributed), color: C.s4, width: 1.5, marker: false },
      ],
      // The chart pads its range 8% below the lowest value, which on an
      // all-positive money series puts a tick just under zero and renders it
      // as "$-0.00". Snap sub-dollar magnitudes to a clean zero.
      yFormat: (x) => '$' + fmtCompact(Math.abs(x) < 1 ? 0 : x),
      valueFormat: (x) => '$' + Number(x).toLocaleString('en-US', { maximumFractionDigits: 0 }),
    }));
  }
}

/* ================================================================= SETTINGS */

function renderSettings() {
  hideTip();
  const zone = activeZone();
  const sess = (STATE.session || {}).session || {};
  const onMarketTime = viewerOnMarketTime();

  const themeRow = ['system', 'light', 'dark'].map((mode) => `<button type="button"
    class="seg-opt${SETTINGS.theme === mode ? ' on' : ''}" data-set-theme="${mode}"
    aria-pressed="${SETTINGS.theme === mode}">${
    mode === 'system' ? 'Follow system' : mode === 'light' ? 'Light' : 'Dark'}</button>`).join('');

  const zoneOpts = TIMEZONES.map((z) => {
    const resolved = z.id === 'auto' ? activeZone() : z.id;
    const now = timeIn(new Date().toISOString(), resolved);
    return `<option value="${esc(z.id)}"${SETTINGS.timezone === z.id ? ' selected' : ''}>${
      esc(z.label)} — ${esc(now)}</option>`;
  }).join('');

  // Market hours in the viewer's zone. Derived from the timestamps the server
  // sends with each segment, so US daylight-saving transitions are handled by the
  // server's own calendar rather than re-implemented here.
  const hoursRows = (sess.segments || [])
    .filter((seg, i, all) => all.findIndex((x) => x.phase === seg.phase) === i)
    .map((seg) => `<tr${seg.active ? ' style="background:var(--surface-2)"' : ''}>
      <td class="name"><span class="ses-dot p-${esc(seg.phase)}" style="display:inline-block;
        margin-right:7px;vertical-align:1px"></span>${esc(seg.label)}${
    seg.active ? ' <span style="color:var(--ink-muted);font-size:11px">— now</span>' : ''}</td>
      <td>${esc(timeIn(seg.start_at, 'America/New_York'))} – ${
    esc(timeIn(seg.end_at, 'America/New_York'))} ET</td>
      <td>${esc(timeIn(seg.start_at, zone))} – ${esc(timeIn(seg.end_at, zone))} ${
    esc(zoneAbbrev(zone))}</td>
    </tr>`).join('');

  views.settings.innerHTML = `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Appearance')}</h2>
    <p class="sub">Both themes are hand-picked rather than one flipped into the other, so
      contrast and colour-vision separation hold either way.</p>
    <div class="settings-row">
      <div class="settings-label">Theme
        <span class="settings-hint">“Follow system” tracks your operating system setting and
          changes with it.</span></div>
      <div class="seg">${themeRow}</div>
    </div>
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Time zone')}</h2>
    <p class="sub"><strong>US market hours are defined in Eastern Time and don't move.</strong>
      This setting only changes the clock they're displayed against, so you can see when the open
      and close land where you are.</p>
    <div class="settings-row">
      <div class="settings-label">Show times in
        <span class="settings-hint">Currently ${esc(zone)} (${esc(zoneAbbrev(zone))})${
    onMarketTime ? ' — the same as market time, so nothing is converted.' : '.'}</span></div>
      <select id="tz-select" class="settings-select">${zoneOpts}</select>
    </div>

    ${hoursRows ? `
      <h3 style="margin-top:14px">${hg('Market hours')}</h3>
      <table class="data narrow">
        <thead><tr><th>Session</th><th>Eastern (market)</th><th>Your zone</th></tr></thead>
        <tbody>${hoursRows}</tbody>
      </table>
      <p class="caveat">Overnight straddles midnight, so its two halves share one row. Daylight
        saving shifts these by an hour on different dates in different countries — the conversion
        follows each zone's own calendar rather than assuming a fixed offset.</p>
    ` : `<div class="callout">Load a ticker once and the session times will appear here.</div>`}
  </div>

  <div class="panel span2">
    <h2>${hg('About this build')}</h2>
    ${kv([
    ['Data source', 'Yahoo Finance via yfinance — quotes delayed roughly 15 minutes'],
    ['Assistant', 'Pulse is switched off in this build'],
    ['Optic\u2019s Positions', 'One shared simulated ledger, no real money'],
    ['Stored on this device', 'Theme, time zone, chart preferences and any Roth holdings you enter'],
    ['Stored on the server', 'Nothing about you'],
  ])}
    <p class="caveat">Settings live in this browser only. Clearing site data resets them.</p>
  </div>`;
}

/* ======================================================= OPTIC'S POSITIONS */

const money = (v, digits = 0) => (v === null || v === undefined || Number.isNaN(v)
  ? '—'
  : (v < 0 ? '-$' : '$') + Math.abs(Number(v)).toLocaleString('en-US', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }));

/** "NVDA $180 call · Aug 21" for an option, plain ticker for shares. */
function positionLabel(p) {
  if (p.instrument !== 'option') return `<strong>${esc(p.ticker)}</strong> shares`;
  const exp = p.expiry
    ? new Date(p.expiry + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : '';
  return `<strong>${esc(p.ticker)}</strong> $${fmt(p.strike, 0)} ${esc(p.option_type || '')}
    <div style="color:var(--ink-muted);font-size:11px">expires ${esc(exp)}</div>`;
}

/** What the trade is betting on. A long put is stored as direction "long" —
 *  correct for P&L, since the premium is owned — but "long" next to a put reads
 *  as a bullish bet, so the bias is spelled out instead. */
function sideCell(p) {
  if (p.instrument !== 'option') return esc(p.direction);
  const bias = p.option_type === 'put' ? 'bearish' : 'bullish';
  return `${bias}<div style="color:var(--ink-muted);font-size:11px">Long premium</div>`;
}

function heldDays(from, to) {
  if (!from) return null;
  const a = new Date(from).getTime();
  const b = to ? new Date(to).getTime() : Date.now();
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  return Math.max(Math.round((b - a) / 86400000), 0);
}

/** Options quote per share but trade in 100-lots, so the two instruments need
 *  different words for "how much" or the table reads as a factor-100 error. */
function sizeCell(p) {
  if (p.instrument === 'option') {
    return `${fmt(p.qty, 0)} contract${p.qty === 1 ? '' : 's'}
      <div style="color:var(--ink-muted);font-size:11px">${money(p.qty * p.entry_price * 100)} premium</div>`;
  }
  return `${fmt(p.qty, 0)} shares
    <div style="color:var(--ink-muted);font-size:11px">${money(p.qty * p.entry_price)} notional</div>`;
}

function trackerUniverseHint(cfg) {
  if (cfg.universe !== 'nasdaq') {
    return `Watchlist: ${(cfg.watchlist || []).map((x) => esc(x)).join(', ')}. A scan puts all of
      them through the full analysis.`;
  }
  return `Universe: <strong>every NASDAQ-listed common stock</strong> — about 3,000 names, from
    NASDAQ's own daily symbol directory. A scan screens all of them on price and volume, then puts
    the top ${fmt(cfg.shortlist_size, 0)} through the full analysis, so it takes a few minutes. It
    also runs on its own every few hours while the server is up.`;
}

function progressHTML(prog) {
  const pct = prog.total ? Math.min(Math.round((prog.done / prog.total) * 100), 100) : null;
  return `<div class="tracker-progress">
    <div class="tracker-progress-head">
      <span class="spinner"></span>
      <strong>${esc(prog.stage || 'working')}</strong>
      ${prog.note ? `<span class="mono">${esc(prog.note)}</span>` : ''}
      ${prog.total ? `<span class="mono">${fmt(prog.done, 0)} / ${fmt(prog.total, 0)}</span>` : ''}
      ${prog.trigger === 'scheduled' ? '<span class="chip neutral" style="padding:1px 7px"><span class="dot"></span>Scheduled</span>' : ''}
    </div>
    ${pct === null ? '' : `<div class="tracker-progress-track">
      <div class="tracker-progress-fill" style="width:${pct}%"></div></div>`}
  </div>`;
}

/** The funnel from the last real scan. Shown because "we scan the whole NASDAQ"
 *  and "we analysed 30 names" are both true, and only showing one of them would
 *  misrepresent the other. */
function funnelPanelHTML(f, gates, cfg) {
  const sc = f.screen || {};
  const rows = (f.shortlist || []).map((m, i) => `<tr${m.analysed ? '' : ' style="opacity:0.5"'}>
    <td style="color:var(--ink-muted)">${i + 1}</td>
    <td class="name"><strong>${esc(m.symbol)}</strong></td>
    <td class="${signClass(m.score)}">${m.score > 0 ? '+' : ''}${fmt(m.score, 0)}</td>
    <td>${fmt(m.price, 2)}</td>
    <td>$${fmtCompact(m.dollar_volume, 0)}</td>
    <td class="${signClass(m.roc20)}">${fmtPct(m.roc20, 1)}</td>
    <td style="color:var(--ink-muted);font-size:11px">${m.analysed ? 'Analysed' : 'Not reached'}</td>
  </tr>`).join('');

  return `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('How the shortlist was chosen')}</h2>
    <p class="sub">${esc(f.universe_source || '')}</p>

    <div class="funnel">
      ${[
    ['Listed', sc.universe_size, 'NASDAQ common stocks'],
    ['Had usable data', sc.with_data, 'a year of daily bars'],
    ['Passed liquidity', sc.passed, `over $${fmtCompact(gates.min_dollar_volume, 0)} a day`],
    ['Analysed', f.shortlist ? (f.shortlist.filter((m) => m.analysed).length || 0) : 0,
      'full swing composite'],
  ].map(([label, value, note]) => `<div class="funnel-step">
        <span class="funnel-value">${fmt(value, 0)}</span>
        <span class="funnel-label">${esc(label)}</span>
        <span class="funnel-note">${esc(note)}</span>
      </div>`).join('<span class="funnel-arrow">→</span>')}
    </div>

    <p class="caveat" style="margin-top:2px">Dropped along the way:
      ${fmt(sc.dropped_illiquid, 0)} too thinly traded,
      ${fmt(sc.dropped_short_history, 0)} without a year of history,
      ${fmt(sc.dropped_too_volatile, 0)} moving more than ${fmt(gates.max_atr_pct, 0)}% a day,
      ${fmt(sc.dropped_already_moved, 0)} already up or down more than
      ${fmt(gates.max_abs_1m_move_pct, 0)}% in a month.
      ${sc.already_held ? `${fmt(sc.already_held, 0)} ranked well but are already held.` : ''}</p>
    ${sc.failed_batches ? `<div class="callout">${fmt(sc.failed_batches, 0)} batch(es) of about
      ${fmt(150, 0)} symbols each never returned data, even after a retry — almost always the free
      feed's rate limit. Those names weren't screened at all, so this ranking covers slightly less
      than the whole exchange.</div>` : ''}
    ${f.throttled_skips ? `<div class="callout">${fmt(f.throttled_skips, 0)} shortlisted name(s) were
      skipped because the feed was still rate-limiting when their options chain was requested. They
      weren't traded on partial data.</div>` : ''}

    <h3>${hg('Screen ranking')}</h3>
    <p class="sub">Top ${fmt((f.shortlist || []).length, 0)} by absolute score. Greyed rows ranked
      high enough but weren't reached — the scan stopped when a cap bound.</p>
    <table class="data">
      <thead><tr><th>#</th><th>Symbol</th><th>Screen score</th><th>Price ($)</th>
        <th>$ volume/day</th><th>1-month</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${f.capped ? `<div class="callout">Stopped early — ${esc(f.capped)}.</div>` : ''}
    <p class="caveat">${gloss(sc.caveat || '')}</p>
  </div>`;
}

function renderTracker(d) {
  hideTip();
  const t = d || {};
  if (t.error) { views.tracker.innerHTML = errorHTML(t.error); return; }

  const s = t.summary || {};
  const cfg = t.config || {};
  const capacity = t.capacity || {};
  const open = t.open || [];
  const closed = t.closed || [];
  const prog = t.progress || {};
  // The server is the source of truth on whether a scan is running: a background
  // scheduled scan can be in flight without this browser having started it.
  const scanning = !!prog.running || !!STATE.trackerScanning;
  const gates = cfg.screen_gates || {};
  const feed = t.feed || {};
  const marketOpen = !!t.market_open;
  // The most recent scan that actually screened a universe. A manual "look at
  // these tickers" run has no funnel, and shouldn't blank out the last real one.
  const lastFunnel = (t.scans || []).map((x) => x.funnel)
    .find((f) => f && f.screen && f.screen.universe_size);

  const openRows = open.map((p) => `<tr>
    <td class="name">${positionLabel(p)}</td>
    <td>${cap(sideCell(p))}</td>
    <td>${sizeCell(p)}</td>
    <td>${fmt(p.entry_price, 2)}
      <div style="color:var(--ink-muted);font-size:11px">${new Date(p.entry_at).toLocaleDateString()}</div></td>
    <td>${fmt(p.mark_price, 2)}
      <div style="color:var(--ink-muted);font-size:11px">${esc(cap(p.mark_source) || '—')}</div></td>
    <td>${fmt(p.stop, 2)}</td>
    <td>${fmt(p.target, 2)}</td>
    <td class="${signClass(p.pnl)}"><strong>${money(p.pnl, 0)}</strong>
      <div style="font-size:11px">${fmtPct(p.pnl_pct, 1)}</div></td>
    <td>${money(p.risk_dollars, 0)}</td>
    <td>${fmt(p.composite, 0)}</td>
    <td>${heldDays(p.entry_at) === null ? '—' : heldDays(p.entry_at) + 'd'}</td>
  </tr>`).join('');

  const closedRows = closed.map((p) => `<tr>
    <td class="name">${positionLabel(p)}</td>
    <td>${cap(sideCell(p))}</td>
    <td>${sizeCell(p)}</td>
    <td>${fmt(p.entry_price, 2)}</td>
    <td>${fmt(p.exit_price, 2)}</td>
    <td class="${signClass(p.pnl)}"><strong>${money(p.pnl, 0)}</strong>
      <div style="font-size:11px">${fmtPct(p.pnl_pct, 1)}</div></td>
    <td>${esc(cap(p.exit_reason) || '—')}</td>
    <td>${heldDays(p.entry_at, p.exit_at) === null ? '—' : heldDays(p.entry_at, p.exit_at) + 'd'}</td>
    <td>${p.exit_at ? new Date(p.exit_at).toLocaleDateString() : '—'}</td>
  </tr>`).join('');

  // Notes get their own full-width row rather than a sixth column: they include
  // the reason a leg was declined, which is the useful part and far too long to
  // read in a cell squeezed off the right edge of a scrolling table.
  const scanRows = (t.scans || []).map((sc) => `<tr>
    <td class="name">${new Date(sc.ran_at).toLocaleString()}</td>
    <td>${esc(cap(sc.trigger))}</td>
    <td>${fmt(sc.considered, 0)}</td>
    <td>${fmt(sc.opened, 0)}</td>
    <td>${fmt(sc.closed, 0)}</td>
  </tr>
  <tr><td colspan="5" style="color:var(--ink-muted);font-size:11.5px;line-height:1.6;
      padding-top:0;white-space:normal">
    ${esc(cap((sc.notes || []).join(' · ')) || 'Nothing cleared the bar')}
    ${(sc.funnel || {}).screen && sc.funnel.screen.ranking_reused
    ? `<div style="margin-top:3px">Screen ranking reused from
        ${fmt(sc.funnel.screen.ranking_age_minutes, 0)} minutes earlier — daily bars don't change
        intraday, and re-downloading the exchange is what earns a rate limit.</div>` : ''}
  </td></tr>`).join('');

  const months = t.months || [];
  const mo = t.month || {};
  const moStats = months.find((m) => m.key === (t.selected_month || mo.key)) || {};
  const viewingCurrent = !!mo.is_current;

  const monthPicker = months.length ? `<select id="tracker-month" class="settings-select"
    style="flex:0 1 210px" aria-label="Month to show">
      ${months.slice().reverse().map((m) => `<option value="${esc(m.key)}"${
    m.key === (t.selected_month || '') ? ' selected' : ''}>${esc(m.label)}${
    m.key === months[months.length - 1].key ? ' (current)' : ''}</option>`).join('')}
    </select>` : '';

  // Month-by-month, oldest first. The point is the shape of the run, not any one
  // number — a single good month and six flat ones is a different thing from six
  // consistent ones, and an all-time total hides which you're looking at.
  const monthRows = months.slice().reverse().map((m) => `<tr${
    m.key === (t.selected_month || '') ? ' style="background:var(--surface-2)"' : ''}>
    <td class="name">${esc(m.label)}${m.key === months[months.length - 1].key
    ? ' <span style="color:var(--ink-muted);font-size:11px">— in progress</span>' : ''}</td>
    <td>${fmt(m.opened_count, 0)}</td>
    <td>${fmt(m.closed_count, 0)}</td>
    <td class="${signClass(m.realised_pnl)}"><strong>${money(m.realised_pnl, 0)}</strong></td>
    <td class="${signClass(m.return_pct)}">${fmtPct(m.return_pct, 2)}</td>
    <td>${m.win_rate_pct === null || m.win_rate_pct === undefined
    ? '—' : fmt(m.win_rate_pct, 0) + '%'}</td>
    <td class="${signClass(m.expectancy)}">${money(m.expectancy, 0)}</td>
    <td>${fmt(m.profit_factor, 2)}</td>
    <td>${money(m.end_equity, 0)}</td>
  </tr>`).join('');

  const monthClosedRows = (mo.closed || []).map((p) => `<tr>
    <td class="name">${positionLabel(p)}</td>
    <td>${sideCell(p)}</td>
    <td>${fmt(p.entry_price, 2)}</td>
    <td>${fmt(p.exit_price, 2)}</td>
    <td class="${signClass(p.pnl)}"><strong>${money(p.pnl, 0)}</strong>
      <div style="font-size:11px">${fmtPct(p.pnl_pct, 1)}</div></td>
    <td>${esc(cap(p.exit_reason) || '—')}</td>
    <td>${p.exit_at ? new Date(p.exit_at).toLocaleDateString() : '—'}</td>
  </tr>`).join('');

  const monthOpenRows = (mo.still_open || []).map((p) => `<tr>
    <td class="name">${positionLabel(p)}</td>
    <td>${sideCell(p)}</td>
    <td>${sizeCell(p)}</td>
    <td>${fmt(p.entry_price, 2)}</td>
    <td>${fmt(p.mark_price, 2)}</td>
    <td class="${signClass(p.pnl)}"><strong>${money(p.pnl, 0)}</strong>
      <div style="font-size:11px">${fmtPct(p.pnl_pct, 1)}</div></td>
    <td>${heldDays(p.entry_at) === null ? '—' : heldDays(p.entry_at) + 'd'}</td>
  </tr>`).join('');

  const empty = !open.length && !closed.length;

  views.tracker.innerHTML = `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg("Optic's Positions")}</h2>
    <p class="sub">One shared, simulated ledger — the same record for everyone who opens this page.
      It trades the terminal's own signals with fixed rules, in both instruments the Swing tab
      produces: the shares, and the exact option contract it recommended.</p>

    <div class="tracker-bar">
      <button class="btn primary" type="button" id="tracker-scan" ${scanning ? 'disabled' : ''}>
        ${scanning ? 'Scan running…' : 'Run a scan now'}</button>
      <button class="btn" type="button" id="tracker-mark" ${scanning ? 'disabled' : ''}>Refresh marks</button>
      <span class="tracker-hint">${trackerUniverseHint(cfg)}</span>
    </div>

    ${marketOpen ? '' : `<div class="callout" style="margin-top:10px">
      <strong>The market is closed.</strong> Open positions are still re-marked at the closing
      price, but no new entries are taken while the tape is shut — a fill at a stale price isn't a
      trade anyone could have got. Scanning resumes at the next open (9:30am ET, weekdays).</div>`}

    ${scanning ? progressHTML(prog) : ''}
    ${feed.throttled ? `<div class="callout bad" style="margin-top:10px">
      <strong>The price feed is rate-limiting right now.</strong> Screening thousands of symbols on a
      free data feed earns a temporary block, and a blocked options request comes back looking like
      a stock with no options at all. Optic skips those names rather than opening a
      shares-only trade and recording it as what was recommended — so a scan during a block will
      take fewer positions, not wrong ones. Clears in about
      ${fmt(feed.seconds_remaining, 0)}s.</div>` : ''}

    <div class="grid c4" style="margin:12px 0">
      ${tile('Equity', money(s.equity), `started at ${money(s.start_equity)}`, signClass(s.realised_pnl))}
      ${tile('Realised P&L', money(s.realised_pnl), `${s.closed_count || 0} closed trades`, signClass(s.realised_pnl))}
      ${tile('Unrealised P&L', money(s.unrealised_pnl), `${s.open_count || 0} open now`, signClass(s.unrealised_pnl))}
      ${tile('Total return', fmtPct(s.return_pct, 2), 'realised plus open marks', signClass(s.return_pct))}
    </div>
    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Position slots', `${capacity.open_positions || 0} / ${cfg.max_open_positions || '—'}`,
    `${capacity.position_slots_left || 0} left`)}
      ${tile('Risk deployed', money(capacity.open_risk, 0),
    `${fmt(capacity.open_risk_pct, 1)}% of a ${fmt(cfg.max_portfolio_risk_pct, 0)}% budget`)}
      ${tile('Risk budget left', money(capacity.risk_budget_left, 0), 'before the book stops adding')}
      ${tile('New per scan', fmt(cfg.max_new_per_scan, 0), 'so the book fills over days')}
    </div>
    <p class="caveat">Equity counts closed trades only. Open positions are shown but deliberately kept
      out of the sizing calculation, so an unrealised run-up can't quietly increase the size of the
      next bet. The caps exist because the universe is the whole exchange — without them one scan
      could find thirty qualifying setups and put a third of the account at risk in an afternoon, on
      names that are mostly the same momentum bet under different tickers.</p>
  </div>

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Month by month')}</h2>
    <p class="sub">Results split by the month a trade <em>closed</em> — the month the money was
      actually made or lost. A position opened in one month and closed in the next counts toward the
      month it closed in, and appears in the earlier month's opened count.</p>

    <div class="tracker-bar" style="margin-bottom:12px">
      ${monthPicker}
      <span class="tracker-hint">Showing <strong>${esc(mo.label || '—')}</strong>${
    viewingCurrent ? ' — still in progress, so these figures are not final.' : '.'}
        The record runs from ${esc(months.length ? months[0].label : 'this month')} and includes
        every trade the ledger has taken, nothing excluded.</span>
    </div>

    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Closed this month', fmt(moStats.closed_count, 0),
    `${fmt(moStats.opened_count, 0)} position${moStats.opened_count === 1 ? '' : 's'} opened`)}
      ${tile('Realised P&L', money(moStats.realised_pnl, 0),
    `from ${fmt(moStats.closed_count, 0)} closed`, signClass(moStats.realised_pnl))}
      ${tile('Return', fmtPct(moStats.return_pct, 2),
    `on ${money(moStats.start_equity, 0)} at the start`, signClass(moStats.return_pct))}
      ${tile('Expectancy', money(moStats.expectancy, 0), 'average per closed trade',
    signClass(moStats.expectancy))}
    </div>

    ${monthClosedRows ? `
      <h3>${hg('Closed in this month')}</h3>
      <table class="data">
        <thead><tr><th>Position</th><th>Side</th><th>Entry</th><th>Exit</th><th>P&amp;L</th>
          <th>Why it closed</th><th>Closed</th></tr></thead>
        <tbody>${monthClosedRows}</tbody>
      </table>` : `<div class="callout">No trades closed in ${esc(mo.label || 'this month')}.${
    viewingCurrent ? ' Positions opened this month are still running.' : ''}</div>`}

    ${monthOpenRows ? `
      <h3 style="margin-top:14px">${hg('Opened in this month and still held')}</h3>
      <table class="data">
        <thead><tr><th>Position</th><th>Side</th><th>Size</th><th>Entry</th><th>Mark</th>
          <th>P&amp;L</th><th>Held</th></tr></thead>
        <tbody>${monthOpenRows}</tbody>
      </table>
      <p class="caveat">Unrealised. These carry into whichever month they eventually close in.</p>
    ` : ''}

    ${months.length > 1 ? `
      <h3 style="margin-top:16px">${hg('Consistency')}</h3>
      <table class="data">
        <thead><tr><th>Month</th><th>Opened</th><th>Closed</th><th>Realised</th><th>Return</th>
          <th>Win rate</th><th>Expectancy</th><th>Profit factor</th><th>Equity after</th></tr></thead>
        <tbody>${monthRows}</tbody>
      </table>
      <p class="caveat">${gloss('Equity after carries forward, so each month\u2019s return is '
    + 'measured against what the account was worth when that month began rather than against the '
    + 'original stake. A month with no closed trades is still a row — taking nothing is a '
    + 'decision, and hiding it would flatter the record.')}</p>
    ` : `<p class="caveat">One month of record so far. A consistency table needs several months
      before it says anything — treat a single month, good or bad, as noise.</p>`}
  </div>

  ${lastFunnel ? funnelPanelHTML(lastFunnel, gates, cfg) : ''}

  ${empty ? `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>No trades yet</h2>
    <p class="sub">The ledger is empty. It only opens a position when a setup clears a composite score
      of ${fmt(cfg.min_composite, 0)}, and most scans find nothing — which is the intended behaviour,
      not a fault. Run a scan above, or wait for the background one.</p>
  </div>` : ''}

  ${s.closed_count ? `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Track record')}</h2>
    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Expectancy', money(s.expectancy, 0), 'average result per closed trade', signClass(s.expectancy))}
      ${tile('Win rate', s.win_rate_pct === null ? '—' : fmt(s.win_rate_pct, 0) + '%', `${s.win_count} of ${s.closed_count}`)}
      ${tile('Average win', money(s.avg_win, 0), s.win_count ? `across ${s.win_count}` : 'none yet', 'up')}
      ${tile('Average loss', money(s.avg_loss, 0), s.loss_count ? `across ${s.loss_count}` : 'none yet', 'down')}
    </div>
    <div class="grid c4">
      ${tile('Profit factor', fmt(s.profit_factor, 2), 'gross wins ÷ gross losses')}
      ${tile('Closed trades', fmt(s.closed_count, 0), 'the only results that are final')}
      ${tile('Winners', fmt(s.win_count, 0), null, 'up')}
      ${tile('Losers', fmt(s.loss_count, 0), null, 'down')}
    </div>
    <p class="caveat">${gloss('A sample this small says almost nothing yet. Win rate on its own is the '
    + 'least useful number here — expectancy, the average result per trade, is what decides whether '
    + 'there is an edge. Treat anything under about fifty closed trades as noise.')}</p>
  </div>` : ''}

  ${open.length ? `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Open positions')}</h2>
    <p class="sub">Marked at the latest available price. Options are looked up in the live chain each
      time; when a contract has no usable quote the mark falls back to a Black-Scholes estimate and
      the row says so.</p>
    <table class="data">
      <thead><tr><th>Position</th><th>Side</th><th>Size</th><th>Entry</th><th>Mark</th>
        <th>Stop</th><th>Target</th><th>P&amp;L</th><th>Risk</th><th>Score</th><th>Held</th></tr></thead>
      <tbody>${openRows}</tbody>
    </table>
    <p class="caveat">Stop and target are prices on the <em>underlying</em> for both instruments. An
      option also carries its own premium-based exits at −50% and +100%, because the stock can sit
      still while time decay drains the position.</p>
  </div>` : ''}

  ${closed.length ? `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Closed trades')}</h2>
    <p class="sub">Most recent first. The exit reason is the honest part of the record — a table full
      of time stops means the signals were early, not unlucky.</p>
    <table class="data">
      <thead><tr><th>Position</th><th>Side</th><th>Size</th><th>Entry</th><th>Exit</th>
        <th>P&amp;L</th><th>Why it closed</th><th>Held</th><th>Closed</th></tr></thead>
      <tbody>${closedRows}</tbody>
    </table>
  </div>` : ''}

  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('How these positions are taken')}</h2>
    <p class="sub">Fixed rules, set in advance and applied identically to every ticker. Written down
      here so the record can't be improved after the fact by changing its mind.</p>
    <div class="grid c2">
      <div>
        <h3>${hg('Position sizing')}</h3>
        ${kv([
    ['Account', money(s.start_equity) + ' notional'],
    ['Risk per share trade', fmt(cfg.risk_per_trade_pct, 1) + '% of equity'],
    ['Max risk per option trade', fmt(cfg.max_option_risk_pct, 1) + '% of equity'],
    ['Single-contract exception', 'up to ' + fmt(cfg.option_single_contract_cap_pct, 0) + '% of equity'],
    ['Share position cap', '25% of equity in notional'],
    ['Open positions', 'at most ' + fmt(cfg.max_open_positions, 0)],
    ['Total risk deployed', 'at most ' + fmt(cfg.max_portfolio_risk_pct, 0) + '% of equity'],
    ['New positions per scan', 'at most ' + fmt(cfg.max_new_per_scan, 0)],
  ])}
        <p class="caveat">Shares are sized so that being stopped out costs exactly the risk budget —
          a wide stop therefore buys fewer shares, not more risk. Options are sized on the whole
          premium, because a long option can genuinely go to zero and a stop cannot prevent it.</p>
      </div>
      <div>
        <h3>Entries and exits</h3>
        ${kv([
    ['Universe', cfg.universe === 'nasdaq' ? 'every NASDAQ common stock (~3,000)' : 'fixed watchlist'],
    ['Screened down to', fmt(cfg.shortlist_size, 0) + ' names per scan'],
    ['Takes a trade when', 'composite score ≥ ' + fmt(cfg.min_composite, 0) + ' (either direction)'],
    ['Stop', 'Just beyond the nearest real support or resistance level, or twice the average daily range if none is close'],
    ['Target', 'twice the risk distance — fixed, not fitted'],
    ['Option exits', '−50% / +100% premium, underlying stop, or expiry'],
    ['Time stop', fmt(cfg.max_hold_days, 0) + ' days'],
    ['Per ticker', 'one idea at a time'],
    ['Trades only', 'during the regular session, 9:30–4:00 ET'],
  ])}
      </div>
    </div>
    <div class="callout bad" style="margin-top:12px">
      <strong>What these numbers are not.</strong>
      <ul style="margin:6px 0 0 16px;padding:0">
        ${(t.caveats || []).map((c) => `<li>${gloss(c)}</li>`).join('')}
      </ul>
    </div>
  </div>

  ${scanRows ? `
  <div class="panel span2">
    <h2>${hg('Scan history')}</h2>
    <table class="data">
      <thead><tr><th>Ran</th><th>Trigger</th><th>Considered</th><th>Opened</th><th>Closed</th></tr></thead>
      <tbody>${scanRows}</tbody>
    </table>
  </div>` : ''}`;
}

/* ================================================================== INDICES */

function renderIndices(d) {
  hideTip();
  const idx = d || {};
  const gvm = idx.growth_vs_market || {};
  if (idx.error) { views.indices.innerHTML = errorHTML(idx.error); return; }

  views.indices.innerHTML = `
  <div class="panel span2" style="margin-bottom:14px">
    <h2>${hg('Index regime')}</h2>
    <p class="sub">${gloss(idx.regime_summary || '')}</p>
    <table class="data">
      <thead><tr><th>Index</th><th>Last</th><th>1y</th><th>3y CAGR</th><th>5y CAGR</th><th>10y CAGR</th><th>vs 40w</th><th>vs 200w</th><th>Wk RSI</th><th>Drawdown</th><th>Phase</th></tr></thead>
      <tbody>${(idx.indices || []).map((r) => `<tr>
        <td class="name">${esc(r.name)}<div style="color:var(--ink-muted);font-size:11px">${esc(r.note || '')}</div></td>
        <td>${fmt(r.last, 2)}</td>
        <td class="${signClass(r.return_1y_pct)}">${fmtPct(r.return_1y_pct, 1)}</td>
        <td class="${signClass(r.cagr_3y_pct)}">${fmtPct(r.cagr_3y_pct, 1)}</td>
        <td class="${signClass(r.cagr_5y_pct)}">${fmtPct(r.cagr_5y_pct, 1)}</td>
        <td class="${signClass(r.cagr_10y_pct)}">${fmtPct(r.cagr_10y_pct, 1)}</td>
        <td class="${signClass(r.vs_40w_sma)}">${fmtPct(r.vs_40w_sma, 1)}</td>
        <td class="${signClass(r.vs_200w_sma)}">${fmtPct(r.vs_200w_sma, 1)}</td>
        <td>${fmt(r.weekly_rsi, 0)}</td>
        <td class="${signClass(r.current_drawdown_pct)}">${fmtPct(r.current_drawdown_pct, 1)}</td>
        <td class="name">${esc(cap(r.phase) || '')}</td>
      </tr>`).join('')}</tbody>
    </table>
    <p class="caveat">CAGR is the annualized rate of return over the period, so a 10-year
      figure smooths through crashes rather than hiding them — check the drawdown column alongside it.</p>
  </div>

  ${gvm.series ? `
  <div class="panel span2">
    <h2>${hg('Growth vs the broad market (QQQ / SPY)')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— daily</span></h2>
    <p class="sub">${gloss(gvm.note || '')}</p>
    <div class="grid c2" style="margin-bottom:6px">
      ${tile('QQQ / SPY ratio', fmt(gvm.qqq_spy_ratio, 3), 'rising means growth is leading')}
      ${tile('Over 3 months', fmtPct(gvm.chg_3m_pct, 1), 'growth vs broad market', signClass(gvm.chg_3m_pct))}
    </div>
    <div id="chart-growth-value"></div>
  </div>` : ''}
  `;

  if (gvm.series) {
    mount('chart-growth-value', (w) => lineChart({
      width: w,
      height: 190,
      labels: gvm.dates || [],
      series: [{ name: 'QQQ / SPY', values: gvm.series, color: C.s7, fill: true }],
      yFormat: (x) => fmt(x, 3),
    }));
  }
}

/* ================================================================ LONG TERM */

function renderLong(d) {
  hideTip();
  const h = d.holding || {};
  const lt = h.long_trend || {};
  const dd = h.drawdown || {};
  const risk = h.risk || {};
  const val = h.valuation || {};

  if (h.error) { views.long.innerHTML = errorHTML(h.error); return; }

  views.long.innerHTML = `
  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Long-term view')} — ${esc(h.ticker)}</h2>
      <p class="sub">${esc(h.name || '')}${(h.fundamentals || {}).sector ? ' · ' + esc(h.fundamentals.sector) : ''}</p>
      <div style="display:flex;align-items:flex-end;gap:20px;flex-wrap:wrap">
        <div>
          <div class="hero-label">Conviction</div>
          <div class="hero ${signClass(h.conviction_score)}">${h.conviction_score > 0 ? '+' : ''}${fmt(h.conviction_score, 0)}</div>
          <div class="note" style="color:var(--ink-muted);font-size:12px">Of a possible
            +${fmt((h.conviction_scale || {}).max_possible, 0)}</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          ${toneChip(h.conviction)}
          <span class="chip neutral"><span class="dot"></span>${esc(cap(lt.phase) || '')}</span>
        </div>
      </div>
      <div class="callout info">${gloss(h.plan || '')}</div>
      ${((h.data_quality || {}).warnings || []).map((w) => `<div class="callout bad">${gloss(w)}</div>`).join('')}

      <h3>${hg('What makes up this score')}</h3>
      <p class="sub">Every factor the model checked and what each one contributed. Mostly price
        behaviour — the valuation and income factors can add at most 13 of the
        ${fmt((h.conviction_scale || {}).max_possible, 0)} available points.</p>
      <table class="data">
        <thead><tr><th>Factor</th><th>Type</th><th>Points</th><th>Why</th></tr></thead>
        <tbody>${(h.conviction_factors || []).map((f) => `<tr>
          <td class="name">${esc(cap(f.label))}</td>
          <td style="color:var(--ink-muted)">${esc(cap(f.kind))}</td>
          <td class="${signClass(f.points)}"><strong>${f.points > 0 ? '+' : ''}${fmt(f.points, 0)}</strong></td>
          <td style="color:var(--ink-2);font-size:12.5px">${gloss(f.detail)}</td>
        </tr>`).join('')}
        <tr style="border-top:1px solid var(--border-strong)">
          <td class="name"><strong>Total</strong></td><td></td>
          <td class="${signClass(h.conviction_score)}"><strong>${h.conviction_score > 0 ? '+' : ''}${fmt(h.conviction_score, 0)}</strong></td>
          <td style="color:var(--ink-muted);font-size:12.5px">${
  (h.conviction_scale || {}).thresholds
    ? 'High at ' + h.conviction_scale.thresholds.high + '+, moderate at ' + h.conviction_scale.thresholds.moderate + '+' : ''}</td>
        </tr></tbody>
      </table>
      <p class="caveat">This is a trend-and-relative-strength model with a valuation sanity
        check — not a fundamental analysis. A strong score means the price behaviour has been
        strong, not that the business is cheap or high quality.</p>
      <p class="caveat">${esc(h.disclaimer || '')}</p>
    </div>

    <div class="panel">
      <h2>${hg('Return & risk')}</h2>
      <p class="sub">Compound growth by horizon, against ${esc('SPY')} as the benchmark.</p>
      <div class="grid c4" style="margin-bottom:12px">
        ${tile('1-year', fmtPct((h.horizons || {}).return_1y_pct, 1), null, signClass((h.horizons || {}).return_1y_pct))}
        ${tile('3-year CAGR', fmtPct((h.horizons || {}).cagr_3y_pct, 1), null, signClass((h.horizons || {}).cagr_3y_pct))}
        ${tile('5-year CAGR', fmtPct((h.horizons || {}).cagr_5y_pct, 1), null, signClass((h.horizons || {}).cagr_5y_pct))}
        ${tile('vs SPY (5y)', fmtPct(h.excess_cagr_5y_pct, 1), `SPY ${fmtPct(h.benchmark_cagr_5y_pct, 1)}`, signClass(h.excess_cagr_5y_pct))}
      </div>
      ${kv([
    ['Annualized volatility', fmt(risk.annualised_vol_pct, 1) + '%'],
    ['Downside volatility', fmt(risk.downside_vol_pct, 1) + '%'],
    ['Return / vol (1y)', fmt(risk.sharpe_proxy, 2)],
    ['Sortino proxy', fmt(risk.sortino_proxy, 2)],
    ['Beta vs SPY', fmt(risk.beta_vs_spy, 2)],
    ['Correlation vs SPY', fmt(risk.correlation_vs_spy, 2)],
    ['Positive days', fmt(risk.pct_positive_days, 1) + '%'],
    ['Best / worst day', `${fmtPct(risk.best_day_pct, 1)} / ${fmtPct(risk.worst_day_pct, 1)}`],
  ])}
      <p class="caveat">Return/vol and Sortino use a zero risk-free rate — a relative screen, not a performance report.</p>
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel span2">
      <h2>${hg('Weekly structure')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— weekly bars</span></h2>
      <p class="sub">${gloss(lt.guidance || '')} Weekly bars with the 40-week and 200-week averages — the lines that separate secular bull from bear phases.</p>
      <div id="legend-weekly"></div>
      <div id="chart-weekly"></div>
      <div class="grid c3" style="margin-top:12px">
        ${tile('vs 40-week SMA', fmtPct(lt.vs_40w_sma, 1), `level ${fmt(lt.sma_40w, 2)}`, signClass(lt.vs_40w_sma))}
        ${tile('vs 200-week SMA', fmtPct(lt.vs_200w_sma, 1), `level ${fmt(lt.sma_200w, 2)}`, signClass(lt.vs_200w_sma))}
        ${tile('Weekly RSI', fmt(lt.weekly_rsi, 1), '40-week slope ' + fmtPct(lt.slope_40w_pct_3m, 1))}
      </div>
    </div>
  </div>

  <div class="grid c2" style="margin-bottom:14px">
    <div class="panel">
      <h2>${hg('Drawdown')} <span style="color:var(--ink-muted);font-weight:400;text-transform:none;letter-spacing:0">— daily</span></h2>
      <p class="sub">Currently ${fmtPct(dd.current_drawdown_pct, 1)} from the all-time high of ${usd(dd.all_time_high)}, set on ${esc(dd.ath_date || '')}.
        Worst on record: ${fmtPct(dd.max_drawdown_pct, 1)} (${esc(dd.max_drawdown_date || '')}).</p>
      <div id="chart-drawdown"></div>
    </div>

    <div class="panel">
      <h2>${hg('Valuation & accumulation')}</h2>
      <ul class="reasons">${(val.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>
      <p class="caveat">${esc(val.caveat || '')}</p>
      <h3>${hg('Accumulation zones')}</h3>
      <table class="data">
        <thead><tr><th>Level</th><th>Price ($)</th><th>Distance</th><th>Role</th></tr></thead>
        <tbody>${(h.accumulation_zones || []).map((z) => `<tr>
          <td class="name" style="white-space:normal">${esc(cap(z.label))}</td>
          <td>${fmt(z.price, 2)}</td>
          <td class="${signClass(z.distance_pct)}">${fmtPct(z.distance_pct, 1)}</td>
          <td class="name" style="color:var(--ink-muted)">${esc(cap(z.kind))}</td>
        </tr>`).join('')}</tbody>
      </table>
      ${kv([
    ['Dividend yield', val.dividend_yield !== null && val.dividend_yield !== undefined ? fmt(val.dividend_yield * 100, 2) + '%' : '—'],
    ['Forward P/E', fmt(val.forward_pe, 1)],
    ['Trailing P/E', fmt(val.trailing_pe, 1)],
    ['Price / book', fmt(val.price_to_book, 2)],
    ['Analyst mean target', usd((h.fundamentals || {}).analyst_target)],
  ])}
    </div>
  </div>

  `;

  if (lt.weekly_closes) {
    const n = lt.weekly_closes.length;
    // Accumulation zones already include the 40w/200w averages — those get
    // their own dedicated lines below, so only the retracement-based zones
    // (support/resistance from the 3-year range) are added from this list,
    // to avoid drawing the same level twice.
    const zoneRefs = (h.accumulation_zones || [])
      .filter((z) => z.price && !/average/i.test(z.label || ''))
      .map((z) => ({
        value: z.price,
        // "38.2%" on its own reads like a return, not a price level.
        label: `${z.label.replace(' retracement of the 3-year range', '')} pullback · ${usd(z.price)}`,
        color: C.refSR,
        pattern: '6 4',
      }));

    mount('legend-weekly', legend([
      { name: 'Weekly close', color: C.s1 },
      { name: '40-week SMA', color: C.s2, dash: true },
      { name: '200-week SMA', color: C.s4, dash: true },
      { name: 'Support / resistance', color: C.refSR, dash: true },
    ]));
    mount('chart-weekly', (w) => lineChart({
      width: w,
      height: 280,
      labels: lt.weekly_dates || [],
      series: [{ name: 'Weekly close', values: lt.weekly_closes, color: C.s1 }],
      refLines: [
        lt.sma_40w ? { value: lt.sma_40w, label: `40-week average ${usd(lt.sma_40w)}`, color: C.s2 } : null,
        lt.sma_200w ? { value: lt.sma_200w, label: `200-week average ${usd(lt.sma_200w)}`, color: C.s4 } : null,
        ...zoneRefs,
      ].filter(Boolean),
      yFormat: (x) => fmt(x, 0),
      valueFormat: (x) => fmt(x, 2),
    }));
  }

  if (dd.series) {
    mount('chart-drawdown', (w) => lineChart({
      width: w,
      height: 190,
      labels: dd.dates || [],
      series: [{ name: 'Drawdown from high', values: dd.series, color: C.s8, fill: true }],
      yFormat: (x) => fmt(x, 0) + '%',
      valueFormat: (x) => fmt(x, 2) + '%',
      zeroLine: true,
    }));
  }
}

/* =================================================================== LOADER */

async function loadSwing(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.swing && STATE.swing.ticker === STATE.ticker && !force) { revealPanels(views.swing); return; }
  if (!silent) views.swing.innerHTML = loadingHTML(`options analytics for ${STATE.ticker}`);
  try {
    const data = await getJSON(`/api/ticker/${encodeURIComponent(STATE.ticker)}?max_expiries=4&macro=true`);
    STATE.swing = data;
    if (data.macro && !data.macro.error) {
      STATE.market = STATE.market || {};
      STATE.market.macro = data.macro;
    }
    renderSwing(data);
    if (!silent) revealPanels(views.swing);
    updateStatus();
    updateChatContext();
  } catch (err) {
    // A background refresh tick shouldn't wipe out a perfectly good dashboard
    // over one transient network blip — only a manual/foreground load does.
    if (!silent) views.swing.innerHTML = errorHTML(err.message);
    else console.warn('Silent swing refresh failed:', err.message);
  }
}

async function loadMarket(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.market && STATE.market.sectors && !force) { renderMarket(STATE.market); revealPanels(views.market); return; }
  if (!silent) views.market.innerHTML = loadingHTML('macro and sector data (this pulls ~40 symbols)');
  try {
    const data = await getJSON('/api/market');
    STATE.market = data;
    renderMarket(data);
    if (!silent) revealPanels(views.market);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.market.innerHTML = errorHTML(err.message);
    else console.warn('Silent market refresh failed:', err.message);
  }
}

async function loadLong(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.long && STATE.long.ticker === STATE.ticker && !force) { renderLong(STATE.long); revealPanels(views.long); return; }
  if (!silent) views.long.innerHTML = loadingHTML(`10-year history for ${STATE.ticker} and the major indices`);
  try {
    const data = await getJSON(`/api/longterm/${encodeURIComponent(STATE.ticker)}?indices=false`);
    data.ticker = STATE.ticker;
    STATE.long = data;
    renderLong(data);
    if (!silent) revealPanels(views.long);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.long.innerHTML = errorHTML(err.message);
    else console.warn('Silent long-term refresh failed:', err.message);
  }
}

async function loadScalp(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.scalp && STATE.scalp.ticker === STATE.ticker && !force) { renderScalp(STATE.scalp); revealPanels(views.scalp); return; }
  if (!silent) views.scalp.innerHTML = loadingHTML(`intraday data for ${STATE.ticker}`);
  try {
    const data = await getJSON(`/api/scalp/${encodeURIComponent(STATE.ticker)}`);
    data.ticker = STATE.ticker;
    STATE.scalp = data;
    renderScalp(data);
    if (!silent) revealPanels(views.scalp);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.scalp.innerHTML = errorHTML(err.message);
    else console.warn('Silent scalp refresh failed:', err.message);
  }
}

async function loadRoth(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.roth && !force) { renderRoth(STATE.roth); revealPanels(views.roth); return; }
  if (!silent) views.roth.innerHTML = loadingHTML('ten years of history for the fund universe');
  try {
    // POST, not GET: a portfolio has no business in a URL, browser history or an
    // access log, and the holdings text is arbitrary length.
    const data = await postJSON('/api/retirement', STATE.rothInputs);
    STATE.roth = data;
    renderRoth(data);
    if (!silent) revealPanels(views.roth);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.roth.innerHTML = errorHTML(err.message);
    else console.warn('Silent Roth refresh failed:', err.message);
  }
}

async function loadTracker(force, opts = {}) {
  const silent = !!opts.silent;
  // Shared ledger, so nothing about the loaded ticker invalidates it.
  if (STATE.tracker && !force) { renderTracker(STATE.tracker); revealPanels(views.tracker); return; }
  if (!silent) views.tracker.innerHTML = loadingHTML("Optic's own position ledger");
  try {
    const data = await getJSON(`/api/tracker${STATE.trackerMonth ? `?month=${encodeURIComponent(STATE.trackerMonth)}` : ''}`);
    STATE.tracker = data;
    renderTracker(data);
    if (!silent) revealPanels(views.tracker);
    // A scheduled scan may already be running; show its progress live.
    if ((data.progress || {}).running) startTrackerPoll();
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.tracker.innerHTML = errorHTML(err.message);
    else console.warn('Silent tracker refresh failed:', err.message);
  }
}

/** Poll the ledger while a scan is in flight.
 *
 * A NASDAQ-wide scan runs for minutes on the server, so the scan request returns
 * straight away and the state is fetched on a timer instead. This also picks up a
 * *scheduled* scan nobody in this browser started, which is why the poll keys off
 * the server's own progress flag rather than a local one. */
let trackerPoll = null;

function stopTrackerPoll() {
  if (trackerPoll) { clearInterval(trackerPoll); trackerPoll = null; }
}

function startTrackerPoll() {
  if (trackerPoll) return;
  trackerPoll = setInterval(async () => {
    // Nothing to poll for if the user has navigated away from the tab.
    if (STATE.view !== 'tracker') { stopTrackerPoll(); return; }
    try {
      const data = await getJSON(`/api/tracker${STATE.trackerMonth ? `?month=${encodeURIComponent(STATE.trackerMonth)}` : ''}`);
      const wasRunning = !!((STATE.tracker || {}).progress || {}).running;
      STATE.tracker = data;
      renderTracker(data);
      if (!(data.progress || {}).running) {
        stopTrackerPoll();
        STATE.trackerScanning = false;
        // Only animate on the transition, not on every quiet poll.
        if (wasRunning) revealPanels(views.tracker);
      }
    } catch (err) {
      console.warn('Tracker poll failed:', err.message);
    }
  }, 4000);
}

/** Start a scan, or refresh marks. The scan returns immediately and the polling
 *  loop takes over from there; marking is quick enough to just await. */
async function runTrackerAction(kind) {
  if (STATE.trackerScanning) return;
  STATE.trackerScanning = true;
  if (STATE.tracker) renderTracker(STATE.tracker);
  try {
    if (kind === 'scan') {
      await postJSON('/api/tracker/scan', {});
      startTrackerPoll();
      return;                       // the poll owns the UI from here
    }
    await postJSON('/api/tracker/mark', {});
    STATE.trackerScanning = false;
    await loadTracker(true);
  } catch (err) {
    STATE.trackerScanning = false;
    if (STATE.tracker) renderTracker(STATE.tracker);
    const bar = document.querySelector('.tracker-bar');
    if (bar) bar.insertAdjacentHTML('afterend', errorHTML(err.message));
  }
}

async function loadIndices(force, opts = {}) {
  const silent = !!opts.silent;
  // Market-wide, so unlike the ticker panels there's nothing to invalidate when
  // the symbol changes — only an explicit refresh refetches.
  if (STATE.indices && !force) { renderIndices(STATE.indices); revealPanels(views.indices); return; }
  if (!silent) views.indices.innerHTML = loadingHTML('index history (this pulls 10 years per index)');
  try {
    const data = await getJSON('/api/indices');
    STATE.indices = data;
    renderIndices(data);
    if (!silent) revealPanels(views.indices);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.indices.innerHTML = errorHTML(err.message);
    else console.warn('Silent indices refresh failed:', err.message);
  }
}

async function loadEarnings(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.earnings && STATE.earnings.ticker === STATE.ticker && !force) {
    renderEarnings(STATE.earnings); revealPanels(views.earnings); return;
  }
  if (!silent) views.earnings.innerHTML = loadingHTML(`earnings data for ${STATE.ticker}`);
  try {
    const data = await getJSON(`/api/earnings/${encodeURIComponent(STATE.ticker)}`);
    data.ticker = STATE.ticker;
    STATE.earnings = data;
    renderEarnings(data);
    if (!silent) revealPanels(views.earnings);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) views.earnings.innerHTML = errorHTML(err.message);
    else console.warn('Silent earnings refresh failed:', err.message);
  }
}

function loadView(view, force) {
  if (view === 'home') return renderHome();
  // Macro & Sectors is market-wide, so it works with no ticker loaded. The other
  // three are ticker-specific: send the user back to pick one rather than firing
  // a request at /api/ticker/null.
  if (!['market', 'indices', 'roth', 'tracker', 'settings'].includes(view) && !STATE.ticker) {
    views[view].innerHTML = `<div class="panel"><h2>No ticker loaded</h2>
      <p class="sub">Enter a symbol in the top bar, or pick one on the
      <button class="btn" type="button" data-goto-home style="padding:2px 9px;font-size:12px">Home</button> page.</p></div>`;
    return;
  }
  if (view === 'swing') return loadSwing(force);
  if (view === 'scalp') return loadScalp(force);
  if (view === 'earnings') return loadEarnings(force);
  if (view === 'market') return loadMarket(force);
  if (view === 'indices') return loadIndices(force);
  if (view === 'roth') return loadRoth(force);
  if (view === 'tracker') return loadTracker(force);
  if (view === 'settings') return renderSettings();
  if (view === 'long') return loadLong(force);
}

const MARKET_STATE_LABELS = {
  PRE: 'Pre-market',
  PREPRE: 'Pre-market',
  REGULAR: 'Open',
  POST: 'After-hours',
  POSTPOST: 'Closed',
  CLOSED: 'Closed',
};

function friendlyMarketState(raw) {
  if (!raw) return 'unknown';
  return MARKET_STATE_LABELS[raw] || raw;
}

/* The status line reports the *active* view, not the Swing tab.
 *
 * It used to read only STATE.swing, so opening a ticker straight onto Earnings or
 * Long-Term left it stuck on "AAPL — loading…" forever: nothing was loading, the
 * panel below was fully rendered, and the line was describing a fetch that had
 * never been started. It also showed swing-only fields — expiries, the swing
 * verdict — on tabs where they mean nothing. */
/* ------------------------------------------------------- session strip
 *
 * A price outside regular hours needs two numbers, not one: the settled close
 * everyone quotes, and where the stock is actually trading. Showing only the
 * close is how a 6% after-hours gap goes unnoticed; showing only the extended
 * print loses the reference it should be measured against.
 *
 * The phase comes from the server, which knows New York time regardless of the
 * visitor's clock or timezone. The countdown ticks locally so it stays smooth
 * without polling every second. */

// One hue per session, following the arc of the day: violet through the small
// hours, amber at dawn, blue for the main session, orange at dusk. Distinct
// enough to tell apart at 6px tall, and the same colours drive the dot, the
// segment and the legend so there's nothing to cross-reference.
// Views where the loaded symbol is the subject. Everywhere else — Indices,
// Macro, Roth, Optic's Positions, Settings, Home — the tab is about the market or
// the app, so a company profile and one stock's closing price are just noise
// carried over from whatever was loaded last.
const TICKER_VIEWS = ['swing', 'scalp', 'earnings', 'long'];

const SESSION_PHASES = [
  { phase: 'overnight', label: 'Overnight', hours: '8pm – 4am' },
  { phase: 'pre', label: 'Pre-market', hours: '4am – 9:30am' },
  { phase: 'regular', label: 'Regular', hours: '9:30am – 4pm' },
  { phase: 'after', label: 'After hours', hours: '4pm – 8pm' },
];

function humanCountdown(minutes) {
  if (minutes === null || minutes === undefined) return '';
  if (minutes < 1) return 'any moment';
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h === 0) return `${m} minute${m === 1 ? '' : 's'}`;
  if (m === 0) return `${h} hour${h === 1 ? '' : 's'}`;
  return `${h} hour${h === 1 ? '' : 's'} and ${m} minute${m === 1 ? '' : 's'}`;
}

function renderSessionBar() {
  const host = $('#sessionbar');
  if (!host) return;
  const data = STATE.session;
  // The strip needs session data, which only arrives with a ticker fetch. Once
  // it's there it stays useful on every tab, because market hours aren't
  // per-symbol — only the company and price rows below are.
  if (!data) { host.hidden = true; return; }

  const sess = data.session || {};
  const p = data.prices || {};
  const phase = sess.phase || 'closed';

  const segments = (sess.segments || []).map((seg) => `<span class="ses-seg p-${
    esc(seg.phase)}${seg.active ? ' active' : ''}" style="left:${seg.start_pct}%;width:${
    seg.width_pct}%" title="${esc(seg.label)}"></span>`).join('');

  // Legend, so the colours are decodable without hovering. The live one is
  // called out rather than left for the reader to match against the bar.
  // Hours converted to the viewer's zone, from the timestamps the server sends
  // with each segment — so a reader in London sees when the US open lands for
  // them instead of a bare "9:30am" that means nothing where they are.
  const zone = activeZone();
  const zoneTag = zoneAbbrev(zone);
  const onMarketTime = viewerOnMarketTime();
  const segByPhase = {};
  (sess.segments || []).forEach((seg) => {
    if (!segByPhase[seg.phase]) segByPhase[seg.phase] = seg;
  });
  const legend = SESSION_PHASES.map((ph) => {
    const seg = segByPhase[ph.phase];
    const hours = seg
      ? `${timeIn(seg.start_at, zone)} – ${timeIn(seg.end_at, zone)}`
      : ph.hours;
    return `<span class="ses-key${ph.phase === phase ? ' live' : ''}">
      <i class="p-${ph.phase}"></i>${esc(ph.label)}
      <em>${esc(hours)}</em></span>`;
  }).join('');

  // Where "now" sits on the 24-hour strip — the same marker TradingView draws.
  const marker = `<span class="ses-now" style="left:${sess.day_pct}%"></span>`;

  const tickerRelevant = TICKER_VIEWS.includes(STATE.view);

  const closeBlock = !tickerRelevant ? '' : `<div class="ses-price">
    <span class="ses-plabel">${sess.is_regular ? 'Today' : 'At the close'}</span>
    <span class="ses-pval">${fmt(p.regular_close, 2)}</span>
    <span class="ses-pnote ${signClass(p.regular_change_pct)}">${
    fmtPct(p.regular_change_pct, 2)} on the day</span>
  </div>`;

  const showExtended = tickerRelevant && !sess.is_regular
    && p.change_from_close_pct !== null && p.change_from_close_pct !== undefined;

  const nowBlock = showExtended ? `<div class="ses-price">
    <span class="ses-plabel">${esc(cap(p.current_kind) || 'Now')}</span>
    <span class="ses-pval ${signClass(p.change_from_close_pct)}">${fmt(p.current, 2)}</span>
    <span class="ses-pnote ${signClass(p.change_from_close_pct)}">${
    fmtPct(p.change_from_close_pct, 2)} vs the close</span>
  </div>` : '';

  // What the company actually does. Clamped to two lines rather than truncated
  // in JS: splitting on sentence boundaries breaks on "Inc." and every other
  // abbreviation, and a half-sentence reads like a bug. CSS clamps at whatever
  // fits and the full text is one click away.
  const prof = data.profile || {};
  const meta = [
    prof.is_fund ? prof.category : prof.sector,
    prof.is_fund ? prof.fund_family : prof.industry,
    prof.employees ? `${fmtCompact(prof.employees, 0)} employees` : null,
    prof.city && prof.country ? `${prof.city}, ${prof.country}` : prof.country,
  ].filter(Boolean).map((x) => esc(x)).join(' · ');

  const companyBlock = (tickerRelevant && (prof.name || prof.summary)) ? `<div class="ses-company">
    <div class="ses-co-head">
      <span class="ses-co-name">${esc(prof.name || data.ticker || '')}</span>
      ${prof.kind_label ? `<span class="chip neutral" style="padding:0 6px;font-size:10px"><span class="dot"></span>${esc(prof.kind_label)}</span>` : ''}
      ${meta ? `<span class="ses-co-meta">${meta}</span>` : ''}
      ${prof.website ? `<a class="ses-co-link" href="${esc(prof.website)}" target="_blank"
        rel="noopener noreferrer">Site</a>` : ''}
    </div>
    ${prof.summary ? `<p class="ses-co-sum" id="ses-summary">${esc(prof.summary)}</p>
      <button type="button" class="ses-co-more" id="ses-more">More</button>` : `
      <p class="ses-co-sum expanded" style="color:var(--ink-muted)">No business description in the
      feed for this symbol.</p>`}
  </div>` : '';

  const nextText = (sess.next && sess.next.label)
    ? `${esc(sess.next.label)} in ${humanCountdown(sess.next.minutes_away)}`
    : '';

  host.hidden = false;
  host.innerHTML = `
    ${companyBlock}
    <div class="ses-main">
      <span class="ses-dot p-${esc(phase)}"></span>
      <div class="ses-head">
        <span class="ses-phase">${esc(sess.label || '')}</span>
        <span class="ses-sub">${esc(dayIn(sess.now_et, zone))} ${
    esc(timeIn(sess.now_et, zone))} ${esc(zoneTag)}${
    onMarketTime ? '' : ` · ${esc(sess.weekday || '')} ${esc(sess.now_et_label || '')} ET`}${
    nextText ? ` · ${nextText}` : ''}</span>
      </div>
      ${closeBlock}
      ${nowBlock}
      <div class="ses-strip">${segments}${marker}</div>
    </div>
    <div class="ses-legend">${legend}
      <span class="ses-key ses-zone">${onMarketTime
    ? `Times in ${esc(zoneTag)} — market time`
    : `Times in ${esc(zoneTag)}; market runs on ET`}<button type="button"
        data-goto-settings>change</button></span>
    </div>
    ${tickerRelevant && p.stale_note ? `<div class="ses-warn">${gloss(p.stale_note)}</div>` : ''}
    <div class="ses-desc">${gloss(sess.description || '')}</div>`;

  dedupeGlossTerms(host);

  // Hide the toggle when the summary already fits — a "more" button that expands
  // nothing is worse than no button.
  const sum = $('#ses-summary');
  const more = $('#ses-more');
  if (sum && more) {
    if (sum.scrollHeight <= sum.clientHeight + 1) more.hidden = true;
    more.addEventListener('click', () => {
      const open = sum.classList.toggle('expanded');
      more.textContent = open ? 'Less' : 'More';
    });
  }
}

async function loadSession(force) {
  if (!STATE.ticker) { STATE.session = null; renderSessionBar(); return; }
  if (STATE.session && STATE.session.ticker === STATE.ticker && !force) {
    renderSessionBar();
    return;
  }
  try {
    const data = await getJSON(`/api/session/${encodeURIComponent(STATE.ticker)}`);
    const firstLoad = !STATE.session;
    STATE.session = data;
    renderSessionBar();
    // The Quote panel keys its extended-hours block off the session phase, and
    // the swing view usually paints before this request lands.
    if (firstLoad && STATE.view === 'swing' && STATE.swing) renderSwing(STATE.swing);
  } catch (err) {
    console.warn('Session strip unavailable:', err.message);
  }
}

// Re-fetch on the minute so the phase and countdown stay honest across a session
// boundary — the difference between "after hours" and "overnight" is a real one.
setInterval(() => { if (STATE.ticker) loadSession(true); }, 60000);

function updateStatus() {
  // Home is the landing page. Whatever symbol is still in memory isn't what this
  // page is about, and printing it next to an empty search box reads as a bug —
  // which is exactly how it was reported.
  if (STATE.view === 'home') {
    setStatus([
      STATE.ticker
        ? `${esc(STATE.ticker)} is loaded — pick a tab above, or search another symbol.`
        : 'Search a ticker or company name to begin.',
      liveIndicatorHTML(),
    ]);
    return;
  }
  // 'settings' belongs here too: it has no symbol of its own, so it shouldn't be
  // nagging for one.
  if (!STATE.ticker
      && !['market', 'indices', 'roth', 'tracker', 'settings'].includes(STATE.view)) {
    setStatus(['No ticker loaded — enter a symbol to begin.']);
    return;
  }

  const d = STATE[STATE.view];
  if (!d) {
    // Only claim to be loading if a fetch really is in flight. The loaders put a
    // spinner in the container when they start and replace it when they finish,
    // so its presence *is* the pending state — no separate flag to fall out of
    // sync with reality.
    const host = views[STATE.view];
    const busy = !!(host && host.querySelector('.loading'));
    setStatus([
      STATE.ticker
        ? `${esc(STATE.ticker)}${busy ? ' — loading…' : ''}`
        : (busy ? 'Loading…' : 'Ready.'),
      liveIndicatorHTML(),
    ]);
    return;
  }

  const parts = [];
  const quote = d.quote || {};
  // Long-Term nests everything under `holding` and carries a bare `price`.
  const holding = d.holding || {};
  // Market-wide views aren't about the loaded symbol — Optic's Positions is one
  // shared ledger, so prefixing it with whatever ticker happens to be loaded
  // would imply the two are related.
  const tickerViews = ['swing', 'earnings', 'long', 'scalp'];
  const label = d.ticker || holding.ticker
    || (tickerViews.includes(STATE.view) ? STATE.ticker : null);
  const price = quote.price !== undefined && quote.price !== null
    ? quote.price : (holding.price !== undefined ? holding.price : d.spot);
  if (label) {
    parts.push(`<strong style="color:var(--ink-2)">${esc(label)}</strong>${
      price ? ' ' + fmt(price, 2) : ''}`);
  }
  if (quote.change_pct !== undefined && quote.change_pct !== null) {
    parts.push(`<span class="${signClass(quote.change_pct)}">${fmtPct(quote.change_pct, 2)}</span>`);
  }
  // Outside the session the regular-hours change is yesterday's news; the
  // extended-hours print is where the price actually is.
  const extPct = quote.post_market_change_pct !== undefined && quote.post_market_change_pct !== null
    ? quote.post_market_change_pct : quote.pre_market_change_pct;
  const extPrice = quote.post_market_price || quote.pre_market_price;
  if (extPct !== undefined && extPct !== null) {
    const which = quote.post_market_change_pct !== undefined
      && quote.post_market_change_pct !== null ? 'after hrs' : 'pre-mkt';
    parts.push(`${which} ${extPrice ? fmt(extPrice, 2) + ' ' : ''}<span class="${
      signClass(extPct)}">${fmtPct(extPct, 2)}</span>`);
  }

  // One line per view, saying what that view actually knows.
  if (STATE.view === 'swing') {
    parts.push(`Verdict: ${esc(cap((d.verdict || {}).stance) || 'n/a')}`);
    parts.push(`Expiries: ${((d.expiries || {}).used || []).join(', ') || 'none'}`);
  } else if (STATE.view === 'earnings') {
    const lr = d.latest_result || {};
    const nr = d.next_report || {};
    const e = d.extended_hours || {};
    if (lr.just_reported) {
      parts.push(`Reported ${esc(lr.date || '')} · ${fmtPct(lr.surprise_pct, 1)} surprise`);
      if (e.available && e.move_pct !== null && e.move_pct !== undefined) {
        parts.push(`${esc(cap(e.kind))} <span class="${signClass(e.move_pct)}">${
          fmtPct(e.move_pct, 1)}</span>`);
      }
    }
    else if (nr.date) parts.push(`Next report: ${esc(nr.date)}${
      nr.days_away === null || nr.days_away === undefined ? '' : ` (${nr.days_away}d)`}`);
    else parts.push('No scheduled report');
  } else if (STATE.view === 'long') {
    if (holding.conviction) {
      parts.push(`Conviction: ${esc(cap(holding.conviction))}${
        holding.conviction_score !== undefined && holding.conviction_score !== null
          ? ` (${fmt(holding.conviction_score, 0)})` : ''}`);
    }
  } else if (STATE.view === 'scalp') {
    if (d.price_vs_vwap_pct !== undefined && d.price_vs_vwap_pct !== null) {
      parts.push(`Vs VWAP: ${fmtPct(d.price_vs_vwap_pct, 2)}`);
    }
  } else if (STATE.view === 'market') {
    // macro.regime is a string, not an object.
    parts.push(`Regime: ${esc(cap((d.macro || {}).regime) || 'n/a')}`);
  } else if (STATE.view === 'tracker') {
    const s = d.summary || {};
    parts.push(`Optic's Positions: ${s.open_count || 0} open · ${s.closed_count || 0} closed`);
    parts.push(`<span class="${signClass(s.total_pnl)}">${fmtPct(s.return_pct, 2)}</span>`);
  }

  if (d.generated_at) {
    parts.push(`Source: ${esc(d.data_source || 'yfinance')} · ${
      new Date(d.generated_at).toLocaleTimeString()}`);
  }
  if (quote.market_state) parts.push(`Market: ${esc(friendlyMarketState(quote.market_state))}`);
  parts.push(liveIndicatorHTML());
  setStatus(parts);
}

/* ------------------------------------------------------- live auto-refresh
   Re-pulls whatever view is on screen every 20s while the US market is open
   (9:30am-4:00pm ET, Monday-Friday) and the tab is actually visible. Off
   hours it goes quiet on its own — there's nothing new to refresh toward. */

const REFRESH_INTERVAL_MS = 20000;
let refreshTimer = null;

function isMarketOpenET() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', hour12: false,
    weekday: 'short', hour: '2-digit', minute: '2-digit',
  }).formatToParts(new Date());
  const map = {};
  parts.forEach((p) => { map[p.type] = p.value; });
  if (map.weekday === 'Sat' || map.weekday === 'Sun') return false;
  const minutesSinceMidnight = parseInt(map.hour, 10) * 60 + parseInt(map.minute, 10);
  return minutesSinceMidnight >= 9 * 60 + 30 && minutesSinceMidnight < 16 * 60;
}

function liveIndicatorHTML() {
  return isMarketOpenET()
    ? '<span class="chip bull"><span class="dot" style="animation:pulse-beat 1.8s ease-in-out infinite"></span>Live · refreshing every 20s</span>'
    : '<span class="chip neutral"><span class="dot"></span>Market closed · auto-refresh paused</span>';
}

function tickAutoRefresh() {
  updateStatus(); // keep the live/closed chip accurate even off the swing tab
  if (document.hidden || !isMarketOpenET()) return;
  if (STATE.view === 'swing' && STATE.swing) loadSwing(true, { silent: true });
  else if (STATE.view === 'market' && STATE.market) loadMarket(true, { silent: true });
  // Long-term view is deliberately excluded — multi-year context doesn't
  // change intraday, so there's nothing there worth re-fetching every 20s.
  // Scalp has its own faster timer below — a squeeze setup can turn in seconds,
  // not the 20s that's fine for a swing thesis.
}

// The one tab where 20s is too slow to be worth calling "live" — minute bars
// and near-term gamma are the whole point, so this ticks separately and faster.
const SCALP_REFRESH_INTERVAL_MS = 8000;
let scalpRefreshTimer = null;

function tickScalpRefresh() {
  if (document.hidden || !isMarketOpenET()) return;
  if (STATE.view === 'scalp' && STATE.scalp) loadScalp(true, { silent: true });
}

function startAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  if (scalpRefreshTimer) clearInterval(scalpRefreshTimer);
  refreshTimer = setInterval(tickAutoRefresh, REFRESH_INTERVAL_MS);
  // No point running the fast scalp timer while that view is hidden.
  if (!HIDDEN_VIEWS.has('scalp')) {
    scalpRefreshTimer = setInterval(tickScalpRefresh, SCALP_REFRESH_INTERVAL_MS);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    tickAutoRefresh(); // catch up immediately on return
    if (!HIDDEN_VIEWS.has('scalp')) tickScalpRefresh();
  });
}

/* ===================================================================== CHAT */

const chatState = { messages: [], busy: false };

function chatContextPayload() {
  const ctx = {};
  if (STATE.view === 'swing' || STATE.swing) {
    const s = STATE.swing;
    if (s) {
      ctx.ticker = s.ticker;
      ctx.quote = s.quote;
      ctx.verdict = s.verdict;
      ctx.technicals = s.technicals;
      ctx.gex = s.gex;
      ctx.greeks = s.greeks;
      ctx.flow = s.flow;
      ctx.news = s.news;
      ctx.entry_plan = s.entry_plan;
      ctx.company = s.company;
      ctx.naked_ideas = s.naked_ideas;
      ctx.strategy_ideas = s.strategy_ideas;
    }
  }
  if (STATE.scalp) ctx.scalp = STATE.scalp;
  if (STATE.market) {
    ctx.macro = STATE.market.macro;
    ctx.sectors = STATE.market.sectors;
  }
  if (STATE.long) ctx.long_term = STATE.long;
  // Summary and open positions only. The full closed-trade list can run to
  // dozens of rows and would crowd out the analysis the question is about.
  if (STATE.tracker) {
    ctx.tracker = {
      summary: STATE.tracker.summary,
      open: STATE.tracker.open,
      config: STATE.tracker.config,
      caveats: STATE.tracker.caveats,
    };
  }
  ctx.active_view = STATE.view;
  return ctx;
}

function updateChatContext() {
  const bits = [];
  if (STATE.swing) bits.push(STATE.swing.ticker + ' options');
  if (STATE.scalp) bits.push('scalp/intraday');
  if (STATE.earnings) bits.push('earnings');
  if (STATE.market && STATE.market.sectors) bits.push('macro+sectors');
  if (STATE.indices) bits.push('indices');
  if (STATE.roth) bits.push('roth model');
  if (STATE.long) bits.push('long-term');
  if (STATE.tracker) bits.push('tracker');
  const chip = $('#chat-ctx');
  chip.className = 'chip ' + (bits.length ? 'bull' : 'neutral');
  chip.innerHTML = `<span class="dot"></span><span>${bits.length ? esc(cap(bits.join(' · '))) : 'No context'}</span>`;

  const suggestions = STATE.swing ? [
    'Why did the ranker pick that strike over a cheaper OTM one?',
    'What does the gamma profile imply for a swing long here?',
    'Is the flow confirming or fighting the chart?',
    'Walk me through the entry zone and what invalidates it.',
    'Does the short interest or insider activity change the read?',
    'How does the earnings record affect holding through the print?',
  ] : ['Load a ticker first, then ask about its analysis.'];
  $('#chat-suggest').innerHTML = suggestions
    .map((q) => `<button type="button" data-q="${esc(q)}">${esc(q.length > 46 ? q.slice(0, 44) + '…' : q)}</button>`)
    .join('');
}

function mdLite(text) {
  let out = esc(text);
  out = out.replace(/```([\s\S]*?)```/g, (m, code) => `<pre style="background:var(--surface-2);padding:8px;border-radius:6px;overflow-x:auto;font-size:11.5px">${code}</pre>`);
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/^### (.*)$/gm, '<strong>$1</strong>');
  out = out.replace(/^## (.*)$/gm, '<strong>$1</strong>');
  out = out.replace(/^\s*[-*] (.*)$/gm, '• $1');
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--s1)">$1</a>');
  return out;
}

function addMsg(role, text) {
  const log = $('#chat-log');
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  wrap.innerHTML = `<div class="who">${role === 'user' ? 'You' : role === 'err' ? 'Error' : ASSISTANT_NAME}</div>
    <div class="bubble"></div><div class="status"></div><div class="sources"></div>`;
  wrap.querySelector('.bubble').innerHTML = role === 'user' ? esc(text) : mdLite(text || '');
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
  return wrap;
}

async function streamTo(url, body, node) {
  const bubble = node.querySelector('.bubble');
  const statusEl = node.querySelector('.status');
  const sourcesEl = node.querySelector('.sources');
  let acc = '';

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error('Request failed (' + res.status + ')');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop();
    for (const chunk of chunks) {
      let event = 'message';
      let data = '';
      chunk.split('\n').forEach((line) => {
        if (line.startsWith('event: ')) event = line.slice(7).trim();
        else if (line.startsWith('data: ')) data += line.slice(6);
      });
      if (!data) continue;
      let payload;
      try { payload = JSON.parse(data); } catch (e) { continue; }

      if (event === 'delta') {
        acc += payload.text || '';
        statusEl.textContent = '';
        bubble.innerHTML = mdLite(acc);
      } else if (event === 'status') {
        statusEl.innerHTML = `<span class="spinner"></span>${esc(payload.state || '')}…`;
      } else if (event === 'error') {
        node.classList.add('err');
        statusEl.textContent = '';
        bubble.innerHTML = mdLite(payload.message || 'Unknown error.');
      } else if (event === 'done') {
        statusEl.textContent = '';
        const list = payload.sources || payload.citations || [];
        if (list.length) {
          sourcesEl.innerHTML = '<div style="color:var(--ink-muted);margin-bottom:2px">Sources</div>'
            + list.map((sc) => `<a href="${esc(sc.url)}" target="_blank" rel="noopener">${esc(sc.title || sc.url)}</a>`).join('');
        }
      }
      $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
    }
  }
  return acc;
}

async function sendChat(text) {
  if (chatState.busy || !text.trim()) return;
  chatState.busy = true;
  $('#chat-send').disabled = true;
  $('#chat-research').disabled = true;

  addMsg('user', text);
  chatState.messages.push({ role: 'user', content: text });
  const node = addMsg('assistant', '');
  node.querySelector('.status').innerHTML = '<span class="spinner"></span>thinking…';

  try {
    const reply = await streamTo('/api/chat', {
      messages: chatState.messages,
      context: chatContextPayload(),
      web: $('#chat-web').checked,
    }, node);
    if (reply) chatState.messages.push({ role: 'assistant', content: reply });
  } catch (err) {
    node.classList.add('err');
    node.querySelector('.status').textContent = '';
    node.querySelector('.bubble').textContent = err.message;
  } finally {
    chatState.busy = false;
    $('#chat-send').disabled = false;
    $('#chat-research').disabled = false;
  }
}

async function runResearch() {
  if (chatState.busy) return;
  chatState.busy = true;
  $('#chat-send').disabled = true;
  $('#chat-research').disabled = true;

  const custom = $('#chat-input').value.trim();
  addMsg('user', custom || `Deep research: ${STATE.ticker || 'the market'}`);
  $('#chat-input').value = '';
  const node = addMsg('assistant', '');
  node.querySelector('.status').innerHTML = '<span class="spinner"></span>searching…';

  try {
    await streamTo('/api/research', {
      ticker: STATE.ticker,
      question: custom || null,
      context: chatContextPayload(),
    }, node);
  } catch (err) {
    node.classList.add('err');
    node.querySelector('.bubble').textContent = err.message;
  } finally {
    chatState.busy = false;
    $('#chat-send').disabled = false;
    $('#chat-research').disabled = false;
  }
}

/* ===================================================================== INIT */

/* Where the gear returns you to.
 *
 * Recorded on every transition rather than only when the gear is used, so it also
 * works when Settings was reached from the session strip's "change" link — the
 * gear should always send you back to whatever you were actually reading. */
let viewBeforeSettings = 'home';

function switchView(view, force) {
  if (HIDDEN_VIEWS.has(view)) view = 'home';
  if (view !== 'tracker') stopTrackerPoll();
  // Captured before STATE.view is overwritten.
  if (view === 'settings' && STATE.view !== 'settings') viewBeforeSettings = STATE.view;
  STATE.view = view;
  Object.entries(views).forEach(([k, node]) => node.classList.toggle('active', k === view));
  document.querySelectorAll('nav.tabs button').forEach((b) => {
    b.setAttribute('aria-selected', String(b.dataset.view === view));
  });
  // The settings gear sits in the top bar, not the tab strip, so it isn't covered
  // by the loop above.
  const gear = $('#settings-btn');
  if (gear) {
    const open = view === 'settings';
    gear.setAttribute('aria-pressed', String(open));
    gear.setAttribute('aria-label', open ? 'Close settings' : 'Settings');
    gear.title = open
      ? `Close settings — back to ${VIEW_NAMES[viewBeforeSettings] || 'Home'}`
      : 'Settings — appearance and time zone';
  }
  // Reconcile the search box with what's actually loaded. The two had drifted —
  // the status line said MSFT while the box sat empty — and rather than hunt every
  // path that can clear one without the other, they're squared up on every tab
  // change. Either half being wrong is a lie about what you're looking at.
  const box = $('#ticker-input');
  if (box && STATE.ticker && box.value.trim().toUpperCase() !== STATE.ticker) {
    box.value = STATE.ticker;
  }

  loadView(view, !!force);
  // Both of these describe the active view, so they have to change with the tab
  // rather than wait for the next 20-second refresh tick.
  updateStatus();
  renderSessionBar();
}

document.querySelectorAll('nav.tabs button').forEach((btn) => {
  if (HIDDEN_VIEWS.has(btn.dataset.view)) { btn.hidden = true; return; }
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// Human names for the views, for the gear's tooltip.
const VIEW_NAMES = {
  home: 'Home', swing: 'Swing', scalp: 'Scalps', earnings: 'Earnings',
  market: 'Macro', indices: 'Indices', long: 'Long-Term', roth: 'Roth',
  tracker: "Optic's Positions", settings: 'Settings',
};

const settingsBtn = $('#settings-btn');
if (settingsBtn) {
  settingsBtn.addEventListener('click', () => {
    if (STATE.view !== 'settings') { switchView('settings'); return; }
    // Second press: back where you came from. Guard the ticker-only views — the
    // symbol could have been cleared while Settings was open, and returning to a
    // "No ticker loaded" panel is a worse answer than Home.
    let back = viewBeforeSettings;
    const needsTicker = !['home', 'market', 'indices', 'roth', 'tracker'].includes(back);
    if (back === 'settings' || (needsTicker && !STATE.ticker)) back = 'home';
    switchView(back);
  });
}

/* Charts bake the container's pixel width into their viewBox, so a width change
 * (window resize, or the chat panel taking 400px off the right) needs a re-render
 * to stay sharp. Re-render only — no reveal animation, since nothing new arrived.
 */
const rerenderActiveView = () => {
  if (STATE.view === 'home') return; // no charts to re-scale
  // Settings draws from SETTINGS, not from a fetched payload, so it has no
  // STATE entry to gate on.
  if (STATE.view === 'settings') { renderSettings(); return; }
  const d = STATE[STATE.view];
  if (!d) return;
  if (STATE.view === 'swing') renderSwing(d);
  else if (STATE.view === 'scalp') renderScalp(d);
  else if (STATE.view === 'earnings') renderEarnings(d);
  else if (STATE.view === 'market') renderMarket(d);
  else if (STATE.view === 'indices') renderIndices(d);
  else if (STATE.view === 'roth') renderRoth(d);
  else if (STATE.view === 'tracker') renderTracker(d);
  else if (STATE.view === 'settings') renderSettings();
  else if (STATE.view === 'long') renderLong(d);
};

let resizeTimer = null;
let lastMainWidth = 0;
const watchWidth = (el) => {
  if (!el || typeof ResizeObserver === 'undefined') return;
  // Seed the width first: ResizeObserver always fires once on observe(), and an
  // unseeded first callback would re-render the view right after the initial
  // load — wiping the reveal animation's classes mid-cascade.
  lastMainWidth = Math.round(el.getBoundingClientRect().width);
  // ResizeObserver rather than window.onresize: it also catches the chat panel
  // opening, sidebar layout shifts, and zoom — anything that changes the real
  // content width, not just the window's.
  new ResizeObserver((entries) => {
    const w = Math.round(entries[0].contentRect.width);
    // Ignore height-only changes and scrollbar-sized jitter. Swapping panels for
    // a loading spinner makes the page short enough to drop the scrollbar, which
    // widens <main> by ~15px — re-rendering on that would interrupt the reveal
    // cascade mid-flight, and a 15px difference isn't worth a redraw anyway.
    if (!w || Math.abs(w - lastMainWidth) < 24) return;
    lastMainWidth = w;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(rerenderActiveView, 150);
  }).observe(el);
};
watchWidth(document.querySelector('main'));

/* --------------------------------------------------------- symbol typeahead
 *
 * One implementation driving both boxes (top bar and home), because two copies of
 * keyboard handling is two places for the arrow keys to behave differently.
 *
 * Deliberate choices:
 *  - Debounced, so typing "apple" is one request rather than five.
 *  - Results are only applied if the query still matches what's in the box, since
 *    responses can arrive out of order and a stale list is worse than none.
 *  - Enter with nothing highlighted submits whatever was typed, so someone who
 *    knows the symbol never has to touch the dropdown.
 */
const SEARCH_DEBOUNCE_MS = 160;

function attachTypeahead(inputId, listId) {
  const input = document.getElementById(inputId);
  const list = document.getElementById(listId);
  if (!input || !list) return;

  let items = [];
  let active = -1;
  let timer = null;
  let lastQuery = '';

  const close = () => {
    list.hidden = true;
    list.innerHTML = '';
    input.setAttribute('aria-expanded', 'false');
    items = [];
    active = -1;
  };

  const choose = (i) => {
    const pick = items[i];
    if (!pick) return;
    input.value = pick.symbol;
    close();
    loadTicker(pick.symbol);
  };

  const highlight = (text, query) => {
    // Mark the matched run, the way the reference does — it's what makes a long
    // list scannable. Escaped first, then the marker is inserted, so the match
    // can't smuggle in markup.
    const safe = esc(text);
    const q = esc(query);
    if (!q) return safe;
    const at = safe.toLowerCase().indexOf(q.toLowerCase());
    if (at < 0) return safe;
    return safe.slice(0, at) + '<b>' + safe.slice(at, at + q.length) + '</b>'
      + safe.slice(at + q.length);
  };

  const render = (query) => {
    if (!items.length) { close(); return; }
    list.innerHTML = items.map((r, i) => `<li role="option" id="${listId}-${i}"
      aria-selected="${i === active}" class="${i === active ? 'on' : ''}" data-index="${i}">
      <span class="combo-sym">${highlight(r.symbol, query)}</span>
      <span class="combo-name">${highlight(r.name, query)}</span>
      ${r.etf ? '<span class="combo-tag">ETF</span>' : ''}
    </li>`).join('');
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };

  const move = (delta) => {
    if (!items.length) return;
    active = (active + delta + items.length) % items.length;
    render(lastQuery);
    const el = list.querySelector('.on');
    if (el) el.scrollIntoView({ block: 'nearest' });
  };

  input.addEventListener('input', () => {
    const query = input.value.trim();
    lastQuery = query;
    clearTimeout(timer);
    if (query.length < 1) { close(); return; }
    timer = setTimeout(async () => {
      try {
        const data = await getJSON(`/api/search?q=${encodeURIComponent(query)}&limit=10`);
        // Out-of-order guard: only paint if this is still what's typed.
        if (input.value.trim() !== query) return;
        items = data.results || [];
        active = -1;
        render(query);
      } catch (err) {
        close();
      }
    }, SEARCH_DEBOUNCE_MS);
  });

  input.addEventListener('keydown', (evt) => {
    if (evt.key === 'ArrowDown') { evt.preventDefault(); move(1); }
    else if (evt.key === 'ArrowUp') { evt.preventDefault(); move(-1); }
    else if (evt.key === 'Escape') { close(); }
    else if (evt.key === 'Enter' && active >= 0) {
      // Only intercept when something is highlighted; otherwise the form submits
      // the typed symbol as it always did.
      evt.preventDefault();
      choose(active);
    }
  });

  list.addEventListener('mousedown', (evt) => {
    const li = evt.target.closest('[data-index]');
    if (!li) return;
    evt.preventDefault();               // keep focus off the list
    choose(Number(li.dataset.index));
  });

  // Closing on blur has to be deferred, or the click that selected an item is
  // cancelled before it lands.
  input.addEventListener('blur', () => setTimeout(close, 120));
}

/** Load a ticker from anywhere (top bar, home form, home quick-pick). */
function loadTicker(raw) {
  const next = (raw || '').trim().toUpperCase();
  if (!next) return;
  STATE.ticker = next;
  STATE.swing = null;
  STATE.scalp = null;
  STATE.earnings = null;
  STATE.long = null;
  $('#ticker-input').value = next;
  STATE.session = null;
  loadSession(true);
  // Coming from home there's nothing to show on home, so land on the analysis.
  switchView(STATE.view === 'home' ? 'swing' : STATE.view, true);
}

$('#ticker-form').addEventListener('submit', (evt) => {
  evt.preventDefault();
  loadTicker($('#ticker-input').value);
});

// Home form, quick-picks, and the "no ticker" panel's link back to home.
document.addEventListener('submit', (evt) => {
  if (evt.target.id !== 'home-form') return;
  evt.preventDefault();
  loadTicker($('#home-input').value);
});
document.addEventListener('change', (evt) => {
  if (evt.target.id === 'tracker-month') {
    STATE.trackerMonth = evt.target.value;
    loadTracker(true);
    return;
  }
  if (evt.target.id === 'tz-select') {
    SETTINGS.timezone = evt.target.value;
    saveTimezone();
    return;
  }
  if (evt.target.id === 'chart-range') {
    chartRange = evt.target.value;
    try { localStorage.setItem(CHART_RANGE_KEY, chartRange); } catch (e) { /* private mode */ }
  } else if (evt.target.id === 'chart-interval') {
    chartInterval = evt.target.value;
    try { localStorage.setItem(CHART_INTERVAL_KEY, chartInterval); } catch (e) { /* private mode */ }
  } else {
    return;
  }
  if (STATE.swing) renderSwing(STATE.swing);
});

document.addEventListener('click', (evt) => {
  const modeBtn = evt.target.closest('[data-chart-mode]');
  if (modeBtn) {
    chartMode = modeBtn.dataset.chartMode === 'candle' ? 'candle' : 'line';
    try { localStorage.setItem(CHART_MODE_KEY, chartMode); } catch (e) { /* private mode */ }
    if (STATE.swing) renderSwing(STATE.swing);
    return;
  }
  const levelBtn = evt.target.closest('[data-toggle-levels]');
  if (levelBtn) {
    const which = levelBtn.dataset.toggleLevels;
    if (which === 'fib') {
      showFib = !showFib;
      try { localStorage.setItem(SHOW_FIB_KEY, showFib ? 'on' : 'off'); } catch (e) { /* private */ }
    } else {
      showSR = !showSR;
      try { localStorage.setItem(SHOW_SR_KEY, showSR ? 'on' : 'off'); } catch (e) { /* private */ }
    }
    if (STATE.swing) renderSwing(STATE.swing);
    return;
  }
  const themeBtn = evt.target.closest('[data-set-theme]');
  if (themeBtn) {
    SETTINGS.theme = themeBtn.dataset.setTheme;
    applyTheme();
    return;
  }
  if (evt.target.closest('#tracker-scan')) { runTrackerAction('scan'); return; }
  if (evt.target.closest('#tracker-mark')) { runTrackerAction('mark'); return; }
  const pick = evt.target.closest('[data-pick]');
  if (pick) { loadTicker(pick.dataset.pick); return; }
  if (evt.target.closest('[data-goto-home]')) switchView('home');
  if (evt.target.closest('[data-goto-settings]')) switchView('settings');
});

// Roth controls: inputs live in STATE so the panel survives tab switches.
document.addEventListener('submit', (evt) => {
  if (evt.target.id !== 'roth-form') return;
  evt.preventDefault();
  const years = parseInt($('#roth-years').value, 10);
  const annual = parseFloat($('#roth-annual').value);
  STATE.rothInputs = {
    years: Number.isFinite(years) ? Math.min(Math.max(years, 1), 45) : 30,
    risk: $('#roth-risk').value || 'balanced',
    annual: Number.isFinite(annual) ? Math.min(Math.max(annual, 0), 100000) : 7000,
    holdings: $('#roth-holdings').value || '',
    stock_candidates: $('#roth-stocks').value || '',
  };
  saveRothInputs();
  loadRoth(true);
});

$('#chat-toggle').addEventListener('click', () => {
  document.body.classList.toggle('chat-open');
  if (document.body.classList.contains('chat-open')) $('#chat-input').focus();
  // Charts re-render themselves via the ResizeObserver on <main> — opening the
  // panel takes 400px off the content width.
});
$('#chat-close').addEventListener('click', () => document.body.classList.remove('chat-open'));
$('#chat-send').addEventListener('click', () => {
  const text = $('#chat-input').value;
  $('#chat-input').value = '';
  sendChat(text);
});
$('#chat-research').addEventListener('click', runResearch);
$('#chat-input').addEventListener('keydown', (evt) => {
  if (evt.key === 'Enter' && (evt.metaKey || evt.ctrlKey)) {
    evt.preventDefault();
    $('#chat-send').click();
  }
});
$('#chat-suggest').addEventListener('click', (evt) => {
  const btn = evt.target.closest('button[data-q]');
  if (btn) sendChat(btn.dataset.q);
});

document.addEventListener('keydown', (evt) => {
  if ((evt.metaKey || evt.ctrlKey) && evt.key === 'k') {
    evt.preventDefault();
    document.body.classList.add('chat-open');
    $('#chat-input').focus();
  }
});

/* Every renderer replaces its view's innerHTML wholesale, so the header pass has
 * to run after each one. Wrapping them here keeps it in a single place instead of
 * a trailing call appended to eight functions that would drift apart over time. */
[
  ['swing', () => renderSwing], ['scalp', () => renderScalp], ['earnings', () => renderEarnings],
  ['market', () => renderMarket], ['indices', () => renderIndices], ['roth', () => renderRoth],
  ['tracker', () => renderTracker], ['long', () => renderLong],
].forEach(([view, get]) => {
  const original = get();
  const wrapped = function (...args) {
    const result = original.apply(this, args);
    // Notice first, before the panels — and inserted here rather than in each
    // renderer so a view physically cannot be added without it.
    const banner = legalBanner(view);
    if (banner && views[view] && !views[view].querySelector('.legal-area')) {
      views[view].insertAdjacentHTML('afterbegin', banner);
    }
    glossHeaders(views[view]);
    dedupeGlossTerms(views[view]);
    return result;
  };
  // Reassign the binding the rest of the file calls through.
  switch (view) {
    case 'swing': renderSwing = wrapped; break;
    case 'scalp': renderScalp = wrapped; break;
    case 'earnings': renderEarnings = wrapped; break;
    case 'market': renderMarket = wrapped; break;
    case 'indices': renderIndices = wrapped; break;
    case 'roth': renderRoth = wrapped; break;
    case 'tracker': renderTracker = wrapped; break;
    case 'long': renderLong = wrapped; break;
    default: break;
  }
});

/* Follow the OS theme.
 *
 * CSS variables update on their own, but the charts are SVG built in JS from a
 * colour cache, so they have to be told and then redrawn — otherwise a flip
 * leaves every chart painted for the previous theme while the page around it
 * changes. */
function watchColorScheme() {
  if (!window.matchMedia) return;
  const query = window.matchMedia('(prefers-color-scheme: dark)');
  const onChange = () => {
    // An explicit choice outranks the OS; only 'system' should react to a flip.
    if (SETTINGS.theme !== 'system') return;
    applyTheme();
  };
  if (query.addEventListener) query.addEventListener('change', onChange);
  else if (query.addListener) query.addListener(onChange);   // older Safari
}

(async function boot() {
  attachTypeahead('ticker-input', 'ticker-results');
  loadSettings();              // before anything reads SETTINGS
  syncChartTheme();            // before the first chart is drawn
  watchColorScheme();
  initLegalFooter();
  initGlossaryTooltips();
  loadRothInputs();
  updateChatContext();
  renderHome();
  updateStatus();
  try {
    const health = await getJSON('/api/health');
    renderHomeStatus(health);
    if (!health.assistant.enabled) {
      addMsg('assistant', `Hi, I'm ${ASSISTANT_NAME}. I'm not configured yet — ` + health.assistant.hint
        + '\n\nEverything else in the terminal works without me.');
      $('#chat-send').disabled = true;
      $('#chat-research').disabled = true;
    } else {
      addMsg('assistant', `Hi, I'm **${ASSISTANT_NAME}**, running on **${health.assistant.model}**. I can see whatever the terminal has computed for the loaded ticker — ask me about the gamma regime, the flow proxy, the recommended strike, or hit **Deep research** for a live sourced brief.`);
    }
  } catch (e) { /* backend health is non-fatal for the UI */ }
  startAutoRefresh();
  // Deliberately no initial ticker fetch: the home page waits for the user to
  // choose one instead of assuming SPY.
})();
