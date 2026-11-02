<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 06 — DOSSIER SIMPLICITY, ANALYSIS REPLACEMENT, AND RELIABILITY OVERHAUL
Read all previous phase reports.
Your assignment is to rebuild the presentation and interaction logic of the Dossier experience without sacrificing reliable analytical functionality.
The investor demonstration revealed:

1. Dossier search was inconsistent.
2. Simple Analysis was not simple enough.
3. Show Advanced Analysis did not behave as expected.
4. The analytical interface required too much reading.

Fix all four issues thoroughly.
1. Inspect the Dossier pipeline
Map:

* Symbol selection.
* Data requests.
* Financial-data normalization.
* AI generation.
* Prompt templates.
* Caching.
* Loading states.
* Rendering.
* Analysis mode state.
* Error handling.
* Source attribution.

Identify where incorrect or stale information can enter the pipeline.
2. Simple Analysis redesign
The default analysis must be understandable to a beginner.
Use a concise information hierarchy such as:
WHAT'S HAPPENING?
A short explanation of the relevant market or company information.
WHY DOES IT MATTER?
An understandable description of the important supporting context.
WHAT ELSE SHOULD I KNOW?
Relevant uncertainty, limitations, or additional facts.
Avoid excessive paragraphs and unnecessary terminology.
Use the user's selected knowledge level.
Do not present speculative claims as facts.
Do not provide personalized investment recommendations.
3. Advanced Analysis behavior
The Show Advanced Analysis button must replace the displayed Simple Analysis.
It must NOT append a second section below the first.
Expected interaction:

* Simple Analysis is visible initially.
* User clicks Show Advanced Analysis.
* The existing content area transitions to Advanced Analysis.
* Simple Analysis is no longer simultaneously displayed.
* The button becomes Show Simple Analysis.
* Clicking it restores the simple content.
* Ticker selection remains unchanged.
* The page does not unexpectedly jump.
* No duplicate analysis sections appear.

Use a single authoritative mode state.
Consider separate state for analysis data and visible presentation mode.
Do not trigger repeated paid AI calls when previously generated valid content can safely be reused.
4. Async correctness
Test ticker changes while:

* Simple Analysis is loading.
* Advanced Analysis is loading.
* The user switches analysis modes.
* A provider request fails.
* A cached response becomes stale.
* The user navigates away and returns.

Ensure that responses are associated with the correct ticker, request identity, data timestamp, and analysis mode.
Do not render results belonging to a previously selected ticker.
5. Advanced Analysis design
Advanced Analysis should offer genuinely deeper research.
Retain accurate existing functionality such as:

* Financial metrics.
* Fundamental context.
* Technical indicators.
* Historical comparisons.
* Risk and volatility measures.
* Source information.
* Relevant assumptions.

Only expose features supported by actual available data.
Do not fabricate unsupported metrics.
Organize advanced content into clearly separated, understandable sections.
Avoid creating an excessively long unstructured essay.
6. Search regression verification
Confirm the Phase 03 search fixes remain working.
Test:

* Direct ticker search.
* Company-name search.
* Rapid switching.
* Invalid ticker.
* Browser refresh.
* Back/forward navigation.
* Search during analysis loading.

7. Visual and motion refinement
Implement a restrained transition between Simple and Advanced views.
Avoid:

* Flickering.
* Layout jumps.
* Duplicate loading indicators.
* Excessively slow animations.
* Unnecessary scroll movement.
* Incorrect content height calculations.

Respect reduced-motion settings.
8. Accuracy and source validation
Check representative Dossier outputs against provider responses.
Verify:

* Numerical calculations.
* Company identities.
* Dates.
* Data freshness.
* Indicator interpretation.
* Source references.
* Missing-data behavior.

Never display fabricated market information.
9. Required tests
Add tests for:

* Simple-to-advanced transition.
* Advanced-to-simple transition.
* Exactly one visible analysis mode.
* Correct selected ticker.
* Failed data requests.
* Rapid ticker changes.
* Knowledge-level behavior.
* Stale response prevention.
* Data accuracy where verifiable.

Completion gate
Dossier search works.
Simple Analysis is genuinely easy to understand.
Advanced Analysis replaces Simple Analysis correctly.
There is no duplicated analysis.
The interface is visually simpler.
Underlying data and AI statements remain reliable.
Relevant browser and regression tests pass.
