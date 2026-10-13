# Terminals, charting and data platforms: competitive research for Optic

Researcher: competitive research agent. All sources read 2026-10-12. Evidence tags: DOC, MKT, OBS, 3P, INF (see brief).
Status: complete.

## 1. Bloomberg Terminal (professional reference)

Sources (all read 2026-10-12): Bloomberg product pages returned HTTP 403 to the fetcher, so official claims below come via
Bloomberg press releases as indexed in search and trade press:
[B1] Bloomberg press, Jan 2025 news summaries, via https://www.thetradenews.com/bloomberg-launches-gen-ai-summarisation-tool-for-news/ ;
[B2] Bloomberg press, Nov 2025 "AI Summary for Company News", https://www.bloomberg.com/company/press/investors-harness-bloombergs-expanded-ai-tools-to-discover-and-summarize-news (search snippet; page 403);
[B3] ASKB launch, Feb 2026, https://www.fi-desk.com/bloomberg-terminal-gains-conversational-ai-interface/ ;
[B4] ASKB on mobile, Aug 2026, https://itbrief.com.au/story/bloomberg-brings-askb-ai-to-mobile-with-cross-device-sync ;
[B5] University of Delaware Bloomberg function list, https://lerner.udel.edu/seeing-opportunity/bloomberg-functions-list ;
[B6] HSE Bloomberg training manual (EVTS), https://finance.hse.ru/data/2019/09/19/1540920642/Bloomberg%20Training%20Manual.pdf ;
[B7] Bloomberg Professional app, https://professional.bloomberg.com/products/bloomberg-terminal/access/bloomberg-professional-app and App Store id407761767 ;
[B8] Cost estimates, https://eulerpool.com/blog/bloomberg-terminal-cost and https://costbench.com/software/financial-data-terminals/bloomberg-terminal/ .

**1. Audience and promise.** Institutional investors, traders, analysts; promise is one place for all data, news,
analytics and messaging. [MKT, B7] Seat priced around $28k-$32k/year on two-year contracts; no published list price. [3P, B8]

**2. Compelling workflow.** Ticker + function mnemonic grammar: DES (description), CN (company news), GP (price graph),
HP (history), EVTS (events calendar), ALRT (price alerts), BLP Launchpad (custom multi-panel monitor). [DOC, B5, B6]
The value is that every function shares the loaded security, so moving from "what is it" to "what's new" to "what's
the chart" is one keystroke each. [INF]

**3. Time to first insight.** Fast for a trained user, slow for a new one: universities teach it via cheat sheets and
certification (Bloomberg Market Concepts), and users are told to type HELP to find functions. [DOC, B5] Jargon is
total; mnemonics must be learned. [INF]

**4. Hierarchy and disclosure.** DES is the canonical "start here" page; you page forward for more depth (progressive
disclosure by paging rather than by hiding). [DOC, B5] Launchpad lets each user set their own default screen of
monitors, news, and charts. [DOC, B5]

**5. Workflows.** Alerts (ALRT) on price; news alerts on market-moving events (economic, geopolitical, climate). [DOC, B5; MKT, B7]
EVTS filters upcoming earnings/calls by security or index. [DOC, B6] Launchpad monitors are the watchlist. [DOC, B5]

**6. AI.**
- AI news summaries: three bullets atop Bloomberg News stories (Jan 2025), extended to more sources (Nov 2025);
  outputs reviewed by subject-matter experts to tune the model. [MKT, B1, B2]
- AI Summary for Company News (Nov 2025): a timestamped digest of recent news about a company, grouped by financial
  analysis topics, aimed at companies in the user's portfolio. [MKT, B2] This is Bloomberg's direct answer to "what
  happened with this name lately?".
- Earnings-call summaries evolved into Document Search & Analysis / document insights (Q&A over filings, transcripts). [MKT, B2]
- ASKB (beta, Feb 2026): conversational layer over a network of agents using several commercial and open-weight LLMs;
  grounds answers in Bloomberg data with attribution; returns BQL query code with any data analysis so results are
  reproducible in Excel/BQuant; annotated charts; multi-step workflows can be saved, re-run, and shared; users can upload
  PDFs/Word files. [MKT/3P, B3]
- ASKB mobile (Aug 2026): persistent session continues from desktop to phone; synced profile (role, focus area);
  "answer validators" and source attribution; scheduled Morning Reports viewable on both; in development: reading the
  user's worksheets and surfacing the news most relevant to them. [3P, B4]
- Quality: no independent accuracy testing found; all claims vendor-sourced. [INF]

**7. Mobile.** Bloomberg Professional app for Bloomberg Anywhere subscribers: news (TOP, Live Blogs), messaging,
security data, portfolios, worksheets, alerts; bookmarked research and saved searches sync desktop to mobile. [DOC, B7]

**8. Recurring value / pricing.** Messaging network (IB), real-time news, alerts, and now scheduled AI Morning Reports.
No free tier; enterprise sale. [3P, B8]

**9. Weaknesses for retail.** Price, learning curve, jargon. Its AI aims at analysts who already know what to ask. [INF]

**Journeys.**
- J1 (unfamiliar company): DES then page forward, then CN, then GP; now ASKB can answer plain questions with sources. [DOC, B5; MKT, B3]
- J2 (swing thesis): GP charts + EVTS for upcoming catalysts + ALRT on levels. [DOC, B5, B6]
- J3 (sudden move): CN headlines plus the AI Company News summary grouped by topic and timestamped. [MKT, B2]
- J4 (exposure): portfolio functions exist (PORT) but were not documented in sources read; ASKB will read worksheets (in development). [3P, B4; INF]

**What translates to retail.** (a) One loaded ticker shared across every view (Optic's Dossier already does this);
(b) a canonical "description page" with plain paging; (c) timestamped, topic-grouped "what happened" digests tied to
your holdings; (d) AI answers that show their work (BQL code) and sources; (e) saved, re-runnable AI workflows;
(f) scheduled morning report that continues on mobile. [INF]

## 2. Koyfin

Sources (read 2026-10-12): [K1] pricing https://www.koyfin.com/pricing/ ; [K2] Getting started https://www.koyfin.com/help/getting-started-with-koyfin/ ;
[K3] v3.66 Desktop alerts https://www.koyfin.com/help/release-notes/v3-66-desktop-alerts/ ; [K4] alerts feature page https://www.koyfin.com/features/alerts/ ;
[K5] v3.69 Transcript Summaries https://www.koyfin.com/help/release-notes/v3-69-transcript-summaries/ ; [K6] Mobile app features https://www.koyfin.com/help/mobile-app-feautres/ ;
[K7] v3.43 Portfolio Exposures https://www.koyfin.com/help/release-notes/v3-43-portfolio-exposures/ and My Portfolios help https://www.koyfin.com/help/my-portfolios/ ;
[K8] ki-syndikat review https://www.ki-syndikat.de/tools/koyfin/ ; [K9] CFO Club review https://thecfoclub.com/it/tools/recensione-koyfin/ ;
[K10] TraderHQ Koyfin vs FinChat https://traderhq.com/koyfin-vs-finchat/ ; [K11] Koyfin 2026 advisor blog https://www.koyfin.com/blog/best-portfolio-management-software/ .

**1. Audience and promise.** Positioned as the affordable Bloomberg alternative for self-directed investors, students
(schools program), and increasingly RIAs/advisors (advisor tiers are the most expensive). [MKT, K1, K2] Tiering shows
the commercial center of gravity has moved to advisors (client proposals, custodian integrations). [INF, K1]

**2. Compelling workflow.** Dashboards: user-built pages combining watchlists, graphs, news feeds, scatter plots; plus
security "Snapshots" and Bloomberg-style shortcut codes (G = historical graph, DVD, EXP = ETF exposure, A/B relative
performance) reachable from a "/" command bar. [DOC, K2] Screener spans 100K+ securities and 5,900+ filters. [DOC, K2]

**3. Time to first insight.** Right sidebar shows watchlists, movers and news; clicking a ticker loads it; a Data
Dictionary defines metrics; hovering the time dot shows data freshness. [DOC, K2] Reviewers call it intuitive for
experienced analysts but note a learning curve for beginners. [3P, K9] Value is greatest after the user builds dashboards. [INF]

**4. Hierarchy / jargon.** Dense professional vocabulary; jargon is handled by a separate Data Dictionary, not inline.
[DOC, K2] Defaults: prebuilt market dashboards and Financial Analysis templates; customization is the main path. [DOC, K2]
Freshness indicator per ticker is a small, trust-building default worth noting. [DOC, K2]

**5. Workflows.**
- Alerts (v3.66): price, valuation, technical indicator, and document alerts (press releases, news, transcripts,
  filings); can be set on a whole watchlist or portfolio at once; created from charts/snapshots/tables; managed in one
  searchable list; delivered in-app bell, email, and mobile push. Limits: Free 5, Plus 50, Premium 500 (watchlist and
  portfolio alerts at Premium). [DOC, K3, K4]
- Portfolio exposure (v3.43): pie/table breakdown by security, sector, industry, asset class, country; X-ray look-through
  for funds; Holdings Contribution table showing what each holding adds to an exposure; benchmark comparison to flag
  over/under-exposure. [DOC, K7] Risk metrics (beta, alpha, Sharpe, max drawdown, stress tests) for portfolios. [MKT, K11]
- Model portfolios for target allocations with performance and risk metrics (Advisor tiers). [DOC, K1, K2]

**6. AI.** Narrow and embedded, not a chat assistant: v3.69 Transcript Summaries turn any call (earnings, investor
day, M&A) into an overview with a KPI trend table, segment commentary, guidance, risks, and Q&A highlights; "View
Summary" button atop the transcript; unlimited on all paid plans; back to 2015. [DOC, K5] Third parties describe it as a
point feature, not a freely queryable assistant. [3P, K8, K10] No context-aware assistant found. [INF]

**7. Mobile.** iOS/Android app with price and press-release alerts (push + email), configurable watchlist columns,
fundamental graphs, actuals vs consensus; later notes add My Portfolio on mobile and iOS home-screen widgets. [DOC, K6]

**8. Pricing / upgrade triggers.** Free: 2 years financials, 1 year estimates, 2 watchlists, 2 screens, 2 dashboards,
limited snapshots and news, 5 alerts. Plus $39/mo: 10 years data, unlimited lists/screens/dashboards, transcripts,
filings, premium news, AI transcript summaries, 50 alerts. Premium $79/mo: advanced My Portfolio analytics, custom
formulas, 500 alerts. Advisor Core $209, Advisor Pro $299; annual saves up to 30%. [DOC, K1, K3] Upgrade triggers are
count caps (the third watchlist/screen/dashboard, the sixth alert) and history depth (2Y to 10Y). [INF, K1]

**9. Weaknesses.** No synthesis: it shows every number but does not say what matters or why. [INF] No plain-English
layer beyond a glossary; no "why did it move" explanation found. [INF] Beginners face a learning curve. [3P, K9]

**Journeys.**
- J1: Snapshot + FA templates + transcripts + AI transcript summary (paid). [DOC, K2, K5]
- J2: Historical Graph with templates; technical-indicator alerts. [DOC, K2, K3]
- J3: Right-sidebar news and movers; document alerts; no causal explanation layer documented. [DOC, K2, K3; INF]
- J4: Strongest of the five here for self-directed users: exposures with fund X-ray and holdings contribution (Plus/Premium). [DOC, K7]

## 3. TradingView

Sources (read 2026-10-12/13): [T1] pricing https://www.tradingview.com/pricing/ ; [T2] AI Copilot blog (Sep 28, 2026) https://www.tradingview.com/blog/en/ai-copilot-now-on-tradingview-61231/ ;
[T3] Chart Copilot beta blog (Apr 2, 2026) https://www.tradingview.com/blog/en/tradingview-ai-chart-copilot-beta-57730/ ; [T4] AI corporate news blog (Mar 27, 2026) https://www.tradingview.com/blog/en/ai-powered-news-57454/ ;
[T5] Earnings/splits/dividends on chart https://www.tradingview.com/support/solutions/43000494799-how-can-i-enable-disable-colored-circles-of-earnings-splits-or-dividends-on-a-chart/ and economic events https://www.tradingview.com/support/solutions/43000494798-how-can-i-enable-disable-colored-circles-dots-of-economic-events-on-a-chart/ ;
[T6] Follow earnings and news from chart (official TradingView idea) https://www.tradingview.com/chart/AAPL/t2YpB163-How-To-Follow-Earnings-and-News-From-Your-Chart/ ;
[T7] Watchlist alerts https://www.tradingview.com/support/solutions/43000739708-watchlist-alerts-your-trading-edge/ ; [T8] Alerts intro/channels https://www.tradingview.com/support/solutions/43000520149-introduction-to-tradingview-alerts/ ; [T9] notification schedule https://www.tradingview.com/support/solutions/43000787196-notification-schedule-for-alerts/ ;
[T10] Layouts and drawings sync https://www.tradingview.com/support/solutions/43000746975-tradingview-layouts-a-quick-guide/ and https://www.tradingview.com/support/solutions/43000690945-my-drawings-do-not-sync-in-different-devices/ ;
[T11] MCP server beta (Sep 16, 2026) via TradingView News/Crypto Briefing https://www.tradingview.com/news/cryptobriefing:c81f3a880094b:0-tradingview-enables-ai-agent-connectivity-via-mcp-server-in-public-beta/ ;
[T12] Copilot price observation, Kagels https://www.kagels-trading.de/tradingview-ki-copilot/ ; [T13] TradersPost AI features overview https://blog.traderspost.io/article/tradingview-ai-features-chart-copilot-documents-news .

**1. Audience and promise.** Chart-first platform for retail traders across stocks, crypto, FX, futures; massive
community (Ideas, Pine Script indicators). [MKT, T1] Core promise: best-in-class charts anywhere, synced to the cloud. [INF]

**2. Compelling workflow.** Supercharts: open a symbol, add indicators and drawings, set an alert from the chart, get a
push on the phone. Layouts autosave to the cloud; drawings can sync per layout or globally across all charts of a
symbol. [DOC, T10] Community scripts and ideas supply ready-made analysis. [INF]

**3. Time to first insight.** Seconds to a clean chart (no login needed for basic charts). [INF] Interpretation is left
to the user or to community ideas; no plain-English explanation layer on Basic. [INF]

**4. Hierarchy / disclosure.** Chart is the home; news, calendar, watchlist, alerts sit in a right-hand toolbar.
[DOC, T6] Clutter control is built in: earnings/dividend/split labels hide automatically when a chart is heavily
compressed and return on zoom. [DOC, T5] Economic-calendar view has a "high impact only" mode that hides noise. [DOC, T5]

**5. Workflows.**
- "Why did it move": earnings shown as "E" icons on the date axis with estimates on hover, plus dividends, splits,
  optional earnings break lines, and economic events on index/futures/FX charts. [DOC, T5] News is a side panel that
  follows the chart's ticker, not markers on the price line. [OBS of official idea page, T6] So TradingView links
  *scheduled* events to the chart but does not pin *news* to the bar that moved. [INF]
- Alerts: price, technical, indicator/Pine conditions; channels app push, browser toast, email, webhook (paid), sound,
  plain text; alert presets; notification schedules that log off-hours triggers without notifying. [DOC, T8, T9]
- Watchlist alerts: one condition across a list; symbols added later are included automatically; extended hours
  supported for US stocks; per-symbol throttling (15 triggers/3 min). [DOC, T7] Premium/Ultimate only. [DOC, T1]
- AI corporate news (Mar 2026): AI monitors SEC filings (8-K, 10-K/Q, Form 4, 13D, S-1), writes factual sub-minute
  summaries minutes after filing, each with a direct link to the source filing; filter News Flow by watchlist + event
  type (earnings, M&A, management changes, insider trades over $500k, IPOs, ownership changes); save a feed and get
  push alerts. [DOC, T4]
- AI document summaries of 10-K/10-Q/transcripts from June 2024 onward. [3P, T13]
- Screener with AI screener requests metered by plan (100 to 500; mapping to tiers is inferred). [DOC/INF, T1]

**6. AI.** AI Copilot (Sep 2026) is a side-panel assistant in Supercharts that sees the current chart and uses quotes,
indicators, financials, news, earnings, economic calendar and Screener data. It *acts*: switches symbols/layouts, adds
indicators, draws levels/support-resistance/patterns, creates and manages alerts and watchlists, writes and applies Pine
Script with backtest analysis, runs screens. [DOC, T2] Sold as a monthly add-on on top of any paid plan (one user saw
about EUR 8.93/month incl. VAT [3P, T12]); monthly usage cap; not on mobile yet; disclaimer that it can be wrong and is
analysis, not advice. [DOC, T2] Citations not described. [DOC, T2] Earlier browser-extension beta found Pine generation
unreliable. [3P, T13] MCP server beta (Sep 2026) lets paid users connect external AI agents to quotes, screeners,
watchlists, alerts, fundamentals, filings (delayed data). [3P, T11] Portfolio context not mentioned. [DOC, T2]

**7. Mobile.** Full-featured iOS/Android apps; push alerts; the top-left chart of a layout opens first on mobile. [DOC, T8, T10]
Continuity caveat: editing the same layout on several devices can overwrite changes; indicators do not sync between
layouts. [DOC, T10]

**8. Pricing / upgrade triggers (annual billing).** Basic free: 1 chart per tab, 2 indicators per chart, 3 price
alerts, 1 watchlist of 30 symbols, 1 portfolio of 20 holdings, 5K bars, ads. Essential $12.95/mo (5 indicators, 20
price + 20 technical alerts, no ads, webhooks), Plus $29.95 (10 indicators, 100 alerts), Premium $59.95 (25
indicators, 400 alerts, 2 watchlist alerts), Ultimate $199.95 (50 indicators, 1,000 alerts, 15 watchlist alerts).
[DOC, T1] The upgrade moment is hitting the 3rd indicator or 4th alert mid-analysis, and ads; AI is a separate add-on. [INF, T1]

**9. Weaknesses.** Assumes the user already knows TA; fundamentals and "what it does" are thin; the Copilot is paid-on-
paid and desktop-only; nothing explains a move in words for free. [INF; DOC, T2]

**Journeys.**
- J1: Symbol page + financials + AI filing summaries; Copilot can answer questions (paid add-on). [DOC, T2; 3P, T13]
- J2: Best-in-class: multi-timeframe charts, drawings, technical alerts, Copilot drawing levels and writing alerts. [DOC, T2, T8]
- J3: E-icons and calendar events on chart + ticker-following news panel + AI filing news; user still correlates by eye. [DOC, T4, T5, T6]
- J4: Basic portfolio tracking (1 portfolio, 20 holdings free); no exposure X-ray documented. [DOC, T1; INF]

## 4. Finviz (free + Elite)

Sources (read 2026-10-12/13): [F1] homepage https://finviz.com/ (fetched; text) ; [F2] Elite page https://finviz.com/elite ;
[F3] screener https://finviz.com/screener.ashx (fetched) ; [F4] quote page https://finviz.com/quote.ashx?t=AAPL (fetched) and
https://finviz.com/quote.ashx?t=NVDA (loaded in browser pane, no login) ; [F5] map https://finviz.com/map.ashx (loaded in browser pane,
no login; hovered one tile) ; [F6] blog "A New Era for News on Finviz" (Feb 24, 2026) https://finviz.com/blog/a-new-era-for-news-on-finviz ;
[F7] maps KB/blogs https://finviz.com/knowledge-base/market-data-research/maps-groups/introduction-to-maps and https://finviz.com/blog/the-finviz-matrix-market-breadth-visualized/ ;
[F8] Stock Alarm comparison (competitor marketing) https://pro.stockalarm.io/alternative/finviz .

**1. Audience and promise.** Free, fast market scanning for active retail traders; "financial visualizations". Elite
for real-time, charts, alerts, no ads. [MKT, F1, F2]

**2. Compelling workflow.** Home is a one-screen market read: timestamped market recap, breadth (advancers/decliners,
new highs/lows, % above SMA50/200), signal tables where every tag (Top Gainers, Unusual Volume, New High, Upgrades,
Earnings Before/After, Insider Buying, chart patterns) links to a pre-filtered screener, an S&P 500 1-day map tile,
headlines, economic and earnings calendars, insider trades, futures, FX/bonds. [OBS, F1] Signal-to-screener links make
"what's unusual today" one click. [INF]

**3. Time to first insight.** Near zero: no login, the homepage itself answers "what is the market doing and what is
moving". [OBS, F1] A "First Time Here?" guided-tour prompt exists. [OBS, F1]

**4. Hierarchy / jargon.** Dense fixed-order tables, no customization on free. [OBS, F1] Quote page: header, tabs
(Overview, Compare, Short Interest, Financials, Options, Filings), sector/industry tags, Set Alert / Add to Portfolio,
peers and holding ETFs, chart, an ~84-field snapshot grid, analyst rating changes, news, description, insiders. [OBS, F4]
Screener filters have no plain-language explanations. [OBS, F3] Description sits far below the snapshot grid:
numbers first, story last. [OBS, F4]

**5. Workflows.**
- Screener: tabs Descriptive / Fundamental / Technical / News / ETF / All; Signal dropdown (incl. "Major News" and
  pattern scans); 17 result views (Overview, Valuation, Charts, News, Snapshot, Maps, Stats...); 11,727 results by
  default, 20 per page; presets; Export/Alert buttons; several options Elite-only. [OBS, F3]
- Maps: tiles sized by market cap, colored by performance; S&P 500, Dow, Nasdaq 100, Russell 2000, world, ETFs, crypto,
  themes, market-cap and insider maps; Map/Bubbles/Matrix views; a colorblind mode. [OBS, F5; DOC, F7] Intraday and
  real-time maps are Elite. [DOC, F2]
- **"Why Is It Moving" (key finding).** Map onboarding tooltip announces hovering any tile for an AI summary of why it
  moved. [OBS, F5] Hovering AMZN showed a card: industry, date (Oct 13, 2026), a one-line reason (price-target trims by
  two brokers ahead of Q3 earnings), change, and peer moves. [OBS, F5] On the NVDA quote page a timestamped one-line
  headline sits directly above the chart with "More" and thumbs up/down feedback. [OBS, F4] The page data includes a
  `whyMoving` object with headline, bullet summary, a sentiment label, and a catalyst flag. [OBS, F4] Quality issue
  observed: the NVDA headline (a Microsoft in-house chip story) and the three bullets (a geopolitical item and an
  optical-module spec) described different stories, and no source link appeared in that object. [OBS, F4]
- Daily Digest (stock pages + home), Weekly Digest on weekends, Market Pulse real-time feed filterable by % move, and
  screener hover cards showing chart + latest digest headline. [DOC, F6]
- Charts: earnings (E) and dividend (D) markers on the date axis of the daily chart. [OBS, F4]
- Alerts: none on free; Elite has unlimited stock, price, screener, portfolio, and calendar alerts. [DOC, F2]

**6. AI.** Narrow and ambient: one-line "why it moved" per ticker on map hover and above the quote chart, with a
feedback control. [OBS, F4, F5] No assistant, no context awareness of holdings, no visible citations in the observed
summary. [OBS, F4; INF] Elite page mentions exporting data for AI agents; no AI feature listed. [DOC, F2]

**7. Mobile.** Web only; no official native app found (a competitor states alerts are email only, no native app).
[3P, F8; INF]

**8. Pricing / upgrade triggers.** Free: delayed quotes, daily charts only, no alerts, ads, 3 years financials,
50 portfolios x 50 holdings, screener refresh 3 min. Elite $39.50/mo or $299.50/yr ($24.96/mo): real-time incl.
pre/after-hours, intraday and multi-chart layouts, unlimited alerts, export, advanced filters, 8 years financials,
intraday maps, no ads. [DOC, F2] Upsells are everywhere: top banner, Charts and Compare links, Set Alert icon, Stats
view, a modal on each page; interstitial display ads on free pages. [OBS, F1, F3, F4] Upgrade trigger: wanting an
alert, an intraday chart, or real-time data during the session. [INF]

**9. Weaknesses.** No explanations of metrics; ad-heavy; no mobile app; why-it-moved summaries appear to have
headline/bullet mismatches and no sources. [OBS, F3, F4] Portfolio is a tracker, not exposure analysis. [INF, F2]

**Journeys.**
- J1: Quote page snapshot grid, peers, holding ETFs, description; fast for experts, cryptic for novices. [OBS, F4]
- J2: Pattern-signal scans + daily charts free; intraday, alerts, backtests Elite. [OBS, F1; DOC, F2]
- J3: Best free answer of the five: map hover and quote-page one-line "why it moved" plus Major News signal. [OBS, F3, F4, F5]
- J4: Portfolio tracker only; no X-ray documented. [DOC, F2; INF]

## 5. Morningstar Investor (chosen for J4 portfolio exposure; Stock Rover noted)

Chosen over Stock Rover because Morningstar's X-Ray and Stock Intersection are the best-known consumer answers to
"how exposed am I, really?" across stocks and funds. Morningstar.com help pages returned 403 to the fetcher; findings
come from the Investor product page, search-indexed help snippets, and reviews.
Sources (read 2026-10-12/13): [M1] Investor stock-analysis page https://www.morningstar.com/mm/investor/stock-analysis ;
[M2] help-center snippets (X-Ray, portfolio) https://www.morningstar.com/help-center/portfolio/xray and https://www.morningstar.com/help-center/portfolio (search snippets only) ;
[M3] Morningstar "hidden overlap" article https://www.morningstar.com/whats-new/how-to-spot-hidden-overlap-in-your-funds-and-avoid-the-diversification-trap (search snippet) ;
[M4] older Morningstar classroom/article on intersection http://news.morningstar.com/classroom2/course.asp?docId=4433&page=3 and https://www.morningstar.com/articles/607766/caution-beware-of-dangerous-portfolio-intersections (snippets) ;
[M5] Wall Street Survivor review (affiliate) https://www.wallstreetsurvivor.com/?p=11823 ; [M6] Freenance review https://freenance.io/products/morningstar-investor-review-2026-premium-mutual-fund-etf-research/ ;
[M7] Mo chatbot launch coverage (2023) https://www.financial-planning.com/news/morningstar-openai-powered-chatbot-mo-enters-beta-for-financial-advisors-investors ;
[M8] Stock Rover plans https://www.stockrover.com/plans/ .

**1. Audience and promise.** Long-term fundamental investors, especially fund/ETF holders; independent ratings and
fair values. [MKT, M1; 3P, M5]

**2. Compelling workflow.** Link or enter holdings, open X-Ray, then Stock Intersection to see the real underlying
stock exposure across funds and individual positions. [DOC, M2, M3]

**3. Time to first insight.** Fast once holdings are in (linking brokerage accounts is supported). [3P, M5; DOC, M2]
Ratings compress analysis into symbols (stars, moat badge) a novice can read before understanding the method. [INF, M1]

**4. Hierarchy / jargon.** Proprietary shorthand is the hierarchy: star rating = current price vs fair value estimate,
adjusted for the uncertainty rating (bigger discount, more stars); economic moat = wide / narrow / none, from five
named sources (network effects, intangibles, cost advantage, switching costs, efficient scale). [MKT, M1] Each badge
links to a methodology, but the vocabulary still has to be learned. [INF]

**5. Workflows.**
- X-Ray breakdowns: asset class, sector, world regions, fees, stock stats, style box; views show how each security
  contributes to each total. [DOC, M2]
- Stock Intersection: aggregates stock holdings from your mutual funds and individual stocks to reveal overlap; shows
  the dollar value and percent of net assets each underlying stock represents. [DOC, M2, M4] Historically it looked at
  each fund's top 50 holdings only (dated source). [DOC, M4]
- Screeners with 200+ data points incl. fair value and ratings; alerts on price, fundamentals, and rating changes. [3P, M6]
- Charts are basic line charts; no candlesticks or TA; quotes may lag. [3P, M6]

**6. AI.** "Mo" chatbot (beta, 2023) on Investor and pro platforms, built on Morningstar's research library via Azure
OpenAI; summarizes Morningstar's own research in conversation; explicitly not advice. [3P, M7] No 2026 update found.
Not described as holdings-aware. [INF]

**7. Mobile.** Web, iOS, Android; watchlists/portfolios sync; reviewers rate the app weaker than web. [3P, M5]

**8. Pricing / upgrade triggers.** Free site: news, basic quotes and fund data. Investor: $34.95/mo or $249/yr, 7-day
trial: analyst reports, fair values, full X-Ray, screeners. [MKT, M1; 3P, M5] Upgrade trigger: seeing a star/fair value
teaser or wanting X-Ray on your own portfolio. [INF]
Stock Rover (reference): Premium $29/mo annual (2 brokerages linked), Premium Plus $49 (research reports on 7,000+
stocks, fair value, 5 brokerages), Ultimate $79, Ultimate Pro $149. [DOC, M8]

**9. Weaknesses.** Traders underserved (no TA, lagging quotes); tools called cumbersome; not prescriptive; price hard
to justify for casual users or those holding one or two index funds. [3P, M5, M6] Overlap is shown but rarely
translated into "what this means for you if X falls 20%". [INF]

**Journeys.**
- J1: Analyst report + fair value + moat give a fast opinionated take on covered names (~1,000-1,600 stocks; counts vary by source). [MKT, M1; 3P, M5, M6]
- J2: Poor fit (no TA). [3P, M6]
- J3: News and analyst commentary; no documented "why it moved" summary. [MKT, M1; INF]
- J4: The reference implementation: X-Ray + Stock Intersection with per-holding contribution. [DOC, M2, M3]

## Summary table

| Competitor strength | User problem solved | Evidence type + source | Implication for Optic |
|---|---|---|---|
| Finviz map hover + quote-page one-line "why it moved" | "Why is this red/green today?" in one gesture, free | OBS, F4, F5; DOC, F6 | Free "why it moved" is now table stakes. Optic must beat it on trust: cite the source, timestamp, and say when no clear cause exists (Finviz showed headline/bullet mismatch with no source). |
| Finviz signal tables linking to pre-filtered screens | "What is unusual today?" with zero setup | OBS, F1, F3 | Home "What matters today" items should each open the Scan that produced them. |
| TradingView AI Copilot that sees the chart and acts (draws levels, sets alerts, runs screens) | Turning intent into chart actions without menus | DOC, T2 | Milo's propose-then-confirm actions are on par with a paid-on-paid add-on; make that a headline differentiator and keep it free in a limited form. |
| TradingView AI filing news with source link + watchlist/event filters + push | Knowing material filings minutes after they post | DOC, T4 | Optic's what-changed digest should link each item to its 8-K/Form 4/10-Q and allow "only my watchlist, only insider buys" filters. |
| TradingView earnings/dividend/econ events on chart, auto-decluttered | Linking scheduled catalysts to price | DOC, T5 | Put earnings, ex-div, and macro markers on Optic charts, plus the step TV lacks: news pins on the bars that moved. |
| TradingView watchlist alerts (one rule, whole list, auto-includes new symbols) | Monitoring 5-25 names without 25 alerts | DOC, T7 | Optic watches should allow one plain rule on a whole watchlist; competitors paywall this (TV Premium+, Koyfin Premium). |
| Koyfin document alerts (press releases, transcripts, filings) on watchlist/portfolio | "Tell me when my companies publish something" | DOC, K3 | Add "new filing / earnings call / press release" as a watch type, delivered with a one-paragraph summary. |
| Koyfin transcript summaries with KPI trend table, guidance, risks, Q&A | Reading an earnings call in two minutes | DOC, K5 | Optic earnings tab can summarize calls in the same shape but in plain English with "what changed vs last quarter". |
| Koyfin and Morningstar exposure X-ray with per-holding contribution | "Am I more concentrated than I think?" | DOC, K7, M2 | Paper portfolio should show sector/country/top-stock exposure with fund look-through and a plain "your top 3 names are 41% of you" line. |
| Morningstar star/moat/fair-value badges | A novice can read a verdict before the method | MKT, M1 | Optic Score can work the same way only if each badge opens a short "why this score" and a track record; avoid unvalidated precision. |
| Bloomberg ASKB: sources, BQL code, validators, saved re-runnable workflows | Trusting and reusing AI analysis | MKT/3P, B3, B4 | Milo answers should show "computed from" (fields, dates, source) and let users save a prompt as a recurring digest. |
| Bloomberg AI Company News summary, timestamped and grouped by topic, for portfolio names | Catching up on a company fast | MKT, B2 | Dossier news tab should open with a topic-grouped, timestamped digest above the raw list. |
| Bloomberg ASKB desktop-to-mobile session continuity + scheduled Morning Reports | Picking up research on the phone | 3P, B4 | Milo conversations and the daily Read should continue on phone; a scheduled morning email is the obvious missing channel. |
| Count-capped free tiers (TV 2 indicators/3 alerts; Koyfin 2 lists/5 alerts; Finviz no alerts) | n/a (monetization) | DOC, T1, K1, F2 | Upgrade moments cluster on alerts, history depth, real-time, and count caps. Optic can gate depth/volume, not comprehension. |

## Baseline expectations
What a serious user will assume exists, based on all five:
1. A single ticker context shared across chart, news, financials, and alerts (Bloomberg DES/CN/GP; Koyfin snapshots; TV layouts). [DOC, B5, K2, T10]
2. Earnings (and dividend) markers on the price chart, with hover details. [DOC, T5; OBS, F4]
3. A ticker-following news feed beside the chart, and an earnings + economic calendar. [DOC, T6; OBS, F1]
4. Price and technical alerts with push and email; on paid tiers, alerts on whole watchlists. [DOC, T7, T8, K3; DOC, F2]
5. A screener with presets plus one-click "today's movers / unusual volume / new highs" scans. [OBS, F1, F3]
6. A market heatmap sized by market cap, colored by return. [OBS, F5]
7. Portfolio tracking with sector/asset/country breakdowns; on serious tools, fund look-through. [DOC, K7, M2]
8. Some AI summarization of filings, transcripts, or news with links back to the source. [DOC, K5, T4; MKT, B1]
9. Cloud sync to a mobile app with push alerts (Finviz is the exception, web only). [DOC, K6, T8, B7]
10. A visible data-freshness signal (Koyfin time dot; Finviz delayed-quote notice). [DOC, K2; OBS, F1]

## Proven ideas worth adapting
1. **Ambient "why it moved" (Finviz).** Adapt: one sentence on every mover tile, watchlist row, and above the
   Dossier chart, but with a source link, a timestamp, a confidence word ("clear cause" / "likely" / "no clear news,
   moved with sector"), and a sector-relative check. Finviz's observed mismatch is the opening. [OBS, F4, F5]
2. **News pinned to the chart.** Nobody reviewed pins headlines to the bar that moved (TV shows events, not news;
   Finviz shows E/D only). Adapt: mark the day's largest move on the chart with the cause sentence; tap opens sources. [DOC, T5, T6; OBS, F4; INF]
3. **Signals that open the screen behind them (Finviz).** Each "What matters today" card should open the Scan,
   pre-filled and explained. [OBS, F1]
4. **Chart-aware assistant that acts (TV Copilot, Bloomberg ASKB).** Optic already has this in Milo; emphasize
   grounding ("drawn at the 50-day average, 212.40 as of 4:00 PM") and the confirm step. [DOC, T2; MKT, B3]
5. **Show-your-work AI (ASKB BQL code, validators).** Adapt as a collapsible "How Milo got this" listing the computed
   fields, dates, and data source, which also mitigates unlicensed-data and hallucination risk. [MKT, B3; 3P, B4]
6. **Saved, re-runnable AI workflows (ASKB).** Let a user save "my Monday watchlist check" as a scheduled digest; a
   natural paid feature. [MKT, B3]
7. **Document alerts (Koyfin) + AI filing news (TV).** "Alert me when any watchlist name files an 8-K or insider
   buys" with a two-line plain summary and the filing link. [DOC, K3, T4]
8. **Transcript summary template (Koyfin).** KPI trend table, guidance, risks, Q&A highlights, translated into plain
   questions ("Did they raise guidance? What worried analysts?"). [DOC, K5]
9. **Exposure X-ray with contribution (Koyfin/Morningstar).** For paper portfolios: sector, country, top underlying
   stocks including ETF look-through, and a sentence on what drives the risk. [DOC, K7, M2]
10. **Clutter control (TV).** Auto-hide event labels when zoomed out; "high impact only" toggle for macro events;
    this matches Optic's density complaint. [DOC, T5]
11. **Verdict badges with methodology one tap away (Morningstar).** Keep Optic Score but attach "why" and a measured
    history, since Optic has no validated edge yet. [MKT, M1]

## Unserved needs / gaps
1. **Trustworthy free causal explanation.** Finviz's free why-it-moved has no visible sources and showed a headline
   unrelated to its bullets; TradingView and Koyfin leave correlation to the user; Bloomberg's version costs ~$30k. [OBS, F4; DOC, T6; 3P, B8]
2. **Plain-English layer.** Every product handles jargon with glossaries or methodology pages, not inline
   explanation; Koyfin and Finviz are dense, Bloomberg needs training, TV assumes TA literacy. [DOC, K2, B5; OBS, F3; INF]
3. **Free context-aware AI.** TV Copilot is a paid add-on on a paid plan and desktop-only; Bloomberg's is
   institutional; Koyfin's is a transcript button; Finviz has no assistant; Morningstar's Mo is a 2023 beta. [DOC, T2, K5; 3P, M7]
4. **Holdings-aware AI.** None documented reads the user's portfolio to explain impact ("your book fell 1.8%, 70% of
   that from NVDA"); Bloomberg lists it as in development. [3P, B4; INF]
5. **Exposure for stock pickers, explained.** X-ray exists but outputs pies and tables; no one turns concentration into
   a sentence with a scenario. Koyfin puts full analytics at Premium $79; Morningstar at $249/yr. [DOC, K1, K7; MKT, M1]
6. **Free watchlist-wide alerts.** Paywalled at TV Premium ($59.95/mo) and Koyfin Premium; Finviz has no free alerts. [DOC, T1, K3, F2]
7. **Mobile continuity of AI and research.** TV Copilot is not on mobile; Finviz has no app; only Bloomberg syncs AI
   sessions across devices. [DOC, T2; 3P, F8, B4]
8. **Students.** Koyfin courts schools; Bloomberg is taught via certification; nobody teaches concepts in the flow of
   a real ticker for free. [DOC, K2, B5; INF]
