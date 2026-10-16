# Issue ledger (launch audit 2026-10-16)

Severity: P1 wrong info / privacy / broken core task; P2 cognitive overload / unclear flow; P3 accessibility / missing feedback; P4 responsive / consistency; P5 polish.
Status: OPEN, FIXED <commit> (how verified), HANDED (to whom), OWNER (needs the owner), WONTFIX (why).
Branch `launch-audit`, baseline tag `launch-audit-baseline` = origin/main 2fb664a. Nothing deployed.

## Summary table

| # | Sev | Area | Issue | Status |
|---|-----|------|-------|--------|
| B1 | P1 | Accounts (live) | Production mail backend is `log` (no SMTP_HOST): no confirmation or password-reset email is ever sent | OWNER |
| B2 | P1 | Billing (live) | `/api/billing/status`: "Plans are not on sale yet." No paid plan can be bought | OWNER |
| B3 | P1 | Legal | No Terms of Service or Privacy Policy in the product; brokerage consent says they "are not published yet" | OWNER |
| L1 | P1 | Insiders > Federal contracts | `/api/contracts` 500 on every call, live too, since 2026-10-13 | FIXED 9877833 |
| L2 | P2 | Search | Company name + Enter loads a bogus symbol | FIXED 2c07b00 |
| L3 | P1 | Options | Off-hours (nights, weekends) the chain has no quotes; the opening panel said nothing about options or why | FIXED 2c07b00 |
| L4 | P1 | Read | Index strip printed fund prices under index names ("S&P 500 771.79" vs Home's 7,744) | FIXED 2c07b00 |
| L5 | P1 | Overview | "Long-term conviction: Neutral" beside the Optic Score's "High conviction" | FIXED 2c07b00 |
| L6 | P2 | Retirement | Every section folded, including the one holding the form | FIXED 2c07b00 |
| L7 | P1 | Milo | Offline error says "the question is still in the box"; Send had emptied it | FIXED 2c07b00 |
| L8 | P3 | Milo | Send and Deep research live with the allowance spent; press returned a red 429 | FIXED 2c07b00 |
| L9 | P3 | Milo | Allowance count stale after Deep research | FIXED 2c07b00 |
| L10 | P2 | Palette | "News" row opened the Read; Options/Investing/Earnings not findable | FIXED 2c07b00 |
| L11 | P3 | All pages | Tab title "Optic Terminal" on every page (WCAG 2.4.2) | FIXED 2c07b00 |
| L12 | P3 | Phone bar | More tab's accessible name stayed "Alerts. N unread" after the dot cleared | FIXED 2c07b00 |
| L13 | P4 | Recent | Symbols with digits (7203.T) dropped from Recent | FIXED 2c07b00 |
| L14 | P4 | Settings | "Close settings. Back to Home" when returning to another page | FIXED 2c07b00 |
| L15 | P4 | Source labels | "yfinance" (a Python library) named as the data source | FIXED 2c07b00 |
| L16 | P3 | Home | Footer said "Checking data source..." all visit when the status check failed | FIXED 2c07b00 |
| L17 | P2 | Overview | Each conclusion stated 2 to 4 times; Simple = same 8,000px page | FIXED b04f337 |
| L18 | P4 | Money format | "$-86.45" beside "+$100.00" (shared usd()) | FIXED b04f337 |
| L19 | P4 | Brokerage | Consent note printed "terms-draft-...|shown:none" | FIXED b04f337 |
| L20 | P3 | Auth copy | Readers told the link "went to the server log" | FIXED b04f337 |
| L21 | P1 | Retirement privacy | "posted only to your own local server" (false on the hosted site) | FIXED b04f337 |
| L22 | P4 | Framework | "-50% from the price"; ISO date in the earnings headline | FIXED b04f337 |
| L23 | P2 | Home (desktop) | 14 trend cards above the Desk put its bottom line at y=1699 | FIXED b5ee657 |
| L24 | P3 | Contrast | --pos 4.67, --neg 4.04, --s1 4.31, critical text 3.26 on panels | FIXED b5ee657, 2638fb3 |
| L25 | P3 | Dossier | No h1 on Overview/Earnings/Financials/News/Investing | FIXED b5ee657 |
| L26 | P4 | Watchlist | Signal header right-aligned "What changed" instead (stale nth-child) | FIXED b5ee657 |
| L27 | P1 | Earnings | Implied move silently from last trades overnight | FIXED b5ee657 |
| L28 | P3 | Report a problem | Signed out: focus stayed on the pill, Escape did nothing | FIXED c9d1272 |
| L29 | P3 | Milo toggle | No aria-expanded/aria-controls | FIXED c9d1272 |
| L30 | P4 | Compare | Remove dropped the last box whatever was meant | FIXED c9d1272 |
| L31 | P4 | Overview (index) | ^GSPC "The share price", "the fund's price" | FIXED 94f84e0 |
| L32 | P4 | Digest/research | ISO dates in report lines | FIXED 94f84e0 |
| L33 | P4 | Options | Key Stats above the price card | FIXED 1157d65 |
| L34 | P1 | Macro | Imperative trading directives under a "Not a recommendation" banner | FIXED 8d9e6bc |
| L35 | P3 | Watchlist | Remove had no undo | FIXED 86a3072 |
| L36 | P2 | Retirement | Drift and contribution answers folded after Recalculate | FIXED 5c22047 |
| L37 | P1 | Read | "The next edition is due 8:15 am" when none has ever been published | FIXED 9f9e64c |
| L38 | P3 | Levels | Professional-only panels tagged "Advanced" with the switch on | FIXED adf1609 |
| L39 | P1 | Earnings/Investing | A slow reply drew the previous company's numbers under the new symbol | FIXED 4cee2c5 |
| L40 | P1 | Options research | Old symbol's contracts kept; failed refresh hidden; out-of-order replies | FIXED 4cee2c5 |
| L41 | P1 | Financials | Previous symbol's congressional trades; failure worded as no disclosure | FIXED 4cee2c5 |
| L42 | P2 | Earnings | Pre-earnings brief vanished on any redraw | FIXED 4cee2c5 |
| L43 | P2 | Options/Macro | 20 s refresh wiped typed inputs, open menus, the currency search | FIXED 4cee2c5 |
| L44 | P1 | Explore -> Sector Read | Paid read written into a missing or folded host, often never shown; refusals cached | FIXED 4cee2c5 |
| L45 | P1 | Watchlists (signed in) | Switching lists and back reloaded old symbols over edits | FIXED 4cee2c5 |
| L46 | P1 | Alerts | "Clear all" one-press hard delete for everyone, no catch | FIXED d27ec0e |
| L47 | P1 | Chart Alerts widget | Visitors' Clear opened a prompt asking for OPTIC_WRITE_TOKEN | FIXED d27ec0e |
| L48 | P1 | Delete account | Password typed into window.prompt (clear text); no word on billing/brokerage | FIXED d27ec0e |
| L49 | P2 | Paper Desk | Toggles wiped the ticket; preview only after a refused submit; first keystrokes lost | FIXED 49cafc0 |
| L50 | P3 | Optic Portfolio | Stuck "Scan running..." after leaving and returning | FIXED 0d4ddc7 |
| L51 | P2 | Options (Simple) | Price chart started folded (substring key) | FIXED 0d4ddc7 |
| L52 | P3 | Panels | Explain chart in a heading folded the chart | FIXED 0d4ddc7 |
| L53 | P4 | Financials | "Optic's Read" link had no handler | FIXED 0d4ddc7 |
| L54 | P1 | Instrument | Missing RSI labelled "Oversold territory" | FIXED 0d4ddc7 |
| L55 | P4 | Earnings/Investing/Financials | "—%" for missing figures | FIXED f37ddb1 |
| L56 | P4 | Scan | Ask Milo tooltip said draft-only; it can spend one message to read words | FIXED b72c343 |
| D1 | P1 | AI spend | /api/earnings/{T}/brief, /api/sectors/{S}/read, /api/catalyst-mode have no _spend_guard; any visitor opening Earnings for many tickers pays one write per ticker per 6 h | OWNER decision |
| D2 | P1 | Boot | renderHome runs before a deep link's route, so every deep link fires /api/home (desk-writing path) first | OPEN |
| D3 | P2 | Investing | "The model's rule at this score: Suitable as a core long-term holding" reads as advice; the star rule sentence was removed for the same reason on 2026-10-08 | OWNER decision |
| D4 | P2 | Long-term score | "Resolved catalyst -12" from one headline tag moves a multi-year score 12 points | OWNER/framework |
| D5 | P4 | Milo entry points | Five visual styles (gold button, blue pills, grey Explain chips, gold Explain chart, links) | OWNER decision |
| H4 | P2 | Brokerage "Write it up" | Records the spend before writing; a failed write 502s with the message gone | HANDED source-foundation session |
| H1 | P1 | Brokerage overview | Total value is broker-priced, Today's change is market-priced on $19k more | HANDED source-foundation session |
| H2 | P2 | Brokerage briefing | "Possibly related" headlines unrelated (same SpaceX piece under NVDA and AAPL) | HANDED source-foundation session |
| H3 | P4 | Brokerage status | "not switched on for this deployment" reaches guests | HANDED source-foundation session |

## Details

### B1 Production does not send email
- Evidence: `GET https://theopticterminal.com/api/auth/providers` -> `mail: {available:false, backend:"log", reason:"No SMTP_HOST is set..."}` (2026-10-16 09:36 UTC).
- Impact: a subscriber cannot confirm an address or reset a forgotten password; a locked-out paying customer has no recovery route. Admin status also depends on a verified address.
- Needs: SMTP relay credentials in Railway (SMTP_HOST etc., see DEPLOY.md). Not something code can supply.
- Copy fixed meanwhile (L20).

### B2 Billing is off on production
- Evidence: `GET /api/billing/status` -> `{"available":false,"reason":"Plans are not on sale yet. Every account is on Free."}`.
- Needs: Stripe live keys and `BILLING_LIVE_APPROVED` (app/billing.py), and the owner's decision to sell.

### B3 No published Terms or Privacy Policy
- Evidence: sign-up (static/auth.js body()) asks for no acceptance and links none; brokerage consent prints "(Sandbox: the documents are not published yet.)"; consent version strings are `terms-draft-2026-10-12+privacy-draft-2026-10-12`.
- Needs: legal text approved by the owner. Not written here.

### L1 Federal contracts answer 500 (live since 2026-10-13)
- Root cause: app/main.py imported `app.analytics.contracts` as `contracts_mod`, shadowing the federal awards module.
- Fix: `option_contracts_mod`; route test in tests/test_contracts.py. Verified: test passes; Insiders loads contracts locally after restart.

### L2 Company name + Enter
- Fix: `typedNamePick()` in attachTypeahead. Verified: costco->COST, apple->AAPL, F->F, top bar microsoft->MSFT; an Enter before the list answers still falls back to Not found + Did you mean.

### L3 Options page off-hours
- Repro: 05:15 ET, #/AAPL/options. `gex.error`/`flow.error`: "no quotes and no open interest near the price ... The free feed serves the chain like this outside market hours". First panel said only "Optic's short-term signals: leaning bullish".
- Fix: renderOptionsPlain leads with "There are no options readings right now." and the server's reason; the stance line says options are left out. Verified in headless Chrome.

### L4 Read strip
- Fix: rows labelled "SPY · S&P 500" etc. with a title saying it is the fund's price. Verified.

### L5 Two "conviction" readings disagreeing
- Root cause: two models. longterm.py (trend, five-year record) feeds the Optic Score; app/research's verdict weighs quality against valuation.
- Fix: the research tile says "Quality and price together: Neutral", naming what it combines. The Optic Score's existing note already explains that its high score is not a cheap price.

### L6 Retirement folded
- Fix: `PANELS_OPEN_BY_DEFAULT.roth = ['roth ira model allocation']`; test updated. Verified: form visible with defaults 30 / Balanced / 7000.

### L7-L9 Milo send states
- L7: on failure the question returns to the box and the unanswered turn leaves `chatState.messages`, so a resend is one question.
- L8: `pulseAllowanceSpent()`; Send and Deep research disabled while the note says all messages are used; a timer reloads the allowance at `next_at`.
- L9: runResearch calls loadAllowance in finally.
- Verified: unit-level only (no API key locally; a live Milo exchange was not run, to spend nothing).

### L17 Overview, one set of answers
- Measured (AAPL, 390x844, default level): sections What changed 918, Key takeaways 1,106, Optic Score 963, Four questions 1,167, Bull/bear 743 px; page 8,000px; Simple identical.
- Changes: takeaways' sentences moved into the four question tiles (drawn before the grades arrive); digest headlines folded; "Not checked" moved to the method note; bull/bear folded below Advanced.
- After: page 6,525px (-18%), desktop sections 3,780 -> 3,071px. Valuation stated in one tile (plus the Optic Score's reconciling note), earnings date in one tile plus the What next list.
- Hypothesis, not measured: fewer repeated readings reduce the "which of these do I believe" effort. Needs user testing.
- Before/after: runs/r1-desktop/desktop-AAPL.png, runs/r1-mobile/phone-AAPL.png -> shots/after/.
