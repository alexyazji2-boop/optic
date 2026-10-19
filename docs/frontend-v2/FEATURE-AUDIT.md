# TapeDash reference against Optic: feature comparison and gap list

**Date:** 2026-10-18.

**Sources:** the owner's TapeDash screenshots and feature list (primary reference), and a read-only code audit of `~/Optic/wt-v2` at `0b6d318`. File and line references below are to that tree.

**Evidence levels:**
- **Verified:** run this session against the local server (:8075) in the workspace preview, with live data.
- **Code:** the route, module or UI source was read.
- **Doc:** only a document says so.

**Classes:**

| Class | Meaning |
|---|---|
| A | In v2 now |
| B | In Classic, awaiting v2 migration |
| C | Partly built |
| D | Genuinely new: no backend or UI |
| E | Needs data or infrastructure Optic does not have |

**What everything rests on:**
- **Quotes and chains:** yfinance, about 15 minutes delayed. Tradier replaces it only when `TRADIER_ACCESS_TOKEN` is set (`app/providers/tradier.py`).
- **No trade tape:** chains carry no prints, aggressor side or opening/closing flags, and open interest is the previous session's (`docs/options/OPTIONS-AUDIT.md:22,138-144`).
- **No streaming:** only Milo streams.

## Research and markets
| # | Feature | Class | Evidence | Source | Level |
|---|---|---|---|---|---|
| 1 | Indices strip with VIX | A | `/api/home` (main.py:2522); v2 `home.js:22-71`; workspace Indices panel | yfinance | Verified |
| 2 | Sentiment and regime | A | **Sentiment:** `analytics/sentiment.py:381`, `/api/sentiment`. **Regime factors:** `analytics/macro.py`. **v2:** `read.js`, `macro.js`, workspace panel. **Not covered:** true exchange breadth (advance/decline, new highs and lows, put/call) is **E** (`sentiment.py:3-9`) | yfinance prices | Verified |
| 3 | Expected move | A | **Index:** VIX÷√252 (`macro.py:140`). **Per ticker:** the straddle (`analytics/earnings.py:538`). **IV rank:** `app/iv_history.py` | yfinance and Cboe indices | Verified (index) |
| 4 | Sector heatmap and rotation | A | `/api/market` sectors, `stockmaps.py:393`, `rotation.py:152`; workspace heatmap with 1 day, 1 week and 1 month | SPDR ETFs via yfinance | Verified |
| 5 | Economic calendar | C | **Schedule:** `app/events.py:636`. **Actual and prior:** from FRED (`events.py:602`), shown in the workspace as Actual and Prior. **Missing:** consensus is licensed and absent (**E**, `fred.py:287-291`); released results on Home are on the unmerged `home-released-results` branch | BLS, Fed, CFTC, FRED | Verified |
| 6 | Economy indicator explorer | C | `analytics/econ.py:203`, `/api/econ`; workspace Economy panel (list, history chart, explanation). **Missing:** the release schedule is not joined to each series, and there is no consensus | FRED | Verified |
| 7 | Earnings calendar with implied moves | C | **List:** `app/earnings_week.py:95`, `/api/earnings-week?offset=`; Classic `app.js:31735`; workspace panel (this week and next, consensus, implied move per row on request). **Missing:** before-open/after-close (`earnings_week.py:353-357`); the scan covers about 150 names | yfinance | Verified |
| 15 | News with tiers and ticker tags | C | **Per ticker:** tiers and catalyst tags (`app/news.py`). **Market wires:** RSS by desk (`feeds.py`); workspace panels. **Missing:** market-wide ticker tags; it polls rather than pushes | yfinance news, RSS, agencies, EDGAR 8-K | Verified |
| 27 | Morning, closing and weekly reports, archive | C | **Desk editions:** `desk/edition.py` (premarket and close; `DESK_EDITION_AUTO`). **Weekly:** `app/weekly.py`. **Archive:** `/api/desk/editions` exists, but **neither app has an archive UI** | Model and feeds | Code |
| 28 | Insider and institutional | A | **Form 4:** `app/insiders.py:365`, v2 `insiders.js`. **13F top holders:** per company. **Missing:** a market-wide 13F view | SEC EDGAR; 13F lag 45 days | Code |
| 29 | Congress transactions | A (House) | `analytics/congress.py:533`, v2 `insiders.js`, `financials.js`. Senate deliberately omitted | House Clerk PTRs | Code |
| 37 | Seasonality A; "why it's moving" C; ETF flows E; crowd index and flow map D | mixed | `seasonality.py:301`; `digest.py`; Pulse "what's pulling hardest" is Classic-only (I4) | | Code |

## Company and fundamentals
| # | Feature | Class | Evidence | Level |
|---|---|---|---|---|
| 19 | Fundamentals checklist | C | `analytics/earnings.py:880-990` reads improving, deteriorating or mixed. It reaches the ticker payload and Classic (`app.js:13679`). v2 shows text only (`financials.js:23-33`) | Code |
| 20 | Financial charts | C | **In v2:** annual revenue, net income, FCF and EPS; segment and region tables (XBRL). **Fetched but not charted:** capex, CFO, SBC, interest income and expense, buybacks (`valuation/inputs.py:30-110`). **Not fetched:** receivables, opex breakdown, debt maturities. **No** buyback-vs-dilution or repurchase-vs-RSU charts | Code |
| 16 | Dealer gamma A; strategy builder and volatility desk A; max pain D | | `gex.py`, `vol_surface.py`, `/api/options/{t}/analyze`. **Max pain is deliberately absent:** the research finds no support for it (`GEX-FLOW-LIQUIDITY.md:43`) | Code |
| 17 | Contract picker | C | `analytics/contracts.py:55`, `/api/options/{t}/research` (filters, an Optic liquidity label, theta, vega, chance of finishing in the money). **Deliberately unranked** (`contracts.py:1-12`); the workspace Contracts panel shows it **without grades** | Verified |
| 18 | Options risk desk | A | `brokerage/options_risk.py`, v2 `brokerage.js` | Code (sandbox) |

## Charting, setups, alerts
| # | Feature | Class | Evidence | Level |
|---|---|---|---|---|
| 21 | Chart workspace | C | **v2 (`pages/chart.js`):** 1m to 1W bars, MA, EMA, Bollinger, Fib, S/R, GEX, earnings marks, volume, RSI, MACD, 7 drawing tools, and now **Market structure breaks** (new, below). **Classic-only (M1):** 14 studies, 7 more drawing tools, 18 widgets, and the free deterministic "Chart read" popover (`app.js:23060-23135`). **Missing in both:** multi-chart layouts and a compare overlay | Verified (v2) |
| new | **Market Structure Break (MSB)** | A (new, 2026-10-18) | **Code:** `ui/pricechart.js` `marketStructure`. **Rule:** swing highs and lows with 3, 5 or 10 bars either side. A swing *forms* at its own bar but is only *known* once the bars after it have closed; a close beyond the latest known, unbroken swing is a break, and only a close after the swing became known can count. **Drawing:** dotted from where the swing formed to where it became known, solid from there to the break, with the MSB label at the known bar and a marker at the breaking close; the hover title gives all three dates. **Stability:** one forward pass, so a recorded break never changes when later bars arrive (`test_a_later_bar_never_changes_a_recorded_structure_break`: 40 random series × strengths 3, 5, 10 × every prefix). **Also:** in Milo's chart context with `swing_formed_on`, `swing_known_on` and `broke_on`; unit test `test_market_structure_breaks_follow_confirmed_swings_only` | Verified |
| 22 | Nightly ranked setups | C | **Swing setups:** `analytics/setups.py` (watching, armed, triggered, ended; daily and 4h). **Paper ledger:** stop, target and exit reason (`paper.py`). **Missing:** a published ranked list, an R:R column, a multi-timeframe trend table and an archive of outcomes | Code |
| 23 | Screener A; setup scan C (I5); backtest B | | `screener.py:214` (price and volume only); `backtest.py:384`, Classic widget | Code |
| 24 | Trade alerts timeline and record | C | **Kinds:** idea, closed, pattern, risk (`app/alerts.py:47-75`). **Ledger:** entry, stop, target, exit (`paper.py`). **Missing:** update and stop-move events, and a per-trade timeline. **Not live:** production e-mail is off | Code |
| 25 | Signal history and track record | B | `signal_history.py`, `signal_archive.py`, `/api/signals`, `/api/validation`; Classic UI. **Needs:** the `validation` branch (M4) | Code |
| 26 | Model portfolio and paper trading | A | `paper.py`, `/api/tracker`, v2 `tracker.js`; `papertrade.py`, v2 `paper.js` | Code |
| 32 | Notifications bell | C | **Backend:** unseen counts (`account.py:897-925`, `alerts.py:169`). **Classic:** phone badge. **v2:** no bell | Code |

## Workspace, help, learning, community
| # | Feature | Class | Evidence | Level |
|---|---|---|---|---|
| 33 | Workspace (layouts, panels, lock, home screen, linked panels) | **A in private preview** (new 2026-10-18) | **Home is the workspace** (owner, 2026-10-18), `pages/workspace.js`: 4 layouts (Market Overview the default, Options Research, Long-Term Investing, My Desk), 18 panels including the old Home's own, move (drag and keys), resize, hide, lock, reset, save as My Desk, one linked ticker, phone priority | Verified (52 Home checks and 18 walkthrough checks, cold and cached) |
| 34 | Command palette and ticker search | A | `ui/palette.js` | Verified (Stage 0) |
| 35 | "How to read this" per tool | C | Every workspace panel has it. Elsewhere v2 has method notes on some panels | Verified (workspace) |
| 30a | Glossary tooltips and Learn widget | **B** | Classic `GLOSSARY` (`app.js:433-573`), Learn widget (`app.js:26385`). **This was missing from CAPABILITY-MATRIX.md; added as C17** | Code |
| 36 | AI chart read | A (paid) | v2 "Explain this chart" asks Milo. Classic's free popover is C18 | Code |
| 30b | Lessons, chart drills, replay, skill rating, challenges, leaderboard | D | No code. See NEW-PRODUCTS.md | Code (absence) |
| 31 | Squawk D/E; community D; contact support A | | `/api/feedback`, "Report a problem" | Code |

## Options flow and off-exchange data (E: new data needed)
| # | Feature | What Optic has | What it would need |
|---|---|---|---|
| 8 | Market tide | nothing | OPRA trades with condition codes and the NBBO at each trade, stored intraday |
| 9 | Unusual flow table | **a proxy only:** "most active contracts" from one chain snapshot (volume and OI, `analytics/flow.py`), labelled a proxy | the same OPRA feed. Never present the proxy as executed prints |
| 10 | Golden or tracked flow outcomes | nothing | OPRA prints, plus an outcome store (see NEW-PRODUCTS.md, P2) |
| 12, 14 | Flow search, DTE tide | nothing | stored OPRA prints |
| 13 | Dark-pool prints and levels | **FINRA Reg SHO off-exchange *short volume* only** (`analytics/extras.py:156`), shown as short volume. It is not prints | a licensed equities trades feed (TRF/ADF prints on the SIP tape). FINRA's free ATS data is weekly and 2 to 4 weeks late |
| 37a | ETF flows | nothing | daily shares outstanding or creations and redemptions |

## The ten gaps that matter most for the research-workspace release
1. **Charting parity (M1):** 14 studies, 7 drawing tools, 18 widgets and the free chart read are still Classic-only.
2. **Earnings week as a page:** the workspace panel covers the list and on-request implied moves, but the standalone page and the before-open/after-close timing are missing.
3. **Track record and signal history (M4):** blocked on the `validation` branch.
4. **Economic data:** release-to-series join and released results on Home.
5. **Glossary tooltips and help (C17):** Classic-only, and were missing from the matrix.
6. **Notifications:** v2 has no bell; production e-mail is off.
7. **Fundamentals depth:** the checklist is not in v2; XBRL fields are fetched but not charted.
8. **Research tools (M3):** setup filters, rules and backtests; no ranked nightly list.
9. **Report archive:** the endpoint exists, with no UI in either app.
10. **Multi-chart layouts and a chart compare overlay:** in neither app.
