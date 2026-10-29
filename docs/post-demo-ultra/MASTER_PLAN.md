# Post-demo ultra overhaul: master plan

Owner's directives, verbatim: [directives/](directives/) (00 master rules, 01 to 11 phases, 12 overnight
controller, 13 the owner's sequencing instruction). This file is the plan; [PROGRESS.md](PROGRESS.md) is the
live state; [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) is the single record of what each requirement's
status is and what evidence backs it.

## Mission

After the 2026-10-28 investor demonstration: make Optic simpler, more reliable, faster, more accurate, more
legally defensible and professionally polished, without removing valuable analysis and without giving
personalised investment advice.

## Ground rules for this work (digest of directive 00, the controller and the owner's instruction)

- One phase at a time, in order. A phase is finished only when every requirement in it is PASS, or is
  BLOCKED / UNVERIFIED for a named external reason recorded in [BLOCKERS.md](BLOCKERS.md). No phase starts
  while the previous one has work left (owner, 2026-10-29).
- Verification cycle for every meaningful change: discover, reproduce, diagnose, implement, test, verify in
  the browser where possible, document. Status words: PASS, FAIL, PARTIAL, BLOCKED, NOT TESTED. Implemented
  is not verified.
- No deploy, no push to `main`, no change to production data, billing, brokerage connections or external
  accounts. The branch is local (`post-demo-ultra`, upstream unset). This overrides the owner's standing
  "push finished work automatically" note for this overhaul, because every phase says "Do not deploy".
- No fabricated data, citations, metrics or test evidence. No faked streaming. Stand-in model checks are
  labelled stand-in, never live-model validation.
- No secrets or brokerage details in logs, screenshots, fixtures or reports. The repository is public.
- Legal text: inventory and propose; never rewrite the substance of Terms, Privacy or disclaimers as if
  engineering could make them compliant.
- Navigation names (rail sections, menu items, phone bar) change only on the owner's explicit yes.
- Frontend work follows the `optic-frontend` skill and `docs/frontend-v2/DESIGN-STANDARD.md`.

## Baseline

| Item | Value |
|---|---|
| Baseline commit | `9fa0f36` (origin/main, live in production since 2026-10-28, investor-readiness release) |
| Baseline tag | `post-demo-ultra-baseline` (local tag) |
| Working branch | `post-demo-ultra`, worktree `~/Optic/wt-ultra` |
| Shared checkout | `~/Optic/options-terminal` on stale local `main` (704 behind origin, 2 ahead) with other sessions' uncommitted edits: untouched, preserved |
| Python | `~/Optic/options-terminal/.venv` (symlinked into the worktree) |

## Phases

| Phase | Directive | Deliverables beyond the shared files | Status |
|---|---|---|---|
| Setup | 00, 12, 13 | branch, saved directives, tracking files, CLAUDE.md section | in progress |
| 01 Discovery and baseline | [01](directives/01-discovery-baseline.md) | FEATURE_REGISTRY, initial TEST_RESULTS, BUG_REGISTER | not started |
| 02 Advice safeguards and legal consistency | [02](directives/02-advice-elimination-legal.md) | COMPLIANCE_REVIEW.md, central AI policy, disclaimer registry | not started |
| 03 Search, ticker state, SPY default, navigation | [03](directives/03-search-ticker-navigation.md) | precedence rules, regression scenarios | not started |
| 04 Radical simplicity | [04](directives/04-radical-simplicity.md) | SIMPLICITY_AUDIT.md, before/after shots | not started |
| 05 Knowledge-level slider | [05](directives/05-knowledge-level.md) | one preference, one prompt contract | not started |
| 06 Dossier | [06](directives/06-dossier.md) | Simple/Advanced replacement, async correctness | not started |
| 07 Milo streaming and conversation | [07](directives/07-milo-streaming.md) | latency measurements, New Chat, Close | not started |
| 08 Milo grounding and evaluation | [08](directives/08-milo-knowledge-eval.md) | tool contracts, 100+ case evaluation | not started |
| 09 Market data integrity | [09](directives/09-market-data-integrity.md) | reconciliation table, caching audit | not started |
| 10 Performance, security, accessibility, polish | [10](directives/10-performance-security-a11y-polish.md) | measurements, cost model, a11y and security findings | not started |
| 11 Adversarial final audit | [11](directives/11-adversarial-final-audit.md) | FINAL_REPORT.md and the release decision | not started |

The prioritised work list for phases 02 to 11 is written at the end of Phase 01, from what discovery finds.

## Files in this folder

| File | Holds |
|---|---|
| [PROGRESS.md](PROGRESS.md) | current phase, done and not done, commits, next action (updated at every milestone) |
| [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) | every requirement with ID, status, evidence, files |
| [FEATURE_REGISTRY.md](FEATURE_REGISTRY.md) | every route, tab and control, with its data and auth needs |
| [BUG_REGISTER.md](BUG_REGISTER.md) | every defect found, P0/P1/P2, root cause, fix, verification |
| [TEST_RESULTS.md](TEST_RESULTS.md) | exact commands and outcomes, dated |
| [DECISIONS.md](DECISIONS.md) | interpretations and choices, with reasons |
| [BLOCKERS.md](BLOCKERS.md) | what cannot be done here and what would unblock it |
| [FINAL_REPORT.md](FINAL_REPORT.md) | Phase 11's report |
