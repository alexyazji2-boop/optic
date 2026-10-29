# Progress

Read this and [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) before changing anything (directive 12).

## Current state

- **Current phase:** 02 advice safeguards and legal consistency, closing (report below). Phase 01 complete.
- **Branch / worktree:** `post-demo-ultra` in `~/Optic/wt-ultra`, from `9fa0f36` (tag `post-demo-ultra-baseline`). Upstream unset; nothing pushed or deployed.
- **Commits:** `fce3e71` setup; `8040f8a` and `795325a` Phase 01; `d4a2b1a` Phase 01 report; `ce60b16` Phase 02 policy module (WIP); `c6724ff` Milo portfolio privacy (cherry-pick of 2236205); then the Phase 02 commit.
- **Local server:** launch config `optic-ultra` (:8250, stand-in model :8251 from `tools/milo_standin_ultra.py`, which adds an `ADVISE` keyword that makes the answer break the policy; data `~/Optic/ultra-data`, sandbox brokerage, jobs off, no real model key). Seed password in `~/Optic/ultra-data/seed-output.txt` (never print it). The server does not reload: restart it after editing static files, or the browser keeps the old `?v=` copies.
- **Working folder (outside the repo):** `~/Optic/work/post-demo-ultra-2026-10-29/` (tools/, crawl1/, dead/, sheets/, baseline/, milo/, registry/, phase02/).
- **Resource rule:** at most two subagents at a time (DECISIONS D-007).
- **Next action:** Phase 03 (search, ticker state, SPY default, "Follows <TICKER>", navigation): read `directives/03-search-ticker-navigation.md` and the R03 rows, then BUG-003, 038, 044, 050, 066 in BUG_REGISTER.

## Phase 02 report (directive 02; reporting format of directive 00)

1. **Inspected.** Every model prompt in `app/ai.py` and `app/research/milo.py`; the three model entry points and the ten writers; every rule-written research generator the Phase 01 registry and the advice scan pointed to (352 hits at baseline, triaged line by line); the v2 and Classic pages that show them; alerts, account and alert emails, onboarding, upgrade copy; the Terms, Privacy policy, full disclaimer, page notices, AI labels, brokerage consent, data-source and delay statements.
2. **Problems discovered.** 24 advisory-risk pathways (COMPLIANCE_REVIEW section 1) and 13 disclosure findings (section 7). New in this phase beyond Phase 01's rows: per-fund dollars of the reader's contribution still on Retirement; the public "New trade idea" alerts; persuasive option rationales ("a price you already like"); Classic's options panel ("never pay above", "Exit if the stock closes past this"); Milo's options chips ("a swing long here"); the "1% or less" checklist rule; the unsupported "most likely to break out"; the linked-scan spend (BUG-036); and the measured weakness of a phrase-by-phrase output check (5 of 15, then 10 of 40 on unseen sentences).
3. **Root causes.** No shared policy; nothing read a model's answer first; rule-written research in trade-plan words with internal labels shown raw; owner formats that predate the directive; two copies of every disclosure; two front ends (COMPLIANCE_REVIEW section 2).
4. **Fixes implemented.** `app/ai_policy.py`: a ten-rule policy on every model call (three entry points, enforced by a syntax-tree test), a request classifier with the server's own line and a turn instruction, a sentence-level output check rebuilt twice on measured misses, JSON-aware cleaning for writers, a one-sentence stream gate and an end-of-stream amend with a note the reader sees and keeps. Prompts reworded. Every rule-written pathway reworded or withheld in v2 and, where it instructed, Classic. One disclosure registry with a tested v2 copy and notices on 20 views. Paper-book alerts said as simulated. Linked scans run only after a press.
5. **Files changed.** Listed in COMPLIANCE_REVIEW 3.3; new: `app/ai_policy.py`, `app/research/words.py`, `static/v2/js/core/research-words.js`, `tests/test_ai_policy.py`, `tests/test_legal_registry.py`, `tests/test_scan_link_consent.py`, `tests/fixtures/advice_set_a_2026-10-29.json`, `docs/post-demo-ultra/COMPLIANCE_REVIEW.md`.
6. **Tests executed.** Full suite six times (TEST_RESULTS, Phase 02); 240 new tests in three new files; 22 existing test files updated to the new wording; five mutation checks; `node --check` on 26 changed files; compileall; chat-route probes with the stand-in model; the Milo panel in headless Chrome; the 56-route crawl; notices on 20 routes; the scan link with and without a press; the output check on two independent held-out sets and on 544 sentences of stored real-model text.
7. **Passed / failed.** Final suite 7471 passed, 1 skipped, 0 failed (run 7). Output check on unseen sentences: 10 of 40 advice caught and 2 of 40 research wrongly flagged (set A, version 2); 27 of 50 and 1 of 50 (set B, version 3); version 4 not yet measured on unseen sentences. 0 false alarms on 544 sentences of stored real-model text and 2,361 of Optic's own research text. Requirements R02-01 to R02-13: 12 PASS, R02-11 BLOCKED. The seven named prompts with the real model: NOT TESTED (BL-01).
8. **Browser verification.** Milo panel (policy line, removal note, both kept in history); Overview, Options, Investing, Retirement (v2 and Classic), Macro pairs, Alerts, Compare, Paper Desk, Scan; notices on 20 routes; no console errors.
9. **Outstanding.** R02-11 BLOCKED on BL-01; counsel questions Q1 to Q12 (BL-02); owner decisions BL-07 (model-based check), BL-08 (brokerage consent version), BL-09 (overnight feed and Yahoo data); BUG-032's cost part (Phase 10).
10. **Commit and next phase.** The Phase 02 commit (log below); next is Phase 03.

## Phase 01 report (directive 01; reporting format of directive 00)

1. **Inspected.** The whole repository at 9fa0f36: 189 Python modules (about 94,600 lines), 241 routes, the v2 front end (112 JS files, 4 CSS files), Classic's route set, CLAUDE.md and the existing docs, 516 test files, the deploy configuration, every local branch with unshipped commits. The running app on a local server: 56 v2 routes at four sizes, guest and signed in (448 loads), Classic's 26 views at two sizes, a dead-click pass (2,431 controls listed on 56 routes, 1,006 pressed and responding), the Milo pipeline through the stand-in, the server log.
2. **Problems discovered.** 77 findings in BUG_REGISTER: 9 P0, 33 P1, 35 P2. P0: Milo's portfolio tool on every page (BUG-007); login CSRF in Google/Apple sign-in, live in production (BUG-043); the "Risk and process" persona leading with position size and stops (BUG-045); the Overview's trade plan with entry, targets, stop and shares (BUG-056); the Options entry order with limit price, target and stop (BUG-057); the options contract picker (BUG-024) and Retirement's model allocation (BUG-025), both to assess; the overnight Robinhood feed without a switch (BUG-022); unlicensed Yahoo data (BUG-023, BLOCKED). The demo's complaints all reproduced: the advanced switch appends instead of replacing (BUG-001) and rewrites the knowledge level (BUG-002); "Follows <T>" and no SPY default (BUG-003); reading load (BUG-004: 1,384 words on the NVDA Overview before a click; BUG-005: Home's 12 panels and 187 controls); Milo sends nothing until the whole context is built (1.5 to 2.2 s cold with the stand-in).
3. **Root causes.** Named per row in BUG_REGISTER. Recurring ones: analytics modules write their output as instructions (setups, entries, sizing) and the pages print them; the knowledge level doubles as a density switch; Home's linked ticker falls back to the last company opened; fetches without request identity when a setting changes; OAuth state not bound to the browser.
4. **Fixes implemented.** None (discovery phase: "Do not redesign", "Do not make unrelated feature changes").
5. **Files changed.** `docs/post-demo-ultra/**` and a CLAUDE.md section only.
6. **Tests executed.** pytest full suite; `node --check` on 122 JS files; compileall; ruff (pyflakes rules) in a throwaway venv; route-table extraction; crawl of 500 loads; dead-click pass on 78 route views; three Milo stand-in probes; three read-only GETs against production (`/docs` exposure) and one free models call (key check).
7. **Passed / failed.** pytest 7108 passed, 1 skipped (opt-in live EDGAR), 0 failed, 6 warnings. node 122/122. 0 script errors and 0 overflow on every load. Ruff 59 findings, no undefined names. Local Anthropic key refused (401).
8. **Browser verification.** Headless Chrome crawl at 1440, 1280, 768, 390 (guest and signed in) and the browser pane: the advanced switch, "Follows AMD", the skip link opening MAIN, Dossier and palette searches, the Milo panel, a cold Dossier load.
9. **Outstanding.** Everything in BUG_REGISTER (by phase); BL-01 real model key; BL-06 Docker for the image build; agent-sourced registry rows not individually re-verified (their top claims were).
10. **Commit and next phase.** `795325a`; next is Phase 02. To continue in another session: open `~/Optic/wt-ultra`, read this file, REQUIREMENTS_MATRIX.md and `directives/02-advice-elimination-legal.md`, then start the `optic-ultra` server from `~/Desktop/.claude/launch.json`.

## Log

### 2026-10-29 setup
- Created the worktree and branch; unset the upstream. Saved the 14 directive messages verbatim. Wrote the tracking files and the CLAUDE.md section.

### 2026-10-29 Phase 01 (01:18 to 04:58 ET by the commit times, with a stop from about 02:00 to 04:50 at the usage limit)
- Baseline suite, syntax and lint checks, route table, architecture, crawl, dead clicks, Milo probe, security baseline, journeys, dependencies, visual audit, four registry files, 77 findings, R01 statuses (11 PASS, R01-05 PARTIAL: image build blocked).

### 2026-10-29 Phase 02 (05:00 to 06:55 ET)
- Policy module, wiring, prompts, rule-written research in v2 and Classic, disclosure registry, Milo and Classic notice and note, alerts, scan consent; output check rebuilt twice on held-out sets written by separate agents; COMPLIANCE_REVIEW.md; suite green (run 7); committed (not pushed).
