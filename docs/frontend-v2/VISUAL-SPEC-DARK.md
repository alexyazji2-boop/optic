# v2 visual system, revised for the dark research workspace (2026-10-18)

**Primary reference:** the owner's TapeDash screenshots, for layout, density, navigation and research workflows.

**Secondary references:** Robinhood Banking and Kalshi, for polish, typography and confidence.

**What this is:** an original Optic system. Its identity stays Optic's: the logo, the gold, Inter and Space Grotesk, the names, and Milo. Nothing is copied: no TapeDash colours, names, layouts or copy.

## 1. Decisions that change earlier ones (owner, please confirm)

| # | Earlier decision | Now | Why | Status in the preview |
|---|---|---|---|---|
| X1 | v2 opens in ivory (light) unless the OS asks for dark | **v2 opens dark.** Ivory stays as the Light choice, and "Match the system" stays available | The owner asked for a near-black canvas as the application's look | Built. Only v2 changes; Classic's own default (follow the OS) is untouched. The shared key `optic.theme` keeps its values (`light`, `dark`, `system`); only an absent key means dark in v2 and "system" in Classic |
| X2 | The rail lists groups only; a group's pages appear only as tabs at the top of the page ("each name in one place", owner's point 1) | An **expandable sidebar**: each group with several pages opens to list them, and the page tabs stay on the page | The owner asked for a consistent expandable sidebar; TapeDash's navigation depends on it | Built. Each name now appears in two places, the sidebar and the page tabs. **No name changed** (`nav.js`) |
| X3 | No new navigation names without the owner's yes | The workspace needs a way in | | **Not added to the sidebar.** It is reached from Home, the command palette and a top-bar button. The rail entry, and its name, wait for the owner |
| X4 | 16 px body text everywhere | 14 px in workspace panels and tables; reading pages stay at 16 px | "Compact where users compare data" | Built. The 12 px floor holds: chart ticks only |
| X5 | Gold is light, not paint | Unchanged. Gold marks selection, focus, the active preset, the linked ticker and Milo. Primary buttons are ink on charcoal, never filled gold | TapeDash fills its primary buttons; Optic does not | Kept |
| X6 | The gold hover pill is on the sidebar only | Unchanged | | Kept |

## 2. Colour (dark, the default)
| Token | Value | Use |
|---|---|---|
| `--c-plane` | #0b0b0a | the canvas (near-black) |
| `--c-plane-2` | #0f0f0e | the sidebar |
| `--c-raised` | #151513 | panels |
| `--c-sunk` | #1c1b19 | inputs, hovered rows, segmented controls |
| `--c-line` | #2a2926 | panel borders, table rules |
| `--c-line-2` | #1f1e1c | quiet dividers inside panels |
| `--c-ink` | #eceae4 | figures, titles |
| `--c-ink-2` | #bdb9b0 | body text |
| `--c-ink-3` | #918d85 | labels and timestamps (5.4:1 on a panel; never smaller than 12 px) |
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
- **Reading pages:** 16 px.
- **No all-caps labels.** Panel titles are 14 px semibold in sentence case.

## 4. Layout and density
- **Shell:** an expandable sidebar (236 px, or 76 px collapsed), a 56 px top bar, and the content area.
- **Workspace:** a 12-column grid with 12 px gutters.
  - **Width:** each panel spans 3, 4, 6, 8 or 12 columns.
  - **Height:** compact (260 px), standard (380 px) or tall (560 px). The panel body scrolls inside itself.
- **Panel anatomy:** one border, no shadow, 10 px radius, and no card inside a card.
  - **Header (40 px):** a grip, the title, the linked-ticker chip, "How to read this", Ask Milo and a ⋯ menu.
  - **Body:** padded 12 px.
  - **Footer:** a single line with the source, the as-of time and the delayed or stale state.
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

## 8. Help
- **"How to read this":** every panel has it, in two or three plain sentences, opened in place.
- **Depth on demand:** the glossary and Milo.

## 9. Responsive
- **Under 1100 px:** panels are 6 or 12 columns wide.
- **Under 860 px:**
  - **Layout:** one column. The sidebar becomes the phone bar (names unchanged), and the workspace shows panels in their saved order, at full width.
  - **Controls:** resizing is hidden. Reordering stays available through the ⋯ menu (Move up, Move down).
  - **Tables:** scroll sideways inside the panel and keep their first column fixed.
  - **Charts:** redraw at the panel's width.
