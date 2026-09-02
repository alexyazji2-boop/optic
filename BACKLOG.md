# Optic Terminal — TrendSpider feature backlog

Captured from a batch of screenshots. Grouped by what they actually are rather
than the order they arrived, because most of them are one build.

Status key: **done** · **ready** (buildable now, no blockers) · **needs a key**
(your account, I can't create it) · **needs a host** (blocked on deploying)

---

## Done

| # | Feature | Notes |
|---|---------|-------|
| 1 | Ticker logos in search | Ticker-keyed cascade (parqet → FMP), monogram underneath. No extra request per keystroke. |
| 2 | Sector rotation (RRG) | Curved Catmull-Rom tails, smoothed, four quadrants. Macro tab. |
| 3 | Seasonality module | `/api/seasonality/{ticker}` + Swing panel + dock widget. |
| 4 | Shared chart style model | Per-overlay colour / thickness / params, stored as palette tokens. Swing and Charting both read it, so they cannot drift. |
| 5 | Charting tab | First tab, full-height chart (743px vs Swing's 420px), measured from the layout. |
| 6 | Top toolbar | Fibs · Trends · Indicators · Volume · Events, each a dropdown with colour swatches. Plus interval, range, candle/line. |
| 7 | Overlay legend | Over the chart's top-left, live values, hide and remove per row. |
| 8 | Chart lag | Fixed: 20–26ms per interaction, was an erratic 16–1370ms. |

---

## The Chart workspace — six screenshots, one build

This is the big one. Ordered as I'd build it, because each layer feeds the next.

| # | Layer | Effort | Notes |
|---|-------|--------|-------|
| 4 | ~~**Chart state model**~~ **DONE** | M | Per-indicator config: colour, thickness, length, offset, price source. Everything below reads from this. Build first or the rest gets rewritten. |
| 4b | ~~**Top toolbar**~~ **DONE** | S | The circled row: `MTFA · Fibs · Trends · Indicators · Candle Patterns · Chart Patterns · Heatmap · Other · Alerts&Bots`. This is the organising element for everything else — each button opens its own dropdown. **Most of these already exist in Optic**, just scattered across the Swing tab. |
| 5 | ~~**Tab + full-height chart**~~ **DONE** | M | New top-level tab, separate from Analysis. Candles + volume, sized to the viewport instead of a fixed 340px. |
| 6 | ~~**Overlay legend**~~ **DONE** | S | `SMA (50, 0, close) 753.96` top-left, click to hide, × to remove. Reads the state model. |
| 7 | **Indicator manager dialog** | M | Searchable list, per-indicator colour swatch / thickness / params. The "Manage Indicators" screenshot. |
| 8 | ~~**Fib restyle**~~ **DONE** — plain labelled lines | S | Plain lines + `0.618 (748.30)` labels. **Reverses an earlier instruction** — see note below. |
| 9 | ~~**Auto trend lines**~~ **DONE** — pivot-fitted, relevance-filtered | M | Pivot-derived support/resistance trendlines, bull/bear coloured, toggled from a Trends button. Optic already has `find_pivots`. |
| 10 | ~~**Drawing engine**~~ **DONE** — 9 tools, undo/redo, per-symbol persistence | **L** | Hit-testing, selection handles, drag, snap, persistence, undo. ~20 tools in that rail. I'd ship 6 that feel right before 20 that don't: trendline, ray, horizontal, rectangle, fib, text. |
| 11 | ~~**Dockable widgets**~~ **DONE** — 14 widgets + icon rail | M | Right-hand column: seasonality, analyst estimates, watchlist, scanner results. Collapsible, closable, add/remove. |
| 11b | ~~**Per-indicator styling**~~ **DONE** | M | The "Manage Indicators" dialog: colour swatch, line thickness, length, offset, price source, per indicator. Searchable list on the left, stacked settings cards on the right. Depends on #4. |

---

## Pulse

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 19 | ~~Response formatting~~ **DONE** — sections, key-levels table, Bottom line, follow-ups | done | Structured output: section headers, bold figures, a key-levels table, a Bottom Line, and clickable follow-up suggestions at the end. This is a system-prompt change, so it is cheap. |
| 20 | ~~Starter prompt cards~~ **DONE** — 12 cards, symbol-aware | done | Empty-state cards. Must reflect what Pulse can actually do — no "send me an email" examples until alerts exist. |
| 21 | Pulse has no credit | **blocked** | Every call currently returns "out of credit or hit its spend limit". Both items above are untestable until that is topped up. |

---

## Standalone panels

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 12 | ~~Forex — all pairs, searchable~~ **DONE** — 15 pairs, 5 drivers | done | Each pair with its macroeconomic read (carry, terms of trade, risk proxy). Macro tab currently has 3 FX symbols; this widens it and explains them. |
| 13 | Pulse starter prompts | **ready** | Cards on the empty state. Must reflect what Pulse can actually do — no alerts/email examples. |
| 14 | ~~Stock Maps~~ **DONE** — squarified treemap + bubble, 8 templates | done | Treemap + bubble chart over a screen. Templates like "P/E outliers in Energy". Uses `sec_facts` + `screen.py`. Genuinely good for research. |

---

## Other data types

From the "display other types of data" screenshot.

Built: dividends, splits, analyst estimates, relative performance, market
breadth, short volume (FINRA), crypto fear & greed, fundamentals. **Not built:**
dark pool and retail activity %, which have no free source.

| Data | Status | Source |
|------|--------|--------|
| Dividends | **ready** | yfinance |
| Splits | **ready** | yfinance (already used in `pe_history`) |
| Analyst estimates | **ready** | already in the app, needs surfacing on the chart |
| Relative performance | **ready** | trivial vs any benchmark |
| Market breadth | **ready** | already computed on Macro |
| Federal Reserve (FRED) | **ready** | FRED API, free, needs a free key |
| Fundamentals | **ready** | `sec_facts` already does this |
| Short volume (FINRA Reg SHO) | **ready** | FINRA publishes daily files, free |
| Crypto Fear & Greed | **ready** | alternative.me, free |
| **Dark pool volume** | **needs a key** | No free source. Paid vendor only. |
| **Retail traders activity %** | **needs a key** | Paid vendor only. |

---

## Alerts

| # | Piece | Status |
|---|-------|--------|
| 15 | Rules engine + in-app inbox | **ready** — zero setup, works today |
| 16 | Email delivery | **needs a key** — SMTP app password or Resend/Postmark key, in `.env` like `TRADIER_ACCESS_TOKEN`. I never see it. |
| 17 | Text delivery | **needs a key** — Twilio, paid per message, verified number. I can't create accounts or enter payment details. |
| 18 | Any of it being trustworthy | **needs a host** |

**On 18:** alerts that only fire while the laptop is awake and the tunnel is up
are worse than no alerts, because you'd rely on them. The tunnel died twice
today and mints a new hostname on every restart. This is the third feature
today that deploying gates — the others were the public link and ITMatrix.
Render is excluded per your earlier instruction; Fly.io fits (the Dockerfile
already exists) and gives a hostname that stops changing.

---

## Declined, with reasons

| Feature | Why |
|---------|-----|
| ITMatrix gamma | $89–150/mo paid product. Won't scrape it. Optic already computes GEX; what ITMatrix adds is replay, 3D surface, dark pool, index options. |
| ML Lab / predictive models | 10y of daily bars with user-chosen inputs and no holdout protocol is an overfitting machine. Your own 30-config sweep killed the momentum filter for exactly this reason. |
| Custom JavaScript studies | Arbitrary code execution in an app deliberately left open and unauthenticated. |
| 200+ indicators | The Swing tab already needs 124 glossary definitions. A marketing number, not a research improvement. |

---

## Flagged contradiction

On the fib styling: earlier the instruction was *"don't use only dashed lines to
represent them, make it creative"*, which is why fibs became filled bands with
spaced labels. The new screenshot is the opposite — thin plain lines, one label
each, "EXACTLY this, simple".

I'll follow the newer one. Noting it because the same argument applies to the
S/R bands and supply-demand zones from that pass, and they should probably be
flattened too for consistency. Say if so.


---

## Also added along the way (not on the original list)

| Feature | Notes |
|---------|-------|
| Pulse personalities | Six response lenses. Changes which figures the answer leads with, never the figures. |
| Session dividers | Vertical lines where the trading day changes, with a toggle. Intraday only. |
| Undo / redo | Snapshot stack over the drawing list, ⌘Z / ⇧⌘Z. |
| Chart coordinate frame | `lineChart` now exposes its scales, so any overlay can convert pixels to (bar, price). |
| Bubble chart | New chart type. Area proportional to the measure, not radius. |
| Sloped segments | `lineChart` can draw trend lines and any two-point drawing, not just horizontals. |
