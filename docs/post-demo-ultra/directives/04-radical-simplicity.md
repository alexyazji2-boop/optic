<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 04 — RADICAL SIMPLICITY AND FIRST-TIME USER EXPERIENCE OVERHAUL
Read all previous phase reports.
THIS IS THE MOST IMPORTANT PRODUCT DESIGN PHASE.
The investor feedback was that Optic has valuable capabilities but is overwhelming to look at and requires too much reading.
Your mission is to dramatically simplify the entire terminal WITHOUT removing valuable analytical functionality.
Do not merely adjust spacing, colors, or fonts.
Reconsider the information architecture, default content density, navigation clarity, and language throughout the entire product.
1. First-time user audit
Evaluate every major screen from the perspective of someone who has never used a financial terminal.
Ask:

* What is this page for?
* What should the user look at first?
* What does the main number represent?
* Why does the displayed information matter?
* What can the user do next?
* Which labels require financial knowledge?
* How much unnecessary reading is required?
* How many simultaneous actions compete for attention?
* Is the main benefit apparent within approximately 30 seconds?

These are usability heuristics, not proof of actual user comprehension. Do not claim validated user outcomes without real user tests.
2. Visual density audit
Inspect every route, not just the homepage.
Review:

* Number of visible cards.
* Competing headings.
* Excessive statistics.
* Long descriptions.
* Dense tables.
* Technical jargon.
* Duplicate information.
* Repeated buttons.
* Excessive icons.
* Unnecessary borders.
* Nested cards.
* Large empty gaps.
* Inconsistent spacing.
* Unclear hierarchy.
* Sidebar complexity.
* Modal complexity.
* Chart controls.
* AI response layouts.

Reduce unnecessary cognitive load.
3. Simple-first architecture
Every primary screen should present three layers:
LAYER 1 — Essential information.
Visible immediately, understandable to beginners.
LAYER 2 — Supporting information.
Available through contextual expansion or secondary sections.
LAYER 3 — Advanced research.
Accessible for experienced users without cluttering the initial experience.
Preserve advanced capability.
Do not simply hide everything or make the user click through multiple menus to find essential information.
4. Homepage simplification
Review the homepage as a landing point for returning and first-time users.
Determine whether it clearly communicates:

* What Optic does.
* How users can start.
* What market context is currently displayed.
* How to search.
* Where to access Milo.
* Where to access deeper research.

Avoid excessive dashboards, paragraphs, overlapping promotional sections, and redundant controls.
Do not remove essential existing features without checking their use cases.
5. Navigation simplification
Review whether feature names are clear.
Identify confusing or redundant navigation items.
Optimize the hierarchy of primary versus secondary destinations.
Users should not need to memorize where important functionality lives.
Preserve existing deep links and route compatibility where feasible.
6. Global language simplification
Review every user-facing label, description, tooltip, placeholder, and AI-generated explanation.
Create consistent writing guidelines:

* Explain before using jargon.
* Use shorter sentences.
* Put the main insight first.
* Avoid unnecessary introductory filler.
* Avoid repeating the same metric in multiple places.
* Explain technical terms only when needed.
* Keep numerical and source detail accessible.
* Prefer direct language over promotional language.

Do not simplify until information becomes misleading.
7. Unified Simple and Advanced presentation model
Evaluate a global Simple View and Advanced View approach.
Simple View should prioritize:

* Essential information.
* Plain-English interpretation.
* Minimal controls.
* Clear next actions.

Advanced View should expose:

* Deeper metrics.
* More technical information.
* Additional chart indicators.
* Expanded research controls.

The knowledge-level slider introduced in Phase 05 should control language complexity independently from visual information density.
Do not create conflicting mode systems.
If a global presentation mode would materially complicate existing architecture, document the tradeoffs and implement consistent per-feature progressive disclosure instead.
8. Component-by-component review
For every component, determine:
KEEP — Valuable and already clear.
SIMPLIFY — Useful but unnecessarily complicated.
COLLAPSE — Useful secondary detail.
RELOCATE — Valuable but in the wrong part of the interface.
MERGE — Duplicates another component.
REMOVE — No longer serves a distinct purpose and is safe to remove.
Document every removal.
Do not delete functionality simply because it is visually complex.
9. Design system consistency
Audit:

* Button styling.
* Typography.
* Spacing.
* Card layout.
* Form fields.
* Tabs.
* Dropdowns.
* Tooltips.
* Icons.
* Charts.
* Loading states.
* Error messages.
* Empty states.
* Navigation.
* Modals.

Reuse shared components and design tokens.
Eliminate obvious generic AI-generated dashboard patterns.
Create a coherent visual language inspired by the restraint and interaction quality of established financial and productivity applications, without copying their assets or proprietary designs.
10. Responsive simplicity
Verify that the interface remains understandable at desktop, laptop, tablet, and mobile sizes.
No overlapping labels.
No inaccessible controls.
No hidden essential content.
No horizontal overflow unless explicitly appropriate for data tables or charts.
11. Visual regression checks
Capture before-and-after screenshots for materially modified routes.
Inspect differences manually or with available visual testing tools.
Verify that simplification did not introduce layout regressions.
Deliverables
Produce SIMPLICITY_AUDIT.md.
For every route record:

* Original cognitive load.
* Original visual problems.
* Changes made.
* Content relocated.
* Content removed.
* Features preserved.
* Before/after evidence.
* Unresolved limitations.

Completion gate
Every discovered primary route has been reviewed.
Critical usability problems have been addressed.
The default experience has a clear hierarchy.
Beginners are not forced to read advanced analysis.
Advanced functionality remains accessible.
No major visual regressions remain.
Do not declare success based solely on aesthetic improvements. Verify real navigation and interaction behavior.
