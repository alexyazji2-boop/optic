<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 05 — RESTORE KNOWLEDGE-LEVEL PERSONALIZATION
Read all previous phase reports.
In Classic Optic, the homepage contained a feature asking users how they wanted Optic to communicate.
Find the original implementation in the repository or Git history.
Restore and improve this capability using a polished five-position slider.
1. Required knowledge levels
Level 1: New to Markets.
Use basic everyday English and define financial terminology.
Level 2: Beginner.
Use simple explanations and introduce essential terminology.
Level 3: Intermediate.
Use balanced financial terminology and explanatory context.
Level 4: Advanced.
Use professional technical language and deeper analytical reasoning.
Level 5: Expert.
Use concise, precise financial research language with advanced metrics where relevant.
2. UI implementation
The slider must:

* Have five discrete positions.
* Display the selected level.
* Provide a short preview of the explanation style.
* Be visually consistent with Optic.
* Support keyboard and touch navigation.
* Include accessible labels.
* Work across responsive viewports.
* Avoid intrusive onboarding.
* Be editable later through Settings.

Use native accessible controls or an established accessible component where appropriate.
3. Persist user preferences
Create a single authoritative preference.
For authenticated users, persist it through the existing approved settings architecture.
For guests, use an appropriate existing persistence mechanism.
Handle unavailable persistence gracefully.
Avoid storing separate contradictory values in different components.
4. Apply globally
The preference must affect explanatory content in:

* Milo.
* Dossier simple analysis.
* Dossier advanced explanation wording.
* Market summaries.
* Relevant chart explanations.
* Portfolio research explanations.
* Educational articles.
* Other discovered AI-generated explanatory features.

Do not force the preference into raw data tables where no text adaptation is needed.
5. AI prompt contracts
Define reusable response-style instructions.
Do not duplicate five different knowledge-level prompts independently across multiple services.
Prefer one centrally maintained policy for explanatory complexity.
The user preference must not affect:

* Actual financial figures.
* Calculations.
* Source reliability.
* Risk caveats.
* Legal disclosures.
* Whether missing data is disclosed.
* Whether advisory safeguards apply.

6. Avoid excessive regeneration
When users change the slider, ensure new AI responses use the updated preference.
For already generated content, implement a clear and efficient regeneration or explanation-level change behavior where supported.
Do not silently change historical conversation records.
Avoid unnecessary API costs.
7. Testing
Test all five levels against the same factual input.
Confirm:

* Different vocabulary.
* Different explanation depth.
* Consistent financial numbers.
* Consistent source attribution.
* Consistent uncertainty.
* No personalized advice.
* Stable preference after refresh.
* Correct behavior across tabs.
* Consistent Milo behavior.
* Correct guest and logged-in behavior.

Completion gate
The slider works.
The preference persists where supported.
Milo and Dossier honor it.
Users can change it easily.
The five levels are meaningfully different.
All underlying factual information stays consistent.
Complete browser and automated tests before reporting PASS.
