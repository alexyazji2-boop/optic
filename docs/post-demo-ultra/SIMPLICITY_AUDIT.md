# Simplicity audit (Phase 04)

Post-demo overhaul, directive 04 ("Radical simplicity and first-time user experience"). Branch `post-demo-ultra`,
worktree `~/Optic/wt-ultra`, measured on the local server (launch config `optic-ultra`, :8250). Nothing was deployed.

**What this is and is not.** Every primary route was reviewed against the directive's nine first-time-user
questions and measured in a browser. The questions are usability heuristics answered by the engineer, not results
from real users; no reader was tested, and nothing here claims that readers now understand more (directive 04,
section 1). The numbers count what renders: words, controls, cards and folds a reader can see.

## How it was measured

- **Tool.** `~/Optic/work/post-demo-ultra-2026-10-29/tools/density.py`, headless Chrome 152, guest, fresh
  profile, dark theme. Each route is opened and settled for 2.5 s, then the tool counts the visible words on the
  first screen and on the whole page, the headings, the interactive controls (also those on the first screen),
  icon-only buttons, cards and sections, open and closed folds, tables, charts, page height and sideways overflow.
  It also takes a first-screen screenshot.
- **Before** is `2f6a548`, the commit Phase 03 ended on, served from its own clean worktree on :8252 with its own
  copy of the data. **After** is the Phase 04 tree on :8250. Both runs used live delayed market data on Thursday
  2026-10-29 during the regular session, minutes apart, so a few counts move with the data (a headline more or less).
  Changes of under about 30 words on a route that Phase 04 did not touch are that noise.
- **Sizes.** 1440×900 and 390×844 for the measured comparison; 1024×768 and 768×1024 for the responsive check.
- **A correction to the tool before any figure was used (D-022).** In Chrome 152 the contents of a closed fold
  still report a layout box, so the first version counted folded text as visible. Every figure here comes from the
  corrected tool, which also requires `checkVisibility()`. The first run is kept as
  `phase04/superseded-before-rectvis`; on NVDA it counted 4,749 words where 1,417 are visible.
- **Dead clicks.** `tools/deadclicks.py` presses every visible control on each route with a real mouse event and
  records any that change nothing (no DOM change, route, request, focus or state attribute). It had the same flaw and
  the same correction.

Evidence folders, all under `~/Optic/work/post-demo-ultra-2026-10-29/phase04/`:
- `before-2f6a548/` (1440 and 390) and `after/` (1440, 1024, 768 and 390), each with `density.json` and a
  first-screen PNG per route and size.
- `before-secondary/` and `after-secondary/`, for the 13 secondary routes.
- `pairs-w1440-*.jpg` and `pairs-w390-*.jpg` (before and after side by side); `after-w1024-sheet.jpg` and
  `after-w768-sheet.jpg`.
- `dead-after/` (the ten reported routes, after the first fixes) and `dead-final/` (the changed routes, final code),
  from the dead-click runs.
- `phase03-regression/` (Phase 03's scenarios run again).

## Summary of what changed

| Change | Why | Where |
|---|---|---|
| Density is its own setting, Simple or Advanced, separate from Milo's knowledge level | One switch changed both what pages show and how Milo explains (BUG-002) | `core/prefs.js`, `ui/sections.js`, Settings, the Dossier switch (D-019) |
| Home opens 6 of 13 panels in Simple (Market Overview), 4 of 7 (Options), 5 of 8 (Long-term); the rest one press away in Add panel, all of them in Advanced | First visit showed 12 panels and 186 controls (BUG-005) | `pages/workspace.js` (D-020) |
| Analysts shows the newest 40 actions, then "Show all N" | 2,927 words and a 14,629 px page for one week's actions | `pages/analysts.js`, `ui/table.js` |
| Explore's catalogue of every screen and Retirement's fund table and correlation matrix fold in Simple and open in Advanced | Reference detail above the reader's first need | `ui/states.js` `simpleFold`, `pages/explore.js`, `pages/retirement.js` |
| Read says why reports matter once, not on each of 20 rows | Repetition (BUG-076) | `pages/read.js` |
| The Overview's method and policy ids moved into "How this works" | Traceability strings in headline copy (BUG-009) | `pages/overview-research.js` |
| The liquidity grade's words are Liquid, Fair, Thin, and Too wide to trade or No usable quote, with "spread 3.2%" beside them | "Tight" and "Wide" named the spread, but the grade also weighs activity (BUG-010) | `app/analytics/liquidity.py`, `pages/options.js` (D-024) |
| One name per model: Optic's market score (Home, Macro), Index score (Read, said to differ), Where each index stands (Indices); one label set for the expected move | "Regime" named three models (registry B X-6, X-7) | macro, read, indices, workspace |
| A time on the five pages that had none; the Desk's footer says when its words were written | Registry B X-10, H-2 | `ui/states.js` `asOfLine`/`whenText`, macro, indices, explore, instrument, compare, market-shared, workspace, `app/main.py` |
| Calmer colour: heatmap tint at most 28% on a fixed scale; analyst ratings in ink | Colour drew the eye where no action is implied (BUG-077) | `css/pages.css`, `pages/workspace.js`, `pages/analysts.js` |
| Presses that did nothing now say why: Compare's chips (hidden when full), "Update panels" (already shown), the chart watchlist's empty Add | BUG-075 | compare, workspace, chart-widgets |
| One set of Follow buttons on Home's first screen; the first-visit card says in one line what Optic is, and no longer points at a panel Simple hides | Duplication found in the before and after review; directive 04 section 4 | `pages/workspace.js` |
| The unrouted Home page and the workspace's handlers for undrawn controls removed, about 345 lines | Dead code that had been edited as if live (registry B X-2) | `pages/home.js`, `pages/workspace.js` (D-021) |
| Text arrows on the Overview's "What should I look at next?" replaced by the line icon | Design standard: icons, not text glyphs | `pages/overview-research.js`, `css/pages.css` |

## 1. First-time user audit (heuristic)

Each row answers the directive's questions for one screen: what it is for, what to look at first, what the main
number is, why it matters, what to do next, which labels need financial knowledge, how much reading it asks, how many
actions compete, and whether the main benefit shows within about 30 seconds. "Yes" in the last column is the
engineer's judgement, not a measurement.

| Screen | For | Look at first | Main number | Why it matters | What next | Labels that need knowledge | Visible words, 1440 | Controls on the first screen | Benefit in about 30 s |
|---|---|---|---|---|---|---|---|---|---|
| Home `#/` | A start point and the day's market | The first-visit card, then Markets at a glance | Index levels and the day's moves | The day's direction in one strip | Search a company, read the market, follow a starter | VIX, US 10Y (unit lines say what each is); "linked panels" (explained under the box) | 1,872 → 672 | 46 → 39 | Yes |
| Dossier start `#/dossier` | Opening a company | The search box | None | n/a | Type a name or ticker; recent companies | None | 39 | 6 | Yes |
| Overview `#/NVDA` | One company's research | The header (price, move), then what the company does | The share price and day's move | What the business is and how its price has moved | The tabs, Watch, Ask Milo, the next-step links | Stage, Optic Score, grades, P/E (glossary words) | 1,417 → 1,409 | 41 → 40 | Partly: the first screen yes, the rest is long (Phase 06) |
| Chart `#/NVDA/chart` | Price history | The chart | The last price and the bar readout | How the price got here | Range, style, indicators | Indicator names | 193 | 65 | Yes |
| Options `#/NVDA/options` | What options price | The one-line read and six option figures | The implied move | How far the market prices the stock to move | Research and screen contracts | Implied move, IV, skew, dealer gamma, delta (glossary words) | 1,096 → 1,111 | 28 | Partly: needs options knowledge |
| Investing `#/NVDA/investing` | The long-term view | The long-term trend score | The trend score and returns | Long-run trend and valuation against history | Scenarios, the DCF | CAGR, drawdown, multiples, fair value | 2,118 → 2,147 | 30 | Partly: long (Phase 06) |
| Earnings `#/NVDA/earnings` | The coming report | Optic's reading of the setup | The report date and the priced move | Reports move prices | Earlier reports, revisions | EPS, estimate revisions, implied move | 1,013 | 33 | Partly |
| Financials `#/NVDA/financials` | The statements | The summary | Revenue, margins | What the business earns | Statements, filings | Statement terms | 2,146 | 36 | Partly: long (Phase 06) |
| News `#/NVDA/news` | Headlines and catalysts | The newest headlines | None | What changed lately | Open a story | Short interest (glossary word) | 454 → 423 | 18 → 21 | Yes |
| Fund Overview `#/SPY` | A fund's research | The header and what the fund holds | Price and day's move | What the fund is | The tabs | Expense, holdings terms | 1,071 → 1,070 | 38 | Partly: long (Phase 06) |
| Compare `#/compare?t=NVDA,AMD` | Two to four names side by side | The boxes and Optic's take | Each name's score per horizon | Which name leads which horizon, said not to predict returns | Change names, Ask Milo | Swing, position and long-term setup; RSI | 1,303 → 1,316 | 8 | Partly |
| Read `#/read` | The day's market brief | Today's Read headline | The index moves | What moved and why, in a paragraph | More from today, the tabs | VIX, catalysts | 1,202 → 1,160 | 12 | Yes |
| Macro `#/macro` | Conditions across assets | The market today, in brief | Optic's market score | Whether inputs lean to risk or caution | In depth tabs | Risk-on, curve, VIX, breadth | 365 → 373 | 7 | Partly: a specialist page |
| Indices `#/indices` | Long-run index trends | What the indices say | How many indices are above their 200-week average | Where the long cycle stands | Index funds, Index Read | 200-week and 40-week averages, dispersion | 448 → 468 | 11 | Partly |
| Instrument `#/instrument/^GSPC` | An index, rate, commodity or coin | The tiles and the chart | The last price | Its level and trend | Range, style, Ask Milo | RSI, 200-day | 96 → 104 | 11 | Yes |
| Earnings week `#/earnings` | Who reports this week | The list by day | Report dates, priced moves | Reports move prices | Open a company | Consensus, EPS | 598 | 14 | Yes |
| Explore `#/explore` | Ways to find stocks | Start with a question | The top names for each question | A starting list, said not to be a recommendation | See the full list (Scan) | Few | 1,255 → 619 | 16 | Yes |
| Scan `#/scan` | Screening | Find stocks | Matches per screen | Narrow the market to a list | Run a screen, add filters | Filter names | 683 | 26 | Partly |
| Insiders `#/insiders` | Insider and House trades | The filters and newest rows | Trade size and date | Who bought or sold, and when it was disclosed | Filter, open a company | Form 4, disclosure lag | 1,758 | 23 | Partly |
| Analysts `#/analysts` | Rating and target changes | The newest rows | Target and action | What firms changed this week | Filter, Show all, open a company | Initiation, price target | 2,927 → 701 | 32 | Yes |
| Optic Portfolio `#/portfolio` | Optic's simulated book | Three simulated accounts | Each account's return | How the rules have done, simulated | Positions, track record | Shortlist, simulated (name proposal, section 5) | 528 | 19 | Partly |
| Paper Desk `#/paper` | Practice trades | Portfolio health and Open a trade | The paper book's value | Practice without money | Open a trade | Paper trade | 379 | 16 | Yes |
| Retirement `#/retirement` | An example Roth allocation | The model inputs | The example allocation | A rules-based example to compare with | Change horizon and risk | CAGR, drawdown, correlation | 1,631 → 1,171 | 10 | Partly |
| Brokerage `#/brokerage` (guest) | Linking a brokerage, read-only | What Optic can and cannot see | None for a guest | What linking does and does not do | Sign in | None | 241 | 2 | Yes |
| Watchlist `#/watchlist` | Followed names | The list (empty for a new guest) | Prices and moves | Your names in one place | Add a name | None | 96 | 6 | Yes |
| Alerts `#/alerts` | Price and signal alerts | Your alerts | None | Being told when something happens | Add an alert | None | 277 | 5 | Yes |
| Saved research `#/research` | Saved research | Start an investigation | None | Keeping your questions | Ask a question | None | 134 | 5 | Yes |
| Settings `#/settings` | Preferences and account | Account, then appearance | None | n/a | Change a setting | None | 577 → 606 | 10 | Yes |
| Sign in `#/signin` | Signing in | The form | None | n/a | Sign in or create an account | None | 41 | 7 | Yes |

## 2. Visual density: measured

Before is `2f6a548` and after is the Phase 04 tree, as "before → after"; a single number did not change.

| Route | Size | First-screen words | Visible words | Controls | Cards | Closed folds | Page height (px) |
|---|---|---|---|---|---|---|---|
| Home `#/` | 1440 | 359 → 303 | 1,872 → 672 | 186 → 71 | 12 → 5 | 16 → 8 | 3,427 → 2,149 |
| Dossier start `#/dossier` | 1440 | 39 | 39 | 6 | 2 | 0 | 901 |
| Overview `#/NVDA` | 1440 | 260 → 264 | 1,417 → 1,409 | 98 → 99 | 12 | 18 → 19 | 5,139 → 5,211 |
| Chart `#/NVDA/chart` | 1440 | 86 | 193 | 66 | 1 | 2 | 1,369 |
| Options `#/NVDA/options` | 1440 | 211 | 1,096 → 1,111 | 88 | 5 | 6 | 4,555 |
| Investing `#/NVDA/investing` | 1440 | 308 → 306 | 2,118 → 2,147 | 106 | 39 | 15 | 8,040 → 8,087 |
| Earnings `#/NVDA/earnings` | 1440 | 363 | 1,013 | 53 | 12 | 4 | 3,827 |
| Financials `#/NVDA/financials` | 1440 | 199 | 2,146 | 82 | 31 | 6 | 8,425 |
| News `#/NVDA/news` | 1440 | 122 → 144 | 454 → 423 | 29 → 30 | 1 | 3 | 2,575 → 2,405 |
| Fund Overview `#/SPY` | 1440 | 234 → 233 | 1,071 → 1,070 | 65 | 16 | 11 | 4,360 |
| Compare `#/compare?t=NVDA,AMD` | 1440 | 289 | 1,303 → 1,316 | 14 | 5 | 0 | 4,184 → 4,206 |
| Read `#/read` | 1440 | 238 | 1,202 → 1,160 | 43 | 2 | 1 | 3,376 → 3,330 |
| Macro `#/macro` | 1440 | 181 → 189 | 365 → 373 | 19 | 13 | 2 | 2,121 → 2,112 |
| Indices `#/indices` | 1440 | 203 → 212 | 448 → 468 | 19 | 6 | 0 | 2,269 |
| Instrument `#/instrument/^GSPC` | 1440 | 96 → 104 | 96 → 104 | 11 | 5 | 0 | 1,064 |
| Earnings week `#/earnings` | 1440 | 220 | 598 | 37 | 0 | 1 | 2,526 |
| Explore `#/explore` | 1440 | 260 | 1,255 → 619 | 68 → 50 | 8 | 0 → 1 | 3,776 → 2,678 |
| Scan `#/scan` | 1440 | 197 | 683 | 106 | 3 | 0 | 3,556 |
| Insiders `#/insiders` | 1440 | 178 | 1,758 | 146 | 1 | 0 | 2,064 |
| Analysts `#/analysts` | 1440 | 128 | 2,927 → 701 | 226 → 67 | 1 | 0 | 14,629 → 3,729 |
| Optic Portfolio `#/portfolio` | 1440 | 385 | 528 | 28 | 10 | 3 | 1,955 |
| Paper Desk `#/paper` | 1440 | 129 | 379 | 25 | 4 | 1 | 1,927 |
| Retirement `#/retirement` | 1440 | 192 | 1,631 → 1,171 | 33 → 22 | 18 | 0 → 2 | 5,026 → 3,903 |
| Brokerage `#/brokerage` (guest) | 1440 | 241 | 241 | 2 | 2 | 0 | 1,000 |
| Watchlist `#/watchlist` | 1440 | 96 | 96 | 6 | 0 | 0 | 901 |
| Alerts `#/alerts` | 1440 | 171 | 277 | 6 | 4 | 0 | 1,631 |
| Saved research `#/research` | 1440 | 134 | 134 | 5 | 2 | 0 | 901 |
| Settings `#/settings` | 1440 | 212 | 577 → 606 | 14 → 16 | 8 → 9 | 0 | 2,754 → 2,931 |
| Sign in `#/signin` | 1440 | 41 | 41 | 7 | 0 | 0 | 1,032 |
| Home `#/` | 390 | 123 → 122 | 390 → 278 | 58 → 37 | 13 → 6 | 14 → 6 | 3,728 → 2,632 |
| Dossier start `#/dossier` | 390 | 36 | 36 | 6 | 3 | 0 | 1,151 |
| Overview `#/NVDA` | 390 | 127 | 1,424 → 1,396 | 90 → 91 | 12 | 18 → 19 | 9,020 → 8,958 |
| Chart `#/NVDA/chart` | 390 | 53 | 165 | 34 | 1 | 3 | 1,700 |
| Options `#/NVDA/options` | 390 | 117 | 942 → 957 | 92 | 5 | 6 | 7,163 |
| Investing `#/NVDA/investing` | 390 | 209 | 2,139 | 101 | 39 | 15 | 14,333 |
| Earnings `#/NVDA/earnings` | 390 | 199 | 1,005 | 44 | 12 | 4 | 5,942 |
| Financials `#/NVDA/financials` | 390 | 94 | 2,043 | 62 | 31 | 7 | 13,067 |
| News `#/NVDA/news` | 390 | 98 → 97 | 439 → 415 | 21 | 1 | 3 | 3,413 → 3,307 |
| Fund Overview `#/SPY` | 390 | 137 | 1,063 | 58 | 16 | 11 | 7,099 |
| Compare `#/compare?t=NVDA,AMD` | 390 | 207 | 901 → 914 | 16 | 5 | 0 | 5,887 → 5,931 |
| Read `#/read` | 390 | 162 | 1,200 → 1,158 | 42 | 2 | 1 | 6,248 → 6,132 |
| Macro `#/macro` | 390 | 115 → 124 | 363 → 371 | 18 | 13 | 2 | 3,245 → 3,234 |
| Indices `#/indices` | 390 | 119 → 113 | 446 → 469 | 18 | 6 | 0 | 2,929 → 2,994 |
| Instrument `#/instrument/^GSPC` | 390 | 74 | 96 → 104 | 14 | 5 | 0 | 1,585 |
| Earnings week `#/earnings` | 390 | 157 | 598 | 37 | 0 | 1 | 4,083 |
| Explore `#/explore` | 390 | 110 | 1,259 → 617 | 65 → 47 | 8 | 0 → 1 | 7,666 → 4,699 |
| Scan `#/scan` | 390 | 92 | 638 | 97 | 3 | 1 | 4,610 |
| Insiders `#/insiders` | 390 | 105 | 1,755 | 143 | 1 | 0 | 2,958 |
| Analysts `#/analysts` | 390 | 77 | 2,514 → 615 | 222 → 63 | 1 | 0 | 15,252 → 4,291 |
| Optic Portfolio `#/portfolio` | 390 | 145 | 524 | 26 | 10 | 3 | 3,264 |
| Paper Desk `#/paper` | 390 | 53 | 375 | 23 | 4 | 1 | 3,201 |
| Retirement `#/retirement` | 390 | 74 | 1,627 → 1,167 | 31 → 20 | 18 | 0 → 2 | 8,101 → 6,631 |
| Brokerage `#/brokerage` (guest) | 390 | 195 | 241 | 2 | 2 | 0 | 1,630 |
| Watchlist `#/watchlist` | 390 | 95 | 95 | 5 | 0 | 0 | 1,140 |
| Alerts `#/alerts` | 390 | 121 | 276 | 5 | 4 | 0 | 2,124 |
| Saved research `#/research` | 390 | 134 | 134 | 5 | 2 | 0 | 1,379 |
| Settings `#/settings` | 390 | 155 | 577 → 606 | 14 → 16 | 8 → 9 | 0 | 3,851 → 4,095 |
| Sign in `#/signin` | 390 | 41 | 41 | 7 | 0 | 0 | 1,216 |

**Reading the table.** Home (1,872 to 672 visible words at 1440), Analysts (2,927 to 701), Explore (1,255 to 619) and Retirement (1,631 to 1,171) carry the reductions. The as-of lines add 8 to 20 words to Macro,
Indices, Instrument and Compare. Settings gained its "How much each page shows" section. The Dossier tabs
are unchanged apart from wording: their reading load (BUG-004, NVDA 1,409 visible words, 5,211 px at 1440) is the
subject of Phase 06's directive, which rebuilds the Dossier's Simple and Advanced analysis. Phase 04 made the
Dossier's "Show advanced analysis" a density control (D-019) so that Phase 06 builds on one mode state.

Directive 04's density list, against what the review found:

| Item | Finding and what was done |
|---|---|
| Number of visible cards | Home 12 to 5 at 1440. Other routes unchanged. |
| Competing headings | Home's first screen had five panel headings plus the first-visit card. Now it has the card, Markets at a glance, then Quote and Watchlist. |
| Excessive statistics | The market score, sentiment gauge, expected move ratios and heatmap left Home's Simple first screen and stay one press away. |
| Long descriptions | Read's repeated report sentence was cut (BUG-076). The Overview's ids moved to the fold. Explore's screen catalogue is folded. |
| Dense tables | Analysts is capped at 40 rows. Retirement's universe and correlation tables are folded in Simple. Insiders already draws one list at a time, capped at 60, 40 and 12 rows. |
| Technical jargon | One name per model. "Regime", "Tight" and "Wide" are gone where they misled (WRITING_GUIDELINES.md). Remaining jargon on Options and Macro is explained by the glossary words. |
| Duplicate information | Two Follow sets on Home became one. The duplicate Home page was removed. Explore's sector table and Macro's sector board both remain: they measure different things, and Explore links to Macro. |
| Repeated buttons | Each Home panel header still carries About, Ask Milo, Options and Refresh. Fewer panels mean fewer of them (controls 186 to 71). |
| Excessive icons | Icon-only buttons are counted per route in density.json; none were added. |
| Unnecessary borders, nested cards | None found nested. Containers follow the design standard (V-11, Phase 01). |
| Large empty gaps, inconsistent spacing | No large empty gaps found on the measured routes. The spacing literals (1,844, of which 835 are off the 4px scale) are Phase 10's visual consistency audit (D-025, section 9). |
| Unclear hierarchy | Home's first screen now has one card, the market strip and one company. |
| Sidebar complexity | Nine groups, unchanged; see section 5 for the proposals. |
| Modal complexity | The palette, the Milo panel and the drawer were not changed (Milo is Phase 07). |
| Chart controls | The Chart page is the design reference and was left as it is. Its empty Add now says what to do. |
| AI response layouts | Phase 07's subject; not changed here. |

## 3. Simple-first layers

Layer 1 is what a beginner sees first. Layer 2 is supporting detail, one press away. Layer 3 is the advanced
research.

| Screen | Layer 1 (visible at once) | Layer 2 (one press) | Layer 3 (advanced) |
|---|---|---|---|
| Home | Greeting and date; the first-visit card (search, Read, follow); Markets at a glance; Quote and chart; Watchlist; What matters today; Desk; your portfolio (linked) | Each panel's About and "How fresh" details; the Desk's whole edition; Add panel | Advanced: market score, expected move, heatmap, calendar, earnings, news, movers; Options and Long-term layouts; Customize |
| Dossier Overview | Header with price and move; what the company does; the past year; four questions; key figures | Glossary words; each section's "How this works"; bull and bear case | "Advanced research" fold (rung 2) and the Show advanced analysis switch (Phase 06 rebuilds this) |
| Chart | The chart, range, style | Indicators, layers, Chart read | Drawing tools, studies, panes |
| Options | One-line read and the six option figures | Research contracts, screen contracts, position builder | Positioning and flow, setups and strategy tabs; method folds |
| Investing, Earnings, Financials, News | Each tab's lead section | Folded specialist sections | Rung-2 sections, Advanced (Phase 06) |
| Compare | The two boxes, Optic's take | How they moved, where each scores | Side by side, method lines |
| Read | Today's Read and the index strip | More from today; the in-page tabs | Catalyst library, official sources |
| Macro | The market today, in brief; Optic's market score | The 12 terms of the score; expected move | In depth: 11 tabs in four groups |
| Indices | What the indices say; major index funds | Index Read (on request) | Where each index stands (the long-run table) |
| Explore | Three questions with their top names; what is worth a look today | Every screen (folded), Sectors, Cross-asset | Scan |
| Analysts, Insiders | Filters and the newest rows | Show all; sorting | Per-company history |
| Retirement | The model allocation and projection | Holdings comparison, overlap, Roth notes | Fund universe and correlation tables (folded in Simple) |
| Settings | Account, appearance, text size | What a page shows, how Milo explains | Report a problem, build details |

## 4. Home

| Does Home say... | Where, after Phase 04 |
|---|---|
| What Optic does | The first-visit card's line under its heading, "Prices, options, financials and filings for US stocks and funds, each figure with its source." (added in Phase 04; the removed page's welcome had said it), then its three ways in; the legal footer's description. |
| How to start | The same card's three actions: search, Read today's market, follow a starter. |
| What market context is shown | Markets at a glance, with its source and its time, such as "Updated 10:17 AM EDT, Delayed 15 min". |
| How to search | The top bar's "Search or ask" (⌘K) and the card's "Search for a company". |
| Where Milo is | The top bar's Ask Milo (Scout), and each panel's Ask Milo. |
| Where deeper research is | Each linked panel names its company and opens its Dossier; "Read today's market"; Advanced and Add panel bring back every panel. |

What was kept on purpose: the four layouts and Customize (a returning reader's own desk), every panel (hidden, not
removed), the linked-ticker box (Phase 03), the Desk (now with its own time), the starters. What went: the unrouted
second Home page, its knowledge question and its loaders. No reader could reach them (D-021).

## 5. Navigation review (proposals only; renames need the owner's yes)

The rail has nine groups in three sections (Research: Home, Dossier, Compare, Markets, Discover; Tracking:
Positions, Brokerage, Watchlist; Owner: Reports). The phone bar is Home, Markets, Watchlist, Dossier, More. Every
route and deep link from before Phase 04 still resolves: every page slug, `#/workspace` (Home), `#/dossier`,
`#/earnings`, `#/research`, `#/brokerage/<section>`, `#/instrument/<symbol>` and share-class tickers (`core/router.js`,
unchanged); no route was removed. These names are the owner's (the classic app's, word for word), and a
rename was reverted on 2026-10-11 for lack of a yes, so nothing below was changed (D-023).

| Name | What a newcomer may not see | Proposal for the owner |
|---|---|---|
| Dossier | That it is a company's research page | Keep the name; consider "Company" or a subtitle in the rail's tooltip ("A company's research") |
| Markets → Read | A verb as a page name; that it is the daily market brief | "Today" or "Daily brief" |
| Positions → Optic Portfolio | That it is Optic's own simulated book, not the reader's portfolio (Brokerage is the reader's) | "Model portfolio" or "Optic's paper book" |
| Discover → Explore and Scan | Both start from screens; Explore links into Scan | Keep both; Explore is the guided start, Scan the full tool. Consider stating that in each page's subtitle |
| Positions → Paper Desk | Fine for readers who know "paper trading" | Keep |
| Compare (a group of one page) | Nothing | Keep |
| Watchlist → Alerts | Nothing | Keep |

Primary and secondary destinations: the phone bar already holds the four most used, and Discover sits in More, in
the owner's order of 2026-10-19. No change is proposed there.

## 6. Language

WRITING_GUIDELINES.md holds the ten rules with examples from this pass. The copy changed under them is listed in
the summary table above. Three pieces of copy were reviewed and kept:

- **"Company or fund shown in linked panels"** (Home). The owner's beginner brief of 2026-10-20 chose this wording
  and a test pins it; the hint line under it explains linked panels in plain words.
- **The Expected move formulas** ("VIX ÷ 16", "14-day ATR ÷ 1.6"). The 2026-10-22 pitch audit put the conversion
  beside the ratio so the arithmetic can be checked. On Home the panel is now in Advanced only.
- **Two long method sentences in the Overview's folds** ("The wording uses fixed cut-offs ...", 100 words; "The
  model adds and subtracts points for ...", 51 words, which repeats the factor table beneath it). Both are Classic's
  analytical copy, ported word for word under the owner's rule, so they were left as they are. Proposal for the
  owner: allow the first to be set as a list in the same words, and the second to point at its table.

A scan of all v2 interface strings for filler and promotional words ("simply", "seamless", "powerful", "unlock"
and similar) found two uses of "easily", both in definitions ("how easily a stock can be bought or sold"), where it
carries meaning. A scan for sentences over 40 words found the two above and the legal pages' long sentences.

## 7. Simple and Advanced: the model

One density setting (Simple or Advanced), stored on Classic's key `optic.mode.v1`, decides what pages show. The
knowledge level decides only the words (Milo's, and Phase 05's slider). Settings has a control for each, and each
says it leaves the other alone. The Dossier's "Show advanced analysis" is the density control. The folds in
`ui/sections.js`, `simpleFold` and Home's panel sets follow density. Tests: `tests/test_v2_density.py`
(8 tests). Directive 04 section 7 allowed per-feature disclosure instead if a global mode would complicate the
architecture. It did not, because every fold already went through one switch point (D-019).

## 8. Component review

KEEP: valuable and already clear. SIMPLIFY: useful but more complicated than it needs to be. COLLAPSE: useful
secondary detail, now one press away. RELOCATE: in the wrong place. MERGE: duplicates another. REMOVE: no distinct
purpose and safe to remove. Every removal is listed after the table.

| Route | Component | Decision | What was done, or why kept |
|---|---|---|---|
| Shell | Rail (9 groups), top bar, phone bar | KEEP | Names are the owner's; proposals in section 5 |
| Shell | Search palette (⌘K), Ask Milo, account | KEEP | Phase 03 fixed the palette; Milo is Phase 07 |
| Shell | Legal footer, page notices | KEEP | Owner's rule; Phase 02 registry |
| Shell | Glossary words (`term()`), "How this works" folds | KEEP | The shared way to explain a term once (layer 2) |
| Home | First-visit card "New to Optic? Three ways to start" | SIMPLIFY | Says what Optic is in one line; stays until dismissed; no pointer to a panel Simple hides; the only Follow set on the first screen |
| Home | Layouts row (four presets) and Customize | KEEP | A returning reader's own desk |
| Home | Linked-ticker box and hint | KEEP, SIMPLIFY | Says when the panels already show the ticker (BUG-075) |
| Home | Markets at a glance | KEEP | Simple's market context |
| Home | Quote and chart; Watchlist | KEEP, SIMPLIFY | The empty Watchlist leaves the Follow buttons to the card while it is up |
| Home | What matters today | KEEP | The day's schedule in one list |
| Home | Optic Desk | KEEP, SIMPLIFY | The footer says Written or Compiled with its own time (H-2) |
| Home | Your portfolio | KEEP | Only with a linked brokerage |
| Home | Market conditions (market score, sentiment) | COLLAPSE, SIMPLIFY | Advanced or Add panel; one name, "Optic's market score" (X-6) |
| Home | Expected move | COLLAPSE, SIMPLIFY | Advanced or Add panel; one label set with Macro (X-7) |
| Home | Sector heatmap | COLLAPSE, SIMPLIFY | Advanced or Add panel; tint at most 28%, fixed scale (BUG-077) |
| Home | Economic calendar; Earnings this week | COLLAPSE | What matters today carries both; `#/earnings` has the week |
| Home | Market news; Moved most this month | COLLAPSE | Read and Explore carry them |
| Home | Changes, Questions, Trends, Scan alerts, Economy | KEEP | Already in Add panel only |
| Home | Options layout: positioning, earnings, company news | COLLAPSE | Advanced; quote, watchlist, contracts and volatility stay |
| Home | Long-term layout: financial trends, ownership, company news | COLLAPSE | Advanced; quote, watchlist, business, valuation and portfolio stay |
| Home | The unrouted second Home page | REMOVE | See the removals below (D-021) |
| Dossier | Header, tabs, Watch, Alert, Compare, Export, ⋯ menu | KEEP | The menu's actions all say what they did when pressed; the dead-click reports were folded-menu artifacts (D-022) |
| Dossier | "Show advanced analysis" | SIMPLIFY | Density only (D-019); Phase 06 makes it replace the Simple content |
| Overview | What the company does; the past year; key figures; bull and bear | KEEP | Layer 1 |
| Overview | Four questions | SIMPLIFY | Method and policy ids moved into the fold (BUG-009) |
| Overview | What should I look at next? | SIMPLIFY | Line icons replace text arrows |
| Overview | Advanced research | COLLAPSE | Folded already; Phase 06 rebuilds it |
| Options | One-line read and six figures; tabs | KEEP | The reference pattern for a dossier tab |
| Options | Research contracts table | SIMPLIFY | Liquid, Fair, Thin; "spread x%" named (BUG-010) |
| Options | Screen contracts; position builder | KEEP | Phase 02 made both describe rather than instruct |
| Chart | Chart, toolbar, widgets | KEEP, SIMPLIFY | The watchlist widget's empty Add says what to do (BUG-075) |
| Investing, Earnings, Financials, News, Sheet | Their sections | KEEP | Measured here; reading load is Phase 06's |
| Compare | Boxes, take, moves, bars, side by side | KEEP | An as-of line at the end (X-10) |
| Compare | Recently viewed chips | SIMPLIFY | Not offered when all four boxes are full (BUG-075) |
| Read | Today's Read; index strip | KEEP | Layer 1 |
| Read | More from today | SIMPLIFY | The report sentence is said once (BUG-076) |
| Read | "Market regime" tab | SIMPLIFY | Now "Index score", and it says how it differs (X-6); its group is "Sentiment and trend" |
| Macro | The market today, in brief | KEEP, SIMPLIFY | An as-of line (X-10) |
| Macro | Macro regime block | SIMPLIFY | Now "Optic's market score", "Market score, −100 to +100" (X-6) |
| Macro | Expected S&P move | SIMPLIFY | Home's labels (X-7) |
| Macro | In depth (11 tabs, four groups) | KEEP | Already layer 3 |
| Indices | What the indices say | KEEP, SIMPLIFY | As-of: the last finished week, and that this week counts at the latest price |
| Indices | Index regime table | SIMPLIFY | Now "Where each index stands" (X-6) |
| Indices, Macro | Fund boards | SIMPLIFY | The price time and kind stated (X-10) |
| Instrument | Tiles, chart | KEEP, SIMPLIFY | "Last price as of ..." (X-10) |
| Explore | Questions, worth a look today, sectors, cross-asset | KEEP | As-of lines on sectors and cross-asset (X-10) |
| Explore | Every screen | COLLAPSE | Folded in Simple, open in Advanced, the heading and its line stay in view |
| Explore and Macro | Two sector tables | KEEP (not MERGE) | Different measures (relative week and month against SPY; the trend board); Explore links to Macro |
| Scan, Insiders, Earnings week | Their pages | KEEP | Tables already capped or tabbed |
| Analysts | Actions table | SIMPLIFY | The newest 40, then Show all; rating words in ink; target arrows muted (BUG-077) |
| Optic Portfolio, Paper Desk | Their pages | KEEP | Phase 02 changed their wording; a name proposal in section 5 |
| Retirement | Model, projection, comparisons, Roth notes | KEEP | Layer 1 and 2 |
| Retirement | Fund universe table; correlation matrix | COLLAPSE | Folded in Simple, open in Advanced; heading and its line stay in view |
| Brokerage, Watchlist, Alerts, Saved, Sign in | Their pages | KEEP | Light already |
| Settings | Appearance, text size, keyboard, time zone | KEEP | |
| Settings | "How Milo explains things" | SIMPLIFY | Milo's language only, and says so |
| Settings | "How much each page shows" | SIMPLIFY | A control of its own, so density no longer rides on Milo's level (D-019) |
| Owner pages | Reports, usage, accounts, metrics | KEEP | Owner only; not part of a reader's first use |

**Removals, each one.**
1. `pages/home.js`: the unrouted Home page. That is its `render`, `dispose`, `render_`, `loadHome`, `loadWatch`,
   `loadPriority`, `loadMovers`, `loadStarters`, `loadModes`, `loadBrokerage`, `wire`, `wireForms` (a search box no
   route drew), `onLists`, `retry`, `welcome`, `starters`, `modes`, `scene` (an expected-move statement panel),
   `strip` (a market strip), `movers`, `desk` (a Desk section), `setScene`, `inst`, `moveLabel`, the `timer` and
   `live` state, and the imports only they used. None was reachable: `app.js` routes Home to `pages/workspace.js`.
   Each visible piece has a live counterpart: greeting, What matters today, Desk, portfolio, starters (in the
   first-visit card), the index strip panel and the Expected move panel.
2. `pages/workspace.js`: the handlers for `[data-v2-home-ready]` ("See your Home"), `[data-v2-mode]` and
   `[data-ws-mode]` (a first-visit knowledge question), the `NEW` state and `loadNew`. Nothing draws these
   controls, and nothing called `loadNew`.
3. The first-visit card's clause "Market conditions below sums it up too". That panel is not in Simple.
4. The Watchlist panel's duplicate Follow buttons while the first-visit card is up. They return when it is dismissed.
5. Colour, not content: the analyst rating words' green and red, and the target arrows' green and red.

Styles for the removed page (`.welcome`, `.starter`, `.scene`, `.mstrip`, `.modes`, `.paths`) remain in the CSS.
Their selectors are shared, so removing them is left for a separate pass (D-021).

## 9. Design-system consistency

Checked against `docs/frontend-v2/DESIGN-STANDARD.md` and its tests. `tests/test_v2_design_standard.py` and
`tests/test_v2_checklist.py` pass on the Phase 04 tree (20 tests: sizes, weights, two faces, tokens, radii, no em
dashes, no emoji, gold only where allowed).

| Area | Status | Evidence | Done in Phase 04 | Still open |
|---|---|---|---|---|
| Buttons | PASS | `.btn`, `.btn-quiet`, one `.btn-primary` per view, quiet `.btn-milo` | "Show all N" and the new folds use the shared classes | |
| Typography | PASS, headline sizes PARTIAL (Phase 10) | Inter and Space Grotesk only; scale tokens; weights 400 to 600 (tests) | Rating words and target arrows use ink tokens | Headline figures still carry literal sizes per component (standard item 2), for Phase 10 (D-025) |
| Spacing | PARTIAL (Phase 10) | 4px scale defined (`--s-1` to `--s-10`) | New rules use 4px steps | 1,844 spacing literals, 835 off the 4px scale (6, 10, 14, 18 px most often): Phase 10's visual consistency audit (D-025) |
| Cards | PASS | One container per source, none nested (Phase 01 V-11) | Home's Simple first view: 5 cards at 1440 instead of 12 | |
| Form fields | PASS | `.field`, squared to `--r-ctl` | | |
| Tabs | PASS | Text tabs, a 2px gold bar under the current one | The in-page tab "Index score" replaces "Market regime" | |
| Dropdowns and menus | PASS | `details.menu`, kept open across redraws by `render` | | |
| Tooltips and glossary | PASS | `term()` popover, hover tip and keyboard focus | The dead-click reports on terms were folded-content artifacts (D-022) | |
| Icons | PASS | One line family, `ui/icons.js` | The Overview's text arrows replaced by `icon('arrow')`; remove buttons already used `icon('close')` | Scan's funnel keeps "→" as notation between two counts |
| Charts | PASS | Own SVG engines; Chart page is the reference | Heatmap tint at most 28%, on a fixed scale | |
| Loading states | PASS | `skeleton()` | | Dossier header while loading, BUG-031 (Phase 10) |
| Errors | PASS | `failed()` says what failed and offers Try again | | Try again doubles listeners on Scan, Read and Indices, BUG-037 (Phase 10) |
| Empty states | PASS | `empty()` and panel notes say what to do | The empty Watchlist no longer repeats the first-visit card's buttons | |
| Navigation | PASS | Rail, tabs and phone bar unchanged | Proposals only (section 5) | The owner's decision on names |
| Modals and drawers | PASS | Drawer, palette, Milo panel | | Milo's layout is Phase 07's |
| Generic dashboard patterns | Improved | Home's twelve equal panels, each with four icon buttons, was the clearest case | Simple opens five or six panels, led by one card | |
| Light theme | PASS for what Phase 04 changed | Contrast measured in the browser pane in light (ivory) and dark (charcoal): time lines 7.1 and 8.3:1, fold summaries 6.5 and 10.9:1, rating words 17.0 and 16.0:1, next-step labels 7.1 and 8.3:1, heatmap tile text 11.2 to 14.9:1 (light) and 9.2 to 14.2:1 (dark) at full tint | | The rest of the light theme was not re-checked (standard item 7) |
| Classic | NOT TESTED | | Only the shared liquidity words changed (D-024) | Classic keeps its own sizes, gold buttons and pills (standard item 8) |

## 10. Responsive simplicity

Measured on the Phase 04 tree at 1440×900 (desktop), 1024×768 (laptop), 768×1024 (tablet) and 390×844 (phone),
every primary route, guest. Overflow is `scrollWidth - clientWidth` on the page. Overlapping text is the probe's
check: two visible pieces of text whose line boxes share more than 3px each way, after clipping by any scroller.
A sticky bar over scrolled content does not count.

| Size | Routes measured | Sideways overflow (scrollWidth - clientWidth > 0) | Overlapping text (pairs) | Tallest page |
|---|---|---|---|---|
| 1440 | 29 | none | none | nvda-financials, 8,425 |
| 1024 | 29 | none | none | nvda-investing, 9,879 |
| 768 | 29 | none | none | nvda-financials, 11,627 |
| 390 | 29 | none | none | nvda-investing, 14,333 |

- **No hidden essential content.** On a phone, Home opens the essential panels (the market strip, the quote and the
  watchlist) and folds the rest to their title and one line, loading them only when opened, as before Phase 04.
  Simple folds only supporting detail, and each fold's heading stays in view.
- **No inaccessible controls.** Every control on the changed routes was pressed by the dead-click run (section 11).
  Phase 01's checks of unnamed controls and contrast were 0 on every load (V-11). Small touch targets at 390 remain
  BUG-014, which belongs to Phase 10.
- **Tables.** Wide tables scroll inside `.tscroll` and say "Scroll sideways for every column" on a phone. That is the
  sideways scroll the directive allows for data tables.

## 11. Visual regression

Before and after first-screen screenshots were put side by side for every materially changed route at 1440 and 390,
and looked at by eye (`tools/pair_sheet.py`; `phase04/pairs-w1440-*.jpg`, `pairs-w390-*.jpg`). The "before" run did
not cover 1024 and 768, so those sizes were inspected after the changes only (`phase04/after-w1024-sheet.jpg`,
`after-w768-sheet.jpg`), alongside the probe's overflow and overlap counts (section 10). The dead-click run pressed
every control on the changed routes after the changes.

| Route | What changed on screen | Regression found |
|---|---|---|
| Home | The market score, expected move and heatmap left Simple's first screen; the linked box and Quote and chart follow Markets at a glance | None. The review found one set of Follow buttons too many (fixed, BUG-079) |
| Analysts | Rating words in ink, target arrows muted; 40 rows, then Show all | None |
| Read | Unchanged first screen; the report sentence once, lower down | None |
| Macro | "Figures as of ..." under the brief; "Optic's market score"; "Market score, −100 to +100" | None |
| Indices | A weekly-close line under the readings; the fund board's price time | The first version said "through Oct 30" on Thursday Oct 29, because the current week's bar carries its Friday's date. Fixed to name the last finished week (Oct 23) and say this week counts at the latest price |
| Explore | Time lines on sectors and cross-asset; the catalogue folded | None |
| Compare | A time line at the end; chips gone when the boxes are full | None |
| Instrument | "Last price as of ..." | None |
| Overview, Options, SPY, Settings | Below the first screen only (fold ids, icons, words, a new Settings section) | None |
| Retirement | Two tables folded in Simple | None |

Interaction checks: the first-visit card in the browser pane (Not now, Follow, Done, and the card leaving). The fold
memory after a full rebuild, open and closed. Every changed route's time line, rendered with no script errors. The
Phase 03 search and ticker scenarios, run again on the Phase 04 tree. The dead-click run on the changed routes at
1440 and 390, guest and signed in (results in TEST_RESULTS.md, Phase 04).

## Per-route record

Each route below records its original load and problems, what changed, what moved or went, what was kept, the
evidence, and what is still open. Numbers are visible words / controls / page height at 1440, before → after, from
section 2.

**Home `#/`.** Load: 1,872 → 672 visible words, 186 → 71 controls, 3,427 → 2,149 px at 1440; 390 → 278 words at 390. Problems: Twelve panels of equal weight on a first visit, each header with four icon buttons; a saturated heatmap the loudest thing on the page; the market score, expected move ratios and heatmap on the first screen; two sets of Follow buttons; the Desk footer gave the time the page was assembled, not when the note was written. Changed: Simple panel sets (D-020); heatmap tint capped on a fixed scale; one Follow set; Desk time is when written or compiled; "Update panels" says when nothing changes. Relocated: Market conditions, Expected move, Sector heatmap, Economic calendar, Earnings this week, Market news and Moved most this month to Advanced or Add panel. Removed: The unrouted second Home page; handlers for undrawn controls; a first-visit pointer to a hidden panel. Preserved: Every panel, the four layouts, Customize, the linked-ticker box, the Desk, the starters. Evidence: `phase04/before-2f6a548/home-w1440.png`, `phase04/after/home-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Each panel header still carries four controls.

**Dossier start `#/dossier`.** Load: 39 visible words, 6 controls, 901 px at 1440; 36 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Search box, recent companies. Evidence: `phase04/before-2f6a548/dossier-start-w1440.png`, `phase04/after/dossier-start-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Overview `#/NVDA`.** Load: 1,417 → 1,409 visible words, 98 → 99 controls, 5,139 → 5,211 px at 1440; 1,424 → 1,396 words at 390. Problems: Long: 1,417 visible words over 16 headings and 19 closed folds at 1440; ids in the Four questions' lead; text arrows. Changed: Ids into the fold (BUG-009); arrows are icons; "Show advanced analysis" is density only. Relocated: Method and policy ids into How this works. Removed: None. Preserved: Every section, the Advanced research fold, the tabs and actions. Evidence: `phase04/before-2f6a548/nvda-w1440.png`, `phase04/after/nvda-w1440.png` (before at 1440 and 390, after at all four sizes). Open: The reading load (BUG-004) is Phase 06.

**Chart `#/NVDA/chart`.** Load: 193 visible words, 66 controls, 1,369 px at 1440; 165 words at 390. Problems: None new; an empty watchlist Add said nothing. Changed: The empty Add says what to do. Relocated: None. Removed: None. Preserved: The whole chart page. Evidence: `phase04/before-2f6a548/nvda-chart-w1440.png`, `phase04/after/nvda-chart-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Options `#/NVDA/options`.** Load: 1,096 → 1,111 visible words, 88 controls, 4,555 px at 1440; 942 → 957 words at 390. Problems: "Tight 3.2%" beside "Fair 0.3%". Changed: Liquid, Fair, Thin, with "spread x%" beside the word. Relocated: None. Removed: None. Preserved: Every option figure, table and tab. Evidence: `phase04/before-2f6a548/nvda-options-w1440.png`, `phase04/after/nvda-options-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Options knowledge still needed; glossary words explain each term.

**Investing `#/NVDA/investing`.** Load: 2,118 → 2,147 visible words, 106 controls, 8,040 → 8,087 px at 1440; 2,139 words at 390. Problems: Long: 2,118 visible words, 8,040 px at 1440. Changed: None in Phase 04. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/nvda-investing-w1440.png`, `phase04/after/nvda-investing-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Phase 06.

**Earnings `#/NVDA/earnings`.** Load: 1,013 visible words, 53 controls, 3,827 px at 1440; 1,005 words at 390. Problems: Long-ish: 1,013 visible words. Changed: None in Phase 04. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/nvda-earnings-w1440.png`, `phase04/after/nvda-earnings-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Phase 06.

**Financials `#/NVDA/financials`.** Load: 2,146 visible words, 82 controls, 8,425 px at 1440; 2,043 words at 390. Problems: Long: 2,146 visible words, 8,425 px at 1440. Changed: None in Phase 04. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/nvda-financials-w1440.png`, `phase04/after/nvda-financials-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Phase 06.

**News `#/NVDA/news`.** Load: 454 → 423 visible words, 29 → 30 controls, 2,575 → 2,405 px at 1440; 439 → 415 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/nvda-news-w1440.png`, `phase04/after/nvda-news-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Fund Overview `#/SPY`.** Load: 1,071 → 1,070 visible words, 65 controls, 4,360 px at 1440; 1,063 words at 390. Problems: Long for a fund: 1,071 visible words. Changed: As the Overview. Relocated: As the Overview. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/spy-w1440.png`, `phase04/after/spy-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Phase 06.

**Compare `#/compare?t=NVDA,AMD`.** Load: 1,303 → 1,316 visible words, 14 controls, 4,184 → 4,206 px at 1440; 901 → 914 words at 390. Problems: Recent chips pressed to nothing once the four boxes were full; no time on the result. Changed: Chips hidden when full; "Compared as of ..." line. Relocated: None. Removed: None. Preserved: Every section of the comparison. Evidence: `phase04/before-2f6a548/compare-w1440.png`, `phase04/after/compare-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Scores need the method to read (said on the page).

**Read `#/read`.** Load: 1,202 → 1,160 visible words, 43 controls, 3,376 → 3,330 px at 1440; 1,200 → 1,158 words at 390. Problems: One sentence repeated on each of 20 report rows; "Market regime" named a different model from Home's and Macro's. Changed: The sentence once; "Index score" tab that says how it differs. Relocated: The report sentence to the list's foot. Removed: Nineteen repeats of one sentence. Preserved: Every section and tab. Evidence: `phase04/before-2f6a548/read-w1440.png`, `phase04/after/read-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Macro `#/macro`.** Load: 365 → 373 visible words, 19 controls, 2,121 → 2,112 px at 1440; 363 → 371 words at 390. Problems: No time on the page; "Macro regime" and "Risk score" for the score Home calls Optic's market score; a second label set for the expected move. Changed: As-of line; one name and one label set; the stance line names the market score. Relocated: None. Removed: None. Preserved: Every section and the In depth tabs. Evidence: `phase04/before-2f6a548/macro-w1440.png`, `phase04/after/macro-w1440.png` (before at 1440 and 390, after at all four sizes). Open: A specialist page; jargon explained by glossary words.

**Indices `#/indices`.** Load: 448 → 468 visible words, 19 controls, 2,269 px at 1440; 446 → 469 words at 390. Problems: No time on the page; "Index regime" for each index's long-run phase. Changed: As-of line naming the last finished week; "Where each index stands"; the fund board's price time. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/indices-w1440.png`, `phase04/after/indices-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Instrument `#/instrument/^GSPC`.** Load: 96 → 104 visible words, 11 controls, 1,064 px at 1440; 96 → 104 words at 390. Problems: No time on the tiles. Changed: "Last price as of ...". Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/instrument-w1440.png`, `phase04/after/instrument-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Earnings week `#/earnings`.** Load: 598 visible words, 37 controls, 2,526 px at 1440; 598 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/earnings-week-w1440.png`, `phase04/after/earnings-week-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Explore `#/explore`.** Load: 1,255 → 619 visible words, 68 → 50 controls, 3,776 → 2,678 px at 1440; 1,259 → 617 words at 390. Problems: No time on sectors and cross-asset; the full catalogue of screens open on first view. Changed: As-of lines; the catalogue folded in Simple. Relocated: The screen catalogue into a fold. Removed: None. Preserved: Every screen (one press), the guided questions, sectors, cross-asset. Evidence: `phase04/before-2f6a548/explore-w1440.png`, `phase04/after/explore-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Scan `#/scan`.** Load: 683 visible words, 106 controls, 3,556 px at 1440; 638 words at 390. Problems: None new. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/scan-w1440.png`, `phase04/after/scan-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Filter names need some knowledge.

**Insiders `#/insiders`.** Load: 1,758 visible words, 146 controls, 2,064 px at 1440; 1,755 words at 390. Problems: Dense but tabbed and capped. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/insiders-w1440.png`, `phase04/after/insiders-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Analysts `#/analysts`.** Load: 2,927 → 701 visible words, 226 → 67 controls, 14,629 → 3,729 px at 1440; 2,514 → 615 words at 390. Problems: Every action of the window at once (2,927 words, 14,629 px); coloured rating words. Changed: The newest 40, then Show all; ratings in ink; target arrows muted. Relocated: Rows after the 40th behind Show all. Removed: Rating colours. Preserved: Every row, the sort, the filters. Evidence: `phase04/before-2f6a548/analysts-w1440.png`, `phase04/after/analysts-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Optic Portfolio `#/portfolio`.** Load: 528 visible words, 28 controls, 1,955 px at 1440; 524 words at 390. Problems: The name may read as the reader's own portfolio. Changed: None (a name proposal for the owner). Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/portfolio-w1440.png`, `phase04/after/portfolio-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Owner's decision on the name.

**Paper Desk `#/paper`.** Load: 379 visible words, 25 controls, 1,927 px at 1440; 375 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/paper-w1440.png`, `phase04/after/paper-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Retirement `#/retirement`.** Load: 1,631 → 1,171 visible words, 33 → 22 controls, 5,026 → 3,903 px at 1440; 1,627 → 1,167 words at 390. Problems: The fund universe table and correlation matrix in full on a first visit. Changed: Both folded in Simple, open in Advanced. Relocated: The two tables into folds. Removed: None. Preserved: Every section, the model and projection. Evidence: `phase04/before-2f6a548/retirement-w1440.png`, `phase04/after/retirement-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Brokerage `#/brokerage` (guest).** Load: 241 visible words, 2 controls, 1,000 px at 1440; 241 words at 390. Problems: None for a guest. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/brokerage-w1440.png`, `phase04/after/brokerage-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Signed-in sections were not re-measured (owner's live data).

**Watchlist `#/watchlist`.** Load: 96 visible words, 6 controls, 901 px at 1440; 95 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/watchlist-w1440.png`, `phase04/after/watchlist-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Alerts `#/alerts`.** Load: 277 visible words, 6 controls, 1,631 px at 1440; 276 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/alerts-w1440.png`, `phase04/after/alerts-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Saved research `#/research`.** Load: 134 visible words, 5 controls, 901 px at 1440; 134 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/saved-w1440.png`, `phase04/after/saved-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

**Settings `#/settings`.** Load: 577 → 606 visible words, 14 → 16 controls, 2,754 → 2,931 px at 1440; 577 → 606 words at 390. Problems: One switch for two settings: Milo's language and what pages show. Changed: Two sections, each saying it leaves the other alone. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/settings-w1440.png`, `phase04/after/settings-w1440.png` (before at 1440 and 390, after at all four sizes). Open: Phase 05 adds the five-level slider.

**Sign in `#/signin`.** Load: 41 visible words, 7 controls, 1,032 px at 1440; 41 words at 390. Problems: None found. Changed: None. Relocated: None. Removed: None. Preserved: Everything. Evidence: `phase04/before-2f6a548/signin-w1440.png`, `phase04/after/signin-w1440.png` (before at 1440 and 390, after at all four sizes). Open: None.

## Completion gate (directive 04)

| Gate item | Status | Evidence |
|---|---|---|
| Every discovered primary route has been reviewed | PASS | The 29 primary routes were measured before and after and answered against the nine questions (sections 1 and 2). The 13 secondary routes a guest can open were measured before and after (TEST_RESULTS). The signed-in-only pages were looked at in Phase 01's signed-in screenshots (`phase04/signed-in-review-sheet.jpg`) and were not changed. With no linked brokerage, each Brokerage section shows the connection gate and the list of what Optic can and cannot see, which is disclosure and stays. Problem Reports, Claude usage, Accounts and Metrics are the owner's tables. |
| Critical usability problems have been addressed | PASS for Phase 04's scope | Home (BUG-005), the density coupling (BUG-002), Analysts (BUG-078), Read's repetition (BUG-076), the silent presses (BUG-075), the missing times and the shared "regime" (BUG-042). The Dossier's reading load (BUG-004) is Phase 06's by the owner's phase plan. |
| The default experience has a clear hierarchy | PASS | Home's Simple first screen: one card, the market strip, one company. Every page leads with its finding, and supporting detail sits one press away with its heading in view (section 3). |
| Beginners are not forced to read advanced analysis | PASS outside the Dossier; the Dossier is Phase 06's | Simple folds specialist sections (`ui/sections.js` rung), Home's Advanced panels, Explore's catalogue and Retirement's tables. The Dossier's Advanced research is folded; its Simple analysis is rebuilt in Phase 06. |
| Advanced functionality remains accessible | PASS | Nothing a reader could reach was removed. Advanced, Add panel, every fold and every route still work. The dead-click run on the changed routes found nothing that does not answer a press (TEST_RESULTS). |
| No major visual regressions remain | PASS | Before and after sheets (1440, 390); after-only sheets (1024, 768); overflow 0 and overlapping text 0 on all 29 routes at four sizes. The two problems the review found were fixed. |
| Real navigation and interaction behaviour verified | PASS | Dead-click run (guest at 1440 and 390, signed in at 1440), the Phase 03 search and ticker scenarios run again on the Phase 04 tree, and browser checks of the first-visit card and fold memory (TEST_RESULTS) |

## Limits

- No reader was tested. The first-time-user answers are heuristics.
- One market day, one data set. Counts move a little with live data.
- The light theme and Classic were not re-measured. Classic shows the new liquidity words (D-024) and is otherwise
  unchanged.
- The Dossier tabs' reading load is Phase 06's work. Milo's layouts are Phase 07's.
- Spacing literals, headline sizes and the remaining inline method text from the design standard's list are not
  solved here (section 9).
