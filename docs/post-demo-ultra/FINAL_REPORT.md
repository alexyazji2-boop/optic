# Final report

Written in Phase 11 (directive 11, sections 11 and 12), 2026-10-30, on branch `post-demo-ultra`. Nothing was pushed or
deployed.

## Decision: NOT READY: BLOCKING ISSUES REMAIN

The terminal is simpler, more reliable and more accurate than the build the investors saw. Every step of the demo
journey passed on the final tree. Every defect this audit could reproduce in Optic's own code was fixed, except four
P2s. Three P0 items remain, and none of them can be closed by engineering alone:

1. **Milo's advice safeguards are not verified end to end (BUG-132, P0, OPEN).**
   - The last-line output check caught 14 of 50 advice sentences in a fresh set nobody had tuned it on.
   - Whether the model writes such sentences in the first place has never been measured, because no model key works
     on this machine (BL-01).
   - **What would unblock it:**
     - a working key, to run the evaluation suite's 100 answer-level checks and an unseen set of advice requests
       against the real model;
     - the owner's decision on a model-based reading of each answer (BL-07);
     - counsel on the advice boundaries (BL-02).
2. **The market data is unlicensed (BUG-022, BUG-023, P0, BLOCKED).** Yahoo Finance and an undocumented Robinhood
   endpoint feed the prices. During this audit Yahoo also refused some requests. The pages stated each refusal, but a
   demo depends on it. That is the owner's and counsel's decision (BL-09).

Everything else is ready for a human staging review, with the manual checks in section 17.

## 1 to 6. Features

FEATURE_REGISTRY.md inventories **95** features, the ids of its index:
- the shell, search, Milo and account rows A1 to A31;
- Home's layout and 27 panels;
- Markets, Discover, Compare;
- the Dossier's frame and eight tabs;
- Positions, Brokerage, Watchlist and Alerts, and the owner pages;
- Classic (one row for its 26 views) and the API (one row for its routes).

| Group | Ids | Tested | Passing | Partly verified | Blocked | Not tested | Evidence (TEST_RESULTS Phase 11) |
|---|---|---|---|---|---|---|---|
| Shell (A1 to A11) | 11 | 10 | 10 | | | 1 | the feature check, the journeys at three sizes, X09, X11. Scroll memory (A11) not tested |
| Search (A12 to A15) | 4 | 4 | 4 | | | | journey steps 3 and 4; X06, X10, X11; Phase 03's 27 scenarios; the API sweep |
| Milo (A16 to A20) | 5 | 5 | 5 | | | | journey steps 9 to 13; X02, X03, X10, X14; the Phase 07 and 08 reruns; the evaluation suite |
| Account (A21 to A31) | 11 | 10 | 9 | 1 | 1 | | the feature check, the keep sheet, the level across tabs, the API sweep. Sign-up, forgot and reset in the browser not rerun (A21; the suite covers them at the API). Email links, provider sign-in and passkeys need the providers and an authenticator (A22) |
| Home (00 to 27) | 28 | 28 | 27 | 1 | | | the feature check and `phase11_home_panels.py`. Your portfolio hides itself with nothing linked, by design; its linked state was not shown in Phase 11 |
| Markets (01 to 05) | 5 | 5 | 5 | | | | the feature check, failure states, journey step 15 |
| Discover (01 to 04) | 4 | 4 | 4 | | | | the same |
| Compare | 1 | 1 | 1 | | | | the same, X13 |
| Dossier (00 to 08) | 9 | 9 | 9 | | | | the feature check, journey steps 3 to 8, Phase 06's 16 checks and accuracy run, X01, X04, X06, X12 |
| Positions (01 to 03) | 3 | 3 | 3 | | | | the feature check, failure states |
| Brokerage (00 to 05) | 6 | 6 | 6 | | | | journey step 14, the scorecard check, Phase 09's H, Phase 10's R6 |
| Watchlist, Alerts | 2 | 2 | 2 | | | | the feature check (guest and reader) |
| Owner pages (01 to 04) | 4 | 4 | 4 | | | | the feature check, failure states |
| Classic | 1 | 1 | 1 | | | | 26 views at 1440 and 390, clean |
| API | 1 | 1 | 1 | | | | 145 GET routes as guest and reader: no 5xx |
| **Total** | **95** | **93** | **91** | **2** | **1** | **1** | |

**Failing: 0.** Every failure the checks found was fixed and checked again, or traced to a condition: a provider's
refusal, the audit's own load, or a check that was wrong. The open P2s (section 9) sit in passing features.

## 7. Bugs fixed

The register has 201 rows (BUG-001 to BUG-202; 140 was never assigned):
- 180 VERIFIED;
- 3 FIXED and awaiting what only a live environment or a browser timing can show;
- 11 BLOCKED on outside parties;
- 2 WONTFIX, with reasons;
- 5 OPEN.

Phase 11 found 23 of them (BUG-180 to BUG-202, the last after this report was first written):
- fixed 19: 18 VERIFIED, and BUG-182 FIXED with a source-level test, its two-minute timing being impractical to drive
  in a browser;
- decided not to fix 1 (BUG-192);
- left 3 OPEN, all P2.

The ones that mattered most:
- **BUG-200 (P1):** `/api/ticker` lost the next report date whenever a company's option chain was complete, in the
  build the investors saw since 2026-10-13. Milo's context and "what matters next" had no report date.
- **BUG-201 (P1):** with the date back, a report that had already happened read as the next one (KO).
- **BUG-202 (P1, never live):** BUG-201's first fix, made in the provider, would have taken the week's earlier reports, and
  their results, out of Earnings this week. The fix now sits where the next report is read. Found while preparing a
  hotfix of BUG-200 and BUG-201 for live main (section 17).
- **BUG-181 (P1):** Phase 10 had broken the owner's `publish.sh` deploy check.
- **BUG-193 (P1):** the Options page stayed loading for good after a failed load.
- **BUG-197:** a level changed in another tab left the open page in its old wording.

## 8. Remaining P0 issues

| Bug | What | Status | Needs |
|---|---|---|---|
| BUG-132 | The advice output check caught 14 of 50 unseen advice sentences; the model's own behaviour is unmeasured | OPEN | a working key (BL-01), the owner's decision on a model-based check (BL-07), counsel (BL-02) |
| BUG-022 | The overnight price comes from an undocumented Robinhood endpoint | BLOCKED | the owner and counsel (BL-09); a switch exists (`OPTIC_OVERNIGHT_FEED`) |
| BUG-023 | Yahoo Finance's data is not licensed for redistribution | BLOCKED | the owner: a licensed provider (researched 2026-10-24) |
| BUG-043 | Google's and Apple's sign-in state bound to the browser (Phase 10) | FIXED | Apple's live sign-in, which needs Apple, to verify |

## 9. Remaining P1 issues

| Bug | What | Status | Needs |
|---|---|---|---|
| BUG-021 | Production mail is in log mode: verification and reset links never reach a reader | BLOCKED | the owner's SMTP choice (BL-04) |
| BUG-026 | The public Optic Portfolio, a model book of Optic's signals with pretend money | BLOCKED | counsel (question Q4) |
| BUG-156 | The data-not-instructions rule now covers tools, search and files, and links show their host | FIXED | a live model to verify (BL-01) |

There is no open P1 defect in Optic's code. The open P2s:
- BUG-173: the header grows when a cold quote arrives (the owner's call);
- BUG-187: sign-in state is bound to one host (the live site is not affected);
- BUG-195: two example links wrap unevenly;
- BUG-198: an unknown symbol keeps the Dossier's actions.

## 10. Milo evaluation results

- **The evaluation suite:** 137 cases in 18 categories, 949 of 949 request-level checks.
  - **What it covers:** tool choice, factual support, calculations, freshness, authorization, injection, citations,
    the policy, the level and the budget.
  - **What it cannot cover:** the 100 answer-level checks need a model. None can be called (the key is refused,
    rechecked today), so they did not run.
- **The advice output check:** 14 of 50 advice sentences caught on fresh set D, and 0 of 50 research sentences held
  back. On set C, before Phase 08 widened the check, it had caught 28 of 50 (D-099).
- **End to end with the stand-in model:**
  - streaming in steps, with the first words in 0.16 to 0.68 s;
  - tools named while they run and listed with their times;
  - figures matching Optic's data within a cent;
  - New, Close, reopen and history;
  - isolation between readers;
  - the composer's limit, and the server's 413 for an overlong question;
  - a level change between two questions.
- **Not measured:** how a real model answers, how long its answers are, and whether it keeps to the advice policy
  (BL-01).

## 11. Market-data verification findings

- **Prices:** the header prices of SPY and NVDA within 0.5% of the quote API, and the Dossier's share price the
  quote's. Milo's three-month change and closes match the daily bars within a cent. The sandbox brokerage's weights
  recompute from their values.
- **The Dossier's figures against the provider's own answers:** 10 of 10 symbols, an unknown one included.
- **The reconciliation** (278 rows against a separate Yahoo client and the SEC), run three times:
  - **The final run:** 271 PASS, 5 FAIL, 2 UNVERIFIED.
  - **The misses are conditions, not defects:**
    - extended-hours prints read seconds apart;
    - a quote Yahoo refused that moment and Optic served marked partial;
    - TSM's yield, which Yahoo works at the previous close on a day the stock fell 5.9%.
  - **Two real defects it found, fixed:** the lost next report date (BUG-200) and a past report shown as next
    (BUG-201). BUG-201's first fix was itself moved (BUG-202).
- **Across features:** one SPY price on the quote, chart, Dossier and Milo (Phase 09's A, rerun). Late answers never
  reach the next symbol's page (Phase 09's B; X01, X08).
- **Conditions seen:** Yahoo refused some requests during the audit. Every page that met a refusal stated it and
  showed no figure in its place.

## 12. Simplicity improvements

Measured as a first-time guest against the build the investors saw (9fa0f36), the same afternoon:
- **Home at 1440:** cards 12 to 5, controls 92 to 65, words 799 to 666, page height 2,820 to 2,340 px.
- **Home on a phone:** controls 58 to 39, cards 13 to 6.
- **NVDA's Overview at 1440:** words 1,392 to 467, controls 96 to 45, cards 12 to 3, page height 4,996 to 2,495 px.
  Simple Analysis first; the Advanced Analysis replaces it only when asked.
- **Simple Analysis:** reads at about grade 6.5 (Flesch 70), with its terms defined in the sentence.
- **The level:** five levels on one slider, in three places. They change the words, never the figures, and now follow
  the reader across tabs.
- **The first view:** says what Optic is ("Prices, options, financials and filings for US stocks and funds, each
  figure with its source") and offers three ways to start.

The directive's questions, answered from what was measured:
- **Is the Home page overwhelming?** Less so: about a third fewer controls and half the cards.
- **Do readers have to read too much?** The Overview has two thirds fewer words.
- **Are there technical labels?** They are defined at the reader's level.
- **Do features compete?** One analysis at a time, and one primary action per view.
- **Is Simple Analysis simple?** At grade 6.5, mostly, but it still carries one sentence on how options dealers hedge.
- **Are advanced controls optional?** Yes.
- **Is the value apparent?** It is the first line of the first view.
- **Are Milo's answers long?** Not measurable without a model (BL-01).
- **Are numbers easy to read?** They carry tabular figures, their time and their source.
- **Is the navigation intuitive?** Names were unchanged by rule, and 27 navigation scenarios pass.

None of this is a reader study.

## 13. Performance measurements

- **Against Phase 09** (Phase 10's A/B with the feed answering, headless Chrome at 1440): no regression.
  - Dossier ready in 0.30 to 0.25 s, Home 0.36 to 0.35 s, Options 2.40 to 2.30 s.
  - Layout shift 0 on the Dossier, Compare, Markets and Earnings week (up to 0.217 before), and 0.004 on Home.
- **Search:** 15 to 21 ms cold, under 0.01 ms repeated, with the same answers on 8,139 query and limit pairs.
- **The event loop:** the longest stall while a question's symbols are found went from 112 to 16 ms.
- **Home in Phase 11:** on a quiet server every panel showed within 2.5 s at 1440 and none stayed loading on a phone.
  Under the audit's own load, with Yahoo refusing, panels took longer than 12 s and then filled in or stated the
  failure.
- **Not measured:** a real phone, a real network, production, or a real model's latency.

## 14. Security findings

- **Phase 10's review** (SECURITY_REVIEW.md): 17 findings (1 High, 6 Medium, 10 Low). 12 fixed and tested. 5 escalated
  to the owner (BL-10 to BL-13):
  - the Milo ceiling's number and a spend stop outside the app;
  - closing the origin to traffic that does not come through Cloudflare;
  - downloading a dependency scanner and pinned fonts;
  - the `__Host-` cookies, a session-bound CSRF value, passkey verification and the full CSP.
- **Phase 11's independent review of that commit:** one P1, the deploy check, now fixed; P2s fixed except BUG-187 and
  BUG-192. No key or token in any of the 1,196 tracked files.
- **Not done:**
  - a dependency vulnerability scan (BL-12);
  - any test against production or a third party;
  - penetration testing.

## 15. Legal-review dependencies

Engineering cannot settle these; each is written up for qualified counsel in COMPLIANCE_REVIEW.md:
- **Advice:** whether the policy, its disclosures and the research pages' wording are enough (section 6). Whether a
  model-based check is required, given the measured recall (section 4.2, BL-07).
- **Terms and Privacy:** their sufficiency, including the deletion and AI-disclosure wording (sections 6, 7 and 10).
- **Linking consent:** it still names the 2026-10-12 drafts (BL-08).
- **Market-data licensing:** Yahoo and the overnight feed (BL-09). Also the legal pages' "delayed about 15 minutes"
  sentence (section 9).
- **The public Optic Portfolio** (BUG-026).
- **The analytics design:** before anything is built (ANALYTICS_REVIEW.md).

## 16. Relevant Git commits (branch `post-demo-ultra`, from `9fa0f36`, nothing pushed)

| Commit | What |
|---|---|
| fce3e71 | Setup: the owner's directives saved, the tracking files |
| 8040f8a, 795325a, d4a2b1a | Phase 01: discovery and baseline |
| ce60b16, c6724ff, a76916b, 6f2e814 | Phase 02: one advice policy (with Milo's portfolio-privacy fix taken by hand from its branch) |
| 7b14b56, 2f6a548 | Phase 03: search, ticker state, SPY by default |
| 381a018, b07e181 | Phase 04: radical simplicity |
| e64a5ee, 448e633 | Phase 05: five knowledge levels |
| 0448900, 1652e14 | Phase 06: the Dossier |
| 874c109, f26af09 | Phase 07: Milo's streaming and conversation |
| ab5a2ae, 0268f7f | Phase 08: Milo's grounding and the evaluation suite |
| 17024f0, 3698975 | Phase 09: market data integrity |
| 3971e7f, a0e60f8 | Phase 10: performance, security, accessibility and failure states |
| e0dd2ff and the commit after it | Phase 11: the final audit, its fixes and this report (the second commit records the first one's id) |
| 537e101 and the commit after it | After Phase 11: BUG-202, the report-date fix moved out of the provider (the second records the first one's id) |

## 17. Production readiness recommendation

**Not ready for production.** It is ready for a human staging review once someone with the owner's authority accepts
the risks in section 8 for a staging audience. These manual and outside checks are required before production:

- **Legal:** counsel on everything in section 15.
- **Security:**
  - the owner's decisions on BL-10 to BL-13;
  - a dependency vulnerability scan;
  - the origin closed to traffic around Cloudflare;
  - Apple's live sign-in checked (BUG-043).
- **External providers:**
  - **A working Anthropic key.** Then run `tests/milo_eval/run_model.py` (the 100 answer-level checks) and an unseen
    set of advice requests against the real model, and read Milo's answers for length and grounding.
  - **SnapTrade** with real credentials (BL-03).
  - **SMTP**, so verification and reset mail reaches readers (BL-04, BUG-021).
  - **A licensed market-data provider** (BL-09).
  - **The production image built and checked** (BL-06; `publish.sh` reads the commit again).
- **User acceptance:** the fifteen-step demo by a person on a real iPhone in Safari and on a laptop, on a real
  network; a screen-reader pass (VoiceOver); a first-time reader trying Home and the Dossier.
- **Owner decisions:**
  - BUG-173 (the one-line header against its growth);
  - the Milo ceiling's number (BL-10);
  - the brokerage consent version (BL-08);
  - whether to build the analytics design.

Do not deploy from this branch without those, and only on the owner's word.

**One fix can go live on its own.** BUG-200 (the lost next report date) has been live since 2026-10-13. A hotfix of it and
BUG-201, built from live main, is on branch `hotfix-next-report-date` (`8e2cbf4`, worktree `~/Optic/wt-hotfix-report-date`),
rebased onto live main's `a10eaba` after WaveTrend shipped: one commit, its suite green (7,158 passed, 1 skipped), checked on
a local server with real data. It is not pushed: shipping
it is the owner's call.
