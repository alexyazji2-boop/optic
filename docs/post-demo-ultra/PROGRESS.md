# Progress

Read this and [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) before changing anything (directive 12).

## Current state

- **Current phase:** 02 advice safeguards and legal consistency (starting). Phase 01 complete (report below).
- **Branch / worktree:** `post-demo-ultra` in `~/Optic/wt-ultra`, from `9fa0f36` (tag `post-demo-ultra-baseline`). Upstream unset; nothing pushed or deployed.
- **Commits:** `fce3e71` setup; `8040f8a` Phase 01 checkpoint; `795325a` Phase 01 complete; then this report.
- **Local server:** launch config `optic-ultra` (:8250, stand-in model :8251, data `~/Optic/ultra-data`, sandbox brokerage, jobs off, no real model key). Seed password in `~/Optic/ultra-data/seed-output.txt` (never print it).
- **Working folder (outside the repo):** `~/Optic/work/post-demo-ultra-2026-10-29/` (tools/, crawl1/, dead/, sheets/, baseline/, milo/, registry/).
- **Resource rule:** at most two subagents at a time (six at once hit the session limit at 02:00 ET and stalled the run until 04:50; DECISIONS D-007).
- **Next action:** Phase 02, starting with the advice pathways in `app/ai.py` (12 prompts), the deterministic generators (BUG-033, 034, 056, 057, 058, 060, 061, 062, 070), the persona (BUG-045), the portfolio exposure (BUG-007), then the central policy module and output validator, the legal surfaces and the disclaimer registry.

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

### 2026-10-29 Phase 01 (01:18 to about 05:30 ET, with a stop from 02:00 to 04:50 at the usage limit)
- Baseline suite, syntax and lint checks, route table, architecture, crawl, dead clicks, Milo probe, security baseline, journeys, dependencies, visual audit, four registry files, 77 findings, R01 statuses (11 PASS, R01-05 PARTIAL: image build blocked).
