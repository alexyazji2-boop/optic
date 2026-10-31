# Progress

Read this and [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) before changing anything (directive 12).

## Current state

- **Current phase:** none. Phases 01 to 11 are complete (reports below). FINAL_REPORT.md holds the decision: **NOT READY: BLOCKING ISSUES REMAIN** (BUG-132, the advice output check, P0; BUG-022 and BUG-023, unlicensed market data, P0, the owner's and counsel's).
- **Branch / worktree:** `post-demo-ultra` in `~/Optic/wt-ultra`, from `9fa0f36` (tag `post-demo-ultra-baseline`). Upstream unset; nothing pushed or deployed.
- **Commits:** `fce3e71` setup; `8040f8a` and `795325a` Phase 01; `d4a2b1a` Phase 01 report; `ce60b16` Phase 02 policy module (WIP); `c6724ff` Milo portfolio privacy (cherry-pick of 2236205); `a76916b` Phase 02; `6f2e814` its commit id; `7b14b56` Phase 03; `2f6a548` its commit id; `381a018` Phase 04; `b07e181` its commit id; `e64a5ee` Phase 05; `448e633` its commit id; `0448900` Phase 06; `1652e14` its commit id; `874c109` Phase 07; `f26af09` its commit id; `ab5a2ae` Phase 08; `0268f7f` its commit id; `17024f0` Phase 09; `3698975` its commit id; `3971e7f` Phase 10; `a0e60f8` its commit id; `e0dd2ff` Phase 11; `6bc305f` its commit id; `537e101` BUG-202's fix (after Phase 11); the commit after it records that id.
- **Local server:** launch config `optic-ultra` (:8250, stand-in model :8251 from `tools/milo_standin_ultra.py`, which adds an `ADVISE` keyword that makes the answer break the policy and, since Phase 05, writes a Sector Read and a portfolio briefing in their writers' shapes; data `~/Optic/ultra-data`, sandbox brokerage, jobs off, no real model key). Seed password in `~/Optic/ultra-data/seed-output.txt` (never print it). The server does not reload Python: restart it after editing server code. The desktop app stops it when the session is paused; start it again with preview_start. `optic-ultra-p09` (:8252) serves the Phase 09 commit and `optic-ultra-base` (:8253) the demo-day build, from scratch worktrees, for A/B runs.
- **Working folder (outside the repo):** `~/Optic/work/post-demo-ultra-2026-10-29/` (tools/, phase02/ to phase11/ and the earlier folders). Phase 11's tools are `tools/phase11_*.py` and `tools/phase11_batch.sh`; its results are in `phase11/`.
- **Resource rule:** at most two subagents at a time (DECISIONS D-007).
- **Next action:** the owner's. FINAL_REPORT.md sections 8 and 17 list what only the owner, counsel and outside providers can do: a working model key and the model-based check (BUG-132), licensed data (BUG-022, BUG-023), the security decisions (BL-10 to BL-13), SMTP, and a human run of the demo on real devices. Nothing here is to be pushed or deployed without the owner's word. The hotfix of BUG-200 and BUG-201 went live on the owner's yes on 2026-10-31 as `8e2cbf4` (now origin/main), and was checked on the live site (FINAL_REPORT section 17).

## Phase 11 report (directive 11; reporting format of directive 00)

1. **Inspected.**
   - **Features:** every inventoried feature: the 75 route-level rows of the index at 1440 and 390, with a refresh and
     a failure state.
   - **The demo:** the fifteen-step investor journey under five scenarios.
   - **Adversarial use:** fourteen attempts to break the terminal.
   - **Earlier phases:** their browser checks (Phase 03, 06, 07, 08, 09, 10), rerun on the final tree.
   - **Correctness:** the market-data reconciliation (three times) and the Dossier's accuracy run.
   - **Milo:** the evaluation suite, and a fresh unseen advice set (BUG-132).
   - **Simplicity:** the first-time density of the build the investors saw against this one.
   - **Coverage:** Classic's 26 views; every GET API route.
   - **Engineering:** the checks with their commands; the requirements matrix row by row.
   - **Review:** an independent review of Phase 10's commit.
2. **Problems discovered.**
   - **Advice:** the advice output check caught 14 of 50 unseen advice sentences (BUG-132, reopened, P0).
   - **In Phase 10's own work (BUG-181 to BUG-189 and BUG-192, from the review):**
     - the deploy script's commit check broken (P1);
     - typed text wiped by the Paper Desk's re-mark;
     - one EDGAR 503 failing eleven forms;
     - a budget-refused logo cached a day;
     - a report shown under the wrong conversation;
     - Home's desk note line wrong before its first write;
     - the sign-in state bound to one host;
     - a race in the search memo;
     - a malformed turn raising;
     - a lock race that can fetch one key twice (BUG-192, accepted as WONTFIX: no wrong figure).
   - **Older, found by the audit's checks:**
     - the next report date lost from every company's analysis (BUG-200, P1, live since 2026-10-13), and once back, a
       past report shown as next (BUG-201, P1);
     - the Options readings left loading for good after a failure (BUG-193, P1);
     - owner pages calling a 503 a refusal (BUG-194);
     - the Brokerage scorecard printing JSON (BUG-190);
     - the palette asking a logo for typed text, and logo misses logged as errors (BUG-191, BUG-196);
     - a level change in another tab not reaching the page (BUG-197);
     - offline and refused sentences with the wrong verb (BUG-199);
     - an unknown symbol keeping the Dossier's actions (BUG-198);
     - the Home card's example links wrapping unevenly (BUG-195);
     - the Milo suite's cache price (BUG-180).
   - **Found after the report:** BUG-201's first fix, in the provider, would have taken the week's earlier reports, with
     their results, out of Earnings this week (BUG-202, P1, never live). Found while preparing the hotfix, by tracing the
     provider's other readers; the fix moved to where the next report is read.
3. **Root causes.**
   - **A rule-based classifier measured on its authors' sets:** it does not carry to new phrasings (D-099).
   - **Effects not traced to their readers:** a script reading a health field; a pop-once leg read twice.
   - **A provider's quirk taken as data:** Yahoo keeps a past report in its calendar.
   - **Failure paths that skip one widget:** the Options readings.
   - **Status codes read loosely:** a 503 as a refusal; a 5xx as a dead host.
   - **Cross-tab state:** reached the slider, not the page.
4. **Fixes implemented.**
   - **Server:**
     - commit and uptime public again (D-095);
     - only refusals hold a feed host back (D-096);
     - no-store and 204 for logo misses;
     - the desk note's reasons told apart (D-097);
     - legs readable twice (BUG-200);
     - the first report date not yet past (BUG-201);
     - the search memo keyed to its directory;
     - malformed turns skipped.
   - **v2:**
     - the Paper Desk re-mark waits for the reader;
     - reports keep their conversation;
     - the Options readings stop on a failure;
     - owner pages tell a failure from a refusal;
     - the scorecard's inputs written out;
     - no logo for typed text;
     - a level change in another tab rewords the page;
     - number-neutral failure sentences.
   - **The Milo suite:** prices cache reads at the verified rate.
   - **Not fixed (D-099):** the advice check was not widened again, so set D stays a measure; the remedy is the owner's
     (BL-07, BL-01).
5. **Files changed.**
   - **Server:** `app/main.py`, `app/ai_store.py`, `app/feeds.py`, `app/universe.py`, `app/providers/yf.py`.
   - **v2:** `core/api.js`, `core/prefs.js`, `ui/milo.js`, `ui/palette.js`, `ui/symbols.js`, and the pages brokerage,
     home, options, paper and reports.
   - **Classic:** `static/app.js`.
   - **Tests:**
     - `tests/test_phase11_fixes.py` (new, 13 tests);
     - updated: `test_health_version`, `test_health_refused_key`, `test_desk_freshness`, `test_phase10_hardening`,
       `test_v2_overview_classic_port`, `test_v2_search_rows`;
     - `tests/milo_eval/run.py`.
   - **Docs:**
     - FINAL_REPORT.md;
     - TEST_RESULTS Phase 11;
     - BUG_REGISTER BUG-180 to BUG-201, with BUG-132 reopened;
     - DECISIONS D-095 to D-100;
     - REQUIREMENTS_MATRIX R11, and 25 cells filled across R02 to R06;
     - BLOCKERS BL-01 and BL-07;
     - FEATURE_REGISTRY and COMPLIANCE_REVIEW section 4.2.
6. **Tests executed.**
   - The full suite.
   - The Milo evaluation suite.
   - Set D.
   - The feature check and its rechecks.
   - Home's panel timings.
   - Eight journey runs.
   - The adversarial run, three times over.
   - The reruns of Phase 03, 06, 07, 08, 09 and 10's checks.
   - The accuracy run.
   - The reconciliation, three times.
   - Classic's crawl at two sizes.
   - The API sweep.
   - The density comparison.
   - The syntax, unused-code and secret scans.
7. **Passed / failed.**
   - **Suite:** 8,084 passed, 1 skipped, 0 failed.
   - **Milo suite:** 949 of 949 request-level checks.
   - **Set D:** 14 of 50 caught.
   - **Journey:** the final runs 15 of 15, three times.
   - **Adversarial:** 14 of 14.
   - **Earlier phases' tools:**
     - Phase 03: 27 of 27;
     - Phase 06: 16 of 16;
     - Phase 07: 27 of 28 (C18's isolation held; account B's daily allowance was spent);
     - Phase 08: 3 of 3;
     - Phase 09: A to H;
     - Phase 10's resilience: 12 of 12.
   - **Accuracy:** 10 of 10.
   - **Reconciliation:** the final run 271 PASS, 5 FAIL, 2 UNVERIFIED, all misses conditions.
   - **Classic:** 52 of 52.
   - **API sweep:** no 5xx.
   - **Features:** 91 of 95 passing, 2 partly verified, 1 blocked, 1 not tested.
8. **Browser verification.**
   - **How:** headless Chrome on live data against the local server, with screenshots for every journey step, every
     feature row and the comparison.
   - **What it showed:**
     - the demo journey whole at three sizes, after reloads and with back and forward;
     - every failure condition stated;
     - figures matching the providers and Optic's own data.
9. **Outstanding** (FINAL_REPORT sections 8 and 17):
   - **The P0s:** BUG-132 (the owner's: BL-07, BL-01), and BUG-022 and BUG-023 (the owner's and counsel's: BL-09).
   - **Open P2s:** BUG-173, BUG-187, BUG-195, BUG-198.
   - **Not testable here:** a real model, real providers, real devices, a screen reader, and counsel.
   - **The hotfix:** none left. BUG-200 and BUG-201 went live as `8e2cbf4` on 2026-10-31, on the owner's yes.
10. **Commit and next phase.** Committed on `post-demo-ultra` as `e0dd2ff` (not pushed, not deployed); the commit
    after it records the id. There is no next phase: the decision is the owner's.

## Phase 10 report (directive 10; reporting format of directive 00)

1. **Inspected.**
   - **Performance:** seven routes and six interactions in headless Chrome, at the baseline, after the fixes and in two
     A/B runs against the Phase 09 commit; search and the event loop measured in the server's own process.
   - **Cost and scale:** every paid or rate-limited provider and its call paths (COST_AUDIT.md).
   - **Visual consistency and motion:** 29 routes at four widths (116 checks), Large text on eight routes, reduced
     motion on eight.
   - **Accessibility:** 25 routes at 1440 and 390 against WCAG 2.2 AA checks; the palette, the Milo panel, the level
     slider and focus after an alert edit.
   - **Security:** the fifteen listed areas, read in the code, with nothing run against production or a third party
     (SECURITY_REVIEW.md).
   - **Resilience:** the twelve listed conditions, injected in the browser.
   - **Analytics:** what the terminal records today and could record without new tracking (ANALYTICS_REVIEW.md).
   - **Left from earlier phases:** the register's rows marked 10, and the cache audit's S01, S09, S16 and S19.
2. **Problems discovered.** 28 new rows (BUG-152 to BUG-179), and 31 earlier rows taken up.
   - **Spend:**
     - no Milo ceiling that free accounts could not walk around (BUG-152, High);
     - a page load writing the desk note through a paid call (BUG-032);
     - Classic's catalyst panel writing a paid read when opened (BUG-175);
     - the ledger's price for Sonnet 5.5 cache hits (BUG-176);
     - the first ceiling counting paying readers (BUG-178).
   - **Security:**
     - tokens in logged query strings (BUG-153);
     - no body limit (BUG-154);
     - a pre-account hijack (BUG-155);
     - the data-not-instructions rule not covering tool results and links (BUG-156);
     - the logo proxy (BUG-157);
     - unpinned dependencies (BUG-158);
     - Google's unbound sign-in state (BUG-159);
     - a report-only CSP (BUG-160);
     - fonts without integrity (BUG-161);
     - 500s on a non-ASCII token (BUG-162) and on a line break in an address (BUG-163);
     - passkeys without user verification (BUG-164);
     - sliding sessions and cookie names (BUG-165);
     - Classic's escaping (BUG-166);
     - exception text in answers (BUG-167);
     - addresses in mail logs (BUG-168).
   - **Performance:**
     - layout shift on four routes;
     - search's per-row work on every keystroke (BUG-053);
     - the chat route finding symbols on the event loop (BUG-113);
     - the adapter cache (BUG-169);
     - dead feed hosts (BUG-170);
     - the directory's retries (BUG-171).
   - **Reliability:** an unreadable answer breaking the Dossier (BUG-174), and an order-dependent test (BUG-172).
   - **Accessibility and visual:**
     - an 11.7 px label, and Insiders' tables squeezed on phones (BUG-014);
     - focus lost after an alert edit (BUG-015);
     - 23 px links (BUG-179);
     - Settings' Motion: Reduce not reaching two scrollers (BUG-177);
     - the header growing as a cold quote arrives (BUG-031, BUG-173).
3. **Root causes.**
   - **Limits:** counted per account or per address only, which a new free account or a new address resets.
   - **Reads that wrote:** a page's reads allowed to make paid writes.
   - **Work redone on every request** that can be done once: search's per-row preparation, the screener ranking read
     from disk. It ran on the only event loop.
   - **Caches:** no bound, and failures not remembered (the adapter, feed hosts, the directory).
   - **Framework defaults trusted:** the access log prints the whole target; no body limit; exception text passed
     through.
   - **Sign-in flows written for the happy path:** a state not bound to its browser, an unverified address that could
     be linked, sessions that never ended.
   - **The page frame:** the main region collapsed while a route loaded, and the API client turned an unreadable body
     into null.
4. **Fixes implemented** (D-076 to D-094).
   - **Spend:**
     - a server-wide Milo ceiling, the owner's number, that paying readers and owners do not count against (D-076);
     - the desk note written by the keep-warm job only (D-091);
     - Classic's catalyst panel reads what is kept.
   - **Access:**
     - the client address from the edge (D-078);
     - problem reports for the signed-in owner only (D-079);
     - the body limit and the question length (D-089);
     - per-address limits on search, alert checks and wrong write tokens;
     - the logo proxy limited to listed symbols within a budget.
   - **Sign-in:**
     - Google's and Apple's state bound to the browser;
     - no linking by email to an address with a password;
     - an absolute 90-day session limit (D-082);
     - Permissions-Policy and the opener policy (D-083).
   - **Leaks:**
     - secrets and search text out of the access log;
     - masked addresses in mail logs;
     - exception text scrubbed (D-088);
     - the data-not-instructions rule over everything the model reads, and links showing their host;
     - the reader's own blocks only with questions about them (D-093).
   - **Speed:**
     - search prepared once a directory, with answers kept (D-090);
     - symbols found in a worker thread;
     - the adapter cache swept and capped;
     - failed hosts and directory refreshes remembered;
     - shared Yahoo reads;
     - the main region's height kept while a route loads.
   - **States:**
     - Earnings week's building state;
     - Macro's breadth states;
     - the Dossier's quiet refreshes;
     - an unreadable answer stated as a failure (BUG-174);
     - a cut-off Milo answer kept and marked;
     - brokerage Reconnect;
     - the guest sheet's Close.
   - **Accessibility:**
     - 12 px labels and 24 px links;
     - focus back to the edited alert;
     - dialog roles on the palette and drawers;
     - Motion: Reduce reaching every scroller;
     - phone tables that scroll in their own strips.
   - **Hygiene:** 41 unused imports and 8 leftover locals removed.
5. **Files changed** (106 modified, 5 new).
   - **Server:**
     - `app/main.py`, `app/ai.py`, `app/ai_store.py`, `app/metrics.py`, `app/universe.py`, `app/feeds.py`,
       `app/providers/yf.py`, `app/feedback.py`, `app/billing.py`;
     - `app/auth/` (`routes.py`, `linking.py`, `store.py`, `config.py`, `ratelimit.py`, `mailer.py`);
     - `app/brokerage/` (`snaptrade.py` and three more), `app/valuation/store.py` and four more;
     - `app/public_errors.py` (new);
     - 33 files with unused imports or leftover locals removed (the rest of `app/analytics`, `app/research`,
       `app/desk` and others).
   - **v2:**
     - core: `core/api.js`, `core/device.js`, `core/milo-text.js`, `app.js`;
     - ui: `ui/milo.js`, `ui/sections.js`, `ui/strips.js`;
     - pages: brokerage, dossier, earningsweek, indices, insiders, macro, paper, read, retirement, scan, settings,
       tracker and watchlist;
     - CSS: `components.css`, `pages.css`.
   - **Classic:** `static/app.js`.
   - **Tests:** `tests/test_phase10_hardening.py` (new, 47 tests), and 14 tests updated for the deliberate changes.
   - **Docs:**
     - new: SECURITY_REVIEW.md, COST_AUDIT.md, ANALYTICS_REVIEW.md;
     - DECISIONS D-076 to D-094;
     - BUG_REGISTER BUG-152 to BUG-179, with 31 earlier rows closed;
     - BLOCKERS BL-10 to BL-13;
     - REQUIREMENTS_MATRIX R10;
     - TEST_RESULTS;
     - DATA_PATHWAYS (S01, S09, S16 and S19 fixed);
     - FEATURE_REGISTRY;
     - COMPLIANCE_REVIEW section 10.
6. **Tests executed.**
   - The full suite.
   - The performance runs: a baseline, after the fixes, and two A/B runs against the Phase 09 commit.
   - The search equivalence and timing.
   - The event-loop stall.
   - The accessibility checks, twice.
   - The 116-check visual sweep and its follow-ups.
   - The twelve resilience cases, over three runs.
   - The focus, building, header, blank, cut-off and guest-sheet checks.
   - The unused-code scan.
7. **Passed / failed.**
   - **Suite:** 8,068 passed, 1 skipped, 0 failed. An intermediate run had 8 failures, all fixed (TEST_RESULTS).
   - **Search:** 8,139 of 8,139 pairs identical.
   - **Accessibility:** 0 contrast failures in 9,517 texts, 0 unnamed controls, 0 targets under 24 px after the fix.
   - **Resilience:** 12 of 12 PASS, no uncaught exception.
   - **Sweep:** 116 checks, 91 clean, the 25 flagged each explained or fixed.
   - **The register:** 162 VERIFIED, 3 FIXED, 11 BLOCKED, 1 WONTFIX, 1 OPEN (BUG-173, the owner's call).
8. **Browser verification.**
   - **What ran:** headless Chrome 156 on live delayed data against the local server, with screenshots for the sweep,
     Large text, the header, the focus check and the building state.
   - **What it showed:** no regression in the A/B; layout shift at 0 on Home, Dossier, Compare, Markets and Earnings
     week; every failure condition with a stated recovery; focus and dialogs correct.
9. **Outstanding.**
   - **Escalated to the owner** (BLOCKERS BL-10 to BL-13):
     - the Milo ceiling's number and an outside spend stop;
     - closing the origin to traffic around Cloudflare;
     - downloading a dependency scanner and pinned fonts;
     - the cookie rename, the session-bound CSRF value, passkey verification and the full CSP.
   - **Open:** BUG-173, the header growing at 1440 and 390 as a cold quote arrives.
   - **Not verified:**
     - a screen reader;
     - a real phone;
     - a real model (BL-01);
     - Apple's sign-in live;
     - dependency vulnerabilities.
   - **Phase 11** owes a fresh unseen advice set (BUG-132).
10. **Commit and next phase.** Committed as `3971e7f` on `post-demo-ultra` (not pushed, not deployed); next is
    Phase 11.

## Phase 09 report (directive 09; reporting format of directive 00)

1. **Inspected.**
   - **Pathways:** every financial-data pathway and every cache, from a read-only audit cited to the line
     (DATA_PATHWAYS.md). Eleven of its twenty risks and four of its pathway claims were checked by hand.
   - **The live data:** Optic's figures through its own API, against Yahoo's and the SEC's own responses
     (RECONCILIATION.md).
   - **The session rules:** against NYSE's published calendar.
   - **The workflows:** the eight scenarios, in headless Chrome.
   - **Cross-feature:** the Phase 09 bugs left open by earlier phases (BUG-011, BUG-012, BUG-013, BUG-064,
     BUG-067, BUG-098).
2. **Problems discovered.**
   - **The yield:** worked at another moment's price (BUG-136).
   - **Made-up readings:** the RSI's 50s (BUG-137), and a VWAP with no volume (BUG-138).
   - **The session:** half days and holiday evenings misread (BUG-139).
   - **Stale or wrong statements:** the pattern study's typed-in figures, wrong today (BUG-067), and "delayed about
     15 minutes" beside quotes that state no delay (BUG-098).
   - **Labels and readings:** two models with one company's two numbers unexplained (BUG-011), one score read and
     coloured two ways (BUG-064), a whole's parts not adding up and one change rounded two ways (BUG-012), an
     unlabelled weight basis (BUG-141), a result not yet in the feed read as nothing (BUG-013).
   - **Caches:** reader answers not marked private (BUG-142), six-hour stand-ins unlabelled (BUG-143), refusals kept
     for hours (BUG-144), stale corporate actions (BUG-145), failed pulls kept (BUG-146), deleted holdings kept in
     memory (BUG-147), the browser's refused refresh and memos (BUG-148), Milo not told the data's age (BUG-149),
     the news length (BUG-150).
   - **The carry:** a dividend carry assumed without saying so (BUG-151).
3. **Root causes.**
   - **Precomputed figures:** passed through from the feed at another moment.
   - **Fills:** used in place of a missing value.
   - **Labels by phase:** one label per phase, not per cause.
   - **Copied figures:** ported word for word with the copy.
   - **Rounding:** each surface rounded its own way.
   - **Failures cached as answers:** and stand-ins handed on as current.
   - **Headers:** only the routes that asked for them set any.
4. **Fixes implemented.**
   - **Delay wording** (D-067).
   - **Yield** (D-068).
   - **No reading without its inputs** (D-069).
   - **The session against NYSE's calendar** (D-070).
   - **The pattern study's figures from the study** (D-071).
   - **One score, one reading** (D-072).
   - **One rounding rule per figure** (D-073).
   - **The cache audit's fixes** (D-074).
   - **The reconciliation method** (D-075).
5. **Files changed.**
   - **Server:** `app/providers/yf.py`, `app/analytics/technicals.py`, `indicators.py`, `extras.py`,
     `watchlist.py`, `relperf.py`, `regime.py`, `sectors.py`, `watches.py`, `app/session.py`, `app/main.py`,
     `app/ai.py`, `app/milo_tools.py`, `app/milo_data.py`, `app/research/service.py`, `app/brokerage/service.py`.
   - **v2:** `core/api.js`, `core/format.js`, `core/marketTime.js`, `core/status.js`, `ui/finfigs.js`,
     `ui/milo.js`, and the pages alerts, brokerage, compare, dcf, dossier, dossier-frame, earningsweek, investing,
     options-panels, overview-research, paper, retirement, settings, sheet and workspace.
   - **Classic:** `static/app.js`.
   - **Tests:** `tests/test_market_data_integrity.py` (new), `tests/fixtures/pattern_base_rates_2026-10-29.json`
     (new), and eight tests updated for the deliberate changes.
   - **Docs:** DATA_PATHWAYS.md and RECONCILIATION.md (new); DECISIONS D-067 to D-075; BUG_REGISTER BUG-136 to
     BUG-151, with BUG-011, BUG-012, BUG-013, BUG-064, BUG-067 and BUG-098 closed; REQUIREMENTS_MATRIX R09;
     TEST_RESULTS; FEATURE_REGISTRY; COMPLIANCE_REVIEW section 9.
6. **Tests executed.**
   - The full suite.
   - The reconciliation (twice in full on the final tree, after the first run's fixes).
   - Scenarios A to H.
   - The session tests against NYSE's calendar.
   - The new integrity tests.
7. **Passed / failed.**
   - **Suite:** 8,015 passed, 1 skipped, 0 failed (`phase09/pytest-full-2.txt`).
   - **Reconciliation:** 278 rows, 277 PASS, 1 UNVERIFIED (the first run's 9 failures: 6 the reference's definitions, 3 Optic's yield).
   - **Scenarios:** A to H all PASS, no script exceptions.
8. **Browser verification.**
   - **What ran:** headless Chrome on live delayed data, as scenarios A to H, with screenshots in
     `phase09/scenarios/shots`.
   - **What it showed:** one SPY price across four surfaces; NVDA everywhere after a late AAPL answer; stated missing
     and failure states with no invented figure; recovery from a reload mid-load; cached freshness labels; two
     readers isolated; and brokerage weights that recompute.
9. **Outstanding.**
   - **Phase 10:** the cache audit's S01, S09, S16 and S19 (an unbounded adapter cache, duplicate Yahoo fetches, no
     negative cache for feeds, the symbol directory's lock), plus BUG-112 and BUG-113.
   - **Not observable at the run's hour:** a pre-market price, and a regular session observed live (R09-02, R09-03
     PARTIAL).
   - **Not reconciled:** news timestamps, reported EPS and margins, and currency conversion (R09-02).
   - **For counsel:** the legal page's delay sentence (COMPLIANCE_REVIEW section 9).
10. **Commit and next phase.** Committed as `17024f0` on `post-demo-ultra` (not pushed, not deployed); next is Phase 10.

## Phase 08 report (directive 08; reporting format of directive 00)

1. **Inspected.**
   - **Tools and context:** every tool Milo can call and every source the server loads into CONTEXT, with a read-only
     audit cited to the line (MILO_TOOLS.md).
   - **Prompt and policy:** the grounding rules in the system prompt, and the advice policy's request classifier and
     output check.
   - **Prior work:** the milo-upgrade branch's tools, freshness block and evaluation harness (D-006 input).
   - **Live timing:** the chat route's own timing for definitions and for other questions.
2. **Problems discovered.**
   - **The wrong company's evidence:** it followed the page's ticker, not the one named (BUG-114).
   - **Quote times were fetch times,** and index symbols were refused (BUG-115, BUG-116).
   - **Unreachable data:** no price history, filings, reported results or name lookup, though Optic reads all four
     (BUG-117).
   - **Definitions waited** 0.5 to 5.9 s for data they do not use (BUG-118).
   - **Five advisory requests went unclassified** (BUG-119).
   - **The news tool lost Optic's scores** (BUG-120).
   - **Yesterday's market brief could arrive unflagged** (BUG-121).
   - **Lists were cut silently** (BUG-122).
   - **Unknown symbols read as failed sources** (BUG-123).
   - **A tool promised fields it never returns** (BUG-124).
   - **A failed accounts lookup read as "not signed in"** (BUG-125).
   - **The unknown-symbol note was dropped first** (BUG-126).
   - **An uncapped list** (BUG-127).
   - **A judgement was held back as an instruction** (BUG-092).
   - **Found by the stand-in's answers:** Milo's own sentences held back as advice (BUG-128, BUG-133); figures loaded
     for the question had no source tag, so they were tagged as the page's quote (BUG-129); fixture defects (BUG-130);
     answer checks that failed honest answers (BUG-131, BUG-135); definitions at the two simplest levels running past
     the prompt's length (BUG-134).
   - **Found by an unseen set (C):** the advice output check caught 28 of 50 advice sentences nobody had tuned it for,
     the same before and after this phase's first changes (BUG-132).
3. **Root causes.**
   - **Precedence:** the page's ticker took precedence over the question.
   - **Times:** compactors copied the fetch time and fixed text.
   - **Missing tools:** none existed for what the pages read.
   - **Context:** every question gathered the full context.
   - **Patterns:** they did not cover the phrasings.
   - **Key names:** they drifted between the news module and its compactor.
   - **Copies and cuts:** `_market_block` copied levels only, and `trim` kept no record of its cuts.
   - **Errors:** a 404 was caught as a generic exception, a description outgrew its result, and a failed lookup set the
     user to none.
   - **Budget order:** a section had no place in it.
   - **Written before any answer existed:** the output check's shapes, the format prompt's source keys, the fixtures'
     typed-in numbers and the answer checks.
   - **Two rules that pulled apart:** the simplest levels ask for every term defined and every point explained, and
     nothing said the narrow-question length holds at every level.
4. **Fixes implemented.**
   - **Evidence follows the named symbol** (D-050).
   - **A freshness block on every result, and quotes with the trade's own time** (D-051).
   - **Four data tools** (D-052).
   - **Definitions fetch nothing** (D-053).
   - **The audit's grounding fixes** (D-054).
   - **The evaluation suite** (D-055).
   - **The classifier's patterns** (D-056).
   - **The narrowed lean rule** (D-057).
   - **The grounding classes mapped and answers read through a stand-in** (D-058).
   - **Two exemptions in the output check and a timing rule** (D-059).
   - **`auto_loaded` as a source key** (D-060).
   - **The stand-in in rounds, with a corrected check kept apart from a measure** (D-061).
   - **A price history cut to its window** (D-062).
   - **Repetition and the prompt's format checked on every answer** (D-063).
   - **The advice output check widened from set C, with four exemptions** (D-064).
   - **The definition length at every level** (D-065).
   - **Round 2's check corrections, kept apart from the score as first scored** (D-066).
5. **Files changed.**
   - **Server:** `app/milo_tools.py`, `app/milo_data.py` (new, from milo-upgrade), `app/main.py`, `app/ai.py`,
     `app/ai_policy.py`.
   - **Front ends:** the `auto_loaded` source in `static/v2/js/core/milo-text.js` and `static/app.js`.
   - **Tests:** `tests/milo_eval/` (new: fixtures, harness, cases, checks, answer checks, runner),
     `tests/test_milo_eval.py`, `tests/test_milo_grounding.py`, `tests/test_milo_data_tools.py` (from milo-upgrade,
     adapted to the portfolio privacy rule), `tests/test_milo_tools.py` (tool count), `tests/test_pulse_sources.py`
     (the new key), `tests/test_milo_take_chart.py` (the citable keys), `tests/test_ai_policy.py` and
     `tests/fixtures/advice_set_c_2026-10-29.json` (set C as a regression set) and `tests/conftest.py` (the two markers).
   - **Docs:** MILO_TOOLS.md (new), DECISIONS D-050 to D-066, BUG_REGISTER BUG-114 to BUG-135 and BUG-092,
     REQUIREMENTS_MATRIX, TEST_RESULTS, FEATURE_REGISTRY.
6. **Tests executed.**
   - The full suite.
   - The evaluation suite: 137 cases and 949 request-level checks.
   - The grounding tests and the data tools' tests.
   - End-to-end checks E01 to E03 on live data.
   - Server timing for definitions.
   - The output check against regression sets A and B.
   - The stand-in's answers in three rounds: sixteen; twenty-four from a fresh agent after the fixes; ten definitions
     after the length rule.
   - The output check on unseen set C, then on sets A, B and C, 1,506 sentences of Optic's own research text and 433 of
     the stand-in's (`tools/phase08_advice_regression.py`).
7. **Passed / failed.**
   - **Suite:** 7,970 passed, 1 skipped, 0 failed.
   - **Evaluation suite:** 949 of 949 request-level checks; all 18 categories.
   - **E01 to E03:** 3 of 3.
   - **Stand-in answers** (a proxy, not the production model, BL-01):
     - Round 1: 5 of 16 as first scored, 12 of 16 re-scored with no answer changed.
     - Round 2, after the fixes: 18 of 24 as first scored, 21 re-scored (257 of 261 checks; routing 24 of 24).
     - Round 3, ten definitions after D-065: all within the length; 4 of 10 as first scored, 10 re-scored.
   - **Advice output check on unseen set C:** 28 of 50 advice sentences caught, 1 of 50 research held back; then
     widened (50 of 50 and 0 of 50 as a regression set), with no unseen measure until Phase 11.
8. **Browser verification.**
   - **What ran:** headless Chrome against the local server on live delayed data, with the stand-in asking for the new
     price-history tool and for a quote.
   - **What it showed:** the activity line, the sources fold with both times, and the figures, which match Optic's own
     daily bars. Rerun on the final tree (2026-10-30, 1:20 AM ET): 3 of 3 again, the quote observed at 4 pm and
     retrieved at 1:20 am.
9. **Outstanding.**
   - **Blocked (BL-01):** the production model's own answers, routing and latency. The suite's answer checks and
     `tests/milo_eval/run_model.py` are ready for the first run with a working key.
   - **Phase 11:** an unseen set for the widened advice check (BUG-132 stays FIXED until then).
   - **Phase 10:** BUG-112 and BUG-113.
   - **Phase 09:** BUG-098.
   - **For the owner:** the documented limits that stay (MILO_TOOLS.md), and the milo-upgrade guide and playbooks, which
     were not taken.
10. **Commit and next phase.** Committed as `ab5a2ae` on `post-demo-ultra` (not pushed, not deployed); next is Phase 09.

## Phase 07 report (directive 07; reporting format of directive 00)

1. **Inspected.** Milo's whole path from Send to the last word, the fourteen stages of directive 07 (STREAMING_PIPELINE.md): the
   panel's submit, request and stream reader, the chat route and its checks, the context, the tool loop, the model call, the
   advice gate, the transport, the drawing, the scrolling and the finish. Also New conversation, Close, history and delete; the
   composer; the knowledge level; Classic's handling of the same stream. Measured on the code before (`1652e14`, its own
   worktree and data on :8252) and after, in headless Chrome, against the stand-in model.
2. **Problems discovered.**
   - **Drawing:** every frame rebuilt the whole answer, each finished paragraph 15 times at the median and a chart 16
     times (BUG-107). The arriving paragraph was raw markdown (BUG-108).
   - **Waiting:** the response began only once the context was gathered: nothing for 102 ms, 318 ms uncached (BUG-106).
     The activity line was not true to what was happening (BUG-105).
   - **Scrolling:** a reader at the end was left 52 to 163 px behind (BUG-100); a 40 px scroll up was pulled back
     (BUG-101); the panel reopened at the top (BUG-099).
   - **History and delete:** history was redrawn every frame while Milo answered (BUG-102), and a conversation deleted
     mid-answer came back (BUG-103).
   - **New conversation:** a silent disabled button while Milo answered (BUG-104).
   - **Composer:** the 4,000-character cut was silent (BUG-109); a pasted image was ignored (BUG-110).
   - **Phones:** 36 px of conversation on a 375 by 549 phone (BUG-111).
   - **For Phase 10:** no server-side question length (BUG-112); synchronous work in the chat context holds the event loop
     (BUG-113).
3. **Root causes.** `paintLive` set the whole answer's HTML each frame and its tail as text. The route built the context
   before returning the stream. Following the end was guessed with a 120 px allowance after each frame's changes, and
   nothing restored or re-pinned the view. The answer's end saved the conversation on screen whatever the list said. The
   short-screen rules started at 520 px.
4. **Fixes implemented.**
   - **The gate's cadence:** kept, with the trade-off recorded (D-042).
   - **The route:** starts at once, says each step and times every answer (D-043).
   - **The drawing:** the finished part drawn once, where pieces equal the whole; the arriving paragraph as markdown; the
     chart once; the finish in place (D-044).
   - **Following the end:** the reader's choice; the place restored on reopening (D-045).
   - **While Milo answers:** New conversation and history wait and say why; Close leaves the answer running; delete guarded
     (D-046).
   - **History:** local-only, per account, documented, with the server design it would need (D-047).
   - **Small phones:** room for the conversation (D-048). **The composer:** the limit said, pasted images attached (D-049).
   - **Classic:** its step list skips the two new server steps and reads as before.
5. **Files changed.**
   - **Server:** `app/ai.py` (`StreamClock`, the `writing` step, tool timing), `app/main.py` (the chat route, `_chat_context`).
   - **v2:** `static/v2/js/ui/milo.js`, `static/v2/js/core/milo-text.js` (`settledEnd`, `streamingHTML`, `seen`),
     `static/v2/css/components.css`.
   - **Classic:** `static/app.js` (one branch).
   - **Tests:** `tests/test_v2_milo_streaming.py` (new, 11); `test_v2_milo_redesign.py`, `test_v2_milo_scout.py` and
     `test_spend_guard.py` (its model stub is now async, as the real one is) updated.
   - **Docs:** STREAMING_PIPELINE.md (new), DECISIONS D-042 to D-049, BUG_REGISTER BUG-099 to BUG-113, REQUIREMENTS_MATRIX,
     TEST_RESULTS, FEATURE_REGISTRY.
6. **Tests executed.**
   - The full suite.
   - The new streaming tests: parity a character at a time over four answers, the settle rules, the tail, the panel's
     rules, the route's first step and error, the timing, Unicode, Classic.
   - The 28 browser checks (`tools/phase07_checks.py`) on the code before and after.
   - The latency and rendering measurement (`tools/phase07_measure.py`): five answers each, three with a chart, one
     uncached.
   - Raw-socket timing of the stream on both servers.
   - A scroll-nudge probe, Classic's step list on both servers, and the phone layout measured at 375 by 549.
7. **Passed / failed.**
   - **Suite:** 7558 passed, 1 skipped, 0 failed (`phase07/pytest-full.txt`).
   - **Browser checks:** 28 of 28 after; 20 of 28 before (C08, C12, C15a, C15b, C17, C21, C23, C25 failed).
   - **Requirements:** R07-02 to R07-11 PASS. R07-01 PARTIAL: Optic's stages are measured, and the real model's own times
     are BLOCKED (BL-01).
   - **Measured:**
     - The first line now reaches the reader at 24 ms, not 109.
     - Each finished paragraph is drawn twice in all (was 15 at the median), and a chart once (was 16).
     - Frame work p95 is 1.7 ms (was 2.6), with no long tasks.
     - Input delay stays at most 3 ms.
     - The first text, at about 840 ms, is set by the emulated model and the gate's first sentence, unchanged.
8. **Browser verification.** Headless Chrome at 1440 by 900, 390 by 844 and 375 by 549, with screenshots looked at.
   - The phone screenshot showed BUG-111, which the checks had passed.
   - The first after run failed C03, because the incremental drawing split a list from its lead-in, and three checks on the
     end distance (BUG-100). Both were fixed before this report.
   - Reading Classic's handler showed it would have listed "Gathering" and "Writing" as steps. It now skips them, and its
     list is the same as before on both servers.
9. **Outstanding.**
   - **Phase 10:** BUG-112 (the server-side question length) and BUG-113 (the event loop).
   - **Phase 08:** BUG-092.
   - **Phase 09:** BUG-098.
   - **For the owner:** whether to fold the tool row or header on small phones (D-048), and whether server-side history is
     wanted (D-047).
   - **Blocked:** the real model's latency (BL-01). Every answer now logs its timing for when one runs.
10. **Commit and next phase.** `874c109`; next is Phase 08.

## Phase 06 report (directive 06; reporting format of directive 00)

1. **Inspected.** The Overview's whole pipeline (DOSSIER_PIPELINE.md): the router and search, the eleven payloads and the header's price refresh, the client caches, the fixed-rule readings of `overview-research.js`, the loading and error paths, the redraws and the section helpers, the density state behind "Show advanced analysis", and the sources each section names. The payloads of five kinds of symbol (a company, a loss-maker, a fund, a coin, an index).
2. **Problems discovered.**
   - **The switch:** it opened two folds under the simple content instead of replacing it, and its label never changed (BUG-001).
   - **Reading load:** the default view held 1,409 visible words in 12 cards (BUG-004).
   - **The answer guard:** answers were checked by symbol only, so a late answer from an earlier visit to the same ticker could be drawn (BUG-095).
   - **Try again:** it wired the page's handlers a second time, so the switch then cancelled itself (BUG-094).
   - **Focus:** a search opened as a page arrived lost focus to the page's heading, and the Overview's redraw then dropped focus to the body (BUG-093, BUG-097).
   - **The day's move:** the header's 20-second price refresh would have left the new Simple Analysis saying an older move (BUG-096).
   - **Data:** SPY's quote states no delay while the data caveat says 15 minutes (BUG-098, for Phase 09).
3. **Root causes.** The switch was a density control that opened folds; the research was one long page with a fold at the end; requests had no identity beyond the symbol; `wire()` ran on every render; the shell's arrival focus did not know about the search.
4. **Fixes implemented.**
   - **One analysis area:** it shows the Simple Analysis or the Advanced Analysis, swapped by the density setting, the one state (D-035).
   - **The Simple Analysis:** three answers by fixed rules in five registers, with the same figures and every caveat at every level (D-036).
   - **The Advanced Analysis:** Classic's research word for word, in twelve separate sections with the duplicates merged (D-037).
   - **The swap:** a 150 ms fade, the reader's place kept, focus kept, said to a screen reader (D-038).
   - **The visit token** for every answer; handlers wired once (D-039).
   - **The Simple Analysis follows the header's price** (D-040).
   - **The arrival focus** waits for the search, and the heading keeps focus through redraws (D-041).
5. **Files changed.**
   - **Pages:** `static/v2/js/pages/overview-simple.js` (new), `pages/dossier.js`, `pages/dossier-frame.js`, `pages/overview-research.js`.
   - **Shell and styles:** `app.js`, `css/pages.css`.
   - **Tests:** `tests/test_v2_dossier_analysis.py` (new); `test_v2_overview_classic_port.py`, `test_v2_parity_b6a.py` and `test_pitch_audit_2026_10_22.py` updated.
   - **Docs:** DOSSIER_PIPELINE.md (new), DECISIONS D-035 to D-041, BUG_REGISTER, REQUIREMENTS_MATRIX, TEST_RESULTS, FEATURE_REGISTRY, SIMPLICITY_AUDIT.
6. **Tests executed.**
   - The full suite.
   - Phase 06's 12 unit tests.
   - Sixteen browser checks (D1 to D16), with requests failed or held in the browser.
   - The accuracy run on ten symbols.
   - Phase 03's 27 search scenarios, and a 60-search loop with focus logged.
   - The Phase 04 density tool on the Overview.
   - Five symbols' simple analyses read at several levels.
7. **Passed / failed.** Suite 7547 passed, 1 skipped, 0 failed. Browser checks 16 of 16. Accuracy 10 of 10. Search scenarios 27 of 27 after BUG-093's fix (26 of 27 before). R06-01 to R06-09 PASS, and R05-05 now PASS.
8. **Browser verification.** Headless Chrome for every check, at 1440, 390 and 375 by 549, with screenshots of both views looked at. The first reads found:
   - D4: the simple view landed 49 px low after a swap.
   - Four wording faults.
   - BUG-093, BUG-096 and BUG-097.
   All are fixed (TEST_RESULTS, Phase 06).
9. **Outstanding.**
   - **Phase 09:** BUG-098, a delay stated two ways by the data.
   - **Phase 08:** BUG-092, the advice check's "I'd lean toward" pattern.
   - **Blocked:** the production model's answers (BL-01); nothing on the Overview needs them.
10. **Commit and next phase.** `0448900`; next is Phase 07.

## Phase 05 report (directive 05; reporting format of directive 00)

1. **Inspected.** Classic's homepage question and its history (`app.js` `knowledgeOnboardingHTML`, 41eec2f; `components/knowledge.js`, 194bb3d) and v2's removal of it (22b2cc7). The three homes of the level (`app/knowledge.py`, Classic's component, v2's `core/prefs.js`), Milo's own Level select, the settings architecture (`/api/auth/preferences`, `user_preferences`). Every model call (`app/ai.py`: Milo, deep research, the portfolio briefing, and eight shared writers) and every place their texts show. The glossary marking on rule-written text, the Chart page's readings and Learn panel. Both apps' Brokerage briefing and Classic's account and research requests.
2. **Problems discovered.** v2 no longer asked the question, and the old labels described explanations rather than readers. Milo kept its own level control. The level lived only in the browser, so it did not follow a signed-in reader, and Classic's changes would have been undone by v2. Deep research and the briefing ignored the level (Classic's deep research too). Nothing let a reader re-explain a shared text at their level. Rule-written text explained terms the same way at every level, and eight chart studies had no definitions at all. During the work, the briefing's level line was missing on the first paint, and Classic misdescribed a write-up for the same figures at another level (BUG-083 to BUG-091).
3. **Root causes.** The ladder predated the directive's five levels and carried an Adaptive mode. The preference had no account column. Per-reader writers took no level argument. Shared texts were written once with no path to another register. The glossary covered the terms Optic had needed so far, not the studies.
4. **Fixes implemented.**
   - **The levels:** five, with the directive's names and styles, written once with one invariant (D-026). Adaptive is retired (D-027).
   - **One preference with one account rule,** in both apps (D-028).
   - **One slider:** a native range input with the level named and an illustration. It sits in Home's first-visit card, Settings and Milo (D-031).
   - **Per-reader writers take the level:** Milo, deep research and the briefing (both apps); the briefing is kept per level and says which level it was worded for.
   - **Shared texts** offer "Explain it for X" as a Milo draft. Milo's history keeps each answer's level (D-029).
   - **Rule-written text** follows the glossary policy (D-030), and the chart studies are defined in the server's words (D-032).
   - **The Privacy text** names the stored level (D-033).
5. **Files changed.** `app/knowledge.py`, `app/ai.py`, `app/main.py`, `app/db.py` (migration 19), `app/auth/store.py`, `app/brokerage/workspace_routes.py`; v2 `core/prefs.js`, `core/store.js`, `core/glossary.js`, `ui/levelslider.js` (new), `ui/milo.js`, `ui/states.js`, `ui/glossmark.js`, `pages/settings.js`, `pages/workspace.js`, `pages/home.js`, `pages/brokerage.js`, `pages/chart-widgets.js`, `pages/legalpages.js`, `app.js`, `css/components.css`, `css/pages.css`; Classic `components/knowledge.js`, `app.js`, `brokerage.js`; tests `test_knowledge_level_apply.py` and `test_v2_knowledge_level.py` (new), `test_knowledge_modes.py`, `test_milo_reasoning.py`, `test_brokerage_workspace.py`, `test_brokerage.py`, `test_pulse_tone.py`, `test_ui_mode.py`, `test_v2_beginner.py`, `test_v2_density.py`, `test_v2_milo_personas.py`; docs DECISIONS D-026 to D-034, BUG_REGISTER BUG-083 to BUG-092, REQUIREMENTS_MATRIX, TEST_RESULTS, COMPLIANCE_REVIEW section 8, BLOCKERS, FEATURE_REGISTRY.
6. **Tests executed.** The full suite on the final tree. Phase 05's 25 new tests and the updated ones. Twenty-one browser checks in headless Chrome (L1 to L17, the Brokerage line in both apps, Classic's deep research, Home's Desk, a failed save), with screenshots. The five-level proxy run (D-034).
7. **Passed / failed.** Suite 7529 passed, 1 skipped, 0 failed. Browser checks 21 of 21. The proxy run: the five answers keep the same figures, caveats and sources and differ in vocabulary and depth; Optic's advice check found nothing in four and one false positive at Advanced (BUG-092). R05-01 to R05-04, R05-06 and R05-07 PASS. R05-05 PARTIAL: the Dossier's rule-written analysis reads alike from Beginner to Advanced until Phase 06's Simple Analysis. R05-08 PARTIAL: the production model's own answers are blocked (BL-01).
8. **Browser verification.** Headless Chrome for every check above, on the local server with the stand-in model, as a guest and signed in, in both apps. The screenshots of the slider at five sizes, the terms at three levels, the Desk, the Chart, the Learn panel and both Brokerage pages were looked at; they showed the two layout problems listed in TEST_RESULTS (BUG-083, BUG-088), both fixed.
9. **Outstanding.**
   - **Phase 06 by the directives' design:** level-specific wording for the Dossier's Simple Analysis (directive 06 section 2), which moves R05-05 to PASS.
   - **Blocked:** the production model's answers at each level (BL-01).
   - **For the owner:** whether the Privacy addition moves EFFECTIVE or needs an announcement (D-033).
10. **Commit and next phase.** `e64a5ee`; next is Phase 06.

## Phase 04 report (directive 04; reporting format of directive 00)

1. **Inspected.** Every primary route (29) and the secondary ones a guest can open (13), measured before (`2f6a548`, its own worktree and data on :8252) and after, at 1440 and 390, and after at 1024 and 768 as well. Every Home panel and layout; the density and knowledge-level code in `core/prefs.js`, `ui/sections.js`, Settings and the Dossier switch; every page's time and source lines; the registry's simplicity findings (B: H-2, H-4, X-2, X-3, X-6, X-7, X-10; Phase 01 V-01 to V-11); Phase 01's dead-click reports.
2. **Problems discovered.** Home opened twelve equal panels (186 controls, 1,872 visible words at 1440) with the market score, the expected move ratios and a saturated heatmap on its first screen. Analysts drew a week's actions at once (14,629 px). One switch set both density and Milo's language (BUG-002). "Regime" named three different models. Five pages showed no time, and the Desk's footer gave the page's time as the note's. Read repeated one sentence on 20 rows. The Overview's lead line carried method and policy ids, and the liquidity words named the spread when the grade weighs more. Presses on Compare's chips, "Update panels" and the chart watchlist's empty Add did nothing. Home had two sets of Follow buttons, and an unrouted second Home page had been edited as if it were live. Folded tables sat in full on Explore and Retirement. The measuring tools counted folded content as visible (D-022).
3. **Root causes.** Density rode on the knowledge level. Home's layouts opened every panel. Each page wrote its own time line, or none. Names grew per page. Colour was chosen by sign alone. Handlers returned without saying anything. Dead code was kept for its exports.
4. **Fixes implemented.** Density is its own setting (D-019), and Home has Simple panel sets (D-020). Analysts shows the newest 40, then Show all. Explore's catalogue and Retirement's two reference tables fold in Simple, through the shared `simpleFold`. A shared `asOfLine` and `whenText` put a time on Macro, Indices, Explore, Instrument and Compare; Indices names the last finished week. The Desk says Written or Compiled with its own time. One name per model and one label set for the expected move. The heatmap tint is capped on a fixed scale and rating words are ink. Each silent press now says why. One set of Follow buttons. The unrouted page and the undrawn handlers are removed (D-021). The report sentence is said once, the ids are folded, the liquidity words are Liquid, Fair and Thin with the spread named, and the arrows are icons. WRITING_GUIDELINES.md and SIMPLICITY_AUDIT.md were written.
5. **Files changed.** `static/v2/js/core/prefs.js`, `ui/sections.js`, `ui/states.js`, `ui/table.js`, `pages/workspace.js`, `pages/home.js`, `pages/settings.js`, `pages/dossier.js`, `pages/dossier-frame.js`, `pages/analysts.js`, `pages/compare.js`, `pages/chart-widgets.js`, `pages/explore.js`, `pages/retirement.js`, `pages/indices.js`, `pages/instrument.js`, `pages/macro.js`, `pages/market-shared.js`, `pages/read.js`, `pages/options.js`, `pages/overview-research.js`, `css/pages.css`; `app/main.py`, `app/analytics/liquidity.py`, `app/analytics/macro.py`, `app/analytics/contract_picker.py` (a comment); tests `test_v2_density.py`, `test_v2_simplicity.py` (new), `test_v2_workspace_state.py`, `test_v2_ticker_state.py`, `test_v2_beginner.py`, `test_v2_parity_b3.py`, `test_pitch_audit_2026_10_22.py`; docs SIMPLICITY_AUDIT.md, WRITING_GUIDELINES.md (new), DECISIONS D-019 to D-025, BUG_REGISTER, REQUIREMENTS_MATRIX, TEST_RESULTS, FEATURE_REGISTRY.
6. **Tests executed.** The full suite once on the final tree. Phase 04's new tests (`test_v2_density.py`, `test_v2_simplicity.py`, the design-standard test). Density measurements of the 29 primary routes, before at 1440 and 390 and after at all four sizes, and of the 13 secondary routes. Dead-click runs: guest at 1440 and 390, signed in at 1440. Phase 03's 27 scenarios again. Browser checks of the first-visit card, the fold memory, the time lines, the phone menus and contrast in both themes (TEST_RESULTS, Phase 04).
7. **Passed / failed.** Suite 7506 passed, 1 skipped, 0 failed. Dead controls 0, with 898 presses answered. Scenarios 27 of 27. Overflow and overlapping text 0 at every size. R04-01 to R04-12 PASS, with R04-09's spacing literals handed to Phase 10 (D-025).
8. **Browser verification.** Headless Chrome for every measurement, dead-click run and scenario; the browser pane for the first-visit card, the fold memory, the time lines, the Overview's icons and the API words. Before and after sheets at 1440 and 390 and after-only sheets at 1024 and 768 were looked at; they showed the two problems listed in TEST_RESULTS, both fixed.
9. **Outstanding.** None in Phase 04's scope. Handed on by the phase plan: the Dossier tabs' reading load (BUG-004) to Phase 06; spacing literals and headline sizes to Phase 10 (D-025). For the owner: the navigation names proposed in SIMPLICITY_AUDIT.md section 5, and the two long ported method sentences on the Overview (section 6).
10. **Commit and next phase.** `381a018`; next is Phase 05.

## Phase 03 report (directive 03; reporting format of directive 00)

1. **Inspected.** Every search box in v2 (the palette, the typeahead and the 16 boxes in FEATURE_REGISTRY A14), the resolver logic in each, the API client's cache, Home's linked-ticker state and the "Follows" chip with everything that reads them, the router and shell, and every Dossier tab's loads for identity checks after an await.
2. **Problems discovered.** "Follows <ticker>" came from Home falling back to the watchlist or the last company opened and then saving it (BUG-003). The palette's places fell back to the Recent list; Enter on an empty box opened the first row; a failed search was cached for 5 minutes and let a page that only shared letters take Enter from a typed ticker; Home and the Dossier start opened indices as company Dossiers and could navigate after the reader had left; Home's box did nothing when it found nothing; three symbol boxes had no suggestions; the printable sheet and the Chart's intraday levels could take a previous company's late answer; Home, Macro, Indices and Read let an earlier answer win; Skip to content opened the ticker MAIN; Home's sector-board link opened the ticker MARKET.
3. **Root causes.** No single rule for "which symbol" (D-016); each box with its own resolver; module-level state written after an await without checking it was still the same render.
4. **Fixes implemented.** `store.DEFAULT_SYMBOL` and one precedence; the chip and fallback removed, a chosen ticker kept (`linkChosen`); `core/resolve.js` for typed text with a navigation ticket; palette fixes (this visit or SPY, nothing chosen until the reader moves, honest `aria-expanded`, the stale-list note, saved questions without a reload, word-start page matching, a typed symbol keeps Enter when search is down, This week's earnings); suggestions and room for names on the symbol boxes; identity guards on the sheet, Chart, Home, Macro, Indices and Read; the skip link and the Macro link.
5. **Files changed.** `static/v2/js/core/resolve.js` (new), `core/api.js`, `core/store.js`, `core/homelink.js`, `core/research.js`, `ui/palette.js`, `ui/typeahead.js`, `app.js`, `pages/workspace.js`, `pages/home.js`, `pages/dossierstart.js`, `pages/sheet.js`, `pages/chart.js`, `pages/macro.js`, `pages/indices.js`, `pages/read.js`, `pages/paper.js`, `pages/alerts.js`, `pages/watchlist.js`, `pages/chart-widgets.js`, `pages/insiders.js`, `css/pages.css`; tests `tests/test_v2_ticker_state.py` (new), `test_v2_phase2.py`, `test_v2_workspace_state.py`.
6. **Tests executed.** Full suite twice; the design-standard and checklist tests; 27 interaction scenarios in headless Chrome (TEST_RESULTS, Phase 03); screenshots of Home's quote panel at 1440 and 390.
7. **Passed / failed.** Suite 7486 passed, 1 skipped, 0 failed. Scenarios 27 of 27 (run 1 found two real faults, fixed). R03-01 to R03-11 PASS.
8. **Browser verification.** Headless Chrome for every scenario; the browser pane for the palette's rows under each typed word, the search queueing measurement and Home at 375 px. The pane's partly drawn chart was its stalled draw-in animation; headless Chrome draws it in full.
9. **Outstanding.** None in Phase 03's scope. Noted for later phases: locally a search typed during a cold Dossier load waits for a free connection (HTTP/1.1; production is HTTP/2); `/api/search` re-reads the ranking file on each request and is unmetered (R-S-2, Phase 10).
10. **Commit and next phase.** `7b14b56`; next is Phase 04.

## Phase 02 report (directive 02; reporting format of directive 00)

1. **Inspected.** Every model prompt in `app/ai.py` and `app/research/milo.py`; the three model entry points and the ten writers; every rule-written research generator the Phase 01 registry and the advice scan pointed to (352 hits at baseline, triaged line by line); the v2 and Classic pages that show them; alerts, account and alert emails, onboarding, upgrade copy; the Terms, Privacy policy, full disclaimer, page notices, AI labels, brokerage consent, data-source and delay statements.
2. **Problems discovered.** 24 advisory-risk pathways (COMPLIANCE_REVIEW section 1) and 13 disclosure findings (section 7). New in this phase beyond Phase 01's rows: per-fund dollars of the reader's contribution still on Retirement; the public "New trade idea" alerts; persuasive option rationales ("a price you already like"); Classic's options panel ("never pay above", "Exit if the stock closes past this"); Milo's options chips ("a swing long here"); the "1% or less" checklist rule; the unsupported "most likely to break out"; the linked-scan spend (BUG-036); and the measured weakness of a phrase-by-phrase output check (5 of 15, then 10 of 40 on unseen sentences).
3. **Root causes.** No shared policy; nothing read a model's answer first; rule-written research in trade-plan words with internal labels shown raw; owner formats that predate the directive; two copies of every disclosure; two front ends (COMPLIANCE_REVIEW section 2).
4. **Fixes implemented.** `app/ai_policy.py`: a ten-rule policy on every model call (three entry points, enforced by a syntax-tree test), a request classifier with the server's own line and a turn instruction, a sentence-level output check rebuilt twice on measured misses, JSON-aware cleaning for writers, a one-sentence stream gate and an end-of-stream amend with a note the reader sees and keeps. Prompts reworded. Every rule-written pathway reworded or withheld in v2 and, where it instructed, Classic. One disclosure registry with a tested v2 copy and notices on 20 views. Paper-book alerts said as simulated. Linked scans run only after a press.
5. **Files changed.** Listed in COMPLIANCE_REVIEW 3.3; new: `app/ai_policy.py`, `app/research/words.py`, `static/v2/js/core/research-words.js`, `tests/test_ai_policy.py`, `tests/test_legal_registry.py`, `tests/test_scan_link_consent.py`, `tests/fixtures/advice_set_a_2026-10-29.json`, `docs/post-demo-ultra/COMPLIANCE_REVIEW.md`.
6. **Tests executed.** Full suite six times (TEST_RESULTS, Phase 02); 240 new tests in three new files; 22 existing test files updated to the new wording; five mutation checks; `node --check` on 26 changed files; compileall; chat-route probes with the stand-in model; the Milo panel in headless Chrome; the 56-route crawl; notices on 20 routes; the scan link with and without a press; the output check on two independent held-out sets and on 544 sentences of stored real-model text.
7. **Passed / failed.** Final suite 7471 passed, 1 skipped, 0 failed (run 7). Output check on unseen sentences: 10 of 40 advice caught and 2 of 40 research wrongly flagged (set A, version 2); 27 of 50 and 1 of 50 (set B, version 3); version 4 not yet measured on unseen sentences. 0 false alarms on 544 sentences of stored real-model text and 2,361 of Optic's own research text. Requirements R02-01 to R02-13: 12 PASS, R02-11 BLOCKED. The seven named prompts with the real model: NOT TESTED (BL-01).
8. **Browser verification.** Milo panel (policy line, removal note, both kept in history); Overview, Options, Investing, Retirement (v2 and Classic), Macro pairs, Alerts, Compare, Paper Desk, Scan; notices on 20 routes; no console errors.
9. **Outstanding.** R02-11 BLOCKED on BL-01; counsel questions Q1 to Q12 (BL-02); owner decisions BL-07 (model-based check), BL-08 (brokerage consent version), BL-09 (overnight feed and Yahoo data); BUG-032's cost part (Phase 10).
10. **Commit and next phase.** `a76916b`; next is Phase 03. To continue in another session: open `~/Optic/wt-ultra`, read this file, REQUIREMENTS_MATRIX.md and `directives/03-search-ticker-navigation.md`, then start the `optic-ultra` server.

## Phase 01 report (directive 01; reporting format of directive 00)

1. **Inspected.** The whole repository at 9fa0f36: 189 Python modules (about 94,600 lines), 241 routes, the v2 front end (112 JS files, 4 CSS files), Classic's route set, CLAUDE.md and the existing docs, 516 test files, the deploy configuration, every local branch with unshipped commits. The running app on a local server: 56 v2 routes at four sizes, guest and signed in (448 loads), Classic's 26 views at two sizes, a dead-click pass (2,431 controls listed on 56 routes, 1,006 pressed and responding), the Milo pipeline through the stand-in, the server log.
2. **Problems discovered.** 77 findings in BUG_REGISTER: 9 P0, 33 P1, 35 P2. P0: Milo's portfolio tool on every page (BUG-007); login CSRF in Google/Apple sign-in, live in production (BUG-043); the "Risk and process" persona leading with position size and stops (BUG-045); the Overview's trade plan with entry, targets, stop and shares (BUG-056); the Options entry order with limit price, target and stop (BUG-057); the options contract picker (BUG-024) and Retirement's model allocation (BUG-025), both to assess; the overnight Robinhood feed without a switch (BUG-022); unlicensed Yahoo data (BUG-023, BLOCKED). The demo's complaints all reproduced: the advanced switch appends instead of replacing (BUG-001) and rewrites the knowledge level (BUG-002); "Follows <T>" and no SPY default (BUG-003); reading load (BUG-004: 1,384 words on the NVDA Overview before a click; BUG-005: Home's 12 panels and 187 controls); Milo sends nothing until the whole context is built (1.5 to 2.2 s cold with the stand-in).
3. **Root causes.** Named per row in BUG_REGISTER. Recurring ones: analytics modules write their output as instructions (setups, entries, sizing) and the pages print them; the knowledge level doubles as a density switch; Home's linked ticker falls back to the last company opened; fetches without request identity when a setting changes; OAuth state not bound to the browser.
4. **Fixes implemented.** None (discovery phase: "Do not redesign", "Do not make unrelated feature changes").
5. **Files changed.** `docs/post-demo-ultra/**` and a CLAUDE.md section only.
6. **Tests executed.** pytest full suite; `node --check` on 122 JS files; compileall; ruff (pyflakes rules) in a throwaway venv; route-table extraction; crawl of 500 loads; dead-click pass on 78 route views; three Milo stand-in probes; three read-only GETs against production (`/docs` exposure) and one free models call (key check).
7. **Passed / failed.** pytest 7108 passed, 1 skipped (opt-in live EDGAR), 0 failed, 6 warnings. node 122/122. 0 script errors and 0 overflow on every load. Ruff 59 findings, no undefined names. Local Anthropic key refused (401).
8. **Browser verification.** Headless Chrome crawl at 1440, 1280, 768, 390 (guest and signed in) and the browser pane: the advanced switch, "Follows AMD", the skip link opening MAIN, Dossier and palette searches, the Milo panel, a cold Dossier load.
9. **Outstanding.** Everything in BUG_REGISTER (by phase); BL-01 real model key; BL-06 Docker for the image build; agent-sourced registry rows not individually re-verified (their top claims were).
10. **Commit and next phase.** `795325a`; next is Phase 02. To continue in another session: open `~/Optic/wt-ultra`, read this file, REQUIREMENTS_MATRIX.md and `directives/02-advice-elimination-legal.md`, then start the `optic-ultra` server from `~/Desktop/.claude/launch.json`.

## Log

### 2026-10-29 setup
- Created the worktree and branch; unset the upstream. Saved the 14 directive messages verbatim. Wrote the tracking files and the CLAUDE.md section.

### 2026-10-29 Phase 01 (01:18 to 04:58 ET by the commit times, with a stop from about 02:00 to 04:50 at the usage limit)
- Baseline suite, syntax and lint checks, route table, architecture, crawl, dead clicks, Milo probe, security baseline, journeys, dependencies, visual audit, four registry files, 77 findings, R01 statuses (11 PASS, R01-05 PARTIAL: image build blocked).

### 2026-10-29 Phase 02 (05:00 to 06:55 ET)
- Policy module, wiring, prompts, rule-written research in v2 and Classic, disclosure registry, Milo and Classic notice and note, alerts, scan consent; output check rebuilt twice on held-out sets written by separate agents; COMPLIANCE_REVIEW.md; suite green (run 7); committed (not pushed).

### 2026-10-29 Phase 03
- Ticker precedence and SPY default, "Follows" removed, one resolver, palette and typeahead fixes, identity guards, 27 scenarios passed, suite green; committed (not pushed).

### 2026-10-29 Phase 05
- Five levels with the directive's names, one slider in three places, one preference with an account column and one rule in both apps (including a failed save), the level applied to Milo, deep research and the briefing in both apps, "Explain it for" on shared texts, the glossary policy on rule-written text and chart readings, the five-level proxy run, 22 browser checks, suite green; committed (not pushed).

### 2026-10-29 Phase 06
- Dossier pipeline mapped; one analysis area swapping a rule-written Simple Analysis (five levels) and the sectioned Advanced Analysis on the density setting; visit tokens; the swap's fade and place; the Simple Analysis following the header's price; the search focus race fixed; 16 browser checks, accuracy 10 of 10, Phase 03's 27 scenarios; suite green; committed (not pushed).

### 2026-10-29 Phase 07
- The fourteen stages traced and measured before and after; the route starts at once and times every answer; the answer drawn as it arrives, a finished paragraph once, the chart once, the arriving paragraph as markdown; following the end left to the reader; New conversation and history wait for an answer and say why, Close leaves it running, reopening restores the place; history local and per account (documented); the limit said, pasted images attached; small phones given room; Classic unchanged; 28 of 28 browser checks (20 before), suite green; committed (not pushed).

### 2026-10-30 Phase 08 (to 01:43 ET)
- The 137-case evaluation suite, Milo's four data tools, freshness on every tool result, the research pack following the named symbol, stand-in rounds and advice set C; suite green; committed (not pushed).

### 2026-10-30 Phase 09 (to 02:50 ET)
- Every pathway and cache documented, the reconciliation (277 of 278 PASS, 1 UNVERIFIED), the session against NYSE's calendar, scenarios A to H, eleven cache risks fixed; suite green; committed (not pushed).

### 2026-10-30 Phase 10 (02:50 to about 13:30 ET)
- Performance baseline, fixes and two A/B runs; the cost audit; the security review (12 fixed, 5 escalated); 25 routes checked for accessibility; the 116-check sweep; twelve resilience cases; the analytics review; 28 new rows and 31 earlier ones closed; suite green; committed (not pushed).

### 2026-10-30 Phase 11 (about 13:30 to 18:45 ET, with a pause of about three hours at the usage limit)
- The feature check (95 ids), the demo journey under five scenarios (15 of 15 on the final tree), 14 adversarial cases, the earlier phases' checks rerun, the reconciliation three times, the Milo suite, a fresh advice set (14 of 50 caught), the density comparison with the demo-day build, an independent review of Phase 10; 22 defects found, 18 fixed; FINAL_REPORT: NOT READY, blocking issues remain; suite green; committed (not pushed).

### 2026-10-30 evening, after Phase 11: the hotfix and BUG-202 (about 20:00 to 21:45 ET)
- On the owner's yes, a hotfix of BUG-200 and BUG-201 for live main: branch `hotfix-next-report-date` from origin/main `9fa0f36` in `~/Optic/wt-hotfix-report-date`, one commit (`543a6e5`), suite 7,112 passed, 1 skipped; not pushed.
- Tracing the provider's other readers while porting showed BUG-202: Phase 11's BUG-201 fix, made in the provider, would have taken the week's earlier reports out of Earnings this week and the weekly digest. The fix moved to `_upcoming` in `_swing_snapshot` on both branches, with identical code and one shared test file so they merge cleanly; the provider gives Yahoo's date again.
- Real data on local servers after the close: live main's code had no next report for NVDA, MSFT, AAPL, KO or META, and took KO's and META's past reports as the surface's event; the hotfix has NVDA 2026-11-17, MSFT 2027-01-27 and AAPL 2026-11-02, and nothing past. Yahoo then refused this machine's quote and chain requests (401), so this branch's `/api/ticker` could not be read again; its Earnings this week, rebuilt with the fix, kept the week's 22 past reports with their results, as the hotfix's did (TEST_RESULTS, after Phase 11).
- Live main moved to `a10eaba` (WaveTrend shipped). The hotfix rebased onto it without conflict as `8e2cbf4`; suite 7,158 passed, 1 skipped. `git merge-tree` of this branch with the hotfix and with live main: no conflict.

### 2026-10-31: the hotfix shipped (about 15:40 ET)
- On the owner's yes. origin/main was still `a10eaba`, so the commit whose suite had passed (7,158 passed, 1 skipped) went as it was: `a10eaba..8e2cbf4`, a fast-forward from `~/Optic/wt-hotfix-report-date`, at 19:40:28 UTC. The live site served `8e2cbf4` 90 seconds later (booted 19:41:43 UTC; one health check went unanswered during the swap).
- On the live site, before and after (`~/Optic/work/hotfix-report-date-2026-10-30/ship/`): before, the field was missing for NVDA, MSFT, AAPL, KO and META, and KO's and META's surfaces marked every expiry as holding a past report; after, NVDA 2026-11-17, MSFT 2027-01-27 and AAPL 2026-11-02 (the date Apple announced), and KO and META have no next report and no surface event (TEST_RESULTS, after Phase 11).
- This branch merges with the new live main without conflict (`git merge-tree`, exit 0). It is still not pushed (D-100, D-101).
