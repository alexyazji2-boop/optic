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
