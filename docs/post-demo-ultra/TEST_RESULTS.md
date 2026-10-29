# Test results

Every entry gives the date and time (ET), the commit tested, the exact command or check script, and the
outcome as reported by the tool. Nothing here is summarised from memory. Working files (raw outputs, crawl
JSON, screenshots, scripts) are outside the public repository in
`~/Optic/work/post-demo-ultra-2026-10-29/`.

## Baseline (Phase 01), commit 9fa0f36 (origin/main, live)

### Tooling that exists in the repository

| Check the directive asks for | What the repository has | Result |
|---|---|---|
| Production build | None. No bundler or build step: `static/` is served as-is (CLAUDE.md). The deploy image is `Dockerfile` (python:3.12-slim); Docker is not installed on this machine, so the image was not built. | NOT TESTED (no build step; image build BLOCKED locally) |
| Type checker | None (no TypeScript, no mypy configuration). | not applicable |
| Linter | None configured (no ruff/flake8/eslint configuration). Ad-hoc substitute below. | ad-hoc only |
| Unit and integration tests | pytest suite in `tests/` (Python; client contracts read as text; some JS run under JavaScriptCore). | PASS, see below |
| Browser end-to-end tests | None in the repository. Earlier audits kept CDP check scripts outside it (`~/Optic/work/...`); this overhaul's copies are in `~/Optic/work/post-demo-ultra-2026-10-29/tools/`. | see crawl below |

### Commands and outcomes

| When (ET) | Command | Outcome |
|---|---|---|
| 2026-10-29 01:18:52 to 01:22:23 | `.venv/bin/python -m pytest -q -p no:cacheprovider` in `~/Optic/wt-ultra` | **7108 passed, 1 skipped, 6 warnings in 208.84 s**, exit 0. Warnings: urllib3 NotOpenSSLWarning (LibreSSL in the local Python 3.9), starlette per-request cookies deprecation (3, in tests/test_frontend_switch.py), pandas `'M'` FutureWarning (2, tests/test_valuation_inputs.py:212). The one skip is `tests/test_brokerage_exposure.py:586` ("reads EDGAR; set OPTIC_LIVE_EDGAR=1 to run"), a deliberate live-network test (confirmed with `pytest -rs tests/test_brokerage_exposure.py`). Raw: `baseline/pytest-baseline.txt`. |
| 2026-10-29 01:3x | `node --check` on every `.js` under `static/` (node v26.12.0) | **122 files, 0 failed** |
| 2026-10-29 01:3x | `.venv/bin/python -m compileall -q app tests` | ok |
| 2026-10-29 01:3x | `ruff 0.17.3 check --no-cache --select F --target-version py39 app` (pyflakes rules, run from a throwaway venv in the session scratchpad; not a repository tool) | **59 findings: 45 F401 unused import, 13 F841 unused local, 1 F811 redefinition; 0 undefined names.** Raw: `baseline/ruff-F-app.txt`. Logged as BUG-017, BUG-018. |
| 2026-10-29 01:2x | FastAPI route table read from `app.main.app.routes` | 241 routes, 231 under `/api`, 2 streaming (`/api/chat`, `/api/research`). Raw: `baseline/api-routes.json`, guards per handler in `baseline/route-guards.json`. |

### Environment differences worth knowing

- Local tests run on the shared venv's Python 3.9 (LibreSSL 2.8.3); production runs Python 3.12 in Docker. The
  suite cannot catch a 3.12-only failure.
- The local server (`optic-ultra`, :8250) uses a copy of the investor-audit data (`~/Optic/ultra-data`), the
  sandbox brokerage provider, background jobs off, and a stand-in for the Anthropic API on :8251. No real model
  key is used and nothing can be spent.

### Milo pipeline probe (stand-in model, so Optic's own pipeline only, never the real model's latency)

`tools/milo_probe.py`: signs in as the demo account, posts one question to `/api/chat`, times the SSE stream.

| Question, context | Headers (first byte) | First event | First text | Done | Events |
|---|---|---|---|---|---|
| "What happened to NVDA today?", NVDA (caches warm from the crawl) | 0.307 s | 0.322 s | 0.406 s | 0.794 s | assumed 1, status 1, retrieved 1, delta 10, done 1 |
| "What happened to KO today?", KO (cold) | 2.200 s | 2.213 s | 2.254 s | 2.626 s | same |
| "Explain this chart.", PEP (cold) | 1.466 s | 1.475 s | 1.535 s | 1.918 s | same |

Reading: the server streams real deltas, but nothing at all reaches the browser until the whole context is
built (`app/main.py` `/api/chat` gathers research, framework, chart levels and the linked portfolio before it
returns the `StreamingResponse`); cold, that is 1.5 to 2.2 s here before the model is even asked.

### Rendered crawl (Phase 01), 2026-10-29 01:22 to 01:47 ET, local server :8250 at 9fa0f36

Tool: `tools/crawl.py` (headless Chrome over CDP; kit from the 2026-10-27 audit plus a rendered-inventory probe),
`tools/classic_crawl.py`, `tools/summarize.py`. Raw: `crawl1/`.

| Pass | Loads | Script exceptions / console errors | Sideways overflow | Error states shown | Placeholder text | Notes |
|---|---|---|---|---|---|---|
| v2 guest, 56 routes x 1440/1280/768/390 | 224 | 0 (only the expected 404s on `#/ZZZZQ`) | 0 | 0 | 0 | `#/earnings?week=1` kept 7 skeletons past the 30 s cap on a cold server (BUG-016); `/api/dispersion`, `/api/implied-correlation`, `/api/stockmap` slow on first build |
| v2 signed in (demo account, owner on this server), same 56 x 4 | 224 | 0 | 0 | 1: `#/SPY/options` at 768, "The contracts did not load" after a Yahoo 503, a graceful state | 0 | `/api/brokerage/status` requested twice on every brokerage page |
| Classic guest, 26 views x 1440/390 | 52 | 0 | 0 | 0 | 0 | logos from unavatar.io blocked by ORB on `#/earnings` (BUG-028); `#/explore` empty at 1440 only (BUG-029) |
| Server log during all of the above | | 0 tracebacks, 0 HTTP 500 | | | | 6 Yahoo refusals (`401 Invalid Crumb`, `401 User is unable to access this feature`), all handled |

Density per route (guest, 1440): highest visible word counts Analysts 2,648, NVDA Financials 2,066, NVDA Investing 2,021
(268 controls), Insiders 1,620, Privacy 1,465, NVDA Overview 1,390 (177 controls), BRK-B 1,357, Retirement 1,322,
Home 1,135 (187 controls), NVDA Earnings 1,085, Read 1,033. Small touch targets flagged by the audit script at 390:
NVDA Investing 30, NVDA Overview 30, BRK-B 24, BTC 12. Contrast and unnamed-control counts were 0 on every load
(audit.js rules; Phase 10 re-measures with WCAG 2.2 tooling).

## Phase 02 (advice policy and legal consistency), 2026-10-29, working tree on c6724ff

All runs: `.venv/bin/python -m pytest -q -p no:cacheprovider -rf` in `~/Optic/wt-ultra`; raw output in
`phase02/pytest-run*.txt`. Times are when each run's output file was last written (ET).

| Run | Ended | Outcome | What failed, and what was done |
|---|---|---|---|
| 1 | 05:22 | 9 failed, 7120 passed, 1 skipped | Tests pinning the old wording (take format, contract budget and picker, pitch audit, Milo prompt block, trade journal, beginner pass, Classic port, shortlist): each read and updated to the new wording |
| 2 | 05:41 | 2 failed, 7203 passed, 1 skipped | The glossary must match Classic's word for word (Classic's stop-loss entry updated too); Milo's saved conversation now carries the policy notes (test updated, still no file data) |
| 3 | 05:56 | 3 failed, 7205 passed, 1 skipped | Classic panel names and column definitions renamed in this phase (definitions table, panel lists and two tests updated) |
| 4 | 06:17 | 2 failed, 7212 passed, 1 skipped | The scan go-ahead key had to be classed (a this-tab, read-once key, like `optic.reload.place`); the zones wording test |
| 5 | 06:23 | **7214 passed, 1 skipped, 0 failed** | |
| 6 | 06:35 | **7369 passed, 1 skipped, 0 failed** | With the rebuilt output check and set A as regression cases |
| 7 (final) | 06:55 | **7471 passed, 1 skipped, 0 failed** | Version 4 of the output check, sets A and B as regression cases, the unsupported-claims rule |

Other checks:

| Check | Outcome | Raw |
|---|---|---|
| `node --check` on the 26 JS files changed in this phase | 26 passed, 0 failed | |
| `python -m compileall -q app tests` | ok | |
| Mutation checks in a scratch copy (5 mutations of the policy wiring and the notice copy) | each failed at least one test | `phase02/mutation-checks.txt` |
| Chat route with the stand-in model: "Tell me exactly what stock to buy." | `notice` before any `delta`; categories `pick_for_me` | `phase02/milo/declined.jsonl` |
| Chat route with the stand-in model: an answer containing "You should buy it before the report." | the sentence never streamed; `amend` before `done`, removed 1, rule `trade_instruction` | `phase02/milo/advise2.jsonl` |
| Milo panel, signed in, headless Chrome (`tools/milo_policy_ui.py`) | policy line above the answer; removal note under it; both restored after reload from history; 0 page errors | `phase02/milo-ui/` |
| Crawl, signed in, 56 v2 routes at 1440 (`tools/crawl.py`) | 0 script errors; only the deliberate `#/ZZZZQ` 404s | `phase02/crawl/` |
| Notice on each research route (browser pane) | the right `.legal-area` text on all 20 routes | |
| `#/scan?q=` without a press (browser pane) | the words fill the box; no `/api/screener/ask` request | |
| `#/scan?q=` after Milo's card (flag set) | the scan ran ("12 of 746 ranked names match"); the flag was consumed | |
| Earnings brief stance label (a test brief planted in the local data copy, removed after) | v2 "The evidence leans positive"; Classic "Evidence leans positive" | |
| Output check on set A (80, written by a separate agent that never saw the code), version 2 | advice 10 of 40 caught; research 2 of 40 wrongly flagged | `phase02/heldout-result.json` |
| Output check on set B (100, another agent, saw neither the code nor set A), version 3 | advice 27 of 50 caught; research 1 of 50 wrongly flagged | `phase02/heldout-result-b.json` |
| Version 4 on sets A and B (seen, regression) | 90 of 90; 0 of 90 | `tests/test_ai_policy.py` |
| Version 4 on stored real text (544 sentences) and Optic's own research text (2,361 sentences, 4 tickers) | 0 flagged on either, after fixing the 1 and 5 false alarms found | |
| Output check speed | 0.14 ms per sentence; 4.3 ms for a 30-sentence answer | |
| The seven named prompts with the real model | NOT TESTED: the key is refused (BL-01) | |


## Phase 03 (search, ticker state, navigation), 2026-10-29, working tree on 6f2e814

### Interaction scenarios (headless Chrome, `tools/phase03_scenarios.py`, raw `phase03/phase03-all.json`)

The search provider was slowed or failed by pausing `/api/search` (or one company's `/api/ticker` or
`/api/take-chart`) in the browser tab only, never on the server. Run 1 found two failures (S5, S12), both real:
see "Found by the scenarios" below. After the fixes every scenario passed.

| ID | Scenario | Result |
|---|---|---|
| S1 | First visit: Home shows SPY | PASS |
| S2 | No "Follows <ticker>" on Home | PASS |
| S3 | Opening AMD then Home keeps SPY | PASS |
| S4 | An explicit choice (a name typed) is used, kept on reload; a bad one is said | PASS |
| S5 | 20 sequential ticker changes through the search | PASS |
| S6 | 10 rapid ticker changes, twice: the page shows only the last one | PASS |
| S7 | 10 invalid or unsupported searches get feedback; an invalid address says so | PASS |
| S8 | 10 direct-link, back, forward and refresh sequences | PASS |
| S9 | Keyboard only: / opens, arrows move, Escape closes, Enter opens | PASS |
| S10 | Enter on an empty search opens nothing | PASS |
| S11 | Slow search (2.5 s): typing on and pressing Enter opens what was typed last | PASS |
| S12 | Search provider failing (503): said plainly; a typed symbol still opens; a name opens the search | PASS |
| S13 | Dossier start: names, cases, a share class and an index each open the right page; no match opens the search | PASS |
| S14 | A slow answer does not move a reader who has gone elsewhere | PASS |
| S15 | Skip to content moves focus, not the address | PASS |
| S16 | The sidebar marks the current section | PASS |
| S17 | Home's sector-board link goes to Macro | PASS |
| S18 | Phone width: search opens and selects; no sideways overflow | PASS |
| S19 | Signed out and signed in: an owner page refuses a guest and opens for the owner; a Dossier opens either way | PASS |
| S20 | Clicking a result opens it | PASS |
| S21 | Clearing the search returns the empty list and throws nothing | PASS |
| S22 | A suggestion list draws above the page and a pick fills the box | PASS |
| S23 | An empty Dossier search stays put and puts focus in the box | PASS |
| S24 | Sidebar: Dossier opens the start page until a company is opened, then that company; Markets reaches Macro | PASS |
| S25 | Phone bar: Markets (its first page, Read, on a fresh visit), Watchlist and Home each open their page | PASS |
| S26 | Printable sheet: a slow answer for the sheet opened first never fills the next one | PASS |
| S27 | Home: picking another company while a panel loads, the late answer for the first never draws | PASS |

### The sixteen failure modes (directive 03, section 1)

| Failure mode | What was found | Evidence |
|---|---|---|
| Input not accepting text | Not reproduced in any box | S4, S5, S9, S13, S22 |
| Results failing to load | A failed answer was cached for 5 minutes (R-PAL-6): no longer cached | S12; `core/api.js` `keep` |
| Incorrect symbol resolution | With search down, a page whose search words contained the letters took Enter ("ko" opened Scan, "dis" Explore, "spy" Indices); pages now match by the start of a word and a symbol-shaped word keeps Enter. Home and the Dossier start opened an index as a company Dossier: now one resolver | S5, S12, S13 |
| Results too slow | Server answers in about 25 ms; locally a search typed while a cold Dossier loads waited 3.25 s for a free browser connection (HTTP/1.1, six per host). Production is HTTP/2 (checked 2026-10-29), which shares one connection | measured in the browser pane |
| Input losing focus | Not reproduced; the typeahead keeps focus on a pick | S9, S22 |
| Submitting twice | Not reproduced: one navigation per Enter in 20 changes | S5 |
| Enter failing | Enter on an empty box opened the first row (R-PAL-3): now opens nothing | S10 |
| Clicking a result doing nothing | Not reproduced | S20 |
| Results disappearing | Not reproduced | S9, S11 |
| Dropdown behind other elements | Not reproduced: the list is the topmost element at its own position | S22 |
| Closing before selection | Not reproduced | S20, S22 |
| State resetting on navigation | The palette closes on navigation by design; nothing else resets | S8 |
| Selection not updating downstream data | Not reproduced; Home's box now takes a name too | S4, S5, S6 |
| Failure after refresh | Not reproduced | S8 |
| Mobile | Not reproduced at 390 px; no sideways overflow | S18, S25 |
| Stale responses overwriting newer ones | Palette and typeahead already dropped them; found and fixed on the printable sheet (BUG-066), the Chart's intraday levels, Home panels (BUG-040), Macro, Indices and Read | S6, S11, S26, S27 |

### Suite

| Run | Outcome |
|---|---|
| After the main Phase 03 changes | **7486 passed, 1 skipped, 0 failed** (`phase03/pytest-run1.txt`) |

## Phase 04 (radical simplicity), 2026-10-29, working tree on 2f6a548

Raw results under `~/Optic/work/post-demo-ultra-2026-10-29/phase04/`. All runs are guest in a fresh headless Chrome
152 profile on live delayed data, Thursday 2026-10-29 during the regular session, unless marked.

### Density (`tools/density.py`; SIMPLICITY_AUDIT.md sections 2 and 10)

| Run | Server | Sizes | Routes | Outcome |
|---|---|---|---|---|
| Before (first try) | 2f6a548 worktree, :8252 | 1440, 390 | 29 | Superseded: the probe counted the contents of closed folds (D-022); kept as `superseded-before-rectvis` |
| Before | 2f6a548 worktree, :8252 | 1440, 390 | 29 | `before-2f6a548/` |
| After (final code) | Phase 04 tree, :8250 | 1440, 1024, 768, 390 | 29 | `after/`; no errors; overflow 0 and overlapping text 0 at every size |
| Secondary, before | 2f6a548 worktree, :8252 | 1440, 390 | 13 | `before-secondary/` |
| Secondary, after | Phase 04 tree, :8250 | 1440, 1024, 768, 390 | 13 | `after-secondary/`; no errors; overflow 0 and overlapping text 0 at every size |
| Home again | Phase 04 tree, :8250 | 1440, 1024, 768, 390 | 1 | `after-home-final/`, folded into `after/`: the first-visit card gained its one-line description after the main run |

| Route, 1440 | Visible words | Controls | Cards | Page height |
|---|---|---|---|---|
| Home | 1,872 → 672 | 186 → 71 | 12 → 5 | 3,427 → 2,149 px |
| Analysts | 2,927 → 701 | 226 → 67 | 1 | 14,629 → 3,729 px |
| Explore | 1,255 → 619 | 68 → 50 | 8 | 3,776 → 2,678 px |
| Retirement | 1,631 → 1,171 | 33 → 22 | 18 | 5,026 → 3,903 px |
| Home, 390 | 390 → 278 | 58 → 37 | 13 → 6 | 3,728 → 2,632 px |

The other routes moved by under 30 words, and the time lines account for most of that. On the secondary routes, `#/workspace` follows Home (1,881 → 678 words) and the instruments gained their time line (+8 words). The rest are unchanged or within data noise (BRK.B and BTC −26 words, from one headline). The Dossier tabs are unchanged in load
(Phase 06).

### Dead clicks (`tools/deadclicks.py`, corrected probe; `dead-final/`)

Each visible control on the route is pressed with a real mouse event, then the run checks for a DOM change, a route
change, a request, a focus move or a state attribute flipping. Controls that destroy, send or sign out are skipped,
never pressed.

| Run | Routes | Presses that answered | Dead controls | Notes |
|---|---|---|---|---|
| Guest, 1440 | 21 changed or reported routes | 559 | 0 | 9 presses of the page's own current tab (Options on Options, and so on), which have nothing to do |
| Guest, 390 | 8 | 236 | 0 | |
| Signed in, 1440 | Home, `#/workspace`, Settings | 103 | 0 | "Update panels", Phase 01's one signed-in dead control, now answers. Save, Sign out, Revoke, Delete and Report were skipped by design |

### Phase 03 scenarios, run again on the Phase 04 tree (`phase03-regression/`)

`tools/phase03_scenarios.py` against :8250 after every Phase 04 change: **27 of 27 PASS**. That covers the SPY default,
no "Follows", 20 sequential and 10 rapid ticker changes, invalid input, history, keyboard only, a slow and a failing
search, the Dossier start, the sidebar and phone bar, the printable sheet, and late answers. Phase 04's changes to
Home's panel set and the first-visit card did not move any of them.

### Browser checks (the browser pane, :8250)

| Check | Result |
|---|---|
| First visit: the card shows "Not now" and one set of Follow buttons; Follow Apple turns it to "Done"; Done removes the card | PASS |
| A Simple fold the reader opens stays open after the page is rebuilt, and one they close stays closed | PASS |
| The time lines render on Indices, Explore (two), Macro, Compare, Instrument and the fund boards; no script errors | PASS |
| Indices names the last finished week ("through Oct 23"), not the current week's Friday | PASS (after the fix) |
| The Overview's next steps show five line icons and no text arrows | PASS |
| `/api/options/NVDA/research` grades read Liquid 9, Fair 23, Thin 2, Too wide to trade 13 | PASS |
| `/api/market` stance reads "The market score's inputs lean mildly toward risk ..." | PASS |
| Phone 375: the Dossier's ⋯ menu shows six items, and each answers. Copy ticker closes the menu and says the browser did not allow copying (a scripted press); Show on Home goes Home and says so, and the quote panel shows NVDA; Export research sheet opens `#/NVDA/sheet` | PASS |
| Phone 375: the chart's Line and Area sit in the chart's style menu, and each switches the style | PASS |
| Phone 375: Scan's "10% pull back after 20% rally" sits in a closed fold. Opened and pressed, it fills the box and runs the screen | PASS |
| Analysts: 40 rows and "Show all 200"; the press shows all 200 and moves focus to row 41; a sort keeps every row | PASS |
| Contrast of the changed elements, light (ivory) and dark (charcoal): time lines 7.1 and 8.3:1, fold summaries 6.5 and 10.9:1, rating words 17.0 and 16.0:1, next-step labels 7.1 and 8.3:1, heatmap tile text at least 11.2 (light) and 9.2 (dark) at full tint | PASS (AA is 4.5:1) |

### Found by Phase 04's own checks

- The density and dead-click tools counted folded content as visible (D-022), and were fixed before any figure was
  reported. Phase 01's 27 guest dead clicks at 1440 break down as follows:
  - **Real, 7, all fixed:** five Compare chips, the chart watchlist's empty Add and "Update panels".
  - **SPY, 11:** confirmed inside the closed Advanced research fold (the key-figure terms, "5 sources" and "How this
    works").
  - **The other 9:** BTC's terms and fold, the terms on NVDA's Options and News, and Earnings week's "Consensus". The
    corrected re-run (`dead-after/`) reports none of them, so each was either not visible or answered its press.
    The fold cause is inferred for these, not confirmed control by control.
- The Indices time line first named a future day (the current week's bar carries its Friday's date). Fixed.
- Home's first screen offered two sets of Follow buttons (BUG-079). Fixed.
- Phase 03 had pinned, and recorded as live, a search box in an unrouted Home page (BUG-082). Corrected.

### Suite

| Run | Outcome |
|---|---|
| The final Phase 04 tree, after every change | **7506 passed, 1 skipped, 0 failed** in 229 s (`phase04/pytest-full.txt`) |
| Phase 04's own tests | `tests/test_v2_density.py` 8 and `tests/test_v2_simplicity.py` 11, plus the design-standard test for "Density and times"; all pass |


## Phase 05 (knowledge-level slider), 2026-10-29, working tree on b07e181

Raw results are under `~/Optic/work/post-demo-ultra-2026-10-29/phase05/`. Browser runs use headless Chrome 152 against
the local server (:8250) on live delayed data, Thursday 2026-10-29 in the regular session. Signed-in runs use the local
demo account, and its level is put back to Advanced afterwards. Brokerage runs link the local sandbox brokerage
(synthetic holdings, no credentials) and unlink it afterwards. Milo, deep research and the briefing are answered by
the stand-in model (`tools/milo_standin_ultra.py`), so these runs check what Optic sends and shows, not a real model's
words. The five-level answers come from the proxy run below.

### Browser checks (`tools/phase05_checks.py`, `phase05_checks2.py`, `phase05_brokerage_line.py`, `phase05_classic_research.py`)

| Check | Result |
|---|---|
| L1 One page's terms at each level (`#/NVDA/options`): New to Markets 25 marks, 19 with their definition in the sentence and the 6 in tables or figure labels marked only; Beginner, Intermediate, Advanced 25 marks and no definitions in place; Expert none | PASS |
| L2 The Settings slider by keyboard: named "Explain things for"; Right twice from Intermediate reaches Expert, and `aria-valuetext` and the label follow | PASS |
| L3 The level survives a refresh | PASS |
| L4 A second tab follows a change made in the first | PASS |
| L5 An id from before Phase 05 (`professional`) reads as Expert and is rewritten once | PASS |
| L6 Home's first-visit card asks "How should Optic speak to you?" with the slider; Left from Intermediate sets Beginner | PASS |
| L7 A shared text (an Index Read) at Beginner offers "Explain it for Beginner"; the press drafts the question with the text in Milo's box and sends nothing (0 requests) | PASS |
| L8 Phone 390: the slider 332 by 44 px, its level above it, no sideways scroll | PASS |
| L9 Signed in: a change is saved to the account; another device's older level in this browser is replaced by the account's at the next load | PASS |
| L10 Milo: an answer keeps the level it was asked at; after a change, a note says earlier answers stay as written and "Ask again for Expert" drafts the question without sending it | PASS |
| L11 The request Milo sends carries the reader's level block (stand-in log) | PASS |
| L12 Touch, phone 390 with touch emulation: a drag from the middle to the right end sets Expert (the label previews Advanced on the way and nothing is stored until release); a tap at the left end sets New to Markets | PASS |
| L13 The three sliders (Settings, Home's card, Milo's Response settings) at 1440, 1024, 768, 390 and 375 by 549: no part overlaps another or leaves the screen, no sideways scroll, 44 px tall on touch screens | PASS |
| L14 Classic signed in: Classic takes the account's level at load, a pick in Classic's question is saved to the account, and v2 shows it | PASS |
| L15 The Chart page's study readings (Keltner, ADX, MFI on): New to Markets defines ADX and money flow index in the sentence; Intermediate marks three terms; Expert marks none | PASS |
| L16 The written portfolio briefing (sandbox): asked at Beginner, the request carries the Beginner block and the answer is labelled `beginner` | PASS |
| L17 The Chart's Learn panel: choosing ADX shows its definition and drafts "Explain ADX: what it measures, why someone would use it, and what it cannot tell me." in Milo's box; nothing sent | PASS |
| Brokerage, v2: a write-up says "Worded for Beginner." on the first paint; at Expert the page says "An earlier write-up (just now) was worded for Beginner; this one would be for Expert." and offers Write it up | PASS |
| Brokerage, Classic: the same two lines, from the same kept write-up | PASS |
| Classic's Deep research at Beginner: the request carries the Beginner block (BUG-089) | PASS |
| Home's Desk at Beginner and Expert: "Worded for Intermediate readers. Explain it for X" at the line's size; nothing at Intermediate | PASS |
| A signed-in save that fails (the account's PATCH made to fail in the page): the level stays in this browser and the toast says "Kept in this browser. Your account did not save it; Optic will try again on your next visit."; at the next load, the account unchanged, the browser's level is sent up and kept (`tools/phase05_failed_save.py`) | PASS |

### Five levels on one question (the proxy run; DECISIONS D-034)

One question on one fixed context, a test fixture rather than market data: "Is NVDA expensive at a P/E of 31.2, and
what is the options market pricing for its next report?"
- **Quote:** price 214.01, the day's move -0.64%, quotes delayed 15 minutes.
- **Valuation:** trailing P/E 31.2, forward 27.4.
- **Options:** the Nov 27 expiry, 29 days out, at-the-money IV 41.1%, implied move 9.16%.
- **Calendar:** the report on Nov 17.
- **Source:** Yahoo Finance.

**How the answers were made.**
- Optic built its own Milo request at each level (`tools/phase05_proxy_build.py`, `phase05/proxy/request-<level>.json`).
  The five are identical apart from the level block, about 51,000 characters of system prompt each.
- Each request went to a separate Sonnet 5.5 agent (Milo's production model) under a neutral file name, `blind-a` to
  `blind-e` (the mapping is in `blind-map.json`).
- Each agent was asked to answer as the model receiving the request. Milo's tools were not available, so answers came
  from the context alone.
- The answers were measured by `tools/phase05_proxy_metrics.py` (`metrics.json`).
- The run used about 0.92 million agent tokens of the session's plan and no API credit.

| Level | Words | Sentences | Words per sentence | Flesch reading ease | Words of 3+ syllables | Glossary terms used | Explained where used |
|---|---|---|---|---|---|---|---|
| New to Markets | 340 | 27 | 12.6 | 81.8 | 6.5% | 3 | 3 |
| Beginner | 323 | 23 | 14.0 | 72.4 | 8.4% | 3 | 2 |
| Intermediate | 303 | 18 | 16.8 | 68.0 | 9.9% | 4 | 0 |
| Advanced | 324 | 21 | 15.4 | 69.0 | 9.9% | 4 | 0 |
| Expert | 293 | 22 | 13.3 | 69.2 | 8.5% | 5 | 0 |

| Check, all five answers | Result |
|---|---|
| Figures outside the fixture and its simple derivations (the 14% the two multiples imply, the implied move as $19.60, the 11:00 ET capture time) | None |
| Says the quotes are delayed; calls the forward P/E an estimate; gives the implied move no direction; puts the report before the expiry | Yes, all five |
| Names the source | Yes, all five |
| Optic's whole-answer advice check (`ai_policy.check_output`) | 0 findings in four answers. 1 at Advanced: "I'd lean toward 'expensive' if $NVDA's own history puts today's multiple near the top of its range". This is a conditional valuation judgment, not a trade instruction, so it is a false positive of the check's "I'd lean toward" pattern (BUG-092) |

What differs, from reading the five answers:
- **New to Markets** defines each term where it uses it ("price-to-earnings ratio: what you pay for each $1 of profit
  from the last 12 months"). It makes one comparison outside markets ("like paying $31.20 for a shop that earns $1 a
  year") and says why the reading matters to someone holding the stock.
- **Beginner** uses the standard names and explains each in a sentence ("The price-to-earnings ratio (P/E) is the share
  price divided by earnings per share"), one idea to a sentence. Both lower levels leave out the implied-volatility
  figure: they select fewer figures but alter none.
- **Intermediate** uses ordinary financial terms with brief context: trailing and forward earnings, at-the-money
  implied volatility. It derives the 14% earnings growth the two multiples imply.
- **Advanced** uses professional terms without definitions. It adds the base rate (past post-report moves) and what
  would change the read.
- **Expert** is the densest. It gives the derived figures (1.14, about 14%, the implied move as $19.60 either way),
  says what argues against the read and what would change it, and defines nothing.

**Reading.** On this model and question, the five levels change the vocabulary and the depth and keep the same figures,
caveats and sources. No answer gives personal advice. The two lower levels separate clearly on readability. The upper
three separate more on reasoning (derived figures, counter-arguments, base rates) than on readability statistics. This
is one question, through an agent rather than Optic's API path, so it is a proxy and not a measure of Optic's
production answers (BLOCKERS BL-01).

### Found by Phase 05's own checks

- The Brokerage page's "Worded for" line was missing on the first paint (BUG-083). Fixed.
- With write-ups kept per level, Classic would have called a write-up for the same figures at another level "from
  different figures" (BUG-084), and a level chosen in Classic never reached the account, so v2 reverted it (BUG-085).
  Both fixed.
- The glossary had no entry for eight chart studies (BUG-086), and a lone capital "A" stayed capital inside an
  inline definition (BUG-087). Fixed.
- The "Explain it for" link was body-sized in meta lines (BUG-088). Classic's deep research never sent the level
  (BUG-089). Fixed.
- After a failed save the toast promised the level was kept, but the next load put the account's older level back
  (BUG-090). Fixed with the version rule (D-028).
- New to Markets added definitions inside table cells and figure labels (BUG-091). Definitions now join prose only.
- Four older tests pinned the level ids from before Phase 05 or a stub without the new `mode` argument; they were
  updated to check the same properties under the new names.
- The desktop app stopped the local server while the session was paused (its log ends with a normal shutdown). It
  was started again from its launch entry, and every check after that ran on the restarted server.

### Suite

| Run | Outcome |
|---|---|
| The Phase 05 tree before the second set of checks | 7519 passed, 1 skipped, 4 failed (the four pinned tests above) |
| The final Phase 05 tree, after every code change | **7529 passed, 1 skipped, 0 failed** in 212 s (`phase05/pytest-full.txt`) |
| Phase 05's own tests | `tests/test_knowledge_level_apply.py` (9), `tests/test_v2_knowledge_level.py` (16); `tests/test_knowledge_modes.py`, `test_pulse_tone.py`, `test_ui_mode.py`, `test_brokerage.py` updated; all pass |
