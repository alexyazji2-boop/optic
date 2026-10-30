# The Dossier Overview's pipeline (post-demo Phase 06, directive 06 section 1)

How a ticker becomes the Overview page, step by step. For each step: where in the code it happens, and where stale or
wrong information could enter, with what now guards against it. "Rendered" means checked in headless Chrome
(`tools/phase06_checks.py`, `tools/phase06_accuracy.py`); "Source" means read from the code.

## 1. Symbol selection

- The address is `#/SYM`. `core/router.js` `parse` reads the symbol, upper-cases it and accepts only
  `[A-Z0-9.^=-]{1,12}`; anything else is a Not found page.
- The search (`ui/palette.js`, `core/resolve.js`, Phase 03) resolves typed text to a symbol before it changes the
  address. The shell (`app.js` `show`) gives each navigation a fresh page element and disposes of the last page.
- **Where it went wrong:** the shell focuses the new page's heading one frame after it arrives. A search opened
  inside that frame lost its focus, and the next Enter did nothing: 3 of 40 searches in a row (BUG-093, rendered).
  The heading now waits while the search or a drawer is open.

## 2. Data requests

`pages/dossier.js` `render` asks for eleven payloads at once, each a free read:

| Payload | Endpoint | Client cache |
|---|---|---|
| Quote | `/api/quote/SYM` | 20 s |
| Session | `/api/session/SYM` | 60 s |
| Prices, financials, news, signals | `/api/ticker/SYM?max_expiries=4&macro=true` | 2 min |
| Research grades | `/api/framework/SYM?mode=combined` | 5 min |
| Fair value | `/api/fair-value/SYM` | 10 min |
| Long-term model | `/api/longterm/SYM?indices=false` | 10 min |
| Earnings | `/api/earnings/SYM` | 10 min |
| Digest | `/api/digest/SYM` | 5 min |
| Segments | `/api/segments/SYM` | 10 min |
| Chart marks | `/api/extras/SYM?benchmark=SPY` | 10 min |
| Weinstein stage | `/api/stage?symbol=SYM` | 30 min |

The header's price is asked again every 20 seconds through the trading day (4:00 to 20:00 New York) and every 5 minutes
outside it (`dossier-frame.js` `livePrice`, `core/poll.js`). A signed-in reader's thesis check reads `/api/theses`.

**Where it went wrong:** each answer was checked against the symbol only, so an answer from an earlier visit to the
same ticker could land in a later visit (BUG-095, Source). The event handlers were also added again on Try again, so one press
of the switch swapped the view twice, back to where it was (BUG-094, rendered).

**What guards it now:**
- Every response is tied to the visit that asked for it (`VISIT`, `mine()`), including the stage's retry and the
  track record's late load.
- The handlers are wired once per page element.

Rendered checks D6 to D8, D10 and D15 release held answers after the page has moved on; none of them is drawn.

## 3. Normalisation

- **On the server:** the payloads come from Yahoo Finance, with Tradier where configured, SEC filings and Optic's own
  models.
- **On the client:**
  - `fresher()` merges two quotes by their trade time, so an older one never overwrites a newer.
  - `overview-research.js` reads the payloads by fixed rules: `priceRead`, `businessRead`, `valuationRead`,
    `factors`, `earningsNext`.
  - `overview-simple.js` `simpleFacts` gathers the Simple Analysis's facts from those same readings, so its year's
    change is the chart's.

**Where stale or wrong data can enter:**
- **Quote delay:** the quote's stated delay can disagree with the data caveat. SPY's `delayed_minutes` is 0 while
  `/api/ticker`'s caveat says about 15 minutes (BUG-098, for Phase 09). The page repeats the quote's own statement
  and invents none.
- **Annual figures:** they can be months old. The Simple Analysis says which fiscal year they are from.
- **Report times:** a future report's time of day on the feed is a placeholder, so no time is said for one
  (`core/reports.js`).
- **Forward P/E:** a negative forward P/E (a loss expected) is not shown as a multiple.

## 4. AI generation and prompt templates

- **Nothing on the Overview is written by a model.** Every sentence is a fixed rule over the payloads; the same data
  gives the same words.
- **Ask Milo entries:** they only draft a question, and nothing is sent until the reader presses Send. Milo's answer
  then uses the reader's knowledge level through `app/knowledge.py` `prompt_for` and the advice policy
  (`app/ai_policy.py`).
- **No paid call on load:** the toggle and the level change fetch nothing (rendered check D1: no request on a swap).

## 5. Caching

- **Client:** `core/api.js` keeps each answer for the time in the table above and shares one request in flight per
  address. A return visit within those times is drawn from cache (rendered check D11: no request on return).
- **Server:** each endpoint has caches of its own. A research read built before the latest close is marked stale
  (`framework.freshness.state`), and the page then shows a stale line.
- **Where staleness can enter:** after a return visit the figures can be up to their cache time old. Each section
  says how fresh its figures are, and the Simple Analysis repeats the quote's last trade.

## 6. Loading states

- **Simple Analysis:** it waits for the four payloads it reads (`/api/ticker`, `/api/session`, `/api/longterm`,
  `/api/earnings`) and shows one loading line until then, so no sentence says "no history" for a history that is
  still arriving.
- **Fallbacks:** each of the four has a fallback when it fails. The session read had none, which would have left the
  new Simple Analysis waiting, so a failed session read now falls back to no session (Source).
- **Advanced Analysis:** its sections show their own loading states as their payloads arrive (rendered check D9:
  one loading line in the Simple view, either view while loading).

## 7. Rendering

- **Redraws:** `paint` redraws the page on every arrival. It keeps open folds, the scroll position, and focus on the
  button, a range, or the heading; a focused heading used to be lost to the body on every redraw (BUG-097).
- **Section helpers:** `ui/sections.js` adds folding, the jump strip and Panels, and `ui/glossmark.js` marks terms
  by the reader's level.
- **The header's price refresh** updates the header's price alone. The Simple Analysis, which says the same day's
  move, is redrawn in place when the quote it was written from has moved on (BUG-096, rendered check D16).

## 8. Analysis mode state

One state, the density setting (`core/prefs.js` `density`, `optic.mode.v1`, D-019):
- **Simple** draws the Simple Analysis and **Advanced** draws the Advanced Analysis, in one area (`#ov-analysis`),
  never both.
- **The button** ("Show advanced analysis" or "Show simple analysis") sets the state. Settings' "How much each page
  shows" sets the same one.
- **The data** (`D`, per visit) is separate from the view, so a swap redraws from what is already loaded.

Before Phase 06 the switch opened folds under the simple content (BUG-001), and four names pointed at one key
(BUG-068).

## 9. Error handling

- **Quote:** a symbol with no quote and no history is a no-listing page. A source that does not answer is said as
  that, not as an unknown symbol.
- **Price history:** a failed history shows the chart's error with Try again, and the Simple Analysis says the figures
  did not load and points to it.
- **Other sections:** each says its own failure in place (rendered check D10: a failing `/api/ticker`, then Try
  again, then one press swaps once).

## 10. Source attribution

- **The chart:** it names its source and last close ("Daily closes, split-adjusted, through Oct 29, 2026. Source:
  Yahoo Finance").
- **The Simple Analysis:** it says the quote's delay and last trade, and the fiscal year its business figures come
  from.
- **The Advanced Analysis:** it ends with How this page is built, and every grade and score carries its method and
  its limits.
- **Rendered:** `tools/phase06_accuracy.py` checks the stated source and last date against the payloads for ten
  symbols.
