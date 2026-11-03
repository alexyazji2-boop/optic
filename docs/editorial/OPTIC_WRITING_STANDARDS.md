# Optic's writing standards

The house style for every word Optic shows a reader: interface copy, server-written notes, error and empty states,
and every model's answer. Written in Phase 12 (2026-11-02, directive 14 Parts 2 and 3). It replaces nothing:
`docs/post-demo-ultra/WRITING_GUIDELINES.md` (the ten rules of Phase 04), "Writing for Optic" in the optic-frontend
skill and `docs/frontend-v2/DESIGN-STANDARD.md` still hold, and this page is the fuller version they point to.

The examples are Optic's own, taken from the corrections made in this pass (`WRITING_CORRECTIONS.md` has all of
them). Where a rule is enforced by code, it says where.

## 1. Who Optic sounds like

A financial research editor writing for an intelligent reader. The reader is not necessarily trained, so Optic
explains what needs explaining, once, and never talks down. It is:
- **professional:** specific and calm;
- **direct:** the finding first;
- **plain:** the shorter word, the concrete noun;
- **accurate:** figures, sources and times exactly as the data has them;
- **confident only where the data is:** a measurement is stated, an inference is labelled.

Optic does not sound like a brochure ("powerful insights"), an academic paper, a trading desk talking to itself
("event premium into the print"), or a chatbot ("Great question! Let's dive in").

## 2. The rules

1. **State the most useful information first.** The first sentence answers the section's question. Method, scale
   and caveats come after it, or inside "How this works".
2. **No introductory sentences.** Not "This section shows", "Here you can", "It's important to note".
3. **Vary the sentences.** Three in a row that open the same way read as a template. A sentence with four or more
   commas is usually two sentences.
4. **Say a thing once.** A heading, the sentence under it, the fold and the panel below each say something new. Do
   not repeat a point in different words or close on a summary of what was just said.
5. **Precise over impressive.** "use", not "utilize"; "before", not "prior to"; "cheap", not "attractively valued".
6. **Financial terms used exactly.** "Percentage points" for a change in a rate; "distribution yield" for a fund.
   Price targets are attributed to analysts. Delta is not a probability of profit.
7. **Explain jargon at the reader's level** (section 4), the first time it appears on a page, in the sentence or
   by the dotted glossary term.
8. **Length follows importance.** A tooltip is a phrase, a section's lead is a sentence, a method is a fold.
9. **No filler to reach a length.** A quiet day gets a short note.
10. **No stock conclusions.** "In conclusion", "Ultimately", "Overall" and "Bottom line" restatements go. A closing
    line earns its place by adding something: what would change the read, or what to check next.
11. **Uncertainty is kept where it is real, once.** "The direction of the flow is inferred" is said once, where it
    matters. Not "may potentially", and not a caveat on every sentence.
12. **No exaggeration of what Optic does** (section 8).
13. **Every figure keeps its source and its time**, and every time says which clock it is: prices updated, text
    written, list compiled.
14. **One thing, one name**, everywhere (section 5).
15. **Plain English without losing accuracy.** A simplification that changes the meaning is a mistake, not a
    simplification.

And three house rules that predate this page: no em dashes in reader copy (a colon, comma, full stop or "to"), sentence
case for headings and buttons, and no emoji.

## 3. Weak writing and the correction

| Weak | Better | Rule |
|---|---|---|
| "Optic leverages powerful, cutting-edge AI-driven technology to deliver comprehensive financial market insights." | "Research stocks, follow market data and ask Milo questions in one terminal." | 12, 5 |
| "The RSI indicator, which is widely utilized by traders, provides valuable insights into momentum conditions." | "RSI measures recent price momentum. Readings above 70 are commonly called overbought, and below 30 oversold." | 5, 2 |
| "VIX {level}. Elevated; size down and widen stops" (Macro, before this pass) | "VIX {level}. Elevated: options are pricing wider daily swings" | the advice policy; 6 |
| "Mixed global regime. US and international indices are diverging. Favor the strongest." (Indices) | "{n} of {m} major indices are above their 200-week averages: US and international indices are diverging." | the advice policy; 14 |
| "With no big news today, moves are mostly traders shuffling their bets, so where prices actually end up matters more than any explanation for them." (Optic Desk) | "With no big report today, where prices close says more than any move during the day." | 9, 10 |
| "Interest rates on government bonds are down and the dollar is flat, but one of the two has barely moved, so together they do not tell a clear story." | "Interest rates on government bonds are down and the dollar is flat, so together they give no clear signal." | 4 |
| "A risk to weigh: optic star rating 1 of 5: above its usual valuation range. Optic's fair-value model places the price above the range it treats as usual for this company." | "A risk to weigh: Optic's star rating is 1 of 5 (above its usual valuation range). The rating compares the price with the range Optic's fair-value model treats as usual for this company." | 4, 3 |
| "It reports today." (at 7:25 PM, with the results in the headlines beside it) | "Its report was due today." | 13 |
| "AAPL reports on Mon Nov 2, in 0 days" | "AAPL reports today, Mon Nov 2" | templates must survive 0 and 1 |
| "No consensus (the average of what analysts forecast) estimates" (New to Markets) | the definition goes after the whole phrase, or not inline at all | 7 |
| "We encountered an unexpected issue while attempting to retrieve the requested information. Please try again at a later time." | "Couldn't load market data. Try again." | section 6 |

## 4. Explaining at the reader's level

Optic has five levels, chosen on the slider (`app/knowledge.py`): New to Markets, Beginner, Intermediate (the
default), Advanced and Expert. **A level changes the wording, never the facts:** no level rounds a figure
differently, drops a caveat or a disclosure, hides that something is missing, or changes what the advice policy
declines (the invariant in `knowledge.INVARIANT`).

| Level | Words | Terms | Depth |
|---|---|---|---|
| New to Markets | Everyday words, short sentences | Every term explained in the sentence or by the dotted term, shown inline at this level only | The core idea and one reason |
| Beginner | Plain, some standard terms | A term explained the first time on a page | The idea, the reason and the main caveat |
| Intermediate | Standard financial language | Terms marked to explain themselves on tap | Supporting context, no over-explaining |
| Advanced | Professional language | Not defined | Which readings disagree, the base rate, what would make it wrong |
| Expert | Terminal register | No definitions, no scene-setting | The readings carry the argument; proxies and assumptions labelled in a word |

Rules for the inline definitions at New to Markets (`ui/glossmark.js`, tested in
`tests/test_editorial_standards.py`):
- A definition follows a whole noun phrase. It never goes inside one ("consensus estimates" stays whole).
- A definition shown inline is never marked again, so definitions do not nest.
- An acronym's expansion keeps its capitals ("Earnings Per Share").
- A table cell, a figure's label or a tile's label keeps its mark without a definition inside it.

## 5. Financial terminology

One thing, one name, on every page. The checker reports a variant where it appears (`tests/editorial/rules.py`
`TERMS`, rule I1).

| Say | Not | Why |
|---|---|---|
| Sign in, sign out | log in, login, logout | The app's own buttons |
| Watchlist | watch list | |
| Email | e-mail | |
| Milo | Pulse | Pulse is the assistant's old name (renamed 2026-10-12) |
| P/E | PE ratio | |
| Year over year | year-on-year | |
| Optic's market score (Home, Macro); Index score (Read); Where each index stands (Indices) | "regime" for any of them | Three different models (WRITING_GUIDELINES rule 3) |
| Liquid, Fair, Thin, Too wide to trade, No usable quote | Tight, Wide | The option grades as the table shows them (BUG-010) |
| Move priced by options, one day; Typical day lately; Priced against typical | other wordings of the expected move | X-7 |
| Optic Portfolio: three shared simulated books | "ledger", "paper book" for it | "Paper Desk" is the reader's own simulated trades |
| Distribution yield (funds) | dividend yield, for a fund | |
| Percentage points, for a change in a rate | percent | A margin from 20% to 22% rose 2 points, a 10% rise |

## 6. Errors, empty states and loading

- **An error says what failed and what the reader can do:** "Milo could not answer. Your question is back in the
  box." Never "Something went wrong", never an apology, never an exception's text.
- **An empty state says why it is empty and the next step:** "No alerts yet. Press New alert to watch a price
  level, a day's move, an RSI line, a change in Optic's stance or an earnings date."
- **A missing figure is "Not reported"** or the reason it is missing, and no conclusion is drawn from it.
- **A loading line names what is loading:** "Gathering this week's events and report dates."

## 7. Milo and every other model writer

The rules every model request carries are `app/editorial.py WRITING_RULES`. They are appended after the writer's
own prompt and before the advice policy, so the policy reads last (`ai._ask`, `ai.build_chat_request`,
`ai.deep_research`). The rules:
- start with the answer;
- every sentence adds a fact, a reason, a comparison or a limit;
- plain, precise words;
- no stock phrases;
- varied rhythm;
- structure that follows the content;
- one hedge, where the uncertainty is;
- keep every figure's date and source and everything the policy asks for;
- no ellipses, exclamation marks, em dashes or emoji.

A writer's own prompt keeps its structure: the Earnings brief's headings, the Desk's JSON, Milo's follow-ups and
action cards. The writing rules govern the sentences inside it. Nothing here retrains a model: the rules are
instructions, and the corrections library (`WRITING_CORRECTIONS.md`) is the record of approved changes that new
prompts and copy are written against.

The answer-level checks hold Milo's answers to the same line when a model can be run
(`tests/milo_eval/answer_checks.py`: `no_ai_phrasing`, `no_filler`, `no_repetition`, `level_length`, `well_formed`).

## 8. What Optic never claims

- **Promotional adjectives are prohibited:**
  - always: "revolutionary", "unparalleled", "game-changing", "cutting-edge", "state-of-the-art", "world-class",
    "best-in-class", "unmatched", "next-generation", "AI-powered", "seamless", "empower";
  - unless the sentence also gives the measurement: "powerful", "comprehensive", "robust".
- **No unmeasured effect is stated as a fact:** "Breakouts have follow-through", "Money has been moving here, not
  just visiting" and "A bigger surprise either way is likely" were removed. A score or signal is described as rules
  applied to past data, with its measured record where it has one.
- **No interface copy tells a reader what to do with their money:** no "size down", "widen stops", "favor the
  strongest" or "keep it to a handful of funds". That is the advice policy (`app/ai_policy.py`, COMPLIANCE_REVIEW),
  and it holds for fixed copy as much as for Milo.
- **No development commentary in reader copy:** source paths ("app/valuation/METHODS.md in the source"), "the
  honest framing", "700-name scale", "larger than the terminal shipped with".

## 9. Sources and attribution

- **Every figure names its source and time:**
  - in the panel's line ("Yahoo Finance. Updated 7:18 PM EST");
  - in a tool result's `meta`;
  - in Milo's source tags (`[[src KEY]]`, which become chips).
- **An opinion is attributed:** "analysts rate it a buy", never "it is a buy".
- **A model's words are labelled as a model's:** "Written by an AI model from the figures". Fixed rules' words are
  labelled as rules': "Compiled by fixed rules".
- **News is headlines:** "a headline reported", never what an article argues.
- **A link shows where it goes.** Milo's links carry their host, and an address that hides its host is not a link.

## 10. Legal text

Terms, Privacy, the disclaimers, the brokerage consent and the advice notices are not rewritten here. They are
reviewed and flagged for counsel (BL-02); the inventory marks them `legal`. Two findings of this pass wait on the
owner or counsel:
- two disclaimers that repeat the sentence above them, on Earnings and Retirement;
- the consent's "count towards your Optic portfolio".

## 11. The workflow

- **For new copy**, before review:
  `.venv/bin/python -m tests.editorial.review diff` checks only the texts a branch adds or changes. It fails on an
  `error`, lists warnings for an editor, and needs no API.
- **The gate:** `tests/test_editorial_standards.py` fails the suite on an `error` finding in v2 or server copy. An
  exception needs a reasoned line in `tests/editorial/allow.txt`. Classic is reported and not gated (the owner's
  rule: Classic is left as it is unless asked).
- **The inventory:** `.venv/bin/python -m tests.editorial.review inventory` rewrites `docs/editorial/inventory/`:
  every text with its route, file, line, findings, suggestion and status.
- **The optional model read:**
  `... review diff --ai --dry-run` shows what would be sent and the estimated cost. With `--max-dollars N` and a
  working key it asks the chat model to read the new texts against this page. It never runs from the suite.
- **The library:** every meaningful correction goes into `WRITING_CORRECTIONS.md`, with the original, the revision,
  the reason, the feature and the rule, so the next writer and the next prompt start from approved examples.
- **What the checker cannot do:** judge whether a sentence is clear, true or necessary. It finds the patterns, and
  an editor reads the page. Phase 12 did both: the checker over 18,000 texts, and a line-by-line read of 27 pages at
  three levels.
