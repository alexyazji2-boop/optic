# Rendered inventory (generated from the 2026-10-29 crawl of 9fa0f36, local server :8250)

One block per route as rendered at 1440x900, for a guest and for the signed-in demo account (owner on that server).
Controls are listed once per distinct label within the page (`#main`), with their kind; the app shell (rail, top bar,
footer) is listed once at the top. Counts are of visible elements after the page settled. Source-level detail
(handlers, states, storage) is in the A to D files beside this one.

## App shell (guest, 1440)

- body: Skip to content; Optic Terminal, Home; Settings; Collapse
- nav.rail-nav: Home; Dossier; Compare; Markets; Discover; Positions; Watchlist
- header.topbar: Search companies, tickers and pages, or ask Milo; Ask Milo; Sign in
- header.ws-head: About Markets at a glance: how to read it, its sou; Ask Milo about Markets at a glance; Markets at a glance options; Refresh; About Market conditions: how to read it, its sourc; Ask Milo about Market conditions; Market conditions options; About Expected move: how to read it, its source an; Ask Milo about Expected move; Expected move options; About Sector heatmap: how to read it, its source a; Ask Milo about Sector heatmap; Sector heatmap options; Follows SPY; About Quote and chart: how to read it, its source ; Ask Milo about Quote and chart; Quote and chart options; Keep SPY here when the link changes; About Watchlist: how to read it, its source and ho; Ask Milo about Watchlist; Watchlist options; About Economic calendar: how to read it, its sourc; Ask Milo about Economic calendar; Economic calendar options; About Earnings this week: how to read it, its sour; Ask Milo about Earnings this week; Earnings this week options; About What matters today: how to read it, its sour; Ask Milo about What matters today; What matters today options; About Market news: how to read it, its source and ; Ask Milo about Market news; Market news options; About Optic Desk: how to read it, its source and h; Ask Milo about Optic Desk; Optic Desk options; About Moved most this month: how to read it, its s; Ask Milo about Moved most this month; Moved most this month options
- #legal-footer: Report a problem; Full disclaimer; Terms of use; Privacy policy; Use the classic app

### `#/accounts` (accounts)

#### guest: 20 words, 20 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Accounts
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 90 words, 25 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 8 API paths
- Headings: Accounts
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (1 distinct): Collapse
- Table in "": 1 rows; columns: Person, Joined, Last active, Last sign-in, Signs in with, Status
- API: /api/admin/accounts, /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/alerts` (alerts)

#### guest: 273 words, 25 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 6 API paths
- Headings: Watchlist , Alerts / Your alerts / What fired / Signal history / From Optic's paper book
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in or create an account
- button (4 distinct): Collapse; New alert; RSI; Set a swing setup alert
- API: /api/ai-allowance, /api/alerts, /api/auth/me, /api/health, /api/session, /api/watches/catalogue
- Notes shown: No alerts yet A price level, a day's move, an RSI line, a change in Optic's stance or an e / A history needs an account Signed in, Optic checks your alerts on its own schedule and kee / No signals yet One is recorded when a swing-setup alert of yours fires on a completed cand / Nothing from the book yet A new paper trade idea, a closed position, a confirmed pattern o
#### signed in: 379 words, 32 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 11 API paths
- Headings: Watchlist , Alerts / Your alerts / What fired / Signal history / From Optic's paper book
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; AAPL; Brokerage
- button (5 distinct): Collapse; New alert; All 2; Price 2; Set a swing setup alert
- input(checkbox) (1 distinct): on
- summary (1 distinct): These stay in this inbox: nothing here is emailed yet
- Folds: These stay in this inbox: nothing here is emailed yet
- API: /api/ai-allowance, /api/alerts, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/signals, /api/watches, /api/watches/catalogue, /api/watches/hits, /api/watchlists
- Notes shown: No alerts yet A price level, a day's move, an RSI line, a change in Optic's stance or an e / No signals yet One is recorded when a swing-setup alert of yours fires on a completed cand / Nothing from the book yet A new paper trade idea, a closed position, a confirmed pattern o

### `#/analysts` (analysts)

#### guest: 2648 words, 245 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 5 API paths
- Headings: Discover , Analysts / Analyst actions
- a (107 distinct): Skip to content; Optic Terminal, Home; Settings; BA; PYPL; STX; SHOP; HOOD; V; SOFI; AMD; XYZ; PFG; IDXX; EBAY; DDOG; MELI; PCTY; GLXY; CDNS; AVGO; PLTR; RMBS; TRMB; THRM; ROST; TPG; CG; FISV; VRNS; CDNA; CAI; NTRA; GH; ABNB; MTCH; CEG; UNH; AMKR; CSX; OLLI; CTSH; FSLR; TLN; MRNA ...
- button (22 distinct): Collapse; Search; All; Upgrades; Downgrades; Initiations; Target raised; Target lowered; Any; Buy; Hold; Sell; Day; 7 days; 30 days; Date; Symbol; Analyst; Prior target; Target; Action; Rating
- input(text) (1 distinct): Symbol, such as NVDA
- Table in "Analyst actions": 200 rows; columns: Date, Symbol, Analyst, Prior target, Target, Action, Rating
- API: /api/ai-allowance, /api/analysts/latest, /api/auth/me, /api/health, /api/session
#### signed in: 2655 words, 247 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Discover , Analysts / Analyst actions
- a (88 distinct): Skip to content; Optic Terminal, Home; Settings; AAL; TLN; CEG; REGN; ADP; BA; NXPI; CHKP; PYPL; HAS; KMB; STX; APP; SHOP; CAKE; ROIV; MANH; UTHR; HOOD; PCAR; LPLA; ENPH; CSGP; V; JAZZ; FFIV; GEHC; SOFI; HBAN; FCNCA; RGEN; PFG; BIIB; WWD; KTOS; FTAI; TRI; TEAM; DDOG; MTCH; FORM; FROG ...
- button (22 distinct): Collapse; Search; All; Upgrades; Downgrades; Initiations; Target raised; Target lowered; Any; Buy; Hold; Sell; Day; 7 days; 30 days; Date; Symbol; Analyst; Prior target; Target; Action; Rating
- input(text) (1 distinct): Symbol, such as NVDA
- Table in "Analyst actions": 200 rows; columns: Date, Symbol, Analyst, Prior target, Target, Action, Rating
- API: /api/ai-allowance, /api/analysts/latest, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watchlists

### `#/ZZZZQ` (bad-ticker)

#### guest: 54 words, 37 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 1212 ms, 17 API paths
- Headings: ZZZZQ , Overview
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Go to Home
- button (2 distinct): Collapse; Search for the company
- Folds: 
- API: /api/ai-allowance, /api/auth/me, /api/digest/ZZZZQ, /api/earnings/ZZZZQ, /api/extras/ZZZZQ, /api/fair-value/ZZZZQ, /api/framework/ZZZZQ, /api/health, /api/logo/ZZZZQ, /api/longterm/ZZZZQ, /api/quote/ZZZZQ, /api/segments/ZZZZQ, /api/session, /api/session/ZZZZQ, /api/stage, /api/ticker/ZZZZQ, /api/validation
- Notes shown: Optic has no listing for ZZZZQ No quote and no price history came back for this symbol. It
#### signed in: 54 words, 39 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 619 ms, 22 API paths
- Headings: ZZZZQ , Overview
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Go to Home
- button (2 distinct): Collapse; Search for the company
- Folds: 
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/build, /api/digest/ZZZZQ, /api/earnings/ZZZZQ, /api/extras/ZZZZQ, /api/fair-value/ZZZZQ, /api/framework/ZZZZQ, /api/health, /api/logo/ZZZZQ, /api/longterm/ZZZZQ, /api/quote/ZZZZQ, /api/segments/ZZZZQ, /api/session, /api/session/ZZZZQ, /api/stage, /api/theses, /api/ticker/ZZZZQ, /api/validation, /api/watches/hits, /api/watchlists
- Notes shown: Optic has no listing for ZZZZQ No quote and no price history came back for this symbol. It

### `#/brokerage/connections` (brk-connections)

#### guest: 207 words, 21 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 5 API paths
- Headings: Brokerage / Link your brokerage / What Optic can and cannot see
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session
#### signed in: 238 words, 23 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 7 API paths
- Headings: Brokerage / Connections / What Optic can and cannot see
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (2 distinct): Collapse; Connect a brokerage
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/brokerage/events` (brk-events)

#### guest: 207 words, 21 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 5 API paths
- Headings: Brokerage / Link your brokerage / What Optic can and cannot see
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session
#### signed in: 238 words, 23 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 6 API paths
- Headings: Brokerage / Connections / What Optic can and cannot see
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (2 distinct): Collapse; Connect a brokerage
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watchlists

### `#/brokerage/holdings` (brk-holdings)

#### guest: 207 words, 21 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 5 API paths
- Headings: Brokerage / Link your brokerage / What Optic can and cannot see
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session
#### signed in: 238 words, 23 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 7 API paths
- Headings: Brokerage / Connections / What Optic can and cannot see
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (2 distinct): Collapse; Connect a brokerage
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/brokerage/overview` (brk-overview)

#### guest: 207 words, 21 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 5 API paths
- Headings: Brokerage / Link your brokerage / What Optic can and cannot see
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session
#### signed in: 238 words, 23 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 7 API paths
- Headings: Brokerage / Connections / What Optic can and cannot see
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (2 distinct): Collapse; Connect a brokerage
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/brokerage/performance` (brk-performance)

#### guest: 207 words, 21 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 5 API paths
- Headings: Brokerage / Link your brokerage / What Optic can and cannot see
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session
#### signed in: 238 words, 23 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 6 API paths
- Headings: Brokerage / Connections / What Optic can and cannot see
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (2 distinct): Collapse; Connect a brokerage
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watchlists

### `#/BRK.B` (brkb)

#### guest: 1357 words, 174 visible controls, 6 tables, 1 charts, 21 folds (0 open), settle 4222 ms, 17 API paths
- Headings: BRK-B Berkshire Hathaway Inc. , Overview / What Berkshire Hathaway Inc. does / The past year / Four questions, answered separately / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Key figures / Bull case and bear case / Bull case / Bear case / Taken together / What changed lately / Your thesis check / What should I look at next? / COMING UP / RESEARCH STEPS / More on Berkshire Hathaway Inc. / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (36 distinct): Skip to content; Optic Terminal, Home; Settings; Berkshire Hathaway Earnings Preview: What to Expect; Berkshire Hathaway (BRK-B) Starts Spending Its Cash, but Is ; The Zacks Analyst Blog Highlights Apple, Berkshire Hathaway,; Berkshire Hathaway Specialty Insurance Promotes Virginie Pel; UBS Adjusts Price Target on Berkshire Hathaway to $628 From ; UBS Adjusts Price Target on Berkshire Hathaway to $942,405 F; All headlines on News; Open Financials; Open Investing; Open the chart; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Profitable: about 16 cents of profit per dolla; Evidence for: Beat analysts' earnings estimates in 5 of the ; Evidence for: Holds more cash than debt ($244.2B net cash); Evidence for: Share price up 11% over the period shown; Evidence for: Earnings report on Nov 7, in 9 days; Evidence for: Priced above its own history: 13.6 times earni; Evidence for: Revenue fell 3.2% in the latest fiscal year; Evidence for: Net income fell 24.8% in the latest fiscal yea; Review past results before the report on Nov 7 Earnings →; Check the statements behind the weaker figures Financials →; See how the price compares with its own valuation history In; Read the 12 latest headlines News →; 8-K; 10-Q; Chart89%of its 52-week range; OptionsBullishmoderate conviction; EarningsNov 7, 2026in 9 days; Financials10.0%revenue growth, 22.3% margin; News12headlines, neutral; Investing13.6trailing P/E, valuation and holding case; All 12 headlines
- button (41 distinct): Collapse; Fold What the company does; Market value; Fold The past year; 3M; 6M; 1Y; Measure between two dates; Fold Four questions, answered separately; Fold Optic Score; Fold Key figures; Market cap; P/E (trailing); Revenue growth, last quarter; Profit margin, 12 months; 52-week high; 52-week low; Fold Bull case and bear case; Fold Taken together; Fold What changed lately; Ask Milo about this; Oct 28 No meaningful change: moved -0.5% (within its usual r; Oct 27 Berkshire Hathaway Earnings Preview: What to Expect B; Oct 26 The Zacks Analyst Blog Highlights Apple, Berkshire Ha; Oct 26 Berkshire Hathaway Specialty Insurance Promotes Virgi; Fold Your thesis check; Start a thesis check; Fold What should I look at next?; Ask Milo a question about BRK-B Ask Milo →; Fold More on the company; P/E (forward); EPS (trailing); EPS (forward); Open price; High last session; Low last session; Volume; Average volume; Beta; Short interest; Days to cover
- button[switch] (1 distinct): Show advanced analysis
- summary (13 distinct): What it does, in full; Latest headlines neutral; The 4 marked dates; Show the figures; Why; How this is calculated; Show the case for and against (4 for, 4 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key s; Read more; 8 sources; How this works
- g[button] (4 distinct): Earnings report, Nov 1, 2025; Earnings report, Feb 28, 2026; Earnings report, May 2, 2026; Earnings report, Aug 8, 2026
- Table in "The 4 marked dates": 4 rows; columns: Date, Marked, What
- Table in "Why": 7 rows; columns: 
- Table in "Why": 5 rows; columns: 
- Table in "Why": 3 rows; columns: 
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 3 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; What it does, in full; Latest headlines neutral; The 4 marked dates; Show the figures; Why; Show the figures; Why; Show the figures; Why; Why; How this is calculated; How this is calculated; Show the case for and against (4 for, 4 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key statistics,; Read more; 8 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/digest/BRK-B, /api/earnings/BRK-B, /api/extras/BRK-B, /api/fair-value/BRK-B, /api/framework/BRK-B, /api/health, /api/logo/BRK-B, /api/longterm/BRK-B, /api/quote/BRK-B, /api/segments/BRK-B, /api/session, /api/session/BRK-B, /api/stage, /api/ticker/BRK-B, /api/validation
#### signed in: 1357 words, 210 visible controls, 6 tables, 1 charts, 21 folds (0 open), settle 686 ms, 21 API paths
- Headings: BRK-B Berkshire Hathaway Inc. , Overview / What Berkshire Hathaway Inc. does / The past year / Four questions, answered separately / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Key figures / Bull case and bear case / Bull case / Bear case / Taken together / What changed lately / Your thesis check / What should I look at next? / COMING UP / RESEARCH STEPS / More on Berkshire Hathaway Inc. / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (36 distinct): Skip to content; Optic Terminal, Home; Settings; Berkshire Hathaway Earnings Preview: What to Expect; Berkshire Hathaway (BRK-B) Starts Spending Its Cash, but Is ; The Zacks Analyst Blog Highlights Apple, Berkshire Hathaway,; Berkshire Hathaway Specialty Insurance Promotes Virginie Pel; UBS Adjusts Price Target on Berkshire Hathaway to $628 From ; UBS Adjusts Price Target on Berkshire Hathaway to $942,405 F; All headlines on News; Open Financials; Open Investing; Open the chart; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Profitable: about 16 cents of profit per dolla; Evidence for: Beat analysts' earnings estimates in 5 of the ; Evidence for: Holds more cash than debt ($244.2B net cash); Evidence for: Share price up 11% over the period shown; Evidence for: Earnings report on Nov 7, in 9 days; Evidence for: Priced above its own history: 13.6 times earni; Evidence for: Revenue fell 3.2% in the latest fiscal year; Evidence for: Net income fell 24.8% in the latest fiscal yea; Review past results before the report on Nov 7 Earnings →; Check the statements behind the weaker figures Financials →; See how the price compares with its own valuation history In; Read the 12 latest headlines News →; 8-K; 10-Q; Chart89%of its 52-week range; OptionsBullishmoderate conviction; EarningsNov 7, 2026in 9 days; Financials10.0%revenue growth, 22.3% margin; News12headlines, neutral; Investing13.6trailing P/E, valuation and holding case; All 12 headlines
- button (63 distinct): Collapse; Fold What the company does; Market value; Fold The past year; 3M; 6M; 1Y; dividend; Measure between two dates; EPS; Fold Four questions, answered separately; Revenue; Net income; Net margin; Return on equity; operating margin; revenue; Balance sheet; liquidity; Dilution; P/E; Free cash flow; EMA; guidance; consensus; Guidance; Fold Optic Score; forward P/E; Fold Key figures; Market cap; P/E (trailing); Revenue growth, last quarter; Profit margin, 12 months; 52-week high; 52-week low; Fold Bull case and bear case; Fold Taken together; Fold What changed lately; Ask Milo about this; Oct 28 No meaningful change: moved -0.5% (within its usual r; Oct 27 Berkshire Hathaway Earnings Preview: What to Expect B; Oct 26 The Zacks Analyst Blog Highlights Apple, Berkshire Ha; Oct 26 Berkshire Hathaway Specialty Insurance Promotes Virgi; Fold Your thesis check; Start a thesis check ...
- button[switch] (1 distinct): Show advanced analysis
- summary (13 distinct): What it does, in full; Latest headlines neutral; The 4 marked dates; Show the figures; Why; How this is calculated; Show the case for and against (4 for, 4 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key s; Read more; 8 sources; How this works
- g[button] (4 distinct): Earnings report, Nov 1, 2025; Earnings report, Feb 28, 2026; Earnings report, May 2, 2026; Earnings report, Aug 8, 2026
- Table in "The 4 marked dates": 4 rows; columns: Date, Marked, What
- Table in "Why": 7 rows; columns: 
- Table in "Why": 5 rows; columns: 
- Table in "Why": 3 rows; columns: 
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 3 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; What it does, in full; Latest headlines neutral; The 4 marked dates; Show the figures; Why; Show the figures; Why; Show the figures; Why; Why; How this is calculated; How this is calculated; Show the case for and against (4 for, 4 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key statistics,; Read more; 8 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/digest/BRK-B, /api/earnings/BRK-B, /api/extras/BRK-B, /api/fair-value/BRK-B, /api/framework/BRK-B, /api/health, /api/logo/BRK-B, /api/longterm/BRK-B, /api/quote/BRK-B, /api/segments/BRK-B, /api/session, /api/session/BRK-B, /api/stage, /api/theses, /api/ticker/BRK-B, /api/validation, /api/watches/hits, /api/watchlists

### `#/brokerage` (brokerage)

#### guest: 207 words, 21 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 5 API paths
- Headings: Brokerage / Link your brokerage / What Optic can and cannot see
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session
#### signed in: 238 words, 23 visible controls, 0 tables, 0 charts, 1 folds (1 open), settle 0 ms, 6 API paths
- Headings: Brokerage / Connections / What Optic can and cannot see
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (2 distinct): Collapse; Connect a brokerage
- summary (1 distinct): What Optic can and cannot see
- Folds: [open] What Optic can and cannot see
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watchlists

### `#/BTC-USD` (btc)

#### guest: 1121 words, 131 visible controls, 3 tables, 1 charts, 14 folds (0 open), settle 3269 ms, 18 API paths
- Headings: BTC-USD Bitcoin USD , Overview / What Bitcoin USD does / The past year / Four questions, answered separately / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Key figures / Bull case and bear case / Bull case / Bear case / Taken together / What changed lately / Your thesis check / What should I look at next? / COMING UP / RESEARCH STEPS / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (25 distinct): Skip to content; Optic Terminal, Home; Settings; BTC USD Outlook: Thailand Opens Bitcoin ETF Route on Oct 16; BTC USD Analysis: Oil, Fed and Senate Uncertainty Weigh on B; BTC USD Price Prediction: Can Bitcoin Hold $64,000 Before We; Bitcoin ETFs Own Just 8.5% of BTC as IBIT Ends a Two-Day Out; Bitcoin Price Today: US Money Supply Hits $23.3Tn to Why is ; Bitcoin ETF News: BTC USD Weekly Surge Comes as ETF Flows Re; All headlines on News; Open the chart; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Trading 27% below its highest close of the per; Read the full financial statements Financials →; See how the price compares with its own valuation history In; Read the 7 latest headlines News →; Compare BTC-USD side by side with a competitor Compare →; Chart40%of its 52-week range; OptionsLeaning bearishlow conviction; Earningsn/ano date published; Financialsn/arevenue growth; News7headlines, neutral; Investingn/atrailing P/E, valuation and holding case; All 7 headlines
- button (29 distinct): Collapse; Fold What the company does; Market value; Fold The past year; 3M; 6M; 1Y; Measure between two dates; Fold Four questions, answered separately; Fold Optic Score; Fold Key figures; Market cap; 52-week high; 52-week low; Fold Bull case and bear case; Fold Taken together; Fold What changed lately; Ask Milo about this; Oct 28 The feed's newest completed candle is Oct 27, 2026, o; Oct 27 Bitcoin ETFs Own Just 8.5% of BTC as IBIT Ends a Two-; Fold Your thesis check; Start a thesis check; Fold What should I look at next?; Ask Milo a question about BTC-USD Ask Milo →; Open price; High last session; Low last session; Volume; Average volume
- button[switch] (1 distinct): Show advanced analysis
- summary (10 distinct): Latest headlines neutral; Why; Show the figures; How this is calculated; Show the case for and against (0 for, 1 against); What has been moving it recently; Advanced research Optic's short-term signal score, all key s; Read more; 2 sources; How this works
- Table in "Why": 8 rows; columns: 
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 4 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; Latest headlines neutral; Why; Show the figures; Why; How this is calculated; How this is calculated; Show the case for and against (0 for, 1 against); What has been moving it recently; Advanced research Optic's short-term signal score, all key statistics,; Read more; 2 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/build, /api/digest/BTC-USD, /api/earnings/BTC-USD, /api/extras/BTC-USD, /api/fair-value/BTC-USD, /api/framework/BTC-USD, /api/health, /api/logo/BTC-USD, /api/longterm/BTC-USD, /api/quote/BTC-USD, /api/segments/BTC-USD, /api/session, /api/session/BTC-USD, /api/stage, /api/ticker/BTC-USD, /api/validation
#### signed in: 1121 words, 133 visible controls, 3 tables, 1 charts, 14 folds (0 open), settle 1263 ms, 20 API paths
- Headings: BTC-USD Bitcoin USD , Overview / What Bitcoin USD does / The past year / Four questions, answered separately / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Key figures / Bull case and bear case / Bull case / Bear case / Taken together / What changed lately / Your thesis check / What should I look at next? / COMING UP / RESEARCH STEPS / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (25 distinct): Skip to content; Optic Terminal, Home; Settings; BTC USD Outlook: Thailand Opens Bitcoin ETF Route on Oct 16; BTC USD Analysis: Oil, Fed and Senate Uncertainty Weigh on B; BTC USD Price Prediction: Can Bitcoin Hold $64,000 Before We; Bitcoin ETFs Own Just 8.5% of BTC as IBIT Ends a Two-Day Out; Bitcoin Price Today: US Money Supply Hits $23.3Tn to Why is ; Bitcoin ETF News: BTC USD Weekly Surge Comes as ETF Flows Re; All headlines on News; Open the chart; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Trading 27% below its highest close of the per; Read the full financial statements Financials →; See how the price compares with its own valuation history In; Read the 7 latest headlines News →; Compare BTC-USD side by side with a competitor Compare →; Chart40%of its 52-week range; OptionsLeaning bearishlow conviction; Earningsn/ano date published; Financialsn/arevenue growth; News7headlines, neutral; Investingn/atrailing P/E, valuation and holding case; All 7 headlines
- button (29 distinct): Collapse; Fold What the company does; Market value; Fold The past year; 3M; 6M; 1Y; Measure between two dates; Fold Four questions, answered separately; Fold Optic Score; Fold Key figures; Market cap; 52-week high; 52-week low; Fold Bull case and bear case; Fold Taken together; Fold What changed lately; Ask Milo about this; Oct 28 The feed's newest completed candle is Oct 27, 2026, o; Oct 27 Bitcoin ETFs Own Just 8.5% of BTC as IBIT Ends a Two-; Fold Your thesis check; Start a thesis check; Fold What should I look at next?; Ask Milo a question about BTC-USD Ask Milo →; Open price; High last session; Low last session; Volume; Average volume
- button[switch] (1 distinct): Show advanced analysis
- summary (10 distinct): Latest headlines neutral; Why; Show the figures; How this is calculated; Show the case for and against (0 for, 1 against); What has been moving it recently; Advanced research Optic's short-term signal score, all key s; Read more; 2 sources; How this works
- Table in "Why": 8 rows; columns: 
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 4 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; Latest headlines neutral; Why; Show the figures; Why; How this is calculated; How this is calculated; Show the case for and against (0 for, 1 against); What has been moving it recently; Advanced research Optic's short-term signal score, all key statistics,; Read more; 2 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/digest/BTC-USD, /api/earnings/BTC-USD, /api/extras/BTC-USD, /api/fair-value/BTC-USD, /api/framework/BTC-USD, /api/health, /api/logo/BTC-USD, /api/longterm/BTC-USD, /api/quote/BTC-USD, /api/segments/BTC-USD, /api/session, /api/session/BTC-USD, /api/stage, /api/theses, /api/ticker/BTC-USD, /api/validation, /api/watchlists

### `#/compare` (compare)

#### guest: 50 words, 27 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Compare
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (7 distinct): Collapse; Compare; Add ticker; BTC-USD; BRK-B; SPY; NVDA
- input(text) (1 distinct): A ticker, or a company name
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 50 words, 29 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Compare
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (7 distinct): Collapse; Compare; Add ticker; BTC-USD; BRK-B; SPY; NVDA
- input(text) (1 distinct): A ticker, or a company name
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/compare?t=NVDA,MSFT` (compare-2)

#### guest: 1241 words, 30 visible controls, 1 tables, 1 charts, 0 folds (0 open), settle 14467 ms, 5 API paths
- Headings: Compare / Optic's take / How they have moved / Where each name leads / Swing setup 1–8 weeks / Position setup several weeks to several months / Long-term trend multi-year / Side by side
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; NVDA; MSFT
- button (8 distinct): Collapse; Compare; Add ticker; BTC-USD; BRK-B; SPY; Ask Milo about this comparison; Measure between two dates
- input(text) (1 distinct): A ticker, or a company name
- Table in "Side by side": 31 rows; columns: Metric, NVDA NVIDIA Corporation Technolo, MSFT Microsoft Corporation Techn
- Charts: How they have moved 1054x240
- API: /api/ai-allowance, /api/auth/me, /api/compare, /api/health, /api/session
#### signed in: 1241 words, 38 visible controls, 1 tables, 1 charts, 0 folds (0 open), settle 0 ms, 8 API paths
- Headings: Compare / Optic's take / How they have moved / Where each name leads / Swing setup 1–8 weeks / Position setup several weeks to several months / Long-term trend multi-year / Side by side
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; NVDA; MSFT
- button (12 distinct): Collapse; Compare; Add ticker; BTC-USD; BRK-B; SPY; RSI; relative strength; Ask Milo about this comparison; Measure between two dates; Implied volatility; Forward P/E
- input(text) (1 distinct): A ticker, or a company name
- Table in "Side by side": 31 rows; columns: Metric, NVDA NVIDIA Corporation Technolo, MSFT Microsoft Corporation Techn
- Charts: How they have moved 1054x240
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/compare, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/dossier` (dossier-start)

#### guest: 41 words, 25 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Dossier / Well-known names
- a (7 distinct): Skip to content; Optic Terminal, Home; Settings; AAPL Apple; NVDA NVIDIA; MSFT Microsoft; SPY S&P 500 fund
- button (2 distinct): Collapse; Open
- input(text) (1 distinct): Search a company, fund or ticker
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 41 words, 30 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 14 API paths
- Headings: Dossier / Main Watchlist / Well-known names
- a (10 distinct): Skip to content; Optic Terminal, Home; Settings; AAPL; TSLA; SPY; QQQ; NVDA; PCRX; MSFT Microsoft
- button (2 distinct): Collapse; Open
- input(text) (1 distinct): Search a company, fund or ticker
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/logo/AAPL, /api/logo/MSFT, /api/logo/NVDA, /api/logo/PCRX, /api/logo/QQQ, /api/logo/SPY, /api/logo/TSLA, /api/session, /api/watches/hits, /api/watchlists

### `#/earnings?week=1` (earnings-next)

#### guest: 9 words, 22 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 30615 ms, 5 API paths
- Headings: Earnings next week
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/earnings-week, /api/health, /api/session
#### signed in: 383 words, 60 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 8 API paths
- Headings: Earnings next week / Monday 2 6 reporting / Tuesday 3 8 reporting / Wednesday 4 9 reporting / Thursday 5 6 reporting / Friday 6 None
- a (32 distinct): Skip to content; Optic Terminal, Home; Settings; AAPL Apple Inc.; GRAB Grab Holdings Limited; ON ON Semiconductor Corporation; PLTR Palantir Technologies Inc.; ROKU Roku, Inc.; VRTX Vertex Pharmaceuticals Incorporated; AMD Advanced Micro Devices, Inc.; AMGN Amgen Inc.; ANET Arista Networks, Inc.; DUOL Duolingo, Inc.; MPC Marathon Petroleum Corporation; PFE Pfizer Inc.; SHOP Shopify Inc.; SMCI Super Micro Computer, Inc.; APP AppLovin Corporation; ARM Arm Holdings plc; CAVA CAVA Group, Inc.; CVS CVS Health Corporation; DDOG Datadog, Inc.; ELF e.l.f. Beauty, Inc.; MCD McDonald's Corporation; QCOM QUALCOMM Incorporated; UBER Uber Technologies, Inc.; ABNB Airbnb, Inc.; AFRM Affirm Holdings, Inc.; COP ConocoPhillips; DKNG DraftKings Inc.; IONQ IonQ, Inc.; U Unity Software Inc.
- button (5 distinct): Collapse; EPS; revenue; consensus; Consensus
- summary (1 distinct): How this works
- Folds: How this works
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings-week, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/earnings` (earnings-week)

#### guest: 487 words, 61 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 5 API paths
- Headings: Earnings this week / Monday 26 1 reporting / Tuesday 27 4 reporting / Wednesday 28 9 reporting / Thursday 29 Today 14 reporting / Friday 30 4 reporting
- a (35 distinct): Skip to content; Optic Terminal, Home; Settings; VZ Verizon Communications Inc.; HOOD Robinhood Markets, Inc.; KO The Coca-Cola Company; PYPL PayPal Holdings, Inc.; SOFI SoFi Technologies, Inc.; GOOGL Alphabet Inc.; MSFT Microsoft Corporation; CMG Chipotle Mexican Grill, Inc.; F Ford Motor Company; FDX FedEx Corporation; KLAC KLA Corporation; NOW ServiceNow, Inc.; PSX Phillips 66; VRT Vertiv Holdings Co; AMZN Amazon.com, Inc.; LLY Eli Lilly and Company; MA MA; BMY Bristol-Myers Squibb Company; CAT Caterpillar Inc.; COIN Coinbase Global, Inc.; GILD Gilead Sciences, Inc.; INTC Intel Corporation; LIN Linde plc; MRK Merck & Co., Inc.; MSTR Strategy Inc; RBLX Roblox Corporation; RIVN Rivian Automotive, Inc.; SBUX Starbucks Corporation; XOM ExxonMobil Holdings Corporation; ABBV AbbVie Inc.; CVX Chevron Corporation; REGN Regeneron Pharmaceuticals, Inc.
- button (6 distinct): Collapse; EPS; Revenue; consensus; revenue; Consensus
- summary (1 distinct): How this works
- Folds: How this works
- API: /api/ai-allowance, /api/auth/me, /api/earnings-week, /api/health, /api/session
#### signed in: 487 words, 57 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 7 API paths
- Headings: Earnings this week / Monday 26 1 reporting / Tuesday 27 4 reporting / Wednesday 28 9 reporting / Thursday 29 Today 14 reporting / Friday 30 4 reporting
- a (35 distinct): Skip to content; Optic Terminal, Home; Settings; VZ Verizon Communications Inc.; HOOD Robinhood Markets, Inc.; KO The Coca-Cola Company; PYPL PayPal Holdings, Inc.; SOFI SoFi Technologies, Inc.; GOOGL Alphabet Inc.; MSFT Microsoft Corporation; CMG Chipotle Mexican Grill, Inc.; F Ford Motor Company; FDX FedEx Corporation; KLAC KLA Corporation; NOW ServiceNow, Inc.; PSX Phillips 66; VRT Vertiv Holdings Co; AMZN Amazon.com, Inc.; LLY Eli Lilly and Company; MA MA; BMY Bristol-Myers Squibb Company; CAT Caterpillar Inc.; COIN Coinbase Global, Inc.; GILD Gilead Sciences, Inc.; INTC Intel Corporation; LIN Linde plc; MRK Merck & Co., Inc.; MSTR Strategy Inc; RBLX Roblox Corporation; RIVN Rivian Automotive, Inc.; SBUX Starbucks Corporation; XOM ExxonMobil Holdings Corporation; ABBV AbbVie Inc.; CVX Chevron Corporation; REGN Regeneron Pharmaceuticals, Inc.
- button (1 distinct): Collapse
- summary (1 distinct): How this works
- Folds: How this works
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings-week, /api/health, /api/session, /api/watchlists

### `#/explore` (explore)

#### guest: 1121 words, 84 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 11 API paths
- Headings: Discover , Explore / Start with a question / Which stocks have moved the most? / Which stocks are trading unusually heavily? / Which stocks have a steady upward trend? / What is worth a look today / Every screen / Market movers / Momentum leaders / Volume / Trend structure / High risk / Relative performance / Sectors / Cross-asset
- a (60 distinct): Skip to content; Optic Terminal, Home; Settings; NTSK; LQDA; AVBP; See the full list; THRM; PCRX; TECH; MKTX; BWIN; Market movers; Top gainers with volume; Top decliners with volume; Momentum leaders; At 52-week highs; Extended. Stretched from the mean; Unusual volume; Volume leaders; Pullback in an uptrend; Steady uptrends; Below a falling 200-day; High-risk swings, upside; High-risk swings, downside; Top 5% of their peers; Bottom 5% of their peers; Just broke into the top 20%; Just dropped into the bottom 20%; XLK; XLF; XLV; XLY; XLP; XLE; XLI; XLB; XLU; XLRE; XLC; The sector board and rotation are on Macro; US 3M −1.11% 2.4×; TLT −0.78% 1.3×; US 10Y +1.04% 1.1×; Russell 2000 futures +0.72% 0.8× ...
- button (2 distinct): Collapse; Ask Milo about the biggest move
- Table in "Sectors": 11 rows; columns: Sector, Week, Month, Read
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/home, /api/scanners, /api/scanners/groups, /api/scanners/movers, /api/scanners/steady, /api/scanners/volume, /api/sectors/board, /api/session
#### signed in: 1121 words, 86 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 13 API paths
- Headings: Discover , Explore / Start with a question / Which stocks have moved the most? / Which stocks are trading unusually heavily? / Which stocks have a steady upward trend? / What is worth a look today / Every screen / Market movers / Momentum leaders / Volume / Trend structure / High risk / Relative performance / Sectors / Cross-asset
- a (60 distinct): Skip to content; Optic Terminal, Home; Settings; NTSK; LQDA; AVBP; See the full list; THRM; PCRX; TECH; MKTX; BWIN; Market movers; Top gainers with volume; Top decliners with volume; Momentum leaders; At 52-week highs; Extended. Stretched from the mean; Unusual volume; Volume leaders; Pullback in an uptrend; Steady uptrends; Below a falling 200-day; High-risk swings, upside; High-risk swings, downside; Top 5% of their peers; Bottom 5% of their peers; Just broke into the top 20%; Just dropped into the bottom 20%; XLK; XLF; XLV; XLY; XLP; XLE; XLI; XLB; XLU; XLRE; XLC; The sector board and rotation are on Macro; US 3M −1.11% 2.4×; TLT −0.78% 1.3×; US 10Y +1.04% 1.1×; Russell 2000 futures +0.74% 0.8× ...
- button (2 distinct): Collapse; Ask Milo about the biggest move
- Table in "Sectors": 11 rows; columns: Sector, Week, Month, Read
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/home, /api/scanners, /api/scanners/groups, /api/scanners/movers, /api/scanners/steady, /api/scanners/volume, /api/sectors/board, /api/session, /api/watchlists

### `#/` (home)

#### guest: 1135 words, 187 visible controls, 3 tables, 1 charts, 15 folds (0 open), settle 5524 ms, 14 API paths
- Headings: Good morning / New to Optic? Three ways to start / Markets at a glance / Market conditions / Expected move / Sector heatmap / Quote and chart / Watchlist / Economic calendar / Earnings this week / What matters today / Market news / Optic Desk / What could happen next / Today's reports / Moved most this month
- a (16 distinct): Skip to content; Optic Terminal, Home; Settings; Apple · AAPL; NVIDIA · NVDA; Read today's market; S&P 500 7,744 +0.28% Index points; Nasdaq 100 29,813 +0.55% Index points; Russell 2000 2,831 +0.41% Index points; VIX 16.91 −3.48% Volatility index; US 10Y 5.05% +5 bp Yield, change in basis points; WTI Crude 101.25 −1.49% Dollars a barrel Since Wed's settle;; Gold 4,057 +0.13% Dollars an ounce Since Wed's settle; Wed −; Bitcoin 80,329 −1.15% Dollars; SPY; See the whole week, by day
- button (94 distinct): Collapse; ticker; Search for a company; watchlist; Follow Apple AAPL; Follow NVIDIA NVDA; Follow Microsoft MSFT; Follow S&P 500 fund SPY; Not now; Customize; risk; 1 day; 1 week; 1 month; Technology XLK +0.80%; Financials XLF +0.45%; Energy XLE +0.35%; Industrials XLI +0.34%; Health Care XLV +0.30%; Materials XLB +0.16%; Consumer Discretionary XLY −0.10%; Consumer Staples XLP −0.36%; Communication Services XLC −0.43%; Real Estate XLRE −0.73%; Utilities XLU −0.84%; Update panels; 3M; 6M; 1Y; Measure between two dates; This week; Next week; VZ; HOOD; KO; PYPL; SOFI; GOOGL; MSFT; CMG; F; FDX; KLAC; NOW; PSX ...
- button[tab] (4 distinct): Market Overview; Options Research; Long-Term Investing; My Desk
- summary (3 distinct): How these readings are built; The whole desk; What this does not tell you (3)
- input(text) (1 distinct): SPY
- Table in "How these readings are built": 12 rows; columns: Factor, Reading, Effect on the score
- Table in "Earnings this week": 32 rows; columns: Day, Company, EPS est., Revenue est., Implied move
- Table in "Moved most this month": 12 rows; columns: Ticker, 1 month, Volume
- Folds: ; ; How these readings are built; ; ; ; ; ; ; ; ; ; The whole desk; What this does not tell you (3); 
- Charts: Quote and chart 698x230
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/brokerage/status, /api/earnings-week, /api/health, /api/home, /api/market, /api/priority, /api/quote/SPY, /api/scanners/movers, /api/sentiment, /api/session, /api/take-chart/SPY
#### signed in: 1206 words, 209 visible controls, 4 tables, 1 charts, 16 folds (0 open), settle 2572 ms, 16 API paths
- Headings: Good morning, Demo / Markets at a glance / Market conditions / Expected move / Sector heatmap / Quote and chart / Watchlist / Economic calendar / Earnings this week / What matters today / Market news / Optic Desk / What could happen next / Today's reports / Moved most this month
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500 7,744 +0.28% Index points; Nasdaq 100 29,813 +0.55% Index points; Russell 2000 2,831 +0.41% Index points; VIX 16.91 −3.48% Volatility index; US 10Y 5.05% +5 bp Yield, change in basis points; WTI Crude 101.20 −1.54% Dollars a barrel Since Wed's settle;; Gold 4,056 +0.10% Dollars an ounce Since Wed's settle; Wed −; Bitcoin 80,260 −1.23% Dollars; AAPL; See the whole week, by day
- button (114 distinct): Collapse; Customize; risk; 1 day; 1 week; 1 month; Technology XLK +0.80%; Financials XLF +0.45%; Energy XLE +0.35%; Industrials XLI +0.34%; Health Care XLV +0.30%; Materials XLB +0.16%; Consumer Discretionary XLY −0.10%; Consumer Staples XLP −0.36%; Communication Services XLC −0.43%; Real Estate XLRE −0.73%; Utilities XLU −0.84%; Update panels; TSLA; SPY; QQQ; NVDA; PCRX; 3M; 6M; 1Y; Measure between two dates; AAPL; This week; Next week; VZ; HOOD; KO; PYPL; SOFI; GOOGL; MSFT; CMG; F; FDX; KLAC; NOW; PSX; VRT; AMZN ...
- button[tab] (4 distinct): Market Overview; Options Research; Long-Term Investing; My Desk
- summary (4 distinct): How these readings are built; How this is sorted and timed; The whole desk; What this does not tell you (3)
- input(text) (1 distinct): AAPL
- Table in "How these readings are built": 12 rows; columns: Factor, Reading, Effect on the score
- Table in "Watchlist": 6 rows; columns: Ticker, Price, Day, Changed
- Table in "Earnings this week": 32 rows; columns: Day, Company, EPS est., Revenue est., Implied move
- Table in "Moved most this month": 12 rows; columns: Ticker, 1 month, Volume
- Folds: ; ; How these readings are built; ; ; ; ; ; ; ; How this is sorted and timed; ; ; The whole desk; What this does not tell you (3); 
- Charts: Quote and chart 698x230
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/brokerage/status, /api/earnings-week, /api/health, /api/home, /api/market, /api/priority, /api/quote/AAPL, /api/scanners/movers, /api/sentiment, /api/session, /api/take-chart/AAPL, /api/watchlist, /api/watchlists

### `#/indices` (indices)

#### guest: 364 words, 38 visible controls, 2 tables, 1 charts, 0 folds (0 open), settle 1733 ms, 6 API paths
- Headings: Markets , Indices / What the indices say / Major index funds / Index regime / Growth against the broad market (QQQ / SPY)
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; SPY; QQQ; IWM; DIA; S&P 500; Nasdaq 100; Dow Jones; Russell 2000; Developed ex-US; Emerging Markets
- button (7 distinct): Collapse; Index Read for SPY; Index Read for QQQ; Index Read for IWM; Index Read for DIA; Ask Milo about the indices; Measure between two dates
- Table in "Major index funds": 4 rows; columns: Fund, Price, Trend, Bullish above, Bearish below, Rotation, Read
- Table in "Index regime": 6 rows; columns: Index, Last, 1 year, 3 years a year, 5 years a year, 10 years a year, Against 40-week, Against 200-week, Weekly RSI, From the high, Phase
- Charts: Growth against the broad market (QQQ / SPY) 1054x190
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/indices, /api/indices/board, /api/session
#### signed in: 364 words, 41 visible controls, 2 tables, 1 charts, 0 folds (0 open), settle 0 ms, 9 API paths
- Headings: Markets , Indices / What the indices say / Major index funds / Index regime / Growth against the broad market (QQQ / SPY)
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; SPY; QQQ; IWM; DIA; S&P 500; Nasdaq 100; Dow Jones; Russell 2000; Developed ex-US; Emerging Markets
- button (8 distinct): Collapse; Index Read for SPY; Index Read for QQQ; Index Read for IWM; Index Read for DIA; Ask Milo about the indices; RSI; Measure between two dates
- Table in "Major index funds": 4 rows; columns: Fund, Price, Trend, Bullish above, Bearish below, Rotation, Read
- Table in "Index regime": 6 rows; columns: Index, Last, 1 year, 3 years a year, 5 years a year, 10 years a year, Against 40-week, Against 200-week, Weekly RSI, From the high, Phase
- Charts: Growth against the broad market (QQQ / SPY) 1054x190
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/indices, /api/indices/board, /api/session, /api/watches/hits, /api/watchlists

### `#/insiders` (insiders)

#### guest: 1620 words, 164 visible controls, 1 tables, 1 charts, 0 folds (0 open), settle 0 ms, 8 API paths
- Headings: Discover , Insiders / House trades / Disclosed trades per day / Most disclosed / The filings newest 60 of 3,018, traded Sep 29 to Oct 27
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Filing
- button (59 distinct): Collapse; Show filings; All; Buys; Sales; Other; Filter; 14 days; 30 days; 90 days; MSFT; AAPL; NVDA; HD; AMZN; IBM; MCD; DIS; LOW; PEP; SOLS; GOOG; WSBC; BRK.B; CVX; XOM; COST; PG; TSM; T; FITB; RPM; ADI; FDX; WSM; ABT; CMG; MA; SBUX; TSLA; TJX; VZ; V; WMT; NEE ...
- input(text) (2 distinct): NVDA, or blank for everything; Member's name
- button[tab] (3 distinct): House trades 3,018; Insider filings Loading; Federal contracts 12
- select(select-one) (1 distinct): Any time 30 days 90 days A year {Any time, 30 days, 90 days, A year}
- Table in "House trades": 60 rows; columns: Member, Owner, Symbol, Transaction, Amount, Traded, Filed, Filing
- Charts: House trades 613x150
- API: /api/ai-allowance, /api/auth/me, /api/build, /api/congress, /api/contracts, /api/health, /api/insiders/latest, /api/session
#### signed in: 1620 words, 167 visible controls, 1 tables, 1 charts, 0 folds (0 open), settle 0 ms, 10 API paths
- Headings: Discover , Insiders / House trades / Disclosed trades per day / Most disclosed / The filings newest 60 of 3,018, traded Sep 29 to Oct 27
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Filing
- button (60 distinct): Collapse; Show filings; All; Buys; Sales; Other; Filter; 14 days; 30 days; 90 days; MSFT; AAPL; NVDA; HD; AMZN; IBM; MCD; DIS; LOW; PEP; SOLS; GOOG; WSBC; BRK.B; CVX; XOM; COST; PG; TSM; T; FITB; RPM; ADI; rebalance; FDX; WSM; ABT; CMG; MA; SBUX; TSLA; TJX; VZ; V; WMT ...
- input(text) (2 distinct): NVDA, or blank for everything; Member's name
- button[tab] (3 distinct): House trades 3,018; Insider filings 18; Federal contracts 12
- select(select-one) (1 distinct): Any time 30 days 90 days A year {Any time, 30 days, 90 days, A year}
- Table in "House trades": 60 rows; columns: Member, Owner, Symbol, Transaction, Amount, Traded, Filed, Filing
- Charts: House trades 613x150
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/congress, /api/contracts, /api/health, /api/insiders/latest, /api/session, /api/watches/hits, /api/watchlists

### `#/instrument/%5EGSPC` (inst-gspc)

#### guest: 97 words, 31 visible controls, 0 tables, 1 charts, 0 folds (0 open), settle 2260 ms, 5 API paths
- Headings: S&P 500 (^GSPC)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (12 distinct): Collapse; RSI; 1M; 3M; 6M; 1Y; 2Y; 5Y; Line; Candles; Area; Measure between two bars
- Charts: ? 1092x401
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/instrument, /api/session
#### signed in: 97 words, 32 visible controls, 0 tables, 1 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: S&P 500 (^GSPC)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (11 distinct): Collapse; 1M; 3M; 6M; 1Y; 2Y; 5Y; Line; Candles; Area; Measure between two bars
- Charts: ? 1092x401
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/instrument, /api/session, /api/watchlists

### `#/instrument/CL%3DF` (inst-oil)

#### guest: 154 words, 30 visible controls, 0 tables, 1 charts, 0 folds (0 open), settle 444 ms, 5 API paths
- Headings: WTI Crude (CL=F)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (11 distinct): Collapse; 1M; 3M; 6M; 1Y; 2Y; 5Y; Line; Candles; Area; Measure between two bars
- Charts: ? 1092x401
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/instrument, /api/session
#### signed in: 154 words, 32 visible controls, 0 tables, 1 charts, 0 folds (0 open), settle 605 ms, 7 API paths
- Headings: WTI Crude (CL=F)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (11 distinct): Collapse; 1M; 3M; 6M; 1Y; 2Y; 5Y; Line; Candles; Area; Measure between two bars
- Charts: ? 1092x401
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/instrument, /api/session, /api/watchlists

### `#/instrument/%5ETNX` (inst-tnx)

#### guest: 96 words, 31 visible controls, 0 tables, 1 charts, 0 folds (0 open), settle 0 ms, 5 API paths
- Headings: US 10Y (^TNX)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (12 distinct): Collapse; RSI; 1M; 3M; 6M; 1Y; 2Y; 5Y; Line; Candles; Area; Measure between two bars
- Charts: ? 1092x401
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/instrument, /api/session
#### signed in: 96 words, 33 visible controls, 0 tables, 1 charts, 0 folds (0 open), settle 0 ms, 8 API paths
- Headings: US 10Y (^TNX)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (12 distinct): Collapse; RSI; 1M; 3M; 6M; 1Y; 2Y; 5Y; Line; Candles; Area; Measure between two bars
- Charts: ? 1092x401
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/instrument, /api/session, /api/watches/hits, /api/watchlists

### `#/macro` (macro)

#### guest: 338 words, 40 visible controls, 0 tables, 1 charts, 2 folds (0 open), settle 0 ms, 13 API paths
- Headings: Markets , Macro / The market today, in brief / Mildly risk-on / Expected S&P move, from the VIX / In depth / Equal weight against cap weight (RSP / SPY)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (12 distinct): Collapse; risk-on; Ask Milo about the regime; ATR; implied volatility; Breadth; Sector board; Sector strength; Rotation; Themes and pairs; relative strength; Measure between two dates
- summary (2 distinct): How the score is built, 12 terms; How this works
- button[tab] (4 distinct): Breadth and sectors; Rates and the economy; Cross-asset; Stock maps
- Folds: How the score is built, 12 terms; How this works
- Charts: In depth 1054x190
- API: /api/ai-allowance, /api/auth/me, /api/dispersion, /api/econ, /api/econ/CPIAUCSL, /api/forex, /api/health, /api/implied-correlation, /api/market, /api/rotation, /api/sectors/board, /api/session, /api/stockmap
#### signed in: 338 words, 37 visible controls, 0 tables, 1 charts, 2 folds (0 open), settle 0 ms, 15 API paths
- Headings: Markets , Macro / The market today, in brief / Mildly risk-on / Expected S&P move, from the VIX / In depth / Equal weight against cap weight (RSP / SPY)
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (8 distinct): Collapse; Ask Milo about the regime; Breadth; Sector board; Sector strength; Rotation; Themes and pairs; Measure between two dates
- summary (2 distinct): How the score is built, 12 terms; How this works
- button[tab] (4 distinct): Breadth and sectors; Rates and the economy; Cross-asset; Stock maps
- Folds: How the score is built, 12 terms; How this works
- Charts: In depth 1054x190
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/dispersion, /api/econ, /api/econ/CPIAUCSL, /api/forex, /api/health, /api/implied-correlation, /api/market, /api/rotation, /api/sectors/board, /api/session, /api/stockmap, /api/watchlists

### `#/metrics` (metrics)

#### guest: 20 words, 20 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Metrics
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 362 words, 26 visible controls, 4 tables, 0 charts, 1 folds (0 open), settle 0 ms, 8 API paths
- Headings: Metrics / Sign-ups and weekly active accounts / Came back after four weeks / Questions to Milo / Model calls by feature / Plans
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (1 distinct): Collapse
- summary (1 distinct): How this works
- Table in "Sign-ups and weekly active accounts": 12 rows; columns: Week of, Sign-ups, Verified, Active accounts
- Table in "Sign-ups and weekly active accounts": 12 rows; columns: Week of, Sign-ups, Old enough, Came back
- Table in "Sign-ups and weekly active accounts": 3 rows; columns: Feature, 7 days, 30 days
- Table in "Sign-ups and weekly active accounts": 0 rows; columns: Plan, Accounts
- Folds: How this works
- API: /api/admin/metrics, /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/thisisnotavalidpage` (notfound)

#### guest: 21 words, 21 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Page not found
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Go to Home
- button (2 distinct): Collapse; Search
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
- Notes shown: That address is not a page Check the ticker, or search for the company. Search Go to Home
#### signed in: 21 words, 23 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Page not found
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Go to Home
- button (2 distinct): Collapse; Search
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists
- Notes shown: That address is not a page Check the ticker, or search for the company. Search Go to Home

### `#/NVDA` (nvda)

#### guest: 1390 words, 177 visible controls, 6 tables, 1 charts, 21 folds (0 open), settle 4807 ms, 17 API paths
- Headings: NVDA NVIDIA Corporation , Overview / What NVIDIA Corporation does / The past year / Four questions, answered separately / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Key figures / Bull case and bear case / Bull case / Bear case / Taken together / What changed lately / Your thesis check / What should I look at next? / COMING UP / RESEARCH STEPS / More on NVIDIA Corporation / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (33 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; NVDA Stock Edges Down On DOJ Interest In $12.9 Billion Huggi; OpenAI Reportedly Plans to Buy Google's AI Chips. Should You; Nvidia Shareholders Have a Major Reason to Be Bullish After ; Nvidia's $3 billion Meta bet reveals a 30-fold shift; Nvidia Stock Has Dropped Nearly 6% in a Month; Now Jim Crame; All headlines on News; Open Financials; Open Investing; Open the chart; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Revenue grew 65.5% in the latest fiscal year; Evidence for: Profitable: about 56 cents of profit per dolla; Evidence for: Beat analysts' earnings estimates in 8 of the ; Evidence for: Holds more cash than debt ($51.5B net cash); Evidence for: Earnings report on Nov 17, in 19 days; Review past results before the report on Nov 17 Earnings →; Read the full financial statements Financials →; See how the price compares with its own valuation history In; Read the 9 latest headlines News →; 8-K; 10-Q; Chart65%of its 52-week range; OptionsNeutralno conviction; EarningsNov 17, 2026in 19 days; Financials105.9%revenue growth, 63.7% margin; News9headlines, neutral; Investing27.2trailing P/E, valuation and holding case; All 9 headlines
- button (42 distinct): Collapse; Fold What the company does; Market value; Fold The past year; 3M; 6M; 1Y; Measure between two dates; Fold Four questions, answered separately; Fold Optic Score; Fold Key figures; Market cap; P/E (trailing); Revenue growth, last quarter; Profit margin, 12 months; Dividend yield; 52-week high; 52-week low; Fold Bull case and bear case; Fold Taken together; Fold What changed lately; Ask Milo about this; Oct 28 No meaningful change: moved -1.2% (within its usual r; Oct 29 S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected A; Oct 28 NVDA Stock Edges Down On DOJ Interest In $12.9 Billio; Oct 29 OpenAI Reportedly Plans to Buy Google's AI Chips. Sho; Fold Your thesis check; Start a thesis check; Fold What should I look at next?; Ask Milo a question about NVDA Ask Milo →; Fold More on the company; P/E (forward); EPS (trailing); EPS (forward); Open price; High last session; Low last session; Volume; Average volume; Beta; Short interest; Days to cover
- button[switch] (1 distinct): Show advanced analysis
- summary (13 distinct): What it does, in full; Latest headlines neutral; The 8 marked dates; Show the figures; Why; How this is calculated; Show the case for and against (4 for, 2 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key s; Read more; 5 sources; How this works
- g[button] (8 distinct): Earnings report, Nov 19, 2025; Ex-dividend date, Dec 4, 2025; Earnings report, Feb 25, 2026; Ex-dividend date, Mar 11, 2026; Earnings report, May 20, 2026; Ex-dividend date, Jun 4, 2026; Earnings report, Aug 26, 2026; Ex-dividend date, Sep 10, 2026
- Table in "The 8 marked dates": 8 rows; columns: Date, Marked, What
- Table in "Why": 7 rows; columns: 
- Table in "Why": 5 rows; columns: 
- Table in "Why": 3 rows; columns: 
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 5 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; What it does, in full; Latest headlines neutral; The 8 marked dates; Show the figures; Why; Show the figures; Why; Show the figures; Why; Why; How this is calculated; How this is calculated; Show the case for and against (4 for, 2 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key statistics,; Read more; 5 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/digest/NVDA, /api/earnings/NVDA, /api/extras/NVDA, /api/fair-value/NVDA, /api/framework/NVDA, /api/health, /api/logo/NVDA, /api/longterm/NVDA, /api/quote/NVDA, /api/segments/NVDA, /api/session, /api/session/NVDA, /api/stage, /api/ticker/NVDA, /api/validation
#### signed in: 1387 words, 223 visible controls, 6 tables, 1 charts, 21 folds (0 open), settle 0 ms, 21 API paths
- Headings: NVDA NVIDIA Corporation , Overview / What NVIDIA Corporation does / The past year / Four questions, answered separately / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Key figures / Bull case and bear case / Bull case / Bear case / Taken together / What changed lately / Your thesis check / What should I look at next? / COMING UP / RESEARCH STEPS / More on NVIDIA Corporation / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (33 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; NVDA Stock Edges Down On DOJ Interest In $12.9 Billion Huggi; OpenAI Reportedly Plans to Buy Google's AI Chips. Should You; Nvidia Shareholders Have a Major Reason to Be Bullish After ; Nvidia's $3 billion Meta bet reveals a 30-fold shift; Nvidia Stock Has Dropped Nearly 6% in a Month; Now Jim Crame; All headlines on News; Open Financials; Open Investing; Open the chart; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Revenue grew 65.5% in the latest fiscal year; Evidence for: Profitable: about 56 cents of profit per dolla; Evidence for: Beat analysts' earnings estimates in 8 of the ; Evidence for: Holds more cash than debt ($51.5B net cash); Evidence for: Earnings report on Nov 17, in 19 days; Review past results before the report on Nov 17 Earnings →; Read the full financial statements Financials →; See how the price compares with its own valuation history In; Read the 9 latest headlines News →; 8-K; 10-Q; Chart65%of its 52-week range; OptionsNeutralno conviction; EarningsNov 17, 2026in 19 days; Financials105.9%revenue growth, 63.7% margin; News9headlines, neutral; Investing27.2trailing P/E, valuation and holding case; All 9 headlines
- button (66 distinct): Collapse; Fold What the company does; revenue; Market value; Fold The past year; 3M; 6M; 1Y; dividend; Measure between two dates; EPS; Fold Four questions, answered separately; Revenue; Net income; Net margin; Operating margin; net income; free cash flow; Balance sheet; liquidity; Dilution; P/E; Free cash flow; EMA; guidance; consensus; Guidance; Fold Optic Score; dealer gamma; forward P/E; Fold Key figures; Market cap; P/E (trailing); Revenue growth, last quarter; Profit margin, 12 months; Dividend yield; 52-week high; 52-week low; Fold Bull case and bear case; Fold Taken together; Fold What changed lately; Ask Milo about this; Oct 28 No meaningful change: moved -1.2% (within its usual r; Oct 29 S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected A; Oct 28 NVDA Stock Edges Down On DOJ Interest In $12.9 Billio ...
- button[switch] (1 distinct): Show advanced analysis
- summary (13 distinct): What it does, in full; Latest headlines neutral; The 8 marked dates; Show the figures; Why; How this is calculated; Show the case for and against (4 for, 2 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key s; Read more; 5 sources; How this works
- g[button] (8 distinct): Earnings report, Nov 19, 2025; Ex-dividend date, Dec 4, 2025; Earnings report, Feb 25, 2026; Ex-dividend date, Mar 11, 2026; Earnings report, May 20, 2026; Ex-dividend date, Jun 4, 2026; Earnings report, Aug 26, 2026; Ex-dividend date, Sep 10, 2026
- Table in "The 8 marked dates": 8 rows; columns: Date, Marked, What
- Table in "Why": 7 rows; columns: 
- Table in "Why": 5 rows; columns: 
- Table in "Why": 3 rows; columns: 
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 5 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; What it does, in full; Latest headlines neutral; The 8 marked dates; Show the figures; Why; Show the figures; Why; Show the figures; Why; Why; How this is calculated; How this is calculated; Show the case for and against (4 for, 2 against); What has been moving it recently; Recent SEC filings 5 newest; Advanced research Optic's short-term signal score, all key statistics,; Read more; 5 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/digest/NVDA, /api/earnings/NVDA, /api/extras/NVDA, /api/fair-value/NVDA, /api/framework/NVDA, /api/health, /api/logo/NVDA, /api/longterm/NVDA, /api/quote/NVDA, /api/segments/NVDA, /api/session, /api/session/NVDA, /api/stage, /api/theses, /api/ticker/NVDA, /api/validation, /api/watches/hits, /api/watchlists

### `#/NVDA/chart` (nvda-chart)

#### guest: 205 words, 100 visible controls, 0 tables, 1 charts, 2 folds (0 open), settle 1451 ms, 9 API paths
- Headings: NVDA NVIDIA Corporation , Chart
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (52 distinct): Collapse; Layers 2; Chart read; Reset; Fit; Candles; Line; Area; Select and move; Trend line; Ray; Horizontal line; Vertical line; Channel; Rectangle; Fibonacci retracement; Fibonacci extension; Pitchfork; Arrow; Text note; Measure; Risk / reward; Position size; Snap to candles; Undo the last drawing change; Redo; Delete the selected drawing; Remove all drawings on NVDA; Explain; Full screen; 4 overlays; Measure between two bars; Remove the Volume pane; Watch; Alerts; News; Analysts; Season; Notes; Insiders; Reports; Checklist; Stop check; Options; Key levels ...
- summary (1 distinct): Indicators 1
- input(search) (1 distinct): Find an indicator
- input(checkbox) (1 distinct): on
- select(select-one) (2 distinct): 1m 5m 15m 30m 1h 4h 1D 1W {1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W}; Regular hours Extended hours {Regular hours, Extended hours}
- svg[slider] (1 distinct): Bars shown, from the whole history
- Folds: ; Indicators 1
- Charts: Indicators 1 898x532
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/intraday/NVDA, /api/logo/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA
#### signed in: 208 words, 102 visible controls, 0 tables, 1 charts, 2 folds (0 open), settle 0 ms, 11 API paths
- Headings: NVDA NVIDIA Corporation , Chart
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (52 distinct): Collapse; Layers 2; Chart read; Reset; Fit; Candles; Line; Area; Select and move; Trend line; Ray; Horizontal line; Vertical line; Channel; Rectangle; Fibonacci retracement; Fibonacci extension; Pitchfork; Arrow; Text note; Measure; Risk / reward; Position size; Snap to candles; Undo the last drawing change; Redo; Delete the selected drawing; Remove all drawings on NVDA; Explain; Full screen; 4 overlays; Measure between two bars; Remove the Volume pane; Watch; Alerts; News; Analysts; Season; Notes; Insiders; Reports; Checklist; Stop check; Options; Key levels ...
- summary (1 distinct): Indicators 1
- input(search) (1 distinct): Find an indicator
- input(checkbox) (1 distinct): on
- select(select-one) (2 distinct): 1m 5m 15m 30m 1h 4h 1D 1W {1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W}; Regular hours Extended hours {Regular hours, Extended hours}
- svg[slider] (1 distinct): Bars shown, from the whole history
- Folds: ; Indicators 1
- Charts: Indicators 1 898x532
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/intraday/NVDA, /api/logo/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA, /api/watchlists

### `#/NVDA/earnings` (nvda-earnings)

#### guest: 1085 words, 93 visible controls, 6 tables, 4 charts, 4 folds (0 open), settle 0 ms, 10 API paths
- Headings: NVDA NVIDIA Corporation , Earnings / The next report / Earlier reports / Reported against expected / What the price did after / The business behind the reports / Quarters / Fiscal years / What analysts expect / Pre-earnings brief / Estimate revisions / Analyst view / Optic's reading of the setup / What options price for the report Advanced
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (27 distinct): Collapse; Fold The next report; earnings report; earnings per share; EPS; consensus; revenue; liquidity; Fold Earlier reports; Fold The business behind the reports; Revenue; Net income; Gross margin; Operating margin; year over year; Fold Pre-earnings brief; Write the pre-earnings brief; Fold Estimate revisions; guidance; Fold Analyst view; Ask Milo about the analysts; price target; Fold Optic's reading of the setup; Event premium; implied volatility; straddle; Open What options price for the report
- summary (1 distinct): View data
- Table in "View data": 8 rows; columns: Quarter, Reported on, Estimate, Reported, Difference, Surprise, Result, Reaction
- Table in "View data": 5 rows; columns: Period, Revenue, Growth, Net income, Growth, Gross margin, Operating margin
- Table in "View data": 4 rows; columns: Period, Revenue, Growth, Net income, Growth, Gross margin, Operating margin
- Table in "View data": 4 rows; columns: Period, EPS, EPS growth, Revenue, Revenue growth, Analysts
- Table in "Estimate revisions": 4 rows; columns: Period, Estimate, 30 days, 90 days, Up, 30 days, Down, 30 days
- Table in "Analyst view": 4 rows; columns: Month, Strong buy, Buy, Hold, Sell, Strong sell
- Folds: ; Panels; View data; View data
- Charts: Earlier reports 515x230; Earlier reports 515x230; The business behind the reports 1054x230; Estimate revisions 1054x150
- API: /api/ai-allowance, /api/auth/me, /api/earnings/NVDA, /api/earnings/NVDA/brief, /api/health, /api/logo/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA
#### signed in: 1088 words, 73 visible controls, 6 tables, 4 charts, 4 folds (0 open), settle 0 ms, 12 API paths
- Headings: NVDA NVIDIA Corporation , Earnings / The next report / Earlier reports / Reported against expected / What the price did after / The business behind the reports / Quarters / Fiscal years / What analysts expect / Pre-earnings brief / Estimate revisions / Analyst view / Optic's reading of the setup / What options price for the report Advanced
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (15 distinct): Collapse; Fold The next report; earnings report; earnings per share; EPS; consensus; Fold Earlier reports; Fold The business behind the reports; Fold Pre-earnings brief; Write the pre-earnings brief; Fold Estimate revisions; Fold Analyst view; Ask Milo about the analysts; Fold Optic's reading of the setup; Open What options price for the report
- summary (1 distinct): View data
- Table in "View data": 8 rows; columns: Quarter, Reported on, Estimate, Reported, Difference, Surprise, Result, Reaction
- Table in "View data": 5 rows; columns: Period, Revenue, Growth, Net income, Growth, Gross margin, Operating margin
- Table in "View data": 4 rows; columns: Period, Revenue, Growth, Net income, Growth, Gross margin, Operating margin
- Table in "View data": 4 rows; columns: Period, EPS, EPS growth, Revenue, Revenue growth, Analysts
- Table in "Estimate revisions": 4 rows; columns: Period, Estimate, 30 days, 90 days, Up, 30 days, Down, 30 days
- Table in "Analyst view": 4 rows; columns: Month, Strong buy, Buy, Hold, Sell, Strong sell
- Folds: ; Panels; View data; View data
- Charts: Earlier reports 515x230; Earlier reports 515x230; The business behind the reports 1054x230; Estimate revisions 1054x150
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings/NVDA, /api/earnings/NVDA/brief, /api/health, /api/logo/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA, /api/watchlists

### `#/NVDA/financials` (nvda-financials)

#### guest: 2066 words, 90 visible controls, 9 tables, 13 charts, 7 folds (1 open), settle 0 ms, 11 API paths
- Headings: NVDA NVIDIA Corporation , Financials / Summary, FY26 / What the figures say / Statements / Revenue and profit / Margins / Cash flow / Cash and debt / Per share / Balance sheet and margins, latest / Segments and geography / Revenue, by business segment / Operating income, by business segment / Revenue, by product and service / Revenue, by geography / Revenue, by business segment / Operating income, by business segment / Revenue, by product and service / Revenue, by geography / Earnings track record / Insider and institutional activity / Short interest / Corporate actions and flow / Dividends / Splits / Off-exchange short volume / Against SPY / Recent SEC filings / Congressional disclosures
- a (7 distinct): Skip to content; Optic Terminal, Home; Settings; Insiders page; 8-K; 10-Q; DEF 14A
- button (17 distinct): Collapse; Expand all; Collapse all; Show every section; Fold Summary; Fold Statements; Fiscal years; Quarters; Fold Segments and geography; Fold Earnings track record; Fold Insider and institutional activity; Ask Milo about insiders; Fold Short interest; Fold Corporate actions and flow; Measure between two dates; Fold Recent SEC filings; Fold Congressional disclosures
- summary (5 distinct): Panels; What the figures say; View data; Recent insider transactions; Each year's total
- input(checkbox) (1 distinct): on
- Table in "View data": 12 rows; columns: Fiscal year, FY26to Jan 31 26, FY25to Jan 31 25, FY24to Jan 31 24, FY23to Jan 31 23, FY22to Jan 31 22
- Table in "View data": 3 rows; columns: By business segment, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "View data": 3 rows; columns: By business segment, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "View data": 7 rows; columns: By product and service, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "View data": 5 rows; columns: By geography, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "Earnings track record": 8 rows; columns: Report, Estimate, Reported, Surprise
- Table in "Recent insider transactions": 20 rows; columns: Traded, Insider, Role, Action, Shares, Value
- Table in "Each year's total": 8 rows; columns: Year, Total a share
- Folds: ; Panels; [open] What the figures say; View data; View data; Recent insider transactions; Each year's total
- Charts: Statements 515x220; Statements 515x200; Statements 515x220; Statements 515x202; Statements 515x200; Statements 517x170; Statements 517x170; Segments and geography 515x200; Segments and geography 515x200; Segments and geography 515x200; Corporate actions and flow 1054x150; Corporate actions and flow 1054x150
- API: /api/ai-allowance, /api/auth/me, /api/congress, /api/extras/NVDA, /api/health, /api/logo/NVDA, /api/quote/NVDA, /api/segments/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA
#### signed in: 2069 words, 92 visible controls, 9 tables, 13 charts, 7 folds (1 open), settle 0 ms, 14 API paths
- Headings: NVDA NVIDIA Corporation , Financials / Summary, FY26 / What the figures say / Statements / Revenue and profit / Margins / Cash flow / Cash and debt / Per share / Balance sheet and margins, latest / Segments and geography / Revenue, by business segment / Operating income, by business segment / Revenue, by product and service / Revenue, by geography / Revenue, by business segment / Operating income, by business segment / Revenue, by product and service / Revenue, by geography / Earnings track record / Insider and institutional activity / Short interest / Corporate actions and flow / Dividends / Splits / Off-exchange short volume / Against SPY / Recent SEC filings / Congressional disclosures
- a (7 distinct): Skip to content; Optic Terminal, Home; Settings; Insiders page; 8-K; 10-Q; DEF 14A
- button (17 distinct): Collapse; Expand all; Collapse all; Show every section; Fold Summary; Fold Statements; Fiscal years; Quarters; Fold Segments and geography; Fold Earnings track record; Fold Insider and institutional activity; Ask Milo about insiders; Fold Short interest; Fold Corporate actions and flow; Measure between two dates; Fold Recent SEC filings; Fold Congressional disclosures
- summary (5 distinct): Panels; What the figures say; View data; Recent insider transactions; Each year's total
- input(checkbox) (1 distinct): on
- Table in "View data": 12 rows; columns: Fiscal year, FY26to Jan 31 26, FY25to Jan 31 25, FY24to Jan 31 24, FY23to Jan 31 23, FY22to Jan 31 22
- Table in "View data": 3 rows; columns: By business segment, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "View data": 3 rows; columns: By business segment, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "View data": 7 rows; columns: By product and service, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "View data": 5 rows; columns: By geography, FY26to Jan 25 26, FY25to Jan 26 25, FY24to Jan 28 24, FY23to Jan 29 23, FY22to Jan 30 22
- Table in "Earnings track record": 8 rows; columns: Report, Estimate, Reported, Surprise
- Table in "Recent insider transactions": 20 rows; columns: Traded, Insider, Role, Action, Shares, Value
- Table in "Each year's total": 8 rows; columns: Year, Total a share
- Folds: ; Panels; [open] What the figures say; View data; View data; Recent insider transactions; Each year's total
- Charts: Statements 515x220; Statements 515x200; Statements 515x220; Statements 515x202; Statements 515x200; Statements 517x170; Statements 517x170; Segments and geography 515x200; Segments and geography 515x200; Segments and geography 515x200; Corporate actions and flow 1054x150; Corporate actions and flow 1054x150
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/congress, /api/extras/NVDA, /api/health, /api/logo/NVDA, /api/quote/NVDA, /api/segments/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA, /api/watches/hits, /api/watchlists

### `#/NVDA/investing` (nvda-investing)

#### guest: 2021 words, 268 visible controls, 10 tables, 2 charts, 16 folds (0 open), settle 0 ms, 14 API paths
- Headings: NVDA NVIDIA Corporation , Investing / Long-term trend score, from price history / Return and risk / Weekly structure / Drawdown, daily / The multiple against its own history Advanced / Fair value and stars / What analysts say / Dividend score: 58 of 100, solid / Fair-value model, discounted cash flow / What moves the value most / Scenarios and other methods, side by side / What today's price implies / Sensitivity / Bear, base and bull / Single changes people ask about / Valuation scenarios / Valuation and accumulation levels Advanced
- a (40 distinct): Skip to content; Optic Terminal, Home; Settings; CashAndCashEquivalentsAtCarryingValue, 10-Q, Jul 26, 2026; DebtSecuritiesCurrent, 10-Q, Jul 26, 2026; Jul 26, 2026; PreferredStockValueOutstanding, 10-Q, Jul 26, 2026; Revenues, 10-K, filed 2026-02-25; Revenues, 10-K, filed 2025-02-26; Revenues, 10-K, filed 2024-02-21; OperatingIncomeLoss, 10-K, filed 2026-02-25; OperatingIncomeLoss, 10-K, filed 2025-02-26; OperatingIncomeLoss, 10-K, filed 2024-02-21; IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordi; IncomeTaxExpenseBenefit, 10-K, filed 2026-02-25; IncomeTaxExpenseBenefit, 10-K, filed 2025-02-26; IncomeTaxExpenseBenefit, 10-K, filed 2024-02-21; NetIncomeLoss, 10-K, filed 2026-02-25; NetIncomeLoss, 10-K, filed 2025-02-26; NetIncomeLoss, 10-K, filed 2024-02-21; DepreciationDepletionAndAmortization, 10-K, filed 2026-02-25; DepreciationDepletionAndAmortization, 10-K, filed 2025-02-26; DepreciationDepletionAndAmortization, 10-K, filed 2024-02-21; PaymentsToAcquireProductiveAssets, 10-K, filed 2026-02-25; PaymentsToAcquireProductiveAssets, 10-K, filed 2025-02-26; PaymentsToAcquireProductiveAssets, 10-K, filed 2024-02-21; NetCashProvidedByUsedInOperatingActivities, 10-K, filed 2026; NetCashProvidedByUsedInOperatingActivities, 10-K, filed 2025; NetCashProvidedByUsedInOperatingActivities, 10-K, filed 2024; ShareBasedCompensation, 10-K, filed 2026-02-25; ShareBasedCompensation, 10-K, filed 2025-02-26; ShareBasedCompensation, 10-K, filed 2024-02-21; InterestExpenseNonoperating, 10-K, filed 2026-02-25; InterestExpense, 10-K, filed 2024-02-21; PaymentsOfDividends, 10-K, filed 2026-02-25; PaymentsOfDividends, 10-K, filed 2025-02-26; PaymentsOfDividends, 10-K, filed 2024-02-21; PaymentsForRepurchaseOfCommonStock, 10-K, filed 2026-02-25; PaymentsForRepurchaseOfCommonStock, 10-K, filed 2025-02-26; PaymentsForRepurchaseOfCommonStock, 10-K, filed 2024-02-21
- button (40 distinct): Collapse; Fold Long-term trend score, from price history; Ask Milo about this score; Fold Return and risk; Fold Weekly structure; Weekly; Monthly; 1Y; 3Y; 5Y; 10Y; All; Candles; Line; Area; Measure between two bars; Fold Drawdown, daily; Measure between two dates; Open The multiple against its own history; Fold Fair value and stars; Ask Milo about fair value; Fold Fair-value model, discounted cash flow; Discount rate and long-run growth; Margin and growth; Capex and discount rate; Compare with peers; Value the segments; Why is NVDA's model value above the market price?; Which assumptions matter most in NVDA's valuation?; What happens to NVDA's value if capital spending stays eleva; How much of NVDA's value comes from the terminal period?; What growth would justify NVDA's price today?; Is a DCF appropriate for NVDA?; Reset to the defaults; Save a snapshot; Fold Valuation scenarios; Ask Milo about these scenarios; Fill the base case from history; Save; Open Valuation and accumulation levels
- summary (14 distinct): Technical levels 1; What this range cannot say; The forecast, year by year; How the discount rate is built; From enterprise value to a value per share; Linked income statement, balance sheet and cash flow; Other valuation methods and when each fits; Reported history and sources; Formulas and conventions; Assumptions: see why each was chosen, and change any of them; Set individual years; Assumptions for the dividend model; Saved models for NVDA; Your own starting figures
- input(checkbox) (1 distinct): on
- input(text) (56 distinct): for example ORCL, ADBE, CRM; 90.635; 68.153; 6; 2.5; 10; 60.382; 58.974; 5; 2.798; 2.571; 44.161; 20.906; 40; 13.46; 19.23; 4.99; 2.216; 4.23; 0; 5.39; 25; market weights; built from the parts above; 38.267; Revenue growth, 2027; Revenue growth, 2028; Revenue growth, 2029; Revenue growth, 2030; Revenue growth, 2031; Revenue growth, 2032; Revenue growth, 2033; Revenue growth, 2034; Revenue growth, 2035; Revenue growth, 2036; Operating margin, 2027; Operating margin, 2028; Operating margin, 2029; Operating margin, 2030; Operating margin, 2031; Operating margin, 2032; Operating margin, 2033; Operating margin, 2034; Operating margin, 2035; Operating margin, 2036 ...
- select(select-one) (3 distinct): Mid-year (cash arrives through the year)End of year {Mid-year (cash arr, End of year}; Value driver: growth costs reinvestmentGrow the last year's  {Value driver: grow, Grow the last year}; Adjusted toward 1 (Blume)Raw, as measured {Adjusted toward 1 , Raw, as measured}
- Table in "Long-term trend score, from price history": 6 rows; columns: Factor, Type, Raw points, Why
- Table in "Fair value and stars": 4 rows; columns: Part, Value, Points, Why
- Table in "Fair-value model, discounted cash flow": 5 rows; columns: Discount rate (WACC) down, Termi, 1.5%, 2.0%, 2.5%, 3.0%, 3.5%
- Table in "Fair-value model, discounted cash flow": 8 rows; columns: Measure, Bear, Base, Bull
- Table in "The forecast, year by year": 14 rows; columns: Year, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036
- Table in "How the discount rate is built": 8 rows; columns: 
- Table in "From enterprise value to a value per share": 12 rows; columns: 
- Table in "Linked income statement, balance sheet and cash flow": 22 rows; columns: Line, Year 1, Year 2, Year 3, Year 4, Year 5, Year 6, Year 7, Year 8, Year 9, Year 10
- Folds: ; Panels; Technical levels 1; What this range cannot say; The forecast, year by year; How the discount rate is built; From enterprise value to a value per share; Linked income statement, balance sheet and cash flow; Other valuation methods and when each fits; Reported history and sources; Formulas and conventions; Assumptions: see why each was chosen, and change any of them; Set individual years; Assumptions for the dividend model; Saved models for NVDA; Your own starting figures
- Charts: Weekly structure 1054x441; Drawdown, daily 1054x170
- API: /api/ai-allowance, /api/auth/me, /api/fair-value/NVDA, /api/framework/NVDA, /api/health, /api/logo/NVDA, /api/longterm/NVDA, /api/pe-history/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/validation, /api/valuation-inputs/NVDA, /api/valuation/NVDA
#### signed in: 2024 words, 317 visible controls, 10 tables, 2 charts, 16 folds (0 open), settle 0 ms, 19 API paths
- Headings: NVDA NVIDIA Corporation , Investing / Long-term trend score, from price history / Return and risk / Weekly structure / Drawdown, daily / The multiple against its own history Advanced / Fair value and stars / What analysts say / Dividend score: 58 of 100, solid / Fair-value model, discounted cash flow / What moves the value most / Scenarios and other methods, side by side / What today's price implies / Sensitivity / Bear, base and bull / Single changes people ask about / Valuation scenarios / Valuation and accumulation levels Advanced
- a (40 distinct): Skip to content; Optic Terminal, Home; Settings; CashAndCashEquivalentsAtCarryingValue, 10-Q, Jul 26, 2026; DebtSecuritiesCurrent, 10-Q, Jul 26, 2026; Jul 26, 2026; PreferredStockValueOutstanding, 10-Q, Jul 26, 2026; Revenues, 10-K, filed 2026-02-25; Revenues, 10-K, filed 2025-02-26; Revenues, 10-K, filed 2024-02-21; OperatingIncomeLoss, 10-K, filed 2026-02-25; OperatingIncomeLoss, 10-K, filed 2025-02-26; OperatingIncomeLoss, 10-K, filed 2024-02-21; IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordi; IncomeTaxExpenseBenefit, 10-K, filed 2026-02-25; IncomeTaxExpenseBenefit, 10-K, filed 2025-02-26; IncomeTaxExpenseBenefit, 10-K, filed 2024-02-21; NetIncomeLoss, 10-K, filed 2026-02-25; NetIncomeLoss, 10-K, filed 2025-02-26; NetIncomeLoss, 10-K, filed 2024-02-21; DepreciationDepletionAndAmortization, 10-K, filed 2026-02-25; DepreciationDepletionAndAmortization, 10-K, filed 2025-02-26; DepreciationDepletionAndAmortization, 10-K, filed 2024-02-21; PaymentsToAcquireProductiveAssets, 10-K, filed 2026-02-25; PaymentsToAcquireProductiveAssets, 10-K, filed 2025-02-26; PaymentsToAcquireProductiveAssets, 10-K, filed 2024-02-21; NetCashProvidedByUsedInOperatingActivities, 10-K, filed 2026; NetCashProvidedByUsedInOperatingActivities, 10-K, filed 2025; NetCashProvidedByUsedInOperatingActivities, 10-K, filed 2024; ShareBasedCompensation, 10-K, filed 2026-02-25; ShareBasedCompensation, 10-K, filed 2025-02-26; ShareBasedCompensation, 10-K, filed 2024-02-21; InterestExpenseNonoperating, 10-K, filed 2026-02-25; InterestExpense, 10-K, filed 2024-02-21; PaymentsOfDividends, 10-K, filed 2026-02-25; PaymentsOfDividends, 10-K, filed 2025-02-26; PaymentsOfDividends, 10-K, filed 2024-02-21; PaymentsForRepurchaseOfCommonStock, 10-K, filed 2026-02-25; PaymentsForRepurchaseOfCommonStock, 10-K, filed 2025-02-26; PaymentsForRepurchaseOfCommonStock, 10-K, filed 2024-02-21
- button (66 distinct): Collapse; Fold Long-term trend score, from price history; Ask Milo about this score; relative strength; Forward P/E; Fold Return and risk; Correlation; Fold Weekly structure; Weekly; Monthly; 1Y; 3Y; 5Y; 10Y; All; Candles; Line; Area; Measure between two bars; RSI; Fold Drawdown, daily; Measure between two dates; Open The multiple against its own history; Fold Fair value and stars; Ask Milo about fair value; EPS; P/E; price target; Dividend; Fold Fair-value model, discounted cash flow; Revenue; operating margin; Discount rate and long-run growth; Margin and growth; Capex and discount rate; consensus; balance sheet; revenue; Free cash flow; EBITDA; operating income; dilution; book value; Net income; Balance sheet ...
- summary (14 distinct): Technical levels 1; What this range cannot say; The forecast, year by year; How the discount rate is built; From enterprise value to a value per share; Linked income statement, balance sheet and cash flow; Other valuation methods and when each fits; Reported history and sources; Formulas and conventions; Assumptions: see why each was chosen, and change any of them; Set individual years; Assumptions for the dividend model; Saved models for NVDA; Your own starting figures
- input(checkbox) (1 distinct): on
- input(text) (56 distinct): for example ORCL, ADBE, CRM; 90.635; 68.153; 6; 2.5; 10; 60.382; 58.974; 5; 2.798; 2.571; 44.161; 20.906; 40; 13.46; 19.23; 4.99; 2.216; 4.23; 0; 5.39; 25; market weights; built from the parts above; 38.267; Revenue growth, 2027; Revenue growth, 2028; Revenue growth, 2029; Revenue growth, 2030; Revenue growth, 2031; Revenue growth, 2032; Revenue growth, 2033; Revenue growth, 2034; Revenue growth, 2035; Revenue growth, 2036; Operating margin, 2027; Operating margin, 2028; Operating margin, 2029; Operating margin, 2030; Operating margin, 2031; Operating margin, 2032; Operating margin, 2033; Operating margin, 2034; Operating margin, 2035; Operating margin, 2036 ...
- select(select-one) (3 distinct): Mid-year (cash arrives through the year)End of year {Mid-year (cash arr, End of year}; Value driver: growth costs reinvestmentGrow the last year's  {Value driver: grow, Grow the last year}; Adjusted toward 1 (Blume)Raw, as measured {Adjusted toward 1 , Raw, as measured}
- Table in "Long-term trend score, from price history": 6 rows; columns: Factor, Type, Raw points, Why
- Table in "Fair value and stars": 4 rows; columns: Part, Value, Points, Why
- Table in "Fair-value model, discounted cash flow": 5 rows; columns: Discount rate (WACC) down, Termi, 1.5%, 2.0%, 2.5%, 3.0%, 3.5%
- Table in "Fair-value model, discounted cash flow": 8 rows; columns: Measure, Bear, Base, Bull
- Table in "The forecast, year by year": 14 rows; columns: Year, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036
- Table in "How the discount rate is built": 8 rows; columns: 
- Table in "From enterprise value to a value per share": 12 rows; columns: 
- Table in "Linked income statement, balance sheet and cash flow": 22 rows; columns: Line, Year 1, Year 2, Year 3, Year 4, Year 5, Year 6, Year 7, Year 8, Year 9, Year 10
- Folds: ; Panels; Technical levels 1; What this range cannot say; The forecast, year by year; How the discount rate is built; From enterprise value to a value per share; Linked income statement, balance sheet and cash flow; Other valuation methods and when each fits; Reported history and sources; Formulas and conventions; Assumptions: see why each was chosen, and change any of them; Set individual years; Assumptions for the dividend model; Saved models for NVDA; Your own starting figures
- Charts: Weekly structure 1054x441; Drawdown, daily 1054x170
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/fair-value/NVDA, /api/framework/NVDA, /api/health, /api/logo/NVDA, /api/longterm/NVDA, /api/pe-history/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/validation, /api/valuation-inputs/NVDA, /api/valuation-models, /api/valuation/NVDA, /api/valuations, /api/watches/hits, /api/watchlists

### `#/NVDA/news` (nvda-news)

#### guest: 422 words, 51 visible controls, 0 tables, 1 charts, 3 folds (0 open), settle 0 ms, 8 API paths
- Headings: NVDA NVIDIA Corporation , News / News and catalysts / Catalyst types found / About NVDA 6 / Market context 3
- a (12 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; NVDA Stock Edges Down On DOJ Interest In $12.9 Billion Huggi; OpenAI Reportedly Plans to Buy Google's AI Chips. Should You; Nvidia Shareholders Have a Major Reason to Be Bullish After ; Nvidia's $3 billion Meta bet reveals a 30-fold shift; Nvidia Stock Has Dropped Nearly 6% in a Month; Now Jim Crame; The Fed Holds Interest Rates in a 10 to 2 Vote. Here's What ; Stealth Bear Market Hits Crypto Stocks as Coinbase, Circle, ; Federal Reserve Holds Interest Rates Steady Ahead of Midterm
- button (6 distinct): Collapse; Ask Milo about the news; Earnings 1, neutral; M&A 1, bullish; Policy / supply chain 1, neutral; Macro event 1, neutral
- summary (2 distinct): How this works; How these are ranked
- Folds: ; How this works; How these are ranked
- Charts: News and catalysts 1054x176
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/logo/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA
#### signed in: 425 words, 56 visible controls, 0 tables, 1 charts, 3 folds (0 open), settle 0 ms, 11 API paths
- Headings: NVDA NVIDIA Corporation , News / News and catalysts / Catalyst types found / About NVDA 6 / Market context 3
- a (12 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; NVDA Stock Edges Down On DOJ Interest In $12.9 Billion Huggi; OpenAI Reportedly Plans to Buy Google's AI Chips. Should You; Nvidia Shareholders Have a Major Reason to Be Bullish After ; Nvidia's $3 billion Meta bet reveals a 30-fold shift; Nvidia Stock Has Dropped Nearly 6% in a Month; Now Jim Crame; The Fed Holds Interest Rates in a 10 to 2 Vote. Here's What ; Stealth Bear Market Hits Crypto Stocks as Coinbase, Circle, ; Federal Reserve Holds Interest Rates Steady Ahead of Midterm
- button (9 distinct): Collapse; Ask Milo about the news; Implied volatility; Earnings 1, neutral; M&A 1, bullish; Policy / supply chain 1, neutral; Macro event 1, neutral; guidance; short interest
- summary (2 distinct): How this works; How these are ranked
- Folds: ; How this works; How these are ranked
- Charts: News and catalysts 1054x176
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/logo/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA, /api/watches/hits, /api/watchlists

### `#/NVDA/options` (nvda-options)

#### guest: 678 words, 88 visible controls, 0 tables, 2 charts, 3 folds (0 open), settle 0 ms, 10 API paths
- Headings: NVDA NVIDIA Corporation , Options / Pick a contract / Research contracts / Position builder / What options are pricing / How value moves
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (32 distinct): Collapse; Implied move; Expect a rise; Expect a fall; 7 days; 14 days; 30 days; 60 days; Find contracts; Calls; Puts; More columns; open interest; Long call; Long put; Bull call spread; Bear put spread; Covered call; Cash-secured put; Straddle; Strangle; Iron condor; Call calendar; Apply; Fold What options are pricing; Fold How value moves; Call; Put; 45 days; delta; gamma; implied volatility
- button[tab] (3 distinct): Contracts and pricing; Positioning and flow; Setups and strategy
- input(text) (6 distinct): Most premium at risk, in dollars; Target price for the stock, optional; Price at which the idea is wrong, optional; 0.25; 0.65; Halfway
- input(checkbox) (1 distinct): on
- select(select-one) (4 distinct): Expiry for the table and the position builder {Oct 30, 1 day, Nov 2, 4 days, Nov 4, 6 days, Nov 6, 8 days, Nov 13, 15 days, Nov 20, 22 days, m, Nov 27, 29 days, Dec 4, 36 days, Dec 18, 50 days, m, Jan 15, 78 days, m, Feb 19, 113 days, , Mar 19, 141 days, }; Any Far, .10 to .30 Middle, .30 to .50 At the money, .40 to  {Any, Far, .10 to .30, Middle, .30 to .50, At the money, .40 , Deep, .60 to .90}; Any 5% 10% 25% {Any, 5%, 10%, 25%}; Any 100 500 1,000 {Any, 100, 500, 1,000}
- summary (2 distinct): Costs and timing; How this works
- input(number) (1 distinct): Implied volatility, percent
- Folds: ; Costs and timing; How this works
- Charts: How value moves 1054x200; How value moves 1054x200
- API: /api/ai-allowance, /api/auth/me, /api/earnings/NVDA, /api/health, /api/logo/NVDA, /api/options/NVDA/research, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA
- Notes shown: No usable quotes for this expiry The option chain the feed returned has no quotes and no o / No options pricing right now The chain did not have enough two-sided quotes to read.
#### signed in: 681 words, 84 visible controls, 0 tables, 2 charts, 3 folds (0 open), settle 0 ms, 13 API paths
- Headings: NVDA NVIDIA Corporation , Options / Pick a contract / Research contracts / Position builder / What options are pricing / How value moves
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (27 distinct): Collapse; Expect a rise; Expect a fall; 7 days; 14 days; 30 days; 60 days; Find contracts; Calls; Puts; More columns; Long call; Long put; Bull call spread; Bear put spread; Covered call; Cash-secured put; Straddle; Strangle; Iron condor; Call calendar; Apply; Fold What options are pricing; Fold How value moves; Call; Put; 45 days
- button[tab] (3 distinct): Contracts and pricing; Positioning and flow; Setups and strategy
- input(text) (6 distinct): Most premium at risk, in dollars; Target price for the stock, optional; Price at which the idea is wrong, optional; 0.25; 0.65; Halfway
- input(checkbox) (1 distinct): on
- select(select-one) (4 distinct): Expiry for the table and the position builder {Oct 30, 1 day, Nov 2, 4 days, Nov 4, 6 days, Nov 6, 8 days, Nov 13, 15 days, Nov 20, 22 days, m, Nov 27, 29 days, Dec 4, 36 days, Dec 18, 50 days, m, Jan 15, 78 days, m, Feb 19, 113 days, , Mar 19, 141 days, }; Any Far, .10 to .30 Middle, .30 to .50 At the money, .40 to  {Any, Far, .10 to .30, Middle, .30 to .50, At the money, .40 , Deep, .60 to .90}; Any 5% 10% 25% {Any, 5%, 10%, 25%}; Any 100 500 1,000 {Any, 100, 500, 1,000}
- summary (2 distinct): Costs and timing; How this works
- input(number) (1 distinct): Implied volatility, percent
- Folds: ; Costs and timing; How this works
- Charts: How value moves 1054x200; How value moves 1054x200
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings/NVDA, /api/health, /api/logo/NVDA, /api/options/NVDA/research, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA, /api/watches/hits, /api/watchlists
- Notes shown: No usable quotes for this expiry The option chain the feed returned has no quotes and no o / No options pricing right now The chain did not have enough two-sided quotes to read.

### `#/NVDA/sheet` (nvda-sheet)

#### guest: 468 words, 30 visible controls, 2 tables, 1 charts, 0 folds (0 open), settle 0 ms, 10 API paths
- Headings: NVIDIA Corporation NVDA / The business Reported / Key financials Reported / Valuation Optic / Earnings Estimate / Price, past year Reported / Chart structure Optic / Options positioning Estimate / Evidence for and against Optic / Supporting / Conflicting / Principal risks / Sources
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Back to the Dossier
- button (11 distinct): Collapse; Print or save as PDF; Revenue; Net income; Free cash flow; P/E; EPS; resistance; MACD; Implied volatility; gamma
- Table in "NVIDIA Corporation NVDA": 5 rows; columns: 
- Table in "Chart structure Optic": 4 rows; columns: Level, Role, Away, Touches
- Charts: NVIDIA Corporation NVDA 710x146
- API: /api/ai-allowance, /api/auth/me, /api/earnings/NVDA, /api/fair-value/NVDA, /api/health, /api/longterm/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA
#### signed in: 468 words, 23 visible controls, 2 tables, 1 charts, 0 folds (0 open), settle 0 ms, 12 API paths
- Headings: NVIDIA Corporation NVDA / The business Reported / Key financials Reported / Valuation Optic / Earnings Estimate / Price, past year Reported / Chart structure Optic / Options positioning Estimate / Evidence for and against Optic / Supporting / Conflicting / Principal risks / Sources
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Back to the Dossier
- button (2 distinct): Collapse; Print or save as PDF
- Table in "NVIDIA Corporation NVDA": 5 rows; columns: 
- Table in "Chart structure Optic": 4 rows; columns: Level, Role, Away, Touches
- Charts: NVIDIA Corporation NVDA 710x146
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings/NVDA, /api/fair-value/NVDA, /api/health, /api/longterm/NVDA, /api/quote/NVDA, /api/session, /api/session/NVDA, /api/ticker/NVDA, /api/watchlists

### `#/paper` (paper)

#### guest: 373 words, 55 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 5 API paths
- Headings: Positions , Paper Desk / Open a trade / Open, 0 / Record / Replay a past decision
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (9 distinct): Collapse; Long; Short; Shares; Option; Add evidence; Open the trade; Clear; Start
- input(text) (9 distinct): NVDA; Held the 200-day and volume came in; Held the 50-day average; RSI back above 50; Below its 200-day; sector lagging; Earnings; A daily close above 352; A close below the 50-day; Opened strong, volume above average
- input(number) (2 distinct): 100; Last price
- summary (1 distinct): The plan
- select(select-one) (2 distinct): Pullback in a trendBreakoutEarnings reactionReversalRange tr {Pullback in a tren, Breakout, Earnings reaction, Reversal, Range trade, Other}; Price trendMomentumVolumeLevelsOptions positioningBusiness a {Price trend, Momentum, Volume, Levels, Options positionin, Business and valua, News or a schedule, The market}
- input(date) (0 distinct): 
- input(checkbox) (1 distinct): on
- Folds: The plan
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/replays, /api/session
#### signed in: 382 words, 60 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 8 API paths
- Headings: Positions , Paper Desk / Open a trade / Open, 0 / Record / Replay a past decision
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (12 distinct): Collapse; Long; Short; Shares; Option; Add evidence; Open the trade; Clear; EMA; Start; RSI; oversold
- input(text) (9 distinct): NVDA; Held the 200-day and volume came in; Held the 50-day average; RSI back above 50; Below its 200-day; sector lagging; Earnings; A daily close above 352; A close below the 50-day; Opened strong, volume above average
- input(number) (2 distinct): 100; Last price
- summary (1 distinct): The plan
- select(select-one) (2 distinct): Pullback in a trendBreakoutEarnings reactionReversalRange tr {Pullback in a tren, Breakout, Earnings reaction, Reversal, Range trade, Other}; Price trendMomentumVolumeLevelsOptions positioningBusiness a {Price trend, Momentum, Volume, Levels, Options positionin, Business and valua, News or a schedule, The market}
- input(date) (0 distinct): 
- input(checkbox) (1 distinct): on
- Folds: The plan
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/replays, /api/session, /api/watches/hits, /api/watchlists

### `#/portfolio` (portfolio)

#### guest: 560 words, 56 visible controls, 0 tables, 0 charts, 3 folds (0 open), settle 0 ms, 5 API paths
- Headings: Positions , Optic Portfolio / Three simulated accounts / Optic Portfolio Balanced / Month by month / No trades yet / Earlier records / How these positions are taken
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (15 distinct): Collapse; Fold Three simulated accounts; Ask Milo what differs; Conservative Smaller risk per trade Value $100.0K Record No ; Balanced Middle risk per trade Value $100.0K Record No trade; Aggressive Higher risk: bigger gains and bigger losses Value; Fold Optic Portfolio Balanced; Run a scan now; Refresh marks; Realised P&L; Unrealised P&L; Open Month by month; Fold No trades yet; Open Earlier records; Open How these positions are taken
- summary (2 distinct): Run the shared scan or refresh prices; How the book limits its risk
- Folds: Panels; Run the shared scan or refresh prices; How the book limits its risk
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session, /api/tracker
#### signed in: 568 words, 56 visible controls, 0 tables, 0 charts, 3 folds (0 open), settle 0 ms, 7 API paths
- Headings: Positions , Optic Portfolio / Three simulated accounts / Optic Portfolio Balanced / Month by month / No trades yet / Earlier records / How these positions are taken
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (13 distinct): Collapse; Fold Three simulated accounts; Ask Milo what differs; Conservative Smaller risk per trade Value $100.0K Record No ; Balanced Middle risk per trade Value $100.0K Record No trade; Aggressive Higher risk: bigger gains and bigger losses Value; Fold Optic Portfolio Balanced; Run a scan now; Refresh marks; Open Month by month; Fold No trades yet; Open Earlier records; Open How these positions are taken
- summary (2 distinct): Run the shared scan or refresh prices; How the book limits its risk
- Folds: Panels; Run the shared scan or refresh prices; How the book limits its risk
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/tracker, /api/watchlists

### `#/privacy` (privacy)

#### guest: 1465 words, 24 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Privacy policy / Who this covers / What you give when you create an account / What Optic keeps while you use it / How we use it / Cookies and tracking / Milo, the assistant / Linking a brokerage (Pro) / Payments / Email / Market data sources / Where it is kept, and for how long / Deleting your account / Your choices and rights / Contact and changes
- a (6 distinct): Skip to content; Optic Terminal, Home; Settings; commercial terms; privacy policy; theopticterminal@gmail.com
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 1465 words, 26 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 6 API paths
- Headings: Privacy policy / Who this covers / What you give when you create an account / What Optic keeps while you use it / How we use it / Cookies and tracking / Milo, the assistant / Linking a brokerage (Pro) / Payments / Email / Market data sources / Where it is kept, and for how long / Deleting your account / Your choices and rights / Contact and changes
- a (6 distinct): Skip to content; Optic Terminal, Home; Settings; commercial terms; privacy policy; theopticterminal@gmail.com
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watchlists

### `#/read` (read)

#### guest: 1033 words, 54 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 11 API paths
- Headings: Markets , Read / More from today / Market-moving events 4 / Earnings this week 20 / Sector read-through 9 / Scanner names 20
- a (27 distinct): Skip to content; Optic Terminal, Home; Settings; VZ; HOOD; KO; PYPL; SOFI; CMG; F; FDX; XLK; XLF; XLV; XLP; XLE; XLRE; XLB; XLU; PCRX; AVBP; PTC; NTSK; UNIT; HAS; RPD; APPN
- button (6 distinct): Collapse; Build today's Read; Today's priority; Overnight, worldwide; Headlines; Official releases and sources
- button[tab] (3 distinct): Today; Catalysts and calendar; Sentiment and regime
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/catalyst-mode, /api/catalysts, /api/desk/edition, /api/health, /api/priority, /api/sentiment, /api/session, /api/weekly
- Notes shown: Today's Read is not ready yet Today's Read has not been built yet. It is built every 20 mi
#### signed in: 1033 words, 56 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 13 API paths
- Headings: Markets , Read / More from today / Market-moving events 4 / Earnings this week 20 / Sector read-through 9 / Scanner names 20
- a (27 distinct): Skip to content; Optic Terminal, Home; Settings; VZ; HOOD; KO; PYPL; SOFI; CMG; F; FDX; XLK; XLF; XLV; XLP; XLE; XLRE; XLB; XLU; PCRX; AVBP; PTC; NTSK; UNIT; HAS; RPD; APPN
- button (6 distinct): Collapse; Build today's Read; Today's priority; Overnight, worldwide; Headlines; Official releases and sources
- button[tab] (3 distinct): Today; Catalysts and calendar; Sentiment and regime
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/brokerage/status, /api/catalyst-mode, /api/catalysts, /api/desk/edition, /api/health, /api/priority, /api/sentiment, /api/session, /api/watchlists, /api/weekly
- Notes shown: Today's Read is not ready yet Today's Read has not been built yet. It is built every 20 mi

### `#/reports` (reports)

#### guest: 21 words, 20 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Problem Reports
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 44 words, 27 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Problem Reports
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (3 distinct): Collapse; Open 0; Resolved 0
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/feedback, /api/health, /api/session, /api/watchlists

### `#/retirement` (retirement)

#### guest: 1322 words, 45 visible controls, 3 tables, 1 charts, 0 folds (0 open), settle 2099 ms, 5 API paths
- Headings: Positions , Retirement / Roth IRA model allocation / The fund weights as one portfolio, 2019 to 2026 / Target weights / Contribution projection / Where to put this year's contribution / Individual stock sleeve / What the Roth wrapper changes / Fund universe / Correlation
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; VTI; VEA; BND; VWO; QQQ; VNQ; AVUV; VOO; SCHD; GLD
- button (2 distinct): Collapse; Recalculate
- input(number) (2 distinct): 30; 7000
- select(select-one) (1 distinct): Conservative Balanced Growth {Conservative, Balanced, Growth}
- input(text) (1 distinct): e.g. AAPL, KO, MSFT
- textarea(textarea) (1 distinct): VTI 12000 VXUS 4000 BND 1500
- Table in "Roth IRA model allocation": 7 rows; columns: Fund, Weight, Per year, Expense, Yield, 10y return a year, Volatility, Worst drawdown
- Table in "Fund universe": 10 rows; columns: Fund, In model, Expense, Return a year, full history, 5y CAGR, Volatility, Return / vol, Worst drawdown, History
- Table in "Correlation": 10 rows; columns: Fund, VTI, VOO, QQQ, AVUV, VEA, VWO, SCHD, VNQ, BND, GLD
- Charts: Contribution projection 1054x300
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/retirement, /api/session
#### signed in: 1322 words, 47 visible controls, 3 tables, 1 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Positions , Retirement / Roth IRA model allocation / The fund weights as one portfolio, 2019 to 2026 / Target weights / Contribution projection / Where to put this year's contribution / Individual stock sleeve / What the Roth wrapper changes / Fund universe / Correlation
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; VTI; VEA; BND; VWO; QQQ; VNQ; AVUV; VOO; SCHD; GLD
- button (2 distinct): Collapse; Recalculate
- input(number) (2 distinct): 30; 7000
- select(select-one) (1 distinct): Conservative Balanced Growth {Conservative, Balanced, Growth}
- input(text) (1 distinct): e.g. AAPL, KO, MSFT
- textarea(textarea) (1 distinct): VTI 12000 VXUS 4000 BND 1500
- Table in "Roth IRA model allocation": 7 rows; columns: Fund, Weight, Per year, Expense, Yield, 10y return a year, Volatility, Worst drawdown
- Table in "Fund universe": 10 rows; columns: Fund, In model, Expense, Return a year, full history, 5y CAGR, Volatility, Return / vol, Worst drawdown, History
- Table in "Correlation": 10 rows; columns: Fund, VTI, VOO, QQQ, AVUV, VEA, VWO, SCHD, VNQ, BND, GLD
- Charts: Contribution projection 1054x300
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/retirement, /api/session, /api/watchlists

### `#/research` (saved)

#### guest: 133 words, 24 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Saved research / Your questions / Start an investigation
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; Which names look strongest right now? Named screens over the; How do two or three names stack up? Scored across three hori
- button (3 distinct): Collapse; What is going on with one company? Search a ticker to open t; I need sources and citations. Deep research runs live web so
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
- Notes shown: Nothing saved yet Press Save under a question you asked Milo, and it is kept here to ask a
#### signed in: 118 words, 25 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 8 API paths
- Headings: Saved research / Your questions / Start an investigation
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; Which names look strongest right now? Named screens over the; How do two or three names stack up? Scored across three hori
- button (3 distinct): Collapse; What is going on with one company? Search a ticker to open t; I need sources and citations. Deep research runs live web so
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/saved-research, /api/session, /api/watches/hits, /api/watchlists
- Notes shown: Nothing saved yet Press Save under a question you asked Milo, and it is kept here to ask a

### `#/scan` (scan)

#### guest: 569 words, 125 visible controls, 1 tables, 0 charts, 1 folds (1 open), settle 0 ms, 7 API paths
- Headings: Discover , Scan / Find stocks / Scanners / What this screen returned / Does the score work?
- a (54 distinct): Skip to content; Optic Terminal, Home; Settings; PCRX; PCRX chart; PTC; PTC chart; HAS; HAS chart; VSTM; VSTM chart; FTRE; FTRE chart; KNSA; KNSA chart; ICLR; ICLR chart; HURN; HURN chart; NTSK; NTSK chart; FRSH; FRSH chart; XNCR; XNCR chart; APPN; APPN chart; AVPT; AVPT chart; CART; CART chart; TENB; TENB chart; AMPL; AMPL chart; CBRL; CBRL chart; GTLB; GTLB chart; AZTA; AZTA chart; RPD; RPD chart; CERT; CERT chart ...
- button (26 distinct): Collapse; Find symbols now; Ask Milo to help phrase it; Strong stocks on the 200-day average right now; Near 52-week highs on heavy volume; Pullbacks in strong uptrends; Under $20 and up 20% in the last 3 months; 10% pull back after 20% rally; 2% or more above prev close; Named scans; Shortlist; Build a screen; Market movers 3; Momentum leaders 3; Volume 2; Trend structure 3; High risk 2; Relative performance 4; Momentum leaders; At 52-week highs; Extended. Stretched from the mean; Watch; liquidity; short interest; Ask Milo about this test; Run the test
- textarea(textarea) (1 distinct): Strong stocks on the 200-day average right now
- summary (1 distinct): Examples 6
- Table in "Scanners": 25 rows; columns: Symbol, Price, Score ▼, 1-month, 3-month, 52-wk range, Next
- Folds: [open] Examples 6
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/scanners, /api/scanners/groups, /api/scanners/momentum, /api/session
#### signed in: 572 words, 125 visible controls, 1 tables, 0 charts, 1 folds (1 open), settle 0 ms, 9 API paths
- Headings: Discover , Scan / Find stocks / Scanners / What this screen returned / Does the score work?
- a (54 distinct): Skip to content; Optic Terminal, Home; Settings; PCRX; PCRX chart; PTC; PTC chart; HAS; HAS chart; VSTM; VSTM chart; FTRE; FTRE chart; KNSA; KNSA chart; ICLR; ICLR chart; HURN; HURN chart; NTSK; NTSK chart; FRSH; FRSH chart; XNCR; XNCR chart; APPN; APPN chart; AVPT; AVPT chart; CART; CART chart; TENB; TENB chart; AMPL; AMPL chart; CBRL; CBRL chart; GTLB; GTLB chart; AZTA; AZTA chart; RPD; RPD chart; CERT; CERT chart ...
- button (25 distinct): Collapse; Find symbols now; Ask Milo to help phrase it; Strong stocks on the 200-day average right now; Near 52-week highs on heavy volume; Pullbacks in strong uptrends; Under $20 and up 20% in the last 3 months; 10% pull back after 20% rally; 2% or more above prev close; Named scans; Shortlist; Build a screen; Market movers 3; Momentum leaders 3; Volume 2; Trend structure 3; High risk 2; Relative performance 4; Momentum leaders; At 52-week highs; Extended. Stretched from the mean; Watching on Main Watchlist; Watch; Ask Milo about this test; Run the test
- textarea(textarea) (1 distinct): Strong stocks on the 200-day average right now
- summary (1 distinct): Examples 6
- Table in "Scanners": 25 rows; columns: Symbol, Price, Score ▼, 1-month, 3-month, 52-wk range, Next
- Folds: [open] Examples 6
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/scanners, /api/scanners/groups, /api/scanners/momentum, /api/session, /api/watchlists

### `#/settings` (settings)

#### guest: 634 words, 33 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Settings / Account / Appearance / Text size / Keyboard / How Milo explains things / Time zone / Market hours / About this build / Report a problem
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; Create an account; Sign in
- button (10 distinct): Collapse; Dark; Light; Follow system; Reduce; Compact; Default; Large; Show the shortcuts; Report a problem
- input[switch](checkbox) (1 distinct): on
- select(select-one) (1 distinct): My device’s time zone, 1:22 am New York. Eastern (market tim {My device’s time z, New York. Eastern , Chicago: Central, , Denver: Mountain, , Los Angeles. Pacif, Toronto, 1:22 am, São Paulo, 2:22 am, London, 5:22 am, Paris / Berlin / M, Istanbul, 8:22 am, Dubai, 9:22 am, Mumbai, 10:52 am}
- Table in "Time zone": 4 rows; columns: Session, Eastern (market)
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 992 words, 48 visible controls, 1 tables, 0 charts, 0 folds (0 open), settle 0 ms, 10 API paths
- Headings: Settings / Profile / Security / Password / Passkeys 0 / Connected accounts / Active sessions / Plan / Delete account / Appearance / Text size / Keyboard / How Milo explains things / Time zone / Market hours / About this build / Report a problem
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Manage
- button (19 distinct): Collapse; Save; Change; Remove; Add a passkey; Sign out; Revoke; Show all 30 sessions; Sign out of all devices; Delete this account; Dark; Light; Follow system; Reduce; Compact; Default; Large; Show the shortcuts; Report a problem
- input(text) (2 distinct): First; Last
- input[switch](checkbox) (1 distinct): on
- select(select-one) (1 distinct): My device’s time zone, 1:31 am New York. Eastern (market tim {My device’s time z, New York. Eastern , Chicago: Central, , Denver: Mountain, , Los Angeles. Pacif, Toronto, 1:31 am, São Paulo, 2:31 am, London, 5:31 am, Paris / Berlin / M, Istanbul, 8:31 am, Dubai, 9:31 am, Mumbai, 11:01 am}
- Table in "Time zone": 4 rows; columns: Session, Eastern (market)
- API: /api/ai-allowance, /api/auth/identities, /api/auth/me, /api/auth/sessions, /api/billing/status, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/signin` (signin)

#### guest: 43 words, 26 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Sign in to Optic
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (5 distinct): Collapse; Sign in with a passkey; Sign in; Forgot your password?; Create an account
- input(email) (1 distinct): Email
- input(password) (1 distinct): Password
- input(checkbox) (1 distinct): on
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 1206 words, 209 visible controls, 4 tables, 1 charts, 16 folds (0 open), settle 2565 ms, 18 API paths
- Headings: Good morning, Demo / Markets at a glance / Market conditions / Expected move / Sector heatmap / Quote and chart / Watchlist / Economic calendar / Earnings this week / What matters today / Market news / Optic Desk / What could happen next / Today's reports / Moved most this month
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500 7,744 +0.28% Index points; Nasdaq 100 29,813 +0.55% Index points; Russell 2000 2,831 +0.41% Index points; VIX 16.91 −3.48% Volatility index; US 10Y 5.05% +5 bp Yield, change in basis points; WTI Crude 101.20 −1.54% Dollars a barrel Since Wed's settle;; Gold 4,056 +0.10% Dollars an ounce Since Wed's settle; Wed −; Bitcoin 80,260 −1.23% Dollars; AAPL; See the whole week, by day
- button (114 distinct): Collapse; Customize; risk; 1 day; 1 week; 1 month; Technology XLK +0.80%; Financials XLF +0.45%; Energy XLE +0.35%; Industrials XLI +0.34%; Health Care XLV +0.30%; Materials XLB +0.16%; Consumer Discretionary XLY −0.10%; Consumer Staples XLP −0.36%; Communication Services XLC −0.43%; Real Estate XLRE −0.73%; Utilities XLU −0.84%; Update panels; TSLA; SPY; QQQ; NVDA; PCRX; 3M; 6M; 1Y; Measure between two dates; AAPL; This week; Next week; VZ; HOOD; KO; PYPL; SOFI; GOOGL; MSFT; CMG; F; FDX; KLAC; NOW; PSX; VRT; AMZN ...
- button[tab] (4 distinct): Market Overview; Options Research; Long-Term Investing; My Desk
- summary (4 distinct): How these readings are built; How this is sorted and timed; The whole desk; What this does not tell you (3)
- input(text) (1 distinct): AAPL
- Table in "How these readings are built": 12 rows; columns: Factor, Reading, Effect on the score
- Table in "Watchlist": 6 rows; columns: Ticker, Price, Day, Changed
- Table in "Earnings this week": 32 rows; columns: Day, Company, EPS est., Revenue est., Implied move
- Table in "Moved most this month": 12 rows; columns: Ticker, 1 month, Volume
- Folds: ; ; How these readings are built; ; ; ; ; ; ; ; How this is sorted and timed; ; ; The whole desk; What this does not tell you (3); 
- Charts: Quote and chart 698x230
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/brokerage/status, /api/build, /api/earnings-week, /api/health, /api/home, /api/market, /api/priority, /api/quote/AAPL, /api/scanners/movers, /api/sentiment, /api/session, /api/take-chart/AAPL, /api/watches/hits, /api/watchlist, /api/watchlists

### `#/SPY` (spy)

#### guest: 937 words, 128 visible controls, 3 tables, 1 charts, 14 folds (0 open), settle 3464 ms, 17 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Overview / What State Street SPDR S&P 500 ETF Trust is / The past year / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Bull case and bear case / Bull case / Bear case / The long-term record / What changed lately / What should I look at next? / COMING UP / RESEARCH STEPS / More on State Street SPDR S&P 500 ETF Trust / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (23 distinct): Skip to content; Optic Terminal, Home; Settings; What State Street SPDR S&P 500 ETF (SPY) Bought: NVIDIA Lead; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; Exchange-Traded Funds Higher, Equity Futures Mixed Pre-Bell ; S&P 500, Nasdaq Jump On Chipmaker Strength As Investors Eye ; Stocks Without AI Are Beating the S&P 500 by 6 Points This M; Jeff Bezos Says Retirees Should Buy the S&P 500 Instead of A; All headlines on News; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Share price up 13% over the period shown; See how the price compares with its own valuation history In; Read the 9 latest headlines News →; Compare SPY side by side with a competitor Compare →; SC 13G; Chart94%of its 52-week range; OptionsNeutralno conviction; Earningsn/ano date published; News9headlines, mildly bullish; Investing24.5trailing P/E, valuation and holding case; All 9 headlines
- button (30 distinct): Collapse; Fold What the company is; Fold The past year; 3M; 6M; 1Y; Measure between two dates; What is it? A large blend fund from State Street Investment ; What do its holdings cost? 24.5 times trailing earnings. Pri; How has the share price moved? Up 12.7% over a year. From 68; What does it pay? 0.99% a year. Distributions pass on what t; Fold Optic Score; Fold Bull case and bear case; Fold The long-term record; Fold What changed lately; Ask Milo about this; Oct 28 No meaningful change: moved +0.3% (within its usual r; Oct 27 What State Street SPDR S&P 500 ETF (SPY) Bought: NVID; Fold What should I look at next?; Ask Milo a question about SPY Ask Milo →; Fold More on the company; P/E (trailing); Dividend yield; Open price; High last session; Low last session; Volume; Average volume; 52-week high; 52-week low
- button[switch] (1 distinct): Show advanced analysis
- summary (11 distinct): Latest headlines mildly bullish; The 4 marked dates; How this is calculated; Show the case for and against (1 for, 0 against); What has been moving it recently; Key figures; Recent SEC filings 4 newest; Advanced research Optic's short-term signal score, all key s; Read more; 5 sources; How this works
- g[button] (4 distinct): Ex-dividend date, Dec 19, 2025; Ex-dividend date, Mar 20, 2026; Ex-dividend date, Jun 18, 2026; Ex-dividend date, Sep 18, 2026
- Table in "The 4 marked dates": 4 rows; columns: Date, Marked, What
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 2 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; Latest headlines mildly bullish; The 4 marked dates; How this is calculated; How this is calculated; Show the case for and against (1 for, 0 against); What has been moving it recently; Key figures; Recent SEC filings 4 newest; Advanced research Optic's short-term signal score, all key statistics,; Read more; 5 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/digest/SPY, /api/earnings/SPY, /api/extras/SPY, /api/fair-value/SPY, /api/framework/SPY, /api/health, /api/logo/SPY, /api/longterm/SPY, /api/quote/SPY, /api/segments/SPY, /api/session, /api/session/SPY, /api/stage, /api/ticker/SPY, /api/validation
#### signed in: 942 words, 130 visible controls, 3 tables, 1 charts, 14 folds (0 open), settle 2833 ms, 20 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Overview / What State Street SPDR S&P 500 ETF Trust is / The past year / Optic Score / SHORT TERM: 2 TO 8 WEEKS / LONG TERM: SEVERAL YEARS / Bull case and bear case / Bull case / Bear case / The long-term record / What changed lately / What should I look at next? / COMING UP / RESEARCH STEPS / More on State Street SPDR S&P 500 ETF Trust / Optic's read / Key stats / The rest of this ticker / Latest headlines / How this page is built
- a (23 distinct): Skip to content; Optic Terminal, Home; Settings; What State Street SPDR S&P 500 ETF (SPY) Bought: NVIDIA Lead; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; Exchange-Traded Funds Higher, Equity Futures Mixed Pre-Bell ; S&P 500, Nasdaq Jump On Chipmaker Strength As Investors Eye ; Stocks Without AI Are Beating the S&P 500 by 6 Points This M; Jeff Bezos Says Retirees Should Buy the S&P 500 Instead of A; All headlines on News; The full breakdown, on Options; The full breakdown, on Investing; Evidence for: Share price up 13% over the period shown; See how the price compares with its own valuation history In; Read the 9 latest headlines News →; Compare SPY side by side with a competitor Compare →; SC 13G; Chart94%of its 52-week range; OptionsNeutralno conviction; Earningsn/ano date published; News9headlines, mildly bullish; Investing24.5trailing P/E, valuation and holding case; All 9 headlines
- button (30 distinct): Collapse; Fold What the company is; Fold The past year; 3M; 6M; 1Y; Measure between two dates; What is it? A large blend fund from State Street Investment ; What do its holdings cost? 24.5 times trailing earnings. Pri; How has the share price moved? Up 12.7% over a year. From 68; What does it pay? 0.99% a year. Distributions pass on what t; Fold Optic Score; Fold Bull case and bear case; Fold The long-term record; Fold What changed lately; Ask Milo about this; Oct 28 No meaningful change: moved +0.3% (within its usual r; Oct 27 What State Street SPDR S&P 500 ETF (SPY) Bought: NVID; Fold What should I look at next?; Ask Milo a question about SPY Ask Milo →; Fold More on the company; P/E (trailing); Dividend yield; Open price; High last session; Low last session; Volume; Average volume; 52-week high; 52-week low
- button[switch] (1 distinct): Show advanced analysis
- summary (11 distinct): Latest headlines mildly bullish; The 4 marked dates; How this is calculated; Show the case for and against (1 for, 0 against); What has been moving it recently; Key figures; Recent SEC filings 4 newest; Advanced research Optic's short-term signal score, all key s; Read more; 5 sources; How this works
- g[button] (4 distinct): Ex-dividend date, Dec 19, 2025; Ex-dividend date, Mar 20, 2026; Ex-dividend date, Jun 18, 2026; Ex-dividend date, Sep 18, 2026
- Table in "The 4 marked dates": 4 rows; columns: Date, Marked, What
- Table in "How this is calculated": 4 rows; columns: Input, Reading, Weight, Points
- Table in "How this is calculated": 2 rows; columns: Factor, Model points, What it found
- Folds: ; Panels; Latest headlines mildly bullish; The 4 marked dates; How this is calculated; How this is calculated; Show the case for and against (1 for, 0 against); What has been moving it recently; Key figures; Recent SEC filings 4 newest; Advanced research Optic's short-term signal score, all key statistics,; Read more; 5 sources; How this works
- Charts: The past year 1054x316
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/digest/SPY, /api/earnings/SPY, /api/extras/SPY, /api/fair-value/SPY, /api/framework/SPY, /api/health, /api/logo/SPY, /api/longterm/SPY, /api/quote/SPY, /api/segments/SPY, /api/session, /api/session/SPY, /api/stage, /api/theses, /api/ticker/SPY, /api/validation, /api/watchlists

### `#/SPY/chart` (spy-chart)

#### guest: 208 words, 99 visible controls, 0 tables, 1 charts, 2 folds (0 open), settle 2021 ms, 10 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Chart
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (52 distinct): Collapse; Layers 2; Chart read; Reset; Fit; Candles; Line; Area; Select and move; Trend line; Ray; Horizontal line; Vertical line; Channel; Rectangle; Fibonacci retracement; Fibonacci extension; Pitchfork; Arrow; Text note; Measure; Risk / reward; Position size; Snap to candles; Undo the last drawing change; Redo; Delete the selected drawing; Remove all drawings on SPY; Explain; Full screen; 4 overlays; Measure between two bars; Remove the Volume pane; Watch; Alerts; News; Analysts; Season; Notes; Insiders; Reports; Checklist; Stop check; Options; Key levels ...
- summary (1 distinct): Indicators 1
- input(search) (1 distinct): Find an indicator
- input(checkbox) (1 distinct): on
- select(select-one) (2 distinct): 1m 5m 15m 30m 1h 4h 1D 1W {1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W}; Regular hours Extended hours {Regular hours, Extended hours}
- svg[slider] (1 distinct): Bars shown, from the whole history
- Folds: ; Indicators 1
- Charts: Indicators 1 898x532
- API: /api/ai-allowance, /api/auth/me, /api/build, /api/health, /api/intraday/SPY, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY
#### signed in: 213 words, 101 visible controls, 0 tables, 1 charts, 2 folds (0 open), settle 0 ms, 11 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Chart
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (52 distinct): Collapse; Layers 2; Chart read; Reset; Fit; Candles; Line; Area; Select and move; Trend line; Ray; Horizontal line; Vertical line; Channel; Rectangle; Fibonacci retracement; Fibonacci extension; Pitchfork; Arrow; Text note; Measure; Risk / reward; Position size; Snap to candles; Undo the last drawing change; Redo; Delete the selected drawing; Remove all drawings on SPY; Explain; Full screen; 4 overlays; Measure between two bars; Remove the Volume pane; Watch; Alerts; News; Analysts; Season; Notes; Insiders; Reports; Checklist; Stop check; Options; Key levels ...
- summary (1 distinct): Indicators 1
- input(search) (1 distinct): Find an indicator
- input(checkbox) (1 distinct): on
- select(select-one) (2 distinct): 1m 5m 15m 30m 1h 4h 1D 1W {1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W}; Regular hours Extended hours {Regular hours, Extended hours}
- svg[slider] (1 distinct): Bars shown, from the whole history
- Folds: ; Indicators 1
- Charts: Indicators 1 898x518
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/intraday/SPY, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY, /api/watchlists

### `#/SPY/earnings` (spy-earnings)

#### guest: 120 words, 34 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 2051 ms, 9 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Earnings
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (1 distinct): Collapse
- Folds: 
- API: /api/ai-allowance, /api/auth/me, /api/earnings/SPY, /api/health, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY
- Notes shown: No earnings for SPY SPY has no earnings data. No scheduled report, no reported history and
#### signed in: 125 words, 36 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 12 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Earnings
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (1 distinct): Collapse
- Folds: 
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings/SPY, /api/health, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY, /api/watches/hits, /api/watchlists
- Notes shown: No earnings for SPY SPY has no earnings data. No scheduled report, no reported history and

### `#/SPY/financials` (spy-financials)

#### guest: 97 words, 37 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 7 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Financials / Financials do not apply to SPY
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; Open Investing; Open Overview
- button (2 distinct): Collapse; Fold Financials do not apply to SPY
- Folds: 
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY
#### signed in: 102 words, 39 visible controls, 0 tables, 0 charts, 1 folds (0 open), settle 0 ms, 9 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Financials / Financials do not apply to SPY
- a (5 distinct): Skip to content; Optic Terminal, Home; Settings; Open Investing; Open Overview
- button (2 distinct): Collapse; Fold Financials do not apply to SPY
- Folds: 
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/watchlists

### `#/SPY/investing` (spy-investing)

#### guest: 548 words, 77 visible controls, 1 tables, 2 charts, 3 folds (0 open), settle 0 ms, 14 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Investing / Long-term trend score, from price history / Return and risk / Weekly structure / Drawdown, daily / What its holdings cost / Valuation and accumulation levels Advanced
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (23 distinct): Collapse; Fold Long-term trend score, from price history; Ask Milo about this score; Fold Return and risk; Correlation; Fold Weekly structure; Weekly; Monthly; 1Y; 3Y; 5Y; 10Y; All; Candles; Line; Area; Measure between two bars; RSI; Fold Drawdown, daily; Measure between two dates; Fold What its holdings cost; P/E; Open Valuation and accumulation levels
- summary (1 distinct): Technical levels 1
- input(checkbox) (1 distinct): on
- Table in "Long-term trend score, from price history": 3 rows; columns: Factor, Type, Raw points, Why
- Folds: ; Panels; Technical levels 1
- Charts: Weekly structure 1054x441; Drawdown, daily 1054x170
- API: /api/ai-allowance, /api/auth/me, /api/fair-value/SPY, /api/framework/SPY, /api/health, /api/logo/SPY, /api/longterm/SPY, /api/pe-history/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/validation, /api/valuation-inputs/SPY, /api/valuation/SPY
#### signed in: 553 words, 79 visible controls, 1 tables, 2 charts, 3 folds (0 open), settle 0 ms, 19 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Investing / Long-term trend score, from price history / Return and risk / Weekly structure / Drawdown, daily / What its holdings cost / Valuation and accumulation levels Advanced
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (23 distinct): Collapse; Fold Long-term trend score, from price history; Ask Milo about this score; Fold Return and risk; Correlation; Fold Weekly structure; Weekly; Monthly; 1Y; 3Y; 5Y; 10Y; All; Candles; Line; Area; Measure between two bars; RSI; Fold Drawdown, daily; Measure between two dates; Fold What its holdings cost; P/E; Open Valuation and accumulation levels
- summary (1 distinct): Technical levels 1
- input(checkbox) (1 distinct): on
- Table in "Long-term trend score, from price history": 3 rows; columns: Factor, Type, Raw points, Why
- Folds: ; Panels; Technical levels 1
- Charts: Weekly structure 1054x441; Drawdown, daily 1054x170
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/fair-value/SPY, /api/framework/SPY, /api/health, /api/logo/SPY, /api/longterm/SPY, /api/pe-history/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/validation, /api/valuation-inputs/SPY, /api/valuation-models, /api/valuation/SPY, /api/valuations, /api/watches/hits, /api/watchlists

### `#/SPY/news` (spy-news)

#### guest: 400 words, 49 visible controls, 0 tables, 1 charts, 3 folds (0 open), settle 1826 ms, 8 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , News / News and catalysts / Catalyst types found / About SPY 1 / Market context 8
- a (12 distinct): Skip to content; Optic Terminal, Home; Settings; What State Street SPDR S&P 500 ETF (SPY) Bought: NVIDIA Lead; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; Exchange-Traded Funds Higher, Equity Futures Mixed Pre-Bell ; S&P 500, Nasdaq Jump On Chipmaker Strength As Investors Eye ; Stocks Without AI Are Beating the S&P 500 by 6 Points This M; Jeff Bezos Says Retirees Should Buy the S&P 500 Instead of A; Stock Market: Will S&P 500 Open Up or Down Today?; Micron’s Long-Term Returns Crushed the S&P 500. Does the Rec; Intuitive Machines Surges 9% as Small-Cap Space Selloff Reve
- button (5 distinct): Collapse; Ask Milo about the news; Macro event 2, bullish; Earnings 1, neutral; Policy / supply chain 1, bullish
- summary (2 distinct): How this works; How these are ranked
- Folds: ; How this works; How these are ranked
- Charts: News and catalysts 1054x176
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY
#### signed in: 403 words, 51 visible controls, 0 tables, 1 charts, 3 folds (0 open), settle 2888 ms, 10 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , News / News and catalysts / Catalyst types found / About SPY 1 / Market context 8
- a (12 distinct): Skip to content; Optic Terminal, Home; Settings; What State Street SPDR S&P 500 ETF (SPY) Bought: NVIDIA Lead; S&P 500, Nasdaq Futures Dip As Weaker-Than-Expected Alphabet; Exchange-Traded Funds Higher, Equity Futures Mixed Pre-Bell ; S&P 500, Nasdaq Jump On Chipmaker Strength As Investors Eye ; Stocks Without AI Are Beating the S&P 500 by 6 Points This M; Jeff Bezos Says Retirees Should Buy the S&P 500 Instead of A; Stock Market: Will S&P 500 Open Up or Down Today?; Micron’s Long-Term Returns Crushed the S&P 500. Does the Rec; Intuitive Machines Surges 9% as Small-Cap Space Selloff Reve
- button (5 distinct): Collapse; Ask Milo about the news; Macro event 2, bullish; Earnings 1, neutral; Policy / supply chain 1, bullish
- summary (2 distinct): How this works; How these are ranked
- Folds: ; How this works; How these are ranked
- Charts: News and catalysts 1054x176
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/logo/SPY, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY, /api/watchlists

### `#/SPY/options` (spy-options)

#### guest: 692 words, 93 visible controls, 1 tables, 2 charts, 5 folds (0 open), settle 4530 ms, 10 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Options / Pick a contract / Research contracts / Position builder / What options are pricing / How value moves
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (34 distinct): Collapse; Expect a rise; Expect a fall; 7 days; 14 days; 30 days; 60 days; Find contracts; Calls; Puts; More columns; open interest; Long call; Long put; Bull call spread; Bear put spread; Covered call; Cash-secured put; Straddle; Strangle; Iron condor; Call calendar; Apply; Fold What options are pricing; Ask Milo about implied volatility; ATM; delta; dividend; Fold How value moves; Call; Put; 45 days; gamma; implied volatility
- button[tab] (3 distinct): Contracts and pricing; Positioning and flow; Setups and strategy
- input(text) (6 distinct): Most premium at risk, in dollars; Target price for the stock, optional; Price at which the idea is wrong, optional; 0.25; 0.65; Halfway
- input(checkbox) (1 distinct): on
- select(select-one) (4 distinct): Expiry for the table and the position builder {Oct 29, 0 days, Oct 30, 1 day, Nov 2, 4 days, Nov 3, 5 days, Nov 4, 6 days, Nov 5, 7 days, Nov 6, 8 days, Nov 13, 15 days, Nov 20, 22 days, m, Nov 27, 29 days, Nov 30, 32 days, Dec 4, 36 days}; Any Far, .10 to .30 Middle, .30 to .50 At the money, .40 to  {Any, Far, .10 to .30, Middle, .30 to .50, At the money, .40 , Deep, .60 to .90}; Any 5% 10% 25% {Any, 5%, 10%, 25%}; Any 100 500 1,000 {Any, 100, 500, 1,000}
- summary (3 distinct): Costs and timing; Compare expiries; How this works
- input(number) (1 distinct): Implied volatility, percent
- Table in "Compare expiries": 4 rows; columns: Expiry, Days, ATM IV, Straddle move, 1-SD move, Put skew, Quoted, Report inside
- Folds: ; Costs and timing; Compare expiries; How this works; How this works
- Charts: How value moves 1054x200; How value moves 1054x200
- API: /api/ai-allowance, /api/auth/me, /api/earnings/SPY, /api/health, /api/logo/SPY, /api/options/SPY/research, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY
- Notes shown: No usable quotes for this expiry The option chain the feed returned has no quotes and no o
#### signed in: 697 words, 86 visible controls, 1 tables, 2 charts, 5 folds (0 open), settle 2060 ms, 13 API paths
- Headings: SPY State Street SPDR S&P 500 ETF Trust , Options / Pick a contract / Research contracts / Position builder / What options are pricing / How value moves
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (28 distinct): Collapse; Expect a rise; Expect a fall; 7 days; 14 days; 30 days; 60 days; Find contracts; Calls; Puts; More columns; Long call; Long put; Bull call spread; Bear put spread; Covered call; Cash-secured put; Straddle; Strangle; Iron condor; Call calendar; Apply; Fold What options are pricing; Ask Milo about implied volatility; Fold How value moves; Call; Put; 45 days
- button[tab] (3 distinct): Contracts and pricing; Positioning and flow; Setups and strategy
- input(text) (6 distinct): Most premium at risk, in dollars; Target price for the stock, optional; Price at which the idea is wrong, optional; 0.25; 0.65; Halfway
- input(checkbox) (1 distinct): on
- select(select-one) (4 distinct): Expiry for the table and the position builder {Oct 29, 0 days, Oct 30, 1 day, Nov 2, 4 days, Nov 3, 5 days, Nov 4, 6 days, Nov 5, 7 days, Nov 6, 8 days, Nov 13, 15 days, Nov 20, 22 days, m, Nov 27, 29 days, Nov 30, 32 days, Dec 4, 36 days}; Any Far, .10 to .30 Middle, .30 to .50 At the money, .40 to  {Any, Far, .10 to .30, Middle, .30 to .50, At the money, .40 , Deep, .60 to .90}; Any 5% 10% 25% {Any, 5%, 10%, 25%}; Any 100 500 1,000 {Any, 100, 500, 1,000}
- summary (3 distinct): Costs and timing; Compare expiries; How this works
- input(number) (1 distinct): Implied volatility, percent
- Table in "Compare expiries": 4 rows; columns: Expiry, Days, ATM IV, Straddle move, 1-SD move, Put skew, Quoted, Report inside
- Folds: ; Costs and timing; Compare expiries; How this works; How this works
- Charts: How value moves 1054x200; How value moves 1054x200
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/earnings/SPY, /api/health, /api/logo/SPY, /api/options/SPY/research, /api/quote/SPY, /api/session, /api/session/SPY, /api/ticker/SPY, /api/watches/hits, /api/watchlists
- Notes shown: No usable quotes for this expiry The option chain the feed returned has no quotes and no o

### `#/terms` (terms)

#### guest: 816 words, 23 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Terms of use / Agreeing to these terms / What Optic is / Who can use it / Your account / Plans and payment / Using Optic fairly / The data and Milo / Linking a brokerage / Your content / Availability and changes / No warranty / Limits of liability / Ending / Law and disputes / General / Changes and contact
- a (6 distinct): Skip to content; Optic Terminal, Home; Settings; Privacy policy; terms and conditions; theopticterminal@gmail.com
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 816 words, 25 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Terms of use / Agreeing to these terms / What Optic is / Who can use it / Your account / Plans and payment / Using Optic fairly / The data and Milo / Linking a brokerage / Your content / Availability and changes / No warranty / Limits of liability / Ending / Law and disputes / General / Changes and contact
- a (6 distinct): Skip to content; Optic Terminal, Home; Settings; Privacy policy; terms and conditions; theopticterminal@gmail.com
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches/hits, /api/watchlists

### `#/usage` (usage)

#### guest: 21 words, 20 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Claude usage
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (1 distinct): Collapse
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
#### signed in: 414 words, 25 visible controls, 2 tables, 0 charts, 0 folds (0 open), settle 0 ms, 7 API paths
- Headings: Claude usage / Latest calls
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (1 distinct): Collapse
- Table in "Latest calls": 3 rows; columns: Feature, Today, 7 days, 30 days, Calls, Unused, Failed
- Table in "Latest calls": 25 rows; columns: When, Feature, Model, Input, Output, Cost, Result
- API: /api/ai-allowance, /api/ai/usage, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watchlists

### `#/watchlist` (watchlist)

#### guest: 63 words, 25 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 4 API paths
- Headings: Watchlist
- a (4 distinct): Skip to content; Optic Terminal, Home; Settings; Sign in
- button (2 distinct): Collapse; Add
- input(text) (1 distinct): Add a ticker, such as MSFT
- API: /api/ai-allowance, /api/auth/me, /api/health, /api/session
- Notes shown: You are not following anything yet Add a ticker below to start your watchlist.
#### signed in: 254 words, 48 visible controls, 0 tables, 0 charts, 0 folds (0 open), settle 0 ms, 9 API paths
- Headings: Watchlist
- a (3 distinct): Skip to content; Optic Terminal, Home; Settings
- button (22 distinct): Collapse; Main Watchlist 6; New list; Rename; Add; All; Bullish; Bearish; Moved 2%+; Reorder; TSLA, 404.22, −0.80% today, Leading the market, Bullish. Ope; Remove TSLA from Main Watchlist; NVDA, 215.38, −1.17% today, Bearish. Open the detail; Remove NVDA from Main Watchlist; AAPL, 343.83, −0.94% today, Neutral. Open the detail; Remove AAPL from Main Watchlist; QQQ, 725.61, +0.60% today, Neutral. Open the detail; Remove QQQ from Main Watchlist; SPY, 772.31, +0.34% today, Neutral. Open the detail; Remove SPY from Main Watchlist; PCRX, 36.39, −0.03% today, Bullish. Open the detail; Remove PCRX from Main Watchlist
- input(text) (1 distinct): Add a ticker, such as MSFT
- input(search) (1 distinct): Find in this list
- select(select-one) (1 distinct): Biggest movers Gainers Losers Something changed Volume again {Biggest movers, Gainers, Losers, Something changed, Volume against ave, Next earnings, Optic signal, A-Z, My order}
- API: /api/ai-allowance, /api/auth/me, /api/brokerage/status, /api/health, /api/session, /api/watches, /api/watchlist, /api/watchlist/earnings, /api/watchlists

### `#/workspace` (workspace-alias)

#### guest: 1312 words, 217 visible controls, 3 tables, 1 charts, 16 folds (0 open), settle 505 ms, 14 API paths
- Headings: Good morning / New to Optic? Three ways to start / Markets at a glance / Market conditions / Expected move / Sector heatmap / Quote and chart / Watchlist / Economic calendar / Earnings this week / What matters today / Market news / Optic Desk / What could happen next / Today's reports / Moved most this month
- a (16 distinct): Skip to content; Optic Terminal, Home; Settings; Apple · AAPL; NVIDIA · NVDA; Read today's market; S&P 500 7,744 +0.28% Index points; Nasdaq 100 29,813 +0.55% Index points; Russell 2000 2,831 +0.41% Index points; VIX 16.91 −3.48% Volatility index; US 10Y 5.05% +5 bp Yield, change in basis points; WTI Crude 101.24 −1.50% Dollars a barrel Since Wed's settle;; Gold 4,057 +0.13% Dollars an ounce Since Wed's settle; Wed −; Bitcoin 80,334 −1.14% Dollars; SPY; See the whole week, by day
- button (122 distinct): Collapse; ticker; Search for a company; watchlist; Follow Apple AAPL; Follow NVIDIA NVDA; Follow Microsoft MSFT; Follow S&P 500 fund SPY; Not now; Customize; risk; ATR; 1 day; 1 week; 1 month; Technology XLK +0.80%; Financials XLF +0.45%; Energy XLE +0.35%; Industrials XLI +0.34%; Health Care XLV +0.30%; Materials XLB +0.16%; Consumer Discretionary XLY −0.10%; Consumer Staples XLP −0.36%; Communication Services XLC −0.43%; Real Estate XLRE −0.73%; Utilities XLU −0.84%; Update panels; NVDA; 3M; 6M; 1Y; Measure between two dates; This week; Next week; VZ; HOOD; KO; PYPL; SOFI; GOOGL; MSFT; CMG; F; FDX; KLAC ...
- button[tab] (4 distinct): Market Overview; Options Research; Long-Term Investing; My Desk
- summary (4 distinct): How these readings are built; How this is sorted and timed; The whole desk; What this does not tell you (3)
- input(text) (1 distinct): SPY
- Table in "How these readings are built": 12 rows; columns: Factor, Reading, Effect on the score
- Table in "Earnings this week": 32 rows; columns: Day, Company, EPS est., Revenue est., Implied move
- Table in "Moved most this month": 12 rows; columns: Ticker, 1 month, Volume
- Folds: ; ; How these readings are built; ; ; ; ; ; ; ; How this is sorted and timed; ; ; The whole desk; What this does not tell you (3); 
- Charts: Quote and chart 698x230
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/brokerage/status, /api/earnings-week, /api/health, /api/home, /api/market, /api/priority, /api/quote/SPY, /api/scanners/movers, /api/sentiment, /api/session, /api/take-chart/SPY
#### signed in: 1206 words, 212 visible controls, 4 tables, 1 charts, 16 folds (0 open), settle 2821 ms, 17 API paths
- Headings: Good morning, Demo / Markets at a glance / Market conditions / Expected move / Sector heatmap / Quote and chart / Watchlist / Economic calendar / Earnings this week / What matters today / Market news / Optic Desk / What could happen next / Today's reports / Moved most this month
- a (13 distinct): Skip to content; Optic Terminal, Home; Settings; S&P 500 7,744 +0.28% Index points; Nasdaq 100 29,813 +0.55% Index points; Russell 2000 2,831 +0.41% Index points; VIX 16.91 −3.48% Volatility index; US 10Y 5.05% +5 bp Yield, change in basis points; WTI Crude 101.19 −1.55% Dollars a barrel Since Wed's settle;; Gold 4,055 +0.09% Dollars an ounce Since Wed's settle; Wed −; Bitcoin 80,259 −1.23% Dollars; AAPL; See the whole week, by day
- button (117 distinct): Collapse; Customize; risk; 1 day; 1 week; 1 month; Technology XLK +0.80%; Financials XLF +0.45%; Energy XLE +0.35%; Industrials XLI +0.34%; Health Care XLV +0.30%; Materials XLB +0.16%; Consumer Discretionary XLY −0.10%; Consumer Staples XLP −0.36%; Communication Services XLC −0.43%; Real Estate XLRE −0.73%; Utilities XLU −0.84%; Update panels; SPY; NVDA; TSLA; QQQ; PCRX; 3M; 6M; 1Y; Measure between two dates; AAPL; This week; Next week; VZ; HOOD; KO; PYPL; SOFI; GOOGL; MSFT; CMG; F; FDX; KLAC; NOW; PSX; VRT; AMZN ...
- button[tab] (4 distinct): Market Overview; Options Research; Long-Term Investing; My Desk
- summary (4 distinct): How these readings are built; How this is sorted and timed; The whole desk; What this does not tell you (3)
- input(text) (1 distinct): AAPL
- Table in "How these readings are built": 12 rows; columns: Factor, Reading, Effect on the score
- Table in "Watchlist": 6 rows; columns: Ticker, Price, Day, Changed
- Table in "Earnings this week": 32 rows; columns: Day, Company, EPS est., Revenue est., Implied move
- Table in "Moved most this month": 12 rows; columns: Ticker, 1 month, Volume
- Folds: ; ; How these readings are built; ; ; ; ; ; ; ; How this is sorted and timed; ; ; The whole desk; What this does not tell you (3); 
- Charts: Quote and chart 698x230
- API: /api/ai-allowance, /api/auth/me, /api/brief, /api/brokerage/status, /api/earnings-week, /api/health, /api/home, /api/market, /api/priority, /api/quote/AAPL, /api/scanners/movers, /api/sentiment, /api/session, /api/take-chart/AAPL, /api/watches/hits, /api/watchlist, /api/watchlists

