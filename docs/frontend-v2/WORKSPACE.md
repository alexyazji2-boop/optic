# Home, the research workspace (`#/`, private preview)

`static/v2/js/pages/workspace.js`. Built 2026-10-18 on branch `v2-dark-workspace`.

**What the owner decided (2026-10-18):** Home *is* the workspace. It opens on the Market Overview layout with a visible layout selector. My Desk is the reader's own saved layout. There is no separate workspace destination, no new sidebar name and no top-bar button. Old `#/workspace` links land on Home.

**Checked by** (in `~/Optic/work/v2-2026-10-17/workspace/`):
- `ws_verify_home.py`: 47 checks on Home's layouts, linking, panels, states and phone folding.
- `walkthrough.py`: the owner's review flow, step by step, on a desktop and a narrow screen (18 checks).
- `style_audit.py`: Home measured against the other seven representative pages.

## Layouts
| Layout | Panels, in order | Open first on a phone |
|---|---|---|
| Market Overview (the default) | Indices, Your portfolio, What matters today, Watchlist, Quote and chart, Company news, Contracts, Sentiment and regime, Expected move, Sector heatmap, Economic calendar, Optic Desk, Earnings this week, Moved most this month, Market news, Latest scan alerts, Economy | Indices, Your portfolio, What matters today, Watchlist, Quote and chart |
| Options Research | Watchlist, Quote and chart, Contracts, Expected move, Earnings this week, Company news, Moved most this month | Watchlist, Quote and chart, Contracts |
| Long-Term Investing | Your portfolio, Watchlist, Quote and chart, Fair value, Sector heatmap, Economy, Sentiment and regime, Company news | Your portfolio, Watchlist, Quote and chart, Fair value |
| My Desk | the reader's own: a copy of Market Overview, or whatever "Save as My Desk" stores | as Market Overview |

**Your portfolio** shows only when an account is linked. A reader with no linked account does not see an empty panel.

**What Home carried over from the old Home:** the greeting and date, the first-visit welcome and starters (shown to a new reader above the layout), What matters today with its filters, the Optic Desk, the portfolio value with its chart, Latest scan alerts and Moved most this month. Their copy is unchanged; the panels reuse the old Home's own renderers (`pages/home.js`).

**What a reader can do to a layout:**
- **Move a panel:** drag its grip (mouse), use the arrow keys on the grip, or use the panel's ⋯ menu (Move earlier, Move later).
- **Resize a panel:**
  - drag the corner, which snaps to columns;
  - or use the menu: Narrower, Wider, Shorter, Taller, Full width.
- **Hide and restore:** Hide removes a panel; Add panel lists the hidden ones.
- **Lock layout:** hides every move and resize control.
- **Reset:** restores the layout's standard panels.
- **Save as My Desk:** stores the current arrangement as the reader's own layout.
- **Saving:** layouts, the lock, what is folded on a phone, and the linked ticker are kept in `optic.v2.workspace.v1`. That is a setting, not personal data, and it is not shelved on an account switch.

## Linked ticker
- **Linked panels:** Quote and chart, Company news, Contracts and Fair value. Each shows the ticker in a gold chip.
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
- **On a phone:** mid, IV and volume are hidden; "All columns" in the ⋯ menu shows them.
- **Later (W3 in MIGRATION-TRACKER.md, not built):** an explainable suitability ranking. The reader chooses the criteria (for example the delta range, the most spread they accept, the least open interest, days to expiry); the ranking shows each contract's standing on each criterion and why it ranks where it does. It ranks fit to the reader's stated criteria, never the chance a trade works.

## Data and states
- **Wording:** Home says it is "connected to Optic's existing data sources". It never calls the page "live".
- **Freshness, per panel:** every footer names the source, the as-of time, and how fresh that source is, from the server's own cache periods (`FRESH` in `workspace.js`):

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

## On a phone (under 860 px)
- One column, panels in the layout's order.
- The layout's essential panels are open; the rest are folded to their title and one line, and load only when opened. What the reader opens or folds is kept per layout.
- The layout tabs scroll in one row. Add panel, Lock, Reset and Save as My Desk sit under "Layout options".
- Charts are kept short: 170 px for Quote and chart, 150 px for Economy.
- Touch targets are 44 px on a coarse pointer.

## Milo
- **Ask Milo:** each panel's button sends the panel ("Home: Contracts") as `focus.asked_from`, plus the linked ticker for linked panels. The question is drafted in the drawer, not sent.
- **Context:** carries the layout, the visible panels, the regime, the expected move, sentiment and the linked quote.
- **Paid calls:** only when the reader sends.

## Not yet
- several link groups;
- the explainable contract ranking (W3);
- panels for products that need new data (NEW-PRODUCTS.md).
