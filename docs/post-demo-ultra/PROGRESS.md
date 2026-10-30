# Progress

Read this and [REQUIREMENTS_MATRIX.md](REQUIREMENTS_MATRIX.md) before changing anything (directive 12).

## Current state

- **Current phase:** 07 Milo streaming and conversation (next). Phases 01 to 06 complete (reports below).
- **Branch / worktree:** `post-demo-ultra` in `~/Optic/wt-ultra`, from `9fa0f36` (tag `post-demo-ultra-baseline`). Upstream unset; nothing pushed or deployed.
- **Commits:** `fce3e71` setup; `8040f8a` and `795325a` Phase 01; `d4a2b1a` Phase 01 report; `ce60b16` Phase 02 policy module (WIP); `c6724ff` Milo portfolio privacy (cherry-pick of 2236205); `a76916b` Phase 02; `6f2e814` its commit id; `7b14b56` Phase 03; `2f6a548` its commit id; `381a018` Phase 04; `b07e181` its commit id; `e64a5ee` Phase 05; `448e633` its commit id; `0448900` Phase 06.
- **Local server:** launch config `optic-ultra` (:8250, stand-in model :8251 from `tools/milo_standin_ultra.py`, which adds an `ADVISE` keyword that makes the answer break the policy and, since Phase 05, writes a Sector Read and a portfolio briefing in their writers' shapes; data `~/Optic/ultra-data`, sandbox brokerage, jobs off, no real model key). Seed password in `~/Optic/ultra-data/seed-output.txt` (never print it). The server does not reload Python: restart it after editing server code. The desktop app stops it when the session is paused; start it again with preview_start.
- **Working folder (outside the repo):** `~/Optic/work/post-demo-ultra-2026-10-29/` (tools/, crawl1/, dead/, sheets/, baseline/, milo/, registry/, phase02/ to phase06/; the five-level proxy run in phase05/proxy/).
- **Resource rule:** at most two subagents at a time (DECISIONS D-007). One proxy answer costs about 180,000 agent tokens.
- **Next action:** Phase 07 (Milo streaming, New Chat, Close): read `directives/07-milo-streaming.md`, the R07 rows, and the Milo findings in registry A (A16 to A20). The Phase 06 browser tools are `tools/phase06_checks.py` (requests held or failed in the browser) and `tools/phase06_accuracy.py`.

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
10. **Commit and next phase.** COMMIT_LINE; next is Phase 08.

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
