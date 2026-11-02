<!-- Saved verbatim from the owner's chat message of 2026-10-29. Do not edit; record interpretations in ../DECISIONS.md. -->

PHASE 10 — PERFORMANCE, SECURITY, ACCESSIBILITY, VISUAL CONSISTENCY, AND FINAL POLISH
Read all previous phase reports.
Your mission is to eliminate the remaining technical and visual weaknesses that make Optic feel unfinished or inconsistently engineered.
Do not prioritize visual polish over unresolved correctness or security defects.
1. Performance baseline
Measure applicable:

* Initial page load.
* Largest Contentful Paint.
* Interaction to Next Paint.
* Cumulative Layout Shift.
* Route navigation.
* Chart rendering.
* Search latency.
* Dossier loading time.
* Milo time to first visible response.
* AI response rendering overhead.
* JavaScript bundle sizes.
* API request counts.
* Main-thread blocking.

Collect real measurements under documented conditions.
Compare before and after where a valid baseline exists.
2. Optimize root causes
Investigate:

* Duplicate API requests.
* Excessive polling.
* Unnecessary React re-renders.
* Expensive component calculations.
* Large unused dependencies.
* Oversized JavaScript bundles.
* Poor code splitting.
* Repeated AI calls.
* Inefficient Markdown rendering.
* Uncontrolled animation loops.
* Layout thrashing.
* Slow chart redraws.
* Memory leaks.
* Missing request cancellation.

Prefer targeted fixes with measured results.
3. API cost and scalability audit
Identify actual providers and current usage patterns.
Estimate cost under explicit assumptions for:

* 100 active users.
* 1,000 active users.
* 10,000 active users.

Include relevant:

* AI input and output token usage.
* Financial-data requests.
* Caching.
* Database operations.
* Infrastructure.
* Monitoring.
* Brokerage-provider charges.
* Any provider-specific rate limits.

Do not fabricate current provider pricing.
If pricing cannot be verified, mark those estimates as provisional.
Identify redundant calls and opportunities for safe caching.
Do not introduce new paid infrastructure without authorization.
4. Visual consistency audit
Inspect every route for:

* Inconsistent padding.
* Uneven margins.
* Incorrect alignment.
* Conflicting border radii.
* Inconsistent text sizes.
* Inconsistent button heights.
* Different hover behaviors.
* Misaligned icons.
* Overlapping dropdowns.
* Broken responsive layouts.
* Truncated text.
* Excessive visual density.
* Conflicting color treatments.
* Unnecessary decorative elements.
* Inconsistent chart presentation.

Use the existing design system where possible.
5. Animation improvements
Refine:

* Page transitions.
* Tab changes.
* Button hover states.
* Modal opening and closing.
* Dropdown behavior.
* Chart loading.
* Dossier mode switching.
* Milo processing states.
* Skeleton loading.
* Content appearance.
* Error and success feedback.

Animations must be subtle, responsive, and purposeful.
Avoid artificial waiting.
Avoid excessive animation libraries.
Respect prefers-reduced-motion.
Do not use motion that causes layout shifts or delays access to information.
6. Accessibility
Review applicable WCAG 2.2 AA requirements.
Test:

* Keyboard navigation.
* Visible focus.
* Semantic HTML.
* Input labels.
* Color contrast.
* Dialog focus management.
* Screen-reader announcements.
* Slider accessibility.
* Chart alternatives where appropriate.
* Form validation.
* Reduced motion.
* Mobile touch targets.
* Zoom and responsive text.

Correct critical barriers.
Document any requirements not fully verified.
7. Security
Perform a non-destructive review of:

* Authentication.
* Authorization.
* User-specific API access.
* Brokerage credential handling.
* Secret exposure.
* Cross-site scripting.
* Cross-site request forgery where applicable.
* Input validation.
* API rate limiting.
* Prompt injection.
* Sensitive-data logging.
* Database access controls.
* Dependency vulnerabilities.
* Session handling.
* Error-message information exposure.

Never print secrets.
Never perform intrusive penetration testing against production or third-party services without authorization.
8. Failure resilience
Test:

* No internet connection.
* Slow network.
* Failed market-data provider.
* Failed AI provider.
* Expired authentication.
* Expired brokerage connection.
* API rate limit.
* Invalid provider response.
* Empty data.
* Request timeout.
* Rapid repeated interactions.
* Browser refresh during loading.

Every critical workflow needs a clear recovery path.
Avoid indefinite spinners.
9. User analytics review
Inspect whether the terminal can measure privacy-conscious events such as:

* Onboarding completion.
* Search success and failure.
* Dossier usage.
* Milo submission success and failure.
* Brokerage connection failures.
* Abandoned flows.
* Feature engagement.

Do not introduce intrusive tracking.
Do not capture financial account details or sensitive conversation text unnecessarily.
Document analytics recommendations separately if implementation requires new services or consent changes.
Completion gate
Critical performance regressions are resolved.
No known critical security vulnerabilities remain unaddressed without explicit escalation.
Major accessibility barriers are fixed.
Visual inconsistencies are corrected.
Loading and error states are professional and consistent.
Real measurements, screenshots, and test outcomes are documented.
Do not deploy.
