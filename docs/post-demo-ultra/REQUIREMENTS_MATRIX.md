# Requirements matrix

The single record of every requirement in directives 01 to 11 and its verified status. IDs are `R<phase>-<nn>`.
Status words (directive 00): PASS, FAIL, PARTIAL, BLOCKED, NOT TESTED. "Implemented" is never a status.

Where a requirement is a defect to fix, its original behaviour, desired behaviour and root cause are in the
[BUG_REGISTER.md](BUG_REGISTER.md) row named in Notes. Evidence names a test (file::test), a check script and
its result line, or a screenshot path. Code inspection alone is never PASS for a behavioural requirement.

## Phase 01: discovery and baseline

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R01-01 | Document the actual architecture: frontend, backend/API, auth, persistence, brokerage, market data, AI and Milo orchestration, prompts and tool definitions, streaming, charting, caching/state, routing, design system, animation, logging/monitoring, tests, build/deploy | whole repo | PASS | FEATURE_REGISTRY Part 1 covers all 17 areas; route table `baseline/api-routes.json` | docs only | Source; agents' per-file claims spot-checked, not all re-read |
| R01-02 | Identify duplicate systems, abandoned components, conflicting implementations (do not delete) | whole repo | PASS | FEATURE_REGISTRY Part 1 (8 duplicate or abandoned systems), Part 7 (unshipped branches) | docs only | none deleted (as directed) |
| R01-03 | Inventory every route, page and tab with components, controls, inputs, charts, tables, AI sections, tooltips, links, modals, loading/error/empty states, API dependencies, preferences, auth needs | all routes | PASS | Part 2 index; registry/A-D (Source, about 1,600 + 740 file:line citations, 271 + about 220 + 104 control rows); registry/rendered-inventory.md (Rendered, 56 routes x guest and signed in); registry/api-routes.md (232 routes) | docs only | Source entries are agent-written: top claims verified (BUG-033/034/038/043/044/045/056/057), the rest Source-only |
| R01-04 | Run the app locally with non-production configuration | local server | PASS | launch config `optic-ultra` (:8250, stand-in model :8251, sandbox brokerage, jobs off, copied seed data); 448 + 52 crawled loads | ~/Desktop/.claude/launch.json (outside repo) | no real model key (BL-01) |
| R01-05 | Run the existing build, type check, lint, unit, integration and browser e2e checks; record failures before fixing | tooling | PARTIAL | pytest 7108 passed / 1 skipped (live EDGAR, opt-in) / 6 warnings in 208.84 s; node --check 122/122; compileall ok; ruff F 59 findings, 0 undefined names; no type checker, linter, JS runner or e2e suite exists in the repo | docs only | production image build BLOCKED: Docker not installed (BL-06) |
| R01-06 | Inspect console errors, failed requests, unhandled exceptions in the browser | all routes | PASS | crawl events: 0 exceptions and 0 console errors on 448 v2 loads and 52 Classic loads; failed requests only the expected 404s and one Yahoo 503; server log 0 tracebacks, 0 HTTP 500 | docs only | headless Chrome only; Safari not tested here |
| R01-07 | Visual audit of every accessible route at 1440x900, 1280x800, 768x1024, 390x844 with screenshots | all routes | PASS | all routes captured at 1440/1280/768/390 for guest and signed in (crawl1/); automated overflow, clipping, contrast, unnamed and small-target checks on every load; contact sheets reviewed at all four sizes; full pages of the 9 main routes at 1440; findings V-01 to V-11 in FEATURE_REGISTRY Part 8 | docs only | eye review of 1280 and 768 was at thumbnail size |
| R01-08 | Map journeys: first visit, onboarding, ticker search, research/Dossier, chart, Milo, brokerage connection, portfolio research, account settings; where context should persist | workflows | PASS | FEATURE_REGISTRY Part 4 (9 journeys, where each breaks, what should persist) | docs only | onboarding mapped from source and the sign-in page; the email-confirmation step was not executed (mail sink needed; Phase 11 repeats it) |
| R01-09 | Map shared ticker state, preferences, auth, financial data, AI prompts, cached responses, conversation state | dependencies | PASS | FEATURE_REGISTRY Part 5 (module fan-in, 11 shared-state rows, 68 storage keys) | docs only | Source |
| R01-10 | Security baseline: secrets, data authorisation, credentials in the browser, sensitive logging (non-destructive) | whole repo | PASS | FEATURE_REGISTRY Part 6; BUG-006, -022, -030, -043 (P0 login CSRF), -052, -053, -054 | docs only | non-destructive; nothing exercised against production beyond three read-only GETs |
| R01-11 | Rank every issue P0/P1/P2; for serious ones name files and a verification method | BUG_REGISTER | PASS | BUG_REGISTER: every row has P0/P1/P2, files and a verification method | docs only | priorities for agent-sourced rows to be confirmed when each phase reproduces them |
| R01-12 | A safe git working branch exists | git | PASS | branch `post-demo-ultra` (worktree ~/Optic/wt-ultra) from 9fa0f36, tag `post-demo-ultra-baseline`, upstream unset; commits fce3e71, 8040f8a | git | none |

## Phase 02: advice safeguards and legal consistency

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R02-01 | Locate every advice-generating pathway: Milo prompts and tools, Dossier generators, portfolio analysis, brokerage-linked AI, news summaries, chart interpretations, risk outputs, alerts, email templates, research reports, deprecated AI endpoints, marketing, onboarding, homepage copy | all AI and copy | PASS | COMPLIANCE_REVIEW.md section 1 (24 pathways); advice_scan.py baseline 352 hits triaged line by line (phase02/triage-now.tsv); every prompt read | app/ai.py, app/research, app/analytics, static/v2, static/app.js | Email templates (auth mail) and alerts checked: factual; paper-book alerts reworded (D-013) |
| R02-02 | Find explicit and implicit advice, including personalised rankings, suggested actions and broker-linked recommendations | all AI and copy | PASS | COMPLIANCE_REVIEW P5, P11, P12, P17, P21 (brokerage write-up, contract screener, Retirement, rankings, public alerts) | see section 3.3 | Counsel questions Q2 to Q5 stay open |
| R02-03 | Preserve factual research (prices, fundamentals, indicators, statements, volatility, composition, concentration, sourced analyst ratings, education, explicit-assumption scenarios) | all research | PASS | Full suite 7,214 passed / 0 failed (pytest-run5); crawl 56 routes no script errors (phase02/crawl); test_ai_policy education and research sets (16 + 37 + 16 kept) |  | Research kept on purpose is listed in COMPLIANCE_REVIEW section 1 |
| R02-04 | Replace personalised instructions with accurate factual explanation | all AI and copy | PASS | Rule-written surfaces: test_ai_policy rule-written research tests, 22 updated wording tests, browser reads of Overview, Options, Investing, Retirement, Macro, Compare, Paper Desk, Alerts, Classic Retirement | section 3.3 files | What the real model writes is R02-11 |
| R02-05 | One reusable AI behaviour policy applied to every AI feature, covering buy/sell decisions, position sizing, guaranteed returns, certainty, brokerage recommendations, unsupported claims, missing/stale data, fact vs interpretation | app AI layer | PASS | test_ai_policy::test_every_model_call_in_app_goes_through_the_three_policy_points (syntax tree), ::test_ask_carries_the_policy_and_cleans_the_reply, ::test_milos_request_carries_the_policy..., ::test_deep_research_carries_the_policy_and_is_amended_too; mutation checks M1 to M4 | app/ai_policy.py, app/ai.py | POLICY_VERSION advice-policy-2026-10-29 |
| R02-06 | Structured output validation and targeted checks, not only keyword blocking or one prompt | app AI layer | PASS | Request classifier + fixed server line, StreamGate, JSON-aware sanitize, end-of-stream amend; detection rates measured on held-out sentences (COMPLIANCE_REVIEW 4.2) | app/ai_policy.py | Recall on unseen phrasing is limited and reported, not claimed complete (D-015) |
| R02-07 | Locate Terms, Privacy, financial disclaimers, AI and brokerage disclosures, data licensing, timeliness notices, billing disclosures; identify inconsistencies | legal surfaces | PASS | COMPLIANCE_REVIEW section 7 (13 findings): Terms, Privacy, disclaimers, AI and brokerage disclosures, data sources and delays, billing | app/legal.py, static/v2/js/pages/legalpages.js, app/brokerage/service.py |  |
| R02-08 | One registry of reusable disclaimer wording | legal surfaces | PASS | app/legal.py PAGE_AREAS, FOOTER_LINE, LABELS, REGISTRY_VERSION; tests/test_legal_registry.py (3) | app/legal.py, static/v2/js/core/legal.js | Remaining duplicate wordings listed for a decision (section 7 items 1 to 4, 8) |
| R02-09 | Proposed legal changes written for counsel; no silent change to a policy's substance | legal surfaces | PASS | COMPLIANCE_REVIEW sections 6 and 7; no Terms or Privacy text changed; the two notices aligned were aligned to the words already on the pages |  |  |
| R02-10 | Context-sensitive disclosure of AI content, data delays, modelled figures, third-party sources, limitations, research vs advice, without overwhelming screens | all surfaces | PASS | Browser check: the right notice on all 20 research routes; AI labels on Milo, writers and the brokerage write-up; delay statements consistent | static/v2/js/core/legal.js, pages | Three AI label wordings still differ (section 7 item 8) |
| R02-11 | The seven jailbreak prompts get no personalised transaction recommendation; educational questions still work | Milo and AI entry points | BLOCKED | Deterministic part PASS: all seven classified, the server line arrives before any model text (milo_probe declined.jsonl; Milo panel check in headless Chrome); an advice sentence from the model is never streamed (advise2.jsonl). The real model NOT TESTED: BL-01 (key refused) | app/ai_policy.py | Rerun the seven prompts with a working key (Phase 08) |
| R02-12 | Regression tests: policy on every AI entry point, portfolio recommendation requests, trade instructions, guaranteed-return wording, missing data, injected instructions in retrieved content, educational answers | tests | PASS | tests/test_ai_policy.py (156), tests/test_legal_registry.py (3), tests/test_scan_link_consent.py (1); entry points, portfolio requests, trade instructions, guarantees, missing data, injected instructions, education | tests/ | Mutation checks: phase02/mutation-checks.txt |
| R02-13 | COMPLIANCE_REVIEW.md with pathways, root causes, corrections, tests, remaining risks, counsel questions, disclaimer findings | docs | PASS | docs/post-demo-ultra/COMPLIANCE_REVIEW.md |  |  |

## Phase 03: search, ticker state, SPY default, navigation

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R03-01 | Find every search implementation and whether they share a provider, component, resolver, cache or state | all search boxes | PASS | FEATURE_REGISTRY A12 to A15 (Phase 01); since Phase 03 one resolver, core/resolve.js, for the palette (Home's search), the Dossier start page and Home's linked-panel box (corrected in Phase 04: the "Home search box" was in an unrouted page, D-021); the typeahead (ui/typeahead.js) and every symbol box read the same /api/search | static/v2/js/core/resolve.js, ui/palette.js, ui/typeahead.js | TEST_RESULTS Phase 03 lists every box |
| R03-02 | Investigate the 16 listed search failure modes | all search boxes | PASS | TEST_RESULTS Phase 03, "The sixteen failure modes": each reproduced, fixed or shown not to occur, with its scenario |  | Found and fixed: a failed search gave Enter to a page that only shared letters; "nvidia" opened as a ticker with search down; Enter on an empty box opened the first row; a failed answer cached for 5 minutes |
| R03-03 | Search behaves per the 10-step specification (focus, type, results, arrows, Enter, click, Escape, clear, invalid feedback, correct downstream update) | all search boxes | PASS | Scenarios S9 (keys), S10 (empty Enter), S20 (click), S21 (clear), S7 and S12 (invalid and provider down), S5, S13, S22 | ui/palette.js, ui/typeahead.js |  |
| R03-04 | Debounce where useful; cancellation or request identity so an older response never overwrites the latest selection | search client | PASS | Debounce 120 ms (palette) and 160 ms (typeahead) with request identity; resolver ticket for navigation; failed answers not cached; scenario S11 (2.5 s delay, last text wins), S14 | core/resolve.js, core/api.js | Cancellation not added: identity checks cover it and production is HTTP/2 (TEST_RESULTS Phase 03) |
| R03-05 | Remove the "Follows <TICKER>" UI and its unwanted behaviour after tracing its effect on ticker selection, navigation, Dossier, charts, watchlists, Milo, portfolio, stored preferences | located in Phase 03 | PASS | tests/test_v2_ticker_state.py (chip gone, label and menu kept); scenarios S2, S3; traced effects in D-017 | pages/workspace.js, core/homelink.js, css/pages.css | BUG-003 |
| R03-06 | SPY is the default symbol with no explicit selection; documented, tested precedence (route, in-session selection, persisted preference, SPY) | ticker context | PASS | D-016 precedence; tests (first visit, Recent and watchlist ignored, unchosen saved ticker ignored, chosen kept); scenarios S1, S3, S4, S24 | core/store.js, pages/workspace.js, ui/palette.js |  |
| R03-07 | Dossier search passes the 13 listed scenarios | Dossier | PASS | Scenarios S13 (ticker, name, lower and mixed case, BRK.B, ^GSPC, no match), S23 (empty), S7 (invalid address), S12 and S14 (provider down, slow), S8 (direct, back, refresh), S6 (rapid switching during loads) | pages/dossierstart.js, core/resolve.js |  |
| R03-08 | Every displayed analysis belongs to the selected ticker (no stale cross-symbol rendering) | Dossier and research | PASS | Guards audited on every Dossier tab; fixes to the sheet (BUG-066) and the Chart's intraday levels; scenarios S6 (20 rapid changes, the name matched the last), S26, S27 | pages/sheet.js, pages/chart.js, pages/workspace.js |  |
| R03-09 | Cross-feature ticker context across terminal, Dossier, charts, research, news, Milo; intentional exceptions documented | ticker context | PASS | DECISIONS D-016 (one precedence; Home, Compare, the Chart overlay, Watchlist, Alerts and Paper Desk keep their own selection; Milo takes the page's symbol) |  |  |
| R03-10 | Navigation: back/forward, direct links, refresh, new tabs, sidebar, active indicators, search-result navigation, mobile, signed in and guest | router | PASS | Scenarios S8 (direct links, back, forward, refresh), S19 (new tabs, guest and owner), S16 and S24 (sidebar and its indicator), S5 and S20 (search-result navigation), S18 and S25 (phone search and phone bar), S15 (skip link) | core/router.js, ui/shell.js, app.js |  |
| R03-11 | Executed scenarios: 20 sequential changes, 10 rapid, 10 invalid, 10 refresh/navigation, keyboard-only, simulated latency, failed provider | tests | PASS | phase03/phase03-all.json: 27 scenarios, 27 passed (20 sequential, 10 rapid x2, 10 invalid, 10 sequences x5 checks, keyboard only, 2.5 s latency, 503 provider) | tools/phase03_scenarios.py |  |

## Phase 04: radical simplicity and first use

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R04-01 | First-time-user audit of every major screen against the nine questions (heuristics, not user-test claims) | all primary routes | PASS | SIMPLICITY_AUDIT.md section 1: the nine questions answered for 29 primary routes, as heuristics | docs | No reader was tested; no outcome claimed |
| R04-02 | Visual density audit of every route (cards, headings, statistics, text length, tables, jargon, duplicates, buttons, icons, borders, nesting, gaps, spacing, hierarchy, sidebar, modals, chart controls, AI layouts) | all routes | PASS | SIMPLICITY_AUDIT.md section 2: density.py before (2f6a548) and after, 29 routes at 1440 and 390, plus the directive's 18-item list | tools/density.py | Probe corrected for folded content before use (D-022) |
| R04-03 | Every primary screen has essential / supporting / advanced layers without hiding essentials behind menus | all primary routes | PASS | SIMPLICITY_AUDIT.md section 3: three layers per primary screen; Simple folds supporting detail with its heading in view (sections.js, simpleFold, Home sets) | ui/sections.js, ui/states.js, pages/workspace.js | The Dossier tabs' layer 1 is rebuilt in Phase 06 |
| R04-04 | Homepage communicates what Optic does, how to start, market context, search, Milo, deeper research | Home | PASS | SIMPLICITY_AUDIT.md section 4; Home 1,872 to 672 visible words, 186 to 71 controls, 12 to 5 cards at 1440; first-visit card checked in the browser (Not now, Follow, Done) | pages/workspace.js | D-020; BUG-005, BUG-079 |
| R04-05 | Navigation clarity reviewed; redundant items identified; hierarchy improved; deep links kept (renames need the owner's yes) | rail, phone bar | PASS | SIMPLICITY_AUDIT.md section 5: names reviewed, proposals listed for the owner, every route and deep link kept (core/router.js unchanged) | nav.js (unchanged) | Renames need the owner's yes (D-023) |
| R04-06 | Writing guidelines written and applied to labels, descriptions, tooltips, placeholders, AI explanations | all copy | PASS | WRITING_GUIDELINES.md (10 rules with examples); applied: one name per model, times that say their clock, words that describe the grade, the report sentence once | docs, pages/*.js, app/analytics/liquidity.py, app/analytics/macro.py | AI explanations: the policy and Milo's prompts are Phases 02, 07 and 08 |
| R04-07 | Simple/Advanced presentation model evaluated; no conflicting mode systems; knowledge level separate from density | app-wide | PASS | D-019; tests/test_v2_density.py (8 tests): density and the knowledge level move apart, the Dossier switch is density only, Home's sets follow density | core/prefs.js, ui/sections.js, pages/settings.js, pages/dossier-frame.js | Phase 05 adds the five-level slider on the knowledge side |
| R04-08 | Every component classified KEEP / SIMPLIFY / COLLAPSE / RELOCATE / MERGE / REMOVE; every removal documented | all components | PASS | SIMPLICITY_AUDIT.md section 8: every component classified; each removal listed (the unrouted Home page, undrawn handlers, a stale pointer, duplicate buttons, rating colours) | pages/home.js, pages/workspace.js | D-021 |
| R04-09 | Design-system consistency of buttons, type, spacing, cards, fields, tabs, dropdowns, tooltips, icons, charts, loading, errors, empty states, navigation, modals | all components | PASS | SIMPLICITY_AUDIT.md section 9: 15 areas checked; tests/test_v2_design_standard.py and test_v2_checklist.py pass; icons and colour fixed | css/pages.css, pages/overview-research.js | Phase 04 scope: the audit, tokens in all new work, icons and colour fixed. Snapping the 835 off-scale spacing values and the headline sizes is Phase 10's visual consistency audit (D-025); the light theme was checked for the changed elements only (contrast 6.5:1 and up), Classic not re-checked |
| R04-10 | Understandable at desktop, laptop, tablet, mobile; no overlap, no inaccessible controls, no unintended horizontal overflow | all routes | PASS | SIMPLICITY_AUDIT.md section 10: 29 routes at 1440, 1024, 768 and 390: no sideways overflow, no overlapping text by the probe | tools/density.py (overlap check) | Small phone targets are BUG-014 (Phase 10) |
| R04-11 | Before/after screenshots for every materially changed route, inspected for regressions | docs | PASS | SIMPLICITY_AUDIT.md section 11: before and after sheets (phase04/pairs-*.jpg) inspected; two problems found and fixed (a future date on Indices, duplicate Follow buttons); dead-click run on the changed routes | tools/pair_sheet.py, tools/deadclicks.py |  |
| R04-12 | SIMPLICITY_AUDIT.md with per-route load, problems, changes, relocations, removals, preserved features, evidence, limits | docs | PASS | SIMPLICITY_AUDIT.md: per-route records with load, problems, changes, relocations, removals, preserved features, evidence and limits | docs/post-demo-ultra/SIMPLICITY_AUDIT.md |  |

## Phase 05: knowledge-level slider

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R05-01 | Find Classic's original "how should Optic talk to you" implementation in the repo or history | Classic Home | NOT TESTED | | | |
| R05-02 | Five levels as specified: New to Markets, Beginner, Intermediate, Advanced, Expert | preference | NOT TESTED | | | |
| R05-03 | Slider: five discrete positions, shows the level, previews the style, consistent look, keyboard and touch, accessible labels, responsive, unintrusive, editable in Settings | Home, Settings | NOT TESTED | | | |
| R05-04 | One authoritative preference; account persistence through the existing settings architecture; guest persistence; graceful when storage fails; no contradictory copies | preference store | NOT TESTED | | | |
| R05-05 | Applies to Milo, Dossier simple and advanced wording, market summaries, chart explanations, portfolio explanations, educational articles, other AI explanations; not to raw tables | all explanatory text | NOT TESTED | | | |
| R05-06 | One central prompt contract for complexity; the level never changes figures, calculations, sources, caveats, disclosures, missing-data notes or safeguards | app AI layer | NOT TESTED | | | |
| R05-07 | New responses use the new level; a clear, cheap way to re-explain existing content; history never rewritten silently | Milo, Dossier | NOT TESTED | | | |
| R05-08 | Tests across all five levels on the same input: vocabulary, depth, same numbers, sources, uncertainty, no advice, survives refresh, across tabs, Milo, guest and signed in | tests | NOT TESTED | | | |

## Phase 06: Dossier

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R06-01 | Map the Dossier pipeline (selection, requests, normalisation, AI, prompts, caching, loading, rendering, mode state, errors, sources) and where stale or wrong data can enter | Dossier | NOT TESTED | | | |
| R06-02 | Simple Analysis a beginner understands: what's happening, why it matters, what else to know; knowledge level; no speculation as fact; no advice | Dossier | NOT TESTED | | | |
| R06-03 | Show Advanced Analysis replaces Simple (never appends); button toggles to Show Simple Analysis; ticker unchanged; no jump; no duplicates; one mode state; no repeated paid calls | Dossier | NOT TESTED | | | |
| R06-04 | Async correctness when the ticker changes during simple load, advanced load, mode switch, provider failure, stale cache, navigation away and back | Dossier | NOT TESTED | | | |
| R06-05 | Advanced Analysis is deeper research from real data only, in separated sections | Dossier | NOT TESTED | | | |
| R06-06 | Phase 03 search fixes still pass (7 listed cases) | Dossier search | NOT TESTED | | | |
| R06-07 | Restrained Simple/Advanced transition without flicker, jumps, duplicate loaders, slow motion, scroll moves or height errors; reduced motion respected | Dossier | NOT TESTED | | | |
| R06-08 | Representative outputs checked against provider responses (numbers, identities, dates, freshness, indicator readings, sources, missing data) | Dossier | NOT TESTED | | | |
| R06-09 | Tests for both transitions, one visible mode, correct ticker, failed requests, rapid changes, knowledge level, stale-response prevention, data accuracy | tests | NOT TESTED | | | |

## Phase 07: Milo streaming and conversation

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R07-01 | Trace a message through all 14 stages and measure first visible response, first token, total time, event rate, render cost, re-renders, tool delays | Milo | NOT TESTED | | | |
| R07-02 | Genuine incremental streaming: immediate display, ordered chunks, Unicode and Markdown, efficient state, input not blocked, scroll while streaming, clean termination, useful network errors, aborted requests stop mutating | Milo | NOT TESTED | | | |
| R07-03 | Smooth rendering without big irregular blocks, flicker, paragraph re-renders, jumpy Markdown, vanishing messages, scroll snapping, typing delay, main-thread blocking, duplicates, stuck thinking | Milo | NOT TESTED | | | |
| R07-04 | Truthful activity states shown only while that activity happens; no hidden reasoning; no fabricated tool use | Milo | NOT TESTED | | | |
| R07-05 | New Chat: distinct conversation, cleared view, clean context, no carried instructions, history kept, no duplicates on repeated clicks | Milo | NOT TESTED | | | |
| R07-06 | Close (X): closes the panel, keeps history, no corruption, restores on reopen, predictable with a stream in flight; close, new and delete distinct | Milo | NOT TESTED | | | |
| R07-07 | Conversation persistence: correct user, no cross-user access, retrieval, missing/deleted handled, accurate IDs, no mixing; or documented local-only behaviour | Milo | NOT TESTED | | | |
| R07-08 | Composer: Enter, Shift+Enter, empty, large, paste, rapid, disabled, duplicate prevention, network failure, retry, stop, focus, mobile | Milo | NOT TESTED | | | |
| R07-09 | Auto-scroll only near the bottom; never force down after the reader scrolls up; a quiet jump-to-latest | Milo | NOT TESTED | | | |
| R07-10 | Milo honours the Phase 05 level for later responses without altering stored facts or records | Milo | NOT TESTED | | | |
| R07-11 | Reproducible tests for the 16 listed cases, with before/after measurements | tests | NOT TESTED | | | |

## Phase 08: Milo grounding, tools and evaluation

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R08-01 | Map every tool and data source Milo can actually use (quotes, history, fundamentals, statements, indicators, Dossier, news, economics, portfolio, brokerage facts, page context, other features) | Milo | NOT TESTED | | | |
| R08-02 | Tool contracts (purpose, input/output schema, auth, provider, caching, freshness, failures, rate limits, cost, allowed use); inputs validated; context kept relevant | Milo tools | NOT TESTED | | | |
| R08-03 | Fact / calculation / interpretation / unknown distinguished; no invented current price or event; timestamps and delay limits stated | Milo | NOT TESTED | | | |
| R08-04 | Context awareness for the six listed questions; no claimed access to unsupplied screen content; no mixing earlier tickers | Milo | NOT TESTED | | | |
| R08-05 | Financial accuracy across the 12 listed kinds, against reference data where available | Milo | NOT TESTED | | | |
| R08-06 | Evaluation suite of at least 100 cases over the 15 categories, with prompts, reference data, expected behaviour, results; deterministic checks where possible | tests | NOT TESTED | | | |
| R08-07 | Response quality: direct, no filler, right length, level respected, no repetition, formatting, source vs inference, uncertainty, no invented citations, educational refusals | Milo | NOT TESTED | | | |
| R08-08 | Correct tool routing; no needless tool calls or tokens | Milo | NOT TESTED | | | |
| R08-09 | Injected instructions in retrieved content cannot redirect Milo; user data isolated; no unauthorised brokerage disclosure | Milo | NOT TESTED | | | |
| R08-10 | Regression tracking of correctness, tool choice, unsupported claims, advice violations, quality, latency, tokens, cost | tests | NOT TESTED | | | |

## Phase 09: market data integrity

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R09-01 | Inventory every financial-data pathway, provider to API to normalisation to cache to calculation to frontend to AI context, and where errors can enter | data layer | NOT TESTED | | | |
| R09-02 | Correctness of every supported metric in the directive's list (prices incl. pre/post, history, changes, charts, MAs, RSI, VWAP, indicators, market cap, ratios, earnings, revenue, dividends, corporate actions, names, symbol maps, portfolio totals and weights, currency, news times, summaries) | data layer | NOT TESTED | | | |
| R09-03 | Session accuracy: regular, pre, post, weekends, holidays, delayed quotes, historical sessions; never "live" for delayed data | session, quotes | NOT TESTED | | | |
| R09-04 | Independent check of calculation logic incl. zero denominators, missing values, currency, corporate actions; no arbitrary zero fallbacks | calculations | NOT TESTED | | | |
| R09-05 | Cross-feature consistency, with legitimate differences explained on screen | all data surfaces | NOT TESTED | | | |
| R09-06 | Scenarios A to H executed | workflows | NOT TESTED | | | |
| R09-07 | Caching audit (keys, expiry, symbol and user scope, auth boundaries, duplicates, stale-while-revalidate, invalidation, session awareness); no cross-user or cross-ticker leakage | caches | NOT TESTED | | | |
| R09-08 | Reconciliation table against live provider responses; UNVERIFIED where unverifiable | docs | NOT TESTED | | | |
| R09-09 | Provider failure never shows fabricated data or unlabelled stale values; consistent, simple states | all data surfaces | NOT TESTED | | | |

## Phase 10: performance, security, accessibility, polish

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R10-01 | Measured baseline: load, LCP, INP, CLS, route changes, chart render, search, Dossier, Milo first response, render overhead, bundle sizes, request counts, main-thread blocking | app-wide | NOT TESTED | | | |
| R10-02 | Root-cause fixes for duplicate requests, polling, re-renders, heavy calculations, unused code, bundle size, splitting, repeated AI calls, Markdown, animation loops, layout thrash, chart redraws, leaks, missing cancellation, with measurements | app-wide | NOT TESTED | | | |
| R10-03 | Cost and scaling estimate for 100 / 1,000 / 10,000 users under explicit assumptions; unverified prices marked provisional; safe caching opportunities | docs | NOT TESTED | | | |
| R10-04 | Visual consistency of padding, margins, alignment, radii, type, button heights, hovers, icons, dropdowns, responsive layout, truncation, density, colour, decoration, charts | all routes | NOT TESTED | | | |
| R10-05 | Purposeful, reduced-motion-aware animation for transitions, tabs, hovers, modals, dropdowns, chart loading, Dossier mode, Milo states, skeletons, content, feedback | app-wide | NOT TESTED | | | |
| R10-06 | WCAG 2.2 AA review: keyboard, focus, semantics, labels, contrast, dialogs, announcements, slider, chart alternatives, validation, reduced motion, touch targets, zoom; critical barriers fixed | app-wide | NOT TESTED | | | |
| R10-07 | Non-destructive security review of the 15 listed areas; never print secrets | app-wide | NOT TESTED | | | |
| R10-08 | Failure resilience for the 12 listed conditions; recovery path for every critical workflow; no endless spinners | app-wide | NOT TESTED | | | |
| R10-09 | Privacy-conscious analytics review and recommendations | app-wide | NOT TESTED | | | |

## Phase 11: adversarial final audit

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R11-01 | Every FEATURE_REGISTRY feature verified on the 12 listed points; untested features listed separately | all features | NOT TESTED | | | |
| R11-02 | Every requirement has status, evidence, test reference, files, limits; no behavioural PASS from inspection alone | this file | NOT TESTED | | | |
| R11-03 | The 15-step investor-demo journey executed | workflow | NOT TESTED | | | |
| R11-04 | Repeatability across the 11 listed scenarios, each recorded | workflow | NOT TESTED | | | |
| R11-05 | Adversarial testing of the 12 listed behaviours | app-wide | NOT TESTED | | | |
| R11-06 | Financial correctness against configured providers | data | NOT TESTED | | | |
| R11-07 | Milo evaluation suite run, failures documented | Milo | NOT TESTED | | | |
| R11-08 | Simplicity regression against the ten listed questions | app-wide | NOT TESTED | | | |
| R11-09 | Reproducible P0s fixed, P1s fixed where feasible, P2s recorded, no reclassification | BUG_REGISTER | NOT TESTED | | | |
| R11-10 | Full engineering checks with exact commands and outcomes | tooling | NOT TESTED | | | |
| R11-11 | Final deliverables with the 17 listed figures | docs | NOT TESTED | | | |
| R11-12 | Final decision: READY FOR HUMAN STAGING REVIEW or NOT READY, with required manual verifications | docs | NOT TESTED | | | |
