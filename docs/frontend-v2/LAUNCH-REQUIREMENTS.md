# Frontend v2: launch requirements that are not resolved

Copying the classic app's notices into v2 (Stage 0, item 4) restores what the
product already said. It does not make the product ready to launch. These are
the requirements that are still open, kept separate so restored text is never
read as proof of readiness. Each needs the owner; none is solved by v2 code.

| # | Requirement | State on 2026-10-18 | Who | Effect in v2 |
|---|---|---|---|---|
| L1 | Published Terms of Service and Privacy Policy, linked from the product | Not written. `TERMS_URL`, `PRIVACY_URL` unset (launch audit B3) | Owner, with legal review | Sign-up has no terms to agree to; brokerage consent says the documents "are not published yet"; the footer links to neither |
| L2 | Email delivery | Production mail backend is `log` (no `SMTP_HOST`) (B1) | Owner | Confirmation, password reset, alert and problem-report emails are never sent. v2 says so on screen, as Classic does |
| L3 | Billing | Off ("Plans are not on sale yet") (B2); live needs Stripe keys and `BILLING_LIVE_APPROVED` | Owner | Upgrade buttons are hidden behind the server's own "not on sale" reason |
| L4 | Legal review of the notices themselves | The text is the classic app's, unchanged; no review is recorded. v2 shows the same footer, full disclaimer, per-page notices and Milo notice | Owner, ideally counsel | Placement differs from Classic in one way: per-page notices sit at the foot of each page rather than inside the first panel |
| L5 | Model spend without a guard on three routes | `/api/earnings/{T}/brief`, `/api/sectors/{S}/read`, `/api/catalyst-mode` (D1) | Owner decision | v2 calls none of them on load (click-only, labelled), but a direct request still spends |
| L6 | "Suitable as a core long-term holding" reads as advice | Classic Investing (D3) | Owner decision | Not shown in v2 (checked: the string does not appear in `static/v2`) |
| L7 | Google and Apple sign-in | Not configured on this deployment | Owner | v2 hides the buttons when the server says a provider is unavailable |
| L8 | Brokerage provider | `BROKERAGE_OWNER_ONLY` on; SnapTrade terms URL, consent and retention statements depend on L1 | Owner | v2 follows the server's gating word for word |
| L9 | Accessibility claims | Automated audit and keyboard paths checked; no VoiceOver, TalkBack or NVDA session yet; no accessibility statement | Owner | Do not claim conformance until a screen-reader pass is done |
| L10 | Cookies and storage | Only first-party session cookies and local storage; no analytics. Not yet described anywhere a reader can read | Owner, with L1 | The Privacy Policy should say what is stored where (Settings, About this build, already lists it) |
| L11 | Classic spends on page load | Paid-call probe, 2026-10-18 (STAGE0-EVIDENCE.md §5): loading Classic's Earnings, Read and Macro pages made one model call each (`earnings/{T}/brief` and the Read and Macro reads), with no cached copy in the probe's data | Owner decision; Classic is live and was not changed | v2 made 0 model calls across 80 page loads (40 views, desktop and phone). Once v2 is the default, only readers who choose Classic trigger these |
