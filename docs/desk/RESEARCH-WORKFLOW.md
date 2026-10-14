# Optic Desk: research and publication workflow

The editorial rules are in `EDITORIAL-SPEC.md`. This file is the machinery: where
the evidence comes from, how an edition is built and kept, how Milo retrieves
sources, what it costs and what it cannot see. A sample edition is in
`samples/2026-10-13-close.md`.

## 1. Sources (all free, all keyless; inspected before building)

| Kind | Source | Module | Freshness | Notes |
|---|---|---|---|---|
| Index, sector, company moves | Yahoo daily bars | `providers/yf.py batch_history` | 5 min cache; about 15 min delayed in session | Close to close; the last bar forms during the session |
| Yields, dollar, oil, gold, copper, HYG, VIX, futures | Yahoo quotes via the macro strip | `analytics/macro.py` | 30 s quotes | Yield changes computed in bp from two closes, not the feed's percent-of-yield |
| Official series | FRED CSV (agencies' own data) | `analytics/econ.py` | 6 h | DGS2, DGS10, T10Y2Y, DFF, CPI, core PCE, UNRATE, PAYEMS, ICSA, HY OAS, breakevens, mortgage rate; each keeps the period it describes |
| Calendar | BLS schedule, FOMC, expiries | `events.py` | as published | Previous print from the agency's release; no consensus (licensed) |
| Rate path | CME fed funds futures via Yahoo | `morning_desk.rate_path` | 30 s | Shared helper `main._rate_path_for` so the card and the edition agree |
| Earnings | Yahoo calendar and history | `earnings_week.py`, `yf.earnings_history` | 1 h | EPS only; two consensus figures that can disagree (flagged) |
| News | RSS (CNBC, MarketWatch, WSJ, FT, BBC, NPR, OilPrice, Fed, BLS, BEA, SEC...) | `feeds.py` | 15 min | Each source carries `access` (open, metered, paid); paid stories are headline and link only |
| Options | Yahoo chains, Optic's surface | `analytics/vol_surface.py` | 60 s chain | SPY and QQQ expected moves by named expiry; IV30 |
| Filings (Milo) | SEC EDGAR submissions, 10-K text | `analytics/filings.py`, `analytics/business.py` | 1 h / 6 h | Needs `FEED_CONTACT` |
| Fundamentals (Milo) | Yahoo statements | `yf.financials` | 1 h | Revenue, margins, OCF, capex, FCF, buybacks, SBC, diluted shares, debt |

Not available from any free source, and never implied: consensus forecasts for
economic releases, reported revenue against its estimate, guidance text and
management commentary, the options trade tape, same-day open interest, quote
sizes. yfinance and the Robinhood overnight feed are unofficial interfaces.

## 2. Stages (`app/desk/`)

1. **Gather** (`evidence.py`, wired by `main._desk_sources`): every fact as an
   `Evidence` row with source, link, publication time, event time, period,
   comparison base and method. Each leg fails independently into `coverage`.
   News starts at the regular close before the session the edition covers.
   Stories are clustered (`model.cluster`): the same event across outlets is one
   report with an outlet count, never independent confirmation.
2. **Outline** (`outline.py`): deterministic. Salience is a move against the
   instrument's own typical close-to-close day (20 sessions). The lead theme,
   the tension (a high-impact release within two days), three to six numbers,
   relationship tests with a status, companies, leaders and laggards, what to
   watch, conflicts, limits and the word target (700 to 1,100; 350 to 650 on a
   quiet day).
3. **Draft** (`ai.write_edition`, `EDITION_PROMPT`): the model writes JSON whose
   every unit cites evidence ids, from the outline and the evidence it uses only.
4. **Check** (`check.py`): numbers against cited evidence at the written
   precision (or a difference of two cited figures, a figure quoted from a cited
   headline, or a thousands-scaled figure written in full); units; conflicting
   consensus; expected-move expiry and the earnings caveat; dealer estimates;
   advice; em dashes; shouting; stale-as-today; month mismatches; length.
5. **Repair once**, then **assemble** (`assemble.py`): a refused draft is sent
   back with the checker's list; a second refusal, no model, or a model error
   publishes the deterministic edition, which passes the same checks.
6. **Keep** (`edition.py`): one row per `date:slot` in `desk_editions.db`, with
   the edition, the evidence it cites, the outline's relationships and limits,
   and metrics.

## 3. Schedule and serving

| Setting | Default | Meaning |
|---|---|---|
| `DESK_EDITION_AUTO` | `false` | Turn the five-minute loop on (`main._edition_loop`) |
| `DESK_EDITION_TIMES` | `premarket=08:15,close=16:30,closed=10:00` | ET times per slot |
| `DESK_EDITION_TOKENS` | `8000` | Output ceiling per draft |

Trading days get `premarket` and `close`; weekends and NYSE holidays get
`closed` (`session.market_holidays`). A slot is claimed in `ai_store` (two
attempts, 30 minutes apart) so a deploy or a second process cannot write it
twice. `GET /api/desk/edition` only reads: it serves the due edition, else the
newest kept one with `is_today` and a freshness line ("from 2026-10-13; today's
has not been published"), and when the next is due. `POST
/api/desk/edition/publish` (write-guarded) publishes now, optionally `force`
and `test_label`. The Home card shows the headline and summary with its date;
the Read page shows the whole edition.

## 4. Metrics kept with each edition

Stage timings (gather, outline, draft, repair, assemble), total time, model
calls with tokens and cost (`ai_store.cost` at list prices, also in the usage
ledger under "Optic Desk daily edition"), coverage per leg, failed legs,
evidence counts by kind, and the check result (errors, warnings, words,
numbers verified, and the refused draft's errors when the assembled edition
was published).

Measured locally on 2026-10-13: the gather took 146 s on a cold cache (with the
test suite running alongside) and is the slow stage; outline and checks take a
few milliseconds. A written edition is one Opus call of about 15,000 input and
2,500 to 4,000 output tokens, roughly $0.10 to $0.15 at list prices, plus at
most one repair: under $1 a trading day for two editions, about $20 a month.

## 5. Milo's research pack (`research.py`)

`main._with_research` runs on every chat question (scope "none" excepted):
`intent` picks long_term, pre_earnings, day_trade, swing, macro or desk from
the question and the reader's saved horizon; the plan for that intent runs in
parallel with an 8-second budget, a slow source being skipped and named. Items
carry source, link, period and timestamp; `not_available` names what the free
data lacks. Banks and insurers get no free cash flow or capex (meaningless for
lenders). A Desk question carries the section's text and its cited evidence,
with prices re-read so Milo can say what moved since publication. The prompt
(`SYSTEM_PROMPT`) tells him to choose evidence by the question, lead with the
assessment, cite `research`, and treat the Desk as analysis rather than a source.

## 6. Running it locally

```
cd ~/Optic/wt-desk
TRACKER_DATA_DIR=/tmp/desk .venv/bin/python -c "import app.main as m; print(m._publish_edition('close', force=True, test_label='Local test'))"
```

Without `ANTHROPIC_API_KEY` this publishes the assembled edition. Email
distribution is not built; nothing here sends anything.
