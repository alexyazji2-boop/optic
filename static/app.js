/* Optic Terminal — view layer. */

const ASSISTANT_NAME = 'Pulse';

const STATE = {
  // No ticker until the user picks one — the terminal opens on the home page
  // rather than silently deciding SPY is what you wanted to look at.
  ticker: null,
  view: 'home',
  trackerScanning: false,
  trackerMonth: null,
  trackerBook: 'balanced',
  swing: null,
  earnings: null,
  market: null,
  scan: null,
  evaluation: null,
  compare: null,
  compareInputs: ['', ''],
  scanGroups: [],
  scanGroupNote: '',
  correlation: null,
  bookRisk: null,
  intraday: null,
  sectorBoard: null,
  indexBoard: null,
  seasonality: null,
  seasonalityFor: '',
  rotation: null,
  forex: null,
  forexQuery: '',
  stockMap: null,
  stockMapTemplate: 'sector-month',
  extras: null,
  extrasFor: '',
  alerts: null,
  econ: null,
  econCode: 'CPIAUCSL',
  econCatalogue: null,
  // The workspace's own symbol. Deliberately separate from the analysis symbol:
  // the chart tab is somewhere you go to look at a chart, and having it snap to
  // whatever the Swing tab last loaded would make it useless as a place to
  // compare something else.
  chartSymbol: '',
  chartData: null,
  trendlines: null,
  trendlinesFor: '',
  sectorRead: null,
  sectorReadCache: {},
  sentiment: null,
  weekly: null,
  catalysts: null,
  catalystScan: '',
  catalystMode: null,
  priority: null,
  scanId: 'momentum',
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
  swing: $('#view-swing'), earnings: $('#view-earnings'),
  market: $('#view-market'), indices: $('#view-indices'), long: $('#view-long'),
  tracker: $('#view-tracker'), brief: $('#view-brief'),
  compare: $('#view-compare'),
  instrument: $('#view-instrument'),
  chart: $('#view-chart'),
  scan: $('#view-scan'),
  settings: $('#view-settings'),
};

/* ------------------------------------------------------------- glossary
   Beginner-facing jargon gets a dotted underline; hovering (or tabbing to it
   with a keyboard) shows a plain-English definition using the same tooltip
   the charts use. Applied to narrative text (summaries, rationale, notes) —
   not to table headers or labels, where it would just add visual noise. */

const GLOSSARY = {
  'liquidity': "How easily something can be bought or sold without moving its price. A stock trading a few hundred thousand dollars a day is illiquid: your own order becomes the market, and the price you get is nothing like the price you saw.",
  'dollar volume': "Share price multiplied by shares traded. The actual money changing hands each day. A better liquidity measure than share count, since a million shares of a $2 stock is a far smaller market than a million shares of a $200 one.",
  'screen': "A first-pass filter over a large list of stocks, used to decide which few deserve real analysis. A screen ranks candidates; it does not decide whether a trade is good.",
  'universe': "The full set of stocks a strategy is allowed to consider before any filtering. A strategy that only ever looks at ten names has a ten-name universe, however sophisticated the rest of it is.",
  'paper trading': "Placing trades on record without real money, so the results can be measured later. The prices are real; the positions are not.",
  'expectancy': "The average profit or loss per trade across every completed trade. Positive means the approach made money on average; negative means it lost, no matter how good the win rate looks.",
  'profit factor': "Total money made by the winners divided by total money lost by the losers. Above 1.0 is profitable; below 1.0 is not.",
  'win rate': "The share of completed trades that made money. On its own it says very little. A 30% win rate is excellent if the winners are five times the size of the losers.",
  'stop loss': "A price set in advance where you exit if the trade goes against you. It defines the loss before entering, instead of deciding in the moment.",
  'time stop': "Closing a trade because it hasn't worked within a set number of days, rather than because it hit a price. Capital sitting in an idea that isn't moving has a cost.",
  'realised p&l': "Profit and loss from trades that have already closed. This is the number that is final.",
  'unrealised p&l': "Profit and loss on positions still open. It changes every time the price moves and only becomes real when the position closes.",
  'slippage': "The gap between the price you expected and the price you actually got. It always works against you, and it's why simulated results tend to beat live ones.",
  'mid price': "The midpoint between the best buy and sell price. Filling at the mid is optimistic. In practice you usually pay closer to the worse side, especially on options.",
  'risk-on': "Investors are feeling confident and buying riskier assets (stocks, crypto) instead of safe ones (bonds, cash).",
  'risk-off': "Investors are nervous and moving money into safe assets (bonds, cash, gold) instead of risky ones like stocks.",
  'gamma': "How fast an option's directional exposure (its delta) changes as the stock price moves. High gamma means the trade's behavior can flip quickly.",
  'dealer gamma': "A measure of how much stock market-maker dealers must buy or sell to stay hedged as the price moves. It hints at whether trading will feel calm or wild.",
  'gamma flip': "The price level where dealers switch from calming price swings down to amplifying them, or the reverse.",
  'flip point': "The price level where dealers switch from calming price swings down to amplifying them, or the reverse.",
  'gex': "Gamma Exposure. An estimate of dealer hedging pressure at each price level, used to guess whether a stock will feel calm (range-bound) or wild (trending).",
  'delta': "How much an option's price moves for every $1 move in the stock. A delta of 0.50 means the option gains about $0.50 when the stock gains $1.",
  'theta': "How much value an option loses every single day just from time passing, even if the stock doesn't move. Often called ‘time decay’.",
  'theta decay': "The steady loss of an option's value simply from time passing, even if the stock price doesn't move.",
  'vega': "How much an option's price changes when the market's expectation of future volatility (movement) changes.",
  'implied volatility': "The market's guess at how much a stock will move in the future, baked into the option's price. Higher implied volatility means more expensive options.",
  'iv rank': "Where today's implied volatility sits between its own highest and lowest point over roughly the past year, on a 0-100 scale. High IV rank means options are historically expensive right now; low means they're historically cheap.",
  'iv percentile': "The percentage of days over roughly the past year where implied volatility was lower than it is today. Similar to IV rank, but counts days instead of measuring the full high-low range.",
  'realized volatility': "How much a stock has actually moved, measured from its real price history, as opposed to implied volatility, which is a forward-looking guess baked into option prices.",
  'open interest': "The total number of option contracts at a given strike that are currently open, bought or sold but not yet closed or expired.",
  'breakeven': "The stock price an option needs to reach for you to not lose money on the trade, ignoring commissions.",
  'iron condor': "A strategy that profits if the stock stays inside a price range. You sell options on both sides of the range and buy further-out options to cap your risk.",
  'iron butterfly': "Like an iron condor, but the options you sell are both at today's price instead of spread apart. Collects more money upfront but needs the stock to stay very still.",
  'straddle': "Buying a call and a put at the same strike price. A bet that the stock will move a lot, in either direction.",
  'strangle': "Like a straddle, but the call and put are at different (further out) strike prices. Cheaper, but needs a bigger move to make money.",
  'put/call ratio': "How many put options (bets a stock will fall) are being traded compared to call options (bets it will rise). A high ratio can mean traders are nervous.",
  'relative strength': "How a stock or sector is performing compared to a benchmark like the S&amp;P 500. Not just whether it's up, but whether it's beating the market.",
  'z-score': "A way to measure how unusual a value is compared to its recent normal range. A z-score of +2 or higher (or -2 or lower) means it's unusually stretched.",
  'basis points': "A tiny unit for measuring rates. 100 basis points equals 1%.",
  'rsi': "Relative Strength Index. A 0-100 gauge of whether a stock has been bought or sold too aggressively recently. Above 70 often means overbought, below 30 often means oversold.",
  'macd': "A trend-following indicator that compares two moving averages to help spot when momentum is shifting up or down.",
  'atr': "Average True Range. A measure of how much a stock typically moves in a single day. A higher ATR means a more volatile stock.",
  'fibonacci retracement': "A charting tool that marks likely support and resistance price levels using a mathematical ratio, meant to guess where a pullback might stop.",
  'support': "A price level where a falling stock has tended to stop falling and bounce.",
  'resistance': "A price level where a rising stock has tended to stop rising and pull back.",
  'short interest': "The percentage of a stock's available shares that have been sold short (bet against) by traders expecting the price to fall.",
  'days to cover': "How many days it would take, at average trading volume, for all short sellers to buy back their shares. A proxy for how ‘trapped’ short sellers might be.",
  'pair trade': "Betting on one stock or asset relative to another. Going long the one you think will do better and short the one you think will do worse.",
  'moving average': "The average closing price over a set number of past days, used to smooth out day-to-day noise and show the underlying trend.",
  'overbought': "A stock has risen quickly enough that it may be due for a pause or pullback.",
  'oversold': "A stock has fallen quickly enough that it may be due for a bounce.",
  'liquidity': "How easily a stock or option can be bought or sold without moving its price much. Low liquidity means wide bid/ask spreads and harder fills.",
  'bid/ask spread': "The gap between the highest price a buyer will pay (bid) and the lowest price a seller will accept (ask). A wide spread makes a trade more expensive to enter and exit.",
  'vwap': "Volume-Weighted Average Price. The average price paid today, weighted by how much volume traded at each price. Above VWAP is generally considered strong for the day; below is weak.",
  'opening range': "The high and low price set in the first few minutes after the market opens. Breaking above or below it is a common early signal of the day's direction.",
  'relative volume': "How much a stock is trading today compared to how much it normally trades at this same point in the day. Well above 1x means unusually heavy activity.",
  'rvol': "Relative Volume. How much a stock is trading today compared to its normal volume at this same point in the day. Well above 1x means unusually heavy activity.",
  'pivot point': "A price level calculated from yesterday's high, low, and close, used intraday as a quick reference for where a stock might find support or resistance today.",
  '0dte': "Zero Days to Expiry. An option expiring the same day it's traded. Its price can swing very fast since there's no time left for the bet to play out.",
  'gamma squeeze': "A rapid, self-reinforcing price move that happens when dealers who sold options must keep buying (or selling) the stock to stay hedged as the price moves, which pushes the price further in the same direction.",
  'short squeeze': "A rapid price rise that forces traders who bet against a stock (short sellers) to buy it back to limit their losses, and that buying pushes the price up even more.",
  'call wall': "The strike with the largest call open interest / gamma exposure above the price. Dealers hedging those calls tend to sell as the stock rallies into it, so it often acts like a ceiling.",
  'put wall': "The strike with the largest put open interest / gamma exposure below the price. Dealers hedging those puts tend to buy as the stock falls into it, so it often acts like a floor.",
  'gamma pin': "The single strike with the largest gamma exposure in either direction. The level dealer hedging tends to pull price toward, especially as expiry gets close.",
  'r1': "First resistance. A level derived from yesterday's high/low/close where an intraday rally often stalls first, before testing R2.",
  'r2': "Second resistance. A level derived from yesterday's high/low/close, further above price than R1 and a tougher ceiling to break through.",
  's1': "First support. A level derived from yesterday's high/low/close where an intraday decline often stalls first, before testing S2.",
  's2': "Second support. A level derived from yesterday's high/low/close, further below price than S1 and a tougher floor to break through.",
  'eps': "Earnings Per Share. The company's profit divided by its share count. It's the single number analysts forecast and the market judges the report against.",
  'consensus': "The average of what analysts forecast. Beating it isn't automatically good news. What matters is whether the market had already priced in more.",
  'implied move': "How big a move the options market is pricing for a stock, read from the cost of buying a call and a put at the same strike. If it costs 6% of the share price, traders expect roughly a 6% move.",
  'straddle cost': "The combined price of a call and a put at the same strike. It's what you pay to bet on a big move in either direction, and doubles as the market's estimate of that move's size.",
  'beat rate': "How often a company has reported earnings above the analyst consensus. A high rate usually means management guides conservatively, so a beat is already expected.",
  'surprise': "The gap between reported earnings and what analysts expected, in percent. Positive is a beat, negative is a miss.",
  'event premium': "The extra cost baked into option prices ahead of a known event like earnings. It evaporates the moment the event passes, which is why long options can lose money even when the stock moves your way.",
  'price target': "Where an analyst thinks the stock will trade, usually 12 months out. Useful as a sentiment gauge, unreliable as a forecast. Targets sit above the current price in almost every market.",
  'gross margin': "What proportion of revenue is left after the direct cost of making the product. Rising gross margin means pricing power or cheaper inputs.",
  'operating margin': "What proportion of revenue is left after all the running costs of the business. It's the cleanest read on whether growth is actually becoming more profitable.",
  'year over year': "Comparing a quarter with the same quarter twelve months earlier, rather than the one just before it. This strips out seasonality. Most businesses aren't supposed to have equal quarters.",
  'glidepath': "The practice of shifting from stocks toward bonds as your horizon shortens, so a crash close to when you need the money can't undo decades of growth.",
  'expense ratio': "The annual percentage a fund charges to run it, taken automatically from your returns. 0.03% is $3 a year per $10,000; 1% is $100. Over decades the difference compounds into real money.",
  'cagr': "Compound Annual Growth Rate. The steady yearly rate that would produce the same end result as the actual bumpy path. It smooths over crashes rather than hiding them, so read it alongside the worst drawdown.",
  'rebalance': "Selling some of what has grown and buying what has lagged, to return to your target weights. Inside a Roth this triggers no tax, which makes it far easier than in a taxable account.",
  'correlation': "How closely two investments move together, from -1 (opposite) to +1 (identical). Two funds with correlation near 1 are effectively the same bet.",
  'dte': "Days to expiry. How many calendar days until the option stops trading and either pays out or expires worthless.",
  'oi': "Open interest. The number of contracts at that strike currently held open by someone. High open interest means a lot of money is already positioned there.",
  'itm': "In the money. The option already has real value if exercised today: a call below the stock price, or a put above it.",
  'otm': "Out of the money. The option has no value if exercised today, and needs the stock to move before it does.",
  'atm': "At the money. The strike sits closest to where the stock is trading right now.",
  'sma': "Simple moving average. The plain average closing price over a number of days, used to define the trend.",
  'ema': "Exponential moving average. Like a moving average but weighted toward recent days, so it turns faster than the simple version.",
  'yoy': "Year over year. Comparing a period with the same period a year earlier, which removes seasonal distortion from the comparison.",
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
  'quote': "The current price and where it sits inside today's range and the past year's range. The baseline every other panel is measured against.",
  'options analytics': 'The options-market side of the analysis: greeks, dealer gamma exposure and call-versus-put flow.',
  'strike & entry recommendation': "Which option contract the terminal would pick given the current read, and the price level where entering makes sense instead of chasing.",
  'price, moving averages & fibonacci': "The price history with trend lines and common pullback levels drawn on. Used to judge whether the trend is intact and where a move is likely to pause.",
  'rsi (14)': 'A momentum gauge from 0-100 showing whether the stock has been bought or sold too hard recently. Above 70 is stretched, below 30 is washed out.',
  'macd (12, 26, 9)': 'A trend gauge comparing two moving averages, used to spot momentum turning up or down before the price move is obvious.',
  'delta analysis': "How much directional exposure sits in this stock's options. A read on whether the options market is positioned long or short.",
  'gamma analysis': 'Where option positions are most sensitive to price moves, which tells you which price levels are likely to attract or repel the stock.',
  'fear & greed': "A reading of how much risk appetite is in the market right now, from 0 (extreme fear) to 100 (extreme greed). It describes positioning, not value. It says where the crowd is, never what happens next.",
  'does the score work?': "A test of whether the screen's score actually predicts anything, measured against two controls: a random score, and the stock's own three-month return with no weighting at all.",
  'sector confirmation': "Whether the sector around a stock agrees with it. A supportive group is a tailwind for a setup, never a reason on its own. Every name still needs its own momentum and risk structure.",
  'sector board': "Each SPDR sector against the prior session's high and low, with a read on whether money is moving into it or out of it relative to the index.",
  '\u0394 to break': 'How far price is from the level it would have to clear for the short-term trend to turn up. Negative means it is still underneath.',
  '\u0394 to breakdown': 'How far price is above the level that would turn the short-term trend down. Negative means it has already broken.',
  'market regime score': 'One number for what kind of market this is right now. Is the tape helping a position or working against it. Built from index trend, sector breadth, the VIX, whether small caps are confirming, and how many sectors are participating.',
  'vex. Dealer vanna exposure': 'How much dealer hedging demand changes when implied volatility moves, rather than when price moves. Gamma answers "what if the stock moves"; vanna answers "what if the market re-prices risk".',
  'cex. Dealer charm exposure': 'How much dealer hedging demand changes from time passing alone, with neither price nor volatility moving. It builds into expiry, which is why the last days of an options cycle have a drift of their own.',
  'gex. Dealer gamma exposure': 'An estimate of how much stock market-makers must buy or sell to stay hedged as price moves. It hints at whether the tape will feel calm and range-bound or fast and trending.',
  'call vs put flow': "Whether today's options activity leans toward bullish bets (calls) or bearish bets (puts). A read on positioning, not a promise of direction.",
  'net premium by strike': 'How much money is actually being spent at each strike price, showing where traders are placing real bets rather than just quoting.',
  'buy calls / puts': 'Straightforward directional trades. Buying a call to bet the stock rises, or a put to bet it falls. Simple, but all the premium is at risk.',
  'options strategies': 'Multi-leg trades that profit from a price range, a change in volatility, or one asset moving relative to another, rather than pure direction.',
  'news & catalysts': 'Recent headlines scored for tone, plus scheduled events like earnings that tend to move the stock and keep options expensive.',

  // ---- company data
  'company data': 'The business behind the ticker. Revenue, profit, how heavily it is bet against, and who owns the shares.',
  'short interest': 'How much of the stock has been sold short (bet against) and how long those bets would take to unwind. Heavy short interest is fuel for a squeeze.',
  'financials': 'Revenue, profit and cash flow across recent years. Whether the underlying business is growing or shrinking.',
  'earnings track record': 'How the company has done versus expectations in past quarters, which sets how much the market trusts its guidance.',
  'insider & institutional activity': 'Whether company executives and large funds have been buying or selling. Occasionally an early signal of confidence or concern.',

  'squeeze read': 'How likely a sharp self-reinforcing move is right now. Either from dealers hedging options (gamma squeeze) or short sellers being forced to buy back (short squeeze).',
  'session snapshot': "Where the stock sits today against the levels intraday traders actually watch: the average price paid, the opening range, and yesterday's pivots.",
  'near-term gamma': 'Dealer hedging pressure at the nearest option expiry, which shapes how the price behaves for the rest of today.',
  'liquidity & short interest': 'Whether you can get in and out of these options cheaply, and how heavily the stock is bet against.',

  // ---- earnings
  'latest result': "The quarter the company just reported: what it delivered against what analysts expected. A beat is only half the story. The session after the print is what says whether the market cared, and a company can beat and still sell off.",
  'reported eps': "Earnings per share the company actually delivered for the quarter, next to the figure analysts had modelled. The gap between them is the surprise.",
  'next report': "When the company next reports results, what analysts expect, and how much movement the options market is charging for the event.",
  'event pricing': "Whether the options are expensive or cheap for the period they cover, measured against how far this stock has actually moved over the same span. Expensive favors selling premium; cheap favors buying it.",
  'estimate revisions': "Whether analysts have been raising or cutting their forecasts recently. Estimates move in response to company guidance, so the direction of travel is the closest public read on guidance you can get from free data.",
  'surprise history': "How reported earnings compared with consensus in past quarters, and (more usefully) what the stock actually did the session afterwards. A company can beat every quarter and still sell off.",
  'financial growth': "Revenue, profit and margin trends versus the same quarter a year earlier, so seasonality doesn't distort the comparison. Expanding margins mean growth is getting more profitable, not just bigger.",
  'forward estimates': "What analysts model for coming quarters and fiscal years, and how many of them are covering the name. Fewer analysts means a less reliable consensus.",
  'annual growth': "Full-year revenue, profit and margins, which show the multi-year trajectory a single quarter can easily disguise.",
  'analyst view': "Where the sell side thinks the stock is going and how the ratings are split. Best treated as a sentiment and positioning gauge. Targets sit above spot in almost every market.",

  // ---- macro & sectors
  'macro regime': 'Whether the overall market is currently rewarding risk-taking or punishing it, scored from cross-asset signals like the VIX, credit, the dollar and oil. It sets how aggressive to be, not what to buy.',
  'market breadth': 'How many parts of the market are joining a move. A rally with broad participation tends to keep going; one carried by a handful of names is fragile.',
  'cross-asset dashboard': 'Key markets outside stocks. Volatility, the dollar, bonds, commodities, credit and crypto. Because these usually move before equities do.',
  'cross-asset ratios': 'One market divided by another, which exposes relative shifts (like small caps versus large caps) that a single price chart hides.',
  'sector relative strength': "Which sectors are beating or lagging the S&P 500. Showing where money is actually flowing, not just what's green today.",
  'themes & sub-industries': 'Narrower baskets than sectors, like clean energy or cybersecurity, ranked against the broad market.',
  'niche industries': 'Very specific industry baskets, like semiconductors or memory chips, where strength often shows up before a broad sector average reflects it.',
  'breakout candidates': 'Groups coiled near the top of their range with improving relative strength. Statistically the most likely to break out next.',
  'ratio pair trades': "Going long one thing and short another, so the profit comes from the gap between them and you're far less exposed to the market's overall direction.",

  // ---- long-term & indices
  // ---- roth
  'roth ira model allocation': "A rules-based target mix built from your horizon and risk tolerance, measured against ten years of fund data. A starting point to compare your own plan against. Not advice, and it knows nothing about your income, taxes or other accounts.",
  'target weights': "The model's suggested split, with what each fund costs to own, what it yields, and how badly it has fallen in the past. Weights are targets to rebalance toward, not prices to chase.",
  'contribution projection': "What steady annual contributions would compound to at the blended historical return of these funds. Arithmetic on the past, not a forecast. The band shows uncertainty in the average rate, not the risk of a bad decade arriving early.",
  'what the roth wrapper changes': "Reasoning that applies specifically because this is a Roth: growth and distributions are never taxed, losses aren't deductible, and the annual limit is small.",
  'fund universe': "Every candidate fund measured over its full history (return, cost, volatility and worst drawdown) so you can see why the model picked what it picked, and what it left out.",
  'correlation': "How closely two funds move together, from -1 to +1. Near +1 means owning both adds little diversification; the low pairs are what actually reduce risk.",
  'drift from target': "How far your actual holdings have wandered from the model weights. Markets cause this on their own. Whatever grows fastest ends up overweight, quietly making the portfolio riskier than you chose.",
  "where to put this year's contribution": "A buy-only rebalancing plan: point new money at whatever is underweight and drift closes without selling anything. The simplest maintenance there is.",
  'overlap in your holdings': "Pairs of your holdings that move almost identically. Owning both feels like diversification but isn't. It's one bet at double the size, with twice the paperwork.",
  'individual stock sleeve': "An optional slice for single companies, capped by your risk setting and horizon, with each candidate gated on its long-run record. The concentrated part of the portfolio, sized so a single blow-up can't derail the plan.",

  // ---- optic's positions
  "optic's positions": "The terminal's own simulated trading record. Whenever a scan finds a setup that clears the conviction bar, it takes the trade on paper. Both as shares and as the option contract it recommended. And holds it until a stop, target, time limit or expiry closes it. It exists so the recommendations can be judged on results instead of on how confident they sound.",
  'track record': "Results across every closed trade. Win rate on its own is close to meaningless. A strategy can win 70% of the time and still lose money if the losses are bigger. Expectancy, the average result per trade, is the number that decides whether an edge exists.",
  'open positions': "Trades the terminal currently holds on paper, marked at the latest available price. These P&L numbers move with the market and are not final. Nothing counts until the position closes.",
  'closed trades': "Every completed trade with the reason it ended. The exit reasons are the honest part: a record full of time stops means the signals were early or wrong, not just unlucky.",
  'scan history': "When the terminal last looked for trades, how many tickers it considered and how many it actually took. Most scans should open nothing. A system that finds a trade every time it looks isn't being selective.",
  'how the shortlist was chosen': "The funnel behind every scan. The universe is the whole NASDAQ, but running the full analysis on 3,000 stocks would take hours, so a cheap price-and-volume screen ranks them first and only the top names get the real work. This panel shows what was dropped at each step and why, so \"we scan the whole exchange\" and \"we analysed thirty names\" are both visible at once rather than one standing in for the other.",
  'screen ranking': "The screen's own ordering. A trend and momentum score built from price and volume alone. It is not the terminal's verdict and carries no options, news or fundamental input; its only job is to choose what gets a closer look. A name at the top of this table can still be rejected outright by the full analysis.",
  'month by month': "The record split by calendar month, so consistency is visible rather than hidden inside one all-time total. Six steady months and one lucky month can produce the same headline number and mean completely different things, and splitting by month also lines each result up against the market conditions it was trading in.",
  'consistency': "Every month since the record began, including months with no trades at all. Equity carries forward, so each month's return is measured against what the account was worth when that month started. Watch the shape of the run, not the best month.",
  'closed in this month': "Trades that finished during the selected month. These are the only results that count toward that month's realised figures.",
  'opened in this month and still held': "Positions started in the selected month that haven't closed yet. Their profit or loss is unrealised and will land in whichever month they eventually close.",
  'how these positions are taken': "The fixed rules the ledger follows: what it will take, how big, and when it gets out. They're set in advance and applied identically to every ticker, so the record can't be improved after the fact by changing its mind.",
  'position sizing': "How the size of each trade is decided. Shares are sized so that being stopped out costs a fixed fraction of the account, which means a volatile stock with a wide stop gets a smaller position. Options are sized on the whole premium, because a long option really can go to zero.",

  'growth vs the broad market (qqq / spy)': "Whether high-growth megacaps are leading or lagging the wider market. Rising means money favors long-duration growth; falling means it's rotating to value and cyclicals. A style-leadership read, not a direction call.",
  'index regime': 'Where the major indices sit in their own long-run cycle. The backdrop every individual stock trades against. A great company in a falling index still usually falls.',
  'long-term view': 'The multi-year picture for owning the shares outright: structural trend, drawdown history, and whether current prices are a reasonable place to accumulate. Options play no part at this horizon.',
  'weekly structure': 'Price history in weekly bars, which strips out daily noise so the underlying multi-year trend is visible.',
  'drawdown': "How far below its all-time high the asset sits now, and how deep past declines went. The downside you'd have had to sit through.",
  'return & risk': 'Long-run returns alongside how much volatility you had to endure to earn them. High returns from a wild ride are not the same as steady ones.',
  'valuation & accumulation': 'Whether the stock looks expensive or cheap versus its own history, and the price zones where long-term buyers have stepped in before.',

  // ---- sub-sections
  'fundamental momentum': "Which way the company's numbers are trending. Whether analysts are raising or cutting forecasts, how recent quarters landed against expectations, and whether revenue and margins are expanding. It is shown next to the composite rather than inside it: revision trends do carry signal over a few weeks, but the composite is a technicals-led read and folding fundamentals in would move every score in the terminal. Valuation is left out entirely, because at a two-to-eight-week horizon it tells you nothing about direction.",
  'component scores': 'The individual inputs behind the overall verdict and the weight each one carries, so you can see what is driving the number.',
  "what's driving it": 'The specific readings that pushed the score to where it is.',
  'what makes up this score': "Every factor the model weighed and the points each contributed, so you can see where the number came from. The weightings are the author's judgement, not a fitted model. Read the factors, not just the total.",
  'volatility context': 'Whether options are currently expensive or cheap compared with how much the stock has actually been moving. Expensive options favor selling premium over buying it.',
  'what would create a trade': 'The price levels that would turn the current no-trade read into an actionable setup.',
  'where to enter': 'The price zone the terminal considers a reasonable entry, as opposed to chasing a move already underway.',
  'entry zone levels': 'The specific prices that bound the suggested entry area.',
  'target & risk': 'Where the trade is aiming, and the level that would prove the idea wrong.',
  'candidate strikes, ranked': 'Option contracts scored against each other on cost, liquidity and probability of working out.',
  'notable contracts': 'Individual option contracts with unusual volume or open interest relative to their own normal. Often where new positioning is showing up.',
  'at-the-money greeks by expiry': 'How sensitive the closest-to-price options are, broken out by expiry date.',
  'gamma concentration by expiry': 'Which expiry dates hold the most dealer hedging pressure. Near-dated concentration makes price moves sharper.',
  'net gex by strike': 'Dealer hedging pressure at each individual strike price.',
  'gamma profile across spot': 'How dealer hedging pressure would change if the stock moved up or down from here. Where the tape flips from calm to fast.',
  'key levels': 'The strikes acting most like a ceiling or a floor because of how options are positioned there.',
  'fibonacci levels': 'Pullback prices derived from a mathematical ratio, used as rough guesses for where a move might pause. Widely watched, which is part of why they sometimes work.',
  'support & resistance': "Price levels the stock has genuinely reversed at, scored on four things: how many times price turned there, how firmly it was rejected (long wicks beat bars that closed at their extreme), how much volume traded across the level, and how recently it was last defended. Unlike Fibonacci, these come from actual candle history rather than a ratio.",
  'moving averages': 'Average prices over various periods, used to define the trend and act as moving support or resistance.',
  'rotation': 'Which sectors money is moving into and out of right now. The shift beneath a flat-looking index.',
  'equal-weight vs cap-weight (rsp / spy)': 'Whether the average stock is keeping up with the megacaps. When it is not, the index is being carried by a few names and the rally is narrower than it looks.',
  'accumulation zones': 'Price areas where long-term buyers have historically stepped in. Useful for staging purchases rather than buying all at once.',
  'headlines': 'Recent news articles, each scored for tone.',
  'catalyst types detected': 'The kinds of events the headlines mention. Earnings, guidance, product news, legal, or M&A.',
  'next report': 'When the company next reports earnings. Options usually stay expensive into that date and cheapen sharply after it.',
  'recent insider transactions': 'Buying and selling by the company’s own executives and directors.',
  'largest reported holders': 'The biggest institutional shareholders, from their most recent filings.',
  'why': 'The specific readings behind this verdict, so you can judge the reasoning rather than trusting the score.',
  'why the chart reads': 'The individual technical signals behind the bias, and which way each one is pointing.',

  // ---- cross-asset dashboard group headings
  'volatility': "How much movement the market expects. Rising volatility means traders are paying up for protection. Usually a warning sign for stocks.",
  'rates': 'Government bond yields. Rising yields make future company profits worth less today, which pressures growth stocks hardest.',
  'fx': 'Currencies. A strong US dollar tightens global financial conditions and squeezes overseas earnings; a fast-falling yen can force a global unwind.',
  'commodities': 'Raw materials. Oil and copper strength can signal real demand, but a spike becomes a cost shock that squeezes profit margins.',
  'credit': "Corporate bonds. Credit markets usually crack before stocks do, so weakness here is one of the earliest warnings you'll get.",
  'equity': 'The major stock indices themselves, for direct comparison against everything else on this dashboard.',
  'crypto': 'Bitcoin and friends, treated here as a pure risk-appetite gauge. It tends to move first and hardest when speculative money shifts.',
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
/* Chart mounting, deferred and chunked.
 *
 * Measured on a Swing load: nineteen charts went from zero to nineteen in a single
 * step inside one 100ms task. Nothing arrived progressively — the tab sat empty and
 * then lurched into existence, which is what "all at once and laggy" describes, and
 * 100ms of blocked main thread is six dropped frames on the way.
 *
 * Two changes, and the second matters more than the first.
 *
 * **Off-screen charts wait.** Of nineteen charts maybe three are visible; the rest
 * are built for a scroll position the reader has not reached. An IntersectionObserver
 * builds each one shortly before it comes into view. A hidden tab never intersects
 * at all, so switching to it is what triggers its charts — which is also more
 * correct than the old width-720 fallback, because by then the host has a real width
 * and the chart is not built to a guessed one.
 *
 * **Visible charts build one per frame.** Yielding between them turns one long task
 * into several short ones. The total work is the same; the difference is that the
 * browser can paint and respond between each, so panels fill in rather than
 * appearing together after a freeze.
 *
 * Only builder functions are deferred. A legend or a plain node is cheap and mounts
 * synchronously — deferring those would add latency for no gain.
 */
const CHART_QUEUE = [];
const PENDING_HOSTS = new Set();
let chartQueueRunning = false;
let chartSweeper = null;

function buildChartNow(host, builder) {
  // Zero width means the host is not laid out yet — a collapsed panel, or a view
  // that is not the active one. Building here would size the chart to a guess, so
  // report failure and let the sweeper come back to it.
  const w = Math.round(host.clientWidth);
  if (!w) return false;
  const el = builder(Math.max(w, 320));
  if (!el) return true;
  host.innerHTML = '';
  host.appendChild(el);
  host.style.minHeight = '';
  // After insertion, never before: the draw-on animation measures each path's
  // length, and a detached node reports zero.
  animateChart(el);
  return true;
}

function settleHost(host) {
  PENDING_HOSTS.delete(host);
  CHART_BUILDERS.delete(host);
  delete host.dataset.chartPending;
  if (chartObserver) chartObserver.unobserve(host);
}

/* The safety net, and the reason this is not observer-only.
 *
 * Deferring a build means something has to guarantee it eventually happens. An
 * IntersectionObserver does not: it never reports a host inside a `display: none`
 * ancestor, so a chart in a collapsed panel or an inactive tab would wait forever
 * — and because the host is cleared up front, "forever" looks like a permanently
 * empty box. That is exactly what happened to the main price chart.
 *
 * So the observer is only an accelerator. This sweep is what makes the deferral
 * safe: it runs while anything is pending and builds whatever has become
 * measurable, whether that is because the reader scrolled, expanded a panel or
 * switched tab. It stops itself when the set empties.
 */
function ensureChartSweeper() {
  if (chartSweeper || !PENDING_HOSTS.size) return;
  chartSweeper = setInterval(() => {
    if (!PENDING_HOSTS.size) {
      clearInterval(chartSweeper);
      chartSweeper = null;
      return;
    }
    [...PENDING_HOSTS].forEach((host) => {
      if (!host.isConnected) { settleHost(host); return; }
      if (!host.clientWidth) return;              // still not laid out
      const builder = CHART_BUILDERS.get(host);
      if (!builder) { settleHost(host); return; }
      if (buildChartNow(host, builder)) settleHost(host);
    });
  }, 350);
}

function runChartQueue() {
  if (chartQueueRunning) return;
  chartQueueRunning = true;
  const step = () => {
    const job = CHART_QUEUE.shift();
    if (!job) { chartQueueRunning = false; return; }
    // The host may have been replaced by a re-render between queueing and now.
    if (job.host.isConnected && job.host.dataset.chartPending === job.token) {
      if (buildChartNow(job.host, job.builder)) settleHost(job.host);
      else {
        // Not measurable yet — hand it to the sweeper rather than dropping it.
        CHART_BUILDERS.set(job.host, job.builder);
        PENDING_HOSTS.add(job.host);
        ensureChartSweeper();
      }
    }
    if (CHART_QUEUE.length) requestAnimationFrame(step);
    else chartQueueRunning = false;
  };
  requestAnimationFrame(step);
}

/* Declared before the observer that reads it. */
const CHART_BUILDERS = new WeakMap();
let chartToken = 0;

/* rootMargin gives the chart a screen's warning, so it is drawn before it scrolls
 * into view rather than popping in underneath the reader. */
const chartObserver = ('IntersectionObserver' in window)
  ? new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const host = entry.target;
      const builder = CHART_BUILDERS.get(host);
      if (!builder) { settleHost(host); return; }
      CHART_QUEUE.push({ host, builder, token: host.dataset.chartPending });
      chartObserver.unobserve(host);
      runChartQueue();
    });
  }, { rootMargin: '600px 0px' })
  : null;

/* Chart mounting, deferred and chunked.
 *
 * Measured on a Swing load: nineteen charts went from zero to nineteen in a single
 * step inside one 100ms task. Nothing arrived progressively — the tab sat empty and
 * then lurched into existence, which is what "all at once and laggy" describes.
 *
 * Visible charts now build one per animation frame, so one long task becomes
 * several short ones and the browser can paint between them. Charts well below the
 * fold wait for the observer. Anything the observer cannot see is caught by the
 * sweeper above, so no deferral can strand a chart.
 *
 * Only builder functions are deferred. A legend or a plain node is cheap and mounts
 * synchronously — deferring those would add latency for no gain.
 */
function mount(id, node) {
  const host = document.getElementById(id);
  if (!host) return;
  if (typeof node !== 'function') {
    if (node) { host.innerHTML = ''; host.appendChild(node); }
    return;
  }
  const token = String(++chartToken);
  host.dataset.chartPending = token;
  // Cleared up front, even though the build is deferred: leaving the old node in
  // place meant a host below the fold kept showing the PREVIOUS ticker's chart
  // until it scrolled into view, and a stale chart under a new heading is worse
  // than an empty box because nothing marks it stale. The reserved height stops
  // the page jumping when the real one lands.
  if (host.firstChild) {
    host.innerHTML = '';
    if (!host.style.minHeight) host.style.minHeight = '160px';
  }

  const box = host.getBoundingClientRect();
  const near = !chartObserver
    || (box.top < window.innerHeight + 600 && box.bottom > -600);
  if (near) {
    CHART_QUEUE.push({ host, builder: node, token });
    runChartQueue();
    return;
  }
  CHART_BUILDERS.set(host, node);
  PENDING_HOSTS.add(host);
  chartObserver.observe(host);
  ensureChartSweeper();
}

/* ------------------------------------------------------------------ reveal */

const REVEAL_STEP_MS = 55;   // gap between consecutive panels
/* Past this the step tightens instead of stopping. A hard cap gave every panel
   after the tenth an identical delay, so on a 27-panel tab eighteen of them
   arrived together — the stagger died exactly where a long page needs it most. */
const REVEAL_SOFT_MS = 420;
const REVEAL_TAIL_MS = 14;   // per-panel step once past the soft knee
const REVEAL_CAP_MS = 900;   // absolute ceiling, so nothing waits about
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
  'last': 'How long ago the level was last tested, in bars. So 17w means seventeen weeks ago on a weekly chart.',
  'role': 'Whether this level sits below the current price (support, a potential floor) or above it (resistance, a potential ceiling).',
  'value': 'The current value of the average, in dollars.',
  'price vs': 'Where the stock is trading relative to that average, as a percentage. Positive means price is above it.',
  '10-day slope': 'Whether the average itself is rising or falling over the last ten days. The direction of the trend, not just where price sits.',
  'level': 'The Fibonacci retracement percentage this line is drawn at.',
  'level ($)': 'The price of the level, with whether it sits below the current price (support) or above it (resistance).',
  'spread': 'The gap between the best bid and the best ask, as a percentage of the mid price. Wider spreads cost more to get in and out of.',
  'type': 'Call or put.',
  'setup': 'What the numbers suggest doing, if anything.',
  'thesis': 'The reasoning behind the pair. Why one side should outperform the other.',
  'betting on': 'Which way the trade needs the stock to go. Bullish makes money as the stock rises, bearish as it falls. A bought put is a bearish bet even though the contract itself is owned, which is why the direction is spelled out rather than left as long or short.',
  'paid': 'The price the position was opened at, and underneath it the latest price it is marked at. For an option both are premium per share, not the share price.',
  'where it stands': 'How far the stock has travelled along the line between the stop and the target. The small tick is where the trade opened, the dot is where the stock is now, and the shaded stretch between them is the ground it has covered.',
  'up or down': 'Profit or loss at the latest mark, in dollars and as a percentage of what was paid. Nothing is settled until the position closes, so treat every figure here as provisional.',
  'if stopped': 'The loss this position was sized to take if the stop is hit. It was decided before the trade opened, which is what makes the total risk on the page a real ceiling rather than an estimate.',
  'signal score': 'How strongly the scan rated this setup when it opened, out of 100. Shown as strength only. The direction it was rating is the Betting on column, so a bearish 44 and a bullish 44 both read as 44 here rather than one of them as minus 44. It is a record of why the trade was taken, not a live reading: it is not recalculated as the position runs.',
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

/* One observer for the whole app, created lazily.
 *
 * A fresh IntersectionObserver per render would leak one per view switch, and
 * they are cheap to share: the callback only ever reads the entry it was given.
 *
 * rootMargin pulls the trigger line 12% up from the bottom of the viewport, so
 * a panel starts its fade slightly before it is fully exposed. Triggering
 * exactly at the edge means the motion finishes off-screen on a fast scroll and
 * the reader sees a static panel arrive. */
let revealObserver = null;

function revealOnEnter(el, delayMs) {
  if (!revealObserver) {
    revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const node = entry.target;
        node.style.animationDelay = `${node.dataset.revealDelay || 0}ms`;
        node.classList.add('reveal');
        // Once revealed, stop watching. A panel that re-animates every time it
        // re-enters the viewport turns an entrance into a flicker on any scroll
        // back up the page.
        revealObserver.unobserve(node);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.01 });
  }
  el.dataset.revealDelay = String(Math.round(delayMs));
  revealObserver.observe(el);
}

/* Stagger panels in as they reach the viewport.
 *
 * This used to fire every panel's animation at render time. Anything below the
 * fold therefore played its entrance while off-screen and was finished long
 * before it was scrolled to, so the effect existed only for the two or three
 * panels that happened to be visible on load. On a long view most of the work
 * was invisible by construction.
 *
 * Panels already on screen keep the render-time stagger, because they ARE the
 * arrival; panels below wait for the scroll. The delay curve is unchanged:
 * linear up to a soft knee, compressed after it, hard-capped, so a view with
 * thirty panels does not make the last one wait two seconds.
 */
function revealPanels(host) {
  if (!host) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  host.classList.remove('revealing');
  // Reading offsetWidth forces a reflow, so re-adding the class restarts the
  // animation instead of the browser collapsing the remove/add into a no-op.
  void host.offsetWidth;
  host.classList.add('revealing');

  const fold = window.innerHeight || 800;
  let onScreen = 0;

  host.querySelectorAll('.panel').forEach((el) => {
    el.classList.remove('reveal');
    const box = el.getBoundingClientRect();
    const visible = box.top < fold && box.bottom > 0;

    if (visible) {
      // Index by how many are already on screen, not by position in the list,
      // so the visible group staggers 0, 55, 110... regardless of how many
      // panels sit below the fold.
      const linear = onScreen * REVEAL_STEP_MS;
      onScreen += 1;
      const delay = linear <= REVEAL_SOFT_MS
        ? linear
        : REVEAL_SOFT_MS + (linear - REVEAL_SOFT_MS) * (REVEAL_TAIL_MS / REVEAL_STEP_MS);
      el.style.animationDelay = `${Math.round(Math.min(delay, REVEAL_CAP_MS))}ms`;
      el.classList.add('reveal');
    } else if (typeof IntersectionObserver === 'function') {
      // Below the fold: a short fixed delay rather than a growing one. Its
      // stagger comes from the order it is scrolled into, not from its index.
      revealOnEnter(el, 40);
    } else {
      el.classList.add('reveal');
    }
  });

  // Then sweep the rest of the view.
  //
  // A view is not built by one call. Each loader renders into its own host and
  // calls this with that host, so panels belonging to a different host were
  // never seen here: measured on Macro, 11 panels sat below the fold and 1 was
  // observed. The other 10 were visible but inert, which made the effect look
  // broken rather than absent — some panels faded in and most did not.
  //
  // Cheap enough to do unconditionally: one querySelectorAll over a view that
  // holds tens of panels, and observing an element twice is a no-op in the
  // IntersectionObserver API anyway.
  armViewReveals();
}

/** Observe every panel in the active view that no host has claimed yet. */
function armViewReveals() {
  if (typeof IntersectionObserver !== 'function') return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const view = document.querySelector('.view.active');
  if (!view) return;
  const fold = window.innerHeight || 800;
  view.querySelectorAll('.panel').forEach((el) => {
    if (el.classList.contains('reveal') || el.dataset.revealDelay !== undefined) return;
    const box = el.getBoundingClientRect();
    if (box.top < fold && box.bottom > 0) {
      // Already on screen when it appeared: show it now rather than waiting for
      // a scroll that may never come.
      el.classList.add('reveal');
    } else {
      revealOnEnter(el, 40);
    }
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

/* Recognised from the message, not from a flag threaded through fifteen call
 * sites. getJSON produces exactly two shapes for an unreachable origin — "the
 * server is unreachable (HTTP 5xx) after N attempts" and "the connection dropped
 * after N attempts" — and matching on those means every view that renders an
 * error gets the better copy and the recovery poller, including the ones added
 * later by someone who has never read this function. */
const ORIGIN_DOWN_RE = /(server is unreachable|connection dropped).*attempts/i;

function errorHTML(msg, opts = {}) {
  const down = opts.originUnreachable || ORIGIN_DOWN_RE.test(String(msg || ''));
  if (!down) {
    return `<div class="error-box"><strong>Could not load.</strong> ${esc(msg)}</div>`;
  }
  /* The tunnel case, which needs different words.
   *
   * This is not a bug in the request — the whole origin is gone. The address
   * this page was opened from is a temporary Cloudflare quick tunnel, and it
   * gets a brand-new hostname every time it restarts, so there is nothing the
   * client can do to find the replacement. Saying so is more useful than
   * repeating the status code, and the poller below means a short blip heals
   * without anyone reloading.
   */
  startOriginWatch();
  return `<div class="error-box">
    <strong>The server is not reachable.</strong> ${esc(msg)}.
    <div class="error-note">This address is a temporary tunnel, and it changes
      every time the server restarts. So if it has rotated, this link is dead
      and no reload will bring it back. Watching for it to return…
      <span id="origin-watch-state">checking</span>.</div>
    <div class="error-acts">
      <button type="button" class="btn" data-origin-retry>Try again now</button>
    </div>
  </div>`;
}

/* Poll the origin until it answers, then reload once.
 *
 * A tunnel blip lasts seconds and a rotation is permanent, and the page cannot
 * tell them apart from the outside. So it watches: if the origin comes back the
 * view recovers on its own, and if it never does the message has already said
 * the link is dead. Backs off to 15s so a genuinely dead address is not polled
 * every two seconds for the rest of the day.
 */
let originWatchTimer = null;
let originWatchDelay = 3000;
function startOriginWatch() {
  if (originWatchTimer) return;
  const tick = async () => {
    originWatchTimer = null;
    const label = document.getElementById('origin-watch-state');
    try {
      const res = await fetch('/healthz', { cache: 'no-store' });
      if (res.ok) {
        if (label) label.textContent = 'back. Reloading';
        // One reload, not a re-render: the origin having gone away and returned
        // means anything cached in memory may describe a server that has since
        // restarted.
        setTimeout(() => window.location.reload(), 400);
        return;
      }
    } catch (e) { /* still down */ }
    originWatchDelay = Math.min(originWatchDelay * 1.6, 15000);
    if (label) label.textContent = `still down, next check in ${Math.round(originWatchDelay / 1000)}s`;
    originWatchTimer = setTimeout(tick, originWatchDelay);
  };
  originWatchTimer = setTimeout(tick, originWatchDelay);
}

/* The write token, for the few actions that change the record.
 *
 * Reading every panel is open to anyone. Starting a scan, re-marking positions
 * and clearing the alert inbox are not, because the hosted ledger is the track
 * record and a stranger appending trades to it is indistinguishable from the
 * owner doing so.
 *
 * Kept in localStorage rather than a cookie: it is not a session, there is
 * nothing to log into, and a cookie would be sent on every request including
 * the reads that do not want it. */
const WRITE_TOKEN_KEY = 'optic.writeToken';

function writeToken() {
  try { return localStorage.getItem(WRITE_TOKEN_KEY) || ''; } catch (e) { return ''; }
}

function setWriteToken(value) {
  try {
    if (value) localStorage.setItem(WRITE_TOKEN_KEY, value);
    else localStorage.removeItem(WRITE_TOKEN_KEY);
  } catch (e) { /* private mode: it will ask again next time */ }
}

async function postJSON(url, body) {
  const headers = { 'Content-Type': 'application/json' };
  const token = writeToken();
  if (token) headers['X-Optic-Token'] = token;
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body || {}),
  });
  // 401 means this action needs the token. Ask once, store it, and retry — so
  // the owner is prompted at the moment it matters instead of meeting a bare
  // "unauthorised" with no way to act on it.
  if (res.status === 401) {
    const supplied = window.prompt(
      'This action changes the saved record, so it needs the write token.\n'
      + 'Set OPTIC_WRITE_TOKEN on the server, then paste it here.');
    if (supplied) {
      setWriteToken(supplied.trim());
      return postJSON(url, body);
    }
  }
  if (!res.ok) {
    // HTTP/2 carries no status text, so res.statusText is '' over the tunnel and
    // over any modern host — which surfaced as a bare "Could not load." with no
    // reason at all. The status code is always available, so it's the fallback,
    // and 5xx from a proxy gets named because that failure is about the
    // connection rather than anything the app did.
    let detail = '';
    try { detail = ((await res.json()).detail || '').toString(); } catch (e) { /* not JSON */ }
    if (!detail) {
      detail = res.status >= 502 && res.status <= 530
        ? `the server is unreachable (HTTP ${res.status}). The tunnel may have dropped`
        : `${res.statusText || 'request failed'} (HTTP ${res.status})`;
    }
    throw new Error(detail);
  }
  return res.json();
}

/* A proxy 5xx is usually a blink, not a diagnosis.
 *
 * The link runs through a tunnel, and the tunnel's edge occasionally answers one
 * request with 520 or 502 while it reconnects — the next request goes through
 * fine. Reported from a real load: the page header rendered, one panel came back
 * 520, and the whole view was replaced by "the server is unreachable" on a site
 * that was working a second either side of it.
 *
 * So GETs retry. They are reads with no side effects, which is what makes this
 * safe; POSTs deliberately do not, because "run a scan" is not something to fire
 * twice because an acknowledgement went missing.
 *
 * Only connection-shaped failures qualify. A 404 or a 500 from the app itself is
 * an answer, and repeating the question will not change it.
 */
/* Sized against what the tunnel actually does.
 *
 * Its log shows the edge connection dropping every three or four minutes and
 * coming back in anything from one to twelve seconds — and a free quick tunnel
 * holds exactly one connection (`--ha-connections 4` is accepted and ignored),
 * so there is no second link to carry traffic while the first reconnects. Every
 * drop is therefore a total outage for its whole duration.
 *
 * A first pass at this used 600ms and 1800ms, which covers a 2.4-second gap and
 * would have missed most of the real ones. These four cover about sixteen
 * seconds, which covers all of them observed so far, and the first retry is
 * still fast enough that a one-second blip is invisible. */
const RETRY_DELAYS_MS = [500, 1500, 4000, 9000];

function worthRetrying(status) {
  // 502/503/504 from any proxy, and Cloudflare's own 520-530 range.
  return status === 502 || status === 503 || status === 504
    || (status >= 520 && status <= 530);
}

async function getJSON(url) {
  let lastDetail = '';
  let attempts = 0;

  for (let i = 0; i <= RETRY_DELAYS_MS.length; i += 1) {
    attempts = i + 1;
    let res;
    try {
      res = await fetch(url);
    } catch (err) {
      // A dropped connection throws rather than returning a status. Same class
      // of failure, same treatment.
      lastDetail = 'the connection dropped';
      if (i < RETRY_DELAYS_MS.length) {
        await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[i]));
        continue;
      }
      break;
    }

    if (res.ok) return res.json();

    // HTTP/2 carries no status text, so res.statusText is '' over the tunnel and
    // over any modern host — which surfaced as a bare "Could not load." with no
    // reason at all. The status code is always available, so it's the fallback,
    // and 5xx from a proxy gets named because that failure is about the
    // connection rather than anything the app did.
    let detail = '';
    try { detail = ((await res.json()).detail || '').toString(); } catch (e) { /* not JSON */ }
    if (detail) throw new Error(detail);           // the app answered; that is the answer

    if (!worthRetrying(res.status)) {
      throw new Error(`${res.statusText || 'request failed'} (HTTP ${res.status})`);
    }
    lastDetail = `the server is unreachable (HTTP ${res.status})`;
    if (i < RETRY_DELAYS_MS.length) {
      await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[i]));
    }
  }

  /* Marked, so the error box can offer recovery instead of just a status code.
   *
   * A reader who gets this cannot fix it from the page: the app was served from
   * an address that has since stopped resolving, and the client has no way to
   * discover the new one. Saying "HTTP 530 after 5 attempts" is accurate and
   * useless. The box that renders this explains what actually happened and
   * starts watching for the origin to come back. */
  const err = new Error(`${lastDetail} after ${attempts} attempts`);
  err.originUnreachable = true;
  throw err;
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
  { id: 'America/New_York', label: 'New York. Eastern (market time)' },
  { id: 'America/Chicago', label: 'Chicago: Central' },
  { id: 'America/Denver', label: 'Denver: Mountain' },
  { id: 'America/Los_Angeles', label: 'Los Angeles. Pacific' },
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
    pulse: '<strong>Not financial advice.</strong> Pulse states which way the <em>data</em> leans and how strongly. That is a reading of numbers on this screen, not a recommendation for you: it knows nothing about your horizon, capital, tax position or other holdings, and cannot judge whether any of this suits you. It can be confidently wrong. The inputs are delayed, several are labelled proxies, and a lean is not a forecast.',
    swing: '<strong>Not a recommendation.</strong> The strikes, limit prices, stops and targets on this tab are model output, not advice to place any trade. Options can expire worthless and lose the entire premium.',
    long: '<strong>Not a recommendation.</strong> A conviction score summarises historical data. It says nothing about whether this holding suits your horizon, taxes or existing exposure.',
    roth: '<strong>Not retirement or tax advice.</strong> A rules-based illustration to compare against your own plan. It is not tailored to your income, tax situation, other accounts or goals, and contribution limits and eligibility change. Confirm current rules with the IRS and a licensed professional.',
    earnings: '<strong>Not a recommendation.</strong> Event pricing describes what the market is charging, not what you should do about it. Holding an option through a report can lose money even when the direction is right.',
    tracker: '<strong>Hypothetical performance.</strong> These positions were never placed with real money. Simulated results are prepared with the benefit of hindsight, assume fills at the mid price, and bear no commission, slippage, financing, borrow cost or tax. No real account would necessarily achieve results resembling these, and simulated performance does not indicate future results.',
    market: '<strong>Not a recommendation.</strong> A regime read on the market as a whole, not a view on any individual security, and not advice to change your positioning.',
    indices: '<strong>Not a recommendation.</strong> Long-run index context, not advice to buy, sell or hold any index fund.',
    brief: '<strong>Not a recommendation.</strong> A summary of published news, not analysis of it, and not a view on any security mentioned. Headlines belong to their publishers and link to the original, and nothing here has been verified independently. Scheduled releases are calendar dates, not forecasts.',
  },
};

/** The per-view notice, as markup to prepend to a view. */
function legalBanner(view) {
  const text = LEGAL.areas[view];
  if (!text) return '';
  return `<div class="legal-area" role="note">${text}</div>`;
}

/* The assistant's own notice. Pulse now commits to a directional read, which is
 * the one place in the app where model output most resembles a recommendation —
 * so it says so above the conversation rather than only in the page footer. */
function initPulseLegal() {
  const host = document.getElementById('pulse-legal');
  if (host) host.innerHTML = LEGAL.areas.pulse || '';
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

const CHART_MODE_KEY = 'optic.chart.mode';
const SHOW_FIB_KEY = 'optic.chart.fib.v2';
const SHOW_SR_KEY = 'optic.chart.sr.v2';
const CHART_RANGE_KEY = 'optic.chart.range';

const CHART_INTERVAL_KEY = 'optic.chart.interval';

// Bar counts per interval, so "3M" means 63 daily bars or 13 weekly ones rather
// than 63 of whatever is selected.
const CHART_RANGES = [
  // Intraday ranges are a different kind of thing from the rest: they come from
  // their own endpoint at their own resolution, and the daily-derived overlays
  // (moving averages, Fibonacci, RSI, MACD) do not apply to them. Marked so the
  // renderer can suppress what would otherwise be drawn from the wrong series.
  { key: '1d', label: '1D', intraday: true },
  { key: '5d', label: '5D', intraday: true },
  { key: '1m', label: '1M', daily: 21, weekly: 5 },
  { key: '3m', label: '3M', daily: 63, weekly: 13 },
  { key: '6m', label: '6M', daily: 126, weekly: 26 },
  { key: '1y', label: '1Y', daily: 252, weekly: 52 },
  { key: 'all', label: 'All', daily: Infinity, weekly: Infinity },
];

// The long-term chart's own controls. Separate keys from the swing chart's: the
// two answer different questions, and a 6-month daily view is meaningless on a
// twelve-year structure chart, so the preferences shouldn't leak between them.
const LT_MODE_KEY = 'optic.lt.mode';
const LT_RANGE_KEY = 'optic.lt.range';
const LT_INTERVAL_KEY = 'optic.lt.interval';

// Bar counts per interval. The server sends ~627 weekly bars (12 years).
const LT_RANGES = [
  { key: '1y', label: '1Y', weekly: 52, monthly: 12 },
  { key: '3y', label: '3Y', weekly: 156, monthly: 36 },
  { key: '5y', label: '5Y', weekly: 260, monthly: 60 },
  { key: '10y', label: '10Y', weekly: 520, monthly: 120 },
  { key: 'all', label: 'All', weekly: Infinity, monthly: Infinity },
];
const LT_INTERVALS = [
  { key: 'weekly', label: 'Weekly' },
  { key: 'monthly', label: 'Monthly' },
];

let ltMode = 'line';
let ltRange = '5y';
let ltInterval = 'weekly';
try {
  const m = localStorage.getItem(LT_MODE_KEY);
  if (m === 'line' || m === 'candle') ltMode = m;
  const r = localStorage.getItem(LT_RANGE_KEY);
  if (LT_RANGES.some((x) => x.key === r)) ltRange = r;
  const i = localStorage.getItem(LT_INTERVAL_KEY);
  if (LT_INTERVALS.some((x) => x.key === i)) ltInterval = i;
} catch (e) { /* private mode */ }

/** Roll weekly OHLCV bars up to calendar months. */
function aggregateMonthly(ser) {
  const dates = ser.dates || [];
  if (!dates.length) return ser;
  const out = { dates: [], open: [], high: [], low: [], close: [], volume: [] };
  let key = null;
  dates.forEach((d, i) => {
    const monthKey = d.slice(0, 7);
    const o = (ser.open || [])[i], h = (ser.high || [])[i],
      l = (ser.low || [])[i], c = (ser.close || [])[i], v = (ser.volume || [])[i];
    if (c === null || c === undefined) return;
    if (monthKey !== key) {
      key = monthKey;
      out.dates.push(d); out.open.push(o); out.high.push(h);
      out.low.push(l); out.close.push(c); out.volume.push(v || 0);
    } else {
      const j = out.close.length - 1;
      // Open stays the month's first, close becomes its last, extremes extend.
      if (h !== null && h !== undefined) out.high[j] = Math.max(out.high[j], h);
      if (l !== null && l !== undefined) out.low[j] = Math.min(out.low[j], l);
      out.close[j] = c;
      out.volume[j] = (out.volume[j] || 0) + (v || 0);
    }
  });
  out.monthly = true;
  return out;
}

/** Slice a long-term series to the selected timeframe. */
function ltSlice(ser, rangeKey, intervalKey) {
  const base = intervalKey === 'monthly' ? aggregateMonthly(ser) : ser;
  const spec = LT_RANGES.find((r) => r.key === rangeKey) || LT_RANGES[2];
  const want = intervalKey === 'monthly' ? spec.monthly : spec.weekly;
  const total = (base.dates || []).length;
  const take = want === Infinity ? total : Math.min(want, total);
  const cut = (a) => (Array.isArray(a) ? a.slice(total - take) : a);
  return {
    dates: cut(base.dates), open: cut(base.open), high: cut(base.high),
    low: cut(base.low), close: cut(base.close), volume: cut(base.volume),
    shown_bars: take, total_bars: total, monthly: !!base.monthly,
  };
}

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
let showFib = false;
let showSR = false;
// The averages and the volume strip were always on. They are levels too, and a
// reader who wants to see raw price action was previously stuck with four
// overlays they could not remove.
let showMA = false;
let showVol = true;
let showVbp = false;
let showInsiders = false;
let showZones = false;
let showEMA = false;
// Auto trend lines. New, and shared with the Swing chart like the rest.
let showTrends = false;
const SHOW_TRENDS_KEY = 'optic.chart.trends.v1';
// Session dividers — the vertical dashed lines that mark where one trading day
// ends and the next begins. Only meaningful on an intraday chart, where the gap
// between 16:00 and 09:30 is invisible in the bars but is where most of the
// move happened.
let showSessions = false;
const SHOW_SESSIONS_KEY = 'optic.chart.sessions.v1';
const SHOW_MA_KEY = 'optic.chart.ma.v2';

/* One flag per average, not one per family.
 *
 * The Indicators menu shows six checkboxes — SMA 20/50/200, EMA 9/21/50 — and
 * all six wrote to two variables, so clicking any one silently flipped its two
 * neighbours. The code even said so: "a checkbox that silently also cleared its
 * two neighbours would be worse than one labelled honestly", and then shipped
 * exactly that. The stated reason — the server sends the family as a unit — is
 * not true either: sma20, sma50 and sma200 arrive as separate arrays and always
 * have.
 *
 * The family flags stay, meaning "any member of this family is on", because the
 * Swing tab's single Moving averages checkbox and the Clear-all still want that
 * question answered. Seeded from the family flag on first read, so an existing
 * reader's chart looks the same after this change as before it. */
const MA_MEMBERS = ['sma20', 'sma50', 'sma200'];
const EMA_MEMBERS = ['ema9', 'ema21', 'ema50'];
const seriesFlagKey = (id) => `optic.chart.series.${id}.v1`;
const seriesOn = {};

function loadSeriesFlags() {
  const seed = (ids, family) => ids.forEach((id) => {
    let stored = null;
    try { stored = localStorage.getItem(seriesFlagKey(id)); } catch (e) { /* private */ }
    seriesOn[id] = stored === null ? family : stored === 'on';
  });
  seed(MA_MEMBERS, showMA);
  seed(EMA_MEMBERS, showEMA);
}

function setSeriesFlag(id, on) {
  seriesOn[id] = !!on;
  try { localStorage.setItem(seriesFlagKey(id), on ? 'on' : 'off'); } catch (e) { /* private */ }
  // Keep the family flag meaning "any of these is on", so the Swing checkbox
  // and anything else reading it stays truthful.
  if (MA_MEMBERS.includes(id)) {
    showMA = MA_MEMBERS.some((m) => seriesOn[m]);
    storeFlag(SHOW_MA_KEY, showMA);
  } else if (EMA_MEMBERS.includes(id)) {
    showEMA = EMA_MEMBERS.some((m) => seriesOn[m]);
    storeFlag(SHOW_EMA_KEY, showEMA);
  }
}

/** Whether one average should be drawn: its own switch, and its family's. */
function seriesShown(id) {
  return !!seriesOn[id];
}

/** Turn a whole family on or off — what the Swing tab's single checkbox means. */
function setFamily(which, on) {
  (which === 'ema' ? EMA_MEMBERS : MA_MEMBERS).forEach((id) => {
    seriesOn[id] = !!on;
    try { localStorage.setItem(seriesFlagKey(id), on ? 'on' : 'off'); } catch (e) { /* private */ }
  });
  if (which === 'ema') { showEMA = !!on; storeFlag(SHOW_EMA_KEY, on); }
  else { showMA = !!on; storeFlag(SHOW_MA_KEY, on); }
}
const SHOW_VOL_KEY = 'optic.chart.vol.v2';
const SHOW_VBP_KEY = 'optic.chart.vbp.v2';
const SHOW_INS_KEY = 'optic.chart.insiders.v2';
const SHOW_ZONES_KEY = 'optic.chart.zones.v2';
const SHOW_EMA_KEY = 'optic.chart.ema.v2';
try {
  chartMode = localStorage.getItem(CHART_MODE_KEY) === 'candle' ? 'candle' : 'line';
  const savedRange = localStorage.getItem(CHART_RANGE_KEY);
  if (CHART_RANGES.some((r) => r.key === savedRange)) chartRange = savedRange;
  const savedInterval = localStorage.getItem(CHART_INTERVAL_KEY);
  if (CHART_INTERVALS.some((i) => i.key === savedInterval)) chartInterval = savedInterval;
  /* The chart opens as price and volume, and nothing else.
   *
   * Everything else is opt-in — moving averages included. With the families that
   * had accumulated by default, one chart carried three averages, ten dashed
   * Fibonacci and support lines, shaded supply and demand bands, insider markers
   * and five channel overlays: fifteen lines and eleven price tags stacked down
   * the right edge. A chart that has to be decluttered before it can be read is
   * not showing price.
   *
   * The keys are versioned (.v2) for a reason that matters more than the defaults:
   * a stored preference beats a default, so changing the default alone would have
   * left every browser that had already switched things on exactly as cluttered.
   * Bumping the key discards the accumulated state once, so everyone gets the
   * clean chart and builds their own view back up from it.
   *
   * Volume stays on. It is a separate strip under the price rather than a line
   * across it, so it costs nothing in legibility and reading volume with price is
   * not an advanced option.
   */
  showFib = localStorage.getItem(SHOW_FIB_KEY) === 'on';
  showSR = localStorage.getItem(SHOW_SR_KEY) === 'on';
  showMA = localStorage.getItem(SHOW_MA_KEY) === 'on';
  showVol = localStorage.getItem(SHOW_VOL_KEY) !== 'off';
  showVbp = localStorage.getItem(SHOW_VBP_KEY) === 'on';
  showInsiders = localStorage.getItem(SHOW_INS_KEY) === 'on';
  showZones = localStorage.getItem(SHOW_ZONES_KEY) === 'on';
  showEMA = localStorage.getItem(SHOW_EMA_KEY) === 'on';
  loadSeriesFlags();
} catch (e) { /* private mode */ }

// Bars shown in the MACD panel. Capped independently of the price chart: a
// crossover is a short-horizon event, and at 500 bars two lines a few points
// apart are one thick stroke. Roughly a quarter of a trading year on dailies.
/* Smallest momentum window worth drawing.
 *
 * This used to be a hard cap: RSI and MACD clamped to 70 bars no matter what the
 * price chart showed, which was defensible when there was no timeframe control —
 * a 500-bar MACD is an unreadable hairline and you could not see where the cross
 * happened. Now the pills govern the tab, so clamping meant picking "1Y" and
 * getting a year of price above 70 days of momentum: three charts stacked
 * vertically, sharing an x-axis label, disagreeing about what period they show.
 *
 * It is kept as a *floor* instead. Choosing "1M" gives 21 price bars, and a MACD
 * over 21 bars has barely emerged from its own 26-bar warm-up — so the momentum
 * panels widen to at least this many bars and say so in their headings. */
const MACD_WINDOW = 70;

/** Bars the momentum panels show. Always what the timeframe pill selected.
 *
 * A floor was tried here and could not work: the MACD series is sliced to the
 * price window upstream, so asking for more bars than that returned fewer than
 * the heading promised — "last 70 days" above a 21-bar chart. One control
 * governing every panel is the point, so the panels take the window they are
 * given and report it honestly. Pick a wider pill for a longer momentum read. */
function momentumBars(shown, available) {
  return Math.min(Number(shown) || available, available);
}

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
    return `<p class="caveat" style="margin:var(--space-2) 0 0">No crossover in the last ${zoom} ${unit}s —
      ${what} has stayed ${gap >= 0 ? 'above' : 'below'} its signal line throughout, so momentum has
      not changed direction in this window. The gap is currently
      ${widening ? 'widening' : 'narrowing'}${widening ? '' : ', which is what precedes a cross'}.</p>`;
  }
  const when = cross.barsAgo === 0
    ? `on the latest ${unit}`
    : `${cross.barsAgo} ${unit}${cross.barsAgo === 1 ? '' : 's'} ago`;
  const date = dates[cross.index] ? ` (${esc(dates[cross.index])})` : '';
  return `<p class="caveat" style="margin:var(--space-2) 0 0">Last crossover: ${what} crossed
    <strong>${cross.bullish ? 'above' : 'below'}</strong> its signal line ${when}${date}. A
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


/** Is the selected timeframe an intraday one? */
function isIntradayRange(key) {
  const spec = CHART_RANGES.find((r) => r.key === (key || chartRange));
  return !!(spec && spec.intraday);
}

/* Build a price_series-shaped object from intraday bars.
 *
 * Shaped identically to the daily series so the chart code needs no special
 * case — but deliberately WITHOUT sma20/sma50/sma200/ema21. Those are daily
 * averages; overlaying a 200-day line on a chart of the last six hours would
 * draw a flat line across the top and imply it means something here. The same
 * reasoning is why the momentum panels stay on daily bars and say so. */
function intradaySeries(intra) {
  if (!intra || !intra.available) return null;
  return {
    dates: intra.times || [],
    close: intra.closes || [],
    volume: intra.volumes || [],
    shown_bars: intra.bars || 0,
    total_bars: intra.bars || 0,
    intraday: true,
    interval: intra.interval,
    weekly: false,
  };
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
  // Every array gets cut, rather than a named list of them.
  //
  // The named list is how adding ema9 and ema50 to the payload broke the chart:
  // they were not in it, so the `...ps` spread passed them through at full length
  // — 492 points against 126 dates. lineChart sizes its x-axis from the longest
  // series it is handed, so the plot stretched to 492 bars and the y-axis was
  // dragged down to prices from two years ago. Everything in price_series is a
  // series except `bars`, which is a number, so "slice every array" is both
  // correct and immune to the next field someone adds.
  const out = { ...ps };
  Object.keys(out).forEach((key) => {
    if (Array.isArray(out[key])) out[key] = cut(out[key]);
  });
  return {
    ...out,
    shown_bars: take, total_bars: total, weekly: !!ps.weekly,
  };
}

// A handful of liquid, recognisable starting points rather than a "top movers"
// list, which would need its own endpoint and would be stale outside market hours.
const HOME_QUICK_PICKS = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'AMD', 'MSFT', 'IWM'];

/* The landing cards, grouped exactly as the navigation is.
 *
 * They drifted twice: once when the tab strip was reordered, and again when the
 * nav was regrouped — Roth kept a card of its own after moving inside Optic's
 * Positions, while Read and Scan had no card at all despite being two of the
 * five sections. A landing page that describes a different terminal from the one
 * the bar navigates is worse than no landing page.
 *
 * Grouping them under the same headings is the fix that keeps them honest: a new
 * section has to be placed somewhere, so it cannot be silently omitted. */
const HOME_SECTIONS = [
  {
    group: 'analyse',
    label: 'Analyse a ticker',
    note: 'Load a symbol and these three work it from different angles.',
    cards: [
      {
        view: 'swing',
        color: 'var(--s1)',
        title: 'Swing / Options',
        body: 'Composite verdict from technicals, dealer gamma, vanna and charm, flow and news, plus a strike and expiry recommendation with an entry trigger, and whether the sector agrees.',
      },
      {
        view: 'earnings',
        color: 'var(--s5)',
        title: 'Earnings',
        body: 'A written pre-earnings brief, surprise history against how the stock actually traded afterwards, estimate revisions, and whether the options market is overcharging for the event.',
      },
      {
        view: 'long',
        color: 'var(--s4)',
        title: 'Long-Term Shares',
        body: 'For buying and holding the shares themselves: ten-year structure, drawdown history, accumulation zones, valuation against its own history, and a conviction score. No options here.',
      },
    ],
  },
  {
    group: 'market',
    label: 'Read the market',
    note: 'No ticker needed. What happened, what is scheduled, and what kind of tape this is.',
    cards: [
      {
        view: 'brief',
        color: 'var(--s6, var(--s3))',
        title: 'Read',
        body: 'The release moving the tape right now with its cross-asset reaction, a weekly market update, fear and greed with every input shown, the macro calendar including opex and VIX expiry, and a searchable library of catalysts with the companies connected to them.',
      },
      {
        view: 'market',
        color: 'var(--s3)',
        title: 'Macro & Sectors',
        body: 'Cross-asset regime from VIX, the dollar, rates and commodities. Every sector against its overnight levels and whether money is rotating in or out, plus implied correlation. How much the market is paying for names to move together.',
      },
      {
        view: 'indices',
        color: 'var(--s7)',
        title: 'Indices',
        body: 'The major index ETFs against their prior-session range with a written read on each, then where the indices sit in their own long-run cycle: multi-year returns, drawdown from the high, and whether the average stock is keeping pace with the megacaps.',
      },
    ],
  },
  {
    group: 'scan',
    label: 'Find candidates',
    note: 'Named questions asked of the whole ranked universe.',
    cards: [
      {
        view: 'scan',
        color: 'var(--s2)',
        title: 'Scan',
        body: 'Seven named scans over the names that clear the screen\'s liquidity and history gates. Breakouts, pullbacks, unusual volume, steady trends, and the weak side too. Each one states what it cannot see.',
      },
      {
        view: 'scan',
        color: 'var(--s8)',
        title: 'Does the score work?',
        body: 'The one panel here that tests a claim instead of making one. It replays the screen\'s score through history and reports whether it predicted anything, measured against a random score and against a single raw momentum number.',
      },
    ],
  },
  {
    group: 'portfolio',
    label: 'Track a book',
    note: 'The terminal\'s own record, and a long-horizon baseline.',
    cards: [
      {
        view: 'tracker',
        color: 'var(--s2)',
        title: "Optic's Positions",
        body: "The terminal's own paper-traded record. When a scan finds a setup good enough it takes the trade. As shares and as the option it recommended, with a stop, a target and a size, then holds it to the exit. Book-level risk sits above it: whether those positions are separate bets or one bet with several tickets.",
      },
      {
        view: 'tracker',
        color: 'var(--s8)',
        title: 'Roth IRA model',
        body: 'Inside Optic\'s Positions. A rules-based model allocation of low-cost index funds from your horizon and risk tolerance, with cost, correlation and a contribution projection. Not advice. A baseline to compare your own plan against.',
      },
    ],
  },
];

function renderHome() {
  hideTip();
  const quick = HOME_QUICK_PICKS
    .map((t) => `<button type="button" data-pick="${t}">${t}</button>`)
    .join('');

  // Clickable: a card that describes a destination should be a way to reach it.
  const cards = HOME_SECTIONS.map((sec) => `
    <section class="home-sec">
      <h2 class="home-sec-title">${esc(sec.label)}</h2>
      <p class="home-sec-note">${esc(sec.note)}</p>
      <div class="home-cards">${sec.cards.map((c) => `
        <button type="button" class="home-card" data-goto-view="${esc(c.view)}"
          style="--accent:${c.color}">
          <h3>${esc(c.title)}</h3>
          <p>${esc(c.body)}</p>
        </button>`).join('')}</div>
    </section>`).join('');

  views.home.innerHTML = `
  <div class="home">
    <svg class="home-logo" viewBox="0 0 32 32" aria-label="Optic Terminal logo" role="img">
      <!-- No outer ring. The header's brand-mark has never had one, so the two
           marks now match; the ring also boxed in a shape whose whole point is
           that it is an aperture. Only the eye group is left, which is what the
           blink scales. -->
      <g class="home-logo-eye">
        <path d="M2.6 16C6.3 8.9 10.9 5.4 16 5.4S25.7 8.9 29.4 16C25.7 23.1 21.1 26.6 16 26.6S6.3 23.1 2.6 16Z"
              fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" opacity="0.7"/>
        <!-- pathLength="100" normalises the dash maths: the redraw can then be
             written as an offset from 0 to 100 without measuring the path. -->
        <path class="home-logo-line" pathLength="100"
              d="M7.4 20.2 11.4 15.6 14.6 17.8 18.6 11.6 21.6 14 23.9 11.4"
              fill="none" stroke="var(--s1)"
              stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
        <circle class="home-logo-dot" cx="23.9" cy="11.4" r="1.5" fill="var(--s1)"/>
      </g>
    </svg>

    <h1 class="home-title">Optic <span>Terminal</span></h1>

    <p class="home-proto">
      <strong>Prototype.</strong> A personal research project, still being built. Expect rough
      edges, gaps in the data and figures that lag the market. It is a tool for forming a view,
      not a recommendation to act on one.
    </p>

    <p class="home-lede">
      A market research workbench, from a multi-week swing to a multi-year hold. Load a ticker
      and it works through the technical structure, options positioning, earnings and financial
      growth, analyst estimates, news tone and the macro backdrop. Then puts them together into
      one read, and tells you where the inputs disagree.
    </p>

    <form class="home-search" id="home-form">
      <div class="combo">
        <input id="home-input" placeholder="Search a ticker or company. E.g. NVDA or Apple"
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
      <span class="dot-sep"><span class="chip neutral" style="padding:var(--space-0) var(--space-2)"><span class="dot"></span>Checking data source…</span></span>
    </div>
  </div>`;

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
    `<span class="dot-sep"><span class="chip ${realtime ? 'bull' : 'neutral'}" style="padding:var(--space-0) var(--space-2)"><span class="dot"></span>${
      realtime ? `real-time chains via ${esc(provider)}` : `${esc(provider)} feed · quotes delayed ~15 min`}</span></span>`,
    `<span class="dot-sep"><span class="chip ${assistantOn ? 'bull' : 'neutral'}" style="padding:var(--space-0) var(--space-2)"><span class="dot"></span>${
      assistantOn ? `${ASSISTANT_NAME} ready` : `${ASSISTANT_NAME} needs an API key`}</span></span>`,
    '<span>Greeks computed locally via Black-Scholes. Analysis only, not investment advice.</span>',
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
  const sx = d.structure || {};
  // Sliced for display before the template is built — the panel heading reads
  // shown_bars, and `const` has no hoisting, so this must precede it.
  // Support/resistance and Fibonacci stay computed server-side on full history,
  // so narrowing the view never changes the levels.
  // Intraday ranges come from their own endpoint, in the same shape, so the
  // chart code below needs no special case. What they deliberately lack is the
  // daily-derived overlays — see intradaySeries().
  const intra = (STATE.intraday && STATE.intraday.ticker === STATE.ticker
    && STATE.intraday.range === chartRange) ? STATE.intraday : null;
  const psIntra = isIntradayRange(chartRange) ? intradaySeries(intra) : null;
  const ps = psIntra || sliceSeries(d.technicals && d.technicals.price_series ? d.technicals.price_series : {}, chartRange, chartInterval);
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

  const cs = d.cases || {};
  const caseList = (rows, kind) => (rows || []).map((a) => `<li class="case-row">
    <span class="case-dot ${kind} s${a.strength}"></span>
    <div>
      <strong>${esc(a.claim)}</strong>
      <span class="case-src">${esc(a.source)}</span>
      <div class="case-detail">${gloss(a.detail)}</div>
    </div>
  </li>`).join('');

  const html = `

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Swing verdict')} · ${esc(d.ticker)}</h2>
      <p class="sub">${gloss(v.summary || '')}</p>
      <div style="display:flex;align-items:flex-end;gap:var(--space-5);flex-wrap:wrap">
        <div>
          <div class="hero-label">Composite</div>
          <div class="hero ${Math.round(v.composite_score || 0) === 0
    ? 'flat' : signClass(v.composite_score)}">${
  Math.round(v.composite_score || 0) > 0 ? '+' : ''}${fmt(v.composite_score, 0)}</div>
          <div class="note subnote sm">Out of ±100</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:var(--space-2)">
          ${toneChip(v.stance)}
          <span class="chip neutral"><span class="dot"></span>Conviction: ${esc(v.conviction || 'n/a')}</span>
          ${v.signal_agreement_pct !== null && v.signal_agreement_pct !== undefined
    ? `<span class="chip neutral"><span class="dot"></span>${fmt(v.signal_agreement_pct, 0)}% signal agreement</span>` : ''}
        </div>
      </div>

      <h3>${hg('What makes up this score')}${askPulse('composite')}</h3>
      <p class="sub">${gloss(v.scale_note || '')}</p>
      <table class="data">
        <thead><tr><th>Input</th><th>Score</th><th>Status</th><th>Weight</th><th>Adds</th><th></th></tr></thead>
        <tbody>
        <!-- An excluded input gets a row, a reason and the weight it would have
             carried, rather than a dimmed line saying "n/a".
             The composite renormalises over whatever is available, which means a
             score built from three of five inputs reads identically to one built
             from all five. Naming what dropped out, and what it was worth, is the
             difference between a number you can audit and one you take on trust. -->
        ${(v.breakdown || []).map((b) => `<tr${b.unavailable ? ' class="row-excluded"' : ''}>
          <td class="name">${esc(cap(b.component))}</td>
          <td class="${signClass(b.score)}">${b.unavailable ? '—'
    : (b.score > 0 ? '+' : '') + fmt(b.score, 0)}</td>
          <td>${b.unavailable
    ? `<span class="chip bear"><span class="dot"></span>Excluded</span>
       <div class="caveat" style="margin:var(--space-0) 0 0">${esc(b.status_reason || '')}</div>`
    : '<span class="chip neutral"><span class="dot"></span>Included</span>'}</td>
          <td>${b.unavailable
    ? `<span class="muted">0% <span class="caption">(of ${
      fmt(b.nominal_weight_pct, 0)}%)</span></span>`
    : fmt(b.weight_pct, 0) + '%' + (b.nominal_weight_pct !== undefined
      && b.nominal_weight_pct !== null && Math.abs(b.nominal_weight_pct - b.weight_pct) >= 1
      ? `<div class="caveat" style="margin:var(--space-0) 0 0">nominal ${fmt(b.nominal_weight_pct, 0)}%, up on a redistribution</div>` : '')}</td>
          <td class="${signClass(b.contribution)}">${b.unavailable ? '—'
    : (b.contribution > 0 ? '+' : '') + fmt(b.contribution, 1)}</td>
          <td>${b.unavailable ? '' : `<span data-bar="${b.score}"></span>`}</td>
        </tr>`).join('')}
        <tr style="border-top:1px solid var(--border-strong)">
          <td class="name"><strong>Composite</strong></td><td></td><td></td><td></td>
          <td class="${signClass(v.composite_score)}"><strong>${v.composite_score > 0 ? '+' : ''}${fmt(v.composite_score, 1)}</strong></td>
          <td></td>
        </tr>
        </tbody>
      </table>
      <p class="sub" style="margin-top:var(--space-2)">Bullish at +30, leaning at +10, and the mirror
        image on the downside.</p>
      <!-- Explanations sit below rather than in a table column: this panel is half-width,
           and a prose column there truncated instead of wrapping.

           Collapsed by default. This is the same five paragraphs of glossary on
           every ticker, and expanded it made the panel roughly three times the
           height of the quote panel beside it. The mismatch left ~500px of dead
           column to its right, and pushed the chart below the fold. What each
           input measures is worth one click when you want it and noise when you
           don't; the scores and weights it explains stay visible above. -->
      <details class="factor-defs-wrap">
        <summary>What each input measures</summary>
        <dl class="factor-defs">
          ${(v.breakdown || []).map((b) => `<dt>${esc(cap(b.component))}</dt>
            <dd>${gloss(b.measures)}</dd>`).join('')}
        </dl>
      </details>
      <!-- Conflicts used to be stacked here as callouts. Optic's Perspective now
           lists every one of them as a bear-side argument, so repeating them made
           the same warning appear twice on one screen, and the three callouts
           were what pushed this panel to ~880px against the quote panel's ~390px,
           leaving a ~490px empty column beside it. -->
      <p class="caveat">${esc(d.data_caveat || '')}</p>
    </div>

    <div class="panel">
      <h2>${hg('Quote')}</h2>
      <p class="sub">${esc(q.name || '')}${q.exchange ? ' · ' + esc(q.exchange) : ''}</p>
      <div style="display:flex;align-items:flex-end;gap:var(--space-4);flex-wrap:wrap;margin-bottom:var(--space-3)">
        <div>
          <div class="hero-label">${extQ ? 'Regular close' : 'Last'}</div>
          <div class="hero">${fmt(q.price, 2)}</div>
        </div>
        <div class="${signClass(q.change_pct)}" style="font-size:var(--t-heading);font-weight:600">
          ${q.change !== null && q.change !== undefined ? (q.change > 0 ? '▲ ' : q.change < 0 ? '▼ ' : '') + fmt(q.change, 2) : ''}
          (${fmtPct(q.change_pct, 2)})
        </div>
        ${extQ ? `<div>
          <div class="hero-label">${esc(extQ.kind)}</div>
          <div class="hero ${signClass(extQ.pct)}" style="font-size:var(--t-d3)">${fmt(extQ.price, 2)}</div>
          <div class="${signClass(extQ.pct)} small">${
    fmtPct(extQ.pct, 2)} vs the close</div>
        </div>` : ''}
      </div>
      ${extQ ? `<p class="caveat" style="margin:-4px 0 var(--space-3)">Extended-hours trade, on a fraction of
        regular-session volume. Every other number in this panel, and every level on the chart.
        Is measured from the ${usd(q.price)} close, not from here.</p>` : ''}
      ${kv([
    ["Today's range", `${usd(q.day_low)} – ${usd(q.day_high)}`],
    ['52-week range', `${usd(q.fifty_two_low)} – ${usd(q.fifty_two_high)}`],
    ['Volume vs 3m avg', q.volume && q.avg_volume ? `${fmtCompact(q.volume)} (${fmt(q.volume / q.avg_volume * 100, 0)}%)` : '—'],
    ['ATR (14)', `${fmt((t.volatility || {}).atr14, 2)} (${fmt((t.volatility || {}).atr_pct, 2)}%)`],
    // 20-day realized vol used to sit here too. It is in Volatility context twice
    // over — as its own row and inside the window ladder — so this was the third
    // copy of one number on one page.

    ['Expected 2-week range', `±${fmt((t.volatility || {}).expected_2w_move_pct, 1)}%`],
    ['Market cap', fmtCompact(q.market_cap)],
    ['Sector', esc(q.sector || '—')],
  ])}
    </div>
  </div>

  ${cs.available ? `<div class="panel gap">
    <h2>${hg("Optic's Perspective")} · ${esc(d.ticker)}</h2>
    <p class="sub">On the numbers below, ${esc(cs.balance)}. Every line cites what
      triggered it, so you can check it against the panel it came from.</p>
    <div class="grid c2">
      <div class="case-col bull">
        <h3><span class="case-tag bull">Bull</span> Why it could work</h3>
        ${cs.bull && cs.bull.length ? `<ul class="case-list">${caseList(cs.bull, 'bull')}</ul>`
    : '<p class="caveat">Nothing in today\'s data argues the long side.</p>'}
      </div>
      <div class="case-col bear">
        <h3><span class="case-tag bear">Bear</span> What could break it</h3>
        ${cs.bear && cs.bear.length ? `<ul class="case-list">${caseList(cs.bear, 'bear')}</ul>`
    : '<p class="caveat">Nothing in today\'s data argues the short side.</p>'}
      </div>
    </div>
    <p class="caveat">${gloss(cs.method || '')}</p>
  </div>` : ''}

  <!-- Fundamental momentum, moved out of the swing-verdict panel.
       Its own first line says it is not part of the score above, so it was never
       really part of that panel. And it was what made the panel 1299px tall
       against the quote panel's 500px, leaving ~800px of dead column beside it.
       Full width also suits it better: the readings and their explanations sit
       side by side here instead of stacking in a half-width column. -->
  ${renderCloseDefence(d.close_defence, { horizonWord: 'today' })}

  ${em.available ? `<div class="panel gap">
    <h2>${hg('Fundamental momentum')} <span class="chip ${
    em.tone === 'good' ? 'bull' : em.tone === 'bad' ? 'bear' : 'neutral'}"
      style="margin-left:var(--space-2)"><span class="dot"></span>${esc(cap(em.read))}</span></h2>
    <p class="sub"><strong>Not part of the composite score.</strong> Shown because revisions and
      surprise history do carry signal over a few weeks. Read alongside the composite, not
      folded into it.</p>
    <!-- Stacked, not two columns. The readings table is short and the definition
         list beside it is roughly twice its height, so at panel width the pair
         wrapped and left a 442x265 empty cell inside the card. -->
    <div>
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
    </div>
    <p class="caveat">${gloss(em.excluded_note || '')}</p>
  </div>` : ''}

  ${renderSectorConfirm(d.sector_confirm)}

  <div id="patterns-host" class="span-all">${renderPatterns(d)}</div>

  <div id="seasonality-host" class="span-all">${renderSeasonality(STATE.seasonality)}</div>

  <div id="extras-host" class="span-all">${renderExtras(STATE.extras)}</div>



  ${renderEntryPlan(d.entry_plan)}

  <div class="grid c2 gap">
    <div class="panel span2">
      <h2>${hg('Price, moving averages & Fibonacci')}${askPulse('profile')} <span class="th-plain">· ${
  ps.intraday ? `${esc(ps.interval || '')} bars, ${ps.shown_bars} over ${
    chartRange === '1d' ? 'today' : 'five sessions'}`
    : `${ps.weekly ? 'weekly' : 'daily'} bars, ${ps.shown_bars} of ${ps.total_bars} shown`}</span></h2>
      ${ps.intraday
    ? `<p class="sub">Intraday price only. The moving averages, Fibonacci levels, RSI and
        MACD on this tab are all computed from <strong>daily</strong> closes. Drawing a
        200-day line across six hours of trade would put a flat line on the chart and imply
        it meant something here, so they are left off rather than redrawn from the wrong
        series. The panels below still show the daily read.</p>`
    : `<p class="sub">Bias <strong>${esc(t.bias || 'n/a')}</strong>· ${fibDirectionSentence(t)}
        ${showFib || showSR
    ? 'Levels you have switched on are drawn as shaded bands rather than lines. A Fibonacci interval and a support shelf are both ranges, and a hairline claims a precision neither has. The band price currently sits in is labelled.'
    : 'Fibonacci and support levels are off. Switch them on under <em>Technical Levels</em>. They are still listed in the tables below.'}</p>`}
      ${isIntradayRange(chartRange) && intra && intra.loading
    ? '<p class="sub">Loading intraday bars…</p>' : ''}
      ${isIntradayRange(chartRange) && intra && intra.available === false
    ? `<div class="callout">${esc(intra.reason || 'Intraday bars are unavailable for this symbol.')}</div>` : ''}
      ${ps.intraday && intra && intra.session_note
    ? `<p class="caveat">${esc(intra.session_note)}</p>` : ''}
      <div class="chart-toolbar">
        <label class="range-pick"${ps.intraday ? ' hidden' : ''}>Interval
          <select id="chart-interval"${ps.intraday ? ' disabled' : ''}>
            ${CHART_INTERVALS.map((i) => `<option value="${i.key}"${
  i.key === chartInterval ? ' selected' : ''}>${i.label}</option>`).join('')}
          </select>
        </label>
        ${rangePills(CHART_RANGES, chartRange, 'data-chart-range', 'Timeframe')}
        <div class="seg" role="group" aria-label="Chart style">
          <button type="button" data-chart-mode="line"
            aria-pressed="${chartMode === 'line'}">Line</button>
          <button type="button" data-chart-mode="candle"
            aria-pressed="${chartMode === 'candle'}">Candles</button>
        </div>
        <details class="lvl-menu">
          <summary aria-label="Indicators">
            <span class="lvl-icon" aria-hidden="true"></span>Indicators${
  indicatorIds.length ? ` <span class="lvl-count">${indicatorIds.length}</span>` : ''}
            <i class="cal-caret" aria-hidden="true"></i>
          </summary>
          <div class="lvl-pop wide" role="group" aria-label="Indicator visibility">
            <p class="lvl-note">Overlays draw on this chart. The rest need their own
              scale. RSI is 0-100, on-balance volume is a share count. So they get a
              pane underneath rather than being squeezed onto the price axis.</p>
            ${indicatorIds.length ? `<button type="button" class="lvl-clear"
              data-clear-indicators>Clear all</button>` : ''}
            ${IND_FALLBACK_CATALOGUE.map((r) => {
    const on = indicatorIds.includes(r.id);
    const overlay = IND_PRICE_PANE.includes(r.id);
    return `<label class="lvl-opt" title="${esc(r.measures)}">
              <input type="checkbox" data-ind="${esc(r.id)}"${on ? ' checked' : ''}
                ${ps.intraday && overlay ? 'disabled' : ''}>
              <span class="ind-drop-name">${esc(r.name)}</span>
              <span class="ind-drop-where">${overlay ? 'on the chart' : 'own pane'}</span>
            </label>`;
  }).join('')}
          </div>
        </details>

        <details class="lvl-menu">
          <summary aria-label="Technical levels">
            <span class="lvl-icon" aria-hidden="true"></span>Technical Levels${
  levelCount() ? ` <span class="lvl-count">${levelCount()}</span>` : ''}
            <i class="cal-caret" aria-hidden="true"></i>
          </summary>
          <div class="lvl-pop" role="group" aria-label="Technical level visibility">
            ${ps.intraday ? `<p class="lvl-note">These are all computed from daily
              closes, so none of them apply to an intraday chart. Pick 1M or wider
              to use them.</p>` : ''}
            <label class="lvl-opt"><input type="checkbox" data-level-opt="ma"
              ${showMA ? 'checked' : ''} ${ps.intraday ? 'disabled' : ''}>
              <span class="lvl-key ma"></span>Moving averages</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="fib"
              ${showFib ? 'checked' : ''} ${ps.intraday ? 'disabled' : ''}>
              <span class="lvl-key fib"></span>Fibonacci levels</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="sr"
              ${showSR ? 'checked' : ''} ${ps.intraday ? 'disabled' : ''}>
              <span class="lvl-key sr"></span>Support &amp; resistance</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="vol"
              ${showVol ? 'checked' : ''}>
              <span class="lvl-key vol"></span>Volume</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="vbp"
              ${showVbp ? 'checked' : ''}>
              <span class="lvl-key vbp"></span>Volume by price</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="insiders"
              ${showInsiders ? 'checked' : ''} ${ps.intraday ? 'disabled' : ''}>
              <span class="lvl-key ins"></span>Insider trades</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="ema"
              ${showEMA ? 'checked' : ''} ${ps.intraday ? 'disabled' : ''}>
              <span class="lvl-key ema"></span>EMA 9 / 21 / 50</label>
            <label class="lvl-opt"><input type="checkbox" data-level-opt="zones"
              ${showZones ? 'checked' : ''} ${ps.intraday ? 'disabled' : ''}>
              <span class="lvl-key zone"></span>Supply &amp; demand</label>
            ${levelCount() ? `<button type="button" class="lvl-clear" data-clear-levels>
              Clear all</button>` : ''}
          </div>
        </details>
      </div>
      <div id="legend-price"></div>
      <div id="chart-price"></div>
      <div id="chart-price-note"></div>

      <!-- Price location. Rides the same 20s poll as everything else on this
           tab: the server refreshes the forming bar from the live quote before
           deriving these, so they move with price rather than with the 5-minute
           history cache. -->
      ${sx.volume_profile && sx.volume_profile.available ? `
      <div class="grid c4" style="margin-top:var(--space-3)">
        ${tile('Value area', `${usd(sx.volume_profile.val)} – ${usd(sx.volume_profile.vah)}`,
    `Point of control ${usd(sx.volume_profile.poc)}. Price is ${esc(sx.volume_profile.location || '')}`,
    sx.volume_profile.location === 'above value' ? 'up'
      : sx.volume_profile.location === 'below value' ? 'down' : '')}
        ${(sx.pivots || {}).available ? tile('Today\'s pivot',
    usd(sx.pivots.pp),
    `R1 ${usd(sx.pivots.r1)} · S1 ${usd(sx.pivots.s1)} · ${
      sx.pivots.spot_above_pivot ? 'price is above it' : 'price is below it'}`,
    sx.pivots.spot_above_pivot ? 'up' : 'down') : ''}
        ${(sx.ema_stack || {}).available ? tile('EMA 9/21/50',
    cap(sx.ema_stack.read),
    `${usd(sx.ema_stack.ema9)} · ${usd(sx.ema_stack.ema21)} · ${usd(sx.ema_stack.ema50)}`,
    sx.ema_stack.bullish_stack ? 'up' : sx.ema_stack.bearish_stack ? 'down' : '') : ''}
        ${(sx.bandwidth || {}).available ? tile('Band width',
    `${fmt(sx.bandwidth.percentile, 0)}th pct`,
    `${fmt(sx.bandwidth.bandwidth_pct, 1)}% wide: ${esc(sx.bandwidth.read)}`) : ''}
      </div>
      ${(sx.volume_profile.lvns || []).length ? `<p class="caveat">Thin traded volume near ${
    sx.volume_profile.lvns.slice(0, 3).map((n) => usd(n.price)).join(', ')
  }. Moves tend to travel quickly through prices nobody is defending.</p>` : ''}
      ${(sx.candles || {}).patterns && sx.candles.patterns.length ? `<p class="caveat">${
    sx.candles.patterns.map((c) => `<strong>${esc(cap(c.pattern))}</strong> (${esc(c.direction)}) ${
      esc(c.date || '')}`).join(' · ')}. ${esc(sx.candles.note)}</p>` : ''}
      <p class="caveat">${gloss(sx.volume_profile.method || '')}</p>` : ''}

      <!-- Indicator panes, in the panel they belong to. An indicator that needs its
           own scale is still about THIS chart, so putting it in a separate panel
           further down the page meant scrolling away from the price to read
           something derived from it. -->
      <div id="ind-panes-host">${renderIndicatorPanes()}</div>

      <div class="grid c3" style="margin-top:var(--space-3)">
        <div>
          <h3>${hg('Support & resistance')}</h3>
          <p class="sub" style="margin-bottom:var(--space-2)">From ${chartInterval} candles, matching the
            chart above. Ranked by strength, not just how often price visited.</p>
          <table class="data">
            <!-- Four columns, not six. This table lives in a third-width panel, and
                 role reads naturally under the price while "5 touches, last 17w ago"
                 is one fact, not two. Six columns simply could not fit and the
                 table was overflowing into the panel beside it. -->
            <thead><tr><th>Level ($)</th><th>Distance</th><th>Strength</th><th>Touches</th></tr></thead>
            <tbody>${srComputed.map((l) => `<tr>
              <td class="name">${usd(l.price)}
                <div class="subnote">${esc(cap(l.role))}</div></td>
              <td class="${signClass(l.distance_pct)}">${fmtPct(l.distance_pct, 1)}</td>
              <td><strong>${fmt(l.strength, 0)}</strong><span data-bar="${l.strength}" data-bar-max="100"></span></td>
              <td>${fmt(l.touches, 0)}
                <div class="subnote">${l.last_touch_bars_ago === 0
    ? 'testing now' : 'last ' + l.last_touch_bars_ago + srUnit + ' ago'}</div></td>
            </tr>`).join('') || '<tr><td colspan="4" class="muted">Not enough repeated reversals in the lookback window.</td></tr>'}</tbody>
          </table>
          <p class="caveat">Strength blends four things: how many pivots cluster there, how much
            of each pivot bar was rejection wick rather than body, the share of total volume that
            traded across the level, and how recently it was last defended. Merge width scales
            with ATR, so a level is really a band. The table shows its midpoint. Switching the
            chart to weekly recomputes these from weekly bars, which surfaces bigger structural
            shelves and drops the minor daily ones.</p>
        </div>
        <div>
          <h3>${hg('Fibonacci levels')} <span class="chip ${
    ((t.fibonacci || {}).direction || '').toLowerCase() === 'bearish' ? 'bear' : 'bull'}"
            style="margin-left:var(--space-2)"><span class="dot"></span>${
    ((t.fibonacci || {}).direction || '').toLowerCase() === 'bearish'
      ? 'High → low' : 'Low → high'}</span></h3>
          <p class="sub" style="margin-bottom:var(--space-2)">${
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
              <td class="name muted">${esc(cap(l.role))}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>
        <!-- Spans the row rather than taking one cell. This grid holds three
             blocks but wraps to two columns at panel width, so the third sat
             alone with an empty cell beside it. A 343px void inside the card's
             border. Spanning costs no extra height: the row is as tall as this
             table either way. -->
        <div class="span-all">
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

  <div class="grid c2 gap momentum-row">
    <div class="panel">
      <h2>${hg('RSI (14)')} <span class="th-plain">· last ${
    ps.shown_bars || MACD_WINDOW} ${ps.weekly ? 'weeks' : 'days'}</span></h2>
      <p class="sub">${fmt((t.rsi || {}).value, 1)} out of 100: ${esc((t.rsi || {}).state || 'n/a')}.
        Above 70 is overbought, below 30 oversold; 50 divides bullish from bearish momentum.</p>
      <div id="legend-rsi"></div>
      <div id="chart-rsi"></div>
      <div id="rsi-cross-note"></div>
    </div>
    <div class="panel">
      <h2>${hg('MACD (12, 26, 9)')} <span class="th-plain">· last ${
    ps.shown_bars || MACD_WINDOW} ${ps.weekly ? 'weeks' : 'days'}</span></h2>
      <p class="sub">MACD ${fmt((t.macd || {}).macd, 3)} vs signal ${fmt((t.macd || {}).signal, 3)}:
        ${esc((t.macd || {}).state || 'n/a')}${(t.macd || {}).event ? `, ${esc(t.macd.event)}` : ''}.</p>
      <div id="legend-macd"></div>
      <div id="chart-macd"></div>
      <div id="macd-cross-note"></div>
    </div>
  </div>

  ${gex.error ? `<div class="panel gap"><h2>${hg('Options analytics')}</h2><div class="callout bad">${esc(gex.error)}</div></div>` : `
  <div class="grid c2 gap">
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

  <div class="grid c2 gap">
    <div class="panel span2">
      <h2>${hg('GEX. Dealer gamma exposure')}${askPulse('gex')}</h2>
      <p class="sub">Net ${(gex.totals || {}).net_gex >= 0 ? '+' : ''}$${fmtCompact((gex.totals || {}).net_gex)} of dealer delta per 1% move.
        Regime: <strong>${esc((gex.regime || {}).state || '')}</strong>.
        ${(gex.regime || {}).flip_point ? `Gamma flip at <strong>${fmt(gex.regime.flip_point, 2)}</strong> (${fmtPct((gex.regime || {}).flip_distance_pct, 2)} away).` : ''}</p>
      <div class="callout info">${gloss((gex.regime || {}).note || '')}<br><br><strong>For swings:</strong> ${gloss((gex.regime || {}).swing_implication || '')}</div>

      <div class="grid c2" style="margin-top:var(--space-3)">
        <div>
          <h3>${hg('Net GEX by strike')}</h3>
          <div id="legend-gex"></div>
          <div id="chart-gex"></div>
        </div>
        <div>
          <h3>${hg('Gamma profile across spot')}${askPulse('gamma-profile')}</h3>
          <p class="sub">Where the curve crosses zero is the flip point. Above it dealers dampen moves, below it they amplify them.</p>
          <div id="chart-gamma-profile"></div>
          <h3>${hg('Key levels')}${askPulse('levels')}</h3>
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

  ${renderVanna(gex)}

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Call vs put flow')}${askPulse('flow')}</h2>
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
      <p class="sub">Calls positive, puts negative. Where today's money actually went.</p>
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
        </tr>`).join('') || '<tr><td colspan="9" class="muted">No unusual activity above the volume and premium thresholds.</td></tr>'}</tbody>
      </table></div>
    </div>
  </div>

  <div class="panel gap">
    <h2>${hg('Buy calls / puts')}</h2>
    <p class="sub">Naked directional options. Quick-glance card in the same format as the strategies below.
      For a fully ranked set of strikes scored against a projected target, see the Strike &amp; Entry
      Recommendation panel above. Strikes and premiums are live from the chain, filtered for liquidity.
      Not recommendations. The sizing decision is yours.</p>
    ${(d.naked_ideas || []).length
    ? (d.naked_ideas || []).map(renderIdea).join('')
    : '<div class="callout">No naked directional idea. The composite read is neutral, so buying a call or put outright has no edge. See the strategies below for range-bound or volatility-driven setups instead.</div>'}
  </div>

  <div class="panel gap">
    <h2>${hg('Options strategies')}</h2>
    <p class="sub">Multi-leg and cross-underlying structures. Spreads, condors, straddles/strangles, and sector
      pair trades. Matched to the stance, the gamma regime, and (where relevant) implied-vol pricing.</p>
    ${(d.strategy_ideas || []).length
    ? (d.strategy_ideas || []).map(renderIdea).join('')
    : '<div class="callout">No strategy generated. The chain lacked liquid contracts at the target deltas.</div>'}
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
      ${(news.articles || []).map((a) => `<div style="padding:var(--space-2) 0;border-bottom:1px solid var(--grid)">
        <div style="display:flex;gap:var(--space-3);align-items:baseline;flex-wrap:wrap">
          ${toneChip(a.tone)}
          <a href="${esc(a.url)}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none;flex:1;min-width:240px">${esc(a.title)}</a>
          <span class="subnote">${esc(a.publisher)}${a.age_hours !== null ? ` · ${fmt(a.age_hours, 0)}h ago` : ''}</span>
        </div>
        ${a.summary ? `<div style="color:var(--ink-2);font-size:var(--t-small);margin-top:var(--space-1)">${esc(a.summary.slice(0, 220))}</div>` : ''}
        ${(a.catalysts || []).length ? `<div style="margin-top:var(--space-1)">${a.catalysts.map((c) => `<span class="chip neutral" style="margin-right:var(--space-1)"><span class="dot"></span>${esc(cap(c.type))}</span>`).join('')}</div>` : ''}
      </div>`).join('') || '<div class="muted">No headlines returned for this ticker.</div>'}
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
        label: claimLabel(c.price) ? `${c.name} · ${usd(c.price)}. Nothing above this` : '',
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
    /* Averages now take their colour and width from the shared style store, so a
     * change made in the Chart tab's indicator dialog shows up here too.
     *
     * That store's DEFAULTS are the collision-checked ones below; a colour the
     * user picked deliberately wins over them. This is a real trade and worth
     * naming: the automatic reassignment existed because in candle mode the
     * candles own the aqua/red pair and the mid average used to land ΔE 7 from
     * the Fibonacci lines. A hand-picked colour can walk back into that. The
     * dialog is the place someone is looking at the chart while choosing, so
     * they will see it — which is more than the old silent reassignment gave
     * anyone who disagreed with it. */
    const styleOf = (id) => overlayStyle(id);
    const maColors = candleMode
      ? { fast: C.s1, mid: C.s2, slow: C.s4 }
      : { fast: styleOf('sma20').color, mid: styleOf('sma50').color,
        slow: styleOf('sma200').color };

    // Everything the base chart is already using, so the overlays can take hues
    // nothing else on this plot has claimed. Collected here rather than assumed,
    // because candle mode and line mode occupy different slots.
    // The EMA fan gets its own hue family: fast-to-slow inside one colour would
    // be indistinguishable, and reusing the SMA colours makes a chart with both
    // families on unreadable.
    const emaColors = { fast: styleOf('ema9').color, mid: styleOf('ema21').color,
      slow: styleOf('ema50').color };
    const baseColors = candleMode
      ? [C.ink, C.s3, C.s8, maColors.fast, maColors.mid, maColors.slow]
      : [C.s1, maColors.fast, maColors.mid, maColors.slow];
    if (showFib && !ps.intraday) baseColors.push(C.refFib);
    if (showSR && !ps.intraday) baseColors.push(C.refSR);
    if (showVbp) baseColors.push(C.ink2);
    if (showInsiders && !ps.intraday) baseColors.push(C.s3, C.neg);
    if (showZones && !ps.intraday) baseColors.push(C.neg, C.s3);
    if (showEMA && !ps.intraday) {
      baseColors.push(emaColors.fast, emaColors.mid, emaColors.slow);
    }
    const overlayPalette = allocateOverlayColors(baseColors);
    // Kept on STATE so the written explanations below can show the same swatch as
    // the line on the chart. Recomputing it there would drift the moment the base
    // colours differ — which they do between line and candle mode.
    STATE.overlayPalette = overlayPalette;

    mount('legend-price', legend([
      ...(candleMode
        ? [{ name: ps.weekly ? 'Up week' : 'Up day', color: C.s3 },
          { name: ps.weekly ? 'Down week' : 'Down day', color: C.s8 }]
        : [{ name: 'Close', color: C.s1 }]),
      /* Derived from the same per-average switches as the series, so the
       * legend cannot name a line that is not on the chart. It previously
       * dropped the 200 entry on weekly while the series still drew it. */
      ...(ps.intraday ? [] : [
        ['sma20', ps.weekly ? '20-week SMA' : '20-day SMA', maColors.fast],
        ['sma50', ps.weekly ? '50-week SMA' : '50-day SMA', maColors.mid],
        ['sma200', '200-day SMA', maColors.slow],
      ].filter(([id]) => seriesShown(id)).map(([, name, color]) => ({ name, color }))),
      showFib && !ps.intraday ? { name: 'Fibonacci level', color: C.refFib, dash: true } : null,
      showSR && !ps.intraday ? { name: 'Support / resistance', color: C.refSR, dash: true } : null,
      showVbp ? { name: 'Volume by price', color: C.ink2, boxed: true } : null,
      showInsiders && !ps.intraday ? { name: 'Insider buy', color: C.s3, boxed: true } : null,
      showInsiders && !ps.intraday ? { name: 'Insider sell', color: C.neg, boxed: true } : null,
      // One entry per indicator, not per line. Keltner and Donchian each draw
      // several lines in one colour, and three legend rows reading "Keltner upper /
      // mid / lower" would be longer than the rest of the legend combined for no
      // extra information. Six unlabelled lines on the chart is the failure this
      // avoids — the reader could see them and not know which was VWAP.
      ...(ps.intraday ? [] : [
        ['ema9', 'EMA 9', emaColors.fast],
        ['ema21', 'EMA 21', emaColors.mid],
        ['ema50', 'EMA 50', emaColors.slow],
      ].filter(([id]) => seriesShown(id)).map(([, name, color]) => ({ name, color }))),
      ...(ps.intraday ? [] : indicatorOverlayLegend(overlayPalette)),
    ].filter(Boolean)));
    // Daily-derived overlays do not belong on an intraday chart: the averages
    // are not in the intraday series at all, and the Fib and support levels are
    // anchored to daily swings. Drawing them here would put lines on the chart
    // that describe a different timeframe from the one on screen.
    // Fibonacci and support/resistance are drawn as bands now; only the
    // resistance ceilings stay as lines, because a 52-week high is a single print
    // rather than a zone.
    const overlayRefs = ps.intraday ? [] : [
      ...ceilingRefs,
      // Fibs are lines again, not bands — see fibLines for why.
      ...(showFib ? fibLines((t.fibonacci || {}).levels, t.spot) : []),
    ];
    const levelBands = ps.intraday ? [] : [
      ...(showSR ? srBands(srLevels, (t.volatility || {}).atr14, t.spot) : []),
    ];
    const trendSegs = ps.intraday || !showTrends ? []
      : trendSegments(STATE.trendlines, ps.dates || []);
    mount('chart-price', (w) => lineChart({
      width: w,
      height: 420,
      // Four lines converge here; the value at the end of each is what a reader
      // was previously hovering or cross-referencing a tile to find.
      valueTags: true,
      labels: ps.dates || [],
      // Volume rides under the price. The series is already sliced to the
      // selected timeframe upstream, so it lines up bar-for-bar with the dates.
      volume: showVol ? (ps.volume || null) : null,
      // In candle mode the close series is kept but not stroked: the hover
      // crosshair and tooltip read from the series list, so dropping it would
      // silently disable them.
      series: [
        // In candle mode this series is not stroked — it exists so the crosshair
        // and tooltip have something to read. It took s1, which the 20-day average
        // also takes in candle mode, so the tooltip showed two rows with one
        // swatch. C.ink is outside the categorical slots entirely, which is right
        // for it: in candle mode it is not another line, it is the price the
        // candles already draw.
        { name: 'Close',
          values: ps.close,
          color: candleMode ? C.ink : C.s1,
          hidden: candleMode,
          fill: !candleMode },
        /* Per-average switches, matching the Charting tab's Indicators menu —
         * the flags are shared, so the two tabs cannot disagree about which
         * averages are on. Labels keep this tab's bar-unit naming. */
        ...(ps.intraday ? [] : [
          ['sma20', ps.weekly ? '20-week SMA' : '20-day SMA', ps.sma20, maColors.fast],
          ['sma50', ps.weekly ? '50-week SMA' : '50-day SMA', ps.sma50, maColors.mid],
          ['sma200', '200-day SMA', ps.sma200, maColors.slow],
        ].filter(([id]) => seriesShown(id)).map(([id, name, values, color]) => ({
          name, values: values || [], color, width: styleOf(id).width, marker: false,
        }))),
        // Selected overlays, drawn on the price axis. Dashed so they read as
        // something you switched on rather than part of the base chart, and
        // excluded on intraday for the same reason the daily averages are: they
        // are computed from daily bars and would describe a different timeframe
        // from the one on screen.
        ...(ps.intraday ? [] : [
          ['ema9', 'EMA 9', ps.ema9, emaColors.fast],
          ['ema21', 'EMA 21', ps.ema21, emaColors.mid],
          ['ema50', 'EMA 50', ps.ema50, emaColors.slow],
        ].filter(([id]) => seriesShown(id)).map(([id, name, values, color]) => ({
          name, values: values || [], color, width: styleOf(id).width, marker: false,
        }))),
        ...(ps.intraday ? [] : indicatorOverlaySeries((ps.dates || []).length,
          overlayPalette)),
      ],
      candles: candleMode
        ? { open: ps.open, high: ps.high, low: ps.low, close: ps.close }
        : null,
      refLines: overlayRefs,
      segments: trendSegs,
      // Both computed from the visible window, so they describe what is on screen.
      volumeProfile: showVbp ? volumeByPrice(ps) : null,
      // Supply above, demand below, in the sign colours already used everywhere
      // else for "sellers waiting" and "buyers waiting". Intraday is excluded for
      // the same reason the averages are: the zones are derived from daily bases.
      bands: [
        ...levelBands,
        ...(showZones && !ps.intraday ? zoneBands(d.patterns) : []),
      ],
      events: (showInsiders && !ps.intraday)
        ? insiderEvents(ps, ((d.company || {}).ownership || {}).recent_transactions) : null,
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
    const offScale = overlayRefs.filter(
      (r) => isFinite(r.value) && (r.value < dLo - slack || r.value > dHi + slack));
    const note = document.getElementById('chart-price-note');
    if (note) {
      const one = offScale.length === 1;
      note.innerHTML = offScale.length
        ? `<p class="caveat" style="margin:var(--space-2) 0 0">${offScale.length} level${one ? '' : 's'} ${
          one ? 'sits' : 'sit'} too far outside the price range on screen to draw, so ${
          one ? "it isn't" : "they aren't"} shown here: ${one ? 'it is' : 'they are'} still
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
    const rsiZoom = momentumBars(ps.shown_bars, rsiSource.length);
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

    // The indicator panes are part of this panel now, so this render owns their
    // hosts and has to mount their charts too. Without it the panes appeared with
    // their headings and readings but an empty box where the chart belongs — the
    // markup was rebuilt and nothing put anything in it.
    drawIndicatorCharts();

    mount('chart-rsi', (w) => lineChart({
      valueTags: true,
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
    const zoom = momentumBars(ps.shown_bars, full.macd.length);
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
      { name: 'Histogram (MACD − signal)', color: C.s3, boxed: true },
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
      resistance. Places a bounce has a reason to stall.`;
  }
  return `<strong>bullish retracement</strong>, measured swing low → swing high:
    up from ${lo}${loDate} to ${hi}${hiDate}. Price has since given back
    ${pct}% of that rise, so these levels sit <strong>below</strong> price and act as
    support. Places a pullback has a reason to hold.`;
}

function renderEntryPlan(p) {
  if (!p) return '';

  if (!p.actionable) {
    return `<div class="panel gap">
      <h2>${hg('Strike & entry recommendation')}</h2>
      <p class="sub">${esc(p.headline || '')}</p>
      ${(p.reasoning || []).map((r) => `<div class="callout">${gloss(r)}</div>`).join('')}
      ${(p.waiting_for || []).filter(Boolean).length ? `<h3>${hg('What would create a trade')}</h3>
        <table class="data"><thead><tr><th>Trigger</th><th>Result</th></tr></thead><tbody>
        ${(p.waiting_for || []).filter(Boolean).map((w) => `<tr>
          <td class="name">${esc(w.condition)}</td><td class="name dim">${esc(w.then)}</td>
        </tr>`).join('')}</tbody></table>` : ''}
      ${(p.iv_context || {}).available ? `<h3>${hg('Volatility context')}${askPulse('iv')}</h3>
        <p class="sub">${gloss(p.iv_context.guidance || '')}</p>` : ''}
    </div>`;
  }

  const r = p.recommended || {};
  const t = p.target || {};
  const o = p.order_guidance || {};
  const risk = p.risk || {};
  const iv = p.iv_context || {};
  const hv = (STATE.swing && STATE.swing.technicals
    && STATE.swing.technicals.volatility) || {};

  return `<div class="panel gap">
    <h2>${hg('Strike & entry recommendation')}</h2>
    <p class="sub">Derived from the ${esc(p.stance)} read at ${esc(p.conviction)} conviction. Candidates are repriced with
      Black-Scholes at the projected target, so the ranking reflects payoff, not just a convenient delta.</p>

    <div class="callout info" style="font-size:var(--t-base);border-left-color:var(--good)">
      <strong>${esc(p.headline)}</strong>
    </div>

    <div class="grid c4" style="margin:var(--space-4) 0">
      ${tile('Contract', `${strikeLabel(r.strike)} ${p.direction === 'long' ? 'call' : 'put'}`,
    `Expires ${esc(r.expiry || '')} · ${r.dte || 0} days left · ${
      r.moneyness === 'ITM' ? 'already in the money' : 'not yet in the money'}`)}
      ${tile('Limit price', usd(o.limit_price), `Per share, never pay above ${
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
        ${(p.entry_options || []).map((e) => `<div style="padding:var(--space-2) 0;border-bottom:1px solid var(--grid)">
          <div style="display:flex;gap:var(--space-3);align-items:baseline;flex-wrap:wrap">
            <strong style="font-size:var(--t-body)">${esc(e.style)}</strong>
            ${e.zone ? `<span class="chip neutral"><span class="dot"></span>${usd(e.zone[0])} – ${usd(e.zone[1])}</span>` : ''}
          </div>
          <div style="color:var(--ink-2);font-size:var(--t-small);margin-top:var(--space-1)">${gloss(e.detail)}</div>
          <div style="color:var(--ink-muted);font-size:var(--t-small);margin-top:var(--space-0)">Confirmation: ${gloss(e.confirmation)}</div>
        </div>`).join('')}

        <h3>${hg('Entry zone levels')}</h3>
        <table class="data">
          <thead><tr><th>Level</th><th>Price ($)</th></tr></thead>
          <tbody>${((p.entry_zone || {}).levels || []).map((z) => `<tr>
            <td class="name">${esc(cap(z.label))}</td><td>${usd(z.price)}</td>
          </tr>`).join('') || '<tr><td colspan="2" class="muted">No structural levels below spot.</td></tr>'}</tbody>
        </table>
      </div>

      <div>
        <h3>${hg('Target & risk')}</h3>
        ${kv([
    ['Price target', `${usd(t.target_price)}. A ${fmtPct(t.move_required_pct, 1)} move from here`],
    ['Where that target comes from', esc(t.target_source || '')],
    ['Expected time to get there', `${t.estimated_trading_days || '?'} trading days (about ${
      t.estimated_calendar_days || '?'} calendar days)`],
    ['Stop on the stock', `${usd(risk.underlying_stop)}. Exit if the stock closes past this`],
    ['How that stop was set', esc(risk.stop_basis || '')],
    ['Average daily range (14 days)', `${usd(t.atr14)} a day`],
  ])}
        <div class="caveat">${gloss(risk.invalidation || '')} ${gloss(risk.position_sizing || '')}</div>

      </div>
    </div>

    <h3>${hg('Candidate strikes, ranked')}</h3>
    <p class="sub">Every column after the greeks is a repriced scenario at ${usd(t.target_price)} in about
      ${t.estimated_calendar_days || '?'} days. “Flat” is what you lose if the move simply doesn't happen. The most
      common outcome, and the reason deep-OTM contracts score badly here.</p>
    <table class="data">
      <thead><tr>
        <th>#</th><th>Strike ($)</th><th>Expiry</th><th>Days left</th><th>Mid ($)</th><th>Spread</th><th>Delta</th><th>Theta ($/day)</th>
        <th>Breakeven</th><th>At target</th><th>IV −20%</th><th>If flat</th><th>Half against</th><th>OI</th>
      </tr></thead>
      <tbody>${(p.candidates || []).map((c) => `<tr${c.rank === 1 ? ' style="background:var(--surface-2)"' : ''}>
        <td>${c.rank}${c.rank === 1 ? ' ★' : ''}</td>
        <td class="name">${fmt(c.strike, 1)} <span class="muted">${esc(c.moneyness)}</span></td>
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
  </div>
  <!-- Volatility context, moved out of the entry plan's right column.
       It describes the underlying's vol, not this particular trade, and it was
       the reason that column ran 1131px against 561px on the left. A 570px void
       inside the card, which the panel border made look like a failed section
       rather than empty space. Two more rows landed here with the HV ladder,
       which is what pushed it over. -->
  ${iv.available ? `<div class="panel gap">
      <h3>${hg('Volatility context')}${askPulse('iv')}</h3>
      ${kv([
  ['Implied volatility, at the money', fmt(iv.atm_iv_pct, 1) + '% a year. What options are pricing in'],
  ['Realized volatility, last 20 days', fmt(iv.realised_vol_20d_pct, 1) + '% a year. What the stock actually did'],
  ['Implied ÷ realized', fmt(iv.iv_to_realised_ratio, 2) + 'x. Above 1.0 means options look expensive'],
  ['Read', esc(iv.verdict || '')],
  // The ladder qualifies the ratio above: 1.3x against vol that has doubled in
  // a fortnight is the market catching up, not an expensive option.
  hv.hv_10d !== null && hv.hv_10d !== undefined
    ? ['Realized vol by window', `${fmt(hv.hv_10d, 1)}% over 10 days · ${
        fmt(hv.hv_20d, 1)}% over 20 · ${fmt(hv.hv_30d, 1)}% over 30 · ${
        fmt(hv.hv_60d, 1)}% over 60`] : null,
  hv.hv_trend
    ? ['Recent movement', `${esc(cap(hv.hv_trend))}${hv.hv_fast_vs_slow_pct !== null
        && hv.hv_fast_vs_slow_pct !== undefined
        ? `· 10-day sits ${fmt(Math.abs(hv.hv_fast_vs_slow_pct), 0)}% ${
            hv.hv_fast_vs_slow_pct >= 0 ? 'above' : 'below'} the 60-day` : ''}`] : null,
  iv.iv_rank_proxy !== null && iv.iv_rank_proxy !== undefined
    ? ['IV rank (proxy)', fmt(iv.iv_rank_proxy, 0) + ' out of 100. Where today sits in the past year'] : null,
  iv.realised_vol_rank_pct !== null && iv.realised_vol_rank_pct !== undefined
    ? ['Realized vol rank', fmt(iv.realised_vol_rank_pct, 0) + ' out of 100 across the last 52 weeks'] : null,
  iv.realised_vol_percentile_pct !== null && iv.realised_vol_percentile_pct !== undefined
    ? ['Realized vol percentile', fmt(iv.realised_vol_percentile_pct, 0) + '% of the last 52 weeks were calmer'] : null,
  iv.realised_vol_52w_low !== null && iv.realised_vol_52w_low !== undefined
    ? ['Realized vol range, 52 weeks', `${fmt(iv.realised_vol_52w_low, 1)}% to ${fmt(iv.realised_vol_52w_high, 1)}%`] : null,
])}
      <div class="callout ${iv.verdict === 'rich' ? '' : 'info'}">${gloss(iv.guidance || '')}</div>
      ${iv.rank_guidance ? `<div class="callout info">${gloss(iv.rank_guidance)}</div>` : ''}
      ${hv.hv_trend_note ? `<div class="caveat">${gloss(hv.hv_trend_note)}</div>` : ''}
      ${iv.term_structure ? `<div class="caveat">${gloss(iv.term_structure)}</div>` : ''}
      ${iv.iv_rank_proxy !== null && iv.iv_rank_proxy !== undefined ? `<p class="caveat">${gloss(iv.method || '')}</p>` : ''}
  </div>` : ''}`;
}

/* ------------------------------------------------------------ company panel */

function renderCompany(co) {
  if (!co || co.error) {
    return co && co.error ? `<div class="panel gap"><h2>${hg('Company data')}</h2>
      <div class="callout bad">${esc(co.error)}</div></div>` : '';
  }
  const si = co.short_interest || {};
  const fn = co.financials || {};
  const eh = co.earnings_history || {};
  const ow = co.ownership || {};
  // Filings hang off the top-level payload, not the company block, so they are read
  // from STATE rather than threaded through renderCompany's single argument.
  const fl = (STATE.swing || {}).filings || {};
  const ap = fn.annual_periods || [];
  const an = fn.annual || {};

  const finRow = (label, values, money) => `<tr>
    <td class="name">${esc(label)}</td>
    ${(ap || []).map((_, i) => `<td>${values && values[i] !== null && values[i] !== undefined
    ? (money ? '$' + fmtCompact(values[i]) : fmt(values[i], 2)) : '—'}</td>`).join('')}
  </tr>`;

  return `
  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Short interest')}</h2>
      ${si.available ? `
        <p class="sub">Squeeze potential: <strong>${esc(si.squeeze_potential)}</strong>${si.settlement_date ? ` · settled ${esc(si.settlement_date)}` : ''}</p>
        <div class="grid c3" style="margin-bottom:var(--space-3)">
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
    : '<div class="callout">No earnings history. Typical for ETFs and index products.</div>'}
    </div>
  </div>

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Financials')}</h2>
      ${fn.available ? `
        <p class="sub">Annual statements, most recent first.</p>
        <div class="grid c3" style="margin-bottom:var(--space-3)">
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
      <h2>${hg('Recent SEC filings')}</h2>
      ${fl.available ? `
        <p class="sub">What the company itself has filed, newest first. An 8-K's item code is
          the filer's own classification of the event, not an interpretation of it.</p>
        <table class="data">
          <thead><tr><th>Filed</th><th>Form</th><th>What it is</th><th></th></tr></thead>
          <tbody>${(fl.filings || []).map((f) => `<tr>
            <td class="name">${esc(f.filed || '')}</td>
            <td class="name"><strong>${esc(f.form)}</strong></td>
            <td class="name dim">${esc(f.what || '')}</td>
            <td><a href="${esc(f.url)}" target="_blank" rel="noopener noreferrer nofollow"
              style="color:var(--s1)">Open</a></td>
          </tr>`).join('')}</tbody>
        </table>
        ${fl.newest_age_days !== null && fl.newest_age_days !== undefined
    ? `<p class="caveat">Newest filing is ${fmt(fl.newest_age_days, 0)} days old.</p>` : ''}
        <p class="caveat">${gloss(fl.method || '')}</p>`
    : `<div class="callout">${esc(fl.reason || 'No filings available for this symbol.')}</div>`}
    </div>

    <div class="panel">
      <h2>${hg('Insider & institutional activity')}</h2>
      ${ow.available ? `
        <p class="sub">Insiders are net <strong>${esc(ow.insider_signal)}</strong> over the last six months.</p>
        <div class="grid c3" style="margin-bottom:var(--space-3)">
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
            <td class="name muted">${esc(tx.position)}</td>
            <td class="name">${esc(tx.date)}</td>
            <td class="name ${tx.action === 'purchase' ? 'up' : tx.action === 'sale' ? 'down' : ''}">${esc(cap(tx.action))}</td>
            <td>${fmtCompact(tx.shares)}</td>
            <td>${tx.value ? '$' + fmtCompact(tx.value) : '—'}</td>
          </tr>`).join('') || '<tr><td colspan="6" class="muted">No recent filings.</td></tr>'}</tbody>
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
      <span class="subnote sm">${esc(idea.expiry)} · ${idea.dte}d</span>
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
    <div style="margin-top:var(--space-2)">${kv([
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
    rp.underlying_stop ? ['Stop on the stock', `${usd(rp.underlying_stop)} · ${esc(rp.stop_basis || '')}`] : null,
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
    <div style="margin-top:var(--space-2)">${kv([
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

/* Market Catalyst Mode: the release currently moving the tape.
 *
 * The reference design for this had a "consensus vs actual" block. There is no
 * consensus here and the panel says why rather than leaving a gap: surveyed
 * estimates are licensed, and a stale one sitting beside a real actual
 * manufactures a surprise that never happened. What IS shown is the release in
 * the agency's own words and the cross-asset board, which is measured.
 *
 * The reaction chips are session changes, not reactions attributed to the
 * print. That distinction is on the panel, not buried in a method note, because
 * it is the difference between an observation and a causal claim. */
const CAT_IMPACT_CLASS = { high: 'down', medium: 'warn', low: 'flat' };

function catalystModeStep(label, done) {
  return `<li class="${done ? 'done' : ''}"><span class="step-dot" aria-hidden="true"></span>${esc(label)}</li>`;
}

function renderCatalystMode(c) {
  if (!c) return '';
  if (!c.available) {
    // The explainer and the archive link belong here too. A quiet week is exactly
    // when a reader wonders what this section is for, and the stored catalysts are
    // still worth reaching.
    return `<div class="panel span-all">
      ${explainer('catalyst-mode', 'Market catalyst mode',
    'When a major release such as CPI or an FOMC decision is driving the market, this '
    + 'section shows what it was and how the tape moved alongside it.', '#catmode-idle')}
      <h2>${hg('Market catalyst')}</h2>
      <p class="sub" id="catmode-idle">${esc(c.reason || 'No catalyst release right now.')}</p>
      <p class="caveat"><button type="button" class="cat-archive-link"
        data-goto-catalysts>Catalyst archive. Every stored event, searchable</button></p>
    </div>`;
  }
  const r = c.release || {};
  const rx = c.reaction || {};
  const read = c.read || {};
  const chips = (rx.assets || []).map((a) => `<span class="rx-chip" title="${esc(a.name)} · ${esc(a.reads)}">
    <strong>${esc(a.symbol)}</strong>
    <span class="${signClass(a.change_pct)}">${a.change_pct > 0 ? '+' : ''}${fmt(a.change_pct, 2)}%</span>
  </span>`).join('');

  return `<div class="panel span-all catmode">
    ${explainer('catalyst-mode', 'Market catalyst mode',
    'When a major release such as CPI or an FOMC decision is driving the market, this '
    + 'section shows what it was and how the tape moved alongside it.', '#catmode-method')}
    <div class="catmode-head">
      <div>
        <span class="catmode-kicker">Market Catalyst Mode</span>
        ${r.source_detail ? `<span class="catmode-cat">${esc(r.source_detail)}</span>` : ''}
      </div>
      ${r.impact ? `<span class="cal-impact ${r.impact}">${esc(r.impact)} impact</span>` : ''}
    </div>
    <h2 class="catmode-title">${esc(r.title || '')}</h2>
    <p class="catmode-when">${esc((r.age || {}).at_et || '')}${
  r.source ? ` · ${esc(r.source)}` : ''}</p>

    <div class="grid c3" style="margin-top:var(--space-4)">
      <div class="catmode-box">
        <div class="idx-lbl">Released</div>
        <div class="catmode-ago">${esc((r.age || {}).label || '')}</div>
        ${r.summary ? `<p class="catmode-sum">${esc(r.summary.slice(0, 260))}</p>` : ''}
      </div>
      <div class="catmode-box">
        <div class="idx-lbl">Consensus vs actual</div>
        <div class="catmode-noconsensus">Not shown</div>
        <p class="catmode-sum">${esc((c.consensus || {}).reason || '')}</p>
      </div>
      <div class="catmode-box">
        <div class="idx-lbl">Catalyst timeline</div>
        <ul class="catmode-steps">
          ${catalystModeStep('Released', true)}
          ${catalystModeStep('Market reaction measured', !!(rx.assets || []).length)}
          ${catalystModeStep('Written read', !!read.available)}
        </ul>
      </div>
    </div>

    ${chips ? `<div class="catmode-reaction">
      <div class="idx-lbl">Market reaction <span style="text-transform:none;letter-spacing:0">· ${
  esc(rx.basis || '')}</span></div>
      <div class="rx-chips">${chips}</div>
    </div>` : ''}

    ${read.available ? `
      ${read.headline ? `<p class="earn-brief-lede" style="margin-top:var(--space-5)">${esc(read.headline)}</p>` : ''}
      <div class="weekly-body">${briefProse(read.paragraphs)}</div>
      <p class="caveat">${esc(read.disclaimer || '')}</p>`
    : '<p class="caveat" style="margin-top:var(--space-4)">No written read for this release.</p>'}
    <p class="caveat" id="catmode-method">${gloss(c.method || '')}</p>
    <p class="caveat"><button type="button" class="cat-archive-link"
      data-goto-catalysts>Catalyst archive. Every stored event, searchable</button></p>
  </div>`;
}

/* Mount one deferred panel without rebuilding the tab around it.
 *
 * The Read tab is assembled from a synchronous payload plus five panels that
 * arrive on their own schedule. Each of those loaders used to finish by calling
 * renderBrief(), which sets innerHTML on the whole view — so a single page load
 * tore down and rebuilt roughly 1,500 nodes ten times over five seconds.
 *
 * That is what "laggy" looked like from the outside: the page jumped as each
 * panel landed, every open <details> snapped shut, the reveal animation replayed
 * on panels the reader was already looking at, and anything typed into the
 * headline search was wiped mid-keystroke.
 *
 * Each panel now owns a host element and replaces only its own contents. The
 * renderBrief fallback is kept for the case where the tab has not been built
 * yet — then there is no host to write into and a full render is correct. */
function mountPanel(hostId, html) {
  const host = document.getElementById(hostId);
  if (!host) {
    if (STATE.brief) renderBrief(STATE.brief);
    return;
  }
  if (host.innerHTML === html) return;   // nothing changed; do not touch the DOM
  host.innerHTML = html;
  revealPanels(host);
}

async function loadCatalystMode() {
  if (STATE.catalystMode) return;
  try {
    STATE.catalystMode = await getJSON('/api/catalyst-mode');
    mountPanel('catmode-host', renderCatalystMode(STATE.catalystMode));
  } catch (err) {
    console.warn('Catalyst mode unavailable:', err.message);
  }
}

/* The catalyst library.
 *
 * Read-only by default. The refresh that scans for new catalysts is a POST
 * behind an explicit button, because it costs a model call and writes to the
 * store, and neither should happen because somebody opened a tab.
 *
 * Every company row carries TWO separate judgements — how direct the link is,
 * and how strong the read-through is — shown side by side rather than merged.
 * A mega-cap can be directly involved in something that is a rounding error on
 * its revenue, and a single "relevance" score would hide exactly that. */
const CAT_HORIZON_CLASS = {
  'short-term': 'flat', 'medium-term': 'warn', 'long-term': 'up',
};
const CAT_DIRECT_CLASS = { direct: 'up', indirect: 'flat', peripheral: 'flat' };
const CAT_STRENGTH_CLASS = { strong: 'up', moderate: 'flat', weak: 'down' };

const CATALYST_FILTERS = { q: '', status: 'relevant', category: '', sector: '', theme: '' };

function catalystCard(c) {
  const companies = (c.companies || []).map((co) => `<tr>
    <td class="name"><button type="button" class="tkr" data-analyse="${esc(co.ticker)}"
      >${esc(co.ticker)}</button></td>
    <td class="name dim">${esc(co.name)}</td>
    <td><span class="cat-tag ${CAT_DIRECT_CLASS[co.directness] || 'flat'}">${esc(co.directness)}</span></td>
    <td><span class="cat-tag ${CAT_STRENGTH_CLASS[co.strength] || 'flat'}">${esc(co.strength)}</span></td>
    <td class="name" style="color:var(--ink-2);font-size:var(--t-micro)">${esc(co.why || '')}</td>
  </tr>`).join('');

  return `<details class="cat-card">
    <summary>
      <div class="cat-meta">
        <span class="cat-horizon ${CAT_HORIZON_CLASS[c.horizon] || 'flat'}">${esc(c.horizon)}</span>
        <span class="cat-cat">${esc((c.category || '').replace('-', ' '))}</span>
        <span class="cat-date">${esc(c.event_date || '')}</span>
        ${c.relevant ? '' : '<span class="cat-archived">archived</span>'}
      </div>
      <h3 class="cat-title">${esc(c.title)}</h3>
      <p class="cat-summary">${esc(c.summary || '')}</p>
      <div class="cat-themes">${(c.themes || []).map((t) => esc(t)).join(' · ')}</div>
      <i class="cal-caret" aria-hidden="true"></i>
    </summary>
    <div class="cat-body">
      ${companies ? `<table class="data">
        <thead><tr><th>Ticker</th><th>Company</th><th>Link</th><th>Read-through</th><th>Why</th></tr></thead>
        <tbody>${companies}</tbody>
      </table>
      <p class="caveat">Which companies are connected, how direct the link is and how strong
        the read-through is are <strong>judgements</strong>, not data. Tickers are verified
        against EDGAR's company directory; the connection itself is an inference.</p>`
    : '<p class="sub">No company links were stored for this catalyst.</p>'}
      ${c.source_url ? `<p class="caveat"><a href="${esc(c.source_url)}" target="_blank"
        rel="noopener noreferrer nofollow" style="color:var(--s1)">Source${
  c.source_name ? ' · ' + esc(c.source_name) : ''}</a></p>` : ''}
    </div>
  </details>`;
}

function renderCatalysts(d) {
  const f = CATALYST_FILTERS;
  const facets = (d && d.facets) || { categories: [], sectors: [], themes: [] };
  const opts = (list, sel, anyLabel) => [`<option value="">${anyLabel}</option>`]
    .concat(list.map((v) => `<option value="${esc(v)}"${v === sel ? ' selected' : ''}>${
  esc(v.replace('-', ' '))}</option>`)).join('');

  const head = `<div class="panel span-all">
    <div class="weekly-kicker">Optic Research</div>
    <h2 class="weekly-title">Catalyst Library</h2>
    <p class="weekly-sub">Important market events do not stop mattering the day they are
      published. Every catalyst analysed here is stored with the public companies connected
      to it, how direct that connection is, and how strong the read-through is. Research
      context only, never a recommendation.</p>
    <div class="cat-controls">
      <div class="cat-search">
        <input type="search" id="cat-q" placeholder="Search catalysts, themes or tickers"
          value="${esc(f.q)}" aria-label="Search catalysts">
        <button type="button" class="btn" data-cat-search>Search</button>
      </div>
      <div class="cat-filters">
        <label>Status <select data-cat-filter="status">
          <option value="relevant"${f.status === 'relevant' ? ' selected' : ''}>Currently relevant</option>
          <option value="archived"${f.status === 'archived' ? ' selected' : ''}>Archived</option>
          <option value="all"${f.status === 'all' ? ' selected' : ''}>All</option>
        </select></label>
        <label>Category <select data-cat-filter="category">${
  opts(facets.categories, f.category, 'All categories')}</select></label>
        <label>Sector <select data-cat-filter="sector">${
  opts(facets.sectors, f.sector, 'All sectors')}</select></label>
        <label>Theme <select data-cat-filter="theme">${
  opts(facets.themes, f.theme, 'All themes')}</select></label>
      </div>
      <button type="button" class="bulk-btn" data-cat-refresh>Scan for new catalysts</button>
    </div>
  </div>`;

  if (!d) return head + `<div class="panel span-all">${loadingHTML('the catalyst library')
    .replace(/^<div class="panel">|<\/div>$/g, '')}</div>`;
  if (!d.available) {
    return head + `<div class="panel span-all"><div class="callout">${
  esc(d.reason || 'The catalyst library is unavailable.')}</div></div>`;
  }
  const list = d.catalysts || [];
  return head + `<div class="panel span-all">
    <p class="note" style="color:var(--ink-muted);margin:0 0 var(--space-3)">${
  fmt(d.matched, 0)} catalyst${d.matched === 1 ? '' : 's'}${
  d.stored_total !== d.matched ? ` of ${fmt(d.stored_total, 0)} stored` : ''}</p>
    ${STATE.catalystScan ? `<div class="callout">${esc(STATE.catalystScan)}</div>` : ''}
    ${list.length ? `<div class="cat-list">${list.map(catalystCard).join('')}</div>`
    : `<div class="callout">Nothing matches these filters. The library only contains events
       a scan has identified as durable. If it is empty, run a scan.</div>`}
    <p class="caveat">${gloss(d.method || '')}</p>
  </div>`;
}

/* Lives inside the Read tab now. It writes into its own host element rather
 * than the whole view, so a brief refresh cannot wipe an active search — the
 * library keeps its own filter state and reloads independently. */
function catalystHost() {
  return document.getElementById('catalyst-host');
}

async function loadCatalysts(force) {
  const host = catalystHost();
  if (!host) return;
  if (STATE.catalysts && !force) { host.innerHTML = renderCatalysts(STATE.catalysts); return; }
  host.innerHTML = renderCatalysts(null);
  const f = CATALYST_FILTERS;
  const qs = new URLSearchParams({ q: f.q, status: f.status, category: f.category,
    sector: f.sector, theme: f.theme }).toString();
  try {
    STATE.catalysts = await getJSON(`/api/catalysts?${qs}`);
  } catch (err) {
    STATE.catalysts = { available: false, reason: err.message };
  }
  const el = catalystHost();
  if (el) { el.innerHTML = renderCatalysts(STATE.catalysts); revealPanels(el); }
}

async function refreshCatalysts(btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Scanning…'; }
  try {
    const r = await postJSON('/api/catalysts/refresh', {});
    STATE.catalystScan = r.available
      ? `Scanned ${r.scanned} stories · ${r.identified} catalyst${r.identified === 1 ? '' : 's'} identified${
        r.tickers_dropped ? ` · ${r.tickers_dropped} unresolvable ticker${r.tickers_dropped === 1 ? '' : 's'} dropped` : ''}`
      : (r.reason || 'The scan could not run.');
  } catch (err) {
    STATE.catalystScan = err.message;
  }
  STATE.catalysts = null;
  await loadCatalysts(true);
}

/* The weekly market update.
 *
 * A longer read than the morning note and a different job: the morning note is
 * two minutes before the open about today, this frames a week. Rendered as an
 * article — one column, capped measure, real headings — because it is meant to
 * be read rather than scanned, and prose set the full width of a wide panel is
 * genuinely harder to read.
 *
 * Collapsed by default on a weekday and open at the start of the week, since
 * that is when it is new. */
function renderWeekly(w) {
  if (!w) return '';
  if (!w.available) {
    return `<div class="panel span-all"><h2>${hg('Weekly market update')}</h2>
      <p class="sub">${esc(w.reason || 'No weekly update available.')}</p></div>`;
  }
  const e = (w.facts || {}).earnings || {};
  const days = (e.days || []).map((d) => `<li><strong>${esc(d.day)}:</strong> ${
  d.symbols.map((sym) => `<button type="button" class="tkr" data-analyse="${esc(sym)}"
    >${esc(sym)}</button>`).join(' ')}</li>`).join('');

  return `<div class="panel span-all weekly">
    <div class="weekly-kicker">Weekly Market Analysis</div>
    <h2 class="weekly-title">${esc(w.headline || 'Weekly market update')}</h2>
    ${w.subhead ? `<p class="weekly-sub">${esc(w.subhead)}</p>` : ''}
    <div class="weekly-body">${briefProse(w.paragraphs)}</div>
    ${days ? `<div class="weekly-earnings">
      <h3 class="prose-h">Reporting this week, from the watchlist</h3>
      <ul>${days}</ul>
      <p class="caveat">${esc(e.note || '')}</p>
    </div>` : ''}
    <p class="caveat">${gloss(w.method || '')}</p>
    <p class="caveat">${esc(w.disclaimer || '')}</p>
  </div>`;
}

async function loadWeekly() {
  if (STATE.weekly) return;
  try {
    STATE.weekly = await getJSON('/api/weekly');
    mountPanel('weekly-host', renderWeekly(STATE.weekly));
  } catch (err) {
    console.warn('Weekly update unavailable:', err.message);
  }
}

/* Fear and greed.
 *
 * Optic's own reading rather than a copy of CNN's — three of their seven inputs
 * need exchange breadth and market-wide options data free sources do not carry,
 * and publishing a number under a familiar name with different inputs behind it
 * is the worst option available. The panel says so, and lists every input.
 *
 * The comparisons are recomputed from truncated price history, not read from a
 * stored log, so "vs a month ago" is real on the day this ships instead of
 * blank until a month has passed. */
const FG_CLASS = {
  'Extreme Fear': 'fg-xfear', Fear: 'fg-fear', Neutral: 'fg-neutral',
  Greed: 'fg-greed', 'Extreme Greed': 'fg-xgreed',
};

function fgDelta(h) {
  if (!h) return '';
  // Decide flatness on the ROUNDED value, not the raw one. A change of +0.3
  // rendered as "\u2191+0" — an arrow pointing up next to a zero — which reads as
  // a bug rather than as a small move.
  const shown = Math.round(h.change);
  if (shown === 0) return '<span class="fg-delta">unchanged</span>';
  return `<span class="fg-delta ${shown > 0 ? 'pos' : 'neg'}">${
  shown > 0 ? '\u2191+' : '\u2193'}${shown}</span>`;
}

/** Persist a chart toggle, tolerating private mode. */
function storeFlag(key, on) {
  try { localStorage.setItem(key, on ? 'on' : 'off'); } catch (e) { /* private mode */ }
}

/* A <details> menu stays open when you click elsewhere, which for a dropdown is
 * wrong — it should behave like every other menu on the page. */
document.addEventListener('click', (evt) => {
  document.querySelectorAll('details.lvl-menu[open]').forEach((d) => {
    if (!d.contains(evt.target)) d.removeAttribute('open');
  });
});
document.addEventListener('keydown', (evt) => {
  if (evt.key !== 'Escape') return;
  document.querySelectorAll('details.lvl-menu[open]').forEach((d) => d.removeAttribute('open'));
});

/* Sector confirmation.
 *
 * The weakest of the three claims this terminal makes about a setup, and shown
 * as such: a supportive group is a tailwind, never a reason. The panel states
 * that in its own words rather than leaving the reader to infer it from a green
 * badge.
 *
 * Two relative-strength numbers, not one. Beating the index while trailing every
 * peer means the sector carried the move — a reader shown only "+5% vs SPY"
 * would read that as stock selection, which is exactly backwards. */
const SC_VERDICT_CLASS = { supportive: 'up', against: 'down', mixed: 'flat' };

/* Volume by price, computed from the bars already on screen.
 *
 * Each session's volume is assigned to the bucket its CLOSE falls in. The
 * textbook version spreads a bar's volume across its whole high-low range, which
 * is more faithful but needs intraday data to be more than a guess — with daily
 * bars the spread is itself an assumption. Close-bucketing is the honest simple
 * choice and the shape it produces is the same shape: fat where price spent
 * time, thin where it passed through.
 *
 * Computed over the visible window, so it answers "where did volume trade in
 * what I am looking at" rather than over some fixed lookback the chart does not
 * show. */
const VBP_BUCKETS = 40;

/* Supply and demand zones as chart bands.
 *
 * Colour carries the side rather than a label doing it: supply is where sellers
 * are waiting, which is the same thing every other panel here paints in the
 * negative colour. Broken zones never arrive — the backend drops them — so a
 * band on the chart is always one that has not been traded through.
 */
function zoneBands(patterns) {
  const zones = (patterns && patterns.zones) || [];
  return zones.map((z) => ({
    top: z.top,
    bottom: z.bottom,
    color: z.side === 'supply' ? C.neg : C.s3,
    label: `${z.side === 'supply' ? 'Supply' : 'Demand'} ${fmt(z.bottom, 2)}–${fmt(z.top, 2)}`,
    opacity: 0.13,
  }));
}

/* How many annotation families are switched on. Shown on the closed dropdown so
 * the amount of clutter on the chart is visible without opening it — the state
 * that produced an unreadable plot was invisible until you went looking. Volume is
 * excluded: it is a separate strip, not an annotation over the price. */
function levelCount() {
  return [showMA, showEMA, showFib, showSR, showVbp, showInsiders, showZones]
    .filter(Boolean).length;
}

/* Fibonacci as filled bands between consecutive levels, not seven dashed lines.
 *
 * Seven dashes at seven prices asks the reader to hold "which pair am I between"
 * in their head. The band between two ratios is the thing that actually matters —
 * price is inside 0.5-0.618 or it is not — so that is what gets drawn, with the
 * line only marking each edge.
 *
 * Colour runs cool at the top of the range to warm at the bottom, so where price
 * sits in the retracement is readable without consulting a legend. The golden
 * pair keeps a stronger fill because it is the one most people act on.
 */

/* Fibonacci as plain labelled lines.
 *
 * This reverses an earlier decision, deliberately and on instruction. The
 * previous version drew them as filled bands with a colour ramp, from "don't use
 * only dashed lines, make it creative"; the newer instruction is the opposite —
 * thin lines, one label each, "simple and visually understandable", matching how
 * every charting package draws them. The bands version and its FIB_RAMP palette
 * are deleted rather than left commented out.
 *
 * The argument for the flat version is real, not just deference: a Fibonacci
 * ratio IS a single price, not a zone. A band implies the level has width, which
 * is a claim the arithmetic does not make. Support and resistance are genuinely
 * zones and stay as bands; these are ratios of a measured swing and are exact.
 *
 * Label format follows the reference: `0.618 (748.30)` — the ratio, so you know
 * which line it is, and the price, so you do not have to read it off the axis.
 */
function fibLines(levels, spot) {
  return (levels || [])
    .filter((l) => l.price !== null && l.price !== undefined)
    .sort((a, b) => b.price - a.price)
    .map((l) => {
      const ratio = String(l.label || '').replace(/[^0-9.]/g, '');
      return {
        value: l.price,
        color: l.is_golden ? C.refSR : C.refFib,
        // The golden pair gets the weight. Everything else is annotation.
        emphasis: !!l.is_golden,
        dim: !l.is_golden && l.role !== 'resistance',
        // Solid, not dashed. The instruction was "simple", and seven dashed
        // lines at three dash patterns is what made the old version busy.
        dash: false,
        label: `${ratio || l.label} (${fmt(l.price, 2)})`,
        detail: [
          ['Level', String(l.label || '')],
          ['Price', fmt(l.price, 2)],
          ['Role', String(l.role || '')],
          spot ? ['From here', fmtPct(((l.price - spot) / spot) * 100, 1)] : null,
        ].filter(Boolean),
      };
    });
}

/* Support and resistance as bands, which is what they already are.
 *
 * The levels are built by clustering pivots with an ATR-scaled tolerance, so each
 * one is a band and the table has always shown its midpoint. Drawing a single
 * dashed line was therefore drawing something narrower than the finding — a level
 * at 189.90 is really "somewhere around 189.90, give or take", and a hairline
 * implies a precision the method does not have.
 *
 * Band thickness is that tolerance. Fill strength is the level's own strength
 * score, so a shelf defended five times reads heavier than one touched twice.
 */
const SR_BAND_LIMIT = 4;

function srBands(levels, atrValue, spot) {
  const half = Math.max(0.15, (atrValue || 0) * 0.30);
  // The four strongest, and only those price could plausibly reach. Shading all
  // eight produced fourteen near-identical stripes across the plot — a striped
  // background rather than a reading, and strictly worse than the dashed lines it
  // replaced. A level twenty percent away is in the table; it does not need to be
  // painted across the chart.
  const reach = (atrValue || 0) * 8;
  const near = (levels || [])
    .filter((l) => !spot || !reach || Math.abs(l.price - spot) <= reach)
    .sort((a, b) => (b.strength || 0) - (a.strength || 0))
    .slice(0, SR_BAND_LIMIT);
  return near.map((l) => {
    const strength = Math.max(0, Math.min(100, l.strength || 0));
    return {
      top: l.price + half,
      bottom: l.price - half,
      color: l.role === 'support' ? C.pos : C.neg,
      opacity: 0.07 + (strength / 100) * 0.11,
      label: '',
      // No edge lines. The band IS the level, and outlining every one of them is
      // what turned shading back into stripes.
      edge: false,
    };
  });
}

function volumeByPrice(ps) {
  const closes = (ps.close || []).filter((v) => v !== null && isFinite(v));
  const vols = ps.volume || [];
  if (closes.length < 10 || !vols.length) return null;
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  if (!(hi > lo)) return null;

  const step = (hi - lo) / VBP_BUCKETS;
  const buckets = new Array(VBP_BUCKETS).fill(0);
  (ps.close || []).forEach((c, i) => {
    const v = vols[i];
    if (c === null || !isFinite(c) || v === null || !isFinite(v)) return;
    const idx = Math.min(VBP_BUCKETS - 1, Math.max(0, Math.floor((c - lo) / step)));
    buckets[idx] += v;
  });

  const peak = Math.max(...buckets);
  return buckets.map((volume, i) => ({
    price: lo + (i + 0.5) * step,
    volume,
    // The point of control: the single price level with the most volume behind it.
    poc: volume === peak && peak > 0,
  })).filter((b) => b.volume > 0);
}

/* Insider transactions mapped onto chart bar indices.
 *
 * The transaction dates are calendar dates; the chart's x-axis is bar positions.
 * A trade on a weekend or holiday has no bar, and a trade older than the visible
 * window has no position at all — both are dropped rather than clamped to the
 * edge, because a marker pinned to the first bar of the window implies the trade
 * happened then. */
function insiderEvents(ps, transactions) {
  const dates = ps.dates || [];
  if (!dates.length || !(transactions || []).length) return null;
  const keys = dates.map((d) => String(d).slice(0, 10));

  /* Snap a transaction to the bar whose period contains it, rather than
   * demanding an exact date match.
   *
   * Exact matching silently dropped almost everything on an aggregated
   * interval. A weekly chart has one bar per Friday, so a purchase made on a
   * Tuesday matched nothing and vanished: Intel's CEO buying $10.0M on
   * 2026-08-11 disappeared between the 08-07 and 08-14 bars, while a sale that
   * happened to land on a bar date survived. The chart therefore showed sells
   * and no buys, which reads as "insiders are only selling" — a false
   * conclusion produced by a lookup, not by the data.
   *
   * It also fixes daily charts, where a transaction dated on a weekend or a
   * market holiday had no bar of its own and was dropped for the same reason.
   *
   * The last bar at or before the date is the right target: that bar's period
   * is the one the trade happened in. Anything before the first bar is out of
   * range and stays dropped. */
  const barFor = (iso) => {
    if (!iso) return undefined;
    let lo = 0;
    let hi = keys.length - 1;
    if (iso < keys[0]) return undefined;
    if (iso >= keys[hi]) return hi;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (keys[mid] <= iso) lo = mid; else hi = mid - 1;
    }
    return lo;
  };

  const out = [];
  (transactions || []).forEach((t) => {
    const action = String(t.action || '').toLowerCase();
    // Only actual purchases and sales. "other" covers option exercises, grants
    // and gifts, which are compensation events rather than a view on the price.
    if (action !== 'purchase' && action !== 'sale') return;
    const i = barFor(String(t.date || '').slice(0, 10));
    if (i === undefined) return;
    const value = Number(t.value) || 0;
    out.push({
      index: i,
      kind: action === 'purchase' ? 'buy' : 'sell',
      value,
      label: value ? `${action === 'purchase' ? 'Buy' : 'Sell'} $${fmtCompact(value)}` : null,
      /* The hover text for the marker.
       *
       * Says "Insider" explicitly. On the chart a bare "Buy $9.0M" could be
       * anything — a trade idea, a block print — and only the legend, which is
       * collapsed by default, said otherwise.
       *
       * Carries the trade's own date rather than the bar's: on a weekly chart
       * the marker sits on the week containing the trade, and showing the bar
       * date would misreport when it happened by up to four days. */
      detail: [
        `Insider ${action === 'purchase' ? 'buy' : 'sell'}`,
        value ? `$${fmtCompact(value)}` : null,
        String(t.date || '').slice(0, 10) || null,
        t.insider || null,
        t.position || null,
      ].filter(Boolean).join(' · '),
    });
  });
  return out.length ? out : null;
}

/* Revenue against the multiple the market paid for it.
 *
 * Two series, two scales, one chart — bars for revenue on the left axis, a line
 * for the trailing P/E on the right. Sharing one axis would be meaningless:
 * revenue is in hundreds of billions and a P/E is in the twenties.
 *
 * The reason to put them together is the divergence. Revenue rising while the
 * multiple compresses means the business grew and the market paid less for it,
 * which is a different situation from both rising together, and neither series
 * alone shows it. */
function renderRevenueMultiple(rm) {
  if (!rm) return '';
  if (!rm.available) {
    return `<div class="panel span2"><h2>${hg('Revenue and the multiple')}</h2>
      <p class="sub">${esc(rm.reason || 'Unavailable.')}</p></div>`;
  }
  const years = rm.years || [];
  const maxRev = Math.max(...years.map((y) => y.revenue), 1);
  const pes = years.map((y) => y.pe).filter((v) => v !== null && v !== undefined);
  const peLo = pes.length ? Math.min(...pes) : 0;
  const peHi = pes.length ? Math.max(...pes) : 1;
  const peSpan = (peHi - peLo) || 1;

  const rows = years.map((y) => {
    const h = (y.revenue / maxRev) * 100;
    // The P/E dot's vertical position within the bar's own column, on its own
    // scale — padded off the edges so the extremes are still visible.
    const peTop = y.pe === null || y.pe === undefined
      ? null : 8 + (1 - (y.pe - peLo) / peSpan) * 76;
    return `<div class="rm-col">
      <div class="rm-plot">
        <div class="rm-bar" style="height:${h.toFixed(1)}%"></div>
        ${peTop !== null ? `<span class="rm-pe" style="top:${peTop.toFixed(1)}%"
          title="Trailing P/E for fiscal ${esc(y.label)}">${fmt(y.pe, 1)}</span>` : ''}
      </div>
      <div class="rm-rev">$${fmtCompact(y.revenue)}</div>
      <div class="rm-label">${esc(y.label)}</div>
    </div>`;
  }).join('');

  // Did revenue and the multiple move the same way? That is the read.
  const first = years[0] || {};
  const last = years[years.length - 1] || {};
  let divergence = '';
  if (first.pe !== null && last.pe !== null && first.pe !== undefined && last.pe !== undefined) {
    const revUp = last.revenue > first.revenue;
    const peUp = last.pe > first.pe;
    divergence = revUp && !peUp
      ? `Revenue grew at <strong>${fmt(rm.revenue_cagr_pct, 1)}% a year</strong> while the
         multiple compressed from ${fmt(first.pe, 1)} to ${fmt(last.pe, 1)}. The business got
         bigger and the market paid less for each dollar of it.`
      : revUp && peUp
        ? `Revenue and the multiple both rose. Growth of
           <strong>${fmt(rm.revenue_cagr_pct, 1)}% a year</strong> plus a rerating from
           ${fmt(first.pe, 1)} to ${fmt(last.pe, 1)}. Part of the share-price move is the
           business and part is sentiment.`
        : !revUp && peUp
          ? `Revenue fell while the multiple expanded from ${fmt(first.pe, 1)} to
             ${fmt(last.pe, 1)}. The market is paying more for less, which is a bet on
             something the revenue line does not yet show.`
          : `Revenue and the multiple both fell. The business shrank and the market
             marked it down with it.`;
  }

  return `<div class="panel span2">
    <h2>${hg('Revenue and the multiple')}${askPulse('revmultiple')}</h2>
    <p class="sub">What the business earned, against what the market paid for it. Bars are
      annual revenue; the number floating in each column is that fiscal year's trailing P/E.</p>
    <div class="rm-chart">${rows}</div>
    <div class="rm-legend">
      <span><i class="rm-key bar"></i>Annual revenue</span>
      <span><i class="rm-key pe"></i>Trailing P/E that year</span>
    </div>
    ${divergence ? `<p class="sc-note">${divergence}</p>` : ''}
    <p class="caveat">${gloss(rm.method || '')}</p>
  </div>`;
}

/* Today's priority board.
 *
 * Four columns of triage over data the terminal already has. It exists because
 * the Read tab, the calendar, the sector board and the scanners each answer
 * their own question well and none of them says which to look at first.
 *
 * Preview three per column with the full list behind a disclosure, rather than
 * four scrolling columns — the point is a glance, and a board you have to scroll
 * is a list again. */
const PRI_IMPACT_CLASS = { high: 'high', medium: 'medium', low: 'low' };

function priorityRow(r) {
  const label = r.ticker
    ? `<button type="button" class="tkr" data-analyse="${esc(r.ticker)}">${esc(r.ticker)}</button>`
    : '';
  return `<div class="pri-row">
    <div class="pri-row-top">
      <span class="cal-impact ${PRI_IMPACT_CLASS[r.impact] || 'low'}">${esc(r.impact || '')}</span>
      ${label}
      ${r.when ? `<span class="pri-when">${esc(r.when)}${r.time ? ' · ' + esc(r.time) : ''}</span>` : ''}
    </div>
    <div class="pri-title">${esc(r.title || '')}</div>
    ${r.why ? `<p class="pri-why">${esc(String(r.why).slice(0, 190))}</p>` : ''}
  </div>`;
}

/* Dismissible first-run explainers.
 *
 * A panel whose name does not explain itself gets one notice, once. Dismissal is
 * remembered per notice, so it cannot become the kind of banner a reader learns
 * to close reflexively — which is the failure mode that makes every subsequent
 * notice invisible too.
 *
 * "Learn more" scrolls to the panel's own method note rather than opening
 * anything: the long explanation already exists there, and duplicating it into a
 * modal would be a second copy to keep in sync. */
const NOTICE_KEY = 'optic.notices.dismissed';

function noticeDismissed(id) {
  try {
    return (JSON.parse(localStorage.getItem(NOTICE_KEY) || '[]') || []).includes(id);
  } catch (e) { return false; }
}

function dismissNotice(id) {
  try {
    const seen = JSON.parse(localStorage.getItem(NOTICE_KEY) || '[]') || [];
    if (!seen.includes(id)) seen.push(id);
    localStorage.setItem(NOTICE_KEY, JSON.stringify(seen));
  } catch (e) { /* private mode: it will simply show again */ }
  document.querySelectorAll(`[data-notice="${id}"]`).forEach((n) => n.remove());
}

function explainer(id, kicker, text, learnMoreSel) {
  if (noticeDismissed(id)) return '';
  return `<div class="explainer" data-notice="${esc(id)}">
    <span class="ex-icon" aria-hidden="true">i</span>
    <div class="ex-body">
      <div class="ex-kicker">${esc(kicker)}</div>
      <p class="ex-text">${esc(text)}</p>
      <div class="ex-actions">
        <button type="button" class="ex-got" data-notice-ok="${esc(id)}">Got it</button>
        ${learnMoreSel ? `<button type="button" class="ex-more"
          data-notice-more="${esc(learnMoreSel)}">Learn more</button>` : ''}
      </div>
    </div>
    <button type="button" class="ex-close" data-notice-ok="${esc(id)}"
      aria-label="Dismiss">×</button>
  </div>`;
}

function renderPriority(p) {
  if (!p) return '';
  if (!p.available) {
    return `<div class="panel span-all"><h2>${hg("Today's priority")}</h2>
      <p class="sub">${esc(p.reason || 'Nothing on the board right now.')}</p></div>`;
  }
  const cols = (p.columns || []).map((c) => `
    <section class="pri-col">
      <h3 class="pri-col-title">${esc(c.name)}<span class="pri-count">${fmt(c.total, 0)}</span></h3>
      <p class="pri-col-blurb">${esc(c.blurb)}</p>
      ${(c.preview || []).map(priorityRow).join('')
    || '<p class="sub">Nothing here today.</p>'}
      ${c.total > (c.preview || []).length ? `<details class="pri-more">
        <summary>Show all ${fmt(c.total, 0)}<i class="cal-caret" aria-hidden="true"></i></summary>
        <div>${(c.rows || []).slice((c.preview || []).length).map(priorityRow).join('')}</div>
      </details>` : ''}
    </section>`).join('');

  return `<div class="panel span-all">
    <h2>${hg("Today's priority")}${askPulse('priority')}</h2>
    <p class="sub">The calendar, the earnings scan, the sector board and the scanners in one
      view. Ordered by published impact and how soon it lands, not by a guess at what will
      matter most.</p>
    <div class="pri-board">${cols}</div>
    <p class="caveat">${gloss(p.method || '')}</p>
  </div>`;
}

async function loadPriority() {
  if (STATE.priority) return;
  try {
    STATE.priority = await getJSON('/api/priority');
  } catch (err) {
    STATE.priority = { available: false, reason: err.message };
  }
  mountPanel('priority-host', renderPriority(STATE.priority));
}

/* Detected patterns, each shown next to what actually followed it.
 *
 * The reason this panel exists in this shape: every other tool that draws a
 * double bottom also tells you it is bullish, and stops. That is a claim about
 * the future wearing the clothes of a measurement. So the conventional reading
 * and the measured base rate sit in the same row, and where they disagree the
 * panel does not resolve it — the reader can see both and the sample size.
 *
 * On this data most of them disagree, and the panel says so plainly rather than
 * burying it: fifteen candlestick patterns across 43 names and ten years come
 * out at hit rates between 46% and 51%.
 */
const PATTERN_STATE_LABEL = {
  confirmed: 'confirmed',
  unconfirmed: 'not confirmed',
  candle: 'single bar',
};

function baseRateCell(rates, name, state) {
  const key = `${name}|${state}`;
  const entry = ((rates && rates.patterns) || {})[key];
  const h = entry && entry.h21;
  if (!h || h.hit_rate === null || h.hit_rate === undefined) {
    return `<span class="pat-rate none">too few to measure${
  entry ? ` (${fmt(entry.sample, 0)})` : ''}</span>`;
  }
  // Coloured against 50%, not against zero: the question is whether the
  // conventional reading beat a coin toss, and a 52% hit rate is not a win.
  const edge = h.edge_mean_pct;
  const worked = h.hit_rate > 0.53;
  const failed = h.hit_rate < 0.47;
  return `<span class="pat-rate ${worked ? 'worked' : failed ? 'failed' : 'flat'}">
    ${fmt(h.hit_rate * 100, 0)}% of ${fmt(h.n, 0)}
    <span class="pat-edge">${edge > 0 ? '+' : ''}${fmt(edge, 2)}% vs its own drift</span>
  </span>`;
}

/* Trailing P/E over time, with revenue growth beside it.
 *
 * These two belong together because they answer opposite halves of one question:
 * revenue growth is what the business did, the multiple is what the market paid
 * for it. Revenue rising while the multiple compresses is a completely different
 * situation from both rising, and neither line says that alone.
 */
/* The indicator picker.
 *
 * Nine optional indicators, fetched only when selected. They are not in the
 * ticker payload because computing all nine on every page load is work nobody
 * asked for, and because these are a deliberate choice rather than part of the
 * base read.
 *
 * Each one carries what it measures and, where relevant, what it does not. That
 * is the part most platforms leave out: the catalogue tells you an indicator
 * exists and its default parameters, and says nothing about whether the number
 * means anything. Given what the pattern base rates in this terminal measured,
 * the honest framing is that these describe the tape rather than forecast it —
 * VWAP is here because desks are benchmarked against it, which is a fact about
 * behaviour, not evidence that crossing it predicts a move. */
const IND_STATE_KEY = 'optic.indicators.v2';
let indicatorIds = [];
try {
  const saved = localStorage.getItem(IND_STATE_KEY);
  if (saved) indicatorIds = JSON.parse(saved).filter((x) => typeof x === 'string');
} catch (e) { /* private mode or corrupt value */ }

/* The written half of a pane: what the indicator is, why it earns the space, and
 * what it will not tell you.
 *
 * Three separate registers, kept visually separate on purpose. `represents` is a
 * definition and is simply true. `why` is the argument for looking at it at all.
 * `caveat` is the limitation, and it is not hidden behind a tooltip — after
 * measuring the pattern base rates in this terminal and finding most of them a coin
 * toss, a panel that explains an indicator without stating its limits would be
 * selling something.
 *
 * The live reading of the current value sits above the chart instead, because it is
 * the one line that changes and the one most likely to be read.
 */
function indicatorExplainer(v) {
  // An overlay has no pane, so it must not say "pane". Small, but this panel spends
  // its effort on saying precisely what each thing is and where it is drawn.
  const label = v.pane === 'price' ? 'What this overlay means' : 'What this pane means';
  const rows = [
    v.represents ? { label: 'What it is', text: v.represents } : null,
    v.why ? { label: 'Why it matters', text: v.why } : null,
    v.caveat ? { label: 'What it will not tell you', text: v.caveat } : null,
  ].filter(Boolean);
  if (!rows.length) return `<p class="caveat">${esc(v.measures || '')}</p>`;
  return `<details class="ind-explain">
    <summary>${esc(label)}<i class="cal-caret" aria-hidden="true"></i></summary>
    <div class="ind-explain-body">
      <p class="ind-measures">${esc(v.measures || '')}</p>
      ${rows.map((r) => `<div class="ind-explain-row">
        <span class="ind-explain-label">${esc(r.label)}</span>
        <p>${esc(r.text)}</p>
      </div>`).join('')}
    </div>
  </details>`;
}

/* The overlays, explained.
 *
 * They draw on the price chart, so they have no pane of their own and previously
 * had nowhere to say what they were — five extra lines appeared on the plot with
 * only a legend label between them and the reader. Each row carries the same
 * swatch colour as its line, so the text is tied to the thing it describes rather
 * than to a name you have to match by eye.
 */
function renderOverlayReadings() {
  const got = (STATE.indicators && STATE.indicators.indicators) || {};
  const palette = STATE.overlayPalette || {};
  const rows = indicatorIds
    .filter((id) => IND_PRICE_PANE.includes(id) && id !== 'sec')
    .map((id) => {
      const v = got[id];
      if (!v || !v.available) return '';
      return `<div class="ov-row">
        <div class="ov-head">
          <span class="ov-dot" style="background:${esc(palette[id] || C.s7)}"></span>
          <span class="ov-name">${esc(v.name)}</span>
          <span class="ov-where">on the chart</span>
        </div>
        ${v.reading ? `<p class="ind-reading">${esc(v.reading)}</p>` : ''}
        ${indicatorExplainer(v)}
      </div>`;
    })
    .filter(Boolean);
  if (!rows.length) return '';
  return `<div class="ov-block">
    <div class="idx-lbl">Drawn on the price chart above</div>
    ${rows.join('')}
  </div>`;
}

function renderIndicatorPanes() {
  const overlays = renderOverlayReadings();
  // Nothing chosen: render nothing. The dropdown that chooses them is a few
  // pixels above, so a "nothing selected" notice would state the obvious and
  // reserve space for it.
  if (!indicatorIds.some((id) => !IND_PRICE_PANE.includes(id) || id === 'sec')) {
    return overlays;
  }
  const data = STATE.indicators;
  if (!data) return '<p class="loading"><span class="spinner"></span>Computing…</p>';
  if (!data.available) {
    return `<div class="callout">${esc(data.reason || 'Unavailable.')}</div>`;
  }
  const got = data.indicators || {};
  const parts = indicatorIds.map((id) => {
    // Overlays are drawn on the price chart, so a pane here as well would render
    // the same three lines twice under two different headings. The regression
    // channel is the exception: its lines overlay the chart, but its slope and
    // R-squared are numbers rather than a drawing and still need somewhere to go.
    if (IND_PRICE_PANE.includes(id) && id !== 'sec') return '';
    const v = got[id];
    if (!v) return '';
    if (!v.available) {
      return `<div class="ind-pane"><div class="idx-lbl">${esc(id)}</div>
        <p class="sub">${esc(v.reason || 'Unavailable.')}</p></div>`;
    }
    if (v.fit) {
      const f = v.fit;
      if (!f.available) {
        return `<div class="ind-pane"><div class="idx-lbl">${esc(v.name)}</div>
          <p class="sub">${esc(f.reason)}</p></div>`;
      }
      return `<div class="ind-pane">
        <div class="idx-lbl">${esc(v.name)}</div>
        ${v.reading ? `<p class="ind-reading">${esc(v.reading)}</p>` : ''}
        <div class="ind-fit">
          <span>Slope <strong class="${signClass(f.slope_pct_per_bar)}">${
  f.slope_pct_per_bar > 0 ? '+' : ''}${fmt(f.slope_pct_per_bar, 3)}%</strong> a session</span>
          <span>R² <strong>${fmt(f.r_squared, 2)}</strong></span>
          <span>Channel ${fmt(f.lower, 2)} – ${fmt(f.upper, 2)}</span>
          <span>over ${fmt(f.bars, 0)} bars</span>
        </div>
        ${indicatorExplainer(v)}
      </div>`;
    }
    return `<div class="ind-pane">
      <div class="idx-lbl">${esc(v.name)}${v.last !== null && v.last !== undefined
    ? `· ${fmt(v.last, 1)}` : ''}</div>
      ${v.reading ? `<p class="ind-reading">${esc(v.reading)}</p>` : ''}
      <div id="legend-ind-${esc(id)}"></div>
      <div id="chart-ind-${esc(id)}"></div>
      ${indicatorExplainer(v)}
    </div>`;
  });
  return overlays + parts.join('');
}

/* Shown before the first fetch returns, so the picker has labels to draw. Kept in
 * step with indicators.CATALOGUE server-side; if it drifts, the server copy wins
 * because the payload carries it. */
/* ================================================== chart style settings
 *
 * One store for how every overlay is drawn: colour, line width, and the
 * parameters that define it (length, offset, price source). Both price charts
 * read from it — the compact one on Swing and the full one on the Chart tab —
 * so a moving average you recolour in one place is that colour everywhere. Two
 * independent copies of this state was the alternative, and they would have
 * drifted the first time either chart gained a control the other did not.
 *
 * Colours are stored as *token names* ('s2', 'refSR') rather than hex, so a
 * saved preference still resolves correctly after a theme switch. Storing
 * '#d95926' would pin a dark-theme hue into the light theme, where it fails
 * contrast — the exact class of bug the palette tokens exist to prevent.
 *
 * `null` in a style field means "use the default", so a stored preference from
 * an older version cannot pin a value the app has since changed its mind about.
 */
const CHART_STYLE_KEY = 'optic.chart.style.v1';

/* The defaults, and the schema. Anything not in here cannot be styled, which is
 * deliberate: a settings dialog that offers a control the renderer ignores is
 * worse than no control. */
const OVERLAY_DEFS = [
  { id: 'sma20', label: 'SMA 20', group: 'Moving averages', color: 's2',
    width: 1.5, params: { length: 20, offset: 0, source: 'close' } },
  { id: 'sma50', label: 'SMA 50', group: 'Moving averages', color: 's3',
    width: 1.5, params: { length: 50, offset: 0, source: 'close' } },
  { id: 'sma200', label: 'SMA 200', group: 'Moving averages', color: 's4',
    width: 1.5, params: { length: 200, offset: 0, source: 'close' } },
  { id: 'ema9', label: 'EMA 9', group: 'Moving averages', color: 's5',
    width: 1.4, params: { length: 9, offset: 0, source: 'close' } },
  { id: 'ema21', label: 'EMA 21', group: 'Moving averages', color: 's7',
    width: 1.4, params: { length: 21, offset: 0, source: 'close' } },
  { id: 'ema50', label: 'EMA 50', group: 'Moving averages', color: 's6',
    width: 1.4, params: { length: 50, offset: 0, source: 'close' } },
  { id: 'fib', label: 'Fibonacci', group: 'Levels', color: 'refFib', width: 1 },
  { id: 'sr', label: 'Support & resistance', group: 'Levels', color: 'refSR', width: 1 },
  { id: 'zones', label: 'Supply & demand', group: 'Levels', color: 'neg', width: 1 },
  { id: 'vbp', label: 'Volume by price', group: 'Volume', color: 'ink2', width: 1 },
  { id: 'vol', label: 'Volume', group: 'Volume', color: 'ink2', width: 1 },
  { id: 'insiders', label: 'Insider trades', group: 'Events', color: 's3', width: 1 },
  { id: 'sessions', label: 'Session dividers', group: 'Events', color: 'ink2', width: 1 },
  { id: 'trends', label: 'Auto trend lines', group: 'Levels', color: 'pos', width: 1.6 },
];

const OVERLAY_BY_ID = Object.fromEntries(OVERLAY_DEFS.map((d) => [d.id, d]));

/* Line widths offered. A free-text box invites 0.3 and 17, neither of which
 * renders usefully, and a slider gives no repeatable value. */
const WIDTH_CHOICES = [1, 1.5, 2, 2.5, 3];

/* The colours a user can pick, as tokens. The categorical eight plus the two
 * reference hues and the two directional ones — the same set the charts already
 * draw from, so a hand-picked colour cannot land outside the validated palette
 * and collide with a series under colour-vision simulation. */
const COLOR_CHOICES = [
  's1', 's2', 's3', 's4', 's5', 's6', 's7', 's8',
  'refSR', 'refFib', 'pos', 'neg', 'ink', 'ink2',
];

const PRICE_SOURCES = ['close', 'open', 'high', 'low', 'hl2', 'ohlc4'];

let chartStyle = {};
try {
  const saved = JSON.parse(localStorage.getItem(CHART_STYLE_KEY) || '{}');
  if (saved && typeof saved === 'object') chartStyle = saved;
} catch (e) { /* private mode, or hand-edited storage */ }

/** The resolved style for one overlay: stored preference over default. */
function overlayStyle(id) {
  const def = OVERLAY_BY_ID[id] || {};
  const saved = chartStyle[id] || {};
  const colorToken = COLOR_CHOICES.includes(saved.color) ? saved.color : def.color;
  return {
    id,
    label: def.label || id,
    group: def.group || 'Other',
    colorToken,
    // Resolved through C so a theme switch repaints without touching storage.
    color: C[colorToken] || C.ink,
    width: WIDTH_CHOICES.includes(saved.width) ? saved.width : (def.width || 1.5),
    params: { ...(def.params || {}), ...(saved.params || {}) },
  };
}

function setOverlayStyle(id, patch) {
  if (!OVERLAY_BY_ID[id]) return;
  const next = { ...(chartStyle[id] || {}) };
  if (patch.color !== undefined) next.color = patch.color;
  if (patch.width !== undefined) next.width = Number(patch.width);
  if (patch.params) next.params = { ...(next.params || {}), ...patch.params };
  chartStyle[id] = next;
  try { localStorage.setItem(CHART_STYLE_KEY, JSON.stringify(chartStyle)); }
  catch (e) { /* private mode: the session still works, it just forgets */ }
}

function resetOverlayStyle(id) {
  if (id) delete chartStyle[id];
  else chartStyle = {};
  try { localStorage.setItem(CHART_STYLE_KEY, JSON.stringify(chartStyle)); }
  catch (e) { /* private mode */ }
}

/** Has this overlay been changed from its default? Drives the "reset" affordance,
 *  which should only appear when there is something to reset. */
function overlayStyled(id) {
  const s = chartStyle[id];
  return !!s && (s.color !== undefined || s.width !== undefined
    || (s.params && Object.keys(s.params).length > 0));
}

const IND_FALLBACK_CATALOGUE = [
  { id: 'vwap', name: 'Anchored VWAP', group: 'Execution',
    measures: 'The volume-weighted average price paid since the anchor date.' },
  { id: 'bollinger', name: 'Bollinger bands', group: 'Volatility',
    measures: 'A 20-day average with bands at 2 standard deviations of the close.' },
  { id: 'keltner', name: 'Keltner channel', group: 'Volatility',
    measures: 'An EMA with bands at 2x ATR.' },
  { id: 'donchian', name: 'Donchian channel', group: 'Volatility',
    measures: 'The highest high and lowest low of the last 20 sessions.' },
  { id: 'sec', name: 'Regression channel', group: 'Trend',
    measures: 'A least-squares fit with bands at 2 standard errors.' },
  { id: 'adx', name: 'ADX and DI', group: 'Trend',
    measures: 'Trend strength, with direction carried separately.' },
  { id: 'stochastic', name: 'Stochastic', group: 'Momentum',
    measures: 'Where the close sits inside the recent range.' },
  { id: 'obv', name: 'On-balance volume', group: 'Flow',
    measures: 'Volume signed by the day\u2019s direction, accumulated.' },
  { id: 'mfi', name: 'Money flow index', group: 'Flow',
    measures: 'RSI computed on price times volume.' },
  { id: 'rs', name: 'Relative strength line', group: 'Trend',
    measures: 'Price divided by SPY, rebased to 100.' },
];

const IND_COLORS = ['s1', 's3', 's4', 'neg'];

/* Which indicators belong ON the price axis rather than in their own pane.
 *
 * Everything here is quoted in the same units as price, so overlaying it is
 * meaningful. ADX is 0-100, on-balance volume is a share count and the relative
 * strength line is rebased to 100 — putting any of those on a price axis would
 * either flatten the price to a line or push the indicator off the top. Mirrors
 * the `pane` field the server already sets; kept client-side too so the dropdown
 * can label each option before the first fetch returns. */
const IND_PRICE_PANE = ['vwap', 'bollinger', 'keltner', 'donchian', 'sec'];

/* Overlay colours are ALLOCATED, not hard-coded, and the difference is the whole
 * point of doing it this way.
 *
 * The fixed map this replaces assigned VWAP the same amber as the 200-day average
 * and Donchian the same green as the 50-day, so the chart legend and the hover
 * tooltip each showed two different series with one swatch. Hard-coding cannot fix
 * that class of bug properly, because what the base chart occupies changes with
 * the mode: line mode uses s1 for the close and s2/s3/s4 for the averages, candle
 * mode uses s3 and s8 for the bodies and shifts the averages to s1/s2/s4. Any
 * fixed choice collides in one mode or the other.
 *
 * So the base colours are collected at render time and each overlay takes the next
 * hue nobody is using. Allocation walks the catalogue in a fixed order rather than
 * the order boxes were ticked, so a given set of indicators always gets the same
 * colours regardless of how it was assembled.
 *
 * Ordered by distance from the categorical slots the base chart draws from. s6 is
 * deliberately late: it is a dark green that sits close to s3, so it is a last
 * resort rather than a peer of the others.
 */
/* Ordered by distance from the categorical slots the base chart draws from.
 *
 * `refFib` is deliberately NOT here: it is the same hex as `ink2` (#c3c2b7), so
 * including both put Keltner and the regression channel on one colour in the very
 * case this allocator exists to prevent.
 */
const IND_COLOR_POOL = ['s7', 's5', 'ink2', 's8', 'refSR', 's6'];

/* Last resort when the pool is exhausted.
 *
 * The first version fell back to a fixed slot, which duplicated whatever already
 * held it — with candles, support/resistance and five overlays on at once, the
 * pool ran out and the fallback handed the regression channel the same purple as
 * VWAP. A generator cannot run out: it walks the hue circle in coarse steps and
 * returns the first colour not already spoken for, so the guarantee holds no
 * matter how many series end up on one plot.
 */
function spareHue(taken) {
  for (let h = 30; h < 360; h += 37) {
    const candidate = `hsl(${h} 62% 62%)`;
    if (!taken.has(candidate)) return candidate;
  }
  return 'hsl(0 0% 70%)';
}

function allocateOverlayColors(usedColors) {
  const taken = new Set((usedColors || []).filter(Boolean));
  const out = {};
  let cursor = 0;
  // Catalogue order, so the assignment is stable across selections.
  IND_FALLBACK_CATALOGUE.forEach((row) => {
    if (!IND_PRICE_PANE.includes(row.id) || !indicatorIds.includes(row.id)) return;
    while (cursor < IND_COLOR_POOL.length && taken.has(C[IND_COLOR_POOL[cursor]])) {
      cursor += 1;
    }
    const slot = IND_COLOR_POOL[cursor];
    const color = slot ? C[slot] : spareHue(taken);
    out[row.id] = color;
    taken.add(color);
    cursor += 1;
  });
  return out;
}

/* One legend entry per selected overlay, named for the indicator rather than the
 * line, and only for those whose data has actually arrived. Keltner and Donchian
 * each draw several lines in one colour, and three rows reading "Keltner upper /
 * mid / lower" would be longer than the rest of the legend for no extra
 * information. */
function indicatorOverlayLegend(palette) {
  const got = (STATE.indicators && STATE.indicators.indicators) || {};
  const colors = palette || allocateOverlayColors([]);
  return indicatorIds
    .filter((id) => IND_PRICE_PANE.includes(id))
    .map((id) => {
      const v = got[id];
      if (!v || !v.available || !v.lines || !v.lines.length) return null;
      return { name: v.name, color: colors[id] || C.s7 };
    })
    .filter(Boolean);
}

/* Align an indicator series to the bars the chart is actually plotting.
 *
 * A correctness step, not a tidiness one. The indicator endpoint is asked for two
 * years; the chart might be showing 126 bars. lineChart sizes its x-axis from the
 * longest series it is given, so a 500-point overlay against 126 labels stretched
 * the axis to 500 and squashed the whole price history into the left quarter of the
 * plot, with the y-axis dragged down to two-year-old lows.
 *
 * Both series end on the same bar — the latest — so alignment is from the right. A
 * shorter indicator history is left-padded with nulls rather than stretched, so the
 * line simply starts where its data starts.
 */
function alignToChart(values, bars) {
  if (!Array.isArray(values)) return [];
  if (values.length === bars) return values;
  if (values.length > bars) return values.slice(values.length - bars);
  return new Array(bars - values.length).fill(null).concat(values);
}

function indicatorOverlaySeries(bars, palette) {
  const got = (STATE.indicators && STATE.indicators.indicators) || {};
  const colors = palette || allocateOverlayColors([]);
  const out = [];
  indicatorIds.forEach((id) => {
    if (!IND_PRICE_PANE.includes(id)) return;
    const v = got[id];
    if (!v || !v.available || !v.lines) return;
    v.lines.forEach((line, i) => {
      out.push({
        name: line.name,
        values: bars ? alignToChart(line.values, bars) : line.values,
        color: colors[id] || C.s7,
        width: 1.4,
        dash: i === 0 ? null : '4 3',
        marker: false,
      });
    });
  });
  return out;
}

function drawIndicatorCharts() {
  const data = STATE.indicators;
  if (!data || !data.available) return;
  const labels = data.dates || [];
  indicatorIds.forEach((id) => {
    const v = (data.indicators || {})[id];
    if (!v || !v.available || !v.lines) return;
    const host = document.getElementById(`chart-ind-${id}`);
    if (!host) return;
    const series = v.lines.map((line, i) => ({
      name: line.name,
      values: line.values,
      color: C[IND_COLORS[i % IND_COLORS.length]],
    }));
    mount(`legend-ind-${id}`, legend(series.map((x) => ({ name: x.name, color: x.color }))));
    mount(`chart-ind-${id}`, (w) => lineChart({
      width: w,
      height: 150,
      labels,
      series,
      valueTags: true,
      refLineFit: 'clip',
      refLines: (v.reference || []).map((r) => ({
        value: r.value, color: C.ink2, label: r.label, pattern: '3 3', dim: true,
      })),
    }));
  });
}

async function loadIndicators(force) {
  if (!STATE.ticker) return;
  if (!indicatorIds.length) { STATE.indicators = null; return; }
  const key = `${STATE.ticker}|${indicatorIds.join(',')}`;
  if (STATE.indicatorsKey === key && !force) return;
  STATE.indicatorsKey = key;
  let payload;
  try {
    payload = await getJSON(
      `/api/indicators/${encodeURIComponent(STATE.ticker)}`
      + `?ids=${encodeURIComponent(indicatorIds.join(','))}`);
  } catch (err) {
    payload = { available: false, reason: err.message };
  }
  // Ticking four boxes quickly starts four requests, and they do not come back in
  // order. Without this check the slowest reply wins: selecting VWAP, ADX, RS then
  // the regression channel left the channel missing from the panel because a
  // three-indicator response landed after the four-indicator one.
  if (STATE.indicatorsKey !== key) return;
  STATE.indicators = payload;
  const host = document.getElementById('ind-panes-host');
  if (host && STATE.view === 'swing') {
    host.innerHTML = renderIndicatorPanes();
    drawIndicatorCharts();
  }
  // An overlay changes the price chart and its legend, both of which were built
  // before this payload existed — the chart ended up carrying six extra lines
  // that the legend did not name. Only re-render when an overlay is actually
  // selected, so choosing a pane-only indicator stays a local update.
  if (STATE.swing && STATE.view === 'swing'
      && indicatorIds.some((id) => IND_PRICE_PANE.includes(id))) {
    preserveUI(views.swing, () => renderSwing(STATE.swing));
  }
}

/* One cross-asset instrument, full history.
 *
 * Every table of instruments in the terminal — the macro dashboard, the ratios,
 * the rates and FX blocks — showed a 90-day sparkline and stopped there. A
 * sparkline says "roughly this shape"; it cannot tell you where the level sits
 * against its own year, and it has no axis to read. Clicking the row now opens
 * the real chart.
 *
 * Presented as a sub-tab of the group you were already in rather than a modal or
 * a new top-level tab. Opening VIX from Macro should not move you out of Market,
 * and it should be somewhere you can come back to and close.
 */
const INSTRUMENT_RANGES = [
  { key: '1mo', label: '1M' }, { key: '3mo', label: '3M' },
  { key: '6mo', label: '6M' }, { key: '1y', label: '1Y' },
  { key: '2y', label: '2Y' }, { key: '5y', label: '5Y' },
];
let instrumentRange = '1y';
let instrumentMode = 'line';

function renderInstrument(d) {
  if (!d) return '<div class="panel span-all"><p class="sub">Pick an instrument.</p></div>';
  if (d === 'loading') {
    return viewSkeleton('instrument history', 6);
  }
  if (!d.available) {
    return `<div class="panel span-all"><h2>${hg('Instrument')}</h2>
      <div class="callout">${esc(d.reason || 'Unavailable.')}</div></div>`;
  }
  const s = d.snapshot || {};
  const decimals = Math.abs(s.last || 0) < 10 ? 4 : 2;

  const stat = (label, value, cls, note) => `<div class="tile">
    <span class="label">${hg(label)}</span>
    <span class="value ${cls || ''}">${value}</span>
    ${note ? `<span class="note">${esc(note)}</span>` : ''}</div>`;

  return `<div class="panel span-all">
    <div class="weekly-kicker">${esc(d.group || 'cross-asset')}</div>
    <h2 class="weekly-title">${esc(d.label)}${askPulse('instrument')}</h2>
    <p class="weekly-sub">${esc(cap(d.note || ''))} · ${esc(d.symbol)},
      ${fmt((d.dates || []).length, 0)} daily bars.</p>

    <div class="inst-stats">
      ${stat('Last', fmt(s.last, decimals))}
      ${stat('1 day', fmtPct(s.chg_1d, 2), signClass(s.chg_1d))}
      ${stat('20 days', fmtPct(s.chg_20d, 2), signClass(s.chg_20d))}
      ${stat('vs 200-day', fmtPct(s.vs_sma200, 1), signClass(s.vs_sma200))}
      ${stat('RSI', fmt(s.rsi, 0), '',
    s.rsi >= 70 ? 'overbought territory' : s.rsi <= 30 ? 'oversold territory' : 'mid-range')}
      ${stat('From 52-week high', fmtPct(s.pct_from_52w_high, 1), signClass(s.pct_from_52w_high))}
    </div>

    <div class="chart-toolbar" style="margin-top:var(--space-4)">
      ${rangePills(INSTRUMENT_RANGES, instrumentRange, 'data-inst-range', 'Timeframe')}
      <div class="seg" role="group" aria-label="Chart style">
        <button type="button" data-inst-mode="line"
          aria-pressed="${instrumentMode === 'line'}">Line</button>
        <button type="button" data-inst-mode="candle"
          aria-pressed="${instrumentMode === 'candle'}">Candles</button>
      </div>
    </div>
    <div id="legend-inst"></div>
    <div id="chart-inst"></div>
    <p class="caveat">${gloss('Daily bars from the same feed the cross-asset tables read, so '
    + 'the level here and the level in the table are the same number. An index level, a '
    + 'yield proxy and a currency cross are not tradeable instruments. This is the '
    + 'reference series, not a price you could deal at.')}</p>
  </div>`;
}

function drawInstrumentChart(d) {
  if (!d || d === 'loading' || !d.available) return;
  const host = document.getElementById('chart-inst');
  if (!host) return;
  const candles = instrumentMode === 'candle' && d.open && d.high && d.low
    ? { open: d.open, high: d.high, low: d.low, close: d.close } : null;
  mount('legend-inst', legend([
    { name: d.label, color: C.s1 },
    ...(d.volume ? [{ name: 'Volume', color: C.ink2, boxed: true }] : []),
  ]));
  mount('chart-inst', (w) => lineChart({
    width: w,
    height: 380,
    labels: d.dates || [],
    volume: d.volume || null,
    series: [{ name: d.label, values: d.close, color: C.s1,
      hidden: !!candles, fill: !candles }],
    candles,
    valueTags: true,
  }));
}

async function loadInstrument(force) {
  const inst = STATE.instrument;
  if (!inst) { views.instrument.innerHTML = renderInstrument(null); return; }
  const key = `${inst.symbol}|${instrumentRange}`;
  if (STATE.instrumentKey === key && !force) {
    views.instrument.innerHTML = renderInstrument(STATE.instrumentData);
    drawInstrumentChart(STATE.instrumentData);
    return;
  }
  STATE.instrumentKey = key;
  views.instrument.innerHTML = renderInstrument('loading');
  let payload;
  try {
    payload = await getJSON(`/api/instrument?symbol=${encodeURIComponent(inst.symbol)}`
      + `&range=${encodeURIComponent(instrumentRange)}`);
  } catch (err) {
    payload = { available: false, reason: err.message };
  }
  // Same stale-response guard as the indicator picker: switching instrument or
  // timeframe quickly starts several fetches and they do not return in order.
  if (STATE.instrumentKey !== key) return;
  STATE.instrumentData = payload;
  views.instrument.innerHTML = renderInstrument(payload);
  drawInstrumentChart(payload);
  revealPanels(views.instrument);
}

/* Open an instrument chart from any table row that carries the attributes. */
function openInstrument(symbol, label, fromGroup) {
  STATE.instrument = { symbol, label };
  STATE.instrumentFrom = fromGroup || groupForView(STATE.view);
  // The exact view, not just the group. Closing the chart returned to the
  // group's first tab, so opening VIX from Macro and closing it landed on Read.
  if (STATE.view !== 'instrument') STATE.instrumentBack = STATE.view;
  STATE.instrumentData = null;
  STATE.instrumentKey = null;
  switchView('instrument');
}

/* The overnight session worldwide.
 *
 * The morning read was entirely domestic, which left out the fact that by the time
 * New York opens the day has already been priced twice — once in Asia, once in
 * Europe. Ordered by when each market traded rather than alphabetically or by size,
 * because the handoff from Tokyo to Frankfurt to New York is the content.
 *
 * The correlation column is the part that matters most, and it usually says the
 * unglamorous thing. It answers the question a percentage cannot: has this market
 * actually been moving with the S&P at all? A 6% night in Seoul reads very
 * differently at 0.32 than it would at 0.8, and no amount of narrative can
 * substitute for that number.
 */
function renderGlobal(g) {
  if (!g) return '';
  if (!g.available) {
    return `<div class="panel span-all"><h2>${hg('Overnight, worldwide')}</h2>
      <p class="sub">${esc(g.reason || 'Unavailable.')}</p></div>`;
  }
  const row = (r) => `<tr class="inst-clickable" data-instrument="${esc(r.symbol)}"
      data-instrument-label="${esc(r.label)}" tabindex="0" role="button"
      title="Open the full chart for ${esc(r.label)}">
    <td class="name"><span class="inst-link">${esc(r.label)}</span>
      <span class="pat-sub">${esc(r.region)} · ${esc(r.note)}</span></td>
    <td class="num ${signClass(r.chg_1d)}">${fmtPct(r.chg_1d, 2)}</td>
    <td class="num ${signClass(r.chg_5d)}">${fmtPct(r.chg_5d, 2)}</td>
    <td class="num ${signClass(r.chg_20d)}">${fmtPct(r.chg_20d, 2)}</td>
    <td class="num">${r.corr_spx === null || r.corr_spx === undefined ? '—'
    : `<span class="gm-corr ${r.corr_spx >= g.corr_threshold ? 'linked' : 'loose'}"
        >${fmt(r.corr_spx, 2)}</span>`}
      <span class="pat-sub">${esc(r.corr_read || '')}</span></td>
  </tr>`;

  return `<div class="panel span-all">
    <h2>${hg('Overnight, worldwide')}${askPulse('global')}</h2>
    <p class="sub">Every market that traded before the US open, in the order it
      traded. And how tightly each one has actually moved with the S&amp;P over the
      last ${fmt(g.corr_window, 0)} sessions.</p>

    ${(g.sessions || []).map((sess) => `
      <h3 class="pat-head">${esc(sess.label)}</h3>
      <p class="caveat" style="margin-top:0">${sess.advancing} up, ${sess.declining} down,
        average ${fmtPct(sess.avg_move_pct, 2)} on the session.</p>
      <div class="table-scroll"><table class="data pat-table">
        <thead><tr><th>Market</th><th class="num">Session</th><th class="num">5 days</th>
          <th class="num">20 days</th>
          <th class="num">Correlation to the S&amp;P</th></tr></thead>
        <tbody>${sess.rows.map(row).join('')}</tbody>
      </table></div>`).join('')}

    ${(g.crosses || []).length ? `<h3 class="pat-head">What carries it into US hours</h3>
    <div class="table-scroll"><table class="data pat-table">
      <thead><tr><th>Cross</th><th class="num">1 day</th><th class="num">5 days</th>
        <th class="num">20 days</th><th class="num">Correlation to the S&amp;P</th></tr></thead>
      <tbody>${g.crosses.map(row).join('')}</tbody>
    </table></div>` : ''}

    <div class="callout"><strong>${g.linked_count} of ${g.market_count}</strong> of these
      markets have moved with the S&amp;P closely enough over the last
      ${fmt(g.corr_window, 0)} sessions to read across
      (correlation at or above ${fmt(g.corr_threshold, 1)}). For the rest, a big night
      is a fact about that market rather than a signal about this one. Which is
      usually the honest answer, and the one a narrative would talk you out of.</div>

    <p class="caveat">${gloss(g.method || '')}</p>
    <p class="caveat">No causal claim is made here and none should be read in.
      Headlines and market moves that happen the same morning are adjacent, not
      necessarily connected, and nothing in this panel can tell the two apart.
      The correlation column is the closest it gets, and it is a description of the
      past quarter rather than an explanation of today.</p>
  </div>`;
}

async function loadGlobal() {
  if (STATE.globalOvernight) return;
  try {
    STATE.globalOvernight = await getJSON('/api/global');
  } catch (err) {
    STATE.globalOvernight = { available: false, reason: err.message };
  }
  mountPanel('global-host', renderGlobal(STATE.globalOvernight));
}

function renderPeHistory(p) {
  if (!p) return '';
  if (!p.available) {
    return `<div class="panel span-all"><h2>${hg('Multiple and revenue history')}</h2>
      <p class="sub">${esc(p.reason || 'Unavailable.')}</p>
      ${(p.notes || []).map((n) => `<p class="caveat">${esc(n)}</p>`).join('')}</div>`;
  }

  const growth = p.revenue_growth || [];
  const recent = growth.slice(-8).reverse();
  const b = p.pe_bands || {};
  const anchor = p.anchor || {};

  return `<div class="panel span-all">
    <h2>${hg('Multiple and revenue history')}${askPulse('pehistory')}</h2>
    <p class="sub">Price divided by trailing-twelve-month diluted earnings, weekly,
      straight from ${fmt(p.counts.eps_quarters || 0, 0)} quarters of SEC filings.
      Alongside what revenue was doing over the same stretch.</p>

    <div class="pe-tiles" style="margin-top:var(--space-4)">
      <div class="tile"><span class="label">${hg('Trailing P/E now')}</span>
        <span class="value">${fmt(p.pe_current, 1)}</span>
        <span class="note">${fmt(p.pe_percentile, 0)}th percentile of its own last
          ${fmt(Math.round((p.band_weeks || 0) / 52), 0)} years</span></div>
      <div class="tile"><span class="label">${hg('Its own median')}</span>
        <span class="value">${fmt(p.pe_median, 1)}</span>
        <span class="note">quarter range ${fmt(b['25'], 0)} to ${fmt(b['75'], 0)}</span></div>
      <div class="tile"><span class="label">${hg('Latest revenue growth')}</span>
        <span class="value ${growth.length ? signClass(growth[growth.length - 1].growth_pct) : ''}">${
  growth.length ? `${growth[growth.length - 1].growth_pct > 0 ? '+' : ''}${
    fmt(growth[growth.length - 1].growth_pct, 1)}%` : '—'}</span>
        <span class="note">${growth.length ? esc(growth[growth.length - 1].label)
    + ' versus a year earlier' : 'no filed history'}</span></div>
      <div class="tile"><span class="label">${hg('Cross-check')}</span>
        <span class="value ${anchor.agrees ? 'pos' : anchor.available ? 'neg' : ''}">${
  anchor.available ? (anchor.agrees ? 'Agrees' : 'Differs') : '—'}</span>
        <span class="note">${anchor.available
    ? `ours ${fmt(anchor.ours, 1)} against the data provider's ${fmt(anchor.provider, 1)}`
    : 'no provider figure to compare'}</span></div>
    </div>

    <div id="legend-pe" style="margin-top:var(--space-4)"></div>
    <div id="chart-pe"></div>

    ${recent.length ? `<div class="table-scroll" style="margin-top:var(--space-4)">
      <table class="data">
        <thead><tr><th>Quarter ended</th><th class="num">Revenue</th>
          <th class="num">Versus a year earlier</th><th>Public from</th></tr></thead>
        <tbody>${recent.map((g) => `<tr>
          <td class="name">${esc(g.label)}<span class="pat-sub">${esc(g.period_end)}</span></td>
          <td class="num">$${fmt(g.revenue / 1e9, 2)}B</td>
          <td class="num ${signClass(g.growth_pct)}">${g.growth_pct > 0 ? '+' : ''}${
    fmt(g.growth_pct, 1)}%</td>
          <td>${esc(g.available_from)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>` : ''}

    ${(p.notes || []).map((n) => `<div class="callout">${esc(n)}</div>`).join('')}
    ${anchor.available && !anchor.agrees ? `<div class="callout">Our trailing P/E of
      ${fmt(anchor.ours, 1)} differs from the data provider's ${fmt(anchor.provider, 1)}
      by ${fmt(anchor.diff_pct, 1)}%. The two are built from different sources, so a
      gap this wide means one of them is wrong and this panel cannot tell you which.
      Treat the level as approximate.</div>` : ''}
    <p class="caveat">${gloss(p.method || '')}</p>
    <p class="caveat">${esc(p.source || '')}${p.cache_age_days !== null
    && p.cache_age_days !== undefined ? `, cached ${fmt(p.cache_age_days, 0)} days`
    : ''}. ${p.loss_weeks ? `${fmt(p.loss_weeks, 0)} weeks are missing from the line
      because the trailing year was loss-making.` : ''}</p>
  </div>`;
}

function drawPeChart(p) {
  if (!p || !p.available || !p.pe_series || !p.pe_series.length) return;
  const host = document.getElementById('chart-pe');
  if (!host) return;
  const pts = p.pe_series;
  const b = p.pe_bands || {};
  mount('legend-pe', legend([
    { name: 'Trailing P/E', color: C.s1 },
    { name: 'Its own median', color: C.ink2, boxed: true },
  ]));
  mount('chart-pe', (w) => lineChart({
    width: w,
    height: 210,
    labels: pts.map((x) => x.date),
    series: [{ name: 'Trailing P/E', values: pts.map((x) => x.pe), color: C.s1,
      fill: true }],
    valueTags: true,
    yFormat: (v) => fmt(v, 0),
    // Clipped, not expanded. A name that once traded at 600x would otherwise
    // squash a decade of 20-40x into the bottom two pixels of the pane.
    refLineFit: 'clip',
    refLines: [
      { value: b['50'], color: C.ink2, label: `median ${fmt(b['50'], 0)}x`,
        emphasis: true },
      { value: b['25'], color: C.ink2, dim: true, pattern: '2 3' },
      { value: b['75'], color: C.ink2, dim: true, pattern: '2 3' },
    ].filter((r) => r.value !== null && r.value !== undefined),
  }));
}

/* ------------------------------------------------------------ seasonality
 *
 * Does the calendar itself carry information for this ticker?
 *
 * The panel is built around the thing every other version of it leaves out. A
 * bar chart of average monthly returns is easy and misleading: fifteen years
 * gives fifteen observations per calendar month against a monthly standard
 * deviation near 7%, and at that ratio the gap between the best and worst month
 * is what noise looks like. So n is on every row, the significance threshold is
 * corrected for the number of buckets tested, and "noise" is printed plainly
 * because it is the expected answer.
 */

const SEAS_VERDICT = {
  significant: { cls: 'up', label: 'Significant',
    tip: 'Clears the corrected threshold. The effect is larger than the sample size can easily explain by chance.' },
  unproven: { cls: 'warn', label: 'Unproven',
    tip: 'Would pass on its own at p<0.05, but does not survive correcting for how many buckets were tested. Suggestive, not established.' },
  noise: { cls: 'muted', label: 'Noise',
    tip: 'Indistinguishable from chance at this sample size. The expected answer for most tickers and most months.' },
  'too few': { cls: 'muted', label: 'Too few',
    tip: 'Not enough observations to say anything. A mean was still computed; it should not be read as a finding.' },
};

function seasVerdict(v) {
  const meta = SEAS_VERDICT[v] || SEAS_VERDICT.noise;
  return `<span class="seas-verdict ${meta.cls}" title="${esc(meta.tip)}">${meta.label}</span>`;
}

/** A bar that reads from a shared centre, so rows compare against each other
 *  rather than each against its own maximum. */
function seasBar(value, scale) {
  const v = Number(value);
  if (!Number.isFinite(v) || !scale) return '<div class="seas-bar"></div>';
  const pct = Math.min(Math.abs(v) / scale, 1) * 50;
  const side = v >= 0 ? 'left:50%' : `right:50%`;
  return `<div class="seas-bar"><i class="${v >= 0 ? 'up' : 'down'}"
    style="${side};width:${pct.toFixed(1)}%"></i></div>`;
}

function seasRows(section, rows, digits, robustKey) {
  const scale = Math.max(...rows.map((r) =>
    Math.abs(Number((r.excess || {}).mean) || 0)), 0.0001);
  return rows.map((r) => {
    const e = r.excess || {}, raw = r.raw || {};
    const n = raw.n || 0;
    return `<tr>
      <td class="name">${esc(r.label)}${r.is_reporting_month
    ? ` <span class="seas-rpt" title="This is one of the months the company usually publishes results in. A calendar effect landing here is most likely the earnings reaction rather than the season.">reports</span>` : ''}</td>
      <td>${n}</td>
      <td class="${signClass(raw.mean)}">${fmt(raw.mean, digits)}%</td>
      <td class="${signClass(e.mean)}"><strong>${fmt(e.mean, digits)}%</strong></td>
      <td>${seasBar(e.mean, scale)}</td>
      <td>${raw.hit_rate === null || raw.hit_rate === undefined
    ? '—' : fmt(raw.hit_rate, 0) + '%'}</td>
      <td class="${signClass(raw[robustKey])}">${fmt(raw[robustKey], digits)}%</td>
      <td>${e.p === null || e.p === undefined ? '—' : fmt(e.p, 3)}</td>
      <td>${seasVerdict(e.verdict)}</td>
    </tr>`;
  }).join('');
}

function renderSeasonality(s) {
  if (!s) return '';
  if (s.error) {
    return `<div class="panel span2"><h2>${hg('Seasonality')}</h2>
      <p class="sub">${esc(s.error)}</p></div>`;
  }
  const mo = s.monthly || {}, wd = s.weekday || {}, tom = s.turn_of_month || {};
  const found = s.significant_count || 0;

  const headline = found
    ? `<strong>${found} effect${found === 1 ? '' : 's'} clear${found === 1 ? 's' : ''} the
       corrected threshold.</strong> That is more than usual. Check the sample size and
       whether the month is one the company reports in before treating it as real.`
    : `<strong>Nothing here clears the corrected threshold.</strong> That is the normal
       result, and it is the honest one: at this sample size the differences between months
       are what chance produces. Read the table as texture, not as a signal.`;

  return `<div class="panel span2 gap">
    <h2>${hg('Seasonality')}</h2>
    <p class="sub">Whether the calendar itself carries information for ${esc(s.ticker)}.
      Returns sliced by month, weekday and the turn of the month, over
      ${fmt(s.years, 0)} years (${esc(s.start)} to ${esc(s.end)}). Every figure is shown
      both raw and net of ${esc(s.benchmark)} over the same period, because "December is
      strong" must not just mean "the market went up in December".</p>

    <div class="callout" style="margin:0 0 12px">${headline}</div>

    <h3>${hg('Month of the year')}</h3>
    <p class="caveat" style="margin-top:0">${fmt(mo.periods, 0)} months of history, so about
      ${fmt((mo.periods || 0) / 12, 0)} observations behind each row. Twelve buckets are
      tested, so the bar for significance is 0.05 ÷ 12 = <strong>p &lt;
      ${fmt(mo.threshold, 4)}</strong>, not 0.05. Testing twelve things gives twelve
      chances to get lucky once.</p>
    <table class="data">
      <thead><tr><th>Month</th><th>Years</th><th>Mean</th><th>vs ${esc(s.benchmark)}</th>
        <th></th><th>Up</th><th>Ex best yr</th><th>p</th><th>Verdict</th></tr></thead>
      <tbody>${seasRows('monthly', mo.rows || [], 2, 'mean_ex_best')}</tbody>
    </table>
    <p class="caveat"><strong>Ex best yr</strong> is the same mean with that month's single
      best year removed. A column that collapses when one year comes out was one year, not a
      season. ${(s.reporting_months || []).length ? `Months marked
      <span class="seas-rpt">reports</span> are when ${esc(s.ticker)} usually publishes
      results. An effect there is most likely the earnings reaction wearing a calendar
      costume.` : ''}</p>

    <h3 style="margin-top:18px">${hg('Day of the week')}</h3>
    <p class="caveat" style="margin-top:0">Worth more than the monthly grid on sample size
      alone: ${fmt(wd.periods, 0)} trading days gives roughly
      ${fmt((wd.periods || 0) / 5, 0)} observations per weekday against about fifteen per
      calendar month, so a real effect has somewhere to show up. Five buckets, so the bar is
      <strong>p &lt; ${fmt(wd.threshold, 3)}</strong>.</p>
    <table class="data">
      <thead><tr><th>Day</th><th>Days</th><th>Mean</th><th>vs ${esc(s.benchmark)}</th>
        <th></th><th>Up</th><th>Median</th><th>p</th><th>Verdict</th></tr></thead>
      <tbody>${seasRows('weekday', wd.rows || [], 3, 'median')}</tbody>
    </table>
    <p class="caveat">This table shows the median rather than the drop-the-best-one figure
      used above. Removing a single observation is a real check against 15 years; against
      700 days it moves the mean by nothing and would only look like a check. The median is
      the honest robustness column at this sample size. Far from the mean means a few large
      days are carrying it.</p>

    <h3 style="margin-top:18px">${hg('Turn of the month')}</h3>
    <p class="caveat" style="margin-top:0">The last ${fmt((tom.window || {}).before, 0)} and
      first ${fmt((tom.window || {}).after, 0)} trading days of each month against the rest
      of it. The window fixed in advance rather than chosen for producing the best number.
      One comparison, so no correction is owed and the bar is the plain p &lt; 0.05.</p>
    <table class="data">
      <thead><tr><th>Window</th><th>Days</th><th>Mean</th><th>vs ${esc(s.benchmark)}</th>
        <th>Up</th></tr></thead>
      <tbody>${(tom.rows || []).map((r) => `<tr>
        <td class="name">${esc(r.label)}</td>
        <td>${(r.raw || {}).n || 0}</td>
        <td class="${signClass((r.raw || {}).mean)}">${fmt((r.raw || {}).mean, 3)}%</td>
        <td class="${signClass((r.excess || {}).mean)}"><strong>${
  fmt((r.excess || {}).mean, 3)}%</strong></td>
        <td>${fmt((r.raw || {}).hit_rate, 0)}%</td>
      </tr>`).join('')}</tbody>
    </table>
    <p class="caveat">Gap between the two windows:
      <strong>${fmt(tom.gap, 3)}%</strong> per day net of ${esc(s.benchmark)}, p =
      ${tom.p === null || tom.p === undefined ? '—' : fmt(tom.p, 3)} —
      ${seasVerdict(tom.verdict)}.</p>

    <p class="caveat" style="margin-top:14px">${gloss('Two limits worth holding on to. The '
    + 'correction above is within this ticker: check twenty tickers and you get twenty fresh '
    + 'chances at a false positive, and roughly one will land. And fifteen years is a single '
    + 'market regime for many names. A company listed after 2010 has never seen a sustained '
    + 'bear market in this sample, so a month that looks reliably strong may only have been '
    + 'tested in conditions that flattered it.')}</p>
  </div>`;
}

function renderPatterns(d) {
  const p = d && d.patterns;
  if (!p) return '';
  if (!p.available) {
    return `<div class="panel span2"><h2>${hg('Chart patterns')}</h2>
      <p class="sub">${esc(p.reason || 'Not enough history to read structure.')}</p></div>`;
  }
  const rates = STATE.patternRates;
  const structural = p.chart_patterns || [];
  const zones = p.zones || [];
  const candles = (p.candles || []).slice(0, 6);

  const stateChip = (pat) => {
    if (pat.confirmed === null) return '<span class="pat-chip open">forming</span>';
    if (pat.confirmed) {
      return `<span class="pat-chip conf">confirmed${
        pat.confirmed_on ? ' ' + esc(pat.confirmed_on) : ''}</span>`;
    }
    return '<span class="pat-chip unconf">not confirmed</span>';
  };

  const structRows = structural.length ? structural.slice().reverse().map((pat) => {
    const state = pat.confirmed === null ? 'candle'
      : (pat.confirmed ? 'confirmed' : 'unconfirmed');
    return `<tr>
      <td class="name">${esc(pat.name)}
        <span class="pat-sub">${esc(pat.start_date)} → ${esc(pat.end_date)},
          ${fmt(pat.span_bars, 0)} bars${pat.amplitude_atr
    ? ` · ${fmt(pat.amplitude_atr, 1)}× a typical day's range` : ''}</span>
        <span class="pat-conv">Conventionally: ${esc(pat.conventional)}</span></td>
      <td>${stateChip(pat)}</td>
      <td class="num">${pat.confirmed === null
    ? '<span class="pat-rate none">nothing to measure until it resolves</span>'
    : baseRateCell(rates, pat.name, state)}</td>
    </tr>`;
  }).join('') : '';

  const candleRows = candles.map((c) => `<tr>
    <td class="name">${esc(c.name)}
      <span class="pat-sub">${esc(c.date)}${c.bar_offset === 0 ? ' · latest bar'
    : ` · ${fmt(c.bar_offset, 0)} bars ago`} · ${esc(c.note)}</span>
      <span class="pat-conv">Conventionally: ${esc(c.conventional)}</span></td>
    <td><span class="pat-chip ${c.direction === 'bullish' ? 'up'
    : c.direction === 'bearish' ? 'down' : 'flat'}">${esc(c.direction)}</span></td>
    <td class="num">${baseRateCell(rates, c.name, 'candle')}</td>
  </tr>`).join('');

  const zoneRows = zones.map((z) => `<tr>
    <td class="name">${z.side === 'supply' ? 'Supply' : 'Demand'} zone
      <span class="pat-sub">Based ${esc(z.formed)}, left ${esc(z.left_on)} on a move of
        ${fmt(z.departure_atr, 1)}× a typical day's range over
        ${fmt(z.base_bars, 0)} bars of base</span>
      <span class="pat-conv">${z.side === 'supply'
    ? 'Sellers were waiting here and price could not hold above it.'
    : 'Buyers were waiting here and price could not stay below it.'}</span></td>
    <td class="num">${fmt(z.bottom, 2)} – ${fmt(z.top, 2)}</td>
    <td class="num ${signClass(z.distance_pct)}">${z.distance_pct > 0 ? '+' : ''}${
  fmt(z.distance_pct, 1)}%</td>
  </tr>`).join('');

  return `<div class="panel span-all">
    <h2>${hg('Chart patterns')}${askPulse('patterns')}</h2>
    <p class="sub">Structure, candles and zones read mechanically off the daily bars.
      Then, next to each one, what actually happened afterwards across 43 names and ten
      years. The two columns often disagree, and this panel deliberately does not
      resolve that for you.</p>

    ${structural.length ? `<h3 class="pat-head">Structure</h3>
    <div class="table-scroll"><table class="data pat-table">
      <thead><tr><th>Pattern</th><th>State</th>
        <th class="num">Conventional reading held, 21 sessions</th></tr></thead>
      <tbody>${structRows}</tbody>
    </table></div>
    <p class="caveat">A reversal pattern is only <em>confirmed</em> once a close has
      cleared its neckline, and cleared it promptly. A crossing months later is a
      coincidence, not a resolution. Confirmation is the whole difference on this
      data: all four confirmed structures land between 51% and 55%, and all four
      unconfirmed ones at or below 50%, one of them at 31%. A pattern that fails to
      confirm is not a weaker version of the same signal, it is the trend carrying
      on.</p>`
    : '<p class="sub">No structural pattern currently passes the size, prior-move and '
      + 'freshness tests over the last year.</p>'}

    ${zones.length ? `<h3 class="pat-head">Supply and demand</h3>
    <div class="table-scroll"><table class="data pat-table">
      <thead><tr><th>Zone</th><th class="num">Range</th>
        <th class="num">From spot</th></tr></thead>
      <tbody>${zoneRows}</tbody>
    </table></div>
    <p class="caveat">A zone is not the same thing as support. Support is a price that
      held; a zone is a price where one side was so heavily outnumbered that price
      could not stay there. A base no wider than ${fmt(p.tolerances.base_max_atr, 1)}×
      a typical day's range, then a departure of at least
      ${fmt(p.tolerances.departure_atr, 1)}× within ${fmt(4, 0)} bars. Both halves are
      required, so ordinary congestion does not qualify. Switch them on under
      <em>Technical Levels</em> to see them on the chart.
      ${p.zones_out_of_horizon ? `${fmt(p.zones_out_of_horizon, 0)} further zone${
    p.zones_out_of_horizon === 1 ? ' is' : 's are'} too far from spot to be reached in
      ${fmt(p.zone_horizon_bars, 0)} sessions and ${p.zones_out_of_horizon === 1
    ? 'is' : 'are'} not listed.` : ''}</p>` : ''}

    ${candleRows ? `<h3 class="pat-head">Recent candles</h3>
    <div class="table-scroll"><table class="data pat-table">
      <thead><tr><th>Bar</th><th>Direction</th>
        <th class="num">That direction held, 21 sessions</th></tr></thead>
      <tbody>${candleRows}</tbody>
    </table></div>
    <p class="caveat">Every candlestick pattern here measures between 46% and 51% on a
      sample of two to twelve thousand occurrences. That is a coin toss, and it is the
      most useful thing this panel can tell you about them: they describe what the bar
      did, and on this evidence they do not forecast what the next twenty do.</p>` : ''}

    <p class="caveat">${gloss(p.method || '')}</p>
    ${rates && rates.available ? `<p class="caveat">Base rates: ${
  gloss(rates.method || '')} Cached, ${fmt(rates.cache_age_days || 0, 0)} days old.</p>`
    : `<p class="caveat">Base rates have not been computed on this machine yet, so the
      measured column is empty. They take about ninety seconds to build.</p>`}
  </div>`;
}

function renderSectorConfirm(sc) {
  if (!sc || !sc.available) return '';
  const cls = SC_VERDICT_CLASS[sc.verdict] || 'flat';
  const tile = (label, value, sub, tone) => `<div class="sc-tile">
    <div class="idx-lbl">${esc(label)}</div>
    <div class="sc-val ${tone || ''}">${value}</div>
    ${sub ? `<div class="sc-sub">${esc(sub)}</div>` : ''}
  </div>`;

  return `<div class="panel span2">
    <h2>${hg('Sector confirmation')}${askPulse('sectorconfirm')}</h2>
    <p class="sub">${esc(sc.ticker)} · ${esc(sc.label)}, measured over the last ${
  fmt(sc.window_sessions, 0)} sessions.</p>
    <div class="grid c3" style="margin-top:var(--space-3)">
      ${tile('Stock sector', esc(sc.sector || '—'))}
      ${tile('Sector ETF benchmark',
    `<button type="button" class="tkr" data-analyse="${esc(sc.etf)}">${esc(sc.etf)}</button>`,
    sc.etf_name)}
      ${tile('Sector ETF trend',
    `<span class="sec-trend ${SECTOR_TREND_CLASS[sc.etf_trend] || 'flat'}">${
  esc(SECTOR_TREND_LABEL[sc.etf_trend] || sc.etf_trend || 'unknown')}</span>`,
    sc.etf_summary)}
      ${tile('RS vs SPY',
    sc.rs_vs_spy_pct === null ? '—'
      : `${sc.rs_vs_spy_pct > 0 ? '+' : ''}${fmt(sc.rs_vs_spy_pct, 2)}%`,
    sc.rs_vs_spy_label, signClass(sc.rs_vs_spy_pct))}
      ${tile('RS vs sector ETF',
    sc.rs_vs_sector_pct === null ? '—'
      : `${sc.rs_vs_sector_pct > 0 ? '+' : ''}${fmt(sc.rs_vs_sector_pct, 2)}%`,
    sc.rs_vs_sector_label, signClass(sc.rs_vs_sector_pct))}
      ${tile('Confirmation', `<span class="sec-trend ${cls}">${esc(sc.label)}</span>`)}
    </div>
    <p class="sc-note">${esc(sc.note || '')}</p>
    ${sc.conflict ? `<div class="callout"><strong>The two readings disagree.</strong>
      ${esc(sc.conflict)}</div>` : ''}
    <p class="caveat">${gloss(sc.method || '')}</p>
  </div>`;
}

/* Signal evaluation.
 *
 * The only panel here that tests a claim rather than making one, and the only
 * one whose result is currently unflattering. It stays visible for exactly that
 * reason: a terminal that scores things and never checks whether the scores work
 * is asking to be believed on authority.
 *
 * An information coefficient is never shown without its controls. On its own the
 * number is uninterpretable — a random score run through overlapping windows can
 * look meaningful, and a composite can look skilful while losing to one raw
 * factor. Both controls sit in the same table. */
function renderEvaluation(e) {
  if (!e) return '';
  if (!e.available) {
    return `<div class="panel span-all"><h2>${hg('Does the score work?')}</h2>
      <p class="sub">${esc(e.reason || 'Evaluation unavailable.')}</p></div>`;
  }
  const rows = (e.comparison || []).map((c) => `<tr>
    <td class="name">${fmt(c.horizon_sessions, 0)} sessions</td>
    <td class="num ${signClass(c.composite_ic)}">${c.composite_ic === null ? '—' : fmt(c.composite_ic, 4)}</td>
    <td class="num muted">${c.random_ic === null ? '—' : fmt(c.random_ic, 4)}</td>
    <td class="num">${c.single_factor_ic === null ? '—' : fmt(c.single_factor_ic, 4)}</td>
    <td><span class="cat-tag ${c.beats_single_factor ? 'up' : 'down'}">${
  c.beats_single_factor ? 'beats it' : 'loses'}</span></td>
  </tr>`).join('');

  const detail = (e.horizons || []).map((h) => `<details class="eval-h">
    <summary>${fmt(h.horizon_sessions, 0)}-session horizon: IC ${
  fmt(h.information_coefficient, 4)}, positive on ${fmt(h.ic_positive_share_pct, 0)}% of ${
  fmt(h.ic_dates, 0)} dates<i class="cal-caret" aria-hidden="true"></i></summary>
    <table class="data">
      <thead><tr><th>Score bucket</th><th class="num">n</th><th class="num">Mean excess</th>
        <th class="num">Hit rate</th><th class="num">95% interval</th></tr></thead>
      <tbody>${(h.buckets || []).filter((b) => b.n).map((b) => `<tr>
        <td class="name">${esc(b.bucket)}</td>
        <td class="num">${fmt(b.n, 0)}</td>
        <td class="num ${signClass(b.mean_pct)}">${b.mean_pct > 0 ? '+' : ''}${fmt(b.mean_pct, 2)}%</td>
        <td class="num">${fmt(b.hit_rate_pct, 1)}%</td>
        <td class="num muted">${b.ci95_pct
    ? `${fmt(b.ci95_pct[0], 2)} to ${fmt(b.ci95_pct[1], 2)}` : '—'}</td>
      </tr>`).join('')}</tbody>
    </table>
  </details>`).join('');

  return `<div class="panel span-all">
    <h2>${hg('Does the score work?')}${askPulse('evaluate')}</h2>
    <p class="sub">The screen's own trend-and-momentum score, replayed across
      ${fmt(e.sample_size, 0)} names of ${fmt(e.universe_total, 0)} at ${fmt(e.evaluation_dates, 0)}
      historical dates: ${fmt(e.observations, 0)} observations. Each score is computed only from
      bars that existed at the time, and returns are measured against the rest of the universe on
      the same day.</p>

    <div class="callout ${(e.comparison || []).some((c) => c.beats_single_factor) ? '' : 'warn'}">
      <strong>Result.</strong> ${esc(e.verdict || '')}</div>

    <table class="data" style="margin-top:var(--space-3)">
      <thead><tr><th>Horizon</th><th class="num">Composite</th><th class="num">Random</th>
        <th class="num">3-month return alone</th><th>vs single factor</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="caveat">${gloss(e.control_note || '')}</p>

    <div style="margin-top:var(--space-4)">${detail}</div>

    <p class="caveat">${gloss(e.interpretation || '')}</p>
    <div class="callout"><strong>What this cannot fix.</strong>
      <ul class="reasons">${(e.biases || []).map((b) => `<li>${esc(b)}</li>`).join('')}</ul></div>
  </div>`;
}

async function loadEvaluation() {
  if (STATE.evaluation) return;
  try {
    STATE.evaluation = await getJSON('/api/evaluate');
  } catch (err) {
    STATE.evaluation = { available: false, reason: err.message };
  }
  const host = document.getElementById('eval-host');
  if (host) { host.innerHTML = renderEvaluation(STATE.evaluation); revealPanels(host); }
}

/* Implied correlation and the expiry clock.
 *
 * Implied correlation is the number behind the dispersion trade: index vol
 * against the vol of its own parts. It is shown with its approximation stated
 * on the panel, not in a footnote, because the level is NOT CBOE's COR index
 * and quoting it as though it were would be the whole error.
 *
 * The expiry clock sits with it because both are about the same mechanics: how
 * much of what is priced is index-level hedging, and when that hedging stops
 * existing. */
const CORR_BAND_CLASS = { high: 'down', low: 'up', normal: 'flat' };

function renderCorrelation(c) {
  if (!c || !c.available) {
    return c ? `<div class="panel span2"><h2>${hg('Implied correlation')}</h2>
      <p class="sub">${esc(c.reason || 'Unavailable.')}</p></div>` : '';
  }
  const ex = c.expiries || {};
  const comps = (c.components || []).map((x) => `<tr>
    <td class="name"><button type="button" class="tkr" data-analyse="${esc(x.symbol)}"
      >${esc(x.symbol)}</button></td>
    <td class="num">${fmt(x.iv_pct, 1)}%</td>
    <td class="num muted">${fmt(x.weight_pct, 1)}%</td>
  </tr>`).join('');

  return `<div class="panel span2">
    <h2>${hg('Implied correlation')}${askPulse('impliedcorr')}</h2>
    <p class="sub">How much the market is paying for these names to move together.</p>
    <div class="fg-top" style="margin-top:var(--space-2)">
      <div>
        <div class="idx-lbl">Implied correlation</div>
        <div class="fg-score ${CORR_BAND_CLASS[c.band] || ''}" style="font-size: var(--t-d1)">${
  fmt(c.implied_correlation, 2)}</div>
        <div class="fg-label-lg ${CORR_BAND_CLASS[c.band] || ''}">${esc(c.band)}</div>
      </div>
      <div class="fg-hist-row" style="margin:0;flex:1 1 260px">
        <div class="fg-hbox"><div class="fg-hl">${esc(c.index)} implied vol</div>
          <div class="fg-hv">${fmt(c.index_iv_pct, 1)}%</div></div>
        <div class="fg-hbox"><div class="fg-hl">Components, weighted</div>
          <div class="fg-hv">${fmt(c.weighted_component_iv_pct, 1)}%</div></div>
      </div>
    </div>
    <p class="sc-note">${esc(c.plain || '')}</p>
    <p class="caveat">${esc(c.dispersion_note || '')}</p>

    ${ex.available ? `<div class="callout" style="margin-top:var(--space-3)">
      <strong>Expiry clock.</strong> ${esc(ex.note || '')}
      Next monthly expiry ${esc((ex.next_opex || {}).when_label || '')}${
  (ex.next_opex || {}).kind === 'witching' ? ' (quadruple witching)' : ''};
      VIX settles ${esc((ex.next_vix_expiry || {}).when_label || '')}. A Wednesday
      morning auction, not the Friday close.</div>` : ''}

    <details class="eval-h" style="margin-top:var(--space-3)">
      <summary>Components: ${fmt(c.components_used, 0)} names, weighted by ${
  esc(c.weighted_by)}<i class="cal-caret" aria-hidden="true"></i></summary>
      <table class="data">
        <thead><tr><th>Name</th><th class="num">ATM IV</th><th class="num">Weight</th></tr></thead>
        <tbody>${comps}</tbody>
      </table>
    </details>
    ${c.strained ? `<div class="callout warn">The identity returned ${fmt(c.implied_correlation_raw, 2)},
      above 1.0, which means this basket is not representing the index well right now.
      The clipped figure above is shown, but treat the level as unreliable today.</div>` : ''}
    <p class="caveat">${gloss(c.method || '')}</p>
  </div>`;
}

async function loadCorrelation() {
  if (STATE.correlation) return;
  try {
    STATE.correlation = await getJSON('/api/implied-correlation');
  } catch (err) {
    STATE.correlation = { available: false, reason: err.message };
  }
  if (STATE.market) renderMarket(STATE.market);
}

/* Portfolio-level risk.
 *
 * The ledger reports each trade alone, which is right for managing a position
 * and wrong for managing a book. This is the view that says whether several
 * tickets are one bet.
 *
 * Two numbers are kept deliberately apart. The diversification ratio measures
 * how much the holdings actually cancel each other; sector weight measures how
 * much they share an exposure. A book can look clean on the first and be one
 * decision away from a common shock on the second — nine small-cap biotechs
 * with a highest pairwise correlation of 0.52 and 60% of the book in healthcare
 * is exactly that case. Collapsing them into one "risk score" would hide it. */
function renderPortfolioRisk(r) {
  if (!r) return '';
  if (!r.available) {
    return `<div class="panel span-all"><h2>${hg('Book-level risk')}</h2>
      <p class="sub">${esc(r.reason || 'Unavailable.')}</p></div>`;
  }
  const dr = r.diversification_ratio;
  const drClass = dr === null ? 'flat' : dr < 1.15 ? 'down' : dr >= 1.5 ? 'up' : 'flat';

  const positions = (r.positions || []).map((p) => `<tr>
    <td class="name"><button type="button" class="tkr" data-analyse="${esc(p.symbol)}"
      >${esc(p.symbol)}</button></td>
    <td class="name dim">${esc(p.sector || '')}</td>
    <td class="num">${fmt(p.weight_pct, 1)}%</td>
    <td class="num muted">${p.risk_contribution_pct === undefined
    ? '—' : fmt(p.risk_contribution_pct, 1) + '%'}</td>
  </tr>`).join('');

  const pairs = (r.top_pairs || []).slice(0, 6).map((p) => `<tr>
    <td class="name">${esc(p.a)} / ${esc(p.b)}</td>
    <td class="num ${Math.abs(p.correlation) >= 0.7 ? 'down' : ''}">${
  p.correlation > 0 ? '+' : ''}${fmt(p.correlation, 2)}</td>
  </tr>`).join('');

  return `<div class="panel span-all">
    <h2>${hg('Book-level risk')}${askPulse('bookrisk')}</h2>
    <p class="sub">${fmt(r.names, 0)} names, ${usd(r.gross_exposure)} gross. The ledger above
      reports each trade on its own; this asks whether they are separate bets.</p>

    <div class="fg-hist-row" style="margin-top:var(--space-3)">
      <div class="fg-hbox">
        <div class="fg-hl">Diversification ratio</div>
        <div class="fg-hv ${drClass}">${dr === null ? '—' : fmt(dr, 2)}</div>
        <div class="sc-sub">1.0 means nothing is cancelling</div>
      </div>
      <div class="fg-hbox">
        <div class="fg-hl">Book volatility</div>
        <div class="fg-hv">${r.portfolio_vol_pct === null ? '—' : fmt(r.portfolio_vol_pct, 0) + '%'}</div>
        <div class="sc-sub">vs ${fmt(r.weighted_avg_vol_pct, 0)}% average of the parts</div>
      </div>
      <div class="fg-hbox">
        <div class="fg-hl">Effective positions</div>
        <div class="fg-hv">${r.effective_positions === null ? '—' : fmt(r.effective_positions, 1)}</div>
        <div class="sc-sub">of ${fmt(r.names, 0)} held</div>
      </div>
      <div class="fg-hbox">
        <div class="fg-hl">Largest / top 3</div>
        <div class="fg-hv">${fmt(r.largest_weight_pct, 0)}% / ${fmt(r.top3_weight_pct, 0)}%</div>
        <div class="sc-sub">of gross exposure</div>
      </div>
    </div>

    <div class="callout ${r.concentrated ? 'warn' : ''}" style="margin-top:var(--space-3)">
      <strong>${r.concentrated ? 'This is one bet.' : 'Correlation read.'}</strong>
      ${esc(r.verdict || '')}</div>

    ${r.sector_warning ? `<div class="callout warn"><strong>Shared exposure.</strong>
      ${esc(r.sector_warning)}</div>` : ''}

    <div class="grid c2" style="margin-top:var(--space-4)">
      <div>
        <h3>${hg('Where the money and the risk sit')}</h3>
        <table class="data">
          <thead><tr><th>Name</th><th>Sector</th><th class="num">Weight</th>
            <th class="num">Risk share</th></tr></thead>
          <tbody>${positions}</tbody>
        </table>
      </div>
      <div>
        <h3>${hg('Most correlated pairs')}</h3>
        <table class="data">
          <thead><tr><th>Pair</th><th class="num">${fmt(r.window_sessions, 0)}-day correlation</th></tr></thead>
          <tbody>${pairs || '<tr><td colspan="2">Not enough overlapping history.</td></tr>'}</tbody>
        </table>
        <h3 style="margin-top:var(--space-4)">${hg('Sector exposure')}</h3>
        <table class="data">
          <tbody>${(r.sectors || []).map((x) => `<tr>
            <td class="name">${esc(x.sector)}</td>
            <td style="width:50%">${regimeBar((x.weight_pct - 50) * 2)}</td>
            <td class="num">${fmt(x.weight_pct, 0)}%</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>
    </div>

    <div class="callout" style="margin-top:var(--space-4)"><strong>Summed stop risk
      ${usd(r.summed_stop_risk)}.</strong> ${esc(r.summed_risk_note || '')}</div>
    <p class="caveat">${gloss(r.method || '')}</p>
  </div>`;
}

async function loadPortfolioRisk() {
  if (STATE.bookRisk) return;
  try {
    STATE.bookRisk = await getJSON(
      `/api/portfolio-risk?book=${encodeURIComponent(STATE.trackerBook || 'balanced')}`);
  } catch (err) {
    STATE.bookRisk = { available: false, reason: err.message };
  }
  const host = document.getElementById('book-risk-host');
  if (host) { host.innerHTML = renderPortfolioRisk(STATE.bookRisk); revealPanels(host); }
}

function renderSentiment(f) {
  if (!f || !f.available) return '';
  const h = f.history || {};
  const pos = Math.max(0, Math.min(100, f.score));

  const rows = (f.components || []).filter((c) => c.score !== null).map((c) => {
    const t = (c.label_text || '').toLowerCase();
    const band = t.includes('greed') ? 'up' : t.includes('fear') ? 'down' : 'flat';
    return `<div class="fg-comp">
      <div class="fg-comp-head">
        <span class="fg-comp-name"><dfn class="gloss-term" tabindex="0"
          data-def="${esc(c.note)}">${esc(c.label)}</dfn></span>
        <span class="fg-comp-weight">Weight ${fmt(c.weight_pct, 0)}%</span>
        <span class="fg-comp-score ${band}">${fmt(c.score, 0)}<span class="fg-of"> / 100</span></span>
      </div>
      <p class="fg-comp-q">${esc(c.question || '')}</p>
      <div class="fg-comp-bar"><i class="fg-comp-fill ${band}" style="width:${
  Math.max(0, Math.min(100, c.score))}%"></i></div>
      <div class="fg-comp-foot">
        <span class="fg-comp-band ${band}">${esc(c.label_text || '')}</span>
        <span class="fg-comp-reading">${esc(c.reading || '')}</span>
      </div>
      ${c.detail ? `<p class="fg-comp-under"><span>Underlying:</span> ${esc(c.detail)}.</p>` : ''}
    </div>`;
  }).join('');

  const hist = (key, label) => {
    const x = h[key];
    if (!x) return '';
    return `<div class="fg-hbox">
      <div class="fg-hl">${label}</div>
      <div class="fg-hrow"><span class="fg-hv">${fmt(x.score, 0)}</span>${fgDelta(x)}</div>
    </div>`;
  };

  return `<div class="panel span-all fg-panel">
    <h2>${hg('Fear & Greed')}${askPulse('feargreed')}</h2>
    <div class="fg-top">
      <div>
        <div class="idx-lbl">Current reading</div>
        <div class="fg-score ${FG_CLASS[f.label] || ''}">${fmt(f.score, 0)}</div>
        <div class="fg-label-lg ${FG_CLASS[f.label] || ''}">${esc(f.label)}</div>
      </div>
      <div class="fg-meta">
        <div>Data quality: <strong class="${f.data_quality === 'healthy' ? 'pos' : 'warn'}">${
  esc(f.data_quality || '')}</strong> · ${fmt(f.inputs_used, 0)} of ${fmt(f.inputs_total, 0)} inputs</div>
        <div>Methodology <strong>${esc(f.methodology || '')}</strong></div>
      </div>
    </div>

    <div class="fg-scale">
      <div class="fg-scale-bar"><i class="fg-marker" style="left:${pos}%"></i></div>
      <div class="fg-scale-labels">
        <span>Extreme fear</span><span>Fear</span><span>Neutral</span><span>Greed</span><span>Extreme greed</span>
      </div>
    </div>

    <div class="fg-hist-row">
      ${hist('prev_close', 'vs. prev close')}
      ${hist('week', 'vs. 1 week ago')}
      ${hist('month', 'vs. 1 month ago')}
    </div>

    <div class="idx-lbl" style="margin-top:var(--space-5)">Component breakdown</div>
    <div class="fg-comps">${rows}</div>

    <p class="caveat">${esc(f.caveat || '')}</p>
    <p class="caveat">${gloss(f.method || '')}</p>
  </div>`;
}

/* Written sector / index reads.
 *
 * One shared drawer rather than a drawer per row: only one can be open at a
 * time anyway, and eleven collapsed containers each holding a paid, unfetched
 * request is eleven things to keep in sync for no benefit.
 *
 * The board itself never waits on this. Eleven rows of arithmetic render
 * instantly; this is a model call for the one row someone clicked, and the
 * mechanical summary sentence is already on the card while it loads. */
const SECTOR_STANCE_CLASS = { constructive: 'up', cautious: 'down', 'two-sided': 'flat' };

function sectorReadButton(symbol) {
  return `<button type="button" class="sector-read-btn" data-sector-read="${esc(symbol)}"
    >Sector Read <span aria-hidden="true">\u203a</span></button>`;
}

function renderSectorRead(host) {
  const el = document.getElementById(host);
  if (!el) return;
  const r = STATE.sectorRead;
  if (!r) { el.innerHTML = ''; return; }
  if (r.loading) {
    el.innerHTML = `<div class="panel"><h2>${esc(r.symbol)}. Reading the board…</h2>
      <p class="sub">Writing from the levels and returns for ${esc(r.symbol)}.</p></div>`;
    return;
  }
  if (!r.available) {
    el.innerHTML = `<div class="panel"><h2>${esc(r.symbol)} read</h2>
      ${r.summary ? `<p class="sub">${esc(r.summary)}</p>` : ''}
      <div class="callout">${esc(r.reason || 'No written read available.')}</div></div>`;
    return;
  }
  const row = r.row || {};
  el.innerHTML = `<div class="panel sector-read">
    <div class="earn-brief-head">
      <h2>${esc(r.symbol)}${row.name ? ` \u00b7 ${esc(row.name)}` : ''} read</h2>
      <div style="display:flex;gap:var(--space-2);align-items:center">
        ${r.stance ? `<span class="earn-stance ${SECTOR_STANCE_CLASS[r.stance] || 'flat'}"
          >${esc(r.stance)}</span>` : ''}
        <button type="button" class="bulk-btn" data-sector-read-close>Close</button>
      </div>
    </div>
    ${r.headline ? `<p class="earn-brief-lede">${esc(r.headline)}</p>` : ''}
    <div class="earn-brief">${briefProse(r.paragraphs)}</div>
    <p class="caveat">${gloss(r.method || '')}</p>
    <p class="caveat">${esc(r.disclaimer || '')}</p>
  </div>`;
  el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

async function openSectorRead(symbol, host) {
  const sym = (symbol || '').toUpperCase();
  const cached = STATE.sectorReadCache[sym];
  if (cached) { STATE.sectorRead = cached; renderSectorRead(host); return; }
  STATE.sectorRead = { loading: true, symbol: sym };
  renderSectorRead(host);
  try {
    const data = await getJSON(`/api/sectors/${encodeURIComponent(sym)}/read`);
    data.symbol = data.symbol || sym;
    STATE.sectorReadCache[sym] = data;
    if ((STATE.sectorRead || {}).symbol !== sym) return;   // a later click won
    STATE.sectorRead = data;
  } catch (err) {
    STATE.sectorRead = { symbol: sym, available: false, reason: err.message };
  }
  renderSectorRead(host);
}

/* Major index ETFs as cards — the same board and the same levels, three or four
 * instruments instead of eleven, so cards read better than a table. */
function renderIndexBoard(b) {
  if (!b || !b.available) return '';
  const cards = (b.rows || []).filter((r) => r.available).map((r) => {
    const cls = SECTOR_TREND_CLASS[r.trend] || 'flat';
    return `<div class="idx-card ${cls}">
      <div class="idx-card-head">
        <div>
          <div class="idx-sym">${esc(r.symbol)}</div>
          <div class="idx-name">${esc(r.name)}</div>
        </div>
        <span class="sec-trend ${cls}">${esc(SECTOR_TREND_LABEL[r.trend] || r.trend)}</span>
      </div>
      <div class="idx-nums">
        <div><span class="idx-lbl">Price</span><span class="idx-val">$${fmt(r.price, 2)}</span></div>
        <div><span class="idx-lbl">Bull above</span><span class="idx-val pos">$${fmt(r.bull_above, 2)}</span></div>
        <div><span class="idx-lbl">Bear below</span><span class="idx-val neg">$${fmt(r.bear_below, 2)}</span></div>
      </div>
      <p class="idx-summary">${esc(r.summary || '')}</p>
      ${sectorReadButton(r.symbol)}
    </div>`;
  }).join('');
  if (!cards) return '';
  return `<div class="panel span2">
    <h2>${hg('Major ETFs')}${askPulse('sectorboard')}</h2>
    <p class="sub">Each index ETF against the prior session's high and low. The same two
      prices the sector board uses, asked of the market as a whole.</p>
    <div class="idx-cards">${cards}</div>
    <div id="index-read-host"></div>
    <p class="caveat">${gloss(b.method || '')}</p>
  </div>`;
}

/* The sector board: each SPDR sector against its own overnight levels.
 *
 * The levels are the prior completed session's high and low, which is why the
 * table can state them as plain prices a reader can check on any chart rather
 * than as the output of a model.
 *
 * Trend and rotation sit in separate columns on purpose. A sector can be above
 * yesterday's high while still losing ground to the index all month — a sector
 * rising inside a market rising faster, which is not where money is going.
 * Collapsing both into one verdict would hide precisely that case.
 *
 * Rotation here is a verdict, not a second copy of the relative-strength table
 * below it: that panel already carries RS over four windows, and repeating those
 * numbers would be two places to read the same thing and one place for them to
 * disagree. */
const SECTOR_TREND_LABEL = {
  uptrend: 'Overnight Uptrend', downtrend: 'Overnight Downtrend', neutral: 'Neutral',
};
const SECTOR_TREND_CLASS = { uptrend: 'up', downtrend: 'down', neutral: 'flat' };
const ROTATION_CLASS = { in: 'up', out: 'down', turning: 'warn', neutral: 'flat', unknown: 'flat' };

function renderSectorBoard(b) {
  if (!b || !b.available) return '';
  const c = b.counts || {};
  const rows = (b.rows || []).map((r) => {
    if (!r.available) {
      return `<tr><td class="name"><strong>${esc(r.symbol)}</strong></td>
        <td class="name">${esc(r.name)}</td>
        <td colspan="7" class="muted">${esc(r.reason || 'Unavailable')}</td></tr>`;
    }
    const tcls = SECTOR_TREND_CLASS[r.trend] || 'flat';
    const rot = r.rotation || {};
    return `<tr>
      <td class="name"><button type="button" class="tkr" data-analyse="${esc(r.symbol)}"
        >${esc(r.symbol)}</button></td>
      <td class="name">${esc(r.name)}</td>
      <td><span class="sec-trend ${tcls}">${esc(SECTOR_TREND_LABEL[r.trend] || r.trend)}</span>${
  r.trend === 'neutral' ? ''
    : r.intact ? '<span class="sec-note" title="Same state as the prior session. The trend has held">intact</span>'
      : r.changed ? '<span class="sec-note flip" title="This state is new as of today; the prior session was different">new today</span>' : ''}</td>
      <td class="num">$${fmt(r.price, 2)}</td>
      <td class="num pos">$${fmt(r.bull_above, 2)}</td>
      <td class="num neg">$${fmt(r.bear_below, 2)}</td>
      <td class="num ${signClass(r.to_break_pct)}">${fmtPct(r.to_break_pct, 2)}</td>
      <td class="num ${signClass(r.to_breakdown_pct)}">${fmtPct(r.to_breakdown_pct, 2)}</td>
      <td class="name"><span class="sec-rot ${ROTATION_CLASS[rot.state] || 'flat'}"
        title="${esc(rot.note || '')}">${esc(rot.label || '—')}</span></td>
      <td>${sectorReadButton(r.symbol)}</td>
    </tr>`;
  }).join('');

  return `<div class="grid c2 gap">
    <div class="panel span2">
      <h2>${hg('Sector board')}${askPulse('sectorboard')}</h2>
      <p class="sub">Every SPDR sector against the prior session's high and low. The two
        prices the overnight and pre-market session traded around. Above the high is an
        uptrend, below the low a downtrend, between them undecided.
        <strong>${c.uptrend || 0}</strong> up, <strong>${c.downtrend || 0}</strong> down,
        <strong>${c.neutral || 0}</strong> undecided.</p>
      <div class="table-scroll">
      <table class="data sector-board">
        <thead><tr>
          <th>ETF</th><th>Sector</th><th>Trend</th>
          <th class="num">Price</th><th class="num">Bull above</th><th class="num">Bear below</th>
          <th class="num">${hg('Δ to break')}</th><th class="num">${hg('Δ to breakdown')}</th>
          <th>${hg('Rotation')}</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
      </div>
      <p class="caveat">Δ to break is how far price sits from the level it must clear;
        Δ to breakdown how far above the level it must hold. Negative means price is the
        wrong side of that level already.</p>
      <p class="caveat">${gloss(b.method || '')}</p>
      <div id="sector-read-host"></div>
    </div>
  </div>
`;
}

/* ------------------------------------------------- sector relative rotation
 *
 * Where each sector sits against the index on two axes, with a tail showing
 * where it came from. The tail is what makes it worth drawing: a dot in
 * "Leading" says a sector is strong, and only the tail says whether it has just
 * arrived or is on its way out.
 */
const ROT_QUADS = {
  leading: { label: 'Leading', cls: 'up',
    tip: 'Outperforming the index and still gaining ground. The strongest quadrant, and the one sectors leave first.' },
  weakening: { label: 'Weakening', cls: 'warn',
    tip: 'Still outperforming, but the lead is shrinking. Sectors usually pass through here on the way out of Leading.' },
  lagging: { label: 'Lagging', cls: 'down',
    tip: 'Underperforming and still losing ground. The weakest quadrant.' },
  improving: { label: 'Improving', cls: 'accent',
    tip: 'Still underperforming, but closing the gap. Sectors pass through here on the way back to Leading, or turn round and drop back to Lagging.' },
};

function rotationQuadChip(q) {
  const meta = ROT_QUADS[q] || { label: q, cls: '', tip: '' };
  return `<span class="rot-quad ${meta.cls}" title="${esc(meta.tip)}">${meta.label}</span>`;
}

function renderRotation(r) {
  if (!r) return '';
  if (r.error) {
    return `<div class="panel span2"><h2>${hg('Sector rotation')}</h2>
      <p class="sub">${esc(r.error)}</p></div>`;
  }
  const secs = r.sectors || [];
  const counts = r.counts || {};
  const crossed = r.crossed || [];
  const p = r.params || {};

  const order = ['leading', 'weakening', 'improving', 'lagging'];
  const tally = order.map((q) => `<div class="rot-tally">
    ${rotationQuadChip(q)}<strong>${counts[q] || 0}</strong>
    <span>${(secs.filter((x) => x.quadrant === q).map((x) => esc(x.symbol)).join(' ')) || '—'}</span>
  </div>`).join('');

  const rows = secs.map((x) => `<tr>
    <td class="name"><button type="button" class="tkr" data-analyse="${esc(x.symbol)}"
      title="Open the full analysis for ${esc(x.symbol)}">${esc(x.symbol)}</button>
      <div style="color:var(--ink-muted);font-size:var(--t-caption)">${esc(x.name)}</div></td>
    <td>${rotationQuadChip(x.quadrant)}</td>
    <td class="${signClass((x.strength || 100) - 100)}">${fmt(x.strength, 2)}</td>
    <td class="${signClass((x.momentum || 100) - 100)}">${fmt(x.momentum, 2)}</td>
    <td class="${signClass(x.d_strength)}">${fmt(x.d_strength, 2)}</td>
    <td class="${signClass(x.d_momentum)}">${fmt(x.d_momentum, 2)}</td>
    <td>${x.quadrant === x.previous_quadrant ? '<span style="color:var(--ink-muted)">—</span>'
    : `${rotationQuadChip(x.previous_quadrant)} <span style="color:var(--ink-muted)">→</span>`}</td>
  </tr>`).join('');

  return `<div class="panel span2 gap">
    <h2>${hg('Sector rotation')}</h2>
    <p class="sub">All eleven sectors against ${esc(r.benchmark)} on two axes, both centred
      on 100: <strong>relative strength</strong> across, <strong>relative momentum</strong> up.
      Each sector trails ${fmt(r.tail, 0)} weeks of history, so you can see not just where it
      is but which way it is heading. Sectors tend to travel clockwise.
      Improving → Leading → Weakening → Lagging. Though plenty turn back
      without completing the loop.</p>

    <div class="rot-tallies">${tally}</div>

    <div id="chart-rotation" class="chart-host"></div>

    ${crossed.length ? `<div class="callout" style="margin-top:12px">
      <strong>Crossed a boundary this week:</strong>
      ${crossed.map((c) => `${esc(c.symbol)} ${esc(c.from)} → ${esc(c.to)}`).join(' · ')}.
      A crossing is the earliest thing this chart says, and also the least reliable.
      A sector sitting near a line can cross back next week without anything having changed.
    </div>` : ''}

    <table class="data" style="margin-top:12px">
      <thead><tr><th>Sector</th><th>Quadrant</th><th>Strength</th><th>Momentum</th>
        <th>Δ strength</th><th>Δ momentum</th><th>Moved from</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>

    <p class="caveat">Tails are smoothed over ${fmt(p.smooth, 0)} weeks and drawn as curves.
      Unsmoothed, each sector jumped about a quarter of the chart per week and the tails
      crossed into a tangle. The cost is lag: a sector that turns shows it here a week or two
      after it turned, so read this for rotation, not for the bar it started on.</p>
    <p class="caveat">${gloss('Both axes are z-scores against each sector\u2019s own last '
    + fmt(p.norm_window, 0) + ' weeks, so 102 means "unusual for this sector recently", not '
    + '"unusual in absolute terms". A sector that has quietly outperformed for the whole '
    + 'window reads as ordinary, because the window has absorbed it. Weekly bars, because '
    + 'daily rotation is mostly noise. The tail thrashes across the boundaries on '
    + 'nothing.')}</p>
    <p class="caveat">This is not an RRG&reg;, and the numbers are not the JdK RS-Ratio and
      RS-Momentum. Those are Julius de Kempenaer\u2019s, trademarked, and their exact
      normalisation is not published. The quadrant layout is the same because the layout is
      the useful part; the arithmetic behind it is
      ${esc('rs / SMA(rs, ' + p.lookback + ')')}, z-scored, which is stated in full in the
      module so it can be argued with. Readings will not tie out against StockCharts.</p>
  </div>`;
}

/* ==================================================== the chart workspace
 *
 * A place to work rather than a page to read, which is the whole reason it is a
 * separate tab: the chart gets the viewport instead of 420px in a column of
 * panels, and the controls sit around it instead of above it.
 *
 * Almost nothing here is new capability. Optic already had fibs, support and
 * resistance, supply and demand zones, volume by price, insider marks, the
 * moving-average families, the indicator catalogue and the pattern engine —
 * scattered down the Swing tab as a stack of checkboxes. This gives them a
 * toolbar and a canvas. The one genuinely new thing is drawings.
 */

/* The toolbar. Each entry is a menu, and each menu is a set of overlay toggles
 * that already existed. Grouped the way someone reaches for them rather than the
 * way they are implemented — "is this level real" is one question whether the
 * answer comes from a pivot, a Fibonacci ratio or a volume shelf. */
const WS_MENUS = [
  { id: 'fibs', label: 'Fibs', items: ['fib'] },
  { id: 'trends', label: 'Trends', items: ['trends', 'sr', 'zones'] },
  { id: 'indicators', label: 'Indicators', items: ['sma20', 'sma50', 'sma200', 'ema9', 'ema21', 'ema50'], manage: true },
  { id: 'volume', label: 'Volume', items: ['vol', 'vbp'] },
  { id: 'events', label: 'Events', items: ['insiders', 'sessions'] },
];

/* Which global flag each toggle drives. The flags are the ones the Swing chart
 * already uses, so a toggle here moves that chart too — which is the point of
 * sharing the settings rather than duplicating them. */
const WS_FLAGS = {
  fib: () => showFib, sr: () => showSR, zones: () => showZones,
  vbp: () => showVbp, vol: () => showVol, insiders: () => showInsiders,
  sma20: () => seriesShown('sma20'), sma50: () => seriesShown('sma50'),
  sma200: () => seriesShown('sma200'),
  ema9: () => seriesShown('ema9'), ema21: () => seriesShown('ema21'),
  ema50: () => seriesShown('ema50'),
  trends: () => showTrends,
  sessions: () => showSessions,
};

function wsOverlayOn(id) {
  const get = WS_FLAGS[id];
  return get ? !!get() : false;
}

/** The clickable legend that sits over the top-left of the chart.
 *
 * Modelled on the reference: one row per active overlay, its parameters in
 * brackets, its current value, and controls to hide or remove it. The value is
 * the part that earns the space — it is the number a reader was previously
 * hovering the line or cross-referencing a tile to find. */
function wsLegend(ps) {
  const rows = [];
  const last = (arr) => {
    if (!Array.isArray(arr)) return null;
    for (let i = arr.length - 1; i >= 0; i -= 1) {
      if (Number.isFinite(arr[i])) return arr[i];
    }
    return null;
  };
  const add = (id, valueSeries, detail) => {
    if (!wsOverlayOn(id)) return;
    const st = overlayStyle(id);
    const v = last(valueSeries);
    rows.push(`<div class="ws-leg-row" data-ws-leg="${esc(id)}">
      <span class="ws-leg-name" style="color:${st.color}">${esc(st.label)}${
  detail ? ` <span class="ws-leg-args">(${esc(detail)})</span>` : ''}</span>
      ${v === null ? '' : `<span class="ws-leg-val">${fmt(v, 2)}</span>`}
      <button type="button" class="ws-leg-btn" data-ws-hide="${esc(id)}"
        title="Hide ${esc(st.label)}">&#128065;</button>
      <button type="button" class="ws-leg-btn" data-ws-off="${esc(id)}"
        title="Remove ${esc(st.label)}">&times;</button>
    </div>`);
  };

  const p = (id) => overlayStyle(id).params || {};
  add('sma20', ps.sma20, `${p('sma20').length}, ${p('sma20').offset}, ${p('sma20').source}`);
  add('sma50', ps.sma50, `${p('sma50').length}, ${p('sma50').offset}, ${p('sma50').source}`);
  add('sma200', ps.sma200, `${p('sma200').length}, ${p('sma200').offset}, ${p('sma200').source}`);
  add('ema9', ps.ema9, `${p('ema9').length}`);
  add('ema21', ps.ema21, `${p('ema21').length}`);
  add('ema50', ps.ema50, `${p('ema50').length}`);
  add('vol', ps.volume, `${p('vol').length || 20}, SMA`);
  add('fib', null, 'retracement');
  add('sr', null, 'pivots');
  add('zones', null, 'supply / demand');
  add('vbp', null, 'by price');
  add('insiders', null, 'form 4');
  add('trends', null, 'auto');

  /* Collapsible.
   *
   * The legend sits ON the chart, so with a full indicator set it covers the
   * top-left corner — which on a rising series is exactly where the reader is
   * looking. Collapsed it keeps the one thing worth having at all times (which
   * symbol, which timeframe) plus a count, so nothing is hidden without a trace.
   *
   * The header is the toggle rather than a separate control: it is already the
   * widest target in the box and a 12px chevron beside it would be the smaller,
   * fiddlier version of the same thing.
   */
  const n = rows.length;
  const draws = wsDrawings().length;
  /* Rows are laid out horizontally in narrow mode by CSS, not by rendering
   * different markup — same DOM, so collapsing and expanding behaves identically
   * at either width and there is only one thing to keep correct. */
  return `<div class="ws-legend${wsLegendOpen ? '' : ' collapsed'}">
    <button type="button" class="ws-leg-title" data-ws-leg-toggle
      aria-expanded="${wsLegendOpen}"
      title="${wsLegendOpen ? 'Collapse' : 'Expand'} the indicator list">
      <span class="ws-leg-caret">${wsLegendOpen ? '&#9662;' : '&#9656;'}</span>
      ${esc(STATE.chartSymbol || '')}
      <span class="ws-leg-args">${esc(chartInterval)} · ${esc(chartRange)}</span>
      ${wsLegendOpen ? '' : `<span class="ws-leg-count">${n} overlay${
  n === 1 ? '' : 's'}${draws ? ` · ${draws} drawing${draws === 1 ? '' : 's'}` : ''}</span>`}
    </button>
    ${wsLegendOpen ? `<div class="ws-leg-body">
      ${rows.join('') || '<div class="ws-leg-empty">No overlays. Add one from the toolbar</div>'}
      <div class="ws-leg-row ws-leg-static">Drawings
        <span class="ws-leg-val" data-ws-draw-count>${draws}</span></div>
    </div>` : ''}
  </div>`;
}

/* The tool rail. Nine tools, chosen over the reference's twenty on the grounds
 * that six that feel right beat twenty that do not — the core annotation set
 * plus the three measurement tools, which is what a terminal actually needs.
 * Each is a real interaction with drag handles and persistence, not an icon. */
const WS_TOOLS = [
  { id: 'cursor', label: 'Select', glyph: '&#10530;', hint: 'Select and move a drawing' },
  { id: 'trend', label: 'Trend line', glyph: '&#9585;', hint: 'A line between two points' },
  { id: 'ray', label: 'Ray', glyph: '&#8599;', hint: 'A line that extends past the second point' },
  { id: 'hline', label: 'Level', glyph: '&#9473;', hint: 'A horizontal price level' },
  { id: 'vline', label: 'Date line', glyph: '&#9474;', hint: 'A vertical line marking one bar' },
  { id: 'channel', label: 'Channel', glyph: '&#8801;', hint: 'Two parallel trend lines' },
  { id: 'rect', label: 'Rectangle', glyph: '&#9633;', hint: 'A box around a region' },
  { id: 'fibdraw', label: 'Fib retracement', glyph: '&#9776;', hint: 'Fib levels between two points' },
  { id: 'fibext', label: 'Fib extension', glyph: '&#9783;', hint: 'Projected levels beyond the move' },
  { id: 'pitchfork', label: 'Pitchfork', glyph: '&#9868;', hint: 'Andrews pitchfork from three pivots' },
  { id: 'arrow', label: 'Arrow', glyph: '&#8594;', hint: 'A pointer at something' },
  { id: 'text', label: 'Text', glyph: 'T', hint: 'A note on the chart' },
  { id: 'ruler', label: 'Measure', glyph: '&#8596;', hint: 'Price and date distance between two points' },
  { id: 'rr', label: 'Risk / reward', glyph: '&#9707;', hint: 'Entry, stop and target as a box' },
  { id: 'position', label: 'Position size', glyph: '&#8721;', hint: 'Shares to buy for a given risk' },
];

function wsToolRail() {
  return `<div class="ws-rail" role="toolbar" aria-label="Drawing tools">
    ${WS_TOOLS.map((t) => `<button type="button" class="ws-tool${
  wsTool === t.id ? ' on' : ''}" data-ws-tool="${t.id}" title="${esc(t.hint)}"
      aria-pressed="${wsTool === t.id}">${t.glyph}</button>`).join('')}
    <div class="ws-rail-gap"></div>
    <button type="button" class="ws-tool" data-ws-undo
      ${wsUndoStack.length ? '' : 'disabled'}
      title="Undo (${navigator.platform.startsWith('Mac') ? '\u2318Z' : 'Ctrl+Z'})">&#8630;</button>
    <button type="button" class="ws-tool" data-ws-redo
      ${wsRedoStack.length ? '' : 'disabled'}
      title="Redo (${navigator.platform.startsWith('Mac') ? '\u21e7\u2318Z' : 'Ctrl+Y'})">&#8631;</button>
    <button type="button" class="ws-tool" data-ws-clear-draw
      ${wsDrawings().length ? '' : 'disabled'}
      title="Delete every drawing on this symbol">&#128465;</button>
  </div>`;
}

function wsToolbar() {
  return `<div class="ws-toolbar">
    ${WS_MENUS.map((m) => {
    const activeCount = m.items.filter(wsOverlayOn).length;
    return `<div class="ws-menu">
      <button type="button" class="ws-menu-btn${activeCount ? ' on' : ''}"
        data-ws-menu="${m.id}" aria-expanded="${wsMenuOpen === m.id}">
        ${esc(m.label)}${activeCount ? ` <span class="ws-count">${activeCount}</span>` : ''}
      </button>
      ${wsMenuOpen === m.id ? `<div class="ws-menu-pop">
        ${m.items.map((id) => {
    const st = overlayStyle(id);
    return `<label class="ws-opt">
          <input type="checkbox" data-ws-opt="${esc(id)}"${wsOverlayOn(id) ? ' checked' : ''}>
          <span class="ws-swatch" style="background:${st.color}"></span>
          <span>${esc(st.label)}</span>
        </label>`;
  }).join('')}
        ${m.manage ? `<button type="button" class="ws-manage" data-ws-manage>
          Manage indicators…</button>` : ''}
      </div>` : ''}
    </div>`;
  }).join('')}
    <div class="ws-toolbar-gap"></div>
    ${rangePills(CHART_INTERVALS, chartInterval, 'data-ws-interval', 'Interval')}
    ${rangePills(CHART_RANGES, chartRange, 'data-ws-range', 'Range')}
    ${wsWindow ? `<button type="button" class="ws-menu-btn ws-zoom-reset"
      data-ws-zoom-reset title="Back to the ${esc(chartRange)} range">Reset zoom</button>` : ''}
    <button type="button" class="ws-menu-btn${chartMode === 'candle' ? ' on' : ''}"
      data-ws-mode="${chartMode === 'candle' ? 'line' : 'candle'}">${
  chartMode === 'candle' ? 'Candles' : 'Line'}</button>
  </div>`;
}

/* ---------------------------------------------------------------- drawings
 *
 * Stored per symbol in localStorage, as data rather than as pixels: each drawing
 * keeps the bar index and the price it was anchored to, so it stays attached to
 * the same place on the chart when the range, interval or window size changes.
 * Storing screen coordinates was the alternative and it would put every drawing
 * in the wrong place the first time the panel was resized.
 */
const WS_DRAW_KEY = 'optic.chart.drawings.v1';
let wsTool = 'cursor';
let wsMenuOpen = null;
let wsDrawStore = {};
let wsSelected = null;
try {
  const saved = JSON.parse(localStorage.getItem(WS_DRAW_KEY) || '{}');
  if (saved && typeof saved === 'object') wsDrawStore = saved;
} catch (e) { /* private mode, or hand-edited storage */ }

function wsDrawings() {
  return wsDrawStore[STATE.chartSymbol || ''] || [];
}

function wsSaveDrawings(list) {
  wsDrawStore[STATE.chartSymbol || ''] = list;
  try { localStorage.setItem(WS_DRAW_KEY, JSON.stringify(wsDrawStore)); }
  catch (e) { /* private mode: the drawings live for the session only */ }
}


/* Which global each workspace toggle sets, and where it is remembered. Kept as
 * one table rather than an if-chain so the workspace toolbar, the Swing
 * checkboxes and the indicator dialog cannot disagree about what a toggle does. */
const WS_SETTERS = {
  fib: (on) => { showFib = on; storeFlag(SHOW_FIB_KEY, on); },
  sr: (on) => { showSR = on; storeFlag(SHOW_SR_KEY, on); },
  zones: (on) => { showZones = on; storeFlag(SHOW_ZONES_KEY, on); },
  vbp: (on) => { showVbp = on; storeFlag(SHOW_VBP_KEY, on); },
  vol: (on) => { showVol = on; storeFlag(SHOW_VOL_KEY, on); },
  insiders: (on) => { showInsiders = on; storeFlag(SHOW_INS_KEY, on); },
  sessions: (on) => { showSessions = on; storeFlag(SHOW_SESSIONS_KEY, on); },
  trends: (on) => {
    showTrends = on; storeFlag(SHOW_TRENDS_KEY, on);
    // Its own endpoint, fetched only when asked for — fitting every pivot pair
    // over a year is real work and most sessions never turn this on.
    if (on) loadTrendlines(STATE.view === 'chart' ? STATE.chartSymbol : STATE.ticker);
  },
  // Each average has its own switch now. See setSeriesFlag: it also keeps the
  // family flag in step, so anything asking "are moving averages on?" still
  // gets a true answer.
  sma20: (on) => setSeriesFlag('sma20', on),
  sma50: (on) => setSeriesFlag('sma50', on),
  sma200: (on) => setSeriesFlag('sma200', on),
  ema9: (on) => setSeriesFlag('ema9', on),
  ema21: (on) => setSeriesFlag('ema21', on),
  ema50: (on) => setSeriesFlag('ema50', on),
};

function wsSetOverlay(id, on) {
  const set = WS_SETTERS[id];
  if (set) set(on);
}

/* The ledger for the trading widget.
 *
 * Deliberately not loadTracker(): that one renders the whole Optic's Positions
 * view and calls beginLoad on it, which from here means building a few hundred
 * nodes into a hidden tab to fill one 260px panel. This fetches the same payload
 * and repaints just the widget.
 */
async function wsLoadTracker() {
  try {
    STATE.tracker = await getJSON('/api/tracker');
  } catch (err) {
    STATE.tracker = { error: err.message };
  }
  if (STATE.view === 'chart') wsRepaintWidget('trading');
}

/** Open or close a dock widget, repainting only the dock. */
function wsToggleWidget(id, on) {
  if (!WS_WIDGETS.some((w) => w.id === id)) return;
  if (wsIsNarrow()) {
    // Single-select. Clicking the open one closes it, which is the only way to
    // get the chart back to full width without widening the window.
    wsNarrowWidget = (wsNarrowWidget === id) ? null : id;
  } else {
    wsDockOpen = on
      ? [...wsDockOpen.filter((x) => x !== id), id]
      : wsDockOpen.filter((x) => x !== id);
    wsSaveDock();
  }
  const dock = document.getElementById('ws-dock');
  if (dock) dock.innerHTML = wsDock();
  const rail = views.chart.querySelector('.ws-wrail');
  if (rail) rail.outerHTML = wsWidgetRail();
  wsSyncNarrow();
  // `on` is only meaningful in wide mode; narrow mode toggles, so re-read it.
  on = wsIsNarrow() ? wsNarrowWidget === id : wsDockOpen.includes(id);
  // Two widgets need data the page has not necessarily fetched yet.
  if (on && id === 'seasonality') loadSeasonality(false, STATE.chartSymbol);
  if (on && id === 'trading' && !STATE.tracker) wsLoadTracker();
  if (on && id === 'alerts') loadAlerts(true);
}

/** Repaint one widget's body. Cheaper than the dock and it keeps the others'
 *  scroll position and any half-typed note. */
function wsRepaintWidget(id) {
  const host = document.getElementById(`ws-w-${id}`);
  if (host) host.innerHTML = wsWidgetBody(id);
}

/* ------------------------------------------------- the indicator manager
 *
 * The dialog behind "Manage indicators…": every styleable overlay, searchable,
 * with its colour, line width and parameters. Writes through the shared style
 * store, so a change here lands on both charts.
 *
 * Two deliberate limits. Colours come from the validated palette rather than a
 * free colour picker — the eight categorical hues plus the reference and
 * directional ones are the set that has been checked for separation under
 * colour-vision simulation, and an arbitrary hex can land indistinguishably on
 * top of a series that is already drawn. And widths are a fixed list, because a
 * text box invites 0.3 and 17, neither of which renders as a line.
 */
let wsManageOpen = false;
let wsManageQuery = '';

function wsManagePanel() {
  if (!wsManageOpen) return '';
  const q = wsManageQuery.trim().toLowerCase();
  const groups = {};
  OVERLAY_DEFS.forEach((def) => {
    if (q && !def.label.toLowerCase().includes(q) && !def.group.toLowerCase().includes(q)) return;
    (groups[def.group] = groups[def.group] || []).push(def);
  });
  const names = Object.keys(groups);

  return `<div class="ws-modal" data-ws-modal>
    <div class="ws-modal-box" role="dialog" aria-label="Manage indicators">
      <div class="ws-modal-head">
        <strong>Manage indicators</strong>
        <button type="button" class="ws-leg-btn" data-ws-manage-close
          title="Close">&times;</button>
      </div>
      <div class="ws-modal-bar">
        <input type="search" placeholder="Search indicators" data-ws-manage-q
          value="${esc(wsManageQuery)}" aria-label="Search indicators">
        <button type="button" class="btn" data-ws-manage-reset>Reset all to defaults</button>
      </div>
      <div class="ws-modal-body">
        ${names.length ? names.map((g) => `<div class="ws-mgroup">
          <h4>${esc(g)}</h4>
          ${groups[g].map((def) => wsManageRow(def)).join('')}
        </div>`).join('') : '<p class="ws-none">Nothing matches that.</p>'}
      </div>
      <p class="ws-modal-foot">Colours come from the palette the charts already
        draw from, which is the set checked for separation under colour-vision
        simulation. A free hex can land invisibly on top of a line that is
        already there. Changes apply to the Charting tab and the Swing chart
        together, and are remembered on this device.</p>
    </div>
  </div>`;
}

function wsManageRow(def) {
  const st = overlayStyle(def.id);
  const on = wsOverlayOn(def.id);
  const p = st.params || {};
  return `<div class="ws-mrow">
    <div class="ws-mrow-top">
      <label class="ws-opt" style="padding:0">
        <input type="checkbox" data-ws-opt="${esc(def.id)}"${on ? ' checked' : ''}>
        <span class="ws-mrow-name" style="color:${st.color}">${esc(st.label)}</span>
      </label>
      ${overlayStyled(def.id) ? `<button type="button" class="ws-leg-btn"
        data-ws-style-reset="${esc(def.id)}" title="Back to the default"
        style="opacity:1">reset</button>` : ''}
    </div>
    <div class="ws-mrow-controls">
      <span class="ws-mfield">
        <label>Colour</label>
        <span class="ws-swatches">${COLOR_CHOICES.map((tok) => `<button type="button"
          class="ws-cswatch${tok === st.colorToken ? ' on' : ''}"
          style="background:${C[tok] || '#888'}"
          data-ws-style="${esc(def.id)}" data-ws-color="${tok}"
          title="${tok}" aria-label="${tok}"></button>`).join('')}</span>
      </span>
      <span class="ws-mfield">
        <label>Width</label>
        <select data-ws-style="${esc(def.id)}" data-ws-width aria-label="Line width">
          ${WIDTH_CHOICES.map((w) => `<option value="${w}"${
    w === st.width ? ' selected' : ''}>${w}px</option>`).join('')}
        </select>
      </span>
      ${p.length === undefined ? '' : `<span class="ws-mfield">
        <label>Length</label>
        <input type="number" min="2" max="400" step="1" value="${fmt(p.length, 0)}"
          data-ws-style="${esc(def.id)}" data-ws-param="length" aria-label="Length">
      </span>`}
      ${p.offset === undefined ? '' : `<span class="ws-mfield">
        <label>Offset</label>
        <input type="number" min="-100" max="100" step="1" value="${fmt(p.offset, 0)}"
          data-ws-style="${esc(def.id)}" data-ws-param="offset" aria-label="Offset">
      </span>`}
      ${p.source === undefined ? '' : `<span class="ws-mfield">
        <label>Price source</label>
        <select data-ws-style="${esc(def.id)}" data-ws-param="source"
          aria-label="Price source">
          ${PRICE_SOURCES.map((sv) => `<option value="${sv}"${
    sv === p.source ? ' selected' : ''}>${sv}</option>`).join('')}
        </select>
      </span>`}
    </div>
    ${p.length !== undefined && Number(p.length) !== (OVERLAY_BY_ID[def.id].params || {}).length
    ? `<p class="ws-mnote">Length is set to ${fmt(p.length, 0)}, but the server sends
      this average at its standard ${fmt((OVERLAY_BY_ID[def.id].params || {}).length, 0)}.
      The label will say ${fmt(p.length, 0)} and the line will still be
      ${fmt((OVERLAY_BY_ID[def.id].params || {}).length, 0)} until the recompute lands.
      So this is recorded, not yet honoured.</p>` : ''}
  </div>`;
}

/** The workspace. Rendered whole, then the chart is mounted into it. */
function renderChartWorkspace(d) {
  hideTip();
  const host = views.chart;
  if (!STATE.chartSymbol) {
    host.innerHTML = `<div class="ws-empty">
      <h2>Charting</h2>
      <p class="sub">A full-height chart with its own toolbar, overlays and drawings.
        Overlay settings are shared with the Swing tab, so a moving average you recolour
        here is that colour there too.</p>
      <form class="ws-load" id="ws-form">
        <input id="ws-symbol" type="text" placeholder="Ticker" autocomplete="off"
          spellcheck="false" aria-label="Ticker to chart">
        <button class="btn primary" type="submit">Open chart</button>
      </form>
      <div class="ws-quick">${['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'AMD']
    .map((t) => `<button type="button" class="btn" data-ws-load="${t}">${t}</button>`).join('')}</div>
    </div>`;
    return;
  }
  if (d === 'loading') {
    host.innerHTML = `<div class="ws-empty">${loadingHTML(STATE.chartSymbol + ' chart')}</div>`;
    return;
  }
  if (!d || d.error) {
    host.innerHTML = `<div class="ws-empty">${errorHTML((d && d.error) || 'No data.')}
      <div class="ws-quick"><button type="button" class="btn" data-ws-load="">Try another
        ticker</button></div></div>`;
    return;
  }

  const ps = wsSeries(d);
  const q = d.quote || {};
  const bar = wsLastBar(ps);

  host.innerHTML = `
  ${wsToolbar()}
  <div class="ws-body">
    ${wsToolRail()}
    <div class="ws-canvas${wsTool === 'cursor' ? '' : ' arming'}">
      <div class="ws-head">
        <strong>${esc(STATE.chartSymbol)}</strong>
        <span class="ws-head-name">${esc((d.profile || {}).name || '')}</span>
        <span class="ws-ohlc" id="ws-ohlc">${wsOhlcRow(bar)}</span>
        <span class="${signClass(q.change_pct)}" id="ws-chg">${fmtPct(q.change_pct, 2)}</span>
        <span class="ws-head-state">${esc(cap(marketSessionET()))}</span>
      </div>
      ${wsLegend(ps)}
      <div class="ws-plot">
        <div id="ws-chart" class="ws-chart"></div>
        <!-- The drawing layer sits over the chart rather than inside it: the
             chart is rebuilt on every redraw and drawings have to survive that,
             and dragging one should cost a setAttribute, not a chart rebuild. -->
        <div id="ws-draw" class="ws-draw"></div>
      </div>
      <!-- The navigator. Panning gets its own visible control so the plot's
           drag is free to measure, which is the gesture people expect from a
           price chart. Dragging inside the window moves it, dragging an edge
           resizes it, clicking outside jumps there. -->
      <div id="ws-nav" class="ws-nav" title="Drag to move the view. Drag an edge to resize it"></div>
    </div>
    <div class="ws-dock" id="ws-dock">${wsDock()}</div>
    ${wsWidgetRail()}
  </div>
  ${wsManagePanel()}`;
}

/** The O/H/L/C row in the chart header.
 *
 * Extracted so the hover handler and the initial render produce the same markup
 * — when they were separate the hovered version quietly lost the sign colouring
 * on the close, and the two drifted every time one was edited. */
function wsOhlcRow(bar, dateLabel) {
  const chg = (bar.close !== null && bar.open !== null) ? bar.close - bar.open : null;
  return [
    dateLabel ? `<span class="ws-ohlc-date">${esc(dateLabel)}</span>` : '',
    `<span>O <b>${fmt(bar.open, 2)}</b></span>`,
    `<span>H <b>${fmt(bar.high, 2)}</b></span>`,
    `<span>L <b>${fmt(bar.low, 2)}</b></span>`,
    `<span>C <b class="${signClass(chg)}">${fmt(bar.close, 2)}</b></span>`,
    bar.volume !== null && bar.volume !== undefined
      ? `<span>V <b>${Math.round(bar.volume).toLocaleString()}</b></span>` : '',
  ].join('');
}

/** Point the header at one bar, or back at the last bar when the cursor leaves.
 *
 * The header showed O/H/L/C from wsLastBar and never moved, which is worse than
 * showing nothing: it reads as a live readout of whatever the crosshair is on,
 * so a hovered peak was reported with the closing figures from the right-hand
 * edge of the chart. The tooltip had the right numbers all along; the row that
 * looks authoritative had the wrong ones.
 *
 * Writes innerHTML on two small spans rather than re-rendering. The header is
 * ~8 nodes and this fires on every pointer move, so a view rebuild here is
 * exactly the mistake that made this chart feel laggy before. */
function wsHoverReadout(i) {
  const row = document.getElementById('ws-ohlc');
  if (!row) return;
  const d = STATE.chartData;
  if (!d || d === 'loading') return;
  const ps = wsSeries(d);
  const chg = document.getElementById('ws-chg');

  if (i === null || i === undefined) {
    const bar = wsLastBar(ps);
    row.innerHTML = wsOhlcRow(bar);
    if (chg) {
      const pct = (d.quote || {}).change_pct;
      chg.className = signClass(pct);
      chg.textContent = fmtPct(pct, 2);
    }
    return;
  }

  const at = (arr, k) => {
    const v = arr && arr[k === undefined ? i : k];
    return v === undefined || v === null ? null : v;
  };
  const bar = {
    open: at(ps.open), high: at(ps.high), low: at(ps.low),
    close: at(ps.close), volume: at(ps.volume),
  };
  row.innerHTML = wsOhlcRow(bar, at(ps.dates));

  // The percentage beside it becomes the hovered bar's own move, not the
  // quote's day change — leaving the day change there next to another bar's
  // prices would be two unrelated numbers reading as one.
  if (chg) {
    const prev = i > 0 ? at(ps.close, i - 1) : null;
    const pct = (prev && bar.close !== null) ? ((bar.close - prev) / prev) * 100 : null;
    chg.className = signClass(pct);
    chg.textContent = pct === null ? '' : fmtPct(pct, 2);
  }
}

/** The price series for the workspace, sliced to the chosen range the same way
 *  the Swing chart does it — one function so the two cannot show different bars
 *  for the same selection. */
/* The zoom and pan window, in bar indices over the full series.
 *
 * null means "no manual zoom": the range pills decide the window, which is the
 * behaviour everything else in the app assumes. Once set it overrides them,
 * and picking a range pill clears it again — a pill is a statement about how
 * much history you want, so honouring it while silently keeping an old zoom
 * would make the pills look broken.
 *
 * Held as indices rather than dates because every series in the payload is
 * already index-aligned, so a window is two integers and needs no lookup. */
let wsWindow = null;
const WS_MIN_BARS = 12;   // below this the x-axis has nothing to say

function wsFullSeries(d) {
  const raw = ((d.technicals || {}).price_series) || {};
  // Aggregate before windowing, for the same reason sliceSeries does: rolling
  // up after cutting produces a partial first bar.
  return chartInterval === 'weekly' ? aggregateWeekly(raw) : raw;
}

function wsClampWindow(win, total) {
  if (!win || !total) return null;
  let span = Math.max(WS_MIN_BARS, Math.min(total, Math.round(win.to - win.from)));
  let from = Math.round(win.from);
  from = Math.max(0, Math.min(total - span, from));
  return { from, to: from + span };
}

function wsSeries(d) {
  const full = wsFullSeries(d);
  const total = (full.dates || []).length;
  const win = wsClampWindow(wsWindow, total);
  if (!win) {
    // sliceSeries aggregates to weekly itself when told to, and does it BEFORE
    // slicing so the first bar is not a partial week. Rolling up here as well
    // would aggregate twice, so it gets the raw payload.
    const raw = ((d.technicals || {}).price_series) || {};
    return sliceSeries(raw, chartRange, chartInterval);
  }
  // Same "slice every array" rule as sliceSeries, and for the same reason: a
  // named list of fields goes stale the moment the payload gains one, and a
  // series left at full length stretches lineChart's x-axis to fit it.
  const out = { ...full };
  Object.keys(out).forEach((k) => {
    if (Array.isArray(out[k])) out[k] = out[k].slice(win.from, win.to);
  });
  return { ...out, shown_bars: win.to - win.from, total_bars: total,
           weekly: !!full.weekly, zoomed: true };
}

/** Current window as concrete indices, whatever set it. */
function wsWindowNow(d) {
  const total = ((wsFullSeries(d).dates) || []).length;
  const win = wsClampWindow(wsWindow, total);
  if (win) return { ...win, total };
  const shown = (wsSeries(d).dates || []).length;
  return { from: Math.max(0, total - shown), to: total, total };
}

/* Candles need OHLC. The mode is a preference; whether it can be honoured is a
 * property of the data, and an intraday series arrives without open/high/low. */
function wsCandles(ps) {
  return chartMode === 'candle' && !!(ps.open && ps.high && ps.low);
}

function wsLastBar(ps) {
  const at = (arr) => (Array.isArray(arr) && arr.length ? arr[arr.length - 1] : null);
  // Volume included so the resting readout has the same columns as the hovered
  // one. Without it the V field appeared only while the cursor was over the
  // plot, and the header changed width as the mouse entered and left it.
  return { open: at(ps.open), high: at(ps.high), low: at(ps.low),
           close: at(ps.close), volume: at(ps.volume) };
}

/* ------------------------------------------------------------- the dock
 *
 * Widgets down the right-hand side. Each is a panel that can be collapsed or
 * closed, and which ones are open is remembered — the reference's version is a
 * workspace you arrange once, not a fixed sidebar.
 */
/* ------------------------------------------------------- the widget catalogue
 *
 * Thirteen, matching the reference's rail. Almost all of them are a view onto
 * data the terminal already fetches for the loaded symbol — news, insiders,
 * analyst coverage, the chain, the filings — so a widget costs a render function
 * rather than an endpoint. The three that are genuinely local (notes, checklist,
 * watchlist) keep their state in localStorage.
 *
 * Two are honest stubs, and say so on their face rather than looking broken:
 * alerts and bots both need a server that is awake when the market is, which
 * this is not yet. A widget that silently never fires would be worse than one
 * that explains why.
 */
/* Monochrome glyphs only.
 *
 * The first set used emoji codepoints — newspaper, briefcase, chart, bulb — and
 * macOS renders those in full colour whatever the CSS says. Fourteen of them in
 * a 54px rail read as a row of coloured stickers next to a black chart, which is
 * the opposite of what a terminal rail should look like.
 *
 * Every glyph below is from a block with no emoji presentation, so it inherits
 * the rail's colour and goes green when the widget is open — which is what makes
 * "which of these is on" readable at a glance. */
const WS_WIDGETS = [
  { id: 'watchlist', label: 'Watch', icon: '&#9776;' },      // trigram, list
  { id: 'alerts', label: 'Alerts', icon: '&#9873;' },        // flag
  { id: 'news', label: 'News', icon: '&#9636;' },            // horizontal fill
  { id: 'analysts', label: 'Analysts', icon: '&#9650;' },    // up triangle
  { id: 'seasonality', label: 'Season', icon: '&#9639;' },   // grid
  { id: 'notes', label: 'Notes', icon: '&#9998;' },          // pencil
  { id: 'insiders', label: 'Insiders', icon: '&#9673;' },    // fisheye
  { id: 'reports', label: 'Reports', icon: '&#9635;' },      // vertical fill
  { id: 'checklist', label: 'Checklist', icon: '&#10003;' }, // check
  { id: 'options', label: 'Options', icon: '&#9671;' },      // lozenge
  { id: 'levels', label: 'Key levels', icon: '&#9776;' },    // trigram
  { id: 'patterns', label: 'Patterns', icon: '&#9651;' },    // hollow triangle
  { id: 'trading', label: 'Trading', icon: '&#9644;' },      // black rectangle
  { id: 'learn', label: 'Learn', icon: '&#9678;' },          // bullseye
];

/* Per-symbol free text. The one thing on this page the terminal cannot derive:
 * why *you* are looking at this chart. Saved on blur rather than per keystroke —
 * localStorage writes are synchronous and a write per character on a long note
 * is a measurable stall. */
const WS_NOTES_KEY = 'optic.chart.notes.v1';
function wsNotes() {
  try { return JSON.parse(localStorage.getItem(WS_NOTES_KEY) || '{}') || {}; }
  catch (e) { return {}; }
}
function wsSaveNote(sym, text) {
  const all = wsNotes();
  if (text.trim()) all[sym] = text; else delete all[sym];
  try { localStorage.setItem(WS_NOTES_KEY, JSON.stringify(all)); }
  catch (e) { /* private mode */ }
}

/* A pre-trade checklist. Fixed questions rather than user-defined ones, because
 * the value of a checklist is that it asks the same things every time — an
 * editable one becomes a list of the questions you already like the answers to.
 * State is per symbol, so ticking NVDA does not tick AMD. */
const WS_CHECKS = [
  'Do I know what invalidates this?',
  'Is the stop at a level, not a round number?',
  'Is this sized so the stop costs 1% or less?',
  'Am I early, or chasing?',
  'Does the higher timeframe agree?',
  'Is earnings inside my holding period?',
  'Would I take the other side at this price?',
];
const WS_CHECK_KEY = 'optic.chart.checks.v1';
function wsChecks() {
  try { return JSON.parse(localStorage.getItem(WS_CHECK_KEY) || '{}') || {}; }
  catch (e) { return {}; }
}
function wsSaveCheck(sym, idx, on) {
  const all = wsChecks();
  const list = new Set(all[sym] || []);
  if (on) list.add(idx); else list.delete(idx);
  all[sym] = [...list];
  try { localStorage.setItem(WS_CHECK_KEY, JSON.stringify(all)); }
  catch (e) { /* private mode */ }
}

const WS_WATCH_KEY = 'optic.chart.watch.v1';
function wsWatch() {
  try {
    const v = JSON.parse(localStorage.getItem(WS_WATCH_KEY) || 'null');
    if (Array.isArray(v) && v.length) return v;
  } catch (e) { /* private mode */ }
  return ['SPY', 'QQQ', 'IWM', 'NVDA', 'AAPL', 'MSFT', 'AMD', 'TSLA'];
}
function wsSaveWatch(list) {
  try { localStorage.setItem(WS_WATCH_KEY, JSON.stringify(list)); }
  catch (e) { /* private mode */ }
}

let wsLearnTerm = '';
/* In a narrow column the dock is hidden, so the rail behaves as single-select:
 * one widget at a time, shown as an overlay over the chart. Without this,
 * clicking a rail button changed state and displayed nothing — the buttons
 * looked broken when in fact their output was behind `display: none`. */
let wsNarrowWidget = null;
const WS_LEGEND_KEY = 'optic.chart.legend.v1';
/* Collapsed unless asked for.
 *
 * This defaulted open with a comment arguing that a new reader has no idea the
 * header is a toggle. Fair, but the cost is five stacked rows over the plot:
 * symbol and interval, the volume reading, insider trades, the drawing count
 * and the measure hint. Roughly 70px of the one view whose entire purpose is
 * chart height, spent on text the toolbar and the OHLC header already carry.
 *
 * Collapsed it is one line that still reads "N overlays", which is both the
 * summary and the hint that there is something to expand. The preference is
 * remembered either way, so the choice is paid for once. */
let wsLegendOpen = false;
try {
  if (localStorage.getItem(WS_LEGEND_KEY) === 'open') wsLegendOpen = true;
} catch (e) { /* private mode */ }
const WS_DOCK_KEY = 'optic.chart.dock.v1';
// Four to start. Opening all fourteen would put 3,000px of widgets beside a
// chart nobody could then see, and which four you want is personal — the rail
// on the right adds the rest in one click and remembers the arrangement.
let wsDockOpen = ['watchlist', 'levels', 'news', 'seasonality'];
try {
  const saved = JSON.parse(localStorage.getItem(WS_DOCK_KEY) || 'null');
  if (Array.isArray(saved)) wsDockOpen = saved.filter((x) => WS_WIDGETS.some((w) => w.id === x));
} catch (e) { /* private mode */ }

function wsSaveDock() {
  try { localStorage.setItem(WS_DOCK_KEY, JSON.stringify(wsDockOpen)); }
  catch (e) { /* private mode */ }
}

function wsDock() {
  // Narrow: exactly one, whichever the rail last selected. Wide: everything the
  // reader has opened.
  const showing = wsIsNarrow()
    ? (wsNarrowWidget ? [wsNarrowWidget] : [])
    : wsDockOpen;
  return `<div class="ws-dock-panels">
  ${showing.map((id) => {
    const w = WS_WIDGETS.find((x) => x.id === id);
    if (!w) return '';
    return `<div class="ws-widget" data-ws-widget="${id}">
      <div class="ws-widget-head">
        <span>${esc(w.label)}</span>
        <button type="button" class="ws-leg-btn" data-ws-widget-close="${id}"
          title="Close ${esc(w.label)}">&times;</button>
      </div>
      <div class="ws-widget-body" id="ws-w-${id}">${wsWidgetBody(id)}</div>
    </div>`;
  }).join('') || '<p class="ws-none">No widgets open. Pick one from the rail.</p>'}
  </div>`;
}

/* The icon rail. Every widget one click away and its own on/off state visible,
 * which a dropdown of fourteen names is not. Labels under the icons because
 * fourteen unfamiliar glyphs is a memory test — the reference does the same. */
function wsWidgetRail() {
  return `<div class="ws-wrail" role="toolbar" aria-label="Widgets">
    ${WS_WIDGETS.map((w) => {
    const on = wsIsNarrow() ? wsNarrowWidget === w.id : wsDockOpen.includes(w.id);
    return `<button type="button"
      class="ws-wrail-btn${on ? ' on' : ''}"
      data-ws-widget-toggle="${w.id}" aria-pressed="${on}"
      title="${esc(w.label)}">
      <span class="ws-wrail-ico">${w.icon}</span>
      <span class="ws-wrail-lab">${esc(w.label)}</span>
    </button>`;
  }).join('')}
  </div>`;
}

/* ------------------------------------------------------------------ alerts
 *
 * An inbox of things the terminal noticed, recorded server-side so it fills
 * whether or not anyone had the page open.
 *
 * Delivery — email or text — is deliberately not wired, and the panel says why
 * rather than showing a disabled toggle. Two things are missing and only one of
 * them is a credential: the other is a server that stays awake when the market
 * is open. An alert that silently misses the move it was created for is worse
 * than no alert, because you would have stopped watching for it yourself.
 */
async function loadAlerts(force) {
  if (STATE.alerts && !force) return;
  try { STATE.alerts = await getJSON('/api/alerts?limit=60'); }
  catch (err) { STATE.alerts = { error: err.message, alerts: [] }; }
  if (STATE.view === 'chart') wsRepaintWidget('alerts');
  paintAlertBadge();
}

/** The unseen count on the widget rail, so a new alert is visible without the
 *  widget being open. */
function paintAlertBadge() {
  const btn = document.querySelector('[data-ws-widget-toggle="alerts"]');
  if (!btn) return;
  const n = (STATE.alerts || {}).unseen || 0;
  let dot = btn.querySelector('.ws-wrail-badge');
  if (!n) { if (dot) dot.remove(); return; }
  if (!dot) {
    dot = document.createElement('span');
    dot.className = 'ws-wrail-badge';
    btn.appendChild(dot);
  }
  dot.textContent = n > 9 ? '9+' : String(n);
}

function alertsBody() {
  const a = STATE.alerts;
  if (!a) { loadAlerts(); return loadingHTML('alerts'); }
  if (a.error) return `<p class="ws-none">${esc(a.error)}</p>`;

  const rows = a.alerts || [];
  const d = a.delivery || {};

  const list = rows.length ? `<ul class="ws-list alert-list">${rows.map((x) => `
    <li class="alert-row${x.seen ? '' : ' unseen'}">
      <div class="alert-top">
        <span class="alert-kind ${esc(x.urgency || 'normal')}">${esc(x.kind_label || x.kind)}</span>
        ${x.ticker ? `<button type="button" class="tkr"
          data-ws-load="${esc(x.ticker)}">${esc(x.ticker)}</button>` : ''}
        <span class="ws-leg-args">${esc(briefAgo(x.created_at) || '')}</span>
      </div>
      <div class="alert-title">${esc(x.title)}</div>
      ${x.body ? `<div class="alert-body">${esc(x.body)}</div>` : ''}
    </li>`).join('')}</ul>
    <div class="alert-acts">
      <button type="button" class="btn" data-alerts-seen>Mark all read</button>
      <button type="button" class="btn" data-alerts-clear>Clear</button>
    </div>`
    : `<p class="ws-none">Nothing yet. Alerts are recorded when a scan opens or
       closes a position, so the first ones arrive after the next scan.</p>`;

  return `${list}
  <div class="alert-delivery">
    <strong>${d.enabled ? 'Delivery is on.' : 'Nothing is being sent to you.'}</strong>
    ${d.enabled ? '' : `
      <ul class="alert-blockers">${(d.blockers || []).map((b) =>
    `<li>${esc(b)}</li>`).join('')}</ul>`}
  </div>`;
}

function wsWidgetBody(id) {
  const d = STATE.chartData && STATE.chartData !== 'loading' ? STATE.chartData : null;
  const sym = STATE.chartSymbol || '';
  const none = (why) => `<p class="ws-none">${esc(why)}</p>`;

  if (id === 'watchlist') {
    const list = wsWatch();
    return `<ul class="ws-list">${list.map((t) => `<li class="ws-watch-row">
      <button type="button" class="tkr${t === sym ? ' on' : ''}"
        data-ws-load="${esc(t)}">${esc(t)}</button>
      <button type="button" class="ws-leg-btn" data-ws-unwatch="${esc(t)}"
        title="Remove ${esc(t)}">&times;</button>
    </li>`).join('')}</ul>
    <form class="ws-add" data-ws-watch-form>
      <input type="text" placeholder="Add ticker" aria-label="Add to watchlist"
        data-ws-watch-input spellcheck="false" autocomplete="off">
    </form>
    ${sym && !list.includes(sym) ? `<button type="button" class="btn"
      data-ws-watch-add="${esc(sym)}">Add ${esc(sym)}</button>` : ''}`;
  }

  if (id === 'alerts') return alertsBody();

  if (id === 'news') {
    const n = (d || {}).news || {};
    const arts = (n.articles || []).slice(0, 7);
    if (!arts.length) return none(d ? 'No recent coverage.' : 'Load a symbol.');
    return `<p class="ws-leg-args">${esc(cap(n.overall_tone || ''))}${
  n.article_count ? ` · ${fmt(n.article_count, 0)} stories` : ''}</p>
    <ul class="ws-list">${arts.map((a) => `<li>
      <a href="${esc(a.link || a.url || '#')}" target="_blank" rel="noopener"
        class="ws-news-link">${esc((a.title || '').slice(0, 92))}</a>
      <span class="ws-leg-args">${esc(a.publisher || a.source || '')}</span>
    </li>`).join('')}</ul>`;
  }

  if (id === 'analysts') {
    const q = (d || {}).quote || {};
    const rows = [];
    // The field is `analyst_target`, not `target_mean`. Reading the wrong name
    // rendered a widget with two rows and no numbers, which looks like missing
    // data rather than a wrong key — worth naming so the next one is checked.
    if (q.analyst_target) rows.push(['Mean target', money(q.analyst_target, 2)]);
    if (q.recommendation) {
      // "strong_buy" is a machine token; nobody writes that.
      rows.push(['Consensus', cap(String(q.recommendation).replace(/_/g, ' '))]);
    }
    if (q.forward_pe) rows.push(['Forward P/E', fmt(q.forward_pe, 1)]);
    if (q.peg_ratio) rows.push(['PEG', fmt(q.peg_ratio, 2)]);
    if (q.revenue_growth !== undefined && q.revenue_growth !== null) {
      rows.push(['Revenue growth', fmtPct(q.revenue_growth * 100, 1)]);
    }
    const em = (d || {}).earnings_momentum || {};
    if (em.revision_direction) rows.push(['Revisions', cap(em.revision_direction)]);
    if (!rows.length) return none(d ? 'No analyst data for this symbol.' : 'Load a symbol.');
    return `<table class="data narrow"><tbody>${rows.map(([k, val]) =>
      `<tr><td class="name">${esc(k)}</td><td>${val}</td></tr>`).join('')}</tbody></table>
    ${q.analyst_target && q.price ? `<p class="ws-leg-args">${
  fmtPct(((q.analyst_target - q.price) / q.price) * 100, 1)} to the mean target. A target
      is a forecast, and the record of them as a group is poor. Read it as
      sentiment, not as a level.</p>` : ''}`;
  }

  if (id === 'seasonality') {
    if (!STATE.seasonality || STATE.seasonalityFor !== sym) return loadingHTML('seasonality');
    return wsSeasonalityMini(STATE.seasonality);
  }

  if (id === 'notes') {
    const text = wsNotes()[sym] || '';
    return `<textarea class="ws-note" data-ws-note="${esc(sym)}" rows="6"
      placeholder="Why are you looking at ${esc(sym || 'this')}? What would change your mind?"
      >${esc(text)}</textarea>
    <p class="ws-leg-args">Saved for ${esc(sym || 'this symbol')} on this device.
      The one thing on the page the terminal cannot work out for you.</p>`;
  }

  if (id === 'insiders') {
    const own = ((d || {}).company || {}).ownership || {};
    const six = own.insider_6m || {};
    const tx = (own.recent_transactions || []).slice(0, 6);
    const rows = [];
    if (own.insider_signal) rows.push(['6-month signal', cap(own.insider_signal)]);
    if (six.net_shares !== undefined && six.net_shares !== null) {
      rows.push(['Net shares', fmtCompact(six.net_shares, 1)]);
    }
    if (six.purchase_count) rows.push(['Buys', fmt(six.purchase_count, 0)]);
    if (six.sale_count) rows.push(['Sells', fmt(six.sale_count, 0)]);
    const si = ((d || {}).company || {}).short_interest || {};
    if (si.short_percent_float) rows.push(['Short float', fmt(si.short_percent_float, 1) + '%']);
    if (si.days_to_cover) rows.push(['Days to cover', fmt(si.days_to_cover, 1)]);
    if (!rows.length && !tx.length) return none(d ? 'No ownership data.' : 'Load a symbol.');
    return `${rows.length ? `<table class="data narrow"><tbody>${rows.map(([k, v]) =>
      `<tr><td class="name">${esc(k)}</td><td>${v}</td></tr>`).join('')}</tbody></table>` : ''}
    ${tx.length ? `<ul class="ws-list">${tx.map((t) => {
    const shares = Number(t.shares || 0);
    return `<li><span class="${shares > 0 ? 'up' : 'down'}">${
      shares > 0 ? 'Bought' : 'Sold'}</span>
      ${esc((t.insider || '').slice(0, 24))}
      <span class="ws-leg-args">${esc(t.date || '')}</span></li>`;
  }).join('')}</ul>` : ''}`;
  }

  if (id === 'reports') {
    const fin = ((d || {}).company || {}).financials || {};
    const eh = ((d || {}).company || {}).earnings_history || {};
    const rows = [];
    if (fin.revenue_growth_pct !== undefined && fin.revenue_growth_pct !== null) {
      rows.push(['Revenue growth', fmtPct(fin.revenue_growth_pct, 1)]);
    }
    if (fin.gross_margin_pct) rows.push(['Gross margin', fmt(fin.gross_margin_pct, 1) + '%']);
    if (fin.trailing_pe) rows.push(['P/E (trailing)', fmt(fin.trailing_pe, 1)]);
    if (fin.forward_pe) rows.push(['P/E (forward)', fmt(fin.forward_pe, 1)]);
    if (eh.beat_rate_pct !== undefined && eh.beat_rate_pct !== null) {
      rows.push(['EPS beat rate', fmt(eh.beat_rate_pct, 0) + '%']);
    }
    const f = ((d || {}).filings || {}).filings || [];
    if (!rows.length && !f.length) return none(d ? 'No filings or financials.' : 'Load a symbol.');
    return `${rows.length ? `<table class="data narrow"><tbody>${rows.map(([k, v]) =>
      `<tr><td class="name">${esc(k)}</td><td>${v}</td></tr>`).join('')}</tbody></table>` : ''}
    ${f.length ? `<ul class="ws-list">${f.slice(0, 5).map((x) => `<li>
      <a href="${esc(x.url || '#')}" target="_blank" rel="noopener" class="ws-news-link">${
  esc(x.form || '')}</a> <span class="ws-leg-args">${esc(x.filed || x.date || '')}</span>
    </li>`).join('')}</ul>` : ''}`;
  }

  if (id === 'checklist') {
    const on = new Set((wsChecks()[sym] || []));
    return `<ul class="ws-checks">${WS_CHECKS.map((q, i) => `<li>
      <label><input type="checkbox" data-ws-check="${i}"${on.has(i) ? ' checked' : ''}>
        <span>${esc(q)}</span></label></li>`).join('')}</ul>
    <p class="ws-leg-args">${on.size} of ${WS_CHECKS.length} for ${esc(sym || '—')}.
      Fixed questions on purpose. A checklist you can edit becomes a list of the
      questions you already like the answers to.</p>`;
  }

  if (id === 'options') {
    const g = (d || {}).gex || {};
    const gk = (d || {}).greeks || {};
    const rows = [];
    // regime is {state, note}, not a string — cap() on the object rendered
    // "[object Object]" on the widget.
    if ((g.regime || {}).state) rows.push(['Gamma regime', cap(g.regime.state)]);
    if ((g.totals || {}).net_gex !== undefined) {
      rows.push(['Net GEX', money((g.totals || {}).net_gex, 0)]);
    }
    // gex.levels is a dict of NAMED levels — call_wall, put_wall, gamma_pin —
    // not a list. Treating it as one threw and took the whole dock down with it.
    const LEVEL_LABELS = {
      call_wall: 'Call wall', put_wall: 'Put wall',
      gamma_pin: 'Gamma pin', max_oi_strike: 'Most open interest',
    };
    Object.entries(g.levels || {}).forEach(([k, l]) => {
      if (!l || !LEVEL_LABELS[k]) return;
      rows.push([LEVEL_LABELS[k], `${fmt(l.strike, 2)}${
        l.distance_pct === undefined ? '' : ` (${fmtPct(l.distance_pct, 1)})`}`]);
    });
    const atm = gk.atm_greeks || {};
    if (atm.iv) rows.push(['ATM IV', fmt(atm.iv * (atm.iv < 3 ? 100 : 1), 1) + '%']);
    if (!rows.length) return none(d ? 'No chain for this symbol.' : 'Load a symbol.');
    return `<table class="data narrow"><tbody>${rows.map(([k, v]) =>
      `<tr><td class="name">${esc(k)}</td><td>${v}</td></tr>`).join('')}</tbody></table>
    <p class="ws-leg-args">${esc(((g.regime || {}).note || g.assumption || '').slice(0, 150))}</p>`;
  }

  if (id === 'levels') {
    const lv = (((d || {}).technicals) || {}).support_resistance || [];
    if (!lv.length) return none(d ? 'No levels found.' : 'Load a symbol.');
    const spot = ((d || {}).technicals || {}).spot;
    return `<table class="data narrow"><tbody>${lv.slice(0, 9).map((l) => `<tr>
      <td class="name">${fmt(l.price, 2)}</td>
      <td class="${l.role === 'resistance' ? 'down' : 'up'}">${esc(l.role || '')}</td>
      <td>${spot ? fmtPct(((l.price - spot) / spot) * 100, 1) : ''}</td>
      <td>${fmt(l.strength, 0)}</td>
    </tr>`).join('')}</tbody></table>`;
  }

  if (id === 'patterns') {
    const pat = (d || {}).patterns || {};
    const chart = (pat.chart_patterns || []).slice(0, 4);
    const candles = (pat.candle_patterns || []).slice(0, 4);
    if (!chart.length && !candles.length) return none(d ? 'Nothing detected.' : 'Load a symbol.');
    return `${chart.length ? `<ul class="ws-list">${chart.map((x) => `<li>
      <strong>${esc(x.name || x.kind || '')}</strong>
      <span class="ws-leg-args">${esc(x.status || '')}</span></li>`).join('')}</ul>` : ''}
    ${candles.length ? `<p class="ws-leg-args" style="margin-top:var(--space-1)">Candles:
      ${candles.map((c) => esc(c.name || c.kind || '')).join(', ')}</p>` : ''}`;
  }

  if (id === 'trading') {
    const t = STATE.tracker;
    if (!t) return `${none('Ledger not loaded.')}
      <button type="button" class="btn" data-goto-view="tracker">Open Optic's Positions</button>`;
    const mine = (t.open || []).filter((p) => p.ticker === sym);
    const s2 = t.summary || {};
    return `<table class="data narrow"><tbody>
      <tr><td class="name">Equity</td><td>${money(s2.equity, 0)}</td></tr>
      <tr><td class="name">Open</td><td>${fmt(s2.open_count, 0)}</td></tr>
      <tr><td class="name">Return</td><td class="${signClass(s2.return_pct)}">${
  fmtPct(s2.return_pct, 2)}</td></tr>
    </tbody></table>
    ${mine.length ? `<p class="ws-leg-args">Holding ${esc(sym)}: ${mine.map((p) =>
    `${fmt(p.qty, 0)} ${p.instrument === 'option' ? 'contracts' : 'shares'} at ${
      fmt(p.entry_price, 2)}`).join('; ')}</p>`
    : `<p class="ws-leg-args">No position in ${esc(sym || 'this name')}.</p>`}`;
  }

  if (id === 'learn') {
    // The glossary the app already carries, surfaced as something you can browse
    // rather than only discover by hovering the right word.
    const terms = Object.keys(GLOSSARY || {}).sort();
    if (!terms.length) return none('No glossary loaded.');
    const pick = wsLearnTerm && GLOSSARY[wsLearnTerm] ? wsLearnTerm : terms[0];
    return `<select class="settings-select" data-ws-learn style="width:100%">
      ${terms.map((t) => `<option value="${esc(t)}"${t === pick ? ' selected' : ''}>${
  esc(cap(t))}</option>`).join('')}
    </select>
    <p style="margin-top:var(--space-2);line-height:1.5">${esc(GLOSSARY[pick])}</p>
    <p class="ws-leg-args">${terms.length} terms. The same definitions the dotted
      underlines show, browsable. Which is the only way they work on a phone,
      where there is no hover.</p>`;
  }

  return '';
}

/** A compact month grid for the dock. The full panel with the significance
 *  columns lives on the Swing tab; this is the at-a-glance version. */
function wsSeasonalityMini(sn) {
  if (sn && sn.error) return `<p class="sub">${esc(sn.error)}</p>`;
  const rows = ((sn || {}).monthly || {}).rows || [];
  if (!rows.length) return '<p class="sub">Not enough history.</p>';
  const val = (r) => (r.raw || {}).mean;
  const max = Math.max(...rows.map((r) => Math.abs(val(r) || 0)), 0.01);
  const meta = (sn.monthly || {});
  return `<div class="ws-seas">${rows.map((r) => {
    const v = val(r) || 0;
    const raw = r.raw || {};
    const h = Math.max(Math.round((Math.abs(v) / max) * 34), 2);
    // Bar height is the mean, the number above it is the hit rate. Two different
    // measures deliberately: a month can be up 9 years in 15 and still average
    // negative if the losses are bigger, and that disagreement is the useful part.
    return `<div class="ws-seas-col" title="${esc(r.label || '')}: mean ${fmt(v, 2)}% over ${
  fmt(raw.n, 0)} years, up ${fmt(raw.hit_rate, 0)}% of them: ${esc(raw.verdict || '')}">
      <span class="ws-seas-pct">${fmt(raw.hit_rate, 0)}</span>
      <span class="ws-seas-bar ${v >= 0 ? 'up' : 'down'}" style="height:${h}px"></span>
      <span class="ws-seas-lab">${esc((r.short || '').slice(0, 1))}</span>
    </div>`;
  }).join('')}</div>
  <p class="ws-leg-args">Bar is the mean move, the figure above is how often it
    was up. ${fmt(sn.years, 0)} years. Hover for the verdict, at n=${
  fmt(((rows[0] || {}).raw || {}).n, 0)} per month, most come back noise, and
    the full panel on the Swing tab shows why.</p>`;
}


/* Trend lines as chart segments.
 *
 * The server returns each line in *bar index* space against its own 1-year daily
 * frame. The chart may be showing a slice of that (3M, 6M) or weekly bars, so
 * the indexes have to be rebased onto whatever is on screen — matched by DATE,
 * not by offset, because a weekly rollup changes the bar count entirely and an
 * index-arithmetic shortcut would put every line in the wrong place.
 *
 * Colour carries the reading: a line still holding is drawn in the direction it
 * implies, and a broken one is drawn in the opposite colour, dashed. That is the
 * whole value of automating this — "this support broke" is the event, and it
 * should not require comparing two numbers in a table.
 */
function trendSegments(tl, chartDates) {
  if (!tl || !tl.available || !Array.isArray(chartDates) || !chartDates.length) return [];
  const srcDates = tl.dates || [];
  // Where each chart bar sits in the server's frame, and vice versa.
  const posInChart = new Map();
  chartDates.forEach((d, i) => posInChart.set(d, i));

  return (tl.lines || []).map((l) => {
    const d1 = srcDates[l.start_index];
    const d2 = srcDates[l.end_index];
    if (!d1 || !d2) return null;
    // A weekly chart has no bar for most daily dates, so fall back to the
    // nearest chart bar at or after the anchor.
    const nearest = (target) => {
      if (posInChart.has(target)) return posInChart.get(target);
      for (let i = 0; i < chartDates.length; i += 1) {
        if (chartDates[i] >= target) return i;
      }
      return null;
    };
    const x1 = nearest(d1);
    const x2 = chartDates.length - 1;
    if (x1 === null || x1 >= x2) return null;

    const holding = !l.broken;
    const bullish = l.kind === 'support' ? holding : !holding;
    return {
      x1, y1: l.start_price,
      x2, y2: l.price_now,
      color: bullish ? C.pos : C.neg,
      width: l.broken ? 1.4 : 1.8,
      dash: l.broken ? '5 4' : null,
      opacity: l.broken ? 0.75 : 0.9,
      label: `${l.kind === 'support' ? 'S' : 'R'} ${l.touches}\u00d7${
        l.broken ? ' broken' : ''}`,
    };
  }).filter(Boolean);
}

/** Trend lines load per symbol, on demand — only when the overlay is on. */
async function loadTrendlines(symbol, force) {
  const sym = symbol || STATE.chartSymbol || STATE.ticker;
  if (!sym) return;
  if (STATE.trendlinesFor === sym && !force) return;
  STATE.trendlinesFor = sym;
  try {
    STATE.trendlines = await getJSON(`/api/trendlines/${encodeURIComponent(sym)}`);
  } catch (err) {
    STATE.trendlines = { available: false, reason: err.message };
  }
  if (STATE.view === 'chart') wsRedrawChart();
  else if (STATE.view === 'swing' && STATE.swing) {
    preserveUI(views.swing, () => renderSwing(STATE.swing));
  }
}

/* ==================================================== the drawing layer
 *
 * Nine tools that draw onto the chart, plus selection, dragging and delete.
 *
 * **Anchored to data, not to pixels.** Every drawing stores (bar index, price)
 * for each of its points. Storing screen coordinates is the obvious shortcut and
 * it breaks the first time the window is resized, the range is changed or the
 * dock is opened — the drawing stays where it was on screen and is now pointing
 * at a different date and a different price, which is worse than losing it.
 *
 * **A separate SVG on top, not part of the chart.** The chart is rebuilt from
 * scratch on every redraw; drawings must survive that, and they must not be
 * cleared by an unrelated overlay toggle. Keeping them in their own layer also
 * means dragging a drawing costs one `setAttribute`, not a chart rebuild.
 *
 * **Snapping.** Creating a drawing snaps its price to the nearest OHLC value of
 * the bar under the cursor when within SNAP_PX. Freehand placement to the
 * half-cent is a false precision — you almost always mean "that high".
 */
const DRAW_SNAP_PX = 7;
/* Grab tolerance for a drawn line, in viewBox units. Fourteen is about 9
   screen pixels at the usual scale: wide enough to hit without aiming, narrow
   enough that two nearby lines stay separately selectable. */
const DRAW_HIT_WIDTH = 14;
const DRAW_HANDLE_R = 4.5;
// Fib ratios for the drawn tool. The same set the analysis uses, so a hand-drawn
// retracement and a computed one are comparable.
const DRAW_FIBS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.272, 1.618];

let wsDragging = null;      // { id, part, startPoints } while a pointer is down
let wsPending = null;       // the drawing being created

/** How many points each tool needs before the drawing is finished. */
const TOOL_POINTS = {
  trend: 2, ray: 2, hline: 1, vline: 1, channel: 3, rect: 2,
  fibdraw: 2, fibext: 3, pitchfork: 3, arrow: 2, text: 1,
  ruler: 2, rr: 3, position: 3,
};

function wsToolNeeds(tool) { return TOOL_POINTS[tool] || 0; }

/** Nearest interesting price on a bar, for snapping. */
function wsSnapPrice(ps, index, price, frame) {
  const at = (arr) => (Array.isArray(arr) && Number.isFinite(arr[index]) ? arr[index] : null);
  const candidates = [at(ps.high), at(ps.low), at(ps.close), at(ps.open)]
    .filter((v) => v !== null);
  let best = price;
  let bestPx = Infinity;
  candidates.forEach((c) => {
    const px = Math.abs(frame.yOf(c) - frame.yOf(price));
    if (px < bestPx) { bestPx = px; best = c; }
  });
  return bestPx <= DRAW_SNAP_PX ? best : price;
}

function wsDrawId() {
  return 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

/* ------------------------------------------------------------- rendering */

function wsRenderDrawings() {
  const host = document.getElementById('ws-chart');
  const svg = host && host.querySelector('svg.chart');
  const layer = document.getElementById('ws-draw');
  if (!layer) return;
  const frame = svg && svg.chartFrame;
  if (!frame) { layer.innerHTML = ''; return; }

  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs, text) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v !== null && v !== undefined) node.setAttribute(k, String(v));
    });
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const root = el('svg', {
    class: 'ws-draw-svg', viewBox: `0 0 ${frame.width} ${frame.height}`,
    width: '100%', height: frame.height, preserveAspectRatio: 'xMidYMid meet',
  });

  const P = (pt) => [frame.xOf(pt.i), frame.yOf(pt.p)];
  const list = wsDrawings();

  list.forEach((dr) => {
    if (dr.hidden) return;
    const sel = dr.id === wsSelected;
    const colour = C[dr.color] || C.accent;
    const g = el('g', { 'data-draw': dr.id, class: 'ws-dr' + (sel ? ' on' : '') });
    const pts = (dr.points || []).map(P);

    /* stroke falls back twice on purpose.
     *
     * el() skips an undefined attribute rather than writing "undefined", so a
     * missing palette slot produced a line with no stroke: invisible, while
     * still counting in "2 drawings" and still selectable. A drawing with no
     * colour should be the wrong colour, never nothing. */
    const line = (x1, y1, x2, y2, extra) => el('line', Object.assign({
      x1, y1, x2, y2, stroke: colour || C.s1 || '#3987e5',
      'stroke-width': dr.width || 1.6, 'stroke-linecap': 'round',
    }, extra || {}));

    if (dr.kind === 'trend' && pts.length === 2) {
      g.appendChild(line(pts[0][0], pts[0][1], pts[1][0], pts[1][1]));
    } else if (dr.kind === 'ray' && pts.length === 2) {
      // Extended to the right edge, which is the point of a ray.
      const [x1, y1] = pts[0]; const [x2, y2] = pts[1];
      const dx = x2 - x1;
      const edge = frame.margin.l + frame.plotW;
      const k = dx === 0 ? 0 : (edge - x1) / dx;
      g.appendChild(line(x1, y1, dx === 0 ? x2 : edge,
        dx === 0 ? y2 : y1 + (y2 - y1) * k));
    } else if (dr.kind === 'hline' && pts.length === 1) {
      const y = pts[0][1];
      g.appendChild(line(frame.margin.l, y, frame.margin.l + frame.plotW, y,
        { 'stroke-dasharray': '6 4' }));
      g.appendChild(el('text', {
        x: frame.margin.l + frame.plotW - 4, y: y - 5, 'text-anchor': 'end',
        fill: colour, 'font-size': 10, 'font-weight': 600,
      }, fmt(dr.points[0].p, 2)));
    } else if (dr.kind === 'rect' && pts.length === 2) {
      g.appendChild(el('rect', {
        x: Math.min(pts[0][0], pts[1][0]), y: Math.min(pts[0][1], pts[1][1]),
        width: Math.abs(pts[1][0] - pts[0][0]), height: Math.abs(pts[1][1] - pts[0][1]),
        fill: colour, 'fill-opacity': 0.12, stroke: colour,
        'stroke-width': dr.width || 1.4,
      }));
    } else if (dr.kind === 'fibdraw' && pts.length === 2) {
      const p0 = dr.points[0].p; const p1 = dr.points[1].p;
      const x1 = Math.min(pts[0][0], pts[1][0]);
      const x2 = frame.margin.l + frame.plotW;
      DRAW_FIBS.forEach((r) => {
        const price = p0 + (p1 - p0) * r;
        const y = frame.yOf(price);
        g.appendChild(line(x1, y, x2, y, {
          opacity: (r === 0.618 || r === 0.5) ? 0.95 : 0.6,
          'stroke-width': (r === 0.618 || r === 0.5) ? 1.8 : 1,
        }));
        g.appendChild(el('text', {
          x: x1 + 3, y: y - 4, fill: colour, 'font-size': 10,
        }, `${r} (${fmt(price, 2)})`));
      });
    } else if (dr.kind === 'vline' && pts.length === 1) {
      const x = pts[0][0];
      g.appendChild(line(x, frame.margin.t, x, frame.margin.t + frame.priceH,
        { 'stroke-dasharray': '5 4' }));
      g.appendChild(el('text', {
        x: x + 4, y: frame.margin.t + 12, fill: colour, 'font-size': 10,
      }, (frame.labels[Math.round(dr.points[0].i)] || '').slice(0, 10)));
    } else if (dr.kind === 'channel' && pts.length === 3) {
      // Two parallel lines: the base through the first two points, and a copy
      // shifted to pass through the third. Parallel by construction rather than
      // by eye, which is the only reason to have the tool at all.
      const [a, b, c] = dr.points;
      const slope = b.i === a.i ? 0 : (b.p - a.p) / (b.i - a.i);
      const at = (i, anchor) => anchor.p + slope * (i - anchor.i);
      const x2i = frame.bars - 1;
      [a, c].forEach((anchor, k) => {
        g.appendChild(line(frame.xOf(a.i), frame.yOf(at(a.i, anchor)),
          frame.xOf(x2i), frame.yOf(at(x2i, anchor)),
          { opacity: k === 0 ? 1 : 0.85 }));
      });
      g.appendChild(el('path', {
        d: `M${frame.xOf(a.i)},${frame.yOf(at(a.i, a))}`
          + ` L${frame.xOf(x2i)},${frame.yOf(at(x2i, a))}`
          + ` L${frame.xOf(x2i)},${frame.yOf(at(x2i, c))}`
          + ` L${frame.xOf(a.i)},${frame.yOf(at(a.i, c))} Z`,
        fill: colour, 'fill-opacity': 0.08, stroke: 'none',
      }));
    } else if (dr.kind === 'fibext' && pts.length === 3) {
      // Three points: the move (A to B) and where the retracement ended (C).
      // Levels project from C by multiples of the A-B distance, which is what
      // makes this an extension rather than a retracement.
      const [a, b, c] = dr.points;
      const span = b.p - a.p;
      const x1 = frame.xOf(Math.min(a.i, c.i));
      const x2 = frame.margin.l + frame.plotW;
      [0, 0.618, 1, 1.272, 1.618, 2, 2.618].forEach((r) => {
        const price = c.p + span * r;
        const y = frame.yOf(price);
        g.appendChild(line(x1, y, x2, y, {
          opacity: (r === 1.618 || r === 1) ? 0.95 : 0.55,
          'stroke-width': (r === 1.618 || r === 1) ? 1.8 : 1,
        }));
        g.appendChild(el('text', { x: x1 + 3, y: y - 4, fill: colour, 'font-size': 10 },
          `${r} (${fmt(price, 2)})`));
      });
    } else if (dr.kind === 'pitchfork' && pts.length === 3) {
      // Andrews pitchfork: a handle from the first pivot to the midpoint of the
      // other two, and two tines parallel to it through those two points.
      const [a, b, c] = dr.points;
      const mid = { i: (b.i + c.i) / 2, p: (b.p + c.p) / 2 };
      const slope = mid.i === a.i ? 0 : (mid.p - a.p) / (mid.i - a.i);
      const x2i = frame.bars - 1;
      const at = (i, anchor) => anchor.p + slope * (i - anchor.i);
      // The handle stops at the midpoint; the tines run to the right edge.
      g.appendChild(line(frame.xOf(a.i), frame.yOf(a.p),
        frame.xOf(mid.i), frame.yOf(mid.p), { 'stroke-dasharray': '4 3' }));
      [mid, b, c].forEach((anchor, k) => {
        g.appendChild(line(frame.xOf(anchor.i), frame.yOf(anchor.p),
          frame.xOf(x2i), frame.yOf(at(x2i, anchor)),
          { opacity: k === 0 ? 1 : 0.75,
            'stroke-width': k === 0 ? (dr.width || 1.6) + 0.4 : (dr.width || 1.6) }));
      });
    } else if (dr.kind === 'arrow' && pts.length === 2) {
      const [x1, y1] = pts[0]; const [x2, y2] = pts[1];
      g.appendChild(line(x1, y1, x2, y2));
      // Head sized in screen pixels, not in data units, so it stays a
      // recognisable arrow at every zoom level.
      const ang = Math.atan2(y2 - y1, x2 - x1);
      const h = 9;
      g.appendChild(el('path', {
        d: `M${x2},${y2} L${x2 - h * Math.cos(ang - 0.4)},${y2 - h * Math.sin(ang - 0.4)}`
          + ` L${x2 - h * Math.cos(ang + 0.4)},${y2 - h * Math.sin(ang + 0.4)} Z`,
        fill: colour,
      }));
    } else if (dr.kind === 'position' && pts.length === 3) {
      // Entry, stop, and the account risk expressed as a price distance. Shares
      // = risk budget / risk per share, which is the arithmetic people most
      // often do wrong in their head and then size four times too big.
      const [entry, stop, budgetPt] = dr.points;
      const perShare = Math.abs(entry.p - stop.p);
      const budget = Math.abs(budgetPt.p - entry.p) * 100;
      const shares = perShare ? Math.floor(budget / perShare) : 0;
      const x1 = frame.xOf(Math.min(entry.i, stop.i));
      const x2 = frame.margin.l + frame.plotW;
      const yE = frame.yOf(entry.p); const yS = frame.yOf(stop.p);
      g.appendChild(el('rect', {
        x: x1, y: Math.min(yE, yS), width: x2 - x1, height: Math.abs(yS - yE),
        fill: C.neg, 'fill-opacity': 0.14, stroke: C.neg, 'stroke-width': 1,
      }));
      g.appendChild(el('text', {
        x: x1 + 5, y: Math.min(yE, yS) - 5, fill: C.ink, 'font-size': 11,
        'font-weight': 600,
      }, `${fmt(shares, 0)} shares · ${fmt(perShare, 2)}/share · risk ${money(budget, 0)}`));
    } else if (dr.kind === 'text' && pts.length === 1) {
      g.appendChild(el('text', {
        x: pts[0][0], y: pts[0][1], fill: colour, 'font-size': 12,
        'font-weight': 600,
      }, dr.text || 'note'));
    } else if (dr.kind === 'ruler' && pts.length === 2) {
      const a = dr.points[0]; const b = dr.points[1];
      g.appendChild(line(pts[0][0], pts[0][1], pts[1][0], pts[1][1],
        { 'stroke-dasharray': '4 3' }));
      g.appendChild(el('rect', {
        x: Math.min(pts[0][0], pts[1][0]), y: Math.min(pts[0][1], pts[1][1]),
        width: Math.abs(pts[1][0] - pts[0][0]), height: Math.abs(pts[1][1] - pts[0][1]),
        fill: colour, 'fill-opacity': 0.07,
      }));
      const dPct = a.p ? ((b.p - a.p) / a.p) * 100 : 0;
      const bars = Math.abs(b.i - a.i);
      g.appendChild(el('text', {
        x: (pts[0][0] + pts[1][0]) / 2, y: Math.min(pts[0][1], pts[1][1]) - 6,
        'text-anchor': 'middle', fill: colour, 'font-size': 10, 'font-weight': 600,
      }, `${fmt(b.p - a.p, 2)} (${fmtPct(dPct, 2)}) · ${bars} bars`));
    } else if (dr.kind === 'rr' && pts.length === 3) {
      // Entry, stop, target. Drawn as two stacked boxes so the shape itself
      // shows whether the reward is bigger than the risk — which is the only
      // question this tool exists to answer.
      const [entry, stop, target] = dr.points;
      const x1 = frame.xOf(Math.min(entry.i, stop.i, target.i));
      const x2 = frame.margin.l + frame.plotW;
      const yE = frame.yOf(entry.p);
      const yS = frame.yOf(stop.p);
      const yT = frame.yOf(target.p);
      g.appendChild(el('rect', {
        x: x1, y: Math.min(yE, yS), width: x2 - x1, height: Math.abs(yS - yE),
        fill: C.neg, 'fill-opacity': 0.16, stroke: C.neg, 'stroke-width': 1,
      }));
      g.appendChild(el('rect', {
        x: x1, y: Math.min(yE, yT), width: x2 - x1, height: Math.abs(yT - yE),
        fill: C.pos, 'fill-opacity': 0.16, stroke: C.pos, 'stroke-width': 1,
      }));
      const risk = Math.abs(entry.p - stop.p);
      const reward = Math.abs(target.p - entry.p);
      g.appendChild(el('text', {
        x: x1 + 5, y: yE - 5, fill: C.ink, 'font-size': 11, 'font-weight': 600,
      }, `${risk ? fmt(reward / risk, 2) : '—'}R · risk ${fmt(risk, 2)} · reward ${fmt(reward, 2)}`));
    }

    /* An invisible fat twin behind every stroked line, purely to catch the
     * pointer.
     *
     * Measured on a finished trend line: a 1.6px stroke was selectable only
     * within one pixel of its centre. Two pixels either side and the click went
     * through to the chart's hover overlay instead, so clicking a drawing to
     * select or move it missed almost every attempt. That is what "the drawings
     * do not work" actually was, once the layer had stopped swallowing events.
     *
     * Done here by cloning rather than inside the line() helper, so it covers
     * every tool that draws a line without each having to remember: trend, ray,
     * horizontal, vertical, channel, fib, extension, pitchfork, arrow, ruler.
     * Rectangles already take pointer-events: all across their whole area, and
     * handles are circles big enough to grab.
     *
     * stroke: transparent still hit-tests, because pointer-events: stroke asks
     * about the stroke's geometry and not whether it was painted. */
    [...g.querySelectorAll('line')].forEach((ln) => {
      const hit = ln.cloneNode(false);
      hit.setAttribute('stroke', 'transparent');
      hit.setAttribute('stroke-width', DRAW_HIT_WIDTH);
      hit.removeAttribute('stroke-dasharray');
      hit.setAttribute('class', 'ws-dr-hit');
      g.insertBefore(hit, g.firstChild);
    });

    // Handles, only on the selected drawing. Every drawing showing its handles
    // would put twenty grab targets on a chart you are trying to read.
    if (sel) {
      pts.forEach(([x, y], i) => {
        g.appendChild(el('circle', {
          cx: x, cy: y, r: DRAW_HANDLE_R, fill: C.surface,
          stroke: colour, 'stroke-width': 2,
          class: 'ws-dr-handle', 'data-handle': i,
        }));
      });
    }
    root.appendChild(g);
  });

  // The in-progress drawing, so you can see what you are placing.
  if (wsPending && wsPending.points.length) {
    const g = el('g', { class: 'ws-dr ws-dr-pending' });
    wsPending.points.map(P).forEach(([x, y]) => {
      g.appendChild(el('circle', { cx: x, cy: y, r: 3, fill: C.accent }));
    });
    if (wsPending.points.length === 2) {
      const a = P(wsPending.points[0]); const b = P(wsPending.points[1]);
      g.appendChild(el('line', {
        x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: C.accent,
        'stroke-width': 1.4, 'stroke-dasharray': '3 3',
      }));
    }
    root.appendChild(g);
  }

  layer.innerHTML = '';
  layer.appendChild(root);
}

/* ------------------------------------------------------- undo and redo
 *
 * A stack of whole drawing lists rather than a stack of operations. The lists are
 * small — a busy chart has a dozen drawings of a handful of points each — and
 * snapshots are correct by construction, where an operation log has to get every
 * inverse right and silently corrupts the chart when one of them is wrong.
 * Capped so a long session cannot grow it without bound.
 */
const WS_UNDO_MAX = 40;
let wsUndoStack = [];
let wsRedoStack = [];

/** Snapshot before a change. Call this, then mutate. */
function wsPushUndo() {
  wsUndoStack.push(JSON.stringify(wsDrawings()));
  if (wsUndoStack.length > WS_UNDO_MAX) wsUndoStack.shift();
  // Any new edit invalidates the redo branch — the alternative is a tree, and
  // nobody expects redo to resurrect work from a path they abandoned.
  wsRedoStack = [];
}

function wsUndo() {
  if (!wsUndoStack.length) return;
  wsRedoStack.push(JSON.stringify(wsDrawings()));
  wsSaveDrawings(JSON.parse(wsUndoStack.pop()));
  wsSelected = null;
  wsRenderDrawings();
  wsSyncDrawChrome();
}

function wsRedo() {
  if (!wsRedoStack.length) return;
  wsUndoStack.push(JSON.stringify(wsDrawings()));
  wsSaveDrawings(JSON.parse(wsRedoStack.pop()));
  wsSelected = null;
  wsRenderDrawings();
  wsSyncDrawChrome();
}

/** Repaint the bits of chrome that report drawing state, without a full render. */
function wsSyncDrawChrome() {
  const rail = views.chart && views.chart.querySelector('.ws-rail');
  if (rail) rail.outerHTML = wsToolRail();
  const count = views.chart && views.chart.querySelector('[data-ws-draw-count]');
  if (count) count.textContent = String(wsDrawings().length);
  /* The .arming class belongs here, with the rest of the chrome.
   *
   * It was only ever set in the toolbar click handler, while wsTool is assigned
   * in four places. Completing a drawing resets the tool to cursor and calls
   * this function, which rebuilt the rail and left .arming behind — and that
   * class is what keeps pointer-events: auto on the drawing layer.
   *
   * So after drawing one line the whole chart went dead: the draw layer stayed
   * on top and swallowed every pointer event, killing the crosshair, the
   * tooltip, the OHLC header readout, selecting a drawing and dragging one. The
   * tool rail showed the cursor tool as active the entire time, so nothing
   * visible explained it. Escape had the same problem by the same route.
   *
   * Derived from wsTool rather than set alongside it, so the two cannot
   * disagree again no matter where the tool changes. */
  const canvas = views.chart && views.chart.querySelector('.ws-canvas');
  if (canvas) canvas.classList.toggle('arming', wsTool !== 'cursor');
  updateStatus();
}

/* ------------------------------------------------------- pointer handling */

/** Chart coordinates from a pointer event, or null if outside the plot. */
function wsPointAt(evt) {
  const host = document.getElementById('ws-chart');
  const svg = host && host.querySelector('svg.chart');
  const frame = svg && svg.chartFrame;
  if (!frame) return null;
  const box = svg.getBoundingClientRect();
  // The SVG is scaled to its container, so pointer pixels have to be converted
  // into viewBox units before the frame's scales mean anything.
  const scale = box.width / frame.width;
  const px = (evt.clientX - box.left) / scale;
  const py = (evt.clientY - box.top) / scale;
  if (px < frame.margin.l || px > frame.margin.l + frame.plotW) return null;
  if (py < frame.margin.t || py > frame.margin.t + frame.priceH) return null;
  const i = Math.max(0, Math.min(frame.bars - 1, frame.indexAt(px)));
  return { i, p: frame.priceAt(py), frame, px, py };
}

function wsBeginDraw(evt) {
  if (wsTool === 'cursor') return false;
  const at = wsPointAt(evt);
  if (!at) return false;
  const ps = wsSeries(STATE.chartData);
  const price = wsSnapPrice(ps, at.i, at.p, at.frame);

  if (!wsPending) {
    wsPending = { kind: wsTool, points: [] };
  }
  wsPending.points.push({ i: at.i, p: price });

  if (wsPending.points.length >= wsToolNeeds(wsTool)) {
    const dr = {
      id: wsDrawId(),
      kind: wsPending.kind,
      points: wsPending.points,
      color: 'accent',
      width: 1.6,
    };
    if (dr.kind === 'text') {
      // eslint-disable-next-line no-alert
      const t = window.prompt('Note text');
      if (!t) { wsPending = null; wsRenderDrawings(); return true; }
      dr.text = t;
    }
    wsPushUndo();
    wsSaveDrawings([...wsDrawings(), dr]);
    wsPending = null;
    wsSelected = dr.id;
    // Back to the select tool: a tool that stays armed draws a second shape the
    // next time you click to inspect something.
    wsTool = 'cursor';
    wsSyncDrawChrome();
  }
  wsRenderDrawings();
  return true;
}

function wsHitDrawing(evt) {
  const g = evt.target.closest && evt.target.closest('[data-draw]');
  return g ? g.dataset.draw : null;
}

/* Delegated on the document, not attached to the layer.
 *
 * The first version attached pointerdown/move/up to #ws-draw and guarded with a
 * `wired` flag on the element. It did not work, and the reason is worth writing
 * down: renderChartWorkspace replaces the whole view, so the #ws-draw the
 * listeners were bound to gets thrown away and a fresh unwired one takes its
 * place. The flag lives on the element, so it goes with it — but the *call* to
 * re-install only happens from wsMountChart, and any later re-render leaves a
 * layer with no listeners at all. Symptom: the tool arms, the cursor changes,
 * the layer is on top and hit-testable, and clicking does nothing.
 *
 * Delegating removes the whole class of bug: there is one listener for the
 * lifetime of the page and it does not care how many times the layer is rebuilt.
 */
/* ------------------------------------------------------- the navigator
 *
 * The whole series drawn small, with the visible window marked on it. Dragging
 * the window pans, dragging an edge resizes, clicking outside jumps there.
 *
 * Built with raw SVG rather than lineChart: this needs no axes, no hover, no
 * tooltip and no value tags, and passing a chart builder a dozen `false` flags
 * to switch its features off is harder to read than forty lines that draw a
 * path.
 */
const WS_NAV_EDGE = 6;   // grab width for the resize handles, in px

function wsRenderNav() {
  const host = document.getElementById('ws-nav');
  if (!host || !STATE.chartData || STATE.chartData === 'loading') return;
  const full = wsFullSeries(STATE.chartData);
  const closes = full.close || [];
  const total = closes.length;
  const box = host.getBoundingClientRect();
  const W = Math.max(1, Math.round(box.width));
  const H = Math.max(1, Math.round(box.height));
  if (total < 2 || W < 40) { host.innerHTML = ''; return; }

  const vals = closes.filter((v) => v !== null && isFinite(v));
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = (hi - lo) || 1;
  const X = (i) => (i / (total - 1)) * W;
  const Y = (v) => H - 3 - ((v - lo) / span) * (H - 6);

  let d = '';
  closes.forEach((v, i) => {
    if (v === null || !isFinite(v)) return;
    d += `${d ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`;
  });
  const area = d ? `${d}L${W} ${H}L0 ${H}Z` : '';

  const win = wsWindowNow(STATE.chartData);
  const x1 = X(win.from);
  const x2 = X(Math.max(win.from + 1, win.to - 1));

  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <path class="ws-nav-area" d="${area}"/>
    <path class="ws-nav-line" d="${d}"/>
    <rect class="ws-nav-mask" x="0" y="0" width="${Math.max(0, x1).toFixed(1)}" height="${H}"/>
    <rect class="ws-nav-mask" x="${x2.toFixed(1)}" y="0" width="${Math.max(0, W - x2).toFixed(1)}" height="${H}"/>
    <rect class="ws-nav-window" x="${x1.toFixed(1)}" y="0" width="${Math.max(1, x2 - x1).toFixed(1)}" height="${H}"/>
    <rect class="ws-nav-edge" data-nav-edge="from" x="${(x1 - 1).toFixed(1)}" y="0" width="2" height="${H}"/>
    <rect class="ws-nav-edge" data-nav-edge="to" x="${(x2 - 1).toFixed(1)}" y="0" width="2" height="${H}"/>
  </svg>`;
  host.dataset.navFrom = String(x1);
  host.dataset.navTo = String(x2);
  host.dataset.navTotal = String(total);
}

let wsNavDrag = null;

document.addEventListener('pointerdown', (evt) => {
  if (STATE.view !== 'chart') return;
  const host = evt.target.closest && evt.target.closest('#ws-nav');
  if (!host || evt.button !== 0) return;
  evt.preventDefault();
  const box = host.getBoundingClientRect();
  const x = evt.clientX - box.left;
  const total = Number(host.dataset.navTotal || 0);
  const x1 = Number(host.dataset.navFrom || 0);
  const x2 = Number(host.dataset.navTo || 0);
  if (!total) return;
  const win = wsWindowNow(STATE.chartData);
  const barsPerPx = total / Math.max(1, box.width);

  let mode = 'move';
  if (Math.abs(x - x1) <= WS_NAV_EDGE) mode = 'from';
  else if (Math.abs(x - x2) <= WS_NAV_EDGE) mode = 'to';
  else if (x < x1 || x > x2) {
    // A click outside the window centres it there, rather than doing nothing.
    // Jumping is the whole point of an overview strip.
    const spanBars = win.to - win.from;
    const centre = Math.round(x * barsPerPx);
    wsWindow = { from: centre - Math.round(spanBars / 2), to: centre + Math.ceil(spanBars / 2) };
    wsApplyWindow(wsWindow);
    wsRedrawChart();
    return;
  }
  wsNavDrag = { mode, x, from: win.from, to: win.to, barsPerPx, box };
  host.classList.add('dragging');
  host.setPointerCapture && host.setPointerCapture(evt.pointerId);
});

document.addEventListener('pointermove', (evt) => {
  if (!wsNavDrag) return;
  const host = document.getElementById('ws-nav');
  const dx = (evt.clientX - wsNavDrag.box.left) - wsNavDrag.x;
  const bars = Math.round(dx * wsNavDrag.barsPerPx);
  let next;
  if (wsNavDrag.mode === 'move') {
    next = { from: wsNavDrag.from + bars, to: wsNavDrag.to + bars };
  } else if (wsNavDrag.mode === 'from') {
    next = { from: Math.min(wsNavDrag.from + bars, wsNavDrag.to - WS_MIN_BARS), to: wsNavDrag.to };
  } else {
    next = { from: wsNavDrag.from, to: Math.max(wsNavDrag.to + bars, wsNavDrag.from + WS_MIN_BARS) };
  }
  // Resizing writes from/to directly: wsApplyWindow preserves the span, which is
  // right for a pan and wrong for a handle drag.
  const total = Number(host.dataset.navTotal || 0);
  const span = Math.max(WS_MIN_BARS, Math.min(total, next.to - next.from));
  const from = Math.max(0, Math.min(total - span, next.from));
  const settled = { from, to: from + span };
  if (wsWindow && wsWindow.from === settled.from && wsWindow.to === settled.to) return;
  wsWindow = settled;
  wsRedrawChart();
});

document.addEventListener('pointerup', () => {
  if (!wsNavDrag) return;
  wsNavDrag = null;
  const host = document.getElementById('ws-nav');
  if (host) host.classList.remove('dragging');
});

/* ------------------------------------------------------- zoom and pan
 *
 * Wheel zooms about the bar under the cursor; drag moves the window.
 *
 * Anchored on the cursor rather than the centre, because zooming is nearly
 * always aimed at something: centre-anchored zoom slides the thing you were
 * looking at off to one side and you chase it.
 *
 * Both listeners are delegated on the document and installed once at parse
 * time. renderChartWorkspace replaces the whole view, so anything bound to the
 * chart node dies on the next re-render, which is the bug the drawing handlers
 * already carry a long comment about.
 *
 * Drag pans, and the Stocks-style measurement moves to shift-drag. Only one of
 * the two can own a plain drag, and pan is the one people reach for first on a
 * chart with a scroll wheel. Two-finger touch still measures, untouched.
 */
function wsBarUnderCursor(evt) {
  const host = document.getElementById('ws-chart');
  const svg = host && host.querySelector('svg.chart');
  const frame = svg && svg.chartFrame;
  if (!frame) return null;
  const box = svg.getBoundingClientRect();
  const scale = box.width / frame.width;
  const px = (evt.clientX - box.left) / scale;
  if (px < frame.margin.l || px > frame.margin.l + frame.plotW) return null;
  return Math.max(0, Math.min(frame.bars - 1, frame.indexAt(px)));
}

function wsApplyWindow(win) {
  const total = ((wsFullSeries(STATE.chartData).dates) || []).length;
  const next = wsClampWindow(win, total);
  if (!next) return false;
  const prev = wsWindow;
  wsWindow = next;
  // Nothing moved: skip the redraw rather than repaint an identical chart at
  // the edge of the data, which is where a wheel gesture spends its last turns.
  if (prev && prev.from === next.from && prev.to === next.to) return false;
  return true;
}

document.addEventListener('wheel', (evt) => {
  if (STATE.view !== 'chart' || !STATE.chartData || STATE.chartData === 'loading') return;
  const host = evt.target.closest && evt.target.closest('#ws-chart');
  if (!host) return;
  const bar = wsBarUnderCursor(evt);
  if (bar === null) return;
  evt.preventDefault();          // the page must not scroll while zooming

  const cur = wsWindowNow(STATE.chartData);
  const span = cur.to - cur.from;
  // 1.15 per notch. Measured against 1.5, which crossed a year of daily bars
  // in three clicks and overshot constantly.
  const factor = evt.deltaY > 0 ? 1.15 : 1 / 1.15;
  const nextSpan = Math.max(WS_MIN_BARS, Math.min(cur.total, Math.round(span * factor)));
  // Keep the cursor's bar at the same fraction across the plot.
  const anchorIdx = cur.from + bar;
  const frac = span > 1 ? bar / (span - 1) : 0.5;
  const from = Math.round(anchorIdx - frac * (nextSpan - 1));
  if (wsApplyWindow({ from, to: from + nextSpan })) wsRedrawChart();
}, { passive: false });

/* Panning lives in the navigator, not on the plot.
 *
 * A plain drag on the chart used to pan, which meant measuring needed a shift
 * modifier to tell the two apart. That is a rule you have to be told, and it was
 * being told in a hint that had itself been collapsed out of view.
 *
 * The navigator strip fixes it by giving each gesture its own surface: you move
 * the view by dragging the window under the chart, and the plot's drag is free
 * to do the thing a price chart is expected to do, which is read the change
 * between two points. Neither needs a key held down, and both are visible.
 */

function wsResetZoom() {
  if (wsWindow === null) return;
  wsWindow = null;
  wsRedrawChart();
}

function wsInstallDrawHandlers() {
  // Kept as a no-op so the call sites do not have to change. The listeners below
  // are installed once at parse time.
}

document.addEventListener('pointerdown', (evt) => {
  if (STATE.view !== 'chart') return;
  const layer = evt.target.closest && evt.target.closest('#ws-draw');
  if (!layer) return;
  if (wsBeginDraw(evt)) { evt.preventDefault(); return; }
  const id = wsHitDrawing(evt);
  if (!id) { wsSelected = null; wsRenderDrawings(); return; }
  wsSelected = id;
  const handle = evt.target.closest('[data-handle]');
  const dr = wsDrawings().find((x) => x.id === id);
  if (!dr) return;
  wsPushUndo();
  wsDragging = {
    id,
    part: handle ? Number(handle.dataset.handle) : 'all',
    from: wsPointAt(evt),
    original: JSON.parse(JSON.stringify(dr.points)),
  };
  // Captured on the layer so a fast drag that leaves the plot keeps sending
  // moves — without this the drawing stops following the cursor at the edge.
  try { layer.setPointerCapture(evt.pointerId); } catch (e) { /* not capturable */ }
  wsRenderDrawings();
  evt.preventDefault();
});

document.addEventListener('pointermove', (evt) => {
  if (!wsDragging) return;
  const at = wsPointAt(evt);
  if (!at || !wsDragging.from) return;
  const dr = wsDrawings().find((x) => x.id === wsDragging.id);
  if (!dr) return;
  const di = at.i - wsDragging.from.i;
  const dp = at.p - wsDragging.from.p;
  dr.points = wsDragging.original.map((pt, idx) => {
    if (wsDragging.part === 'all' || wsDragging.part === idx) {
      return { i: Math.max(0, pt.i + di), p: pt.p + dp };
    }
    return { ...pt };
  });
  // Not saved per move: pointermove fires dozens of times a second and
  // localStorage writes are synchronous. Saved once, on pointerup.
  wsRenderDrawings();
});

function wsEndDrag() {
  if (!wsDragging) return;
  wsSaveDrawings(wsDrawings());
  wsDragging = null;
  wsSyncDrawChrome();
}
document.addEventListener('pointerup', wsEndDrag);
document.addEventListener('pointercancel', wsEndDrag);

/** Delete or duplicate the selection from the keyboard. */
function wsDrawKeys(evt) {
  if (STATE.view !== 'chart') return;
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((evt.target.tagName || ''));
  if (typing) return;
  const meta = evt.metaKey || evt.ctrlKey;
  if (meta && evt.key.toLowerCase() === 'z') {
    evt.preventDefault();
    if (evt.shiftKey) wsRedo(); else wsUndo();
    return;
  }
  if (meta && evt.key.toLowerCase() === 'y') { evt.preventDefault(); wsRedo(); return; }
  if ((evt.key === 'Delete' || evt.key === 'Backspace') && wsSelected) {
    evt.preventDefault();
    wsPushUndo();
    wsSaveDrawings(wsDrawings().filter((x) => x.id !== wsSelected));
    wsSelected = null;
    wsRenderDrawings();
    wsSyncDrawChrome();
    return;
  }
  if (evt.key === 'Escape') {
    // Cancel a half-placed drawing, and drop the selection.
    wsPending = null; wsSelected = null; wsTool = 'cursor';
    wsRenderDrawings(); wsSyncDrawChrome();
  }
}

/* Guarantee the chart actually got drawn.
 *
 * mount() is asynchronous — it queues against rAF and falls back to a 350ms
 * sweeper — and every redraw issues a fresh job that invalidates the previous
 * one by token. Opening Pulse fires three redraws in quick succession (the CSS
 * reflow handler, the ResizeObserver and rerenderActiveView), and the races
 * between them left the host with a pending token and no SVG: each job found its
 * token superseded and skipped, and the last one landed in a frame where the
 * host had not been laid out yet.
 *
 * Rather than untangle the ordering, this checks the outcome. If the host is
 * measurable and still empty a frame later, build straight into it — the
 * builder is cheap and idempotent, and a chart that is definitely there beats a
 * scheduling scheme that is definitely elegant.
 */
function wsEnsureChart() {
  const host = document.getElementById('ws-chart');
  if (!host || host.querySelector('svg')) return;
  const w = Math.round(host.clientWidth);
  if (!w) return;                       // genuinely not laid out; nothing to do yet
  /* Its OWN builder, not CHART_BUILDERS.
   *
   * The map is only populated on mount()'s deferred path — a host near the
   * viewport goes straight to the rAF queue and never gets an entry. So the
   * first version of this returned immediately in exactly the case it existed
   * for, and the chart stayed blank until something else happened to redraw it.
   *
   * The real trigger turned out to be the 20-second silent refresh: it calls
   * wsRefresh, which rebuilds the workspace and re-mounts, and when that mount
   * raced with anything else the host was left cleared with a superseded token.
   * From the reader's side the chart simply vanished every so often. */
  if (!wsChartBuilder) return;
  if (buildChartNow(host, wsChartBuilder)) settleHost(host);
}

/* A watchdog for the chart itself.
 *
 * There is a race between mount()'s deferred queue and anything that rebuilds
 * the workspace in the same tick — the silent refresh, a width change, a panel
 * toggle. When it bites, the host is left cleared with a superseded token and
 * the chart is blank until something else happens to redraw it, which measured
 * as up to twenty seconds.
 *
 * I could not find the ordering bug despite a long attempt, so this treats the
 * symptom honestly: once a second, if the chart view is active and the host is
 * measurable and empty, draw into it. One cheap DOM query per second, and it
 * turns a twenty-second blank panel into a flicker.
 */
let wsChartWatchdog = null;
function wsStartChartWatchdog() {
  if (wsChartWatchdog) return;
  wsChartWatchdog = setInterval(() => {
    if (STATE.view !== 'chart') return;
    const host = document.getElementById('ws-chart');
    if (!host || host.querySelector('svg') || !host.clientWidth) return;
    wsEnsureChart();
  }, 1000);
}

/** Mount the workspace chart. Separate from the render so a toolbar click can
 *  redraw just the chart without rebuilding the dock and losing its scroll. */
/* How much vertical space the fixed chrome above the workspace takes.
 *
 * Measured rather than assumed: the header, the nav rows and the session bar are
 * all variable — the nav wraps to two lines on a narrow window, and the session
 * bar appears and disappears with the market. A hardcoded 132px was right on
 * exactly one window size and left the chart either overflowing or short
 * everywhere else. Written to a custom property so the CSS keeps ownership of
 * the layout and this only supplies the number.
 */
function wsSyncChromeHeight() {
  const view = views.chart;
  if (!view || !view.classList.contains('active')) return;
  // The VIEW's own offset, not main's. Measured on main it came out 24px short,
  // because main carries 24px of padding above its first child — the workspace
  // then ran 24px past the bottom of the window on every screen.
  const top = Math.round(view.getBoundingClientRect().top + window.scrollY);
  // The legal footer is in normal flow below main and is deliberately NOT
  // subtracted. Shrinking the chart by 110px so a disclosure fits on screen is
  // the wrong trade in the one view whose entire purpose is chart height; it
  // sits below the fold and scrolls to, like any footer.
  document.documentElement.style.setProperty('--chrome-h', `${top}px`);
}

let wsChartBuilder = null;

function wsMountChart() {
  wsSyncChromeHeight();
  const d = STATE.chartData;
  if (!d || d === 'loading' || d.error) return;
  const ps = wsSeries(d);
  const styleOf = (id) => overlayStyle(id);
  const intraday = !!ps.intraday;

  // Kept on a module-level handle so wsEnsureChart can re-run it if the mount
  // is superseded. Reassigned on every call, so it always closes over the
  // current payload rather than a stale one.
  wsChartBuilder = (w) => {
    /* The chart takes the height the layout actually has, not a constant. This
     * is the point of the tab: on a 900px window the Swing chart gets 420px and
     * this gets ~600, which is the difference between reading a trend and
     * squinting at one.
     *
     * Measured from the CANVAS minus the header, not from the chart host itself.
     * mount() empties the host before calling this builder, so at this moment
     * the host has no content and reports a height of zero — measuring it gave
     * 0 every time and the chart silently fell back to the 360px floor. The
     * canvas is the grid cell and its height is real whether or not the chart
     * inside it has been drawn yet. */
    /* Measure the PLOT, which is exactly the box the chart is meant to fill.
     *
     * This used to be canvas-height minus head-height, which was wrong twice
     * over: it forgot the legend, and it forgot that the layout can change shape
     * after the mount. On a narrow column — where the rail moves to a row along
     * the bottom — the numbers disagreed badly: the plot had 570px and the chart
     * was drawn at 160, because the builder measured mid-reflow and baked that
     * into the SVG's height attribute, and nothing re-measured afterwards.
     *
     * The plot's height is right whether or not anything has been drawn into it,
     * so there is no ordering problem to get wrong. The old calculation is kept
     * as a fallback for the case where the plot is not laid out yet. */
    const canvas = document.querySelector('.ws-canvas');
    const head = document.querySelector('.ws-head');
    const legend = document.querySelector('.ws-legend');
    /* The legend is subtracted only when it is in normal flow. At full width it
     * is absolutely positioned over the chart and costs no height; in a narrow
     * column it becomes a real row above it. The old version never subtracted it
     * and overran by however tall it was. */
    const avail = canvas
      ? Math.round(canvas.getBoundingClientRect().height
        - (head ? head.getBoundingClientRect().height : 0)
        - (legend && getComputedStyle(legend).position === 'static'
          ? legend.getBoundingClientRect().height : 0))
      : 0;
    const height = Math.max(avail || 0, 360);
    return lineChart({
      width: w,
      height,
      valueTags: true,
      labels: ps.dates || [],
      volume: showVol ? (ps.volume || null) : null,
      candles: wsCandles(ps) ? {
        open: ps.open || [], high: ps.high || [],
        low: ps.low || [], close: ps.close || [],
      } : null,
      // Levels the workspace draws. Fibs as labelled lines, support and
      // resistance as bands, supply and demand as bands — same functions the
      // Swing chart uses, so the two cannot render the same level differently.
      refLines: intraday ? [] : [
        ...(showFib ? fibLines(((d.technicals || {}).fibonacci || {}).levels,
          (d.technicals || {}).spot) : []),
      ],
      bands: intraday ? [] : [
        ...(showSR ? srBands(((d.technicals || {}).support_resistance || []),
          ((d.technicals || {}).volatility || {}).atr14, (d.technicals || {}).spot) : []),
        ...(showZones ? zoneBands((d.patterns || {})) : []),
      ],
      segments: intraday || !showTrends ? []
        : trendSegments(STATE.trendlines, ps.dates || []),
      series: [
        { name: 'Close', values: ps.close, color: wsCandles(ps) ? C.ink : C.s1,
          hidden: wsCandles(ps), fill: !wsCandles(ps) },
        /* One entry per average, each gated on its own switch, so the six
         * checkboxes in the Indicators menu mean what they say. Excluded
         * wholesale on intraday, as before: these are computed from daily bars
         * and would describe a different timeframe from the one on screen. */
        ...(intraday ? [] : [
          ['sma20', 'SMA 20', ps.sma20], ['sma50', 'SMA 50', ps.sma50],
          ['sma200', 'SMA 200', ps.sma200], ['ema9', 'EMA 9', ps.ema9],
          ['ema21', 'EMA 21', ps.ema21], ['ema50', 'EMA 50', ps.ema50],
        ].filter(([id]) => seriesShown(id)).map(([id, name, values]) => ({
          name, values: values || [], color: styleOf(id).color,
          width: styleOf(id).width, marker: false,
        }))),
      ],
      /* Insider markers and volume-by-price.
       *
       * Both were offered as toggles in the Events and Volume menus and neither
       * was passed to the chart, so switching them on changed a checkbox and
       * nothing else. The Swing chart has drawn both for a long time; this call
       * was simply written without them. Same helpers, so the two tabs cannot
       * disagree about where an insider print sits.
       *
       * Excluded on intraday for the reason the averages are: these are derived
       * from daily bars and would be describing a different timeframe from the
       * one on screen. */
      events: (showInsiders && !intraday)
        ? insiderEvents(ps, ((d.company || {}).ownership || {}).recent_transactions)
        : null,
      volumeProfile: showVbp ? volumeByPrice(ps) : null,
      // Drop a level that sits outside the plotted price range rather than
      // letting it compress the actual price action into a band in the middle.
      refLineFit: 'clip',
      yFormat: (v) => fmt(v, 2),
      valueFormat: (v) => fmt(v, 2),
      onHover: wsHoverReadout,
      sessions: showSessions ? (ps.sessions || ps.dates || null) : null,
    });
  };
  mount('ws-chart', wsChartBuilder);
  // The navigator shows the window the chart is displaying, so it has to be
  // redrawn whenever that window moves.
  wsRenderNav();
  // After the chart, because the drawing layer reads the frame the chart hangs
  // on its own node — there is nothing to convert coordinates against until it
  // exists. The queue in mount() is async, so this waits a frame.
  requestAnimationFrame(() => requestAnimationFrame(() => {
    wsEnsureChart();
    wsStartChartWatchdog();
    wsRenderDrawings();
    wsInstallDrawHandlers();
    wsSyncNarrow();
    wsWatchWidth();
    wsRenderNav();
  }));
}

/** Load a symbol into the workspace.
 *
 * Uses the same /api/ticker payload the Swing tab does, so a symbol already
 * loaded there costs nothing extra — the provider cache serves it.
 */
async function loadChartWorkspace(symbol, force) {
  const sym = String(symbol || STATE.chartSymbol || '').trim().toUpperCase();
  if (!sym) { STATE.chartSymbol = ''; renderChartWorkspace(null); return; }
  if (sym === STATE.chartSymbol && STATE.chartData && !force) {
    renderChartWorkspace(STATE.chartData);
    wsMountChart();
    return;
  }
  STATE.chartSymbol = sym;
  STATE.chartData = 'loading';
  renderChartWorkspace('loading');
  try {
    const data = await getJSON(`/api/ticker/${encodeURIComponent(sym)}`);
    STATE.chartData = data;
  } catch (err) {
    STATE.chartData = { error: err.message };
  }
  if (STATE.view !== 'chart') return;
  renderChartWorkspace(STATE.chartData);
  wsMountChart();
  // The dock's seasonality widget needs its own request; not awaited so the
  // chart is usable while it lands.
  if (wsDockOpen.includes('seasonality')) loadSeasonality(false, sym);
  if (showTrends) loadTrendlines(sym);
}

/* Redraw the workspace chart when Pulse opens or closes.
 *
 * CSS reflows the grid on `body.chat-open`, but the chart is an SVG drawn at a
 * measured pixel width — it does not rescale, it has to be rebuilt. One frame's
 * delay so the new layout has been applied before anything measures it.
 */
function wsOnChatToggle() {
  if (STATE.view !== 'chart') return;
  /* Deliberately does NOT rebuild the chart.
   *
   * The CSS reflow keyed off `body.chat-open` is what fixes the layout, and it
   * needs no JavaScript. Rebuilding on top of it is what I could not get right:
   * every variant — surgical redraw, full wsRefresh, rAF, a 250ms timeout —
   * left the host cleared with no SVG, and the chart only came back on the next
   * silent refresh twenty seconds later. Measured repeatedly; the failure is in
   * mount()'s token/queue interaction with a same-tick DOM rebuild and I have not
   * found it.
   *
   * So the chart is left alone. It keeps the SVG it already has, which is drawn
   * at the previous width and therefore slightly narrow or wide until the next
   * refresh redraws it correctly. A chart at the wrong width is a cosmetic
   * problem; a blank panel is not, and the blank version is what the rebuild
   * produced. Fixing the underlying race is worth doing and is not this change.
   */
  wsSyncChromeHeight();
  wsSyncNarrow();
}

/* Narrow mode for the workspace.
 *
 * The layout is four columns — tool rail, chart, dock, widget rail — and at full
 * width that is right. With Pulse open the workspace gets roughly 520px, and the
 * grid happily gives the dock its 285px and leaves the chart about 100px, which
 * is where the overlapping in the report came from: the chart header and the
 * absolutely-positioned legend end up on top of each other because there is no
 * room for either.
 *
 * So below a threshold the dock is dropped. Not shrunk — dropped, because a
 * 120px-wide news widget is not a smaller version of a useful one. The widget
 * rail stays, so any widget is one click from coming back, and it comes back as
 * an overlay rather than by stealing the chart's width again.
 *
 * A ResizeObserver rather than a media query: the trigger is the WORKSPACE's
 * width, not the viewport's, and those differ by 400px exactly when Pulse is
 * open — which is the case this exists for.
 */
const WS_NARROW_PX = 720;
let wsNarrowObserver = null;

function wsIsNarrow() {
  const body = views.chart && views.chart.querySelector('.ws-body');
  return !!(body && (body.classList.contains('narrow')
    || document.body.classList.contains('chat-open')));
}

function wsSyncNarrow() {
  const body = views.chart && views.chart.querySelector('.ws-body');
  if (!body) return;
  const w = body.getBoundingClientRect().width;
  if (!w) return;
  body.classList.toggle('narrow', w < WS_NARROW_PX);
  // In narrow mode the dock is an overlay and shows only for the one selected
  // widget; wide, it is a column and shows whatever is open.
  body.classList.toggle('dock-open',
    wsIsNarrow() ? !!wsNarrowWidget : wsDockOpen.length > 0);
}

/* The node currently observed, and the width last acted on.
 *
 * Both at module scope because they have to survive this function being called
 * again, and that is the whole bug it used to have.
 *
 * wsMountChart calls wsWatchWidth on every mount. The old version disconnected
 * and rebuilt the observer each time with `last = 0` — and a ResizeObserver
 * always delivers one observation as soon as you observe(), so the callback ran
 * immediately with the real width, compared it against zero, sailed past the
 * 24px jitter guard, and scheduled a redraw 140ms later. That redraw mounted
 * the chart, which called wsWatchWidth, which built another observer with
 * `last = 0` again.
 *
 * The result was a self-sustaining loop at about 7Hz — measured at 77 redraws
 * in 12 idle seconds. It was close to invisible because each redraw produced
 * the same picture, but wsRedrawChart replaces the toolbar with
 * `outerHTML = wsToolbar()`, so every 140ms every button in it was destroyed
 * and recreated. A click needs mousedown and mouseup on the SAME element, so
 * roughly whenever a rebuild landed mid-click the click event was never
 * generated at all: the interval pills, the Indicators checkboxes and the
 * range buttons all "did nothing", intermittently and unreproducibly. */
let wsNarrowObserved = null;
let wsNarrowLastWidth = 0;
let wsNarrowTimer = null;

function wsWatchWidth() {
  const body = views.chart && views.chart.querySelector('.ws-body');
  if (!body || typeof ResizeObserver === 'undefined') return;
  // Already watching this exact node — re-observing it is what caused the loop.
  // renderChartWorkspace replaces .ws-body wholesale, so a genuinely new node
  // still gets picked up here.
  if (wsNarrowObserver && wsNarrowObserved === body) return;
  if (wsNarrowObserver) wsNarrowObserver.disconnect();
  wsNarrowObserved = body;
  // Seeded from the width the element already has, so the observer's initial
  // observation is a no-op instead of a 693px "change" from zero.
  wsNarrowLastWidth = Math.round(body.getBoundingClientRect().width);
  wsNarrowObserver = new ResizeObserver((entries) => {
    const w = Math.round(entries[0].contentRect.width);
    // Scrollbar-sized jitter is not a layout change worth a chart rebuild.
    if (!w || Math.abs(w - wsNarrowLastWidth) < 24) return;
    wsNarrowLastWidth = w;
    wsSyncNarrow();
    clearTimeout(wsNarrowTimer);
    wsNarrowTimer = setTimeout(() => { wsSyncChromeHeight(); wsRedrawChart(); }, 140);
  });
  wsNarrowObserver.observe(body);
}

/** Redraw after a toolbar change: the toolbar and legend rebuild, the chart
 *  re-mounts, the dock is left alone so its scroll and widgets survive. */
let wsResizeTimer = null;
window.addEventListener('resize', () => {
  if (STATE.view !== 'chart') return;
  clearTimeout(wsResizeTimer);
  // Debounced: a drag fires this continuously and each pass rebuilds the chart.
  wsResizeTimer = setTimeout(() => { wsSyncChromeHeight(); wsRedrawChart(); }, 160);
});

/* Redraw the chart and the things that describe it — nothing else.
 *
 * `wsRefresh` used to rebuild the entire view on every toolbar click: toolbar,
 * header, legend, chart and the whole dock, ~430 nodes, including re-rendering
 * the seasonality bars and the key-levels table that had not changed. Two costs,
 * and the second was the one that showed:
 *
 *   - the dock lost its scroll position and any open widget re-flashed
 *   - the new chart host started life with zero width, so buildChartNow could
 *     not measure it, mount() handed it to the 350ms sweeper, and the redraw
 *     landed between a third of a second and 1.4 seconds after the click.
 *     Measured: 533ms, 28ms, 1370ms, 16ms across four consecutive clicks —
 *     the alternation is the sweeper being caught mid-interval.
 *
 * Updating the pieces in place keeps the host alive with a real width, so the
 * build happens on the next frame instead of waiting for a poll.
 */
function wsRedrawChart() {
  if (STATE.view !== 'chart' || !STATE.chartData || STATE.chartData === 'loading') return;
  const d = STATE.chartData;
  const ps = wsSeries(d);

  // The toolbar owns which pill is lit and which menu is open.
  const tb = views.chart.querySelector('.ws-toolbar');
  if (tb) tb.outerHTML = wsToolbar();

  // The legend's values change with the range, so it is rebuilt — but it is
  // ~12 nodes, not 430.
  const leg = views.chart.querySelector('.ws-legend');
  if (leg) leg.outerHTML = wsLegend(ps);

  // A control change is a redraw, not a reveal. The draw-on animation is for
  // content arriving; replaying a 620ms stroke every time someone nudges the
  // range is what "laggy" actually looked like here.
  setChartAnimation(false);
  wsMountChart();
  requestAnimationFrame(() => requestAnimationFrame(wsEnsureChart));
}

/** Full rebuild. Only for a new symbol, where the dock's contents are stale too. */
function wsRefresh() {
  if (STATE.view !== 'chart' || !STATE.chartData || STATE.chartData === 'loading') return;
  renderChartWorkspace(STATE.chartData);
  wsMountChart();
}


/* ------------------------------------------------------------------ forex
 *
 * Fifteen pairs, searchable, each with the mechanism that moves it and what it
 * reads across to. The commentary is the panel, not decoration: EUR/USD at
 * 1.1617 is not information until you know that up is a weaker dollar, that the
 * pair is 58% of the dollar index, and that a stronger dollar trims the reported
 * earnings of every US multinational.
 *
 * Search matches the label, either currency, the group or the driver, because
 * "yen", "carry" and "commodity" are all things someone actually types.
 */
function renderForex(fx) {
  if (!fx) return '';
  if (fx.error) {
    return `<div class="panel span2 gap"><h2>${hg('Currencies')}</h2>
      <p class="sub">${esc(fx.error)}</p></div>`;
  }
  const pairs = fx.pairs || [];
  const groups = fx.groups || [];

  const row = (p) => {
    const s = p.snapshot || {};
    const dec = Math.abs(s.last || 0) < 20 ? 4 : 2;
    return `<tr>
      <td class="name">
        <button type="button" class="tkr" data-instrument="${esc(p.symbol)}"
          data-instrument-label="${esc(p.label)}"
          title="Open the full history for ${esc(p.label)}">${esc(p.label)}</button>
        <div class="fx-sub">${esc(p.base)} / ${esc(p.quote)}</div>
      </td>
      <td>${fmt(s.last, dec)}</td>
      <td class="${signClass(s.chg_1d)}">${fmtPct(s.chg_1d, 2)}</td>
      <td class="${signClass(s.chg_20d)}">${fmtPct(s.chg_20d, 1)}</td>
      <td class="${signClass(s.vs_sma200)}">${fmtPct(s.vs_sma200, 1)}</td>
      <td><span class="fx-driver">${esc(p.driver)}</span></td>
      <td class="fx-means">${esc(p.up_means)}</td>
    </tr>
    <tr class="fx-detail"><td colspan="7">
      <div class="fx-read"><strong>${esc(p.reading)}</strong></div>
      <div class="fx-grid">
        <div><span class="fx-lab">What it is</span>${esc(p.what)}</div>
        <div><span class="fx-lab">What moves it</span>${esc(p.moves_on)}</div>
        <div><span class="fx-lab">Read across to equities</span>${esc(p.equities)}</div>
      </div>
    </td></tr>`;
  };

  return `<div class="panel span2 gap">
    <h2>${hg('Currencies')}</h2>
    <p class="sub">Every pair quoted base/quote, so the price is how many units of
      the second currency buys one of the first. Which way round that is decides
      what a move means, and reading it backwards is the commonest way to
      misinterpret an FX screen. So each row spells out what <em>up</em> means
      rather than leaving it to be inferred.</p>

    <div class="tracker-bar" style="margin-bottom:12px">
      <input id="fx-q" type="search" class="settings-select" style="flex:0 1 260px"
        placeholder="Search. A currency, a group, or a driver"
        value="${esc(fx.query || '')}" aria-label="Search currency pairs">
      <span class="tracker-hint">${fmt(fx.count, 0)} of ${fmt(fx.total, 0)} pairs.
        Try <em>yen</em>, <em>carry</em> or <em>commodity</em>.</span>
    </div>

    ${pairs.length ? groups.map((g) => {
    const inGroup = pairs.filter((p) => p.group === g);
    if (!inGroup.length) return '';
    return `<h3 style="margin-top:var(--space-3)">${hg(g)}</h3>
      <table class="data fx-table">
        <thead><tr><th>Pair</th><th>Last</th><th>1 day</th><th>20 days</th>
          <th>vs 200-day</th><th>Driver</th><th>Up means</th></tr></thead>
        <tbody>${inGroup.map(row).join('')}</tbody>
      </table>`;
  }).join('') : `<div class="callout">${esc(fx.reason || 'Nothing matched.')}</div>`}

    <h3 style="margin-top:var(--space-4)">${hg('The five drivers')}</h3>
    <table class="data">
      <thead><tr><th>Driver</th><th>What it means</th></tr></thead>
      <tbody>${Object.entries(fx.drivers || {}).map(([k, v]) =>
    `<tr><td class="name">${esc(cap(k))}</td>
      <td style="text-align:left;white-space:normal">${esc(v)}</td></tr>`).join('')}</tbody>
    </table>
    <p class="caveat">Nothing here forecasts. Each row describes the mechanism and
      the current reading; where a pair has no defensible read across to US
      equities it says so rather than inventing one. EUR/GBP and USD/INR are two
      that do.</p>
  </div>`;
}

/** Forex loads after the Macro tab, and again on each search. */
async function loadForex(force, query) {
  const q = query === undefined ? (STATE.forexQuery || '') : query;
  if (STATE.forex && !force && q === (STATE.forexQuery || '')) return;
  STATE.forexQuery = q;
  try {
    STATE.forex = await getJSON(`/api/forex?q=${encodeURIComponent(q)}`);
  } catch (err) {
    STATE.forex = { error: err.message };
  }
  const host = document.getElementById('forex-host');
  if (host && STATE.view === 'market') {
    host.innerHTML = renderForex(STATE.forex);
    revealPanels(host);
  }
}

/* ------------------------------------------------------------- stock maps
 *
 * A screen drawn rather than tabulated. Two shapes, and the choice between them
 * is the design: a treemap says "how much of this exists, and what is it doing",
 * a bubble chart says "how do these two measures relate". A treemap cannot show
 * a correlation and a scatter cannot show weight, so both exist.
 *
 * The server does the squarify layout in 0-100 space, so this only has to scale
 * it to the pixels available — which means a resize is a re-scale, not a refetch.
 */
function mapColour(value, domain) {
  if (value === null || value === undefined) return C.grid;
  const { min, max, higher_is_better: hib } = domain || {};
  if (min === null || max === null || min === undefined || max === undefined) return C.grid;
  const span = max - min || 1;
  if (hib === null || hib === undefined) {
    // No good end: a sequential ramp from muted to accent. Using a
    // green-to-red diverging scale on RSI would imply 70 is bad and 30 is good,
    // which is a claim the measure does not make.
    const t = Math.max(0, Math.min(1, (value - min) / span));
    return `color-mix(in srgb, ${C.s1} ${Math.round(t * 85 + 15)}%, ${C.surface})`;
  }
  // Diverging around the midpoint, so the neutral colour lands on the middle of
  // the range rather than on zero — a month where every sector rose should not
  // paint the whole map green.
  const mid = (min + max) / 2;
  const t = Math.max(0, Math.min(1, Math.abs(value - mid) / (span / 2)));
  const good = hib ? value >= mid : value <= mid;
  const hue = good ? C.pos : C.neg;
  return `color-mix(in srgb, ${hue} ${Math.round(t * 78 + 8)}%, ${C.surface})`;
}

function mapValue(v, measure) {
  if (v === null || v === undefined) return '—';
  const unit = (measure || {}).unit || '';
  if (unit === '$') return fmtCompact(v, 1);
  if (unit === '%') return fmtPct(v, 1);
  if (unit === 'x') return fmt(v, 1) + 'x';
  return fmt(v, 1);
}

function renderStockMap(sm) {
  if (!sm) return '';
  if (sm.error) {
    return `<div class="panel span2 gap"><h2>${hg('Stock maps')}</h2>
      <p class="sub">${esc(sm.error)}</p></div>`;
  }
  const tpl = sm.template || {};
  const M = sm.measures || {};
  const dom = sm.colour_domain || {};

  const picker = `<div class="map-picker">${(sm.templates || []).map((t) =>
    `<button type="button" class="pill${t.id === tpl.id ? ' on' : ''}"
      data-map-template="${esc(t.id)}">${esc(t.label)}</button>`).join('')}</div>`;

  let body = '';
  if (tpl.shape === 'tile') {
    const tiles = sm.layout || [];
    body = `<div class="map-tiles" role="img"
      aria-label="${esc(tpl.label)} treemap">
      ${tiles.map((t) => {
    const cv = t.values[tpl.color];
    const sv = t.values[tpl.size];
    // Labels only where the tile can hold them. A ticker overflowing a 2%
    // sliver is worse than an unlabelled sliver you can hover.
    const roomy = t.w > 9 && t.h > 7;
    return `<div class="map-tile" style="left:${t.x}%;top:${t.y}%;
        width:${t.w}%;height:${t.h}%;background:${mapColour(cv, dom)}"
        ${(sm.drillable || []).includes(t.symbol)
    ? `data-map-sector="${esc(t.symbol)}"` : ''}
        data-instrument="${esc(t.symbol)}" data-instrument-label="${esc(t.name)}"
        title="${esc(t.name)} (${esc(t.symbol)}): ${esc((M[tpl.color] || {}).label)}: ${
  mapValue(cv, M[tpl.color])}, ${esc((M[tpl.size] || {}).label)}: ${mapValue(sv, M[tpl.size])}">
        ${roomy ? `<span class="map-tile-sym">${esc(t.symbol)}</span>
          <span class="map-tile-val">${mapValue(cv, M[tpl.color])}</span>` : ''}
      </div>`;
  }).join('')}
    </div>
    <p class="map-legend">Tile size is <strong>${esc((M[tpl.size] || {}).label)}</strong>,
      colour is <strong>${esc((M[tpl.color] || {}).label)}</strong>
      (${mapValue(dom.min, M[tpl.color])} to ${mapValue(dom.max, M[tpl.color])}).
      Colour diverges around the middle of the range, not around zero. A month
      when everything rose should not paint the whole map green.</p>`;
  } else {
    body = `<div id="map-bubbles" class="chart-host"></div>
    <p class="map-legend">Across is <strong>${esc((M[tpl.x] || {}).label)}</strong>,
      up is <strong>${esc((M[tpl.y] || {}).label)}</strong>, bubble size is
      <strong>${esc((M[tpl.size] || {}).label)}</strong>, colour is
      <strong>${esc((M[tpl.color] || {}).label)}</strong>.</p>`;
  }

  return `<div class="panel span2 gap">
    <h2>${hg('Stock maps')}</h2>
    <p class="sub">${esc(tpl.question || '')}</p>
    ${picker}
    <p class="map-universe">${sm.sector
    ? `<button type="button" class="map-crumb" data-map-sector-back>All sectors</button>
       <span class="map-crumb-sep">\u203a</span> <strong>${esc(sm.sector)}</strong> \u00b7 `
    : ''}${esc(sm.universe_label || '')}${
  sm.rows ? ` \u00b7 ${fmt(sm.rows.length, 0)} shown` : ''}${
  sm.sector ? '' : ` \u00b7 <span class="map-hint">click a sector to see the names inside it</span>`}</p>
    ${sm.holdings_caveat ? `<p class="caveat" style="margin:0 0 var(--space-3)">${
  esc(sm.holdings_caveat)}</p>` : ''}
    ${body}
    ${(sm.dropped || []).length ? `<div class="callout" style="margin-top:12px">
      <strong>${fmt(sm.dropped.length, 0)} dropped</strong> for missing measures:
      ${sm.dropped.map((x) => `${esc(x.symbol)} (${esc(x.missing)})`).join(', ')}.
      Dropped rather than drawn at zero. A P/E of nothing plotted at the origin
      reads as "very cheap", which is the opposite of the truth for a company
      with no earnings.</div>` : ''}
    <table class="data" style="margin-top:12px">
      <thead><tr><th>Name</th>
        ${Object.keys(M).map((k) => `<th>${esc(M[k].label)}</th>`).join('')}
      </tr></thead>
      <tbody>${(sm.rows || []).map((r) => `<tr>
        <td class="name"><button type="button" class="tkr"
          data-instrument="${esc(r.symbol)}" data-instrument-label="${esc(r.name)}"
          >${esc(r.symbol)}</button>
          <div style="color:var(--ink-muted);font-size:var(--t-caption)">${esc(r.name)}</div></td>
        ${Object.keys(M).map((k) => `<td>${mapValue(r.values[k], M[k])}</td>`).join('')}
      </tr>`).join('')}</tbody>
    </table>
    <p class="caveat">${gloss('A treemap is unusually good at making a comparison '
    + 'look authoritative, so every measure is named and every raw value is in the '
    + 'table beneath. A tile is only as good as the measure under it: price-to-book '
    + 'means something for a bank and close to nothing for a software company, and '
    + 'a high dividend yield is more often a falling price than a generous board.')}</p>
  </div>`;
}

async function loadStockMap(template, force, sector) {
  const t = template || STATE.stockMapTemplate || 'sector-month';
  // `sector` is undefined for an ordinary load and null to climb back out, so
  // the two cases have to be told apart rather than collapsed with `||`.
  const s = sector === undefined ? (STATE.stockMapSector || null) : (sector || null);
  if (STATE.stockMap && !force && t === STATE.stockMapTemplate
      && s === (STATE.stockMapSector || null)) return;
  STATE.stockMapTemplate = t;
  STATE.stockMapSector = s;
  const host = document.getElementById('stockmap-host');
  if (host) host.innerHTML = `<div class="panel span2 gap">${loadingHTML(
    s ? `${s} holdings` : 'stock map')}</div>`;
  try {
    STATE.stockMap = await getJSON(`/api/stockmap?template=${encodeURIComponent(t)}${
      s ? `&sector=${encodeURIComponent(s)}` : ''}`);
  } catch (err) {
    STATE.stockMap = { error: err.message };
  }
  if (!host || STATE.view !== 'market') return;
  host.innerHTML = renderStockMap(STATE.stockMap);
  mountStockMapChart();
  revealPanels(host);
}

function mountStockMapChart() {
  const sm = STATE.stockMap;
  if (!sm || sm.error) return;
  const tpl = sm.template || {};
  if (tpl.shape !== 'bubble') return;
  const dom = sm.colour_domain || {};
  mount('map-bubbles', (w) => bubbleChart((sm.rows || []).map((r) => ({
    label: r.symbol,
    name: r.name,
    x: r.values[tpl.x],
    y: r.values[tpl.y],
    size: r.values[tpl.size],
    color: mapColour(r.values[tpl.color], dom),
  })), {
    width: w,
    height: Math.min(Math.max(w * 0.6, 320), 480),
    xLabel: (sm.measures[tpl.x] || {}).label || tpl.x,
    yLabel: (sm.measures[tpl.y] || {}).label || tpl.y,
    xUnit: (sm.measures[tpl.x] || {}).unit || '',
    yUnit: (sm.measures[tpl.y] || {}).unit || '',
  }));
}

/* --------------------------------------------------- the other data types
 *
 * Dividends, splits, off-exchange short volume and relative performance. Four
 * small datasets in one panel because they are all per-symbol and none is big
 * enough to earn its own.
 *
 * Two of the items on the original list are absent and the panel says so:
 * dark-pool volume and retail-activity percentage have no free source. Both are
 * sold by vendors who aggregate broker feeds, and the only way to display them
 * would be to guess.
 */
function renderExtras(x) {
  if (!x) return '';
  if (x.error) {
    return `<div class="panel span2 gap"><h2>${hg('Corporate actions & flow')}</h2>
      <p class="sub">${esc(x.error)}</p></div>`;
  }
  const a = x.actions || {};
  const sv = x.short_volume || {};
  const rel = x.relative || {};

  const divBlock = a.pays_dividend ? `
    <h3>${hg('Dividends')}</h3>
    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Latest payment', money((a.dividends.slice(-1)[0] || {}).amount, 2),
    esc((a.dividends.slice(-1)[0] || {}).date || ''))}
      ${tile('Growth streak', `${fmt(a.growth_streak_years, 0)}y`,
    a.last_cut_year ? `last cut ${a.last_cut_year}` : 'no cut on record')}
      ${tile('Annual total', money((a.annual.slice(-1)[0] || {}).total, 2),
    `${(a.annual.slice(-1)[0] || {}).year || ''}. Last complete year`)}
      ${tile('Payments on record', fmt(a.dividends.length, 0), 'most recent 24 shown')}
    </div>
    <table class="data">
      <thead><tr><th>Year</th><th>Total paid</th><th>Change</th></tr></thead>
      <tbody>${(a.annual || []).slice().reverse().map((row, i, arr) => {
    const prev = arr[i + 1];
    const chg = prev && prev.total ? ((row.total - prev.total) / prev.total) * 100 : null;
    return `<tr><td class="name">${row.year}</td><td>${money(row.total, 2)}</td>
      <td class="${signClass(chg)}">${chg === null ? '—' : fmtPct(chg, 1)}</td></tr>`;
  }).join('')}</tbody>
    </table>
    <p class="caveat">${esc(a.note || '')}</p>` : `
    <h3>${hg('Dividends')}</h3>
    <div class="callout">No dividend on record for ${esc(x.ticker)}.</div>`;

  const splitBlock = (a.splits || []).length ? `
    <h3 style="margin-top:var(--space-4)">${hg('Splits')}</h3>
    <table class="data">
      <thead><tr><th>Date</th><th>Ratio</th></tr></thead>
      <tbody>${a.splits.slice().reverse().map((s) =>
    `<tr><td class="name">${esc(s.date)}</td><td>${fmt(s.ratio, 2)}-for-1</td></tr>`).join('')}</tbody>
    </table>` : '';

  const svBlock = (sv.rows || []).length ? `
    <h3 style="margin-top:var(--space-4)">${hg('Off-exchange short volume')}</h3>
    <div class="grid c4" style="margin-bottom:10px">
      ${tile('Latest', fmt(sv.latest_pct, 1) + '%', esc((sv.rows[0] || {}).date || ''))}
      ${tile(`${fmt(sv.days, 0)}-day average`, fmt(sv.average_pct, 1) + '%',
    'this symbol’s own baseline')}
      ${tile('vs its average',
    fmtPct((sv.latest_pct || 0) - (sv.average_pct || 0), 1),
    'percentage points', signClass((sv.average_pct || 0) - (sv.latest_pct || 0)))}
      ${tile('Days on record', fmt(sv.days, 0), 'FINRA publishes daily')}
    </div>
    <p class="caveat"><strong>Read this against its own average, not against 50%.</strong>
      ${esc(sv.caveat || '')}</p>` : `
    <h3 style="margin-top:var(--space-4)">${hg('Off-exchange short volume')}</h3>
    <div class="callout">${esc(sv.error || 'No FINRA rows for this symbol.')}</div>`;

  const relBlock = rel.error ? `
    <h3 style="margin-top:var(--space-4)">${hg('Relative performance')}</h3>
    <div class="callout">${esc(rel.error)}</div>` : `
    <h3 style="margin-top:var(--space-4)">${hg('Relative performance')} <span
      class="th-plain">· vs ${esc(rel.benchmark)}</span></h3>
    <div class="grid c5" style="margin-bottom:10px">
      ${['5d', '20d', '60d', '120d', '252d'].map((k) => tile(k.replace('d', ' days'),
    (rel.excess || {})[k] === null || (rel.excess || {})[k] === undefined
      ? '—' : fmtPct(rel.excess[k], 1),
    'excess return', signClass((rel.excess || {})[k]))).join('')}
    </div>
    <div id="chart-relative" class="chart-host"></div>
    <p class="caveat">${esc(rel.note || '')}</p>`;

  return `<div class="panel span2 gap">
    <h2>${hg('Corporate actions & flow')}</h2>
    <p class="sub">Four datasets that did not have a home: what the company has
      paid out, what it has split, how much of its recent volume printed short
      off-exchange, and how it has done against the index rather than in
      isolation.</p>
    ${divBlock}
    ${splitBlock}
    ${svBlock}
    ${relBlock}
    <p class="caveat">Two items from the same list are deliberately missing.
      <strong>Dark-pool volume</strong> and <strong>retail-activity percentage</strong>
      have no free source. Both are sold by vendors who aggregate broker feeds,
      and the only way to show them here would be to guess. An absent panel beats
      a fabricated one.</p>
  </div>`;
}

async function loadExtras(force) {
  const sym = STATE.ticker;
  if (!sym) return;
  if (STATE.extrasFor === sym && !force) return;
  STATE.extrasFor = sym;
  try {
    STATE.extras = await getJSON(`/api/extras/${encodeURIComponent(sym)}`);
  } catch (err) {
    STATE.extras = { error: err.message };
  }
  const host = document.getElementById('extras-host');
  if (host && STATE.view === 'swing') {
    host.innerHTML = renderExtras(STATE.extras);
    revealPanels(host);
    /* Mount two frames later, not immediately.
     *
     * Fresh HTML in a host goes through the collapsible pass, which re-parents
     * everything into a new .panel-body — and until that has run and laid out,
     * the chart host measures zero width. mount() then hands it to the 350ms
     * sweeper, which found it and settled it without drawing. The symptom was a
     * chart host with no pending token and no SVG, which looks like the mount
     * never happened rather than like it happened too early. */
    requestAnimationFrame(() => requestAnimationFrame(mountRelativeChart));
  }
}

function mountRelativeChart() {
  const rel = (STATE.extras || {}).relative;
  if (!rel || rel.error || !(rel.ratio || []).length) return;
  mount('chart-relative', (w) => lineChart({
    width: w,
    height: 200,
    labels: rel.dates || [],
    series: [{ name: `${rel.ticker} / ${rel.benchmark}`, values: rel.ratio,
      color: C.s1, fill: true }],
    // 100 is where the pair started, so it is the line that matters — above is
    // outperformance, below is not.
    refLines: [{ value: 100, color: C.baseline, label: 'even', emphasis: true }],
    yFormat: (v) => fmt(v, 1),
  }));
}

/* ------------------------------------------------------------ economic data
 *
 * FRED series, plotted in the form they are actually read in. The per-series
 * choice between level and change is the whole point: CPI as a level is a line
 * that only ever rises, and the unemployment rate as a change is noise. Applying
 * one rule to all of them is how an economic chart ends up technically correct
 * and useless, so each series declares its own and the label says which you are
 * looking at.
 */
function renderEcon(e) {
  if (!e) return '';
  const cat = STATE.econCatalogue;
  if (!cat) return '';

  const picker = `<div class="econ-groups">${(cat.groups || []).map((g) => `
    <div class="econ-group">
      <span class="econ-group-lab">${esc(g.label)}</span>
      <div class="econ-pills">${g.series.map((sx) =>
    `<button type="button" class="pill${sx.code === STATE.econCode ? ' on' : ''}"
        data-econ="${esc(sx.code)}" title="${esc(sx.label)} · ${esc(sx.form_label)}"
        >${esc(sx.label)}</button>`).join('')}</div>
    </div>`).join('')}</div>`;

  let body;
  if (!e || e === 'loading') {
    body = loadingHTML('the series');
  } else if (e.error) {
    body = `<div class="callout">${esc(e.error)}</div>`;
  } else {
    const u = e.unit === '$' ? 'bn' : e.unit;
    const val = (v) => (v === null || v === undefined ? '—'
      : `${fmt(v, Math.abs(v) < 10 ? 2 : 1)}${u}`);
    body = `
      <div class="grid c4" style="margin:12px 0">
        ${tile('Latest', val(e.latest.value), esc(e.latest.date))}
        ${tile('Previous', val((e.previous || {}).value),
    e.previous ? esc(e.previous.date) : 'no prior reading')}
        ${tile('Change', e.change === null ? '—' : val(e.change),
    'on the last reading', signClass(e.change))}
        ${tile('12-year average', val(e.average), `range ${val(e.min)} to ${val(e.max)}`)}
      </div>
      <div id="chart-econ" class="chart-host"></div>
      <p class="caveat"><strong>${esc(e.label)}</strong>, ${esc(e.form_label)}.
        ${esc(e.note)}</p>
      <p class="caveat">${esc(e.source)}. No forecast column: FRED publishes what
        was released, and consensus estimates are surveyed and licensed. So this
        can tell you what the number was and what it was last time, and cannot
        tell you what anyone expected.</p>`;
  }

  return `<div class="panel span2 gap">
    <h2>${hg('Economic data')}</h2>
    <p class="sub">${esc(cat.note || '')}</p>
    ${picker}
    ${body}
  </div>`;
}

async function loadEconCatalogue() {
  if (STATE.econCatalogue) return;
  try { STATE.econCatalogue = await getJSON('/api/econ'); }
  catch (err) { STATE.econCatalogue = { groups: [], note: err.message }; }
}

async function loadEcon(code, force) {
  await loadEconCatalogue();
  const c = code || STATE.econCode || 'CPIAUCSL';
  if (STATE.econ && !force && c === STATE.econCode) return;
  STATE.econCode = c;
  const host = document.getElementById('econ-host');
  if (host && STATE.view === 'market') {
    STATE.econ = 'loading';
    host.innerHTML = renderEcon(STATE.econ);
  }
  try { STATE.econ = await getJSON(`/api/econ/${encodeURIComponent(c)}`); }
  catch (err) { STATE.econ = { error: err.message }; }
  if (!host || STATE.view !== 'market') return;
  host.innerHTML = renderEcon(STATE.econ);
  mountEconChart();
  revealPanels(host);
}

function mountEconChart() {
  const e = STATE.econ;
  if (!e || e === 'loading' || e.error || !(e.values || []).length) return;
  mount('chart-econ', (w) => lineChart({
    width: w,
    height: 260,
    labels: e.dates || [],
    series: [{ name: e.label, values: e.values, color: C.s1, fill: true }],
    valueTags: true,
    // Zero matters on a change series and not on a level, so it is drawn only
    // where the series can actually cross it.
    zeroLine: e.form !== 'level' || (e.min !== null && e.min < 0),
    yFormat: (v) => fmt(v, Math.abs(v) < 10 ? 1 : 0),
  }));
}

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
  /* Display names for the asset groups.
   *
   * Spelled out rather than run through cap(), which only uppercases the first
   * letter: 'fx' would render as "Fx". These are acronyms and initialisms, so the
   * mapping is explicit and a new group has to be named deliberately instead of
   * silently arriving lowercase. */
  const GROUP_LABELS = {
    volatility: 'Volatility',
    rates: 'Rates',
    fx: 'FX',
    commodities: 'Commodities',
    credit: 'Credit',
    crypto: 'Crypto',
  };
  const groupLabel = (g) => GROUP_LABELS[g] || cap(g);

  const sectorMax = Math.max(10, ...(s.sectors || []).map((r) => Math.abs(r.composite || 0)));

  // The whole row opens the chart. `data-instrument` is the opt-in: any other
  // table in the terminal gets the same behaviour by carrying these two
  // attributes, without knowing anything about the instrument view.
  const instRow = (r) => `<tr class="inst-clickable" data-instrument="${esc(r.symbol || '')}"
    data-instrument-label="${esc(r.label || '')}" tabindex="0" role="button"
    title="Open the full chart for ${esc(r.label || '')}">
    <td class="name"><span class="inst-link">${esc(cap(r.label))}</span><div class="subnote">${esc(cap(r.note) || '')}</div></td>
    <td>${fmt(r.last, r.last && r.last < 10 ? 4 : 2)}</td>
    <td class="${signClass(r.chg_1d)}">${fmtPct(r.chg_1d, 2)}</td>
    <td class="${signClass(r.chg_5d)}">${fmtPct(r.chg_5d, 2)}</td>
    <td class="${signClass(r.chg_20d)}">${fmtPct(r.chg_20d, 2)}</td>
    <td class="${signClass(r.vs_sma200)}">${fmtPct(r.vs_sma200, 1)}</td>
    <td>${fmt(r.rsi, 0)}</td>
    <td><span data-spark='${esc(JSON.stringify(r.series || []))}'></span></td>
  </tr>`;

  views.market.innerHTML = `
  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Macro regime')}</h2>
      <p class="sub">${esc(m.stance || '')}</p>
      <div style="display:flex;align-items:flex-end;gap:var(--space-5);flex-wrap:wrap">
        <div>
          <div class="hero-label">Risk score</div>
          <div class="hero ${signClass(m.risk_score)}">${m.risk_score > 0 ? '+' : ''}${fmt(m.risk_score, 0)}</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:var(--space-2)">
          ${toneChip(m.regime)}
          ${m.curve_3m10y !== null && m.curve_3m10y !== undefined
    ? `<span class="chip ${m.curve_3m10y < 0 ? 'bear' : 'neutral'}"><span class="dot"></span>3m/10y curve ${fmt(m.curve_3m10y, 2)}</span>` : ''}
          <span class="chip neutral"><span class="dot"></span>VIX ${fmt((inst['^VIX'] || {}).last, 1)}</span>
        </div>
      </div>
      <h3>${hg('What\'s driving it')}</h3>
      <ul class="reasons">${(m.notes || []).map((n) => `<li>${gloss(n)}</li>`).join('')}</ul>
      ${macroFactors(m)}
    </div>

    <!-- Breadth and rotation only. Equal-weight vs cap-weight moved to its own
         full-width panel below: this panel was carrying three separate topics and
         ran 832px against the 315px macro-regime panel beside it, which is where
         the 447x517 void on this tab came from. Splitting it balances the row and
         gives the chart the width it actually wants. -->
    <div class="panel">
      <h2>${hg('Market breadth')}</h2>
      <p class="sub">${gloss((s.breadth || {}).note || '')}</p>
      <div class="grid c2">
        ${tile('Sectors above 200-day', fmt((s.breadth || {}).pct_sectors_above_200sma, 0) + '%')}
        ${tile('Sectors above 50-day', fmt((s.breadth || {}).pct_sectors_above_50sma, 0) + '%')}
      </div>
      <h3>${hg('Rotation')}</h3>
      <p style="color:var(--ink-2);font-size:var(--t-body);margin:0">${gloss(s.rotation_note || '')}</p>
      ${(s.suggested_pair || {}).long ? `<div class="callout info">Cleanest expression right now:
        <strong>long ${esc(s.suggested_pair.long)} / short ${esc(s.suggested_pair.short)}</strong>. ${esc(s.suggested_pair.note)}</div>` : ''}
    </div>
  </div>

  <div id="rotation-host" class="span-all">${renderRotation(STATE.rotation)}</div>

  <div id="econ-host" class="span-all">${renderEcon(STATE.econ)}</div>

  <div id="stockmap-host" class="span-all">${renderStockMap(STATE.stockMap)}</div>

  <div id="forex-host" class="span-all">${renderForex(STATE.forex)}</div>

  ${evc.note ? `<div class="panel gap">
    <h2>${hg('Equal-weight vs cap-weight (RSP / SPY)')} <span class="th-plain">· daily bars</span></h2>
    <p class="sub">${gloss(evc.note)}</p>
    <div class="grid c4">
      ${tile('RSP / SPY over 3 months', fmtPct(evc.chg_3m_pct, 1), 'equal-weight vs cap-weight', signClass(evc.chg_3m_pct))}
      ${tile('Over 1 year', fmtPct(evc.chg_1y_pct, 1), 'equal-weight vs cap-weight', signClass(evc.chg_1y_pct))}
    </div>
    <div id="chart-breadth"></div>
  </div>` : ''}

  <div class="panel gap">
    <h2>${hg('Cross-asset dashboard')} <span class="th-plain">· daily bars</span></h2>
    <p class="sub">Level, momentum across three horizons, position versus the 200-day, and a 90-day trace.</p>
    ${groupOrder.filter((g) => (m.groups || {})[g]).map((g) => `
      <h3>${hg(groupLabel(g))}</h3>
      <table class="data">
        <thead><tr><th>Instrument</th><th>Last</th><th>1d</th><th>5d</th><th>20d</th><th>vs 200d</th><th>RSI</th><th>90-day</th></tr></thead>
        <tbody>${m.groups[g].filter((r) => !r.error).map(instRow).join('')}</tbody>
      </table>`).join('')}
  </div>

  <div class="panel gap">
    <h2>${hg('Cross-asset ratios')} <span class="th-plain">· daily bars</span></h2>
    <p class="sub">Ratio lines carry the regime signal that absolute levels hide.</p>
    <div class="grid c2">
      ${(m.ratios || []).map((r, i) => `<div>
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:var(--space-3)">
          <strong style="font-size:var(--t-body)">${esc(r.name)}</strong>
          ${toneChip(r.signal)}
        </div>
        <div style="color:var(--ink-muted);font-size:var(--t-small);margin:var(--space-0) 0 var(--space-2)">${esc(r.reads)}</div>
        <div style="display:flex;gap:var(--space-4);font-size:var(--t-small);font-variant-numeric:tabular-nums;margin-bottom:var(--space-1)">
          <span>5d <span class="${signClass(r.chg_5d)}">${fmtPct(r.chg_5d, 1)}</span></span>
          <span>20d <span class="${signClass(r.chg_20d)}">${fmtPct(r.chg_20d, 1)}</span></span>
          <span>60d <span class="${signClass(r.chg_60d)}">${fmtPct(r.chg_60d, 1)}</span></span>
        </div>
        <div id="ratio-chart-${i}"></div>
      </div>`).join('')}
    </div>
  </div>

  <div class="grid c2 gap">${renderCorrelation(STATE.correlation)}</div>

  ${renderSectorBoard(STATE.sectorBoard)}

  <div class="grid c2 gap">
    <div class="panel span2">
      <h2>${hg('Sector relative strength')}</h2>
      <p class="sub">Ranked on the ratio line against ${esc(s.benchmark || 'SPY')}. Leadership, not beta. Composite blends 1-week to 6-month relative strength with trend confirmation.</p>
      <table class="data">
        <thead><tr><th>#</th><th>Sector</th><th>Composite</th><th></th><th>RS 1w</th><th>RS 1m</th><th>RS 3m</th><th>RS 6m</th><th>RSI</th><th>vs 50d</th><th>vs 200d</th><th>Strength</th></tr></thead>
        <tbody>${(s.sectors || []).map((r) => `<tr>
          <td>${r.rank}</td>
          <td class="name">${esc(r.name)} <span class="muted">${esc(r.symbol)}</span></td>
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

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Themes & sub-industries')}</h2>
      <p class="sub">Same ranking method applied to narrower baskets, where rotation shows up first.</p>
      <table class="data">
        <thead><tr><th>#</th><th>Theme</th><th>Composite</th><th>RS 1m</th><th>RS 3m</th><th>RSI</th><th>Breakout</th></tr></thead>
        <tbody>${(s.themes || []).map((r) => `<tr>
          <td>${r.rank}</td>
          <td class="name">${esc(r.name)} <span class="muted">${esc(r.symbol)}</span></td>
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
      <p class="sub">Coiled near a range high, in a volatility squeeze, with momentum in the constructive band. All three together. Any one alone is noise.</p>
      ${(s.breakout_candidates || []).map((r) => `<div style="padding:var(--space-2) 0;border-bottom:1px solid var(--grid)">
        <div style="display:flex;justify-content:space-between;gap:var(--space-3);align-items:baseline">
          <strong>${esc(r.symbol)} <span style="color:var(--ink-2);font-weight:400">${esc(r.name)}</span></strong>
          <span class="chip ${r.breakout_ready ? 'bull' : 'neutral'}"><span class="dot"></span>Score ${fmt(r.breakout_score, 0)}</span>
        </div>
        <ul class="reasons">${(r.breakout_reasons || []).map((x) => `<li>${gloss(x)}</li>`).join('')}</ul>
      </div>`).join('') || '<div class="muted">Nothing is set up cleanly right now. That is itself information.</div>'}
    </div>
  </div>

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Niche industries')}</h2>
      <p class="sub">One level narrower than the themes above. Single sub-industries and thematic baskets
        (memory chips, uranium, cybersecurity, rare earths...) that rotation often reaches before it shows
        up in the broader sector or theme ETFs.</p>
      <table class="data">
        <thead><tr><th>#</th><th>Niche</th><th>Composite</th><th>RS 1m</th><th>RS 3m</th><th>RSI</th><th>Breakout</th></tr></thead>
        <tbody>${(s.niche || []).map((r) => `<tr>
          <td>${r.rank}</td>
          <td class="name">${esc(r.name)} <span class="muted">${esc(r.symbol)}</span></td>
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

  if (STATE.rotation && !STATE.rotation.error) {
    mount('chart-rotation', (w) => rotationChart(STATE.rotation.sectors || [], {
      width: w, height: Math.min(Math.max(w * 0.72, 380), 560),
    }));
  }

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


function meterHTML(score, color) {
  const pct = Math.max(0, Math.min(100, score || 0));
  return `<div style="background:var(--surface-2);height:8px;border-radius:4px;overflow:hidden;margin-top:var(--space-1)">
    <div style="width:${pct}%;height:100%;background:${color};transition:width 0.3s ease"></div>
  </div>`;
}

/* ================================================================= EARNINGS */

/* Render a paragraph array that may carry "## " heading lines.
 *
 * The model returns prose as an array of paragraphs, some of which are section
 * headings. Escaping each one and wrapping it in <p> — which is what the morning
 * desk did — puts a literal "## What happened" on the page, so this splits the
 * two cases and runs inline markdown over the rest for the bolded figure. */
function briefProse(paragraphs) {
  return (paragraphs || []).map((raw) => {
    const t = String(raw).trim();
    if (!t) return '';
    const h = t.match(/^#{2,3}\s+(.*)$/);
    if (h) return `<h3 class="prose-h">${esc(h[1])}</h3>`;
    return `<p>${mdLite(t)}</p>`;
  }).join('');
}

/* The written pre-earnings brief.
 *
 * Fetched separately from the panel it sits above. The panel's own figures are
 * computed locally in well under a second; a model call is neither that fast nor
 * that certain to arrive, and blocking the table on the prose would make the
 * fast half look as slow as the slow half. So the numbers render, then this
 * fills in above them.
 *
 * Nothing here is load-bearing. Every figure the brief discusses is already in
 * the tables below it, so when it fails the reader loses commentary, not data —
 * which is why the failure state is one quiet line rather than an error box. */
const EARN_STANCE_CLASS = {
  'leaning bullish': 'up', 'leaning bearish': 'down', 'two-sided': 'flat',
};

/* The earnings week.
 *
 * Shown when no ticker is loaded, because "who reports this week" is the
 * question a reader has BEFORE they have picked a name — and the tab used to
 * answer it with "no ticker loaded", which is a dead end where a calendar
 * belongs.
 *
 * Grouped by day and not by session: the provider gives a date with no
 * before-open or after-close tag, and a name filed under the wrong session is
 * worse than one filed under neither. Every ticker is a link into the full
 * analysis, so the calendar is also the way in. */
/* Side-by-side comparison.
 *
 * Its own tab because it answers a question no per-ticker page can: "which of
 * these". That needs the same metrics computed the same way at the same moment
 * for every name, which is exactly what opening two tabs and eyeballing them
 * fails to guarantee.
 *
 * Three horizons ranked separately, and the interesting output is when they
 * disagree — a name can top the swing ranking and come last multi-year. A single
 * blended "winner" would hide that, so there isn't one. */
/* The metric rows, grouped.
 *
 * Grouped because an ungrouped list of twenty numbers makes the reader do the
 * sorting: "vs 200-day" and "worst drawdown on record" are both percentages
 * with a minus sign and they answer completely different questions. The headings
 * say which question each block answers.
 *
 * `means` is the one-line reading. It is on every row rather than the few that
 * seemed obscure, because which ones are obscure depends on the reader.
 *
 * `lead` marks the higher or lower value where the direction genuinely has a
 * meaning — "cheaper", "less volatile", "compounded faster". It is deliberately
 * absent on RSI (mid-range is the good part, so neither end wins), on distance
 * from a moving average (further above is stronger trend and worse entry at the
 * same time) and on beta and implied vol (higher is not worse, it is different).
 * A marker on those would be inventing a verdict. */
const CMP_GROUPS = [
  {
    title: 'Where it trades',
    rows: [
      { key: 'price', label: 'Price', kind: 'usd',
        means: 'Last close.' },
      { key: 'change_pct', label: 'Today', kind: 'pct',
        means: 'One session. Shown for context and kept out of the position and '
          + 'long-term scores.' },
    ],
  },
  {
    title: 'Momentum and trend',
    rows: [
      { key: 'rsi', label: 'RSI (14)', kind: 'num0',
        means: 'Above 70 is stretched, below 30 is washed out, 50 is neutral. '
          + 'The middle-upper 50s to 60s is the trending zone.' },
      { key: 'rs_vs_spy', label: 'Versus SPY, 21 sessions', kind: 'pct', lead: 'high',
        means: 'How much it beat or lagged the index over the last month.' },
      { key: 'vs_sma20', label: 'Above / below the 20-day', kind: 'pct',
        means: 'Short-term trend. Far above means extended, below means the '
          + 'near-term trend has broken.' },
      { key: 'vs_sma50', label: 'Above / below the 50-day', kind: 'pct',
        means: 'The line most swing traders watch for whether the trend is intact.' },
      { key: 'vs_sma200', label: 'Above / below the 200-day', kind: 'pct',
        means: 'The dividing line between a long uptrend and a long downtrend.' },
      { key: 'vs_sma40w', label: 'Above / below the 40-week', kind: 'pct',
        means: 'The same idea on a weekly chart. Slower, and harder to whipsaw.' },
    ],
  },
  {
    title: 'How much it moves',
    rows: [
      { key: 'atr_pct', label: 'Typical daily range', kind: 'pct_plain',
        means: 'How far it travels on an average day, as a share of price. '
          + 'Sets how wide a stop has to be.' },
      { key: 'iv_pct', label: 'Implied volatility', kind: 'pct_plain',
        means: 'What the option market is charging for future movement.' },
      { key: 'hv_pct', label: 'Realised volatility, 20 sessions', kind: 'pct_plain',
        means: 'What it actually did. Implied above realised means options are '
          + 'priced for more movement than has been happening.' },
      { key: 'annual_vol_pct', label: 'Annualised volatility', kind: 'pct_plain',
        means: 'The same measure over the full history, used in the return-per-'
          + 'unit-of-vol figure below.' },
      { key: 'beta_vs_spy', label: 'Beta versus SPY', kind: 'num2',
        means: 'Roughly how much it moves for a 1% index move. Above 1 amplifies '
          + 'the market, below 1 dampens it.' },
    ],
  },
  {
    title: 'What it costs',
    rows: [
      { key: 'forward_pe', label: 'Forward P/E', kind: 'num1',
        means: 'Price against next year’s expected earnings. Lower is cheaper, '
          + 'which is not the same as better. A low multiple often means low '
          + 'expected growth.' },
      { key: 'pe_percentile', label: 'That multiple against its own past',
        kind: 'pctile', lead: 'low', sub: 'pe_read',
        means: 'Where today’s multiple sits in this company’s own range. 25th '
          + 'means cheaper than it has been three quarters of the time.' },
    ],
  },
  {
    title: 'The multi-year record',
    rows: [
      { key: 'cagr_5y_pct', label: 'Five-year return', kind: 'pct', lead: 'high',
        note: 'per year',
        means: 'Annualised, so a name listed for five years and one listed for '
          + 'twenty are comparable.' },
      { key: 'excess_cagr_5y_pct', label: 'Five-year return versus SPY', kind: 'pct',
        lead: 'high', note: 'per year',
        means: 'The part of that return the index did not give you. Negative means '
          + 'the index would have done better.' },
      { key: 'cagr_per_vol_5y', label: 'Return per unit of volatility', kind: 'num2',
        lead: 'high', note: 'SPY ≈ 0.65',
        means: 'How much of that return you were paid per unit of turbulence. '
          + 'Two names can compound at the same rate through very different rides.' },
      { key: 'drawdown_pct', label: 'Below the all-time high', kind: 'pct',
        means: 'Where it sits now versus its own peak. Near the high is a stronger '
          + 'trend; far below it leaves more room to recover.' },
      { key: 'max_drawdown_pct', label: 'Worst fall on record', kind: 'pct_neutral',
        lead: 'high',
        means: 'The deepest peak-to-trough this name has actually put a holder '
          + 'through. What a bad stretch looks like here.' },
      { key: 'trend_phase', label: 'Multi-year phase', kind: 'text',
        means: 'Where the weekly chart sits against its long averages.' },
    ],
  },
  {
    title: "Optic's own score",
    rows: [
      { key: 'composite', label: 'Composite', kind: 'signed', lead: 'high',
        means: 'The swing-tab score for this name. Included so you can see whether '
          + 'it agrees with the horizon ranks above.' },
    ],
  },
];

const CMP_ROWS = CMP_GROUPS.flatMap((g) => g.rows);

function cmpCell(kind, v) {
  if (v === null || v === undefined || v === '') return '<span class="cmp-na">—</span>';
  if (kind === 'text') return esc(String(v));
  if (kind === 'usd') return '$' + fmt(v, 2);
  if (kind === 'pct') return `<span class="${signClass(v)}">${v > 0 ? '+' : ''}${fmt(v, 2)}%</span>`;
  if (kind === 'pct_plain') return fmt(v, 1) + '%';
  if (kind === 'pct_neutral') return fmt(v, 2) + '%';
  if (kind === 'pctile') return fmt(v, 0) + 'th';
  if (kind === 'num0') return fmt(v, 0);
  if (kind === 'num1') return fmt(v, 1);
  if (kind === 'num2') return fmt(v, 2);
  if (kind === 'signed') return `<span class="${signClass(v)}">${v > 0 ? '+' : ''}${fmt(v, 0)}</span>`;
  return fmt(v, 2);
}

/* Which cell leads a row, where "leads" is defined for that metric.
 *
 * Returns the ticker or null. Null when the row has no defined direction, when
 * fewer than two names have the figure, or when the two are close enough that
 * calling one of them the leader would be reading precision that is not there —
 * the threshold is 2% of the spread across the row, stated in the legend. */
function cmpLeader(row, cols) {
  if (!row.lead) return null;
  const vals = cols.map((r) => r[row.key]).filter((v) => typeof v === 'number' && Number.isFinite(v));
  if (vals.length < 2) return null;
  const best = row.lead === 'high' ? Math.max(...vals) : Math.min(...vals);
  const rest = vals.filter((v) => v !== best);
  const runnerUp = row.lead === 'high' ? Math.max(...rest) : Math.min(...rest);
  const spread = Math.max(...vals) - Math.min(...vals);
  if (spread === 0 || Math.abs(best - runnerUp) < spread * 0.02) return null;
  const hit = cols.find((r) => r[row.key] === best);
  return hit ? hit.ticker : null;
}

/* Two scores this close are the same score. 5 points on a 0-100 scale is inside
 * the noise of the inputs — an RSI reading a point different moves a horizon
 * score by more than that — so the panel says "level" rather than naming a
 * winner it cannot support. */
const CMP_TIE_POINTS = 5;

function cmpRankRead(hid, c) {
  const ranks = (c.ranks || {})[hid] || [];
  if (ranks.length < 2) return '';
  const [first, second] = ranks;
  const gap = first.score - second.score;
  if (gap < CMP_TIE_POINTS) {
    return `${esc(first.ticker)} and ${esc(second.ticker)} are level here `
      + `(${fmt(first.score, 0)} against ${fmt(second.score, 0)}). Too close to separate.`;
  }
  return `${esc(first.ticker)} leads, ${fmt(gap, 0)} points clear of ${esc(second.ticker)}.`;
}

/* Loading. A skeleton of the table that is coming rather than a line of text in
 * an empty box: the panel keeps the height and shape it is about to have, so the
 * page does not jump when the numbers land, and the reader can see what is being
 * assembled. */
function cmpSkeleton(names) {
  const cols = names.length || 2;
  return `<div class="panel span-all cmp-loading" aria-busy="true">
    <p class="loading"><span class="spinner"></span>Pulling ${
  names.length ? names.map((n) => esc(n)).join(' and ') : 'both names'} in full.
      The same analysis the Swing and Long-Term tabs run, for each name.</p>
    <div class="cmp-skel" aria-hidden="true">
      ${Array.from({ length: 9 }, (_, row) => `<div class="cmp-skel-row"
        style="grid-template-columns:minmax(140px,2fr) repeat(${cols}, minmax(70px,1fr))">
        <span class="cmp-skel-bar lbl" style="animation-delay:${row * 70}ms"></span>
        ${Array.from({ length: cols }, (__, i) => `<span class="cmp-skel-bar"
          style="animation-delay:${(row * cols + i) * 70}ms"></span>`).join('')}
      </div>`).join('')}
    </div>
  </div>`;
}

function renderCompare(c) {
  const inputs = (STATE.compareInputs || ['', '']).map((v, i) => `
    <input class="cmp-input" data-cmp-input="${i}" value="${esc(v)}"
      placeholder="TICKER ${i + 1}" spellcheck="false" autocomplete="off"
      aria-label="Ticker ${i + 1}">`).join('');

  const head = `<div class="panel span-all">
    <div class="weekly-kicker">Compare tickers</div>
    <h2 class="weekly-title">Side-by-side${askPulse('compare')}</h2>
    <p class="weekly-sub">Two to four stocks or ETFs ranked across momentum, technical
      structure, volatility and longer-term value. The three horizons are scored separately,
      so a name can lead one and trail another. That disagreement is the useful part.</p>
    ${(c && c.horizons || []).length ? `<div class="grid c3" style="margin-top:var(--space-4)">
      ${c.horizons.map((h) => `<div class="cmp-hz">
        <div class="idx-lbl">${esc(h.name)}</div>
        <div class="cmp-hz-h">Horizon: ${esc(h.horizon)}</div>
        <p class="cmp-hz-b">${esc(h.basis)}</p>
      </div>`).join('')}
    </div>` : ''}
    <div class="cmp-controls">
      ${inputs}
      <button type="button" class="btn" data-cmp-run>Compare</button>
      ${(STATE.compareInputs || []).length < 4
    ? '<button type="button" class="bulk-btn" data-cmp-add>+ Add ticker</button>' : ''}
      ${(STATE.compareInputs || []).length > 2
    ? '<button type="button" class="bulk-btn" data-cmp-drop>− Remove</button>' : ''}
    </div>
  </div>`;

  if (c === 'loading') {
    return head + cmpSkeleton((STATE.compareInputs || [])
      .map((v) => String(v || '').toUpperCase().trim()).filter(Boolean));
  }
  if (!c) {
    return head + `<div class="panel span-all"><p class="sub">Enter two tickers and press
      Compare. Nothing is fetched until you do.</p></div>`;
  }
  if (!c.available) {
    const why = (c.failed || []).map((f) => `${esc(f.ticker)} · ${esc(f.reason)}`);
    return head + `<div class="panel span-all"><div class="callout">${
  esc(c.reason || 'Not enough names loaded to compare.')}${
  why.length ? '<br>' + why.join('<br>') : ''}</div></div>`;
  }

  const cols = c.rows || [];
  const rankRow = (hid) => {
    const ranks = (c.ranks || {})[hid] || [];
    const byTicker = Object.fromEntries(ranks.map((r) => [r.ticker, r]));
    const hz = (c.horizons || []).find((h) => h.id === hid) || {};
    return `<tr class="cmp-rank">
      <td class="name">${esc(hz.name || hid)}
        <span class="cmp-means">${cmpRankRead(hid, c)}</span></td>
      ${cols.map((r) => {
    const hit = byTicker[r.ticker];
    if (!hit) return '<td class="num"><span class="cmp-na">—</span></td>';
    return `<td class="num"><span class="cmp-badge${hit.rank === 1 ? ' win' : ''}">${
      hit.rank === 1 ? 'best' : '#' + hit.rank}</span> ${fmt(hit.score, 0)}</td>`;
  }).join('')}
    </tr>`;
  };

  const metricRow = (m) => {
    const leader = cmpLeader(m, cols);
    return `<tr>
      <td class="name">${hg(m.label)}${m.note
    ? `<span class="cmp-note">${esc(m.note)}</span>` : ''}
        <span class="cmp-means">${esc(m.means || '')}</span></td>
      ${cols.map((r) => `<td class="num${leader === r.ticker ? ' cmp-lead' : ''}">${
    cmpCell(m.kind, r[m.key])}${leader === r.ticker
    ? `<span class="cmp-lead-dot" title="${m.lead === 'high' ? 'Higher' : 'Lower'} on this measure">·</span>`
    : ''}${m.sub && r[m.sub]
    ? `<span class="cmp-sub-read">${esc(r[m.sub])}</span>` : ''}</td>`).join('')}
    </tr>`;
  };

  const anyLead = CMP_ROWS.some((m) => m.lead && cmpLeader(m, cols));

  return head + `<div class="panel span-all">
    <div class="table-scroll">
    <table class="data cmp-table">
      <thead><tr><th>Metric</th>${cols.map((r) => `<th class="num">
        <button type="button" class="tkr" data-analyse="${esc(r.ticker)}">${esc(r.ticker)}</button>
        <span class="cmp-name">${esc(r.name && r.name !== r.ticker ? r.name : '')}</span>
        <span class="cmp-sector">${esc(r.sector || '')}</span>
      </th>`).join('')}</tr></thead>
      <tbody>
        ${(c.horizons || []).map((h) => rankRow(h.id)).join('')}
        ${CMP_GROUPS.map((g) => `<tr class="cmp-group"><td colspan="${cols.length + 1}">${
  esc(g.title)}</td></tr>${g.rows.map(metricRow).join('')}`).join('')}
      </tbody>
    </table>
    </div>
    ${(c.failed || []).length ? `<div class="callout">Could not load: ${
  c.failed.map((f) => `${esc(f.ticker)} (${esc(f.reason)})`).join(', ')}.</div>` : ''}
    ${anyLead ? `<p class="caveat">A dot marks the higher or lower reading on the rows where
      that direction means something. Cheaper, less turbulent, compounded faster. Rows
      without one have no better end: mid-range is the good part of RSI, and a higher beta or
      a richer implied vol is a different stock, not a worse one. Marks are dropped when the
      two readings are within 2% of the row's spread.</p>` : ''}
    <p class="caveat">${gloss(c.method || '')}</p>
  </div>`;
}

async function loadCompare(force) {
  if (STATE.compare && !force) { views.compare.innerHTML = renderCompare(STATE.compare); return; }
  views.compare.innerHTML = renderCompare(STATE.compare || null);
  revealPanels(views.compare);
}

async function runCompare() {
  const wanted = (STATE.compareInputs || [])
    .map((v) => String(v || '').toUpperCase().trim()).filter(Boolean);
  if (wanted.length < 2) {
    STATE.compare = { available: false, reason: 'Give at least two tickers.' };
    views.compare.innerHTML = renderCompare(STATE.compare);
    return;
  }
  views.compare.innerHTML = renderCompare('loading');
  try {
    STATE.compare = await getJSON(`/api/compare?tickers=${encodeURIComponent(wanted.join(','))}`);
  } catch (err) {
    STATE.compare = { available: false, reason: err.message };
  }
  views.compare.innerHTML = renderCompare(STATE.compare);
  revealPanels(views.compare);
}

/* A company logo, high-resolution where one exists, with a monogram underneath.
 *
 * The monogram is rendered first and the image sits on top of it. That ordering
 * matters: every logo service misses some companies, and an <img> that fails
 * leaves a broken icon — here the failure reveals a finished design instead.
 *
 * SOURCES, in the order tried, chosen by measuring all seven of this week's
 * reporters rather than by reputation:
 *
 *   unavatar.io  returns VECTOR svg for NVIDIA, Salesforce, CrowdStrike and
 *                Affirm, and a 192px png for Marvell. Vector is the real answer
 *                to "high resolution" — it has no resolution to run out of.
 *   favicone     the fallback, and better than unavatar for Intuit specifically
 *                (152px against 60px).
 *   monogram     when both miss.
 *
 * Rejected, with the reason, because the obvious candidates all fail:
 *   Clearbit     shut down after the HubSpot acquisition — returns nothing.
 *   logo.dev     401 without an API key.
 *   Brandfetch   308 redirect loop on the public CDN; the real API needs a key.
 *   Google s2    works everywhere but is a browser-tab favicon: 32px for
 *                Salesforce and HP, and it hands back a JPEG at sz=128.
 *
 * The cascade is driven by a data attribute rather than nested inline handlers,
 * because an onerror that rewrites its own src has to know which step it is on or
 * it loops forever on a domain nobody serves.
 */
/* Ordered CORRECTNESS first, resolution second.
 *
 * Google is the baseline because across these seven domains it returned the right
 * mark every time — including HP's, which matters below. It is only a favicon, so
 * it is often small.
 *
 * unavatar is the upgrade: vector or 150-256px for most names. But it is not
 * always RIGHT — for hp.com it serves a generic document icon at 32px, and the
 * first version of this cascade happily swapped HP's real logo for it because both
 * were 32px and only "did it load" was being checked.
 *
 * So each step is kept only if it is genuinely bigger than what it replaced. A
 * source that is no larger has bought nothing and may have lost the logo, so it
 * is reverted. Correct beats sharp.
 */
const LOGO_SOURCES = [
  (d) => `https://www.google.com/s2/favicons?domain=${encodeURIComponent(d)}&sz=64`,
  (d) => `https://unavatar.io/${encodeURIComponent(d)}`,
  (d) => `https://favicone.com/${encodeURIComponent(d)}?s=256`,
];

function companyMark(ticker, domain, size) {
  const px = size || 32;
  const initials = String(ticker || '?').slice(0, 4);
  // Hue from the ticker, so a company always gets the same colour and a column of
  // monograms is varied rather than uniform grey.
  let hash = 0;
  for (let i = 0; i < initials.length; i += 1) {
    hash = (hash * 31 + initials.charCodeAt(i)) % 360;
  }
  const img = domain
    ? `<img src="${esc(LOGO_SOURCES[0](domain))}" alt=""
        loading="lazy" referrerpolicy="no-referrer"
        data-logo-domain="${esc(domain)}" data-logo-step="0"
        data-logo-min="${px * 2}"
        onerror="nextLogoSource(this)" onload="checkLogoSharpness(this)">`
    : '';
  return `<span class="co-mark" style="--co-size:${px}px;--co-hue:${hash}"
    aria-hidden="true"><span class="co-mono">${esc(initials)}</span>${img}</span>`;
}

/* Advance an <img> to the next logo source, or give up and show the monogram.
 * Global because it is called from an inline handler. */
window.nextLogoSource = function nextLogoSource(img) {
  const step = Number(img.dataset.logoStep || 0) + 1;
  const domain = img.dataset.logoDomain;
  if (!domain || step >= LOGO_SOURCES.length) { img.remove(); return; }
  img.dataset.logoStep = String(step);
  img.src = LOGO_SOURCES[step](domain);
};

/* Try the next source when this one LOADED but is too small.
 *
 * An error-only cascade is not enough. Intuit is the case that showed it: the
 * first source returns a valid 60px png, so nothing errors and the cascade never
 * fires — while the second source has it at 152px. "Succeeded" and "good enough"
 * are different questions and only the first was being asked.
 *
 * An SVG reports naturalWidth from its intrinsic size, which can be small even
 * though it scales perfectly, so vectors are exempt: they have no resolution to
 * be short of.
 */
window.checkLogoSharpness = function checkLogoSharpness(img) {
  const min = Number(img.dataset.logoMin || 0);
  const step = Number(img.dataset.logoStep || 0);
  const width = img.naturalWidth || 0;
  const src = img.currentSrc || img.src || '';
  const isVector = /\.svg(\?|$)/i.test(src);

  // Track the best source seen so far, so a step that turns out worse has
  // something to fall back to. A vector wins outright — it has no resolution to
  // run short of — so it ends the walk.
  const bestWidth = Number(img.dataset.logoBestWidth || 0);
  if (isVector) {
    img.dataset.logoBestSrc = src;
    img.dataset.logoBestWidth = '99999';
    return;
  }
  if (width > bestWidth) {
    img.dataset.logoBestSrc = src;
    img.dataset.logoBestWidth = String(width);
  } else if (img.dataset.logoBestSrc && src !== img.dataset.logoBestSrc) {
    // This step is no better than one already seen. HP is the case: unavatar
    // serves a generic document icon at the same 32px as Google's real logo, and
    // taking it would have replaced a correct mark with a wrong one.
    const keep = img.dataset.logoBestSrc;
    if (step >= LOGO_SOURCES.length - 1) { img.src = keep; return; }
    img.dataset.logoStep = String(step + 1);
    img.src = LOGO_SOURCES[step + 1](img.dataset.logoDomain);
    return;
  }

  if (!min || step >= LOGO_SOURCES.length - 1) {
    // Out of sources: settle on the best one found.
    if (img.dataset.logoBestSrc && src !== img.dataset.logoBestSrc) {
      img.src = img.dataset.logoBestSrc;
    }
    return;
  }
  // Still short of the box, and there is another source to try.
  if (width && width < min) nextLogoSource(img);
};

function renderEarningsWeek(w) {
  if (!w) return `<div class="panel span-all"><h2>${hg('Earnings this week')}</h2>
    <p class="sub">Loading the week…</p></div>`;
  if (!w.available) {
    return `<div class="panel span-all"><h2>${hg('Earnings this week')}</h2>
      <p class="sub">${esc(w.reason || 'Unavailable.')}</p></div>`;
  }

  const cols = (w.days || []).map((d) => `
    <section class="ew-day${d.is_today ? ' today' : ''}${d.is_past ? ' past' : ''}">
      <header class="ew-day-head">
        <span class="ew-dow">${esc(d.short)}</span>
        <span class="ew-dom">${fmt(d.day_number, 0)}</span>
        ${d.is_today ? '<span class="ew-today">today</span>' : ''}
        <span class="ew-count">${fmt(d.count, 0)}</span>
      </header>
      ${d.rows.length ? d.rows.map((r) => `
        <button type="button" class="ew-row${r.major ? ' major' : ''}"
          data-analyse="${esc(r.ticker)}">
          ${companyMark(r.ticker, r.domain, 34)}
          <span class="ew-tick">${esc(r.ticker)}${r.major
    ? '<span class="ew-major">major</span>' : ''}</span>
          <span class="ew-name">${esc(r.name || '')}</span>
          <span class="ew-eps">${r.eps_consensus === null || r.eps_consensus === undefined
    ? '<i>no estimate</i>'
    : `street <b>${fmt(r.eps_consensus, 2)}</b>${r.revenue_consensus
      ? ` · rev $${fmtCompact(r.revenue_consensus)}` : ''}`}</span>
          ${r.confirmed === false ? '<span class="ew-unconf">date not confirmed</span>' : ''}
        </button>`).join('')
    : '<p class="ew-empty">Nothing from the watchlist.</p>'}
    </section>`).join('');

  return `<div class="panel span-all">
    <div class="ew-head">
      <div>
        <h2>${hg('Earnings this week')}${askPulse('earningsweek')}</h2>
        <p class="sub">${esc(w.week_label)} · <strong>${fmt(w.total, 0)}</strong> reporting
          from the watchlist${w.majors ? `, <strong>${fmt(w.majors, 0)}</strong> index-moving`
    : ''}. Click any ticker to open the full analysis.</p>
      </div>
      <div class="ew-nav">
        <button type="button" class="bulk-btn" data-ew-offset="${(w.offset || 0) - 1}"
          aria-label="Previous week">‹</button>
        <button type="button" class="bulk-btn" data-ew-offset="0">This week</button>
        <button type="button" class="bulk-btn" data-ew-offset="${(w.offset || 0) + 1}"
          aria-label="Next week">›</button>
      </div>
    </div>
    <div class="ew-board">${cols}</div>
    <p class="caveat">${esc(w.session_note || '')}</p>
    <p class="caveat">${gloss(w.method || '')}</p>
  </div>`;
}

async function loadEarningsWeek(offset) {
  const want = offset === undefined ? (STATE.earningsWeekOffset || 0) : offset;
  STATE.earningsWeekOffset = want;
  if (STATE.earningsWeek && STATE.earningsWeek.offset === want) {
    if (!STATE.ticker) renderEarnings(STATE.earnings || {});
    return;
  }
  STATE.earningsWeek = null;
  if (!STATE.ticker) renderEarnings(STATE.earnings || {});
  try {
    STATE.earningsWeek = await getJSON(`/api/earnings-week?offset=${want}`);
  } catch (err) {
    STATE.earningsWeek = { available: false, reason: err.message, offset: want };
  }
  if (!STATE.ticker) renderEarnings(STATE.earnings || {});
}

function renderEarningsBrief(b) {
  const host = document.getElementById('earnBriefHost');
  if (!host) return;
  if (!b || !b.available) {
    host.innerHTML = `<h2>${hg('Pre-earnings brief')}</h2>
      <p class="sub">${esc((b && b.reason) || 'No written brief for this ticker.')}</p>`;
    host.classList.add('brief-empty');
    return;
  }
  host.classList.remove('brief-empty');
  const stance = b.stance || '';
  host.innerHTML = `
    <div class="earn-brief-head">
      <h2>${hg('Pre-earnings brief')}</h2>
      ${stance ? `<span class="earn-stance ${EARN_STANCE_CLASS[stance] || 'flat'}">${
  esc(stance)}</span>` : ''}
    </div>
    ${b.headline ? `<p class="earn-brief-lede">${esc(b.headline)}</p>` : ''}
    <div class="earn-brief">${briefProse(b.paragraphs)}</div>
    <p class="caveat">${gloss(b.method || '')}</p>
    <p class="caveat">${esc(b.disclaimer || '')}</p>`;
}

async function loadEarningsBrief(ticker) {
  const host = document.getElementById('earnBriefHost');
  if (!host) return;
  const hit = STATE.earningsBrief;
  if (hit && hit.ticker === ticker) { renderEarningsBrief(hit); return; }

  host.innerHTML = `<h2>${hg('Pre-earnings brief')}</h2>
    <p class="sub">Reading the figures below…</p>`;
  try {
    const b = await getJSON(`/api/earnings/${encodeURIComponent(ticker)}/brief`);
    b.ticker = ticker;
    STATE.earningsBrief = b;
    // The reader may have moved on while this was in flight.
    if (STATE.ticker === ticker) renderEarningsBrief(b);
  } catch (err) {
    renderEarningsBrief({ available: false,
      reason: `The brief could not be loaded (${err.message}). Every figure it would `
        + 'discuss is in the panels below.' });
  }
}

function renderEarnings(d) {
  hideTip();
  // Without a ticker the tab used to say "no ticker loaded" and stop. The week's
  // calendar is the right answer to the question a reader has at that point, and
  // every ticker on it is a way in.
  if (!STATE.ticker) {
    views.earnings.innerHTML = renderEarningsWeek(STATE.earningsWeek);
    return;
  }
  if (d.error) {
    views.earnings.innerHTML = `<div class="panel"><h2>${hg('Next report')}</h2>
      <div class="callout bad">${esc(d.error)}</div></div>`;
    return;
  }
  if (d.not_applicable) {
    views.earnings.innerHTML = `<div class="panel"><h2>No earnings for ${esc(d.ticker || '')}</h2>
      <div class="callout info">${esc(d.reason)}</div>
      <p class="sub" style="margin-top:var(--space-3)">The Swing / Options and Macro tabs all work
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
  <div class="panel span2 gap" id="earnBriefHost"></div>
  <div class="panel span2 gap">
    <h2>${hg(reported ? 'Latest result' : 'Next report')} · ${esc(d.ticker || '')}</h2>
    <p class="sub">${gloss(v.headline || '')}</p>
    <div class="hero-row" style="display:flex;align-items:baseline;gap:var(--space-4);flex-wrap:wrap;margin-bottom:var(--space-3)">
      <div>
        <span class="hero-label">${hg(reported ? 'Reported EPS' : 'Next report')}</span>
        <div class="hero ${reported ? signClass(lr.surprise_pct) : ''}" style="font-size:var(--t-d2)">${
  reported ? fmt(lr.eps_reported, 2) : (nr.date ? esc(nr.date) : '—')}</div>
        <span class="note subnote">${
  reported
    ? `Vs ${fmt(lr.eps_estimate, 2)} expected · reported ${esc(lr.date || '')}`
    : nr.confirmed === false ? 'estimated date, not yet confirmed by the company' : 'confirmed date'}</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:var(--space-2)">
        ${daysChip}
        ${reactionChip}
        <span class="chip ${revCls}"><span class="dot"></span>Estimates ${esc(rev.direction || 'unknown')}</span>
        ${pr.available ? `<span class="chip ${stanceCls}"><span class="dot"></span>Event ${esc(pr.stance)}</span>` : ''}
      </div>
    </div>
    <div class="grid c4" style="margin-bottom:var(--space-3)">
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
      rate can't warn you about. The result was fine and the market sold it anyway. Whatever moved
      the price is in the guidance or on the call, not in the headline number.</div>` : ''}
    <h3>${hg('Why')}</h3>
    <ul class="reasons">${(v.reasons || []).map((r) => `<li>${gloss(r)}</li>`).join('')}</ul>
    ${reported && ext.available ? `<p class="caveat">${gloss(ext.caveat || '')}${
  ext.as_of ? ` Last ${esc(ext.kind)} print ${new Date(ext.as_of).toLocaleString()}.` : ''}</p>` : ''}
    <p class="caveat">${esc(d.data_caveat || '')}</p>
  </div>

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Event pricing')}</h2>
      ${reported && !pr.available ? `<div class="callout">The report is out, so there's no event left
        to price. Straddle cost only means something ahead of the print. Once the numbers land the
        premium collapses, which is the whole reason it was expensive going in.</div>` : ''}
      ${pr.stale ? `<div class="callout">${gloss(pr.stale_note || '')}</div>` : ''}
      ${pr.available ? `
        <p class="sub">${gloss(pr.note || '')}</p>
        <div class="grid c2" style="margin-bottom:var(--space-3)">
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

  <div class="panel span2 gap">
    <h2>${hg('Surprise history')}</h2>
    ${sp.available ? `
    <p class="sub">Reported EPS against consensus, and what the stock actually did the session after.</p>
    <div class="grid c4" style="margin-bottom:var(--space-3)">
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

  <div class="panel span2 gap">
    <h2>${hg('Financial growth')} <span class="th-plain">· quarterly, year over year</span></h2>
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
    <div class="grid c4" style="margin-bottom:var(--space-3)">
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
    <p class="caveat">Price targets are sentiment, not forecasts. They cluster above spot in almost every market.</p>
  </div>
  `;
}

/* Roth inputs persist in localStorage rather than on the server: holdings are the
 * user's own financial data, and this app has no account system to protect it
 * with. Storing it locally keeps the only copy on their machine. */
const ROTH_STORE_KEY = 'optic.roth.inputs';

/** Where the Roth section renders, inside Optic's Positions.

    A function rather than a cached node: the tracker view re-renders and a held
    reference would point at a detached element, which is the same trap the
    catalyst library fell into. */
function rothHost() {
  return document.getElementById('roth-host');
}

function saveRothInputs() {
  try { localStorage.setItem(ROTH_STORE_KEY, JSON.stringify(STATE.rothInputs)); }
  catch (e) { /* private mode or quota. The inputs just won't persist */ }
}

function loadRothInputs() {
  try {
    const saved = JSON.parse(localStorage.getItem(ROTH_STORE_KEY) || 'null');
    if (saved && typeof saved === 'object') Object.assign(STATE.rothInputs, saved);
  } catch (e) { /* corrupt entry. Fall back to defaults */ }
}

/* ================================================================= ROTH IRA */

/** Render a {symbol: value} holdings map back into the textarea's line format. */
function rothHoldingsText(holdings) {
  if (!holdings || typeof holdings !== 'object') return '';
  return Object.entries(holdings).map(([sym, val]) => `${sym} ${val}`).join('\n');
}

function renderRoth(d) {
  hideTip();
  if (d.error) { (rothHost() || {}).innerHTML = errorHTML(d.error); return; }

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
    <td class="name"><strong>${esc(r.symbol)}</strong><div class="subnote">${esc(r.name)}</div></td>
    <td><strong>${fmt(r.weight_pct, 1)}%</strong></td>
    <td>${money(r.annual_dollars)}</td>
    <td>${fmt(r.expense_ratio_pct, 2)}%</td>
    <td>${fmt(r.yield_pct, 2)}%</td>
    <td>${fmtPct(r.cagr_10y_pct, 1)}</td>
    <td>${fmt(r.volatility_pct, 1)}%</td>
    <td class="down">${fmtPct(r.max_drawdown_pct, 0)}</td>
  </tr>`).join('');

  const fundRows = (d.funds || []).map((r) => `<tr${r.in_model_pct ? ' style="background:var(--surface-2)"' : ''}>
    <td class="name"><strong>${esc(r.symbol)}</strong><div class="subnote">${esc(r.note || '')}</div></td>
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
    if (i === j) return '<td class="muted">—</td>';
    const hot = v !== null && v >= 0.85;
    const cool = v !== null && v <= 0.35;
    return `<td style="color:${hot ? 'var(--s2)' : cool ? 'var(--s3)' : 'var(--ink-2)'}">${fmt(v, 2)}</td>`;
  }).join('')}
      </tr>`).join('')}</tbody>
    </table>` : '';

  (rothHost() || {}).innerHTML = `
  <div class="panel span2 gap">
    <h2>${hg('Roth IRA model allocation')}</h2>
    <p class="sub">Set your horizon and risk tolerance. The model is derived from those, not assumed.</p>

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
      <label style="flex:1 1 100%">Your current holdings. One per line, symbol then dollar value
        <textarea id="roth-holdings" rows="4" spellcheck="false"
          placeholder="VTI 12000&#10;VXUS 4000&#10;BND 1500">${esc(rothHoldingsText(inp.holdings))}</textarea>
      </label>
      <button class="btn primary" type="submit">Recalculate</button>
    </form>
    <p class="caveat" style="margin-top:var(--space-2)">Holdings stay on this device. Saved in your browser
      and posted only to your own local server to compute the numbers. Nothing is stored server-side.</p>
    <p class="caveat" style="margin-top:var(--space-2)">${gloss(d.limit_note || '')}</p>

    <div class="grid c4" style="margin:var(--space-3) 0">
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
    <div class="callout bad" style="margin-top:var(--space-3)">${esc(d.disclaimer || '')}</div>
  </div>

  <div class="panel span2 gap">
    <h2>${hg('Contribution projection')}</h2>
    ${pr.available ? `
      <p class="sub">Contributing ${money(pr.annual_contribution)} a year for ${pr.years} years at
        a blended ${fmt(pr.rate_pct, 1)}%. The weighted historical return of the funds above.</p>
      <div class="grid c4" style="margin-bottom:var(--space-3)">
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
  <div class="panel span2 gap">
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
    <p class="caveat">Funds that track the same thing are counted as one exposure. Holding VOO
      where the model lists VTI isn't drift, it's the same bet under a different ticker.</p>
  </div>` : ''}

  <div class="panel span2 gap">
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
        without selling anything. Selling inside a Roth is tax-free, so it's an option, just not
        the default.</p>
    ` : `<div class="callout">${esc(rb.note || 'Enter your holdings above.')}</div>`}
  </div>

  ${ov.available ? `
  <div class="panel span2 gap">
    <h2>${hg('Overlap in your holdings')}</h2>
    <p class="sub">${gloss(ov.note || '')}</p>
    ${(ov.pairs || []).length ? (ov.pairs.map((p) => `<div class="callout ${p.same_role ? 'bad' : ''}">
      <strong>${esc(p.a)} + ${esc(p.b)}</strong>· correlation ${fmt(p.correlation, 2)}.
      ${gloss(p.note)}</div>`).join('')) : '<div class="callout info">Nothing is doubled up.</div>'}
  </div>` : ''}

  <div class="panel span2 gap">
    <h2>${hg('Individual stock sleeve')}</h2>
    <p class="sub">${gloss(sl.note || '')}</p>
    ${(sl.rows || []).length ? `<table class="data">
      <thead><tr><th>Stock</th><th>Conviction</th><th>Score</th><th>10y CAGR</th><th>Worst drawdown</th><th>History</th><th>Suggested</th></tr></thead>
      <tbody>${sl.rows.map((r) => `<tr${r.eligible ? '' : ' style="opacity:0.62"'}>
        <td class="name"><strong>${esc(r.symbol)}</strong><div class="subnote">${esc(r.name || '')}</div></td>
        <td>${r.error ? '<span class="down">Error</span>' : toneChipConviction(r.conviction)}</td>
        <td class="${signClass(r.conviction_score)}">${fmt(r.conviction_score, 0)}</td>
        <td>${fmtPct(r.cagr_10y_pct, 1)}</td>
        <td class="down">${fmtPct(r.max_drawdown_pct, 0)}</td>
        <td>${fmt(r.years_of_history, 0)}y</td>
        <td>${r.eligible ? `<strong>${fmt(r.suggested_pct, 1)}%</strong>` : '—'}</td>
      </tr>`).join('')}</tbody>
    </table>
    ${sl.rows.filter((r) => r.reject_reason || r.error).map((r) => `<div class="callout">
      <strong>${esc(r.symbol)}</strong>· ${esc(r.reject_reason || r.error)}</div>`).join('')}
    ${sl.rows.flatMap((r) => (r.warnings || []).map((w) => `<div class="callout bad">
      <strong>${esc(r.symbol)}</strong>· ${gloss(w)}</div>`)).join('')}
    ` : ''}
    <div class="callout bad" style="margin-top:var(--space-2)">${gloss(sl.caveat || '')}</div>
  </div>

  <div class="panel span2 gap">
    <h2>${hg('What the Roth wrapper changes')}</h2>
    <p class="sub">Reasoning specific to a Roth, as opposed to generic allocation advice.</p>
    ${(d.roth_notes || []).map((n) => `<div class="callout info">
      <strong>${esc(n.title)}</strong><br>${gloss(n.body)}</div>`).join('')}
  </div>

  <div class="panel span2 gap">
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

  (rothHost() || document).querySelectorAll('[data-bar]').forEach((host) => {
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
      esc(z.label)} · ${esc(now)}</option>`;
  }).join('');

  // Market hours in the viewer's zone. Derived from the timestamps the server
  // sends with each segment, so US daylight-saving transitions are handled by the
  // server's own calendar rather than re-implemented here.
  const hoursRows = (sess.segments || [])
    .filter((seg, i, all) => all.findIndex((x) => x.phase === seg.phase) === i)
    .map((seg) => `<tr${seg.active ? ' style="background:var(--surface-2)"' : ''}>
      <td class="name"><span class="ses-dot p-${esc(seg.phase)}" style="display:inline-block;
        margin-right:var(--space-2);vertical-align:1px"></span>${esc(seg.label)}${
    seg.active ? ' <span class="subnote">· now</span>' : ''}</td>
      <td>${esc(timeIn(seg.start_at, 'America/New_York'))} – ${
    esc(timeIn(seg.end_at, 'America/New_York'))} ET</td>
      <td>${esc(timeIn(seg.start_at, zone))} – ${esc(timeIn(seg.end_at, zone))} ${
    esc(zoneAbbrev(zone))}</td>
    </tr>`).join('');

  views.settings.innerHTML = `
  <div class="panel span2 gap">
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

  <div class="panel span2 gap">
    <h2>${hg('Time zone')}</h2>
    <p class="sub"><strong>US market hours are defined in Eastern Time and don't move.</strong>
      This setting only changes the clock they're displayed against, so you can see when the open
      and close land where you are.</p>
    <div class="settings-row">
      <div class="settings-label">Show times in
        <span class="settings-hint">Currently ${esc(zone)} (${esc(zoneAbbrev(zone))})${
    onMarketTime ? '. The same as market time, so nothing is converted.' : '.'}</span></div>
      <select id="tz-select" class="settings-select">${zoneOpts}</select>
    </div>

    ${hoursRows ? `
      <h3 style="margin-top:var(--space-4)">${hg('Market hours')}</h3>
      <table class="data narrow">
        <thead><tr><th>Session</th><th>Eastern (market)</th><th>Your zone</th></tr></thead>
        <tbody>${hoursRows}</tbody>
      </table>
      <p class="caveat">Overnight straddles midnight, so its two halves share one row. Daylight
        saving shifts these by an hour on different dates in different countries. The conversion
        follows each zone's own calendar rather than assuming a fixed offset.</p>
    ` : `<div class="callout">Load a ticker once and the session times will appear here.</div>`}
  </div>

  <div class="panel span2">
    <h2>${hg('About this build')}</h2>
    ${kv([
    ['Data source', 'Yahoo Finance via yfinance. Quotes delayed roughly 15 minutes'],
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


/* Robinhood-style timeframe pills.
 *
 * Replaces the <select> the ranges used to live in. A dropdown hides the options
 * until you open it, so switching timeframe was two interactions and you could
 * not see what else was available; a pill row shows the whole set and costs one
 * tap. On a phone it also removes the native picker sheet, which was covering
 * the chart you were trying to compare against.
 *
 * `attr` is the data attribute the click delegate listens on, so one renderer
 * serves every chart rather than each growing its own control.
 */
/* Re-render without moving the page under the reader.
 *
 * The chart controls — timeframe, interval, candle/line, the Technical Levels
 * toggles — each rebuild their whole tab. Measured on the Swing tab that is
 * ~2,600 nodes replaced, and the visible result was worse than the cost: the
 * scroll position shifted by over a hundred pixels because panels above the
 * viewport re-measured, every open drawer snapped shut, and focus was dropped so
 * a keyboard user lost their place entirely.
 *
 * Splitting each control out to redraw only its own chart is the deeper fix and
 * a much larger change to renderSwing. This preserves the three things the
 * reader actually notices, around any re-render, in one place:
 *
 *   - scroll offset, restored before the browser paints so there is no visible jump
 *   - which <details> were open, keyed on their summary text rather than position
 *     so the match survives a panel appearing or disappearing
 *   - focus, and the caret inside a text field
 *
 * Keyed on summary text because index-based keys silently reopen the wrong
 * drawer the moment the panel list changes length. */
function detailsKey(el) {
  const sum = el.querySelector('summary');
  return (el.id || (sum ? sum.textContent.trim().slice(0, 60) : '')) || null;
}

function preserveUI(host, fn) {
  // A control press is not a fresh load. animateNextChart is sticky — set true
  // by the last foreground load and only ever cleared by the resize path — so
  // every timeframe or candle/line press was replaying the draw-on animation
  // across all nineteen charts on the Swing tab. Redrawing a chart the reader is
  // already looking at should be instant; the animation is for data arriving.
  setChartAnimation(false);
  const scroll = window.scrollY;
  const open = new Set();
  (host || document).querySelectorAll('details[open]').forEach((el) => {
    const key = detailsKey(el);
    if (key) open.add(key);
  });
  const active = document.activeElement;
  const focusId = active && active.id ? active.id : null;
  const caret = active && typeof active.selectionStart === 'number'
    ? [active.selectionStart, active.selectionEnd] : null;

  fn();

  (host || document).querySelectorAll('details').forEach((el) => {
    const key = detailsKey(el);
    if (key && open.has(key)) el.open = true;
  });
  if (focusId) {
    const back = document.getElementById(focusId);
    if (back) {
      back.focus({ preventScroll: true });
      if (caret && typeof back.setSelectionRange === 'function') {
        try { back.setSelectionRange(caret[0], caret[1]); } catch (e) { /* not a text input */ }
      }
    }
  }
  // Same frame, before paint: setting it after a paint is what shows up as a jump.
  if (window.scrollY !== scroll) window.scrollTo({ top: scroll, behavior: 'instant' });
}

function rangePills(items, active, attr, label) {
  return `<div class="pills" role="group" aria-label="${esc(label || 'Timeframe')}">${
    items.map((it) => `<button type="button" class="pill${it.key === active ? ' on' : ''}"
      ${attr}="${esc(it.key)}" aria-pressed="${it.key === active}">${esc(it.label)}</button>`)
      .join('')}</div>`;
}

/** "NVDA $180 call · Aug 21" for an option, plain ticker for shares. */
/* "Close defence": the one level a closing print has to stay the right side of.
 *
 * Deliberately a single number rather than a table of support. Moving averages
 * and pivots are defined on closes, so intraday pokes decide nothing — and of the
 * dozen levels the app knows, only the nearest one on the defended side can break
 * first. Showing all of them is what the support/resistance table is for. */
function renderCloseDefence(cd, opts = {}) {
  if (!cd || !cd.available) return '';
  const up = cd.direction === 'up';
  const trend = up ? 'uptrend' : 'downtrend';

  if (!cd.must_hold) {
    return `<div class="panel gap">
      <h2>${hg('Close defence')}${askPulse('defence')}</h2>
      <div class="callout">${gloss(cd.note || '')}</div>
    </div>`;
  }

  const mh = cd.must_hold;
  const mins = cd.minutes_to_close;
  const clock = (mins === null || mins === undefined)
    ? 'The session is closed, so this is the level the next close has to respect.'
    : `${Math.floor(mins / 60) ? Math.floor(mins / 60) + 'h ' : ''}${mins % 60}m left in the session.`;

  return `<div class="panel gap">
    <h2>${hg('Close defence')}${askPulse('defence')} <span class="chip ${up ? 'bull' : 'bear'}"
      style="margin-left:var(--space-2)"><span class="dot"></span>${esc(cap(trend))}</span></h2>
    <p class="sub">To carry this ${esc(trend)} overnight, ${esc(opts.horizonWord || 'today')}'s
      close needs to hold ${up ? 'above' : 'below'} one level. ${esc(clock)}</p>

    <div class="grid c4">
      ${tile(up ? 'Must close above' : 'Must close below', usd(mh.price),
    `${esc(mh.label)} · ${fmt(Math.abs(mh.distance_pct), 2)}% ${up ? 'below' : 'above'} here`,
    up ? 'up' : 'down')}
      ${tile('Cushion', `${fmt(cd.cushion_pct, 2)}%`,
    cd.tight ? 'Inside a normal day of noise. Treat as live' : 'Room before it is tested',
    cd.tight ? 'down' : '')}
      ${cd.next_level ? tile('Next level down', usd(cd.next_level.price),
    `${esc(cd.next_level.label)}. Where price goes if the first gives`) : ''}
    </div>

    <div class="callout ${cd.tight ? '' : 'info'}">Lose ${usd(mh.price)} on the close and
      it breaks <strong>${esc(cd.consequence)}</strong>.</div>
    ${cd.cadence_note ? `<div class="caveat">${gloss(cd.cadence_note)}</div>` : ''}
    <p class="caveat">${gloss(cd.method || '')}</p>
  </div>`;
}

/* ---------------------------------------------------------- open positions
 *
 * This panel is the first thing a stranger scrolls to, and it used to sit below
 * the month-by-month record, the scan funnel and the track record — four panels
 * of statistics before you could see what the ledger actually owns. It now comes
 * directly after the summary, because "what is it holding right now" is the
 * question the page is opened to answer.
 */

/** Where a trade sits on its own stop-to-target line, as a fraction: 0 is the
 *  stop, 1 is the target. One formula covers both directions — for a short the
 *  target is below the stop, both differences flip sign, and the ratio comes out
 *  the right way up on its own.
 *
 *  Options are measured on the *underlying*, not the premium, because that is
 *  what the stop and the target are prices of. The two can disagree: a call can
 *  be losing money while the stock creeps toward the target, because time decay
 *  ran faster than the move. Showing that divergence is the point of putting the
 *  two side by side, not a fault in either. */
function positionTravel(p) {
  const n = (v) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? null : Number(v));
  const stop = n(p.stop), target = n(p.target);
  const now = n(p.mark_spot) === null ? n(p.mark_price) : n(p.mark_spot);
  const entry = n(p.entry_spot) === null ? n(p.entry_price) : n(p.entry_spot);
  if (stop === null || target === null || now === null) return null;
  // A target at or below zero is unreachable — a stock cannot trade through
  // zero, so the position can only ever exit at its stop or its time stop.
  // Three live short positions were recorded this way before the scanner
  // learned to decline them; drawing a gauge to a price that cannot happen
  // would be worse than saying so.
  if (target <= 0) return { stop, target, now, unreachable: true };
  const span = target - stop;
  if (!span) return null;
  const frac = (v) => Math.max(0, Math.min(1, (v - stop) / span));
  return {
    stop, target, now, entry,
    at: frac(now),
    from: entry === null ? null : frac(entry),
    // Has the stock moved toward the target since the trade opened, or back
    // toward the stop? That is the question the bar answers.
    ahead: entry === null ? null : (now - entry) / span >= 0,
  };
}

/** The stop-to-target gauge for one open position.
 *
 * A row of prices tells you where the stock is. It does not tell you whether the
 * trade is nearly over, which is the first thing anyone wants to know, and
 * working it out from four numbers and a direction is more arithmetic than a
 * reader should have to do per row. */
function travelCell(p) {
  const t = positionTravel(p);
  if (!t) return '<span class="muted">—</span>';
  if (t.unreachable) {
    // No track and no dot. With only one end of the scale real there is nowhere
    // honest to put the marker, and drawing it at the left of an empty rail says
    // "sitting on its stop", which is a different and much worse thing than
    // "this trade has no target".
    return `<div class="pos-gauge">
      <div class="pos-ends"><span>stop ${fmt(t.stop, 2)}</span><span>now ${fmt(t.now, 2)}</span></div>
      <div class="pos-read">No reachable target. Stop or time stop only.</div>
    </div>`;
  }
  const cls = t.ahead === null ? '' : (t.ahead ? ' up' : ' down');
  const at = t.at * 100;
  const from = t.from === null ? at : t.from * 100;
  // The fill spans entry-to-now rather than stop-to-now: it is the ground this
  // trade has covered, which is what "ahead" and "behind" mean here.
  const a = Math.min(at, from), b = Math.max(at, from);
  return `<div class="pos-gauge">
    <div class="pos-ends">
      <span>stop ${fmt(t.stop, 2)}</span><span>target ${fmt(t.target, 2)}</span>
    </div>
    <div class="pos-track">
      <div class="pos-fill${cls}" style="left:${a.toFixed(1)}%;width:${(b - a).toFixed(1)}%"></div>
      ${t.from === null ? '' : `<i class="pos-entry" style="left:${from.toFixed(1)}%"
        title="opened with the stock at ${fmt(t.entry, 2)}"></i>`}
      <i class="pos-now${cls}" style="left:${at.toFixed(1)}%"
        title="the stock is at ${fmt(t.now, 2)} now"></i>
    </div>
    <div class="pos-read">${Math.round(at)}% toward target${
    p.instrument === 'option' ? '<br>measured on the stock' : ''}</div>
  </div>`;
}

/** One plain sentence of state of play.
 *
 * Eleven rows of numbers do not add up to an impression on their own, and the
 * tiles above give totals rather than a spread. This says how the holdings are
 * split and which two rows are worth looking at first. */
function openStateOfPlay(open) {
  const scored = open.filter((p) => Number.isFinite(Number(p.pnl)));
  if (!scored.length) return '';
  const up = scored.filter((p) => Number(p.pnl) > 0);
  const down = scored.filter((p) => Number(p.pnl) < 0);
  const best = scored.reduce((m, p) => (Number(p.pnl) > Number(m.pnl) ? p : m), scored[0]);
  const worst = scored.reduce((m, p) => (Number(p.pnl) < Number(m.pnl) ? p : m), scored[0]);
  const name = (p) => `${esc(p.ticker)}${p.instrument === 'option' ? ' (option)' : ''}`;
  const parts = [`<strong>${up.length} of ${scored.length} are up</strong>`];
  if (down.length) parts.push(`${down.length} ${down.length === 1 ? 'is' : 'are'} down`);
  const flat = scored.length - up.length - down.length;
  if (flat) parts.push(`${flat} ${flat === 1 ? 'is' : 'are'} flat`);
  const extremes = best === worst ? ''
    : ` Best is ${name(best)} at ${money(best.pnl, 0)}; worst is ${name(worst)} at
        ${money(worst.pnl, 0)}.`;
  return `<div class="callout" style="margin:0 0 var(--space-3)">${parts.join(', ')}.${extremes}
    None of it is real money. The ledger records what the terminal's rules would have done, and no
    order is ever sent to a broker.</div>`;
}

/** The open-positions panel. Split out of renderTracker so it can be placed at
 *  the top of the tab rather than reachable only by scrolling past everything
 *  the ledger has ever done. */
function openPositionsPanel(open) {
  if (!open.length) return '';
  const rows = open.map((p) => `<tr>
    <td class="name">${positionLabel(p)}</td>
    <td>${cap(sideCell(p))}</td>
    <td>${sizeCell(p)}</td>
    <td>${fmt(p.entry_price, 2)}
      <div class="subnote">now ${fmt(p.mark_price, 2)}${
    p.mark_source === 'model' ? ' · estimated' : ''}</div></td>
    <td>${travelCell(p)}</td>
    <td class="${signClass(p.pnl)}"><strong>${money(p.pnl, 0)}</strong>
      <div class="caption">${fmtPct(p.pnl_pct, 1)}</div></td>
    <td>${money(p.risk_dollars, 0)}</td>
    <td>${Number.isFinite(Number(p.composite)) ? fmt(Math.abs(p.composite), 0) : '—'}</td>
    <td>${heldDays(p.entry_at) === null ? '—' : heldDays(p.entry_at) + 'd'}</td>
  </tr>`).join('');

  return `<div class="panel span2 gap">
    <h2>${hg('Open positions')}</h2>
    <p class="sub">The ${open.length === 1 ? 'one trade' : `${open.length} trades`} the ledger is
      holding right now. Each row is one trade, and it will end at one of two prices decided when it
      opened: a <strong>stop</strong>, which cuts the loss if the trade is wrong, or a
      <strong>target</strong>, which takes the gain if it is right. The bar shows how far the stock
      has travelled between the two. The small tick is where the trade opened, the dot is where the
      stock is now, and the shaded stretch between them is the ground it has covered.</p>

    ${openStateOfPlay(open)}

    <table class="data">
      <thead><tr><th>Position</th><th>Betting on</th><th>Size</th><th>Paid</th>
        <th>Where it stands</th><th>Up or down</th><th>If stopped</th><th>Signal score</th>
        <th>Held</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="caveat">Stop and target are prices on the <em>underlying stock</em> for both
      instruments, which is why an option row can be losing while its bar is moving the right way:
      the stock can sit still, or even drift the correct way slowly, while time decay drains the
      premium. An option therefore also carries its own exits on the premium itself, at −50% and
      +100%. Options are re-priced from the live chain each time; when a contract has no usable
      quote the mark falls back to a Black-Scholes estimate and the row is marked "estimated".</p>
    ${open.some((p2) => p2.target !== null && p2.target !== undefined
    && Number(p2.target) <= 0) ? `<p class="caveat">A row reading
      <em>no reachable target</em> is a short whose stop was wide enough to put its 2:1 target below
      zero. A stock cannot trade through zero, so that position can only ever end at its stop or its
      time stop, and it was never really the 2:1 trade the rules describe. The scanner now declines
      these outright; the ones on the book were opened before it did, and they are left in place
      rather than quietly deleted. An inconvenient record is still the record.</p>` : ''}
  </div>`;
}


function positionLabel(p) {
  // The ticker is the way in to the reasoning. A composite score answers "how
  // strongly" but never "why this name", and the ledger is only credible if the
  // analysis behind each entry is one click away.
  const sym = `<button type="button" class="tkr" data-analyse="${esc(p.ticker)}"
    title="Open the full analysis for ${esc(p.ticker)}">${esc(p.ticker)}</button>`;
  if (p.instrument !== 'option') return `${sym} shares`;
  const exp = p.expiry
    ? new Date(p.expiry + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : '';
  return `${sym} $${fmt(p.strike, 0)} ${esc(p.option_type || '')}
    <div class="subnote">expires ${esc(exp)}</div>`;
}

/** What the trade is betting on.
 *
 * A long put is stored as direction "long" — correct for P&L, since the premium
 * is owned — but "long" next to a put reads as a bullish bet, so the bias is
 * spelled out instead.
 *
 * Both instruments now use the same two words. The share rows said "long" and
 * "short" while the option rows said "bullish" and "bearish", so a table holding
 * both looked like it was describing four different things when it was
 * describing two. The mechanic goes underneath, where it explains rather than
 * competes: "bearish" is the bet, "sold short" is how it was taken. */
function sideCell(p) {
  const note = (text) => `<div class="subnote">${text}</div>`;
  if (p.instrument !== 'option') {
    const long = p.direction === 'long';
    return `${long ? 'bullish' : 'bearish'}${note(long ? 'Owns the shares' : 'Sold short')}`;
  }
  const put = p.option_type === 'put';
  return `${put ? 'bearish' : 'bullish'}${note(`Owns the ${put ? 'put' : 'call'}`)}`;
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
      <div class="subnote">${money(p.qty * p.entry_price * 100)} premium</div>`;
  }
  return `${fmt(p.qty, 0)} shares
    <div class="subnote">${money(p.qty * p.entry_price)} notional</div>`;
}

function trackerUniverseHint(cfg) {
  if (cfg.universe !== 'nasdaq') {
    return `Watchlist: ${(cfg.watchlist || []).map((x) => esc(x)).join(', ')}. A scan puts all of
      them through the full analysis.`;
  }
  return `Universe: <strong>every NASDAQ-listed common stock</strong>· about 3,000 names, from
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
      ${prog.trigger === 'scheduled' ? '<span class="chip neutral" style="padding:var(--space-0) var(--space-2)"><span class="dot"></span>Scheduled</span>' : ''}
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
    <td class="muted">${i + 1}</td>
    <!-- Same control as the holdings tables: the symbol is the way into its
         analysis. A screen row is a name the terminal thinks is interesting, so
         "why?" is the immediate next question and it should not require retyping
         the ticker into the search box. -->
    <td class="name"><button type="button" class="tkr" data-analyse="${esc(m.symbol)}"
      title="Open the full analysis for ${esc(m.symbol)}">${esc(m.symbol)}</button></td>
    <td class="${signClass(m.score)}">${m.score > 0 ? '+' : ''}${fmt(m.score, 0)}</td>
    <td>${fmt(m.price, 2)}</td>
    <td>$${fmtCompact(m.dollar_volume, 0)}</td>
    <td class="${signClass(m.roc20)}">${fmtPct(m.roc20, 1)}</td>
    <td class="subnote">${m.analysed ? 'Analysed' : 'Not reached'}</td>
  </tr>`).join('');

  return `
  <div class="panel span2 gap">
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

    <p class="caveat" style="margin-top:var(--space-0)">Dropped along the way:
      ${fmt(sc.dropped_illiquid, 0)} too thinly traded,
      ${fmt(sc.dropped_short_history, 0)} without a year of history,
      ${fmt(sc.dropped_too_volatile, 0)} moving more than ${fmt(gates.max_atr_pct, 0)}% a day,
      ${fmt(sc.dropped_already_moved, 0)} already up or down more than
      ${fmt(gates.max_abs_1m_move_pct, 0)}% in a month.
      ${sc.already_held ? `${fmt(sc.already_held, 0)} ranked well but are already held.` : ''}</p>
    ${sc.failed_batches ? `<div class="callout">${fmt(sc.failed_batches, 0)} batch(es) of about
      ${fmt(150, 0)} symbols each never returned data, even after a retry. Almost always the free
      feed's rate limit. Those names weren't screened at all, so this ranking covers slightly less
      than the whole exchange.</div>` : ''}
    ${f.throttled_skips ? `<div class="callout">${fmt(f.throttled_skips, 0)} shortlisted name(s) were
      skipped because the feed was still rate-limiting when their options chain was requested. They
      weren't traded on partial data.</div>` : ''}

    <h3>${hg('Screen ranking')}</h3>
    <p class="sub">Top ${fmt((f.shortlist || []).length, 0)} by absolute score. Greyed rows ranked
      high enough but weren't reached. The scan stopped when a cap bound.</p>
    <table class="data">
      <thead><tr><th>#</th><th>Symbol</th><th>Screen score</th><th>Price ($)</th>
        <th>$ volume/day</th><th>1-month</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${f.capped ? `<div class="callout">Stopped early: ${esc(f.capped)}.</div>` : ''}
    <p class="caveat">${gloss(sc.caveat || '')}</p>
  </div>`;
}

/* The three books.
 *
 * Same scan, different rules — so the selector is also the comparison: each card
 * carries that book's own equity and record, which is the only way the choice
 * means anything. Sharing one equity pool would have let the aggressive book's
 * losses shrink the conservative book's position sizes and turned three
 * independent records into one entangled one. */
const BOOK_TONE = { conservative: 'flat', balanced: 'up', aggressive: 'warn' };

function renderBookSelector(d) {
  const books = d.books || [];
  if (books.length < 2) return '';
  const active = d.book || 'balanced';
  const cards = books.map((b) => {
    const su = b.summary || {};
    const ret = su.return_pct;
    return `<button type="button" class="book-card${b.id === active ? ' on' : ''}"
      data-book="${esc(b.id)}">
      <span class="bk-top">
        <span class="bk-name">${esc(b.label)}</span>
        <span class="cat-tag ${BOOK_TONE[b.id] || 'flat'}">${esc(b.tagline)}</span>
      </span>
      <span class="bk-figs">
        <span><i>Equity</i>$${fmtCompact(b.equity)}</span>
        <span><i>Return</i><b class="${signClass(ret)}">${ret === null || ret === undefined
    ? '\u2014' : (ret > 0 ? '+' : '') + fmt(ret, 2) + '%'}</b></span>
        <span><i>Open</i>${fmt(su.open_count, 0)}</span>
        <span><i>Closed</i>${fmt(su.closed_count, 0)}</span>
      </span>
      <span class="bk-rules">${fmt(b.risk_per_trade * 100, 1)}% per trade ·
        score bar ${fmt(b.min_composite, 0)} ·
        ${b.allow_options ? (b.prefer_options ? 'options preferred' : 'shares + options')
    : 'shares only'} · max daily range ${fmt(b.max_atr_pct, 0)}%</span>
      <span class="bk-blurb">${esc(b.blurb)}</span>
    </button>`;
  }).join('');

  return `<div class="panel span-all">
    <h2>${hg('Three books')}${askPulse('books')}</h2>
    <p class="sub">The same scan run under three sets of rules. Identical candidates, so
      comparing them says what a risk tolerance costs and earns rather than comparing three
      different signals. Each book has its own $100,000 and its own record.</p>
    <div class="book-cards">${cards}</div>
    <p class="caveat">${gloss('They differ in the four things that actually change a risk '
    + 'profile: how selective the entry bar is, how much is risked per trade, which '
    + 'instruments are allowed, and how volatile a name may be. Nothing changes the '
    + 'analysis. A setup is a setup, and these decide what to do about it. The '
    + 'existing record belongs to the balanced book because those are the rules that '
    + 'produced it.')}</p>
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

  const closedRows = closed.map((p) => `<tr>
    <td class="name">${positionLabel(p)}</td>
    <td>${cap(sideCell(p))}</td>
    <td>${sizeCell(p)}</td>
    <td>${fmt(p.entry_price, 2)}</td>
    <td>${fmt(p.exit_price, 2)}</td>
    <td class="${signClass(p.pnl)}"><strong>${money(p.pnl, 0)}</strong>
      <div class="caption">${fmtPct(p.pnl_pct, 1)}</div></td>
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
  <tr><td colspan="5" style="color:var(--ink-muted);font-size:var(--t-caption);line-height:1.65;
      padding-top:0;white-space:normal">
    ${esc(cap((sc.notes || []).join(' · ')) || 'Nothing cleared the bar')}
    ${(sc.funnel || {}).screen && sc.funnel.screen.ranking_reused
    ? `<div style="margin-top:var(--space-1)">Screen ranking reused from
        ${fmt(sc.funnel.screen.ranking_age_minutes, 0)} minutes earlier. Daily bars don't change
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
    ? ' <span class="subnote">· in progress</span>' : ''}</td>
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
      <div class="caption">${fmtPct(p.pnl_pct, 1)}</div></td>
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
      <div class="caption">${fmtPct(p.pnl_pct, 1)}</div></td>
    <td>${heldDays(p.entry_at) === null ? '—' : heldDays(p.entry_at) + 'd'}</td>
  </tr>`).join('');

  const empty = !open.length && !closed.length;

  views.tracker.innerHTML = `
  ${renderBookSelector(d)}

  <div class="panel span2 gap">
    <h2>${hg("Optic's Positions")}</h2>
    <p class="sub">One shared, simulated ledger. The same record for everyone who opens this page.
      It trades the terminal's own signals with fixed rules, in both instruments the Swing tab
      produces: the shares, and the exact option contract it recommended.</p>

    <div class="tracker-bar">
      <button class="btn primary" type="button" id="tracker-scan" ${scanning ? 'disabled' : ''}>
        ${scanning ? 'Scan running…' : 'Run a scan now'}</button>
      <button class="btn" type="button" id="tracker-mark" ${scanning ? 'disabled' : ''}>Refresh marks</button>
      <span class="tracker-hint">${trackerUniverseHint(cfg)}</span>
    </div>

    ${marketOpen ? '' : `<div class="callout" style="margin-top:var(--space-3)">
      <strong>The market is closed.</strong> Open positions are still re-marked at the closing
      price, but no new entries are taken while the tape is shut. A fill at a stale price isn't a
      trade anyone could have got. Scanning resumes at the next open (9:30am ET, weekdays).</div>`}

    ${scanning ? progressHTML(prog) : ''}
    ${feed.throttled ? `<div class="callout bad" style="margin-top:var(--space-3)">
      <strong>The price feed is rate-limiting right now.</strong> Screening thousands of symbols on a
      free data feed earns a temporary block, and a blocked options request comes back looking like
      a stock with no options at all. Optic skips those names rather than opening a
      shares-only trade and recording it as what was recommended. So a scan during a block will
      take fewer positions, not wrong ones. Clears in about
      ${fmt(feed.seconds_remaining, 0)}s.</div>` : ''}

    <div class="grid c4" style="margin:var(--space-3) 0">
      ${tile('Equity', money(s.equity), `started at ${money(s.start_equity)}`, signClass(s.realised_pnl))}
      ${tile('Realised P&L', money(s.realised_pnl), `${s.closed_count || 0} closed trades`, signClass(s.realised_pnl))}
      ${tile('Unrealised P&L', money(s.unrealised_pnl), `${s.open_count || 0} open now`, signClass(s.unrealised_pnl))}
      ${tile('Total return', fmtPct(s.return_pct, 2), 'realised plus open marks', signClass(s.return_pct))}
    </div>
    <div class="grid c4" style="margin-bottom:var(--space-3)">
      ${tile('Position slots', `${capacity.open_positions || 0} / ${cfg.max_open_positions || '—'}`,
    `${capacity.position_slots_left || 0} left`)}
      ${tile('Risk deployed', money(capacity.open_risk, 0),
    `${fmt(capacity.open_risk_pct, 1)}% of a ${fmt(cfg.max_portfolio_risk_pct, 0)}% budget`)}
      ${tile('Risk budget left', money(capacity.risk_budget_left, 0), 'before the book stops adding')}
      ${tile('New per scan', fmt(cfg.max_new_per_scan, 0), 'so the book fills over days')}
    </div>
    <p class="caveat">Equity counts closed trades only. Open positions are shown but deliberately kept
      out of the sizing calculation, so an unrealised run-up can't quietly increase the size of the
      next bet. The caps exist because the universe is the whole exchange. Without them one scan
      could find thirty qualifying setups and put a third of the account at risk in an afternoon, on
      names that are mostly the same momentum bet under different tickers.</p>
  </div>

  ${openPositionsPanel(open)}

  <div class="panel span2 gap">
    <h2>${hg('Month by month')}</h2>
    <p class="sub">Results split by the month a trade <em>closed</em>· the month the money was
      actually made or lost. A position opened in one month and closed in the next counts toward the
      month it closed in, and appears in the earlier month's opened count.</p>

    <div class="tracker-bar" style="margin-bottom:var(--space-3)">
      ${monthPicker}
      <span class="tracker-hint">Showing <strong>${esc(mo.label || '—')}</strong>${
    viewingCurrent ? '. Still in progress, so these figures are not final.' : '.'}
        The record runs from ${esc(months.length ? months[0].label : 'this month')} and includes
        every trade the ledger has taken, nothing excluded.</span>
    </div>

    <div class="grid c4" style="margin-bottom:var(--space-3)">
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
      <h3 style="margin-top:var(--space-4)">${hg('Opened in this month and still held')}</h3>
      <table class="data">
        <thead><tr><th>Position</th><th>Side</th><th>Size</th><th>Entry</th><th>Mark</th>
          <th>P&amp;L</th><th>Held</th></tr></thead>
        <tbody>${monthOpenRows}</tbody>
      </table>
      <p class="caveat">Unrealised. These carry into whichever month they eventually close in.</p>
    ` : ''}

    ${months.length > 1 ? `
      <h3 style="margin-top:var(--space-4)">${hg('Consistency')}</h3>
      <table class="data">
        <thead><tr><th>Month</th><th>Opened</th><th>Closed</th><th>Realised</th><th>Return</th>
          <th>Win rate</th><th>Expectancy</th><th>Profit factor</th><th>Equity after</th></tr></thead>
        <tbody>${monthRows}</tbody>
      </table>
      <p class="caveat">${gloss('Equity after carries forward, so each month\u2019s return is '
    + 'measured against what the account was worth when that month began rather than against the '
    + 'original stake. A month with no closed trades is still a row. Taking nothing is a '
    + 'decision, and hiding it would flatter the record.')}</p>
    ` : `<p class="caveat">One month of record so far. A consistency table needs several months
      before it says anything. Treat a single month, good or bad, as noise.</p>`}
  </div>

  ${lastFunnel ? funnelPanelHTML(lastFunnel, gates, cfg) : ''}

  ${empty ? `
  <div class="panel span2 gap">
    <h2>No trades yet</h2>
    <p class="sub">The ledger is empty. It only opens a position when a setup clears a composite score
      of ${fmt(cfg.min_composite, 0)}, and most scans find nothing. Which is the intended behaviour,
      not a fault. Run a scan above, or wait for the background one.</p>
  </div>` : ''}

  ${s.closed_count ? `
  <div class="panel span2 gap">
    <h2>${hg('Track record')}</h2>
    <div class="grid c4" style="margin-bottom:var(--space-3)">
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
    + 'least useful number here. Expectancy, the average result per trade, is what decides whether '
    + 'there is an edge. Treat anything under about fifty closed trades as noise.')}</p>
  </div>` : ''}

  <div id="roth-host" class="span-all"></div>

  ${open.length ? `
  <div id="book-risk-host" class="span-all">${
  STATE.bookRisk ? renderPortfolioRisk(STATE.bookRisk) : ''}</div>` : ''}

  ${closed.length ? `
  <div class="panel span2 gap">
    <h2>${hg('Closed trades')}</h2>
    <p class="sub">Most recent first. The exit reason is the honest part of the record. A table full
      of time stops means the signals were early, not unlucky.</p>
    <table class="data">
      <thead><tr><th>Position</th><th>Side</th><th>Size</th><th>Entry</th><th>Exit</th>
        <th>P&amp;L</th><th>Why it closed</th><th>Held</th><th>Closed</th></tr></thead>
      <tbody>${closedRows}</tbody>
    </table>
  </div>` : ''}

  <div class="panel span2 gap">
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
        <p class="caveat">Shares are sized so that being stopped out costs exactly the risk budget.
          A wide stop therefore buys fewer shares, not more risk. Options are sized on the whole
          premium, because a long option can genuinely go to zero and a stop cannot prevent it.</p>
      </div>
      <div>
        <h3>Entries and exits</h3>
        ${kv([
    ['Universe', cfg.universe === 'nasdaq' ? 'every NASDAQ common stock (~3,000)' : 'fixed watchlist'],
    ['Screened down to', fmt(cfg.shortlist_size, 0) + ' names per scan'],
    ['Takes a trade when', 'composite score ≥ ' + fmt(cfg.min_composite, 0) + ' (either direction)'],
    ['Stop', 'Just beyond the nearest real support or resistance level, or twice the average daily range if none is close'],
    ['Target', 'twice the risk distance. Fixed, not fitted'],
    ['Option exits', '−50% / +100% premium, underlying stop, or expiry'],
    ['Time stop', fmt(cfg.max_hold_days, 0) + ' days'],
    ['Per ticker', 'one idea at a time'],
    ['Trades only', 'during the regular session, 9:30–4:00 ET'],
  ])}
      </div>
    </div>
    <div class="callout bad" style="margin-top:var(--space-3)">
      <strong>What these numbers are not.</strong>
      <ul style="margin:var(--space-2) 0 0 var(--space-4);padding:0">
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
  ${renderIndexBoard(STATE.indexBoard)}

  <div class="panel span2 gap">
    <h2>${hg('Index regime')}</h2>
    <p class="sub">${gloss(idx.regime_summary || '')}</p>
    <table class="data">
      <thead><tr><th>Index</th><th>Last</th><th>1y</th><th>3y CAGR</th><th>5y CAGR</th><th>10y CAGR</th><th>vs 40w</th><th>vs 200w</th><th>Wk RSI</th><th>Drawdown</th><th>Phase</th></tr></thead>
      <tbody>${(idx.indices || []).map((r) => `<tr>
        <td class="name">${esc(r.name)}<div class="subnote">${esc(r.note || '')}</div></td>
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
      figure smooths through crashes rather than hiding them. Check the drawdown column alongside it.</p>
  </div>

  ${gvm.series ? `
  <div class="panel span2">
    <h2>${hg('Growth vs the broad market (QQQ / SPY)')} <span class="th-plain">· daily</span></h2>
    <p class="sub">${gloss(gvm.note || '')}</p>
    <div class="grid c2" style="margin-bottom:var(--space-2)">
      ${tile('QQQ / SPY ratio', fmt(gvm.qqq_spy_ratio, 3), 'rising means growth is leading')}
      ${tile('Over 3 months', fmtPct(gvm.chg_3m_pct, 1), 'growth vs broad market', signClass(gvm.chg_3m_pct))}
    </div>
    <div id="chart-growth-value"></div>
  </div>` : ''}
  `;

  if (gvm.series) {
    mount('chart-growth-value', (w) => lineChart({
      valueTags: true,
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
  const vh = h.valuation_history || {};

  if (h.error) { views.long.innerHTML = errorHTML(h.error); return; }

  views.long.innerHTML = `
  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Long-term view')} · ${esc(h.ticker)}</h2>
      <p class="sub">${esc(h.name || '')}${(h.fundamentals || {}).sector ? ' · ' + esc(h.fundamentals.sector) : ''}</p>
      <div style="display:flex;align-items:flex-end;gap:var(--space-5);flex-wrap:wrap">
        <div>
          <div class="hero-label">Conviction</div>
          <div class="hero ${signClass(h.conviction_score)}">${h.conviction_score > 0 ? '+' : ''}${fmt(h.conviction_score, 0)}</div>
          <div class="note subnote sm">Of a possible
            +${fmt((h.conviction_scale || {}).max_possible, 0)}</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:var(--space-2)">
          ${toneChip(h.conviction)}
          <span class="chip neutral"><span class="dot"></span>${esc(cap(lt.phase) || '')}</span>
        </div>
      </div>
      <div class="callout info">${gloss(h.plan || '')}</div>
      ${((h.data_quality || {}).warnings || []).map((w) => `<div class="callout bad">${gloss(w)}</div>`).join('')}

      <h3>${hg('What makes up this score')}${askPulse('composite')}</h3>
      <p class="sub">Every factor the model checked and what each one contributed. Mostly price
        behaviour. The valuation and income factors can add at most 13 of the
        ${fmt((h.conviction_scale || {}).max_possible, 0)} available points.</p>
      <table class="data">
        <thead><tr><th>Factor</th><th>Type</th><th>Points</th><th>Why</th></tr></thead>
        <tbody>${(h.conviction_factors || []).map((f) => `<tr>
          <td class="name">${esc(cap(f.label))}</td>
          <td class="muted">${esc(cap(f.kind))}</td>
          <td class="${signClass(f.points)}"><strong>${f.points > 0 ? '+' : ''}${fmt(f.points, 0)}</strong></td>
          <td style="color:var(--ink-2);font-size:var(--t-small)">${gloss(f.detail)}</td>
        </tr>`).join('')}
        <tr style="border-top:1px solid var(--border-strong)">
          <td class="name"><strong>Total</strong></td><td></td>
          <td class="${signClass(h.conviction_score)}"><strong>${h.conviction_score > 0 ? '+' : ''}${fmt(h.conviction_score, 0)}</strong></td>
          <td class="subnote sm">${
  (h.conviction_scale || {}).thresholds
    ? 'High at ' + h.conviction_scale.thresholds.high + '+, moderate at ' + h.conviction_scale.thresholds.moderate + '+' : ''}</td>
        </tr></tbody>
      </table>
      <p class="caveat">This is a trend-and-relative-strength model with a valuation sanity
        check. Not a fundamental analysis. A strong score means the price behaviour has been
        strong, not that the business is cheap or high quality.</p>
      <p class="caveat">${esc(h.disclaimer || '')}</p>
    </div>

    <div class="panel">
      <h2>${hg('Return & risk')}</h2>
      <p class="sub">Compound growth by horizon, against ${esc('SPY')} as the benchmark.</p>
      <div class="grid c4" style="margin-bottom:var(--space-3)">
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
      <p class="caveat">Return/vol and Sortino use a zero risk-free rate. A relative screen, not a performance report.</p>
    </div>
  </div>
  ${renderCloseDefence(d.close_defence, { horizonWord: 'this week' })}


  <div class="grid c2 gap">
    <div class="panel span2">
      <h2>${hg('Weekly structure')} <span class="th-plain">· weekly bars</span></h2>
      <p class="sub">${gloss(lt.guidance || '')} Weekly bars with the 40-week and 200-week averages. The lines that separate secular bull from bear phases.</p>
      <div id="lt-toolbar"></div>
      <div id="legend-weekly"></div>
      <div id="chart-weekly"></div>
      <div class="grid c3" style="margin-top:var(--space-3)">
        ${tile('vs 40-week SMA', fmtPct(lt.vs_40w_sma, 1), `level ${fmt(lt.sma_40w, 2)}`, signClass(lt.vs_40w_sma))}
        ${tile('vs 200-week SMA', fmtPct(lt.vs_200w_sma, 1), `level ${fmt(lt.sma_200w, 2)}`, signClass(lt.vs_200w_sma))}
        ${tile('Weekly RSI', fmt(lt.weekly_rsi, 1), '40-week slope ' + fmtPct(lt.slope_40w_pct_3m, 1))}
      </div>
    </div>
  </div>

  <div class="grid c2 gap">
    <div class="panel">
      <h2>${hg('Drawdown')} <span class="th-plain">· daily</span></h2>
      <p class="sub">Currently ${fmtPct(dd.current_drawdown_pct, 1)} from the all-time high of ${usd(dd.all_time_high)}, set on ${esc(dd.ath_date || '')}.
        Worst on record: ${fmtPct(dd.max_drawdown_pct, 1)} (${esc(dd.max_drawdown_date || '')}).</p>
      <div id="chart-drawdown"></div>
    </div>

    ${renderRevenueMultiple((d.holding || {}).revenue_multiple)}

    <div id="pe-host" class="span-all">${renderPeHistory(STATE.peHistory)}</div>

    ${vh.available ? `<div class="panel">
      <h2>${hg('Valuation vs its own history')}</h2>
      <p class="sub">A multiple only means something against a yardstick. The one that needs
        no cross-company assumptions is the company against itself. Is this expensive
        <em>for this name</em>?</p>
      <div class="grid c4">
        ${tile('Trailing P/E now', fmt(vh.current_pe, 1) + '\u00d7',
    vh.read ? cap(vh.read) : '',
    vh.percentile >= 75 ? 'down' : vh.percentile <= 25 ? 'up' : '')}
        ${tile('5-year median', fmt(vh.median_pe, 1) + '\u00d7',
    `Range ${fmt(vh.low_pe, 1)}\u00d7 to ${fmt(vh.high_pe, 1)}\u00d7 over ${
      fmt(vh.usable_years, 0)} profitable years`)}
        ${vh.percentile !== null && vh.percentile !== undefined
    ? tile('Where it sits', `${fmt(vh.percentile, 0)}th pct`,
      'of its own five-year range',
      vh.percentile >= 75 ? 'down' : vh.percentile <= 25 ? 'up' : '') : ''}
        ${vh.premium_to_median_pct !== null && vh.premium_to_median_pct !== undefined
    ? tile('Versus median', fmtPct(vh.premium_to_median_pct, 1),
      vh.premium_to_median_pct >= 0 ? 'paying up against its own norm'
        : 'below its own norm',
      vh.premium_to_median_pct >= 0 ? 'down' : 'up') : ''}
      </div>
      <table class="data narrow" style="margin-top:var(--space-3)">
        <thead><tr><th>Fiscal year</th><th>Diluted EPS</th><th>Average price</th>
          <th>Trailing P/E</th></tr></thead>
        <tbody>${(vh.years || []).map((y) => `<tr>
          <td class="name">${esc(y.period)}</td>
          <td>${fmt(y.eps, 2)}</td>
          <td>${usd(y.avg_price)}</td>
          <td>${y.pe !== null && y.pe !== undefined
    ? fmt(y.pe, 1) + '\u00d7'
    : `<span class="muted">${esc(y.note || 'n/a')}</span>`}</td>
        </tr>`).join('')}</tbody>
      </table>
      <p class="caveat">${gloss(vh.method || '')}</p>
    </div>` : ''}

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
          <td class="name muted">${esc(cap(z.kind))}</td>
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
        // Trimmed: the long form ran to ~30 characters per pill and five of them
        // stacked was most of what made this chart unreadable.
        label: `${z.label.replace(' retracement of the 3-year range', '')} · ${usd(z.price)}`,
        color: C.refSR,
        pattern: '6 4',
      }));

    // Twelve years of weekly OHLCV from the server, sliced and optionally rolled
    // up to months here. Falls back to the old closes-only arrays if an older
    // response is cached.
    const ltSer = (lt.series && (lt.series.dates || []).length)
      ? ltSlice(lt.series, ltRange, ltInterval)
      : { dates: lt.weekly_dates || [], close: lt.weekly_closes || [],
          shown_bars: (lt.weekly_dates || []).length,
          total_bars: (lt.weekly_dates || []).length };
    const ltCandles = ltMode === 'candle' && ltSer.open && ltSer.high && ltSer.low;
    const unit = ltSer.monthly ? 'month' : 'week';

    mount('lt-toolbar', () => {
      const wrap = document.createElement('div');
      wrap.className = 'chart-toolbar';
      wrap.innerHTML = `
        <span class="range-pick"><label for="lt-interval">Interval</label>
          <select id="lt-interval">${LT_INTERVALS.map((i) => `<option value="${i.key}"${
        i.key === ltInterval ? ' selected' : ''}>${i.label}</option>`).join('')}</select></span>
        ${rangePills(LT_RANGES, ltRange, 'data-lt-range', 'Timeframe')}
        <span class="seg">
          <button type="button" data-lt-mode="line" aria-pressed="${ltMode !== 'candle'}">Line</button>
          <button type="button" data-lt-mode="candle" aria-pressed="${ltMode === 'candle'}">Candles</button>
        </span>`;
      return wrap;
    });

    /* The moving averages, computed here rather than read off the payload.
     *
     * The server sends sma_40w and sma_200w as single numbers — today's value —
     * and this chart drew each as a horizontal line across the whole plot. On a
     * twelve-year view that is actively misleading: it looks like the average
     * and is really a flat line at the latest reading, so a reader comparing
     * 2019 price against "the 40-week average" was comparing it against 2026.
     *
     * Periods are in BARS, taking their unit from the interval, which is what
     * the Swing chart already does ('20-week SMA' on weekly, '20-day' on
     * daily). A 200-bar average needs 200 bars, and on the monthly rollup of a
     * twelve-year series there are only ~144 — so it is dropped rather than
     * drawn as an empty line, and the legend follows the same test. */
    const ltMa = (period) => {
      const vals = smaSeries(ltSer.close || [], period);
      return vals.some((v) => v !== null) ? vals : null;
    };
    /* Always drawn, deliberately not behind the shared Moving averages toggle.
     *
     * That toggle governs discretionary overlays on a daily chart, defaults to
     * off, and this view has no control for it — gating here would have deleted
     * the two lines this panel argues from ("price is above its 40-week
     * average" is the phase read) for anyone who had not turned on a switch
     * that lives on another tab. On the long-horizon view these averages are
     * the subject, not an overlay. */
    const ltMa40 = ltMa(40);
    const ltMa200 = ltMa(200);

    mount('legend-weekly', legend([
      ...(ltCandles
        ? [{ name: `Up ${unit}`, color: C.s3 }, { name: `Down ${unit}`, color: C.s8 }]
        : [{ name: `${ltSer.monthly ? 'Monthly' : 'Weekly'} close`, color: C.s1 }]),
      ...(ltMa40 ? [{ name: `40-${unit} average`, color: overlayStyle('sma50').color }] : []),
      ...(ltMa200 ? [{ name: `200-${unit} average`, color: overlayStyle('sma200').color }] : []),
      ...(showVol ? [{ name: 'Volume', color: C.ink2 }] : []),
      { name: 'Accumulation zones', color: C.refSR, dash: true },
    ]));

    mount('chart-weekly', (w) => lineChart({
      valueTags: true,
      width: w,
      // Matches the Swing chart. This was 340 against Swing's 420, so the
      // longest-horizon view on the terminal had the shortest plot.
      height: 420,
      labels: ltSer.dates || [],
      // Honours the same shared Volume toggle as every other price chart. The
      // weekly payload has carried volume all along and this chart dropped it.
      volume: showVol ? (ltSer.volume || null) : null,
      series: [
        { name: `${ltSer.monthly ? 'Monthly' : 'Weekly'} close`,
          values: ltSer.close, color: C.s1, hidden: ltCandles, fill: !ltCandles },
        ...(ltMa40 ? [{ name: `40-${unit} average`, values: ltMa40,
          color: overlayStyle('sma50').color, width: overlayStyle('sma50').width,
          marker: false }] : []),
        ...(ltMa200 ? [{ name: `200-${unit} average`, values: ltMa200,
          color: overlayStyle('sma200').color, width: overlayStyle('sma200').width,
          marker: false }] : []),
      ],
      candles: ltCandles
        ? { open: ltSer.open, high: ltSer.high, low: ltSer.low, close: ltSer.close }
        : null,
      // Only the zones remain as horizontal lines, because a retracement level
      // genuinely is one price. The averages are series now.
      refLines: zoneRefs,
      // Labels hug the left edge here. On a twelve-year chart the newest bars are
      // crowded against the right, so right-aligned tags covered the price action
      // they were annotating — which is what made this chart hard to read.
      refLabelSide: 'left',
      refLineFit: 'clip',
      yFormat: (x) => fmt(x, 0),
      valueFormat: (x) => fmt(x, 2),
    }));
  }

  if (dd.series) {
    drawPeChart(STATE.peHistory);
    mount('chart-drawdown', (w) => lineChart({
      valueTags: true,
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

/* Busy state for a view that is refetching.
 *
 * Every loader used to open with `views.x.innerHTML = loadingHTML(...)`, which
 * throws away a screen the reader was looking at and replaces it with a single
 * line of text. Switching from Swing to Macro and back meant the page went blank
 * and rebuilt from nothing each way, even though the payload was often already
 * cached and the wait was under a second. That flash is most of what reads as
 * unfinished.
 *
 * Two cases, and they want opposite things:
 *
 *   - First visit, nothing on screen: there is nothing to preserve, so render a
 *     skeleton in the shape of what is coming. Better than a bare sentence
 *     because the panel keeps the height it is about to have.
 *   - Already populated: keep the old numbers on screen, dim them slightly and
 *     mark the view aria-busy. Stale figures clearly labelled as loading are more
 *     useful than no figures, and nothing moves until the new ones land.
 *
 * The label is still announced for screen readers in both cases — the visual
 * treatment changes, the message does not. */
function viewSkeleton(label, rows = 4) {
  return `<div class="panel span-all view-skel" aria-busy="true">
    <p class="loading"><span class="spinner"></span>Loading ${esc(label)}…</p>
    <div class="skel-stack" aria-hidden="true">
      ${Array.from({ length: rows }, (_, i) => `<span class="skel-bar"
        style="width:${[92, 74, 84, 62, 78, 70][i % 6]}%;animation-delay:${i * 80}ms"></span>`).join('')}
    </div>
  </div>`;
}

function beginLoad(host, label, rows) {
  if (!host) return;
  const populated = host.children.length > 0 && !host.querySelector('.view-skel');
  if (!populated) {
    host.innerHTML = viewSkeleton(label, rows);
    return;
  }
  host.classList.add('is-busy');
  host.setAttribute('aria-busy', 'true');
  let bar = host.querySelector('.busy-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'busy-bar';
    bar.setAttribute('role', 'status');
    bar.innerHTML = `<span class="sr-only">Loading ${esc(label)}…</span>`;
    host.prepend(bar);
  }
}

function endLoad(host) {
  if (!host) return;
  host.classList.remove('is-busy');
  host.removeAttribute('aria-busy');
  const bar = host.querySelector('.busy-bar');
  if (bar) bar.remove();
}

/* =================================================================== LOADER */

/* The filing history is its own request.
 *
 * Deliberately not folded into the long-term payload: it needs SEC XBRL, which is
 * a different host with its own rate limits and its own cache lifetime measured in
 * days rather than minutes. Making the tab wait on it would put an agency's
 * politeness delay in front of a page that has everything else already. */
/** Seasonality loads after the tab, not with it.
 *
 * Fifteen years of daily bars for the ticker and the benchmark, plus the SEC
 * filing history for the reporting-month flag. None of it changes intraday —
 * the calendar is the one input that is known in advance — so making the page
 * wait on it would buy nothing.
 */
/** Rotation loads after the Macro tab, not with it.
 *
 * Two years of weekly bars for twelve symbols in one batched download. It is not
 * slow, but it is not what the tab is about either, and the rest of the page
 * should not wait behind it.
 */
async function loadRotation(force) {
  if (STATE.rotation && !force) return;
  try {
    STATE.rotation = await getJSON('/api/rotation');
  } catch (err) {
    STATE.rotation = { error: err.message };
  }
  const host = document.getElementById('rotation-host');
  if (host && STATE.view === 'market') {
    host.innerHTML = renderRotation(STATE.rotation);
    if (!STATE.rotation.error) {
      mount('chart-rotation', (w) => rotationChart(STATE.rotation.sectors || [], {
        width: w, height: Math.min(Math.max(w * 0.72, 380), 560),
      }));
    }
    revealPanels(host);
  }
}

/* `symbol` is optional and exists for the chart workspace, which tracks its own
 * ticker rather than the analysis one — the two are deliberately independent, so
 * this cannot just read STATE.ticker. */
async function loadSeasonality(force, symbol) {
  const sym = symbol || STATE.ticker;
  if (!sym) return;
  if (STATE.seasonalityFor === sym && !force) return;
  STATE.seasonalityFor = sym;
  try {
    STATE.seasonality = await getJSON(`/api/seasonality/${encodeURIComponent(sym)}`);
  } catch (err) {
    STATE.seasonality = { error: err.message, ticker: sym };
  }
  const host = document.getElementById('seasonality-host');
  if (host && STATE.view === 'swing') {
    host.innerHTML = renderSeasonality(STATE.seasonality);
    revealPanels(host);
  }
  // The workspace dock shows a compact version of the same payload.
  const dockHost = document.getElementById('ws-w-seasonality');
  if (dockHost && STATE.view === 'chart') {
    dockHost.innerHTML = wsSeasonalityMini(STATE.seasonality);
  }
}

async function loadPeHistory(force) {
  const sym = STATE.ticker;
  if (!sym) return;
  if (STATE.peHistoryFor === sym && !force) return;
  STATE.peHistoryFor = sym;
  try {
    STATE.peHistory = await getJSON(`/api/pe-history/${encodeURIComponent(sym)}`);
  } catch (err) {
    STATE.peHistory = { available: false, reason: err.message };
  }
  const host = document.getElementById('pe-host');
  if (host && STATE.view === 'long') {
    host.innerHTML = renderPeHistory(STATE.peHistory);
    drawPeChart(STATE.peHistory);
    revealPanels(host);
  }
}

async function loadPatternRates() {
  if (STATE.patternRates) return;
  try {
    STATE.patternRates = await getJSON('/api/patterns/base-rates');
  } catch (err) {
    STATE.patternRates = { available: false, reason: err.message };
  }
  // One panel, not the whole tab. This used to re-render the entire Swing view,
  // which threw away the staggered reveal that had just been applied to all 27
  // panels — every one lost its `reveal` class before it had animated, so the tab
  // arrived in a single block instead of flowing in. Mounting into the patterns
  // host leaves the rest of the page untouched.
  if (STATE.swing && STATE.view === 'swing') {
    mountPanel('patterns-host', renderPatterns(STATE.swing));
  }
}

async function loadSwing(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.swing && STATE.swing.ticker === STATE.ticker && !force) { revealPanels(views.swing); return; }
  if (!silent) beginLoad(views.swing, `options analytics for ${STATE.ticker}`);
  try {
    const data = await getJSON(`/api/ticker/${encodeURIComponent(STATE.ticker)}?max_expiries=4&macro=true`);
    STATE.swing = data;
    if (data.macro && !data.macro.error) {
      STATE.market = STATE.market || {};
      STATE.market.macro = data.macro;
    }
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderSwing(data);
    endLoad(views.swing);
    if (!silent) revealPanels(views.swing);
    loadPatternRates();
    loadIndicators();
    loadSeasonality();
    loadExtras();
    /* Also mounted here, not only from loadExtras.
     *
     * When the payload is already in STATE — a tab switch, a silent refresh —
     * loadExtras returns at its cache guard and never reaches its mount, while
     * renderSwing has just rendered the panel from that same cached state. The
     * result was a permanently empty chart box on every visit after the first.
     * Two frames, so the collapsible pass has re-parented and laid out. */
    requestAnimationFrame(() => requestAnimationFrame(mountRelativeChart));
    updateStatus();
    updateChatContext();
  } catch (err) {
    // A background refresh tick shouldn't wipe out a perfectly good dashboard
    // over one transient network blip — only a manual/foreground load does.
    if (!silent) {
      endLoad(views.swing);
      views.swing.innerHTML = errorHTML(err.message,
        { originUnreachable: err.originUnreachable });
    }
    else console.warn('Silent swing refresh failed:', err.message);
  }
}


/* ------------------------------------------------------------- daily brief
   Reports; it does not judge. Every other tab scores something — this one
   states what was published and links to the source, and the only numbers it
   generates are the price moves in the overview. That boundary is deliberate:
   a news page that quietly ranked securities would be an unlabelled
   recommendation, so catalyst tags here are descriptive and there is no
   composite. */

/* ------------------------------------------------------------- Optic's Read
 *
 * Laid out as desks rather than one long column: a ticker strip, the morning
 * desk, what's scheduled, a lead story, then Markets / Economy / Technology /
 * Politics / World. The shape is borrowed from a wire front page because the
 * job is the same — let someone scan for the two things they care about instead
 * of reading thirty headlines in source order.
 *
 * Company 8-K announcements used to sit in here and were removed on request.
 */

function briefAgo(iso) {
  if (!iso) return '';
  const then = Date.parse(iso);
  if (!isFinite(then)) return '';
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

/* ------------------------------------------------- when the read last changed
 *
 * "Last built 3h ago" on its own leaves the reader doing arithmetic to work out
 * whether that was before or after something they saw elsewhere. Over a weekend
 * — when the gap between builds is the whole point of the page — it is the least
 * useful form there is. The exact stamp answers the question; the relative form
 * stays alongside it because it is the faster read of the two.
 */

// Kept in step with BRIEF_ANCHOR_HOUR in app/main.py. If that moves, this is the
// other end of the same fact and has to move with it.
const BRIEF_ANCHOR_ET_HOUR = 9;

/** The wall-clock fields of an instant, read in a named zone. */
function clockParts(date, zone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: zone, hour12: false, hour: '2-digit', minute: '2-digit',
  }).formatToParts(date);
  const get = (t) => Number((parts.find((p) => p.type === t) || {}).value);
  return { hour: get('hour') % 24, minute: get('minute') };
}

/** The next 09:00 Eastern as an instant.
 *
 * Done by reading the Eastern clock and stepping forward by the difference,
 * rather than by arithmetic on a UTC offset — the offset is the thing that
 * changes at a DST boundary. Two passes: the first lands near the target, the
 * second re-reads the Eastern clock there and corrects the hour that a boundary
 * crossing would otherwise have introduced. */
function nextBriefAnchor(now = new Date()) {
  let when = new Date(now.getTime());
  for (let pass = 0; pass < 2; pass += 1) {
    let mins;
    try {
      const et = clockParts(when, 'America/New_York');
      mins = BRIEF_ANCHOR_ET_HOUR * 60 - (et.hour * 60 + et.minute);
    } catch (e) {
      return null;
    }
    if (mins <= 0 && pass === 0) mins += 24 * 60;
    when = new Date(when.getTime() + mins * 60000);
  }
  return when;
}

/** "Sat, Aug 30, 2026 at 8:35 pm GMT+2" — in whichever zone the reader picked. */
function stampIn(iso, zone) {
  if (!iso) return '';
  try {
    const date = new Date(iso).toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', timeZone: zone,
    });
    return `${date} at ${timeIn(iso, zone)} ${zoneAbbrev(zone, iso)}`;
  } catch (e) {
    return '';
  }
}

function roughGap(ms) {
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${Math.max(mins, 1)} minutes`;
  const hrs = Math.round(mins / 60);
  return hrs === 1 ? 'about an hour' : `about ${hrs} hours`;
}

/** The last-updated line for the Read hero, plus when the next one lands. */
function readUpdatedHTML(iso) {
  const zone = activeZone();
  const stamp = stampIn(iso, zone);
  const ago = briefAgo(iso);
  const next = nextBriefAnchor();
  const nextIso = next ? next.toISOString() : null;
  return `<p class="read-updated">
    <span class="read-updated-dot"></span>
    <strong>Last updated</strong> ${stamp ? esc(stamp) : 'time not recorded'}${
  ago ? ` <span class="read-updated-ago">· ${esc(ago)}</span>` : ''}
  </p>
  ${nextIso ? `<p class="read-next">Next rebuild ${esc(stampIn(nextIso, zone))}
    <span class="read-updated-ago">· in ${esc(roughGap(next - new Date()))}</span>.
    The terminal rebuilds this read at 9:00 am Eastern <strong>every day, weekends
    included</strong>, so it keeps picking up news while the market is shut and a
    Monday read covers everything back to Friday's close.</p>` : ''}`;
}

function briefWhen(iso) {
  if (!iso) return '<span>time not given</span>';
  const zone = activeZone();
  return `<span title="${esc(`${dayIn(iso, zone)} ${iso.slice(0, 10)}, ${
    timeIn(iso, zone)} ${zoneAbbrev(zone)}`)}">${esc(briefAgo(iso))}</span>`;
}

function briefTags(e) {
  return (e.catalysts || []).slice(0, 2).map((c) =>
    `<span class="chip ${c.importance === 'high' ? 'warn' : 'neutral'}"><i class="dot"></i>${
      esc(cap(c.type))}</span>`).join('');
}

function briefLink(e, text) {
  const label = text === undefined ? esc(e.title) : text;
  return e.url
    ? `<a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer nofollow">${label}</a>`
    : label;
}

function briefHeadline(e) {
  const tags = briefTags(e);
  return `<li class="brief-item tone-${esc(e.tone_label || 'neutral')}">
    <div class="brief-head">${briefLink(e)}</div>
    <div class="brief-meta">
      <span class="brief-src">${esc(e.source)}${e.source_detail ? ` · ${esc(e.source_detail)}` : ''}</span>
      <span class="brief-dot">·</span>${briefWhen(e.published)}${
        tags ? `<span class="brief-tags">${tags}</span>` : ''}
    </div>
  </li>`;
}

/* The one story given room. Picked by recency and source weight — never by tone,
 * and never by a model deciding what was interesting. */
function briefLead(e) {
  if (!e) return '';
  return `<div class="read-lead tone-${esc(e.tone_label || 'neutral')}">
    <div class="read-lead-kicker">Leading now</div>
    <h3 class="read-lead-title">${briefLink(e)}</h3>
    ${e.summary ? `<p class="read-lead-sum">${esc(e.summary)}</p>` : ''}
    <div class="brief-meta">
      <span class="brief-src">${esc(e.source)}${e.source_detail ? ` · ${esc(e.source_detail)}` : ''}</span>
      <span class="brief-dot">·</span>${briefWhen(e.published)}
      <span class="brief-tags">${briefTags(e)}</span>
    </div>
  </div>`;
}

/* Index strip. Same idea as the row of quotes across the top of a wire site:
 * the numbers everything else in the page is describing, in one glance. */
function briefStrip(indices) {
  const rows = (indices || []).filter((r) => r.day !== null && r.day !== undefined);
  if (!rows.length) return '';
  return `<div class="read-strip">${rows.map((r) => `
    <div class="read-tick">
      <span class="read-tick-name">${esc(r.name)}</span>
      <span class="read-tick-last">${fmt(r.last, 2)}</span>
      <span class="read-tick-day ${signClass(r.day)}">${fmtPct(r.day, 2)}</span>
    </div>`).join('')}</div>`;
}

const READ_CONF_HINT = {
  published: 'Date and time as published by the agency.',
  recurring: 'Derived from the release’s weekly schedule, not a confirmed posting — '
    + 'a federal holiday can move it.',
};

/* Impact bands. Three, not a 1-10 number: the reader's decision is binary —
 * be flat into this or not — and the gap between weight 5 and 6 is not real. */
const CAL_IMPACT_LABEL = { high: 'High impact', medium: 'Medium', low: 'Low' };

/* Category labels for the filter row. The keys match events.CATEGORY_RULES —
 * if a category is added server-side and not here it falls back to its id
 * rather than disappearing from the filter. */
const CAL_CATEGORY_LABEL = {
  inflation: 'Inflation',
  fed: 'Fed',
  jobs: 'Jobs',
  growth: 'Growth',
  housing: 'Housing',
  energy: 'Energy',
  positioning: 'Positioning',
  other: 'Other',
};

/* Format a reading in its own unit. The unit and the rounding both come from
 * fred.py — it already picked the digits appropriate to the series, so this
 * appends a symbol rather than re-rounding and losing a decimal.
 *
 * Units are '%', 'k' and 'm' — matching fred.SERIES_MAP, not invented here. */
function calNum(value, unit) {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const sign = n > 0 ? '+' : '';
  if (unit === 'k') return `${sign}${n}K`;
  if (unit === 'm') return `${n}M`;
  if (unit === '%') return `${sign}${n}%`;
  return String(n);
}

/* The three-number strip: previous, forecast, actual.
 *
 * Forecast is always empty, and it is still shown as a labelled column. Leaving
 * the column out would let the row read as complete when the one number a
 * reader most wants is the one we cannot source — an explicit blank with the
 * reason under the drawer is the honest version. */
function calReadings(r) {
  if (!r || !r.available) return '<span class="cal-nums empty" aria-hidden="true"></span>';
  const cell = (label, value, cls, blank) => `<span class="cal-num ${cls}">
    <span class="cal-num-lbl">${label}</span>
    <span class="cal-num-val${value === null && blank ? ' pending' : ''}">${
  value === null ? (blank || '—') : esc(value)}</span>
  </span>`;
  // "pending" rather than an em-dash on a release that has not happened: a dash
  // reads as data we failed to find, and this one does not exist yet.
  return `<span class="cal-nums">
    ${cell('prev', calNum(r.previous, r.unit), 'prev')}
    ${cell('est', null, 'est')}
    ${cell('actual', calNum(r.actual, r.unit), 'act',
    r.is_upcoming ? 'pending' : null)}
  </span>`;
}

/* One calendar row. Expandable when there is something to explain, a plain row
 * when there is not — a disclosure arrow that opens onto nothing trains the
 * reader to stop clicking the ones that would have been worth opening. */
function calRow(e) {
  const impact = e.impact || 'low';
  const readings = e.readings || {};
  const head = `
    <span class="read-cal-time">${esc(e.time_label || 'all day')}</span>
    <span class="read-cal-what">
      ${e.short ? `<span class="chip strong"><i class="dot"></i>${esc(e.short)}</span>` : ''}
      ${briefLink({ url: e.source_url, title: e.title })}
    </span>
    ${calReadings(readings)}
    <span class="cal-impact ${impact}" title="${esc(e.impact_note || '')}">${
  esc(CAL_IMPACT_LABEL[impact] || impact)}</span>
    <span class="read-cal-who" title="${esc(READ_CONF_HINT[e.confidence] || '')}">${
  esc(e.agency_short)}${e.confidence === 'recurring' ? ' · scheduled' : ''}</span>`;

  const cls = `read-cal-row${e.importance >= 9 ? ' major' : ''}`;
  if (!e.why && !readings.available) return `<div class="${cls}">${head}</div>`;

  const prev = e.previous ? `
    <div class="cal-prev">
      <span class="cal-prev-tag">Last time</span>
      <a href="${esc(e.previous.url || '#')}" target="_blank" rel="noopener noreferrer nofollow"
        >${esc(e.previous.headline)}</a>
      ${e.previous.age_days !== null && e.previous.age_days !== undefined
    ? `<span class="cal-prev-age">${fmt(e.previous.age_days, 0)} days ago</span>` : ''}
    </div>` : '';

  const detail = readings.available ? `
    <div class="cal-detail">
      <div class="cal-detail-grid">
        <div><span class="cal-detail-lbl">Series</span>
          <span class="cal-detail-val">${esc(readings.series_label || '')}
            <span class="cal-detail-id">${esc(readings.series || '')}</span></span></div>
        <div><span class="cal-detail-lbl">${
  readings.is_upcoming ? 'Previous reading' : 'This print'}</span>
          <span class="cal-detail-val">${
  esc(calNum(readings.is_upcoming ? readings.previous : readings.actual, readings.unit) || '—')}
            ${readings.as_of ? `<span class="cal-detail-id">as of ${
    esc(readings.as_of)}</span>` : ''}</span></div>
        <div><span class="cal-detail-lbl">Consensus</span>
          <span class="cal-detail-val">not carried</span></div>
      </div>
      <p class="cal-detail-note">${esc(readings.forecast_note || '')}</p>
      ${readings.is_upcoming
    ? `<p class="cal-detail-note">This release has not printed. The figure above is what
        the next one will be compared against, not a result.</p>` : ''}
    </div>` : '';

  return `<details class="${cls} cal-open">
    <summary>${head}<i class="cal-caret" aria-hidden="true"></i></summary>
    <div class="cal-why">
      ${e.why ? `<p>${esc(e.why)}</p>` : ''}
      ${detail}
      ${prev}
    </div>
  </details>`;
}

/* Vanna and charm exposure — the other two dealer-hedging channels.
 *
 * A dealer's hedge is a function of three things, and gamma is only one of them.
 * Delta moves when spot moves (gamma), when implied volatility moves (vanna),
 * and when time simply passes (charm). GEX answers the first question and the
 * terminal has always computed the other two — they were in the payload and
 * nothing rendered them.
 *
 * Units are already per readable step: vanna is divided by 100 in the greeks, so
 * it is dollars of dealer delta per ONE point of implied vol, and charm is
 * divided by 365, so it is dollars per calendar day.
 *
 * What this panel deliberately does NOT do is give vanna a flip point. Gamma has
 * one because the sign of gamma exposure changes at a computable spot price.
 * Vanna's effect depends on the path implied volatility takes, and this terminal
 * does not forecast volatility — so the magnitudes are shown, the mechanism is
 * explained, and no crossing level is invented to look symmetrical with GEX. */
/* ------------------------------------------------- "Ask Pulse" buttons

   Some panels here are genuinely hard the first time you meet them. A gamma
   profile across spot, a vanna number, a value area — the tooltip says what the
   words mean, but "what does this mean *for the thing I am looking at right
   now*" is a different question, and it is the one people actually have.

   So each of these buttons opens Pulse with a prompt already written for that
   section and this ticker. Two deliberate choices:

   **The prompt is placed in the box, not sent.** Sending on click would spend
   money on a request the reader did not word and cannot preview, and it takes
   the question away from them. Seeing a good prompt and being able to edit it
   also teaches what a good prompt looks like, which a silent auto-send does not.

   **Each prompt asks for plain language explicitly.** Without that the answer
   comes back in the same register as the panel, which is the thing the reader
   was already stuck on. */

const PULSE_TOPICS = {
  gex: 'Explain the dealer gamma exposure (GEX) panel for {t} in plain language. What is '
    + 'the flip point, which side of it are we on, and what does that actually mean for how '
    + "the stock is likely to trade today? Assume I have not met the term before.",
  'gamma-profile': 'Explain the "gamma profile across spot" chart for {t} as if I have never '
    + 'seen one. What is the curve showing, what does the zero crossing mean, and how would I '
    + 'use it when deciding whether to trade this today?',
  vanna: 'Explain vanna and charm exposure for {t} in plain English. I understand gamma is '
    + 'about price moving. What are these two about, why should I care, and which of the '
    + 'three matters most for this name right now?',
  flow: 'Explain the call-versus-put flow panel for {t} simply. What is it actually measuring, '
    + 'why is it called a proxy, and how much weight should I put on it?',
  iv: 'Explain implied volatility, IV rank and the IV/HV ratio for {t} in plain language. Are '
    + 'options on this name currently expensive or cheap, and compared to what?',
  profile: 'Explain the market profile and value area for {t} as if I am new to it. What is the '
    + 'point of control, what does the value area tell me, and how do traders actually use them?',
  composite: 'Explain how the composite score for {t} is built and what it is really saying. '
    + 'Which components are pulling which way, and where do they disagree?',
  defence: 'Explain the "close defence" idea for {t} in plain language. Why does a closing '
    + 'price matter more than an intraday one, and what exactly has to hold?',
  feargreed: 'Explain the Fear & Greed reading in plain language. What are the five inputs, what is it actually measuring, and how much weight should I put on an extreme reading?',
  indicators: 'Explain the optional indicators in plain language. VWAP, ADX, Keltner versus Bollinger, on-balance volume, the relative strength line. Which of these do institutions actually use, and for what?',
  pehistory: 'Explain the multiple and revenue history panel. What is a trailing P/E, why does it matter that earnings are attached to the filing date rather than the quarter end, and what does it mean when revenue is growing while the multiple falls?',
  morning: 'Explain the morning desk. What period does it cover, why does the window change between a Monday and a Tuesday, and what does it deliberately not tell me about the geopolitical headlines it lists?',
  global: 'Explain the overnight worldwide panel. Why are the markets ordered by session, what does the correlation to the S&P actually tell me, and should I read across from a big move in Korea or China to the US open?',
  patterns: 'Explain the chart patterns panel in plain language. What does it mean that a pattern is confirmed or not, what is a supply or demand zone as opposed to support, and how should I read the fact that most of these patterns measure close to a coin toss?',
  compare: 'Explain the side-by-side comparison. Why are the three horizons ranked separately, and what does it mean when a name is best on one and worst on another?',
  calendar: 'Explain the economic calendar in plain language. What do prev, est and actual mean, why is the estimate column always empty, and which of the releases showing here actually moves the market?',
  earningsweek: "Explain the earnings week calendar. What does the street's consensus EPS mean, why is there no before-open or after-close split, and which of these reports actually moves the index?",
  books: 'Explain the three books. What actually differs between conservative, balanced and aggressive, and what does comparing them tell me that one book alone would not?',
  priority: 'Explain the priority board. What are the four columns, how is the ordering decided, and which column should I actually look at first?',
  revmultiple: 'Explain the revenue-and-multiple panel for {t} in plain language. What does it mean when revenue is growing but the P/E is falling, and which one should I pay more attention to?',
  impliedcorr: 'Explain implied correlation in plain language. What does it mean that index implied vol is lower than the vol of its own components, and what is a dispersion trade?',
  evaluate: 'Explain the signal evaluation panel in plain language. What is an information coefficient, why are the random and single-factor controls there, and what does it mean that the composite loses to a single momentum number?',
  sectorconfirm: 'Explain the sector confirmation panel for {t} in plain language. What is the difference between relative strength against SPY and against the sector ETF, and why does it matter which one is stronger?',
  sectorboard: 'Explain the sector board in plain language. What are the bull-above and bear-below levels, why does the prior session\'s high and low matter, and what is the difference between a sector trending up and money rotating into it?',
  regime: 'Explain the index regime score in plain language. What kind of market is this '
    + 'right now, how is the number built, and what should it change about how I read '
    + 'individual setups?',
  levels: 'Explain the call wall, put wall and gamma pin for {t} simply. Why would dealer '
    + 'hedging make these act like a ceiling or a floor, and how reliable is that?',
};

/* The button. Small, quiet, and next to the heading it explains. */
function askPulse(topic) {
  return `<button type="button" class="ask-pulse" data-ask="${esc(topic)}"
    title="Have Pulse explain this section in plain language">Ask Pulse</button>`;
}

function openPulseWith(topic) {
  const tmpl = PULSE_TOPICS[topic];
  if (!tmpl) return;
  const ticker = STATE.ticker || 'the market';
  const text = tmpl.replace(/\{t\}/g, ticker);
  document.body.classList.add('chat-open');
  const box = $('#chat-input');
  if (!box) return;
  box.value = text;
  box.focus();
  // Put the caret at the end rather than selecting, so Enter sends as-is but
  // typing edits rather than replaces.
  box.setSelectionRange(text.length, text.length);
  box.dispatchEvent(new Event('input', { bubbles: true }));
}

function renderVanna(gex) {
  const t = (gex || {}).totals || {};
  const vanna = t.net_vanna;
  const charm = t.net_charm;
  if (vanna === undefined && charm === undefined) return '';

  const g1 = Math.abs(t.net_gex || 0);        // $ delta per 1% spot move
  const v1 = Math.abs(vanna || 0);            // $ delta per 1 vol point
  // Which hedging channel is larger right now, in each one's own natural step.
  // Comparable because both are dollars of dealer delta per one unit of the
  // thing that moved — a 1% move in spot, a 1-point move in implied vol.
  const dominant = (g1 && v1)
    ? (g1 >= v1 ? 'price' : 'volatility')
    : null;
  const ratio = (g1 && v1) ? (Math.max(g1, v1) / Math.min(g1, v1)) : null;

  return `<div class="grid c2 gap">
    <div class="panel span2">
      <h2>${hg('VEX. Dealer vanna exposure')}${askPulse('vanna')}</h2>
      <p class="sub">Dealer hedging responds to three things, and gamma is only one.
        Delta moves when the stock moves, when implied volatility moves, and when time
        passes. These are the other two.</p>

      <div class="grid c2" style="margin-top:var(--space-1)">
        <div>
          <h3>${hg('Vanna')}</h3>
          <div class="hero ${signClass(vanna)}" style="font-size:var(--t-d2)">${
  vanna >= 0 ? '+' : '−'}$${fmtCompact(Math.abs(vanna))}</div>
          <p class="sub">of dealer delta per <strong>1 point</strong> of implied volatility.</p>
          <p class="note">Vanna is the same for a call and a put at the same strike. It is a
            property of how far the strike sits from the price, not of the option type. What
            makes the total signed is the assumption about which side the dealer is on.</p>
        </div>
        <div>
          <h3>${hg('Charm')}</h3>
          <div class="hero ${signClass(charm)}" style="font-size:var(--t-d2)">${
  charm >= 0 ? '+' : '−'}$${fmtCompact(Math.abs(charm))}</div>
          <p class="sub">of dealer delta per <strong>calendar day</strong>, from time alone.</p>
          <p class="note">This is the flow that builds into expiry: with neither price nor
            volatility moving, the hedge still has to change, which is where the drift into
            an opex Friday comes from.</p>
        </div>
      </div>

      ${dominant ? `<div class="callout info" style="margin-top:var(--space-3)">
        <strong>Right now the ${dominant} channel is larger.</strong>
        A 1% move in the stock shifts dealer delta by about $${fmtCompact(g1)};
        a 1-point move in implied volatility shifts it by about $${fmtCompact(v1)}.
        Roughly ${fmt(ratio, 1)}× ${dominant === 'price' ? 'more from price' : 'more from volatility'}.
        ${dominant === 'volatility'
    ? 'When vanna dominates, a repricing of risk moves the hedge more than the tape does, '
      + 'which is how a session can drift without any obvious news in the price.'
    : 'When gamma dominates, the hedging that matters is driven by the stock itself, and '
      + 'the GEX flip point above is the level to watch.'}</div>` : ''}

      <p class="caveat">${gloss('Same sign convention and the same estimate as GEX above — '
    + 'these are computed from the same chain and the same dealer assumption, so they '
    + 'inherit the same uncertainty. Open interest is a stale, once-a-day figure and '
    + 'the dealer side is assumed rather than observed.')}</p>
      <p class="caveat">There is deliberately no vanna equivalent of the gamma flip point.
        Gamma has one because the sign of gamma exposure changes at a spot price that can be
        computed. Vanna's effect depends on the path implied volatility takes, and this
        terminal does not forecast volatility. Inventing a crossing level here would look
        symmetrical and mean nothing.</p>
    </div>
  </div>
`;
}

/* Upcoming releases. Importance drives size, not colour: a CPI print and a
 * county-wage release are both facts about a calendar, and only one of them
 * moves anything.
 *
 * Filtered client-side. The whole 21-day window arrives in one payload, so
 * narrowing it to "high impact" or "inflation" is a re-render, not a refetch —
 * a filter that costs a network round trip gets used once. */
const CAL_RANGES = [
  { id: 'today', label: 'Today', days: 0 },
  { id: 'week', label: 'This week', days: 6 },
  { id: 'all', label: 'Next 21 days', days: null },
];

function calFilterState() {
  return { impact: STATE.calImpact || 'all', range: STATE.calRange || 'all' };
}

function calMatches(e, f) {
  if (f.impact === 'high' && e.impact !== 'high') return false;
  if (f.impact !== 'all' && f.impact !== 'high' && e.category !== f.impact) return false;
  const days = CAL_RANGES.find((r) => r.id === f.range);
  if (days && days.days !== null && (e.days_away === null || e.days_away === undefined
    || e.days_away > days.days)) return false;
  return true;
}

function briefCalendar(cal) {
  const all = (cal && cal.events) || [];
  if (!all.length) {
    return `<div class="panel"><h2>On the calendar</h2>
      <p class="sub">Nothing scheduled in the next ${cal ? cal.horizon_days : 21} days
      from the sources we read.</p></div>`;
  }
  const f = calFilterState();
  const events = all.filter((e) => calMatches(e, f));

  // Only the categories actually in this window get a pill. A "Housing" filter
  // that always returns nothing is worse than no filter.
  const present = [];
  all.forEach((e) => {
    if (e.category && !present.includes(e.category)) present.push(e.category);
  });
  const count = (id) => all.filter((e) => calMatches(e, { ...f, impact: id })).length;
  const pill = (id, label) => `<button type="button" class="cal-pill${
    f.impact === id ? ' on' : ''}" data-cal-impact="${esc(id)}"
    aria-pressed="${f.impact === id}">${esc(label)}
    <span class="cal-pill-n">${count(id)}</span></button>`;

  const filters = `<div class="cal-filters">
    <div class="cal-pills" role="group" aria-label="Filter by category">
      ${pill('all', 'All')}
      ${pill('high', 'High impact')}
      ${present.map((c) => pill(c, CAL_CATEGORY_LABEL[c] || c)).join('')}
    </div>
    <div class="cal-pills" role="group" aria-label="Filter by date">
      ${CAL_RANGES.map((r) => `<button type="button" class="cal-pill${
    f.range === r.id ? ' on' : ''}" data-cal-range="${r.id}"
        aria-pressed="${f.range === r.id}">${esc(r.label)}</button>`).join('')}
    </div>
  </div>`;

  const byDay = new Map();
  events.forEach((e) => {
    const key = e.when_label || '';
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(e);
  });
  const groups = [...byDay.entries()].map(([label, rows]) => `
    <div class="read-cal-day">
      <div class="read-cal-date">${esc(label)}</div>
      <div class="read-cal-rows">${rows.map((e) => calRow(e)).join('')}</div>
    </div>`).join('');
  const derived = events.some((e) => e.confidence === 'recurring');
  const priced = events.filter((e) => (e.readings || {}).available).length;

  return `<div class="panel" id="cal-panel">
    <h2>${hg('On the calendar')}${askPulse('calendar')}</h2>
    <p class="sub">Scheduled releases in the next ${cal.horizon_days} days, from each
      agency's own calendar. Times are Eastern. Open a row for what it measures and
      the figure the next print will be compared against.</p>
    ${filters}
    ${events.length ? `<div class="read-cal">${groups}</div>` : `
      <p class="sub" style="margin-top:var(--space-4)">Nothing in this window matches that filter.
        ${all.length} release${all.length === 1 ? '' : 's'} scheduled overall.</p>`}
    <p class="caveat">A date here says a release is scheduled. Never what it will say.
      ${priced ? `Prev and actual are read from FRED for the ${priced} release${
    priced === 1 ? '' : 's'} in view that map to a published series; the rest carry no
      numbers because no free series matches them cleanly.` : ''}
      The estimate column is deliberately empty everywhere: consensus forecasts are a
      surveyed, licensed product, and a “forecast” quietly copied from a stale free
      mirror is worse than an honest gap.
      ${derived ? 'Rows marked <em>scheduled</em> come from a recurring weekly rule rather '
        + 'than a published date: the CFTC publishes no machine-readable calendar, so a '
        + 'federal holiday can shift the real posting.' : ''}
      ${(cal.degraded || []).length ? `The ${cal.degraded.join(' and ')} calendar could not be
        read on this refresh, so releases from it are missing.` : ''}</p>
  </div>`;
}

/* The index regime score: one number for what kind of tape this is.
 *
 * Deliberately not a verdict on any security. It answers "is the market helping
 * or hindering right now", which is the context every other panel is read
 * against — a +48 setup in a defensive tape is a worse setup, and until this
 * existed the reader had to assemble that judgement from four panels by eye.
 *
 * The components are shown with their weights and their own scores because the
 * composite alone hides the interesting case: +20 with breadth at -60 is a very
 * different market from +20 with everything at +20. */
const REGIME_LABELS = {
  trend: 'Trend', breadth: 'Breadth', volatility: 'Volatility',
  participation: 'Participation', leadership: 'Leadership',
};

const REGIME_WHY = {
  trend: 'Where the S&P has been over the past week and month. The direction the '
    + 'tape has actually been travelling, not where anyone thinks it should go.',
  breadth: 'The share of sectors trading above their own 200-day average. An index '
    + 'carried by five names is a different market from the same index carried by '
    + 'four hundred, and the headline level cannot tell them apart.',
  volatility: 'The VIX level, and which way it moved today. A low and falling VIX '
    + 'means hedging is cheap and nobody is rushing to buy protection.',
  participation: 'Small caps against the S&P over a month. Small caps leading is a '
    + 'genuine appetite-for-risk tell; lagging badly is an early warning.',
  leadership: 'How many sectors are higher today. A broad advance is more durable '
    + 'than one carried by a single group.',
};

function regimeBar(value) {
  // A centre-anchored bar: the zero line is the thing being compared against,
  // so a bar growing left from centre reads as negative without needing a label.
  const v = Math.max(-100, Math.min(100, Number(value) || 0));
  const half = Math.abs(v) / 2;
  const side = v >= 0 ? `left:50%;width:${half}%` : `right:50%;width:${half}%`;
  return `<span class="regime-bar"><i class="regime-fill ${v >= 0 ? 'pos' : 'neg'}"
    style="${side}"></i></span>`;
}

function briefRegime(r) {
  if (!r || !r.available) return '';
  const score = Number(r.score);
  const cls = score >= 12 ? 'pos' : score <= -12 ? 'neg' : 'flat';
  const comps = r.components || {};
  const weights = r.weights || {};
  const rows = Object.keys(REGIME_LABELS)
    .filter((k) => comps[k] !== undefined && comps[k] !== null)
    .map((k) => `<tr>
      <td class="name"><dfn class="gloss-term" tabindex="0"
        data-def="${esc(REGIME_WHY[k])}">${esc(REGIME_LABELS[k])}</dfn></td>
      <td style="width:44%">${regimeBar(comps[k])}</td>
      <td class="num ${signClass(comps[k])}">${comps[k] > 0 ? '+' : ''}${fmt(comps[k], 0)}</td>
      <td class="num muted">${fmt(weights[k], 0)}%</td>
    </tr>`).join('');

  return `<div class="panel">
    <h2>${hg('Market regime score')}${askPulse('regime')}</h2>
    <div class="regime-head">
      <div>
        <div class="hero ${cls}">${score > 0 ? '+' : ''}${fmt(score, 0)}</div>
        <span class="note muted">on a −100 to +100 scale</span>
      </div>
      <div class="regime-verdict">
        <span class="regime-stance ${cls}">${esc(r.stance || '')}</span>
        <p class="regime-plain">${esc(r.plain || '')}</p>
        ${r.effect ? `<p class="regime-effect">${esc(r.effect)}</p>` : ''}
      </div>
    </div>
    <table class="data regime-table">
      <thead><tr><th>Input</th><th></th><th class="num">Score</th><th class="num">Weight</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${(r.notes || []).length ? `<ul class="regime-notes">${
  r.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
    ${(r.conflicts || []).length ? `<div class="callout">
      <strong>Not everything agrees.</strong> ${esc(r.conflicts.join('; '))}. A composite
      built from inputs pulling in opposite directions is a weaker read than the same
      number with everything aligned.</div>`
    : `<p class="caveat">All ${Object.keys(comps).length} inputs point the same way as the
      composite${r.agreement_pct !== undefined ? ` (${fmt(r.agreement_pct, 0)}% agreement)` : ''}.</p>`}
    <p class="caveat">${gloss(r.scale_note || '')}</p>
    <p class="caveat">${gloss(r.method || '')}</p>
  </div>`;
}

function briefSourceLine(sources) {
  if (!sources || !sources.length) return '';
  const bad = sources.filter((s) => s.error);
  const ok = sources.filter((s) => !s.error);
  const names = [...new Set(ok.map((s) => s.name))].join(', ');
  let text = ok.length ? `Sources: ${names}.` : '';
  if (bad.length) {
    text += ` ${bad.length} source${bad.length === 1 ? '' : 's'} unreachable on the last`
      + ` refresh (${bad.map((s) => s.name).join(', ')})`
      + `${bad.some((s) => s.stale) ? '. Showing the last good copy' : ''}.`;
  }
  return `<p class="caveat">${esc(text)}</p>`;
}

/* ------------------------------------------------------------- wire search */

let readSearchSeq = 0;

async function runReadSearch(query) {
  const host = document.getElementById('read-results');
  if (!host) return;
  const q = (query || '').trim();
  if (!q) {
    host.innerHTML = '';
    return;
  }
  const seq = ++readSearchSeq;
  host.innerHTML = '<p class="sub">Searching…</p>';
  try {
    const d = await getJSON(`/api/brief/search?q=${encodeURIComponent(q)}`);
    if (seq !== readSearchSeq) return;   // a later keystroke already won
    if (!d.results || !d.results.length) {
      host.innerHTML = `<p class="sub">No headline matches “${esc(q)}” in the
        ${d.searched || 0} stories currently loaded.</p>`;
      return;
    }
    host.innerHTML = `<p class="sub">${d.matched} match${d.matched === 1 ? '' : 'es'}
      in ${d.searched} stories across ${d.sources} sources.</p>
      <ul class="brief-list">${d.results.map(briefHeadline).join('')}</ul>`;
  } catch (err) {
    if (seq !== readSearchSeq) return;
    host.innerHTML = `<p class="err">Could not search. ${esc(err.message || '')}</p>`;
  }
}

function renderBrief(d) {
  hideTip();
  if (d.missing) {
    views.brief.innerHTML = `<div class="panel"><h2>Nothing on record for ${esc(d.day)}</h2>
      <p class="sub">${esc(d.reason || '')} The record starts the first day the
      server ran this tab.</p></div>`;
    return;
  }

  const o = d.overview || {};
  const macro = d.macro || {};
  const wires = d.wires || {};
  const summary = d.summary || {};
  const groups = o.groups || {};
  const desks = wires.desks || [];

  const deskNav = desks.length
    ? `<nav class="read-nav">${desks.map((k) =>
        `<a href="#read-desk-${esc(k.id)}">${esc(k.label)}</a>`).join('')}</nav>`
    : '';

  views.brief.innerHTML = `
  ${briefStrip(groups.indices)}

  <div class="panel read-hero">
    <div class="read-hero-top">
      <div>
        <h2>Optic's Read: ${esc(d.day)}</h2>
        ${readUpdatedHTML(d.built_at)}
      </div>
      <div class="read-search">
        <input id="read-q" type="search" placeholder="Search the headlines"
               autocomplete="off" aria-label="Search headlines">
      </div>
    </div>
    <div id="read-results"></div>
    ${legalBanner('brief')}
  </div>

  <div class="panel span-all">
    <h2>${hg('Morning desk')}${askPulse('morning')}</h2>
    <p class="sub">${esc(summary.headline || '')}</p>
    <!-- What period this read covers, stated rather than assumed. On a Monday it
         is ~65 hours and on a Tuesday ~24, and a reader checking whether the
         weekend is in here should not have to work that out. -->
    ${(d.wires || {}).window_hours ? `<p class="brief-window">Covering the
      ${fmt(d.wires.window_hours, 0)} hours since the previous session closed${
  d.wires.window_hours >= 48 ? '. The full weekend' : ''}. Rebuilt at 9:00 Eastern
      every day, weekends included, so nothing that happens while the market is
      shut waits until Monday to appear.</p>` : ''}
    <div class="brief-summary">
      ${briefProse(summary.paragraphs)
        || '<p class="sub">Market moves were not available on this refresh.</p>'}
    </div>
    <p class="caveat">${esc(summary.method || '')} ${esc(o.note || '')}</p>
  </div>

  <div id="global-host" class="span-all">${renderGlobal(STATE.globalOvernight)}</div>

  <div id="priority-host" class="span-all">${renderPriority(STATE.priority)}</div>

  <div id="catmode-host" class="span-all">${renderCatalystMode(STATE.catalystMode)}</div>

  <div id="catalyst-host" class="span-all">${
  STATE.catalysts ? renderCatalysts(STATE.catalysts) : ''}</div>

  <div id="weekly-host" class="span-all">${renderWeekly(STATE.weekly)}</div>

  <div id="sentiment-host" class="span-all">${renderSentiment(STATE.sentiment)}</div>

  ${briefRegime(d.index_regime)}

  ${briefCalendar(d.calendar)}

  ${briefLead(wires.lead)}
  ${deskNav}

  <div class="read-desks">
    ${desks.map((k) => `
      <section class="panel read-desk" id="read-desk-${esc(k.id)}">
        <h2>${esc(k.label)}</h2>
        <ul class="brief-list">${k.entries.map(briefHeadline).join('')}</ul>
      </section>`).join('')}
  </div>

  <div class="panel">
    <h2>Official releases</h2>
    <p class="sub">Federal Reserve, Bureau of Labor Statistics, Bureau of Economic
      Analysis and SEC. Published releases, first-hand.</p>
    ${macro.entries && macro.entries.length
      ? `<ul class="brief-list">${macro.entries.map(briefHeadline).join('')}</ul>`
      : '<p class="sub">Nothing published recently.</p>'}
    ${macro.backfilled
      ? `<p class="caveat">${macro.in_window === 0 ? 'Nothing new' : `Only ${macro.in_window} release${
          macro.in_window === 1 ? '' : 's'}`} in the last ${Math.round((macro.window_hours || 0) / 24)} days,
         so the ${macro.backfilled} most recent earlier release${macro.backfilled === 1 ? '' : 's'} are shown
         as well. Official statistics are periodic; each card carries its own date.</p>`
      : ''}
    ${briefSourceLine(macro.sources)}
  </div>

  <div class="panel">
    <h2>Where this comes from</h2>
    <p class="sub">${esc(d.attribution || '')}</p>
    ${briefSourceLine(wires.sources)}
    ${(d.degraded_sources || []).length
      ? `<p class="caveat">Degraded on this build: ${esc((d.degraded_sources || []).join(', '))}.</p>`
      : ''}
  </div>`;

  const box = document.getElementById('read-q');
  if (box) {
    let timer = null;
    box.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => runReadSearch(box.value), 220);
    });
    box.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); clearTimeout(timer); runReadSearch(box.value); }
      if (ev.key === 'Escape') { box.value = ''; runReadSearch(''); }
    });
  }
}

async function loadBrief(force, opts = {}) {
  const silent = !!opts.silent;
  const day = opts.day || null;
  // A day switch has to refetch even when today's brief is already in STATE.
  if (STATE.brief && !force && !day && STATE.briefDay === null) {
    renderBrief(STATE.brief); revealPanels(views.brief); loadSentiment(); loadWeekly(); loadCatalystMode(); loadCatalysts(); loadPriority(); loadGlobal(); return;
  }
  if (!silent) {
    views.brief.innerHTML = loadingHTML(day
      ? `Optic’s Read for ${day}`
      : 'today’s Read. Market moves, the release calendar and the wires');
  }
  try {
    const qs = day ? `?day=${encodeURIComponent(day)}` : '';
    const data = await getJSON(`/api/brief${qs}`);
    STATE.brief = data;
    STATE.briefDay = day;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderBrief(data);
    // Not awaited: one extra request each, and the tab is already usable.
    loadSentiment();
    loadWeekly();
    loadCatalystMode();
    loadCatalysts();
    loadPriority();
    loadGlobal();
    if (!silent) revealPanels(views.brief);
    updateStatus();
  } catch (err) {
    if (!silent) { endLoad(views.brief); views.brief.innerHTML = errorHTML(err.message); }
    else console.warn('Silent brief refresh failed:', err.message);
  }
}


/* ------------------------------------------------------------- scanners

   Named scans over the ranking the screener already built. The expensive work —
   downloading and scoring ~3,000 symbols — happens in the background on its own
   schedule, so switching scans here is a filter and a sort over rows that
   already exist, and is meant to feel instant.

   Every scan renders its own blind spot next to its results. That is not a
   disclaimer bolted on: a breakout scan finds the *shape* of a breakout and
   cannot tell a real one from a failed one, and a reader who does not know that
   is reading the table as a list of tips. */

function scanCell(kind, value) {
  if (value === null || value === undefined) return '—';
  if (kind === 'pct') return `<span class="${signClass(value)}">${value > 0 ? '+' : ''}${fmt(value, 1)}%</span>`;
  if (kind === 'pct_plain') return `${fmt(value, 2)}%`;
  if (kind === 'mult') return `${fmt(value, 2)}×`;
  if (kind === 'ratio') return `${fmt(value * 100, 0)}%`;
  if (kind === 'score') return `<span class="${signClass(value)}">${fmt(value, 0)}</span>`;
  // Dollar volume runs to hundreds of millions; the plain formatter would print
  // nine digits into a table column.
  if (kind === 'usd') return `$${fmtCompact(value)}`;
  return fmt(value, 2);
}

function renderScan(cat, res) {
  /* Two levels, because thirteen scans in one row is a menu nobody reads: group
   * cards for the question, then pills for the specific scan inside it. The
   * active group is derived from the active scan rather than tracked separately —
   * one source of truth means the two rows cannot disagree about where you are. */
  const groups = STATE.scanGroups || [];
  const activeGroup = groups.find((g) => (g.scans || []).some((x) => x.id === STATE.scanId))
    || groups[0];

  const groupCards = groups.map((g) => `
    <button type="button" class="scan-group${g.id === (activeGroup || {}).id ? ' on' : ''}"
      data-scan-group="${esc(g.id)}">
      <span class="sg-name">${esc(g.name)}</span>
      <span class="sg-count">${fmt(g.count, 0)}</span>
      <span class="sg-blurb">${esc(g.blurb)}</span>
    </button>`).join('');

  const members = (activeGroup || {}).scans || (cat.scans || []);
  const tabs = members.map((sc) => `
    <button type="button" class="scan-pill${sc.id === STATE.scanId ? ' on' : ''}"
      data-scan="${esc(sc.id)}" title="${esc(sc.looks_for || '')}">${esc(sc.name)}</button>`).join('');

  const head = `<div class="panel span-all">
    <h2>${hg('Scanners')}</h2>
    <p class="sub">Named scans over the ${cat.considered ? fmt(cat.considered, 0) : ''} names that
      cleared the screen's gates, out of a ${cat.universe_size ? fmt(cat.universe_size, 0) : ''}-symbol
      universe. Pick a question; the answer is already computed.</p>
    ${groupCards ? `<div class="scan-groups">${groupCards}</div>` : ''}
    <div class="scan-pills">${tabs}</div>
    ${STATE.scanGroupNote ? `<p class="caveat">${gloss(STATE.scanGroupNote)}</p>` : ''}
  </div>`;

  if (res === 'loading') {
    return head + `<div class="panel span-all"><p class="sub">Running the scan…</p></div>`;
  }
  if (!res || !res.available) {
    return head + `<div class="panel span-all"><div class="callout">${
  esc((res && res.reason) || 'This scan is unavailable.')}</div></div>`;
  }

  const cols = res.columns || [];
  const rows = (res.rows || []).map((r) => `<tr>
    <td class="name"><button type="button" class="tkr" data-analyse="${esc(r.symbol)}"
      >${esc(r.symbol)}</button></td>
    <td class="num">${fmt(r.price, 2)}</td>
    ${cols.map((c) => `<td class="num">${scanCell(c.kind, r[c.key])}</td>`).join('')}
  </tr>`).join('');

  return head + `<div class="panel span-all">
    <h2>${esc(res.name)}</h2>
    <p class="sub">${esc(res.looks_for)}</p>
    ${res.stale ? `<div class="callout warn">The ranking behind this is
      ${fmt(res.age_hours, 0)} hours old, so these are yesterday's positions rather than
      today's. A scan is a claim about now.</div>` : ''}
    <p class="note" style="color:var(--ink-muted);margin:0 0 var(--space-2)">
      ${fmt(res.matched, 0)} matched${res.matched > res.shown
    ? `, showing the first ${fmt(res.shown, 0)}` : ''}${res.age_hours !== null
    ? ` · ranking ${fmt(res.age_hours, 1)}h old` : ''}</p>
    ${rows ? `<table class="data">
      <thead><tr><th>Symbol</th><th class="num">Price</th>${
  cols.map((c) => `<th class="num">${esc(c.label)}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody>
    </table>` : `<div class="callout">Nothing currently matches this scan. That is a
      result, not a failure. These conditions are meant to be selective.</div>`}
    <div class="callout scan-blind"><strong>What this scan cannot see.</strong>
      ${esc(res.blind_spot)}</div>
    <p class="caveat">${gloss(res.method || '')}</p>
  </div>
  <div id="eval-host" class="span-all">${
  STATE.evaluation ? renderEvaluation(STATE.evaluation) : ''}</div>`;
}

async function loadScan(force) {
  if (!STATE.scan || force) {
    views.scan.innerHTML = loadingHTML('the scanner catalogue');
    try {
      STATE.scan = await getJSON('/api/scanners');
      // Groups are a separate, cheap read; a failure here degrades to the flat
      // list rather than taking the whole tab down.
      try {
        const g = await getJSON('/api/scanners/groups');
        STATE.scanGroups = g.groups || [];
        STATE.scanGroupNote = g.note || '';
      } catch (e) { STATE.scanGroups = []; }
    } catch (err) {
      views.scan.innerHTML = errorHTML(err.message);
      return;
    }
  }
  await runScan(STATE.scanId);
}

async function runScan(id) {
  STATE.scanId = id;
  const cat = STATE.scan || { scans: [] };
  // Paint the pills immediately so the click registers, then fill the results.
  views.scan.innerHTML = renderScan(cat, 'loading');
  bindScanPills();
  try {
    const res = await getJSON(`/api/scanners/${encodeURIComponent(id)}`);
    if (STATE.scanId !== id) return;          // a faster click won
    views.scan.innerHTML = renderScan(cat, res);
  } catch (err) {
    views.scan.innerHTML = renderScan(cat, { available: false, reason: err.message });
  }
  bindScanPills();
  revealPanels(views.scan);
  loadEvaluation();
}

function bindScanPills() {
  views.scan.querySelectorAll('[data-scan-group]').forEach((b) => {
    b.addEventListener('click', () => {
      const g = (STATE.scanGroups || []).find((x) => x.id === b.dataset.scanGroup);
      // Land on the group's first scan — a group is a way in, not a destination.
      if (g && (g.scans || []).length) runScan(g.scans[0].id);
    });
  });
  views.scan.querySelectorAll('[data-scan]').forEach((b) => {
    b.addEventListener('click', () => runScan(b.getAttribute('data-scan')));
  });
}


/* Intraday bars, fetched only when a reader actually picks 1D or 5D.
 *
 * Not part of /api/ticker: that payload is daily bars and everything built on
 * them, and most readers never touch these pills. Fetching intraday on every
 * ticker load would be a request per view for data usually nobody looks at. */
async function loadIntraday(range) {
  const ticker = STATE.ticker;
  if (!ticker) return;
  const cached = STATE.intraday;
  if (cached && cached.ticker === ticker && cached.range === range) {
    if (STATE.swing) renderSwing(STATE.swing);
    return;
  }
  STATE.intraday = { ticker, range, loading: true };
  if (STATE.swing) renderSwing(STATE.swing);
  try {
    const data = await getJSON(`/api/intraday/${encodeURIComponent(ticker)}?range=${encodeURIComponent(range)}`);
    data.ticker = ticker;
    data.range = range;
    // The reader may have switched ticker or timeframe while this was in flight.
    if (STATE.ticker !== ticker || chartRange !== range) return;
    STATE.intraday = data;
  } catch (err) {
    STATE.intraday = { ticker, range, available: false, reason: err.message };
  }
  if (STATE.swing) renderSwing(STATE.swing);
}

async function loadSentiment() {
  if (STATE.sentiment) return;
  try {
    STATE.sentiment = await getJSON('/api/sentiment');
    mountPanel('sentiment-host', renderSentiment(STATE.sentiment));
  } catch (err) {
    console.warn('Sentiment unavailable:', err.message);
  }
}

async function loadIndexBoard() {
  if (STATE.indexBoard) return;
  try {
    STATE.indexBoard = await getJSON('/api/indices/board');
    if (STATE.indices) renderIndices(STATE.indices);
  } catch (err) {
    console.warn('Index board unavailable:', err.message);
  }
}

async function loadSectorBoard() {
  if (STATE.sectorBoard) return;
  try {
    STATE.sectorBoard = await getJSON('/api/sectors/board');
    if (STATE.market) renderMarket(STATE.market);
  } catch (err) {
    console.warn('Sector board unavailable:', err.message);
  }
}

/* The risk score, decomposed.
 *
 * This panel used to end after a two-line summary while the breadth panel beside
 * it ran three times taller, leaving a void down the left of the tab. The fix is
 * not to pad it: the score is built from twelve weighted terms that the payload
 * already carried and the panel discarded, so the honest filler is the arithmetic
 * itself.
 *
 * A diverging bar per term, because the useful reading is which way each one
 * pushes and how hard — a column of signed numbers makes the reader do that. Zero
 * contributors are kept rather than filtered: "crude is inside its band so it adds
 * nothing" is a fact about the regime, and dropping it would leave the reader
 * wondering whether crude was considered at all.
 */
function macroFactors(m) {
  const rows = (m.factors || []).filter((f) => f.contribution !== null
    && f.contribution !== undefined);
  if (!rows.length) return '';
  const sorted = [...rows].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  const peak = Math.max(...sorted.map((f) => Math.abs(f.contribution)), 1);
  const unattributed = m.score_unattributed;

  return `<h3>${hg('What makes up this score')}</h3>
    <p class="caveat" style="margin-top:0">Each term is the weight this model puts on
      one market, times how far it has moved. Sorted by how much it is actually
      moving the number.</p>
    <div class="mf-list">
      ${sorted.map((f) => {
    const v = f.contribution;
    const pct = (Math.abs(v) / peak) * 50;
    return `<div class="mf-row" title="${esc(f.rule || '')}">
        <span class="mf-name">${esc(f.factor)}
          <span class="mf-rule">${esc(f.rule || '')}</span></span>
        <span class="mf-bar">
          <span class="mf-neg">${v < 0
      ? `<i style="width:${pct.toFixed(1)}%"></i>` : ''}</span>
          <span class="mf-axis"></span>
          <span class="mf-pos">${v > 0
      ? `<i style="width:${pct.toFixed(1)}%"></i>` : ''}</span>
        </span>
        <span class="mf-val ${v === 0 ? 'zero' : signClass(v)}">${
  v > 0 ? '+' : ''}${fmt(v, 1)}</span>
      </div>`;
  }).join('')}
    </div>
    <div class="mf-total">
      <span>${sorted.length} terms</span>
      <span class="mf-sum ${signClass(m.risk_score)}">${m.risk_score > 0 ? '+' : ''}${
  fmt(m.risk_score, 1)}</span>
    </div>
    ${unattributed ? `<div class="callout">${fmt(unattributed, 1)} points of the score are
      not explained by the terms above. That means either the score hit its own
      &plusmn;100 bound, or a rule was added without recording its contribution. The
      decomposition is supposed to add up to the number it decomposes.</div>` : ''}`;
}

async function loadMarket(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.market && STATE.market.sectors && !force) {
    renderMarket(STATE.market); revealPanels(views.market); loadSectorBoard(); loadCorrelation(); return;
  }
  if (!silent) beginLoad(views.market, 'macro and sector data (this pulls ~40 symbols)');
  try {
    const data = await getJSON('/api/market');
    STATE.market = data;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderMarket(data);
    // Not awaited: one extra request each, and the rest of the tab should not wait.
    loadSectorBoard();
    loadCorrelation();
    loadRotation();
    loadForex();
    loadStockMap();
    loadEcon();
    endLoad(views.market);
    if (!silent) revealPanels(views.market);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) {
      endLoad(views.market);
      views.market.innerHTML = errorHTML(err.message,
        { originUnreachable: err.originUnreachable });
    }
    else console.warn('Silent market refresh failed:', err.message);
  }
}

async function loadLong(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.long && STATE.long.ticker === STATE.ticker && !force) { renderLong(STATE.long); revealPanels(views.long); return; }
  if (!silent) beginLoad(views.long, `10-year history for ${STATE.ticker} and the major indices`);
  try {
    const data = await getJSON(`/api/longterm/${encodeURIComponent(STATE.ticker)}?indices=false`);
    data.ticker = STATE.ticker;
    STATE.long = data;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderLong(data);
    endLoad(views.long);
    if (!silent) revealPanels(views.long);
    loadPeHistory();
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) { endLoad(views.long); views.long.innerHTML = errorHTML(err.message); }
    else console.warn('Silent long-term refresh failed:', err.message);
  }
}


async function loadRoth(force, opts = {}) {
  const silent = !!opts.silent;
  if (STATE.roth && !force) { renderRoth(STATE.roth); revealPanels(rothHost() || document.body); return; }
  if (!silent) (rothHost() || {}).innerHTML = loadingHTML('ten years of history for the fund universe');
  try {
    // POST, not GET: a portfolio has no business in a URL, browser history or an
    // access log, and the holdings text is arbitrary length.
    const data = await postJSON('/api/retirement', STATE.rothInputs);
    STATE.roth = data;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderRoth(data);
    if (!silent) revealPanels(rothHost() || document.body);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) (rothHost() || {}).innerHTML = errorHTML(err.message);
    else console.warn('Silent Roth refresh failed:', err.message);
  }
}

/** Query string for the ledger: which book, and which month to detail. */
function trackerQuery() {
  const qs = new URLSearchParams({ book: STATE.trackerBook || 'balanced' });
  if (STATE.trackerMonth) qs.set('month', STATE.trackerMonth);
  return qs.toString();
}

async function loadTracker(force, opts = {}) {
  const silent = !!opts.silent;
  // Shared ledger, so nothing about the loaded ticker invalidates it.
  if (STATE.tracker && !force) {
    renderTracker(STATE.tracker); revealPanels(views.tracker);
    loadPortfolioRisk(); loadRoth(); return;
  }
  if (!silent) beginLoad(views.tracker, "Optic's own position ledger");
  try {
    const data = await getJSON(`/api/tracker?${trackerQuery()}`);
    STATE.tracker = data;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderTracker(data);
    // Not awaited: one more request each, and the ledger is already usable.
    loadPortfolioRisk();
    loadRoth();
    endLoad(views.tracker);
    if (!silent) revealPanels(views.tracker);
    // A scheduled scan may already be running; show its progress live.
    if ((data.progress || {}).running) startTrackerPoll();
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) { endLoad(views.tracker); views.tracker.innerHTML = errorHTML(err.message); }
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
      const data = await getJSON(`/api/tracker?${trackerQuery()}`);
      const wasRunning = !!((STATE.tracker || {}).progress || {}).running;
      STATE.tracker = data;
      // A poll is a background refresh: never animate — unless a chart from the
      // foreground load is still waiting to be scrolled to, in which case the
      // replacement inherits the wait rather than cancelling it.
      setChartLive(isTapeLiveET());
      setChartAnimation(hasPendingDraws());
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
  if (STATE.indices && !force) {
    renderIndices(STATE.indices); revealPanels(views.indices); loadIndexBoard(); return;
  }
  if (!silent) beginLoad(views.indices, 'index history (this pulls 10 years per index)');
  try {
    const data = await getJSON('/api/indices');
    STATE.indices = data;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderIndices(data);
    // Not awaited: one extra request, and the tab is already usable.
    loadIndexBoard();
    endLoad(views.indices);
    if (!silent) revealPanels(views.indices);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) { endLoad(views.indices); views.indices.innerHTML = errorHTML(err.message); }
    else console.warn('Silent indices refresh failed:', err.message);
  }
}

async function loadEarnings(force, opts = {}) {
  const silent = !!opts.silent;
  if (!STATE.ticker) {
    // Nothing to analyse yet — show the week and stop, rather than requesting a
    // per-ticker payload for a ticker that does not exist.
    renderEarnings({});
    revealPanels(views.earnings);
    loadEarningsWeek();
    return;
  }
  if (STATE.earnings && STATE.earnings.ticker === STATE.ticker && !force) {
    renderEarnings(STATE.earnings); revealPanels(views.earnings);
    loadEarningsBrief(STATE.ticker); return;
  }
  if (!silent) beginLoad(views.earnings, `earnings data for ${STATE.ticker}`);
  try {
    const data = await getJSON(`/api/earnings/${encodeURIComponent(STATE.ticker)}`);
    data.ticker = STATE.ticker;
    STATE.earnings = data;
    setChartLive(isTapeLiveET());
    setChartAnimation(!silent || hasPendingDraws());
    renderEarnings(data);
    endLoad(views.earnings);
    if (!silent) revealPanels(views.earnings);
    // Not awaited: the panel is already usable and this can take seconds.
    loadEarningsBrief(STATE.ticker);
    updateStatus();
    updateChatContext();
  } catch (err) {
    if (!silent) { endLoad(views.earnings); views.earnings.innerHTML = errorHTML(err.message); }
    else console.warn('Silent earnings refresh failed:', err.message);
  }
}

function loadView(view, force) {
  if (view === 'home') return renderHome();
  // Market-wide views work with no ticker loaded. Earnings is now in this list
  // too: without a symbol it shows the week's calendar rather than a dead end, so
  // it must be allowed to reach its own loader instead of being intercepted here.
  // The remaining ticker-specific views send the reader back to pick one rather
  // than firing a request at /api/ticker/null.
  if (!['market', 'indices', 'roth', 'tracker', 'settings', 'brief', 'scan',
    'earnings', 'compare', 'instrument', 'chart'].includes(view) && !STATE.ticker) {
    views[view].innerHTML = `<div class="panel"><h2>No ticker loaded</h2>
      <p class="sub">Enter a symbol in the top bar, or pick one on the
      <button class="btn" type="button" data-goto-home style="padding:var(--space-0) var(--space-2);font-size:var(--t-small)">Home</button> page.</p></div>`;
    return;
  }
  // The workspace tracks its own symbol, so it neither needs STATE.ticker nor
  // follows it. With nothing chosen it shows its own picker rather than the
  // generic "no ticker loaded" dead end.
  if (view === 'chart') return loadChartWorkspace(STATE.chartSymbol, force);
  if (view === 'swing') return loadSwing(force);
  if (view === 'earnings') return loadEarnings(force);
  if (view === 'compare') return loadCompare(force);
  if (view === 'instrument') return loadInstrument(force);
  if (view === 'scan') return loadScan(force);
  if (view === 'market') return loadMarket(force);
  if (view === 'indices') return loadIndices(force);
  if (view === 'tracker') return loadTracker(force);
  if (view === 'brief') return loadBrief(force);
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
const TICKER_VIEWS = ['swing', 'earnings', 'long'];

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
      ${prof.kind_label ? `<span class="chip neutral" style="padding:0 var(--space-2);font-size:var(--t-micro)"><span class="dot"></span>${esc(prof.kind_label)}</span>` : ''}
      ${meta ? `<span class="ses-co-meta">${meta}</span>` : ''}
      ${prof.website ? `<a class="ses-co-link" href="${esc(prof.website)}" target="_blank"
        rel="noopener noreferrer">Site</a>` : ''}
    </div>
    ${prof.summary ? `<p class="ses-co-sum" id="ses-summary">${esc(prof.summary)}</p>
      <button type="button" class="ses-co-more" id="ses-more">More</button>` : `
      <p class="ses-co-sum expanded muted">No business description in the
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
    ? `Times in ${esc(zoneTag)}. Market time`
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
        ? `${esc(STATE.ticker)} is loaded. Pick a tab above, or search another symbol.`
        : 'Search a ticker or company name to begin.',
      liveIndicatorHTML(),
    ]);
    return;
  }
  // 'settings' belongs here too: it has no symbol of its own, so it shouldn't be
  // nagging for one. Nor should 'compare', which takes its symbols from its own
  // inputs, or 'earnings', which shows the week's calendar with nothing loaded.
  // The chart workspace has its own symbol, so it reports that rather than
  // nagging about STATE.ticker — which it does not use and does not follow.
  if (STATE.view === 'chart') {
    /* The gesture hint belongs here, not in the legend.
     *
     * It was a legend row, and then the legend was collapsed by default to give
     * the plot back 70px — which hid the one line explaining that the chart
     * zooms, pans and measures. A hint nobody sees is worse than no hint,
     * because it looks like the gestures do not exist.
     *
     * This strip is always on screen and already spent, so the line costs no
     * chart height. It also reports the zoom, so a window that no longer
     * matches the range pill says so rather than looking like a broken pill. */
    setStatus(STATE.chartSymbol
      ? [`Chart: ${STATE.chartSymbol}`,
        wsWindow ? `${chartInterval} · zoomed` : `${chartInterval} · ${chartRange}`,
        `${wsDrawings().length} drawing${wsDrawings().length === 1 ? '' : 's'}`,
        'Scroll zooms, drag the strip below to move, drag the chart to measure']
      : ['Chart. Pick a symbol to begin.']);
    return;
  }
  if (!STATE.ticker
      && !['market', 'indices', 'roth', 'tracker', 'settings', 'brief',
        'compare', 'earnings', 'instrument'].includes(STATE.view)) {
    setStatus(['No ticker loaded. Enter a symbol to begin.']);
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
        ? `${esc(STATE.ticker)}${busy ? '. Loading…' : ''}`
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
  const tickerViews = ['swing', 'earnings', 'long'];
  const label = d.ticker || holding.ticker
    || (tickerViews.includes(STATE.view) ? STATE.ticker : null);
  const price = quote.price !== undefined && quote.price !== null
    ? quote.price : (holding.price !== undefined ? holding.price : d.spot);
  if (label) {
    parts.push(`<strong class="dim">${esc(label)}</strong>${
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
  if (STATE.view === 'brief') {
    const degraded = (d.degraded_sources || []).length;
    parts.push(`Read for ${esc(d.day || '')}`);
    const stories = ((d.wires || {}).desks || [])
      .reduce((n, k) => n + (k.entries || []).length, 0);
    parts.push(`${stories} stor${stories === 1 ? 'y' : 'ies'} · ${
      ((d.macro || {}).entries || []).length} releases · ${
      ((d.calendar || {}).events || []).length} scheduled`);
    if (degraded) parts.push(`${degraded} source${degraded === 1 ? '' : 's'} degraded`);
  }
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

/* Which session is running, in Eastern time.
 *
 * Three states, not two. The old boolean was "regular hours or nothing", which
 * meant the whole terminal treated 16:01 exactly like 03:00 on a Sunday — the
 * price froze at the close and the refresh stopped, even though the tape is still
 * moving and the quote still changes. Extended-hours volume is thin, but a stale
 * close presented as the current price is wrong in a way thin volume is not.
 *
 * Windows are the standard US equity sessions: pre-market 04:00-09:30,
 * regular 09:30-16:00, after-hours 16:00-20:00.
 */
function marketSessionET() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', hour12: false,
    weekday: 'short', hour: '2-digit', minute: '2-digit',
  }).formatToParts(new Date());
  const map = {};
  parts.forEach((p) => { map[p.type] = p.value; });
  if (map.weekday === 'Sat' || map.weekday === 'Sun') return 'closed';
  const mins = parseInt(map.hour, 10) * 60 + parseInt(map.minute, 10);
  if (mins >= 9 * 60 + 30 && mins < 16 * 60) return 'regular';
  if (mins >= 4 * 60 && mins < 9 * 60 + 30) return 'pre';
  if (mins >= 16 * 60 && mins < 20 * 60) return 'after';
  return 'closed';
}

function isMarketOpenET() {
  return marketSessionET() === 'regular';
}

/* Whether prices are still moving at all — the question the refresh and the
 * chart's live dot should actually be asking. `isMarketOpenET` answers a
 * narrower one and is kept for the places that genuinely mean regular hours,
 * like whether the paper book may take an entry. */
function isTapeLiveET() {
  return marketSessionET() !== 'closed';
}

const SESSION_LABEL = {
  regular: 'Live · refreshing every 20s',
  pre: 'Pre-market · refreshing every 20s',
  after: 'After hours · refreshing every 20s',
};

function liveIndicatorHTML() {
  const session = marketSessionET();
  if (session === 'closed') {
    return '<span class="chip neutral"><span class="dot"></span>Market closed · auto-refresh paused</span>';
  }
  // Extended hours get the same pulse but their own label, so "live" never
  // implies regular-session liquidity.
  const tone = session === 'regular' ? 'bull' : 'neutral';
  return `<span class="chip ${tone}"><span class="dot" style="animation:pulse-beat 1.8s ease-in-out infinite"></span>${SESSION_LABEL[session]}</span>`;
}

function tickAutoRefresh() {
  updateStatus(); // keep the live/closed chip accurate even off the swing tab
  if (document.hidden || !isTapeLiveET()) return;
  if (STATE.view === 'swing' && STATE.swing) loadSwing(true, { silent: true });
  else if (STATE.view === 'market' && STATE.market) loadMarket(true, { silent: true });
  // Long-term view is deliberately excluded — multi-year context doesn't
  // change intraday, so there's nothing there worth re-fetching every 20s.
}


function startAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(tickAutoRefresh, REFRESH_INTERVAL_MS);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    tickAutoRefresh(); // catch up immediately on return
  });
}

/* ===================================================================== CHAT */

const chatState = {
  messages: [],
  busy: false,
  // Identifies the live conversation in the saved list, so re-saving updates it
  // in place instead of appending a near-duplicate after every exchange.
  conversationId: 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
};

/* ------------------------------------------------------ Pulse conversations
 *
 * Kept in this browser's localStorage, never on the server, and that is a
 * deliberate decision rather than the lazy option.
 *
 * This terminal is deliberately unauthenticated — anyone with the URL can use it,
 * which is how it was asked to work. There is no account to attach a transcript
 * to, so a server-side history would be one shared log: every visitor would read
 * everyone else's questions and append to the same thread. For a tool people point
 * at their own positions, that is a privacy leak dressed as a feature.
 *
 * Two things are deliberately NOT stored.
 *
 * Attachments. Image and PDF payloads pass through to the API and are discarded,
 * which is the existing promise; writing their base64 into localStorage would
 * quietly break it and exhaust a 5MB quota in a couple of screenshots. The note
 * that a file was attached is kept, the file is not.
 *
 * Anything beyond the caps below. localStorage throws when full, and a chat that
 * silently stops saving is worse than one that visibly keeps the last thirty.
 */
const PULSE_STORE_KEY = 'optic.pulse.history.v1';
const PULSE_MAX_CONVERSATIONS = 30;
const PULSE_MAX_MESSAGES = 60;      // per conversation, oldest trimmed first
const PULSE_MAX_CHARS = 12000;      // per message, so one huge paste cannot fill the quota

function pulseLoadHistory() {
  try {
    const raw = localStorage.getItem(PULSE_STORE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    // Corrupt or unreadable: start clean rather than breaking the panel.
    return [];
  }
}

function pulseSaveHistory(list) {
  try {
    localStorage.setItem(PULSE_STORE_KEY, JSON.stringify(list));
    return true;
  } catch (e) {
    // Quota. Drop the oldest half and try once — losing old conversations is a
    // far better failure than silently never saving again.
    try {
      localStorage.setItem(PULSE_STORE_KEY,
        JSON.stringify(list.slice(0, Math.max(1, Math.floor(list.length / 2)))));
      return true;
    } catch (e2) {
      return false;
    }
  }
}

function pulseTitle(messages) {
  const first = (messages || []).find((m) => m.role === 'user');
  if (!first) return 'Empty conversation';
  return String(first.content || '').replace(/\s+/g, ' ').trim().slice(0, 70)
    || 'Empty conversation';
}

/* Persist the live conversation. Called after each exchange rather than on unload:
 * a beforeunload handler is not guaranteed to run, and losing the last answer is
 * exactly the one a reader wanted to keep. */
function pulsePersist() {
  if (!chatState.messages.length) return;
  const messages = chatState.messages
    .slice(-PULSE_MAX_MESSAGES)
    .map((m) => ({ role: m.role,
      content: String(m.content || '').slice(0, PULSE_MAX_CHARS) }));
  const list = pulseLoadHistory().filter((c) => c.id !== chatState.conversationId);
  list.unshift({
    id: chatState.conversationId,
    at: new Date().toISOString(),
    title: pulseTitle(messages),
    ticker: STATE.ticker || null,
    messages,
  });
  pulseSaveHistory(list.slice(0, PULSE_MAX_CONVERSATIONS));
}

function pulseNewConversation() {
  chatState.messages = [];
  chatState.conversationId = 'c' + Date.now().toString(36)
    + Math.random().toString(36).slice(2, 6);
  const log = $('#chat-log');
  if (log) log.innerHTML = '';
  renderPulseHistory(false);
}

function pulseResume(id) {
  const hit = pulseLoadHistory().find((c) => c.id === id);
  if (!hit) return;
  chatState.conversationId = hit.id;
  chatState.messages = (hit.messages || []).map((m) => ({ ...m }));
  const log = $('#chat-log');
  if (log) {
    log.innerHTML = '';
    chatState.messages.forEach((m) => addMsg(m.role === 'user' ? 'user' : 'bot', m.content));
    // A resumed conversation is history, so it opens where it left off rather
    // than at the top.
    log.scrollTop = log.scrollHeight;
  }
  renderPulseHistory(false);
}

function pulseDelete(id) {
  pulseSaveHistory(pulseLoadHistory().filter((c) => c.id !== id));
  if (chatState.conversationId === id) pulseNewConversation();
  else renderPulseHistory(true);
}

let pulseHistoryOpen = false;

function renderPulseHistory(open) {
  if (open !== undefined) pulseHistoryOpen = open;
  const host = document.getElementById('pulse-history');
  if (!host) return;
  // Set here rather than in the click handler: the drawer also closes itself when
  // a conversation is resumed, and a toggle that reports expanded while collapsed
  // is wrong for anyone reading the button through a screen reader.
  const toggle = document.getElementById('chat-history-btn');
  if (toggle) toggle.setAttribute('aria-expanded', String(pulseHistoryOpen));
  if (!pulseHistoryOpen) { host.hidden = true; host.innerHTML = ''; return; }
  const list = pulseLoadHistory();
  host.hidden = false;
  host.innerHTML = `
    <div class="ph-head">
      <span>${list.length} saved conversation${list.length === 1 ? '' : 's'}</span>
      <button type="button" class="bulk-btn" data-pulse-new>New</button>
    </div>
    ${list.length ? `<div class="ph-list">${list.map((c) => `
      <div class="ph-item${c.id === chatState.conversationId ? ' on' : ''}">
        <button type="button" class="ph-open" data-pulse-open="${esc(c.id)}">
          <span class="ph-title">${esc(c.title)}</span>
          <span class="ph-meta">${esc((c.at || '').slice(0, 16).replace('T', ' '))}
            · ${fmt((c.messages || []).length, 0)} messages${
  c.ticker ? ' · ' + esc(c.ticker) : ''}</span>
        </button>
        <button type="button" class="ph-del" data-pulse-del="${esc(c.id)}"
          title="Delete this conversation" aria-label="Delete">&times;</button>
      </div>`).join('')}</div>`
    : '<p class="sub" style="padding:var(--space-2) var(--space-0)">Nothing saved yet.</p>'}
    <p class="caveat">Stored in this browser only, never uploaded, and not visible
      to anyone else using this link. Attachments are not saved: the file itself was
      never kept, only the note that one was sent. The last
      ${fmt(PULSE_MAX_CONVERSATIONS, 0)} conversations are retained.</p>`;
}

function chatContextPayload() {
  /* Everything the browser has loaded, regardless of which tab is on screen.
   *
   * The active view decides what *you* are looking at; it should never decide what
   * Pulse is allowed to know. Earnings was missing entirely here — the context
   * summary line claimed to include it, so the UI said "earnings" while the model
   * received nothing of the sort and had to answer earnings questions blind. */
  const ctx = {};
  {
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
  if (STATE.market) {
    ctx.macro = STATE.market.macro;
    ctx.sectors = STATE.market.sectors;
  }
  if (STATE.earnings) ctx.earnings = STATE.earnings;
  if (STATE.indices) ctx.indices = STATE.indices;
  if (STATE.brief) {
    // The daily brief, minus the per-story lists — headlines alone would swamp
    // the analysis the question is usually about.
    ctx.read = {
      day: STATE.brief.day,
      summary: STATE.brief.summary,
      overview: STATE.brief.overview,
      calendar: STATE.brief.calendar,
    };
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
  // The starter cards name the loaded symbol, so they go stale when it changes.
  renderPulseEmpty();
  const bits = [];
  if (STATE.swing) bits.push(STATE.swing.ticker + ' options');
  if (STATE.earnings) bits.push('earnings');
  if (STATE.market && STATE.market.sectors) bits.push('macro+sectors');
  if (STATE.indices) bits.push('indices');
  if (STATE.roth) bits.push('roth model');
  if (STATE.long) bits.push('long-term');
  if (STATE.tracker) bits.push('tracker');
  const chip = $('#chat-ctx');
  chip.className = 'chip ' + (bits.length ? 'bull' : 'neutral');
  chip.innerHTML = `<span class="dot"></span><span>${bits.length ? esc(cap(bits.join(' · '))) : 'No context'}</span>`;

  /* The chip row above the input is now only for follow-ups on a loaded
   * symbol. The empty-state starter cards cover the "what can I ask" job
   * properly, and the chip row's version of it was a single dead line reading
   * "Load a ticker first" — which is the state a reader is already in. */
  const suggestions = STATE.swing ? [
    'Why did the ranker pick that strike over a cheaper OTM one?',
    'What does the gamma profile imply for a swing long here?',
    'Is the flow confirming or fighting the chart?',
    'Walk me through the entry zone and what invalidates it.',
    'Does the short interest or insider activity change the read?',
    'How does the earnings record affect holding through the print?',
  ] : [];
  $('#chat-suggest').innerHTML = suggestions
    .map((q) => `<button type="button" data-q="${esc(q)}">${esc(q.length > 46 ? q.slice(0, 44) + '…' : q)}</button>`)
    .join('');
}

/* ------------------------------------------------- Pulse: persona and starters
 *
 * Two additions. A persona picker, which changes the lens and never the numbers
 * — every persona works from the same CONTEXT and is instructed to cite the same
 * figures. And an empty state with starter prompts, because "Load a ticker
 * first, then ask about its analysis" was the entire empty state and it is a
 * dead end.
 *
 * The starters are constrained to what this terminal can actually do. The
 * reference product offers "alert me if NVDA moves 3%" and "send me an email
 * every morning" — Pulse has neither, and a starter card that fails is worse
 * than one fewer card.
 */
const PULSE_PERSONA_KEY = 'optic.pulse.persona.v1';
let pulsePersona = 'neutral';
try {
  const saved = localStorage.getItem(PULSE_PERSONA_KEY);
  if (saved) pulsePersona = saved;
} catch (e) { /* private mode */ }

let PULSE_PERSONAS = [
  { id: 'neutral', label: 'Neutral analyst', blurb: 'Balanced, cites the numbers.' },
];

async function loadPersonas() {
  try {
    const d = await getJSON('/api/personas');
    if (Array.isArray(d.personas) && d.personas.length) PULSE_PERSONAS = d.personas;
    if (!PULSE_PERSONAS.some((p) => p.id === pulsePersona)) pulsePersona = d.default;
  } catch (e) { /* keep the built-in default */ }
  renderPersonaPicker();
}

function renderPersonaPicker() {
  const host = document.getElementById('chat-persona');
  if (!host) return;
  const current = PULSE_PERSONAS.find((p) => p.id === pulsePersona) || PULSE_PERSONAS[0];
  host.innerHTML = `<label class="pulse-persona-lab" for="pulse-persona">Lens</label>
    <select id="pulse-persona" class="settings-select" aria-label="Response lens">
      ${PULSE_PERSONAS.map((p) => `<option value="${esc(p.id)}"${
  p.id === pulsePersona ? ' selected' : ''}>${esc(p.label)}</option>`).join('')}
    </select>
    <span class="pulse-persona-blurb">${esc(current ? current.blurb : '')}</span>`;
}

/* The starter cards.
 *
 * Grouped so the list is scannable, and every one of them is answerable from
 * what the terminal computes. The ticker-specific ones only appear once a symbol
 * is loaded, because a card that needs data you have not got is a card that
 * produces a hedge instead of an answer.
 */
const PULSE_STARTERS = [
  { need: 'ticker', text: 'Walk me through the composite score on {T}. Which inputs are carrying it, and where do they disagree?' },
  { need: 'ticker', text: 'What is the strongest argument AGAINST the current setup on {T}?' },
  { need: 'ticker', text: 'Give me the bull and bear case for {T} over the next quarter, from the numbers on screen.' },
  { need: 'ticker', text: 'Is {T}’s seasonality real, or is the sample too small to say?' },
  { need: 'ticker', text: 'What does the dealer gamma profile imply if {T} breaks its nearest level?' },
  { need: 'ticker', text: 'How has {T} actually traded after its last eight earnings reports?' },
  { need: null, text: 'What is the macro regime saying right now, and which sectors is it favouring?' },
  { need: null, text: 'Which currency pairs are worth watching this week, and why?' },
  { need: null, text: 'Explain how this terminal computes dealer gamma, and what assumption it is making.' },
  { need: null, text: 'Summarise what happened in the market since the last close.' },
  { need: null, text: 'How is the paper-trading ledger actually doing, and is the sample big enough to mean anything?' },
  { need: null, text: 'Which chart patterns has this terminal measured as actually working, and at what hit rate?' },
];

function pulseStarters(expanded) {
  const sym = STATE.ticker || STATE.chartSymbol || '';
  const usable = PULSE_STARTERS.filter((c) => !c.need || sym);
  const shown = expanded ? usable : usable.slice(0, 4);
  return `<div class="pulse-empty">
    <h3>What would you like to look at?</h3>
    <p class="pulse-empty-sub">Pulse reads the terminal's own computed output for
      whatever is on screen${sym ? `· currently <strong>${esc(sym)}</strong>` : ''}.
      Ask anything, or start with one of these.</p>
    <div class="pulse-cards">
      ${shown.map((c, i) => {
    const text = c.text.replace(/\{T\}/g, sym || 'the symbol');
    return `<button type="button" class="pulse-card" data-q="${esc(text)}">
        <span class="pulse-card-n">${i + 1}</span>
        <span>${esc(text)}</span>
      </button>`;
  }).join('')}
    </div>
    ${usable.length > shown.length
    ? '<button type="button" class="pulse-more" data-pulse-more>see more examples</button>'
    : (expanded ? '<button type="button" class="pulse-more" data-pulse-less>show fewer</button>' : '')}
    ${sym ? '' : `<p class="pulse-empty-note">Load a ticker to unlock the
      symbol-specific prompts. Everything above works without one.</p>`}
  </div>`;
}

let pulseStartersExpanded = false;

/** Show or clear the empty state, depending on whether the log has messages. */
function renderPulseEmpty() {
  const log = document.getElementById('chat-log');
  if (!log) return;
  const hasMsgs = !!log.querySelector('.msg');
  const existing = log.querySelector('.pulse-empty');
  if (hasMsgs) { if (existing) existing.remove(); return; }
  log.innerHTML = pulseStarters(pulseStartersExpanded);
}

function mdLite(text) {
  let out = esc(text);
  out = out.replace(/```([\s\S]*?)```/g, (m, code) => `<pre style="background:var(--surface-2);padding:var(--space-2);border-radius:6px;overflow-x:auto;font-size:var(--t-caption)">${code}</pre>`);
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Single-asterisk italics, after bold so the ** pass has already consumed
  // its markers. Without this the model's emphasis rendered as literal
  // asterisks in the middle of a sentence.
  out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
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
  const wasPinned = isPinnedToBottom(log) || role === 'user';
  log.appendChild(wrap);
  followStream(log, wasPinned);
  return wrap;
}

/* Reveal a streamed reply the way a chat client should.
 *
 * Two rounds of this got it wrong in instructive ways. First version wrote every
 * network chunk straight to the DOM, so the model's uneven cadence — "Net", " G",
 * then a 90-character burst — became visible stutter. Second version paced the
 * reveal per animation frame, which fixed the rhythm but still assigned
 * `bubble.innerHTML` for the whole message on every frame: the entire subtree
 * rebuilt 60 times a second, with cost growing as the reply got longer. That is
 * the lag that survived.
 *
 * The shape that actually works splits the message in two. Text before the last
 * paragraph break is settled — it is parsed as markdown once and never touched
 * again. Only the trailing paragraph is rewritten per frame, and as a plain text
 * node, which is the cheapest DOM write there is. Per-frame cost becomes
 * proportional to the current paragraph instead of the whole answer, so a
 * 4,000-character reply streams exactly as smoothly as a 200-character one.
 */
/* Follow the stream only while the reader is already at the bottom.
 *
 * The log did `scrollTop = scrollHeight` on every SSE event, which meant every
 * delta - dozens a second - dragged the view back down. Scrolling up to re-read
 * the first paragraph while the answer was still arriving was impossible: the
 * next chunk yanked you to the end. That is the "laggy" behaviour; it was never
 * frame rate, which measured fine.
 *
 * So scroll position becomes a mode. Sitting at the bottom means "follow along"
 * and new text keeps the view pinned. Scrolling up means "I am reading" and the
 * stream is left to grow underneath until you come back down. This is how every
 * terminal pager and chat client behaves, and the tolerance exists because
 * fractional scroll heights make an exact equality test never true.
 */
const SCROLL_STICK_PX = 48;

function isPinnedToBottom(el) {
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_STICK_PX;
}

function followStream(el, wasPinned) {
  if (el && wasPinned) el.scrollTop = el.scrollHeight;
}

// Backlog past which the renderer stops pacing and simply catches up.
const CATCH_UP_CHARS = 220;

function createStreamRenderer(bubble) {
  bubble.textContent = '';
  const settledEl = document.createElement('div');
  const tailEl = document.createElement('span');
  bubble.append(settledEl, tailEl);

  let target = '';        // everything received
  let shown = 0;          // characters revealed
  let settledLen = 0;     // characters already committed as markdown
  let frame = null;

  // Reduced motion means no gratuitous animation: paint on arrival instead.
  const instant = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const paint = () => {
    const visible = target.slice(0, shown);
    const cut = visible.lastIndexOf('\n\n');
    if (cut + 2 > settledLen) {
      settledLen = cut + 2;
      settledEl.innerHTML = mdLite(target.slice(0, settledLen));
    }
    // Cheapest possible write for the part that changes every frame.
    tailEl.textContent = visible.slice(settledLen);
  };

  const tick = () => {
    const behind = target.length - shown;
    if (behind > 0) {
      /* Keep pace with the stream, then smooth what is left.
       *
       * A third of the buffer per frame still trailed a fast burst: the model can
       * deliver several hundred characters between two frames, and draining a
       * third of a growing backlog means the visible text runs permanently behind
       * the text already received. That gap is what reads as lag — not dropped
       * frames, which measured fine at 14ms.
       *
       * So above a threshold it stops rationing and shows everything it has; below
       * it, half the remainder per frame keeps short trickles smooth rather than
       * word-by-word. */
      const step = behind > CATCH_UP_CHARS ? behind : Math.max(4, Math.ceil(behind / 2));
      shown = Math.min(target.length, shown + step);
      paint();
    }
    if (shown >= target.length) { frame = null; return; }
    frame = requestAnimationFrame(tick);
  };

  return {
    push(text) {
      if (!text) return;
      target += text;
      if (instant) { shown = target.length; paint(); return; }
      if (frame === null) frame = requestAnimationFrame(tick);
    },
    /** Commit everything now, fully formatted. Used on done and on error. */
    flush() {
      shown = target.length;
      if (frame !== null) { cancelAnimationFrame(frame); frame = null; }
      settledLen = target.length;
      settledEl.innerHTML = mdLite(target);
      tailEl.textContent = '';
    },
    text() { return target; },
  };
}

async function streamTo(url, body, node) {
  const bubble = node.querySelector('.bubble');
  const statusEl = node.querySelector('.status');
  const sourcesEl = node.querySelector('.sources');
  const render = createStreamRenderer(bubble);
  let acc = '';

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    // Read the server's explanation rather than reporting a bare number. A 400
    // here means "you sent nothing to research", which is worth saying out loud.
    let detail = '';
    try { detail = ((await res.json()).detail || '').toString(); } catch (e) { /* not JSON */ }
    statusEl.textContent = '';
    if (!detail && res.status >= 502 && res.status <= 530) {
      // 502-530 come from Cloudflare, not this server: the quick tunnel that was
      // serving this page has been replaced, so the hostname in the address bar
      // no longer routes anywhere. The app is almost certainly running fine on a
      // new address — which is worth saying, because "HTTP 530" reads as the
      // assistant breaking rather than the link having expired.
      detail = `This link has expired (HTTP ${res.status}). The temporary tunnel serving `
        + 'this page was replaced. The terminal is still running on a new address; '
        + 'ask for the current link and reload.';
    }
    throw new Error(detail || `Request failed (HTTP ${res.status})`);
  }

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
      // Read the mode *before* this event lengthens the log, or the measurement is
      // taken against the new height and always looks scrolled-away.
      const logEl = $('#chat-log');
      const pinned = isPinnedToBottom(logEl);

      if (event === 'delta') {
        acc += payload.text || '';
        statusEl.textContent = '';
        render.push(payload.text || '');
      } else if (event === 'status') {
        statusEl.innerHTML = `<span class="spinner"></span>${esc(payload.state || '')}…`;
      } else if (event === 'error') {
        node.classList.add('err');
        statusEl.textContent = '';
        render.flush();
        bubble.innerHTML = mdLite(payload.message || 'Unknown error.');
      } else if (event === 'done') {
        statusEl.textContent = '';
        render.flush();
        const list = payload.sources || payload.citations || [];
        if (list.length) {
          sourcesEl.innerHTML = '<div style="color:var(--ink-muted);margin-bottom:var(--space-0)">Sources</div>'
            + list.map((sc) => `<a href="${esc(sc.url)}" target="_blank" rel="noopener">${esc(sc.title || sc.url)}</a>`).join('');
        }
      }
      followStream(logEl, pinned);
    }
  }
  // However the loop exited — normal end, aborted body, malformed tail — the
  // reader must not be left mid-reveal with text it already received.
  render.flush();
  return acc;
}

/* Staged chat attachments.
 *
 * Held in memory as base64 and sent with the next message, then dropped. Nothing
 * is uploaded ahead of time and nothing is stored server-side, so there is no
 * upload directory to secure and no orphaned files if the reader changes their
 * mind.
 *
 * Limits are checked here and again on the server. A browser-side check is a
 * courtesy that keeps the reader from waiting on a doomed request; it is not a
 * control, because anything can post to the endpoint directly.
 */
const ATTACH_OK_TYPES = new Set([
  'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf',
]);
const ATTACH_MAX_BYTES = 5 * 1024 * 1024;
const ATTACH_MAX_FILES = 4;

const attachState = [];

function fmtBytes(n) {
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + 'MB';
  if (n >= 1024) return Math.round(n / 1024) + 'KB';
  return n + 'B';
}

/* Staged attachments, shown as what they are.
 *
 * A filename is the least useful thing to show about a screenshot: the whole
 * point of attaching one is the picture, and "Screenshot 2026-08-14 at..." tells
 * you nothing about which screenshot you grabbed. The base64 is already in
 * memory for the send, so the thumbnail costs nothing extra — no second read, no
 * network, no disk.
 *
 * PDFs get a document tile rather than a render: drawing a first page needs a
 * PDF engine, and a wrong-looking page is worse than an honest icon. */
function renderAttachments() {
  const host = $('#chat-attachments');
  if (!host) return;
  host.innerHTML = attachState.map((a, i) => {
    const remove = `<button type="button" class="att-x" data-drop-attach="${i}"
      aria-label="Remove ${esc(a.name)}">×</button>`;
    if (a.error) {
      return `<span class="att-tile bad" title="${esc(a.name)}">
        <span class="att-meta"><span class="nm">${esc(a.name)}</span>
        <span class="sz">${esc(a.error)}</span></span>${remove}</span>`;
    }
    const isImage = (a.media_type || '').startsWith('image/');
    const body = (isImage && a.data)
      ? `<img class="att-thumb" src="data:${esc(a.media_type)};base64,${a.data}"
           alt="${esc(a.name)}">`
      : `<span class="att-doc" aria-hidden="true">PDF</span>`;
    return `<span class="att-tile${isImage ? ' img' : ''}" title="${esc(a.name)}">
      ${body}
      <span class="att-meta">
        <span class="nm">${esc(a.name)}</span>
        <span class="sz">${fmtBytes(a.size)}</span>
      </span>
      ${remove}
    </span>`;
  }).join('');
}

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    // readAsDataURL gives "data:<type>;base64,<payload>" — the API wants only the
    // payload, so the prefix is stripped rather than sent and rejected.
    fr.onload = () => {
      const out = String(fr.result || '');
      const comma = out.indexOf(',');
      resolve(comma >= 0 ? out.slice(comma + 1) : out);
    };
    fr.onerror = () => reject(new Error('could not be read'));
    fr.readAsDataURL(file);
  });
}

async function addAttachments(files) {
  for (const file of [...files]) {
    if (attachState.length >= ATTACH_MAX_FILES) {
      addMsg('assistant', `Only ${ATTACH_MAX_FILES} files can go with one message.`);
      break;
    }
    const entry = { name: file.name || 'attachment', size: file.size,
      media_type: file.type || '', data: null, error: null };
    if (!ATTACH_OK_TYPES.has(entry.media_type)) {
      entry.error = 'unsupported type';
    } else if (file.size > ATTACH_MAX_BYTES) {
      entry.error = `over ${ATTACH_MAX_BYTES / (1024 * 1024)}MB`;
    } else {
      try { entry.data = await readAsBase64(file); }
      catch (e) { entry.error = 'unreadable'; }
    }
    attachState.push(entry);
  }
  renderAttachments();
}

/** The payload for the next send: only files that actually read cleanly. */
function attachmentsPayload() {
  return attachState.filter((a) => a.data && !a.error)
    .map((a) => ({ name: a.name, media_type: a.media_type, data: a.data }));
}

function clearAttachments() {
  attachState.length = 0;
  renderAttachments();
}

function initAttachments() {
  const btn = $('#chat-attach');
  const input = $('#chat-file');
  if (btn && input) {
    btn.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
      await addAttachments(input.files || []);
      input.value = '';                 // so the same file can be picked again
    });
  }
  // Drag and drop onto the panel, which is how people actually move a screenshot.
  // The panel is <aside id="chat"> — there is no .chat-panel class, and querying
  // for one bound the listeners to nothing while looking like it had worked.
  const panel = $('#chat');
  if (panel) {
    ['dragenter', 'dragover'].forEach((ev) => panel.addEventListener(ev, (e) => {
      if (!(e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files'))) return;
      e.preventDefault();
      panel.classList.add('dropping');
    }));
    ['dragleave', 'drop'].forEach((ev) => panel.addEventListener(ev, () => {
      panel.classList.remove('dropping');
    }));
    panel.addEventListener('drop', async (e) => {
      const files = e.dataTransfer && e.dataTransfer.files;
      if (!files || !files.length) return;
      e.preventDefault();
      await addAttachments(files);
    });
  }
}

async function sendChat(text) {
  if (chatState.busy || !text.trim()) return;
  chatState.busy = true;
  $('#chat-send').disabled = true;
  $('#chat-research').disabled = true;

  const files = attachmentsPayload();
  // Name the files in the transcript. The bytes are not kept in chatState — only
  // this note — so scrolling back shows what was sent without re-uploading it on
  // every subsequent turn.
  const fileNote = files.length
    ? `\n\n[attached: ${files.map((f) => f.name).join(', ')}]` : '';
  addMsg('user', text + fileNote);
  chatState.messages.push({ role: 'user', content: text + fileNote });
  const node = addMsg('assistant', '');
  node.querySelector('.status').innerHTML = '<span class="spinner"></span>thinking…';

  try {
    const reply = await streamTo('/api/chat', {
      messages: chatState.messages,
      context: chatContextPayload(),
      web: $('#chat-web').checked,
      attachments: files,
      persona: pulsePersona,
    }, node);
    clearAttachments();
    if (reply) chatState.messages.push({ role: 'assistant', content: reply });
    pulsePersist();
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
  /* With an empty box and no ticker loaded, this used to post
   * {ticker: null, question: null} — which the server rejects with a 400 — while
   * still printing "Deep research: the market" as though a question had been
   * asked. The button looked broken because the request never contained the thing
   * the transcript said it did.
   *
   * So the fallback question is now written out explicitly and sent. Pressing
   * Deep research with nothing loaded is a reasonable thing to do: it means
   * "brief me on the market", and that is answerable. */
  const marketFallback = 'Give me a live sourced brief on the overall market right '
    + 'now: index direction, what is driving it, notable movers, and the macro '
    + 'releases or events traders are positioned around.';
  const question = custom || (STATE.ticker ? null : marketFallback);
  const label = custom || `Deep research: ${STATE.ticker || 'the market'}`;

  addMsg('user', label);
  $('#chat-input').value = '';
  const node = addMsg('assistant', '');
  node.querySelector('.status').innerHTML = '<span class="spinner"></span>searching…';

  try {
    await streamTo('/api/research', {
      ticker: STATE.ticker || null,
      question,
      context: chatContextPayload(),
    }, node);
  } catch (err) {
    node.classList.add('err');
    // Kill the spinner too: it kept saying "searching…" beneath the failure.
    node.querySelector('.status').textContent = '';
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
/* Navigation groups.
 *
 * The tab strip reached eleven peers and overflowed its own bar. Flattening
 * everything to one row also made a claim that was not true: that these are all
 * the same kind of destination. Three of them analyse whichever ticker is
 * loaded and are inert without one; four describe the market; two are the
 * reader's own holdings.
 *
 * So the top row is what you are working ON and the second row is which page
 * inside it. Analyse is hidden entirely until a symbol exists, because three
 * destinations whose only content is "No ticker loaded" are three destinations
 * that waste a click.
 */
const NAV_GROUPS = [
  { id: 'home', label: 'Home', views: ['home'] },
  { id: 'chart', label: 'Charting', views: ['chart'] },
  { id: 'analyse', label: 'Analysis', views: ['swing', 'earnings', 'compare', 'long'] },
  { id: 'market', label: 'Market', views: ['brief', 'market', 'indices'] },
  { id: 'scan', label: 'Scan', views: ['scan'] },
  // Named for what it is rather than what it resembles. "Portfolio" implies
  // holdings you own; this is the terminal's own simulated ledger, and the app
  // already called it Optic's Positions in the panel heading, the status line
  // and paper.py. One name for one thing.
  { id: 'portfolio', label: "Optic's Positions", views: ['tracker'] },
];

const SUB_LABELS = {
  chart: 'Charting',
  swing: 'Swing', earnings: 'Earnings', compare: 'Compare', long: 'Long-Term',
  brief: 'Read', market: 'Macro', indices: 'Indices',
  tracker: "Optic's Positions",
};

const SUB_TITLES = {
  chart: 'Charting. Full-height chart, overlays and drawings',
  swing: 'Swing trading and options analysis',
  earnings: 'Earnings analysis and the pre-earnings brief',
  compare: 'Compare two to four tickers side by side',
  instrument: 'Full history for one cross-asset instrument',
  long: 'Long-term share holdings',
  brief: "Optic's Read. The daily market, macro and world summary",
  market: 'Macro regime and sector rotation',
  indices: 'Major index long-run cycle',
  tracker: "Optic's Positions. The terminal's own paper-traded record",
};

/** Which group a view belongs to. */
function groupForView(view) {
  // The instrument chart has no fixed home: it belongs to the group that opened
  // it, so the subnav keeps the reader where they were.
  if (view === 'instrument' && STATE.instrumentFrom) return STATE.instrumentFrom;
  const g = NAV_GROUPS.find((x) => x.views.includes(view));
  return g ? g.id : 'home';
}

/** Repaint both rows for the active view. */
/* One row of sections, each opening a menu of its pages on hover.
 *
 * The two-row version put a second strip of tabs under the first, which cost
 * ~50px of permanent vertical chrome and asked the reader to hold two levels of
 * navigation in view at all times to use one of them. A group with a single page
 * is a plain button; a group with several opens a menu.
 *
 * Hover opens it, but the button itself still navigates on click and the menu is
 * keyboard reachable — hover alone is not an interaction anyone on a touchscreen
 * or a keyboard can perform, so it accelerates the mouse case rather than being
 * the only way in.
 */
function paintNav(view) {
  const active = groupForView(view);
  const nav = document.querySelector('nav.tabs-group');
  if (!nav) return;

  // The instrument chart is a transient page attached to whichever group opened
  // it, so it appears inside that group's menu rather than as a fixed entry.
  const extraFor = (groupId) => (
    STATE.instrument && STATE.instrumentFrom === groupId
      ? [{ view: 'instrument', label: STATE.instrument.label, dynamic: true }]
      : []);

  nav.innerHTML = NAV_GROUPS.map((group) => {
    const pages = [...group.views.map((v) => ({ view: v, label: SUB_LABELS[v] || v })),
      ...extraFor(group.id)];
    const isActive = group.id === active;
    const single = pages.length < 2;
    if (single) {
      return `<button role="tab" class="nav-top" data-group="${group.id}"
        aria-selected="${isActive}">${esc(group.label)}</button>`;
    }
    // Just the section name. The page you are on is marked inside the menu, which
    // is enough — repeating it on the button made the bar wider and said the same
    // thing twice.
    return `<div class="nav-item${isActive ? ' on' : ''}">
      <button role="tab" class="nav-top" data-group="${group.id}"
        aria-selected="${isActive}" aria-haspopup="true"
        >${esc(group.label)}<i class="nav-caret" aria-hidden="true"></i></button>
      <div class="nav-menu" role="menu">
        ${pages.map((p) => `<button role="menuitem" class="nav-page${
  p.view === view ? ' current' : ''}" data-view="${p.view}"
          title="${esc(SUB_TITLES[p.view] || '')}">${esc(p.label)}${
  p.dynamic ? `<i class="sub-close" data-close-instrument
            title="Close this chart" aria-hidden="true">\u00d7</i>` : ''}</button>`).join('')}
      </div>
    </div>`;
  }).join('');

  // The second row is gone, so anything still holding it must not reserve space.
  const sub = document.getElementById('subnav');
  if (sub) { sub.innerHTML = ''; sub.hidden = true; }
}

let viewBeforeSettings = 'home';

function switchView(view, force) {
  if (view !== 'tracker') stopTrackerPoll();
  // Captured before STATE.view is overwritten.
  if (view === 'settings' && STATE.view !== 'settings') viewBeforeSettings = STATE.view;
  STATE.view = view;
  Object.entries(views).forEach(([k, node]) => node.classList.toggle('active', k === view));
  if (view !== 'settings') NAV_LAST[groupForView(view)] = view;
  paintNav(view);
  // The settings gear sits in the top bar, not the tab strip, so it isn't covered
  // by the loop above.
  const gear = $('#settings-btn');
  if (gear) {
    const open = view === 'settings';
    gear.setAttribute('aria-pressed', String(open));
    gear.setAttribute('aria-label', open ? 'Close settings' : 'Settings');
    gear.title = open
      ? `Close settings. Back to ${VIEW_NAMES[viewBeforeSettings] || 'Home'}`
      : 'Settings. Appearance and time zone';
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

/* Delegated, because the second row is rebuilt on every switch — a bind-once
 * loop would only ever reach the buttons that existed at load. */
document.addEventListener('click', (evt) => {
  const groupBtn = evt.target.closest('nav.tabs-group button[data-group]');
  if (groupBtn) {
    const g = NAV_GROUPS.find((x) => x.id === groupBtn.dataset.group);
    if (!g) return;
    // Land on the page you were last on inside this group, so switching away
    // and back does not silently reset you to its first tab.
    const remembered = NAV_LAST[g.id];
    switchView(g.views.includes(remembered) ? remembered : g.views[0]);
    return;
  }
  // Any page button inside the nav, wherever it lives. This was scoped to
  // `nav.tabs-sub` — the second row — so when the pages moved into dropdowns
  // inside `nav.tabs-group` nothing matched and clicking Earnings did nothing at
  // all. The menu rendered, opened, and was inert.
  const viewBtn = evt.target.closest('nav.tabs [data-view]');
  if (viewBtn && viewBtn.dataset.view) {
    switchView(viewBtn.dataset.view);
    // Drop focus so the menu closes: it is held open by :focus-within, and a
    // button that keeps focus after navigating leaves the menu covering the page
    // it just took you to.
    if (viewBtn.blur) viewBtn.blur();
  }
});

// Last page visited inside each group.
const NAV_LAST = {};

// Paint once for whatever view the app opens on. Without this the second row
// renders empty-but-visible on first load, which is a stray rule across the page.
paintNav(STATE.view || 'home');

// Human names for the views, for the gear's tooltip.
const VIEW_NAMES = {
  chart: 'Charting',
  home: 'Home', swing: 'Swing', earnings: 'Earnings',
  market: 'Macro', indices: 'Indices', long: 'Long-Term', roth: 'Roth',
  tracker: "Optic's Positions", settings: 'Settings', brief: "Optic's Read",
};

// The logo goes home, the way it does on essentially every site. It was a plain
// div before, so clicking it did nothing.
const brandBtn = $('#brand-home');
if (brandBtn) brandBtn.addEventListener('click', () => switchView('home'));

const settingsBtn = $('#settings-btn');
if (settingsBtn) {
  settingsBtn.addEventListener('click', () => {
    if (STATE.view !== 'settings') { switchView('settings'); return; }
    // Second press: back where you came from. Guard the ticker-only views — the
    // symbol could have been cleared while Settings was open, and returning to a
    // "No ticker loaded" panel is a worse answer than Home.
    let back = viewBeforeSettings;
    const needsTicker = !['home', 'market', 'indices', 'roth', 'tracker', 'brief'].includes(back);
    if (back === 'settings' || (needsTicker && !STATE.ticker)) back = 'home';
    switchView(back);
  });
}

/* Charts bake the container's pixel width into their viewBox, so a width change
 * (window resize, or the chat panel taking 400px off the right) needs a re-render
 * to stay sharp. Re-render only — no reveal animation, since nothing new arrived.
 */
const rerenderActiveView = () => {
  // A resize redraw is not a fresh load — replaying the draw-on animation while
  // someone drags a window edge would fire it on every frame.
  setChartLive(isTapeLiveET());
  setChartAnimation(false);
  if (STATE.view === 'home') return; // no charts to re-scale
  // Settings draws from SETTINGS, not from a fetched payload, so it has no
  // STATE entry to gate on.
  if (STATE.view === 'settings') { renderSettings(); return; }
  /* The workspace keeps its payload in STATE.chartData, not STATE.chart, so the
   * generic lookup below found nothing and returned before redrawing. That is
   * why opening Pulse left the chart drawn at its old width with the legend
   * sitting on top of the header: the observer fired, this function bailed, and
   * nothing re-measured. */
  if (STATE.view === 'chart') {
    wsSyncChromeHeight();
    wsSyncNarrow();
    wsRedrawChart();
    return;
  }
  const d = STATE[STATE.view];
  if (!d) return;
  if (STATE.view === 'swing') renderSwing(d);
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
      ${tickerMark(r.symbol)}
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

/* Logos in the ticker typeahead.
 *
 * A separate cascade from the earnings one, because that keys off a company's
 * website domain and this cannot: the search endpoint returns a symbol and a
 * name, and fetching ten company profiles per keystroke to learn ten domains
 * would make the box unusable. These two services key off the plain ticker.
 * Both were measured against equities and ETFs — AAPL, NVDA, SPY, QQQ, ATAI,
 * CDNA, XLK all resolve on each — which matters because a search list is mostly
 * names you have not heard of, exactly where a logo helps most.
 *
 * The monogram renders first and the image loads over it, so the row never
 * reflows and a symbol with no logo anywhere still looks deliberate rather than
 * broken. */
const TICKER_LOGO_SOURCES = [
  (t) => `https://assets.parqet.com/logos/symbol/${encodeURIComponent(t)}`,
  (t) => `https://financialmodelingprep.com/image-stock/${encodeURIComponent(t)}.png`,
];

window.nextTickerLogo = function nextTickerLogo(img) {
  const step = Number(img.dataset.tlStep || 0) + 1;
  const sym = img.dataset.tlSym;
  if (!sym || step >= TICKER_LOGO_SOURCES.length) { img.remove(); return; }
  img.dataset.tlStep = String(step);
  img.src = TICKER_LOGO_SOURCES[step](sym);
};

function tickerMark(symbol, size) {
  const px = size || 22;
  const sym = String(symbol || '?').toUpperCase();
  const initials = sym.slice(0, 4);
  let hash = 0;
  for (let i = 0; i < initials.length; i += 1) {
    hash = (hash * 31 + initials.charCodeAt(i)) % 360;
  }
  return `<span class="co-mark" style="--co-size:${px}px;--co-hue:${hash}"
    aria-hidden="true"><span class="co-mono">${esc(initials)}</span><img
      src="${esc(TICKER_LOGO_SOURCES[0](sym))}" alt="" loading="lazy"
      referrerpolicy="no-referrer" data-tl-sym="${esc(sym)}" data-tl-step="0"
      onerror="nextTickerLogo(this)"></span>`;
}

/** Load a ticker from anywhere (top bar, home form, home quick-pick). */
function loadTicker(raw, destination) {
  const next = (raw || '').trim().toUpperCase();
  if (!next) return;
  STATE.ticker = next;
  STATE.swing = null;
  STATE.earnings = null;
  STATE.earningsBrief = null;
  STATE.long = null;
  $('#ticker-input').value = next;
  STATE.session = null;
  loadSession(true);
  // Coming from home there's nothing to show on home, so land on the analysis.
  // `destination` is for callers that must leave their own tab. Clicking a
  // holding in Optic's Positions means "show me why", which is the swing read,
  // not a re-render of the ledger you were already looking at.
  const target = destination || (STATE.view === 'home' ? 'swing' : STATE.view);

  /* Landing on Charting has to move the chart's own symbol.
   *
   * The workspace deliberately keeps a symbol separate from STATE.ticker, so
   * you can chart one name while analysing another. That is worth having across
   * tabs, but it broke the header box: typing BSX and pressing Load while
   * standing on Charting set STATE.ticker, re-entered the chart view, and the
   * view reloaded itself from its OWN unchanged symbol. The chart carried on
   * showing INTC while the box read BSX, and BSX had quietly loaded into tabs
   * that were not on screen.
   *
   * The header box is the only symbol input visible from Charting, so using it
   * there means "chart this". Assigned before switchView, because the view
   * entry reads STATE.chartSymbol to decide what to fetch. */
  if (target === 'chart') STATE.chartSymbol = next;

  switchView(target, true);
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
  if (evt.target.id === 'lt-interval') {
    ltInterval = evt.target.value;
    try { localStorage.setItem(LT_INTERVAL_KEY, ltInterval); } catch (e) { /* private mode */ }
    if (STATE.long) renderLong(STATE.long);
    return;
  }
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
  if (evt.target.id === 'chart-interval') {
    chartInterval = evt.target.value;
    try { localStorage.setItem(CHART_INTERVAL_KEY, chartInterval); } catch (e) { /* private mode */ }
  } else {
    return;
  }
  if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
});

document.addEventListener('click', (evt) => {
  // Closing the instrument tab. Checked before the row handler so the little x
  // does not also re-open the chart it is dismissing.
  // Pulse conversation history.
  if (evt.target.closest('#chat-history-btn')) {
    renderPulseHistory(!pulseHistoryOpen);
    return;
  }
  if (evt.target.closest('[data-alerts-seen]')) {
    postJSON('/api/alerts/seen', {}).then(() => loadAlerts(true));
    return;
  }
  if (evt.target.closest('[data-alerts-clear]')) {
    postJSON('/api/alerts/clear', {}).then(() => loadAlerts(true));
    return;
  }
  if (evt.target.closest('[data-origin-retry]')) {
    // Reset the backoff so an explicit click checks immediately rather than
    // waiting out a delay that has grown to fifteen seconds.
    originWatchDelay = 500;
    if (originWatchTimer) { clearTimeout(originWatchTimer); originWatchTimer = null; }
    startOriginWatch();
    return;
  }
  if (evt.target.closest('[data-pulse-new]')) { pulseNewConversation(); return; }
  if (evt.target.closest('[data-pulse-more]')) {
    pulseStartersExpanded = true; renderPulseEmpty(); return;
  }
  if (evt.target.closest('[data-pulse-less]')) {
    pulseStartersExpanded = false; renderPulseEmpty(); return;
  }
  const starter = evt.target.closest('.pulse-card');
  if (starter) {
    const box = document.getElementById('chat-input');
    if (box) { box.value = starter.dataset.q; box.focus(); }
    return;
  }
  const phOpen = evt.target.closest('[data-pulse-open]');
  if (phOpen) { pulseResume(phOpen.dataset.pulseOpen); return; }
  const phDel = evt.target.closest('[data-pulse-del]');
  if (phDel) { pulseDelete(phDel.dataset.pulseDel); return; }
  if (evt.target.closest('[data-close-instrument]')) {
    evt.stopPropagation();
    const back = STATE.instrumentBack;
    const group = NAV_GROUPS.find((g) => g.id === STATE.instrumentFrom);
    STATE.instrument = null;
    STATE.instrumentData = null;
    STATE.instrumentKey = null;
    STATE.instrumentFrom = null;
    switchView(back || (group ? group.views[0] : 'market'));
    return;
  }
  // Back to a bare price chart in one click. Worth having as an explicit control
  // rather than expecting six unticks: the state that made the chart unreadable
  // took one click each to build up and should take one to undo.
  if (evt.target.closest('[data-clear-levels]')) {
    setFamily('ma', false); setFamily('ema', false);
    showFib = false; showSR = false;
    showVbp = false; showInsiders = false; showZones = false;
    [[SHOW_MA_KEY, false], [SHOW_EMA_KEY, false], [SHOW_FIB_KEY, false],
      [SHOW_SR_KEY, false], [SHOW_VBP_KEY, false], [SHOW_INS_KEY, false],
      [SHOW_ZONES_KEY, false]]
      .forEach(([k, v]) => storeFlag(k, v));
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  if (evt.target.closest('[data-clear-indicators]')) {
    indicatorIds = [];
    try { localStorage.setItem(IND_STATE_KEY, '[]'); } catch (e) { /* private mode */ }
    STATE.indicators = null;
    STATE.indicatorsKey = null;
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  /* Drilling into a sector map, checked BEFORE data-instrument.
   *
   * Every tile carries data-instrument so it can open a chart, and that handler
   * is right below this one. A sector tile carries both, so if the instrument
   * check ran first a click on XLE would open the XLE chart and the drill would
   * be unreachable. Sectors drill, individual names open: one level down, the
   * tiles are ordinary stocks with no data-map-sector, so the handler below
   * takes them and the behaviour a reader already knows is unchanged. */
  const drill = evt.target.closest('[data-map-sector]');
  if (drill) {
    loadStockMap(STATE.stockMapTemplate, true, drill.dataset.mapSector);
    return;
  }
  if (evt.target.closest('[data-map-sector-back]')) {
    loadStockMap(STATE.stockMapTemplate, true, null);
    return;
  }
  const instCell = evt.target.closest('[data-instrument]');
  if (instCell && instCell.dataset.instrument) {
    openInstrument(instCell.dataset.instrument,
      instCell.dataset.instrumentLabel || instCell.dataset.instrument);
    return;
  }
  const instRangeBtn = evt.target.closest('[data-inst-range]');
  if (instRangeBtn) {
    instrumentRange = instRangeBtn.dataset.instRange;
    loadInstrument(true);
    return;
  }
  const instModeBtn = evt.target.closest('[data-inst-mode]');
  if (instModeBtn) {
    instrumentMode = instModeBtn.dataset.instMode === 'candle' ? 'candle' : 'line';
    preserveUI(views.instrument, () => {
      views.instrument.innerHTML = renderInstrument(STATE.instrumentData);
      drawInstrumentChart(STATE.instrumentData);
    });
    return;
  }
  // Timeframe pills. Same shape for every chart that has them, so a new chart
  // only needs to emit rangePills() with its own attribute to be wired up.
  const tf = evt.target.closest('[data-chart-range]');
  if (tf) {
    chartRange = tf.dataset.chartRange;
    try { localStorage.setItem(CHART_RANGE_KEY, chartRange); } catch (e) { /* private mode */ }
    if (isIntradayRange(chartRange)) { loadIntraday(chartRange); return; }
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  const ltTf = evt.target.closest('[data-lt-range]');
  if (ltTf) {
    ltRange = ltTf.dataset.ltRange;
    try { localStorage.setItem(LT_RANGE_KEY, ltRange); } catch (e) { /* private mode */ }
    if (STATE.long) preserveUI(views.long, () => renderLong(STATE.long));
    return;
  }
  const modeBtn = evt.target.closest('[data-chart-mode]');
  if (modeBtn) {
    chartMode = modeBtn.dataset.chartMode === 'candle' ? 'candle' : 'line';
    try { localStorage.setItem(CHART_MODE_KEY, chartMode); } catch (e) { /* private mode */ }
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  const ltBtn = evt.target.closest('[data-lt-mode]');
  if (ltBtn) {
    ltMode = ltBtn.dataset.ltMode === 'candle' ? 'candle' : 'line';
    try { localStorage.setItem(LT_MODE_KEY, ltMode); } catch (e) { /* private mode */ }
    if (STATE.long) preserveUI(views.long, () => renderLong(STATE.long));
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
  /* --------------------------------------- the indicator manager */
  if (evt.target.closest('[data-ws-manage]')) {
    wsManageOpen = true; wsManageQuery = ''; wsMenuOpen = null;
    wsRefresh();
    return;
  }
  if (evt.target.closest('[data-ws-manage-close]')) {
    wsManageOpen = false; wsRefresh(); return;
  }
  // Click the backdrop to dismiss, but not a click inside the box.
  const backdrop = evt.target.closest('[data-ws-modal]');
  if (backdrop && evt.target === backdrop) { wsManageOpen = false; wsRefresh(); return; }
  if (evt.target.closest('[data-ws-manage-reset]')) {
    resetOverlayStyle(null);
    wsRefresh();
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  const styleReset = evt.target.closest('[data-ws-style-reset]');
  if (styleReset) {
    resetOverlayStyle(styleReset.dataset.wsStyleReset);
    wsRefresh();
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  const swatch = evt.target.closest('[data-ws-color]');
  if (swatch) {
    setOverlayStyle(swatch.dataset.wsStyle, { color: swatch.dataset.wsColor });
    wsRefresh();
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  /* ------------------------------------------------ chart workspace */
  const econBtn = evt.target.closest('[data-econ]');
  if (econBtn) { loadEcon(econBtn.dataset.econ, true); return; }
  const mapT = evt.target.closest('[data-map-template]');
  if (mapT) { loadStockMap(mapT.dataset.mapTemplate, true, null); return; }
  const wsLoad = evt.target.closest('[data-ws-load]');
  if (wsLoad) {
    const sym = wsLoad.dataset.wsLoad;
    if (!sym) { STATE.chartSymbol = ''; STATE.chartData = null; renderChartWorkspace(null); }
    else loadChartWorkspace(sym);
    return;
  }
  /* An open dropdown closes when you click away from it.
   *
   * wsMenuOpen was only ever cleared by clicking the same button again, so a
   * menu left open sat over the interval and range pills underneath it. Placed
   * before the button handler so the toggle below still works: a click on the
   * button matches [data-ws-menu] and returns there, and a click inside the
   * popup matches .ws-menu and is left alone so the checkboxes keep working. */
  if (wsMenuOpen && STATE.view === 'chart' && !evt.target.closest('.ws-menu')) {
    wsMenuOpen = null;
    const tbc = views.chart.querySelector('.ws-toolbar');
    if (tbc) tbc.outerHTML = wsToolbar();
    // Deliberately no return: the click was meant for whatever is underneath,
    // and swallowing it would mean every first click after opening a menu did
    // nothing but close it.
  }
  const wsMenu = evt.target.closest('[data-ws-menu]');
  if (wsMenu) {
    const id = wsMenu.dataset.wsMenu;
    wsMenuOpen = wsMenuOpen === id ? null : id;
    // Toolbar only. Opening a dropdown does not change the chart, and rebuilding
    // it to show a menu was redrawing 743px of SVG to reveal six checkboxes.
    const tb2 = views.chart.querySelector('.ws-toolbar');
    if (tb2) tb2.outerHTML = wsToolbar();
    return;
  }
  if (evt.target.closest('[data-ws-zoom-reset]')) { wsResetZoom(); return; }
  const wsMode = evt.target.closest('[data-ws-mode]');
  if (wsMode) {
    chartMode = wsMode.dataset.wsMode;
    try { localStorage.setItem(CHART_MODE_KEY, chartMode); } catch (e) { /* private mode */ }
    wsRedrawChart();
    return;
  }
  const wsRange = evt.target.closest('[data-ws-range]');
  if (wsRange) {
    chartRange = wsRange.dataset.wsRange;
    wsWindow = null;   // a range pill overrides a manual zoom
    try { localStorage.setItem(CHART_RANGE_KEY, chartRange); } catch (e) { /* private mode */ }
    wsRedrawChart();
    return;
  }
  const wsInt = evt.target.closest('[data-ws-interval]');
  if (wsInt) {
    chartInterval = wsInt.dataset.wsInterval;
    wsWindow = null;   // a range pill overrides a manual zoom
    try { localStorage.setItem(CHART_INTERVAL_KEY, chartInterval); } catch (e) { /* private mode */ }
    wsRedrawChart();
    return;
  }
  const wsTl = evt.target.closest('[data-ws-tool]');
  if (wsTl) {
    // Same: picking a tool changes the rail, not the chart.
    wsTool = wsTl.dataset.wsTool;
    wsPending = null;
    // One owner for the rail and the arming class, so this cannot drift from
    // the paths that reset the tool.
    wsSyncDrawChrome();
    wsRenderDrawings();
    return;
  }
  const wsOff = evt.target.closest('[data-ws-off]');
  if (wsOff) { wsSetOverlay(wsOff.dataset.wsOff, false); wsRedrawChart(); return; }
  const wsWClose = evt.target.closest('[data-ws-widget-close]');
  if (wsWClose) { wsToggleWidget(wsWClose.dataset.wsWidgetClose, false); return; }
  const wsWTog = evt.target.closest('[data-ws-widget-toggle]');
  if (wsWTog) {
    const id = wsWTog.dataset.wsWidgetToggle;
    wsToggleWidget(id, !wsDockOpen.includes(id));
    return;
  }
  const wsUnwatch = evt.target.closest('[data-ws-unwatch]');
  if (wsUnwatch) {
    wsSaveWatch(wsWatch().filter((t) => t !== wsUnwatch.dataset.wsUnwatch));
    wsRepaintWidget('watchlist');
    return;
  }
  const wsWatchAdd = evt.target.closest('[data-ws-watch-add]');
  if (wsWatchAdd) {
    const t = wsWatchAdd.dataset.wsWatchAdd;
    if (t && !wsWatch().includes(t)) wsSaveWatch([...wsWatch(), t]);
    wsRepaintWidget('watchlist');
    return;
  }
  const legToggle = evt.target.closest('[data-ws-leg-toggle]');
  if (legToggle) {
    wsLegendOpen = !wsLegendOpen;
    try { localStorage.setItem(WS_LEGEND_KEY, wsLegendOpen ? 'open' : 'closed'); }
    catch (e) { /* private mode */ }
    // Legend only. Collapsing a list is not a reason to redraw 743px of SVG.
    const leg = views.chart.querySelector('.ws-legend');
    if (leg) leg.outerHTML = wsLegend(wsSeries(STATE.chartData));
    return;
  }
  if (evt.target.closest('[data-ws-undo]')) { wsUndo(); return; }
  if (evt.target.closest('[data-ws-redo]')) { wsRedo(); return; }
  if (evt.target.closest('[data-ws-clear-draw]')) {
    if (!wsDrawings().length) return;
    wsPushUndo();
    wsSaveDrawings([]);
    wsSelected = null;
    wsRenderDrawings();
    wsSyncDrawChrome();
    return;
  }
  const pick = evt.target.closest('[data-pick]');
  if (pick) { loadTicker(pick.dataset.pick); return; }
  if (evt.target.closest('[data-cat-search]')) {
    CATALYST_FILTERS.q = (document.getElementById('cat-q') || {}).value || '';
    loadCatalysts(true);
    return;
  }
  const catFilter = evt.target.closest('[data-cat-filter]');
  if (catFilter && catFilter.tagName === 'SELECT') { /* handled on change */ }
  const catRefresh = evt.target.closest('[data-cat-refresh]');
  if (catRefresh) { refreshCatalysts(catRefresh); return; }
  const sread = evt.target.closest('[data-sector-read]');
  if (sread) {
    openSectorRead(sread.dataset.sectorRead,
      STATE.view === 'indices' ? 'index-read-host' : 'sector-read-host');
    return;
  }
  if (evt.target.closest('[data-sector-read-close]')) {
    STATE.sectorRead = null;
    renderSectorRead('sector-read-host'); renderSectorRead('index-read-host');
    return;
  }
  const ask = evt.target.closest('[data-ask]');
  if (ask) { openPulseWith(ask.dataset.ask); return; }
  const analyse = evt.target.closest('[data-analyse]');
  if (analyse) { loadTicker(analyse.dataset.analyse, 'swing'); return; }
  const drop = evt.target.closest('[data-drop-attach]');
  if (drop) {
    attachState.splice(Number(drop.dataset.dropAttach), 1);
    renderAttachments();
    return;
  }
  if (evt.target.closest('[data-goto-catalysts]')) {
    const host = document.getElementById('catalyst-host');
    if (host) host.scrollIntoView({ block: 'start', behavior: 'smooth' });
    return;
  }
  // The calendar filters swap one panel, not the whole Read tab: re-rendering
  // renderBrief would close every other <details> on the page to change a pill.
  const calImpact = evt.target.closest('[data-cal-impact]');
  const calRange = evt.target.closest('[data-cal-range]');
  if (calImpact || calRange) {
    if (calImpact) STATE.calImpact = calImpact.dataset.calImpact;
    if (calRange) STATE.calRange = calRange.dataset.calRange;
    const host = document.getElementById('cal-panel');
    const cal = (STATE.brief || {}).calendar;
    if (host && cal) host.outerHTML = briefCalendar(cal);
    return;
  }
  if (evt.target.closest('[data-cmp-run]')) { runCompare(); return; }
  if (evt.target.closest('[data-cmp-add]')) {
    STATE.compareInputs = [...(STATE.compareInputs || []), ''];
    views.compare.innerHTML = renderCompare(STATE.compare);
    return;
  }
  if (evt.target.closest('[data-cmp-drop]')) {
    STATE.compareInputs = (STATE.compareInputs || []).slice(0, -1);
    views.compare.innerHTML = renderCompare(STATE.compare);
    return;
  }
  const ewBtn = evt.target.closest('[data-ew-offset]');
  if (ewBtn) { loadEarningsWeek(Number(ewBtn.dataset.ewOffset)); return; }
  const bookBtn = evt.target.closest('[data-book]');
  if (bookBtn) {
    STATE.trackerBook = bookBtn.dataset.book;
    STATE.tracker = null;
    STATE.bookRisk = null;
    loadTracker(true);
    return;
  }
  const noticeOk = evt.target.closest('[data-notice-ok]');
  if (noticeOk) { dismissNotice(noticeOk.dataset.noticeOk); return; }
  const noticeMore = evt.target.closest('[data-notice-more]');
  if (noticeMore) {
    const target = document.querySelector(noticeMore.dataset.noticeMore);
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' });
      // A brief highlight, so it is obvious which paragraph answered the question.
      target.classList.add('ex-flash');
      setTimeout(() => target.classList.remove('ex-flash'), 1600);
    }
    return;
  }
  const gotoView = evt.target.closest('[data-goto-view]');
  if (gotoView) { switchView(gotoView.dataset.gotoView); return; }
  if (evt.target.closest('[data-goto-home]')) switchView('home');
  if (evt.target.closest('[data-goto-settings]')) switchView('settings');
});

/* The chart note saves when you leave the box, not per keystroke: localStorage
 * writes are synchronous, and a write per character on a few paragraphs is a
 * stall you can feel while typing. */
document.addEventListener('blur', (evt) => {
  const note = evt.target.closest && evt.target.closest('[data-ws-note]');
  if (note) wsSaveNote(note.dataset.wsNote, note.value);
}, true);

// Roth controls: inputs live in STATE so the panel survives tab switches.
document.addEventListener('submit', (evt) => {
  if (evt.target.matches('[data-ws-watch-form]')) {
    evt.preventDefault();
    const box = evt.target.querySelector('[data-ws-watch-input]');
    const t = (box.value || '').trim().toUpperCase();
    if (t && !wsWatch().includes(t)) wsSaveWatch([...wsWatch(), t]);
    box.value = '';
    wsRepaintWidget('watchlist');
    return;
  }
  if (evt.target.id === 'ws-form') {
    evt.preventDefault();
    const box = document.getElementById('ws-symbol');
    if (box && box.value.trim()) loadChartWorkspace(box.value);
    return;
  }
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
  wsOnChatToggle();
  if (document.body.classList.contains('chat-open')) $('#chat-input').focus();
  // Charts re-render themselves via the ResizeObserver on <main> — opening the
  // panel takes 400px off the content width.
});
$('#chat-close').addEventListener('click', () => {
  document.body.classList.remove('chat-open');
  wsOnChatToggle();
});
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

/* ------------------------------------------------------- collapsible panels
 *
 * Swing measured 14,700px — about seventeen screens. Everything it knows is on
 * one page in one column, which is thorough and unusable: the reader scrolls past
 * the greeks to reach the financials and loses the verdict they came for.
 *
 * Applied as a post-render pass rather than in each renderer. There are 81 panels
 * across nine views; wrapping each one at its build site would mean 81 edits and a
 * new panel could silently miss the treatment. Here it is one place, and a panel
 * physically cannot be added without inheriting it.
 *
 * What stays open is chosen per view, and the rule is "what did the reader come
 * for": on Swing that is the verdict, the quote, the two summary panels and the
 * chart. The rest opens on a click and remembers the choice, so a reader who
 * always wants the option chain gets it every time after the first.
 */

// Headings that stay expanded on first load, per view. Matched case-insensitively
// on the panel's own h2 text, so a heading rename shows up as a panel that starts
// collapsed rather than as a crash.
const PANELS_OPEN_BY_DEFAULT = {
  swing: [
    'swing verdict', 'quote', "optic's perspective", 'close defence',
    'price, moving averages', 'seasonality', 'corporate actions',
  ],
  earnings: ['event pricing', 'earnings verdict', 'next report'],
  long: ['long-term view', 'close defence', 'valuation vs its own history'],
  market: ['macro regime', 'market breadth', 'sector rotation', 'stock maps',
    'currencies', 'economic data'],
  brief: ["optic's read", 'weekly market analysis', 'morning desk', 'on the calendar'],
  tracker: ['the record', 'open positions', 'how the ledger works'],
  indices: ['major etfs', 'index regime'],
  roth: [],
};

const COLLAPSE_KEY = 'optic.panels.open';

function collapseState() {
  try { return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') || {}; }
  catch (e) { return {}; }
}

function rememberCollapse(id, open) {
  try {
    const all = collapseState();
    all[id] = open;
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify(all));
  } catch (e) { /* private mode: the session still works, it just forgets */ }
}

/** Stable-ish id for a panel: view plus its heading text. */
function panelId(view, title) {
  return view + '|' + title.toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 48);
}

/* Expand-all / collapse-all.
 *
 * Placed at the top of the view rather than floating, because it is a rare
 * action and a persistent floating control would compete with the content for
 * attention on every scroll. The label reflects what pressing it will DO, not
 * the current state — a button reading "Expanded" leaves the reader guessing
 * whether that is a description or a destination. */
function setAllPanels(view, open) {
  const host = views[view];
  if (!host) return;
  host.querySelectorAll('.panel[data-collapsible="1"]').forEach((panel) => {
    const btn = panel.querySelector(':scope > h2 > .panel-toggle');
    if (!btn) return;
    panel.classList.toggle('is-open', open);
    panel.classList.toggle('is-closed', !open);
    btn.setAttribute('aria-expanded', String(open));
    const title = (panel.querySelector(':scope > h2')?.textContent || '').trim();
    btn.setAttribute('aria-label', (open ? 'Collapse ' : 'Expand ') + title);
    if (panel.dataset.panelId) rememberCollapse(panel.dataset.panelId, open);
  });
  const bar = host.querySelector('.panel-bulk');
  if (bar) bar.dataset.allOpen = String(open);
}

function addBulkControl(view) {
  const host = views[view];
  if (!host || host.querySelector('.panel-bulk')) return;
  if (host.querySelectorAll('.panel[data-collapsible="1"]').length < 4) return;
  const bar = document.createElement('div');
  bar.className = 'panel-bulk span-all';
  bar.innerHTML = `<button type="button" class="bulk-btn" data-bulk="open">Expand all</button>
    <button type="button" class="bulk-btn" data-bulk="close">Collapse all</button>`;
  bar.addEventListener('click', (evt) => {
    const b = evt.target.closest('[data-bulk]');
    if (b) setAllPanels(view, b.dataset.bulk === 'open');
  });
  host.insertBefore(bar, host.firstChild);
}

function makePanelsCollapsible(view) {
  const host = views[view];
  if (!host) return;
  const openByDefault = PANELS_OPEN_BY_DEFAULT[view] || [];
  const saved = collapseState();

  host.querySelectorAll('.panel').forEach((panel) => {
    // Only panels with their own h2 are collapsible. A panel without a heading has
    // nothing to click and nothing to label the collapsed state with.
    const head = panel.querySelector(':scope > h2');
    if (!head || panel.dataset.collapsible === '1') return;

    const title = (head.textContent || '').trim();
    if (!title) return;
    const id = panelId(view, title);
    const isDefaultOpen = openByDefault.some((k) => title.toLowerCase().includes(k));
    const open = Object.prototype.hasOwnProperty.call(saved, id) ? !!saved[id] : isDefaultOpen;

    panel.dataset.collapsible = '1';
    panel.dataset.panelId = id;
    panel.classList.toggle('is-open', open);
    panel.classList.toggle('is-closed', !open);

    // Everything after the heading becomes the collapsible body, so the heading
    // stays visible as the thing you click.
    const body = document.createElement('div');
    body.className = 'panel-body';
    let node = head.nextSibling;
    while (node) {
      const next = node.nextSibling;
      body.appendChild(node);
      node = next;
    }
    panel.appendChild(body);

    // The heading becomes the control. A button inside it rather than a click
    // handler on the h2 itself, so it is reachable by keyboard and announced.
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'panel-toggle';
    btn.setAttribute('aria-expanded', String(open));
    btn.setAttribute('aria-label', (open ? 'Collapse ' : 'Expand ') + title);
    head.appendChild(btn);
    head.classList.add('is-toggle');
  });
}

// One delegated listener for every panel on every view.
document.addEventListener('input', (evt) => {
  const mq = evt.target.closest('[data-ws-manage-q]');
  if (mq) {
    wsManageQuery = mq.value;
    // Repaint the modal only, so the box keeps focus and the caret position.
    const modal = views.chart.querySelector('[data-ws-modal]');
    if (modal) {
      modal.outerHTML = wsManagePanel();
      const again = views.chart.querySelector('[data-ws-manage-q]');
      if (again) { again.focus(); again.setSelectionRange(again.value.length, again.value.length); }
    }
    return;
  }
  const box = evt.target.closest('[data-cmp-input]');
  if (!box) return;
  // Held in state because every control here re-renders the panel; without this
  // adding a third ticker would clear the first two.
  const idx = Number(box.dataset.cmpInput);
  const next = [...(STATE.compareInputs || [])];
  next[idx] = box.value;
  STATE.compareInputs = next;
});

document.addEventListener('keydown', (evt) => {
  wsDrawKeys(evt);
  if (evt.key === 'Enter' && evt.target.id === 'fx-q') {
    evt.preventDefault();
    loadForex(true, evt.target.value);
    return;
  }
  if (evt.key === 'Escape' && wsManageOpen) { wsManageOpen = false; wsRefresh(); return; }
  if (evt.key === 'Enter' && evt.target.closest('[data-cmp-input]')) runCompare();
  // A row advertised as role="button" has to work from the keyboard, or the
  // affordance is a lie to anyone not using a mouse.
  const row = evt.target.closest('[data-instrument]');
  if (row && (evt.key === 'Enter' || evt.key === ' ')) {
    evt.preventDefault();
    openInstrument(row.dataset.instrument,
      row.dataset.instrumentLabel || row.dataset.instrument);
  }
});

document.addEventListener('change', (evt) => {
  const ind = evt.target.closest('[data-ind]');
  if (ind) {
    const id = ind.dataset.ind;
    indicatorIds = ind.checked
      ? [...indicatorIds.filter((x) => x !== id), id]
      : indicatorIds.filter((x) => x !== id);
    try { localStorage.setItem(IND_STATE_KEY, JSON.stringify(indicatorIds)); }
    catch (e) { /* private mode */ }
    // The panes and the price chart both live in the price panel now, so one
    // re-render of that panel covers the checkbox, the overlays and the panes.
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    loadIndicators(true);
    return;
  }
  /* The Learn widget's term picker.
   *
   * wsLearnTerm was declared and read but never written: there was no handler
   * for this select at all. A native select still changes what it displays, so
   * the control moved while the definition below it stayed pinned to the first
   * term alphabetically. The widget showed "Universe" selected above the
   * definition of 0dte, which reads as the wrong definition rather than as a
   * dead control. */
  const wsLearn = evt.target.closest('[data-ws-learn]');
  if (wsLearn) {
    wsLearnTerm = wsLearn.value;
    wsRepaintWidget('learn');
    return;
  }
  const wsOpt = evt.target.closest('[data-ws-opt]');
  if (wsOpt) {
    wsSetOverlay(wsOpt.dataset.wsOpt, wsOpt.checked);
    wsRedrawChart();
    // The Swing chart shares these flags, so it has to redraw too or the two
    // tabs disagree about what is switched on.
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  const opt = evt.target.closest('[data-level-opt]');
  if (opt) {
    const on = opt.checked;
    const key = opt.dataset.levelOpt;
    if (key === 'ma') { setFamily('ma', on); }
    else if (key === 'fib') { showFib = on; storeFlag(SHOW_FIB_KEY, on); }
    else if (key === 'sr') { showSR = on; storeFlag(SHOW_SR_KEY, on); }
    else if (key === 'vol') { showVol = on; storeFlag(SHOW_VOL_KEY, on); }
    else if (key === 'vbp') { showVbp = on; storeFlag(SHOW_VBP_KEY, on); }
    else if (key === 'insiders') { showInsiders = on; storeFlag(SHOW_INS_KEY, on); }
    else if (key === 'zones') { showZones = on; storeFlag(SHOW_ZONES_KEY, on); }
    else if (key === 'ema') { setFamily('ema', on); }
    if (STATE.swing) preserveUI(views.swing, () => renderSwing(STATE.swing));
    return;
  }
  const f = evt.target.closest('[data-cat-filter]');
  if (!f) return;
  CATALYST_FILTERS[f.dataset.catFilter] = f.value;
  loadCatalysts(true);
});

document.addEventListener('click', (evt) => {
  const head = evt.target.closest('.panel > h2.is-toggle');
  if (!head) return;
  // Let links and glossary terms inside the heading behave normally.
  if (evt.target.closest('a, .gloss-term, .chip, .ask-pulse')) return;
  const panel = head.parentElement;
  const open = !panel.classList.contains('is-open');
  panel.classList.toggle('is-open', open);
  panel.classList.toggle('is-closed', !open);
  const btn = head.querySelector('.panel-toggle');
  if (btn) {
    btn.setAttribute('aria-expanded', String(open));
    btn.setAttribute('aria-label', (open ? 'Collapse ' : 'Expand ')
      + (head.textContent || '').trim());
  }
  if (panel.dataset.panelId) rememberCollapse(panel.dataset.panelId, open);
});

/* Every renderer replaces its view's innerHTML wholesale, so the header pass has
 * to run after each one. Wrapping them here keeps it in a single place instead of
 * a trailing call appended to eight functions that would drift apart over time. */
[
  ['swing', () => renderSwing], ['earnings', () => renderEarnings],
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
    // Last, so it wraps the finished DOM including anything the steps above added.
    makePanelsCollapsible(view);
    addBulkControl(view);
    return result;
  };
  // Reassign the binding the rest of the file calls through.
  switch (view) {
    case 'swing': renderSwing = wrapped; break;
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
  initPulseLegal();
  initAttachments();
  initGlossaryTooltips();
  loadRothInputs();
  updateChatContext();
  renderPulseEmpty();
  // Not awaited: the picker falls back to a built-in default until the server's
  // list arrives, so nothing waits on it.
  loadPersonas();
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
      // The model id is deliberately not announced. It told the reader nothing
      // actionable, and it framed the assistant as a wrapper around a model
      // rather than as part of the terminal.
      addMsg('assistant', `Ask me anything. About the loaded ticker's gamma regime, flow or recommended strike, about the market as a whole, or attach a chart or PDF. **Deep research** runs live web sources.`);
    }
  } catch (e) { /* backend health is non-fatal for the UI */ }
  startAutoRefresh();
  // Deliberately no initial ticker fetch: the home page waits for the user to
  // choose one instead of assuming SPY.
})();
