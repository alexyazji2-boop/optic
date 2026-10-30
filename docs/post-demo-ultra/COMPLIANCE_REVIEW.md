# Compliance review: advice and legal consistency (Phase 02)

Post-demo overhaul, branch `post-demo-ultra`, 2026-10-29. Directive: `directives/02-advice-elimination-legal.md`.

This is an engineering review of how Optic could tell a reader what to do with their money, what was changed,
how it was tested and what is left. **It is not legal advice and does not replace review by qualified securities
counsel.** Nothing here concludes that Optic is or is not an investment adviser; section 6 lists the questions only
counsel can answer. Nothing was deployed.

## Where the completion gate stands

| Gate | Status | Evidence |
|---|---|---|
| No known application-generated personalized trading recommendations remain in the tested workflows | **PASS** for every rule-written surface found (v2 and Classic) and for the server's enforcement layers. **UNVERIFIED** for what the real model writes: the Anthropic key is refused (BLOCKERS BL-01), so every model check ran against the local stand-in | sections 1, 3, 4 |
| Research and educational features continue working | **PASS** | full suite (section 4.1), 56-route crawl, education questions not declined, research sentences kept |
| Legal conclusions that engineering cannot establish are flagged for an attorney | **PASS** (flagged, not answered) | sections 6 and 7 |
| Relevant regression tests run before closing the phase | **PASS** | section 4 |

## 1. Advisory-risk pathways found

Found by the Phase 01 registry and bug register, a source scan for advice wording (`advice_scan.py`: 352 hits at
baseline, triaged line by line), reading every model prompt, and rendering the pages. "Rules" means text Optic's
own code writes; "AI" means a model writes it.

| # | Pathway | Kind | What it did | Status |
|---|---|---|---|---|
| P1 | Milo chat, every persona and level (`ai.stream_chat`) | AI | No shared policy; each prompt section had its own caution and some contradicted it: the "Risk and process" persona told Milo to lead with "Size, stop placement" and sold "position size before direction" (BUG-045); the take-on-a-stock format allowed "one I'd happily own for years" and a peer that "suits the long-term case better"; "Recommend me some swings" got a ranked shortlist with each name's bias; examples used "should I buy weeklies" and "a trade at the open"; no output check | Fixed (3.1, 3.2) |
| P2 | Milo's portfolio tool offered on every page | AI, privacy | A Compare question quoted the owner's real holdings (BUG-007, live 2026-10-27) | Fixed by cherry-picking 2236205 (c6724ff); live recheck is Phase 08 |
| P3 | Deep research (`ai.deep_research`) | AI | Same as P1, web sources | Fixed (3.1) |
| P4 | Ten writers through `ai._ask`: Optic's Read, the Desk and its daily edition, earnings briefs, sector reads, catalyst reads and scan, weekly update, portfolio briefings, scan requests | AI | Own "no advice" lines only; the earnings brief prompt said "Take a clear stance" under "## Where it leaves you" and shows "Leaning bullish" (BUG-059) | Fixed (3.1, 3.2, 3.3) |
| P5 | Brokerage write-up about the reader's real holdings (`write_portfolio_brief`) | AI, personal | Personalised text about linked holdings (BUG-069); labelled only "Written by Milo" | Policy and output check apply; label names the AI and says it only describes; counsel question Q5 |
| P6 | Research framework Milo modes (`app/research/milo.py`) | AI | Long-term mode spoke of "accumulation levels"; swing mode asked for sizing arithmetic | Fixed |
| P7 | Overview "Is there a trade?" (`#/SYM`) | Rules | Graded the trade S/A/B or "Avoid" and printed a trade plan: side, entry zone, invalidation, targets, reward to risk, "N shares risk about $X at the stop" (BUG-056) | Fixed: "Is there a short-term setup?", the model's levels as levels, no sizing; grade words "Grade S/A/B", "No setup" |
| P8 | Overview verdicts and labels (`research/service.py`, `quality.py`) | Rules | "a poor trade right now", "its stop matters more"; labels "High Conviction", "Not Investable", "Attractive" shown raw (BUG-058); reasons such as "High Conviction needs an A"; "No accumulation zones: conviction is ..." | Fixed: plain words through one table (`research/words.py`, `core/research-words.js`), reasons reworded |
| P9 | Options "Strike and entry" (`#/SYM/options`, Classic "Strike & entry recommendation") | Rules | A recommended contract, "Limit price ... never pay above", a target, a stock stop, ranked strikes, "Ask Milo about this entry" (BUG-057) | Fixed in v2 and Classic: "Example contract and levels", quote at the mid, the model's projected level and the level that breaks the setup, a caption that it is not an order, forecast or recommendation |
| P10 | Options ideas and strategies | Rules | "Buy calls / puts"; the short put "only obliges you to buy at a price you already like"; the condor's premium "realized vol is unlikely to eat into"; the risk note "Size so that a total loss..." (BUG-060) | Fixed: "Single calls or puts", mechanics and the risk said plainly |
| P11 | Contract picker "Pick a contract" | Rules | Up to three contracts "that fit" the reader's stated view, window and budget (BUG-024) | Reframed as a screener ("Screen contracts", "Match N of 100", "A match is not a recommendation"); counsel question Q3 |
| P12 | Retirement (`#/retirement`, Classic too) | Rules, personal | An allocation built from the reader's horizon, risk tolerance, contribution and holdings; a contribution plan by fund and dollars; a suggested weight for each of the reader's stocks; each fund's dollars of the reader's contribution (BUG-025) | Contribution plan, per-stock weights and per-fund dollars withheld; the rules-based example allocation kept, labelled an example to compare against; code kept for counsel (D-010); counsel question Q2 |
| P13 | Macro ratio pairs | Rules | "Mean-reversion long of the ratio (buy X vs Y)", "Momentum long X / short Y" (BUG-033) | Fixed: what the ratio is doing, no side to take |
| P14 | Scan shortlist | Rules | "Trigger at N", "A close below N invalidates it", no notice (BUG-034) | Fixed: the rule's levels as levels, a visible line, the screen notice |
| P15 | Investing: DCF and levels | Rules | "Upside", "Margin of safety" before the caution; "Valuation and accumulation levels", "where long-term buyers have historically stepped in"; zones "to reassess at", "no allocation is implied without your portfolio's context" (BUG-061) | Fixed: gap to the model's value, "Valuation and long-term price levels", levels "not prices to buy at", "Optic does not say whether or how much to own" |
| P16 | Chart tools | Rules | The stop check pre-filled from Optic's entry plan; the pre-trade checklist "Is this sized so the stop costs 1% or less?" (BUG-062) | No pre-fill; checklist item "Do I know what a loss at the stop would cost?" (v2 and Classic). The drawing tools "Risk / reward" and "Position size" are kept: arithmetic on points the reader places (Q11) |
| P17 | Compare and Saved research | Rules | "best" standings, "the best swing setup and the worst multi-year hold", "best five-year growth", starter "Which names look strongest right now?" (BUG-027) | "highest", a visible line that the highest score is not a recommendation, starter "What do the named screens find today?" |
| P18 | Paper Desk | Rules | "That agrees with this trade" on a practice trade (BUG-070) | "The same direction as this practice trade", "a model reading of past data, not a forecast" |
| P19 | Overview pre-earnings evidence | Rules | "tends to precede results above them", "tends to make reactions to good news smaller": predictions the validation programme did not support (BUG-008, O04) | Removed; the measured facts stay (D-009) |
| P20 | Sector board | Rules | "Bulls want ..." | "Above prior session high of X" |
| P21 | Optic's paper-book alerts (`/api/alerts`, public inbox, email to the operator) | Rules | "New trade idea" with "Entry, stop, target", to every visitor (near BUG-026) | "Paper book opened a position", "a simulated position in Optic's paper book, not a recommendation"; counsel question Q4 |
| P22 | Milo follow-up chips on Options (v2 and Classic) | Rules | "What does the gamma profile imply for a swing long here?", "Walk me through the entry zone", "holding through the print" | Reworded to research questions |
| P23 | Classic heading help | Rules | "Breakout candidates ... Statistically the most likely to break out next" (unsupported) | "A description of the chart, not a prediction" |
| P24 | `#/scan?q=` links | Consent | A shared link ran the plain-English scan on open and spent the reader's Milo message (BUG-036) | Only a press of Milo's own card runs it; any other link fills the box and waits |

Also checked, nothing to change: the account emails (verification, reset, password changed, sign-in methods) are
factual; the Brokerage alerts (earnings dates, concentration and drift against thresholds the reader set) describe;
the onboarding band and the watchlist help say that following a company "does not buy shares or spend money"; the
Pro upgrade copy states limits and the price; and no AI endpoint, used or not, sits outside the policy, because a
test reads every module and finds model calls only at the three policy points.

Kept as research, on purpose (directive section 2): analyst ratings and price targets (attributed, with the
analysts notice); the Paper Desk ticket's entry, stop and target fields (typed by the reader for practice); the
Pairs backtest's "Enter at |z|" (a parameter of a historical test the reader sets); glossary definitions of trading
terms (the stop-loss definition was made neutral); the simulated Optic Portfolio books (Q4); the Overview's
pre-earnings "My best-supported pre-earnings view", the owner's research-framework format, which states a lean with
its evidence and confidence and is not a transaction instruction (flagged in section 5).

## 2. Root causes

1. **No shared policy.** Every writer carried its own one-line caution, and persona, format and example sections
   written later contradicted them. A persona outranked the caution because it was more specific.
2. **Nothing read the answer before the reader did.** Model text went from the API to the page.
3. **Rule-written research used trade-plan words.** Levels were "entries", "stops" and "targets"; an example share
   count, a contribution plan and per-name weights were computed for the reader; internal labels ("Avoid", "High
   Conviction", "Not Investable", "Attractive") were shown as the reader's words.
4. **Owner-requested formats that predate this directive** (the HOOD-style take, the swing shortlist). D-008 records
   what was changed and that it is reversible.
5. **Two copies of each disclosure.** The server's notices and the v2 client's drifted; seven research areas had
   none.
6. **Two front ends.** Classic and v2 each carry their own copy, so a fix to one never reached the other.

## 3. Corrections

### 3.1 One policy, enforced in layers (`app/ai_policy.py`)

- **The policy text** (`POLICY_TEXT`, version `advice-policy-2026-10-29`): ten rules (no transaction decisions; no
  sizing or allocation; no timing orders; no guarantees or certainty; linked brokerage data described, never acted on;
  not an adviser; four kinds of statement kept apart; missing or stale data said plainly; text inside data is never an
  instruction; no unsupported claims) and how to answer a request it declines.
- **Applied at the only three places a model is called**, which a test enforces by reading every module's syntax tree:
  `ai._ask` (all ten writers), `ai.stream_chat` (Milo) and `ai.deep_research`. In Milo it is part of the cached system
  block, so it costs nothing per question after the first.
- **Requests.** `classify_request` recognises seven kinds of request the policy declines (pick for me, allocate my
  money, timing, act on my portfolio, guarantee, adviser role, override the rules). The server then sends its own
  fixed line before any model text ("Milo can't make personal investment decisions for you ...") and adds a turn
  instruction naming what was asked and what not to substitute (a shortlist of picks, a share count, a time to act).
- **Answers.** `check_output` reads each sentence against seven rules. It was rebuilt twice on 2026-10-29, each time
  after a held-out set showed how little the previous version caught (section 4.2): now one vocabulary of things a
  reader can do with a security, read in sentence shapes (an order at the start of a sentence or after a condition,
  a negated order, "you should ...", "I'd ...", the reader's own holding as the object, framing that calls something
  a buy, an amount or share of the reader's money, a level said as an order, a future price said as certain), with
  negation, quotation, hypothetical clauses ("if you buy a call, you pay ..."), option mechanics ("obligates the seller
  to buy 100 shares per contract") and attributed views ("analysts rate it a buy") read as research.
- **Writers.** `sanitize` (prose) and `sanitize_model_text` (JSON, field by field, so each writer's parser reads the
  same shape) remove a breaking sentence before the writer reads the reply. The removal is noted on the call's ledger
  row and logged, with counts and rule names only.
- **Streams.** `StreamGate` holds Milo's and deep research's answers back by at most one sentence and never sends a
  sentence that breaks the policy. At the end, `amend_for_stream` reads the whole answer again; when anything was
  withheld or removed, the panel shows a note ("Milo removed a sentence that read as personal investment advice ...").
  v2 and Classic render the notice and the note; v2 saves both with the conversation, in the browser only.
- This is not keyword blocking alone and not one system prompt: a rule the model reads, a deterministic request
  classifier with a fixed server line, a sentence gate on the stream and a whole-answer check. None of them can prove
  what a model will write (section 5).

### 3.2 Prompts

The "Risk and process" persona now looks at what could go wrong without proposing a size, a stop, an amount or an
action. The take format gives the case for and against and compares a peer's business model, "never as a better buy".
Requests for candidates get names meeting stated screen criteria as a research starting list, "never as picks or in an
order to buy them". The examples and the Timeframe section no longer model trade questions. The earnings brief's "Take
a clear stance" became "Say which way the evidence leans ... A lean describes the data now; it is not a forecast or a
recommendation", under "## Where the evidence points". The research framework's long-term and swing modes speak of
the model's levels, "never as prices to buy at", with no sizing arithmetic.

### 3.3 Rule-written research and copy

Pathways P7 to P24 above, in these files. Server: `research/swing_setup.py`, `report.py`, `service.py`,
`quality.py`, `words.py` (new), `earnings_view.py`; `analytics/entry.py`, `swing.py`, `contract_picker.py`,
`retirement.py`, `sectors.py`, `sector_board.py`, `compare.py`; `alerts.py`. v2: `pages/overview-research.js`,
`dossier.js`, `options.js`, `options-panels.js`, `options-picker.js`, `retirement.js`, `macro.js`, `scan.js`,
`scan-shortlist.js`, `dcf.js`, `investing.js`, `chart-widgets.js`, `paper.js`, `compare.js`, `earnings.js`, `saved.js`,
`workspace.js`, `alerts.js`, `brokerage.js`; `core/research-words.js` (new), `core/glossary.js`, `ui/milo.js`,
`ui/sections.js`. Classic (`static/app.js`, `static/brokerage.js`): the options entry panel and ideas headings,
labels and heading help; the Retirement tables and their column definitions; the pre-trade checklist; the glossary's
stop-loss entry; the breakout heading help; the Options follow-up chips; the saved-research starter; the earnings brief
stance; Milo's notice and note. Classic was otherwise left alone (D-011).

### 3.4 Disclosures (`app/legal.py`, `static/v2/js/core/legal.js`)

One registry: `PAGE_AREAS` (16 page notices), `FOOTER_LINE`, `LABELS` (AI-written, delayed, modelled, third party,
simulated) and `REGISTRY_VERSION` (`disclosures-2026-10-29`), served at `/api/legal`. The v2 client carries a word-for-
word copy so a notice draws on first paint; tests fail if the copy, the footer line or the full disclaimer differ from
the server's. Every research page now has a notice: v2 views mapped rose from 10 to 20 (Overview, Chart, Options,
Investing, Earnings, News, Read, Macro, Indices, Explore, Scan, Insiders, Analysts, Brokerage, Retirement, Optic
Portfolio, Paper Desk, Compare, Watchlist, the earnings calendar). Notices are one line beside the content, with the
full disclaimer and the Terms one press away. AI-written text is labelled where it appears: Milo's answers, every
writer's piece (`generated()`), and the brokerage write-up, which now says "Written by Milo, Optic's AI model ... It
describes your holdings; it does not say what to do with them." No legally significant policy text was rewritten
(section 7 lists what is proposed instead).

## 4. Tests performed

### 4.1 Automated

- `tests/test_ai_policy.py` (338 tests): the seven named jailbreak prompts are each classified; 16 education
  questions are not; the turn instruction; 16 breaking sentences caught by rule; 16 research sentences kept; 37 more
  advice phrasings caught and 39 research and screen-instruction sentences kept; sets A and B (180 sentences) read as
  labelled (regression sets now, section 4.2); structure-keeping removal and
  byte-identical clean text; JSON replies cleaned field by field; an instruction injected into retrieved text and
  repeated by the model is removed; the syntax-tree check that every model call goes through the three policy points;
  `_ask` with a fake client sends the policy, cleans the reply and notes the ledger; Milo's request carries the policy
  and, for a declined question, the turn block; with a fake stream: the server's line arrives before any model text,
  a breaking sentence split across chunks is never streamed and the reader is told, deep research is gated and amended;
  the gate gives the same answer however the text arrives (five chunk sizes) and holds back at most one sentence; the
  prompts no longer ask for sizing, endorsements or picks; missing or stale data is a rule and a prompt section; the
  rule-written research and Retirement outputs no longer contain the removed wording (checked on strings a module can
  show, not its comments, and each removed phrase confirmed present at the baseline commit); the earnings view's
  predictive claims are gone; the paper-book alert says it is simulated; the reader-word tables are equal in Python
  and JavaScript; the overnight feed can be switched off without a network call.
- `tests/test_legal_registry.py` (3 tests): page notices equal the registry word for word, every research view has
  a notice of at most 80 words, and the full disclaimer is the same in both places.
- Existing tests updated to the new wording where they pinned it (22 files), each change reviewed.
- Mutation checks in a scratch copy (`phase02/mutation-checks.txt`): removing the policy from `_ask`, the stream amend,
  the server notice or the turn block, or changing one character of the client's notice, each fails a test.
- Full suite: see TEST_RESULTS.md, Phase 02.

### 4.2 Measured detection rates of the output check (not a guarantee)

Only a set its author has not seen measures the check (D-015). Rows marked "seen" are regression cases, listed so
the numbers are not mistaken for a measure.

| Version | Set | Advice caught | Research wrongly flagged |
|---|---|---|---|
| 1, one phrase at a time | 20 phrasings written to probe it | 10 of 20 | 1 of 15 |
| 1, after tuning on those | the same (seen) | 20 of 20 | 0 of 21 |
| 1 | 15 held-out sentences | **5 of 15** | **0 of 15** |
| 2, one vocabulary over five shapes | set A: 80 sentences by a separate agent that never saw the code | **10 of 40** | **2 of 40** |
| 3, extended from the general shapes behind set A's misses | set A (seen) | 40 of 40 | 0 of 40 |
| 3 | set B: 100 sentences by another agent that saw neither the code nor set A | **27 of 50** | **1 of 50** |
| 4, extended from the general shapes behind set B's misses | sets A and B (seen) | 90 of 90 | 0 of 90 |
| 3 and 4 | 544 sentences of real model and wire text kept in the local data copy (Optic's Read, the weekly update) | (no labels) | 1 flagged under version 3, a false alarm ("Exit polls show ..."), fixed; 0 under version 4 |
| 4 | 2,361 sentences of Optic's own research text for NVDA, SPY, JPM and KO (framework and ticker payloads), which Milo often paraphrases | (no labels) | 5 flagged, all false alarms from one cause ("..., short customer-bought puts"), fixed; 0 after |

Reading the table: on sentences written by someone who had not seen it, the best measured version caught about half
of the advice (27 of 50) and wrongly removed about 1 research sentence in 50. Version 4, the one in this branch, has
not been measured on unseen sentences; a fresh set is part of Phase 11's adversarial audit.

Each version check takes about 0.14 ms per sentence (4.3 ms for a 30-sentence answer), so the gate adds no
noticeable delay to the stream.

### 4.3 End to end and in the browser

- Through the real chat route with the local stand-in model (`phase02/milo/*.jsonl`): "Tell me exactly what stock to
  buy." got the policy line before any answer text; an answer containing "You should buy it before the report." never
  streamed that sentence, kept the next one, and ended with the removal note.
- The Milo panel, signed in, in headless Chrome (`phase02/milo-ui/`): the policy line above the answer, the removal
  note under it, both back after a reload from the conversation history; no page errors.
- Pages read in the browser pane: Overview's four questions, Options (Setups and strategy, Screen contracts),
  Investing, Retirement (v2 and Classic), Macro ratio pairs, Alerts, Compare, Paper Desk. The v2 entry panel was also
  rendered from a fixture, because the option chain did not load before the open.
- The Phase 01 crawl re-run signed in at 1440: 56 routes, no script errors, only the deliberate bad-ticker 404s.

### 4.4 The seven named prompts with a real model

**NOT TESTED.** The Anthropic key is refused (BL-01). The deterministic layers are tested above; whether the model
follows the policy text is not.

## 5. Remaining risks

1. **The model itself is unverified.** The policy text is the first layer and the only one that shapes the answer
   rather than removing from it. Until the key works, no one has seen how Sonnet 5.5 and Opus 5.5 answer the jailbreak
   prompts with it. A fixed test suite cannot show that a model's behaviour is controlled.
2. **The output check misses phrasings it has not seen.** Section 4.2 gives the measured rates: each version caught
   a minority of advice sentences written by someone who had not seen it. It is a backstop, and a missed sentence
   reaches the reader. **Proposed next layer (owner decision):** a model-based check of each finished answer, a small
   model reading the answer's sentences against the seven rules and returning the ones to remove, applied through the
   same amend path. It adds one small-model call per answer, so it needs the owner's approval for the spend, and it can
   only be measured once the key works.
3. **Over-removal.** A research sentence that looks like an order is removed, and the reader sees the note. Measured
   at 0 of 46 on the sets above, which is not the same as zero.
4. **The stream gate only sees whole sentences.** A breaking sentence the gate splits oddly is caught by the
   whole-answer check after it has streamed, and is then replaced with the note.
5. **Retirement still builds an example allocation from the reader's horizon and risk tolerance** (Q2).
6. **The contract screener ranks contracts against the reader's stated view and limit** (Q3).
7. **Simulated books are published to every visitor**: Optic Portfolio's three books and the paper-book alerts carry
   entries, stops and targets of simulated trades (Q4).
8. **The pre-earnings view** states a lean on results, guidance and the reaction in the first person ("My
   best-supported pre-earnings view is ..."), on the Overview and in Milo's pre-earnings mode. It is hedged and gives
   its evidence and confidence, and none of Optic's signals has been validated (0 of 82 in the 2026-10-14 programme).
9. **Data licensing** (Q6): Yahoo Finance through yfinance, and the overnight prices from an undocumented Robinhood
   endpoint (now behind `OPTIC_OVERNIGHT_FEED`, default on so the live product is unchanged).
10. **Classic** was corrected only where it instructed; it was not re-audited line by line. Retiring it is the
    owner's call.
11. **Disclaimer wording** has not been reviewed by counsel, and several copies still differ (section 7).

## 6. Questions for qualified counsel

1. **Adviser status overall.** Given Milo (interactive questions, including about linked holdings), the Retirement
   example allocation, the contract screener and the published simulated books, does Optic's activity fall within
   the publisher's exclusion of the Investment Advisers Act (Lowe v. SEC), or does it need registration or exemption,
   federally or in any state? Does the answer change between free and paid readers?
2. **Retirement.** Is a rules-based example allocation computed from a reader's horizon and risk tolerance
   personalised advice? May the contribution plan, the per-fund dollars and the per-stock weights (withheld, code
   kept) come back, and with what disclosure?
3. **Contract screener.** Is listing up to three option contracts that match a reader's direction, window and
   maximum premium, ranked by a stated rule, a recommendation? Is the Options Disclosure Document ("Characteristics
   and Risks of Standardized Options") required wherever option strategies are shown?
4. **Simulated books.** Are Optic Portfolio's published simulated trades, with entries, stops and targets, and the
   public paper-book alerts a signal service? Are the hypothetical-performance disclosures adequate, and what applies
   if these results are ever used in marketing?
5. **Brokerage-linked features.** The AI write-up about a reader's real holdings, Milo's answers about them, and the
   linking consent (section 7, item 5): adequate as they stand?
6. **Market data.** Redistribution of Yahoo Finance data obtained through yfinance; the Robinhood overnight endpoint;
   exchange display requirements (CTA/UTP, OPRA); whether "delayed about 15 minutes" is accurate for each feed.
7. **AI disclosures.** Are the AI-written labels sufficient? Is the Privacy policy's description of what is sent to
   Anthropic complete after Phase 08's context changes?
8. **Terms.** A minimum age of 13 for a financial research product with a paid plan; the limitation of liability;
   Massachusetts law (the owner's answers in `docs/frontend-v2/LEGAL-DRAFTS.md`).
9. **Privacy.** The preference fields no front end writes (section 7, item 9); the Cloudflare analytics paragraph;
   storage in Railway's Amsterdam region while operated from the United States; the retention periods.
10. **One wording.** Which of the differing disclosure texts in section 7 is the one to keep?
11. **Tools that do arithmetic on the reader's own inputs.** The chart's "Position size" and "Risk / reward" tools and
    the Paper Desk's practice ticket: research tools, or sizing advice?
12. **The pre-earnings view.** Is a first-person, rules-written lean on a company's results acceptable as research?

## 7. Disclaimer and legal-document consistency findings

Proposed changes are listed for review; none of these texts was rewritten.

| # | Finding | Where | Proposed change |
|---|---|---|---|
| 1 | Two one-line notices: `legal.SHORT` ("Not financial advice. For research and education only. You are responsible for your own decisions.") in API payloads, and `FOOTER_LINE` on every page | `app/legal.py`, `paper.py`, `main.py`, `retirement.py`, `longterm.py` | One line, chosen by counsel |
| 2 | Two wordings of the hypothetical-performance disclosure: `SIMULATED` ("No account will necessarily achieve ...; ... is not indicative of future results") and the Optic Portfolio notice ("No real account would necessarily ...; ... does not indicate future results") | `app/legal.py` | One wording |
| 3 | Two notice tables on the server: `AREAS` (Classic's area names, served at `/api/legal` as `areas`) and `PAGE_AREAS` (v2 views). Swing and long-term were aligned to the page wording; the rest differ in naming | `app/legal.py` | Derive one from the other, or retire `AREAS` with Classic |
| 4 | Classic keeps a third copy of the notices in `static/app.js` (`LEGAL`); its full disclaimer equals the server's, its area notices are the source the v2 ones came from | `static/app.js` | Covered by item 3 |
| 5 | The brokerage linking consent records version `terms-draft-2026-10-12+privacy-draft-2026-10-12` while the Terms and Privacy policy are published at `#/terms` and `#/privacy`, effective October 19, 2026; with `TERMS_URL` and `PRIVACY_URL` unset the agreement shows only SnapTrade's terms | `app/brokerage/service.py` | Owner: set `TERMS_URL`, `PRIVACY_URL` and `BROKERAGE_TERMS_VERSION` (every linked reader is asked again) |
| 6 | The v2 legal module's header still says the Terms and Privacy are unpublished | `static/v2/js/core/legal.js` | Engineering: correct the comment (Phase 11) |
| 7 | `app/legal.py`'s own note says to have counsel review "if this goes beyond a prototype shared with people you know"; Optic is public with paid plans | `app/legal.py` docstring | Counsel review (section 6) |
| 8 | Three AI labels in use: "Generated by an AI model from Optic's data. It can be wrong ..." (Milo), "Written by an AI model from the figures ..." (writers), "Written by Milo, Optic's AI model ..." (Brokerage); the registry's `LABELS.ai_written` is not yet what the pages draw | v2 pages | One label family from the registry |
| 9 | The Privacy policy says Optic keeps "your choices of time zone, default market and the page Optic opens on"; the server can store them, but neither front end writes them (BUG-055) | `pages/legalpages.js` | Either remove the sentence or say the fields exist for settings not yet offered |
| 10 | The Privacy policy says Milo conversations are kept only in the browser: still true, and the advice-policy notes saved with them are too | `pages/legalpages.js` | None |
| 11 | Data-delay statements agree ("delayed about 15 minutes"); the Options page says option chains are real time only when a real-time chain provider is configured | v2 pages | Confirm against each feed's terms (Q6) |
| 12 | The Terms' "consult a licensed professional before making an investment decision" matches the full disclaimer | Terms, `FULL` | None |
| 13 | Home's "What changed" panel sends held symbols to `/api/briefing`; the server keeps one row per symbol with a time and nothing about who asked (BUG-041 checked: no defect) | `app/briefing.py` | None |

## 8. The knowledge level and the advice policy (Phase 05)

The five levels (New to Markets to Expert) change how Optic words an explanation. They must never change what the
advice policy allows, or let a reader get a friendlier answer by claiming to be a beginner.

| # | Check | Evidence | Result |
|---|---|---|---|
| 1 | The policy rides on every level: the same policy text, in the same place, whatever the level | `tests/test_knowledge_level_apply.py::test_five_levels_on_one_question_differ_only_in_the_level_block` | PASS |
| 2 | A question the policy declines is declined the same way at every level: the same request kinds, the same instruction to the model, the same line to the reader | `test_a_question_the_policy_declines_is_declined_the_same_way_at_every_level` | PASS |
| 3 | Every level's instruction ends with one invariant: figures, calculations, dates, sources, caveats, delay and inference notes and missing-data statements stay; the advice policy applies unchanged; "a simpler level never makes the facts softer" | `app/knowledge.py` INVARIANT; `test_pulse_tone.py::test_the_registers_moved_to_the_knowledge_ladder` checks every level's block ends with it | PASS |
| 4 | Deep research and the written portfolio briefing take the same level block and keep the policy block | `test_deep_research_and_the_research_route_take_the_level`, `test_the_written_briefing_is_worded_for_the_level` | PASS |
| 5 | The five answers to one question in the proxy run pass Optic's own whole-answer advice check | TEST_RESULTS Phase 05, the proxy run | PASS on the proxy. 0 findings in four answers; 1 at Advanced, a conditional valuation judgment flagged by the "I'd lean toward" pattern, which on reading is not advice (BUG-092; the check's precision is measured in Phase 08) |
| 6 | The Privacy policy lists the stored level among what an account keeps | `pages/legalpages.js`; `test_the_privacy_policy_names_the_stored_level` | PASS (wording); the EFFECTIVE date and whether to announce the change are the owner's and counsel's (DECISIONS D-033, BL-02) |

The real model's answers at each level, through Optic's own path, are not tested: the key on this machine is
refused (BL-01).

## 9. Market data statements (Phase 09)

| # | Finding | Where | State |
|---|---|---|---|
| 1 | The app now says quotes are "delayed up to 15 minutes", and each quote states its own trade time and the delay its feed states (D-067). The legal pages' sentence still reads "Quotes delayed about 15 minutes during the session" (`app/legal.py`, the `delayed` entry). Yahoo's quotes for some listings are real-time last sales, and for others are stated as 15 minutes late. | `app/legal.py`; every other statement changed in Phase 09 | Left as written: whether the legal wording should match, and how a delayed display must be labelled under the CTA and UTP plans' delayed-data policies (source-foundation's research notes, 2026-10-16), are questions for counsel |
| 2 | A quote the feed marks as not delayed and under two minutes old can read "Live" on a Dossier (the owner's safeguard of 2026-10-21, unchanged). Whether Optic may show such a price as live under Yahoo's terms is a licensing question, not an engineering one. | `static/v2/js/core/marketTime.js` `sessionFreshness` | For counsel and the owner |

## 10. Privacy-relevant changes (Phase 10)

| # | Finding | Where | State |
|---|---|---|---|
| 1 | The brokerage deletion sentence said Optic "deletes everything Optic stored" about a linked brokerage. A saved thesis or Milo answer, the consent record and alert settings stay. It now names what is deleted (accounts, holdings, history, alerts and briefings, with the encryption key) and what is kept, in both apps (BUG-074). The Privacy policy's own deletion section was not changed. | `static/v2/js/pages/brokerage.js`, `static/app.js` | For counsel: whether the Privacy policy should say the same |
| 2 | A reader's watchlist rows, paper book and journal, and retirement plan went to the AI provider with every question asked from those pages. They now go only with a question about them (D-093), so less personal data is sent. | `app/main.py` `_personal_blocks_for` | PASS (tests/test_phase10_hardening.py); the Privacy policy's description of what is sent is question 7 in section 6 |
| 3 | The access log recorded search text and any token, code or state in a query string; mail log lines carried the full address. Both are now redacted or masked. The Privacy policy's sentence on server logs ("what it asked for and when") stays true. | `app/main.py` `_RedactQuery`, `app/auth/mailer.py` | PASS (tests) |
| 4 | No tracking was added. ANALYTICS_REVIEW.md proposes first-party counts with no conversation text or account details; building them needs Privacy wording and counsel (BL-02). | ANALYTICS_REVIEW.md | Not built; for the owner and counsel |

