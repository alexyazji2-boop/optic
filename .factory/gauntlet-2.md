## Gauntlet record, machine half: Optic, CON-54, Pass 2 (card D-48-7)

**Kind of run: real browser from outside, through the gate, real passwords** (Playwright Chromium, headless, driven from the ops Mac against https://edge-optic-production.up.railway.app with the real gate password, signing in on the product's own form by typing the evaluator's and the owner's real passwords read from `~/.conjure/optic-eval.key` into process memory). The suite ran from a fresh clone on the ops Mac. The human half and the verdict are the operator's; no label was applied and the issue was not moved by this record.

Product: Optic (inherited repository, NEW BUILD lane, no Legacy label). Issue CON-54 "Pass 2: Optic", state Building, labels Free and Refine; order 69988272-31ff-416d-9687-f21e101ab3fa. Environment: Railway project `conjure-optic-eval`, environment `production`, service `optic` behind `edge-optic`. Commit tested: **620c6d490d2b091bf326b82325bc730444efd23e** (fork sidprobstein/optic, branch `factory/pass-2-works-data-workspace`; code identical to b9c005b, the build's last count, 620c6d4 adds only the plan's status). Run 2026-11-17, 22:05 to 23:00 UTC, after the market's close.

### Could not be reached (failures of the test, not passes)

1. **Intraday lines in session, the live dot, and 1D drawing today's line.** The run fell after the close (22:14 to 22:55 UTC), so `/api/sparklines` answered `status: closed` ("Market closed: After hours") and every row took its 30-session fallback. The closed half was reached and passes (items 5a to 5c); the in-session half is NOT RUN and is ask 14 of the human script, to be walked between 14:30 and 21:00 UTC.
2. **The reset link followed.** The reset email reached the sink; its link was left unused on purpose so the evaluator's password stays the one the key file holds (deploy record, item 11).
3. **Suite from clean: not green.** 9,162 passed, **3 failed**, 1 skipped (DEFECT D2 below).

NOT APPLICABLE, stated, not passed: Stripe Checkout, the portal plan change and BILLING TRUTH beyond the off state (billing is off by design this pass: no STRIPE_* variable; the off state is item 11); the comped paid tier (the evaluator account reads plan "Enterprise" on this copy, so the paid half of Milo ran on it; no plan ladder is on sale); OUTCOME INSTRUMENTED (no `## Outcome` block names an outcome for this pass; none invented); one live connection per integration: his market feeds and SEC EDGAR were live on the copy and every figure came through them; SnapTrade is LIMIT L1.

### Documents read, with their stamps

- `product/linear-docs/gauntlet-instructions.md`: `updated: 2026-10-13T19:20:21.805Z`. `product/linear-docs/build-instructions.md`, THE HTTP SOAK and BILLING TRUTH: `updated: 2026-10-13T19:20:21.113Z`. `product/llm-pattern.md`: no stamp in the file ("Standard of record, written 2026-09-29"), rule 10 used below.
- Scope: `customers/optic/pass-summary-2026-11-17.md` (Round 2) and the per-item plan `.factory/pass-2-plan.md` at 620c6d4, with `.factory/pass-2-six-features-record.md` and `.factory/pass-2-workflow-record.md`.
- House shape: `handoffs/optic-pass-1/` (deploy-verify rounds 2 and 6, gauntlet rounds 1 and 6, `hosting/README.md`, the Pass 1 human script for the account addresses).
- Seeds: the repository has no seed scripts; the records below were read off the deployment.
- Baseline: the build's count at b9c005b, 9,165 passed, 1 skipped (plan, "Status"); Pass 1 round six, 9,102 passed, 1 skipped.

### Deploy verification, quoted

From `handoffs/optic-pass-2/deploy-verify-CON-54.md`: "DEPLOY VERIFIED at 620c6d490d2b091bf326b82325bc730444efd23e on b8ff68cc-2ed2-4297-a1b8-9bd47307f060, identified by tree checksum 08db9da6... and build id 2c20c6cd6149". Migration 22 (`workspace_layouts`) applied: `python -m app.db status` applied [1..22] = known [1..22]. Customer data counts identical apart from the new migration.

### Counts block

| Item | Result |
| --- | --- |
| Commit tested | 620c6d4, fresh clone of the fork branch in a new empty directory, HEAD verified equal, push address DISABLED |
| Suite from clean | **9,162 passed, 3 failed, 1 skipped of 9,166**, 2,011 s (22:14:56 to 22:48:33 UTC), outbound HTTP pinned to 127.0.0.1:9, no ANTHROPIC_API_KEY in the shell |
| The three failures | `tests/e2e/test_pass2_six_features.py::test_the_research_sheet_exports_as_a_pdf_with_the_company_and_its_tags` (line 93, `'AAPL' in ''` after print), `::test_a_passkey_is_added_in_settings_and_signs_in_on_its_own[server0]` (line 178, `[data-v2-pk-signin]` never appeared after sign-out), `tests/e2e/test_pass2_workspace.py::test_a_named_layout_saved_in_one_browser_opens_in_another` (line 46, the "is saved on your account" toast never appeared). Re-run alone three times: 1 of 3 passed, then 0 of 3, then 0 of 3. DEFECT D2 |
| The one skip | `tests/test_brokerage_exposure.py::test_live_qqq` (his live EDGAR test, `OPTIC_LIVE_EDGAR=1` to run), the same one skip as every earlier run |
| Against the baseline | build at b9c005b: 9,165 passed, 1 skipped; this run: 9,162 passed, 3 failed, 1 skipped; same total |
| Browser journeys in the suite | 127 of 130 passed (the three above) |
| Pass 2 tests | 63 collected under test_pass2_*: 60 passed, the same 3 failed |
| Eval, quality set | `tests/test_milo_eval.py`: 221 tests in the file, all passed (181 cases, each its own test, plus coverage checks) |
| Eval, injection set | INJ-01 to INJ-14, **14 of 14**; red team `tests/test_milo_redteam.py` **38 of 38** |
| Eval, live smoke | Excluded for want of a key in the suite's shell (his `tests/milo_eval/run_model.py` is not collected by pytest); not a skip. Milo itself answered live on the copy (items 3, 4, 14) |
| Suite needs no API key | yes |
| HTTP soak | 30 page loads, 8,640 requests, 0 failures, signed in as the evaluator through the gate (session's own runner); in-container reading 418, 422, then 440 fds and 2.07 to 2.20 GB RSS (observation O1) |
| OUTCOME INSTRUMENTED | NOT APPLICABLE: no outcome named |
| Stack torn down | No stack was brought up (the journeys start their own servers on free ports); the clones, the virtual environment, the runners and their output stay in the session scratchpad |

The model call changed this pass only in what the page sends (`in_view` on Financials, checked and capped on the server in `app/ai.py`); no eval case was added for it, so rule 10 is met by the existing sets, which ran.

### The browser run, item by item (through the gate, real passwords)

Accounts: the evaluator account (the second Pass 1 test account, address starting con51-r2-f26b93) for every signed-in item, the owner account for item 18. Desktop 1440 by 900 unless a row says phone (390 by 844).

| # | Round 2 item | Asked | What the copy did | Pass |
| --- | --- | --- | --- | --- |
| 1 | (gate) | the gate in a real browser | none 401, wrong password 401, product not shown either time; right 200, build id 2c20c6cd6149 | yes |
| 2 | (account) | sign in, wrong password first | 401 and "Email or password is incorrect."; the real password typed: 200, avatar shown; `/api/ai-allowance` plan Enterprise, 4,000 a day | yes |
| 3 | 3. Milo given the view | Financials (AAPL, quarters), Ask Milo opened first, Cash flow by quarter scrolled to and pressed, "Explain this chart" | request `context.focus.in_view` = {metric "Cash flow by quarter", period "quarters"}; Milo answered about cash generation by quarter ("Free cash flow ... ran $25.9B in the latest quarter") | yes |
| 3b | 3. Milo given the view | the same chart pressed FIRST, then Ask Milo in the top bar, then the question (twice) | Opening the Milo panel narrows the page and moves the chart (top 291 px to 812 px); the request said in view = "Revenue and profit", and Milo explained revenue and net income by quarter, not the chart pressed | **no, DEFECT D1** |
| 3c | 3. Place kept across tabs | Financials scrolled to the insider and ownership sections, Overview by its tab, back to Financials by its tab | first heading in view "Operating income, by business segment" before and after, scroll 4,579 px both times, address #/AAPL/financials | yes |
| 4 | 4. Reported facts apart | the answers above | figures underlined with their source ("$30.7B", Reported: Company; "27.6%", Reported: Sources Milo read) and the line "Underlined figures are reported, from the source beside them; the rest is Milo's reading of them." | yes |
| 5 | 4. Full SEC insider history | Financials, Insider trades, full history; 2, 5 and 10 years | the section with its year switch (5 pressed); "0 open-market purchases and 80 sales since Nov 18, 2021"; the note "Yahoo Finance lists the latest 87 rows, back to Nov 18, 2024; before that, 40 trades come from Form 4 filings read from SEC EDGAR. 38 filings are still being read; this table fills in as they are." At 10 years the page's own request: 91 rows, 40 Yahoo and 51 SEC, each SEC row with its accession (linked to EDGAR), oldest 2022-02-01, 280 of 409 filings still unread at that moment. The table shows the latest 25, all Yahoo rows here | yes |
| 6 | 4. Source and time per figure | Financials and Home | sources named on every chart legend and panel ("Yahoo Finance, delayed up to 20 minutes", SEC filings on the statements) | yes |
| 7a | 5. Intraday ticker rows | Home at Advanced, the watchlist panel | after the close: header "30 sessions", AAPL's line "AAPL, past 30 sessions, up +4.5%", no status line (drawn only in session) | yes, closed half; session half NOT RUN |
| 7b | 5. 1D on the headline chart | press 1D | 1D pressed; "No line for today: the last 30 daily closes: the market is closed. 3M, 6M and 1Y draw the daily closes."; no live dot (drawn only with an intraday line) | yes, closed half; session half NOT RUN |
| 7c | 5. | then 1Y | "Daily closes, past year. Green: ends above its start (dashed)." with "Yahoo Finance, delayed up to 20 minutes" | yes |
| 8 | 6. Financials as charts | Financials, AAPL, Fiscal years then Quarters | years: 10 charts (Revenue and profit, Margins, Cash flow, Cash and debt, Balance sheet, Per share, two segment and two revenue mixes); quarters: 12, adding Cash flow by quarter and Cash and debt by quarter; the Balance sheet shape drawn | yes |
| 8b | 6. Analyst targets drawn | AAPL Earnings | "Analysts' price targets from 250.00 to 425.00, averaging 345.63; the price now is 351.91", drawn as the range with the dot | yes |
| 9 | 7. The Desk's right side | Home, the Optic Desk panel | a right column (200 px beside a 288 px edition) headed Built from (the feeds named, the stories linked with their publishers), Your saved research ("Nothing saved yet."), Ask Milo (questions); Home at Advanced is 3,823 px tall at 1440 by 900 | yes |
| 10 | 8. Link groups | Options layout at Advanced; press the Company news panel's group three times; change the Blue ticker | Blue, Gold, Teal, Blue; aria "Company news is in the Gold link group. Press to move it to the next group"; with Company news in Gold, Blue went SPY to MSFT and Company news stayed on SPY; Gold kept after a reload. Restored to Blue and SPY after | yes |
| 11 | 9. Upgrade with billing off | Settings and Brokerage as the evaluator; Settings as the owner | no Upgrade button and no price anywhere; Brokerage says "Brokerage linking is not switched on for this deployment."; the owner's Settings reads "Plans are not on sale yet. Every account is on Free." and no button | yes |
| 12 | 8. Named layouts across two browsers | Customize, "Save this layout as" a name, Save to my account; a second browser signed in through the form, Saved layouts, Open; reset; delete | PUT 200, "Gauntlet two 1726 is saved on your account. Open it from any browser."; the second browser listed "Saved layouts (1)" and opened it: "Gauntlet two 1726 is open as My Desk."; "Reset Market Overview to its standard panels" worked; Delete 200, 0 layouts left | yes (see D2 for the first-half-second race) |
| 13 | 8. The company grid | `#/AAPL/workspace` at Advanced | heading "AAPL panels", "Every panel follows AAPL unless you move it to another link group."; panels quote, tearn, value, fin, cnews, own, vol, gex, biz, all on AAPL, no market panels; reached from the stock page by "Open as panels"; Home's own linked ticker unchanged (SPY) | yes |
| 14 | 2. Deep Research, our own question | AAPL, Milo, "How exposed is Apple to a slowdown in China this year?", Deep research | `/api/research` 200 after 92 s; the question verbatim in the request; labelled "Deep research: read from live web sources."; 5,386 characters about China with sources | yes |
| 15 | 2. Passkeys | Settings, Add a passkey (Chromium's virtual authenticator); sign out on this device; Sign in with a passkey | register verify 200; sign-out 200 and `/api/auth/me` signed out; login verify 200, signed in as the evaluator; both passkeys made by the run removed after (DELETE 200, 200; 0 left) | yes |
| 16 | 2. Index Read | Indices, the SPY read | `/api/sectors/SPY/read` 200; "SPY, Cautious. The downtrend label lapses, but the index is sitting right on its 200-day..." | yes |
| 17 | 2. Exports | `#/AAPL/sheet` printed by Chromium | a 210,251-byte PDF with the company on it | yes |
| 17b | 2. Alert delivery | `#/alerts?symbol=AAPL` | the form opens for AAPL; `/api/alerts` delivery `enabled: false`, "These alerts are shown in Optic; email delivery is not set up for readers." (LIMIT L2) | yes, off state |
| 17c | 2. Brokerage link | Brokerage | the off state, with the watchlist and the Paper Desk offered; the link itself LIMIT L1 | off state yes |
| 18 | (owner) | Metrics as the owner | the page draws: front end v2, "2 accounts: 2 used Optic in the last 7 days...", the signal counts | yes |
| 19 | 1. The eight workflows | every screen of the eight (research a company 8, what moved today 6, watch names 2, screen 4, practise or model 4, brokerage 1, account 2), signed in, live feeds, 60 s to settle; Ask Milo pressed on each | no page error, no raw text, no block left loading, no error outside the shared states, the rail and a way forward on every screen; Milo opened on every screen (the sheet excepted by design) | yes |
| 20 | (account) | forgot password for the evaluator and an unknown address | the same sentence "If an account uses that address, a reset link is on its way."; Mailpit: "Reset your Optic Terminal password" to the evaluator, nothing to the unknown address; link not used | yes, arrival |

### Accessibility (axe, WCAG 2.1 A and AA, on the live copy, signed in)

16 scans, desktop 1440 and phone 390. No sideways scroll on any. No page errors.

- Clean (0 violations) at both widths: Home at Advanced, Home with Customize open (named layouts, link groups), Home at Intermediate, Settings; Brokerage at 1440.
- `#/AAPL/workspace` (new): `definition-list` (serious), the earnings panel's key-value list `#wsb-tearn > .ws-kv`, 4 nodes at 1440, 1 at 390. DEFECT D3.
- `#/AAPL/financials`, quarters: `scrollable-region-focusable` (serious), `#fin-congress > .tscroll` at 1440 and `#fin-earnings > .tscroll[data-wide]` (3 nodes) at 390. DEFECT D3.
- `#/AAPL/earnings`: `color-contrast` (serious) on a `.toast` at 1440; `scrollable-region-focusable` on `#sec-estimate-revisions > .tscroll[data-wide]` (2) at 390. LIMIT L3.
- Brokerage at 390: `color-contrast` on a `.toast`. LIMIT L3.

All four rules fire on markup that was already in 2ed9722 (the `.ws-kv` list, the `.tscroll` tables, the shared toast); they show now because the company grid is a new screen and the live data makes the tables overflow, which the suite's fixtures do not (the same shape as Pass 1's D1).

### Findings

**DEFECT**

- **D1. Milo is told the wrong chart when the chart is pressed before Milo is opened.** Plan item 3 says the chart or section "pressed or nearest the top" is sent to Milo. On Financials at 1440, pressing Cash flow by quarter and then Ask Milo in the top bar opens the side panel, which narrows the page and moves the chart; the request named "Revenue and profit" (twice, items 3b) and Milo explained the wrong chart. With Milo already open the same press works (item 3). Where: `static/v2/js/ui/inview.js` with the page's repaint on the narrower width; the suite's `tests/test_pass2_place.py` does not open the panel after the press.
- **D2. Three of this pass's own journeys fail from a clean clone** (counts block): the export, the passkey and the named-layout journeys, 1 of 3 and then 0 of 3 passing alone. The build's own count at the same code was green, so they depend on the machine or the hour. One has a product half, reproduced on the copy through the gate: a name typed into "Save this layout as" within about half a second of pressing Customize is wiped when the saved-layout list arrives and the bar repaints (the suite's journey types at once; a person typing a second later is not affected). The other two were not diagnosed further here: the export journey reads `#main` as empty after switching to print media; the passkey journey finds no "Sign in with a passkey" button after sign-out (on the copy a passkey sign-in fired on its own on the sign-in page right after sign-out, through the browser's passkey autofill, which may be what the journey meets).
- **D3. axe serious violations on screens this pass delivers, on live data**: the company grid (`definition-list`) and Financials (`scrollable-region-focusable`), both widths. Plan item 6 promised axe clean on the drawn Financials page; item 8 adds the grid.

**CORRECT REFUSAL**

- The gate without and with wrong credentials (401, nothing of Optic shown). A wrong password: "Email or password is incorrect." Forgot password: "If an account uses that address, a reset link is on its way." for both addresses, and mail only for the real one. Billing off: no Upgrade and no price; "Plans are not on sale yet. Every account is on Free." Brokerage off: "Brokerage linking is not switched on for this deployment." Alert email off: "These alerts are shown in Optic; email delivery is not set up for readers."

**LIMIT** (for the operator to carry to the next round as scope)

- **L1. The brokerage link (SnapTrade) cannot be tested**: no SnapTrade test keys exist yet. The off state was checked; the link waits on test keys.
- **L2. The alert digest recipient is an open product question for Alexander**: as built, delivery sends one digest to one configured address (`ALERT_EMAIL_TO`, else `FEEDBACK_EMAIL_TO`), the owner's, not to each reader who set an alert. Recorded, not decided.
- **L3. axe on screens outside Round 2's items**: the Earnings tab's estimate revisions table at 390 and the shared toast's contrast (Earnings at 1440, Brokerage at 390). Pre-existing markup.
- **L4. Declared not built in this pass by the plan**: Investing and Earnings send their tab to Milo, not the chart in view; the sector or holdings donut and the sector treemap; the Read page's Desk keeps its own layout; the grid is reached by "Open as panels", not a stock-page tab; more than one price (tiers) is round 3.

**Observations (not findings)**

- O1. After the soak the uvicorn process held 422 file descriptors and 2.17 GB, and 440 and 2.20 GB five minutes later at rest (Pass 1: 121 to 171 and 0.4 to 0.7 GB). The EDGAR insider fill was reading 280 AAPL filings in the background then. Worth one more reading by the operator before delivery.
- O2. The evaluator account is on plan Enterprise on this copy (4,000 Milo messages a day), so the free plan's 3-a-day refusal is not what it meets.
- O3. A code comment in `pages/workspace.js` (the company grid) still says "Gold and Violet"; the screen says Teal.

**Harness faults** (fixed and re-run before this report, counted neither way)

- The first 1D check matched another "1D" button; re-run on `[data-hm-span='1d']`.
- The first named-layout run typed the name at once and lost it to the repaint (the race in D2), and a later reset step clicked a closed menu; re-run typing after the list arrived and opening the menu first.
- The company-grid check ran while Customize was still open from the failed layout run, so the linked-ticker box was hidden; re-run with Customize closed.
- The first insider check looked only at the 25 rows shown (all Yahoo); re-read through the page's own request (51 SEC rows).
- The place-kept check compared raw scroll offsets while the page was still filling; re-run comparing the heading in view (item 3 of the plan: "Operating income, by business segment" before and after, scroll 4,579 both times).
- The first Milo-context check read `focus` at the top of the request instead of `context.focus`; the reading was corrected and the run repeated.
- The first passkey run waited for a sign-out request by the wrong path, so its passkey stayed; the second run signed out through the sessions list and removed both passkeys.
- The first reset-mail run reused one page for two addresses and found the form still in its forgot mode; re-run in a fresh browser per address.

### Leave as found

Created on the copy by this run, all ours:

- Evaluator account: about 20 sessions from fresh browsers (signed in through the form; most left to expire); five Milo messages (four chats on AAPL Financials at about 22:28, 22:30, 22:31 and 22:32 UTC and one Deep Research at about 22:29; its plan allows 4,000 a day); one password-reset token, mailed, not used; two passkeys added and removed (0 left); one named layout saved and deleted (0 left); the Home layout reset to its standard panels, the link group put back to Blue and the Blue ticker back to SPY; preference rows touched by the level control.
- Owner account: one session (Settings and Metrics read only).
- `usage_event` visit rows from each fresh browser context; Mailpit: one reset message to the evaluator.
- Nothing else: no variable set, edge-optic, mailpit and edge-optic-mail not touched, no customer data on the copy, no Stripe object, no SnapTrade call.

Screenshots and raw results: `scratchpad/p2/run/` of this session (untracked, outside every repository).

### Readiness

Machine half on 620c6d4: deploy verified; the browser run from outside passed every reachable Round 2 item except D1; three DEFECTS stand (D1 Milo's chart in view when Milo opens after the press; D2 three of the pass's own journeys red from a clean clone; D3 axe on the company grid and Financials on live data), and the in-session intraday half is NOT RUN until the market is open. Not satisfied as it stands; the human half and the verdict are the operator's.

Key file: `~/.conjure/optic-eval.key` is still in place (mode 600, lines user, gate, evaluator, admin): the human half and the delivery recording still need it.


### Round two, 2026-11-18 (D1, D2, D3 re-tested)

**Kind of run: real browser from outside, through the gate, real passwords** (Playwright Chromium, headless, driven from the ops Mac against https://edge-optic-production.up.railway.app with the real gate password, signing in on the product's own form with the evaluator's real password read from `~/.conjure/optic-eval.key` into process memory). The suite ran from a fresh clone on the ops Mac. Round two re-tests the DEFECT items of round one (the section above) only, plus a short re-walk and soak; the human half and the verdict are the operator's; no label was applied, the issue was not moved and nothing was posted on it.

Product: Optic (NEW BUILD lane). Issue CON-54, order 69988272-31ff-416d-9687-f21e101ab3fa. Environment: Railway project `conjure-optic-eval`, environment `production`, service `optic` behind `edge-optic`. Commit tested: **c91613ea6fcd5dec2adabd5707bbe673712e859f** (fork sidprobstein/optic, branch `factory/pass-2-works-data-workspace`). Run 2026-11-17 23:19 to 2026-11-18 00:37 UTC, after the market's close. Operator's word in session: "Fix D1, D2, D3 now, redeploy, re-run the affected items."

#### Could not be reached (failures of the test, not passes)

1. **The in-session intraday half** (round one's item 1) stays NOT RUN: this round also fell after the close, and it is not a defect item. Ask 14 of the human script.
2. **The reset link followed**: not in scope this round and not repeated (deploy record, item 11).

#### Deploy verification, quoted

From `handoffs/optic-pass-2/deploy-verify-CON-54-round2.md`: "DEPLOY VERIFIED at c91613ea6fcd5dec2adabd5707bbe673712e859f on f61fc25c-d201-4015-be98-318a6cff8e7c, identified by tree checksum 28cee1c9... and build id 9c1e4f84ae82". Migrations applied [1..22] = known [1..22], unchanged; customer data counts identical in every table.

#### The fixes

| Defect | Fix commit | What changed | Suite case that now covers it |
| --- | --- | --- | --- |
| D1 | 785f01d (file renamed in 38ff235) | `static/v2/js/ui/inview.js`: the press is kept by the chart's name, found again after the page redraws, and holds until the reader scrolls on their own (wheel, swipe or a scrolling key). Cause: the press was held as an element that had to stay on screen; Financials redraws every chart as its later figures arrive (the EDGAR insider fill), so the pressed element was gone by the question, and the panel had also moved it (on the copy this round: from 291 px to 1,334 px, off screen) | `tests/e2e/test_pass2_milo_view.py::test_a_chart_pressed_before_milo_opens_from_the_top_bar_is_the_one_milo_is_told`: press the chart, open Milo from the top bar, let the held insider history redraw the page, ask, read `context.focus.in_view` in the chat request; then a wheel scroll hands it back. Fails on the old inview.js ("Cash flow"), passes now |
| D2, product edge | 46c47e1 | `pages/workspace.js`: the saved-layout list redraws in its own slot; the typed name is kept apart from the box and put back, with the caret, on any whole-bar redraw | `tests/e2e/test_pass2_workspace.py::test_a_named_layout_saved_in_one_browser_opens_in_another` types the name the moment Customize opens, holds the list until then, checks name and focus survive its arrival. Fails on the old workspace.js (`'' == 'Earnings week'`), passes now |
| D2, the journeys | 46c47e1, c91613e | Export: waited for "Apple" in `#main`, which the Overview it came from already showed, so it read the Overview or the page in between; now waits for the sheet and its enabled print button. Passkey: opened sign-in by changing only the #, where the app still held the signed-in account and went Home; now loads sign-in afresh after the cookies are cleared, and clicks through locators that survive Settings' redraws. Index Read (found red once in this round's first clean run, "Element is not attached to the DOM"): the same stale-handle wait, now a locator and a wait until the read has finished | the three named journeys plus `test_the_index_read_is_asked_from_the_board_and_answers_in_place` |
| D3 | 556014f | Company grid (`pages/workspace.js`): each figure's note was a `small` inside a dl group; it is now a second `dd`, styled as before. Financials (`ui/align.js`): a table box that scrolls either way becomes a keyboard stop (`tabindex=0`, `role=region`, a name from its caption, fold or section heading); only what was added is removed when it stops scrolling; re-measured when a fold opens | `tests/e2e/test_pass2_axe.py`, four cases: Financials with quarters, the earnings record and fifteen congressional trades, and the company grid with its Earnings panel drawn, each at 1440 and 390, axe clean. All four fail on the old markup |

#### Counts block

| Item | Result |
| --- | --- |
| Commit tested | c91613e, fresh clone of the fork branch in a new empty directory, HEAD verified equal, tree clean, push address DISABLED |
| Suite from clean | **9,170 passed, 0 failed, 1 skipped of 9,171**, 1,967 s (23:53:19 to 00:26:07 UTC), outbound HTTP pinned to 127.0.0.1:9, no ANTHROPIC_API_KEY in the shell |
| The one skip | `tests/test_brokerage_exposure.py::test_live_qqq` (his live EDGAR test, `OPTIC_LIVE_EDGAR=1` to run), the same one skip as every earlier run |
| Against round one | 9,162 passed, 3 failed, 1 skipped of 9,166; now 9,170 passed, 1 skipped of 9,171 (the 5 new cases: 1 D1 journey, 4 axe journeys) |
| Earlier clean runs this round, not counted as the result | at 556014f, collection refused: the new journey's file name `tests/e2e/test_pass2_place.py` collided with `tests/test_pass2_place.py` (renamed in 38ff235); at 38ff235, 9,169 passed, 1 failed (the Index Read journey, fixed in c91613e), 1 skipped |
| The journeys alone, ten times each, in the clean clone | export **10 of 10**, passkey **10 of 10**, named layout **10 of 10**; Index Read 10 of 10 (00:26 to 00:36 UTC) |
| Browser journeys in the suite | 135 of 135 passed |
| Pass 2 tests | 68 collected under test_pass2_*: 68 passed |
| Eval, quality set | `tests/test_milo_eval.py`: 221 of 221 passed |
| Eval, injection set | INJ-01 to INJ-14, **14 of 14**; red team `tests/test_milo_redteam.py` **38 of 38** |
| Eval, live smoke | Excluded for want of a key in the suite's shell; not a skip. Milo answered live on the copy (D1 runs) |
| Suite needs no API key | yes |
| HTTP soak | 30 page loads, 8,640 requests, 0 failures, as the evaluator through the gate |
| OUTCOME INSTRUMENTED | NOT APPLICABLE: no outcome named |
| Stack torn down | none brought up (the journeys start their own servers); clones, runners and output stay in the session scratchpad |

No model call changed this round (D1 changes only which name the page sends; the server's check in `app/ai.py` is unchanged), so rule 10 is met by the sets above.

#### The re-run, item by item (through the gate, real passwords, evaluator account, 1440 by 900 unless a row says 390)

| # | Item | Asked | What the copy did | Re-verified (UTC) | Pass |
| --- | --- | --- | --- | --- | --- |
| D1 a | Milo given the view, D1's order | Financials (AAPL), Quarters, Cash flow by quarter scrolled to 291 px and pressed, then Ask Milo in the top bar, "Explain this chart in two short paragraphs." | the panel moved the chart from 291 px to 1,334 px; the chat request carried `context.focus.in_view` = {metric "Cash flow by quarter", period "quarters"}; Milo answered "For AAPL, the quarterly cash flow chart..." (1,976 characters, on cash flow) | 23:56:50 | yes |
| D1 b | the same, a second fresh browser | as above | the same in_view; "For AAPL, the cash flow chart shows quar..." (1,782 characters) | 23:56:58 | yes |
| L1 | Named layouts, typing right after Customize | Customize pressed, the name typed at once (finished 0.30 s after the press), Save to my account | the saved-list request answered at +0.24 s, while the name was being typed; the box still held "Round two 2357" after it; PUT 200; "Round two 2357 is saved on your account." | 23:57:05 | yes |
| L2 | ...across two browsers | a second browser, signed in through the form, Customize, Saved layouts, Open | "Saved layouts (1)"; "Round two 2357 is open as My Desk." | 23:57:07 | yes |
| L3 | ...delete | Delete in Saved layouts | DELETE 200, 0 layouts left | 23:57:07 | yes |
| E1 | Export to PDF | `#/AAPL/sheet`, after its print button was enabled, printed by Chromium | a 210,250-byte PDF; the sheet's text has AAPL and Apple; no page error | 23:57:11 | yes |
| P1 | Passkey add | Settings, Add a passkey (Chromium's virtual authenticator) | register verify 200; 1 passkey on the account | 23:57:13 | yes |
| P2 | Sign in with the passkey alone | Settings' "Sign out" on this device, then a fresh sign-in page, "Sign in with a passkey" | sign-out 200; `/api/auth/me` signed out; login verify 200; signed in as the evaluator | 23:57:16 | yes |
| P3 | Remove | Remove, then confirm | DELETE 200; 0 passkeys left | 23:57:16 | yes |
| X1 | axe, company grid, 1440 | `#/AAPL/workspace` at Advanced, the Earnings panel drawn | 0 violations; no sideways scroll | 23:57:27 | yes |
| X2 | axe, Financials, 1440 | `#/AAPL/financials`, Quarters | 0 violations; four scrolling table boxes, each `tabindex=0` with a name (three "View data, table" in Segments, "Congressional disclosures, table") | 23:57:30 | yes |
| X3 | axe, company grid, 390 | as X1 | 0 violations; no sideways scroll | 23:58:02 | yes |
| X4 | axe, Financials, 390 | as X2 | 0 violations; eight scrolling boxes, each reachable and named (Statements, Segments, "Earnings track record, table", "Insider trades, full history, table", "Congressional disclosures, table") | 23:58:06 | yes |
| W1 | Re-walk, Home at Advanced | signed in, live feeds | no raw text, no failed block, no sideways scroll, no page error | 23:59:07 | yes |
| W2 | Re-walk, Home at Beginner | same | same | 00:00:09 | yes |
| W3 | Re-walk, AAPL Overview | same | same, nothing left loading | 00:00:12 | yes |
| W4 | Re-walk, AAPL Chart | same | same, nothing left loading | 00:00:16 | yes |
| S | Soak | 30 page loads through the gate, signed in | 8,640 requests, all 200, 0 failures | 00:02 to 00:09 | yes |

axe: **zero serious and zero critical** (zero violations of any impact) on the company grid and Financials at both widths, on live data.

#### Verdicts on round one's defects

- **D1: fixed and re-verified.** The pressed chart reaches Milo after the panel opens and moves it, twice on the copy; covered by the new journey, which fails on the old code.
- **D2: fixed and re-verified.** The layout name typed during the list's arrival is kept on the copy; the suite from clean is green (9,170 passed, 1 skipped) and the three journeys pass 10 of 10 alone; the fourth journey of the same kind found on the way (Index Read) is fixed under the same defect and also 10 of 10.
- **D3: fixed and re-verified.** axe clean on both screens at both widths on live data; covered by four new journeys that fail on the old markup.

#### Findings this round

**DEFECT**: none new.

**LIMIT**

- **L5. Names of the Financials table boxes repeat.** Several boxes in one section carry the same name ("View data, table" three or four times in Segments). axe's WCAG A and AA rules pass; its best-practice rule `landmark-unique` (not in the bar this pass promised) would flag them. One line in `ui/align.js` (prefix the section's heading) would fix it. Not fixed: outside D1 to D3.

**Observations (not findings)**

- O1. Memory and file descriptors at rest. On the new process: at boot 54 fds, 390 MB; after the browser run 277 fds, 1.09 GB; after the soak 344 fds, 1.14 GB; at rest 365 (00:10), 577 (00:27) and 579 fds (00:36) with 1.24 GB. The previous process (620c6d4) read 570 fds and 2.26 GB at rest at 23:19, an hour after round one. Pass 1: 121 to 171 fds, 0.4 to 0.7 GB. The count rises with use and levels near 580 at rest; what the descriptors are was not readable from the ssh session (readlink refused). Worth the operator's eye before delivery; not a regression of this round (the same growth on the code before it).
- O2. The D3 change to `ui/align.js` is shared, so table boxes that scroll on other pages (the Earnings tab's estimate revisions at 390, LIMIT L3) are now keyboard stops as well; not re-scanned this round, so L3 is carried unchanged.

#### Limits carried forward

- **L1. The brokerage link (SnapTrade)**: still untestable, no SnapTrade test keys; carried unchanged.
- **L2. The alert digest recipient**: still an open product question for the customer (one configured address, the owner's); carried unchanged.
- **L3. axe outside Round 2's items** (the Earnings tab's estimate revisions table at 390, the shared toast's contrast): carried; the table part may now be covered by D3's shared fix (O2), not re-scanned; the toast contrast is untouched.
- **L4. Declared not built in this pass**: Investing and Earnings send their tab to Milo, not the chart in view; the sector or holdings donut and treemap; the Read page's Desk keeps its layout; the grid reached by "Open as panels"; tiers are round 3. Carried unchanged.

#### Harness faults (fixed and re-run before this report, counted neither way)

- The re-walk counted the skeleton inside Home's hidden "Your portfolio" panel as "still loading" (the panel is hidden until the brokerage answers, by design, and the skeleton is not visible: hidden, no offsetParent); re-read checking visibility, nothing visible left loading.
- The first count before the deploy timed out on `railway ssh` (connect timeout); retried at 23:54:58 UTC, and that reading is the one in the deploy record.

#### Leave as found

Created on the copy by this run, all ours, on the evaluator account only:

- About 17 sessions from fresh browsers through the form (most left to expire) and one from the passkey sign-in; 2 Milo chat messages (23:56, on AAPL Financials; the plan allows 4,000 a day); one named layout saved and deleted (0 left); one passkey added and removed (0 left); the second browser's Home put back on Market Overview; `usage_event` rows from each fresh browser.
- Nothing else: no variable set; edge-optic, mailpit and edge-optic-mail not touched; no mail sent; no Stripe object; no SnapTrade call; the owner account and the first test account not touched.

Screenshots, the PDF and raw results: `scratchpad/r2/run/` of this session (untracked, outside every repository).

#### Readiness

Machine half on c91613e: deploy verified; D1, D2 and D3 fixed and re-verified on the live copy through the gate; the suite from clean green apart from the one standing skip; the in-session intraday half still NOT RUN until the market is open. The human half and the verdict are the operator's.

Key file: `~/.conjure/optic-eval.key` is still in place (mode 600, lines user, gate, evaluator, admin): the human half and the delivery recording still need it.

### Round three, 2026-11-18 (D4, D5 from the human half re-tested)

**Kind of run: real browser from outside, through the gate, real passwords** (Playwright Chromium, headless, driven from the ops Mac against https://edge-optic-production.up.railway.app with the real gate password, signing in on the product's own form with the evaluator's real password read from `~/.conjure/optic-eval.key` into process memory). The suite ran from a fresh clone on the ops Mac. Round three re-tests the two DEFECT items of the human half (Conjure `handoffs/optic-pass-2/gauntlet-CON-54-human-half.md`, D4 and D5) and the machine checks they touch; the human re-walk of asks 11 and 26 and the verdict are the operator's; no label was applied, the issue was not moved and nothing was posted on it.

Product: Optic (NEW BUILD lane). Issue CON-54, order 69988272-31ff-416d-9687-f21e101ab3fa. Environment: Railway project `conjure-optic-eval`, environment `production`, service `optic` behind `edge-optic`. Commit tested: **34a30b71c56866c8c41f62e1c922f0555c5f1f7c** (fork sidprobstein/optic, branch `factory/pass-2-works-data-workspace`). Run 2026-11-18 18:09 to 19:35 UTC, the market open until 21:00 UTC. Operator's word in session: the go to fix D4 and D5, redeploy in place and re-run the affected machine checks.

#### Could not be reached (failures of the test, not passes)

1. **Asks 11 and 26 by a person** (source line under the Financials charts; the sheet printed from a real browser's print dialog): the machine re-ran both below, but the operator's own Chrome print is the one that showed D4, and Chromium headless only reproduces it by printing on paper wide enough to keep the desktop layout. The operator's re-walk of asks 11 and 26 is still to do.
2. **The reset link followed**: not in scope this round and not repeated (deploy record, item 11).

#### Deploy verification, quoted

From Conjure `handoffs/optic-pass-2/deploy-verify-CON-54-round3.md`: "DEPLOY VERIFIED at 34a30b71c56866c8c41f62e1c922f0555c5f1f7c on f33bedf0-b97c-480a-b293-e577e671b930, identified by tree checksum 98929266... and build id 7689d8061f5e". Migrations applied [1..22] = known [1..22], unchanged; customer data counts identical in every table. Railway reached on the FALLBACK login (no workspace token file on this Mac).

#### The fixes

| Defect | Fix commit | What changed | Suite case that now covers it |
| --- | --- | --- | --- |
| D4, the width | 5856ac7 | `static/v2/css/pages.css`, `@media print`: the shell, the sheet, each sheet page and its lists are blocks, not grids. Cause: the block hid `.rail` but left `.shell` its two columns (`var(--rail) minmax(0, 1fr)`, components.css line 5), so a print from a window wider than the 860 px breakpoint laid the sheet into the rail's 256 px column. Headless Chromium at Letter and A4 paper width never saw it: those widths fall under the breakpoint, where the shell is one column anyway, which is why round two's export check passed | `tests/test_research_sheet.py::test_the_sheet_prints_in_one_column_and_never_as_a_grid` (reads the print block as text) and `tests/e2e/test_pass2_print.py::test_the_research_sheet_prints_at_full_width_from_a_wide_window[Letter]` and `[A4]` (1280 px window, print media, `.sheet` at least 600 px wide, two pages at most). All three fail on the old stylesheet (the journey: `{'x': 0, 'w': 256, 'shell': 'grid'}`) |
| D4, the overlap | 5856ac7 | Same block. A second cause, not the width: inside a grid Chromium printed a paragraph broken across a page over the one after it (the operator's page 2: "Beat the estimate" over "revenue of about"). Measured on the copy over a sweep of 48 PDFs (Letter, A4 and a 13.33 in wide sheet, page heights 4 to 11.5 in): 242 overlapping characters with the old CSS, 70 with the shell made one column alone, 0 with blocks. The grids' gaps became top margins (3 px between parts, 9 px above a heading, 2 px between list items) | the same text test (the shell, the sheet and the pages are blocks); the sweep is in the session scratchpad, not in the suite |
| D5 | 34a30b7 | `static/v2/js/pages/financials.js`: each of the eight statement charts ends its caption with "Source: " and the feed's own source line, or "the company's statements, as Yahoo Finance carries them" when the feed names none; the segment figures with "Source: the company's 10-Q and 10-K filings, from SEC EDGAR". The period line stays; existing class `fv-unit`, no new colour; no delay wording (statements are filed, not quoted) | `tests/test_pass2_provenance.py::test_every_financials_chart_names_its_source_under_it_and_no_delay`, which fails on the old financials.js ("no source line under Revenue and profit") |

#### The print, before and after (on the copy, AAPL, `#/AAPL/sheet`, signed in)

| Measure | Before (c91613e, f61fc25c) | After (34a30b7, f33bedf0) |
| --- | --- | --- |
| `.sheet` in print media, 1280 px window | 256 px wide at x 0; `.shell` grid `256px 1024px` | 1280 px wide at x 0; `.shell` block |
| `.sheet` at the printable areas, 710 x 940 and 688 x 1010 | 710 and 688 px wide, 1,813 and 1,809 px tall | 710 and 688 px wide, 1,790 and 1,809 px tall |
| Chromium PDF at Letter and A4 (laid out at the paper's width) | 2 pages each, 0 overlapping characters | 2 pages each, 0 overlapping characters |
| Chromium PDF on a 13.33 in wide sheet (the desktop layout, as the operator's Chrome printed) | 4 pages, the sheet in a narrow left column | 2 pages |
| Sweep of 48 PDFs, overlapping characters | 242 | 0 |
| The operator's PDF (Chrome 157, Letter) | 4 pages, 33 overlapping characters on page 2 | not re-printed by a person (see above) |

Overlap is counted on the PDF's own text layer (pdfplumber), characters whose boxes cross another's by half a glyph each way; the same count finds the 33 on the operator's page 2. The block's comment now cites these measurements in place of "measured at 710 x 940".

#### Counts block

| Item | Result |
| --- | --- |
| Commit tested | 34a30b7, fresh clone of the fork branch in a new empty directory, HEAD verified equal, tree clean, push address DISABLED (the clone that was deployed) |
| Suite from clean | **9,174 passed, 0 failed, 1 skipped of 9,175**, 1,998 s (19:00:57 to 19:34:17 UTC), no ANTHROPIC_API_KEY in the shell |
| The one skip | `tests/test_brokerage_exposure.py::test_live_qqq` (reads EDGAR; `OPTIC_LIVE_EDGAR=1` to run), the same one skip as every earlier run |
| Suite in the working checkout, before the push | 9,174 passed, 1 skipped (18:09:26 to 18:42:43 UTC); `node --check static/v2/js/pages/financials.js` passed (no other JS edited) |
| Against round two | 9,170 passed, 1 skipped of 9,171; now 9,174 passed, 1 skipped of 9,175 (the 4 new cases: 1 print text test, 2 print journeys, 1 source-line text test) |
| Pass 2 browser journeys, `tests/e2e/test_pass2_*.py`, from the clean clone | **26 passed** in 426 s (18:53:39 to 19:00:46 UTC), among them the two print journeys, the four axe journeys and the Milo-view journey |
| Browser journeys in the suite | 137 collected under tests/e2e, all passed in the clean run |
| Pass 2 tests | 71 collected under test_pass2_* (unit and e2e): 71 passed |
| Eval, quality set | `tests/test_milo_eval.py`: 221 of 221 passed |
| Eval, injection set | INJ-01 to INJ-14, **14 of 14**; red team `tests/test_milo_redteam.py` **38 of 38** |
| Eval, live smoke | Excluded for want of a key in the suite's shell; not a skip. Milo answered live on the copy (D1 re-run below) |
| Suite needs no API key | yes |
| HTTP soak | 30 page loads, 8,640 requests, 0 failures, as the evaluator through the gate |
| OUTCOME INSTRUMENTED | NOT APPLICABLE: no outcome named |
| Stack torn down | none brought up (the journeys start their own servers); clones, runners and output stay in the session scratchpad |

No model call changed this round. The figcaption change touches the chart Milo is told about only in its markup: the page names the chart in view by its heading (`ui/inview.js`), which is unchanged, and the Milo-view journey and the live re-run below both send "Cash flow by quarter".

#### The re-run, item by item (through the gate, real passwords, evaluator account, 1440 by 900 unless a row says otherwise)

| # | Item | Asked | What the copy did | Re-verified (UTC) | Pass |
| --- | --- | --- | --- | --- | --- |
| R1 | Print, 1280 px window, Letter | `#/AAPL/sheet` after its print button was enabled, print media, PDF at Letter | `.sheet` 1280 px wide at x 0, shell block; 2 pages, 210,213 bytes, 0 overlapping characters; no page error | 18:45 | yes |
| R2 | Print, 1280 px window, A4 | as R1, PDF at A4 | 2 pages, 210,080 bytes, 0 overlapping characters | 18:45 | yes |
| R3 | Print, printable areas | windows of 710 x 940 and 688 x 1010, print media | 710 and 688 px wide, 1,790 and 1,809 px tall; no overlapping boxes in the DOM | 18:45 | yes |
| R4 | Print, desktop layout on paper | a 13.33 by 11 in sheet from a 1280 px window, the shape of the operator's print | 2 pages (4 before) | 18:45 | yes |
| R5 | Print, page-break sweep | 48 PDFs, Letter, A4 and 13.33 in wide, heights 4 to 11.5 in | 0 overlapping characters (242 before) | 18:45:39 | yes |
| S1 | Source under every Financials chart, fiscal years | `#/AAPL/financials`, Fiscal years | 10 figures, each with a source line: the six statement charts "Source: The company's annual and quarterly statements as Yahoo Finance carries them" (the feed's own line), the four segment figures "Source: the company's 10-Q and 10-K filings, from SEC EDGAR"; the period lines kept; no delay wording | 18:50:14 | yes |
| S2 | ...quarters | the same, Quarters | 12 figures, each with a source line, Cash flow by quarter and Cash and debt by quarter among them; no delay wording | 18:50:17 | yes |
| X1 | axe, Financials, quarters, 1440 | WCAG 2.1 A and AA, live data, the source lines drawn | 0 violations; 12 source lines; no sideways scroll; no page error | 18:46:54 | yes |
| X2 | axe, Financials, quarters, 390 | as X1 at 390 by 844 | 0 violations; 12 source lines; no sideways scroll | 18:46:58 | yes |
| D1 a | Milo given the view, after the caption change | Financials (AAPL), Quarters, Cash flow by quarter scrolled to 291 px and pressed, then Ask Milo in the top bar, "Explain this chart in two short paragraphs." | the panel moved the chart from 291 px to 1,316 px; the chat request carried `context.focus.in_view` = {metric "Cash flow by quarter", period "quarters"}; Milo answered on cash flow (1,834 characters) | 18:47:06 | yes |
| D1 b | the same, a second fresh browser | as above | the same in_view; 1,852 characters, on cash flow | 18:47:16 | yes |
| Soak | 30 page loads through the gate, signed in | | 8,640 requests, all 200, 0 failures | 18:50 to 18:56 | yes |

axe: **zero violations of any impact** on Financials at both widths, on live data, with the new caption lines.

#### Verdicts on the human half's defects

- **D4: fixed and re-verified by the machine.** The sheet prints at the page's width from a wide window, two pages at Letter and A4, and the page-break overlap is gone over every page height tried; covered by a text test and two journeys that fail on the old stylesheet. The operator's own print (ask 26) is still to re-walk.
- **D5: fixed and re-verified by the machine.** Every chart on Financials names its source under it, with no delay, at both periods; covered by a text test that fails on the old code. Ask 11 is still to re-walk.

#### Findings this round

**DEFECT**: none new.

**Observations (not findings)**

- O3. The statement charts' source line takes the feed's own wording when it sends one, so on the copy it reads "Source: The company's annual and quarterly statements as Yahoo Finance carries them" (capital T, no comma), while the segment figures read "Source: the company's 10-Q and 10-K filings, from SEC EDGAR". Both are correct; the capital after "Source:" is a style point the operator may want lowercased in the next round. At 1440 the longer line wraps to leave one word ("them") on its second line in the two-up charts.
- O1, carried. Memory and file descriptors at rest on the new process: at boot 85 fds, 416 MB; after the browser run 278 fds, 1.28 GB; after the soak 281 fds, 1.37 GB (flat across the soak); after the clean suite, at rest, 19:34:25 UTC, 541 fds, 1.80 GB. The same climb with use as rounds one and two; worth the operator's eye before delivery; not a regression of this round.

#### Limits carried forward

- **L1. The brokerage link (SnapTrade)**: still untestable, no SnapTrade test keys.
- **L2. The alert digest recipient**: still an open product question for the customer.
- **L3. axe outside Round 2's items** (the Earnings tab's estimate revisions table at 390, the shared toast's contrast); the human half's F2 (the save toast not noticed) sits here.
- **L4. Declared not built in this pass**: unchanged.
- **L5. Names of the Financials table boxes repeat**: unchanged.

#### Harness faults (fixed and re-run before this report, counted neither way)

- The first source-line run timed out in the fiscal-years view waiting for a Playwright `:text-is` selector (also with `state="attached"`) while the figures were on the page (read directly at the time: ten figure headings, Revenue and profit first). Rewritten as a wait on the headings' text; S1 then passed.
- The PDF overlap counter first compared whole words on different lines only and found 0 on the operator's PDF, where the overlapping lines share one baseline; rewritten to compare characters, it finds the operator's 33 and was used for every count above.

#### Leave as found

Created on the copy by this run, all ours, on the evaluator account only:

- 17 sessions from fresh browsers through the form (sessions 81 to 98, most left to expire); 2 Milo chat messages (18:47, on AAPL Financials; milo_questions 37 to 39); `usage_event` rows from each fresh browser (624 to 651); auth_attempts 58 to 60.
- Nothing else: no layout, passkey or watch made; no variable set; edge-optic, mailpit and edge-optic-mail not touched; no mail sent; no Stripe object; no SnapTrade call; the owner account and the first test account not touched.

PDFs, screenshots and raw results: `scratchpad/r3/run/` of this session (untracked, outside every repository).

#### Readiness

Machine half on 34a30b7: deploy verified; D4 and D5 fixed and re-verified on the live copy through the gate; the suite from clean green apart from the one standing skip. Next is the operator's re-walk of asks 11 and 26, then the verdict, which is the operator's.

Key file: `~/.conjure/optic-eval.key` is still in place (mode 600): the re-walk and the delivery recording still need it.
