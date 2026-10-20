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

### Explanations
- **Visible:** a section shows its finding and one useful line.
- **Folded:** methods, formulas, conventions and caveats go behind one shared fold, "How this works" (`ui/states.js` `how()`), under those words everywhere.
- **Where it's applied:** the Options contracts table and the dealer gamma panel. The table's report-inside-the-expiry note stays in view, because it is a finding.

### Headers
Every dossier tab uses the Chart page's one-line header (`dossier-frame.js` `header()` now defaults to `bar`):
- the ticker and name;
- the price and the day's move;
- the extended-hours price;
- Alert, Compare, Watch and Ask about at the right.

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
