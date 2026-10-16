# Launch audit, 2026-10-16

A pass over the whole terminal before subscriptions open: cognitive load first,
then accessibility, function, data integrity, and a regression run. Branch
`launch-audit`, from origin/main 2fb664a (tag `launch-audit-baseline`).
**Nothing here is deployed.** 24 commits, 27 files, +1,107 / -377 lines.

## Release assessment

**Not ready to sell subscriptions yet.** The product itself is close: the
defects that showed wrong data, lost what a reader typed, or broke a core task
are fixed on this branch and covered by tests. Three blockers are outside the
code and need the owner:

1. **Email is not sent in production.** `/api/auth/providers` reports
   `mail.backend = "log"` (no `SMTP_HOST`). No confirmation or password-reset
   email reaches anyone, so a paying customer who forgets a password cannot
   get back in.
2. **Billing is off.** `/api/billing/status`: "Plans are not on sale yet."
   It needs Stripe live keys, `BILLING_LIVE_APPROVED`, and a test purchase.
3. **No Terms of Service or Privacy Policy.** Sign-up asks for no acceptance
   and links neither. Brokerage consent says they "are not published yet".

When those three are resolved and this branch has shipped and been checked
live, the assessment becomes **ready with explicit limitations** (see
"Remaining" below).

## How it was checked

- **Crawl.** `tools/crawl.py` (outside the repo, in the owner's work folder)
  drives headless Chrome over all 23 routes at 1440x900, 768x1024, 390x844 and
  320x640. For each page it records exceptions, console errors, failed
  requests, horizontal overflow, unnamed controls, touch targets, heading
  order, duplicate ids, approximate text contrast, and values that render as
  `undefined`, `NaN`, `null` or `—%`.
- **Journeys.** `tools/drive.py` scripts each journey in a fresh or a returning
  browser profile against a local server: sandbox brokerage, a seeded local
  account, no AI key. Nothing ran against the live site except read-only GETs
  that cannot spend.
- **Code inventory.** Each view's render function, endpoints, controls and
  states, read from source. The defects it turned up are folded into the
  ledger below.
- **Tests.** The full suite passes at 44de21f: 6,166 passed, 1 skipped.

## Coverage matrix

Status: **V** verified with no defect found; **F** fixed and re-verified;
**B** blocked; **N** not tested (the reason is given).

### Routes, at 1440 / 768 / 390 / 320 px

| Route | Load, errors, overflow | Notes |
|---|---|---|
| Home | F | Desk moved above the trend cards on desktop; status footer failure state |
| Dossier Overview | F | One set of answers; h1; index and fund wording |
| Chart | V | Keyboard, studies note fixed |
| Options | F | Off-hours state; Key Stats order; refresh keeps input; research table race |
| Investing | F | Stale-reply race; fair-value retry; `—%` |
| Earnings | F | Stale-reply race; brief survives redraws; implied-move basis; dates |
| Financials | F | Congress race and failure wording; dead link; h1 |
| News | V | |
| Compare | F | Per-box remove |
| Read | F | Fund labels; no phantom Desk edition; schedule copy |
| Macro | F | Directive wording; repaints keep state; Sector Read shows |
| Indices | V | |
| Explore | F | Sector Read from Explore now appears |
| Scan | F | Ask Milo tooltip |
| Insiders | F | Federal contracts 500 (live) |
| Analysts | V | |
| Optic Portfolio | F | Scan state on return; selector and empty state open |
| Paper Desk | F | Ticket keeps input; live preview |
| Retirement | F | Form and answers open; privacy line corrected |
| Watchlist | F | Undo; header alignment; list switching keeps edits |
| Alerts | F | Clear all confirms; widget gated |
| Settings | F | Data source; delete account form |
| Brokerage (6 sections) | F | Money signs; consent note; fees "Not supplied"; backend findings handed to the brokerage session |
| Reports, Usage, Accounts (owner) | N | Not opened as owner on live; local owner views not exercised |

Final regression crawl (44de21f, 23 routes x desktop/390/320 = 69 loads, in
the regular session): 0 exceptions, 0 failed requests, 0 horizontal overflow,
0 broken values. Low-contrast text outside charts went from 29 / 28 / 28 hits
to 2 / 4 / 7 (desktop / 390 / 320); what is left is de-emphasised "no data"
labels, the Read's "·" separators and heat-map tile text.

### States

| State | Status | Where verified |
|---|---|---|
| Loading | V | every route, crawl settle detection |
| Empty | V/F | watchlist, alerts, paper, retirement, tracker "No trades yet" (now open) |
| Error / failed read | F | congress, options research, valuation and five loaders now retry |
| Partial data | F | options chain without quotes (overnight), brokerage partial sync (sandbox scenario not run) |
| Stale / delayed | F | implied move from last trades; source labels; Read schedule |
| Signed out | V | every route as a guest |
| Signed in | V | local seeded account: watchlists, alerts, settings, brokerage |
| Feature off | F | Desk edition absent; brokerage off (copy handed over) |
| Owner-only | N | not exercised as owner |

### Journeys

| # | Journey | Result |
|---|---|---|
| 1 | Beginner researching an unfamiliar company | **F.** Typing "costco" and pressing Enter opened a Not found page. It now opens COST. The Overview states each conclusion once. |
| 2 | Returning user checking what changed | **F.** Desk bottom line moved from y=1699 to y=790, "What changed" from 2778 to 1868 (1440x900). |
| 3 | Swing trader assessing a setup | **F.** Off-hours chain state, the 20 s refresh no longer wipes inputs, research table race. In-session flow verified at 10:15 ET. |
| 4 | Investor on quality and valuation | **F.** Two "conviction" readings reconciled. "-50% from the price" now reads "50% below". Stale race. |
| 5 | Preparing for earnings | **F.** Brief survives redraws, implied move says when it comes from last trades, dates readable. |
| 6 | Connecting a brokerage | **V** (sandbox): consent, connect, authorise, overview, sections. Value basis and headline relevance handed to the brokerage session, now fixed on its branch. |
| 7 | Milo without page context | **N** for answers: no key locally, and the live site was not asked so nothing was spent. UI states fixed: send failure, spent allowance, toggle state. |
| 8 | Retirement planning | **F.** Form visible, answers open after Recalculate, privacy line accurate. |

## Fixed, by user impact

**Wrong or misleading information**
- `/api/contracts` answered 500 on every call, live too, since 2026-10-13. Insiders' federal contracts panel was empty.
- A slow reply showed the previous company's Earnings or Investing numbers under the new symbol, then cached them.
- Options research kept the previous symbol's contracts; a failed refresh was hidden.
- Financials showed the previous symbol's congressional trades. A failed read was worded "an absence of a disclosure".
- The Read's strip labelled fund prices as indices ("S&P 500 771.79" beside Home's 7,744).
- Overnight, the Options page's first panel said nothing about the chain having no quotes.
- The Earnings implied move came from yesterday's last trades overnight, with no label.
- The Overview said "High conviction" and "Long-term conviction: Neutral" one panel apart.
- The Read promised "The next edition is due 8:15 am" when none had ever been published.
- Retirement said holdings were "posted only to your own local server". On the hosted site they go to Optic's server, which keeps no copy.
- Macro gave trading instructions ("Favor puts...", "long XLE / short XLI") under its own "Not a recommendation" banner.
- A missing RSI was labelled "Oversold territory". Missing percentages printed "—%".

**Lost work or broken tasks**
- The Options and Macro 20-second refresh wiped typed inputs and open sections.
- The Paper Desk wiped the ticket on every toggle, and its preview appeared only after a refused submit.
- Signed-in watchlist edits were lost when switching lists and back.
- Watchlist rows could be removed with no undo.
- Alerts "Clear all" deleted every alert for everyone in one press. The chart widget asked visitors for the server's write token.
- Delete account took the password in a clear-text browser prompt.
- A Sector Read opened from Explore was paid for and often never shown.
- The Pre-earnings brief vanished whenever the page redrew.
- Retirement opened with its form folded.
- Optic Portfolio stuck on "Scan running...".
- The command palette's News row opened the Read. Typing a company name and pressing Enter opened Not found.

**Accessibility and feedback**
- Every page now has its own tab title (WCAG 2.4.2), and Dossier pages have an h1.
- Report a problem takes and returns focus, and Escape works when signed out.
- The Milo toggle has `aria-expanded`. The More tab's accessible name resets when the badge clears.
- Red, green, link blue and fear text reach 4.5:1 on panels, and the red stays clear of the study colours.
- Milo's failed send puts the question back in the box. Send is shut while the allowance is spent. Deep research refreshes the count.

## Cognitive load: the largest reductions

| Change | Measured before | After | Basis |
|---|---|---|---|
| Overview: takeaways folded into the four questions; digest headlines and bull/bear folded below Advanced | 8,000 px at 390 px. Valuation stated 4 times, earnings date 4 times. Simple identical to default. | 6,525 px (-18%). Each conclusion stated once in its tile, plus the score's reconciling note. | Measured height. "Less re-reading" is a hypothesis for user testing. |
| Home (desktop): trends after the Desk and "what changed" | Desk at y=1699, what changed at y=2778 | 790 and 1868 | Measured. Matches the phone order the owner already uses. |
| Search by company name | Enter on "costco" opened Not found plus a Did-you-mean chip (2 steps) | Opens COST (1 step) | Verified for costco, apple, microsoft. F stays F. |
| Retirement | Form folded, 7 shut headings | Form and both answers open | Verified |
| Options off-hours | No reason given on the opening panel | Reason first; stance says options were left out | Verified at 05:15 and 10:15 ET |

## Decisions made without asking (all reversible)

- **Overview merge.** Key Takeaways now live inside the Four Questions tiles for companies. Funds keep the takeaways section. One `framed` branch in `renderOverviewView` restores it.
- **Home desktop order.** The trend board moved below the Desk and watchlist, the phone's existing order. One CSS `order`.
- **Macro wording.** Regime stances are descriptions, not instructions. Strings in `app/analytics/macro.py` and `sectors.py`.
- **Desk edition panel hidden** from readers when no edition exists. The owner still sees it.
- **Token colours.** `--pos #11b011`, `--neg #e76f68`, `--s1 #4a93ea` in the dark theme, re-measured on today's panels.
- **"Quality and price together"** replaces "Long-term conviction" in the research tile.

## For the owner to decide

1. **AI spend without a guard.** `/api/earnings/{T}/brief`, `/api/sectors/{S}/read` and `/api/catalyst-mode` call the model with no `_spend_guard`. The earnings brief is cached per ticker for 6 h, but any visitor opening Earnings across many tickers pays one write each. CLAUDE.md requires research endpoints to answer guests as before, so the choice is yours: account-only writes, a daily cap, or leave as is.
2. **"Suitable as a core long-term holding."** The long-term model's rule sentence on Investing reads as advice. The star rule sentence was removed for the same reason on 2026-10-08.
3. **"Resolved catalyst -12."** One headline tag moves a multi-year conviction score by 12 points.
4. **Milo entry points.** They use five visual styles: the gold Ask Milo button, blue pills, grey Explain chips, a gold Explain chart pill, and links.
5. **Brokerage "Write it up"** spends a message before writing. A refund needs an "unrecord" in `app/auth/ratelimit.py`.

## Remaining, untested and limits

- **Milo answers.** Streaming, tools, sources and cancellation were not exercised: no key locally, and live was not asked. The Milo reasoning session owns that work.
- **Real devices and assistive technology.** No iOS Safari or Android device, no VoiceOver or NVDA. Headless Chrome only, with keyboard paths checked by script.
- **Owner views** (Reports, Usage, Accounts) were not exercised.
- **Inventory items not fixed**, by function name:
  - `loadCatalysts`, `loadContracts` and `loadInsidersCongress` have no sequence guard.
  - `STATE.catalystOpen` survives a symbol change.
  - `loadWatchCatalogue` caches a failure.
  - `loadSignals` drops a filter press made during loading.
  - The chart's Manage indicators Length is recorded but not honoured.
  - The chart Watch widget keeps its own list.
  - The Reports CSRF wording, and Accounts showing the raw "Failed to fetch".
  - `/api/watchlist` keeps 40 symbols while an account list holds 200 (from the code read, not reproduced).
  - Company logos are fetched from third parties, and the font CDN is not version-pinned.
  - Home re-polls `/api/home` every 20 s, which can trigger desk rewrites.
- **Performance (live, measured).** `/api/ticker` takes 2.2–2.8 s and returns about 250 KB. `app.js` is 834 KB gzipped. Not changed here.
- **Heuristic checks.** The contrast check ignores gradients and images, and chart axis text reads as 1:1.
