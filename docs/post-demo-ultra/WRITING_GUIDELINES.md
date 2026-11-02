# Writing guidelines for Optic's interface

Post-demo overhaul, Phase 04 (directive 04, section 6). These apply to every label, description, tooltip, placeholder,
empty and error state, and to the instructions Milo is given about how to explain. They extend "Writing for Optic" in
the optic-frontend skill and `docs/frontend-v2/DESIGN-STANDARD.md`; where those say more, they still hold. The advice
policy (`app/ai_policy.py`, COMPLIANCE_REVIEW.md) sits above all of this: no wording may recommend a trade.

Each rule has an example from the product, mostly from changes made in this pass. They are writing rules, not evidence
that readers understand the result; no reader was tested (directive 04, section 1).

## 1. The main finding first

The first sentence of a section answers the section's question. Method, scale and caveats come after it, or inside
"How this works".

- Before: "These four are graded separately, each by its own stated rules (method research-1.0, policy policy-2026-10-14), and none has been shown to predict returns."
- After: "These four are graded separately, each by its own stated rules, and none has been shown to predict returns." The method and policy ids are in the fold (BUG-009).

## 2. Explain a term before relying on it, once

A term a newcomer may not know is either the dotted glossary word (`term()`), which explains itself where it appears,
or a plain phrase. A page does not explain the same thing twice.

- Before: each of 20 earnings rows on Read ended "An earnings report resets the estimate the price is built on, which is why the option market charges more into it."
- After: the sentence appears once, under the list (BUG-076).

## 3. One thing, one name

A model, a figure or a setting has the same name on every page. Two different models never share a name.

- "Regime" named three models: the macro score (Home, Macro), the index score (Read) and each index's long-term phase
  (Indices). Now: **Optic's market score** on Home and Macro; **Index score** on Read, which says it is a different
  measure; **Where each index stands** on Indices (registry B X-6).
- The expected move's three figures had two label sets. Now both pages say **Move priced by options, one day**,
  **Typical day lately** and **Priced against typical** (X-7).

## 4. Words that describe the whole thing they label

A word must describe everything that went into it.

- Before: "Tight 3.2%" beside "Fair 0.3%". The grade weighed open interest and volume, but the word described the spread.
- After: **Liquid**, **Fair**, **Thin**, and **Too wide to trade** or **No usable quote** when it cannot be traded, with "spread 3.2%" written beside the word (BUG-010).

## 5. Every time says what it measures

A time names its clock: when prices were taken, when words were written, when a list was read.

- "Prices as of 10:05 AM EDT" (Explore's sectors, the fund boards), "Weekly closes through Oct 23. This week counts at the latest price." (Indices, on a Thursday: the current week's bar is dated Friday, so the line names the last finished week), "Last price
  as of ..." (an instrument), "Compared as of ..." (Compare): five pages had no time at all (X-10).
- The Desk's footer said when the page was assembled. It now says **Written** with the note's own time, or
  **Compiled** for the version built by fixed rules (H-2).

## 6. Short sentences, plain verbs, no filler

Cut "Here you can", "This section shows", "Simply", "Powerful", "Seamless" and similar openers. Buttons say what
happens: "Show all 212", "Update panels", "Type a ticker to add, such as SPY."

## 7. Say what happened, and what to do next

When a press cannot do anything, say why and what to do. Never leave the press silent.

- "Update panels" with the box already on SPY did nothing. It now says "The linked panels already show SPY." (BUG-075)
- An empty Add on the chart's watchlist now says "Type a ticker to add, such as SPY."

## 8. Colour carries direction, never opinion

Green and red mark a figure that rose or fell. A firm's Buy, Hold or Sell is an opinion, so all three are ink; the
Action column carries the change. A heatmap's strength is scaled to a fixed size of move, so a quiet day looks quiet
(BUG-077).

## 9. Never more certain than the data

Do not simplify until the meaning changes. Missing data says "Not reported" or why. A score that has not been shown
to predict returns says so where it is shown. A model's words are labelled as a model's ("Written by an AI model from
the figures"), and rules' words as rules' ("Compiled by fixed rules").

## 10. Numbers and sources stay one step away, never gone

Simple view folds the specialist research; it does not delete it. A figure's source and method are in its panel's
details or the "How this works" fold, and Advanced (or one press) opens them.

## Applying the rules

- New copy: check it against these ten rules before review.
- Tests pin the wording where it carries meaning: `tests/test_v2_simplicity.py` (names, times, colour, presses) and
  `tests/test_v2_checklist.py` (no em dashes, no emoji).
- Navigation names (the rail, its fly-outs and the phone bar) are not changed by these rules. A rename needs the
  owner's yes (the owner's standing rule; D-023). SIMPLICITY_AUDIT.md lists the names proposed for the owner.
