<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 01 — EXHAUSTIVE REPOSITORY DISCOVERY AND BASELINE AUDIT
Read CLAUDE.md and the existing post-demo engineering documentation.
Your assignment is to inspect the ENTIRE Optic repository and produce a verified, actionable inventory of everything that exists.
Do not redesign the interface during this phase.
Do not make unrelated feature changes.
1. Architecture discovery
Identify and document the actual:

* Frontend framework and versions.
* Backend services and API architecture.
* Authentication system.
* Database and persistence layer.
* Brokerage integration architecture.
* Market-data APIs and providers.
* AI models and Milo orchestration.
* Prompt templates and AI tool definitions.
* Streaming architecture.
* Charting framework.
* Caching and state management.
* Navigation and routing.
* Design system and styling tools.
* Animation dependencies.
* Logging and monitoring.
* Testing infrastructure.
* Build and deployment configuration.

Identify unnecessary duplicate systems, abandoned components, and conflicting implementations.
Do not delete them yet.
2. Full route and feature inventory
Discover every actual route, page, and tab.
For every route, enumerate:

* Every visible component.
* Every interactive component.
* Every button and its expected action.
* Every dropdown and option.
* Every input and search field.
* Every chart and time-range selector.
* Every data table.
* Every AI-generated section.
* Every tooltip.
* Every navigation link.
* Every modal.
* Every loading state.
* Every error state.
* Every empty state.
* Every API dependency.
* Every user preference.
* Every feature requiring authentication.

Create a structured FEATURE_REGISTRY.md.
Do not limit discovery to the features named by the user.
3. Functional baseline
Run the application locally with the correct non-production configuration.
Execute the existing:

* Production build.
* Type checker.
* Linter.
* Unit tests.
* Integration tests.
* Browser end-to-end tests, if present.

Record all failures before fixing them.
Inspect browser console errors, failed network requests, hydration errors, and unhandled exceptions.
4. First-pass visual audit
Inspect every accessible route at:

* Desktop 1440 × 900.
* Laptop 1280 × 800.
* Tablet 768 × 1024.
* Mobile 390 × 844.

Capture screenshots where possible.
Identify:

* Inconsistent spacing.
* Excessive information density.
* Broken alignment.
* Overflow.
* Unclear navigation.
* Unresponsive controls.
* Unnecessary complexity.
* Long AI-generated text.
* Confusing labels.
* Poor contrast.
* Unprofessional loading states.

Do not change the UI during this discovery phase.
5. Core workflow mapping
Map the actual user journeys for:

* First-time visit.
* User onboarding.
* Ticker search.
* Research and Dossier.
* Chart exploration.
* Milo conversation.
* Brokerage connection.
* Portfolio research.
* Account settings.

Identify where context should persist between features.
6. Dependency and risk analysis
Determine which components share:

* Ticker state.
* User preferences.
* Authentication.
* Financial data.
* AI prompts.
* Cached responses.
* Conversation state.

Document dependencies so future changes do not create regressions.
7. Security baseline
Identify apparent security weaknesses without conducting destructive or intrusive testing.
Review secret handling, data authorization, browser exposure of credentials, and sensitive logging.
Do not display credentials in reports.
8. Deliverables
Complete:

* FEATURE_REGISTRY.md
* MASTER_PLAN.md
* REQUIREMENTS_MATRIX.md
* BUG_REGISTER.md
* Initial TEST_RESULTS.md
* Initial PROGRESS.md

Rank every issue P0, P1, or P2.
For each serious issue, identify the affected files and a recommended verification method.
Completion gate
Do not report this phase complete unless:

1. Every discovered route has been inventoried.
2. Core feature dependencies have been mapped.
3. Existing build and test results have been recorded.
4. The most important broken workflows have been identified.
5. A safe Git working branch exists.
6. Future phases can refer to the feature registry without rediscovering everything.

Where browser access is unavailable, clearly distinguish source-code inspection from rendered UI verification.
Finish with a concise report and the exact command or instructions needed to continue with Phase 02.
