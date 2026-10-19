# Home, the research workspace (`#/`, private preview)

`static/v2/js/pages/workspace.js`. Built 2026-10-18 on branch `v2-dark-workspace`.

**What the owner decided (2026-10-18):** Home *is* the workspace. It opens on the Market Overview layout with a visible layout selector. My Desk is the reader's own saved layout. There is no separate workspace destination, no new sidebar name and no top-bar button. Old `#/workspace` links land on Home.

**Changed 2026-10-19 (owner's placement review and overnight brief):** the three layouts were rearranged around their question, with six new linked panels; the layout tabs have their own row and the linked ticker its own toolbar under them; moving, resizing, hiding, adding, Save as My Desk and Reset appear only in Customize (there is no Lock button); the first-visit welcome is one compact band that can be dismissed.

**Checked by:**
- `~/Optic/work/v2-overnight/ws_verify_home2.py`: the 2026-10-18 checks updated for the layouts and Customize mode (the earlier script is kept beside it in `~/Optic/work/v2-2026-10-17/workspace/`).
- `~/Optic/work/v2-overnight/walkthrough2.py`: the owner's review flow, now picking AAPL in Market Overview and switching to Options Research for the contracts.
- `tests/test_v2_navigation_layout.py`: the layouts' order, Customize-only controls and the first-visit band.
- `cold_load.py`: Home's first load timed request by request, cold and cached (PERFORMANCE.md).
- `milo_e2e.py` with `milo_standin.py`: Ask Milo from a panel through to the answer, against a stand-in model (7 checks).
- `style_audit.py`: Home measured against the other seven representative pages.

## Layouts
| Layout | Panels, in order | Open first on a phone |
|---|---|---|
| Market Overview (the default) | Indices; Sentiment and regime with Expected move and Sector heatmap; Quote and chart with Watchlist; Economic calendar with Earnings this week; What matters today with Market news; Optic Desk with Moved most this month; Your portfolio | Indices, Sentiment and regime, Quote and chart, Watchlist |
| Options Research | Quote and chart with Watchlist; Contracts; Volatility with Positioning; Earnings (the linked company's) with Company news | Quote and chart, Contracts, Volatility |
| Long-Term Investing | Quote and chart with Watchlist; Business quality with Fair value; Financial trends with Ownership; Company news; Your portfolio | Quote and chart, Business quality, Fair value |

Panels named "with" share a row. Lists and tables fill their row's height; the other panel sizes to its content (VISUAL-SPEC-DARK.md section 4). Layout version 4 (2026-10-19) brought these defaults; a reader's linked ticker and My Desk carried over.

**The six panels added 2026-10-19, all linked to the ticker:**
- **Volatility:** 30-day implied volatility and its rank, the at-the-money straddle's move, skew. From the ticker's options snapshot.
- **Positioning:** dealer gamma estimated from open interest, the walls and the flip point. An estimate, labelled as one.
- **Earnings:** the linked company's next report, the implied move and its record against estimates.
- **Business quality:** the research framework's grade across seven measures, from SEC filings, and its valuation label.
- **Financial trends:** four fiscal years of revenue, net income and free cash flow, with margins.
- **Ownership:** insiders' six-month activity and the largest holders' last changes, with the scope and threshold stated.

A fund linked to a company-only panel (Business quality, Financial trends, Ownership) says the panel does not apply to a fund rather than showing an empty panel. Outside market hours the free feed serves option chains without quotes; Contracts, Volatility and Positioning say so.
| My Desk | the reader's own: a copy of Market Overview, or whatever "Save as My Desk" stores | as Market Overview |

**Your portfolio** shows only when an account is linked. A reader with no linked account does not see an empty panel.

**What Home carried over from the old Home:** the greeting and date, the first-visit welcome and starters (shown to a new reader above the layout), What matters today with its filters, the Optic Desk, the portfolio value with its chart, Latest scan alerts and Moved most this month. Their copy is unchanged; the panels reuse the old Home's own renderers (`pages/home.js`).

**The bar:** the layout tabs on their own row with Customize at its right; under them a toolbar with the linked ticker and the last few tickers as quick picks.

**What a reader can do to a layout, in Customize** (Customize replaces the toolbar with an edit bar: Add panel, Save as My Desk, a ⋯ menu holding Reset, and Done):
- **Move a panel:** drag its grip (mouse), use the arrow keys on the grip, or use the panel's ⋯ menu (Move earlier, Move later).
- **Resize a panel:**
  - drag the corner, which snaps to columns;
  - or use the menu: Narrower, Wider, Shorter, Taller, Full width.
- **Hide and restore:** Hide removes a panel; Add panel lists the hidden ones.
- **Reset:** restores the layout's standard panels.
- **Save as My Desk:** stores the current arrangement as the reader's own layout and leaves Customize.
- **Outside Customize** there are no grips, resize corners or move items: the layout cannot be changed by accident.
- **Saving:** layouts, what is folded on a phone, and the linked ticker are kept in `optic.v2.workspace.v1`. That is a setting, not personal data, and it is not shelved on an account switch.

**First visit:** a reader with no watchlist sees one band above the layout: "New to Optic? Start with a few names.", Follow buttons for a few well-known names, the explanation level, and Not now. Dismissing it is kept in `optic.v2.onboard.v1`; it does not come back.

## Linked ticker
- **Linked panels:** Quote and chart, Company news, Contracts, Fair value, Volatility, Positioning, Earnings, Business quality, Financial trends and Ownership. Each shows the ticker in a gold chip, and never draws data fetched for a ticker it is no longer linked to.
- **Choosing the ticker:**
  - choose a row in Watchlist, Moved most this month or Earnings this week;
  - choose a sector tile;
  - or type a ticker in the bar.
- **What follows the ticker:** linked panels reload; Milo's context and each linked panel's Ask Milo question carry the ticker. A folded linked panel loads the new ticker when it is opened.
- **What stays put:** the market panels (Indices, Sentiment and regime, Expected move, Sector heatmap, Economic calendar, Earnings this week, Moved most this month, Market news, Economy) describe the market and never change with it.
- **Multiple link groups:** TapeDash's coloured link groups (several tickers at once) are not built. One link covers the stated workflow. A second group is a later choice.

## Leaving and coming back
Opening detailed research (the ticker in Quote and chart opens the Dossier) and pressing Back returns to Home:
- at the same scroll position;
- with the same linked ticker;
- with every panel setting as it was (for example the heatmap period);
- with the same panels open or folded on a phone;
- without reloading what was on screen. The data already shown is repainted at once and refreshed quietly; a quiet refresh that changed nothing repaints nothing.

`walkthrough.py` checks each of these on a desktop and a narrow screen.

## Contracts: transparent comparison now, ranking later
- **Now:** the 14 contracts nearest the money at one expiry (by the size of delta, so puts work too), with strike, mid, cost, spread, delta, IV, open interest, volume and Optic's liquidity label. Every column sorts, in either direction. There is no pick, grade or score.
- **On a phone:** the row shows strike, cost, delta and liquidity, which fit a 375 px screen; the button at its end opens mid, spread, IV, open interest and volume beneath it. "All columns" in the ⋯ menu shows the full table.
- **Later (W3 in MIGRATION-TRACKER.md, not built):** an explainable suitability ranking. The reader chooses the criteria (for example the delta range, the most spread they accept, the least open interest, days to expiry); the ranking shows each contract's standing on each criterion and why it ranks where it does. It ranks fit to the reader's stated criteria, never the chance a trade works.

## Data and states
- **Wording:** Home says it is "connected to Optic's existing data sources". It never calls the page "live".
- **The footer is one line:** a short source, the as-of time (with the date when it is not today), and a status: "Delayed 15 min" or "Market closed", the source's cadence, "Updating" while a board is rebuilt, or the data's age in the warning colour when it is more than three cycles old ("Built 22 hours ago").
- **About this panel** (the "?" button, or the ⋯ menu on a phone) holds the rest: the full source, how fresh it is, any calculation note, and what Optic does not have. How fresh, from the server's own cache periods (`FRESH` in `workspace.js`):

| Panel | How fresh |
|---|---|
| Indices, Watchlist, Sector heatmap | quotes delayed about 15 minutes; refreshed every minute while the market is open |
| Your portfolio | valued at Optic's delayed prices, refreshed every minute in session; quantities as of the last broker sync |
| What matters today | rebuilt at most every 10 minutes |
| Quote and chart | quote delayed about 15 minutes; daily closes re-read at most every 5 minutes |
| Company news | headlines re-read at most every 10 minutes |
| Contracts | chain delayed about 15 minutes; re-read at most once a minute |
| Sentiment and regime, Expected move | from delayed quotes; refreshed every minute while the market is open |
| Economic calendar | schedule from the last built Read (every 20 minutes); actual and prior from FRED, re-read at most every 6 hours |
| Optic Desk | written before the open and after the close; the latest edition |
| Earnings this week | rebuilt at most once an hour |
| Moved most this month | Optic's nightly universe scan |
| Market news | the last built Read, every 20 minutes |
| Latest scan alerts | the scheduled scan |
| Economy | FRED series, re-read at most every 6 hours |
| Fair value | earnings data re-read at most every 6 hours; price delayed about 15 minutes |

- **Refresh:** the market panels refresh every minute while the regular session is open and the tab is visible.
- **States:** each panel has its own loading skeleton, error with "Try again", unavailable (what is missing and why) and stale state. A linked panel whose source returns nothing for the ticker says so in those words.
- **Fixture data:** none. Nothing on Home uses sample data.

## The first load, cold and cached
Measured with `cold_load.py`, signed in, straight after a server restart (cold) and again (cached), 2026-10-18:

| | Cold, before | Cold, now | Cached, now |
|---|---|---|---|
| What matters today | never: the request hit the 90 s limit | 0.3 s | 0.3 s |
| Earnings this week | never: the request hit the 90 s limit | 0.5 s | 0.3 s |
| Indices, regime, expected move, Desk, alerts (`/api/home`) | 0.5 s | 1.8 s | 0.8 s |
| Your portfolio | 4.8 s | 6.3 s | 1.0 s |
| Every other panel | under 1.6 s | under 2.8 s | under 1.1 s |

- **What changed:** the two scans (about 150 companies each) are served from their last build at once, labelled "Updating", while a fresh build runs in the jobs' lane; the build is kept on disk (`data/boards/`), so a deploy starts from it. A build from another New York day is never served, since its rows say "today" as of the day it was built. On the very first build ever, Home asks with `quick=true`, says it is gathering after 6 s and asks again every 12 s instead of waiting; Classic, which keeps its answer for half an hour, waits for the build as before (`main._served_while_rebuilt`, tests in `tests/test_board_serving.py`).
- **Still slow cold:** Your portfolio (6.3 s, the brokerage overview prices every holding) and, in the first seconds after a deploy, `/api/home` while the boot warm-up runs. `/api/home` is not served stale on purpose: it carries the session and the alert list, which must be current.
- **A provider blip:** when the provider briefly returns nothing for a ticker, a linked panel says so and tries once more by itself after 5 s.

## On a phone (under 860 px)
- One column, panels in the layout's order.
- The header shows two controls, both 44 px: the title (which folds or opens the panel) and the ⋯ menu, which holds About this panel, Ask Milo about this, moving, hiding, All columns and Refresh.
- The layout's essential panels are open; the rest are folded to their title and one line, and load only when opened. What the reader opens or folds is kept per layout.
- The layout tabs scroll in one row with Customize beside them. The data-sources line under the greeting is hidden: every footer names its source.
- Charts are kept short: 170 px for Quote and chart, 150 px for Economy.
- Touch targets are 44 px on a coarse pointer.

## Milo
- **Ask Milo:** each panel's button sends the panel ("Home: Contracts") as `focus.asked_from`, plus the linked ticker for linked panels. The question is drafted in the drawer, not sent.
- **End to end, with a stand-in model** (`milo_e2e.py`, 7 of 7): the drawer sends; the route accepts it within the allowance; CONTEXT tells the model the reader is on "AAPL's Home: Contracts"; the model asks for Optic's `get_quote`, Optic runs it on real data (343.46) and hands it back; the answer streams into the drawer with its sources. A real model's answers are not checked here: that needs the key, in the private preview (PREVIEW-PACKAGE.md section 7).
- **Context:** carries the layout, the visible panels, the regime, the expected move, sentiment and the linked quote.
- **Paid calls:** only when the reader sends.

## Not yet
- several link groups;
- the explainable contract ranking (W3);
- panels for products that need new data (NEW-PRODUCTS.md).
