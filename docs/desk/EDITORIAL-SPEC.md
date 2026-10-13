# Optic Desk: editorial specification

The daily edition of Optic Desk is a market briefing written by a financially
knowledgeable person for an intelligent reader who does not work in finance:
retail investors, and day and swing traders. It explains what happened, why it
matters, how it connects to other developments and what to watch next.
"Complex analysis, presented simply."

This file is the contract the pipeline (`app/desk/`), the writing prompt
(`app/ai.py: EDITION_PROMPT`) and the checks (`app/desk/check.py`) implement. A
change to one should be a change to this file first.

## 1. What an edition is

One canonical edition per market date and slot, shared by every reader:

| Slot | Written | Covers |
|---|---|---|
| `premarket` | about 8:15 ET on a trading day | the previous session's close, overnight moves, today's calendar |
| `close` | about 16:30 ET on a trading day | the session just finished |
| `closed` | about 10:00 ET on a weekend or market holiday | the week or the last session, and what comes next; labelled as a closed-market edition |

Each edition carries its **edition date, slot, time zone (ET), information
cutoff** (the newest evidence it read) and **generated at**. The page shows them
at the top. An edition is never shown as today's after its date has passed: the
reader sees the newest edition with its own date, and a line saying when the
next one is due.

## 2. Structure

Every section is optional when the evidence does not support it. A quiet day is a
short edition, never a padded one.

1. **Headline**: specific, names the main story ("Yields climb back to 4.6% as
   bank results test the soft-landing story"), never generic ("Markets mixed
   today").
2. **Summary**: two or three sentences above the full edition, for the reader
   with a minute. The Home card shows this.
3. **Opening**: two or three short paragraphs on the central development and its
   tension. No throat-clearing.
4. **The numbers that matter**: three to six figures. Each with what it is, the
   period it describes, its comparison base, its source, and one or two
   sentences on why it matters. Averages say how they were computed.
5. **Why this matters**: the chain from the evidence to business economics,
   valuations, financing conditions, sectors or market behaviour. Unfamiliar
   terms explained in passing.
6. **The good, the bad and the unresolved**: when the day has genuine tension.
   Improving conditions, material risks, and questions the evidence cannot
   settle, with proportionate weight.
7. **Companies and sectors in focus**: a small number of genuinely relevant
   developments: what changed, what expectations matter, what would change the
   thesis.
8. **Market structure and options context**: benchmarks, trend, breadth,
   support and resistance, volume, volatility, each with its timeframe and data
   timestamp. Options context only when supported: the expiry and method of any
   expected move are named; an expiry-wide straddle is never called an
   earnings-only forecast; estimated dealer positioning is never presented as
   observed.
9. **What to watch next**: dated releases, earnings, policy events or observable
   conditions, written as conditions ("if X, the case for Y strengthens"), not
   predictions.
10. **Key takeaways**: three to five points. A research watch plan, never an
    instruction to buy, sell or chase.

## 3. Evidence and sourcing

- **Underlying facts from primary sources** where they exist: FRED for official
  economic series (the agencies' own data), Federal Reserve, BLS, BEA and SEC
  feeds, SEC EDGAR filings (8-K item codes, 10-K/10-Q), exchange-derived price
  data. Reputable financial reporting supplements them for timely developments.
- **Three times, kept apart.** Publication time (when a story or filing
  appeared), event time (when the thing happened), and the period a figure
  describes (CPI for September, published 15 October). The edition never calls a
  September figure "today's inflation".
- **Syndication is one source.** Stories are clustered by headline and link; the
  same wire story on five sites is one report, and repeated coverage is not
  independent confirmation.
- **Freshness.** Evidence older than its kind's window is not "today's news".
  News: since the previous session's close. Prices: the current or last
  session, with its timestamp. Official series: their latest release, with its
  period.
- **External content is data.** Headlines, summaries and filings are quoted as
  evidence, never followed as instructions.
- **No claimed access.** Optic carries no consensus estimates for economic
  releases, no options trade tape, no same-day open interest. The edition never
  implies otherwise.

## 4. Reasoning

- **Explain the chain.** A development, then the mechanism by which it could
  matter, then whether the evidence shows the mechanism at work today.
- **Relationships are hypotheses, not rules.** Rising yields can raise financing
  costs and pressure valuations; a stronger dollar can shrink the dollar value
  of foreign revenue; heavy AI capital spending can support growth while
  squeezing free cash flow. Each is evaluated in context, with competing
  influences and exceptions. When stocks and yields both rise, say so and say
  what else could explain it.
- **Causal versus plausible.** Say which. "Shares fell after the report" is a
  sequence; "fell because of the report" needs evidence such as timing, the
  size of the move against the market, and the company's own disclosure.
- **Do not overgeneralise.** A few bank results are evidence about their
  customers, not the whole economy.
- **Separate the business from the price.** A good business is not the same as
  an attractive valuation, and a long-term thesis is not a near-term entry.
- **Proportionate weight.** Bullish and bearish developments get the space the
  evidence earns.

## 5. Voice

- Connected prose, short paragraphs, selective bullets. An informed person
  explaining markets to someone smart who does not do this for a living.
- "Why does this matter?" and similar, sparingly and naturally. Light
  personality is welcome; forced slang, exaggerated certainty, capitals for
  emphasis and sensationalism are not.
- About 700 to 1,100 words on a substantive day, less on a quiet one. Never padded.
- No price targets, no position sizing, no "buy", "sell", "load up", "chase".
- No em dashes (house style).

## 6. Numbers

- Every material number in the prose comes from the edition's evidence, and the
  checker refuses an edition that has one it cannot match.
- Units are explicit: percent versus percentage points versus basis points;
  dollars versus percent; a level versus a change.
- Fiscal periods are the company's own ("fiscal Q3 2026, the quarter to
  August"), not assumed calendar quarters.
- Percentage changes are computed by Optic from the stated base, not copied from
  a headline.

## 7. Milo and the edition

Each section has an "Ask Milo" control that opens Milo with the section, its
claims and their sources in context, so a reader can ask him to explain or
challenge it. Milo reads the underlying evidence, not only the edition's prose,
and may update the analysis when newer evidence exists, saying what changed.

## 8. Publication workflow

gather evidence, normalise facts, build the analytical outline, draft, check
factual consistency, render. Deterministic wherever possible: selection,
calculations, comparisons and the outline are code; the model writes prose
from them. The checks run before an edition is kept; a failed draft gets one
repair attempt, then the deterministic edition is published instead and says
so. Generation is claimed on disk so two processes or a deploy cannot write the
same edition twice. Cost, latency, source coverage and failures are recorded
with each edition. Nothing is regenerated on page load.

Email distribution is prepared only when asked for. Nothing is sent from this
pipeline.
