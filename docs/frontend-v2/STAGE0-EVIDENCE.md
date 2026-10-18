# Stage 0 evidence: the five blocking areas

**Date:** 2026-10-18.

**Where it ran:**
- **Branch:** `frontend-v2` in `~/Optic/wt-v2`.
- **Server:** the local server on :8075 (no AI key, background jobs off, sandbox brokerage).
- **Scratch servers:** the probe and rollback runs used their own copies of the local data.
- **Scripts and raw output:** in `~/Optic/work/v2-2026-10-17/stage0/`.

**What was not touched:**
- the live app;
- no deployment;
- no push.

**How each area was checked:** in a real browser (headless Chrome through the DevTools protocol) against the real server, unless a line says otherwise.

## 1. Milo essentials
| Requirement | Evidence | Limitation |
|---|---|---|
| Conversations and saved history | **History:** a v2 conversation lands in `optic.pulse.history.v1` (30 conversations × 60 messages, same caps as Classic). History reopens it. Classic reads it and can delete it, and v2 then drops it (round trip §7.9) | None |
| Rendered answers and sources | **Rendering:** a stubbed stream rendered markdown, `[[src]]` source links, `[[chart]]` (closes from `/api/take-chart`), up to two action cards, and "→" follow-ups. **Safety:** non-http links stay as text. **Unit test:** `test_milo_answers_render_sources_charts_actions_and_follow_ups` | Real model answers were not exercised locally (no key). The owner checks them in the preview |
| Correct context after navigation (the wrong-context bug) | **AAPL Overview, then MSFT Options:** the panel reads "MSFT Dossier, Options" and the payload has no AAPL field. A previous_ticker note is added only on a follow-up across symbols. **Leak guard:** any context object whose symbol differs from the route is dropped. **Reset:** `resetContext(route)` runs on every navigation | None found |
| Where a question was asked from | A block's Ask Milo (for example "Brokerage: VOO thesis") labels the context with that block and, on a page with no symbol, names the block's symbol; the top bar resets it to the whole page. Checked in the browser on Brokerage Overview and Events | The block's own figures are M5 |
| User settings | **Panel controls:** Level (5 modes), Analyst (from `/api/personas`) and Timeframe are sent as mode, persona and horizon. **Shared with Classic:** the Analyst chosen in either app is used by the other (§7.10) | None |
| Allowance and unavailable states | **Blocked states:** switched off, sign-in required, and allowance spent with the next reset time each disable Send and say why. **Allowance line:** shown from `/api/ai-allowance` | None |
| Cancellation and interrupted responses | **Stop:** the answer is kept as "[Stopped by the reader: incomplete]". **Cut stream:** kept as "[Cut off: incomplete]". **Failure before any text:** the exchange is removed and the question goes back in the box. **Offline and server-down:** each has its own message | None |
| Mobile keyboard | **Fit:** a `visualViewport` resize sets `--vvh` on the panel, so the box stays above the keyboard | Checked in phone emulation only. Real iOS Safari is on the owner's preview checklist |

## 2. Sign-in and account flows
| Flow | Evidence |
|---|---|
| Create account, verify link (`?verify=`) | Real local flow: the sign-up message is shown, and the verify link is consumed and scrubbed from the address |
| Forgot, then reset (`?reset=`) | **Reset:** the token is checked, then held in memory only. **Passwords:** the old one is refused (401) and the new one accepted (200). **Landing:** after reset the reader lands on the next page, not back on the reset form |
| Google or Apple callbacks | **Return:** `?auth=ok&next=` lands on next. **Errors:** `?auth_error=` names the provider and opens sign-in. **Server fix:** a sign-in started from `/v2/` now returns to `/v2/` (`app/auth/routes.py`, `_home`); `//evil.example` falls back to `/` (test in `tests/test_auth_providers.py`) |
| Passkeys | Registration and sign-in, through Chrome's virtual authenticator (`stage0/passkey_check.py`) |
| Recovery | **Covered:** sign out everywhere, the reset link, and the guest-data question on sign-in ("bring them in" now also brings guest theses and valuation scenarios, as Classic does) |
| Billing, brokerage and alert links | **Landing:** the billing success message, the brokerage callback flash (kept until the reader changes section) and the alert e-mail link `#/brokerage/events` all land correctly |

**Limitation:** Google and Apple are not configured locally, so only the return path was exercised; the real round trip with each provider is an owner check in the preview (L7).

## 3. Search and palette
**What was checked:**
- **Exact page names:** they win over a ticker guess ("scan" then Enter opens Scan).
- **Symbols:** a symbol shows its actions (Chart, News, Earnings, Investing, Compare) and its saved research.
- **Questions:** a typed question selects "Ask Milo", which drafts it in Milo.
- **Screen requests:** these match the named screens from `/api/scanners`, plus the Sector board.
- **Gated destinations:** the owner-only and brokerage entries follow the server's flags.

**Bug found and fixed in Stage 0:** a signed-in reader's saved research was fetched after the first paint and never drawn until the next keystroke. The palette now paints again when it arrives (round trip §7.5).

**Unit test:** `test_the_palette_reads_page_names_questions_tickers_and_screens`.

## 4. Legal notices and disclosures
**What is in v2:**
- **Footer and disclaimer:** Classic's text, unchanged (`core/legal.js`), on every page.
- **Page notices:** nine page types (Options, Investing, Retirement, Earnings, Portfolio, Paper Desk, Macro, Indices, Read).
- **Milo notice:** in the Milo panel.

**Checked:** notices are present on those pages and absent from Overview and Financials, as in Classic.

**Open launch requirements:** listed separately in LAUNCH-REQUIREMENTS.md (L1 to L11). Restored text is not proof of readiness.

## 5. App shell: links, versions, caching, and paid calls on load
| Item | Evidence |
|---|---|
| Feed and e-mail links | §2 (verify, reset, auth, billing, brokerage, alerts). Classic's own links now pass through `safeHref` (37 sites); v2's `html` template neutralises `javascript:`, `data:`, `vbscript:` and protocol-relative URLs in `href`/`src`/`action` (unit test `test_links_with_unsafe_schemes_are_neutralised`) |
| Version detection | `/api/build` carries v2's own stamp, so a v2-only change does not ask Classic tabs to reload, and the reverse. An open v2 tab checks on return and every 10 minutes, and offers Reload; it never reloads by itself. The same check carries a rollback (§10) |
| Caching | v2's HTML has an import map giving every module a content hash, plus modulepreload. Versioned addresses are `immutable`; everything else is `no-cache`. A warm v2 load revalidates nothing: 69 files from cache, 3 KB static transfer (§6). Test: `test_versioned_v2_assets_are_immutable_and_the_rest_revalidate` |
| App shell | Footer status from `/api/health`, session chip, offline bar, new-version bar, rail Collapse, Report a problem |
| **No paid model calls on load** | **Probe:** `paid_call_probe.py` ran the real app on :8077 with a fake key, so every page believed Milo was on (`/api/ai-allowance` said enabled). The Anthropic SDK was replaced with a recorder that logs and refuses every call. **v2:** all 40 views × desktop and phone = **80 page loads, 0 model calls** (corrected 2026-10-18: earlier copies said 45 views and 90 loads; the probe log shows 80; re-run on the preview code, again 0 in 80). The only SDK activity was free: client objects built by the status check, and the key check (`models.list`), which costs nothing. **Classic, same probe:** 27 pages, **3 paid calls on load** (Earnings brief, Read, Macro) when no cached copy existed. Classic is live and was not changed; recorded as L11 |

**Limitation:** the probe covers page loads and the default interactions in `v2_check.py`. It does not cover scheduled jobs (off locally), and it does not cover buttons that are labelled as model calls ("Write the read").

## 6. Load performance under realistic conditions (`load_perf.py`)
**How it was measured:**
- **Session:** signed-in demo account, against the local server.
- **Server caches:** warmed first, so the figures measure the frontend.
- **Runs:** two per cell; medians shown.
- **Phone profile:** 390×844, 150 ms RTT, 1.6 Mbps down, CPU slowed 4×.
- **Desktop profile:** 1440×900, 40 ms RTT, 10 Mbps.
- **Cold:** browser cache cleared.
- **Warm:** a fresh visit with the cache.

| Profile, page | v2 first paint | v2 content ready | v2 code downloaded | Classic first paint | Classic content ready | Classic code downloaded |
|---|---|---|---|---|---|---|
| Phone, Home, cold | 2.73 s | 4.03 s | 330 KB | 3.44 s | 8.05 s | 1,349 KB |
| Phone, Dossier, cold | 2.74 s | 4.25 s | 330 KB | 3.46 s | 7.16 s | 1,351 KB |
| Phone, Home, warm | 0.27 s | 1.23 s | 3 KB | 0.42 s | 1.36 s | 13 KB |
| Phone, Dossier, warm | 0.28 s | 1.76 s | 3 KB | 0.43 s | 0.72 s* | 13 KB |
| Desktop, Home, cold | 0.67 s | 1.69 s | 330 KB | 0.63 s | 1.66 s | 1,350 KB |
| Desktop, Dossier, cold | 0.68 s | 1.69 s | 330 KB | 0.62 s | 1.28 s* | 1,351 KB |
| Desktop, Home, warm | 0.10 s | 0.51 s | 3 KB | 0.14 s | 0.53 s | 13 KB |
| Desktop, Dossier, warm | 0.10 s | 1.07 s | 3 KB | 0.15 s | 0.29 s* | 13 KB |

**How "content ready" is defined:**
- **v2:** the page view is present, with no skeletons, and has text.
- **Classic:** no loading placeholders, and text present.

\* Classic's Dossier fills panels progressively without placeholders, so its "ready" fires before all its data is in. Its network-idle times are a fairer comparison: phone warm 2.46 s against v2's 1.69 s; desktop warm 0.65 s against v2's 1.03 s.

**Requests:**
- **v2 cold:** 85 requests, 73 of them module files fetched in parallel (preloaded).
- **Classic:** 32 requests, but a 2.6 MB script.

**Known costs:**
- **Phone first paint:** v2's cold phone first paint (2.7 s) is the module graph. Bundling would lower it; that is M8 work, not a blocker.
- **Desktop Dossier:** v2's warm desktop Dossier waits on `/api/ticker` before drawing its first section.

## 7. Data round trips between Classic and v2 (`roundtrip.py`, 61 checks, all pass)
**How it ran:**
- **Browser:** one browser, the same origin, both apps.
- **Writes:** through each app's own code. Classic uses its global functions; v2 uses its modules or page controls.
- **Reads:** what the other app renders or sends, plus the server or browser store underneath.

**Areas covered, both directions:**
1. **Watchlists:** create, rename, follow, remove, and the open list.
2. **Price alerts:** create, switch off and on, delete.
3. **Theses:** Classic Dossier and v2 Brokerage.
4. **Valuation scenarios:** including your own revenue, notes, history tags and clearing.
5. **Saved research.**
6. **Paper trades:** open in v2, close in Classic.
7. **Retirement inputs.**
8. **Chart drawings:** Classic-only kinds survive v2; a line drawn with the pointer in v2 is read by Classic.
9. **Milo history.**
10. **Preferences:** theme, text size, time zone, knowledge level, Analyst.
11. **Recent symbols.**
12. **Account isolation:**
    - with account B signed in, none of account A's paper trades, Milo conversations or drawings are live or on the page, in either app;
    - signing A back in, through the other app, restores them.

**Faults the round trips found, all fixed in Stage 0:**

| # | Fault | Fix |
|---|---|---|
| R1 | v2 parsed Classic's remembered open list (a bare id) as JSON, failed, and overwrote it with the first list | Read as a string (`core/store.js`) |
| R2 | A Brokerage thesis save (either app) wiped the Dossier's snapshot: the "what changed" baseline and the thesis check's conditions | Server keeps the stored snapshot when a save sends none (`app/account.py`, test `test_a_workspace_thesis_save_keeps_the_dossiers_snapshot`) |
| R4 | A thesis or valuation deleted in v2 came back: Classic re-adopted its browser copy on its next load | v2 deletes the browser copy too (`store.forgetLocalCopy`) |
| R5 | A v2 valuation re-save dropped your own revenue and share count, wrote `note: null` without `v: 1`, kept stale history tags, and deleted a scenario whose notes were not empty. v2 also pre-filled the years and required return, so it saved defaults | v2 now writes Classic's exact body. It shows the "Your own starting figures" boxes, uses Classic's empty rule, starts blank with placeholders, and fills the exit P/E from the company's median multiple, as Classic does (test `test_a_v2_valuation_save_keeps_what_the_classic_app_wrote`) |
| R6 | v2's "bring them in" did not bring guest theses or scenarios | It now adopts both (the server never overwrites) |
| R8 | A v2 alert check did not record what it found: no `/api/watches/seen` when signed in; no `last_evidence` or signal history as a guest | Ported from Classic's `checkWatchSymbol` |
| R10 | v2's Milo "draw this level" stored the time as a date string | Stored as milliseconds, like every other drawing |
| (new) | Signed in, v2 never kept the open list in `optic.chart.watch.v1`, which Classic's chart dock and alert builder read | v2 mirrors it |
| (new) | v2's guest saved-research list had no cap | Capped at 40, as Classic |

**Found but not changed (Classic, live):**
- **R3:** Classic's thesis-check save blanks the Brokerage "risks" and "watching for" fields.
- **R7:** a fresh Classic guest's first follow also saves four starter symbols.
- **Watchlist chips:** after a reload on its Watchlist page, Classic draws placeholder chips before the account loads and does not redraw them. Its state is right; the chips catch up on the next navigation. This was reproduced with Classic alone.
- **Legacy drawings:** `optic.chart.drawings.v1` is migrated only by Classic.

**Not tested in reverse:** saved research from v2 to Classic. v2 saves only through a Milo action card and has no list page (M5). The check is recorded as a gap, not a pass.

## 8 and 9. Branch review, capability matrix, migration
These are in their own files:
- BRANCH-REVIEW.md;
- CAPABILITY-MATRIX.md: 34 implemented and tested, 10 incomplete, 16 Classic-only groups;
- MIGRATION.md: milestones M1 to M9, each with acceptance checks.

## 10. Rollback rehearsal (`rollback_rehearsal.py`, 20 of 20)
**Setup:** a scratch server on :8079, restarted with each setting while two signed-in readers kept v2 tabs open.

**What passed:**
- **v2 as default:** "/" serves v2.
- **Default rolled back:** `OPTIC_DEFAULT_UI=classic`. An open v2 tab at "/" is told it moved back. "Open the classic app" lands on the same page (`/classic#/watchlist`). The reader is still signed in, KO (followed in v2) is in the list, the dark theme set in v2 is applied, and the Milo conversation is kept. A reader who chose v2 keeps it.
- **Access rolled back:** `OPTIC_V2_ACCESS=owner`. A non-owner's open v2 tab is told v2 is closed. They get Classic at "/" and at "/v2/", even with the v2 cookie. The owner still gets v2 and still sees KO.
- **No settings, as production is today:** "/" is Classic and "/v2/" is v2.
- **Restart time:** 2.1 to 2.6 s for each setting change.

## 11. Tests and audit
**Tests added in Stage 0:**
- `tests/test_frontend_switch.py`: 7 tests, including the rollback fields on `/api/build`;
- `tests/test_frontend_v2_stage0.py`: 4 tests, run in JavaScriptCore;
- one thesis-snapshot test in `tests/test_brokerage_workspace.py`;
- one test for the OAuth return root.

**Suite:** 6,202 passed, 1 skipped (was 6,189 before Stage 0). The first full run found 5 failures, all from Stage 0 changes:
- four tests pinned to the old exact strings (`esc(...)` now `safeHref(...)`, and `/api/build`'s new fields);
- one flagged a real leftover: the block label on Milo buttons was written but never read. It is now sent as `focus.asked_from` (§1).

**Audit:** `v2_check.py --audit` on 15 views (Home in three states, Dossier, Investing, Options, Chart, Alerts, Watchlist, Brokerage Events, Sign in, Settings for a member and a guest, Paper Desk, Retirement) × desktop and phone × light and dark: 60 captures, 0 faults (contrast, unnamed controls, small targets, heading order, duplicate ids, overflow).

## 12. Remaining limitations
- **Not exercised locally:** the real model, real Google and Apple, real iOS Safari, and the owner's real brokerage. Each is on the preview checklist.
- **Classic-only capabilities:** 16 groups remain, each scheduled in MIGRATION.md. Classic stays the bridge until they are migrated and verified.
- **Branches:** the five recommended for integration (BRANCH-REVIEW.md) are not merged. Each needs the owner's yes.

## Backend and Classic changes in this branch (disclosed for review)
- **`app/frontend.py`** (new): which app each reader gets, the v2 page with versioned assets, and cache headers.
- **`app/main.py`:**
  - routes `/`, `/classic`, `/v2/`;
  - immutable caching for versioned v2 assets;
  - `/api/build` adds `v2`, `ui` and `v2_open`;
  - `data-v2-available` on Classic's page.
- **`app/auth/routes.py`:** a provider sign-in returns to `/v2/` or `/classic` when it started there.
- **`app/account.py`:** a thesis save without a snapshot keeps the stored one.
- **Classic (`static/app.js`, `brokerage.js`, `valuation.js`, `index.html`):**
  - `safeHref` on every data-built `href`;
  - "Try the new design" in the footer, shown only when v2 is open to that reader.
