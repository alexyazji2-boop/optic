# Milo evaluation suite: report

Run 2026-11-02 20:35 on fixtures (`tests/milo_eval`), 181 cases, 7 s. No model was called.

## Automated checks (executed)

| Family | Passed | Checks |
|---|---|---|
| tool_selection | 246 | 246 |
| factual_support | 130 | 130 |
| calculation | 27 | 27 |
| freshness | 146 | 146 |
| authorization | 34 | 34 |
| injection | 2 | 2 |
| citation_plumbing | 362 | 362 |
| policy | 53 | 53 |
| level | 50 | 50 |
| budget | 181 | 181 |

## Scores by the directive's dimensions (request level, 0 to 100)

Each dimension is the share of request-level checks that feed it which passed. Answer relevance and context
correctness beyond what the request carries need an answer, so they are not scored here.

| Dimension | Score | Checks |
|---|---|---|
| factual_accuracy | 100.0 | 157 |
| source_grounding | 100.0 | 508 |
| tool_correctness | 100.0 | 246 |
| answer_relevance | not executed (needs a model) | 0 |
| clarity | 100.0 | 50 |
| instruction_compliance | 100.0 | 234 |
| context_correctness | not executed (needs a model) | 0 |
| safety | 100.0 | 36 |

## Critical failures (reported apart, never averaged in)

None.

## The directive's suites (Part 4.3)

| Suite | Cases passing every check | Cases | Minimum |
|---|---|---|---|
| Financial education | 16 | 16 | 15 |
| Market data and ticker questions | 32 | 32 | 20 |
| Company fundamentals | 17 | 17 | 15 |
| Technical analysis | 16 | 16 | 15 |
| Dossier interpretation | 17 | 17 | 15 |
| Portfolio factual research | 17 | 17 | 15 |
| Multi-turn context retention | 15 | 15 | 15 |
| Missing or stale data | 15 | 15 | 10 |
| Personalized advice prevention | 13 | 13 | 10 |
| Prompt injection and adversarial input | 15 | 15 | 15 |
| Product feature and navigation questions | 8 | 8 | 5 |

| Category | Cases passing every check | Cases |
|---|---|---|
| Beginner finance questions (beginner) | 15 | 15 |
| Advanced research (advanced) | 8 | 8 |
| Ticker lookup (ticker_lookup) | 8 | 8 |
| Market summaries (market_summary) | 7 | 7 |
| Indicator interpretation (indicator) | 13 | 13 |
| Company fundamentals (fundamentals) | 12 | 12 |
| Portfolio research (portfolio) | 11 | 11 |
| Missing data (missing_data) | 8 | 8 |
| Stale data (stale_data) | 6 | 6 |
| Ambiguous questions (ambiguous) | 6 | 6 |
| Incorrect user assumptions (wrong_assumption) | 6 | 6 |
| Advisory requests (advisory) | 12 | 12 |
| Prompt injection (injection) | 14 | 14 |
| Multi-turn conversation (multi_turn) | 15 | 15 |
| Feature-navigation questions (navigation) | 8 | 8 |
| Context awareness (section 4) (context) | 8 | 8 |
| Financial accuracy of tool figures (section 5) (accuracy) | 8 | 8 |
| User data isolation (section 9) (isolation) | 6 | 6 |
| Dossier interpretation (Phase 12) (dossier) | 10 | 10 |

## Latency (measured, fixtures, no network, no model)

* Request assembly through `/api/chat`: median 0.009 s, p95 0.011 s, max 1.523 s (181 cases).
* Tool calls through the toolbox: median 0.0008 s, max 1.513 s (56 calls).

## Request size and estimated cost per answer (sizes measured, tokens and cost estimated)

* Characters sent per request (system prompt, CONTEXT, tools): median 68,412, max 83,981.
* Estimated input per answer 38,006 tokens median (two model rounds, base prompt cached), output 1,200 tokens assumed.
* Estimated cost per answer: median $0.0313, max $0.0486, at $2 / $10 per million tokens in / out and cached input at $0.10.

## Answer-level checks (not executed)

150 answer checks are defined across the cases (`answer_checks.py`), with 798 outcomes named unacceptable. None ran: no model can be called on this machine (BLOCKERS BL-01), so there are no answers to check. Correctness of answers, unsupported claims in answers, advice in answers and answer quality are therefore NOT TESTED; the request-level checks above are what was measured.

## Failures

None.
