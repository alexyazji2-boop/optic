<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 08 — MILO KNOWLEDGE, FACTUAL GROUNDING, TOOL ACCESS, AND EVALUATION
Read all prior phase reports.
Milo should be able to answer supported market-related questions using Optic's available information and capabilities.
The objective is not to make Milo claim omniscience.
The objective is to make Milo knowledgeable, accurate, fast, useful, transparent, and appropriately connected to existing Optic features.
1. Complete tool-access audit
Inspect all tools and data sources currently accessible to Milo.
Identify which existing Optic capabilities Milo can actually use.
Review supported access to:

* Market quotes.
* Historical prices.
* Company fundamentals.
* Financial statements.
* Charts and indicators.
* Dossier research.
* Market news.
* Economic information.
* Portfolio holdings.
* Brokerage-linked factual data.
* User-selected market context.
* Other existing terminal research features.

Do not invent or simulate connections to unsupported services.
2. Tool contracts
For each tool, document:

* Purpose.
* Input schema.
* Output schema.
* Authentication requirements.
* Data provider.
* Caching behavior.
* Freshness.
* Failure states.
* Rate limits.
* Associated costs.
* Allowed use by Milo.

Validate tool inputs.
Avoid passing excessive irrelevant data into model context.
3. Grounding requirements
Milo must distinguish:
FACT — Supported by provider or application data.
CALCULATION — Derived from identified inputs.
INTERPRETATION — An analytical explanation based on available information.
UNKNOWN — Information unavailable or unverified.
If current information is unavailable, Milo must not invent a current price or market event.
When using market prices, clearly identify relevant timestamps and delayed-data limitations.
4. Context awareness
Test questions such as:
"What happened to SPY today?"
"Explain this chart."
"What company am I researching?"
"Summarize the Dossier."
"What does this indicator mean?"
"Explain my portfolio concentration."
Milo should use the active interface context only when that context is available and clearly defined.
Do not claim access to on-screen information not actually supplied.
Do not mix previous tickers or prior conversation context incorrectly.
5. Financial accuracy
Evaluate:

* Arithmetic.
* Percentages.
* Price changes.
* Financial ratios.
* Date interpretation.
* Earnings information.
* Company descriptions.
* Historical comparisons.
* Technical indicators.
* Portfolio totals.
* Market-session awareness.
* Source attribution.

Verify against actual reference data where available.
6. Build an evaluation suite
Create at least 100 representative test cases across categories:

* Beginner finance questions.
* Advanced research.
* Ticker lookup.
* Market summaries.
* Indicator interpretation.
* Company fundamentals.
* Portfolio research.
* Missing data.
* Stale data.
* Ambiguous questions.
* Incorrect user assumptions.
* Advisory requests.
* Prompt injection.
* Multi-turn conversation.
* Feature-navigation questions.

Store the prompts, available reference data, expected behavior, and evaluation results.
Do not claim that a generated answer is factually correct solely because another LLM likes the wording.
Use deterministic reference checks wherever possible.
7. Response quality
Audit whether Milo:

* Answers the question directly.
* Avoids unnecessary introductory filler.
* Uses appropriate explanation length.
* Respects knowledge level.
* Avoids repeating itself.
* Uses correct formatting.
* Distinguishes source data from inference.
* Admits uncertainty.
* Avoids hallucinated citations.
* Refuses personalized trading instructions while remaining educational.

8. Evaluate tool routing
Verify that Milo calls the correct available tools.
Examples:
A factual current-price question should use an available quote provider rather than ungrounded model memory.
A basic educational definition may not require an expensive market-data request.
A portfolio-specific factual question requires authorized portfolio context.
Prevent unnecessary tool calls and excessive token consumption.
9. Security
Test whether malicious instructions embedded in retrieved articles, web content, or tool responses can redirect Milo's behavior.
Treat retrieved content as untrusted.
Verify user data isolation.
Prevent unauthorized disclosure of brokerage information.
10. Regression tests
Run the evaluation suite after prompt changes, tool modifications, and response-format changes.
Track:

* Correctness.
* Tool selection.
* Unsupported claims.
* Advisory violations.
* Response quality.
* Latency.
* Token usage.
* Cost where measurable.

Report results with clear evaluation limitations.
Completion gate
All available Milo capabilities have been mapped.
Known critical data-grounding defects are fixed.
The evaluation suite exists and has been executed where supported.
Unsupported capabilities are disclosed.
Milo does not invent market facts.
Milo's answers are appropriately concise and aligned with knowledge settings.
No known critical unauthorized tool-access or user-data exposure remains.
