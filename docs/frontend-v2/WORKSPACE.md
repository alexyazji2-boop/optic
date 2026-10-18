# The research workspace (`#/workspace`, preview)

`static/v2/js/pages/workspace.js`. Built 2026-10-18 on branch `v2-dark-workspace`. Checked by `~/Optic/work/v2-2026-10-17/workspace/ws_verify.py` (45 checks).

## Layouts
| Preset | Panels, in order |
|---|---|
| Market Overview | Indices, Sentiment and regime, Expected move, Sector heatmap, Economic calendar, Earnings this week, Moved most this month, Watchlist, Quote and chart, Market news, Company news, Economy |
| Options Research | Watchlist, Quote and chart, Contracts, Expected move, Earnings this week, Company news, Moved most this month |
| Long-Term Investing | Watchlist, Quote and chart, Fair value, Sector heatmap, Economy, Sentiment and regime, Company news |
| My Desk | the reader's own: a copy of Market Overview, or whatever "Save as My Desk" stores |

**What a reader can do to a layout:**
- **Move a panel:** drag its grip (mouse), use the arrow keys on the grip, or use the panel's ⋯ menu (Move earlier, Move later).
- **Resize a panel:**
  - drag the corner, which snaps to columns;
  - or use the menu: Narrower, Wider, Shorter, Taller, Full width.
- **Hide and restore:** Hide removes a panel; Add panel lists the hidden ones.
- **Lock layout:** hides every move and resize control.
- **Reset:** restores the preset's standard layout.
- **Open this at Home:** Home opens the workspace in this browser.
- **Saving:** layouts are saved per preset in `optic.v2.workspace.v1`. That is a setting, not personal data, and it is not shelved on an account switch. It holds the linked ticker too.

## Linked ticker
- **Linked panels:** Quote and chart, Company news, Contracts and Fair value. Each shows the ticker in a gold chip.
- **Choosing the ticker:**
  - choose a row in Watchlist, Moved most this month or Earnings this week;
  - choose a sector tile;
  - or type a ticker in the bar.
- **What follows the ticker:** linked panels reload; Milo's context and each linked panel's Ask Milo question carry the ticker.
- **What stays put:** Indices, Sentiment and regime, Expected move, Sector heatmap, Economic calendar, Earnings this week, Moved most this month, Market news and Economy describe the market and never change with it.
- **Multiple link groups:** TapeDash's coloured link groups (several tickers at once) are not built. One link covers the stated workflow. A second group is a later choice.

## Data and states
- **Data:** every panel reads an existing endpoint with its own cache time.
- **Refresh:** market panels refresh every minute while the regular session is open and the tab is visible.
- **States:** each panel has its own:
  - **loading:** a skeleton;
  - **error:** what failed, with "Try again";
  - **unavailable:** what is missing and why;
  - **stale:** the age or "last close" in the footer.
- **Footer:** gives the source and the as-of time.
- **Fixture data:** none. Nothing in the workspace uses sample data.

## Milo
- **Ask Milo:** each panel's button sends the panel ("Workspace: Sector heatmap") as `focus.asked_from`, plus the linked ticker for linked panels.
- **Context:** carries the layout, the visible panels, the regime, the expected move, sentiment and the linked quote.
- **Paid calls:** only on a click.

## Not yet
- a sidebar entry (waits for the owner to name it);
- several link groups;
- panels for products that need new data (NEW-PRODUCTS.md).
