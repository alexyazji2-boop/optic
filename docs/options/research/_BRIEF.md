# Options research brief (shared by research agents)

Optic Terminal is a retail research web app (promise: "Complex analysis, presented simply"). Its Options tab
uses free Yahoo Finance chains via yfinance: per contract bid, ask, last, volume, open interest, implied
volatility (Yahoo's own), strike, expiry, in-the-money flag, last trade date. NO trade tape, NO quote sizes,
NO trade conditions, NO aggressor side, NO intraday OI, quotes delayed ~15 min, OI is the prior session's.
It computes Black-Scholes greeks locally, dealer gamma exposure (GEX) and vanna exposure (VEX) by strike,
a gamma flip, call/put walls, put/call ratios, an "unusual activity" list, an IV-rank proxy from realised
vol (no IV history stored), term structure, skew, expected/implied earnings move, an entry plan that picks
contracts, and strategy ideas (verticals, single legs).

## Rules
- Use public sources: exchange documentation (Cboe, Nasdaq, CME where relevant), OCC and the Options
  Industry Council (OIC), SEC/FINRA publications, academic papers (SSRN, journals), broker education/docs
  (Schwab, Fidelity, IBKR, tastytrade), and transparent practitioner methodology write-ups (e.g. SqueezeMetrics
  white papers, SpotGamma/Menthor Q/Cboe research notes where they publish methods). Use WebSearch and WebFetch.
- Never sign up, log in, enter data, purchase, or download files.
- Label every claim: **MATH** (established pricing/risk mathematics), **EMP** (empirically supported, cite
  the study and sample), **HEUR** (practitioner heuristic), **MKT** (marketing/unverified), **PROP**
  (proprietary, cannot be reproduced). Never imply you know an institution's private strategy; note
  conflicting evidence.
- Source URL + date read (2026-10-13) for every claim. Paraphrase; quotes under 15 words.
- WRITE YOUR FILE EARLY (skeleton within minutes) AND UPDATE IT INCREMENTALLY.

## For each approach, record
Source(s) | Rationale | Required data (and whether Yahoo free chains provide it) | Market conditions where it
applies | Weaknesses / failure modes | Implementation cost for Optic | How Optic could validate it.

## End your file with
- A research-to-implementation matrix: approach | evidence type | data available in Optic now? | what to
  build or change | effort (S/M/L) | validation method.
- "What Optic must NOT claim" (common overclaims in this area, with evidence).
- Concrete formulas/definitions Optic should adopt (with units), where established.
Keep it dense and factual, 3,000-5,000 words.
