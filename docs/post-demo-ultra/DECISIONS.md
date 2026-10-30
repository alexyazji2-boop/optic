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
*Correction, Phase 04:* the "Home's search box" this names was in a Home page that had not been routed since the
workspace became Home; no reader could reach it. Home's search is the top bar's palette, which this resolver also
serves. The unrouted page was removed (D-021), and the test that pinned its search box now checks the Dossier start.

**D-019 (Phase 04) What a page shows and how it is explained are two settings.** Density is Simple or Advanced, one
state of its own (`prefs.density()`), stored on Classic's key `optic.mode.v1` with Classic's values (`simple`,
`pro`); Classic declares that key and no longer reads it, so nothing conflicts. The Dossier's "Show advanced analysis",
the sections' folds (`ui/sections.js`) and Home's panel set follow density; the knowledge level (`optic.knowledge.v1`)
sets Milo's language only, through Settings' "Advanced answers from Milo" until Phase 05's slider. A reader who never
set density gets it once from the knowledge level (Advanced or above means Advanced), so anyone who had turned on
"Show advanced analysis" (which used to write the knowledge level) keeps the sections they saw; after that the two
never move each other (BUG-002). Directive 04 section 7 allowed per-feature disclosure instead if a global mode would
complicate the architecture; it did not, because the folds already had one switch point.

**D-020 (Phase 04) Home opens a smaller set of panels in Simple.** Each preset has a Simple set: Market Overview shows
the index strip, the linked quote, the watchlist, What matters today, the Desk and the portfolio (6 of 13); Options
Research shows the quote, watchlist, contracts and volatility (4 of 7); Long-Term Investing shows the quote,
watchlist, business, valuation and portfolio (5 of 8); My Desk starts as Market Overview. The other panels are hidden, not removed: Add panel brings each back, Advanced shows the whole
preset, and a layout the reader has changed is kept in either view. Chosen by what a first visit needs (what moved,
what is scheduled, one company, the reader's own names) against BUG-005's first visit: 12 panels, 187 controls.

**D-021 (Phase 04) The unrouted Home page is removed, not kept as a fallback.** `pages/home.js` still held the
standalone Home page from before the workspace became Home: its render, loaders, handlers, welcome card, starters,
market strip and expected-move scene, about 330 lines no route reached. It had been edited as if live (Phase 03
changed its search box), which is the risk registry B X-2 named. Every piece a reader can see lives in the workspace
already (greeting, What matters today, the Desk, the portfolio, the starters in the first-visit card, the index strip
panel, the expected-move panel), so nothing visible was lost. The workspace's handlers for controls nothing draws
(the knowledge-level buttons, "See your Home", the knowledge select and the loader that fetched their choices on
every first visit and repainted every panel) went with it. Their styles in pages.css remain; removing unused CSS is
left for a separate pass because selectors are shared.

**D-022 (Phase 04) Measurements count only what a reader can see.** Chrome 152 gives the contents of a closed fold a
layout box (`::details-content` is `content-visibility: hidden`), so the first version of the Phase 04 density and
dead-click tools counted folded text as visible and pressed folded controls (SPY's key-figure terms, the Dossier's
More menu). Both tools now also require `checkVisibility()`. The "before" measurement was taken again with the
corrected probe; the first run is kept, marked superseded, to show the size of the error (NVDA's visible words: 4,749
counted, 1,417 visible). No figure from the flawed run is reported.

**D-023 (Phase 04) In-page names follow the writing guidelines; navigation names wait for the owner.** Section
headings, in-page tabs, labels and help text were changed where WRITING_GUIDELINES.md calls for it (one model, one
name; a word that describes the whole grade). The rail's sections and items, their fly-outs and the phone bar were
reviewed and left as they are: SIMPLICITY_AUDIT.md lists proposed renames for the owner's yes (the owner's standing
rule; a rename was reverted on 2026-10-11 for lack of one).

**D-024 (Phase 04) The liquidity words change on the server, so Classic shows them too.** The grade's words come from
`app/analytics/liquidity.py` and both apps read them from the same API. "Tight" and "Wide" named the spread when the
grade also weighs open interest and volume; "Liquid" and "Thin" describe the whole grade in either app. The grade
keys (`good`, `fair`, `poor`, `not_tradable`) and every threshold are unchanged.

**D-025 (Phase 04) Spacing and headline sizes are normalised in Phase 10, not here.** Directive 04 section 9 asks for
an audit and for shared components and tokens. Directive 10 section 4 names "inconsistent padding", "uneven
margins" and "inconsistent text sizes" for every route. Phase 04 audited them and uses the tokens in everything it
added. It did not snap the existing literals: 1,844 spacing values in pages.css, components.css and base.css, 835 of
them off the 4px scale (6, 10, 14 and 18 px most often), and the headline figures' per-component sizes. Snapping them
re-spaces every page, which then needs a visual review of every route at four sizes. Doing that here and again in
Phase 10 would review the same pages twice. The counts and the design standard's list are Phase 10's input
(SIMPLICITY_AUDIT.md section 9).


**D-026 (Phase 05) The five levels carry the directive's names.** The ladder had five modes named for the
explanation (Simple, Financially Literate, Advanced, Professional, Adaptive); the code said the labels described
the explanation rather than the reader. Directive 05 names five levels for the reader (New to Markets, Beginner,
Intermediate, Advanced, Expert) with a style for each, so those names and styles replace the old ones
(`app/knowledge.py`, the one place the styles are written). Old ids keep working: `simple` reads as New to Markets,
`literate` as Intermediate, `professional` as Expert, in the server, Classic and v2, and a stored old id is rewritten
once so both apps read the same value. Classic's panel ladder keeps its four rungs: New to Markets and Beginner share
Simple's, so no Classic layout moves.

**D-027 (Phase 05) Adaptive is retired.** Adaptive judged the depth from each question. It is not one of the five
positions, and a slider with a sixth hidden mode would not show the reader what they get. A stored `adaptive` reads
as Intermediate, where its layout already sat, and the reader's chosen level is always the one used
(`knowledge.resolve_for_answer` returns it; the name is kept for its callers).

**D-028 (Phase 05) One preference, with one rule for the account.** The value is Classic's key
`optic.knowledge.v1` in the browser and `user_preferences.knowledge_level` for a signed-in reader (migration 19,
additive: one nullable column; unknown values are dropped, old ids mapped). The rule, in v2 (`core/store.js`) and
Classic (`components/knowledge.js`) alike:
- At sign-in, an account that has a level wins and is written to the browser without being sent back.
- An account that never chose takes the level this browser chose, if it chose one.
- Each change made while signed in is saved to the account. A save that fails keeps the level in the browser,
  and the slider says so. The failure is remembered (`optic.knowledge.pending.v1`) with the unsaved level itself, the
  account, and the version of its preferences this browser last saw (`updated_at`, now returned with the preferences
  and never set by a client). At the next load the unsaved level is sent up if nothing has changed the account since,
  and yields to the account's newer level if something has. Versions are compared, never clocks. The entry is a
  personal key (both apps' PERSONAL_KEYS), so it is shelved with the account's other things when someone else uses
  the browser, and it carries its own level because the shared level setting may have changed in between.
- A guest's level lives in the browser only. Where storage is refused (private mode), the default is used and
  nothing breaks.

The session's own answer (`/api/auth/me`) already carries the preferences, so v2 asks for them separately only when
it does not. Density stays its own setting (D-019): the slider never changes which panels a page shows.

**D-029 (Phase 05) Shared texts are written once; per-reader texts take the level.** Directive 05 section 6 asks
that new answers use the new level, that existing content can be re-explained cheaply, that history is never
silently changed and that API costs are avoided. So:
- **Per-reader writers take the level:** Milo, deep research and the written portfolio briefing (both apps). The
  briefing is kept per figures and per level. A write-up says which level it was worded for. When the reader's level
  has moved, the page says "an earlier write-up was worded for X; this one would be for Y", and nothing is written
  until the reader asks.
- **Shared texts stay as written:** the Read, the Desk, Sector and Index Reads, pre-earnings briefs and editions are
  written once for every reader, in the Intermediate register, so a level never costs another model call. A reader at
  another level gets one "Explain it for X" press, which drafts a Milo question holding the text. Nothing is sent
  until the reader presses Send.
- **Milo's history keeps each answer's level.** A later level change adds a note that earlier answers stay as they
  were written, and offers "Ask again for X" as a draft. No answer is rewritten or sent again.

**D-030 (Phase 05) Rule-written text follows the glossary policy; Phase 06 builds the Simple Analysis on it.**
Text written by fixed rules (the Overview, chart readings, the Options and Earnings notes) cannot be reworded per
level without five hand-written versions of every sentence. The level decides how its terms are explained instead:
- **New to Markets:** a term's definition sits in the sentence, from the glossary's own first sentence (up to 140
  characters).
- **Beginner to Advanced:** the term is marked and explains itself when pressed.
- **Expert:** no marks.

A definition joins prose only. A term in a table cell or a figure's label keeps its mark, so data rows keep their
shape (directive 05 section 4). Beginner, Intermediate and Advanced therefore read alike on rule-written text. Directive 06 section 2 rebuilds the
Dossier's Simple Analysis and requires it to use the reader's level; that is where the Dossier's rule-written
wording gets level-specific text, built on this preference.

**D-031 (Phase 05) The first-visit question is asked again, in Home's first-visit card.** v2 had asked "How should
Optic speak to you?" on Home (de6b20b, 48e073d) and moved the level to Settings only on 2026-10-19 (22b2cc7); Phase 04
removed the handlers left behind (D-021). Directive 05 restores Classic's homepage question (Classic: `app.js`
`knowledgeOnboardingHTML`, 41eec2f, 2026-09-14; the levels in `components/knowledge.js`, 194bb3d). It returns as the
compact slider inside the card a first visit already shows: no modal, no extra card, dismissed with the card. The
same slider is in Settings and in Milo's Response settings, where Milo's own Level select used to be.

**D-032 (Phase 05) Chart studies are defined in the server's own words.** The Chart page's explanations are its
studies' readings under the chart. The glossary had no entry for eight of them, so New to Markets defined none. The
entries added are the server's description of what it computes (`app/analytics/indicators.py`, CATALOGUE
"represents"), word for word. They go into both glossaries, which must stay identical (tests/test_v2_chart_widgets.py),
so Classic's term tips gain them too. A test keeps them equal to the server's text.

**D-033 (Phase 05) The privacy text names the stored level; its date is the owner's.** The Privacy page lists what
Optic keeps with an account. The level is now one of those things, so the list says so. The page's rule is that a
change moves EFFECTIVE and a significant one is announced first. Whether this addition is significant, and whether it
moves the date, is for the owner and counsel (BLOCKERS BL-02). EFFECTIVE is unchanged and COMPLIANCE_REVIEW section 8
carries the item.

**D-034 (Phase 05) Five meaningfully different answers are measured on a proxy, not claimed for production.** The
key on this machine is refused (BL-01). Optic's own request for one question on one fixed context was built at each
level. Each was answered by a separate Sonnet 5.5 agent (Milo's production model), given that one request under a
neutral file name, and the answers were measured by a deterministic script (TEST_RESULTS, Phase 05). That shows what
the prompts do to that model. It is not Optic's API path, and it is reported as a proxy.

**D-035 (Phase 06) The analysis view is the density setting.** Directive 06 asks for one authoritative mode state,
kept apart from the analysis data. Phase 04 had already made "how much a page shows" one setting of its own
(`optic.mode.v1`, D-019), and Settings already offers it. The Overview's Simple and Advanced views are that setting,
read in one place (`paint`: `prefs.advancedOn()`). The button sets it, and its label names the other view. No second
key was added, so the button and Settings can never disagree. The data (`D`, one per visit) is separate from the
view, so a swap redraws from what is loaded and fetches nothing. Classic's Overview, still served at `/classic`,
keeps its own switch and layout: the rebuilt Dossier is v2's, which every reader gets at `/`.

**D-036 (Phase 06) The Simple Analysis is written by rules, at the reader's level.** A default view that called a
model would cost money on every visit, and the owner's rule is no paid call on load. So the three answers are fixed
rules over the payloads the page already loads (`pages/overview-simple.js`), in five registers, one per knowledge
level. The registers change the words, how much is explained and how dense the figures are. They never change a
figure, and every caveat is said at every level (a risk's reason is kept even at Expert, because for some risks it is
the caveat). At New to Markets and Beginner the section explains its own terms, so the page's glossary marks stay off
it; at the other levels the marks work as elsewhere. This is where the Dossier's rule-written text gets
level-specific wording (D-030), and R05-05 moves to PASS on it.

**D-037 (Phase 06) The Advanced Analysis is Classic's research, word for word, in separate sections.** The four
questions, the Optic Score, the bull case and the bear case, Taken together, Optic's read, What changed lately, the
thesis check, What to look at next, the rest of the ticker, the filings and the method keep their words. Four things
changed in how they are put together:
- The Advanced research fold is gone. Its blocks are sections of their own, so the jump strip lists them.
- Key figures (7) and Key stats (18) were the same figures twice; they are one Key statistics section.
- The bull case and the bear case are open rather than folded behind a count.
- The headlines block is gone; the About section's Latest headlines already holds them.

**D-038 (Phase 06) The swap is a quick fade that keeps the reader's place.** A press replaces the analysis area with
the other view. The new view fades in over `--m-content` (150 ms) with `--ease-out`, opacity only, so nothing moves,
and the shared reduced-motion rules switch the fade off. A reader who was inside the analysis area is shown the new
view from its start, under the sticky header (the jump strip is measured as it is after the swap). A reader above it
stays where they are. Focus stays on the button, and a status line says which view is showing.

**D-039 (Phase 06) A response is drawn only into the visit that asked for it.** Every request of an Overview visit
carries that visit's token, and its answer is applied only while that visit is current, which includes the stage
read's retry and the track record's late load. Checking the symbol alone let an earlier visit to the same ticker draw
into a later one (BUG-095). The page's handlers are wired once per page element; Try again re-rendered into the same
element and doubled them (BUG-094).

**D-040 (Phase 06) The Simple Analysis follows the header's price.** The header refreshes its price every 20 seconds
through the trading day. The Simple Analysis says the same day's move and last trade, so it is redrawn in place,
alone, when the quote it was written from has moved on. Without that, the two would disagree on one screen (BUG-096).
The Advanced Analysis has no sentence that depends on the live quote.

**D-041 (Phase 06) The arrival focus waits for the search.** The shell focuses each new page's heading one frame
after it arrives, so a screen reader hears where it landed. When the search or a drawer is open, it now leaves focus
where the reader put it (BUG-093). The Overview keeps a focused heading focused through its redraws (BUG-097). Both
were found by Phase 03's 20-search scenario. Before the fix one run missed 3 of 40 searches in a row; after it, none
of 120 missed.

**D-042 (Phase 07) The safety gate's cadence stays.** Phase 02's gate (`app/ai_policy.py` StreamGate) releases the
answer in whole sentences, so that no sentence that breaks the advice policy is ever shown, even for a moment. An
answer therefore arrives in about 20 steps of a sentence each: 51 characters at the median, 248 ms apart (p90 416).
That is smoother than it sounds (each step is drawn in place), and the two ways to make it finer are both ruled out:
streaming text before the gate has read it, or holding sentences back to reveal them a character at a time (directive
07: "Do not fake streaming"). The first visible word waits for the first complete sentence; in the emulation the gate
held text for up to 747 ms. The trade-off is recorded here and in STREAMING_PIPELINE.md.

**D-043 (Phase 07) The transport stays, the response starts at once, and the server times every answer.** Server-sent
events read with `fetch` were already genuine text-delta streaming (`messages.stream`). They suit a one-way answer
with a POST body, cookies and a CSRF header, and nothing was replaced. What changed:
- The chat route returns its stream before it gathers the page's figures, and says so first (`status: gathering`,
  "Reading NVDA's figures"). A failure while gathering is an error event the reader is shown ("Milo could not gather
  the figures for this question. Send it again in a moment."), without the internals.
- Each model round says `writing` ("Working out the answer"). A tool's line lasts only while the tool runs.
- `StreamClock` records, from the request's arrival: the context ready, the first model event, the first model text,
  the first text the gate let out, each tool's time, the rounds, the text events and the longest gate hold. It is sent
  with `done` and logged as `milo timing:`, so production's first real answers give the real model's figures.
- The route yields for 5 ms after its first line, so the line leaves before the context work starts. Parts of that
  work hold the event loop (BUG-113, Phase 10).

**D-044 (Phase 07) An answer is drawn as it arrives, and a finished paragraph once.** `paintLive` appends the finished
part of the answer and draws only the paragraph still arriving, at most once a frame. The answer's chart is made and
drawn once.
- `settledEnd` (core/milo-text.js) ends the finished part only where drawing in pieces gives what drawing the whole
  answer gives. Never inside a code block or a bold run. Never before a list item, because mdLite joins a list to the
  paragraph above it. Never before a line too short to tell, and never into the follow-ups.
- The parity is tested a character at a time over answers with every kind of markdown Milo writes, and in the
  browser (C03).
- The arriving paragraph is drawn as markdown (`streamingHTML`): bold or a code block still open is closed for now,
  and a marker only begun waits.
- The limit of two action cards and two figures counts the whole answer (`seen`).
- At the end the answer is finished in place (`paintFinished`): what is on screen stays, and only the parts around
  the text are drawn.

**D-045 (Phase 07) Following the end is the reader's choice.** New output follows a reader at the end of the
conversation and never one who has moved up. Following is decided from the reader's own scrolling (`noteScroll`):
- Optic only ever scrolls to the end, so a view that moved up was moved by the reader.
- A wheel turned up stops the following before the view moves.
- Within 60 px of the end is the end again.
- A chart or a figure drawn later, and the log getting shorter (the composer growing, a phone's keyboard), keep a
  following reader at the end (`keepEnd`, a ResizeObserver).
"Latest" appears 160 px from the end; it scrolls there and follows again. The 120 px allowance measured after each
frame's changes is gone: it left a following reader behind and pulled a reader 40 px up back down (BUG-100,
BUG-101). The panel opens again where the reader was: at the end, or at the place they had scrolled up to (BUG-099).

**D-046 (Phase 07) Close, New conversation and Delete while Milo answers.** The answer being written belongs to the
conversation on screen.
- **Close (X):** closes the panel and the answer carries on behind it. It is saved whole when it ends. Opening the
  panel again shows it, still arriving if it is (C13, C14).
- **New conversation, and Conversation history:** wait for the answer. They stay reachable (aria-disabled, not
  disabled). A press says "Milo is still answering. Stop the answer first, then start a new conversation" (or "then
  open your history"). Stop is beside the box. With history waiting, nothing is drawn over the list, and nothing can
  open another conversation into the answer's place (BUG-102, BUG-104).
- **Delete:** while Milo answers, the open conversation cannot be deleted; another can. A deleted conversation stays
  deleted (BUG-103).
- **Repeats:** New conversation pressed six times makes no conversations (only one with a message is saved). It
  keeps the draft and clears the conversation's context, its previous ticker included.
- Close is the X, New conversation the compose icon, Delete the bin beside each saved conversation in history. They
  are three different controls in three places.

**D-047 (Phase 07) Conversations are kept in this browser, apart for each account.** Milo's history is the classic
app's key `optic.pulse.history.v1`. It is a personal key, read and written only while this browser holds the
signed-in person's things (`core/device.js` holds()). Signing out shelves it, and another account or a guest starts
empty. The panel says so: "Saved in this browser only, never uploaded, and kept apart for each account."
- **Checked (C18):** the demo account, then another account, then a guest, then the demo account again, on one
  browser. Each saw only its own. The guest's key held no one else's text. Coming back restored the demo account's
  14 conversations.
- **Ids:** random (`c` + time + random), and one conversation updated stays one entry (C16).
- **A deleted conversation:** removed from the list, and from the screen when it is the open one (C17).
- **A missing or unreadable list** reads as empty. A full one keeps the newest half.
- **Server-side history, not built.** It would need: a `conversations` table keyed by the user id with messages
  stored per row; every read and write checked against the session's user (no id alone opens anything); random,
  unguessable ids; real deletion, with the account's deletion and export; a retention period; and a Privacy policy
  change, since the policy now says conversations are not kept (counsel, BL-02). The owner decides whether it is
  wanted.

**D-048 (Phase 07) A small phone upright keeps room for the conversation.** At 860 px wide or less and 600 px tall or
less (an iPhone SE's Safari is 375 by 549), the panel hides the subtitle ("Research assistant") and the attached line
(the context bar names what is attached). It also hides the example question and takes the persona row's padding.
The data line ("Prices are delayed up to 15 minutes. Not financial advice.") and every control stay. After an answer
the conversation had 36 px; it now has 125 px. The tool row (Modes, Search the web, Deep research) still takes two
rows at 375 px. Folding it or the header away is a design decision for the owner, not taken here.

**D-049 (Phase 07) The question's limit is said, and a pasted image is attached.** A question holds 4,000 characters,
as before. When the box is full it says "That is 4,000 characters, the most a question can hold." After a paste that
was cut, it says how many characters were left out. Both appear under the box on every screen size. An image pasted
into the box is attached as a dropped one is, with the same checks. Send with an empty box returns focus to the box
and sends nothing.

