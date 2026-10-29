# Registry B: Home, Markets, Discover, Compare (v2 front end)

Priority scale: P0 (blocks launch or is unsafe), P1 (fix before the owner's next release), P2 (fix in the next pass); "P2 (low)" marks a P2 that is cosmetic or wording-only.

Evidence label: **Source** only. Everything below was read from code in `~/Optic/wt-ultra` (branch
`post-demo-ultra`, HEAD `fce3e71`; `static/` and `app/` are identical to `9fa0f36`, checked with
`git diff --stat 9fa0f36 HEAD -- static app`, which printed nothing). Nothing was rendered, no server was started and
no request was made. Where a statement is about what shows at a given width it cites the CSS rule that gates it
(`static/v2/css/pages.css`), not a screenshot.

Citation form: `file:line`. Front-end files are under `static/v2/js/` and named bare when the name is unique
(`workspace.js`, `read.js`); others carry their folder (`ui/states.js`, `core/legal.js`, `app.js`). Server lines are
`app/main.py:NNNN` unless another file is named. "Spend" means a call to the Anthropic API.

## 0. Scope map

| Route | View id (`core/router.js`) | Module(s) | Reached from |
|---|---|---|---|
| `#/` (old `#/workspace` lands here, `router.js:13`) | `home` | `pages/workspace.js` (the page) with blocks imported from `pages/home.js` | rail Home, phone bar Home (`nav.js:18,64`) |
| `#/read` | `brief` | `pages/read.js`, `ui/grouptabs.js` | Markets tabs `pages/tabs.js:29-33`, `nav.js:29-33` |
| `#/macro` | `market` | `pages/macro.js`, `pages/market-shared.js`, `ui/grouptabs.js` | Markets tabs |
| `#/indices` | `indices` | `pages/indices.js`, `pages/market-shared.js` | Markets tabs |
| `#/instrument/<SYM>` | `instrument` | `pages/instrument.js`, `ui/pricechart.js` | Home indices strip, Macro rows, Read hero, Indices table; no tab of its own (`nav.js:72` files it under Markets) |
| `#/earnings`, `#/earnings?week=-1\|0\|1` | `earningsweek` | `pages/earningsweek.js` | Home Earnings panel link (`workspace.js:452`); `router.js:15` |
| `#/explore` | `explore` | `pages/explore.js` | Discover tabs |
| `#/scan`, `?id=<scan>`, `?mode=build\|shortlist`, `?q=<words>` | `scan` | `pages/scan.js`, `pages/scan-shortlist.js` | Discover tabs; Explore cards; Milo "Find stocks" card |
| `#/insiders`, `?symbol=`, `?view=house\|insiders\|contracts` | `insiders` | `pages/insiders.js`, `core/congress.js` | Discover tabs |
| `#/analysts` | `analysts` | `pages/analysts.js`, `ui/table.js`, `ui/typeahead.js` | Discover tabs |
| `#/compare`, `#/compare?t=A,B[,C,D]` | `compare` | `pages/compare.js`, `ui/bars.js`, `ui/score.js` | rail Compare; ticker menu (`ui/company.js:6`); Scan "Compare the first N" (`scan.js:85`) |

Not part of this section, with the reason:

- `pages/signals.js` is the signal history on **Alerts** (`alerts.js:3,26`); none of the routes above imports it.
- `pages/home.js` also defines a complete older Home page (`render`, `dispose`, `onLists`, `retry`, `loadHome`, `welcome`,
  `starters`, `modes`, `scene`, `strip`, `movers`, `desk`, `wireForms`: `home.js:499-728` and the blocks above it), but
  `app.js:60` maps `home` to `pages/workspace.js`, so that page is not reachable (risk X-2).
- `ui/sections.js` (fold, jump strip, Panels chooser) is **not called by any page in this section**; its callers are
  `dossier.js:387`, `financials.js:406`, `options.js:427`, `investing.js:307`, `earnings.js:237`, `tracker.js:320`.
- `ui/grouptabs.js` is used by Read (`read.js:297`) and Macro (`macro.js:233`) only.
- `ui/strips.js` is global (`app.js:340`): it adds scroll arrows, wheel and mouse-drag to `.tabs, .tabset, .mstrip, .drail,
  .bk-tabs, .chw-rail, .ch-draw, .ws-presets, .chips-scroll, .sec-list, .cs-strip, .palette-filters` (`strips.js:18`). On
  Home that covers the layout tabs (`.ws-presets`) and the week strip in What matters today (`.cs-strip`); the arrows are
  `aria-hidden`, `tabindex=-1` mouse conveniences (`strips.js:27-28`).
- `core/market-questions.js` feeds only Home's "Questions worth asking" panel (`workspace.js:316`).

### Shared behaviour used by every route here

- **Retry** (`app.js:280-283`): a `data-v2-retry="<key>"` button calls `page.retry[key](view, route)`, or re-shows the route
  when the page has no such key.
- **Ask Milo buttons** (`ui/milo.js:320-322`, handled `app.js:242-246`) open the panel with the question **drafted**; nothing is
  sent (`openMilo` has `send=false`, `milo.js:1042`). They also send the figures of the block they sit in
  (`panelFigures`, `milo.js:66-80`). Starter questions inside the open Milo panel do send on press (`milo.js:269-272,1260`):
  that belongs to the Milo section.
- **Typeahead** (`ui/typeahead.js`) is attached by `app.js:338` to any input marked `data-v2-ta`: `/api/search?q=&limit=10`
  after 160 ms, ArrowUp/Down move, Enter takes the highlighted row or, with none, the one company whose name was typed
  (`typedNamePick`, `typeahead.js:18-26`), Escape closes. Marked inputs in this section: Home's linked-ticker box
  (`workspace.js:745`), Analysts (`analysts.js:45`), Compare (`compare.js:154`). No other box in this section has it.
- **Glossary marks** (`ui/glossmark.js`, started `app.js:339`): the first mention of a defined term in each section becomes a
  button that opens its definition; never inside links, buttons, tables' controls, tabs, menus, charts, `.tick` or the
  Milo panel (`glossmark.js:22-25`); Professional level marks nothing (`glossmark.js:32`). Explicit marks in this section:
  `term('ticker')`, `term('watchlist')` (`workspace.js:812,816`), `term('risk-on','risk')` (`workspace.js:367`).
- **Per-page legal notice** (`core/legal.js:36-41`, placed by `app.js:163-177`): only these views carry one: `market`
  (Macro), `indices`, `brief` (Read), plus `swing`, `long`, `roth`, `earnings`, `tracker`, `paper` elsewhere. **Home, Explore,
  Scan, Insiders, Analysts, Compare, Instrument and Earnings-week have none** (risk X-1). Every page has the shell footer
  line "Not financial advice. ..." (`ui/shell.js:85`, `core/legal.js:34`).
- **Fetch cache** (`core/api.js:89-107`): `get` returns a cached copy inside `ttl`, a stale copy at once (refreshing behind it,
  no callback) after it, and dedupes concurrent identical requests. It has no abort for superseded requests; pages that
  guard against late answers do it with their own counters (noted per page).

## 1. Can merely opening a page spend money? (server side, for each endpoint these pages call)

Seven server routes called from this section can reach `ai.*`: `/api/home` (the Desk), `/api/brief` (the Read), `/api/catalyst-mode`,
`/api/weekly`, `/api/sectors/{symbol}/read`, `/api/screener/ask`, and `/api/catalysts/refresh` (only when `CATALYST_READER=model`).
`app/ai.py` is imported only by `main.py`, `brief.py`, `catalysts.py`, `live_mirror.py` and `metrics.py` (grep), and none of
`analysts.py`, `insiders.py`, `contracts.py`, `priority.py`, `earnings_week.py`, `shortlist.py`, `briefing.py` or
`analytics/compare.py` imports it.

| Route | On open, with no press | On a press | Bound and evidence |
|---|---|---|---|
| `#/` Home | **Yes, indirectly.** Six panels call `GET /api/home` (`workspace.js:290,315,330,343,357,380`); its `morning_desk` leg calls `_desk_prose` (`main.py:2907,3164,3201`). The first request of an Eastern day with an enabled key writes the Desk with one model call (`main.py:2969-2983`, `ai.write_morning_desk`); when the tape has moved past the written note, a background rewrite starts (`main.py:3205-3210`, `_rewrite_desk_soon` 3015-3028). No sign-in needed. | Ask Milo buttons only draft. | Writes are claimed on disk: `DESK_MAX_ATTEMPTS = 2` per day, retry after one hour (`main.py:2951-2952`); rewrites at most one per `DESK_REWRITE_MINUTES` (30) and `DESK_REWRITES_PER_DAY` (12) (`main.py:3011-3012`); the code's own estimate is "about six cents" a rewrite (`main.py:3010`). No per-visitor guard. |
| `#/explore` | **Yes, same leg**: `explore.js:104` calls `/api/home`. | none | as above |
| `#/read` | **No.** `/api/brief?cached=true` "never build or write" (`main.py:3413-3421`, `brief.py:1060-1090`); `/api/desk/edition` "never writes" (`main.py:3382-3386`); `/api/catalyst-mode?cached=true` and `/api/weekly?cached=true` serve only kept pieces (`main.py:4883-4900,4640-4670`). | "Build today's Read" / "Update it now" calls plain `GET /api/brief` (`read.js:57`) which can build and write the Read (`brief.py:944-962`, claim `READ_MAX_ATTEMPTS = 3`, 1 h retry, `brief.py:90-91`). "Write the read" calls `/api/catalyst-mode` (`read.js:347`; `ai.OPEN_WRITE_LIMITS["catalyst_read"]` 24 a day, `ai.py:1764-1768`; cached 1 h). "Write this week's update" calls `/api/weekly` (`read.js:352`; once per ISO week, kept in `weekly_store`). "Scan for new catalysts" POSTs `/api/catalysts/refresh` (`read.js:357`; spends only if `CATALYST_READER=model`, default `rules`: `catalysts.py:104,766-772`). | Each is a labelled button. The Read build says the cost before the press (`read.js:46`). |
| `#/macro`, `#/indices` | **No.** | A "Sector Read" / "Index Read" row button calls `GET /api/sectors/{sym}/read` (`ms:33`, `macro.js:286`, `indices.js:60`), a paid write (`main.py:4581-4610`, `ai.write_sector_read`). | Capped at `SECTOR_READS_PER_DAY` = 30 across all visitors, cached 1 h per symbol (`ai.py:1764-1768,2160-2200`); anonymous visitors may press. |
| `#/scan` | **No on a plain open.** **Yes for an account's allowance** when the address carries `?q=`: `scan.js:236-238` runs the request on load. | "Find symbols now", an example chip or a recent request calls `POST /api/screener/ask` (`scan.js:218`). The fixed parser reads most requests free; leftover words go to Milo through `_spend_guard` (`main.py:6537-6566`), kept per phrase (`ai_store.kept("scan", key)`). | `GUEST_AI_CALLS_PER_DAY` defaults to 0 (`main.py:7375`), so a guest is refused and told so (`main.py:6547-6550`); an account spends one Milo message. |
| `#/instrument`, `#/earnings`, `#/insiders`, `#/analysts`, `#/compare` | **No.** | none | `/api/instrument`, `/api/earnings-week`, `/api/insiders/latest`, `/api/congress`, `/api/contracts`, `/api/analysts/*`, `/api/compare` import no AI module; `compare.take` is "Derived, not written. No model call" (`app/analytics/compare.py:474-476`). |

Heavy but not paid: `/api/priority` and `/api/earnings-week` scan about 150 companies cold ("earnings 66.6s", `main.py:5217-5224`);
Home asks for both on every open (`workspace.js:282,438`), served from the last build with a background rebuild
(`main.py:5215-5262,5292-5322`).

### 1.1 Endpoint index (every API path these pages call, with its handler and whether it can reach Anthropic)

| Endpoint | Handler | Called by | Can reach Anthropic? |
|---|---|---|---|
| `GET /api/home` | `main.py:2865` | Home (indices, regime, expected, desk, questions, alerts), Explore | **Yes**: `_morning_desk` -> `_desk_prose` / `_rewrite_desk_soon` (`main.py:3164,3201,3210`) |
| `GET /api/brief` (`?cached=true`) | `main.py:3413` | Read, Home calendar and news (cached) | Only without `cached`: `brief_mod.state` can build and write the Read (`brief.py:944-962,1060`); the Read page asks plain only on its build button |
| `GET /api/brief/search` | `main.py:3424` | Read | no |
| `GET /api/desk/edition` | `main.py:3382` | Read | no ("never writes") |
| `GET /api/catalyst-mode` | `main.py:4883` | Read | Only without `cached`: `ai.write_catalyst_read` (`main.py:4895`) |
| `GET /api/weekly` | `main.py:4640` | Read | Only without `cached`: `ai.write_weekly_update` (`main.py:4699`) |
| `GET /api/catalysts`, `POST /api/catalysts/refresh` | `main.py:4792`, `4837` | Read | refresh only when `CATALYST_READER=model` (`catalysts.py:104,772`) |
| `GET /api/validation` | `main.py:2181` | Read (Market regime history line) | no |
| `GET /api/priority` | `main.py:5215` | Home priority, Read | no |
| `GET /api/sentiment` | `main.py:4613` | Home regime, Read | no |
| `GET /api/market` | `main.py:1719` | Home sectors, Macro | no |
| `GET /api/rotation`, `/api/stockmap`, `/api/forex`, `/api/implied-correlation`, `/api/dispersion` | `main.py:6020`, `5640`, `5630`, `4954`, `4943` | Macro | no |
| `GET /api/sectors/board`, `/api/indices/board`, `/api/trends/board` | `main.py:4545`, `4555`, `4565` | Macro, Explore; Indices; Home trends | no |
| `GET /api/sectors/{symbol}/read` | `main.py:4581` | Macro, Indices (press) | **Yes**: `ai.write_sector_read` (`main.py:4595`), 30 a day, 1 h cache |
| `GET /api/indices` | `main.py:1801` | Indices | no |
| `GET /api/instrument` | `main.py:6232` | Instrument; the legacy Home chart | no |
| `GET /api/earnings-week` | `main.py:5335` | Home earnings, `#/earnings` | no |
| `GET /api/earnings/{ticker}` | `main.py:1174` | Home Earnings (linked) and implied-move Load | no (the brief writer is `POST .../brief`, not used here) |
| `GET /api/scanners`, `/api/scanners/groups`, `/api/scanners/{id}` | `main.py:6442`, `6424`, `6649` | Explore, Scan, Home movers (`movers`) | no |
| `GET /api/screener/fields`, `POST /api/screener` | `main.py:6600`, `6611` | Scan | no |
| `POST /api/screener/ask` | `main.py:6517` | Scan | **Conditionally**: leftover words go to `ai.read_scan_request` after `_spend_guard` (`main.py:6547-6552`) |
| `GET /api/shortlist`, `GET /api/evaluate` | `main.py:2478`, `4910` | Scan | no |
| `GET /api/congress`, `/api/insiders/latest`, `/api/contracts` | `main.py:4721`, `6472`, `2775` | Insiders | no |
| `GET /api/analysts/latest`, `/api/analysts/{ticker}` | `main.py:6489`, `6501` | Analysts | no |
| `GET /api/compare` | `main.py:5360` | Compare | no |
| `POST /api/briefing` | `main.py:2035` | Home changes | no |
| `GET /api/watchlist` | `main.py:2837` | Home watch | no |
| `GET /api/quote/{t}`, `/api/take-chart/{t}`, `/api/news/{t}`, `/api/ticker/{t}`, `/api/fair-value/{t}`, `/api/framework/{t}`, `/api/options/{t}/research` | `main.py:1144`, `5612`, `3370`, `1086`, `5423`, `1205`, `1516` | Home linked panels | no |
| `GET /api/econ`, `/api/econ/{code}` | `main.py:5983`, `5989` | Home economy, Macro | no |
| `GET /api/brokerage/status`, `.../workspace/overview`, `.../workspace/performance` | `app/brokerage/routes.py:90`; `app/brokerage/workspace_routes.py:65,90` | Home portfolio | no |
| `GET /api/search` | `main.py:1875` | typeahead boxes (Home linked ticker, Analysts, Compare) | no |
| `GET /api/knowledge/modes` | `main.py:7572` | not called by the routed Home | no |

---

## 2. Home — `#/`

- Files: `pages/workspace.js` (1,192 lines; the page), `pages/home.js` (blocks: `portfolio`, `eventsBlock`, `catalystStrip`, `deskBody`,
  `changesBlock`, `trendsBlock`, `evPress`, `briefingHoldings`, `hello`, `etDate`, `STARTERS`, `STARTER_NAMES`, `STARTER_ABOUT`),
  `core/market-questions.js`, `core/homelink.js`, `core/poll.js`, `core/status.js` (`marketSession`), `core/instrument.js`
  (`kindOf`, `learn`), `core/finviz.js` (`MISSING`), `pages/options-panels.js` (`row30`, `skewWords`), `ui/chart.js`
  (`lineChart`, `spark`, `meter`, `mountCharts`), `ui/term.js`, `ui/score.js`, `ui/states.js`, `ui/strips.js`.
- Purpose: a customisable grid of 27 kinds of panel (market conditions, the linked company's data, the reader's own lists),
  chosen by one of four layouts, with Market Overview open by default.
- Auth: guest works fully (lists in this browser). Signed in: the `watch` and `changes` panels use the account's lists
  (`store.activeList`, `store.allSymbols`), the server adds the account's own watch names to the briefing
  (`main.py:2054`), the Your-portfolio panel appears once a brokerage is linked (`workspace.js:268-272`; the server can
  restrict this to the owner, `app/brokerage/routes.py:90-92`), and the onboarding text drops "Kept in this browser until
  you sign in" (`workspace.js:816`). Owner: nothing differs on this page.

### 2.1 Sections in render order (`paintAll`, `workspace.js:839-851`)

| # | Section | What it shows | Source | Default |
|---|---|---|---|---|
| 1 | Page head | `h1` greeting (`hello()`, `home.js:43-48`: Good morning/afternoon/evening, plus first name when signed in) and a date line `etDate(session.now_et)` + session label | the Indices panel's `/api/home` answer (`workspace.js:841,843,893`); with no Indices panel in the layout, today's date from the clock and no session label | always |
| 2 | First-visit band | "New to Optic? Three ways to start" (section 2.4) | local | shown only while `isNew() && !onboarded()` (`workspace.js:801,845`) |
| 3 | Layout bar | four layout tabs (select under 640 px), Customize | local | always |
| 4 | Edit bar | Add panel, Save as My Desk, ⋯ Reset | local | only while Customize is on (`workspace.js:730`) |
| 5 | Grid | the layout's panels in saved order, with the linked-ticker row placed immediately above the first linked panel (`workspace.js:847`); text "Every panel is hidden. Use Add panel, or Reset." when none | per panel | desktop: every panel open (folding exists only at 860 px and under, `workspace.js:59`; `.ws-tbtn` is `display:none` otherwise, `pages.css:1599`); phone: only the layout's `ESSENTIAL` panels open, the rest show their one-line blurb (`workspace.js:56,126-135,788`) |

Layouts (`PRESETS`, `workspace.js:41-52`; panel, grid columns of 12, height s/m/l):

| Layout (`data-ws-preset`) | Panels in order | Phone-open (`ESSENTIAL`, `:56`) |
|---|---|---|
| `market` Market Overview (default, `:166`) | indices 12m, regime 4m, expected 4m, sectors 4m, quote 8m, watch 4s, calendar 6s, earnings 6s, priority 6m, news 6s, desk 6m, movers 6s, portfolio 12m (13) | indices, regime, quote, watch |
| `options` Options Research | quote 8m, watch 4s, contracts 12l, vol 6m, gex 6m, tearn 6m, cnews 6s (7) | quote, contracts, vol |
| `longterm` Long-Term Investing | quote 8m, watch 4s, biz 6m, value 6m, fin 6m, own 6m, cnews 12s, portfolio 12m (8) | quote, biz, value |
| `mine` My Desk | the reader's own; a copy of Market Overview until changed (`:51,1029`) | indices, regime, quote, watch |

Five panels are in no layout and only reachable through Customize > Add panel: `changes`, `questions`, `trends`, `alerts`,
`economy`. A panel a later version adds is appended hidden to a saved layout (`workspace.js:186`).

### 2.2 The linked ticker and the "Follows <TICKER>" chip (traced from code)

**Chosen.** (1) Start: `load()` reads `link` from `optic.v2.workspace.v1`; if it is empty it is the first symbol of the open
watchlist, else the most recent company opened (`store.recent()[0]`), else `SPY` (`workspace.js:170,189`). (2) Change by
`setLink(sym)` (`workspace.js:931-948`), which upper-cases, strips a leading `$`, requires `/^[A-Z0-9.^=-]{1,12}$/`, returns
silently when invalid or unchanged (`:933`), then saves, pushes the symbol onto Recent (`store.pushRecent`), re-presses every
`data-ws-pick` button, redraws every linked panel's chip, updates the box, reloads every unpinned linked panel that is not
folded (`:943-944`), says "Linked panels now follow X." (`:946`) and refreshes Milo's context (`:947`). It is called from:
the linked-ticker form (`:1110`), any `data-ws-pick` press (`:1030`: the Watchlist, Earnings and Movers tables' ticker buttons,
the recent chips, each Sector heatmap tile, "Link AAPL/MSFT/NVDA" in a fund's Business/Financials/Ownership panel), and the
`v2:homelink` window event (`:1165`) raised by "Show on Home" in a Dossier header menu or a company drawer (`ui/company.js:8`,
`app.js:248-253`, `core/homelink.js:6-17`); when Home is not mounted `linkHome` writes `link` straight into the saved
workspace for the next visit.

**Stored.** `optic.v2.workspace.v1`: `{v:5, preset, layouts, custom, locked, link, fold, settings}` (`workspace.js:34-35,191-195`);
a pin is `settings.<panel>.pin` (`KEEP`/`keepOf`, `:160-162`). It is a setting, not a personal key (`workspace.js:4`), so
`core/device.js` does not shelve it on a sign-in change (it is absent from `PERSONAL_KEYS`, `device.js:17-46`).

**Followed.** Ten panels have `linked: true`: `quote`, `cnews`, `contracts`, `value`, `vol`, `gex`, `tearn`, `biz`, `fin`,
`own`. The other 17 are about the market or the reader's lists and never follow it. In Market Overview only `quote` is linked.

**The chip.** `linkChip(id)` (`workspace.js:754-759`) is a button `data-ws-pin` reading **"Follows <S.link>"**, title "Follows X, the
ticker chosen above these panels. Press to keep X here when the link changes."; once pressed it reads **"Kept on <T>"**
(`.is-kept`, "it does not follow the linked ticker. Press to follow X again"). A pinned panel uses `symOf(id) = pin || S.link`
(`:714`) for its data and its Ask Milo, and is skipped by `setLink` (`:939`). The hint row above the first linked panel says
"Panels marked [Follows] show this company or fund; the others show the whole market. Press a panel's marker to keep its
ticker when this one changes." (`:747`).

**Guard against late answers.** `DLINK[id]` records which ticker a panel's data is for; `loadPanel` drops an answer when the
panel's ticker moved while it loaded (`:903,911`) and `paintBody` shows a skeleton rather than data for another ticker (`:876`).

### 2.3 Controls

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Layout tab ×4 | tab (`role=tab`, `data-ws-preset`) | Market Overview, Options Research, Long-Term Investing, My Desk | sets `S.preset`, saves, repaints, announces "<label> layout." (`workspace.js:1029`; template `:726`) | Choosing My Desk when it has no visible panel copies Market Overview into it (`:1029`). Hidden at 640 px and under (`pages.css:1702`). Gets strip arrows/wheel/drag (`strips.js:18`). |
| Layout select | `select[data-ws-presetsel]`, aria-label "Layout" | same four options | same as the tab (`:1108`) | Shown only at 640 px and under (`pages.css:1700-1704`); refocused only on a fine pointer (iOS reopens a menu on focus, `:1108`). |
| Customize / Done | button `data-ws-edit`, `aria-pressed` | "Customize", "Done" | toggles `EDIT`, repaints, announces, refocuses the button (`:1085`; `:728`) | While on: link row hidden (`:847`), grips and resize corners drawn. |
| Add panel (n) | `details.ws-add` menu | "Add panel (n)"; one button per hidden panel (its title); "Every panel is showing." when none | `data-ws-show`: unhides it, moves it to the end, scrolls to it, focuses its menu (`:1078-1083`; `:732`) | Edit mode only. Optional panels that are absent (no brokerage) are not offered (`:723`). |
| Save as My Desk | button `data-ws-save` | "Save as My Desk" | copies this layout and its phone folds to My Desk, switches to it, leaves edit, toasts "Saved as My Desk." with Undo when it replaced one (`:1093-1102`) | Not drawn when My Desk is the layout (`:733`). |
| More layout actions | `details.ws-menu`, aria-label "More layout actions" | "Reset <layout> to its standard panels" (`data-ws-reset`) | restores `defaults(k)`, clears that layout's folds and customised flag, saves, toasts with Undo (`:1087-1092`; `:734`) | Edit mode only. |
| Linked ticker | text input `#ws-link`, `maxlength=12`, `data-v2-ta="submit"`, `autocomplete=off`, `spellcheck=false` | label "Company or fund shown in linked panels" | form submit -> `setLink(f.link.value)` (`:1110`; `:745`) | A typeahead pick submits the form (`typeahead.js:61`). No error text for an invalid or unchanged value (`:933`). |
| Update panels | submit button | "Update panels" | submits the form | A company name typed and submitted with this button (not Enter-with-typeahead) is taken as a ticker: "Apple" becomes `APPLE` (risk H-5). |
| Recent chips (up to 5) | button `data-ws-pick` (`tickBtn`), `aria-pressed` | recent companies and the open list's symbols, excluding the linked one (`:743-746`) | `setLink(sym)` (`:1030`) | Empty for a new guest. |
| Search for a company | button `data-v2-open-palette` | "Search for a company" | opens the global palette (`app.js:241`) | First-visit band. |
| Apple · AAPL, NVIDIA · NVDA | links | "Apple · AAPL", "NVIDIA · NVDA" | `#/AAPL`, `#/NVDA` (`:813`) | First-visit band. |
| Read today's market | link styled button | "Read today's market" | `#/read` (`:815`) | First-visit band. |
| Follow <name> <SYM> ×4 | toggle button `data-v2-watch`, `aria-pressed` | "Follow Apple AAPL", "Follow NVIDIA NVDA", "Follow Microsoft MSFT", "Follow S&P 500 fund SPY" / "Following ..." (`followBtn`, `:803-806`) | `toggleWatch` -> `store.follow` (`app.js:247`, `ui/company.js:40-53`), toast "X added to <list>." with Undo | Adds to the open list; never buys. SPY's tooltip: "SPY is a fund that holds the 500 companies of the S&P 500 ..." (`home.js:35`). The same four buttons also appear in the Watchlist panel when the list is empty (`:475`). |
| Not now / Done | button `data-ws-onboard-done` | "Not now" (the "Done" label is unreachable, risk H-4) | stores `optic.v2.onboard.v1 = done` and `optic.knowledge.asked.v1 = 1`, repaints, announces "Welcome dismissed. How Optic explains things is in Settings." (`:1086`; `:819`) | |
| Term marks | buttons `data-v2-term` | "ticker", "watchlist" | open a definition (`ui/term.js`) | `workspace.js:812,816`. |
| Grip | button `data-ws-grip`, aria-label "Move <title>: arrow keys move it earlier or later" | grip icon | ArrowUp/Left move earlier, ArrowDown/Right later (`:1112-1116`); pointer drag reorders, Escape cancels, a press without movement changes nothing (`:1120-1152`) | Edit mode only; hidden at 860 px and under (`pages.css:1624`). |
| Resize corner | `span[data-ws-resize]`, `aria-hidden`, title "Drag to resize" | none | drag snaps to 3, 4, 6, 8 or 12 columns (`:1134,1146`) | Edit mode only; hidden at 860 px and under. |
| Panel fold (title button) | button `data-ws-fold`, `aria-expanded` | the panel title + chevron | `setFold` (`:972-979`, `:1031`), saved per layout | Visible only at 860 px and under (`pages.css:1599,1632`); on desktop only the plain title shows. |
| About this panel (?) | button `data-ws-how`, `aria-expanded` | "?" icon, aria-label "About <title>: how to read it, its source and how fresh it is" | shows or hides the panel's explanation: scope line, `how` paragraph, Source, How fresh, Note, Not in Optic (`:1033`, `:787`, `paintBody` `:891-892`) | Hidden at 860 px and under (`pages.css:1630`); the ⋯ menu carries it there. |
| Ask Milo (panel) | button `data-v2-milo` (drafts) | Milo icon, aria-label "Ask Milo about <title>" | `openMilo` with the panel's question and figures (`app.js:242-246`); `data-v2-milo-sym` is the panel's ticker for linked panels (`:773`) | Hidden at 860 px and under; menu item "Ask Milo about this" there (`:776`). |
| ⋯ panel menu | `details.ws-menu` | aria-label "<title> options" | opens the menu below; clicking an item closes it (`:1032`) | |
| menu: About this panel | button (phone only) | "About this panel" | as About (`:775`) | `.ws-phone-only` shown at 860 px and under (`pages.css:1598,1627`). |
| menu: Ask Milo about this | button (phone only) | "Ask Milo about this" | as Ask Milo (`:776`) | |
| menu: Move earlier / Move later | buttons `data-ws-move` | "Move earlier", "Move later" | swaps with the neighbour, announces, focuses the grip or menu (`:960-968,1063`) | Edit only; disabled at the ends (`:778`). |
| menu: Narrower / Wider | buttons `data-ws-span` | "Narrower", "Wider" | steps the span 3/4/6/8/12 (`:969-971,1064`) | Edit only; hidden at 1100 px and under (`pages.css:1618`). |
| menu: Shorter / Taller | buttons `data-ws-h` | "Shorter", "Taller" | height s/m/l (`:1065`) | Edit only; only list panels and the three chart panels offer it (`sized`, `:764,780`); hidden at 860 px and under. |
| menu: Full width / Back to its width | button `data-ws-full` | those words | toggles span 12 and remembers the old span as `was` (`:1066`) | Edit only. |
| menu: Hide panel | button `data-ws-hide` | "Hide panel" | hides it, focuses the next shown panel, announces "<title> hidden. Add panel brings it back." (`:1077`) | Edit only. |
| menu: All columns / Fewer columns | button `data-ws-cols` | those words | toggles the panel's secondary columns (`.all-cols`, `:1036`) | Phone only; offered for `watch`, `earnings`, `movers`, `contracts` (`:763,783`). |
| menu: Keep X here... / Follow the linked ticker (X) | button `data-ws-pin` | "Keep <link> here when the link changes" / "Follow the linked ticker (<S.link>)" | pin or unpin (`:1067-1076`) | Linked panels only. |
| menu: Refresh | button `data-ws-reload` | "Refresh" | `loadPanel(id, {force:true})` (`:1084`) | Every panel. |
| Try again | button `data-ws-reload` | "Try again" | same (`:872`) | Appended to a panel's error card. |

Keyboard and gesture notes: `Escape` cancels a drag (`:1142`); `Enter`/`Space` work on every button; the `details` menus close on a click
elsewhere or Escape (`app.js:286-293`). Layout and folds persist (`save()`), see 2.6.

### 2.4 First-visit band (the only onboarding on Home)

`onboard()` (`workspace.js:807-821`), a `section#ws-new` titled "New to Optic? Three ways to start": (1) "Research a company.
Search by its name, such as Apple, or by its ticker ..." with the search button and two company links; (2) "Understand today's
market. What moved, what is scheduled and what it means, in a few lines; Market conditions below sums it up too." with
"Read today's market"; (3) "Save a company to follow. Following adds it to your watchlist; it does not buy shares or spend
money." with the four Follow buttons; then Not now. Shown while `isNew()` (no followed name in any list and no linked
portfolio, `:716`) and `optic.v2.onboard.v1` is not `done` (`:800-801`). A linked portfolio arriving later repaints it away
(`:927`). The first Follow press makes `isNew()` false, so the whole band is removed by the lists subscription
(`onLists`, `:1186-1189`) before a second name can be followed there.

**Knowledge-level question: none.** The routed Home never asks "How should Optic speak to you?". The comment says the level
"stays in Settings" (`workspace.js:797-798`). The question exists only in the unrouted page (`home.js:492-496`, loaded by
`loadModes` `home.js:631-640` from `/api/knowledge/modes`). The workspace still carries its handlers (`:1057-1062,1105`),
`NEW`/`loadNew` (`:715,853-858`) and `/api/knowledge/modes` is never requested by the routed Home (risk H-4).

### 2.5 Charts, tables, AI text, tooltips, menus

- Charts: Quote and chart (`lineChart` 3M/6M/1Y, dashed support/resistance overlays, a Measure ruler button inside every
  `lineChart`, `ui/chart.js:46,322`), Economy (`lineChart`, years axis over 36 readings), Your portfolio (area chart with
  "Source changes" marks), Fair value (`meter` SVG), sparklines in the Economy list, sector heat tiles (colour mix by
  magnitude, `workspace.js:402-403`). Crosshair is hover and keyboard (`chart.js:216-290`).
- Tables: Watchlist, Earnings, Movers, Contracts, Calendar, Regime factors, Financial trends, Business measures (columns in
  each panel entry below).
- AI-written text: the Optic Desk panel only (`morning_desk.voice == "written"`), labelled by `voiceWords` "Written for today by
  an AI model (<model>) from the day's figures and nothing else." or "Compiled by fixed rules ... no model wrote it."
  (`home.js:319`). Endpoint `/api/home`; spend, cache and bound in section 1. When a written note is replaced, the panel says so
  (`voiceWhy`, `home.js:321-326`). Not AI: Changes ("no model writes them", `workspace.js:301`), Questions (fixed rules),
  every figure.
- Tooltips: link chip title (`:757-758`), factor rule `title` (`:363`), Calendar missing-figure `title` (`:425`), Earnings
  "Not recorded" `title` (`:450`), ticker-button `title` for SPY (`:805`).
- Menus and drawers: panel ⋯ menus, the layout ⋯ menu, Add panel menu; "About this panel" is an inline disclosure, not a dialog.
  The palette (`data-v2-open-palette`) and Milo are drawers owned by other sections.

### 2.6 States, API, storage

- Loading: `skeleton('rows', 4, "Loading <title>")` per panel, two lines for Markets at a glance (`workspace.js:789`); a
  panel mid-reload shows the same (`:900`); after a timeout it says "Still loading <title>" and asks once more after 3 s
  (`:916-921`). A board the server is still building (`d.building`) is asked again after 12 s (`:907`). Footer words
  "Building" / "Updating" (`:889`).
- Error: `failed(<title>, err)` plus a "Try again" button (`:871-873`); for a linked panel a not-found is
  "<title> did not load. The data provider has nothing for X just now. ..." and is retried once after 5 s (`:866-870,923`).
- Empty: each panel has its own sentence (per panel entries). A panel holding only a sentence shrinks (`data-sparse`, `:886`).
- Stale: footer "Built N ago" when the data is older than three times its cadence (`:888-890`); the Indices panel adds
  "Some missing" with the unavailable list in About (`:351`).
- Missing optional panel: Your portfolio is `hidden` when no brokerage is linked (`:766,863`), but is drawn with a skeleton until
  `/api/brokerage/status` answers (risk H-10).
- API: every panel's own (table in 2.7); `GET /api/knowledge/modes` is not called; `GET /api/search` (typeahead).
- Storage read or written: `optic.v2.workspace.v1` (layout, link, folds, panel settings, pins); `optic.v2.onboard.v1` (written);
  `optic.knowledge.asked.v1` (written by Not now); `optic.recent.v1`, `optic.watchlists.v1`, `optic.chart.watch.v1`,
  `optic.watchlist.account.v1` through `core/store.js`; `optic.paper.v1` and `optic.roth.inputs` (read, symbols only, for the
  Changes panel, `home.js:362-371`); `optic.options.group.v1` (written when a change opens Options at a section,
  `workspace.js:1001`); `optic.timezone` (read for footer times, `:234`); `sessionStorage` scroll memory (`core/scrollmem.js:10,25`).
  Panel settings saved: sectors period, quote range, contracts side and sort, calendar impact, economy group and series,
  priority filter, and each linked panel's pin (`KEEP`, `:160`). Not saved: Earnings week, Contracts expiry, implied moves.
- Refresh: the poll ticks every 20 s from 4:00 to 20:00 New York time on weekdays and every 5 minutes otherwise, paused while the
  tab is hidden (`core/poll.js:25-33,36`); a tick reloads the market panels (`MARKET_PANELS`: indices, regime, expected, sectors, watch,
  quote, contracts, portfolio, trends) quietly only while the regular session is open (`workspace.js:1156,1179-1183`). A quiet reload that changed nothing repaints nothing (`:909`).
  Other tabs' changes to the workspace key are re-read (`:1169`).

### 2.7 Panel inventory (27 kinds; each has its own entry in section 3)

| id | Title | Default span | Linked | In layouts | Endpoint(s) | Spend? |
|---|---|---|---|---|---|---|
| portfolio | Your portfolio | 12 | no (optional) | market, longterm, mine | `/api/brokerage/status`, `/api/brokerage/workspace/overview`, `.../performance?period=3m` | no |
| priority | What matters today | 8 | no | market, mine | `/api/priority?quick=true` | no |
| desk | Optic Desk | 6 | no | market, mine | `/api/home` | **yes** (section 1) |
| changes | What changed since yesterday | 8 | no | none (Add panel) | `POST /api/briefing` | no |
| questions | Questions worth asking | 4 | no | none | `/api/home` | **yes** (the same call) |
| trends | Index and sector trends | 12 | no | none | `/api/trends/board` | no |
| alerts | Latest scan alerts | 4 | no | none | `/api/home` | **yes** (the same call) |
| indices | Markets at a glance | 12 | no | market, mine | `/api/home` | **yes** (the same call) |
| regime | Market conditions | 6 | no | market, mine | `/api/home`, `/api/sentiment` | **yes** (the same call) |
| expected | Expected move | 6 | no | market, mine | `/api/home` | **yes** (the same call) |
| sectors | Sector heatmap | 6 | no | market, mine | `/api/market` | no |
| calendar | Economic calendar | 6 | no | market, mine | `/api/brief?cached=true` | no |
| earnings | Earnings this week | 8 | no | market, mine | `/api/earnings-week?offset=&quick=true`; `/api/earnings/{sym}` on Load | no |
| movers | Moved most this month | 4 | no | market, mine | `/api/scanners/movers` | no |
| watch | Watchlist | 4 | no | all four | `/api/watchlist?symbols=` | no |
| quote | Quote and chart | 8 | **yes** | all four | `/api/quote/{sym}`, `/api/take-chart/{sym}?span=` | no |
| cnews | Company news | 6 | **yes** | options, longterm | `/api/news/{sym}` | no |
| news | Market news | 6 | no | market, mine | `/api/brief?cached=true` | no |
| economy | Economy | 12 | no | none | `/api/econ`, `/api/econ/{code}` for every series | no |
| contracts | Contracts | 12 | **yes** | options | `/api/options/{sym}/research?side=&delta_lo=0.15&delta_hi=0.85[&expiry=]` | no |
| value | Fair value | 6 | **yes** | longterm | `/api/fair-value/{sym}` | no |
| vol | Volatility | 6 | **yes** | options | `/api/ticker/{sym}?max_expiries=4&macro=true` | no |
| gex | Positioning | 6 | **yes** | options | same ticker read | no |
| tearn | Earnings | 6 | **yes** | options | `/api/earnings/{sym}` | no |
| biz | Business quality | 6 | **yes** | longterm | `/api/framework/{sym}?mode=combined` | no |
| fin | Financial trends | 6 | **yes** | longterm | same ticker read | no |
| own | Ownership | 6 | **yes** | longterm | same ticker read | no |

(`workspace.js:263-697`; layouts `:41-52`.) The "same call" panels share one `/api/home` request through the fetch cache.

### 2.8 Density: what a first-time visitor gets by default (as coded, guest, desktop wider than 1100 px, nothing followed)

- Blocks: page head, first-visit band, layout bar, linked-ticker row, **13 panels in the grid** (12 once the portfolio status
  answers "none").
- Fixed controls: first-visit band 9 (1 search, 3 links, 4 Follow, 1 Not now) + 2 glossary marks = 11; layout bar 5 (4 tabs +
  Customize); linked-ticker row 2; panel headers 12 x 3 (About, Ask Milo, ⋯) + 1 chip = 37 (the fold buttons exist but are
  hidden above 860 px); fixed in-body controls 31 (Sector heatmap 3 + 11, Quote 3 + 1, empty Watchlist 4 Follow, Calendar 2,
  Earnings 2, What matters today 2, Market conditions 1, Optic Desk 2). **About 86 fixed controls.**
- Data-driven in-body controls, from the template caps: Markets at a glance up to 8 links, Market news up to 14, Moved most up
  to 12, What matters today up to about 35 (week strip, event rows, show-more buttons), Earnings 2 per reporting company
  (ticker button and implied-move Load) + 1, Optic Desk 1. **Up to about 70 plus 2 per reporting company** (about 215
  interactive elements in a 30-company week).
- Phone: 4 panels open, 8 folded to a title and one line; layout select instead of tabs.

### 2.9 Risks seen in code (Home page)

| ID | P | Risk | Where |
|---|---|---|---|
| H-1 | P1 | Opening Home can spend: six panels share `/api/home`, whose server leg writes the Desk (first request of the day) and rewrites it in the background when the tape moves, with no sign-in and no per-visitor guard; bounded only by disk claims (2 first writes, 12 rewrites a day). | `workspace.js:290,343,357`; `main.py:2907,2955-2983,3015-3028,3205-3210` |
| H-2 | P2 | Desk freshness copy fits only the edition block: About says "Written before the open and after the close; this is the latest edition", but the lead, bottom line and branches (`morning_desk`) are written on the day's first request and rewritten when the tape moves, and the scheduled edition is off by default (`DESK_EDITION_AUTO`). The footer time is the `/api/home` build time, not when the note was written, so a morning note can read as freshly updated. | `workspace.js:75,296`; `main.py:2937-3030,4113-4121`; `home.js:319` |
| H-3 | P2 | Late answers for panel settings: `loadPanel` drops a late answer only when the *ticker* moved, not when Earnings' week, Quote's range, or Contracts' side/expiry changed, so the last answer to land wins and can disagree with the highlighted button. | `workspace.js:902-909`, `:1041-1042`, `:1106` |
| H-4 | P2 | Dead handlers and an unreachable "Done": `[data-ws-mode]`, `[data-v2-mode]`, `#ws-modes`, `[data-v2-home-ready]`, `loadNew`/`NEW`, an unused `recent` in `bar()`, and the "Done" label of the band can never show because the first Follow removes the band. | `workspace.js:715,724,819,853-858,1056-1062,1105,1186-1189` |
| H-5 | P2 | Setting the linked ticker is silent on failure and does not normalise share classes: an invalid or unchanged value does nothing and says nothing; `BRK.B` is kept as typed (the router and store turn it into `BRK-B`), so every linked panel asks the provider for a symbol it will not know. | `workspace.js:931-948`; `core/router.js:38`; `core/store.js:105-109` |
| H-6 | P2 | A ticker button in the Watchlist, Earnings, Movers and heatmap tables *relinks the panels* instead of opening the company; the only company link is the Quote panel's symbol. | `workspace.js:261,403,451,464,477` |
| H-7 | P2 | A linked ticker derived from the account's first watchlist name is saved into a non-personal key and survives sign-out. | `workspace.js:189,193-194`; `core/device.js:17-46` |
| H-8 | P2 | The Changes panel sends every followed name plus open paper positions, planner holdings and brokerage holdings (symbols only) to `POST /api/briefing`, which keeps "the names asked about, with a time and no owner". The panel says "sent as symbols only" but not that the server keeps them; the panel is off by default. | `workspace.js:301,303`; `home.js:362-371`; `main.py:2024,2035-2040` |
| H-9 | P2 | The regime score and the sentiment gauge are drawn in green and red with a filled line, with no on-screen note about whether the score has been shown to work; Home has no area notice. | `workspace.js:367-368`; `core/legal.js:36` |
| H-11 | P2 | The Index and sector trends panel's link "The full sector board" points to `#/market`, which the router reads as the ticker `MARKET` (Macro's slug is `macro`). | `home.js:448`; `core/router.js:38-44`; `nav.js:31` |
| H-10 | P2 (low) | Your portfolio is drawn at 12 columns with a skeleton for every guest until `/api/brokerage/status` answers; when a real-time chain provider is configured (`realtime_chain`) the shell footer says option chains are real-time while the Contracts, Volatility and Positioning panels say "delayed about 15 minutes". | `workspace.js:70,82,83,766`; `core/status.js:30`; `main.py:1041` |

---

## 3. Home panels (one entry per panel kind)

Every panel has the common chrome in 2.3 (About, Ask Milo, ⋯ menu with Refresh, plus the chip for linked panels), a body
(`#wsb-<id>`), a footer (`#wsf-<id>`: short source, "Updated <time> <zone>" when the payload has a time, then a status such as
"Delayed 15 min", "<date> close" or a cadence word, `workspace.js:94-110,890`) and an About block (scope, `how`, Source, How
fresh, Note, Not in Optic, `:891-892`). A panel's footer time comes from the field named in its entry. Auth is "guest or
account, nothing changes" unless stated. Storage is the workspace key only unless stated. "Spend" is section 1.

### Home panel: Your portfolio — `portfolio`
- Files: `workspace.js:264-278`; body `portfolio()` `home.js:98-132`.
- Purpose: the linked brokerage's value now, the day's move, a three-month value chart and the holdings that moved the total most.
- Auth: account with a linked brokerage only. Guest, or an account with none: the panel stays hidden (`workspace.js:766,863`;
  `/api/brokerage/status` returns no `connections` for a guest, `app/brokerage/routes.py:98-100`).
- Shows, in order: label "Your portfolio, value now" with a holdings-count pill; the value (`money`); "+$x (+y%) on the day" and, when it
  differs by more than $1, "Your broker's own total: $X, <ago>"; under 7 days of history a sentence saying how many days Optic has and
  that the chart "appears once there is a week of them", plus a time-weighted return when two values exist, otherwise the three-month
  chart with "It includes your own deposits and withdrawals, so it is not a return", then the time-weighted return with its source
  words (`home.js:116,122-125`); right side: a holdings table (Holding with "N shares", Price, Day, Effect; the six largest by
  absolute effect, `:126-128`), the basis sentence and "Last sync <ago>", two links.
- Controls: holding rows `a.pf-row` -> `#/<SYM>` (`home.js:128`); "All holdings" -> `#/brokerage/holdings`; "Performance" ->
  `#/brokerage/performance` (`:130`); chart Measure button and crosshair. Nothing else.
- States: loading skeleton (`workspace.js:789`); absent: hidden; performance failure is tolerated (`:271`) and the panel says "The
  value chart fills in as daily snapshots accumulate." (`home.js:124`); error: card with Try again.
- API: `GET /api/brokerage/status` (`workspace.js:268`), `GET /api/brokerage/workspace/overview`, `GET /api/brokerage/workspace/performance?period=3m`
  (`:271`; `app/brokerage/workspace_routes.py:65,90`). Spend: no. Reads the reader's holdings: Ask Milo here sends this panel's figures (`milo.js:66-80`).
- Footer: "Your linked brokerage, read-only" with no time (`:276`); "Last sync" is in the body. Refreshed with the market poll (`:1156`).
- Risks: H-10 (skeleton shown to guests); a `ctx.portfolio` side effect inside `portfolio()` feeds the chart (`home.js:109`), so the chart needs the body drawn first.

### Home panel: What matters today — `priority`
- Files: `workspace.js:279-286`; body `eventsBlock` `home.js:257-289`, `catalystStrip` `:234-256`, `evPress` `:293-313`.
- Purpose: today's calendar, this week's earnings and sector moves, grouped by when they land.
- Shows, in order: a week strip (`.cs-strip`, one cell per weekday up to the feed's horizon: "Today", "Tue 28", up to two items a day and an "N more" button; a closed day says "Market closed: <reason>", an empty one "Nothing tracked"), a key ("High impact", "Company report"), the note for the open item, two filter chips, groups **Now** (Sector moves), **Today** (Releases and reports), **This week** (Through the next N days), **Earlier this week** (Reported, with results), each up to 3 rows then "Show N more"; "Updated <ago>"; fold "How this is sorted and timed".
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Filter chips | `button[data-v2-evfilter]`, `aria-pressed` | "Everything", "Your names <n>" | sets `ps('priority').filter`, saves, repaints, refocuses (`workspace.js:1055`; `home.js:281-282`) | Persisted. "Your names" hides the week strip (`home.js:279`). |
| Week-strip item | `button.cs-btn[data-v2-cs]`, `aria-expanded`, `aria-controls="cs-note"` | the release or ticker, time or result, "(high impact)" for screen readers | toggles the note under the strip (`evPress`, `home.js:307-311`; repaint `workspace.js:1054`) | Items with no `why`, result or ticker are plain text (`home.js:241`). |
| "N more" | `button.cs-more` | "<n> more" | opens a note listing the rest of that day (`home.js:221-224`) | |
| Event row | `button.ev-head[data-v2-ev]`, `aria-expanded` | ticker or "Sector", title, meta (when, time, "<impact> impact", "on your list"), result | opens its body in place (`evPress`, `home.js:294-299`) | Open rows are remembered by key across repaints (`EV_OPEN`, `home.js:137`). |
| Show N more / Show fewer | `button.ev-more[data-v2-evmore]` | "Show 4 more" / "Show fewer" | opens the group's remaining rows (`home.js:300-306`) | |
| Open <TICKER> | link | "Open NVDA" | `#/<TICKER>` (`home.js:277`) | |
| How this is sorted and timed | `details.method[data-v2-fold]` | | disclosure; kept open across repaints (`workspace.js:879-881`) | |

- States: building: server answers `{available:false, building:true, reason}` after 6 s (`main.py:5326`), shown as a sentence and asked again after 12 s (`workspace.js:907`); unavailable: `ws-note` with the reason (`:283`); empty: "Nothing scheduled that moves the market / No major releases, earnings or sector moves in the next few days." (`home.js:263`); filter empty: "None of your names has an event in the next N days." (`:287`); error card.
- API: `GET /api/priority?quick=true` (`workspace.js:282`; `main.py:5215`). Spend: no (heavy cold scan, section 1). Footer time `generated_at` (`:284`).
- Storage: `priority.filter`.
- Risks: duplicates Read's "Today's priority" rendering of the same endpoint (X-3); a result body shows revenue, growth and reaction text from the server (`home.js:161-179`).

### Home panel: Optic Desk — `desk`
- Files: `workspace.js:287-298`; body `deskBody` `home.js:327-344`.
- Purpose: the day's Desk note: bottom line, lead, branches, the day's reports and its limits.
- Shows, in order: "For <date>. <voice words>"; when an edition is kept, a block "Today's edition" or "Latest edition, <date>, <slot>" with headline, summary and link "The full edition"; "**Bottom line.** ..." (`md.overall`); the first lead paragraph; fold "The whole desk" (rest of the lead, "What could happen next" branches, "Note.", "Today's reports"); fold "What this does not tell you (N)"; a line saying why the written version is not showing (`voiceWhy`).
- Controls: link "The full edition" -> `#/read` (`home.js:333`); `details.desk-more` and `details.desk-limits` (closed by default, `data-v2-fold`).
- AI-written: yes, `ai.write_morning_desk` (`main.py:2985-3000`), labelled; the edition block is also AI-written when one is kept (`desk_edition_mod.served`, `main.py:3224-3236`; the page never writes one).
- States: unavailable: "No Desk edition is available right now." or the server's reason (`workspace.js:293`); loading and error common.
- API: `GET /api/home` -> `morning_desk`. **Spend: this is the leg that can pay**, and every panel that reads `/api/home` starts the same call (section 1; risk H-1).
- Footer: "Optic Desk", time = `/api/home` generated_at (`:296`); the write time is not shown unless the note was replaced (risk H-2).
- Risks: H-1, H-2. The "What could happen next" branches are model-written; the prompt asks for "if this, then that" and not a prediction of which happens (`app/ai.py:2775-2815`); the output itself was not checked here.

### Home panel: What changed since yesterday — `changes`
- Files: `workspace.js:299-311`; body `changesBlock` `home.js:379-400`, `changeRow` `:372-378`, `briefingHoldings` `:362-371`.
- Purpose: the latest completed session against the one before for the reader's names, item by item, from fixed rules.
- In no layout by default; added from Customize.
- Shows, in order: period label and notes; a summary sentence; up to 4 items (symbol, "Held", headline, an Open button, detail, why shown once per kind); "All N changes"; "No meaningful change: SYM +x%."; "Not checked: ..."; per-name stale lines; a first-read note; fold "How this is compared".
- Controls: "Open" button `button.dc-open[data-v2-dc][data-v2-dc-view][data-v2-dc-panel]`, text "<panel or Chart/Options/Earnings/Financials/Investing> ->" -> `openChange` navigates to `#/<SYM>[/<view>]` and, when a panel is named, waits up to 10 s (40 x 250 ms) for its section, opens it and holds it in view until the reader scrolls (`workspace.js:1000-1025,1053`); "All N changes" / "Show fewer" `button[data-v2-dc-all]` (`:1052`; not persisted); fold "How this is compared".
- States: skeleton "Comparing your names" (`home.js:380`); `available:false`: the server's reason (`:382`); names with no saved reading are re-asked once after 25 s (`workspace.js:305`).
- API: `POST /api/briefing {symbols, holdings}` (`workspace.js:303`; `main.py:2035`). Spend: no. Privacy: risk H-8.
- Storage read: `optic.paper.v1`, `optic.roth.inputs`.

### Home panel: Questions worth asking — `questions`
- Files: `workspace.js:312-318`; `core/market-questions.js` (whole file).
- Purpose: up to five questions to draft into Milo, built from today's real moves, the session, the top story, a due release and a rotating pool.
- Controls: up to 5 `button.btn-milo.ws-q[data-v2-milo]` whose label is the question; a press drafts it (nothing is sent: `workspace.js:316`, `app.js:242-246`). No other control.
- States: "No questions until the market figures load." (`:316`); loading and error common.
- API: `GET /api/home`. Spend: shares the `/api/home` call (H-1); the press itself does not spend.
- Risks: wording drafts forecasts ("Is the market underpricing risk?", "What is the market bracing for?", "Is the market getting complacent?", `market-questions.js:34,68`), which the reader sends to Milo; it also duplicates `rankedMoves` (X-4).

### Home panel: Index and sector trends — `trends`
- Files: `workspace.js:319-326`; `trendsBlock` `home.js:442-450`, `trendBasis` `:409-429`, `trendCell` `:430-441`.
- Purpose: SPY, QQQ, IWM and the 11 SPDR sector funds against the prior completed session's high and low.
- In no layout by default.
- Shows: a sentence naming the levels and price kind (last close, regular session, delayed minutes); group "Indices" then "Sectors" as cells (symbol, price, name, "Uptrend/Downtrend/Neutral", a price-kind note when different, distance to the level, the action sentence); "The full sector board" link; fold "How the levels are set".
- Controls: each cell is a link `a.tr-link` -> `#/<SYM>` (`home.js:434`); link "The full sector board" -> `#/market` (`home.js:448`), which is not a route: `market` is the Macro view's id, its address slug is `macro` (`nav.js:31`), so the router reads `#/market` as the ticker `MARKET` and opens a Dossier for it (`core/router.js:38-44`); fold.
- States: skeleton "Loading the board"; unavailable: "The trend board is unavailable right now (<reason>)." (`:444`).
- API: `GET /api/trends/board` (`main.py:4565`). Spend: no. Footer time `generated_at`.
- Risks: **H-11 (P2) broken link**: "The full sector board" opens a Dossier for `MARKET`, not Macro (`home.js:448`; every other link in this section's files uses a real slug, checked by listing them). The "action" and "vs level" sentences are server text (`sector_board_mod.trends`), not read here; the same funds appear in the Sector heatmap from a different endpoint (X-5).

### Home panel: Latest scan alerts — `alerts`
- Files: `workspace.js:327-338`.
- Purpose: the last six alerts Optic's scheduled scan raised. In no layout by default.
- Controls: each row a link `#/<TICKER>` (empty ticker gives `#/`, `:334`); link "Alerts" -> `#/alerts`.
- States: "The scheduled scan has not flagged anything recently." (`:333`).
- API: `GET /api/home` -> `alerts`. Spend: shares the `/api/home` call. Footer: source only, no time (`:336`); rows carry their age.
- Risks: footer has no time (X-10); an alert with no ticker links to `#/` (P2, low, `:334`).

### Home panel: Markets at a glance — `indices`
- Files: `workspace.js:339-353`.
- Purpose: eight cross-asset readings: S&P 500, Nasdaq 100, Russell 2000, VIX, US 10Y, WTI Crude, Gold, Bitcoin (`STRIP`, `:246`).
- Shows: one cell per instrument with a figure (rates with %), its move in percent (rates in basis points, `moveText` `:256-260`), a unit line (`UNIT`, `:240`), and for futures after the 6 PM reopen "Since <day>'s settle; <day> +x%" (`basisLine` `:251-255`). Missing instruments are left out.
- Controls: each cell is a link `a.ws-cell` -> `#/instrument/<symbol>` (`:349`). Nothing else.
- States: "No index readings came back from the feed." (`:346`); footer "Some missing" with the list in About (`:351`); note "Outside the regular session, equities are at the last close; futures and crypto keep trading." (`:351`).
- API: `GET /api/home` -> `macro.groups`. Spend: shares the `/api/home` call. Footer time `generated_at`; status "Delayed 15 min" or "<date> close" (`:110`).
- Risks: none beyond H-1; colours are direction only and the About says so (`:342`).

### Home panel: Market conditions — `regime`
- Files: `workspace.js:354-376`.
- Purpose: two separate readings: Optic's regime score (named rules) and a sentiment gauge.
- Shows: a lead "<plain words>. <stance>" (`PLAIN_REGIME`, `STANCE`, `:242-245`); "Optic's market score" (-100 to +100, tone-coloured with a signed line, "From -100, cautious, to +100, leaning toward <risk>" with a glossary mark); "Sentiment gauge" (score, label, line, "0 is extreme fear, 100 extreme greed") or its reason; fold "How these readings are built" with the factor table (Factor, Reading, Effect on the score) and the gauge's inputs as bars.
- Controls: `details.ws-more` (closed); a glossary mark. Nothing else.
- States: sentiment failure is shown as `{available:false, reason}` (`:357`); no macro: "Not available".
- API: `GET /api/home`, `GET /api/sentiment` (`main.py:4613`). Spend: shares the `/api/home` call. Footer time: the later of sentiment or home `generated_at` (`:374`).
- Risks: H-9; three other places show "regime" for different models (X-6).

### Home panel: Expected move — `expected`
- Files: `workspace.js:377-392`.
- Shows: "Priced, as one day" (+-x% = VIX / 16, points), "Typical day lately" (+-y%, 14-day ATR / 1.6), "Priced against typical" (x times), and the server's reading sentence.
- Controls: none. States: "Expected move unavailable: the VIX or the S&P 500 quote did not load." (`:383`).
- API: `GET /api/home` -> `macro.expected_move`. Spend: shares the call. Footer time `generated_at`.
- Risks: the same figure is labelled three ways on three pages (X-7).

### Home panel: Sector heatmap — `sectors`
- Files: `workspace.js:393-407`.
- Purpose: the 11 SPDR sector funds coloured by their move over a chosen period.
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Period | segmented buttons `data-ws-set="sectors:period:<k>"`, `aria-pressed` | "1 day", "1 week", "1 month" | sets the period, saves it, repaints (`workspace.js:1037-1044`; `:401`) | Persisted. |
| Tile x11 | `button.ws-heat-t[data-ws-pick]`, `aria-pressed` | sector name, symbol, move | links the fund to the linked panels (`:1030`; `:403`) | Colour is mixed by magnitude (`--mix`); every tile prints its figure. Linking a sector fund makes Business quality, Financial trends and Ownership say it is a fund and offer three company links (`notCompany`, `:702-703`). |

- States: "No sector readings came back from the feed." (`:399`). API: `GET /api/market` (`main.py:1719`), which is about 40 symbols and slow cold (`macro.js:6`). Spend: no. Footer time `generated_at`.
- Risks: a third source for the same funds (X-5); a tile press changes the linked ticker to a fund, which turns three company panels into "is a fund" notes (by design, `:702`).

### Home panel: Economic calendar — `calendar`
- Files: `workspace.js:408-434`; `impSeg` `:705`.
- Purpose: scheduled US releases for the coming days from the last built Read.
- Shows: an impact filter and a table: Time (ET), Release (with "Released" flag and agency), Impact, and, when any row has figures, Actual and Prior (cells say why empty: "Not applicable", "Not released yet", "Not available", `core/finviz.js:165`), grouped by day.
- Controls: impact segmented buttons `data-ws-set="calendar:imp:<k>"`: "All", "Medium and high" (`:705`; persisted).
- States: no Read: "The calendar comes with the day's Read, which is not ready yet." (`:413`); empty: "Nothing scheduled[ at medium or high impact] in the window." (`:416`).
- API: `GET /api/brief?cached=true` (`workspace.js:411`). Spend: no. Footer time `built_at`, note "From the last built Read." when stale, and in About "Not in Optic: ... Consensus forecasts are licensed and not in Optic." (`:432`).
- Risks: a second rendering of the same calendar exists on Read (X-3).

### Home panel: Earnings this week — `earnings`
- Files: `workspace.js:435-456`.
- Purpose: who reports this or next week with EPS and revenue consensus and an on-request implied move.
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Week | segmented `data-ws-set="earnings:offset:<0\|1>"` | "This week", "Next week" | drops the data and reloads (`:1041`; `:440`) | Not persisted. Only two of the page's three weeks. |
| Ticker | `button.ws-tick[data-ws-pick]` | the ticker | links it (`:1030`; `:451`) | Does not open the company (H-6). |
| Load | `button.textlink[data-ws-im]`, aria-label "Load the implied move for <T>" | "Load" | `GET /api/earnings/<T>`; shows "Reading the chain...", then "+-x% to <date>" or the reason (`:1045-1050`) | One option-chain read per press; not for rows already reported. |
| See the whole week | link | "See the whole week, by day" | `#/earnings[?week=1]` (`:452`) | |

- Shows: Day with time ("Time not set"/"Time not known" when the source has none), Company ("Unconfirmed" flag), EPS est., Revenue est., Implied move; reported rows say "Reported: <result>" and "Not recorded" with a reason on hover (`:450-452`).
- States: unavailable: the reason (`:441`); none: "No reports found for <week> among the N companies checked." (`:443`); all out: "Every report in <week> is out. The coming week is under Next week." (`:446`).
- API: `GET /api/earnings-week?offset=<n>&quick=true` (`:438`), `GET /api/earnings/{sym}` (`:1047`). Spend: no. Footer: time `generated_at`, "N companies checked, M could not be read".
- Risks: H-3 (week toggle race).

### Home panel: Moved most this month — `movers`
- Files: `workspace.js:457-468`. Purpose: the 12 largest one-month moves among liquid US stocks, from the nightly scan.
- Shows: Ticker (button), 1 month (signed, coloured), Volume (x its normal, secondary column). Controls: ticker buttons `data-ws-pick` (`:464`). "Ranking loading: N of M symbols." while building (`:462`).
- API: `GET /api/scanners/movers` (`main.py:6649`). Footer: "Scan N h old" and "older than usual" (`:466`). Spend: no.
- Risks: a ranked list headed by size of move with no "not a recommendation" line here (Explore says it, `explore.js:39`); H-6.

### Home panel: Watchlist — `watch`
- Files: `workspace.js:469-482`; `followBtn` `:803-806`.
- Purpose: the open watchlist's price and day move, up to 30 names.
- Controls: ticker buttons `data-ws-pick`; when the list is empty, four Follow buttons (`:475`; Apple, NVIDIA, Microsoft, S&P 500 fund); "The whole list is on Watchlist" link when more than 30 (`:478`); columns Ticker, Price, Day, Changed (secondary).
- States: empty: "Your open watchlist is empty. Follow a few names to start, or press Watch on any company." (`:474`).
- API: `GET /api/watchlist?symbols=<up to 30>` (`:472`; `main.py:2837`). Spend: no. Footer has no time (`:480`).
- Reload: on any list change (`onLists`, `:1190`).
- Risks: H-6; the symbols of the reader's list travel in the query string.

### Home panel: Quote and chart — `quote`
- Files: `workspace.js:483-505`. Linked. Purpose: the linked ticker's price, day change and daily-close chart with nearest support and resistance.
- Controls: range `data-ws-set="quote:span:<3m|6m|1y>"` "3M/6M/1Y" (persisted; reloads, `:1042`); symbol link `a.ws-sym` -> `#/<link>` (`:493`); chart crosshair and Measure.
- States: "No quote for <T>. Check the ticker." (`:489`); "Day's change not reported yet" (`:492`); partial quote note (`:494`); "No price history for <T>." (`:496`).
- API: `GET /api/quote/{sym}`, `GET /api/take-chart/{sym}?span=` (`:486`). Spend: no. Footer time `c.as_of`. It also teaches `core/instrument.js` whether the symbol is a fund (`learn`, `:486`), which repaints Business, Fair value, Financials, Ownership (`:1167`).
- Risks: H-3 (range answers can land out of order, `:1042`); no other found.

### Home panel: Company news — `cnews`
- Files: `workspace.js:506-517`. Linked. Purpose: up to 12 headlines about the linked ticker, newest first, with publisher and age.
- Controls: each headline an external link (`target=_blank rel="noopener noreferrer"`, `:513`). An earnings warning callout when present.
- States: "No recent headlines for <T>." (`:512`). API: `GET /api/news/{sym}` (`:509`). Spend: no. Footer: source and cadence "Every 10 min", no time.
- Risks: footer has no time (X-10; each headline carries its age).

### Home panel: Market news — `news`
- Files: `workspace.js:518-531`. Purpose: up to 14 wire headlines from the last built Read, with publisher, age and, when the feed has it, "leans positive/negative/mixed".
- Controls: external links. States: "No wire headlines in the last built Read." (`:526`). API: `GET /api/brief?cached=true`. Footer time `built_at`. Spend: no.
- Risks: the "leans positive" tag is a tone label on a headline (`:527`); the About says "Nothing here is written by a model".

### Home panel: Economy — `economy`
- Files: `workspace.js:532-555`. In no layout by default. Purpose: 23 FRED indicators in five groups with a chart for the chosen one.
- Controls: group buttons `data-ws-set="economy:group:<k>"`: "All", "Inflation", "Labour", "Growth and activity", "Rates and policy", "Credit and money"; series buttons `data-ws-set="economy:code:<code>"` (one per indicator with its latest value, date, change and a sparkline); chart with Measure. Both persisted.
- States: "That series did not come back from FRED." (`:550`). API: `GET /api/econ` then one `GET /api/econ/{code}` per series, 23 requests in one load (`:536-538`; `app/analytics/econ.py:34-45,49`). Spend: no. Footer: "FRED, St. Louis Fed", no time.
- Risks: 24 requests for one panel; a series failure is shown only if it is the selected one.

### Home panel: Contracts — `contracts`
- Files: `workspace.js:556-581`; `CONTRACT_COLS` `:204-215`. Linked. Purpose: the 14 option contracts nearest the money for the linked ticker at one expiry.
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Side | segmented `data-ws-set="contracts:side:<call\|put>"` | "Calls", "Puts" | clears the expiry and reloads (`:1042`; `:571`) | Persisted. |
| Expiry | `select[data-ws-expiry]` inside `label.ws-sel` | "<date> (<n>d[, monthly])", up to 14 | sets the expiry, reloads (`:1106`; `:572`) | Not persisted. |
| Column sort x9 | `button.th-sort[data-ws-sort]` in `th[aria-sort]` | Strike, Mid, Cost, Spread, Delta, IV, Open int., Volume, Liquidity | toggles ascending/descending, saves, announces (`:1035`; `:575`) | Persisted; default Strike ascending. Optic ranks nothing (`:202`). |
| Row details | `button.ws-rowbtn[data-ws-row]`, `aria-expanded` | chevron, aria-label "Every figure for the <strike> <side>" | opens the secondary figures (`:1034`; `:576`) | |
| All columns | phone menu item | | `:1036` | |

- Shows: "ATM IV x%, straddle prices +-y% to expiry" when present; the table; Cost = mid x 100 (dollars per contract).
- States: no chain: the reason (`:561`); nothing in the band: the chain's own reason or "No <side>s with a two-sided quote between 0.15 and 0.85 delta at this expiry." (`:570`).
- API: `GET /api/options/{sym}/research?side=&delta_lo=0.15&delta_hi=0.85[&expiry=]` (`:559`; `main.py:1516`). Spend: no. Footer time `fetched_at`; note "Mid is between bid and ask; you usually pay more." (`:579`). Reloaded by the 20 s poll in session.
- Risks: H-3; "Cost" and a ready table of nearest-the-money contracts is as close to a trade ticket as Home gets; the About says there is no grade or pick (`:558`); no area notice on Home (X-1).

### Home panel: Fair value — `value`
- Files: `workspace.js:582-593`; `meter` `ui/chart.js:344-358`. Linked. Purpose: where the price sits against the company's own five-year P/E range.
- Shows: a range gauge (low, "fair <mid>", high, price marker) and "<T> trades at <price>, <below|inside|above its range|too wide to call>. <basis>" (`app/analytics/fair_value.py:49-55`).
- Controls: none. States: the server's reason or "No fair value range for <T>: it needs positive earnings and enough price history." (`:588`). API: `GET /api/fair-value/{sym}` (`main.py:5423`). Spend: no. Footer time `generated_at`.
- Risks: the gauge label "fair N" reads as a target price (P2, low); the sentence itself is neutral and the About says "not where it is going".

### Home panel: Volatility — `vol`
- Files: `workspace.js:597-612`. Linked. Shows: "Implied move to <date>" (+-x%, days, "includes earnings"), "Implied volatility, 30 days" with its one-year rank, "Skew, <date>" ("Puts dearer", "Calls dearer", "About equal", `options-panels.js:32`); link "<T> options in full" -> `#/<T>/options`.
- States: the chain's reason (`optionsReason`, `:701`): outside market hours "the free feed can serve it unquoted" (About). API: `GET /api/ticker/{sym}?max_expiries=4&macro=true` (`:699`; `main.py:1086`), shared with Positioning, Financial trends, Ownership. Spend: no. Footer time `generated_at`.
- Risks: none found beyond H-10 (delay wording).

### Home panel: Positioning — `gex`
- Files: `workspace.js:613-629`. Linked. Shows: "Dealer gamma" (Positive/Negative with "Hedging tends to damp moves" / "extend moves"), "Call wall", "Put wall" (strike and distance), "Flip point" ("None within 12%"), and the server note.
- Controls: none. States: the chain's reason. API: the same ticker read. Footer: "Optic dealer-gamma estimate from Yahoo Finance open interest". Spend: no.
- Risks (P2, low): "Hedging tends to damp/extend moves" is a causal claim about price; the About calls it "an estimate from public open interest, not reported positions".

### Home panel: Earnings (linked) — `tearn`
- Files: `workspace.js:630-646`. Linked. Shows: "Next report" (date, days, date status), "Options price for it" (+-x%, times its usual move), "Average report-day move", "Beat rate" (n of m); link "<T> earnings in full" -> `#/<T>/earnings`.
- States: `not_applicable`: the server's reason (`:635`). API: `GET /api/earnings/{sym}` (`:633`; `main.py:1174`), no AI. Footer time `generated_at`. Spend: no.
- Risks: none found.

### Home panel: Business quality — `biz`
- Files: `workspace.js:647-661`; `notCompany` `:702-703`. Linked. Shows: "Grade <A-F>" with "Valuation: <label>" and seven component grades, then the framework's "why" sentence.
- Controls: for a fund, three `button.ws-tick[data-ws-pick]` "Link AAPL", "Link MSFT", "Link NVDA" and a link "Its long-term record" (`:702-703`).
- States: no grade: the summary or "No business grade for <T>." (`:654`). API: `GET /api/framework/{sym}?mode=combined` (`:650`; `main.py:1205`), deterministic. Footer time `generated_at`.
- Risks: P2 (a): the valuation label comes from `app/research/quality.py:77` ("Attractive", "Fair", "Full", "Stretched") and is printed beside a letter grade; "Attractive" next to "Grade A" reads as an endorsement.

### Home panel: Financial trends — `fin`
- Files: `workspace.js:662-679`. Linked. Shows: four fiscal years of Revenue, Net income, Free cash flow (compact), operating and net margin, revenue growth; link "<T> financials in full" -> `#/<T>/financials`. Fund: `notCompany`.
- States: "No statements for <T> in the feed." (`:669`). API: the shared ticker read -> `company.financials`. Footer time `generated_at`. Spend: no.
- Risks: none found.

### Home panel: Ownership — `own`
- Files: `workspace.js:680-696`. Linked. Shows: "Insiders, 6 months" (signal word, buys, sales), "Held by institutions" (percent), "Largest holders" (raised, cut, of n, threshold). Fund: `notCompany`.
- States: "No ownership data for <T> in the feed." (`:687`). API: the shared ticker read -> `company.ownership`. Footer: "SEC Form 4 and 13F via Yahoo Finance", time `generated_at`. Spend: no.
- Risks: "Insiders, 6 months: <signal>" is a word such as bullish or bearish from the server (`capFirst(o.insider_signal)`, `:690`), a directional label on a company; P2, low.

---

## 4. Markets, Discover and Compare routes

### 4.1 Read — `#/read`
- Files: `pages/read.js` (371 lines), `pages/tabs.js` (`sectionHead`, `tabSelect`), `ui/grouptabs.js`, `ui/states.js` (`generated`, `how`, `empty`, `failed`, `skeleton`), `core/track.js`, `ui/score.js`, `core/marketTime.js`.
- Purpose: the day's Read (an AI-written morning note over computed figures), the Desk edition, and ten supporting views in three groups.
- Auth: guest; nothing changes when signed in except the Ask Milo allowance. Notice: "Not a recommendation. A summary of published news ..." (`core/legal.js:36-41`, area `brief`).
- Sections in render order (`paint`, `read.js:279-287`):
  1. Page head: `h1` "Markets" (+ screen-reader ", Read") and the tabs Read | Macro | Indices (`tabs.js:29-33`; a select on phones, `app.js:296-300`). Always.
  2. **Read hero** (`readHero`, `:69-91`), open. Missing: "Today's Read is not ready yet" with the cost sentence and a build button (`:73`). Loaded: index-fund strip (+ "Fund prices, not index levels."), label "Optic's Read, <date>", headline `h2`, sub-line "Prices and headlines updated <ago>[. Showing the previous day's Read until today's is ready | . A newer edition is due shortly]. Covering the N hours since the previous session closed[, the whole weekend].", the build control when previous-day or stale, Ask Milo, the AI paragraphs (a line starting `## ` is an `h3`), the AI label, "The text covers the session of <day>", "The text was written from the figures at that time; the prices above are newer." when more than 30 min apart (`:85`), an unmatched-figure warning (`:86`), fold "How the Read is made", the headline search and its results.
  3. **Desk edition** (`desk()`, `:27-40`), open, absent when none is kept: label "Optic Desk, <slot>[, a test edition]", headline, AI label, summary, per-section items each with source links (`a.cite`), fold "How this edition was made".
  4. **More from today** (`h2#rd-more-h`): grouped tabs (below).
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Markets tabs | links in `nav.tabs`; select `data-v2-tabsel` on phones | Read, Macro, Indices | navigate (`app.js:296-300`) | |
| Index strip cell xN | `a.mcell` | "<SYM> <name>", last, day move | `#/<SYM>` (`:76`) | Fund prices (SPY, QQQ ...), said so (`:77`). |
| Ask Milo about the Read | `miloButton` | "Ask Milo about the Read" | drafts "What matters most in today's Read, and what period does it cover?" (`:82`) | |
| Build today's Read | `button[data-v2-read-build]` | "Build today's Read" (also "Build today's Read now", "Update it now" as a text button, `:81`) | `buildRead` (`:52-68`, handler `:342`): `GET /api/brief` (no `cached`), then asks `cached=true` every 8 s up to 15 times while `refreshing`, toasts on failure, focuses the headline (`:67`) | **Paid** (section 1). One at a time (`D.building`). The cost is stated before the press: "one model call for this edition, shared by every reader. It can take half a minute." (`:46,49`). |
| Search the headlines | `input[name=q]` in `form[data-v2-read-search][role=search]` | placeholder "Search the headlines" | typing: 220 ms debounce then `GET /api/brief/search?q=&limit=40` (`:328-332,363-371`); Enter searches now (`:335`); Escape clears (`:333`) | Late answers dropped by `D.sseq` (`:366`). Server `q` max 120 (`main.py:3426`); longer gives an error line "Could not search ..." (`:96`). |
| Result headline xN | external link | the headline, source, age, "subscription" for paid sources | opens the publisher (`target=_blank rel=noopener`, `:100`) | |
| How the Read is made / How this edition was made | `details.more-inline` | | disclosure | closed by default. |
| Group tabs x3 | `button[role=tab]` in `.gtabs` | Today, Catalysts and calendar, Sentiment and regime | click, ArrowLeft/Right wrap, Home, End (`grouptabs.js:37-48`) | Default group 0; state kept per visit (`tabState`, `:309`). |
| Sub-view chips | `button.chip[data-gs]`, `aria-pressed` | Group 1: Today's priority, Overnight, worldwide, Headlines, Official releases and sources. Group 2: On the calendar, Market catalyst, Catalyst library. Group 3: Fear and Greed, Market regime, Weekly analysis (`RGROUPS`, `:289-293`) | `grouptabs.js:40` | Drawn when the group has more than one view. |
| Priority row ticker | link `a.tk-link` | the ticker | `#/<T>` (`:119`) | |
| Overnight market | link | market label | `#/instrument/<SYM>` (`:109`) | |
| Write the read | `button[data-v2-catread]` | "Write the read" | `GET /api/catalyst-mode` forced (`:345-349`) | **Paid**, on a release in the last 72 h; 24 a day ceiling, kept 1 h. Says "Written by an AI model when someone asks, then kept for an hour and shared with every reader." (`:134`). |
| Catalyst search | `input[name=q]` + submit "Search" in `form[data-v2-cat-form]` | placeholder "Search catalysts" | `cat.q`, `loadCats()` (`:336`) | |
| Status / Category / Sector / Theme | `select[data-v2-cat]` | Status: Relevant now, Archived, All; the others "All" + facets from the server (`:143-146`) | change -> `loadCats()` (`:338`) | Late answers are not dropped (RD-3). |
| Catalyst card | `details.cat-card` | horizon, category, date, title, summary | opens the company table and source link (`:147-149`) | Company links `#/<T>`. |
| Scan for new catalysts | `button[data-v2-cat-refresh]` | "Scan for new catalysts" / "Scanning..." | `POST /api/catalysts/refresh` (`:355-360`); toast with the server message | Rules reader by default (no spend). One at a time, spaced 15 min for non-owners (`main.py:4837-4870`). |
| Write this week's update | `button[data-v2-weekly-write]` | "Write this week's update" | `GET /api/weekly` forced (`:350-354`) | **Paid**, once per ISO week for everyone; text "Written by an AI model when someone asks, in about a minute, then kept for the week and shared with every reader." (`:161`). |
| Ask Milo what goes into this | `miloButton` (Fear and Greed) | | drafts (`:178`) | |
| Calendar impact chips | `button.chip[data-v2-cal-impact]` | All, High impact, one per category with its count ("Company reports" for earnings) | `cal.impact`, repaint (`:343`; `:252`) | Not persisted (module memory). |
| Calendar window | `button[data-v2-cal-range]` | Today, This week, "Next <N> days" | `cal.range` (`:344`; `:253`) | |
| Calendar item links | external link on a release title; `#/<T>/earnings` on a report | | (`:222,232,236`) | |
| Insider filings link | link | "Insider filings are on Insiders" | `#/insiders` (`:271`) | |
| Try again | `button[data-v2-retry="brief"]` | "Try again" | `retry.brief`: invalidates `/api/brief`, calls `render` again (`:324`) | Re-adds every listener (RD-1). |

- Inputs: headline search (above); catalyst search; no ticker box. No glossary marks are placed by hand; the app-wide marker may mark eligible prose (`glossmark.js:22-25`).
- Tables: Overnight (Market, Day, 5 days, 20 days, With the S&P, `:109`); Catalyst companies (Company, How directly, Strength, Why, `:148`); Fear and Greed inputs (Input, Weight, Score, Reading, `:176`); Regime inputs (Input, Weight, Reading, How it is scaled, `:187`).
- AI-generated: the Read paragraphs (`/api/brief?cached=true`, written by the background loop or by the Build button, kept per edition), the Desk edition (`/api/desk/edition`, never written by a page load), the catalyst read, the weekly analysis. Each carries "Written by an AI model from the figures, <ago>. It interprets them and can be wrong; the figures are the record." (`ui/states.js:24-29`), or "Compiled by fixed rules from the figures; no model wrote it." when mechanical. Nothing is said when the payload carries neither marker (`states.js:25`).
- States: hero: loading `skeleton('lines',6,"Loading today's Read")` (`:72`); error `failed("Today's Read", ..., {retry:'brief'})` (`:71`); missing: the empty card with the build button (`:73`); building: "Building today's Read. It appears here when it is done." (`:48`); "It is still being built. It appears here when you come back, or press again in a minute." (`:65`). Views: overnight (`:104-107`), priority (`:116-117`), catalyst (`:125-126`), library (`:140-141,150`), weekly (`:158-161`), sentiment (`:172-173`), regime (`:183`), calendar (`:240-242,254-255`). Failure of priority or the catalyst fetch is drawn as an empty state (RD-2).
- API: `GET /api/brief?cached=true`, `GET /api/brief` (build), `GET /api/brief/search`, `GET /api/desk/edition`, `GET /api/priority`, `GET /api/catalyst-mode[?cached=true]`, `GET /api/weekly[?cached=true]`, `GET /api/sentiment`, `GET /api/catalysts`, `POST /api/catalysts/refresh`, `GET /api/validation` (Market regime's history line, `core/track.js:76`).
- Storage: none. `tabState`, `cal`, `cat` live in module memory; scroll position in `sessionStorage` (`core/scrollmem.js`).
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| RD-1 | P2 | "Try again" calls `render` on the same element, so `wire` adds every handler a second time: Write the read, Write this week's update and Scan for new catalysts then each fire twice (the server single-flights the paid writes; the second catalyst POST gets a 409 or cooldown toast). | `read.js:324,326-362`; `app.js:280-283` |
| RD-2 | P2 | A failed fetch is drawn as an empty answer: priority ("Nothing on the board right now"), catalyst mode ("No release is driving the market ... Nothing major has been released in the last 72 hours"). | `read.js:117,125-126,317-318` |
| RD-3 | P2 | Catalyst filters: each select or search calls `loadCats` with no request identity, so an older answer can overwrite a newer filter. | `read.js:301-306,336-338` |
| RD-4 | P2 (low) | The Read's hero strip lists fund prices (SPY, QQQ, IWM ...) under "Indices" while Home and Indices show index levels; the line "Fund prices, not index levels." is the only bridge. | `read.js:76-77` |

### 4.2 Macro — `#/macro`
- Files: `pages/macro.js` (291), `pages/market-shared.js`, `ui/grouptabs.js`, `ui/chart.js`, `core/poll.js`.
- Purpose: the macro regime and what it is made of, the S&P's expected move, then twelve views in four groups.
- Auth: guest; nothing changes signed in. Notice: "Not a recommendation. A regime read on the market as a whole, not a view on any individual security, and not advice to change your positioning." (`core/legal.js:36`).
- Sections in render order (`paint`, `macro.js:236-245`): head with Markets tabs; then, from `GET /api/market` (90 s timeout): error card, or a skeleton with "Loading about 40 instruments. This can take up to 30 seconds." (`:240`), or **"The market today, in brief"** (three bullets: lean, breadth and equal-weight, rotation, `:25-31`) and **Macro regime** (label, `h2` regime, Ask Milo, Risk score / 3-month to 10-year curve / VIX, stance, notes, fold "How the score is built, N terms", then "Expected S&P move, from the VIX" with three figures and a "How this works" fold, `:33-49`); then **In depth** (`h2`) with the grouped tabs. Groups (`MGROUPS`, `:224-229`): Breadth and sectors (Breadth, Sector board, Sector strength, Rotation, Themes and pairs), Rates and the economy (Yield curve, Economic data), Cross-asset (Cross-asset, Currencies, Ratios, Correlation and dispersion), Stock maps (Stock maps; one view, no chips). Open: the two top sections and the first view, Breadth.
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Markets tabs | links / select | Read, Macro, Indices | navigate | |
| Ask Milo about the regime | `miloButton` | | drafts "What is driving the macro regime right now, and what would change it?" (`:37`) | |
| How the score is built / How this works | `details` | | disclosure (`:40,48`) | closed. |
| Group tabs x4, sub chips | as 4.1 | see Sections | `grouptabs.js` | State kept per visit (`tabState`, `:252`). |
| Breadth chart | `lineChart` RSP against SPY, 190 px, Measure button | | hover and keyboard crosshair (`:56,216`) | Only when the server sends the series. |
| Yield curve rows | links | 3 month, 5 year, 10 year | `#/instrument/^IRX\|^FVX\|^TNX` (`:64`) | |
| Rotation map | interactive SVG, each sector `g.rr-s` a tab stop (`tabindex=0`, `role=img`) | | hover, focus or tap shows a box with quadrant, strength, momentum; Escape or a tap elsewhere hides it (`:83-135`) | Dots are labelled to avoid overlap (`:96-103`). |
| Rotation table links | links | sector symbols | `#/<SYM>` (`:73`) | |
| Economic series chip xN | `button.chip[data-v2-econ]`, `aria-pressed` | the series label | loads `GET /api/econ/<code>?years=12`, repaints (`:282`) | Default CPIAUCSL (`:253`). No request identity (MC-3). |
| Economic chart | `lineChart` 240 px, Measure | | (`:218`) | |
| Map template chip | `button.chip[data-v2-map]` | the template label | `GET /api/stockmap?template=` (`:283`) | |
| Map tile | `g.tile[role=button][tabindex=0][data-v2-map-sector]` (only when large enough) | symbol and move | drills into a sector (`:284,289`); Enter or Space (`:289`) | |
| All sectors | `button[data-v2-map-back]` | "All sectors" | back to the top map (`:285`) | |
| Open a sector chips | `button.chip[data-v2-map-sector]` | sector names | drill (`:153`) | |
| The full table | `details` | | disclosure (`:154`) | |
| Currency search | `input[name=q]` + "Find" in `form[data-v2-fx]` | placeholder "Find a currency, such as yen" | `GET /api/forex?q=` (`:290`) | No validation or length cap. |
| The five drivers | `details` | | (`:176`) | |
| Cross-asset row | `tr.inst-row[data-v2-inst]`, plus a name link and a sparkline link | | the whole row opens `#/instrument/<SYM>` unless a control inside was pressed (`:281`) | Row click is mouse-only; the name link is the keyboard path (`:278-280` comment). |
| Components | `details` | "Components (n)" | (`:192`) | |
| Ask Milo about implied correlation | `miloButton` | | drafts (`:196`) | |
| Sector Read (per row) | `button.btn-sm[data-v2-sread]`, aria-label "Sector Read for <SYM>" | "Sector Read" | `loadSectorRead` -> `GET /api/sectors/<SYM>/read` (`market-shared.js:19,32-35`; `macro.js:286`) | **Paid** (section 1); "An A Sector Read is written by an AI model when you ask for it, and kept for an hour." (`market-shared.js:20`). |
| Close (read) | `button[data-v2-sread-close]` | "Close" | clears the read (`:287`) | |
| Sector rows | links | `#/<SYM>` (`market-shared.js:16`) | | |
| Try again | `button[data-v2-retry="market"]` | | `retry.market` -> `loadMarket()` (`:272`) | No re-wire. |

- Inputs: the currency search only.
- Tables (columns): Yield curve (Maturity, Now, 20 sessions ago, Change); Rotation (Sector, Quadrant, Strength, Momentum, Change in strength); Currencies per group (Pair, Last, Day, 20 days, Against the 200-day, Reading); Cross-asset per group (Instrument, Last, Day, 5 days, 20 days, Against the 200-day, RSI, 90 sessions); Ratios (Ratio, Reading, 5 days, 20 days, 60 days, Trend); Sector board (Fund, Price, Trend, Bullish above, Bearish below, Rotation, Read); Sector strength (Sector, Day, 1 month, 3 months, 6 months, RSI, Against the 50-day, Against the 200-day); Themes (Name, Day, 1 month, 3 months, Against the 200-day) for themes, breakout candidates and niche industries; Pair trades (Pair, Ratio, z-score 60 days, 5 days, 20 days, Setup).
- Charts: RSP/SPY line, economic series line, rotation map (custom SVG), stock map (SVG treemap with colour mixed from the colour domain), sparklines in Cross-asset and Ratios.
- AI-generated: the Sector Read block (headline, a stance label, paragraphs, `generated()` label) from `/api/sectors/<SYM>/read` (`market-shared.js:23-30`), on a press only.
- States: error card with Try again (`:240`); loading skeleton as above; per-view skeletons for rotation, econ, map, currencies, correlation (`:68,138,146,172,189`); empty: "Rotation is not available" (`:69`), "Stock maps are not available" (`:147`), "Currencies did not load" (`:173`), "No sector is set up for a breakout right now." (`:208`), "Not available right now." (`:189,193`). Views that read only `D.m` (Breadth, Yield curve, Cross-asset, Ratios, Sector strength, Themes) draw empty tables, with no loading or error text of their own, until `/api/market` answers or when it fails (MC-2).
- API: `GET /api/market`, `GET /api/rotation?tail=8`, `GET /api/econ`, `GET /api/econ/CPIAUCSL?years=12`, `GET /api/stockmap[?template=&sector=]`, `GET /api/forex[?q=]`, `GET /api/implied-correlation`, `GET /api/dispersion`, `GET /api/sectors/board`, `GET /api/sectors/{sym}/read`. Refresh: `/api/market` quietly every 60 s in pre, regular and after hours, every 10 minutes otherwise (`:269`).
- Storage: none (module memory).
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| MC-1 | P1 | Trade-structure wording under a page notice that says the page is "not advice to change your positioning": "Strongest against weakest right now: long XLE, short XLU"; a pair table whose Setup column reads "stretched. Mean-reversion long of the ratio (buy X vs Y)" or "trending. Momentum long X / short Y"; a "Breakout candidates" table; breadth note "Long setups are fighting the current." | `macro.js:55,208,210`; server text `app/analytics/sectors.py:238-250,347,380-385` |
| MC-2 | P2 | Six views and the economy view show a blank table or an endless skeleton instead of a state: they read `D.m` with no loading or error branch, and a failed first `/api/econ/CPIAUCSL` sets `D.econ = null`, which is the "loading" value (`!s ? skeleton('chart')`). | `macro.js:52-65,138-143,178-212,258-261` |
| MC-3 | P2 | Late answers win: economic series, stock map, sector drill, back, Sector Read and currency search each set a module value and await with no request counter. | `macro.js:282-290` |
| MC-4 | P2 | No time or delay line on the regime, breadth, cross-asset or board views (only the curve says "Source: Yahoo Finance Treasury yield indices"); `/api/market` carries `generated_at` (`main.py:1730`) but no text on the page shows it. | `macro.js:236-245,64,142` |
| MC-5 | P2 | The Sector Read prints the model's `stance` ("Constructive", "Cautious", "Two-sided") as the label of the read, a directional rating on a fund; the prompt forbids entries, exits and buy/sell wording but not the label. | `market-shared.js:28`; `app/ai.py:2150-2156` |

### 4.3 Indices — `#/indices`
- Files: `pages/indices.js` (68), `pages/market-shared.js`, `ui/chart.js`.
- Purpose: what the major indices say together, the index funds' trend board with an Index Read on request, the long-run regime of each index and growth against the broad market.
- Auth: guest. Notice: "Not a recommendation. Long-run index context, not advice to buy, sell or hold any index fund." (`core/legal.js:36`).
- Sections in render order (`paint`, `indices.js:41-51`): head with tabs; error card with Try again or skeleton "Loading ten years per index" or **What the indices say** (four rows: Secular trend, Dispersion, Furthest from a high, Style, `:16-30`); **Major index funds** (board table + read block, `:46`); **Index regime** (`h2` + Ask Milo + table, `:33-35`); **Growth against the broad market (QQQ / SPY)** with Ratio and 3 months, a note and a chart (`:36-38`). All open.
- Controls: Markets tabs; "Ask Milo about the indices" (`:33`, drafts "What do the major indices say about the market cycle right now?"); per-row **Index Read** `button[data-v2-sread]` and **Close** (`market-shared.js:19,27-29`; handlers `indices.js:58-62`; paid, section 1); fund links `#/<SYM>` (`market-shared.js:16`); index links `#/instrument/<SYM>` (`indices.js:35`); QQQ/SPY chart with Measure (`:49`); Try again `data-v2-retry="indices"` -> `render` (`:68`).
- Tables: Board (Fund, Price, Trend, Bullish above, Bearish below, Rotation, Read); Index regime (Index, Last, 1 year, 3/5/10 years a year, Against 40-week, Against 200-week, Weekly RSI, From the high, Phase).
- AI-generated: Index Read (as Sector Read).
- States: error `failed('The index picture', ..., {retry:'indices'})` (`:45`); loading skeleton (`:45`); board skeleton/empty via `sectorBoard` (`market-shared.js:10-11`); read block loading, error, unavailable with Close (`:25-27`).
- API: `GET /api/indices/board` (`:63`), `GET /api/indices` (`:64`; 60 s timeout), `GET /api/sectors/{sym}/read`.
- Storage: none.
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| IX-1 | P2 | The click handler is added in `render`, and the retry calls `render` again, so a second set of handlers is added; the Index Read request has no counter, so pressing two rows quickly can show the first read under the second row's label. | `indices.js:58-62,68` |
| IX-2 | P2 | No time or delay on any figure: `/api/indices` and the board carry `generated_at`, which is not shown; the board says only "Levels from the prior session's range." | `indices.js:44-47`; `market-shared.js:20` |
| IX-3 | P2 | Index Read prints the model's stance as a label (same as MC-5). | `market-shared.js:28` |

### 4.4 Instrument — `#/instrument/<SYM>`
- Files: `pages/instrument.js` (76), `ui/pricechart.js`, `core/router.js` (`previous`, `parse`), `nav.js` (`pageOf`).
- Purpose: one cross-asset instrument (an index, a yield, a pair, a commodity, a future): five or six tiles and its chart. "A reference series, not a price you could deal at."
- Auth: guest. No notice (X-1).
- Sections (`paint`, `instrument.js:18-42`): head (a "Back to <page>" link when the previous address is a known page that is not another instrument, `:46-51`; label (FX, group or "Instrument"); `h1` "<name> (<label or symbol>)"; Ask Milo "Ask Milo what this is"; about or note); or error card, or chart skeleton; tiles **Last** (with the day move and, for futures after the 6 PM reopen, "since <day>'s settle"), the settled session's own tile, **20 days**, **Against the 200-day** (with the average), **RSI** (with "Overbought territory" at 70 or more, "Oversold territory" at 30 or less, "Mid-range", "Not enough history", `:26`), **From the 52-week high**; chart tools; chart; "A reference series ... Source: Yahoo Finance. Tiles use a year of bars whatever the range." plus a futures note.
- Controls: Back link (`:50`); Ask Milo (`:28`); **Range** `button[data-v2-inst-range]` 1M, 3M, 6M, 1Y, 2Y, 5Y (reloads, `:34,70`); **Style** `button[data-v2-inst-style]` Line, Candles, Area (`chart.set({style})`, `:35,71`); the price chart's own interactions: wheel and pinch zoom, drag pan, crosshair, keyboard arrows, +/-, Home/End (`ui/pricechart.js:1-14`); Try again (`:76`). The chart is drawn with volume when the feed has it and with RSI, MACD and event markers off (`:40`).
- Inputs: none. The symbol is the address segment (any text; an unknown one gives the server's 404 "No history for 'X'.", `main.py:6252-6254`).
- States: error `failed('This instrument', ...)` (`:29`); skeleton (`:29`); fewer than 5 bars: tiles without a chart (`:38`).
- API: `GET /api/instrument?symbol=<SYM>&range=<r>` (`:59`; `main.py:6232`). Spend: no. Late answers dropped by `gen` (`:55,61`).
- Storage: none. `range` and `style` are module variables that outlive a symbol (`:16`).
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| IN-1 | P2 | No as-of time or delay: "Source: Yahoo Finance" only; the tiles say "Last" with no timestamp, though the payload carries `generated_at` and the chart's dates. | `instrument.js:30,37`; `main.py:6295` |
| IN-2 | P2 (low) | "Overbought territory" / "Oversold territory" labels on RSI 70 / 30 read as signals; the same page says it is a reference series. | `instrument.js:26,33` |
| IN-3 | P2 (low) | A range chosen on one instrument carries to the next, and a 5-year view requested on a short-history symbol is shown as is. | `instrument.js:16,59` |

### 4.5 Earnings week — `#/earnings`
- Files: `pages/earningsweek.js` (80), `ui/states.js`, `core/store.js`.
- Purpose: who reports this week, last week or next week among the widely followed names, with consensus and the reader's own names marked.
- Auth: guest; "You follow it" marks come from the open browser or account lists. No notice (X-1; the `earnings` notice belongs to a company's Earnings tab).
- Sections (`paint`, `:44-52`): `h1` "Earnings <last week|this week|next week>" and the week buttons; a summary line ("<week>: N reporting among the M widely followed names Optic checks, K of them index-moving. Open one for its earnings analysis."); one section per weekday (`h2` "<day> <n>" with "Today" and "N reporting"/"None"); rows; "Calendar read <ago>. Dates and consensus from Yahoo Finance. N companies could not be read."; fold "How this works" (session note and method).
- Controls: **Week** `button[data-v2-ew]` "Last week", "This week", "Next week" (`:50`; click -> sets the offset, `history.replaceState` to `#/earnings?week=<n>`, reloads, `:70-75`); each row is a link to `#/<T>/earnings` (`:23`) with: EPS (reported: "EPS 1.23 against 1.10 expected: beat" from `result_short`; coming: "EPS 1.10"; none: "No EPS estimate"), revenue consensus, the session label ("Before the open"/"After the close" when trusted, else "Time not set"/"Time not known"), "Revenue estimate not recorded" with the reason on hover, "Index-moving", "You follow it", "Date not confirmed" (`:15-26`).
- States: loading skeleton `aria-busy` (`:30,51`); error `failed(..., {retry:'week'})` (`:29`); unavailable: the reason (`:31`); empty day: "Nothing scheduled among the names checked." (`:37`).
- API: `GET /api/earnings-week?offset=<-1|0|1>` (`:57`; `main.py:5335`), served from the last build while a new one runs (`main.py:5292-5330`). Spend: no. Late answers dropped by `seq` (`:55,58,60`).
- Storage: none; `?week=` in the address.
- Risks: X-1 (no notice) only; a result word ("beat"/"miss") comes from the server (`result_short`).

### 4.6 Explore — `#/explore`
- Files: `pages/explore.js` (110), `pages/tabs.js`, `core/format.js`.
- Purpose: a reading of what is worth a look, the screens grouped by the question each asks, sectors against the S&P, and cross-asset moves ranked against each instrument's typical day.
- Auth: guest. No notice (X-1), but the first section says "Being on a list is not a recommendation; open a company to research it." (`:39`).
- Sections in render order (`paint`, `:86-93`): head with Discover tabs (Explore, Scan, Insiders, Analysts); unless all three sources failed: **Start with a question** (three cards: "Which stocks have moved the most?", "Which stocks are trading unusually heavily?", "Which stocks have a steady upward trend?", each with a preview of the first three names, "N of M stocks match, ranked <age>", and a "See the full list" button, `:32-45`); **What is worth a look today** (up to three rows: what is screenable, biggest move or "A quiet tape", sector breadth, `:47-57`); **Every screen** (groups with each scan linked and its "looks for" line, `:59-66`); **Sectors** (table Sector, Week, Month, Read; link "The sector board and rotation are on Macro", `:68-76`); **Cross-asset** (list ranked by move against typical day with Ask Milo, `:78-84`). A stale line names any missing source (`:92`) or a full error card with Try again (`:91`).
- Controls: Discover tabs; **See the full list** `a.btn` -> `#/scan?id=<scan>` (`:44`); preview names `a.textlink` -> `#/<SYM>` (`:42`); screen links -> `#/scan?id=<id>` (`:64`); sector links `#/<SYM>` (`:74`); "The sector board and rotation are on Macro" -> `#/macro` (`:75`); cross-asset rows -> `#/instrument/<SYM>` (`:83`); **Ask Milo about the biggest move** (`:82`, drafts "Why is X moving +y% today, and does it matter for stocks?"); Try again `data-v2-retry="explore"` (`:91,109`).
- States: previews: skeleton per card then "Nothing to preview right now." (`:42-43`); catalogue: skeleton, "The ranking is still loading. The screens open now and fill when it finishes.", "The scanner catalogue is unavailable right now." (`:61,63`); sections that have no data are omitted.
- API: `GET /api/scanners`, `GET /api/scanners/groups`, `GET /api/sectors/board`, `GET /api/home` (30 s timeout), `GET /api/scanners/{movers|volume|steady}?limit=3` (`:101-106`). **Spend: yes, through `/api/home`** (H-1).
- Storage: none.
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| EX-1 | P1 | Opening Explore calls `/api/home` only to rank cross-asset moves, which can start the Desk write (H-1). | `explore.js:104`; `main.py:2907` |
| EX-2 | P2 | The Sectors and Cross-asset lists show a move and a "x times its typical day" figure with no time, delay or session line; the heading "What is worth a look today" is the only ranking language. | `explore.js:55,73-84` |

### 4.7 Scan — `#/scan`
- Files: `pages/scan.js` (297), `pages/scan-shortlist.js` (52), `ui/company.js` (`watchButton`), `core/device.js` (`holds`).
- Purpose: three ways to find stocks over one ranked universe (Find stocks in plain words; Named scans; Build a screen) plus a nightly shortlist and a replay of the score.
- Auth: guest for everything free. Reading words the fixed parser cannot read needs an account and spends one Milo message (section 1). Recents and the built screen are stored only while this browser holds the account's things (`holds`, `scan.js:37-38`). No notice (X-1).
- Sections in render order (`paint`, `:182-191`): head with Discover tabs; **Find stocks** (`ask()`, `:94-112`); a mode section headed "Scanners", "Nightly shortlist" or "Build a screen" with a three-button mode switch (`:187-189`); **Does the score work?** (`evaluation()`, `:170-179`). Open: all.
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Discover tabs | links / select | Explore, Scan, Insiders, Analysts | navigate | |
| Describe the stocks you want | `textarea#sc-ask[name=text]`, `maxlength=300`, `rows=2` | placeholder "Strong stocks on the 200-day average right now" | Enter submits, Shift+Enter newline (`:263`); an empty submit focuses the box and toasts "Describe the stocks you want first, in a few words." (`:215`) | |
| Find symbols now | submit `.btn-primary` | "Find symbols now" / "Screening..." | `runAsk` -> `POST /api/screener/ask` (`:210-224,260`) | One at a time (`S.asking`). Can spend (section 1). |
| Ask Milo to help phrase it / Ask Milo about the results | `miloButton` | | drafts a request or a question listing the first 15 symbols (`:98`) | |
| Examples | `details.sc-ex` (open on wide screens, closed on phones, `:93,101`) with chips | six examples (`EXAMPLES`, `:24`) | each chip runs the request at once (`:280`) | A press can spend an account's message. |
| Your recent requests | chips; "Clear" | up to 6 | run again (`:280`); Clear removes `optic.scan.recent.v1` (`:281`) | Keyed by who is here. |
| Edit as filters | `button[data-v2-ask-edit]` | "Edit as filters" | copies the read spec into Build a screen (`:282`) | |
| Mode | segmented `button[data-v2-scan-mode]` | Named scans, Shortlist, Build a screen | switches, updates the address (`:283-287`) | |
| Scan group | `button.chip[data-v2-scan-group]` | group name with a count | runs the group's first scan (`:288`) | |
| Scan | `button[data-v2-scan]`, `title` = what it looks for | scan names (thirteen, `:5`) | `runScan` -> `GET /api/scanners/<id>?limit=25` (`:194-199,289`) | Address becomes `#/scan?id=`. While the ranking builds the page asks again every 5 s (`:200`). |
| Result row | `th[scope=row] a` -> `#/<SYM>`; icon link "<SYM> chart"; **Watch** button (`watchButton`) | | (`:83,89,126`) | Watch toggles the open list (`app.js:247`). |
| Compare the first N | `a.btn-sm` | "Compare the first 4" | `#/compare?t=A,B,C,D` (`:85`) | Passes the top-ranked names to Compare (SC-4). |
| Build a screen: Field | `select[data-v2-flt-field=i]` | the field labels from `/api/screener/fields` | sets the field, clears bounds (`:273`) | |
| Minimum / Maximum | `input[data-v2-flt-min\|max=i]`, `inputmode=decimal`, placeholders "min", "max" | | parse: trims, strips commas, empty is none, non-number marks the box `.bad` (`:266-268`); Run with a bad bound toasts "One of the bounds is not a number, so the screen did not run." (`:204`) | Saved to `optic.screener.v1` on each keystroke (`:252-257`). |
| Remove filter | `button.icon-btn[data-v2-flt-del]`, aria-label "Remove the <label> filter" | x | splices it (`:291`) | |
| Add filter | `button[data-v2-flt-add]` | "Add filter" | adds the first unused field; disabled at the maximum (`:290`) | |
| Reset all | `button.textlink[data-v2-flt-reset]` | "Reset all" | blank spec, refocus Add filter (`:292`) | |
| Also require | checkboxes `data-v2-state` | the state labels | toggles, saves (`:274`) | |
| Sort by / Direction | `select[data-v2-screen-sort\|dir]` | fields; "Highest first", "Lowest first" | saves (`:275-276`) | |
| Run screen | submit `.btn-primary` | "Run screen" / "Screening..." | `runScreen` -> `POST /api/screener` (`:201-209`) | One at a time; a finished result is kept this visit (`SCREENED`). |
| Shortlist | a section in the mode switch | | `loadShortlist` -> `GET /api/shortlist` (`:246-250`); items: symbol link to the chart, "Rising/Falling setup", the setup, state chip, why, "Trigger at N" or "It closed through N", invalidation, supports and conflicts lists, catalysts, "N of M conditions met", volume ratio, older-data note (`scan-shortlist.js:12-24`) | |
| The forward record | table in the shortlist | Name, Setup, Then, Invalidated, Move its way 10 sessions | | `scan-shortlist.js:26-36`. |
| Run the test | `button[data-v2-eval]` | "Run the test" | `GET /api/evaluate` (`:293`; `main.py:4910`) | Replays the score over 220 names; first run is slow; no spend. |
| Ask Milo about this test | `miloButton` | | drafts (`:172`) | |
| Per-horizon bucket tables | `details.more-inline` | "<n> sessions, by score bucket" | | `:177`. |
| Try again | `data-v2-retry="scan"`, `"catalogue"`, `"shortlist"` | | `retry.scan/catalogue/shortlist` (`:245`) | `catalogue` re-renders (SC-3). |

- Inputs: see the table. Bounds are free text with no min/max range checks beyond "is a number"; the box shows `.bad`, no message until Run.
- Tables: scan results (Symbol, Price, then the scan's own columns with a bar in the ranked column where the values spread, Next); screen matches (Symbol, the filter columns, Next); shortlist record; evaluation (Horizon, Composite, Random, 3-month return alone, Against one factor) and bucket tables (Bucket, n, Mean excess, Hit rate, 95% interval).
- AI-generated: "Read by Milo" appears when words were read by the model (`:105`); the shortlist and every table are rule-based.
- States: catalogue skeleton / `failed('The scanner catalogue', ..., {retry:'catalogue'})` (`:189`); scan skeleton "Running the scan" / error / `available:false` with a build bar "N of M symbols screened" (`:80,122`) / "No symbols match this scan right now: ... That is a result, not a failure." (`:127`); stale "The ranking is N hours old, so these results describe an earlier session." (`:123`); screen "Nothing clears every condition. That is a result rather than a failure: the funnel says which bound emptied it." (`:166`); shortlist skeleton, error, "No shortlist yet", "Nothing qualified on that close" (`scan-shortlist.js:41-50`).
- API: `GET /api/scanners`, `/api/scanners/groups`, `/api/scanners/{id}`, `/api/screener/fields`, `POST /api/screener`, `POST /api/screener/ask`, `GET /api/shortlist`, `GET /api/evaluate`.
- Storage: `optic.scan.recent.v1` (up to 6 requests), `optic.screener.v1` (the built screen); both personal keys (`core/device.js:20,27`). Module memory: `ASKED`, `SCREENED`, kept for the visit so Back from a result shows the same answer without asking again (`:26-29`). The address records the state (`remember`, `:32-35`).
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| SC-1 | P1 | Entry and stop language for named stocks: "Rising setup" / "Falling setup", "Armed, waiting", "Trigger at N", "A close below N invalidates it", on a page with no notice; the "not a recommendation or a forecast" sentence sits inside a closed fold. | `scan-shortlist.js:10,14,17-19,47`; `core/legal.js:36` |
| SC-2 | P2 | An address with `?q=<words>` runs the request on load and can spend the opener's Milo message (a guest is refused). | `scan.js:236-238`; `main.py:6537-6566` |
| SC-3 | P2 | After "Try again" on the catalogue error, `render` runs again on the same element and every handler is added twice: one press of Add filter adds two filters, one Remove removes two. | `scan.js:245,258,290-291`; `app.js:280-283` |
| SC-4 | P2 | A ranked list with a one-press "Compare the first 4" and no on-page "not a recommendation" sentence (Explore has one; Scan does not). | `scan.js:85,125-128` |
| SC-5 | P2 | "right now" copy over a ranking that is hours old: the examples and the placeholder say "right now" while the result says "Ranking N hours old". | `scan.js:24,97,124` |

### 4.8 Insiders — `#/insiders`
- Files: `pages/insiders.js` (178), `core/congress.js`, `ui/chart.js` (`mountCharts`).
- Purpose: three public filing records on one page: House members' trades, company insiders' Form 4s and federal contract awards. "A record of what was filed, not a signal: nothing here is ranked by how profitable it looked." (`:122`).
- Auth: guest. No notice (X-1).
- Sections (`paint`, `:117-129`): head with Discover tabs and the sentence above; a symbol box; a three-tab view switch with counts; one `section#iv-panel` at a time: **House trades**, **Insider filings** or **Federal contracts** (the open one is set by `?view=`; default House). Each starts with a coverage line (`cover`, "Partial." when not complete).
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Symbol | `input[name=t]`, `maxlength=10` in `form[data-v2-ins-form][role=search]` | placeholder "NVDA, or blank for everything"; button "Show filings" | upper-cases, loads all three views (`:165`; `:123`) | No typeahead and no symbol validation. Address `?symbol=` pre-fills (`:146`). |
| Clear | `button[data-v2-ins-reset]` | "Clear" | clears the symbol (`:160`) | Only with a symbol. |
| View tabs x3 | `button[role=tab][data-v2-ins-view]` with a count | House trades, Insider filings, Federal contracts | click or ArrowLeft/Right/Home/End (`:153,168-173`) | Count says "Loading", "Failed", "Unavailable", "None" or a number, with "+" when partial (`:107-115`). |
| Transaction | segmented `button[data-v2-ins-side]` | All, Buys, Sales, Other | reloads House (`:154`) | |
| Traded within | `select[data-v2-ins-since]` | Any time, 30 days, 90 days, A year | reloads (`:167`) | |
| Member | `input[name=m]`, `maxlength=80` + "Filter" in `form[data-v2-ins-hform]` | placeholder "Member's name" | sets the member, reloads (`:164`) | |
| Clear filters | `button.textlink[data-v2-ins-hclear]` | | (`:155`) | |
| Chart window | segmented `button[data-v2-ins-days]` | 14 days, 30 days, 90 days | reloads House with `activity_days` (`:156`) | |
| Most disclosed | `button.textlink[data-v2-ins-pick]` per symbol; also each table symbol | the ticker | sets (or clears if the same) the symbol filter for all three views (`:152`) | |
| Filing link | external link | "Filing" | opens the Clerk's PDF (`:70`) | |
| Show | segmented `button[data-v2-ins-show]` | Buys and sells, Buys only, Everything filed | reloads Form 4s (`:157`) | |
| Refresh | `button[data-v2-ins-refresh]` | "Refresh" | `loadI(true)` forces the server to re-read (`:158`) | Calls EDGAR through the server. |
| Row details | `button.ins-rowbtn[data-v2-ins-row]`, `aria-expanded` | chevron "Details of this filing" | opens shares, price, value, filing, code note, accession (`:159`; `:86,89`) | |
| EDGAR link | external link | "Form 4" or "Form 4, amendment" | opens the index page (`:80`) | |
| Award link, USAspending link | external | "Award", "USAspending" | | `:102,103`. |
| Try again | `data-v2-retry="congress\|insiders\|contracts"` | | `:177` | No re-wire. |

- Tables: House filings (Member, Owner, Symbol, Transaction, Amount, Traded, [Close that day with a symbol], Filed, Filing); Form 4s (Symbol, Insider, Transaction, Shares, Price, Value, Traded, Filed, Filing); Awards (Awarded, Recipient, Agency, Amount, Award). Chart: disclosed trades per day (custom SVG bars, buys, other, sales; legend line, `:35-43`).
- States: per view: skeleton, `failed(..., {retry})` (`:48,76,96`), partial coverage line, "No House trades match[ in X]. An absence of a disclosure, not evidence that nothing was traded." (`:58`), "No House filings have been read yet." (`:58`), "Nothing matching in what has been read." (`:90`), `available:false` reasons (`:78,98`). A symbol's Form 4 history keeps reading in rounds up to 9 (`:137`).
- API: `GET /api/congress`, `GET /api/insiders/latest`, `GET /api/contracts`. Spend: no. Late answers dropped per view by `seq` (`:131-141`).
- Storage: none.
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| IS-1 | P2 (low) | Buys and sales are coloured green and red ("up"/"down") and a "Buys only" filter is offered, which reads as a signal despite the sentence under the heading; no notice. | `insiders.js:20,68,82,87,122` |
| IS-2 | P2 (low) | The ticker box has no typeahead or validation (Analysts and Compare have it), so a company name gives empty results worded as "no House trades match in <text>". | `insiders.js:123,165` |

### 4.9 Analysts — `#/analysts`
- Files: `pages/analysts.js` (80), `ui/table.js`, `ui/typeahead.js`.
- Purpose: what each firm did to its rating and price target, across the covered names or for one symbol.
- Auth: guest. No notice (X-1).
- Sections (`paint`, `:40-51`): head with Discover tabs; one section "Analyst actions[: <T>]" with a search form, three segmented filters and the table (or states).
- Controls: **Symbol** `input[name=t]`, `maxlength=24`, `data-v2-ta` (typeahead), placeholder "Symbol, such as NVDA" + **Search** (`:45,76`); a typeahead pick loads at once (`v2:ta-pick`, `:75`); **All names** `button[data-v2-an-clear]` (`:72`); **Show** `button[data-v2-an-show]` All, Upgrades, Downgrades, Initiations, Target raised, Target lowered (`:12,69`); **Rating** `button[data-v2-an-rating]` Any, Buy, Hold, Sell (`:13,70`); **Window** `button[data-v2-an-days]` Day, 7 days, 30 days (+ Year for one symbol) (`:42,71`); sortable column headers `button.th-sort[data-v2-sort="an:<key>"]` (`ui/table.js:28-32`; handler `:73`); symbol links `#/<T>`; Try again `data-v2-retry="analysts"` (`:80`).
- Table columns (`COLS`, `:16-24`): Date (with age), Symbol, Analyst, Prior target ("New", "Not given", number; hidden on phones), Target (with an up/down arrow), Action (coloured), Rating (class `rt-<class>`, title "From <prior rating>"). Default sort: Date descending.
- States: skeleton (`:29`), `failed('The analyst actions', ..., {retry:'analysts'})` (`:28`), lead line variants including "Analyst actions are loading for the first time. They appear here when they finish." and "Nothing on <T> matching. A longer window, or All under Show, may find more." (`:31-33`); table empty "Nothing to show." (`ui/table.js:34`).
- API: `GET /api/analysts/latest?days=&show=&rating=` or `GET /api/analysts/<T>?limit=200&...` (`:57`; `main.py:6489,6501`). Spend: no. Late answers dropped by `seq` (`:54,58`).
- Storage: none (`Q` and `sort` are module variables that outlive a visit).
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| AN-1 | P2 | Third-party Buy/Hold/Sell ratings and target moves are listed, filterable by rating and coloured, with only a date note ("when Yahoo Finance recorded the firm's action") and no statement that they are the firms' opinions and not Optic's; no notice. | `analysts.js:13,22-23,37,49` |

### 4.10 Compare — `#/compare`
- Files: `pages/compare.js` (294), `ui/bars.js`, `ui/score.js`, `ui/chart.js`, `core/store.js`.
- Purpose: two to four stocks or funds side by side, ranked on three horizons that are scored separately, with Optic's take, how they have moved, where each leads and a metric table. One request, only when the reader presses Compare.
- Auth: guest; recents from this browser or the account (`store.recent`, `:152`). No notice (X-1).
- Sections in render order (`paint`, `:223-237`): `h1` "Compare" and its sub-line ("... The three horizons are scored separately, so a name can lead one and trail another. That disagreement is the useful part."); **Choose tickers** (form, "Recently viewed" chips or "Nothing is fetched until you press Compare.", and after a result the three horizon cards "Horizon: <h>" with their basis and "These are Compare's own scores ... so their numbers differ from these."); result region (`aria-live`): loading card, error card, or **Optic's take**, **How they have moved**, **Where each name leads**, **Side by side**. Open: all.
- Controls:

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| Ticker N | `input[data-v2-cmp-input=i][data-v2-ta]`, `maxlength=24`, `autocapitalize=characters` | placeholder "Ticker 1", title "A ticker, or a company name" | typing marks the result stale when the set differs (`:267-272`); a typeahead pick fills it and moves to the next empty box (`:274-278`) | 2 to 4 boxes. |
| Remove ticker | `button.icon-btn[data-v2-cmp-drop]` | x, aria-label "Remove ticker N (SYM)" | removes it (`:284`) | Only with more than two boxes. |
| Add ticker | `button[data-v2-cmp-add]` | "Add ticker" | adds a box up to 4 (`:283`) | |
| Compare | submit `.btn-primary` | "Compare" / "Comparing..." | `run()` -> `GET /api/compare?tickers=` (`:239-255,266`) | Disabled while running. `#/compare?t=A,B` runs on open (`:292`). |
| Recently viewed | `button.chip[data-v2-cmp-pick]` | up to 6 symbols | fills the first empty box (`:285-289`) | |
| What each row measures | `button[data-v2-cmp-means]`, `aria-pressed` | "What each row measures" / "Hide what each row measures" | toggles the definitions under each row (`:282`; `:209`) | |
| Compare <set> / Try again | `button[data-v2-cmp-again]` | "Compare AAPL, MSFT" / "Try again" | `run({force})` (`:281`) | Shown when the boxes differ from the result, or on an error (`:232-233`). |
| Ask Milo about this comparison | `miloButton` | | drafts "Compare X, Y. <headline> Which would you look at first for my timeframe, and what is each one's biggest risk?" (`:166`) | The whole table's figures go as context (`miloCompare`, `:112-143`). |
| Ticker header links | links | each name | `#/<T>` (`:211`) | |
| Chart | `lineChart` indexed to 100, up to 4 lines, Measure button | | (`:186-190`) | |

- Inputs: ticker boxes only; names are upper-cased and de-duplicated (`wanted`, `:147`); fewer than two gives "Give at least two tickers." (`:241`). Keyboard: Enter submits the form; typeahead keys.
- Tables and bars: horizontal bars per horizon (`hbars`, `:200`); the metric table: three horizon rows, then 22 metric rows in six groups (Where it trades; Momentum and trend; How much it moves; What it costs; The multi-year record; Optic's own score; `GROUPS`, `:17-46`) with a dot on the leader of a row where one direction is better (`leader`, `:65-79`).
- AI-generated: none ("no model call", `:4`; `compare.take` is "Derived, not written", `app/analytics/compare.py:474-476`).
- States: loading card "Pulling X and Y in full. The same analysis the Options and Investing tabs run, for each name." (`:231`); error "Not compared" with the server's reason and per-name failures (`:232`); stale banner "These results are for <set>. Press Compare for <set>." (`:233`); per-cell "n/a, <why>" (`:49`); "Could not load: <T> (<reason>)." (`:218`).
- API: `GET /api/compare?tickers=A,B[,C,D]` (`:245`; `main.py:5360`), cached 5 minutes, `force` on Try again, invalidated on failure (`:247-250`). Spend: no (up to four full swing snapshots server-side). Late answers dropped by `seq` (`:243,249`).
- Storage: none; inputs, result and `showMeans` are module variables kept for the session ("as the classic page keeps STATE.compare", `:146`); the address is rewritten to `#/compare?t=...` after a good run (`:252-253`).
- Risks seen in code:

| ID | P | Risk | Where |
|---|---|---|---|
| CP-1 | P1 | A ranking that reads as a pick: "Optic's take", a headline such as "X leads every horizon.", per-horizon winners, "best", "#2", green and red 0-100 scores with filled lines; the statement that the scores have not been shown to predict returns is only in what Milo is sent, not on screen; no notice. | `compare.js:85-97,165-170,214,141`; `app/analytics/compare.py:551-566`; `core/legal.js:36` |
| CP-2 | P2 | No computed-at time or price date on screen ("Price: Last close." names no date); `generated_at` goes to Milo only. | `compare.js:19,130` |
| CP-3 | P2 | The Ask Milo draft asks "Which would you look at first for my timeframe, and what is each one's biggest risk?", inviting a preference. | `compare.js:166` |
| CP-4 | P2 (low) | "Optic's own score: Composite" can differ from a Dossier's Optic Score for the same name; the page says so once, under the horizon cards. | `compare.js:44-45,230` |

---

## 5. Cross-page risks (referenced above as X-n)

| ID | P | Class | Risk | Where |
|---|---|---|---|---|
| X-1 | P1 | (a) advice wording | Only Macro, Indices and Read carry a per-page notice. Home, Explore, Scan, Insiders, Analysts, Compare, Instrument and Earnings-week have none, and three of them (Scan shortlist, Compare, Home Contracts) show ranked or trade-shaped output. The shell footer line is the only statement there. | `core/legal.js:36-41`; `app.js:163-177`; `ui/shell.js:85` |
| X-2 | P2 | (c)(d) abandoned code | A second, unrouted Home page (`render`, `loadHome`, `welcome`, `starters`, `modes`, `scene`, `strip`, the legacy `retry`) is still exported and imported for its blocks, and the workspace keeps handlers and state for controls it no longer draws. A change to one copy can silently miss the other. | `home.js:22-31,461-496,499-728`; `app.js:60`; `workspace.js:715,724,853-858,1056-1062,1105` |
| X-3 | P2 | (c) duplicates | The same data is drawn twice in different words: "What matters today" (Home, `eventsBlock`) and "Today's priority" (Read, `priority()`); the economic calendar (Home table, Read timeline); the sentiment gauge (Home Market conditions, Read Fear and Greed). Two things are called "Optic Desk": Home's panel is the day's `morning_desk` (written on the first request), Read's section is the scheduled edition (`DESK_EDITION_AUTO` is off by default). | `workspace.js:279-298,408-434`; `read.js:27-40,114-121,170-179,221-257`; `main.py:4113-4121` |
| X-4 | P2 (low) | (c) duplicates | "Rank the day's moves against each instrument's typical day" exists twice with the same constant 1.6 (`RANGE_PER_SIGMA`): Home's Questions and Explore's Cross-asset. | `core/market-questions.js:11-26`; `explore.js:13-28` |
| X-5 | P2 | (c) conflicting | The 11 sector funds and 3 index funds come from three endpoints on three pages that can disagree at one moment: Home's heatmap (`/api/market`), Home's trend board (`/api/trends/board`, which states price kind and delay), and Macro, Explore and Indices (`/api/sectors/board`, `/api/indices/board`). | `workspace.js:322,396`; `macro.js:266`; `explore.js:103`; `indices.js:63` |
| X-6 | P2 | (c) conflicting | "Regime" names three models: Home "Market conditions" and Macro "Macro regime" (the macro risk score, -100 to +100); Read "Market regime" (the brief's `index_regime`, a different scale and weights); Indices "Index regime" (cycle phase per index). A reader sees different numbers under one word. | `workspace.js:354-376`; `macro.js:33-49`; `read.js:181-190`; `indices.js:32-35` |
| X-7 | P2 (low) | (c) conflicting | One expected-move figure carries three label sets: Home "Priced, as one day / Typical day lately / Priced against typical"; Macro "Options price, as one day / Its typical day lately / Priced against typical"; the unrouted Home "about N points either way". | `workspace.js:385-387`; `macro.js:47`; `home.js:86-91` |
| X-8 | P2 | (c)(d) handlers | A `retry` entry that calls `render` again re-runs `wire(main)` on the same element, so every listener is doubled: Read (paid buttons), Indices (Index Read), Scan (filters double-add and double-remove). | `read.js:324,326`; `indices.js:58,68`; `scan.js:245,258,290-291`; `app.js:280-283` |
| X-9 | P2 | (e) states | A failed fetch is drawn as an empty answer or as nothing: Read priority and catalyst, Macro's tables and economic series. | `read.js:117,125-126`; `macro.js:52-65,138-143,178-212` |
| X-10 | P2 | (f) time and source | No as-of time or delay line on Macro, Indices, Explore (sectors, cross-asset), Instrument or Compare, although each payload has `generated_at`, `as_of` or a price date. Home panels do carry one; Watchlist, Economy, Company news and Latest scan alerts have none in the footer. | `macro.js:236-245`; `indices.js:44-47`; `explore.js:73-84`; `instrument.js:37`; `compare.js:19`; `workspace.js:336,480,515,553` |
| X-11 | P2 | (b) late answers | `core/api.js` has no abort, and several controls change a setting and await with no request counter: Home Earnings week, Quote range, Contracts side and expiry; Macro economic series, map, drill, Sector Read, currencies; Indices Index Read; Read catalyst filters. Pages with a counter: Instrument (`gen`), Earnings week, Insiders, Analysts, Compare, Scan (`S.scanId`), Read headline search, the typeahead. | `workspace.js:902-909`; `macro.js:282-290`; `indices.js:60`; `read.js:301-306`; `instrument.js:55`; `earningsweek.js:55`; `compare.js:243` |

## 6. All risks, ranked

| P | ID | One line |
|---|---|---|
| P1 | H-1 / EX-1 | Opening Home or Explore calls `/api/home`, which can write the Desk with a model call (first request of the day, background rewrites up to 12 a day); anonymous, bounded only by disk claims. `workspace.js:290,343,357`; `explore.js:104`; `main.py:2907,2955-2983,3015-3028` |
| P1 | MC-1 | Macro prints "long X, short Y" and pair setups ("Mean-reversion long ... (buy X vs Y)") under a notice saying it is not advice to change positioning. `macro.js:55,208,210`; `app/analytics/sectors.py:238-250,380-385` |
| P1 | SC-1 | Scan shortlist gives "Trigger at N" and "A close below N invalidates it" for named stocks, no notice, disclaimer in a closed fold. `scan-shortlist.js:14,17-19,47` |
| P1 | CP-1 | Compare ranks names ("leads every horizon", "best", "#2", green/red scores) with no on-screen note that the scores have not been shown to predict returns. `compare.js:85-97,165-170,214,141` |
| P1 | X-1 | Eight of the eleven routes here have no per-page notice. `core/legal.js:36` |
| P2 | H-2 | Desk freshness copy fits only the edition block; the footer time is the page's build time, not when the note was written. `workspace.js:75,296`; `main.py:2937-3030` |
| P2 | H-3, MC-3, IX-1, RD-3 (X-11) | Last answer wins when a setting changes during a load. |
| P2 | X-8 | Retry doubles every listener (Scan Add filter adds two). `scan.js:245,258,290`; `read.js:324` |
| P2 | X-9, MC-2, RD-2 | Failures drawn as empty, blank tables, an endless skeleton. `read.js:117,125`; `macro.js:138-143` |
| P2 | X-10 | No as-of time on five pages. |
| P2 | SC-2 | `#/scan?q=` spends an account's Milo message on open. `scan.js:236-238` |
| P2 | H-4, X-2 | Unrouted Home and dead handlers; the first Follow removes the first-visit band; "Done" unreachable. `workspace.js:819,1186-1189` |
| P2 | H-11 | Home trends panel's "The full sector board" link opens a Dossier for `MARKET` (should be `#/macro`). `home.js:448` |
| P2 | H-5 | Linked-ticker box fails silently, keeps `BRK.B`, turns "Apple" into `APPLE`. `workspace.js:931-948` |
| P2 | H-6 | Ticker buttons in Home tables relink panels instead of opening the company. `workspace.js:261,451,464,477` |
| P2 | H-8 | Briefing sends followed and held symbols; the server keeps the names with a time. `workspace.js:303`; `main.py:2024` |
| P2 | H-9, MC-5, IX-3 | Green/red market score with no validation note; Sector/Index Read stance labels. `workspace.js:367`; `market-shared.js:28` |
| P2 | `biz` | "Valuation: attractive/stretched" beside a letter grade. `workspace.js:655`; `app/research/quality.py:77` |
| P2 | AN-1, SC-4 | Third-party Buy/Hold/Sell lists and a one-press "Compare the first 4" with no opinion/recommendation sentence. `analysts.js:13,37`; `scan.js:85` |
| P2 | X-3, X-5, X-6 | Duplicate or conflicting renderings of calendar, priority, sector funds and "regime". |
| P2 (low) | X-4, X-7, IS-1, IS-2, IN-2, IN-3, CP-4, RD-4, H-10, `value`, `gex`, `own` | Minor duplicates, colour on filings, RSI words, module-level state, skeleton flash, cadence copy. |

## 7. Method and limits

- Read in full: `workspace.js`, `home.js`, `read.js`, `macro.js`, `indices.js`, `instrument.js`, `earningsweek.js`, `explore.js`, `scan.js`,
  `scan-shortlist.js`, `insiders.js`, `analysts.js`, `compare.js`, `market-shared.js`, `tabs.js`, `grouptabs.js`, `strips.js`,
  `sections.js`, `market-questions.js`, `homelink.js`, `core/api.js`, `core/store.js`, `core/poll.js`, `core/prefs.js`, `ui/states.js`,
  `ui/typeahead.js`, `ui/table.js`, `app.js`, `nav.js`, `router.js`. Read in part: `ui/milo.js` (button, `panelFigures`, `openMilo`,
  starters), `ui/chart.js`, `ui/pricechart.js`, `ui/glossmark.js`, `ui/term.js`, `core/device.js`, `core/legal.js`, `core/track.js`,
  `static/v2/css/pages.css` rules named in the text.
- Server side: only the routes named above, and for each whether an `ai.*` call is reachable. `app/analytics/*` text was read only
  where cited (`compare.py`, `sectors.py`); the wording of other server-supplied sentences (`why`, `reading`, `stance`, `action`, `note`,
  the shortlist's `why_included`, `/api/priority` rows) was not audited here.
- Not done: no rendering, no network, no run. A statement about visibility cites the CSS rule, not a screenshot. The Milo panel, palette,
  shell, Settings and the other routes are other sections' work.
- Counts: 11 route entries (Home plus ten) and 27 Home panel entries, 38 in all. Controls: 149 rows in the ten control tables (Home 32, What matters today 7, Sector heatmap 2, Earnings this week 4, Contracts 5, Read 23, Macro 24, Scan 26, Insiders 16, Compare 10) and about 73 more named in the inline lists of the other entries, so about 220 control kinds. A repeated element (eleven heat tiles, up to 5 recent chips, N result rows) is one control kind.
