# Registry C: the Dossier (one company or fund), v2 front end

Evidence label: **Source** only. Everything below was read from code in `~/Optic/wt-ultra` (branch
`post-demo-ultra`, HEAD `fce3e71`; `git status --short static app tests` printed nothing, so the code was clean when read).
Nothing was rendered, no server was started, no request was made, no file in the worktree was touched. Where a statement
says what a reader sees at a given moment it is an inference from the code and is marked "by source". Where I cite a
measurement made by another session (`docs/post-demo-ultra/BUG_REGISTER.md`, rows marked Rendered there) I say so; I did not
re-verify it.

Citation form: `file:line`. Front-end files are under `static/v2/js/` and named bare when the name is unique
(`dossier.js`, `options.js`); others carry their folder (`ui/states.js`, `core/api.js`). Server lines are `app/main.py:NNNN`
unless another file is named. "Spend" means a call to the Anthropic API. IDs: `F-DOSSIER-nn` for entries, `FR-`, `OV-`, `CH-`,
`OP-`, `IN-`, `ER-`, `FI-`, `NW-`, `SH-` for controls, `R-xx-n` for risks (priority P0/P1/P2 as defined in directive 00 and
quoted in `BUG_REGISTER.md`: P0 advice behaviour, broken core functions, incorrect financial data, security; P1 simplicity,
Dossier usability, consistency, accessibility, first use; P2 polish). Risk classes (a) to (g) are the ones in the brief:
(a) advice wording, (b) stale-response races, (c) duplicate or conflicting implementations, (d) control without handler or
handler without control, (e) missing loading/error/empty state, (f) figure without time or source, or a fabricated-looking
fallback, (g) excessive reading on the default Overview.

## 0. Scope map

| Route | View id (`core/router.js`) | Module(s) | Tab label (`nav.js:19-27`) |
|---|---|---|---|
| `#/<SYM>` | `overview` (default, `router.js:43`) | `pages/dossier.js`, `pages/overview-research.js`, `pages/thesis.js` | Overview |
| `#/<SYM>/chart` | `chart` | `pages/chart.js`, `pages/chart-widgets.js`, `pages/chart-studies.js`, `pages/chart-chrome.js`, `ui/pricechart.js`, `ui/chartread.js` | Chart |
| `#/<SYM>/options` | `swing` | `pages/options.js`, `pages/options-panels.js`, `pages/options-picker.js`, `pages/setups.js` | Options |
| `#/<SYM>/investing` | `long` | `pages/investing.js`, `pages/valuation-scenarios.js`, `pages/dcf.js`, `core/dcf-fields.js` | Investing |
| `#/<SYM>/earnings` | `earnings` | `pages/earnings.js` (imports `historyRatio` from `dossier.js:151`) | Earnings |
| `#/<SYM>/financials` | `financials` | `pages/financials.js` | Financials (dropped for a fund, `dossier-frame.js:162`) |
| `#/<SYM>/news` | `news` | `pages/news.js` | News |
| `#/<SYM>/sheet` | `sheet` | `pages/sheet.js` | none: not a tab, reached from "Export" (`router.js:41-42`) |

Shared by all seven tabs: `pages/dossier-frame.js` (header, actions, tab strip, live price), `pages/tabs.js`, `ui/company.js`
(Watch, the ⋯ menu), `ui/sections.js` (folds), `ui/drawer.js`, `ui/term.js`, `ui/glossmark.js`, `core/glossary.js`, `core/prefs.js`,
`core/instrument.js`, `core/poll.js`, `core/marketTime.js`, `core/finviz.js` (sentence builders for Financials and Earnings),
`core/format.js`.

Route facts (`core/router.js:20-44`): the first path segment is upper-cased; `BRK.B` and `BRK/B` become `BRK-B` (`:36-38`); a
symbol that fails `^[A-Z0-9.^=-]{1,12}$` is the `notfound` view (`:39`, drawn by `bridge.js:17-24`: "Page not found", "That address is
not a page", Search and Go to Home); `#/<SYM>/<anything else>` falls back to the Overview with the address left as typed
(`:43`, risk R-FR-7). The hash `#/dossier` is a different page (`dossierstart.js`) and is not audited here.

How a Dossier page mounts (`app.js:135-196`): the page module is fetched lazily (`app.js:51-63`); a later route wins a race
(`const my = ++SHOW`, `:140`; `if (my !== SHOW) return`, `:145,149`); the previous page's `dispose()` runs (`:151`); the drawer
and palette are closed; a fresh `div.page-view` is made; `page.render(view, route, app)` is called and any thrown error draws
"This page did not load" with the message and a link (`:185-188`); the first `h1` is focused and the title is announced
(`:194-195`). A per-area legal notice is placed by a MutationObserver (`app.js:165-176`): after the page's first direct-child
`section.section`, or **appended at the end** when the page has none. `core/legal.js:36` gives notices to `swing`, `long`,
`earnings` among these views, and to none of `overview`, `chart`, `financials`, `news`, `sheet`.

## 1. The "Show advanced analysis" switch, traced

This is the control the owner's Phase 06 directive calls out (it must replace the simple content, not append). Findings first,
evidence after.

- **It does not replace anything.** Every section the Overview can show is rendered at every setting. The switch changes
  three things: whether two `details[data-adv]` folds start open, how many "Coming up" events are listed, and the global
  knowledge level that other pages and Milo read. The label never changes. Source, below.
- **Where it is drawn:** `advSwitch()` (`dossier-frame.js:119-122`) is a `button.adv-switch[role=switch][aria-checked]` with the
  fixed text "Show advanced analysis" and a `title` ("Opens Advanced research and the full case for and against on this page, and
  has Milo answer at the Advanced level"). Only `dossier.js` imports it (`dossier.js:23`), and only the main Overview draw
  places it (`dossier.js:353`, inside `.dh-tools` in the sticky `.dstick`). The unlisted-ticker draw omits it (`:349`). No other
  tab shows the switch.
- **Click path:** delegated listener, `dossier.js:421` → `prefs.setAdvanced(!prefs.advancedOn())`.
- **Where the state is stored:** `localStorage["optic.knowledge.v1"]` (`prefs.js:8`), one of `simple, literate, advanced,
  professional, adaptive` (`prefs.js:9`), default `literate` (`prefs.js:10,110`). `advancedOn()` is true at rung 2 or 3, so
  "professional" also reads as on (`prefs.js:111`). Turning on stores the rung it left in `optic.knowledge.basic.v1` and sets
  `advanced`; turning off restores that rung unless it is itself advanced or higher, else `literate`; both set
  `optic.knowledge.asked.v1 = "1"` and emit `knowledge` (`prefs.js:118-124`). Failures to write are swallowed (`prefs.js:36-37`).
- **Repaint:** `prefs.onChange` registered in `render()` (`dossier.js:384`) sets `advMoved = true` and calls `paint()`; `paint()`
  reads `prefs.advancedOn()` into the context (`dossier.js:343`) and, because `advMoved` was set, lets the `data-adv` folds follow
  the switch instead of keeping what the reader had opened (`dossier.js:333,366`).
- **What it opens or changes on the Overview:**
  1. `details.cs-fold[data-adv]` "Show the case for and against (N for, M against)" gets `open` (`overview-research.js:468`).
  2. `details.adv-fold[data-adv]` "Advanced research" gets `open` (`overview-research.js:757`).
  3. `events()` keeps 8 instead of 4 "Coming up" rows and, only then, includes expiry, COT and Opex rows (`overview-research.js:209-224`,
     called from `nextSection`, `:477`).
  Nothing is removed at either setting: the Advanced research section is always the last section (`dossier.js:360`), folded when off.
  Another session recorded the effect as Rendered (BUG-001: words 1,384 to 2,063, height 5,994 to 8,792 px at 1440, no section
  removed); I did not re-measure it.
- **A second, dead mechanism on the same page:** `sections(main, 'overview', { levels: { 'advanced research': 2 } })`
  (`dossier.js:387`) hands `ui/sections.js` a rung for a heading containing "advanced research", but `find()` only lists a
  `section.section` that has a direct `h2` or `.section-head h2` (`sections.js:49-52`) and the Advanced research section has
  neither (its title is a `span.t-h2` inside a `summary`, `overview-research.js:758`). By source the entry matches nothing: that
  section is never tagged "Advanced", never listed in the Panels chooser and not touched by Expand all or Collapse all.
- **Other readers of the same key** (so the one switch is also each of these): `sections.js:53,17` (rung → which sections start
  folded: Investing `investing.js:307` folds "The multiple against its own history" and "Valuation and accumulation levels" below
  rung 2, Earnings `earnings.js:237` folds "What options price for the report"); `glossmark.js:30-33` (auto glossary marks are off at
  Professional); `ui/milo.js:506-512` (the Milo "Level" select, five options, writes it with `prefs.setKnowledge`, `milo.js:1236`) and
  `milo.js:838` (`mode: prefs.knowledge()` posted to `/api/chat`); `pages/settings.js:145,288` (the same state, labelled "Advanced
  answers from Milo"); `pages/tracker.js:120`; `pages/home.js:493,632,708` and `pages/workspace.js:1058,1105` write the key
  directly (no `knowledge` event). So one preference has at least four names and several entry points (BUG-002; risk R-FR-1).
- **Not stored per ticker, not per tab, not synced to the account** by anything in this section: it is one browser key.

## 2. Entries

---

### F-DOSSIER-00 Shared frame: header, actions, tabs, section chrome — every `#/<SYM>...` route except Sheet

- **Files:** `pages/dossier-frame.js`, `pages/tabs.js`, `ui/company.js`, `ui/symbols.js`, `core/poll.js`, `core/marketTime.js`,
  `core/instrument.js`, `ui/sections.js`, `ui/drawer.js`, `ui/term.js`, `ui/glossmark.js`, `core/glossary.js`, `core/prefs.js`, `nav.js`.
- **Purpose:** one company header (symbol, name, price and how fresh it is, Weinstein stage on the Overview, actions), the tab strip
  that is the only place the seven pages are listed, and the folding, jump and glossary chrome the long tabs share.
- **Auth:** guest sees everything. Signed in: the Watch button writes to the account's lists (`store.follow` and `unfollowEverywhere`, `company.js:45-48`),
  guests' go to this browser (`store.js`, not audited here). Alert and Compare are links to other pages. No owner-only control.
  (The whole v2 app can be closed to non-owners, `app.js:136`; not Dossier-specific.)
- **Sections in render order:** header (`dossier-frame.js:131-158`) → actions inside it (`:106-113`) → tab strip (`:163-166`) → on the
  Overview only, the `.dh-tools` row with the advanced switch (`dossier.js:353`) → the page body. The header is sticky as part of
  `.dstick` on all tabs except Chart, which draws header and tabs as plain blocks (`chart.js:591`).

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| FR-01 Logo | image, decorative | none (`alt=""`, `aria-hidden`) | `<img src="/api/logo/SYM">` (`ui/symbols.js:30-33`); an error leaves the initial letter (`symbols.js:41-44`) | skipped for symbols failing `LOGO_SYM` or in `NO_LOGO` |
| FR-02 Heading | h1 | SYMBOL, name, hidden ", Overview" etc. | focus target on arrival (`app.js:194`) | `dossier-frame.js:142` |
| FR-03 Price block | read-only text | price, change and %, `priceWhen`, extended print | refreshed in place every 20 s by `livePrice` (`dossier-frame.js:79-101`) | cadence and pause rules in the API section |
| FR-04 Stage label | button (Overview only) | "Stage 3 · Topping" plus a tag such as "breakdown" | `term('stage:SYM')` opens the definition popover (`dossier-frame.js:127`, `ui/term.js:74-78`) | text from `/api/stage`; plus "Replayed on history" from `/api/validation` (`dossier.js:320-326`) |
| FR-05 Explain | button (Overview only) | "Explain" | drafts a Milo question, nothing sent (`dossier-frame.js:128`; `milo.js:1042`) | question text `OR.stageWords(...).ask`, `overview-research.js:776` |
| FR-06 Alert | link | "Alert" | `#/alerts?symbol=SYM` (`dossier-frame.js:109`) | page is another section |
| FR-07 Compare | link | "Compare" | `#/compare?t=SYM` (`:109`) | |
| FR-08 Export | link | "Export" | `#/SYM/sheet`, `title="A printable research sheet"` (`:109`) | four names for one page: Export, Export research sheet, Research sheet, Print or save as PDF |
| FR-09 Watch | toggle button | "Watch" or "Watching" | `data-v2-watch` → `toggleWatch` (`app.js:247`, `company.js:40-55`): follows or takes it off every list, toast with Undo | `aria-pressed`; all Watch buttons follow list changes (`app.js:306-312`) |
| FR-10 Ask about SYM | button | "Ask about SYM" | drafts "What is the case for SYM right now?" into Milo (`dossier-frame.js:110`) | context string names the tab |
| FR-11 More actions | `details.menu` | ⋯ (`aria-label="More actions for SYM"`) | closes on outside click or Escape (`app.js:286-294`) | items below |
| FR-11a Set an alert | link, phone only | "Set an alert" | `#/alerts?symbol=SYM` (`company.js:7`) | `.menu-phone` |
| FR-11b Compare | link, phone only | "Compare" | `#/compare?t=SYM` | |
| FR-11c Export research sheet | link, phone only | "Export research sheet" | `#/SYM/sheet` | |
| FR-11d Show on Home | button | "Show on Home" | `linkHome(sym)`, toast, goes Home if not there (`app.js:248-255`, `company.js:8`) | |
| FR-11e Copy ticker | button | "Copy ticker" | `navigator.clipboard.writeText` (`app.js:215-232`, `company.js:9`) | toast on refusal |
| FR-11f Copy price and time | button | "Copy price and time" | copies the price as on screen with its time, or says there is none yet (`app.js:215-232`; selector `.dhead .dh-price`, `company.js:10`) | |
| FR-12 Tab links | links ×7 | Overview, Chart, Options, Investing, Earnings, Financials, News | `hrefFor(view, sym)` (`tabs.js:16-18`); the press animates first (`app.js:234`, `ui/motion.js:89`) | Financials omitted for a fund (`dossier-frame.js:162`); `aria-current="page"` |
| FR-13 Phone view selector | select | label "SYM Dossier", options = tabs | `change` sets `location.hash` (`app.js:295-300`; markup `tabs.js:11-14`) | CSS shows it under 640 px (`tabs.js:7-10`) |
| FR-14 Section chips | buttons | section titles, cut at 28 characters (`sections.js:81-90`) | `openSection` opens a folded or hidden section and scrolls (`sections.js:134-144,155`) | strip drawn at six or more shown sections (`sections.js:93`); Overview, Investing, Earnings; not Options groups, not Financials (`strip:false`) |
| FR-15 Expand all / Collapse all | buttons | "Expand all", "Collapse all" | write every shown section's open state (`sections.js:156-160`) | bar drawn at four or more sections (`sections.js:93`); disabled when nothing to do (`:117-120`) |
| FR-16 Panels | `details.menu` | "Panels", count "N off" | per-section checkbox hides or shows a section (`sections.js:168-174`); "Show every section" button (`:104,161`) | stored in this browser |
| FR-17 Section fold | button in every heading | arrow, `aria-label` "Fold X" / "Open X" | `setOpen` (`sections.js:126-131,163-166`); the heading itself is also a target except over a link, button, term or summary | `data-sec-fold` |
| FR-18 Drawer | modal dialog | kicker, title, body; "Close" icon button | Close button, scrim click, Escape (`ui/drawer.js:49-52`, `trapFocus` `:59`); focus returns to the opener or its twin (`:115`, `:16-26`) | used for chart marks and fund answers on the Overview |
| FR-19 Term | button | any defined word, dotted | click, Enter or Space opens a popover with the definition, an illustration if one exists, "Explain this with Milo" and "Close" (`ui/term.js:116-136,146-152`); hover or keyboard focus shows a tip after 250 ms (`:138-145`); Escape closes (`:154`) | definitions from `core/glossary.js`, `BASICS`, `STATS`, live ones via `defineLive` |
| FR-20 Auto glossary marks | text → term buttons | first mention of a glossary key per section | `glossmark.watch` marks after every redraw (`glossmark.js:56-104`, started at `app.js:339`) | off at Professional only (`glossmark.js:32-33`); skips links, buttons, headings holding a term, `.dhead`, `.dstick`, charts, menus (`:22-25`) |

- **Inputs:** none in the frame.
- **Charts, tables, AI:** none. No AI. The header price and the stage come from free reads.
- **States:** loading: a price skeleton `span.sk` with `role="status"` and `aria-label="Loading the price"` while there is no price
  and no error (`dossier-frame.js:143`); error: when the quote fails the price area is **blank** (`:143`, `D.quoteError ? ''`) and
  only the Overview adds a message (`dossier.js:354`); on Options, Investing, Earnings, Financials, News and Chart nothing explains
  it (risk R-FR-3); empty and not-found: none in the frame (the Overview's is in F-DOSSIER-01).
- **API dependencies:** `GET /api/quote/{SYM}` (ttl 20 s, timeout 15 s, `dossier-frame.js:65`); `GET /api/session/{SYM}` (ttl 60 s,
  `:66`); the live loop calls the same two with the quote forced (`ttl 0, force`, `:86`) every 20 s from 04:00 to 20:00 New York on
  weekdays, every 5 minutes otherwise, paused while the tab is hidden with one catch-up on return, never two at once
  (`core/poll.js:22-49`); the Chart tab asks every 15 s (`chart.js:705`); `GET /api/logo/{SYM}` (image). A holiday counts as a
  trading day (`poll.js:22-24`).
- **Preferences and storage:** reads `optic.knowledge.v1` (switch, Overview only); `optic.panels.open` and `optic.panels.hidden.v1`
  (`sections.js:19`: `{"view|title": bool}`); `optic.recent.v1` (written by each page's `store.pushRecent`, `store.js:83-91`); the
  watchlist keys through `store` (`optic.watchlists.v1`, `optic.chart.watch.v1`; list in `core/device.js:23-24`); `optic.session.holder.v1`
  decides whether personal keys may be read (`device.js:192-197`).
- **Risks:**
  - R-FR-1 (c) **P1** one preference, four names: Dossier "Show advanced analysis" (`dossier-frame.js:121`), Settings "Advanced answers
    from Milo" (`settings.js:145`), Milo "Level" select with five levels (`milo.js:512`), Home and Workspace onboarding pickers that write
    the key directly (`home.js:708`, `workspace.js:1058,1105`); the Overview's `levels` entry is dead (`dossier.js:387`); Investing and
    Earnings follow the level but show no switch. See section 1 (BUG-001, BUG-002).
  - R-FR-2 (b) **P2** no request is ever cancelled: `request()` accepts a `signal` (`core/api.js:39-42`) but `get()` never passes one
    (`api.js:89-107`) and no Dossier page creates an AbortController, so switching tickers quickly leaves every started request
    (the Overview starts eleven, plus the track-record read, section 3.2) running to completion on the server. Correctness is protected by symbol checks, not by
    cancellation.
  - R-FR-3 (e) **P2** a failed quote leaves the header price blank with no sentence on six of seven tabs (`dossier-frame.js:143`).
  - R-FR-4 (c) **P2** `store.pushRecent(sym)` runs at the start of `render()` on Chart (`chart.js:702`), Options (`options.js:469`),
    Investing (`investing.js:300`), Earnings (`earnings.js:230`), Financials (`financials.js:400`) and News (`news.js:81`) before any
    quote confirms the symbol, while the Overview deliberately waits for a confirmed quote (`dossier.js:390-393`: a mistyped ZZZZQ
    "stayed, and a guest's Home linked its panels to it"). The same bug the Overview fixed is open on the other tabs.
  - R-FR-5 (c) **P2** naming: the Overview tab is "Overview" (`nav.js:19`, hidden heading `dossier-frame.js:142`) but its page title is
    "SYM Dossier, Optic" (`dossier.js:379`); the sheet has four names (FR-08).
  - R-FR-6 (a) **P1** per-area legal notices exist for `swing`, `long`, `earnings` only (`core/legal.js:36`). The Overview, which holds an
    entry zone, targets, a stop and a sizing example (R-OV-1), the Chart, with Risk/reward and Position size tools, Financials, News
    and the Sheet have none; and for a page with no direct-child `section.section` (Options, Earnings: their sections sit inside
    wrapper divs, `options.js:477-479`, `earnings.js:204`) the observer appends the notice **at the end of the page** (`app.js:173`),
    so the Options notice that says "the strikes, limit prices, stops and targets on this tab are model output, not advice"
    (`core/legal.js:23`) sits after all the content (by source, not rendered).
  - R-FR-7 (c) **P2** an unknown tab slug (`#/AAPL/foo`) shows the Overview and keeps the address (`router.js:43`).

---

### F-DOSSIER-01 Overview — `#/<SYM>`

- **Files:** `pages/dossier.js` (page, chart, fund answers, About, What changed, More), `pages/overview-research.js` (four
  questions, Optic Score, key figures, bull and bear, what next, Advanced research, stage words), `pages/thesis.js` (thesis check),
  `pages/dossier-frame.js`, `ui/chart.js` (the line chart), `ui/drawer.js`, `ui/term.js`, `ui/sections.js`, `core/finviz.js`
  (`pctChange`, `composition`), `core/instrument.js`, `core/track.js`, `core/prefs.js`, `core/format.js`, `ui/states.js`.
- **Purpose:** one company or fund on a page: what it is, the past year's price, four separately graded questions, two Optic scores,
  the case for and against, what changed, and a thesis check; the specialist block opens with the advanced switch.
- **Auth:** guest: everything on the page reads; the thesis check works and is kept in this browser. Signed in: the thesis check also
  loads from and saves to the account (`GET /api/theses`, `PUT` and `DELETE /api/theses/{SYM}`, `thesis.js:316,245,255,268`, all
  `require_user` plus CSRF on writes, `app/account.py:564-660`); Watch and "Show on Home" act on the account's lists. Owner: nothing
  extra. A personal key is only read or written while this browser holds the signed-in person's things (`holds`, `thesis.js:146`).
- **Mode:** a company gets the company layout; only `kind === 'fund'` gets the fund layout (`dossier.js:102`; `instrument.js:20-30`).
  An index or a coin gets the company layout (risk R-OV-14).

**Sections in render order** (`dossier.js:353-361`; "Level" = what `prefs.advancedOn()` changes)

| # | Section (heading text) | What it shows | Data source | Default | Advanced / knowledge level |
|---|---|---|---|---|---|
| 1 | (sticky header, tab strip, switch row) | see F-DOSSIER-00 | `/api/quote`, `/api/session`, `/api/stage` | open | none |
| 2 | (no heading) listing state | "Optic has no listing for SYM" or "SYM's quote did not load" | quote and ticker errors | only on error | none |
| 3 | (no heading) stale line | the framework's own freshness sentence | `framework.freshness` when `state === 'stale'` (`dossier.js:355`) | only when stale | none |
| 4 | "What NAME does" (fund: "What NAME is") | two-sentence lead (max 320 characters, `dossier.js:256-261`), Industry or Kind of fund, "Where its revenue comes from" (top two segments), Share price with change and "today" or "at the last close", Market value; folds "What it does, in full" and "Latest headlines" | `/api/session` profile (the 10-K business section when EDGAR has one, else Yahoo, `main.py:3354-3359`), `/api/quote`, `/api/segments`, `/api/ticker` news | section open, folds closed | none |
| 5 | "The past year" / "six months" / "three months" | range buttons, a one-line title ("SYM is up N% over the past year, M% below its highest close"), a source line, the line chart with E/D/S marks and the options-implied gold cone, fold "The N marked dates", freshness line | `/api/ticker` price series, earnings history; `/api/extras` dividends and splits; `/api/earnings` implied move (`dossier.js:60-97`) | open | none |
| 6 | company: "Four questions, answered separately" | four cards: "Is it a strong business?", "Is the price attractive?", "Is there a trade?", "What about earnings?", each with a value, a plain answer, a one-line sub, and folds "Show the figures" (up to three cards) and "Why" (up to four); a method footer | `/api/framework` (`long_term`, `swing`, `earnings`), `/api/ticker`, `/api/longterm`, `/api/fair-value` | open, folds closed | none |
| 6f | fund: four answers (no heading; `aria-label="Four questions, answered"`) | "What is it?", "What do its holdings cost?", "How has the share price moved?", "What does it pay?" as buttons | `/api/session`, `/api/longterm`, `/api/quote` (`dossier.js:103-148`) | open | none |
| 6g | fund: "A risk to weigh" line | first bear-case point | client rules | when one exists | none |
| 7 | "Optic Score" | two cards: "Short term: 2 to 8 weeks", "Long term: several years": n of 100, scale bar, label, one line, up to three drivers, notes, fold "How this is calculated" | `/api/ticker` (`verdict`, `pulse`, `why`), `/api/longterm` | open, folds closed; omitted when neither score exists (`overview-research.js:601`) | none |
| 8 | company: "Key figures" | seven labelled figures that exist: Market cap, P/E (trailing), Revenue growth last quarter, Profit margin 12 months, Dividend yield, 52-week high, 52-week low | `/api/ticker` quote, short interest (`overview-research.js:263`) | open | none (the other eleven are in Advanced research) |
| 9 | "Bull case and bear case" | fold "Show the case for and against (N for, M against)" holding two lists of up to four points, each with an "Evidence" link; fold "What has been moving it recently"; a "not ranked, not written by a model" line | client rules over the payloads (`overview-research.js:156-205`) | section open; case fold **closed unless advanced**; drivers fold closed | case fold opens at advanced (`:468`) |
| 10 | fund: "The long-term record" | 1, 3, 5, 10 year returns, largest fall, below its high now, volatility | `/api/longterm` (`dossier.js:193-205`) | open | none |
| 11 | company: "Taken together" | one synthesis sentence, the framework verdict, up to three lines, a note | `/api/framework.combined`; `/api/longterm`, `/api/fair-value` for the sentence (`dossier.js:209-238`) | open; absent for a fund or without a framework read | none |
| 12 | "What changed lately" | period label, "Ask Milo about this", up to N rows (observed changes plus up to three headlines "as possible explanations") each a collapsed row with a source link | `/api/digest/{SYM}` (`dossier.js:241-253`) | open, rows closed; omitted when nothing | none |
| 13 | company: "Your thesis check" | the reader's own conditions and note | `thesis.js` plus `/api/theses` | open | none |
| 14 | "What should I look at next?" | "Coming up" (up to 4 dated events) and "Research steps" (up to 4 links plus an Ask Milo button) | `/api/ticker` (`news`, `earnings_history.upcoming`, `whats_next`) | open | 8 events, including Opex, COT and expiry rows, at advanced (`overview-research.js:209-224`) |
| 15 | "More on NAME" | fund: fold "Key figures"; fold "Recent SEC filings" (five newest) | `/api/ticker` filings (`dossier.js:301-317`) | open, folds closed; omitted when empty (`:314`) | none |
| 16 | "Advanced research" (a `details`, no `h2`) | Optic's read, all key statistics, a card per other tab, three headlines, "How this page is built" | `/api/ticker` (`overview-research.js:754-762`) | **closed unless advanced** | opens at advanced (`:757`) |
| 17 | (disclaimer line) | `ticker.disclaimer` or "Not financial advice. For research and education only." | `/api/ticker` (`legal.SHORT`, `main.py:913`) | shown | none |

**Reading load by source (risk R-OV-10).** Fixed and typical dynamic text visible before any click, estimated from the templates:
header and tabs about 40 words; About about 80; chart title, source line and cone sentence about 60; four question cards about 480
(four cards of about 100 plus a 70-word footer that prints the method and policy ids, BUG-009); Optic Score about 300; Key figures
about 45; Bull and bear about 35 (fold closed); Taken together about 100; What changed about 60; thesis prompt about 45; What next about
110; disclaimer about 15. That is roughly 1,200 to 1,400 words in eleven or twelve sections with about twenty closed folds. Another
session recorded 1,384 visible words, 11 H2 sections and 21 closed folds for NVDA at 1440 (BUG-004, Rendered there); I did not
re-measure it.

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| OV-01 Show advanced analysis | switch | "Show advanced analysis" | `dossier.js:421` → `prefs.setAdvanced` (`prefs.js:118-124`) | traced in section 1; focus is restored after the repaint (`dossier.js:335,371`) |
| OV-02 Chart range | segmented buttons | "3M", "6M", "1Y" (`aria-pressed`) | `dossier.js:419-420`: sets module variable `range` and repaints | not stored; survives moving between tickers in a visit (`dossier.js:39`); windows 63, 126, 252 sessions, calendar months for a market that trades daily (`:43-45`, `overview-research.js:42-50`) |
| OV-03 Chart reading | pointer, touch, keys on the chart | none (`svg role="img" tabindex="0"`, `aria-label` = the text summary, `ui/chart.js:132`) | pointer move or tap shows date and close; ArrowLeft/Right step 1 bar, Shift 20, Home/End ends; past the last close the pointer or ArrowRight reads the cone's range ("N to M through DATE ... What the market charges for, not a forecast") (`ui/chart.js:238-261,282-300`) | a touch does not focus the chart (`ui/chart.js:268-273`) |
| OV-04 Chart Measure | button plus gestures | "Measure between two dates" (icon) | `ui/chart.js:197`; Shift-drag, hold 400 ms on touch, two fingers, or the M key; Escape clears (`:198-236,285-289`) | `aria-pressed`; result announced "Measured A to B: change" (`:194-195`) |
| OV-05 Event marks | SVG buttons `role="button" tabindex="0"` | E (earnings report), D (ex-dividend date), S (split) | click, Enter or Space → `drawer.open` (`ui/chart.js:315-318`; `dossier.js:91-95`) | an earnings mark's drawer has "Ask Milo about this report" (drafts "How did SYM react to the DATE report?") |
| OV-06 Marked dates | `details` fold | "The N marked dates" | native; table Date, Marked, What (`overview-research.js:301-306`) | all marks in words for a keyboard |
| OV-07 About folds | `details` ×2 | "What it does, in full" (when longer than the lead); "Latest headlines" (up to 6) | native (`dossier.js:285-286,297`) | headlines open in a new tab, `rel=noopener`; link "All headlines on News" |
| OV-08 Card fold: figures | `details` ×≤3 | "Show the figures" | native (`overview-research.js:326-331`) | each ends with a link "Open Financials", "Open Investing" or "Open the chart" |
| OV-09 Card fold: why | `details` ×≤4 | "Why" | native (`overview-research.js:351`) | business: component grades, "Two ways this could lose money over three years", "Levels to reassess at"; price: component table; trade: "Reasons to skip it", the plan table, a sizing example; earnings: results, guidance, reaction, cases, what would prove it wrong |
| OV-10 Score fold | `details` ×2 | "How this is calculated" | native (`overview-research.js:602-616`) | tables of inputs or factors; links "The full breakdown, on Options" and "on Investing" |
| OV-11 Key figure labels | term buttons ×7 | each figure's name | `term('stat:ID')` popover (`overview-research.js:264`; `ui/term.js:35-54`) | definition text per figure, with "Explain this with Milo" |
| OV-12 Case fold | `details[data-adv]` | "Show the case for and against (N for, M against)" | native; opens at advanced (`overview-research.js:468`) | each point may carry an "Evidence" link to a tab (`:462`) |
| OV-13 Drivers fold | `details` | "What has been moving it recently" | native (`overview-research.js:469-471`) | links to the news story (`rel="noopener noreferrer nofollow"`) |
| OV-14 Ask Milo about this | button | "Ask Milo about this" | drafts "What changed for SYM lately, and does it matter?" (`dossier.js:249`) | in What changed lately |
| OV-15 Change row | button `data-v2-ev` | date, text, detail, chevron | toggles `aria-expanded` and the body (`dossier.js:431-436`) | body is a "Read at the source" link or the detail text |
| OV-16 Start a thesis check | button | "Start a thesis check" | `thesis.js:278` → `startEdit(null)` | |
| OV-17 Thesis conditions | checkboxes ×7 | "The price stays above its 200-day average"; "Revenue keeps growing"; "It stays profitable"; "It keeps meeting or beating earnings estimates"; "The price stays within 20% of its usual price-to-earnings"; "It keeps up with its sector"; "The price stays above a level I choose" | `thesis.js:297-301` (draft follows every change); a box whose figure is missing is disabled (`:188`) | each shows "Holds today" / "Does not hold today: figures" (`:178-182`) |
| OV-18 Thesis level | text input | `name="tc-level"`, `inputmode="decimal"`, `aria-label="Your level in dollars"`, placeholder 90% of the price | typing ticks the level box (`thesis.js:295`) | parsed by `levelOf` (`:97`) |
| OV-19 Thesis note | textarea | "In your own words (optional)", `maxlength=2000`, placeholder "For example: services keep growing faster than hardware." | `thesis.js:294` | |
| OV-20 Save | submit | "Save my thesis check" / "Save changes" | `thesis.js:302` → `save` (`:231-249`) | writes the browser copy first, then `PUT /api/theses/{SYM}` when signed in; toast; a failed account write keeps the browser copy (`:247`) |
| OV-21 Cancel | button | "Cancel" | `thesis.js:280` | |
| OV-22 Edit / Delete | buttons | "Edit", "Delete" | `thesis.js:279,281` → `startEdit`, `remove` (`:251-262`) | Delete removes immediately and offers Undo twice: an inline "Undo" button and a toast action (`:203,259-261`) |
| OV-23 Ask Milo to stress-test it | button | "Ask Milo to stress-test it" | drafts the text from `stressText` (`thesis.js:136-139`) | text includes the reader's conditions and own words |
| OV-24 Next: research steps | links ×≤4 | e.g. "Review past results before the report on DATE", "Read the full financial statements", "See how the price compares with its own valuation history", "Read the N latest headlines", "Compare SYM side by side with a competitor" | `hrefFor(view, sym)` or `#/compare?t=SYM` (`overview-research.js:485-486`) | the set depends on the data (`nextSteps`, `:226-234`) |
| OV-25 Next: Ask Milo | button | "Ask Milo a question about SYM" | `data-v2-milo` draft (`overview-research.js:487`) | "Nothing is sent until you press Send" (`:488`) |
| OV-26 SEC filings | `details` | "Recent SEC filings" | native (`dossier.js:310,316`) | five links, new tab |
| OV-27 Advanced research | `details[data-adv]` | "Advanced research" | native; opens at advanced (`overview-research.js:757`) | contains OV-28 to OV-32 |
| OV-28 Read more | `details` | "Read more" | native (`overview-research.js:693`) | what carries the read, what is against it, what "conviction" measures (bands 5, 15, 25 points from 50) |
| OV-29 Sources | `details` | "N sources" | native (`:711`) | |
| OV-30 Method | `details` | "How this works" (`how()`, `ui/states.js:18`) | native (`:717`) | |
| OV-31 Key stats | term buttons | up to eighteen stat names | `term('stat:ID')` (`:264,760`) | Market cap, P/E trailing and forward, EPS trailing and forward, Dividend yield, Open price, High and Low (today or last session), Volume, Average volume, 52-week high and low, Beta, Short interest, Days to cover, Profit margin, Revenue growth (`:237-261`) |
| OV-32 The rest of this ticker | links ×≤6 | cards "Chart", "Options", "Earnings", "Financials" (not a fund), "News", "Investing" | `hrefFor` (`overview-research.js:735`) | each card carries one figure and a note |
| OV-33 Headlines in Advanced | links ×3 plus one | the headlines; "All N headlines" | `overview-research.js:741-742` | |
| OV-34 Fund answers | buttons ×4 (fund only) | the four fund questions | `dossier.js:422-430` opens the drawer "SYM, evidence and method" with an Ask Milo button | `aria-expanded`, `aria-describedby` |
| OV-35 Unlisted | button and link | "Search for the company"; "Go to Home" | `data-v2-open-palette` (`app.js:241`); `#/` (`dossier.js:350`) | |
| OV-36 Try again | button | "Try again" | `failed(..., {retry:'dossier'})` → `retry.dossier` (`dossier.js:440`; `app.js:280-283`) | invalidates `/api/quote` and `/api/ticker` only, then re-renders; the other nine reads come from the client cache |
| OV-37 Section chrome | see F-DOSSIER-00 | chips, Expand all, Collapse all, Panels, per-heading fold | `sections(main, 'overview', ...)` (`dossier.js:387`) | applies to every section that has an `h2`; the Advanced research section has none |

- **Inputs:** the thesis form only (OV-17 to OV-19). Validation: the level box must be above zero if its condition is ticked
  ("Enter your level in dollars, above zero, or untick that condition."), at least one condition must be ticked ("Pick at least one
  condition."), and the page's data must have loaded ("This page's data has not loaded yet, so the conditions cannot be read. Try again
  in a moment.") (`thesis.js:233-235`). Keyboard: native form; Enter in the level box submits the form; there is no Escape handler on
  the form. A half-typed note, ticked boxes and the caret survive the page's redraws because the section is one node kept for the
  visit (`thesis.js:305-331`). Elsewhere the page has no text input.
- **Charts and tables:** one line chart (`ui/chart.js lineChart`, area, `label` "SYM closing price", `pad` 26/52/24/0, height 220 to
  340, `focusEnd`, `monthStep` 3 for 1Y else 1, `future` sessions and `cone` from the options-implied move, `dossier.js:82-97`); a
  marked-dates table (3 columns); the four-question component tables (`q-table`); the Optic Score input tables (4 and 3 columns);
  all other content is prose and definition lists. **AI-generated sections: none** (see the API list: every handler is fixed rules;
  `overview-research.js:9-10`, `:747`; `app/research` and `app/analytics` import no model client). "Ask Milo" controls draft only.
- **Tooltips and glossary:** `term('stat:...')` on key figures and key stats, `term('market cap')` on Market value (`dossier.js:295`),
  `term('stage:SYM')` in the header, auto marks per section (F-DOSSIER-00 FR-19, FR-20); `title` text on the "Optic's read" tier chip
  and each factor label (`overview-research.js:709,713`).
- **Modals, drawers, menus:** the evidence drawer for event marks and, for a fund, answers; the ⋯ menu; the Panels menu.
- **States** (exact text, file:line):
  - Loading: chart `skeleton('chart', 1, 'Loading the price history')` (`dossier.js:69`); four questions: "Grading…" in each card
    (`overview-research.js:431,438`); long-term score "Working out the long-term score…" (`:624`); What changed `skeleton('lines', 2,
    'Loading what changed')` (`dossier.js:243`); fund record skeleton (`:195`); fund answers shimmer (`:146`); thesis "Checking your
    conditions…", "Waiting for this page's data.", "Loading from your account…" (`thesis.js:164,169,156`). About, Optic Score, Key
    figures, Bull and bear, What next and Advanced research have **no placeholder**: each returns nothing until `/api/ticker` answers
    (`overview-research.js:451,460,476,599,755`; `dossier.js:288`), so the page grows as data arrives (risk R-OV-9).
  - Error: quote: "SYM's quote did not load" with Try again, or, when the source is unreachable, "The quote source did not answer for SYM"
    (`dossier.js:354,393`); price history: "The price history did not load" with Try again (`:357`); four grades: "The four grades
    are not available right now: MESSAGE." and "... not available for this symbol: REASON." (`overview-research.js:437,439`), **no retry
    button**; long-term score: "The long-term score is not available: REASON." (`:624`); trend answer of a fund: "Not available
    right now." (`dossier.js:133`); fund answers: "The four answers did not load" only when framework, fair value and earnings all failed
    (`:358`); thesis: "Your account's copy did not load, so this is the copy in this browser." (`thesis.js:156`). A failed
    `/api/ticker` removes five sections silently and shows only the chart's error. A failed digest, segments or extras read shows nothing
    (`dossier.js:403-406`). A failed stage read is asked once more after 30 seconds and is otherwise silent (`:409-411`).
  - Empty: "No price history to draw / The quote above is current; the chart returns when the history does." (`:70`); "Not enough price
    history." (`:136`); "No bull-case point stands out in the data Optic holds." (`overview-research.js:464`); "No bear-case point stands
    out in the data Optic holds. That is not the same as no risk: every stock can fall." (`:465`); "No scheduled company events or economic
    releases in the data for the coming days." (`:483`); What changed, More on and About are omitted when empty (`dossier.js:244-247,314,288`).
  - **Not-found ticker:** when the quote and the price history both answer "not found" the page draws one state and stops: title
    "Optic has no listing for SYM", text "No quote and no price history came back for this symbol. It may be misspelled, delisted, or
    listed outside the US under another form.", buttons "Search for the company" and "Go to Home" (`dossier.js:347-352`). With only the quote
    missing: the same title with "No quote came back for this symbol..." (`:354`). The other six tabs have no such state (risk R-FR-3).
- **API dependencies (METHOD path — purpose):** `GET /api/quote/{SYM}` — header price; `GET /api/session/{SYM}` — session phase, profile,
  business description; `GET /api/ticker/{SYM}?max_expiries=4&macro=true` — the snapshot most sections read; `GET /api/framework/{SYM}?mode=combined`
  — four graded questions and the combined verdict; `GET /api/fair-value/{SYM}` — star rating; `GET /api/longterm/{SYM}?indices=false` — long-term
  score, valuation history, fund record; `GET /api/earnings/{SYM}` — implied move and next report; `GET /api/digest/{SYM}` — what changed;
  `GET /api/segments/{SYM}` — revenue by segment for one line; `GET /api/extras/{SYM}?benchmark=SPY` — dividend and split marks;
  `GET /api/stage?symbol=SYM` — header stage; `GET /api/validation` — track-record sentence in the stage definition (`core/track.js:77`);
  signed in: `GET /api/theses`, `PUT` and `DELETE /api/theses/{SYM}`; `GET /api/logo/{SYM}`. Order, returns, model use and caching are in
  section 3.
- **Preferences and storage:** `optic.knowledge.v1`, `optic.knowledge.basic.v1`, `optic.knowledge.asked.v1` (the switch);
  `optic.panels.open`, `optic.panels.hidden.v1` (folds and hidden sections); `optic.thesis.v1` (personal key; the backing copy for
  both guests and signed-in readers, `thesis.js:7-12,145-148`); `optic.recent.v1` (pushed once a quote confirms the symbol,
  `dossier.js:393`); the chart range is a module variable, not stored.
- **Risks:**
  - R-OV-1 (a) **P0** a trade plan on the Overview. The third card is titled "Is there a trade?", its value is "Grade S", "Grade A",
    "Grade B", "Avoid", "No Setup" or "Insufficient Data" (`overview-research.js:393-394`; vocabulary `app/research/swing_setup.py:462-500,526-537`),
    its fold lists "Reasons to skip it, most damaging first", then a table of Setup, **Entry zone**, Confirmation, **Invalidation**, **Targets**, Reward
    to risk, Holding, Earnings, a reassess line and a sizing sentence "N shares risk about $X at the stop" (`overview-research.js:381-391`;
    plan fields `swing_setup.py:432-455`, sizing `:453-455`). The fold is closed by default, the card's value and one-line reason are not.
    This is the kind of content directive 02 names as advice ("This is a great entry point"; "Tell me precisely when to enter this position" is on its test list). The page has no
    area notice (R-FR-6). Suggested: describe the setup ("The chart shows a pullback in an uptrend"), drop grade letters and "Avoid", move
    levels to Options under an explicit "worked example" label, remove the sizing sentence from the Overview.
  - R-OV-2 (a) **P1** "Taken together" is visible by default and speaks as a verdict: "A tradeable setup in a business the framework would
    not hold for years (...). The trade rests on price behaviour, so its stop matters more than the business case", "A good company can be a poor
    trade right now" (`app/research/service.py:497-513`, drawn `dossier.js:233-237`); the labels "High Conviction", "Constructive", "Weak
    Structure", "Not Investable" (`app/research/quality.py:927-969`) appear in the business card's sub line (`overview-research.js:360`) and
    in the synthesis sentence "Optic's combined long-term case is high conviction." (`dossier.js:219-221`).
  - R-OV-3 (a) **P2** call-like vocabulary around otherwise hedged scores: the short-term card's label is "Bullish" or "Leaning bearish"
    (`overview-research.js:521,535`) for "2 to 8 weeks", the headings "What should I look at next?" (`:478`) and "Research steps" (`:484`),
    "Levels to reassess at" (`:363`). The footer hedges are strong ("neither has been shown to predict returns. Not a recommendation to buy
    or sell", `:627`); the vocabulary is what reads as a call.
  - R-OV-4 (c) **P1** the advanced switch and its dead `levels` entry (section 1; R-FR-1).
  - R-OV-5 (b) **P2** open folds are restored by summary text. `paint()` collects the text of every open `details` and, after the redraw,
    opens every `details` whose summary text matches (`dossier.js:338,364-368`), and the page repaints after each of about twelve
    answers (`dossier.js:389`). Up to four cards each have a "Why" fold and up to three have "Show the figures", so opening one "Why" opens the others at
    the next repaint; and the case fold's summary contains counts (`overview-research.js:468`), so when a later answer changes the counts a
    fold the reader opened no longer matches and closes.
  - R-OV-6 (b, f) **P1** stale body. `api.get` returns a cached payload of any age at once and refreshes it in the background
    (`core/api.js:93-100`); no Dossier call passes `onUpdate` (the only occurrences are in `api.js`), so the refreshed copy is used only by the next
    visit. On a revisit within one page load the body paints the old snapshot while the header price is forced fresh every 20 s
    (`dossier-frame.js:86`). Key figures read `ticker.quote` (`overview-research.js:451`) not the merged live quote, so the price, the 52-week
    range and the volume beside each other can be from different times with no label; "Worked out X ago" is printed only past 60 minutes
    (short term) or 24 hours (long term) (`:532-533,560-561`).
  - R-OV-7 (f) **P2** a fixed sentence about timing: "US dollars; quotes delayed about 15 minutes" is a literal in the template
    (`dossier.js:283`), while the server says "Quote and options chain are real-time via Tradier" when that provider is configured
    (`main.py:867-871`) and the header words its freshness from the quote (`core/marketTime.js:51-58`). `sheet.js:63` repeats the literal.
  - R-OV-8 (f) **P2** the headline figures carry no visible source or time of their own: Key figures says only "Select a label for what it
    means" (`overview-research.js:456`); the Optic Score footer says what 50 means (`:627`); the source line is on the chart (`:298`) and
    in "How this page is built", which sits inside the closed Advanced research fold (`:744-753`).
  - R-OV-9 (e) **P2** sections appear only when data arrives and vanish if it does not: five sections return an empty string without
    `/api/ticker` (`overview-research.js:451,460,476,599,755`) and the only failure message is the chart's (`dossier.js:357`); the four-grade
    failure has text and no retry (`overview-research.js:437-439`).
  - R-OV-10 (g) **P1** about 1,200 to 1,400 words and about twenty closed folds before any click, in eleven to twelve sections (breakdown above;
    BUG-004). The four-question card values are placed first and carry about 100 words each with their plain answer, risk sentence and sub line
    (`overview-research.js:347-352`).
  - R-OV-11 (c) **P2** the same short-term read appears three times in three phrasings: the Optic Score card (`:516-536`), "Optic's short-term
    signals" in the drivers fold (`:200-201`) and "Optic's read" in Advanced research (`:702-718`); and the seven Key figures are a subset of the
    eighteen Key stats (`:263`, `:760`). Directive 06 asks for no duplicated analysis.
  - R-OV-12 (c) **P2** three implementations of "the case for and against": client rules here (`:156-189`), the server's `cases` on Options
    (`options-panels.js:232`) and on the Sheet (`sheet.js:47,98-99`); also `valuationRead` exists twice (`thesis.js:44-50`,
    `overview-research.js:124-141`) and `firstSentences` twice (`dossier.js:256-261`, `sheet.js:23`).
  - R-OV-13 (b) **P2** a read that writes: `GET /api/framework/{SYM}?mode=combined` saves an immutable pre-earnings forecast when the read
    is available (`app/research/service.py:439-440`, default `save_forecast=True`; the route passes no override, `app/main.py:1212`), for any
    guest and any symbol that matches the pattern (`main.py:1208-1209`).
  - R-OV-14 (e) **P2** only a fund gets its own layout (`dossier.js:102`); `#/^GSPC` and `#/BTC-USD` get company questions (`instrument.js:44-47`
    already knows neither has financials).
  - R-OV-15 (privacy) **P2** the reader's thesis conditions and note ride in Milo's context (`dossier.js:378`, `thesis.js:334`) and go to the
    model when the reader presses Send in Milo.
  - R-OV-16 (d) **P2** `RP` (`core/reports.js`) is imported and not used (`dossier.js:19`); the `levels` entry is dead (section 1).
  - R-OV-17 (e) **P2** a missing Weinstein stage is silent after one retry at 30 s (`dossier.js:409-411`).

---

### F-DOSSIER-02 Chart — `#/<SYM>/chart` (optional `?interval=daily&range=1Y&show=ov:ma|pane:rsi`, set by Milo's chart cards, `chart.js:682-688`)

- **Files:** `pages/chart.js` (page, toolbar, bars, comparison), `pages/chart-widgets.js` (eighteen side panels), `pages/chart-studies.js`
  (server studies), `pages/chart-chrome.js` (colours, legend state, full screen), `ui/pricechart.js` (the chart: gestures, legend,
  navigator), `ui/chartread.js` (the Chart read), plus `ui/drawings.js`, `ui/studies.js`, `ui/timeaxis.js` (geometry, not audited line by line).
- **Purpose:** a full-height interactive price chart: bar size and range, candles, line or area, averages and bands, levels, events,
  oscillator panes, the reader's drawings, a comparison in percent, and side panels for research, notes and small tools.
- **Auth:** guest: everything works. Drawings, Notes, the Checklist and the Stop check are personal keys, read and written only while this browser
  holds the signed-in person's things, otherwise drawings are not read and a save says "Drawings are not saved: this browser is holding another
  account's things." (`chart.js:89-99`; `chart-widgets.js:71-80`). Signed in: the Watch panel edits the account's lists. Owner: nothing.
- **Mode:** same page for company, fund, index and coin; "Extended" hours is disabled for an index or a coin (`chart.js:588`).

**Sections in render order** (`chart.js:590-601`): header and tab strip (plain blocks, not sticky) → `section.chart-page` holding: (1) `#ch-tools`
toolbar row → (2) `#ch-layers` second row (hidden until Layers is pressed, `chart.js:394`) → a confirm banner or a note form when one is active →
(3) `.ch-stage`: `#ch-draw` drawing rail, `#ch-body` the plot, `.ch-wrail` the widget rail with a visually hidden Milo button
("Ask Milo about the SYM chart", `chart.js:595`), `.ch-side` (the Chart read aside and any open panels) → (4) `.ch-foot`: the data note `#ch-note`, the
study and comparison notes `#ch-snote` (`aria-live="polite"`), and a gesture hint (touch or pointer wording, `chart.js:598`). Nothing here is
gated by the knowledge level. First-visit defaults (`chart.js:77`): 1-hour bars, range 6M, candles, regular hours, overlays MA, Earnings
and Insider trades on, Volume pane on, no widget open, Layers row closed, Chart read off.

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| CH-01 Indicators | `details.menu` | "Indicators" plus a count | native; body below (`chart.js:373`) | closes on outside click or Escape (`app.js:286-294`) |
| CH-01a Find | search input | "Find an indicator" (`aria-label` "Find an indicator, level or pane") | `input` handler filters overlays and panes by name, key and aliases (`chart.js:337-347,797-803`) | "Nothing here is called Q. Try a word such as average, RSI or volume." |
| CH-01b Overlays ×9 | checkboxes | "MA 20, 50, 200"; "EMA 9, 21, 50"; "EMA 9 / 21 cloud"; "EMA 21 / 50 cloud"; "Bollinger 20, 2"; "Keltner channel"; "Donchian channel"; "Regression channel"; "Anchored VWAP" | `change` → `V.overlays[k]`, `saveView`, `ST.need` (`chart.js:746`) | a one-line help under each where `ST.HELP` has one (`chart-studies.js:17-37`); disabled with a reason by `cannot(k)` (`chart.js:323-331`) |
| CH-02 Layers | toggle button | "Layers" plus a count | `chart.js:761` toggles the second row (`aria-expanded`, `aria-controls="ch-layers"`) | title "Levels, events, candle colours, panes and colours" |
| CH-03 Chart read | toggle button (desktop) | "Chart read" | `chart.js:772`: shows the aside (`aria-pressed`) | title "The trend, the nearest levels, RSI and MACD, from daily sessions" |
| CH-04 Reset | button (desktop) | "Reset" | `chart.js:762-768`: every overlay off, every pane off except Volume, drawings kept; toast "Back to price and volume. Your drawings are kept." with Undo | disabled when already clean (`:351,383`) |
| CH-05 More chart settings | `details.menu` (phone) | ⋯ | holds the Style group, "Chart read", "Reset indicators", "Fit every bar", "Full screen"/"Leave full screen", "Explain this chart" (`chart.js:375-381`) | the Style, Fit and Full screen controls are on the toolbar or plot on a wide screen |
| CH-06 Draw | toggle button | "Draw" with a pencil | `chart.js:779`: shows the drawing tools row on a phone; always shown on a wide screen (`:407`) | |
| CH-07 Bar size | select | "Bar size": 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W (`chart.js:38-43`) | `change` → `V.interval`, `loadBars()` (`:743`); weekly with an unsupported range resets to 1Y | a symbol with no intraday feed falls back to daily bars with a note (`:123-128`) |
| CH-08 Session | select (intraday only) | "Regular hours" / "Extended hours" (phone: "Regular" / "Extended"); "Extended (none here)" disabled for an index or coin | `change` → `V.session`, `loadBars()` (`:742`) | title "Which hours the bars cover" |
| CH-09 Range | segmented buttons, or a select on a phone (daily and weekly only) | "1M", "3M", "6M", "1Y", "All" | `chart.js:760,744`: `All`, or leaving it, refetches bars; else `newRange()` | stored in the view |
| CH-10 Fit | button (wide screen) | "Fit" | `chart.fit()` (`chart.js:774`) | title "Every loaded bar on screen" |
| CH-11 Reset zoom | button | "Reset zoom" (hidden until zoomed) | `chart.home()` (`chart.js:769`) | a second one over the plot for a phone (`pricechart.js:227`) |
| CH-12 Style | segmented icon buttons | "Candles", "Line", "Area" (`aria-label` and `title`) | `chart.set({style})` (`chart.js:773`) | Weinstein stages and MA Trend colour candles only (`:325`) |
| CH-13 Compare | `details.menu` in the Layers row | "Compare" plus a count | form below (`chart.js:295-305`) | up to three symbols; lines in percent from one start bar |
| CH-13a Compare box | text input + "Add" submit | placeholder "Add a symbol, such as SPY", `maxlength=12`, `aria-label` "Symbol to compare with SYM" | `submit` → `addCompare` (`chart.js:808-811,310-317`) | refusals: "That does not look like a ticker. Try letters such as SPY.", "This chart is SYM already.", "SYM is on the chart already.", "Up to 3 at a time. Remove one first.", "SYM is a yield, so its percent change is not a return. Compare it on Macro instead." (`:282-290`) |
| CH-13b Suggestions | buttons | "SPY", "QQQ", "IWM" (those not used) | `chart.js:756` | |
| CH-13c Remove / Stop / Start | buttons | "Remove" per symbol; "Stop comparing"; "Start from the first bar in view" | `chart.js:757-759` | a bar another symbol lacks is a gap, never a carried close (`:241-244`) |
| CH-14 Levels | `details.menu` | "Levels" | seven checkboxes: "Fibonacci", "Support and resistance", "Dealer gamma levels", "Supply and demand", "Accumulation zones", "Auto trend lines", "Volume by price" (`chart.js:62,65-67`) | |
| CH-15 Events | `details.menu` | "Events" | five checkboxes: "Market structure breaks" (with a "Swing strength" select: 3, 5, 10 "bars each side", `chart.js:333-334,745`), "Earnings", "Insider trades", "SEC filings", "Session dividers" | the MSB help text explains known-late swings |
| CH-16 Candle colours | `details.menu` | "Candle colours" | "Weinstein stages", "MA Trend Identifier" | disabled unless Candles |
| CH-17 Panes | `details.menu` | "Panes" plus a count | nine checkboxes: "Volume", "RSI 14", "MACD 12, 26, 9", "Trend Strength Oscillator", "ADX and DI", "Stochastic", "On-balance volume", "Money flow index", "Relative strength line" (`chart.js:72,397`) | `change` → `V.panes[k]`, repaint (`:747`); the volume-based ones are disabled when the symbol reports no volume (`:322,328`) |
| CH-18 Colours | `details.menu` | "Colours" | per slot "Candle up", "Candle down", "Line": eleven preset swatches (Green, Red, Gold, Blue, Orange, Teal, Amber, Pink, Violet, White or Black, Grey), a colour-wheel input, "Default"; "Reset all to the theme" (`chart-chrome.js:74-93`) | contrast under 3:1 prints "Hard to see against the chart background at N:1. A mark needs about 3:1 to read as a shape." (`:71`); keys `optic.chart.colors.v1` |
| CH-19 Drawing tools ×15 | toggle buttons in a toolbar | "Select and move", "Trend line", "Ray", "Horizontal line", "Vertical line", "Channel", "Rectangle", "Fibonacci retracement", "Fibonacci extension", "Pitchfork", "Arrow", "Text note", "Measure", "Risk / reward", "Position size" (`chart.js:47-49`) | `chart.js:780`: sets the tool and toasts what it asks for (`TOOL_HOW`, `:53-58`) | Escape cancels (`:464`) |
| CH-20 Snap | toggle | "Snap to candles" | `chart.js:770`; `optic.chart.snap.v1` = "off" or "on" | title says what each state does |
| CH-21 Undo, Redo, Delete, Remove all | buttons | "Undo the last drawing change", "Redo", "Delete the selected drawing", "Remove all drawings on SYM" | `chart.js:771,781-783`; remove-all asks "Remove all N drawings on SYM?" with [Remove] [Keep them] | undo history survives a rebuild on the same bars (`pricechart.js:201`) |
| CH-22 Note text | text input + submit | "Note on the chart" (`maxlength=120`, required); "Place it", "Cancel" | `chart.js:808-816`, `:784` | for the Text note tool |
| CH-23 Explain | button (wide screen) | "Explain" | drafts "Explain the SYM chart: the trend, support, resistance, momentum, volume and risk, and what would invalidate the read." (`chart.js:446`) | |
| CH-24 Full screen | toggle | expand or shrink icon, "Full screen" | `chart.js:775,545-550`: class `ch-max` on `html` plus the browser's full screen (`chart-chrome.js:106-119`); Escape leaves unless it is cancelling a drawing, a note, a menu or a dialog (`chart.js:555-562`) | announces "Full screen. Escape or the full screen button goes back." |
| CH-25 Chart tools | buttons over the plot | "Measure between two bars", "Zoom out", "Zoom in" | `pricechart.js:1109-1116`: zoom by 1.5 about the latest bar shown; Measure toggles | `aria-pressed` on Measure |
| CH-26 Legend | disclosure and buttons | "N overlays, M drawings" (or "No overlays"); per row a remove cross | `pricechart.js:771-775` toggles and stores `optic.chart.legend.v1` (`chart-chrome.js:97-99`); a cross calls `removeOverlay` (`chart.js:505-516`) | the cross is named "Remove NAME" |
| CH-27 Pane remove | buttons | a cross per pane | `pricechart.js:595,1115` → `removeOverlay` | |
| CH-28 Navigator | slider (`svg role="slider"`, `aria-valuetext` "DATE to DATE, N of M bars") | the whole history, small | drag the window to move, drag an edge to resize, press outside to jump (`pricechart.js:777-833`); keys: arrows a tenth of the view, PageUp and PageDown a whole view, Home, End, plus and minus (`:836-841`) | |
| CH-29 Price scale | drag strip | title "Drag up or down to stretch the price scale. Double-click to fit it to the bars." | `pricechart.js:221,862-874,1050-1051` | also ArrowUp and ArrowDown on the plot (`:1173`) |
| CH-30 Plot gestures | pointer, wheel, touch | none | wheel and trackpad zoom about the pointer, sideways or Shift pans, ctrl-wheel and Safari pinch zoom, drag pans, Shift-drag measures; one gesture has one owner, the page or a chart, for 200 ms (`pricechart.js:61-120,1058-1096`); touch: sideways pans, up or down scrolls the page, 300 ms hold reads bars, two fingers pinch and pan, hold plus a second finger measures (`:895-946`) | design note `docs/frontend-v2/CHART-GESTURES.md` (named in the file header) |
| CH-31 Plot keyboard | `svg role="application" tabindex="0"` | none | ←, → move the crosshair (Shift pans a tenth of the view); ↑, ↓ stretch the price scale; plus, minus zoom; Home, End; M measures; Enter or Space opens an insider trade under the crosshair; Delete or Backspace removes the selected drawing; Escape cancels, then deselects; Ctrl or Cmd+Z undo; Shift+Ctrl/Cmd+Z or Ctrl/Cmd+Y redo (`pricechart.js:1169-1183`) | page-wide undo, redo and Delete only while focus is on the page or a button or link inside the chart page (`:1099-1108,114-119`) |
| CH-32 Insider arrows | SVG marks | green arrow under a bar for a purchase, red over it for a sale | click or tap → `#/insiders?symbol=SYM&view=insiders` (`chart.js:460`; `pricechart.js:988-989`) | tip box names the insider and amount |
| CH-33 Drawings | direct manipulation | the reader's own drawings | click selects, drag moves, drag a handle moves a point (`pricechart.js:862-885`); stored per symbol in `optic.chart.drawings.v2` (`chart.js:88-100`) | two-point tools also place with a single drag (`:886-894`) |
| CH-34 Widget rail | toolbar of toggle buttons ×18 | Watch, Alerts, News, Analysts, Season, Notes, Insiders, Reports, Checklist, Stop check, Options, Key levels, Stats, Patterns, Pairs, Backtest, Trading, Learn (`chart-widgets.js:31-50`) | `chart.js:752` → `toggleWidget`; arrow keys, Home and End move along the rail (`:787-796`) | open ones are remembered (`V.dock`); on a phone one shows at a time; each panel has a Close button (`chart.js:753`) |

Panel controls (each opens from CH-34; `chart-widgets.js` BODY, lines 153-462):

| Control | Kind | Label or text | Action (file:line) | Notes |
|---|---|---|---|---|
| CH-35 Watch | list select (when more than one list), per-symbol link and remove button, add form, "Add SYM" | "Watchlist", "Remove SYM from NAME", placeholder "Add ticker" (typeahead `data-v2-ta="submit"`), "Add", "Add SYM" | `chart-widgets.js:154-163,690-703,746-753`: `store.unfollow` with Undo toast; `store.follow` | text says whose list it is: "The lists on your account, the same as the Watchlist page." or "Kept in this browser until you sign in." |
| CH-36 Alerts | link | "Your watches and every alert" | `#/alerts` (`:172`) | the feed is "Shared by every reader of Optic" |
| CH-37 News, Reports, Options, Analysts, Insiders, Trading | links | "News for SYM"/"All news for SYM", "Financials for SYM", "Options for SYM", "Analyst actions across the market", "Insider filings and House trades", "Open Optic Portfolio" | `more(href, text)` (`:136`) | read the already-loaded ticker payload; Analysts and Trading and Alerts make their own request once open |
| CH-38 Season | `details` | "Exact figures" | native (`:223`) | monthly means and hit rates; link "The full table, with the medians and the baseline, on the Options tab" |
| CH-39 Notes | textarea | `rows=6`, placeholder "Why are you looking at SYM? What would change your mind?" | saved on `change` and flushed on redraw, leaving or symbol change (`:228-232,675-684,706`) | disabled with a reason when this browser holds another account's things |
| CH-40 Insiders and Key levels toggles | checkboxes | "Show on the chart" | `C.overlay('ins' or 'sr', on)` (`:741-742`) | |
| CH-41 Checklist | checkboxes ×7 | "Do I know what invalidates this?"; "Is the stop at a level, not a round number?"; "Is this sized so the stop costs 1% or less?"; "Am I early, or chasing?"; "Does the higher timeframe agree?"; "Is earnings inside my holding period?"; "Would I take the other side at this price?" (`:59-67`) | `change` (`:708-715`), per symbol | "Fixed questions on purpose." |
| CH-42 Stop check | inputs | "Entry" (number, step 0.01), "Stop" (placeholder "Your stop"), "Buffer past the level" select (0.1, 0.25, 0.5 ATR), "Account (optional)" (placeholder "For sizing"), "Show on the chart" checkbox, `details` "What this rests on" | `chart-widgets.js:277-315,716-725`; request `GET /api/stop-check/{SYM}?stop=&buffer=&entry=&account=&risk_pct=` (`:485-498`) | the stop is **pre-filled from the entry plan** ("Stop from the entry plan (1.5 ATR from the price). Type your own to check it.", `:285,478-483`) |
| CH-43 Pairs | input + "Test", peer chips | "Pair SYM with" (placeholder "Symbol", typeahead), "Test"; chips of the six most alike peers; "Ask Milo about this pair"; `details` "How this is tested" | `chart-widgets.js:367-397,511-517,746-754` | |
| CH-44 Backtest | selects, number and checkbox inputs, buttons | "Strategy" (server catalogue), "Bars", "Period" (1, 2, 5, 10 years or All history; or "Last 60 sessions" on 5m), `details` "Rules" with the rule's parameters and "Run again", "Show trades on the chart", "Ask Milo about this test", `details` "How this is tested" | `chart-widgets.js:401-443,533-563,696,726-740` | default strategy `macd_turn_below_zero`, 5 years (`:92`); runs when opened |
| CH-45 Learn | select | "Term" (every glossary key) | shows the definition (`:456-461,743`) | |

- **Inputs and validation:** Compare box (above); Find; Note text; widget inputs; Stop check numbers have `min=0` and no other client
  validation; Backtest parameters take the catalogue's `min`, `max`, `step` (`chart-widgets.js:556-563`). Keyboard: chart keys above; the widget rail
  is one toolbar stop with arrows (`chart.js:787-796`); menus close on Escape with focus returned to the summary (`app.js:289-294`).
- **Charts and tables:** the plot is SVG: candles, line or area; price pane, volume band, up to nine panes drawn under it (`pricechart.js:245-260`);
  overlays (averages, bands, channels, levels, zones, volume by price, stage and MA Trend candle colours, earnings, insider and filing marks, session
  dividers, market structure breaks); comparison lines in percent; drawings with geometry for 15 tools. Bars: daily from `/api/ticker`
  (two years) or `/api/daily-bars` (All), weekly `/api/weekly-bars`, intraday `/api/intraday` (`chart.js:103-157`). Tables in panels: Key levels (Level, Role,
  Away, Strength), Season (Month, Mean, Up, Reads as), Stop check (Yours, Buffered), Backtest trades (Bought, Sold, Return). The Chart read card: "Chart
  read, daily", a trend word ("Uptrend", "Downtrend", "Mixed trend"), facts, nearest support and resistance, RSI 14, MACD 12, 26, 9 (`ui/chartread.js:21-81`).
  **AI-generated sections: none** (`chart-widgets.js:9-10`; the Milo buttons draft only).
- **Tooltips and glossary:** `title` text on every icon control; Learn panel; auto glossary marks do not enter `.chart-wrap`, `.chart-slot`, `.menu` or buttons (`glossmark.js:22-25`).
- **Modals, drawers, menus:** six `details.menu` menus, the phone ⋯ menu, a full-screen mode, toasts with Undo; no drawer.
- **States:** loading: `skeleton('chart', 1, 'Loading bars')` (`chart.js:442`), or a dimmed chart with the note "Loading 1h bars" while new bars arrive (`:109,436`); error:
  "The bars did not load" with Try again (`:441`; `failed()`, `ui/states.js:32-34`), or an inline note with a "Try again" link over the dimmed chart (`:437`); too few bars: "Not
  enough bars to draw." (`:150`); no intraday feed: "REASON Showing daily bars instead." (`:128`); ticker payload failed: each payload-reading panel says "This symbol's figures did not
  load" with Try again (`chart-widgets.js:145`), the Chart read says "SYM's daily technicals did not load, so there is no read. The chart itself is unaffected." (`chartread.js:66`);
  empty: panel texts such as "Nothing detected.", "No levels found.", "No analyst data for this symbol.", "A fund has no earnings, so it has no analyst estimates or price target of its own. Its holdings
  do." (`chart-widgets.js:196,339,359`); a symbol without volume: "SYM reports no volume, so there is nothing to draw." (`chart.js:328`). **Not-found ticker: none found**: the page shows the generic bars error (risk R-CH-4).
- **API dependencies:** `GET /api/quote/{SYM}`, `GET /api/session/{SYM}` — header (15 s live loop); `GET /api/ticker/{SYM}?max_expiries=4&macro=true` — daily bars, levels, gamma, filings, panels (ttl 120 s);
  `GET /api/intraday/{SYM}?range=KEY&window=HISTORY&session=regular|extended` (ttl 60 s); `GET /api/weekly-bars/{SYM}?span=max|10y` and `GET /api/daily-bars/{SYM}` (ttl 1 h);
  studies: `GET /api/indicators/{SYM}?ids=...&intraday=..&window=..&session=..|weekly=true&range=..|range=max&anchor=..` (ttl 5 min), `GET /api/stage?symbol=` (1 h), `GET /api/trendlines/{SYM}` (10 min),
  `GET /api/longterm/{SYM}` (1 h) (`chart-studies.js:78-84`); panels: `GET /api/alerts?limit=20`, `GET /api/analysts/{SYM}?limit=6`, `GET /api/seasonality/{SYM}`, `GET /api/tracker?book=balanced`,
  `GET /api/stop-check/{SYM}?...`, `GET /api/pairs/{SYM}/peers`, `GET /api/pairs/{SYM}?b=PEER`, `GET /api/backtest/strategies`, `GET /api/backtest/{SYM}?strategy=&timeframe=&years=&...`
  (`chart-widgets.js:108-119,489-495,507,538,552`); comparison: the intraday, weekly or daily bar reads for each compared symbol (`chart.js:250-256`); the Watch panel uses the store's list endpoints. No model.
- **Preferences and storage:** `optic.v2.chart.v1` (view: interval, range, style, session, read, layers, dock, overlays, panes, msbK, compare, cmpAnchor; `chart.js:76-86`); `optic.chart.drawings.v2`
  (per symbol, personal); `optic.chart.snap.v1`; `optic.chart.colors.v1`; `optic.chart.legend.v1`; `optic.chart.notes.v1`, `optic.chart.checks.v1`, `optic.chart.stopcheck.v1` (personal, `chart-widgets.js:70-71`);
  `optic.chart.backtest.v1`, `optic.chart.pairs.v1`; `optic.recent.v1`; `document.title` is rewritten every 15 s with the price (`chart.js:168-171`).
- **Risks:**
  - R-CH-1 (a) **P1** sizing and stop tools without a notice: the Stop check opens pre-filled with a stop "from the entry plan (1.5 ATR from the price)" (`chart-widgets.js:285`; `scInputs` reads `t.entry_plan.risk.underlying_stop`,
    `:478-483`), the Checklist asks "Is this sized so the stop costs 1% or less?" (`:62`), and the plot offers "Risk / reward" and "Position size" ("N shares, X a share at risk, risk $Y", `pricechart.js:647-652`).
    They compute the reader's own points, but the pre-filled stop is a suggestion; the page has no area notice (R-FR-6).
  - R-CH-2 (b) **P2** a late write after an `await`: in the no-intraday fallback `loadBars()` checks `current()` before the nested `await loadBars()` and not after, then writes `D.note` (`chart.js:124-128`), so a note about the
    previous symbol can land on the next one's footer if the reader switches during the nested load. Everything else here is guarded by `D.sym` and `barSeq` (`:105-106,151,154`; `core(sym)` `:708`; `loadTicker` `:715`; widgets by box identity `chart-widgets.js:100-105`).
  - R-CH-3 (f) **P2** a bar with a missing open, high or low is drawn with the close in its place and no flag (`chart.js:159`; same in `investing.js:123`), so a feed gap looks like a flat candle.
  - R-CH-4 (e) **P2** no not-found state: a symbol with no bars gets "The bars did not load ... If the data source is refusing requests, it shows here as soon as it answers" (`core/api.js:135-137`; `chart.js:441`), wording written for an outage, and the symbol is already in Recents (R-FR-4).
  - R-CH-5 (d) **P2** `OV_GROUP` names four group headings for the Indicators menu and is never used (`chart.js:70`).
  - R-CH-6 (g) **P2** no level gating: 23 overlays, 9 panes, 15 drawing tools and 18 panels are all present at every knowledge level (`chart.js:61-72,47-49`; `chart-widgets.js:31-50`); only the phone folds some controls into a ⋯ menu (`chart.js:375`).
  - R-CH-7 (f) **P2** panel figures without a time: Analysts "Mean target", Stats, Insiders and Reports rows print no as-of date (`chart-widgets.js:184-204,234-254,256-269,346-354`).
  - R-CH-8 (f) **P2** the live tick rewrites the forming bar's close, and its high or low when the quote passes them, from the quote (`pricechart.js:1215-1222`; `chart.js:173-185`): the newest candle mixes the bar feed and the quote feed, and nothing says so.

---

### F-DOSSIER-03 Options — `#/<SYM>/options`

- **Files:** `pages/options.js` (page, readings, research table, position builder, group tabs), `pages/options-panels.js` (every panel's body), `pages/options-picker.js` (contract picker),
  `pages/setups.js` (swing setups tool), `ui/pricechart.js` (Price panel), `ui/xychart.js`, `ui/bars.js`, `ui/chart.js`, `ui/score.js`, `core/track.js`, `core/watches.js`.
- **Purpose:** what options are pricing, the chain at one expiry, a position builder priced by the server, and the specialist readings (dealer gamma, flow, greeks, swing verdict, entry, ideas, levels, setups, patterns).
- **Auth:** guest: everything. The budget key `optic.entry.budget.v1` is read and written only while this browser holds the person's things (`options.js:63-70`); the picker's plan key `optic.v2.picker.v1` is listed as personal (`core/device.js:41`) but is written without that check (`options-picker.js:16-17`, R-OP-13). Signed in: "Alert me when this
  triggers" posts to `/api/watches` (`core/watches.js:24-30`), guests' alerts stay in this browser (max 40, `:31-39`). A built position is kept in memory only, per symbol, for the visit (`options.js:42-48`).
- **Mode:** same page for every symbol; there is no kind check, so a fund, index or coin gets the page and whatever errors the chain returns.

**Sections in render order** (`options.js:477-479`, `paintTop` `:371-378`): sticky header and tab strip (`#op-head`) → `#op-top`: a failure banner when `/api/ticker` failed, a lede line (`digest.lede`), the readings strip
(up to six cells, `:73-94`) → group tab bar → three tab panels, one visible (stored choice, default the first):

| Group (tab) | Subtitle | Sections |
|---|---|---|
| "Contracts and pricing" | none | "Pick a contract" (`#op-picker`), "Research contracts", "Position builder", then "What options are pricing", "How value moves" (`options.js:381-385`) |
| "Positioning and flow" | "Dealer gamma is estimated from open interest, not reported positions; flow is the day's options volume, not a record of trades." | "Dealer gamma", "Flow", "Delta and gamma" |
| "Setups and strategy" | "The swing read, the entry it points to and the ideas sized to a budget are model output from these figures, not recommendations." | "Swing verdict", "Strike and entry", "Ideas", "Price", "Levels and momentum", "Swing setups", "Chart patterns and seasonality" |

Each group's sections fold (`sections(h, 'swing', {strip: false})`, `options.js:427`); the Expand all, Collapse all and Panels bar appears only on a group with four or more sections, so only the third (`sections.js:93-94`). No section is level-gated
(`options.js:425-426`). The readings strip cells: "Implied move through DATE" (±N%, range, days, "the DATE report included"), "Average report-day move", "Priced against history", "Implied volatility, 30 days" (rank), "Skew, DATE", "Dealer gamma"
(`options.js:83-91`). Area notice: `swing` (by source at the **foot** of the page, R-FR-6).

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| OP-01 Group tabs ×3 | `role="tablist"` buttons | "Contracts and pricing", "Positioning and flow", "Setups and strategy" | click, ←, →, Home, End (`options.js:577,581-587`); `showGroup` stores `optic.options.group.v1` (`:429-436`) | `aria-selected`, roving tabindex |
| OP-02 View | segmented buttons | "Expect a rise" / "Expect a fall" | `options-picker.js:123-129` | **default "Expect a rise"** (`:16`) |
| OP-03 Holding period | segmented buttons | "7 days", "14 days", "30 days", "60 days" | same | default 30 |
| OP-04 Most premium at risk | text input | `aria-label` "Most premium at risk, in dollars" | read on submit (`:113`); sent as at least 1, default 500 (`:21`) | no client error message |
| OP-05 Target price | text input, optional | placeholder 107% (rise) or 93% (fall) of spot | sent only when above 0 (`:22`) | the placeholder is a suggestion |
| OP-06 Invalidation | text input, optional | `aria-label` "Price at which the idea is wrong, optional" | same | |
| OP-07 Hold through earnings | checkbox | "I mean to hold through the next earnings report (DATE)" | `through_event` | |
| OP-08 Find contracts | submit | "Find contracts" / "Finding…" | `run()` → `GET /api/options/{SYM}/picker` (`:114-119,131`) | nothing is requested until pressed (`:73`) |
| OP-09 Practice this trade | button per pick | "Practice this trade" | `practice()` writes `optic.v2.paper.draft.v1` and sets `location.hash = '#/paper'` (`:99-103`) | "Opens the Paper Desk with this contract and your plan filled in. Nothing is bought." |
| OP-10 Retry | button | "Try again" (`data-v2-retry="picker"`) | `options-picker.js:123-128` (stops the page's own retry) | shown when no expiries came back |
| OP-11 Expiry | select | "Expiry for the table and the position builder": "MMM D, N days[, monthly]"; "Loading expiries" / "Expiries unavailable" | `change` (`options.js:590-596`): option legs on another expiry are cleared with a toast, then `loadResearch()` | disabled until expiries load |
| OP-12 Side | segmented buttons | "Calls", "Puts" | `options.js:557`; saved in `optic.options.filters.v1` | |
| OP-13 Delta | select | "Any", "Far, .10 to .30", "Middle, .30 to .50", "At the money, .40 to .60", "Deep, .60 to .90" (`options.js:49`) | `change` → saved, reload (`:597`) | |
| OP-14 Widest spread | select | "Any", "5%", "10%", "25%" | same | default 25 |
| OP-15 Least open interest | select | "Any", "100", "500", "1,000" | same | |
| OP-16 Unquoted | checkbox | "Include N contracts without a two-sided quote" | same; reveals the added rows (`:597,356`) | drawn only when it would change the list (`:276,285`) |
| OP-17 Columns | text button | "More columns" / "Fewer columns" | `options.js:559` | adds Decay a day, Per vol pt, ITM model, OI / volume, Early exercise |
| OP-18 Row details | icon button per row | "The N call's details" | `options.js:554` | shows delta, IV, breakeven, cost, OI, ITM model, liquidity reasons |
| OP-19 Add | button per row | "Add" (or "Not tradable") | `options.js:560-576`: adds one long contract or one more of the same; four option legs at most; toast "Added the N call. ..." with "See the position" | the page does not jump (`:332-333`) |
| OP-20 All strikes | text button | "Show all N strikes" / "Show the 15 nearest the money" | `options.js:558` | |
| OP-21 See the position | button | "See the position" | `toBuilder()` (`options.js:341,555`) | |
| OP-22 Templates ×10 | chips | "Long call", "Long put", "Bull call spread", "Bear put spread", "Covered call", "Cash-secured put", "Straddle", "Strangle", "Iron condor", "Call calendar" (`options.js:37-41`) | `options.js:550` → `template()` (`:202-235`) picks strikes by nearest delta (0.5, 0.3, 0.25, 0.2, 0.1) | disabled without an expiry or without two-sided quotes (`:106`) |
| OP-23 Leg controls | buttons and number input | "Make it a sale" / "Make it a buy"; "One fewer", "One more"; quantity (1 to 100; shares 1 to 100,000, step 100); "Remove LEG" | `options.js:551-553,598` | toast "Quantity is 1 to N." on a bad value |
| OP-24 Costs and timing | `details` form | "Slippage, share of half-spread", "Fee per contract", "Days from now for the grid" (placeholder "Halfway"), "Apply" | `submit` (`options.js:601-609`): 0 to 1; 0 to 10; saved in `optic.options.filters.v1` | toasts "Slippage is 0 to 1, a share of half the spread." / "Fee is 0 to 10 dollars a contract." |
| OP-25 Scenario time | segmented buttons | the `when` labels in the server's grid, capitalised | `options.js:556` | |
| OP-26 Result folds | `details` | "How this works" (`how()`), "Liquidity and assumptions" | native | |
| OP-27 Milo buttons | buttons | "Ask Milo about this position", about implied volatility, dealer gamma, the flow, these ideas, this entry, the setups, the patterns, plus `digest.follow_ups` | draft only; each panel's button is moved beside its heading (`options.js:418-423`) | |
| OP-28 Value lab | buttons and number input | "Call" / "Put"; "7 days", "14 days", "30 days", "45 days", "60 days"; "IV" (5 to 200, `aria-label` "Implied volatility, percent") | `options.js:579,599`; `options-panels.js:363-366` | Black-Scholes in the page, labelled "A teaching model" (`:369`) |
| OP-29 Ideas budget | segmented buttons, input, button | "No limit", "$100", "$250", "$500", "$1,000", "$2,500"; "Your own" and "Use it" | `options.js:578,611` (whole dollars, 1 to 1,000,000; toast otherwise) reloads `/api/ticker` with `&budget=` | saved as `optic.entry.budget.v1` |
| OP-30 Folds in panels | `details` | "Compare expiries", "What each input measures", "Candidate strikes, ranked", "How this works" | native | |
| OP-31 Price panel | chart | "Daily bars, split-adjusted, with the 20, 50 and 200-day averages" | the same gestures as CH-25 to CH-33 without the toolbar (`options.js:525-542`); an insider arrow opens the Insiders page | crosshair is synced with the RSI and MACD charts below by date (`sync: 'opt-daily'`) |
| OP-32 Setups filters ×5 | selects | "Symbols" ("This symbol (SYM)" and each list with its count), "Direction" (Both, Bullish, Bearish), "Timeframe" ("Daily, weekly trend"; "4-hour, daily trend" or "4-hour (one symbol only)"), "Strategy" (All and nine families: Trend pullback, Moving-average crosses, RSI and MACD, Fibonacci, Triple stochastic, Donchian, Anchored VWAP, Support and resistance, Squeeze), "Status" (Live and just ended, Armed or triggered, Triggered, Armed, Watching, Invalidated or expired, Everything) | `setups.js:155-164,313-319` saves `optic.setups.view.v1` and rescans | up to 40 symbols; 4-hour for one symbol only |
| OP-33 Rule settings | button and form | "Rule settings" (", changed"); per preset "Run this preset" and its parameters; "Apply", "Back to the defaults", "Close" | `setups.js:173-185,323-324,342-356`; `optic.setups.params.v1` keeps only changes | "Every preset is a hypothesis to test, not a strategy known to work." |
| OP-34 Setup rows | buttons | "Details" / "Hide" per row | `setups.js:326-330` fetches the detail once | inside: "Alert me when this triggers" → "Alert set" (`:233,331-340`), a chart, the checks table, a history table, and a contract filter form: "Days to expiry, from" and "to", "Open interest at least", "Volume today at least", "Spread at most (%)", "Show contracts" / "Apply" (`:201-224,342-347`) |
| OP-35 Retry | buttons | "Try again" (`data-ss-retry`, and the page's `retry.ticker`, `retry.research`) | `setups.js:325`; `options.js:544` | |

- **Inputs and validation:** Picker (OP-04 to OP-07): no visible error; values are clamped when the query is built (`options-picker.js:20-26`). Position builder (OP-23, OP-24), Ideas (OP-29), Value lab (OP-28): the toasts quoted
  above. Setups: numbers clamped by the server and by `paramsFrom` (`setups.js:87-99`). Keyboard: tabs use arrows; forms submit with Enter.
- **Charts and tables:** payoff chart (`xyChart`: "At expiry", "Today", "Halfway", breakeven dots, "Now" marker, x from 75% to 125% of spot, `options.js:174-186`); implied volatility by expiry (line), net dealer gamma by strike (bars), gamma profile
  (xy), traded time value by strike (bars), per-idea payoff at expiry, RSI and MACD over 70 days with a signal line and a marked last cross (`options-panels.js:257-340`), value-lab decay and delta curves, the daily price chart, and for a setup a closing-price chart with trigger and
  invalidation lines. Tables: contracts (Strike, Delta, Bid / ask, Spread, IV, Breakeven, Cost, then four more), Compare expiries (8 columns), scenarios grid (IV change down, price move across), greeks by expiry (8), support and resistance (6), Fibonacci (4), moving averages (4),
  most active contracts (7), candidate strikes (10), patterns (3), zones (3), candles (3), seasonality (6), setups (7), setup checks (4), setup history (4), setup contracts (12). **AI-generated sections: none** (`options.js:6-7`; the Milo buttons draft).
- **Tooltips and glossary:** liquidity badge `title` (the reasons), "vol > prior OI" chip `title`; auto marks inside panels; no `term()` calls.
- **Modals, drawers, menus:** none; toasts with actions (`See the position`, `Open Alerts`).
- **States:** loading: skeletons "Loading what options are pricing", "Loading contracts", "Loading GROUP", "Pricing the position" (`options.js:75,288,413,133`), picker "Reading the chain for contracts that fit" (`options-picker.js:71`), setups "Reading SYM…" (`setups.js:269`); errors: "Options data did not load" with Try again (`options.js:375`), "The contracts did not load"
  with Try again (`:287`), "No option expiries came back ... nothing is wrong with your plan" (`options-picker.js:69`), "The position could not be priced" (`options.js:134`), "No positioning read right now" with the server's reason (`:416`); empty: "No usable quotes for this expiry" (`:289`), "No calls to show at this expiry" with the filter counts
  (`:301`), "No idea fits" (`options-panels.js:164`), "No daily bars" (`options.js:522`), "No setups match these filters." (`setups.js:274`); the readings strip draws nothing when it has no cells (`options.js:92`). **Not-found ticker:** `D.tErr` from `/api/ticker` ("No price data found for 'X'.") through the generic `explain()` text; no dedicated state.
- **API dependencies:** `GET /api/quote/{SYM}`, `GET /api/session/{SYM}` (header, 20 s); `GET /api/earnings/{SYM}` (ttl 10 min); `GET /api/ticker/{SYM}?max_expiries=4&macro=true[&budget=N]` (ttl 2 min; repeated quietly every minute while pre, regular or after
  hours, `options.js:496-506`); `GET /api/options/{SYM}/research?side=&delta_lo=&delta_hi=&min_oi=&include_unquoted=[&expiry=][&max_spread=]` (ttl 1 min; again every 2 minutes); the same with `delta_lo=0&delta_hi=1` per template (`:191`);
  `POST /api/options/{SYM}/analyze` `{legs, slippage, fee_per_contract, days_forward}` (priced again every 2 minutes while a position is held, `:505`); `GET /api/options/{SYM}/picker?thesis=&hold_days=&max_premium=[&target=][&invalidation=][&through_event=true]`;
  `GET /api/seasonality/{SYM}`, `GET /api/relperf/{SYM}`, `GET /api/patterns/base-rates` (timeout 150 s) when the patterns panel opens (`:442`); `GET /api/setups/catalogue`, `GET /api/setups?symbols=&timeframe=&direction=&status=[&presets=][&params=][&provisional=1]`,
  `GET /api/setups/{SYM}/detail?...`, `GET /api/setups/{SYM}/options?...` (`setups.js:113-148`); `GET /api/validation` (track-record lines, `core/track.js:77`); `POST /api/watches` (an alert). No model.
- **Preferences and storage:** `optic.options.filters.v1` (side, delta, maxSpread, minOi, unquoted, slippage, fee), `optic.options.group.v1`, `optic.entry.budget.v1` (personal), `optic.v2.picker.v1` (personal), `optic.setups.view.v1`, `optic.setups.params.v1`,
  `optic.v2.paper.draft.v1` (written by OP-09), `optic.panels.open` and `optic.panels.hidden.v1` for the third group's sections (view "swing"), the in-memory `KEPT` position (`options.js:46-48`).
- **Risks:**
  - R-OP-1 (a) **P0** "Strike and entry" reads as an order ticket. When the plan is actionable it prints Contract, **Limit price** with "never above N", Cost per contract, Breakeven, "If the target is hit" (a return %), "If IV drops 20%", then "Setups and where each stands", **Target**, **Stock stop**, "Typical time"
    (`options-panels.js:208-217`; `order_guidance` built in `app/analytics/entry.py:1004-1030`). The server's headline hedges ("An example contract for this setup ... Picked by Optic's rules from the chain, not a recommendation to trade", `entry.py:1139,1154-1155`) but the table the reader reads is the order. It sits in "Setups and strategy" under a
    subtitle that says "not recommendations" (`options.js:390`), and the swing notice that says "limit prices, stops and targets ... are model output" (`core/legal.js:23`) is at the foot of the page (R-FR-6). Suggested: label it "Worked example", drop "never above" and "Limit price".
  - R-OP-2 (a) **P1** "Pick a contract" ranks up to three contracts for a stated view with "Fit N of 100", defaults to "Expect a rise" and $500 (`options-picker.js:16,28-65,110`) and offers "Practice this trade" (`:64`); the section's own copy is "Optic shows up to three contracts that fit, or says none does" (`:110`).
    It is personalised to the reader's stated plan; the hedges are in a fold (`how(...)`, `:76`).
  - R-OP-3 (a) **P1** "Ideas" has two groups named "Buy calls or puts" and "Strategies" with legs, prices, "Most it can make", "Most it can lose" and a budget chooser "Most you'll risk on one contract" (`options-panels.js:157-180`). The closing line says "Example structures for this setup ... Model output, not a recommendation to trade" (`:165`).
  - R-OP-4 (a) **P2** "Swing setups" lists Bullish or Bearish rules with Status (Armed, Triggered), a trigger level and an invalidation level per row and an "Alert me when this triggers" button (`setups.js:248-262,233`), under the line "nothing here places a trade, and every rule is a hypothesis to test" (`options-panels.js:386`).
  - R-OP-5 (c) **P1** two statements about what 50 means: Options says "50 is no edge either way" (`options-panels.js:229`; also `ui/score.js:4`), while the Overview says "50 is each model's neutral midpoint ... it is not a measured break-even. Neither score ... has been shown to predict returns" and records why it stopped saying "no edge"
    (`overview-research.js:497-500,627`). The same composite is on both pages. Also two "Bull case / Bear case" implementations (R-OV-12).
  - R-OP-6 (f) **P1** measured-looking statistics written into prose, not read from the payload: "confirmed structures land between 51% and 55%, unconfirmed ones at or below 50%" (`options-panels.js:417`), "Every candlestick pattern here measures between 46% and 51% on samples of two to twelve thousand" (`:426`), "across 43 names and ten years" (`:411`, `:393`).
    They go stale when the base-rate cache is rebuilt, and no date or version accompanies them.
  - R-OP-7 (f) **P2** "With your slippage and fees" (`options.js:150`) labels defaults the reader never chose: slippage 0.25 and a $0.65 fee (`options.js:57`).
  - R-OP-8 (e) **P2** the readings strip is silent when it has no cells (`options.js:92`); a fund, index or coin gets the page with no kind check.
  - R-OP-9 (a) **P2** templates choose strikes for the reader by nearest delta and then price them (`options.js:202-235`): "Iron condor" is one press.
  - R-OP-10 (g) **P2** the page has three groups, fifteen sections (five, three and seven), a picker and a builder, with no level gating (`options.js:425-426`).
  - R-OP-11 (d) **P2** `addAlert` is imported and unused (`options.js:29`); `data-v2-op-form` is a form with no submit handler (it holds only selects and buttons, `:279`).
  - R-OP-12 (b) none found: every await checks `stillHere(g)` (`options.js:51-54,484-485,452,353`); the picker and the setups tool have their own sequence and symbol checks (`options-picker.js:116-118`, `setups.js:119,127`).
  - R-OP-13 (c) **P2** the picker's plan (view, holding period, premium, target, invalidation) is saved with a bare `localStorage.setItem` (`options-picker.js:17`) while the page's own budget key checks `holds(...)` (`options.js:63-70`) and `core/device.js:41` lists the picker key as personal, so on a browser holding another account's things the plan is still written and read.

---

### F-DOSSIER-04 Investing — `#/<SYM>/investing`

- **Files:** `pages/investing.js` (page), `pages/valuation-scenarios.js` (the reader's Bear, Base, Bull), `pages/dcf.js` (the fair-value model), `core/dcf-fields.js` (its 25 assumption boxes), `ui/pricechart.js` (weekly structure), `ui/chart.js`, `ui/score.js`,
  `core/track.js`, `core/instrument.js`.
- **Purpose:** the long-term picture: a trend score and what it is built from, return and risk, weekly structure, drawdown, the multiple against its own history, a fair value range with stars, a discounted cash flow model the reader can edit, the reader's own
  scenarios, and accumulation levels. A fund gets "What its holdings cost" instead of the company valuation blocks (`investing.js:248-255,284`).
- **Auth:** guest: everything; saved scenarios and models stay in this browser. Signed in: scenarios `PUT /api/valuations/{SYM}` (`valuation-scenarios.js:67-83`), saved DCF models `POST /api/valuation-models` (`dcf.js:600-612`); both `require_user` with CSRF
  (`app/account.py:804-840`, `app/valuation/store.py:104-165`); a guest's local copies are read only while this browser holds them (`valuation-scenarios.js:33`).
- **Mode:** `can(kindOf(sym, D)).valuation` chooses company or fund blocks (`investing.js:282`).

**Sections in render order** (`investing.js:283-284`): sticky header and tab strip → "Long-term trend score, from price history" → "Return and risk" → "Weekly structure" → "Drawdown, daily" → company: "The multiple against its own history",
"Fair value and stars", "Fair-value model, discounted cash flow" (`dcf.js:802`, one node kept for the visit), "Valuation scenarios"; fund: "What its holdings cost" → "Valuation and accumulation levels". The area notice for `long` is placed after the first section (`app.js:165-176`;
`core/legal.js:24`: "A conviction score summarises historical data. It says nothing about whether this holding suits your horizon, taxes or existing exposure."). **Level gating** (`investing.js:307`): "The multiple against its own history" and "Valuation and accumulation levels"
start folded below rung 2 (Simple, Financially Literate, Adaptive), each tagged "Advanced" (`sections.js:68`); the reader's own fold choices win (`sections.js:36`). The jump strip appears (six or more sections).

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| IN-01 Interval | segmented buttons | "Weekly", "Monthly" | `investing.js:343` saves `optic.lt.interval`, repaints | |
| IN-02 Range | segmented buttons | "1Y", "3Y", "5Y", "10Y", "All" (default 5Y) | `investing.js:342` saves `optic.lt.range`; All fetches `/api/weekly-bars/{SYM}?span=max` (`:321-325`) | |
| IN-03 Style | segmented icon buttons | "Candles", "Line", "Area" (default Line) | `investing.js:344` saves `optic.lt.mode` | |
| IN-04 Technical levels | `details.menu` | "Technical levels" plus a count; checkboxes "Retracements", "Support and resistance", "Volume" | `change` → keys `optic.chart.fib.v2`, `optic.chart.sr.v2`, `optic.chart.vol.v2` ("on" / "off"), updates the chart in place (`investing.js:331-338`) | help: "Retracements of the three-year range, and support and resistance found on these weekly bars, as bands." |
| IN-05 Weekly chart | plot | the shared price chart without a toolbar | gestures as CH-25 to CH-31 (`pricechart.js`); 40 and 200 bar averages; arrow keys step each bar | hint under it: "Drag to pan, scroll or pinch to zoom, arrow keys to step through each week." |
| IN-06 Milo buttons | buttons | "Ask Milo about this score", "...the multiple", "...fair value", "...these scenarios", and four to six model questions (IN-14) | draft only (`investing.js:55,76,211,235,260`) | |
| IN-07 Folds | `details` | "Revenue growth, last 8 quarters"; "Revenue and the multiple, by fiscal year"; "What this range cannot say" | native | |
| IN-08 Scenario inputs, shared | text inputs | "Years ahead" (1 to 15), "Required return" (0 to 50, % a year) | form `input` → results recalculate after 350 ms (`investing.js:360-370`; `valuation-scenarios.js:20,59-65`) | an out-of-range value prints "Between LO and HI" and blocks Save |
| IN-09 Scenario inputs, own figures | `details` with two inputs | "Your own revenue (optional)", "Your own share count (optional)" (e.g. 394B, 15.2B) | same; parsed by `amount()` (`valuation-scenarios.js:26`) | opens itself when a figure is set (`:119`) |
| IN-10 Scenario cases | three fieldsets ×4 inputs and a note | Bear, Base, Bull: "Revenue growth" (−95 to 500, % a year), "Net margin" (−500 to 100, %), "Share count change" (−50 to 100, % a year), "Exit P/E" (0.1 to 1000, times earnings), "Note" (1,000 characters) | same | outputs per case: "EPS in year N", "Price then", "Value today", "Against today's price", "Price-only rate ... a year; dividends are not in it." (`valuation-scenarios.js:103-107`) |
| IN-11 Fill the base case | button | "Fill the base case from history" | `investing.js:345-358`: growth, margin, share change and, when there is one, the median P/E, to one decimal; marks them "from history" | disabled without a history growth figure (`valuation-scenarios.js:125`) |
| IN-12 Save | submit | "Save" | `investing.js:371-378` → `VS.save` (`:67-83`); status "Saved to your account just now." / "Saved in this browser just now." / "Cleared." | blocked with "Not saved: fix the boxes marked first." |
| IN-13 DCF retry | button | "Try again" (`data-dcf-retry`) | `dcf.js:768` | when the model failed to load |
| IN-14 DCF questions | buttons ×4 to 6 | e.g. "Why is SYM's model value below the market price?", "Which assumptions matter most in SYM's valuation?", "What happens to SYM's value if capital spending stays elevated?", "How much of SYM's value comes from the terminal period?", "What growth would justify SYM's price today?", "Is a DCF appropriate for SYM?" | draft only (`dcf.js:412-420`) | |
| IN-15 Missing figures | text inputs, buttons | "for example 24.4B"; candidate buttons "$X, element"; "Run the model" | `dcf.js:211-217,779-790` (`data-dcf-base`, `-suggest`, `-base-run`) | shown only when a reported line is missing; "the model does not choose for you" |
| IN-16 Sensitivity tabs | segmented buttons | "Discount rate and long-run growth", "Margin and growth", "Capex and discount rate" | `dcf.js:297-302,766` | heat map: each cell a full run, shaded by distance from the price, number always printed |
| IN-17 DCF folds | `details[data-dcf-sec]` | "The forecast, year by year", "How the discount rate is built", "From enterprise value to a value per share", "Linked income statement, balance sheet and cash flow", "Other valuation methods and when each fits", "Reported history and sources", "Formulas and conventions", "Set individual years" | native; open state kept in `V.open` (`dcf.js:762`) | |
| IN-18 Bridge | checkboxes | "Count it" per bridge line | `dcf.js:363,756-758`: reruns | |
| IN-19 Assumptions | `details` form | "Assumptions: see why each was chosen, and change any of them": 25 numeric boxes in six groups (Growth 5, Profitability 3, Reinvestment 6, Taxes 2, Discount rate 8, Cross-check 1; `core/dcf-fields.js:4-28`), three selects "Discounting" (Mid-year / End of year), "Terminal value" (Value driver / Grow the last year's cash flow), "Beta" (Adjusted toward 1 (Blume) / Raw, as measured), "Set individual years" (Revenue growth, Operating margin, Capex / revenue per forecast year) | `dcf.js:435-459,427-433,728-760`: recalculates after 350 ms (`:163`) with `POST /api/valuation/{SYM}/run` (`:165-178`) | a box shows the default as a grey placeholder and why (`kindTag`: Reported, From history, Analyst estimate, Market, Assumption, Derived, `:75-76`) |
| IN-20 Dividend and cost-of-equity form | `details` | "Assumptions for the dividend model" (up to 8 boxes: return on equity, book value growth, dividend growth, years, price-to-FFO) | `dcf.js:539-555` | only for a bank, insurer, REIT or dividend payer the server fits |
| IN-21 Reset | button | "Reset to the defaults" | `dcf.js:422-425,767` | |
| IN-22 Peers | text input and button | "Peers (optional, comma-separated)" (placeholder "for example ORCL, ADBE, CRM"); "Compare with peers" / "Compare again" | `dcf.js:468-473,487-488,770` → `GET /api/valuation/{SYM}/comps[?peers=]` | with no list: "the largest companies in the same industry within 25 times of its size, the eight closest" |
| IN-23 Sum of the parts | buttons and inputs | "Value the segments", "Recalculate", per-segment "times" boxes (EV / EBIT), "Try again" | `dcf.js:475-483,503-519,771-772` → `POST /api/valuation/{SYM}/sotp` | |
| IN-24 Saved models | input and buttons | "Name this model (optional)" (80 characters), "Save a snapshot"; per model "Rerun exactly", "Compare with now", "Use these assumptions", "Delete" then "Delete it" / "Keep it" | `dcf.js:557-666,769-778` (up to 40 locally, `:25`) | signed in: `GET/POST/DELETE /api/valuation-models`, `POST /api/valuation-models/replay` |
| IN-25 Milo proposal hooks | none (page registers `preview`, `apply`, `undo`) | | `registerValuation(VAL_API)` (`dcf.js:804,826-840`): Milo's proposal card can change the assumptions | the change happens on the card's press (Milo section); noted here because it edits this page's inputs |

- **Inputs and validation:** scenarios: ranges above, "Between LO and HI" / "A positive amount, like 394B" (`valuation-scenarios.js:59-65`); DCF boxes: a non-number answers "LABEL needs a number." (`dcf.js:118`), amounts accept B, M, K, T
  (`:139-148`), a failed run prints "The figures below are from the last assumptions that worked." (`:681`); Technical levels: none. Keyboard: native form controls.
- **Charts and tables:** weekly structure (`createPriceChart`, twelve years of weekly bars or all, monthly roll-up, 40 and 200 averages, retracement lines and support and resistance bands, `investing.js:119-163`); drawdown line; weekly P/E line with median and quartile lines;
  a fair value meter (`meter()`, `ui/chart.js:344-360`); DCF: tornado, range rows, heat maps, tables. Tables: score factors (4 columns), fiscal-year P/E (4), revenue and multiple (3), accumulation levels (4), dividend parts (4), and the model's tables. **AI-generated sections: none**
  (`investing.js:7-8`, `dcf.js:16`); only the Milo buttons.
- **Tooltips and glossary:** auto marks; `title` on buttons; no `term()`.
- **Modals, drawers, menus:** one `details.menu`; no drawer.
- **States:** loading: skeletons "Loading the long-term model" (`investing.js:69`), "Loading the multiple history" (`:210`), "Loading fair value" (`:231`), "Loading valuation inputs" (`:258`), a chart skeleton (`:110`), "Loading the fair-value model…" (`dcf.js:696`), "Loading saved models…" (`:665`);
  error: "The long-term model did not load" with Try again (`investing.js:68`); the model: its reason text plus Try again (`dcf.js:697-698`); empty: "Not enough weekly history to draw" (`investing.js:148`), "No P/E history for this company." (`:211`), "No fair value estimate for this company." (`:240`),
  "No star rating." with the reason (`:236`); a failed `/api/fair-value` or `/api/valuation-inputs` read draws **nothing** (`:230-232,258-259,313-314`). **Not-found ticker:** `D.ltErr` through the generic message; no dedicated state.
- **API dependencies:** `GET /api/quote/{SYM}`, `GET /api/session/{SYM}` (header); `GET /api/longterm/{SYM}?indices=false` (ttl 10 min); `GET /api/pe-history/{SYM}?years=10` (1 h); `GET /api/fair-value/{SYM}` (10 min); `GET /api/valuation-inputs/{SYM}` (10 min);
  `GET /api/framework/{SYM}?mode=combined` (5 min; the "business-and-price case" cross-check, `investing.js:73,318`); `GET /api/weekly-bars/{SYM}?span=max` (All); scenarios: `GET /api/valuations` (signed in, ttl 0), `PUT` and `DELETE /api/valuations/{SYM}`; model: `GET /api/valuation/{SYM}[?refresh=true]` (10 min),
  `POST /api/valuation/{SYM}/run`, `GET /api/valuation/{SYM}/comps`, `POST /api/valuation/{SYM}/sotp`, `GET/POST/DELETE /api/valuation-models[/id]`, `POST /api/valuation-models/replay`; `GET /api/validation`. A fund skips the P/E, fair value and inputs reads (`investing.js:312`). No model.
- **Preferences and storage:** `optic.lt.mode`, `optic.lt.range`, `optic.lt.interval`, `optic.chart.fib.v2`, `optic.chart.sr.v2`, `optic.chart.vol.v2` (`investing.js:38-39`); `optic.valuation.v1` (personal, guests' scenarios, `valuation-scenarios.js:17`); `optic.dcf.v1` (`{edits: {SYM: ...}, models: [...]}`, personal, `dcf.js:24,28-43`);
  `optic.panels.open` and `optic.panels.hidden.v1` (view "long").
- **Risks:**
  - R-IN-1 (a) **P1** price-target-like figures lead the model section: "Model value, base case", "Upside to the base value", "Margin of safety" and the sentence "Under these assumptions, this model estimates NAME is worth about $X a share" (`dcf.js:181-211,229-241`), beside "Fair value range", stars and "Average target ... +N%" (`investing.js:229-245`).
    The caution "It is not a price target, a forecast Optic stands behind, or a signal to buy or sell" is the last line of the section (`dcf.js:701`).
  - R-IN-2 (a) **P1** "Valuation and accumulation levels": "Levels where long-term buyers have historically stepped in" and "(golden zone)" (`investing.js:264-273`), echoed on the Overview as "Levels to reassess at" (`overview-research.js:363`). It carries "Not targets and not advice" (`:271`) and is folded below rung 2 by default.
  - R-IN-3 (c) **P1** one number, several readings: the long-term trend score is coloured by Classic's 55 and 45 here (`investing.js:77`; `ui/score.js:15`) and by the model's own bands on the Overview, which says a neutral 43 showed red under the old rule (`overview-research.js:499-500`); the model's label is "High on the trend model" here
    (`investing.js:77`) and "Strongly positive" there (`overview-research.js:546`), while "High Conviction" is a third thing, the quality-and-price label (`app/research/quality.py:956`). Three "fair value" constructs share the tab with different bases: the stars range from the company's own P/E (`app/analytics/fair_value.py:150-200`), the DCF, and the reader's
    scenarios. The page adds a "Read it beside the price" note only when the trend score and the price disagree (`investing.js:74,79`).
  - R-IN-4 (e) **P2** a failed fair value or inputs read removes its section without a word (`investing.js:230-232,258-259`).
  - R-IN-5 (f) **P2** "Analysts' average target" in the levels section has no date (`investing.js:268`).
  - R-IN-6 (b) none found: answers check `D.sym` (`investing.js:308`); the model checks symbol and sequence (`dcf.js:153,168-169`); `loadAll` writes into the state captured before its `await` and then repaints the current one (`:321-325`); its failure toast can appear after leaving (P2, trivial).

---

### F-DOSSIER-05 Earnings — `#/<SYM>/earnings`

- **Files:** `pages/earnings.js`; `pages/dossier.js` (`historyRatio`, `:151-164`), `core/reports.js`, `core/finviz.js`, `ui/bars.js`, `ui/chart.js`, `ui/states.js` (`generated`, `how`), `ui/term.js`, `core/marketTime.js`.
- **Purpose:** the next report (or the latest result), what analysts expect, the surprise and reaction record, growth, estimate revisions, analysts, what options price for the report, and an optional AI-written brief.
- **Auth:** guest reads everything except writing the brief. Writing the brief needs an account and spends one Milo message; a kept brief shows for everyone (`earnings.js:116-125`; server `app/main.py:1317-1363`). Owner: unlimited allowance (`main.py:7471-7487`).
- **Mode:** a fund or index shows "No earnings for SYM" (`earnings.js:201`).

**Sections in render order** (`earnings.js:203`): sticky header and tab strip → "The next report" or "The latest report" → "Earlier reports" → "The business behind the reports" → "Pre-earnings brief" → "Estimate revisions" → "Analyst view" → "Optic's reading of the setup" → "What options price for the report"
→ a data caveat and disclaimer line. Sections are skipped when the data is absent. Area notice `earnings` (by source at the foot, R-FR-6, `core/legal.js:26`). **Level gating:** "What options price for the report" starts folded below rung 2 (`earnings.js:237`), tagged "Advanced".

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| ER-01 Write the brief | button | "Write the pre-earnings brief" | click → `loadBrief()` (`earnings.js:238,216-224`) → `POST /api/earnings/{SYM}/brief` | shown only when none is kept and the server says it can write (`:122`) |
| ER-02 Sign in | link | "Sign in or create an account" | `#/signin` (`:119`) | on an `auth` error |
| ER-03 Brief retry | button | "Try again" | `retry.brief` → `loadBrief()` (`:249`) | |
| ER-04 View data | `details` ×2 | "View data" (surprise table; growth tables) | native (`:90,159`) | |
| ER-05 Option folds | `details` | "How this works" (`how()`) | native (`:112`) | |
| ER-06 Ask Milo | buttons | "Ask Milo about the event pricing", "Ask Milo about the analysts" | draft only (`:105,169`) | |
| ER-07 Terms | term buttons | "earnings per share", "EPS", "consensus", "earnings report", "implied move", "straddle", "implied volatility" | `term()` popovers (`:52,56,105,109`) | |
| ER-08 Charts | SVG with hover | EPS estimate against reported, price move in the reaction session, report-day move against what options price, revenue and net income, estimate change over 90 days | `ui/bars.js` (`signedBars`, `groupedBars`) | each has a text note per bar |
| ER-09 Section chrome | see F-DOSSIER-00 | chips, Expand all, Collapse all, Panels | `sections(main, 'earnings', ...)` (`earnings.js:237`) | |

- **Inputs:** none. **Charts and tables:** grouped bars (EPS estimate, reported, with Beat, Miss or In line under each quarter), reaction bars, report-day size against a reference line, revenue and net income with hollow estimate bars, revision bars; tables: surprise history (8 columns), growth quarters and years, what analysts expect, estimate revisions (6), analyst ratings by month (6).
- **AI-generated section: the Pre-earnings brief** (the only paid call the Dossier pages themselves make; Milo's own Send is separate).
  - Request: `GET /api/earnings/{SYM}/brief` (free; ttl 5 min; reads a kept brief, never writes, `main.py:1282-1314`; `earnings.js:211-215`) then `POST /api/earnings/{SYM}/brief` (only on the button; timeout 90 s; `earnings.js:216-224`).
  - Model and prompt: `claude-opus-5-5` (`app/ai.py:55`); `EARNINGS_PROMPT` (`ai.py:1696-1744`): a newsletter voice, five fixed "## " headings ("The setup", "What the numbers have been doing", "The track record", "What the market is charging", "Where it leaves you"), "Take a clear stance. Leaning bullish, leaning bearish, or genuinely two-sided",
    "Frame it as what the data supports, not as an instruction", and hard rules: only figures in the DATA block, no invented narrative, "No price targets of your own, no position sizing, no entries or exits, no telling the reader to buy or sell". Input: `facts` from `_earnings_brief_facts` (the earnings analysis, recent filings, profile),
    pruned and cut at 60,000 characters (`ai.py:2050`), up to 4,000 output tokens (`:1829`).
  - Output handling: JSON parsed; a stance outside the three allowed values is blanked; trailing bare headings dropped (`ai.py:2067-2095`). **There is no check that every number appears in the facts or that no advice wording slipped through**; the rules are in the prompt only. The page shows the stance as a label above the headline, then the paragraphs (bold kept, everything else escaped, `core/format.js:119-122`),
    then `generated()`: "Written by an AI model from the figures, X ago. It interprets them and can be wrong; the figures are the record." (`ui/states.js:24-29`) and the server's method and disclaimer ("A reading of published data, not advice and not a recommendation ...", `ai.py:2097-2106`).
  - Cache: memory `_EARNINGS_CACHE` keyed "SYM:<next report date>", 64 entries, TTL 21,600 s (env `EARNINGS_BRIEF_TTL`); the same on disk through `ai_store` so a deploy does not repay (`ai.py:1826-1829,1971-1996`); one writer per key at a time, a second request waits and is served the first's brief (`:1999-2009`, `main.py:1337-1341`).
  - Guards: CSRF (`main.py:1331`); server ceiling of 30 new briefs per rolling day (`EARNINGS_BRIEFS_PER_DAY`; `ai.py:1764-1796`, counted from the on-disk ledger, checked before the reader's allowance, `main.py:1343-1346`); then the reader's allowance `_spend_guard` (`main.py:7468-7515`) and `_count_question` (`:1349`).
    Cost note in code: at most about $0.14 a brief at list price (`ai.py:1756-1759`).
- **Tooltips and glossary:** the seven `term()` words above; `title` on tier chips elsewhere.
- **Modals, drawers, menus:** none.
- **States:** loading: `skeleton('lines', 6, 'Loading the earnings data')` (`earnings.js:200`); error: "The earnings data did not load" with Try again (`:199`); not applicable: "No earnings for SYM / Funds and indices do not report earnings." or the server's reason (`:201`); no date: "No report date on record for SYM. There is no next report date and no latest result in the feed for this company." (`:51`);
  brief: "Looking for a brief already written..." (`:117`), skeleton "Writing the brief" (`:118`), "Writing a brief uses one Milo message, so it needs a free account. A brief someone has already written shows here for everyone." (`:119`), the limit message plus "A brief someone else writes for this report will show here." (`:120`), "The brief did not load" with Try again (`:121`), the server's reason when it cannot write or the daily ceiling is
  reached (`:123`). Sections with no data are omitted (`:128-130,147-149,166-168`). **Not-found ticker:** the generic error.
- **API dependencies:** `GET /api/quote/{SYM}`, `GET /api/session/{SYM}`; `GET /api/ticker/{SYM}?max_expiries=4&macro=true` (ttl 2 min; for the report-day move, `:242`); `GET /api/earnings/{SYM}` (ttl 10 min, timeout 60 s, `:243`); `GET` and `POST /api/earnings/{SYM}/brief`.
- **Preferences and storage:** `optic.panels.open` and `optic.panels.hidden.v1` (view "earnings"); nothing else.
- **Risks:**
  - R-ER-1 (a) **P1** the AI brief publishes a direction: a label "Leaning bullish" or "Leaning bearish" above the headline (`earnings.js:124`), a section headed "Where it leaves you", written to "Take a clear stance" (`ai.py:1696-1744`), published "unedited" (the prompt's own words) with no post-generation check (`ai.py:2067-2111`). The disclaimer is below the text.
    Directive 02 asks for structured output validation, not prompt rules alone.
  - R-ER-2 (b) **P2** a second click listener per retry: `render()` adds a `click` handler to the page node each time it runs (`earnings.js:238`) and "Try again" on an error re-renders the same node (`:249`), so after a retry "Write the pre-earnings brief" calls `loadBrief()` twice. The server serves the second from the first's lock, but both requests
    pass `_spend_guard` before the lock (`main.py:1343-1350`), which the route's own docstring concedes ("Two requests arriving in the same instant can still both pass the in-flight check", `:1331-1334`), so a reader's allowance can be charged twice for one brief.
  - R-ER-3 (f) **P2** the word "undefined" can print: "Ratings" is built as `${a.buys} buy, ${a.holds} hold, ${a.sells} sell` whenever there is a mean target or any ratings row (`earnings.js:168,170`), but the server sets those counts only when a ratings row exists (`app/analytics/earnings.py:866-874`).
  - R-ER-4 (e) **P2** the brief GET recomputes the whole earnings analysis to find the report date used as the cache key (`main.py:1238-1262,1302`), so opening the tab runs the analysis twice on the server (once for the panel, once for the brief key).
  - R-ER-5 (a) **P2** "Optic's reading of the setup" is a headline plus reasons (`earnings.js:63-71`), labelled "A model's reading of the figures on this page, not a recommendation."; it is fixed rules, not a model, despite the word "model".
  - R-ER-6 (b) none else: every answer checks `D.sym` (`earnings.js:239,242,244-246`) and the brief checks the state it started from (`:214,221`).

---

### F-DOSSIER-06 Financials — `#/<SYM>/financials`

- **Files:** `pages/financials.js`; `core/finviz.js` (sentences), `core/congress.js`, `ui/bars.js`, `ui/chart.js`, `core/instrument.js`, `ui/sections.js`.
- **Purpose:** the latest fiscal year in figures and words, the statements as charts and a table, segments and geography, the earnings record, ownership, short interest, corporate actions, SEC filings and House trades.
- **Auth:** guest only; nothing is personal except the period choice.
- **Mode:** a fund, index or coin gets "Financials do not apply to SYM" (`financials.js:378-383,427-431`); the tab is not listed for a fund (`dossier-frame.js:162`).

**Sections in render order** (`financials.js:371`): sticky header and tab strip → "Summary, fiscal YEAR" (five figures and a fold "What the figures say", open on wide screens) → jump list (three or more sections) → "Statements" → "Segments and geography" → "Earnings track record" → "Insider and institutional activity" → "Short interest"
→ "Corporate actions and flow" → "Recent SEC filings" → "Congressional disclosures". Each is drawn only when its data exists. No level gating; `sections(main, 'financials', {strip: false})` (`:406`) so each section folds and the Expand all, Collapse all and Panels bar shows at four or more. No area notice.

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| FI-01 Jump chips | buttons (up to 9) | "Summary", "Statements", "Segments", "Earnings record", "Ownership", "Short interest", "Corporate actions", "SEC filings", "Congress" (only those present) | `financials.js:412,410`: opens the section if folded or hidden, scrolls, focuses its heading | |
| FI-02 Jump select | select | "Jump to": "Choose a section" and the same | `change` (`:416`) | for a phone |
| FI-03 Period | segmented buttons ×2 | "Fiscal years", "Quarters" (Statements; and Segments when quarterly filings exist) | `financials.js:413-415` saves `optic.v2.financials.period.v1`, repaints, restores focus | cash flow and balance sheet stay yearly |
| FI-04 Figures fold | `details` | "What the figures say" | native (`:104`) | open at 641 px and wider |
| FI-05 Data folds | `details` | "View data" ×2, "Recent insider transactions", "Each year's total" | native | links to the Insiders page and to `#/insiders` |
| FI-06 Ask Milo | button | "Ask Milo about insiders" | draft only (`:225`) | |
| FI-07 Links | links | "Insiders page", filing form links (new tab), "Open Investing", "Open Overview" | | the last two on the not-applicable state |

- **Inputs:** none. **Charts and tables:** grouped bars (revenue, operating income, net income), margin lines, cash flow bars with a bridge, cash and debt bars, EPS and share count, segment bars and stacked fiscal-year mix, holder bars, dividend columns, short volume line, relative performance line; every chart has a one-sentence takeaway built from its own figures (`core/finviz.js`); tables: statements by period, segments, insider transactions, earnings track record, congress trades. **AI-generated sections: none.**
- **Tooltips and glossary:** auto marks; no `term()`.
- **States:** loading: "Loading the statements" (`financials.js:368`), "Reading segment filings" (`:296`), "Loading corporate actions" (`:245`); error: "The financial statements did not load" with Try again (`:367`); not applicable: "Financials do not apply to SYM" with a sentence per kind (`:380-383`); the segment read asks again up to five times at 400 ms while filings are unread (`:388-394`);
  failures of extras or congress draw nothing (`:429-430,246,275`). Missing figures say "Not reported" or give a reason ("a loss, so no growth rate", `:210`). **Not-found ticker:** the generic error.
- **API dependencies:** `GET /api/quote/{SYM}`, `GET /api/session/{SYM}`; `GET /api/ticker/{SYM}?max_expiries=4&macro=true` (ttl 2 min); `GET /api/extras/{SYM}?benchmark=SPY` (10 min); `GET /api/congress?ticker=SYM&limit=40` (10 min); `GET /api/segments/{SYM}` (ttl 0; server caches filings 30 days, submissions 6 h, `app/analytics/segments.py:56-57`). No model.
- **Preferences and storage:** `optic.v2.financials.period.v1`; `optic.panels.open`, `optic.panels.hidden.v1` (view "financials").
- **Risks:**
  - R-FI-1 (e) **P2** a failed extras or congress read removes its section silently (`financials.js:429-430`); a failed segments read after the first attempt is silent (`:393`).
  - R-FI-2 (f) **P2** the word "undefined" can print in the ownership sentence "N of the M largest holders raised their stake" if the counts are missing (`financials.js:228`).
  - R-FI-3 (a) **P2** "Squeeze potential: HIGH" and "Net buying / Net selling" are server or rule labels about future price behaviour or insider intent (`financials.js:75,88,218`); they are hedged in the text beside them.
  - R-FI-4 (b) none found: guards `D.sym` (`:388-389,419-420,427`) and one listener set per node (`main.dataset.finWired`, `:407-408`).
  - R-FI-5 (c) **P2** the same insider facts are in four places with different slices: Financials (6-month tally and 20 trades), the Chart's Insiders panel (6 trades), the chart arrows, and `#/insiders` (`financials.js:221-233`; `chart-widgets.js:234-254`).

---

### F-DOSSIER-07 News — `#/<SYM>/news`

- **Files:** `pages/news.js`; `ui/states.js`, `core/marketTime.js`, `core/format.js`.
- **Purpose:** headlines about one company, tagged and scored by fixed rules: tone, tier, catalyst type, a two-lane timeline.
- **Auth:** guest only.

**Sections in render order** (`news.js:49-69,74`): sticky header and tab strip → one section "News and catalysts": tone line and method fold, "Ask Milo about the news", earnings warning and held-feed notes, timeline, key, "Catalyst types found" chips, "About SYM N" list, "Market context N" list, a fetch-time line,
fold "How these are ranked". No gating, no area notice, no folds API.

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| NW-01 Catalyst chips | toggle buttons | one per type found, "Type N, lean" | click sets the filter and repaints, focus kept (`news.js:87-92,62`) | `aria-pressed` |
| NW-02 Show all | text button | "Show all" | same (`news.js:62`) | only while filtered |
| NW-03 Headline links | links | each title | new tab, `rel="noopener"` (`news.js:43`) | |
| NW-04 Ask Milo | button | "Ask Milo about the news" | draft "Which recent SYM headlines matter for the stock, and why?" (`news.js:58`) | |
| NW-05 Folds | `details` ×2 | "How this works"; "How these are ranked" | native (`news.js:57,66`) | tiers and their rules, matching terms, limits ("cannot read sarcasm, judge a source or know what the market already priced") |
| NW-06 Timeline | SVG, `role="img"` | markers ▲ ▼ ● sized by tier | none (a picture of the list below, which has every link) (`news.js:35-36`) | each mark has a `<title>` |

- **Inputs:** none. **Charts and tables:** the timeline only. **AI-generated: none** (`news.js:1-3`; the tone is a fixed word list with negation and future-tense rules). **Tooltips:** `title` on tier pills and tone chips (the scored terms are the evidence, `news.js:42`).
- **States:** loading `skeleton('rows', 5, 'Loading headlines')` and error "The headlines did not load" with Try again (`news.js:74`); empty "No headlines for this company right now" with the server's reason (`:52`); "Not scored" for a headline with no scored term (`:42`). **Not-found ticker:** the generic error.
- **API dependencies:** `GET /api/quote/{SYM}`, `GET /api/session/{SYM}`; `GET /api/ticker/{SYM}?max_expiries=4&macro=true` (the `news` block, ttl 2 min; the server reads Yahoo news cached 10 minutes, `app/providers/yf.py:742`, 12 articles by default, `app/news.py:994`). No model.
- **Preferences and storage:** none (the filter is a module variable, reset on each render, `news.js:78`).
- **Risks:**
  - R-NW-1 (b) **P2** an error can land on another symbol's page: the success path assigns into the state captured before the `await` (`news.js:94`), but the `catch` writes `D.err` into whatever `D` is **now** (`:95`), so a slow failure for the previous ticker marks the next ticker's page "The headlines did not load" even when its own data arrives
    (the painting rule `D.err ? failed(...) : ...` puts the error first, `:74`).
  - R-NW-2 (a) **P2** "Bullish overall, net +0.8" and per-headline "Bullish wording" are directional words (`news.js:42,57`); the fold says they describe wording, not the price (`:57`).
  - R-NW-3 (c) **P2** headlines appear in four places with different counts: Overview About (6), Advanced (3) and the drivers fold (1), the Chart News panel (7), and here (up to 12) (`dossier.js:286`, `overview-research.js:738`, `chart-widgets.js:177`).

---

### F-DOSSIER-08 Sheet — `#/<SYM>/sheet`

- **Files:** `pages/sheet.js`; `ui/chart.js` (the one chart), `core/marketTime.js`, `core/format.js`.
- **Purpose:** a printable two-page research sheet; each figure tagged Reported, Estimate or Optic; opened from "Export", printed or saved as a PDF by the browser.
- **Auth:** guest; "Private holdings are never included" (`sheet.js:118`).

**Sections in render order** (`sheet.js:116-119`): an action bar, then `article.sheet` with page 1 ("The business", "Key financials", "Valuation", the P/E line, "Earnings", "Price, past year") and page 2 ("Chart structure", "Options positioning", "Evidence for and against" in Supporting and Conflicting, "Principal risks", "Sources").
There is no header, tab strip or live price on this route.

**Controls**

| Control | Kind | Label or text | Action (handler, file:line) | Notes |
|---|---|---|---|---|
| SH-01 Back | link | "Back to the Dossier" | `#/SYM` (`sheet.js:116`) | |
| SH-02 Print | button | "Print or save as PDF" | click → `window.print()` (`:117,135`); disabled until ticker, fair value and earnings have answered (`:115`) | "Two pages, Letter or A4. Private holdings are never included." |

- **Inputs, charts, AI:** none; one closing-price chart (past year, 680 by 140). **States:** loading `skeleton('lines', 8, 'Gathering the figures for the sheet')` and "Gathering the figures…" (`:118-119`); error "SYM's research sheet did not load" with Try again only when the ticker read failed (`:114`); a missing figure is "Not reported" or a sentence ("No annual statements in the feed for SYM.", "No valuation range
  for this company.", "No report date in the feed.", "No usable option chain when this was generated."). **Not-found ticker:** the error above.
- **API dependencies:** `GET /api/ticker/{SYM}?max_expiries=4&macro=true`, `GET /api/session/{SYM}`, `GET /api/quote/{SYM}`, `GET /api/fair-value/{SYM}`, `GET /api/earnings/{SYM}`, `GET /api/longterm/{SYM}?indices=false` (`sheet.js:129-134`). No model.
- **Preferences and storage:** none.
- **Risks:**
  - R-SH-1 (b) **P1** a previous symbol's answer can fill this sheet: `step` applies each answer with `D[k] = d` inside the `.then` callback (`sheet.js:128`), where `D` is read when the callback runs, not when the request started, and there is no symbol check. Open the AAPL sheet, move to MSFT's before AAPL's `ticker` read returns, and AAPL's payload is written
    into MSFT's state; whichever of the two answers arrives last stays. The title and symbol are MSFT's, the figures can be AAPL's, and the page is meant to be printed and shared. Suggested: capture `const box = D` and write `box[k]`, and check `D.sym === sym` before painting.
  - R-SH-2 (f) **P2** "Generated DATE, TIME" is the moment of rendering (`new Date()`, `sheet.js:107`), not the time the figures were read; with the client cache the figures can be older, and "Quote at TIME, delayed about 15 minutes" is a literal (`:63`).
  - R-SH-3 (e) **P2** a failed fair-value, earnings, longterm or session read becomes an empty object (`:128`) and reads as absence: "No valuation range for this company." (`:77`) for a read that failed.
  - R-SH-4 (a) **P2** "so results have less room to disappoint" (`sheet.js:104`) is a prediction in the risks list; the valuation line is hedged ("A reading against its own history, not an intrinsic value or a forecast", `:76`).
  - R-SH-5 (d) **P2** `render()` adds a click listener each time it runs (`:135`), so a retry leaves two and one press calls `window.print()` twice.

---
## 3. Dossier pipeline map

Selection → requests → normalisation → AI → caching → render → mode state → errors → sources. The Overview is mapped in full; the other tabs reuse the same client (`core/api.js`) and the same `/api/ticker` snapshot, so only their differences are noted.

### 3.1 Selection (symbol, tab, kind)

- The address is parsed in `core/router.js:20-44` (upper-case, `BRK.B` to `BRK-B`, pattern `^[A-Z0-9.^=-]{1,12}$`, tab slug, `sheet`). A bad symbol is the "Page not found" page (`bridge.js:17-24`); an unknown tab slug is the Overview (`router.js:43`).
- Ways in that are **not** audited here: the top-bar search and palette (`ui/palette.js`, `/api/search`), Home panels, watchlist rows (the row drawer's "Open the Dossier" button is `company.js:120`), Milo links, the ⋯ menus; all end in `hrefFor(view, sym)` (`nav.js:56-64`).
- A symbol's kind (company, fund, index, crypto, unknown) is learnt from the session profile or the quote's `quote_type` (`core/instrument.js:12-30`) and remembered for the visit; an unknown kind is treated as a company, and the tab strip redraws when the kind is learnt (`dossier-frame.js:171-177`).
  Only `fund` changes the Overview's layout (R-OV-14).
- Recents: the Overview adds the symbol after a quote confirms it (`dossier.js:393`); the other six tabs add it when they start (R-FR-4).

### 3.2 Requests, in the order the Overview issues them (`dossier.js:374-413`)

The thesis read starts first, at the first paint, for a signed-in reader (`thesis.js:315-318`, called from `dossier.js:362,385`); then items 1 to 12 start **together**, not one after another, and each answer triggers a complete repaint of the page (`dossier.js:389`). Item 13 repeats forever while the tab is visible.

| # | Client call (ttl, timeout) | Server handler | What it returns (as the Overview reads it) | Model? | Server cache |
|---|---|---|---|---|---|
| 0 | `GET /api/theses` (signed in; ttl 0 forced) | `app/account.py:564` | `{theses: {SYM: {bull, bear, catalysts, invalidation, snapshot, saved_at}}, count, limit}` | no | none (database) |
| 1 | `GET /api/quote/{SYM}` (20 s, 15 s; `dossier.js:393`) | `main.py:1144-1171` | `{ticker, available, quote}` or `{available: false}` (plus `unreachable: true` when the source failed); quote: price, change, percent, name, market cap, volume, 52-week range, P/E, yield, beta, market state, trade time, delay | no | no route cache; provider quote cache: Yahoo 30 s (`providers/yf.py:732`), Tradier 5 s (`tradier.py:50`); a `Server-Timing` header |
| 2 | `GET /api/session/{SYM}` (60 s, default 20 s; `:394`) | `main.py:3316-3363` | `{ticker, session {phase, label, is_regular, last_close}, prices {phase, extended}, profile {name, summary, industry, sector, category, fund_family, is_fund, is_company, summary_source}, name}`; the 10-K business text replaces Yahoo's when EDGAR has one | no | profile 1 day (`yf.py:1716`); the EDGAR lookup runs in the background and lands on a later poll (`main.py:3350-3354`) |
| 3 | `GET /api/ticker/{SYM}?max_expiries=4&macro=true` (2 min, 60 s; `:395-398`) | `main.py:1086-1118` → `_swing_snapshot` (`:596-975`) | one large payload: `quote`, `verdict` (swing composite), `technicals` (two years of daily bars, averages, RSI, MACD, support and resistance), `structure`, `patterns`, `gex`, `vol_surface`, `iv_rank`, `flow`, `greeks`, `news`, `entry_plan`, `company` (financials, margins, growth, earnings history, short interest, ownership), `earnings_momentum`, `naked_ideas`, `strategy_ideas`, `cases`, `filings`, `sector_confirm`, `pulse`, `why`, `whats_next`, `digest`, `disclaimer`, `data_source`, `data_caveat`, `generated_at` | no | none at route level; its legs use provider caches (history 300 s `yf.py:741`, news 600 s `:742`, chain 60 s `:733`, filed statements 6 h `:763`); tonight's overnight print is attached to a copy (`main.py:1121-1138`) |
| 4 | `GET /api/framework/{SYM}?mode=combined` (5 min, 60 s; `:399`) | `main.py:1205-1212` → `app/research/service.py:147` | `{available, long_term {quality, valuation, chart, conviction, accumulation, loss_paths, ...}, swing {grade, setup, plan, objections, why, ...}, earnings {pre or post}, combined {lines, verdict, note}, freshness, data {gaps, sources}, method_version, policy, limitations}` | no ("Deterministic, no model call", `main.py:1196-1200`) | in-memory `_CACHE["SYM:combined"]`, 600 s, not stored when any source has a gap (`service.py:34,162-166,237-240`); fetch budget 45 s (`:29-33`); **saves a forecast on read** (R-OV-13) |
| 5 | `GET /api/fair-value/{SYM}` (10 min, 30 s; `:400`) | `main.py:5423-5427` | `{fair_value {low, mid, high, wide, basis, limits}, stars {stars, word, rule, note}, analysts, dividend, morningstar}` | no | provider caches |
| 6 | `GET /api/longterm/{SYM}?indices=false` (10 min, 45 s; `:401`) | `main.py:1738-1768` | `{generated_at, holding {conviction_score, conviction, conviction_factors, conviction_scale, long_trend, horizons, risk, drawdown, valuation, valuation_history, accumulation_zones, ...}, close_defence}` | no | news read cached 10 min (`main.py:1750`); price history provider cache |
| 7 | `GET /api/earnings/{SYM}` (10 min, 45 s; `:402`) | `main.py:1174-1189` | `{next_report, latest_result, surprise, revisions, growth, analyst, pricing, implied, verdict, extended_hours, generated_at}` | no | provider caches (earnings dates 1 h, estimates 1 h, history 6 h: `yf.py:1275,1829,1664`) |
| 8 | `GET /api/digest/{SYM}` (5 min, 30 s; `:403`) | `main.py:2086-2105` | `{available, changed[], explanations[], period, describes, session_date}` | no ("Fixed rules, no model call", `main.py:2070-2072`) | `_DIGEST_CACHE[("one", SYM, period.latest)]`, 900 s, cleared when over 300 entries (`main.py:2074-2075,2093-2102`) |
| 9 | `GET /api/segments/{SYM}` (10 min, 60 s; `:404`) | `main.py:6459-6470` | `{available, tables[...], quarters, filings_read, filings_unread}` read from each filing's XBRL | no | SEC submissions 6 h, filing documents 30 days, parsing capped per call (`analytics/segments.py:56-57`) |
| 10 | `GET /api/extras/{SYM}?benchmark=SPY` (10 min, 30 s; `:406`) | `main.py:5656-5680` | `{actions {dividends, splits, ...}, short_volume, relative}` | no | actions 6 h, short volume 4 h (`analytics/extras.py:130,202`) |
| 11 | `GET /api/stage?symbol=SYM` (30 min, 45 s; `:409-411`, asked once more after 30 s on failure) | `main.py:6203-6220` | `{available, stage, name, label, transition, transition_short, explain, limits}` | no | none at route level |
| 12 | `GET /api/validation` (30 min, 60 s; `core/track.js:77`, started `dossier.js:412`) | `main.py:2181-2200` | `{claims {composite, regime, walls, setups}, history {rules}, as_of}` | no | in-memory 6 h (`main.py:2127-2128,2189-2198`) |
| 13 | `GET /api/quote` and `GET /api/session` again, forced (every 20 s from 04:00 to 20:00 ET on weekdays, else 5 min; hidden tab paused; `dossier-frame.js:79-101`) | as 1 and 2 | merged into the state by `fresher` | no | as 1 and 2 |
| 14 | `<img src="/api/logo/{SYM}">` | `main.py:1860` | an image | no | Optic fetches and keeps logos (`ui/symbols.js:7`) |

Other tabs add: Chart (bars, studies, panels: F-DOSSIER-02), Options (`/api/options/...`, `/api/setups...`, `POST /api/options/{SYM}/analyze`: F-DOSSIER-03), Investing (`/api/pe-history`, `/api/valuation-inputs`, `/api/valuation...`: F-DOSSIER-04), Earnings (`/api/earnings/{SYM}/brief`: F-DOSSIER-05), Financials (`/api/congress`: F-DOSSIER-06). Server caches for those: setups scan, key = symbols, timeframe, presets, directions, overrides, provisional, status and the minute, 60 s, cleared past
64 entries (`main.py:2277-2280,2517-2531`); intraday bars 30 s at the provider (`yf.py:1404`); chain 60 s (Yahoo) or 8 s (Tradier) (`yf.py:733`, `tradier.py:51`); the brief 6 h (below).

### 3.3 Normalisation (what is changed between the response and the page)

- Kind and layout: `learn`, `kindOf` (`core/instrument.js:12-40`).
- Quotes: `fresher(a, b)` keeps the later trade and fills gaps from the other (`dossier-frame.js:55-59`; used `dossier.js:393,396`, `dossier-frame.js:90`, `options.js:454,484`). Key figures read `ticker.quote` instead (`overview-research.js:451`).
- Series: `series()` keeps finite closes above zero (`dossier.js:52-56`); `windowOf` and `windowStart` cut by sessions for a market with sessions and by calendar months for one that trades every day (`dossier.js:43-45`; `overview-research.js:33-50`).
- Missing values: `num`, `money`, `signed`, `compact`, `shortDate` return "n/a" or an empty string, never zero (`core/format.js:11-70`); `isNum` refuses blanks, booleans and arrays (`:11-12`).
- Prose from the server: `clean()` rewrites provider exception text into plain sentences (the pattern list is `core/format.js:91-106`), replaces em dashes with colons and ISO dates with "Nov 2, 2026" (`:108-113`).
- Scores: `score100` places a score on 0 to 100 (`:136-142`): the short term is 50 plus half the composite (`overview-research.js:516-520`); the long term uses the model's own minimum and maximum (`:538-564`).
- Rules over payloads, each with fixed cut-offs the page lists in "How this page is built" (`overview-research.js:744-753`): `businessRead`, `priceRead`, `valuationRead`, `factors`, `drivers`, `events`, `nextSteps`, `keyStatRows`.
- One context object per paint, `OR.context(...)` (`overview-research.js:765-769`; `dossier.js:343`).

### 3.4 AI generation

- **On any Dossier page load, no request reaches the Anthropic API.** Checked from the code side: every handler in 3.2 is a fixed-rule or arithmetic builder, `app/research`, `app/analytics` and `app/digest.py` import no model client (searched), and the route comments say so (`main.py:1196-1200,2070-2072`).
- **The Earnings brief** is the one paid Dossier call, user-pressed: F-DOSSIER-05 gives the model, prompt, output handling, cache, guards and cost.
- **Milo:** every "Ask Milo" button on these pages drafts a question into the panel and sends nothing (`ui/milo.js:320-322,1042`; `app.js:242-246`). A press of Send posts to `POST /api/chat` or `/api/research` (`ui/milo.js:833-838`) with the page's registered context (`provideContext`: Overview `dossier.js:378`, Chart `chart.js:706`, Options `options.js:473`, Investing `investing.js:304`,
  Earnings `earnings.js:234`, Financials `financials.js:404`, News `news.js:85`) and `mode: prefs.knowledge()`. That belongs to the Milo section. Two Dossier-specific facts: the Overview's context includes the reader's thesis conditions and note (R-OV-15), and the DCF registers hooks through which Milo's proposal card can edit its assumptions (IN-25).

### 3.5 Caching, client and server

- Client (`core/api.js:73-107`): an in-memory `Map` keyed by the request path; `get(path, {ttl, force, timeout})`. Fresh within `ttl`: returned. **Older: the old copy is returned at once and a refresh starts in the background; its result is kept for the next call and delivered through `onUpdate` only if the caller passed one (no Dossier call does).** A call
  in flight is shared. A failure deletes the entry (`:103-105`); an answer containing `building` is not kept (`:102-103`). `invalidate(prefix)` is used by the Overview's and Earnings' retries (`dossier.js:440`, `earnings.js:249`). The cache lives until the page is reloaded.
- TTLs the client asks for: quote 20 s, session 60 s, ticker 2 min, framework 5 min, digest 5 min, fair value, longterm, earnings, segments and extras 10 min, stage 30 min, validation 30 min, bars 1 h, intraday 1 min (sections 2 and 3.2).
- Server caches are listed with each request in 3.2; none of them is keyed by, or returns, a "data as of" that the client compares: the client trusts each payload's own `generated_at` where it prints one.

### 3.6 Render

- `paint()` rebuilds the whole Overview with `draw(main, html...)` after every answer (`dossier.js:331-372`), about a dozen times in a first load. It keeps scroll position, the focused control (answers, range, Watch, the switch), the open `details` and open change rows (`:334-341,364-371`); the thesis section is a persistent node re-parented into its slot (`thesis.js:305-331`); the chart redraws from the cached series
  (`dossier.js:82-97`; `ui/chart.js:362-396`, the draw-on runs once per page visit).
- Folds are kept by summary text, not by identity (R-OV-5). `ui/sections.js` re-applies its folds in a MutationObserver after every redraw (`sections.js:218-225`); `glossmark` marks glossary terms after every redraw (`glossmark.js:96-104`).
- A refresh never moves the reader's place by design (`core/poll.js:1-11`): only `.dh-price` and `.dh-state` are swapped (`dossier-frame.js:94-96`).

### 3.7 Analysis mode state

- One stored value, `optic.knowledge.v1`, read at paint time (`prefs.js:110`; `dossier.js:343`); changes arrive by the `knowledge` event (`prefs.js:123`; `dossier.js:384`); a module flag `advMoved` makes the next paint apply the switch to the folds (`dossier.js:35,333`). There is **no separate "analysis data" versus "presentation mode" state**: the content is the same at both settings, so there is no
  request to repeat when the switch moves (it reads the payloads already loaded), and no paid call is repeated by it.
- Not stored per ticker or per tab; written by four other places (section 1; R-FR-1).

### 3.8 Errors

- `ApiError(kind, status, message, body)` with kinds offline, timeout, auth, forbidden, notfound, limit, server, bad, cancelled (`core/api.js:11-32,49-56`); a response with `X-Optic-V2: closed` raises an event (`:62`). Messages: `explain()` (`:126-141`) and `failed()` (`ui/states.js:32-41`): the server's own sentence when it sent one, else a standard line; for `notfound` with a server sentence the text ends with "If the data source is refusing requests, it shows here as soon as it answers." (`api.js:135-137`), which also prints for a symbol that does not exist.
- Page-level: a thrown render error is "This page did not load" with the message (`app.js:185-188`); a module that cannot be fetched says "Its code could not be fetched" (`app.js:146-148`).
- Per tab: see the States line of each entry; the Overview alone has a "no listing" state and splits "source did not answer" from "not found" (`dossier.js:393`); six tabs leave a failed quote as a blank price (R-FR-3); several sections vanish on failure (R-OV-9, R-IN-4, R-FI-1).

### 3.9 Sources and times shown to the reader

| Where | What it says | File:line |
|---|---|---|
| Header price | "Close of Fri Oct 23", "Delayed N minutes, last trade TIME", "Live, last trade TIME", an extended print with its time | `dossier-frame.js:42-48,143-145`; `core/marketTime.js:51-58` |
| Overview chart | "Daily closes, split-adjusted, through DATE. Source: Yahoo Finance[, Tradier, with Yahoo Finance where it has no data]. Marked: E ..., D ..., S ... Next report DATE." | `overview-research.js:296-299` |
| Overview four questions | method and policy ids, the framework's freshness text, "Not loaded: GAPS" | `overview-research.js:444` |
| Overview Optic Score | "Worked out X ago" only past 60 minutes or 24 hours; what 50 means | `overview-research.js:532-533,560-561,627` |
| Overview Key figures, Bull and bear | no source or time of their own | R-OV-8 |
| Overview "How this page is built" | sources, cut-offs and "Nothing here is a recommendation to buy or sell" (inside the closed Advanced fold) | `overview-research.js:744-753` |
| Options | "Quotes read TIME, delayed about 15 minutes" in session or "from the last session the feed has"; the feed caveat in a fold | `options.js:131,155,328` |
| Earnings | "Read X ago. Estimates, reported EPS and prices from Yahoo Finance, N quarters of history." | `earnings.js:58` |
| Financials | "The company's statements as Yahoo Finance carries them", fiscal-period labels, "Source: House Clerk disclosures", "Based on N of the M most recent filings" | `financials.js:162,279,335` |
| News | "Optic fetched this list at TIME" | `news.js:65` |
| Sheet | a tag per figure (Reported, Estimate, Optic) and a Sources paragraph with a generation time | `sheet.js:16-18,107` |
| Brief | "Written by an AI model from the figures, X ago ...", method, disclaimer | `ui/states.js:24-29`; `ai.py:2097-2106` |

### 3.10 Does a response for a previous ticker land on the new page?

| Page | Request identity | AbortController | Symbol check before render | Gap |
|---|---|---|---|---|
| Overview | a new `D = {sym}` per render; each answer applies only `if (D.sym === sym)` and repaints only then (`dossier.js:377,389`); `live` flag (`:332`); the stage retry and the poll check too (`:410`, `dossier-frame.js:88`) | none (R-FR-2) | yes | A to B to A: an answer for the first A applies to the second A's state (same symbol, harmless) |
| Chart | `barSeq` plus `D.sym` (`chart.js:105-106,151,154,192`); `box = D` for the ticker promise (`:203-204`); widgets and studies by box identity (`chart-widgets.js:100-105`, `chart-studies.js:47-52`); `core().then` and `loadTicker` check `D.sym` (`:708,715`) | none | yes | a note written after an `await` (R-CH-2) |
| Options | a `GEN` counter, `stillHere(g)` after every `await` (`options.js:51-54,452-458,484-492`); `B.seq`, `R.seq`; picker `S.seq` (`options-picker.js:116-118`); setups `SS.sym` (`setups.js:119,127`) | none | yes | none found |
| Investing | `step` checks `D.sym` (`investing.js:308`); the model `V.sym` and `V.seq` (`dcf.js:153,168-169`) | none | yes | none found |
| Earnings | `D.sym` checks (`earnings.js:239,242,244-246`); the brief checks the state it started from (`:214,221`) | none | yes | duplicate listener (R-ER-2) |
| Financials | `D.sym` checks (`financials.js:388-389,419-420,427`) | none | yes | none found |
| News | success path writes into the state captured before the `await` (`news.js:94`); error path writes into the current state (`:95`) | none | partly | R-NW-1 |
| Sheet | none | none | **no** | R-SH-1 |

### 3.11 Where stale or wrong information can enter

1. **Any-age cached answers** painted first, refreshed for the next visit (`core/api.js:93-100`), with no page using `onUpdate` (R-OV-6). On a revisit in one page load every Overview section can be older than its TTL; only the header price is forced fresh.
2. **The body and the header disagree** by design: Key figures and the Optic Score come from the snapshot, the header from the merged live quote (R-OV-6).
3. **Literals that state a fact about data**: "quotes delayed about 15 minutes" (`dossier.js:283`, `sheet.js:63`) and the base-rate statistics in prose (`options-panels.js:393,411,417,426`).
4. **Late writes to the wrong state**: `sheet.js:128`, `news.js:95`, `chart.js:128`.
5. **Payload ages differ on one screen**: `ticker` (2 min), `framework` (up to 10 min server plus 5 min client), `longterm` (10 min), `digest` (up to 15 min server plus 5 min client), `stage` (30 min), each stamped by its own `generated_at` that the page does not compare or print except past 60 minutes (short-term score) and 24 hours (long-term).
6. **Read-through side effects**: a forecast saved by a GET (R-OV-13).
7. **Failure that looks like absence**: a failed fair-value, inputs, digest, segments, extras or congress read draws nothing (R-IN-4, R-FI-1, R-SH-3), and a failed quote leaves the price blank (R-FR-3).
8. **Silent substitutions in bars**: a missing open, high or low becomes the close (R-CH-3); the live tick mutates the forming bar from the quote (R-CH-8).

---

## 4. Index of P0 and P1 risks (this section)

| ID | P | Class | One line | Evidence |
|---|---|---|---|---|
| R-OV-1 | P0 | a | Overview "Is there a trade?" card: grade S/A/B or "Avoid"; its fold prints entry zone, targets, invalidation and a sizing sentence | `overview-research.js:378-395`; `swing_setup.py:462-537` |
| R-OP-1 | P0 | a | Options "Strike and entry": Limit price, "never above", Target, Stock stop, return "if the target is hit" | `options-panels.js:208-217`; `entry.py:1004-1030` |
| R-OV-2 | P1 | a | "Taken together": "a poor trade right now", "its stop matters more than the business case"; labels "High Conviction", "Not Investable" | `service.py:497-513`; `quality.py:927-969`; `dossier.js:229-238` |
| R-ER-1 | P1 | a | AI brief shows "Leaning bullish/bearish" under "Take a clear stance", with no output validation | `earnings.js:124`; `ai.py:1696-1744,2067-2111` |
| R-OP-2 | P1 | a | "Pick a contract": ranked contracts with "Fit N of 100", default "Expect a rise" | `options-picker.js:16,28-65` |
| R-OP-3 | P1 | a | "Ideas": "Buy calls or puts" and "Strategies" with prices and budget | `options-panels.js:157-180` |
| R-IN-1 | P1 | a | DCF tiles "Model value", "Upside", "Margin of safety" before the caution at the foot | `dcf.js:181-241,701` |
| R-IN-2 | P1 | a | "Accumulation levels", "Levels to reassess at" | `investing.js:264-273`; `overview-research.js:363` |
| R-CH-1 | P1 | a | Stop check pre-filled from the entry plan; "Risk / reward", "Position size" tools | `chart-widgets.js:285`; `pricechart.js:647-652` |
| R-FR-6 | P1 | a | no per-area notice on Overview and Chart; Options and Earnings notices land at the foot | `core/legal.js:36`; `app.js:165-176` |
| R-OV-4, R-FR-1 | P1 | c | the advanced switch does not replace content; four names for one key; dead `levels` entry | section 1 |
| R-OP-5 | P1 | c | "50 is no edge either way" contradicts the Overview | `options-panels.js:229`; `overview-research.js:627` |
| R-IN-3 | P1 | c | one score coloured and named two ways; three "fair value" constructs | `investing.js:77`; `overview-research.js:499-500,546` |
| R-OV-6 | P1 | b, f | stale body: any-age cached payloads, no `onUpdate`, key figures from the snapshot | `api.js:93-100`; `overview-research.js:451` |
| R-SH-1 | P1 | b | a previous symbol's answer can fill the printable sheet | `sheet.js:128` |
| R-OP-6 | P1 | f | measured-looking statistics written into prose | `options-panels.js:393,411,417,426` |
| R-OV-10 | P1 | g | about 1,200 to 1,400 words and about twenty closed folds before any click | section 2, F-DOSSIER-01; BUG-004 |

## 5. Counts for this section

Written by the main session after this agent stopped at the usage limit (2026-10-29): 9 route entries (F-DOSSIER-01 to F-DOSSIER-09), about 104 control-table rows (counted by kind in the first column), 739 file:line citations, the pipeline map (3.1 to 3.11) and the risk index above.
<!-- END-PART-5 -->
