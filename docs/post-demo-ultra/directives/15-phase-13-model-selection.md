<!-- Saved verbatim from the owner's chat message of 2026-11-02, sent while Phase 12 was starting. Do not edit. -->

OPTIC — PHASE 13: MILO MODEL EVALUATION, QUALITY STANDARDS, ACCEPTABLE ERROR POLICY & COST OPTIMIZATION
MISSION
Determine whether the current LLM powering Milo is the best option for Optic's financial research use case.
Do not assume the existing model is optimal.
Do not recommend an alternative based solely on general-purpose benchmarks, marketing claims, or perceived intelligence.
You must establish Optic-specific quality standards, build reproducible evaluations, compare suitable models under equivalent conditions, measure real operating costs, and recommend the best architecture.
Read all previous audit reports, especially Phase 12's Milo evaluation and security findings.
Reuse its datasets, security tests, and evaluation infrastructure rather than creating a second disconnected framework.
This is a test-driven engineering and model-selection assignment.
Do not change Milo's production model without my explicit approval.
PART 1 — IDENTIFY MILO'S CURRENT MODEL AND ARCHITECTURE
Inspect the actual codebase.
Determine:

* Exact LLM provider.
* Configured model identifier.
* Model version or snapshot.
* System and developer prompts.
* Tool-calling implementation.
* Retrieval architecture.
* Financial-data integrations.
* User-context construction.
* Conversation-history handling.
* Streaming infrastructure.
* Token consumption.
* API cost.
* Fallback logic.
* Provider rate limits.

Confirm whether Sonnet 5.5 currently powers Milo. Do not assume that it does.
Distinguish the model running Claude Code from the API model used by Milo.
Trace at least three representative user queries through the actual system to understand where latency, cost, and factual errors originate.
Document the findings.
PART 2 — DEFINE MILO'S REQUIRED PERFORMANCE STANDARD
Answer:
What level of intelligence, accuracy, reliability, and speed does Milo need to provide a compelling financial research experience?
Separate workloads into:

1. Basic financial education.
2. Real-time or recent market information.
3. Company fundamentals.
4. Technical indicator explanations.
5. Dossier research.
6. Connected portfolio interpretation.
7. Multi-source financial research.
8. Multi-turn reasoning.
9. Platform navigation and help.
10. Questions requiring unavailable information.

For each workload, specify:

* Expected behavior.
* Required data sources.
* Tool requirements.
* Appropriate reasoning depth.
* Accuracy criteria.
* Response latency target.
* Financial risk level.
* Appropriate explanation length.
* Prohibited behavior.
* Evaluation method.

Do not treat all questions as equally difficult or equally risky.
For example, explaining what RSI means is a different task from accurately calculating portfolio concentration using connected brokerage data.
PART 3 — DEFINE ACCEPTABLE AND UNACCEPTABLE MISTAKES
Create a severity-based AI error policy.
Severity 0 — Critical
Examples:

* Unauthorized user-data disclosure.
* Materially incorrect financial figures presented as verified.
* Fabricated current prices.
* Fabricated source citations used to support consequential claims.
* Prohibited personalized investment instructions.
* Unauthorized tool execution.

These are release-blocking defects.
Severity 1 — Major
Examples:

* Incorrect answer to an important research question.
* Incorrect ticker or company context.
* Missing critical risk or uncertainty information.
* Wrong tool selection producing unreliable analysis.
* Incorrect numerical calculations that meaningfully affect the answer.

These require correction and targeted regression tests.
Severity 2 — Moderate
Examples:

* Incomplete but nonmisleading analysis.
* Missing secondary context.
* Excessive verbosity.
* Poor explanation at the selected knowledge level.
* Unnecessary tool calls.

These should be tracked and improved.
Severity 3 — Minor
Examples:

* Slightly awkward formatting.
* Minor stylistic inconsistency.
* Nonessential repetition.

These should not block release independently.
Create concrete examples and severity criteria.
Determine which mistakes are categorically prohibited and which can be tolerated at controlled frequencies.
Do not use average benchmark scores to conceal critical failures.
PART 4 — BUILD A MODEL-INDEPENDENT TEST HARNESS
The evaluation infrastructure must support more than one LLM provider.
Reuse the existing Milo evaluation dataset.
Expand it where necessary to include realistic and difficult Optic-specific questions.
For every test case, record:

* Test identifier.
* Workload category.
* Difficulty.
* Risk level.
* User question.
* Conversation context.
* Knowledge level.
* Available reference data.
* Authorized tools.
* Expected factual answer or acceptable answer criteria.
* Prohibited outcomes.
* Evaluation rubric.
* Model response.
* Tool calls.
* Latency.
* Token usage.
* Estimated cost.
* Result.

Use deterministic checks for calculations, citations, and tool authorization.
Use human-reviewed rubrics for clarity, reasoning quality, and usefulness.
If an LLM judge is used, identify it, calibrate it against human-reviewed samples, and disclose its limitations.
Run repeated trials for nondeterministic tasks.
Use separate development and held-out evaluation sets to reduce benchmark overfitting.
Do not alter evaluation criteria after seeing model results merely to favor a particular provider.
PART 5 — EVALUATE CLAUDE SONNET 5.5
If Sonnet 5.5 is currently powering Milo, establish its performance baseline.
If it is not, evaluate it as a candidate where authorized API access exists.
Measure:

1. Financial factual accuracy.
2. Tool selection correctness.
3. Mathematical correctness.
4. Source grounding.
5. Hallucination frequency.
6. Multi-turn context accuracy.
7. Financial-advice safeguard performance.
8. Data-access security behavior.
9. Beginner explanation quality.
10. Advanced explanation quality.
11. Time to first token.
12. Total response latency.
13. Cost per completed task.
14. Error and timeout rates.

Report the exact model version and configuration.
Do not claim Sonnet 5.5 meets Optic's standards without actual test evidence.
PART 6 — IDENTIFY AND COMPARE ALTERNATIVE MODELS
Research suitable currently available models from authorized providers.
Consider relevant categories:

* Higher-capability proprietary models.
* Mid-tier proprietary models.
* Lower-cost lightweight models.
* Open-weight models.
* Self-hosted models where technically practical.

Include candidates from Anthropic, OpenAI, Google, and suitable open-weight providers where supported by the actual integration requirements.
Verify current model identifiers, tool-calling support, context limits, API availability, pricing, and applicable data-handling terms.
Do not invent model capabilities or pricing.
Use equivalent evaluation conditions where possible:

* Same test questions.
* Same financial reference data.
* Same authorized tools.
* Comparable prompt instructions.
* Equivalent conversation context.
* Appropriate provider-specific configuration.
* Comparable measurement methodology.

Do not disadvantage a candidate through an incompatible tool format or invalid parameter configuration.
Do not assume every model requires identical prompting to perform optimally. Document justified adaptations.
Separate model capability from failures caused by Optic's retrieval, prompts, or tool infrastructure.
PART 7 — COST-PER-QUALITY EVALUATION
Do not select models based only on price per million tokens.
Calculate the actual cost of completing useful Optic tasks.
Include:

* Input tokens.
* Output tokens.
* Reasoning tokens or other billable usage where applicable.
* Cached tokens.
* Tool calls.
* Retries.
* Failed requests.
* Relevant infrastructure costs.
* External data-provider requests.

For open-weight models, account for:

* Hosting.
* GPU or compute requirements.
* Scaling.
* Maintenance.
* Operational reliability.
* Engineering overhead.

Model realistic workload mixes.
Estimate costs at:

* 100 monthly active users.
* 1,000 monthly active users.
* 10,000 monthly active users.

Use explicit assumptions for queries per user, token consumption, tool usage, and peak concurrency.
Create cost-versus-quality comparisons.
Identify the cheapest model that satisfies each workload's quality and safety requirements.
Do not make purchases or generate substantial paid evaluation traffic without approval.
Use available mocks, fixtures, and locally authorized testing to prepare the comparison harness first.
PART 8 — EVALUATE INTELLIGENT MODEL ROUTING
Determine whether Milo would benefit from using different models for different tasks.
Example architecture to evaluate:
Simple financial definitions
Potentially routed to a smaller, cheaper model.
Routine market-data explanations
Potentially routed to a fast model with verified tools.
Complex multi-source financial research
Potentially routed to a higher-capability reasoning model.
Simple product-navigation questions
Potentially answered through deterministic retrieval or application logic without an expensive model.
High-risk or unsupported requests
Handled through appropriate safeguards, clarification, refusal, or escalation rather than simply selecting a more powerful model.
Do not implement this architecture automatically.
First determine whether it produces meaningful improvements compared with one model.
Evaluate:

* Routing accuracy.
* Added latency.
* Cost savings.
* Reliability.
* Additional maintenance burden.
* Security consistency.
* User experience.
* Regression risk.

Recommend intelligent routing only if the test results justify its complexity.
PART 9 — QUALITY GATES AND STATISTICAL VALIDATION
Establish measurable release standards.
Use initial proposed targets as hypotheses, not guaranteed capabilities:

* At least 98% correctness on verified financial factual claims.
* At least 99% correct tool selection on applicable cases.
* No observed fabricated current prices in release-gate tests.
* No confirmed cross-user data-access vulnerabilities.
* No prohibited personalized trading instructions in release-gate tests.
* At least 90% passing relevance and clarity rubrics.

Review whether these thresholds are appropriate for each risk category.
Calculate confidence intervals where feasible.
Do not claim that zero observed failures means zero underlying risk.
Report sample sizes and limitations.
Require additional testing for high-risk workloads.
Where benchmarks are too small to support reliable conclusions, identify the uncertainty instead of manufacturing confidence.
PART 10 — PROVIDE AN EVIDENCE-BASED MODEL RECOMMENDATION
The final report must directly answer:
1. What standard must Milo meet?
Specify requirements by workload and risk level.
2. What mistakes are acceptable?
Provide the formal error-severity policy.
3. Does Claude Sonnet 5.5 meet the standards?
Answer using measured results.
4. If not, what other models might qualify?
Rank candidates based on completed evaluations, not reputation.
5. If Sonnet 5.5 qualifies, are there cheaper alternatives that also qualify?
Compare real task-level costs and relevant quality differences.
6. Should Milo use one model or multiple models?
Provide an architecture recommendation backed by evidence.
7. What improvements should be made to Milo independent of model choice?
Identify weaknesses in prompts, retrieval, tools, caching, authorization, or data quality that a model swap alone would not fix.
REQUIRED DELIVERABLES
Create:

* `docs/ai/MILO_QUALITY_STANDARDS.md`
* `docs/ai/MILO_ACCEPTABLE_ERROR_POLICY.md`
* `docs/ai/MILO_MODEL_COMPARISON.md`
* `docs/ai/MILO_COST_ANALYSIS.md`
* `docs/ai/MILO_ROUTING_RECOMMENDATION.md`
* `docs/ai/MILO_PHASE_13_FINAL_REPORT.md`

Implement reusable benchmark code and appropriate test fixtures.
Produce machine-readable test results where possible.
Provide a final recommendation with:

* Best-performing tested model.
* Lowest-cost qualifying tested model.
* Best quality-to-cost option.
* Recommended architecture.
* Expected operating-cost assumptions.
* Critical remaining uncertainties.
* Required human review.
* Required approval before changing production.

Never fabricate benchmark outcomes.
Do not change Milo's production model.
Do not deploy.
Begin with the actual Milo architecture and existing evaluation datasets, then build the comparison framework and run only authorized tests. DO NOT START UNTIL EVERYTHING FROM PHASE 12 HAS BEEN COMPLETED.
