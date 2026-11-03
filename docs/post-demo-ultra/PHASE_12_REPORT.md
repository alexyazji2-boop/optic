# Phase 12 report: writing, Milo's evaluation, and the red team

Directive 14 (`directives/14-phase-12-writing-eval-security.md`), 2026-11-02, branch `phase-12-writing-milo-security`
in `~/Optic/wt-phase12`, cut from live `main` at `d22522a`. Nothing was pushed or deployed, and no production data,
account, billing or brokerage setting was touched. The detail is in the deliverables:

| Deliverable | What it holds |
|---|---|
| `docs/editorial/OPTIC_WRITING_STANDARDS.md` | Optic's voice, the fifteen rules, levels, terms, errors, AI writing, sources, prohibited claims, the workflow |
| `docs/editorial/WRITING_CORRECTIONS.md` | Every correction: was, now, why, where, rule; and what was flagged instead |
| `docs/editorial/inventory/` | The generated inventory: `TEXT_INVENTORY.md`, `text_inventory.csv` (route, file and line, kind, words, problems, suggestion, status), `stats.json` |
| `docs/ai/MILO_ARCHITECTURE_AUDIT.md` | Provider, models, parameters, prompts, tools, retrieval, memory, citations, streaming, errors, usage, limits |
| `docs/ai/MILO_EVALUATION_RESULTS.md` | The benchmark, its baseline and results, the advice sets, performance, the runner, regression commands |
| `docs/security/MILO_DATA_ACCESS_MAP.md` | Every pathway, what leaves the server, data classes, authorization checks |
| `docs/security/MILO_RED_TEAM_REPORT.md` | Findings MRT-01 to MRT-10, the standing boundaries, release gates, remaining risks |

## The nineteen answers (directive 14, final report requirements)

1. **User-facing text sources inventoried:**
   - 18,036 texts from 321 files: 123 client scripts, 2 HTML shells and 196 server modules;
   - by kind: 12,758 client, 5,135 server, 125 legal and 18 model prompts, each traced to its constant;
   - by app: 7,378 in v2 and 5,505 in Classic;
   - rendered text of 27 routes captured at three levels (81 captures).
2. **Reviewed:**
   - all 18,036 by the deterministic checker;
   - line by line: Home, the Overview, the Milo panel and every model prompt (by me), and 25 more pages (by an
     independent copy editor working from the captures).
3. **Revised:**
   - 81 corrections, each recorded with its reason and rule (WRITING_CORRECTIONS A to L): 6 model-instruction
     changes, plus a shared writing block for every model request; 75 interface and server-copy corrections;
   - 9 findings flagged for the owner or counsel instead (section M).
4. **Recurring writing problems:**
   - the same point said twice (the copy editor's commonest finding, 15 cases);
   - claims nothing measures, coaching, and development notes in reader copy (15). Five of these were advice:
     "size down and widen stops", "Favor the strongest" (BUG-210);
   - templates that break on real data: "in 0 days", "1 sessions", lowercased names (8);
   - comma-heavy nested sentences;
   - in the prompts: duplicated voice rules, invitations to ellipses and capitals, and a fixed closing heading that
     restated each answer.

   Stock AI phrases ("cutting-edge", "It's important to note") were nearly absent: 0 in v2.
5. **Editorial workflow:**
   - deterministic rules over the directive's families (`tests/editorial/rules.py`);
   - the extractor and inventory (`extract.py`, `review.py inventory`);
   - a diff reviewer for a branch's new copy (`review.py diff`), with an optional, capped model read (`--ai`);
   - a suite gate with a reasoned allow list (`tests/test_editorial_standards.py`, `allow.txt`);
   - the standards and the corrections library;
   - one set of writing rules on every model request (`app/editorial.py`).
6. **Benchmark cases:** 181 in the directive's eleven suites. That is Phase 08's 137 plus 44 new, every suite at or
   above its minimum, with the directive's fields on each case (benchmark `milo-bench-2026-11-02.1`).
7. **Evaluations executed:**
   - request level: the 181 cases with their 1,231 checks, three times (live `main`'s code, after the fixes, the
     final tree);
   - advice checks: two unseen sets of 220 items (E scored twice while unread, F once on each version), four
     development sets and a 1,506-sentence research corpus;
   - end to end: 72 answers with the stand-in model;
   - answer level: none. No model can be called (BL-01, rechecked: still 401).
8. **Accuracy and quality:**
   - request level, live `main` against now: 173 to 181 of 181 cases, safety 94.4 to 100, instruction compliance
     97.4 to 100, factual accuracy, grounding, tool correctness and clarity 100 and 100;
   - critical failures: two before (POR-10, INJ-11), none now;
   - advice recall on the held-out set F: request reader 18% to 30%, output check 24% to 32%, with no new false
     positive;
   - answer accuracy, relevance and grounding: NOT TESTED.
9. **Measured performance** (local, stand-in model, real providers, network-dependent):
   - first text: median 0.31 s, p95 4.67 s;
   - total: median 0.65 s, p95 4.98 s;
   - 0 errors and 0 timeouts in 72;
   - the advice gate's hold: median 155 ms;
   - request assembly on fixtures: median 9 ms;
   - cost per answer: estimated $0.031 from request size, against the live ledger's measured ~$0.11 (the ledger is
     the figure to use).
10. **Data-access pathways inventoried:** 11 inbound (P1 to P11) and 6 outbound destinations, each with its
    authorization check (MILO_DATA_ACCESS_MAP).
11. **Security tests executed:**
    - 38 red-team tests: reproductions, standing boundaries, fake secrets and conversation isolation;
    - the benchmark's 15 adversarial and 17 portfolio cases;
    - mutation checks of every fix, which restored live `main`'s files and saw the tests fail.
12. **Vulnerabilities discovered:** 10.
    - 2 High: MRT-01, a forged event in the shared framework read and the forecast record; MRT-10, the advice
      safeguards' recall.
    - 2 Medium: MRT-02, a link that hides its host; MRT-03, Classic's history on a failed switch.
    - 6 Low: MRT-04 to MRT-09.
13. **Fixed:** 7: MRT-01, 02, 03, 04, 05, 08 and 09, each verified by a test that fails on the old code. MRT-10 was
    improved but stays open.
14. **Outstanding security risks:**
    - MRT-10, which waits on a model-based check (BL-07) and a key (BL-01);
    - the model's behaviour under injection, unmeasured;
    - model-written web search queries as a channel;
    - MRT-06, the device shelves at sign-out (the owner's call);
    - MRT-07, accepted;
    - minimisation in the portfolio's performance part;
    - no third-party penetration test or dependency scan (BL-12).
15. **Features not fully tested:**
    - every Milo answer, and therefore relevance, clarity, carry-over and adherence;
    - web search and deep research with a model; attachments with a model;
    - a real brokerage link (sandbox only, BL-03);
    - Classic's copy, reviewed but not edited by rule;
    - legal text (counsel's);
    - real phones and the iPhone app.
16. **Files modified:**
    - 17 server modules (`app/`, `app/editorial.py` new);
    - 27 v2 scripts and `static/app.js`;
    - 13 existing test files changed;
    - new: `tests/editorial/` (extractor, rules, reviewer, allow list), `tests/test_editorial_standards.py`,
      `tests/test_milo_redteam.py`, `tests/test_ai_policy_requests.py` and the set E fixture in
      `tests/milo_eval/advice_sets/`;
    - the docs above, the two directives saved verbatim, and the tracking files (PROGRESS, BUG_REGISTER BUG-203 to
      216, DECISIONS D-102 to 111, TEST_RESULTS, BLOCKERS).
17. **Tests:** baseline 8,230 passed and 1 skipped. Final: **8,628 passed, 1 skipped, 0 failed** (249 s). The 398
    new tests are the editorial gate and rules, the red team, the policy's request sets and the benchmark's new cases.
18. **Git commit:** `35348c98` (Phase 12's work); the commit after it records that id and adds the archived
    benchmark run, `docs/ai/eval-results/milo-bench-2026-11-02.1/` (folder named by time and commit).
19. **Readiness for human staging review:**
    - **This branch:** ready for a human staging review. Its suite is green, the changed pages were checked in a
      browser at three sizes, and nothing is deployed.
    - **Production:** the overhaul's decision stands, **NOT READY** (FINAL_REPORT). The advice safeguards, now
      measured on two unseen sets, are the clearest reason. They need the owner's decision on a model-based check
      and a working key, and with those, a run of `run_model.py` on the 181 cases.

## Acceptance criteria (directive 14)

| Criterion | Status | Evidence |
|---|---|---|
| The copy has been systematically reviewed | PASS | the inventory; 27 routes read at three levels |
| Repetitive AI-writing patterns meaningfully reduced | PASS for the copy read; Classic by rule NOT TESTED | WRITING_CORRECTIONS; the gate |
| Terminology accurate; financial and legal information intact | PASS | no figure, source or time changed; legal text flagged, not rewritten |
| A reusable editorial process exists | PASS | the checker, the diff reviewer, the gate, the standards, the library |
| Milo has a reproducible benchmark | PASS | 181 cases, versioned, archived runs |
| Major capabilities evaluated, results measurable | PARTIAL | request level and safeguards measured; answers BLOCKED (BL-01) |
| Failures documented; tests rerunnable | PASS | MILO_EVALUATION_RESULTS; the commands there |
| Accessible data sources mapped; authorization boundaries evaluated | PASS | MILO_DATA_ACCESS_MAP |
| Cross-user isolation tested with synthetic data | PASS | readers A and B, every portfolio part, scope ids, history |
| Prompt injection tested | PASS at the server; the model's behaviour BLOCKED | the red team; INJ cases |
| No known critical data-disclosure vulnerability unmitigated in the tested environment | PASS | MRT-01 to 09; MRT-10 is a safeguard gap, not a disclosure |
| Relevant tests pass; changes documented | PASS | the suite; this folder |
| No production data modified; no deployment | PASS | nothing pushed |
| Remaining limitations identified | PASS | items 14 and 15 above |
