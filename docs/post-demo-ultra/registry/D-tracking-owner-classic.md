# Registry D: Tracking group, owner pages and the Classic route map

Evidence label: **Source** only. Everything below was read from code in `~/Optic/wt-ultra` (branch
`post-demo-ultra`; `app/`, `static/` and `tests/` are identical to origin/main `9fa0f36`, checked with
`git diff --stat 9fa0f36 HEAD -- app static tests`, which printed nothing). Nothing was rendered, no server was started, no
request was made, no file in the worktree was touched. A sentence about what a reader "sees" is an inference from the code.
Rows of `docs/post-demo-ultra/BUG_REGISTER.md` marked Rendered were not re-verified.

Citation form: `file:line`. Front-end files live in `static/v2/js/`; `pages/`, `core/` and `ui/` are folders of it and a bare name
is a file in `pages/` (`tracker.js`). Server files: `main.py` = `app/main.py`; the others carry their folder
(`brokerage/routes.py`, `account.py`). "Spend" means a call to the Anthropic API. Priorities follow directive 00 as quoted in
the bug register (P0 advice behaviour, broken core functions, incorrect financial data, security; P1 simplicity, Milo
reliability, usability, consistency, first use; P2 polish). Risk classes are the brief's: (a) wording or AI output that tells a
reader to buy, sell, rebalance, size or allocate; (b) one reader's portfolio or alerts reaching another reader, a log or Milo
unasked; (c) stale-response races; (d) dead controls; (e) missing loading, error or empty states; (f) figures without time or
source, unclear denominators, fallbacks of 0. IDs: `XX-nn` for controls and states of an entry, `R-XX-n` for its risks. Risks
already in the bug register keep their `BUG-nnn`.

## 0. Pieces every entry relies on

**0.1 Navigation and gating** (`nav.js`, `shell.js`, `app.js`)
- Rail groups for this section: Positions (`portfolio`: Optic Portfolio `#/portfolio`, Paper Desk `#/paper`, Retirement
  `#/retirement`, `nav.js:40-44`); Brokerage (`#/brokerage`, `feature: 'brokerage'`, `nav.js:45`); Watchlist (`follow`:
  Watchlist `#/watchlist`, Alerts `#/alerts`, `nav.js:46-49`); Reports (`owner: true`: Problem Reports `#/reports`, Claude
  usage `#/usage`, Accounts `#/accounts`, Metrics `#/metrics`, `nav.js:50-55`). The rail headings are "Tracking" for the first
  three and "Owner" for Reports (`nav.js:15`). Every page of these groups is `v2: true`; none opens in Classic.
- `visibleGroups` hides Reports unless `me.admin` and Brokerage unless the flag is set (`nav.js:88-90`). The flags are set in
  `app.js:108-114`: `admin` from `/api/auth/me` (payload field `admin`, `auth/routes.py:123`, true only for a verified address in
  `ADMIN_EMAILS`, `auth/admin.py:66-79`), `brokerage` only for a signed-in reader after `GET /api/brokerage/status` answers
  `available`. **Hiding is cosmetic**: `router.js:19-35` and the `PAGES` map (`app.js:63`) open every one of these routes for
  anyone who types the address; the server guard is the real gate (named per entry).
- Phone bar: Home, Markets, Watchlist, Dossier, More (`nav.js:63-69`); More lists every other visible group, so Positions,
  Brokerage (flag) and Reports (admin) live there (`shell.js:133-143`). The top-bar bell (`data-v2-bell`, link `#/alerts`) and the
  phone Watchlist badge show the signed-in reader's unread alert hits (`shell.js:39-54`), counted by
  `GET /api/watches/hits?limit=1` every 2 minutes in the trading day and 10 minutes outside it, only when signed in
  (`core/unread.js:11-19`).
- Page chrome: `sectionHead(group, view)` draws the h1 as the group label, a screen-reader-only ", <page>", the group tab strip
  and, under 640 px, a `<select data-v2-tabsel>` whose change navigates (`tabs.js:11-33`, `app.js:295-299`). Brokerage and the
  owner pages draw their own h1 (`brokerage.js:420`, `reports.js:145`).

**0.2 Folds, jump chips and Panels (`ui/sections.js`)**, used by Optic Portfolio only among these routes (`tracker.js:320`):
a fold button `button.sec-fold[data-sec-fold]` in every section heading, and the whole heading is a target unless it holds a
link or button (`sections.js:70, 163-165`); with six or more sections a "Jump to a section" strip of chips `[data-sec-jump]`
(`sections.js:99`; labels cut at 28 characters, `:90`); "Expand all" and "Collapse all" `[data-sec-bulk]`, each disabled when it
would change nothing (`:100, 117-120`); a "Panels" menu `details.menu.sec-panels` with one checkbox per section
`[data-sec-show]` and "Show every section" `[data-sec-showall]` (`:101-104`). Storage: `optic.panels.open` and
`optic.panels.hidden.v1` (`:19`); the knowledge level `optic.knowledge.v1` decides which unopened sections start folded
(`:17, 36, 53`).

**0.3 Ask Milo buttons and what leaves the page.** `button.btn-milo[data-v2-milo=<question>][data-v2-milo-ctx][data-v2-milo-sym]`
(`ui/milo.js:320-322`). A press only drafts: "Nothing is sent until the reader presses Send" (`milo.js:13`); `app.js:242-246`
passes the question, the label and the figures of the panel the button sits in (`panelFigures`, `milo.js:66-79`). On Send the
context is built from the page's `provideContext` provider, the route and the panel (`milo.js:106-128`); the reader can set the
scope to this page, market only, or none (`milo.js:52`) and take parts out. So each `provideContext` named below is **what leaves
the browser on Send in the default "This page" scope**, sent to `POST /api/chat` (`main.py:7848-7857`, `_spend_guard`: owner
unlimited; signed in, the plan allowance, Free 3 a day; guest, per configuration, `main.py:7468-7519`, `auth/store.py:661`).
Server-side Milo can add the linked brokerage portfolio on its own rules (entry `#/brokerage`, R-BK-1).

**0.4 Shared interaction parts.** Toast with optional Undo: 10 s with an action, 5 s without (`ui/toast.js:5-23`). Drawer: modal
dialog, Tab trapped, Escape or the close button shuts it, focus returns to the opener (`ui/drawer.js:76-122`). Typeahead on any
`[data-v2-ta]` input: `GET /api/search?q=&limit=10`, arrow keys, Enter, Escape; `data-v2-ta="submit"` also submits the form when
a suggestion is picked (`ui/typeahead.js:61-93`). API client: `X-Optic-CSRF` taken from cookie `optic_csrf` is sent on every call,
reads included (`core/api.js:44-47`); 20 s default timeout (`:39`); GET cache 60 s with stale-while-revalidate (`:89-107`);
statuses 401/403/404/409/422/429 become `auth/forbidden/notfound/bad/limit` and `explain()` words them (`:25-32, 126-141`).

**0.5 Browser storage and whose things these are** (`core/device.js`). Personal keys (`device.js:17-46`) include
`optic.paper.v1`, `optic.roth.inputs`, `optic.v2.replay.v1`, `optic.v2.paper.draft.v1`, `optic.brokerage.scope.v1`,
`optic.watchlists.v1`, `optic.chart.watch.v1`, `optic.watchlist.account.v1`, `optic.watches.v1`, `optic.signals.v1`. They are read
and written only while `holds(user)` is true (`device.js:192-197`); when a different person settles the page reloads and the
shelf swaps (`device.js:157-184`). Not personal (stay put): `optic.v2.watchlist.sort.v1`, `optic.brokerage.section.v1`,
`optic.panels.*`, `optic.knowledge.*`, `optic.timezone`, `optic.rail.tight.v2`.

**0.6 Legal notice per area** (`app.js:165-176`, `core/legal.js:21-41`): a "Hypothetical performance" notice follows the first
section of `#/portfolio` and `#/paper`, and a "Not retirement or tax advice" notice follows `#/retirement`. **No notice is mapped
for `#/brokerage`, `#/watchlist`, `#/alerts` or the owner pages** (`legal.js:36`); the global footer line and "Full disclaimer"
(`legal.js:34, 43-46`) are on every page.

---

## 1. Positions group

### Optic Portfolio — `#/portfolio`
- Files: `pages/tracker.js` (324 lines); shared `ui/scenarios.js`, `ui/sections.js`, `ui/bars.js`, `ui/chart.js`, `ui/states.js`,
  `pages/tabs.js`. Server: `main.py:3440-3584` (ledger, mark, scan), `main.py:4965-5067` (risk, scenarios), `app/paper.py` (the
  ledger), `app/analytics/portfolio_risk.py`, `app/analytics/scenarios.py`.
- Purpose: Optic's own simulated record: three rule-set books (conservative, balanced, aggressive, $100,000 each) running one scan,
  their open and closed trades, record, risk and hypothetical revaluation, the same for every reader (`tracker.js:1-6, 252`).
- Auth: guest, account and owner read the same page (`GET /api/tracker` has no guard, `main.py:3463-3473`). Signed in adds one
  sentence, "Accounts you link are under Brokerage, read only." (`tracker.js:253`). Pressing "Run a scan now" or "Refresh marks"
  is open to everyone but throttled for anyone who is not the owner: a scan only if 30 minutes have passed since the last scan of any
  kind, marks only every 2 minutes, both counted for the whole site, not per reader (`main.py:3482-3488, 3551-3565, 7238-7239`); the owner
  (admin session with CSRF, or the write token) never waits (`main.py:7209-7216, 7272-7327`).
- Sections in render order (`tracker.js:251-257`, `rest` `:218-240`):
  1. Header: h1 "Positions", tab strip (Optic Portfolio, Paper Desk, Retirement), a "whose" note: "This is Optic's demonstration
     portfolio, not yours. Three simulated accounts trade Optic's own signals with pretend money, the same for every reader. No money
     is real and no order reaches a broker." and a link to Paper Desk (`:251-253`).
  2. **Three simulated accounts** (`books`, `:84-100`; only when the API sends two or more books): one card per book (value, return,
     open, closed or "No trades yet", "Record from DATE", rules line, blurb), a note when records start on different days (`:98`).
     Data: `/api/tracker` `books[]`.
  3. **Optic Portfolio** (`ledger`, `:102-124`): pill with the book's name, fold "Run the shared scan or refresh prices", notices
     (cooldown, market closed, scan progress, feed throttled), four tiles (Account value, Realised P&L, Unrealised P&L, Total
     return), fold "How the book limits its risk" (five tiles). Data: `summary`, `config`, `capacity`, `progress`, `feed`.
  4. **Open positions** (`openPositions`, `:126-140`; only with open trades): lead line, a chart when two or more are scored, the
     table, stop/target explanation.
  5. **Month by month** (`months`, `:142-163`): month select, two tiles rows, closed-in-month table, opened-and-still-held table,
     and with more than one month a Consistency chart and table.
  6. **How the shortlist was chosen** (`funnel`, `:165-179`; only when a scan funnel exists).
  7. **No trades yet** (`:256`; only when the book has no open and no closed trade).
  8. **Track record** (`record`, `:181-188`; only with closed trades).
  9. **Book-level risk** (`risk`, `:190-216`; only with open trades). Data: `/api/portfolio-risk`.
  10. **What could happen to these positions** (`:257`, `scenariosSection`; only with open trades). Data:
      `/api/portfolio-scenarios`. Hypothetical, "never shown beside recorded performance" (`ui/scenarios.js:1-6`).
  11. **Closed trades**, **Earlier records**, **How these positions are taken** (sizing and entries/exits rules, the universe list,
      "What these numbers are not" caveats, the area disclaimer), **Scan history** (`:221-239`).
  Folds: open by default are "optic portfolio", "open positions", "three simulated accounts", "no trades yet"; every other section
  starts folded until the reader opens it (`:320`, rule at `ui/sections.js:36-39`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| TR-01 | button x3, toggle | Book card: label, a pill ("Smaller risk per trade", "Middle risk per trade", "Higher risk: bigger gains and bigger losses", `RISK_WORDS` `:83`), Value, Return, Open, Closed, rules line, blurb (`:92-97`) | `[data-v2-book]` click: sets `book`, clears `month`, `load()`, then focuses `#op-h` (`:314`) | `aria-pressed` follows the server's `d.book` (`:92`); pressing the current book does nothing (`:314`); module-level `book` defaults to `balanced` and survives leaving the page (`:20, 309`) |
| TR-02 | Milo button | "Ask Milo what differs" | drafts "Explain the three books..." (`:90`) | label `Optic Portfolio` |
| TR-03 | fold (details) | "Run the shared scan or refresh prices" | native toggle (`:110-113`) | not drawn while a scan runs (`:110`); explains the cooldown and the universe |
| TR-04 | button | "Run a scan now" | `[data-v2-tk=scan]` click, `action('scan')` (`:315, 296-306`): `POST /api/tracker/scan {}`, 20 s | sets `scanning`; page then polls `/api/tracker` every 4 s while `progress.running` (`:274-278`); a 429 or 409 shows the server's sentence in `.state[role=status]` (`:303, 114`) |
| TR-05 | button | "Refresh marks" | `action('mark')`: `POST /api/tracker/mark {}`, 60 s; toast "Marks refreshed." (`:299-300`) | same refusal handling; clears cached risk and scenarios and reloads (`:305`) |
| TR-06 | fold (details) | "How the book limits its risk" | native toggle; open when `advancedOn()` (`:120`) | knowledge level read from `optic.knowledge.v1` |
| TR-07 | select | "Month to show" (visually hidden label); options: every month newest first, last one marked "(current)" (`:148`) | `[data-v2-tk-month]` change: `month = value; load(true)` (`:317`) | drawn only when months exist |
| TR-08 | Milo button | "Ask Milo about gross exposure" | drafts "What is gross exposure..." (`:201`) | label `Optic Portfolio, book-level risk` |
| TR-09 | links | Ticker links `#/SYM` in the tables (`:57, 177, 208`); "Paper Desk" `#/paper` and "Brokerage" `#/brokerage` (`:253`) | hash navigation | Brokerage sentence shows for every signed-in reader (R-TR-3) |
| TR-10 | button (retry) | "Try again" in the three error cards (`:194, 254`; `ui/scenarios.js:66-67`) | `[data-v2-retry]` -> `app.js:280-283` -> `retry.load / risk / scenarios` (`:324`) | `risk` and `scenarios` clear their slot and reload |
| TR-11 | chrome | Section folds, jump chips, Expand all, Collapse all, Panels menu | see 0.2 | up to 12 sections, so the jump strip is drawn |
| TR-12 | chrome | Group tabs and phone `<select>` | see 0.1 | |

- Inputs and forms: the month select only. No typed input. Focus and scroll are kept when a background repaint (scan poll, risk
  arriving) redraws the page (`:244-259`).
- Charts and tables: charts `open` (unrealised P&L per open trade, `signedBars`, `:135, 263`), `months` (realised P&L per month,
  `:157, 264`); sector `hbars` (`:214`); a stop-to-target gauge per open row, `role=img`, `aria-label` = the sentence from
  `travelRead` (`:44-52, 76`); tooltips `title` on the entry tick ("opened with the stock at ...") and the "now" dot (`:76`).
  Tables and columns: Open positions: Position, Betting on, Size, Paid, Where it stands, Up or down, If stopped, Signal score, Held
  (`:136`). Closed in month: Position, Side, Entry, Exit, P&L, Why it closed, Closed (`:152`). Opened and still held: Position, Side,
  Size, Entry, Mark, P&L, Held (`:155`). Consistency: Month, Opened, Closed, Realised, Return, Win rate, Expectancy, Profit factor,
  Equity after (`:159`). Screen ranking: #, Symbol, Screen score, Price, $ volume/day, 1-month, Reached (`:176`). Risk: Name, Sector,
  Exposure, Risk (`:207`); Pair, N-day correlation (`:211`). Closed trades: Position, Side, Size, Entry, Exit, P&L, Why it closed,
  Held, Closed (`:223`). Earlier records: Book, Trades, Result (`:227`). Scan history: Ran, Trigger, Considered, Opened, Closed
  (`:237`). Scenarios: If, Change in value, Of today's value, Hardest hit, and with options Options alone, Delta alone says
  (`ui/scenarios.js:22`).
- AI-generated sections: none. "No model call anywhere on the page" (`:5-6`); the two Milo buttons spend only when the reader sends.
- Menus, drawers, modals: none besides the shared Panels menu.
- States:
  - Loading: `skeleton('rows', 6, "Loading Optic's own position ledger")` (`:254`); risk "Measuring how these positions move
    together, from three months of returns…" (`:193`); scenarios "Revaluing every position under each scenario…"
    (`ui/scenarios.js:65`).
  - Error: `failed("Optic's position ledger", D.err, {retry:'load'})` (`:254`); risk (`:194`); scenarios (`ui/scenarios.js:66-67`).
    A failed quiet reload (the 4 s poll, a month change) sets no error and keeps the old figures (`:275`).
  - Empty: section "No trades yet": "The ledger is empty. It only opens a position when a name's composite score clears N, and most
    scans find nothing. Open "Run the shared scan" above to run one, or wait for the scheduled one." (`:256`); month "No trades closed
    in {month}." (`:154`); risk "Unavailable." fallback (`:195`); scenarios `reason` (`ui/scenarios.js:68`).
  - Not signed in: the same page without the Brokerage sentence (`:253`). Not linked: not applicable.
  - Other notices: cooldown or scan refusal (`:114`), "The market is closed." (`:115`), scan progress with done/total (`:116`), "The
    price feed is rate-limiting right now." with seconds left (`:117`).
- API dependencies:
  - `GET /api/tracker?book=&month=`: ledger for one book (all three books' headline figures included); public (`main.py:3463-3473`);
    called `force`, 45 s timeout (`:272`).
  - `POST /api/tracker/scan`: starts a background scan, returns at once; public, 30 min cooldown, 409 while one runs, owner exempt;
    a visitor cannot choose tickers (`main.py:3538-3584`).
  - `POST /api/tracker/mark`: re-prices open positions; public, 2 min cooldown, owner exempt (`main.py:3476-3490`).
  - `GET /api/portfolio-risk?book=`: concentration and correlation of the open book; public; 120 s cache, 60 s timeout
    (`main.py:4965-4979`; `:283`).
  - `GET /api/portfolio-scenarios?book=`: revaluation; public; 120 s cache, 90 s timeout (`main.py:5046-5067`; `:291`).
- Preferences and storage: none of its own. Reads `optic.knowledge.v1` (`:120`) and `optic.timezone` (through `stamp`, `:238`);
  section folds in `optic.panels.open` and `optic.panels.hidden.v1` (0.2). Milo context on Send: `{view:'tracker', tracker:{book,
  summary, open (first 20: ticker, instrument, direction, pnl, stop, target), caveats}}` (`:311`): shared public data.
- Risks seen in code:
  - **R-TR-1 (c) P2** `tracker.js:268-281, 282-286, 314, 317`. `load()` never checks that `book` or `month` still match the request
    when it answers, and `loadRisk()` has no check at all (`loadScenarios` does, `:289-294`). Switching books or months quickly can
    put book A's ledger under book B's risk table, because risk is keyed to `book` at reply time.
  - **R-TR-2 (f) P2** `tracker.js:118-119, 137, 91, 230, 79`. No figure on the page carries a time: marks, P&L and account value have no
    "as of", although every position row has `marked_at` (`paper.py:673, 818, 926`) and the payload has scan times. `su.total_pnl || 0`
    turns a missing realised figure into "flat" (`:91`); `(bk.max_notional_pct || 0.25) * 100` prints "25% of equity" when the field is
    absent (`:230`); the percent under each P&L (`:79`) names no base.
  - **R-TR-3 (d) P2** `tracker.js:253`. Every signed-in reader is told "Accounts you link are under Brokerage" and given the link,
    although the Brokerage group is hidden unless the server says linking is open to them (`app.js:111-113`; owner-only mode,
    `brokerage/service.py:129-153`); Alerts gates its sentence on the flag (`alerts.js:270, 278`).
  - **R-TR-4 (f/abuse) P2** `main.py:3476-3490, 3538-3584, 7296-7300`. Any visitor can start the scan of about 3,000 names (global 30 min
    cooldown) and the re-mark (2 min). `_PUBLIC_LAST["mark"]` is set before the work runs (`:3488`), so a failed mark still starts the
    cooldown; a finished scan sends the owner an alert mail when mail is configured (`:3521`); the public branch has no CSRF check (only the
    operator branch calls `csrf_guard`, `:7296-7300`), so another site can fire either press from a reader's browser.
  - **R-TR-5 (e) P2** `tracker.js:275`. The 4 s progress poll swallows failures: a stalled poll leaves the progress bar frozen with
    no message.
  - Wording (a): no sentence tells a reader to trade; the rules and the "What these numbers are not" list describe the demonstration
    book (`:230-235`). The product-level question (a public model book of Optic's signals) is already BUG-026.

### Paper Desk — `#/paper`  (replay open: `#/paper?replay=<id>`)
- Files: `pages/paper.js` (400), `pages/paper-replay.js` (202), `core/journal.js`, `core/marketTime.js`, `ui/pricechart.js` (replay
  chart), `ui/bars.js`, `ui/chart.js`. Server: `main.py:2814-2834` (`/api/paper/mark`), `app/papertrade.py`, `main.py:1407` (chain),
  `:1086` (ticker read), `:5074-5090` (replays), `app/replays.py`.
- Purpose: the reader's own practice book, typed in by hand and priced by Optic, kept in this browser; a trade journal; and "Replay a
  past decision" (`paper.js:1-6`, `paper-replay.js:1-6`).
- Auth: no sign-in needed; no server account is involved at all. Guest and account run the same code; the book is read and saved
  only while `holds(user)` (`paper.js:78, 81`). Signed in adds "under your account, and hidden when you sign out" to the sub-line
  (`:273`); a sign-in or sign-out reloads the book and re-prices it (`:400`). The server routes it calls are all public and store
  nothing.
- Sections in render order (`paper.js:272-274`): header (h1 "Positions", tabs, sub-line "Practice trades you enter yourself, priced by
  Optic. They are saved in this browser only... Nothing reaches a broker or Optic Portfolio."); the replay section first when one is open;
  **Portfolio health** (`:93-113`, only with open trades); a "Filled from ..." note when a plan was handed over (`:274`); **Open a trade**
  (`:143-170`); **Open, N** (`:190-201`); **Record** with "With the terminal, and against it" and **Closed** (`:236-255`); **Journal
  review** (`:220-234`, only with closed trades); **Replay a past decision** at the foot when no replay is open (`:274`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| PD-01 | input text | "Symbol", placeholder NVDA, `maxlength 12`, id `pt-ticker` (`:152`) | `change`: upper-cases, clears expiry and strike, then (after focus lands) loads the option chain if instrument is Option, else repaints (`:365`) | no typeahead (`data-v2-ta` absent) |
| PD-02 | segmented buttons | "Direction": Long, Short (`:153`) | `[data-v2-pt-dir]` click: `ticket.direction`, repaint (`:371`) | `aria-pressed` |
| PD-03 | segmented buttons | "Instrument": Shares, Option (`:154`) | `[data-v2-pt-inst]` click; Option with a symbol loads the chain (`:372`) | |
| PD-04 | segmented buttons | "Call or put": Call, Put (`:155`) | `[data-v2-pt-ot]` click: clears strike (`:373`) | Option only |
| PD-05 | select | "Expiry": the chain's expiries; "Pick an expiry" or the loading text (`:156`) | `[data-v2-pt-expiry]` change: sets expiry, clears strike (`:366`) | disabled until a chain is read |
| PD-06 | select | "Strike": strikes of that expiry and side; "Pick a strike" (`:157`) | `[data-v2-pt-strike]` change (`:367`) | disabled until an expiry is chosen |
| PD-07 | button (text link) | "Try again" after "Could not read the options chain for X (reason)." (`:158`) | `[data-v2-pt-chain]`: reload chain (`:374`) | |
| PD-08 | input number | "Shares" or "Contracts", `min 0`, `step any`, placeholder 100 (`:160`) | `input` event writes `ticket.qty`, refreshes the preview (`:342-351`) | |
| PD-09 | input number | "Entry price" or "Entry premium", placeholder = chain mid or "Last price" (`:161`) | same | placeholder promises a last price the code does not have for shares (R-PD-4) |
| PD-10 | input number | "Stop" (`aria-required`) (`:162`) | same | required by `openTrade` (`:311`) |
| PD-11 | input number | "Target (optional)" (`:163`) | same | |
| PD-12 | input text | "Why, and what would prove you wrong", `maxlength 600` (`:164`) | same | |
| PD-13 | fold | "The plan" (`:116-133`): opens by itself when a draft, a trigger or a catalyst is set (`:118`) | native | kept open through repaints (`:271, 277`) |
| PD-14 | select | "Setup": Pullback in a trend, Breakout, Earnings reaction, Reversal, Range trade, Other (`core/journal.js:11-14`; `:119`) | `[data-v2-pt-plan]` change (`:361`) | |
| PD-15 | input number | "Planned hold, days", `min 1`, `step 1` (`:120`) | same | |
| PD-16 | select + input, repeated | "What supports it": kind select (Price trend, Momentum, Volume, Levels, Options positioning, Business and valuation, News or a scheduled event, The market; `journal.js:17-26`) and a text box, `maxlength 160` (`:122-123`) | `[data-v2-pt-ev-fam]` change (`:359`); `[data-v2-pt-ev-text]` input (`:343-344`) | starts with 2 rows; a count of independent kinds is shown (`:125, journal.js:63-75`) |
| PD-17 | button (text link) | "Add evidence" (up to 6 rows) (`:124`) | `[data-v2-pt-ev-add]` pushes a "volume" row (`:376`) | no control to remove a row |
| PD-18 | input text x5 | "What argues against it" (`maxlength 320`), "Catalyst" (120), "Entry trigger, if it is conditional" (200), "What would make it wrong" (200), "What you saw when you entered" (200) (`:126-132`) | `input` / `change` write `ticket[name]` (`:347-348, 361`) | |
| PD-19 | input date | "Its date" (catalyst date) (`:128`) | same | |
| PD-20 | checkbox | "I mean to hold through it" (`:129`) | `change` (`:361`) | |
| PD-21 | button (text link) | "Load it" in "Optic has no read on X loaded." (`:167`) | `[data-v2-pt-read]`: `GET /api/ticker/SYM...`, stores stance, conviction, score, summary (`:297-302, 375`) | else the line "Optic reads X as bullish, N conviction. That agrees with this trade." appears (`:166`) |
| PD-22 | submit | "Open the trade" (`:169`) | form `submit`: reads fields, `openTrade()`, repaint, then `mark()` (`:387-395`) | Enter in any field submits; `novalidate` (`:151`) |
| PD-23 | button | "Clear" (`:169`) | keeps ticker, instrument and direction, blanks the rest (`:377`) | |
| PD-24 | button (text link) | "Price it again" after a failed mark (`:170`) | `[data-v2-pt-remark]`: `mark()` (`:378`) | only after a failure |
| PD-25 | buttons per open row | "Close" (title "Close at the current mark") (`:198`) | `[data-v2-pt-close]` -> `close(id)`: moves the trade to Closed at the mark, stores P&L and R, focuses `#po-h` (`:379, 322-330`) | disabled without a mark price |
| PD-26 | folds per open row | "Plan for POSITION, as opened / changed N times" with Target (number), Planned hold, days (number), "What would make it wrong" (text) (`:181-188`) | `[data-v2-pt-rev]` change: `J.revise` appends a dated revision, saves, repaints (`:354-358`) | original plan is never overwritten (`journal.js:46-54`) |
| PD-27 | button + confirm | "Clear the book" -> "Delete N open and M closed" (danger) and "Keep them" (`:253-254`) | `[data-v2-pt-reset]` arm / keep / do (`:380-385`) | arming moves focus to "Keep them"; "Optic Portfolio is not touched." |
| PD-28 | Milo button | "Ask Milo to review my process" (`:227`) | drafts a review request (the text says "Use only what is recorded.") | label `Paper Desk, journal review` |
| PD-29 | folds + selects + input per closed trade (newest 30) | "Entered as planned?", "Exited as planned?", "Sized to the planned risk?" (options Not recorded, Yes, No), "Reflection" (`maxlength 400`) (`:204-217`) | `[data-v2-pt-adh]` change (`:360`); `[data-v2-pt-refl]` input saves at once (`:345-346`) | |
| PD-30 | links | symbols and "Optic Portfolio"/tabs | `sectionHead('portfolio','paper')` (`:272`) | |

- Inputs and forms: the ticket is one `<form data-v2-pt-form novalidate>`. Rules in `openTrade` (`:303-321`): a symbol; fewer than
  50 open positions (`MAX`, `:24`); for an option a picked expiry and strike; quantity above 0; an entry price above 0 (typed, or the
  picked contract's mid, or the chain's spot only when a chain for that ticker is loaded, `:305`); a stop above 0 ("A stop is required.
  Everything here is reported in multiples of what a trade risked, and a trade with no stop has no denominator."); the stop on the
  correct side of entry. The preview (`:172-178`) shows cost, risk, reward:risk and a wrong-side warning, live. Keyboard: Enter submits;
  the Delete-all confirm is a two-button group with focus on "Keep them".
- Charts, tables, menus: Exposure bar `role=img` with a legend (`:109-110`); chart `r` (R multiple of each closed trade, last 30,
  `signedBars`, `:245, 280`). Open table: Position, Entry, Mark, Marked from, P&L, R, Optic then, (Close) (`:193`). Closed table:
  Position, Entry, Exit, P&L, R, Optic then, Closed (`:249`), newest 50. Journal tables: Group, Trades, Won, Average result, Average R
  for By setup, By time held, Catalysts, Following the plan (`:224, 231`). Tooltip: `title` = Optic's summary on "Optic then" (`:197`).
- AI-generated sections: none. The page says its marks and reads are Optic's calculations; Milo is reached only through PD-28 and the
  top-bar button. Milo context on Send: `reader_holdings` (first 30 open positions: ticker, instrument, direction, qty, entry price,
  stop, P&L) and `journal` (the last 20 closed trades with plan, revisions, exit note, adherence and the reader's own reflection text)
  (`:339`, `core/journal.js:129-137`); the server then adds a sector summary of the book if the question matches `_PORTFOLIO_WORDS`
  (`main.py:6849-6851, 7048-7052`).
- States: loading chain "Reading X's chain…" (`:149`); marking "pricing…" in the mark column and the pill "N of M not marked" (`:196, 104`);
  chain failure (`:158`); price failure "Could not price the book just now (...)" plus PD-24 (`:287, 170`); empty book "No open
  positions. The ticket above opens one." (`:199-200`); no closed trades "Nothing closed yet. Every number here is realised: an open
  position's profit is a quote, not a result." (`:238`); form errors are the strings of `openTrade` shown in `.pt-note[role=status]`
  (`:392-393, 170`). Not signed in: the sub-line omits "under your account" (`:273`). Not linked: not applicable.
- API dependencies: `POST /api/paper/mark` (public, stateless, up to 50 positions, returns marks, `marked_at`, `dropped`, `capped`;
  `main.py:2814-2834`, `papertrade.py:132-190`; 60 s timeout, `:286`); `GET /api/chain/{SYM}?max_expiries=6` (public; cache 120 s,
  45 s, `:293`); `GET /api/ticker/{SYM}?max_expiries=4&macro=true` (public; 60 s, `:299`); `GET /api/health` (`realtime_chain` flag,
  `:341`); `GET /api/replays`; `GET /api/replays/{id}?at=N`.
- Preferences and storage: `optic.paper.v1` read and written (`:24, 76-81`), `optic.v2.paper.draft.v1` read once and removed on render
  (`:23, 338`; written by the contract picker), `optic.v2.replay.v1` (replay attempts), all personal keys. The sub-line says the book
  exists only in this browser; there is no export.
- Risks seen in code:
  - **R-PD-1 (b) P2** `paper.js:339`, `core/journal.js:129-137`. Every Milo question sent from this page in the default scope carries the
    reader's open positions and up to 20 closed trades including free-text reflections, whatever the question; the reader can detach
    parts in the panel (`ui/milo.js:115, 127`) but nothing says so on the page.
  - **R-PD-2 (c/d) P2** `paper.js:283-289, 387-395, 198, 170`. `mark()` returns at once while another mark is in flight, so a trade
    opened in that moment is never priced: its Close button stays disabled and "Price it again" appears only after a failure.
  - **R-PD-3 (d) P2** `paper.js:198, 323-324, 253-254`. A position whose mark cannot be fetched (no quote, an option chain that cannot
    be read) cannot be closed and has no manual exit price; the only way to remove it is "Clear the book", which deletes everything.
  - **R-PD-4 (d/e) P2** `paper.js:161, 305, 310, 365, 372`. The Entry box reads "Last price" for shares, but no spot is loaded unless an
    option chain for that ticker was read earlier (`loadChain` runs only for options), so a blank entry stops with "What price did you get
    in at?".
  - **R-PD-5 (e) P2** `paper.js:78, 81, 318`; `core/device.js:192-197`; `app.js:95-104`. While the browser holds someone else's things (a
    guest's papers awaiting the "Keep what you made on this browser?" answer) `holds()` is false: the book reads empty and a trade opened
    is kept in memory only, with no message.
  - **R-PD-6 (f) P2** `paper.js:322-329, 396, 199`. Marks are taken at page load and after each trade, never on a timer, yet Close
    books the exit at whatever mark is held; the footnote gives the time (`:199`) but the Close button and the Closed table do not.
  - **R-PD-7 (a) P2** `paper.js:166, 195-197, 246-247`. "Optic reads NVDA as bullish ... That agrees with this trade." and "Traded with
    Optic's read / against it" give a stance on the reader's own entry; it is stated as a record ("Recorded on the trade, and scored
    separately below") but reads as an endorsement. Related to BUG-025/BUG-027.
  - **R-PD-8 (e) P2** `paper.js:286`; `papertrade.py:178-189`. The server's `dropped` and `capped` are ignored, so a position it
    refused shows only "not marked".
  - Replay: no risk found; the server sends only bars up to the session shown (`paper-replay.js:1-6`).

#### Replay a past decision — section of `#/paper`, deep link `#/paper?replay=<id>`
- Files: `pages/paper-replay.js`; `app/replays.py`. Six replays: NVDA January 2024, SPY March 2024, META January 2022, AAPL February
  2025, JPM March 2024, XOM March 2023 (`replays.py:49-59`), 20 sessions before and 20 after the decision (`:38-39`).
- Purpose: show a real past chart one completed session at a time, stop where Optic's setup rule flagged something, take the
  reader's decision before the next session, then set it beside the rule's own outcome (`paper-replay.js:1-6`).
- Auth: all readers; decisions kept in the browser only (`:20-24`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| RP-01 | button per replay | "Start" or "Replay again" (`:53`) | `[data-v2-rp-open]`: `open(id)`, address becomes `#/paper?replay=ID` (`:178, 163`; `paper.js:261-266`) | shows "Replayed once; your reasoning is kept." |
| RP-02 | button | "Back to the replays" (twice) (`:107, 87`) | `[data-v2-rp-close]` (`:179`) | |
| RP-03 | button | "Play" / "Pause" (`aria-pressed`) (`:97`) | `[data-v2-rp-play]`: steps one session every 900 ms (`:182, 156, 16`) | disabled at the decision session, at the end, or loading |
| RP-04 | buttons | "Next session", "Next 5" (`:98-99`) | `[data-v2-rp-step]` (`:181`); the decision is never skipped (`:149`) | |
| RP-05 | button | "Go to the review" (`:100`) | `[data-v2-rp-review]` (`:183`) | after a decision |
| RP-06 | segmented | "Take it", "Pass" (`:68`) | `[data-v2-rp-choice]` (`:180`) | |
| RP-07 | select + 3 numbers | "Side" (Long, Short), "Entry" (defaults to the last close), "Stop" (defaults to the rule's invalidation), "Target (optional)" (`:69-72`) | `input` keeps them in `R.form` (`:186`) | only when "Take it" |
| RP-08 | textarea | "Why, in a sentence or two", `maxlength 600` (`:73`) | same | |
| RP-09 | submit | "Keep my decision" (disabled until a choice) (`:74`) | `submit`: needs entry and stop for "Take it"; stores the attempt (last 10 per replay) (`:187-195, 24`) | focus moves to "Next session" |
| RP-10 | button | "Replay it again" (`:87`) | `[data-v2-rp-again]` marks the attempt reviewed, reloads from 20 sessions before (`:184`) | |
| RP-11 | link | "SYM on the chart today" `#/SYM/chart` (`:87`) | navigation | |
| RP-12 | keys | ArrowRight steps one session (not inside the chart); Space toggles play unless a button has focus (`:196-200`) | | |

- Chart: `createPriceChart` candles with moving averages and volume, lines for trigger, invalidation and the reader's stop and target,
  an event marker at the decision (`:117-130`). Review shows "Over the next N sessions it ...: R multiple" computed by `planResult`
  from the daily bars, assuming the stop when one bar touches both stop and target (`:28-46, 84`).
- States: library loading skeleton "Loading the replays" and failure card with retry (`:49-50, 165`); replay loading "Loading the replay"
  (`:109`), failure card (`:108`).
- API: `GET /api/replays` (public, cached 10 min, `:160`), `GET /api/replays/{id}?at=N` (public, cached 1 h, 60 s, `:139`;
  `main.py:5074-5090`). Storage `optic.v2.replay.v1` (personal).

### Retirement — `#/retirement`
- Files: `pages/retirement.js` (168), `ui/xychart.js`, `ui/chart.js`, `pages/tabs.js`. Server: `main.py:1772-1798`,
  `app/analytics/retirement.py`.
- Purpose: "A rules-based model allocation to compare your own against. Not retirement or tax advice." (`retirement.js:123`): a Roth IRA
  model from the reader's horizon, risk, contribution, stock candidates and current holdings, with drift, a rebalancing plan and a
  projection (`:1-5`).
- Auth: none needed; guest, account and owner identical. Inputs are kept in this browser under a personal key and sent to the server
  to be computed, "which computes the plan and keeps no copy" (`:44`; `main.py:1773-1780`: "Nothing here is persisted"). A sign-in or
  sign-out re-reads the inputs and recomputes (`:168`).
- Sections in render order (`:119-130`, `sections` `:86-117`): header with the sub-line; **Roth IRA model allocation** (form, the
  server's `limit_note`, then the model: equity/bond/gold tiles, expense ratio, yield, blended history, "Target weights" table,
  caveat, server disclaimer); **Contribution projection**; **Drift from target** (only when holdings were given); **Where to put this
  year's contribution**; **Overlap in your holdings** (only when the server returns overlap data, which needs two or more holdings with history); **Individual stock sleeve**;
  **What the Roth wrapper changes**; **Fund universe**; **Correlation** (only when a matrix exists). The area notice "Not retirement or
  tax advice" follows the first section (`legal.js:25`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| RT-01 | input number | "Years until you'd draw on it", `min 1 max 45` (`:38`) | read on submit, clamped to 1-45 (`:24-32, 160`) | clamp is silent |
| RT-02 | select | "Risk tolerance": Conservative, Balanced, Growth (`:39`) | same | any other value becomes balanced (`:28`) |
| RT-03 | input number | "Annual contribution ($)", `min 0 max 100000 step 500` (`:40`) | clamped to 0-100,000 (`:29`) | |
| RT-04 | input text | "Individual stock candidates (optional)", placeholder "e.g. AAPL, KO, MSFT" (`:41`) | sent as typed | no format check |
| RT-05 | textarea | "Your current holdings. One per line, symbol then dollar value", 4 rows, placeholder "VTI 12000 / VXUS 4000 / BND 1500" (`:42`) | sent as typed | the server's parse is echoed back into the box (`:140-142`) |
| RT-06 | submit | "Recalculate" / "Calculating…" (disabled while loading) (`:43`) | `submit` on `[data-v2-roth]`: clamps, saves inputs to `optic.roth.inputs` (if `holds`), `load()` (`:157-163`) | Enter submits |
| RT-07 | links | fund symbols `#/SYM` in Target weights, Buy table, Stock sleeve, Fund universe (`:61, 97, 105, 113`) | navigation | |
| RT-08 | button (retry) | "Try again" in the error card (`:126`) | `retry.load` (`:167`) | |
| RT-09 | chrome | tabs and phone select | `sectionHead('portfolio','roth')` (`:122`) | |

- Inputs and forms: validation is the silent clamp above; no inline messages, `novalidate` (`:37`). The first load runs at render with
  the saved or default inputs (30 years, balanced, $7,000, no holdings), before the reader does anything (`:152-165`).
- Charts and tables: chart `proj` (`xyChart`: At the historical rate, Lower scenario, Upper scenario, Contributions only, with a
  legend and a summary sentence, `:65-84`). Tables: Target weights: Fund, Weight, Per year, Expense, Yield, 10y return a year,
  Volatility, Worst drawdown (`:60`); Drift: Exposure, You hold, Current, Target, Drift, (bar) (`:91`); Buy: Buy, Exposure, Amount,
  Share of contribution, (bar) (`:96`); Stock sleeve: Stock, Conviction, Score, 10y price return a year, Worst drawdown, History,
  Suggested (`:104`); Fund universe: Fund, In model, Expense, Return a year full history, 5y CAGR, Volatility, Return / vol, Worst
  drawdown, History (`:112`); Correlation matrix, cells at 0.85 or more marked hot, 0.35 or less cool (`:114-116`).
- AI-generated sections: none ("No model call", `:5`). Milo context on Send: `{view:'roth', roth:{inputs, allocation, blended,
  projection:{years, balance_base}}}` (`:156`); `inputs` is the server's echo and includes the typed holdings with dollar values.
- States: loading `skeleton('rows', 5, 'Loading ten years of history for the fund universe')` (`:126`) with the sections below absent;
  error `failed('The model', D.err, {retry:'load'})` (`:126`); empty rebalance "Enter your current holdings to get a rebalancing plan."
  (`:100`); projection unavailable `pr.note || 'Projection unavailable.'` (`:66`); drift and overlap sections are simply omitted when
  there is nothing to show (`:89, 101`). Not signed in: same.
- API dependencies: `POST /api/retirement` with `{years, risk, annual, holdings, stock_candidates}`; public; stateless; 90 s timeout
  (`:135`; `main.py:1772-1798`).
- Preferences and storage: `optic.roth.inputs` read (`:149`) and written on submit (`:161`), personal key; nothing else.
- Risks seen in code:
  - **R-RT-1 (a) P1** `retirement.js:94-99, 104-105, 89-93`; `retirement.py:575-577, 629-630, 666-677, 722`. The page turns the reader's
    holdings and contribution into dollar instructions: a table whose first column is headed "Buy" with an amount and a share of the
    contribution per fund, a section "Where to put this year's contribution", a "Suggested" weight per stock, a drift summary "Worth
    correcting with this year's contribution.", "Contribute at target weights, or rebalance by selling if the overweights bother you.",
    "Selling inside a Roth triggers no tax, so the only cost is the spread." and "Holding both is close to holding one at double the
    weight." Mitigations present: "Not retirement or tax advice." (`:123`), the area notice (`legal.js:25`), the server's disclaimer
    (`:62`; `retirement.py:3-8, 1000`). Same finding as BUG-025, with these strings.
  - **R-RT-2 (c/e) P2** `retirement.js:126-127`. When a recalculation fails, `D.d` keeps the last good result: the error card replaces
    the model block but "Contribution projection", "Drift", the Buy table and the rest stay on screen, computed for the previous
    inputs while the form shows the new ones.
  - **R-RT-3 (e/f) P2** `retirement.js:24-32, 125`; `main.py:1795`. Out-of-range inputs are clamped without a word (the server's
    `limit_note` is the only explanation, `:125`); no result carries an "as of" although the payload has `generated_at`; the blended
    history window shows only years (`:57`).
  - **R-RT-4 (b) P2** `retirement.js:156`. Milo's page context contains the typed holdings and amounts on every question asked from
    this page.
  - **R-RT-5 (resource) P2** `retirement.js:164`; `main.py:1772-1798`. Every visit posts a computation over ten years of history for the
    fund universe before any action, and the route has no per-caller limit.

---

## 2. Brokerage

One page module, five section routes (`router.js:19, 33`: `#/brokerage` plus `/overview`, `/holdings`, `/performance`, `/events`,
`/connections`; any other second segment, or a capital letter, gives `section: null`, so the reader's last section opens; Classic
lowercases and rejects unknown ones, `app.js:47535-47541`). The first entry covers the gate before a link, the link flow, the frame
and the server; the five that follow cover what each section draws.

### Brokerage, gate and frame — `#/brokerage`
- Files: `pages/brokerage.js` (629); `ui/scenarios.js`, `ui/chart.js`, `ui/milo.js`, `core/format.js` (`billingOff`). Server:
  `app/brokerage/routes.py` (377), `workspace_routes.py` (175), `service.py`, `workspace.py`, `alerts.py`, `briefing.py`, `store.py`,
  `app/billing.py`, `main.py:7701-7845` and `8103-8109`, `ai.py:1891-1947`. Classic's `static/brokerage.js` calls the same routes.
- Purpose: the reader's own linked brokerage accounts, read-only: "Optic cannot place, cancel or move anything" (`brokerage.js:420`;
  no order route exists, `:8-11`). Before a link it is sign-in, plan and consent; after, five sections (`:1-4`).
- Auth, what each reader gets (page: `brokerage.js:401-411`, server: `routes.py:90-115`):

| Reader | Server answer | What the page draws |
|---|---|---|
| Guest, linking switched off or owner-only deployment | `{available:false, reason:"Brokerage linking is not switched on for this deployment.", permissions}` (`routes.py:94-97`; `service.py:126, 146-153`: in owner-only mode everyone but the owner gets this sentence word for word) | one paragraph, the reason (`:405`); the rail item is hidden (`app.js:111-113`) |
| Guest, linking on | `{available:true, signed_in:false, provider, mode, permissions}` (`routes.py:98-100`) | "Link your brokerage": "See your real holdings in Optic and ask Milo about them. Read-only: Optic cannot trade or move money. Sign in first; linking is part of the paid plan." and a "Sign in" button to `#/signin`, then the permissions fold open (`:406, 85-89`). The workspace routes answer a guest 401, and the page never calls them |
| Signed in, Free plan | `entitlement.can_link=false`, `paid_limits`, `consent`, `connections:[]` (`routes.py:101-114`; Free links nothing, `auth/store.py:661-663`) | if `GET /api/billing/status` says billing is unavailable: "Link your brokerage. Linking is part of the paid plan." plus the billing sentence (`:92`; `format.js:146-149`: "Plans are not on sale yet. Every account is on Free." for a reader, setup detail for the owner); otherwise "Link your brokerage with Pro", the plan's connections, daily and manual syncs, Milo allowance, the Upgrade button and "You are on Free. Cancel any time from Settings." (`:94-98`), then the permissions fold open (`:408`) |
| Signed in, may link (Pro, or the owner), nothing linked | adds `consent` (accepted, version, document URLs) | the Connections section: "Connect a brokerage" (disabled until the consent box is ticked), "Nothing linked yet. Connect a brokerage to see your holdings here.", "After you finish at the provider, it brings you back to this page.", permissions fold open (`:409, 133-142`) |
| Signed in, linked | `connections[]` with accounts | the frame: header, scope select, freshness pills, Ask Milo, five tabs, panel (`:410-411, 158-164`) |
| Signed in, linked, plan lapsed | `paused_at`, `provider_closed_at` | a "Syncing is paused" section above Connections with "Resume with Pro" (`:136`) |
| Owner (verified admin) | limits raised to at least 3 connections, 10 accounts, 5 manual syncs a day (`service.py:238-241`) | owner-only suffixes on the consent line and on provider failures (`:105`; `routes.py:73-87`) |

- **The link flow, step by step.**
  1. Consent: an unticked box "I agree to Optic's Terms and Privacy Policy and to SnapTrade's End User Terms. I understand Optic gets
     read-only access and that holdings I ask Milo about are sent to Anthropic to answer." (`brokerage.js:99-107`); a document appears
     only if its URL is configured, and sandbox or owner-only builds say so in brackets (`:104-105`; `service.py:91-110`). A reader who
     has agreed to the current version sees "You agreed to the linking terms on DATE." (`:100`).
  2. "Connect a brokerage" posts `POST /api/brokerage/connect` with `consent_version` when the box was ticked (`:541-546`). Server:
     session and CSRF, 10 attempts an hour per reader, then `service.start_link`: linking enabled for this reader, plan allows it,
     consent recorded for this version with a hashed address, connection cap, a provider user registered and a single-use state token
     stored, then the provider's portal URL returned (`routes.py:118-131`; `service.py:280-306`). Refusals: 503 not switched on, 402 not
     entitled, 428 "Agree to the terms first. Tick the box above Connect.", 424 provider failure (`routes.py:62-87`).
  3. The page follows the URL only if it starts with `/api/brokerage/sandbox/` or is https on `snaptrade.com` or `stripe.com`
     (`SAFE`, `:47, 548`); otherwise the toast "The connection link did not point at the provider, so Optic did not follow it."
     (`:549`). The provider's link expires in five minutes, so it is fetched at the click (`:545`).
  4. Provider portal. Real: SnapTrade's hosted page; the reader signs in at the broker there and "Optic never sees or stores your
     brokerage password" (`routes.py:41-45`). Sandbox (`BROKERAGE_PROVIDER=sandbox`, refused on a hosted deployment unless
     `BROKERAGE_SANDBOX_ON_HOST`, `service.py:166-167`): Optic's own page `GET /api/brokerage/sandbox/portal?session=` with a radio
     list of scenarios and two forms, "Allow read-only access" and "Cancel", posting to `/api/brokerage/sandbox/authorize` and
     `/abandon`; these three routes need no sign-in and no CSRF, are keyed by the one-time session id, and answer 404 unless the
     sandbox provider is configured (`routes.py:277-352`).
  5. Return: `GET /api/brokerage/callback?state=` needs the session cookie and a state token that this same reader started; it imports
     the one new connection, removes any other connection the provider holds for the reader, refuses (and removes) a connection that
     allows trading, enforces the cap, then answers 303 to `/?brokerage=<code>#/brokerage` with code linked, abandoned, expired,
     unsupported, error, limit, notreadonly or nothing (`routes.py:134-156`; `service.py:309-318`). The page reads the code, removes it
     from the address, shows one status line from `FLASH` ("Connected. Your accounts are synced below.", "Connection cancelled.
     Nothing was linked.", and so on) and opens Connections (`brokerage.js:36-44, 510-512`); the line stays until the reader moves to
     another section (`:416`).
  6. After linking, a sandbox build says on every section: "Sandbox: test data only. These accounts, holdings and values are made up
     for demonstration and belong to no one." (`:417-421`).
  7. A broken connection offers "Reconnect", which repeats steps 2 to 5 with `{reconnect: id}` (`:541-546`).
- **Disconnect and delete.** Per connection: "Disconnect" arms the row, which then shows "Disconnect and delete" and "Keep" and the
  line "Disconnecting removes it at the provider and deletes Optic's copy of its data now." (`:125-126`); confirming posts
  `POST /api/brokerage/connections/{id}/disconnect`: remove at the provider, delete the connection, its accounts, holdings,
  transactions and its part of every stored snapshot; if the provider does not answer the removal is queued and retried and the
  toast says so; the last connection removed triggers the full delete (`:558-562`; `service.py:671-702`). "Delete all brokerage data"
  arms the same way ("Yes, delete all brokerage data" / "Keep it") and posts `POST /api/brokerage/delete-data`: every connection,
  holding, snapshot, alert, written briefing and link state, and the encryption key, so backups cannot be read (`:143-144, 563-567`;
  `service.py:705-720`; `store.py:451-466`). Leaving never asks `open_to`, so it works in owner-only mode and on any plan (`routes.py:187-194`).
  Not removed: the reader's written theses and their alert settings (`store.py:458-465`; R-BK-8).

**Server routes the page uses** (`routes.py`, `workspace_routes.py`)

| Method and path | Guard | Notes |
|---|---|---|
| `GET /api/brokerage/status` | session optional (`current_user`) | guest gets the reduced answer above; calls `connections_payload` for a signed-in reader (`routes.py:90-115`); also called by `app.js:111` after every sign-in to decide whether the rail shows Brokerage |
| `POST /api/brokerage/connect` | `require_user`, CSRF, 10 per hour per reader | `routes.py:118-131` |
| `GET /api/brokerage/callback` | session + single-use state token bound to the reader | redirects only; `routes.py:134-156` |
| `POST /api/brokerage/connections/{id}/sync` | `require_user`, CSRF, plan entitlement, per-plan daily cap | 402 not paid, 409 needs reconnect, 429 "Your plan includes N manual sync(es) a day..."; the cap is spent only when the provider accepted (`routes.py:159-184`) |
| `POST /api/brokerage/connections/{id}/disconnect` | `require_user`, CSRF | ids are looked up with the reader's id, so another reader's answers 404 (`routes.py:187-194`, docstring `:1-12`) |
| `PATCH /api/brokerage/accounts/{id}` | `require_user`, CSRF | `selected` (counted) or `nickname` (`routes.py:197-213`) |
| `POST /api/brokerage/delete-data` | `require_user`, CSRF | `routes.py:216-220` |
| `GET /api/brokerage/workspace/{overview, holdings, scorecard, options, scenarios, performance, events, briefing, alerts}` | `_reader`: session, `open_to`, a link with at least one account (else 409 "No brokerage is linked yet. Connect one in Connections.") (`workspace_routes.py:39-45`) | reads only; `accounts=` ids are filtered to the reader's own by `service.scoped`; `performance` validates `period` (1m, 3m, ytd, 1y, all) and `benchmark` (SPY, VTI, QQQ, ACWI, AGG) with 400 (`:90-97`) |
| `POST /api/brokerage/workspace/briefing/written` | `_reader` + CSRF + the Milo spend guard | **the only AI writer reachable from these routes** (below) |
| `POST /api/brokerage/workspace/alerts/refresh`, `.../alerts/seen`, `PUT .../alerts/settings` | `_reader` + CSRF | `workspace_routes.py:148-175` |
| `GET /api/billing/status`; `POST /api/billing/checkout`, `/portal` | `current_user`; `require_user` + CSRF | upgrade and manage-plan buttons (`billing.py:110-175`) |
| `PUT /api/theses/{SYM}`, `DELETE /api/theses/{SYM}` | `require_user` + CSRF | the thesis form (`account.py:582-654`) |
| `POST /api/chat` | `_spend_guard` | when the reader sends any Ask Milo draft; may attach the linked portfolio (R-BK-1) |

- **Where an AI can be reached.** (1) `POST /api/brokerage/workspace/briefing/written` calls `HOOKS['write_brief']` =
  `ai.write_portfolio_brief` after `HOOKS['spend_guard']` = `_portfolio_spend_guard`, which runs the Milo allowance check and counts a
  "portfolio" question (`workspace_routes.py:116-136`; `main.py:8103-8109, 7457-7519`; `ai.py:1916-1947`). It sends the slim facts
  (`today`, `since_sync`, `drivers`, `upcoming`, `observations`, `limitations`: holding-level moves, headlines, event dates, the
  reader's weights) to the Anthropic API on `PULSE_MODEL`, capped at 40,000 characters (`ai.py:1931-1933`; `workspace_routes.py:131`); the
  reader's text is kept sealed per reader and reused for the same facts (`store.save_briefing`, `workspace_routes.py:135`). A cache
  hit returns before the guard, so repeating the same facts is free (`:123-125`). The owner is exempt from the allowance (`main.py:7471-7487`).
  (2) Milo itself (`POST /api/chat`) can receive the linked portfolio block and the `get_my_portfolio` tool (`main.py:7701-7845`).
  No other brokerage route imports or calls a model (grep of `app/brokerage/` for `anthropic` and `ai.` finds only the hook names).

**Controls (gate and frame)**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| BK-01 | button-link | "Sign in" (guest) (`:406`) | `#/signin` | |
| BK-02 | fold | "What Optic can and cannot see": the server's six permission sentences, then "Provider: X" and, in sandbox, "(sandbox: test data only)" (`:85-89`) | native; open when nothing is linked (`:142, 406, 408`) | the sentences are `routes.py:41-55` |
| BK-03 | button | "Upgrade" or "Upgrade for PRICE" (`:97`) | `[data-v2-bill=checkout]`: `POST /api/billing/checkout`, follow the URL only if `SAFE` (`:535-539`) | disabled while the request runs |
| BK-04 | button | "Resume with Pro" (`:136`) | same | |
| BK-05 | button | "Try again" under "Brokerage did not load" (`:403`) | `[data-v2-bk-reload]` reloads status and section (`:526`) | |
| BK-06 | select | "Accounts": "All counted accounts (N)" and one entry per account "NAME MASK", suffixed " (not counted)" (`:160`) | `[data-v2-bk-scope]` change: stores the id in `optic.brokerage.scope.v1`, drops cached data, reloads (`:607`) | one account or all; ids not owned are ignored (`:79`) |
| BK-07 | Milo button | "Ask Milo" with the section's question (`SECTIONS`, `:24-30`; `:161`) | drafts; label `Brokerage: <Section>` | Overview "What deserves my attention in my linked portfolio this week?"; Holdings "Where am I concentrated, counting what my ETFs hold?"; Performance "How has my portfolio done against the S&P 500, and how much of the change was my own deposits and withdrawals?"; Events "Which earnings and events affect me in the next two weeks?"; Connections "What can Optic see in my linked accounts, and what can it not?" |
| BK-08 | tabs x5 | Overview, Holdings & Exposure, Performance, Events & Research, Connections (`role=tab`, one tab stop) (`:162`) | `[data-v2-bk-tab]` click: `setSection` pushes `#/brokerage/<id>` and stores `optic.brokerage.section.v1`, repaints, loads (`:525, 491-498`); ArrowLeft, ArrowRight, Home, End move between tabs (`:587-593`) | the panel is `role=tabpanel` with the tab as its label (`:163`) |
| BK-09 | button | "Try again" under "<Section> did not load" (`:170`) | `[data-v2-bk-retry]` forces a reload of the section (`:527`) | |
| BK-10 | status pills | "Broker data as of ...", "Synced N ago", "Pre-market quotes / After-hours quotes / Quotes N ago (delayed N min)" (`:150-157`) | none | from the overview or holdings payload |

- Inputs and forms: the scope select; keyboard as BK-08. Focus and scroll are kept across repaints (`:414-424`).
- States: status loading `skeleton('rows', 4, 'Loading your brokerage')` (`:404`); status error card (`:403`); not available (`:405`);
  guest (`:406`); upgrade (`:408`); not linked (`:409`); section loading `skeleton('rows', 5, 'Loading <Section>')` (`:172`); section error card
  with the server's sentence (`:170, 451`); a section that throws while drawing: "This section could not be drawn. Reload the page; if
  it persists, report it from Settings, Report a problem." (`:166`); sandbox banner (`:421`).
- Preferences and storage: `optic.brokerage.section.v1` (read `:512`, written `:495`; device setting, not in the personal list);
  `optic.brokerage.scope.v1` (read `:76-80`, written `:607`; personal); `optic.thesis.v1` (one symbol's browser copy removed when a
  thesis is deleted, `:577`; `store.js:345-351`). Milo context on Send: `{view:'brokerage', brokerage_scope:[ids], focus_label}`
  (`:513`): ids only, no holdings; the server attaches holdings itself (R-BK-1). The overview refreshes itself every 60 s from 4:00 am
  to 8:00 pm ET on weekdays while the tab is visible (`:479-489, 489`).
- Risks seen in code:
  - **R-BK-1 (b) P0, BUG-007** `main.py:7784-7787, 7802-7845, 7738-7778` (fix `2236205` exists only on branch `milo-portfolio-privacy`;
    `git merge-base --is-ancestor 2236205 HEAD` says it is not in this branch). `_LINKED_WORDS` matches bare "position(s)",
    "exposure", "allocation", "concentrat*", "portfolio", "holdings", "i own", "i hold"; on a match from any page `/api/chat` receives the
    reader's whole `brokerage_portfolio` block (holdings, weights, fund look-through); and `get_my_portfolio` is offered on every page
    unless the reader set the scope to none or market (`:7776-7777`), fenced only by its description. A Compare question containing
    "position setup" quoted the owner's real holdings (live, 2026-10-27). A reader who linked an account and then asks anything with
    these words is sent to Anthropic without having asked about their portfolio.
  - **R-BK-2 (a) P1** `ai.py:1901-1902, 1911, 1945-1947`; Milo's prompt `ai.py:390-391`. Personalised AI text about real holdings is kept
    from advising by prompt alone: "Describe; do not advise. No buying, selling, trimming, adding or 'consider'" and "never tell the
    reader to buy, sell or rebalance". Nothing after generation checks the briefing fields (`headline`, `what_changed`, `drivers`,
    `ahead`, `attention`): the code only strips em dashes, then stores and shows it as "Written by Milo from the measured figures"
    (`brokerage.js:221`). The server-built text I read (`briefing.py:190-230`, `alerts.py:165-265`, `portfolio.py:333-362`,
    `exposure.py:362-396`, `options_risk.py:622-713`) describes and never instructs; the nearest to an instruction is "Check the account
    for the exercise, assignment or removal." (`options_risk.py:653`).
  - **R-BK-3 (f) P2** `workspace_routes.py:126-134`; `main.py:7500-7507`; `workspace.py:581-589`. "Write it up" spends one Milo message in
    `_spend_guard` before the writer runs and nothing refunds it when the model fails (502 "The briefing could not be written."); the
    cache key contains the top eight moves rounded to 0.1%, so the same day's briefing is "not charged again" only while the prices stay
    put (the page promises "The same figures are kept and not charged again", `brokerage.js:222`).
  - **R-BK-4 (d) P2** `brokerage.js:124, 135, 138`; `service.py:287-289`. "Reconnect" is offered when `ent.can_link`, but the consent box is
    drawn only when a new connection can be added; with the plan's connections full and the terms version changed, Reconnect answers 428
    "Tick the box above Connect." and no box exists.
  - **R-BK-5 (d) P2** `brokerage.js:559, 564, 491-498`. "Disconnect and delete" and "Yes, delete all brokerage data" stay armed (`S.armed`)
    when the reader leaves the section and comes back; one click then deletes.
  - **R-BK-6 (a/legal) P2** `core/legal.js:21-36`. No area notice is mapped for Brokerage although it shows scores such as "Moderately
    diversified", scenario losses and an AI briefing about real holdings; the page relies on per-block disclaimers (`brokerage.js:271`,
    `ui/scenarios.js:71`) and the global footer.
  - **R-BK-7 (b) P2** `routes.py:277-352`; `service.py:166-167`. The sandbox portal and its two POST routes need neither a session nor a
    CSRF header; they exist only while the sandbox provider is configured and not on a hosted deployment unless a flag allows it.
  - **R-BK-8 (e) P2** `brokerage.js:143`; `store.py:458-465`. The section says "deletes everything Optic stored about them", but the
    reader's theses (Dossier-shared, `account.py:582-643`) and `portfolio_alert_settings` remain.
  - Race check: `loadSection`, `loadBriefing`, `loadExtras` and `refreshOverview` all drop a reply whose scope key or request key changed
    (`brokerage.js:442-455, 457-478, 483-488`); no stale-response defect found.

### Brokerage Overview — `#/brokerage/overview`
- Files: `pages/brokerage.js:182-223`; server `workspace.py:248-290, 569-589`, `briefing.py`.
- Purpose: value, the day's move, change since the last sync, the largest holdings, what deserves attention, the written briefing.
- Auth: signed in, linked, and open to the reader (above).
- Sections in render order: four tiles (**Value now** or **Total value**, **Today**, **Since your last sync**, **Unrealised gain**), each
  tagged Broker-reported, Market data or Optic calculation (`:187-192, 60-62`); **What you own** (`bo-h`, five largest as a share of long
  value, "By kind", a button) and **Deserves attention** (`ba-h`, up to five observations, unread alerts, "Coming up" up to six events)
  side by side (`:193-201`); **Briefing** (`bb-h`, `:209-223`); **Ask about your portfolio** (`bq-h`, `:203-205`); the "What this cannot
  tell you" fold (`:206`).
- Data source: `GET /api/brokerage/workspace/overview?accounts=` (`:448`) and `GET .../briefing` (`:461`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| OV-01 | button | "Holdings & Exposure" (`:197`) | `[data-v2-bk-go=holdings]`: switch section (`:525`) | |
| OV-02 | text link per observation | "Open" (when the observation points to another section) (`:199`) | `[data-v2-bk-go]` | |
| OV-03 | text link | "Read alerts" when there are unread alerts (`:200`) | `[data-v2-bk-go=events]` | |
| OV-04 | button | "Write it up" / "Writing..." (disabled while running); "Uses one Milo message. The same figures are kept and not charged again." (`:222`) | `[data-v2-bk-write]`: `POST /api/brokerage/workspace/briefing/written {accounts}`, 90 s (`:530-534`) | paid; owner exempt; on failure toast "The briefing could not be written." (`:532`) |
| OV-05 | Milo chips x6 | "Where is my portfolio concentrated?", "Which upcoming earnings affect my holdings?", "Explain my exposure in plain English.", "What changed since my last sync?", "Why did my portfolio move today?", "What risks deserve more research?" (`ASKS` `:35`; `:204`) | each `[data-v2-milo]` drafts the question with label "Your linked portfolio" and the panel's figures | note: "Milo reads only your own linked accounts, read-only, and describes rather than advises. Each question uses one Milo message when you send it." (`:205`) |
| OV-06 | links | headline links under "Possibly related" (`newsItem`, `:208, 218-219`) | open the publisher's page in a new tab, `rel=noopener` | the page says they are matched by time, "not evidence that they caused the move" (`:220`) |
| OV-07 | fold | "What this cannot tell you" (`limits`, `:63`) | native | |

- Tables and AI: Measured table: Holding, Today, Contribution (`:216`). **AI-generated section**: the written briefing (headline and
  four paragraphs "what changed", "drivers", "ahead", "attention") with "Written by Milo from the measured figures on this page, N ago."
  (`:221`); endpoint `POST .../briefing/written`; paid (one Milo message per new set of figures) as in the gate entry. Before it is written
  the page shows the measured figures and the headlines only.
- States: loading skeleton "Loading Overview" (`:172`); error card with Try again (`:170`); briefing loading "Measuring what moved..."
  (`:211`) and error text (`:212`); "No quotes" in the Today tile and "Optic could not price your holdings just now." (`:190`); "Nothing stands
  out: no concentration over your thresholds, no reports this week, every account synced." (`:199`); "Nothing scheduled in the window for what
  you hold." (`:347`); "Nothing to show." (`:66`); "No quotes to measure with just now." (`:216`); "No large movers to look for headlines about."
  (`:218`); "An earlier write-up (N ago) was from different figures." (`:222`).
- Risks: R-BK-1 to R-BK-3 above apply. **R-BK-9 (f) P2** `brokerage.js:191, 194, 69`: the "Since your last sync" tile falls back with
  `|| '0'` on an array, which is truthy when empty, so an empty change shows a blank tile; `holdings_count || 0` prints "0 holdings ... in 0
  accounts" when the field is missing; `shareRows` turns a missing value into 0 and `bars()` then hides the row without saying so.

### Brokerage Holdings & Exposure — `#/brokerage/holdings`
- Files: `pages/brokerage.js:226-283`; server `workspace.py:291-460`, `exposure.py`, `lookthrough.py`, `scorecard.py`, `options_risk.py`;
  scenarios `ui/scenarios.js`, `app/analytics/scenarios.py`.
- Purpose: every holding with the broker's price and Optic's quote, exposure by sector, asset class, country, currency and company
  (looking through funds), five assessments, option Greeks and a hypothetical revaluation.
- Sections in render order: **Holdings** (`bh-h`); **Exposure** (`be-h`); **Optic scorecard** (`bs-h`); **Options risk** (`bx-h`, only
  with option positions); **What could happen to these positions** (`bsn-h`, only with holdings or options); **Cash** and **Not counted**
  (side by side, only when present); the limits fold (`:230-239`).
- Data: `GET .../holdings` (`:448`); then in parallel `GET .../scorecard`, `GET .../options` (only with options) and `GET .../scenarios`
  (only with holdings or options) (`:466-478`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| HX-01 | links | each holding's symbol `#/SYM` (`:234`) | navigation | |
| HX-02 | segmented | "Sector view": "With look-through", "Direct only" (`:249`) | `[data-v2-bk-sectors]` swaps the bars client-side (`:528`) | no request |
| HX-03 | folds | "Inputs and method" per assessment (`:270`); "What this cannot tell you" under holdings, exposure, options (`:63, 239, 256, 282`) | native | |
| HX-04 | button (retry) | "Try again" in the scenarios error (`ui/scenarios.js:66-67`) | `retry.scenarios` (`:628`) | |
| HX-05 | top-bar Ask Milo | see BK-07 | | |

- Tables and charts: Holdings: Holding, Accounts, Qty, Broker price, Quote now, Value, Weight, Cost basis, Unrealised (`:232`). Companies:
  Company, Direct, Through funds, Total, Share (`:253`). Options risk: Contract, Contracts, IV, Delta (sh), Theta / day, Vega / pt, Notes
  (`:278`). Scenarios: If, Change in value, Of today's value, Hardest hit, Options alone, Delta alone says (`ui/scenarios.js:22`). Share
  bars for top holdings, kind, sector, asset class, country, currency (`bars`, `:64-68`). Scorecard: five assessments (Diversification and
  Financial quality carry a 0-100 score; the others are labelled "Not scored"), a bar, driver names and "Not assessed" lines (`:264-271`;
  `scorecard.py:1-30`).
- AI-generated sections: none; Ask Milo only.
- States: loading skeleton; error card; empty table "No holdings in these accounts." (`:236`); scorecard "Calculating the five assessments..."
  (`:259`), error text (`:260`), "No assessments could be made." (`:270`); options "Calculating Greeks..." (`:274`), unavailable text
  (`:275`); scenarios states (`ui/scenarios.js:65-68`); a 2% difference note "The broker's price and Optic's quote differ by 2% or more for
  ..." (`:237`).
- Risks: **R-BK-10 (f) P2** `brokerage.js:232, 235, 236, 254`. Column "Weight" names no denominator (the Overview says "share of long value",
  `:194`); "Unrealised" percent names no base; the table prints missing cost basis as "Not supplied" (good) but `direct_usd || 0` and
  `stock_shares || 0` print 0 for a missing figure (`:254, 281`). Scenario "Of today's value" is explained in the fold, not in the header.
  (a) The scenario lead sentence "If every holding fell 10% together, these positions would be worth about $X less" is personalised and
  hypothetical, labelled so (`ui/scenarios.js:30-35, 71`); no instruction found.

### Brokerage Performance — `#/brokerage/performance`
- Files: `pages/brokerage.js:285-343`; server `workspace.py:468-548`, `performance.py`.
- Purpose: time-weighted and money-weighted return against a chosen benchmark, flows, income and costs, attribution.
- Sections in render order: **Performance** (`bp-h`: period buttons, benchmark select, short-history note, four tiles, "Measured START to
  END", two charts); **Money in and out**; **Income and costs**; **What drove it**; **History this rests on** (`:301-328`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| PF-01 | segmented x5 | "Period": 1M, 3M, YTD, 1Y, All (`PERIODS` `:32`; `:302`) | `[data-v2-bk-period]`: sets `W.period`, clears cached data, reloads (`:529`) | a period reaching back past the first stored value is disabled with title "Needs history back to DATE" and "All" shows pressed (`:300, 302`) |
| PF-02 | select | "Benchmark": S&P 500 (SPY), US total market (VTI), Nasdaq 100 (QQQ), World stocks (ACWI), US bonds (AGG) (`BENCHMARKS` `:33`; `:303`) | `[data-v2-bk-bench]` change (`:608`) | server accepts only these five (`workspace_routes.py:32, 95-96`) |
| PF-03 | folds | "What this cannot tell you"; "How these are calculated" (`:328`) | native | |

- Charts: `cum` (cumulative time-weighted return against the benchmark, two lines and a zero line, `lineChart`) and `val` (account value
  against starting value plus net deposits), the two crosshairs synchronised by date (`:330-343`); both state "The value line includes your
  own deposits and withdrawals, so it is not a return" (`:311`). Tables: "What drove it": Holding, Contribution, Of average capital (`:322`).
- States: not enough history: `limitations[0]` or "There is not enough history yet to measure a return." (`:312`); attribution unavailable
  reason (`:324`); add-on note "SnapTrade's balance-history add-on is off for these accounts..." (`:327`); short periods (`:304`).
- Risks: none of class (a). **(f)** the tiles carry their source chip and the measured dates (`:305-308`), the best-labelled figures in
  this section; one gap: `Fees paid` and `Taxes withheld` take `Math.abs` of the stored value (`:318`), so a refund would read as a charge.

### Brokerage Events & Research — `#/brokerage/events`
- Files: `pages/brokerage.js:346-398`; server `workspace.py:550-566`, `events.py`, `desk_section.py`, `alerts.py`.
- Purpose: calendar of what the reader holds, the reader's own theses, Optic Desk sources that touch their holdings, portfolio alerts.
- Sections in render order: **Your calendar** (`bv-h`); **Your theses** (`bt-h`); **Optic Desk, for your portfolio** (`bk-desk`);
  **Alerts** (`bl-h`) (`:357-366`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| EV-01 | buttons-as-links | "Earnings analysis", "Dossier", "Options" per calendar row (`:351`) | links to `#/SYM/earnings`, `#/SYM`, `#/SYM/options` (server strings, made hash-safe by `v2href`, `:354`) | |
| EV-02 | button | "Edit" per thesis (`:376`) | `[data-v2-bk-thesis-edit]` shows the form for that symbol (`:572`) | |
| EV-03 | button, two-step | "Delete", then "Delete thesis" (`data-v2-confirm`) (`:376`) | first press arms (`W.thesisArmed`), second `DELETE /api/theses/SYM` and removes the browser copy (`:574-579`) | no timeout on the armed state |
| EV-04 | buttons | one per held symbol without a thesis (up to 12), after "Write down why you own it:" (`:381`) | `[data-v2-bk-thesis-edit]` | |
| EV-05 | form | six fields: "Why I own it", "Horizon" (input, 200 characters, placeholder "For example: 3 to 5 years"), "What I am assuming", "What would make me reassess", "Risks I accept", "What I am watching for" (textareas, 2 rows, 8000 characters) (`THESIS_FIELDS` `:46`; `:370-372`) | submit: `PUT /api/theses/SYM` with `{bull, horizon, assumptions, invalidation, bear, catalysts}` (`:615-621`) | "Save thesis" and "Cancel" (`:372, 573`); the server needs at least one non-empty field (`account.py:598-601`) and caps 200 theses (`:503, 606-613`) |
| EV-06 | Milo button | "Ask Milo about this thesis" (`:380`) | drafts "How does what has happened since I saved my SYM thesis bear on it? My thesis: ..." with up to 300 characters of the reader's own text and 200 of "reassess if" | the reader's words go to Milo only on Send |
| EV-07 | links | "Source" per desk item (new tab), "Read the full edition" `#/read` (`:363, 365`) | navigation | |
| EV-08 | button | "Check now" (`:389`) | `[data-v2-bk-alerts=check]`: `POST /api/brokerage/workspace/alerts/refresh`; toast "N new alert(s)." (`:582`) | evaluates the reader's counted accounts and stores new alerts |
| EV-09 | button | "Mark all read" when unread (`:389`) | `POST .../alerts/seen` (`:583`) | |
| EV-10 | links | "Open" per alert (`:388`) | navigation | |
| EV-11 | fold | "Alert settings" (`:390`) | native | |
| EV-12 | checkbox + select | "A holding reports within [3, 7, 14] days"; "One holding passes [10, 15, 20, 25, 33] % or one sector passes [30, 40, 50, 60] %"; "A holding's weight moves [3, 5, 10] points in about a month"; "A sector's share moves [5, 10, 15] points in about a month"; "Something new about a name with a thesis"; "A connection needs attention" (`:391-395`) | `[data-v2-bk-alert]` change edits a draft only (`:609-613`) | choices come from the server (`alerts.py:43-49`) |
| EV-13 | checkbox | "Also email me a count of new alerts (nothing about holdings is put in the email)" (`:396`) | same draft | server mail carries a count and a link only (`alerts.py:323-342`) |
| EV-14 | button | "Save alert settings" (`:397`) | `PUT /api/brokerage/workspace/alerts/settings` with the draft; toast "Alert settings saved." (`:584`) | server validates every value against the choices (`alerts.py:84-120`) |

- Tables and lists: calendar rows (date, "in N days", symbol, Earnings / Ex-dividend / Option expiry, Confirmed or Estimated tag, "Its last N
  reports came after the close.", "N% of portfolio", note) (`:349-351`); theses with "Since you saved it" developments (`:379`); desk items
  (`:363`).
- AI-generated sections: none written for the reader. "Optic Desk, for your portfolio" shows the Desk edition's own sources that touch the
  holdings: "nothing was rewritten for you" (`:362`).
- States: "Nothing scheduled in the window for what you hold." (`:347`); "No theses yet." (`:380`); "Nothing new found in headlines, filings or
  the calendar." (`:379`); desk unavailable `clean(desk.reason || 'No edition is available.')` (`:365`); "Nothing in this edition touches what you
  hold." (`:363`); "No alerts yet." (`:388`).
- Background, not reader-initiated: the brokerage loop wakes every ten minutes and, for each linked reader whose alerts were not
  refreshed in the last six hours (`ALERTS_EVERY_HOURS`), evaluates them and, if the reader opted in, mails a count and a link
  (`routes.py:358-377`; `workspace.py:595-640`; `alerts.py:323-342`). Alert text is stored sealed per reader (`alerts.py:271-293`).
- Risks: none of classes (a), (c). Alert wording is descriptive ("Above the 20% you set for a single holding", `alerts.py:200`).

### Brokerage Connections — `#/brokerage/connections`
- Files: `pages/brokerage.js:108-145`; server `routes.py`, `service.py`, `store.py`.
- Purpose: link, sync, rename, count or leave out accounts, reconnect, disconnect, delete.
- Sections in render order: the paused notice (when the plan lapsed); **Connections** (`bc-h`: "Connect a brokerage", consent line, plan
  sentence, one card per connection); "What Optic can and cannot see" fold; **Delete all brokerage data** (`bd-h`, only when connections exist)
  (`:136-144`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| CN-01 | checkbox | consent sentence (see the link flow) (`:106`) | `[data-v2-bk-consent]` change: enables or disables Connect without a repaint (`:600`) | state `S.agreed` is module-level |
| CN-02 | button | "Connect a brokerage" (`disabled aria-disabled` until ticked) (`:137`) | `[data-v2-bk-connect]`: the link flow (`:541-550`) | drawn only when the plan can add a connection |
| CN-03 | button per connection | "Sync now" / "Syncing..." (`:123`) | `[data-v2-bk-sync]`: `POST /connections/{id}/sync`, 90 s; toast from the result ("Refresh requested. Your broker's data usually arrives within a few minutes; this page updates when it does.", "Synced.", "Synced, but some data did not arrive.", "Your broker needs you to reconnect.", "The provider did not respond. Showing the last good data.", "A sync is already running.", ...) (`:552-557`) | hidden for expired, closed, paused or unsupported connections; plan cap enforced by the server |
| CN-04 | button per connection | "Reconnect" (`:124`) | `[data-v2-bk-reconnect]`: connect with `{reconnect:id}` (`:541-546`) | for expired, closed or error status |
| CN-05 | button, two-step | "Disconnect", then "Disconnect and delete" and "Keep" (`:125`) | `[data-v2-bk-disconnect]` arm / confirm / `[data-v2-bk-disarm]` (`:558-562, 568`) | confirm posts `/connections/{id}/disconnect` |
| CN-06 | checkbox per account | "NAME MASK, type, currency" with the sync state text (`:130-131`) | `[data-v2-bk-select]` change: `PATCH /accounts/{id} {selected}`, reverted on failure (`:601-606`) | "counted" accounts feed every section |
| CN-07 | button + input | "Rename", then a text box (40 characters, "Leave it blank to use the broker's name"), "Save", "Cancel" (`:127-131`) | `[data-v2-bk-rename]` etc.; Enter saves, Escape cancels (`:569-571, 595-597, 623-627`) | `PATCH /accounts/{id} {nickname}` |
| CN-08 | button, two-step | "Delete all brokerage data", then "Yes, delete all brokerage data" and "Keep it" (`:144`) | `[data-v2-bk-delete]` arm / confirm (`:563-567`) | `POST /delete-data` |
| CN-09 | fold | "What Optic can and cannot see" (`:142`) | native | |
| CN-10 | button | "Resume with Pro" (`:136`) | `[data-v2-bill]` | |

- Status words per connection: Connected, Partial sync, First sync running, Needs reconnecting, Provider not responding, Sync failed, Not
  supported, Paused: plan ended, Closed (`STATUS` `:45`); account lines "Broker data as of DATE", "Partial: some data did not arrive",
  "Provider did not respond; showing the last good data", "Last sync failed; showing the last good data", "No longer reported by the broker;
  left out", "Waiting for first data" (`:108-117`).
- States: "Nothing linked yet..." (`:140`); "Syncing is paused" with the 7-day and 30-day rules (`:136`; `routes.py:52-54`); plan sentence "Your plan
  links up to N connection(s) and M accounts. Accounts sync on their own once a day; Sync now is limited to K a day." or "Linking and syncing are
  part of the paid plan. Your stored data stays until you delete it or the retention period ends." (`:139`).
- Risks: R-BK-4, R-BK-5, R-BK-8 above.

---

## 3. Watchlist and Alerts

### Watchlist — `#/watchlist`
- Files: `pages/watchlist.js` (427); `core/store.js` (lists), `core/poll.js`, `ui/company.js` (row helpers and the company drawer),
  `ui/typeahead.js`, `ui/chart.js` (`spark`), `pages/tabs.js`. Server: `account.py:122-387` (stored lists), `main.py:2837-2862` (the feed),
  `app/analytics/watchlist.py`.
- Purpose: the reader's named lists as rows (price, day change, 30-session sparkline, volume against its 20-session average, next earnings,
  "what changed", signal), with sort, filter, find, reorder, add, remove with Undo, and a company drawer (`watchlist.js:1-10`).
- Auth: guest, account, owner differ only in where lists live. **Guest**: this browser, `optic.watchlists.v1` plus the flat `optic.chart.watch.v1`
  that Classic reads, at most 12 lists (`store.js:12-16, 114-142, 186-192`); the page says "Only in this browser. Sign in and Optic offers to bring
  these lists into your account, as lists. An account already used on this browser keeps its own lists, and these wait here until you sign
  out." (`:208`). **Signed in**: the account's lists on the server, capped by plan (Free 3, Pro 25, Enterprise 200, `auth/store.py:661-669`), the
  open list remembered in `optic.watchlist.account.v1` and mirrored into the flat key (`store.js:144-161, 186-192`); "On your account: saved as
  you change it, and the same on any device you sign in on." (`:207`). At sign-in the guest's lists are offered ("Bring them into my account",
  `app.js:97-103, 257-279`) and merged by name (`POST /api/watchlists/adopt`, `account.py:333-387`). The owner sees nothing different.
- Sections in render order: header (h1 "Watchlist", Ask Milo, tabs Watchlist and Alerts, `:305`); `#wl-body` (`:213-228`): lists bar or the
  first-list welcome, the add form, the saved note, the pulse tiles (Today: N up, N down; Biggest move; Something changed: N of M; Signals: N
  bullish, N bearish, `:121-134`), the controls, the rows with their footnote (`:149-192`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| WL-01 | Milo button | "Ask Milo about this list" (`:305`) | drafts "Which names on my watchlist need attention, and why?" | label `Watchlist` |
| WL-02 | chips | one per list: name and count (`:109`) | `[data-v2-list]`: `store.setActive`, clears rows, search, undo (`:387`) | `aria-pressed` |
| WL-03 | chip | "New list" (`:110`) | `[data-v2-list-new]`: opens the name form; at the cap it is `aria-disabled` and a toast says "The Free plan keeps 3 watchlists. Rename or delete one to make room." (guest: "Twelve lists is the limit...") (`:388-391`) | |
| WL-04 | form | name box (`maxlength 60`, required) with "Create list" or "Rename", and "Cancel" (`:102-107`) | `submit`: `store.createList` / `renameList` (`:364-373`); Escape cancels (`:375-377`); Cancel `:393` | duplicate names refused (409 or the guest check, `store.js:309, 322`) |
| WL-05 | text link | "Rename" (`:112`) | `[data-v2-list-rename]` (`:392`) | |
| WL-06 | text link, two-step | "Delete", then "Delete “NAME” and its N names?" with "Delete" and "Keep it" (`:113-115`) | `[data-v2-list-delete]` ask / no / yes: `store.deleteList`, toast "Deleted NAME." (`:394-401`) | only with two or more lists; the last list cannot be deleted (`store.js:327`); no Undo for a deleted list |
| WL-07 | icon buttons | "Move NAME earlier" and "Move NAME later" (`:116`) | `[data-v2-list-move]`: `store.moveList` (`:402`) | only with two or more lists |
| WL-08 | input + submit | "Add a ticker, such as MSFT" (`maxlength 12`, required, typeahead `data-v2-ta="submit"`) and "Add" (`:222-224`) | `submit` (`:335-363`): upper-case and share-class form; must match `^[A-Z0-9.^=-]{1,12}$` else toast "That does not look like a ticker. Try letters such as MSFT."; duplicate toast "SYM is already on NAME."; `api.knownSymbol` false gives "No quote came back for SYM. Check the symbol, or try its exchange suffix, such as SHOP.TO." while "could not ask" lets it through; `store.follow`; toast and inline Undo "SYM added to NAME." | one add per symbol at a time (`:346-350`); picking a suggestion adds it at once |
| WL-09 | input search | "Find in this list" (`:199`) | `input`: filters rows by symbol, drops the held order (`:378-380`) | shown only when the list has names |
| WL-10 | segmented | "Show": All, Bullish, Bearish, Moved 2%+ (`FILTERS` `:42-47`; `:200`) | `[data-v2-wl-filter]` (`:403`) | an unpriced row shows only under All (`:159`) |
| WL-11 | select | "Sort": Biggest movers, Gainers, Losers, Something changed, Volume against average, Next earnings, Optic signal, A-Z, My order (`SORTS` `:31-41`; `:201`) | `[data-v2-wl-sort]` change; stores `optic.v2.watchlist.sort.v1` (`:381-383`) | default "Something changed"; rows without the figure go last (`:27-29`) |
| WL-12 | button | "Reorder" (`:202`) | `[data-v2-wl-reorder]`: sort "My order", filter All, clears search, focuses the first move button (`:406`) | hidden while the sort is already "My order" |
| WL-13 | icon buttons | "Move SYM up" / "Move SYM down" (`:188`) | `[data-v2-sym-move]`: `store.moveSymbol`, focus stays on the same button (`:408-413`) | only in "My order" with no filter or search (`:169`) |
| WL-14 | button | each priced row (symbol, price, change, sparkline, volume, earnings, what changed, signal), `aria-haspopup=dialog` (`:181-186`) | `[data-v2-company]`: `openCompany` drawer (`:422-425`) | Up and Down arrows move between rows, Enter or Space opens (`:330-334`) |
| WL-15 | icon button | "Remove SYM from NAME" (`:189`) | `[data-v2-unwatch]`: `store.unfollow`, focus to the next row, inline Undo and toast (`:414-421`) | |
| WL-16 | button | "Re-sort" (`:171`) | `[data-v2-wl-resort]` (`:404`) | shown when a refresh would reorder the rows (see below) |
| WL-17 | button | "Undo" (`:172`) | `[data-v2-wl-undo]`: re-runs the inverse (`:407, 320-325`) | inline copy lasts 15 s (`:318`); the toast 10 s |
| WL-18 | buttons | "Clear the search" (`:174`), "Show all" (`:175`) | `[data-v2-wl-clear]`, `[data-v2-wl-filter=all]` (`:405, 403`) | empty-result cards |
| WL-19 | text link | "Try again" in "Prices did not load: ..." (`:170`) | `retry.watchlist` (`:312`) | |
| WL-20 | link | "Sign in" in the guest note (`:208`) | `#/signin` | |

- Company drawer (`ui/company.js:103-129`, opened by WL-14): title the symbol; "Last price", changes today, over 5 days and over 20; What changed, Signal
  with its reason, Volume, Next earnings (fetched on open if the page has not got it), Alerts ("None set. Set one" or "N set, M fired today. See
  it", links to `#/alerts?symbol=SYM`), Lists; buttons "Open the Dossier", Watch or Watching (removes the symbol from every list it is on, with
  Undo, `company.js:31-55`), "Chart", "Options", "Earnings", a "More" menu (Set an alert, Compare, Export research sheet [these three only on a
  phone], Show on Home, Copy ticker; `company.js:5-11`), "Ask Milo about SYM" (drafts "What should I know about SYM right now?"); footnote "From
  daily bars and the companies' published calendars, by fixed rules: nothing here is written by a model. Each change names the number that
  triggered it." (`:124`).
- Refresh behaviour: `poll` runs `quietRefresh` every 60 s in the trading day (4:00 to 20:00 ET weekdays) and every 5 minutes outside it, pauses while
  the tab is hidden, catches up once on return (`:73, 297`; `core/poll.js:25-50`). A refresh keeps the order on screen (`S.hold`) and offers
  "Re-sort" instead of moving rows under the reader; a price that moved flashes green or red for 1.2 s (`:274-291`).
- Tables and charts: a grid, not a table: Symbol, Price, Today, 30 sessions, Volume, Earnings, What changed, Signal (header `aria-hidden`, `:178`);
  sparkline per row (`:183`); footnote "Checked for new prices at TIME; checked again every minute in the trading day (or five minutes outside it).
  METHOD Volume is the last session's against its 20-session average. Earnings dates are the companies' published or expected dates, from Yahoo
  Finance." (`:191`).
- AI-generated sections: none (WL-01 and the drawer's Ask Milo spend only on Send). Milo context on Send: `{view:'watchlist', watchlist:{name, rows
  (every row object with its sparkline), earnings}}` (`:298`): the reader's own list.
- States: no lists: "You are not following anything yet. Add a ticker below to start your watchlist." (`:221`); empty list: "Nothing on this list yet.
  Add a ticker above, or press Watch on any company." (`:152`); loading `skeleton('rows', n, 'Loading the list')` (`:153`); list load failure
  `failed('Your watchlists', ..., {retry:'lists'})` (`:220`); feed failure banner and rows kept with "Price not loaded." (`:155, 170`); an unpriced row
  shows the server's reason, "No data returned for this symbol." (`:83, 187`); earnings cell "…" while loading, "Not loaded", "None set" (`:139-141`); no
  match for a search or filter (`:173-176`).
- API dependencies: `GET /api/watchlist?symbols=` (up to 40 per call, the page chunks lists longer than 40; public; cache 60 s, forced by the poll;
  `:76-84`; `main.py:2837-2852`); `GET /api/watchlist/earnings?symbols=` (public; cache 1 h; `:90`; `main.py:2855-2862`); `GET /api/watches` (signed in,
  alert counts, 30 s; `company.js:91-98`); `GET /api/quote/{SYM}` (add check, 5 min; `core/api.js:83-87`); `GET /api/search` (suggestions). Signed in
  only, all through `require_user`, writes with CSRF, every query scoped by the reader's id so another reader's id answers 404
  (`account.py:11-15`): `GET /api/watchlists`, `POST /api/watchlists`, `PATCH /api/watchlists/{id}`, `PUT /api/watchlists/{id}/order`, `PUT
  /api/watchlists/order`, `DELETE /api/watchlists/{id}`, `POST /api/watchlists/{id}/items`, `DELETE /api/watchlists/{id}/items/{symbol}`, `POST
  /api/watchlists/adopt` (`account.py:122-387`).
- Preferences and storage: `optic.v2.watchlist.sort.v1` (`:49, 64, 382`, device setting); `optic.watchlists.v1`, `optic.chart.watch.v1`,
  `optic.watchlist.account.v1` (`store.js:12-14`); `optic.watches.v1` read for the guest's alert counts (`company.js:94`); all personal keys except the sort.
- Risks seen in code:
  - **R-WL-1 (a) P2** `watchlist.js:44-45, 132, 186, 305`; `ui/company.js:57, 114`. A personal list carries "Bullish" and "Bearish" filters, a count "N
    bullish, N bearish" and a per-row signal word, and the Milo prompt asks which names "need attention". They are labelled as fixed-rule
    trend states ("price above a rising 9 > 21 > 50 stack", `analytics/watchlist.py:173-176`) and the drawer says nothing is model-written, but a
    reader can take "Bearish" on their own holding as advice.
  - **R-WL-2 (f) P2** `watchlist.js:80, 182, 191`. "Checked for new prices at TIME" is the browser's own clock at the fetch, also when the answer came
    from the 60 s cache, and the Price column carries no per-row as-of; the only market time is the "Daily bars to the session of DATE" line (`:133`).
  - **R-WL-3 (c) P2** `watchlist.js:80-81, 91`. `fetchRows` writes `S.checked` and `S.method`, and the earnings reply is merged into `S.earn`, before
    the staleness checks (`:266, 94`), so a superseded request can still set them; harmless today because both are keyed or cosmetic.
  - **R-WL-4 (d) P2** `watchlist.js:114-115`. Deleting a list asks once and cannot be undone, while removing a name and adding one both offer Undo.
  - **R-WL-5 (b) P2** `watchlist.js:298`. The reader's whole list, with every row's figures, goes to Milo with each question asked from this page.

### Alerts — `#/alerts`
- Files: `pages/alerts.js` (562), `pages/signals.js` (267), `core/watches.js`, `core/unread.js`, `ui/drawer.js`, `ui/typeahead.js`. Server:
  `account.py:905-1217` (stored alerts and hits), `main.py:2650-2772` (catalogue, check, run), `:2220-2267` (signal history), `:5697-5740` (the
  inbox), `app/watch_runner.py`, `app/analytics/watches.py`, `app/alerts.py`.
- Purpose: three kinds kept apart (`alerts.js:1-7`): the reader's own conditions on a symbol (with what fired and the signal history), Optic's own
  paper-book alerts (the same for everyone), and a pointer to portfolio alerts on Brokerage.
- Auth: **Guest**: alerts in `optic.watches.v1`, at most 40 (`core/watches.js:8-9, 33-37`); never checked by the server schedule: "In this browser.
  Checked only while this page is open, when you press Check now. Sign in to have Optic check them for you and keep what fired." (`:147`); "What
  fired" is replaced by "A history needs an account" with a sign-in button (`:180-182`); signal history in `optic.signals.v1`, at most 200
  (`signals.js:16-17`). **Signed in**: alerts on the server (limit 40, `account.py:905, 1070-1075`), checked by the scheduler on market days about
  every 30 minutes from 9:30 to 4:00 ET and once after the close, skipping holidays, prices about 15 minutes behind; "What fired" kept; signal
  history kept (`:148`). **Owner**: also the shared inbox's controls (`isOwner`, `:207`).
- Sections in render order (`:272-278`): **Your alerts** (`h-w`; "New alert"); **What fired** (`h-hits`); **Signal history** (`h-sg`); **From Optic's
  paper book** (`h-l`, "Not yours: these fire on the paper book Optic keeps for its scans and on the ranked universe, the same for every reader.",
  `:264-267`); and, only when the Brokerage flag is on, "Alerts about your linked brokerage holdings (earnings, concentration, drift) are on Brokerage"
  (`:270, 278`).

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| AL-01 | button | "New alert" (`:274`) | `[data-v2-al-new]`: opens the drawer form for a blank alert (`:501`) | |
| AL-02 | link | each symbol, to its Dossier (`:162`) | navigation | |
| AL-03 | button | "Check now" / "Checking…" per symbol (`:163`) | `[data-v2-check]`: `POST /api/watches/check {ticker, watches:[{id, kind, params}]}`, 60 s (`:510-523`); `record()` keeps what it read (signed in: `POST /api/watches/seen`; guest: into `optic.watches.v1` and `optic.signals.v1`, `:52-75`) | "Every alert on SYM is paused." toast when none are active (`:513`) |
| AL-04 | button | "Add" (plus icon) per symbol (`:164`) | opens the form for that symbol | |
| AL-05 | button | "Edit" per alert (`:171`) | `[data-v2-al-edit]`: form with the symbol and condition fixed, value editable (`:502-505`) | drawn only when the condition has a value |
| AL-06 | button | "Pause" / "Resume" per alert (`:172`) | `[data-v2-al-pause]` -> `setActive`: `PATCH /api/watches/{id} {active}`; toast "Paused: ..." or "Resumed: ... It starts again from its next check." (`:439-451`) | resuming re-arms from the next check |
| AL-07 | button | "Delete" per alert (`:173`) | `[data-v2-al-del]` -> `remove`: `DELETE /api/watches/{id}` (a soft delete; what it fired stays in the history) at once, no confirm; inline "Undo" and a toast (`:453-474`) | Undo posts `/api/watches/{id}/restore` or puts the browser row back |
| AL-08 | button | "Undo" (`:155`) | `[data-v2-al-undo]` (`:508`) | the inline copy has no timer; the toast lasts 10 s |
| AL-09 | chips | "Show": All, Price, Technical, Research signals, Options activity, with counts (only families that have hits) (`:83, 189`) | `[data-v2-al-fam]` (`:509`) | signed in only |
| AL-10 | checkbox | "New only (N)" (`:190`) | `change` (`:554`) | |
| AL-11 | button | "Show everything" (`:192`) | clears the family filter | |
| AL-12 | button | "Mark all as seen" (`:197`) | `[data-v2-hits-seen]`: `POST /api/watches/hits/seen`, then refresh the bell count (`:548-551`) | |
| AL-13 | selects x2-4 | Signal history filters: Status (All, Open, Invalidated, Expired), Side (Both, Bullish, Bearish), Symbol (when more than one), Setup (when more than one) (`signals.js:251-254`) | `change`: reloads the section (`alerts.js:556-558`) | signed in, the server filters (`/api/signals`); a guest's are filtered in the browser (`signals.js:104-109`) |
| AL-14 | button | "Show all" (`signals.js:256`) | `[data-sg-reset]` (`alerts.js:547`) | |
| AL-15 | fold per record | Date, symbol and setup, Bullish or Bearish, Open, Invalidated or Expired, and what the close was after 1, 5, 10 and 20 candles (`signals.js:234-241`) | native; open state kept across repaints (`alerts.js:561`) | detail: the record as it fired, what followed, conditions met, readings (`signals.js:198-231`) |
| AL-16 | button | "Set a swing setup alert" (no signals yet) (`signals.js:257`) | opens the form with that condition | |
| AL-17 | chips | Optic's book kinds with counts (only when more than one kind) (`:258`) | `[data-v2-book-kind]` (`:525`) | |
| AL-18 | checkbox | "Unread only (N)" (owner) (`:259`) | `change` (`:555`) | |
| AL-19 | button | "Why this fired" / "Hide why" (`:241`) | `[data-v2-book-why]`: the rule's own sentence and up to eight readings (`:526, 210-213`) | `aria-expanded` |
| AL-20 | button | "Mark read" per row (owner, unread) (`:242`) | `[data-v2-book-seen]`: `POST /api/alerts/seen {ids}` (`:527-537`) | a non-owner call answers `{marked:0, shared:false}` (`main.py:5719-5734`) |
| AL-21 | button | "Mark all read" (owner) (`:262`) | `[data-v2-book-seen-all]` | |
| AL-22 | button, two-step | "Clear all", then "Remove all N alerts from the inbox? This clears them for every reader and cannot be undone." with "Clear all" and "Keep them" (`:255-256, 262`) | `[data-v2-book-clear]` / `-yes` / `-no`: `POST /api/alerts/clear` (`:539-546`) | owner only; server `_write_guard` (`main.py:5737-5740`) |
| AL-23 | button | "Show all" when a view matches none (`:261`) | `[data-v2-book-kind=all]` | |
| AL-24 | drawer form | see below | | |
| AL-25 | button (retry) | "Try again" in each error card (`:152, 183, 246`; `signals.js:247`) | `retry.{watches, hits, alerts, catalogue, signals}` (`:433-437`) | |
| AL-26 | link | "Brokerage" (`:278`), "Sign in or create an account" (`:181`) | navigation | |

- **The alert form (a drawer, a sheet on a phone)** (`formBody` `:284-298`, `openForm` `:329-333`): "Symbol" (typeahead `data-v2-ta="submit"`, 12
  characters, read-only when editing); "When" select grouped Price, Technical, Research signals, Options activity, with the server's thirteen
  conditions: Price rises above, Price falls below, Moves more than (percent, default 4), RSI rises above (70), RSI falls below (30), MACD turns
  (Either direction, Bullish, Bearish), Breaks past every mapped level, Unusual options activity (Vol / OI at least, 2), Optic stance changes (Any
  change, Bullish, Leaning bullish only, Neutral, Leaning bearish only, Bearish), Earnings within (days, 7), Analyst estimates revised (Either direction,
  Revised up, Revised down), Insider transactions filed (Any filing, Purchases, Sales), A swing setup triggers (Any setup or a preset), Short interest
  changes by (percent, 15) (`analytics/watches.py:36-190`); the value field; a live sentence saying what fires and the current price from `GET
  /api/quote/SYM` (`summary` `:304-320`); an inline error line; "Create alert" or "Save changes" and "Cancel"; "Your other alerts on SYM"; the
  condition's own reason. Validation (`submit` `:340-384`): symbol shape, a quote exists for a new symbol, a value above zero (below 100 for a percent
  or RSI, 1 to 365 for days), no duplicate (guest `:368`; server 409), at most 40 (guest `:372`; server 403); a price alert is armed with the quote on
  screen (`ref_price`, `:359`). The server re-checks bounds and vocabulary (`account.py:944-989`). The form's events are caught on `document` while the
  page is open (`:476-497`). Focus returns to the row's Edit or "Check now" (`:381-382`).
- Tables and charts: lists, no charts. Optic's book groups rows by urgency (Needs attention, Worth knowing, For the record, `:206`).
- AI-generated sections: none; no Milo button on the page. Milo context on Send from this page: `{view:'alerts', alerts:[{symbol, condition, active,
  last_met_at}]}` (`:422`).
- States: loading skeletons "Loading your alerts", "Loading what fired", "Loading Optic's book" (`:154, 184, 247`); errors `failed('Your alerts' / 'What fired'
  / "Optic's book" / 'The list of conditions' / 'Signal history', ...)` (`:152, 183, 246, 286`; `signals.js:247`); empty "No alerts yet. A price level, a day's
  move, an RSI line, a change in Optic's stance or an earnings date." (`:156`), "Nothing has fired yet" (`:191`), "Nothing from the book yet" with the
  common-case explanation (`:250`), "No signals yet" (`signals.js:257`); not signed in: the history card (`:181`) and the browser-only note (`:147`);
  per-alert status lines "Fired today, TIME", "Last fired N ago", "Could not check: ...", "Checked N ago: STATE", "Set when SYM was $X", "Not checked yet. Its
  first check arms it; it fires on the change after that." (`:111-122`); owner delivery note "Set up to email you..." or the blockers fold (`:220-233`).
- API dependencies: `GET /api/watches/catalogue` (public, 1 h); signed in: `GET /api/watches` (`require_user`), `GET /api/watches/hits?limit=60`,
  `POST /api/watches`, `PATCH /api/watches/{id}`, `DELETE /api/watches/{id}`, `POST /api/watches/{id}/restore`, `POST /api/watches/seen`, `POST
  /api/watches/hits/seen`, `GET /api/signals` (all `require_user`, writes with CSRF; `account.py:1002-1217`, `main.py:2220-2234`); both: `POST
  /api/watches/check` (public: a guest's check needs no account; a signed-in reader's firing swing-setup alert is also written to their history;
  `main.py:2656-2716`), `POST /api/signals/followup` (public, stateless, at most 60 signals, `main.py:2236-2267`), `GET /api/alerts?limit=50`
  (public; delivery detail only for the owner, `main.py:5697-5716`), `POST /api/alerts/seen` and `POST /api/alerts/clear` (owner or write token,
  `main.py:5719-5740`), `GET /api/quote/{SYM}`, `GET /api/search`. `POST /api/watches/run` (the scheduler's, `_write_guard`) is not called by the page.
- Preferences and storage: `optic.watches.v1` (guest alerts), `optic.signals.v1` (guest signal history, `signals.js:16`), both personal; none else.
- Risks seen in code:
  - **R-AL-1 (d) P2** `alerts.js:289`; `ui/typeahead.js:61`. The symbol box has `data-v2-ta="submit"`, so picking a suggestion submits the whole form at
    once. With the default "Price rises above" the empty level stops it with "Level needs a number above zero."; but if the reader chose a condition with
    a default first (Moves more than 4%, RSI above 70, Earnings within 7 days, any choice-based one) and then picks a symbol, the alert is created before
    they can read the sentence.
  - **R-AL-2 (f) P2** `alerts.js:148, 318, 402`; `analytics/watches.py:636-639`; `main.py:3602, 3752, 3841`. The cadence ("about every 30 minutes from 9:30
    to 4:00 ET and once after the close, skipping exchange holidays") is typed into the page twice while the server's own `schedule` is fetched into
    `S.schedule` and never read; `WATCH_AUTO=false` stops the scheduled checks with no change to this copy.
  - **R-AL-3 (c) P2** `alerts.js:420, 398-415`. `render()` replaces the module-level `S` while earlier requests are still in flight; their
    callbacks write into the new `S`, so a quick leave and return can fill the new page with the old answers (same data, but a repaint on a page the
    reader has just rebuilt). Focus handling on a saved edit is BUG-015.
  - **R-AL-4 (resource) P2** `main.py:2656-2716`. `POST /api/watches/check` is public, builds a full swing snapshot per call ("about 20 seconds each",
    `:2668-2670`) and has no per-caller limit beyond the 25-watch cap in the body.
  - **R-AL-5 (b) P2** `main.py:5697-5716`. The shared inbox's `unseen` count, which is the owner's read state, is returned to every caller of
    `GET /api/alerts`; the page hides it from non-owners (`alerts.js:266`) but the API does not.
  - Wording (a): none found; the condition reasons say "Low RSI is not a buy signal" (`analytics/watches.py:75`).

---

## 4. Owner pages

All four are drawn by one module, `pages/reports.js` (189 lines), chosen by `route.view` (`app.js:63`: `reports`, `usage`, `accounts`, `metrics` all map to
`P.reports`). Common behaviour: the h1 is the page's name and, for the owner only, the group tab strip (Problem Reports, Claude usage, Accounts,
Metrics) (`reports.js:145`); `isOwner()` is `me.admin` from `/api/auth/me` (`:18`); a reader who is not the owner gets `notOwner()` and **no request is
made** (`load()` returns before fetching, `:151`); a refused answer (401, 403, 503) shows "These are not yours to read" / "This is not yours to read"
with the server's sentence (`:29-33`); any other failure is `failed(..., {retry:'load'})` (`:32`); loading is `skeleton('rows', 5, 'Loading')` (`:143`);
a reply is dropped when a newer request has started or the page left (`seq`, `:150, 159`); signing in or out re-runs the check (`onAuth`, `:189`). No page
here calls a model (`:5-6`). The group is `owner: true` in the rail (`nav.js:50`) and the palette (`ui/palette.js:33-36`). There is no area legal notice
(`core/legal.js:36`) and no storage.

Non-owner text: signed in: "These are for the owner of this site. This account is not the owner's, or its address has not been verified yet."
(Problem Reports only); guest: "These are for the owner of this site. Sign in with the owner's address to read them." and a "Sign in" button; the other
three pages: "This is for the owner of this site. Sign in with the owner's address to read it." (`:21-28`).

### Problem Reports — `#/reports`
- Files: `pages/reports.js:35-53`; server `main.py:5794-5882, 5963-5980`, `app/feedback.py`.
- Purpose: the owner's inbox of what readers filed with "Report a problem" (which needs a signed-in reader, `main.py:5822-5827`).
- Auth / server guard: `GET /api/feedback` and both resolve routes use `_write_guard`: a verified owner session **with the CSRF header**, or the shared write
  token in `x-optic-token`; with neither, 401 (token configured), 503 (hosted, no token configured), 403 (cookie without CSRF header); **open to anyone only on
  a local run with no token** (`main.py:7272-7327`, copy `:5745-5755`). The write token is not stored by v2; Classic keeps it in `optic.writeToken` (BUG-030).
- Sections: one: the Open and Resolved switch with counts, a lead line, a "Resolve all N" button, an email-delivery note, the list.

**Controls**

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| OR-01 | segmented | "Open N", "Resolved N" (`:43`) | `[data-v2-rp-tab]`: sets the tab, reloads (`:170`) | module-level `tab` is not reset on a later visit (`:17`) |
| OR-02 | button, two-step | "Resolve all N", then "Resolve all N? Press again to confirm" (`:44`) | `[data-v2-rp-all]`: first press arms for 5 s, second `POST /api/feedback/resolve-all`, toast "Resolved N." (`:177-182`) | open tab only |
| OR-03 | button per report | "Mark resolved" / "Reopen" (`:48`) | `[data-v2-rp-resolve]`: `POST /api/feedback/{id}/resolve {resolved}`, toast, reload (`:171-176`) | an update, never a delete (`main.py:5960-5962`) |
| OR-04 | link | "From NAME-less address" `mailto:` to the reporter (`:50`) | opens the mail client | the address is the reporter's account email |
| OR-05 | button/link | "Sign in" (non-owner, guest) (`:25-27`) | `#/signin` | |
| OR-06 | button (retry) | "Try again" (`:32`) | `retry.load` (`:187`) | |

- List fields: "Filed TIME, emailed or stored", the message (escaped), "From EMAIL" or "No account: sent before reports needed one", "Page: ... Reply to: ...
  USER-AGENT", "Resolved TIME" (`:46-52`). Counts and leads (`:38-42`): "Nothing resolved yet.", "Showing the N most recently resolved of M.", "Nothing open.", "No problem reports
  yet. When a reader uses Report a Problem, it lands here.", "Showing the newest N of M."; delivery note "Email delivery is off. ..." (`:45`).
- API: `GET /api/feedback?limit=50&status=open|resolved` (`:155`); `POST /api/feedback/{id}/resolve`; `POST /api/feedback/resolve-all`.
- Risks: **R-OR-1 (b) P2** `main.py:5847-5882, 5896-5911` against `:5928, 5957`: only Accounts and Metrics reply `Cache-Control: no-store`; this list (readers' addresses
  and messages) and the usage ledger carry no cache header (the same is true of the brokerage workspace, watchlist, watches and theses JSON, which hold holdings and
  personal lists: nothing under `app/brokerage/` or `account.py` sets one). **R-OR-2 (e) P2** `reports.js:29-33`: an expired owner session answers 401 "Sign in with the
  owner's account to see this page." but the card is headed "This is not yours to read".

### Claude usage — `#/usage`
- Files: `pages/reports.js:55-79`; server `main.py:5896-5911`, `app/ai_store.py`.
- Purpose: what the model has cost this deployment, by feature, "Recorded since DATE" (`:67`).
- Auth / guard: `_write_guard` as above, with its own refusal copy (`main.py:5885-5893`).
- Sections: lead line; table "Cost by feature": Feature, Today, 7 days, 30 days, Calls, Unused, Failed, with the Total in the footer (column `title`s explain Calls,
  "Answers written but thrown away", "Calls that failed", `:72`); the method note; "Latest calls" (25 rows): When, Feature, Model, Input, Output, Cost, Result (Used, Thrown
  away, Failed; the cell `title` is the call's note) (`:76-78`).
- Controls: none beyond the group tabs. No refresh button: the page reloads on a visit.
- States: `d.available === false` shows the server's reason or "The usage ledger could not be read." (`:65`); lead variants "No calls recorded. The assistant has no key, so nothing calls Claude and
  nothing is recorded until it has one." and "No calls recorded yet. Every call to Claude is recorded here from this deploy on." (`:68-69`); cost words "no price", "<$0.01", "+ unpriced" (`:56-62`).
- API: `GET /api/ai/usage` (forced), `GET /api/health` (60 s, failure ignored; supplies `assistant.enabled`) (`:156`).
- Risks: none of classes (a), (c). Costs are list prices for today, 7 and 30 days (`main.py:5900-5905`); "Today" has no stated day boundary (UTC or ET is not said on the page).

### Accounts — `#/accounts`
- Files: `pages/reports.js:81-92`; server `main.py:5914-5946`, `app/auth/store.py:534-583`.
- Purpose: everyone who has made an account, newest first.
- Auth / guard: `_owner_session_guard`: `ADMIN_EMAILS` must be configured (else 403 for everybody, the owner included), a session (401), a verified admin (403), and the CSRF header;
  there is no write-token path, "whose write token would let anyone holding that string read every reader's email" (`main.py:5914-5946`). Reply is `Cache-Control: no-store` (`:5928`).
- Sections: lead ("N accounts. X new in the last 7 days, Y in the last 30. Z with a verified email." or "Nobody has made an account yet.", `:84`); a table in a keyboard-reachable scroll region
  `role=region aria-label="Accounts table, scrolls sideways"` (`:87`): Person (name or "(no name)", email), Joined, Last active ("Not recorded" when absent), Last sign-in ("Never"), Signs in with
  (Password, a provider, Passkey or "N passkeys", or "None"), Status (Deactivated, Verified, Not verified); a note "No passwords or tokens are shown or kept here." (`:91`).
- Controls: none beyond the group tabs; no per-account action exists.
- States: as the common block; empty lead above.
- API: `GET /api/admin/accounts` (forced). The payload has no ids, hashes or provider subjects (`auth/store.py:534-543`).
- Risks: none of classes (a) to (f) beyond R-OR-2.

### Metrics — `#/metrics`
- Files: `pages/reports.js:94-137`; server `main.py:5949-5957`, `app/metrics.py`.
- Purpose: sign-ups, active accounts, four-week retention, questions to Milo and plans, "counted from Optic's own tables" with no analytics service (`:133`).
- Auth / guard: `_owner_session_guard` as Accounts; `Cache-Control: no-store` (`main.py:5957`). Counts only, no addresses (`:5951-5954`); the owner's own account and questions are left out and the
  page says so (`:99, 121`).
- Sections in render order: lead; four tiles (Accounts, Active 7 days, Active 30 days, Verified email); "Sign-ups and weekly active accounts" (Week of, Sign-ups, Verified, Active accounts, with "from DATE" or
  "Not recorded" for weeks before tracking began; a week still running reads ", so far"); "Came back after four weeks" (Week of, Sign-ups, Old enough, Came back with a percent, or "Too new"); "Questions
  to Milo" (Asked through, 7 days, 30 days, Since counting began; or "No questions counted yet."); "Model calls by feature" (Feature, 7 days, 30 days) when the ledger can be read; "Plans" (Plan, Accounts); fold
  "How this works"; "Counted TIME." (`:107-136`).
- Controls: none beyond the group tabs (the "How this works" fold is native).
- API: `GET /api/admin/metrics` (forced).
- Risks: none found. Weeks before recording are labelled, partial weeks are labelled, and retention says "Too new" rather than a zero (`:103-104, 118`): the best-labelled figures of this section.

---


## 5. Classic route map (written by the main session after this agent stopped at the usage limit, 2026-10-29)

Classic is served at `/classic`. Its addresses are the same hash routes as v2 (v2's router was written to use
Classic's scheme, `static/v2/js/core/router.js:1-3`), so every Classic view has a v2 page at the same address. The
26 views below are the ones the Classic crawl loaded (`tools/classic_crawl.py`), checked against `NAV_GROUPS` in
`static/app.js:47233` and `static/v2/js/nav.js`.

| Classic address | Classic view id | v2 page at the same address | Notes |
|---|---|---|---|
| `#/` | view-home | Home (`pages/workspace.js` with blocks from `pages/home.js`) | Classic's Home asked how Optic should explain things (`components/knowledge.js`); v2's Home does not (Phase 05) |
| `#/SYM` | view-overview | Overview (`pages/dossier.js`, `overview-research.js`) | |
| `#/SYM/chart` | view-chart | Chart (`pages/chart.js`) | |
| `#/SYM/options` | view-swing | Options (`pages/options.js`) | |
| `#/SYM/investing` | view-long | Investing (`pages/investing.js`) | |
| `#/SYM/earnings` | view-earnings | Earnings (`pages/earnings.js`) | |
| `#/SYM/financials` | view-financials | Financials (`pages/financials.js`) | |
| `#/SYM/news` | view-news | News (`pages/news.js`) | |
| `#/compare` | view-compare | Compare | |
| `#/read` | view-brief | Read | |
| `#/macro` | view-market | Macro | |
| `#/indices` | view-indices | Indices | |
| `#/explore` | view-explore | Explore | empty at 1440 in the crawl (BUG-029) |
| `#/scan` | view-scan | Scan | |
| `#/insiders` | view-insiders | Insiders | |
| `#/analysts` | view-analysts | Analysts | |
| `#/portfolio` | view-tracker | Optic Portfolio | |
| `#/paper` | view-paper | Paper Desk | |
| `#/retirement` | view-roth | Retirement | |
| `#/watchlist` | view-watchlist | Watchlist | |
| `#/alerts` | view-alerts | Alerts | |
| `#/settings` | view-settings | Settings | |
| `#/instrument/^GSPC` | view-instrument | Instrument | |
| `#/earnings` | view-earnings (week) | Earnings this week (`pages/earningsweek.js`) | |
| `#/brokerage` | view-brokerage | Brokerage | |
| `#/reports` | view-reports | Problem Reports (owner) | |

v2-only addresses with no Classic view: `#/signin`, `#/terms`, `#/privacy`, `#/dossier` (start page), `#/research`
(saved research), `#/SYM/sheet` (printable sheet), `#/usage`, `#/accounts`, `#/metrics`, `#/brokerage/<section>`.
No Classic view lacks a v2 equivalent.
