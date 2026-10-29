# Decisions

Each entry: what was decided, why, and what would change it.

**D-001 (setup) Work from production, in its own worktree.** Branch `post-demo-ultra` cut from origin/main
`9fa0f36`, which is what theopticterminal.com serves. The shared checkout's local `main` is 704 commits behind
origin and holds other sessions' uncommitted edits; it is left exactly as it was (master rule: preserve
pre-existing uncommitted changes).

**D-002 (setup) Nothing leaves this machine.** The branch has no upstream and is never pushed. Every phase says
"Do not deploy" and the master rules forbid deploys and production-data changes without explicit
authorization, so the owner's older standing instruction to push finished work does not apply here. The
owner's 2026-10-29 "You have permission to do whatever is necessary for this task" is read as covering local
engineering, local servers, local copies of data, test accounts and fixtures. It is not read as permission to
deploy, push, write production data, link real brokerage accounts or change billing, because the task's own
text excludes those.

**D-003 (setup) The directives are saved verbatim.** The overnight controller says they were saved in the
repository; a search of every checkout, docs folder and Downloads found no copy. They are in `directives/`
exactly as sent, so they survive context compaction. Interpretations go here, never into those files.

**D-005 (Phase 01) v2 is the product under repair; Classic is inventoried at route level.** Every visitor gets
v2 at `/` (OPTIC_DEFAULT_UI=v2 since 2026-10-19); Classic is the fallback at `/classic`, kept until the owner
approves retiring it, and the house rule is to leave Classic's copy alone unless the task is about it
(owner, 2026-10-25). So the registry lists Classic's 26 views and what replaces each in v2, and the crawl
checks Classic for script errors and placeholder text. Server-side changes (AI policy, prompts, data
correctness) reach both front ends and are tested for both.

**D-006 (Phase 01) Other branches' unshipped fixes are inputs, merged only when a phase needs them.** Several
local branches hold work the owner has not shipped (FEATURE_REGISTRY Part 7). A phase that needs one (for
example the Milo portfolio-privacy fix for Phase 02/08, or the Milo evaluation harness for Phase 08) takes
only that change, by cherry-pick or by hand, records the source commit here, and runs the full suite; nothing
is merged wholesale, and nothing leaves this machine.

**D-004 (setup) One phase at a time, nothing left behind.** The owner's sequencing instruction (directive 13)
makes every phase a gate: the next phase starts only when the previous one's requirements are PASS or
BLOCKED / UNVERIFIED for a named external reason.

**D-007 (Phase 01) Visual review done in the main session.** Six subagents running at once hit the account's
session limit at about 02:00 ET; the four still running stopped and nothing ran until 04:50 ET. The registry
agents' files were nearly complete (C's counts and D's Classic map were finished by hand); the two screenshot
reviewers had written nothing, so the visual audit was done here from labelled contact sheets and the crawl's
measurements (FEATURE_REGISTRY Part 8). From now on at most two subagents run at a time.

**D-008 (Phase 02) Earlier owner-requested formats that the advice policy overrides.** Two things the owner had
asked for are changed because the 2026-10-29 directive forbids what they produced, and both are reversible:
(1) Milo's "take on a stock" (owner's HOOD-style take, 2026-10-15) kept its shape but no longer lets Milo say "this
is one I'd happily own for years" or name a peer that "suits the long-term case better": the long-term part is now
the case for and against, and a peer is a comparison of business models. (2) "Recommend me some swings" no longer
gets a ranked shortlist with each name's bias; it gets names meeting stated screen criteria, presented as a research
starting list, with the panel's fixed line that Milo does not pick investments.

**D-009 (Phase 02) Open owner decision O04 resolved conservatively.** The Overview's pre-earnings evidence no longer
says rising estimates "tend to precede results above them" (unsupported by Optic's validation programme) or that a
risk-off market "tends to make reactions to good news smaller"; the measured facts stay. Reversible in
app/research/earnings_view.py.

**D-010 (Phase 02) Deterministic trade plans are kept as research, not deleted.** The swing setup, the options
entry planner, the contract picker and the long-term levels are core research features. Their data and arithmetic
stay; what changed is how they are said: model levels with their assumptions instead of entries, stops, targets
and sizes for the reader, and no sizing outputs at all (the swing plan's share-count example, the options sizing
sentence, Retirement's per-fund contribution amounts and per-stock suggested weights are withheld). The
internal labels ("Avoid", "High Conviction", "Attractive") still drive the logic; readers are told what the rules
found (app/research/words.py, static/v2/js/core/research-words.js). Retirement's contribution plan is kept in
code (`_rebalance_with_new_money`) so it can return after counsel review.

**D-011 (Phase 02) Classic's copy is changed where it instructs, and nowhere else.** The house rule (D-005) leaves
Classic's copy alone unless the task is about it; this phase is about every surface that tells a reader what to do,
and Classic is one press away at `/classic`. So its options entry panel and ideas headings, labels and heading help,
the Retirement tables, the pre-trade checklist, the stop-loss glossary entry, the breakout heading help, the Options
follow-up chips, the saved-research starter and the earnings brief's stance label now say what v2 says, and Classic
renders Milo's policy notice and removal note. Nothing else in Classic was restyled or reworded.

**D-012 (Phase 02) Milo's stream is held back by one sentence.** The end-of-stream amend alone let a reader watch an
advice sentence appear and then be replaced. The stream gate (`ai_policy.StreamGate`) sends each sentence once its end
has arrived and never sends one that breaks the policy. The cost is that text arrives a sentence at a time rather than
word by word; Phase 07 may tune how that looks, but not remove the gate.

**D-013 (Phase 02) The paper book's alerts say they are simulated.** The public inbox called each simulated position
a "New trade idea" with "Entry, stop, target". It is now "Paper book opened a position", a simulated position in
Optic's paper book and not a recommendation. Whether the book should be public at all is counsel question Q4.

**D-014 (Phase 02) Retirement shows no dollars of the reader's contribution per fund.** Withholding the contribution
plan (D-010) left the same plan in the allocation table's "Per year" column (weight times the reader's contribution).
The column is gone in v2 and Classic and the server no longer computes it; the example's weights stay.

**D-015 (Phase 02) The output check is measured on sentences its author has not seen.** The first version was tuned
one phrase at a time and caught 5 of 15 held-out advice sentences. It was rebuilt as one action vocabulary over five
sentence shapes, and its rates are measured on a set written by a separate agent that was told not to read the code.
Sets used for tuning become regression tests and are never reported as a measure.

**D-016 (Phase 03) One precedence for "which symbol", and where pages keep their own.** Wherever a page needs a
symbol the reader did not give: (1) the address's symbol; (2) the company opened on this visit (memory only:
`store.openedNow()`), for the palette's places and the sidebar's Dossier link; (3) the reader's saved choice where a
page keeps one, which today is only Home's linked panels; (4) SPY (`store.DEFAULT_SYMBOL`). The Recent list and the
watchlist never choose a symbol on their own: they outlive the visit. Intentional exceptions, each with its own
selection: Home's linked panels (the reader's choice, else SPY; they do not follow the Dossier); Compare (its `?t=`
list); the Chart's compare overlay; Watchlist, Alerts and Paper Desk (their own records); Macro, Indices and the
market pages (the whole market, no symbol). Milo takes the page's symbol (`provideContext`) and any symbol the
question names. The palette's Dossier row with no company open goes to the Dossier start page, as the sidebar does
(owner, 2026-10-21).

**D-017 (Phase 03) "Follows <ticker>" is removed; a saved Home ticker is kept only if it was chosen.** The chip on
each linked panel is gone, and so is the behaviour behind it: Home's ticker fell back to the watchlist's first name
or the last company opened, and that fallback was then saved, so Home showed it on every later visit. A company panel
now names its ticker as plain text, keeping a panel on its own ticker stays in the panel's menu, and a ticker is
saved only when the reader chooses it (the box above the panels, a ticker pressed on Home, "Show on Home"), marked
`linkChosen`. Saved workspaces from before carry no such mark, so every reader's Home shows SPY once, including a
reader who had chosen a ticker on purpose; that is the price of telling the two apart, and choosing again keeps it.

**D-018 (Phase 03) One resolver for typed text.** `core/resolve.js` decides what typed text names for the palette,
Home's search box, the Dossier start page and Home's linked-panel box: an exact symbol (share classes in their dashed
form), else a name people use, else a company whose name starts with the word typed; an index, rate, currency,
future or crypto opens its instrument page. A text that names nothing opens the search with it (Home did nothing
before), and a navigation after an awaited search only happens while the reader is still where they typed it.
