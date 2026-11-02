# Registry section A: app shell, search, Milo panel, account and preferences

Read-only source audit of `~/Optic/wt-ultra` (branch `post-demo-ultra`, HEAD `fce3e71`, 2026-10-29). Nothing was run, rendered or requested over the network: every statement below is **Source** evidence read from code. "The source draws X" means the template contains X, not that a browser was seen showing it.

## Conventions

- `x.js:N` with no prefix means `static/v2/js/x.js` line N (so `app.js:236` is `static/v2/js/app.js`, `ui/milo.js:1170` is `static/v2/js/ui/milo.js`, `core/api.js:39`, `pages/settings.js:246`). Classic files carry their `static/` prefix. Server files carry `app/`.
- Priorities: P0 = fix before anything else (secret or another reader's data exposed, money lost), P1 = fix before real readers rely on it, P2 = tidy or tighten.
- Risk letters follow the brief: (a) advice-like wording, (b) late response with no identity or abort, (c) duplicated or conflicting implementation, (d) control without handler or handler without control, (e) missing loading, error or empty state, (f) data without a time or source, (g) exposure of another reader's data or a secret.
- "Auth" says who can use the thing. **v2 itself is served only to the signed-in owner by default** (`OPTIC_V2_ACCESS` defaults to `owner`, `app/frontend.py:50-55, 67-71`; `/` serves classic to everyone else, `app/main.py:8250-8256`), so "guest" below means "when v2 is opened to all".
- Files not present: `static/v2/js/core/aiconsent.js` does not exist and no AI-consent gate exists anywhere in v2 (grep for `consent` finds only `pages/brokerage.js`). `static/v2/js/ui/symbols.js` exists and is covered.

## Entries in this file

Shell and navigation: A1 Page document and boot, A2 Router and page loader, A3 Rail, A4 Top bar, A5 Phone bar and More sheet, A6 Inspector drawer and its sheets, A7 Legal footer and status line, A8 Not found, load failure and bridge views, A9 Banners, notices and live regions, A10 App-wide click and key delegation, A11 Scroll memory.
Search: A12 Search palette, A13 Ticker typeahead and result rows, A14 Every other search or symbol box, A15 Search backend.
Milo: A16 Milo panel, A17 Answer renderer, A18 Scout (as the panel uses it), A19 Chat and research endpoints, A20 Levels, personas and timeframes.
Account and preferences: A21 Sign in page, A22 Email and provider links and passkeys, A23 Settings, A24 Terms and Privacy, A25 Dossier start, A26 Saved research, A27 Device session and personal keys, A28 Preferences, store and API client, A29 Auth endpoints, A30 Storage key master table, A31 Server-synced settings.
Closing: B Consolidated risk register for this section, C Not verified.

---

# Part 1. App shell and navigation

### A1 Page document and boot — `global`
- Files: `static/v2/index.html`, `app.js`, `core/device.js`, `core/classic.js`, `app/frontend.py` (page assembly), `app/main.py:8236-8270` (`/`, `/classic`, `/v2/`).
- Purpose: one HTML shell that paints the saved theme and text size before first paint, loads Scout, then boots the module graph and the shell.
- Auth: v2 reaches only the owner by default (see Conventions). The page loads for everyone it is served to; account state is read by `GET /api/auth/me` (`core/store.js:47`).
- Sections in render order: (1) `<head>` fonts from jsDelivr, four CSS files, inline theme script (`index.html:17-35`); (2) classic script `/components/scout.js` (`index.html:38`) then `js/app.js` module (`index.html:39`); the server injects an import map, `modulepreload` links, `#v2-graph` JSON, `<meta name="optic-build">` and `data-classic` on `<html>` (`app/frontend.py:136-152`); (3) body: empty `<div id="app">` and a `<noscript>` line (`index.html:42-43`); (4) `shell.mount()` fills `#app` (`ui/shell.js:71-90`).
- Boot order (`app.js:317-351`): theme, scale, motion applied (318), system-theme and `storage` listeners (319-321), `shell.mount` (322), `watchTables` (323), `wireGlobal` (324), `watchBuild` (325), `watchStatus` (326), `store.loadMe()` (327), `deviceCheck()` (328; may reload), `handleAuthLinks()` (332), `afterAuth()` (335), `checkAvailability()` (336), `startUnread` (337), `wireTypeahead(document)` (338), `watchGlossary` (339), `startStrips` (340), `scrollmem.start` (341), `router.onRoute(show)` (342), link `replaceState` (343-345), `router.start()` (346), sign-in toasts (347-350). `core/device.js` is imported first so a pending account switch finishes before any store reads (`app.js:1-3`, `core/device.js:204-218`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Skip link | link `a.skip[href="#main"]` | "Skip to content" | None of its own; a plain hash link (`ui/shell.js:72`) | Hash router reads `#main` as symbol MAIN (see R1) |
| No-JS link | link in `<noscript>` | "current app" | Navigates to `/` (`index.html:43`) | Says the current app needs JavaScript too |

- Inputs and search fields: none.
- Charts, tables, AI sections, tooltips, modals: none. Third-party request from the browser: jsDelivr fonts (`index.html:17-19`), disclosed in the privacy text (`pages/legalpages.js:45`).
- States: loading: none found (empty `#main`, `ui/shell.js:84`, until the first route draws after `await`s at `app.js:327-346`); error: none found for a failed module graph (`app.js:353` runs `boot()` unguarded); `<noscript>` text (`index.html:43`); toast "Optic could not check your sign-in. Showing this browser's lists for now." (`app.js:334`).
- API dependencies: `GET /api/auth/me` (force, 10 s, `core/store.js:47`); signed in: `GET /api/watchlists` (`core/store.js:167`), `GET /api/brokerage/status` (`app.js:111`); `GET /api/ai-allowance` (`ui/milo.js:333`); `GET /api/session` (`core/status.js:17`); `GET /api/health` (`core/status.js:29`); `GET /api/watches/hits?limit=1` poll (`core/unread.js:15`); `GET /api/build` (`core/build.js:22`).
- Preferences and storage keys: reads `optic.theme`, `optic.ui.scale.v1` (`index.html:28,32`); full table in A30.
- Risks seen in code:
  - R1 (P1, b/d): the skip link is `href="#main"` (`ui/shell.js:72`) with no click handler anywhere (grep of `static/v2/js` finds none). In a hash router `router.parse('#main')` returns `{view:'overview', symbol:'MAIN'}` (`core/router.js:21-43`), so a keyboard or screen-reader reader who activates "Skip to content" is taken to the Dossier for MAIN instead of past the navigation. Needs a handler that focuses `#main` without changing the address.
  - R2 (P2, e): no recovery UI if `app.js` or its import map fails to load, and `boot()` is not wrapped (`app.js:353`); the page stays blank.
  - R3 (P2, e): the first route is drawn only after `/api/auth/me` (10 s ceiling), `deviceCheck`, `handleAuthLinks` and, for a signed-in reader, `/api/watchlists` (20 s default) have returned (`app.js:327-346`); `#main` is empty meanwhile with no skeleton.

### A2 Router and page loader — `global` (every `#/…` address)
- Files: `core/router.js`, `nav.js`, `app.js:48-77, 135-198`, `core/classic.js`, `pages/bridge.js`.
- Purpose: turns the hash into a view, loads that page's module on first use, draws it into `#main`, and keeps the shell in step.
- Auth: none for routing. The owner pages (`reports`, `usage`, `accounts`, `metrics`) are hidden from the rail unless `me.admin` (`nav.js:88-90`) but the addresses can be typed by anyone; the server decides (`pages/reports.js:25-27` tells a non-owner "These are for the owner of this site").
- Route table (hash address → view → module): `#/` and `#/workspace` → `home` → `pages/workspace.js`; `#/dossier` → `dossierstart` → `pages/dossierstart.js`; `#/SYM` → `overview` → `pages/dossier.js`; `#/SYM/chart|options|investing|earnings|financials|news` → `chart|swing|long|earnings|financials|news`; `#/SYM/sheet` → `sheet`; `#/compare`; `#/read` → `brief` → `pages/read.js`; `#/macro` → `market`; `#/indices`; `#/explore`; `#/scan`; `#/insiders`; `#/analysts`; `#/portfolio` → `tracker`; `#/paper`; `#/retirement` → `roth`; `#/brokerage[/overview|holdings|performance|events|connections]`; `#/watchlist`; `#/alerts`; `#/reports|usage|accounts|metrics` → all `pages/reports.js`; `#/settings`; `#/signin`; `#/terms`, `#/privacy` → `pages/legalpages.js`; `#/instrument/SYM`; `#/earnings` → `earningsweek` (the week's reports); `#/research` → `saved` (`core/router.js:6-43`, `app.js:49-63`). An address whose first segment is not `[A-Z0-9.^=-]{1,12}` is `notfound` (`core/router.js:39`); anything of that shape that is not a slug is treated as a ticker (`core/router.js:38-43`).
- Sections in render order (`show()`, `app.js:135-198`): closed-v2 check → classic redirect (137); signed-in visitors to `#/signin` go Home (138); the page module is awaited with a newest-wins counter `SHOW` (140-150); previous page `dispose()`, drawers and palette closed (151-153); new `.page-view` replaces `#main` content (158-160); legal area notice re-inserted by a `MutationObserver` after the first section (165-176); `shell.paint` (178); `resetContext` for Milo (180); `scrollmem.arrive` (181); `page.render` (182); heading focus and `announce(title)` in the next frame (192-196).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Phone view selector | `select[data-v2-tabsel]` (drawn by `pages/tabs.js:13`) | "<group> view" with each page's label | Sets `location.hash` (or `location.href` for a non-hash value) (`app.js:295-299`) | Options come from `hrefFor` per page |
| Tab press | `nav.tabs a[href^="#"]` | page tab labels | `motion.tabPressed` (`app.js:234`) | Visual only; the hash change loads the page |
| Try again (module did not load) | link `a.btn` | "Try again" | Plain link to `hrefFor(view, symbol)` (`app.js:146`) | See R4 |
| Try again (render threw) | link `a.btn` | "Try again" | Same (`app.js:187`) | See R4 |

- Inputs and search fields: none.
- Charts, tables, AI sections: none. Legal area notices are static text from `core/legal.js:21-32` for views `swing, long, roth, earnings, tracker, paper, market, indices, brief` only (`core/legal.js:36`).
- States: loading: `.page-line` thin bar while a section loads (`app.js:121-124`, `ui/motion.js watchLoading`); error: "This page did not load / Its code could not be fetched. Check the connection and try again." (`app.js:146`) and "This page did not load / `<e.message>` or An error stopped it." (`app.js:187`); empty: none found.
- API dependencies: none of its own (page modules are static files).
- Preferences and storage keys: none; reads the address only. `history.state.v2k` is written by `core/scrollmem.js` (A11).
- Risks seen in code:
  - R4 (P1, e): both "Try again" controls are `<a href="#/…">` pointing at the address already showing (`app.js:146, 187`). A same-fragment link fires no `hashchange`, so `router.onRoute(show)` never runs and nothing is retried (`core/router.js:52-60`; there is no click handler for these anchors in `app.js:229-284`). The only working recovery is a manual reload. Use `router.go(...)`, which re-runs listeners for an identical hash (`core/router.js:53`), or a `data-v2-retry` button.
  - R5 (P2, g): a render failure prints the raw `e.message` of the JavaScript error to the reader (`app.js:187`).
  - R6 (P2, c/d): migration scaffolding is dead now that every page is `v2: true` (`nav.js:19-55`): the "opens in the classic app" labels and `.legacy` icon (`ui/shell.js:108-109, 138-142`), `pages/bridge.js:26-31` (only `notfound` ever reaches the bridge because `PAGES` has an entry for every other view, `app.js:63`), and `hrefFor`'s classic branch (`nav.js:77-86`).
  - R7 (P2, e): a ticker that shares a name with a route slug (`#/SCAN`, `#/READ`, …) can never be opened by address (`core/router.js:35-38`; none was checked against the directory); `#/watchlst` (a typo) opens a Dossier for WATCHLST rather than a not-found page (`core/router.js:38-43`).
  - R8 (P2, e): `announce(document.title…)` runs in the next animation frame (`app.js:192-196`) while many pages set `document.title` only after their data arrives, so a screen reader may hear the previous page's title.

### A3 Rail (desktop navigation) and its collapse — `global`
- Files: `ui/shell.js:14-35, 93-116`, `nav.js`, `app.js:236`.
- Purpose: labelled destinations for desktop (hidden at 860 px and below, `static/v2/css/components.css:695-697`).
- Auth: guest sees Home, Dossier, Compare, Markets, Discover, Positions, Watchlist; **Brokerage** appears only when `/api/brokerage/status` says `available` for a signed-in reader (`app.js:109-114`, `nav.js:88-90`); **Reports** only when `me.admin` (`app.js:108`).
- Sections in render order: brand link; `nav.rail-nav` with captions "Research" (Home, Dossier, Compare, Markets, Discover), "Tracking" (Positions, Brokerage, Watchlist) and "Owner" (Reports) (`nav.js:15`, `ui/shell.js:102-113`); foot with Settings and Collapse (`ui/shell.js:116`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Brand | link `a.brand` | "OPTIC TERMINAL" (aria-label "Optic Terminal, Home") | `#/` (`ui/shell.js:114`) | |
| Home | link `a.rail-row` | "Home" | `#/` (`ui/shell.js:105-111`) | `aria-current="page"` on the current group |
| Dossier | link | "Dossier" | `#/dossier` with no company opened this visit; `#/SYM` or the last Dossier tab for the company opened (`ui/shell.js:21-26, 98`) | Never reopens the persisted Recent list (owner rule, `core/store.js:78-82`) |
| Compare | link | "Compare" | `#/compare` | |
| Markets | link | "Markets" | Last page open in the group this visit, else `#/read` (Read, Macro, Indices) (`ui/shell.js:18-26`) | In-memory `NAV_LAST` |
| Discover | link | "Discover" | `#/explore` or last of Explore, Scan, Insiders, Analysts | |
| Positions | link | "Positions" | `#/portfolio` or last of Optic Portfolio, Paper Desk, Retirement | |
| Brokerage | link | "Brokerage" | `#/brokerage` | Only when the flag is on |
| Watchlist | link | "Watchlist" | `#/watchlist` or Alerts | |
| Reports | link | "Reports" | `#/reports` or last of Problem Reports, Claude usage, Accounts, Metrics | Owner only |
| Settings | link `a.rail-row` | "Settings" | `#/settings` (`ui/shell.js:116`) | |
| Collapse | button `[data-v2-rail-collapse]`, `aria-pressed` | "Collapse" | Toggles `.is-tight` on `.shell` and writes `optic.rail.tight.v2` (`app.js:236`, `ui/shell.js:14-16`) | State restored at mount (`ui/shell.js:73`) |
| Search fallback row | button `[data-v2-open-palette]` | group label | Opens the palette (`ui/shell.js:112`) | Never drawn, see R9 |

- Inputs and search fields: none.
- States: none found (rail is drawn synchronously from `nav.js`); the Brokerage row appears late (after `/api/brokerage/status`) and `afterAuth` resets the flag to false before re-reading it (`app.js:108-114`).
- API dependencies: `GET /api/brokerage/status` (`app.js:111`).
- Preferences and storage keys: `optic.rail.tight.v2` read/written by `ui/shell.js:15-16` (and watched by Milo's layout, `ui/milo.js:1037-1040`).
- Risks seen in code:
  - R9 (P2, d): `groupHref` always returns a string for the Dossier group (`ui/shell.js:24`), so the `button[data-v2-open-palette]` branch of the rail (`ui/shell.js:112`) and of the phone bar (`ui/shell.js:127`) can never be drawn; it is dead markup.
  - R10 (P2, c): the rail's Dossier link follows the "opened this visit" rule (`ui/shell.js:98`) but the palette's page rows fall back to the persisted Recent list (A12 R-PAL-1), two rules for one decision.

### A4 Top bar — `global`
- Files: `ui/shell.js:39-54, 71-90, 145-160`, `core/status.js:14-25`, `app.js:241-256`.
- Purpose: search, market session, alerts bell, Milo and account.
- Auth: Sign in chip for guests, initials for signed-in readers; bell only for signed-in readers with unread alerts (`core/unread.js:14-16`).
- Sections in render order: brand (phone only, CSS `static/v2/css/components.css:699`), search button, spacer, session chip, bell, Ask Milo, account button (`ui/shell.js:76-83`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Brand (small) | link `a.brand-sm` | logo; aria-label "Optic Terminal, Home" | `#/` (`ui/shell.js:77`) | Shown at phone width |
| Search | button `.search-btn[data-v2-open-palette]` | "Search or ask" (short: "Search") and a `⌘K` key hint; aria-label "Search companies, tickers and pages, or ask Milo" | `palette.open(b, {symbol: route.symbol})` (`app.js:241`) | The hint says ⌘K on every platform (`ui/shell.js:78`) while the shortcuts sheet adapts to Ctrl (`ui/shortcuts.js:8-9`) |
| Session chip | status `#session-chip` (`role=status aria-live=off`) | phase dot, label, ", next <label> at <clock>" | Not interactive; `title` holds the description and early-close note (`core/status.js:22-23`) | Refreshed each minute and when the tab returns (`core/status.js:50-51`) |
| Alerts bell | link `a.topbar-bell[data-v2-bell]`, `hidden` until unread | aria-label "Alerts" or "Alerts, N unread alerts"; badge shows `9+` above 9 | `#/alerts` (`ui/shell.js:39-46, 80`) | Count from `GET /api/watches/hits?limit=1` every 2 min (10 min off-hours) |
| Ask Milo | button `.topbar-milo[data-v2-milo]` | "Ask Milo" with Scout badge | `openMilo({...figures: panelFigures(b)})`, no panel so no figures (`app.js:242-246`) | `title` "Milo is switched off right now" when off (`ui/milo.js:355`) |
| Account | button `.account-btn[data-v2-account]`, `aria-haspopup=dialog` | "Sign in", or initials (first letter of first name or email plus last initial) | Opens the Account sheet (`app.js:254`, A6) | Empty text while `auth==='loading'` (`ui/shell.js:149`); `unknown` auth reads as "Sign in" (`ui/shell.js:155-158`) |
| Skip link | link | "Skip to content" | See A1 R1 | First element in the document |

- Inputs and search fields: none (the search button opens the palette, A12).
- Charts, tables, AI sections, tooltips: session chip `title`. Milo button is the entry to an AI section (A16).
- States: session chip renders empty when `/api/session` fails (`core/status.js:24`); bell hidden at zero.
- API dependencies: `GET /api/session` (ttl 50 s, 10 s timeout, `core/status.js:17`), `GET /api/watches/hits?limit=1` (`core/unread.js:15`).
- Preferences and storage keys: `optic.timezone` for the "next at" clock (`core/prefs.js:104-107`).
- Risks seen in code:
  - R11 (P2, c): hard-coded `⌘K` hint (`ui/shell.js:78`) vs platform-aware sheet (`ui/shortcuts.js:8-9`).
  - R12 (P2, f): the account chip shows "Sign in" when sign-in state is `unknown` (the check failed) (`ui/shell.js:145-158`, `core/store.js:51-53`); a signed-in owner whose `/api/auth/me` timed out is invited to sign in again, and only Settings explains (`pages/settings.js:39`).

### A5 Phone bar and the More sheet — `global` (≤ 860 px)
- Files: `ui/shell.js:118-143`, `nav.js:63-69`, `app.js:255`.
- Purpose: five-slot bottom bar; More lists every destination the bar does not name.
- Auth: as the rail.
- Sections in render order: `nav.tabbar[aria-label="Sections"]` with Home, Markets, Watchlist, Dossier, More (`nav.js:63-69`); the More sheet is an inspector drawer titled "More" with kicker "Sections" (`app.js:255`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Home tab | link `[data-v2-tab="home"]` | "Home" | `#/` | |
| Markets tab | link | "Markets" | Last Markets page this visit, else `#/read` | |
| Watchlist tab | link `[data-v2-tab="follow"]` | "Watchlist" plus a count dot (`9+`) when alerts are unread; aria-label "Watchlist. N unread alerts" | `#/watchlist` | Alerts live under this tab (`ui/shell.js:47-53`) |
| Dossier tab | link | "Dossier" | `#/dossier` or the company opened this visit | |
| More | button `[data-v2-more]` | "More" | `drawer.open({kicker:'Sections', title:'More', body: shell.moreBody()})` (`app.js:255`) | `aria-current="page"` when the current group is not on the bar (`ui/shell.js:120-121`) |
| More: Compare | link `a.more-row` | "Compare" with "Two to four tickers side by side" | `#/compare` | Captions from `WHAT` (`ui/shell.js:28-35`) |
| More: Explore, Scan, Insiders, Analysts | links under the "Discover" caption | "Explore", "Scan", "Insiders", "Analysts" with captions | `#/explore`, `#/scan`, `#/insiders`, `#/analysts` | |
| More: Optic Portfolio, Paper Desk, Retirement | links under "Positions" | with captions | `#/portfolio`, `#/paper`, `#/retirement` | |
| More: Brokerage | link | "Brokerage" "Your linked accounts, read-only" | `#/brokerage` | Flag only |
| More: Problem Reports, Claude usage, Accounts, Metrics | links under "Reports" | with captions ("What readers reported as broken", "What the model has cost", "Everyone who signed up", "Sign-ups, actives, retention and Milo") | `#/reports`, `#/usage`, `#/accounts`, `#/metrics` | Owner only |
| More: Settings | link | "Settings" "Your account and preferences" | `#/settings` | |
| More: Sign in | link | "Sign in" "A free account, for Milo and a saved watchlist" | `#/signin` (`ui/shell.js:142`) | Guests only |
| Search fallback tab | button `[data-v2-open-palette]` | group label | Opens palette | Never drawn (A3 R9) |

- Inputs and search fields: none on the bar (search is the top bar's button; the phone shows only "Search", `static/v2/css/components.css:699-701`).
- States: bar is mounted empty then painted by the route (`static/v2/css/components.css:743-745` reserves its height); More has no empty state because Settings is always present.
- API dependencies: none beyond A3.
- Preferences and storage keys: none.
- Risks seen in code: none beyond A3 R9. More lists each page of a multi-page group by its own address (`hrefFor`, `ui/shell.js:140`) and a single-page group through `groupHref` (141), so it never uses the in-memory "last page in this section" memory the rail uses; consistent by design.

### A6 Inspector drawer and the sheets built on it — `global`
- Files: `ui/drawer.js`, `app.js:95-104, 200-211, 254-279`, `ui/shortcuts.js`, `pages/settings.js:176-198`, `core/dom.js:62-88`.
- Purpose: one modal sheet (a bottom sheet on phones) for the Account sheet, More, the Welcome-back question, Keyboard shortcuts, Report a problem and other pages' evidence. `makeDrawer()` makes a second one with its own root for Milo (`ui/milo.js:996`).
- Auth: Account sheet differs by sign-in; Report needs an account.
- Sections in render order: scrim, panel `role=dialog aria-modal=true` with header (kicker, h2, optional actions, Close) and body (`ui/drawer.js:44-48, 87-90`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Close | icon button `[data-v2-close]` | aria-label "Close" (title "Close" when the drawer has header actions) | `close()` (`ui/drawer.js:49-51, 87`) | Focus returns to the opener, or its "twin" if the page redrew (`ui/drawer.js:16-26, 115`) |
| Scrim | div `.drawer-scrim` | none | `close()` on click (`ui/drawer.js:50`) | Dismisses sticky sheets too (R13) |
| Escape | key | none | `close()` via `trapFocus` when modal, or the panel's own handler when docked (`ui/drawer.js:59, 63`; `core/dom.js:64`) | |
| Tab | key | none | Focus trapped inside while modal (`core/dom.js:66-71`) | |
| Account: Sign in or create an account | link `a.btn.btn-primary` | "Sign in or create an account" | `#/signin` (`app.js:203`) | Guest sheet text "Signed out. Watchlists and watches are kept in this browser." |
| Account: Watchlists / Settings / Saved research | links `a.rail-row` in `nav.more-list[aria-label="Account"]` | "Watchlists", "Settings", "Saved research" | `#/watchlist`, `#/settings`, `#/research` (`app.js:209`) | Signed in only |
| Account: Sign out | button `[data-v2-signout]` | "Sign out" | `store.signOut()` then `app.settleAuth({said:'out', next:'#/'})` (`app.js:256`) | Posts `/api/auth/logout` |
| Welcome back: Bring them into my account | button `[data-v2-guest="bring"]` | "Bring them into my account" | `bringGuestThings()`, adopts lists, theses and valuation scenarios (`app.js:257-279`) | Sheet is `keep: true` |
| Welcome back: Leave them for the next guest | button `[data-v2-guest="keep"]` | "Leave them for the next guest" | `keepGuestThingsOut()` then reload (`app.js:259`, `core/device.js:136-150`) | |
| Shortcuts: static list | text | 5 groups, 19 key rows (`ui/shortcuts.js:11-39`) | None | Opened by `?`, the palette row, Settings, or `[data-v2-shortcuts]` |
| Report: message | textarea `name=message` | placeholder "What you did, what you expected, what happened instead." `maxlength=2000` | Counter shows "N left" under 300 (`pages/settings.js:194`) | Cmd or Ctrl+Enter sends (195) |
| Report: Send | submit | "Send" | `POST /api/feedback` with the typed text plus a context line (build "v2", page hash, where it was opened from, window size) and `page: hash` (`pages/settings.js:190-191`) | 401 reopens the sign-in variant (192) |
| Report: Cancel | button `[data-v2-report-cancel]` | "Cancel" | `drawer.close({force:true})` (`pages/settings.js:197`) | |
| Report (guest): Sign in | link | "Sign in" | `#/signin` (`pages/settings.js:178`) | Title "Sign in to report a problem" |

- Inputs and search fields: Report textarea only (above).
- Charts, tables, AI sections: none. Modals: all of the above; `announce("<title> opened")` on open (`ui/drawer.js:97`).
- States: Report error text "That did not send. <explanation>" (`pages/settings.js:192`); success toast "Sent. Thank you." or "Saved. It is on the server and will be passed on." (191).
- API dependencies: `POST /api/auth/logout` (`core/store.js:70`); `POST /api/watchlists/adopt`, `POST /api/theses/adopt`, `POST /api/valuations/adopt` (`app.js:267, 274-275`); `POST /api/feedback` (`pages/settings.js:191`).
- Preferences and storage keys: reads `optic.watchlists.v1`, `optic.chart.watch.v1`, `optic.thesis.v1`, `optic.valuation.v1` for adoption (`app.js:264, 357`); holder keys via `core/device.js` (A27).
- Risks seen in code:
  - R13 (P1, e): the "Keep what you made on this browser?" sheet is `keep: true` (`app.js:98`) but its Close button, scrim and Escape still dismiss it (`ui/drawer.js:49-51, 59`). `keep` only survives navigation (`ui/drawer.js:107`). Dismissed, the question cannot be reopened until a reload; meanwhile `holds(user)` is false (`core/device.js:192-197`), so `loadHistory` returns `[]` and `saveHistory` returns false (`ui/milo.js:132-138`) and `persist()` ignores the result (`ui/milo.js:145`): the signed-in reader's Milo conversations, Recent list and drafts silently stop saving.
  - R14 (P2, e): "Report a problem" from the footer sends the page hash and window size with the report (`pages/settings.js:190`); Milo reports send the first ~2,000 characters of a question and answer (`ui/milo.js:420-425`); the sheet says only "Sent from <email>" (`pages/settings.js:185`), so the extra context is disclosed on the Settings page (`pages/settings.js:170`) and in Milo's form, but not in the sheet itself.
  - R15 (P2, d): the Account sheet has no link to the Terms or Privacy page; they are reachable only from the footer (`core/legal.js:44`).

### A7 Legal footer and status line — `global`
- Files: `ui/shell.js:85`, `core/legal.js`, `core/status.js:26-37`, `app.js:235-239`.
- Purpose: app status, the disclaimer, policy links and the way back to the classic app.
- Auth: same for all.
- Sections in render order (`ui/shell.js:85`, `core/legal.js:43-46`): status paragraph with "Report a problem"; disclaimer line with "Full disclaimer"; policy links; classic switch; hidden full disclaimer.
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Report a problem | button `[data-v2-report-open]` | "Report a problem" | `openReport(...)` (`app.js:235`, `pages/settings.js:176`) | Sign-in sheet for guests |
| Full disclaimer | button `[data-v2-legal-more]`, `aria-expanded`, `aria-controls="legal-full"` | "Full disclaimer" / "Hide the full disclaimer" | Toggles `#legal-full` (`app.js:238`) | Five paragraphs (`core/legal.js:12-18`) |
| Terms of use | link | "Terms of use" | `#/terms` (`core/legal.js:44`) | |
| Privacy policy | link | "Privacy policy" | `#/privacy` | |
| Use the classic app | link `[data-v2-use-classic]` href `/classic` | "Use the classic app" and "The same account and data; you can come back from its footer." | Sets cookie `optic_ui=classic; path=/; max-age=31536000; samesite=lax` then `location.href = /classic + hash` (`app.js:237`) | Cookie has no `Secure` flag |

- Text drawn (not controls): `#app-status` "Quotes from Yahoo Finance, delayed about 15 minutes. Milo is available." or "Option chains real-time; other quotes may be delayed." and "Milo is switched off in this build." or "Milo is available with a free account." (`core/status.js:30-35`); line "Not financial advice. Optic Terminal is an independent research tool, not a broker-dealer or investment adviser. Data may be delayed or wrong, and trading involves substantial risk of loss." (`core/legal.js:34`).
- States: status line renders empty on failure (`core/status.js:36`); no loading state.
- API dependencies: `GET /api/health` (ttl 5 min) and `GET /api/ai-allowance` (ttl 1 min) (`core/status.js:29, 32`).
- Preferences and storage keys: writes cookie `optic_ui` (`app.js:237`); the print sheet hides the footer (`static/v2/css/pages.css:1941`) and the research sheet carries its own line (`pages/sheet.js:107`).
- Risks seen in code:
  - R16 (P2, f/e): the status line is computed once at boot (`core/status.js:49`) and never again, so after a first-time sign-in with nothing to swap (no reload, `core/device.js:165-173`) it still says "Milo is available with a free account." and a failed `/api/health` leaves it blank for the visit.
  - R17 (P2, c): "Delayed about 15 minutes" is a fixed sentence (`core/status.js:30`); Milo's panel computes a similar sentence from `/api/health` separately (`ui/milo.js:521`).
  - R18 (P2, f): Terms and Privacy are marked in force (`pages/legalpages.js:8`) and the file says they were "Not reviewed by a lawyer" (`pages/legalpages.js:3-5`); the footer presents them without that caveat.

### A8 Not found, load failure and bridge views — `#/<unknown address>`
- Files: `pages/bridge.js`, `app.js:143-148, 185-188`, `core/router.js:39`.
- Purpose: what the reader sees when an address is not a page, a module fails, or a page throws.
- Auth: none.
- Sections in render order (not found): header `h1` "Page not found"; state card "That address is not a page / Check the ticker, or search for the company." with two buttons (`pages/bridge.js:20-22`); `document.title = "Page not found, Optic"` (23).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Search | button `[data-v2-open-palette]` | "Search" | Opens the palette (`app.js:241`) | |
| Go to Home | link | "Go to Home" | `#/` (`pages/bridge.js:22`) | |
| Open <page> (bridge) | link | "Open <label>" with an out icon | Classic address (`pages/bridge.js:30`) | Unreachable now (A2 R6) |
| Try again | link | "Try again" | See A2 R4 | |

- Inputs and search fields: none. States: this entry is the state. Risks: see A2 R4, R6.

### A9 Banners, notices and live regions — `global`
- Files: `core/build.js`, `core/status.js:38-56`, `ui/toast.js`, `core/dom.js:76-88`, `app.js:119-124`, `ui/milo.js:346-357`.
- Purpose: tell the reader the app changed under them, the network is gone, or something succeeded.
- Auth: none.
- Controls and text: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| New version bar | `div.build-new[role=status]` | "A new version of Optic is ready." | See buttons below (`core/build.js:47`) | Checked when the tab becomes visible and every 10 min, at most once a minute (`core/build.js:19-20, 55-59`) |
| Reload | button `[data-v2-build-reload]` | "Reload" | `location.reload()` (`core/build.js:49`) | Never automatic (`core/build.js:1-9`) |
| Later | button `[data-v2-build-later]` | "Later" | Removes the bar (`core/build.js:51`) | |
| Moved-to-classic bar | same element | "Optic has moved this page back to the classic app. Your lists, settings and Milo history are there too." | | When `/api/build` says `ui === 'classic'` and the path is not under `/v2` (`core/build.js:25`) |
| Open the classic app | button `[data-v2-build-classic]` | "Open the classic app" | `location.href = CLASSIC + hash` (`core/build.js:50`) | |
| Closed bar | same | "The new design is switched off for now. Everything you saved is in the classic app, which opens on this page." | | No Later; next navigation redirects (`app.js:137`) |
| Offline bar | `div#offline-bar[role=status]` | "You are offline. What is on screen stays; new figures load when you are back." | None | Shown only while `navigator.onLine === false` and the server has not answered in 30 s (`core/status.js:40-47`) |
| Toast | `div.toast` | any message; optional action button (Undo etc.) | Action runs and the toast hides (`ui/toast.js:15-16`) | One at a time; 5 s, 10 s with an action |
| Live region | `p.sr[role=status][aria-live=polite]` | route titles, drawer opened, Milo states | None | `core/dom.js:78-88` |
| Page line | `div.page-line` | none | None | Thin bar under the top bar while a section loads (`app.js:121-124`) |
| Milo-off description | hidden `p#milo-off-desc` | "Milo is switched off right now. The button opens Milo, which says why; everything else in Optic works without it." | Describes every `[data-v2-milo]` button when Milo is off (`ui/milo.js:346-357`) | |

- States: build check fails silently when offline (`core/build.js:27`); toasts have no history.
- API dependencies: `GET /api/build` via raw `fetch` with `cache: 'no-store'` (`core/build.js:22`); `optic:v2-closed` event from `X-Optic-V2: closed` on any API answer (`core/api.js:62`, `app/main.py:8272-8290`).
- Preferences and storage keys: none.
- Risks seen in code:
  - R19 (P2, e): a toast disappears after 5 s with no way back to it (`ui/toast.js:21`), including the error toast the Watch button builds from `explain(e, 'The change')` (`ui/company.js:53`); the live region is the only persistent record.
  - R20 (P2, c): the offline notice and `api.explain` both phrase offline separately (`core/status.js:45` vs `core/api.js:129`).

### A10 App-wide click and key delegation — `global`
- Files: `app.js:229-315`.
- Purpose: one document-level listener set that serves every `data-v2-*` control no matter which page drew it.
- Controls (delegated selectors): 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| `[data-v2-report-open]` | button | "Report a problem" | `openReport` (`app.js:235`) | Footer |
| `[data-v2-rail-collapse]` | button | "Collapse" | rail fold (`app.js:236`) | A3 |
| `[data-v2-use-classic]` | link | "Use the classic app" | cookie + redirect (`app.js:237`) | A7 |
| `[data-v2-legal-more]` | button | "Full disclaimer" | toggle (`app.js:238`) | A7 |
| `[data-v2-shortcuts]` | button | "Show the shortcuts" (Settings) | `openShortcuts` (`app.js:239`) | |
| `[data-v2-copy]`, `[data-v2-copy-price]` | menu items on the Dossier "⋯" menu | ticker or price text | `copyFrom`: copies `SYM` or `SYM price change, when` from `.dhead .dh-price`, closes the menu, toast "Copied: …" or "No price for SYM on screen yet." (`app.js:215-227, 240`) | Copies only what the page shows |
| `[data-v2-open-palette]` | buttons | the top-bar Search button, the onboarding cards' Search buttons, Not found "Search" | palette (`app.js:241`) | The rail and phone-bar fallbacks carrying it are never drawn (A3 R9) |
| `[data-v2-milo]` | Ask Milo buttons on pages | button label; `data-v2-milo` is the drafted question | `openMilo` with `about`, `symbol`, `figures: panelFigures(b)` (`app.js:242-246`) | Drafts only; `panelFigures` reads the visible figures of the enclosing panel (`ui/milo.js:66-79`) |
| `[data-v2-watch]` | Watch buttons | "Watch" / "Watching" | `toggleWatch(sym)` (`app.js:247`; `ui/company.js:40-55`) | Writes the list; toast with Undo |
| `[data-v2-homelink]` | "Show on Home" | | `linkHome(sym)`; toast "Home's linked panels now follow SYM." (`app.js:248-253`; `core/homelink.js:7-15`) | Writes `optic.v2.workspace.v1` when Home is not open |
| `[data-v2-account]` | top-bar chip | | Account sheet | A4, A6 |
| `[data-v2-more]` | phone bar | | More sheet | A5 |
| `[data-v2-signout]` | button | "Sign out" | `store.signOut` + `settleAuth` (`app.js:256`) | |
| `[data-v2-guest]` | buttons | bring / keep | `app.js:257-279` | A6 |
| `[data-v2-retry]` | "Try again" buttons from `ui/states.js:failed` | "Try again" | `page.retry[name]` or re-`show` (`app.js:280-283`) | Works, unlike A2 R4 |
| `details.menu[open]` | any ⋯ or Indicators menu | | Closes on an outside click (`app.js:286-288`) and on Escape, focus back to its summary (`app.js:289-293`) | |
| `Ctrl or Cmd + K` | key | | Toggles the palette; seeds it from a focused `input[type=search]` or `input[type=text]` that is not the palette (`app.js:302`) | Works while typing |
| `/` | key | | Opens the palette when not typing and no drawer is open (`app.js:303`) | |
| `?` | key | | Opens the shortcuts sheet when not typing, no drawer and no palette (`app.js:304`) | |

- Also started here and drawn on every page: sideways-strip edge arrows (`ui/strips.js:1-23, 102-115`, `button.strip-edge` titles "Scroll back" and "Scroll on", `tabindex=-1`, `aria-hidden`), glossary marks with an "Explain this with Milo" button (`ui/glossmark.js`, `ui/term.js:126`, drafts into Milo), table alignment (`ui/align.js`), the unread poll (`core/unread.js`).
- States: none of its own.
- API dependencies: only through the controls it routes.
- Preferences and storage keys: see A30 for `optic.watchlists.v1`, `optic.v2.workspace.v1`.
- Risks seen in code:
  - R21 (P2, c): the `lists` subscriber rewrites `textContent` of every `.btn[data-v2-watch]` to "Watching" or "Watch" (`app.js:309-312`), which erases any icon or longer label a page gave that button.
  - R22 (P2, b): `adoptKeyed` posts the browser's theses and scenarios and swallows every failure (`app.js:355-361`), so a failed import is silent and the sheet has already closed (`app.js:258`).

### A11 Scroll memory — `global`
- Files: `core/scrollmem.js`.
- Purpose: Back, forward and refresh return the reader to where they were; each history entry gets `history.state.v2k` and its scroll position kept in `sessionStorage` (80 entries) (`core/scrollmem.js:7-26`); `scroll-restoration` set to manual (29-30); restored once the page is tall enough, cancelled by wheel, touch, key or pointer (38-55).
- Controls: none. States: none. API: none. Storage: `sessionStorage['optic.v2.scroll.v1']` (read 10, write 25). Risks: none seen; `pushState` for the palette copies `v2k` into the palette's history entry (`ui/palette.js:326`), so the two entries share one scroll slot, harmless.


---

# Part 2. Search

### A12 Search palette — `global` (Ctrl or Cmd+K, "/", the top-bar button)
- Files: `ui/palette.js`, `ui/symbols.js`, `nav.js`, `core/store.js`, `core/device.js`, `core/router.js`, `app.js:241, 302-303`; backend in A15.
- Purpose: one box to open a company, fund, index or page, run a named screen, or draft a question for Milo.
- Auth: guest and account. Owner pages (`reports`, `usage`, `accounts`, `metrics`) only when `me.admin`; Brokerage only when its flag is on (`allowed`, `ui/palette.js:84`). Saved-research rows come from `GET /api/saved-research` for a signed-in reader, from `optic.research.v1` for a guest when this browser holds the guest's things (`ui/palette.js:112-115`).
- Sections in render order (`ui/palette.js:236-247, 287-304`): input row (search glass, input, Clear, divider, Close); filter chips (only when the results hold symbol rows); results list `role=listbox`; status note `role=status`; hint row ("↑ ↓ move", "↵ open", "esc close", "> pages and actions", `aria-hidden`). Result groups, empty box: Recent (up to 5), Companies (AAPL, NVDA, MSFT, SPY, 2 to 4 shown), Actions (first 3), Go to (first 4) (`ui/palette.js:141-150`). Typed query, in order: Screen rows (when it reads as a request for a list), "Go to" exact page, "Open" row for a ticker-shaped word or the top directory hit, other "Go to" pages, Actions, Ask Milo (first when it reads as a question), Symbols, then "More for SYM" (`ui/palette.js:160-232`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Open from top bar | button | "Search or ask" | `palette.open(b, {symbol})` (`app.js:241`) | |
| Open from keyboard | keys | Ctrl or Cmd+K; "/" | Toggle; "/" only when not typing and no drawer is open (`app.js:302-303`) | Cmd+K seeds from a focused search or text field (`app.js:302`) |
| Open from pages | buttons `[data-v2-open-palette]` | "Search" (Not found), "Search for a company" (Home onboarding, `pages/workspace.js:813`), "Search" in the "Look up a company" card (`pages/home.js:528`); `palette.open(f.q,{seed})` from `pages/dossierstart.js:51` | `app.js:241` | |
| Search input | `input[type=search][role=combobox]` | placeholder "Search a company, fund or ticker"; aria-label "Search a company, fund, index or page, or ask Milo a question" | `input` event: clears or shows Clear, repaints after 120 ms (`ui/palette.js:258`) | No `maxlength` |
| Clear | button `[data-pal-clear]`, hidden when empty | "Clear" | Empties the box, repaints, refocuses (`ui/palette.js:253`) | |
| Close | button `[data-pal-close]` | aria-label "Close search", title "Close" | `close()` (`ui/palette.js:252`) | |
| Scrim | div | none | `close()` (`ui/palette.js:252`) | |
| Filter chips (7) | buttons `[data-pal-filter]`, `aria-pressed` | "All", "Stocks", "Funds", "Indices", "Futures", "Crypto", "Currencies" (`ui/symbols.js:15`) | Sets `filter`, redraws; non-All keeps only symbol rows of that kind (`ui/palette.js:254-255, 279-290`) | Shown only for kinds present |
| Recent rows | option buttons | each recent symbol, "Open again" | `go(openHref(sym))` (`ui/palette.js:143`) | Up to 5 |
| Clear recent symbols | option button | "Clear recent symbols" / "Forgets them in this browser" | `store.clearRecent()` then repaint; the palette stays open (`ui/palette.js:144, 315`) | |
| Company rows | option buttons | AAPL "iPhone, Mac and services"; NVDA "Chips for AI and graphics"; MSFT "Software and cloud"; SPY "A fund that tracks the S&P 500" (`ui/palette.js:235`) | `go(openHref(sym))` (146) | Static list |
| Action rows (9) | option buttons | "Market overview" `#/macro`; "Today's read" `#/read`; "Find movers" `#/scan?id=movers`; "Find unusual volume" `#/scan?id=volume`; "Momentum leaders" `#/scan?id=momentum`; "Compare stocks" `#/compare`; "Charting" (company in context, else `#/`); "Ask Milo"; "Keyboard shortcuts" (`ui/palette.js:100-110`) | `run()` | Actions match typed words of 3+ letters (165) |
| Go to rows (28 places) | option buttons | Home, Optic's Read, Macro & sectors, Indices, Explore, Scan, Paper Desk, Analyst actions, Insiders, Problem Reports (owner), Claude usage (owner), Accounts (owner), Metrics (owner), Watchlist, Alerts, Compare, Saved research (`#/research`), Dossier: Overview, Chart, Options, Investing, Earnings, Financials, News, Optic Portfolio, Retirement, Settings, Brokerage (flag) (`ui/palette.js:23-52`) | `go(placeHref(p))` (86) | Match on label or search words |
| Open row | option button | the symbol, its name and kind word, key mark "enter" when it is the Enter target | `go(openHref(sym, kind))`: instruments (index, rate, fx, commodity, future, crypto) go to `#/instrument/SYM`, others to `#/SYM` (`ui/palette.js:57-59, 121`) | |
| Per-symbol rows | option buttons | Chart, Options, Earnings (not for funds), News, Investing, Compare, each saved question (up to 3, "Saved research"); for an index or future that has a fund, "Options on SPY/QQQ/IWM/DIA" | Each `go(hrefFor(view, sym))` or `go('#/compare?t=SYM')`; saved question drafts into Milo (`ui/palette.js:123-133`) | Grouped under "More for SYM" after the symbol list (214-220) |
| Symbols rows | option buttons | logo or initial, symbol, name (typed letters marked), kind | `go(openHref(symbol, kind))` (211) | Up to 12 from the directory |
| Screen rows | option buttons | named screen, its "looks for" text, optional caveat "Does not filter by <sector>…", "Sector board" | `go('#/scan?id=…')`, `go('#/macro')` (`ui/palette.js:222-230`) | Shown when the text reads as "find/show/list… stocks/names" (65-66) |
| Ask Milo row | option button | the typed text; "With SYM and this page in context" or "Milo answers with this page in context" | `openMilo({question: q, opener})`: drafts only (`ui/palette.js:173`) | First when it reads as a question; Enter-marked then |
| Keyboard | keys in the input | ArrowDown/ArrowUp (wrap), Home, End, Enter, Escape | Move selection (`ui/palette.js:259-262, 305-312`); Enter waits for the answer to the exact text, then chooses (263-268); Escape closes (`trapFocus`, 329) | IME composition ignored (260) |

- Inputs and search fields: the one input above. Debounce 120 ms (`ui/palette.js:258`). Request identity: a module counter `seq` increments on every repaint (273) and is checked after the directory fetch (183) and after the screens catalogue fetch (224); stale answers are dropped. **No cancellation**: `api.get` takes no abort signal (`core/api.js:89-107`), so a superseded request runs to completion and is cached. Rows from the typed text alone are drawn at once ("early", 174-175) before the network answers. Empty box: Recent, Companies, Actions, Go to (141-150). `>` first: pages and actions only, no company search, no Milo row, notice `No page or action matches "<text>".` (152-159). Over 40 characters, or a question of more than three words: the directory is not asked (178) and an Ask Milo row is offered (173-174). No match: "Nothing matches. Try a ticker such as AAPL, or ask a question." (301) plus a notice `No company, fund or index matches "<text>".` (209). Search down: "Company search is not answering right now. Typed symbols still open, and pages and Milo work as usual." (208); the typed symbol row says "Search is unavailable; opens as typed" (204). Ticker-shaped text with no listing: "No listing found; opens as typed" or "Not a listed symbol; opens as typed" (204), so any typed word can be opened.
- Where a chosen result goes: `choose()` closes the palette silently, then runs the row (`ui/palette.js:313-319`); `go(href)` replaces the palette's own history entry so Back returns to where the search began (`ui/palette.js:87-99`): `location.replace(path + search + href)`, or `history.back()` when the target is the current address, else `router.go(href)`. Ask Milo and saved-question rows open Milo with the text drafted and nothing sent (`ui/palette.js:108, 133, 173`).
- Charts, tables, AI sections, tooltips, modals: the palette is a modal dialog (`role=dialog aria-modal=true`, `ui/palette.js:240`). It calls no model. A "Find stocks" phrase only opens Scan; Scan's own paid fallback is on that page.
- States: loading: early rows then final rows, no spinner; error: the two notices above; empty: the "Nothing matches" line.
- API dependencies: `GET /api/search?q=&limit=12` (ttl 5 min, 8 s, `ui/palette.js:181`), `GET /api/scanners` (ttl 10 min, only for list-shaped text, 223), `GET /api/saved-research?limit=200` (ttl 1 min, signed in, on first open, 337), `GET /api/logo/{symbol}` per symbol row (`ui/symbols.js:32`).
- Preferences and storage keys: reads and clears `optic.recent.v1` through `core/store.js` (`recent`, `clearRecent`); reads `optic.research.v1` for a guest (`ui/palette.js:113`); history entry `{v2palette:1}` (326).
- Risks seen in code:
  - R-PAL-1 (P2, c): symbol pages (Dossier: Overview, Chart, Options, Investing, Earnings, Financials, News) fall back to the first symbol in the persisted Recent list when no company is open (`symFor`, `ui/palette.js:85`), the behaviour the owner removed from the Dossier link because that list "outlives the visit" (`core/store.js:78-82`); with no Recent at all the same rows go to `#/` (86), not the Dossier start page `#/dossier`.
  - R-PAL-2 (P2, c): no row reaches the week's earnings (`#/earnings`), `#/dossier` or the instrument pages; the "Earnings" place needs a company (`ui/palette.js:45`).
  - R-PAL-3 (P2, e): Enter on an empty box opens the first row, the most recent symbol or AAPL, because no row carries the Enter mark and `sel` defaults to 0 (`ui/palette.js:295, 263-268`).
  - R-PAL-4 (P2, e): `aria-expanded="true"` is fixed on the combobox even when the list is empty (`ui/palette.js:241`).
  - R-PAL-5 (P2, e): `forgetResearch()` is exported (`ui/palette.js:351`) and never called (no other file references it), and the saved-research list is fetched once per page life (336-338), so a question saved from Milo does not show under "More for SYM" until reload.
  - R-PAL-6 (P2, b): a `{available:false}` directory answer is cached for 5 minutes (`ui/palette.js:181` with `core/api.js:103`), so "Company search is not answering" can outlast the outage for that text.
  - R-PAL-7 (P2, c): Home and Dossier start resolve a typed name with their own code that is not instrument-aware (see A14), so the same text opens different pages from the palette and from those boxes.
  - R-PAL-8 (P2, g): a list-shaped phrase calls `GET /api/scanners`, which can start the server's whole-universe ranking build when none exists or it is stale (`app/main.py:6442-6456, 5164-5187`), from an anonymous request.

### A13 Ticker typeahead and result rows — `global` (any box marked `data-v2-ta`)
- Files: `ui/typeahead.js`, `ui/symbols.js`, `app.js:338`.
- Purpose: suggestions under symbol boxes: logo, symbol, name, kind of listing, typed letters marked, corners squared, no outside logo services.
- Auth: none.
- Sections in render order: `ul.ta-list[role=listbox][aria-label="Suggestions"]` appended to the box's host (`[data-v2-ta-host]`, else the label's parent) (`ui/typeahead.js:40-46`); each row `li[role=option]` holds a logo span (image from `/api/logo/SYM`, or the symbol's first character), `.sym-sym`, `.sym-name`, `.sym-kind` (`ui/symbols.js:35-38`). Kind words: stock, fund etf, index, crypto, futures, currency, rate (`ui/symbols.js:12`).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Suggestion row | `li[data-ta-i]` | symbol, name, kind | Pick on `mousedown` (focus stays in the box) → `choose(i)`: writes `pick.symbol` into the box, closes the list, fires `v2:ta-pick` (bubbles), and for `data-v2-ta="submit"` calls `form.requestSubmit()` (`ui/typeahead.js:55-62, 88-92`) | |
| Arrow keys | keys | none | ArrowDown/ArrowUp cycle the highlight (`ui/typeahead.js:80-81`) | |
| Enter | key | none | Picks the highlighted row, else `typedNamePick` (only a name typed in full, never a symbol or text with `^ = . -`), else the form takes the typed text (`ui/typeahead.js:18-26, 83-86`) | |
| Escape | key | none | Closes the list only (`stopPropagation`) (`ui/typeahead.js:82`) | |
| Blur | event | none | Closes after 120 ms unless focus came back (`ui/typeahead.js:93`) | |

- Inputs and search fields: boxes that opt in (marked `data-v2-ta`): Home welcome-card search (`pages/home.js:470`), Dossier start (`pages/dossierstart.js:36`), Home linked-panel box (`pages/workspace.js:745`), Compare tickers 2 to 4 (`pages/compare.js:154`), Alerts symbol (`pages/alerts.js:289`), Watchlist add (`pages/watchlist.js:223`), Analysts (`pages/analysts.js:45`), Chart watch widget add (`pages/chart-widgets.js:160`) and pair box (`pages/chart-widgets.js:370`). Debounce 160 ms (`DEBOUNCE_MS`, `ui/typeahead.js:14, 75`). Request identity: counter `S.seq`, plus the same box still active, the same text, and focus still in it (`ui/typeahead.js:68-73`); no abort. Empty text closes the list (67). `limit=10`, ttl 60 s, 8 s timeout (71). Failure closes the list silently (74). Text over 40 characters is not guarded and the server answers 422, which also closes silently.
- Where a chosen result goes: nowhere by itself; the page's handler decides (Compare fills the next empty box, `pages/compare.js:274-279`; Analysts reloads, `pages/analysts.js:75`; submit-mode boxes run their form).
- Charts, tables, AI sections: none. Tooltips: none.
- States: loading: none (the list appears when it answers); error: none shown; empty: no list.
- API dependencies: `GET /api/search?q=&limit=10` (`ui/typeahead.js:71`); `GET /api/logo/{symbol}` per row (`ui/symbols.js:32`), skipped for a symbol whose logo already failed this visit (`NO_LOGO`, 19, 41-47).
- Preferences and storage keys: none.
- Risks seen in code:
  - R-TA-1 (P2, c): symbol boxes that do not opt in: Chart compare (`pages/chart.js:298`), Insiders symbol (`pages/insiders.js:123`), Paper ticket symbol (`pages/paper.js:152`).
  - R-TA-2 (P2, c): boxes with suggestions cap input at 12 characters (Alerts, Watchlist, Home link, Chart widgets) so a company name longer than 12 cannot be typed, while Compare and Analysts allow 24.
  - R-TA-3 (P2, c): `typedNamePick` takes the first row whose name merely contains the text (`ui/typeahead.js:25`); the palette requires a word-start match before it promotes a name (`ui/palette.js:63, 189`).

### A14 Every other search or symbol box in v2 — `global` (inventory)
- Files: see the table. Purpose: the full list of text boxes a reader can type a company or phrase into, so each page's registry entry can point here.
- Auth: guest unless noted. Controls (one per box; "Suggestions" says whether it opts in to A13): 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Home welcome-card search (new readers) | `input[name=q]` + "Open" in `form[role=search][data-v2-search-form]` | placeholder "Try AAPL or Nvidia"; Suggestions yes | Submit: if the text is ticker-shaped it is used upper-cased; it asks `/api/search?q&limit=5` and an exact symbol wins, else the first result; then `location.hash = '#/SYM'` (`pages/home.js:469-470, 668-681`) | Not kind-aware (an index opens a Dossier, R-A14-1); nothing happens if no result and the text is not ticker-shaped; no check after the await that the reader is still on Home |
| Dossier start search | `input[name=q]` + "Open" | placeholder "Search a company, fund or ticker"; Suggestions yes | Submit: exact listed symbol opens `#/SYM`; otherwise the palette opens seeded with the text; a failed search with ticker-shaped text opens it as typed (`pages/dossierstart.js:41-52`) | Same late-navigation and index issues |
| Home linked-panel box | `input#ws-link name=link` + "Update panels" | label "Company or fund shown in linked panels"; `maxlength 12`; Suggestions yes | `setLink(value)` (`pages/workspace.js:745, 1110`) | |
| Compare tickers | `input[data-v2-cmp-input]` ×2 to 4 | placeholder "Ticker N"; `maxlength 24`; Suggestions yes | `v2:ta-pick` fills and moves to the next empty box (`pages/compare.js:154, 274-279`) | |
| Alerts symbol | `input[name=symbol]` | placeholder "Symbol, such as AAPL"; `maxlength 12`, required; readonly when editing; Suggestions yes (submit) | Alert form submit (`pages/alerts.js:289, 479`) | |
| Watchlist add | `input[name=sym]` | placeholder "Add a ticker, such as MSFT"; `maxlength 12`; Suggestions yes (submit) | Add form (`pages/watchlist.js:223`) | |
| Watchlist find | `input[type=search][data-v2-wl-q]` | placeholder "Find in this list" | Client-side filter, repaints rows (`pages/watchlist.js:199, 379`) | No request |
| Analysts search | `input[name=t]` + "Search" | placeholder "Symbol, such as NVDA"; `maxlength 24`; Suggestions yes | `Q.ticker = value; load()` (`pages/analysts.js:45, 75-76`) | |
| Insiders member | `input[name=m]` + "Filter" | placeholder "Member's name"; `maxlength 80` | Insiders filter form (`pages/insiders.js:56`) | |
| Insiders symbol | `input[name=t]` + "Show filings" | placeholder "NVDA, or blank for everything"; `maxlength 10` | `Q.ticker = …; loadAll()` (`pages/insiders.js:123, 165`) | No suggestions |
| Chart compare symbol | `input[name=s]` + "Add" | placeholder "Add a symbol, such as SPY"; `maxlength 12` | Chart compare form (`pages/chart.js:298, 810`) | No suggestions |
| Chart indicator finder | `input[type=search][data-v2-ch-find]` | placeholder "Find an indicator" | Filters the Indicators menu (`pages/chart.js:373, 798`) | |
| Chart watch widget | `input[name=s]` + "Add" | placeholder "Add ticker"; `maxlength 12`; Suggestions yes (submit) | `pages/chart-widgets.js:160, 748` | |
| Chart pair box | `input[name=b]` + "Test" | placeholder "Symbol"; `maxlength 12`; Suggestions yes (submit) | `setPeer` (`pages/chart-widgets.js:370, 754`) | |
| Read headline search | `input[name=q]` in `form[role=search]` | placeholder "Search the headlines" | `runSearch` → `GET /api/brief/search?q=&limit=40`, ttl 60 s, counter `sseq` drops stale answers, Escape clears (`pages/read.js:88, 329-336, 363-371`) | |
| Read catalyst search | `input[name=q]` + button | placeholder "Search catalysts" | `cat.q = …; loadCats()` (`pages/read.js:144, 336`) | |
| Macro currency find | `input[name=q]` | placeholder "Find a currency, such as yen" | `GET /api/forex?q=` (`pages/macro.js:174, 290`) | `q` max 40 on the server (`app/main.py:5631`) |

- Risks seen in code:
  - R-A14-1 (P2, c): Home (`pages/home.js:668-681`) and Dossier start (`pages/dossierstart.js:49-50`) send every result to `#/SYM`, while the palette sends an index, rate, currency, future or crypto to `#/instrument/SYM` (`ui/palette.js:57-59`); typing "VIX" or choosing `^GSPC` in those boxes opens a company Dossier for an index.
  - R-A14-2 (P2, b): both handlers set `location.hash` after an awaited search with no check that the reader is still on that page (`pages/home.js:668-681`, `pages/dossierstart.js:44-51`); a slow answer yanks the reader to the Dossier they typed.
  - R-A14-3 (P2, e): Home's box does nothing, silently, when the text is not ticker-shaped and the directory returns nothing (`pages/home.js:668-681`); Dossier start falls through to the palette (`pages/dossierstart.js:51`).

### A15 Search backend — `GET /api/search`, `GET /api/logo/{symbol}`, `GET /api/scanners`
- Files: `app/main.py:1806-1884, 6442-6456`, `app/universe.py:171-500`.
- Purpose: the directory the palette and typeahead read; the logos in result rows; the list of named screens.
- Auth: none for all three; no rate limit on any of them; no model call (no Anthropic spend).
- `GET /api/search?q=&limit=`: `q` at most 40 characters (longer is a 422), `limit` 1 to 25, default 10 (`app/main.py:1875-1884`). Answer `{query, results:[{symbol, name, etf, kind, match, dollar_volume}], available, stale, reason?}` (`app/universe.py:405-413, 450-495`). `available:false` when the directory could not be read, `stale:true` when yesterday's copy stood in (`app/universe.py:405-413`). Source: NASDAQ's two public symbol files, cached per market day in `data/symbols.json` (`app/universe.py:182-276`); instruments, rates, currencies, commodities, futures and crypto from `macro.INSTRUMENTS` and `longterm.INDEX_META` with typed aliases such as "spx", "10 year", "dollar" (`app/universe.py:314-364`). Ranking: exact symbol, alias, symbol prefix, name prefix, a word of the name, contains; shells and leveraged products drop two tiers, funds one; ties by dollar volume then shorter symbol (`app/universe.py:416-500`); a dotted class (BRK.B) comes back dashed (487).
- `GET /api/logo/{symbol}`: symbol must match `^[A-Z][A-Z0-9.\-]{0,9}$` else 404 (`app/main.py:1816, 1863`); Optic's server fetches Parqet then Financial Modeling Prep (1813, 1820-1832), keeps a hit 14 days and a miss 2 days on disk (1815, 1835-1857), serves with `nosniff` and a sandboxing CSP (1869-1872); only 4 fetches at once (1817).
- `GET /api/scanners`: named scans and whether a ranking exists; calling it can start the ranking build (`app/main.py:6442-6456, 5164-5187`).
- States: failure shapes are in A12 and A13. API dependencies: the universe files at nasdaqtrader.com (server side only).
- Preferences and storage keys: none.
- Risks seen in code:
  - R-S-1 (P2, g): `/api/logo/{symbol}` accepts any symbol-shaped string, not only listed ones, so each new string costs up to two outbound fetches and writes a `.none` marker file on disk with no rate limit (`app/main.py:1835-1872`); an anonymous caller can fill the logo folder and tie up the four fetch slots.
  - R-S-2 (P2, g): `search()` re-reads and parses `screen_ranking.json` on every request (`app/universe.py:291-306, 435`), and each keystroke from every client reaches it unmetered (`app/main.py:1875-1884`).
  - R-S-3 (P2, f): results carry `stale` and `reason` but the palette ignores both (`ui/palette.js:181-182`); a reader is never told the directory is a day old.


---

# Part 3. Milo

### A16 Milo panel — `global` (top-bar "Ask Milo", every `[data-v2-milo]` button, the palette, Saved research, glossary pops)
- Files: `ui/milo.js` (1,335 lines), `core/milo-text.js`, `core/research.js`, `core/legal.js:42`, `ui/finfigs.js`, `ui/chart.js`, `ui/drawer.js` (`makeDrawer`, second instance with `cls drawer-milo`, `ui/milo.js:996`), `components/scout.js`, `core/prefs.js:109-124`, `core/store.js`, `core/device.js`, `app.js:242-246`. Server in A19 and A20.
- Purpose: a side panel conversation with the research assistant about the page open, the market, or nothing, with answers streamed from the server and conversations kept in this browser.
- Auth: asking needs an account unless the server's guest allowance is above zero (default 0, `app/main.py:7375`): a guest sees a sign-in card and no composer (`ui/milo.js:360-368, 677-683, 736`). Signed in: Free 3 questions a day; Pro 15 a day and 100 in any 30 days (`app/auth/store.py:661-666`); the verified owner is unmetered (`app/main.py:7411-7416, 7468-7487`). Switched off when the server has no key (`ai.enabled === false`, `ui/milo.js:364`). Reading the panel, history and settings never needs an account.
- Sections in render order (`openMilo`, `ui/milo.js:1058-1097`): (1) header: compact Scout, "Milo", "Research assistant", History, New conversation, Close, width grip; (2) `.milo-chrome`: access card (sign-in, off or used up), context bar (what Milo receives, attached parts, the "Not financial advice." line with an info button, Response settings), a moved-company note, the Optic Persona menu (`ui/milo.js:684-687`); (3) `.milo-log[role=log][aria-live=polite]`: the opening (Scout greeting, "What would you like to understand?", a one-line prompt, three starters), or the conversation, or the history list; a "Latest" button; (4) `form.milo-form`: suggestion slot, tools row, attached files, composer, foot (what is attached, allowance line).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| History | icon button `[data-v2-milo-history]`, `aria-expanded` | aria-label "Conversation history" | `toggleHistory()` shows or hides the saved list in place of the log (`ui/milo.js:1157-1162, 1172, 1264`) | Composer and draft stay |
| New conversation | icon button `[data-v2-milo-new]` | aria-label "New conversation" | `newConversation()` blanks conversation, items and per-answer data (`ui/milo.js:1163-1169, 1173`) | Disabled while an answer streams, title says "stop the answer first" (698); does not clear an open report (R-M5) |
| Close | icon button `[data-v2-close]` | "Close" | Drawer `close()` (`ui/drawer.js:49-51`); the `closed` callback keeps the draft, turns Search the web off, unlays the dock (`ui/milo.js:1096`) | Escape does the same (`ui/drawer.js:59, 63`); an answer still streaming keeps streaming |
| Width grip | `div.milo-grip[role=separator]`, focusable | aria-label "Milo's width. Drag, or use the arrow keys; double-click for the default." | Pointer drag; Left/Right ±24 px (Shift ±96), Home = 320, End = widest; double-click resets (`ui/milo.js:1111-1154`) | Writes `optic.chat.width.v2` only when chosen (1123) |
| Sign in or create an account | link `a.btn` | "Sign in or create an account" | `#/signin` (`ui/milo.js:680`) | Guests when an account is required; copy lists what works without one (681) |
| Context menu | `details.menu.milo-ctx-pick` summary | "What Milo receives: <current>" (e.g. "NVDA / Chart", "Market only", "No page context") | Opens the three options (`ui/milo.js:660`) | |
| Option: This page | button `[data-v2-milo-scope="auto"]`, `aria-pressed` | "This page: <label>" / "The figures on the page you have open." | `S.scope='auto'` (`ui/milo.js:1252-1257`) | |
| Option: Market only | `[data-v2-milo-scope="market"]` | "Market only" / "The market's state: indices, sectors and the macro read. No company." | `S.scope='market'` | Sends focus plus macro, sectors, indices, read (125) |
| Option: No page context | `[data-v2-milo-scope="none"]` | "No page context" / "Your question and this conversation only." | `S.scope='none'` | Sends focus only (124) |
| What is attached | `details.milo-parts` summary | "What is attached: N parts, SYM, 1D bars, range" or "This page sends no figures of its own: only which page it is" | Lists each part of the page context by name (`ui/milo.js:533-544`) | Read from the same `buildContext` that Send uses |
| Remove (part) | text button `[data-v2-milo-drop]` | "Remove" (aria-label "Remove <part> from what Milo receives") | Adds the part to `S.dropped` (`ui/milo.js:1301-1306`) | Stays out until the page changes (`resetContext` clears, 84) |
| Put back (part) | text button `[data-v2-milo-undrop]` | "Put back" | Removes it from `S.dropped` | |
| About Milo's data | icon button `[data-v2-milo-info]`, `aria-expanded` | aria-label "About Milo's data and its limits" | Toggles `.milo-info` (freshness sentence, "Milo reads Optic's own figures…", allowance line) (`ui/milo.js:663, 666, 1251`) | |
| Not financial advice fold | `details.legal-milo` summary | "Not financial advice. What Milo's reading is, and is not" | Opens the paragraph from `LEGAL.areas.pulse` (`core/legal.js:22, 42`) | Inside the info block only |
| Response settings | button `[data-v2-milo-settings]`, `aria-expanded` | "Response settings" (title "Response settings: Level and Timeframe") | `setSettings(!open)` (`ui/milo.js:1176-1181, 1249`) | Opens a non-modal dialog (`role=dialog aria-modal=false`, 510) |
| Settings scrim | div `[data-v2-milo-settings-done]` | none | Closes the dialog (`ui/milo.js:509, 1250`) | A click elsewhere in the panel also closes it (1240) |
| Close Response settings | icon button `[data-v2-milo-settings-done]` | aria-label "Close Response settings" | Closes and returns focus to Response settings (`ui/milo.js:511, 1250`) | |
| Level | `select[data-v2-milo-mode]` | "Level": Simple, Financially Literate, Advanced, Professional, Adaptive (from `/api/knowledge/modes`) with each one's blurb beneath | `prefs.setKnowledge(value)`; repaints (`ui/milo.js:512-513, 1234-1237`) | Writes `optic.knowledge.v1` and `optic.knowledge.asked.v1` (`core/prefs.js:113-116`); hidden if the catalogue fails to load (505) |
| Timeframe (4) | segmented buttons `[data-v2-milo-hz]`, `aria-pressed` | "Auto", "Day", "Swing", "Long term" (ids `auto`, `day`, `swing`, `long`; `title` is the server blurb) | `setPref('optic.milo.horizon.v1', id)` (`ui/milo.js:514-516, 1259`) | Sent as `horizon` with the next question |
| What a persona changes | `details.more-inline.milo-pp-foot` summary | "What a persona changes" with "Changes" and "Never changes" lists | Opens static lists from `/api/personas` (`ui/milo.js:517`) | |
| Start a new conversation | text button `[data-v2-milo-new]` | "Start a new conversation" | `newConversation()` (`ui/milo.js:672, 1265`) | Shown when the page's company differs from the conversation's (669-673) |
| Persona menu | `details.menu.milo-pp-pick` summary | "Optic Persona: <name>" | Opens the five options (`ui/milo.js:500`) | |
| Persona options (5) | radio buttons `[data-v2-milo-pp]` in a `radiogroup` | "Neutral analyst", "Long-term investor", "Risk and process", "Statistician", "Devil's advocate", each with a blurb | `pickPersona(id)` writes `optic.pulse.persona.v1`; arrows, Home and End move the choice (`ui/milo.js:495-502, 1208-1215, 1258, 1326-1334`) | Announces "<name>. Applies from your next question." |
| Scout guide | button `.scout-btn`, `aria-haspopup=menu` | aria-label "Milo guide: what to ask, examples and animation" (the figure) | `scoutPress`: a wave or tilt and the menu (`ui/milo.js:245-249, 1241`) | |
| Guide: What can I ask? | menu item `[data-v2-scout-act=ask]` | "What can I ask?" / "Hide what I can ask" | Toggles the sentence `CAN_ASK` (`ui/milo.js:193, 251-259, 264`) | |
| Guide: example questions | menu item `[data-v2-scout-act=examples]` | "Show example questions" / "Hide example questions" | Toggles the 12-question list (6 need a company) (`ui/milo.js:195-209, 265`) | Each example only drafts (below) |
| Guide: Animation (3) | `menuitemradio` `[data-v2-scout-motion]` | "Full", "Subtle", "Still" | `OpticScout.setMotion(v)` (`ui/milo.js:262, 1243-1247`) | Writes `optic.scout.motion.v1` (`components/scout.js:361`) |
| Starters (up to 3) | buttons `[data-v2-milo-start]` | the question, per page (`STARTERS`, `ui/milo.js:272-290`), e.g. "What matters most for NVDA right now, from the figures on this page?" | **`send(question)` at once** (`ui/milo.js:1260`) | Hidden whenever asking is blocked (316) |
| Example questions (up to 12) | buttons `[data-v2-milo-follow]` | e.g. "What is the macro regime saying right now, and which sectors is it favouring?" | Puts the text in the box, sends nothing (`ui/milo.js:317, 1291`) | |
| Save (question) | button `[data-v2-milo-save]` | "Save" / "Saved" | `saveQuestion` then toast with "Open Saved research" or "Create a free account" (`ui/milo.js:391, 1275-1284`) | Shown for questions over 12 characters |
| Follow-up questions (≤4) | buttons `[data-v2-milo-follow]` in `role=group` | the lines the model ended with "→" | Draft into the box (`core/milo-text.js:70-81`; `ui/milo.js:404, 1291`) | |
| Source chips | links `a.milo-src` / button `[data-v2-milo-srclist]` | label such as "Quote", "Dealer gamma", "Sources Milo read" | Link to the page the source lives on for the answer's company, or open the Sources fold (`core/milo-text.js:84-96`; `ui/milo.js:1314`) | 51 source keys (`core/milo-text.js:19-36`); unknown keys vanish |
| Sources fold | `details.milo-src-all` summary | "Sources (n)": Cited, "Sources Milo read", "Data Milo retrieved", "Loaded because the question named them" | Lists links (`target=_blank rel=noopener`, https only) and observed or retrieved times (`ui/milo.js:469-478`) | |
| Copy | button `[data-v2-milo-copy]` | "Copy" → "Copied" / "Copy failed" | `navigator.clipboard.writeText` of the answer with source chips as plain words, minus follow-ups (`ui/milo.js:1308-1313`) | |
| Ask again | button `[data-v2-milo-again]` | "Ask again" (title "Put the question back in the box") | Drafts the question (`ui/milo.js:1292`) | Only when the answer has its question |
| Report a problem | button `[data-v2-milo-report]`, `aria-expanded` | "Report a problem" (title "Tell Optic this answer has a wrong figure or a mistake") | Opens an inline form under the answer (`ui/milo.js:1293-1299`) | |
| Report text | `textarea` `maxlength=600` | label "What is wrong with this answer?"; placeholder "For example: the P/E it gives is not the one on the Overview" | Draft kept as the log redraws (`ui/milo.js:411-419, 1197`) | Empty → "Say what is wrong first, in a few words." (1190) |
| Send report | submit | "Send report" / "Sending..." | `POST /api/feedback` with the text, the question (300 chars) and the answer (to about 2,000 chars in all) and page "Milo, <context>" (`ui/milo.js:420-429, 1186-1192`) | Success "Report sent. It goes to the people who run Optic, with this question and answer attached." (413) |
| Cancel report | button `[data-v2-milo-report-cancel]` | "Cancel" | Closes the form (`ui/milo.js:1300`) | |
| Action card: Go / Confirm | button `[data-v2-milo-act-go]` | "Go" (navigates) or "Confirm" (writes) | `runAction(a, card, i)` (`ui/milo.js:953-991, 1318-1322`) | See A17 for the nine kinds |
| Action card: Not now | button `[data-v2-milo-act-skip]` | "Not now" | Disables the card, "Left as it was." (`ui/milo.js:1315`) | Write actions only |
| Valuation card (3) | buttons `[data-v2-milo-val-preview]`, `-apply`, `-undo` | "Show the effect", "Apply to my working model", "Undo" | `valuationPress` against the model open on Investing (`ui/milo.js:915-943, 1316`) | Changes working assumptions only, never a saved model |
| Answer links | `a[target=_blank][rel=noopener]` | the link text | Only `http(s)` links are made (`core/milo-text.js:57`) | |
| Back to the conversation | button `[data-v2-milo-history-close]` | "Back to the conversation" | `toggleHistory(false)` (`ui/milo.js:482, 1263`) | |
| Saved conversation | button `[data-v2-milo-open]` | title (first question, 70 chars), date, message count, company, "open now" | Loads it as the current conversation (`ui/milo.js:483, 1266-1273`) | Ignored while an answer streams |
| Delete conversation | icon button `[data-v2-milo-del]` | aria-label "Delete <title>", title "Delete" | Removes it from storage at once (`ui/milo.js:483, 1274`) | No confirmation or undo (R-M7) |
| Latest | button `[data-v2-milo-latest]` | "Latest" | Scrolls the log to its end, smooth unless motion is reduced (`ui/milo.js:1261`) | Appears when more than 160 px from the end (716) |
| Options follow-ups (6) | quiet buttons `[data-v2-milo-follow]` | "Why did the ranker pick that strike over a cheaper OTM one?", "What does the gamma profile imply for a swing long here?", "Is the flow confirming or fighting the chart?", "Walk me through the entry zone and what invalidates it.", "Does the short interest or insider activity change the read?", "How does the earnings record affect holding through the print?" (`ui/milo.js:556`) | Draft only | Only on the Options tab with a company, scope This page, once a conversation exists (557-562) |
| Use this example | quiet button `[data-v2-milo-follow]` | "For example: <question>" and "Use this example" | Drafts (`ui/milo.js:549-553, 562`) | Shown when the box is empty and a conversation exists |
| Modes | `details.menu.milo-modes` summary | "Modes" | Lists research modes (`ui/milo.js:613-615`) | `aria-disabled` while busy |
| Mode buttons | buttons `[data-v2-milo-mode]` + `[data-v2-milo-follow]` | by page: company: Quick read, Catalysts, Thesis check, Risk review, Deep research; chart: Read this chart, Key levels, Catalysts; Brokerage: What needs attention, Why it moved, My earnings, Exposure, Research next; Positions or Watchlist: Portfolio risk, Event risk, What needs review; Scan: Explain these results, Compare the leaders; otherwise: Market read, This week's catalysts, Deep research (`ui/milo.js:569-607`) | Writes the mode's question into the box, closes the menu, marks Deep research as the suggested next step (`ui/milo.js:1288, 1291`) | Drafts only |
| Search the web | toggle `[data-v2-milo-web]`, `aria-pressed` | "Search the web" (title "Milo also searches the web for your next questions. Each search adds to what a question costs. Off again when this panel closes.") | `S.web = !S.web`; sent as `web` (`ui/milo.js:616, 1286`) | Not remembered; disabled while busy |
| Deep research | button `[data-v2-milo-deep]` | "Deep research" (title "…Uses one Milo question and several web searches.") | **`send(box text, {deep:true})` at once** to `/api/research` (`ui/milo.js:617, 1287`) | Empty box → "Deep research: SYM" or "Deep research: the market" (808) |
| Attach | button `[data-v2-milo-attach]` | aria-label "Attach an image or PDF" (title lists PNG, JPEG, GIF, WebP, PDF, 4 files of 5 MB) | Opens the hidden file picker (`ui/milo.js:1068, 1289`) | Disabled at 4 files or while busy (632) |
| File picker | hidden `input[type=file][multiple]` | accept PNG, JPEG, GIF, WebP, PDF | `addFiles` checks type, size, count and the first bytes (`ui/milo.js:160-176, 634-651, 1228`) | A bad file is listed "Not sent: <reason>" |
| Remove file | icon button `[data-v2-milo-unattach]` | aria-label "Remove <name>" | Drops it (`ui/milo.js:626, 1290`) | |
| Question box | `textarea#milo-q` | placeholder "Ask about SYM" or "Ask Milo"; `maxlength=4000` | Enter sends, Shift+Enter a new line (`ui/milo.js:1198`) | Auto-grows (718-724); disabled when asking is blocked except "used up" (734) |
| Send | submit `[data-v2-milo-send]` | aria-label "Send" (title "Send (Enter). Shift and Enter for a new line") | `send(text)` (`ui/milo.js:1185`) | Disabled while busy or blocked; hidden while busy (729) |
| Stop | button `[data-v2-milo-stop]` | aria-label and title "Stop the answer" | `stop()` aborts the fetch, only from 600 ms after Send (`ui/milo.js:906, 1262`) | Takes Send's place and focus (731-733) |
| Drop files | drag and drop on the panel | none | `addFiles(dataTransfer.files)`; ignored when blocked (`ui/milo.js:1229-1231`) | |

- Inputs and search fields: the question box (above); the report box; the Level select. Keyboard: Enter sends (not during IME composition), Shift+Enter newline, Escape closes the open menu, then Response settings, then the panel (`ui/milo.js:1198-1206`); inside the guide menu Escape, arrows, Home, End work and Tab closes it (1217-1226); personas respond to arrows, Home, End (1208-1215); the width grip responds to arrows, Home, End (1140-1148). Empty question: `send` returns without doing anything (`ui/milo.js:809`).
- Request sent (see A19 for the server side): `POST /api/chat` with `{messages, context, web, attachments, persona, mode, horizon}`; Deep research sends `POST /api/research` with `{ticker, question, context}` only (`ui/milo.js:833-839`). `messages` is every earlier turn plus the new question. `context` is built at the press from the route then on screen (`buildContext`, `ui/milo.js:106-128`): `focus {scope, view, view_label, ticker, captured_at, asked_from?, chart?, previous_ticker?}` plus the parts the page registered (`provideContext`, 81) minus removed parts, plus `panel` (the visible figures of the block an Ask Milo button sat in, `panelFigures`, 66-79). Headers: JSON, `Accept: text/event-stream`, `X-Optic-CSRF` read from the cookie (835).
- How the stream is read and drawn (`ui/milo.js:850-871, 749-763`): `res.body.getReader()` and a `TextDecoder`; text is split on a blank line (`\n\n`), each block's `event:` and `data:` lines read, `JSON.parse`, malformed blocks skipped (CRLF framing would not split; the server writes `\n\n`, `app/ai.py:1690-1691`). Events handled: `delta` (append), `status` (line under the answer), `attachments` (files not sent), `assumed` (shown only when the timeframe came from the question and differs from the setting), `retrieved` (looked up so far), `error`, `done` (citations, read, retrieved, loaded, named). Drawing: on the next animation frame, paragraphs before the last blank line go through `renderAnswer`, the last paragraph is plain text with unfinished `[[tags]]` hidden (`core/milo-text.js:179`), so no raw tag flashes; auto-scroll only if the reader is within 120 px of the end (760); the question just sent always scrolls into view (707). There is no reconnect or resume: a dropped connection ends the answer as cut off, and blocks with no `data:` line (comments, pings) are ignored (861).
- Activity and thinking states, each tied to an event (`ui/milo.js:37-52`): submitted "Sending your question" (set at the press, 823); preparing "Preparing the answer" (response headers ok, no text yet, 842); retrieving: server `status` events mapped to "Thinking it through", "Searching the web", "Searching live sources", "Reading what it found" or the server's own words such as "Reading your linked portfolio (summary)" (51, 863); streaming (first `delta` clears the line, 862); complete (`done`); stopped; failed; cut off. A progress element `span.activity[role=progressbar]` shows while live (402), a note "No reply from the server for 30 seconds. You can keep waiting or stop the answer." after 30 s of silence (49-50, 830), and "Looked up so far: …" while tools run (757). Scout moves on the same events only (`ui/milo.js:181-190, 862-863, 887-896`).
- Conversation persistence: in memory `S.conv {id, messages, lastTicker}`, `S.items`, per-answer `meta` (context, sources, files names), `S.draft`, `S.files`, `S.scope`, `S.dropped`, `S.web`. After an answer ends, `persist()` writes the conversation to `localStorage['optic.pulse.history.v1']`: `{id, at, title, ticker, messages:[{role, content}]}`, newest first, at most 30 conversations, 60 messages, 12,000 characters each; on a quota error it keeps the newest half (`ui/milo.js:132-146`). It is a personal key: read and written only while this browser holds the signed-in person's things (`holds`, 132, 134). Sources, the "About" lines, attachments and figures are not stored; a reopened conversation rebuilds only the question and the company (1269-1271). Nothing about a conversation is kept on the server by the panel; the server sees each request's messages and context (A19). Settings live in `optic.pulse.persona.v1`, `optic.milo.horizon.v1`, `optic.knowledge.v1`, `optic.chat.width.v2`, `optic.scout.motion.v1`.
- Charts, tables, AI-generated sections: the answer is AI-generated and **spends the operator's money** on every Send (starters, follow-ups sent by hand, Deep research, "Ask again"). Inline charts `[[chart SYM span]]` are drawn from `GET /api/take-chart/{sym}?span=` (cached 10 min, `ui/milo.js:782-797`) and captioned "SYM, daily closes over <span>, through <date>. Dashed: support and resistance, where price turned before. Source: Yahoo Finance." Figures `[[figure kind SYM]]` come from Optic's own pages' endpoints (`ui/finfigs.js:32, 54, 69`) and are captioned "drawn by Optic, not by Milo" (`ui/milo.js:774`). Markdown tables are drawn by `mdLite` (A17). Tooltips: titles on the buttons above. Modals: the panel is a dialog or, when there is room (`CONTENT_MIN` 760 px beside the rail), a docked complementary panel that stays across pages (`ui/milo.js:999-1033`); Response settings is a non-modal dialog.
- States: loading: Level and Persona are drawn once their catalogues arrive (an empty `is-loading` persona box until then, 497); guest card (679-681); off "Milo is switched off right now, so it cannot answer questions. Everything else in Optic works without it." (364); used up "You have used today's N questions. The next one is available <weekday time>." (366); history empty "Nothing saved yet." (483); sending and quiet states above; stopped "Stopped by you. This answer is incomplete." and cut "The connection ended before Milo finished. This answer is incomplete." (403); failure before any text: the exchange is removed, a note with the reason is added and the question (and files) go back to the box (880-886); offline "You appear to be offline. The question is still in the box: send it again once you are back on." (801); HTTP failure "Milo did not respond (HTTP n). Wait a moment and send it again; your question is still in the box." (802) or "Milo did not answer (HTTP n)." (848); 401 "Milo needs a free account. Sign in to ask."; 429 the server's sentence or "No questions left for now." (846-847); report errors (427); attachment problems "Not sent: <reason>" (625); inline chart "No price history for SYM." (790); figure "No figure: <reason>" (773).
- API dependencies: `POST /api/chat`, `POST /api/research` (SSE, spend); `GET /api/ai-allowance` (forced on open and after every answer, `ui/milo.js:374-377, 900`); `GET /api/personas` and `GET /api/knowledge/modes` (ttl 1 h, 378-382); `GET /api/health` (ttl 1 min, 1093); `GET /api/take-chart/{sym}`; `GET /api/ticker/{s}`, `/api/segments/{s}`, `/api/earnings/{s}` for figures; `POST /api/feedback`; `POST/GET/DELETE /api/saved-research` (`core/research.js:29, 45, 61`); `POST /api/watchlists/{id}/items` and friends through `store.follow` for the "watch" action.
- Preferences and storage keys: `optic.pulse.history.v1` (r/w, personal key), `optic.pulse.persona.v1` (r/w), `optic.milo.horizon.v1` (r/w), `optic.knowledge.v1` and `optic.knowledge.asked.v1` (w, via `core/prefs.js`), `optic.chat.width.v2` and legacy `optic.chat.width.v1` (r/w, `ui/milo.js:1102-1124`), `optic.scout.motion.v1` (r/w, `components/scout.js`), `optic.research.v1` (guest saved questions, `core/research.js:10-13, 54`), `optic.chart.drawings.v2` (the "level" action writes a dashed line labelled Milo, `ui/milo.js:984-987`).
- Risks seen in code:
  - R-M1 (P1, g): a reader's linked-brokerage holdings can reach a question that is not about their portfolio. The server attaches the portfolio when the last question matches a loose pattern that includes the bare words "portfolio", "position(s)", "holding(s)", "exposure", "exposed", "concentrat…", "allocation" (`app/main.py:7784-7787`), and `get_my_portfolio` is offered to the model on every page unless the scope is Market only or No page context (`app/main.py:7776-7777`, `7738-7778`). The commit that fixes it (`2236205`, "attach or offer the linked portfolio only for questions about it", found live 2026-10-27 when a Compare question quoted the owner's MSFT weight) is **not an ancestor of this branch** (`git merge-base --is-ancestor` says no). It applies to a signed-in reader whose brokerage is linked and switched on for them (`app/main.py:7818-7830`), and then the question and the holdings go to the model provider.
  - R-M2 (P1, a): the "Risk and process" persona is described to readers as "position size before direction" (`app/ai.py:139-141`, served by `/api/personas`) and its prompt tells the model to lead with "Size, stop placement, whether the thesis is falsifiable, before discussing direction at all" (`app/ai.py:143-146`), against the base rule never to tell the reader what to do with their money (`app/ai.py:391, 943`). The deep-research default question is written "for a swing trader looking out two to eight weeks" (`app/ai.py:3630-3635`).
  - R-M3 (P2, c): the file header says "Nothing is sent until the reader presses Send. Every entry point drafts." (`ui/milo.js:13`), but a starter press sends and spends a question at once (`ui/milo.js:1260`) and Deep research does the same (1287) and is the dearest call in the app (adaptive thinking, high effort, up to 10 web searches, 12,000 tokens, `app/ai.py:3640-3652`). Only the Deep research and Search the web titles disclose cost (616-617); the starters do not.
  - R-M4 (P2, e): an `error` event after some text has arrived leaves the partial answer shown and persisted as if complete: `failed` is set but `ended` is empty, so no "incomplete" marker is added (`ui/milo.js:867, 880-897`); only a note below it carries the failure, and a reopened conversation has no note.
  - R-M5 (P2, b): the open report form and "Report sent" state are keyed by message index in a module-level `S.report` that New conversation and History-open never clear (`ui/milo.js:1163-1169, 1266-1274`); the same index in another conversation then shows another answer's draft or "Report sent", and Send attaches the new conversation's question and answer (420-423).
  - R-M6 (P2, b): `persist()` records the company of the page open when the answer **finishes** (`ui/milo.js:144`), not the page asked from (`meta.symbol`, 822), so an answer that streamed while the reader moved to another company is saved, and later labelled "About …", under the wrong company.
  - R-M7 (P2, e): deleting a saved conversation is immediate with no confirmation or undo (`ui/milo.js:1274`).
  - R-M8 (P2, e): Level, Persona and Timeframe are not sent with Deep research (`ui/milo.js:836-839`), yet the dialog says a change "applies to your next question" (518).
  - R-M9 (P2, e): the daily allowance is spent when the request arrives, before any model call (`app/main.py:7857, 7500-7505`), so an answer that fails still costs one while the panel says the question is back in the box (`ui/milo.js:880-886`). The "used up" sentence always says "today's N questions" even when the monthly cap of a paid plan ran out (366; `app/main.py:7424-7427`).
  - R-M10 (P2, c): `data-v2-milo-mode` names two different controls, the Level select (`ui/milo.js:512`) and the research-mode buttons (615), and the click branch at 1288 runs for both.
  - R-M11 (P2, e): there is no hard timeout on a stream, only the 30-second notice (`ui/milo.js:49-50, 830`); a failed `loadChoices` silently removes the Level control and leaves one persona (379-381, 505).
  - R-M12 (P2, a): drafted wording presumes a trade frame: "Walk me through the entry zone and what invalidates it.", "…for a swing long here?", "Why did the ranker pick that strike…" (`ui/milo.js:556`), Compare starter "Which of these looks strongest, and on what measure?" (281), Scan mode "Which are worth a closer look?" (600). Each only drafts, and the answer is governed by the server prompt.
  - R-M13 (P2, g): there is no AI-consent step (no `aiconsent.js`, no gate): the first Send transmits the page's figures, including a whole panel's visible figures for an Ask Milo button (`ui/milo.js:66-79`), and any attached file to the model provider; disclosure is the "What is attached" fold (540) and the privacy text (`pages/legalpages.js:52-54`).
  - R-M14 (P2, e): `paintLive` redraws every settled paragraph and re-mounts inline charts on each animation frame (`ui/milo.js:749-763`), quadratic on a long answer.
  - R-M15 (P2, f): `ai._human_error` tells public readers "Nothing is wrong with your key or the terminal" (`app/ai.py:1121-1124`), and on the hosted site tells them the deployment's own key was refused (`app/ai.py:1136-1139`).
  - R-M16 (P2, c): the knowledge ladder exists twice, `core/prefs.js:109-124` and classic `static/components/knowledge.js`, which v2 does not load (`index.html:38-39`).

### A17 Answer renderer and answer tags — `global` (`core/milo-text.js`)
- Files: `core/milo-text.js`, used by `ui/milo.js`.
- Purpose: turns the model's text into safe HTML and the server's tags into chips, charts, figures and action cards.
- Auth: none (pure functions).
- Sections: `renderAnswer` = split trailing follow-ups, `mdLite` markdown, charts, figures, actions, source chips (`core/milo-text.js:172-177`).
- Safety (Source): `mdLite` calls `esc()` on the whole text first and only then adds a small markdown subset (code, bold, italic, `##` headings, bullets, numbered steps, `[text](https://…)` links, `|` tables); links must start with `http://` or `https://` (`core/milo-text.js:47-67`, `core/format.js:130-132`); action JSON is escaped into attributes (151-163); a chart tag accepts only `[A-Z0-9.^=-]{1,12}` and a fixed span list (12).
- Controls: the tags the server's prompt contract defines. 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| `[[src key]]` | chip | label from 51 keys, e.g. Quote, Dealer gamma, Fair-value model, Sources Milo read | Link to the page for the answer's company (`sourceHref`, 41-44) or open the Sources fold | At most one chip per label per paragraph (84-95) |
| `[[chart SYM 1m/3m/6m/1y/2y/5y]]` | figure | "SYM, daily closes over the last <span>" | Drawn by `mountAnswerCharts` (`ui/milo.js:782-797`) | |
| `[[figure revenue/margins/cashflow/segments/eps/reactions SYM]]` | figure | "Drawing SYM's figures from Optic's data" | `FF.build` (`ui/milo.js:766-779`) | At most 2 per answer (170) |
| `[[action open SYM section]]` | card | "Open SYM, <Section>" | `router.go('#/SYM/<slug>')` (`ui/milo.js:957`) | Sections: Overview, Chart, Options, Investing, Earnings, Financials, News |
| `[[action compare SYM SYM …]]` | card | "Compare A, B" (2 to 4) | `#/compare?t=…` (958) | |
| `[[action watch SYM "list"]]` | card | "Add SYM to "list"" | `store.follow` into the named list or the active one; says when the named list does not exist (968-974) | **Writes**; Confirm and Not now |
| `[[action chart range interval]]` | card | "Chart: 1M, daily" | `#/SYM/chart?interval=…&range=…` (963) | Ranges 1m, 3m, 6m, 1y, all; daily or weekly |
| `[[action indicator id]]` | card | "Show <study>" | `#/SYM/chart?show=…` (965-966) | 13 study ids (`core/milo-text.js:110-111`) |
| `[[action screen words]]` | card | "Find stocks: "<words>"" | `#/scan?q=…` (960) | Card says words the free reader cannot read use one Milo question when run (160) |
| `[[action save "question"]]` | card | "Save this question to Research" | `saveQuestion` (975-978) | **Writes**; Confirm and Not now |
| `[[action level price "note"]]` | card | "Mark 123.45 on the chart (note)" | Draws a dashed level only if the price is within 0.25% of a level in the answer's own context, then navigates to the chart (947-952, 979-990) | **Writes** `optic.chart.drawings.v2` |
| `[[action valuation KEY=VALUE … "reason"]]` | card | "Try on the model on screen: …" or "Open the valuation model" | Preview, Apply, Undo against the open model (915-943) | Changes working assumptions only |
| Follow-ups `→ question` | buttons | the question | Drafts (70-81) | At most 4 |

- States: invalid action → "Not available: <reason>." (`core/milo-text.js:151`); more than 2 action cards or 2 figures → the extras are dropped silently (165, 170).
- API dependencies: none here. Storage: none here. 
- Risks seen in code: none beyond A16 R-M12; escaping order is correct, so a model answer cannot inject markup.

### A18 Scout, as the panel uses it — `global`
- Files: `static/components/scout.js` (classic script, `window.OpticScout`), `ui/milo.js:181-268`, `core/prefs.js:64-69`, top-bar badge (`ui/shell.js:81`, CSS only).
- Purpose: Milo's mascot; reacts only to real Milo events, never on its own loop.
- Auth: none. Used API: `OpticScout.html({size,label})`, `.attach(el,{slot})`, `.motion()`, `.setMotion(v)`; controller `.set(state, via)`, `.gesture(name)`, `.state` (`components/scout.js:115-130, 337-379`). Controls: the guide button and menu (A16). Nothing is fetched but sprites from this site (`components/scout.js:45`). Storage: `optic.scout.motion.v1` (`components/scout.js:100-112, 359-364`); Settings' Motion: Reduce counts as the system asking (`components/scout.js:109-112`). States: without the script the panel reads the same, without the figure (`ui/milo.js:191-192, 212`). Risks: none seen.

### A19 Chat and research endpoints — `POST /api/chat`, `POST /api/research`, `GET /api/ai-allowance`
- Files: `app/main.py:7330-7569, 7738-7914`, `app/ai.py:1690, 3440-3698`, `app/milo_tools.py`, `app/auth/ratelimit.py`.
- Purpose: stream a model answer to the panel.
- Auth: **spend guard** `_spend_guard` runs first (`app/main.py:7857, 7468-7558`): verified owner passes unmetered (7471-7487); a signed-in reader is checked against the monthly cap (paid plans) then spends one of the day's allowance (`auth_ratelimit.spend('ai_day', …)`, Free 3, Pro 15, Enterprise 4,000) (7488-7507); a guest gets 401 "Milo needs a free account. 3 messages a day once you are in, and everything else in the terminal stays open either way." unless `GUEST_AI_CALLS_PER_DAY` is raised (7508-7519); then an in-memory hourly burst cap of 30 per address (`AI_CALLS_PER_HOUR`, 7360, 7532-7558). If the accounts database is unreadable the daily half is skipped and logged once (7529-7530, 7394-7401). `_count_question` records the question for Metrics (7858, 7457-7465). **No `csrf_guard`** on either route although they spend a session's allowance (the client sends the header anyway, `ui/milo.js:835`); `SameSite=Lax` is the only cross-site defence (`app/auth/config.py:73-88`).
- Request contract (`/api/chat`, `app/main.py:7859-7870`): `messages [{role, content}]`, `context {…}` (any `brokerage_portfolio` or `brokerage_linked` the browser sends is stripped, 7793-7799), `web bool`, `attachments [{name, media_type, data base64}]` (max 4, 5 MB each, PNG, JPEG, GIF, WebP, PDF, re-checked, `app/ai.py:1029-1051`), `persona` (default `neutral`), `mode` (normalised, `app/knowledge.py:166-175`), `horizon` (normalised, `app/horizon.py`). `/api/research` (`app/main.py:7898-7914`): `ticker`, `question`, `context`; 400 "Provide a ticker or a question." when both are empty.
- Does it stream? Yes. `StreamingResponse(media_type="text/event-stream")` with `Cache-Control: no-cache` and `X-Accel-Buffering: no` (`app/main.py:7889-7895, 7910-7914`); frames are `event: <name>\ndata: <json>\n\n` (`app/ai.py:1690-1691`). `/api/chat` events: `status {state}`, `attachments {problems}`, `assumed {level, horizon, horizon_source}`, `delta {text}`, `retrieved {items}`, `done {model, citations, read, retrieved, loaded, named, usage}`, `error {message}` (`app/ai.py:3452-3603`). `/api/research` events: `status`, `delta`, `done {sources:[{title,url,age}], model}`, `error` (3609-3698). Starlette's GZip middleware (`app/main.py:245`) skips `text/event-stream` in the installed Starlette 0.49.3 (`…/starlette/middleware/gzip.py:9`), but `requirements.txt` only asks for `fastapi>=0.110`.
- What runs per question: the server also loads data for named symbols (`_augment_chat_context`), a research pack, the research framework and chart levels, and the linked portfolio when it decides the question is about it (`app/main.py:7871-7888`); the model may then call up to 13 tools (quote, options, chart levels, fundamentals, valuation, earnings, news, market, compare, assessment, screen, my watchlists, my portfolio) for up to 4 tool rounds (`app/main.py:7769-7775`, `app/milo_tools.py:42`), each round a model call; model `claude-sonnet-5-5` (`app/ai.py:60`). So one guarded "question" can be up to five model calls plus web searches. Deep research: one call with adaptive thinking, effort high, `max_tokens` 12,000 and up to 10 web searches (`app/ai.py:3640-3652`).
- Spends the operator's money: yes, both. Errors before the stream: 401, 429 (monthly sentence, daily sentence "That is N assistant messages today…", or hourly "…in an hour from this connection. Try again in about N minutes."), 400.
- `GET /api/ai-allowance` (`app/main.py:7561-7569, 7404-7454`): `{allowance:{scope, used, allowed, left, next_at, plan, plan_label, signed_in_allowance, requires_account, enforced, month?}, ai:{enabled, model, credential_source, hint, key_refused?}}`; anonymous.
- States and API dependencies: Anthropic API server-side. Storage: server keeps a per-call ledger of size and model with no user (`app/ai_store.py:293-322`) and a per-question count with the user id and kind (`app/metrics.py:55-61`).
- Risks seen in code:
  - R-B-1 (P1, g): see A16 R-M1 (portfolio attachment rule, `app/main.py:7776-7787`).
  - R-B-2 (P2, g): `/api/ai-allowance` and `/api/health` are anonymous and return the model name, which credential source is in use (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or an `ant auth` profile), whether Anthropic refused the key at the last check, a hint naming the environment variable, the deployed commit, boot time, uptime and the applied migration list (`app/ai.py:1244-1296`, `app/main.py:1020-1052, 7561-7569`).
  - R-B-3 (P2, g): every per-address bucket here and in A29 is keyed on the first entry of `X-Forwarded-For`, which the caller can set (`app/auth/ratelimit.py:67-78, 120-139`): the hourly burst cap, the password-reset, report, OAuth and passkey-login limits can be sidestepped by changing the header. The per-email buckets on sign-in, register and forgot-password, the per-user buckets and the per-account daily allowance do not depend on it.
  - R-B-4 (P2, e): see A16 R-M9 (allowance spent before the model call).
  - R-B-5 (P2, c): `/api/chat` and `/api/research` skip `csrf_guard` that every other session write calls (`app/main.py:7857, 7902`).

### A20 Levels, personas and timeframes — `GET /api/knowledge/modes`, `GET /api/personas`
- Files: `app/knowledge.py`, `app/ai.py:99-195`, `app/horizon.py`, `app/main.py:7155-7178, 7572-7580`.
- Purpose: the choices in Response settings and the persona menu, served so the menu and the behaviour share one source.
- Auth: none. Spend: none (static catalogues).
- Levels (`app/knowledge.py:58-163`, order 163): Simple (ladder 0), Financially Literate (1, default), Advanced (2), Professional (3), Adaptive (judges from the question; panels at level 1). `normalise` falls back to Financially Literate (166-175). `resolve_for_answer` makes Adaptive answer as Simple when the question starts like "what is", "explain", "eli5", "I'm new", as Advanced when it uses "gamma", "skew", "basis" and the like, else Literate (225-261). The catalogue states what a level changes (words, panel count, term explanation) and never changes (the figures) (213-221).
- Personas (`app/ai.py:113-186`): `neutral` "Neutral analyst" (default), `longterm` "Long-term investor", `stoic` "Risk and process", `quant` "Statistician", `skeptic` "Devil's advocate"; served with `changes` and `never_changes` lists (99-107).
- Timeframes (`app/horizon.py`): `auto` "Auto", `day` "Day trading", `swing` "Swing", `long` "Long term"; words in the question override the saved choice for one answer (`stated_in`); nothing is written back.
- States, API, storage: as A16.
- Risks seen in code: R-M2 (persona wording); the "Simple" level prompt asks the model to answer "why does this matter to somebody holding this stock" after each point (`app/knowledge.py:73-74`), which invites a holder-specific read (P2, a).


---

# Part 4. Account and preferences

### A21 Sign in, create account, forgot and reset — `#/signin` (`?mode=up`, `?mode=forgot`, `?mode=reset`)
- Files: `pages/signin.js`, `core/passkey.js`, `core/authlinks.js`, `app.js:84-92, 138, 343-345`.
- Purpose: one page, four modes, against the same `/api/auth` routes as classic.
- Auth: guests. A signed-in reader is sent Home, except in reset mode (`app.js:138`).
- Sections in render order (`pages/signin.js:32-69`): sign in: h1 "Sign in to Optic", line "Your watchlists, watches and Milo questions are kept on your account.", provider row (passkey, Google, Apple, only the ones the server says are available) and "or with email", the form, "Forgot your password?", "New to Optic? Create an account". Create: h1 "Create your account", "Free. Keeps your watchlists and alerts on every device, and opens Milo.", provider row, form, the Terms and Privacy agreement line, "Have an account? Sign in". Forgot: h1 "Reset your password" and "Enter the address on the account. If it has a password, a reset link goes to that inbox and works once, for 15 minutes.". Reset: h1 "Choose a new password", "Every signed-in device is signed out when this is done."
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Sign in with a passkey | button `[data-v2-pk-signin]` | "Sign in with a passkey" → "Waiting for your device..." | `passkey.signIn({remember})` then `done('in')` (`pages/signin.js:85-90`; `core/passkey.js:34-47`) | Shown when the browser supports it and the server does not say unavailable (22-24); a cancelled prompt shows nothing (89) |
| Continue with Google | link `a.btn` | "Continue with Google" | Browser navigation to `/api/auth/google/start?next=<encoded /v2/ + hash>` (`pages/signin.js:25`) | Only when `providers.google.available` |
| Continue with Apple | link | "Continue with Apple" | `/api/auth/apple/start?next=…` (26) | Only when available |
| Email | `input[type=email][name=email]` | placeholder "Email"; autocomplete `username webauthn` (sign in) or `email` (create) | Form field (58) | |
| Password | `input[type=password][name=password]` | placeholder "Password"; `current-password` or `new-password` | Form field (59) | Create mode lists the server's password rules (60, 18) |
| First name, Last name | inputs (create only) | placeholders "First name" (required), "Last name" | Form fields (56-57) | |
| Confirm password | input (create) | "Confirm password" | Mismatch → "Those passwords do not match." before any request (100) | |
| Keep me signed in on this device | checkbox `name=remember`, checked | "Keep me signed in on this device" | Sent as `remember` (98, 101) | Honoured on sign-in only (R-SI-2) |
| Sign in / Create account | submit | "Sign in" / "Create account" | `POST /api/auth/login` (98) or `/api/auth/register` (101), then `done('in')` | Button disabled while sending (96) |
| Forgot your password? | text button `[data-v2-auth-mode=forgot]` | "Forgot your password?" | Switches mode (84) | |
| New to Optic? / Have an account? | text buttons `[data-v2-auth-mode=up]` / `[data-v2-auth-mode=in]` | "Create an account" / "Sign in" | Switches mode (84) | |
| Send reset link | submit (forgot) | "Send reset link" | `POST /api/auth/forgot-password` then a note (106-110) | |
| Back to sign in | text button | "Back to sign in" | Switches mode | |
| Set password and sign in | submit (reset) | "Set password and sign in" | `POST /api/auth/reset-password {token, password, confirm_password}`, then `done('')`, toast "Password changed, and you are signed in." (111-117) | Token held in memory only (`startReset`, 14) |
| Send a new link | text button | "Send a new link" | Switches to forgot (48) | Reset mode with no token |
| Terms of use, Privacy policy | links | "Terms of use", "Privacy policy" | `#/terms`, `#/privacy` (66) | Create mode only |

- Inputs and search fields: all forms are `novalidate`; the only client check is that two passwords match; everything else is the server's sentence shown in `#si-err` (`role=alert`) (`pages/signin.js:71, 118-122`); a limit answer reads "Too many attempts. Wait a minute and try again." (71). The first field is focused except on touch devices (77). Enter submits.
- Charts, tables, AI sections, modals: none.
- States: loading: submit button disabled; passkey button text; error: `#si-err`; success: toasts "Account created. A confirmation link is on its way to your inbox." (103), "…Email is not switched on yet, so no confirmation message was sent." or "…the confirmation email could not be sent. You can request another from Settings." (103), forgot note "If an account uses that address, a reset link is on its way." or "Email is not switched on yet, so a reset link cannot be sent. Devices already signed in stay signed in." (108); empty: none.
- API dependencies: `POST /api/auth/login`, `/register`, `/forgot-password`, `/reset-password`, `/passkeys/login/options`, `/passkeys/login/verify`; `GET /api/auth/google/start`, `/apple/start`; providers and the password rules come from `GET /api/auth/me` (`pages/signin.js:16-17`). After success `api.invalidate('/api/')` then `app.settleAuth` (81).
- Preferences and storage keys: none written here; sign-in destination is replaced into the address first because settling may reload (81).
- Risks seen in code:
  - R-SI-1 (P1, g): see A29 R-A29-1 (the provider sign-in start and callback are not tied to the browser that began them).
  - R-SI-2 (P2, d): "Keep me signed in on this device" is sent on Create account (`pages/signin.js:101`) but `register` ignores `remember` and always issues the long session (`app/auth/routes.py:207`, `_remember` is read only by login and passkey login, 251, 658).
  - R-SI-3 (P2, d): `autocomplete="username webauthn"` (`pages/signin.js:58`) promises passkey autofill, but nothing calls `navigator.credentials.get` with conditional mediation (`core/passkey.js:34-47` always opens the modal prompt).
  - R-SI-4 (P2, c): `store.signIn()` is a second login implementation with no caller (`core/store.js:64-68`); sign-in is posted inline (`pages/signin.js:98`).
  - R-SI-5 (P2, e): sign-in always lands on Home: nothing in v2 produces `#/signin?next=…` (grep), so the "Sign in" link in Milo's card, the Saved research page and the "Create a free account" toast all drop the reader's place (`pages/signin.js:81`; `ui/milo.js:680, 1282`).
  - R-SI-6 (P2, g): a wrong password for an address that has no password but has Google, Apple or a passkey answers "That account signs in with Google…" (`app/auth/routes.py:227-240`), which tells anyone typing an address that the account exists and how it signs in; the code comments accept this. Register answers 409 for a known address (189-195).

### A22 Links from email and providers, and passkeys — `global` (`?verify=`, `?reset=`, `?auth=`, `?auth_error=`)
- Files: `core/authlinks.js`, `core/passkey.js`, `app.js:332-347`.
- Purpose: act once on a link that arrived in the address, then remove it from the address.
- Auth: none.
- Controls (no UI; the address parameters are the inputs): 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| `?verify=TOKEN` | address parameter | toast "Email address confirmed." or the server's sentence or "That confirmation link is no longer valid." | Scrubbed from the address, then `POST /api/auth/verify-email` (`core/authlinks.js:37-42`) | Reloads `/api/auth/me` on success |
| `?reset=TOKEN` | address parameter | toast "That reset link is no longer valid." if bad | Scrubbed, `GET /api/auth/reset/check?token=`; valid → reset form with the token kept in memory; invalid → forgot form (`core/authlinks.js:43-53`; `app.js:343`) | The token is not left in the address |
| `?auth=ok&next=…` | address parameter | toast "Signed in as <email>." | Scrubbed; the part of `next` after `#` is restored as the route (`core/authlinks.js:54-60`; `app.js:345, 347`) | |
| `?auth_error=<code>&provider=<p>` | address parameter | one of eight sentences (state, provider, config, taken, needs_link, no_email, inactive, denied), with the provider's name worked in (`core/authlinks.js:10-28`) | Scrubbed; `needs_link` opens the sign-in page (`core/authlinks.js:61-67`) | |
| Add a passkey | function `create(name)` called from Settings | "Saved "<name>"." | `POST …/passkeys/register/options`, `navigator.credentials.create`, `POST …/passkeys/register/verify` (`core/passkey.js:10-31`) | Writes `optic.auth.passkeyMade` for classic (22) |
| Sign in with a passkey | function `signIn({remember})` | see A21 | `POST …/passkeys/login/options`, `navigator.credentials.get`, `POST …/passkeys/login/verify` (34-47) | |

- States: toasts above. API dependencies: as the table. Storage: `optic.auth.passkeyMade` (write, `core/passkey.js:22`; read by classic `static/auth.js:259-261`).
- Risks seen in code: R-AL-1 (P2, g): the emailed tokens travel in the query string of `/?verify=` and `/?reset=`, so they reach the server's access log (kept up to 90 days per the privacy text, `pages/legalpages.js:80`) even though the page removes them from the address at once (`core/authlinks.js:29-33`); reset tokens last 15 minutes and are single-use, verification tokens a day (`app/auth/config.py:52-53`).

### A23 Settings — `#/settings`
- Files: `pages/settings.js`, `core/prefs.js`, `core/passkey.js`, `core/device.js`, `core/format.js:146-150`, `ui/states.js`.
- Purpose: the account (profile, security, plan, deletion), this browser's preferences, what is stored where, and Report a problem.
- Auth: a guest sees an Account card with Create an account and Sign in, then Appearance, Text size, Keyboard, Milo level, Time zone, About, Report (`pages/settings.js:36-45`); a signed-in reader also sees Profile, Security, Plan and Delete account (46-70). Brokerage "Manage" appears when the provider is available (61). Sign-in state `unknown` shows "Your sign-in could not be checked just now…" and a "Try now" button (39).
- Sections in render order (`pages/settings.js:201-206`): header h1 "Settings"; Account or Profile, Security, Plan, Delete account; Appearance (Theme, Motion); Text size; Keyboard; How Milo explains things; Time zone (with a market-hours table); About this build; Report a problem.
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Create an account | link | "Create an account" | `#/signin?mode=up` (`pages/settings.js:44`) | Guest |
| Sign in | link | "Sign in" | `#/signin` (44) | Guest |
| Try now | button `[data-v2-set-recheck]` | "Try now" | `store.loadMe()` then `settleAuth` (250) | Unknown state |
| First name, Last name, Save | inputs + submit | "First", "Last", "Save" | `PATCH /api/auth/profile`; toast "Profile saved." (`pages/settings.js:49-51, 293-295`) | |
| Resend link | button `[data-v2-set-resend]` | "Resend link" | `POST /api/auth/resend-verification`; toast per answer (251) | Shown while the email is unconfirmed (53) |
| Change / Add a password | button `[data-v2-pw-toggle]`, `aria-expanded` | "Change" or "Add a password" | Opens the form (259) | |
| Password form | inputs + submit | "Current password" (if one is set), "New password", "Confirm new password", "Save password", "Cancel" | `POST /api/auth/change-password`; toast "Password changed. N other sessions signed out." (297-301) | Rules shown from the server (100) |
| Remove the password | two-step: `[data-v2-sec-arm="provider:email"]` then `[data-v2-sec-do]` | "Remove" → "Remove the password" and "Keep" | `DELETE /api/auth/identities/email` (266) | Disabled when it is the only way in, with that title (88, 93) |
| Rename passkey | button `[data-v2-pk-rename-open]` then form | "Rename" → name input, "Save", "Cancel" | `PATCH /api/auth/passkeys/{id}`; toast "Passkey renamed." (269-270, 304-307) | |
| Remove passkey | two-step arm and do | "Remove" → "Remove the passkey" and "Keep" | `DELETE /api/auth/passkeys/{id}` (265) | Text "The device it lives on will no longer sign you in." (106) |
| Add a passkey | button `[data-v2-pk-add]` | "Add a passkey" → "Waiting for your device..." | `passkey.create('')`; toast `Saved "<name>".` (271-276) | Disabled with a title when unsupported (107) |
| Connect Google / Apple | link | "Connect" | Navigation to `/api/auth/<p>/start?link=1&next=<path>` (111) | Only when available; otherwise the server's reason |
| Disconnect Google / Apple | two-step | "Disconnect" → "Disconnect Google" and "Keep" | `DELETE /api/auth/identities/{provider}` (266) | Refused when it is the last method (`app/auth/routes.py:580-583`) |
| Sign out / Revoke (per session) | button `[data-v2-sess]` | "Sign out" (this device) or "Revoke" | `DELETE /api/auth/sessions/{id}`; ending this one calls `settleAuth` (278-283) | Rows show device label, last used, IP address, signed-in time (114) |
| Show all sessions | text button `[data-v2-sess-all]`, `aria-expanded` | "Show all N sessions" / "Show the five most recent" | Toggles (277) | |
| Sign out of all devices | two-step | "Sign out of all devices" → "Sign out everywhere, including here" and "Keep" | `POST /api/auth/logout-all` then `settleAuth` (264) | |
| Upgrade to Pro / Billing history / Manage billing | buttons `[data-v2-billing]` | "Upgrade to Pro, <price>", "Billing history", "Manage billing" | `POST /api/billing/checkout` or `/portal`, then `location.href = url` only if it is on stripe.com or snaptrade.com (`SAFE`, 23; 252-256) | When billing is off: the sentence "Plans are not on sale yet. Every account is on Free." (`core/format.js:146-150`) |
| Manage (linked brokerages) | link | "Manage" | `#/brokerage/connections` (61) | |
| Delete this account | button `[data-v2-set-del]` | "Delete this account" | Opens the confirm form (257) | |
| Delete form | inputs + submit | "Type <email> to confirm", "Your password" (if one is set), "Delete the account", "Cancel" | `POST /api/auth/delete-account`; `handDeviceSessionToGuest()`; toast "Account deleted. The terminal stays open." (308-313) | Server also checks the typed address and the password (`app/auth/routes.py:729-737`) |
| Theme | segmented `[data-v2-theme]` | "Dark", "Light", "Follow system" | `prefs.setTheme` (246) | `optic.theme` |
| Motion | segmented `[data-v2-motion]` | "Follow system", "Reduce" | `prefs.setMotion` (247) | `optic.v2.motion.v1` |
| Text size | segmented `[data-v2-scale]` | "Compact", "Default", "Large" | `prefs.setScale` (248) | `optic.ui.scale.v1`; zoom 1/1.15, 1, 1.3/1.15 (`core/prefs.js:34`) |
| Show the shortcuts | button `[data-v2-shortcuts]` | "Show the shortcuts" | Opens the shortcuts sheet (`app.js:239`) | |
| Advanced answers from Milo | switch `[data-v2-adv]` | "Advanced answers from Milo" | `prefs.setAdvanced(checked)`; toast (288) | On = Advanced, off returns to the level chosen before (`core/prefs.js:117-124`) |
| Show times in | `select[data-v2-tz]` | 17 options: "My device's time zone", New York, Chicago, Denver, Los Angeles, Toronto, São Paulo, London, Paris / Berlin / Madrid, Istanbul, Dubai, Mumbai, Singapore, Hong Kong, Tokyo, Sydney, UTC, each with its current clock (`core/prefs.js:13-31`; `pages/settings.js:149`) | `prefs.setTimezone` (287) | `optic.timezone` |
| Report a problem | button `[data-v2-report]` | "Report a problem" | `openReport` (249) | A6 |

- Inputs and search fields: profile names (no `maxlength` on the page; the server cuts at 80), passwords (`required`, server rules), typed email for deletion, passkey name (`maxlength 60`).
- Charts, tables, AI sections: the Market hours table (Session, Eastern (market), Your zone) from `GET /api/session` (`pages/settings.js:150-152`). Tooltips: titles on disabled controls. No AI.
- States: loading: "Checking..." (38), skeleton "Loading your sign-in methods" (85), "Checking plans..." (75), skeleton "Loading market hours" (153); error: "Could not load your sign-in methods: …" (86), "Market hours could not be read just now." (153), per-form error lines, toasts from `api.explain(e, "The change")` (241); billing return banner "Thanks. Your plan updates as soon as the payment provider confirms it, usually within a minute." or "Checkout cancelled. Nothing was charged." (232); empty: "None yet." passkeys, "None." sessions (105, 115).
- API dependencies: `GET /api/auth/identities`, `/api/auth/sessions` (forced), `GET /api/billing/status`, `GET /api/brokerage/status`, `GET /api/session`, `GET /api/health`; writes as in the table; `POST /api/feedback`.
- Preferences and storage keys: `optic.theme`, `optic.v2.motion.v1`, `optic.ui.scale.v1`, `optic.timezone`, `optic.knowledge.v1`, `optic.knowledge.basic.v1`, `optic.knowledge.asked.v1` (all `core/prefs.js`). None of these is synced to the account.
- Risks seen in code:
  - R-ST-1 (P2, d): the account has server-side `time_zone`, `default_market` and `default_landing` and routes to read and write them (`app/auth/store.py:589-626`, `app/auth/routes.py:693-705`), and the privacy text says they are kept (`pages/legalpages.js:27`), but no v2 control writes them and v2 never reads `me.preferences`; the time zone chosen here lives only in this browser.
  - R-ST-2 (P2, f): "Delete this account" says everything kept on it is removed (`pages/settings.js:63`) but, after deleting, `handDeviceSessionToGuest()` leaves the person's browser-held things (Milo chats, paper trades, drawings, recent symbols) in place as a guest's (`core/device.js:186-189`), and the page does not say so.
  - R-ST-3 (P2, g): a profile picture, if set, is drawn as `<img src>` from any `http` or `https` address the server accepted (`pages/settings.js:48`, `app/auth/routes.py:430-437`), so a third-party host sees the reader's address and browser; plain `http` is allowed.
  - R-ST-5 (P1, e): a wrong **current password** (Change password) or a wrong **password on Delete account** is answered 401 by the server (`app/auth/routes.py:464, 737`), `core/api.js:26` classifies every 401 as `auth`, and the two forms show a server sentence only for `bad` (400, 409, 422) (`pages/settings.js:301, 313`), so the reader is told "Sign in to see the password." or "Sign in to see deleting the account." (`core/api.js:131`), as if they had been signed out.
  - R-ST-4 (P2, e): sign-out-everywhere and revoke-this-device rely on the device-session reload to clear in-memory cached answers (`pages/settings.js:264, 281`); only sign-in, sign-up and sign-out call `api.invalidate('/api/')` (`core/store.js:66, 70`, `pages/signin.js:81`). After account deletion the 15 to 60 second cached GETs are not dropped (`pages/settings.js:308-313`).

### A24 Terms of use and Privacy policy — `#/terms`, `#/privacy`
- Files: `pages/legalpages.js`.
- Purpose: the two documents, in force from October 19, 2026 (`pages/legalpages.js:8-9`).
- Auth: none. Sections: header (title, "Effective October 19, 2026. See also …"); `article.legal-doc` with 16 Terms sections or 14 Privacy sections (`pages/legalpages.js:18-95, 97-151, 164-166`). Terms: Agreeing to these terms, What Optic is, Who can use it, Your account, Plans and payment, Using Optic fairly, The data and Milo, Linking a brokerage, Your content, Availability and changes, No warranty, Limits of liability, Ending, Law and disputes, General, Changes and contact. Privacy: Who this covers, What you give when you create an account, What Optic keeps while you use it, How we use it, Cookies and tracking, Milo the assistant, Linking a brokerage (Pro), Payments, Email, Market data sources, Where it is kept and for how long, Deleting your account, Your choices and rights, Contact and changes.
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Cross-link | link | "Terms of use" / "Privacy policy" | `#/terms`, `#/privacy` (`pages/legalpages.js:165`) | |
| In-text Privacy link | link | "Privacy policy" | `#/privacy` (99) | |
| Anthropic commercial terms, Anthropic privacy policy | external links `target=_blank rel=noopener` | "commercial terms", "privacy policy" | Open anthropic.com (53) | |
| SnapTrade terms | external link | "terms and conditions" | Opens snaptrade.com (125) | |
| Contact | `mailto:` links | `theopticterminal@gmail.com` | Opens a mail client (16, 88, 93, 149) | |

- Inputs, charts, AI sections: none. States: none (static text). API dependencies: none. Storage: none.
- Risks seen in code: R-LG-1 (P2, f): the file states the pages are "Not reviewed by a lawyer" while `IN_FORCE = true` (`pages/legalpages.js:3-5, 8`); R-ST-1 above (privacy text names stored choices no control writes); the privacy text says holdings go to Milo "only when your question is about your portfolio or you ask from the Brokerage page" (`pages/legalpages.js:53`), which A16 R-M1 shows is not what the server enforces on this branch.

### A25 Dossier start — `#/dossier`
- Files: `pages/dossierstart.js`, `ui/palette.js`, `ui/symbols.js`, `core/store.js`.
- Purpose: Dossier with no company open: a search box and three short lists.
- Auth: none. Sections in render order (`pages/dossierstart.js:33-40`): header h1 "Dossier" with "Everything Optic has on one company or fund: the business, the price, the options and what comes next. Choose one to open it."; search form; "Opened recently" (up to 6, instruments left out); the active list's name or "Your watchlist" (up to 8, not repeating recents); "Well-known names" (AAPL Apple, NVDA NVIDIA, MSFT Microsoft, SPY S&P 500 fund, minus any already shown) (15, 29-32).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Search box | `input[name=q][data-v2-ta=submit]` | placeholder "Search a company, fund or ticker" | Typeahead (A13); submit below (`pages/dossierstart.js:36`) | Focused on non-touch devices (53) |
| Open | submit | "Open" | `GET /api/search?q&limit=5`; exact symbol → `location.hash = '#/SYM'`; otherwise `palette.open(box, {seed: q})`; a failed search with ticker-shaped text opens as typed (41-52) | R-A14-1, R-A14-2 |
| Company rows | links `a.ds-row` | logo, symbol, optional name | `#/SYM` (22) | |

- Inputs: empty submit refocuses the box (45). Debounce: none on the form (typeahead has its own). Invalid text: goes to the palette (51).
- States: loading: none; empty: lists with nothing to show are omitted (20); error: none shown (search failure falls back).
- API dependencies: `GET /api/search`, `GET /api/logo/{sym}` per row. Storage: reads `optic.recent.v1` and the watchlist through `core/store.js`. Milo context: `{view:'dossierstart'}` (28).
- Risks seen in code: R-A14-1 and R-A14-2.

### A26 Saved research — `#/research`
- Files: `pages/saved.js`, `core/research.js`, `ui/milo.js`.
- Purpose: the questions the reader kept to ask Milo again, plus four ways to start an investigation.
- Auth: guest (this browser's list, up to 40, `core/research.js:11`) or account (server list, plan limit: Free 40, Pro 1,000).
- Sections in render order (`pages/saved.js:40-46`): header "Saved research" with "Questions you kept to ask again" (and a sign-in link for guests); "Your questions" list; "Start an investigation" (4 routes).
- Controls: 

| Control | Kind | Label or text | Action it performs (handler, file:line) | Notes |
|---|---|---|---|---|
| Sign in | link | "Sign in" | `#/signin` (`pages/saved.js:43`) | Guests |
| Company link | link | the symbol | `#/SYM` (36) | Or "The market" with no link |
| Ask again | button `[data-sv-ask]` | "Ask again" | `openMilo({question, symbol, about:'Saved research'})`: drafts only (55) | |
| Forget | button `[data-sv-forget]` | "Forget" (aria-label "Forget: <question>") | Removes it (account: `DELETE /api/saved-research/{id}`), then toast "Forgotten." with Undo that saves it again (57-62; `core/research.js:59-70`) | |
| Route: strongest names | link | "Which names look strongest right now?" | `#/scan` (16) | |
| Route: stack up | link | "How do two or three names stack up?" | `#/compare` (17) | |
| Route: one company | button `[data-sv-route]` | "What is going on with one company?" | Opens Milo with nothing drafted (56) | |
| Route: sources | button | "I need sources and citations." | Opens Milo and focuses its Deep research button (56) | Does not send |

- Inputs: none. States: loading skeleton "Loading saved research" (`pages/saved.js:30`); error `failed('Saved research', err, {retry:'saved'})` with a working retry (29, 73); empty "Nothing saved yet / Press Save under a question you asked Milo, and it is kept here to ask again." plus where they are kept (33).
- API dependencies: `GET /api/saved-research?limit=200` (forced), `POST /api/saved-research`, `DELETE /api/saved-research/{id}` (all session; writes need CSRF, `app/account.py:412-485`). Request identity: counter `seq` (`pages/saved.js:48-49`). Storage: `optic.research.v1` for guests. Milo context: the first 20 saved questions with symbols (68), sent to Milo only if the reader asks from this page and leaves "Saved research" attached.
- Risks seen in code: R-SV-1 (P2, e): Forget removes by matching text, so two identical guest entries differing only in case or spacing are one (`core/research.js:24, 65`); the Undo toast re-saves through `saveQuestion`, which would refuse at the plan limit and say so (`core/research.js:37-48`) rather than restore.


### A27 Device session and personal keys — `global` (`core/device.js`)
- Files: `core/device.js`, `app.js:95-104, 256-279`, `core/store.js`, `ui/milo.js`.
- Purpose: a browser can serve several people over time; a "personal key" is read and written only while this browser holds that person's things, so one person's lists, chats or trades never show under another's name. The classic app uses the same keys and shelf format (`core/device.js:1-10`).
- How it works: `optic.session.holder.v1` names who the personal keys belong to (`guest` or an account id) (12, 15). When a different person settles (sign in, sign out, another account), the old person's keys are copied to `optic.session.shelf.<who>`, removed, the newcomer's shelf is put back, and the page **reloads** so nothing is shown under the wrong name (83-99, 157-184). A guest with things on the browser who signs in is asked first (A6 Welcome back). Another tab switching person reloads this tab (221-227). `holds(user)` is true only for the holder (192-197) and gates `store.readJSON/writeJSON` (`core/store.js:35-42`), Milo history (`ui/milo.js:132, 134`), saved research (`core/research.js:32, 50`), the palette's saved rows (`ui/palette.js:113`) and the "level" action (`ui/milo.js:982`).
- The 28 personal keys (`core/device.js:17-46`): `optic.brokerage.scope.v1`, `optic.recent.v1`, `optic.scan.recent.v1`, `optic.pulse.history.v1`, `optic.research.v1`, `optic.chart.watch.v1`, `optic.watchlists.v1`, `optic.watchlist.account.v1`, `optic.watches.v1`, `optic.screener.v1`, `optic.signals.v1`, `optic.thesis.v1`, `optic.valuation.v1`, `optic.dcf.v1`, `optic.chart.drawings.v1`, `optic.chart.drawings.v2`, `optic.chart.notes.v1`, `optic.chart.checks.v1`, `optic.chart.stopcheck.v1`, `optic.paper.v1`, `optic.roth.inputs`, `optic.snapshots.v1`, `optic.entry.budget.v1`, `optic.v2.picker.v1`, `optic.v2.replay.v1`, `optic.v2.paper.draft.v1`, `optic.writeToken`, `optic.auth.passkeyOffered`. The "Welcome back" sheet names 13 of them under 12 phrases ("recent searches", "a watchlist", "watches", "theses", "saved research", "valuation scenarios", "signal history", "a screen", "paper trades", "chart drawings", "chart notes", "Milo conversations") (`core/device.js:48-62`).
- Controls: the two buttons of the sheet (A6). Inputs: none. States: none of its own; `'ask'` leaves personal keys unreadable until answered (R13). API: adoption posts in A6.
- Risks seen in code:
  - R13 (P1, e): see A6 (dismissing the question blocks personal reads and writes silently).
  - R-DS-1 (P2, g): keys that hold a reader's own choices are not shelved, so on a shared browser the next person sees them: Home's layout and linked company `optic.v2.workspace.v1` (`pages/workspace.js:34, 160-194`; `core/homelink.js:4`), `optic.options.filters.v1`, `optic.setups.view.v1`, `optic.setups.params.v1`, `optic.brokerage.section.v1`, `optic.chart.backtest.v1`, `optic.chart.pairs.v1`, `optic.v2.onboard.v1`. They carry company names and settings, not credentials.
  - R-DS-2 (P2, g): `optic.writeToken`, the owner's token for writes to the shared record, sits in localStorage in classic (`static/app.js:1921-1940`) and v2 only shelves it (`core/device.js:44`); any script on the page can read it, and a shelved copy persists under `optic.session.shelf.*`.
  - R-DS-3 (P2, e): when the swap cannot be written the module sets `stuck` and returns 'ok' without reloading (`core/device.js:174, 216`) while `holds` stays false, so the signed-in reader's personal keys silently do not save.

### A28 Preferences, store and API client — `global` (`core/prefs.js`, `core/store.js`, `core/api.js`)
- Files: those three, `core/format.js`.
- Purpose: device preferences shared with classic by key; shared reader state (who is signed in, watchlists, recent symbols); the one HTTP client.
- `core/prefs.js`: theme (`dark` default, `light`, `system`, writes `data-theme` `charcoal` or `ivory` and the theme-color meta, 47-56), Motion (`system` or `reduce`, writes `html[data-motion]`, 62-69), text size (`compact`, `default`, `large` as zoom, 34, 72-78), time zone (17 ids, `auto` default, 13-31, 81-88; clock helpers `stamp`, `dayTime`, `clock`), knowledge level (`simple`, `literate` default, `advanced`, `professional`, `adaptive`; `setKnowledge`, `setAdvanced`, 109-124). Reads and writes are wrapped so private mode never throws (36-37).
- `core/store.js`: `loadMe` (`GET /api/auth/me`, force; state `auth` is `loading`, `guest`, `user` or `unknown`, 45-57), `plan()`, `signIn` (unused), `signOut` (`POST /api/auth/logout`, 64-71); Recent symbols (8 kept, `optic.recent.v1`, 74-100; the visit's own `openedNow()` is memory only, 81-82); watchlists: an account's live on the server (`/api/watchlists…`, optimistic writes that roll back on refusal, re-read after a timeout, 207-235), a guest's in `optic.watchlists.v1` and the flat `optic.chart.watch.v1` mirror (114-151); limits: guest 12 lists, account plan 3 (Free) (186-192); share classes kept dashed (`BRK-B`) (105-109).
- `core/api.js`: `get(path,{ttl,force,onUpdate,timeout})` with an in-memory cache keyed by path, stale-while-revalidate, one shared promise per path, and no caching of a body that says `building` (89-107); `post/put/patch/del` (109-112); default timeout 20 s (39); sends `X-Optic-CSRF` from the `optic_csrf` cookie on **every** method (45-47); errors classified `offline`, `timeout`, `auth`, `forbidden`, `notfound`, `limit`, `server`, `bad` (11-32); `explain(err, what)` writes the sentence for a card (126-141); `asOf` pulls generated_at, freshness, source (144-155); dispatches `optic:reached` and `optic:v2-closed` (60-62).
- Controls: none. States: none of its own. Storage: A30.
- Risks seen in code:
  - R-API-1 (P2, b): `get()` has no abort signal and nothing in v2 can cancel a GET; pages and the palette rely on counters to ignore stale answers (`core/api.js:89-107`; `request()` supports `signal` only for writes, 39-42).
  - R-API-2 (P2, g): the cache is keyed by path alone and is emptied by `api.invalidate('/api/')` only at sign-in, sign-up and sign-out (`core/store.js:66, 70`; `pages/signin.js:81`); correctness for other transitions (revoke here, sign out everywhere, delete account) rests on the device-session reload (A27).
  - R-API-3 (P2, e): a 200 whose body is not JSON becomes `null` silently (`core/api.js:64-65`), and an error body that is not JSON becomes "Request failed" (67-68), so a proxy's HTML error page reads as empty data or a generic failure.
  - R-API-5 (P2, e): `explain()` is worded for reads: its timeout line is "<what> took too long to load. The data provider may be slow right now." and its default is "<what> did not load." (`core/api.js:130, 139`), so a failed write in Settings or on the watch buttons reads "The change took too long to load. The data provider may be slow right now." (`pages/settings.js:241`, `ui/company.js:53`, `app.js:270`).
  - R-API-4 (P2, f): a cached answer past its TTL is returned at once and refreshed in the background (`core/api.js:92-100`); callers that do not pass `onUpdate` (the palette, Milo's allowance) can show an old answer with no sign it is old.

### A29 Auth endpoints the front end calls — `app/auth/routes.py` (prefix `/api/auth`)
- Files: `app/auth/routes.py`, `app/auth/deps.py`, `app/auth/ratelimit.py:36-63`, `app/auth/config.py`.
- Purpose: the whole account surface. Cookies: `optic_session` (HttpOnly, `Secure` when hosted, `SameSite=Lax`, path `/`, 30 days slid on `/me`, or a browser-session cookie with a one-day server limit when "keep me signed in" is off) and `optic_csrf` (same but readable by script) (`app/auth/config.py:23-24, 29-44, 58-88`). `csrf_guard` passes a request with **no** session cookie, otherwise requires the `X-Optic-CSRF` header to equal the cookie (`app/auth/deps.py:126-147`). The front end sends the header on every request (`core/api.js:46`).
- Routes (the bare numbers in the first column are line numbers in `app/auth/routes.py`): 

| Method and path | Needs a session | CSRF | Rate limit (per address and per extra bucket) | Called by v2 | Notes |
|---|---|---|---|---|---|
| `GET /api/auth/providers` (`app/auth/routes.py:131`) | no | no | none | no | Same data is in `/me` |
| `GET /api/auth/me` (138) | optional | no | none | `core/store.js:47` | Returns user, `admin` boolean, `methods`, `preferences`, `subscription`, `session_id`, `csrf`, `providers`, `mail`, `password_policy`; sets the CSRF cookie when absent; slides the session; `Cache-Control: no-store` |
| `POST /api/auth/register` (168) | no | no | `register` 5 per hour (per address and per email) | `pages/signin.js:101` | 409 for a known address; signs in (long session whatever `remember` says) |
| `POST /api/auth/login` (213) | no | no | `login` 10 per 15 min (address and email) | `pages/signin.js:98` | Same time cost whether or not the account exists |
| `POST /api/auth/logout` (257) | no | `csrf_guard` | none | `core/store.js:70` | |
| `POST /api/auth/logout-all` (274) | yes | yes | none | `pages/settings.js:264` | |
| `POST /api/auth/forgot-password` (297) | no | no | `forgot` 5 per hour (address and email) | `pages/signin.js:107` | One answer whether or not the address exists; mail sent after the reply |
| `GET /api/auth/reset/check` (335) | no | no | none | `core/authlinks.js:47` | `token` up to 200 characters |
| `POST /api/auth/reset-password` (347) | no | no | `reset` 10 per hour (address only) | `pages/signin.js:113` | Single use; signs in |
| `POST /api/auth/verify-email` (393) | no | no | none | `core/authlinks.js:40` | Consumed by POST so a mail scanner's GET cannot spend it |
| `POST /api/auth/resend-verification` (408) | yes | yes | `verify_resend` 5 per hour (address, user) | `pages/settings.js:251` | |
| `PATCH /api/auth/profile` (425) | yes | yes | none | `pages/settings.js:293` | Names cut at 80; `avatar_url` must be http or https |
| `POST /api/auth/change-password` (449) | yes | yes | `password_change` 10 per hour | `pages/settings.js:299` | Signs out every other session and emails a notice |
| `GET /api/auth/sessions` (504) | yes | no | none | `pages/settings.js:210` | Own sessions with IP, user agent, label |
| `DELETE /api/auth/sessions/{id}` (524) | yes | yes | none | `pages/settings.js:280` | Scoped to the caller |
| `GET /api/auth/identities` (543) | yes | no | none | `pages/settings.js:210` | Also lists passkeys and methods |
| `DELETE /api/auth/identities/{provider}` (559) | yes | yes | none | `pages/settings.js:266` | Refuses the last way in |
| `GET /api/auth/passkeys` (591) | yes | no | none | no | |
| `POST /api/auth/passkeys/register/options` (600) | yes | yes | `passkey_challenge` 30 per 15 min | `core/passkey.js:12` | 503 when passkeys are off |
| `POST /api/auth/passkeys/register/verify` (611) | yes | yes | `passkey_verify` 20 per 15 min | `core/passkey.js:23` | |
| `POST /api/auth/passkeys/login/options` (637) | no | no | `passkey_challenge` | `core/passkey.js:36` | |
| `POST /api/auth/passkeys/login/verify` (646) | no | no | `passkey_verify` | `core/passkey.js:41` | Signs in |
| `PATCH /api/auth/passkeys/{id}` (663) | yes | yes | none | `pages/settings.js:306` | |
| `DELETE /api/auth/passkeys/{id}` (675) | yes | yes | none | `pages/settings.js:265` | |
| `GET /api/auth/preferences` (693) | yes | no | none | no | `time_zone`, `default_market`, `default_landing` |
| `PATCH /api/auth/preferences` (700) | yes | yes | none | no | No UI in v2 or classic writes it |
| `GET /api/auth/subscription` (708) | yes | no | none | no | Settings uses `/me` and `/api/billing/status` |
| `POST /api/auth/delete-account` (720) | yes | yes | none | `pages/settings.js:310` | Typed email, and password when one is set; cancels the subscription and deletes brokerage data first |
| `GET /api/auth/{provider}/start` (785) | only with `link=1` | no (GET) | `oauth_start` 30 per 15 min | `pages/signin.js:25-26`, `pages/settings.js:111` (navigation) | `google` or `apple`; stores state, nonce and PKCE verifier server-side; `next` up to 200 characters |
| `GET /api/auth/google/callback` (856) | no | no | `oauth_callback` 30 per 15 min | browser redirect | Signs in |
| `POST /api/auth/apple/callback` (899), `GET …/apple/callback` (913) | no | no | `oauth_callback` | browser redirect | Apple posts from its own domain, so no cookie rides with it |

- Other session-bound calls the shell and account pages make: `GET /api/billing/status` (optional session), `POST /api/billing/checkout` and `/portal` (session, CSRF), `POST /api/feedback` (session, CSRF, `feedback` 10 per hour), `/api/watchlists…`, `/api/saved-research…`, `/api/theses/adopt`, `/api/valuations/adopt` (session; writes need CSRF) (`app/billing.py:110-175`, `app/main.py:5794-5844`, `app/account.py`).
- Risks seen in code:
  - R-A29-1 (P1, g): the provider sign-in is not tied to the browser that started it. `state` is a row in the database, deleted on use, looked up by value at the callback; nothing the browser holds (a cookie, a header) is compared with it (`app/auth/store.py:468-492`, `app/auth/routes.py:808-815, 818-853`). The module says this is what prevents login CSRF (`app/auth/oauth.py:13-15`) and explains that a cookie cannot be used because Apple's callback is a cross-site POST (`app/auth/oauth.py:24-30`). What it does not stop: an attacker starts a flow in their own browser, completes the provider step, keeps the final redirect from being followed and sends the callback address (their `state` and `code`) to a signed-in or signed-out victim; the server then signs the **victim's browser into the attacker's account** (`_sign_in(response, …)`, `app/auth/routes.py:850-853`), and whatever the victim saves next (watchlists, saved research, a brokerage link, a problem report that names their address) lands in the attacker's account. The cookie policy text "no endpoint here changes state on GET" (`app/auth/config.py:73-81`) is not true of the two GET callbacks. Inferred from code, not exercised. A fix that fits both providers: at `/start` set a short-lived HttpOnly `SameSite=Lax` cookie holding a hash of `state` and require it at Google's GET callback; for Apple's POST use a `SameSite=None; Secure` cookie for that provider only, or sign `state` together with a per-browser value.
  - R-A29-2 (P2, c/d): four routes have no caller in v2 (`/providers`, `/passkeys` list, `/preferences` both methods, `/subscription`) while `/me` and `/identities` carry the same data; the preferences pair has no UI anywhere (R-ST-1).
  - R-A29-3 (P2, e): `verify-email` and `reset/check` have no limit entry (`app/auth/ratelimit.py:36-50`), `reset-password` has only the address bucket, and every address bucket is spoofable (A19 R-B-3).
  - R-A29-4 (P2, g): `GET /api/auth/me` returns the CSRF value in the body to any same-origin script (`app/auth/routes.py:143-146`), as the double-submit design intends; it is `no-store` (161) but the cookie is script-readable by design (`app/auth/deps.py:115-123`). Mentioned so a future change that adds script from another origin (the jsDelivr font stylesheets are CSS only today, `index.html:17-19`) is checked against it.

### A30 Storage key master table — `global`
- Scope: every Web Storage key and cookie this section's code touches, plus the page-owned keys found by grep so other sections can cross-check. "Personal" = shelved per person by `core/device.js` (A27). Lines are where the key is defined or used; r = reads, w = writes.

| Key | Store | Personal | Written by | Read by | Notes |
|---|---|---|---|---|---|
| `optic.theme` | localStorage | no | `core/prefs.js:37, 55` (Settings theme) | `index.html:28`, `core/prefs.js:47` | Shared with classic; absent = dark in v2 |
| `optic.ui.scale.v1` | localStorage | no | `core/prefs.js:78` | `index.html:32`, `core/prefs.js:72` | `compact`, `large`; absent = default |
| `optic.timezone` | localStorage | no | `core/prefs.js:87` | `core/prefs.js:81`, clock helpers | Not synced to the account |
| `optic.v2.motion.v1` | localStorage | no | `core/prefs.js:69` | `core/prefs.js:63` | `reduce` or absent |
| `optic.knowledge.v1`, `optic.knowledge.basic.v1`, `optic.knowledge.asked.v1` | localStorage | no | `core/prefs.js:113-124`; `pages/home.js:708-709`; `pages/workspace.js:1058, 1086, 1105`; classic `static/components/knowledge.js` | `core/prefs.js:110`; `pages/home.js:493, 632`; `ui/glossmark.js:30, 33`; `ui/sections.js:234`; sent to the server as `mode` (`ui/milo.js:838`) | The level ladder |
| `optic.rail.tight.v2` | localStorage | no | `ui/shell.js:16` | `ui/shell.js:15` | `1` or `0` |
| `optic.scout.motion.v1` | localStorage | no | `components/scout.js:361` | `components/scout.js:105` | `full`, `subtle`, `still` |
| `optic.chat.width.v2` (and legacy `optic.chat.width.v1`) | localStorage | no | `ui/milo.js:1123` (removed on double-click, 1149) | `ui/milo.js:1106-1107` | Written only when chosen |
| `optic.pulse.persona.v1` | localStorage | no | `ui/milo.js:179, 1327` | `ui/milo.js:177` | |
| `optic.milo.horizon.v1` | localStorage | no | `ui/milo.js:179, 1259` | `ui/milo.js:178` | |
| `optic.pulse.history.v1` | localStorage | yes | `ui/milo.js:135-136` | `ui/milo.js:132` | Milo conversations |
| `optic.research.v1` | localStorage | yes | `core/research.js:54, 68-69` | `core/research.js:13`, `ui/palette.js:113` | Guest saved questions, 40 |
| `optic.recent.v1` | localStorage | yes | `core/store.js:90, 97, 100` (callers: dossier, chart, options, investing, earnings, financials, news, workspace) | `core/store.js:76, 87` | Eight symbols |
| `optic.watchlists.v1`, `optic.chart.watch.v1` | localStorage | yes | `core/store.js:136-142`; mirrored for signed-in readers (147-151) | `core/store.js:116, 127`; `app.js:264` (adoption) | Guest lists and the flat classic mirror |
| `optic.watchlist.account.v1` | localStorage | yes | `core/store.js:159, 197` | `core/store.js:156` | Which account list is open (a bare string) |
| `optic.thesis.v1`, `optic.valuation.v1` | localStorage | yes | `pages/thesis.js:147`; `pages/valuation-scenarios.js:80`; `core/store.js:349` (delete) | `pages/thesis.js:143`; `pages/valuation-scenarios.js:33`; `app.js:274-275, 357` (adoption); `pages/brokerage.js:577` | |
| `optic.watches.v1` | localStorage | yes | `core/watches.js:18` | `core/watches.js:14`; `ui/company.js:94` | Guest alerts |
| `optic.chart.drawings.v2` (and `.v1`) | localStorage | yes | `pages/chart.js:98`; **`ui/milo.js:987`** | `pages/chart.js:90, 96`; `ui/milo.js:984` | Milo's "level" action writes here |
| `optic.chart.notes.v1`, `optic.chart.checks.v1`, `optic.chart.stopcheck.v1` | localStorage | yes | `pages/chart-widgets.js:79` | `pages/chart-widgets.js:75` | |
| `optic.paper.v1`, `optic.v2.paper.draft.v1`, `optic.v2.replay.v1`, `optic.v2.picker.v1` | localStorage | yes | `pages/paper.js:81, 338`; `pages/paper-replay.js:21`; `pages/options-picker.js:17, 101` | same files; `pages/home.js:364` | |
| `optic.roth.inputs`, `optic.dcf.v1`, `optic.screener.v1`, `optic.scan.recent.v1`, `optic.signals.v1`, `optic.snapshots.v1`, `optic.entry.budget.v1`, `optic.brokerage.scope.v1` | localStorage | yes | `pages/retirement.js:161`; `pages/dcf.js:35`; `pages/scan.js:38`; `pages/signals.js:30`; `pages/options.js:69`; `pages/brokerage.js:77` | same files; `pages/home.js:366` | Page-owned; see those entries |
| `optic.writeToken`, `optic.auth.passkeyOffered` | localStorage | yes | classic only | classic only | v2 only shelves them (`core/device.js:44-45`) |
| `optic.auth.passkeyMade` | localStorage | no | `core/passkey.js:22` | classic `static/auth.js:259-261` | Write-only in v2 |
| `optic.session.holder.v1` | localStorage | n/a | `core/device.js:91, 131, 140, 171, 188` | `core/device.js:163, 195` | Who owns the personal keys |
| `optic.session.shelf.<who>` | localStorage | n/a | `core/device.js:89` | `core/device.js:78, 92` | A person's keys while someone else is signed in |
| `optic.session.next` | sessionStorage | n/a | `core/device.js:143, 177` | `core/device.js:207-208` | Said once after a reload |
| `optic.v2.scroll.v1` | sessionStorage | n/a | `core/scrollmem.js:25` | `core/scrollmem.js:10` | 80 positions |
| `optic.v2.workspace.v1` | localStorage | **no** | `pages/workspace.js:194`; `core/homelink.js:13` | `pages/workspace.js:165`; `core/homelink.js:12` | Home layout, linked company (R-DS-1) |
| Page-owned, not personal | localStorage | no | `optic.v2.onboard.v1` (`pages/workspace.js:800, 1086`); `optic.options.group.v1` (`pages/options.js:431`); `optic.options.filters.v1` (`pages/options.js:61`); `optic.chart.colors.v1`, `optic.chart.legend.v1` (`pages/chart-chrome.js:31, 99`); `optic.chart.snap.v1`, `optic.v2.chart.v1` (`pages/chart.js:770, 86`); `optic.chart.backtest.v1`, `optic.chart.pairs.v1` (`pages/chart-widgets.js:79`); `optic.chart.fib.v2`, `.sr.v2`, `.vol.v2`, `optic.lt.interval`, `.mode`, `.range` (`pages/investing.js:47`); `optic.v2.financials.period.v1` (`pages/financials.js:414`); `optic.v2.watchlist.sort.v1` (`pages/watchlist.js:406`); `optic.panels.hidden.v1`, `optic.panels.open` (`ui/sections.js:24`); `optic.setups.view.v1`, `optic.setups.params.v1` (`pages/setups.js:33, 43`); `optic.brokerage.section.v1` (`pages/brokerage.js:31`) | each owner | Listed so other sections can confirm |
| `optic_session` cookie | cookie | n/a | server (`app/auth/routes.py:94`) | server only (HttpOnly) | |
| `optic_csrf` cookie | cookie | n/a | server (`app/auth/deps.py:115-123`) | `core/api.js:20-23, 46`; `ui/milo.js:835` | Script-readable by design |
| `optic_ui` cookie | cookie | n/a | `app.js:237` (to `classic`), classic footer (to `v2`) | `app/frontend.py:80-85` | One year, `SameSite=Lax`, no `Secure` |

### A31 Server-synced and device-only settings — `global`
- Purpose: what follows the person to another device and what does not.

| Setting | Where it lives | Written by (control → endpoint) | Read by | Notes |
|---|---|---|---|---|
| Name | server | Settings Name form → `PATCH /api/auth/profile` (`pages/settings.js:293`) | `/api/auth/me`, Account sheet | |
| Email, password, passkeys, connected sign-ins, sessions | server | Settings Security (A23) | `/api/auth/me`, `/identities`, `/sessions` | |
| Plan and billing | server (Stripe) | Settings Plan → `POST /api/billing/checkout`, `/portal` | `/api/auth/me` `subscription`, `/api/billing/status` | Billing may be off |
| Watchlists | server for accounts, browser for guests | store → `/api/watchlists…` | `core/store.js:163-180` | Guest lists adopted at sign-in (`app.js:264-271`) |
| Saved research | server for accounts, browser for guests | Milo "Save", action card → `POST /api/saved-research` | Saved research, palette | |
| Alerts (watches), theses, valuation scenarios and models | server for accounts | their pages (other sections) | | Adopted at sign-in (`app.js:274-275`) |
| `time_zone`, `default_market`, `default_landing` | server row per account | **nothing in v2 or classic** | **nothing in v2** | R-ST-1 |
| Theme, motion, text size, time zone, knowledge level | this browser | Settings (A23) and Milo's Level | `index.html`, `core/prefs.js` | Not synced; a new device starts at defaults |
| Milo persona, timeframe, width, Scout motion | this browser | Milo (A16) | Milo | Persona and timeframe are sent with each question |
| Milo conversations | this browser | Milo | Milo | Never uploaded except when a reader reports an answer |
| Rail collapsed, Home layout, chart view and the page-owned keys in A30 | this browser | their pages | their pages | |

---

# Part 5. Consolidated risk register for this section

Priority first, then the entry. Every line is a read of the code, not a test; "dup" marks one finding listed under two entries.

| ID | Pri | Kind | Where | One line |
|---|---|---|---|---|
| R-A29-1 (dup R-SI-1) | P1 | g | `app/auth/store.py:468-492`; `app/auth/routes.py:808-853` | Provider sign-in state is not bound to the browser that began it, so a callback link made by an attacker signs a victim into the attacker's account (login CSRF). |
| R-M1 (dup R-B-1) | P1 | g | `app/main.py:7776-7777, 7784-7787`; fix `2236205` not in branch | A reader's linked holdings can be attached or fetched for a question that is not about their portfolio (seen live 2026-10-27). |
| R-M2 | P1 | a | `app/ai.py:139-146, 3630-3635` | "Risk and process" persona is sold as "position size before direction" and told to lead with size and stop placement, against the base rule never to tell readers what to do with money. |
| R1 | P1 | b/d | `ui/shell.js:72`; `core/router.js:21-43` | The skip link changes the hash to `#main`, which the router opens as the Dossier for MAIN. |
| R4 | P1 | e | `app.js:146, 187` | "Try again" on a failed page is a same-address link; no `hashchange`, nothing retries. |
| R13 (dup R-DS) | P1 | e | `app.js:95-104`; `ui/drawer.js:49-51`; `ui/milo.js:132-146` | Dismissing "Keep what you made on this browser?" leaves personal keys unreadable; Milo history and drafts silently stop saving. |
| R-ST-5 | P1 | e | `pages/settings.js:301, 313`; `core/api.js:26, 131`; `app/auth/routes.py:464, 737` | A wrong current password or deletion password shows "Sign in to see the password." instead of saying the password is wrong. |
| R-M3 | P2 | c/f | `ui/milo.js:13, 1260, 1287`; `app/ai.py:3640-3652` | Starters and Deep research send and spend at once while the header says nothing is sent until Send; Deep research is the dearest call. |
| R-A14-1, R-PAL-7 | P2 | c | `ui/palette.js:57-59` vs `pages/home.js:668-681`, `pages/dossierstart.js:49-50` | Home and Dossier start open an index as a company Dossier; the palette opens the instrument page. |
| R-M4 | P2 | e | `ui/milo.js:867, 880-897` | A partial answer followed by an error is shown and saved as if complete. |
| R-M5 | P2 | b | `ui/milo.js:420-423, 1163-1169, 1266-1274` | A report form or "Report sent" follows the message index into another conversation. |
| R-M6 | P2 | b | `ui/milo.js:144` | A conversation is saved under the company open when the answer finished, not when it was asked. |
| R-A14-2 | P2 | b | `pages/home.js:668-681`; `pages/dossierstart.js:44-51` | Search submits set `location.hash` after an await with no check the reader is still there. |
| R-B-2 | P2 | g | `app/main.py:1033-1052, 7561-7569`; `app/ai.py:1244-1296` | Anonymous health and allowance answers expose model, credential source, key-refused state, commit, uptime and migrations. |
| R-B-3 | P2 | g | `app/auth/ratelimit.py:67-78, 120-139` | Per-address buckets trust the caller's `X-Forwarded-For`. |
| R-S-1 | P2 | g | `app/main.py:1835-1872` | `/api/logo/{symbol}` fetches and writes a marker for any symbol-shaped string, unmetered. |
| R-S-2 | P2 | g | `app/universe.py:291-306, 435` | `/api/search` re-reads `screen_ranking.json` on every keystroke, unmetered. |
| R-PAL-8 | P2 | g | `ui/palette.js:223`; `app/main.py:6442-6456, 5164-5187` | A list-shaped phrase can start the whole-universe ranking build from an anonymous GET. |
| R-B-4 (R-M9) | P2 | e | `app/main.py:7857, 7500-7505`; `ui/milo.js:366, 880-886` | The allowance is spent before the model call; a failure still costs one, and "used up" ignores the monthly cap. |
| R-B-5 | P2 | c | `app/main.py:7857, 7902` | The two spend routes skip `csrf_guard`; only `SameSite=Lax` protects them. |
| R-M7 | P2 | e | `ui/milo.js:1274` | Deleting a saved conversation has no confirmation or undo. |
| R-M8 | P2 | e | `ui/milo.js:836-839, 518` | Level, persona and timeframe are not sent with Deep research. |
| R-M10 | P2 | c | `ui/milo.js:512, 615, 1288` | `data-v2-milo-mode` names two controls. |
| R-M11 | P2 | e | `ui/milo.js:49-50, 379-381` | No stream timeout; a failed catalogue load hides Level silently. |
| R-M12 | P2 | a | `ui/milo.js:281, 556, 600` | Drafted wording presumes a trade frame ("entry zone", "swing long", "ranker pick that strike"). |
| R-M13 | P2 | g | `ui/milo.js:66-79, 540` | No AI-consent step; first Send transmits page figures, panel figures and files to the model provider. |
| R-M14 | P2 | e | `ui/milo.js:749-763` | Streaming redraws all settled paragraphs and charts each frame. |
| R-M15 | P2 | f | `app/ai.py:1121-1124, 1136-1139` | Public readers are told "your key" is fine, or that the deployment's key was refused. |
| R-M16 | P2 | c | `core/prefs.js:109-124` vs `static/components/knowledge.js` | The knowledge ladder is implemented twice. |
| R-SI-2 | P2 | d | `pages/signin.js:101`; `app/auth/routes.py:207` | "Keep me signed in" on Create account is ignored. |
| R-SI-3 | P2 | d | `pages/signin.js:58`; `core/passkey.js:34-47` | `webauthn` autocomplete token with no conditional passkey prompt. |
| R-SI-4 | P2 | c | `core/store.js:64-68` | `store.signIn` duplicates sign-in and has no caller. |
| R-SI-5 | P2 | e | `pages/signin.js:81`; `ui/milo.js:680` | Sign-in always returns to Home; nothing sends `next`. |
| R-SI-6 | P2 | g | `app/auth/routes.py:227-240, 189-195` | Sign-in and register answers reveal that an address has an account and how it signs in. |
| R-ST-1 | P2 | d/f | `app/auth/routes.py:693-705`; `pages/legalpages.js:27` | Server preference routes and the privacy text exist; no control writes or reads them. |
| R-ST-2 | P2 | f | `pages/settings.js:63`; `core/device.js:186-189` | Delete account does not say browser-held things stay. |
| R-ST-3 | P2 | g | `pages/settings.js:48`; `app/auth/routes.py:430-437` | Profile picture loads from any http or https host. |
| R-ST-4, R-API-2 | P2 | g | `pages/settings.js:264, 281, 308-313`; `core/store.js:66, 70` | Only sign-in, sign-up and sign-out empty the API cache; other transitions lean on the reload. |
| R-DS-1 | P2 | g | `core/device.js:17-46`; `pages/workspace.js:34` | Home layout and linked company are not shelved per person. |
| R-DS-2 | P2 | g | `core/device.js:44`; `static/app.js:1921` | The owner's write token is in localStorage and shelved copies persist. |
| R-DS-3 | P2 | e | `core/device.js:174, 216` | A failed swap leaves personal keys unreadable with no message. |
| R-AL-1 | P2 | g | `core/authlinks.js:29-33`; `pages/legalpages.js:80` | Reset and verify tokens reach the access log via the query string. |
| R-API-1 | P2 | b | `core/api.js:89-107` | GET cannot be cancelled. |
| R-API-3, R-API-4, R-API-5 | P2 | e/f | `core/api.js:64-68, 92-100, 130, 139` | Non-JSON 200s read as empty data; stale cached answers are returned unmarked; read-worded failure sentences are used for writes. |
| R-PAL-1, R-PAL-2, R-PAL-3, R-PAL-4, R-PAL-5, R-PAL-6 | P2 | c/e | `ui/palette.js:45, 85-86, 241, 263-268, 295, 336-351` | Recent-list fallback, missing places, Enter on an empty box, fixed `aria-expanded`, uncleared research cache, cached outage. |
| R-TA-1, R-TA-2, R-TA-3 | P2 | c | `pages/chart.js:298`, `pages/insiders.js:123`, `pages/paper.js:152`, `ui/typeahead.js:25` | Inconsistent opt-in, length caps and name matching. |
| R-S-3 | P2 | f | `ui/palette.js:181-182` | Directory `stale` and `reason` are ignored. |
| R2, R3, R5, R6, R7, R8, R9, R10, R11, R12, R14, R15, R16, R17, R18, R19, R20, R21, R22 | P2 | various | see each entry | Boot blank states, raw error text, dead migration scaffolding, dead rail fallback, hard-coded hint, unknown-auth chip, report context disclosure, stale footer sentence, toasts that vanish, Watch label rewrite, silent adoption failure. |
| R-LG-1 | P2 | f | `pages/legalpages.js:3-8` | Terms and Privacy are in force and unreviewed by a lawyer. |
| R-SV-1, R-AL-1 | P2 | e | `core/research.js:24, 37-48, 65` | Forget and Undo match by text and re-save through the plan limit. |

---

# Part 6. Not verified and limits of this audit

- No page was loaded and no request was made; layout, colour, motion and focus behaviour are not claimed. Only the CSS rules cited were read.
- The plan limits, the owner-only default for v2 and the hosted Starlette version are read from code and `requirements.txt`; production environment values (`OPTIC_V2_ACCESS`, `GUEST_AI_CALLS_PER_DAY`, `AI_CALLS_PER_HOUR`, provider keys) were not checked. Starlette 0.49.3 in `options-terminal/.venv` was read for the GZip behaviour; the deployed version is unknown.
- R-A29-1 and R-M1 are inferred from reading the OAuth and Milo routes; neither was exercised. The commit `2236205` was inspected with read-only `git` commands only.
- `ui/motion.js`, `ui/align.js`, `ui/term.js`, `core/glossary.js`, `core/poll.js` and `core/watches.js` were skimmed for their public effects only; the prompts in `app/ai.py` were read at the persona, horizon, error and spend-guard sections, not in full.
- The page-owned search boxes in A14 and the page-owned storage keys in A30 were located by grep and cited at their definition; their handlers belong to the entries for those pages.
- `static/v2/js/core/aiconsent.js` does not exist; no consent gate was found. `static/components/knowledge.js` (classic) was referenced, not audited.
