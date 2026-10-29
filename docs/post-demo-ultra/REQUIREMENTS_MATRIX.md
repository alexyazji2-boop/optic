# Requirements matrix

The single record of every requirement in directives 01 to 11 and its verified status. IDs are `R<phase>-<nn>`.
Status words (directive 00): PASS, FAIL, PARTIAL, BLOCKED, NOT TESTED. "Implemented" is never a status.

Where a requirement is a defect to fix, its original behaviour, desired behaviour and root cause are in the
[BUG_REGISTER.md](BUG_REGISTER.md) row named in Notes. Evidence names a test (file::test), a check script and
its result line, or a screenshot path. Code inspection alone is never PASS for a behavioural requirement.

## Phase 01: discovery and baseline

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R01-01 | Document the actual architecture: frontend, backend/API, auth, persistence, brokerage, market data, AI and Milo orchestration, prompts and tool definitions, streaming, charting, caching/state, routing, design system, animation, logging/monitoring, tests, build/deploy | whole repo | NOT TESTED | | | |
| R01-02 | Identify duplicate systems, abandoned components, conflicting implementations (do not delete) | whole repo | NOT TESTED | | | |
| R01-03 | Inventory every route, page and tab with components, controls, inputs, charts, tables, AI sections, tooltips, links, modals, loading/error/empty states, API dependencies, preferences, auth needs | all routes | NOT TESTED | | | |
| R01-04 | Run the app locally with non-production configuration | local server | NOT TESTED | | | |
| R01-05 | Run the existing build, type check, lint, unit, integration and browser e2e checks; record failures before fixing | tooling | NOT TESTED | | | |
| R01-06 | Inspect console errors, failed requests, unhandled exceptions in the browser | all routes | NOT TESTED | | | |
| R01-07 | Visual audit of every accessible route at 1440x900, 1280x800, 768x1024, 390x844 with screenshots | all routes | NOT TESTED | | | |
| R01-08 | Map journeys: first visit, onboarding, ticker search, research/Dossier, chart, Milo, brokerage connection, portfolio research, account settings; where context should persist | workflows | NOT TESTED | | | |
| R01-09 | Map shared ticker state, preferences, auth, financial data, AI prompts, cached responses, conversation state | dependencies | NOT TESTED | | | |
| R01-10 | Security baseline: secrets, data authorisation, credentials in the browser, sensitive logging (non-destructive) | whole repo | NOT TESTED | | | |
| R01-11 | Rank every issue P0/P1/P2; for serious ones name files and a verification method | BUG_REGISTER | NOT TESTED | | | |
| R01-12 | A safe git working branch exists | git | NOT TESTED | | | |

## Phase 02: advice safeguards and legal consistency

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R02-01 | Locate every advice-generating pathway: Milo prompts and tools, Dossier generators, portfolio analysis, brokerage-linked AI, news summaries, chart interpretations, risk outputs, alerts, email templates, research reports, deprecated AI endpoints, marketing, onboarding, homepage copy | all AI and copy | NOT TESTED | | | |
| R02-02 | Find explicit and implicit advice, including personalised rankings, suggested actions and broker-linked recommendations | all AI and copy | NOT TESTED | | | |
| R02-03 | Preserve factual research (prices, fundamentals, indicators, statements, volatility, composition, concentration, sourced analyst ratings, education, explicit-assumption scenarios) | all research | NOT TESTED | | | |
| R02-04 | Replace personalised instructions with accurate factual explanation | all AI and copy | NOT TESTED | | | |
| R02-05 | One reusable AI behaviour policy applied to every AI feature, covering buy/sell decisions, position sizing, guaranteed returns, certainty, brokerage recommendations, unsupported claims, missing/stale data, fact vs interpretation | app AI layer | NOT TESTED | | | |
| R02-06 | Structured output validation and targeted checks, not only keyword blocking or one prompt | app AI layer | NOT TESTED | | | |
| R02-07 | Locate Terms, Privacy, financial disclaimers, AI and brokerage disclosures, data licensing, timeliness notices, billing disclosures; identify inconsistencies | legal surfaces | NOT TESTED | | | |
| R02-08 | One registry of reusable disclaimer wording | legal surfaces | NOT TESTED | | | |
| R02-09 | Proposed legal changes written for counsel; no silent change to a policy's substance | legal surfaces | NOT TESTED | | | |
| R02-10 | Context-sensitive disclosure of AI content, data delays, modelled figures, third-party sources, limitations, research vs advice, without overwhelming screens | all surfaces | NOT TESTED | | | |
| R02-11 | The seven jailbreak prompts get no personalised transaction recommendation; educational questions still work | Milo and AI entry points | NOT TESTED | | | |
| R02-12 | Regression tests: policy on every AI entry point, portfolio recommendation requests, trade instructions, guaranteed-return wording, missing data, injected instructions in retrieved content, educational answers | tests | NOT TESTED | | | |
| R02-13 | COMPLIANCE_REVIEW.md with pathways, root causes, corrections, tests, remaining risks, counsel questions, disclaimer findings | docs | NOT TESTED | | | |

## Phase 03: search, ticker state, SPY default, navigation

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R03-01 | Find every search implementation and whether they share a provider, component, resolver, cache or state | all search boxes | NOT TESTED | | | |
| R03-02 | Investigate the 16 listed search failure modes | all search boxes | NOT TESTED | | | |
| R03-03 | Search behaves per the 10-step specification (focus, type, results, arrows, Enter, click, Escape, clear, invalid feedback, correct downstream update) | all search boxes | NOT TESTED | | | |
| R03-04 | Debounce where useful; cancellation or request identity so an older response never overwrites the latest selection | search client | NOT TESTED | | | |
| R03-05 | Remove the "Follows <TICKER>" UI and its unwanted behaviour after tracing its effect on ticker selection, navigation, Dossier, charts, watchlists, Milo, portfolio, stored preferences | located in Phase 03 | NOT TESTED | | | |
| R03-06 | SPY is the default symbol with no explicit selection; documented, tested precedence (route, in-session selection, persisted preference, SPY) | ticker context | NOT TESTED | | | |
| R03-07 | Dossier search passes the 13 listed scenarios | Dossier | NOT TESTED | | | |
| R03-08 | Every displayed analysis belongs to the selected ticker (no stale cross-symbol rendering) | Dossier and research | NOT TESTED | | | |
| R03-09 | Cross-feature ticker context across terminal, Dossier, charts, research, news, Milo; intentional exceptions documented | ticker context | NOT TESTED | | | |
| R03-10 | Navigation: back/forward, direct links, refresh, new tabs, sidebar, active indicators, search-result navigation, mobile, signed in and guest | router | NOT TESTED | | | |
| R03-11 | Executed scenarios: 20 sequential changes, 10 rapid, 10 invalid, 10 refresh/navigation, keyboard-only, simulated latency, failed provider | tests | NOT TESTED | | | |

## Phase 04: radical simplicity and first use

| ID | Requirement | Route / component | Status | Evidence / tests | Files | Notes |
|---|---|---|---|---|---|---|
| R04-01 | First-time-user audit of every major screen against the nine questions (heuristics, not user-test claims) | all primary routes | NOT TESTED | | | |
| R04-02 | Visual density audit of every route (cards, headings, statistics, text length, tables, jargon, duplicates, buttons, icons, borders, nesting, gaps, spacing, hierarchy, sidebar, modals, chart controls, AI layouts) | all routes | NOT TESTED | | | |
| R04-03 | Every primary screen has essential / supporting / advanced layers without hiding essentials behind menus | all primary routes | NOT TESTED | | | |
| R04-04 | Homepage communicates what Optic does, how to start, market context, search, Milo, deeper research | Home | NOT TESTED | | | |
| R04-05 | Navigation clarity reviewed; redundant items identified; hierarchy improved; deep links kept (renames need the owner's yes) | rail, phone bar | NOT TESTED | | | |
| R04-06 | Writing guidelines written and applied to labels, descriptions, tooltips, placeholders, AI explanations | all copy | NOT TESTED | | | |
| R04-07 | Simple/Advanced presentation model evaluated; no conflicting mode systems; knowledge level separate from density | app-wide | NOT TESTED | | | |
| R04-08 | Every component classified KEEP / SIMPLIFY / COLLAPSE / RELOCATE / MERGE / REMOVE; every removal documented | all components | NOT TESTED | | | |
| R04-09 | Design-system consistency of buttons, type, spacing, cards, fields, tabs, dropdowns, tooltips, icons, charts, loading, errors, empty states, navigation, modals | all components | NOT TESTED | | | |
| R04-10 | Understandable at desktop, laptop, tablet, mobile; no overlap, no inaccessible controls, no unintended horizontal overflow | all routes | NOT TESTED | | | |
| R04-11 | Before/after screenshots for every materially changed route, inspected for regressions | docs | NOT TESTED | | | |
| R04-12 | SIMPLICITY_AUDIT.md with per-route load, problems, changes, relocations, removals, preserved features, evidence, limits | docs | NOT TESTED | | | |

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
