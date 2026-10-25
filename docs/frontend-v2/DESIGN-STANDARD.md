# Optic design standard (v2), 2026-10-19

The character is a precise, credible financial research product. It keeps the dark charcoal direction, the Optic mark and Scout. The Chart page is the reference: a compact identity line, clear tools, and most of the screen for the work.

The tokens live in `static/v2/css/tokens.css`. `tests/test_v2_design_standard.py` keeps the rules from drifting, and `tests/test_v2_checklist.py` keeps the owner's checklist.

## The rules

### Hierarchy
There are four levels, and each has one look.

1. **Page navigation:** the sidebar and the page and dossier tabs. Tabs are text, and the current one is ink with a 2px gold bar under it.
2. **Local controls:** segmented controls, selects and toolbars. They are quiet: a sunk track, and an active fill for the choice, with no gold.
3. **Primary findings:** the headline answer or number, in ink, at `--t-xl` and up.
4. **Supporting information:** ink-2 for supporting text and ink-3 for labels, sources and times, at `--t-sm` to `--t-base`.

### Type
- **Faces:** Inter for reading, Space Grotesk for labels and tickers.
- **Sizes:** eight steps, `--t-xs 12`, `--t-sm 13`, `--t-md 14`, `--t-base 15`, `--t-lg 16`, `--t-xl 18`, `--t-lead 20` and `--t-2xl 24`.
  - Half-pixel sizes were rounded up into these.
  - A literal size of 22px or more is allowed only for a component's headline figure.
- **Weights:** 400, 500 and 600, nothing else.

### Figures
`font-variant-numeric: tabular-nums` applies to every place numbers are compared: value tiles, tables, the header price, panels, the chart readout, segmented controls, chips and legends. Numbers in tables are right-aligned (`table.t`, `table.st .n`).

### Scores (owner, 2026-10-21)
A score with a good and a bad side is coloured and has a thin line filled to it (`ui/score.js`), as Classic showed:
- a 0 to 100 score where 50 is no edge (the Optic Score, the composite, the long-term trend score, Compare's horizon scores): green from 55, red to 45, grey between;
- a signed score (the market score, −100 to +100): green above zero, red below, its line filled out from a middle mark;
- a banded reading (the dividend score, the sentiment gauge): its band's side (strong or solid, greed: green; weak, fear: red).

The figure carries the colour too and the words say the reading, so colour never carries it alone; the line is hidden from a screen reader. A reading with no good side (RSI, IV rank, the trend strength oscillator) stays uncoloured, and a rank (Compare's "best") is not a direction.

### Search (owner, 2026-10-21)
Every search for a symbol looks like TradingView's, squared: the top bar's search has a search icon, the box, Clear and close; then a filter row (All, and only the kinds of listing the results hold: Stocks, Funds, Indices, Futures, Crypto, Currencies); then one row per listing: the logo (from Optic's `/api/logo`, the symbol's initial where there is none), the symbol, the name, and the kind of listing on the right (`ui/symbols.js`). The letters typed are gold in the symbol and the name (the owner's choice). The symbol boxes on the pages (Watchlist, Alerts, Analysts, Compare, the Chart tab, Home's linked ticker) show the same rows under them (`ui/typeahead.js`, opted into with `data-v2-ta`). No exchange is shown: the search does not carry one.

### Surfaces and borders
| Token | Used for |
|---|---|
| `--c-plane` | the page |
| `--c-plane-2` | the sidebar, and a control's track |
| `--c-raised` | panels, cards, drawers and menus |
| `--c-sunk` | inputs, wells, the reader's own Milo bubble, and hover on quiet controls |
| `--c-active` | a chosen segment or tab |

- **Borders:** `--c-line` draws a container's edge. `--c-line-2` divides rows inside it.
- **Nesting:** a block inside a panel does not get a second card. It gets a divider, or nothing.
- **Containers follow the relationship of their contents:**
  - Home's panels are separate cards, because each is its own source and freshness.
  - A row of related figures is one container with dividers.
  - Prose sits on the page.

### Corner radii, by what the shape holds
| Token | Size | Used for |
|---|---|---|
| `--r-xs` | 4px | marks, swatches, tags inside rows |
| `--r-sm` | 6px | an item inside a control (a segment, a menu row) |
| `--r-md` | 8px | controls: buttons, inputs, selects, chips, segmented tracks |
| `--r-lg` | 12px | panels, cards, menus, popovers |
| `--r-xl` | 16px | sheets and drawers on a phone, the palette |

- **Pill:** `--r-pill` is the sidebar's gold hover pill (owner's rule) and counts. 50% is for avatars, dots and round icon buttons.
- **Literal:** 2px for bars and marks.

### Controls
- **Height:** 44px (`--tap`) for anything a finger reaches. A dense toolbar (the Chart page) uses 36px (`--ctl-sm`) controls inside a 44px row, and coarse pointers get 44px everywhere.
- **Buttons:**
  - Default: raised with a line border.
  - `.btn-quiet`: no border.
  - `.btn-primary`: gold fill with dark ink. That's the view's one most important action, such as Send, Sign in, Create account, Compare or Run screen.
  - `.btn-milo`: quiet, with Milo's line icon before the words.
- **A pressed toggle** such as Watching: the active fill and an ink-3 border, never gold.
- **Text links:** ink, underlined in `--c-line`, and fully underlined on hover.

### Gold
Gold appears for:
- the current selection (the tab bar, the current sidebar icon);
- the view's one most important action (`.btn-primary`);
- the brand mark;
- focus;
- the top bar's Ask Milo (Scout's head, and the one gold-outlined Milo entry);
- data in charts.

The sidebar's gold hover pill stays the sidebar's alone (owner's rule). Milo inside pages, pressed toggles, links and panel actions are not gold.

### Elevation
Shadows are only for what floats over the page:
- `--sh-pop` for menus, popovers and tips;
- `--sh-sheet` for drawers and the palette.

A segmented control's chosen segment keeps a 1px ring. Gold bars are inset shadows standing in for borders.

### Icons
One family, the line icons in `ui/icons.js`: a 24px grid, a stroke of about 1.6 to 1.8, round joins. The shared panels' text glyphs (⠿, ?, ⋯) became `grip`, `help` and `more`. Scout is the mascot, not an icon. He appears on the top bar's button and in the Milo panel only.

### Decoration and motion
- No decorative gradients, glows, stock illustrations or emoji. The two gold glows (the Home scene's lens and the first-visit art) were removed.
- Two gradients remain, both functional: the sidebar's divider and the loading shimmer.
- Motion answers an action (opening, expanding), or carries meaning (Scout reacting to Milo's events, the loading shimmer). Under reduced motion it stops.
- **One motion system** (2026-10-22, `ui/motion.js`, tokens in `css/tokens.css`): `--m-press` 90 ms for a control's own feedback, `--m-content` 150 ms for content arriving, `--m-panel` 200 ms for a drawer or panel, `--m-exit` 130 ms for anything leaving (faster than it came); `--ease-out` for entrances, `--ease-drawer` for sheets. No page writes its own durations. Nothing is delayed to make a motion visible. Added 2026-10-24: `--m-hover` 120 ms for hover and focus colour, `--m-reveal` 400 ms for a line chart's first draw (it was 620 ms), `--m-stagger` 24 ms between at most the first four things that arrive together.
- **The activity line** is the one loading indicator that moves: thin, gold, only while there is real work. The page's sits under the top bar while a section still shows its skeleton (after 220 ms, so a fast load never flashes); Milo's runs inside an answer from Send until it is complete, stopped or failed. With reduced motion it stands still at full width.
- **Tabs** (every strip: a Dossier's and a section's): the pressed tab is the selected one in the same frame as the press, and its gold bar slides from the last one, before the next page's code has loaded. The content under the header fades in once drawn, on phones too, where the strip is a menu. Only between pages of one strip, never when the same page draws again. A new symbol keeps its own loading layout. No full-page fades, no staggered rows, no background flashes on prices, no pulsing controls.
- **A changed price** (the Dossier header and the watchlist, on a refresh) holds its direction's colour for about a second and eases back. The figure is the record; nothing counts up to it.
- **Charts:** the first line or area chart on a page traces itself in over `--m-reveal`. Any press, key or wheel on it, a zoom, a pan or a new bar finishes it at once; a redraw over the same bars carries it on. Changing the Chart page's bar size dims the chart on screen with "Loading 1h bars" over it until the new bars replace it in one frame; if they fail it stays dimmed with the reason and Try again. Axes never animate, and one symbol's line never turns into another's.
- **The Motion setting** (Settings, Appearance; `optic.v2.motion.v1`): "Follow system" or "Reduce". Reduce sets `html[data-motion="reduce"]`, which the CSS and `reducedMotion()` in `core/dom.js` treat exactly as the system setting, and Scout goes still with it unless the reader chose his motion.
- **Milo's states** are only those an event supports: submitted, preparing, retrieving (the server's own tool words), streaming, complete, stopped, failed (`MILO_STATES` in `ui/milo.js`). After 30 seconds with nothing from the server, the answer says "No reply from the server for 30 seconds" beside Stop, and the line goes when anything arrives. Milo's context bar lists the parts of the page that go with a question, each removable until the reader changes page. Each answer has Report a problem, which goes to the operator's problem reports with the question and answer, and says it does not train the model.

### Phase 2 of the motion proposal (2026-10-24)
- **Keyboard:** `?` outside a field opens the one list of shortcuts (`ui/shortcuts.js`); every key on it is one the code handles, and a test pairs them. In the search box, `>` first lists pages and actions only.
- **Linked panels on Home** say "Follows NVDA" on a squared marker; pressing it keeps that panel's ticker ("Kept on NVDA", dashed) until pressed again. One function, `symOf(id)`, is the ticker a panel loads and paints.
- **One More menu per ticker** (`tickerMenu` in `ui/company.js`) on the Dossier header and the company drawer. Copy price copies the figure on screen with the words that date it, never one that is not shown.
- **SEC filing marks** on the price chart come from the ticker payload's EDGAR list, on their filing dates, off by default; the note says only the latest are marked.
- **Compare** (Chart, Layers): up to three symbols in percent from a stated start bar, the first bar at or after the start's moment. Bars are matched by time; a missing bar is a gap. Yields are refused. Layers in price and the drawing tools stand aside while comparing.
- **Crosshair sync:** charts given the same `sync` group follow each other by date (Options: price, RSI and MACD; Brokerage: return and value). Each shows its own figure; a chart with no point on that date says so.

### Price chart indicators
The owner's mapping (2026-10-24): VWAP the one cool hue (the indicator exception to "no purple"), EMA 50 red and dashed, EMA 21 green, EMA 9 the ink, white on charcoal. Tokens `--c-ind-vwap`, `--c-ind-ema50`, `--c-ind-ema21`, `--c-ind-ema9` in `css/tokens.css`. The red and green are deeper and shifted from `--c-neg` and `--c-pos` so a line never reads as a candle, every one clears 4.5:1 on a panel in both themes, and each line is named at its right end in its own colour (`.endl` in `ui/pricechart.js`), so none is identified by colour alone.

### Explanations
- **Visible:** a section shows its finding and one useful line.
- **Folded:** methods, formulas, conventions and caveats go behind one shared fold, "How this works" (`ui/states.js` `how()`), under those words everywhere.
- **Where it's applied:** the Options contracts table and the dealer gamma panel. The table's report-inside-the-expiry note stays in view, because it is a finding.

### Long pages and sideways strips (Classic parity B3, 2026-10-21)
- **Sections fold.** Every top-level section with a heading folds by its heading or its chevron button (`ui/sections.js`). A folded section is its heading line alone. Sections above the reader's knowledge level start folded and say "Advanced".
- **The section strip.** A page with six or more sections gets a strip of their names with Expand all, Collapse all and Panels. It is sticky under the header on a desktop and scrolls away on a phone, like the header. The section on screen is lit like a tab: ink with the gold bar.
- **Sideways strips say there is more with an arrow, not a fade.** A fade would be a third gradient. The arrow sits over the strip's edge, in the colour behind it, only while there is more that way, and it scrolls the strip (`ui/strips.js`).

### Headers
Every dossier tab uses the Chart page's one-line header (`dossier-frame.js` `header()` now defaults to `bar`):
- the company's logo (`/api/logo`, over the symbol's initial; `ui/symbols.js`), as in Classic's header (2026-10-25);
- the ticker and name;
- the price and the day's move;
- the extended-hours price;
- on the Overview only, the Weinstein stage as a text label in the same line ("Stage 2, advancing"), never a chip; what it means for the symbol opens from the label (Classic parity B6a);
- Alert, Compare, Watch and Ask about at the right.

The Overview adds two of Classic's controls (owner's screenshots, 2026-10-25):
- the Weinstein stage in Classic's words ("Stage 3 · Topping breakdown") as a text label, never a chip, coloured by its stage, opening what it means for the symbol, with Explain beside it, which drafts the question for Milo. With the stage the header takes a second line, and the actions sit on it at the right;
- "Show advanced analysis" at the end of the tab row (under the tabs on a phone): a squared switch on Classic's knowledge keys, so it, Settings and Classic never disagree. It opens Advanced research and the full case for and against.

The account button never wraps (`white-space: nowrap; flex: none`).

## What changed, measured
| | Before | After |
|---|---|---|
| Font sizes in the CSS | 26 distinct | the 8 steps, plus 6 headline-figure sizes (22, 26, 28, 30, 34, 40px) |
| Font weights | 6 (400 to 700) | 3 |
| Corner radii | 25 distinct values | 5 steps, pill, 50%, and 2px for bars |
| Shadows | 18 | 14 (2 elevation tokens; the rest are rings and bars) |
| Gradients | 4 (two decorative glows) | 2, both functional |
| Gold on the first screen, outside charts and the sidebar (1440×900, signed in) | Home about 6, dossier 3, Options 5, Chart about 6 (counted from the before screenshots) | Home 3, dossier 2, Options 3, Chart 3 (`gold_probe.py`) |
| Research starts on a dossier at 1440 (top of the tabs) | 203px on Overview, 290px on Options (actions wrapped) | 140px |
| Ink-3 on a panel (dark) | 6.7:1 | 8.4:1 |

**Checked:**
- `sweep2.py` at five sizes on twelve routes: 60 of 60 clean (no overflow, nothing under 12px, no clipped tabs, no em dashes), and the launch audit at 0 faults (contrast, unnamed controls, small targets, heading order, duplicate ids).
- Full suite: 6361 passed, 1 skipped.

**Screenshots:** before and after side by side for Home, the AAPL dossier, Chart and Options at 1440, and Home, dossier and Chart at 390. They're in `docs/frontend-v2/design-standard/`. The capture tool is `~/Optic/work/v2-design-standard/capture.py`.

## The review's fixes, done with it
- **The Read's `**bold**` markers:** the paragraphs now render bold, escaped first (`format.js` `bolded()`). This covers the Read, the release read, the weekly update, a stock's read and the pre-earnings brief.
- **Short interest:**
  - A missing share of float was shown as 0.0% and concluded "Squeeze potential low".
  - The server now says "not known" without it (`fundamentals.py`, so Classic prints the honest word too).
  - v2 shows "Not reported" for every missing figure and draws no squeeze reading.
- **Markets' two clocks:** "Prices and headlines updated N ago" for the data refresh. Under the text: "This text was written N ago, from the figures at that time; the prices above are newer" when they are.
- **Discover's line** is now a description of what the section shows.
- **Chart:** Explain and full screen no longer sit on the readout when a side panel narrows the plot.

## Remaining inconsistencies
1. **Spacing:** 52 distinct gap values and 125 distinct paddings remain. The 4px scale (`--s-1` to `--s-10`) is defined, but most page CSS still uses literal values, including off-scale 6, 10 and 14px.
2. **Headline figure sizes** are literal per component (22 to 40px) rather than two or three named steps.
3. **Explanations:** only Options is folded. Inline method text remains in several places:
   - the Overview chart's footnote about Greeks, which does not belong under a price chart;
   - Investing's valuation notes;
   - Earnings;
   - several Home panels' sub-lines;
   - the Options group sub-lines.
4. **Filter chips** use an inverted ink fill when pressed. That is a third selection look, for multi-select filters, and it should be decided deliberately.
5. **Text glyphs:** three "×" remove buttons (Compare, Scan, Milo history) and five "→" in copy remain.
6. **Unused code:** the tall dossier header code path still exists but no caller uses it.
7. **The light theme** was not re-screenshotted in this pass. Its ink-3 was deepened, but nothing else was checked.
8. **Classic is untouched.** It still has its own sizes, gold buttons and pills.
9. **Gold declarations in the CSS** still number about 120, most of them chart encodings and focus rings. The on-screen count above is the measure that matters.
10. **Home's starter cards** label "Follow" in gold, which is outside the list of gold uses. This was found by the optic-frontend skill's test run, and the label should be ink.
