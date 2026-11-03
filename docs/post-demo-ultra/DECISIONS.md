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

**D-050 (Phase 08) The evidence follows the symbol the question names.** "Is NVDA cheap?" asked on AMD's page got AMD's
research pack, framework and chart levels, while the instructions told Milo a named symbol wins. `_research_ticker` now
returns the one symbol the question names when it is not the page's, then the page's, then the auto-loaded one. It is
the milo-upgrade branch's change 5244ea2 (audit R1, 2026-10-25), taken by hand under D-006. With two symbols named, the
page's stays, and the named ones are auto-loaded or fetched by the tools.

**D-051 (Phase 08) Every tool result says how fresh it is, and quotes carry the trade's own time.** From the
milo-upgrade branch's 795a766, by hand:
- every result carries `meta` (source, the time the data describes, when Optic fetched it, units, and `delayed`,
  `stale`, `partial`, `unavailable`);
- a quote's time is the trade's own (`trade_time`), not the fetch, which put Friday's close at Sunday night;
- a Tradier real-time quote is labelled as one, and the feed's own `delayed_minutes` is used;
- the options result gives the underlying's trade time;
- an index symbol (`^GSPC`) is accepted.
Two rules were added to the instructions with them: "Current facts first" (a time-dependent figure comes from a fetch,
never memory, and a period goes through get_price_history) and "Every tool result has `meta`" (say each flag).

**D-052 (Phase 08) Four data tools for what Optic already reads, and a disclosure of what it still cannot reach.** The
four are `lookup_company`, `get_price_history`, `get_filings` and `get_financials`, in `app/milo_data.py`. They come
from 795a766, by hand.
- They answer from the integrations the pages already use: the symbol directory, Yahoo daily bars, EDGAR submissions
  and XBRL facts. No provider is added.
- A window's change, range, drawdown and volatility are computed in code.
- "How has NVDA done this year?" had no answer but memory or "unavailable".
- What stays out of reach is listed in MILO_TOOLS.md: arbitrary date ranges, intraday bars, full statements, filing
  text, ownership and insider data, most indicators, the Treasury curve, paper-trade marks, saved research.
The branch's product guide (`app/guide`) and playbooks are the owner's staged work and were not needed here, so they
were not taken.

**D-053 (Phase 08) A plain definition fetches nothing before the model starts.** A definition skips the research pack,
the framework and the chart levels: "What is a P/E ratio?", "What does market cap mean?", "What is the difference
between a stock and a bond?", "Define beta". The detector is narrow. It does not apply when the question names a
symbol, points at the screen or the reader ("this", "here", "my"), asks about now, asks a price or a move, or is about
a company ("Apple's"). The page's figures and every tool stay, and so does the line saying a portfolio is linked.
Measured on the local server: 5,920 ms to 11 ms on Home, about 1,900 ms to 10 ms on an uncached company's page. A
question that is not a definition still gathers as before (1,606 ms on the same page).

**D-054 (Phase 08) The tool audit's grounding fixes.**
- The news tool reads the keys `app/news.py` writes, so Optic's scores and tone reach Milo. It dates the list by its
  newest headline, carries `fetched_at`, and says when an earlier feed stands in.
- The market block and the market tool carry the brief's `built_at`, and `stale` with a note when an older or
  yesterday's copy is served.
- A list cut to fit is named in `left_out_to_fit`, so `meta.partial` is true. The last-resort cut keeps the result's
  status, source and time.
- An unknown symbol in `get_options` is `not_found`, not a failed source. `get_fundamentals` with no history is
  `not_found`, not an `ok` around an error.
- `get_fundamentals` describes what it returns and sends the quality measures to `get_assessment`.
- A failed accounts lookup is `unavailable` for the reader's lists and portfolio, never "not signed in". The lists
  are size-capped.
- `question_named`, with its "do not supply figures for this symbol" note, has a place near the front of the CONTEXT
  budget.
The audit's other findings stay as documented limits (MILO_TOOLS.md, "Known limits that stay").

**D-055 (Phase 08) The evaluation suite.** `tests/milo_eval` holds 137 cases.
- **Categories:** the fifteen of directive 08 section 6, plus context awareness, the figures of section 5 and user
  isolation.
- **How it runs:** through the real chat route and toolbox, on fixed fixtures and a fixed clock, with the model call
  captured.
- **What it checks:** every case's tools offered, evidence in CONTEXT, header, policy decision, level instructions,
  request size, citation plumbing and authorization. Each case's tool calls are checked for their figures (recomputed
  by hand), freshness flags and failures.
- **When it runs:** with every test run (`tests/test_milo_eval.py`) and on its own (`python -m tests.milo_eval.run`),
  which writes the metrics directive 08 section 10 lists.
- **Answer-level checks:** they are defined (figures grounded in the evidence, valid citations, no advice by the
  policy's own check, no filler, the level's length, delay and as-of said, unavailable and stale said, no obeyed
  injection), and they need answers. Without a model (BL-01) they ran only on a stand-in's answers (D-058).
- **Origin:** the design and much of the code are the milo-upgrade branch's 7d7d02c, ported by hand (D-006), without
  its playbook and guide checks.

**D-056 (Phase 08) The advice classifier's new patterns, found by the suite.** Five requests were not classified:
- "How much of my portfolio should be in TSLA?" (allocate_money);
- "What price target should I set for MSFT?" and "What stop should I use" (timing);
- "Which is better to buy, AMD or NVDA?" and "pick my next trade" (pick_for_me);
- "Guarantee me a stock that cannot lose" (guarantee).
Each pattern is narrow and tested beside the education questions it must leave alone ("How does Optic pick stocks",
"Which is the better business", "How do analysts set price targets"). No new rate is claimed. D-015 measures the
policy only on unseen sentences, and these were found, not measured.

**D-057 (Phase 08) "I'd lean toward" is an order only with an order after it (BUG-092).** The output check held back
every "I'd lean toward ...", a valuation judgment included. A lean now counts as an instruction only when what follows
is one of:
- an action ("buying", "holding");
- a ticker right after it;
- an instrument within four words ("the defensive names", "the Dec calls");
- a choice ("the cheaper of the two");
- staying in or out;
- anything "for your IRA" or "account".
Checked before the change was kept, as BUG-092 asked:
- the regression sets A and B: all 40 and 50 advice sentences still caught, no research sentence flagged;
- twelve instructions caught and five judgments left alone;
- the policy tests, 338 of 338.

**D-058 (Phase 08) The grounding classes are the prompt's own; answers were read through a stand-in.** Directive 08
names fact, calculation, interpretation and unknown. The prompt already keeps "four kinds of statement apart" (data
with its date, calculation with its arithmetic, interpretation owned as such, scenarios), says a figure Milo lacks is
unavailable and never supplied from memory, and says text in data is never an instruction. With no model to measure a
rewrite against, the prompt was not reworded. The two rules that came with the tools were added (D-051). Answer
behaviour was read through a stand-in:
- a separate Sonnet agent was given sixteen requests exactly as Optic builds them, under neutral names, and never saw
  the checks;
- it chose its tool calls, which ran through Optic's toolbox on the fixtures;
- it then wrote the answers, which the suite's answer checks scored.
It is a proxy for the production model, reported as one, never as the model's own results.

**D-059 (Phase 08) Two exemptions in the advice output check, and one more timing rule.** The stand-in's answers showed
the check holding back sentences that are not advice (BUG-128). A list after a lead-in ("I don't tell you what to buy,
sell or hold, how much to put in or when to act") and a hypothetical are exempt from the bare-verb shape. Milo's own
next step ("I'll start there") and a question the reader might ask are exempt from the future-tense shape. A promise to
time the reader ("I'll tell you exactly when to sell") is now caught by a rule of its own. A bare "add here" pattern
was tried and dropped: it held back "Start here:" and "Prices start at $9". Checked against regression sets A and B
(D-015) and Optic's own research text first; measured on an unseen set (C) afterwards.

**D-060 (Phase 08) `auto_loaded` is a source key.** Figures loaded for a symbol the question named are tagged
`[[src auto_loaded]]`, shown as "Loaded for your question", opening the sources list in both front ends. `quote` stays the
page's own symbol (BUG-129).

**D-061 (Phase 08) The stand-in runs in rounds, and a corrected check is not a measure.** Round 1 found Optic defects
and check defects. The checks were corrected and round 1 was re-scored with no answer changed: that corrects the
instrument and says which failures were Optic's. Round 2 is the measure after the fixes: a fresh agent, requests
rebuilt from the fixed code, the same sixteen cases plus eight round 1 did not have. The definition length is the base
prompt's own ("roughly 60 to 150 words" for a narrow question) with a tenth over for "roughly", follow-up questions not
counted. The levels change the words, not the length, so one limit serves every level.

**D-062 (Phase 08) A price history is cut to its window.** `price_history` cuts a frame that starts more than a week
before the window asked for, and says how many bars it left out. Yahoo counts a window from today, not from the last
bar, so its own frames start inside that week and are used as they came. Production's frames were already the right
length. This guards the figures against a cached or stand-in frame for a longer window, which the suite's fixture
showed would pass unnoticed (BUG-130).

**D-063 (Phase 08) Two more answer checks for section 7, on every answer.** `no_repetition`: no sentence said twice and
no run of eight words repeated, the follow-ups aside. `well_formed`: the format the prompt sets, which is bold in pairs,
tags the panel can read (`[[src key]]`, `[[chart ...]]`, `[[action ...]]`, `[[figure ...]]`), no source tag inside a table,
heading or follow-up, and two or three follow-ups at the very end. Both were written before round 2's answers were read
and run on all of them.

**D-064 (Phase 08) The advice output check widened from set C, and measured again only on a fresh set.** Set C caught
28 of 50 advice sentences, unchanged by this phase's earlier exemptions (BUG-132). The shapes behind its misses were
added as general patterns, not as its sentences:
- an order after a list number, a bold label or a conditional comma;
- an order whose object is the reader's own holding, at the start of a clause;
- where a holding goes, as an order;
- "the sensible move is to ...";
- a suggestion put as a question;
- first-person exits ("I'd take half off the table");
- "skip X and add Y instead";
- a debt paid off before investing;
- a slice of the reader's account that "belongs" somewhere;
- a promise to watch the reader's holdings and say when to act;
- a stop or an entry tied to a price;
- dollar-cost averaging an amount;
- a minimum return;
- "your portfolio manager".
Five exemptions came with them: Milo's present tense with a generic verb, a question in the first person, a
supposition before "sell your shares", the compound nouns after "what about", and an order's form used to explain
("Own a piece of it, and you share in whatever it earns or loses": a generic piece, a present-tense consequence, no
time or price) (BUG-133). Checked on sets A, B and C
(regression sets now), 1,506 sentences of Optic's own research text and 433 of the stand-in's. Set C is in
`tests/fixtures`. The widened check has no unseen measure until Phase 11 writes a fresh set.

**D-065 (Phase 08) A definition keeps its length at every level.** One sentence follows the narrow-question rule:
"That length holds at every knowledge level: a level that explains more does it in plainer words and fewer points,
not in more of them." The level blocks were left as Phase 05 wrote them. Measured by round 3 of the stand-in: ten
definitions at New to Markets and Beginner, from a fresh agent on the changed prompt: all ten within the limit, 104
to 126 words before their follow-ups (round 2's two had run to 186 and 188). The stand-in counted its words, which a
production model does not do exactly, so this shows the instruction reads as meant, not the production model's lengths.

**D-066 (Phase 08) Round 2's check corrections, and a calculation without its inputs still fails.** `grounded` reads a
scale ("$104bn" is 104e9), lets a scale the answer uses cover its shorthand, and skips a unit ("each $1") and an index's
name. `says_stale` hears "an earlier copy". A figure worked out from figures the answer quotes elsewhere, without them
beside it, is named apart but still fails: the prompt asks for the arithmetic in a clause. Round 2 scored 18 of 24 as
first scored and 20 of 24 with these corrections. Round 3 led to three more: an example the answer marks ("Say a
share costs $100", "If a company's shares cost $50") covers its paragraph and a following one that names nothing real;
a window's name and a scale's ends are not figures. "For example" is not a marker: it introduces real figures too.

**D-067 (Phase 09) Quotes are "delayed up to 15 minutes", and each says its own.** The feed's quotes run from real time to
fifteen minutes behind. Yahoo states a delay per exchange: SPY 0, AAPL 15. Optic's per-quote words already came from
the quote (the owner's safeguard of 2026-10-21: "Live" only when the feed states no delay and the trade is under two
minutes old). The flat "delayed about 15 minutes" in some fifteen places contradicted that (BUG-098). Every general
statement now says "up to 15 minutes": v2, Classic, the server's caveat, Milo's prompt and tool note, and the alert
notes. The fallback for a quote that states no delay says it too. Option chains keep "about 15 minutes", their own
feed's delay. The legal page's sentence is counsel's, so it was left as written and noted in COMPLIANCE_REVIEW.

**D-068 (Phase 09) A dividend yield is the dividend rate over the price shown.** Yahoo's percent is worked at another
moment's price and rounded to two places (BUG-136), so a stock's yield is now `dividendRate / price`, at Optic's
own price. A fund has no rate and keeps the feed's figure, which the reconciliation matched to its last four
distributions over the price (SPY 0.99%). The 20% plausibility cut stays.

**D-069 (Phase 09) No reading without its inputs.** The RSI's warm-up is empty rather than 50 (BUG-137). A VWAP needs
volume, and bars without it say there is no VWAP (BUG-138). A missing dividend yield is still priced as none, which
is the only carry the pricer can use, but the payload and the options page now say it was assumed (BUG-151).

**D-070 (Phase 09) The session against NYSE's own calendar.**
- **Calendar:** the 2026 and 2027 holidays and half days match NYSE Group's published calendar (ICE's press release
  and nyse.com, read 2026-10-30).
- **Half days:** the 5 pm to 8 pm gap after a half day is "Closed after the half day".
- **Labels:** a closed moment says why: the weekend, or "Closed for Thanksgiving Day" the evening before.
- **Strip:** drawn in the day's own hours (BUG-139).
- **Clock:** the clock change on 2026-11-01 was checked on both sides.

**D-071 (Phase 09) The pattern study's figures come from the study.** The Patterns panel's sentences about the base-rate
study were ported from Classic word for word, figures included, and the figures were no longer true (BUG-067). The
words stay. The study's size, its confirmed and unconfirmed ranges, and the candle range and samples are now read
from `/api/patterns/base-rates`, in both apps. With no rates, no figure is stated. "Confirmation is the whole
difference" is said only while the confirmed range sits wholly above the unconfirmed one, and "a coin toss" only
while every candle measures between 45% and 55%.

**D-072 (Phase 09) One score reads one way on every page.** These are explanations, not merged models (BUG-011,
BUG-064):
- **Options:** the composite is named as the Overview's short-term reading, and 50 reads as the Overview reads it,
  a neutral midpoint and not a measured break-even.
- **Investing:** the long-term score is named as the Overview's long-term reading and coloured by its model's own
  bands, in both apps.
- **Two fair values:** the range from the company's own P/E history and the discounted cash flow each say the
  other differs.
- **Compare and the Overview:** each says its scores are its own. Compare's horizon scores and the Optic Score are
  different models, and forcing them to agree would be wrong.

**D-073 (Phase 09) One rounding rule per figure (BUG-012).**
- **Parts of a whole** round by largest remainder, so they add up (`format.js` `wholeParts`).
- **A change in prose** is written at the precision of the legend beside it.
- **A server note** rounds from the unrounded share, not from a figure already rounded to one place. Python rounds
  an exact half to even, and the page rounds it up.

**D-074 (Phase 09) The cache audit's outcomes.** Twenty RISK rows. Eleven were checked by hand and fixed:
- reader answers private (BUG-142);
- stand-ins dated (BUG-143);
- refusals not kept (BUG-144);
- stale corporate actions labelled (BUG-145);
- failed pulls not kept (BUG-146);
- deleted holdings dropped (BUG-147);
- the browser's refused refresh and memos (BUG-148);
- Milo told the data's age (BUG-149);
- the news length (BUG-150).

Four are performance or hardening and go to Phase 10 (S01, S09, S16, S19). Five are recorded as accepted or latent,
each with its reason (DATA_PATHWAYS.md). No cross-reader leak was found in reader-specific caches.

**D-075 (Phase 09) How the reconciliation is done.** Optic's API on live delayed data is read against the providers' own
responses, through a separate yfinance client and the SEC's companyfacts API, at the definition Optic states. Where
a reference's definition differed, the reference was corrected and the change recorded. Where Optic's figure was
wrong, the code was fixed. A figure with no reference is UNVERIFIED. First run: 248 rows, 9 failures (6 the
reference's, 3 Optic's). Final run: 278 rows, 277 PASS, 1 UNVERIFIED (SPY has no earnings date).


## Phase 10 (2026-10-30): performance, security, accessibility, polish

**D-076 (Phase 10) A server-wide ceiling on Milo questions, the owner's number.** The security review (SEC-01, the one
High finding) showed that accounts are free and unverified, so a script registering addresses got a fresh allowance
each time with nothing over them all. `MILO_QUESTIONS_PER_DAY` (default 300) counts the last 24 hours' questions from
guests and free accounts in `milo_questions`, before either allowance is charged; the owner's are left out, and so are
paying readers', who are never refused by it (their plan has its own monthly cap; the cost audit found the first version
refused Pro readers too). It bounds the number of questions, not their cost: about $0.11 a message measured on
2026-10-11, and up to about $1.44 for a question that reaches every limit (cost audit), so a dollar ceiling read from the
ledger is proposed for the owner. 0 switches it off. The default is a guard, not a product limit: the owner sets it, and a
spend limit in the Anthropic console still sits outside the app (BLOCKERS).

**D-077 (Phase 10) Email verification is still not required for Milo.** `require_verified` exists and the review asks for
it, but production has no mail relay (BUG-021, BLOCKED), so requiring a click in an inbox would leave every account on the
guest tier; the code records this as a deliberate choice. The ceiling (D-076) bounds the exposure instead. Revisit when
the owner configures mail.

**D-078 (Phase 10) The client address comes from the edge.** theopticterminal.com resolves to Cloudflare addresses and
uses Cloudflare's name servers (checked 2026-10-30 with a DNS lookup, no request to the site), so `CF-Connecting-IP`,
which Cloudflare sets and overwrites, is the address the rate limits use; `CLIENT_IP_HEADER` and `TRUSTED_PROXY_HOPS`
cover a different edge. A request sent to the platform's own address rather than through Cloudflare can still write the
header: closing the origin to direct traffic is the owner's (BLOCKERS).

**D-079 (Phase 10) Problem reports are read by the signed-in owner only.** Each report carries its reporter's email, so
the write token no longer reads them (`_owner_session_guard`, as on Accounts); both report pages already used the owner's
session with the CSRF header. The token still resolves reports, which returns no personal data. Wrong tokens are limited
to 20 an hour per address.

**D-080 (Phase 10) Classic's `esc` is unchanged.** Escaping the apostrophe changed Classic's markup everywhere (four tests
pinned its text), against the rule that Classic's copy stays word for word. The one single-quoted attribute it fed
(`data-spark`) is double-quoted instead, and a test refuses any new single-quoted interpolation in Classic.

**D-081 (Phase 10) Passkeys keep "preferred" user verification.** The code records the trade-off: "required" would refuse a
hardware key with no PIN. Escalated as a Low finding (SEC-13) for the owner rather than changed.

**D-082 (Phase 10) Session hardening, partly.** Sessions now end 90 days after sign-in however much they are used
(`SESSION_MAX_DAYS`). The `__Host-` cookie names and a CSRF value bound to the session are not changed: renaming the
cookies signs every reader out at the next deploy, which is the owner's call (SEC-14).

**D-083 (Phase 10) Headers added, the full CSP not enforced yet.** `Permissions-Policy` (camera, microphone, location,
payment, USB off; fullscreen and passkeys left alone) and `Cross-Origin-Opener-Policy: same-origin-allow-popups` are set.
Enforcing the full policy needs nonces for the inline import map and theme boot, and `report-to` needs a collector; both
are proposed, not done (SEC-09).

**D-084 (Phase 10) The fonts stay on jsDelivr.** The owner's rule names jsDelivr for Inter and Space Grotesk, so they are
not moved; pinning their versions and adding integrity attributes is proposed (SEC-10, BUG-019).

**D-085 (Phase 10) No dependency scanner was downloaded.** Installing pip-audit (or any scanner) downloads packages, which
needs the owner's approval; the installed versions are listed and a hashed lock file is proposed (SEC-07). BLOCKED.

**D-086 (Phase 10) The open scan buttons stay open.** The tracker scan, marks and catalyst refresh were opened to every
reader at the owner's request ("make sure they work without the need of an API key"); their global spacing bounds them.
The watch check, the owner's unread count, the post-close reading order and the valuation replay were fixed (BUG-072).

**D-087 (Phase 10) Web search is not switched off when a portfolio is attached.** Injected text can arrive in headlines
and filings as well as search results, so turning one source off would not close it. Instead the prompts say that tool
results, search results and files are data, never instructions, and both apps show the host beside every link Milo
writes (SEC-05).

**D-088 (Phase 10) Exception text is scrubbed, not replaced.** Most of the thirty sites carry Optic's own sentences
("needs a positive cash flow") or say usefully what failed, so `app/public_errors.public` removes hosts, URLs and file
paths and keeps the sentence (SEC-16).

**D-089 (Phase 10) A body limit of 2 MB, more for Milo.** Every route takes at most `BODY_MAX_BYTES` (2 MB); the chat and
research routes take four 5 MB attachments in base64 on top. A question is at most 8,000 characters, twice the v2
composer's, so a paragraph pasted into Classic still goes (BUG-112, SEC-03).

**D-090 (Phase 10) Faster search with the same ranking.** The per-row work moved to once a directory and answers are kept
for the directory's day; 8,139 query and limit pairs gave identical results before and after (`tools/phase10_search.py`), and a test pins the
ranking rules (BUG-053).

**D-091 (Phase 10) The desk note is written by the keep-warm job, never by a reader's page load.** BUG-032: the first Home
of the day and up to twelve after it made a paid call, against the owner's rule that reading a page costs nothing. The
note is still written (the owner asked for it to "update whenever necessary"), by the keep-warm job, which runs only while
readers are around, within the same daily bounds (two attempts, twelve rewrites); Home only reads what is kept.
`DESK_PROSE_AUTO=false` leaves Home on the assembled desk.

**D-092 (Phase 10) Starters send; everything else drafts.** BUG-049 asked why the panel's starters send when other entry
points draft. The owner decided on 2026-10-20 that starters "must send meaningful requests"; the code comment that said
every entry point drafts was wrong and is corrected. WONTFIX.

**D-093 (Phase 10) The reader's own blocks travel only with questions about them.** BUG-071: the server leaves a
watchlist's rows, a paper book and its journal, and a retirement plan out of a question that is not about them, and the
panel says so. The test is wide ("my", "these", "here", "list", "book", "plan", "should I", "I own" and the like),
because leaving a block out by mistake costs an answer about the reader's own list.

**D-094 (Phase 10) Measurements under a throttled feed.** The back-to-back A/B of the Phase 09 commit and this tree ran
while Yahoo was refusing this machine (both servers waited the 20 s gate maximum on cold symbols afterwards), so page
timings that depend on cold fetches are recorded as conditions, not as a change; the client-side figures (layout
shift, interaction delay, search, Milo's first words) and the in-process measurements (search cost, event-loop stalls)
are the ones compared.

**D-095 (Phase 11) The commit and uptime are public again.** Phase 10 made them the operator's (BUG-052), but the
owner's `publish.sh` reads `commit` from an anonymous `/api/health` to see a deploy land, and DEPLOY.md reads
`uptime_seconds` to tell a crashloop from a deploy (BUG-181, found by the independent review of Phase 10's commit).
The repository is public, so the deployed commit tells a visitor nothing they cannot read already. Where the AI
credential comes from, whether Anthropic refused it, and the migrations stay the operator's.

**D-096 (Phase 11) A feed host is held back only when it did not answer or refused.** S16's memory (Phase 10) also
counted a 5xx, which is one document's: one EDGAR query's 503 failed the other eleven forms for a minute (BUG-183). A
host that answered costs no timeout to ask again; a 403 or 429 is given to the caller, so the host is left alone for
`HOST_DOWN_SECONDS`.

**D-097 (Phase 11) The desk note says which kind of missing.** With only the keep-warm job writing it (D-091), "could
not be produced" covered three states. `pending` ("is not ready yet") before the day's first attempt, `off` ("is
switched off on this terminal") with `DESK_PROSE_AUTO=false`, and `unwritten` after an attempt failed, told apart by
the store's own attempt count (BUG-186).

**D-098 (Phase 11) How the final audit counts.** A provider's refusal (Yahoo answered 401 "Invalid Crumb" to some
requests during the audit) is a condition, not a defect, when the page states it; a page that leaves a skeleton or
says nothing is a defect whatever the cause. The reader's and the guest's checks run in separate browsers (pages in
one browser share cookies, so a guest's sign-out signed the reader out in the first run, which was discarded). The
demo journey answers the keep sheet the way a presenter would ("Bring them into my account"). Findings from the
independent review were each checked before being acted on.

**D-099 (Phase 11) The advice output check is not widened again; its measure stands.** On fresh set D the check caught
14 of 50 advice sentences (0 of 50 research sentences held back), after Phase 08 widened it on set C, where it had
caught 28 of 50. A rule set tuned on one agent's phrasings did not carry to the next agent's, so another round tuned
on D would only make D a regression set (D-015) and need a set E to measure, with no reason to expect a different
outcome. The check stays as the last of the layers (the request classifier, the prompt's policy, the check), BUG-132
is OPEN, and what would change the picture is the owner's: a model-based reading of each finished answer (BL-07, one
small-model call per answer) and a working key, so the answers themselves can be measured (BL-01).

**D-100 (Phase 11) The final decision is NOT READY.** Directive 11 offers two outcomes. With BUG-132 open (Milo's
advice safeguards measured weak and the model's own behaviour unmeasured) and the market data unlicensed (BUG-022,
BUG-023), the blocking issues are P0 and none can be closed by engineering alone. Everything else passed or is
recorded. The decision names what would unblock each, and the manual checks a human staging review needs
(FINAL_REPORT sections 8 and 17).

**D-101 (after Phase 11) The report-date hotfix shipped on its own.** On 2026-10-31 the owner said yes to shipping the
hotfix of BUG-200 and BUG-201 while this branch stays held (D-100). It went from its own branch, cut from live main and
rebased onto `a10eaba`, so nothing else from this branch reached the live site. This branch carries the same code and
the same test file, so merging it later changes nothing for these two defects.

## Phase 12 (directive 14, 2026-11-02): writing, Milo's evaluation, red team

**D-102 Phase 12 works on its own branch from live main.** The overhaul's branch shipped on 2026-11-01, so Phase 12 is
`phase-12-writing-milo-security` in `~/Optic/wt-phase12`, cut from live `d22522a`, with the same tracking files.
Nothing is pushed or deployed; the directive says so too.

**D-103 Classic gets security fixes only.** The owner's rule is that Classic is left as it is unless asked, and that
ports from Classic keep its analytical copy word for word. Phase 12 therefore inventories and checks Classic's copy
but does not rewrite it. The editorial gate does not fail on Classic. Two security fixes do go into `static/app.js`:
MRT-02's link rule and MRT-03's history guard. Server-written notes change in both apps, since both show them.

**D-104 One set of writing rules for every model request.** `app/editorial.py WRITING_RULES` goes on every request,
after the writer's own prompt and before the advice policy, so the policy reads last. Writer prompts keep their
structure and lose their duplicated voice rules and the invitation to ellipses. `FORMAT_PROMPT` keeps the risk
paragraph and the closing condition but not a fixed **Bottom line** heading. The rules cost about 500 tokens a
request, inside the cached prefix for chat.

**D-105 Copy pinned by the owner's briefs stays word for word.** Where a test pins wording from an owner's brief (the
beginner brief's Home sentences, the Classic glossary), the copy is changed only to fix a real defect, never to
restyle it. My first rewrite of four Home sentences was reverted on these grounds.

**D-106 The benchmark extends Phase 08's suite.** There is no second framework: `tests/milo_eval/cases.py` keeps its
format and gains the directive's suites and fields (`annotate`). Runs are archived per benchmark version and commit
under `docs/ai/eval-results/`. Phase 13 is to reuse this, as directive 15 asks.

**D-107 How the advice checks are measured.** Patterns are written against development sets only, and measured on a
set written afterwards by a separate agent and scored before anyone reads it. A set whose misses have been read
becomes development material. E was scored, then used; F is the held-out measure, kept outside the repository. A
model writing my sets would anchor them on my patterns, so the sets come from an agent told not to read the code.

**D-108 No real-model evaluation.** BL-01 was rechecked on 2026-11-02 and the key is still refused. The answer-level
checks stay ready, with a `--model`, `--suite` and `--trials` runner. Latency is measured end to end with the stand-in
and labelled as Optic's own time.

**D-109 What counts as a server-owned key.** These are the keys the server writes and Milo is told are Optic's own
retrieval: `auto_loaded`, `auto_load_skipped`, `question_named`, `research`, `chart_levels`, `screen_candidates`,
`market`, `portfolio_summary` and the two brokerage keys. `framework` and `track_record` are page data the Overview
sends, so they stay. No v2 or Classic page sends a dropped key (checked by reading every `provideContext` and
Classic's payload).

**D-110 MRT-06 and MRT-07 are left.** Clearing Milo's conversations at sign-out would remove the come-back that the
device shelves exist for; that trade is the owner's. Model-chosen tool inputs write the same shared rows an anonymous
`/api/ticker/{t}?expiries=` already can, so Milo adds no capability.

**D-111 Legal and consent text is flagged, not rewritten.** Two disclaimers that repeat the line above them
(Earnings, Retirement) and the brokerage consent's "count towards your Optic portfolio" are listed for counsel and
the owner (WRITING_CORRECTIONS M).
