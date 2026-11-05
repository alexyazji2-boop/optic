# Handoff 10: Guided Investigation ("Investigate this company")

Branch `handoff-10-guided-investigation`. It depends on Handoffs 1 (verified figures), 5 (the library), 6 (ticker
context) and 9 (the events timeline), which are four open PRs on four branches. So it is cut from
`handoff-10-base`: origin/main with those four branches merged.
- **Merge conflicts resolved:** Handoff 5's `seenAt` against Handoff 1's figure list in Milo's sources line, two pages'
  imports, and two rule sections in the design standard.
- **Suite on the base:** 8,335 passed.

Its PR is based on `handoff-10-base`, so the diff shows this handoff alone; merge #9, #13, #14 and #17 first. Not
deployed.

## What existed, verified first

| The handoff asks to verify | What the code has |
|---|---|
| Multi-step Milo orchestration | None. Deep research (`/api/research`) is one streamed call; the research pack (`desk/research.py`) gathers facts with sources for one chat answer. No checklist, no step persistence. |
| Whether Milo is metered | Yes. Per rolling 24 hours: Free 3, Pro 15 (and 100 in 30 days), Enterprise 4,000; guests need an account (401); a server-wide 300 for free and guests; 30 an hour per address. `GET /api/ai-allowance` says what is left; the Milo panel shows "N of M left". Each `/api/chat` request is one unit (`_spend_guard`). |
| Saved summaries (Handoff 5) | `saved_research` rows by kind (company, comparison, conversation, sheet); a body only for conversations; PATCH renames only. |
| Registry figures (Handoff 1) | Nine figures (net margin FY and TTM, forward P/E, free and operating cash flow FY and TTM, net debt, net debt with leases), each with inputs, period, as-of date and source; `figures.for_ticker`. No revenue or growth figure. |
| Ticker context (Handoff 6) | The panel sends `context.focus` with the Dossier section; the server checks it (`research_focus`). |
| Segments and KPIs ("Top 25 #12") | `/api/segments` has revenue and operating income by segment, product and geography from the filings; `kpis` is always null, and its note says operating KPIs are not tagged in filings. No KPI picks exist. |
| Peers ("Top 25 #14") | The valuation workspace's `comps`: the industry's largest companies within 25 times the company's size (eight closest), each multiple's peer median and quartiles, how many peers had one; Yahoo Finance, trailing twelve months. |
| Recent events (Handoff 9) | `timeline.cached` per ticker and period. |

## What was built

**`app/investigation.py`**
- **The six steps:** fixed, each with what it reads and what it asks.
- **One gatherer per step:** the facts it may use, numbered (F1, F2 and so on), each with its period, as-of date and source. What its sources did not have goes under `missing`.
  - Step 2 takes the registry's figures and the inputs they are worked out from, and nothing else. The registry has no growth figure, which the step says rather than computing one.
  - A segment's share of revenue, a count of the timeline's insider trades or a peer-dispersion ratio is Optic's own working, with its formula.
- **The model call** (`answer`) is one per step, through `ai._ask`, one of the app's three policy points (a guard test holds every model call to them):
  - Milo's model (`PULSE_MODEL`), his prompt and the advice policy, plus a block that says: use only the facts, cite them, compute nothing, say what is not available, describe rather than advise.
  - `_ask` applies the policy to the reply and records the call in the cost ledger as `investigation`. It now also notes how many sentences it removed (`ai.last_removed()`), so the step can say so.
  - No tools, and a 2-minute limit.
- **The check** (`check`) reads the answer's figures:
  - A figure that matches a fact as written, or rounded from it, stays.
  - A sentence with a figure that matches no fact is taken out and listed under "Could not verify".
  - Dates, years, fiscal labels and small counts are not figures.
- **A step with no facts** makes no call, spends nothing and says "Not reported".
- **Keeping it:**
  - a draft row in the library (kind `investigation`) when the reader starts, signed in;
  - updated as each step finishes;
  - marked saved on Save to library.
  - The reader's edits and notes are kept beside the facts, which are never edited.

**Routes (`app/main.py`)**

| Route | What it does |
|---|---|
| `GET /api/investigate/{t}/plan` | The steps, the most it can cost against the reader's allowance, the longest it can take, and whether it will be kept. Spends nothing. |
| `POST /api/investigate/{t}` | Starts one, in the reader's order and skips. Keeps a draft when signed in; when the library is full it says it is not kept. |
| `POST /api/investigate/{t}/step` | One step: facts, then a charge to the allowance (`_spend_guard`, counted as `investigation`) only if Milo is asked, then the answer and the check. Stored into the draft. A model failure is the step's ("Milo did not answer this step", in Milo's own words for the error); an allowance refusal is the usual 429 or 401. |
| `GET` and `PATCH /api/investigate/item/{id}` | Read or change one kept investigation: edits, notes, name, skips, stopped, saved. Ownership as in Handoff 5: another account gets 404. |

**The library (`app/library.py`, `core/library.js`, `pages/saved.js`)**
- **The kind:** a new `investigation` kind, listed, renamed and deleted like the rest.
- **Not POST:** `POST /api/library` refuses it, since an investigation is kept by its own page.
- **In Saved research:** it shows "Draft: 3 of 6 steps done", "Partial: …" or "Complete: …", and opens at `#/SYM/investigate?saved=<id>`.

**The page (`pages/investigate.js`, `#/SYM/investigate`)**
- **The plan:**
  - each step to include or skip and to move up or down, with what it reads;
  - "Before you start": steps, Milo usage ("Uses up to 6 assistant messages… You have 12 left on the Pro plan"), time ("6 steps take at most 12 minutes") and whether it is kept.
  - Start is the confirmation and names the cost. It is off, with the reason, when the allowance cannot cover the steps.
- **Running:**
  - The steps run one at a time with a progress line, each with its state in words.
  - Stop cancels the running step; Continue runs what is left; Skip, Retry and Run again are per step. A failed step leaves the rest.
- **Each step shows:**
  - Milo's text, with each figure's fact cited;
  - Optic's verified figures as a table (definition, formula, period, as-of date, source number);
  - "Could not verify" as its own list;
  - the numbered sources.
- **The summary:**
  - complete or "Partial", naming what was skipped, failed or not run;
  - each step's text, which the reader can edit, and their notes;
  - every step's could-not-verify items;
  - all the sources once;
  - the disclaimer.
  - Actions: Save to library, Edit summary, and Ask a follow-up, which opens Milo on this page with the investigation in context. The context bar reads "Researching AAPL · Investigation".
- **On a phone**, the steps are a progress list with the current one open.
- **Entry points:** "Investigate this company" in the Dossier's ⋯ menu on every tab, and a section of that name on the Overview after the analysis.
- **Navigation:** the router (`investigate` like `sheet`), the app's page map, and Milo's `DOSSIER` set and section words (client `pageLabel`, server `_CTX_SECTIONS` and the header's wording).

## Acceptance tests (Handoff 10)

`tests/test_guided_investigation.py` (12 tests). Every source is stood in, and so is the model, through Milo's own
client; the allowance is the real one.

- **AAPL completes all six steps with per-step sources and a saved summary; a skipped step gives a coherent partial
  summary labelled as such.** `test_acceptance_1_*`:
  - six steps, six calls on Milo's model and prompt;
  - every fact naming a listed source;
  - every answer citing its facts;
  - kept as a draft, then saved and listed in the library as a complete investigation;
  - the summary with all six steps and the sources.
  - With Peers skipped: "Partial. 5 of 6 steps done. Skipped: Peers…", and no Peers section.
- **"Could not verify" items are in their own section, never mixed with verified figures.** `test_acceptance_2_*`:
  - the model's "about 12% of sales" sentence is out of every answer and in each list with its figure;
  - what the sources lacked is listed too (forward P/E, growth, KPIs, the failed analyst feed);
  - step 2's facts are registry figures and their inputs only;
  - drawn: the table before the heading, the sentence only after it;
  - the checker on its own.
- **A mid-investigation failure keeps the completed steps and allows retry.** `test_acceptance_3_*`:
  - step 3 failing, the steps after it still running;
  - the draft keeping the five;
  - the page showing Retry and "The other steps are unaffected";
  - retried, the investigation whole.
- **Usage, when metered, is shown before starting.** `test_acceptance_4_*`:
  - a Free account (3 left): "Uses up to 6 assistant messages… You have 3 left on the Free plan", and Start off with the reason;
  - three steps fit;
  - a guest is told to sign in;
  - an unmetered account is told so;
  - and the server charges the same way: the fourth step is a 429, the three kept.
- **Edge cases:**
  - a fund with none of the figures: every step "Not reported", no call, nothing spent;
  - another account gets 404;
  - a ticker mismatch gets 409;
  - the library refuses POSTing an investigation;
  - edits change the words, never the facts;
  - the risk step turns the earlier "could not verify" into questions, with Optic's own segment share;
  - advice is removed as from every Milo answer;
  - Saved research's wording and the address;
  - a follow-up's context, on the client and the server;
  - the entry points and one gold action at a time.

## Live check, 2026-11-04

A local server on this branch, the real data sources (SEC EDGAR, Yahoo Finance, the House archive), the local test account (Enterprise) and a stand-in model that answers each step from its facts (no key, nothing spent).

- **The plan:** six steps, "You have 3989 left on the Enterprise plan", "6 steps take at most 12 minutes", kept as a draft.
- **The run:** one step at a time, in about 29 seconds.
  - Step 3 failed on purpose (an overloaded API, retried by the client and then given up) while the others finished.
  - Retry completed it: "Complete: all 6 steps."
- **Financial health:** Apple's fiscal 2026 registry figures (net margin 27.6%, operating cash flow $145.1B, free cash flow $136.1B, net debt $24.8B), each with its inputs, period, as-of date and SEC source.
  - "Could not verify" held the registry's missing growth figure and the stand-in's invented "12% of sales" sentence, which was not in the text.
- **Saved:** "Saved to Saved research as “Investigation of AAPL, Nov 4, 2026”", listed as "Complete: 6 of 6 steps done".
  - Edits and a note were kept, the facts unchanged.
  - Reloading the saved address resumed it.
- **Reorder, skip, stop:**
  - Risks moved above Recent events and Peers skipped: "Start investigation, up to 5 messages".
  - Stop during step 2, then "Continue, up to 4 messages".
  - The summary: "Partial. 5 of 6 steps done. Skipped: Peers."
- **Ask a follow-up:** opened Milo with "Researching AAPL · Investigation" and the question box empty.
- **Phone, 390 and 375 by 549:** the progress list with one step open, 44 px controls, nothing sideways. The Overview's new section did not move the header.

## Decisions for review

1. **The base branch.** The four dependencies are separate PRs, so this is built on their merge, `handoff-10-base`, pushed for the PR's base only.
2. **The steps' facts are gathered by Optic, not looked up by Milo.** Each step answers from a fixed set of numbered facts, so the verified list is Optic's and the check is exact. No tools, as the handoff asks: "one grounded Milo call per step".
3. **A sentence with an unmatched figure is moved, not marked.** The handoff asks that "could not verify" never be mixed with verified figures; a marked sentence would still sit in the text.
4. **Drafts are kept as the steps run.** Handoff 5's rule is that nothing is saved without a press; here the press is Start, the plan says it is kept, and Save to library marks it saved. Without it, a failure or leaving the page would lose the steps, which the handoff rules out.
5. **Each step that asks Milo is one assistant message**, charged before the call like a question, so a failed step still counts; the plan says so. A step with no facts costs nothing.
6. **Peers, segments and events are the existing sources**, said with their own limits (the peer rule and its n, the segments' periods, the timeline's reach). Industry KPI picks ("Top 25 #12") do not exist, which step 3 says.
7. **The Overview's entry is a section after the analysis**, not a button in the tab row, where it pushed the analysis toggle onto a second line on a desktop.

## Found and not fixed here

1. **A stopped step still finishes on the server** if the model was already answering, and is then in the draft. Stop cancels the page's wait and marks the step stopped.
2. **Steps are not timed in production**, so the time line states the 2-minute limit per step rather than a typical time.
3. **The investigation is not a Milo conversation.** A follow-up opens the panel with the investigation as context; the conversation and the investigation are saved separately.
