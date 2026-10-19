# v2 visual system, revised for the dark research workspace (2026-10-18)

**Primary reference:** the owner's TapeDash screenshots, for layout, density, navigation and research workflows.

**Secondary references:** Robinhood Banking and Kalshi, for polish, typography and confidence.

**What this is:** an original Optic system. Its identity stays Optic's: the logo, the gold, Inter and Space Grotesk, the names, and Milo. Nothing is copied: no TapeDash colours, names, layouts or copy.

## 1. Decisions that change earlier ones

The owner reviewed X1 to X3 on 2026-10-18 and decided them; the table records the outcome.

| # | Earlier decision | Now | Why | Status in the preview |
|---|---|---|---|---|
| X1 | v2 opens in ivory (light) unless the OS asks for dark | **v2 opens dark.** Ivory stays as the Light choice, and "Follow system" stays available | The owner asked for a near-black canvas as the application's look | **Accepted by the owner.** Built. Only v2 changes; Classic's own default (follow the OS) is untouched. The shared key `optic.theme` keeps its values (`light`, `dark`, `system`); only an absent key means dark in v2 and "system" in Classic |
| X2 | The rail lists groups only; a group's pages appear only as tabs at the top of the page ("each name in one place", owner's point 1) | Proposed: an expandable sidebar listing each group's pages as well | | **Rejected by the owner: navigation is never repeated.** The sidebar is for destinations; a destination's tabs are for its distinct views. The expandable lists were removed (`shell.js`), and the rail is back to destinations only. **No name changed** (`nav.js`) |
| X3 | No new navigation names without the owner's yes | The workspace needs a way in | | **Resolved by the owner: Home is the workspace.** Home opens on the Market Overview layout, with a visible layout selector (Market Overview, Options Research, Long-Term Investing, My Desk). My Desk is the reader's own saved layout. There is no separate destination, no new rail name and no top-bar button; old `#/workspace` links land on Home |
| X4 | 16 px body text everywhere | 13.5 to 14 px in Home's panels and in tables; 15 px on every other page | "Compact where users compare data", and one page system across all pages (owner, 2026-10-18) | Built. Nothing on any page is under 12 px, chart labels included (style audit, 2026-10-18) |
| X5 | Gold is light, not paint | Unchanged. Gold marks selection, focus, the active preset, the linked ticker and Milo. Primary buttons are ink on charcoal, never filled gold | TapeDash fills its primary buttons; Optic does not | Kept |
| X6 | The gold hover pill is on the sidebar only | Unchanged | | Kept |

## 2. Colour (dark, the default)
| Token | Value | Use |
|---|---|---|
| `--c-plane` | #0b0b0a | the canvas (near-black) |
| `--c-plane-2` | #0f0f0e | the sidebar |
| `--c-raised` | #161614 | panels |
| `--c-sunk` | #201f1c | inputs, hovered rows |
| `--c-active` | #2d2c28 | a chosen segment, tab or drawing tool (with a 1 px line or the gold edge) |
| `--c-line` | #363430 | panel borders, table rules (1.46:1 against a panel, was 1.26:1) |
| `--c-line-2` | #272623 | quiet dividers inside panels |
| `--c-ink` | #f3f1eb | headings and primary figures (16:1 on a panel) |
| `--c-ink-2` | #c9c5bc | supporting text and inactive controls (10.5:1) |
| `--c-ink-3` | #a29e95 | labels and timestamps (6.8:1 on a panel, was 5.5:1; never smaller than 12 px) |

**Four steps of emphasis** (owner, 2026-10-18 second review: "secondary text and borders look subdued"): headings and figures in `--c-ink` and semibold; supporting text in `--c-ink-2`; labels and times in `--c-ink-3`; an inactive control reads in `--c-ink-2` and a chosen one is `--c-active` with full ink and semibold, so chosen and not chosen differ by more than a shade.
| `--c-gold` | #d4b144 | selection, focus, Milo, the mark |
| `--c-pos` / `--c-neg` | #4cc38a / #f07a66 | direction only, always with a sign or arrow, never colour alone |
| `--c-warn` | #e7b25a | stale or unavailable data |

**Ivory (Light)** keeps the approved values in `tokens.css`.

## 3. Type
- **Inter for reading, Space Grotesk for labels and tickers.**
- **Workspace and tables:**
  - body 14 px / 1.45;
  - labels 13 px;
  - figures 14 to 16 px semibold with tabular numbers;
  - headline figures 22 to 28 px.
- **Every other page:** 15 px reading text; tables 13.5 px with 12 px headers; a second line inside a cell (a mid, a share count) never under 12 px.
- **Page titles:** 28 px semibold (24 px on a phone) on Home, Macro, Watchlist, Alerts and Settings. A company's pages lead with the price instead (44 px, 34 px on a phone), with the name and sector above it.
- **No all-caps labels.** Home's panel titles are 15 px semibold in sentence case, in full ink.

## 4. Layout and density
- **Shell:** a labelled sidebar of destinations only (236 px, or 76 px collapsed), a 56 px top bar, and the content area. A destination's views are its page tabs, never listed again in the sidebar.
- **One page system:** every page sits on Home's canvas. Each top-level section is a bordered charcoal panel (`--c-raised`, 1 px `--c-line`, 10 px radius, 16/18 px padding, 12 px apart; 12 px padding on a phone). Section titles are 18 px. Measured on all eight representative pages at both sizes (`style_audit.py`).
- **Home (the workspace):** a 12-column grid with 12 px gutters.
  - **Width:** each panel spans 3, 4, 6, 8 or 12 columns.
  - **Default heights by kind** (owner, 2026-10-18 second review: "identical styling doesn't require identical proportions"):
    - **Lists and tables** (Watchlist, Company news, Contracts, Economic calendar, Earnings this week, Moved most this month, Market news, Latest scan alerts) start at a height for their kind (compact 210 px, standard 300 px, tall 470 px of body), fill the rest of their row, and scroll inside.
    - **Everything else** (Indices, Your portfolio, What matters today, Quote and chart, Sentiment and regime, Expected move, Sector heatmap, Optic Desk, Economy, Fair value) sizes to its content and never stretches, so it is never half empty. Charts take their height from the panel's height choice (Quote and chart 170, 230 or 340 px).
    - **The default layouts pair them:** a panel that sizes to its content beside a list that fills the row (Quote and chart with Watchlist, What matters today with Company news, Sector heatmap with Economic calendar, Optic Desk with Earnings).
    - **No holes:** a row the next panel cannot join ends early, and its last panel widens to the row's end (for example when Your portfolio is absent). Saved widths are unchanged.
    - **Your portfolio** spans the width with its value and chart beside the holdings.
- **Panel anatomy:** one border, no shadow, 10 px radius, and no card inside a card.
  - **Header (40 px):** a grip, the title, the linked-ticker chip, "?" (About this panel), Ask Milo and a ⋯ menu.
  - **Body:** padded 12 px.
  - **Footer: one line.** A short source, the as-of time (with the date when it is not today), and a status in a word or two: "Delayed 15 min" or "Market closed" for quoted panels, the source's cadence for the rest ("Every 10 min", "Hourly", "Nightly scan"), "Updating" while a board is rebuilt, and "Built 22 hours ago" in `--c-warn` when a source is more than three of its cycles old.
  - **About this panel** ("?"): how to read it, then the full source, how fresh it is, any calculation note, and what Optic does not have (for example licensed consensus forecasts).
  - **Narrow panels** (under 420 px): Ask Milo shows as its mark, with the words kept for screen readers, so the title is never cut.
- **Compact and generous space:**
  - Comparisons (tables, metric strips, heatmaps) are compact.
  - Charts and explanations get room: a chart panel is 6 columns or wider.
- **Not used:**
  - floating controls over content (Milo is in the top bar and in panel headers, not a floating button);
  - decorative badges;
  - nested cards;
  - grey text under 12 px.

## 5. Tables
- **Numbers:** right-aligned with tabular numbers and the unit in the header. Text is left-aligned.
- **Headers:** sortable headers are buttons with `aria-sort` (`ui/table.js`).
- **Rows:** 36 px on desktop and 44 px on touch.
  - A selected row has a gold left rule and `aria-selected`.
  - A row that sets the linked ticker is a button row with Enter and Space.
- **Pagination:** shown when there are more than 25 rows ("1–25 of 151", Previous and Next). Filters sit in one row above the table.
- **Empty, stale and unavailable** each have their own line in words, never a dash alone.

## 6. Charts
- **The Chart page** (owner, 2026-10-18 second review: "the large company header and multiple rows of text buttons push the chart downward"):
  - a one-line header: ticker, name, price, change, the extended-hours price, and small Watch, Alert, Compare and Ask Milo;
  - one row of settings: bar size, range or session, style as three named icons, Indicators, and zoom out, zoom in and fit as named icons;
  - the drawing tools as a column of named icon buttons beside the plot, grouped as pointer, lines (horizontal, vertical, trend, ray), shapes (rectangle, Fibonacci) and notes, then undo, delete selected and remove all; on a phone they are a row behind "Draw";
  - the plot fills the rest of the window: it starts 275 px down at 1440 by 900 (it started about 475 px down) and is 614 px tall.
- **One engine per kind:**
  - `ui/pricechart.js` for prices;
  - `ui/chart.js` for lines, sparklines and meters;
  - `ui/xychart.js` and `ui/bars.js` for bars.
- **Axes:** on the right with price-scaled ticks, and a grid at 1 px in `--c-chart-grid`.
- **Interaction:** a tooltip on hover or focus, and a crosshair on price charts.
- **Legend:** shown when there are two or more series, with direct labels when there are four or fewer.
- **Range controls:** a segmented control above the chart, at the right.
- **Expanded view:** the panel goes to full width.
- **The as-of line:** goes under every chart.

## 7. Data status (everywhere a figure appears)
- **Live, delayed and closed:** from the session and the quote's own time.
- **Stale:** when the data is older than its refresh period, in `--c-warn` with the age.
- **Unavailable:** names what is missing and why.
- **Error:** says what did not load, with "Try again".
- **Loading:** shaped skeletons, never spinners.
- **Fixture data** (the preview only, and only where no live source exists): labelled "Sample data" in the panel footer.
- **How fresh, per panel:** the footer gives the status in a word or two; About this panel gives the full sentence from the server's own cache periods (quotes delayed about 15 minutes and refreshed every minute in session, option chains re-read at most once a minute, headlines every 10 minutes, earnings data and FRED series every 6 hours, movers from the nightly scan). The words are in `FRESH`, `CADENCE` and `SRC` in `pages/workspace.js`. The page says it is connected to Optic's existing data sources; it never says "live" for a whole page.
- **A change of source inside a chart:** the line breaks there, a dashed bridge joins the two sides, and a rule says "Source changes", so a step is never read as a gain or loss (Your portfolio, where the provider's estimated balances give way to Optic's own snapshots).

## 8. Help
- **"About this panel":** every panel has it, opened in place: two or three plain sentences on how to read it, then where its figures come from and how fresh they are.
- **Depth on demand:** the glossary and Milo.

## 9. Responsive
- **Under 1100 px:** panels are 6 or 12 columns wide.
- **Under 860 px:**
  - **Layout:** one column. The sidebar becomes the phone bar (names unchanged), and Home shows panels in their saved order, at full width.
  - **What opens first:** each layout names its essential panels (Market Overview: indices, portfolio, the linked quote, watchlist, today's priority). Those are open; the rest are folded to a title bar and load only when opened. What the reader opens or folds is kept per layout.
  - **Panel header:** two controls, both 44 px: the title itself (which folds or opens the panel) and the ⋯ menu. About this panel, Ask Milo about this, moving, hiding, All columns and Refresh are in the menu.
  - **Chart heights:** 170 px for the linked quote and 150 px for economic series, so a chart never fills the screen.
  - **Contracts:** the row shows strike, cost, delta and liquidity, which fit a 375 px screen; a button at the row's end opens every other figure (mid, spread, IV, open interest, volume) beneath it. "All columns" in the ⋯ menu shows the full table, and says to scroll sideways.
  - **Other tables:** secondary columns (revenue estimates; volume on movers; the watchlist's last change) are hidden on a phone; "All columns" shows them.
  - **Controls:** resizing is hidden. Reordering stays available through the ⋯ menu (Move up, Move down).
  - **Tables:** scroll sideways inside the panel and keep their first column fixed.
  - **Charts:** redraw at the panel's width.

## 10. Navigation and shared controls (added 2026-10-19)
Three levels, each with one look (owner's placement review: "sidebar destinations, page or workspace tabs, local filters and actions"):
- **Destinations:** the rail and the phone bar. The gold hover pill stays on the sidebar only. The phone bar reads Home, Markets, Watchlist, Dossier, More; More lists every other destination, Discover first among them.
- **Page and workspace tabs:**
  - A destination's page is headed by the destination's name (Markets, Discover, Positions, Watchlist); its tab row names the view. The selected tab has a gold underline.
  - Under 640 px a tab row becomes a view selector (`.tabsel`): the list's name in small type, then the current view in 16 px, with a chevron. Nothing is clipped at the screen edge.
  - A page with more than one group of tools uses a group bar (`.op-groups`, `.gtabs`): equal segments in a sunken track; the selected one is raised with a gold border. Under 640 px a four-group bar is two by two, and labels wrap rather than clip. A group's own views are chips under the bar (`.gsub`).
- **Local filters and actions:**
  - Seg buttons and chips for filters; selects for long lists.
  - A ticker's actions sit together at the right of its header: Watch, then "Ask about SYM", whose outline is the Milo gold. Alert and Compare are quiet (`.btn-quiet`: no border, ink-2 text); under 640 px they move under ⋯.
  - The top bar's "Ask Milo" is the general launcher; a contextual Milo button names what it asks about.
  - A ⋯ or Indicators menu closes on a click elsewhere and on Escape, returning focus to its button.

## 11. States added 2026-10-19
- **Coverage line** (`.ins-cover`): before the rows, what a view covers (which filings, which dates) and how much of it is read. A partial result is marked "Partial." in the warning colour, with what is still to read.
- **Milo off:** when the deployment has no model, every Milo button has a dashed outline and an "Off" tag (a corner badge on the phone's icon button) and is described for screen readers. It still opens Milo, which says why.
- **One reason, said once:** when every panel in a group fails for the same reason (an unquoted option chain outside market hours), the group says it once.
- **Disabled until ready:** controls that need data not yet loaded (the Options templates before an expiry has loaded) are disabled, and the select names what it is waiting for ("Loading expiries", "Expiries unavailable").

## 12. Financials
- A summary first: the latest fiscal year's figures in a row of readings (two columns on a phone), then what the statements say.
- A jump list of the sections the company has: chips under the top bar on a wide screen (they stay in view while scrolling), a "Jump to" selector on a phone. A jump moves focus to the section's heading.
- Chart cards state the latest value and its change on the year before above the bars.
- Tables keep their first column in place while the figures scroll; figures are right-aligned with tabular numerals.
