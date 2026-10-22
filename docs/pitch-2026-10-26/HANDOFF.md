# Pitch-readiness corrections: handoff

Written 2026-10-22, against the audit in `~/Optic/work/pitch-audit-2026-10-22/AUDIT.md`.

- **Branch** `pitch-fixes` in `~/Optic/wt-pitch`, from origin/main `fc027f1` (the audited `a0a5fe5` plus the Home released-results work another session shipped today).
- **Release candidate** tag `pitch-rc-2026-10-22` (the commit is in the closing message and in `pytest-rc-final.txt`). **Not pushed, not deployed.**
- **Preview** (local only): `optic-pitch-milo` at http://localhost:8112 (Milo answered by a local stand-in model, no key, no spend); `optic-pitch` at http://localhost:8111 (no model). Both serve v2 as production does (`OPTIC_DEFAULT_UI=v2`, `OPTIC_V2_ACCESS=all`).
- **Evidence folder** `~/Optic/work/pitch-audit-2026-10-22/`: `pytest-*.txt`, `rc-shots/`, `milo-standin-log/`.
- Regression tests for every item below: `tests/test_pitch_audit_2026_10_22.py`.

## Evidence types

- **Behavioural test**: a function run on fixtures (Python, or JavaScriptCore for front-end modules).
- **Browser, viewport**: the built-in browser pane at 1024 (desktop), 390 and 360 wide, emulated. Not a physical device.
- **Source inspection**: read, not run.
- **Live**: theopticterminal.com, read-only GETs. Nothing was clicked or written there.

## Items

| # | Item | Status | Cause found | Change | Verified by |
|---|---|---|---|---|---|
| 1 | Valuation answer means the opposite | Fixed | Answers written for "is it cheap?" under "Is the share price expensive?" | Question "How is it priced against its own history?"; five descriptive star states, a too-wide range, no range, a failed source; quality answers describe the grade; 4 stars no longer "below the range"; fund drawers keep fund questions | Tests (all states); browser: AAPL at 347 against 244 to 307 reads "Above its usual valuation range." |
| 2 | Earnings both ahead and resolved | Fixed | Any recent headline tagged "earnings" counted as a resolved report; no date check | Earnings is resolved only when the calendar has a report in the window and the headline follows it; previews are pending with the calendar's date, or set aside as ambiguous; every warning names its event, date basis, headline and publisher; "rich after the event" only after a dated report | Tests: future, completed, calendar-just-passed, ambiguous, two catalysts, entry plan both ways |
| 3 | Expected move hides a conversion | Fixed | Ratio used ATR / 1.6, page showed raw ATR | Every surface shows ATR / 1.6 beside the ratio; ratio computed from the displayed figures; VIX / 16 labelled a daily equivalent of 30-day implied volatility; Classic's "implied volatility for a year" corrected | Tests; browser: ±1.19 ÷ ±0.60 = 1.98× on Home |
| 4 | Flow labels claim buyers and openings | Fixed | Labels outran the method note | "Call share of traded time value", "volume above prior open interest", no "new" badge, no speculation/protection/fear/chase words; Classic, options brief and Milo's tool text and payload caveat too | Test over the flow output and panels |
| 5 | Retirement split disagrees with table | Fixed | Summary taken before REIT/gold came out of bonds | Split read off final weights after every sleeve; gold and REITs shown | Tests: 3 risks x 5 horizons, with and without a stock sleeve; 30y balanced now 94/6.5 |
| 6 | Retirement uses price returns | Fixed | Unadjusted Close; full-history CAGRs of different lengths blended | Adjusted close (distributions reinvested), basis per fund; the model's own hypothetical record over the shared window, rebalanced each January; projection names rate basis, contribution timing, nominal dollars, and calls the band a sensitivity scenario; Roth notes give qualified-withdrawal conditions | Live data check: BND -1.58% price vs 1.44% total a year over 10 years; tests incl. a dividend fixture and a mixed-basis case |
| 7 | Option counted as one share | Fixed | Value = price x contracts | Premium at risk, notional and delta exposure apart; multiplier and delta from the position if given, else standard 100 and Black-Scholes at the mark's IV, said; unsolvable delta listed as not covered | Tests: ATM call, put, short, adjusted contract, expired, mixed book |
| 7b | Brokerage risk engine | Reviewed, no change | `options_risk.py` already uses provider multipliers and delta share-equivalents; `exposure.py` shows options as one market-value line and says so | None | Source inspection |
| 8 | Entry rules vs the ledger | Fixed (disclosure) | Ledger opens on the composite bar at the scan price; never checks triggers | Each setup armed / triggered / invalidated at the last close; plan and Portfolio page say the books do not wait for triggers; gamma and flow named as one source; no book rule changed | Tests |
| 9 | Honest validation | Preserved | n/a | No new strategy search or backtest run; losses untouched; fill model stated beside the record; composite "not a probability" | Tests on same-bar stop-first and gap fill |
| 10 | Past vs upcoming earnings | Fixed | Home: shipped by the other session (`fc027f1`). Read: every report "reports" | Read: "reported" by the ET day, today's "reports today" | Test incl. 11:30 PM ET |
| 11 | Chart vs one-year answer | Fixed | Chart started one session later | Chart window is the answer's window, both dates shown | Test |
| 12 | Investing scope | Fixed | Static "does not measure valuation" | Scope read off its factor rows; raw points vs mapped score; "on the trend model" | Source + tests |
| 13 | Unjustified certainty | Fixed | Seven phrasings | Gamma conclusions carry the assumption; pair text names residual beta, decay, correlation; regime texts (server and Home) state inputs only; "premium typically builds"; days to cover as a crowding measure; no suitability or accumulation claims | Tests; browser |
| 14 | News tone and times | Fixed | Substring matching, no negation, no tense, landing pages kept | Whole words with inflections, negation, future half-weight, margin-pressure terms, landing pages dropped and counted, publication time and fetch time named | Tests. The feed gives one time per story, so "updated" time is not available |
| 15 | Escaped link; alert identity | Fixed | String interpolated into the template; close alerts named only ticker and reason | `html` template; alerts carry instrument, book, trade id, entry price; kept apart by id | Tests |
| 16 | Formatting | Partly fixed | | `plural()` on day counts; one-line disagreements | Tests. **Outstanding:** a full sweep of mixed price precision and repeated introductions/disclosures |
| 17 | Milo provenance | Fixed | Header came from the page | "About NVDA; AAPL ... attached as context"; symbols named but not loaded say "no NVDA data came back"; each source has instrument, data type, observed and retrieved times | Tests; browser with the stand-in, during real Yahoo 401s |
| 18 | Milo evaluation | Partly done | | Stand-in round trip verified: route, allowance, tool call, stream, sources, about line, cross-company, slow data | **Blocked:** answer quality needs a real-model allowance; stop, retry and history restore not exercised this session |
| 19 | Phone hierarchy | Partly fixed | | Scan examples fold (scanners 830 to 552 px at 360); Home first-visit card 533 to 353 px; Financials prose folds (period control 1251 to 925 px). Earnings already leads correctly | **Outstanding:** Options, Compare, Watchlist/Alerts, Chart overlays |
| 20 | Health hint | Fixed | Hint not conditional | Hint only when off | Test; running server says "configured" |
| 21 | Deterministic tests | Fixed | Milo tests read the live NASDAQ directory | Fixed directory fixture | Reproduced the 3 failures with sockets off and empty data dir; full suite offline: 6,692 passed, 0 failed |
| 22 | Headers | Fixed (pending deploy) | None set by app or proxy | Enforced: nosniff, no framing, object-src none, base-uri self, referrer; HSTS over HTTPS only; full CSP report-only | Tests; browser: no violations from Optic's own pages on Dossier and Chart |
| 23 | Commercial dependencies | Documented | | `COMMERCIAL-DEPENDENCIES.md` | n/a |
| 25 | Congress repeated rows | Outstanding | Not investigated | | |

## Disputed or refined findings

- **Item 2's scope.** The audit allowed that separate pending and resolved events can coexist. The fix keeps that: two different catalysts stay two events. The defect was narrower: an earnings headline with no date check.
- **Item 3.** The arithmetic was right; the denominator was hidden. Fixed as a display problem, with the ratio now computed from the rounded figures shown.
- **Item 7b.** The brokerage engine does not share the paper-book defect.
- **Milo's two P/E comparisons** (audit note): different bases, not an error. Unchanged.

## Remaining before Monday

1. **Deploy**: nothing is pushed. Pushing `pitch-fixes` to main deploys it; that needs your word. It fast-forwards from origin/main `fc027f1`.
2. **Cold first loads**: on a fresh server the framework read took about 31 s and fair value can pass the page's 30 s limit while Yahoo is refusing requests (seen today). Open the demo tickers on the live site a few minutes before presenting.
3. **Yahoo refusals** (401s) were intermittent today; panels fail honestly with Try again.
4. **Data rights**: see `COMMERCIAL-DEPENDENCIES.md`.
5. **Not verified**: physical iPhone Safari and Android Chrome; real Milo answer quality; production behaviour of the new headers behind Cloudflare; Classic-only copy beyond the shared server strings.
6. **Other unpushed work** waiting on you: `portfolio-triggers` (book rules) and `input-defects`. Not merged here.

## Demonstration route

Home (Market Overview: Markets at a glance, Market conditions, Expected move) → search AAPL → Overview (the four answers; open "Evidence and method" on the valuation answer) → Financials (summary figures, Fiscal years / Quarters) → Earnings (the next report, beat-but-fell) → Chart (one range change, Explain) → Ask about AAPL with one short question.

Avoid presenting: options flow as who is buying, Retirement as a forecast, Optic Portfolio results as proof of an edge, "real time".
