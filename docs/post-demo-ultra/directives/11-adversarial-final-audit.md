<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 11 — ADVERSARIAL FINAL AUDIT, COMPLETE REGRESSION TESTING, AND INVESTOR READINESS
Read the master engineering instructions and ALL previous phase reports.
You are now acting as an independent QA lead reviewing the work completed by the engineering team.
Do not assume previous phases were successful.
Do not trust previous PASS labels without reviewing their evidence.
Your mission is to find every remaining defect that could harm a real user's experience or undermine confidence during an investor demonstration.
1. Full independent feature verification
Use FEATURE_REGISTRY.md.
Review EVERY inventoried feature.
For each feature, verify:

* It renders correctly.
* It accepts expected input.
* Its primary interaction works.
* Its output is correct.
* Its loading state works.
* Its error state works.
* Its empty state works.
* Its navigation works.
* It does not generate console errors.
* It does not break on refresh.
* It behaves correctly with realistic user interactions.
* Its responsive presentation remains usable.

Do not sample only a handful of features and claim the entire terminal works.
Record untested features separately.
2. Complete requirements verification
Use REQUIREMENTS_MATRIX.md.
Every requirement must have:

* A status.
* Actual evidence.
* A test reference.
* Relevant changed files.
* Remaining limitations.

No requirement may remain marked PASS based solely on code inspection when behavioral testing is necessary.
3. Critical investor-demo workflow
Execute the following complete user journey:
STEP 1 — Open Optic as a new user.
Verify the homepage is understandable, attractive, and functional.
STEP 2 — Interact with the knowledge-level preference.
Verify the explanation style changes appropriately.
STEP 3 — Search for SPY.
Verify SPY loads correctly and displays supported market information.
STEP 4 — Search for a different ticker.
Verify all relevant components update correctly.
STEP 5 — Open Dossier.
Verify the selected company and research information are correct.
STEP 6 — Read Simple Analysis.
Verify a beginner can understand the writing without unnecessary jargon.
STEP 7 — Click Show Advanced Analysis.
Verify advanced analysis REPLACES simple analysis.
STEP 8 — Return to Simple Analysis.
Verify there is no duplicate content or state corruption.
STEP 9 — Open Milo.
Ask a basic market question.
Verify smooth streaming and factual grounding.
STEP 10 — Ask Milo a more advanced question.
Verify appropriate tool use, source transparency, and financial accuracy.
STEP 11 — Create a New Chat.
Verify conversation isolation.
STEP 12 — Close Milo.
Verify the interface closes appropriately without corrupting history.
STEP 13 — Reopen Milo.
Verify appropriate conversation restoration.
STEP 14 — Test brokerage linking.
Use approved sandbox, demo, or synthetic account data.
Verify accurate connection states and portfolio calculations.
Do not use live brokerage credentials without authorization.
STEP 15 — Navigate through other major terminal features.
Verify navigation, data loading, and visual consistency.
4. Repeatability tests
Run the critical demo journey multiple times.
Test:

* Fresh browser session.
* Existing authenticated session.
* Normal network.
* Simulated slow network.
* Desktop viewport.
* Laptop viewport.
* Mobile viewport.
* Browser refresh.
* Back and forward navigation.
* Concurrent API requests.
* Provider failure scenarios.

Document exactly which scenarios were executed.
5. Independent adversarial testing
Actively attempt to break the terminal through legitimate user interaction.
Examples:

* Change tickers rapidly.
* Submit repeated Milo prompts.
* Close Milo while streaming.
* Refresh during Dossier loading.
* Open multiple tabs.
* Use invalid symbols.
* Switch knowledge levels during analysis.
* Navigate during pending API calls.
* Disconnect network access.
* Submit unusually long input.
* Use keyboard-only navigation.
* Trigger missing-data states.

Look for race conditions and inconsistent state.
6. Financial correctness
Check representative information against actual configured providers.
Verify:

* Correct ticker.
* Correct company.
* Correct data timestamp.
* Accurate calculations.
* No fabricated metrics.
* No stale analysis attached to a new ticker.
* No contradictory cross-feature data without explanation.

7. AI evaluation
Run the Milo evaluation suite created in Phase 08.
Include:

* Educational finance questions.
* Company research.
* Current data requests.
* Missing information.
* Adversarial advice requests.
* Prompt-injection attempts.
* Multi-turn conversations.
* Portfolio-specific factual research.

Document failures honestly.
8. Simplicity regression
Return to the original investor feedback.
Check specifically:

* Does the homepage still feel overwhelming?
* Are users forced to read too much?
* Are there unnecessary technical labels?
* Do multiple features compete for attention?
* Is Simple Analysis truly simple?
* Are advanced controls optional?
* Is the platform's value proposition immediately apparent?
* Does Milo produce overly long answers?
* Are important numbers easy to interpret?
* Is navigation intuitive?

Do not allow technical correctness to conceal poor usability.
9. Release-blocking defect classification
P0 — Security exposure, materially incorrect financial data, personalized advisory behavior in prohibited workflows, broken core navigation, critical authentication defects, or unrecoverable major failures.
P1 — Reproducible core workflow bugs, substantial usability failures, important accessibility barriers, or significant performance regressions.
P2 — Minor visual inconsistencies and noncritical refinements.
Address all reasonably reproducible P0 defects within the authorized local scope.
Fix P1 defects where feasible.
Record remaining P2 issues.
Never reclassify a serious issue merely to make the project appear complete.
10. Run full engineering checks
Execute the available:

* Production build.
* Type checking.
* Linting.
* Unit tests.
* Integration tests.
* End-to-end tests.
* Financial calculations tests.
* Milo evaluation suite.
* Search tests.
* Dossier tests.
* Accessibility tests.
* Visual regression checks.
* Security checks.

Report exact commands and outcomes.
11. Final deliverables
Update:

* FINAL_REPORT.md
* TEST_RESULTS.md
* BUG_REGISTER.md
* REQUIREMENTS_MATRIX.md
* PROGRESS.md
* BLOCKERS.md

Include:

1. Number of inventoried features.
2. Number of tested features.
3. Number passing.
4. Number failing.
5. Number blocked.
6. Number not tested.
7. Number of bugs fixed.
8. Remaining P0 issues.
9. Remaining P1 issues.
10. Milo evaluation results.
11. Market-data verification findings.
12. Simplicity improvements.
13. Performance measurements.
14. Security findings.
15. Legal-review dependencies.
16. Relevant Git commits.
17. Production readiness recommendation.

Do not fabricate measurements or percentages.
12. Final engineering decision
Provide one of these outcomes:
READY FOR HUMAN STAGING REVIEW
OR
NOT READY — BLOCKING ISSUES REMAIN
Do not declare the application fully production-ready merely because automated tests pass.
Explicitly identify any required manual legal, security, user-acceptance, or external-provider verification.
Do not deploy to production.
The final objective is a terminal that is simpler, more reliable, more accurate, and demonstrably improved after the investor feedback.
Begin the independent audit now. Do not stop at reviewing documentation. Reproduce problems, fix authorized local defects, run the tests again, and document the actual results.
